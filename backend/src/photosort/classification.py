from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image, ImageFilter, ImageStat

# specs/features/0024-top-photo-selection-category-mix.md, decisions/0015-lokale-kategorie-
# klassifikation.md: bewusst ein eigenes Modul statt Erweiterung von scoring.py, damit die neue
# mediapipe-Abhaengigkeit nicht in den leichten Phase-A-Importpfad (worker.py::run_project_scoring,
# laeuft fuer JEDES gescannte Foto) einsickert - classification.py wird nur von criteria.py (und
# darueber vom neuen run_criterion_scoring-Job, specs/features/0037-gatefuehrte-bewertungs-
# pipeline-mit-backfill.md) importiert. `classify_category`/`CategoryCandidate`/
# `select_top_n_with_category_mix` sind mit Spec 0037 entfallen - die Kategorie-Ableitung lebt jetzt
# in criteria.py::derive_category_key (datengetrieben aus Kriterien-Werten statt eines hart
# codierten Einzelaufrufs), die Rangfolge in ranking.py::rank_photos (ersetzt das Quotenverfahren).

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

# Security-Review-Fund (Nice-to-have): ohne einen automatisierten Abgleich wuerde eine kuenftige
# versehentliche Beschaedigung/Ersetzung der Binaerdatei (fehlerhaftes Merge, LFS-Fehlkonfiguration)
# nicht auffallen, bevor die Erkennungsguete spuerbar leidet - siehe test_classification.py.
FACE_DETECTOR_MODEL_SHA256 = "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f"

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


# --- Symmetrie (specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md,
# decisions/0026-modellwahl-symmetrie-horizont-freiraum-kriterien.md Punkt 1): Quadranten-Energie-
# Vergleich auf der bereits vorhandenen Laplace-Kantenkarte - keine neue Abhaengigkeit, reine
# Wiederverwendung von _laplace_edges_without_border_artifact (bisher nur fuer
# compute_uniform_area_fraction genutzt).


def _mean_abs_edge_energy(edges: np.ndarray) -> float:
    """"Energie" eines Bildbereichs (ADR 0026 Punkt 1) = mittlerer Betrag der Laplace-
    Kantenwerte - ein Aktivitaets-/Kontrastmass, keine Positions-/Motivbewertung (Abgrenzung zu
    goldener_schnitt). 0-geschuetzt gegen ein leeres Array (degenerierter Quadrant bei sehr
    kleinen Bildern, analog compute_uniform_area_fraction's total_tiles-Schutz)."""
    return float(np.abs(edges).mean()) if edges.size else 0.0


def _safe_relative_diff(a: float, b: float) -> float:
    """0-geschuetzte relative Differenz (ADR 0026 Punkt 1: `|E_a - E_b| / (E_a + E_b)`) - liefert
    0.0 statt ZeroDivisionError/NaN, wenn beide Seiten keine Energie haben (z.B. komplett
    flaechiges Bild)."""
    total = a + b
    if total == 0:
        return 0.0
    return abs(a - b) / total


