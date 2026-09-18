"""Event-Bildung: die Gliederung eines Kriterien-Laufs in Einheiten mit Anfang, Ende, Ort und
Namen.

REIN und DB-FREI. Bewusst nicht in `scoring.py` - das ist Phase A (`assign_clusters`, vor dem
Ausschuss-Gate) und bleibt davon unberuehrt.

LOGGING-AUFLAGE fuer jede kuenftige Logzeile dieses Moduls: Koordinaten gehoeren NIE ins Log, ein
Sehenswuerdigkeit-Name nur als `%r` und laengenbegrenzt.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from photosort.places import (
    MAX_PLACE_NAME_LENGTH,
    PlaceInfo,
    place_cell,
    usable_locality,
)
from photosort.scoring import (
    GPS_CLUSTER_SPLIT_DISTANCE_METERS,
    TIME_CLUSTER_GAP,
    haversine_meters,
)
from photosort.selection import carried_motifs

# Raeumliche Ausdehnung, ab der ein neues Event beginnt - gleichrangig neben TIME_CLUSTER_GAP.
# Dokumentierte, UNKALIBRIERTE Modulkonstante im Muster von TIME_CLUSTER_GAP/
# GPS_CLUSTER_SPLIT_DISTANCE_METERS, bewusst kein Settings-/Env-Wert.
#
# Groessenordnung Stadtviertel: ueber der Streuung eines einzelnen Ortsbesuchs (100-300 m) und
# ueber der Schrittschwelle von 500 m. Der Wert ist aenderbar und durch keinen Test gepinnt - ein
# Test auf den Zahlwert waere eine Spiegelung des Codes.
EVENT_EXTENT_MAX_METERS = 1000.0

# Der geschlossene Vorrat von `events.place_kind`. Ein Wert ausserhalb ist ein Datenfehler und
# wird im Lesepfad zu "kein Ortsbezug", nie zu einer 500.
PLACE_KINDS = ("landmark", "coordinate", "multiple")

# Groesse, unter der ein Segment als zu klein gilt. Dokumentierte, UNKALIBRIERTE Modulkonstante im
# Muster von EVENT_EXTENT_MAX_METERS, bewusst kein Settings-/Env-Wert.
#
# Ein Wert von 1 hiesse "kein Segment ist je zu klein" - `MIN_EVENT_PHOTOS >= 2` ist die einzige
# Aussage, die ein Test ueber diesen Wert treffen darf, und sie ist eine Ungleichung.
MIN_EVENT_PHOTOS = 2

# --- Der geschlossene Vorrat der TRENNURSACHEN (ADR 0117 Punkt 4) -------------------------------
#
# Jede Grenze traegt die MENGE der Signale, die sie gemeldet haben, nie ein einzelnes: Der
# Durchlauf wertet alle aus, mehrere duerfen gleichzeitig zutreffen, und ein Bericht mit einer
# Ursache je Grenze addierte sich zu mehr als hundert Prozent oder unterschluege Ursachen.
BOUNDARY_TIME_GAP = "zeitluecke"
BOUNDARY_CALENDAR_DAY = "kalendertag"
BOUNDARY_STEP = "schritt"
BOUNDARY_EXTENT = "ausdehnung"
BOUNDARY_LANDMARK = "sehenswuerdigkeit"
# Kein Eintrag in `default_signals()`: Der Motivwechsel ist eine Segmentierung ueber die ganze
# Folge (ADR 0109) und trennt als ERZWUNGENER START. Er braucht trotzdem seinen Namen, sonst
# stuende in der Statistik eine Grenze ohne Ursache.
BOUNDARY_MOTIF_CHANGE = "motivwechsel"

BOUNDARY_CAUSES = (
    BOUNDARY_TIME_GAP,
    BOUNDARY_CALENDAR_DAY,
    BOUNDARY_STEP,
    BOUNDARY_EXTENT,
    BOUNDARY_LANDMARK,
    BOUNDARY_MOTIF_CHANGE,
)

# Wie viele aufeinanderfolgende mitredende Fotos einen Motivwechsel bestaetigen muessen, das erste
# abweichende eingeschlossen. Dokumentierte, UNKALIBRIERTE Modulkonstante im Muster von
# EVENT_EXTENT_MAX_METERS - aenderbar, durch keinen Test auf den Zahlwert gepinnt.
# Ein Wert von 1 widerspraeche der Zusage "ein einzelnes abweichendes Foto trennt nie".
MOTIF_CHANGE_CONFIRMING_PHOTOS = 3


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


def _anchors(entry_list: Sequence[LocationEntry]) -> list[LocationEntry]:
    """Die koordinatentragenden Fotos, zeitlich geordnet.

    Der Tie-Break der Ordnung traegt die Zusage "bei identischem `taken_at` gewinnt die kleinere
    `photo_id`" - ohne ihn haengt das Ergebnis an der Zeilenreihenfolge der Datenbank."""
    return sorted(
        (entry for entry in entry_list if _measured(entry) is not None),
        key=lambda entry: (entry.taken_at, entry.photo_id),
    )


