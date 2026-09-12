from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from photosort.events import (
    EVENT_EXTENT_MAX_METERS,
    BoundarySignal,
    BuiltEvent,
    DayBoundarySignal,
    EffectiveLocation,
    EventCandidate,
    ExtentSignal,
    LandmarkChangeSignal,
    LocationEntry,
    StepDistanceSignal,
    TimeGapSignal,
    build_events,
    default_signals,
    infer_locations,
)
from photosort.scoring import (
    GPS_CLUSTER_SPLIT_DISTANCE_METERS,
    TIME_CLUSTER_GAP,
    haversine_meters,
)

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
) -> EventCandidate:
    """Ein Kandidat mit EIGENER, gemessener Koordinate."""
    return EventCandidate(
        photo_id=photo_id,
        taken_at=taken_at,
        location=EffectiveLocation(lat=lat, lon=lon, inferred=False),
        gps_lat=lat,
        gps_lon=lon,
        landmark_name=landmark_name,
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
    """specs/features/0426-zeitversatz-je-kamera.md: `build_events` bekommt seit ADR 0089 die
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
