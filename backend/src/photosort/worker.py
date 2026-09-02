from __future__ import annotations

import asyncio
import enum
import logging
import os
from collections.abc import Callable, Collection, Sequence
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

from photosort.aesthetics import AestheticsModelLike, build_aesthetics_model, compute_aesthetics
from photosort.categories import LOCAL_CATEGORY_SIGNALS, resolve_category
from photosort.classification import (
    FaceBoundingBox,
    FaceDetectorLike,
    FaceLandmarkerLike,
    ObjectDetection,
    ObjectDetectorLike,
    SceneClassifierLike,
    SceneLabel,
    build_face_detector,
    build_face_landmarker,
    build_object_detector,
    build_scene_classifier,
    classify_scene,
    detect_face_orientation,
    detect_objects,
    detect_person,
)
from photosort.cloud_vision import TokenUsage, vision_model_for_provider
from photosort.config import settings
from photosort.criteria import (
    CRITERIA_REGISTRY,
    animal_detections,
    compute_content_landscape,
    compute_essen_trinken_score,
    compute_fahrzeug_score,
    compute_freiraum_score,
    compute_gebaeude_score,
    compute_golden_ratio_score,
    compute_landmark_score,
    compute_landschaft_score,
    compute_symmetrie_score,
    compute_tier_score,
    content_people_from_faces,
    is_landmark_candidate,
    normalize_exposure,
    normalize_sharpness,
)
from photosort.db import async_session_factory
from photosort.horizon import compute_horizon_tilt_score
from photosort.label_embedding import LabelEmbedderLike, build_label_embedder
from photosort.landmark import (
    LandmarkClientLike,
    LandmarkDetection,
    build_landmark_client,
)
from photosort.logging_config import configure_logging
from photosort.models import (
    ClassificationPhase,
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    FineLabel,
    Photo,
    PhotoCategoryClassification,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoFineLabel,
    PhotoLandmarkDetection,
    PhotoRanking,
    PhotoScore,
    Project,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
)
from photosort.opencloud.client import IMAGE_EXTENSIONS, OpenCloudClient, OpenCloudError
from photosort.opencloud.exif import extract_taken_at
from photosort.opencloud.webdav_xml import DavEntry
from photosort.pricing import compute_cost_usd
from photosort.ranking import rank_photos
from photosort.remote_classification import (
    CategoryDetectionClientLike,
    FineLabelSnapshotEntry,
    RemoteClassification,
    build_category_classification_client,
    resolve_canonical_label,
)
from photosort.scoring import (
    SHARPNESS_REJECT_THRESHOLD,
    DuplicateCandidate,
    TimeClusterCandidate,
    assign_duplicate_clusters,
    assign_time_clusters,
    compute_dhash,
    compute_exposure,
    compute_sharpness,
)
from photosort.thumbnails import generate_variants, variant_path

# specs/features/0056-structured-logging-cloud-vision-errors.md, ADR 0034 Punkt 2: idiomatisches
# Standard-Pattern, Modul-Konstante direkt nach den Imports - kein Logger-Objekt wird injiziert/
# durchgereicht. worker.py ist die einzige Stelle mit Zugriff auf sowohl die Exception als auch
# den Foto-Kontext (landmark.py/remote_classification.py/cloud_vision.py brauchen dafuer keinen
# eigenen Logger).
logger = logging.getLogger(__name__)

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

# Analog SCORE_COMMIT_BATCH_SIZE, fuer CriterionScoringRun.photos_processed
# (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md, ersetzt das fruehere
# TOP_SELECTION_COMMIT_BATCH_SIZE/TopSelectionRun). Kleiner als SCORE_COMMIT_BATCH_SIZE, da
# mediapipe-Inferenz (content_people-Kriterium) pro Foto eine spuerbare Laufzeit hat (Architektur-
# Abschnitt der Spec) - ein grober Batch von 25 wuerde den Live-Fortschritt bei typischen
# Ausschuss-Ueberlebenden-Mengen faktisch einfrieren, aehnlich dem in Spec 0023 behobenen
# Scan-Zaehler-Problem. Modul-Konstante statt Default-Parameterwert, damit Tests sie per
# monkeypatch.setattr(worker, "CRITERION_SCORING_COMMIT_BATCH_SIZE", ...) verkleinern koennen.
CRITERION_SCORING_COMMIT_BATCH_SIZE = 5

# specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR decisions/0025-cloud-
# landmark-erkennung.md Punkt 4: der Cloud-Aufruf nutzt ausschliesslich die bestehende
# display-Cache-Variante, die thumbnails.py::generate_variants immer als JPEG schreibt - fester
# Wert statt einer Format-Erkennung. Umbenannt von _LANDMARK_IMAGE_MIME_TYPE
# (specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md): identisches
# Bildquellen-Muss-Kriterium (ADR 0032 Punkt 5) gilt jetzt fuer BEIDE Cloud-Vision-Pfade.
_CLOUD_VISION_IMAGE_MIME_TYPE = "image/jpeg"

# Default-Gewichtung fuer ranking.py::rank_photos (Akzeptanzkriterium der Spec: "nur die
# strukturelle Faehigkeit ist Teil dieser Spec, kein konkreter Default" - Gleichgewichtung aller
# im Register bekannten Kriterien ist der einfachste, austauschbare Platzhalter, siehe ADR 0021
# Punkt 3). Die eigentliche, spaetere Gewichtungs-/Formel-Entscheidung aendert nur diesen
# Aufrufer-Default, nie das Datenmodell oder rank_photos selbst.
DEFAULT_CRITERION_WEIGHTS: dict[str, float] = {key: 1.0 for key in CRITERIA_REGISTRY}


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
        if extension not in IMAGE_EXTENSIONS:
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
    run: ScanRun | ScoringRun | CriterionScoringRun | RemoteCategoryClassificationRun,
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
    if isinstance(run, CriterionScoringRun):
        # specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, ADR 0050 Punkt 3:
        # `phase = NULL` heisst "laeuft nicht mehr" - das gilt fuer einen fehlgeschlagenen Lauf
        # genauso wie fuer einen erfolgreichen. HIER statt in run_classification/
        # run_criterion_scoring, weil _fail_run der einzige gemeinsame "auf FAILED setzen"-Pfad
        # ist: er wird auch vom Fortschritts-Watchdog (reap_stalled_runs -> _fail_if_stalled)
        # benutzt, der einen haengenden Lauf abraeumt, ohne dass die Job-Coroutine je zurueckkehrt.
        # `phase` existiert nur auf CriterionScoringRun, deshalb die isinstance-Pruefung statt
        # eines gemeinsamen Basisklassen-Feldes (die vier Run-Modelle haben bewusst keine, ADR
        # 0019).
        run.phase = None
    await session.commit()
    # Copilot-Review-Fund (PR #67): das vorangehende rollback() expired ORM-Objekte der Session -
    # ohne dieses refresh() koennte ein direkter Attributzugriff auf `run` NACH der Rueckkehr aus
    # _fail_run (z.B. `run.id` in scan_project/score_project/classify, die den
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
    suggested_status setzen -> ScoringRun auf success/failed setzen. `local_quality_score` (Spec
    0024) ist mit specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md entfallen -
    Ranking-Grundlage ist jetzt die Kriterien-/Rangfolgen-Schicht (criteria.py/ranking.py).
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
                # - alte duplicate_of/cluster_key/suggested_status-Werte aus einem frueheren Lauf
                # duerfen nicht stehen bleiben, bevor der neue Cluster-Pass unten sie ggf. neu
                # setzt.
                score.sharpness = sharpness
                score.exposure = exposure
                score.phash = phash
                score.duplicate_of = None
                score.cluster_key = None
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

        for photo_id in computed:
            score = existing_scores[photo_id]
            if photo_id in rejected_ids:
                score.suggested_status = RatingStatus.REJECTED
                score.duplicate_of = duplicate_of_map.get(photo_id)
            else:
                score.cluster_key = cluster_map[photo_id]

        scoring_run.suggestions_found = len(rejected_ids)
        scoring_run.status = ScanStatus.SUCCESS
        scoring_run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        # Ausschuss-Gate-Autoset (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
        # backfill.md): kein Ausschuss gefunden -> nichts zu sichten, das Gate blockiert dann
        # nicht mit einer leeren Liste. Ein nachfolgender expliziter confirm-ausschuss-gate-
        # Aufruf bleibt trotzdem fehlerfrei moeglich (Idempotenz, siehe api/projects.py).
        if scoring_run.suggestions_found == 0:
            scoring_run.gate_confirmed_at = _now_utc()
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


class CriterionScoringGuardError(Exception):
    """Fachliche Vorbedingung fuer run_criterion_scoring nicht erfuellt (die uebergebene
    scoring_run_id ist nicht mehr der aktuell neueste erfolgreiche ScoringRun, z.B. wegen eines
    zwischenzeitlichen Re-Scan/Re-Scoring) - wird wie jede andere Exception im umgebenden
    try/except als FAILED-Lauf mit error_message behandelt (Akzeptanzkriterium der Spec: Guard im
    Worker-Job, zusaetzlich zum eigenen 409 der API-Schicht, ADR 0021 Punkt 7)."""


