from __future__ import annotations

import asyncio
import enum
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from arq.connections import RedisSettings
from arq.cron import cron
from arq.worker import func as arq_func
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from photosort.classification import (
    CategoryCandidate,
    FaceDetectorLike,
    build_face_detector,
    classify_category,
    select_top_n_with_category_mix,
)
from photosort.config import settings
from photosort.db import async_session_factory
from photosort.models import (
    Photo,
    PhotoCategory,
    PhotoScore,
    Project,
    RatingStatus,
    ScanRun,
    ScanStatus,
    ScoringRun,
    TopSelectionRun,
)
from photosort.opencloud.client import OpenCloudClient, OpenCloudError
from photosort.opencloud.exif import extract_taken_at
from photosort.opencloud.webdav_xml import DavEntry
from photosort.scoring import (
    SHARPNESS_REJECT_THRESHOLD,
    DuplicateCandidate,
    TimeClusterCandidate,
    assign_duplicate_clusters,
    assign_time_clusters,
    compute_dhash,
    compute_exposure,
    compute_sharpness,
    local_quality_score,
)
from photosort.thumbnails import generate_variants, variant_path

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
_EXIF_CANDIDATE_EXTENSIONS = {".jpg", ".jpeg"}
_EXIF_RANGE_BYTES = 131_072

# Wie oft ScoringRun.photos_processed waehrend der Verarbeitung zwischen-committet wird
# (decisions/0006-local-scoring-datamodel.md: "mind. alle 25 Fotos", damit ein pollender Client
# echten, monoton wachsenden Fortschritt sieht statt nur Start-/Endzustand). Modul-Konstante statt
# Default-Parameterwert, damit Tests sie per monkeypatch.setattr(worker, "SCORE_COMMIT_BATCH_SIZE",
# ...) verkleinern koennen, ohne echte 25+ Testfotos anlegen zu muessen (Teststrategie-Abschnitt
# der Spec, "neues Testmuster").
SCORE_COMMIT_BATCH_SIZE = 25

# Analog SCORE_COMMIT_BATCH_SIZE, aber fuer ScanRun.files_found (specs/features/0022-scan-live-
# fortschrittszaehler.md, zweitmalige Anwendung des in decisions/0006-local-scoring-datamodel.md
# etablierten Musters). Modul-Konstante statt Default-Parameterwert, damit Tests sie per
# monkeypatch.setattr(worker, "SCAN_COMMIT_BATCH_SIZE", ...) verkleinern koennen. Urspruenglich
# (vor specs/features/0036-scan-performance-zweiphasig-parallel.md) sass der Checkpoint-Aufruf an
# JEDEM Ausstiegspunkt eines einzigen interleaved Loops (zwei `continue`-Zweige fuer uebersprungene
# Endung/unveraenderten Etag) - seit der Zwei-Phasen-Umstrukturierung gilt dieselbe Kadenz jetzt
# ueber den gemeinsamen Helfer _maybe_commit_progress_checkpoint (unten), einmal aufgerufen aus
# Phase 1 (_enumerate_scan_entries, je gelistetem Eintrag) und einmal aus der Skip-Schleife von
# Phase 2a in run_project_scan (je Skip-Entscheidung) - strukturell ausgeschlossen, dass ein
# Skip-Fall den Checkpoint verpasst, da beide Phasen denselben einzigen Aufrufpunkt durchlaufen
# (kein `continue`-Zweig mehr, der ihn versehentlich umgehen koennte). Ohne diese Kadenz waere der
# Live-Zaehler im dominanten Realweltfall (Re-Scan mit ueberwiegend unveraenderten Dateien)
# faktisch nie erreichbar (urspruenglicher Review-Fund, gilt fuer die neue Struktur unveraendert).
#
# Batch-Groessen-Fix (specs/features/0023-scan-fortschritt-batch-groesse-fix.md): auf 1 statt 25
# gesetzt, anders als SCORE_COMMIT_BATCH_SIZE oben. run_project_scoring ist CPU-only (lokale
# Heuristiken auf bereits gecachten Bildern) und schnell genug, dass Batching den Commit-Overhead
# sinnvoll reduziert - run_project_scan dagegen ist netzwerkgebunden (EXIF-Range-Read und
# Thumbnail-Generierung pro Datei ueber OpenCloud-WebDAV), ein zusaetzlicher DB-Commit pro Datei
# faellt gegenueber der Netzwerklatenz nicht messbar ins Gewicht. Bei 25 blieb der Live-Zaehler
# bei jedem Scan mit weniger als 25 Dateien waehrend der gesamten Laufzeit bei 0 eingefroren
# (typischer Fall: Familienfoto-Ergaenzung, Spec 0022 nachgebessert).
SCAN_COMMIT_BATCH_SIZE = 1

# Analog SCORE_COMMIT_BATCH_SIZE, fuer TopSelectionRun.candidates_processed
# (specs/features/0024-top-photo-selection-category-mix.md). Kleiner als SCORE_COMMIT_BATCH_SIZE,
# da mediapipe-Inferenz pro Kandidatenfoto eine spuerbare Laufzeit hat (Architektur-Abschnitt der
# Spec) - ein grober Batch von 25 wuerde den Live-Fortschritt bei typischen Kandidatenpool-Groessen
# (wenige bis niedrige zweistellige Anzahl pro Cluster) faktisch einfrieren, aehnlich dem in Spec
# 0023 behobenen Scan-Zaehler-Problem. Modul-Konstante statt Default-Parameterwert, damit Tests sie
# per monkeypatch.setattr(worker, "TOP_SELECTION_COMMIT_BATCH_SIZE", ...) verkleinern koennen.
TOP_SELECTION_COMMIT_BATCH_SIZE = 5

# Kandidatenpool-Formel je Cluster (Akzeptanzkriterium der Spec): begrenzt, wie viele Fotos pro
# Cluster ueberhaupt lokal klassifiziert werden (mediapipe-Inferenz ist der teuerste Schritt) - das
# 3-fache der Zielanzahl, mindestens aber 6, damit auch bei kleinem top_n_per_cluster genug
# Kategorie-Vielfalt fuer das Quotenverfahren zur Verfuegung steht.
TOP_SELECTION_CANDIDATE_POOL_MULTIPLIER = 3
TOP_SELECTION_CANDIDATE_POOL_MINIMUM = 6


