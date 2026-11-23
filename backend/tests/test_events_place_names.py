"""Ereignis-Gruppierung: Ortsname eines Ereignisses, sein Rueckhalt in den Fotos und die
Namensvergabe ueber die Ereignisse eines Laufs.
"""

from __future__ import annotations

import math
from dataclasses import replace
from itertools import permutations

import pytest

from photosort import events as events_module
from photosort.events import (
    BuiltEvent,
    ExtentSignal,
    assign_place_names,
)
from photosort.places import MAX_PLACE_NAME_LENGTH, PlaceInfo
from photosort.scoring import haversine_meters
from tests.support.event_grouping import (
    BASE_LAT,
    BASE_LON,
    EPSILON_TIME,
    T0,
    _at,
    _build,
    _confirming,
    _inherited_candidate,
    _latitude_at,
    _measured_candidate,
    _min_share,
    _north,
    _placeless_candidate,
    _radius,
    _time_gap,
)


class TestEventPlace:
    """Der Ortsbezug entsteht AUSSCHLIESSLICH aus gemessenen Koordinaten und Namen."""

    def test_inherited_coordinates_never_feed_the_place(self) -> None:
        """Obwohl die uebernommenen Werte die Grenzen mitbestimmt haben."""
        candidates = [
            _inherited_candidate(1, T0),
            _inherited_candidate(2, _at(minutes=1), lat=_north(100.0)),
        ]

        [event] = _build(candidates)

        assert (event.place_kind, event.place_lat, event.place_lon) == (None, None, None)

    def test_inherited_coordinates_still_determine_the_boundaries(self) -> None:
        candidates = [
            _inherited_candidate(1, T0),
            _inherited_candidate(2, _at(minutes=1), lat=_north(5000.0)),
        ]

        assert len(_build(candidates, [ExtentSignal()])) == 2

    def test_a_single_rounded_cell_becomes_a_coordinate(self) -> None:
        candidates = [
            _measured_candidate(1, T0, lat=48.8584, lon=2.2945),
            _measured_candidate(2, _at(minutes=1), lat=48.8590, lon=2.2950),
        ]

        [event] = _build(candidates)

        assert (event.place_kind, event.place_lat, event.place_lon) == ("coordinate", 48.86, 2.29)

    def test_the_written_coordinate_is_rounded_never_full_precision(self) -> None:
        [event] = _build([_measured_candidate(1, T0, lat=48.858370, lon=2.294481)])

        assert (event.place_lat, event.place_lon) == (48.86, 2.29)

    def test_minus_zero_is_normalised(self) -> None:
        [event] = _build([_measured_candidate(1, T0, lat=-0.001, lon=-0.002)])

        assert (event.place_lat, event.place_lon) == (0.0, 0.0)
        assert str(event.place_lat) == "0.0"

    def test_two_cells_become_multiple_without_any_coordinate(self) -> None:
        candidates = [
            _measured_candidate(1, T0, lat=48.85, lon=2.29),
            _measured_candidate(2, _at(minutes=1), lat=48.95, lon=2.29),
        ]

        [event] = _build(candidates, [])

        assert (event.place_kind, event.place_lat, event.place_lon) == ("multiple", None, None)

    def test_a_name_wins_over_any_coordinate(self) -> None:
        candidates = [
            _measured_candidate(1, T0, lat=48.85, lon=2.29, landmark_name="Eiffelturm"),
            _measured_candidate(2, _at(minutes=1), lat=48.85, lon=2.29, landmark_name="Eiffelturm"),
        ]

        [event] = _build(
            candidates, landmark_points_by_name=_confirming("Eiffelturm", at=(48.85, 2.29))
        )

        assert event.place_kind == "landmark"
        assert event.landmark_name == "Eiffelturm"
        assert (event.place_lat, event.place_lon) == (None, None)

    def test_an_event_takes_a_name_that_one_of_its_photos_backs(self) -> None:
        """Der Rueckhalt, nicht die Reihenfolge: Ein einzelner benannter unter zwei Fotos genuegt
        (die Haelfte liegt ueber dem Zehntel) - auch wenn er nicht das erste ist."""
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), landmark_name="Eiffelturm"),
        ]

        [event] = _build(candidates, [], landmark_points_by_name=_confirming("Eiffelturm"))

        assert event.landmark_name == "Eiffelturm"

    def test_two_names_with_the_same_support_leave_the_earlier_one_winning(self) -> None:
        """Der GLEICHSTAND: Zwei Namen mit JE einem Traegerfoto. Der Rueckhalt entscheidet zuerst,
        die Reihenfolge erst bei Gleichstand - hier gewinnt deshalb der fruehere."""
        candidates = [
            _measured_candidate(1, T0, landmark_name="Zugspitze"),
            _measured_candidate(2, T0 + EPSILON_TIME, landmark_name="Eibsee"),
        ]

        [event] = _build(candidates, landmark_points_by_name=_confirming("Zugspitze", "Eibsee"))

        assert event.photo_ids == (1, 2)
        assert event.landmark_name == "Zugspitze"
        assert event.place_kind == "landmark"

    def test_the_name_with_more_support_wins_across_a_merge_of_the_third_stage(self) -> None:
        """`_built` laeuft NACH Stufe 3, gezaehlt wird also ueber die Mitglieder des FERTIGEN
        Events. Das zu kleine Segment stellt den FRUEHEREN Namen voran - er verliert trotzdem, weil
        ihn nur ein Foto bezeugt und den anderen beide Fotos des Nachbarn."""
        big = events_module.MIN_EVENT_PHOTOS
        opening = _time_gap() + EPSILON_TIME
        candidates = [
            _measured_candidate(1, T0, landmark_name="Zugspitze"),
            *(
                _measured_candidate(
                    10 + index, T0 + opening + index * EPSILON_TIME, landmark_name="Eibsee"
                )
                for index in range(big)
            ),
        ]

        [event] = _build(
            candidates,
            min_event_photos=None,
            landmark_points_by_name=_confirming("Zugspitze", "Eibsee"),
        )

        assert len(event.photo_ids) == big + 1
        assert event.landmark_name == "Eibsee"

    def test_an_event_without_any_name_carries_none(self) -> None:
        [event] = _build([_measured_candidate(1, T0)])

        assert event.landmark_name is None

    def test_a_measured_coordinate_of_a_nameless_photo_counts(self) -> None:
        candidates = [
            _placeless_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=48.85, lon=2.29),
        ]

        [event] = _build(candidates, [])

        assert (event.place_kind, event.place_lat, event.place_lon) == ("coordinate", 48.85, 2.29)


