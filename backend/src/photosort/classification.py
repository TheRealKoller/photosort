from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image, ImageFilter, ImageStat

from photosort.models import PhotoCategory

# specs/features/0024-top-photo-selection-category-mix.md, decisions/0015-lokale-kategorie-
# klassifikation.md: bewusst ein eigenes Modul statt Erweiterung von scoring.py, damit die neue
# mediapipe-Abhaengigkeit nicht in den leichten Phase-A-Importpfad (worker.py::run_project_scoring,
# laeuft fuer JEDES gescannte Foto) einsickert - classification.py wird nur vom neuen, separaten
# select_top_photos-Job importiert.

# Laplace-Kernel-Varianz-Schwellwert je 8x8-Kachel, unterhalb dessen eine Kachel als "flaechig/
# uniform" gilt - dieselbe Kennzahl wie scoring.py::compute_sharpness (Laplace-Kernel-Varianz),
# nur pro Kachel statt ueber das gesamte Bild angewendet. Bewusst dieselbe Groessenordnung wie
# scoring.SHARPNESS_REJECT_THRESHOLD (15.0) - beide messen dieselbe zugrunde liegende Eigenschaft
# (lokaler Kantenkontrast), nicht kalibriert gegen einen echten Fotokorpus (kein Korpus im Repo,
# siehe Teststrategie-Abschnitt der Spec und scoring.py-Kommentar zu SHARPNESS_REJECT_THRESHOLD).
UNIFORM_TILE_VARIANCE_THRESHOLD = 15.0

# Kachelraster fuer compute_uniform_area_fraction (Architektur-Abschnitt der Spec: "8x8").
_UNIFORM_TILE_GRID = 8

# Anteil "flaechiger" Kacheln, ab dem ein Foto ohne erkanntes Gesicht als LANDSCAPE statt DETAIL
# gilt (Prioritaetskette der Spec). Technische Detailentscheidung der Umsetzung, nicht gegen einen
# echten Fotokorpus kalibriert (siehe Teststrategie-Abschnitt) - ein typisches Landschaftsfoto
# (Himmel/Wasser/gleichmaessige Flaechen) sollte mindestens die Haelfte des Kachelrasters als
# uniform ausweisen.
LANDSCAPE_UNIFORM_FRACTION_THRESHOLD = 0.5

# Mindest-Konfidenz einer mediapipe-Gesichtserkennung, ab der detect_person ein Gesicht als
# tatsaechlich erkannt wertet - eigene, explizite Schwelle statt sich blind auf den Detector selbst
# zu verlassen (der intern ebenfalls mit einem konfigurierten min_detection_confidence arbeitet),
# damit die Entscheidungslogik unabhaengig von der konkreten Detector-Konfiguration testbar bleibt
# (siehe FakeFaceDetector in test_classification.py).
FACE_DETECTION_CONFIDENCE_THRESHOLD = 0.5

# Gepinnte, direkt im Repository eingecheckte .tflite-Modelldatei (Security-Abschnitt der Spec:
# kein Laufzeit-Download vom Worker aus einer externen CDN-URL) - technische Detailentscheidung der
# Umsetzung: statt eines Download-Schritts WAEHREND `docker build` (der selbst wieder eine
# Pruefsummen-Verifikation braeuchte und einen Netzwerkzugriff zur Build-Zeit voraussetzt) wird die
# ~230KB grosse Datei wie ein normales Code-Asset direkt committet - reproduzierbar ueber die
# Git-Historie, kein zusaetzlicher Build-Schritt. Quelle: offizielles mediapipe-Modell-Repository
# (https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/
# blaze_face_short_range.tflite, sha256 b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380
# b0152f). "assets/" statt "models/" als Verzeichnisname, um keine Namenskollision mit dem
# bestehenden Modul photosort/models.py (Datenmodelle) zu erzeugen.
_FACE_DETECTOR_MODEL_PATH = Path(__file__).parent / "assets" / "blaze_face_short_range.tflite"

_LAPLACE_KERNEL = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1)


