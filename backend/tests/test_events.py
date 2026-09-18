from __future__ import annotations

import ast
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from itertools import permutations, product
from pathlib import Path

import pytest

from photosort import events as events_module
from photosort.events import (
    BOUNDARY_CALENDAR_DAY,
    BOUNDARY_CAUSES,
    BOUNDARY_EXTENT,
    BOUNDARY_LANDMARK,
    BOUNDARY_MOTIF_CHANGE,
    BOUNDARY_STEP,
    BOUNDARY_TIME_GAP,
    EVENT_EXTENT_MAX_METERS,
    BoundarySignal,
    BuiltEvent,
    DayBoundarySignal,
    EffectiveLocation,
    EventCandidate,
    EventFormation,
    EventSpan,
    ExtentSignal,
    LandmarkChangeSignal,
    LocationEntry,
    StepDistanceSignal,
    TimeGapSignal,
    assign_place_names,
    build_events,
    default_signals,
    event_for_time,
    explain_events,
    infer_locations,
    inherited_locations,
    motif_change_starts,
)
from photosort.places import MAX_PLACE_NAME_LENGTH, PlaceInfo
from photosort.scoring import (
    GPS_CLUSTER_SPLIT_DISTANCE_METERS,
    TIME_CLUSTER_GAP,
    haversine_meters,
)
from photosort.selection import MOTIF_PRESENCE_THRESHOLD

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "photosort"

# Bezugszeitpunkt aller Faelle. Zonenlos, wie `Photo.taken_at` selbst.
T0 = datetime(2026, 7, 20, 10, 0, 0)

# Bezugsort aller Faelle. Verschoben wird ausschliesslich nach NORDEN: die Breitengrad-Strecke
# haengt nicht vom Laengengrad ab, und die umschliessende Box wird damit zur reinen Nord-Sued-
# Strecke - der Abstand zweier Punkte IST dann ihre Box-Diagonale.
BASE_LAT = 48.0
BASE_LON = 2.0
_METERS_PER_DEGREE_LATITUDE = 111_195.0

# Abstand zum jeweiligen SYMBOL, gross genug, um die Naeherung der Grad-Umrechnung zu ueberdecken,
# und klein gegen jede Schwelle. Die Zahlwerte der Schwellen stehen in KEINEM Testfall.
EPSILON_METERS = 50.0
EPSILON_TIME = timedelta(seconds=1)


def _at(**delta: float) -> datetime:
    return T0 + timedelta(**delta)


def _north(meters: float) -> float:
    """Breitengrad `meters` noerdlich von `BASE_LAT`."""
    return BASE_LAT + meters / _METERS_PER_DEGREE_LATITUDE


def _measured_candidate(
    photo_id: int,
    taken_at: datetime,
    *,
    lat: float = BASE_LAT,
    lon: float = BASE_LON,
    landmark_name: str | None = None,
    motif_strengths: Mapping[str, float] | None = None,
) -> EventCandidate:
    """Ein Kandidat mit EIGENER, gemessener Koordinate."""
    return EventCandidate(
        photo_id=photo_id,
        taken_at=taken_at,
        location=EffectiveLocation(lat=lat, lon=lon, inferred=False),
        gps_lat=lat,
        gps_lon=lon,
        landmark_name=landmark_name,
        motif_strengths=motif_strengths,
    )


def _inherited_candidate(
    photo_id: int,
    taken_at: datetime,
    *,
    lat: float = BASE_LAT,
    lon: float = BASE_LON,
    landmark_name: str | None = None,
) -> EventCandidate:
    """Ein Kandidat mit UEBERNOMMENEM Ort - wirksam fuer die Grenzen, nie fuer den Ortsbezug."""
    return EventCandidate(
        photo_id=photo_id,
        taken_at=taken_at,
        location=EffectiveLocation(lat=lat, lon=lon, inferred=True),
        gps_lat=None,
        gps_lon=None,
        landmark_name=landmark_name,
    )


def _placeless_candidate(
    photo_id: int, taken_at: datetime, *, landmark_name: str | None = None
) -> EventCandidate:
    """Ein Kandidat ganz ohne Ort - der Normalfall eines Projekts ohne jede Koordinate."""
    return EventCandidate(
        photo_id=photo_id,
        taken_at=taken_at,
        location=None,
        gps_lat=None,
        gps_lon=None,
        landmark_name=landmark_name,
    )


# Die Staerken der Motivfaelle stehen ausschliesslich als SYMBOL zur Praesenzgrenze - kein Fall
# nennt ihren Zahlwert. `_AT_THRESHOLD` und `_JUST_BELOW` sind das Paar, an dem ein in `events.py`
# nachgebautes `>` statt des geteilten inklusiven `>=` rot wird.
_ABOVE = 1.0
_AT_THRESHOLD = MOTIF_PRESENCE_THRESHOLD
_JUST_BELOW = math.nextafter(MOTIF_PRESENCE_THRESHOLD, 0.0)
_BELOW = 0.0

# Vier frei gewaehlte Schluessel: `events.py` kennt das Motiv-Vokabular nicht und darf es nicht
# kennen - fuer die Regel zaehlt allein die MENGE der getragenen Schluessel.
_MOTIF_KEYS = ("a", "b", "c", "d")


def _picture(*carried: str) -> dict[str, float]:
    """Eine Motiv-Kopfzeile, die GENAU die genannten Motive traegt.

    Die uebrigen stehen ausgeschrieben unter der Grenze - `_picture()` ist damit die vorhandene
    Kopfzeile ohne ein einziges getragenes Motiv (das leere Motivbild) und ausdruecklich etwas
    anderes als `None` (keine Kopfzeile)."""
    strengths = {key: _BELOW for key in _MOTIF_KEYS}
    strengths.update({key: _ABOVE for key in carried})
    return strengths


def _motif_candidates(
    pictures: Sequence[Mapping[str, float] | None], *, excluded: Collection[int] = ()
) -> list[EventCandidate]:
    """Kandidaten aus einer Folge von Motiv-Kopfzeilen - `photo_id` IST der Index.

    Ohne Ort, ohne Namen und mit einem Sekundenabstand: kein anderes Trennsignal spricht mit,
    gleich wie lang die Folge wird. Nur so darf die Laenge aus dem Symbol
    `MOTIF_CHANGE_CONFIRMING_PHOTOS` wachsen, ohne dass Zeitluecke oder Tagesgrenze dazwischen-
    geraten."""
    return [
        EventCandidate(
            photo_id=index,
            taken_at=T0 + index * EPSILON_TIME,
            motif_strengths=None if picture is None else dict(picture),
            excluded_document=index in excluded,
        )
        for index, picture in enumerate(pictures)
    ]