# Die von _compute_content_criteria best-effort berechneten Kriterien-Keys (specs/features/
# 0037/0038) - eine Liste statt sechs einzelner if-Bloecke im Aufrufer, damit ein weiteres
# kuenftiges Bild-basiertes Kriterium keine Kopie des Upsert-Codes braucht. Die zugehoerige
# CriterionSource wird bewusst NICHT hier dupliziert, sondern direkt aus criteria.py::
# CRITERIA_REGISTRY abgeleitet (Copilot-Review-Fund, PR #88) - eine kuenftige Aenderung an der
# Registry (z.B. ein Kriterium wechselt von local_heuristic zu local_ml) bleibt so automatisch
# konsistent, ohne dass diese Stelle separat nachgepflegt werden muss.
#
# Umbenannt von _CONTENT_CRITERION_KEYS/_CONTENT_CRITERION_SOURCES (specs/features/0045-
# kategorien-aus-statistiken-ableiten.md, ADR 0023): bezeichnet weiterhin die bildbasiert
# berechneten Kriterien fuer die Upsert-Buchhaltung (inkl. goldener_schnitt/aesthetics, die NIE
# eine Kategorie bilden duerfen) - eine fachlich andere Menge als CriterionDefinition.
# category_eligible (welche Kriterien ueberhaupt eine Kategorie bilden DUERFEN). Rein kosmetische
# Umbenennung, keine Verhaltensaenderung.
_IMAGE_ANALYSIS_CRITERION_KEYS: tuple[str, ...] = (
    "content_people",
    "content_landscape",
    "tier",
    "goldener_schnitt",
    "gebaeude",
    # specs/features/0217-landschaft-erkennung-spezifitaets-vorrang.md ab hier (zweites Kriterium
    # aus derselben Szenen-Klassifikation, siehe _compute_content_criteria).
    "landschaft",
    "aesthetics",
    # specs/features/0289-feste-kategorien.md ab hier: zwei weitere Kriterien aus DERSELBEN
    # COCO-Detektorausgabe wie `tier` (siehe _compute_content_criteria).
    "fahrzeug",
    "essen_trinken",
    # specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md ab hier.
    "symmetrie",
    "horizont",
    "freiraum",
)
_IMAGE_ANALYSIS_CRITERION_SOURCES: dict[str, CriterionSource] = {
    key: CRITERIA_REGISTRY[key].source for key in _IMAGE_ANALYSIS_CRITERION_KEYS
}


def _try_build[T](build: Callable[[], T]) -> T | None:
    """Best-effort Modell-/Detektor-Konstruktion (Copilot-Review-Fund, PR #88): ein Fehlschlag
    GENAU EINES Builders (fehlendes/defektes Asset, mediapipe-/tensorflow-Laufzeitproblem) darf
    weder den gesamten CriterionScoringRun noch die von den UEBRIGEN, erfolgreich gebauten
    Modellen abhaengigen Kriterien mit sich reissen - konsistent mit dem Best-effort-Grundsatz,
    der bereits fuer die einzelnen Kriterien-Berechnungen selbst gilt (siehe
    _compute_content_criteria)."""
    try:
        return build()
    except Exception:
        return None


def _select_landmark_candidates(
    candidate_values: dict[int, dict[str, float]], already_scored_photo_ids: set[int]
) -> list[int]:
    """Vorfilterung + Skip-bereits-gescorter-Fotos fuer den landmark-Cloud-Aufruf
    (specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR decisions/0025-
    cloud-landmark-erkennung.md Punkt 3) - reine, DB-freie Funktion, isoliert unit-testbar (analog
    _classify_scan_entries). Ein Foto wird nur dann Kandidat, wenn im selben Lauf content_landscape
    ODER gebaeude die jeweils registrierte category_presence_threshold erreicht (`>=`, inklusiv,
    Wiederverwendung der bereits vorhandenen Registry-Schwellwerte statt eines neuen, doppelt
    gepflegten Grenzwerts) UND noch keine landmark-Zeile aus einem frueheren Lauf existiert (die
    einzige, bewusst dokumentierte Ausnahme vom sonst projektweiten "jeder Lauf scort neu"-
    Prinzip). Gibt die photo_id-Reihenfolge von candidate_values zurueck (Einfuege-/Verarbeitungs-
    reihenfolge der Foto-Schleife, keine weitere Sortierung noetig).

    Die eigentliche Schwellenwert-Pruefung lebt seit specs/features/0058-cloud-vision-status-
    transparenz.md/decisions/0035-cloud-vision-attempt-fehler-persistierung.md Punkt 4 in
    criteria.py::is_landmark_candidate (gemeinsam mit der API-seitigen Read-Time-Ableitung
    genutzt) - hier bleibt nur noch das Skip-bereits-gescorter-Fotos-Verhalten, das worker-
    spezifisch bleibt (keine API-Entsprechung)."""
    candidates: list[int] = []
    for photo_id, values in candidate_values.items():
        if photo_id in already_scored_photo_ids:
            continue
        if is_landmark_candidate(values):
            candidates.append(photo_id)
    return candidates


def _log_cloud_vision_failure(
    phase: str, photo_id: int, relative_path: str, exc_type_name: str, exc_message: str
) -> None:
    """Strukturiertes WARNING-Logging fuer einen best-effort uebersprungenen Cloud-Vision-Aufruf
    (specs/features/0056-structured-logging-cloud-vision-errors.md, ADR 0034) - gemeinsam genutzt
    von der Landmark-Phase (run_criterion_scoring) und der Remote-Kategorie-Phase
    (run_remote_category_classification). Level WARNING statt ERROR (ADR 0034 Punkt 3): der Skip
    ist erwartetes, dokumentiertes best-effort-Verhalten (ADR 0025 Punkt 3/ADR 0032 Punkt 5), der
    Lauf selbst bleibt SUCCESS. Kein exc_info=True/Traceback (ADR 0034 Punkt 5) - eine Zeile pro
    fehlgeschlagenem Foto reicht fuer Fehlergrund + Foto-Kontext.

    `exc_type_name`/`exc_message` statt der rohen Exception (Copilot-Review-Fund auf PR #255,
    specs/features/0058-cloud-vision-status-transparenz.md/ADR 0035 Punkt 3): der Aufrufer
    berechnet `type(exc).__name__`/`str(exc)` GENAU EINMAL an der jeweiligen Call-Site und reicht
    beide Werte sowohl hierher als auch an `_record_cloud_vision_error` durch - keine zweite,
    potenziell abweichende Auswertung an zwei Stellen (auch wenn `type()`/`str()` reine Funktionen
    sind und ein tatsaechliches Auseinanderlaufen hier nie beobachtbar war, war die vorherige
    Fassung eine dokumentierte, aber nicht eingehaltene Architektur-Vorgabe). `exc_message` wird
    ausschliesslich aus der bereits an der Exception-Konstruktionsstelle sanitierten Meldung
    uebernommen (siehe cloud_vision.py::raise_for_vision_api_status/*_response_to_json, bestehendes
    Sicherheits-Muss-Kriterium aus ADR 0025/0031/0032) - hier NIE erneut auf
    response.text/.json()/.headers zugreifen."""
    logger.warning(
        "Cloud-Vision-Aufruf fehlgeschlagen (%s): photo_id=%s relative_path=%s %s: %s",
        phase,
        photo_id,
        relative_path,
        exc_type_name,
        exc_message,
    )


# specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
# fehler-persistierung.md Punkt 2: defensive Obergrenze fuer eine entartete Fehlermeldung, analog
# remote_classification.py::MAX_REMOTE_LABEL_LENGTH - die eigentliche Absicherung bleibt die in
# ADR 0034 Punkt 5 verifizierte str(exc)-Konstruktion (keine Secrets/Rohdaten), diese Kappung ist
# nur eine Storage-/Degenerationsgrenze.
#
# Sicherheits-Muss-Kriterium der Spec 0058 (Nachschaerfung von ADR 0034 Punkt 5, da die
# Zielgruppe dieser Fehlermeldung jetzt vom Server-Log-Leser zum App-Nutzer waechst): vor der
# Umsetzung verifiziert, ob str(exc) bei einem von httpx.HTTPError gewrappten Netzwerkfehler
# (landmark.py::LandmarkApiError/remote_classification.py::RemoteCategoryClassificationApiError,
# jeweils "... API nicht erreichbar: {exc}") URL-Query-Parameter enthalten koennte. Ergebnis:
# NEIN, aus zwei unabhaengigen Gruenden. (1) Beide Call-Sites rufen ausschliesslich die fest
# codierten URL-Konstanten ANTHROPIC_MESSAGES_URL/MISTRAL_CHAT_COMPLETIONS_URL auf
# (cloud_vision.py) - beide ohne Query-String, jeglicher Payload (Bilddaten/API-Key) wird per
# POST-Body/-Header uebertragen, nie als Query-Parameter. (2) Selbst wenn eine URL Query-Parameter
# enthielte, haengt httpx.HTTPError.__str__() diese nicht automatisch an - empirisch verifiziert
# (httpx 0.27+): sowohl httpx.ConnectError als auch httpx.TimeoutException geben ausschliesslich
# die dem Konstruktor uebergebene Nachricht zurueck (z.B. "Connection refused"), unabhaengig davon,
# ob eine .request mit Query-Parametern angehaengt ist.
_MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH = 500


async def _record_cloud_vision_error(
    session: AsyncSession,
    photo_id: int,
    phase: CloudVisionPhase,
    exc_type_name: str,
    exc_message: str,
    now: datetime,
) -> None:
    """Upsert der letzten bekannten Fehler-Zeile fuer dieses Foto x CloudVisionPhase (ADR 0035
    Punkt 2/3) - bewusst getrennt von _log_cloud_vision_failure (ephemeres Log vs. dauerhafte,
    per API abrufbare Persistenz mit Lösch-Pfad bei Erfolg, siehe dortiger Docstring). Nimmt
    `exc_type_name`/`exc_message` bereits fertig berechnet entgegen (Copilot-Review-Fund auf PR
    #255) - der Aufrufer berechnet `type(exc).__name__`/`str(exc)` GENAU EINMAL an der jeweiligen
    Call-Site und reicht beide Werte sowohl hierher als auch an _log_cloud_vision_failure durch,
    keine zweite Auswertung derselben Exception an zwei Stellen. Reines `session.add`/Attribut-
    Update, kein eigener Commit (Persistierung laeuft ueber die bereits bestehenden periodischen
    Commit-Punkte der jeweiligen Schleife, analog _upsert_landmark_detection)."""
    existing = await session.get(PhotoCloudVisionError, (photo_id, phase))
    if existing is None:
        existing = PhotoCloudVisionError(photo_id=photo_id, phase=phase)
        session.add(existing)
    existing.error_type = exc_type_name
    existing.error_message = exc_message[:_MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH]
    existing.attempted_at = now


