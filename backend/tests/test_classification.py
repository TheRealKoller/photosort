from __future__ import annotations

import hashlib
import random
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageDraw

from photosort.classification import (
    _FACE_DETECTOR_MODEL_PATH,
    _OBJECT_DETECTOR_MODEL_PATH,
    _SCENE_CLASSIFIER_MODEL_PATH,
    ANIMAL_DETECTION_CONFIDENCE_THRESHOLD,
    FACE_DETECTOR_MODEL_SHA256,
    OBJECT_DETECTOR_MODEL_SHA256,
    SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD,
    SCENE_CLASSIFIER_MODEL_SHA256,
    AnimalDetection,
    FaceBoundingBox,
    SceneLabel,
    classify_scene,
    compute_symmetry_score,
    compute_uniform_area_fraction,
    detect_animals,
    detect_person,
)


def _solid(color: tuple[int, int, int] = (120, 120, 120), size: int = 160) -> Image.Image:
    return Image.new("RGB", (size, size), color=color)


def _noisy(size: int = 160, seed: int = 0) -> Image.Image:
    # Pseudozufaellige, hochfrequente Textur ohne wiederkehrende Struktur (jedes Pixel unabhaengig
    # zufaellig) - jede 8x8-Kachel hat dadurch eine deutlich von 0 verschiedene Laplace-Varianz,
    # anders als eine flaeche Farbe.
    rng = random.Random(seed)
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            value = rng.randrange(256)
            pixels[x, y] = (value, value, value)
    return image


def _half_uniform_half_noisy(size: int = 160) -> Image.Image:
    # Obere Haelfte flaechig, untere Haelfte texturiert - liefert einen ueber das 8x8-Kachelraster
    # exakt hälftig verteilten Uniform-Anteil (4 von 8 Zeilen je Kachelspalte).
    image = _noisy(size=size)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, size, size // 2), fill=(100, 100, 100))
    return image


class TestFaceDetectorModelAsset:
    def test_committed_tflite_model_matches_the_documented_sha256(self) -> None:
        # Security-Review-Fund (Nice-to-have): erkennt eine kuenftige versehentliche
        # Beschaedigung/Ersetzung der committeten Binaerdatei (fehlerhaftes Merge,
        # LFS-Fehlkonfiguration) sofort in CI, statt erst durch spuerbar schlechtere
        # Erkennungsguete aufzufallen.
        digest = hashlib.sha256(_FACE_DETECTOR_MODEL_PATH.read_bytes()).hexdigest()
        assert digest == FACE_DETECTOR_MODEL_SHA256


class TestObjectDetectorModelAsset:
    def test_committed_tflite_model_matches_the_documented_sha256(self) -> None:
        # Security-Muss-Kriterium (Spec-0038-Security-Abschnitt, Punkt 3, hochgestuft von
        # "nice to have"): je gepinntem Modell-Asset ein eigener Integritaets-Test.
        digest = hashlib.sha256(_OBJECT_DETECTOR_MODEL_PATH.read_bytes()).hexdigest()
        assert digest == OBJECT_DETECTOR_MODEL_SHA256


class TestSceneClassifierModelAsset:
    def test_committed_tflite_model_matches_the_documented_sha256(self) -> None:
        digest = hashlib.sha256(_SCENE_CLASSIFIER_MODEL_PATH.read_bytes()).hexdigest()
        assert digest == SCENE_CLASSIFIER_MODEL_SHA256


class TestComputeUniformAreaFraction:
    def test_uniform_image_has_fraction_near_one(self) -> None:
        assert compute_uniform_area_fraction(_solid()) > 0.9

    def test_noisy_image_has_fraction_near_zero(self) -> None:
        assert compute_uniform_area_fraction(_noisy()) < 0.1

    def test_half_uniform_half_noisy_image_is_about_half(self) -> None:
        fraction = compute_uniform_area_fraction(_half_uniform_half_noisy())
        assert 0.35 <= fraction <= 0.65

    def test_image_smaller_than_the_tile_grid_does_not_crash(self) -> None:
        # Test-Engineer-Review-Fund (Nice-to-have): ein Bild kleiner als das 8x8-Kachelraster
        # (in der Praxis unwahrscheinlich, die display-Cache-Variante hat eine deutlich groessere
        # Mindestgroesse, siehe thumbnails.py::DISPLAY_MAX_SIZE) darf die degenerierte
        # Kachel-`continue`-Behandlung nicht mit einer Exception verlassen.
        fraction = compute_uniform_area_fraction(_solid(size=4))
        assert 0.0 <= fraction <= 1.0


