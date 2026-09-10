"""specs/features/0349-verwaiste-bildkopien-aufraeumen.md, ADR 0076: die async-Klammer um den
Verzeichnisdurchgang.

Die Ebene, auf der die GUELTIGKEITSMENGE geprueft wird - Fotos werden direkt als `Photo`-Zeilen
angelegt, ohne Scan und ohne Fake-Client. Die reinen Funktionen darunter
(`collect_cache_entries`/`delete_orphaned_entries`) sind in `test_thumbnails.py` geprueft, die
Anbindung an den Lauf in `test_worker_scan_project.py`.
"""

from __future__ import annotations

import os
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import cache_cleanup
from photosort.cache_cleanup import CACHE_CLEANUP_GRACE_SECONDS, cleanup_orphaned_cache
from photosort.models import Photo, Project
from photosort.thumbnails import CacheSweepResult, display_path, thumbnail_path

# Optionale Anfuehrungszeichen und ein optionales Schema-Praefix: der Dialekt entscheidet, ob
# `FROM photos`, `FROM "photos"` (Postgres/SQLite), `FROM \`photos\`` (MySQL) oder
# `FROM "public"."photos"` gerendert wird. Ohne die Quotes traefe das Muster beim ersten Dialekt-
# wechsel nicht mehr, und der Reihenfolge-Test unten wuerde rot, ohne dass sich an der geprueften
# Reihenfolge etwas geaendert haette. Das `\b` hinter `photos` haelt `photos_archive` draussen.
_QUOTE = r'["`]?'
_PHOTO_SELECT = re.compile(
    rf"\s*SELECT\b.*\bFROM\s+(?:{_QUOTE}\w+{_QUOTE}\s*\.\s*)?{_QUOTE}photos\b{_QUOTE}",
    re.IGNORECASE | re.DOTALL,
)

_LOGGER_NAME = "photosort.cache_cleanup"

# Weit ausserhalb bzw. innerhalb der Schonfrist - die Sekundengenauigkeit der Umrechnung ist
# nirgends Gegenstand, nur ihre Groessenordnung.
_LANGE_HER = 30 * 24 * 3600.0


def _now() -> float:
    import time

    return time.time()


