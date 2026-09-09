from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import atan2, cos, radians, sin, sqrt

from PIL import Image, ImageFilter, ImageStat

# Schwellenwerte fuer Phase A (specs/features/0003-automatic-best-photo-selection.md,
# decisions/0006-local-scoring-datamodel.md). Bewusst als benannte Konstanten statt Magic Numbers,
# aber NICHT gegen echte Kamerafotos kalibriert (kein Korpus im Repo, siehe Teststrategie-Abschnitt
# der Spec) - nur die Logik "Wert unter/ueber Schwelle -> erwartetes Verhalten" ist getestet.
# Tatsaechliche Kalibrierung bleibt manueller Smoke-Test mit echten Projektfotos vor dem Merge.

# Laplace-Kernel-Varianz unterhalb dieses Werts gilt als "zu unscharf fuer eine Empfehlung".
# Ein 64x64-Schachbrettmuster (staerkster realistischer Kantenkontrast) liegt weit darueber,
# eine komplett flaeche Farbe bei exakt 0 - der Wert liegt bewusst niedrig im Bereich dazwischen,
# um nur eindeutig unscharfe Aufnahmen (starkes Verwackeln/Fehlfokus) zu erfassen.
SHARPNESS_REJECT_THRESHOLD = 15.0

# Hamming-Distanz (von 64 moeglichen Bits) unterhalb/gleich der zwei dHashes als "nahezu
# identisch" gelten - Standardempfehlung fuer 64-Bit-dHash-Duplikaterkennung liegt bei ca. 10% der
# Bitlaenge; 6 von 64 Bit ist etwas strenger, um Fehlalarme zwischen aehnlichen, aber
# eigenstaendigen Motiven zu vermeiden (Burst-Serien sind praktisch bitidentisch bis auf minimales
# Rauschen/Kompressionsartefakte).
DUPLICATE_HAMMING_THRESHOLD = 6

# Zeitliche Luecke, ab der ein neues Zeitfenster-Cluster beginnt (cluster_key) - trennt
# unterschiedliche Aufnahme-Anlaesse/Situationen innerhalb eines Projekts. Reine Zeitfenster-Bildung
# ohne visuelle Aehnlichkeit (technische Detailentscheidung, siehe Architektur-Abschnitt der Spec).
TIME_CLUSTER_GAP = timedelta(hours=1)

# Haversine-Distanz, ab der ein neues Cluster beginnt - gleichrangig neben TIME_CLUSTER_GAP
# (specs/features/0051-gps-landmark-cluster-bildung.md, ADR 0029 Punkt 5, ADR 0072 Entscheidung 4).
# Dokumentierte, UNKALIBRIERTE Modulkonstante wie TIME_CLUSTER_GAP/SHARPNESS_REJECT_THRESHOLD -
# bewusst kein Settings-/Env-Wert (die sind im Projekt Infrastruktur-Parametern vorbehalten).
#
# 500 statt der 2000 aus dem unverbindlichen Vorschlag in ADR 0029: der ausloesende Fall der Spec
# ist "zwei Sehenswuerdigkeiten kurz hintereinander", und die liegen innerstaedtisch typischerweise
# einige hundert Meter auseinander (Eiffelturm <-> Trocadero ca. 700 m) - 2000 m haetten genau den
# benannten Fall nicht getrennt. 500 m liegt zugleich sicher oberhalb der Streuung eines einzelnen
# Ortsbesuchs (Umherlaufen plus GPS-Ungenauigkeit, Groessenordnung 100-300 m). Bewusst in Kauf
# genommene Kehrseite: Aufnahmen aus einem fahrenden Fahrzeug erzeugen viele kleine Cluster.
#
# ACHTUNG: die Schwelle begrenzt den SCHRITT zwischen zwei aufeinanderfolgenden Fotos, nicht den
# DURCHMESSER eines Clusters - ein Spaziergang in 400-m-Schritten teilt nie und kann Kilometer
# ueberspannen. Deshalb traegt api/photos.py::PhotoLocationOut ein `source`-Feld: eine hergeleitete
# Koordinate ist eine Schaetzung, nie eine Messung.
GPS_CLUSTER_SPLIT_DISTANCE_METERS = 500.0