def _laplace_edges_without_border_artifact(grayscale: Image.Image) -> Image.Image:
    """Wendet den Laplace-Kernel auf das GESAMTE Bild an (nicht pro Kachel), gepolstert mit
    Rand-Wiederholung (`np.pad(..., mode="edge")`), statt Pillows Standardverhalten (unveraenderter
    Originalwert am Bildrand, kein Zero-Padding - siehe scoring.py::compute_sharpness-Kommentar).
    Bei einem GLOBAL angewendeten Filter faellt dieser 1px-Randeffekt fuer ein einzelnes
    Grossflaechen-Sharpness-Mass nicht ins Gewicht (scoring.py); hier wird das Ergebnis aber
    anschliessend in ein 8x8-Kachelraster zerschnitten - ohne Korrektur wuerde JEDE am Bildrand
    liegende Kachel (28 von 64) faelschlich eine hohe Varianz zeigen, selbst bei einem komplett
    flaechigen Bild (Review-Fund waehrend der Umsetzung)."""
    array = np.asarray(grayscale)
    padded = np.pad(array, pad_width=1, mode="edge")
    filtered = Image.fromarray(padded).filter(_LAPLACE_KERNEL)
    width, height = grayscale.size
    return filtered.crop((1, 1, width + 1, height + 1))


def compute_uniform_area_fraction(image: Image.Image) -> float:
    """Anteil der Kacheln eines 8x8-Rasters, deren Laplace-Kernel-Varianz unterhalb von
    UNIFORM_TILE_VARIANCE_THRESHOLD liegt - reuse derselben Technik wie
    scoring.py::compute_sharpness, hier pro Kachel statt global angewendet (Architektur-Abschnitt
    der Spec). 1.0 = komplett flaechiges Bild, 0.0 = durchgehend texturiert/kontrastreich."""
    grayscale = image.convert("L")
    width, height = grayscale.size
    edges = _laplace_edges_without_border_artifact(grayscale)
    tile_width = max(1, width // _UNIFORM_TILE_GRID)
    tile_height = max(1, height // _UNIFORM_TILE_GRID)

    uniform_tiles = 0
    total_tiles = 0
    for row in range(_UNIFORM_TILE_GRID):
        top = row * tile_height
        bottom = height if row == _UNIFORM_TILE_GRID - 1 else top + tile_height
        if top >= bottom:
            continue
        for col in range(_UNIFORM_TILE_GRID):
            left = col * tile_width
            right = width if col == _UNIFORM_TILE_GRID - 1 else left + tile_width
            if left >= right:
                continue
            variance = ImageStat.Stat(edges.crop((left, top, right, bottom))).var[0]
            total_tiles += 1
            if variance < UNIFORM_TILE_VARIANCE_THRESHOLD:
                uniform_tiles += 1

    return uniform_tiles / total_tiles if total_tiles else 0.0


class DetectionResultLike(Protocol):
    """Die schmale Teilmenge von mediapipe.tasks.python.components.containers.DetectionResult, die
    detect_person braucht - erlaubt einen FakeFaceDetector in Tests ohne echte mediapipe-Typen
    (Teststrategie-Abschnitt der Spec)."""

    detections: list[object]


class FaceDetectorLike(Protocol):
    def detect(self, image: object) -> DetectionResultLike: ...


def _to_mp_image(image: Image.Image) -> object:
    # Lokaler Import (statt Modul-weit): haelt die harte mediapipe-Abhaengigkeit auf den Pfad
    # begrenzt, der tatsaechlich ein echtes Bild klassifiziert - Tests, die detect_person mit einem
    # FakeFaceDetector aufrufen, brauchen trotzdem eine echte mediapipe-Installation fuer diese
    # Konvertierung (mediapipe ist ab dieser Spec eine harte Backend-Abhaengigkeit, siehe
    # pyproject.toml), aber nie ein echtes .tflite-Modell.
    import mediapipe as mp

    rgb = image.convert("RGB")
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(rgb))


def detect_person(image: Image.Image, detector: FaceDetectorLike) -> bool:
    """mediapipe Face Detector Task-API (Architektur-Abschnitt der Spec) auf der bereits gecachten
    display-Variante. `detector` ist injizierbar (siehe FaceDetectorLike) - die reale
    Modellkonstruktion (build_face_detector) laeuft in keinem automatisierten Test."""
    result = detector.detect(_to_mp_image(image))
    for detection in result.detections:
        categories = getattr(detection, "categories", [])
        if any(category.score >= FACE_DETECTION_CONFIDENCE_THRESHOLD for category in categories):
            return True
    return False


def build_face_detector() -> FaceDetectorLike:
    """Baut den echten mediapipe FaceDetector aus dem zur Build-Zeit gebuendelten .tflite-Modell
    (Security-Abschnitt der Spec - kein Laufzeit-Download). Wird NIE in einem automatisierten Test
    aufgerufen (Infrastruktur-/CI-Risiko, siehe Teststrategie-Abschnitt), nur vom Worker-Job."""
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core.base_options import BaseOptions

    options = vision.FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(_FACE_DETECTOR_MODEL_PATH)),
        min_detection_confidence=FACE_DETECTION_CONFIDENCE_THRESHOLD,
    )
    detector: FaceDetectorLike = vision.FaceDetector.create_from_options(options)
    return detector


