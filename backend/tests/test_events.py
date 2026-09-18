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
    BOUNDARY_CAUSES,
    BOUNDARY_DURATION,
    BOUNDARY_EXTENT,
    BOUNDARY_LANDMARK,
    BOUNDARY_MOTIF_CHANGE,
    BOUNDARY_STEP,
    BOUNDARY_TIME_GAP,
    UNBREAKABLE_CAUSES,
    BoundarySignal,
    BuiltEvent,
    EffectiveLocation,
    EventCandidate,
    EventFormation,
    EventMergeError,
    EventSpan,
    EventSpanSignal,
    ExtentSignal,
    LandmarkChangeSignal,
    LocationEntry,
    MergeOutcome,
    Segment,
    StepDistanceSignal,
    TimeGapSignal,
    assign_place_names,
    build_events,
    default_signals,
    event_for_time,
    explain_events,
    infer_locations,
    inherited_locations,
    merge_small_segments,
    motif_change_starts,
)
from photosort.places import MAX_PLACE_NAME_LENGTH, PlaceInfo
from photosort.scoring import haversine_meters
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

# "kein Segment ist je zu klein" - damit bleibt Stufe 3 wirkungslos. JEDER Fall, der ein Signal oder
# die Motivregel zum Gegenstand hat, laeuft damit: Sonst liefe er STILL durch das Zusammenlegen
# hindurch, und seine erwartete Gliederung haette eine zweite, ungenannte Ursache. Die Stufe selbst
# hat ihre eigenen Faelle (`TestTheThirdStage*`, `TestBuildEventsRunsTheThirdStage`).
_NO_MERGING = 1


def _time_gap() -> timedelta:
    """Die geltende Zeitluecken-Schwelle - als MODULATTRIBUT gelesen, nie als Zahl."""
    return events_module.EVENT_TIME_GAP


def _step_max() -> float:
    """Die geltende Schritt-Schwelle - als Modulattribut gelesen."""
    return events_module.EVENT_STEP_MAX_METERS


def _extent_max() -> float:
    """Die geltende Ausdehnungs-Schwelle - als Modulattribut gelesen."""
    return events_module.EVENT_EXTENT_MAX_METERS


def _max_span() -> timedelta:
    """Die geltende Dauergrenze - als Modulattribut gelesen."""
    return events_module.EVENT_MAX_SPAN


def _merge_gap() -> timedelta:
    """Die geltende Ueberbrueckungsgrenze von Stufe 3 - als Modulattribut gelesen."""
    return events_module.MERGE_MAX_GAP


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


# Zeitluecke, Schritt, Ausdehnung, Dauergrenze, Ueberbrueckung, Mindestgroesse. `None` ist der
# Betriebssatz. Jeder weitere Satz haelt die drei zulaessigen Ungleichungen ein
# (`MERGE_MAX_GAP > EVENT_TIME_GAP`, `MIN_EVENT_PHOTOS >= 2`, `EVENT_MAX_SPAN < 24 h`) und laesst
# `EPSILON_METERS`/`EPSILON_TIME` klein gegen jede seiner Schwellen.
_SHIFTED_CONSTANT_SETS: tuple[tuple[object, ...] | None, ...] = (
    None,
    (timedelta(hours=3), 1500.0, 4000.0, timedelta(hours=20), timedelta(hours=5), 3),
    (timedelta(minutes=10), 300.0, 600.0, timedelta(hours=2), timedelta(minutes=25), 2),
)

_SHIFTED_CONSTANT_NAMES = (
    "EVENT_TIME_GAP",
    "EVENT_STEP_MAX_METERS",
    "EVENT_EXTENT_MAX_METERS",
    "EVENT_MAX_SPAN",
    "MERGE_MAX_GAP",
    "MIN_EVENT_PHOTOS",
)