class OpenCloudScanClient(Protocol):
    """The subset of OpenCloudClient that scanning needs — kept narrow so tests can fake it."""

    async def resolve_drive(self, name: str | None) -> Any: ...

    def walk(self, webdav_url: str, root_path: str) -> Any: ...

    async def get_range(self, webdav_url: str, relative_path: str, length: int) -> bytes: ...

    async def download(self, webdav_url: str, relative_path: str) -> bytes: ...


def _extension(relative_path: str) -> str:
    return os.path.splitext(relative_path)[1].lower()


class SkipReason(enum.Enum):
    """specs/features/0036-scan-performance-zweiphasig-parallel.md, ADR 0020 (Phase 2a): warum ein
    Eintrag NICHT zu einem Arbeitsposten fuer Phase 2b wird. Zwei getrennte Werte statt eines
    einzelnen bool-Flags, weil nur UNSUPPORTED_EXTENSION zusaetzlich ScanRun.files_skipped
    hochzaehlt (bestehende Semantik, siehe run_project_scan) - UNCHANGED_ETAG zaehlt nur in
    files_found (Fortschritt), nicht in files_skipped."""

    UNSUPPORTED_EXTENSION = "unsupported_extension"
    UNCHANGED_ETAG = "unchanged_etag"


@dataclass
class ScanWorkItem:
    """Ein Eintrag aus Phase 1, der in Phase 2b tatsaechlich verarbeitet werden muss (neue Datei
    oder geaenderter Etag) - `existing_photo` ist `None` fuer neue Dateien, sonst die zu
    aktualisierende Zeile."""

    relative_path: str
    entry: DavEntry
    existing_photo: Photo | None


@dataclass
class ScanEntryDecision:
    """Ergebnis der Klassifikation eines einzelnen Phase-1-Eintrags: entweder ein Skip-Grund ODER
    ein Arbeitsposten, nie beides - siehe _classify_scan_entries."""

    relative_path: str
    skip_reason: SkipReason | None
    work_item: ScanWorkItem | None


@dataclass
class ScanClassification:
    """Ergebnis von _classify_scan_entries fuer die vollstaendige Phase-1-Liste.

    `decisions` behaelt bewusst die Eingabereihenfolge bei (run_project_scan iteriert sie fuer die
    Checkpoint-Kadenz von files_found/files_skipped in Phase 2a, siehe ADR 0020) - `work_items` ist
    eine reine Teilmenge davon (nur die Eintraege mit skip_reason is None), fuer Phase 2b."""

    decisions: list[ScanEntryDecision] = field(default_factory=list)
    work_items: list[ScanWorkItem] = field(default_factory=list)
    seen_paths: set[str] = field(default_factory=set)


def _classify_scan_entries(
    entries: list[tuple[str, DavEntry]],
    existing_photos: dict[str, Photo],
) -> ScanClassification:
    """specs/features/0036-scan-performance-zweiphasig-parallel.md, ADR 0020 (Phase 2a): reine
    Funktion, keine Session-/DB-Zugriffe - isoliert unit-testbar (siehe
    test_worker_scan_classification.py). Identische fachliche Entscheidungslogik wie der fruehere
    inline Loop-Koerper in run_project_scan (unsupported extension -> Skip + files_skipped;
    unveraenderter Etag -> Skip ohne files_skipped; sonst -> Arbeitsposten), nur ohne die
    Verarbeitung selbst."""
    classification = ScanClassification()
    for relative_path, entry in entries:
        extension = _extension(relative_path)
        if extension not in _IMAGE_EXTENSIONS:
            classification.decisions.append(
                ScanEntryDecision(relative_path, SkipReason.UNSUPPORTED_EXTENSION, None)
            )
            continue

        classification.seen_paths.add(relative_path)
        existing_photo = existing_photos.get(relative_path)
        if existing_photo is not None and existing_photo.etag == entry.etag:
            classification.decisions.append(
                ScanEntryDecision(relative_path, SkipReason.UNCHANGED_ETAG, None)
            )
            continue

        work_item = ScanWorkItem(relative_path, entry, existing_photo)
        classification.decisions.append(ScanEntryDecision(relative_path, None, work_item))
        classification.work_items.append(work_item)

    return classification


def _naive_utc(value: datetime) -> datetime:
    # Stored as naive UTC throughout (matches sqlite/Postgres TIMESTAMP WITHOUT TIME ZONE);
    # WebDAV last-modified values arrive timezone-aware and must be normalized before storing
    # so they stay comparable with EXIF-derived (always naive) timestamps.
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def _fail_run(
    session: AsyncSession,
    run: ScanRun | ScoringRun | TopSelectionRun,
    error_message: str,
) -> None:
    """Gemeinsame "Lauf auf FAILED setzen"-Logik fuer alle drei run_*-Funktionen
    (specs/features/0034-scan-haenger-fortschritts-watchdog.md, ADR 0019) - kein Decorator/Wrapper
    um die drei Funktionen (die bleiben strukturell eigenstaendig, ihre Erfolgspfade unterscheiden
    sich zu stark), nur Vermeidung von vier identischen Zeilen an sechs Call-Sites (drei
    Funktionen x je CancelledError- und Exception-Zweig). Kein Kontrollfluss (kein raise/return)
    hier drin - das bleibt an jeder Call-Site sichtbar."""
    await session.rollback()
    run.status = ScanStatus.FAILED
    run.error_message = error_message
    run.finished_at = _now_utc()
    await session.commit()
    # Copilot-Review-Fund (PR #67): das vorangehende rollback() expired ORM-Objekte der Session -
    # ohne dieses refresh() koennte ein direkter Attributzugriff auf `run` NACH der Rueckkehr aus
    # _fail_run (z.B. `run.id` in scan_project/score_project/select_top_photos, die den
    # Rueckgabewert von run_project_scan/run_project_scoring/run_top_selection unmittelbar
    # weiterverwenden) einen impliziten Lazy-Load ausserhalb eines aktiven greenlet-Kontexts
    # ausloesen (sqlalchemy.exc.MissingGreenlet) - siehe test_worker_fail_run.py.
    await session.refresh(run)


