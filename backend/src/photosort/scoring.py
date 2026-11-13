from __future__ import annotations

from collections.abc import Sequence
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

# --- Duplikaterkennung: drei Stufen, alle Vergleiche inklusiv (ADR 0145) -----------------------
#
# Die Zahlen sind Startwerte; ein Kalibrierlauf bestaetigt oder verschiebt sie. Bewusst eigene
# Namen je Zahl und kein Settings-/Env-Wert: ein Laufzeithebel waere ein Schalter an der Grenze,
# die mitbestimmt, welche Fotos den Homeserver Richtung Cloud-Anbieter verlassen.

# Stufe 1: grober 64-Bit-dHash, grosszuegiges Netz. Ein Paar darueber ist kein Kandidat.
DUPLICATE_CANDIDATE_HAMMING = 12

# Bandzahl der exakten Kandidatensuche = Grenze + 1. Bei Hamming <= der Grenze stimmt nach dem
# Schubfachprinzip mindestens eines der disjunkten Baender exakt ueberein.
DUPLICATE_CANDIDATE_BANDS = 13

# "Aehnlich": grober und feiner dHash.
DUPLICATE_SIMILAR_HAMMING = 8
DUPLICATE_SIMILAR_FINE_HAMMING = 64

# Zeitfenster fuer "aehnlich", paarweise geprueft - nicht nur gegen den Gewinner.
DUPLICATE_SIMILAR_TIME_WINDOW = timedelta(minutes=15)

# "Praktisch identisch": feiner dHash UND z-normiertes 32x32-Grauwertgitter. Sind beide Gitter
# varianzfrei, entscheidet die rohe mittlere Grauwertdifferenz.
IDENTICAL_FINE_HAMMING = 16
IDENTICAL_GRID_MAD = 0.06
IDENTICAL_FLAT_MAD = 1.0

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

# Feiner dHash: 17x16 Graustufen-Pixel liefern 16x16=256 Vergleiche -> 256 Bit.
_FINE_DHASH_WIDTH = 17
_FINE_DHASH_HEIGHT = 16

# Grauwertgitter der dritten Stufe: 32x32 Pixel als `bytes`.
_GRID_WIDTH = 32
_GRID_HEIGHT = 32


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


def compute_fine_dhash(image: Image.Image) -> int:
    """Feiner Difference Hash: 17x16-Graustufenraster, 256 Bit als `int`.

    Dieselbe Form wie `compute_dhash`, nur feiner: er trennt eine neu gespeicherte Kopie von einer
    Serienaufnahme mit verschobenem Ausschnitt, die der grobe 64-Bit-Hash nicht trennt."""
    grayscale = image.convert("L").resize(
        (_FINE_DHASH_WIDTH, _FINE_DHASH_HEIGHT), Image.Resampling.LANCZOS
    )
    pixels = list(grayscale.getdata())

    value = 0
    for row in range(_FINE_DHASH_HEIGHT):
        row_pixels = pixels[row * _FINE_DHASH_WIDTH : (row + 1) * _FINE_DHASH_WIDTH]
        for col in range(_FINE_DHASH_WIDTH - 1):
            value = (value << 1) | (1 if row_pixels[col] > row_pixels[col + 1] else 0)
    return value


def compute_gray_grid(image: Image.Image) -> bytes:
    """Das Grauwertgitter der dritten Stufe: 32x32 Pixel, row-major, ein Byte je Pixel."""
    grayscale = image.convert("L").resize((_GRID_WIDTH, _GRID_HEIGHT), Image.Resampling.LANCZOS)
    return grayscale.tobytes()


@dataclass(frozen=True)
class PhotoFingerprint:
    """Die vollstaendige Duplikat-Signatur eines Fotos fuer EINEN Scoring-Lauf.

    Die feine Signatur und das Grauwertgitter leben nur im Speicher; persistiert wird weiterhin
    allein `PhotoScore.phash` (der grobe 64-Bit-dHash).

    `taken_at_trusted` ist falsch, wenn die Aufnahmezeit aus `last_modified` abgeleitet wurde.
    `taken_at` bleibt dann gefuellt (der Scan schreibt beide Spalten NOT NULL), wird fuer
    "aehnlich" aber nicht gelesen."""

    photo_id: int
    phash: int
    fine_phash: int
    gray_grid: bytes
    sharpness: float
    taken_at: datetime | None
    taken_at_trusted: bool
    # Aufloesung des Originals in Pixeln (`Photo.pixel_count`). `None` heisst "unbekannt" und ist
    # ein regulaerer Zustand: Der Fingerabdruck sortiert dann in Durchgang 1 zuletzt, und der Lauf
    # entscheidet die Gruppe nicht automatisch (ADR 0146 Punkt 1). Eine Schaetzung ist untersagt.
    pixel_count: int | None = None