class _UnderEveryConfirmingWindow:
    """Jeder Fall einer erbenden Klasse laeuft unter MEHREREN Fensterlaengen.

    Die Fensterlaenge ist eine aenderbare, unkalibrierte Festlegung; kein Fall darf ihren Zahlwert
    pinnen. Die Faelle bauen ihre Folgen deshalb aus `_window()` statt aus einer Zahl, und diese
    Fixture setzt die Modulkonstante auf jeden Wert der Liste. Ein Fall, der den Zahlwert doch
    spiegelt, wird unter mindestens einem Parameter rot.

    VORAUSSETZUNG, die still braeche: Die Konstante wird als MODULATTRIBUT gelesen
    (`events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS`, siehe `_window`). Ein `from ... import` baende
    den Wert beim Import des Testmoduls, und die Faelle waeren unter der Fixture falsch
    dimensioniert."""

    @pytest.fixture(
        autouse=True,
        params=sorted({2, 5, events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS}),
    )
    def _confirming_window(
        self, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(events_module, "MOTIF_CHANGE_CONFIRMING_PHOTOS", request.param)


def _window() -> int:
    """Die aktuell geltende Fensterlaenge - als Modulattribut gelesen, nie als Zahl."""
    return events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS


def assert_event_invariants(
    candidates: Sequence[EventCandidate], events: Sequence[BuiltEvent]
) -> None:
    """Die vier Zusagen ueber JEDE Event-Folge eines Laufs - laeuft am Ende JEDES
    `build_events`-Falls, nicht nur dort, wo der Fall sie zum Gegenstand hat.

    Kein Property-Testing: `hypothesis` waere eine ADR-pflichtige neue Abhaengigkeit."""
    assert [event.position for event in events] == list(range(1, len(events) + 1))

    for event in events:
        assert event.started_at <= event.ended_at
        assert event.photo_ids, "ein Event ohne Fotos ist keines"

    for earlier, later in zip(events, events[1:], strict=False):
        assert earlier.ended_at <= later.started_at

    assigned = [photo_id for event in events for photo_id in event.photo_ids]
    assert sorted(assigned) == sorted(candidate.photo_id for candidate in candidates)
    assert len(assigned) == len(set(assigned)), "ein Foto gehoert zu genau einem Event"


def _build(
    candidates: Sequence[EventCandidate], signals: list[BoundarySignal] | None = None
) -> list[BuiltEvent]:
    """`build_events` plus der Invarianten-Helfer - jeder Fall dieser Datei laeuft hierueber."""
    events = build_events(candidates, signals)
    assert_event_invariants(candidates, events)
    return events


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


class TestTimeGapSignal:
    """Unveraendertes Verhalten, geprueft am SYMBOL `TIME_CLUSTER_GAP`."""

    def _two_photos(self, distance: timedelta) -> list[EventCandidate]:
        return [_placeless_candidate(1, T0), _placeless_candidate(2, T0 + distance)]

    def test_below_the_symbol_stays_one_event(self) -> None:
        events = _build(self._two_photos(TIME_CLUSTER_GAP - EPSILON_TIME), [TimeGapSignal()])

        assert len(events) == 1

    def test_above_the_symbol_splits(self) -> None:
        events = _build(self._two_photos(TIME_CLUSTER_GAP + EPSILON_TIME), [TimeGapSignal()])

        assert len(events) == 2

    def test_exactly_at_the_symbol_does_not_split(self) -> None:
        """`>` und nicht `>=` - exakt, weil `timedelta`-Arithmetik exakt ist."""
        events = _build(self._two_photos(TIME_CLUSTER_GAP), [TimeGapSignal()])

        assert len(events) == 1


class TestDayBoundarySignal:
    """Der Kalendertag als Grenze - neu, und OHNE Zahlwert: verglichen werden die ersten zehn
    Zeichen des zonenlosen Zeitstempels."""

    def test_one_minute_across_midnight_splits(self) -> None:
        candidates = [
            _placeless_candidate(1, datetime(2026, 7, 20, 23, 59, 30)),
            _placeless_candidate(2, datetime(2026, 7, 21, 0, 0, 30)),
        ]

        events = _build(candidates, [DayBoundarySignal()])

        assert [event.photo_ids for event in events] == [(1,), (2,)]

    def test_the_same_day_does_not_split(self) -> None:
        candidates = [
            _placeless_candidate(1, datetime(2026, 7, 20, 0, 0, 1)),
            _placeless_candidate(2, datetime(2026, 7, 20, 23, 59, 59)),
        ]

        events = _build(candidates, [DayBoundarySignal()])

        assert len(events) == 1


class TestStepDistanceSignal:
    """Der SCHRITT zwischen zwei aufeinanderfolgenden Fotos, geprueft am Symbol
    `GPS_CLUSTER_SPLIT_DISTANCE_METERS`."""

    def _two_photos(self, meters: float) -> list[EventCandidate]:
        return [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_north(meters)),
        ]

    def test_below_the_symbol_stays_one_event(self) -> None:
        candidates = self._two_photos(GPS_CLUSTER_SPLIT_DISTANCE_METERS - EPSILON_METERS)

        assert len(_build(candidates, [StepDistanceSignal()])) == 1

    def test_above_the_symbol_splits(self) -> None:
        candidates = self._two_photos(GPS_CLUSTER_SPLIT_DISTANCE_METERS + EPSILON_METERS)

        assert len(_build(candidates, [StepDistanceSignal()])) == 2

    def test_exactly_at_the_threshold_does_not_split(self) -> None:
        """`>` und nicht `>=`, exakt festgelegt: die Schwelle wird auf den GEMESSENEN Abstand
        gesetzt, statt eine Koordinate zu suchen, die den Zahlwert zufaellig trifft."""
        candidates = self._two_photos(500.0)
        distance = haversine_meters(BASE_LAT, BASE_LON, _north(500.0), BASE_LON)

        assert len(_build(candidates, [StepDistanceSignal(distance)])) == 1
        assert len(_build(candidates, [StepDistanceSignal(distance - 1e-9)])) == 2

    def test_the_reference_is_the_last_effective_coordinate_of_the_running_event(self) -> None:
        """Nicht der Event-Anfang: eine Kette kleiner Schritte teilt der SCHRITT nie."""
        candidates = [
            _measured_candidate(index, _at(minutes=index), lat=_north(index * 400.0))
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


class TestExtentSignal:
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
            _measured_candidate(
                2, _at(minutes=1), lat=_north(EVENT_EXTENT_MAX_METERS - EPSILON_METERS)
            ),
        ]

        assert len(_build(candidates, [ExtentSignal()])) == 1

    def test_above_the_symbol_splits(self) -> None:
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(
                2, _at(minutes=1), lat=_north(EVENT_EXTENT_MAX_METERS + EPSILON_METERS)
            ),
        ]

        assert len(_build(candidates, [ExtentSignal()])) == 2

    def test_exactly_at_the_threshold_does_not_split(self) -> None:
        """`>` und nicht `>=`, exakt festgelegt (siehe Schritt-Signal)."""
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(minutes=1), lat=_north(1000.0)),
        ]
        diagonal = haversine_meters(BASE_LAT, BASE_LON, _north(1000.0), BASE_LON)

        assert len(_build(candidates, [ExtentSignal(diagonal)])) == 1
        assert len(_build(candidates, [ExtentSignal(diagonal - 1e-9)])) == 2

    def test_the_extent_includes_the_photo_under_consideration(self) -> None:
        """REGRESSIONSFALL: das ueberschreitende Foto BEGINNT das neue Event, es beendet nicht das
        alte - sonst begaenne das neue Event ein Foto zu spaet."""
        candidates = [
            _measured_candidate(index, _at(minutes=index), lat=_north(index * 300.0))
            for index in range(1, 6)
        ]

        events = _build(candidates, [ExtentSignal()])

        # Foto 5 liegt 1200 m ueber Foto 1; die Box bis Foto 4 misst 900 m.
        assert [event.photo_ids for event in events] == [(1, 2, 3, 4), (5,)]

    def test_the_extent_splits_where_the_step_never_would(self) -> None:
        """Der fachliche Kern: ein Spaziergang in 400-m-Schritten ueber 3 km. Jeder EINZELNE
        Schritt bleibt unter der Schritt-Schwelle, das Event wird trotzdem getrennt."""
        candidates = self._walk(step_meters=400.0, count=9)

        by_step = _build(candidates, [StepDistanceSignal()])
        by_extent = _build(candidates, [ExtentSignal()])

        assert len(by_step) == 1
        assert len(by_extent) > 1

    def test_a_long_pause_at_the_same_place_tears_nothing_apart(self) -> None:
        """Komplementaer zum Fall darueber: Verweilen ist keine Grenze, solange die Zeitluecke
        unterschritten bleibt."""
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, T0 + TIME_CLUSTER_GAP - EPSILON_TIME),
            _measured_candidate(3, T0 + 2 * (TIME_CLUSTER_GAP - EPSILON_TIME)),
        ]

        assert len(_build(candidates, default_signals())) == 1

    def test_only_the_running_event_counts(self) -> None:
        """Die Box wird an JEDER Grenze zurueckgesetzt, auch an einer fremden."""
        candidates = [
            _measured_candidate(1, T0, lat=_north(0.0)),
            _measured_candidate(2, _at(hours=3), lat=_north(5000.0)),
        ]

        events = _build(candidates, [TimeGapSignal(), ExtentSignal()])

        assert [event.photo_ids for event in events] == [(1,), (2,)]


