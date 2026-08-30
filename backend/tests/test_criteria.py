from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw

from photosort.classification import (
    SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD,
    SCENE_LABEL_MIN_CONFIDENCE,
    AnimalDetection,
    FaceBoundingBox,
    FaceOrientation,
    SceneLabel,
)
from photosort.criteria import (
    ARCHITECTURE_CATEGORIES,
    CATEGORY_SPECIFIC_MIN_PHOTOS,
    CATEGORY_SPECIFICITY_CONTENT,
    CATEGORY_SPECIFICITY_NAMED,
    CATEGORY_UNRECOGNIZED,
    CRITERIA_REGISTRY,
    DYNAMIC_LABEL_PRESENCE_THRESHOLD,
    FREIRAUM_YAW_DEADZONE_DEGREES,
    LANDSCAPE_SCENE_CATEGORIES,
    LANDSCHAFT_LABEL_MIN_CONFIDENCE,
    compute_content_landscape,
    compute_content_people,
    compute_freiraum_score,
    compute_gebaeude_score,
    compute_golden_ratio_score,
    compute_landmark_score,
    compute_landschaft_score,
    compute_symmetrie_score,
    compute_tier_score,
    derive_active_categories,
    derive_category_key,
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

    def test_exactly_five_content_criteria_are_category_eligible(self) -> None:
        # Akzeptanzkriterium der Spec 0045, erweitert um landmark (specs/features/0047-
        # sehenswuerdigkeit-erkennung-cloud-vision-api.md) und seit specs/features/0217/ADR 0046
        # Punkt 1 mit `landschaft` STATT `content_landscape` (Flaechigkeit ist ein reines
        # Ranking-Signal, keine Inhaltsaussage): genau content_people/landschaft/tier/gebaeude/
        # landmark sind category_eligible=True - reine Qualitaetskriterien nie. Bewusst weiterhin
        # eine MENGEN-Assertion (nicht auf einen Anzahl-Vergleich abgeschwaecht).
        eligible = {key for key, d in CRITERIA_REGISTRY.items() if d.category_eligible}
        assert eligible == {
            "content_people",
            "landschaft",
            "tier",
            "gebaeude",
            "landmark",
        }

    def test_registry_contains_landschaft_with_the_correct_source_and_threshold(self) -> None:
        # specs/features/0217, ADR 0046 Punkt 1: neues, echtes Inhalts-Kriterium aus derselben
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
        # ADR 0046 Punkt 1: compute_uniform_area_fraction misst Texturarmut, keine Landschaft -
        # das Kriterium bleibt als Ranking-Signal erhalten, darf aber keine Kategorie mehr bilden.
        # Der Anzeigename behauptet entsprechend keine Inhaltsaussage mehr.
        definition = CRITERIA_REGISTRY["content_landscape"]
        assert definition.display_name == "Flächigkeit"
        assert definition.category_eligible is False
        assert definition.category_presence_threshold is None

    def test_category_specificity_is_one_of_the_two_defined_levels(self) -> None:
        # Registry-Invariante (specs/features/0217, ADR 0046 Punkt 2): Spezifitaet ist ein
        # Registry-ATTRIBUT mit genau zwei Stufen, keine im Ableitungscode gepflegte
        # Prioritaetsliste.
        for key, definition in CRITERIA_REGISTRY.items():
            assert definition.category_specificity in {
                CATEGORY_SPECIFICITY_CONTENT,
                CATEGORY_SPECIFICITY_NAMED,
            }, f"{key}: unbekannte Spezifitaets-Stufe"

    def test_named_specificity_is_set_exactly_for_landmark(self) -> None:
        named = {
            key
            for key, d in CRITERIA_REGISTRY.items()
            if d.category_specificity == CATEGORY_SPECIFICITY_NAMED
        }
        assert named == {"landmark"}

    def test_specificity_only_carries_meaning_for_category_eligible_criteria(self) -> None:
        # Invariante aus dem Architektur-Abschnitt der Spec 0217: ein nicht kategorie-faehiges
        # Kriterium kann nie eine Kategorie bilden, seine Spezifitaet ist bedeutungslos und muss
        # deshalb auf dem Default stehen bleiben (sonst suggeriert die Registry eine Rangordnung,
        # die nirgends ausgewertet wird).
        for key, definition in CRITERIA_REGISTRY.items():
            if not definition.category_eligible:
                assert definition.category_specificity == CATEGORY_SPECIFICITY_CONTENT, (
                    f"{key}: Spezifitaet gesetzt, obwohl nicht kategorie-faehig"
                )

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
        # Nicht-Regressions-Pflicht (specs/features/0217 AK2, Testkonzept-Regel 1 zu ADR 0046):
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
    """specs/features/0217, ADR decisions/0046 Punkt 1: echte, inhaltsbasierte Landschafts-
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

    specs/features/0217, ADR 0046 Punkt 5: die Vorfilterung prueft seit dieser Spec `landschaft`
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
        # Inklusiver Vergleich (`>=`), analog derive_active_categories/derive_category_key.
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
        # Regel 2 zu ADR 0046): ein texturarmes/unscharfes Foto ohne Landschaftsmotiv verlaesst
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


class TestDeriveActiveCategories:
    def test_empty_candidate_pool_yields_empty_set_without_zero_division(self) -> None:
        assert derive_active_categories({}) == frozenset()

    def test_criterion_with_zero_hits_stays_inactive(self) -> None:
        candidate_values = {
            1: {"content_people": 0.0, "landschaft": 0.9},
            2: {"content_people": 0.0, "landschaft": 0.9},
        }
        active = derive_active_categories(candidate_values)
        assert "content_people" not in active
        assert "landschaft" in active

    def test_exactly_at_the_fifteen_percent_threshold_is_active_inclusive(self) -> None:
        # 15 von 100 Kandidaten erfuellen die Presence-Schwelle -> genau 15% -> aktiv (inklusiv).
        candidate_values = {i: {"tier": 0.9 if i < 15 else 0.0} for i in range(100)}
        active = derive_active_categories(candidate_values)
        assert "tier" in active

    def test_just_below_the_threshold_stays_inactive(self) -> None:
        candidate_values = {i: {"tier": 0.9 if i < 14 else 0.0} for i in range(100)}
        active = derive_active_categories(candidate_values)
        assert "tier" not in active

    def test_just_above_the_threshold_is_active(self) -> None:
        candidate_values = {i: {"tier": 0.9 if i < 16 else 0.0} for i in range(100)}
        active = derive_active_categories(candidate_values)
        assert "tier" in active

    def test_missing_values_for_some_photos_count_as_not_present(self) -> None:
        # Best-effort: fuer photo 2/3 wurde landschaft gar nicht erst berechnet (fehlender Key
        # statt 0.0) - zaehlt trotzdem als "nicht vorhanden", kein KeyError. Nur 1 von 3 (33%)
        # erfuellt die Presence-Schwelle, unter der 50%-Testschwelle.
        candidate_values = {
            1: {"landschaft": 0.9},
            2: {},
            3: {},
        }
        active = derive_active_categories(candidate_values, threshold_fraction=0.5)
        assert "landschaft" not in active

    def test_custom_threshold_fraction_is_respected(self) -> None:
        candidate_values = {i: {"tier": 0.9 if i < 5 else 0.0} for i in range(10)}
        assert "tier" not in derive_active_categories(candidate_values, threshold_fraction=0.6)
        assert "tier" in derive_active_categories(candidate_values, threshold_fraction=0.5)


class TestDeriveCategoryKey:
    def test_people_wins_when_only_people_is_active(self) -> None:
        values = {"content_people": 1.0, "landschaft": 1.0}
        active = frozenset({"content_people"})
        assert derive_category_key(values, active) == "people"

    def test_recognised_landscape_without_people_is_landschaft(self) -> None:
        # specs/features/0217 AK1: der Kategorie-Key kommt jetzt aus dem echten Inhalts-Kriterium
        # `landschaft` (Allow-Listen-Treffer), nicht mehr aus der Flaechigkeits-Heuristik.
        values = {"content_people": 0.0, "landschaft": 0.9}
        active = frozenset({"content_people", "landschaft"})
        assert derive_category_key(values, active) == "landschaft"

    def test_no_landscape_label_without_people_falls_back_to_the_catch_all(self) -> None:
        values = {"content_people": 0.0, "landschaft": 0.0}
        active = frozenset({"content_people", "landschaft"})
        assert derive_category_key(values, active) == CATEGORY_UNRECOGNIZED

    def test_a_high_content_landscape_value_alone_never_forms_a_category(self) -> None:
        # AK1 der Spec 0217: content_landscape ist strukturell nicht mehr kategorie-faehig - ein
        # texturarmes Bild ohne Landschaftsmotiv landet im Catch-all, nie in "landscape".
        values = {"content_landscape": 0.95}
        active = frozenset({"content_landscape", "landschaft"})
        assert derive_category_key(values, active) == CATEGORY_UNRECOGNIZED

    def test_missing_criteria_falls_back_to_the_unrecognized_catch_all_without_crashing(
        self,
    ) -> None:
        # Best-effort-Fall: beide Inhalts-Kriterien fuer dieses Foto konnten nicht berechnet
        # werden (z.B. fehlende display-Cache-Datei) - die Kette darf nicht crashen.
        assert derive_category_key({}, frozenset({"content_people"})) == CATEGORY_UNRECOGNIZED

    def test_no_active_categories_at_all_falls_back_to_the_unrecognized_catch_all(self) -> None:
        # Kein Kriterium im Lauf erreichte die 15%-Haeufigkeitsschwelle - jedes Foto landet im
        # Catch-all, unabhaengig von den einzelnen Kriterien-Werten.
        values = {"content_people": 1.0, "landschaft": 1.0}
        assert derive_category_key(values, frozenset()) == CATEGORY_UNRECOGNIZED

    def test_highest_score_wins_among_several_active_criteria(self) -> None:
        # tier (0.4) schlaegt gebaeude (0.2), obwohl content_people nicht erfuellt ist -
        # Akzeptanzkriterium: "gewinnt der hoechste normierte Score".
        values = {"tier": 0.4, "gebaeude": 0.2, "content_people": 0.0}
        active = frozenset({"tier", "gebaeude", "content_people"})
        assert derive_category_key(values, active) == "tier"

    def test_tie_break_is_alphabetical_by_criterion_key(self) -> None:
        # landschaft und tier erreichen exakt denselben Score (dieselbe Spezifitaets-Stufe) ->
        # alphabetisch fruehester criterion_key gewinnt ("landschaft" < "tier").
        values = {"landschaft": 0.6, "tier": 0.6}
        active = frozenset({"landschaft", "tier"})
        assert derive_category_key(values, active) == "landschaft"

    def test_gebaeude_and_tier_derive_category_keys_without_manual_mapping(self) -> None:
        assert derive_category_key({"tier": 0.5}, frozenset({"tier"})) == "tier"
        assert derive_category_key({"gebaeude": 0.5}, frozenset({"gebaeude"})) == "gebaeude"

    def test_active_but_below_the_photos_own_presence_threshold_does_not_win(self) -> None:
        # tier ist AKTIV im Lauf (Haeufigkeitsschwelle erreicht), aber DIESES Foto selbst hat nur
        # einen sehr niedrigen tier-Score unterhalb der Presence-Schwelle - gewinnt trotzdem nicht,
        # nur weil es das aktivste unter den Werten waere.
        values = {"tier": 0.001, "content_people": 0.0}
        active = frozenset({"tier", "content_people"})
        assert derive_category_key(values, active) == CATEGORY_UNRECOGNIZED


class TestDeriveActiveCategoriesDynamicKeys:
    """specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
    decisions/0032 Punkt 1: neuer, optionaler dritter Parameter `dynamic_keys` - zur Laufzeit
    entdeckte Remote-Label-Pseudo-Keys (`f"remote:{canonical_key}"`) werden an derselben 15%-
    Haeufigkeitsschwelle gemessen wie die registrierten lokalen Kriterien. Regressionspflicht
    zuerst: alle obigen TestDeriveActiveCategories-Faelle bleiben mit dem Default
    `dynamic_keys=frozenset()` unveraendert gruen (siehe oben, keine Aenderung noetig)."""

    def test_dynamic_key_becomes_active_when_it_reaches_the_threshold(self) -> None:
        candidate_values = {i: {"remote:hund": 0.9 if i < 15 else 0.0} for i in range(100)}
        active = derive_active_categories(
            candidate_values, dynamic_keys=frozenset({"remote:hund"})
        )
        assert "remote:hund" in active

    def test_dynamic_key_below_the_share_threshold_is_active_via_the_absolute_minimum(
        self,
    ) -> None:
        # Auf die neue Regel UMGESTELLTER Bestandstest (specs/features/0217, ADR 0046 Punkt 3):
        # 14 von 100 (< 15%) blieben bis Spec 0055 inaktiv - ein Remote-Key ist als NAMED-Stufe
        # jetzt bereits ueber die absolute Mindest-Trefferzahl aktiv. Der Fall "wirklich zu
        # selten" (2 Treffer) steht in TestDeriveActiveCategoriesSpecificity.
        candidate_values = {i: {"remote:hund": 0.9 if i < 14 else 0.0} for i in range(100)}
        active = derive_active_categories(
            candidate_values, dynamic_keys=frozenset({"remote:hund"})
        )
        assert "remote:hund" in active

    def test_dynamic_presence_threshold_is_exactly_inclusive(self) -> None:
        # Ein Wert exakt an DYNAMIC_LABEL_PRESENCE_THRESHOLD zaehlt als "vorhanden" (inklusiv,
        # `>=`) - ein von einem Vision-LLM gelieferter Wert ist bereits eine "erkannt"-Aussage,
        # dieser Schwellwert trennt nur "vorhanden" von "fehlender Eintrag".
        candidate_values = {
            i: {"remote:hund": DYNAMIC_LABEL_PRESENCE_THRESHOLD if i < 15 else 0.0}
            for i in range(100)
        }
        active = derive_active_categories(
            candidate_values, dynamic_keys=frozenset({"remote:hund"})
        )
        assert "remote:hund" in active

    def test_a_dynamic_key_not_present_in_any_candidate_stays_inactive(self) -> None:
        candidate_values = {1: {"content_people": 1.0}, 2: {"content_people": 1.0}}
        active = derive_active_categories(
            candidate_values, dynamic_keys=frozenset({"remote:hund"})
        )
        assert "remote:hund" not in active

    def test_local_and_dynamic_keys_are_evaluated_independently(self) -> None:
        candidate_values = {
            i: {
                "content_people": 1.0 if i < 15 else 0.0,
                "remote:hund": 1.0 if i < 50 else 0.0,
            }
            for i in range(100)
        }
        active = derive_active_categories(
            candidate_values, dynamic_keys=frozenset({"remote:hund"})
        )
        assert "content_people" in active
        assert "remote:hund" in active


class TestDeriveCategoryKeyDynamicKeys:
    def test_dynamic_key_wins_when_it_has_the_highest_score(self) -> None:
        values = {"tier": 0.4, "remote:hund": 0.6}
        active = frozenset({"tier", "remote:hund"})
        assert (
            derive_category_key(values, active, dynamic_keys=frozenset({"remote:hund"}))
            == "hund"
        )

    def test_dynamic_key_wins_over_a_higher_scoring_local_key(self) -> None:
        # Auf die neue Regel UMGESTELLTER Bestandstest (specs/features/0217, ADR 0046 Punkt 2):
        # bis Spec 0055 gewann hier der hoehere Score (tier 0.6), seit dem Spezifitaets-Vorrang
        # gewinnt der benannte, konkrete Inhalt - unabhaengig vom Zahlenwert (die beiden Zahlen
        # stammen aus unvergleichbaren Skalen).
        values = {"tier": 0.6, "remote:hund": 0.4}
        active = frozenset({"tier", "remote:hund"})
        assert (
            derive_category_key(values, active, dynamic_keys=frozenset({"remote:hund"}))
            == "hund"
        )

    def test_dynamic_key_below_its_own_presence_threshold_does_not_win(self) -> None:
        values = {"remote:hund": 0.001}
        active = frozenset({"remote:hund"})
        result = derive_category_key(values, active, dynamic_keys=frozenset({"remote:hund"}))
        assert result == CATEGORY_UNRECOGNIZED

    def test_tie_break_is_alphabetical_on_the_full_prefixed_key(self) -> None:
        # Tie-Break innerhalb DERSELBEN Spezifitaets-Stufe (zwei Remote-Keys, beide NAMED) bei
        # identischem Score: alphabetisch nach dem VOLLEN, praefixierten Key ("remote:aal" <
        # "remote:hund"), nicht nach dem entpraefixierten Anzeigenamen - ADR 0032 Punkt 1,
        # unveraendert deterministisch.
        values = {"remote:hund": 0.5, "remote:aal": 0.5}
        active = frozenset({"remote:hund", "remote:aal"})
        result = derive_category_key(
            values, active, dynamic_keys=frozenset({"remote:hund", "remote:aal"})
        )
        assert result == "aal"

    def test_remote_prefix_is_stripped_symmetrically_to_the_content_prefix(self) -> None:
        values = {"remote:strand": 0.9}
        active = frozenset({"remote:strand"})
        result = derive_category_key(values, active, dynamic_keys=frozenset({"remote:strand"}))
        assert result == "strand"


class TestDeriveActiveCategoriesSpecificity:
    """specs/features/0217, ADR decisions/0046 Punkt 3: die Aktivierungsschwelle wird
    spezifitaetsabhaengig - CONTENT behaelt die reine 15%-Regel, NAMED ist zusaetzlich ab
    CATEGORY_SPECIFIC_MIN_PHOTOS absoluten Treffern aktiv (ODER-Verknuepfung, damit sehr kleine
    Projekte nicht schlechter gestellt werden als bisher)."""

    def test_named_key_is_active_at_exactly_the_minimum_photo_count(self) -> None:
        # 3 von 100 = 3% Anteil, weit unter 15% - trotzdem aktiv (AK4).
        assert CATEGORY_SPECIFIC_MIN_PHOTOS == 3
        candidate_values = {i: {"remote:elefant": 0.9 if i < 3 else 0.0} for i in range(100)}
        active = derive_active_categories(
            candidate_values, dynamic_keys=frozenset({"remote:elefant"})
        )
        assert "remote:elefant" in active

    def test_named_key_with_two_hits_and_a_low_share_stays_inactive(self) -> None:
        candidate_values = {i: {"remote:elefant": 0.9 if i < 2 else 0.0} for i in range(100)}
        active = derive_active_categories(
            candidate_values, dynamic_keys=frozenset({"remote:elefant"})
        )
        assert "remote:elefant" not in active

    def test_named_key_with_two_hits_is_active_when_the_share_reaches_fifteen_percent(
        self,
    ) -> None:
        # Kleines Projekt (10 Kandidaten): 2 Treffer = 20% - die ODER-Verknuepfung darf niemanden
        # schlechter stellen als die bisherige reine Anteilsregel.
        candidate_values = {i: {"remote:elefant": 0.9 if i < 2 else 0.0} for i in range(10)}
        active = derive_active_categories(
            candidate_values, dynamic_keys=frozenset({"remote:elefant"})
        )
        assert "remote:elefant" in active

    def test_registered_named_criterion_landmark_follows_the_same_rule(self) -> None:
        candidate_values = {i: {"landmark": 0.9 if i < 3 else 0.0} for i in range(100)}
        assert "landmark" in derive_active_categories(candidate_values)

    def test_content_criterion_keeps_the_pure_fifteen_percent_rule(self) -> None:
        # 3 von 100 reichen fuer ein CONTENT-Kriterium ausdruecklich NICHT.
        candidate_values = {i: {"tier": 0.9 if i < 3 else 0.0} for i in range(100)}
        assert "tier" not in derive_active_categories(candidate_values)

    def test_specific_min_photos_is_overridable(self) -> None:
        candidate_values = {i: {"landmark": 0.9 if i < 3 else 0.0} for i in range(100)}
        assert "landmark" not in derive_active_categories(
            candidate_values, specific_min_photos=4
        )
        assert "landmark" in derive_active_categories(candidate_values, specific_min_photos=3)

    def test_empty_candidate_pool_stays_safe_with_the_new_rule(self) -> None:
        assert derive_active_categories({}, dynamic_keys=frozenset({"remote:x"})) == frozenset()


class TestDeriveCategoryKeySpecificity:
    """specs/features/0217, ADR decisions/0046 Punkt 2: Spezifitaets-Vorrang ersetzt "hoechster
    Score gewinnt" als PRIMAERE Regel - Auswahlschluessel `(-specificity, -score, key)`. Innerhalb
    einer Stufe bleibt die vertraute Regel unveraendert (siehe TestDeriveCategoryKey oben)."""

    def test_named_criterion_wins_against_a_higher_scoring_content_criterion(self) -> None:
        values = {"landmark": 0.6, "tier": 0.95}
        active = frozenset({"landmark", "tier"})
        assert derive_category_key(values, active) == "landmark"

    def test_remote_label_wins_against_content_people_with_a_perfect_score(self) -> None:
        # AK3 der Spec 0217 (Stakeholder-Entscheidung vom 2026-08-30): ein Foto mit erkannten
        # Gesichtern UND einem Remote-Schlagwort ("Hochzeit") landet unter dem Schlagwort.
        values = {"content_people": 1.0, "remote:hochzeit": 0.3}
        active = frozenset({"content_people", "remote:hochzeit"})
        assert (
            derive_category_key(values, active, dynamic_keys=frozenset({"remote:hochzeit"}))
            == "hochzeit"
        )

    def test_highest_score_still_decides_within_the_same_specificity_level(self) -> None:
        values = {"landschaft": 0.4, "gebaeude": 0.8}
        active = frozenset({"landschaft", "gebaeude"})
        assert derive_category_key(values, active) == "gebaeude"

    def test_tie_break_between_two_named_keys_is_alphabetical_on_the_full_key(self) -> None:
        # "landmark" < "remote:hund" - beide NAMED, identischer Score.
        values = {"landmark": 0.7, "remote:hund": 0.7}
        active = frozenset({"landmark", "remote:hund"})
        assert (
            derive_category_key(values, active, dynamic_keys=frozenset({"remote:hund"}))
            == "landmark"
        )

    def test_photo_without_any_fulfilled_criterion_lands_in_the_unrecognized_catch_all(
        self,
    ) -> None:
        # AK5/AK6 der Spec 0217: der Catch-all heisst "unerkannt", "detail" wird nicht mehr
        # automatisch vergeben.
        assert CATEGORY_UNRECOGNIZED == "unerkannt"
        assert derive_category_key({}, frozenset({"tier"})) == "unerkannt"

    def test_a_remote_label_slugified_to_the_catch_all_key_does_not_collide_with_it(
        self,
    ) -> None:
        # Security-Abschnitt der Spec 0217, Punkt 2: ein Remote-Label "Unerkannt" ergaebe
        # canonical_key "unerkannt" - es wird eindeutig abgesetzt, statt echte Erkennungen in den
        # Auffang-Abschnitt zu mischen.
        values = {"remote:unerkannt": 0.9}
        active = frozenset({"remote:unerkannt"})
        result = derive_category_key(
            values, active, dynamic_keys=frozenset({"remote:unerkannt"})
        )
        assert result != CATEGORY_UNRECOGNIZED
        assert result.startswith(CATEGORY_UNRECOGNIZED)

    def test_a_named_key_below_its_own_presence_threshold_does_not_win(self) -> None:
        # Spezifitaet hebt die Presence-Pruefung des Fotos NICHT auf: landmark liegt unter seiner
        # Registry-Schwelle (0.5), das Foto qualifiziert sich dafuer gar nicht erst.
        values = {"landmark": 0.4, "tier": 0.9}
        active = frozenset({"landmark", "tier"})
        assert derive_category_key(values, active) == "tier"
