from __future__ import annotations

import ast
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from fractions import Fraction
from itertools import permutations, product
from pathlib import Path

import pytest

from photosort import events as events_module
from photosort import scoring as scoring_module
from photosort.events import (
    BOUNDARY_CAUSES,
    BOUNDARY_DURATION,
    BOUNDARY_EXTENT,
    BOUNDARY_LANDMARK,
    BOUNDARY_MOTIF_CHANGE,
    BOUNDARY_STEP,
    BOUNDARY_TIME_GAP,
    MERGE_BLOCK_EXTENT,
    MERGE_BLOCK_NO_NEIGHBOUR,
    MERGE_BLOCK_REASONS,
    MERGE_BLOCK_SPAN,
    MERGE_BLOCK_TIME_GAP,
    MERGE_BLOCK_UNBREAKABLE,
    BoundarySignal,
    BuiltEvent,
    EffectiveLocation,
    EventCandidate,
    EventFormation,
    EventMergeError,
    EventSpan,
    EventSpanSignal,
    ExtentSignal,
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


def _merge_extent_max() -> float:
    """Die geltende Ausdehnungsgrenze von STUFE 3 - als Modulattribut gelesen.

    Eine andere als `_extent_max()`: Riegel (c) prueft seit ADR 0118 eine eigene, groessere
    Grenze. Praefte er weiter die Trennschwelle, waere die Stufe fuer genau die Segmente
    unpassierbar, die die Ausdehnung getrennt hat."""
    return events_module.MERGE_EXTENT_MAX_METERS


def _max_span() -> timedelta:
    """Die geltende Dauergrenze - als Modulattribut gelesen."""
    return events_module.EVENT_MAX_SPAN


def _merge_gap() -> timedelta:
    """Die geltende Ueberbrueckungsgrenze von Stufe 3 - als Modulattribut gelesen."""
    return events_module.MERGE_MAX_GAP


def _min_share() -> Fraction:
    """Der geltende Rueckhalt eines Sehenswuerdigkeitsnamens - als MODULATTRIBUT gelesen, nie als
    Zahl. Die Faelle bauen ihre Foto- und Traegermengen aus Zaehler und Nenner dieses Bruchs."""
    return events_module.LANDMARK_MIN_SHARE


def _at(**delta: float) -> datetime:
    return T0 + timedelta(**delta)


def _north(meters: float) -> float:
    """Breitengrad `meters` noerdlich von `BASE_LAT`."""
    return BASE_LAT + meters / _METERS_PER_DEGREE_LATITUDE


def _radius() -> float:
    """Der gueltige Umkreis eines Sehenswuerdigkeitsnamens - als MODULATTRIBUT gelesen, nie als
    Zahl. Alle Faelle dieser Datei rechnen die Grenze an diesem Symbol."""
    return events_module.LANDMARK_PLAUSIBILITY_RADIUS_METERS


def _latitude_at(distance_meters: float) -> float:
    """Der Breitengrad, dessen Nordabstand von `BASE_LAT` GENAU `distance_meters` betraegt.

    Gebildet ueber den Erdradius, mit dem `haversine_meters` rechnet - NICHT ueber `_north`. Die
    beiden weichen um den Unterschied zwischen `_METERS_PER_DEGREE_LATITUDE` (111195.0) und dem
    tatsaechlichen Bogen (R * pi/180 ~ 111194.93) ab; das sind 7e-8 relativ, genug, um den Fall
    "genau auf der Grenze" unbemerkt nach innen zu schieben."""
    return BASE_LAT + math.degrees(distance_meters / scoring_module._EARTH_RADIUS_METERS)


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


# Zeitluecke, Schritt, Ausdehnung, Dauergrenze, Ueberbrueckung, Mindestgroesse, Ausdehnungsgrenze
# von Stufe 3. `None` ist der Betriebssatz. Jeder weitere Satz haelt die vier zulaessigen
# Ungleichungen ein (`MERGE_MAX_GAP > EVENT_TIME_GAP`, `MIN_EVENT_PHOTOS >= 2`,
# `EVENT_MAX_SPAN < 24 h`, `MERGE_EXTENT_MAX_METERS > EVENT_EXTENT_MAX_METERS`) und laesst
# `EPSILON_METERS`/`EPSILON_TIME` klein gegen jede seiner Schwellen.
_SHIFTED_CONSTANT_SETS: tuple[tuple[object, ...] | None, ...] = (
    None,
    (timedelta(hours=3), 1500.0, 4000.0, timedelta(hours=20), timedelta(hours=5), 3, 5500.0),
    (timedelta(minutes=10), 300.0, 600.0, timedelta(hours=2), timedelta(minutes=25), 2, 900.0),
)

_SHIFTED_CONSTANT_NAMES = (
    "EVENT_TIME_GAP",
    "EVENT_STEP_MAX_METERS",
    "EVENT_EXTENT_MAX_METERS",
    "EVENT_MAX_SPAN",
    "MERGE_MAX_GAP",
    "MIN_EVENT_PHOTOS",
    "MERGE_EXTENT_MAX_METERS",
)


class _UnderShiftedEventConstants:
    """Jeder Fall einer erbenden Klasse laeuft unter MEHREREN Saetzen der sieben Schwellen.

    Die sieben sind aenderbare, unkalibrierte Festlegungen; kein Fall darf ihren Zahlwert pinnen.
    Die Faelle bauen ihre Lage deshalb aus `_time_gap()`, `_step_max()`, `_extent_max()`,
    `_max_span()`, `_merge_gap()` und `_merge_extent_max()` statt aus einer Zahl, und diese Fixture setzt die
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
    """Die FUENF Zusagen ueber JEDE Event-Folge eines Laufs - laeuft am Ende JEDES
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

    # Die GEGENANZEIGE der Namensregel (Spec 0514): Traegt ein Event ueberhaupt einen Namen, dann
    # bezeugt ihn mindestens `LANDMARK_MIN_SHARE` seiner Mitglieder. Gezaehlt ueber `_usable_name` -
    # dieselbe Traegerdefinition, die die Produktion benutzt, statt einer zweiten Fassung hier.
    name_by_photo = {
        candidate.photo_id: events_module._usable_name(candidate.landmark_name)
        for candidate in candidates
    }
    share = _min_share()
    for event in events:
        if event.landmark_name is None:
            continue
        carriers = sum(
            1 for photo_id in event.photo_ids if name_by_photo.get(photo_id) == event.landmark_name
        )
        assert carriers * share.denominator >= len(event.photo_ids) * share.numerator


def _diagonal_of(
    event: BuiltEvent, location_by_id: Mapping[int, EffectiveLocation | None]
) -> float | None:
    """Die Diagonale der umschliessenden Box eines Events - `None` ohne jede wirksame Koordinate."""
    located = [
        location
        for photo_id in event.photo_ids
        if (location := location_by_id[photo_id]) is not None
    ]
    if not located:
        return None
    return haversine_meters(
        min(location.lat for location in located),
        min(location.lon for location in located),
        max(location.lat for location in located),
        max(location.lon for location in located),
    )


def assert_full_signal_invariants(
    candidates: Sequence[EventCandidate], events: Sequence[BuiltEvent]
) -> None:
    """Die DREI Zusagen ueber jede Event-Folge aus dem VOLLEN Signalsatz.

    Kein Event ueber `EVENT_MAX_SPAN`. Kein Event ueber `MERGE_EXTENT_MAX_METERS`. Und kein Event
    AUS DEM DURCHLAUF ueber `EVENT_EXTENT_MAX_METERS`.

    ZWEIGETEILT, NICHT GELOCKERT (ADR 0118 Punkt 4): Die frueher eine Zusage - beide Stufen gegen
    dieselbe Zahl - gilt so nicht mehr, seit Riegel (c) seine eigene, groessere Grenze prueft. Sie
    bloss auf die groessere anzuheben gaebe die Schranke des Durchlaufs stillschweigend mit auf;
    die Ausdehnung eines Events bliebe zwar beschraenkt, aber nicht mehr messbar daran, in welcher
    Stufe sie entstanden ist.

    Die zweite Haelfte misst am Durchlauf selbst: Mit abgeschaltetem Zusammenlegen ist die
    Event-Folge genau seine Gliederung. Gerechnet wird ueber FRISCHE Signale (`None`) - eine bereits
    verbrauchte Liste traege den Zustand des ersten Laufs weiter.

    Als Nachsatz ueber der ganzen Fallmenge, nicht als Einzelfall. Nur fuer den vollen Satz: Eine
    injizierte Teilmenge kennt die Riegel nicht und darf sie ueberschreiten."""
    location_by_id = {candidate.photo_id: candidate.location for candidate in candidates}
    for event in events:
        assert event.ended_at - event.started_at <= _max_span()
        diagonal = _diagonal_of(event, location_by_id)
        if diagonal is not None:
            assert diagonal <= _merge_extent_max()

    for from_the_pass in build_events(candidates, None, min_event_photos=_NO_MERGING):
        diagonal = _diagonal_of(from_the_pass, location_by_id)
        if diagonal is not None:
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
    landmark_points_by_name: Mapping[str, tuple[tuple[float, float], ...]] | None = None,
) -> list[BuiltEvent]:
    """`build_events` plus die Invarianten - jeder Fall dieser Datei laeuft hierueber.

    `min_event_photos` steht VORGABEWEISE auf `_NO_MERGING`: Ein Fall ueber ein Signal soll genau
    dieses Signal messen. Wer Stufe 3 zum Gegenstand hat, gibt `None` (Betriebswert) oder einen
    eigenen Wert mit.

    `landmark_points_by_name` ist die Ortsauskunft der Sehenswuerdigkeitsnamen (Spec 0529). Die
    Vorgabe `None` heisst "keine Auskunft vorhanden" und laesst jeden bestehenden Fall unveraendert."""
    events = build_events(
        candidates,
        signals,
        min_event_photos=min_event_photos,
        landmark_points_by_name=landmark_points_by_name,
    )
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


