from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import atan2, cos, radians, sin, sqrt

from PIL import Image, ImageFilter, ImageStat

# Schwellenwerte für Phase A. Benannte Konstanten statt Magic Numbers, aber NICHT gegen echte
# Kamerafotos kalibriert (kein Korpus im Repo) - nur die Logik "Wert unter/über Schwelle ->
# erwartetes Verhalten" ist getestet. Tatsaechliche Kalibrierung bleibt manueller Smoke-Test mit
# echten Projektfotos vor dem Merge.

# Laplace-Kernel-Varianz unterhalb dieses Werts gilt als "zu unscharf fuer eine Empfehlung". Der
# Wert liegt bewusst niedrig: erfasst werden soll nur eindeutiges Verwackeln/Fehlfokus.
SHARPNESS_REJECT_THRESHOLD = 15.0

# Hamming-Distanz (von 64 moeglichen Bits), unterhalb/gleich derer zwei dHashes als "nahezu
# identisch" gelten. 6 von 64 Bit ist strenger als die uebliche 10-%-Faustregel, um Fehlalarme
# zwischen aehnlichen, aber eigenstaendigen Motiven zu vermeiden.
DUPLICATE_HAMMING_THRESHOLD = 6

# Zeitliche Luecke, ab der ein neues Zeitfenster-Cluster beginnt (cluster_key) - trennt
# unterschiedliche Aufnahme-Anlaesse/Situationen innerhalb eines Projekts. Reine
# Zeitfenster-Bildung ohne visuelle Ähnlichkeit.
TIME_CLUSTER_GAP = timedelta(hours=1)

# Haversine-Distanz, ab der ein neues Cluster beginnt - gleichrangig neben TIME_CLUSTER_GAP.
# Dokumentierte, UNKALIBRIERTE Modulkonstante wie TIME_CLUSTER_GAP/SHARPNESS_REJECT_THRESHOLD,
# bewusst kein Settings-/Env-Wert (die sind im Projekt Infrastruktur-Parametern vorbehalten).
#
# 500 m liegt sicher oberhalb der Streuung eines einzelnen Ortsbesuchs (Umherlaufen plus
# GPS-Ungenauigkeit, Groessenordnung 100-300 m) und unterhalb des Abstands zweier
# innerstaedtischer Sehenswuerdigkeiten. Bewusst in Kauf genommene Kehrseite: Aufnahmen aus einem
# fahrenden Fahrzeug erzeugen viele kleine Cluster.
#
# ACHTUNG: die Schwelle begrenzt den SCHRITT zwischen zwei aufeinanderfolgenden Fotos, nicht den
# DURCHMESSER eines Clusters - ein Spaziergang in 400-m-Schritten teilt nie und kann Kilometer
# ueberspannen. Deshalb traegt api/photos.py::PhotoLocationOut ein `source`-Feld: eine hergeleitete
# Koordinate ist eine Schaetzung, nie eine Messung.
GPS_CLUSTER_SPLIT_DISTANCE_METERS = 500.0

# Mittlerer Erdradius (IUGG) fuer die Haversine-Approximation. Fuer die hier relevante Praezision
# (Cluster-Sprung-Erkennung im Bereich von Metern bis Kilometern) ausreichend - keine neue
# Abhängigkeit für eine einzelne Distanzformel.
_EARTH_RADIUS_METERS = 6_371_008.8

_LAPLACE_KERNEL = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)

# dHash-Rastergroesse: 9x8 Graustufen-Pixel liefern 8x8=64 paarweise Helligkeitsvergleiche
# -> 64 Bit.
_DHASH_WIDTH = 9
_DHASH_HEIGHT = 8


def compute_sharpness(image: Image.Image) -> float:
    """Schaerfe als Varianz eines 3x3-Laplace-Kernels (klassische "Blur-Detection ohne OpenCV",
    liefert dieselbe Kennzahl wie cv2.Laplacian(...).var())."""
    grayscale = image.convert("L")
    edges = grayscale.filter(_LAPLACE_KERNEL)
    variance = ImageStat.Stat(edges).var[0]
    return float(variance)