async def _generate_thumbnails(
    client: OpenCloudScanClient,
    webdav_url: str,
    relative_path: str,
    photo_id: int,
    etag: str,
    cache_dir: Path,
) -> None:
    """Best-effort (specs/features/0002-manual-categorization.md): weder ein Download- noch ein
    Dekodierfehler duerfen den Scan des Projekts abbrechen (anders als die uebrigen
    OpenCloudError-Faelle unten, die den ganzen Scan als FAILED markieren) - ein fehlendes
    Thumbnail aeussert sich nur als 404-Platzhalter im Bild-Endpunkt, siehe thumbnails.py.

    Nimmt bewusst `photo_id`/`etag` statt eines `Photo`-Objekts entgegen (specs/features/0036-
    scan-performance-zweiphasig-parallel.md, ADR 0020, Punkt 2): wird als Teil von
    _fetch_and_thumbnail parallel zu Geschwister-Aufrufen desselben Blocks ausgefuehrt und darf
    deshalb keinerlei Session-Zugriff ausloesen - ein ORM-Objekt hier entgegenzunehmen wuerde dazu
    verleiten, versehentlich weitere (nicht nebenlaeufigkeitssichere) Attribute zu lesen/zu
    setzen."""
    try:
        content = await client.download(webdav_url, relative_path)
    except OpenCloudError:
        return
    generate_variants(cache_dir, photo_id, etag, content)


async def _fetch_and_thumbnail(
    client: OpenCloudScanClient,
    webdav_url: str,
    relative_path: str,
    extension: str,
    fallback_taken_at: datetime,
    photo_id: int,
    etag: str,
    cache_dir: Path,
) -> datetime:
    """Der reine I/O-/CPU-Teil eines einzelnen Arbeitspostens aus Phase 2b (specs/features/0036,
    ADR 0020, Punkt 2): EXIF-Range-Read (nur fuer JPEG-Kandidaten) fuer `taken_at`, danach
    best-effort Download + Thumbnail-Erzeugung - bewusst OHNE jeglichen Session-Zugriff, damit
    mehrere Aufrufe sicher parallel per asyncio.gather laufen koennen (_process_scan_block unten).
    Ein EXIF-Lesefehler wird NICHT abgefangen (identisches Verhalten wie vor der Umstrukturierung):
    ein einzelner OpenCloud-Fehler hier laesst den gesamten Scan fehlschlagen, siehe ADR."""
    taken_at = fallback_taken_at
    if extension in _EXIF_CANDIDATE_EXTENSIONS:
        content = await client.get_range(webdav_url, relative_path, _EXIF_RANGE_BYTES)
        exif_taken_at = extract_taken_at(content)
        if exif_taken_at is not None:
            taken_at = exif_taken_at

    await _generate_thumbnails(client, webdav_url, relative_path, photo_id, etag, cache_dir)
    return taken_at


async def _process_scan_block(
    session: AsyncSession,
    client: OpenCloudScanClient,
    webdav_url: str,
    cache_dir: Path,
    project_id: int,
    block: list[ScanWorkItem],
) -> tuple[int, int]:
    """Verarbeitet einen einzelnen Block von Arbeitsposten (Groesse = settings.
    scan_download_concurrency, specs/features/0036, ADR 0020, Punkt 1/4): zunaechst sequentiell
    Photo-Zeilen anlegen/aktualisieren + flush() (Fallstrick 2 der ADR: KEIN commit() hier - ein
    Absturz in diesem Fenster ist dadurch folgenlos, die Transaktion wird beim Neuverbinden
    verworfen), danach die reinen I/O-Coroutinen des Blocks parallel per asyncio.gather. Der
    Aufrufer (run_project_scan) committet erst NACH erfolgreicher Rueckkehr dieser Funktion - ein
    Commit pro vollstaendig abgearbeitetem Block. Gibt (photos_added, photos_updated) fuer diesen
    Block zurueck."""
    photos: list[Photo] = []
    added = 0
    updated = 0
    for item in block:
        last_modified = (
            _naive_utc(item.entry.last_modified) if item.entry.last_modified else _now_utc()
        )
        if item.existing_photo is not None:
            photo = item.existing_photo
            photo.etag = item.entry.etag or ""
            photo.content_length = item.entry.content_length or 0
            photo.last_modified = last_modified
            updated += 1
        else:
            photo = Photo(
                project_id=project_id,
                relative_path=item.relative_path,
                etag=item.entry.etag or "",
                content_length=item.entry.content_length or 0,
                taken_at=last_modified,  # vorlaeufig, wird unten nach dem gather() ersetzt
                last_modified=last_modified,
            )
            session.add(photo)
            added += 1
        photos.append(photo)

    if added:
        # Nur neu angelegte Zeilen brauchen flush() fuer eine DB-vergebene ID (fuer den
        # Thumbnail-Dateinamen unten) - bereits bestehende Zeilen haben schon eine ID (Code-Review-
        # Fund aus der Vorversion, weiterhin gueltig).
        await session.flush()

    results = await asyncio.gather(
        *[
            _fetch_and_thumbnail(
                client,
                webdav_url,
                item.relative_path,
                _extension(item.relative_path),
                photos[index].last_modified,
                photos[index].id,
                photos[index].etag,
                cache_dir,
            )
            for index, item in enumerate(block)
        ],
        return_exceptions=True,
    )

    # Verifizierter Python-Async-Fallstrick (ADR 0020, siehe auch test_worker_scan_project.py::
    # test_scan_run_marked_failed_on_cancelled_error_from_a_parallel_download): mit
    # return_exceptions=True faengt asyncio.gather() ein CancelledError, das eine EINZELNE Kind-
    # Coroutine wirft, NICHT als Exception ab, sondern reicht es als gewoehnliches Element der
    # Ergebnisliste durch - `await gather(...)` selbst wirft in diesem Fall NICHTS. Ohne diese
    # explizite Pruefung wuerde ein Abbruch mitten in einer parallelen I/O-Coroutine NICHT den
    # bestehenden `except asyncio.CancelledError`-Zweig in run_project_scan erreichen (ADR-0019-
    # Kompatibilitaet, Akzeptanzkriterium der Spec). Eine ECHTE aeussere Task-Cancellation (arq
    # job_timeout) propagiert dagegen bereits ohne Sonderbehandlung roh durch `await gather(...)`
    # hindurch - dieser Fall betrifft ausschliesslich eine Kind-Coroutine, die CancelledError
    # selbst wirft/traegt.
    for result in results:
        if isinstance(result, asyncio.CancelledError):
            raise result
    for result in results:
        if isinstance(result, BaseException):
            raise result

    for photo, taken_at in zip(photos, results, strict=True):
        assert isinstance(taken_at, datetime)  # bereits oben auf Exceptions geprueft
        photo.taken_at = taken_at

    return added, updated


