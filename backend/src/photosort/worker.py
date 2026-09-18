from __future__ import annotations

import asyncio
import enum
import logging
import os
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from arq.connections import RedisSettings
from arq.cron import cron
from arq.worker import func as arq_func
from PIL import Image
from sqlalchemy import delete, func, select, tuple_, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from photosort.aesthetics import AestheticsModelLike, build_aesthetics_model, compute_aesthetics
from photosort.album_suitability import AlbumSuitability
from photosort.cache_cleanup import cleanup_orphaned_cache
from photosort.cameras import CameraIdentity, shifted
from photosort.classification import (
    ANIMAL_CATEGORIES,
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
from photosort.clock import now_utc
from photosort.cloud_vision import ThrottleStats, TokenUsage
from photosort.cloud_vision_throttle import throttle_for_provider
from photosort.config import settings
from photosort.criteria import (
    CRITERIA_REGISTRY,
    FOOD_CATEGORIES,
    VEHICLE_CATEGORIES,
    allow_listed_area_fraction,
    animal_detections,
    bounding_box_area_fraction,
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
from photosort.duplicates import survives_ausschuss
from photosort.event_inputs import read_event_inputs
from photosort.events import assign_place_names, build_events
from photosort.geonames import build_place_resolver
from photosort.horizon import compute_horizon_tilt_score
from photosort.label_embedding import LabelEmbedderLike, build_label_embedder
from photosort.landmark import (
    LANDMARK_CONFIDENCE_THRESHOLD,
    LandmarkClientLike,
    LandmarkDetection,
    PlaceHint,
    build_landmark_client,
    place_hint_for,
)
from photosort.landmark_names import LandmarkNameEntry, resolve_canonical_landmark
from photosort.logging_config import configure_logging
from photosort.models import (
    ClassificationPhase,
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    Event,
    FineLabel,
    LandmarkName,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoFineLabel,
    PhotoLandmarkDetection,
    PhotoMotifAssessment,
    PhotoRanking,
    PhotoScore,
    PlaceLookup,
    Project,
    ProjectCamera,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
)
from photosort.motif_strengths import (
    load_effective_strengths,
    upsert_assessment,
)
from photosort.motifs import local_motif_strengths
from photosort.opencloud.client import IMAGE_EXTENSIONS, OpenCloudClient, OpenCloudError
from photosort.opencloud.exif import extract_camera, extract_gps, extract_taken_at
from photosort.opencloud.webdav_xml import DavEntry
from photosort.places import (
    PLACE_LEVELS,
    PlaceInfo,
    PlaceResolver,
    place_cell,
    sanitize_place_name,
    usable_locality,
)
from photosort.pricing import compute_cost_usd
from photosort.quality import compute_quality_score
from photosort.quality_weights import effective_weights, latest_weight_set
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
    ClusterCandidate,
    DuplicateCandidate,
    assign_clusters,
    assign_duplicate_clusters,
    compute_dhash,
    compute_exposure,
    compute_sharpness,
)
from photosort.selection import (
    SelectionCandidate,
    SelectionEvent,
    effective_target,
    select_album_draft,
)
from photosort.thumbnails import (
    aspect_ratio_of_cached_thumbnail,
    generate_variants,
    thumbnail_path,
    variant_path,
)

# Kein Logger-Objekt wird injiziert oder durchgereicht: worker.py ist die einzige Stelle mit
# Zugriff auf sowohl die Exception als auch den Foto-Kontext - landmark.py/
# remote_classification.py/cloud_vision.py bekommen deshalb keinen eigenen Logger.
logger = logging.getLogger(__name__)

_EXIF_CANDIDATE_EXTENSIONS = {".jpg", ".jpeg"}
_EXIF_RANGE_BYTES = 131_072

# FESTES Grund-Token fuer den einen Fall, in dem der Scan den Versatz eines Fotos nicht anwenden
# kann (das Ergebnis laege ausserhalb des darstellbaren Datumsbereichs) - Muster der
# Grund-Tokens in `opencloud/exif.py`. Kein Rohwert, kein Zeitstempel, kein Fremdtext.
_OFFSET_REASON_OUT_OF_RANGE = "ausserhalb_darstellbarem_bereich"

# Wie oft ScoringRun.photos_processed waehrend der Verarbeitung zwischen-committet wird ("mind. alle
# 25 Fotos", damit ein pollender Client echten, monoton wachsenden Fortschritt sieht statt nur
# Start-/Endzustand). Modul-Konstante statt Default-Parameterwert, damit Tests sie per
# monkeypatch.setattr(worker, "SCORE_COMMIT_BATCH_SIZE", ...) verkleinern koennen, ohne echte 25+
# Testfotos anlegen zu muessen.
SCORE_COMMIT_BATCH_SIZE = 25

# Analog SCORE_COMMIT_BATCH_SIZE, aber für ScanRun.files_found. Modul-Konstante statt
# Default-Parameterwert, damit Tests sie per monkeypatch.setattr(worker,
# "SCAN_COMMIT_BATCH_SIZE", ...) verkleinern können. Dieselbe Kadenz gilt ueber den gemeinsamen
# Helfer _maybe_commit_progress_checkpoint (unten), einmal aufgerufen aus Phase 1
# (_enumerate_scan_entries, je gelistetem Eintrag) und einmal aus der Skip-Schleife von Phase 2a
# in run_project_scan (je Skip-Entscheidung).
#
# 1, nicht 25 wie SCORE_COMMIT_BATCH_SIZE: run_project_scan ist netzwerkgebunden (EXIF-Range-Read
# und Thumbnail-Generierung pro Datei ueber OpenCloud-WebDAV), ein zusaetzlicher DB-Commit pro
# Datei faellt gegenueber der Netzwerklatenz nicht messbar ins Gewicht. Ein groesserer Wert friert
# den Live-Zaehler bei jedem Scan mit weniger Dateien als der Batch waehrend der gesamten Laufzeit
# auf 0 ein - und der dominante Realweltfall ist der Re-Scan mit ueberwiegend unveraenderten
# Dateien.
SCAN_COMMIT_BATCH_SIZE = 1

# Analog SCORE_COMMIT_BATCH_SIZE, fuer CriterionScoringRun.photos_processed. Kleiner als
# SCORE_COMMIT_BATCH_SIZE, da mediapipe-Inferenz (content_people-Kriterium) pro Foto eine spuerbare
# Laufzeit hat - ein grober Batch von 25 wuerde den Live-Fortschritt bei typischen
# Ausschuss-Überlebenden-Mengen faktisch einfrieren. Modul-Konstante statt Default-Parameterwert,
# damit Tests sie per monkeypatch.setattr(worker, "CRITERION_SCORING_COMMIT_BATCH_SIZE", ...)
# verkleinern koennen.
CRITERION_SCORING_COMMIT_BATCH_SIZE = 5

# Der Cloud-Aufruf nutzt ausschliesslich die bestehende display-Cache-Variante, die
# thumbnails.py::generate_variants immer als JPEG schreibt - fester Wert statt einer
# Format-Erkennung. Das Bildquellen-Muss-Kriterium gilt für BEIDE Cloud-Vision-Pfade.
_CLOUD_VISION_IMAGE_MIME_TYPE = "image/jpeg"


class OpenCloudScanClient(Protocol):
    """The subset of OpenCloudClient that scanning needs — kept narrow so tests can fake it."""

    async def resolve_drive(self, name: str | None) -> Any: ...

    def walk(self, webdav_url: str, root_path: str) -> Any: ...

    async def get_range(self, webdav_url: str, relative_path: str, length: int) -> bytes: ...

    async def download(self, webdav_url: str, relative_path: str) -> bytes: ...


def _extension(relative_path: str) -> str:
    return os.path.splitext(relative_path)[1].lower()


class SkipReason(enum.Enum):
    """Phase 2a: warum ein Eintrag NICHT zu einem Arbeitsposten für Phase 2b wird. Zwei
    getrennte Werte statt eines einzelnen bool-Flags, weil nur UNSUPPORTED_EXTENSION
    zusätzlich ScanRun.files_skipped hochzählt (siehe run_project_scan) - UNCHANGED_ETAG
    zählt nur in
    files_found (Fortschritt), nicht in files_skipped."""

    UNSUPPORTED_EXTENSION = "unsupported_extension"
    UNCHANGED_ETAG = "unchanged_etag"


@dataclass
class ScanWorkItem:
    """Ein Eintrag aus Phase 1, der in Phase 2b tatsaechlich verarbeitet werden muss (neue Datei,
    geaenderter Etag, oder die einmalige Kamera-Nachhol-Runde) - `existing_photo` ist `None` fuer
    neue Dateien, sonst die zu aktualisierende Zeile.

    `probe_only` heisst: die Datei ist UNVERAENDERT, gelesen wird nur ihr EXIF-Fenster, um die
    Kamera-Angabe nachzutragen. Die Thumbnails existieren bereits und waeren identisch - ihre
    Neuerzeugung waere ein Voll-Download je Bestandsfoto."""

    relative_path: str
    entry: DavEntry
    existing_photo: Photo | None
    probe_only: bool = False


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
    Checkpoint-Kadenz von files_found/files_skipped in Phase 2a) - `work_items` ist
    eine reine Teilmenge davon (nur die Eintraege mit skip_reason is None), fuer Phase 2b."""

    decisions: list[ScanEntryDecision] = field(default_factory=list)
    work_items: list[ScanWorkItem] = field(default_factory=list)
    seen_paths: set[str] = field(default_factory=set)


def _classify_scan_entries(
    entries: list[tuple[str, DavEntry]],
    existing_photos: dict[str, Photo],
) -> ScanClassification:
    """Phase 2a: reine Funktion, keine Session-/DB-Zugriffe - isoliert unit-testbar (siehe
    test_worker_scan_classification.py). Entscheidungslogik: unsupported extension -> Skip +
    files_skipped; unveraenderter Etag UND Kamera bereits geprueft -> Skip ohne files_skipped;
    unveraenderter Etag UND noch nicht geprueft -> Arbeitsposten mit `probe_only=True`; sonst ->
    voller Arbeitsposten. Die Verarbeitung selbst gehoert nicht hierher.

    Der `probe_only`-Zweig ist die EINMALIGE Nachhol-Runde fuer Bestandsfotos (ADR 0090,
    Konsequenzen): Ohne sie bliebe die Kameraliste in bereits gescannten Projekten leer, denn ein
    unveraendertes Foto wird nie wieder gelesen. Sie laeuft genau einmal je Foto - danach steht
    der Merker, AUCH wenn die Datei keine Kamera nennt."""
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
        unchanged = existing_photo is not None and existing_photo.etag == entry.etag
        if unchanged and existing_photo is not None and existing_photo.camera_probed:
            classification.decisions.append(
                ScanEntryDecision(relative_path, SkipReason.UNCHANGED_ETAG, None)
            )
            continue

        work_item = ScanWorkItem(relative_path, entry, existing_photo, probe_only=unchanged)
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
    return now_utc()


def _set_phase(run: CriterionScoringRun, phase: ClassificationPhase | None) -> None:
    """Die EINZIGE Stelle im Projekt, an der `phase` und `phase_started_at` gesetzt werden.

    Beide gemeinsam, nie einzeln (ADR 0116 Punkt 1): `phase = NULL` nimmt den Beginn mit, jeder
    andere Wert setzt ihn neu. Bliebe der alte Zeitstempel bei einem Wechsel stehen, rechnete die
    Restdauer den Beginn des VORIGEN Teilschritts gegen den Fortschritt des aktuellen - zu gross,
    ohne Fehler und ohne roten Verhaltenstest.

    Kein `commit()` hier: Der Phasenwechsel wird an jeder Aufrufstelle zusammen mit dem uebrigen
    Zustand dieses Schritts committet, und ein zweiter Commit mitten in `_fail_run` verschoebe
    dort die Reihenfolge aus Rollback, Zustand und Commit."""
    run.phase = phase
    run.phase_started_at = None if phase is None else _now_utc()


async def _fail_run(
    session: AsyncSession,
    run: ScanRun | ScoringRun | CriterionScoringRun | RemoteCategoryClassificationRun,
    error_message: str,
) -> None:
    """Gemeinsame "Lauf auf FAILED setzen"-Logik für die run_*-Funktionen. KEIN Kontrollfluss
    (kein raise/return) hier drin - der bleibt an jeder Call-Site sichtbar."""
    await session.rollback()
    run.status = ScanStatus.FAILED
    run.error_message = error_message
    run.finished_at = _now_utc()
    if isinstance(run, CriterionScoringRun):
        # `phase = NULL` heisst "laeuft nicht mehr" - das gilt fuer einen fehlgeschlagenen Lauf
        # genauso wie fuer einen erfolgreichen. HIER statt in run_classification/
        # run_criterion_scoring, weil _fail_run der einzige gemeinsame "auf FAILED setzen"-Pfad ist:
        # er wird auch vom Fortschritts-Watchdog (reap_stalled_runs -> _fail_if_stalled) benutzt,
        # der einen haengenden Lauf abraeumt, ohne dass die Job-Coroutine je zurueckkehrt. `phase`
        # existiert nur auf CriterionScoringRun, deshalb die isinstance-Pruefung statt eines
        # gemeinsamen Basisklassen-Feldes (die vier Run-Modelle haben bewusst keine).
        _set_phase(run, None)
    await session.commit()
    # das vorangehende rollback() expired ORM-Objekte der Session -
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
) -> float | None:
    """Best-effort: weder ein Download- noch ein
    Dekodierfehler duerfen den Scan des Projekts abbrechen (anders als die uebrigen
    OpenCloudError-Faelle unten, die den ganzen Scan als FAILED markieren) - ein fehlendes
    Thumbnail aeussert sich nur als 404-Platzhalter im Bild-Endpunkt, siehe thumbnails.py.

    Gibt das Seitenverhaeltnis des GEZEIGTEN Bildes zurueck, oder `None`, wenn keines ermittelt
    werden konnte (Downloadfehler, nicht dekodierbar, entartetes Verhaeltnis).

    Nimmt bewusst `photo_id`/`etag` statt eines `Photo`-Objekts entgegen: wird als Teil
    von _fetch_and_thumbnail parallel zu Geschwister-Aufrufen desselben Blocks ausgefuehrt und darf
    deshalb keinerlei Session-Zugriff ausloesen - ein ORM-Objekt hier entgegenzunehmen wuerde dazu
    verleiten, versehentlich weitere (nicht nebenlaeufigkeitssichere) Attribute zu lesen/zu
    setzen."""
    try:
        content = await client.download(webdav_url, relative_path)
    except OpenCloudError:
        return None
    return generate_variants(cache_dir, photo_id, etag, content)


@dataclass(frozen=True)
class ScanExifResult:
    """Das EXIF-Ergebnis EINES Arbeitspostens: Zeitpunkt UND Koordinate aus demselben
    Range-Read-Fenster.

    Eingefroren und zusammengesetzt statt zweier nackter Rueckgabewerte, damit die Typzusicherung
    nach `asyncio.gather` in `_process_scan_block` weiterhin die FORM festnageln kann - eine
    durchgereichte `BaseException` (mit `return_exceptions=True` faengt `gather` ein
    `CancelledError` einer Kind-Coroutine NICHT ab) darf nicht in die Felder entpackt werden.

    `gps` ist ein Paar oder `None` - nie eine halbe Koordinate (Paar-Invariante von
    `extract_gps`).

    `taken_at` ist hier die AUFGEZEICHNETE Zeit (EXIF `DateTimeOriginal`, sonst der Rueckfall auf
    `last_modified`) - die Korrektur um den Kamera-Versatz passiert erst im sequentiellen Teil von
    `_process_scan_block`, wo die Kamerazeile und damit der Versatz bekannt sind.

    `aspect_ratio` ist das Seitenverhaeltnis des GEZEIGTEN Bildes, das die Thumbnail-Erzeugung
    ohnehin kennt - `None` fuer einen `probe_only`-Posten (es wurde gar nichts dekodiert) und fuer
    jeden Fehlerfall. Es faellt bei derselben Dekodierung an wie die Vorschau; es entsteht kein
    zusaetzlicher Abruf und kein zweites Dekodieren."""

    taken_at: datetime
    gps: tuple[float, float] | None
    camera: CameraIdentity | None
    aspect_ratio: float | None = None


async def _fetch_and_thumbnail(
    client: OpenCloudScanClient,
    webdav_url: str,
    relative_path: str,
    extension: str,
    fallback_taken_at: datetime,
    photo_id: int,
    etag: str,
    cache_dir: Path,
    *,
    probe_only: bool = False,
) -> ScanExifResult:
    """Der reine I/O-/CPU-Teil eines einzelnen Arbeitspostens aus Phase 2b: EXIF-Range-Read
    (nur für JPEG-Kandidaten) für `taken_at`, die
    GPS-Koordinate UND die Kamera-Angabe, danach best-effort Download + Thumbnail-Erzeugung -
    bewusst OHNE jeglichen Session-Zugriff, damit mehrere Aufrufe sicher parallel per
    asyncio.gather laufen koennen (_process_scan_block unten). Ein EXIF-Lesefehler wird NICHT
    abgefangen: ein einzelner OpenCloud-Fehler hier laesst den gesamten Scan fehlschlagen.

    Alle DREI EXIF-Werte stammen aus DEMSELBEN bereits geladenen Byte-Fenster - kein zusaetzlicher
    Netzwerkzugriff fuer Koordinate oder Kamera. Fuer Nicht-JPEG-Posten wird gar kein EXIF
    gelesen: der Zeitpunkt faellt auf `fallback_taken_at` zurueck, Koordinate und Kamera bleiben
    `None`.

    `probe_only` ueberspringt AUSSCHLIESSLICH die Thumbnail-Erzeugung (die Nachhol-Runde der
    Kamera-Angabe an einer unveraenderten Datei - die Thumbnails existieren und waeren identisch).
    Das EXIF-Fenster wird weiterhin gelesen; genau darum geht es."""
    taken_at = fallback_taken_at
    gps: tuple[float, float] | None = None
    camera: CameraIdentity | None = None
    if extension in _EXIF_CANDIDATE_EXTENSIONS:
        content = await client.get_range(webdav_url, relative_path, _EXIF_RANGE_BYTES)
        exif_taken_at = extract_taken_at(content)
        if exif_taken_at is not None:
            taken_at = exif_taken_at
        gps = extract_gps(content, photo_id=photo_id)
        camera = extract_camera(content, photo_id=photo_id)

    aspect_ratio: float | None = None
    if not probe_only:
        aspect_ratio = await _generate_thumbnails(
            client, webdav_url, relative_path, photo_id, etag, cache_dir
        )
    return ScanExifResult(taken_at=taken_at, gps=gps, camera=camera, aspect_ratio=aspect_ratio)


async def _resolve_project_camera(
    session: AsyncSession,
    project_id: int,
    identity: CameraIdentity,
    cache: dict[tuple[str, str], ProjectCamera],
) -> ProjectCamera:
    """Die Kamerazeile DIESES Projekts zur uebergebenen Identitaet - angelegt, falls es sie noch
    nicht gibt, mit `offset_minutes = 0`.

    Der `cache` wird von `run_project_scan` ueber alle Bloecke eines Laufs durchgereicht: ohne ihn
    entstuende eine Abfrage JE FOTO statt je Kamera, und ein Projekt hat typischerweise zwei
    Kameras und tausende Fotos.

    SICHERHEIT (Projektgrenze): `project_id` steht in derselben Anweisung, die die Zeile
    aufloest - `Photo.camera_id` zeigt damit ausschliesslich auf eine Zeile desselben Projekts."""
    key = (identity.make, identity.model)
    cached = cache.get(key)
    if cached is not None:
        return cached

    existing = (
        await session.execute(
            select(ProjectCamera).where(
                ProjectCamera.project_id == project_id,
                ProjectCamera.make == identity.make,
                ProjectCamera.model == identity.model,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = ProjectCamera(
            project_id=project_id, make=identity.make, model=identity.model, offset_minutes=0
        )
        session.add(existing)
        await session.flush()
    cache[key] = existing
    return existing


async def _process_scan_block(
    session: AsyncSession,
    client: OpenCloudScanClient,
    webdav_url: str,
    cache_dir: Path,
    project_id: int,
    block: list[ScanWorkItem],
    camera_cache: dict[tuple[str, str], ProjectCamera] | None = None,
) -> tuple[int, int]:
    """Verarbeitet einen einzelnen Block von Arbeitsposten, Blockgröße
    settings.scan_download_concurrency: zunächst sequentiell Photo-Zeilen
    anlegen/aktualisieren + flush() - KEIN commit() hier, ein
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
                # Beide vorlaeufig, beide werden unten nach dem gather() ersetzt - erst dort
                # steht der EXIF-Wert fest. `taken_at_original` ist NOT NULL ohne Default und
                # muss deshalb schon hier einen Wert tragen.
                taken_at=last_modified,
                taken_at_original=last_modified,
                last_modified=last_modified,
            )
            session.add(photo)
            added += 1
        photos.append(photo)

    if added:
        # Nur neu angelegte Zeilen brauchen flush() fuer eine DB-vergebene ID (fuer den
        # Thumbnail-Dateinamen unten) - bereits bestehende Zeilen haben schon eine ID.
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
                probe_only=item.probe_only,
            )
            for index, item in enumerate(block)
        ],
        return_exceptions=True,
    )

    # Python-Async-Fallstrick: mit return_exceptions=True faengt asyncio.gather() ein
    # CancelledError, das eine EINZELNE Kind-Coroutine wirft, NICHT als Exception ab, sondern
    # reicht es als gewoehnliches Element der Ergebnisliste durch - `await gather(...)` selbst
    # wirft in diesem Fall NICHTS. Ohne diese explizite Pruefung erreichte ein Abbruch mitten in
    # einer parallelen I/O-Coroutine den `except asyncio.CancelledError`-Zweig in run_project_scan
    # nicht. Eine ECHTE aeussere Task-Cancellation (arq job_timeout) propagiert dagegen ohne
    # Sonderbehandlung roh durch `await gather(...)` hindurch - dieser Fall betrifft ausschliesslich
    # eine Kind-Coroutine, die CancelledError selbst wirft/traegt.
    # Bricht in tests/test_worker_scan_project.py.
    for result in results:
        if isinstance(result, asyncio.CancelledError):
            raise result
    for result in results:
        if isinstance(result, BaseException):
            raise result

    cache = {} if camera_cache is None else camera_cache
    for photo, exif_result, item in zip(photos, results, block, strict=True):
        # Die Typzusicherung nagelt die FORM fest: ohne sie entpackte eine durchgereichte
        # BaseException ihre Attribute in die Foto-Felder, statt oben als Fehler erkannt zu werden.
        assert isinstance(exif_result, ScanExifResult)  # bereits oben auf Exceptions geprueft

        # UNBEDINGT schreiben, auch zurueck auf None - dieselbe Begruendung wie bei `gps_lat`
        # unten: verliert eine Datei ihre Kamera-Angabe, verliert das Foto sie auch. Der Merker
        # wird AUCH OHNE FUND gesetzt, sonst liest jeder weitere Scan den Bestand erneut.
        camera = (
            None
            if exif_result.camera is None
            else await _resolve_project_camera(session, project_id, exif_result.camera, cache)
        )
        photo.camera_id = None if camera is None else camera.id
        photo.camera_probed = True

        # DIE ERSTE der zwei Schreibstellen der Invariante (ADR 0090, Punkt 1; die zweite ist
        # `api/cameras.py`), und beide rechnen ueber `cameras.py::shifted` aus
        # `taken_at_original` - NIE aus dem bestehenden `taken_at`. Eine Differenz auf den
        # bestehenden Wert zu addieren kumulierte bei jedem weiteren Lauf.
        photo.taken_at_original = exif_result.taken_at
        offset_minutes = 0 if camera is None else camera.offset_minutes
        corrected = shifted(exif_result.taken_at, offset_minutes)
        if corrected is None:
            # Ausfallrichtung fuer dieses EINE Foto: die unkorrigierte Zeit plus eine Warnzeile
            # mit festem Token - kein Laufabbruch und kein Datum ausserhalb des darstellbaren
            # Bereichs. Die Invariante ist fuer dieses Foto damit bewusst verletzt; ein Versatz,
            # der das ausloest, ist am Endpunkt gar nicht setzbar (dort 422).
            logger.warning(
                "_process_scan_block: Versatz nicht anwendbar photo_id=%s grund=%s",
                photo.id,
                _OFFSET_REASON_OUT_OF_RANGE,
            )
        photo.taken_at = exif_result.taken_at if corrected is None else corrected
        # SICHERHEIT: UNBEDINGT beide Felder schreiben, auch zurück auf None. Das ist eine
        # DATENSCHUTZBEDINGUNG, keine Aufräum-Kosmetik - dies ist der einzige Pfad, über den
        # das ENTFERNEN von GPS aus einer Quelldatei in PhotoSort ankommt, also genau die
        # Handlung, die eine datenschutzbewusste Person vornimmt. Ein bedingtes Schreiben
        # (`if gps is not None`) hielte die alte Koordinate unbegrenzt fest, und die
        # Anwendung zeigte weiter einen Ort an, den die Datei nachweislich nicht mehr
        # enthält. Abgedeckt durch test_worker_scan_project.py.
        photo.gps_lat, photo.gps_lon = exif_result.gps or (None, None)

        # ERSTER der zwei Schreibwege der Spalte (ADR 0110 Punkt 3). Fuer einen Posten, der die
        # Datei tatsaechlich gelesen hat, wird UNBEDINGT geschrieben - auch zurueck auf `None`:
        # Aendert eine Datei ihre Form, aendert das Foto sie mit, und ein nicht mehr dekodierbares
        # Bild verliert seine Angabe, statt eine falsche zu behalten. Zurueck auf `None` heisst
        # dabei nichts Endgueltiges: `aspect_ratio IS NULL` ist zugleich die Arbeitsmenge der
        # Nachhol-Runde, die es beim naechsten Lauf erneut versucht.
        #
        # Ein `probe_only`-Posten wird dabei UEBERSPRUNGEN statt auf `None` gesetzt: Er hat die
        # Datei gar nicht geladen (das ist sein ganzer Zweck) und weiss deshalb nichts ueber ihre
        # Form. Ein unbedingtes Schreiben loeschte hier bei jedem Scan einen bereits bekannten,
        # unveraendert gueltigen Wert.
        if not item.probe_only:
            photo.aspect_ratio = exif_result.aspect_ratio

    return added, updated


