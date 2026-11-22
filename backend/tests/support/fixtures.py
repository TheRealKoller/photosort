"""Fabriken fuer gemeinsame Testdaten des Backends.

Jede frueher je Testdatei ausgeschriebene Zeile steht hier genau einmal; die Abweichungen der
Aufrufer sind Schluesselwort-Parameter, deren Vorgabe der haeufigste Aufrufer setzt. Reine
Datenerzeugung, deshalb ohne eigene Tests - geprueft wird sie ueber jeden Aufrufer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_opencloud_client
from photosort.cameras import shifted
from photosort.main import app
from photosort.models import (
    CriterionScoringRun,
    DuplicateDecision,
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    Project,
    ProjectCamera,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.opencloud.webdav_xml import DavEntry
from tests.support.fakes import FakeOpenCloudClient

# Der eine feste Bezugsmoment: frueher stand er in jeder Testdatei als eigenes Moduldatum.
DEFAULT_MOMENT = datetime(2023, 1, 1, tzinfo=UTC).replace(tzinfo=None)


async def make_project(
    session: AsyncSession,
    name: str = "Costa Rica",
    *,
    drive_id: str | None = None,
    path: str | None = None,
    cloud_vision_consent: bool = False,
    selection_target: int | None = None,
    flush: bool = False,
) -> Project:
    """Ein Projekt; `opencloud_drive_id`/`opencloud_path` leiten sich aus `name` ab.

    `flush=True` legt es nur in der laufenden Transaktion an (Aufrufer, der die Zeile noch vor
    einem Commit braucht); ohne das Schluesselwort wird committet und neu geladen.
    """
    project = Project(
        name=name,
        opencloud_drive_id=f"drive-{name}" if drive_id is None else drive_id,
        opencloud_path=name if path is None else path,
        cloud_vision_detection_enabled=cloud_vision_consent,
        cloud_vision_consent_at=DEFAULT_MOMENT if cloud_vision_consent else None,
        selection_target=selection_target,
    )
    session.add(project)
    if flush:
        await session.flush()
        return project
    await session.commit()
    await session.refresh(project)
    return project


async def make_project_id(session: AsyncSession, name: str = "Costa Rica", **kwargs: Any) -> int:
    """Wie `make_project`, gibt aber nur die Kennung zurueck - duenne Weiterleitung, keine
    zweite Erzeugung."""
    project = await make_project(session, name, **kwargs)
    return project.id


async def make_user(
    session: AsyncSession,
    username: str = "anleger",
    *,
    password_hash: str = "x",
    flush: bool = False,
) -> User:
    user = User(username=username, password_hash=password_hash)
    session.add(user)
    if flush:
        await session.flush()
        return user
    await session.commit()
    await session.refresh(user)
    return user


async def add_photo(
    session: AsyncSession,
    project: Project | int,
    path: str = "a.jpg",
    *,
    etag: str | None = None,
    content_length: int = 100,
    taken_at: datetime | None = None,
    taken_at_original: datetime | None = None,
    last_modified: datetime | None = None,
    gps: tuple[float, float] | None = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
    camera: ProjectCamera | None = None,
    camera_probed: bool | None = None,
    pixel_count: int | None = None,
    with_score: bool = False,
    sharpness: float = 100.0,
    exposure: float = 0.0,
    cluster_key: str | None = None,
    cluster_key_from_id: bool = False,
    score_computed_at: datetime | None = None,
    suggested_status: RatingStatus | None = None,
    duplicate_of: int | None = None,
    decision: DuplicateDecision | None = None,
    flush: bool = False,
) -> Photo:
    """Ein Foto, wahlweise mit Bewertungszeile und Duplikat-Entscheidung.

    `taken_at` ist die AUFGEZEICHNETE Zeit; mit `camera` wird daraus ueber `shifted` die
    korrigierte Zeit (ADR 0090) - die Invariante gilt damit auch im Testaufbau.
    """
    moment = DEFAULT_MOMENT if taken_at is None else taken_at
    original = moment if taken_at_original is None else taken_at_original
    corrected = shifted(moment, 0 if camera is None else camera.offset_minutes)
    assert corrected is not None
    photo = Photo(
        project_id=project.id if isinstance(project, Project) else project,
        relative_path=path,
        etag=f"etag-{path}" if etag is None else etag,
        content_length=content_length,
        taken_at=corrected,
        taken_at_original=original,
        camera_id=None if camera is None else camera.id,
        camera_probed=camera is not None if camera_probed is None else camera_probed,
        last_modified=corrected if last_modified is None else last_modified,
        gps_lat=gps[0] if gps is not None else gps_lat,
        gps_lon=gps[1] if gps is not None else gps_lon,
        pixel_count=pixel_count,
    )
    session.add(photo)
    await session.flush()
    if with_score:
        session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=sharpness,
                exposure=exposure,
                cluster_key=f"cluster-{photo.id}" if cluster_key_from_id else cluster_key,
                suggested_status=suggested_status,
                duplicate_of=duplicate_of,
                computed_at=corrected if score_computed_at is None else score_computed_at,
            )
        )
    if decision is not None:
        session.add(PhotoDuplicateDecision(photo_id=photo.id, decision=decision))
    if flush:
        await session.flush()
        return photo
    await session.commit()
    await session.refresh(photo)
    return photo


async def add_scoring_run(
    session: AsyncSession,
    project: Project | int,
    *,
    status: ScanStatus = ScanStatus.SUCCESS,
    started_at: datetime | None = None,
    suggestions_found: int = 0,
    flush: bool = False,
) -> ScoringRun:
    run = ScoringRun(
        project_id=project.id if isinstance(project, Project) else project,
        status=status,
        suggestions_found=suggestions_found,
        **({} if started_at is None else {"started_at": started_at}),
    )
    session.add(run)
    if flush:
        await session.flush()
        return run
    await session.commit()
    await session.refresh(run)
    return run


async def add_successful_run(
    session: AsyncSession,
    project: Project | int,
    *,
    status: ScanStatus = ScanStatus.SUCCESS,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    flush: bool = True,
) -> CriterionScoringRun:
    """Ein erfolgreicher Kriterien-Lauf samt seinem Scoring-Lauf (`scoring_run_id`)."""
    project_id = project.id if isinstance(project, Project) else project
    scoring_run = await add_scoring_run(session, project_id, started_at=started_at, flush=True)
    run = CriterionScoringRun(
        project_id=project_id,
        scoring_run_id=scoring_run.id,
        status=status,
        **({} if started_at is None else {"started_at": started_at}),
        **({} if finished_at is None else {"finished_at": finished_at}),
    )
    session.add(run)
    if flush:
        await session.flush()
        return run
    await session.commit()
    await session.refresh(run)
    return run


def write_display_variant(
    cache_dir: Any,
    photo: Photo,
    image: Any = None,
    *,
    size: tuple[int, int] = (160, 160),
    color: tuple[int, int, int] = (100, 100, 100),
) -> None:
    """Legt die display-Variante eines Fotos im Cache an - mit `image` oder einem Platzhalter."""
    from PIL import Image

    from photosort.thumbnails import display_path

    target = display_path(cache_dir, photo.id, photo.etag)
    target.parent.mkdir(parents=True, exist_ok=True)
    if image is None:
        image = Image.new("RGB", size, color=color)
    image.save(target, format="JPEG")


def opencloud_entry(
    name: str,
    *,
    is_collection: bool = False,
    etag: str = "etag",
    href: str | None = None,
    last_modified: datetime | None = None,
    content_length: int | None = None,
) -> DavEntry:
    return DavEntry(
        href=f"/x/{name}" if href is None else href,
        name=name,
        is_collection=is_collection,
        etag=etag,
        last_modified=last_modified,
        content_length=content_length,
    )


async def create_project_via_api(
    client: httpx.AsyncClient, name: str = "Costa Rica", *, path: str | None = None
) -> int:
    """Ein Projekt ueber `POST /projects`, mit dem gemeinsamen OpenCloud-Doppelgaenger."""
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await client.post(
        "/projects",
        json={"name": name, "opencloud_path": name if path is None else path},
    )
    project_id: int = created.json()["id"]
    return project_id