def taken_at_is_trusted(taken_at_original: datetime, last_modified: datetime) -> bool:
    """Ob die Aufnahmezeit aus dem Bild stammt statt aus dem Dateidatum.

    Der Scan schreibt bei fehlendem EXIF `taken_at` UND `taken_at_original` aus `last_modified`;
    dann sind beide gleich. Exakte Ungleichheit, keine Toleranz: eine gerundete Gleichheit
    erklaerte eine abgeleitete Zeit zur Messung."""
    return taken_at_original != last_modified


def _band_ranges(total_bits: int, count: int) -> tuple[tuple[int, int], ...]:
    """`count` disjunkte Bit-Baender ueber `total_bits` Bits als `(offset, breite)`."""
    width, extra = divmod(total_bits, count)
    ranges: list[tuple[int, int]] = []
    offset = 0
    for index in range(count):
        size = width + (1 if index < extra else 0)
        ranges.append((offset, size))
        offset += size
    return tuple(ranges)


_BAND_RANGES = _band_ranges(64, DUPLICATE_CANDIDATE_BANDS)


def candidate_pairs(fingerprints: Sequence[PhotoFingerprint]) -> set[tuple[int, int]]:
    """Stufe 1: alle Kandidatenpaare als `(kleinere id, groessere id)` per Band-Bucketing.

    EXAKT, nicht ungefaehr: Bei Hamming `<= DUPLICATE_CANDIDATE_HAMMING` stimmt nach dem
    Schubfachprinzip mindestens eines der `DUPLICATE_CANDIDATE_BANDS` disjunkten Baender exakt
    ueberein, weil es mehr Baender als erlaubte Abweichungen gibt. Innerhalb eines Buckets wird
    die volle Distanz geprueft; ein Paar, das in mehreren Baendern liegt, steht einmal im
    Ergebnis. Ein Paar, das nur Stufe 1 besteht, ist damit noch KEIN Duplikat.

    Die `photo_id`s eines Laufs sind eindeutig (Datenbank-Primaerschluessel); ein doppeltes Foto
    waere kein Fehler dieser Funktion, sondern ein Fehler des Aufrufers."""
    buckets: dict[tuple[int, int], list[PhotoFingerprint]] = {}
    for fingerprint in fingerprints:
        for index, (offset, width) in enumerate(_BAND_RANGES):
            band = (fingerprint.phash >> offset) & ((1 << width) - 1)
            buckets.setdefault((index, band), []).append(fingerprint)

    pairs: set[tuple[int, int]] = set()
    for bucket in buckets.values():
        for position, left in enumerate(bucket):
            for right in bucket[position + 1 :]:
                distance = (left.phash ^ right.phash).bit_count()
                if distance <= DUPLICATE_CANDIDATE_HAMMING:
                    pairs.add(
                        (min(left.photo_id, right.photo_id), max(left.photo_id, right.photo_id))
                    )
    return pairs


def _moments(grid: bytes) -> tuple[float, float]:
    """Mittelwert und Standardabweichung eines Grauwertgitters."""
    mean = sum(grid) / len(grid)
    variance = sum((value - mean) ** 2 for value in grid) / len(grid)
    return mean, sqrt(variance)


def _raw_mad(left: bytes, right: bytes) -> float:
    return sum(abs(a - b) for a, b in zip(left, right, strict=True)) / len(left)


def _normalised_mad(
    left: bytes,
    left_mean: float,
    left_spread: float,
    right: bytes,
    right_mean: float,
    right_spread: float,
) -> float:
    """Mittlere absolute Differenz der z-Werte: entfernt globale Helligkeits- und
    Kontrastaenderungen, aber keine geometrische Verschiebung."""
    return sum(
        abs((a - left_mean) / left_spread - (b - right_mean) / right_spread)
        for a, b in zip(left, right, strict=True)
    ) / len(left)