async def _clear_cloud_vision_error(
    session: AsyncSession, photo_id: int, phase: CloudVisionPhase
) -> None:
    """Loescht eine ggf. vorhandene Fehler-Zeile nach einem erfolgreichen (Retry-)Versuch (ADR
    0035 Punkt 2: "Aufraeumen bei Erfolg") - haelt die Tabelle konsistent mit ihrer eigenen
    Bedeutung ("letzter bekannter Versuch ist fehlgeschlagen"), auch wenn die Prioritaets-Kaskade
    in api/photos.py::_cloud_vision_status_out einen vergessenen Aufruf funktional abfangen
    wuerde (Erfolg schlaegt Fehler)."""
    existing = await session.get(PhotoCloudVisionError, (photo_id, phase))
    if existing is not None:
        await session.delete(existing)


async def _detect_landmark_for_photo(
    client: LandmarkClientLike, cache_dir: Path, photo: Photo
) -> LandmarkDetection:
    """Der reine I/O-/Netzwerk-Teil eines einzelnen Landmark-Kandidaten (analog
    _fetch_and_thumbnail) - bewusst OHNE Session-Zugriff, damit mehrere Aufrufe sicher parallel
    per asyncio.gather laufen koennen (siehe die Block-Schleife in run_criterion_scoring). Nutzt
    ausschliesslich die bereits vorhandene display-Cache-Variante (ADR 0025 Punkt 4), nie das
    Original - kein erneuter OpenCloud-Zugriff. Ein fehlender/nicht lesbarer Cache-Eintrag
    propagiert als gewoehnliche Exception (best-effort ueber return_exceptions=True in der
    aufrufenden Block-Schleife abgefangen), exakt wie ein LandmarkApiError des Clients selbst."""
    path = variant_path(cache_dir, photo.id, photo.etag, "display")
    image_bytes = path.read_bytes()
    return await client.detect(image_bytes, _CLOUD_VISION_IMAGE_MIME_TYPE)


async def _upsert_landmark_detection(
    session: AsyncSession, photo_id: int, detection: LandmarkDetection, now: datetime, provider: str
) -> None:
    """Legt eine photo_landmark_detections-Zeile nur an, wenn tatsaechlich ein Name identifiziert
    wurde (ADR 0025 Punkt 6, kein Platzhalter-"unbekannt") - wird nur aufgerufen, wenn
    detection.name is not None (siehe Aufrufer). `provider` (specs/features/0054-mistral-
    provider-option-cloud-landmark.md, ADR 0031 Punkt 5) wird atomar mit name/confidence gesetzt -
    dieser Aufruf feuert praktisch nie fuer ein bereits gescortes Foto (Skip ueber
    _select_landmark_candidates anhand von PhotoCriterionScore, providerunabhaengig), ein
    Providerwechsel ueberschreibt das Feld bei bereits gescorten Fotos deshalb nicht."""
    assert detection.name is not None
    existing = await session.get(PhotoLandmarkDetection, photo_id)
    if existing is None:
        existing = PhotoLandmarkDetection(photo_id=photo_id)
        session.add(existing)
    existing.name = detection.name
    existing.confidence = detection.confidence
    existing.computed_at = now
    existing.provider = provider


async def _remote_category_candidates(
    session: AsyncSession, photo_ids: Collection[int]
) -> dict[int, list[str]]:
    """specs/features/0289-feste-kategorien.md, Umsetzungsschritt 5: liest die bereits vorhandenen
    `photo_category_classifications`-Zeilen (seit specs/features/0296-klassifizierung-ein-
    ausloeser-cloud-checkbox.md im Regelfall aus Phase 1 DESSELBEN Laufs, davor aus einem
    frueheren, separat ausgeloesten Lauf - in beiden Faellen KEIN Cloud-Aufruf hier) und liefert
    je Foto die VALIDIERTE Remote-Kandidatenliste.

    Ersetzt das abgeloeste `_merge_remote_category_labels`: dort wurden Remote-Ergebnisse als
    `remote:<canonical_key>`-PSEUDO-KRITERIEN in dieselbe Struktur gemischt, die auch die
    Kriterien-Werte fuehrte (ADR 0032 Punkt 1) - genau die Vermischung von Mess-Signal und
    Taxonomie, die ADR 0049 aufloest. Kandidaten gehen jetzt als reine Kategorie-Keys in
    `resolve_category` ein, gleichberechtigt neben den lokalen Signalen.

    Gemeinsam genutzt von `run_criterion_scoring` UND der Override-Rekonstruktion in
    `api/photos.py` (DRY) - beide leiten die Kategorie damit ueber denselben Codepfad ab."""
    if not photo_ids:
        return {}

    rows = (
        await session.execute(
            select(
                PhotoCategoryClassification.photo_id,
                PhotoCategoryClassification.detected_categories,
            ).where(PhotoCategoryClassification.photo_id.in_(photo_ids))
        )
    ).all()
    return {photo_id: list(detected) for photo_id, detected in rows}


def derive_photo_category(
    criterion_values: dict[str, float], remote_candidates: Sequence[str]
) -> str:
    """Die EINE Kategorie eines Fotos (specs/features/0289-feste-kategorien.md, ADR 0049).

    Lokale Signale und Remote-Kategorien sind zwei Zulieferer EINER Kandidatenmenge; welche
    gewinnt, entscheidet ausschliesslich die feste Vorrangreihenfolge in
    `categories.py::resolve_category`. Die HERKUNFT eines Kandidaten beeinflusst das Ergebnis
    nicht (Akzeptanzkriterium) - dieselbe Kandidatenmenge liefert dieselbe Kategorie, egal ob sie
    lokal oder remote entstanden ist.

    Ein lokales Signal gilt als Kandidat, wenn IRGENDEINES der in `LOCAL_CATEGORY_SIGNALS`
    hinterlegten Kriterien seine registrierte `category_presence_threshold` erreicht (`>=`,
    inklusiv). Ohne jeden Kandidaten ist das Ergebnis `nicht_erkannt` (kein Sonderfallcode - das
    faellt bereits aus `resolve_category` heraus)."""
    candidates: set[str] = set(remote_candidates)
    for category_key, criterion_keys in LOCAL_CATEGORY_SIGNALS.items():
        for criterion_key in criterion_keys:
            definition = CRITERIA_REGISTRY.get(criterion_key)
            if definition is None or definition.category_presence_threshold is None:
                continue
            if criterion_values.get(criterion_key, 0.0) >= definition.category_presence_threshold:
                candidates.add(category_key)
                break
    return resolve_category(candidates)


def _compute_content_criteria(
    cache_dir: Path,
    photo: Photo,
    face_detector: FaceDetectorLike | None,
    animal_detector: ObjectDetectorLike | None,
    scene_classifier: SceneClassifierLike | None,
    aesthetics_model: AestheticsModelLike | None,
    face_landmarker: FaceLandmarkerLike | None,
) -> dict[str, float]:
    """Best-effort wie scoring.py::_compute_photo_metrics (Akzeptanzkriterium der Spec 0037/0038):
    JEDES hier berechnete Kriterium hat sein EIGENES try/except - ein einzelner fehlgeschlagener
    Berechnungsversuch (fehlende/defekte display-Cache-Datei, Modell-Ladefehler in genau einem
    Detektor) darf weder den gesamten Lauf noch die UEBRIGEN, unabhaengig berechenbaren Kriterien
    desselben Fotos mit sich reissen (Spec-0038-AK: "Je Kriterium mindestens ein eigener
    Fehlerfall-Testlauf") - das jeweils betroffene Kriterium bleibt fuer dieses Foto einfach
    ungeschrieben (kein Platzhalterwert wie 0). Die fuenf Detektoren/Modelle (face_landmarker seit
    specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md dazugekommen) sind
    hier bewusst `| None` typisiert (Copilot-Review-Fund, PR #88): schlug der zugehoerige
    `_try_build`-Aufruf im Aufrufer bereits fehl, wird das betroffene Kriterium (bzw. die davon
    abhaengigen) hier einfach uebersprungen, statt mit einem ungueltigen Objekt eine Exception zu
    provozieren, die erst durch das try/except unten "zufaellig" richtig behandelt wuerde.

    detect_person/detect_objects werden je HOECHSTENS einmal aufgerufen und fuer mehrere davon
    abhaengige Kriterien wiederverwendet (content_people+goldener_schnitt bzw. tier+fahrzeug+
    essen_trinken+goldener_schnitt seit specs/features/0289-feste-kategorien.md,
    Akzeptanzkriterium der Spec: Wiederverwendungsnachweis statt Reimplementierung) - vermeidet
    einen zweiten, teuren detect()-Aufruf pro Foto und
    Detektortyp (ADR 0022, Performance-Ueberlegung). goldener_schnitt wird nur dann berechnet,
    wenn BEIDE zugrunde liegenden Detektionen (auch mit leerem Ergebnis) erfolgreich waren - ein
    fehlgeschlagener Detektor darf nicht stillschweigend als "kein Subjekt gefunden" interpretiert
    werden, das waere ein unentdeckter Fehler statt eines ungeschriebenen Kriteriums."""
    path = variant_path(cache_dir, photo.id, photo.etag, "display")
    if not path.is_file():
        return {}
    try:
        with Image.open(path) as opened:
            opened.load()
            image: Image.Image = opened
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
    except Exception:
        return {}

    values: dict[str, float] = {}

    faces: list[FaceBoundingBox] | None = None
    if face_detector is not None:
        try:
            faces = detect_person(image, face_detector)
            values["content_people"] = content_people_from_faces(faces)
        except Exception:
            faces = None

    # specs/features/0289-feste-kategorien.md, Umsetzungsschritt 2: EIN detect_objects-Aufruf
    # speist jetzt drei Kriterien plus goldener_schnitt. Die Objekt-Erkennung und JEDE der drei
    # Score-Berechnungen haben ein EIGENES try/except - ein Fehler in einer Score-Funktion darf
    # die beiden anderen nicht mitreissen (dieselbe Verschaerfung wie bei gebaeude/landschaft
    # unten, ADR 0047 Punkt 3).
    objects: list[ObjectDetection] | None = None
    if animal_detector is not None:
        try:
            objects = detect_objects(image, animal_detector)
        except Exception:
            objects = None
        if objects is not None:
            try:
                values["tier"] = compute_tier_score(objects)
            except Exception:
                pass
            try:
                values["fahrzeug"] = compute_fahrzeug_score(objects)
            except Exception:
                pass
            try:
                values["essen_trinken"] = compute_essen_trinken_score(objects)
            except Exception:
                pass

    try:
        values["content_landscape"] = compute_content_landscape(image)
    except Exception:
        pass

    # specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md, ADR 0026 Punkt 1:
    # keine Modell-/Detektor-Abhaengigkeit - wie content_landscape UNCONDITIONAL berechnet.
    try:
        values["symmetrie"] = compute_symmetrie_score(image)
    except Exception:
        pass

    # ADR 0026 Punkt 2: klassischer cv2-Algorithmus ohne trainiertes Modell - ebenfalls
    # UNCONDITIONAL berechnet, kein injizierbarer Detektor/Builder noetig.
    try:
        values["horizont"] = compute_horizon_tilt_score(image)
    except Exception:
        pass

    # specs/features/0217-landschaft-erkennung-spezifitaets-vorrang.md, ADR 0047 Punkt 1:
    # classify_scene wird GENAU EINMAL pro Foto aufgerufen, dieselbe Label-Liste speist gebaeude
    # UND landschaft (Wiederverwendungsmuster wie detect_person -> content_people +
    # goldener_schnitt; Akzeptanzkriterium AK8: keine zusaetzlichen Kosten pro Foto). Die
    # Label-Ermittlung und jede der beiden Score-Berechnungen haben ein EIGENES try/except - ein
    # Fehler in einer Score-Funktion darf das jeweils andere Kriterium nicht mitreissen (bis zu
    # dieser Spec stand beides in einer Anweisung).
    if scene_classifier is not None:
        scene_labels: list[SceneLabel] | None = None
        try:
            scene_labels = classify_scene(image, scene_classifier)
        except Exception:
            scene_labels = None
        if scene_labels is not None:
            try:
                values["gebaeude"] = compute_gebaeude_score(scene_labels)
            except Exception:
                pass
            try:
                values["landschaft"] = compute_landschaft_score(scene_labels)
            except Exception:
                pass

    if aesthetics_model is not None:
        try:
            values["aesthetics"] = compute_aesthetics(image, aesthetics_model)
        except Exception:
            pass

    if faces is not None and objects is not None:
        try:
            # Verhaltenserhalt (specs/features/0289-feste-kategorien.md, testpflichtig): nur die
            # TIER-Erkennungen sind Kompositions-Subjekt-Kandidaten - kein Auto, kein Teller.
            values["goldener_schnitt"] = compute_golden_ratio_score(
                faces, animal_detections(objects)
            )
        except Exception:
            pass

    # specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md, ADR 0026 Punkt 3:
    # EIGENSTAENDIGER, zusaetzlicher Modellaufruf neben dem obigen face_detector - kein Ersatz,
    # content_people/goldener_schnitt bleiben unveraendert auf dem bestehenden face_detector.
    if face_landmarker is not None:
        try:
            values["freiraum"] = compute_freiraum_score(
                detect_face_orientation(image, face_landmarker)
            )
        except Exception:
            pass

    return values


# specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, decisions/0050-verketteter-
# klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md Punkt 4: defensive Obergrenze fuer die
# zusammengesetzte laufweite Cloud-Fehlermeldung - analog
# _MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH. Die eigentliche Absicherung bleibt, dass jeder
# Baustein entweder fest codiert ist oder aus einer bereits an der Exception-Konstruktionsstelle
# sanitierten Meldung stammt (ADR 0025/0031/0032/0034); diese Kappung ist nur eine Storage-/
# Degenerationsgrenze fuer den Fall mehrerer langer Teilmeldungen.
_MAX_RUN_CLOUD_ERROR_MESSAGE_LENGTH = 1000


def _append_cloud_error(run: CriterionScoringRun, message: str) -> None:
    """Haengt einen Baustein an die laufweite Cloud-Fehlermeldung an, statt sie zu ueberschreiben
    (ADR 0050 Punkt 4): ein Lauf kann mehrere unabhaengige Cloud-Probleme haben (Phase 1
    fehlgeschlagen UND Landmark-Client nicht konstruierbar UND einzelne Landmark-Aufrufe
    fehlgeschlagen), und keines davon darf ein anderes verdecken. Kein eigener Commit - der
    Aufrufer committet ohnehin an seinen bestehenden Punkten."""
    existing = run.cloud_error_message
    combined = message if existing is None else f"{existing} {message}"
    run.cloud_error_message = combined[:_MAX_RUN_CLOUD_ERROR_MESSAGE_LENGTH]


