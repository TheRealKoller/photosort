"""Fotoanzahl und Aufnahmezeitraum eines Projekts - die EINE Definition dieser drei Zahlen.

`GET /projects` und `GET /projects/{id}/stats` zeigen dieselben Werte und beziehen sie von hier,
statt jeder seine eigene Zaehlung zu schreiben. Zwei Definitionen liefen spaetestens dann
auseinander, wenn eine von ihnen auf `taken_at_original` umgestellt wuerde, und die Uebersicht
widerspraeche der Statistikseite desselben Projekts, ohne dass ein Test das bemerkte.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Function, select
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import Photo


@dataclass(frozen=True)
class PhotoAggregate:
    """Die drei Zahlen eines Projekts.

    `photo_count == 0` ist eine Aussage ("keine Fotos"), die beiden `None` sind die Abwesenheit
    einer Aussage ("kein Zeitraum bekannt"). Die Unterscheidung traegt bis in die Anzeige und
    darf an keiner Stelle zu einem `0` oder einem `or`-Fallback verschmelzen."""

    photo_count: int
    taken_at_earliest: datetime | None
    taken_at_latest: datetime | None


#: Der Wert eines Projekts OHNE Fotos. Ein solches Projekt fehlt im Ergebnis der Gruppierung -
#: es bekommt diese benannte Vorgabe, nie eine geratene oder uebernommene Zahl.
EMPTY_PHOTO_AGGREGATE = PhotoAggregate(photo_count=0, taken_at_earliest=None, taken_at_latest=None)


def photo_count_expression() -> Function[int]:
    """Zaehlt `photos.id`, nicht `*`: unter dem LEFT JOIN auf `photo_scores` in `api/stats.py`
    zaehlt der Ausdruck damit Fotos und nicht Join-Zeilen."""
    return sa_func.count(Photo.id)


def taken_at_earliest_expression() -> Function[datetime]:
    return sa_func.min(Photo.taken_at)


def taken_at_latest_expression() -> Function[datetime]:
    return sa_func.max(Photo.taken_at)


async def photo_aggregates_by_project(
    session: AsyncSession, project_ids: Sequence[int]
) -> dict[int, PhotoAggregate]:
    """Die drei Zahlen fuer MEHRERE Projekte in EINER gruppierten Abfrage.

    SICHERHEIT (Spec 0375, S2): `WHERE project_id IN (ids)` zusammen mit `GROUP BY project_id`,
    das Ergebnis strikt ueber `project_id` geschluesselt. Die Ausfallrichtung einer fehlenden
    Einschraenkung ist keine Fehlermeldung, sondern eine plausible fremde Zahl - ohne sie truege
    jede Karte den Bestand der gesamten Instanz, ohne dass irgendetwas rot wird.

    Eine leere Id-Menge fragt die Datenbank nichts: `IN ()` ist als Frage sinnlos und in manchen
    Dialekten ungueltiges SQL.
    """
    ids = list(project_ids)
    if not ids:
        return {}

    rows = await session.execute(
        select(
            Photo.project_id,
            photo_count_expression(),
            taken_at_earliest_expression(),
            taken_at_latest_expression(),
        )
        .where(Photo.project_id.in_(ids))
        .group_by(Photo.project_id)
    )
    return {
        project_id: PhotoAggregate(
            photo_count=int(photo_count),
            taken_at_earliest=taken_at_earliest,
            taken_at_latest=taken_at_latest,
        )
        for project_id, photo_count, taken_at_earliest, taken_at_latest in rows.all()
    }


async def photo_aggregate_for_project(session: AsyncSession, project_id: int) -> PhotoAggregate:
    """Derselbe Weg fuer ein einzelnes Projekt - ausdruecklich kein zweiter Rechenweg."""
    aggregates = await photo_aggregates_by_project(session, [project_id])
    return aggregates.get(project_id, EMPTY_PHOTO_AGGREGATE)
