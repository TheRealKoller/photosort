"""Event-Bildung: die Gliederung eines Kriterien-Laufs in Einheiten mit Anfang, Ende, Ort und
Namen.

REIN und DB-FREI. Bewusst nicht in `scoring.py` - das ist Phase A (`assign_clusters`, vor dem
Ausschuss-Gate) und bleibt davon unberuehrt.

LOGGING-AUFLAGE fuer jede kuenftige Logzeile dieses Moduls: Koordinaten gehoeren NIE ins Log, ein
Sehenswuerdigkeit-Name nur als `%r` und laengenbegrenzt.
"""

from __future__ import annotations

import math
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
from photosort.scoring import haversine_meters
from photosort.selection import carried_motifs

# --- Die SIEBEN eigenen Schwellen der Event-Bildung ----------------------------------------------
#
# Sie stehen hier und nicht in `scoring.py`, obwohl zwei von ihnen dort denselben Zahlwert tragen:
# Dieselben Konstanten steuern `assign_clusters`, also Phase A VOR dem Ausschuss-Gate und damit,
# welche Fotos im Ausschuss gegeneinander antreten. Eine Kalibrierung an ihnen verschoebe still die
# Kandidatenmenge. Phase A bleibt von diesen sieben Werten unberuehrt.
#
# Alle sieben sind dokumentierte Modulkonstanten, ausdruecklich KEIN Settings-/Env-Wert, und werden
# ueberall als MODULATTRIBUT gelesen, nie als Default-Parameterwert gebunden: sonst liefe
# `monkeypatch.setattr` ins Leere und eine Variation waere wirkungslos - gruen, aber ohne Wirkung.
# Kein Test pinnt einen Zahlwert; zulaessig sind genau die vier Ungleichungen
# `MERGE_MAX_GAP > EVENT_TIME_GAP`, `MIN_EVENT_PHOTOS >= 2`, `EVENT_MAX_SPAN < 24 h` und
# `MERGE_EXTENT_MAX_METERS > EVENT_EXTENT_MAX_METERS`.

# Zeitluecke zwischen zwei aufeinanderfolgenden Fotos, ab der ein neues Event beginnt.
# UNKALIBRIERT: Von den Grenzen eines echten Projekts war sie zu 5,6 % alleinige Ursache, `schritt`
# und `ausdehnung` zu 0,0 % - eine Kalibrierung dieser drei kann die Zerstueckelung nicht aufloesen.
EVENT_TIME_GAP = timedelta(hours=1)

# Schritt zwischen zwei aufeinanderfolgenden Fotos. UNKALIBRIERT, siehe oben.
EVENT_STEP_MAX_METERS = 500.0

# Raeumliche Ausdehnung des laufenden Events: die Diagonale der umschliessenden Box. UNKALIBRIERT.
# Groessenordnung Stadtviertel: ueber der Streuung eines einzelnen Ortsbesuchs (100-300 m) und ueber
# der Schrittschwelle.
EVENT_EXTENT_MAX_METERS = 1000.0

# Dauer vom eroeffnenden bis zum betrachteten Foto, ab der ein neues Event beginnt.
#
# HERLEITUNG: Acht Stunden tragen einen ganzen Ausflugstag - Stadtbummel, Zoobesuch, Wanderung - und
# ebenso Silvester oder einen Nachtflug ueber Mitternacht; zwei Reisetage passen nicht hinein. Der
# Wert liegt weit ueber der laengsten an einem echten Projekt gemessenen Eventdauer (1 h 32 min),
# zerschneidet also nichts, was heute zusammengehoert. Er MUSS unter 24 h bleiben: die
# Ueberschriftenform `23:40-01:15 Uhr` ist sonst mehrdeutig.
EVENT_MAX_SPAN = timedelta(hours=8)

# Zeitluecke, die ein zu kleines Segment beim Zuschlagen ueberbruecken darf.
#
# HERLEITUNG: Groesser als `EVENT_TIME_GAP` MUSS der Wert sein, sonst ist die dritte Stufe
# wirkungslos - ein Rest von ein, zwei Bildern traegt keinen eigenen Beleg dafuer, dass mit ihm ein
# neuer Anlass begann. Bewusst nicht groesser als das Doppelte: Ueber eine Luecke von mehr als zwei
# Stunden hinweg anzuhaengen hiesse, eine echte Pause zu ueberspringen, und `EVENT_MAX_SPAN` finge
# das erst bei acht Stunden ab.
MERGE_MAX_GAP = timedelta(hours=2)

# Groesse, unter der ein Segment als zu klein gilt und einem Nachbarn zugeschlagen wird.
#
# HERLEITUNG: Zunaechst gilt nur ein EINZELNES Foto als zu klein - das traf am gemessenen Projekt
# genau die 22 Faelle, um die es geht, und liess die 15 Zwei-Foto-Cluster unberuehrt. Ein Wert von 1
# hiesse "kein Segment ist je zu klein"; `MIN_EVENT_PHOTOS >= 2` ist die einzige Aussage, die ein
# Test ueber diesen Wert treffen darf, und sie ist eine Ungleichung.
MIN_EVENT_PHOTOS = 2

