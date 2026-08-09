from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
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
# monkeypatch.setattr(worker, "SCAN_COMMIT_BATCH_SIZE", ...) verkleinern koennen. Anders als bei
# run_project_scoring hat der Scan-Loop in run_project_scan zwei `continue`-Zweige (uebersprungene
# Endung, unveraenderter Etag) - der Checkpoint-Aufruf (siehe _commit_progress_checkpoint dort)
# sitzt deshalb an JEDEM Ausstiegspunkt der Schleife, nicht nur am regulaeren Ende, sonst waere er
# im dominanten Realweltfall (Re-Scan mit ueberwiegend unveraenderten Dateien) faktisch nie
# erreichbar (Review-Fund).
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


async def _generate_thumbnails(
    client: OpenCloudScanClient,
    webdav_url: str,
    relative_path: str,
    photo: Photo,
    cache_dir: Path,
) -> None:
    """Best-effort (specs/features/0002-manual-categorization.md): weder ein Download- noch ein
    Dekodierfehler duerfen den Scan des Projekts abbrechen (anders als die uebrigen
    OpenCloudError-Faelle unten, die den ganzen Scan als FAILED markieren) - ein fehlendes
    Thumbnail aeussert sich nur als 404-Platzhalter im Bild-Endpunkt, siehe thumbnails.py."""
    try:
        content = await client.download(webdav_url, relative_path)
    except OpenCloudError:
        return
    generate_variants(cache_dir, photo.id, photo.etag, content)


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
        seen_paths: set[str] = set()
        files_found = 0
        photos_added = 0
        photos_updated = 0
        files_skipped = 0

        async def _commit_progress_checkpoint() -> None:
            # Review-Fund (specs/features/0022-scan-live-fortschrittszaehler.md): muss an JEDEM
            # Ausstiegspunkt der Schleife unten aufgerufen werden (Skip wegen Endung, Skip wegen
            # unveraendertem Etag, vollstaendige Verarbeitung) - nicht nur am Ende einer
            # vollstaendigen Verarbeitung. Anders als run_project_scoring hat dieser Loop zwei
            # `continue`-Zweige; ein Checkpoint nur "am Ende" (nach _generate_thumbnails) waere
            # fuer Iterationen, die einen der beiden Zweige treffen, nie erreichbar - im
            # dominanten Realweltfall (Re-Scan mit ueberwiegend unveraenderten Dateien) wuerde der
            # Live-Zaehler dann faktisch nicht wachsen. `files_found` wird per Closure gelesen
            # (kein `nonlocal` noetig, da hier nur gelesen, nicht neu zugewiesen wird).
            if files_found % SCAN_COMMIT_BATCH_SIZE == 0:
                scan_run.files_found = files_found
                # Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-
                # watchdog.md, ADR 0019, Schicht 2): Zweitverwendung dieses bereits bestehenden
                # Zwischen-Commit-Checkpoints - reap_stalled_runs (worker.py) liest diesen Wert,
                # keine neue Checkpoint-Kadenz noetig.
                scan_run.last_progress_at = _now_utc()
                await session.commit()

        entry: DavEntry
        async for relative_path, entry in client.walk(drive.webdav_url, project.opencloud_path):
            files_found += 1
            extension = _extension(relative_path)
            if extension not in _IMAGE_EXTENSIONS:
                files_skipped += 1
                await _commit_progress_checkpoint()
                continue

            seen_paths.add(relative_path)
            existing_photo = existing_photos.get(relative_path)
            if existing_photo is not None and existing_photo.etag == entry.etag:
                await _commit_progress_checkpoint()
                continue

            last_modified = _naive_utc(entry.last_modified) if entry.last_modified else _now_utc()
            taken_at = last_modified
            if extension in _EXIF_CANDIDATE_EXTENSIONS:
                content = await client.get_range(drive.webdav_url, relative_path, _EXIF_RANGE_BYTES)
                exif_taken_at = extract_taken_at(content)
                if exif_taken_at is not None:
                    taken_at = exif_taken_at

            if existing_photo is not None:
                existing_photo.etag = entry.etag or ""
                existing_photo.content_length = entry.content_length or 0
                existing_photo.taken_at = taken_at
                existing_photo.last_modified = last_modified
                photo = existing_photo
                photos_updated += 1
            else:
                photo = Photo(
                    project_id=project.id,
                    relative_path=relative_path,
                    etag=entry.etag or "",
                    content_length=entry.content_length or 0,
                    taken_at=taken_at,
                    last_modified=last_modified,
                )
                session.add(photo)
                photos_added += 1
                # Only newly added rows lack a DB-assigned id; existing_photo already has one
                # from the initial select above, so flushing there on every file would be an
                # unnecessary DB roundtrip per photo (Code-Review-Fund).
                await session.flush()

            await _generate_thumbnails(client, drive.webdav_url, relative_path, photo, cache_dir)
            await _commit_progress_checkpoint()

        removed_paths = set(existing_photos) - seen_paths
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

_STALL_MESSAGE = (
    "Kein Fortschritt seit über 15 Minuten erkannt — vermutlich hängender Verarbeitungsschritt."
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
        await _fail_run(session, run, _STALL_MESSAGE)
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