async def _maybe_commit_progress_checkpoint(
    session: AsyncSession, run: ScanRun, count: int
) -> None:
    """Gemeinsamer Zwischen-Commit-Checkpoint (specs/features/0022-scan-live-fortschrittszaehler.md,
    ADR 0019 Schicht 2) fuer Phase 1 (Enumeration) UND Phase 2a (Skip-Faelle) - ein einziger
    Aufrufpunkt statt der frueheren Closure mit zwei `continue`-Zweigen (specs/features/0036):
    strukturell ausgeschlossen, dass ein Skip-Zweig den Checkpoint verpasst, da jede Iteration in
    Phase 2a denselben Aufruf durchlaeuft."""
    if count % SCAN_COMMIT_BATCH_SIZE == 0:
        run.files_found = count
        run.last_progress_at = _now_utc()
        await session.commit()


async def _enumerate_scan_entries(
    session: AsyncSession,
    client: OpenCloudScanClient,
    webdav_url: str,
    root_path: str,
    scan_run: ScanRun,
) -> list[tuple[str, DavEntry]]:
    """Phase 1 (Enumeration, specs/features/0036-scan-performance-zweiphasig-parallel.md, ADR
    0020, Punkt 1): materialisiert `client.walk(...)` zu einer In-Memory-Liste - KEIN Photo-DB-
    Schreibzugriff, nur periodische files_found/last_progress_at-Checkpoints (bestehende
    Checkpoint-Kadenz, Zweitverwendung von _maybe_commit_progress_checkpoint). Erst nach
    vollstaendigem Abschluss ist die Gesamtzahl bekannt (run_project_scan setzt danach
    ScanRun.total_files)."""
    entries: list[tuple[str, DavEntry]] = []
    files_found = 0
    entry: DavEntry
    async for relative_path, entry in client.walk(webdav_url, root_path):
        entries.append((relative_path, entry))
        files_found += 1
        await _maybe_commit_progress_checkpoint(session, scan_run, files_found)
    return entries


async def run_project_scan(
    session: AsyncSession,
    client: OpenCloudScanClient,
    project: Project,
    drive_name: str | None,
    cache_dir: Path,
) -> ScanRun:
    scan_run = ScanRun(project_id=project.id, status=ScanStatus.RUNNING)
    session.add(scan_run)
    await session.commit()
    await session.refresh(scan_run)

    try:
        drive = await client.resolve_drive(drive_name)

        existing_photos = {
            photo.relative_path: photo
            for photo in (
                await session.execute(select(Photo).where(Photo.project_id == project.id))
            ).scalars()
        }

        # Phase 1 (Enumeration) - siehe _enumerate_scan_entries.
        entries = await _enumerate_scan_entries(
            session, client, drive.webdav_url, project.opencloud_path, scan_run
        )

        # Phasenuebergang (ADR 0020, Punkt 1): total_files wird HIER einmalig gesetzt,
        # files_found auf 0 zurueckgesetzt - das Feld wechselt die Bedeutung von "in Phase 1
        # gelistet" auf "in Phase 2 verarbeitet" (Datenmodell-Bezug der Spec). Sofort committet,
        # damit ein zwischen Phase 1 und Phase 2 beobachtender Client (Polling) diesen konsistenten
        # Zwischenzustand sehen kann (total_files gesetzt, files_found == 0).
        scan_run.total_files = len(entries)
        scan_run.files_found = 0
        scan_run.last_progress_at = _now_utc()
        await session.commit()

        # Phase 2a (Klassifikation, reine Funktion) - siehe _classify_scan_entries.
        classification = _classify_scan_entries(entries, existing_photos)

        files_found = 0
        files_skipped = 0
        for decision in classification.decisions:
            if decision.skip_reason is not None:
                files_found += 1
                if decision.skip_reason is SkipReason.UNSUPPORTED_EXTENSION:
                    files_skipped += 1
                await _maybe_commit_progress_checkpoint(session, scan_run, files_found)

        # Phase 2b (begrenzt parallele Verarbeitung in festen Bloecken) - siehe
        # _process_scan_block. Blockgroesse = settings.scan_download_concurrency (env-
        # ueberschreibbar, ADR 0020 Punkt 5); ein Commit PRO BLOCK (nicht an die
        # SCAN_COMMIT_BATCH_SIZE-Kadenz von Phase 1/2a gekoppelt), das ist zugleich die
        # Crash-Sicherheits-Grenze (Fallstrick 2).
        photos_added = 0
        photos_updated = 0
        # settings.scan_download_concurrency ist per Field(ge=1) in config.py bereits gegen
        # 0/negative Werte validiert (faellt beim Prozessstart auf, test-engineer-/security-
        # engineer-Review-Fund) - kein zusaetzlicher Laufzeit-Clamp hier noetig.
        concurrency = settings.scan_download_concurrency
        work_items = classification.work_items
        for start in range(0, len(work_items), concurrency):
            block = work_items[start : start + concurrency]
            added, updated = await _process_scan_block(
                session, client, drive.webdav_url, cache_dir, project.id, block
            )
            photos_added += added
            photos_updated += updated
            files_found += len(block)
            scan_run.files_found = files_found
            scan_run.last_progress_at = _now_utc()
            await session.commit()

        removed_paths = set(existing_photos) - classification.seen_paths
        for path in removed_paths:
            await session.delete(existing_photos[path])

        scan_run.status = ScanStatus.SUCCESS
        scan_run.finished_at = _now_utc()
        scan_run.files_found = files_found
        scan_run.photos_added = photos_added
        scan_run.photos_updated = photos_updated
        scan_run.photos_removed = len(removed_paths)
        scan_run.files_skipped = files_skipped
        await session.commit()
        return scan_run
    except asyncio.CancelledError:
        # Schicht 1 des Fortschritts-Watchdogs (specs/features/0034-scan-haenger-fortschritts-
        # watchdog.md, ADR 0019): ein arq job_timeout-Ablauf, ein geplanter Worker-Shutdown und ein
        # kuenftiger Job.abort() loesen alle denselben asyncio.CancelledError-Pfad aus (verifiziert
        # im arq-Quellcode, siehe ADR). Anders als die fruehere Annahme (siehe Git-Historie) wird
        # das jetzt bewusst NICHT mehr unbehandelt durchgelassen: der Lauf wird sofort auf FAILED
        # gesetzt, danach re-raised (kein Verschlucken einer BaseException) - arqs eigene
        # Task-/Retry-Buchhaltung funktioniert dadurch unveraendert weiter.
        await _fail_run(
            session, scan_run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown)."
        )
        raise
    except Exception as exc:
        # Terminierungs-Fix (specs/features/0023-scan-fortschritt-batch-groesse-fix.md): vorher
        # wurde hier ausschliesslich OpenCloudError abgefangen - jede andere Exception (z.B. aus
        # dem WebDAV-XML-Parsing, siehe opencloud/client.py::list_folder) lief ungefangen durch
        # und liess den ScanRun dauerhaft auf status="running" haengen, ohne Watchdog/Recovery.
        # OpenCloudError ist eine Teilmenge von Exception, ein einzelner breiter Handler reicht
        # deshalb aus - exakt das bereits bestehende Muster in run_project_scoring unten.
        await _fail_run(session, scan_run, str(exc))
        return scan_run