def compute_exposure(image: Image.Image) -> float:
    """Anteil ueber-/unterbelichteter (vollstaendig geclippter) Pixel aus dem
    Helligkeits-Histogramm: 0.0 = kein geclippter Pixel, 1.0 = vollstaendig ueber- oder
    unterbelichtet."""
    grayscale = image.convert("L")
    histogram = grayscale.histogram()
    total = sum(histogram)
    if total == 0:
        return 0.0
    clipped = histogram[0] + histogram[-1]
    return clipped / total


def compute_dhash(image: Image.Image) -> str:
    """Difference Hash (dHash): Graustufen-Resize auf 9x8 Pixel + bitweiser Vergleich benachbarter
    Pixel -> 64-Bit-Hash, hex-codiert. Strukturell (nicht farb-)sensitiv, ausreichend fuer
    Burst-/Duplikaterkennung nahezu identischer Aufnahmen."""
    grayscale = image.convert("L").resize((_DHASH_WIDTH, _DHASH_HEIGHT), Image.Resampling.LANCZOS)
    pixels = list(grayscale.getdata())

    value = 0
    for row in range(_DHASH_HEIGHT):
        row_pixels = pixels[row * _DHASH_WIDTH : (row + 1) * _DHASH_WIDTH]
        for col in range(_DHASH_WIDTH - 1):
            bit = 1 if row_pixels[col] > row_pixels[col + 1] else 0
            value = (value << 1) | bit
    return f"{value:016x}"


def hamming_distance(hash_a: str, hash_b: str) -> int:
    return bin(int(hash_a, 16) ^ int(hash_b, 16)).count("1")


@dataclass(frozen=True)
class DuplicateCandidate:
    photo_id: int
    phash: str
    sharpness: float


def assign_duplicate_clusters(
    candidates: list[DuplicateCandidate], threshold: int = DUPLICATE_HAMMING_THRESHOLD
) -> dict[int, int]:
    """Gruppiert Fotos anhand der Hamming-Distanz ihrer dHashes (Union-Find, transitiv) und
    bestimmt je Cluster mit mehr als einem Mitglied den Gewinner (hoechste sharpness, bei
    Gleichstand niedrigere photo_id).

    Rueckgabe: photo_id -> duplicate_of, NUR fuer die Verlierer eines Clusters. Fotos ohne
    Duplikat (Cluster-Groesse 1) oder der Cluster-Gewinner selbst tauchen im Ergebnis nicht auf.
    """
    parent: dict[int, int] = {c.photo_id: c.photo_id for c in candidates}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_a] = root_b

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            if hamming_distance(candidates[i].phash, candidates[j].phash) <= threshold:
                union(candidates[i].photo_id, candidates[j].photo_id)

    groups: dict[int, list[DuplicateCandidate]] = {}
    for candidate in candidates:
        groups.setdefault(find(candidate.photo_id), []).append(candidate)

    result: dict[int, int] = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        winner = min(members, key=lambda c: (-c.sharpness, c.photo_id))
        for member in members:
            if member.photo_id != winner.photo_id:
                result[member.photo_id] = winner.photo_id
    return result