async def run_criterion_scoring(
    session: AsyncSession,
    project: Project,
    scoring_run_id: int,
    cache_dir: Path,
    build_detector: Callable[[], FaceDetectorLike] = build_face_detector,
    build_animal_detector: Callable[[], ObjectDetectorLike] = build_object_detector,
    build_classifier: Callable[[], SceneClassifierLike] = build_scene_classifier,
    build_aesthetics: Callable[[], AestheticsModelLike] = build_aesthetics_model,
    build_landmarker: Callable[[], FaceLandmarkerLike] = build_face_landmarker,
    build_landmark_client: Callable[[], LandmarkClientLike] = build_landmark_client,
    *,
    run: CriterionScoringRun | None = None,
    use_cloud: bool = False,
) -> CriterionScoringRun:
    """Berechnet Kriterien-Werte fuer alle Ausschuss-Ueberlebenden eines Projekts und die daraus
    abgeleitete Rangfolge je Partition (cluster_key x category_key) - ersetzt run_top_selection/
    select_top_photos vollstaendig (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
    backfill.md). Ablauf (Architektur-Abschnitt der Spec): CriterionScoringRun anlegen -> Guard
    (scoring_run_id muss der aktuell neueste erfolgreiche ScoringRun sein) -> Kriterien je Foto
    berechnen (sharpness/exposure immer, Inhalts-Kriterien best-effort, periodisch zwischen-
    committet) -> rank_photos je Partition anwenden (reine In-Memory-Aggregation ueber die in
    diesem Lauf berechneten Werte) -> PhotoRanking-Zeilen schreiben -> CriterionScoringRun auf
    success/failed setzen. `build_detector`/`build_animal_detector`/`build_classifier`/
    `build_aesthetics`/`build_landmarker` sind injizierbar (Default: die echte, teure
    Modellkonstruktion) - Tests uebergeben stattdessen Fakes ohne echtes Modell
    (specs/features/0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md:
    build_object_detector/build_scene_classifier/build_aesthetics_model duerfen wie
    build_face_detector NIE in einem automatisierten Test aufgerufen werden - gilt seit
    specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md ebenso fuer
    build_face_landmarker).

    specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, ADR 0050: seit Spec 0296
    ist dies die ZWEITE Phase eines verketteten Klassifizierungslaufs, nicht mehr ein eigenstaendig
    ausgeloester Lauf. Zwei neue keyword-only Parameter:

    - `run`: der bereits von run_classification angelegte Lauf-Datensatz. Wird keiner uebergeben,
      legt diese Funktion ihn wie bisher selbst an (Direktaufruf, z.B. in Tests).
    - `use_cloud`: laufbezogene Cloud-Freigabe (die Checkbox am Ausloeser). Das Gate fuer die
      Landmark-Phase ist ab hier die KONJUNKTION `use_cloud and
      project.cloud_vision_detection_enabled` - `use_cloud` kann eine fehlende Einwilligung nie
      ersetzen, nur eine vorhandene fuer diesen einen Lauf ungenutzt lassen (ADR 0050 Punkt 2).
      Default `False` und damit FAIL-CLOSED: ein Aufrufer, der den Parameter vergisst, verliert
      die Cloud-Anreicherung, statt ungewollte Kosten und einen ungewollten Datenabfluss
      auszuloesen."""
    if run is None:
        run = CriterionScoringRun(
            project_id=project.id,
            scoring_run_id=scoring_run_id,
            status=ScanStatus.RUNNING,
            cloud_requested=use_cloud,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
    run.phase = ClassificationPhase.CRITERIA
    await session.commit()

    try:
        latest_scoring_run = (
            await session.execute(
                select(ScoringRun)
                .where(ScoringRun.project_id == project.id)
                .order_by(ScoringRun.started_at.desc())
                .limit(1)
            )
        ).scalars().first()
        if (
            latest_scoring_run is None
            or latest_scoring_run.status != ScanStatus.SUCCESS
            or latest_scoring_run.id != scoring_run_id
        ):
            raise CriterionScoringGuardError(
                "scoring_run_id entspricht nicht mehr dem aktuell neuesten erfolgreichen "
                "Scoring-Lauf (Re-Scan/Re-Scoring waehrend der Kuratierung)."
            )

        # Bekannter, akzeptierter Performance-Trade-off (ADR 0021 "Konsequenzen", architect-
        # Review-Fund Spec 0037): anders als der fruehere run_top_selection gibt es HIER bewusst
        # KEINEN Kandidatenpool-Vorfilter pro Cluster mehr (Spec 0024: min(cluster_size,
        # max(N*3,6))) - N ist beim Scoren nicht mehr bekannt (wird erst beim Lesen ueber
        # top_n_per_category angewendet), also werden ALLE Ausschuss-Ueberlebenden verarbeitet,
        # nicht nur die aussichtsreichsten. Fuer sehr grosse Projekte potenziell spuerbar, siehe
        # docs/architecture.md.
        rows = (
            await session.execute(
                select(Photo, PhotoScore)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.project_id == project.id, PhotoScore.suggested_status.is_(None))
            )
        ).all()

        run.photos_total = len(rows)
        run.photos_processed = 0
        await session.commit()

        existing_criterion_scores: dict[tuple[int, str], PhotoCriterionScore] = {}
        if rows:
            photo_ids = [photo.id for photo, _score in rows]
            existing_criterion_scores = {
                (row.photo_id, row.criterion_key): row
                for row in (
                    await session.execute(
                        select(PhotoCriterionScore).where(
                            PhotoCriterionScore.photo_id.in_(photo_ids)
                        )
                    )
                ).scalars()
            }

        # Copilot-Review-Fund (PR #88): die Modell-Builder selbst liefen bisher UNGESCHUETZT vor
        # der Foto-Schleife - ein Fehlschlag eines einzelnen Builders (fehlendes/defektes
        # .tflite-/.hdf5-Asset, mediapipe-/tensorflow-Laufzeitproblem) haette den GESAMTEN Lauf
        # als FAILED markiert, obwohl die Kriterien pro Foto bewusst best-effort behandelt werden
        # (Akzeptanzkriterium der Spec 0038). Jeder Builder bekommt deshalb sein eigenes
        # try/except: schlaegt einer fehl, bleibt der zugehoerige Detektor/Klassifikator/das
        # Modell None, _compute_content_criteria ueberspringt dann NUR die davon abhaengigen
        # Kriterien (siehe dortige `if ... is not None`-Wächter) - sharpness/exposure und alle
        # anderen, unabhaengig berechenbaren Kriterien werden trotzdem geschrieben.
        detector = _try_build(build_detector) if rows else None
        animal_detector = _try_build(build_animal_detector) if rows else None
        scene_classifier = _try_build(build_classifier) if rows else None
        aesthetics_model = _try_build(build_aesthetics) if rows else None
        face_landmarker = _try_build(build_landmarker) if rows else None
        now = _now_utc()

        def _upsert_criterion(
            photo_id: int, criterion_key: str, value: float, source: CriterionSource
        ) -> None:
            existing = existing_criterion_scores.get((photo_id, criterion_key))
            if existing is None:
                existing = PhotoCriterionScore(photo_id=photo_id, criterion_key=criterion_key)
                session.add(existing)
                existing_criterion_scores[(photo_id, criterion_key)] = existing
            existing.value = value
            existing.source = source
            existing.computed_at = now

        # photo_id -> {criterion_key: value}, nur die in DIESEM Lauf erfolgreich berechneten
        # Werte (reine In-Memory-Grundlage fuer rank_photos unten, kein erneutes DB-Read noetig).
        candidate_values: dict[int, dict[str, float]] = {}
        cluster_by_photo: dict[int, str] = {}
        processed = 0
        for photo, score in rows:
            values: dict[str, float] = {}

            sharpness_value = normalize_sharpness(score.sharpness)
            _upsert_criterion(
                photo.id, "sharpness", sharpness_value, CriterionSource.LOCAL_HEURISTIC
            )
            values["sharpness"] = sharpness_value

            exposure_value = normalize_exposure(score.exposure)
            _upsert_criterion(
                photo.id, "exposure", exposure_value, CriterionSource.LOCAL_HEURISTIC
            )
            values["exposure"] = exposure_value

            # Kein assert-is-not-None mehr hier (Copilot-Review-Fund, PR #88): jeder der fuenf
            # Builder oben ist ueber _try_build best-effort abgesichert und kann legitim None
            # sein - _compute_content_criteria ueberspringt die davon abhaengigen Kriterien dann
            # selbst, statt dass ein fehlgeschlagener Builder den gesamten Lauf abbricht.
            content_values = _compute_content_criteria(
                cache_dir,
                photo,
                detector,
                animal_detector,
                scene_classifier,
                aesthetics_model,
                face_landmarker,
            )
            for criterion_key, source in _IMAGE_ANALYSIS_CRITERION_SOURCES.items():
                if criterion_key in content_values:
                    _upsert_criterion(
                        photo.id, criterion_key, content_values[criterion_key], source
                    )
                    values[criterion_key] = content_values[criterion_key]

            candidate_values[photo.id] = values
            cluster_by_photo[photo.id] = score.cluster_key or ""

            processed += 1
            if processed % CRITERION_SCORING_COMMIT_BATCH_SIZE == 0:
                run.photos_processed = processed
                # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-
                # watchdog.md, ADR 0019, Schicht 2) - analog run_project_scan oben.
                run.last_progress_at = _now_utc()
                await session.commit()

        run.photos_processed = processed
        await session.commit()

        # specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR
        # decisions/0025-cloud-landmark-erkennung.md ab hier: erste tatsaechlich produktive
        # Cloud-Phase im Kriterien-Scoring-Pfad, laeuft NACH der obigen (rein lokalen/synchronen)
        # Foto-Schleife, VOR der Kategorieableitung/rank_photos (Punkt 3), damit landmark-Werte
        # noch in die Kategorie-/Rangfolgenbildung einfliessen koennen. `project.
        # cloud_vision_detection_enabled` wird hier EINMALIG gelesen (kein Live-Reread waehrend
        # des Laufs, dokumentierte Vereinfachung) - ist der Schalter aus (Default), wird
        # build_landmark_client GAR NICHT ERST aufgerufen: keine Netzwerkverbindung, kein API-Key
        # noetig, kein Byte verlaesst den Server (Security-Muss-Kriterium der Spec).
        # specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, ADR 0050 Punkt 2:
        # `use_cloud` ist ab hier die zweite, laufbezogene Haelfte des Gates - bei abgewaehlter
        # Cloud-Checkbox wird build_landmark_client GAR NICHT ERST aufgerufen, selbst wenn die
        # projektweite Einwilligung vorliegt (Security-Muss-Kriterium der Spec: "kein einziger
        # Cloud-Aufruf im gesamten Durchlauf").
        if use_cloud and project.cloud_vision_detection_enabled and rows:
            landmark_client = _try_build(build_landmark_client)
            if landmark_client is None:
                # ADR 0050 Punkt 4: dieser Fall war bisher vollstaendig stumm - ein nicht
                # konstruierbarer Client liess die Sehenswuerdigkeits-Erkennung wortlos aus.
                # Jetzt Teil der laufweiten Cloud-Fehlermeldung.
                _append_cloud_error(
                    run, "Sehenswuerdigkeits-Erkennung nicht verfuegbar (Initialisierung "
                    "fehlgeschlagen)."
                )
            if landmark_client is not None:
                landmark_failures = 0
                landmark_attempts = 0
                # specs/features/0207-projekt-statistikseite.md, ADR 0051 Punkt 1: Ist-Kosten-
                # Buchfuehrung dieser Phase. Summiert wird ueber die ERFOLGREICHEN Ergebnisse -
                # ein fehlgeschlagener Aufruf liefert keinen auswertbaren Verbrauch (ADR 0051
                # Punkt 6, dokumentierte Untererfassung).
                landmark_api_calls = 0
                landmark_input_tokens = 0
                landmark_output_tokens = 0
                try:
                    already_scored_photo_ids = {
                        photo_id
                        for photo_id, criterion_key in existing_criterion_scores
                        if criterion_key == "landmark"
                    }
                    landmark_candidate_ids = _select_landmark_candidates(
                        candidate_values, already_scored_photo_ids
                    )
                    photos_by_id = {photo.id: photo for photo, _score in rows}
                    landmark_concurrency = settings.landmark_api_concurrency
                    landmark_attempts = len(landmark_candidate_ids)
                    for start in range(0, len(landmark_candidate_ids), landmark_concurrency):
                        block_ids = landmark_candidate_ids[start : start + landmark_concurrency]
                        results = await asyncio.gather(
                            *[
                                _detect_landmark_for_photo(
                                    landmark_client, cache_dir, photos_by_id[photo_id]
                                )
                                for photo_id in block_ids
                            ],
                            return_exceptions=True,
                        )
                        # Derselbe verifizierte Async-Fallstrick wie in _process_scan_block (ADR
                        # 0020, hier zum zweiten Mal zu beachten, ADR 0025 Punkt 3): ein
                        # CancelledError einer einzelnen Kind-Coroutine wird von
                        # return_exceptions=True sonst als gewoehnliches Ergebniselement
                        # durchgereicht statt propagiert.
                        for result in results:
                            if isinstance(result, asyncio.CancelledError):
                                raise result
                        for photo_id, result in zip(block_ids, results, strict=True):
                            if isinstance(result, BaseException):
                                # Best-effort (ADR 0025 Punkt 3): ein einzelner fehlgeschlagener
                                # Cloud-Aufruf (Timeout, 4xx/5xx, fehlender Cache-Eintrag) laesst
                                # fuer dieses Foto keine landmark-Zeile entstehen, alle anderen
                                # Kriterien dieses Fotos bleiben unberuehrt, kein Laufabbruch.
                                # Spec 0056/ADR 0034: dennoch sichtbar ueber docker compose logs.
                                # ADR 0035 Punkt 3/Copilot-Review-Fund PR #255: type(exc).__name__/
                                # str(exc) GENAU EINMAL berechnet, an beide Senken (Logger, DB)
                                # weitergereicht - keine zweite Auswertung.
                                landmark_failures += 1
                                exc_type_name = type(result).__name__
                                exc_message = str(result)
                                _log_cloud_vision_failure(
                                    "landmark",
                                    photo_id,
                                    photos_by_id[photo_id].relative_path,
                                    exc_type_name,
                                    exc_message,
                                )
                                # specs/features/0058-cloud-vision-status-transparenz.md, ADR
                                # 0035 Punkt 3: dauerhafte, per API abrufbare Persistenz desselben
                                # Fehlschlags (getrennt vom Log oben).
                                await _record_cloud_vision_error(
                                    session,
                                    photo_id,
                                    CloudVisionPhase.LANDMARK,
                                    exc_type_name,
                                    exc_message,
                                    now,
                                )
                                continue
                            detection = result
                            # Verbindlich (Spec 0207): jeder STATTGEFUNDENE Aufruf wird gezaehlt,
                            # auch wenn sein `usage`-Block fehlte - der Tokenbeitrag ist dann 0.
                            # Sonst entstuende die stille Kombination "api_calls == 0 bei real
                            # erfolgten Aufrufen", und `api_calls > 0` ist zugleich der Ausloeser
                            # fuer Befund (b) des Unvollstaendigkeits-Hinweises (ADR 0051 Punkt 5).
                            landmark_api_calls += 1
                            if detection.usage is not None:
                                landmark_input_tokens += detection.usage.input_tokens
                                landmark_output_tokens += detection.usage.output_tokens
                            landmark_value = compute_landmark_score(detection)
                            _upsert_criterion(
                                photo_id, "landmark", landmark_value, CriterionSource.CLOUD
                            )
                            candidate_values[photo_id]["landmark"] = landmark_value
                            # ADR 0035 Punkt 2 "Aufraeumen bei Erfolg": ein erfolgreicher
                            # (Retry-)Versuch loescht eine ggf. vorhandene Fehler-Zeile.
                            await _clear_cloud_vision_error(
                                session, photo_id, CloudVisionPhase.LANDMARK
                            )
                            if detection.name is not None:
                                await _upsert_landmark_detection(
                                    session, photo_id, detection, now, settings.landmark_provider
                                )
                finally:
                    aclose = getattr(landmark_client, "aclose", None)
                    if aclose is not None:
                        await aclose()
                    # VERBINDLICH im finally, nicht erst vor `status = SUCCESS` (Spec 0207/ADR
                    # 0051 Punkt 4): ein Lauf, der nach der Cloud-Phase in der Kriterien-Phase
                    # scheitert, hat das Geld bereits ausgegeben. Ohne das Schreiben hier verloere
                    # er den real angefallenen Betrag - und waere wegen `0` statt `NULL` nicht
                    # einmal als Luecke erkennbar. Das Commit ist ebenfalls noetig: der
                    # Fehlerpfad laeuft ueber _fail_run, das mit einem rollback() beginnt.
                    run.landmark_api_calls = landmark_api_calls
                    run.landmark_input_tokens = landmark_input_tokens
                    run.landmark_output_tokens = landmark_output_tokens
                    # Der Betrag wird EINMAL am Phasenende berechnet und eingefroren (ADR 0051
                    # Punkt 4) - eine spaetere Preisaenderung schreibt die Vergangenheit nicht um.
                    run.landmark_cost_usd = compute_cost_usd(
                        vision_model_for_provider(settings.landmark_provider),
                        TokenUsage(
                            input_tokens=landmark_input_tokens,
                            output_tokens=landmark_output_tokens,
                        ),
                    )
                    await session.commit()
                # ADR 0050 Punkt 4: Zaehl-Zusammenfassung statt N Einzelmeldungen - die
                # Einzelfehler bleiben pro Foto ueber photo_cloud_vision_errors abrufbar
                # (ADR 0035), das hier ist die Laufebene.
                if landmark_failures > 0:
                    _append_cloud_error(
                        run,
                        f"Sehenswuerdigkeits-Erkennung: {landmark_failures} von "
                        f"{landmark_attempts} Fotos fehlgeschlagen.",
                    )

        # specs/features/0289-feste-kategorien.md, Umsetzungsschritt 5: laedt die bereits
        # vorhandenen Klassifikations-Zeilen (seit Spec 0296 im Regelfall aus Phase 1 DESSELBEN
        # Laufs, siehe run_classification - KEIN neuer Cloud-Aufruf hier). Sie liefern die
        # REMOTE-Haelfte der Kandidatenmenge; die lokale Haelfte steckt in candidate_values.
        remote_candidates = await _remote_category_candidates(session, candidate_values.keys())

        scores_by_photo_id = {photo.id: score for photo, score in rows}

        partitions: dict[tuple[str, str], dict[int, dict[str, float]]] = {}
        for photo_id, values in candidate_values.items():
            # Die Kategorie ist seit ADR 0049 eine reine PRO-FOTO-Funktion ueber einem
            # geschlossenen Set - keine laufweite Haeufigkeitsaggregation mehr (das abgeloeste
            # derive_active_categories/derive_category_key-Paar aus ADR 0023). Die Zuordnung ist
            # damit unabhaengig davon, welche anderen Fotos im Projekt liegen.
            #
            # specs/features/0055, ADR 0032 Punkt 2 Migration b: ein manueller Override ueberlebt
            # damit automatisch jeden kuenftigen vollen Re-Scoring-Lauf, ohne Sonderfallcode.
            category_key = scores_by_photo_id[photo_id].category_override or derive_photo_category(
                values, remote_candidates.get(photo_id, [])
            )
            partition_key = (cluster_by_photo[photo_id], category_key)
            partitions.setdefault(partition_key, {})[photo_id] = values

        for (cluster_key, category_key), partition_candidates in partitions.items():
            for ranked_photo in rank_photos(partition_candidates, DEFAULT_CRITERION_WEIGHTS):
                session.add(
                    PhotoRanking(
                        criterion_scoring_run_id=run.id,
                        photo_id=ranked_photo.photo_id,
                        cluster_key=cluster_key,
                        category_key=category_key,
                        rank_score=ranked_photo.rank_score,
                        rank_position=ranked_photo.rank_position,
                    )
                )

        run.status = ScanStatus.SUCCESS
        run.phase = None
        run.finished_at = _now_utc()
        await session.commit()
        return run
    except asyncio.CancelledError:
        # Schicht 1 des Fortschritts-Watchdogs (specs/features/0034-scan-haenger-fortschritts-
        # watchdog.md, ADR 0019) - analog run_project_scan/run_project_scoring oben.
        await _fail_run(session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown).")
        raise
    except Exception as exc:
        # Kein Rollback bereits committeter Fortschritts-/Kriterien-Zwischenstaende
        # (Akzeptanzkriterium der Spec, identisches Muster wie run_project_scoring oben).
        await _fail_run(session, run, str(exc))
        return run