async def _maybe_commit_progress_checkpoint(
    session: AsyncSession, run: ScanRun, count: int
) -> None:
    """Gemeinsamer Zwischen-Commit-Checkpoint für Phase 1 (Enumeration) UND Phase 2a
    (Skip-Fälle) - ein einziger Aufrufpunkt statt zweier `continue`-Zweige:
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
    """Phase 1 (Enumeration): materialisiert `client.walk(...)` zu einer In-Memory-Liste - KEIN
    Photo-DB-Schreibzugriff, nur periodische files_found/last_progress_at-Checkpoints (bestehende
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


# Blockgroesse der Nachhol-Runde: je Block ein Commit und ein Fortschrittsstempel (Auflage S1).
# Modul-Konstante statt Default-Parameterwert, damit Tests sie per
# monkeypatch.setattr(worker, "ASPECT_RATIO_CATCH_UP_BATCH_SIZE", ...) verkleinern koennen -
# dasselbe Muster wie SCAN_COMMIT_BATCH_SIZE.
ASPECT_RATIO_CATCH_UP_BATCH_SIZE = 200

# Das aus der VORSCHAU gelesene Verhaeltnis ist wegen der Ganzzahl-Skalierung beim Erzeugen der
# Vorschau nicht exakt das des Originals. Diese relative Abweichung ist die zugesicherte Grenze;
# sie wird nie auf Gleichheit mit dem Scan-Weg geprueft. Bei THUMBNAIL_MAX_SIZE = 400 kann die
# kurze Kante um hoechstens eine halbe Pixelzeile danebenliegen - eine relative Abweichung von
# unter einem Prozent, und damit weit unterhalb dessen, was im Raster sichtbar waere.
ASPECT_RATIO_PREVIEW_TOLERANCE = 0.01


def _read_cached_aspect_ratios(
    cache_dir: Path, photos: Sequence[tuple[int, str]]
) -> list[tuple[int, float]]:
    """Liest das Seitenverhaeltnis der uebergebenen `(photo_id, etag)`-Paare aus ihrer lokalen
    Vorschau-Variante. Ein Paar ohne lesbare Datei kommt schlicht nicht zurueck.

    Rein synchron und ohne DB-Bezug (deshalb Tupel statt ORM-Objekten), genau wie
    `thumbnails.measure_cache_usage`: Der Aufrufer fuehrt sie ueber `asyncio.to_thread` aus, damit
    die Event-Loop bei einem Dateisystemzugriff je Foto nicht blockiert.

    SICHERHEIT (Auflage S4): Der Pfad entsteht AUSSCHLIESSLICH ueber `thumbnails.thumbnail_path`.
    Der `etag` kommt vom WebDAV-Server, ist damit Fremdtext und geht dort nur als SHA-256-Eingabe
    in `cache_key` ein, nie in einen Dateinamen. Jede zweite Pfadbildung, die `etag` oder
    `relative_path` als Namensbestandteil verwendet, bleibt untersagt: ein `etag` mit `../` laese
    sonst aus einem beliebigen Pfad ausserhalb des Cache-Verzeichnisses.

    SICHERHEIT (Auflage S2): Je Foto isoliert - die Fehlerbehandlung liegt vollstaendig in
    `aspect_ratio_of_cached_thumbnail` (bewusst breites `except Exception`). Hier steht deshalb
    kein zweiter, engerer Block."""
    ratios: list[tuple[int, float]] = []
    for photo_id, etag in photos:
        ratio = aspect_ratio_of_cached_thumbnail(thumbnail_path(cache_dir, photo_id, etag))
        if ratio is not None:
            ratios.append((photo_id, ratio))
    return ratios


async def _catch_up_aspect_ratios(
    session: AsyncSession, project_id: int, cache_dir: Path, run: ScanRun
) -> int:
    """Fuellt `Photo.aspect_ratio` fuer die Bestandsfotos des Projekts aus deren lokal
    zwischengespeichertem Vorschaubild - ohne Netz, ohne OpenCloud-Abruf, ohne das Original
    (ADR 0110 Punkt 3). Gibt die Zahl der gefuellten Zeilen zurueck.

    Die Arbeitsmenge ist `aspect_ratio IS NULL` und damit zugleich die Abbruchbedingung: Es gibt
    KEINE Merker-Spalte nach dem Muster von `camera_probed`. Der Merker dort verhindert einen
    wiederholten NETZZUGRIFF je Bestandsfoto; hier kostet ein erneuter Versuch einen lokalen
    Dateizugriff. Fehlt die Cache-Datei, bleibt der Wert `NULL` und der naechste Scan versucht es
    erneut.

    SICHERHEIT (Auflage S1): Je Block wird committet UND `ScanRun.last_progress_at` gesetzt.
    Diese Runde laeuft VOR Phase 1 und damit vor dem ersten Stempel, den `run_project_scan` sonst
    setzt. Ohne eigene Commit-Punkte setzte `reap_stalled_runs` einen Lauf, dessen Runde laenger
    als `STALL_THRESHOLD` (15 Minuten) ohne Stempel arbeitet, auf FAILED - und braeche die
    Coroutine dabei bewusst NICHT ab. Der Scan liefe weiter, waehrend die Oberflaeche
    "fehlgeschlagen" sagt.

    SICHERHEIT (Auflage S1, zweiter Teil): Geladen werden je Foto nur `id` und `etag`, nie ganze
    `Photo`-Objekte ueber den gesamten Bestand - ein `select(Photo)` zoege bei zehntausenden
    Bestandsfotos ebenso viele ORM-Objekte in die Sitzung."""
    rows = (
        (
            await session.execute(
                select(Photo.id, Photo.etag).where(
                    Photo.project_id == project_id,
                    Photo.aspect_ratio.is_(None),
                )
            )
        )
        .tuples()
        .all()
    )
    filled = 0
    for start in range(0, len(rows), ASPECT_RATIO_CATCH_UP_BATCH_SIZE):
        block = list(rows[start : start + ASPECT_RATIO_CATCH_UP_BATCH_SIZE])
        ratios = await asyncio.to_thread(_read_cached_aspect_ratios, cache_dir, block)
        for photo_id, ratio in ratios:
            await session.execute(
                update(Photo).where(Photo.id == photo_id).values(aspect_ratio=ratio)
            )
        filled += len(ratios)
        run.last_progress_at = _now_utc()
        await session.commit()
    return filled


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
        # Nachhol-Runde fuer den Bestand, VOR Phase 1 und vor jedem Netzzugriff dieses Laufs
        # (ADR 0110 Punkt 3). Sie steht bewusst vor dem Laden von `existing_photos`: So schreibt
        # sie ausschliesslich per UPDATE-Anweisung und kann keine ORM-Objekte hinter dem Ruecken
        # der Sitzung veraltern lassen.
        await _catch_up_aspect_ratios(session, project.id, cache_dir, scan_run)

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

        # Phasenuebergang: total_files wird HIER einmalig gesetzt, files_found auf 0
        # zurueckgesetzt - das Feld wechselt die Bedeutung von "in Phase 1 gelistet" auf "in
        # Phase 2 verarbeitet". Sofort committet, damit ein zwischen Phase 1 und Phase 2
        # beobachtender Client (Polling) diesen konsistenten Zwischenzustand sehen kann
        # (total_files gesetzt, files_found == 0).
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
        # _process_scan_block. Blockgroesse = settings.scan_download_concurrency
        # (env-ueberschreibbar); ein Commit PRO BLOCK (nicht an die SCAN_COMMIT_BATCH_SIZE-Kadenz
        # von Phase 1/2a gekoppelt), das ist zugleich die Crash-Sicherheits-Grenze.
        photos_added = 0
        photos_updated = 0
        # settings.scan_download_concurrency ist per Field(ge=1) in config.py bereits gegen
        # 0/negative Werte validiert und fällt beim Prozessstart auf - kein zusätzlicher
        # Laufzeit-Clamp hier nötig.
        concurrency = settings.scan_download_concurrency
        work_items = classification.work_items
        # EIN Cache ueber alle Bloecke des Laufs: sonst eine Kamera-Abfrage je Foto statt je
        # Kamera. Er haelt ORM-Objekte derselben Sitzung, die der Lauf ohnehin durchgaengig
        # benutzt.
        camera_cache: dict[tuple[str, str], ProjectCamera] = {}
        for start in range(0, len(work_items), concurrency):
            block = work_items[start : start + concurrency]
            added, updated = await _process_scan_block(
                session, client, drive.webdav_url, cache_dir, project.id, block, camera_cache
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
    except asyncio.CancelledError:
        # Schicht 1 des Fortschritts-Watchdogs: ein arq job_timeout-Ablauf, ein geplanter
        # Worker-Shutdown und ein künftiger Job.abort() lösen alle denselben
        # asyncio.CancelledError-Pfad aus. Er wird bewusst NICHT unbehandelt durchgelassen: der
        # Lauf wird sofort auf FAILED gesetzt, danach re-raised - kein Verschlucken einer
        # BaseException, arqs eigene Task-/Retry-Buchhaltung funktioniert dadurch unverändert
        # weiter.
        await _fail_run(session, scan_run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown).")
        raise
    except Exception as exc:
        # BREIT abfangen, nicht nur OpenCloudError: jede andere Exception (z.B. aus dem
        # WebDAV-XML-Parsing, siehe opencloud/client.py::list_folder) liefe sonst ungefangen durch
        # und liesse den ScanRun dauerhaft auf status="running" haengen, ohne Watchdog/Recovery.
        # OpenCloudError ist eine Teilmenge von Exception, ein einzelner breiter Handler reicht
        # deshalb aus - dasselbe Muster wie in run_project_scoring unten.
        await _fail_run(session, scan_run, str(exc))
        return scan_run

    # Ab hier ist der Lauf SUCCESS: der Erfolgspfad faellt aus dem `try` HERAUS, beide
    # Fehlerzweige kehren oben zurueck bzw. re-raisen. Damit erreicht die Bereinigung den Abbruch-
    # und den Fehlerpfad strukturell nicht (bei Abbruch/Fehlschlag wird nicht aufgeraeumt, der
    # naechste erfolgreiche Scan holt es nach).
    #
    # AUSSERHALB des Fehler-Handlers und mit eigenem `except`: ein Fehler beim Aufraeumen darf
    # einen bereits erfolgreichen Lauf nicht nachtraeglich auf FAILED setzen. Der unmittelbar
    # vorangehende `commit()` ist zugleich der Commit-Rand, nach dem der Schnappschuss der
    # Bereinigung gezogen wird.
    try:
        await cleanup_orphaned_cache(session, cache_dir)
    except Exception:
        # Das `rollback()` ist keine Kosmetik: schlaegt die Schnappschuss-Abfrage fehl, bliebe die
        # Transaktion sonst blockiert. Es expired aber alle ORM-Objekte der Session - ohne das
        # anschliessende `refresh()` liefe der Attributzugriff auf `scan_run.id` in `scan_project`
        # in einen impliziten Lazy-Load ausserhalb eines aktiven greenlet-Kontexts
        # (sqlalchemy.exc.MissingGreenlet), und der Job stuerzte NACH einem erfolgreichen Scan ab.
        await session.rollback()
        await session.refresh(scan_run)
        logger.warning("Bereinigung des Bild-Caches fehlgeschlagen", exc_info=True)
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
    Berechnung übersprungen. SICHERHEIT: das deckt insbesondere den
    `DecompressionBombError` ab."""
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
    """Scort alle Fotos eines Projekts neu (kein inkrementelles Scoring) auf Basis der bereits vom
    Scan gecachten display-Variante - kein erneuter OpenCloud-Download.

    Ablauf: ScoringRun anlegen -> photos_total setzen -> pro Foto Heuristiken berechnen,
    PhotoScore upserten, photos_processed periodisch committen -> projektweite
    Duplikat-/Cluster-Erkennung -> suggested_status setzen -> ScoringRun auf success/failed
    setzen. Ranking-Grundlage ist die Kriterien-/Rangfolgen-Schicht (criteria.py/ranking.py).
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
            # Bekannte, akzeptierte Lücke: wird die display-Cache-Datei eines
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
                # Vollstaendig ueberschreiben statt nur einzelner Felder: alte
                # duplicate_of/cluster_key/suggested_status-Werte aus einem frueheren Lauf duerfen
                # nicht stehen bleiben, bevor der neue Cluster-Pass unten sie ggf. neu setzt.
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
                # Fortschritts-Watchdog (Schicht 2) - analog run_project_scan oben.
                scoring_run.last_progress_at = _now_utc()
                await session.commit()

        scoring_run.photos_processed = processed
        await session.commit()

        # Um die Koordinate erweitert - KEIN zusaetzlicher Query, die `photos` liegen an dieser
        # Stelle bereits vollstaendig vor.
        cluster_input_by_id = {
            photo.id: (photo.taken_at, photo.gps_lat, photo.gps_lon) for photo in photos
        }

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
        cluster_map = assign_clusters(
            [
                ClusterCandidate(
                    photo_id=photo_id,
                    taken_at=cluster_input_by_id[photo_id][0],
                    gps_lat=cluster_input_by_id[photo_id][1],
                    gps_lon=cluster_input_by_id[photo_id][2],
                )
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
        # Ausschuss-Gate-Autoset: kein Ausschuss gefunden -> nichts zu sichten, das Gate blockiert
        # dann nicht mit einer leeren Liste. Ein nachfolgender expliziter confirm-ausschuss-gate-
        # Aufruf bleibt trotzdem fehlerfrei moeglich (Idempotenz, siehe api/projects.py).
        if scoring_run.suggestions_found == 0:
            scoring_run.gate_confirmed_at = _now_utc()
        await session.commit()
        return scoring_run
    except asyncio.CancelledError:
        # Schicht 1 des Fortschritts-Watchdogs - analog run_project_scan oben.
        await _fail_run(
            session, scoring_run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown)."
        )
        raise
    except Exception as exc:
        # Kein Rollback bereits committeter PhotoScore-Zeilen/des letzten committeten
        # photos_processed-Stands - session.rollback() verwirft nur die seit dem letzten commit()
        # offene, noch nicht persistierte Transaktion, exakt wie im OpenCloudError-Pfad von
        # run_project_scan oben.
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
    try/except als FAILED-Lauf mit error_message behandelt. Der Guard sitzt im Worker-Job,
    zusaetzlich zum eigenen 409 der API-Schicht."""


# Die von _compute_content_criteria best-effort berechneten Kriterien-Keys - eine Liste statt
# einzelner if-Blöcke im Aufrufer, damit ein weiteres bildbasiertes Kriterium keine Kopie des
# Upsert-Codes braucht. Die zugehoerige CriterionSource wird bewusst NICHT hier dupliziert, sondern
# direkt aus criteria.py::CRITERIA_REGISTRY abgeleitet - eine Aenderung an der Registry (z.B. ein
# Kriterium wechselt von local_heuristic zu local_ml) bleibt so automatisch konsistent, ohne dass
# diese Stelle separat nachgepflegt werden muss.
#
# Das ist die Menge der bildbasiert berechneten Kriterien fuer die Upsert-Buchhaltung und eine
# fachlich ANDERE als "traegt ein `presence_threshold`" (welche Kriterien eine Inhaltsaussage
# treffen): hier stehen auch goldener_schnitt/aesthetics, die keine treffen. Die beiden Mengen nie
# gleichsetzen.
_IMAGE_ANALYSIS_CRITERION_KEYS: tuple[str, ...] = (
    "content_people",
    "content_landscape",
    "tier",
    "goldener_schnitt",
    "gebaeude",
    # Zweites Kriterium aus derselben Szenen-Klassifikation, siehe _compute_content_criteria.
    "landschaft",
    "aesthetics",
    # Zwei weitere Kriterien aus DERSELBEN COCO-Detektorausgabe wie `tier` (siehe
    # _compute_content_criteria).
    "fahrzeug",
    "essen_trinken",
    # Kompositions-Ranking-Signale ab hier.
    "symmetrie",
    "horizont",
    "freiraum",
)
_IMAGE_ANALYSIS_CRITERION_SOURCES: dict[str, CriterionSource] = {
    key: CRITERIA_REGISTRY[key].source for key in _IMAGE_ANALYSIS_CRITERION_KEYS
}


def _try_build[T](build: Callable[[], T]) -> T | None:
    """Best-effort Modell-/Detektor-Konstruktion: ein Fehlschlag
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
    """Vorfilterung + Skip-bereits-gescorter-Fotos für den landmark-Cloud-Aufruf - reine, DB-freie
    Funktion, isoliert unit-testbar (analog _classify_scan_entries). Ein Foto wird nur dann
    Kandidat, wenn im selben Lauf content_landscape ODER gebaeude die jeweils registrierte
    presence_threshold erreicht (`>=`, inklusiv; die Registry-Schwellwerte werden
    wiederverwendet, es gibt hier KEINEN zweiten, doppelt gepflegten Grenzwert) UND noch keine
    landmark-Zeile aus einem frueheren Lauf existiert - die einzige, bewusst dokumentierte Ausnahme
    vom sonst projektweiten "jeder Lauf scort neu"-Prinzip. Gibt die photo_id-Reihenfolge von
    candidate_values zurueck, keine weitere Sortierung noetig.

    Die eigentliche Schwellenwert-Prüfung lebt in criteria.py::is_landmark_candidate, gemeinsam
    mit der API-seitigen Read-Time-Ableitung genutzt. Hier steht nur das
    Skip-bereits-gescorter-Fotos-Verhalten, das worker-spezifisch ist (keine API-Entsprechung)."""
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
    """Strukturiertes WARNING-Logging für einen best-effort übersprungenen
    Cloud-Vision-Aufruf - gemeinsam genutzt von der
    Landmark-Phase (run_criterion_scoring) und der Remote-Kategorie-Phase
    (run_remote_category_classification). Level WARNING statt ERROR: der Skip ist erwartetes,
    dokumentiertes best-effort-Verhalten, der Lauf selbst bleibt SUCCESS. Kein
    exc_info=True/Traceback - eine Zeile pro fehlgeschlagenem Foto reicht fuer Fehlergrund +
    Foto-Kontext.

    Nimmt `exc_type_name`/`exc_message` statt der rohen Exception: der Aufrufer berechnet
    `type(exc).__name__`/`str(exc)` GENAU EINMAL an der jeweiligen Call-Site und reicht beide
    Werte sowohl hierher als auch an `_record_cloud_vision_error` durch - keine zweite,
    potenziell abweichende Auswertung an zwei Stellen.

    SICHERHEIT: `exc_message` stammt ausschließlich aus der bereits an der
    Exception-Konstruktionsstelle sanitierten Meldung (siehe
    cloud_vision.py::raise_for_vision_api_status/*_response_to_json) - hier NIE erneut auf
    `response.text`/`.json()`/`.headers` zugreifen."""
    logger.warning(
        "Cloud-Vision-Aufruf fehlgeschlagen (%s): photo_id=%s relative_path=%s %s: %s",
        phase,
        photo_id,
        relative_path,
        exc_type_name,
        exc_message,
    )


def _counted(count: int, singular: str, plural: str) -> str:
    """Zahlwort mit passendem Numerus - "1 Wiederholung", aber "0"/"2 Wiederholungen"."""
    return f"{count} {singular if count == 1 else plural}"


def _log_cloud_vision_throttling(phase: str, provider: str, stats: ThrottleStats) -> None:
    """Strukturiertes WARNING-Logging der VERTEILUNG eines Cloud-Teilschritts, der Gegenpart zu
    _log_cloud_vision_failure daneben.

    Hoechstens EINE Zeile je Teilschritt, und nur wenn tatsaechlich gewartet wurde: der Helfer
    kehrt wirkungslos zurueck, wenn weder eine Anfrage eingereiht noch eine Wiederholung noetig
    war. Das Logvolumen bleibt damit an den Ausnahmefall gebunden statt an jeden Lauf.

    Level WARNING statt INFO: das Root-Level des Projekts ist WARNING, eine INFO-Zeile erschiene in
    `docker compose logs` gar nicht erst.

    SICHERHEIT: `stats` sind ausschließlich ZAHLEN - nie eine Antwort, nie ein Headerwert,
    nie `response.text`/`.headers`/`.json()`.

    Die Zeile benennt den Schrittmacher ausdrücklich als ANBIETERWEIT, und das ist ein bekanntes
    Restrisiko: `ThrottleStats.since()` liest prozessweite Zähler, bei zwei gleichzeitigen Jobs
    enthaelt die Zusammenfassung des einen Laufs die Wartezeiten des anderen. Eine Zahl, die etwas
    anderes misst als ihr Label verspricht, schwaecht genau die Lauf-/Kostentransparenz, der das
    Sicherheitskonzept die Rolle eines Erkennungsmechanismus zuschreibt."""
    if stats.delayed_requests == 0 and stats.retries == 0:
        return
    logger.warning(
        "Cloud-Vision-Anfragen gedrosselt (%s): %s eingereiht, %.1f s verteilt, "
        "%s nach 429 mit %.1f s Wartezeit - der Schrittmacher gilt anbieterweit "
        "(%s) und nicht nur fuer diesen Lauf.",
        phase,
        _counted(stats.delayed_requests, "Anfrage", "Anfragen"),
        stats.total_delay_seconds,
        _counted(stats.retries, "Wiederholung", "Wiederholungen"),
        stats.total_retry_wait_seconds,
        provider,
    )


# Defensive Obergrenze fuer eine entartete Fehlermeldung - die eigentliche Absicherung bleibt die
# str(exc)-Konstruktion (keine Secrets/Rohdaten), diese Kappung ist nur eine Storage-/
# Degenerationsgrenze.
#
# SICHERHEIT (die Zielgruppe dieser Fehlermeldung reicht vom Server-Log-Leser bis zum App-Nutzer):
# Die persistierte Meldung darf keinen URL-Query-Parameter tragen. Betroffen ist der von
# httpx.HTTPError gewrappte Netzwerkfehler
# (landmark.py::LandmarkApiError/remote_classification.py::RemoteCategoryClassificationApiError,
# jeweils "... API nicht erreichbar: {exc}"). Getragen wird die Zusage davon, dass beide Call-Sites
# ausschliesslich die fest codierten URL-Konstanten ANTHROPIC_MESSAGES_URL/
# MISTRAL_CHAT_COMPLETIONS_URL aufrufen (cloud_vision.py) - beide ohne Query-String. Jeglicher
# Payload (Bilddaten/API-Key) geht per POST-Body/-Header, NIE als Query-Parameter; eine URL mit
# Query-String gehoert an diesen Call-Sites nicht hin.
_MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH = 500


async def _commit_phase_costs(session: AsyncSession) -> None:
    """Committet die im `finally`-Block der Cloud-Phase gesetzten Ist-Kostenspalten - und
    wirft dabei NIE.

    Der Aufruf sitzt in einem `finally`, laeuft also auch waehrend eine Exception nach oben
    laeuft. Scheitert genau dieses Commit, wuerde seine eigene Exception die urspruengliche
    ERSETZEN und der eigentliche Fehlergrund waere weder im Log noch in `run.error_message`
    erkennbar - genau in dem Moment, in dem man eine brauchbare Diagnose braucht. Das ist real
    erreichbar: nach einem fehlgeschlagenen `flush()` (z.B. IntegrityError im Klassifizierungs-
    Block) wirft `commit()` einen PendingRollbackError.

    Im Fehlerfall gehen die Kostenwerte dieses Laufs verloren (das Rollback verwirft sie) - das
    ist der bewusst gewaehlte kleinere Schaden: eine fehlende Kostenangabe faellt ueber den
    Unvollstaendigkeits-Hinweis der Statistikseite auf, eine verschluckte Fehlerursache nicht.
    Das anschliessende `rollback()` hinterlaesst eine benutzbare Session, damit `_fail_run` den
    Lauf noch auf FAILED setzen kann.

    Auch dieses `rollback()` ist abgesichert. Es laeuft in genau
    der Lage, in der schon das Commit gescheitert ist (Verbindungsabbruch, DBAPI-Problem) - eine
    Exception von dort verliesse den Helfer und ersetzte die urspruengliche eine Ebene tiefer,
    also genau die Maskierung, gegen die er gebaut ist. Scheitert auch das Aufraeumen, bleibt der
    Session nichts mehr zu retten; _fail_run scheitert dann ebenfalls, aber mit SEINEM eigenen
    Fehler statt mit einem hier ausgeloesten. Sichtbar bleibt beides ueber die zwei Logzeilen.

    Bewusst OHNE `run.id` in der Logzeile: nach einem gescheiterten Commit sind die
    ORM-Attribute expired, ein lesender Zugriff loeste ausserhalb des greenlet-Kontexts einen
    Lazy-Load aus (MissingGreenlet) - dieselbe Falle, die _fail_run mit seinem refresh() abraeumt.
    Der Lauf ist ueber die von _fail_run geschriebene `error_message` identifizierbar."""
    try:
        await session.commit()
    except SQLAlchemyError as exc:
        logger.warning(
            "Ist-Kosten des Laufs konnten nicht gespeichert werden: %s", type(exc).__name__
        )
        try:
            await session.rollback()
        except SQLAlchemyError as rollback_exc:
            logger.warning(
                "Session nach dem gescheiterten Kosten-Commit nicht aufraeumbar: %s",
                type(rollback_exc).__name__,
            )


async def _record_cloud_vision_error(
    session: AsyncSession,
    photo_id: int,
    phase: CloudVisionPhase,
    exc_type_name: str,
    exc_message: str,
    now: datetime,
) -> None:
    """Upsert der letzten bekannten Fehler-Zeile für dieses Foto x CloudVisionPhase - bewusst
    getrennt von _log_cloud_vision_failure (ephemeres Log gegen dauerhafte, per API abrufbare
    Persistenz mit Lösch-Pfad bei Erfolg, siehe dortiger Docstring). Nimmt
    `exc_type_name`/`exc_message` bereits fertig berechnet entgegen - der Aufrufer berechnet
    `type(exc).__name__`/`str(exc)` GENAU EINMAL an der jeweiligen
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
    """Loescht eine ggf. vorhandene Fehler-Zeile nach einem erfolgreichen (Retry-)Versuch
    ("Aufraeumen bei Erfolg") - haelt die Tabelle konsistent mit ihrer eigenen
    Bedeutung ("letzter bekannter Versuch ist fehlgeschlagen"), auch wenn die Prioritaets-Kaskade
    in api/photos.py::_cloud_vision_status_out einen vergessenen Aufruf funktional abfangen
    wuerde (Erfolg schlaegt Fehler)."""
    existing = await session.get(PhotoCloudVisionError, (photo_id, phase))
    if existing is not None:
        await session.delete(existing)


def _landmark_place_hints(
    photos: Collection[Photo], info_by_cell: Mapping[tuple[float, float], PlaceInfo]
) -> dict[int, PlaceHint | None]:
    """Die Ortsangabe je Kandidatenfoto - rein, DB-frei und ohne Netzwerk.

    Ausschliesslich aus der EIGENEN gemessenen Koordinate des Fotos (S3, ADR 0106 Punkt 4): Die
    Inferenzbasis aus `events.py::infer_locations` wird hier nicht gelesen und diese Funktion
    bekommt sie gar nicht erst zu sehen. Ein Foto ohne eigene Koordinate bekommt `None`, und das
    ist kein Fehlerfall.

    Die Stufenwahl selbst liegt in `landmark.py::place_hint_for`; hier steht nur die Zuordnung von
    Foto zu abgelegter Auskunft."""
    hints: dict[int, PlaceHint | None] = {}
    for photo in photos:
        if photo.gps_lat is None or photo.gps_lon is None:
            hints[photo.id] = None
            continue
        info = info_by_cell.get(place_cell(photo.gps_lat, photo.gps_lon))
        hints[photo.id] = place_hint_for(usable_locality(info), photo.gps_lat, photo.gps_lon)
    return hints


def _landmark_place_cells(photos: Collection[Photo]) -> set[tuple[float, float]]:
    """Die abgelegten Zellen der Kandidatenfotos, fuer die es ueberhaupt eine gibt.

    Die Zellen, nach denen gefragt und unter denen abgelegt wird, sind unveraendert die von
    `place_cell` (`PLACE_CELL_DIGITS`) - die Vergroeberung auf die ausgehende Koernung passiert
    erst in `place_hint_for`, am sendenden Rand. Eine eigene Zellsorte in `place_lookups` entstuende
    sonst, und die abgelegte Ortsspur waere nicht mehr die eine des Projekts."""
    return {
        place_cell(photo.gps_lat, photo.gps_lon)
        for photo in photos
        if photo.gps_lat is not None and photo.gps_lon is not None
    }


async def _detect_landmark_for_photo(
    client: LandmarkClientLike, cache_dir: Path, photo: Photo, hint: PlaceHint | None
) -> LandmarkDetection:
    """Der reine I/O-/Netzwerk-Teil eines einzelnen Landmark-Kandidaten (analog
    _fetch_and_thumbnail) - bewusst OHNE Session-Zugriff, damit mehrere Aufrufe sicher parallel
    per asyncio.gather laufen koennen (siehe die Block-Schleife in run_criterion_scoring). Nutzt
    ausschliesslich die bereits vorhandene display-Cache-Variante, nie das
    Original - kein erneuter OpenCloud-Zugriff. Ein fehlender/nicht lesbarer Cache-Eintrag
    propagiert als gewoehnliche Exception (best-effort ueber return_exceptions=True in der
    aufrufenden Block-Schleife abgefangen), exakt wie ein LandmarkApiError des Clients selbst."""
    path = variant_path(cache_dir, photo.id, photo.etag, "display")
    image_bytes = path.read_bytes()
    return await client.detect(image_bytes, _CLOUD_VISION_IMAGE_MIME_TYPE, hint)


async def _upsert_landmark_detection(
    session: AsyncSession,
    photo_id: int,
    detection: LandmarkDetection,
    now: datetime,
    provider: str,
    canonical_name: str | None,
) -> None:
    """Legt eine photo_landmark_detections-Zeile nur an, wenn tatsaechlich ein Name identifiziert
    wurde (kein Platzhalter-"unbekannt") - wird nur aufgerufen, wenn detection.name is not None
    (siehe Aufrufer). `provider` wird atomar mit name/confidence gesetzt -dieser Aufruf feuert
    praktisch nie fuer ein bereits gescortes Foto (Skip ueber _select_landmark_candidates anhand von
    PhotoCriterionScore, providerunabhaengig), ein
    Providerwechsel ueberschreibt das Feld bei bereits gescorten Fotos deshalb nicht.

    ZWEI VERSCHIEDENE ZUSAGEN in einer Zeile: `name` und `confidence` gehen UNGEFILTERT hinein -
    die Antwort ist bezahlt und bleibt vollstaendig erhalten, ob aus ihr ein verwendbarer Name wird,
    entscheidet die Lesestelle. `canonical_name` dagegen setzt der Aufrufer nur oberhalb von
    `LANDMARK_CONFIDENCE_THRESHOLD` und nur mit gebautem Einbetter; sonst bleibt er `None`, und die
    Zeile verhaelt sich exakt wie vor dem Register."""
    assert detection.name is not None
    existing = await session.get(PhotoLandmarkDetection, photo_id)
    if existing is None:
        existing = PhotoLandmarkDetection(photo_id=photo_id)
        session.add(existing)
    existing.name = detection.name
    existing.confidence = detection.confidence
    existing.computed_at = now
    existing.provider = provider
    existing.canonical_name = canonical_name


async def _upsert_album_suitability(
    session: AsyncSession,
    photo_id: int,
    suitability: AlbumSuitability,
    now: datetime,
    provider: str,
) -> None:
    """Schreibt bzw. ersetzt die Albumtauglichkeitszeile eines Fotos - GENAU EINE je Foto, auch
    nach beliebig vielen Laeufen.

    Stufe, Begruendung, Anbieter und Zeitstempel werden gemeinsam gesetzt: die Zeile stammt
    immer vollstaendig aus EINER Antwort, ein gemischter Zustand aus zwei Aufrufen entsteht nicht.
    Aufgerufen wird sie nur mit einer bereits validierten Aussage (`album_suitability.py`) - ohne
    brauchbare Stufe entsteht gar keine Zeile, und das Foto bleibt Kandidat des naechsten Laufs.

    Weder `commit` noch eigene Transaktionsgrenze - die gehoert dem Aufrufer."""
    existing = await session.get(PhotoAlbumSuitability, photo_id)
    if existing is None:
        existing = PhotoAlbumSuitability(photo_id=photo_id)
        session.add(existing)
    existing.level = suitability.level
    existing.reason = suitability.reason
    existing.provider = provider
    existing.computed_at = now


# Der geschlossene eigene Vorrat von `place_lookups.source` - er hat genau einen Eintrag, weil es
# genau einen Weg zur Ortsauskunft gibt (ADR 0105 Punkt 1). Er stammt NIE aus der Antwort.
PLACE_LOOKUP_SOURCE = "geonames"

# Die Fabrik des Auflösers: aus der Menge der noch nicht beschafften Zellen entsteht ein Auflöser
# oder `None`. `None` heisst "es wird keiner gebaut" und ist ein arbeitsfaehiger Zustand.
PlaceResolverFactory = Callable[[Collection[tuple[float, float]]], PlaceResolver | None]


async def _place_infos(
    session: AsyncSession,
    project_id: int,
    cells: Collection[tuple[float, float]],
    build_resolver: PlaceResolverFactory | None,
) -> dict[tuple[float, float], PlaceInfo]:
    """Die Ortsauskunft je vergroeberter Zelle - aus dem Bestand gelesen, nur fuer die FEHLENDEN
    gefragt (Muster `event_inputs.py::_landmark_names`: die reine Logik im Modul, der
    Datenbankzugriff hier).

    SICHERHEIT (S6): Die Bindung an `project_id` steht in der Abfrage ausgeschrieben, und es gibt
    KEINEN Rueckfall auf die Zeile eines anderen Projekts - ein solcher Rueckfall waere der stille
    Weg, auf dem die Lebensdauer-Bindung der Ortsspur aufhoert zu gelten.

    `build_resolver` ist `None` im Request-Pfad (S10) und wird sonst erst gerufen, wenn es
    tatsaechlich etwas zu fragen gibt: ein Durchgang durch den Ortsdatensatz ohne offene Zelle
    waere reine Arbeit. Liefert die Fabrik `None` (Datensatz fehlt oder weicht von seinem Hash
    ab), wird nichts beschafft und nichts geschrieben; die Events behalten Nummer und Zeitspanne.

    DREI AUSGAENGE, und sie sind verschieden (ADR 0102 Punkt 5): **keine Antwort** schreibt KEINE
    Zeile - sonst vergiftete eine voruebergehende Stoerung die Zelle dauerhaft; eine **Antwort
    ohne brauchbare Ebene** schreibt eine Zeile mit leeren Namensstufen und wird nicht erneut
    gefragt; der dritte Ausgang (mehrere Namen in einem Event) faellt erst in `assign_place_names`.

    SCHREIBRAND (S7): Jede Namensstufe laeuft EINZELN durch `sanitize_place_name` - eine
    unbrauchbare Stufe wird `NULL`, nie die ganze Antwort verworfen, und verworfen wird ganz, nie
    abgeschnitten. `matched_level` wird gegen `PLACE_LEVELS` geprueft; ein Wert ausserhalb heisst
    `NULL`. Beides wirkt hier auch fuer einen kuenftigen Auflöser hinter demselben Protokoll.

    Weder `commit` noch eigene Transaktionsgrenze - die gehoert dem Aufrufer."""
    if not cells:
        return {}

    rows = (
        await session.execute(
            select(PlaceLookup).where(
                PlaceLookup.project_id == project_id,
                tuple_(PlaceLookup.cell_lat, PlaceLookup.cell_lon).in_(list(cells)),
            )
        )
    ).scalars()
    by_cell = {
        (row.cell_lat, row.cell_lon): PlaceInfo(
            neighbourhood=row.neighbourhood,
            locality=row.locality,
            matched_level=row.matched_level,
        )
        for row in rows
    }

    missing = sorted(set(cells) - set(by_cell))
    if not missing or build_resolver is None:
        return by_cell

    resolver = build_resolver(missing)
    if resolver is None:
        return by_cell

    now = _now_utc()
    for cell in missing:
        answer = await resolver.resolve(cell)
        if answer is None:
            continue
        level = answer.matched_level if answer.matched_level in PLACE_LEVELS else None
        info = PlaceInfo(
            neighbourhood=sanitize_place_name(answer.neighbourhood),
            locality=sanitize_place_name(answer.locality),
            matched_level=level,
        )
        session.add(
            PlaceLookup(
                project_id=project_id,
                cell_lat=cell[0],
                cell_lon=cell[1],
                neighbourhood=info.neighbourhood,
                locality=info.locality,
                region=sanitize_place_name(answer.region),
                country=sanitize_place_name(answer.country),
                matched_level=level,
                source=PLACE_LOOKUP_SOURCE,
                resolved_at=now,
            )
        )
        by_cell[cell] = info
    return by_cell


@dataclass(frozen=True)
class ContentCriteria:
    """Das Ergebnis der bildbasierten Analyse EINES Fotos: die Kriterien-Werte und die
    Flaechenanteile je Allow-Liste.

    Die Flaechenanteile sind KEIN Kriterium: sie bekommen keine Registry-Zeile, keine
    Datenbankspalte und keinen Eintrag in `_IMAGE_ANALYSIS_CRITERION_KEYS`. Sie sind eine
    Zwischengroesse auf dem Weg zur Motivstaerke (motifs.py::local_motif_strengths) und leben nur
    fuer die Dauer des Laufs - die Bounding-Boxen selbst werden nirgends persistiert.

    Geschluesselt sind sie mit dem KRITERIEN-Schluessel, dessen Allow-Liste sie ausgemessen haben
    (`content_people`, `tier`, `fahrzeug`, `essen_trinken`) - so gibt es keine zweite
    Schluesselmenge, die gegen `criteria.py` driften koennte.

    `not_measurable` traegt AUSSCHLIESSLICH die Kriterien, deren Detektion tatsaechlich LIEF und
    das Merkmal nicht fand - "nicht messbar". Es ist ausdruecklich KEIN Komplement von `values`:
    ein Kriterium, das mangels Detektor oder wegen einer Ausnahme gar nicht berechnet wurde
    ("nicht berechenbar"), fehlt in BEIDEN Mengen. Der Unterschied entscheidet ueber Loeschen
    oder Behalten einer Altzeile - eine Voreinstellung "alles, was nicht in `values` steht"
    loeschte beim Frühausstieg unten den gesamten Kriteriensatz eines Fotos."""

    values: dict[str, float]
    area_fractions: dict[str, float]
    not_measurable: frozenset[str] = frozenset()


def _compute_content_criteria(
    cache_dir: Path,
    photo: Photo,
    face_detector: FaceDetectorLike | None,
    animal_detector: ObjectDetectorLike | None,
    scene_classifier: SceneClassifierLike | None,
    aesthetics_model: AestheticsModelLike | None,
    face_landmarker: FaceLandmarkerLike | None,
) -> ContentCriteria:
    """Best-effort wie scoring.py::_compute_photo_metrics: JEDES hier berechnete Kriterium
    hat sein EIGENES try/except - ein einzelner fehlgeschlagener Berechnungsversuch
    (fehlende/defekte display-Cache-Datei, Modell-Ladefehler in genau einem Detektor) darf
    weder den gesamten Lauf noch die ÜBRIGEN, unabhängig berechenbaren Kriterien desselben
    Fotos mit sich reißen; je Kriterium gibt es dafür einen eigenen Fehlerfall-Testlauf. Das
    betroffene Kriterium bleibt für dieses Foto einfach ungeschrieben (kein Platzhalterwert
    wie 0). Die fünf Detektoren/Modelle sind bewusst `| None` typisiert: schlug der
    zugehörige
    `_try_build`-Aufruf im Aufrufer bereits fehl, wird das betroffene Kriterium (bzw. die davon
    abhaengigen) hier einfach uebersprungen, statt mit einem ungueltigen Objekt eine Exception zu
    provozieren, die erst durch das try/except unten "zufaellig" richtig behandelt wuerde.

    detect_person/detect_objects werden je HOECHSTENS einmal aufgerufen und fuer mehrere davon
    abhaengige Kriterien wiederverwendet (content_people+goldener_schnitt bzw.
    tier+fahrzeug+essen_trinken+goldener_schnitt) - kein zweiter, teurer detect()-Aufruf pro Foto
    und Detektortyp. goldener_schnitt wird nur dann berechnet,
    wenn BEIDE zugrunde liegenden Detektionen (auch mit leerem Ergebnis) erfolgreich waren - ein
    fehlgeschlagener Detektor darf nicht stillschweigend als "kein Subjekt gefunden" interpretiert
    werden, das waere ein unentdeckter Fehler statt eines ungeschriebenen Kriteriums."""
    path = variant_path(cache_dir, photo.id, photo.etag, "display")
    if not path.is_file():
        return ContentCriteria(values={}, area_fractions={})
    try:
        with Image.open(path) as opened:
            opened.load()
            image: Image.Image = opened
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
    except Exception:
        return ContentCriteria(values={}, area_fractions={})

    values: dict[str, float] = {}
    # "Die Detektion lief, das Merkmal fehlt" - gefuellt AUSSCHLIESSLICH dort, wo der Detektor ein
    # Ergebnis geliefert hat und die Score-Funktion `None` zurueckgibt. Nie als Komplement von
    # `values` gebildet: der Fruehausstieg oben verlaesst die Funktion mit zwei LEEREN Mengen,
    # und ein Komplement haette dort jedes Kriterium des Fotos als "nicht messbar" ausgewiesen.
    not_measurable: set[str] = set()
    # Die Flaechenanteile je Allow-Liste, aus DENSELBEN Detektionen wie die Scores darunter - kein
    # zweiter Detektoraufruf. Jede Berechnung hat ihr eigenes try/except wie die Scores: ein
    # Fehlschlag laesst genau diesen Anteil ungeschrieben (das Motiv bleibt bei 0), statt den
    # gesamten Lauf oder die uebrigen Anteile mitzureissen.
    area_fractions: dict[str, float] = {}

    faces: list[FaceBoundingBox] | None = None
    if face_detector is not None:
        try:
            faces = detect_person(image, face_detector)
            values["content_people"] = content_people_from_faces(faces)
        except Exception:
            faces = None
        if faces is not None:
            try:
                # AUSDRUECKLICH getrennt von `content_people`: das Kriterium bleibt die
                # 0.0/1.0-Praesenz (Rangfolge und Landmark-Kandidatenwahl haengen daran), der
                # Anteil ist die zusaetzliche Groesse fuer die Motivstaerke.
                area_fractions["content_people"] = bounding_box_area_fraction(faces)
            except Exception:
                pass

    # EIN detect_objects-Aufruf speist drei Kriterien plus goldener_schnitt. Die Objekt-Erkennung
    # und JEDE der drei Score-Berechnungen haben ein EIGENES try/except - ein Fehler in einer
    # Score-Funktion darf die beiden anderen nicht mitreißen (wie bei gebaeude/landschaft unten).
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
            # Dieselbe eine Detektorausgabe, drei Allow-Listen, drei Flaechenanteile - dieselben
            # Klassenmengen wie die drei Scores darueber.
            for criterion_key, allowed in (
                ("tier", ANIMAL_CATEGORIES),
                ("fahrzeug", VEHICLE_CATEGORIES),
                ("essen_trinken", FOOD_CATEGORIES),
            ):
                try:
                    area_fractions[criterion_key] = allow_listed_area_fraction(objects, allowed)
                except Exception:
                    pass

    try:
        values["content_landscape"] = compute_content_landscape(image)
    except Exception:
        pass

    # Keine Modell-/Detektor-Abhaengigkeit - wie content_landscape UNCONDITIONAL berechnet.
    try:
        values["symmetrie"] = compute_symmetrie_score(image)
    except Exception:
        pass

    # klassischer cv2-Algorithmus ohne trainiertes Modell - ebenfalls
    # UNCONDITIONAL berechnet, kein injizierbarer Detektor/Builder noetig.
    try:
        values["horizont"] = compute_horizon_tilt_score(image)
    except Exception:
        pass

    # classify_scene wird GENAU EINMAL pro Foto aufgerufen, dieselbe Label-Liste speist gebaeude UND
    # landschaft (Wiederverwendungsmuster wie detect_person -> content_people + goldener_schnitt) -
    # keine zusaetzlichen Kosten pro Foto. Die Label-Ermittlung und jede der beiden
    # Score-Berechnungen haben ein EIGENES try/except - ein Fehler in einer Score-Funktion darf das
    # jeweils andere Kriterium nicht mitreissen.
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
            # Nur die TIER-Erkennungen sind Kompositions-Subjekt-Kandidaten - kein Auto,
            # kein Teller.
            golden_ratio = compute_golden_ratio_score(faces, animal_detections(objects))
            # BEIDE Detektionen liefen (das sichern die `is not None` oben): ein `None` heisst
            # hier "kein Subjekt im Bild", also NICHT MESSBAR - und nicht "nicht berechenbar".
            if golden_ratio is None:
                not_measurable.add("goldener_schnitt")
            else:
                values["goldener_schnitt"] = golden_ratio
        except Exception:
            pass

    # EIGENSTAENDIGER, zusaetzlicher Modellaufruf neben dem obigen face_detector - kein Ersatz,
    # content_people/goldener_schnitt bleiben unveraendert auf dem bestehenden face_detector.
    if face_landmarker is not None:
        try:
            freiraum = compute_freiraum_score(detect_face_orientation(image, face_landmarker))
            # Die Detektion lief - ein `None` heisst "kein Gesicht erkannt", also NICHT MESSBAR.
            # Wirft `detect_face_orientation` dagegen, greift das `except` und das Kriterium
            # landet in KEINER der beiden Mengen ("nicht berechenbar").
            if freiraum is None:
                not_measurable.add("freiraum")
            else:
                values["freiraum"] = freiraum
        except Exception:
            pass

    return ContentCriteria(
        values=values, area_fractions=area_fractions, not_measurable=frozenset(not_measurable)
    )


# Defensive Obergrenze fuer die zusammengesetzte laufweite Cloud-Fehlermeldung - analog
# _MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH. Die eigentliche Absicherung bleibt, dass jeder
# Baustein entweder fest codiert ist oder aus einer bereits an der Exception-Konstruktionsstelle
# sanitierten Meldung stammt; diese Kappung ist nur eine Storage-/Degenerationsgrenze für den
# Fall mehrerer langer Teilmeldungen.
_MAX_RUN_CLOUD_ERROR_MESSAGE_LENGTH = 1000


def _append_cloud_error(run: CriterionScoringRun, message: str) -> None:
    """Hängt einen Baustein an die laufweite Cloud-Fehlermeldung an, statt sie zu überschreiben:
    ein Lauf kann mehrere unabhängige Cloud-Probleme haben (Phase 1 fehlgeschlagen UND
    Landmark-Client nicht konstruierbar UND einzelne Landmark-Aufrufe fehlgeschlagen), und keines
    davon darf ein anderes verdecken. Kein eigener Commit - der Aufrufer committet ohnehin an
    seinen bestehenden Punkten."""
    existing = run.cloud_error_message
    combined = message if existing is None else f"{existing} {message}"
    run.cloud_error_message = combined[:_MAX_RUN_CLOUD_ERROR_MESSAGE_LENGTH]


async def _build_grouping_and_rankings(
    session: AsyncSession,
    run: CriterionScoringRun,
    project_id: int,
    values_by_photo_id: Mapping[int, dict[str, float]],
    build_place_resolver: PlaceResolverFactory | None,
) -> None:
    """Die Gliederung eines Laufs samt seiner Rangzeilen: Event-Bildung, Partitionen und
    `PhotoRanking`-Zeilen.

    ZWEI Aufrufer, EIN Weg zur Gliederung: der Kriterien-Lauf (`run_criterion_scoring`) und der
    Neuaufbau nach einer Versatz-Aenderung (`rebuild_run_grouping`). Ein zweiter Rechenweg fuer
    dasselbe liefe auseinander.

    Die Kandidatenmenge IST `values_by_photo_id.keys()`; alles Weitere liest die Funktion selbst.
    Das kostet gegenueber dem durchgereichten Zustand eine Abfrage mehr JE LAUF - der Preis
    dafuer, dass beide Aufrufer garantiert dasselbe tun.

    `build_place_resolver` hat BEWUSST KEINEN Vorgabewert: Mit einer Vorgabe `None` waere eine
    vergessene Aufrufstelle ein stiller Totalausfall der Ortsauflösung; ohne Vorgabe meldet ihn
    `mypy --strict`. `None` heisst hier "liest nur den Bestand und fragt niemanden" und ist der
    Request-Pfad (S10).

    DIE PARTITION IST ALLEIN DAS EVENT. Ein Foto bekommt je Lauf genau eine Rangzeile; es gibt
    keine Kategorie-Ebene und keine Uebersteuerung mehr, und die Motivstaerken bilden
    ausdruecklich keine: eine Staerke ist eine Aussage ueber den Bildinhalt, keine Zugehoerigkeit,
    und keine Schwelle macht daraus eine.

    Weder `commit` noch eigene Transaktionsgrenze - die gehoert dem Aufrufer (Muster
    `project_deletion`)."""
    # DIE KANDIDATENMENGE kommt aus `event_inputs` - derselben Stelle, aus der auch das rein
    # lesende Messkommando sie bezieht (ADR 0117 Punkt 5). Eine zweite, nachbildende Fassung maesse
    # dort etwas anderes, als dieser Lauf tut, waehrend beide fuer sich gruen blieben.
    event_inputs = await read_event_inputs(session, project_id, list(values_by_photo_id))

    # DIE EVENT-BILDUNG. Beim Kriterien-Lauf liegt die Stelle bewusst NACH dem `finally` der
    # Landmark-Phase (sonst fehlten die Namen, die dieser Lauf gerade erst erzeugt hat) und VOR
    # dem Aufbau von `partitions` unten (der Partitionsschluessel IST die `event_id`).
    #
    # `PhotoScore.cluster_key` wird dabei NIE mutiert (Ownership-Grenze): der dort stehende
    # Phase-A-Basiswert bleibt stabil, unabhaengig davon, ob und wann Kriterien-Scoring laeuft.
    # Die Divergenz zu `PhotoRanking.event_id` ist gewollt.
    built_events = build_events(event_inputs.candidates)

    # DIE ORTSNAMEN, zwischen Event-Bildung und Schreiben der Zeilen. Gefragt wird nur fuer Events
    # OHNE Sehenswuerdigkeit: der Ortsname ersetzt sie nicht und tritt nicht daneben - das spart
    # Anfragen und setzt das Akzeptanzkriterium strukturell um.
    cells = {
        cell for built in built_events if built.landmark_name is None for cell in built.place_cells
    }
    info_by_cell = await _place_infos(session, project_id, cells, build_place_resolver)
    place_names = assign_place_names(built_events, info_by_cell)

    event_rows = [
        Event(
            criterion_scoring_run_id=run.id,
            position=built.position,
            started_at=built.started_at,
            ended_at=built.ended_at,
            landmark_name=built.landmark_name,
            place_kind=built.place_kind,
            place_lat=built.place_lat,
            place_lon=built.place_lon,
            place_name=place_name,
        )
        for built, place_name in zip(built_events, place_names, strict=True)
    ]
    session.add_all(event_rows)
    # EIN `flush` fuer alle Events, nicht einer je Event: die Ids werden unten als
    # Partitionsschluessel gebraucht und stehen erst nach dem Schreiben fest.
    await session.flush()
    event_id_by_photo = {
        photo_id: event.id
        for built, event in zip(built_events, event_rows, strict=True)
        for photo_id in built.photo_ids
    }

    # DIE MODELLBEWERTUNG als Grundlage des Qualitaetswerts - gelesen aus der TABELLE, nie aus
    # einer laufinternen Abbildung: der Cloud-Teilschritt ist ein eigener Lauf, und diese Funktion
    # hat auch den zweiten Aufrufer (`rebuild_run_grouping`), der gar keine Cloud-Phase kennt.
    # Ohne Freigabe gibt es keine einzige Zeile, und JEDER Qualitaetswert wird `NULL` - es gibt
    # keinen Rueckfall auf einen lokal gebildeten Wert (ADR 0095, Abschnitt 1).
    level_by_photo_id: dict[int, int] = {
        photo_id: level
        for photo_id, level in (
            await session.execute(
                select(PhotoAlbumSuitability.photo_id, PhotoAlbumSuitability.level).where(
                    PhotoAlbumSuitability.photo_id.in_(values_by_photo_id.keys())
                )
            )
        ).all()
    }

    # DIE GEWICHTE EINMAL JE LAUF, vor der Partitionsschleife - nicht je Foto (Spec 0432): Die
    # geltende Fassung aendert sich waehrend eines Laufs nicht, und ein Lesegang je Foto fiele an
    # keinem Ergebnis auf. Welche Fassung gerechnet hat, haelt die Lauf-Zeile fest; ohne sie ist
    # ein vergangener Rang-Score nach der naechsten Anpassung nicht mehr nachrechenbar. `NULL`
    # heisst dort "Startwerte oder Altzeile".
    weights = await effective_weights(session)
    used_weight_set = await latest_weight_set(session)
    run.quality_weight_set_id = None if used_weight_set is None else used_weight_set.id

    # Eine Partition je Event, ein Foto in genau einer davon.
    partitions: dict[int, dict[int, dict[str, float]]] = {}
    for photo_id, values in values_by_photo_id.items():
        partitions.setdefault(event_id_by_photo[photo_id], {})[photo_id] = values

    for event_id, partition_candidates in partitions.items():
        # `rank_photos` laeuft NUR ueber die bewertete Teilmenge - `rank_position` bleibt dort
        # lueckenlos ab 1. Die uebrigen Fotos der Partition bekommen ihre Zeile unten mit `NULL`
        # in beiden Spalten: sie behalten ihre `event_id`, bleiben im einsehbaren Vorrat und
        # erscheinen nicht im Entwurf.
        quality_scores = {
            photo_id: compute_quality_score(level_by_photo_id[photo_id], values, weights)
            for photo_id, values in partition_candidates.items()
            if photo_id in level_by_photo_id
        }
        ranked_by_photo_id = {ranked.photo_id: ranked for ranked in rank_photos(quality_scores)}
        for photo_id in partition_candidates:
            ranked = ranked_by_photo_id.get(photo_id)
            session.add(
                PhotoRanking(
                    criterion_scoring_run_id=run.id,
                    photo_id=photo_id,
                    event_id=event_id,
                    rank_score=None if ranked is None else ranked.rank_score,
                    rank_position=None if ranked is None else ranked.rank_position,
                )
            )

    # DER AUSWAHLVORSCHLAG ist die FORTSETZUNG dieses Schritts, kein eigener Teilschritt: er
    # haengt unmittelbar hinter den Rangzeilen und innerhalb der bestehenden Phase `RANKING` -
    # kein neuer `ClassificationPhase`-Wert, keine neue Fortschrittsstufe in der Oberflaeche.
    # Damit sind beide Aufrufer dieser Funktion abgedeckt (Kriterien-Lauf und Neuaufbau nach
    # einer Versatz-Aenderung).
    #
    # Das `flush` davor: `_apply_run_selection` liest die Rangzeilen aus der Datenbank, und die
    # eben hinzugefuegten stehen dort erst danach.
    await session.flush()
    await _apply_run_selection(session, run, project_id)


async def _apply_run_selection(
    session: AsyncSession, run: CriterionScoringRun, project_id: int
) -> None:
    """Der Auswahlvorschlag DIESES Laufs: auswahlfaehige Kandidaten laden, die reine Funktion
    rufen, `selection_position` schreiben.

    DIE EINE Rechenstelle fuer alle drei Ausloeser (Kriterien-Lauf, Neuaufbau nach einer
    Versatz-Aenderung, Aenderung des Richtwerts). Ein zweiter Rechenweg liefe auseinander.

    AUSWAHLFAEHIG ist eine Rangzeile dieses Laufs mit `rank_score IS NOT NULL` und ohne
    `excluded_document` am Foto. Der zweite Teil ist die fortgeschriebene Zusage aus ADR 0091
    Punkt 2: ein als Dokument oder Bildschirmabbild erkanntes Foto erscheint in keiner
    Motivauswahl, und der Vorschlag ist eine - es zaehlt deshalb auch nicht als Motivtraeger und
    lenkt die Vergabe nicht um.

    SICHERHEIT (S2): `PhotoRanking` traegt keine `project_id` - die Lauf-Id ist die einzige
    Projektbindung. `criterion_scoring_run_id == run.id` steht deshalb AUSGESCHRIEBEN in jeder
    lesenden und jeder schreibenden Anweisung hier. Fehlte es auch nur in der Schreibanweisung,
    setzte ein Aufruf unter Projekt A `selection_position` auf Rangzeilen eines fremden Laufs -
    ein kohaerenter, aber fremder Vorschlag, dem die Antwort nichts ansieht.

    SICHERHEIT (S8): `user_id` fliesst in keine Abfrage und in keine Schreibanweisung. Der
    Vorschlag ist lauf-global; eine je Nutzer verschiedene Position entsteht nicht.

    Weder `commit` noch eigene Transaktionsgrenze - die gehoert dem Aufrufer."""
    project = await session.get(Project, project_id)
    if project is None:
        return

    # ZURUECKSETZEN ZUERST, und zwar ueber den gesamten Lauf: ein Foto, das im vorigen Vorschlag
    # stand und im neuen nicht mehr, behielte sonst seinen alten Platz.
    await session.execute(
        update(PhotoRanking)
        .where(PhotoRanking.criterion_scoring_run_id == run.id)
        .values(selection_position=None)
    )

    rows = (
        await session.execute(
            select(
                PhotoRanking.photo_id,
                PhotoRanking.event_id,
                PhotoRanking.rank_score,
                Event.position,
                Photo.taken_at,
            )
            .join(Event, Event.id == PhotoRanking.event_id)
            .join(Photo, Photo.id == PhotoRanking.photo_id)
            .where(
                PhotoRanking.criterion_scoring_run_id == run.id,
                Event.criterion_scoring_run_id == run.id,
                Photo.project_id == project_id,
                PhotoRanking.rank_score.is_not(None),
            )
        )
    ).all()
    if not rows:
        return

    candidate_ids = [photo_id for photo_id, _event_id, _score, _position, _taken_at in rows]
    excluded = set(
        (
            await session.execute(
                select(PhotoMotifAssessment.photo_id).where(
                    PhotoMotifAssessment.photo_id.in_(candidate_ids),
                    PhotoMotifAssessment.excluded_document.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    eligible_ids = [photo_id for photo_id in candidate_ids if photo_id not in excluded]
    # Die WIRKSAMEN Staerken, Korrekturen inbegriffen - nie die rohe Staerkezeile.
    strengths_by_photo_id = await load_effective_strengths(session, eligible_ids)

    candidates_by_event: dict[int, list[SelectionCandidate]] = {}
    position_by_event: dict[int, int] = {}
    for photo_id, event_id, rank_score, position, taken_at in rows:
        if photo_id in excluded:
            continue
        position_by_event[event_id] = position
        candidates_by_event.setdefault(event_id, []).append(
            SelectionCandidate(
                photo_id=photo_id,
                taken_at=taken_at,
                quality=rank_score,
                motif_strengths={
                    motif_key: effective.strength
                    for motif_key, effective in strengths_by_photo_id.get(photo_id, {}).items()
                },
            )
        )

    photo_count = (
        await session.execute(
            select(func.count()).select_from(Photo).where(Photo.project_id == project_id)
        )
    ).scalar_one()

    draft = select_album_draft(
        [
            SelectionEvent(
                event_id=event_id,
                position=position_by_event[event_id],
                candidates=candidates,
            )
            for event_id, candidates in candidates_by_event.items()
        ],
        effective_target(project.selection_target, photo_count),
    )
    if not draft:
        return

    # Je PLATZ eine Anweisung statt je Foto: die Zahl der Anweisungen ist damit die groesste
    # Platzzahl eines Events und nicht die Groesse des Vorschlags.
    photo_ids_by_place: dict[int, list[int]] = {}
    for photo_id, place in draft.items():
        photo_ids_by_place.setdefault(place, []).append(photo_id)
    for place, photo_ids in sorted(photo_ids_by_place.items()):
        await session.execute(
            update(PhotoRanking)
            .where(
                PhotoRanking.criterion_scoring_run_id == run.id,
                PhotoRanking.photo_id.in_(sorted(photo_ids)),
            )
            .values(selection_position=place)
        )


async def _latest_successful_criterion_run(
    session: AsyncSession, project_id: int
) -> CriterionScoringRun | None:
    return (
        await session.execute(
            select(CriterionScoringRun)
            .where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
            )
            .order_by(CriterionScoringRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def rebuild_run_selection(session: AsyncSession, project_id: int) -> None:
    """Rechnet NUR den Auswahlvorschlag des letzten erfolgreichen Kriterien-Laufs neu - aus
    persistierten Zeilen, ohne Cloud-Aufruf und ohne Bildverarbeitung.

    Aufgerufen vom Richtwert-Endpunkt. Events und Rangzeilen bleiben dabei unangetastet: der
    Richtwert aendert, wie viele Plaetze wohin gehen, nicht die Gliederung und nicht die
    Rangfolge.

    Kein erfolgreicher Lauf: nichts zu tun. Weder `commit` noch eigene Transaktionsgrenze - die
    gehoert dem Aufrufer (Muster `rebuild_run_grouping`)."""
    run = await _latest_successful_criterion_run(session, project_id)
    if run is None:
        return
    await _apply_run_selection(session, run, project_id)


async def rebuild_run_grouping(session: AsyncSession, project_id: int) -> None:
    """Baut Gliederung und Rangzeilen des LETZTEN ERFOLGREICHEN Kriterien-Laufs neu auf -
    ausschliesslich aus bereits persistierten Werten, ohne Cloud-Aufruf und ohne Bildverarbeitung.

    Aufgerufen vom Versatz-Endpunkt: Reihenfolge, Anzeige und Ortsherleitung sind mit der
    Bedeutungsumkehr von `taken_at` sofort richtig, die EVENTS sind dagegen persistierte
    Lauf-Artefakte (ADR 0087) und waeren es nicht.

    LOESCHEN UND NEUSCHREIBEN statt Umhaengen: `UniqueConstraint(criterion_scoring_run_id,
    position)` laesst alte und neue Events desselben Laufs nicht gleichzeitig zu.

    Kein erfolgreicher Lauf oder keine einzige Rangzeile: nichts zu tun. Weder `commit` noch
    eigene Transaktionsgrenze - die gehoert dem Aufrufer, der genau EINMAL committet (Muster
    `project_deletion`)."""
    run = await _latest_successful_criterion_run(session, project_id)
    if run is None:
        return

    # Die Kandidatenmenge des Laufs sind genau die Fotos seiner Rangzeilen - nicht die aktuellen
    # Ausschuss-Ueberlebenden: ein zwischenzeitliches Re-Scoring darf die Zusammensetzung dieses
    # Laufs nicht nachtraeglich veraendern.
    candidate_ids = set(
        (
            await session.execute(
                select(PhotoRanking.photo_id).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    if not candidate_ids:
        return

    values_by_photo_id: dict[int, dict[str, float]] = {}
    criterion_rows = (
        await session.execute(
            select(
                PhotoCriterionScore.photo_id,
                PhotoCriterionScore.criterion_key,
                PhotoCriterionScore.value,
            ).where(PhotoCriterionScore.photo_id.in_(candidate_ids))
        )
    ).all()
    for photo_id, criterion_key, value in criterion_rows:
        values_by_photo_id.setdefault(photo_id, {})[criterion_key] = value
    # Ein Kandidat ohne einen einzigen Kriterien-Wert bleibt Kandidat: er stand in einer Rangzeile
    # des Laufs und muss auch danach in einer stehen.
    for photo_id in sorted(candidate_ids):
        values_by_photo_id.setdefault(photo_id, {})

    await session.execute(
        delete(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
    )
    await session.execute(delete(Event).where(Event.criterion_scoring_run_id == run.id))
    # Das `flush` VOR dem Neuaufbau: sonst kollidieren die neuen Events mit den alten am
    # Unique-Constraint ueber `(Lauf, position)`.
    await session.flush()

    # `None` STATT EINES AUFLOESERS (S10): Dieser Pfad laeuft in einem Request (Versatz-Endpunkt).
    # Er baut die Namen ausschliesslich aus bereits abgelegten Auskuenften neu und fragt niemanden;
    # eine noch nie gefragte Zelle bleibt hier ohne Namen, bis der naechste Kriterien-Lauf sie
    # beschafft. Ohne diese Grenze koennte ein Request-Pfad nach aussen wirken.
    await _build_grouping_and_rankings(session, run, project_id, values_by_photo_id, None)


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
    build_landmark_client: Callable[[str], LandmarkClientLike] = build_landmark_client,
    build_place_resolver: PlaceResolverFactory = build_place_resolver,
    build_embedder: Callable[[], LabelEmbedderLike] = build_label_embedder,
    *,
    run: CriterionScoringRun | None = None,
    use_cloud: bool = False,
) -> CriterionScoringRun:
    """Berechnet Kriterien-Werte fuer alle Ausschuss-Ueberlebenden eines Projekts und die daraus
    abgeleitete Rangfolge je Partition (event_id). Ablauf:
    CriterionScoringRun
    anlegen -> Guard (scoring_run_id muss der aktuell neueste erfolgreiche ScoringRun sein) ->
    Kriterien je Foto berechnen (sharpness/exposure immer, Inhalts-Kriterien best-effort, periodisch
    zwischen-committet) -> rank_photos je Partition anwenden (reine In-Memory-Aggregation ueber die
    in diesem Lauf berechneten Werte) -> PhotoRanking-Zeilen schreiben -> CriterionScoringRun auf
    success/failed setzen. `build_detector`/`build_animal_detector`/`build_classifier`/
    `build_aesthetics`/`build_landmarker` sind injizierbar (Default: die echte, teure
    Modellkonstruktion) - Tests uebergeben stattdessen Fakes ohne echtes Modell
    (build_object_detector/build_scene_classifier/build_aesthetics_model/
    build_face_landmarker dürfen wie build_face_detector NIE in einem automatisierten Test
    aufgerufen werden).

    Dies ist die ZWEITE Phase eines verketteten Klassifizierungslaufs, kein eigenständig
    ausgelöster Lauf. Zwei keyword-only Parameter:

    - `run`: der bereits von run_classification angelegte Lauf-Datensatz. Wird keiner uebergeben,
      legt diese Funktion ihn selbst an (Direktaufruf, z.B. in Tests).
    - `use_cloud`: laufbezogene Cloud-Freigabe (die Checkbox am Ausloeser). Das Gate fuer die
      Landmark-Phase ist ab hier die KONJUNKTION `use_cloud and
      project.cloud_vision_detection_enabled` - `use_cloud` kann eine fehlende Einwilligung nie
      ersetzen, nur eine vorhandene fuer diesen einen Lauf ungenutzt lassen.
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
    _set_phase(run, ClassificationPhase.CRITERIA)
    await session.commit()

    try:
        latest_scoring_run = (
            (
                await session.execute(
                    select(ScoringRun)
                    .where(ScoringRun.project_id == project.id)
                    .order_by(ScoringRun.started_at.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if (
            latest_scoring_run is None
            or latest_scoring_run.status != ScanStatus.SUCCESS
            or latest_scoring_run.id != scoring_run_id
        ):
            raise CriterionScoringGuardError(
                "scoring_run_id entspricht nicht mehr dem aktuell neuesten erfolgreichen "
                "Scoring-Lauf (Re-Scan/Re-Scoring waehrend der Kuratierung)."
            )

        # Bekannter, akzeptierter Performance-Trade-off: HIER gibt es bewusst KEINEN
        # Kandidatenpool-Vorfilter pro Cluster - N ist beim Scoren nicht bekannt (es wird erst beim
        # Lesen ueber top_n_per_event angewendet), also werden ALLE Ausschuss-Ueberlebenden
        # verarbeitet, nicht nur die aussichtsreichsten. Fuer sehr grosse Projekte potenziell
        # spuerbar, siehe docs/architecture.md.
        rows = (
            await session.execute(
                select(Photo, PhotoScore)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.project_id == project.id, survives_ausschuss())
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

        # Jeder Modell-Builder bekommt ueber _try_build sein eigenes try/except, KEINER laeuft
        # ungeschuetzt: ein Fehlschlag eines einzelnen Builders (fehlendes/defektes
        # .tflite-/.hdf5-Asset, mediapipe-/tensorflow-Laufzeitproblem) markierte sonst den GESAMTEN
        # Lauf als FAILED, obwohl die Kriterien pro Foto bewusst best-effort behandelt werden.
        # Schlaegt einer fehl, bleibt der zugehoerige Detektor/Klassifikator/das Modell None,
        # _compute_content_criteria ueberspringt dann NUR die davon abhaengigen Kriterien (siehe
        # dortige `if ... is not None`-Wächter) - sharpness/exposure und alle anderen, unabhaengig
        # berechenbaren Kriterien werden trotzdem geschrieben.
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

        async def _delete_criterion(photo_id: int, criterion_key: str) -> None:
            """Loescht die Zeile eines NICHT MESSBAREN Kriteriums - ausschliesslich fuer
            `ContentCriteria.not_measurable`, nie fuer ein mangels Detektor oder wegen einer
            Ausnahme unberechnetes.

            Ohne dieses Loeschen liefe die Entscheidung "ein nicht messbares Kriterium wird
            weggelassen" fuer den BESTAND ins Leere: `_upsert_criterion` loescht nie, und die
            Altzeile mit ihrem alten `0.0` bliebe wirksam.

            Der In-Memory-Cache wird MITgeraeumt: bliebe das ORM-Objekt darin stehen, belebte ein
            spaeteres `_upsert_criterion` im selben Lauf eine geloeschte Zeile wieder, und der
            naechste Lauf faende einen Eintrag vor, den es in der Datenbank nicht mehr gibt."""
            existing = existing_criterion_scores.pop((photo_id, criterion_key), None)
            if existing is not None:
                await session.delete(existing)

        # photo_id -> {criterion_key: value}, nur die in DIESEM Lauf erfolgreich berechneten
        # Werte (reine In-Memory-Grundlage fuer rank_photos unten, kein erneutes DB-Read noetig).
        candidate_values: dict[int, dict[str, float]] = {}
        # photo_id -> {criterion_key: Flaechenanteil}. Ebenfalls rein in-memory und ebenfalls
        # AUSSCHLIESSLICH fuer diesen Lauf: die Anteile werden nirgends persistiert, und ohne sie
        # koennte die Kopfzeile unten nicht entstehen (ein spaeterer Neuaufbau der Gliederung hat
        # sie deshalb nicht und schreibt auch keine Kopfzelle).
        area_fractions_by_photo_id: dict[int, dict[str, float]] = {}
        processed = 0
        for photo, score in rows:
            values: dict[str, float] = {}

            sharpness_value = normalize_sharpness(score.sharpness)
            _upsert_criterion(
                photo.id, "sharpness", sharpness_value, CriterionSource.LOCAL_HEURISTIC
            )
            values["sharpness"] = sharpness_value

            exposure_value = normalize_exposure(score.exposure)
            _upsert_criterion(photo.id, "exposure", exposure_value, CriterionSource.LOCAL_HEURISTIC)
            values["exposure"] = exposure_value

            # KEIN assert-is-not-None hier: jeder der fuenf Builder oben ist ueber _try_build
            # best-effort abgesichert und kann legitim None sein - _compute_content_criteria
            # ueberspringt die davon abhaengigen Kriterien dann selbst, statt dass ein
            # fehlgeschlagener Builder den gesamten Lauf abbricht.
            content = _compute_content_criteria(
                cache_dir,
                photo,
                detector,
                animal_detector,
                scene_classifier,
                aesthetics_model,
                face_landmarker,
            )
            for criterion_key, source in _IMAGE_ANALYSIS_CRITERION_SOURCES.items():
                if criterion_key in content.values:
                    _upsert_criterion(
                        photo.id, criterion_key, content.values[criterion_key], source
                    )
                    values[criterion_key] = content.values[criterion_key]

            # NUR `not_measurable` - "die Detektion lief, das Merkmal fehlt". Ein mangels
            # Detektor oder wegen einer Ausnahme unberechnetes Kriterium steht dort nicht und
            # behaelt seine Altzeile.
            for criterion_key in content.not_measurable:
                await _delete_criterion(photo.id, criterion_key)

            candidate_values[photo.id] = values
            area_fractions_by_photo_id[photo.id] = content.area_fractions

            processed += 1
            if processed % CRITERION_SCORING_COMMIT_BATCH_SIZE == 0:
                run.photos_processed = processed
                # Fortschritts-Watchdog (Schicht 2) - analog run_project_scan oben.
                run.last_progress_at = _now_utc()
                await session.commit()

        run.photos_processed = processed
        await session.commit()

        # Die Cloud-Phase laeuft NACH der obigen (rein lokalen/synchronen) Foto-Schleife und VOR
        # der Kategorieableitung/rank_photos, damit landmark-Werte noch in die
        # Kategorie-/Rangfolgenbildung einfliessen können. `project.cloud_vision_detection_enabled`
        # wird hier EINMALIG gelesen (kein Live-Reread während des Laufs, dokumentierte
        # Vereinfachung).
        #
        # SICHERHEIT - das Gate ist die KONJUNKTION aus projektweiter Einwilligung UND
        # laufbezogener `use_cloud`-Freigabe: fehlt eine der beiden, wird
        # build_landmark_client GAR NICHT ERST aufgerufen - keine Netzwerkverbindung, kein
        # API-Key nötig, kein Byte verlässt den Server, kein einziger Cloud-Aufruf im
        # gesamten Durchlauf.
        if use_cloud and project.cloud_vision_detection_enabled and rows:
            # Die Sehenswuerdigkeits-Erkennung ist ein EIGENER, benannter Teilschritt, kein
            # unsichtbarer Teil der Kriterien-Phase: bliebe `phase` hier auf `criteria`, waehrend
            # `photos_processed` bereits auf `photos_total` steht, waere ein langer Durchlauf von
            # einem haengengebliebenen nicht zu unterscheiden.
            _set_phase(run, ClassificationPhase.LANDMARK)
            await session.commit()
            # Das Modell wird EINMAL je Cloud-Phase aufgeloest und danach durchgereicht - derselbe
            # lokale Wert baut den Client, rechnet die Ist-Kosten und landet in der Modellspalte des
            # Laufs. "Angezeigt = abgerechnet = tatsaechlich aufgerufen" ist damit strukturell wahr,
            # nicht das Ergebnis dreier zufaellig gleicher Lesevorgaenge derselben globalen
            # `settings`.
            landmark_model = settings.resolved_landmark_model()
            landmark_client = _try_build(lambda: build_landmark_client(landmark_model))
            if landmark_client is None:
                # Ein nicht konstruierbarer Client laesst die Sehenswuerdigkeits-Erkennung aus -
                # das gehoert VERBINDLICH in die laufweite Cloud-Fehlermeldung, sonst bliebe der
                # Fall stumm.
                _append_cloud_error(
                    run,
                    "Sehenswuerdigkeits-Erkennung nicht verfuegbar (Initialisierung "
                    "fehlgeschlagen).",
                )
            if landmark_client is not None:
                # Die Modellspalte wird am PHASENANFANG committet, nicht erst im `finally` - es ist
                # derselbe lokale Wert, der den Client gebaut hat und gleich die Kosten rechnen
                # wird, nur frueher sichtbar, damit die Oberflaeche schon WAEHREND des Teilschritts
                # sagen kann, wohin die Aufrufe gehen. Der BETRAG bleibt im `finally` und am
                # Phasenende eingefroren.
                run.landmark_model = landmark_model
                await session.commit()
                # Zählerstand des ANBIETERWEITEN Schrittmachers beim Betreten des Teilschritts. Die
                # Zusammenfassung unten entsteht ausschliesslich aus der DIFFERENZ zu diesem
                # Schnappschuss - die Zaehler selbst sind prozessweit und enthalten auch die
                # Wartezeiten des jeweils anderen Cloud-Teilschritts und paralleler Laeufe.
                landmark_throttle = throttle_for_provider(settings.landmark_provider)
                landmark_throttle_before = landmark_throttle.stats()
                landmark_failures = 0
                landmark_attempts = 0
                # Der laufend fortgeschriebene Fortschritt der Phase, streng getrennt von der
                # Kosten-Buchfuehrung unten.
                landmark_processed = 0
                # Ist-Kosten-Buchführung dieser Phase. Summiert wird über die ERFOLGREICHEN
                # Ergebnisse - ein fehlgeschlagener Aufruf liefert keinen auswertbaren Verbrauch
                # (dokumentierte Untererfassung).
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
                    # Die Live-Zaehler werden beim BETRETEN der Phase auf `0` gesetzt, nicht bei
                    # der Zeilenanlage - `NULL` bleibt damit die Aussage "diesen Teilschritt gab es
                    # in diesem Lauf nicht", `0` heisst "gab es, nichts zu tun".
                    # `landmark_photos_total` ist zugleich der Marker, an dem die
                    # API entscheidet, ob dieser Lauf einen Landmark-Eintrag in `cloud_phases`
                    # bekommt - er muss deshalb schon VOR dem ersten Aufruf dastehen, sonst saehe
                    # die Oberflaeche den Teilschritt genau dann nicht, wenn er laeuft.
                    run.landmark_photos_total = landmark_attempts
                    run.landmark_photos_processed = 0
                    run.landmark_failed_calls = 0
                    await session.commit()

                    # DIE ORTSAUSKUNFT, VOR der Blockschleife und in EINEM Zug fuer alle
                    # Kandidaten - nicht je Foto: derselbe Auflöser, dieselbe Tabelle, ein
                    # Durchgang durch den Ortsdatensatz statt einem je Aufnahme. Die Event-Phase
                    # findet ihre Zellen danach ueberwiegend bereits abgelegt vor und baut dann gar
                    # keinen Auflöser mehr (ADR 0106, Konsequenzen).
                    #
                    # Ausschliesslich die EIGENE gemessene Koordinate des Fotos (S3):
                    # `infer_locations` wird hier nicht aufgerufen, und ein Syntaxbaum-Waechter in
                    # tests/test_worker_criterion_scoring.py haelt das fest - ein hinzugefuegter
                    # Aufruf roetet sonst keinen Verhaltenstest, solange die Messlage echte
                    # Koordinaten traegt.
                    landmark_candidate_photos = [
                        photos_by_id[photo_id] for photo_id in landmark_candidate_ids
                    ]
                    landmark_place_infos = await _place_infos(
                        session,
                        project.id,
                        _landmark_place_cells(landmark_candidate_photos),
                        build_place_resolver,
                    )
                    landmark_hints = _landmark_place_hints(
                        landmark_candidate_photos, landmark_place_infos
                    )
                    await session.commit()

                    # DAS NAMENSREGISTER dieses Projekts, einmal je Lauf geladen und danach
                    # mutierbar durchgereicht (Muster `run_remote_category_classification`): Ein
                    # in diesem Lauf neu entstandener Eintrag ergaenzt den Schnappschuss sofort,
                    # sodass ein zweiter aehnlicher Name im selben Lauf auf ihn trifft statt eine
                    # zweite Zeile anzulegen.
                    #
                    # SICHERHEIT (S8): Die Bindung an `project.id` steht in der Abfrage
                    # ausgeschrieben, und es gibt keinen Rueckfall auf das Register eines anderen
                    # Projekts - ein solcher Rueckfall fuehrte die Reisen verschiedener Projekte
                    # zusammen.
                    #
                    # Der Einbetter ist BEST-EFFORT: Ohne ihn entsteht kein kanonischer Name und
                    # kein Registereintrag, der Lauf laeuft unveraendert durch, und jede
                    # Erkennungszeile verhaelt sich wie vor dem Register (sie faellt auf ihren
                    # Rohnamen zurueck). Gebaut wird er erst HIER, innerhalb der Landmark-Phase -
                    # `rebuild_run_grouping` erreicht diese Stelle nie und laedt deshalb kein
                    # 113-MB-Modell in einen Anfragepfad (S10).
                    #
                    # UND NUR, WENN ES UEBERHAUPT KANDIDATEN GIBT: Die Phase wird auch dann
                    # betreten, wenn `_select_landmark_candidates` alles herausgefiltert hat (ein
                    # zweiter Lauf ueber ein bereits vollstaendig gescortes Projekt) - dann laeuft
                    # die Blockschleife null Mal, und ein geladenes 113-MB-Modell waere Arbeit
                    # ohne Gegenwert. Dieselbe Begruendung wie beim `_place_infos` daneben.
                    landmark_embedder = (
                        _try_build(build_embedder) if landmark_candidate_ids else None
                    )
                    # Der Schnappschuss haengt am Einbetter und nicht umgekehrt: Ohne ihn wird er
                    # nie gelesen, und die Abfrage waere derselbe Leerlauf.
                    landmark_register: list[LandmarkNameEntry] = []
                    if landmark_embedder is not None:
                        landmark_register = [
                            LandmarkNameEntry(
                                normalized_name=row.normalized_name,
                                display_name=row.display_name,
                                embedding=list(row.embedding),
                                locality=row.locality,
                                id=row.id,
                            )
                            for row in (
                                await session.execute(
                                    select(LandmarkName).where(
                                        LandmarkName.project_id == project.id
                                    )
                                )
                            )
                            .scalars()
                            .all()
                        ]

                    for start in range(0, len(landmark_candidate_ids), landmark_concurrency):
                        block_ids = landmark_candidate_ids[start : start + landmark_concurrency]
                        results = await asyncio.gather(
                            *[
                                _detect_landmark_for_photo(
                                    landmark_client,
                                    cache_dir,
                                    photos_by_id[photo_id],
                                    landmark_hints[photo_id],
                                )
                                for photo_id in block_ids
                            ],
                            return_exceptions=True,
                        )
                        # Derselbe Async-Fallstrick wie in _process_scan_block: ein CancelledError
                        # einer einzelnen Kind-Coroutine wird von return_exceptions=True sonst als
                        # gewoehnliches Ergebniselement durchgereicht statt propagiert.
                        for result in results:
                            if isinstance(result, asyncio.CancelledError):
                                raise result
                        for photo_id, result in zip(block_ids, results, strict=True):
                            if isinstance(result, BaseException):
                                # Best-effort: ein einzelner fehlgeschlagener Cloud-Aufruf
                                # (Timeout, 4xx/5xx, fehlender Cache-Eintrag) laesst fuer dieses
                                # Foto keine landmark-Zeile entstehen, alle anderen Kriterien
                                # dieses Fotos bleiben unberuehrt, kein Laufabbruch. Dennoch
                                # sichtbar über docker compose logs. type(exc).__name__/str(exc)
                                # GENAU EINMAL berechnet, an beide Senken (Logger, DB)
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
                                # Dauerhafte, per API abrufbare Persistenz desselben Fehlschlags
                                # (getrennt vom Log oben).
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
                            # Verbindlich: jeder STATTGEFUNDENE Aufruf wird gezaehlt,
                            # auch wenn sein `usage`-Block fehlte - der Tokenbeitrag ist dann 0.
                            # Sonst entstuende die stille Kombination "api_calls == 0 bei real
                            # erfolgten Aufrufen", und `api_calls > 0` ist zugleich der Ausloeser
                            # fuer Befund (b) des Unvollstaendigkeits-Hinweises.
                            landmark_api_calls += 1
                            if detection.usage is not None:
                                landmark_input_tokens += detection.usage.input_tokens
                                landmark_output_tokens += detection.usage.output_tokens
                            landmark_value = compute_landmark_score(detection)
                            _upsert_criterion(
                                photo_id, "landmark", landmark_value, CriterionSource.CLOUD
                            )
                            candidate_values[photo_id]["landmark"] = landmark_value
                            # "Aufräumen bei Erfolg": ein erfolgreicher
                            # (Retry-)Versuch loescht eine ggf. vorhandene Fehler-Zeile.
                            await _clear_cloud_vision_error(
                                session, photo_id, CloudVisionPhase.LANDMARK
                            )
                            if detection.name is not None:
                                # DIE KANONISIERUNG, und nur OBERHALB DER GRENZE: Ein unsicherer
                                # und wahrscheinlich falscher Name soll nicht die Anzeigeform eines
                                # Registereintrags besetzen, dem sich spaeter der richtige
                                # anschliesst (ADR 0107 Punkt 5). Ohne Einbetter entsteht kein
                                # kanonischer Name - kein Fehlerfall.
                                #
                                # `name` und `confidence` gehen dagegen UNGEFILTERT in die Zeile:
                                # Die Antwort ist bezahlt und bleibt vollstaendig erhalten.
                                canonical_name: str | None = None
                                if (
                                    landmark_embedder is not None
                                    and detection.confidence >= LANDMARK_CONFIDENCE_THRESHOLD
                                ):
                                    # Die SPERRE ist der aufgeloeste Ortsname dieses Fotos - genau
                                    # die Namensstufe des Hinweises, nie die Koordinatenstufe: Eine
                                    # Zelle von rund 11 km ist als Unterscheidungsmerkmal zweier
                                    # Sehenswuerdigkeiten zu grob.
                                    hint = landmark_hints[photo_id]
                                    entry = resolve_canonical_landmark(
                                        detection.name,
                                        hint.locality if hint is not None else None,
                                        landmark_register,
                                        landmark_embedder,
                                    )
                                    if entry.id is None:
                                        register_row = LandmarkName(
                                            project_id=project.id,
                                            normalized_name=entry.normalized_name,
                                            display_name=entry.display_name,
                                            embedding=entry.embedding,
                                            locality=entry.locality,
                                        )
                                        session.add(register_row)
                                        await session.flush()
                                        # Die `id` NACHSETZEN, auf genau der Instanz im
                                        # Schnappschuss - sonst legte derselbe Eintrag beim
                                        # naechsten Treffer eine zweite Zeile an und verletzte
                                        # `UniqueConstraint(project_id, normalized_name)`.
                                        entry.id = register_row.id
                                    canonical_name = entry.display_name
                                await _upsert_landmark_detection(
                                    session,
                                    photo_id,
                                    detection,
                                    now,
                                    settings.landmark_provider,
                                    canonical_name,
                                )

                        # Fortgeschrieben wird AM BLOCKENDE, nie beim Betreten des Blocks: sonst
                        # stuende nach einem Abbruch mitten im Block ein `processed` da, dem weder
                        # ein Aufruf noch ein Fehlschlag gegenuebersteht (Invariante
                        # `photos_processed == api_calls + failed_calls`).
                        #
                        # `last_progress_at` gehoert VERBINDLICH dazu. Bleibt der Zeitstempel in
                        # dieser Phase unberuehrt, setzt `reap_stalled_runs` einen Lauf mit mehr
                        # als STALL_THRESHOLD (15 min) Landmark-Arbeit auf FAILED - OHNE die
                        # Coroutine abzubrechen. Der Lauf ruft danach unveraendert weiter
                        # kostenpflichtig beim Anbieter an, waehrend die Oberflaeche
                        # "fehlgeschlagen" sagt, und die Kostenerfassung des `finally` schreibt
                        # ihren Betrag auf eine bereits als gescheitert ausgewiesene Zeile.
                        landmark_processed += len(block_ids)
                        run.landmark_photos_processed = landmark_processed
                        run.landmark_failed_calls = landmark_failures
                        run.last_progress_at = _now_utc()
                        await session.commit()
                finally:
                    aclose = getattr(landmark_client, "aclose", None)
                    if aclose is not None:
                        await aclose()
                    # VERBINDLICH im finally, nicht erst vor `status = SUCCESS`: ein Lauf, der nach
                    # der Cloud-Phase in der Kriterien-Phase scheitert, hat das Geld bereits
                    # ausgegeben. Ohne das Schreiben hier verloere er den real angefallenen Betrag
                    # - und waere wegen `0` statt `NULL` nicht einmal als Luecke erkennbar. Das
                    # Commit ist ebenfalls noetig: der Fehlerpfad laeuft ueber _fail_run, das mit
                    # einem rollback() beginnt.
                    run.landmark_api_calls = landmark_api_calls
                    run.landmark_input_tokens = landmark_input_tokens
                    run.landmark_output_tokens = landmark_output_tokens
                    # Der Betrag wird EINMAL am Phasenende berechnet und eingefroren - eine spaetere
                    # Preisaenderung schreibt die Vergangenheit nicht um.
                    run.landmark_cost_usd = compute_cost_usd(
                        landmark_model,
                        TokenUsage(
                            input_tokens=landmark_input_tokens,
                            output_tokens=landmark_output_tokens,
                        ),
                    )
                    # `run.landmark_model` - die Preisgrundlage des eben eingefrorenen Betrags -
                    # steht bereits vom PHASENANFANG her da und ist derselbe lokale
                    # `landmark_model`, aus dem hier der Betrag entsteht. Deshalb KEINE zweite
                    # Zuweisung an dieser Stelle.
                    await _commit_phase_costs(session)
                # Höchstens eine Zeile, und nur wenn in DIESEM Teilschritt tatsaechlich gewartet
                # wurde.
                _log_cloud_vision_throttling(
                    "landmark",
                    settings.landmark_provider,
                    landmark_throttle.stats().since(landmark_throttle_before),
                )
                # Zähl-Zusammenfassung statt N Einzelmeldungen - die Einzelfehler bleiben pro
                # Foto über photo_cloud_vision_errors abrufbar, das hier ist die Laufebene.
                if landmark_failures > 0:
                    _append_cloud_error(
                        run,
                        f"Sehenswuerdigkeits-Erkennung: {landmark_failures} von "
                        f"{landmark_attempts} Fotos fehlgeschlagen.",
                    )

        # DIE LOKALE MOTIV-KOPFZEILE. Ihre Stelle ist NACH der Landmark-Phase, und das ist keine
        # Kosmetik: `bauwerk_sehenswuerdigkeit` ist lokal `max(Szenen-Konfidenz,
        # Sehenswuerdigkeits-Konfidenz)`, und der zweite Wert entsteht erst dort. Vor der Phase
        # geschrieben fehlte der gerade bezahlte Beitrag im Vektor.
        #
        # `upsert_assessment` setzt die Regel selbst durch: eine vorhandene Cloud-Grundlage bleibt
        # unberuehrt, eine lokale wird ersetzt. `excluded_document` ist hier immer `False` - den
        # Ausschluss beantwortet allein das Modell, die lokale Erkennung hat dazu keine Aussage.
        for photo_id, criterion_values in candidate_values.items():
            await upsert_assessment(
                session,
                photo_id,
                source=MotifAssessmentSource.LOCAL,
                strengths=local_motif_strengths(
                    criterion_values, area_fractions_by_photo_id.get(photo_id, {})
                ),
                excluded_document=False,
                provider=None,
                computed_at=now,
            )
        await session.commit()

        # Der RANKING-Teilschritt (Kategorieableitung + rank_photos je Partition + Schreiben der
        # PhotoRanking-Zeilen). Er gehoert fachlich zur Kriterien-Phase, laeuft aber NACH der
        # Landmark-Phase und braucht deshalb einen eigenen Namen: sonst bliebe `phase` hier auf
        # `landmark` bei 100 % Fortschritt stehen ("haengt oder laeuft?") oder muesste auf
        # `criteria` zurueckspringen. Der vierte Wert macht die Abfolge monoton.
        _set_phase(run, ClassificationPhase.RANKING)
        await session.commit()

        await _build_grouping_and_rankings(
            session, run, project.id, candidate_values, build_place_resolver
        )

        run.status = ScanStatus.SUCCESS
        _set_phase(run, None)
        run.finished_at = _now_utc()
        await session.commit()
        return run
    except asyncio.CancelledError:
        # Schicht 1 des Fortschritts-Watchdogs - analog run_project_scan/run_project_scoring oben.
        await _fail_run(session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown).")
        raise
    except Exception as exc:
        # Kein Rollback bereits committeter Fortschritts-/Kriterien-Zwischenstaende - identisches
        # Muster wie run_project_scoring oben.
        await _fail_run(session, run, str(exc))
        return run


async def run_classification(
    session: AsyncSession,
    project: Project,
    scoring_run_id: int,
    cache_dir: Path,
    *,
    use_cloud: bool,
    estimated_cost_usd: float | None = None,
    build_detector: Callable[[], FaceDetectorLike] = build_face_detector,
    build_animal_detector: Callable[[], ObjectDetectorLike] = build_object_detector,
    build_classifier: Callable[[], SceneClassifierLike] = build_scene_classifier,
    build_aesthetics: Callable[[], AestheticsModelLike] = build_aesthetics_model,
    build_landmarker: Callable[[], FaceLandmarkerLike] = build_face_landmarker,
    build_landmark_client: Callable[[str], LandmarkClientLike] = build_landmark_client,
    build_category_client: Callable[
        [str], CategoryDetectionClientLike
    ] = build_category_classification_client,
    build_embedder: Callable[[], LabelEmbedderLike] = build_label_embedder,
) -> CriterionScoringRun:
    """Der EINE, verkettete Klassifizierungslauf:

        Phase "remote_categories" (nur bei aktiver Cloud-Nutzung)
            -> run_remote_category_classification
        Phase "criteria" (immer)
            -> run_criterion_scoring (inkl. Landmark-Teilphase, ebenfalls nur bei aktiver
               Cloud-Nutzung)

    Die Reihenfolge ist der eigentliche Zweck dieser Funktion: `run_criterion_scoring` liest die
    Remote-Ergebnisse ueber `_remote_category_evidence` aus der Datenbank und kann sie nur dann in
    die Kategorieableitung einrechnen, wenn sie bereits geschrieben sind.

    "Aktive Cloud-Nutzung" ist die Konjunktion `use_cloud and
    project.cloud_vision_detection_enabled`: die laufbezogene Checkbox kann eine
    fehlende projektweite Einwilligung nie ersetzen, nur eine vorhandene fuer diesen einen Lauf
    ungenutzt lassen. Ist sie falsch, wird run_remote_category_classification GAR NICHT ERST
    aufgerufen - es entsteht dann auch kein RemoteCategoryClassificationRun.

    Der Lauf-Datensatz (`CriterionScoringRun`) wird HIER angelegt, vor der ersten Phase, und an
    run_criterion_scoring durchgereicht: sonst zeigte `last_criterion_scoring_run` waehrend der
    Remote-Phase noch auf den Lauf davor und die Oberflaeche haette keinen Anker fuer den
    laufenden Vorgang.

    Ein Fehlschlag der Cloud-Phase bricht den Lauf NICHT ab: der lokale
    Bewertungsanteil ist der Kern des Laufs und laeuft vollstaendig durch, die Fehlermeldung
    wandert in `cloud_error_message`.

    Zwei Zusätze:

    - Der `RemoteCategoryClassificationRun` wird HIER angelegt und hineingereicht, und sein
      Fremdschluessel steht an der Lauf-Zeile, BEVOR Phase 1 startet. Damit ist die Zuordnung
      "welcher Remote-Lauf gehoert zu diesem Durchlauf" ein Schluessel statt einer Sortierung -
      noetig, weil die Bilanz einen GELDBETRAG einem bestimmten Durchlauf zuschreibt.
    - `estimated_cost_usd` ist die im Ausloese-Endpunkt serverseitig berechnete Schaetzung dieses
      Laufs. Sie wird hier nur DURCHGEREICHT und gespeichert, NIE neu gerechnet: die Modulgrenze
      "API zaehlt fuer die Schaetzung, Worker selektiert fuer den Lauf" bleibt bestehen. Sie ist
      ein BELEG, keine Eingabe - kein spaeterer Rechenweg liest sie."""
    cloud_active = use_cloud and project.cloud_vision_detection_enabled

    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run_id,
        status=ScanStatus.RUNNING,
        cloud_requested=use_cloud,
        estimated_cost_usd=estimated_cost_usd,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    # Die ERSTE Phase geht ueber denselben Weg wie jede spaetere, statt als
    # Konstruktor-Schluesselwort mitzulaufen. Sonst entkaeme genau sie der Bindung aus ADR 0116
    # Punkt 1, und die erste Phase JEDES Laufs - bei einem Lauf ohne Cloud die laengste - zeigte
    # dauerhaft "wird noch ermittelt", schweigend.
    _set_phase(
        run,
        ClassificationPhase.REMOTE_CATEGORIES if cloud_active else ClassificationPhase.CRITERIA,
    )
    await session.commit()

    if cloud_active:
        # Die Remote-Zeile entsteht hier, und der Fremdschluessel wird VOR dem ersten Cloud-Aufruf
        # committet - sonst haette die pollende Oberflaeche waehrend der gesamten Remote-Phase
        # keinen Anker fuer den Teilschritt, der gerade Geld ausgibt.
        remote_run = RemoteCategoryClassificationRun(
            project_id=project.id, status=ScanStatus.RUNNING
        )
        session.add(remote_run)
        await session.commit()
        await session.refresh(remote_run)
        run.remote_category_classification_run_id = remote_run.id
        await session.commit()

        try:
            remote_run = await run_remote_category_classification(
                session,
                project,
                cache_dir,
                build_client=build_category_client,
                build_embedder=build_embedder,
                run=remote_run,
            )
        except asyncio.CancelledError:
            # Schicht 1 des Fortschritts-Watchdogs: run_remote_category_classification faellt seine
            # EIGENE Zeile bereits ab und wirft weiter - ohne diesen Zweig bliebe der uebergeordnete
            # CriterionScoringRun, den run_classification vor Phase 1 anlegt, bis zum naechsten
            # Cron-Tick auf RUNNING stehen.
            await _fail_run(session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown).")
            raise
        if remote_run.status == ScanStatus.FAILED:
            # _fail_run hat die Session zurueckgerollt und damit JEDES Objekt darin expired -
            # anders als ein commit() (die Session laeuft mit expire_on_commit=False, siehe
            # db.py). Ohne diese beiden refresh()-Aufrufe loeste der naechste Attributzugriff
            # einen impliziten Lazy-Load ausserhalb eines aktiven greenlet-Kontexts aus
            # (MissingGreenlet): `run.cloud_error_message` unmittelbar hier,
            # `project.cloud_vision_detection_enabled`/`project.id` gleich darauf in
            # run_criterion_scoring, das auf derselben Session weiterlaeuft.
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
        build_embedder=build_embedder,
        run=run,
        use_cloud=use_cloud,
    )


async def classify(
    ctx: dict[str, Any],
    project_id: int,
    scoring_run_id: int,
    use_cloud: bool,
    estimated_cost_usd: float | None = None,
) -> int:
    """Der einzige Klassifizierungs-Job.

    `estimated_cost_usd` ist die im Ausloese-Endpunkt berechnete Schaetzung. Der Default `None` ist
    verbindlich - ein zum Zeitpunkt eines Deployments BEREITS EINGEREIHTER Job traegt das Argument
    nicht und darf nicht an der Signaturaenderung scheitern."""
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
            estimated_cost_usd=estimated_cost_usd,
        )
        return run.id


async def _classify_photo_for_remote_category(
    client: CategoryDetectionClientLike, cache_dir: Path, photo: Photo
) -> RemoteClassification:
    """Der reine I/O-/Netzwerk-Teil eines einzelnen Remote-Kategorie-Kandidaten (analog
    _detect_landmark_for_photo) - bewusst OHNE Session-Zugriff, damit mehrere Aufrufe sicher
    parallel per asyncio.gather laufen koennen. Nutzt ausschliesslich die bereits vorhandene,
    auf 2048 px begrenzte display-Cache-Variante - nie das OpenCloud-Original,
    kein EXIF/GPS, kein Dateiname und kein Pfad im Request - SICHERHEIT, Muss-Kriterium."""
    path = variant_path(cache_dir, photo.id, photo.etag, "display")
    image_bytes = path.read_bytes()
    return await client.classify(image_bytes, _CLOUD_VISION_IMAGE_MIME_TYPE, photo.id)


async def select_remote_category_candidates(session: AsyncSession, project_id: int) -> list[Photo]:
    """Kandidatenmenge für die Remote-Kategorie-Klassifizierung: der KOMPLETTE
    Ausschuss-Überlebender-Bestand (`duplicates.py::survives_ausschuss`) OHNE Vorfilter
    (anders als landmark), abzüglich der bereits VOLLSTÄNDIG von der Cloud beurteilten Fotos.

    DAS SKIP-KRITERIUM IST ZUSAMMENGESETZT (Sicherheitsauflage S6): eine Kopfzeile mit
    `source='cloud'` UND eine Albumtauglichkeitszeile. Beide Hälften tragen je einen eigenen
    Fehler:

    - Ein reiner Existenztest auf die Kopfzeile (statt auf `source='cloud'`) machte jedes lokal
      beurteilte Foto dauerhaft zum Nicht-Kandidaten - der Kriterien-Lauf schreibt für JEDES
      beurteilte Foto eine LOKALE Kopfzeile. Die Cloud-Klassifizierung wäre ein stilles No-op.
    - Eine Lockerung auf nur EINES der beiden Merkmale schickt fertig bewertete Fotos erneut an
      den Anbieter: Kosten und wiederholte Datenexposition.

    Die zweite Hälfte ist zugleich die NACHBEWERTUNG: ein Foto aus einem früheren Lauf, das eine
    Cloud-Kopfzeile, aber noch keine Albumtauglichkeit trägt, wird wieder Kandidat - ohne Re-Scan
    und ohne zweiten Auslöser.

    Das lokale Ausschuss-Gate bleibt dabei unberührt und steht ausgeschrieben in DERSELBEN
    Anweisung wie der Skip-Term (S8 jener Spec, S1/S2 von Spec 0374): `join(PhotoScore)` plus
    `survives_ausschuss()` begrenzen weiterhin, welche Fotos den Homeserver überhaupt verlassen
    dürfen. Das Prädikat tritt als weiterer Konjunktionsteil in DIESE Anweisung ein, nie als
    nachgelagerter Filter über einer bereits gebildeten Menge.

    Von `run_remote_category_classification` UND `GET .../classify/estimate` (api/projects.py)
    genutzt - "ermittelt ueber dieselbe Kandidaten-Selektion wie der tatsaechliche Lauf"."""
    rows = (
        (
            await session.execute(
                select(Photo)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.project_id == project_id, survives_ausschuss())
            )
        )
        .scalars()
        .all()
    )

    if not rows:
        return []

    photo_ids = [photo.id for photo in rows]
    cloud_assessed_ids = set(
        (
            await session.execute(
                select(PhotoMotifAssessment.photo_id).where(
                    PhotoMotifAssessment.photo_id.in_(photo_ids),
                    PhotoMotifAssessment.source == MotifAssessmentSource.CLOUD,
                )
            )
        ).scalars()
    )
    suitability_ids = set(
        (
            await session.execute(
                select(PhotoAlbumSuitability.photo_id).where(
                    PhotoAlbumSuitability.photo_id.in_(photo_ids)
                )
            )
        ).scalars()
    )
    return [
        photo
        for photo in rows
        if not (photo.id in cloud_assessed_ids and photo.id in suitability_ids)
    ]


async def run_remote_category_classification(
    session: AsyncSession,
    project: Project,
    cache_dir: Path,
    build_client: Callable[
        [str], CategoryDetectionClientLike
    ] = build_category_classification_client,
    build_embedder: Callable[[], LabelEmbedderLike] = build_label_embedder,
    *,
    run: RemoteCategoryClassificationRun | None = None,
) -> RemoteCategoryClassificationRun:
    """Eigenständiger, expliziter Job - KEIN Teil von run_criterion_scoring, eigene
    Run-Tabelle, eigenes Concurrency-Setting. Best-effort ohne Retry: ein einzelner
    Fehlschlag bricht den Lauf nicht ab, das Foto bleibt beim naechsten Lauf erneut Kandidat.
    `project.cloud_vision_detection_enabled` wird hier EINMALIG gelesen (kein Live-Reread,
    dokumentierte Vereinfachung analog run_criterion_scoring) - ist der Schalter aus (Default)
    ODER der Kandidatenpool leer, wird `build_client` GAR NICHT ERST aufgerufen (Security-Muss-
    Kriterium, geteiltes Consent-Gate mit `landmark`).

    `run` ist der bereits von run_classification angelegte Lauf-Datensatz - dasselbe Muster wie bei
    CriterionScoringRun/run_criterion_scoring, eine Ebene tiefer. Der übergeordnete
    Klassifizierungslauf setzt seinen Fremdschluessel darauf, BEVOR Phase 1 startet; ohne diesen
    frueheren Anlagezeitpunkt haette die Oberflaeche waehrend der Remote-Phase keinen Anker fuer
    den laufenden Vorgang. Wird keiner uebergeben (Direktaufruf, Tests), legt diese Funktion die
    Zeile selbst an."""
    if run is None:
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

        # Eine Auflösung je Cloud-Phase, danach durchgereicht - dasselbe Modell wie in der
        # Landmark-Phase, weil `LANDMARK_MODEL` wie `LANDMARK_PROVIDER` fuer beide Cloud-Anteile
        # gilt.
        model = settings.resolved_landmark_model()
        client = _try_build(lambda: build_client(model))
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

        # Ist-Kosten-Buchführung dieses Laufs, identisch zur Landmark-Phase in
        # run_criterion_scoring - summiert über die ERFOLGREICHEN Ergebnisse, geschrieben im
        # `finally` unten.
        #
        # VOR dem `try` gebunden: der `finally`-Block liest diese drei Namen. Wuerde eine Anweisung
        # INNERHALB des `try` vor ihrer Initialisierung werfen - realistisch ein DB-Fehler beim
        # Laden des Feinlabel-Snapshots -, ersetzte ein UnboundLocalError die urspruengliche
        # Exception, und der eigentliche Fehlergrund waere weder im Log noch in
        # `run.error_message` erkennbar.
        api_calls = 0
        input_tokens = 0
        output_tokens = 0
        # Der Live-Zaehler der Fehlschlaege - streng getrennt von `api_calls` daneben, das die
        # Kosten-Buchfuehrung ist und einmal am Phasenende geschrieben wird.
        failed_calls = 0
        # Modell und Zaehler stehen beim BETRETEN der Phase da, nicht erst im `finally` -
        # `failed_calls = 0` heisst "erfasst, noch nichts fehlgeschlagen" und unterscheidet sich
        # damit von `NULL` = "diese Phase fand nicht statt". Der BETRAG bleibt am Phasenende
        # eingefroren.
        run.model = model
        run.failed_calls = failed_calls
        await session.commit()

        # Zählerstand des ANBIETERWEITEN Schrittmachers beim Betreten des Teilschritts, wie in der
        # Landmark-Phase in run_criterion_scoring. Die Zusammenfassung unten entsteht
        # ausschliesslich aus der DIFFERENZ zu diesem Schnappschuss.
        throttle = throttle_for_provider(settings.landmark_provider)
        throttle_before = throttle.stats()

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
            for start in range(0, len(candidates), concurrency):
                block = candidates[start : start + concurrency]
                results = await asyncio.gather(
                    *[
                        _classify_photo_for_remote_category(client, cache_dir, photo)
                        for photo in block
                    ],
                    return_exceptions=True,
                )
                # Async-Fallstrick - siehe run_criterion_scoring.
                for result in results:
                    if isinstance(result, asyncio.CancelledError):
                        raise result

                for photo, result in zip(block, results, strict=True):
                    if isinstance(result, BaseException):
                        # Best-effort: ein einzelner fehlgeschlagener Cloud-Aufruf laesst fuer
                        # dieses Foto keine Zeile entstehen, das Foto bleibt beim naechsten Lauf
                        # erneut Kandidat. Dennoch sichtbar über docker compose logs.
                        # type(exc).__name__/str(exc) GENAU EINMAL berechnet, an beide Senken
                        # (Logger, DB) weitergereicht - keine zweite Auswertung.
                        #
                        # Das Zählen führt AUSDRÜCKLICH keine weitere Logzeile ein - der
                        # Fehlergrund bleibt, wo er liegt (Logzeile unten mit fester Meldung,
                        # photo_cloud_vision_errors, laufweite cloud_error_message). Der Zaehler
                        # ist eine Anzahl, kein Fremdtext.
                        failed_calls += 1
                        exc_type_name = type(result).__name__
                        exc_message = str(result)
                        _log_cloud_vision_failure(
                            "remote_category",
                            photo.id,
                            photo.relative_path,
                            exc_type_name,
                            exc_message,
                        )
                        # Dauerhafte, per API abrufbare Persistenz desselben Fehlschlags (getrennt
                        # vom Log oben).
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
                    # Verbindlich: jeder stattgefundene Aufruf zaehlt, auch ohne
                    # `usage`-Block (Tokenbeitrag dann 0) - `api_calls > 0` bei Betrag 0/NULL ist
                    # der Ausloeser fuer Befund (b) des Unvollstaendigkeits-Hinweises.
                    api_calls += 1
                    if classification.usage is not None:
                        input_tokens += classification.usage.input_tokens
                        output_tokens += classification.usage.output_tokens

                    # Pro Foto genau EINE Kopfzeile (`source='cloud'`) samt vollstaendigem
                    # Achter-Staerkevektor. Der Vektor kommt VALIDIERT aus dem Parser -
                    # SICHERHEIT: nie die Rohabbildung des Modells, sonst wanderte
                    # unvalidierter Fremdtext über einen zweiten Kanal in API-Antwort und UI
                    # (S8/S9), und ein entarteter Zahlenwert legte über Starlettes
                    # `allow_nan=False` die gesamte Fotoliste des Projekts auf 500.
                    #
                    # `upsert_assessment` setzt die Regel durch, die beide Grundlagen
                    # auseinanderhaelt: eine Cloud-Grundlage schreibt immer und ersetzt eine
                    # vorhandene lokale VOLLSTAENDIG. Die Korrekturzeilen bleiben unangetastet -
                    # sie haengen am Foto und nicht an der Kopfzeile.
                    await upsert_assessment(
                        session,
                        photo.id,
                        source=MotifAssessmentSource.CLOUD,
                        strengths=classification.motif_strengths,
                        excluded_document=classification.excluded,
                        provider=settings.landmark_provider,
                        computed_at=now,
                    )

                    # Die Albumtauglichkeit derselben Antwort, im SELBEN Schleifendurchlauf und mit
                    # demselben `now` - und nach derselben Best-effort-Regel: ohne brauchbare Stufe
                    # entsteht keine Zeile, kein Fehler, kein Laufabbruch. Das Foto bleibt dann
                    # Kandidat des naechsten Laufs (die Auswahl unten verlangt BEIDE Zeilen).
                    if classification.album_suitability is not None:
                        await _upsert_album_suitability(
                            session,
                            photo.id,
                            classification.album_suitability,
                            now,
                            settings.landmark_provider,
                        )

                    # Feinlabels sind reine Zusatzinformation und werden AUCH DANN geschrieben,
                    # wenn das Modell kein Motiv deutlich erkennt. Loesen beide
                    # Labels auf denselben canonical_key auf, entsteht nur eine Zeile - kein
                    # IntegrityError durch UniqueConstraint(photo_id, fine_label_id). Ein
                    # Konfidenz-Vergleich ist dafür nicht nötig, es gewinnt die Erstnennung.
                    entries_by_canonical: dict[str, tuple[FineLabelSnapshotEntry, str]] = {}
                    for raw_label in classification.fine_labels:
                        entry = resolve_canonical_label(raw_label, snapshot, embedder)
                        entries_by_canonical.setdefault(entry.canonical_key, (entry, raw_label))

                    # Die Feinlabel-Zeilen der VORHERIGEN Antwort fallen VOLLSTAENDIG, bevor die
                    # neuen entstehen - dieselbe Regel wie beim Staerkevektor: eine Antwort ist
                    # vollstaendig oder sie existiert nicht, ein Gemisch aus zwei Antworten gibt es
                    # nicht. Seit der geweiteten Kandidatenauswahl ist das keine Kosmetik: ein
                    # erneut gesendetes Foto traegt seine alten Zeilen noch, und ein zweiter
                    # INSERT desselben Labels verletzte `UniqueConstraint(photo_id,
                    # fine_label_id)` - die IntegrityError rollt die Transaktion zurueck und laesst
                    # den GESAMTEN Lauf scheitern, nicht nur dieses eine Foto. Die
                    # `fine_labels`-Registry selbst bleibt unberuehrt (projektuebergreifendes
                    # Vokabular).
                    await session.execute(
                        delete(PhotoFineLabel).where(PhotoFineLabel.photo_id == photo.id)
                    )

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
                    # "Aufräumen bei Erfolg": ein erfolgreicher (Retry-)Versuch
                    # loescht eine ggf. vorhandene Fehler-Zeile - einmal pro Foto, nicht pro Label.
                    await _clear_cloud_vision_error(
                        session, photo.id, CloudVisionPhase.REMOTE_CATEGORY
                    )

                processed += len(block)
                run.photos_processed = processed
                # Der Live-Zähler wird am Block-Commit-Punkt mitgeschrieben - am Blockende, nie
                # beim Betreten des Blocks (sonst stuende nach einem Abbruch mitten im Block ein
                # `processed` da, dem weder ein Aufruf noch ein Fehlschlag gegenuebersteht).
                run.failed_calls = failed_calls
                run.last_progress_at = _now_utc()
                await session.commit()
        finally:
            aclose = getattr(client, "aclose", None)
            if aclose is not None:
                await aclose()
            # Wie in der Landmark-Phase VERBINDLICH im finally und mit eigenem Commit: ein nach
            # begonnener Cloud-Nutzung scheiternder Lauf hat das Geld bereits ausgegeben, und der
            # Fehlerpfad laeuft ueber _fail_run, das mit einem rollback() beginnt. Der Betrag wird
            # einmal berechnet und eingefroren.
            run.api_calls = api_calls
            run.input_tokens = input_tokens
            run.output_tokens = output_tokens
            run.cost_usd = compute_cost_usd(
                model,
                TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            )
            # Wie in der Landmark-Phase oben: `run.model` steht bereits vom Phasenanfang her da
            # (derselbe lokale `model`, aus dem hier der Betrag entsteht) - KEINE zweite Zuweisung.
            await _commit_phase_costs(session)

        # Höchstens eine Zeile, und nur wenn in DIESEM Teilschritt tatsächlich gewartet wurde.
        _log_cloud_vision_throttling(
            "remote_category",
            settings.landmark_provider,
            throttle.stats().since(throttle_before),
        )

        run.status = ScanStatus.SUCCESS
        run.finished_at = _now_utc()
        await session.commit()
        return run
    except asyncio.CancelledError:
        await _fail_run(session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown).")
        raise
    except Exception as exc:
        await _fail_run(session, run, str(exc))
        return run


# Fortschritts-Watchdog: grosszuegiger Not-Anker (24h), NICHT der primaere Terminierungsmechanismus
# - Schicht 2 (STALL_THRESHOLD, siehe reap_stalled_runs) greift fuer jeden echten Stillstand immer
# zuerst. Begrenzt nur den Ressourcenverbrauch eines Defekts in Schicht 2 selbst. Der arq-Default
# von 300s (5 Minuten) ist hier untauglich - er ist deutlich zu kurz fuer legitim lange Scans
# grosser Fotobibliotheken (bindende Stakeholder-Anforderung).
JOB_TIMEOUT_SECONDS = 86400

# Schicht 2 des Fortschritts-Watchdogs: der eigentliche, fortschrittsbasierte
# Stillstands-Schwellwert - ein RUNNING-Lauf, dessen last_progress_at strikt aelter als dieser Wert
# ist, gilt als haengend, unabhaengig von seiner Gesamtlaufzeit (bindende Stakeholder-Anforderung:
# "nur ein echter Stillstand ist ein Fehler, keine feste Obergrenze").
STALL_THRESHOLD = timedelta(minutes=15)


def _stall_message() -> str:
    # Die Minutenzahl wird aus STALL_THRESHOLD abgeleitet, NIE hart codiert - sonst veraltet die
    # Meldung beim naechsten Anpassen von STALL_THRESHOLD unbemerkt.
    minutes = int(STALL_THRESHOLD.total_seconds() // 60)
    return (
        f"Kein Fortschritt seit über {minutes} Minuten erkannt — "
        "vermutlich hängender Verarbeitungsschritt."
    )


async def _fail_if_stalled(
    session: AsyncSession,
    run: ScanRun | ScoringRun | CriterionScoringRun | RemoteCategoryClassificationRun,
) -> bool:
    """Setzt eine einzelne Zeile über _fail_run auf FAILED, isoliert von den übrigen
    Zeilen/Tabellen: ein Fehler bei einer Zeile/Tabelle darf die Bereinigung der übrigen
    nicht blockieren - ein Fehlschlag hier (z.B. ein DB-Fehler beim
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
    """Schicht 2 des Fortschritts-Watchdogs: periodischer arq-Cron-Job (alle 5 Minuten, siehe
    WorkerSettings.cron_jobs), unabhaengig von einer ggf. tatsaechlich noch haengenden Coroutine -
    deckt exakt den Fall ab, den reines Exception-Handling (Schicht 1, _fail_run oben) strukturell
    nie schliessen kann (ein nie zurueckkehrender await liefert nie eine Exception, an die sich
    anknuepfen liesse). session_factory ist injizierbar (Default: die echte, produktive
    async_session_factory) - Tests uebergeben stattdessen eine an eine In-Memory-SQLite-
    Testdatenbank gebundene Factory, analog zu run_criterion_scoring's build_detector-Parameter.
    Die vier Tabellen werden bewusst nacheinander in vier eigenstaendigen Bloecken behandelt
    statt ueber eine generische Schleife (konsistent mit dem Rest dieser Datei: ScanRun/
    ScoringRun/CriterionScoringRun/RemoteCategoryClassificationRun bleiben vier eigenstaendige
    Modelle ohne gemeinsame Basisklasse)."""
    reaped = 0
    threshold = _now_utc() - STALL_THRESHOLD
    async with session_factory() as session:
        try:
            stalled_scan_runs = (
                (
                    await session.execute(
                        select(ScanRun).where(
                            ScanRun.status == ScanStatus.RUNNING,
                            ScanRun.last_progress_at < threshold,
                        )
                    )
                )
                .scalars()
                .all()
            )
        except Exception:
            # Ohne rollback() bliebe die Transaktion auf einer echten Postgres-Verbindung nach
            # einem fehlgeschlagenen SELECT im Zustand "current transaction is aborted" - die
            # nachfolgenden SELECTs fuer ScoringRun/CriterionScoringRun wuerden dann selbst
            # fehlschlagen, obwohl inhaltlich nichts mit ihnen falsch ist. Damit braeche die
            # Zusage "ein Fehler bei einer Tabelle blockiert die Bereinigung der uebrigen nicht"
            # in Produktion - im SQLite-Testsetup unsichtbar, da dort eine vor jedem DB-Zugriff
            # geworfene Python-Exception die DBAPI-Transaktion nie tatsaechlich invalidiert.
            await session.rollback()
            stalled_scan_runs = []
        for scan_run in stalled_scan_runs:
            if await _fail_if_stalled(session, scan_run):
                reaped += 1

        try:
            stalled_scoring_runs = (
                (
                    await session.execute(
                        select(ScoringRun).where(
                            ScoringRun.status == ScanStatus.RUNNING,
                            ScoringRun.last_progress_at < threshold,
                        )
                    )
                )
                .scalars()
                .all()
            )
        except Exception:
            await session.rollback()
            stalled_scoring_runs = []
        for scoring_run in stalled_scoring_runs:
            if await _fail_if_stalled(session, scoring_run):
                reaped += 1

        try:
            stalled_criterion_scoring_runs = (
                (
                    await session.execute(
                        select(CriterionScoringRun).where(
                            CriterionScoringRun.status == ScanStatus.RUNNING,
                            CriterionScoringRun.last_progress_at < threshold,
                        )
                    )
                )
                .scalars()
                .all()
            )
        except Exception:
            await session.rollback()
            stalled_criterion_scoring_runs = []
        for criterion_scoring_run in stalled_criterion_scoring_runs:
            if await _fail_if_stalled(session, criterion_scoring_run):
                reaped += 1

        try:
            stalled_remote_category_runs = (
                (
                    await session.execute(
                        select(RemoteCategoryClassificationRun).where(
                            RemoteCategoryClassificationRun.status == ScanStatus.RUNNING,
                            RemoteCategoryClassificationRun.last_progress_at < threshold,
                        )
                    )
                )
                .scalars()
                .all()
            )
        except Exception:
            await session.rollback()
            stalled_remote_category_runs = []
        for remote_category_run in stalled_remote_category_runs:
            if await _fail_if_stalled(session, remote_category_run):
                reaped += 1

    return reaped


async def _configure_worker_logging(ctx: dict[Any, Any]) -> None:
    """arq-`on_startup`-Hook - dünner Wrapper, NIE die direkte Zuweisung
    `on_startup = configure_logging`: arq ruft on_startup immer mit einem ctx-Positionalargument
    auf, waehrend `configure_logging()` eine Null-Argument-Funktion ist (identisch zum Aufruf in
    main.py::create_app()). Eine direkte Zuweisung braeche erst beim tatsaechlichen Worker-Start
    mit einem TypeError durch."""
    configure_logging()


class WorkerSettings:
    # arq.worker.func(...) statt nackter Funktionsreferenzen: max_tries=1 deaktiviert arqs
    # automatischen Hintergrund-Retry vollstaendig - ein durch job_timeout abgebrochener Job
    # erzeugt dadurch KEINE zweite Run-Zeile (arq prueft job_try > max_tries VOR dem erneuten
    # Coroutine-Aufruf). Damit gilt strukturell: ein Nutzer-Trigger -> genau ein Lauf -> ein
    # eindeutiger Endzustand, sichtbar ueber die "Erneut versuchen"-UI statt eines unsichtbaren
    # automatischen Wiederholungsversuchs.
    functions = (
        arq_func(scan_project, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
        arq_func(score_project, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
        # EIN verketteter Job (Remote-Kategorisierung -> Kriterien-Bewertung), nicht zwei
        # einzelne - die Reihenfolge steckt in run_classification, nicht in einer Bedienanweisung.
        arq_func(classify, timeout=JOB_TIMEOUT_SECONDS, max_tries=1),
    )
    # Schicht 2 des Fortschritts-Watchdogs: run_at_startup=True sorgt dafuer, dass ein
    # Worker-Neustart sofort eine erste Pruefung ausloest, statt bis zu 5 Minuten auf den
    # naechsten regulaeren Tick zu warten - eine bereits vor dem Neustart haengende Zeile soll
    # nicht unnoetig lang unentdeckt bleiben.
    cron_jobs = (cron(reap_stalled_runs, minute=set(range(0, 60, 5)), run_at_startup=True),)
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    # Einer der beiden Prozess-Einstiegspunkte (Worker-Prozess) - derselbe Aufruf sitzt fuer den
    # API-Prozess in main.py::create_app().
    on_startup = _configure_worker_logging
