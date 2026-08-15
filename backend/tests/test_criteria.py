from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from PIL import Image, ImageDraw

from photosort.classification import AnimalDetection, FaceBoundingBox
from photosort.criteria import (
    CATEGORY_DETAIL,
    CATEGORY_LANDSCAPE,
    CATEGORY_PEOPLE,
    CRITERIA_REGISTRY,
    compute_content_landscape,
    compute_content_people,
    compute_golden_ratio,
    compute_golden_ratio_score,
    compute_tier_score,
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

    def test_registry_contains_tier_and_goldener_schnitt_with_the_correct_source(self) -> None:
        # specs/features/0038: tier=local_ml (mediapipe-Modell), goldener_schnitt=local_heuristic
        # (reine Geometrie, kein eigenes Modell).
        assert CRITERIA_REGISTRY["tier"].source == CriterionSource.LOCAL_ML
        assert CRITERIA_REGISTRY["goldener_schnitt"].source == CriterionSource.LOCAL_HEURISTIC


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


@dataclass(frozen=True)
class _FakeSubjectBox:
    """Test-Double fuer ein beliebiges Subjekt mit Bounding-Box (strukturell kompatibel zu
    FaceBoundingBox/AnimalDetection - compute_golden_ratio_score braucht nur x_center/y_center/
    width/height, siehe SubjectBoxLike-Protocol in criteria.py). Steht hier fuer eine Tier-
    Erkennung, bevor AnimalDetection selbst existiert (Spec 0038, Reihenfolge "Goldener Schnitt
    vor Tier") - der Fallback-Pfad ist bewusst gegen den Protocol-Vertrag getestet, nicht gegen
    eine konkrete spaetere Implementierung, siehe test_criteria.py-Ergaenzung nach der
    Tier-Umsetzung fuer den Wiederverwendungsnachweis mit der echten AnimalDetection."""

    x_center: float
    y_center: float
    width: float
    height: float


def _face(x: float, y: float, width: float = 0.1, height: float = 0.1) -> FaceBoundingBox:
    return FaceBoundingBox(x_center=x, y_center=y, width=width, height=height, confidence=0.9)


class TestComputeGoldenRatioScore:
    def test_subject_near_a_third_point_scores_high(self) -> None:
        # Oberer linker Drittel-Schnittpunkt (1/3, 1/3).
        score = compute_golden_ratio_score([_face(1 / 3, 1 / 3)])
        assert score > 0.9

    def test_subject_exactly_centered_scores_noticeably_lower(self) -> None:
        centered = compute_golden_ratio_score([_face(0.5, 0.5)])
        near_third = compute_golden_ratio_score([_face(1 / 3, 1 / 3)])
        assert centered < near_third
        assert centered < 0.6

    def test_falls_back_to_the_largest_animal_box_when_no_face_was_detected(self) -> None:
        # Kein Gesicht, aber eine (hier: gefakte) Tier-Erkennung nah an einem Drittelpunkt -
        # Akzeptanzkriterium der Spec: der Fallback muss nachweislich greifen.
        score = compute_golden_ratio_score([], animals=[_FakeSubjectBox(2 / 3, 2 / 3, 0.2, 0.2)])
        assert score > 0.9

    def test_returns_a_low_documented_fallback_when_neither_face_nor_animal_detected(self) -> None:
        score = compute_golden_ratio_score([], animals=[])
        assert score == 0.0

    def test_multiple_faces_select_the_largest_by_area_not_the_first(self) -> None:
        # Erstes (kleines) Gesicht liegt exakt mittig (niedriger Score), zweites (grosses) Gesicht
        # liegt nah an einem Drittelpunkt (hoher Score) - die groessere Flaeche muss gewinnen.
        score = compute_golden_ratio_score(
            [_face(0.5, 0.5, width=0.05, height=0.05), _face(1 / 3, 1 / 3, width=0.3, height=0.3)]
        )
        assert score > 0.9

    def test_result_stays_within_zero_to_one_for_a_corner_subject(self) -> None:
        # Bildecke (0, 0) ist der Punkt mit dem groessten Abstand zu jedem Drittelpunkt - Grenzfall
        # fuer die Normierung, darf nicht unter 0 rutschen.
        score = compute_golden_ratio_score([_face(0.0, 0.0)])
        assert 0.0 <= score <= 1.0


def _animal(
    category: str, confidence: float, x: float = 0.5, y: float = 0.5, size: float = 0.2
) -> AnimalDetection:
    return AnimalDetection(
        category=category, confidence=confidence, x_center=x, y_center=y, width=size, height=size
    )


class TestComputeTierScore:
    def test_typical_pet_hit_scores_high(self) -> None:
        assert compute_tier_score([_animal("dog", 0.9)]) > 0.8

    def test_no_animal_scores_zero(self) -> None:
        assert compute_tier_score([]) == 0.0

    def test_multiple_animals_the_largest_by_area_wins_not_highest_confidence(self) -> None:
        # Aggregationsregel (Akzeptanzkriterium der Spec: "muss dokumentiert UND getestet sein,
        # keine stillschweigende Auswahl") - konsistent mit der Subjekt-Auswahl in
        # compute_golden_ratio_score: die groesste Bounding-Box-Flaeche gewinnt, nicht die
        # hoechste Konfidenz.
        small_high_confidence = _animal("cat", confidence=0.95, size=0.05)
        large_lower_confidence = _animal("dog", confidence=0.6, size=0.6)
        score = compute_tier_score([small_high_confidence, large_lower_confidence])
        assert score == 0.6


class SpyFaceDetector:
    """Zaehlt Aufrufe von detect() - Wiederverwendungsnachweis fuer compute_golden_ratio
    (Akzeptanzkriterium der Spec: "Spy/Aufrufzaehler statt Reimplementierung")."""

    def __init__(self) -> None:
        self.call_count = 0

    def detect(self, image: object) -> object:
        self.call_count += 1
        return SimpleNamespace(detections=[])


class SpyAnimalDetector:
    def __init__(self) -> None:
        self.call_count = 0

    def detect(self, image: object) -> object:
        self.call_count += 1
        return SimpleNamespace(detections=[])


class TestComputeGoldenRatioReusesDetection:
    def test_calls_detect_person_and_detect_animals_instead_of_reimplementing(self) -> None:
        face_detector = SpyFaceDetector()
        animal_detector = SpyAnimalDetector()

        compute_golden_ratio(_solid(), face_detector, animal_detector)

        assert face_detector.call_count == 1
        assert animal_detector.call_count == 1


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
