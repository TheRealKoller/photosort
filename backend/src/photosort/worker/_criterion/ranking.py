"""Rangfolge und Auswahl: Orts- und Gazetteer-Fabriken, Gliederung, Rangzeilen, Vorschlag."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping

from sqlalchemy import select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker._runs as runs
from photosort.album_stage import load_album_levels
from photosort.event_inputs import read_event_inputs
from photosort.events import LandmarkPointsByName, assign_place_names, build_events
from photosort.geonames import LandmarkGazetteer, folded_landmark_names
from photosort.models import (
    CriterionScoringRun,
    Event,
    LandmarkPlaceLookup,
    Photo,
    PhotoMotifAssessment,
    PhotoRanking,
    PlaceLookup,
    Project,
)
from photosort.motif_strengths import load_effective_strengths
from photosort.persons import load_effective_persons
from photosort.places import (
    PLACE_LEVELS,
    PlaceInfo,
    PlaceResolver,
    sanitize_place_name,
)
from photosort.quality import compute_quality_score
from photosort.quality_weights import effective_weights, latest_weight_set
from photosort.ranking import rank_photos
from photosort.selection import (
    SelectionCandidate,
    SelectionEvent,
    effective_target,
    select_album_draft,
)

# Der geschlossene eigene Vorrat von `place_lookups.source` - er hat genau einen Eintrag, weil es
# genau einen Weg zur Ortsauskunft gibt. Er stammt NIE aus der Antwort.
PLACE_LOOKUP_SOURCE = "geonames"


# Die Fabrik des Auflösers: aus der Menge der noch nicht beschafften Zellen entsteht ein Auflöser
# oder `None`. `None` heisst "es wird keiner gebaut" und ist ein arbeitsfaehiger Zustand.
PlaceResolverFactory = Callable[[Collection[tuple[float, float]]], PlaceResolver | None]


async def place_infos(
    session: AsyncSession,
    project_id: int,
    cells: Collection[tuple[float, float]],
    build_resolver: PlaceResolverFactory | None,
) -> dict[tuple[float, float], PlaceInfo]:
    """Die Ortsauskunft je vergroeberter Zelle - aus dem Bestand gelesen, nur fuer die FEHLENDEN
    gefragt (die reine Logik liegt im Modul, der Datenbankzugriff hier).

    SICHERHEIT: Die Bindung an `project_id` steht in der Abfrage ausgeschrieben, und es gibt KEINEN
    Rueckfall auf die Zeile eines anderen Projekts - ein solcher Rueckfall waere der stille Weg, auf
    dem die Lebensdauer-Bindung der Ortsspur aufhoert zu gelten.

    `build_resolver` ist `None` im Request-Pfad und wird sonst erst gerufen, wenn es tatsaechlich
    etwas zu fragen gibt: ein Durchgang durch den Ortsdatensatz ohne offene Zelle waere reine
    Arbeit. Liefert die Fabrik `None` (Datensatz fehlt oder weicht von seinem Hash ab), wird nichts
    beschafft und nichts geschrieben; die Events behalten Nummer und Zeitspanne.

    DREI AUSGAENGE, und sie sind verschieden: **keine Antwort** schreibt KEINE Zeile - sonst
    vergiftete eine voruebergehende Stoerung die Zelle dauerhaft; eine **Antwort ohne brauchbare
    Ebene** schreibt eine Zeile mit leeren Namensstufen und wird nicht erneut gefragt; der dritte
    Ausgang (mehrere Namen in einem Event) faellt erst in `assign_place_names`.

    SCHREIBRAND: Jede Namensstufe laeuft EINZELN durch `sanitize_place_name` - eine unbrauchbare
    Stufe wird `NULL`, nie die ganze Antwort verworfen, und verworfen wird ganz, nie abgeschnitten.
    `matched_level` wird gegen `PLACE_LEVELS` geprueft; ein Wert ausserhalb heisst `NULL`. Beides
    wirkt hier auch fuer einen kuenftigen Auflöser hinter demselben Protokoll.

    Weder `commit` noch eigene Transaktionsgrenze - die gehoert dem Aufrufer."""
    if not cells:
        return {}

    rows = (
        await session.execute(
            select(PlaceLookup).where(
                PlaceLookup.project_id == project_id,
                tuple_(PlaceLookup.cell_lat, PlaceLookup.cell_lon).in_(list(cells)),
            )
        )
    ).scalars()
    by_cell = {
        (row.cell_lat, row.cell_lon): PlaceInfo(
            neighbourhood=row.neighbourhood,
            locality=row.locality,
            matched_level=row.matched_level,
        )
        for row in rows
    }

    missing = sorted(set(cells) - set(by_cell))
    if not missing or build_resolver is None:
        return by_cell

    resolver = build_resolver(missing)
    if resolver is None:
        return by_cell

    now = runs.now_utc()
    for cell in missing:
        answer = await resolver.resolve(cell)
        if answer is None:
            continue
        level = answer.matched_level if answer.matched_level in PLACE_LEVELS else None
        info = PlaceInfo(
            neighbourhood=sanitize_place_name(answer.neighbourhood),
            locality=sanitize_place_name(answer.locality),
            matched_level=level,
        )
        session.add(
            PlaceLookup(
                project_id=project_id,
                cell_lat=cell[0],
                cell_lon=cell[1],
                neighbourhood=info.neighbourhood,
                locality=info.locality,
                region=sanitize_place_name(answer.region),
                country=sanitize_place_name(answer.country),
                matched_level=level,
                source=PLACE_LOOKUP_SOURCE,
                resolved_at=now,
            )
        )
        by_cell[cell] = info
    return by_cell


# Die Fabrik des Namensverzeichnisses: aus der Menge der noch offenen, bereits GEFALTETEN Namen
# entsteht ein Verzeichnis oder `None`. `None` heisst "es wird keines gebaut" - weil der zweite
# Auszug fehlt oder von seinem Hash abweicht. Der Lauf bleibt arbeitsfaehig und `SUCCESS`, die
# Namen ohne Zeile fallen aber an der Ortspruefung (fail-closed).
LandmarkGazetteerFactory = Callable[[Collection[str]], LandmarkGazetteer | None]


async def landmark_points_by_name(
    session: AsyncSession,
    project_id: int,
    names: Collection[str],
    build_gazetteer: LandmarkGazetteerFactory | None,
) -> LandmarkPointsByName:
    """Die Fundorte je Sehenswuerdigkeitsname - aus dem Bestand gelesen, nur fuer die FEHLENDEN
    gefragt.

    SICHERHEIT: Die Bindung an `project_id` steht in der Abfrage ausgeschrieben, und es gibt KEINEN
    Rueckfall auf die Zeile eines anderen Projekts - ein solcher Rueckfall waere der stille Weg, auf
    dem die Lebensdauer-Bindung der Fundorte aufhoert zu gelten.

    `build_gazetteer` ist `None` im Request-Pfad und wird sonst erst gerufen, wenn es tatsaechlich
    etwas zu fragen gibt: ein Durchgang durch den zweiten Auszug ohne offenen Namen waere reine
    Arbeit. Liefert die Fabrik `None` (Auszug fehlt oder weicht von seinem Hash ab), wird nichts
    beschafft und nichts geschrieben; die Namen fehlen im ERGEBNIS und fallen damit an der
    Ortspruefung (fail-closed).

    DREI AUSGAENGE der Ablage: **keine Zeile** heisst "nie nachgeschlagen" - der Name faellt am
    Event, und beim naechsten Lauf mit Auszug wird nachgeschlagen; eine **nachgeschlagene, leere
    Punktmenge** heisst "nachgeschlagen, ohne Fund" und der Name faellt; eine **gefuellte
    Punktmenge** entscheidet die Umkreispruefung. Geschluesselt ist das Ergebnis mit dem ROhen
    Namen - genau der, den `events.py::_name_of` spaeter als Gewinnername liefert und mit dem die
    Pruefung nachschlaegt. Gefragt und abgelegt wird dagegen der GEFALTETE Name: `Trevi-Brunnen`
    trifft `trevi brunnen`.

    Weder `commit` noch eigene Transaktionsgrenze - die gehoert dem Aufrufer."""
    folded_by_name = folded_landmark_names(names)
    if not folded_by_name:
        return {}

    rows = (
        await session.execute(
            select(LandmarkPlaceLookup).where(
                LandmarkPlaceLookup.project_id == project_id,
                LandmarkPlaceLookup.folded_name.in_(set(folded_by_name.values())),
            )
        )
    ).scalars()
    points_by_folded: dict[str, tuple[tuple[float, float], ...]] = {
        row.folded_name: tuple((float(point[0]), float(point[1])) for point in row.points)
        for row in rows
    }

    missing = sorted(set(folded_by_name.values()) - set(points_by_folded))
    if missing and build_gazetteer is not None:
        gazetteer = build_gazetteer(missing)
        if gazetteer is not None:
            now = runs.now_utc()
            for folded in missing:
                points = gazetteer.points(folded)
                session.add(
                    LandmarkPlaceLookup(
                        project_id=project_id,
                        folded_name=folded,
                        points=[[lat, lon] for lat, lon in points],
                        looked_up_at=now,
                    )
                )
                points_by_folded[folded] = points

    return {
        usable: points_by_folded[folded]
        for usable, folded in folded_by_name.items()
        if folded in points_by_folded
    }


async def build_grouping_and_rankings(
    session: AsyncSession,
    run: CriterionScoringRun,
    project_id: int,
    values_by_photo_id: Mapping[int, dict[str, float]],
    build_place_resolver: PlaceResolverFactory | None,
    build_landmark_gazetteer: LandmarkGazetteerFactory | None,
) -> None:
    """Die Gliederung eines Laufs samt seiner Rangzeilen: Event-Bildung, Partitionen und
    `PhotoRanking`-Zeilen.

    ZWEI Aufrufer, EIN Weg zur Gliederung: der Kriterien-Lauf (`run_criterion_scoring`) und der
    Neuaufbau nach einer Versatz-Aenderung (`rebuild_run_grouping`). Ein zweiter Rechenweg fuer
    dasselbe liefe auseinander.

    Die Kandidatenmenge IST `values_by_photo_id.keys()`; alles Weitere liest die Funktion selbst -
    eine Abfrage mehr JE LAUF, dafuer garantiert dasselbe Verhalten beider Aufrufer.

    `build_place_resolver` hat BEWUSST KEINEN Vorgabewert: Mit einer Vorgabe `None` waere eine
    vergessene Aufrufstelle ein stiller Totalausfall der Ortsauflösung; ohne Vorgabe meldet ihn
    `mypy --strict`. `None` heisst hier "liest nur den Bestand und fragt niemanden" und ist der
    Request-Pfad.

    `build_landmark_gazetteer` hat aus DEMSELBEN Grund KEINEN Vorgabewert: `None` heisst "liest nur
    die abgelegte Auskunft, baut kein Verzeichnis" - auch das ist der Request-Pfad. Eine Vorgabe
    waere der stille Weg, auf dem eine vergessene Aufrufstelle den zweiten Auszug nie oeffnete und
    jeden Namen durchliesse.

    DIE PARTITION IST ALLEIN DAS EVENT. Ein Foto bekommt je Lauf genau eine Rangzeile; es gibt
    keine Kategorie-Ebene und keine Uebersteuerung, und die Motivstaerken bilden ausdruecklich
    keine: eine Staerke ist eine Aussage ueber den Bildinhalt, keine Zugehoerigkeit, und keine
    Schwelle macht daraus eine.

    Weder `commit` noch eigene Transaktionsgrenze - die gehoert dem Aufrufer."""
    # DIE KANDIDATENMENGE kommt aus `event_inputs` - derselben Stelle, aus der auch das rein
    # lesende Messkommando sie bezieht. Eine zweite, nachbildende Fassung maesse dort etwas anderes,
    # als dieser Lauf tut, waehrend beide fuer sich gruen blieben.
    event_inputs = await read_event_inputs(session, project_id, list(values_by_photo_id))

    # DIE EVENT-BILDUNG. Beim Kriterien-Lauf liegt die Stelle bewusst NACH dem `finally` der
    # Landmark-Phase (sonst fehlten die Namen, die dieser Lauf gerade erst erzeugt hat) und VOR
    # dem Aufbau von `partitions` unten (der Partitionsschluessel IST die `event_id`).
    #
    # `PhotoScore.cluster_key` wird dabei NIE mutiert (Ownership-Grenze): der dort stehende
    # Phase-A-Basiswert bleibt stabil, unabhaengig davon, ob und wann Kriterien-Scoring laeuft.
    # Die Divergenz zu `PhotoRanking.event_id` ist gewollt.
    # DIE ORTSPLAUSIBILITAET DES SEHENSWUERDIGKEITSNAMENS, zwischen dem Einlesen und der
    # Event-Bildung: gefragt wird die KANDIDATENMENGE, nicht nur die Gewinnermenge - der Gewinner
    # entsteht erst INNERHALB von `_built`, und nur-Gewinner hiesse, die Eventbildung zweimal zu
    # rechnen oder die Namenswahl aus `_built` herauszuziehen.
    landmark_names = {
        candidate.landmark_name
        for candidate in event_inputs.candidates
        if candidate.landmark_name is not None
    }
    points_by_name = await landmark_points_by_name(
        session, project_id, landmark_names, build_landmark_gazetteer
    )

    built_events = build_events(event_inputs.candidates, landmark_points_by_name=points_by_name)

    # DIE ORTSNAMEN, zwischen Event-Bildung und Schreiben der Zeilen. Gefragt wird fuer JEDES
    # Event mit einer gemessenen Zelle - auch fuer ein benanntes: der Sehenswuerdigkeitsname steht
    # NEBEN dem Ortsnamen und verdeckt ihn nicht mehr, also braucht auch ein benanntes Event seine
    # Ortsaufloesung. Seine `place_kind` bleibt trotzdem `landmark` - verdraengt bleibt allein die
    # KOORDINATENSTUFE (`_place_of`).
    cells = {cell for built in built_events for cell in built.place_cells}
    info_by_cell = await place_infos(session, project_id, cells, build_place_resolver)
    place_names = assign_place_names(built_events, info_by_cell)

    event_rows = [
        Event(
            criterion_scoring_run_id=run.id,
            position=built.position,
            started_at=built.started_at,
            ended_at=built.ended_at,
            landmark_name=built.landmark_name,
            place_kind=built.place_kind,
            place_lat=built.place_lat,
            place_lon=built.place_lon,
            place_name=place_name,
        )
        for built, place_name in zip(built_events, place_names, strict=True)
    ]
    session.add_all(event_rows)
    # EIN `flush` fuer alle Events, nicht einer je Event: die Ids werden unten als
    # Partitionsschluessel gebraucht und stehen erst nach dem Schreiben fest.
    await session.flush()
    event_id_by_photo = {
        photo_id: event.id
        for built, event in zip(built_events, event_rows, strict=True)
        for photo_id in built.photo_ids
    }

    # DIE ZAEHLENDE MODELLSTUFE als Grundlage des Qualitaetswerts - gelesen aus der Tabelle des am
    # LAUF eingefrorenen Verfahrens, nie aus der heutigen Projekteinstellung und nie aus einer
    # laufinternen Abbildung: Diese Funktion hat auch den zweiten Aufrufer
    # (`rebuild_run_grouping`), der keine Bewertungsphase kennt. Fehlt die Stufe dieses Verfahrens,
    # wird der Qualitaetswert `NULL` - es gibt keinen Rueckfall auf das andere Verfahren und keinen
    # lokal gebildeten Wert.
    level_by_photo_id = await load_album_levels(
        session, run.album_level_source, values_by_photo_id.keys()
    )

    # DIE GEWICHTE EINMAL JE LAUF, vor der Partitionsschleife - nicht je Foto: Die geltende Fassung
    # aendert sich waehrend eines Laufs nicht, und ein Lesegang je Foto fiele an keinem Ergebnis
    # auf. Welche Fassung gerechnet hat, haelt die Lauf-Zeile fest; ohne sie ist ein vergangener
    # Rang-Score nach der naechsten Anpassung nicht mehr nachrechenbar. `NULL` heisst dort
    # "Startwerte oder Altzeile".
    weights = await effective_weights(session)
    used_weight_set = await latest_weight_set(session)
    run.quality_weight_set_id = None if used_weight_set is None else used_weight_set.id

    # Eine Partition je Event, ein Foto in genau einer davon.
    partitions: dict[int, dict[int, dict[str, float]]] = {}
    for photo_id, values in values_by_photo_id.items():
        partitions.setdefault(event_id_by_photo[photo_id], {})[photo_id] = values

    for event_id, partition_candidates in partitions.items():
        # `rank_photos` laeuft NUR ueber die bewertete Teilmenge - `rank_position` bleibt dort
        # lueckenlos ab 1. Die uebrigen Fotos der Partition bekommen ihre Zeile unten mit `NULL`
        # in beiden Spalten: sie behalten ihre `event_id`, bleiben im einsehbaren Vorrat und
        # erscheinen nicht im Entwurf.
        quality_scores = {
            photo_id: compute_quality_score(level_by_photo_id[photo_id], values, weights)
            for photo_id, values in partition_candidates.items()
            if photo_id in level_by_photo_id
        }
        ranked_by_photo_id = {ranked.photo_id: ranked for ranked in rank_photos(quality_scores)}
        for photo_id in partition_candidates:
            ranked = ranked_by_photo_id.get(photo_id)
            session.add(
                PhotoRanking(
                    criterion_scoring_run_id=run.id,
                    photo_id=photo_id,
                    event_id=event_id,
                    rank_score=None if ranked is None else ranked.rank_score,
                    rank_position=None if ranked is None else ranked.rank_position,
                )
            )

    # Das `flush` am Ende: Beide Aufrufer rechnen danach den Auswahlvorschlag
    # (`apply_run_selection`), und der liest die Rangzeilen aus der Datenbank - die eben
    # hinzugefuegten stehen dort erst danach.
    await session.flush()


async def apply_run_selection(
    session: AsyncSession, run: CriterionScoringRun, project_id: int
) -> None:
    """Der Auswahlvorschlag DIESES Laufs: auswahlfaehige Kandidaten laden, die reine Funktion
    rufen, `selection_position` schreiben.

    DIE EINE Rechenstelle fuer alle drei Ausloeser (Kriterien-Lauf, Neuaufbau nach einer
    Versatz-Aenderung, Aenderung des Richtwerts). Ein zweiter Rechenweg liefe auseinander.

    AUSWAHLFAEHIG ist eine Rangzeile dieses Laufs mit `rank_score IS NOT NULL` und ohne
    `excluded_document` am Foto: ein als Dokument oder Bildschirmabbild erkanntes Foto erscheint in
    keiner Motivauswahl, und der Vorschlag ist eine - es zaehlt deshalb auch nicht als Motivtraeger
    und lenkt die Vergabe nicht um.

    SICHERHEIT: `PhotoRanking` traegt keine `project_id` - die Lauf-Id ist die einzige
    Projektbindung. `criterion_scoring_run_id == run.id` steht deshalb AUSGESCHRIEBEN in jeder
    lesenden und jeder schreibenden Anweisung hier. Fehlte es auch nur in der Schreibanweisung,
    setzte ein Aufruf unter Projekt A `selection_position` auf Rangzeilen eines fremden Laufs -
    ein kohaerenter, aber fremder Vorschlag, dem die Antwort nichts ansieht.

    SICHERHEIT: `user_id` fliesst in keine Abfrage und in keine Schreibanweisung. Der Vorschlag ist
    lauf-global; eine je Nutzer verschiedene Position entsteht nicht.

    Weder `commit` noch eigene Transaktionsgrenze - die gehoert dem Aufrufer."""
    project = await session.get(Project, project_id)
    if project is None:
        return

    # ZURUECKSETZEN ZUERST, und zwar ueber den gesamten Lauf: ein Foto, das im vorigen Vorschlag
    # stand und im neuen nicht mehr, behielte sonst seinen alten Platz.
    await session.execute(
        update(PhotoRanking)
        .where(PhotoRanking.criterion_scoring_run_id == run.id)
        .values(selection_position=None)
    )

    rows = (
        await session.execute(
            select(
                PhotoRanking.photo_id,
                PhotoRanking.event_id,
                PhotoRanking.rank_score,
                Event.position,
                Photo.taken_at,
            )
            .join(Event, Event.id == PhotoRanking.event_id)
            .join(Photo, Photo.id == PhotoRanking.photo_id)
            .where(
                PhotoRanking.criterion_scoring_run_id == run.id,
                Event.criterion_scoring_run_id == run.id,
                Photo.project_id == project_id,
                PhotoRanking.rank_score.is_not(None),
            )
        )
    ).all()
    if not rows:
        return

    candidate_ids = [photo_id for photo_id, _event_id, _score, _position, _taken_at in rows]
    excluded = set(
        (
            await session.execute(
                select(PhotoMotifAssessment.photo_id).where(
                    PhotoMotifAssessment.photo_id.in_(candidate_ids),
                    PhotoMotifAssessment.excluded_document.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    eligible_ids = [photo_id for photo_id in candidate_ids if photo_id not in excluded]
    # Die WIRKSAMEN Staerken, Korrekturen inbegriffen - nie die rohe Staerkezeile.
    strengths_by_photo_id = await load_effective_strengths(session, eligible_ids)
    # Die WIRKSAMEN Personen (Korrektur vor Erkennung, dieselbe Menge wie der Personenfilter),
    # LIVE gelesen und nur fuer `eligible_ids` - damit erbt das Laden die Projektbindung der
    # Rangzeilen. Weiter geht ausschliesslich `person_id`, nie ein Name; ein Paar (Foto, Person)
    # gehoert in keine Logzeile und keinen Fehlertext, denn beide ueberleben die Loeschung der
    # Person.
    persons_by_photo_id = await load_effective_persons(session, eligible_ids)

    candidates_by_event: dict[int, list[SelectionCandidate]] = {}
    position_by_event: dict[int, int] = {}
    for photo_id, event_id, rank_score, position, taken_at in rows:
        if photo_id in excluded:
            continue
        position_by_event[event_id] = position
        candidates_by_event.setdefault(event_id, []).append(
            SelectionCandidate(
                photo_id=photo_id,
                taken_at=taken_at,
                quality=rank_score,
                motif_strengths={
                    motif_key: effective.strength
                    for motif_key, effective in strengths_by_photo_id.get(photo_id, {}).items()
                },
                person_ids=frozenset(
                    assignment.person_id for assignment in persons_by_photo_id.get(photo_id, [])
                ),
            )
        )

    draft = select_album_draft(
        [
            SelectionEvent(
                event_id=event_id,
                position=position_by_event[event_id],
                candidates=candidates,
            )
            for event_id, candidates in candidates_by_event.items()
        ],
        effective_target(project.selection_target),
    )
    if not draft:
        return

    # Je PLATZ eine Anweisung statt je Foto: die Zahl der Anweisungen ist damit die groesste
    # Platzzahl eines Events und nicht die Groesse des Vorschlags.
    photo_ids_by_place: dict[int, list[int]] = {}
    for photo_id, place in draft.items():
        photo_ids_by_place.setdefault(place, []).append(photo_id)
    for place, photo_ids in sorted(photo_ids_by_place.items()):
        await session.execute(
            update(PhotoRanking)
            .where(
                PhotoRanking.criterion_scoring_run_id == run.id,
                PhotoRanking.photo_id.in_(sorted(photo_ids)),
            )
            .values(selection_position=place)
        )