def _anchor_neighbours(
    anchors: Sequence[LocationEntry], entry: LocationEntry
) -> tuple[LocationEntry | None, LocationEntry | None]:
    """Die beiden koordinatentragenden Nachbarn eines Zeitpunkts - frueher und spaeter.

    Suche ueber `key=` direkt auf `anchors` - keine vorgeschaltete Zeitstempelliste, die waere je
    Foto erneut linear und machte den `bisect` zur Zierde."""
    index = bisect_left(anchors, entry.taken_at, key=lambda anchor: anchor.taken_at)
    earlier = anchors[index - 1] if index > 0 else None
    later = anchors[index] if index < len(anchors) else None
    return earlier, later


def _nearest_anchor(anchors: Sequence[LocationEntry], entry: LocationEntry) -> LocationEntry | None:
    """Der Anker, den ein Foto ohne eigene Koordinate uebernimmt - `None` ohne jeden Anker.

    DIE EINE STELLE, an der die Wahl faellt: `infer_locations` erbt danach, und
    `inherited_locations` misst den Abstand gegen genau diesen Anker. Eine zweite Fassung maesse
    den Abstand zu einem Anker, den das Foto gar nicht geerbt hat.

    Tie-Break (deterministisch): bei gleichem Abstand gewinnt der FRUEHERE Zeitpunkt."""
    earlier, later = _anchor_neighbours(anchors, entry)
    if earlier is None:
        return later
    if later is None:
        return earlier
    if (entry.taken_at - earlier.taken_at) <= (later.taken_at - entry.taken_at):
        return earlier
    return later


@dataclass(frozen=True)
class InheritedLocation:
    """Was eine Ortsuebernahme ueber SICH SELBST aussagt - OHNE jede Koordinate (Block C1).

    `seconds_to_anchor` ist der Abstand zu dem Anker, den dieses Foto tatsaechlich geerbt hat.
    `anchor_span_meters` ist die Entfernung zwischen dem vorherigen und dem naechsten
    koordinatentragenden Foto: Liegen die beiden weit auseinander, ist die Uebernahme ein
    Muenzwurf, und das ist ohne jede aeussere Wahrheit belegbar.

    `None` heisst "es gibt nur einen Nachbarn, also keine Spanne" und ausdruecklich NICHT `0` -
    eine Null hiesse "beide Nachbarn liegen am selben Ort" und waere die guenstigste aller
    Aussagen ueber eine Uebernahme."""

    photo_id: int
    seconds_to_anchor: float
    anchor_span_meters: float | None


