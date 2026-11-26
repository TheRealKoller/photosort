"""Die Endauswahl eines Projekts: Entscheidungen, Einigkeit und Teilnehmerliste."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from photosort.api.deps import get_current_user, get_session
from photosort.api.persons import photo_person_outs
from photosort.api.photos._conversion import (
    NO_PLACE,
    AlbumParticipantOut,
    AlbumSelectionOut,
    to_photo_out,
)
from photosort.api.photos._reads import (
    album_level_source,
    event_and_location_by_photo_id,
    final_selection_decisions,
    get_project_or_404,
    latest_successful_criterion_scoring_run_id,
    partition_sizes,
    photos_by_id,
    place_in_events,
    ranking_by_photo_id,
    run_events,
)
from photosort.final_selection import selection_state_of
from photosort.models import FinalSelectionDecision, Photo, PhotoRanking, Rating, User
from photosort.motif_strengths import load_effective_strengths
from photosort.persons import load_effective_persons

router = APIRouter()


async def _participants(session: AsyncSession) -> list[AlbumParticipantOut]:
    """Alle Konten als AUSDRUECKLICHE Projektion auf zwei Spalten, nach `user_id` sortiert.

    Nie `model_validate(User)`: `password_hash` und `created_at` duerfen diesen Endpunkt nicht
    erreichen. Die LAENGE dieser Liste ist der Nenner der Regel - sie stammt damit
    aus derselben Leseoperation wie die Anzeige, und die beiden koennen nicht auseinandergehen."""
    rows = (await session.execute(select(User.id, User.username).order_by(User.id))).all()
    return [AlbumParticipantOut(user_id=user_id, username=username) for user_id, username in rows]


@router.get("/projects/{project_id}/album-selection", response_model=AlbumSelectionOut)
async def album_selection(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT: ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # router-weite `dependencies`-Liste (siehe Kopfkommentar der Datei) - ein Endpunkt, der diesen
    # Parameter vergisst, waere STILL OEFFENTLICH. `current_user.id` geht unveraendert an
    # `to_photo_out`: die MENGE dieser Antwort ist zwar nutzerunabhaengig, `PhotoOut.suggestion`
    # bleibt es nicht.
    current_user: User = Depends(get_current_user),
) -> AlbumSelectionOut:
    """Die gemeinsame Endauswahl des Projekts - die Menge, die als Album gilt.

    Sie ist ABGELEITET und nirgends gespeichert: Gespeichert wird allein die ausdrueckliche
    gemeinsame Entscheidung. Einigkeit beider Entwuerfe ist eine VORBELEGUNG, die nur wirkt,
    solange keine Entscheidung vorliegt; eine getroffene Entscheidung ueberlebt umgekehrt jede
    spaetere Entwurfsaenderung und jeden neuen Vorschlagslauf.

    Die Antwort traegt DREI Teile: `participants` (alle Konten, auch das ohne jede Bewertung),
    `has_proposal` (trennt die beiden Leerzustaende) und `items`.

    DIE ANTWORTMENGE IST ADDITIV: `strittig ∪ Endauswahl ∪ entschieden`. Der dritte Teil ist keine
    Redundanz - ein ausdruecklich HERAUSGENOMMENES Bild gehoert nicht zur
    Endauswahl und verschwaende sonst aus beiden Sichten; die Entscheidung liesse sich dann nicht
    mehr aendern, obwohl die Story das ausdruecklich zusagt. Es bleibt stattdessen mit einem
    Anzeigezustand stehen, genau wie ein gestrichenes Foto im Entwurf.
    Kein Ausschluss bildet die Menge. Ein Bild, das BEIDE gestrichen haben und ueber das niemand
    entschieden hat, erscheint hier nicht; der Weg zurueck fuehrt ueber den Einzelentwurf.

    KEINE SEITENWEISE, wie der Entwurfszweig. Die Obergrenze der Antwort
    ist `Vorschlag ∪ jemals bewertet ∪ entschieden`; die Zahl der Abfragen ist fest und
    unabhaengig von der Fotoanzahl.

    SICHERHEIT - Projektbindung: `Photo.project_id == project_id` ist eine UND-Bedingung
    ueber die GESAMTE Kandidatenmenge und steht AUSSERHALB der ODER-Verknuepfung ihrer drei
    Quellen; der Rangzweig haengt zusaetzlich am `criterion_scoring_run_id` des letzten
    erfolgreichen Laufs DIESES Projekts. Zwei der drei Quellen sind projektblind:
    `final_selection_decisions` hat nur `photo_id`, `Rating` nur `(photo_id, user_id)`, und
    `PhotoRanking` traegt keine `project_id`. Ein in die ODER-Verknuepfung gerutschtes
    Projektpraedikat ist syntaktisch unauffaellig und liesse jedes jemals bewertete oder
    entschiedene Foto ALLER Projekte in die Antwort - die Endauswahl eines Projekts enthielte dann
    kohaerent aussehende Fotos eines anderen, und das ist die Menge, die der Export nimmt.
    `photos` filtert nur nach Id und ist ausdruecklich KEINE zweite Verteidigungslinie.

    SICHERHEIT: `users` stammt aus DERSELBEN Leseoperation wie `participants`. Gingen
    beide auseinander, behauptete die Ansicht Einigkeit ueber zwei Teilnehmer, waehrend die Regel
    ueber drei rechnet - kein Feld der Antwort saehe dabei widerspruechlich aus."""
    project = await get_project_or_404(project_id, session)
    album_source = await album_level_source(session, project)

    # (1) Teilnehmer UND Nenner aus EINER Leseoperation.
    participants = await _participants(session)
    users = len(participants)

    latest_run_id = await latest_successful_criterion_scoring_run_id(session, project_id)
    if latest_run_id is None:
        # Ohne erfolgreichen Lauf gibt es weder Vorschlag noch Events, in die einzuordnen waere -
        # die Teilnehmerliste steht trotzdem, sonst waere der Leerzustand nicht von einer Instanz
        # ohne Konten zu unterscheiden.
        return AlbumSelectionOut(participants=participants, has_proposal=False, items=[])

    # (2) Die Events des Laufs - einmal, ueber dieselbe Beschaffung wie der Entwurfszweig.
    events = await run_events(session, latest_run_id)

    # (3) DIE KANDIDATENMENGE, eine Obermenge, in EINER Abfrage: vorgeschlagen ODER entschieden
    # ODER jemals mit einer Albumentscheidung versehen. Sie ist vollstaendig - ohne jede
    # Bewertungszeile sind alle Nutzer einig, und Zugehoerigkeit ohne Entscheidung setzt den
    # Vorschlag voraus.
    #
    # `Rating.status.is_not(None)` und nicht das Vorhandensein der Zeile: eine reine
    # Favoritenzeile ist keine Aussage ueber die Albumzugehoerigkeit und holt ein sonst
    # unbeteiligtes Foto nicht herein.
    ranking = aliased(PhotoRanking)
    decision_row = aliased(FinalSelectionDecision)
    candidate_rows = (
        await session.execute(
            select(Photo.id, Photo.taken_at, ranking.event_id, ranking.selection_position)
            # SICHERHEIT: das Pflichtpraedikat, UND-verknuepft ueber die gesamte Menge.
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

    # `has_proposal` aus den Kandidatenzeilen, ohne eigene Abfrage: ein Foto mit
    # `selection_position` ist ueber das erste Praedikat immer Kandidat.
    has_proposal = any(row.selection_position is not None for row in candidate_rows)

    # (4) Hydratation der Kandidaten - `photo.ratings` samt `Rating.user` ist dort bereits eager
    # geladen, die Zaehlung darunter loest deshalb keinen Lazy-Load aus.
    candidate_ids = [row.id for row in candidate_rows]
    photos = await photos_by_id(session, candidate_ids)
    decisions = await final_selection_decisions(session, candidate_ids)

    # (5) DER ZUSTANDSFILTER: behalten wird, was strittig ist ODER zur Endauswahl gehoert ODER
    # eine Entscheidung traegt - derselbe `selection_state`-Aufruf, den `to_photo_out` danach
    # fuer die Felder benutzt. Ohne ihn stuende jedes von beiden gestrichene Foto in der Antwort.
    kept_rows: list[tuple[int, datetime, int | None]] = []
    for row in candidate_rows:
        # Direkter Zugriff, KEIN `.get(...)` mit stillem Ueberspringen: Jede Kandidaten-Id stammt
        # aus `select(Photo.id)` derselben Transaktion, `photos` liefert sie also alle.
        # Ein fehlender Eintrag waere ein Fehler und soll laut scheitern - stillschweigend
        # uebersprungen verschwaende ein Foto aus dem Album, ohne dass etwas es meldet.
        photo = photos[row.id]
        decision = decisions.get(row.id)
        state = selection_state_of(
            photo,
            proposed=row.selection_position is not None,
            decision=decision,
            user_count=users,
        )
        if state.contested or state.included or decision is not None:
            kept_rows.append((row.id, row.taken_at, row.event_id))

    placed = place_in_events(kept_rows, events.spans, events.position_by_event_id)
    ids = placed.ordered_ids
    rankings_by_id = await ranking_by_photo_id(session, latest_run_id, ids)
    sizes = await partition_sizes(session, latest_run_id)
    place_by_id = await event_and_location_by_photo_id(
        session,
        project_id,
        latest_run_id,
        {photo_id: photos[photo_id] for photo_id in ids},
        placed.event_id_by_photo_id,
        events.out_by_id,
    )
    persons_by_id = await load_effective_persons(session, ids)
    motifs_by_id = await load_effective_strengths(session, ids)
    items = [
        to_photo_out(
            photos[photo_id],
            current_user.id,
            project,
            rankings_by_id.get(photo_id),
            sizes,
            # KEINE `curation_position`: Die Endauswahl ist keine numerierte Auswahl, und eine
            # Zahl hier waere eine Rangaussage ueber eine Menge, die keinen Rang kennt.
            None,
            place_by_id.get(photo_id, NO_PLACE),
            motifs_by_id.get(photo_id),
            decisions=decisions,
            user_count=users,
            persons=photo_person_outs(persons_by_id.get(photo_id, [])),
            album_level_source=album_source,
        )
        for photo_id in ids
    ]
    return AlbumSelectionOut(participants=participants, has_proposal=has_proposal, items=items)