def _quadrant_mirrored(size: int = 160) -> Image.Image:
    # Doppelt spiegelsymmetrisches Bild (links-rechts UND oben-unten) - jede der vier Quadranten-
    # Energien ist dadurch exakt (nicht nur ungefaehr) gleich, da der Laplace-Kernel bei einem
    # mit "edge"-Padding gepolsterten, spiegelsymmetrischen Bild spiegel-kovariant rechnet (siehe
    # Kommentar in test_perfectly_symmetric_textured_image_scores_one_point_zero unten).
    half = size // 2
    quadrant = _noisy(size=half, seed=1)
    image = Image.new("RGB", (size, size))
    image.paste(quadrant, (0, 0))
    image.paste(quadrant.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (half, 0))
    image.paste(quadrant.transpose(Image.Transpose.FLIP_TOP_BOTTOM), (0, half))
    image.paste(quadrant.transpose(Image.Transpose.ROTATE_180), (half, half))
    return image


def _one_quadrant_textured(size: int = 160) -> Image.Image:
    half = size // 2
    image = _solid(size=size)
    image.paste(_noisy(size=half, seed=2), (0, 0))
    return image


class TestComputeSymmetryScore:
    def test_uniform_image_scores_exactly_one(self) -> None:
        # Dokumentiertes, kein-Bug-Verhalten (AK der Spec 0048): Gesamtenergie 0 -> beide Diffs
        # per Definition 0 -> score = 1.0, ein flaechiges Bild ist trivial "balanciert".
        assert compute_symmetry_score(_solid()) == 1.0

    def test_extremely_asymmetric_image_scores_well_below_half(self) -> None:
        # Energie nur in einem der vier Quadranten - AK der Spec: "score deutlich unter 0.5".
        assert compute_symmetry_score(_one_quadrant_textured()) < 0.3

    def test_perfectly_symmetric_textured_image_scores_one_point_zero(self) -> None:
        # AK der Spec 0048: "Perfekt symmetrisches, texturiertes Bild -> score == 1.0". Der
        # Laplace-Kernel (kleine ganzzahlige Gewichte auf 8-Bit-Graustufenwerten) rechnet exakt
        # ohne Rundungsverlust, und ein "edge"-gepolstertes, doppelt spiegelsymmetrisches Bild
        # bleibt unter dieser Faltung spiegelsymmetrisch - toleranter Vergleich nur als Schutz vor
        # einer nicht vorhergesehenen Gleitkomma-Feinheit, kein weicher Toleranzwert im
        # eigentlichen Sinn.
        assert compute_symmetry_score(_quadrant_mirrored()) == pytest.approx(1.0, abs=1e-9)

    def test_odd_width_and_height_follow_the_uniform_area_fraction_rounding_rule(self) -> None:
        # AK der Spec 0048: gleiche Rundungsregel wie compute_uniform_area_fraction's 8x8-
        # Kachelraster (`width // 2`, letzter Bereich nimmt den Rest), hier auf ein 2x2-
        # Quadranten-Raster angewendet - unabhaengig ueber dieselbe, bereits an anderer Stelle
        # (TestComputeUniformAreaFraction) getestete Kantenkarte nachgerechnet, NICHT ueber eine
        # Kopie der Score-Formel selbst.
        from photosort.classification import _laplace_edges_without_border_artifact

        image = _noisy(size=160, seed=3).resize((7, 5))
        grayscale = image.convert("L")
        width, height = grayscale.size
        edges = np.abs(
            np.asarray(_laplace_edges_without_border_artifact(grayscale), dtype=np.float64)
        )
        mid_x, mid_y = width // 2, height // 2
        top_left = edges[:mid_y, :mid_x].mean()
        top_right = edges[:mid_y, mid_x:].mean()
        bottom_left = edges[mid_y:, :mid_x].mean()
        bottom_right = edges[mid_y:, mid_x:].mean()
        e_left, e_right = (top_left + bottom_left) / 2, (top_right + bottom_right) / 2
        e_top, e_bottom = (top_left + top_right) / 2, (bottom_left + bottom_right) / 2
        horizontal_diff = abs(e_left - e_right) / (e_left + e_right)
        vertical_diff = abs(e_top - e_bottom) / (e_top + e_bottom)
        expected = max(0.0, min(1.0, 1.0 - (horizontal_diff + vertical_diff) / 2))

        assert compute_symmetry_score(image) == pytest.approx(expected)

    def test_image_smaller_than_the_quadrant_grid_does_not_crash(self) -> None:
        # Degenerierter Grenzfall analog test_image_smaller_than_the_tile_grid_does_not_crash.
        score = compute_symmetry_score(_solid(size=1))
        assert 0.0 <= score <= 1.0