def inherited_locations(entries: Iterable[LocationEntry]) -> list[InheritedLocation]:
    """Je Foto OHNE eigene Koordinate, das tatsaechlich erbt, eine Auskunft ueber die Uebernahme.

    OEFFENTLICH, weil das Messkommando Block C1 ueber genau diese Wahl zaehlt - dieselbe
    Ankerwahl, die `infer_locations` trifft. Ein Foto ohne jeden Anker erbt nicht und erscheint
    hier nicht: es gibt nichts zu berichten, und eine Zeile mit Null-Abstand behauptete eine
    Uebernahme, die nicht stattfand.

    SICHERHEIT (S5): Die Rueckgabe traegt Zahlen, keine Orte. Wer sie ausgibt, tut das in
    Klassen - eine geordnete Folge von Spannen und Zeitlücken waere ein Streckenabdruck."""
    entry_list = list(entries)
    anchors = _anchors(entry_list)
    if not anchors:
        return []

    reports: list[InheritedLocation] = []
    for entry in entry_list:
        if _measured(entry) is not None:
            continue
        nearest = _nearest_anchor(anchors, entry)
        if nearest is None:  # pragma: no cover - `anchors` ist nicht leer
            continue
        earlier, later = _anchor_neighbours(anchors, entry)
        span: float | None = None
        if earlier is not None and later is not None:
            earlier_coordinate = _measured(earlier)
            later_coordinate = _measured(later)
            assert earlier_coordinate is not None and later_coordinate is not None
            span = haversine_meters(
                earlier_coordinate[0],
                earlier_coordinate[1],
                later_coordinate[0],
                later_coordinate[1],
            )
        reports.append(
            InheritedLocation(
                photo_id=entry.photo_id,
                seconds_to_anchor=abs((entry.taken_at - nearest.taken_at).total_seconds()),
                anchor_span_meters=span,
            )
        )
    return reports


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
    anchors = _anchors(entry_list)

    result: dict[int, EffectiveLocation] = {}
    for entry in entry_list:
        measured = _measured(entry)
        if measured is not None:
            result[entry.photo_id] = EffectiveLocation(
                lat=measured[0], lon=measured[1], inferred=False
            )
            continue
        nearest = _nearest_anchor(anchors, entry)
        if nearest is None:
            continue
        nearest_coordinate = _measured(nearest)
        assert nearest_coordinate is not None
        result[entry.photo_id] = EffectiveLocation(
            lat=nearest_coordinate[0], lon=nearest_coordinate[1], inferred=True
        )
    return result


@dataclass(frozen=True)
class EventSpan:
    """Die Zeitspanne EINES fertigen Events - die Lesesicht auf eine `events`-Zeile.

    BEIDE GRENZEN SIND INKLUSIV: `started_at` und `ended_at` sind die Aufnahmezeiten des ersten
    und des letzten Fotos des Events, nicht die Raender eines halboffenen Intervalls."""

    event_id: int
    started_at: datetime
    ended_at: datetime


def _span_order(span: EventSpan) -> tuple[datetime, datetime, int]:
    """Die eine Ordnung, in der `event_for_time` die Spannen betrachtet.

    Sie traegt den Tie-Break: "das FRUEHERE Event gewinnt" ist der erste Eintrag dieser Ordnung.
    Die beiden hinteren Bestandteile machen sie total - ohne sie haengt das Ergebnis bei zwei
    gleich beginnenden Spannen an der Reihenfolge der Abfrage, die ohne `ORDER BY` nichts
    zusichert."""
    return (span.started_at, span.ended_at, span.event_id)


def _distance_to(span: EventSpan, taken_at: datetime) -> timedelta:
    """Der Abstand einer Zeit zur naechstgelegenen GRENZE der Spanne - `0` innerhalb.

    Gemessen wird gegen BEIDE Grenzen. Eine Messung allein gegen `started_at` beantwortet eine
    Zeit kurz vor dem Ende eines langen Events falsch; `event_for_time` faengt diesen Fall zwar
    schon ueber das Enthaltensein ab, aber die Formel bliebe fuer jede Zeit AUSSERHALB eines
    langen Events daneben."""
    if taken_at < span.started_at:
        return span.started_at - taken_at
    if taken_at > span.ended_at:
        return taken_at - span.ended_at
    return timedelta(0)


def event_for_time(spans: Iterable[EventSpan], taken_at: datetime) -> int | None:
    """Das Event, zu dem eine Aufnahmezeit gehoert - `None` ohne jede Spanne.

    ZWEI STUFEN, und die Reihenfolge ist die Zusage: ENTHALTENSEIN SCHLAEGT NAEHE. Liegt die Zeit
    in einer Spanne (beide Grenzen inklusiv), gewinnt diese; erst sonst entscheidet der kleinste
    Abstand zu einer Grenze. Bei Gleichstand - beruehrende Spannen (`ended_at(A) ==
    started_at(B)`) ebenso wie zwei gleich weit entfernte Events - gewinnt das FRUEHERE Event.

    REIN und ohne Uhr; die Reihenfolge der uebergebenen Spannen wirkt sich nicht aus.

    Aufrufer ist der Entwurfszweig von `api/photos.py` fuer die vom Nutzer aufgenommenen Fotos
    ohne Rangzeile. Die Spannenliste wird dort EINMAL geladen und fuer alle Fotos wiederverwendet
    (Auflage S14) - nie eine Abfrage je Foto."""
    ordered = sorted(spans, key=_span_order)
    if not ordered:
        return None
    # `min` liefert bei Gleichstand den ERSTEN Treffer der Eingabefolge - und die ist nach
    # `_span_order` sortiert. Der Tie-Break steht damit an genau einer Stelle.
    nearest = min(ordered, key=lambda span: _distance_to(span, taken_at))
    return nearest.event_id