class _UnderShiftedEventConstants:
    """Jeder Fall einer erbenden Klasse laeuft unter MEHREREN Saetzen der sechs Schwellen.

    Die sechs sind aenderbare, unkalibrierte Festlegungen; kein Fall darf ihren Zahlwert pinnen.
    Die Faelle bauen ihre Lage deshalb aus `_time_gap()`, `_step_max()`, `_extent_max()`,
    `_max_span()` und `_merge_gap()` statt aus einer Zahl, und diese Fixture setzt die
    Modulkonstanten auf jeden Satz der Liste. Ein Fall, der einen Zahlwert doch spiegelt, wird unter
    mindestens einem Parameter rot - hier, und nicht erst bei der naechsten Kalibrierung.

    VORAUSSETZUNG, die still braeche: Die Konstanten werden im Code wie im Test als MODULATTRIBUT
    gelesen. Ein `from ... import` baende den Wert beim Import, und die Fixture liefe ins Leere."""

    @pytest.fixture(autouse=True, params=_SHIFTED_CONSTANT_SETS)
    def _event_constants(
        self, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        if request.param is None:
            return
        for name, value in zip(_SHIFTED_CONSTANT_NAMES, request.param, strict=True):
            monkeypatch.setattr(events_module, name, value)


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


def assert_full_signal_invariants(
    candidates: Sequence[EventCandidate], events: Sequence[BuiltEvent]
) -> None:
    """Die beiden Zusagen ueber jede Event-Folge aus dem VOLLEN Signalsatz: kein Event ueber
    `EVENT_MAX_SPAN`, keines ueber `EVENT_EXTENT_MAX_METERS` - weder als Ergebnis des Durchlaufs
    noch als Ergebnis des Zusammenlegens.

    Als Nachsatz ueber der ganzen Fallmenge, nicht als Einzelfall. Nur fuer den vollen Satz: Eine
    injizierte Teilmenge kennt die beiden Riegel nicht und darf sie ueberschreiten."""
    location_by_id = {candidate.photo_id: candidate.location for candidate in candidates}
    for event in events:
        assert event.ended_at - event.started_at <= _max_span()
        located = [
            location
            for photo_id in event.photo_ids
            if (location := location_by_id[photo_id]) is not None
        ]
        if not located:
            continue
        diagonal = haversine_meters(
            min(location.lat for location in located),
            min(location.lon for location in located),
            max(location.lat for location in located),
            max(location.lon for location in located),
        )
        assert diagonal <= _extent_max()


def _is_the_full_signal_set(signals: list[BoundarySignal] | None) -> bool:
    if signals is None:
        return True
    return [type(signal) for signal in signals] == [type(signal) for signal in default_signals()]


def _build(
    candidates: Sequence[EventCandidate],
    signals: list[BoundarySignal] | None = None,
    *,
    min_event_photos: int | None = _NO_MERGING,
) -> list[BuiltEvent]:
    """`build_events` plus die Invarianten - jeder Fall dieser Datei laeuft hierueber.

    `min_event_photos` steht VORGABEWEISE auf `_NO_MERGING`: Ein Fall ueber ein Signal soll genau
    dieses Signal messen. Wer Stufe 3 zum Gegenstand hat, gibt `None` (Betriebswert) oder einen
    eigenen Wert mit."""
    events = build_events(candidates, signals, min_event_photos=min_event_photos)
    assert_event_invariants(candidates, events)
    if _is_the_full_signal_set(signals):
        assert_full_signal_invariants(candidates, events)
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
        step = (_extent_max() - EPSILON_METERS) / (_window() - 1)
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
        after_the_gap = T0 + _time_gap() + 2 * EPSILON_TIME
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

    def test_a_window_spanning_midnight_keeps_the_motif_boundary_and_nothing_else(self) -> None:
        """Der rueckwirkende Beginn liegt auf dem VORTAG, das bestaetigende Foto dahinter.

        Die MOTIVGRENZE entsteht - und sonst keine: Die Mitternachtsgrenze allein trennt nicht
        mehr, das zweite Event laeuft ueber sie hinweg. Braucht `default_signals()`, weil genau
        dieser Satz die Dauergrenze anstelle des Kalendertags fuehrt."""
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

        assert [event.photo_ids for event in events] == [(0, 1), tuple(range(2, _window() + 2))]
        assert events[1].started_at.date() != events[1].ended_at.date()

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
            EventSpanSignal,
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
    candidates: Sequence[EventCandidate],
    signals: list[BoundarySignal] | None = None,
    *,
    min_event_photos: int | None = _NO_MERGING,
) -> EventFormation:
    """`explain_events` plus die Invarianten - jeder Fall dieser Sektion laeuft hierueber.

    Wie `_build` mit abgeschaltetem Zusammenlegen: Ein Fall ueber die URSACHENMENGE misst die
    Grenzen des Durchlaufs, nicht die, die Stufe 3 davon uebriglaesst."""
    formation = explain_events(candidates, signals, min_event_photos=min_event_photos)
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
        gap = _time_gap() + EPSILON_TIME
        candidates = [_placeless_candidate(1, T0), _placeless_candidate(2, T0 + gap)]

        formation = _explain(candidates, [TimeGapSignal()])

        assert len(formation.events) == 2
        assert formation.causes == (frozenset(), frozenset({BOUNDARY_TIME_GAP}))

    def test_two_signals_at_the_same_boundary_yield_a_set_of_two(self) -> None:
        """Die Grenze traegt die MENGE, nie ein einzelnes Signal: Der Durchlauf wertet alle aus,
        und ein Bericht mit einer Ursache je Grenze unterschluege die zweite."""
        gap = _time_gap() + EPSILON_TIME
        far = _step_max() + EPSILON_METERS
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

    def test_the_duration_reports_under_its_own_name(self) -> None:
        """Die Dauergrenze ist an die Stelle des Kalendertags getreten; ohne ihren Namen im Vorrat
        stuende in Block B eine Grenze ohne Ursache."""
        candidates = [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, T0 + _max_span() + EPSILON_TIME),
        ]

        formation = _explain(candidates, [EventSpanSignal()])

        assert formation.causes[1] == frozenset({BOUNDARY_DURATION})

    def test_the_landmark_change_reports_under_its_own_name(self) -> None:
        candidates = [
            _placeless_candidate(1, T0, landmark_name="Zugspitze"),
            _placeless_candidate(2, _at(seconds=1), landmark_name="Eibsee"),
        ]

        formation = _explain(candidates, [LandmarkChangeSignal()])

        assert formation.causes[1] == frozenset({BOUNDARY_LANDMARK})

    def test_the_extent_reports_under_its_own_name(self) -> None:
        far = _extent_max() + EPSILON_METERS
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
        gap = _time_gap() + EPSILON_TIME
        far = _step_max() + EPSILON_METERS
        candidates = [
            _measured_candidate(1, T0, landmark_name="Zugspitze"),
            _measured_candidate(2, _at(seconds=1), landmark_name="Eibsee"),
            _measured_candidate(3, T0 + gap, lat=_north(far)),
            _placeless_candidate(4, T0 + gap + _max_span() + EPSILON_TIME),
        ]

        formation = _explain(candidates)

        for cause in formation.causes:
            assert cause <= set(BOUNDARY_CAUSES)


