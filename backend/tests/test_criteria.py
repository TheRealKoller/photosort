from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from photosort.classification import (
    ANIMAL_CATEGORIES,
    SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD,
    SCENE_LABEL_MIN_CONFIDENCE,
    FaceBoundingBox,
    FaceOrientation,
    ObjectDetection,
    SceneLabel,
)
from photosort.criteria import (
    ARCHITECTURE_CATEGORIES,
    CRITERIA_REGISTRY,
    FOOD_CATEGORIES,
    FREIRAUM_YAW_DEADZONE_DEGREES,
    LANDSCAPE_SCENE_CATEGORIES,
    LANDSCHAFT_LABEL_MIN_CONFIDENCE,
    VEHICLE_CATEGORIES,
    CriterionDefinition,
    animal_detections,
    compute_content_landscape,
    compute_content_people,
    compute_essen_trinken_score,
    compute_fahrzeug_score,
    compute_freiraum_score,
    compute_gebaeude_score,
    compute_golden_ratio_score,
    compute_landmark_score,
    compute_landschaft_score,
    compute_symmetrie_score,
    compute_tier_score,
    is_landmark_candidate,
    normalize_exposure,
    normalize_sharpness,
)
from photosort.landmark import LandmarkDetection
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

    def test_registry_contains_gebaeude_with_the_correct_source(self) -> None:
        assert CRITERIA_REGISTRY["gebaeude"].source == CriterionSource.LOCAL_ML

    def test_registry_contains_aesthetics_with_the_correct_source(self) -> None:
        assert CRITERIA_REGISTRY["aesthetics"].source == CriterionSource.LOCAL_ML

    def test_registry_contains_the_three_composition_criteria_with_the_correct_source(
        self,
    ) -> None:
        # specs/features/0048: symmetrie/horizont = local_heuristic (keine trainierten Gewichte),
        # freiraum = local_ml (mediapipe FaceLandmarker) - alle drei category_eligible=False.
        assert CRITERIA_REGISTRY["symmetrie"].source == CriterionSource.LOCAL_HEURISTIC
        assert CRITERIA_REGISTRY["horizont"].source == CriterionSource.LOCAL_HEURISTIC
        assert CRITERIA_REGISTRY["freiraum"].source == CriterionSource.LOCAL_ML
        for key in ("symmetrie", "horizont", "freiraum"):
            assert CRITERIA_REGISTRY[key].category_eligible is False
            assert CRITERIA_REGISTRY[key].category_presence_threshold is None

    def test_category_eligible_and_presence_threshold_are_set_together_or_not_at_all(
        self,
    ) -> None:
        # Registry-Invariante (Akzeptanzkriterium der Spec 0045): category_eligible == (threshold
        # is not None), fuer JEDEN Eintrag der Registry - kein Eintrag darf nur eines von beiden
        # setzen.
        for key, definition in CRITERIA_REGISTRY.items():
            assert definition.category_eligible == (
                definition.category_presence_threshold is not None
            ), f"{key}: category_eligible und category_presence_threshold widersprechen sich"

    def test_exactly_these_seven_content_criteria_are_category_eligible(self) -> None:
        # Akzeptanzkriterium der Spec 0045, erweitert um landmark (specs/features/0047) und seit
        # specs/features/0217/ADR 0047 Punkt 1 mit `landschaft` STATT `content_landscape`.
        # specs/features/0289-feste-kategorien.md, Umsetzungsschritt 2: zusaetzlich `fahrzeug` und
        # `essen_trinken` - beide aus der COCO-Detektorausgabe, die bisher berechnet und verworfen
        # wurde (keine zusaetzliche Laufzeit, keine Cloud-Kosten). Bewusst weiterhin eine
        # MENGEN-Assertion (nicht auf einen Anzahl-Vergleich abgeschwaecht).
        eligible = {key for key, d in CRITERIA_REGISTRY.items() if d.category_eligible}
        assert eligible == {
            "content_people",
            "landschaft",
            "tier",
            "gebaeude",
            "landmark",
            "fahrzeug",
            "essen_trinken",
        }

    def test_registry_contains_fahrzeug_and_essen_trinken_with_the_correct_source(self) -> None:
        # specs/features/0289-feste-kategorien.md, Umsetzungsschritt 2: Presence-Schwelle 0.01 wie
        # tier/gebaeude/landschaft - reine "nichts erkannt vs. irgendetwas erkannt"-Trennung, keine
        # zweite Konfidenzkalibrierung.
        for key, display_name in (
            ("fahrzeug", "Fahrzeug erkannt"),
            ("essen_trinken", "Essen erkannt"),
        ):
            definition = CRITERIA_REGISTRY[key]
            assert definition.display_name == display_name
            assert definition.source == CriterionSource.LOCAL_ML
            assert definition.category_eligible is True
            assert definition.category_presence_threshold == 0.01

    def test_registry_contains_landschaft_with_the_correct_source_and_threshold(self) -> None:
        # specs/features/0217, ADR 0047 Punkt 1: neues, echtes Inhalts-Kriterium aus derselben
        # Szenen-Klassifikation wie gebaeude - Presence-Schwelle 0.01 ist wie bei tier/gebaeude
        # eine reine "nichts erkannt vs. irgendetwas erkannt"-Trennung, keine zweite
        # Konfidenzkalibrierung.
        definition = CRITERIA_REGISTRY["landschaft"]
        assert definition.display_name == "Landschaft erkannt"
        assert definition.source == CriterionSource.LOCAL_ML
        assert definition.category_eligible is True
        assert definition.category_presence_threshold == 0.01

    def test_content_landscape_is_a_pure_ranking_signal_without_category_eligibility(
        self,
    ) -> None:
        # ADR 0047 Punkt 1: compute_uniform_area_fraction misst Texturarmut, keine Landschaft -
        # das Kriterium bleibt als Ranking-Signal erhalten, darf aber keine Kategorie mehr bilden.
        # Der Anzeigename behauptet entsprechend keine Inhaltsaussage mehr.
        definition = CRITERIA_REGISTRY["content_landscape"]
        assert definition.display_name == "Flächigkeit"
        assert definition.category_eligible is False
        assert definition.category_presence_threshold is None

    def test_category_specificity_is_removed_from_the_definition(self) -> None:
        """specs/features/0289-feste-kategorien.md, Teststrategie 2 Punkt 7: `category_specificity`
        ist RESTLOS entfernt - die Vorrangentscheidung liegt seit dieser Spec ausschliesslich in
        `categories.py::CATEGORY_REGISTRY.precedence`, ein zweites, konkurrierendes
        Prioritaetsattribut an den Kriterien waere genau die Doppelpflege, die ADR 0049 abschafft.
        Feld-Set-Assertion statt eines blossen `hasattr`-Checks, damit auch ein versehentlich neu
        eingefuehrtes Prioritaetsfeld auffaellt."""
        assert {field.name for field in dataclasses.fields(CriterionDefinition)} == {
            "key",
            "display_name",
            "source",
            "category_eligible",
            "category_presence_threshold",
        }

    def test_registry_contains_landmark_with_the_correct_source_and_threshold(self) -> None:
        # specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR
        # decisions/0025-cloud-landmark-erkennung.md Punkt 2: erste tatsaechlich produktiv
        # geschriebene CriterionSource.CLOUD-Zeile.
        definition = CRITERIA_REGISTRY["landmark"]
        assert definition.display_name == "Sehenswürdigkeit"
        assert definition.source == CriterionSource.CLOUD
        assert definition.category_eligible is True
        assert definition.category_presence_threshold == 0.5

    def test_quality_criteria_are_never_category_eligible(self) -> None:
        for key in ("sharpness", "exposure", "goldener_schnitt", "aesthetics"):
            assert CRITERIA_REGISTRY[key].category_eligible is False
            assert CRITERIA_REGISTRY[key].category_presence_threshold is None