@dataclass(frozen=True)
class EventCandidate:
    """Ein Kandidatenfoto EINES Kriterien-Laufs (die Ausschuss-Ueberlebenden).

    Zwei Ortsangaben nebeneinander, und das ist der Kern: `location` ist der WIRKSAME Ort (eigener
    oder uebernommener) und bestimmt die Grenzen; `gps_lat`/`gps_lon` sind die GEMESSENEN Werte und
    speisen ausschliesslich den Ortsbezug des Events. Eine Ortsaussage ueber eine Einheit darf
    nicht aus Schaetzungen entstehen.

    `landmark_name` kommt bereits durch `sanitize_landmark_name` (worker.py::_landmark_names) -
    `None` heisst "kein verwendbarer Name".

    `motif_strengths` traegt die WIRKSAMEN Staerken (Nutzerkorrektur inbegriffen). `None` heisst
    "keine Motiv-Kopfzeile" und ist ausdruecklich etwas anderes als eine leere Abbildung: jene ist
    eine vorhandene Kopfzeile ohne getragenes Motiv und redet voll mit. Beide Motivfelder haben
    Vorgabewerte - ohne Motivangabe ist die Gliederung die bisherige."""

    photo_id: int
    taken_at: datetime
    location: EffectiveLocation | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None
    landmark_name: str | None = None
    motif_strengths: Mapping[str, float] | None = None
    excluded_document: bool = False


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
    # Die verschiedenen gerundeten GEMESSENEN Zellen dieses Events, sortiert und dublettenfrei.
    # Sie entstehen UNABHAENGIG von `_place_of`, das bei gesetztem `landmark_name` zurueckkehrt,
    # bevor es sie bildet: auch ein Landmark-Event traegt seine Zellen, sonst waere die Ausnahme
    # der Namensvergabe (ein Landmark-Event bekommt keinen Ortsnamen) nicht pruefbar.
    place_cells: tuple[tuple[float, float], ...] = ()


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
    je Kandidat laeuft genau eine der beiden.

    `name` stammt aus `BOUNDARY_CAUSES` und ist die Ursache, unter der dieses Signal in der
    Statistik erscheint. Ein Signal ohne Namen aus dem Vorrat fiele dort unter den Tisch, ohne
    dass eine Summe kleiner wuerde - der Bericht waere still unvollstaendig."""

    @property
    def name(self) -> str: ...

    def is_boundary(self, candidate: EventCandidate) -> bool: ...

    def begin(self, candidate: EventCandidate) -> None: ...

    def advance(self, candidate: EventCandidate) -> None: ...


class TimeGapSignal:
    """Die Zeitluecke zwischen zwei aufeinanderfolgenden Fotos - unveraendertes Verhalten,
    `>` und nicht `>=`."""

    name = BOUNDARY_TIME_GAP

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

    name = BOUNDARY_CALENDAR_DAY

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

    name = BOUNDARY_STEP

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

    name = BOUNDARY_EXTENT

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

    Exakter Zeichenkettenvergleich, KEIN Fuzzy-Matching - und das ist seit ADR 0107 keine
    Vereinfachung mehr, sondern die richtige Arbeitsteilung: Die Vereinheitlichung liegt DAVOR.
    `worker.py::_landmark_names` liefert den bereits auf das projektweite Namensregister
    aufgeloesten Namen, sodass zwei Schreibweisen derselben Sehenswuerdigkeit hier gar nicht mehr
    als verschieden ankommen. Ein Fuzzy-Vergleich an dieser Stelle waere ein zweiter, danebenstehen-
    der Massstab."""

    name = BOUNDARY_LANDMARK

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


