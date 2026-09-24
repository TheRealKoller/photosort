"""Der lokale Ortsdatensatz als `PlaceResolver` - der Produktivpfad der Ortsauflösung.

Gelesen wird der vorbereitete AUSZUG auf dem Volume `place_dataset`, den das getippte Kommando
`python -m photosort.place_dataset` erzeugt (ADR 0105 Punkt 3). Dieses Modul BEZIEHT nichts und
sendet nichts: es liest eine lokale Datei. Der einzige Abruf bei GeoNames steht im Bezugskommando
und tritt nur ein, wenn er getippt wird.

GEPRÜFT WIRD DER AUSZUG SELBST, also genau die Datei, die gelesen wird - vor jedem Gebrauch gegen
den beim Bezug gebildeten Hash. Stimmt er nicht oder fehlt die Datei, wird KEIN Auflöser gebaut
(Muster `build_landmark_client` ohne Einwilligung): kein stiller Ersatzweg, eine laute Zeile mit
festem Grund-Token. Die Events behalten dann Nummer und Zeitspanne, der Lauf läuft durch - das ist
der Zustand von heute, kein Fehlerzustand.

LOGGING-AUFLAGE (S11): Weder eine Koordinate noch ein Ortsname gehört je in eine Logzeile dieses
Moduls - kein angenommener und kein verworfener Wert. Geloggt wird ein festes Grund-Token.

SICHERHEIT (S7): Der Inhalt des Datensatzes ist FREMDTEXT. Ein Ortsdatensatz ist ebenso von
Dritten geschrieben wie eine Dienstantwort; die Auflage hängt an der Herkunft des Textes, nicht an
der Anwesenheit eines Netzwerks. Jeder Name läuft deshalb durch `places.sanitize_place_name` -
verworfen wird ganz, nie abgeschnitten.

DER ZWEITE AUSZUG (Spec 0529, ADR 0123): Neben dem Ortsauszug entsteht aus demselben Bezug ein
zweiter Auszug mit den Klassen `S`, `T`, `L`, `H`, `V` und zusätzlich dem Feld `alternatenames`.
Er wird hier von einem EIGENEN Leser gelesen - `LandmarkGazetteer`, namensgeschlüsselt statt
ortsgeschlüsselt - und mit eigenen Grund-Token geprüft. Die eine Faltung
(`fold_landmark_name`) benutzen beide Seiten; die Sanitisierung steht davor, und
`alternatenames` wird vor der Faltung am Komma zerlegt (S5).
"""

from __future__ import annotations

import gzip
import hashlib
import logging
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, TextIO, cast

from photosort.config import settings
from photosort.landmark import sanitize_landmark_name
from photosort.places import (
    PLACE_LEVELS,
    PlaceAnswer,
    PlaceResolver,
    sanitize_place_name,
)
from photosort.scoring import haversine_meters

logger = logging.getLogger(__name__)

# Die vergroeberte Ortszelle, wie `places.place_cell` sie bildet.
Cell = tuple[float, float]


class PlaceDatasetError(Exception):
    """Der Ortsdatensatz ist nicht benutzbar (fehlt, oder weicht von seinem Hash ab).

    Meldungen nennen Bedingung und Grund-Token, nie eine Koordinate und nie einen Ortsnamen."""


# --- Das Format ---------------------------------------------------------------------------------
#
# Die Ebene kommt aus `featureClass`/`featureCode`, NICHT aus der Bevoelkerungszahl: viele
# `PPLX`-Eintraege (die Viertel-Ebene) tragen `population = 0`, und ein nach Einwohnern
# gefilterter Extrakt naehme die Frage nach der Viertel-Abdeckung negativ vorweg.
GEONAMES_NEIGHBOURHOOD_CODE = "PPLX"
GEONAMES_NAME_FIELD = 1
GEONAMES_LAT_FIELD = 4
GEONAMES_LON_FIELD = 5
GEONAMES_FEATURE_CLASS_FIELD = 6
GEONAMES_FEATURE_CODE_FIELD = 7
GEONAMES_FIELD_COUNT = 8

