"""Die laufenden und wartenden Vorgaenge eines Projekts: Uebersicht und Abbruch.

Ein Vorgang ist genau eine Lauf-Zeile der fuenf Arten (`scan`, `ausschuss`, `classification`,
`export`, `review`). Der Abbruch ist ein Merker (`cancel_requested_at`), kein Signal: der Worker
liest ihn an seinen Pruefpunkten und beendet den Lauf selbst als `cancelled`.

SICHERHEIT (S1): Der Torwaechter haengt am ROUTER. Jede Anweisung dieses Moduls traegt
`project_id` in ihrer `WHERE`-Klausel - eine fremde Lauf-Id ist damit `404` und kein Inhaltsorakel.
Ein Abbruch aendert ausschliesslich den Merker und bei wartenden Laeufen den Endzustand; er
loescht nichts und liest keine Nutzdaten.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel
from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.clock import now_utc
from photosort.models import (
    ClassificationReview,
    CriterionScoringRun,
    ExportRun,
    ExportRunStatus,
    Project,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/projects/{project_id}/operations",
    tags=["operations"],
    dependencies=[Depends(get_current_user)],
)


class OperationKind(StrEnum):
    SCAN = "scan"
    AUSSCHUSS = "ausschuss"
    CLASSIFICATION = "classification"
    EXPORT = "export"
    REVIEW = "review"


# Der deutsche Anzeigename steht NUR hier: die Uebersicht und der Bestaetigungsdialog der
# Oberflaeche nennen denselben Vorgang, und zwei Textlisten drifteten auseinander.
OPERATION_LABELS: dict[OperationKind, str] = {
    OperationKind.SCAN: "Scan",
    OperationKind.AUSSCHUSS: "Ausschuss",
    OperationKind.CLASSIFICATION: "Klassifizierung",
    OperationKind.EXPORT: "Export",
    OperationKind.REVIEW: "Pruefung",
}

# Modell und Status-Enum je Vorgang. Beide Enums tragen dieselben Mitgliedsnamen; die Tabellen
# unterscheiden sich nur in ihrer Klasse.
_MODELS: dict[OperationKind, tuple[type[Any], type[ScanStatus] | type[ExportRunStatus]]] = {
    OperationKind.SCAN: (ScanRun, ScanStatus),
    OperationKind.AUSSCHUSS: (ScoringRun, ScanStatus),
    OperationKind.CLASSIFICATION: (CriterionScoringRun, ScanStatus),
    OperationKind.EXPORT: (ExportRun, ExportRunStatus),
    OperationKind.REVIEW: (ClassificationReview, ScanStatus),
}

# Die Pruefung ist der einzige Vorgang, von dem mehrere gleichzeitig offen sein koennen.
_ALL_OPEN_KINDS = (OperationKind.REVIEW,)

# Deklarative Obergrenze der fremdgesteuerten Pfad-Ids, VOR jeder Verwendung: ein Pydantic-`int`
# ist unbeschraenkt, und jenseits von 2^63 antwortete SQLite mit `500` statt `404`.
_MAX_ID = 1_000_000_000


class OperationOut(BaseModel):
    kind: OperationKind
    run_id: int
    label: str
    status: ScanStatus | ExportRunStatus
    cancel_requested: bool


class OperationsOut(BaseModel):
    operations: list[OperationOut]


class CancelOut(BaseModel):
    kind: OperationKind
    run_id: int
    status: ScanStatus | ExportRunStatus
    outcome: str


class CancelAllOut(BaseModel):
    cancelled: list[CancelOut]


async def _ensure_project(session: AsyncSession, project_id: int) -> None:
    """`404` wortgleich mit `api/projects.py::_get_project_or_404`: ein unbekanntes Projekt
    antwortet nicht mit einer leeren Liste, als waere dort nichts zu tun."""
    found = (
        await session.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")


async def _open_rows(session: AsyncSession, project_id: int, kind: OperationKind) -> list[Any]:
    """Die offenen Zeilen EINES Vorgangs, neueste zuerst - je Art hoechstens eine, ausser bei der
    Pruefung, von der mehrere offen sein koennen."""
    model, status_enum = _MODELS[kind]
    statement = (
        select(model)
        .where(
            model.project_id == project_id,
            model.status.in_((status_enum.QUEUED, status_enum.RUNNING)),
        )
        .order_by(model.started_at.desc(), model.id.desc())
    )
    if kind not in _ALL_OPEN_KINDS:
        statement = statement.limit(1)
    return list((await session.execute(statement)).scalars().all())


async def _operation_out(kind: OperationKind, row: Any) -> OperationOut:
    return OperationOut(
        kind=kind,
        run_id=row.id,
        label=OPERATION_LABELS[kind],
        status=row.status,
        cancel_requested=row.cancel_requested_at is not None,
    )


async def _open_operations(session: AsyncSession, project_id: int) -> list[OperationOut]:
    operations: list[OperationOut] = []
    for kind in OperationKind:
        for row in await _open_rows(session, project_id, kind):
            operations.append(await _operation_out(kind, row))
    return operations


async def _mark_linked_remote_run(session: AsyncSession, criterion_run_id: int) -> None:
    """Setzt den Merker auch an der Cloud-Phase des Klassifizierungslaufs: sie laeuft in einem
    eigenen Job und liest ihre eigene Zeile."""
    remote_id = (
        await session.execute(
            select(CriterionScoringRun.remote_category_classification_run_id).where(
                CriterionScoringRun.id == criterion_run_id
            )
        )
    ).scalar_one_or_none()
    if remote_id is None:
        return
    await session.execute(
        update(RemoteCategoryClassificationRun)
        .where(
            RemoteCategoryClassificationRun.id == remote_id,
            RemoteCategoryClassificationRun.status.in_((ScanStatus.QUEUED, ScanStatus.RUNNING)),
            RemoteCategoryClassificationRun.cancel_requested_at.is_(None),
        )
        .values(cancel_requested_at=now_utc())
    )


async def _request_cancel(
    session: AsyncSession, project_id: int, kind: OperationKind, run_id: int
) -> CancelOut:
    """Merker setzen, ohne je `409` zu antworten: ein zweiter Abbruch, ein Abbruch nach Lauf-Ende
    und ein verlorenes Rennen ergeben `already_finished` mit dem aktuellen Zustand."""
    model, status_enum = _MODELS[kind]
    now = now_utc()

    # Ein wartender Lauf endet SOFORT: es gibt keinen Worker, der ihn noch abschliessen muesste,
    # weil seine Uebernahme einen gesetzten Merker ablehnt.
    ended_queued = await session.execute(
        update(model)
        .where(
            model.id == run_id,
            model.project_id == project_id,
            model.status == status_enum.QUEUED,
            model.cancel_requested_at.is_(None),
        )
        .values(
            cancel_requested_at=now,
            status=status_enum.CANCELLED,
            finished_at=now,
        )
    )
    if cast("CursorResult[Any]", ended_queued).rowcount == 1:
        if kind is OperationKind.CLASSIFICATION:
            await _mark_linked_remote_run(session, run_id)
        await session.commit()
        logger.info(
            "Abbruch eines wartenden Laufs: project_id=%s kind=%s run_id=%s "
            "outcome=cancel_requested",
            project_id,
            kind.value,
            run_id,
        )
        return CancelOut(
            kind=kind,
            run_id=run_id,
            status=status_enum.CANCELLED,
            outcome="cancel_requested",
        )

    # Ein laufender Lauf bekommt nur den Merker: den Endzustand schreibt der Worker.
    marked_running = await session.execute(
        update(model)
        .where(
            model.id == run_id,
            model.project_id == project_id,
            model.status == status_enum.RUNNING,
            model.cancel_requested_at.is_(None),
        )
        .values(cancel_requested_at=now)
    )
    if cast("CursorResult[Any]", marked_running).rowcount == 1:
        if kind is OperationKind.CLASSIFICATION:
            await _mark_linked_remote_run(session, run_id)
        await session.commit()
        logger.info(
            "Abbruch eines laufenden Laufs angefordert: project_id=%s kind=%s run_id=%s "
            "outcome=cancel_requested",
            project_id,
            kind.value,
            run_id,
        )
        return CancelOut(
            kind=kind,
            run_id=run_id,
            status=status_enum.RUNNING,
            outcome="cancel_requested",
        )

    current = (
        await session.execute(
            select(model.status).where(model.id == run_id, model.project_id == project_id)
        )
    ).scalar_one_or_none()
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lauf nicht gefunden.")
    await session.commit()
    logger.info(
        "Abbruch ohne Wirkung: project_id=%s kind=%s run_id=%s outcome=already_finished",
        project_id,
        kind.value,
        run_id,
    )
    return CancelOut(kind=kind, run_id=run_id, status=current, outcome="already_finished")


@router.get("", response_model=OperationsOut)
async def list_operations(
    project_id: Annotated[int, Path(ge=1, le=_MAX_ID)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OperationsOut:
    """Was gerade laeuft oder wartet - die Vorschau der Aktion „Alle abbrechen“. Eine leere Liste
    sperrt sie."""
    await _ensure_project(session, project_id)
    return OperationsOut(operations=await _open_operations(session, project_id))


@router.post("/cancel-all", response_model=CancelAllOut)
async def cancel_all_operations(
    project_id: Annotated[int, Path(ge=1, le=_MAX_ID)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CancelAllOut:
    """Bricht jeden offenen Vorgang DIESES Projekts ab. Die Menge stammt aus derselben Abfrage wie
    die Uebersicht; Vorgaenge anderer Projekte bleiben unberuehrt."""
    await _ensure_project(session, project_id)
    cancelled = [
        await _request_cancel(session, project_id, operation.kind, operation.run_id)
        for operation in await _open_operations(session, project_id)
    ]
    return CancelAllOut(cancelled=cancelled)


@router.post("/{kind}/{run_id}/cancel", response_model=CancelOut)
async def cancel_operation(
    project_id: Annotated[int, Path(ge=1, le=_MAX_ID)],
    kind: OperationKind,
    run_id: Annotated[int, Path(ge=1, le=_MAX_ID)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CancelOut:
    await _ensure_project(session, project_id)
    return await _request_cancel(session, project_id, kind, run_id)
