"""Ereignis-Gruppierung: Ortsableitung, Form, die Trennsignale (Zeitluecke, Dauer, Schritt,
Ausdehnung), Standardsignale, korrigierte Zeit und uebernommene Orte.
(Aufgeteilt aus test_events.py, Spec 0651.)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from photosort.events import (
    BOUNDARY_LANDMARK,
    EffectiveLocation,
    EventCandidate,
    EventSpanSignal,
    ExtentSignal,
    LocationEntry,
    StepDistanceSignal,
    TimeGapSignal,
    default_signals,
    infer_locations,
    inherited_locations,
)
from photosort.scoring import haversine_meters
from tests.support.event_grouping import (
    BASE_LAT,
    BASE_LON,
    EPSILON_METERS,
    EPSILON_TIME,
    T0,
    _AlwaysSignal,
    _at,
    _build,
    _explain,
    _extent_max,
    _max_span,
    _measured_candidate,
    _north,
    _placeless_candidate,
    _SpySignal,
    _step_max,
    _time_gap,
    _UnderShiftedEventConstants,
)


class TestInferLocations:
    """Der projektweit uebernommene Ort - Bezugsmenge ist JEDES Foto des Projekts mit gemessener
    Koordinate, auch ein aussortiertes."""

    def test_own_coordinate_wins_and_is_not_marked_inferred(self) -> None:
        entries = [LocationEntry(photo_id=1, taken_at=T0, gps_lat=48.85, gps_lon=2.29)]

        assert infer_locations(entries) == {
            1: EffectiveLocation(lat=48.85, lon=2.29, inferred=False)
        }

    def test_photo_without_coordinate_inherits_the_temporally_nearest_anchor(self) -> None:
        entries = [
            LocationEntry(photo_id=1, taken_at=_at(hours=-3), gps_lat=10.0, gps_lon=10.0),
            LocationEntry(photo_id=2, taken_at=T0),
            LocationEntry(photo_id=3, taken_at=_at(minutes=10), gps_lat=20.0, gps_lon=20.0),
        ]

        assert infer_locations(entries)[2] == EffectiveLocation(lat=20.0, lon=20.0, inferred=True)

    def test_tie_break_on_equal_distance_prefers_the_earlier_timestamp(self) -> None:
        entries = [
            LocationEntry(photo_id=1, taken_at=_at(minutes=-10), gps_lat=10.0, gps_lon=10.0),
            LocationEntry(photo_id=2, taken_at=T0),
            LocationEntry(photo_id=3, taken_at=_at(minutes=10), gps_lat=20.0, gps_lon=20.0),
        ]

        assert infer_locations(entries)[2] == EffectiveLocation(lat=10.0, lon=10.0, inferred=True)

    def test_tie_break_on_identical_taken_at_prefers_the_smaller_photo_id(self) -> None:
        entries = [
            LocationEntry(photo_id=9, taken_at=T0, gps_lat=20.0, gps_lon=20.0),
            LocationEntry(photo_id=4, taken_at=T0, gps_lat=10.0, gps_lon=10.0),
            LocationEntry(photo_id=2, taken_at=T0),
        ]

        assert infer_locations(entries)[2] == EffectiveLocation(lat=10.0, lon=10.0, inferred=True)

    def test_an_anchor_may_be_a_rejected_photo(self) -> None:
        """Die Bezugsmenge kennt den Ausschuss-Zustand gar nicht: `entries` traegt ALLE Fotos des
        Projekts, der Aufrufer filtert nicht vor."""
        rejected_anchor = LocationEntry(photo_id=1, taken_at=T0, gps_lat=48.85, gps_lon=2.29)
        candidate = LocationEntry(photo_id=2, taken_at=_at(minutes=1))

        assert infer_locations([rejected_anchor, candidate])[2] == EffectiveLocation(
            lat=48.85, lon=2.29, inferred=True
        )

    def test_an_anchor_beyond_a_later_event_boundary_still_counts(self) -> None:
        """Die Herleitung steht VOR der Event-Bildung fest und kennt keine Grenzen - der naechste
        Anker darf jenseits einer spaeteren Trennung liegen."""
        entries = [
            LocationEntry(photo_id=1, taken_at=T0),
            LocationEntry(photo_id=2, taken_at=_at(days=2), gps_lat=48.85, gps_lon=2.29),
        ]

        assert infer_locations(entries)[1] == EffectiveLocation(lat=48.85, lon=2.29, inferred=True)

    def test_without_any_anchor_nobody_inherits(self) -> None:
        entries = [
            LocationEntry(photo_id=1, taken_at=T0),
            LocationEntry(photo_id=2, taken_at=_at(minutes=5)),
        ]

        assert infer_locations(entries) == {}

    def test_a_half_coordinate_is_no_coordinate(self) -> None:
        """Paar-Invariante von `extract_gps`: ein einzeln gesetzter Wert ergaebe eine Position auf
        dem Nullmeridian bzw. dem Aequator."""
        entries = [LocationEntry(photo_id=1, taken_at=T0, gps_lat=48.85, gps_lon=None)]

        assert infer_locations(entries) == {}

    def test_every_inherited_entry_is_marked_inferred(self) -> None:
        entries = [
            LocationEntry(photo_id=1, taken_at=T0, gps_lat=48.85, gps_lon=2.29),
            LocationEntry(photo_id=2, taken_at=_at(minutes=1)),
            LocationEntry(photo_id=3, taken_at=_at(minutes=2)),
        ]

        result = infer_locations(entries)

        assert [result[photo_id].inferred for photo_id in (1, 2, 3)] == [False, True, True]

    def test_empty_input(self) -> None:
        assert infer_locations([]) == {}


class TestBuildEventsShape:
    """Nummer, Fotomenge und Zeitspanne einer gebildeten Folge."""

    def test_no_candidates_no_events(self) -> None:
        assert _build([]) == []

    def test_a_single_event_spans_its_first_and_last_photo(self) -> None:
        candidates = [
            _placeless_candidate(2, _at(minutes=10)),
            _placeless_candidate(1, T0),
            _placeless_candidate(3, _at(minutes=20)),
        ]

        [event] = _build(candidates)

        assert event.position == 1
        assert event.photo_ids == (1, 2, 3)
        assert event.started_at == T0
        assert event.ended_at == _at(minutes=20)

    def test_positions_are_one_based_and_chronological(self) -> None:
        candidates = [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, _at(hours=5)),
            _placeless_candidate(3, _at(hours=10)),
        ]

        events = _build(candidates)

        assert [(event.position, event.photo_ids) for event in events] == [
            (1, (1,)),
            (2, (2,)),
            (3, (3,)),
        ]

    def test_identical_taken_at_is_ordered_by_photo_id(self) -> None:
        candidates = [_placeless_candidate(7, T0), _placeless_candidate(3, T0)]

        [event] = _build(candidates)

        assert event.photo_ids == (3, 7)


class TestTimeGapSignal(_UnderShiftedEventConstants):
    """Unveraendertes Verhalten, geprueft am SYMBOL `EVENT_TIME_GAP`."""

    def _two_photos(self, distance: timedelta) -> list[EventCandidate]:
        return [_placeless_candidate(1, T0), _placeless_candidate(2, T0 + distance)]

    def test_below_the_symbol_stays_one_event(self) -> None:
        events = _build(self._two_photos(_time_gap() - EPSILON_TIME), [TimeGapSignal()])

        assert len(events) == 1

    def test_above_the_symbol_splits(self) -> None:
        events = _build(self._two_photos(_time_gap() + EPSILON_TIME), [TimeGapSignal()])

        assert len(events) == 2

    def test_exactly_at_the_symbol_does_not_split(self) -> None:
        """`>` und nicht `>=` - exakt, weil `timedelta`-Arithmetik exakt ist."""
        events = _build(self._two_photos(_time_gap()), [TimeGapSignal()])

        assert len(events) == 1


class TestEventSpanSignal(_UnderShiftedEventConstants):
    """Die DAUER des laufenden Events, geprueft am Symbol `EVENT_MAX_SPAN` - sie tritt an die
    Stelle des Kalendertags."""

    def _dense_run(self, span: timedelta) -> list[EventCandidate]:
        """Zwei Fotos im Abstand `span`, dazwischen so viele, dass KEINE Zeitluecke mitredet."""
        step = _time_gap() - EPSILON_TIME
        count = int(span / step) + 1
        times = [T0 + index * (span / count) for index in range(count)] + [T0 + span]
        return [_placeless_candidate(index, taken_at) for index, taken_at in enumerate(times)]

    def test_below_the_symbol_stays_one_event(self) -> None:
        candidates = self._dense_run(_max_span() - EPSILON_TIME)

        assert len(_build(candidates, [EventSpanSignal()])) == 1

    def test_above_the_symbol_splits(self) -> None:
        candidates = self._dense_run(_max_span() + EPSILON_TIME)

        assert len(_build(candidates, [EventSpanSignal()])) == 2

    def test_exactly_at_the_symbol_does_not_split(self) -> None:
        """`>` und nicht `>=` - exakt, weil `timedelta`-Arithmetik exakt ist."""
        assert len(_build(self._dense_run(_max_span()), [EventSpanSignal()])) == 1

    def test_the_span_includes_the_photo_under_consideration(self) -> None:
        """Das ueberschreitende Foto BEGINNT das neue Event, es beendet nicht das alte - sonst
        begaenne das neue Event ein Foto zu spaet."""
        candidates = self._dense_run(_max_span() + EPSILON_TIME)

        events = _build(candidates, [EventSpanSignal()])

        assert events[1].photo_ids == (candidates[-1].photo_id,)

    def test_the_reference_is_the_opening_photo_and_not_the_predecessor(self) -> None:
        """Gemessen wird gegen das EROEFFNENDE Foto. Gegen den Vorgaenger gemessen liefe ein
        langsames Fortschreiten unbegrenzt weiter, ohne je zu trennen - die Dauergrenze waere eine
        zweite Zeitluecke."""
        candidates = self._dense_run(_max_span() + EPSILON_TIME)

        assert len(_build(candidates, [EventSpanSignal()])) == 2

    def test_midnight_alone_no_longer_splits(self) -> None:
        """Die tragende Verhaltensaenderung: Zwei Aufnahmen beiderseits von Mitternacht, deren
        Zeitluecke unter der Schwelle liegt, stehen im SELBEN Event."""
        candidates = [
            _placeless_candidate(1, datetime(2026, 7, 20, 23, 59, 30)),
            _placeless_candidate(2, datetime(2026, 7, 21, 0, 0, 30)),
        ]

        events = _build(candidates, default_signals())

        assert [event.photo_ids for event in events] == [(1, 2)]
        assert events[0].started_at.date() != events[0].ended_at.date()


class TestStepDistanceSignal(_UnderShiftedEventConstants):
    """Der SCHRITT zwischen zwei aufeinanderfolgenden Fotos, geprueft am Symbol
    `EVENT_STEP_MAX_METERS`."""

    def _two_photos(self, meters: float) -> list[EventCandidate]:
        return [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_north(meters)),
        ]

    def test_below_the_symbol_stays_one_event(self) -> None:
        candidates = self._two_photos(_step_max() - EPSILON_METERS)

        assert len(_build(candidates, [StepDistanceSignal()])) == 1

    def test_above_the_symbol_splits(self) -> None:
        candidates = self._two_photos(_step_max() + EPSILON_METERS)

        assert len(_build(candidates, [StepDistanceSignal()])) == 2

    def test_exactly_at_the_threshold_does_not_split(self) -> None:
        """`>` und nicht `>=`, exakt festgelegt: die Schwelle wird auf den GEMESSENEN Abstand
        gesetzt, statt eine Koordinate zu suchen, die den Zahlwert zufaellig trifft."""
        candidates = self._two_photos(_step_max())
        distance = haversine_meters(BASE_LAT, BASE_LON, _north(_step_max()), BASE_LON)

        assert len(_build(candidates, [StepDistanceSignal(distance)])) == 1
        assert len(_build(candidates, [StepDistanceSignal(distance - 1e-9)])) == 2

    def test_the_reference_is_the_last_effective_coordinate_of_the_running_event(self) -> None:
        """Nicht der Event-Anfang: eine Kette kleiner Schritte teilt der SCHRITT nie."""
        step = _step_max() - EPSILON_METERS
        candidates = [
            _measured_candidate(index, _at(minutes=index), lat=_north(index * step))
            for index in range(1, 9)
        ]

        assert len(_build(candidates, [StepDistanceSignal()])) == 1

    def test_a_candidate_without_any_location_never_splits(self) -> None:
        assert (
            len(
                _build(
                    [_placeless_candidate(1, T0), _placeless_candidate(2, _at(minutes=1))],
                    [StepDistanceSignal()],
                )
            )
            == 1
        )


class TestExtentSignal(_UnderShiftedEventConstants):
    """Die AUSDEHNUNG des laufenden Events - die Diagonale der umschliessenden Box, geprueft am
    Symbol `EVENT_EXTENT_MAX_METERS`."""

    def _walk(self, step_meters: float, count: int) -> list[EventCandidate]:
        return [
            _measured_candidate(index, _at(minutes=index), lat=_north(index * step_meters))
            for index in range(count)
        ]

    def test_below_the_symbol_stays_one_event(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_north(_extent_max() - EPSILON_METERS)),
        ]

        assert len(_build(candidates, [ExtentSignal()])) == 1

    def test_above_the_symbol_splits(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_north(_extent_max() + EPSILON_METERS)),
        ]

        assert len(_build(candidates, [ExtentSignal()])) == 2

    def test_exactly_at_the_threshold_does_not_split(self) -> None:
        """`>` und nicht `>=`, exakt festgelegt (siehe Schritt-Signal)."""
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_north(_extent_max())),
        ]
        diagonal = haversine_meters(BASE_LAT, BASE_LON, _north(_extent_max()), BASE_LON)

        assert len(_build(candidates, [ExtentSignal(diagonal)])) == 1
        assert len(_build(candidates, [ExtentSignal(diagonal - 1e-9)])) == 2

    def test_the_extent_includes_the_photo_under_consideration(self) -> None:
        """REGRESSIONSFALL: das ueberschreitende Foto BEGINNT das neue Event, es beendet nicht das
        alte - sonst begaenne das neue Event ein Foto zu spaet.

        Die Schrittweite kommt aus dem Symbol: So viele Schritte, dass die Box ERST beim letzten
        Foto reisst - das ist genau die Lage, die den Unterschied sichtbar macht."""
        step = _step_max() - EPSILON_METERS
        count = int(_extent_max() / step) + 2
        candidates = self._walk(step_meters=step, count=count)

        events = _build(candidates, [ExtentSignal()])

        assert [event.photo_ids for event in events] == [
            tuple(range(count - 1)),
            (count - 1,),
        ]

    def test_the_extent_splits_where_the_step_never_would(self) -> None:
        """Der fachliche Kern: ein Spaziergang in Schritten unter der Schritt-Schwelle, ueber eine
        Gesamtstrecke jenseits der Ausdehnung. Jeder EINZELNE Schritt bleibt unter der Schwelle,
        das Event wird trotzdem getrennt."""
        step = _step_max() - EPSILON_METERS
        candidates = self._walk(step_meters=step, count=int(_extent_max() / step) + 2)

        by_step = _build(candidates, [StepDistanceSignal()])
        by_extent = _build(candidates, [ExtentSignal()])

        assert len(by_step) == 1
        assert len(by_extent) > 1

    def test_a_long_pause_at_the_same_place_tears_nothing_apart(self) -> None:
        """Komplementaer zum Fall darueber: Verweilen ist keine Grenze, solange die Zeitluecke
        unterschritten bleibt."""
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, T0 + _time_gap() - EPSILON_TIME),
            _measured_candidate(3, T0 + 2 * (_time_gap() - EPSILON_TIME)),
        ]

        assert len(_build(candidates, default_signals())) == 1

    def test_only_the_running_event_counts(self) -> None:
        """Die Box wird an JEDER Grenze zurueckgesetzt, auch an einer fremden."""
        candidates = [
            _measured_candidate(1, T0, lat=_north(0.0)),
            _measured_candidate(
                2, T0 + _time_gap() + EPSILON_TIME, lat=_north(_extent_max() + EPSILON_METERS)
            ),
        ]

        events = _build(candidates, [TimeGapSignal(), ExtentSignal()])

        assert [event.photo_ids for event in events] == [(1,), (2,)]


class TestTheLandmarkNameDoesNotSplitAnything(_UnderShiftedEventConstants):
    """Die Sehenswuerdigkeit ist seit ADR 0118 KEIN Trennsignal mehr - sie trennt an keiner Stelle
    und haelt keine Grenze mehr fest.

    Gemessen wird ueber den VOLLEN Signalsatz, nicht ueber ein injiziertes Signal: Die Zusage ist
    gerade, dass es das Signal nicht mehr gibt, und ein injizierbares Signal koennte sie nicht
    verfehlen. Alle Faelle liegen dicht unter jeder Schwelle - was hier trennte, traege der
    Name."""

    def test_two_photos_differing_only_in_their_name_stay_in_one_event(self) -> None:
        candidates = [
            _placeless_candidate(1, T0, landmark_name="Eiffelturm"),
            _placeless_candidate(2, T0 + EPSILON_TIME, landmark_name="Louvre"),
        ]

        events = _build(candidates)

        assert [event.photo_ids for event in events] == [(1, 2)]

    def test_a_name_appearing_after_nameless_photos_does_not_split(self) -> None:
        candidates = [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, T0 + EPSILON_TIME, landmark_name="Eiffelturm"),
            _placeless_candidate(3, T0 + 2 * EPSILON_TIME, landmark_name="Louvre"),
        ]

        assert len(_build(candidates)) == 1

    def test_a_run_of_names_never_produces_a_landmark_cause(self) -> None:
        """Der Nachweis in der Waehrung des Berichts: `sehenswuerdigkeit` bleibt im Vorrat und
        steht in der Nachmessung bei null - nicht, weil die Zeile fehlte, sondern weil keine
        Grenze sie mehr traegt."""
        candidates = [
            _placeless_candidate(index, T0 + index * EPSILON_TIME, landmark_name=f"Ort {index}")
            for index in range(6)
        ]

        formation = _explain(candidates)

        assert all(BOUNDARY_LANDMARK not in cause for cause in formation.causes)


class TestSignalsAreNeverShortCircuited(_UnderShiftedEventConstants):
    """Zwei Nachweise. Der zweite ist ein STRUKTUR-, kein Verhaltenstest - er steht, weil das
    Motivwechsel-Signal aus #427 genau auf dieser Zusage aufsetzt."""

    def _after_a_time_boundary(self, jump: float, follow_up: float) -> list[EventCandidate]:
        """Drei Fotos: eines am Bezugsort, dann - hinter einer Zeitluecke - ein Sprung um `jump`
        und ein kleiner Schritt um `follow_up` weiter."""
        after = T0 + _time_gap() + EPSILON_TIME
        return [
            _measured_candidate(1, T0, lat=_north(0.0)),
            _measured_candidate(2, after, lat=_north(jump)),
            _measured_candidate(3, after + EPSILON_TIME, lat=_north(jump + follow_up)),
        ]

    def test_a_time_boundary_also_resets_the_step_signal(self) -> None:
        """Ohne Ruecksetzung verglichen die Schritte des neuen Events weiter gegen eine Koordinate
        aus dem vorherigen - und traennten ein zweites Mal."""
        candidates = self._after_a_time_boundary(
            jump=_step_max() + EPSILON_METERS, follow_up=_step_max() - EPSILON_METERS
        )

        events = _build(candidates, [TimeGapSignal(), StepDistanceSignal()])

        assert [event.photo_ids for event in events] == [(1,), (2, 3)]

    def test_a_time_boundary_also_resets_the_extent_signal(self) -> None:
        candidates = self._after_a_time_boundary(
            jump=_extent_max() + EPSILON_METERS, follow_up=_extent_max() - EPSILON_METERS
        )

        events = _build(candidates, [TimeGapSignal(), ExtentSignal()])

        assert [event.photo_ids for event in events] == [(1,), (2, 3)]

    def test_every_signal_is_asked_about_every_candidate(self) -> None:
        """Der VERTRAG: die Auswertung laeuft ueber eine Liste, nicht ueber ein
        kurzgeschlossenes `or`. Ein Signal, dessen Antwort nichts mehr aendert, wird trotzdem
        gefragt - sonst haenge seine Zustandsfortschreibung an der Listenposition."""
        spy = _SpySignal()
        candidates = [_placeless_candidate(index, _at(minutes=index)) for index in range(1, 5)]

        _build(candidates, [_AlwaysSignal(), spy])

        assert spy.asked == [1, 2, 3, 4]

    def test_every_signal_gets_exactly_one_writing_call_per_candidate(self) -> None:
        spy = _SpySignal()
        candidates = [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, T0 + EPSILON_TIME),
            _placeless_candidate(3, T0 + _time_gap() + 2 * EPSILON_TIME),
        ]

        _build(candidates, [TimeGapSignal(), spy])

        assert sorted(spy.begun + spy.advanced) == [1, 2, 3]
        assert spy.begun == [1, 3]
        assert spy.advanced == [2]