async def run_classification(
    session: AsyncSession,
    project: Project,
    scoring_run_id: int,
    cache_dir: Path,
    *,
    use_cloud: bool,
    build_detector: Callable[[], FaceDetectorLike] = build_face_detector,
    build_animal_detector: Callable[[], ObjectDetectorLike] = build_object_detector,
    build_classifier: Callable[[], SceneClassifierLike] = build_scene_classifier,
    build_aesthetics: Callable[[], AestheticsModelLike] = build_aesthetics_model,
    build_landmarker: Callable[[], FaceLandmarkerLike] = build_face_landmarker,
    build_landmark_client: Callable[[], LandmarkClientLike] = build_landmark_client,
    build_category_client: Callable[
        [], CategoryDetectionClientLike
    ] = build_category_classification_client,
    build_embedder: Callable[[], LabelEmbedderLike] = build_label_embedder,
) -> CriterionScoringRun:
    """Der EINE Klassifizierungslauf (specs/features/0296-klassifizierung-ein-ausloeser-cloud-
    checkbox.md, decisions/0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-
    freigabe.md Punkt 1) - loest die beiden bisher getrennt ausgeloesten Laeufe ab:

        Phase "remote_categories" (nur bei aktiver Cloud-Nutzung)
            -> run_remote_category_classification
        Phase "criteria" (immer)
            -> run_criterion_scoring (inkl. Landmark-Teilphase, ebenfalls nur bei aktiver
               Cloud-Nutzung)

    Die Reihenfolge ist der eigentliche Zweck dieser Funktion: `run_criterion_scoring` liest die
    Remote-Ergebnisse ueber `_remote_category_candidates` aus der Datenbank und kann sie nur dann
    in die Kategorieableitung einrechnen, wenn sie bereits geschrieben sind. Bisher war das eine
    Bedienanweisung ("erst remote, dann bewerten"), die man kennen musste - jetzt ist es eine
    Codezeile.

    "Aktive Cloud-Nutzung" ist die Konjunktion `use_cloud and
    project.cloud_vision_detection_enabled` (ADR 0050 Punkt 2): die laufbezogene Checkbox kann eine
    fehlende projektweite Einwilligung nie ersetzen, nur eine vorhandene fuer diesen einen Lauf
    ungenutzt lassen. Ist sie falsch, wird run_remote_category_classification GAR NICHT ERST
    aufgerufen - es entsteht dann auch kein RemoteCategoryClassificationRun.

    Der Lauf-Datensatz (`CriterionScoringRun`) wird HIER angelegt, vor der ersten Phase, und an
    run_criterion_scoring durchgereicht (ADR 0050 Punkt 3): sonst zeigte
    `last_criterion_scoring_run` waehrend der Remote-Phase noch auf den Lauf davor und die
    Oberflaeche haette keinen Anker fuer den laufenden Vorgang.

    Ein Fehlschlag der Cloud-Phase bricht den Lauf NICHT ab (ADR 0050 Punkt 4): der lokale
    Bewertungsanteil ist der Kern des Laufs und laeuft vollstaendig durch, die Fehlermeldung
    wandert in `cloud_error_message`."""
    cloud_active = use_cloud and project.cloud_vision_detection_enabled

    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run_id,
        status=ScanStatus.RUNNING,
        cloud_requested=use_cloud,
        phase=(
            ClassificationPhase.REMOTE_CATEGORIES if cloud_active else ClassificationPhase.CRITERIA
        ),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    if cloud_active:
        try:
            remote_run = await run_remote_category_classification(
                session,
                project,
                cache_dir,
                build_client=build_category_client,
                build_embedder=build_embedder,
            )
        except asyncio.CancelledError:
            # Schicht 1 des Fortschritts-Watchdogs (specs/features/0034-scan-haenger-fortschritts-
            # watchdog.md, ADR 0019): run_remote_category_classification faellt seine EIGENE Zeile
            # bereits ab und wirft weiter - ohne diesen Zweig bliebe der uebergeordnete
            # CriterionScoringRun, den run_classification vor Phase 1 anlegt, bis zum naechsten
            # Cron-Tick auf RUNNING stehen. Vor Spec 0296 gab es zu diesem Zeitpunkt noch gar
            # keine solche Zeile, deshalb ist das ein mit der Verkettung neu entstandener Fall.
            await _fail_run(
                session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown)."
            )
            raise
        if remote_run.status == ScanStatus.FAILED:
            # _fail_run hat die Session zurueckgerollt und damit JEDES Objekt darin expired -
            # anders als ein commit() (die Session laeuft mit expire_on_commit=False, siehe
            # db.py). Ohne diese beiden refresh()-Aufrufe loeste der naechste Attributzugriff
            # einen impliziten Lazy-Load ausserhalb eines aktiven greenlet-Kontexts aus
            # (MissingGreenlet, derselbe Mechanismus wie im Copilot-Review-Fund PR #67):
            # `run.cloud_error_message` unmittelbar hier, `project.cloud_vision_detection_enabled`/
            # `project.id` gleich darauf in run_criterion_scoring. Bis Spec 0296 fiel das nicht
            # auf, weil der fehlgeschlagene Remote-Lauf das Ende des Jobs war - jetzt laeuft die
            # Kriterien-Phase auf derselben Session weiter.
            await session.refresh(run)
            await session.refresh(project)
            _append_cloud_error(
                run, f"Remote-Kategorisierung fehlgeschlagen: {remote_run.error_message}"
            )
            await session.commit()

    return await run_criterion_scoring(
        session,
        project,
        scoring_run_id,
        cache_dir,
        build_detector,
        build_animal_detector,
        build_classifier,
        build_aesthetics,
        build_landmarker,
        build_landmark_client,
        run=run,
        use_cloud=use_cloud,
    )