def compute_symmetry_score(image: Image.Image) -> float:
    """`symmetrie`-Kriterium (ADR 0026 Punkt 1): Quadranten-Energie-Vergleich auf der
    Laplace-Kantenkarte des GESAMTEN Bildes (nicht auf einem 8x8-Kachelraster wie
    compute_uniform_area_fraction, sondern auf einem 2x2-Quadranten-Raster). Bild wird in vier
    Quadranten geteilt (oben-links/-rechts, unten-links/-rechts); je Quadrant die mittlere
    Kantenenergie, danach paarweise zu E_links/E_rechts/E_oben/E_unten gemittelt (technische
    Detailentscheidung der Umsetzung: gleichgewichtete Mittelung der beiden angrenzenden
    Quadranten-Energien, NICHT eine flaechengewichtete Mittelung ueber alle betroffenen Pixel -
    beide Varianten sind bei einer geraden Bildgroesse identisch, unterscheiden sich nur bei
    ungeraden Massen geringfuegig). `score = clip(1.0 - (horizontal_diff + vertical_diff) / 2, 0,
    1)`.

    Rundungsregel bei ungeraden Bildmassen (AK der Spec 0048, durch Testfall gepinnt): identisch
    zu compute_uniform_area_fraction's 8x8-Kachelraster - `width // 2`/`height // 2` als Grenze
    der ERSTEN Haelfte, die ZWEITE Haelfte nimmt den Rest (`array[mid:]` statt einer symmetrischen
    Aufteilung um die Mitte).

    Fallback (ADR 0026, dokumentiert, kein Bug): komplett flaechiges Bild (Gesamtenergie 0) ->
    beide Diffs per Definition 0 (siehe _safe_relative_diff) -> score = 1.0, ein flaechiges Bild
    ist trivial "balanciert", keine Asymmetrie messbar."""
    grayscale = image.convert("L")
    width, height = grayscale.size
    edges = np.asarray(_laplace_edges_without_border_artifact(grayscale), dtype=np.float64)

    mid_x = width // 2
    mid_y = height // 2

    top_left = _mean_abs_edge_energy(edges[:mid_y, :mid_x])
    top_right = _mean_abs_edge_energy(edges[:mid_y, mid_x:])
    bottom_left = _mean_abs_edge_energy(edges[mid_y:, :mid_x])
    bottom_right = _mean_abs_edge_energy(edges[mid_y:, mid_x:])

    e_left = (top_left + bottom_left) / 2
    e_right = (top_right + bottom_right) / 2
    e_top = (top_left + top_right) / 2
    e_bottom = (bottom_left + bottom_right) / 2

    horizontal_diff = _safe_relative_diff(e_left, e_right)
    vertical_diff = _safe_relative_diff(e_top, e_bottom)
    return max(0.0, min(1.0, 1.0 - (horizontal_diff + vertical_diff) / 2))


class BoundingBoxLike(Protocol):
    """Die schmale Teilmenge von mediapipe.tasks.python.components.containers.BoundingBox, die
    detect_person braucht (Pixel-Koordinaten, nicht normiert)."""

    origin_x: int
    origin_y: int
    width: int
    height: int


class DetectionLike(Protocol):
    categories: list[object]
    bounding_box: BoundingBoxLike


class DetectionResultLike(Protocol):
    """Die schmale Teilmenge von mediapipe.tasks.python.components.containers.DetectionResult, die
    detect_person braucht - erlaubt einen FakeFaceDetector in Tests ohne echte mediapipe-Typen
    (Teststrategie-Abschnitt der Spec)."""

    detections: list[DetectionLike]


class FaceDetectorLike(Protocol):
    def detect(self, image: object) -> DetectionResultLike: ...


@dataclass(frozen=True)
class FaceBoundingBox:
    """Auf die Bildgroesse normierte Position eines erkannten Gesichts (specs/features/0037-
    gatefuehrte-bewertungs-pipeline-mit-backfill.md, Abschnitt "Vorgriffs-Ergaenzung" fuer die
    kuenftige Spec 0038, ADR 0022) - `detect_person` gab bis hierhin nur `bool` zurueck; die
    Positionsdaten braucht erst die spaetere Goldener-Schnitt-Kriterien-Spec, der guenstigste
    Zeitpunkt fuer diese Vertragserweiterung ist aber der ohnehin bevorstehende Neubau von
    criteria.py, nicht ein spaeterer Rework. Alle Werte in [0, 1], Ursprung oben links."""

    x_center: float
    y_center: float
    width: float
    height: float
    confidence: float


def _to_mp_image(image: Image.Image) -> object:
    # Lokaler Import (statt Modul-weit): haelt die harte mediapipe-Abhaengigkeit auf den Pfad
    # begrenzt, der tatsaechlich ein echtes Bild klassifiziert - Tests, die detect_person mit einem
    # FakeFaceDetector aufrufen, brauchen trotzdem eine echte mediapipe-Installation fuer diese
    # Konvertierung (mediapipe ist ab dieser Spec eine harte Backend-Abhaengigkeit, siehe
    # pyproject.toml), aber nie ein echtes .tflite-Modell.
    import mediapipe as mp

    rgb = image.convert("RGB")
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(rgb))