class TestBuildEventsAndTheExplainingFormAreTheSameRun:
    """Ein zweiter Rechenweg fuer dieselbe Gliederung liefe auseinander - und dann maesse Block B
    die Grenzen einer Gliederung, die so nie entstanden ist."""

    def test_the_same_candidates_yield_the_same_events(self) -> None:
        gap = _time_gap() + EPSILON_TIME
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


class TestTheThreeAdmissibleStatementsAboutTheNumbers:
    """Die EINZIGEN drei Aussagen, die ein Test ueber die sechs Zahlwerte treffen darf - und alle
    drei sind Ungleichungen. Jede vierte waere eine Spiegelung des Codes und machte die naechste
    Kalibrierung zu einem Testumbau."""

    def test_a_segment_of_one_photo_is_below_the_minimum(self) -> None:
        """Bei `1` waere kein Segment je zu klein, Stufe 3 bliebe wirkungslos, und die Messung in
        Block B stuende dauerhaft auf null."""
        assert events_module.MIN_EVENT_PHOTOS >= 2

    def test_the_merge_gap_reaches_beyond_the_time_gap(self) -> None:
        """Waere sie nicht groesser, koennte Stufe 3 keine einzige Zeitluecken-Grenze aufloesen -
        die Stufe liefe, ohne je etwas zu tun."""
        assert events_module.MERGE_MAX_GAP > events_module.EVENT_TIME_GAP

    def test_the_maximum_span_stays_below_a_day(self) -> None:
        """Die Vorbedingung der Ueberschriftenform `23:40-01:15 Uhr`: Ab einem Tag waere die
        Spanne ohne Datumsangabe mehrdeutig."""
        assert events_module.EVENT_MAX_SPAN < timedelta(hours=24)