class TestTheNameNeedsTheSupportOfItsPhotos:
    """Spec 0514/ADR 0120: Ein Sehenswuerdigkeitsname benennt ein Event nur, wenn ihn mindestens
    `LANDMARK_MIN_SHARE` seiner Mitglieder bezeugt - genau der Anteil genuegt (inklusiv), kein
    zweiter Kandidat rueckt nach.

    Alle Mengen entstehen aus Zaehler und Nenner des Bruchs; kein Fall nennt die Zehntel als Zahl.
    Die Faelle, die einen Namen erwarten, tragen gemessene Kandidaten und eine bestaetigende
    Auskunft - ohne beide faellt jeder Name (fail-closed).
    """

    def test_a_name_with_more_carriers_beats_an_earlier_one(self) -> None:
        """Der Rueckhalt steht VOR der Reihenfolge: Der fruehere Eibsee hat ein Traegerfoto, der
        spaetere Zugspitze zwei - Zugspitze benennt das Event."""
        candidates = [
            _measured_candidate(1, T0, landmark_name="Eibsee"),
            _measured_candidate(2, T0 + EPSILON_TIME, landmark_name="Zugspitze"),
            _measured_candidate(3, T0 + 2 * EPSILON_TIME, landmark_name="Zugspitze"),
        ]

        [event] = _build(candidates, landmark_points_by_name=_confirming("Eibsee", "Zugspitze"))

        assert event.landmark_name == "Zugspitze"

    def test_the_share_boundary_is_inclusive(self) -> None:
        """Genau `numerator` Traeger unter `denominator` Mitgliedern: das genuegt."""
        share = _min_share()
        candidates = [
            _measured_candidate(
                index,
                T0 + index * EPSILON_TIME,
                landmark_name="Eiffelturm" if index < share.numerator else None,
            )
            for index in range(share.denominator)
        ]

        [event] = _build(candidates, landmark_points_by_name=_confirming("Eiffelturm"))

        assert event.landmark_name == "Eiffelturm"

    def test_one_photo_more_than_the_boundary_falls_short(self) -> None:
        """Ein Foto mehr im Nenner und derselbe eine Traeger: der Anteil reisst. Der verworfene
        Name hinterlaesst keine Spur - das Event faellt in die gewohnte Reihenfolge."""
        share = _min_share()
        candidates = [
            _placeless_candidate(
                index,
                T0 + index * EPSILON_TIME,
                landmark_name="Eiffelturm" if index < share.numerator else None,
            )
            for index in range(share.denominator + 1)
        ]

        [event] = _build(candidates)

        assert event.landmark_name is None
        assert (event.place_kind, event.place_lat, event.place_lon) == (None, None, None)

    def test_the_denominator_is_the_whole_membership_not_only_the_named_photos(self) -> None:
        """Ein Traeger unter DREI Fotos genuegt (1/3 ueber 1/10). Eine Zaehlung ueber nur die
        benannten Fotos ergaebe 1/1 und liesse die Schwelle wirkungslos."""
        candidates = [
            _measured_candidate(1, T0, landmark_name="Eiffelturm"),
            _measured_candidate(2, T0 + EPSILON_TIME),
            _measured_candidate(3, T0 + 2 * EPSILON_TIME),
        ]

        [event] = _build(candidates, landmark_points_by_name=_confirming("Eiffelturm"))

        assert event.landmark_name == "Eiffelturm"

    def test_no_other_name_moves_up_when_the_winner_falls_short(self) -> None:
        """Der Gewinner traegt das Maximum der Traegerzahlen - reisst ER den Anteil, ist jeder
        andere es erst recht. Hier steht der Zweitplatzierte bei einem einzigen Foto und rueckt
        ausdruecklich nicht nach."""
        many = _min_share().denominator * 3
        candidates = [
            _placeless_candidate(
                index,
                T0 + index * EPSILON_TIME,
                landmark_name={0: "Zugspitze", 1: "Zugspitze", 2: "Eibsee"}.get(index),
            )
            for index in range(many)
        ]

        [event] = _build(candidates)

        assert len(event.photo_ids) == many
        assert event.landmark_name is None

    def test_a_single_photo_event_carries_its_name(self) -> None:
        """1 von 1 erfuellt jeden Anteil - der Einzelfall braucht keinen eigenen Zweig."""
        [event] = _build(
            [_measured_candidate(1, T0, landmark_name="Eiffelturm")],
            landmark_points_by_name=_confirming("Eiffelturm"),
        )

        assert event.landmark_name == "Eiffelturm"

    def test_a_blank_name_neither_carries_nor_wins(self) -> None:
        """Ein nach der Sanitisierung leerer Name zaehlt nicht als Traeger - und kann deshalb auch
        nicht gewinnen, obwohl er der fruehere ist."""
        candidates = [
            _measured_candidate(1, T0, landmark_name="   "),
            _measured_candidate(2, T0 + EPSILON_TIME, landmark_name="Eiffelturm"),
        ]

        [event] = _build(candidates, landmark_points_by_name=_confirming("Eiffelturm"))

        assert event.landmark_name == "Eiffelturm"

    def test_a_run_of_blank_names_carries_none(self) -> None:
        candidates = [
            _placeless_candidate(1, T0, landmark_name=""),
            _placeless_candidate(2, T0 + EPSILON_TIME, landmark_name="  "),
        ]

        [event] = _build(candidates)

        assert event.landmark_name is None