class TestDefaultSignals:
    def test_carries_all_four_signal_classes(self) -> None:
        """Die Liste ist der Erweiterungspunkt (#427): ein neues Signal ist eine Klasse und ein
        Eintrag, kein Eingriff in den Durchlauf.

        VIER seit ADR 0118. Die Liste fuehrt ausschliesslich Signale, die TRENNEN - ein nie
        meldender Eintrag machte aus ihr eine Liste mit zwei Bedeutungen."""
        assert [type(signal) for signal in default_signals()] == [
            TimeGapSignal,
            EventSpanSignal,
            StepDistanceSignal,
            ExtentSignal,
        ]

    def test_every_call_yields_fresh_state(self) -> None:
        """Signale sind zustandsbehaftet - eine geteilte Liste tarnte einen Lauf als Fortsetzung
        des vorherigen."""
        first = default_signals()
        second = default_signals()

        assert all(a is not b for a, b in zip(first, second, strict=True))

    def test_build_events_uses_them_by_default(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, T0 + _time_gap() + EPSILON_TIME),
        ]

        assert len(_build(candidates)) == 2


class TestTheCorrectedTimeFeedsTheEventBoundaries:
    """specs/features/0426-zeitversatz-je-kamera.md: `build_events` bekommt seit ADR 0090 die
    KORRIGIERTE Zeit uebergeben und braucht deshalb KEINE eigene Korrekturlogik.

    Der Nachweis ist ein Datensatz, dessen Gliederung mit dem Versatz ANDERS ausfaellt als mit dem
    rohen Wert - liefe die Event-Bildung weiter auf der aufgezeichneten Zeit, zerrisse sie
    Aufnahmen desselben Moments, ohne dass eine Fehlermeldung erschiene."""

    def test_the_recorded_time_splits_what_the_corrected_time_keeps_together(self) -> None:
        offset = _time_gap() + EPSILON_TIME
        raw = [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, T0 + offset),
        ]
        corrected = [
            _placeless_candidate(1, T0),
            # dieselbe Datei, um ihren Versatz zurueckgestellt
            _placeless_candidate(2, T0),
        ]

        assert len(_build(raw)) == 2
        assert len(_build(corrected)) == 1


