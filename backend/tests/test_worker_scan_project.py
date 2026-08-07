from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import worker
from photosort.db import make_session_factory
from photosort.models import Photo, Project, ScanRun, ScanStatus
from photosort.opencloud.client import Drive, OpenCloudError
from photosort.opencloud.webdav_xml import DavEntry
from photosort.thumbnails import display_path, thumbnail_path
from photosort.worker import run_project_scan

DRIVE = Drive(id="drive-1", name="Family", drive_type="project", webdav_url="https://cloud.example.com/dav/spaces/drive-1")


def _entry(name: str, etag: str, last_modified: datetime, content_length: int = 100) -> DavEntry:
    return DavEntry(
        href=f"/dav/spaces/drive-1/CostaRica/{name}",
        name=name,
        is_collection=False,
        etag=etag,
        last_modified=last_modified,
        content_length=content_length,
    )


def _jpeg_bytes() -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (20, 10), color="blue").save(buffer, format="JPEG")
    return buffer.getvalue()


class FakeOpenCloudClient:
    def __init__(
        self,
        entries: list[tuple[str, DavEntry]],
        file_contents: dict[str, bytes] | None = None,
        fail_with: OpenCloudError | None = None,
    ) -> None:
        self._entries = entries
        self._file_contents = file_contents or {}
        self._fail_with = fail_with
        self.range_requests: list[str] = []
        self.download_requests: list[str] = []

    async def resolve_drive(self, name: str | None) -> Drive:
        if self._fail_with:
            raise self._fail_with
        return DRIVE

    async def walk(self, webdav_url: str, root_path: str) -> AsyncIterator[tuple[str, DavEntry]]:
        for item in self._entries:
            yield item

    async def get_range(self, webdav_url: str, relative_path: str, length: int) -> bytes:
        self.range_requests.append(relative_path)
        return self._file_contents.get(relative_path, b"")

    async def download(self, webdav_url: str, relative_path: str) -> bytes:
        self.download_requests.append(relative_path)
        return self._file_contents.get(relative_path, b"")


class WalkFailsMidwayClient(FakeOpenCloudClient):
    """Simuliert einen WebDAV-Abbruch mitten im Ordnerbaum-Durchlauf: `walk()` liefert einige
    Eintraege und wirft danach OpenCloudError, statt (wie bei fail_with) sofort in resolve_drive
    zu scheitern. Belegt den periodischen Zwischen-Commit von scan_run.files_found
    (specs/features/0022-scan-live-fortschrittszaehler.md)."""

    async def walk(self, webdav_url: str, root_path: str) -> AsyncIterator[tuple[str, DavEntry]]:
        for item in self._entries:
            yield item
        raise OpenCloudError("WebDAV-Verbindung waehrend des Durchlaufs verloren")


class WalkFailsWithUnexpectedErrorClient(FakeOpenCloudClient):
    """Terminierungs-Fix (specs/features/0023-scan-fortschritt-batch-groesse-fix.md): simuliert
    eine unerwartete, NICHT-OpenCloudError-Exception mitten im Scan-Loop (z.B. ein Bug im
    XML-Parsing oder eine andere heute unbekannte Fehlerquelle). Vor dem Fix lief das ungefangen
    durch run_project_scan durch, der ScanRun blieb dauerhaft auf status="running" haengen."""

    async def walk(self, webdav_url: str, root_path: str) -> AsyncIterator[tuple[str, DavEntry]]:
        for item in self._entries:
            yield item
        raise RuntimeError("Unerwarteter Parsing-Fehler")