# Die fuenf tatsaechlich gelesenen Felder. Der Auszug behaelt genau sie, an UNVERAENDERTER
# Spaltenposition - deshalb stehen sie hier, beim Leser, und nicht beim Erzeuger: so kann die
# Gleichheit von Rohdatei und Auszug nicht durch zwei driftende Feldlisten verlorengehen.
GEONAMES_KEPT_FIELDS = (
    GEONAMES_NAME_FIELD,
    GEONAMES_LAT_FIELD,
    GEONAMES_LON_FIELD,
    GEONAMES_FEATURE_CLASS_FIELD,
    GEONAMES_FEATURE_CODE_FIELD,
)

# Klasse `P` ist ein Ort, Klasse `A` die Verwaltungsebene. Alles andere (Berge, Gewaesser,
# Bauwerke) traegt keine Ebene, die dieses Projekt fuehrt, und faellt aus dem Auszug.
GEONAMES_KEPT_FEATURE_CLASSES = ("P", "A")

# Die Klassen des ZWEITEN Auszugs: `S` Gebaeude/Gueter/Farmen, `T` Berge/Huegel/Felsen, `L`
# Gebiete/Parks, `H` Gewaesser, `V` Waelder. Keine kuratierte `featureCode`-Liste darin - eine
# solche waere eine Wertung darueber, was eine Sehenswuerdigkeit sein darf, die niemand pflegt und
# deren Luecken still Namen kosten (ADR 0123 Punkt 1).
GEONAMES_LANDMARK_FEATURE_CLASSES = ("S", "T", "L", "H", "V")

# `alternatenames` ist Feld 3. Es wird gelesen, aber NICHT als Name allein: jedes Element ist ein
# eigener Suchschluessel, und die Zerlegung am Komma geschieht vor der Faltung (S5c). `asciiname`
# (Feld 2) bleibt ungenutzt - kein gemessener Name war allein ueber es auffindbar.
GEONAMES_ALTERNATE_NAMES_FIELD = 3

# Die sechs tatsaechlich gelesenen Felder des zweiten Auszugs, an UNVERAENDERTER Spaltenposition -
# dieselbe Begruendung wie bei `GEONAMES_KEPT_FIELDS`: die Feldliste steht beim Leser, damit die
# Gleichheit von Rohdatei und Auszug nicht durch zwei driftende Listen verlorengeht.
GEONAMES_LANDMARK_KEPT_FIELDS = (
    GEONAMES_NAME_FIELD,
    GEONAMES_ALTERNATE_NAMES_FIELD,
    GEONAMES_LAT_FIELD,
    GEONAMES_LON_FIELD,
    GEONAMES_FEATURE_CLASS_FIELD,
    GEONAMES_FEATURE_CODE_FIELD,
)

# Die Grenze der Ortsplausibilitaet (ADR 0123 Punkt 5) - eine EIGENE Konstante, NICHT
# `GEONAMES_MAX_DISTANCE_METERS`: dort geht es darum, ab wann ein Ortsname keiner mehr ist, hier
# darum, ab wann eine Entfernung eine Verwechslung beweist. Beide muessen sich unabhaengig bewegen
# koennen. Dokumentiert-unkalibriert: es gibt keinen Foto-Korpus, gegen den sie sich kalibrieren
# liesse - eine Kalibrierung ist ausdruecklich Out Scope dieser Spec.
LANDMARK_PLAUSIBILITY_RADIUS_METERS = 50_000.0


def _coordinates_in_band(lat_text: str, lon_text: str) -> Cell | None:
    """Breiten-/Laengengrad als Zahlenpaar, oder `None` ausserhalb des Bands.

    S6: EINE Stelle fuer BEIDE Auszuege. Geprueft wird als Bereichsvergleich, NIE geklemmt - ein
    geklemmter Wert staende als Fundort in der JSON-Spalte, verwuerfe den Namen lautlos bei jedem
    kuenftigen Lauf, und ein Lesepfad, der die Spalte ausliefert, legte die Antwort auf `500`.
    `NaN` faellt durch jeden der beiden Vergleiche."""
    try:
        lat = float(lat_text)
        lon = float(lon_text)
    except ValueError:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