def _motif_picture(candidate: EventCandidate) -> frozenset[str] | None:
    """Das MOTIVBILD eines Fotos: die Menge der Motive, die es traegt.

    `None` heisst "redet fuer den Motivwechsel nicht mit" - keine Kopfzeile, oder als Dokument
    bzw. Bildschirmabbild ausgeschlossen. Uebergangen heisst NIE ausgeschlossen: das Foto bleibt
    Mitglied seines Events. Eine vorhandene Kopfzeile ohne ein einziges getragenes Motiv ergibt
    dagegen die leere Menge und redet voll mit.

    Was als getragen gilt, beantwortet AUSSCHLIESSLICH `selection.py::carried_motifs` - dieselbe
    eine, inklusive Grenze wie im Auswahlvorschlag. Eine eigene Grenze hier waere ein zweiter
    Begriff von "dieses Foto zeigt X" im selben Produkt, und die beiden liefen beim naechsten
    Grenzfall auseinander."""
    if candidate.excluded_document or candidate.motif_strengths is None:
        return None
    return carried_motifs(candidate.motif_strengths)


def motif_change_starts(ordered: Sequence[EventCandidate]) -> frozenset[int]:
    """Die Indizes der BEREITS SORTIERTEN Folge, an denen ein bestaetigter Motivwechsel ein neues
    Event erzwingt - die erste Stufe der Event-Bildung, REIN und ohne Kenntnis der Signale.

    Der Motivwechsel ist kein Eintrag in `default_signals()`: Er ist keine paarweise Frage,
    sondern eine Segmentierung ueber die ganze Folge, und das vorwaerts entscheidende
    `BoundarySignal`-Protokoll kann weder das Bestaetigungsfenster noch die Rueckwirkung
    ausdruecken.

    WECHSEL ist die symmetrische Differenz zum Motivbild des Fotos, das den laufenden
    Motivabschnitt EROEFFNET hat - nicht zum unmittelbaren Vorgaenger: gegen den gemessen liefe
    ein langsames Abdriften unbegrenzt weiter, ohne je zu trennen. Kein Wechsel des staerksten
    Motivs und kein Gesamtabstand ueber die Staerken; entschieden wird je Motiv einzeln gegen
    dieselbe eine Grenze.

    BESTAETIGT ist der Wechsel, wenn `MOTIF_CHANGE_CONFIRMING_PHOTOS` aufeinanderfolgende
    mitredende Fotos ihn zeigen - das erste abweichende eingeschlossen -, wobei jedes weitere
    mindestens EINES der zuerst geaenderten Motive weiterhin geaendert zeigt. Das identische
    Motivbild wird bewusst nicht verlangt: dieselbe Situation mit einem zusaetzlichen Motiv im
    Bild darf die Bestaetigung nicht abreissen lassen. Zeigt ein Foto keines davon, zerfaellt das
    Fenster: es beginnt an diesem Foto neu, wenn es selbst abweicht, und entfaellt sonst.

    GELIEFERT wird der Index des ERSTEN Fotos des Fensters, nicht des bestaetigenden; sein
    Motivbild wird der neue Bezug. Der Index ist nie `0` - er setzt einen bereits gesetzten Bezug
    voraus, ein leeres fuehrendes Event kann also nicht entstehen."""
    starts: set[int] = set()
    reference: frozenset[str] | None = None
    window_start = 0
    window_changed: frozenset[str] = frozenset()
    window_count = 0

    for index, candidate in enumerate(ordered):
        picture = _motif_picture(candidate)
        if picture is None:
            continue
        if reference is None:
            reference = picture
            continue

        changed = picture ^ reference
        if window_count and changed & window_changed:
            window_count += 1
        elif changed:
            window_start, window_changed, window_count = index, changed, 1
        else:
            window_count = 0

        if window_count >= MOTIF_CHANGE_CONFIRMING_PHOTOS:
            starts.add(window_start)
            reference = _motif_picture(ordered[window_start])
            window_count = 0

    return frozenset(starts)


def _name_of(members: Sequence[EventCandidate]) -> str | None:
    """Der eine Name eines Events, oder `None`.

    `members` ist nach `(taken_at, photo_id)` sortiert: ein Event traegt hoechstens EINEN Namen
    (dafuer sorgt `LandmarkChangeSignal`) - defensiv gewinnt der des fruehesten Fotos."""
    for member in members:
        name = _usable_name(member.landmark_name)
        if name is not None:
            return name
    return None


