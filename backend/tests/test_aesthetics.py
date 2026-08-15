from __future__ import annotations

import hashlib

import numpy as np
from PIL import Image

from photosort.aesthetics import (
    _ASSET_PATH,
    AESTHETICS_MODEL_SHA256,
    compute_aesthetics,
    compute_aesthetics_score,
)


class TestAestheticsModelAsset:
    def test_committed_weights_file_matches_the_documented_sha256(self) -> None:
        # Security-Muss-Kriterium (Spec-0038-Security-Abschnitt, Punkt 3): je gepinntem
        # Modell-Asset ein eigener Integritaets-Test, analog test_classification.py.
        digest = hashlib.sha256(_ASSET_PATH.read_bytes()).hexdigest()
        assert digest == AESTHETICS_MODEL_SHA256


class TestComputeAestheticsScore:
    def test_distribution_with_expected_value_near_one_scores_near_zero(self) -> None:
        # Fast alle Wahrscheinlichkeitsmasse auf Rating 1 (Index 0) -> Erwartungswert nahe 1.
        distribution = [0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        assert compute_aesthetics_score(distribution) < 0.05

    def test_distribution_with_expected_value_near_ten_scores_near_one(self) -> None:
        # Fast alle Wahrscheinlichkeitsmasse auf Rating 10 (Index 9) -> Erwartungswert nahe 10.
        distribution = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.9]
        assert compute_aesthetics_score(distribution) > 0.95

    def test_uniform_distribution_scores_around_one_half(self) -> None:
        distribution = [0.1] * 10
        score = compute_aesthetics_score(distribution)
        assert abs(score - 0.5) < 0.01

    def test_degenerate_distribution_at_the_low_end_stays_in_range_and_is_exact(self) -> None:
        # Grenzfall: die GESAMTE Wahrscheinlichkeitsmasse liegt auf einer einzelnen Ratingklasse
        # (Akzeptanzkriterium der Spec) - hier Rating 1, der niedrigstmoegliche Erwartungswert.
        distribution = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        assert compute_aesthetics_score(distribution) == 0.0

    def test_degenerate_distribution_at_the_high_end_stays_in_range_and_is_exact(self) -> None:
        distribution = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        assert compute_aesthetics_score(distribution) == 1.0

    def test_degenerate_distribution_in_the_middle_stays_in_range(self) -> None:
        distribution = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
        score = compute_aesthetics_score(distribution)
        assert 0.0 <= score <= 1.0

    def test_empty_distribution_does_not_crash_and_stays_in_range(self) -> None:
        # Degenerierter Grenzfall (Modell-Ladefehler/leere Vorhersage) - kein NaN/ZeroDivisionError
        # durch die Normierungsformel.
        assert compute_aesthetics_score([]) == 0.0

    def test_all_zero_distribution_does_not_crash(self) -> None:
        # Weder eine gueltige Wahrscheinlichkeitsverteilung noch leer - Summe 0 wuerde eine
        # Division durch 0 ausloesen, wenn nicht explizit abgefangen.
        distribution = [0.0] * 10
        score = compute_aesthetics_score(distribution)
        assert 0.0 <= score <= 1.0


class FakeAestheticsModel:
    """Faket die schmale Teilmenge der Keras-Model-API, die compute_aesthetics braucht (ein
    `.predict(batch)` -> np.ndarray der Form (1, 10)) - kein echtes tensorflow-Modell in Tests."""

    def __init__(self, distribution: list[float]) -> None:
        self._distribution = distribution

    def predict(self, batch: np.ndarray) -> np.ndarray:
        return np.array([self._distribution], dtype=np.float32)


class TestComputeAesthetics:
    def test_runs_preprocessing_and_normalization_end_to_end(self) -> None:
        image = Image.new("RGB", (160, 160), color=(120, 120, 120))
        model = FakeAestheticsModel([0.0] * 8 + [0.1, 0.9])  # Erwartungswert nahe 10
        assert compute_aesthetics(image, model) > 0.95

    def test_image_smaller_than_the_model_input_size_does_not_crash(self) -> None:
        # Degenerierter Grenzfall analog test_image_smaller_than_the_tile_grid_does_not_crash in
        # test_classification.py (Teststrategie-Abschnitt der Spec 0038).
        image = Image.new("RGB", (4, 4), color=(50, 50, 50))
        model = FakeAestheticsModel([0.1] * 10)
        score = compute_aesthetics(image, model)
        assert 0.0 <= score <= 1.0