# Raeumliche Ausdehnung, die das ERGEBNIS einer Zusammenlegung nicht ueberschreiten darf (Riegel
# (c) in `_may_merge`).
#
# Sie MUSS groesser sein als `EVENT_EXTENT_MAX_METERS`, sonst prueft Riegel (c) dieselbe Bedingung,
# deren Ueberschreitung die Trennung ausgeloest hat - fuer ausdehnungsgetrennte Segmente waere die
# Stufe damit strukturell unpassierbar.
#
# HERLEITUNG: die Trennschwelle plus EINEN Schritt (`EVENT_EXTENT_MAX_METERS` +
# `EVENT_STEP_MAX_METERS`). Zugeschlagen wird ein Segment unter `MIN_EVENT_PHOTOS`, heute also ein
# einzelnes Foto ohne eigene Ausdehnung; die Box waechst damit genau um dessen Abstand zur Box des
# Nachbarn. Ein Schritt ueber `EVENT_STEP_MAX_METERS` ist im Massstab dieses Projekts bereits ein
# Ortswechsel und trennt fuer sich - mehr als einen zuzulassen hiesse, eine Trennung aufzuloesen,
# die das Projekt selbst so nennt; weniger hiesse, die Stufe weiter leerlaufen zu lassen.
#
# EIN LITERAL, KEINE GERECHNETE SUMME der beiden genannten Konstanten: Die Schwellen werden ueberall
# als Modulattribut gelesen, damit ein Pruefsatz sie verschieben kann, und eine beim Import
# gebundene Summe folgte dieser Verschiebung nicht - gruen, aber ohne Wirkung.
MERGE_EXTENT_MAX_METERS = 1500.0

# Der geschlossene Vorrat von `events.place_kind`. Ein Wert ausserhalb ist ein Datenfehler und
# wird im Lesepfad zu "kein Ortsbezug", nie zu einer 500.
PLACE_KINDS = ("landmark", "coordinate", "multiple")

# --- Der geschlossene Vorrat der TRENNURSACHEN (ADR 0117 Punkt 4) -------------------------------
#
# Jede Grenze traegt die MENGE der Signale, die sie gemeldet haben, nie ein einzelnes: Der
# Durchlauf wertet alle aus, mehrere duerfen gleichzeitig zutreffen, und ein Bericht mit einer
# Ursache je Grenze addierte sich zu mehr als hundert Prozent oder unterschluege Ursachen.
BOUNDARY_TIME_GAP = "zeitluecke"
BOUNDARY_DURATION = "dauer"
BOUNDARY_STEP = "schritt"
BOUNDARY_EXTENT = "ausdehnung"
# Kein Eintrag in `default_signals()` seit ADR 0118: Die Sehenswuerdigkeit trennt nicht mehr. Ihr
# Name bleibt trotzdem im Vorrat - er ist ein BERICHTSWORTSCHATZ, und die Zeile mit 0 ist der
# Nachweis, dass die Aenderung gewirkt hat. Ohne sie haette die Nachmessung eine Zeile weniger als
# die Ausgangsmessung, und kein Leser koennte unterscheiden, ob die Ursache weggefallen oder nie
# gemessen worden ist.
BOUNDARY_LANDMARK = "sehenswuerdigkeit"
# Kein Eintrag in `default_signals()`: Der Motivwechsel ist eine Segmentierung ueber die ganze
# Folge (ADR 0109) und trennt als ERZWUNGENER START. Er braucht trotzdem seinen Namen, sonst
# stuende in der Statistik eine Grenze ohne Ursache.
BOUNDARY_MOTIF_CHANGE = "motivwechsel"

BOUNDARY_CAUSES = (
    BOUNDARY_TIME_GAP,
    BOUNDARY_DURATION,
    BOUNDARY_STEP,
    BOUNDARY_EXTENT,
    BOUNDARY_LANDMARK,
    BOUNDARY_MOTIF_CHANGE,
)

# Die EINE Ursache, die das Zusammenlegen NIE aufloest. Sie ist das einzige Signal, das zwei
# verschiedene Anlaesse AM SELBEN ORT ZUR SELBEN ZEIT trennt; ohne ihren Vorrang waere die Zusage
# "zwei erkennbar verschiedene Anlaesse bleiben getrennt" nicht durchsetzbar. Ein durch Motivwechsel
# abgetrenntes Einzelbild bleibt dadurch allein - genau das sagt ADR 0109 bereits zu.
#
# `BOUNDARY_LANDMARK` steht hier NICHT, obwohl es in `BOUNDARY_CAUSES` steht, und die
# Ungleichbehandlung ist gewollt (ADR 0118 Punkt 2): Dieser Vorrat ist kein Wortschatz, sondern eine
# an JEDER KANTE gelesene Regel. Ein Eintrag, der nie treffen kann, waere hier keine ehrliche Null,
# sondern eine falsche Aussage ueber das laufende System - er behauptete eine Sperre ohne
# Gegenstand und machte `MERGE_BLOCK_UNBREAKABLE` mehrdeutig.
UNBREAKABLE_CAUSES = frozenset({BOUNDARY_MOTIF_CHANGE})