class TestLandmarkChangeSignal:
    """Die Sehenswuerdigkeit als TRENNSIGNAL statt als Gruppierungsmerkmal."""

    def test_a_different_name_splits(self) -> None:
        candidates = [
            _placeless_candidate(1, T0, landmark_name="Eiffelturm"),
            _placeless_candidate(2, _at(minutes=1), landmark_name="Louvre"),
        ]

        events = _build(candidates, [LandmarkChangeSignal()])

        assert [event.photo_ids for event in events] == [(1,), (2,)]

    def test_the_same_name_does_not_split(self) -> None:
        candidates = [
            _placeless_candidate(1, T0, landmark_name="Eiffelturm"),
            _placeless_candidate(2, _at(minutes=1), landmark_name="Eiffelturm"),
        ]

        assert len(_build(candidates, [LandmarkChangeSignal()])) == 1

    def test_a_nameless_photo_never_triggers(self) -> None:
        """Weder als Kandidat noch als laufendes Event: ein namenloses Foto zwischen zwei gleichen
        Namen zerreisst nichts, und ein Name nach namenlosen Fotos ebenfalls nicht."""
        candidates = [
            _placeless_candidate(1, T0, landmark_name="Eiffelturm"),
            _placeless_candidate(2, _at(minutes=1)),
            _placeless_candidate(3, _at(minutes=2), landmark_name="Eiffelturm"),
        ]

        assert len(_build(candidates, [LandmarkChangeSignal()])) == 1

    def test_a_name_after_nameless_photos_does_not_split(self) -> None:
        candidates = [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, _at(minutes=1), landmark_name="Eiffelturm"),
        ]

        assert len(_build(candidates, [LandmarkChangeSignal()])) == 1

    def test_an_empty_name_counts_as_absent(self) -> None:
        """`sanitize_landmark_name` liefert `None`; ein leerer Rest waere trotzdem kein Name."""
        candidates = [
            _placeless_candidate(1, T0, landmark_name="Eiffelturm"),
            _placeless_candidate(2, _at(minutes=1), landmark_name="   "),
        ]

        assert len(_build(candidates, [LandmarkChangeSignal()])) == 1

    def test_the_running_event_keeps_its_first_name_across_nameless_photos(self) -> None:
        candidates = [
            _placeless_candidate(1, T0, landmark_name="Eiffelturm"),
            _placeless_candidate(2, _at(minutes=1)),
            _placeless_candidate(3, _at(minutes=2), landmark_name="Louvre"),
        ]

        events = _build(candidates, [LandmarkChangeSignal()])

        assert [event.photo_ids for event in events] == [(1, 2), (3,)]


class _SpySignal:
    """Ein Signal, das nie trennt und mitschreibt, wonach es gefragt wurde."""

    name = "spion"

    def __init__(self) -> None:
        self.asked: list[int] = []
        self.begun: list[int] = []
        self.advanced: list[int] = []

    def is_boundary(self, candidate: EventCandidate) -> bool:
        self.asked.append(candidate.photo_id)
        return False

    def begin(self, candidate: EventCandidate) -> None:
        self.begun.append(candidate.photo_id)

    def advance(self, candidate: EventCandidate) -> None:
        self.advanced.append(candidate.photo_id)


class _AlwaysSignal:
    """Ein Signal, das bei JEDEM Kandidaten trennt - steht VOR dem Spion in der Liste."""

    name = "immer"

    def is_boundary(self, candidate: EventCandidate) -> bool:
        return True

    def begin(self, candidate: EventCandidate) -> None:
        return None

    def advance(self, candidate: EventCandidate) -> None:
        return None


class TestSignalsAreNeverShortCircuited:
    """Zwei Nachweise. Der zweite ist ein STRUKTUR-, kein Verhaltenstest - er steht, weil das
    Motivwechsel-Signal aus #427 genau auf dieser Zusage aufsetzt."""

    def test_a_time_boundary_also_resets_the_step_signal(self) -> None:
        """Ohne Ruecksetzung verglichen die Schritte des neuen Events weiter gegen eine Koordinate
        aus dem vorherigen - und traennten ein zweites Mal."""
        candidates = [
            _measured_candidate(1, T0, lat=_north(0.0)),
            _measured_candidate(2, _at(hours=3), lat=_north(900.0)),
            _measured_candidate(3, _at(hours=3, minutes=1), lat=_north(1200.0)),
        ]

        events = _build(candidates, [TimeGapSignal(), StepDistanceSignal()])

        assert [event.photo_ids for event in events] == [(1,), (2, 3)]

    def test_a_time_boundary_also_resets_the_extent_signal(self) -> None:
        candidates = [
            _measured_candidate(1, T0, lat=_north(0.0)),
            _measured_candidate(2, _at(hours=3), lat=_north(900.0)),
            _measured_candidate(3, _at(hours=3, minutes=1), lat=_north(1200.0)),
        ]

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
            _placeless_candidate(2, _at(minutes=1)),
            _placeless_candidate(3, _at(hours=3)),
        ]

        _build(candidates, [TimeGapSignal(), spy])

        assert sorted(spy.begun + spy.advanced) == [1, 2, 3]
        assert spy.begun == [1, 3]
        assert spy.advanced == [2]


class TestTheMotifChangeRule(_UnderEveryConfirmingWindow):
    """Die REINE Regel, direkt an `motif_change_starts` gemessen.

    Sie ist keine paarweise Frage, sondern eine Segmentierung ueber die ganze Folge - ihr Ergebnis
    ist eine Indexmenge und damit direkt beobachtbar. Ein Nachweis allein durch `build_events`
    hindurch saehe die Rueckwirkung nicht."""

    def test_a_newly_carried_motif_starts_a_new_event(self) -> None:
        candidates = _motif_candidates([_picture("a")] + [_picture("a", "b")] * _window())

        assert motif_change_starts(candidates) == frozenset({1})

    def test_a_dropped_motif_starts_a_new_event(self) -> None:
        """Die symmetrische Differenz ist SYMMETRISCH: der Wegfall trennt wie das Hinzukommen."""
        candidates = _motif_candidates([_picture("a", "b")] + [_picture("a")] * _window())

        assert motif_change_starts(candidates) == frozenset({1})

    def test_a_changed_strongest_motif_within_the_same_carried_set_starts_nothing(self) -> None:
        """Untersagt ist der Wechsel des STAERKSTEN Motivs (er benennt eine Rangfolge zwischen
        Motiven) - entschieden wird ueber die getragene Menge, und die ist hier unveraendert."""
        candidates = _motif_candidates(
            [{"a": _ABOVE, "b": _AT_THRESHOLD}] + [{"a": _AT_THRESHOLD, "b": _ABOVE}] * _window()
        )

        assert motif_change_starts(candidates) == frozenset()

    def test_a_strength_change_below_the_threshold_starts_nothing(self) -> None:
        """Kein Gesamtabstand ueber die Staerken: unterhalb der Grenze ist jede Bewegung
        dasselbe leere Motivbild."""
        candidates = _motif_candidates([{"a": _BELOW}] + [{"a": _JUST_BELOW}] * _window())

        assert motif_change_starts(candidates) == frozenset()

    def test_the_presence_threshold_is_inclusive_and_not_rebuilt(self) -> None:
        """Beide Haelften in EINEM Fall - ein in `events.py` nachgebautes `>` liesse die erste
        leer und bliebe in der zweiten gruen.

        Genau auf der Grenze gilt ein Motiv als getragen, knapp darunter nicht."""
        exactly_at = _motif_candidates([{"a": _JUST_BELOW}] + [{"a": _AT_THRESHOLD}] * _window())
        just_below = _motif_candidates([{"a": _BELOW}] + [{"a": _JUST_BELOW}] * _window())

        assert motif_change_starts(exactly_at) == frozenset({1})
        assert motif_change_starts(just_below) == frozenset()

    def test_the_reference_is_the_opening_photo_and_not_the_predecessor(self) -> None:
        """Eine Folge, die sich Foto fuer Foto um je EIN Motiv weiterschiebt.

        Gegen den jeweiligen Vorgaenger gemessen traete nie eine Grenze ein: jedes Foto zeigt
        gegenueber seinem Vorgaenger ein ANDERES geaendertes Motiv, und kein Fenster kaeme je
        zustande. Gegen das eroeffnende Foto gemessen trennt das Abdriften."""
        candidates = _motif_candidates(
            [_picture(*(f"m{step}" for step in range(count + 1))) for count in range(_window() + 1)]
        )

        assert motif_change_starts(candidates) == frozenset({1})

    def test_the_start_is_the_first_photo_of_the_window_not_the_confirming_one(self) -> None:
        """DIE RUECKWIRKUNG. Geprueft wird der Index selbst, nicht nur, DASS getrennt wird."""
        candidates = _motif_candidates([_picture("a")] * 2 + [_picture("a", "b")] * _window())

        assert motif_change_starts(candidates) == frozenset({2})

    def test_confirmation_does_not_require_an_identical_picture(self) -> None:
        """Bestaetigt ist der Wechsel, wenn MINDESTENS EINES der zuerst geaenderten Motive
        weiterhin geaendert ist - ein zusaetzlich getragenes Motiv reisst ihn nicht ab."""
        candidates = _motif_candidates(
            [_picture("a"), _picture("a", "b"), _picture("a", "b", "c")]
            + [_picture("a", "b")] * (_window() - 2)
        )

        assert motif_change_starts(candidates) == frozenset({1})

    def test_a_window_one_photo_short_then_a_return_to_the_reference_starts_nothing(self) -> None:
        candidates = _motif_candidates(
            [_picture("a")] + [_picture("a", "b")] * (_window() - 1) + [_picture("a")]
        )

        assert motif_change_starts(candidates) == frozenset()

    def test_a_decayed_window_followed_by_a_full_one_starts_at_the_second_window(self) -> None:
        candidates = _motif_candidates(
            [_picture("a")]
            + [_picture("a", "b")] * (_window() - 1)
            + [_picture("a")]
            + [_picture("a", "b")] * _window()
        )

        assert motif_change_starts(candidates) == frozenset({_window() + 1})

    def test_a_single_deviating_photo_never_starts_an_event(self) -> None:
        """Der verhaltensnahe Zwilling der Ungleichung `MOTIF_CHANGE_CONFIRMING_PHOTOS >= 2`:
        beide werden bei `1` rot, und das ist die zugesagte Wirkung."""
        candidates = _motif_candidates(
            [_picture("a"), _picture("a", "b")] + [_picture("a")] * _window()
        )

        assert motif_change_starts(candidates) == frozenset()

    def test_the_window_length_is_at_least_two(self) -> None:
        """Die EINE Aussage ueber den Zahlwert, und sie ist eine Ungleichung."""
        assert events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS >= 2

    def test_zero_is_never_a_start_and_every_start_is_a_valid_index(self) -> None:
        """Ein Index `0` waere ein leeres fuehrendes Event - er setzt einen bereits gesetzten
        Bezug voraus und kann deshalb nicht entstehen."""
        candidates = _motif_candidates([_picture("a")] + [_picture("b")] * _window())

        starts = motif_change_starts(candidates)

        assert 0 not in starts
        assert starts <= set(range(len(candidates)))
        assert starts

    def test_candidates_without_any_motif_information_yield_no_start(self) -> None:
        """Die Vorgabewerte von `EventCandidate`: ohne Motivangabe liefert die erste Stufe die
        leere Menge und der Durchlauf ist der bisherige."""
        candidates = [_placeless_candidate(index, _at(minutes=index)) for index in range(1, 6)]

        assert motif_change_starts(candidates) == frozenset()