async def scan_project(ctx: dict[str, Any], project_id: int) -> int:
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        async with OpenCloudClient(
            settings.opencloud_base_url, settings.opencloud_username, settings.opencloud_app_token
        ) as client:
            scan_run = await run_project_scan(
                session,
                client,
                project,
                settings.opencloud_drive_name or None,
                cache_dir=Path(settings.photo_cache_dir),
            )
        return scan_run.id


def _compute_photo_metrics(path: Path) -> tuple[float, float, str] | None:
    """Best-effort wie thumbnails.py::generate_variants: ein nicht (mehr) dekodierbares oder
    ungewoehnliches Bild darf den ScoringRun nicht abbrechen, sondern wird fuer die Metrik-
    Berechnung uebersprungen (Sicherheits-Muss-Kriterium der Spec, DecompressionBombError-Fund aus
    Spec 0002)."""
    try:
        with Image.open(path) as opened:
            opened.load()
            image: Image.Image = opened
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            sharpness = compute_sharpness(image)
            exposure = compute_exposure(image)
            phash = compute_dhash(image)
        return sharpness, exposure, phash
    except Exception:
        return None


async def run_project_scoring(
    session: AsyncSession,
    project: Project,
    cache_dir: Path,
) -> ScoringRun:
    """Scort alle Fotos eines Projekts neu (kein inkrementelles Scoring, technische
    Detailentscheidung der Spec) auf Basis der bereits vom Scan gecachten display-Variante - kein
    erneuter OpenCloud-Download. Ablauf (Architektur-Abschnitt der Spec): ScoringRun anlegen ->
    photos_total setzen -> pro Foto Heuristiken berechnen, PhotoScore upserten,
    photos_processed periodisch committen -> projektweite Duplikat-/Cluster-Erkennung ->
    suggested_status/local_quality_score setzen -> ScoringRun auf success/failed setzen.
    """
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.RUNNING)
    session.add(scoring_run)
    await session.commit()
    await session.refresh(scoring_run)

    try:
        photos = (
            (await session.execute(select(Photo).where(Photo.project_id == project.id)))
            .scalars()
            .all()
        )
        scoring_run.photos_total = len(photos)
        scoring_run.photos_processed = 0
        await session.commit()

        existing_scores: dict[int, PhotoScore] = {}
        if photos:
            existing_scores = {
                score.photo_id: score
                for score in (
                    await session.execute(
                        select(PhotoScore).where(
                            PhotoScore.photo_id.in_([photo.id for photo in photos])
                        )
                    )
                ).scalars()
            }

        now = datetime.now(UTC).replace(tzinfo=None)
        # photo_id -> (sharpness, exposure, phash) fuer alle erfolgreich vermessenen Fotos.
        computed: dict[int, tuple[float, float, str]] = {}
        processed = 0
        for photo in photos:
            path = variant_path(cache_dir, photo.id, photo.etag, "display")
            metrics = _compute_photo_metrics(path) if path.is_file() else None
            # Bekannte, akzeptierte Luecke (Architektur-Review-Fund, siehe Konsequenzen-Abschnitt
            # von decisions/0006-local-scoring-datamodel.md): wird die display-Cache-Datei eines
            # bereits in einem frueheren Lauf erfolgreich gescorten Fotos bis zu diesem Lauf
            # unlesbar, bleibt dessen alte PhotoScore-Zeile unveraendert stehen statt geloescht/
            # invalidiert zu werden - dieser Zweig wird dann einfach nicht betreten. In der Praxis
            # unwahrscheinlich (persistentes Cache-Volume ohne Eviction), aber relevant fuer
            # Phase B, die auf phash/cluster_key aufbaut.
            if metrics is not None:
                sharpness, exposure, phash = metrics
                computed[photo.id] = metrics
                score = existing_scores.get(photo.id)
                if score is None:
                    score = PhotoScore(photo_id=photo.id)
                    session.add(score)
                    existing_scores[photo.id] = score
                # Vollstaendig ueberschreiben statt nur einzelner Felder (Akzeptanzkriterium:
                # "ein erneuter Lauf ... ueberschreibt bestehende PhotoScore-Zeilen vollstaendig")
                # - alte duplicate_of/cluster_key/local_quality_score/suggested_status-Werte aus
                # einem frueheren Lauf duerfen nicht stehen bleiben, bevor der neue Cluster-Pass
                # unten sie ggf. neu setzt.
                score.sharpness = sharpness
                score.exposure = exposure
                score.phash = phash
                score.duplicate_of = None
                score.cluster_key = None
                score.local_quality_score = None
                score.suggested_status = None
                score.computed_at = now

            processed += 1
            if processed % SCORE_COMMIT_BATCH_SIZE == 0:
                scoring_run.photos_processed = processed
                # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-
                # watchdog.md, ADR 0019, Schicht 2) - analog run_project_scan oben.
                scoring_run.last_progress_at = _now_utc()
                await session.commit()

        scoring_run.photos_processed = processed
        await session.commit()

        taken_at_by_id = {photo.id: photo.taken_at for photo in photos}

        duplicate_of_map = assign_duplicate_clusters(
            [
                DuplicateCandidate(photo_id=photo_id, phash=phash, sharpness=sharpness)
                for photo_id, (sharpness, exposure, phash) in computed.items()
            ]
        )

        rejected_ids = set(duplicate_of_map.keys())
        for photo_id, (sharpness, _exposure, _phash) in computed.items():
            if sharpness < SHARPNESS_REJECT_THRESHOLD:
                rejected_ids.add(photo_id)

        remaining_ids = [photo_id for photo_id in computed if photo_id not in rejected_ids]
        cluster_map = assign_time_clusters(
            [
                TimeClusterCandidate(photo_id=photo_id, taken_at=taken_at_by_id[photo_id])
                for photo_id in remaining_ids
            ]
        )

        for photo_id, (sharpness, exposure, _phash) in computed.items():
            score = existing_scores[photo_id]
            if photo_id in rejected_ids:
                score.suggested_status = RatingStatus.REJECTED
                score.duplicate_of = duplicate_of_map.get(photo_id)
            else:
                score.local_quality_score = local_quality_score(sharpness, exposure)
                score.cluster_key = cluster_map[photo_id]

        scoring_run.suggestions_found = len(rejected_ids)
        scoring_run.status = ScanStatus.SUCCESS
        scoring_run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()
        return scoring_run
    except asyncio.CancelledError:
        # Schicht 1 des Fortschritts-Watchdogs (specs/features/0034-scan-haenger-fortschritts-
        # watchdog.md, ADR 0019) - analog run_project_scan oben.
        await _fail_run(
            session, scoring_run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown)."
        )
        raise
    except Exception as exc:
        # Kein Rollback bereits committeter PhotoScore-Zeilen/des letzten committeten
        # photos_processed-Stands (Akzeptanzkriterium der Spec) - session.rollback() verwirft nur
        # die seit dem letzten commit() offene, noch nicht persistierte Transaktion, exakt wie im
        # OpenCloudError-Pfad von run_project_scan oben.
        await _fail_run(session, scoring_run, str(exc))
        return scoring_run