def is_practically_identical(left: PhotoFingerprint, right: PhotoFingerprint) -> bool:
    """Stufe 2+3: `fine_hamming <= IDENTICAL_FINE_HAMMING` UND normalisierte Gitter-Differenz
    `<= IDENTICAL_GRID_MAD`.

    Sind BEIDE Gitter varianzfrei, entscheidet die rohe mittlere Grauwertdifferenz
    `<= IDENTICAL_FLAT_MAD`; ist nur eines varianzfrei, ist das Paar nicht identisch. Die Zeit
    spielt hier keine Rolle."""
    if (left.fine_phash ^ right.fine_phash).bit_count() > IDENTICAL_FINE_HAMMING:
        return False
    left_mean, left_spread = _moments(left.gray_grid)
    right_mean, right_spread = _moments(right.gray_grid)
    if left_spread == 0.0 and right_spread == 0.0:
        return _raw_mad(left.gray_grid, right.gray_grid) <= IDENTICAL_FLAT_MAD
    if left_spread == 0.0 or right_spread == 0.0:
        return False
    return (
        _normalised_mad(
            left.gray_grid, left_mean, left_spread, right.gray_grid, right_mean, right_spread
        )
        <= IDENTICAL_GRID_MAD
    )


def _within_window(left: PhotoFingerprint, right: PhotoFingerprint) -> bool:
    """Beide Zeiten verlaesslich und hoechstens ein Fenster auseinander (inklusive)."""
    if not (left.taken_at_trusted and right.taken_at_trusted):
        return False
    left_moment, right_moment = left.taken_at, right.taken_at
    if left_moment is None or right_moment is None:
        return False
    return abs(left_moment - right_moment) <= DUPLICATE_SIMILAR_TIME_WINDOW


def is_similar(left: PhotoFingerprint, right: PhotoFingerprint) -> bool:
    """Stufe 2+3 fuer "aehnlich": grober und feiner dHash innerhalb ihrer Grenzen UND beide
    Zeiten verlaesslich UND `|dt| <= DUPLICATE_SIMILAR_TIME_WINDOW`."""
    if not _within_window(left, right):
        return False
    if (left.phash ^ right.phash).bit_count() > DUPLICATE_SIMILAR_HAMMING:
        return False
    return (left.fine_phash ^ right.fine_phash).bit_count() <= DUPLICATE_SIMILAR_FINE_HAMMING


_IDENTICAL = "identical"
_SIMILAR = "similar"


def _edge_kind(left: PhotoFingerprint, right: PhotoFingerprint) -> str | None:
    """Erst "praktisch identisch", dann "aehnlich" - identische Paare sind zeitunabhaengig."""
    if is_practically_identical(left, right):
        return _IDENTICAL
    if is_similar(left, right):
        return _SIMILAR
    return None


@dataclass(frozen=True)
class DuplicateAssignment:
    """Das Ergebnis EINES Duplikat-Durchlaufs in zwei Aussagen.

    `duplicate_of` ist der Stern `verlierer -> gewinner` wie bisher. `identical_winners` nennt die
    Gewinner der Sterne, die Durchgang 1 ueber AUSSCHLIESSLICH identische Kanten gebaut hat -
    genau deren Verlierer darf der Lauf automatisch entscheiden (ADR 0146 Punkt 1/3). Die Menge
    ist bewusst nicht aus `duplicate_of` ableitbar: Ein aehnlicher Stern hat auch einen Gewinner,
    aber keinen automatischen Anspruch."""

    duplicate_of: dict[int, int]
    identical_winners: frozenset[int]


def _identical_winner_order(fingerprint: PhotoFingerprint) -> tuple[object, ...]:
    """Sortierschluessel von Durchgang 1: hoechste Aufloesung, dann aeltere VERLAESSLICHE
    Aufnahmezeit, zuletzt kleinere Id. Unbekannte Aufloesung sortiert zuletzt, nicht als 0 -
    sonst bevorzugte die Regel eine Aufnahme, ueber die nichts bekannt ist.

    Pfad und Dateiname sind nie Eingabe; der Fingerabdruck traegt sie nicht einmal."""
    return (
        fingerprint.pixel_count is None,
        -(fingerprint.pixel_count or 0),
        not fingerprint.taken_at_trusted,
        fingerprint.taken_at or datetime.max,
        fingerprint.photo_id,
    )


