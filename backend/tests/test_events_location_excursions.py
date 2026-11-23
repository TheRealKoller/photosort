"""Ereignis-Gruppierung: Ortsausfluege, Rueckwaertskompatibilitaet ohne Koordinaten.
(Aufgeteilt aus test_events.py, Spec 0651.)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

import pytest

from photosort import events as events_module
from photosort.events import (
    EventCandidate,
    default_signals,
    explain_events,
    location_excursions,
)
from photosort.places import place_cell
from tests.support.event_grouping import (
    _NO_MERGING,
    BASE_LAT,
    BASE_LON,
    EPSILON_METERS,
    EPSILON_TIME,
    T0,
    _at,
    _build,
    _inherited_candidate,
    _latitude_at,
    _max_span,
    _measured_candidate,
    _north,
    _placeless_candidate,
    _radius,
    _step_max,
    _time_gap,
    _UnderShiftedEventConstants,
)


def _far_north() -> float:
    """Ein Breitengrad knapp JENSEITS der Schritt-Schwelle nach Norden - am Symbol gerechnet."""
    return _north(_step_max() + EPSILON_METERS)


def _far_south() -> float:
    """Ein Breitengrad knapp jenseits der Schritt-Schwelle nach SUEDEN - ein zweiter ferner Ort."""
    return _north(-(_step_max() + EPSILON_METERS))


def _excursion_confirming() -> int:
    """Die geltende Bestaetigungszahl eines Ortswechsels - als Modulattribut gelesen."""
    return events_module.LOCATION_CHANGE_CONFIRMING_PHOTOS


class TestLocationExcursions(_UnderShiftedEventConstants):
    """Die REINE Vorstufe `location_excursions` (ADR 0135 Punkt 1), direkt gemessen.

    Ein Ausreisser ist eine Folge von weniger als `LOCATION_CHANGE_CONFIRMING_PHOTOS` GEMESSENEN
    Fotos jenseits von `EVENT_STEP_MAX_METERS` vom Bezug, nach der das naechste gemessene Foto
    wieder innerhalb der Schwelle am Bezug liegt. Beide Schwellen werden am Symbol gerechnet."""

    def test_a_single_far_photo_between_two_at_the_reference_is_an_excursion(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_far_north()),
            _measured_candidate(3, _at(minutes=2)),
        ]

        assert location_excursions(candidates) == frozenset({2})

    def test_the_first_photo_has_no_reference_and_is_never_an_excursion(self) -> None:
        candidates = [
            _measured_candidate(1, T0, lat=_far_north()),
            _measured_candidate(2, _at(minutes=1)),
            _measured_candidate(3, _at(minutes=2)),
        ]

        assert location_excursions(candidates) == frozenset()

    def test_a_far_last_photo_has_no_return_and_is_no_excursion(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1)),
            _measured_candidate(3, _at(minutes=2), lat=_far_north()),
        ]

        assert location_excursions(candidates) == frozenset()

    def test_two_far_photos_in_a_row_confirm_a_change(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_far_north()),
            _measured_candidate(3, _at(minutes=2), lat=_far_north()),
            _measured_candidate(4, _at(minutes=3)),
        ]

        assert location_excursions(candidates) == frozenset()

    def test_with_a_larger_confirmation_both_far_photos_are_neutralised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die Zahl wird als MODULATTRIBUT gelesen - eine gebundene Vorgabe liefe hier ins Leere."""
        monkeypatch.setattr(events_module, "LOCATION_CHANGE_CONFIRMING_PHOTOS", 3)
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_far_north()),
            _measured_candidate(3, _at(minutes=2), lat=_far_north()),
            _measured_candidate(4, _at(minutes=3)),
        ]

        assert location_excursions(candidates) == frozenset({2, 3})

    def test_two_different_far_places_are_a_change_not_an_excursion(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_far_north()),
            _measured_candidate(3, _at(minutes=2), lat=_far_south()),
            _measured_candidate(4, _at(minutes=3)),
        ]

        assert location_excursions(candidates) == frozenset()

    def test_placeless_photos_neither_interrupt_nor_count(self) -> None:
        """A-∅-X-∅-A: Fotos ganz ohne Ort stehen dazwischen und aendern nichts."""
        candidates = [
            _measured_candidate(1, T0),
            _placeless_candidate(2, _at(minutes=1)),
            _measured_candidate(3, _at(minutes=2), lat=_far_north()),
            _placeless_candidate(4, _at(minutes=3)),
            _measured_candidate(5, _at(minutes=4)),
        ]

        assert location_excursions(candidates) == frozenset({3})

    def test_an_inherited_photo_beside_the_excursion_goes_with_it_and_confirms_nothing(
        self,
    ) -> None:
        """Das Foto ohne Messung hat seinen Ort vom Ausreisser uebernommen: es zaehlt nicht als
        Bestaetigung und verliert seinen Ort mit ihm. Eines mit dem Bezugsort bleibt."""
        candidates = [
            _measured_candidate(1, T0),
            _inherited_candidate(2, _at(minutes=1)),
            _measured_candidate(3, _at(minutes=2), lat=_far_north()),
            _inherited_candidate(4, _at(minutes=3), lat=_far_north()),
            _measured_candidate(5, _at(minutes=4)),
        ]

        assert location_excursions(candidates) == frozenset({3, 4})

    def test_two_separate_excursions_keep_the_same_reference(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_far_north()),
            _measured_candidate(3, _at(minutes=2)),
            _measured_candidate(4, _at(minutes=3), lat=_far_south()),
            _measured_candidate(5, _at(minutes=4)),
        ]

        assert location_excursions(candidates) == frozenset({2, 4})

    def test_a_return_just_inside_the_step_counts(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_north(2 * _step_max())),
            _measured_candidate(3, _at(minutes=2), lat=_north(_step_max() - EPSILON_METERS)),
        ]

        assert location_excursions(candidates) == frozenset({2})

    def test_a_return_just_outside_the_step_is_none(self) -> None:
        """Das vermeintliche Rueckkehrfoto liegt selbst jenseits der Schwelle - es bestaetigt."""
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_north(3 * _step_max())),
            _measured_candidate(3, _at(minutes=2), lat=_north(_step_max() + EPSILON_METERS)),
        ]

        assert location_excursions(candidates) == frozenset()

    def test_a_deviation_just_inside_the_step_is_no_excursion(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_north(_step_max() - EPSILON_METERS)),
            _measured_candidate(3, _at(minutes=2)),
        ]

        assert location_excursions(candidates) == frozenset()

    def test_the_oldest_far_photo_becomes_the_new_reference(self) -> None:
        """Zwei Fotos fern vom alten Bezug, die nicht beieinanderliegen: Das AELTERE wird der neue
        Bezug, und das juengere ist gegen ihn ein Ausreisser, sobald die Folge zu ihm zurueckkehrt."""
        a = _north(3 * _step_max())
        x = _north(4 * _step_max() + EPSILON_METERS)
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=a),
            _measured_candidate(3, _at(minutes=2), lat=x),
            _measured_candidate(4, _at(minutes=3), lat=a),
        ]

        assert location_excursions(candidates) == frozenset({3})

    def test_already_neutralised_candidates_yield_nothing(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_far_north()),
            _measured_candidate(3, _at(minutes=2)),
        ]
        neutralised = [
            replace(candidate, location=None, gps_lat=None, gps_lon=None)
            if candidate.photo_id in location_excursions(candidates)
            else candidate
            for candidate in candidates
        ]

        assert location_excursions(neutralised) == frozenset()

    def test_the_confirmation_is_at_least_two(self) -> None:
        """Die EINE Aussage ueber den Zahlwert, und sie ist eine Ungleichung."""
        assert _excursion_confirming() >= 2