@dataclass(frozen=True)
class GeoNamesEntry:
    """Eine Zeile des Datensatzes, auf die fuenf gebrauchten Felder reduziert."""

    name: str
    lat: float
    lon: float
    feature_class: str
    feature_code: str


def parse_geonames_line(line: str) -> GeoNamesEntry | None:
    """Eine tab-getrennte Zeile, oder `None` bei jeder Unregelmaessigkeit.

    Der Name laeuft durch `sanitize_place_name` (S7). Eine Zeile ohne verwendbaren Namen faellt
    ganz weg - verworfen, nie abgeschnitten."""
    fields = line.rstrip("\n").split("\t")
    if len(fields) < GEONAMES_FIELD_COUNT:
        return None
    name = sanitize_place_name(fields[GEONAMES_NAME_FIELD])
    if name is None:
        return None
    coordinates = _coordinates_in_band(fields[GEONAMES_LAT_FIELD], fields[GEONAMES_LON_FIELD])
    if coordinates is None:
        return None
    lat, lon = coordinates
    return GeoNamesEntry(
        name=name,
        lat=lat,
        lon=lon,
        feature_class=fields[GEONAMES_FEATURE_CLASS_FIELD],
        feature_code=fields[GEONAMES_FEATURE_CODE_FIELD],
    )


# --- Der zweite Auszug: Faltung, Parser und Namensverzeichnis (Spec 0529, ADR 0123) ------------

# „Trennzeichen zu Leerzeichen" (ADR 0123 Punkt 5): jede Nicht-Wort-Folge wird zu EINEM Leerzeichen
# zusammengezogen, Unterstrich eingeschlossen. Das KOMMA ist ausgenommen: `alternatenames` wird
# vorher am Komma zerlegt, und würde das Zeichen hier zu einem Leerzeichen, verschmölzen alle
# Alternativnamen einer Zeile zu einem einzigen Riesenschlüssel (S5c).
_FOLD_SEPARATORS = re.compile(r"[^\w,]+|_")


def fold_landmark_name(raw: str) -> str:
    """Der gefaltete Suchschluessel eines Sehenswuerdigkeitsnamens - die EINE Faltung.

    ADR 0123 Punkt 5: Kleinschreibung, getrennte Diakritika, Trennzeichen zu Leerzeichen. Sie
    liegt HIER und nicht in `landmark_names.py`, weil beide Seiten sie benutzen - diesseits beim
    Aufbau des Suchverzeichnisses, jenseits beim Ablegen des gefalteten Namens in
    `landmark_place_lookups`. Zwei Fassungen liefen auseinander, und die Suche schlüge still fehl.

    Sie gleicht NUR an und entfernt nie ein Zeichen ersatzlos: aus `A/B` wird `A B`, nicht `AB`.
    Eine zu aggressive Faltung zöge verschiedene Sehenswürdigkeiten zusammen und BESTÄTIGTE dann
    einen falschen Namen (S5d)."""
    decomposed = unicodedata.normalize("NFKD", raw)
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    separated = _FOLD_SEPARATORS.sub(" ", without_marks.casefold())
    return " ".join(separated.split())


@dataclass(frozen=True)
class LandmarkEntry:
    """Ein Eintrag des zweiten Auszugs: alle gefalteten Namen und der eine Fundort.

    `folded_names` traegt den gefalteten `name` und jedes gefaltete Element von `alternatenames` -
    fuer die Suche ist beides gleichwertig (S5). Ein Element, das die Sanitisierung nicht
    uebersteht, fehlt hier; der Eintrag bleibt, solange IRGENDEIN Name uebrig bleibt."""

    folded_names: tuple[str, ...]
    lat: float
    lon: float


