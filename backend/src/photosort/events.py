"""Event-Bildung: die Gliederung eines Kriterien-Laufs in Einheiten mit Anfang, Ende, Ort und
Namen.

REIN und DB-FREI. Bewusst nicht in `scoring.py` - das ist Phase A (`assign_clusters`, vor dem
Ausschuss-Gate) und bleibt davon unberuehrt.

LOGGING-AUFLAGE fuer jede kuenftige Logzeile dieses Moduls: Koordinaten gehoeren NIE ins Log, ein
Sehenswuerdigkeit-Name nur als `%r` und laengenbegrenzt.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from photosort.scoring import (
    GPS_CLUSTER_SPLIT_DISTANCE_METERS,
    TIME_CLUSTER_GAP,
    haversine_meters,
)

# Raeumliche Ausdehnung, ab der ein neues Event beginnt - gleichrangig neben TIME_CLUSTER_GAP.
# Dokumentierte, UNKALIBRIERTE Modulkonstante im Muster von TIME_CLUSTER_GAP/
# GPS_CLUSTER_SPLIT_DISTANCE_METERS, bewusst kein Settings-/Env-Wert.
#
# Groessenordnung Stadtviertel: ueber der Streuung eines einzelnen Ortsbesuchs (100-300 m) und
# ueber der Schrittschwelle von 500 m. Der Wert ist aenderbar und durch keinen Test gepinnt - ein
# Test auf den Zahlwert waere eine Spiegelung des Codes.
EVENT_EXTENT_MAX_METERS = 1000.0

# Anzeigerundung der Event-Koordinate: zwei Nachkommastellen entsprechen rund 1,1 km (Vorgabe
# "grob, ~1 km"). Die Rundung liegt im BACKEND, nie im Frontend - dieselbe Zahl entscheidet hier
# ueber `"coordinate"` vs. `"multiple"`, und diese Stufe ist ohne das vollstaendige Event nicht
# bestimmbar.
_EVENT_PLACE_COORDINATE_DIGITS = 2

# Der geschlossene Vorrat von `events.place_kind`. Ein Wert ausserhalb ist ein Datenfehler und
# wird im Lesepfad zu "kein Ortsbezug", nie zu einer 500.
PLACE_KINDS = ("landmark", "coordinate", "multiple")


@dataclass(frozen=True)
class LocationEntry:
    """Ein Foto der Inferenzbasis - JEDES Foto des Projekts, auch ein aussortiertes."""

    photo_id: int
    taken_at: datetime
    gps_lat: float | None = None
    gps_lon: float | None = None


@dataclass(frozen=True)
class EffectiveLocation:
    """Der WIRKSAME Ort eines Fotos: eigene Messung oder uebernommener Ort.

    `inferred` traegt die Zusage, dass ein uebernommener Ort nie als gemessener ausgegeben wird -
    er speist `PhotoOut.location.source == "derived"` und NIE den Ortsbezug eines Events."""

    lat: float
    lon: float
    inferred: bool


def _measured(entry: LocationEntry) -> tuple[float, float] | None:
    """Die Koordinate eines Eintrags - `None`, sobald auch nur eine Komponente fehlt.

    `extract_gps` liefert nie eine halbe Koordinate (Paar-Invariante); ein einzelner gesetzter
    Wert ergaebe hier eine Position auf dem Nullmeridian bzw. dem Aequator."""
    if entry.gps_lat is None or entry.gps_lon is None:
        return None
    return entry.gps_lat, entry.gps_lon


def infer_locations(entries: Iterable[LocationEntry]) -> dict[int, EffectiveLocation]:
    """Der wirksame Ort JEDES Fotos der uebergebenen Menge, projektweit hergeleitet.

    Ein Foto ohne eigene Koordinate uebernimmt die des zeitlich naechstgelegenen Fotos MIT
    Koordinate. Tie-Break (deterministisch, sonst haengt das Ergebnis an der Zeilenreihenfolge der
    Datenbank): bei gleichem Abstand gewinnt der FRUEHERE Zeitpunkt, bei identischem `taken_at` die
    kleinere `photo_id`.

    Ohne jeden Anker erbt niemand - das Ergebnis enthaelt dann keinen Eintrag.

    Die Bezugsmenge ist AUSDRUECKLICH das ganze Projekt, nicht die Kandidatenmenge und nicht das
    Event: ein aussortiertes Foto traegt eine ebenso gueltige Koordinate, und eine Herleitung aus
    dem fertigen Event waere zirkulaer. Die Bindung an `Photo.project_id` liegt beim Aufrufer und
    steht dort ausgeschrieben - ohne sie erbt ein Foto Koordinaten aus einem fremden Projekt."""
    entry_list = list(entries)
    anchors = sorted(
        (entry for entry in entry_list if _measured(entry) is not None),
        key=lambda entry: (entry.taken_at, entry.photo_id),
    )

    result: dict[int, EffectiveLocation] = {}
    for entry in entry_list:
        measured = _measured(entry)
        if measured is not None:
            result[entry.photo_id] = EffectiveLocation(
                lat=measured[0], lon=measured[1], inferred=False
            )
            continue
        if not anchors:
            continue
        # Suche ueber `key=` direkt auf `anchors` - keine vorgeschaltete Zeitstempelliste, die
        # waere je Foto erneut linear und machte den `bisect` zur Zierde.
        index = bisect_left(anchors, entry.taken_at, key=lambda anchor: anchor.taken_at)
        nearest = anchors[min(index, len(anchors) - 1)]
        if index > 0:
            earlier = anchors[index - 1]
            if index >= len(anchors) or (entry.taken_at - earlier.taken_at) <= (
                nearest.taken_at - entry.taken_at
            ):
                nearest = earlier
        nearest_coordinate = _measured(nearest)
        assert nearest_coordinate is not None
        result[entry.photo_id] = EffectiveLocation(
            lat=nearest_coordinate[0], lon=nearest_coordinate[1], inferred=True
        )
    return result


@dataclass(frozen=True)
class EventCandidate:
    """Ein Kandidatenfoto EINES Kriterien-Laufs (die Ausschuss-Ueberlebenden).

    Zwei Ortsangaben nebeneinander, und das ist der Kern: `location` ist der WIRKSAME Ort (eigener
    oder uebernommener) und bestimmt die Grenzen; `gps_lat`/`gps_lon` sind die GEMESSENEN Werte und
    speisen ausschliesslich den Ortsbezug des Events. Eine Ortsaussage ueber eine Einheit darf
    nicht aus Schaetzungen entstehen.

    `landmark_name` kommt bereits durch `sanitize_landmark_name` (worker.py::_landmark_names) -
    `None` heisst "kein verwendbarer Name"."""

    photo_id: int
    taken_at: datetime
    location: EffectiveLocation | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None
    landmark_name: str | None = None


@dataclass(frozen=True)
class BuiltEvent:
    """Ein fertiges Event, bereit zum Persistieren.

    FELDKOMBINATION (gepruefte Invariante): `place_kind='landmark'` ⇒ `landmark_name` gesetzt;
    `'coordinate'` ⇒ beide Koordinaten gesetzt; `'multiple'` ⇒ beide Koordinaten NULL (den einen
    Ort, den sie vertreten muessten, gibt es gerade nicht). Koordinaten stehen GERUNDET, nie in
    voller Praezision. Ohne gemessene Koordinate und ohne Namen ist `place_kind` `None`."""

    position: int
    photo_ids: tuple[int, ...]
    started_at: datetime
    ended_at: datetime
    landmark_name: str | None = None
    place_kind: str | None = None
    place_lat: float | None = None
    place_lon: float | None = None


def _usable_name(name: str | None) -> str | None:
    """Ein Name, der nach Sanitisierung leer ist, gilt als NICHT VORHANDEN - er loest keine Grenze
    aus und wird nicht geschrieben. Verworfen, nie abgeschnitten."""
    return (name or "").strip() or None


class BoundarySignal(Protocol):
    """Ein Trennsignal der Event-Bildung.

    Frage und Fortschreibung sind GETRENNT, und das ist der tragende Teil: nur so darf ein
    zustandsbehaftetes Signal (Ausdehnung) neben einem paarweisen (Zeitluecke) stehen, ohne dass
    die Auswertungsreihenfolge zum Bestandteil des Ergebnisses wird.

    `is_boundary` ist REIN - es aendert keinen Zustand und darf beliebig oft gefragt werden.
    `begin` setzt an einer Grenze zurueck, `advance` schreibt innerhalb des laufenden Events fort;
    je Kandidat laeuft genau eine der beiden."""

    def is_boundary(self, candidate: EventCandidate) -> bool: ...

    def begin(self, candidate: EventCandidate) -> None: ...

    def advance(self, candidate: EventCandidate) -> None: ...


class TimeGapSignal:
    """Die Zeitluecke zwischen zwei aufeinanderfolgenden Fotos - unveraendertes Verhalten,
    `>` und nicht `>=`."""

    def __init__(self, gap: timedelta = TIME_CLUSTER_GAP) -> None:
        self._gap = gap
        self._previous: datetime | None = None

    def is_boundary(self, candidate: EventCandidate) -> bool:
        return self._previous is None or candidate.taken_at - self._previous > self._gap

    def begin(self, candidate: EventCandidate) -> None:
        self._previous = candidate.taken_at

    def advance(self, candidate: EventCandidate) -> None:
        self._previous = candidate.taken_at


class DayBoundarySignal:
    """Der Kalendertag - ein Event reicht nie ueber eine Tagesgrenze hinaus.

    Braucht keinen Zahlwert: verglichen werden die ersten zehn Zeichen des Zeitstempels.
    `taken_at` ist ZONENLOS; eine Zeitzonen-Umrechnung hinge an der Umgebung des ausfuehrenden
    Prozesses."""

    def __init__(self) -> None:
        self._day: str | None = None

    @staticmethod
    def _day_of(candidate: EventCandidate) -> str:
        return candidate.taken_at.isoformat()[:10]

    def is_boundary(self, candidate: EventCandidate) -> bool:
        return self._day is None or self._day_of(candidate) != self._day

    def begin(self, candidate: EventCandidate) -> None:
        self._day = self._day_of(candidate)

    def advance(self, candidate: EventCandidate) -> None:
        self._day = self._day_of(candidate)


class StepDistanceSignal:
    """Der SCHRITT zwischen zwei aufeinanderfolgenden Fotos.

    Bezug ist die letzte WIRKSAME Koordinate des LAUFENDEN Events, nicht der unmittelbare
    zeitliche Vorgaenger: sonst unterdrueckte ein einziges Foto ohne jeden Ort zwischen zwei weit
    auseinanderliegenden Aufnahmen die Trennung vollstaendig. Rueckgesetzt wird an JEDER Grenze,
    auch an einer rein zeitlichen - sonst wuerde das erste Foto eines neuen Events gegen eines aus
    dem vorherigen verglichen und ein zweites Mal getrennt."""

    def __init__(self, split_distance_meters: float = GPS_CLUSTER_SPLIT_DISTANCE_METERS) -> None:
        self._split_distance_meters = split_distance_meters
        self._reference: EffectiveLocation | None = None

    def is_boundary(self, candidate: EventCandidate) -> bool:
        location = candidate.location
        if location is None or self._reference is None:
            return False
        distance = haversine_meters(
            self._reference.lat, self._reference.lon, location.lat, location.lon
        )
        return distance > self._split_distance_meters

    def begin(self, candidate: EventCandidate) -> None:
        self._reference = candidate.location

    def advance(self, candidate: EventCandidate) -> None:
        if candidate.location is not None:
            self._reference = candidate.location


class ExtentSignal:
    """Die AUSDEHNUNG des laufenden Events: die Diagonale der umschliessenden Box aller wirksamen
    Koordinaten, geprueft EINSCHLIESSLICH des gerade betrachteten Fotos - sonst begaenne das neue
    Event ein Foto zu spaet.

    Obere Schranke des Durchmessers bei konstantem Aufwand je Foto; der exakte Durchmesser waere
    quadratisch. Zwei bewusste Kehrseiten: die Schranke trennt etwas frueher, und eine Box ueber
    den 180. Laengengrad faellt maximal gross aus - die Ausfallrichtung ist "trennt", nie
    "behauptet einen Ort"."""

    def __init__(self, max_meters: float = EVENT_EXTENT_MAX_METERS) -> None:
        self._max_meters = max_meters
        self._box: tuple[float, float, float, float] | None = None

    @staticmethod
    def _extended(
        box: tuple[float, float, float, float] | None, location: EffectiveLocation
    ) -> tuple[float, float, float, float]:
        if box is None:
            return (location.lat, location.lat, location.lon, location.lon)
        min_lat, max_lat, min_lon, max_lon = box
        return (
            min(min_lat, location.lat),
            max(max_lat, location.lat),
            min(min_lon, location.lon),
            max(max_lon, location.lon),
        )

    def is_boundary(self, candidate: EventCandidate) -> bool:
        if candidate.location is None or self._box is None:
            return False
        min_lat, max_lat, min_lon, max_lon = self._extended(self._box, candidate.location)
        return haversine_meters(min_lat, min_lon, max_lat, max_lon) > self._max_meters

    def begin(self, candidate: EventCandidate) -> None:
        self._box = None if candidate.location is None else self._extended(None, candidate.location)

    def advance(self, candidate: EventCandidate) -> None:
        if candidate.location is not None:
            self._box = self._extended(self._box, candidate.location)


class LandmarkChangeSignal:
    """Die Sehenswuerdigkeit als TRENNSIGNAL statt als Gruppierungsmerkmal.

    Grenze NUR, wenn Kandidat und laufendes Event je einen nicht-leeren, VERSCHIEDENEN Namen
    tragen. Namenlose Fotos loesen nie aus, und ein einmal gesetzter Name des laufenden Events
    ueberlebt namenlose Fotos - sonst zerrisse eine Aufnahme ohne Erkennung den Ortsbesuch.

    Exakter Zeichenkettenvergleich, KEIN Fuzzy-Matching (bewusste Vereinfachung): zwei
    Schreibweisen-Varianten desselben Orts trennen."""

    def __init__(self) -> None:
        self._name: str | None = None

    def is_boundary(self, candidate: EventCandidate) -> bool:
        name = _usable_name(candidate.landmark_name)
        return name is not None and self._name is not None and name != self._name

    def begin(self, candidate: EventCandidate) -> None:
        self._name = _usable_name(candidate.landmark_name)

    def advance(self, candidate: EventCandidate) -> None:
        if self._name is None:
            self._name = _usable_name(candidate.landmark_name)


def default_signals() -> list[BoundarySignal]:
    """Die fuenf Trennsignale, gleichrangig, in einer LISTE.

    Die Liste ist der Erweiterungspunkt: ein weiteres Signal ist eine Klasse und ein Eintrag - kein
    Eingriff in den Durchlauf, das Datenmodell oder die API.

    Jeder Aufruf liefert FRISCHE Objekte: Signale sind zustandsbehaftet, eine geteilte Liste
    tarnte einen Lauf als Fortsetzung des vorherigen."""
    return [
        TimeGapSignal(),
        DayBoundarySignal(),
        StepDistanceSignal(),
        ExtentSignal(),
        LandmarkChangeSignal(),
    ]


def _rounded(value: float) -> float:
    """Auf die Anzeigegenauigkeit gerundet, mit `-0.0` normalisiert auf `0.0`.

    `-0.0` waere im JSON `-0.0` und in der Anzeige `"-0.00"` - eine Himmelsrichtung, die es nicht
    gibt. Die Addition von `0.0` erledigt das nach IEEE 754 ohne Sonderfallzweig."""
    return round(value, _EVENT_PLACE_COORDINATE_DIGITS) + 0.0


def _place_of(members: Sequence[EventCandidate]) -> tuple[str | None, float | None, float | None]:
    """Die Stufenentscheidung ueber das VOLLSTAENDIGE Event, ausschliesslich aus GEMESSENEN Werten.

    Rangfolge: erkannte Sehenswuerdigkeit -> genau eine gerundete Koordinatenzelle -> mehrere Orte
    -> kein Ortsbezug. Der Name hat Vorrang auch dann, wenn zusaetzlich abweichende Koordinaten
    vorliegen.

    `members` ist nach `(taken_at, photo_id)` sortiert: ein Event traegt hoechstens EINEN Namen
    (dafuer sorgt `LandmarkChangeSignal`) - defensiv gewinnt der des fruehesten Fotos."""
    for member in members:
        name = _usable_name(member.landmark_name)
        if name is not None:
            return "landmark", None, None

    # VERGLICHEN WIRD DIE GERUNDETE Zelle, nicht der Rohwert: ein Vergleich der ungerundeten Werte
    # schluege schon bei zwei 40 m auseinanderliegenden Aufnahmen zu und machte aus einem einzelnen
    # Ortsbesuch "Mehrere Orte".
    cells = {
        (_rounded(member.gps_lat), _rounded(member.gps_lon))
        for member in members
        if member.gps_lat is not None and member.gps_lon is not None
    }
    if not cells:
        return None, None, None
    if len(cells) > 1:
        return "multiple", None, None
    [(lat, lon)] = cells
    return "coordinate", lat, lon


def _name_of(members: Sequence[EventCandidate]) -> str | None:
    for member in members:
        name = _usable_name(member.landmark_name)
        if name is not None:
            return name
    return None


def _built(position: int, members: Sequence[EventCandidate]) -> BuiltEvent:
    place_kind, place_lat, place_lon = _place_of(members)
    return BuiltEvent(
        position=position,
        photo_ids=tuple(member.photo_id for member in members),
        started_at=members[0].taken_at,
        ended_at=members[-1].taken_at,
        landmark_name=_name_of(members),
        place_kind=place_kind,
        place_lat=place_lat,
        place_lon=place_lon,
    )


def build_events(
    candidates: Iterable[EventCandidate], signals: list[BoundarySignal] | None = None
) -> list[BuiltEvent]:
    """Die Event-Bildung: EIN sortierter Durchlauf ueber die Kandidaten eines Kriterien-Laufs.

    Das Ergebnis ist chronologisch geordnet und ueberschneidungsfrei, `position` laeuft
    lueckenlos ab 1, und jeder uebergebene Kandidat steht in genau einem Event.

    Der Durchlauf wertet ALLE Signale aus - `any` ueber eine bereits gebaute LISTE, ausdruecklich
    NICHT kurzgeschlossen - und ruft danach genau eine der schreibenden Methoden auf ALLEN auf.
    Wuerde die Auswertung beim ersten `True` abbrechen, haenge die Zustandsfortschreibung eines
    Signals an seiner Listenposition.

    `signals` ist injizierbar; ohne Angabe gilt `default_signals()`."""
    ordered = sorted(candidates, key=lambda candidate: (candidate.taken_at, candidate.photo_id))
    active = default_signals() if signals is None else signals

    events: list[list[EventCandidate]] = []
    for candidate in ordered:
        # Die Liste wird VOLLSTAENDIG gebaut, bevor `any` sie liest.
        boundary = any([signal.is_boundary(candidate) for signal in active])
        if boundary or not events:
            for signal in active:
                signal.begin(candidate)
            events.append([])
        else:
            for signal in active:
                signal.advance(candidate)
        events[-1].append(candidate)

    return [_built(position, members) for position, members in enumerate(events, start=1)]