class TestAnExcursionStaysInItsEvent(_UnderShiftedEventConstants):
    """Die Einbindung in `explain_events` (ADR 0135 Punkt 2): Ein Ausreisser bleibt Mitglied, aber
    ohne Ort - er verschiebt weder Schritt noch Ausdehnung und speist weder Zelle noch Namen."""

    def _a_x_a(self, *, x_name: str | None = None) -> list[EventCandidate]:
        return [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_far_north(), landmark_name=x_name),
            _measured_candidate(3, _at(minutes=2)),
        ]

    def test_a_x_a_is_one_event_with_the_one_cell_of_a(self) -> None:
        for min_event_photos in (_NO_MERGING, None):
            [event] = _build(self._a_x_a(), min_event_photos=min_event_photos)

            assert event.photo_ids == (1, 2, 3)
            assert event.place_cells == (place_cell(BASE_LAT, BASE_LON),)

    def test_an_excursion_carries_no_boundary_cause(self) -> None:
        formation = explain_events(self._a_x_a(), min_event_photos=_NO_MERGING)

        assert formation.causes == (frozenset(),)

    def test_a_change_without_return_still_splits(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_far_north()),
        ]

        assert [event.photo_ids for event in _build(candidates)] == [(1,), (2,)]

    def test_a_confirmed_change_splits_even_with_a_later_return(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_far_north()),
            _measured_candidate(3, _at(minutes=2), lat=_far_north()),
            _measured_candidate(4, _at(minutes=3)),
        ]

        assert [event.photo_ids for event in _build(candidates)] == [(1,), (2, 3), (4,)]

    def test_a_time_gap_right_after_the_excursion_still_splits(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_far_north()),
            _measured_candidate(3, _at(minutes=1) + _time_gap() + EPSILON_TIME),
        ]

        first, second = _build(candidates)

        assert (first.photo_ids, second.photo_ids) == ((1, 2), (3,))
        assert first.place_cells == (place_cell(BASE_LAT, BASE_LON),)

    def test_an_excursion_with_a_fitting_find_does_not_confirm_the_name(self) -> None:
        """Der Fundort liegt am Ausreisser, nicht am Event: der Name entfaellt."""
        name = "Tower of London"
        far_away = _latitude_at(2 * _radius() + _step_max())
        candidates = [
            _measured_candidate(1, T0, landmark_name=name),
            _measured_candidate(2, _at(minutes=1), lat=far_away, landmark_name=name),
            _measured_candidate(3, _at(minutes=2), landmark_name=name),
        ]

        [event] = _build(candidates, landmark_points_by_name={name: ((far_away, BASE_LON),)})

        assert event.landmark_name is None

    def test_a_new_place_followed_by_a_neighbouring_single_photo_keeps_one_event(self) -> None:
        """P-P, dann A, X neben A und A ab da: Zwei Fotos fern von P sind noch kein Ort, an dem
        zwei Fotos liegen - A wird der neue Bezug, X ist ein Ausreisser, und es bleiben zwei
        Events statt vier."""
        a = _north(3 * _step_max())
        x = _north(4 * _step_max() + EPSILON_METERS)
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1)),
            _measured_candidate(3, _at(minutes=2), lat=a),
            _measured_candidate(4, _at(minutes=3), lat=x),
            *(_measured_candidate(5 + i, _at(minutes=4 + i), lat=a) for i in range(3)),
        ]

        assert [event.photo_ids for event in _build(candidates)] == [(1, 2), (3, 4, 5, 6, 7)]

    def test_nothing_is_written_back_to_the_candidates(self) -> None:
        candidates = self._a_x_a()
        before = list(candidates)

        _build(candidates)

        assert candidates == before
        assert candidates[1].gps_lat == _far_north()