class TestWhichPhotosSpeakForTheMotifChange(_UnderEveryConfirmingWindow):
    """Die drei Zustaende: keine Kopfzeile, leeres Motivbild, ausgeschlossenes Dokument.

    Der erste und der dritte heissen "redet nicht mit", der zweite redet VOLL mit. Fielen zwei
    davon zusammen, waere genau einer der Zwillingsfaelle rot - in welche Richtung sie auch
    zusammenfallen."""

    def test_a_missing_header_is_not_an_empty_motif_picture(self) -> None:
        """DAS ZWILLINGSPAAR: identisch gebaute Folgen, die sich NUR in `None` gegen die
        vorhandene Kopfzeile ohne getragenes Motiv unterscheiden - mit entgegengesetzter
        Erwartung. Ein einzelner Fall bewiese hier nichts."""
        without_header = _motif_candidates([_picture("a")] + [None] * _window())
        empty_picture = _motif_candidates([_picture("a")] + [_picture()] * _window())

        assert motif_change_starts(without_header) == frozenset()
        assert motif_change_starts(empty_picture) == frozenset({1})

    def test_a_photo_without_a_header_never_starts_an_event(self) -> None:
        candidates = _motif_candidates([_picture("a")] + [None] * _window() + [_picture("a")])

        assert motif_change_starts(candidates) == frozenset()

    def test_a_photo_without_a_header_does_not_decay_a_running_window(self) -> None:
        candidates = _motif_candidates(
            [_picture("a")] + [_picture("a", "b")] * (_window() - 1) + [None] + [_picture("a", "b")]
        )

        assert motif_change_starts(candidates) == frozenset({1})

    def test_a_photo_without_a_header_counts_in_no_window(self) -> None:
        """Dieselbe Folge wie oben, nur ohne das bestaetigende Foto dahinter: zaehlte das
        unklassifizierte mit, waere das Fenster hier bereits voll."""
        candidates = _motif_candidates(
            [_picture("a")] + [_picture("a", "b")] * (_window() - 1) + [None]
        )

        assert motif_change_starts(candidates) == frozenset()

    def test_an_excluded_document_is_not_an_empty_motif_picture(self) -> None:
        """Das Zwillingspaar ein zweites Mal - dieselben Kopfzeilen, nur einmal ausgeschlossen."""
        deviating = [_picture("a")] + [_picture("a", "b")] * _window()
        excluded_indices = range(1, _window() + 1)

        assert motif_change_starts(_motif_candidates(deviating)) == frozenset({1})
        assert (
            motif_change_starts(_motif_candidates(deviating, excluded=excluded_indices))
            == frozenset()
        )

    def test_an_excluded_document_never_starts_an_event(self) -> None:
        pictures = [_picture("a")] + [_picture("b")] * _window() + [_picture("a")]
        excluded_indices = range(1, _window() + 1)

        assert motif_change_starts(_motif_candidates(pictures, excluded=excluded_indices)) == (
            frozenset()
        )

    def test_an_excluded_document_does_not_decay_a_running_window(self) -> None:
        pictures = (
            [_picture("a")]
            + [_picture("a", "b")] * (_window() - 1)
            + [_picture("a")]
            + [_picture("a", "b")]
        )

        starts = motif_change_starts(_motif_candidates(pictures, excluded={_window()}))

        assert starts == frozenset({1})

    def test_an_excluded_document_counts_in_no_window(self) -> None:
        pictures = [_picture("a")] + [_picture("a", "b")] * _window()

        starts = motif_change_starts(_motif_candidates(pictures, excluded={_window()}))

        assert starts == frozenset()