# --- Stufe 3: das Zusammenlegen zu kleiner Segmente (Spec 0506, ADR 0117 Punkt 3) ----------------


def _members(
    first_id: int, offsets: Sequence[timedelta], meters_north: float | None
) -> tuple[EventCandidate, ...]:
    """`meters_north=None` heisst "ganz ohne Ort" - die Lage, in der die Entfernung ueber eine
    Kante unbestimmbar ist."""
    if meters_north is None:
        return tuple(
            _placeless_candidate(first_id + index, T0 + offset)
            for index, offset in enumerate(offsets)
        )
    return tuple(
        _measured_candidate(first_id + index, T0 + offset, lat=_north(meters_north))
        for index, offset in enumerate(offsets)
    )


def _tiny(
    offset: timedelta,
    *,
    first_id: int,
    causes: Collection[str] = (),
    meters_north: float | None = 0.0,
) -> Segment:
    """Ein Segment aus EINEM Foto - unter jeder zulaessigen Mindestgroesse (`>= 2`)."""
    return Segment(members=_members(first_id, [offset], meters_north), causes=frozenset(causes))


def _normal_from(
    start: timedelta,
    *,
    first_id: int,
    causes: Collection[str] = (),
    meters_north: float | None = 0.0,
) -> Segment:
    """Genau `MIN_EVENT_PHOTOS` Fotos ab `start`, dicht beieinander.

    Die GROESSE kommt aus dem Symbol, nicht aus einer Zahl: Unter einer anderen Mindestgroesse
    waere ein fest zweielementiges Nachbarsegment selbst zu klein und zoege sich in den Fall
    hinein, den der Fall gar nicht misst."""
    offsets = [start + index * EPSILON_TIME for index in range(events_module.MIN_EVENT_PHOTOS)]
    return Segment(members=_members(first_id, offsets, meters_north), causes=frozenset(causes))


def _normal_until(
    end: timedelta,
    *,
    first_id: int,
    causes: Collection[str] = (),
    meters_north: float | None = 0.0,
) -> Segment:
    """Genau `MIN_EVENT_PHOTOS` Fotos, das LETZTE bei `end`, die uebrigen dicht davor."""
    minimum = events_module.MIN_EVENT_PHOTOS
    offsets = [end - (minimum - 1 - index) * EPSILON_TIME for index in range(minimum)]
    return Segment(members=_members(first_id, offsets, meters_north), causes=frozenset(causes))


def _normal_spanning_the_maximum(first_id: int) -> Segment:
    """Genau `MIN_EVENT_PHOTOS` Fotos, die zusammen GENAU `EVENT_MAX_SPAN` ueberspannen - das
    Segment, neben dem jeder weitere Zuwachs die Dauergrenze reisst."""
    minimum = events_module.MIN_EVENT_PHOTOS
    offsets = [_max_span() * index / (minimum - 1) for index in range(minimum)]
    return Segment(members=_members(first_id, offsets, 0.0), causes=frozenset())


def _ids(outcome: MergeOutcome) -> list[tuple[int, ...]]:
    return [tuple(member.photo_id for member in segment.members) for segment in outcome.segments]


def _block(first_id: int) -> tuple[int, ...]:
    """Die Foto-Ids eines Segments aus `_normal_from`/`_normal_until`."""
    return tuple(range(first_id, first_id + events_module.MIN_EVENT_PHOTOS))


