from __future__ import annotations

from types import SimpleNamespace

from PIL import Image, ImageDraw

from photosort.criteria import (
    CATEGORY_DETAIL,
    CATEGORY_LANDSCAPE,
    CATEGORY_PEOPLE,
    CRITERIA_REGISTRY,
    compute_content_landscape,
    compute_content_people,
    derive_category_key,
    normalize_exposure,
    normalize_sharpness,
)
from photosort.models import CriterionSource


def _solid(color: tuple[int, int, int] = (120, 120, 120), size: int = 160) -> Image.Image:
    return Image.new("RGB", (size, size), color=color)


def _textured(size: int = 160) -> Image.Image:
    image = Image.new("RGB", (size, size), color=(30, 60, 120))
    draw = ImageDraw.Draw(image)
    for offset in range(0, size, 8):
        draw.line((offset, 0, size - offset, size), fill=(220, 180, 90), width=2)
    return image


class FakeFaceDetector:
    def __init__(self, has_face: bool) -> None:
        self._has_face = has_face

    def detect(self, image: object) -> object:
        if not self._has_face:
            return SimpleNamespace(detections=[])
        return SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=[SimpleNamespace(score=0.9)],
                    bounding_box=SimpleNamespace(origin_x=1, origin_y=1, width=10, height=10),
                )
            ]
        )


class TestCriteriaRegistry:
    def test_registry_contains_the_four_mvp_criteria_with_a_source(self) -> None:
        # Akzeptanzkriterium der Spec: mindestens sharpness/exposure + zwei Inhalts-Kriterien
        # tatsaechlich registriert - kein Nachweis einer vollstaendigen Kriterien-Liste noetig.
        assert set(CRITERIA_REGISTRY) >= {
            "sharpness",
            "exposure",
            "content_people",
            "content_landscape",
        }
        for definition in CRITERIA_REGISTRY.values():
            assert isinstance(definition.source, CriterionSource)
            assert definition.display_name


class TestNormalizeSharpness:
    def test_zero_stays_zero(self) -> None:
        assert normalize_sharpness(0.0) == 0.0

    def test_value_within_range_scales_linearly(self) -> None:
        assert 0.0 < normalize_sharpness(100.0) < 1.0

    def test_value_above_ceiling_is_clamped_to_one(self) -> None:
        assert normalize_sharpness(1_000_000.0) == 1.0


class TestNormalizeExposure:
    def test_perfectly_exposed_yields_one(self) -> None:
        assert normalize_exposure(0.0) == 1.0

    def test_fully_clipped_yields_zero(self) -> None:
        assert normalize_exposure(1.0) == 0.0

    def test_higher_raw_exposure_yields_lower_score(self) -> None:
        assert normalize_exposure(0.8) < normalize_exposure(0.2)


class TestComputeContentPeople:
    def test_returns_one_when_a_face_is_detected(self) -> None:
        assert compute_content_people(_solid(), FakeFaceDetector(True)) == 1.0

    def test_returns_zero_when_no_face_is_detected(self) -> None:
        assert compute_content_people(_solid(), FakeFaceDetector(False)) == 0.0


class TestComputeContentLandscape:
    def test_uniform_image_scores_high(self) -> None:
        assert compute_content_landscape(_solid()) > 0.9

    def test_textured_image_scores_low(self) -> None:
        assert compute_content_landscape(_textured()) < 0.3


class TestDeriveCategoryKey:
    def test_people_wins_over_everything_else(self) -> None:
        values = {"content_people": 1.0, "content_landscape": 1.0}
        assert derive_category_key(values) == CATEGORY_PEOPLE

    def test_uniform_without_people_is_landscape(self) -> None:
        values = {"content_people": 0.0, "content_landscape": 0.9}
        assert derive_category_key(values) == CATEGORY_LANDSCAPE

    def test_textured_without_people_falls_back_to_detail(self) -> None:
        values = {"content_people": 0.0, "content_landscape": 0.1}
        assert derive_category_key(values) == CATEGORY_DETAIL

    def test_missing_criteria_falls_back_to_detail_without_crashing(self) -> None:
        # Best-effort-Fall: beide Inhalts-Kriterien fuer dieses Foto konnten nicht berechnet
        # werden (z.B. fehlende display-Cache-Datei) - die Kette darf nicht crashen.
        assert derive_category_key({}) == CATEGORY_DETAIL