class TestTheMotifChangeInsideBuildEvents(_UnderEveryConfirmingWindow):
    """Die zweite Stufe: der erzwungene Start neben den fuenf unveraenderten Signalen."""

    def test_the_story_case_yields_two_events_where_no_other_signal_would(self) -> None:
        """Ruinenbesuch, danach Mittagessen um die Ecke - und der ROT-ANKER daneben: dieselbe
        Folge ohne Motivangaben ergibt genau EIN Event.

        Kein anderes Signal kann den Fall erklaeren: Minutenabstand (unter der Zeitluecke),
        50 m je Schritt (unter Schritt- und Ausdehnungsschwelle), derselbe Kalendertag, kein
        Sehenswuerdigkeitsname."""
        ruins = _picture("ruine")
        lunch = _picture("essen")
        candidates = [
            _measured_candidate(
                index,
                _at(minutes=index),
                lat=_north(index * EPSILON_METERS),
                motif_strengths=picture,
            )
            for index, picture in enumerate([ruins, ruins] + [lunch] * _window())
        ]
        without_motifs = [replace(candidate, motif_strengths=None) for candidate in candidates]

        events = _build(candidates, default_signals())

        assert [event.photo_ids for event in _build(without_motifs, default_signals())] == [
            tuple(range(len(candidates)))
        ]
        assert [event.photo_ids for event in events] == [
            (0, 1),
            tuple(range(2, len(candidates))),
        ]

    def test_an_atypical_opening_photo_becomes_an_event_of_its_own(self) -> None:
        """Ein Event aus einem einzigen Foto ist zugesagt, nicht versehentlich - die Kehrseite
        des festen Bezugs auf das eroeffnende Foto."""
        candidates = _motif_candidates([_picture("a")] + [_picture("b")] * _window())

        events = _build(candidates, default_signals())

        assert [event.photo_ids for event in events] == [(0,), tuple(range(1, _window() + 1))]

    def test_a_photo_that_does_not_speak_stays_a_member_of_its_event(self) -> None:
        """UEBERGANGEN HEISST NIE AUSGESCHLOSSEN: das unklassifizierte (Index 1) und das als
        Dokument ausgeschlossene Foto (Index 2) lenken die Gliederung nicht und stehen trotzdem
        beide in ihrem Event."""
        pictures = [_picture("a"), None, _picture("a")] + [_picture("a", "b")] * _window()
        candidates = _motif_candidates(pictures, excluded={2})

        events = _build(candidates, default_signals())

        assert [event.photo_ids for event in events] == [
            (0, 1, 2),
            tuple(range(3, _window() + 3)),
        ]

    def test_a_forced_start_asks_every_signal_and_then_begins_it(self) -> None:
        """Die tragende Annahme der zweiten Stufe: ein erzwungener Start wirkt wie jede andere
        Grenze. Jedes Signal wird auch dort GEFRAGT - sonst haengt seine Fortschreibung an der
        Listenposition - und bekommt danach `begin`, nicht `advance`."""
        spy = _SpySignal()
        candidates = _motif_candidates([_picture("a")] * 2 + [_picture("a", "b")] * _window())

        _build(candidates, [spy])

        assert spy.asked == [candidate.photo_id for candidate in candidates]
        assert spy.begun == [0, 2]
        assert spy.advanced == [1, *range(3, _window() + 2)]

    def test_a_forced_start_resets_the_extent_and_can_drop_a_later_boundary(self) -> None:
        """DIE KEHRSEITE der Ruecksetzung, und der Grund, warum ein Superset-Vergleich der
        Grenzindizes mit dem motivfreien Lauf die falsche Zusage waere: Hier verschwindet die
        Ausdehnungsgrenze am letzten Foto, weil an frueherer Stelle bereits getrennt wurde.

        Die Schrittweite ist aus `EVENT_EXTENT_MAX_METERS` gebaut: ueber alle Fotos reisst die Box
        die Schwelle, ab dem erzwungenen Start nicht mehr. Nur das Ausdehnungssignal ist im Spiel -
        die Schrittweite laege ueber der Schrittschwelle."""
        step = (EVENT_EXTENT_MAX_METERS - EPSILON_METERS) / (_window() - 1)
        candidates = [
            _measured_candidate(
                index,
                _at(minutes=index),
                lat=_north(index * step),
                motif_strengths=picture,
            )
            for index, picture in enumerate([_picture("a")] + [_picture("a", "b")] * _window())
        ]
        without_motifs = [replace(candidate, motif_strengths=None) for candidate in candidates]

        assert [event.photo_ids for event in _build(without_motifs, [ExtentSignal()])] == [
            tuple(range(_window())),
            (_window(),),
        ]
        assert [event.photo_ids for event in _build(candidates, [ExtentSignal()])] == [
            (0,),
            tuple(range(1, _window() + 1)),
        ]

    def test_a_motif_boundary_on_an_index_that_already_splits_changes_nothing(self) -> None:
        """Faellt die Motivgrenze auf einen Index, an dem ohnehin getrennt wird, sind Anzahl,
        Mitgliedschaft und Positionen identisch zum motivfreien Lauf."""
        # Der Abstand zum Foto davor (das selbst bei `T0 + EPSILON_TIME` liegt) muss die Luecke
        # ECHT ueberschreiten - `TimeGapSignal` vergleicht mit `>`, nicht mit `>=`.
        after_the_gap = T0 + TIME_CLUSTER_GAP + 2 * EPSILON_TIME
        times = [T0, T0 + EPSILON_TIME] + [
            after_the_gap + index * EPSILON_TIME for index in range(_window())
        ]
        candidates = [_placeless_candidate(index, taken_at) for index, taken_at in enumerate(times)]
        candidates = [
            replace(candidate, motif_strengths=picture)
            for candidate, picture in zip(
                candidates,
                [_picture("a")] * 2 + [_picture("a", "b")] * _window(),
                strict=True,
            )
        ]
        without_motifs = [replace(candidate, motif_strengths=None) for candidate in candidates]

        events = _build(candidates, default_signals())
        reference = _build(without_motifs, default_signals())

        assert [(event.photo_ids, event.position) for event in events] == [
            (event.photo_ids, event.position) for event in reference
        ]

    def test_a_window_spanning_midnight_keeps_both_boundaries(self) -> None:
        """Der rueckwirkende Beginn liegt auf dem VORTAG, das bestaetigende Foto dahinter.
        Beide Grenzen entstehen, und kein Event reicht ueber die Tagesgrenze.

        Braucht `default_signals()`: der injizierte Signalsatz der uebrigen Faelle kennt
        `DayBoundarySignal` nicht."""
        before_midnight = datetime(2026, 7, 20, 23, 30, 0)
        last_of_the_day = datetime(2026, 7, 20, 23, 59, 59)
        after_midnight = datetime(2026, 7, 21, 0, 0, 0)
        times = [before_midnight, before_midnight + EPSILON_TIME, last_of_the_day] + [
            after_midnight + index * EPSILON_TIME for index in range(_window() - 1)
        ]
        candidates = [
            EventCandidate(photo_id=index, taken_at=taken_at, motif_strengths=picture)
            for index, (taken_at, picture) in enumerate(
                zip(
                    times,
                    [_picture("a")] * 2 + [_picture("a", "b")] * _window(),
                    strict=True,
                )
            )
        ]

        events = _build(candidates, default_signals())

        assert [event.photo_ids for event in events] == [
            (0, 1),
            (2,),
            tuple(range(3, _window() + 2)),
        ]
        for event in events:
            assert event.started_at.date() == event.ended_at.date()

    def test_a_run_without_any_carried_motif_groups_exactly_as_one_without_motif_fields(
        self,
    ) -> None:
        """Traegt kein Foto ein getragenes Motiv - weder als fehlende Kopfzeile noch als leeres
        Motivbild -, sind Anzahl, Mitgliedschaft und Positionen die bisherigen."""
        offsets = [0, 30, 61, 95, 400, 460, 461, 900, 1400, 1450]
        plain = [
            _placeless_candidate(index, _at(minutes=offset))
            for index, offset in enumerate(offsets, start=1)
        ]
        empty_pictures = [replace(candidate, motif_strengths=_picture()) for candidate in plain]

        reference = [
            (event.photo_ids, event.position) for event in _build(plain, default_signals())
        ]

        assert [
            (event.photo_ids, event.position) for event in _build(empty_pictures, default_signals())
        ] == reference


class TestEveryShortSequenceOverATinyMotifAlphabet(_UnderEveryConfirmingWindow):
    """Eine ERSCHOEPFENDE AUFZAEHLUNG an der Stelle, an der sonst Property-Testing staende -
    `hypothesis` waere eine ADR-pflichtige neue Abhaengigkeit, und hier braucht es keinen Zufall.

    Aufgezaehlt werden ALLE Folgen der Laenge `MOTIF_CHANGE_CONFIRMING_PHOTOS + 2` ueber vier
    Motivbildern: keine Kopfzeile, leeres Motivbild, ein Motiv, zwei Motive. Das deckt die Formen
    ab, die eine handverlesene Fallmenge nicht aufzaehlt (leeres fuehrendes Event, Index 0, ein
    Foto in zwei Events).

    ZULAESSIG ist die Form nur, solange Alphabet und Laenge winzig bleiben: die Zahl der Laeufe
    waechst exponentiell, und jeder einzelne muss linear und DB-frei sein."""

    def test_every_sequence_keeps_the_invariants_and_the_index_promises(self) -> None:
        alphabet = (None, _picture(), _picture("a"), _picture("a", "b"))

        for combination in product(alphabet, repeat=_window() + 2):
            candidates = _motif_candidates(list(combination))
            starts = motif_change_starts(candidates)

            assert 0 not in starts, combination
            assert starts <= set(range(len(candidates))), combination
            # Kein anderes Signal spricht bei diesen Kandidaten mit (Sekundenabstand, kein Ort,
            # kein Name): JEDER erzwungene Start ist damit genau eine Event-Grenze und keine
            # weitere entsteht.
            events = _build(candidates, default_signals())
            assert [event.photo_ids[0] for event in events] == [0, *sorted(starts)], combination


def _reference_time_and_day_events(candidates: Sequence[EventCandidate]) -> list[tuple[int, ...]]:
    """Im Test NACHGEBILDETE Referenz aus Zeitluecke plus Kalendertag.

    Bewusst nicht `assign_clusters`: das kennt die Tagesgrenze nicht und waere als Referenz
    schlicht falsch."""
    groups: list[list[int]] = []
    previous: datetime | None = None
    for candidate in sorted(candidates, key=lambda c: (c.taken_at, c.photo_id)):
        starts = (
            previous is None
            or candidate.taken_at - previous > TIME_CLUSTER_GAP
            or candidate.taken_at.isoformat()[:10] != previous.isoformat()[:10]
        )
        if starts:
            groups.append([])
        groups[-1].append(candidate.photo_id)
        previous = candidate.taken_at
    return [tuple(group) for group in groups]


class TestBackwardCompatibilityWithoutAnyCoordinate:
    """Traegt kein einziges Foto eine Ortsangabe, ist die Gliederung die reine Zeitluecken-
    Gliederung, zusaetzlich getrennt an jeder Kalendertagsgrenze."""

    def test_matches_the_reference_implementation(self) -> None:
        offsets = [0, 30, 61, 95, 400, 460, 461, 900, 1400, 1450]
        candidates = [
            _placeless_candidate(index, _at(minutes=offset))
            for index, offset in enumerate(offsets, start=1)
        ]

        events = _build(candidates, default_signals())

        assert [event.photo_ids for event in events] == _reference_time_and_day_events(candidates)

    def test_a_night_without_a_time_gap_now_separates(self) -> None:
        """Ausdruecklich NICHT "wie heute": die Tagesgrenze ist neu."""
        candidates = [
            _placeless_candidate(1, datetime(2026, 7, 20, 23, 59, 0)),
            _placeless_candidate(2, datetime(2026, 7, 21, 0, 1, 0)),
        ]

        assert len(_build(candidates, default_signals())) == 2


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

        [event] = _build(candidates)

        assert event.place_kind == "landmark"
        assert event.landmark_name == "Eiffelturm"
        assert (event.place_lat, event.place_lon) == (None, None)

    def test_an_event_carries_at_most_one_name(self) -> None:
        """Der chronologisch fruehste Name gewinnt - defensiv, denn das Trennsignal laesst einen
        zweiten Namen gar nicht erst in dasselbe Event."""
        candidates = [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, _at(minutes=1), landmark_name="Eiffelturm"),
        ]

        [event] = _build(candidates, [])

        assert event.landmark_name == "Eiffelturm"

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