class TestTheThirdStageChoosesItsNeighbour(_UnderShiftedEventConstants):
    """Die drei Tie-Break-Stufen, je an einem eigens GEBAUTEN Gleichstand: kleinere Zeitluecke,
    bei Gleichstand kleinere Entfernung, danach der fruehere. Nur angrenzende Segmente."""

    def _three(
        self,
        *,
        gap_before: timedelta,
        gap_after: timedelta,
        meters_before: float = 0.0,
        meters_after: float = 0.0,
    ) -> list[Segment]:
        """Zwei normal grosse Segmente und dazwischen eines aus EINEM Foto."""
        middle = _merge_gap()
        return [
            _normal_until(middle - gap_before, first_id=1, meters_north=meters_before),
            _tiny(middle, first_id=10, causes={BOUNDARY_TIME_GAP}),
            _normal_from(
                middle + gap_after,
                first_id=20,
                causes={BOUNDARY_TIME_GAP},
                meters_north=meters_after,
            ),
        ]

    def test_the_smaller_time_gap_wins(self) -> None:
        outcome = merge_small_segments(
            self._three(gap_before=EPSILON_TIME, gap_after=2 * EPSILON_TIME)
        )

        assert _ids(outcome) == [(*_block(1), 10), _block(20)]

    def test_the_smaller_time_gap_wins_the_other_way_round_too(self) -> None:
        """Der Spiegelfall - ohne ihn bliebe offen, ob die Wahl die Zeitluecke liest oder nur
        immer den frueheren nimmt."""
        outcome = merge_small_segments(
            self._three(gap_before=2 * EPSILON_TIME, gap_after=EPSILON_TIME)
        )

        assert _ids(outcome) == [_block(1), (10, *_block(20))]

    def test_at_an_equal_gap_the_smaller_distance_wins(self) -> None:
        near = _extent_max() / 4
        outcome = merge_small_segments(
            self._three(
                gap_before=EPSILON_TIME,
                gap_after=EPSILON_TIME,
                meters_before=near,
                meters_after=2 * near,
            )
        )

        assert _ids(outcome) == [(*_block(1), 10), _block(20)]

    def test_at_an_equal_gap_the_smaller_distance_wins_the_other_way_round_too(self) -> None:
        near = _extent_max() / 4
        outcome = merge_small_segments(
            self._three(
                gap_before=EPSILON_TIME,
                gap_after=EPSILON_TIME,
                meters_before=2 * near,
                meters_after=near,
            )
        )

        assert _ids(outcome) == [_block(1), (10, *_block(20))]

    def test_at_an_equal_gap_and_an_equal_distance_the_earlier_wins(self) -> None:
        """Die dritte Stufe macht die Regel TOTAL - ohne sie haenge das Ergebnis an der
        Iterationsreihenfolge."""
        outcome = merge_small_segments(self._three(gap_before=EPSILON_TIME, gap_after=EPSILON_TIME))

        assert _ids(outcome) == [(*_block(1), 10), _block(20)]

    def test_a_neighbour_without_a_coordinate_wins_no_tie(self) -> None:
        """Eine unbestimmbare Entfernung zaehlt als groesstmoegliche: Ein Nachbar, ueber den nichts
        bekannt ist, gewinnt keinen Gleichstand. Er bleibt zulaessig - nur eben nicht bevorzugt."""
        middle = _merge_gap()
        segments = [
            _normal_until(middle - EPSILON_TIME, first_id=1, meters_north=None),
            _tiny(middle, first_id=10, causes={BOUNDARY_TIME_GAP}),
            _normal_from(middle + EPSILON_TIME, first_id=20, causes={BOUNDARY_TIME_GAP}),
        ]

        outcome = merge_small_segments(segments)

        assert _ids(outcome) == [_block(1), (10, *_block(20))]


class TestTheFourBoltsAgainstOverMerging(_UnderShiftedEventConstants):
    """Vier Riegel, JE EINZELN: In jedem Fall greift genau einer, die anderen drei halten. Nur so
    steht fest, dass jeder von ihnen fuer sich traegt."""

    def test_all_four_holding_is_the_control_case(self) -> None:
        """Der ROT-ANKER: Dieselbe Lage ohne Verletzung wird tatsaechlich zusammengelegt. Ohne ihn
        bestuenden die vier Faelle darunter auch dann, wenn nie etwas zusammengelegt wuerde."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        assert _ids(merge_small_segments(segments)) == [(*_block(1), 10)]

    def test_bolt_a_the_gap_to_the_neighbour_exceeds_the_merge_gap(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(_merge_gap() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        assert _ids(merge_small_segments(segments)) == [_block(1), (10,)]

    def test_bolt_b_the_duration_of_the_result_exceeds_the_maximum_span(self) -> None:
        """Die Zeitluecke zum Nachbarn bleibt dabei UNTER `MERGE_MAX_GAP` - Riegel (a) haelt, und
        allein die Dauer des Ergebnisses sperrt."""
        segments = [
            _normal_spanning_the_maximum(first_id=1),
            _tiny(_max_span() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        assert _ids(merge_small_segments(segments)) == [_block(1), (10,)]

    def test_bolt_c_the_extent_of_the_result_exceeds_the_maximum_extent(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1, meters_north=0.0),
            _tiny(
                EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_TIME_GAP},
                meters_north=_extent_max() + EPSILON_METERS,
            ),
        ]

        assert _ids(merge_small_segments(segments)) == [_block(1), (10,)]

    def test_bolt_d_a_segment_at_the_minimum_is_never_absorbed(self) -> None:
        """Ein normal grosses Event wird NIE zugeschlagen, auch wenn Zeit, Dauer und Ausdehnung es
        zuliessen - die uebrigen drei Riegel halten hier alle."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _normal_from(EPSILON_TIME, first_id=100, causes={BOUNDARY_TIME_GAP}),
        ]

        outcome = merge_small_segments(segments)

        assert _ids(outcome) == [_block(1), _block(100)]
        assert outcome.dissolved_boundaries == 0


