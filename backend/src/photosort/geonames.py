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
"""

from __future__ import annotations

import gzip
import hashlib
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast

from photosort.config import settings
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
    try:
        lat = float(fields[GEONAMES_LAT_FIELD])
        lon = float(fields[GEONAMES_LON_FIELD])
    except ValueError:
        return None
    return GeoNamesEntry(
        name=name,
        lat=lat,
        lon=lon,
        feature_class=fields[GEONAMES_FEATURE_CLASS_FIELD],
        feature_code=fields[GEONAMES_FEATURE_CODE_FIELD],
    )


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


def geonames_answer(entries: Iterable[GeoNamesEntry], cell: Cell) -> PlaceAnswer | None:
    """Die Auskunft zu einer Zelle aus den Eintraegen in ihrer Nachbarschaft.

    Je Ebene gewinnt der NAECHSTGELEGENE Eintrag. `matched_level` ist die FEINSTE getroffene
    Ebene; ohne jeden verwertbaren Eintrag gibt es keine Antwort (`None`) - das ist ausdruecklich
    etwas anderes als eine Antwort ohne brauchbare Ebene."""
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


# --- Die Pruefung vor jedem Gebrauch -------------------------------------------------------------

# Die Gruende, aus denen kein Auflöser entsteht - FESTE TOKEN. Sie stehen im Log und nirgends
# sonst; ein Pfad, eine Koordinate oder ein Ortsname geraet darueber nie in eine Logzeile (S11).
DATASET_REASON_MISSING = "ortsdatensatz-fehlt"
DATASET_REASON_HASH_MISSING = "ortsdatensatz-hash-fehlt"
DATASET_REASON_HASH_MISMATCH = "ortsdatensatz-hash-abweichung"

_HASH_READ_CHUNK_BYTES = 1024 * 1024


def dataset_hash_path(path: Path) -> Path:
    """Die Hash-Datei NEBEN dem Auszug - eine Stelle, die beide Seiten (Bezug und Pruefung)
    benutzen, damit der Name nicht zweimal entschieden wird."""
    return path.with_name(path.name + ".sha256")


def sha256_of(path: Path) -> str:
    """Der SHA256 einer Datei, stueckweise gelesen - der Auszug misst rund 69 MB."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_READ_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_problem(path: Path) -> str | None:
    """Das Grund-Token, aus dem KEIN Auflöser entsteht, oder `None` bei benutzbarem Auszug.

    Geprueft wird der Auszug SELBST, also genau die Datei, die gelesen wird. Ein Auszug ohne seine
    Hash-Datei ist nicht pruefbar, und "nicht pruefbar" ist hier dasselbe wie "nicht
    verwendbar" - sonst haette ein Loeschen der Hash-Datei die Pruefung abgeschaltet."""
    if not path.is_file():
        return DATASET_REASON_MISSING
    hash_file = dataset_hash_path(path)
    if not hash_file.is_file():
        return DATASET_REASON_HASH_MISSING
    expected = hash_file.read_text(encoding="utf-8").strip().split()
    if not expected or expected[0] != sha256_of(path):
        return DATASET_REASON_HASH_MISMATCH
    return None


def build_place_resolver(cells: Iterable[Cell], path: Path | None = None) -> PlaceResolver | None:
    """Der Auflöser des Produktivpfads, oder `None`.

    `None` heisst "es wird keiner gebaut" und ist ein ARBEITSFAEHIGER Zustand: die Events behalten
    Nummer und Zeitspanne, der Lauf laeuft durch. Es gibt ausdruecklich keinen Ersatzweg - kein
    zweiter Datensatz, kein Dienst, keine Vermutung.

    Der Pfad kommt aus einer Betriebseinstellung mit Vorgabe auf dem Volume, nie aus Datenbank
    oder Request."""
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