class TestDefaultSignals:
    def test_carries_all_five_signal_classes(self) -> None:
        """Die Liste ist der Erweiterungspunkt (#427): ein neues Signal ist eine Klasse und ein
        Eintrag, kein Eingriff in den Durchlauf."""
        assert [type(signal) for signal in default_signals()] == [
            TimeGapSignal,
            DayBoundarySignal,
            StepDistanceSignal,
            ExtentSignal,
            LandmarkChangeSignal,
        ]

    def test_every_call_yields_fresh_state(self) -> None:
        """Signale sind zustandsbehaftet - eine geteilte Liste tarnte einen Lauf als Fortsetzung
        des vorherigen."""
        first = default_signals()
        second = default_signals()

        assert all(a is not b for a, b in zip(first, second, strict=True))

    def test_build_events_uses_them_by_default(self) -> None:
        candidates = [
            _measured_candidate(1, T0, landmark_name="Eiffelturm"),
            _measured_candidate(2, _at(minutes=1), landmark_name="Louvre"),
        ]

        assert len(_build(candidates)) == 2


class TestTheCorrectedTimeFeedsTheEventBoundaries:
    """specs/features/0426-zeitversatz-je-kamera.md: `build_events` bekommt seit ADR 0090 die
    KORRIGIERTE Zeit uebergeben und braucht deshalb KEINE eigene Korrekturlogik.

    Der Nachweis ist ein Datensatz, dessen Gliederung mit dem Versatz ANDERS ausfaellt als mit dem
    rohen Wert - liefe die Event-Bildung weiter auf der aufgezeichneten Zeit, zerrisse sie
    Aufnahmen desselben Moments, ohne dass eine Fehlermeldung erschiene."""

    def test_the_recorded_time_splits_what_the_corrected_time_keeps_together(self) -> None:
        offset = TIME_CLUSTER_GAP + timedelta(minutes=10)
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


def _span(event_id: int, start_minutes: int, end_minutes: int) -> EventSpan:
    """Eine Eventspanne relativ zu `T0`, in Minuten. Zonenlos wie `Photo.taken_at`."""
    return EventSpan(
        event_id=event_id,
        started_at=T0 + timedelta(minutes=start_minutes),
        ended_at=T0 + timedelta(minutes=end_minutes),
    )


class TestEventForTime:
    """`event_for_time` ordnet eine Aufnahmezeit einem Event zu - fuer die Fotos, die der Nutzer
    aufgenommen hat, ohne dass der Lauf ihnen eine Rangzeile gegeben haette.

    REIN, ohne Session und ohne Uhr: dieselbe Eingabe liefert immer dieselbe Zuordnung."""

    def test_a_time_inside_a_span_belongs_to_that_event(self) -> None:
        spans = [_span(7, 0, 60), _span(8, 120, 180)]

        assert event_for_time(spans, T0 + timedelta(minutes=30)) == 7

    def test_containment_beats_proximity(self) -> None:
        """Zusicherung 10: Eine Zeit KURZ VOR dem Ende eines langen Events gehoert diesem Event -
        auch wenn der Abstand zum `started_at` des naechsten kleiner ist als der zum eigenen
        `started_at`. Genau diesen Fall beantwortet eine Abstandsmessung allein gegen `started_at`
        falsch."""
        long_event = _span(1, 0, 600)
        following = _span(2, 610, 640)
        # 599 Minuten vom eigenen Anfang entfernt, aber nur 11 vom Anfang des naechsten.
        moment = T0 + timedelta(minutes=599)

        assert event_for_time([long_event, following], moment) == 1

    def test_both_bounds_are_inclusive(self) -> None:
        spans = [_span(3, 0, 60)]

        assert event_for_time(spans, T0) == 3
        assert event_for_time(spans, T0 + timedelta(minutes=60)) == 3

    def test_touching_spans_go_to_the_earlier_event(self) -> None:
        """Zusicherung 11: `ended_at(A) == started_at(B)` ist ueber zwei Aufnahmen derselben
        Sekunde mit Ortssprung erreichbar. Ohne diesen Fall haengt das Ergebnis an der
        Aufzaehlungsreihenfolge."""
        earlier = _span(1, 0, 60)
        later = _span(2, 60, 120)
        touching_moment = T0 + timedelta(minutes=60)

        assert event_for_time([earlier, later], touching_moment) == 1
        assert event_for_time([later, earlier], touching_moment) == 1

    def test_an_equal_distance_goes_to_the_earlier_event(self) -> None:
        """Zusicherung 12: Die Luecke zwischen den beiden Events ist symmetrisch - die Zeit liegt
        genau in ihrer Mitte."""
        earlier = _span(1, 0, 60)
        later = _span(2, 80, 140)
        middle = T0 + timedelta(minutes=70)

        assert event_for_time([earlier, later], middle) == 1
        assert event_for_time([later, earlier], middle) == 1

    def test_a_time_between_two_events_goes_to_the_nearer_one(self) -> None:
        earlier = _span(1, 0, 60)
        later = _span(2, 100, 160)

        assert event_for_time([earlier, later], T0 + timedelta(minutes=95)) == 2
        assert event_for_time([earlier, later], T0 + timedelta(minutes=65)) == 1

    def test_a_single_event_takes_every_time(self) -> None:
        spans = [_span(5, 100, 200)]

        assert event_for_time(spans, T0) == 5
        assert event_for_time(spans, T0 + timedelta(minutes=150)) == 5
        assert event_for_time(spans, T0 + timedelta(days=30)) == 5

    def test_a_time_before_the_first_and_after_the_last_event(self) -> None:
        spans = [_span(1, 0, 60), _span(2, 120, 180)]

        assert event_for_time(spans, T0 - timedelta(days=1)) == 1
        assert event_for_time(spans, T0 + timedelta(days=1)) == 2

    def test_an_empty_span_list_answers_none(self) -> None:
        assert event_for_time([], T0) is None

    def test_the_result_does_not_depend_on_the_order_of_the_spans(self) -> None:
        """Die Spannenliste kommt aus einer Abfrage - ihre Reihenfolge ist ohne `ORDER BY` nicht
        zugesichert. Jede Permutation muss dieselbe Zuordnung liefern."""
        spans = [_span(1, 0, 60), _span(2, 120, 180), _span(3, 300, 360)]
        moment = T0 + timedelta(minutes=200)

        for permutation in permutations(spans):
            assert event_for_time(list(permutation), moment) == 2


def _modules_building_a_cell(*, with_a_digit_literal: bool) -> dict[str, int]:
    """Je Quelldatei die Zahl der Stellen darin, die eine ORTSZELLE bilden.

    `with_a_digit_literal` trennt die beiden Faelle, um die es geht: `round(wert, 2) + 0.0` ist
    eine eigene Stellschraube und darf nirgends stehen, `round(wert, PLACE_CELL_DIGITS) + 0.0`
    ist die eine benannte.

    Gesucht wird die Signatur `round(<etwas>, <Zahlliteral>) + 0.0` - gezaehlt wird die FORM, nicht
    der Wert. Die Addition von `0.0` normalisiert `-0.0` und ist genau das, was aus einer beliebigen
    Rundung eine Zelle macht; ein blosses `round(wert, 3)` auf einen Qualitaetswert faellt dadurch
    nicht mit herein und soll es auch nicht.

    Eine Stelle, die heute zufaellig ebenfalls auf zwei Stellen rundet, ist genau der Fall, der bei
    der naechsten Aenderung der Koernung zurueckbleibt."""
    found: dict[str, int] = {}
    for path in sorted(SRC_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)):
                continue
            if not (isinstance(node.right, ast.Constant) and node.right.value == 0.0):
                continue
            call = node.left
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)):
                continue
            if call.func.id != "round" or len(call.args) < 2:
                continue
            digits = call.args[1]
            literal = isinstance(digits, ast.Constant) and isinstance(digits.value, int)
            if literal is with_a_digit_literal:
                name = path.relative_to(SRC_DIR).as_posix()
                found[name] = found.get(name, 0) + 1
    return found


