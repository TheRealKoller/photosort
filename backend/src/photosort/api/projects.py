from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import (
    JobEnqueuer,
    get_current_user,
    get_job_enqueuer,
    get_opencloud_client,
    get_session,
)
from photosort.config import settings
from photosort.models import Project, ScanRun, ScanStatus, ScoringRun, TopSelectionRun
from photosort.opencloud.client import OpenCloudClient, OpenCloudError

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(get_current_user)])


class ProjectCreate(BaseModel):
    name: str
    opencloud_path: str


class ScanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ScanStatus
    started_at: datetime
    finished_at: datetime | None
    files_found: int
    photos_added: int
    photos_updated: int
    photos_removed: int
    files_skipped: int
    error_message: str | None


class ScoringRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ScanStatus
    started_at: datetime
    finished_at: datetime | None
    photos_total: int
    photos_processed: int
    suggestions_found: int
    error_message: str | None


class TopSelectionRunSummary(BaseModel):
    """Analog ScoringRunSummary (specs/features/0024-top-photo-selection-category-mix.md) -
    candidates_total/candidates_processed statt photos_total/photos_processed, da hier nur der
    bereits begrenzte Kandidatenpool pro Cluster gezaehlt wird, nicht alle Projektfotos."""

    model_config = ConfigDict(from_attributes=True)

    status: ScanStatus
    started_at: datetime
    finished_at: datetime | None
    top_n_per_cluster: int
    candidates_total: int
    candidates_processed: int
    suggestions_found: int
    error_message: str | None


class SelectTopRequest(BaseModel):
    # ge=1/le=10 serverseitig durchgesetzt (Akzeptanzkriterium der Spec) - nicht nur clientseitig
    # begrenzt.
    top_n_per_cluster: int = Field(ge=1, le=10)


class ProjectOut(BaseModel):
    id: int
    name: str
    opencloud_drive_id: str
    opencloud_path: str
    created_at: datetime
    last_scan: ScanSummary | None = None
    last_scoring_run: ScoringRunSummary | None = None
    last_top_selection_run: TopSelectionRunSummary | None = None


async def _latest_scan_run(session: AsyncSession, project_id: int) -> ScanRun | None:
    result = await session.execute(
        select(ScanRun)
        .where(ScanRun.project_id == project_id)
        .order_by(ScanRun.started_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _latest_scoring_run(session: AsyncSession, project_id: int) -> ScoringRun | None:
    result = await session.execute(
        select(ScoringRun)
        .where(ScoringRun.project_id == project_id)
        .order_by(ScoringRun.started_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _latest_top_selection_run(
    session: AsyncSession, project_id: int
) -> TopSelectionRun | None:
    result = await session.execute(
        select(TopSelectionRun)
        .where(TopSelectionRun.project_id == project_id)
        .order_by(TopSelectionRun.started_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _to_project_out(session: AsyncSession, project: Project) -> ProjectOut:
    scan_run = await _latest_scan_run(session, project.id)
    scoring_run = await _latest_scoring_run(session, project.id)
    top_selection_run = await _latest_top_selection_run(session, project.id)
    return ProjectOut(
        id=project.id,
        name=project.name,
        opencloud_drive_id=project.opencloud_drive_id,
        opencloud_path=project.opencloud_path,
        created_at=project.created_at,
        last_scan=ScanSummary.model_validate(scan_run) if scan_run is not None else None,
        last_scoring_run=(
            ScoringRunSummary.model_validate(scoring_run) if scoring_run is not None else None
        ),
        last_top_selection_run=(
            TopSelectionRunSummary.model_validate(top_selection_run)
            if top_selection_run is not None
            else None
        ),
    )


async def _get_project_or_404(project_id: int, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    client: OpenCloudClient = Depends(get_opencloud_client),
) -> ProjectOut:
    try:
        drive = await client.resolve_drive(settings.opencloud_drive_name or None)
        await client.list_folder(drive.webdav_url, payload.opencloud_path)
    except OpenCloudError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    project = Project(
        name=payload.name,
        opencloud_drive_id=drive.id,
        opencloud_path=payload.opencloud_path,
    )
    session.add(project)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Projekt '{payload.name}' existiert bereits.",
        ) from exc

    await session.refresh(project)
    return await _to_project_out(session, project)


@router.get("", response_model=list[ProjectOut])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[ProjectOut]:
    result = await session.execute(select(Project).order_by(Project.created_at))
    return [await _to_project_out(session, project) for project in result.scalars()]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int, session: AsyncSession = Depends(get_session)
) -> ProjectOut:
    project = await _get_project_or_404(project_id, session)
    return await _to_project_out(session, project)


@router.post("/{project_id}/scan", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    enqueuer: JobEnqueuer = Depends(get_job_enqueuer),
) -> dict[str, str]:
    await _get_project_or_404(project_id, session)
    await enqueuer.enqueue_job("scan_project", project_id)
    return {"status": "queued"}


@router.post("/{project_id}/score", status_code=status.HTTP_202_ACCEPTED)
async def trigger_score(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    enqueuer: JobEnqueuer = Depends(get_job_enqueuer),
) -> dict[str, str]:
    # Analog trigger_scan oben (specs/features/0003-automatic-best-photo-selection.md): derselbe
    # Router-weite dependencies=[Depends(get_current_user)]-Torwaechter, keine Rollenunterscheidung
    # zwischen den beiden bekannten Nutzern - Muss-Kriterium aus dem Security-Abschnitt der Spec.
    await _get_project_or_404(project_id, session)
    await enqueuer.enqueue_job("score_project", project_id)
    return {"status": "queued"}


@router.post("/{project_id}/select-top", status_code=status.HTTP_202_ACCEPTED)
async def trigger_select_top(
    project_id: int,
    payload: SelectTopRequest,
    session: AsyncSession = Depends(get_session),
    enqueuer: JobEnqueuer = Depends(get_job_enqueuer),
) -> dict[str, str]:
    """specs/features/0024-top-photo-selection-category-mix.md: `403` wenn das Feature-Flag aus
    ist, `409` ohne erfolgreichen `ScoringRun` (Phase A muss vorher erfolgreich gelaufen sein),
    sonst enqueue des neuen select_top_photos-Jobs. Legt selbst KEINE TopSelectionRun-Zeile an -
    das erledigt der Job beim tatsaechlichen Start (run_top_selection in worker.py), identisches
    Muster wie trigger_scan/trigger_score oben (ScanRun/ScoringRun werden ebenfalls erst vom Job
    angelegt, nicht synchron hier im Request-Handler)."""
    if not settings.category_selection_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diese Funktion ist derzeit nicht aktiviert.",
        )

    await _get_project_or_404(project_id, session)

    latest_scoring_run = await _latest_scoring_run(session, project_id)
    if latest_scoring_run is None or latest_scoring_run.status != ScanStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fuehre zuerst die lokale Vorauswahl (Ausschuss aussortieren) erfolgreich aus.",
        )

    await enqueuer.enqueue_job("select_top_photos", project_id, payload.top_n_per_cluster)
    return {"status": "queued"}