def detect_person(image: Image.Image, detector: FaceDetectorLike) -> list[FaceBoundingBox]:
    """mediapipe Face Detector Task-API (Architektur-Abschnitt der Spec) auf der bereits gecachten
    display-Variante. `detector` ist injizierbar (siehe FaceDetectorLike) - die reale
    Modellkonstruktion (build_face_detector) laeuft in keinem automatisierten Test.

    Gibt seit specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md eine Liste
    normierter FaceBoundingBox-Treffer zurueck statt eines blossen bool (Vorgriff auf die
    Positionsdaten, die die kuenftige Goldener-Schnitt-Kriterien-Spec 0038 braucht) - fuer den
    aktuellen content_people-Kriterien-Compute aendert sich funktional nichts
    (`bool(detect_person(...))` als Score-Grundlage, siehe criteria.py)."""
    width, height = image.size
    result = detector.detect(_to_mp_image(image))
    boxes: list[FaceBoundingBox] = []
    for detection in result.detections:
        categories = getattr(detection, "categories", [])
        best_confidence = max((category.score for category in categories), default=0.0)
        if best_confidence < FACE_DETECTION_CONFIDENCE_THRESHOLD:
            continue
        box = detection.bounding_box
        boxes.append(
            FaceBoundingBox(
                x_center=(box.origin_x + box.width / 2) / width,
                y_center=(box.origin_y + box.height / 2) / height,
                width=box.width / width,
                height=box.height / height,
                confidence=best_confidence,
            )
        )
    return boxes


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


# --- Tier-Erkennung (specs/features/0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-
# aesthetik.md, decisions/0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md Punkt 1):
# mediapipe Object Detector Task API, EfficientDet-Lite0 (COCO-80-Klassen) - exakt dasselbe
# Muster wie der obige FaceDetector, nur eine andere Task-API derselben bereits vorhandenen
# mediapipe-Abhaengigkeit. Keine neue Abhaengigkeit.

# Tier-relevante COCO-Klassen (ADR 0022 Punkt 1) - 10 von 80 COCO-Klassen. Dokumentierte, bewusst
# akzeptierte Luecke (AK-Pflicht der Spec): COCO enthaelt KEINE Insekten- oder Fisch-Klasse, diese
# werden mit diesem Modell strukturell nicht erkannt (waere eine eigenstaendige, spaetere
# Ergaenzung mit einem anderen Modell, nicht Teil dieser Spec).
ANIMAL_CATEGORIES = frozenset(
    {"bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"}
)

# Mindest-Konfidenz, ab der eine Tier-Erkennung gewertet wird - analog
# FACE_DETECTION_CONFIDENCE_THRESHOLD, eigene explizite Schwelle statt sich auf den vom Detector
# intern konfigurierten score_threshold zu verlassen (gleiche Testbarkeits-Begruendung wie dort).
ANIMAL_DETECTION_CONFIDENCE_THRESHOLD = 0.5

# Gepinnte, im Repository eingecheckte .tflite-Modelldatei (Security-Abschnitt der Spec 0038,
# kein Laufzeit-Download) - analog zum FaceDetector-Muster oben. Quelle: offizielles
# mediapipe-Modell-Repository (https://storage.googleapis.com/mediapipe-models/object_detector/
# efficientdet_lite0/int8/1/efficientdet_lite0.tflite), int8-quantisierte Variante (~4,4 MB,
# innerhalb der von ADR 0022 erwarteten ~4-7 MB).
_OBJECT_DETECTOR_MODEL_PATH = Path(__file__).parent / "assets" / "efficientdet_lite0.tflite"

# Security-Muss-Kriterium (Spec-0038-Security-Abschnitt, Punkt 3: "automatisierter Test fuer jedes
# der vier Modell-Assets, nicht nur nice to have") - siehe test_classification.py.
OBJECT_DETECTOR_MODEL_SHA256 = (
    "0720bf247bd76e6594ea28fa9c6f7c5242be774818997dbbeffc4da460c723bb"
)


class DetectionCategoryLike(Protocol):
    """Die schmale Teilmenge von mediapipe.tasks.python.components.containers.Category, die
    detect_animals braucht."""

    category_name: str | None
    score: float