def parse_landmark_line(line: str) -> LandmarkEntry | None:
    """Eine Rohzeile des zweiten Auszugs als Eintrag, oder `None`, wenn sie nichts beitraegt.

    S5: Jeder Name - `name` wie jedes Element von `alternatenames` - laeuft EINZELN durch
    `sanitize_landmark_name` (dieselbe Funktion wie die Cloud-Pfade) und wird bei Ueberlaenge ganz
    verworfen, nie gekuerzt; ein Element, das die Sanitisierung nicht uebersteht, faellt fuer sich
    weg, nie die ganze Zeile. Die Faltung laeuft DANACH - davor zoege sie Bidi- und
    Zero-Width-Zeichen in den Schluessel (S5b). Die Koordinaten kommen aus der einen Bandpruefung
    (`_coordinates_in_band`), die auch der Ortsauszug benutzt (S6)."""
    fields = line.rstrip("\n").split("\t")
    if len(fields) < GEONAMES_FIELD_COUNT:
        return None
    coordinates = _coordinates_in_band(fields[GEONAMES_LAT_FIELD], fields[GEONAMES_LON_FIELD])
    if coordinates is None:
        return None
    lat, lon = coordinates

    raw_names = [fields[GEONAMES_NAME_FIELD]]
    raw_names.extend(fields[GEONAMES_ALTERNATE_NAMES_FIELD].split(","))
    folded: list[str] = []
    for raw_name in raw_names:
        name = sanitize_landmark_name(raw_name)
        if name is None:
            continue
        folded_name = fold_landmark_name(name)
        if folded_name and folded_name not in folded:
            folded.append(folded_name)
    if not folded:
        return None
    return LandmarkEntry(folded_names=tuple(folded), lat=lat, lon=lon)


class LandmarkGazetteer:
    """Das Namensverzeichnis des zweiten Auszugs: gefalteter Name → Fundorte.

    EIN Durchgang durch den Auszug, und behalten wird ausschliesslich, was zu einem GESUCHTEN
    Namen gehoert: Die gesuchte Namensmenge kommt in den Konstruktor (S7) - ein Gazetteer, der den
    vollen Auszug haelt, erschoepft den Worker-Prozess, und die Ausfallrichtung waere ein OOM
    mitten in einem Lauf, nach den bezahlten Cloud-Aufrufen.

    Jeder gesuchte Name hat einen Eintrag, notfalls die LEERE Punktmenge: Das ist der Zustand
    „nachgeschlagen, ohne Fund" und strikt verschieden von „nie nachgeschlagen" - der fehlenden
    Zeile in `landmark_place_lookups` (ADR 0123 Punkt 2). Ohne offene Namen wird die Datei gar
    nicht erst geoeffnet.

    `names` sind bereits gefaltete Namen; die Faltung auf der Auszugsseite besorgt
    `fold_landmark_name` in `parse_landmark_line`."""

    def __init__(self, path: Path, names: Iterable[str]) -> None:
        points: dict[str, list[Cell]] = {name: [] for name in names}
        if points:
            if not path.is_file():
                raise PlaceDatasetError(
                    f"Der Sehenswuerdigkeitsauszug liegt nicht unter dem angegebenen Pfad "
                    f"({LANDMARK_DATASET_REASON_MISSING})."
                )
            with _open_text(path) as handle:
                for line in handle:
                    entry = parse_landmark_line(line)
                    if entry is None:
                        continue
                    for folded_name in entry.folded_names:
                        if folded_name in points:
                            points[folded_name].append((entry.lat, entry.lon))
        self._points: dict[str, tuple[Cell, ...]] = {
            name: tuple(cells) for name, cells in points.items()
        }

    def points(self, name: str) -> tuple[Cell, ...]:
        """Die Fundorte zu einem gesuchten Namen - `()` heisst „nachgeschlagen, kein Fund"."""
        return self._points.get(name, ())