def _cells_of(members: Sequence[EventCandidate]) -> tuple[tuple[float, float], ...]:
    """Die verschiedenen gerundeten GEMESSENEN Zellen eines Events, sortiert und dublettenfrei.

    Ausschliesslich gemessene Werte: ein uebernommener Ort bestimmt die Grenzen mit, speist den
    Ortsbezug eines Events aber nie - und darf deshalb auch keinen Namen tragen."""
    return tuple(
        sorted(
            {
                place_cell(member.gps_lat, member.gps_lon)
                for member in members
                if member.gps_lat is not None and member.gps_lon is not None
            }
        )
    )


def _place_of(
    cells: Sequence[tuple[float, float]], landmark_name: str | None
) -> tuple[str | None, float | None, float | None]:
    """Die Stufenentscheidung ueber das VOLLSTAENDIGE Event, ausschliesslich aus GEMESSENEN Werten.

    Rangfolge: erkannte Sehenswuerdigkeit -> genau eine gerundete Koordinatenzelle -> mehrere Orte
    -> kein Ortsbezug. Der Name hat Vorrang auch dann, wenn zusaetzlich abweichende Koordinaten
    vorliegen.

    VERGLICHEN WIRD DIE GERUNDETE Zelle, nicht der Rohwert: ein Vergleich der ungerundeten Werte
    schluege schon bei zwei 40 m auseinanderliegenden Aufnahmen zu und machte aus einem einzelnen
    Ortsbesuch "Mehrere Orte".

    `landmark_name` und `cells` kommen als Parameter herein statt hier ein zweites Mal gebildet zu
    werden: so gibt es je EINE Stelle, die "gibt es einen verwendbaren Namen" und "welche Zellen
    hat dieses Event" beantwortet, und die Invariante `place_kind='landmark'` ⇒ `landmark_name`
    gesetzt kann an der einen Aufrufstelle gar nicht auseinanderlaufen."""
    if landmark_name is not None:
        return "landmark", None, None
    if not cells:
        return None, None, None
    if len(cells) > 1:
        return "multiple", None, None
    [(lat, lon)] = cells
    return "coordinate", lat, lon


def _built(position: int, members: Sequence[EventCandidate]) -> BuiltEvent:
    landmark_name = _name_of(members)
    cells = _cells_of(members)
    place_kind, place_lat, place_lon = _place_of(cells, landmark_name)
    return BuiltEvent(
        position=position,
        photo_ids=tuple(member.photo_id for member in members),
        started_at=members[0].taken_at,
        ended_at=members[-1].taken_at,
        landmark_name=landmark_name,
        place_kind=place_kind,
        place_lat=place_lat,
        place_lon=place_lon,
        place_cells=cells,
    )


@dataclass(frozen=True)
class EventFormation:
    """Die Gliederung eines Laufs SAMT der Ursache jeder Grenze - die Erklaerform von
    `build_events`.

    `causes` ist POSITIONSTREU zu `events`: Eintrag `i` ist die Menge der Signale, die die
    EROEFFNENDE Grenze von Event `i` gemeldet haben.

    INDEX 0 TRAEGT IMMER DIE LEERE MENGE. Die Ausnahme haengt an der POSITION, nicht an einem
    einzelnen Signal - sonst braucht jedes kuenftige Signal seine eigene. `TimeGapSignal` meldet
    am ersten Foto `True` (`_previous is None`); ohne diese Ausnahme truege jeder Lauf eine
    erfundene Zeitluecke in der Statistik.

    Daraus folgt die tragende Pruefform: Die Zahl der Grenzen MIT Ursache ist stets
    `Eventzahl - 1`.

    Die Menge wird ausdruecklich NICHT persistiert (ADR 0117 Punkt 4): Stufe 3 liest sie im selben
    Durchlauf, das Messkommando bildet sie ohnehin neu, und eine Spalte waere nach jeder
    Schwellenaenderung veraltet, ohne dass es auffiele."""

    events: tuple[BuiltEvent, ...]
    causes: tuple[frozenset[str], ...]


def build_events(
    candidates: Iterable[EventCandidate], signals: list[BoundarySignal] | None = None
) -> list[BuiltEvent]:
    """Die Event-Bildung - die Gliederung ohne ihre Erklaerung.

    EIN Rechenweg, zwei Sichten: Diese Funktion ist `explain_events` ohne die Ursachenmengen. Ein
    zweiter Durchlauf fuer dasselbe liefe auseinander, und dann maesse das Messkommando die
    Grenzen einer Gliederung, die so nie entstanden ist."""
    return list(explain_events(candidates, signals).events)


