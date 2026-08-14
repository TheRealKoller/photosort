from __future__ import annotations

import hashlib
import random
from types import SimpleNamespace

from PIL import Image, ImageDraw

from photosort.classification import (
    _FACE_DETECTOR_MODEL_PATH,
    FACE_DETECTOR_MODEL_SHA256,
    FaceBoundingBox,
    compute_uniform_area_fraction,
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