class TestTheTwoUntouchableBoundaries(_UnderShiftedEventConstants):
    """Eine Grenze, deren Ursachenmenge `motivwechsel` oder `sehenswuerdigkeit` enthaelt, wird NIE
    aufgeloest - auch nicht, wenn beide Nachbarn alle vier Riegel erfuellen und das Segment aus
    einem einzigen Foto besteht."""

    def _enclosed(self, causes: Collection[str]) -> list[Segment]:
        return [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes=causes),
            _normal_from(2 * EPSILON_TIME, first_id=20, causes=causes),
        ]

    @pytest.mark.parametrize("cause", sorted(UNBREAKABLE_CAUSES))
    def test_a_single_photo_between_two_untouchable_boundaries_stays_alone(
        self, cause: str
    ) -> None:
        outcome = merge_small_segments(self._enclosed({cause}))

        assert _ids(outcome) == [_block(1), (10,), _block(20)]
        assert outcome.dissolved_boundaries == 0
        assert outcome.moved_photo_ids == frozenset()

    def test_the_same_lage_with_a_dissolvable_cause_is_merged(self) -> None:
        """Der ROT-ANKER zu den beiden Faellen darueber: Es liegt an der URSACHE, nicht an der
        Lage."""
        outcome = merge_small_segments(self._enclosed({BOUNDARY_TIME_GAP}))

        assert outcome.dissolved_boundaries == 1

    def test_the_stock_of_untouchable_causes_is_exactly_these_two(self) -> None:
        """Sie sind die einzigen Signale, die zwei Anlaesse AM SELBEN ORT ZUR SELBEN ZEIT trennen.
        Ein dritter Eintrag hier waere eine stille Ausweitung der Sperre."""
        assert UNBREAKABLE_CAUSES == frozenset({BOUNDARY_MOTIF_CHANGE, BOUNDARY_LANDMARK})
        assert UNBREAKABLE_CAUSES <= set(BOUNDARY_CAUSES)

    def test_an_untouchable_cause_inside_a_set_of_two_still_blocks(self) -> None:
        """Die Grenze traegt eine MENGE. Eine Pruefung auf Gleichheit statt auf Enthaltensein
        liesse jede Doppelgrenze durch."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP, BOUNDARY_MOTIF_CHANGE}),
        ]

        assert _ids(merge_small_segments(segments)) == [_block(1), (10,)]


class TestTheThirdStageComesToAStandstill(_UnderShiftedEventConstants):
    """Der Stillstand, maschinenpruefbar - nicht als Behauptung ueber den Ablauf."""

    def _a_blocked_and_a_mergeable_segment(self) -> list[Segment]:
        """Ein Einzelfoto, dessen EINZIGE Kante unantastbar ist (es bleibt gesperrt), davor - und
        danach ein zweites Einzelfoto, das zugeschlagen werden darf."""
        return [
            _tiny(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_MOTIF_CHANGE}),
            _normal_from(2 * EPSILON_TIME, first_id=20, causes={BOUNDARY_TIME_GAP}),
        ]

    def test_a_blocked_segment_does_not_stall_the_rest(self) -> None:
        """Ohne den Zusatz "nicht bereits gesperrt" waehlte jede Runde dasselbe gescheiterte
        Segment erneut, und das zusammenlegbare daneben bliebe unbehandelt."""
        outcome = merge_small_segments(self._a_blocked_and_a_mergeable_segment())

        assert _ids(outcome) == [(1,), (10, *_block(20))]

    def test_the_outcome_is_idempotent(self) -> None:
        """Die maschinenpruefbare Form des Stillstands: Ein zweiter Durchgang aendert nichts
        mehr."""
        once = merge_small_segments(self._a_blocked_and_a_mergeable_segment())
        twice = merge_small_segments(once.segments)

        assert twice.segments == once.segments
        assert twice.dissolved_boundaries == 0
        assert twice.moved_photo_ids == frozenset()

    def test_each_dissolved_boundary_costs_exactly_one_segment(self) -> None:
        """Die je Zusammenlegung strikt fallende Segmentzahl, als Bilanz statt als Behauptung."""
        segments = self._a_blocked_and_a_mergeable_segment()

        outcome = merge_small_segments(segments)

        assert len(outcome.segments) == len(segments) - outcome.dissolved_boundaries
        assert outcome.dissolved_boundaries >= 1

    def test_a_chain_of_tiny_segments_collapses_completely(self) -> None:
        """Ein zusammengelegtes Ergebnis, das noch immer zu klein ist, wird weiter zugeschlagen -
        und ein Foto zaehlt dabei trotzdem nur EINMAL als bewegt."""
        count = 2 * events_module.MIN_EVENT_PHOTOS + 1
        segments = [
            _tiny(
                index * EPSILON_TIME,
                first_id=index,
                causes=() if index == 0 else {BOUNDARY_TIME_GAP},
            )
            for index in range(count)
        ]

        outcome = merge_small_segments(segments)

        assert _ids(outcome) == [tuple(range(count))]
        assert outcome.dissolved_boundaries == count - 1
        assert len(outcome.moved_photo_ids) < count, "ein Foto wechselt hoechstens einmal"

    def test_an_empty_run_is_no_special_case(self) -> None:
        outcome = merge_small_segments([])

        assert outcome == MergeOutcome(
            segments=(), dissolved_boundaries=0, moved_photo_ids=frozenset()
        )

    def test_the_round_limit_raises_instead_of_breaking_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die Rundenobergrenze greift im Betrieb nie; pruefbar ist sie nur, indem man sie
        unterschreitet. Ein stiller Frueabbruch liesse eine halb zusammengelegte Gliederung
        zurueck, die niemandem auffiele - deshalb WIRFT sie."""
        monkeypatch.setattr(events_module, "_round_limit", lambda _: 0)
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        with pytest.raises(EventMergeError):
            merge_small_segments(segments)