class TestTheLandmarkNameNeedsAPlausiblePlace:
    """Spec 0529: Ein erkannter Sehenswuerdigkeitsname benennt ein Event nur, wenn mindestens einer
    seiner Gazetteer-Fundorte im Umkreis des Aufnahmeorts liegt.

    Die Prueffunktion ist ABSICHTLICH direkt aufgerufen: sie ist FAIL-CLOSED (ADR 0135 Punkt 3),
    und vier ihrer Zweige liefern falsch - ueber `_build` allein waeren "keine Auskunft", "keine
    gemessene Zelle", "keine Zeile" und "leere Punktmenge" nicht auseinanderzuhalten. Die Grenze
    wird am SYMBOL gerechnet; kein Fall nennt den Zahlwert."""

    NAME = "Zugspitze"

    def _cell(self) -> tuple[float, float]:
        return (BASE_LAT, BASE_LON)

    def _inside(self) -> tuple[float, float]:
        return (_latitude_at(_radius() / 2), BASE_LON)

    def _outside(self) -> tuple[float, float]:
        return (_latitude_at(_radius() * 2), BASE_LON)

    def test_without_any_lookup_the_name_falls(self) -> None:
        """Keine Auskunft (`None`) ist kein Freibrief: der Name faellt."""
        assert events_module.landmark_name_is_plausible(self.NAME, (self._cell(),), None) is False

    def test_without_a_measured_cell_the_name_falls_beside_an_empty_point_set(self) -> None:
        assert events_module.landmark_name_is_plausible(self.NAME, (), {self.NAME: ()}) is False

    def test_without_a_measured_cell_the_name_falls_beside_a_fitting_point(self) -> None:
        """Ohne Aufnahmeort laesst sich nichts bestaetigen - auch ein vorhandener Fund nicht."""
        assert (
            events_module.landmark_name_is_plausible(self.NAME, (), {self.NAME: (self._inside(),)})
            is False
        )

    def test_a_name_without_an_entry_falls(self) -> None:
        """Der Zustand "nie nachgeschlagen" faellt am Event wie "ohne Fund" - die Ablage bleibt
        dreiwertig, eine fehlende Zeile wird beim naechsten Lauf nachgeschlagen."""
        assert (
            events_module.landmark_name_is_plausible(
                self.NAME, (self._cell(),), {"Andere Sehenswuerdigkeit": (self._inside(),)}
            )
            is False
        )

    def test_a_looked_up_name_without_a_single_point_falls(self) -> None:
        """Zustand 2 (ADR 0123 Punkt 2): nachgeschlagen, kein Fund - der Name faellt."""
        assert (
            events_module.landmark_name_is_plausible(self.NAME, (self._cell(),), {self.NAME: ()})
            is False
        )

    def test_a_point_inside_the_radius_keeps_the_name(self) -> None:
        assert (
            events_module.landmark_name_is_plausible(
                self.NAME, (self._cell(),), {self.NAME: (self._inside(),)}
            )
            is True
        )

    def test_a_point_outside_the_radius_drops_the_name(self) -> None:
        assert (
            events_module.landmark_name_is_plausible(
                self.NAME, (self._cell(),), {self.NAME: (self._outside(),)}
            )
            is False
        )

    def test_the_radius_itself_does_not_count(self) -> None:
        """`<`, nicht `<=`: Die Grenze selbst gehoert nicht mehr zum Umkreis.

        Gerechnet wird am SYMBOL und in beide Richtungen exakt: der Radius ist genau der gemessene
        Abstand dieses Punktes, "knapp darunter" und "knapp darueber" sind die beiden
        Nachbarzahlen (`math.nextafter`) - so steht der Grenzfall ohne jede Zahl im Fall."""
        point = (BASE_LAT + 0.5, BASE_LON)
        at_the_radius = haversine_meters(BASE_LAT, BASE_LON, *point)
        args = (self.NAME, (self._cell(),), {self.NAME: (point,)})

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(events_module, "LANDMARK_PLAUSIBILITY_RADIUS_METERS", at_the_radius)
            assert events_module.landmark_name_is_plausible(*args) is False

            patch.setattr(
                events_module,
                "LANDMARK_PLAUSIBILITY_RADIUS_METERS",
                math.nextafter(at_the_radius, math.inf),
            )
            assert events_module.landmark_name_is_plausible(*args) is True

            patch.setattr(
                events_module,
                "LANDMARK_PLAUSIBILITY_RADIUS_METERS",
                math.nextafter(at_the_radius, 0.0),
            )
            assert events_module.landmark_name_is_plausible(*args) is False

    def test_one_fitting_pair_is_enough_across_several_points(self) -> None:
        """Verglichen wird jedes Paar (Zelle, Fundort): ein einziger Fund im Umkreis genuegt."""
        assert (
            events_module.landmark_name_is_plausible(
                self.NAME,
                (self._cell(),),
                {self.NAME: (self._outside(), self._inside())},
            )
            is True
        )

    def test_one_fitting_pair_is_enough_across_several_cells(self) -> None:
        cells = ((BASE_LAT + 2.0, BASE_LON), self._cell())

        assert (
            events_module.landmark_name_is_plausible(
                self.NAME, cells, {self.NAME: (self._inside(),)}
            )
            is True
        )

    # --- ueber `build_events`: die Pruefung wirkt am fertigen Event ----------------------------

    def test_a_name_without_a_place_in_the_radius_is_dropped(self) -> None:
        candidates = [
            _measured_candidate(1, T0, landmark_name=self.NAME),
            _measured_candidate(2, T0 + EPSILON_TIME, landmark_name=self.NAME),
        ]

        [event] = _build(candidates, landmark_points_by_name={self.NAME: (self._outside(),)})

        assert event.landmark_name is None

    def test_a_fitting_place_keeps_the_name(self) -> None:
        candidates = [
            _measured_candidate(1, T0, landmark_name=self.NAME),
            _measured_candidate(2, T0 + EPSILON_TIME, landmark_name=self.NAME),
        ]

        [event] = _build(candidates, landmark_points_by_name={self.NAME: (self._inside(),)})

        assert event.landmark_name == self.NAME

    def test_without_a_lookup_the_name_falls(self) -> None:
        candidates = [
            _measured_candidate(1, T0, landmark_name=self.NAME),
            _measured_candidate(2, T0 + EPSILON_TIME, landmark_name=self.NAME),
        ]

        [event] = _build(candidates, landmark_points_by_name=None)

        assert event.landmark_name is None

    def test_a_dropped_name_leaves_the_event_as_unnamed_as_a_never_named_one(self) -> None:
        """Keine Auskunft, keine Zeile und leere Punktmenge liefern DASSELBE Event wie Kandidaten,
        die nie einen Namen trugen; nur der bestaetigende Fund behaelt ihn. Kein anderer Name
        rueckt nach, und die Ueberschrift faellt auf den Ort bzw. die Zeit zurueck."""
        candidates = [
            _measured_candidate(1, T0, landmark_name=self.NAME),
            _measured_candidate(2, T0 + EPSILON_TIME, landmark_name=self.NAME),
        ]
        never_named = _build([replace(candidate, landmark_name=None) for candidate in candidates])
        never_looked_up = _build(candidates)
        without_a_find = _build(candidates, landmark_points_by_name={self.NAME: ()})
        missing_entry = _build(
            candidates, landmark_points_by_name={"Andere Sehenswuerdigkeit": (self._inside(),)}
        )
        with_a_find = _build(candidates, landmark_points_by_name={self.NAME: (self._inside(),)})

        assert never_looked_up == without_a_find == missing_entry == never_named
        assert never_named[0].place_kind == "coordinate"
        assert with_a_find[0].landmark_name == self.NAME

    def test_a_name_on_only_inherited_coordinates_falls(self) -> None:
        """Ein Event, das nur uebernommene Koordinaten traegt, hat keine gemessene Zelle - der
        Name faellt, auch neben einem passenden Fund."""
        candidates = [
            _inherited_candidate(1, T0, landmark_name=self.NAME),
            _inherited_candidate(2, T0 + EPSILON_TIME, landmark_name=self.NAME),
        ]

        [event] = _build(candidates, landmark_points_by_name={self.NAME: (self._inside(),)})

        assert event.landmark_name is None
        assert event.place_kind is None

    def test_the_second_best_name_does_not_move_up(self) -> None:
        """KEIN NACHRUECKEN: faellt der Gewinner an der Ortspruefung, traegt das Event gar keinen
        Namen - auch wenn der zweitbeste Kandidat einen Fund im Umkreis haette."""
        candidates = [
            _measured_candidate(1, T0, landmark_name=self.NAME),
            _measured_candidate(2, T0 + EPSILON_TIME, landmark_name=self.NAME),
            _measured_candidate(3, T0 + 2 * EPSILON_TIME, landmark_name="Eibsee"),
        ]

        [event] = _build(
            candidates,
            landmark_points_by_name={self.NAME: (self._outside(),), "Eibsee": (self._inside(),)},
        )

        assert event.landmark_name is None

    def test_the_same_name_is_judged_against_each_events_own_cell(self) -> None:
        """Ein Name in zwei Events wird gegen die Zelle SEINES Events geprueft: derselbe Name am
        passenden Ort bleibt, am fernen faellt er."""
        near = _latitude_at(_radius() / 2)
        far = _latitude_at(_radius() * 2)
        candidates = [
            _measured_candidate(1, T0, lat=near, landmark_name=self.NAME),
            _measured_candidate(
                2, T0 + _time_gap() + EPSILON_TIME, lat=far, landmark_name=self.NAME
            ),
        ]

        events = _build(candidates, landmark_points_by_name={self.NAME: (self._inside(),)})

        assert [event.landmark_name for event in events] == [self.NAME, None]


