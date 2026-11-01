"""Der Export der Endauswahl nach OpenCloud - die drei Antworten der Story an drei Endpunkten.

Anzahl VORHER (`export-preview`, synchron), 202 + Polling WAEHREND (`export`, der Ausloeser),
Bestätigung + Fehlerliste DANACH (`exports/{run_id}`). Dazu `ProjectOut.last_export_run` fuer den
Polling-Zustand (Muster `last_scan`).

SICHERHEIT (S1): Der Torwaechter haengt am ROUTER, nicht am Endpunkt - und genau das ist hier
moeglich, weil KEIN Endpunkt dieses Routers das `User`-Objekt selbst braucht. Der Ausloeser nimmt
kein `current_user` entgegen (das Ergebnis gehoert dem Projekt, `export_runs` ohne `user_id`) -
seine Authentifizierung ist an der Funktionssignatur NICHT sichtbar. Er traegt deshalb DREI
Sicherungen: die Router-Dependency hier, den Eintrag in
`tests/test_auth_guard.py::_protected_router_operations()` und einen eigenen, pfadbenannten
401-Fall in `tests/test_api_export.py`. Die Doppelung traegt, weil der Listeneintrag weder sein
eigenes Vergessen noch eine spaetere Verschiebung des Endpunkts in einen Router ohne
`dependencies`-Liste ueberlebt.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import JobEnqueuer, get_current_user, get_job_enqueuer, get_session
from photosort.final_selection import included_photos
from photosort.models import ExportPhoto, ExportRun, ExportRunStatus, Project

router = APIRouter(prefix="/projects", tags=["export"], dependencies=[Depends(get_current_user)])


async def _ensure_project(session: AsyncSession, project_id: int) -> None:
    """`404` wortgleich mit `api/projects.py::_get_project_or_404`. Ueber eine Abfrage statt
    `session.get`: Nach einem `rollback` darf kein abgelaufenes Objekt der Identity-Map die
    Antwort bestimmen."""
    found = (
        await session.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")


class ExportPreviewOut(BaseModel):
    photo_count: int


class ExportPhotoErrorOut(BaseModel):
    relative_path: str
    error: str


class ExportRunDetailOut(BaseModel):
    id: int
    status: ExportRunStatus
    started_at: datetime
    finished_at: datetime | None
    target_path: str | None
    photo_count: int
    exported_count: int
    failed_count: int
    error_message: str | None
    failed_photos: list[ExportPhotoErrorOut]


@router.get("/{project_id}/export-preview", response_model=ExportPreviewOut)
async def export_preview(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExportPreviewOut:
    """Die Anzahl der Endauswahl-Fotos - dieselbe Ableitung, die der Export gleich nimmt
    (`final_selection.included_photos`), server-autoritativ vor dem Ausloesen."""
    await _ensure_project(session, project_id)
    included = await included_photos(session, project_id)
    return ExportPreviewOut(photo_count=len(included))


@router.post("/{project_id}/export", status_code=status.HTTP_202_ACCEPTED)
async def trigger_export(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    enqueuer: Annotated[JobEnqueuer, Depends(get_job_enqueuer)],
) -> dict[str, str]:
    """Reiht den Export-Job ein und antwortet 202 - der Lauf selbst ist ein Hintergrund-Job
    (Muster `trigger_scan`). Kein `current_user`: das Ergebnis gehoert dem Projekt."""
    await _ensure_project(session, project_id)
    await enqueuer.enqueue_job("export_project", project_id)
    return {"status": "queued"}


@router.get("/{project_id}/exports/{run_id}", response_model=ExportRunDetailOut)
async def get_export_run(
    project_id: int,
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ExportRunDetailOut:
    """Der Lauf samt Fehlerliste je Foto - die Bestätigung DANACH (Anzahl, Zielpfad, Teilfehler).
    Projekt-skopiert: ein Lauf eines anderen Projekts ist `404`, kein Inhalts-Orakel."""
    await _ensure_project(session, project_id)
    run = await session.get(ExportRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Export-Lauf nicht gefunden."
        )
    failed_rows = (
        await session.execute(
            select(ExportPhoto.relative_path, ExportPhoto.error)
            .where(ExportPhoto.export_run_id == run.id, ExportPhoto.error.is_not(None))
            .order_by(ExportPhoto.id)
        )
    ).all()
    return ExportRunDetailOut(
        id=run.id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        target_path=run.target_path,
        photo_count=run.photo_count,
        exported_count=run.exported_count,
        failed_count=run.failed_count,
        error_message=run.error_message,
        failed_photos=[
            ExportPhotoErrorOut(relative_path=relative_path, error=error)
            for relative_path, error in failed_rows
        ],
    )