async def score_project(ctx: dict[str, Any], project_id: int) -> int:
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        scoring_run = await run_project_scoring(
            session, project, cache_dir=Path(settings.photo_cache_dir)
        )
        return scoring_run.id


class TopSelectionGuardError(Exception):
    """Fachliche Vorbedingung fuer select_top_photos nicht erfuellt (kein erfolgreicher
    ScoringRun) - wird wie jede andere Exception im umgebenden try/except von run_top_selection als
    FAILED-Lauf mit error_message behandelt (Akzeptanzkriterium der Spec: Guard im Worker-Job,
    zusaetzlich zum eigenen 409 der API-Schicht)."""


def _candidate_pool_size(cluster_size: int, top_n_per_cluster: int) -> int:
    return min(
        cluster_size,
        max(
            top_n_per_cluster * TOP_SELECTION_CANDIDATE_POOL_MULTIPLIER,
            TOP_SELECTION_CANDIDATE_POOL_MINIMUM,
        ),
    )


def _classify_candidate(
    cache_dir: Path, photo: Photo, detector: FaceDetectorLike
) -> PhotoCategory | None:
    """Best-effort wie scoring.py::_compute_photo_metrics (Akzeptanzkriterium der Spec): ein
    einzelner fehlgeschlagener Klassifikationsversuch (fehlende/defekte display-Cache-Datei) darf
    den gesamten Lauf nicht abbrechen - das betroffene Foto bleibt einfach ohne category."""
    path = variant_path(cache_dir, photo.id, photo.etag, "display")
    if not path.is_file():
        return None
    try:
        with Image.open(path) as opened:
            opened.load()
            image: Image.Image = opened
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            return classify_category(image, detector)
    except Exception:
        return None