# WORAN EINE ZUSAMMENLEGUNG SCHEITERT - der geschlossene Vorrat der Gruende, die an einer KANTE
# eines zu kleinen Segments stehen koennen. Die Reihenfolge ist die der Riegel in `_may_merge` und
# legt die Zeilenfolge des Berichts fest - sie ist KEIN Vorrang: Die Pruefung ist nicht
# kurzgeschlossen, jede Kante meldet alle zutreffenden Gruende.
#
# `MERGE_BLOCK_NO_NEIGHBOUR` ist kein Riegel, sondern der Fall "es gibt ueberhaupt keinen
# Nachbarn". Eine bloss fehlende SEITE eines Randsegments faellt nicht darunter - sie ist kein
# Hindernis und keine Kante.
#
# DIE UNANTASTBARKEIT ZAEHLT ALS EIGENER GRUND, NICHT ALS VIERTER RIEGEL. Sie ist keine Schwelle,
# sondern eine Zusage, und ihre Behebung waere eine andere Entscheidung als die Aenderung einer
# Zahl. Ohne diese Trennung bliebe offen, ob eine Schwelle oder die Sperre blockiert hat.
#
# Riegel (d) - das Segment liegt selbst unter der Mindestgroesse - steht hier NICHT: Er haengt an
# der Auswahl, nicht an einer Kante, und ein Segment, das nicht zu klein ist, wird gar nicht erst
# betrachtet.
#
# Gleichlautend mit drei Eintraegen aus `BOUNDARY_CAUSES` und doch ein eigener Vorrat: Eine
# TRENNURSACHE sagt, warum eine Grenze entstand, ein GRUND hier, warum sie nicht wieder verschwand.
MERGE_BLOCK_UNBREAKABLE = "unantastbar"
MERGE_BLOCK_TIME_GAP = "zeitluecke"
MERGE_BLOCK_SPAN = "dauer"
MERGE_BLOCK_EXTENT = "ausdehnung"
MERGE_BLOCK_NO_NEIGHBOUR = "kein_nachbar"

