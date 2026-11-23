"""Gemeinsame Bausteine der Ereignis-Gruppierungstests."""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping, Sequence
from datetime import datetime, timedelta
from fractions import Fraction

import pytest

from photosort import events as events_module
from photosort import scoring as scoring_module
from photosort.events import (
    BOUNDARY_MOTIF_CHANGE,
    BoundarySignal,
    BuiltEvent,
    EffectiveLocation,
    EventCandidate,
    EventFormation,
    build_events,
    default_signals,
    explain_events,
    location_excursions,
)
from photosort.scoring import haversine_meters

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
    return BASE_LAT + math.degrees(distance_meters / scoring_module.EARTH_RADIUS_METERS)


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


def _confirming(
    *names: str, at: tuple[float, float] = (BASE_LAT, BASE_LON)
) -> dict[str, tuple[tuple[float, float], ...]]:
    """Eine Sehenswuerdigkeitsauskunft, die jeden genannten Namen am Ort `at` BESTAETIGT.

    Die Pruefung ist fail-closed: Ein Fall, der einen Namen erwartet, braucht gemessene Kandidaten
    in der Naehe von `at` und diese Auskunft - ohne sie faellt jeder Name."""
    return {name: (at,) for name in names}


# Die Staerken der Motivfaelle stehen ausschliesslich als SYMBOL zur Praesenzgrenze - kein Fall
# nennt ihren Zahlwert. `_AT_THRESHOLD` und `_JUST_BELOW` sind das Paar, an dem ein in `events.py`
# nachgebautes `>` statt des geteilten inklusiven `>=` rot wird.
_ABOVE = 1.0


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
    # bezeugt ihn mindestens `LANDMARK_MIN_SHARE` seiner Mitglieder. Gezaehlt ueber `usable_name` -
    # dieselbe Traegerdefinition, die die Produktion benutzt, statt einer zweiten Fassung hier.
    name_by_photo = {
        candidate.photo_id: events_module.usable_name(candidate.landmark_name)
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
    injizierte Teilmenge kennt die Riegel nicht und darf sie ueberschreiten.

    Ein Ausreisser (`location_excursions`) geht ohne Ort in die Bildung ein und zaehlt deshalb auch
    hier nicht zur Box."""
    ordered = sorted(candidates, key=lambda candidate: (candidate.taken_at, candidate.photo_id))
    excursions = location_excursions(ordered)
    location_by_id = {
        candidate.photo_id: None if candidate.photo_id in excursions else candidate.location
        for candidate in candidates
    }
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
    Vorgabe `None` heisst "keine Auskunft vorhanden" - jeder Name faellt (fail-closed); wer einen
    Namen erwartet, gibt `_confirming(...)` mit."""
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