class TestTheRoundingStandsAtExactlyOnePlace:
    """ADR 0102 Punkt 2: die Koernung der Ortszelle ist EINE benannte Konstante, nicht ueber den
    Code verteilt. Sie ist die Stellschraube der Sicherheitsentscheidung - wie grob gefragt und
    abgelegt wird, gehoert dorthin und nicht in die Bequemlichkeit einer Aufrufstelle.

    Ein Verhaltenstest roetete hier nichts: eine zweite, zufaellig gleich rundende Stelle liefert
    heute dieselben Werte und driftet erst bei der naechsten Aenderung ab. Die Zusage ist eine
    Aussage ueber eine ANZAHL und braucht deshalb einen strukturellen Waechter."""

    def test_the_old_constant_name_is_gone_from_the_source_tree(self) -> None:
        """`events.py::_EVENT_PLACE_COORDINATE_DIGITS` ist in `places.PLACE_CELL_DIGITS`
        aufgegangen. Bliebe der alte Name irgendwo stehen, gaebe es wieder zwei Stellschrauben."""
        hits = [
            path.relative_to(SRC_DIR).as_posix()
            for path in sorted(SRC_DIR.rglob("*.py"))
            if "_EVENT_PLACE_COORDINATE_DIGITS" in path.read_text(encoding="utf-8")
        ]

        assert hits == []

    def test_no_module_builds_a_cell_with_a_digit_literal_of_its_own(self) -> None:
        """Die Zusage aus ADR 0102 Punkt 2 in ihrer pruefbaren Form: nirgends im Quellbaum steht
        eine zweite Rundung mit STELLENLITERAL. Eine solche Stelle liefert heute dieselben Werte
        wie `place_cell` und bleibt bei der naechsten Aenderung der Koernung zurueck - lautlos."""
        assert _modules_building_a_cell(with_a_digit_literal=True) == {}

    def test_every_named_cell_rounding_lives_in_places(self) -> None:
        """Die Gegenprobe zum Fall darueber: ohne sie bestuende er auch dann, wenn der Walker gar
        nichts faende - etwa nach einer Umbenennung von `round`, einem Wegfall der
        `-0.0`-Normalisierung oder einem Umbau des Quellverzeichnisses.

        VIER Stellen in EINER Datei: zwei Zellrundungen mit je getrennter Breite und Laenge.
        `place_cell` ist die Koernung, mit der gefragt und abgelegt wird, `landmark_place_cell` die
        groebere, mit der eine Koordinate das System verlaesst (Spec 0469, S1). Beide tragen eine
        eigene benannte Konstante und stehen nebeneinander; die Zusage aus ADR 0102 Punkt 2 ist
        nicht "genau eine Rundung", sondern "keine mit Stellenliteral und keine ausserhalb dieses
        Moduls"."""
        assert _modules_building_a_cell(with_a_digit_literal=False) == {"places.py": 4}

    def test_the_guard_would_catch_a_second_rounding(self) -> None:
        """Mikrotest auf den Walker selbst, gegen einen ausgeschriebenen Verstoss - sonst belegt
        keiner der beiden Faelle oben, dass die Form ueberhaupt erkannt wird."""
        offender = ast.parse("cell = (round(lat, 2) + 0.0, round(lon, 2) + 0.0)")
        matches = [
            node
            for node in ast.walk(offender)
            if isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Add)
            and isinstance(node.right, ast.Constant)
            and node.right.value == 0.0
        ]

        assert len(matches) == 2


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

        [event] = _build(candidates)

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

    def test_a_landmark_event_gets_no_place_name_and_triggers_no_district(self) -> None:
        """Zwei Haelften in einem Fall: Das Landmark-Event bekaeme einen Namen (seine Zelle loest
        auf), bekommt aber keinen - und es loest bei dem gleichnamigen Nicht-Landmark-Event auch
        keine Viertel-Ergaenzung aus."""
        events = [
            _place_event(1, BERLIN, landmark_name="Brandenburger Tor"),
            _place_event(2, BERLIN_OST),
        ]
        infos = {BERLIN: _info("Berlin", "Mitte"), BERLIN_OST: _info("Berlin", "Kreuzberg")}

        assert assign_place_names(events, infos) == [None, "Berlin"]

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


# --- Die Trennursache (Spec 0506, ADR 0117 Punkt 4) ---------------------------------------------


def _explain(
    candidates: Sequence[EventCandidate], signals: list[BoundarySignal] | None = None
) -> EventFormation:
    """`explain_events` plus die Invarianten - jeder Fall dieser Sektion laeuft hierueber."""
    formation = explain_events(candidates, signals)
    assert_event_invariants(candidates, list(formation.events))
    assert len(formation.causes) == len(formation.events)
    assert formation.causes[0:1] in ((), (frozenset(),))
    # DIE TRAGENDE PRUEFFORM: Grenzen mit Ursache == Events - 1. Das erste Segment eines Laufs
    # traegt keine Ursache, jedes weitere genau eine Grenze.
    assert sum(1 for cause in formation.causes if cause) == max(len(formation.events) - 1, 0)
    return formation


class TestEverySignalCarriesAName:
    def test_the_default_set_uses_only_names_from_the_closed_stock(self) -> None:
        """Ein Signal ohne Namen aus dem Vorrat faellt in der Statistik unter den Tisch, ohne dass
        eine Summe kleiner wuerde - der Bericht waere dann still unvollstaendig."""
        names = [signal.name for signal in default_signals()]

        assert len(names) == len(set(names)), "zwei gleichnamige Signale sind eine Ursache"
        assert set(names) <= set(BOUNDARY_CAUSES)

    def test_the_forced_start_has_its_own_name_in_the_stock(self) -> None:
        """Der Motivwechsel ist kein Eintrag in `default_signals()` - er trennt trotzdem und
        braucht deshalb seinen Platz im Vorrat."""
        assert BOUNDARY_MOTIF_CHANGE in BOUNDARY_CAUSES
        assert BOUNDARY_MOTIF_CHANGE not in {signal.name for signal in default_signals()}


class TestTheCauseSetPerBoundary:
    def test_the_first_segment_carries_no_cause_even_when_a_signal_reports_one(self) -> None:
        """DIE AUSNAHME HAENGT AN DER POSITION, nicht an `TimeGapSignal`: Das eingeschleuste,
        IMMER trennende Signal meldet auch am ersten Foto, und die Menge bleibt trotzdem leer.
        Ohne diese Verankerung braucht jedes kuenftige Signal seine eigene Ausnahme."""
        candidates = [_placeless_candidate(index, _at(minutes=index)) for index in range(3)]

        formation = _explain(candidates, [_AlwaysSignal()])

        assert len(formation.events) == 3
        assert formation.causes == (frozenset(), frozenset({"immer"}), frozenset({"immer"}))

    def test_the_twin_empty_at_the_start_and_zeitluecke_at_the_second_boundary(self) -> None:
        """Der Zwilling in IDENTISCHER Lage: Dieselbe Zeitluecke, die am Index 0 keine Ursache
        ergibt, ergibt an der zweiten Grenze `zeitluecke`. Ohne diesen Fall truege jeder Lauf eine
        erfundene Zeitluecke in der Statistik."""
        gap = TIME_CLUSTER_GAP + timedelta(minutes=1)
        candidates = [_placeless_candidate(1, T0), _placeless_candidate(2, T0 + gap)]

        formation = _explain(candidates, [TimeGapSignal()])

        assert len(formation.events) == 2
        assert formation.causes == (frozenset(), frozenset({BOUNDARY_TIME_GAP}))

    def test_two_signals_at_the_same_boundary_yield_a_set_of_two(self) -> None:
        """Die Grenze traegt die MENGE, nie ein einzelnes Signal: Der Durchlauf wertet alle aus,
        und ein Bericht mit einer Ursache je Grenze unterschluege die zweite."""
        gap = TIME_CLUSTER_GAP + timedelta(minutes=1)
        far = GPS_CLUSTER_SPLIT_DISTANCE_METERS + EPSILON_METERS
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, T0 + gap, lat=_north(far)),
        ]

        formation = _explain(candidates, [TimeGapSignal(), StepDistanceSignal()])

        assert formation.causes[1] == frozenset({BOUNDARY_TIME_GAP, BOUNDARY_STEP})

    def test_a_forced_motif_start_is_its_own_cause(self) -> None:
        """Ein erzwungener Start ist eine Grenze wie jede andere und muss als solche gezaehlt
        werden - sonst stuende in Block B eine Grenze ohne Ursache."""
        pictures = [_picture("a")] * _window() + [_picture("b")] * _window()

        formation = _explain(_motif_candidates(pictures), [])

        assert len(formation.events) == 2
        assert BOUNDARY_MOTIF_CHANGE in formation.causes[1]

    def test_the_calendar_day_reports_under_its_own_name(self) -> None:
        """Der Ist-Zustand enthaelt heute die Kalendertagsgrenze; ohne ihren Namen im Vorrat waere
        die Ausgangsmessung nicht ehrlich."""
        candidates = [
            _placeless_candidate(1, datetime(2026, 7, 20, 23, 40)),
            _placeless_candidate(2, datetime(2026, 7, 21, 0, 10)),
        ]

        formation = _explain(candidates, [DayBoundarySignal()])

        assert formation.causes[1] == frozenset({BOUNDARY_CALENDAR_DAY})

    def test_the_landmark_change_reports_under_its_own_name(self) -> None:
        candidates = [
            _placeless_candidate(1, T0, landmark_name="Zugspitze"),
            _placeless_candidate(2, _at(seconds=1), landmark_name="Eibsee"),
        ]

        formation = _explain(candidates, [LandmarkChangeSignal()])

        assert formation.causes[1] == frozenset({BOUNDARY_LANDMARK})

    def test_the_extent_reports_under_its_own_name(self) -> None:
        far = EVENT_EXTENT_MAX_METERS + EPSILON_METERS
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(seconds=1), lat=_north(far)),
        ]

        formation = _explain(candidates, [ExtentSignal()])

        assert formation.causes[1] == frozenset({BOUNDARY_EXTENT})

    def test_a_run_without_any_candidate_has_neither_events_nor_causes(self) -> None:
        formation = _explain([])

        assert formation.events == ()
        assert formation.causes == ()

    def test_every_cause_of_a_full_signal_run_stays_inside_the_closed_stock(self) -> None:
        """Als Nachsatz ueber der ganzen Fallmenge, nicht als Einzelfall: Ein neues Signal ohne
        Eintrag im Vorrat wird hier rot, nicht erst im Bericht."""
        gap = TIME_CLUSTER_GAP + timedelta(minutes=1)
        far = GPS_CLUSTER_SPLIT_DISTANCE_METERS + EPSILON_METERS
        candidates = [
            _measured_candidate(1, T0, landmark_name="Zugspitze"),
            _measured_candidate(2, _at(seconds=1), landmark_name="Eibsee"),
            _measured_candidate(3, T0 + gap, lat=_north(far)),
            _measured_candidate(4, datetime(2026, 7, 21, 9, 0)),
        ]

        formation = _explain(candidates)

        for cause in formation.causes:
            assert cause <= set(BOUNDARY_CAUSES)


