from __future__ import annotations

import random
from types import SimpleNamespace

from PIL import Image, ImageDraw

from photosort.classification import (
    CategoryCandidate,
    classify_category,
    compute_uniform_area_fraction,
    detect_person,
    select_top_n_with_category_mix,
)
from photosort.models import PhotoCategory


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


class TestComputeUniformAreaFraction:
    def test_uniform_image_has_fraction_near_one(self) -> None:
        assert compute_uniform_area_fraction(_solid()) > 0.9

    def test_noisy_image_has_fraction_near_zero(self) -> None:
        assert compute_uniform_area_fraction(_noisy()) < 0.1

    def test_half_uniform_half_noisy_image_is_about_half(self) -> None:
        fraction = compute_uniform_area_fraction(_half_uniform_half_noisy())
        assert 0.35 <= fraction <= 0.65


class FakeFaceDetector:
    """Faket die schmale Teilmenge der mediapipe-FaceDetector-API, die detect_person braucht -
    kein echtes .tflite-Modell in Tests (Teststrategie-Abschnitt der Spec)."""

    def __init__(self, scores: list[float]) -> None:
        self._scores = scores

    def detect(self, image: object) -> object:
        return SimpleNamespace(
            detections=[
                SimpleNamespace(categories=[SimpleNamespace(score=score)])
                for score in self._scores
            ]
        )


class TestDetectPerson:
    def test_returns_true_when_a_detection_meets_the_confidence_threshold(self) -> None:
        assert detect_person(_solid(), FakeFaceDetector([0.9])) is True

    def test_returns_false_when_the_only_detection_is_below_the_confidence_threshold(
        self,
    ) -> None:
        assert detect_person(_solid(), FakeFaceDetector([0.1])) is False

    def test_returns_false_with_no_detections_at_all(self) -> None:
        assert detect_person(_solid(), FakeFaceDetector([])) is False

    def test_returns_true_if_any_of_several_detections_meets_the_threshold(self) -> None:
        assert detect_person(_solid(), FakeFaceDetector([0.1, 0.95])) is True


class TestClassifyCategory:
    def test_detected_face_wins_over_everything_else(self) -> None:
        category = classify_category(_solid(), None, detect_person=lambda image, detector: True)
        assert category == PhotoCategory.PEOPLE

    def test_uniform_image_without_a_face_is_landscape(self) -> None:
        category = classify_category(_solid(), None, detect_person=lambda image, detector: False)
        assert category == PhotoCategory.LANDSCAPE

    def test_textured_image_without_a_face_falls_back_to_detail(self) -> None:
        category = classify_category(_noisy(), None, detect_person=lambda image, detector: False)
        assert category == PhotoCategory.DETAIL


class TestSelectTopNWithCategoryMix:
    def test_distributes_via_divmod_across_three_categories_in_fixed_order(self) -> None:
        candidates = [
            CategoryCandidate(1, PhotoCategory.LANDSCAPE, 9.0),
            CategoryCandidate(2, PhotoCategory.LANDSCAPE, 8.0),
            CategoryCandidate(3, PhotoCategory.DETAIL, 9.0),
            CategoryCandidate(4, PhotoCategory.DETAIL, 8.0),
            CategoryCandidate(5, PhotoCategory.PEOPLE, 9.0),
            CategoryCandidate(6, PhotoCategory.PEOPLE, 8.0),
        ]
        # divmod(4, 3) = (1, 1) -> LANDSCAPE (erste in fester Reihenfolge) bekommt den einen
        # Rest-Sitz zusaetzlich: LANDSCAPE=2, DETAIL=1, PEOPLE=1.
        selected = select_top_n_with_category_mix(candidates, 4)
        assert selected == sorted([1, 2, 3, 5])

    def test_tie_break_picks_the_lower_photo_id(self) -> None:
        candidates = [
            CategoryCandidate(2, PhotoCategory.LANDSCAPE, 5.0),
            CategoryCandidate(1, PhotoCategory.LANDSCAPE, 5.0),
        ]
        assert select_top_n_with_category_mix(candidates, 1) == [1]

    def test_only_one_category_present_gets_the_full_quota(self) -> None:
        candidates = [
            CategoryCandidate(i, PhotoCategory.DETAIL, float(i)) for i in range(1, 6)
        ]
        assert select_top_n_with_category_mix(candidates, 3) == [3, 4, 5]

    def test_category_with_too_few_photos_is_not_backfilled_from_other_categories(self) -> None:
        # Kernfall der Spec: divmod(6, 3) = (2, 0) -> Quote 2 je Kategorie. LANDSCAPE hat nur 1
        # Foto -> nur 1 wird gewaehlt, KEIN Nachziehen aus DETAIL/PEOPLE trotz dort vorhandener
        # weiterer Kandidaten - die Gesamttrefferzahl bleibt unter N.
        candidates = [
            CategoryCandidate(1, PhotoCategory.LANDSCAPE, 9.0),
            CategoryCandidate(2, PhotoCategory.DETAIL, 9.0),
            CategoryCandidate(3, PhotoCategory.DETAIL, 8.0),
            CategoryCandidate(4, PhotoCategory.DETAIL, 7.0),
            CategoryCandidate(5, PhotoCategory.PEOPLE, 9.0),
            CategoryCandidate(6, PhotoCategory.PEOPLE, 8.0),
        ]
        selected = select_top_n_with_category_mix(candidates, 6)
        assert selected == sorted([1, 2, 3, 5, 6])

    def test_n_greater_than_cluster_size_returns_all_available_without_padding(self) -> None:
        candidates = [CategoryCandidate(1, PhotoCategory.LANDSCAPE, 5.0)]
        assert select_top_n_with_category_mix(candidates, 10) == [1]

    def test_single_photo_cluster(self) -> None:
        candidates = [CategoryCandidate(42, PhotoCategory.PEOPLE, 1.0)]
        assert select_top_n_with_category_mix(candidates, 3) == [42]

    def test_empty_candidates_returns_empty_list(self) -> None:
        assert select_top_n_with_category_mix([], 3) == []