def _reference_time_and_span_events(candidates: Sequence[EventCandidate]) -> list[tuple[int, ...]]:
    """Im Test NACHGEBILDETE Referenz aus Zeitluecke plus Dauergrenze.

    Bewusst nicht `assign_clusters`: das kennt die Dauergrenze nicht und waere als Referenz
    schlicht falsch. Die Dauer wird gegen das EROEFFNENDE Foto gemessen, nicht gegen den
    Vorgaenger - eine gegen den Vorgaenger gemessene Referenz waere eine zweite Zeitluecke."""
    groups: list[list[int]] = []
    previous: datetime | None = None
    started: datetime | None = None
    for candidate in sorted(candidates, key=lambda c: (c.taken_at, c.photo_id)):
        starts = (
            previous is None
            or started is None
            or candidate.taken_at - previous > _time_gap()
            or candidate.taken_at - started > _max_span()
        )
        if starts:
            groups.append([])
            started = candidate.taken_at
        groups[-1].append(candidate.photo_id)
        previous = candidate.taken_at
    return [tuple(group) for group in groups]


class TestBackwardCompatibilityWithoutAnyCoordinate(_UnderShiftedEventConstants):
    """Traegt kein einziges Foto eine Ortsangabe, ist die Gliederung die reine Zeitluecken-
    Gliederung, zusaetzlich getrennt an jeder Dauergrenze."""

    def _a_run_that_reaches_both_boundaries(self) -> list[EventCandidate]:
        """Eine dichte Folge, die BEIDE zeitlichen Grenzen auf einmal ausloest: Ihre Schritte
        bleiben unter der Zeitluecke, ihre Gesamtdauer reisst die Dauergrenze, und hinter einer
        echten Luecke folgt ein Rest. Eine Folge, die nur die Zeitluecke erreicht, liesse die neue
        Grenze ungeprueft."""
        step = _time_gap() - EPSILON_TIME
        count = int(_max_span() / step) + 2
        times = [T0 + index * step for index in range(count)]
        after = times[-1] + _time_gap() + EPSILON_TIME
        return [
            _placeless_candidate(index, taken_at)
            for index, taken_at in enumerate([*times, after, after + EPSILON_TIME])
        ]

    def test_matches_the_reference_implementation(self) -> None:
        candidates = self._a_run_that_reaches_both_boundaries()

        events = _build(candidates, default_signals())

        assert [event.photo_ids for event in events] == _reference_time_and_span_events(candidates)
        assert len(events) >= 3, "die Lage muss beide zeitlichen Grenzen tatsaechlich erreichen"

    def test_a_night_without_a_time_gap_no_longer_separates(self) -> None:
        """Die abgeloeste Zusage, in ihr Gegenteil verkehrt: Die Tagesgrenze trennt nicht mehr."""
        candidates = [
            _placeless_candidate(1, datetime(2026, 7, 20, 23, 59, 0)),
            _placeless_candidate(2, datetime(2026, 7, 21, 0, 1, 0)),
        ]

        assert len(_build(candidates, default_signals())) == 1
