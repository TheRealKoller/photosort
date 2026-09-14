"""Die Ortsauskunft zu einer vergroeberten Zelle - REIN und DB-FREI.

Dieses Modul beantwortet ausschliesslich "was liegt an dieser Zelle" und kennt die
UNSPEZIFISCHE Stufe (`locality`). Die Gleichnamigkeitspruefung ueber die Events eines Laufs und
das Anhaengen des Viertels liegen in `events.py` - die zusammengesetzte Form "Ort, Viertel"
entsteht dort und ist von hier aus strukturell nicht erreichbar (ADR 0102 Punkt 4).

LOGGING-AUFLAGE fuer jede kuenftige Logzeile dieses Moduls: weder eine Koordinate noch ein
Ortsname gehoert je in ein Log - kein angenommener und kein verworfener Wert. Ein Log ist eine
schwaecher geschuetzte und laenger lebende Oberflaeche als die Datenbank.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from photosort.cloud_vision import _sanitize_label_text

# Die Koernung, mit der gefragt und abgelegt wird: zwei Nachkommastellen sind rund 1,1 km x
# 0,7 km. SICHERHEITSENTSCHEIDUNG, keine Anzeigerundung - verlaesst etwas das System, dann diese
# Zelle. Groeber (rund 11 km) traefe in einer Stadt mehrere Gemeinden und machte die
# Viertel-Regel unerfuellbar; feiner (rund 110 m) traefe Wohnadress-Aufloesung.
#
# EINE Aenderung dieses Werts ist eine Datenschutzaenderung und nimmt `place_lookups` mit: die
# Migration, die ihn aendert, leert die Tabelle - sonst blieben die unter der alten Koernung
# abgelegten Zeilen unerreichbar, aber vorhanden liegen.
PLACE_CELL_DIGITS = 2

# Die Koernung, mit der eine Koordinate das System VERLAESST: eine Nachkommastelle sind rund 11 km
# in der Breite, weniger in der Laenge. Sie gilt fuer die Ortsangabe an die
# Sehenswuerdigkeits-Erkennung (ADR 0106 Punkt 3) und ist damit eine Groessenordnung groeber als
# die oben abgelegte und in der Oberflaeche gezeigte Zelle.
#
# SICHERHEITSENTSCHEIDUNG, keine Genauigkeit: Die Stufe greift genau dort, wo sich kein Ortsname
# aufloesen liess - in duenn besiedelter Gegend, wo eine Koordinate mehr ueber die Familie verraet
# als in einer Stadt. Wer diesen Wert VERFEINERT, gibt mehr ueber jedes Foto ohne aufloesbaren
# Ortsnamen preis; das braucht eine eigene ADR, keine stillschweigende Anpassung.
LANDMARK_PLACE_CELL_DIGITS = 1

# Der geschlossene Vorrat von `matched_level`, von der feinsten zur groebsten Ebene. Ein Wert
# ausserhalb heisst "kein Name aufgeloest" - Mitgliedschaftspruefung statt Cast, nie eine 500
# (Muster `events.py::PLACE_KINDS`).
PLACE_LEVELS = ("neighbourhood", "locality", "region", "country")

# Die beiden Ebenen, auf denen ein Treffer einen ORTSNAMEN traegt - abgeleitet aus der
# Reihenfolge oben statt ein zweites Mal ausgeschrieben, damit beide nicht auseinanderlaufen
# koennen. Ein Treffer auf `region`/`country` gilt als "kein Name aufgeloest", nie als
# duerftiger, aber brauchbarer Name.
NAME_BEARING_LEVELS = PLACE_LEVELS[:2]

# Obergrenze eines verwendbaren Ortsnamens, gleichauf mit `landmark.MAX_LANDMARK_NAME_LENGTH`.
# Wie dort wird VERWORFEN statt abgeschnitten, und das ist hier Korrektheit statt Hygiene:
# `assign_place_names` VERGLEICHT Ortsnamen ueber die Events eines Laufs - zwei verschiedene, auf
# dieselbe Laenge gekappte Namen waeren ein Name, und die Viertel-Regel griffe dann fuer Events
# an verschiedenen Orten.
MAX_PLACE_NAME_LENGTH = 80


def place_cell(lat: float, lon: float) -> tuple[float, float]:
    """Die EINE Rundung des Projekts - `events.py` bildet seine Ortszelle darueber.

    `-0.0` wird auf `0.0` normalisiert: es waere im JSON `-0.0` und in der Anzeige `"-0.00"`, eine
    Himmelsrichtung, die es nicht gibt. Die Addition von `0.0` erledigt das nach IEEE 754 ohne
    Sonderfallzweig."""
    return (round(lat, PLACE_CELL_DIGITS) + 0.0, round(lon, PLACE_CELL_DIGITS) + 0.0)


def landmark_place_cell(lat: float, lon: float) -> tuple[float, float]:
    """Die EINE Vergroeberung dessen, was als Koordinate hinausgeht (S1).

    Getrennt von `place_cell` darueber, weil die Fragen verschieden sind: dort die Koernung, mit
    der gefragt und abgelegt wird, hier die Grenze dessen, was dieses System an Ortsdaten der
    Familie herausgibt. Die `PlaceResolver`-Signaturgrenze deckt diesen Rand nicht - der sendende
    Rand ist hier kein Auflöser, sondern der Vision-Client.

    Sie steht als Funktion und nicht an der Aufrufstelle: `landmark.py::place_hint_for` ist heute
    der einzige Aufrufer, und eine zweite Aufrufstelle bekaeme eine dort nachgerechnete Rundung
    nicht mit.

    `-0.0` wird auf `0.0` normalisiert, aus demselben Grund wie oben.

    Die TEXTFORM entsteht bewusst nicht hier, sondern in `landmark.py` unmittelbar am Prompt: Ein
    Modul, das zwei Ortswerte zu einer Zeichenkette zusammensetzt, waere genau die Form, die ADR
    0102 Punkt 4 diesem Modul untersagt (Waechter in
    tests/test_places.py::TestTheModuleBoundaryFromAdr0102)."""
    return (
        round(lat, LANDMARK_PLACE_CELL_DIGITS) + 0.0,
        round(lon, LANDMARK_PLACE_CELL_DIGITS) + 0.0,
    )


def sanitize_place_name(raw: object) -> str | None:
    """Der einzige Weg, auf dem ein Ortsname in PhotoSort verwendbar wird.

    Zeichensanitisierung mit DERSELBEN Funktion wie der Sehenswuerdigkeits- und der
    Feinlabel-Pfad (`cloud_vision.py::_sanitize_label_text`, nie eine zweite Fassung davon),
    danach die Laengengrenze. `None` heisst "kein verwendbarer Name" - Nicht-String, leer nach der
    Sanitisierung, oder laenger als `MAX_PLACE_NAME_LENGTH`.

    Ein Ortsdatensatz ist ebenso von Dritten geschrieben wie eine Dienstantwort; die Auflage haengt
    an der Herkunft des Textes, nicht an der Anwesenheit eines Netzwerks. Je Stufe EINZELN
    anzuwenden: eine unbrauchbare Stufe wird `None`, nie die ganze Antwort verworfen."""
    if not isinstance(raw, str):
        return None
    sanitized = _sanitize_label_text(raw)
    if not sanitized or len(sanitized) > MAX_PLACE_NAME_LENGTH:
        return None
    return sanitized


@dataclass(frozen=True)
class PlaceAnswer:
    """Was ein Auflöser ueber eine Zelle sagt - in STUFEN, nie als fertiger Anzeigename.

    Vier benannte Stufen und KEIN offener Beutel fuer alles Weitere: Antworten tragen regelmaessig
    Strasse und Hausnummer, die am Parser-Rand verworfen werden und kein Feld erreichen. Ein
    offener Beutel waere genau der Weg, auf dem sie doch ankaemen.

    `matched_level` ist die AUSSAGE DES ANBIETERS darueber, was er getroffen hat, aus `PLACE_LEVELS`
    - keine Ableitung daraus, welche Stufen gefuellt sind. Beides kann auseinanderfallen: eine
    Antwort auf Regionsebene nennt oft trotzdem eine Stadt, und die liegt dann womoeglich Dutzende
    Kilometer entfernt. `None` heisst "keine Ebene, die dieses Projekt fuehrt"."""

    neighbourhood: str | None
    locality: str | None
    region: str | None
    country: str | None
    matched_level: str | None


@dataclass(frozen=True)
class PlaceInfo:
    """Die LESESICHT auf eine abgelegte Auskunft - nur, was zu einem Namen beitraegt.

    Region und Land stehen bewusst nicht darin: ein Treffer, der nur sie benennt, gilt als "kein
    Name aufgeloest", nie als duerftiger, aber brauchbarer Name."""

    neighbourhood: str | None
    locality: str | None
    matched_level: str | None


