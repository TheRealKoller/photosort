"""Event-Zeilen fuer Tests, die `PhotoRanking`-Zeilen von Hand anlegen.

Bewusst kein `test_*`-Modul (wird nicht eingesammelt): `PhotoRanking.event_id` ist ein echter,
nicht-nullbarer Fremdschluessel - eine Rangzeile ohne Event gibt es nicht, und jeder Test, der
frueher `cluster_key="cluster-0"` schrieb, braucht jetzt eine `events`-Zeile. Eine gemeinsame
Stelle statt derselben Hilfsfunktion in acht Dateien.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import CriterionScoringRun, Event


async def event_of_run(
    session: AsyncSession, run: CriterionScoringRun, *, position: int = 1
) -> Event:
    """Das Event mit dieser `position` - angelegt beim ersten Bedarf, danach wiederverwendet.

    Wiederverwendung statt Neuanlage, weil `UniqueConstraint(run, position)` einen zweiten Aufruf
    sonst abwiese und weil ein Test, der zwei Rangzeilen DERSELBEN Partition anlegt, sie auch im
    selben Event haben will."""
    existing = (
        await session.execute(
            select(Event).where(
                Event.criterion_scoring_run_id == run.id, Event.position == position
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    now = datetime.now(UTC).replace(tzinfo=None)
    event = Event(criterion_scoring_run_id=run.id, position=position, started_at=now, ended_at=now)
    session.add(event)
    await session.flush()
    return event


async def event_id_of_run(
    session: AsyncSession, run: CriterionScoringRun, *, position: int = 1
) -> int:
    return (await event_of_run(session, run, position=position)).id
