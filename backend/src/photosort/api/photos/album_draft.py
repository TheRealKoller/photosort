"""Der Album-Entwurf und die Fotoliste: derselbe Bestand, zweimal gelesen.

Der Entwurf ist die Sicht, aus der die Auswahl entsteht; die Fotoliste ist das Nachschlagewerk
daneben. Beide teilen den Rasterfilter und die Kandidatenmenge.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi import Path as PathParam
from pydantic import Field
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from photosort.api.deps import get_current_user, get_session
from photosort.api.persons import photo_person_outs
from photosort.api.photos._conversion import (
    NO_PLACE,
    AlbumDraftOut,
    PhotoListOut,
    RatingFilter,
    to_photo_out,
)
from photosort.api.photos._reads import (
    MAX_QUERY_POSITION,
    PlacedPhotos,
    RunEvents,
    album_level_source,
    event_and_location_by_photo_id,
    event_ids_from_rankings,
    filtered_photo_ids,
    final_selection_decisions,
    get_project_or_404,
    latest_successful_criterion_scoring_run_id,
    partition_sizes,
    photos_by_id,
    place_in_events,
    ranking_by_photo_id,
    run_events,
    user_count,
)
from photosort.models import (
    Photo,
    PhotoMotifAssessment,
    PhotoRanking,
    Rating,
    RatingStatus,
    User,
)
from photosort.motif_strengths import load_effective_strengths
from photosort.persons import load_effective_persons

router = APIRouter()


async def _draft_photo_ids(
    session: AsyncSession,
    project_id: int,
    user_id: int,
    latest_run_id: int,
    run_events: RunEvents,
) -> PlacedPhotos:
    """Der Album-Entwurf DIESES Nutzers:
    `Vorschlag(letzter erfolgreicher Lauf) ∪ Aufgenommen(u) ∪ (Gestrichen(u) ∩ Rangzeile im Lauf)`.

    Er ist ABGELEITET und nirgends gespeichert. "Nie angefasst" ist die Abwesenheit einer eigenen
    Albumentscheidung; daraus folgen "genau ein Entwurf je Nutzer", "ueberdauert die Sitzung" und
    "nur unangefasste Plaetze werden neu befuellt" strukturell statt durchgesetzt.

    EINE ABFRAGE FUER DIE VEREINIGUNG, kein Aneinanderhaengen von Mengen: `PhotoRanking` ist je
    (Lauf, Foto) eindeutig und `Rating` je (Foto, Nutzer) - jedes Foto steht in genau einer Zeile
    und genau einmal in der Antwort.

    KEIN ABLEHNUNGSFILTER: Ein gestrichenes Foto bleibt in der Antwort und traegt seinen Zustand in
    `PhotoOut.ratings[]`; die Ansicht blendet es aus und zeigt es in der Gestrichen-Zeile seines
    Events. Der dritte Zweig nimmt jedes eigene `rejected` an einem Foto mit Rangzeile im Lauf
    auf, auch eine Verwerfung aus dem Bildbestand und unabhaengig vom Vorschlag. Ein gestrichenes
    Foto OHNE Rangzeile (im Ausschuss aussortiert) erfuellt keinen Zweig.

    SICHERHEIT: `Photo.project_id == project_id` steht AUSSERHALB des `or_`, die Rangzeile
    haengt per `outerjoin` am Lauf DIESES Projekts, und alle drei Zweige lesen denselben Alias
    `own_rating` mit `user_id` in der Join-Bedingung. Untersagt sind ein zweiter `Rating`-Alias
    ohne Nutzerbedingung, ein Projektpraedikat innerhalb des `or_` und eine Rangzeile ohne
    Laufpraedikat: Ohne Laufbindung kaemen kohaerente Fotos eines fremden Projekts in die Antwort
    (`PhotoRanking` traegt keine `project_id`), ohne Nutzerbedingung stuenden die Streichungen des
    anderen als eigene in Gestrichen-Zeile und Zaehler.

    Ein Foto, dessen Zeit in keiner Eventspanne einzuordnen ist und das keine Rangzeile hat,
    faellt heraus - die Ausfallrichtung ist "nicht zeigen", nie eine erfundene Gruppe.

    REIHENFOLGE `(events.position, photos.taken_at, photos.id)`, siehe `place_in_events`.

    Die Komplexitaetsklasse ist verbindlich, nicht die Eingabegrenze: Die Menge
    waechst mit den eigenen Handlungen, bis hin zu jedem Foto des Projekts. Die Eventliste kommt
    FERTIG herein und die Zuordnung laeuft in einem Durchgang darueber, nie als Abfrage je Foto."""
    own_rating = aliased(Rating)
    ranking = aliased(PhotoRanking)
    rows = (
        await session.execute(
            select(Photo.id, Photo.taken_at, ranking.event_id)
            .where(Photo.project_id == project_id)
            .outerjoin(
                ranking,
                and_(
                    ranking.photo_id == Photo.id,
                    ranking.criterion_scoring_run_id == latest_run_id,
                ),
            )
            .outerjoin(
                own_rating,
                and_(own_rating.photo_id == Photo.id, own_rating.user_id == user_id),
            )
            .where(
                or_(
                    ranking.selection_position.is_not(None),
                    own_rating.status == RatingStatus.ALBUM_WORTHY,
                    and_(
                        ranking.photo_id.is_not(None),
                        own_rating.status == RatingStatus.REJECTED,
                    ),
                )
            )
        )
    ).all()

    # Die Zeilen werden ausgepackt: ein `Row` ist fuer den Typpruefer kein `tuple`, und die reine
    # Funktion soll ausdruecklich keine SQLAlchemy-Form in ihrer Signatur tragen.
    placement_rows = [(photo_id, taken_at, event_id) for photo_id, taken_at, event_id in rows]
    return place_in_events(placement_rows, run_events.spans, run_events.position_by_event_id)


@router.get("/projects/{project_id}/album-draft", response_model=AlbumDraftOut)
async def album_draft(
    project_id: Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)],
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT: ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # router-weite `dependencies`-Liste und hat kein Vollstaendigkeitsnetz - ein Endpunkt, der
    # diesen Parameter vergisst, waere STILL OEFFENTLICH und gaebe den Entwurf preis.
    current_user: User = Depends(get_current_user),
) -> AlbumDraftOut:
    """Der Album-Entwurf DES ANFRAGENDEN NUTZERS als GANZES samt Eventliste des letzten
    erfolgreichen Laufs; Menge und Reihenfolge siehe `_draft_photo_ids`.

    SICHERHEIT: kein `limit`/`offset`. Die Obergrenze der Antwort ist
    der bewertete Bestand des Laufs zuzueglich der eigenen Aufnahmen; die Menge waechst nur durch
    Handlungen des Anfragenden selbst. Ein abgeschnittener Entwurf, den die Ansicht als
    vollstaendig ausweist, waere ein Zustand, den keine Anzeige als fehlerhaft erkennt.

    Ohne erfolgreichen Lauf sind `events` und `items` leer, auch wenn der Nutzer bereits Fotos
    aufgenommen hat - es gibt dann weder Vorschlag noch Events, in die einzuordnen waere."""
    project = await get_project_or_404(project_id, session)
    album_source = await album_level_source(session, project)

    latest_run_id = await latest_successful_criterion_scoring_run_id(session, project_id)
    if latest_run_id is None:
        return AlbumDraftOut(events=[], items=[], eligible_candidate_count=0)

    events = await run_events(session, latest_run_id)
    content = await _draft_photo_ids(session, project_id, current_user.id, latest_run_id, events)
    ids = content.ordered_ids
    photos = await photos_by_id(session, ids)
    rankings_by_id = await ranking_by_photo_id(session, latest_run_id, ids)
    sizes = await partition_sizes(session, latest_run_id)
    place_by_id = await event_and_location_by_photo_id(
        session,
        project_id,
        latest_run_id,
        photos,
        # Die Abbildung kommt aus der Entwurfsherleitung, NICHT aus den Rangzeilen: ein
        # aufgenommenes Foto ohne Rangzeile haette dort keinen Eintrag und verloere sein Event,
        # obwohl es in der Liste steht.
        content.event_id_by_photo_id,
        events.out_by_id,
    )
    motifs_by_id = await load_effective_strengths(session, ids)
    persons_by_id = await load_effective_persons(session, ids)
    decisions = await final_selection_decisions(session, ids)
    users = await user_count(session)
    items = [
        to_photo_out(
            photos[photo_id],
            current_user.id,
            project,
            rankings_by_id.get(photo_id),
            sizes,
            content.curation_positions,
            place_by_id.get(photo_id, NO_PLACE),
            motifs_by_id.get(photo_id),
            decisions=decisions,
            user_count=users,
            persons=photo_person_outs(persons_by_id.get(photo_id, [])),
            album_level_source=album_source,
        )
        for photo_id in ids
    ]
    eligible_candidate_count = (
        await session.execute(
            select(func.count())
            .select_from(PhotoRanking)
            .where(
                # SICHERHEIT: das Laufpraedikat bindet an dieses Projekt.
                PhotoRanking.criterion_scoring_run_id == latest_run_id,
                PhotoRanking.rank_score.is_not(None),
                ~exists().where(
                    PhotoMotifAssessment.photo_id == PhotoRanking.photo_id,
                    PhotoMotifAssessment.excluded_document.is_(True),
                ),
            )
        )
    ).scalar_one()
    return AlbumDraftOut(
        events=events.ordered,
        items=items,
        eligible_candidate_count=eligible_candidate_count,
    )


@router.get("/projects/{project_id}/photos", response_model=PhotoListOut)
async def list_photos(
    project_id: int,
    rating_status: RatingFilter | None = None,
    # Der alte Entwurfsmodus, ersetzt durch `GET /projects/{id}/album-draft`. Er steht hier noch
    # als `None`-typisierter Parameter, damit ein Aufruf mit ihm LAUT scheitert (`422`) statt
    # still ignoriert zu werden - in BEIDEN Belegungen. Ein vom Service Worker noch nicht
    # ersetzter Client fiele mit `draft=true` sonst still in den Listing-Zweig und zeigte den
    # vollen Bestand als Entwurf, mit einem Zaehler, der niemandes Eingriffe misst.
    draft: None = Query(None, include_in_schema=False),
    # Der alte Auswahlparameter, ersetzt. Er steht hier noch als `None`-typisierter
    # Parameter, damit ein Aufruf mit ihm LAUT scheitert (`422`) statt still ignoriert zu werden -
    # in BEIDEN Belegungen. `selection=false` ist der gefaehrlichere Fall: heute ein gueltiger
    # Aufruf, der sonst still in den Listing-Zweig fiele. Die Antwortmenge des Nachfolgers ist
    # zudem NUTZERABHAENGIG; ein stehengebliebener Aufrufer bekaeme also nicht bloss eine andere
    # Menge, sondern eine mit anderer Bedeutung.
    selection: None = Query(None, include_in_schema=False),
    # Der alte Kuratierungsparameter, ERSATZLOS entfallen. Er steht hier noch als
    # `None`-typisierter Parameter, damit ein Aufruf mit ihm LAUT scheitert (`422`) statt still
    # ignoriert zu werden: FastAPI uebergeht einen unbekannten Query-Parameter kommentarlos, und
    # ein stehengebliebener Aufrufer bekaeme dann den vollen Listing-Zweig statt einer Auswahl -
    # ohne dass irgendwo ein Fehler sichtbar wuerde. Ein Uebergangsweg, der beide Parameter
    # kennt, entsteht bewusst nicht; er waere eine zweite Auswahlregel.
    top_n_per_event: None = Query(None, include_in_schema=False),
    # Ohne diesen Filter kann die Oberflaeche die beiden Fotos fuer den Versatz-Vorschlag nicht
    # anbieten. `ge=1` schliesst `0` und negative Werte aus, `le` verhindert, dass ein Wert
    # jenseits von 2^63 unter SQLite einen OverflowError und damit eine 500 statt einer leeren
    # Liste erzeugt (Muster `MAX_QUERY_POSITION`).
    camera_id: int | None = Query(None, ge=1, le=MAX_QUERY_POSITION),
    # Der Personenfilter: hoechstens zwei Werte je `ge=1, le=MAX_QUERY_POSITION`,
    # danach dedupliziert. Gefiltert wird ueber die Id, nie ueber einen Namen - ein Name gehoerte
    # sonst in Zugriffslog und Browserverlauf. Der Album-Entwurf kennt ihn nicht: er wird immer
    # vollstaendig geliefert und im Client eingeschraenkt, damit seine Zaehlung stimmt.
    person_id: list[Annotated[int, Field(ge=1, le=MAX_QUERY_POSITION)]] = Query(
        default_factory=list, max_length=2
    ),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhotoListOut:
    project = await get_project_or_404(project_id, session)
    album_source = await album_level_source(session, project)

    ids, total = await filtered_photo_ids(
        session,
        project_id,
        current_user.id,
        rating_status,
        limit,
        offset,
        camera_id,
        sorted(set(person_id)),
    )
    photos = await photos_by_id(session, ids)
    # RankingOut wird AUCH hier im Standard-Listing-Zweig befüllt, nicht nur bei
    # top_n_per_event - Grid-/Detailansicht sollen ebenfalls Rang-Score/-Position zeigen
    # koennen, unabhaengig vom top_n_per_event-Kuratierungsmodus.
    latest_run_id = await latest_successful_criterion_scoring_run_id(session, project_id)
    rankings_by_id = (
        await ranking_by_photo_id(session, latest_run_id, ids) if latest_run_id is not None else {}
    )
    sizes = await partition_sizes(session, latest_run_id) if latest_run_id is not None else {}
    place_by_id = await event_and_location_by_photo_id(
        session, project_id, latest_run_id, photos, event_ids_from_rankings(rankings_by_id)
    )
    motifs_by_id = await load_effective_strengths(session, ids)
    persons_by_id = await load_effective_persons(session, ids)
    decisions = await final_selection_decisions(session, ids)
    users = await user_count(session)
    items = [
        to_photo_out(
            photos[photo_id],
            current_user.id,
            project,
            rankings_by_id.get(photo_id),
            sizes,
            # Ohne angeforderte Auswahl traegt JEDE Zugehoerigkeit `curation_position = null` - es
            # gibt in diesem Modus keine Auswahl, zu der sie eine Position haben koennte.
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
    return PhotoListOut(items=items, total=total)