def _haversine_meters(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Großkreisdistanz zweier Koordinaten in METERN (Haversine, Stdlib-`math`).

    Die Einheit ist Teil des Vertrags und nicht bloss Konvention: bei einer Trennschwelle von
    500 m ist ein Meter/Kilometer-Dreher die Grenze zwischen "trennt nie" und "trennt immer", und
    kein abstrakter Schwellwerttest kann ihn finden (er besteht bei jeder Einheit). Deshalb prueft
    test_scoring.py ihn gegen eine bekannte Referenzstrecke: 1 Grad Breite ist rund 111 195 m.

    Haversine statt einer naiven Koordinatendifferenz aus zwei Gruenden, die beide real
    vorkommen: die `cos(lat)`-Daempfung (dieselbe Laengendifferenz ist in Polnaehe eine deutlich
    kuerzere Strecke als am Aequator) und der Wraparound am 180. Meridian (179.9 nach -179.9 sind
    0,2 Grad, nicht 359,8)."""
    lat_a_rad = radians(lat_a)
    lat_b_rad = radians(lat_b)
    delta_lat = lat_b_rad - lat_a_rad
    delta_lon = radians(lon_b - lon_a)
    a = sin(delta_lat / 2) ** 2 + cos(lat_a_rad) * cos(lat_b_rad) * sin(delta_lon / 2) ** 2
    return 2 * _EARTH_RADIUS_METERS * atan2(sqrt(a), sqrt(1 - a))


@dataclass(frozen=True)
class ClusterCandidate:
    """Ein Foto der Phase-A-Clusterbildung.

    `gps_lat`/`gps_lon` haben den Vorgabewert `None` - "kein Ort" ist der Normalfall, kein
    Sonderfall: ein Projekt ganz ohne Koordinaten läuft über denselben Code und liefert
    exakt das reine Zeitfensterverhalten."""

    photo_id: int
    taken_at: datetime
    gps_lat: float | None = None
    gps_lon: float | None = None


def _coordinate_of(candidate: ClusterCandidate) -> tuple[float, float] | None:
    """Die Koordinate eines Kandidaten - `None`, sobald auch nur eine Komponente fehlt.

    `extract_gps` liefert nie eine halbe Koordinate (Paar-Invariante), aber diese Funktion ist der
    einzige Ort, an dem sich das Verlassen darauf raechen wuerde: ein einzelner gesetzter Wert
    ergaebe hier eine Position auf dem Nullmeridian bzw. dem Aequator und risse Cluster auf."""
    if candidate.gps_lat is None or candidate.gps_lon is None:
        return None
    return candidate.gps_lat, candidate.gps_lon


def assign_clusters(
    candidates: list[ClusterCandidate],
    gap: timedelta = TIME_CLUSTER_GAP,
    split_distance_meters: float = GPS_CLUSTER_SPLIT_DISTANCE_METERS,
) -> dict[int, str]:
    """Phase-A-Clusterbildung aus Zeit UND Ort in EINEM sortierten Durchlauf.

    Ein neues Cluster beginnt, wenn die Zeitluecke `gap` ueberschritten wird ODER die
    Haversine-Distanz zum letzten Foto MIT Koordinate im laufenden Cluster
    `split_distance_meters` ueberschreitet. Beide Bedingungen sind GLEICHRANGIG und stehen in
    derselben Pruefung - es gibt keine "Reihenfolge" von Zeit- und Ortstrennung, nur eine
    Cluster-Grenze. `cluster_key` wird pro Lauf neu vergeben, ist also nur innerhalb EINES
    score_project-Laufs stabil/vergleichbar.

    Zwei Feinheiten, die unabhaengig voneinander brechen und deshalb getrennt getestet sind:

    1. **Bezug ist das letzte koordinatentragende Foto des LAUFENDEN Clusters**, nicht der
       unmittelbare zeitliche Vorgaenger. Sonst unterdrueckte ein einziges Foto ohne Koordinate
       zwischen zwei weit auseinanderliegenden Aufnahmen die Trennung vollstaendig. Das Kriterium
       "ein Foto ohne eigene Ortsangabe loest nie selbst eine Trennung aus" bleibt gewahrt: die
       Trennung entsteht am naechsten Foto, das selbst eine Koordinate traegt.
    2. **Die Bezugskoordinate wird an JEDER Cluster-Grenze zurueckgesetzt** - auch an einer rein
       zeitlichen. Ohne das wuerde das erste koordinatentragende Foto eines neuen Clusters gegen
       eines aus dem VORHERIGEN verglichen und ein zweites Mal getrennt; der Fehler ist
       unsichtbar, solange nur eine Grenze im Spiel ist.

    Kumulative Drift ist bewusst KEIN Split: verglichen wird paarweise, nicht gegen Cluster-Anfang
    oder Schwerpunkt - eine Kette aus 300-m-Schritten bleibt ein Cluster, auch ueber 3 km."""
    ordered = sorted(candidates, key=lambda c: (c.taken_at, c.photo_id))

    result: dict[int, str] = {}
    cluster_index = -1
    previous_taken_at: datetime | None = None
    reference_coordinate: tuple[float, float] | None = None
    for candidate in ordered:
        coordinate = _coordinate_of(candidate)

        time_boundary = previous_taken_at is None or candidate.taken_at - previous_taken_at > gap
        distance_boundary = (
            coordinate is not None
            and reference_coordinate is not None
            and _haversine_meters(*reference_coordinate, *coordinate) > split_distance_meters
        )

        if time_boundary or distance_boundary:
            cluster_index += 1
            # Ruecksetzung an der Grenze: der Bezug des neuen Clusters ist die Koordinate DIESES
            # Fotos (bzw. `None`, wenn es keine traegt) - nie eine aus dem vorherigen Cluster.
            reference_coordinate = coordinate
        elif coordinate is not None:
            reference_coordinate = coordinate

        result[candidate.photo_id] = f"cluster-{cluster_index}"
        previous_taken_at = candidate.taken_at
    return result


def refine_clusters_by_landmark(
    base_cluster_key_by_photo: Mapping[int, str],
    landmark_name_by_photo: Mapping[int, str | None],
) -> dict[int, str]:
    """Phase-2-Verfeinerung der Cluster anhand erkannter Sehenswürdigkeiten.

    REIN und DB-FREI: die Namen kommen als einfaches `dict` herein, die Funktion kennt ihre
    Datenherkunft nicht. Das ist Absicht - so bleibt die Schluesselvergabe ohne Cloud-Fixture
    pruefbar, und der Aufrufer entscheidet, ob er sie aus `photo_landmark_detections` oder aus
    einer Testtabelle speist.

    Enthaelt ein Basis-Cluster ZWEI ODER MEHR verschiedene, nicht-leere Namen, bekommt jeder Name
    ein eigenes Cluster: `cluster-3-1`, `cluster-3-2`, ... - 1-basiert, in ALPHABETISCHER
    Reihenfolge der Namen vergeben (Python-Standardsortierung, also Codepunkt-Reihenfolge; keine
    locale-abhaengige Kollation, die die Schluessel zwischen zwei Laeufen umnummerieren koennte).
    Fotos OHNE Namen behalten den unveraenderten Basis-Schluessel - ein Cluster mit zwei Namen und
    namenlosen Fotos ergibt also genau DREI Schluessel. Bei genau einem Namen findet KEINE
    Verfeinerung statt (sonst waeren `cluster-3` und `cluster-3-1` beide belegt, ohne jeden
    Nutzen).

    SICHERHEIT - kein Name im Schlüssel: `cluster_key` ist ein Partitionsschlüssel, der als
    Query-Parameter an `GET /projects/{id}/curation-candidates` zurueckwandert und im Frontend als
    React-Key dient - freier, extern erzeugter LLM-Text hat dort nichts zu suchen.

    Exakter Zeichenkettenvergleich, KEIN Fuzzy-Matching (bewusste Vereinfachung): zwei
    Schreibweisen-Varianten desselben Orts splitten.

    Das Ergebnis geht ausschliesslich nach `PhotoRanking.cluster_key`; `PhotoScore.cluster_key`
    wird NIE mutiert (Ownership-Grenze). Die Divergenz beider Felder ist gewollt.

    SICHERHEIT - OBERE SCHRANKE der Wirkung, Muss-Kriterium für jede steuernde Verwendung eines
    Fremdwerts: der Name stammt aus einem Vision-Modell und steuert hier Kontrollfluss.
    Die Zahl der Teil-Cluster eines Basis-Clusters ist durch die Zahl der Fotos IN DIESEM Cluster
    absolut begrenzt (Extremfall: jedes Foto ein eigenes Cluster) - der Kuratierungsmodus liefert
    dann höchstens den vollen Bildvorrat des Projekts aus, also genau die Antwortgröße, die
    `GET /projects/{id}/curation-candidates` ohnehin als zulässig gesetzt hat."""
    names_by_cluster: dict[str, set[str]] = {}
    for photo_id, base_key in base_cluster_key_by_photo.items():
        name = (landmark_name_by_photo.get(photo_id) or "").strip()
        if name:
            names_by_cluster.setdefault(base_key, set()).add(name)

    # Nur Cluster mit MEHR ALS EINEM verschiedenen Namen werden ueberhaupt aufgeteilt.
    index_by_cluster_and_name = {
        (base_key, name): index
        for base_key, names in names_by_cluster.items()
        if len(names) > 1
        for index, name in enumerate(sorted(names), start=1)
    }

    result: dict[int, str] = {}
    for photo_id, base_key in base_cluster_key_by_photo.items():
        name = (landmark_name_by_photo.get(photo_id) or "").strip()
        index = index_by_cluster_and_name.get((base_key, name))
        result[photo_id] = base_key if index is None else f"{base_key}-{index}"
    return result