# --- Die Namensvergabe ueber die Events eines Laufs ---------------------------------------------
BERLIN = (52.52, 13.40)


BERLIN_OST = (52.53, 13.45)


SPLIT = (43.51, 16.44)


OHNE_NAMEN = (0.0, 0.0)


def _info(locality: str | None, neighbourhood: str | None = None) -> PlaceInfo:
    """Eine abgelegte Auskunft mit AUFLOESENDER Ebene - genau die Lage, in der ein Name entsteht.

    Die Ebene folgt dem Viertel: eine Auskunft mit Viertel hat die Viertel-Ebene getroffen."""
    return PlaceInfo(
        neighbourhood=neighbourhood,
        locality=locality,
        matched_level="neighbourhood" if neighbourhood is not None else "locality",
    )


def _place_event(
    position: int, *cells: tuple[float, float], landmark_name: str | None = None
) -> BuiltEvent:
    """Ein fertiges Event, auf das reduziert, was die Vergabe liest."""
    return BuiltEvent(
        position=position,
        photo_ids=(position,),
        started_at=T0,
        ended_at=_at(minutes=10),
        landmark_name=landmark_name,
        place_kind="landmark" if landmark_name is not None else "coordinate",
        place_cells=tuple(cells),
    )


class TestBuiltEventCarriesItsCells:
    """`place_cells` sind die verschiedenen gerundeten GEMESSENEN Zellen des Events - dieselbe
    Menge, aus der `_place_of` seine Stufenentscheidung bildet."""

    def test_the_cells_are_sorted_and_free_of_duplicates(self) -> None:
        candidates = [
            _measured_candidate(1, T0, lat=48.95, lon=2.29),
            _measured_candidate(2, _at(minutes=1), lat=48.85, lon=2.29),
            _measured_candidate(3, _at(minutes=2), lat=48.8501, lon=2.2901),
        ]

        [event] = _build(candidates, [])

        assert event.place_cells == ((48.85, 2.29), (48.95, 2.29))

    def test_an_event_without_a_measured_coordinate_has_no_cells(self) -> None:
        [event] = _build([_inherited_candidate(1, T0)])

        assert event.place_cells == ()

    def test_a_landmark_event_carries_its_cells_too(self) -> None:
        """`_place_of` kehrt bei gesetztem Namen zurueck, BEVOR es die Zellen bildet - die Zellen
        entstehen deshalb unabhaengig davon. Ohne sie waere der Landmark-Fall der Vergabe unten
        vakuum-gruen: er bestuende auch dann, wenn die Ausnahme ersatzlos entfiele."""
        candidates = [
            _measured_candidate(1, T0, lat=52.52, lon=13.40, landmark_name="Brandenburger Tor"),
        ]

        [event] = _build(
            candidates, landmark_points_by_name=_confirming("Brandenburger Tor", at=(52.52, 13.40))
        )

        assert event.place_kind == "landmark"
        assert event.place_cells == ((52.52, 13.4),)

    def test_the_existing_place_fields_stay_exactly_as_they_were(self) -> None:
        """Regressionsfall: `place_kind`/`place_lat`/`place_lon` bleiben von den Zellen
        vollstaendig unberuehrt."""
        candidates = [
            _measured_candidate(1, T0, lat=48.85, lon=2.29),
            _measured_candidate(2, _at(minutes=1), lat=48.95, lon=2.29),
        ]

        [event] = _build(candidates, [])

        assert (event.place_kind, event.place_lat, event.place_lon) == ("multiple", None, None)