class PlaceResolver(Protocol):
    """Die eine Schnittstelle, hinter der die Wegwahl steht (ADR 0102 Punkt 6).

    SICHERHEIT (S2): Die Signatur nimmt ausschliesslich die bereits vergroeberte Zelle entgegen -
    weder ein Foto noch ein Event noch eine ungerundete Koordinate ist darueber erreichbar.
    `None` heisst "keine Antwort" (Netzfehler, Zeitueberschreitung, Dienst unerreichbar) und ist
    ausdruecklich etwas anderes als eine Antwort ohne brauchbare Ebene: die eine hinterlaesst
    keine Auskunft und wird erneut gefragt, die andere hinterlaesst eine und wird es nicht."""

    async def resolve(self, cell: tuple[float, float]) -> PlaceAnswer | None: ...


def usable_locality(info: PlaceInfo | None) -> str | None:
    """Der aufgeloeste ORTSNAME dieser Zelle, oder `None` - die Stufenpruefung an EINER Stelle.

    Ein Name gilt als aufgeloest, wenn `matched_level in {"neighbourhood", "locality"}` UND
    `locality` gesetzt ist. Bei Widerspruch zwischen Ebene und gefuellter Stufe GEWINNT DIE
    ANBIETERANGABE: ein Treffer auf Regionsebene nennt oft trotzdem eine Stadt, die hier nicht
    gilt.

    Ein Wert ausserhalb von `PLACE_LEVELS` ergibt "kein Name", nie eine Ausnahme."""
    if info is None or info.matched_level is None:
        return None
    if info.matched_level not in NAME_BEARING_LEVELS:
        return None
    return info.locality
