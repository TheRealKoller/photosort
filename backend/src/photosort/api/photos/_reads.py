"""Geteilte Lesehilfen: Projektbindung, Hydratation und Ableitungen mit Datenbankzugriff.

Was mehrere Themengruppen brauchen, steht hier genau einmal; keine Funktion kennt einen Endpunkt.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from photosort.api.photos._conversion import (
    EventOut,
    PhotoPlace,
    RatingFilter,
    event_out,
    location_out,
)
from photosort.duplicates import has_open_suggestion
from photosort.events import EventSpan, LocationEntry, event_for_time, infer_locations
from photosort.models import (
    CategoryMethod,
    CriterionScoringRun,
    Event,
    FinalSelectionDecision,
    Photo,
    PhotoEyeResult,
    PhotoFineLabel,
    PhotoRanking,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    User,
)
from photosort.persons import effective_person_assignments


async def get_project_or_404(project_id: int, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
    return project


async def auto_decided_ids(session: AsyncSession, project_id: int) -> set[int]:
    """Die Fotos DIESES Projekts, deren `PhotoScore.auto_decided` steht (Spec 0639).

    Projektbindung ausgeschrieben in derselben Anweisung, wie alle Zaehlungen dieses Moduls: Der
    Merker ist Lauf-Zustand EINES Projekts und darf eine fremde Antwort nicht veraendern."""
    return set(
        (
            await session.execute(
                select(PhotoScore.photo_id)
                .join(Photo, Photo.id == PhotoScore.photo_id)
                .where(Photo.project_id == project_id, PhotoScore.auto_decided.is_(True))
            )
        ).scalars()
    )


async def filtered_photo_ids(
    session: AsyncSession,
    project_id: int,
    current_user_id: int,
    rating_status: RatingFilter | None,
    limit: int,
    offset: int,
    camera_id: int | None = None,
    person_ids: Sequence[int] = (),
) -> tuple[list[int], int]:
    own_rating = aliased(Rating)
    base = (
        select(Photo.id)
        .where(Photo.project_id == project_id)
        .outerjoin(
            own_rating,
            and_(own_rating.photo_id == Photo.id, own_rating.user_id == current_user_id),
        )
    )
    if camera_id is not None:
        # SICHERHEIT (Projektgrenze): ein weiteres PRAEDIKAT neben dem vorhandenen
        # `Photo.project_id == project_id` - nie eine vorgeschaltete Aufloesung der Kamerazeile,
        # aus deren Fotos dann gelistet wird. Eine `camera_id` aus einem fremden Projekt trifft
        # damit kein Foto und ergibt eine LEERE Liste, ohne den Wert zu spiegeln.
        base = base.where(Photo.camera_id == camera_id)
    # UND-verknuepft: ein Foto muss JEDE genannte Person wirksam tragen - ueber das EINE
    # Konstrukt der wirksamen Zuordnung, Korrektur vor Erkennung. Eine unbekannte Id trifft kein
    # Foto und ergibt eine leere Liste.
    if person_ids:
        effective = effective_person_assignments()
        for person_id in person_ids:
            base = base.where(
                Photo.id.in_(select(effective.c.photo_id).where(effective.c.person_id == person_id))
            )
    if rating_status is RatingFilter.UNRATED:
        # "Unbewertet" ist KEINE ALBUMENTSCHEIDUNG, nicht mehr "keine Zeile": seit `favorite`
        # eine eigene Spalte ist, kann eine Zeile ohne jede Albumentscheidung existieren. Ueber
        # das Zeilenvorhandensein gepruefte Abwesenheit liesse ein nur als Favorit markiertes
        # Foto still aus dem Filter fallen.
        base = base.where(or_(own_rating.id.is_(None), own_rating.status.is_(None)))
    elif rating_status is RatingFilter.SUGGESTED:
        # Bildet dieselbe Regel wie has_suggestion in to_photo_out als SQL-Praedikat nach: keine
        # eigene ALBUMENTSCHEIDUNG des anfragenden Nutzers UND ein OFFENER Vorschlag.
        #
        # "Offen" ist seit ADR 0104 mehr als "suggested_status gesetzt": Eine im Duplikat-Vergleich
        # entschiedene Aufnahme ist beantwortet und verschwindet aus diesem Filter - und damit auch
        # aus der Zaehlung des Ausschuss-Gates, die denselben Filter benutzt. Die Bedingung steht
        # deshalb an EINER Stelle (`duplicates.py::has_open_suggestion`); die Objektfassung
        # daneben bleibt ueber
        # `tests/test_api_photos.py::test_list_photos_suggested_filter_matches_has_suggestion_parity`
        # an sie gebunden.
        base = base.join(PhotoScore, PhotoScore.photo_id == Photo.id).where(
            or_(own_rating.id.is_(None), own_rating.status.is_(None)),
            has_open_suggestion(),
        )
    elif rating_status is RatingFilter.FAVORITE:
        # Eigene SPALTE, nicht mehr ein Wert von `status`. Ohne diesen Zweig wuerfe
        # `RatingStatus("favorite")` unten einen `ValueError` - eine 500 auf einem
        # nutzererreichbaren Query-Parameter (Auflage S11).
        base = base.where(own_rating.favorite.is_(True))
    elif rating_status is not None:
        base = base.where(own_rating.status == RatingStatus(rating_status.value))

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    paged = base.order_by(Photo.taken_at, Photo.id).offset(offset).limit(limit)
    ids = [row[0] for row in (await session.execute(paged)).all()]
    return ids, total


async def photos_by_id(session: AsyncSession, ids: list[int]) -> dict[int, Photo]:
    if not ids:
        return {}
    result = await session.execute(
        select(Photo)
        .where(Photo.id.in_(ids))
        .options(
            selectinload(Photo.ratings).selectinload(Rating.user),
            selectinload(Photo.score),
            # Photo.criterion_scores ist bereits eine ORM-Relationship (models.py) - eager laden
            # statt eines Query pro Foto.
            selectinload(Photo.criterion_scores),
            # Analog
            # eager geladen, inkl. der verknuepften fine_labels-Zeile (fuer canonical_key/
            # display_name, ohne N+1-Query pro Feinlabel).
            selectinload(Photo.fine_labels).selectinload(PhotoFineLabel.fine_label),
            # Eager geladen (analog criterion_scores/fine_labels oben), kein zusaetzliches Query
            # je Foto fuer _cloud_vision_status_out. Ohne dieses selectinload loest
            # photo.landmark_detection einen Lazy-Load aus und schlaegt im Async-Kontext mit
            # MissingGreenlet fehl.
            selectinload(Photo.landmark_detection),
            selectinload(Photo.cloud_vision_errors),
            # Grundlage von `PhotoOut.camera`. EINE Abfrage mehr, unabhaengig von der
            # Fotoanzahl - ohne sie loeste `photo.camera` einen Lazy-Load aus und schluege im
            # Async-Kontext mit MissingGreenlet fehl.
            selectinload(Photo.camera),
            # Grundlage von `PhotoOut.motif_assessment`. Ohne dieses selectinload loeste
            # `photo.motif_assessment` einen Lazy-Load aus und schluege im Async-Kontext mit
            # MissingGreenlet fehl. Die STAERKEN kommen bewusst nicht ueber die Relationship,
            # sondern ueber `load_effective_strengths` - sonst muesste die Korrektur zweimal
            # ausgewertet werden.
            selectinload(Photo.motif_assessment),
            # Grundlage von `PhotoOut.eye_result`. Die FINELABELS kommen ueber die Relationship
            # der Kopfzeile mit - eine Abfrage mehr, unabhaengig von der Fotoanzahl. Ohne dieses
            # selectinload loeste `photo.eye_result` einen Lazy-Load aus und schluege im
            # Async-Kontext mit MissingGreenlet fehl.
            selectinload(Photo.eye_result).selectinload(PhotoEyeResult.fine_labels),
            # Grundlage von `PhotoOut.album_suitability` UND der zweiten Haelfte des
            # Erfolgssignals in `_cloud_vision_status_out`. Ohne dieses selectinload loeste
            # `photo.album_suitability` einen Lazy-Load aus und schluege im Async-Kontext mit
            # MissingGreenlet fehl.
            selectinload(Photo.album_suitability),
            # Grundlage der Objektfassung des Ueberlebenden-Praedikats (`is_candidate`) und der
            # Anzeigeregel des offenen Vorschlags. Ohne dieses selectinload loeste
            # `photo.duplicate_decision` einen Lazy-Load aus und schluege im Async-Kontext mit
            # MissingGreenlet fehl.
            selectinload(Photo.duplicate_decision),
        )
    )
    return {photo.id: photo for photo in result.scalars()}


def event_ids_from_rankings(rankings_by_photo_id: Mapping[int, PhotoRanking]) -> dict[int, int]:
    """Die Event-Abbildung der Lesepfade, die ausschliesslich Fotos MIT Rangzeile liefern.

    Der Entwurfszweig baut seine eigene: dort haben aufgenommene Fotos ohne Rangzeile ihr Event
    ueber `events.py::event_for_time`."""
    return {photo_id: ranking.event_id for photo_id, ranking in rankings_by_photo_id.items()}


async def event_and_location_by_photo_id(
    session: AsyncSession,
    project_id: int,
    criterion_scoring_run_id: int | None,
    photos_by_id: Mapping[int, Photo],
    event_id_by_photo_id: Mapping[int, int],
    known_events: Mapping[int, EventOut] | None = None,
) -> dict[int, PhotoPlace]:
    """Beide Ortsfelder aller Fotos einer Antwort aus ZWEI Abfragen - ihre Zahl ist fest und
    unabhaengig von der Zahl der Fotos.

    (a) Alle Fotos DIESES Projekts als Inferenzbasis von `events.py::infer_locations`. Die
    Bezugsmenge ist ausdruecklich nicht die Antwort und auch nicht die Kandidatenmenge: ein
    aussortiertes Foto traegt eine ebenso gueltige Koordinate. Dieselbe Funktion speist den
    Worker - zwei Herleitungen derselben Sache liefen an dem Tag auseinander, an dem eine ihre
    Bezugsmenge aendert.

    (b) Die Events der uebergebenen Abbildung `photo_id -> event_id`. Sie kommt FERTIG herein
    statt hier aus Rangzeilen gebildet zu werden: der Entwurfszweig ordnet aufgenommene Fotos ohne
    Rangzeile ueber ihre Aufnahmezeit ein, und diese Zuordnung gehoert an die eine Stelle, die
    beide Herkuenfte kennt.

    SICHERHEIT - zwei GETRENNTE Bindungen, beide ausgeschrieben:

    * (M5) Die Inferenzbasis haengt an `Photo.project_id`. Ohne sie erbte ein Foto Koordinaten aus
      einem fremden Projekt.
    * (M1) Die Event-Abfrage haengt an `Event.criterion_scoring_run_id` - `event_id` ist ein
      GLOBALER Surrogatschluessel, und eine Id aus Projekt B identifiziert unter `/projects/A/...`
      eindeutig ein fremdes Event. Die Lauf-Id wird EINMAL PRO REQUEST aufgeloest und hierher
      durchgereicht, nie in dieser Funktion neu bestimmt; fehlt sie, bleibt `event` `None`. Die
      Ausfallrichtung ist "nichts anzeigen", nie "aus irgendeinem Lauf herleiten".

    `known_events` sind die bereits ueber `run_events` (dasselbe Laufpraedikat) geladenen Events
    desselben Laufs; mit ihnen entfaellt die Event-Abfrage hier, die Events eines Laufs werden je
    Anfrage dann genau einmal geladen.

    `photos_by_id` filtert nur nach Id und ist ausdruecklich KEINE zweite Verteidigungslinie."""
    if not photos_by_id:
        return {}

    location_rows = (
        await session.execute(
            select(Photo.id, Photo.taken_at, Photo.gps_lat, Photo.gps_lon).where(
                Photo.project_id == project_id
            )
        )
    ).all()
    effective_locations = infer_locations(
        LocationEntry(photo_id=photo_id, taken_at=taken_at, gps_lat=gps_lat, gps_lon=gps_lon)
        for photo_id, taken_at, gps_lat, gps_lon in location_rows
    )

    events_by_id: Mapping[int, EventOut] = {}
    if known_events is not None:
        events_by_id = known_events
    elif criterion_scoring_run_id is not None and event_id_by_photo_id:
        events_by_id = {
            event.id: event_out(event)
            for event in (
                await session.execute(
                    select(Event).where(
                        # SICHERHEIT: das Pflichtpraedikat, siehe Docstring. Nie die Id allein.
                        Event.criterion_scoring_run_id == criterion_scoring_run_id,
                        Event.id.in_(set(event_id_by_photo_id.values())),
                    )
                )
            )
            .scalars()
            .all()
        }

    return {
        photo_id: PhotoPlace(
            location=location_out(effective_locations.get(photo_id)),
            event=events_by_id.get(event_id_by_photo_id.get(photo_id, 0)),
        )
        for photo_id in photos_by_id
    }


async def final_selection_decisions(session: AsyncSession, photo_ids: list[int]) -> dict[int, bool]:
    """Die gemeinsame Entscheidung je Foto - EINE Abfrage je Anfrage, nie eine je Foto (Muster
    `ranking_by_photo_id`).

    Ein fehlender Eintrag heisst "unentschieden"; es gibt keinen dritten Zustand."""
    if not photo_ids:
        return {}
    result = await session.execute(
        select(FinalSelectionDecision.photo_id, FinalSelectionDecision.included).where(
            FinalSelectionDecision.photo_id.in_(photo_ids)
        )
    )
    return {photo_id: included for photo_id, included in result.all()}


async def user_count(session: AsyncSession) -> int:
    """Der NENNER der Einigkeitsregel: die Zahl der Konten im Bestand.

    Eine einzelne Zahl statt der Nutzerliste, weil die drei Bestands-Lesepfade (Listing, Entwurf,
    Alternativen) von der Nutzermenge nichts anderes brauchen. Der neue Endpunkt zaehlt bewusst
    NICHT hierueber: Er liefert `participants` mit aus, und sein Nenner stammt aus DERSELBEN
    Leseoperation (Auflage S8) - gingen beide auseinander, behauptete die Ansicht Einigkeit ueber
    zwei Teilnehmer, waehrend die Regel ueber drei rechnet, und kein Feld der Antwort saehe dabei
    widerspruechlich aus.

    RESTRISIKO, bewusst getragen und in der Spec benannt: Der Nenner ist die GLOBALE Nutzerzahl.
    Ein drittes, administrativ angelegtes Konto aendert die Endauswahl jedes Projekts, ohne dass
    ein Schreibzugriff stattfindet."""
    return (await session.execute(select(func.count()).select_from(User))).scalar_one()


async def latest_successful_criterion_scoring_run_id(
    session: AsyncSession, project_id: int
) -> int | None:
    return (
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


async def album_level_source(session: AsyncSession, project: Project) -> CategoryMethod:
    """Das Verfahren, dessen Stufe in DIESEM Projekt zaehlt: die am juengsten erfolgreichen Lauf
    eingefrorene Quelle, ohne erfolgreichen Lauf die Projekteinstellung (ADR 0144).

    SICHERHEIT (S3): Gelesen wird ausschliesslich der juengste erfolgreiche Lauf DIESES Projekts
    (`project_id`), nie der global juengste - sonst zeigte ein Projekt die Herkunft eines fremden
    Laufs. Der Livewert der Einstellung gilt nur, solange es keinen Lauf gibt: sonst wirkte ein
    Wechsel sofort, und der bestehende Entwurf wechselte still seine Grundlage.

    EINMAL je Anfrage aufgerufen; der Lauf-Id-Lesepfad daneben bleibt unveraendert."""
    source = (
        await session.execute(
            select(CriterionScoringRun.album_level_source)
            .where(
                CriterionScoringRun.project_id == project.id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
            )
            .order_by(CriterionScoringRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return project.category_method if source is None else source


@dataclass(frozen=True)
class PlacedPhotos:
    """Eine Fotomenge, in die Events eines Laufs EINGEORDNET und darin numeriert - drei
    zusammengehoerige Teile EINER Herleitung.

    Nicht mehr `DraftContent`: Die Einordnung traegt seit Spec 0431 ZWEI Zweige, den Album-Entwurf
    eines Nutzers und die gemeinsame Endauswahl des Projekts. Ein Name, der nur den einen nennt,
    laedt dazu ein, sie fuer den anderen ein zweites Mal zu schreiben.

    `event_id_by_photo_id` steht hier und nicht beim Aufrufer: Fuer ein Foto ohne Rangzeile ist die
    Zuordnung ueber die Aufnahmezeit entstanden, und sie ist zugleich der Sortierschluessel
    gewesen. Zweimal hergeleitet liefe sie an dem Tag auseinander, an dem eine der beiden Stellen
    sich aendert.

    Die Lauf-Id gehoert AUSDRUECKLICH NICHT hierher: Jeder der beiden Zweige loest sie selbst auf,
    und sie ist keine Eigenschaft der Einordnung."""

    ordered_ids: list[int]
    curation_positions: dict[int, int]
    event_id_by_photo_id: dict[int, int]


def place_in_events(
    rows: Sequence[tuple[int, datetime, int | None]],
    spans: Sequence[EventSpan],
    position_by_event_id: Mapping[int, int],
) -> PlacedPhotos:
    """Die EINE Einordnung einer Fotomenge in die Events eines Laufs - von BEIDEN Zweigen
    aufgerufen (Entwurf und Endauswahl), nie zweimal geschrieben.

    Zweimal geschrieben ordneten Entwurf und Endauswahl dieselben Fotos verschieden - sichtbar,
    ohne dass eine Pruefung rot wuerde.

    DIE RANGZEILE HAT VORRANG. Ordnet der Lauf ein aufgenommenes Foto einem anderen Event zu, steht
    es dort - nicht dort, wohin seine Zeit zeigte. Ein Foto, dessen Zeit in keine Eventspanne
    faellt und das keine Rangzeile hat, faellt HERAUS: die Ausfallrichtung ist "nicht zeigen", nie
    eine erfundene Gruppe.

    REIHENFOLGE `(events.position, photos.taken_at, photos.id)` - innerhalb eines Events also
    CHRONOLOGISCH nach der korrigierten Aufnahmezeit, ausdruecklich nicht nach
    `selection_position`. Der Schluessel ist damit TOTAL und fuer vorgeschlagene wie aufgenommene
    Fotos derselbe.

    `curation_positions` ist der Platz in der ANGEZEIGTEN Auswahl des Events - lueckenlos ab 1
    ueber die gelieferte Reihenfolge vergeben, nicht die `selection_position`: ein aufgenommenes
    Foto hat keine, und eine Luecke waere eine Aussage ueber einen Platz, den es nicht gibt.

    Die Komplexitaetsklasse ist verbindlich (Auflage S14): ein Durchgang ueber die Zeilen, nie eine
    Abfrage je Foto. Die Eventliste kommt FERTIG herein."""
    placed: list[tuple[int, int, datetime, int]] = []
    event_id_by_photo_id: dict[int, int] = {}
    for photo_id, taken_at, ranked_event_id in rows:
        event_id = (
            ranked_event_id if ranked_event_id is not None else event_for_time(spans, taken_at)
        )
        if event_id is None or event_id not in position_by_event_id:
            continue
        event_id_by_photo_id[photo_id] = event_id
        placed.append((position_by_event_id[event_id], photo_id, taken_at, event_id))

    placed.sort(key=lambda entry: (entry[0], entry[2], entry[1]))

    ordered_ids: list[int] = []
    curation_positions: dict[int, int] = {}
    seen_per_event: dict[int, int] = {}
    for _, photo_id, _, event_id in placed:
        seen_per_event[event_id] = seen_per_event.get(event_id, 0) + 1
        curation_positions[photo_id] = seen_per_event[event_id]
        ordered_ids.append(photo_id)
    return PlacedPhotos(
        ordered_ids=ordered_ids,
        curation_positions=curation_positions,
        event_id_by_photo_id=event_id_by_photo_id,
    )


@dataclass(frozen=True)
class RunEvents:
    """Die Events EINES Laufs, einmal geladen und in den drei Formen, die die Lesepfade brauchen:
    Spannen und Positionen als Eingabe von `place_in_events`, `EventOut` je Id fuer die Fotos und
    die nach `position` geordnete Liste fuer die Eventliste des Entwurfs."""

    spans: list[EventSpan]
    position_by_event_id: dict[int, int]
    out_by_id: dict[int, EventOut]
    ordered: list[EventOut]


async def run_events(session: AsyncSession, criterion_scoring_run_id: int) -> RunEvents:
    """Die Events eines Laufs aus EINER Abfrage (Auflage S14), von Entwurf und Endauswahl geteilt.

    SICHERHEIT (M1, S2): ausschliesslich ueber `Event.criterion_scoring_run_id` des uebergebenen,
    je Anfrage einmal aufgeloesten Laufs; `EventOut` entsteht nur ueber `event_out`, damit die
    Mitgliedschaftspruefung des Ortsteils (`_event_place_out`) an einer Stelle bleibt."""
    events = (
        (
            await session.execute(
                select(Event)
                .where(Event.criterion_scoring_run_id == criterion_scoring_run_id)
                .order_by(Event.position)
            )
        )
        .scalars()
        .all()
    )
    ordered = [event_out(event) for event in events]
    return RunEvents(
        spans=[
            EventSpan(event_id=event.id, started_at=event.started_at, ended_at=event.ended_at)
            for event in events
        ],
        position_by_event_id={event.id: event.position for event in events},
        out_by_id={event_out.id: event_out for event_out in ordered},
        ordered=ordered,
    )


async def partition_sizes(session: AsyncSession, criterion_scoring_run_id: int) -> dict[int, int]:
    """Größe jeder Event-Partition eines Laufs, für "Rang M von N" im Info-Popover - ein einzelner
    GROUP BY-Query pro Aufruf (nicht pro Foto). Bewusst lauf-global, nicht nutzerspezifisch
    gefiltert - siehe RankingOut.partition_size-Docstring.

    Gezählt wird die BEWERTETE Teilmenge: ein Foto ohne Modellbewertung erscheint nicht im
    Entwurf, und eine Größe, die es mitzählte, machte aus "Rang 1 von 1" ein "Rang 1 von 2" über
    einer Partition mit genau einem einsehbaren Foto. Die Zahl an der Event-Überschrift und der
    tatsächlich einsehbare Vorrat müssen dieselbe Menge beschreiben.

    SICHERHEIT (S2): das Lauf-Prädikat steht auch HIER - diese Zählabfrage speist `partition_size`
    auf jedem Lesepfad, den Alternativen-Endpunkt eingeschlossen, und ist damit eine Abfrage
    dieser Endpunkte wie jede andere."""
    result = await session.execute(
        select(PhotoRanking.event_id, func.count())
        .where(
            PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
            PhotoRanking.rank_position.is_not(None),
        )
        .group_by(PhotoRanking.event_id)
    )
    return {event_id: count for event_id, count in result.all()}


async def ranking_by_photo_id(
    session: AsyncSession, criterion_scoring_run_id: int, photo_ids: list[int]
) -> dict[int, PhotoRanking]:
    """Die Rangzeile je Foto - GENAU EINE, durch den Unique-Constraint `(Lauf, Foto)` garantiert.

    `scalar_one_or_none()` je Foto waere ein Query pro Foto; die Abbildung entsteht deshalb aus
    einer Abfrage."""
    if not photo_ids:
        return {}
    result = await session.execute(
        select(PhotoRanking).where(
            PhotoRanking.criterion_scoring_run_id == criterion_scoring_run_id,
            PhotoRanking.photo_id.in_(photo_ids),
        )
    )
    return {row.photo_id: row for row in result.scalars()}


# SICHERHEIT - Obergrenze von `offset`/`camera_id`/`event_id`/`photo_id`: ein Pydantic-`int` ist
# unbeschraenkt und landet direkt im SQL-Vergleich; unter SQLite (Testlauf und lokale Entwicklung)
# wirft ein Wert jenseits von 2^63 einen `OverflowError` und damit eine 500 statt einer leeren
# Liste. Der Wert liegt weit ueber jeder realistischen Partitionsgroesse - er begrenzt einen
# Missbrauchsfall, nicht die Benutzung.
#
# Steht VOR `list_photos`, nicht erst vor dem Alternativen-Endpunkt: `Query(...)`-Vorgabewerte
# werden zur DEFINITIONSZEIT ausgewertet, eine spaeter definierte Konstante bricht den Import.
#
# OEFFENTLICH (kein fuehrender Unterstrich), weil die Grenze GETEILT ist: `api/duplicate_decisions.py`
# zieht sie von hier. Ein geteilter Grenzwert soll nicht zweimal dastehen - zwei Zahlen liefen
# auseinander, und die kleinere entschiede still, welche Anfrage `422` statt `404` bekommt. Die
# aeltere Nachbildung in `api/cameras.py` bleibt vorerst stehen (eigener Wert, eigene Begruendung);
# sie darf spaeter hierher zusammengezogen werden.
MAX_QUERY_POSITION = 1_000_000_000