class TestAssignPlaceNames:
    """Die Vergabe ueber die Events EINES Laufs - rein, deterministisch, positionstreu.

    Die Viertel-Ergaenzung ist eine Aussage ueber den LAUF und lebt deshalb hier und nicht in
    `places.py` (ADR 0102 Punkt 4)."""

    def test_one_name_over_several_cells_becomes_the_name(self) -> None:
        """Auch dann, wenn eine der Zellen gar keinen Namen liefert - Zellen ohne Namen zaehlen
        nicht mit."""
        events = [_place_event(1, BERLIN, BERLIN_OST, OHNE_NAMEN)]
        infos = {BERLIN: _info("Berlin"), BERLIN_OST: _info("Berlin")}

        assert assign_place_names(events, infos) == ["Berlin"]

    def test_two_different_names_in_one_event_yield_none(self) -> None:
        """Fuer eine Menge von Orten gibt es keinen einen Namen."""
        events = [_place_event(1, BERLIN, SPLIT)]
        infos = {BERLIN: _info("Berlin"), SPLIT: _info("Split")}

        assert assign_place_names(events, infos) == [None]

    def test_an_event_without_any_usable_cell_keeps_its_position(self) -> None:
        events = [_place_event(1), _place_event(2, OHNE_NAMEN)]

        assert assign_place_names(events, {}) == [None, None]

    def test_a_coarse_answer_is_no_name_at_all(self) -> None:
        """Ein Treffer auf Regionsebene nennt oft trotzdem eine Stadt - die gilt hier nicht."""
        events = [_place_event(1, BERLIN)]
        infos = {BERLIN: PlaceInfo(neighbourhood=None, locality="Berlin", matched_level="region")}

        assert assign_place_names(events, infos) == [None]

    def test_a_single_event_in_berlin_is_just_berlin(self) -> None:
        events = [_place_event(1, BERLIN)]
        infos = {BERLIN: _info("Berlin", "Kreuzberg")}

        assert assign_place_names(events, infos) == ["Berlin"]

    def test_only_the_events_sharing_a_name_get_their_district(self) -> None:
        events = [
            _place_event(1, BERLIN),
            _place_event(2, BERLIN_OST),
            _place_event(3, SPLIT),
        ]
        infos = {
            BERLIN: _info("Berlin", "Kreuzberg"),
            BERLIN_OST: _info("Berlin", "Mitte"),
            SPLIT: _info("Split", "Bacvice"),
        }

        assert assign_place_names(events, infos) == ["Berlin, Kreuzberg", "Berlin, Mitte", "Split"]

    def test_the_district_is_added_per_event_not_per_name(self) -> None:
        """Traegt von zwei gleichnamigen Events nur eines ein Viertel, bekommt nur dieses den
        Zusatz - das andere bleibt beim Ortsnamen und ist ueber seine Zeitspanne unterscheidbar."""
        events = [_place_event(1, BERLIN), _place_event(2, BERLIN_OST)]
        infos = {BERLIN: _info("Berlin", "Kreuzberg"), BERLIN_OST: _info("Berlin")}

        assert assign_place_names(events, infos) == ["Berlin, Kreuzberg", "Berlin"]

    def test_two_namesakes_without_any_district_both_keep_the_locality(self) -> None:
        events = [_place_event(1, BERLIN), _place_event(2, BERLIN_OST)]
        infos = {BERLIN: _info("Berlin"), BERLIN_OST: _info("Berlin")}

        assert assign_place_names(events, infos) == ["Berlin", "Berlin"]

    def test_two_different_districts_in_one_event_yield_no_district(self) -> None:
        events = [_place_event(1, BERLIN, BERLIN_OST), _place_event(2, (52.54, 13.41))]
        infos = {
            BERLIN: _info("Berlin", "Kreuzberg"),
            BERLIN_OST: _info("Berlin", "Mitte"),
            (52.54, 13.41): _info("Berlin", "Wedding"),
        }

        assert assign_place_names(events, infos) == ["Berlin", "Berlin, Wedding"]

    def test_a_composed_name_beyond_the_limit_leaves_the_locality_alone(self) -> None:
        """Gekuerzt wird NIE: zwei verschiedene, auf dieselbe Laenge gekappte Namen waeren ein
        Name, und die Viertel-Regel griffe dann fuer Events an verschiedenen Orten.

        Je Event einzeln - das zweite, gleichnamige Event mit kurzem Viertel behaelt seinen."""
        langes_viertel = "V" * MAX_PLACE_NAME_LENGTH
        events = [_place_event(1, BERLIN), _place_event(2, BERLIN_OST)]
        infos = {
            BERLIN: _info("Berlin", langes_viertel),
            BERLIN_OST: _info("Berlin", "Mitte"),
        }

        assert assign_place_names(events, infos) == ["Berlin", "Berlin, Mitte"]

    def test_a_named_event_takes_the_same_place_name_as_without_its_name(self) -> None:
        """Die EINE Ortsregel (ADR 0120 Punkt 2): `assign_place_names` liest `landmark_name`
        ueberhaupt nicht mehr. Geprueft als DIFFERENTIELLE PROBE - dieselbe Eventliste einmal MIT
        und einmal OHNE den Namen, positionsweise dasselbe Ergebnis. Zwei getrennte Erwartungen
        bestuenden auch dann, wenn beide Lagen auseinanderliefen."""
        events = [
            _place_event(1, BERLIN, landmark_name="Brandenburger Tor"),
            _place_event(2, BERLIN_OST),
        ]
        infos = {BERLIN: _info("Berlin", "Mitte"), BERLIN_OST: _info("Berlin", "Kreuzberg")}

        mit_namen = assign_place_names(events, infos)
        ohne_namen = assign_place_names(
            [replace(event, landmark_name=None) for event in events], infos
        )

        assert mit_namen == ohne_namen
        # Gegenprobe gegen eine leere Zusage: hier entsteht tatsaechlich je ein zusammengesetzter
        # Name, und zwar weil das benannte Event jetzt mitzaehlt.
        assert mit_namen == ["Berlin, Mitte", "Berlin, Kreuzberg"]

    def test_a_named_event_alone_in_one_locality_keeps_the_plain_locality(self) -> None:
        """Ein benanntes Event verliert seinen Ortsnamen nicht und bekommt auch keine
        Viertel-Ergaenzung, wo kein zweiter Namenstraeger liegt."""
        events = [_place_event(1, BERLIN, landmark_name="Brandenburger Tor")]
        infos = {BERLIN: _info("Berlin", "Mitte")}

        assert assign_place_names(events, infos) == ["Berlin"]

    def test_the_result_is_aligned_with_the_input_positionwise(self) -> None:
        """Eine um eins verschobene Zuordnung ist der zweite stille Fehler dieser Form."""
        events = [_place_event(1), _place_event(2, SPLIT), _place_event(3)]
        infos = {SPLIT: _info("Split")}

        assert assign_place_names(events, infos) == [None, "Split", None]

    def test_every_permutation_of_the_input_yields_the_same_name_per_event(self) -> None:
        events = [
            _place_event(1, BERLIN),
            _place_event(2, BERLIN_OST),
            _place_event(3, SPLIT),
        ]
        infos = {
            BERLIN: _info("Berlin", "Kreuzberg"),
            BERLIN_OST: _info("Berlin", "Mitte"),
            SPLIT: _info("Split"),
        }
        expected = {1: "Berlin, Kreuzberg", 2: "Berlin, Mitte", 3: "Split"}

        for permutation in permutations(events):
            ordered = list(permutation)
            names = assign_place_names(ordered, infos)
            assert {
                event.position: name for event, name in zip(ordered, names, strict=True)
            } == expected