class TestBuildEventsAndTheExplainingFormAreTheSameRun:
    """Ein zweiter Rechenweg fuer dieselbe Gliederung liefe auseinander - und dann maesse Block B
    die Grenzen einer Gliederung, die so nie entstanden ist."""

    def test_the_same_candidates_yield_the_same_events(self) -> None:
        gap = TIME_CLUSTER_GAP + timedelta(minutes=1)
        candidates = [
            _measured_candidate(1, T0),
            _measured_candidate(2, _at(seconds=30)),
            _measured_candidate(3, T0 + gap),
        ]

        assert list(explain_events(candidates).events) == build_events(candidates)


class TestTheMotifRuleTakesItsTwoFestlegungenInjectably:
    """Fensterlaenge und Praesenzgrenze sind INJIZIERBAR - die Voraussetzung dafuer, dass die
    Empfindlichkeitsmessung (Spec 0506, Block E) den ECHTEN Rechenweg variiert statt eine
    Nachbildung zu messen.

    Ohne Angabe gilt weiterhin der Betriebswert, und zwar als MODULATTRIBUT gelesen: Ein
    Default-Parameterwert in der Signatur baende ihn beim Import, `monkeypatch.setattr` liefe ins
    Leere und die Variation waere wirkungslos - gruen, aber ohne Wirkung.

    Die Staerken dieser Faelle sind FREI GEWAEHLT und stehen zu `MOTIF_PRESENCE_THRESHOLD` in
    keinem Verhaeltnis: Jeder Fall gibt die Grenze, gegen die er misst, selbst mit."""

    _CARRIED = 1.0
    _MIDDLE = 0.8
    _ABSENT = 0.0

    def _sequence(self, length: int) -> list[EventCandidate]:
        """Ein Bezugsfoto, dann `length` Fotos, in denen "b" mit mittlerer Staerke dazukommt.

        Ob daraus ein Wechsel wird, entscheidet allein die mitgegebene Grenze; wie viele Fotos ihn
        bestaetigen muessen, allein die mitgegebene Fensterlaenge."""
        reference = {"a": self._CARRIED, "b": self._ABSENT}
        deviating = {"a": self._CARRIED, "b": self._MIDDLE}
        return _motif_candidates([reference, *([deviating] * length)])

    def test_the_window_length_comes_from_the_argument_not_from_the_constant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die Modulkonstante steht auf einem Wert, unter dem die Folge NICHT bestaetigt - und das
        Argument setzt sich durch. Andersherum bliebe der Fall auch dann gruen, wenn das Argument
        gar nicht gelesen wird."""
        monkeypatch.setattr(events_module, "MOTIF_CHANGE_CONFIRMING_PHOTOS", 5)
        candidates = self._sequence(2)

        assert motif_change_starts(candidates, motif_presence_threshold=self._MIDDLE) == frozenset()
        assert motif_change_starts(
            candidates, confirming_photos=2, motif_presence_threshold=self._MIDDLE
        ) == frozenset({1})

    def test_the_presence_threshold_comes_from_the_argument_too(self) -> None:
        """Dieselbe Folge, dieselbe Fensterlaenge, nur die Grenze wandert: Ueber der mittleren
        Staerke traegt kein Foto "b", und es gibt gar keinen Wechsel."""
        candidates = self._sequence(2)

        assert motif_change_starts(
            candidates, confirming_photos=2, motif_presence_threshold=self._MIDDLE
        ) == frozenset({1})
        assert (
            motif_change_starts(
                candidates, confirming_photos=2, motif_presence_threshold=self._CARRIED
            )
            == frozenset()
        )

    def test_without_arguments_the_module_attributes_apply(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Der Zwilling gegen einen gebundenen Default: Das verschobene Modulattribut MUSS wirken,
        sonst ist die Konstante beim Import eingefroren."""
        candidates = self._sequence(4)
        monkeypatch.setattr(events_module, "MOTIF_CHANGE_CONFIRMING_PHOTOS", 2)

        with_two = motif_change_starts(candidates)

        monkeypatch.setattr(events_module, "MOTIF_CHANGE_CONFIRMING_PHOTOS", 5)
        with_five = motif_change_starts(candidates)

        assert with_two != with_five
        assert with_five == motif_change_starts(candidates, confirming_photos=5)

    def test_the_operating_point_is_unchanged_by_the_new_parameters(self) -> None:
        """KEINE VERHALTENSAENDERUNG am unveraenderten Wert - die Zusage, unter der diese
        Injizierbarkeit ueberhaupt eingebaut werden durfte. Geprueft ueber eine Folge, die unter
        den Betriebswerten tatsaechlich trennt: eine Folge ohne jeden Start waere hier
        vakuum-gruen."""
        candidates = self._sequence(events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS)
        threshold = MOTIF_PRESENCE_THRESHOLD

        assert motif_change_starts(candidates) == motif_change_starts(
            candidates,
            confirming_photos=events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS,
            motif_presence_threshold=threshold,
        )
        assert motif_change_starts(candidates) == frozenset({1})

    def test_the_explaining_form_hands_both_through(self) -> None:
        """`explain_events` reicht beide weiter - sonst kann die Messung die Gliederung nicht
        variieren und misst unter jeder Kombination dieselben Zahlen."""
        candidates = self._sequence(2)

        narrow = explain_events(
            candidates, confirming_photos=2, motif_presence_threshold=self._MIDDLE
        )
        wide = explain_events(
            candidates, confirming_photos=5, motif_presence_threshold=self._MIDDLE
        )

        assert len(narrow.events) == 2
        assert narrow.causes[1] == frozenset({BOUNDARY_MOTIF_CHANGE})
        assert len(wide.events) == 1

    def test_the_explaining_form_without_arguments_is_the_run_itself(self) -> None:
        candidates = self._sequence(events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS)

        assert explain_events(candidates) == explain_events(
            candidates,
            confirming_photos=events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS,
            motif_presence_threshold=MOTIF_PRESENCE_THRESHOLD,
        )


class TestTheMinimumSegmentSizeIsAnInequalityNotANumber:
    def test_a_segment_of_one_photo_is_below_it(self) -> None:
        """Die einzige zulaessige Aussage ueber diesen Zahlwert, und sie ist eine Ungleichung: Bei
        `1` waere kein Segment je zu klein, und die Messung in Block B stuende dauerhaft auf
        null."""
        assert events_module.MIN_EVENT_PHOTOS >= 2


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
