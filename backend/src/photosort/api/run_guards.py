"""Sperren, die ein Endpunkt vor dem Schreiben prüft (HTTP-Schicht).

Ein `409` trägt Statuscode und deutschen Nutzertext; eine solche Prüfung bleibt deshalb in der
HTTP-Schicht, auch wenn sie von mehreren Endpunkt-Modulen gebraucht wird.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import CriterionScoringRun, ScanStatus


async def reject_while_a_criterion_run_is_active(
    session: AsyncSession,
    project_id: int,
    *,
    afterwards: str = "Der Richtwert kann danach gesetzt werden.",
) -> None:
    """`409`, solange der Kriterien-Lauf dieses Projekts laeuft oder wartet.

    ENGER als `api/cameras.py::_reject_while_a_run_is_active`, das auch den Scan erfasst: nur
    dieser Lauftyp schreibt `selection_position`, der Scan nicht.

    Der laufende Lauf liest den Richtwert unmittelbar vor seinem Erfolgsvermerk. Ohne diesen
    Waechter schreibt der Endpunkt den neuen Wert, waehrend der Lauf noch mit dem alten rechnet -
    Ergebnis ist ein Vorschlag nach altem Richtwert unter einer Oberflaeche, die den neuen anzeigt.
    Die Abweichung heilt erst beim naechsten Ausloeser und ist bis dahin nirgends als Fehler
    sichtbar.

    Geprueft wird nur der NEUESTE Lauf (Muster `delete_project`), damit ein haengengebliebener
    Altlauf nicht dauerhaft blockiert - ein solcher wird ohnehin vom Watchdog auf FAILED
    gesetzt.

    `afterwards` ist der Nachsatz, der dem Nutzer sagt, WAS danach moeglich ist - der Richtwert
    oder die Modellwahl. Der Statuscode und der erste Satz bleiben wortgleich."""
    latest = (
        (
            await session.execute(
                select(CriterionScoringRun.status)
                .where(CriterionScoringRun.project_id == project_id)
                .order_by(CriterionScoringRun.started_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if latest in (ScanStatus.RUNNING, ScanStatus.QUEUED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fuer dieses Projekt laeuft gerade eine Klassifizierung. " + afterwards,
        )