def geonames_level(entry: GeoNamesEntry) -> str | None:
    """Die Ebene EINES Eintrags, oder `None` fuer alles, was dieses Projekt nicht fuehrt.

    `PPLX` ("section of populated place") ist die Viertel-Ebene. Klasse `A` ist die
    Verwaltungsebene - genau der als wertlos eingestufte Fall: `ADM*` ergibt `region`, `PCL*` ein
    Land. Beides traegt keinen Ortsnamen."""
    if entry.feature_class == "P":
        if entry.feature_code == GEONAMES_NEIGHBOURHOOD_CODE:
            return "neighbourhood"
        return "locality"
    if entry.feature_class == "A":
        if entry.feature_code.startswith("PCL"):
            return "country"
        if entry.feature_code.startswith("ADM"):
            return "region"
    return None


def _nearest_per_level(
    entries: Iterable[GeoNamesEntry], cell: Cell
) -> dict[str, tuple[float, str]]:
    """Je Ebene der NAECHSTGELEGENE Eintrag in der Nachbarschaft, als `(Entfernung, Name)`.

    DIE EINE Nachbarschaftssuche: `geonames_answer` nimmt davon den Namen, das Messkommando ueber
    `geonames_match_distances` die Entfernung. Eine zweite Fassung maesse die Entfernung zu einem
    Eintrag, dessen Name gar nicht vergeben wurde."""
    lat, lon = cell
    nearest: dict[str, tuple[float, str]] = {}
    for entry in entries:
        level = geonames_level(entry)
        if level is None:
            continue
        distance = haversine_meters(lat, lon, entry.lat, entry.lon)
        if distance > GEONAMES_MAX_DISTANCE_METERS:
            continue
        current = nearest.get(level)
        if current is None or distance < current[0]:
            nearest[level] = (distance, entry.name)
    return nearest


def geonames_match_distances(entries: Iterable[GeoNamesEntry], cell: Cell) -> dict[str, float]:
    """Je Ebene die Entfernung in METERN zu dem Eintrag, der ihren Namen geliefert haette - OHNE
    diesen Namen.

    EIN EIGENER RUECKGABEWEG, ausschliesslich fuer das Messkommando (Spec 0506 Block C2,
    Sicherheitsauflage S4). Die Zahl kommt AUSDRUECKLICH NICHT auf `PlaceAnswer`: Deren
    geschlossener Stufenvorrat ist selbst eine Zusage, und ein Feld dort waere der Weg an den
    `PlaceLookup`-Schreibrand in `worker.py`. Sie wird nicht persistiert, erreicht weder
    `PlaceInfo` noch `place_hint_for` und keinen Modell-Prompt.

    GRUND: Die Entfernung zu einem benannten, oeffentlich enumerierbaren Eintrag ist ein
    Trilaterationsmittel - `locality` und `neighbourhood` derselben Zelle schneiden sich zu rund
    zwei Punkten und unterlaufen die 1,1-km-Koernung, die `PLACE_CELL_DIGITS = 2` zusichert. Wer
    sie ausgibt, tut das deshalb in Klassen und nie je Zelle."""
    return {level: distance for level, (distance, _) in _nearest_per_level(entries, cell).items()}


def geonames_answer(entries: Iterable[GeoNamesEntry], cell: Cell) -> PlaceAnswer | None:
    """Die Auskunft zu einer Zelle aus den Eintraegen in ihrer Nachbarschaft.

    Je Ebene gewinnt der NAECHSTGELEGENE Eintrag. `matched_level` ist die FEINSTE getroffene
    Ebene; ohne jeden verwertbaren Eintrag gibt es keine Antwort (`None`) - das ist ausdruecklich
    etwas anderes als eine Antwort ohne brauchbare Ebene."""
    nearest = _nearest_per_level(entries, cell)
    if not nearest:
        return None
    matched = next((level for level in PLACE_LEVELS if level in nearest), None)
    return PlaceAnswer(
        neighbourhood=nearest["neighbourhood"][1] if "neighbourhood" in nearest else None,
        locality=nearest["locality"][1] if "locality" in nearest else None,
        region=nearest["region"][1] if "region" in nearest else None,
        country=nearest["country"][1] if "country" in nearest else None,
        matched_level=matched,
    )