async def run_top_selection(
    session: AsyncSession,
    project: Project,
    top_n_per_cluster: int,
    cache_dir: Path,
    build_detector: Callable[[], FaceDetectorLike] = build_face_detector,
) -> TopSelectionRun:
    """Waehlt pro Zeitcluster bis zu top_n_per_cluster Top-Fotos aus, unter Beruecksichtigung eines
    Kategorie-Mix (specs/features/0024-top-photo-selection-category-mix.md). Ablauf (Architektur-
    Abschnitt der Spec): TopSelectionRun anlegen -> Guard (letzter ScoringRun muss success sein) ->
    Kandidatenpool pro Cluster bilden (nur suggested_status IS NULL) -> jeden Kandidaten
    klassifizieren (best-effort, periodisch zwischen-committet) -> select_top_n_with_category_mix
    pro Cluster anwenden -> Treffer auf ALBUM_WORTHY setzen -> TopSelectionRun auf success/failed
    setzen. `build_detector` ist injizierbar (Default: die echte, teure Modellkonstruktion) - Tests
    uebergeben stattdessen einen Fake ohne echtes .tflite-Modell (siehe
    test_worker_top_selection.py)."""
    run = TopSelectionRun(
        project_id=project.id, status=ScanStatus.RUNNING, top_n_per_cluster=top_n_per_cluster
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    try:
        latest_scoring_run = (
            await session.execute(
                select(ScoringRun)
                .where(ScoringRun.project_id == project.id)
                .order_by(ScoringRun.started_at.desc())
                .limit(1)
            )
        ).scalars().first()
        if latest_scoring_run is None or latest_scoring_run.status != ScanStatus.SUCCESS:
            raise TopSelectionGuardError(
                "Kein erfolgreicher Scoring-Lauf (Phase A) fuer dieses Projekt vorhanden."
            )

        rows = (
            await session.execute(
                select(Photo, PhotoScore)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.project_id == project.id, PhotoScore.suggested_status.is_(None))
            )
        ).all()

        clusters: dict[str, list[tuple[Photo, PhotoScore]]] = {}
        for photo, score in rows:
            clusters.setdefault(score.cluster_key or "", []).append((photo, score))

        candidate_pools: dict[str, list[tuple[Photo, PhotoScore]]] = {}
        for cluster_key, members in clusters.items():
            pool_size = _candidate_pool_size(len(members), top_n_per_cluster)
            ordered = sorted(
                members, key=lambda member: (-(member[1].local_quality_score or 0.0), member[0].id)
            )
            candidate_pools[cluster_key] = ordered[:pool_size]

        run.candidates_total = sum(len(pool) for pool in candidate_pools.values())
        run.candidates_processed = 0
        await session.commit()

        detector = build_detector()
        classified_by_cluster: dict[str, list[CategoryCandidate]] = {}
        score_by_photo_id: dict[int, PhotoScore] = {photo.id: score for photo, score in rows}
        processed = 0
        for cluster_key, pool in candidate_pools.items():
            candidates: list[CategoryCandidate] = []
            for photo, score in pool:
                category = _classify_candidate(cache_dir, photo, detector)
                # Copilot-Review-Fund (PR #51): `category` immer explizit setzen, auch bei
                # best-effort Fehlschlag (None) - sonst bliebe eine aus einem FRUEHEREN Lauf
                # bereits vorhandene category-Zeile faelschlich stehen, statt geleert zu werden
                # (Akzeptanzkriterium: "das betroffene Foto bleibt ohne category").
                score.category = category
                if category is not None:
                    candidates.append(
                        CategoryCandidate(photo.id, category, score.local_quality_score or 0.0)
                    )
                processed += 1
                if processed % TOP_SELECTION_COMMIT_BATCH_SIZE == 0:
                    run.candidates_processed = processed
                    # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-
                    # watchdog.md, ADR 0019, Schicht 2) - analog run_project_scan oben.
                    run.last_progress_at = _now_utc()
                    await session.commit()
            classified_by_cluster[cluster_key] = candidates

        run.candidates_processed = processed
        await session.commit()

        suggestions_found = 0
        for candidates in classified_by_cluster.values():
            for photo_id in select_top_n_with_category_mix(candidates, top_n_per_cluster):
                score_by_photo_id[photo_id].suggested_status = RatingStatus.ALBUM_WORTHY
                suggestions_found += 1

        run.suggestions_found = suggestions_found
        run.status = ScanStatus.SUCCESS
        run.finished_at = _now_utc()
        await session.commit()
        return run
    except asyncio.CancelledError:
        # Schicht 1 des Fortschritts-Watchdogs (specs/features/0034-scan-haenger-fortschritts-
        # watchdog.md, ADR 0019) - analog run_project_scan/run_project_scoring oben.
        await _fail_run(session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown).")
        raise
    except Exception as exc:
        # Kein Rollback bereits committeter Fortschritts-/Kategorie-Zwischenstaende
        # (Akzeptanzkriterium der Spec, identisches Muster wie run_project_scoring oben).
        await _fail_run(session, run, str(exc))
        return run


async def select_top_photos(ctx: dict[str, Any], project_id: int, top_n_per_cluster: int) -> int:
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        run = await run_top_selection(
            session, project, top_n_per_cluster, cache_dir=Path(settings.photo_cache_dir)
        )
        return run.id


# Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md, ADR 0019):
# grosszuegiger Not-Anker (24h), NICHT der primaere Terminierungsmechanismus - Schicht 2
# (STALL_THRESHOLD, siehe reap_stalled_runs) greift fuer jeden echten Stillstand immer zuerst.
# Begrenzt nur den Ressourcenverbrauch eines (heute nicht vorstellbaren) Defekts in Schicht 2
# selbst. arq-Default waere 300s (5 Minuten) - deutlich zu kurz fuer legitim lange Scans grosser
# Fotobibliotheken (bindende Stakeholder-Anforderung, siehe Spec).
JOB_TIMEOUT_SECONDS = 86400

# Schicht 2 des Fortschritts-Watchdogs (ADR 0019): der eigentliche, fortschrittsbasierte
# Stillstands-Schwellwert - ein RUNNING-Lauf, dessen last_progress_at strikt aelter als dieser Wert
# ist, gilt als haengend, unabhaengig von seiner Gesamtlaufzeit (bindende Stakeholder-Anforderung:
# "nur ein echter Stillstand ist ein Fehler, keine feste Obergrenze").
STALL_THRESHOLD = timedelta(minutes=15)