class TestTheMotifChangeOnlyMarksABoundaryAndNeverOpensOne(_UnderEveryConfirmingWindow):
    """Die zweite Stufe seit ADR 0119: Ein bestaetigter Motivwechsel EROEFFNET kein Event mehr. Er
    vermerkt `motivwechsel` an einer Grenze, die der Signal-Durchlauf an derselben Stelle ohnehin
    zieht; faellt er auf keine solche Grenze, bleibt er wirkungslos und wird verworfen.

    Die Faelle hier ERSETZEN die frueheren, die den erzwungenen Start durch `build_events` hindurch
    als Trennung geprueft haben: Angepasst haetten sie ihren Namen behalten und danach etwas
    anderes geprueft, als sie versprechen. Die Faelle an `motif_change_starts` SELBST gelten
    unveraendert weiter - der Begriff aendert sich nicht, nur seine Wirkung."""

    def test_two_photos_differing_only_in_their_motif_stay_in_one_event(self) -> None:
        """(a) Der umgekehrte Story-Fall: Ruinenbesuch, danach Mittagessen um die Ecke - EIN
        Anlass, und jetzt auch ein Event.

        Kein Signal trennt hier (Minutenabstand unter der Zeitluecke, 50 m je Schritt unter
        Schritt- und Ausdehnungsschwelle, kein Sehenswuerdigkeitsname), und der Motivwechsel allein
        trennt nicht mehr - gleich wie lange er bestaetigt bleibt."""
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

        assert motif_change_starts(candidates) == frozenset({2}), "sonst misst der Fall nichts"
        assert [event.photo_ids for event in _build(candidates, default_signals())] == [
            tuple(range(len(candidates)))
        ]

    def test_an_atypical_opening_photo_no_longer_becomes_an_event_of_its_own(self) -> None:
        """Die Zusage der Spec 0477, die mit ADR 0119 faellt: Ein motivgetrenntes Einzelbild darf
        NICHT mehr allein bestehen. Ohne diesen Fall bliebe die aufgehobene Zusage ungeprueft."""
        candidates = _motif_candidates([_picture("a")] + [_picture("b")] * _window())

        assert motif_change_starts(candidates) == frozenset({1}), "sonst misst der Fall nichts"
        assert [event.photo_ids for event in _build(candidates, default_signals())] == [
            tuple(range(_window() + 1))
        ]

    def test_a_confirmed_change_advances_every_signal_instead_of_beginning_it(self) -> None:
        """DIE RUECKSETZUNG FAELLT MIT: Wo frueher `begin` auf allen Signalen lief, laeuft jetzt
        `advance`. Gefragt wird weiterhin jedes Signal an jedem Foto - sonst haengt seine
        Fortschreibung an der Listenposition."""
        spy = _SpySignal()
        candidates = _motif_candidates([_picture("a")] * 2 + [_picture("a", "b")] * _window())

        _build(candidates, [spy])

        assert motif_change_starts(candidates) == frozenset({2}), "sonst misst der Fall nichts"
        assert spy.asked == [candidate.photo_id for candidate in candidates]
        assert spy.begun == [0]
        assert spy.advanced == [candidate.photo_id for candidate in candidates[1:]]

    def test_without_the_reset_the_extent_runs_on_and_splits_later(self) -> None:
        """(e) DIE EINE RICHTUNG, IN DER DIESE AENDERUNG EINE GRENZE HINZUFUEGT. Ohne den
        erzwungenen Start bekommt `ExtentSignal` kein `begin` mehr und laeuft ueber den
        Motivwechsel hinweg weiter - es meldet an SPAETERER Stelle eine Grenze, die es mit der
        Ruecksetzung nie gebraucht haette.

        Die Lage in Metern, alle aus `EVENT_EXTENT_MAX_METERS` gebaut: Foto 0 am Bezugspunkt, Foto
        1 auf halber Schwelle, ab Foto 2 knapp darueber. Die Box ueber ALLE reisst die Schwelle bei
        Foto 2; die Box AB Foto 1 - so weit haette der erzwungene Start zurueckgesetzt - bleibt mit
        einer halben Schwelle darunter."""
        half = _extent_max() / 2
        beyond = _extent_max() + EPSILON_METERS
        metres = [0.0, half] + [beyond] * (_window() - 1)
        candidates = [
            _measured_candidate(
                index,
                T0 + index * EPSILON_TIME,
                lat=_north(north),
                motif_strengths=picture,
            )
            for index, (north, picture) in enumerate(
                zip(metres, [_picture("a")] + [_picture("a", "b")] * _window(), strict=True)
            )
        ]

        assert motif_change_starts(candidates) == frozenset({1}), "sonst misst der Fall nichts"
        # Wie der erzwungene Start gerechnet haette: ab Foto 1 neu - und dann meldet die
        # Ausdehnung nie wieder.
        assert [event.photo_ids for event in _build(candidates[1:], [ExtentSignal()])] == [
            tuple(range(1, len(candidates)))
        ]
        # Wie jetzt gerechnet wird: die Box laeuft weiter und trennt bei Foto 2 - SPAETER als der
        # erzwungene Start bei Foto 1 getrennt haette.
        assert [event.photo_ids for event in _build(candidates, [ExtentSignal()])] == [
            (0, 1),
            tuple(range(2, len(candidates))),
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

    def test_a_window_spanning_midnight_keeps_everything_in_one_event(self) -> None:
        """Der rueckwirkende Beginn liegt auf dem VORTAG, das bestaetigende Foto dahinter - und
        KEINE der beiden Stellen trennt noch: die Mitternachtsgrenze nicht (seit ADR 0117) und der
        Motivwechsel nicht mehr (seit ADR 0119). Braucht `default_signals()`, weil genau dieser
        Satz die Dauergrenze anstelle des Kalendertags fuehrt.

        Die Fotos liegen einen Sekundenschritt auseinander, der Wechsel faellt auf das erste nach
        Mitternacht. KEIN Abstand dieser Lage ist aus einer Uhrzeit gebaut: Ein Sprung von
        `23:30` auf `23:59:59` risse unter einer kleineren Zeitluecken-Schwelle eine Grenze auf,
        und der Fall maesse dann den Kalendertag gar nicht mehr."""
        midnight = datetime(2026, 7, 21, 0, 0, 0)
        candidates = [
            EventCandidate(
                photo_id=index,
                taken_at=midnight + (index - 2) * EPSILON_TIME,
                motif_strengths=picture,
            )
            for index, picture in enumerate([_picture("a")] * 2 + [_picture("a", "b")] * _window())
        ]

        events = _build(candidates, default_signals())

        assert candidates[1].taken_at.date() != candidates[2].taken_at.date(), (
            "sonst laeuft der Fall gar nicht ueber Mitternacht"
        )
        assert motif_change_starts(candidates) == frozenset({2}), "sonst misst der Fall nichts"
        assert [event.photo_ids for event in events] == [tuple(range(_window() + 2))]
        assert events[0].started_at.date() != events[0].ended_at.date()

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
        found_a_start = False

        for combination in product(alphabet, repeat=_window() + 2):
            candidates = _motif_candidates(list(combination))
            starts = motif_change_starts(candidates)
            found_a_start = found_a_start or bool(starts)

            assert 0 not in starts, combination
            assert starts <= set(range(len(candidates))), combination
            # Kein anderes Signal spricht bei diesen Kandidaten mit (Sekundenabstand, kein Ort,
            # kein Name). Seit ADR 0119 eroeffnet ein bestaetigter Wechsel KEIN Event mehr - die
            # ganze Folge bleibt EIN Event, gleich wie viele Starts die erste Stufe liefert.
            events = _build(candidates, default_signals())
            assert [event.photo_ids for event in events] == [tuple(range(len(candidates)))], (
                combination
            )

        assert found_a_start, "sonst zaehlt die Aufzaehlung nur Folgen ohne jeden Wechsel"


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

    def test_an_event_takes_a_name_that_one_of_its_photos_backs(self) -> None:
        """Der Rueckhalt, nicht die Reihenfolge: Ein einzelner benannter unter zwei Fotos genuegt
        (die Haelfte liegt ueber dem Zehntel) - auch wenn er nicht das erste ist."""
        candidates = [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, _at(minutes=1), landmark_name="Eiffelturm"),
        ]

        [event] = _build(candidates, [])

        assert event.landmark_name == "Eiffelturm"

    def test_two_names_with_the_same_support_leave_the_earlier_one_winning(self) -> None:
        """Der GLEICHSTAND: Zwei Namen mit JE einem Traegerfoto. Der Rueckhalt entscheidet zuerst,
        die Reihenfolge erst bei Gleichstand - hier gewinnt deshalb der fruehere."""
        candidates = [
            _placeless_candidate(1, T0, landmark_name="Zugspitze"),
            _placeless_candidate(2, T0 + EPSILON_TIME, landmark_name="Eibsee"),
        ]

        [event] = _build(candidates)

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
            _placeless_candidate(1, T0, landmark_name="Zugspitze"),
            *(
                _placeless_candidate(
                    10 + index, T0 + opening + index * EPSILON_TIME, landmark_name="Eibsee"
                )
                for index in range(big)
            ),
        ]

        [event] = _build(candidates, min_event_photos=None)

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
    """

    def test_a_name_with_more_carriers_beats_an_earlier_one(self) -> None:
        """Der Rueckhalt steht VOR der Reihenfolge: Der fruehere Eibsee hat ein Traegerfoto, der
        spaetere Zugspitze zwei - Zugspitze benennt das Event."""
        candidates = [
            _placeless_candidate(1, T0, landmark_name="Eibsee"),
            _placeless_candidate(2, T0 + EPSILON_TIME, landmark_name="Zugspitze"),
            _placeless_candidate(3, T0 + 2 * EPSILON_TIME, landmark_name="Zugspitze"),
        ]

        [event] = _build(candidates)

        assert event.landmark_name == "Zugspitze"

    def test_the_share_boundary_is_inclusive(self) -> None:
        """Genau `numerator` Traeger unter `denominator` Mitgliedern: das genuegt."""
        share = _min_share()
        candidates = [
            _placeless_candidate(
                index,
                T0 + index * EPSILON_TIME,
                landmark_name="Eiffelturm" if index < share.numerator else None,
            )
            for index in range(share.denominator)
        ]

        [event] = _build(candidates)

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
            _placeless_candidate(1, T0, landmark_name="Eiffelturm"),
            _placeless_candidate(2, T0 + EPSILON_TIME),
            _placeless_candidate(3, T0 + 2 * EPSILON_TIME),
        ]

        [event] = _build(candidates)

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
        [event] = _build([_placeless_candidate(1, T0, landmark_name="Eiffelturm")])

        assert event.landmark_name == "Eiffelturm"

    def test_a_blank_name_neither_carries_nor_wins(self) -> None:
        """Ein nach der Sanitisierung leerer Name zaehlt nicht als Traeger - und kann deshalb auch
        nicht gewinnen, obwohl er der fruehere ist."""
        candidates = [
            _placeless_candidate(1, T0, landmark_name="   "),
            _placeless_candidate(2, T0 + EPSILON_TIME, landmark_name="Eiffelturm"),
        ]

        [event] = _build(candidates)

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

    Die Prueffunktion ist ABSICHTLICH direkt aufgerufen: ihre fuenf Zweige sind eine REIHENFOLGE,
    und drei davon liefern wahr - ueber `_build` allein waeren "keine Auskunft", "keine gemessene
    Zelle" und "Schluessel fehlt" nicht auseinanderzuhalten. Die Grenze wird am SYMBOL gerechnet;
    kein Fall nennt den Zahlwert."""

    NAME = "Zugspitze"

    def _cell(self) -> tuple[float, float]:
        return (BASE_LAT, BASE_LON)

    def _inside(self) -> tuple[float, float]:
        return (_latitude_at(_radius() / 2), BASE_LON)

    def _outside(self) -> tuple[float, float]:
        return (_latitude_at(_radius() * 2), BASE_LON)

    def test_without_any_lookup_every_name_stays(self) -> None:
        """Zustand 1 (ADR 0123 Punkt 2): Es gibt keine Auskunft - der Name bleibt."""
        assert events_module._landmark_name_is_plausible(self.NAME, (self._cell(),), None) is True

    def test_without_a_measured_cell_the_name_stays_even_beside_an_empty_point_set(self) -> None:
        """Der Pflichtfall "keine Zelle UND leere Punktmenge": Der Zellen-Zweig schlaegt den
        Fund-Zweig, sonst verwuerfe ein Lauf ohne Koordinaten jeden Namen."""
        assert events_module._landmark_name_is_plausible(self.NAME, (), {self.NAME: ()}) is True

    def test_a_name_without_an_entry_keeps_its_name(self) -> None:
        """Zustand 1 am Datenbestand: eine nicht leere Auskunft, in der DIESER Name fehlt, ist
        "nie nachgeschlagen" - niemals "ohne Fund"."""
        assert (
            events_module._landmark_name_is_plausible(
                self.NAME, (self._cell(),), {"Andere Sehenswuerdigkeit": (self._inside(),)}
            )
            is True
        )

    def test_a_looked_up_name_without_a_single_point_falls(self) -> None:
        """Zustand 2 (ADR 0123 Punkt 2): nachgeschlagen, kein Fund - der Name faellt."""
        assert (
            events_module._landmark_name_is_plausible(self.NAME, (self._cell(),), {self.NAME: ()})
            is False
        )

    def test_a_point_inside_the_radius_keeps_the_name(self) -> None:
        assert (
            events_module._landmark_name_is_plausible(
                self.NAME, (self._cell(),), {self.NAME: (self._inside(),)}
            )
            is True
        )

    def test_a_point_outside_the_radius_drops_the_name(self) -> None:
        assert (
            events_module._landmark_name_is_plausible(
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
            assert events_module._landmark_name_is_plausible(*args) is False

            patch.setattr(
                events_module,
                "LANDMARK_PLAUSIBILITY_RADIUS_METERS",
                math.nextafter(at_the_radius, math.inf),
            )
            assert events_module._landmark_name_is_plausible(*args) is True

            patch.setattr(
                events_module,
                "LANDMARK_PLAUSIBILITY_RADIUS_METERS",
                math.nextafter(at_the_radius, 0.0),
            )
            assert events_module._landmark_name_is_plausible(*args) is False

    def test_one_fitting_pair_is_enough_across_several_points(self) -> None:
        """Verglichen wird jedes Paar (Zelle, Fundort): ein einziger Fund im Umkreis genuegt."""
        assert (
            events_module._landmark_name_is_plausible(
                self.NAME,
                (self._cell(),),
                {self.NAME: (self._outside(), self._inside())},
            )
            is True
        )

    def test_one_fitting_pair_is_enough_across_several_cells(self) -> None:
        cells = ((BASE_LAT + 2.0, BASE_LON), self._cell())

        assert (
            events_module._landmark_name_is_plausible(
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

    def test_without_a_lookup_the_name_stays(self) -> None:
        candidates = [
            _measured_candidate(1, T0, landmark_name=self.NAME),
            _measured_candidate(2, T0 + EPSILON_TIME, landmark_name=self.NAME),
        ]

        [event] = _build(candidates, landmark_points_by_name=None)

        assert event.landmark_name == self.NAME

    def test_a_dropped_name_leaves_the_event_as_unnamed_as_a_never_named_one(self) -> None:
        """Zwillings-Tripel der Auskunft (ADR 0123 Punkt 2): kein Eintrag / leere Punktmenge /
        Punkte. Zustand 1 und 3 liefern DASSELBE Event; unterschieden werden sie an der Abwesenheit
        der Zeile, nicht am Ergebnis - der Zustand 2 faellt allein am Namen."""
        candidates = [
            _measured_candidate(1, T0, landmark_name=self.NAME),
            _measured_candidate(2, T0 + EPSILON_TIME, landmark_name=self.NAME),
        ]
        never_looked_up = _build(candidates)  # Zustand 1: gar keine Auskunft
        without_a_find = _build(candidates, landmark_points_by_name={self.NAME: ()})
        with_a_find = _build(candidates, landmark_points_by_name={self.NAME: (self._inside(),)})
        missing_entry = _build(
            candidates, landmark_points_by_name={"Andere Sehenswuerdigkeit": (self._outside(),)}
        )

        assert never_looked_up == with_a_find == missing_entry
        assert without_a_find[0].landmark_name is None
        assert never_looked_up[0] != without_a_find[0]

    def test_a_name_without_a_measured_cell_survives_an_empty_point_set(self) -> None:
        """Der Zellen-Fall schlaegt den Fund-Fall auch ueber den vollen Weg: ein Event ohne jede
        gemessene Zelle behaelt seinen Namen, selbst wenn eine leere Zeile vorliegt."""
        candidates = [
            _placeless_candidate(1, T0, landmark_name=self.NAME),
            _placeless_candidate(2, T0 + EPSILON_TIME, landmark_name=self.NAME),
        ]

        [event] = _build(candidates, landmark_points_by_name={self.NAME: ()})

        assert event.landmark_name == self.NAME

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


# --- Die Trennursache (Spec 0506, ADR 0117 Punkt 4) ---------------------------------------------


def _explain(
    candidates: Sequence[EventCandidate],
    signals: list[BoundarySignal] | None = None,
    *,
    confirming_photos: int | None = None,
    min_event_photos: int | None = _NO_MERGING,
) -> EventFormation:
    """`explain_events` plus die Invarianten - jeder Fall dieser Sektion laeuft hierueber.

    Wie `_build` mit abgeschaltetem Zusammenlegen: Ein Fall ueber die URSACHENMENGE misst die
    Grenzen des Durchlaufs, nicht die, die Stufe 3 davon uebriglaesst."""
    formation = explain_events(
        candidates,
        signals,
        confirming_photos=confirming_photos,
        min_event_photos=min_event_photos,
    )
    assert_event_invariants(candidates, list(formation.events))
    assert len(formation.causes) == len(formation.events)
    assert formation.causes[0:1] in ((), (frozenset(),))
    # DIE TRAGENDE PRUEFFORM: Grenzen mit Ursache == Events - 1. Das erste Segment eines Laufs
    # traegt keine Ursache, jedes weitere genau eine Grenze.
    assert sum(1 for cause in formation.causes if cause) == max(len(formation.events) - 1, 0)
    # DIE ZUSAGE VON ADR 0119, als Nachsatz ueber JEDEM Fall dieser Sektion statt als Einzelfall:
    # `motivwechsel` steht nie allein. Er vermerkt eine Grenze, die ein Signal ohnehin gemeldet
    # hat - allein stehend behauptete er eine, die er selbst eroeffnet haette.
    for cause in formation.causes:
        assert BOUNDARY_MOTIF_CHANGE not in cause or len(cause) >= 2
    return formation


class TestEverySignalCarriesAName:
    def test_the_default_set_uses_only_names_from_the_closed_stock(self) -> None:
        """Ein Signal ohne Namen aus dem Vorrat faellt in der Statistik unter den Tisch, ohne dass
        eine Summe kleiner wuerde - der Bericht waere dann still unvollstaendig."""
        names = [signal.name for signal in default_signals()]

        assert len(names) == len(set(names)), "zwei gleichnamige Signale sind eine Ursache"
        assert set(names) <= set(BOUNDARY_CAUSES)

    def test_the_motif_change_has_its_own_name_in_the_stock(self) -> None:
        """Der Motivwechsel ist kein Eintrag in `default_signals()` und eroeffnet seit ADR 0119
        auch kein Event mehr. Sein Name bleibt trotzdem im Vorrat: Er vermerkt eine Grenze mit, und
        "war beteiligt" ist die Zahl, an der eine spaetere Aenderung dieser Entscheidung gemessen
        wuerde."""
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

    def test_the_duration_reports_under_its_own_name(self) -> None:
        """Die Dauergrenze ist an die Stelle des Kalendertags getreten; ohne ihren Namen im Vorrat
        stuende in Block B eine Grenze ohne Ursache."""
        candidates = [
            _placeless_candidate(1, T0),
            _placeless_candidate(2, T0 + _max_span() + EPSILON_TIME),
        ]

        formation = _explain(candidates, [EventSpanSignal()])

        assert formation.causes[1] == frozenset({BOUNDARY_DURATION})

    def test_the_landmark_keeps_its_name_in_the_supply_without_a_signal_behind_it(self) -> None:
        """Die EHRLICHE NULL (ADR 0118 Punkt 2): `sehenswuerdigkeit` bleibt im Wortschatz, damit die
        Nachmessung ihre Zeile behaelt und mit der Ausgangsmessung vergleichbar bleibt. Verschwaende
        das Symbol, koennte kein Leser unterscheiden, ob die Ursache weggefallen oder nie gemessen
        worden ist. Kein Signal traegt den Namen mehr - sonst waere die Null keine."""
        assert BOUNDARY_LANDMARK in BOUNDARY_CAUSES
        assert all(signal.name != BOUNDARY_LANDMARK for signal in default_signals())

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


class TestTheGroupingNoLongerDependsOnTheFirstStage(_UnderEveryConfirmingWindow):
    """DIE EIGENTLICHE ZUSAGE von ADR 0119, in ihrer starken Form: `explain_events` liefert unter
    einem nie erreichbaren Bestaetigungsfenster DIESELBE Eventfolge wie am Betriebswert -
    verschieden sind allein die Ursachenmengen.

    Gerechnet wird mit den Mitteln des Laufs: dasselbe `explain_events`, nur mit einem Fenster
    groesser als die Zahl der Kandidatenfotos. Mehr aufeinanderfolgende mitredende Fotos als Fotos
    kann es nicht geben, also bestaetigt kein Wechsel - ohne einen Abschaltpfad im Produktivcode."""

    def _mixed_run(self) -> list[EventCandidate]:
        """Vier Abschnitte: ein Bezugsblock, ein zweiter hinter einer Zeitluecke, an der ZUGLEICH
        das Motiv wechselt, ein dritter mit einem Motivwechsel OHNE jedes meldende Signal, und ein
        vierter hinter einem Schritt ohne Motivwechsel.

        Ohne den Zusammenfall im zweiten Abschnitt waere der Vergleich unten vakuum-gleich: Die
        beiden Gliederungen truegen dann auch dieselben Ursachenmengen."""
        window = _window()
        gap = _time_gap() + EPSILON_TIME
        far = _step_max() + EPSILON_METERS
        first = [(T0 + index * EPSILON_TIME, 0.0, _picture("a")) for index in range(window)]
        behind_the_gap = [
            (first[-1][0] + gap + index * EPSILON_TIME, 0.0, _picture("a", "b"))
            for index in range(window)
        ]
        without_a_signal = [
            (behind_the_gap[-1][0] + (index + 1) * EPSILON_TIME, 0.0, _picture("a", "c"))
            for index in range(window)
        ]
        behind_the_step = [
            (without_a_signal[-1][0] + (index + 1) * EPSILON_TIME, far, _picture("a", "c"))
            for index in range(window)
        ]
        return [
            _measured_candidate(index, taken_at, lat=_north(north), motif_strengths=picture)
            for index, (taken_at, north, picture) in enumerate(
                [*first, *behind_the_gap, *without_a_signal, *behind_the_step]
            )
        ]

    def test_the_lay_carries_both_kinds_of_motif_change(self) -> None:
        """Der Waechter unter dieser Klasse: einer der beiden Wechsel faellt auf eine Signalgrenze,
        der andere auf keine. Faellt einer der beiden weg, messen die Faelle darunter die Haelfte
        der Zusage nicht mehr - und blieben gruen."""
        candidates = self._mixed_run()

        assert motif_change_starts(candidates) == frozenset({_window(), 2 * _window()})

    def test_the_unreachable_window_yields_the_very_same_events(self) -> None:
        """(b) Gleiche Fotomengen, gleiche Grenzen, gleiche Positionen - die Gliederung haengt
        nicht mehr an der ersten Stufe."""
        candidates = self._mixed_run()

        operating = _explain(candidates)
        switched_off = _explain(candidates, confirming_photos=len(candidates) + 1)

        assert [(event.photo_ids, event.position) for event in switched_off.events] == [
            (event.photo_ids, event.position) for event in operating.events
        ]

    def test_only_the_cause_sets_differ_and_only_by_the_motif_change(self) -> None:
        """Die Kehrseite des Falls darueber: Etwas UNTERSCHEIDET sich, sonst maesse er nichts - und
        es ist ausschliesslich der Vermerk."""
        candidates = self._mixed_run()

        operating = _explain(candidates)
        switched_off = _explain(candidates, confirming_photos=len(candidates) + 1)

        assert operating.causes != switched_off.causes
        assert tuple(cause - {BOUNDARY_MOTIF_CHANGE} for cause in operating.causes) == (
            switched_off.causes
        )

    def test_a_change_on_a_reported_boundary_joins_its_cause_set(self) -> None:
        """(c) Der Vermerk selbst: Der Motivwechsel faellt mit der Zeitluecke zusammen und steht
        NEBEN ihr in der Menge - nie an ihrer Stelle."""
        formation = _explain(self._mixed_run())

        assert formation.causes[1] == frozenset({BOUNDARY_TIME_GAP, BOUNDARY_MOTIF_CHANGE})

    def test_a_change_without_a_reporting_signal_reaches_no_later_boundary(self) -> None:
        """(d) DER VERMERK WIRD NICHT AUFGESCHOBEN: Der zweite Wechsel faellt auf einen Index, an
        dem kein Signal meldet. Er wird verworfen - die naechste Grenze, die der Schritt zieht,
        nennt nur den Schritt. Ein nachgetragener Vermerk behauptete eine Mitursache an einer
        Stelle, an der der Wechsel nicht stattgefunden hat."""
        formation = _explain(self._mixed_run())

        assert len(formation.events) == 3
        assert formation.causes[2] == frozenset({BOUNDARY_STEP})

    def test_no_cause_set_of_the_run_carries_the_motif_change_alone(self) -> None:
        """Die zweite maschinell gepruefte Zusage, hier an einer Lage mit beiden Arten von
        Wechsel. Als Nachsatz ueber JEDEM Fall dieser Sektion steht sie in `_explain`."""
        formation = _explain(self._mixed_run())

        assert any(BOUNDARY_MOTIF_CHANGE in cause for cause in formation.causes), (
            "sonst misst der Fall nichts"
        )
        for cause in formation.causes:
            assert cause != frozenset({BOUNDARY_MOTIF_CHANGE})


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

    def _sequence(self, length: int, *, strength: float | None = None) -> list[EventCandidate]:
        """Ein Bezugsfoto, dann `length` Fotos, in denen "b" mit mittlerer Staerke dazukommt.

        Ob daraus ein Wechsel wird, entscheidet allein die mitgegebene Grenze; wie viele Fotos ihn
        bestaetigen muessen, allein die mitgegebene Fensterlaenge.

        `strength` waehlt die Staerke von "b". Ein Fall, der KEINE Grenze mitgibt und trotzdem
        einen Wechsel braucht, gibt `_CARRIED` mit: Diese Staerke liegt am oberen Rand der Skala
        und wird unter JEDEM Betriebswert getragen. Mit der mittleren Staerke haenge er still am
        heutigen `MOTIF_PRESENCE_THRESHOLD` und bliebe nach einer Verschiebung vakuum-gruen."""
        reference = {"a": self._CARRIED, "b": self._ABSENT}
        deviating = {"a": self._CARRIED, "b": self._MIDDLE if strength is None else strength}
        return _motif_candidates([reference, *([deviating] * length)])

    def _sequence_behind_a_gap(self, length: int) -> list[EventCandidate]:
        """Dieselbe Folge, aber mit einer ZEITLUECKE genau am Index des Wechsels.

        Seit ADR 0119 wirkt sich die erste Stufe nur noch auf die Ursachenmenge einer Grenze aus,
        die ein Signal ohnehin meldet. Ohne diese Grenze waere an der Gliederung nicht mehr
        abzulesen, ob die beiden Festlegungen ueberhaupt durchgereicht werden."""
        return [
            replace(candidate, taken_at=candidate.taken_at + (_time_gap() + EPSILON_TIME))
            if candidate.photo_id >= 1
            else candidate
            for candidate in self._sequence(length)
        ]

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
        candidates = self._sequence(4, strength=self._CARRIED)
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
        candidates = self._sequence(
            events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS, strength=self._CARRIED
        )
        threshold = MOTIF_PRESENCE_THRESHOLD

        assert motif_change_starts(candidates) == motif_change_starts(
            candidates,
            confirming_photos=events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS,
            motif_presence_threshold=threshold,
        )
        assert motif_change_starts(candidates) == frozenset({1})

    def test_the_explaining_form_hands_both_through(self) -> None:
        """`explain_events` reicht beide weiter - sonst kann die Messung den Vermerk nicht
        variieren und misst unter jeder Kombination dieselben Zahlen.

        Abgelesen wird seit ADR 0119 an der URSACHENMENGE, nicht mehr an der Gliederung: Die
        Zeitluecke zieht die Grenze in beiden Laeufen, und nur unter dem kurzen Fenster steht
        `motivwechsel` daneben."""
        candidates = self._sequence_behind_a_gap(2)

        # Stufe 3 bleibt draussen (`_NO_MERGING`): Der Fall misst den Durchlauf, und das
        # Zusammenlegen zoege das fuehrende Einzelfoto sonst wieder ein.
        narrow = explain_events(
            candidates,
            confirming_photos=2,
            motif_presence_threshold=self._MIDDLE,
            min_event_photos=_NO_MERGING,
        )
        wide = explain_events(
            candidates,
            confirming_photos=5,
            motif_presence_threshold=self._MIDDLE,
            min_event_photos=_NO_MERGING,
        )

        assert len(narrow.events) == len(wide.events) == 2
        assert narrow.causes[1] == frozenset({BOUNDARY_TIME_GAP, BOUNDARY_MOTIF_CHANGE})
        assert wide.causes[1] == frozenset({BOUNDARY_TIME_GAP})

    def test_the_explaining_form_without_arguments_is_the_run_itself(self) -> None:
        candidates = self._sequence(
            events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS, strength=self._CARRIED
        )

        assert explain_events(candidates) == explain_events(
            candidates,
            confirming_photos=events_module.MOTIF_CHANGE_CONFIRMING_PHOTOS,
            motif_presence_threshold=MOTIF_PRESENCE_THRESHOLD,
        )


class TestTheFourAdmissibleStatementsAboutTheNumbers:
    """Die EINZIGEN vier Aussagen, die ein Test ueber die sieben Zahlwerte treffen darf - und alle
    vier sind Ungleichungen. Jede fuenfte waere eine Spiegelung des Codes und machte die naechste
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

    def test_the_merge_extent_reaches_beyond_the_splitting_extent(self) -> None:
        """Waere sie nicht groesser, praefte Riegel (c) dieselbe Bedingung, deren Ueberschreitung
        die Trennung ausgeloest hat - fuer ausdehnungsgetrennte Segmente waere Stufe 3 damit
        strukturell unpassierbar. Eine Ungleichung, kein Zahlwert: WIE viel groesser, ist eine
        Kalibrierungsfrage und steht als Herleitung an der Konstante."""
        assert events_module.MERGE_EXTENT_MAX_METERS > events_module.EVENT_EXTENT_MAX_METERS


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

    def test_bolt_c_the_extent_of_the_result_exceeds_the_merge_extent(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1, meters_north=0.0),
            _tiny(
                EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_TIME_GAP},
                meters_north=_merge_extent_max() + EPSILON_METERS,
            ),
        ]

        assert _ids(merge_small_segments(segments)) == [_block(1), (10,)]

    def test_bolt_c_reads_its_own_limit_not_the_splitting_threshold(self) -> None:
        """DER TRAGENDE FALL von ADR 0118 Punkt 4: Genau die Lage, die die Ausdehnung GETRENNT hat
        - das Ergebnis liegt ueber `EVENT_EXTENT_MAX_METERS` - wird zusammengelegt, weil Riegel (c)
        seine eigene, groessere Grenze prueft. Praefte er weiter die Trennschwelle, waere die Stufe
        fuer ausdehnungsgetrennte Segmente strukturell unpassierbar, und dieser Fall bliebe rot."""
        between = (_extent_max() + _merge_extent_max()) / 2
        segments = [
            _normal_until(timedelta(0), first_id=1, meters_north=0.0),
            _tiny(
                EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_EXTENT},
                meters_north=between,
            ),
        ]

        assert between > _extent_max(), "sonst misst der Fall die neue Grenze gar nicht"
        assert _ids(merge_small_segments(segments)) == [(*_block(1), 10)]

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


class TestNoBoundaryIsUntouchableAnyMore(_UnderShiftedEventConstants):
    """Seit ADR 0119 liest die dritte Stufe ueberhaupt keine Ursachenmenge mehr: `motivwechsel`
    haelt eine Grenze nicht mehr fest, und `UNBREAKABLE_CAUSES` ist ersatzlos entfallen.

    Die Faelle hier ERSETZEN die frueheren zur unantastbaren Grenze - sie sind deren woertliche
    Umkehrung. Der Berichtsgrund `MERGE_BLOCK_UNBREAKABLE` bleibt im Vorrat und steht dauerhaft auf
    0; ohne die Zeile waere eine Riegel-Diagnose nicht mehr gegen die frueheren zu halten, in denen
    `unantastbar` der groesste Blocker war."""

    def _enclosed(self, causes: Collection[str]) -> list[Segment]:
        return [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes=causes),
            _normal_from(2 * EPSILON_TIME, first_id=20, causes=causes),
        ]

    def test_a_segment_opened_by_a_motif_change_is_absorbed_like_any_other(self) -> None:
        """DIE UMKEHRUNG: Genau die Lage, die den Motivwechsel frueher festgehalten hat - ein
        einzelnes Foto zwischen zwei Grenzen mit `motivwechsel`, beide Nachbarn erfuellen alle drei
        Riegel - wird jetzt zugeschlagen."""
        outcome = merge_small_segments(self._enclosed({BOUNDARY_MOTIF_CHANGE}))

        assert _ids(outcome) == [(*_block(1), 10), _block(20)]
        assert outcome.dissolved_boundaries == 1
        assert outcome.moved_photo_ids == frozenset({10})

    def test_the_lage_is_decided_by_the_bolts_alone_not_by_the_cause(self) -> None:
        """Dieselbe Lage unter JEDER Ursachenmenge des Vorrats - das Ergebnis ist immer dasselbe.
        Ein einzelner Eintrag, der die Stufe doch noch liest, wird hier rot, nicht erst im
        Bericht."""
        reference = _ids(merge_small_segments(self._enclosed({BOUNDARY_TIME_GAP})))

        for cause in BOUNDARY_CAUSES:
            assert _ids(merge_small_segments(self._enclosed({cause}))) == reference, cause

    def test_a_motif_change_inside_a_set_of_two_dissolves_too(self) -> None:
        """Die Grenze traegt eine MENGE - und keine Teilmenge davon haelt sie mehr fest."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP, BOUNDARY_MOTIF_CHANGE}),
        ]

        assert _ids(merge_small_segments(segments)) == [(*_block(1), 10)]

    def test_the_block_reason_stays_in_the_supply_with_an_honest_zero(self) -> None:
        """Der Berichtswortschatz behaelt seinen Eintrag, und die Stufe liefert ihn unter KEINER
        Lage - auch nicht an einer Kante, an der alle drei Riegel zugleich sperren."""
        assert MERGE_BLOCK_UNBREAKABLE in MERGE_BLOCK_REASONS

        for cause in BOUNDARY_CAUSES:
            segments = [
                _normal_spanning_the_maximum(first_id=1),
                _tiny(
                    _max_span() + _merge_gap() + EPSILON_TIME,
                    first_id=10,
                    causes={cause},
                    meters_north=_merge_extent_max() + EPSILON_METERS,
                ),
            ]

            [blocked] = merge_small_segments(segments).blocked_segments

            for edge in blocked.edges:
                assert MERGE_BLOCK_UNBREAKABLE not in edge, cause

    def test_the_landmark_keeps_its_place_in_the_cause_vocabulary(self) -> None:
        """Was von der Ungleichbehandlung aus ADR 0118 Punkt 2 bleibt: Der Berichtswortschatz der
        URSACHEN fuehrt weiter beide Namen mit ehrlicher Null bzw. beweglicher Zahl, waehrend die
        an jeder Kante gelesene Regel ganz entfallen ist."""
        assert {BOUNDARY_LANDMARK, BOUNDARY_MOTIF_CHANGE} <= set(BOUNDARY_CAUSES)
        assert not hasattr(events_module, "UNBREAKABLE_CAUSES")


class TestTheThirdStageComesToAStandstill(_UnderShiftedEventConstants):
    """Der Stillstand, maschinenpruefbar - nicht als Behauptung ueber den Ablauf."""

    def _a_blocked_and_a_mergeable_segment(self) -> list[Segment]:
        """Ein Einzelfoto, dessen EINZIGE Kante die Ueberbrueckungsgrenze reisst (es bleibt
        gesperrt), und dahinter ein zweites Einzelfoto, das zugeschlagen werden darf.

        Gesperrt wird hier ueber einen RIEGEL, nicht mehr ueber eine Ursache: Seit ADR 0119 haelt
        keine Ursachenmenge eine Kante mehr fest."""
        return [
            _tiny(timedelta(0), first_id=1),
            _tiny(_merge_gap() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
            _normal_from(_merge_gap() + 2 * EPSILON_TIME, first_id=20, causes={BOUNDARY_TIME_GAP}),
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


class TestWhyASegmentCouldNotBeMerged(_UnderShiftedEventConstants):
    """Block F: Je zu kleinem Segment, das NICHT zugeschlagen werden konnte, steht fest, welche
    Gruende an seinen Kanten standen.

    JE KANTE EINE MENGE, nie ein einzelner Grund: Mehrere Riegel duerfen gleichzeitig zutreffen,
    und eine Meldung mit einem Grund je Kante unterschluege die spaeter geprueften - `ausdehnung`
    steht als letzter und ist genau die Zahl, an der die Frage dieses Blocks haengt.

    EIN SEGMENT HAT SO VIELE KANTEN, WIE ES NACHBARN HAT. Eine nicht vorhandene Seite ist kein
    Hindernis; sie als Kante zu fuehren verfaelschte "an allen Kanten der Grund" - die einzige
    handlungsleitende Spalte - bei jedem Randsegment. `kein_nachbar` greift nur, wenn es
    ueberhaupt keinen Nachbarn gibt."""

    def _tiny_between(
        self,
        *,
        gap_after: timedelta = EPSILON_TIME,
        meters_before: float = 0.0,
        causes: Collection[str] = (BOUNDARY_TIME_GAP,),
    ) -> list[Segment]:
        return [
            _normal_until(timedelta(0), first_id=1, meters_north=meters_before),
            _tiny(EPSILON_TIME, first_id=10, causes=causes),
            _normal_from(EPSILON_TIME + gap_after, first_id=20, causes={BOUNDARY_TIME_GAP}),
        ]

    def test_nothing_is_reported_when_everything_could_be_merged(self) -> None:
        """Der ROT-ANKER: Ohne ihn bestuenden die Faelle darunter auch dann, wenn jede beliebige
        Lage als gesperrt gemeldet wuerde."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        outcome = merge_small_segments(segments)

        assert outcome.dissolved_boundaries == 1
        assert outcome.blocked_segments == ()

    def test_a_segment_at_the_minimum_is_no_case_of_this_block(self) -> None:
        """Riegel (d) haengt an der AUSWAHL, nicht an einer Kante: Ein Segment, das nicht zu klein
        ist, wird gar nicht erst betrachtet - und taucht deshalb mit keinem Grund auf."""
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _normal_from(_merge_gap() + EPSILON_TIME, first_id=100, causes={BOUNDARY_TIME_GAP}),
        ]

        assert merge_small_segments(segments).blocked_segments == ()

    def test_the_gap_to_the_neighbour(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1),
            _tiny(_merge_gap() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_TIME_GAP}),)

    def test_the_duration_of_the_result(self) -> None:
        segments = [
            _normal_spanning_the_maximum(first_id=1),
            _tiny(_max_span() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_SPAN}),)

    def test_the_extent_of_the_result(self) -> None:
        segments = [
            _normal_until(timedelta(0), first_id=1, meters_north=0.0),
            _tiny(
                EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_TIME_GAP},
                meters_north=_merge_extent_max() + EPSILON_METERS,
            ),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_EXTENT}),)

    def test_a_segment_without_any_neighbour_at_all(self) -> None:
        """`kein_nachbar` greift NUR hier - ein einziges Segment im ganzen Lauf. Eine bloss
        fehlende SEITE eines Randsegments ist kein Hindernis und zaehlt nicht als Kante."""
        [blocked] = merge_small_segments([_tiny(timedelta(0), first_id=1)]).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_NO_NEIGHBOUR}),)

    def test_a_segment_at_the_edge_of_the_run_has_exactly_one_edge(self) -> None:
        """Die fehlende Seite taucht NICHT auf. Als eigene Kante gefuehrt, faende sich dieses
        Segment in "an allen Kanten der Grund" bei keinem einzigen Grund wieder - obwohl die
        Ausdehnung dort der Grund war."""
        segments = [
            _tiny(timedelta(0), first_id=1, meters_north=0.0),
            _normal_from(
                EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_TIME_GAP},
                meters_north=_merge_extent_max() + EPSILON_METERS,
            ),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_EXTENT}),)

    def test_two_neighbours_can_stand_for_two_different_reasons(self) -> None:
        """Genau die Lage, fuer die es zwei Zahlen braucht: Keiner der beiden Gruende stand an
        allen Kanten, und eine Zaehlung nur ueber "beteiligt" legte beide Behebungen nahe."""
        segments = [
            _normal_until(
                timedelta(0), first_id=1, meters_north=_merge_extent_max() + EPSILON_METERS
            ),
            _tiny(EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
            _normal_from(_merge_gap() + 2 * EPSILON_TIME, first_id=20, causes={BOUNDARY_TIME_GAP}),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (
            frozenset({MERGE_BLOCK_EXTENT}),
            frozenset({MERGE_BLOCK_TIME_GAP}),
        )

    def test_an_edge_that_violates_several_bolts_reports_them_all(self) -> None:
        """NICHT KURZGESCHLOSSEN, dieselbe Zusage wie fuer die Signale des Durchlaufs
        (`TestSignalsAreNeverShortCircuited`): Alle drei werden ausgewertet. Sonst verschwaende
        `ausdehnung` als zuletzt geprueftes hinter jedem frueheren Grund - und das ist genau die
        Zahl, an der die Frage dieses Blocks haengt. Eine Lage, die ALLE DREI zugleich verletzt."""
        segments = [
            _normal_spanning_the_maximum(first_id=1),
            _tiny(
                _max_span() + _merge_gap() + EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_TIME_GAP},
                meters_north=_merge_extent_max() + EPSILON_METERS,
            ),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (
            frozenset({MERGE_BLOCK_TIME_GAP, MERGE_BLOCK_SPAN, MERGE_BLOCK_EXTENT}),
        )

    def test_the_extent_is_reported_next_to_an_earlier_bolt(self) -> None:
        """Der Fall, den der Kurzschluss verschluckte: Zeitluecke UND Ausdehnung an derselben
        Kante. Wer nur die Zeitluecke lockert, steht danach vor der Ausdehnung."""
        segments = [
            _normal_until(timedelta(0), first_id=1, meters_north=0.0),
            _tiny(
                _merge_gap() + EPSILON_TIME,
                first_id=10,
                causes={BOUNDARY_TIME_GAP},
                meters_north=_merge_extent_max() + EPSILON_METERS,
            ),
        ]

        [blocked] = merge_small_segments(segments).blocked_segments

        assert blocked.edges == (frozenset({MERGE_BLOCK_TIME_GAP, MERGE_BLOCK_EXTENT}),)

    def test_every_reported_reason_comes_from_the_closed_supply(self) -> None:
        """Der Vorrat ist geschlossen: Ein Grund ausserhalb stuende in keiner Zeile des Berichts,
        ohne dass eine Summe kleiner wuerde. Und keine Kante ist leer - eine offene Kante waere
        ein zulaessiger Nachbar, dann waere das Segment gar nicht gesperrt."""
        for segments in (
            self._tiny_between(gap_after=_merge_gap()),
            [_tiny(timedelta(0), first_id=1)],
            [
                _normal_spanning_the_maximum(first_id=1),
                _tiny(_max_span() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
            ],
        ):
            for blocked in merge_small_segments(segments).blocked_segments:
                for edge in blocked.edges:
                    assert edge, "eine leere Kante waere ein zulaessiger Nachbar"
                    assert edge <= set(MERGE_BLOCK_REASONS)
                assert 1 <= len(blocked.edges) <= 2, "so viele Kanten, wie es Nachbarn gibt"

    def test_the_supply_is_exactly_these_five(self) -> None:
        assert MERGE_BLOCK_REASONS == (
            MERGE_BLOCK_UNBREAKABLE,
            MERGE_BLOCK_TIME_GAP,
            MERGE_BLOCK_SPAN,
            MERGE_BLOCK_EXTENT,
            MERGE_BLOCK_NO_NEIGHBOUR,
        )

    def test_exactly_the_segments_that_stayed_too_small_are_reported(self) -> None:
        """Die Bilanz statt einer Behauptung ueber den Ablauf: Beobachtet wird, was tatsaechlich
        stehen geblieben ist - nicht mehr und nicht weniger."""
        segments = [
            _tiny(timedelta(0), first_id=1, causes=()),
            _tiny(_merge_gap() + EPSILON_TIME, first_id=10, causes={BOUNDARY_TIME_GAP}),
            _normal_from(
                2 * _merge_gap() + 2 * EPSILON_TIME, first_id=20, causes={BOUNDARY_TIME_GAP}
            ),
        ]

        outcome = merge_small_segments(segments)

        still_small = [
            segment
            for segment in outcome.segments
            if len(segment.members) < events_module.MIN_EVENT_PHOTOS
        ]
        assert len(outcome.blocked_segments) == len(still_small) == 2

    def test_the_observation_reaches_the_explaining_form(self) -> None:
        """Ohne diesen Weg bliebe die Diagnose in der Stufe stehen, und das Messkommando muesste
        sie nachbilden - es maesse dann etwas anderes, als die Stufe tut."""
        minimum = events_module.MIN_EVENT_PHOTOS
        gap = _merge_gap() + EPSILON_TIME
        # Das erste Segment traegt GENAU die Mindestgroesse - unter einer anderen waere es selbst
        # zu klein und zoege sich in den Fall hinein, den der Fall nicht misst.
        candidates = [
            _placeless_candidate(index, T0 + index * EPSILON_TIME) for index in range(minimum)
        ]
        candidates.append(_placeless_candidate(minimum, T0 + (minimum - 1) * EPSILON_TIME + gap))

        formation = explain_events(candidates)

        assert [event.photo_ids for event in formation.events] == [
            tuple(range(minimum)),
            (minimum,),
        ]
        [blocked] = formation.blocked_segments
        assert blocked.edges == (frozenset({MERGE_BLOCK_TIME_GAP}),)


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
