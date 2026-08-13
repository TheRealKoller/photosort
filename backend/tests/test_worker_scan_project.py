import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
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
        download_delay: float = 0.0,
        on_download: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._entries = entries
        self._file_contents = file_contents or {}
        self._fail_with = fail_with
        self._download_delay = download_delay
        self._on_download = on_download
        self.range_requests: list[str] = []
        self.download_requests: list[str] = []
        # specs/features/0036-scan-performance-zweiphasig-parallel.md: Nachweis echter
        # Nebenlaeufigkeit ohne Wall-Clock-Timing-Assertions (Teststrategie-Abschnitt der Spec) -
        # zaehlt, wie viele download()-Aufrufe gleichzeitig "in Flight" waren.
        self._active_downloads = 0
        self.max_concurrent_downloads = 0

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
        self._active_downloads += 1
        self.max_concurrent_downloads = max(self.max_concurrent_downloads, self._active_downloads)
        try:
            if self._download_delay:
                await asyncio.sleep(self._download_delay)
            if self._on_download is not None:
                await self._on_download(relative_path)
            return self._file_contents.get(relative_path, b"")
        finally:
            self._active_downloads -= 1


class WalkFailsMidwayClient(FakeOpenCloudClient):
    """Simuliert einen WebDAV-Abbruch mitten im Ordnerbaum-Durchlauf: `walk()` liefert einige
    Eintraege und wirft danach OpenCloudError, statt (wie bei fail_with) sofort in resolve_drive
    zu scheitern. Da `walk()` seit der Zwei-Phasen-Umstrukturierung (specs/features/0036) nur noch
    in Phase 1 (Enumeration) aufgerufen wird, faellt ein hier simulierter Fehler IMMER in Phase 1 -
    unabhaengig davon, wie viele Eintraege vorher bereits geliefert wurden, hat Phase 2
    (Klassifikation/Verarbeitung) zu diesem Zeitpunkt noch gar nicht begonnen."""

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


class WalkFailsWithCancelledErrorClient(FakeOpenCloudClient):
    """Schicht 1 des Fortschritts-Watchdogs (specs/features/0034-scan-haenger-fortschritts-
    watchdog.md, ADR 0019): simuliert einen arq job_timeout-Ablauf/Worker-Shutdown mitten im
    Scan-Loop - beide loesen denselben asyncio.CancelledError-Pfad aus. Vor dem Fix lief das als
    BaseException ungefangen durch run_project_scan durch, der ScanRun blieb dauerhaft auf
    status="running" haengen (siehe WalkFailsWithUnexpectedErrorClient oben fuer den analogen,
    bereits behobenen Exception-Fall)."""

    async def walk(self, webdav_url: str, root_path: str) -> AsyncIterator[tuple[str, DavEntry]]:
        for item in self._entries:
            yield item
        raise asyncio.CancelledError()