def assign_duplicate_groups(fingerprints: Sequence[PhotoFingerprint]) -> DuplicateAssignment:
    """Die Duplikatgruppen als STERN um je einen Gewinner: `loser -> winner`.

    ZWEI DURCHGAENGE (ADR 0146 Punkt 1):
    * Durchgang 1 baut Sterne ausschliesslich ueber identische Kanten, sortiert nach
      `_identical_winner_order`. Diese Sterne sind bauartbedingt vollstaendig identisch; ihre
      Gewinner stehen in `identical_winners` und sind fuer Durchgang 2 verbraucht, damit ein
      aehnliches Kettenmitglied den Stern nicht nachtraeglich erweitert (keine teilweise
      automatische Gruppe).
    * Durchgang 2 ist der bisherige Stern ueber die verbliebenen freien Fotos nach
      `(-sharpness, photo_id)`; hier mischen sich identische und aehnliche Kanten wie zuvor,
      aber ein Stern aus Durchgang 1 waechst nicht mehr.

    HARTE STUFE-1-GRENZE in beiden Durchgaengen: Nur Paare aus `candidate_pairs` werden geprueft
    - ein Paar mit grober Hamming-Distanz ueber `DUPLICATE_CANDIDATE_HAMMING` ist kein Kandidat
    und wird nicht einmal angesehen (ADR 0145).

    Aufgenommen werden nur FREIE Fotos mit einer DIREKTEN Kante zum Gewinner - ein Kettenmitglied,
    das nur ueber ein anderes Mitglied haengt, bleibt ungruppiert. Fuer zwei aehnliche (nicht
    identische) Mitglieder gilt zusaetzlich paarweise das Zeitfenster; ein Kandidat, der es gegen
    ein bereits aufgenommenes Mitglied verletzt, wird nicht aufgenommen. Jedes Foto wird
    hoechstens einmal zugeordnet, der Gewinner steht nirgends im Ergebnis."""
    pairs = candidate_pairs(fingerprints)
    assigned: set[int] = set()
    result: dict[int, int] = {}
    identical_winners: set[int] = set()

    # --- Durchgang 1: praktisch identische Sterne ------------------------------------------
    for winner in sorted(fingerprints, key=_identical_winner_order):
        if winner.photo_id in assigned:
            continue
        members = [
            candidate
            for candidate in fingerprints
            if candidate.photo_id not in assigned
            and _is_identical_candidate(winner, candidate, pairs)
        ]
        if not members:
            # Ohne identisches Mitglied bleibt das Foto fuer Durchgang 2 frei - ein Gewinner ohne
            # Stern darf nicht als "verbraucht" gelten, sonst verloere es seinen Platz im
            # Aehnlichkeitsstern.
            continue
        assigned.add(winner.photo_id)
        for member in members:
            assigned.add(member.photo_id)
            result[member.photo_id] = winner.photo_id
        identical_winners.add(winner.photo_id)

    # --- Durchgang 2: der bisherige Stern ueber die verbliebenen freien Fotos ----------------
    ordered = sorted(
        fingerprints, key=lambda fingerprint: (-fingerprint.sharpness, fingerprint.photo_id)
    )
    for winner in ordered:
        if winner.photo_id in assigned:
            continue
        assigned.add(winner.photo_id)
        similar_members: list[PhotoFingerprint] = []
        for candidate in ordered:
            if candidate.photo_id in assigned:
                continue
            key = (
                min(winner.photo_id, candidate.photo_id),
                max(winner.photo_id, candidate.photo_id),
            )
            if key not in pairs:
                continue
            edge = _edge_kind(winner, candidate)
            if edge is None:
                continue
            if edge == _SIMILAR and any(
                not _within_window(candidate, member) for member in similar_members
            ):
                continue
            assigned.add(candidate.photo_id)
            result[candidate.photo_id] = winner.photo_id
            if edge == _SIMILAR:
                similar_members.append(candidate)
    return DuplicateAssignment(duplicate_of=result, identical_winners=frozenset(identical_winners))


def _is_identical_candidate(
    winner: PhotoFingerprint,
    candidate: PhotoFingerprint,
    pairs: set[tuple[int, int]],
) -> bool:
    """Direkte identische Kante UND Kandidat der harten Stufe 1 - in dieser Reihenfolge, damit
    die teurere Pixel-Pruefung nur fuer Paare aus dem Netz laeuft."""
    key = (min(winner.photo_id, candidate.photo_id), max(winner.photo_id, candidate.photo_id))
    return key in pairs and is_practically_identical(winner, candidate)


def haversine_meters(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
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
            and haversine_meters(*reference_coordinate, *coordinate) > split_distance_meters
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