# --- Der Durchgang ------------------------------------------------------------------------------
#
# Suchraster des Durchgangs: eine Zehntelgrad-Kachel, rund 11 km.
#
# ACHTUNG, DAS IST KEINE ZWEITE ORTSZELLE: Dieser Schluessel ist rein prozessintern, entsteht nur
# waehrend des einen Dateidurchgangs, wird NIE abgelegt und NIE abgesendet. Die Ortszelle - der
# Wert, der das System verlaesst - bleibt ausschliesslich `places.place_cell`.
#
# Ein Kranz aus ORTSZELLEN (rund 1,1 km) traegt hier nicht: der Mittelpunkt einer Stadt liegt
# regelmaessig mehrere Kilometer von dem Viertel entfernt, in dem fotografiert wurde. Ein zu enger
# Radius liesse den Ortsnamen dort systematisch ausfallen.
_SEARCH_BUCKET_DIGITS = 1

# Grobe Obergrenze je Treffer. Jenseits davon ist ein Eintrag kein Ortsname mehr, sondern der
# naechste Eintrag irgendwo - grosszuegig, weil der Mittelpunkt einer Grossstadt weit vom
# bereisten Rand liegen kann.
GEONAMES_MAX_DISTANCE_METERS = 25_000.0


def _search_bucket(lat: float, lon: float) -> tuple[float, float]:
    """Der prozessinterne Suchschluessel - siehe `_SEARCH_BUCKET_DIGITS`."""
    return (round(lat, _SEARCH_BUCKET_DIGITS), round(lon, _SEARCH_BUCKET_DIGITS))


def search_buckets_around(cell: Cell) -> tuple[tuple[float, float], ...]:
    """Die Kachel der Zelle und ihre acht Nachbarn - zusammen rund 11 bis 22 km im Umkreis."""
    lat, lon = cell
    step = 10.0**-_SEARCH_BUCKET_DIGITS
    return tuple(
        _search_bucket(lat + row * step, lon + column * step)
        for row in (-1, 0, 1)
        for column in (-1, 0, 1)
    )


def _open_text(path: Path) -> TextIO:
    """Der Auszug liegt gzip-gepackt; eine entpackte Datei daneben bleibt lesbar - so muss er zur
    Untersuchung nicht erst umkopiert werden."""
    if path.suffix == ".gz":
        return cast("TextIO", gzip.open(path, "rt", encoding="utf-8", errors="replace"))
    return path.open(encoding="utf-8", errors="replace")


class GeoNamesResolver:
    """Liest den Auszug in EINEM Durchgang und behaelt nur, was in der Naehe der gefragten Zellen
    liegt.

    Die Zellmenge kommt in den Konstruktor, weil ein Durchgang je Zelle nicht laeuft: der Auszug
    misst gepackt rund 69 MB, ein vollstaendiger Durchgang rund drei Sekunden - einmal je Lauf.
    Gefragt wird ausschliesslich ueber die TATSAECHLICH BESUCHTEN Zellen; dieser Auflöser erzeugt
    keine und rastert kein Rechteck ab."""

    def __init__(self, path: Path, cells: Iterable[Cell]) -> None:
        wanted: dict[Cell, list[GeoNamesEntry]] = {cell: [] for cell in cells}
        bucket_owners: dict[tuple[float, float], list[Cell]] = {}
        for cell in wanted:
            for bucket in search_buckets_around(cell):
                bucket_owners.setdefault(bucket, []).append(cell)
        if not path.is_file():
            # LAUT und ohne stillen Ersatzweg: ein fehlender Datensatz ist etwas anderes als ein
            # Datensatz ohne Treffer, und beide duerfen nicht gleich aussehen.
            raise PlaceDatasetError(
                f"Der Ortsdatensatz liegt nicht unter dem angegebenen Pfad ({DATASET_REASON_MISSING})."
            )
        with _open_text(path) as handle:
            for line in handle:
                entry = parse_geonames_line(line)
                if entry is None:
                    continue
                owners = bucket_owners.get(_search_bucket(entry.lat, entry.lon))
                if owners is None:
                    continue
                for owner in owners:
                    wanted[owner].append(entry)
        self._entries = wanted

    async def resolve(self, cell: Cell) -> PlaceAnswer | None:
        return geonames_answer(self._entries.get(cell, ()), cell)

    def match_distances(self, cell: Cell) -> dict[str, float]:
        """Je Ebene die Entfernung zum namengebenden Eintrag - NUR fuer das Messkommando (S4).

        Bewusst NICHT Teil des `PlaceResolver`-Protokolls: Der Lauf sieht diese Zahl nie, und ein
        kuenftiger Auflöser hinter demselben Protokoll muss sie nicht liefern. Wer sie braucht,
        baut sich seinen Auflöser ueber `build_geonames_resolver` und macht das damit sichtbar."""
        return geonames_match_distances(self._entries.get(cell, ()), cell)