class TestTheThirdStageKeepsTheOpeningCause(_UnderShiftedEventConstants):
    """Aufgeloest wird die Grenze ZWISCHEN den beiden; die eroeffnende des FRUEHEREN bleibt."""

    def test_the_result_carries_the_cause_of_the_earlier_segment(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1, causes={BOUNDARY_EXTENT}),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        [merged] = merge_small_segments(segments).segments

        assert merged.causes == frozenset({BOUNDARY_EXTENT})

    def test_the_first_segment_keeps_its_empty_cause_when_it_is_absorbed(self) -> None:
        """Index 0 traegt die leere Menge, und das muss auch NACH Stufe 3 gelten - sonst truege
        der erste Abschnitt eines Laufs ploetzlich eine Ursache."""
        segments = [
            _tiny(timedelta(0), first_id=1),
            _normal_from(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        [merged] = merge_small_segments(segments).segments

        assert merged.causes == frozenset()


class TestTheCounterIndicationOfTheThirdStage(_UnderShiftedEventConstants):
    """Die Gegenanzeige: Beide Abnahmezahlen dieser Spec wuerden von einer zu aggressiven
    Verschmelzung BESSER erfuellt. Ohne diese beiden Zahlen misst eine Nachmessung nur die
    Unter-Zerstueckelung."""

    def test_nothing_merged_reports_nothing_moved(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _normal_from(_merge_gap() + EPSILON_TIME, first_id=100, causes={BOUNDARY_TIME_GAP}),
        ]

        outcome = merge_small_segments(segments)

        assert outcome.dissolved_boundaries == 0
        assert outcome.moved_photo_ids == frozenset()

    def test_only_the_absorbed_segment_counts_as_moved(self) -> None:
        """Die Fotos des AUFNEHMENDEN Nachbarn sind geblieben, wo sie waren - sie mitzuzaehlen
        machte aus jeder einzelnen Zusammenlegung eine grosse Bewegung."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        outcome = merge_small_segments(segments)

        assert outcome.dissolved_boundaries == 1
        assert outcome.moved_photo_ids == frozenset({10})


class TestBuildEventsRunsTheThirdStage:
    """Stufe 3 laeuft INNERHALB der Event-Bildung - und ihre beiden Festlegungen sind injizierbar,
    sonst liefen die Faelle der Signale still durch sie hindurch."""

    def _a_lonely_photo_behind_a_time_gap(self) -> list[EventCandidate]:
        """Zwei Fotos, dann - hinter einer Zeitluecke, aber innerhalb von `MERGE_MAX_GAP` - ein
        einzelnes. Der Durchlauf trennt, Stufe 3 legt wieder zusammen."""
        gap = events_module.EVENT_TIME_GAP + EPSILON_TIME
        return [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, T0 + EPSILON_TIME),
            _placeless_candidate(3, T0 + EPSILON_TIME + gap),
        ]

    def test_the_operating_values_apply_without_any_argument(self) -> None:
        events = build_events(self._a_lonely_photo_behind_a_time_gap())

        assert [event.photo_ids for event in events] == [(1, 2, 3)]

    def test_the_minimum_is_injectable_and_switches_the_stage_off(self) -> None:
        events = build_events(self._a_lonely_photo_behind_a_time_gap(), min_event_photos=1)

        assert [event.photo_ids for event in events] == [(1, 2), (3,)]

    def test_the_merge_gap_is_injectable(self) -> None:
        """Eine Ueberbrueckung unterhalb der Zeitluecke kann keine Zeitluecken-Grenze mehr
        aufloesen - die Stufe laeuft dann, ohne etwas zu tun."""
        events = build_events(self._a_lonely_photo_behind_a_time_gap(), merge_max_gap=timedelta(0))

        assert [event.photo_ids for event in events] == [(1, 2), (3,)]

    def test_the_constants_are_read_as_module_attributes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ein Default-Parameterwert in der Signatur baende sie beim Import; `monkeypatch.setattr`
        liefe ins Leere und jede Variation waere wirkungslos - gruen, aber ohne Wirkung."""
        monkeypatch.setattr(events_module, "MIN_EVENT_PHOTOS", 1)

        events = build_events(self._a_lonely_photo_behind_a_time_gap())

        assert [event.photo_ids for event in events] == [(1, 2), (3,)]

    def test_the_explaining_form_reports_the_counter_indication(self) -> None:
        formation = explain_events(self._a_lonely_photo_behind_a_time_gap())

        assert formation.dissolved_boundaries == 1
        assert formation.moved_photos == 1
        assert formation.causes == (frozenset(),)

    def test_a_run_without_any_merging_reports_a_counter_indication_of_zero(self) -> None:
        formation = explain_events(self._a_lonely_photo_behind_a_time_gap(), min_event_photos=1)

        assert (formation.dissolved_boundaries, formation.moved_photos) == (0, 0)

    def test_a_merged_event_goes_through_the_one_place_that_builds_them(self) -> None:
        """Ein zusammengelegtes Event durchlaeuft dieselbe Bildung wie jedes andere - es gibt
        keinen zweiten Zweig fuer Name, Zellen, `place_kind` und `position`."""
        gap = events_module.EVENT_TIME_GAP + EPSILON_TIME
        candidates = [
            _measured_candidate(1, T0, landmark_name="Zugspitze"),
            _measured_candidate(2, T0 + EPSILON_TIME),
            _measured_candidate(3, T0 + EPSILON_TIME + gap),
        ]

        [event] = build_events(candidates)

        assert (event.position, event.photo_ids) == (1, (1, 2, 3))
        assert (event.landmark_name, event.place_kind) == ("Zugspitze", "landmark")
        assert len(event.place_cells) == 1
        assert (event.started_at, event.ended_at) == (T0, candidates[-1].taken_at)


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