class DownloadFailsOnceClient(FakeOpenCloudClient):
    """specs/features/0036-scan-performance-zweiphasig-parallel.md, Resume-/Idempotenz-
    Absicherung: simuliert einen einzelnen, unerwarteten Download-Fehler fuer EINEN bestimmten
    Pfad (typischerweise in einem SPAETEREN Block als bereits erfolgreich committete Eintraege) -
    laesst den gesamten Scan fehlschlagen (identisches Verhalten wie ein OpenCloudError), ohne die
    Verarbeitung anderer, bereits abgeschlossener Bloecke rueckwirkend zu beeinflussen."""

    def __init__(self, *args: object, fail_path: str, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._fail_path = fail_path
        self.fail_count = 0

    async def download(self, webdav_url: str, relative_path: str) -> bytes:
        if relative_path == self._fail_path:
            self.fail_count += 1
            raise RuntimeError(f"Unerwarteter Download-Fehler fuer {relative_path}")
        return await super().download(webdav_url, relative_path)


class DownloadRaisesCancelledErrorClient(FakeOpenCloudClient):
    """specs/features/0036, Edge Case "CancelledError aus einer I/O-Coroutine in gather": simuliert
    einen Abbruch NICHT beim Walk (siehe WalkFailsWithCancelledErrorClient oben), sondern in einer
    der parallel laufenden Phase-2b-I/O-Coroutinen selbst - genau der Fall, den
    asyncio.gather(..., return_exceptions=True) OHNE explizite Sonderbehandlung verschlucken
    wuerde (siehe worker.py::_process_scan_block, Kommentar zur CancelledError-Pruefung)."""

    def __init__(self, *args: object, cancel_path: str, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._cancel_path = cancel_path

    async def download(self, webdav_url: str, relative_path: str) -> bytes:
        if relative_path == self._cancel_path:
            raise asyncio.CancelledError("simulierter Abbruch waehrend eines parallelen Downloads")
        return await super().download(webdav_url, relative_path)


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
    assert scan_run.total_files == 1

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
    photos == [] bleibt korrekt."""
    project = await _make_project(db_session)
    client = FakeOpenCloudClient(entries=[], fail_with=OpenCloudError("Ordner nicht erreichbar"))

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.status == ScanStatus.FAILED
    assert scan_run.error_message == "Ordner nicht erreichbar"
    assert scan_run.total_files is None
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


async def test_scan_run_marked_failed_on_cancelled_error(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Akzeptanzkriterium der Spec: CancelledError wird VOR dem erneuten raise abgefangen, der
    ScanRun sofort auf FAILED mit erklaerender error_message gesetzt - die Exception selbst wird
    NICHT verschluckt (arqs eigene Task-/Retry-Buchhaltung braucht sie weiterhin)."""
    project = await _make_project(db_session)
    project_id = project.id
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = WalkFailsWithCancelledErrorClient(
        entries=[
            ("CostaRica/img001.png", _entry("img001.png", "etag-1", modified)),
        ]
    )

    with pytest.raises(asyncio.CancelledError):
        await run_project_scan(db_session, client, project, drive_name=None, cache_dir=tmp_path)

    # project_id wurde VOR dem Aufruf gelesen (nicht project.id danach): session.rollback() in
    # _fail_run expired alle Objekte der Session - ein direkter project.id-Zugriff danach wuerde
    # einen impliziten Lazy-Load ausserhalb des von SQLAlchemy fuer Async-Sessions vorausgesetzten
    # greenlet-Kontexts ausloesen (sqlalchemy.exc.MissingGreenlet, kein Bug dieser Spec).
    scan_run = (
        await db_session.execute(select(ScanRun).where(ScanRun.project_id == project_id))
    ).scalar_one()
    assert scan_run.status == ScanStatus.FAILED
    assert scan_run.error_message


async def test_scan_run_marked_failed_on_cancelled_error_from_a_parallel_download(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """specs/features/0036, Pflicht-Edge-Case: ein asyncio.CancelledError aus einer parallel
    laufenden Phase-2b-I/O-Coroutine muss unveraendert (roh, nicht als generische Exception) den
    bestehenden `except asyncio.CancelledError`-Zweig erreichen (ADR-0019-Kompatibilitaet).

    Kritischer, verifizierter Python-Async-Fallstrick (kein Implementierungsdetail, sondern der
    eigentliche Grund fuer diesen Test): `asyncio.gather(..., return_exceptions=True)` faengt ein
    CancelledError, das eine EINZELNE Kind-Coroutine wirft (statt einer echten aeusseren
    Task-Cancellation), NICHT als Exception ab, sondern reicht es als gewoehnliches Element der
    Ergebnisliste durch (await gather(...) wirft in diesem Fall NICHTS) - siehe
    worker.py::_process_scan_block, das genau deshalb die Ergebnisliste explizit auf
    CancelledError-Instanzen prueft und sie manuell erneut wirft. Ohne diese explizite Pruefung
    wuerde dieser Test fehlschlagen (kein pytest.raises(CancelledError), Scan faelschlich SUCCESS
    oder FAILED mit generischer Fehlermeldung statt des korrekten Watchdog-Schicht-1-Pfads)."""
    monkeypatch.setattr(worker.settings, "scan_download_concurrency", 2)
    project = await _make_project(db_session)
    project_id = project.id
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = DownloadRaisesCancelledErrorClient(
        entries=[
            ("CostaRica/img001.png", _entry("img001.png", "etag-1", modified)),
            ("CostaRica/img002.png", _entry("img002.png", "etag-2", modified)),
        ],
        cancel_path="CostaRica/img002.png",
    )

    with pytest.raises(asyncio.CancelledError):
        await run_project_scan(db_session, client, project, drive_name=None, cache_dir=tmp_path)

    scan_run = (
        await db_session.execute(select(ScanRun).where(ScanRun.project_id == project_id))
    ).scalar_one()
    assert scan_run.status == ScanStatus.FAILED
    assert scan_run.error_message


async def test_scan_phase_one_failure_leaves_total_files_unset_and_no_photos_processed(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Architektur-Konsequenz der Zwei-Phasen-Umstrukturierung (specs/features/0036, ADR 0020):
    `walk()` wird jetzt AUSSCHLIESSLICH in der Enumerationsphase (Phase 1) aufgerufen - ein dort
    auftretender Fehler tritt zwangslaeufig auf, BEVOR Phase 2 (Klassifikation/Verarbeitung)
    ueberhaupt beginnt, selbst wenn `walk()` vorher bereits mehrere echte Eintraege geliefert hat.
    Ersetzt den bisherigen Test `test_scan_marked_failed_after_partial_progress_keeps_committed_
    photos`, dessen Erwartung (3 bereits verarbeitete Photo-Zeilen bleiben trotz Fehler committet)
    auf dem alten, einphasigen interleaved Loop beruhte und mit der neuen Architektur nicht mehr
    zutrifft - Phase 1 legt selbst nie Photo-Zeilen an, das war schon immer Aufgabe von Phase 2."""
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
    # Der letzte Enumerations-Checkpoint (3 gelistete Eintraege) bleibt committet - der
    # Live-Zaehler waehrend einer langen Enumerationsphase funktioniert also weiterhin.
    assert scan_run.files_found == 3
    assert scan_run.total_files is None
    photos = (await db_session.execute(select(Photo))).scalars().all()
    assert photos == []


async def test_scan_commits_files_found_progress_during_enumeration_at_production_batch_size(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Batch-Groessen-Fix (specs/features/0023-scan-fortschritt-batch-groesse-fix.md): bewusst
    OHNE monkeypatch.setattr(worker, "SCAN_COMMIT_BATCH_SIZE", ...) - prueft den echten
    Produktivwert nach dem Fix (1), jetzt fuer die Enumerationsphase (Phase 1, specs/features/0036).

    Verifiziert ueber eine ZWEITE, unabhaengige Session auf demselben In-Memory-Engine (geteilte
    StaticPool-Connection bei sqlite+aiosqlite:///:memory:), die zwischen den walk()-Eintraegen den
    ueber diese Connection sichtbaren DB-Zustand liest - eine reine Attribut-Pruefung auf demselben
    Session-Objekt waere kein Beweis fuer einen echten DB-Roundtrip."""
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


async def test_scan_updates_last_progress_at_at_each_checkpoint(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md, ADR
    0019): last_progress_at wird an den bestehenden Zwischen-Commit-Stellen aktualisiert, die
    reap_stalled_runs (Schicht 2) spaeter liest - verifiziert ueber einen kontrollierten "Uhr"-Wert
    statt einer echten Wartezeit."""
    sentinel = datetime(2030, 1, 1, 12, 0, 0)
    monkeypatch.setattr(worker, "_now_utc", lambda: sentinel)

    project = await _make_project(db_session)
    modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
    client = FakeOpenCloudClient(
        entries=[("CostaRica/img001.png", _entry("img001.png", "etag-1", modified))]
    )

    scan_run = await run_project_scan(
        db_session, client, project, drive_name=None, cache_dir=tmp_path
    )

    assert scan_run.last_progress_at == sentinel


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


class TestTotalFilesTracking:
    """specs/features/0036-scan-performance-zweiphasig-parallel.md: `ScanRun.total_files` wird
    nach Abschluss von Phase 1 einmalig gesetzt (`is not None`-Prueflogik, siehe ADR 0020 Punkt 6)
    und danach nicht mehr veraendert."""

    async def test_total_files_set_after_enumeration_for_mixed_entries(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _make_project(db_session)
        modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
        client = FakeOpenCloudClient(
            entries=[
                ("CostaRica/img001.png", _entry("img001.png", "etag-1", modified)),
                ("CostaRica/notes.txt", _entry("notes.txt", "etag-2", modified)),
            ]
        )

        scan_run = await run_project_scan(
            db_session, client, project, drive_name=None, cache_dir=tmp_path
        )

        assert scan_run.total_files == 2

    async def test_total_files_is_zero_not_none_for_an_empty_project(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        # Der explizit testpflichtige Sonderfall aus dem Akzeptanzkriterium: 0 ist ein
        # vollstaendig gueltiges, informatives Ergebnis (Phase 1 IST abgeschlossen), nicht
        # gleichbedeutend mit "noch nicht abgeschlossen" (None).
        project = await _make_project(db_session)
        client = FakeOpenCloudClient(entries=[])

        scan_run = await run_project_scan(
            db_session, client, project, drive_name=None, cache_dir=tmp_path
        )

        assert scan_run.status == ScanStatus.SUCCESS
        assert scan_run.total_files == 0
        assert scan_run.total_files is not None

    async def test_total_files_reset_of_files_found_is_committed_before_phase_two_starts(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Pflicht-Edge-Case der Spec ("Phasenuebergang"): direkt nach Phase 1 muss total_files
        bereits gesetzt UND files_found bereits auf 0 zurueckgesetzt sein, BEVOR der erste
        Phase-2-Commit stattfindet - beobachtet ueber eine zweite, unabhaengige Session, die beim
        allerersten download()-Aufruf (zwingend nach dem Phase-1-Commit, da Downloads nur in
        Phase 2b passieren) den zu diesem Zeitpunkt sichtbaren DB-Zustand liest."""
        project = await _make_project(db_session)
        modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
        inspection_session_factory = make_session_factory(db_session.bind)
        observed: dict[str, object] = {}

        async def _observe(_relative_path: str) -> None:
            if observed:
                return
            async with inspection_session_factory() as inspection_session:
                committed = (
                    await inspection_session.execute(
                        select(ScanRun).where(ScanRun.project_id == project.id)
                    )
                ).scalar_one()
                observed["total_files"] = committed.total_files
                observed["files_found"] = committed.files_found

        client = FakeOpenCloudClient(
            entries=[("CostaRica/img.jpg", _entry("img.jpg", "etag-1", modified))],
            on_download=_observe,
        )

        await run_project_scan(db_session, client, project, drive_name=None, cache_dir=tmp_path)

        assert observed == {"total_files": 1, "files_found": 0}


class TestBlockOrchestration:
    """specs/features/0036, Phase 2b: begrenzte Parallelisierung in festen Bloecken der Groesse
    settings.scan_download_concurrency (ADR 0020). Pflicht-Edge-Cases der Spec: Blockgrenzen
    (Menge = Blockgroesse, Blockgroesse+1, < Blockgroesse)."""

    @pytest.mark.parametrize(
        ("file_count", "concurrency", "expected_max_concurrent"),
        [
            (2, 2, 2),  # Menge = Blockgroesse: genau ein voller Block
            (3, 2, 2),  # Menge = Blockgroesse + 1: ein voller + ein unvollstaendiger Block
            (1, 2, 1),  # Menge < Blockgroesse: ein einzelner, unvollstaendiger Block
        ],
    )
    async def test_downloads_run_concurrently_bounded_by_block_size(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        file_count: int,
        concurrency: int,
        expected_max_concurrent: int,
    ) -> None:
        monkeypatch.setattr(worker.settings, "scan_download_concurrency", concurrency)
        project = await _make_project(db_session)
        modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
        entries = [
            (f"CostaRica/img{i:03d}.png", _entry(f"img{i:03d}.png", f"etag-{i}", modified))
            for i in range(file_count)
        ]
        # Kuenstliche Verzoegerung (kein Wall-Clock-Assert, siehe Klassen-Docstring) - stellt
        # sicher, dass sich die Downloads eines Blocks tatsaechlich zeitlich ueberlappen, statt
        # durch reine Zufalls-Terminierung ohnehin sequentiell durchzulaufen.
        client = FakeOpenCloudClient(entries=entries, download_delay=0.01)

        scan_run = await run_project_scan(
            db_session, client, project, drive_name=None, cache_dir=tmp_path
        )

        assert scan_run.status == ScanStatus.SUCCESS
        assert scan_run.photos_added == file_count
        assert client.max_concurrent_downloads == expected_max_concurrent

    async def test_scan_run_marked_failed_on_unexpected_download_error_in_a_block(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(worker.settings, "scan_download_concurrency", 2)
        project = await _make_project(db_session)
        modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
        client = DownloadFailsOnceClient(
            entries=[
                ("CostaRica/img001.png", _entry("img001.png", "etag-1", modified)),
                ("CostaRica/img002.png", _entry("img002.png", "etag-2", modified)),
            ],
            fail_path="CostaRica/img002.png",
        )

        scan_run = await run_project_scan(
            db_session, client, project, drive_name=None, cache_dir=tmp_path
        )

        assert scan_run.status == ScanStatus.FAILED
        assert "img002.png" in (scan_run.error_message or "")
        # test-engineer-Review-Fund: belegt explizit den in der Spec ("Edge Cases (Pflicht)")
        # geforderten Teil des `return_exceptions=True`-Verhaltens - die NICHT fehlgeschlagene
        # Geschwister-Coroutine desselben Blocks (img001.png) laeuft tatsaechlich vollstaendig zu
        # Ende, statt durch den Fehler in img002.png sofort abgebrochen zu werden.
        assert "CostaRica/img001.png" in client.download_requests


class TestResumeIdempotency:
    """specs/features/0036, Resume-/Idempotenz-Absicherung: die bestehende Etag-basierte
    Skip-Idempotenz darf durch die Block-Umstrukturierung (flush() ohne commit() vor Abschluss der
    I/O je Block, ADR 0020) nicht gebrochen werden."""

    async def test_full_rescan_of_unchanged_project_triggers_zero_downloads(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(worker.settings, "scan_download_concurrency", 2)
        project = await _make_project(db_session)
        modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
        entries = [
            ("CostaRica/img001.jpg", _entry("img001.jpg", "etag-1", modified)),
            ("CostaRica/img002.jpg", _entry("img002.jpg", "etag-2", modified)),
            ("CostaRica/img003.jpg", _entry("img003.jpg", "etag-3", modified)),
        ]
        first_client = FakeOpenCloudClient(entries=entries)
        first_run = await run_project_scan(
            db_session, first_client, project, drive_name=None, cache_dir=tmp_path
        )
        assert first_run.status == ScanStatus.SUCCESS
        assert first_run.photos_added == 3

        second_client = FakeOpenCloudClient(entries=entries)
        second_run = await run_project_scan(
            db_session, second_client, project, drive_name=None, cache_dir=tmp_path
        )

        assert second_run.status == ScanStatus.SUCCESS
        assert second_run.photos_added == 0
        assert second_run.photos_updated == 0
        assert second_client.download_requests == []
        assert second_client.range_requests == []

    async def test_scan_aborted_mid_block_is_fully_reprocessed_on_a_later_scan_without_duplicates(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Kernbeleg der Crash-Sicherheits-Invariante (ADR 0020, Fallstrick 2): der erste Block
        wird erfolgreich committet, der zweite Block bricht mitten in einem unerwarteten
        Download-Fehler ab (kein commit() fuer diesen Block) - ein Neustart darf weder Duplikate
        erzeugen noch bereits committete Eintraege erneut herunterladen, muss aber die Eintraege
        des abgebrochenen Blocks vollstaendig nachholen."""
        monkeypatch.setattr(worker.settings, "scan_download_concurrency", 2)
        project = await _make_project(db_session)
        project_id = project.id
        modified = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)
        entries = [
            ("CostaRica/img001.jpg", _entry("img001.jpg", "etag-1", modified)),
            ("CostaRica/img002.jpg", _entry("img002.jpg", "etag-2", modified)),
            ("CostaRica/img003.jpg", _entry("img003.jpg", "etag-3", modified)),
            ("CostaRica/img004.jpg", _entry("img004.jpg", "etag-4", modified)),
        ]
        failing_client = DownloadFailsOnceClient(
            entries=entries, fail_path="CostaRica/img003.jpg"
        )

        first_run = await run_project_scan(
            db_session, failing_client, project, drive_name=None, cache_dir=tmp_path
        )
        assert first_run.status == ScanStatus.FAILED

        # project.id (NICHT mehr direkt gelesen, siehe project_id oben): _fail_run's
        # session.rollback() expired alle Objekte der Session, siehe Kommentar bei
        # test_scan_run_marked_failed_on_cancelled_error oben. project wird unten fuer den
        # zweiten Scan-Aufruf trotzdem weiterverwendet - run_project_scan liest project.id selbst
        # innerhalb eines aktiven greenlet-Kontexts, das ist unproblematisch.
        photos_after_failure = (
            (await db_session.execute(select(Photo).where(Photo.project_id == project_id)))
            .scalars()
            .all()
        )
        assert sorted(photo.relative_path for photo in photos_after_failure) == [
            "CostaRica/img001.jpg",
            "CostaRica/img002.jpg",
        ]

        # Un-expired `project` fuer den zweiten Scan-Aufruf unten (rollback() in _fail_run hat es
        # expired) - analog zum bestehenden refresh()-Muster in _fail_run selbst (worker.py).
        await db_session.refresh(project)
        recovering_client = FakeOpenCloudClient(entries=entries)
        second_run = await run_project_scan(
            db_session, recovering_client, project, drive_name=None, cache_dir=tmp_path
        )

        assert second_run.status == ScanStatus.SUCCESS
        # Nur der abgebrochene Block wird nachgeholt/heruntergeladen - der bereits erfolgreich
        # committete erste Block wird NICHT erneut heruntergeladen (Etag unveraendert).
        assert second_run.photos_added == 2
        assert second_run.photos_updated == 0
        assert sorted(recovering_client.download_requests) == [
            "CostaRica/img003.jpg",
            "CostaRica/img004.jpg",
        ]

        all_photos = (
            (await db_session.execute(select(Photo).where(Photo.project_id == project.id)))
            .scalars()
            .all()
        )
        assert sorted(photo.relative_path for photo in all_photos) == [
            "CostaRica/img001.jpg",
            "CostaRica/img002.jpg",
            "CostaRica/img003.jpg",
            "CostaRica/img004.jpg",
        ]
        # Keine Duplikate: der Unique-Constraint (project_id, relative_path) haette einen
        # doppelten Insert-Versuch fuer img001/img002 ohnehin verhindert - diese Assertion
        # dokumentiert die Erwartung zusaetzlich explizit ueber die Zeilenanzahl.
        assert len(all_photos) == 4