async def classify(
    ctx: dict[str, Any], project_id: int, scoring_run_id: int, use_cloud: bool
) -> int:
    """Der einzige Klassifizierungs-Job (specs/features/0296-klassifizierung-ein-ausloeser-cloud-
    checkbox.md) - ersetzt die frueheren, getrennt ausgeloesten Jobs `score_criteria` und
    `classify_categories_remote` vollstaendig."""
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        run = await run_classification(
            session,
            project,
            scoring_run_id,
            cache_dir=Path(settings.photo_cache_dir),
            use_cloud=use_cloud,
        )
        return run.id


async def _classify_photo_for_remote_category(
    client: CategoryDetectionClientLike, cache_dir: Path, photo: Photo
) -> RemoteClassification:
    """Der reine I/O-/Netzwerk-Teil eines einzelnen Remote-Kategorie-Kandidaten (analog
    _detect_landmark_for_photo) - bewusst OHNE Session-Zugriff, damit mehrere Aufrufe sicher
    parallel per asyncio.gather laufen koennen. Nutzt ausschliesslich die bereits vorhandene,
    auf 2048 px begrenzte display-Cache-Variante (ADR 0032 Punkt 5) - nie das OpenCloud-Original,
    kein EXIF/GPS, kein Dateiname und kein Pfad im Request (Security-Muss-Kriterium, unveraendert
    seit Spec 0055)."""
    path = variant_path(cache_dir, photo.id, photo.etag, "display")
    image_bytes = path.read_bytes()
    return await client.classify(image_bytes, _CLOUD_VISION_IMAGE_MIME_TYPE, photo.id)


async def select_remote_category_candidates(session: AsyncSession, project_id: int) -> list[Photo]:
    """Kandidatenmenge fuer die Remote-Kategorie-Klassifizierung (specs/features/0055-remote-
    kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt 5): der KOMPLETTE Ausschuss-
    Ueberlebender-Bestand (PhotoScore.suggested_status IS NULL) OHNE Vorfilter (anders als
    landmark, ADR 0021), abzueglich bereits klassifizierter Fotos (vorhandene
    `photo_category_classifications`-Zeile - seit specs/features/0289-feste-kategorien.md ist die
    1:1-Klassifikations-Zeile das Skip-Kriterium, nicht mehr eine Feinlabel-Zeile: ein Foto mit
    Kategorie, aber ohne Feinlabel, gilt als erledigt). Von `run_remote_category_classification` UND
    `GET .../classify/estimate` (api/projects.py) genutzt - "ermittelt ueber
    dieselbe Kandidaten-Selektion wie der tatsaechliche Lauf" (Akzeptanzkriterium der Spec)."""
    rows = (
        await session.execute(
            select(Photo)
            .join(PhotoScore, PhotoScore.photo_id == Photo.id)
            .where(Photo.project_id == project_id, PhotoScore.suggested_status.is_(None))
        )
    ).scalars().all()

    if not rows:
        return []

    already_classified_ids = set(
        (
            await session.execute(
                select(PhotoCategoryClassification.photo_id).where(
                    PhotoCategoryClassification.photo_id.in_([photo.id for photo in rows])
                )
            )
        ).scalars()
    )
    return [photo for photo in rows if photo.id not in already_classified_ids]


async def run_remote_category_classification(
    session: AsyncSession,
    project: Project,
    cache_dir: Path,
    build_client: Callable[[], CategoryDetectionClientLike] = build_category_classification_client,
    build_embedder: Callable[[], LabelEmbedderLike] = build_label_embedder,
) -> RemoteCategoryClassificationRun:
    """Eigenstaendiger, expliziter Job (specs/features/0055-remote-kategorie-klassifizierung-mit-
    kostenschaetzung.md, ADR 0032 Punkt 5) - KEIN Teil von run_criterion_scoring, eigene Run-
    Tabelle, eigenes Concurrency-Setting. Best-effort ohne Retry: ein einzelner Fehlschlag bricht
    den Lauf nicht ab, das Foto bleibt beim naechsten Lauf erneut Kandidat.
    `project.cloud_vision_detection_enabled` wird hier EINMALIG gelesen (kein Live-Reread,
    dokumentierte Vereinfachung analog run_criterion_scoring) - ist der Schalter aus (Default)
    ODER der Kandidatenpool leer, wird `build_client` GAR NICHT ERST aufgerufen (Security-Muss-
    Kriterium, geteiltes Consent-Gate mit `landmark`)."""
    run = RemoteCategoryClassificationRun(project_id=project.id, status=ScanStatus.RUNNING)
    session.add(run)
    await session.commit()
    await session.refresh(run)

    try:
        candidates = await select_remote_category_candidates(session, project.id)

        run.photos_total = len(candidates)
        run.photos_processed = 0
        await session.commit()

        if not project.cloud_vision_detection_enabled or not candidates:
            run.status = ScanStatus.SUCCESS
            run.finished_at = _now_utc()
            await session.commit()
            return run

        client = _try_build(build_client)
        embedder = _try_build(build_embedder)
        if client is None or embedder is None:
            # Best-effort auf Job-Ebene (analog _try_build-Philosophie der uebrigen Modell-
            # Builder): ein Ladefehler eines der beiden noetigen Bausteine laesst den Lauf
            # erfolgreich, aber wirkungslos enden - kein Crash, kein FAILED-Zustand fuer ein
            # Infrastrukturproblem, das der naechste Lauf ggf. von selbst behebt.
            run.status = ScanStatus.SUCCESS
            run.finished_at = _now_utc()
            await session.commit()
            return run

        try:
            snapshot_rows = (await session.execute(select(FineLabel))).scalars().all()
            snapshot = [
                FineLabelSnapshotEntry(
                    canonical_key=row.canonical_key,
                    display_name=row.display_name,
                    embedding=list(row.embedding),
                    id=row.id,
                )
                for row in snapshot_rows
            ]

            now = _now_utc()
            concurrency = settings.remote_category_classification_concurrency
            processed = 0
            # specs/features/0207-projekt-statistikseite.md, ADR 0051 Punkt 1: Ist-Kosten-
            # Buchfuehrung dieses Laufs, identisch zur Landmark-Phase in run_criterion_scoring -
            # summiert ueber die ERFOLGREICHEN Ergebnisse, geschrieben im `finally` unten.
            api_calls = 0
            input_tokens = 0
            output_tokens = 0
            for start in range(0, len(candidates), concurrency):
                block = candidates[start : start + concurrency]
                results = await asyncio.gather(
                    *[
                        _classify_photo_for_remote_category(client, cache_dir, photo)
                        for photo in block
                    ],
                    return_exceptions=True,
                )
                # Verifizierter Async-Fallstrick (ADR 0020/0025) - siehe run_criterion_scoring.
                for result in results:
                    if isinstance(result, asyncio.CancelledError):
                        raise result

                for photo, result in zip(block, results, strict=True):
                    if isinstance(result, BaseException):
                        # Best-effort (ADR 0032 Punkt 5): ein einzelner fehlgeschlagener Cloud-
                        # Aufruf laesst fuer dieses Foto keine Zeile entstehen, das Foto bleibt
                        # beim naechsten Lauf erneut Kandidat.
                        # Spec 0056/ADR 0034: dennoch sichtbar ueber docker compose logs.
                        # ADR 0035 Punkt 3/Copilot-Review-Fund PR #255: type(exc).__name__/
                        # str(exc) GENAU EINMAL berechnet, an beide Senken (Logger, DB)
                        # weitergereicht - keine zweite Auswertung.
                        exc_type_name = type(result).__name__
                        exc_message = str(result)
                        _log_cloud_vision_failure(
                            "remote_category",
                            photo.id,
                            photo.relative_path,
                            exc_type_name,
                            exc_message,
                        )
                        # specs/features/0058-cloud-vision-status-transparenz.md, ADR 0035
                        # Punkt 3: dauerhafte, per API abrufbare Persistenz desselben Fehlschlags
                        # (getrennt vom Log oben).
                        await _record_cloud_vision_error(
                            session,
                            photo.id,
                            CloudVisionPhase.REMOTE_CATEGORY,
                            exc_type_name,
                            exc_message,
                            now,
                        )
                        continue
                    classification = result
                    # Verbindlich (Spec 0207): jeder stattgefundene Aufruf zaehlt, auch ohne
                    # `usage`-Block (Tokenbeitrag dann 0) - `api_calls > 0` bei Betrag 0/NULL ist
                    # der Ausloeser fuer Befund (b) des Unvollstaendigkeits-Hinweises.
                    api_calls += 1
                    if classification.usage is not None:
                        input_tokens += classification.usage.input_tokens
                        output_tokens += classification.usage.output_tokens

                    # specs/features/0289-feste-kategorien.md, Umsetzungsschritt 5: pro Foto genau
                    # EINE Klassifikations-Zeile. `category_key` ist bereits ueber die feste
                    # Vorrangreihenfolge aufgeloest, `detected_categories` haelt die VALIDIERTE
                    # Kandidatenliste - nie die Rohliste des Modells (Security-Muss-Kriterium:
                    # sonst wanderte unvalidierter Fremdtext ueber einen zweiten Kanal in
                    # API-Antwort und UI).
                    session.add(
                        PhotoCategoryClassification(
                            photo_id=photo.id,
                            category_key=resolve_category(classification.categories),
                            detected_categories=list(classification.categories),
                            provider=settings.landmark_provider,
                            computed_at=now,
                        )
                    )

                    # Feinlabels sind reine Zusatzinformation und werden AUCH DANN geschrieben,
                    # wenn die Kategorie `nicht_erkannt` lautet (Akzeptanzkriterium). Loesen beide
                    # Labels auf denselben canonical_key auf, entsteht nur eine Zeile - kein
                    # IntegrityError durch UniqueConstraint(photo_id, fine_label_id). Ein
                    # Konfidenz-Vergleich ist dafuer nicht mehr noetig (Konfidenzen sind mit
                    # ADR 0049 Entwurfsentscheidung 7 ersatzlos entfallen), es gewinnt die
                    # Erstnennung.
                    entries_by_canonical: dict[str, tuple[FineLabelSnapshotEntry, str]] = {}
                    for raw_label in classification.fine_labels:
                        entry = resolve_canonical_label(raw_label, snapshot, embedder)
                        entries_by_canonical.setdefault(entry.canonical_key, (entry, raw_label))

                    for entry, raw_label in entries_by_canonical.values():
                        if entry.id is None:
                            label_row = FineLabel(
                                canonical_key=entry.canonical_key,
                                display_name=entry.display_name,
                                embedding=entry.embedding,
                            )
                            session.add(label_row)
                            await session.flush()
                            entry.id = label_row.id
                        session.add(
                            PhotoFineLabel(
                                photo_id=photo.id,
                                fine_label_id=entry.id,
                                raw_label=raw_label,
                                provider=settings.landmark_provider,
                                computed_at=now,
                            )
                        )
                    # ADR 0035 Punkt 2 "Aufraeumen bei Erfolg": ein erfolgreicher (Retry-)Versuch
                    # loescht eine ggf. vorhandene Fehler-Zeile - einmal pro Foto, nicht pro Label.
                    await _clear_cloud_vision_error(
                        session, photo.id, CloudVisionPhase.REMOTE_CATEGORY
                    )

                processed += len(block)
                run.photos_processed = processed
                run.last_progress_at = _now_utc()
                await session.commit()
        finally:
            aclose = getattr(client, "aclose", None)
            if aclose is not None:
                await aclose()
            # Wie in der Landmark-Phase VERBINDLICH im finally und mit eigenem Commit (Spec 0207/
            # ADR 0051 Punkt 4): ein nach begonnener Cloud-Nutzung scheiternder Lauf hat das Geld
            # bereits ausgegeben, und der Fehlerpfad laeuft ueber _fail_run, das mit einem
            # rollback() beginnt. Der Betrag wird einmal berechnet und eingefroren.
            run.api_calls = api_calls
            run.input_tokens = input_tokens
            run.output_tokens = output_tokens
            run.cost_usd = compute_cost_usd(
                vision_model_for_provider(settings.landmark_provider),
                TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            )
            await session.commit()

        run.status = ScanStatus.SUCCESS
        run.finished_at = _now_utc()
        await session.commit()
        return run
    except asyncio.CancelledError:
        await _fail_run(
            session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown)."
        )
        raise
    except Exception as exc:
        await _fail_run(session, run, str(exc))
        return run


