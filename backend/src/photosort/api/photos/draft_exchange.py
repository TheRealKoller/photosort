"""Alternativen zum Entwurfsfoto und der Austausch: je ein Aufruf, eine Transaktion.

Der Alternativen-Lesepfad zeigt, was an derselben Stelle des Laufs noch zur Wahl steht; der
Austausch und sein Rueckgaengig schreiben Bewertungen und Ereignis in genau einer Transaktion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Path as PathParam
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from photosort.album_stage import load_album_levels
from photosort.api.deps import get_current_user, get_session
from photosort.api.persons import photo_person_outs
from photosort.api.photos._conversion import NO_PLACE, PhotoOut, to_photo_out
from photosort.api.photos._reads import (
    MAX_QUERY_POSITION,
    album_level_source,
    event_and_location_by_photo_id,
    event_ids_from_rankings,
    final_selection_decisions,
    get_project_or_404,
    latest_successful_criterion_scoring_run_id,
    partition_sizes,
    photos_by_id,
    ranking_by_photo_id,
    user_count,
)
from photosort.api.ratings import RatingWriteOut, write_own_rating
from photosort.feedback_log import record_exchange
from photosort.models import CategoryMethod, Photo, PhotoRanking, Rating, RatingStatus, User
from photosort.motif_strengths import load_effective_strengths
from photosort.persons import load_effective_persons
from photosort.selection import (
    QualityCandidate,
    SeriesWindow,
    TimedCandidate,
    order_alternatives_chronologically,
    order_by_quality,
    series_window,
)

router = APIRouter()


class DraftAlternativesOut(BaseModel):
    """Die Antwortform des Alternativen-Endpunkts.

    `offset` ist der Beginn der ausgelieferten Seite in der vollen Reihe, `reference_index` die
    Stelle des Bezugsbildes darin (Zahl der Kandidaten davor) - ohne Bezugsbild `None`.
    `series_rest` ist die Zahl der Serienaufnahmen jenseits des Bandfensters (nur mit `series`,
    sonst `0`). Alle vier sind wie `total` Funktionen des ANFRAGENDEN Nutzers."""

    items: list[PhotoOut]
    total: int
    offset: int
    reference_index: int | None
    series_rest: int


def _no_alternatives() -> DraftAlternativesOut:
    """Der EINE Leerkoerper jeder gescheiterten Aufloesung - byte-gleich, ohne Rueckspiegelung
    eines Werts. Ein abweichender Koerper je Fehlerursache waere ein Existenz-Orakel."""
    return DraftAlternativesOut(items=[], total=0, offset=0, reference_index=None, series_rest=0)


_SERIES_WITHOUT_REFERENCE = "series ist nur zusammen mit photo_id zulaessig."


@dataclass(frozen=True)
class _AlternativePage:
    """Die geordnete Restmenge und die geschnittene Seite aus EINER Kandidatenabfrage."""

    ids: list[int]
    total: int
    offset: int
    reference_index: int | None
    window: SeriesWindow | None


async def _alternative_page(
    session: AsyncSession,
    *,
    latest_run_id: int,
    event_id: int,
    current_user_id: int,
    reference: TimedCandidate | None,
    series: bool,
    offset: int,
    limit: int,
) -> _AlternativePage | None:
    """Die Kandidaten dieses Events aus dem letzten erfolgreichen Lauf - geordnet und geschnitten.

    `total`, `reference_index`, `offset` und `series_rest` entstehen hier aus DERSELBEN Abfrage;
    der Endpunkt setzt sie nur zusammen. `None` heisst: leere Restmenge."""
    # (2) Die Kandidaten: die Rangzeilen dieses Events ABZUEGLICH des eigenen Entwurfs.
    #
    # Der Entwurf ist `(Vorschlag ∪ Aufgenommen) \ Gestrichen` (ADR 0098 Punkt 1); hier steht
    # dessen Verneinung, ausgeschrieben als zwei Bedingungen:
    #
    #   (a) nicht selbst aufgenommen, und
    #   (b) nicht vorgeschlagen ODER selbst gestrichen.
    #
    # Der zweite Halbsatz von (b) ist die Umkehrbarkeit des Austauschs: ein GESTRICHENES Foto des
    # Vorschlags gehoert nicht mehr zum Entwurf und steht deshalb wieder unter den Alternativen -
    # ohne ihn liesse sich ein Austausch nicht zuruecknehmen. Er ist zugleich der Unterschied zum
    # Entwurfs-LESEPFAD, der gestrichene Fotos als Anzeigezustand in der Antwort traegt: hier
    # gehoeren sie zur Restmenge (Zusicherung 2).
    #
    # `or_(… is_(None), … != …)` und nicht `!=` allein: ohne eigene Bewertungszeile ist `status`
    # `NULL`, und ein blosser Ungleichheitsvergleich ergaebe in SQL `NULL` - jedes unbewertete
    # Foto fiele still aus der Antwort.
    #
    # `Photo.taken_at` kommt per INNEREM Join ueber die Rangzeile; er fuegt keine Zeile hinzu
    # (jede Rangzeile hat genau ein Foto), Lauf- und Event-Praedikat bleiben die Mengenbindung.
    own_rating = aliased(Rating)
    candidate_rows = (
        await session.execute(
            select(PhotoRanking.photo_id, PhotoRanking.rank_score, Photo.taken_at)
            .join(Photo, Photo.id == PhotoRanking.photo_id)
            .outerjoin(
                own_rating,
                and_(
                    own_rating.photo_id == PhotoRanking.photo_id,
                    own_rating.user_id == current_user_id,
                ),
            )
            .where(
                # SICHERHEIT: das Pflichtpraedikat, siehe Docstring von `draft_alternatives`.
                PhotoRanking.criterion_scoring_run_id == latest_run_id,
                PhotoRanking.event_id == event_id,
                or_(
                    own_rating.status.is_(None),
                    own_rating.status != RatingStatus.ALBUM_WORTHY,
                ),
                or_(
                    PhotoRanking.selection_position.is_(None),
                    own_rating.status == RatingStatus.REJECTED,
                ),
            )
        )
    ).all()

    # (3) Ordnen und schneiden - `total`, `reference_index` und `offset` aus derselben Menge.
    reference_index: int | None = None
    window: SeriesWindow | None = None
    if reference is None:
        ordered_ids = order_by_quality(
            QualityCandidate(photo_id=row.photo_id, quality=row.rank_score)
            for row in candidate_rows
        )
        if not ordered_ids:
            return None
    else:
        ordered_ids, reference_index, ordered_times = order_alternatives_chronologically(
            reference,
            (
                TimedCandidate(photo_id=row.photo_id, taken_at=row.taken_at)
                for row in candidate_rows
            ),
        )
        if series:
            # Das Fenster stammt allein vom Server; kein Client-Wert geht in die Rechnung ein.
            window = series_window(ordered_times, reference.taken_at, reference_index)
            offset, limit = window.offset, window.size
    return _AlternativePage(
        ids=ordered_ids[offset : offset + limit],
        total=len(ordered_ids),
        offset=offset,
        reference_index=reference_index,
        window=window,
    )


@router.get("/projects/{project_id}/draft-alternatives", response_model=DraftAlternativesOut)
async def draft_alternatives(
    project_id: int,
    # SICHERHEIT (S4): zwei fremdgesteuerte Objekt-Ids, deklarativ begrenzt VOR jeder Verwendung.
    # `ge=1` schliesst `0` und negative Werte aus, `le` verhindert, dass ein Wert jenseits von
    # 2^63 unter SQLite einen `OverflowError` und damit eine 500 statt einer leeren Liste erzeugt.
    # FastAPI spiegelt bei `422` den Rohwert im `input`-Feld zurueck - er wird ausschliesslich als
    # React-Textknoten gerendert, nie geloggt.
    event_id: int = Query(..., ge=1, le=MAX_QUERY_POSITION),
    # Optional (S8): ohne Bezugsbild (Hinzufuegen-Feld) entfaellt allein die Zeitordnung, nie die
    # Bindung an Lauf und Event.
    photo_id: int | None = Query(None, ge=1, le=MAX_QUERY_POSITION),
    # `limit <= 200` deckelt zugleich die schwere Hydratation ueber `photos` mit ihren
    # `selectinload`s - sie laeuft ausschliesslich ueber die angeforderte Seite, nie ueber die
    # ganze Restmenge.
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0, le=MAX_QUERY_POSITION),
    # Das Band: die Aufnahmeserie um das Bezugsbild, Fenster allein vom Server
    # (`series_window`). Nur mit `photo_id`; `limit`/`offset` sind dann wirkungslos.
    series: bool = Query(False),
    # Ein `None`-typisierter Riegel fuer den frueheren Bandparameter. Er steht
    # hier, damit ein noch nicht aktualisierter Client LAUT scheitert (`422`) statt still die
    # erste Seite der vollen Reihe als Band zu bekommen - Muster des `draft`-Riegels.
    nearest: None = Query(None, include_in_schema=False),
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S1): ausgeschriebene Auth-Dependency. Dieser Router traegt bewusst KEINE
    # router-weite `dependencies`-Liste (siehe Kopfkommentar der Datei), und
    # `_protected_router_operations()` in `test_auth_guard.py` fuehrt ihn nicht - fuer ihn gibt es
    # KEIN Vollstaendigkeitsnetz. Ein Endpunkt, der diesen Parameter vergisst, waere STILL
    # OEFFENTLICH: kein Fehler, keine 401, nur Daten. `current_user.id` geht unveraendert an
    # `to_photo_out` (nie ein Platzhalter wie `0` - der liesse `PhotoOut.suggestion` auch fuer
    # laengst bewertete Fotos wieder aufblitzen).
    current_user: User = Depends(get_current_user),
) -> DraftAlternativesOut:
    """Die Alternativen zu EINEM Bild des Entwurfs (ADR 0098 Punkt 5).

    Inhalt: die Fotos DIESES Events im letzten erfolgreichen Lauf ABZUEGLICH des Entwurfs des
    anfragenden Nutzers (`Vorschlag ∪ eigene Aufnahmen`). Ein von ihm GESTRICHENES Foto ist damit
    enthalten - genau daraus folgt, dass ein Austausch umkehrbar ist. Ein im Ausschuss-Schritt
    aussortiertes Foto hat keine Rangzeile und erscheint hier nicht.

    Reihenfolge und Seitenweise: MIT `photo_id` ordnet
    `selection.py::order_alternatives_chronologically` die volle Restmenge zeitlich nach
    `(Photo.taken_at, photo_id)` und liefert die Stelle des Bezugsbildes (`reference_index`);
    ohne `photo_id` ordnet `order_by_quality`. Danach schneidet `limit`/`offset` die Seite heraus,
    mit `series` das vom Server gewaehlte Serienfenster `series_window(...)` samt `series_rest`.
    `total` ist die RESTMENGE und damit unabhaengig vom Schnitt - ein aus `len(items)` gebildetes
    `total` waere auf der ersten Seite nicht davon zu unterscheiden. `reference_index`, `offset`,
    `series_rest` und `total` entstehen aus DERSELBEN Kandidatenabfrage; es gibt keine eigene
    Zaehl- oder Positionsabfrage.

    SICHERHEIT - Projektbindung (S2): `PhotoRanking` traegt KEINE `project_id`, und `event_id` ist
    ein GLOBALER Surrogatschluessel - eine Id aus Projekt B identifiziert unter `/projects/A/…`
    eindeutig FREMDE Rangzeilen. Ohne das Lauf-Praedikat liefe der Endpunkt nicht in eine
    erkennbar falsche Kollisionsmenge, sondern lieferte KOHAERENTE Fotos eines fremden Projekts:
    die Ausfallrichtung wird unauffaelliger, nicht harmloser. Die einzige Bindung an das Projekt
    des Pfadparameters ist `criterion_scoring_run_id` aus
    `latest_successful_criterion_scoring_run_id(session, project_id)`; sie steht AUSGESCHRIEBEN
    in der Aufloesung des Bezugsfotos, in der Kandidatenabfrage und in `sizes`. Der
    innere Join auf `Photo` (fuer `taken_at`) fuegt keine Zeile hinzu. Die Motivabfrage
    (`load_effective_strengths`) bekommt ausschliesslich die Ids der ausgelieferten Seite.
    `photos` filtert nur nach Id und ist ausdruecklich KEINE zweite Verteidigungslinie.

    SICHERHEIT - das Bezugsbild (S3): `photo_id` wird samt `taken_at` AUSSCHLIESSLICH ueber EINE
    Abfrage auf eine Rangzeile desselben Laufs UND desselben Events aufgeloest, nie ueber
    `session.get(Photo, …)` oder eine zweite Abfrage auf `Photo.taken_at`. Scheitert das, endet
    die Anfrage vor jeder weiteren Abfrage mit `200` und dem byte-gleichen Leerkoerper
    (`_no_alternatives`), ohne Fehlertext und ohne Rueckspiegelung der uebergebenen Werte.
    `photo_id` steuert allein die zeitliche Position (`reference_index`, Serienfenster,
    `series_rest`); ohne das Praedikat wuerde die Zeitposition eines fremden Fotos ablesbar.
    Ein abweichender Statuscode oder Koerper waere daneben ein Existenz-Orakel ueber fremde Ids.

    OHNE `photo_id` (S8) entfaellt Schritt (1) und mit ihm die Zeitordnung: `order_by_quality`
    ordnet dann nach Qualitaet, `reference_index` ist `None`, `series` ergibt `422`. Die
    Kandidatenabfrage steht mit Lauf- UND Event-Praedikat unveraendert - eine unbekannte oder
    projektfremde `event_id` ergibt den Leerkoerper. Untersagt sind ein Ersatz-Bezugsbild (etwa
    das frueheste Foto des Events), eine Menge ohne Event-Praedikat und eine Bindung, die nur im
    Zweig mit Bezugsbild steht."""
    if series and photo_id is None:
        # Laut statt still: ein ignoriertes `series` lieferte eine Liste, die wie ein Band
        # aussieht, aber keines ist. Vor jeder Abfrage.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_SERIES_WITHOUT_REFERENCE
        )
    project = await get_project_or_404(project_id, session)
    album_source = await album_level_source(session, project)

    latest_run_id = await latest_successful_criterion_scoring_run_id(session, project_id)
    if latest_run_id is None:
        return _no_alternatives()

    # (1) Das Bezugsbild samt `taken_at` in EINER Abfrage - alle drei Praedikate ausgeschrieben,
    # siehe Docstring (S3). Nur mit `photo_id`; ohne gibt es keines, und es wird keines
    # ersatzweise gewaehlt (S8).
    reference: TimedCandidate | None = None
    if photo_id is not None:
        reference_row = (
            await session.execute(
                select(PhotoRanking.photo_id, Photo.taken_at)
                .join(Photo, Photo.id == PhotoRanking.photo_id)
                .where(
                    PhotoRanking.criterion_scoring_run_id == latest_run_id,
                    PhotoRanking.event_id == event_id,
                    PhotoRanking.photo_id == photo_id,
                )
            )
        ).first()
        if reference_row is None:
            return _no_alternatives()
        reference = TimedCandidate(photo_id=reference_row.photo_id, taken_at=reference_row.taken_at)

    page = await _alternative_page(
        session,
        latest_run_id=latest_run_id,
        event_id=event_id,
        current_user_id=current_user.id,
        reference=reference,
        series=series,
        offset=offset,
        limit=limit,
    )
    if page is None:
        return _no_alternatives()
    ids = page.ids

    # (4) Die Hydratation laeuft ausschliesslich ueber die Seite, die Motive eingeschlossen.
    strengths_by_id = await load_effective_strengths(session, ids)
    photos = await photos_by_id(session, ids)
    rankings_by_id = await ranking_by_photo_id(session, latest_run_id, ids)
    sizes = await partition_sizes(session, latest_run_id)
    place_by_id = await event_and_location_by_photo_id(
        session, project_id, latest_run_id, photos, event_ids_from_rankings(rankings_by_id)
    )
    persons_by_id = await load_effective_persons(session, ids)
    decisions = await final_selection_decisions(session, ids)
    users = await user_count(session)
    items = [
        to_photo_out(
            photos[alternative_id],
            current_user.id,
            project,
            rankings_by_id.get(alternative_id),
            sizes,
            # KEINE `curation_position`: die Alternativen sind keine Auswahl, zu der ein Bild
            # einen Platz haette. Eine Zahl hier waere eine Rangaussage ueber eine Reihenfolge,
            # die allein am gerade betrachteten Bezugsbild haengt.
            None,
            place_by_id.get(alternative_id, NO_PLACE),
            strengths_by_id.get(alternative_id),
            decisions=decisions,
            user_count=users,
            persons=photo_person_outs(persons_by_id.get(alternative_id, [])),
            album_level_source=album_source,
        )
        # Eigener Name, nicht `photo_id`: der Query-Parameter gleichen Namens ist das BEZUGSBILD
        # und wird oben gebraucht; eine Ueberdeckung hier waere an keiner Stelle sichtbar.
        for alternative_id in ids
    ]
    return DraftAlternativesOut(
        items=items,
        total=page.total,
        offset=page.offset,
        reference_index=page.reference_index,
        series_rest=0 if page.window is None else page.window.rest,
    )


# --- Der Austausch: ein Aufruf, eine Transaktion, ein Ereignis ---------------------------------


class DraftExchangeIn(BaseModel):
    """SICHERHEIT (S4): der Body traegt GENAU ZWEI Felder, beide mit deklarativen Grenzen.

    Kein `user_id`, kein `event_id`, kein `weight`, kein `kind`, kein `criterion_scoring_run_id`,
    kein `motif_strength` - Massenzuweisung ist strukturell ausgeschlossen statt im Handler
    herausgefiltert; `model_config` weist ein zusaetzliches Feld ausdruecklich ab statt es still
    zu verwerfen.

    `weight` WIEGT AM SCHWERSTEN: Es ist der einzige Wert, mit dem ein Aufrufer die eigene
    Korrektur in der global wirkenden Gewichtsableitung ueberproportional zaehlen liesse.

    Die Obergrenze ist nicht Kosmetik: Ein unbeschraenkter Pydantic-`int` erzeugt unter SQLite
    jenseits von 2^63 einen `OverflowError` und damit `500` statt `422`."""

    model_config = ConfigDict(extra="forbid")

    photo_id: int = Field(ge=1, le=MAX_QUERY_POSITION)
    replaced_photo_id: int = Field(ge=1, le=MAX_QUERY_POSITION)


class DraftExchangeOut(BaseModel):
    """Der geschriebene Zustand BEIDER Bewertungszeilen (L2).

    Beide, damit die Oberflaeche wie bisher in ihre bereits geladene Liste fortschreibt statt neu
    zu laden - ein Neuladen risse die gerade getauschte Kachel aus der Entwurfsliste."""

    taken: RatingWriteOut
    struck: RatingWriteOut


@dataclass(frozen=True)
class _ExchangeSide:
    """Eine Seite des Austauschs, AUFGELOEST UEBER IHRE RANGZEILE (S2)."""

    photo_id: int
    event_id: int
    level: int | None
    quality: float | None


# S14: EIN Text fuer die unbekannte und fuer die projektfremde Id. Verschiedene Antworten machten
# den Endpunkt zum Existenz-Orakel ueber fremde Foto-Ids.
_EXCHANGE_REFUSAL = (
    "Beide Bilder muessen zum selben Ereignis des juengsten Vorschlagslaufs dieses Projekts "
    "gehoeren."
)


async def _exchange_sides(
    session: AsyncSession,
    criterion_scoring_run_id: int,
    album_source: CategoryMethod,
    photo_ids: tuple[int, int],
) -> dict[int, _ExchangeSide]:
    """Loest beide Foto-Ids UEBER EINE RANGZEILE des uebergebenen Laufs auf.

    SICHERHEIT (S2), und das ist die tragende Entscheidung dieses Endpunkts: Die Aufloesung laeuft
    ausschliesslich ueber `PhotoRanking` mit dem Praedikat "juengster erfolgreicher Lauf DIESES
    Projekts", NIE ueber `session.get(Photo, …)` mit nachgelagerter Projektpruefung.

    Grund: `PhotoRanking` traegt keine `project_id`, `event_id` ist ein globaler
    Surrogatschluessel, und ohne das Laufpraedikat identifiziert eine Id aus Projekt B unter
    `/projects/A/…` eindeutig FREMDE Zeilen - der Endpunkt liefe dann nicht in eine erkennbar
    falsche Menge, sondern tauschte kohaerent zwei Bilder eines fremden Projekts. Die untersagte
    Alternative ist die nachgelagerte Pruefung auf `Photo.project_id`; sie ist keine zweite
    Verteidigungslinie, sondern der Ersatz der richtigen Bedingung durch eine schwaechere.

    Die Modellstufe kommt aus dem EINEN Lesepunkt (`album_stage.load_album_levels`) mit dem am Lauf
    eingefrorenen Verfahren - und ausschliesslich fuer die Foto-Ids, die eine Rangzeile gestellt
    haben (S3): `load_album_levels` loest nichts auf, die Projektbindung traegt das Laufpraedikat.
    Ein Foto ohne Stufe dieses Verfahrens haelt den Austausch nicht auf (L4), sein Paar ist in der
    Diagnose spaeter nur `unbestimmt`."""
    rows = (
        await session.execute(
            select(PhotoRanking.photo_id, PhotoRanking.event_id, PhotoRanking.rank_score).where(
                PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
                PhotoRanking.photo_id.in_(photo_ids),
            )
        )
    ).all()
    levels = await load_album_levels(
        session, album_source, [photo_id for photo_id, _event_id, _score in rows]
    )
    return {
        photo_id: _ExchangeSide(
            photo_id=photo_id,
            event_id=event_id,
            level=levels.get(photo_id),
            quality=rank_score,
        )
        for photo_id, event_id, rank_score in rows
    }


@router.post("/projects/{project_id}/draft/exchange", response_model=DraftExchangeOut)
async def exchange_draft_photo(
    project_id: Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)],
    payload: DraftExchangeIn,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S1): ausgeschriebene Auth-Dependency. Fuer diesen Router gibt es KEIN
    # Vollstaendigkeitsnetz - ein hier vergessener Parameter waere still oeffentlich: kein Fehler,
    # keine 401, sondern ein unauthentifizierter Schreibzugriff, der ZWEI Bewertungszeilen aendert.
    current_user: User = Depends(get_current_user),
) -> DraftExchangeOut:
    """Tauscht im eigenen Album-Entwurf ein Bild gegen ein anderes desselben Ereignisses: Das
    gewaehlte wird aufgenommen, das ersetzte gestrichen.

    EIN AUFRUF STATT ZWEIER, und das ist der Gegenstand dieses Endpunkts: "B statt A" ist die
    Aussage, die beiden Bilder fuer sich tragen sie nicht. Zwei getrennte Aufrufe liessen sich
    nachtraeglich nur ueber eine Heuristik zu einem Paar zusammenfuegen, und der zweite kann
    fehlschlagen - dann bliebe ein halb ausgefuehrter Austausch stehen.

    BEIDE Bewertungszeilen und das eine Ereignis gehen in EINER Transaktion oder gar nicht
    (Auflage S5). Das Favoriten-Kennzeichen bleibt auf beiden Seiten unberuehrt, weil der Austausch
    durch dieselbe Schreibstelle laeuft wie `PUT /photos/{id}/rating`.

    Er erzeugt AUSDRUECKLICH KEIN zusaetzliches Streich- und Aufnahme-Ereignis: Sonst zaehlte jeder
    Austausch dreifach. Die Umkehr eines Austauschs ist ein weiterer Austausch mit eigenem
    Ereignis; sie loescht nichts.

    `404` ohne Projekt. `422`, wenn beide Verweise dasselbe Foto benennen, wenn eines der Bilder
    nicht ueber eine Rangzeile des juengsten erfolgreichen Laufs dieses Projekts erreichbar ist,
    oder wenn die beiden nicht zum selben Ereignis gehoeren - in allen drei Faellen mit
    demselben Text (Auflage S14). `409` bei einem gleichzeitigen Schreibversuch auf eine der
    beiden Zeilen.

    Die Antwort traegt BEIDE geschriebenen Zeilenzustaende, damit die Oberflaeche fortschreibt
    statt neu zu laden."""
    project = await get_project_or_404(project_id, session)

    if payload.photo_id == payload.replaced_photo_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_EXCHANGE_REFUSAL
        )

    run_id = await latest_successful_criterion_scoring_run_id(session, project_id)
    if run_id is None:
        # Ohne erfolgreichen Lauf gibt es keine Rangzeile, ueber die die Projektbindung liefe -
        # und damit keinen Entwurf, in dem etwas auszutauschen waere. Derselbe Text (S14).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_EXCHANGE_REFUSAL
        )

    # Der Lauf existiert hier bereits - die Quelle stammt damit aus ihm selbst (S2). Ein Foto, das
    # nur die Stufe des anderen Verfahrens traegt, bleibt "unbestimmt".
    sides = await _exchange_sides(
        session,
        run_id,
        await album_level_source(session, project),
        (payload.photo_id, payload.replaced_photo_id),
    )
    taken = sides.get(payload.photo_id)
    struck = sides.get(payload.replaced_photo_id)
    # EINE Bedingung fuer alle drei Ablehnungsgruende: unbekannt, projektfremd, verschiedene
    # Ereignisse. `event_id` stammt damit aus der Rangzeile und nie aus dem Body (S3).
    if taken is None or struck is None or taken.event_id != struck.event_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_EXCHANGE_REFUSAL
        )

    # `record=False` auf BEIDEN Aufrufen: Ohne diese Unterdrueckung entstuenden neben dem
    # Austausch-Ereignis noch ein Streich- und ein Aufnahme-Ereignis, und jeder Austausch zaehlte
    # dreifach. Keiner der beiden Aufrufe committet - die Transaktionsgrenze liegt unten.
    written_taken = await write_own_rating(
        session,
        project_id=project_id,
        photo_id=taken.photo_id,
        user_id=current_user.id,
        next_state=lambda _status, favorite: (RatingStatus.ALBUM_WORTHY, favorite),
        record=False,
    )
    written_struck = await write_own_rating(
        session,
        project_id=project_id,
        photo_id=struck.photo_id,
        user_id=current_user.id,
        next_state=lambda _status, favorite: (RatingStatus.REJECTED, favorite),
        record=False,
    )
    await record_exchange(
        session,
        project_id=project_id,
        user_id=current_user.id,
        photo_id=taken.photo_id,
        replaced_photo_id=struck.photo_id,
        criterion_scoring_run_id=run_id,
        event_id=taken.event_id,
        level=taken.level,
        replaced_level=struck.level,
        quality=taken.quality,
        replaced_quality=struck.quality,
    )
    # DER EINE COMMIT ueber beide Zeilen und das Ereignis (S5).
    await session.commit()
    return DraftExchangeOut(taken=written_taken, struck=written_struck)


class DraftExchangeUndoIn(BaseModel):
    """SICHERHEIT (S6): GENAU vier Felder. Dieselben beiden Ids wie beim Tausch und die beiden
    Vorzustaende als geschlossener Vorrat - jeweils der einzige Zustand ausser "keine
    Entscheidung", aus dem der Tausch die Seite geholt haben kann.

    Beide Vorzustaende sind PFLICHTFELDER, nullbar, aber ohne Vorgabewert: Ein Default `None`
    machte ein vergessenes oder abgeschnittenes Feld zu einer stillen Ruecknahme der
    Albumentscheidung, ein offener Vorrat liesse die Wiederherstellung Zustaende schreiben, die
    kein Tausch erzeugt hat. Mit dem geschlossenen Vorrat kann der Endpunkt nichts, was der Nutzer
    nicht schon ueber `PUT`/`DELETE /photos/{id}/rating` an seinen eigenen Zeilen koennte.

    Kein `user_id`, `event_id`, `weight`, `kind`, `criterion_scoring_run_id`, `favorite` -
    `extra="forbid"` weist jedes weitere Feld ab statt es still zu verwerfen."""

    model_config = ConfigDict(extra="forbid")

    photo_id: int = Field(ge=1, le=MAX_QUERY_POSITION)
    replaced_photo_id: int = Field(ge=1, le=MAX_QUERY_POSITION)
    photo_previous_status: Literal[RatingStatus.REJECTED] | None
    replaced_previous_status: Literal[RatingStatus.ALBUM_WORTHY] | None


class DraftExchangeUndoOut(BaseModel):
    """Der geschriebene Zustand BEIDER eigenen Bewertungszeilen nach der Wiederherstellung."""

    photo: RatingWriteOut
    replaced: RatingWriteOut


# S7: fester Text ohne Rueckspiegelung des gelesenen Zustands.
_UNDO_REFUSAL = (
    "Der Tausch laesst sich nicht mehr rueckgaengig machen: Mindestens eines der beiden Bilder "
    "wurde inzwischen veraendert."
)


@router.post("/projects/{project_id}/draft/exchange/undo", response_model=DraftExchangeUndoOut)
async def undo_draft_exchange(
    project_id: Annotated[int, PathParam(ge=1, le=MAX_QUERY_POSITION)],
    payload: DraftExchangeUndoIn,
    session: AsyncSession = Depends(get_session),
    # SICHERHEIT (S1): ausgeschriebene Auth-Dependency. Fuer diesen Router gibt es KEIN
    # Vollstaendigkeitsnetz - ein hier vergessener Parameter waere ein unauthentifizierter
    # Schreibzugriff, der ZWEI Bewertungszeilen aendert.
    current_user: User = Depends(get_current_user),
) -> DraftExchangeUndoOut:
    """Stellt nach einem Tausch beide eigenen Bewertungszeilen auf ihren Zustand vor dem Tausch
    zurueck - beide oder keine.

    REIHENFOLGE, verbindlich (S5): `404` Projekt -> `422` Bindung -> `409` Vorbedingung ->
    Schreiben. Die Bindung ist wortgleich die des Tauschs (`_exchange_sides`, ein Text fuer gleiche
    Id, fehlenden Lauf, unbekannte, projektfremde Id und verschiedene Events). Stuende die
    Vorbedingung vorn, unterschiede die Antwort eine unbekannte Id (`409`) von einer projektfremden
    - ein Existenz-Orakel ueber fremde Foto-Ids; ohne die Bindung stellte der Endpunkt kohaerent
    zwei Bilder eines fremden Projekts wieder her.

    VORBEDINGUNG (S7): aktuell `photo_id` = `album_worthy` und `replaced_photo_id` = `rejected`,
    gelesen AUSSCHLIESSLICH an den eigenen Zeilen - sonst entschiede der Zustand des anderen Nutzers
    ueber den eigenen Schreibweg. Sonst `409` mit festem Text, keine Zeile geaendert, kein
    Ereignis. Sie faengt die Wiederholung nach Abschluss ab (Doppelklick, zweiter Tab); eine
    Zeilensperre gibt es nicht.

    SCHREIBEN: zweimal `write_own_rating(record=False)` - `favorite` bleibt auf beiden Seiten
    unberuehrt, die Zeileninvariante setzt die Schreibstelle durch -, dazu genau EIN
    `record_exchange` in Gegenrichtung (ADR 0100 Punkt 3: die Umkehr ist ein weiterer Tausch) und
    genau EIN Commit."""
    project = await get_project_or_404(project_id, session)

    if payload.photo_id == payload.replaced_photo_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_EXCHANGE_REFUSAL
        )
    run_id = await latest_successful_criterion_scoring_run_id(session, project_id)
    if run_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_EXCHANGE_REFUSAL
        )
    sides = await _exchange_sides(
        session,
        run_id,
        await album_level_source(session, project),
        (payload.photo_id, payload.replaced_photo_id),
    )
    taken = sides.get(payload.photo_id)
    struck = sides.get(payload.replaced_photo_id)
    if taken is None or struck is None or taken.event_id != struck.event_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=_EXCHANGE_REFUSAL
        )

    own_status = {
        photo_id: own
        for photo_id, own in (
            await session.execute(
                select(Rating.photo_id, Rating.status).where(
                    Rating.user_id == current_user.id,
                    Rating.photo_id.in_((taken.photo_id, struck.photo_id)),
                )
            )
        ).all()
    }
    if (
        own_status.get(taken.photo_id) != RatingStatus.ALBUM_WORTHY
        or own_status.get(struck.photo_id) != RatingStatus.REJECTED
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_UNDO_REFUSAL)

    photo_previous = payload.photo_previous_status
    replaced_previous = payload.replaced_previous_status
    written_photo = await write_own_rating(
        session,
        project_id=project_id,
        photo_id=taken.photo_id,
        user_id=current_user.id,
        next_state=lambda _status, favorite: (photo_previous, favorite),
        record=False,
    )
    written_replaced = await write_own_rating(
        session,
        project_id=project_id,
        photo_id=struck.photo_id,
        user_id=current_user.id,
        next_state=lambda _status, favorite: (replaced_previous, favorite),
        record=False,
    )
    # Der Tausch in Gegenrichtung: das damals ersetzte Bild kehrt zurueck, die Alternative geht.
    await record_exchange(
        session,
        project_id=project_id,
        user_id=current_user.id,
        photo_id=struck.photo_id,
        replaced_photo_id=taken.photo_id,
        criterion_scoring_run_id=run_id,
        event_id=struck.event_id,
        level=struck.level,
        replaced_level=taken.level,
        quality=struck.quality,
        replaced_quality=taken.quality,
    )
    await session.commit()
    return DraftExchangeUndoOut(photo=written_photo, replaced=written_replaced)
