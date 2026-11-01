"""Die abgeleitete Endauswahl als inkludierte MENGE - die eine Stelle, die der Export nimmt.

Die Regel selbst lebt REIN in `album_selection.py::selection_state` und nur dort; dieses Modul
ist ihre DB-gestuetzte Anwendung: Es laedt die Kandidaten eines Projekts (vorgeschlagen ODER
entschieden ODER jemals mit einer Albumentscheidung versehen), rechnet je Foto den Zustand und
liefert die inkludierte Menge zurueck.

GENAU EINE STELLE (Auflage S9 der Spec 0431): Der Lesepfad `api/photos.py::album_selection` und
der Export-Worker rufen dieselbe Regel ueber denselben Einstiegspunkt. Eine zweite Ableitung
lieferte still eine andere, plausibel aussehende Menge - ein falsch abgeleiteter Zielordner oder
eine still abgeflachte Dateistruktur wirft keine Ausnahme, sie liefert ein plausibel aussehendes
Ergebnis.

Dieses Modul importiert AUSDRUECKLICH NICHTS aus `api/` (dieselbe Regel wie `client.py` gegenueber
`worker.py`): `final_selection` wird sowohl vom API-Prozess als auch vom Worker importiert, und ein
`api/`-Import zoegte die gesamte Request-Schicht (und ihre Abhaengigkeiten) in den Worker-Pfad.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from photosort.album_selection import SelectionState, selection_state
from photosort.models import (
    CriterionScoringRun,
    FinalSelectionDecision,
    Photo,
    PhotoRanking,
    Rating,
    RatingStatus,
    ScanStatus,
    User,
)


@dataclass(frozen=True)
class IncludedPhoto:
    """EIN zur Endauswahl gehoerendes Foto: `relative_path` ist zugleich Quell- und Zielpfad
    (der Zielordner spiegelt die Quellstruktur, ADR 0136 Punkt 2)."""

    photo_id: int
    relative_path: str


def selection_state_of(
    photo: Photo, *, proposed: bool, decision: bool | None, user_count: int
) -> SelectionState:
    """Die Eingaenge der Endauswahl-Regel aus EINEM Foto - die Regel selbst lebt in
    `album_selection.py` und nur dort.

    Die beiden Zaehlungen laufen ueber `Rating.status`, NIE ueber das Vorhandensein der Zeile:
    Seit ADR 0098 kann eine Zeile allein den Favoriten tragen, und ein Existenztest machte aus
    einer Auszeichnung eine Streichung.

    EINE Stelle fuer alle Leser (`_to_photo_out`, der Zustandsfilter von `album_selection` und
    `included_photos`): Mehrmals geschrieben liefen die Felder an dem Tag auseinander, an dem
    eine der Stellen sich aendert."""
    return selection_state(
        taken=sum(1 for r in photo.ratings if r.status is RatingStatus.ALBUM_WORTHY),
        rejected=sum(1 for r in photo.ratings if r.status is RatingStatus.REJECTED),
        user_count=user_count,
        proposed=proposed,
        decision=decision,
    )


async def included_photos(session: AsyncSession, project_id: int) -> list[IncludedPhoto]:
    """Die inkludierte Endauswahlmenge eines Projekts, deterministisch nach `photo_id`.

    `user_count` ist die GLOBALE Nutzerzahl (dieselbe Ableitung wie `api/photos.py::_user_count`),
    der Vorschlagsbezug der letzte erfolgreiche Kriterien-Lauf. Ohne einen solchen Lauf gibt es
    weder Vorschlag noch Einigkeit - die Menge ist leer."""
    user_count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    latest_run_id = (
        await session.execute(
            select(CriterionScoringRun.id)
            .where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
            )
            .order_by(CriterionScoringRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_run_id is None:
        return []

    # DIE KANDIDATENMENGE, dieselbe Ableitung wie `api/photos.py::album_selection`: vorgeschlagen
    # ODER entschieden ODER jemals mit einer Albumentscheidung versehen. `Rating.status.is_not(None)`
    # und nicht das Vorhandensein der Zeile.
    ranking = aliased(PhotoRanking)
    decision_row = aliased(FinalSelectionDecision)
    candidate_rows = (
        await session.execute(
            select(Photo.id, Photo.relative_path, ranking.selection_position)
            .where(Photo.project_id == project_id)
            .outerjoin(
                ranking,
                and_(
                    ranking.photo_id == Photo.id,
                    ranking.criterion_scoring_run_id == latest_run_id,
                ),
            )
            .outerjoin(decision_row, decision_row.photo_id == Photo.id)
            .where(
                or_(
                    ranking.selection_position.is_not(None),
                    decision_row.photo_id.is_not(None),
                    Photo.id.in_(select(Rating.photo_id).where(Rating.status.is_not(None))),
                )
            )
        )
    ).all()

    photo_ids = [row.id for row in candidate_rows]
    photos_by_id = (
        {
            photo.id: photo
            for photo in (
                await session.execute(
                    select(Photo)
                    .where(Photo.id.in_(photo_ids))
                    .options(selectinload(Photo.ratings))
                )
            ).scalars()
        }
        if photo_ids
        else {}
    )
    decisions = (
        {
            photo_id: included
            for photo_id, included in (
                await session.execute(
                    select(FinalSelectionDecision.photo_id, FinalSelectionDecision.included).where(
                        FinalSelectionDecision.photo_id.in_(photo_ids)
                    )
                )
            ).all()
        }
        if photo_ids
        else {}
    )

    included: list[IncludedPhoto] = []
    for row in candidate_rows:
        photo = photos_by_id[row.id]
        state = selection_state_of(
            photo,
            proposed=row.selection_position is not None,
            decision=decisions.get(row.id),
            user_count=user_count,
        )
        if state.included:
            included.append(IncludedPhoto(photo_id=row.id, relative_path=photo.relative_path))
    included.sort(key=lambda entry: entry.photo_id)
    return included