async def reassign_photo_category(
    session: AsyncSession,
    criterion_scoring_run_id: int,
    photo_id: int,
    cluster_key: str,
    new_category_key: str,
) -> None:
    """Sofortige Wirkung eines manuellen Kategorie-Overrides (specs/features/0055, ADR 0032 Punkt
    7) - verschiebt EIN Foto synchron zwischen zwei `(cluster_key, category_key)`-Partitionen
    desselben Laufs und ruft `ranking.py::rank_photos` NUR fuer diese zwei Partitionen erneut auf
    (kein neuer Ranking-Algorithmus, kein voller Re-Scoring-Lauf). No-op (0 rank_photos-Aufrufe),
    wenn `new_category_key` bereits der aktuelle Wert ist. Nutzt ausschliesslich bereits
    persistierte `PhotoCriterionScore`-Werte fuer die Neusortierung - KEINE Neuberechnung, kein
    Cloud-Aufruf. Die KATEGORIE selbst wird hier nicht abgeleitet, sondern vom Aufrufer
    uebergeben (Override-Wert bzw. rekonstruierter Wert aus `derive_photo_category`)."""
    ranking = (
        await session.execute(
            select(PhotoRanking).where(
                PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
                PhotoRanking.photo_id == photo_id,
            )
        )
    ).scalar_one_or_none()
    if ranking is None or ranking.category_key == new_category_key:
        return

    ranking.category_key = new_category_key

    # Autoflush (SQLAlchemy-Default) sorgt dafuer, dass die obige Zuweisung bereits VOR dieser
    # SELECT-Ausfuehrung an die DB geschrieben wird - die folgende Abfrage liefert deshalb bereits
    # den Zielzustand (das verschobene Foto erscheint schon in seiner neuen Partition), ohne dass
    # hier manuell zwischen "alter"/"neuer" Partition unterschieden werden muesste.
    partition_rankings = (
        await session.execute(
            select(PhotoRanking).where(
                PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
                PhotoRanking.cluster_key == cluster_key,
                PhotoRanking.category_key.in_({ranking.category_key, new_category_key}),
            )
        )
    ).scalars().all()

    photo_ids = [row.photo_id for row in partition_rankings]
    criterion_rows = (
        await session.execute(
            select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id.in_(photo_ids))
        )
    ).scalars().all() if photo_ids else []

    values_by_photo_id: dict[int, dict[str, float]] = {}
    for row in criterion_rows:
        values_by_photo_id.setdefault(row.photo_id, {})[row.criterion_key] = row.value
    for photo_id_in_partition in photo_ids:
        values_by_photo_id.setdefault(photo_id_in_partition, {})

    rankings_by_photo_id = {ranking_row.photo_id: ranking_row for ranking_row in partition_rankings}
    for category_key in {ranking_row.category_key for ranking_row in partition_rankings}:
        partition_candidates = {
            pid: values_by_photo_id[pid]
            for pid, ranking_row in rankings_by_photo_id.items()
            if ranking_row.category_key == category_key
        }
        for ranked_photo in rank_photos(partition_candidates, DEFAULT_CRITERION_WEIGHTS):
            ranking_row = rankings_by_photo_id[ranked_photo.photo_id]
            ranking_row.rank_score = ranked_photo.rank_score
            ranking_row.rank_position = ranked_photo.rank_position

    await session.commit()


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
    session: AsyncSession,
    run: ScanRun | ScoringRun | CriterionScoringRun | RemoteCategoryClassificationRun,
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
    Testdatenbank gebundene Factory, analog zu run_criterion_scoring's build_detector-Parameter.
    Die vier Tabellen werden bewusst nacheinander in vier eigenstaendigen Bloecken behandelt
    statt ueber eine generische Schleife (konsistent mit dem Rest dieser Datei: ScanRun/
    ScoringRun/CriterionScoringRun/RemoteCategoryClassificationRun bleiben vier eigenstaendige
    Modelle ohne gemeinsame Basisklasse, ADR 0019). Vierter Block seit specs/features/0055-remote-
    kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt 2 Migration d."""
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
            # transaction is aborted" - die nachfolgenden SELECTs fuer ScoringRun/
            # CriterionScoringRun wuerden dann selbst fehlschlagen, obwohl inhaltlich nichts mit
            # ihnen falsch ist. Das
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
            stalled_criterion_scoring_runs = (
                await session.execute(
                    select(CriterionScoringRun).where(
                        CriterionScoringRun.status == ScanStatus.RUNNING,
                        CriterionScoringRun.last_progress_at < threshold,
                    )
                )
            ).scalars().all()
        except Exception:
            await session.rollback()
            stalled_criterion_scoring_runs = []
        for criterion_scoring_run in stalled_criterion_scoring_runs:
            if await _fail_if_stalled(session, criterion_scoring_run):
                reaped += 1

        try:
            stalled_remote_category_runs = (
                await session.execute(
                    select(RemoteCategoryClassificationRun).where(
                        RemoteCategoryClassificationRun.status == ScanStatus.RUNNING,
                        RemoteCategoryClassificationRun.last_progress_at < threshold,
                    )
                )
            ).scalars().all()
        except Exception:
            await session.rollback()
            stalled_remote_category_runs = []
        for remote_category_run in stalled_remote_category_runs:
            if await _fail_if_stalled(session, remote_category_run):
                reaped += 1

    return reaped


async def _configure_worker_logging(ctx: dict[Any, Any]) -> None:
    """arq-`on_startup`-Hook (specs/features/0056-structured-logging-cloud-vision-errors.md, ADR
    0034 Punkt 2, erste Nutzung von arqs on_startup-Mechanismus im Projekt) - duenner Wrapper statt
    direkter Zuweisung `on_startup = configure_logging`: arq ruft on_startup IMMER mit einem
    ctx-Positionalargument auf (verifiziert in arq.worker.Worker.main: `await self.on_startup(
    self.ctx)`), waehrend `configure_logging()` bewusst als Null-Argument-Funktion spezifiziert ist
    (Spec-Akzeptanzkriterium, identisch zum Aufruf in main.py::create_app()). Eine direkte
    Zuweisung wuerde erst beim tatsaechlichen Worker-Start mit einem TypeError durchbrechen."""
    configure_logging()


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
        # specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, ADR 0050 Punkt 1:
        # EIN verketteter Job (Remote-Kategorisierung -> Kriterien-Bewertung) statt der frueheren
        # zwei (score_criteria/classify_categories_remote) - die Reihenfolge, die man bis dahin
        # kennen musste, steckt jetzt in run_classification.
        arq_func(classify, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
    )
    # Schicht 2 des Fortschritts-Watchdogs (ADR 0019), erste Nutzung von arqs Cron-Mechanismus im
    # Projekt: run_at_startup=True sorgt dafuer, dass ein Worker-Neustart sofort eine erste
    # Pruefung ausloest, statt bis zu 5 Minuten auf den naechsten regulaeren Tick zu warten (genau
    # der Bug-Report-Fall: eine bereits vor dem Neustart haengende Zeile soll nicht unnoetig lang
    # unentdeckt bleiben).
    cron_jobs = (cron(reap_stalled_runs, minute=set(range(0, 60, 5)), run_at_startup=True),)
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    # specs/features/0056-structured-logging-cloud-vision-errors.md, ADR 0034 Punkt 2: einer der
    # beiden Prozess-Einstiegspunkte (Worker-Prozess) - derselbe Aufruf sitzt fuer den API-Prozess
    # in main.py::create_app().
    on_startup = _configure_worker_logging