def explain_events(
    candidates: Iterable[EventCandidate], signals: list[BoundarySignal] | None = None
) -> EventFormation:
    """Die Event-Bildung: EIN sortierter Durchlauf ueber die Kandidaten eines Kriterien-Laufs,
    dem die Motivgrenzen als eigene Stufe VORAUSGEHEN - samt der Ursache jeder Grenze.

    Das Ergebnis ist chronologisch geordnet und ueberschneidungsfrei, `position` laeuft
    lueckenlos ab 1, und jeder uebergebene Kandidat steht in genau einem Event.

    Der Durchlauf wertet ALLE Signale aus - eine vollstaendig gebaute LISTE der meldenden Namen,
    ausdruecklich NICHT kurzgeschlossen - und ruft danach genau eine der schreibenden Methoden auf
    ALLEN auf. Wuerde die Auswertung beim ersten Treffer abbrechen, haenge die
    Zustandsfortschreibung eines Signals an seiner Listenposition, und die Ursachenmenge naehme
    nur das erste meldende Signal auf. Aus demselben Grund steht `index in forced_starts` in einer
    eigenen Anweisung NACH der Signalauswertung: davor wuerde an einem erzwungenen Start kein
    Signal mehr gefragt.

    Ein erzwungener Start wirkt wie jede gemeldete Grenze - `begin` laeuft auf allen Signalen und
    ist deren vollstaendige Ruecksetzung. Eine erst spaeter faellige Grenze von Ausdehnung,
    Schritt oder Name kann dadurch entfallen, weil an der frueheren Stelle bereits getrennt wurde.

    `signals` ist injizierbar; ohne Angabe gilt `default_signals()`."""
    ordered = sorted(candidates, key=lambda candidate: (candidate.taken_at, candidate.photo_id))
    forced_starts = motif_change_starts(ordered)
    active = default_signals() if signals is None else signals

    events: list[list[EventCandidate]] = []
    causes: list[frozenset[str]] = []
    for index, candidate in enumerate(ordered):
        # Die Liste wird VOLLSTAENDIG gebaut, bevor `any` sie liest - und sie traegt zugleich, WER
        # gemeldet hat. Ein `any` ueber einen Generator schnitte beides gleichzeitig ab.
        reporting = [signal.name for signal in active if signal.is_boundary(candidate)]
        forced = index in forced_starts
        if reporting or forced or not events:
            for signal in active:
                signal.begin(candidate)
            events.append([])
            # DIE AUSNAHME AN DER POSITION: Das erste Segment eines Laufs traegt keine Ursache,
            # gleich welches Signal an diesem Foto gemeldet hat.
            causes.append(
                frozenset()
                if index == 0
                else frozenset(reporting) | ({BOUNDARY_MOTIF_CHANGE} if forced else set())
            )
        else:
            for signal in active:
                signal.advance(candidate)
        events[-1].append(candidate)

    return EventFormation(
        events=tuple(_built(position, members) for position, members in enumerate(events, start=1)),
        causes=tuple(causes),
    )


class PlaceNamedEvent(Protocol):
    """Was die Namensvergabe von einem Event liest - und mehr nicht.

    Ein Protokoll statt `BuiltEvent`, weil dieselbe Vergabe zwei Aufrufer hat: den Lauf
    (`BuiltEvent`) und das Messkommando (`place_probe.ProbeEvent`). Eine ZWEITE, nachbildende
    Fassung der Regel driftet - und dann misst das Messkommando etwas anderes, als der Lauf
    tatsaechlich tut, waehrend beide fuer sich gruen bleiben.

    Nur-lesende Eigenschaften: beide Aufrufer sind eingefrorene Datenklassen."""

    @property
    def landmark_name(self) -> str | None: ...

    @property
    def place_cells(self) -> tuple[tuple[float, float], ...]: ...


def _the_one_of(values: Iterable[str | None]) -> str | None:
    """Der EINE verschiedene Wert einer Menge, oder `None` bei null oder mehreren.

    Werte `None` zaehlen ausdruecklich NICHT mit: ein Event aus zwei Zellen, von denen nur eine
    einen Namen liefert, traegt diesen Namen."""
    distinct = {value for value in values if value is not None}
    if len(distinct) != 1:
        return None
    return distinct.pop()