# --- Die Pruefung vor jedem Gebrauch -------------------------------------------------------------


class DatasetReasons(NamedTuple):
    """Die drei Grund-Token EINES Auszugs - FESTE TOKEN, die nur im Log stehen und nirgends sonst.

    Zwei Auszuege fuehren je eigene: waeren sie dieselben, liesse sich „der
    Sehenswuerdigkeitsauszug fehlt" nicht von „der Ortsauszug fehlt" unterscheiden, und an genau
    dieser Unterscheidung haengt die fail-open-Ausfallrichtung (S3, S4)."""

    missing: str
    hash_missing: str
    hash_mismatch: str


DATASET_REASON_MISSING = "ortsdatensatz-fehlt"
DATASET_REASON_HASH_MISSING = "ortsdatensatz-hash-fehlt"
DATASET_REASON_HASH_MISMATCH = "ortsdatensatz-hash-abweichung"

DATASET_REASONS = DatasetReasons(
    missing=DATASET_REASON_MISSING,
    hash_missing=DATASET_REASON_HASH_MISSING,
    hash_mismatch=DATASET_REASON_HASH_MISMATCH,
)

LANDMARK_DATASET_REASON_MISSING = "sehenswuerdigkeitsauszug-fehlt"
LANDMARK_DATASET_REASON_HASH_MISSING = "sehenswuerdigkeitsauszug-hash-fehlt"
LANDMARK_DATASET_REASON_HASH_MISMATCH = "sehenswuerdigkeitsauszug-hash-abweichung"

LANDMARK_DATASET_REASONS = DatasetReasons(
    missing=LANDMARK_DATASET_REASON_MISSING,
    hash_missing=LANDMARK_DATASET_REASON_HASH_MISSING,
    hash_mismatch=LANDMARK_DATASET_REASON_HASH_MISMATCH,
)

_HASH_READ_CHUNK_BYTES = 1024 * 1024


def dataset_hash_path(path: Path) -> Path:
    """Die Hash-Datei NEBEN dem Auszug - eine Stelle, die beide Seiten (Bezug und Pruefung)
    benutzen, damit der Name nicht zweimal entschieden wird."""
    return path.with_name(path.name + ".sha256")


def landmark_dataset_path(place_path: Path) -> Path:
    """Der Pfad des zweiten Auszugs - ABGELEITET aus dem des Ortsauszugs, nie eingestellt.

    Keine neue Betriebseinstellung (Spec 0529): Die zweite Datei liegt als Geschwisterdatei neben
    `PLACE_DATASET_PATH`, Muster `dataset_hash_path`. Damit kann sie nicht an einen anderen Ort
    zeigen als der erste Auszug, und der eine Bezug kennt beide Ziele."""
    return place_path.with_name("sehenswuerdigkeits-auszug.txt.gz")