MERGE_BLOCK_REASONS = (
    MERGE_BLOCK_UNBREAKABLE,
    MERGE_BLOCK_TIME_GAP,
    MERGE_BLOCK_SPAN,
    MERGE_BLOCK_EXTENT,
    MERGE_BLOCK_NO_NEIGHBOUR,
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

    `landmark_name` kommt bereits durch `sanitize_landmark_name` (event_inputs.py::_landmark_names) -
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
    """Ein Name, der nach Sanitisierung leer ist, gilt als NICHT VORHANDEN - er wird nicht
    geschrieben, und das Event traegt stattdessen den naechsten vorhandenen. Verworfen, nie
    abgeschnitten: Ein gekuerzter Name benennte ein Event falsch."""
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

    def __init__(self, gap: timedelta | None = None) -> None:
        self._gap = EVENT_TIME_GAP if gap is None else gap
        self._previous: datetime | None = None

    def is_boundary(self, candidate: EventCandidate) -> bool:
        return self._previous is None or candidate.taken_at - self._previous > self._gap

    def begin(self, candidate: EventCandidate) -> None:
        self._previous = candidate.taken_at

    def advance(self, candidate: EventCandidate) -> None:
        self._previous = candidate.taken_at


class EventSpanSignal:
    """Die DAUER des laufenden Events: die Spanne vom EROEFFNENDEN bis zum gerade betrachteten
    Foto, geprueft EINSCHLIESSLICH dieses Fotos - sonst begaenne das neue Event ein Foto zu spaet.

    Zustandsbehaftet im Muster von `ExtentSignal`, und der zeitliche Riegel gegen
    Ueberverschmelzung: Ein Anlass ueber Mitternacht (Silvester, langer Abend, Nachtflug) bleibt EIN
    Event, mehrere Reisetage werden es nicht. Die Grenze ist die Dauer, nicht das Datum.

    Zonenfrei richtig, wo ein Kalendertag es nicht war: `taken_at` ist zonenlos, ein Kalendertag ist
    eine Aussage der lokalen Zeitzone, eine Zeitspanne dagegen die Differenz zweier naiver
    Zeitstempel.

    `>` und nicht `>=`, wie bei der Zeitluecke. `advance` schreibt NICHTS fort - der Bezug ist das
    eroeffnende Foto, und ein Fortschreiben machte die Dauergrenze zu einer zweiten Zeitluecke."""

    name = BOUNDARY_DURATION

    def __init__(self, max_span: timedelta | None = None) -> None:
        self._max_span = EVENT_MAX_SPAN if max_span is None else max_span
        self._started_at: datetime | None = None

    def is_boundary(self, candidate: EventCandidate) -> bool:
        if self._started_at is None:
            return False
        return candidate.taken_at - self._started_at > self._max_span

    def begin(self, candidate: EventCandidate) -> None:
        self._started_at = candidate.taken_at

    def advance(self, candidate: EventCandidate) -> None:
        return None


class StepDistanceSignal:
    """Der SCHRITT zwischen zwei aufeinanderfolgenden Fotos.

    Bezug ist die letzte WIRKSAME Koordinate des LAUFENDEN Events, nicht der unmittelbare
    zeitliche Vorgaenger: sonst unterdrueckte ein einziges Foto ohne jeden Ort zwischen zwei weit
    auseinanderliegenden Aufnahmen die Trennung vollstaendig. Rueckgesetzt wird an JEDER Grenze,
    auch an einer rein zeitlichen - sonst wuerde das erste Foto eines neuen Events gegen eines aus
    dem vorherigen verglichen und ein zweites Mal getrennt."""

    name = BOUNDARY_STEP

    def __init__(self, split_distance_meters: float | None = None) -> None:
        self._split_distance_meters = (
            EVENT_STEP_MAX_METERS if split_distance_meters is None else split_distance_meters
        )
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

    def __init__(self, max_meters: float | None = None) -> None:
        self._max_meters = EVENT_EXTENT_MAX_METERS if max_meters is None else max_meters
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


def default_signals() -> list[BoundarySignal]:
    """Die VIER Trennsignale, gleichrangig, in einer LISTE.

    Die Liste ist der Erweiterungspunkt: ein weiteres Signal ist eine Klasse und ein Eintrag - kein
    Eingriff in den Durchlauf, das Datenmodell oder die API. Sie fuehrt AUSSCHLIESSLICH Signale,
    die trennen; ein nie meldender Eintrag machte aus ihr eine Liste mit zwei Bedeutungen. Deshalb
    ist die Sehenswuerdigkeit hier seit ADR 0118 ersatzlos verschwunden statt stillgelegt.

    Jeder Aufruf liefert FRISCHE Objekte: Signale sind zustandsbehaftet, eine geteilte Liste
    tarnte einen Lauf als Fortsetzung des vorherigen."""
    return [
        TimeGapSignal(),
        EventSpanSignal(),
        StepDistanceSignal(),
        ExtentSignal(),
    ]


def _motif_picture(
    candidate: EventCandidate, motif_presence_threshold: float | None = None
) -> frozenset[str] | None:
    """Das MOTIVBILD eines Fotos: die Menge der Motive, die es traegt.

    `None` heisst "redet fuer den Motivwechsel nicht mit" - keine Kopfzeile, oder als Dokument
    bzw. Bildschirmabbild ausgeschlossen. Uebergangen heisst NIE ausgeschlossen: das Foto bleibt
    Mitglied seines Events. Eine vorhandene Kopfzeile ohne ein einziges getragenes Motiv ergibt
    dagegen die leere Menge und redet voll mit.

    Was als getragen gilt, beantwortet AUSSCHLIESSLICH `selection.py::carried_motifs` - dieselbe
    eine, inklusive Grenze wie im Auswahlvorschlag. Eine eigene Grenze hier waere ein zweiter
    Begriff von "dieses Foto zeigt X" im selben Produkt, und die beiden liefen beim naechsten
    Grenzfall auseinander.

    `motif_presence_threshold` ist die DURCHGEREICHTE Grenze der Empfindlichkeitsmessung und
    stammt ausschliesslich aus dem injizierbaren Parameter von `motif_change_starts`. `None` heisst
    "der Betriebswert gilt"; die Auswahl selbst gibt nie einen Wert mit (Auflage in
    `selection.py::motif_is_present`)."""
    if candidate.excluded_document or candidate.motif_strengths is None:
        return None
    return carried_motifs(candidate.motif_strengths, motif_presence_threshold)


def motif_change_starts(
    ordered: Sequence[EventCandidate],
    *,
    confirming_photos: int | None = None,
    motif_presence_threshold: float | None = None,
) -> frozenset[int]:
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
    voraus, ein leeres fuehrendes Event kann also nicht entstehen.

    BEIDE FESTLEGUNGEN SIND INJIZIERBAR (`None` = Modulkonstante bzw. Betriebswert): Die
    Empfindlichkeitsmessung in `event_probe.py` rechnet dieselbe Kandidatenmenge unter mehreren
    Kombinationen durch und laeuft dabei durch DIESEN Rechenweg - eine nachbildende zweite Fassung
    maesse etwas anderes, als der Lauf tut, waehrend beide fuer sich gruen blieben. Die
    Fensterlaenge wird dafuer als MODULATTRIBUT gelesen, nie als Default-Parameterwert gebunden:
    sonst liefe `monkeypatch.setattr` ins Leere und die Variation waere wirkungslos."""
    confirming = MOTIF_CHANGE_CONFIRMING_PHOTOS if confirming_photos is None else confirming_photos
    starts: set[int] = set()
    reference: frozenset[str] | None = None
    window_start = 0
    window_changed: frozenset[str] = frozenset()
    window_count = 0

    for index, candidate in enumerate(ordered):
        picture = _motif_picture(candidate, motif_presence_threshold)
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

        if window_count >= confirming:
            starts.add(window_start)
            reference = _motif_picture(ordered[window_start], motif_presence_threshold)
            window_count = 0

    return frozenset(starts)


def _name_of(members: Sequence[EventCandidate]) -> str | None:
    """Der Name eines Events, oder `None`.

    DIE REGEL, nicht mehr eine Vorsichtsmassnahme: Ein Event DARF Fotos mit verschiedenen Namen
    enthalten, und der FRUEHESTE gewinnt. `members` ist nach `(taken_at, photo_id)` sortiert; die
    erste Fundstelle ist damit die chronologisch erste.

    Ausgefuehrt NACH Stufe 3 und ausschliesslich hier, an der einen Aufrufstelle `_built` - der
    fruehste Name gewinnt deshalb auch ueber eine Zusammenlegung hinweg, und die Feldinvariante
    `place_kind='landmark'` ⇒ `landmark_name` gesetzt kann nicht auseinanderlaufen."""
    for member in members:
        name = _usable_name(member.landmark_name)
        if name is not None:
            return name
    return None


def measured_position(candidate: EventCandidate) -> tuple[float, float] | None:
    """Die SELBST GEMESSENE Position eines Fotos, oder `None` - DIE EINE BEDINGUNG, an der
    "dieses Foto hat einen eigenen Ort" haengt.

    Eine halbe Koordinate ist keine: Beide Werte muessen stehen. Ein uebernommener Ort
    (`EventCandidate.location`) zaehlt hier ausdruecklich NICHT mit; er bestimmt die Grenzen, speist
    den Ortsbezug eines Events aber nie."""
    lat, lon = candidate.gps_lat, candidate.gps_lon
    if lat is None or lon is None:
        return None
    return lat, lon


def has_measured_coordinate(candidate: EventCandidate) -> bool:
    """Das Praedikat zu `measured_position`, fuer Aufrufer, die nur zaehlen wollen.

    Oeffentlich, weil das Messkommando dieselbe Frage stellt: `event_probe.py` weist je Event neben
    der Zellzahl aus, auf wie vielen gemessenen Fotos sie ueberhaupt beruht. Eine zweite Fassung
    dort waere ein zweiter Begriff von "dieses Foto hat einen Ort" im selben Produkt, und die
    ausgewiesene Zahl stuende neben einer Zellzahl, die nach einer anderen Regel entstanden ist.
    Delegiert, statt die Bedingung zu wiederholen - es gibt sie genau einmal."""
    return measured_position(candidate) is not None


def _cells_of(members: Sequence[EventCandidate]) -> tuple[tuple[float, float], ...]:
    """Die verschiedenen gerundeten GEMESSENEN Zellen eines Events, sortiert und dublettenfrei.

    Ausschliesslich gemessene Werte: ein uebernommener Ort bestimmt die Grenzen mit, speist den
    Ortsbezug eines Events aber nie - und darf deshalb auch keinen Namen tragen."""
    return tuple(
        sorted(
            {
                place_cell(*position)
                for member in members
                if (position := measured_position(member)) is not None
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


# --- Stufe 3: das Zusammenlegen zu kleiner Segmente ----------------------------------------------


class EventMergeError(RuntimeError):
    """Die Rundenobergrenze von Stufe 3 ist gerissen.

    WIRFT, statt abzubrechen: Ein stiller Frueabbruch liesse eine halb zusammengelegte Gliederung
    zurueck, die plausibel aussieht und an der niemandem etwas auffiele."""


@dataclass(frozen=True)
class Segment:
    """Ein Abschnitt der Gliederung, BEVOR aus ihm ein `BuiltEvent` wird - samt der Ursachenmenge
    seiner EROEFFNENDEN Grenze.

    `causes` des ersten Segments eines Laufs ist leer; die Ausnahme haengt an der Position, nicht an
    einem einzelnen Signal."""

    members: tuple[EventCandidate, ...]
    causes: frozenset[str]


@dataclass(frozen=True)
class BlockedSegment:
    """Ein zu kleines Segment, das NICHT zugeschlagen werden konnte, samt den Gruenden je Kante
    (Block F).

    `edges` traegt EINEN EINTRAG JE NACHBARN (also einen oder zwei), in der Reihenfolge frueherer,
    spaeterer; je Eintrag die MENGE der Gruende, die diese Kante sperren. Keine Menge ist leer -
    eine offene Kante waere ein zulaessiger Nachbar, und dann waere das Segment nicht gesperrt.
    Hat das Segment ueberhaupt keinen Nachbarn, steht dort der eine Eintrag
    `{MERGE_BLOCK_NO_NEIGHBOUR}`.

    Eine MENGE je Kante, kein einzelner Grund: Mehrere Riegel duerfen gleichzeitig zutreffen, und
    ein Bericht mit einem Grund je Kante unterschluege die spaeter geprueften.

    Daraus entstehen die beiden Zahlen von Block F - "war an einer Kante beteiligt" und "war an
    allen Kanten der Grund"; nur die zweite ist handlungsleitend.

    REIN BEOBACHTET: Die Aufzeichnung aendert an der Gliederung nichts."""

    edges: tuple[frozenset[str], ...]


@dataclass(frozen=True)
class MergeOutcome:
    """Das Ergebnis von Stufe 3 samt seiner GEGENANZEIGE.

    `dissolved_boundaries` und `moved_photo_ids` sind nicht Beiwerk: Beide Abnahmezahlen dieser
    Spec - der Anteil der Ein-Bild-Cluster und die Eventzahl - wuerden von einer zu aggressiven
    Verschmelzung BESSER erfuellt. Ohne diese beiden misst eine Nachmessung nur die
    Unter-Zerstueckelung.

    `moved_photo_ids` ist eine MENGE, kein Zaehler: Ein Segment, das ueber mehrere Runden weiter
    zugeschlagen wird, traegt seine Fotos jedes Mal mit, und eine Summe zaehlte sie doppelt - der
    Anteil ueberstiege hundert Prozent. Gezaehlt werden die Fotos des jeweils ZUGESCHLAGENEN
    Segments; die des aufnehmenden Nachbarn bleiben, wo sie waren."""

    segments: tuple[Segment, ...]
    dissolved_boundaries: int
    moved_photo_ids: frozenset[int]
    # Woran es lag, dass diese Stufe fast nichts aufgeloest hat - je gesperrtem Segment einer.
    # Die GEGENANZEIGE oben misst, wie viel zusammengelegt WURDE; ohne diese Liste bleibt
    # unbeantwortet, was das Uebrige verhindert hat.
    blocked_segments: tuple[BlockedSegment, ...] = ()


def _extent_meters(members: Sequence[EventCandidate]) -> float:
    """Die Diagonale der umschliessenden Box ueber die WIRKSAMEN Koordinaten - dasselbe Mass, das
    `ExtentSignal` fortschreibt. Ohne jede Koordinate `0.0`: Es gibt keine Ausdehnung zu ueberschrei-
    ten, und eine Ausfallrichtung "unendlich" verboete jedes Zusammenlegen ortsloser Segmente."""
    locations = [member.location for member in members if member.location is not None]
    if not locations:
        return 0.0
    return haversine_meters(
        min(location.lat for location in locations),
        min(location.lon for location in locations),
        max(location.lat for location in locations),
        max(location.lon for location in locations),
    )


def _gap_between(earlier: Segment, later: Segment) -> timedelta:
    """Die Zeitluecke UEBER DIE KANTE: vom letzten Foto des frueheren zum ersten des spaeteren."""
    return later.members[0].taken_at - earlier.members[-1].taken_at


def _step_over(earlier: Segment, later: Segment) -> float:
    """Die Entfernung ueber die Kante - `inf`, wenn eine der beiden Seiten keine wirksame
    Koordinate traegt.

    Der Tie-Break braucht eine TOTALE Ordnung. Eine unbestimmbare Entfernung als groesstmoegliche
    zu werten heisst: Ein Nachbar, ueber den nichts bekannt ist, gewinnt keinen Gleichstand. Sie
    schliesst ihn nicht aus - die Riegel entscheiden das, und die Ausdehnung des Ergebnisses ist
    ohne Koordinate `0.0`."""
    from_location = earlier.members[-1].location
    to_location = later.members[0].location
    if from_location is None or to_location is None:
        return math.inf
    return haversine_meters(from_location.lat, from_location.lon, to_location.lat, to_location.lon)


def _may_merge(earlier: Segment, later: Segment, *, merge_max_gap: timedelta) -> frozenset[str]:
    """Drei der VIER RIEGEL plus die unantastbare Grenze - alles, was an einer KANTE haengt und
    deshalb fuer beide Richtungen ueber sie gleich ausfaellt.

    RUECKGABE: die MENGE der Gruende aus `MERGE_BLOCK_REASONS`, die diese Kante sperren - die LEERE
    Menge, wenn sie offen ist. `_neighbour_for` fragt nur, ob die Menge leer ist; die Gruende
    fallen damit dort an, wo die Pruefung ohnehin steht. Eine nachbildende zweite Pruefung im
    Messkommando maesse etwas anderes, als die Stufe tut, waehrend beide fuer sich gruen blieben
    (ADR 0117 Punkt 5).

    EINE MENGE, NIE EIN EINZELNER GRUND, und die Auswertung ist AUSDRUECKLICH NICHT
    KURZGESCHLOSSEN - dieselbe Zusage wie fuer die Signale des Durchlaufs: Mehrere Riegel duerfen
    gleichzeitig zutreffen, und wer nach dem ersten abbricht, unterschlaegt die spaeteren. Das
    traefe zuerst `ausdehnung` als zuletzt geprueften. Der Preis ist, dass die Ausdehnung auch dann
    gerechnet wird, wenn schon die Zeitluecke sperrt.

    RIEGEL (c) PRUEFT `MERGE_EXTENT_MAX_METERS`, NICHT `EVENT_EXTENT_MAX_METERS` (ADR 0118 Punkt 4)
    - eine eigene, groessere Grenze. Praefte er die Trennschwelle, praefte er dieselbe Bedingung,
    deren Ueberschreitung die Trennung ausgeloest hat, und die Stufe waere fuer genau die Segmente
    unpassierbar, die die Ausdehnung getrennt hat.

    Der vierte Riegel (d) - das Segment selbst liegt unter der Mindestgroesse - haengt am Segment,
    nicht an der Kante, und steht bei der Auswahl. Weil hier nur Kanteneigenschaften stehen, ist
    eine Kante fuer beide Richtungen gleichzeitig zulaessig oder gleichzeitig gesperrt: Daran haengt
    die Terminierung (siehe `_round_limit`).

    Aufgeloest wird die EROEFFNENDE Grenze des SPAETEREN Segments - `later.causes` ist also die
    Menge, die ueber die Unantastbarkeit entscheidet."""
    combined = earlier.members + later.members
    # Die Paare werden VOLLSTAENDIG gebaut, bevor die Auswahl sie liest - eine Kette aus
    # `if ... return` waere der Kurzschluss, den diese Stufe gerade nicht haben darf.
    checked = (
        (MERGE_BLOCK_UNBREAKABLE, bool(later.causes & UNBREAKABLE_CAUSES)),
        (MERGE_BLOCK_TIME_GAP, _gap_between(earlier, later) > merge_max_gap),  # (a)
        (MERGE_BLOCK_SPAN, combined[-1].taken_at - combined[0].taken_at > EVENT_MAX_SPAN),  # (b)
        (MERGE_BLOCK_EXTENT, _extent_meters(combined) > MERGE_EXTENT_MAX_METERS),  # (c)
    )
    return frozenset(reason for reason, blocking in checked if blocking)


def _neighbour_for(
    working: Sequence[Segment], index: int, *, merge_max_gap: timedelta
) -> int | None:
    """Der Nachbar, dem ein zu kleines Segment zugeschlagen wird - `None`, wenn keiner haelt.

    Ausschliesslich ANGRENZENDE Segmente, sonst entstuende eine zeitlich zerrissene Einheit.
    Gewaehlt wird nach kleinerer Zeitluecke, bei Gleichstand nach kleinerer Entfernung, danach der
    FRUEHERE (`index - 1 < index + 1`). Haelt keiner, bleibt das Segment allein: ein gueltiges
    Ergebnis, kein Ausnahmezweig."""
    options: list[tuple[timedelta, float, int]] = []
    for neighbour in (index - 1, index + 1):
        if not 0 <= neighbour < len(working):
            continue
        low = min(index, neighbour)
        earlier, later = working[low], working[low + 1]
        # Eine nicht leere Menge heisst gesperrt - WELCHE Gruende es sind, entscheidet hier nichts.
        if _may_merge(earlier, later, merge_max_gap=merge_max_gap):
            continue
        options.append((_gap_between(earlier, later), _step_over(earlier, later), neighbour))
    if not options:
        return None
    return min(options)[2]


def _blocking_edges(
    working: Sequence[Segment], index: int, *, merge_max_gap: timedelta
) -> tuple[frozenset[str], ...]:
    """Je KANTE die Menge ihrer Sperrgruende, in der Reihenfolge frueherer, spaeterer Nachbar - die
    Beobachtung zu einem Segment, das nicht zugeschlagen werden konnte (Block F).

    EIN SEGMENT HAT SO VIELE KANTEN, WIE ES NACHBARN HAT. Eine nicht vorhandene Seite eines
    Randsegments ist KEINE Kante: Sie ist kein Hindernis, und sie mitzuzaehlen hiesse, dass an
    einem Randsegment nie ein Grund "an allen Kanten" steht - die eine handlungsleitende Spalte
    waere dort strukturell leer. `MERGE_BLOCK_NO_NEIGHBOUR` bleibt deshalb dem Fall vorbehalten, in
    dem es UEBERHAUPT keinen Nachbarn gibt (ein einziges Segment im ganzen Lauf); dass dieser
    Eintrag sonst immer null ist, ist eine ehrliche Null.

    AUFGERUFEN ERST, NACHDEM `_neighbour_for` keinen Nachbarn gefunden hat: Dann ist jede Kante
    gesperrt, also keine der zurueckgegebenen Mengen leer.

    Beobachtend: Diese Funktion wird ausschliesslich gelesen, sie entscheidet nichts. Die Gruende
    kommen aus derselben Pruefung, die auch die Stufe fuehrt - nicht aus einer Nachbildung."""
    edges = [
        _may_merge(
            working[min(index, neighbour)],
            working[min(index, neighbour) + 1],
            merge_max_gap=merge_max_gap,
        )
        for neighbour in (index - 1, index + 1)
        if 0 <= neighbour < len(working)
    ]
    if not edges:
        return (frozenset({MERGE_BLOCK_NO_NEIGHBOUR}),)
    return tuple(edges)


def _smallest_open_index(
    working: Sequence[Segment], blocked: Sequence[bool], minimum: int
) -> int | None:
    """Das kleinste Segment, das NICHT BEREITS ALS GESPERRT FESTSTEHT - bei Gleichstand das
    fruehere (strikt `<`). Der Zusatz "nicht gesperrt" traegt die Terminierung: ohne ihn waehlte
    jede Runde dasselbe gescheiterte Segment erneut."""
    best: int | None = None
    for index, segment in enumerate(working):
        if blocked[index] or len(segment.members) >= minimum:  # (d)
            continue
        if best is None or len(segment.members) < len(working[best].members):
            best = index
    return best


def _round_limit(segment_count: int) -> int:
    """Die Rundenobergrenze: so viele Runden, wie es Segmente gibt.

    Sie haelt, weil je Runde genau eines geschieht - zusammenlegen (die Segmentzahl faellt um eins)
    oder ein Segment sperren. Ein gesperrtes Segment wird durch keine spaetere Runde wieder
    zulaessig: Die Riegel (a)-(c) und die Unantastbarkeit haengen an der Kante, und ein Nachbar kann
    durch Zuwachs nur groesser werden. Es kann auch nicht als Nachbar aufgesogen werden, weil eine
    Kante fuer beide Richtungen gleich ausfaellt. Zusammenlegungen und Sperrungen zusammen koennen
    die Segmentzahl daher nicht ueberschreiten.

    Eigene Funktion, damit ein Test die Grenze unterschreiten und nachweisen kann, dass sie WIRFT
    statt abzubrechen - anders ist ein Sicherungsnetz nicht pruefbar, das im Betrieb nie greift."""
    return segment_count


def merge_small_segments(
    segments: Sequence[Segment],
    *,
    min_event_photos: int | None = None,
    merge_max_gap: timedelta | None = None,
) -> MergeOutcome:
    """Die DRITTE Stufe der Event-Bildung: zu kleine Segmente werden je einem angrenzenden
    zugeschlagen. REIN, oeffentlich und direkt pruefbar - nicht nur durch `build_events` hindurch.

    Ob ein Segment zu klein ist, steht erst fest, wenn es abgeschlossen ist; im vorwaerts
    entscheidenden `BoundarySignal`-Protokoll ist das nicht ausdrueckbar. Deshalb eine Stufe NACH
    dem Durchlauf und kein weiteres Signal.

    Das Ergebnissegment traegt die Ursachenmenge des FRUEHEREN der beiden - seine eroeffnende
    Grenze bleibt bestehen, aufgeloest wird die dazwischen. Index 0 behaelt damit seine leere
    Menge, gleich in welche Richtung dort zusammengelegt wird.

    `min_event_photos` und `merge_max_gap` sind injizierbar (`None` = Modulkonstante). Ohne das
    liefen die Faelle der Signale still durch diese Stufe hindurch, und eine Durchrechnung koennte
    die beiden Werte nicht variieren - sie sind keine Signale."""
    minimum = MIN_EVENT_PHOTOS if min_event_photos is None else min_event_photos
    gap = MERGE_MAX_GAP if merge_max_gap is None else merge_max_gap

    working = list(segments)
    blocked = [False] * len(working)
    reported: list[BlockedSegment] = []
    limit = _round_limit(len(working))
    dissolved = 0
    moved: set[int] = set()
    rounds = 0

    while (index := _smallest_open_index(working, blocked, minimum)) is not None:
        rounds += 1
        if rounds > limit:
            raise EventMergeError(
                f"Stufe 3 hat die Rundenobergrenze von {limit} gerissen. Eine halb "
                "zusammengelegte Gliederung darf nicht zurueckbleiben."
            )
        neighbour = _neighbour_for(working, index, merge_max_gap=gap)
        if neighbour is None:
            # BEOBACHTET IN DEM AUGENBLICK, IN DEM ES FESTSTEHT: Ein gesperrtes Segment wird durch
            # keine spaetere Runde wieder zulaessig (siehe `_round_limit`), und spaeter waeren die
            # Nachbarn womoeglich andere.
            reported.append(
                BlockedSegment(edges=_blocking_edges(working, index, merge_max_gap=gap))
            )
            blocked[index] = True
            continue
        low = min(index, neighbour)
        merged = Segment(
            members=working[low].members + working[low + 1].members,
            causes=working[low].causes,
        )
        moved.update(member.photo_id for member in working[index].members)
        working[low : low + 2] = [merged]
        blocked[low : low + 2] = [False]
        dissolved += 1

    return MergeOutcome(
        segments=tuple(working),
        dissolved_boundaries=dissolved,
        moved_photo_ids=frozenset(moved),
        blocked_segments=tuple(reported),
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
    Schwellenaenderung veraltet, ohne dass es auffiele.

    `dissolved_boundaries` und `moved_photos` sind die GEGENANZEIGE von Stufe 3 (siehe
    `MergeOutcome`). Sie beziehen sich auf die Gliederung VOR dem Zusammenlegen; die Zahl der
    Grenzen davor ist `len(events) - 1 + dissolved_boundaries`.

    `blocked_segments` ist die Gegenfrage dazu: woran es lag, dass das Uebrige NICHT zusammengelegt
    wurde (Block F). Sie reicht die Beobachtung der Stufe durch, statt dass ein Aufrufer sie
    nachbildet."""

    events: tuple[BuiltEvent, ...]
    causes: tuple[frozenset[str], ...]
    dissolved_boundaries: int = 0
    moved_photos: int = 0
    blocked_segments: tuple[BlockedSegment, ...] = ()


def build_events(
    candidates: Iterable[EventCandidate],
    signals: list[BoundarySignal] | None = None,
    *,
    min_event_photos: int | None = None,
    merge_max_gap: timedelta | None = None,
) -> list[BuiltEvent]:
    """Die Event-Bildung - die Gliederung ohne ihre Erklaerung.

    EIN Rechenweg, zwei Sichten: Diese Funktion ist `explain_events` ohne die Ursachenmengen. Ein
    zweiter Durchlauf fuer dasselbe liefe auseinander, und dann maesse das Messkommando die
    Grenzen einer Gliederung, die so nie entstanden ist."""
    return list(
        explain_events(
            candidates,
            signals,
            min_event_photos=min_event_photos,
            merge_max_gap=merge_max_gap,
        ).events
    )


def explain_events(
    candidates: Iterable[EventCandidate],
    signals: list[BoundarySignal] | None = None,
    *,
    confirming_photos: int | None = None,
    motif_presence_threshold: float | None = None,
    min_event_photos: int | None = None,
    merge_max_gap: timedelta | None = None,
) -> EventFormation:
    """Die Event-Bildung in DREI Stufen: die Motivgrenzen, der Durchlauf ueber die Signale und das
    Zusammenlegen zu kleiner Segmente - samt der Ursache jeder Grenze.

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
    ist deren vollstaendige Ruecksetzung. Eine erst spaeter faellige Grenze von Ausdehnung oder
    Schritt kann dadurch entfallen, weil an der frueheren Stelle bereits getrennt wurde.

    Erst NACH Stufe 3 bildet `_built` die Events. Weil das die einzige Stelle bleibt, an der Name,
    Zellen und `place_kind` entstehen, stimmen diese Werte fuer ein zusammengelegtes Event ohne
    eigenen Zweig, und `position` laeuft ohne Nacharbeit lueckenlos ab 1.

    `signals` ist injizierbar; ohne Angabe gilt `default_signals()`. Ebenso die beiden
    Festlegungen der ersten Stufe (`confirming_photos`, `motif_presence_threshold`) und die beiden
    der dritten (`min_event_photos`, `merge_max_gap`), jeweils `None` = Modulkonstante. Die
    Empfindlichkeitsmessung braucht die Ursachenmengen DIESES Durchlaufs unter variierten Werten,
    nicht die einer Nachbildung."""
    ordered = sorted(candidates, key=lambda candidate: (candidate.taken_at, candidate.photo_id))
    forced_starts = motif_change_starts(
        ordered,
        confirming_photos=confirming_photos,
        motif_presence_threshold=motif_presence_threshold,
    )
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

    outcome = merge_small_segments(
        [
            Segment(members=tuple(members), causes=cause)
            for members, cause in zip(events, causes, strict=True)
        ],
        min_event_photos=min_event_photos,
        merge_max_gap=merge_max_gap,
    )

    return EventFormation(
        events=tuple(
            _built(position, segment.members)
            for position, segment in enumerate(outcome.segments, start=1)
        ),
        causes=tuple(segment.causes for segment in outcome.segments),
        dissolved_boundaries=outcome.dissolved_boundaries,
        moved_photos=len(outcome.moved_photo_ids),
        blocked_segments=outcome.blocked_segments,
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