def locality_of_event(
    event: PlaceNamedEvent, info_by_cell: Mapping[tuple[float, float], PlaceInfo]
) -> str | None:
    """Der Ortsname dieses Events - ohne Viertel, das entscheidet erst der Lauf.

    OEFFENTLICH, weil das Messkommando die Gleichnamigkeit ueber genau diesen Wert zaehlt: sie ist
    eine Aussage ueber den Ortsnamen, nicht ueber die fertige Ueberschrift. Ohne diese Stelle
    braeuchte es dort eine zweite Fassung derselben Regel.

    Ein Event MIT Sehenswuerdigkeit bekommt keinen: der Ortsname ersetzt sie nicht und tritt nicht
    daneben. Es zaehlt deshalb auch bei der Gleichnamigkeitspruefung nicht mit und loest bei
    keinem anderen Event die Viertel-Ergaenzung aus.

    Gelesen werden ALLE Zellen des Events, nicht nur die eines `place_kind='coordinate'`: ein
    Event darf die Zellgrenze streifen und waere dann `'multiple'`, obwohl alle Aufnahmen in
    derselben Stadt liegen. Traegt eine Menge von Orten genau einen Namen, ist sie keine Menge von
    Orten."""
    if event.landmark_name is not None:
        return None
    return _the_one_of(usable_locality(info_by_cell.get(cell)) for cell in event.place_cells)


def _district_of(
    event: PlaceNamedEvent, info_by_cell: Mapping[tuple[float, float], PlaceInfo]
) -> str | None:
    """Das EINE Viertel ueber die Zellen dieses Events - bei zwei verschiedenen keines.

    Gezaehlt wird nur ueber Zellen, deren Auskunft tatsaechlich einen Ortsnamen aufloest: das
    Viertel einer Auskunft ohne brauchbare Ebene ist keine Angabe, die hier gilt."""
    return _the_one_of(
        info.neighbourhood
        for cell in event.place_cells
        if (info := info_by_cell.get(cell)) is not None and usable_locality(info) is not None
    )


def assign_place_names(
    events: Sequence[PlaceNamedEvent],
    info_by_cell: Mapping[tuple[float, float], PlaceInfo],
) -> list[str | None]:
    """Der Ortsname JE EVENT eines Laufs, POSITIONSTREU zur uebergebenen Liste.

    Zwei Durchgaenge, und der zweite ist der Grund, warum diese Vergabe hier und nicht in
    `places.py` steht (ADR 0102 Punkt 4): Ob ein Event "Berlin" oder "Berlin, Kreuzberg" heisst,
    haengt davon ab, was sonst im selben Lauf liegt - das ist keine Eigenschaft des Ortes.

    1. Je Event der eine Ortsname seiner Zellen (`None` bei null oder mehreren, und bei einer
       erkannten Sehenswuerdigkeit).
    2. Ueber den ganzen Lauf: Fuer jeden MEHRFACH vergebenen Namen bekommt GENAU JEDES dieser
       Events zusaetzlich sein Viertel, sofern ueber seine Zellen genau eines vorliegt - JE EVENT
       EINZELN, die uebrigen bleiben beim Ortsnamen und sind ueber ihre Zeitspanne
       unterscheidbar.

    REISST die zusammengesetzte Form `MAX_PLACE_NAME_LENGTH`, bleibt der Ortsname allein stehen.
    Gekuerzt wird NIE: zwei verschiedene, auf dieselbe Laenge gekappte Namen waeren ein Name, und
    die Viertel-Regel griffe dann fuer Events an verschiedenen Orten.

    REIN und deterministisch - das Ergebnis haengt nicht von der Reihenfolge der Eingabe ab."""
    localities = [locality_of_event(event, info_by_cell) for event in events]

    occurrences: dict[str, int] = {}
    for locality in localities:
        if locality is not None:
            occurrences[locality] = occurrences.get(locality, 0) + 1

    names: list[str | None] = []
    for event, locality in zip(events, localities, strict=True):
        if locality is None or occurrences[locality] < 2:
            names.append(locality)
            continue
        district = _district_of(event, info_by_cell)
        if district is None:
            names.append(locality)
            continue
        composed = f"{locality}, {district}"
        names.append(locality if len(composed) > MAX_PLACE_NAME_LENGTH else composed)
    return names