async def _make_project(session: AsyncSession, name: str) -> Project:
    project = Project(name=name, opencloud_drive_id="drive-1", opencloud_path=name)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_photo(
    session: AsyncSession, project_id: int, relative_path: str, etag: str
) -> Photo:
    moment = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    photo = Photo(
        project_id=project_id,
        relative_path=relative_path,
        etag=etag,
        content_length=10,
        taken_at=moment,
        last_modified=moment,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


def _write_aged(path: Path, size: int, age_seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    moment = _now() - age_seconds
    os.utime(path, (moment, moment))
    return path


@contextmanager
def _recorded_photo_selects(events: list[str]) -> Iterator[None]:
    """Traegt jedes tatsaechlich abgesetzte `SELECT ... FROM photos` in die GEMEINSAME
    Ereignisliste ein.

    Bewusst dieselbe Liste wie der Verzeichnis-Spion: zwei getrennte Listen waeren kein
    Reihenfolgebeweis. Muster wie in `test_project_deletion.py`."""

    def _listener(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if _PHOTO_SELECT.match(statement):
            events.append("datenbank")

    event.listen(Engine, "before_cursor_execute", _listener)
    try:
        yield
    finally:
        event.remove(Engine, "before_cursor_execute", _listener)


async def test_files_of_photos_in_other_projects_are_never_touched(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Akzeptanzkriterium 3 und Security-Muss-Kriterium 4: die Gueltigkeitsmenge ist
    ungefiltert. Ein Aufbau mit nur EINEM Projekt hielte ein versehentliches
    `where(project_id == ...)` nicht auf - und genau das waere der naheliegendste Fehler dieser
    Bauform."""
    project_a = await _make_project(db_session, "Costa Rica")
    project_b = await _make_project(db_session, "Island")
    photo_a = await _add_photo(db_session, project_a.id, "Costa Rica/a.jpg", "etag-a")
    photo_b = await _add_photo(db_session, project_b.id, "Island/b.jpg", "etag-b")
    file_a = _write_aged(thumbnail_path(tmp_path, photo_a.id, "etag-a"), 100, _LANGE_HER)
    file_b = _write_aged(thumbnail_path(tmp_path, photo_b.id, "etag-b"), 100, _LANGE_HER)
    orphan = _write_aged(thumbnail_path(tmp_path, 9999, "etag-weg"), 300, _LANGE_HER)

    result = await cleanup_orphaned_cache(db_session, tmp_path)

    assert not orphan.exists()
    assert file_a.is_file()
    assert file_b.is_file()
    assert result == CacheSweepResult(
        deleted_files=1, freed_bytes=300, failed_files=0, kept_recent=0
    )


async def test_files_under_a_stale_etag_go_while_the_current_ones_stay(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Akzeptanzkriterium 2, erster Entstehungsweg: ein Foto hat auf OpenCloud eine neue Fassung
    bekommen."""
    project = await _make_project(db_session, "Costa Rica")
    photo = await _add_photo(db_session, project.id, "Costa Rica/a.jpg", "etag-neu")
    stale_thumb = _write_aged(thumbnail_path(tmp_path, photo.id, "etag-alt"), 100, _LANGE_HER)
    stale_display = _write_aged(display_path(tmp_path, photo.id, "etag-alt"), 200, _LANGE_HER)
    current = _write_aged(thumbnail_path(tmp_path, photo.id, "etag-neu"), 100, _LANGE_HER)

    result = await cleanup_orphaned_cache(db_session, tmp_path)

    assert not stale_thumb.exists()
    assert not stale_display.exists()
    assert current.is_file()
    assert result.deleted_files == 2
    assert result.freed_bytes == 300


async def test_files_of_a_photo_removed_from_the_database_go(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Akzeptanzkriterium 2, zweiter Entstehungsweg: das Foto ist auf OpenCloud verschwunden und
    wurde beim Scan aus PhotoSort entfernt - es gibt gar keine Zeile mehr."""
    project = await _make_project(db_session, "Costa Rica")
    survivor = await _add_photo(db_session, project.id, "Costa Rica/a.jpg", "etag-a")
    gone = _write_aged(thumbnail_path(tmp_path, 4242, "etag-weg"), 100, _LANGE_HER)
    kept = _write_aged(thumbnail_path(tmp_path, survivor.id, "etag-a"), 100, _LANGE_HER)

    await cleanup_orphaned_cache(db_session, tmp_path)

    assert not gone.exists()
    assert kept.is_file()


async def test_files_of_a_deleted_project_go_while_another_project_keeps_its_own(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Akzeptanzkriterium 2, dritter Entstehungsweg: ein Projekt wurde geloescht und das
    Aufraeumen seiner Kopien schlug damals fehl."""
    project = await _make_project(db_session, "Island")
    photo = await _add_photo(db_session, project.id, "Island/b.jpg", "etag-b")
    leftovers = [
        _write_aged(thumbnail_path(tmp_path, 5000 + index, "etag-x"), 100, _LANGE_HER)
        for index in range(3)
    ]
    kept = _write_aged(display_path(tmp_path, photo.id, "etag-b"), 100, _LANGE_HER)

    result = await cleanup_orphaned_cache(db_session, tmp_path)

    assert [leftover.exists() for leftover in leftovers] == [False, False, False]
    assert kept.is_file()
    assert result.deleted_files == 3


async def test_the_grace_period_protects_a_young_orphan_and_releases_an_old_one(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Hier - und nur hier - wird die Umrechnung "Konstante -> Grenze" geprueft, mit
    grosszuegigem Abstand statt auf die Sekunde genau."""
    project = await _make_project(db_session, "Costa Rica")
    await _add_photo(db_session, project.id, "Costa Rica/a.jpg", "etag-a")
    young = _write_aged(thumbnail_path(tmp_path, 9001, "etag-weg"), 100, 60.0)
    old = _write_aged(
        thumbnail_path(tmp_path, 9002, "etag-weg"), 100, CACHE_CLEANUP_GRACE_SECONDS + 60.0
    )

    result = await cleanup_orphaned_cache(db_session, tmp_path)

    assert young.is_file()
    assert not old.exists()
    assert result == CacheSweepResult(
        deleted_files=1, freed_bytes=100, failed_files=0, kept_recent=1
    )


def test_the_grace_period_is_one_hour() -> None:
    """Festgenagelt, damit ein stilles Absenken auffaellt: Akzeptanzkriterium 4 haengt allein an
    dieser Zahl. Der Wert ist bewusst eine Konstante und keine Umgebungsvariable - ein
    Korrektheitsabstand, kein Betriebsparameter."""
    assert CACHE_CLEANUP_GRACE_SECONDS == 3600


async def test_the_directory_is_read_before_the_database_snapshot(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Reihenfolge ist Teil der Loesung: nur so ist JEDE Zeile, die zwischen Aufnahme und
    Schnappschuss committet wird, im Schnappschuss enthalten und schuetzt ihre Datei. Umgekehrt
    waere jede in diesem Fenster sichtbar gewordene Datei ungeschuetzt."""
    project = await _make_project(db_session, "Costa Rica")
    photo = await _add_photo(db_session, project.id, "Costa Rica/a.jpg", "etag-a")
    _write_aged(thumbnail_path(tmp_path, photo.id, "etag-a"), 100, _LANGE_HER)
    _write_aged(thumbnail_path(tmp_path, 9999, "etag-weg"), 100, _LANGE_HER)

    events: list[str] = []
    real_collect = cache_cleanup.collect_cache_entries

    def _spy(cache_dir: Path) -> Any:
        events.append("verzeichnis")
        return real_collect(cache_dir)

    monkeypatch.setattr(cache_cleanup, "collect_cache_entries", _spy)

    with _recorded_photo_selects(events):
        await cleanup_orphaned_cache(db_session, tmp_path)

    assert events == ["verzeichnis", "datenbank"]


async def test_both_file_steps_run_outside_the_event_loop(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bisher stand diese Zusage nur in Docstrings: beide Dateiteile laufen ueber
    `asyncio.to_thread`, damit die Event-Loop bei mehreren tausend `stat`-/`unlink`-Aufrufen
    nicht blockiert."""
    project = await _make_project(db_session, "Costa Rica")
    photo = await _add_photo(db_session, project.id, "Costa Rica/a.jpg", "etag-a")
    _write_aged(thumbnail_path(tmp_path, photo.id, "etag-a"), 100, _LANGE_HER)
    _write_aged(thumbnail_path(tmp_path, 9999, "etag-weg"), 100, _LANGE_HER)

    idents: dict[str, int] = {}
    real_collect = cache_cleanup.collect_cache_entries
    real_delete = cache_cleanup.delete_orphaned_entries

    def _collect_spy(cache_dir: Path) -> Any:
        idents["collect"] = threading.get_ident()
        return real_collect(cache_dir)

    def _delete_spy(entries: Any, valid_keys: Any, mtime_cutoff: float) -> Any:
        idents["delete"] = threading.get_ident()
        return real_delete(entries, valid_keys, mtime_cutoff)

    monkeypatch.setattr(cache_cleanup, "collect_cache_entries", _collect_spy)
    monkeypatch.setattr(cache_cleanup, "delete_orphaned_entries", _delete_spy)

    await cleanup_orphaned_cache(db_session, tmp_path)

    assert idents["collect"] != threading.get_ident()
    assert idents["delete"] != threading.get_ident()


async def test_exactly_one_info_line_summarises_the_run_and_carries_no_path(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Die Abschlusszeile besteht aus reinen Zahlen. Pfade stehen ausschliesslich in der
    WARNING-Zeile eines Einzelfehlers (Security-Muss-Kriterium 6)."""
    project = await _make_project(db_session, "Costa Rica")
    await _add_photo(db_session, project.id, "Costa Rica/a.jpg", "etag-a")
    orphan = _write_aged(thumbnail_path(tmp_path, 9999, "etag-weg"), 300, _LANGE_HER)
    young = _write_aged(thumbnail_path(tmp_path, 9998, "etag-weg"), 100, 60.0)

    with caplog.at_level("INFO", logger=_LOGGER_NAME):
        await cleanup_orphaned_cache(db_session, tmp_path)

    records = [record for record in caplog.records if record.name == _LOGGER_NAME]
    assert len(records) == 1
    assert records[0].levelname == "INFO"
    # Gegen `args` statt gegen Teilzeichenketten der Meldung: die vier Werte sind einander
    # gefaehrlich aehnlich ("0" ist Teil von "300"), und eine Substring-Pruefung bliebe gruen,
    # wenn entfernt/freigegeben/fehlgeschlagen/behalten VERTAUSCHT in der Zeile stuenden.
    assert records[0].args == (1, 300, 0, 1)
    message = records[0].getMessage()
    assert str(orphan) not in message
    assert str(young) not in message
    assert str(tmp_path) not in message


async def test_a_missing_cache_directory_is_not_an_error(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    project = await _make_project(db_session, "Costa Rica")
    await _add_photo(db_session, project.id, "Costa Rica/a.jpg", "etag-a")

    with caplog.at_level("INFO", logger=_LOGGER_NAME):
        result = await cleanup_orphaned_cache(db_session, tmp_path / "gibt-es-nicht")

    assert result == CacheSweepResult(
        deleted_files=0, freed_bytes=0, failed_files=0, kept_recent=0
    )
    assert [record.name for record in caplog.records if record.name == _LOGGER_NAME] == [
        _LOGGER_NAME
    ]