class TestComputeSymmetrieScore:
    def test_delegates_to_classification_compute_symmetry_score(self) -> None:
        # Reiner Namens-/Modul-Wrapper (Betroffene-Dateien-Abschnitt der Spec 0048:
        # "compute_symmetrie_score-Delegate"), analog compute_content_landscape ->
        # compute_uniform_area_fraction - kein eigener Algorithmus hier, nur derselbe Wert.
        assert compute_symmetrie_score(_solid()) == 1.0


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
    FaceBoundingBox/ObjectDetection - compute_golden_ratio_score braucht nur x_center/y_center/
    width/height, siehe SubjectBoxLike-Protocol in criteria.py). Steht hier fuer eine Tier-
    Erkennung, bevor ObjectDetection selbst existierte (Spec 0038, Reihenfolge "Goldener Schnitt
    vor Tier") - der Fallback-Pfad ist bewusst gegen den Protocol-Vertrag getestet, nicht gegen
    eine konkrete spaetere Implementierung, siehe test_criteria.py-Ergaenzung nach der
    Tier-Umsetzung fuer den Wiederverwendungsnachweis mit der echten ObjectDetection."""

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


class TestComputeGoldenRatioScoreBehaviourPreservation:
    """specs/features/0289-feste-kategorien.md, Teststrategie 4 - ausdruecklich testpflichtiger
    VERHALTENSERHALT: `compute_golden_ratio_score` bekommt weiterhin ausschliesslich die
    Tier-Erkennungen als Subjekt-Kandidaten. Die geweitete `detect_objects`-Ausgabe darf NICHT in
    diesen unbeteiligten Konsumenten durchschlagen (kein Auto/Teller als Kompositions-Subjekt)."""

    def test_a_single_car_and_no_animal_scores_like_no_detection_at_all(self) -> None:
        with_car = compute_golden_ratio_score(
            [], animals=animal_detections([_detection("car", 0.95, x=1 / 3, y=1 / 3, size=0.5)])
        )
        without_anything = compute_golden_ratio_score([], animals=[])
        assert with_car == without_anything == 0.0

    def test_a_small_animal_wins_over_a_large_car(self) -> None:
        detections = [
            _detection("car", 0.99, x=0.5, y=0.5, size=0.9),
            _detection("dog", 0.6, x=1 / 3, y=1 / 3, size=0.1),
        ]
        score = compute_golden_ratio_score([], animals=animal_detections(detections))
        assert score > 0.9


def _detection(
    category: str, confidence: float, x: float = 0.5, y: float = 0.5, size: float = 0.2
) -> ObjectDetection:
    return ObjectDetection(
        category=category, confidence=confidence, x_center=x, y_center=y, width=size, height=size
    )


class TestAnimalDetections:
    """specs/features/0289-feste-kategorien.md, Teststrategie 4: der Verhaltenserhalt haengt an
    einer BENANNTEN Funktion, nicht nur am Ergebnis eines Konsumenten."""

    def test_filters_to_animal_categories_preserving_order(self) -> None:
        detections = [
            _detection("car", 0.9),
            _detection("dog", 0.8),
            _detection("pizza", 0.7),
            _detection("cat", 0.6),
        ]
        assert [d.category for d in animal_detections(detections)] == ["dog", "cat"]

    def test_empty_input_yields_empty_output(self) -> None:
        assert animal_detections([]) == []

    def test_only_non_animals_yields_empty_output(self) -> None:
        assert animal_detections([_detection("car", 0.9), _detection("laptop", 0.8)]) == []

    def test_every_animal_allow_list_entry_passes_the_filter(self) -> None:
        detections = [_detection(category, 0.9) for category in sorted(ANIMAL_CATEGORIES)]
        assert len(animal_detections(detections)) == len(ANIMAL_CATEGORIES)


class TestComputeTierScore:
    def test_typical_pet_hit_scores_high(self) -> None:
        assert compute_tier_score([_detection("dog", 0.9)]) > 0.8

    def test_no_animal_scores_zero(self) -> None:
        assert compute_tier_score([]) == 0.0

    def test_only_non_animals_score_zero_not_the_cars_confidence(self) -> None:
        """Der eigentliche Regressionsschutz der Spec-0289-Aenderung (Teststrategie 4):
        `compute_tier_score` bekommt seit der Verallgemeinerung detect_animals -> detect_objects
        die UNGEFILTERTE Objektliste und muss selbst auf ANIMAL_CATEGORIES filtern - sonst wuerde
        die Konfidenz eines Autos zum Tier-Score."""
        assert compute_tier_score([_detection("car", 0.95), _detection("pizza", 0.9)]) == 0.0

    def test_the_largest_object_overall_does_not_win_if_it_is_not_an_animal(self) -> None:
        # Gemischte Liste, das flaechengroesste Objekt ist ein Nicht-Tier - der Score stammt vom
        # flaechengroessten TIER, nicht vom groessten Objekt insgesamt.
        score = compute_tier_score(
            [
                _detection("car", confidence=0.99, size=0.9),
                _detection("dog", confidence=0.6, size=0.3),
                _detection("cat", confidence=0.8, size=0.1),
            ]
        )
        assert score == 0.6

    def test_multiple_animals_the_largest_by_area_wins_not_highest_confidence(self) -> None:
        # Aggregationsregel (Akzeptanzkriterium der Spec: "muss dokumentiert UND getestet sein,
        # keine stillschweigende Auswahl") - konsistent mit der Subjekt-Auswahl in
        # compute_golden_ratio_score: die groesste Bounding-Box-Flaeche gewinnt, nicht die
        # hoechste Konfidenz.
        small_high_confidence = _detection("cat", confidence=0.95, size=0.05)
        large_lower_confidence = _detection("dog", confidence=0.6, size=0.6)
        score = compute_tier_score([small_high_confidence, large_lower_confidence])
        assert score == 0.6


class TestComputeFahrzeugScore:
    """Muster wie compute_gebaeude_score: Allow-Listen-gefiltertes Konfidenz-Maximum
    (specs/features/0289-feste-kategorien.md, Umsetzungsschritt 2)."""

    def test_allow_listed_class_scores_its_confidence(self) -> None:
        assert compute_fahrzeug_score([_detection("car", 0.87)]) == 0.87

    def test_non_allow_listed_class_scores_zero_despite_high_confidence(self) -> None:
        assert compute_fahrzeug_score([_detection("dog", 0.99)]) == 0.0

    def test_several_hits_yield_the_maximum(self) -> None:
        score = compute_fahrzeug_score(
            [_detection("bicycle", 0.6), _detection("train", 0.9), _detection("boat", 0.7)]
        )
        assert score == 0.9

    def test_empty_list_scores_zero(self) -> None:
        assert compute_fahrzeug_score([]) == 0.0

    def test_a_weak_allow_listed_hit_does_not_mask_a_strong_one(self) -> None:
        score = compute_fahrzeug_score(
            [_detection("car", 0.51), _detection("truck", 0.95), _detection("person", 0.99)]
        )
        assert score == 0.95


class TestComputeEssenTrinkenScore:
    def test_allow_listed_class_scores_its_confidence(self) -> None:
        assert compute_essen_trinken_score([_detection("pizza", 0.82)]) == 0.82

    def test_non_allow_listed_class_scores_zero_despite_high_confidence(self) -> None:
        assert compute_essen_trinken_score([_detection("car", 0.99)]) == 0.0

    @pytest.mark.parametrize("category", ["cup", "bottle", "bowl", "fork", "knife", "spoon"])
    def test_deliberately_excluded_tableware_classes_score_zero(self, category: str) -> None:
        """Einzige automatisierte Absicherung der in Umsetzungsschritt 2 begruendeten
        Listen-Auswahl: Geschirr/Besteck kommt zu haeufig beilaeufig in Raum-/Personenszenen vor
        und wuerde `essen_trinken` sonst massenhaft falsch ausloesen."""
        assert category not in FOOD_CATEGORIES
        assert compute_essen_trinken_score([_detection(category, 0.99)]) == 0.0

    def test_several_hits_yield_the_maximum(self) -> None:
        score = compute_essen_trinken_score(
            [_detection("apple", 0.6), _detection("cake", 0.93), _detection("banana", 0.7)]
        )
        assert score == 0.93

    def test_empty_list_scores_zero(self) -> None:
        assert compute_essen_trinken_score([]) == 0.0


class TestObjectAllowLists:
    def test_vehicle_and_food_allow_lists_do_not_overlap(self) -> None:
        assert VEHICLE_CATEGORIES & FOOD_CATEGORIES == frozenset()

    def test_neither_allow_list_overlaps_the_animal_allow_list(self) -> None:
        assert VEHICLE_CATEGORIES & ANIMAL_CATEGORIES == frozenset()
        assert FOOD_CATEGORIES & ANIMAL_CATEGORIES == frozenset()


class TestComputeFreiraumScore:
    def test_no_face_detected_scores_zero(self) -> None:
        # AK der Spec 0048: "Kein Gesicht erkannt -> score == 0.0" (niedriger, NICHT neutraler
        # Fallback - analog goldener_schnitt: kein Subjekt = kein Kompositionswert).
        assert compute_freiraum_score(None) == 0.0

    def test_yaw_within_the_deadzone_scores_the_neutral_fallback(self) -> None:
        # AK: "|Yaw| < FREIRAUM_YAW_DEADZONE_DEGREES -> score == 0.5" (kein klares
        # Richtungssignal bei einem nahezu frontalen Blick).
        orientation = FaceOrientation(yaw_degrees=5.0, min_x=0.2, max_x=0.6)
        assert compute_freiraum_score(orientation) == 0.5
        orientation_negative = FaceOrientation(yaw_degrees=-5.0, min_x=0.2, max_x=0.6)
        assert compute_freiraum_score(orientation_negative) == 0.5

    def test_yaw_exactly_at_the_deadzone_boundary_counts_as_outside_not_neutral(self) -> None:
        # AK der Spec 0048: "Yaw exakt an der Deadzone-Grenze zaehlt als AUSSERHALB (`<`, nicht
        # `<=`) -> gerichteter Score, nicht 0.5" - Grenzfall explizit gepinnt.
        assert FREIRAUM_YAW_DEADZONE_DEGREES == 10.0
        orientation = FaceOrientation(yaw_degrees=10.0, min_x=0.1, max_x=0.5)
        score = compute_freiraum_score(orientation)
        assert score != 0.5
        assert score == pytest.approx(0.5 / 0.6)  # looking_space=1-0.5=0.5, opposite=min_x=0.1

    def test_positive_yaw_looks_toward_the_right_edge_of_the_frame(self) -> None:
        # Gesicht weit links im Bild, nach rechts (steigendes x) gedreht - viel Freiraum in
        # Blickrichtung -> hoher Score.
        orientation = FaceOrientation(yaw_degrees=20.0, min_x=0.05, max_x=0.15)
        assert compute_freiraum_score(orientation) == pytest.approx(0.85 / 0.9)

    def test_negative_yaw_looks_toward_the_left_edge_of_the_frame(self) -> None:
        # Gesicht weit rechts im Bild, nach links (fallendes x) gedreht - viel Freiraum in
        # Blickrichtung -> hoher Score. Spiegelbildlich zum vorigen Test (looking_space/
        # opposite_space vertauscht).
        orientation = FaceOrientation(yaw_degrees=-20.0, min_x=0.85, max_x=0.95)
        assert compute_freiraum_score(orientation) == pytest.approx(0.85 / 0.9)

    def test_subject_crowded_against_the_edge_it_looks_toward_scores_low(self) -> None:
        # Gesicht am Bildrand IN Blickrichtung gedraengt (typischer Kompositionsfehler) - wenig
        # Freiraum vor dem Blick -> niedriger Score.
        orientation = FaceOrientation(yaw_degrees=20.0, min_x=0.7, max_x=0.95)
        assert compute_freiraum_score(orientation) == pytest.approx(0.05 / 0.75)

    def test_face_filling_the_entire_image_width_falls_back_to_the_neutral_value(self) -> None:
        # AK der Spec 0048: "looking_space + opposite_space == 0 (Gesicht fuellt die volle
        # Bildbreite) -> score == 0.5" - 0-Schutz, gleiche Argumentationsklasse wie die
        # Yaw-Deadzone.
        orientation = FaceOrientation(yaw_degrees=30.0, min_x=0.0, max_x=1.0)
        assert compute_freiraum_score(orientation) == 0.5

    def test_result_always_stays_within_zero_and_one(self) -> None:
        orientation = FaceOrientation(yaw_degrees=45.0, min_x=0.0, max_x=0.5)
        score = compute_freiraum_score(orientation)
        assert 0.0 <= score <= 1.0


class TestComputeGebaeudeScore:
    def test_allow_listed_category_scores_high(self) -> None:
        score = compute_gebaeude_score([SceneLabel(category="church", confidence=0.9)])
        assert score == 0.9

    def test_non_allow_listed_category_scores_zero_despite_high_confidence(self) -> None:
        # Akzeptanzkriterium der Spec: Nachweis, dass tatsaechlich die Allow-Liste filtert und
        # nicht nur die rohe Modell-Konfidenz durchgereicht wird.
        score = compute_gebaeude_score([SceneLabel(category="dog", confidence=0.95)])
        assert score == 0.0

    def test_no_labels_at_all_scores_zero(self) -> None:
        assert compute_gebaeude_score([]) == 0.0

    def test_picks_the_highest_confidence_allow_listed_label_among_several(self) -> None:
        labels = [
            SceneLabel(category="dog", confidence=0.99),  # nicht in der Allow-Liste
            SceneLabel(category="castle", confidence=0.6),
            SceneLabel(category="church", confidence=0.8),
        ]
        assert compute_gebaeude_score(labels) == 0.8

    def test_allow_listed_label_between_the_old_and_new_lower_bound_still_scores_zero(
        self,
    ) -> None:
        # Nicht-Regressions-Pflicht (specs/features/0217 AK2, Testkonzept-Regel 1 zu ADR 0047):
        # classify_scene liefert seit dieser Spec bereits ab SCENE_LABEL_MIN_CONFIDENCE (0.2) -
        # compute_gebaeude_score muss die alte, inhaltliche Schwelle (0.5) deshalb SELBST
        # durchsetzen, sonst verschiebt eine reine Konstanten-Aenderung stillschweigend das
        # Verhalten dieses unbeteiligten Kriteriums.
        assert SCENE_LABEL_MIN_CONFIDENCE < 0.3 < SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD
        assert compute_gebaeude_score([SceneLabel(category="church", confidence=0.3)]) == 0.0

    def test_allow_listed_label_exactly_at_the_old_threshold_still_hits(self) -> None:
        # Grenzfall exakt AUF der alten Schwelle bleibt inklusiv (`>=`), wie bisher.
        assert compute_gebaeude_score(
            [SceneLabel(category="church", confidence=0.5)]
        ) == 0.5

    def test_a_weak_allow_listed_label_does_not_mask_a_strong_one(self) -> None:
        labels = [
            SceneLabel(category="church", confidence=0.3),  # unter der Gebaeude-Schwelle
            SceneLabel(category="castle", confidence=0.7),
        ]
        assert compute_gebaeude_score(labels) == 0.7


class TestComputeLandschaftScore:
    """specs/features/0217, ADR decisions/0047 Punkt 1: echte, inhaltsbasierte Landschafts-
    Erkennung aus derselben (bereits berechneten) Szenen-Klassifikation wie gebaeude - exakt das
    Muster von compute_gebaeude_score/ARCHITECTURE_CATEGORIES, nur mit eigener Allow-Liste und
    eigener, niedrigerer Konfidenzschwelle."""

    def test_allow_listed_label_scores_its_confidence(self) -> None:
        assert compute_landschaft_score([SceneLabel(category="valley", confidence=0.8)]) == 0.8

    def test_non_allow_listed_label_scores_zero_despite_high_confidence(self) -> None:
        # Kernaussage der Story: ein texturarmes/unspezifisches Foto ohne Landschaftsmotiv bekommt
        # keinen Landschafts-Score, egal wie sicher das Modell bei etwas anderem ist.
        assert compute_landschaft_score([SceneLabel(category="dog", confidence=0.99)]) == 0.0

    def test_no_labels_at_all_scores_zero(self) -> None:
        assert compute_landschaft_score([]) == 0.0

    def test_picks_the_highest_confidence_allow_listed_label_among_several(self) -> None:
        labels = [
            SceneLabel(category="dog", confidence=0.99),  # nicht in der Allow-Liste
            SceneLabel(category="valley", confidence=0.4),
            SceneLabel(category="seashore", confidence=0.7),
        ]
        assert compute_landschaft_score(labels) == 0.7

    def test_label_just_below_the_landschaft_threshold_scores_zero(self) -> None:
        assert LANDSCHAFT_LABEL_MIN_CONFIDENCE == 0.25
        assert compute_landschaft_score([SceneLabel(category="alp", confidence=0.24)]) == 0.0

    def test_label_exactly_at_the_landschaft_threshold_hits_inclusive(self) -> None:
        assert compute_landschaft_score([SceneLabel(category="alp", confidence=0.25)]) == 0.25

    def test_label_just_above_the_landschaft_threshold_hits(self) -> None:
        assert compute_landschaft_score([SceneLabel(category="alp", confidence=0.26)]) == 0.26

    def test_a_weak_allow_listed_label_does_not_mask_a_strong_one(self) -> None:
        labels = [
            SceneLabel(category="alp", confidence=0.1),  # unter der Landschafts-Schwelle
            SceneLabel(category="volcano", confidence=0.6),
        ]
        assert compute_landschaft_score(labels) == 0.6

    def test_allow_list_and_architecture_allow_list_do_not_overlap(self) -> None:
        # Ein Label darf nie gleichzeitig gebaeude UND landschaft ausloesen - die beiden
        # Allow-Listen sind disjunkt (natuerliche Szenen vs. Bauwerke).
        assert LANDSCAPE_SCENE_CATEGORIES.isdisjoint(ARCHITECTURE_CATEGORIES)


class TestComputeLandmarkScore:
    """specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR
    decisions/0025-cloud-landmark-erkennung.md Punkt 2: reine, synchrone, netzwerkfreie
    Funktion - kein LandmarkClientLike/Netzwerk hier noetig."""

    def test_no_identified_name_scores_zero_regardless_of_confidence(self) -> None:
        # Ein Modell-Ladefehler o.ae. koennte theoretisch trotzdem eine hohe confidence liefern -
        # ohne Namen ist das kein Sehenswuerdigkeits-Signal.
        detection = LandmarkDetection(name=None, confidence=0.9)
        assert compute_landmark_score(detection) == 0.0

    def test_identified_name_with_high_confidence_scores_high(self) -> None:
        detection = LandmarkDetection(name="Eiffelturm", confidence=0.87)
        assert compute_landmark_score(detection) == 0.87

    def test_identified_name_with_low_confidence_scores_low(self) -> None:
        detection = LandmarkDetection(name="Eiffelturm", confidence=0.1)
        assert compute_landmark_score(detection) == 0.1

    def test_confidence_above_one_is_clamped(self) -> None:
        # Defensiv, falls das Vision-LLM je einen Wert ausserhalb [0, 1] liefert.
        detection = LandmarkDetection(name="Eiffelturm", confidence=1.5)
        assert compute_landmark_score(detection) == 1.0

    def test_negative_confidence_is_clamped(self) -> None:
        detection = LandmarkDetection(name="Eiffelturm", confidence=-0.3)
        assert compute_landmark_score(detection) == 0.0


class TestIsLandmarkCandidate:
    """specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-
    attempt-fehler-persistierung.md Punkt 4: extrahiert aus worker.py::_select_landmark_candidates
    - reine Schwellenwert-Pruefung (kein Skip-bereits-gescort, das bleibt worker-spezifisch), von
    Live-Lauf UND API-Ableitung (api/photos.py::_cloud_vision_status_out) gemeinsam genutzt.

    specs/features/0217, ADR 0047 Punkt 5: die Vorfilterung prueft seit dieser Spec `landschaft`
    ODER `gebaeude` statt `content_landscape` ODER `gebaeude` - inhaltlich das, was der Filter
    immer ausdruecken sollte ("auf dem Foto ist eine Landschaft oder ein Gebaeude zu sehen").
    Die Bestandsfaelle sind dabei UMGESTELLT, nicht ergaenzt worden."""

    def test_empty_dict_is_not_a_candidate(self) -> None:
        assert is_landmark_candidate({}) is False

    def test_landschaft_below_threshold_and_gebaeude_absent_is_not_a_candidate(
        self,
    ) -> None:
        threshold = CRITERIA_REGISTRY["landschaft"].category_presence_threshold
        assert threshold is not None
        assert is_landmark_candidate({"landschaft": threshold - 0.001}) is False

    def test_landschaft_at_threshold_is_a_candidate(self) -> None:
        # Inklusiver Vergleich (`>=`), analog der uebrigen Presence-Schwellen dieses Moduls.
        threshold = CRITERIA_REGISTRY["landschaft"].category_presence_threshold
        assert threshold is not None
        assert is_landmark_candidate({"landschaft": threshold}) is True

    def test_landschaft_above_threshold_is_a_candidate(self) -> None:
        threshold = CRITERIA_REGISTRY["landschaft"].category_presence_threshold
        assert threshold is not None
        assert is_landmark_candidate({"landschaft": threshold + 0.1}) is True

    def test_gebaeude_at_threshold_is_a_candidate(self) -> None:
        threshold = CRITERIA_REGISTRY["gebaeude"].category_presence_threshold
        assert threshold is not None
        assert is_landmark_candidate({"gebaeude": threshold}) is True

    def test_gebaeude_below_threshold_and_landschaft_absent_is_not_a_candidate(
        self,
    ) -> None:
        threshold = CRITERIA_REGISTRY["gebaeude"].category_presence_threshold
        assert threshold is not None
        assert is_landmark_candidate({"gebaeude": threshold - 0.001}) is False

    def test_either_criterion_reaching_its_threshold_is_sufficient(self) -> None:
        landschaft_threshold = CRITERIA_REGISTRY["landschaft"].category_presence_threshold
        assert landschaft_threshold is not None
        assert is_landmark_candidate({"landschaft": 0.0, "gebaeude": 0.0}) is False
        assert (
            is_landmark_candidate({"landschaft": landschaft_threshold, "gebaeude": 0.0}) is True
        )

    def test_a_photo_with_only_a_high_content_landscape_value_is_no_longer_a_candidate(
        self,
    ) -> None:
        # Kostensenkung, testpflichtig (Security-Abschnitt der Spec 0217 Punkt 1, Testkonzept-
        # Regel 2 zu ADR 0047): ein texturarmes/unscharfes Foto ohne Landschaftsmotiv verlaesst
        # den Homeserver nicht mehr in Richtung des externen Vision-Anbieters.
        assert is_landmark_candidate({"content_landscape": 1.0}) is False

    def test_a_textured_real_landscape_is_newly_a_candidate(self) -> None:
        # Gegenrichtung derselben Verschiebung (die neue Kandidatenmenge ist KEINE Teilmenge der
        # alten, Security-Abschnitt Punkt 1): eine texturreiche echte Landschaftsaufnahme, die den
        # Uniform-Flaechen-Schwellwert nie erreicht haette, ist jetzt Kandidat.
        assert is_landmark_candidate({"landschaft": 0.8, "content_landscape": 0.05}) is True


# Wiederverwendungsnachweis fuer detect_person/detect_animals im Goldener-Schnitt-Kontext
# (Akzeptanzkriterium der Spec: "Spy/Aufrufzaehler statt Reimplementierung") lebt bewusst auf
# Worker-Integrationsebene statt hier, siehe test_worker_criterion_scoring.py::
# test_detect_person_and_detect_animals_are_each_called_at_most_once_per_photo -
# compute_golden_ratio_score selbst ist eine reine Funktion ohne eigenen detect()-Aufruf (siehe
# Docstring in criteria.py), ein Spy-Test dagegen wuerde nur die Aufrufliste der Testfunktion
# selbst zaehlen, nicht die tatsaechliche Produktions-Verdrahtung.