def _stall_message() -> str:
    # Copilot-Review-Fund (PR #67): die Minutenzahl wird bewusst aus STALL_THRESHOLD abgeleitet
    # statt hart codiert - ein spaeteres Anpassen von STALL_THRESHOLD kann die Meldung damit nicht
    # mehr unbemerkt veralten lassen.
    minutes = int(STALL_THRESHOLD.total_seconds() // 60)
    return (
        f"Kein Fortschritt seit über {minutes} Minuten erkannt — "
        "vermutlich hängender Verarbeitungsschritt."
    )


async def _fail_if_stalled(
    session: AsyncSession, run: ScanRun | ScoringRun | TopSelectionRun
) -> bool:
    """Setzt eine einzelne Zeile ueber _fail_run auf FAILED, isoliert von den uebrigen Zeilen/
    Tabellen (Akzeptanzkriterium der Spec 0034: ein Fehler bei einer Zeile/Tabelle darf die
    Bereinigung der uebrigen nicht blockieren) - ein Fehlschlag hier (z.B. ein DB-Fehler beim
    Commit dieser einen Zeile) rollt nur die aktuelle, noch nicht committete Teiltransaktion
    zurueck, bereits zuvor erfolgreich committete Zeilen bleiben unberuehrt."""
    try:
        await _fail_run(session, run, _stall_message())
        return True
    except Exception:
        await session.rollback()
        return False


async def reap_stalled_runs(
    ctx: dict[str, Any],
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
) -> int:
    """Schicht 2 des Fortschritts-Watchdogs (specs/features/0034-scan-haenger-fortschritts-
    watchdog.md, ADR 0019): periodischer arq-Cron-Job (alle 5 Minuten, siehe
    WorkerSettings.cron_jobs), unabhaengig von einer ggf. tatsaechlich noch haengenden Coroutine -
    deckt exakt den Fall ab, den reines Exception-Handling (Schicht 1, _fail_run oben) strukturell
    nie schliessen kann (ein nie zurueckkehrender await liefert nie eine Exception, an die sich
    anknuepfen liesse). session_factory ist injizierbar (Default: die echte, produktive
    async_session_factory) - Tests uebergeben stattdessen eine an eine In-Memory-SQLite-
    Testdatenbank gebundene Factory, analog zu run_top_selection's build_detector-Parameter. Die
    drei Tabellen werden bewusst nacheinander in drei eigenstaendigen Bloecken behandelt statt
    ueber eine generische Schleife (konsistent mit dem Rest dieser Datei: ScanRun/ScoringRun/
    TopSelectionRun bleiben drei eigenstaendige Modelle ohne gemeinsame Basisklasse, ADR 0019)."""
    reaped = 0
    threshold = _now_utc() - STALL_THRESHOLD
    async with session_factory() as session:
        try:
            stalled_scan_runs = (
                await session.execute(
                    select(ScanRun).where(
                        ScanRun.status == ScanStatus.RUNNING,
                        ScanRun.last_progress_at < threshold,
                    )
                )
            ).scalars().all()
        except Exception:
            # architect-Review-Fund (Spec 0034): ohne rollback() bliebe die Transaktion auf einer
            # echten Postgres-Verbindung nach einem fehlgeschlagenen SELECT im Zustand "current
            # transaction is aborted" - die nachfolgenden SELECTs fuer ScoringRun/TopSelectionRun
            # wuerden dann selbst fehlschlagen, obwohl inhaltlich nichts mit ihnen falsch ist. Das
            # wuerde das Akzeptanzkriterium "ein Fehler bei einer Tabelle blockiert die
            # Bereinigung der uebrigen nicht" in Produktion unterlaufen - im SQLite-Testsetup
            # unsichtbar, da dort eine vor jedem DB-Zugriff geworfene Python-Exception die
            # DBAPI-Transaktion nie tatsaechlich invalidiert.
            await session.rollback()
            stalled_scan_runs = []
        for scan_run in stalled_scan_runs:
            if await _fail_if_stalled(session, scan_run):
                reaped += 1

        try:
            stalled_scoring_runs = (
                await session.execute(
                    select(ScoringRun).where(
                        ScoringRun.status == ScanStatus.RUNNING,
                        ScoringRun.last_progress_at < threshold,
                    )
                )
            ).scalars().all()
        except Exception:
            await session.rollback()
            stalled_scoring_runs = []
        for scoring_run in stalled_scoring_runs:
            if await _fail_if_stalled(session, scoring_run):
                reaped += 1

        try:
            stalled_top_selection_runs = (
                await session.execute(
                    select(TopSelectionRun).where(
                        TopSelectionRun.status == ScanStatus.RUNNING,
                        TopSelectionRun.last_progress_at < threshold,
                    )
                )
            ).scalars().all()
        except Exception:
            await session.rollback()
            stalled_top_selection_runs = []
        for top_selection_run in stalled_top_selection_runs:
            if await _fail_if_stalled(session, top_selection_run):
                reaped += 1

    return reaped


class WorkerSettings:
    # arq.worker.func(...) statt nackter Funktionsreferenzen (Fortschritts-Watchdog, ADR 0019):
    # max_tries=1 deaktiviert arqs automatischen Hintergrund-Retry vollstaendig - ein durch
    # job_timeout abgebrochener Job erzeugt dadurch KEINE zweite Run-Zeile (arq prueft
    # job_try > max_tries VOR dem erneuten Coroutine-Aufruf, verifiziert im arq-Quellcode). Damit
    # gilt strukturell: ein Nutzer-Trigger -> genau ein Lauf -> ein eindeutiger Endzustand,
    # sichtbar ueber die bestehende "Erneut versuchen"-UI (Spec 0017/0023) statt eines
    # unsichtbaren automatischen Wiederholungsversuchs.
    functions = (
        arq_func(scan_project, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
        arq_func(score_project, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
        arq_func(select_top_photos, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
    )
    # Schicht 2 des Fortschritts-Watchdogs (ADR 0019), erste Nutzung von arqs Cron-Mechanismus im
    # Projekt: run_at_startup=True sorgt dafuer, dass ein Worker-Neustart sofort eine erste
    # Pruefung ausloest, statt bis zu 5 Minuten auf den naechsten regulaeren Tick zu warten (genau
    # der Bug-Report-Fall: eine bereits vor dem Neustart haengende Zeile soll nicht unnoetig lang
    # unentdeckt bleiben).
    cron_jobs = (cron(reap_stalled_runs, minute=set(range(0, 60, 5)), run_at_startup=True),)
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
