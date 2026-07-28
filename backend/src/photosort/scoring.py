from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

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

_LAPLACE_KERNEL = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)

# dHash-Rastergroesse: 9x8 Graustufen-Pixel liefern 8x8=64 paarweise Helligkeitsvergleiche -> 64 Bit.
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


def local_quality_score(sharpness: float, exposure: float) -> float:
    """Dokumentierte Formel aus Schaerfe+Belichtung (Akzeptanzkriterium der Spec): belohnt hohe
    Schaerfe, bestraft proportional zum Anteil geclippter Pixel. Bewusst simpel (kein weiteres
    Normalisierungsmodell fuer die unbeschraenkte Laplace-Varianz-Skala) - ausreichend, um
    innerhalb eines Clusters die relative Reihenfolge sinnvoll abzubilden; Phase A spricht ohnehin
    keine positive Empfehlung anhand dieses Werts aus (siehe ADR 0006)."""
    return sharpness * (1.0 - exposure)


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


@dataclass(frozen=True)
class TimeClusterCandidate:
    photo_id: int
    taken_at: datetime


def assign_time_clusters(
    candidates: list[TimeClusterCandidate], gap: timedelta = TIME_CLUSTER_GAP
) -> dict[int, str]:
    """Reine Zeitfenster-Clusterbildung (technische Detailentscheidung, siehe Architektur-
    Abschnitt der Spec): sortiert nach taken_at, beginnt ein neues Cluster, sobald die Luecke zum
    vorherigen Foto den Schwellwert ueberschreitet. cluster_key wird pro Lauf neu vergeben, ist
    also nur innerhalb EINES score_project-Laufs stabil/vergleichbar."""
    ordered = sorted(candidates, key=lambda c: (c.taken_at, c.photo_id))

    result: dict[int, str] = {}
    cluster_index = -1
    previous_taken_at: datetime | None = None
    for candidate in ordered:
        if previous_taken_at is None or candidate.taken_at - previous_taken_at > gap:
            cluster_index += 1
        result[candidate.photo_id] = f"cluster-{cluster_index}"
        previous_taken_at = candidate.taken_at
    return result