def classify_category(
    image: Image.Image,
    detector: FaceDetectorLike,
    *,
    detect_person: Callable[[Image.Image, FaceDetectorLike], bool] = detect_person,
) -> PhotoCategory:
    """Deterministische Prioritaetskette (Akzeptanzkriterium der Spec): Gesicht erkannt -> PEOPLE;
    sonst hoher Uniform-Flaechen-Anteil -> LANDSCAPE; sonst -> DETAIL (Fallback). `detect_person`
    ist injizierbar (Default: das echte, oben definierte detect_person) fuer Testbarkeit ohne
    echtes mediapipe-Modell - Tests uebergeben stattdessen ein einfaches Lambda und einen
    beliebigen Platzhalter fuer `detector` (wird vom Fake ohnehin ignoriert). `detector` ist ein
    Pflichtparameter (kein Default): worker.py baut ihn EINMAL pro Job (build_face_detector),
    nicht pro Foto - eine Default-Konstruktion hier wuerde entweder das echte Modell schon beim
    Import laden (teuer, in Tests unerwuenscht) oder pro Aufruf neu bauen (Performance)."""
    if detect_person(image, detector):
        return PhotoCategory.PEOPLE
    if compute_uniform_area_fraction(image) >= LANDSCAPE_UNIFORM_FRACTION_THRESHOLD:
        return PhotoCategory.LANDSCAPE
    return PhotoCategory.DETAIL


# Feste Kategorie-Reihenfolge fuer das Quotenverfahren (Akzeptanzkriterium der Spec) - bestimmt,
# welche Kategorie(n) bei einem divmod-Rest den zusaetzlichen Sitz bekommen.
_CATEGORY_ORDER = (PhotoCategory.LANDSCAPE, PhotoCategory.DETAIL, PhotoCategory.PEOPLE)


@dataclass(frozen=True)
class CategoryCandidate:
    photo_id: int
    category: PhotoCategory
    local_quality_score: float


def select_top_n_with_category_mix(candidates: list[CategoryCandidate], n: int) -> list[int]:
    """Pure, DB-freie Funktion (analog scoring.py::assign_time_clusters): verteilt N per divmod auf
    die im Cluster tatsaechlich vorhandenen Kategorien (feste Reihenfolge LANDSCAPE/DETAIL/PEOPLE),
    waehlt pro Kategorie bis zur Quote die Fotos mit dem hoechsten local_quality_score (Tie-Break:
    niedrigere photo_id). KEIN Nachziehen aus anderen Kategorien, wenn eine Kategorie ihre Quote
    nicht erreicht (Akzeptanzkriterium der Spec) - die tatsaechliche Trefferzahl kann unter N
    bleiben."""
    by_category: dict[PhotoCategory, list[CategoryCandidate]] = {}
    for candidate in candidates:
        by_category.setdefault(candidate.category, []).append(candidate)

    present_categories = [category for category in _CATEGORY_ORDER if category in by_category]
    if not present_categories:
        return []

    quotient, remainder = divmod(n, len(present_categories))

    selected: list[int] = []
    for index, category in enumerate(present_categories):
        quota = quotient + (1 if index < remainder else 0)
        pool = sorted(
            by_category[category], key=lambda c: (-c.local_quality_score, c.photo_id)
        )
        selected.extend(candidate.photo_id for candidate in pool[:quota])

    return sorted(selected)
