"""Der Merker "Ablaufuebersicht gesehen" - je Person und Projekt, ein Lese- und ein Schreibweg.

SICHERHEIT (S1): Der Torwaechter haengt am ROUTER, der Router steht in
`tests/test_auth_guard.py::_protected_router_operations()`, und jeder Endpunkt hat in
`tests/test_api_project_overview.py` einen eigenen 401-Fall. Ohne die Router-Dependency waere
ein spaeter ergaenzter Endpunkt dieses Routers still oeffentlich.

SICHERHEIT (S2/S3): Die Person kommt AUSSCHLIESSLICH aus `get_current_user` - kein Body, kein
Query-Parameter. Gelesen und geschrieben wird genau die Zeile `(current_user.id, project_id)`,
und die Antwort ist genau `{"seen": bool}`. Der Zustand der anderen Person verlaesst den Server
auf keinem Weg; er steht deshalb auch nicht an `ProjectOut`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.models import Project, ProjectOverviewSeen, User

router = APIRouter(
    prefix="/projects", tags=["project-overview"], dependencies=[Depends(get_current_user)]
)


class OverviewSeenOut(BaseModel):
    seen: bool


async def _ensure_project(session: AsyncSession, project_id: int) -> None:
    """`404` wortgleich mit `api/projects.py::_get_project_or_404` (S4). Ueber eine Abfrage statt
    `session.get`: Nach einem `rollback` darf kein abgelaufenes Objekt der Identity-Map die
    Antwort bestimmen."""
    found = (
        await session.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")


@router.get("/{project_id}/overview-seen", response_model=OverviewSeenOut)
async def get_overview_seen(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OverviewSeenOut:
    """Ob die angemeldete Person die Uebersicht dieses Projekts schon geschlossen hat. Ohne
    Nebenwirkung: Lesen legt nie eine Zeile an."""
    user_id = current_user.id
    await _ensure_project(session, project_id)
    row = await session.get(ProjectOverviewSeen, (user_id, project_id))
    return OverviewSeenOut(seen=row is not None)


@router.put("/{project_id}/overview-seen", status_code=status.HTTP_204_NO_CONTENT)
async def mark_overview_seen(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Merkt "gesehen" fuer die angemeldete Person - idempotent, nie `500`.

    Zwischen Pruefung und Einfuegen kann ein zweiter Tab derselben Person dieselbe Zeile oder
    eine Projektloeschung das Projekt wegnehmen; beides endet im `IntegrityError` des `commit`.
    Gefangen wird nur dieser: `rollback`, dann erneute Projektpruefung - `404`, wenn das Projekt
    fort ist, sonst `204`, weil die Zeile dann bereits steht."""
    user_id = current_user.id
    await _ensure_project(session, project_id)
    if await session.get(ProjectOverviewSeen, (user_id, project_id)) is None:
        session.add(ProjectOverviewSeen(user_id=user_id, project_id=project_id))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await _ensure_project(session, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
