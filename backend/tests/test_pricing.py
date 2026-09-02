from __future__ import annotations

import pytest

import photosort.cloud_vision as cloud_vision
from photosort.cloud_vision import ANTHROPIC_VISION_MODEL, MISTRAL_VISION_MODEL, TokenUsage
from photosort.pricing import MODEL_PRICING, ModelPricing, compute_cost_usd

# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md Punkt 2: `compute_cost_usd` ist eine reine Funktion ueber einer Code-Konstante -
# vollstaendig ohne DB und ohne Netz testbar (Teststrategie der Spec, Unit-Ebene).


class TestComputeCostUsd:
    def test_one_million_input_tokens_cost_exactly_the_input_price(self) -> None:
        """Die MTok-Skalierung ist die eigentliche Rechenaussage der Funktion: 1 000 000
        Input-Tokens kosten genau `input_usd_per_mtok`."""
        cost = compute_cost_usd(ANTHROPIC_VISION_MODEL, TokenUsage(1_000_000, 0))

        assert cost == MODEL_PRICING[ANTHROPIC_VISION_MODEL].input_usd_per_mtok

    def test_one_million_output_tokens_cost_exactly_the_output_price(self) -> None:
        cost = compute_cost_usd(ANTHROPIC_VISION_MODEL, TokenUsage(0, 1_000_000))

        assert cost == MODEL_PRICING[ANTHROPIC_VISION_MODEL].output_usd_per_mtok

    def test_input_and_output_are_weighted_separately(self) -> None:
        """Anthropic bepreist Ausgabe teurer als Eingabe - eine Verwechslung der beiden Faktoren
        faellt nur auf, wenn beide Anteile ungleich null und die Preise verschieden sind."""
        pricing = MODEL_PRICING[ANTHROPIC_VISION_MODEL]
        assert pricing.input_usd_per_mtok != pricing.output_usd_per_mtok

        cost = compute_cost_usd(ANTHROPIC_VISION_MODEL, TokenUsage(2_000_000, 3_000_000))

        assert cost is not None
        assert cost == pytest.approx(
            2 * pricing.input_usd_per_mtok + 3 * pricing.output_usd_per_mtok
        )

    def test_the_mistral_model_is_priced_too(self) -> None:
        cost = compute_cost_usd(MISTRAL_VISION_MODEL, TokenUsage(1_000_000, 1_000_000))

        pricing = MODEL_PRICING[MISTRAL_VISION_MODEL]
        assert cost is not None
        assert cost == pytest.approx(pricing.input_usd_per_mtok + pricing.output_usd_per_mtok)

    def test_zero_tokens_cost_zero_not_none(self) -> None:
        """`0.0` heisst "erfasst, keine Kosten" - `None` hiesse "nicht erfasst" (ADR 0051 Punkt 3).
        Ein Lauf ohne Verbrauch darf nicht als Erfassungsluecke erscheinen."""
        cost = compute_cost_usd(ANTHROPIC_VISION_MODEL, TokenUsage(0, 0))

        assert cost == 0.0
        assert cost is not None

    def test_unknown_model_yields_none_instead_of_a_silent_zero(self) -> None:
        """ADR 0051 Punkt 2/Security-Abschnitt der Spec: ein nicht bepreistes Modell faellt als
        "nicht erfasst" auf, statt sich als kostenloser Lauf zu tarnen."""
        usage = TokenUsage(1_000_000, 1_000_000)

        assert compute_cost_usd("ein-nie-bepreistes-modell", usage) is None

    def test_a_realistic_small_usage_stays_below_one_cent(self) -> None:
        cost = compute_cost_usd(ANTHROPIC_VISION_MODEL, TokenUsage(1_500, 60))

        assert cost is not None
        assert 0 < cost < 0.01


class TestModelPricingRegistry:
    def test_every_vision_model_id_of_cloud_vision_has_a_price(self) -> None:
        """Registry-Vollstaendigkeits-Invariante (analog CATEGORY_REGISTRY/CRITERION_REGISTRY) -
        der einzige automatisierte Schutz gegen einen Modellwechsel ohne Preispflege. Bewusst per
        Introspektion ueber `*_VISION_MODEL`-Konstanten statt gegen eine feste Liste: ein NEU
        hinzugefuegtes Modell soll diesen Test zum Fehlschlagen bringen."""
        model_ids = {
            value
            for name, value in vars(cloud_vision).items()
            if name.endswith("_VISION_MODEL") and isinstance(value, str)
        }

        assert model_ids, "keine *_VISION_MODEL-Konstante in cloud_vision.py gefunden"
        assert model_ids <= set(MODEL_PRICING)

    def test_all_prices_are_positive(self) -> None:
        """Ein Preis von 0 wuerde Befund (b) des Unvollstaendigkeits-Hinweises (ADR 0051 Punkt 5)
        strukturell aushebeln - dessen Argument ist "ein Betrag von exakt 0 bei nachweislich
        abgesetzten Aufrufen ist bei Token-Preisen groesser null unmoeglich"."""
        for pricing in MODEL_PRICING.values():
            assert pricing.input_usd_per_mtok > 0
            assert pricing.output_usd_per_mtok > 0

    def test_model_pricing_is_frozen(self) -> None:
        pricing = ModelPricing(input_usd_per_mtok=1.0, output_usd_per_mtok=2.0)

        try:
            pricing.input_usd_per_mtok = 9.0  # type: ignore[misc]
        except AttributeError:
            return
        raise AssertionError("ModelPricing sollte frozen sein")