class TestInheritedLocationsReportWithoutACoordinate:
    """Was eine Uebernahme ueber sich selbst aussagt - der Messgegenstand von Block C1. Die
    Auskunft traegt KEINE Koordinate: nur den Zeitabstand zum gewaehlten Anker und die Spanne
    zwischen den beiden koordinatentragenden Nachbarn."""

    def test_a_photo_with_its_own_coordinate_reports_nothing(self) -> None:
        entries = [LocationEntry(photo_id=1, taken_at=T0, gps_lat=BASE_LAT, gps_lon=BASE_LON)]

        assert inherited_locations(entries) == []

    def test_without_any_anchor_nobody_inherits_and_nobody_reports(self) -> None:
        entries = [LocationEntry(photo_id=1, taken_at=T0)]

        assert inherited_locations(entries) == []

    def test_the_time_distance_is_measured_against_the_anchor_that_was_actually_chosen(
        self,
    ) -> None:
        """Gemessen wird gegen DENSELBEN Anker, den `infer_locations` waehlt - eine zweite Fassung
        der Wahl maesse den Abstand zu einem Anker, den das Foto gar nicht geerbt hat."""
        entries = [
            LocationEntry(photo_id=1, taken_at=_at(minutes=-2), gps_lat=BASE_LAT, gps_lon=BASE_LON),
            LocationEntry(photo_id=2, taken_at=T0),
            LocationEntry(
                photo_id=3, taken_at=_at(minutes=10), gps_lat=_north(1000.0), gps_lon=BASE_LON
            ),
        ]

        [report] = inherited_locations(entries)

        assert report.photo_id == 2
        assert report.seconds_to_anchor == 120.0
        assert infer_locations(entries)[2].lat == BASE_LAT

    def test_the_anchor_span_is_the_distance_between_the_two_neighbours(self) -> None:
        """Die Spanne belegt OHNE jede aeussere Wahrheit, wie wenig eine Uebernahme aussagt:
        Liegen die beiden koordinatentragenden Nachbarn weit auseinander, ist sie ein Muenzwurf."""
        distance = 4000.0
        entries = [
            LocationEntry(photo_id=1, taken_at=_at(minutes=-5), gps_lat=BASE_LAT, gps_lon=BASE_LON),
            LocationEntry(photo_id=2, taken_at=T0),
            LocationEntry(
                photo_id=3, taken_at=_at(minutes=5), gps_lat=_north(distance), gps_lon=BASE_LON
            ),
        ]

        [report] = inherited_locations(entries)

        assert report.anchor_span_meters is not None
        assert report.anchor_span_meters == pytest.approx(distance, rel=0.01)

    def test_with_only_one_neighbour_the_span_is_absent_not_zero(self) -> None:
        """Ausfallrichtung: Es gibt keine Spanne, und `0` hiesse "die beiden Nachbarn liegen am
        selben Ort" - das waere die guenstigste aller Aussagen ueber eine Uebernahme."""
        entries = [
            LocationEntry(photo_id=1, taken_at=_at(minutes=-5), gps_lat=BASE_LAT, gps_lon=BASE_LON),
            LocationEntry(photo_id=2, taken_at=T0),
        ]

        [report] = inherited_locations(entries)

        assert report.anchor_span_meters is None