def sha256_of(path: Path) -> str:
    """Der SHA256 einer Datei, stueckweise gelesen - der Auszug misst 69 MB, der zweite 204 MB."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_READ_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_problem(path: Path, reasons: DatasetReasons = DATASET_REASONS) -> str | None:
    """Das Grund-Token, aus dem KEIN Leser entsteht, oder `None` bei benutzbarem Auszug.

    `reasons` unterscheidet die beiden Auszuege (S3); geprueft wird jeweils der Auszug SELBST, also
    genau die Datei, die gelesen wird. Ein Auszug ohne seine Hash-Datei ist nicht pruefbar, und
    "nicht pruefbar" ist hier dasselbe wie "nicht verwendbar" - sonst haette ein Loeschen der
    Hash-Datei die Pruefung abgeschaltet."""
    if not path.is_file():
        return reasons.missing
    hash_file = dataset_hash_path(path)
    if not hash_file.is_file():
        return reasons.hash_missing
    expected = hash_file.read_text(encoding="utf-8").strip().split()
    if not expected or expected[0] != sha256_of(path):
        return reasons.hash_mismatch
    return None


def build_geonames_resolver(
    cells: Iterable[Cell], path: Path | None = None
) -> GeoNamesResolver | None:
    """DER EINE BAUWEG samt seiner Pruefung, in der konkreten Sicht.

    `None` heisst "es wird keiner gebaut" und ist ein ARBEITSFAEHIGER Zustand: die Events behalten
    Nummer und Zeitspanne, der Lauf laeuft durch. Es gibt ausdruecklich keinen Ersatzweg - kein
    zweiter Datensatz, kein Dienst, keine Vermutung.

    Der Pfad kommt aus einer Betriebseinstellung mit Vorgabe auf dem Volume, nie aus Datenbank
    oder Request.

    Diese Sicht braucht nur, wer `match_distances` braucht - also allein das Messkommando. Der
    Lauf geht ueber `build_place_resolver` und sieht die Entfernung dadurch gar nicht erst (S4).
    Die Hash-Pruefung steht hier und damit an genau EINER Stelle: Ein zweiter Bauweg waere der
    stille Weg an ihr vorbei."""
    dataset = Path(settings.place_dataset_path) if path is None else path
    problem = dataset_problem(dataset)
    if problem is not None:
        logger.error(
            "Ortsauflösung ausgesetzt: der Ortsdatensatz ist nicht verwendbar (%s). Events "
            "behalten Nummer und Zeitspanne; 'python -m photosort.place_dataset' erzeugt ihn neu.",
            problem,
        )
        return None
    return GeoNamesResolver(dataset, cells)


def build_place_resolver(cells: Iterable[Cell], path: Path | None = None) -> PlaceResolver | None:
    """Der Auflöser des Produktivpfads hinter dem Protokoll - der Weg des Laufs."""
    return build_geonames_resolver(cells, path)


def build_landmark_gazetteer(
    names: Iterable[str], path: Path | None = None
) -> LandmarkGazetteer | None:
    """Der Gazetteer des Produktivpfads - der EINE Bauweg samt seiner Pruefung, oder `None`.

    S3: Ohne offene Namen wird gar nichts gebaut; sonst gilt dieselbe Pruefung wie beim Ortsauszug
    ueber das parametrisierte `dataset_problem`, mit EIGENEN Grund-Token. `path` dient dem Test;
    im Betrieb ist es der aus `PLACE_DATASET_PATH` abgeleitete Geschwisterpfad - nie ein Wert aus
    Datenbank oder Request.

    S4 (fail-open): Fehlt der Auszug, wird KEIN Name verworfen, der Lauf bleibt `SUCCESS`. Die
    Alternative waere ein Betriebszustand, in dem ein einzelner fehlender Auszug ALLE
    Sehenswuerdigkeitsnamen eines Laufs auf einmal entfernte."""
    wanted = tuple(names)
    if not wanted:
        return None
    dataset = (
        landmark_dataset_path(Path(settings.place_dataset_path)) if path is None else Path(path)
    )
    problem = dataset_problem(dataset, LANDMARK_DATASET_REASONS)
    if problem is not None:
        logger.error(
            "Sehenswürdigkeitsprüfung ausgesetzt: der Sehenswürdigkeitsauszug ist nicht verwendbar "
            "(%s). Kein Name wird verworfen; 'python -m photosort.place_dataset' erzeugt ihn neu.",
            problem,
        )
        return None
    return LandmarkGazetteer(dataset, wanted)