async def _make_project(session: AsyncSession) -> Project:
    project = Project(name="Costa Rica", opencloud_drive_id="drive-1", opencloud_path="CostaRica")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def test_scan_adds_new_photos(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = FakeOpenCloudClient(
        entries=[
            ("CostaRica/img001.png", _entry("img001.png", "etag-1", modified)),
        ]
    )

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.status == ScanStatus.SUCCESS
    assert scan_run.photos_added == 1
    assert scan_run.files_found == 1
    assert scan_run.files_skipped == 0

    result = await db_session.execute(select(Photo).where(Photo.project_id == project.id))
    photos = result.scalars().all()
    assert len(photos) == 1
    assert photos[0].relative_path == "CostaRica/img001.png"
    # PNG: EXIF not attempted, falls back to last_modified (stored as naive UTC)
    assert photos[0].taken_at == modified.replace(tzinfo=None)


async def test_scan_updates_photo_on_etag_change(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    db_session.add(
        Photo(
            project_id=project.id,
            relative_path="CostaRica/img001.png",
            etag="old-etag",
            content_length=10,
            taken_at=modified,
            last_modified=modified,
        )
    )
    await db_session.commit()

    new_modified = datetime(2023, 8, 16, 10, 0, tzinfo=UTC)
    client = FakeOpenCloudClient(
        entries=[("CostaRica/img001.png", _entry("img001.png", "new-etag", new_modified))]
    )

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.photos_added == 0
    assert scan_run.photos_updated == 1
    photo = (await db_session.execute(select(Photo))).scalar_one()
    assert photo.etag == "new-etag"


async def test_scan_skips_photo_with_unchanged_etag(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    db_session.add(
        Photo(
            project_id=project.id,
            relative_path="CostaRica/img001.jpg",
            etag="same-etag",
            content_length=10,
            taken_at=modified,
            last_modified=modified,
        )
    )
    await db_session.commit()

    client = FakeOpenCloudClient(
        entries=[("CostaRica/img001.jpg", _entry("img001.jpg", "same-etag", modified))]
    )

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.photos_updated == 0
    assert scan_run.photos_added == 0
    assert client.range_requests == []  # unchanged files must not trigger an EXIF re-fetch
    assert client.download_requests == []  # ...nor a redundant thumbnail regeneration


async def test_scan_removes_photos_no_longer_present(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    db_session.add(
        Photo(
            project_id=project.id,
            relative_path="CostaRica/gone.jpg",
            etag="etag",
            content_length=10,
            taken_at=modified,
            last_modified=modified,
        )
    )
    await db_session.commit()

    client = FakeOpenCloudClient(entries=[])

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.photos_removed == 1
    result = await db_session.execute(select(Photo).where(Photo.project_id == project.id))
    assert result.scalars().all() == []


async def test_scan_skips_non_image_files(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = FakeOpenCloudClient(
        entries=[("CostaRica/notes.txt", _entry("notes.txt", "etag", modified))]
    )

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.files_skipped == 1
    assert scan_run.photos_added == 0
    photos = (await db_session.execute(select(Photo))).scalars().all()
    assert photos == []
    assert client.download_requests == []


async def test_scan_extracts_exif_for_jpeg(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    import io

    from PIL import Image
    from PIL.ExifTags import IFD

    image = Image.new("RGB", (4, 4), color="red")
    exif = image.getexif()
    exif.get_ifd(IFD.Exif)[36867] = "2022:01:02 03:04:05"
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)

    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = FakeOpenCloudClient(
        entries=[("CostaRica/img.jpg", _entry("img.jpg", "etag-jpg", modified))],
        file_contents={"CostaRica/img.jpg": buffer.getvalue()},
    )

    await run_project_scan(db_session, client, project, drive_name=None, cache_dir=tmp_path)

    photo = (await db_session.execute(select(Photo))).scalar_one()
    assert photo.taken_at == datetime(2022, 1, 2, 3, 4, 5)
    assert client.range_requests == ["CostaRica/img.jpg"]


async def test_scan_run_marked_failed_on_opencloud_error(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Fehler VOR Schleifenbeginn (resolve_drive schlaegt sofort fehl): kein Zwischen-Commit hat
    je stattgefunden, also verwirft session.rollback() die gesamte (leere) Transaktion -
    photos == [] bleibt korrekt. Nicht zu verwechseln mit
    test_scan_marked_failed_after_partial_progress_keeps_committed_photos unten, wo der Fehler
    ERST NACH mindestens einem periodischen Zwischen-Commit auftritt und deshalb bereits
    verarbeitete Photo-Zeilen bewusst erhalten bleiben (specs/features/0022-scan-live-
    fortschrittszaehler.md, Akzeptanzkriterium "Neue, bewusst akzeptierte Verhaltensaenderung").
    Beide Assertions (photos == [] hier vs. photos vorhanden dort) sind korrekt, weil sie
    unterschiedliche Fehlerzeitpunkte relativ zum ersten Commit abbilden."""
    project = await _make_project(db_session)
    client = FakeOpenCloudClient(entries=[], fail_with=OpenCloudError("Ordner nicht erreichbar"))

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.status == ScanStatus.FAILED
    assert scan_run.error_message == "Ordner nicht erreichbar"
    photos = (await db_session.execute(select(Photo))).scalars().all()
    assert photos == []


async def test_scan_run_marked_failed_on_unexpected_non_opencloud_error(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Terminierungs-Fix (specs/features/0023-scan-fortschritt-batch-groesse-fix.md): vor dem Fix
    fing run_project_scan ausschliesslich OpenCloudError ab - jede andere Exception (z.B. aus dem
    ungeschuetzten WebDAV-XML-Parsing) lief ungefangen durch und liess den ScanRun dauerhaft auf
    "running" haengen. Belegt, dass ein generischer RuntimeError mitten im Walk denselben
    FAILED-Pfad wie OpenCloudError durchlaeuft - kein Haengen, kein Timeout."""
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = WalkFailsWithUnexpectedErrorClient(
        entries=[
            ("CostaRica/img001.png", _entry("img001.png", "etag-1", modified)),
        ]
    )

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.status == ScanStatus.FAILED
    assert "Unerwarteter Parsing-Fehler" in (scan_run.error_message or "")


async def test_scan_marked_failed_after_partial_progress_keeps_committed_photos(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gegenstueck zu test_scan_run_marked_failed_on_opencloud_error oben: der Fehler tritt
    waehrend der Schleife auf, nachdem SCAN_COMMIT_BATCH_SIZE=1 bereits mehrere Zwischen-Commits
    ausgeloest hat. Belegt zugleich den periodischen Commit von scan_run.files_found und die
    bewusst akzeptierte Verhaltensaenderung, dass session.rollback() danach nur noch die seit dem
    letzten Commit offene (leere) Transaktion verwirft, nicht die bereits committeten
    Photo-Zeilen."""
    monkeypatch.setattr(worker, "SCAN_COMMIT_BATCH_SIZE", 1)
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = WalkFailsMidwayClient(
        entries=[
            ("CostaRica/img001.png", _entry("img001.png", "etag-1", modified)),
            ("CostaRica/img002.png", _entry("img002.png", "etag-2", modified)),
            ("CostaRica/img003.png", _entry("img003.png", "etag-3", modified)),
        ]
    )

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.status == ScanStatus.FAILED
    photos = (await db_session.execute(select(Photo))).scalars().all()
    assert len(photos) == 3


async def test_scan_commits_periodically_even_when_a_batch_boundary_lands_on_a_skipped_file(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review-Fund (test-engineer/architect, specs/features/0022): der Zwischen-Commit-Checkpoint
    darf nicht hinter den `continue`-Zweigen fuer uebersprungene Dateiendungen/unveraenderte
    Etags liegen, sonst wird er im DOMINANTEN Realweltfall (erneuter Scan eines bereits
    gescannten Projekts, ueberwiegend unveraenderte Dateien) faktisch nie erreicht - der Live-
    Zaehler wuerde dann trotz periodischem-Commit-Code effektiv nicht live wachsen.

    Aufbau (SCAN_COMMIT_BATCH_SIZE=2): Eintrag 1 (neues Bild) erhoeht files_found auf 1 (kein
    Commit, 1%2 != 0). Eintrag 2 ist eine NICHT-Bilddatei (loest den fruehen `continue` fuer
    unpassende Endung aus) und erhoeht files_found auf 2 - der Checkpoint muss trotz des
    `continue` dieser Iteration greifen (2 % 2 == 0), sonst geht die Commit-Gelegenheit
    ersatzlos verloren. Eintrag 3 (neues Bild) erhoeht files_found auf 3 (kein Commit). Danach
    bricht der Walk mit OpenCloudError ab.

    Faehrt der Checkpoint korrekt bei Eintrag 2, ist zu diesem Zeitpunkt bereits das Foto aus
    Eintrag 1 vollstaendig verarbeitet und wird durch diesen Commit mit persistiert - das Foto
    aus Eintrag 3 bleibt dagegen unkommittet und wird beim abschliessenden Rollback verworfen.
    Erwartung: genau 1 Photo-Zeile in der DB (aus Eintrag 1), nicht 0 (Checkpoint nie erreicht)
    und nicht 2 (Eintrag 3 faelschlich auch committet)."""
    monkeypatch.setattr(worker, "SCAN_COMMIT_BATCH_SIZE", 2)
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = WalkFailsMidwayClient(
        entries=[
            ("CostaRica/img_a.png", _entry("img_a.png", "etag-a", modified)),
            ("CostaRica/notes.txt", _entry("notes.txt", "etag-notes", modified)),
            ("CostaRica/img_b.png", _entry("img_b.png", "etag-b", modified)),
        ]
    )

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.status == ScanStatus.FAILED
    photos = (await db_session.execute(select(Photo))).scalars().all()
    assert [photo.relative_path for photo in photos] == ["CostaRica/img_a.png"]


async def test_scan_commits_files_found_progress_before_final_commit_at_production_batch_size(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Batch-Groessen-Fix (specs/features/0023-scan-fortschritt-batch-groesse-fix.md): bewusst
    OHNE monkeypatch.setattr(worker, "SCAN_COMMIT_BATCH_SIZE", ...) - prueft den echten
    Produktivwert nach dem Fix (1). Vorher (25) blieb der Live-Zaehler bei jedem Scan mit weniger
    als 25 Dateien waehrend der gesamten Laufzeit bei 0 eingefroren (Spec 0022, Bug).

    Verifiziert ueber eine ZWEITE, unabhaengige Session auf demselben In-Memory-Engine (geteilte
    StaticPool-Connection bei sqlite+aiosqlite:///:memory:), die zwischen den walk()-Eintraegen den
    ueber diese Connection sichtbaren DB-Zustand liest - eine reine Attribut-Pruefung auf demselben
    Session-Objekt waere kein Beweis fuer einen echten DB-Roundtrip (expire_on_commit=False haelt
    Attribute unabhaengig davon aktuell). Review-Praezisierung (test-engineer, Spec 0023): beweist
    strenggenommen einen DB-Roundtrip auf der geteilten Connection (flush ODER commit), nicht
    zwingend ausschliesslich commit() - fuer den Testzweck (Nachweis, dass SCAN_COMMIT_BATCH_SIZE=1
    tatsaechlich zu sichtbar wachsenden Zwischenstaenden fuehrt) ausreichend, da der Produktivcode
    an der geprueften Stelle tatsaechlich commit() aufruft."""
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    inspection_session_factory = make_session_factory(db_session.bind)
    observed_committed_counts: list[int] = []

    class ObservingClient(FakeOpenCloudClient):
        async def walk(
            self, webdav_url: str, root_path: str
        ) -> AsyncIterator[tuple[str, DavEntry]]:
            for item in self._entries:
                yield item
                # Laeuft erst, wenn der Konsument (run_project_scan) das aktuelle Element
                # vollstaendig verarbeitet und den naechsten Wert angefragt hat - liest also
                # exakt den Zwischenstand NACH dem periodischen Commit dieses Elements.
                async with inspection_session_factory() as inspection_session:
                    committed_scan_run = (
                        await inspection_session.execute(
                            select(ScanRun).where(ScanRun.project_id == project.id)
                        )
                    ).scalar_one()
                    observed_committed_counts.append(committed_scan_run.files_found)

    client = ObservingClient(
        entries=[
            ("CostaRica/img001.png", _entry("img001.png", "etag-1", modified)),
            ("CostaRica/img002.png", _entry("img002.png", "etag-2", modified)),
            ("CostaRica/img003.png", _entry("img003.png", "etag-3", modified)),
        ]
    )

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.status == ScanStatus.SUCCESS
    assert observed_committed_counts == [1, 2, 3]


async def test_scan_generates_thumbnails_for_new_photo(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = FakeOpenCloudClient(
        entries=[("CostaRica/img.jpg", _entry("img.jpg", "etag-jpg", modified))],
        file_contents={"CostaRica/img.jpg": _jpeg_bytes()},
    )

    await run_project_scan(db_session, client, project, drive_name=None, cache_dir=tmp_path)

    photo = (await db_session.execute(select(Photo))).scalar_one()
    assert client.download_requests == ["CostaRica/img.jpg"]
    assert thumbnail_path(tmp_path, photo.id, photo.etag).is_file()
    assert display_path(tmp_path, photo.id, photo.etag).is_file()


async def test_scan_regenerates_thumbnails_when_etag_changes(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    db_session.add(
        Photo(
            project_id=project.id,
            relative_path="CostaRica/img.jpg",
            etag="old-etag",
            content_length=10,
            taken_at=modified,
            last_modified=modified,
        )
    )
    await db_session.commit()

    client = FakeOpenCloudClient(
        entries=[("CostaRica/img.jpg", _entry("img.jpg", "new-etag", modified))],
        file_contents={"CostaRica/img.jpg": _jpeg_bytes()},
    )

    await run_project_scan(db_session, client, project, drive_name=None, cache_dir=tmp_path)

    photo = (await db_session.execute(select(Photo))).scalar_one()
    assert photo.etag == "new-etag"
    assert thumbnail_path(tmp_path, photo.id, "new-etag").is_file()


async def test_scan_survives_undecodable_image_without_failing(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Ein einzelnes kaputtes/nicht dekodierbares Foto darf den gesamten Scan nicht abbrechen
    (specs/features/0002-manual-categorization.md) - die Metadaten werden trotzdem gespeichert,
    nur die Thumbnail-Variante bleibt fehlend (Frontend zeigt dafuer einen Platzhalter)."""
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = FakeOpenCloudClient(
        entries=[("CostaRica/broken.jpg", _entry("broken.jpg", "etag-broken", modified))],
        file_contents={"CostaRica/broken.jpg": b"not a real jpeg"},
    )

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.status == ScanStatus.SUCCESS
    photo = (await db_session.execute(select(Photo))).scalar_one()
    assert photo.relative_path == "CostaRica/broken.jpg"
    assert not thumbnail_path(tmp_path, photo.id, photo.etag).is_file()


async def test_scan_survives_thumbnail_download_failure_without_failing(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)

    class FailingDownloadClient(FakeOpenCloudClient):
        async def download(self, webdav_url: str, relative_path: str) -> bytes:
            raise OpenCloudError("Download fehlgeschlagen")

    client = FailingDownloadClient(
        entries=[("CostaRica/img.jpg", _entry("img.jpg", "etag-jpg", modified))],
    )

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.status == ScanStatus.SUCCESS
    assert scan_run.photos_added == 1