# Mittlerer Erdradius (IUGG) fuer die Haversine-Approximation. Fuer die hier relevante Praezision
# (Cluster-Sprung-Erkennung im Bereich von Metern bis Kilometern) ausreichend - keine neue
# Abhaengigkeit fuer eine einzelne Distanzformel (ADR 0029 Punkt 4).
_EARTH_RADIUS_METERS = 6_371_008.8

_LAPLACE_KERNEL = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)

# dHash-Rastergroesse: 9x8 Graustufen-Pixel liefern 8x8=64 paarweise Helligkeitsvergleiche
# -> 64 Bit.
_DHASH_WIDTH = 9
_DHASH_HEIGHT = 8


def compute_sharpness(image: Image.Image) -> float:
    """Schaerfe als Varianz eines 3x3-Laplace-Kernels (klassische "Blur-Detection ohne OpenCV",
    liefert dieselbe Kennzahl wie cv2.Laplacian(...).var() - decisions/0006)."""
    grayscale = image.convert("L")
    edges = grayscale.filter(_LAPLACE_KERNEL)
    variance = ImageStat.Stat(edges).var[0]
    return float(variance)


def compute_exposure(image: Image.Image) -> float:
    """Anteil ueber-/unterbelichteter (vollstaendig geclippter) Pixel aus dem Helligkeits-
    Histogramm: 0.0 = kein geclippter Pixel, 1.0 = vollstaendig ueber- oder unterbelichtet."""
    grayscale = image.convert("L")
    histogram = grayscale.histogram()
    total = sum(histogram)
    if total == 0:
        return 0.0
    clipped = histogram[0] + histogram[-1]
    return clipped / total


def compute_dhash(image: Image.Image) -> str:
    """Difference Hash (dHash): Graustufen-Resize auf 9x8 Pixel + bitweiser Vergleich
    benachbarter Pixel -> 64-Bit-Hash, hex-codiert (decisions/0006). Strukturell (nicht
    farb-)sensitiv, ausreichend fuer Burst-/Duplikaterkennung nahezu identischer Aufnahmen."""
    grayscale = image.convert("L").resize(
        (_DHASH_WIDTH, _DHASH_HEIGHT), Image.Resampling.LANCZOS
    )
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
    Gleichstand niedrigere photo_id - Akzeptanzkriterium der Spec).

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
    """Grosskreisdistanz zweier Koordinaten in METERN (Haversine, Stdlib-`math`, ADR 0029 Punkt 4).

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
    """Ein Foto der Phase-A-Clusterbildung (specs/features/0051-gps-landmark-cluster-bildung.md).

    Hiess bis Spec 0051 `TimeClusterCandidate`; die Umbenennung ist Teil derselben Erweiterung
    (dieselbe Funktion um ein zweites Signal ergaenzt, kein Parallelmuster neben der alten).

    `gps_lat`/`gps_lon` haben den Vorgabewert `None` - "kein Ort" ist der Normalfall, kein
    Sonderfall (ADR 0029, Backward Compatibility): ein Projekt ganz ohne Koordinaten laeuft ueber
    denselben Code und liefert exakt das bisherige Zeitfensterverhalten."""

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
    """Phase-A-Clusterbildung aus Zeit UND Ort in EINEM sortierten Durchlauf
    (specs/features/0051-gps-landmark-cluster-bildung.md, ADR 0029 Punkt 1, ADR 0072
    Entscheidung 5). Bis Spec 0051 hiess diese Funktion `assign_time_clusters`.

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

        time_boundary = (
            previous_taken_at is None or candidate.taken_at - previous_taken_at > gap
        )
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
