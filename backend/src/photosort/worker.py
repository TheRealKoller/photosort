from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.config import settings
from photosort.db import async_session_factory
from photosort.models import Photo, Project, ScanRun, ScanStatus
from photosort.opencloud.client import OpenCloudClient, OpenCloudError
from photosort.opencloud.exif import extract_taken_at
from photosort.opencloud.webdav_xml import DavEntry
from photosort.thumbnails import generate_variants

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
_EXIF_CANDIDATE_EXTENSIONS = {".jpg", ".jpeg"}
_EXIF_RANGE_BYTES = 131_072


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

            await session.flush()  # assigns photo.id for newly added rows, needed below
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


class WorkerSettings:
    functions = (scan_project,)
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