class ObjectDetectionLike(Protocol):
    categories: list[DetectionCategoryLike]
    bounding_box: BoundingBoxLike


class ObjectDetectionResultLike(Protocol):
    detections: list[ObjectDetectionLike]


class ObjectDetectorLike(Protocol):
    def detect(self, image: object) -> ObjectDetectionResultLike: ...


@dataclass(frozen=True)
class AnimalDetection:
    """Eine einzelne, oberhalb von ANIMAL_DETECTION_CONFIDENCE_THRESHOLD erkannte Tier-Instanz
    (ADR 0022 Punkt 1) - Bounding-Box-Felder normiert wie FaceBoundingBox (auf die Bildgroesse
    bezogen, [0, 1], Ursprung oben links), damit beide Typen strukturell denselben
    Kompositions-Subjekt-Vertrag (criteria.py::SubjectBoxLike) erfuellen und die Goldener-Schnitt-
    Heuristik sie ohne Sonderfall gleich behandeln kann."""

    category: str
    confidence: float
    x_center: float
    y_center: float
    width: float
    height: float


def detect_animals(image: Image.Image, detector: ObjectDetectorLike) -> list[AnimalDetection]:
    """mediapipe Object Detector Task-API (ADR 0022 Punkt 1) auf der bereits gecachten
    display-Variante, gefiltert auf ANIMAL_CATEGORIES. `detector` ist injizierbar (siehe
    ObjectDetectorLike) - die reale Modellkonstruktion (build_object_detector) laeuft in keinem
    automatisierten Test. Nur die JEWEILS hoechstbewertete Kategorie pro Erkennung wird betrachtet
    (das Modell liefert typischerweise bereits eine nach Score sortierte Kandidatenliste je
    erkanntem Objekt) - keine zweitplatzierte Tier-Kategorie "rettet" eine primaer als etwas
    anderes klassifizierte Erkennung."""
    width, height = image.size
    result = detector.detect(_to_mp_image(image))
    detections: list[AnimalDetection] = []
    for detection in result.detections:
        categories = getattr(detection, "categories", [])
        if not categories:
            continue
        top = categories[0]
        name = getattr(top, "category_name", None)
        score = getattr(top, "score", 0.0)
        if name not in ANIMAL_CATEGORIES or score < ANIMAL_DETECTION_CONFIDENCE_THRESHOLD:
            continue
        box = detection.bounding_box
        detections.append(
            AnimalDetection(
                category=name,
                confidence=score,
                x_center=(box.origin_x + box.width / 2) / width,
                y_center=(box.origin_y + box.height / 2) / height,
                width=box.width / width,
                height=box.height / height,
            )
        )
    return detections


def build_object_detector() -> ObjectDetectorLike:
    """Baut den echten mediapipe ObjectDetector aus dem zur Build-Zeit gebuendelten .tflite-Modell
    (Security-Abschnitt der Spec 0038 - kein Laufzeit-Download). Wird NIE in einem automatisierten
    Test aufgerufen (Infrastruktur-/CI-Risiko, analog build_face_detector), nur vom Worker-Job."""
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core.base_options import BaseOptions

    options = vision.ObjectDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(_OBJECT_DETECTOR_MODEL_PATH)),
        score_threshold=ANIMAL_DETECTION_CONFIDENCE_THRESHOLD,
    )
    detector: ObjectDetectorLike = vision.ObjectDetector.create_from_options(options)
    return detector


# --- Gebaeude-Erkennung (specs/features/0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-
# aesthetik.md, decisions/0022-lokale-modellwahl-tier-gebaeude-aesthetik-kriterien.md Punkt 2):
# mediapipe Image Classifier Task API, ImageNet-1k-Modell EfficientNet-Lite0 - drittes Task-API-
# Paar derselben bereits vorhandenen mediapipe-Abhaengigkeit, keine neue Abhaengigkeit.
#
# WICHTIG, anders als bei Tier: classify_scene filtert NICHT auf die Architektur-Allow-Liste -
# sie liefert alle Klassifikations-Ergebnisse oberhalb von SCENE_CLASSIFICATION_CONFIDENCE_
# THRESHOLD unveraendert zurueck (rohe Modell-Ausgabe). Die Allow-Liste-Filterung passiert bewusst
# erst in criteria.py::compute_gebaeude_score - Akzeptanzkriterium der Spec 0038 verlangt einen
# Testnachweis, "dass tatsaechlich die Allow-Liste filtert und nicht nur die rohe Modell-Konfidenz
# durchgereicht wird"; dieser Nachweis waere hier auf classify_scene-Ebene sinnlos, wenn schon
# hier gefiltert wuerde.

