"""Tests fuer das rein lesende Messkommando der Event-Bildung
(specs/features/0506-cluster-als-anlass.md, decisions/0117-*.md).

Aufbau nach architecture/0002-testkonzept.md, Sektion "Ein rein lesendes Kommando im
Produktivpaket": die Zaehlbloecke rein und ohne DB gegen einen von Hand ausgerechneten
Projektgraphen, `main()` synchron gegen eine dateibasierte SQLite in `tmp_path`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.event_probe import (
    DISTANCE_THRESHOLD_METERS,
    EventProbeError,
    cause_counts,
    inheritance_counts,
    landmark_counts,
    match_distance_counts,
    read_event_probe_input,
    size_counts,
)
from photosort.events import (
    BOUNDARY_CAUSES,
    BOUNDARY_MOTIF_CHANGE,
    BOUNDARY_STEP,
    BOUNDARY_TIME_GAP,
    BuiltEvent,
    EventCandidate,
    EventFormation,
    LocationEntry,
    explain_events,
)
from photosort.geonames import GEONAMES_MAX_DISTANCE_METERS
from photosort.models import (
    CriterionScoringRun,
    Event,
    Photo,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
)

NOW = datetime(2026, 7, 20, 10, 0, 0)


def _candidate(minutes: float, *, gps: tuple[float, float] | None = None) -> EventCandidate:
    """Ein Kandidat OHNE Ort, sofern keiner genannt ist: die Zeitluecke allein gliedert dann."""
    return EventCandidate(
        photo_id=int(minutes * 60),
        taken_at=NOW + timedelta(minutes=minutes),
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
    )


def _candidate_of(entry: LocationEntry) -> EventCandidate:
    """Derselbe Eintrag als Kandidat - ohne `location`, weil Block C1 die Uebernahme selbst misst
    und nicht ihr Ergebnis."""
    return EventCandidate(
        photo_id=entry.photo_id,
        taken_at=entry.taken_at,
        gps_lat=entry.gps_lat,
        gps_lon=entry.gps_lon,
    )


def _named_candidate(
    photo_id: int, minutes: float, name: str, *, gps: tuple[float, float] | None = None
) -> EventCandidate:
    """Ein Kandidat mit bereits geprueftem Sehenswuerdigkeit-Namen - so, wie ihn `event_inputs`
    liefert (`usable_landmark_name` ist dort bereits gelaufen)."""
    return EventCandidate(
        photo_id=photo_id,
        taken_at=NOW + timedelta(minutes=minutes),
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
        landmark_name=name,
    )


async def _project(session: AsyncSession, name: str = "Reise") -> int:
    project = Project(name=name, opencloud_drive_id="drive", opencloud_path=f"/Fotos/{name}")
    session.add(project)
    await session.flush()
    return project.id


async def _photo(
    session: AsyncSession,
    project_id: int,
    *,
    minutes: float,
    gps: tuple[float, float] | None = None,
) -> int:
    photo = Photo(
        project_id=project_id,
        relative_path=f"img{int(minutes * 60):06d}.jpg",
        etag=f"etag-{project_id}-{minutes}",
        content_length=1000,
        taken_at=NOW + timedelta(minutes=minutes),
        taken_at_original=NOW + timedelta(minutes=minutes),
        last_modified=NOW,
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
    )
    session.add(photo)
    await session.flush()
    return photo.id


async def _successful_run(
    session: AsyncSession, project_id: int, photo_ids: list[int]
) -> CriterionScoringRun:
    """Ein erfolgreicher Kriterien-Lauf samt seiner Rangzeilen - die Kandidatenmenge des Laufs.

    Ein Event je Rangzeile: Block A rechnet die Gliederung ohnehin neu, die Event-Zeile traegt
    hier nur den Fremdschluessel."""
    scoring_run = ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project_id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.flush()
    event = Event(
        criterion_scoring_run_id=run.id, position=1, started_at=NOW, ended_at=NOW, place_kind=None
    )
    session.add(event)
    await session.flush()
    session.add_all(
        [
            PhotoRanking(
                criterion_scoring_run_id=run.id,
                photo_id=photo_id,
                event_id=event.id,
                rank_score=0.5,
                rank_position=position,
            )
            for position, photo_id in enumerate(photo_ids, start=1)
        ]
    )
    await session.flush()
    return run


@pytest.mark.asyncio
class TestTheReadPath:
    """Der einzige Datenbankzugriff des Kommandos - und er liest ausschliesslich."""

    async def test_an_unknown_project_refuses_loudly(self, db_session: AsyncSession) -> None:
        with pytest.raises(EventProbeError):
            await read_event_probe_input(db_session, 4711)

    async def test_a_project_without_a_successful_run_is_marked_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """ "Kein erfolgreicher Lauf" ist etwas anderes als "ein Lauf ohne Kandidaten" - eine
        gemeinsame leere Menge verwischte beides."""
        project_id = await _project(db_session)
        await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))

        probe = await read_event_probe_input(db_session, project_id)

        assert probe.run_found is False
        assert probe.candidates == ()

    async def test_the_candidates_are_the_ranked_photos_of_the_run(
        self, db_session: AsyncSession
    ) -> None:
        """Die Kandidatenmenge des Laufs sind genau die Fotos seiner Rangzeilen - nicht die
        aktuellen Fotos des Projekts. Ein nach dem Lauf aussortiertes oder hinzugekommenes Foto
        speist die Inferenzbasis, wird aber nie Kandidat."""
        project_id = await _project(db_session)
        ranked = await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))
        unranked = await _photo(db_session, project_id, minutes=5, gps=(43.52, 16.45))
        await _successful_run(db_session, project_id, [ranked])

        probe = await read_event_probe_input(db_session, project_id)

        assert probe.run_found is True
        assert [candidate.photo_id for candidate in probe.candidates] == [ranked]
        # Die Inferenzbasis bleibt das ganze Projekt: ein aussortiertes Foto traegt eine ebenso
        # gueltige Koordinate.
        assert {entry.photo_id for entry in probe.entries} == {ranked, unranked}

    async def test_only_the_latest_successful_run_is_measured(
        self, db_session: AsyncSession
    ) -> None:
        project_id = await _project(db_session)
        older = await _photo(db_session, project_id, minutes=0, gps=(43.51, 16.44))
        newer = await _photo(db_session, project_id, minutes=5, gps=(43.52, 16.45))
        await _successful_run(db_session, project_id, [older])
        await _successful_run(db_session, project_id, [newer])

        probe = await read_event_probe_input(db_session, project_id)

        assert [candidate.photo_id for candidate in probe.candidates] == [newer]


class TestBlockASizes:
    """Wie sich die Bilder heute ueber die Cluster verteilen - der Ausgangswert, gegen den die
    Abnahme laeuft."""

    def test_the_hand_computed_graph(self) -> None:
        """Vier Events zu 3, 1, 2 und 1 Fotos. Die Zeitluecke steht bei einer Stunde; die
        Abstaende sind so gewaehlt, dass sie klar darueber bzw. darunter liegen - kein Fall
        haengt an einem Zahlwert der Schwelle."""
        formation = explain_events(
            [
                # Event 1: drei Fotos ueber acht Minuten.
                _candidate(0),
                _candidate(4),
                _candidate(8),
                # Event 2: ein einzelnes Foto.
                _candidate(200),
                # Event 3: zwei Fotos ueber zwei Minuten.
                _candidate(400),
                _candidate(402),
                # Event 4: ein einzelnes Foto.
                _candidate(600),
            ]
        )

        counts = size_counts(formation)

        assert counts.events_total == 4
        assert counts.photos_total == 7
        assert counts.events_by_photo_count == {1: 2, 2: 1, 3: 1}
        assert counts.single_photo_events == 2
        # Die vier Groessen sortiert: 1, 1, 2, 3 - der Median liegt zwischen 1 und 2.
        assert counts.median_photos == 1.5
        assert counts.largest_event_photos == 3
        # DAUERN, nie Anfang oder Ende (S2): laengste acht Minuten, kuerzeste null (Einzelfoto).
        assert counts.longest_seconds == 8 * 60
        assert counts.shortest_seconds == 0

    def test_a_run_without_a_single_event_is_a_valid_result(self) -> None:
        """Ein Lauf ohne Kandidaten ist ein gueltiges Messergebnis, kein Fehler - es gibt dann
        keine laengste und keine kuerzeste Dauer, und `None` ist etwas anderes als null."""
        counts = size_counts(explain_events([]))

        assert counts.events_total == 0
        assert counts.photos_total == 0
        assert counts.events_by_photo_count == {}
        assert counts.single_photo_events == 0
        assert counts.median_photos is None
        assert counts.largest_event_photos == 0
        assert counts.longest_seconds is None
        assert counts.shortest_seconds is None


def _segment(position: int, photo_count: int) -> BuiltEvent:
    """Ein fertiges Segment fuer die Zaehlung von Block B - nur Groesse und Position zaehlen."""
    return BuiltEvent(
        position=position,
        photo_ids=tuple(range(position * 100, position * 100 + photo_count)),
        started_at=NOW,
        ended_at=NOW,
    )


def _formation(*segments: tuple[int, frozenset[str]]) -> EventFormation:
    """Eine Gliederung SAMT Ursachen, von Hand gestellt: `(Fotozahl, Ursachenmenge)` je Segment.

    Von Hand statt ueber `explain_events`, weil Block B eine reine Zaehlung ueber die Ursachen ist
    - eine Testlage aus Zeitabstaenden haenge an den Zahlwerten der Schwellen und waere nach der
    Kalibrierung eine Zeitbombe."""
    return EventFormation(
        events=tuple(
            _segment(position, photo_count)
            for position, (photo_count, _) in enumerate(segments, start=1)
        ),
        causes=tuple(causes for _, causes in segments),
    )


class TestBlockBCauses:
    """Welche Trennursache wie oft trennt. Nur "war alleinige Ursache" ist handlungsleitend - eine
    Schwelle anzuheben hilft dort, wo sie allein getrennt hat."""

    def test_the_hand_computed_graph(self) -> None:
        counts = cause_counts(
            _formation(
                # Das erste Segment traegt KEINE Ursache - die Ausnahme haengt an der Position.
                (3, frozenset()),
                # Alleinige Ursache, und sie eroeffnet ein Ein-Bild-Segment.
                (1, frozenset({BOUNDARY_TIME_GAP})),
                # ZWEI Ursachen gleichzeitig: beteiligt, aber keine allein.
                (4, frozenset({BOUNDARY_TIME_GAP, BOUNDARY_STEP})),
                # Alleinige Ursache, aber das Segment ist gross genug.
                (2, frozenset({BOUNDARY_STEP})),
                (1, frozenset({BOUNDARY_MOTIF_CHANGE})),
            )
        )

        # Die Zahl der Grenzen MIT Ursache ist stets `Eventzahl - 1`.
        assert counts.boundaries_total == 4
        assert counts.involved[BOUNDARY_TIME_GAP] == 2
        assert counts.involved[BOUNDARY_STEP] == 2
        assert counts.involved[BOUNDARY_MOTIF_CHANGE] == 1
        # Die Doppelgrenze zaehlt bei KEINER der beiden als alleinige Ursache.
        assert counts.sole[BOUNDARY_TIME_GAP] == 1
        assert counts.sole[BOUNDARY_STEP] == 1
        assert counts.sole[BOUNDARY_MOTIF_CHANGE] == 1
        # Zu kleine Segmente: das Ein-Bild-Segment hinter der Zeitluecke und das hinter dem
        # Motivwechsel. Das Zwei-Bild-Segment hinter dem Schritt zaehlt nicht mit.
        assert counts.opening_a_small_segment[BOUNDARY_TIME_GAP] == 1
        assert counts.opening_a_small_segment[BOUNDARY_STEP] == 0
        assert counts.opening_a_small_segment[BOUNDARY_MOTIF_CHANGE] == 1

    def test_every_cause_of_the_closed_supply_appears_even_at_zero(self) -> None:
        """Eine Ursache, die im Lauf nie gemeldet hat, steht mit null da - sie faellt nicht aus dem
        Bericht. Sonst waere er still unvollstaendig, ohne dass eine Summe kleiner wuerde."""
        counts = cause_counts(_formation((2, frozenset()), (2, frozenset({BOUNDARY_TIME_GAP}))))

        assert set(counts.involved) == set(BOUNDARY_CAUSES)
        assert set(counts.sole) == set(BOUNDARY_CAUSES)
        assert set(counts.opening_a_small_segment) == set(BOUNDARY_CAUSES)

    def test_a_single_event_has_no_boundary_at_all(self) -> None:
        counts = cause_counts(_formation((5, frozenset())))

        assert counts.boundaries_total == 0
        assert sum(counts.involved.values()) == 0

    def test_a_run_without_events_does_not_report_a_negative_boundary_count(self) -> None:
        counts = cause_counts(explain_events([]))

        assert counts.boundaries_total == 0

    def test_a_cause_outside_the_closed_supply_refuses_loudly(self) -> None:
        """Nicht stillschweigend uebergehen: Ein kuenftiges Signal ohne Eintrag in
        `BOUNDARY_CAUSES` verschwaende sonst aus dem Bericht, ohne dass eine Summe kleiner wuerde."""
        with pytest.raises(EventProbeError):
            cause_counts(_formation((2, frozenset()), (2, frozenset({"erfunden"}))))


# --- Block C: die Ortszuordnung, je Mechanismus getrennt -----------------------------------------
#
# Die Entfernungen der Messlage sind nachgerechnet: 0,002 Grad Breite sind rund 222 m, 0,01 Grad
# rund 1112 m, 0,2 Grad rund 22 239 m. Sie liegen damit klar in ihrer Klasse und nicht auf einer
# Grenze.
def _entry(photo_id: int, minutes: float, gps: tuple[float, float] | None = None) -> LocationEntry:
    return LocationEntry(
        photo_id=photo_id,
        taken_at=NOW + timedelta(minutes=minutes),
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
    )


class TestBlockC1InheritedLocations:
    """Der uebernommene Ort - er speist Schritt- und Ausdehnungssignal und damit die Grenzen.

    Beide Groessen stehen NUR in Klassen (S5): Sie entstehen aus voller EXIF-Praezision, und eine
    geordnete Folge daraus waere ein Streckenabdruck."""

    def test_the_hand_computed_graph(self) -> None:
        entries = [
            _entry(1, 0, (0.0, 0.0)),
            # Erbt vom frueheren Anker (30 s) - die Ankerspanne ist die Entfernung zwischen den
            # beiden Nachbarn, rund 22 km.
            _entry(2, 0.5),
            _entry(3, 10, (0.2, 0.0)),
            # NACH dem letzten Anker: es gibt nur einen Nachbarn, also KEINE Spanne - und `None`
            # ist ausdruecklich nicht null.
            _entry(4, 20),
        ]
        candidates = [_candidate_of(entry) for entry in entries]

        counts = inheritance_counts(entries, candidates)

        assert counts.candidates_total == 4
        assert counts.candidates_without_own_coordinate == 2
        assert counts.inheriting == 2
        # 30 s in der untersten Klasse, 600 s in "5 bis unter 30 min".
        assert counts.seconds_to_anchor_classes == (1, 0, 1, 0, 0, 0)
        # Die eine gemessene Spanne liegt ueber der Schwelle.
        assert counts.anchor_span_classes == (0, 0, 0, 0, 1)
        assert counts.without_anchor_span == 1

    def test_only_candidates_are_reported_though_the_whole_project_anchors(self) -> None:
        """Die Inferenzbasis ist das ganze Projekt - berichtet werden die KANDIDATEN. Ein nach dem
        Lauf aussortiertes Foto ohne Koordinate gehoert in keine der beiden Verteilungen; die
        Grenzen dieses Laufs haengen nicht an ihm."""
        entries = [
            _entry(1, 0, (0.0, 0.0)),
            _entry(2, 0.5),
            _entry(3, 3),
            _entry(4, 10, (0.2, 0.0)),
        ]
        candidates = [
            _candidate_of(entries[0]),
            _candidate_of(entries[1]),
            _candidate_of(entries[3]),
        ]

        counts = inheritance_counts(entries, candidates)

        assert counts.candidates_total == 3
        assert counts.candidates_without_own_coordinate == 1
        assert counts.inheriting == 1

    def test_without_a_single_anchor_nobody_inherits(self) -> None:
        """Der entartete Fall: Ohne jeden Anker erbt niemand. Die Zahl der Kandidaten ohne eigene
        Koordinate bleibt trotzdem stehen - sie ist etwas anderes als die Zahl der Uebernahmen."""
        entries = [_entry(1, 0), _entry(2, 5)]
        candidates = [_candidate_of(entry) for entry in entries]

        counts = inheritance_counts(entries, candidates)

        assert counts.candidates_without_own_coordinate == 2
        assert counts.inheriting == 0
        assert counts.seconds_to_anchor_classes == (0, 0, 0, 0, 0, 0)


class TestBlockC2MatchDistances:
    """Der aufgeloeste Ortsname: die Entfernung zwischen Aufnahmeposition und dem Eintrag, der den
    Namen geliefert hat. Ausgegeben in Klassen, nie je Zelle (S4)."""

    def test_the_hand_computed_graph(self) -> None:
        counts = match_distance_counts(
            {
                (0.0, 0.0): 120.0,
                (0.1, 0.0): 3000.0,
                (0.2, 0.0): 22239.0,
                # Eine Zelle, die gar keinen Ortsnamen bekaeme - sie traegt keine Entfernung und
                # darf keine Klasse besetzen.
                (0.3, 0.0): None,
            }
        )

        assert counts.cells_total == 4
        assert counts.cells_with_a_name == 3
        assert counts.distance_classes == (1, 0, 1, 0, 1)
        assert counts.cells_beyond_threshold == 1

    def test_the_threshold_is_the_topmost_class_boundary(self) -> None:
        """Der Anteil oberhalb der Schwelle wird aus der obersten Klasse ABGELESEN, nie ein zweites
        Mal gerechnet - ein zweiter Vergleich liefe beim naechsten Grenzfall auseinander."""
        counts = match_distance_counts(
            {(0.0, 0.0): DISTANCE_THRESHOLD_METERS, (0.1, 0.0): DISTANCE_THRESHOLD_METERS - 1}
        )

        assert counts.distance_classes[-1] == 1
        assert counts.cells_beyond_threshold == counts.distance_classes[-1]

    def test_the_threshold_lies_below_what_the_resolver_will_even_return(self) -> None:
        """Eine Ungleichung, kein Zahlwert: Laege die Schwelle ueber
        `GEONAMES_MAX_DISTANCE_METERS`, koennte Block C2 sie strukturell nie ueberschreiten - der
        Auflöser verwirft weiter entfernte Treffer bereits -, und ein Anteil von null waere dann
        eine Eigenschaft der Schwelle statt ein Messergebnis."""
        assert DISTANCE_THRESHOLD_METERS < GEONAMES_MAX_DISTANCE_METERS


class TestBlockC3LandmarkNames:
    """Der Sehenswuerdigkeitsname - der Weg, ueber den eine Ortsaussage am weitesten danebenliegen
    kann: Ein Name benennt das GANZE Event und verdraengt dessen Koordinatenstufe."""

    def test_a_detection_without_any_place_hint(self) -> None:
        """`landmark.py::place_hint_for` liefert fuer ein Foto ohne eigenes GPS `None` - die
        Erkennung entstand dann ohne jeden Ortshinweis. Ein uebernommener Ort erreicht diese
        Funktion nie."""
        with_gps = _named_candidate(1, 0, "Palast", gps=(0.0, 0.0))
        without_gps = _named_candidate(2, 1, "Palast")

        counts = landmark_counts([with_gps, without_gps], explain_events([]), {})

        assert counts.detections_total == 2
        assert counts.detections_without_place_hint == 1

    def test_a_name_whose_carriers_lie_further_apart_than_the_threshold(self) -> None:
        """Ein innerer Widerspruch, fuer den es keine aeussere Wahrheit braucht: Dieselbe
        Sehenswuerdigkeit kann nicht an zwei 22 km auseinanderliegenden Orten stehen."""
        candidates = [
            _named_candidate(1, 0, "Weit", gps=(0.0, 0.0)),
            _named_candidate(2, 1, "Weit", gps=(0.2, 0.0)),
            # Derselbe Ortsbesuch, rund 1,1 km auseinander - kein Widerspruch.
            _named_candidate(3, 2, "Nah", gps=(0.0, 0.0)),
            _named_candidate(4, 3, "Nah", gps=(0.01, 0.0)),
        ]

        counts = landmark_counts(candidates, explain_events([]), {})

        assert counts.names_total == 2
        assert counts.names_spread_beyond_threshold == 1

    def test_an_event_named_by_exactly_one_of_many_photos(self) -> None:
        """Ein einziges erkanntes Foto benennt hier zwoelf - der Name traegt dann eine Aussage
        ueber Fotos, zu denen er nie erhoben wurde."""
        named = _named_candidate(1, 0, "Palast", gps=(0.0, 0.0))
        others = [_candidate(minutes) for minutes in (1, 2)]
        formation = explain_events([named, *others])

        counts = landmark_counts([named, *others], formation, {})

        assert len(formation.events) == 1
        assert counts.events_named_by_a_single_photo == 1

    def test_an_event_whose_photos_all_carry_the_name_is_not_counted(self) -> None:
        candidates = [
            _named_candidate(1, 0, "Palast", gps=(0.0, 0.0)),
            _named_candidate(2, 1, "Palast", gps=(0.0, 0.0)),
        ]
        formation = explain_events(candidates)

        counts = landmark_counts(candidates, formation, {})

        assert len(formation.events) == 1
        assert counts.events_named_by_a_single_photo == 0

    def test_a_single_photo_event_is_not_counted_either(self) -> None:
        """ "Auf genau einem von VIELEN Fotos" - ein Event aus einem einzigen Foto ist kein
        Widerspruch, sondern der Normalfall."""
        named = _named_candidate(1, 0, "Palast", gps=(0.0, 0.0))
        formation = explain_events([named])

        counts = landmark_counts([named], formation, {})

        assert counts.events_named_by_a_single_photo == 0