class FakeFaceDetector:
    """Faket die schmale Teilmenge der mediapipe-FaceDetector-API, die detect_person braucht -
    kein echtes .tflite-Modell in Tests (Teststrategie-Abschnitt der Spec). Jeder Score erzeugt
    eine Erkennung mit einer festen, plausiblen Pixel-Bounding-Box (specs/features/0037-
    gatefuehrte-bewertungs-pipeline-mit-backfill.md: detect_person gibt seit dieser Spec
    normierte FaceBoundingBox-Objekte statt bool zurueck)."""

    def __init__(
        self,
        scores: list[float],
        box: tuple[int, int, int, int] = (10, 20, 40, 40),
    ) -> None:
        self._scores = scores
        self._box = box

    def detect(self, image: object) -> object:
        origin_x, origin_y, width, height = self._box
        return SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=[SimpleNamespace(score=score)],
                    bounding_box=SimpleNamespace(
                        origin_x=origin_x, origin_y=origin_y, width=width, height=height
                    ),
                )
                for score in self._scores
            ]
        )


class TestDetectPerson:
    def test_returns_a_box_when_a_detection_meets_the_confidence_threshold(self) -> None:
        boxes = detect_person(_solid(size=160), FakeFaceDetector([0.9]))
        assert len(boxes) == 1
        assert boxes[0].confidence == 0.9

    def test_returns_empty_list_when_the_only_detection_is_below_the_confidence_threshold(
        self,
    ) -> None:
        assert detect_person(_solid(), FakeFaceDetector([0.1])) == []

    def test_returns_empty_list_with_no_detections_at_all(self) -> None:
        assert detect_person(_solid(), FakeFaceDetector([])) == []

    def test_returns_a_box_for_each_detection_meeting_the_threshold(self) -> None:
        boxes = detect_person(_solid(), FakeFaceDetector([0.1, 0.95]))
        assert len(boxes) == 1

    def test_bounding_box_is_normalized_to_image_size(self) -> None:
        # 160x160 Bild, Box bei (10, 20, 40, 40) Pixeln -> Zentrum bei (30/160, 40/160).
        boxes = detect_person(_solid(size=160), FakeFaceDetector([0.9], box=(10, 20, 40, 40)))
        box = boxes[0]
        assert box == FaceBoundingBox(
            x_center=30 / 160, y_center=40 / 160, width=40 / 160, height=40 / 160, confidence=0.9
        )


class FakeObjectDetector:
    """Faket die schmale Teilmenge der mediapipe-ObjectDetector-API, die detect_animals braucht -
    kein echtes .tflite-Modell in Tests (analog FakeFaceDetector). Jeder Eintrag in `detections`
    ist (category_name, score); nur die JEWEILS erste Kategorie pro Erkennung wird von
    detect_animals beruecksichtigt (siehe dortige Docstring-Begruendung)."""

    def __init__(
        self,
        detections: list[tuple[str, float]],
        box: tuple[int, int, int, int] = (10, 20, 40, 40),
    ) -> None:
        self._detections = detections
        self._box = box

    def detect(self, image: object) -> object:
        origin_x, origin_y, width, height = self._box
        return SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=[SimpleNamespace(category_name=name, score=score)],
                    bounding_box=SimpleNamespace(
                        origin_x=origin_x, origin_y=origin_y, width=width, height=height
                    ),
                )
                for name, score in self._detections
            ]
        )