# Mindest-Konfidenz, ab der eine Szenen-Klassifikation ueberhaupt in Betracht gezogen wird -
# analog FACE_DETECTION_CONFIDENCE_THRESHOLD/ANIMAL_DETECTION_CONFIDENCE_THRESHOLD.
SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.5

# Gepinnte, im Repository eingecheckte .tflite-Modelldatei (Security-Abschnitt der Spec 0038,
# kein Laufzeit-Download). Quelle: offizielles mediapipe-Modell-Repository
# (https://storage.googleapis.com/mediapipe-models/image_classifier/efficientnet_lite0/int8/1/
# efficientnet_lite0.tflite), int8-quantisierte Variante (~5,4 MB).
_SCENE_CLASSIFIER_MODEL_PATH = Path(__file__).parent / "assets" / "efficientnet_lite0.tflite"

# Security-Muss-Kriterium (Spec-0038-Security-Abschnitt, Punkt 3).
SCENE_CLASSIFIER_MODEL_SHA256 = "bc2ffe19c1118de0c0c2a9088992da5589722656e0fba81421385300a4a34b16"


class ClassificationsLike(Protocol):
    """Die schmale Teilmenge von mediapipe.tasks.python.components.containers.Classifications,
    die classify_scene braucht."""

    categories: list[DetectionCategoryLike]


class ImageClassificationResultLike(Protocol):
    classifications: list[ClassificationsLike]


class SceneClassifierLike(Protocol):
    def classify(self, image: object) -> ImageClassificationResultLike: ...


@dataclass(frozen=True)
class SceneLabel:
    """Eine einzelne, oberhalb von SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD klassifizierte
    ImageNet-1k-Szenen-/Objekt-Kategorie (ADR 0022 Punkt 2) - UNGEFILTERT, siehe Modul-Kommentar
    oben. Kein Bounding-Box-Feld (anders als AnimalDetection/FaceBoundingBox): ein Image
    Classifier bewertet das GESAMTE Bild, keine einzelne Bildregion."""

    category: str
    confidence: float


def classify_scene(image: Image.Image, classifier: SceneClassifierLike) -> list[SceneLabel]:
    """mediapipe Image Classifier Task-API (ADR 0022 Punkt 2) auf der bereits gecachten
    display-Variante - liefert ALLE Klassifikationen oberhalb von
    SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD, unabhaengig davon, ob sie architekturbezogen sind
    (siehe Modul-Kommentar). `classifier` ist injizierbar (siehe SceneClassifierLike) - die reale
    Modellkonstruktion (build_scene_classifier) laeuft in keinem automatisierten Test."""
    result = classifier.classify(_to_mp_image(image))
    labels: list[SceneLabel] = []
    for classifications in result.classifications:
        for category in classifications.categories:
            name = getattr(category, "category_name", None)
            score = getattr(category, "score", 0.0)
            if name is None or score < SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD:
                continue
            labels.append(SceneLabel(category=name, confidence=score))
    return labels


def build_scene_classifier() -> SceneClassifierLike:
    """Baut den echten mediapipe ImageClassifier aus dem zur Build-Zeit gebuendelten .tflite-
    Modell (Security-Abschnitt der Spec 0038 - kein Laufzeit-Download). Wird NIE in einem
    automatisierten Test aufgerufen (Infrastruktur-/CI-Risiko, analog build_face_detector/
    build_object_detector), nur vom Worker-Job."""
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core.base_options import BaseOptions

    options = vision.ImageClassifierOptions(
        base_options=BaseOptions(model_asset_path=str(_SCENE_CLASSIFIER_MODEL_PATH)),
        score_threshold=SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD,
    )
    classifier: SceneClassifierLike = vision.ImageClassifier.create_from_options(options)
    return classifier
