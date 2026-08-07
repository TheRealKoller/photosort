from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from arq.connections import RedisSettings
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.config import settings
from photosort.db import async_session_factory
from photosort.models import (
    Photo,
    PhotoScore,
    Project,
    RatingStatus,
    ScanRun,
    ScanStatus,
    ScoringRun,
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

        entry: DavEntry
        async for relative_path, entry in client.walk(drive.webdav_url, project.opencloud_path):
            files_found += 1
            extension = _extension(relative_path)
            if extension not in _IMAGE_EXTENSIONS:
                files_skipped += 1
                continue

            seen_paths.add(relative_path)
            existing_photo = existing_photos.get(relative_path)
            if existing_photo is not None and existing_photo.etag == entry.etag:
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
    except OpenCloudError as exc:
        await session.rollback()
        scan_run.status = ScanStatus.FAILED
        scan_run.error_message = str(exc)
        scan_run.finished_at = _now_utc()
        await session.commit()
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
    except Exception as exc:
        # Kein Rollback bereits committeter PhotoScore-Zeilen/des letzten committeten
        # photos_processed-Stands (Akzeptanzkriterium der Spec) - session.rollback() verwirft nur
        # die seit dem letzten commit() offene, noch nicht persistierte Transaktion, exakt wie im
        # OpenCloudError-Pfad von run_project_scan oben.
        await session.rollback()
        scoring_run.status = ScanStatus.FAILED
        scoring_run.error_message = str(exc)
        scoring_run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()
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


class WorkerSettings:
    functions = (scan_project, score_project)
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