class TestDetectAnimals:
    def test_returns_a_detection_for_an_animal_category_above_the_threshold(self) -> None:
        detections = detect_animals(_solid(size=160), FakeObjectDetector([("dog", 0.9)]))
        assert len(detections) == 1
        assert detections[0].category == "dog"
        assert detections[0].confidence == 0.9

    def test_returns_empty_list_when_no_detections_at_all(self) -> None:
        assert detect_animals(_solid(), FakeObjectDetector([])) == []

    def test_ignores_a_detection_with_an_empty_categories_list(self) -> None:
        # Degenerierter Grenzfall: das Modell liefert eine Erkennung (Bounding-Box), aber ohne
        # jede Kategorie-Zuordnung - darf nicht crashen (IndexError bei categories[0]).
        class NoCategoryDetector:
            def detect(self, image: object) -> object:
                return SimpleNamespace(
                    detections=[
                        SimpleNamespace(
                            categories=[],
                            bounding_box=SimpleNamespace(
                                origin_x=0, origin_y=0, width=10, height=10
                            ),
                        )
                    ]
                )

        assert detect_animals(_solid(), NoCategoryDetector()) == []

    def test_ignores_a_non_animal_category_even_with_high_confidence(self) -> None:
        # "car" ist eine reguläre COCO-Klasse, aber kein Tier - muss trotz hoher Konfidenz
        # herausgefiltert werden (Verifikation, dass tatsaechlich ANIMAL_CATEGORIES filtert).
        # Dieselbe Filterlogik trifft auch die dokumentierte, bewusst akzeptierte Luecke aus
        # ADR 0022 Punkt 1: COCO enthaelt keine Insekten-/Fisch-Klasse ueberhaupt, ein Foto eines
        # Schmetterlings oder Fischs kann mit diesem Modell strukturell nicht als "tier" erkannt
        # werden (kein eigener Testfall dafuer, analog zum unkalibrierten
        # SHARPNESS_REJECT_THRESHOLD-Kommentar in scoring.py - die Limitierung ist hier nur
        # referenziert, nicht separat assertiert).
        assert detect_animals(_solid(), FakeObjectDetector([("car", 0.95)])) == []

    def test_ignores_an_animal_detection_below_the_confidence_threshold(self) -> None:
        assert ANIMAL_DETECTION_CONFIDENCE_THRESHOLD == 0.5
        assert detect_animals(_solid(), FakeObjectDetector([("cat", 0.1)])) == []

    def test_bounding_box_is_normalized_to_image_size(self) -> None:
        detections = detect_animals(
            _solid(size=160), FakeObjectDetector([("horse", 0.8)], box=(10, 20, 40, 40))
        )
        assert detections[0] == AnimalDetection(
            category="horse",
            confidence=0.8,
            x_center=30 / 160,
            y_center=40 / 160,
            width=40 / 160,
            height=40 / 160,
        )

    def test_multiple_animal_detections_are_all_returned(self) -> None:
        # Aggregation/Auswahl EINES primaeren Tieres (z.B. fuer den Tier-Score) ist Aufgabe von
        # criteria.py::compute_tier_score, nicht von detect_animals selbst - detect_animals liefert
        # bewusst die vollstaendige Liste aller Treffer.
        detections = detect_animals(
            _solid(), FakeObjectDetector([("dog", 0.9), ("cat", 0.7)], box=(0, 0, 20, 20))
        )
        assert {d.category for d in detections} == {"dog", "cat"}

    def test_image_smaller_than_the_detection_box_does_not_crash(self) -> None:
        # Degenerierter Grenzfall analog test_image_smaller_than_the_tile_grid_does_not_crash oben
        # (Teststrategie-Abschnitt der Spec 0038) - kein Crash bei ungewoehnlichen
        # Groessenverhaeltnissen.
        detections = detect_animals(
            _solid(size=4), FakeObjectDetector([("dog", 0.9)], box=(0, 0, 2, 2))
        )
        assert len(detections) == 1
        assert 0.0 <= detections[0].x_center <= 1.0


class FakeSceneClassifier:
    """Faket die schmale Teilmenge der mediapipe-ImageClassifier-API, die classify_scene braucht -
    kein echtes .tflite-Modell in Tests. `categories` ist eine Liste von (category_name, score)."""

    def __init__(self, categories: list[tuple[str, float]]) -> None:
        self._categories = categories

    def classify(self, image: object) -> object:
        return SimpleNamespace(
            classifications=[
                SimpleNamespace(
                    categories=[
                        SimpleNamespace(category_name=name, score=score)
                        for name, score in self._categories
                    ]
                )
            ]
        )


class TestClassifyScene:
    def test_returns_a_label_above_the_confidence_threshold(self) -> None:
        labels = classify_scene(_solid(), FakeSceneClassifier([("church", 0.9)]))
        assert labels == [SceneLabel(category="church", confidence=0.9)]

    def test_ignores_a_label_below_the_confidence_threshold(self) -> None:
        assert SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD == 0.5
        assert classify_scene(_solid(), FakeSceneClassifier([("church", 0.1)])) == []

    def test_does_not_filter_by_architecture_allow_list_itself(self) -> None:
        # WICHTIG (Modul-Kommentar in classification.py): classify_scene liefert die ROHE
        # Modell-Ausgabe zurueck, auch fuer nicht-architekturbezogene Kategorien - die
        # Allow-Liste-Filterung passiert erst in criteria.py::compute_gebaeude_score.
        labels = classify_scene(_solid(), FakeSceneClassifier([("dog", 0.95)]))
        assert labels == [SceneLabel(category="dog", confidence=0.95)]

    def test_returns_all_labels_above_threshold_not_just_the_top_one(self) -> None:
        labels = classify_scene(
            _solid(), FakeSceneClassifier([("church", 0.9), ("castle", 0.7), ("dog", 0.1)])
        )
        assert {label.category for label in labels} == {"church", "castle"}

    def test_returns_empty_list_with_no_categories_at_all(self) -> None:
        assert classify_scene(_solid(), FakeSceneClassifier([])) == []
