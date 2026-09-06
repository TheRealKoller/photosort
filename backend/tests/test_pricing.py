from __future__ import annotations

import inspect
from datetime import date, timedelta
from typing import get_args
from urllib.parse import urlparse

import pytest

from photosort.cloud_vision import (
    ANTHROPIC_VISION_MODEL,
    MISTRAL_VISION_MODEL,
    VISION_MODELS_BY_PROVIDER,
    TokenUsage,
)
from photosort.config import Settings
from photosort.landmark import (
    AnthropicLandmarkClient,
    MistralLandmarkClient,
    build_landmark_client,
)
from photosort.pricing import (
    ASSUMED_USAGE_BY_PROVIDER,
    MODEL_PRICING,
    ModelPricing,
    compute_cost_usd,
    estimate_usd_per_image,
)
from photosort.remote_classification import (
    AnthropicCategoryClient,
    MistralCategoryClient,
    build_category_classification_client,
)

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
    def test_every_selectable_model_has_a_price(self) -> None:
        """Registry-Vollstaendigkeits-Invariante (analog CATEGORY_REGISTRY/CRITERION_REGISTRY) -
        der einzige automatisierte Schutz gegen einen Modellwechsel ohne Preispflege, und seit
        specs/features/0304-cloud-modell-je-anbieter-waehlbar.md zugleich der Schutz davor, dass
        ein WAEHLBARES Modell ohne Preis in die Auswahl geraet (ADR 0059 Punkt 4/5). Bewusst gegen
        `VISION_MODELS_BY_PROVIDER` statt gegen eine feste Liste: ein NEU aufgenommenes Modell
        soll diesen Test zum Fehlschlagen bringen."""
        selectable = {
            model for models in VISION_MODELS_BY_PROVIDER.values() for model in models
        }

        assert selectable, "keine waehlbaren Modelle in VISION_MODELS_BY_PROVIDER gefunden"
        assert selectable <= set(MODEL_PRICING)

    def test_all_prices_are_positive(self) -> None:
        """Ein Preis von 0 wuerde Befund (b) des Unvollstaendigkeits-Hinweises (ADR 0051 Punkt 5)
        strukturell aushebeln - dessen Argument ist "ein Betrag von exakt 0 bei nachweislich
        abgesetzten Aufrufen ist bei Token-Preisen groesser null unmoeglich"."""
        for pricing in MODEL_PRICING.values():
            assert pricing.input_usd_per_mtok > 0
            assert pricing.output_usd_per_mtok > 0

    def test_model_pricing_is_frozen(self) -> None:
        pricing = ModelPricing(
            input_usd_per_mtok=1.0,
            output_usd_per_mtok=2.0,
            source_url="https://example.invalid/preise",
            verified_on=date(2026, 1, 1),
        )

        try:
            pricing.input_usd_per_mtok = 9.0  # type: ignore[misc]
        except AttributeError:
            return
        raise AssertionError("ModelPricing sollte frozen sein")

    def test_every_source_url_points_at_the_official_domain_of_its_provider(self) -> None:
        """Der einzige automatisierbare Teil von ADR 0059 Punkt 5 ("kein aus Websuch-Aggregaten
        oder Analogieschluss gewonnener Wert"): der Beleg muss auf die Doku des Anbieters selbst
        zeigen, nicht auf einen Wiederverkaeufer oder Vergleichsportal. Host-Erlaubnisliste je
        Anbieter, `https` erzwungen."""
        allowed_hosts = {
            "anthropic": ("claude.com", "anthropic.com"),
            "mistral": ("mistral.ai",),
        }

        for provider, models in VISION_MODELS_BY_PROVIDER.items():
            for model in models:
                url = MODEL_PRICING[model].source_url
                host = urlparse(url).hostname or ""

                assert urlparse(url).scheme == "https", model
                assert any(
                    host == allowed or host.endswith(f".{allowed}")
                    for allowed in allowed_hosts[provider]
                ), (model, host)

    def test_the_assumed_usage_is_positive_in_both_directions(self) -> None:
        """Ein `output_tokens=0` schrumpfte die Schaetzung still - und die Schaetzung ist seit
        Spec 0296 die einzige verbliebene Absicherung vor der kostenpflichtigen Aktion."""
        for provider, assumed in ASSUMED_USAGE_BY_PROVIDER.items():
            assert assumed.input_tokens > 0, provider
            assert assumed.output_tokens > 0, provider

    def test_every_price_carries_a_verified_source(self) -> None:
        """ADR 0059 Punkt 5: die Verifikation gegen die offizielle Anbieterdokumentation ist ein
        Pflichtfeld, kein Kommentar - ein Preis ohne Beleg soll nicht stillschweigend durchrutschen
        koennen. Akzeptanzkriterium: "Fuer jedes waehlbare Modell ist ein Preis hinterlegt, der vor
        dem Festschreiben gegen die offizielle Anbieterdokumentation verifiziert wurde - mit Datum
        der Pruefung".

        Der eine Tag Spielraum ist KEIN zugelassenes Zukunftsdatum, sondern eine
        Zeitzonentoleranz (Copilot-Fund, PR #341): `verified_on` ist ein reines `date`, das der
        Eintragende nach seiner LOKALEN Uhr setzt, waehrend die CI in UTC laeuft. Ein am spaeten
        Abend in UTC+2 eingetragenes heutiges Datum liegt in UTC noch im Vortag - ohne Toleranz
        waere der Test in diesem taeglichen Zeitfenster rot, ohne dass etwas falsch waere.
        Gefangen wird damit weiterhin der Fall, um den es geht: ein Datum, das erkennbar nicht von
        einer stattgefundenen Pruefung stammen kann."""
        timezone_slack = timedelta(days=1)

        for model, pricing in MODEL_PRICING.items():
            assert pricing.source_url.startswith("https://"), model
            assert pricing.verified_on <= date.today() + timezone_slack, model

    def test_the_registry_and_the_assumptions_cover_exactly_the_configurable_providers(
        self,
    ) -> None:
        """Drei Stellen fuehren dieselbe Provider-Menge (das `Literal` von
        `Settings.landmark_provider`, die Modell-Registry, die Verbrauchsannahme). Laufen sie
        auseinander, faellt ein neuer Provider entweder aus der Modellwahl oder aus der
        Kostenschaetzung - beides still. Ermittelt per `get_args`, nicht gegen eine vierte Liste."""
        configurable = set(get_args(Settings.model_fields["landmark_provider"].annotation))

        assert set(VISION_MODELS_BY_PROVIDER) == configurable
        assert set(ASSUMED_USAGE_BY_PROVIDER) == configurable


class TestEstimateUsdPerImage:
    """specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, ADR 0059 Punkt 3: die Vorab-
    Schaetzung wird aus MODEL_PRICING abgeleitet statt aus einer zweiten, handgepflegten Konstante
    je Provider."""

    def test_the_default_models_reproduce_the_previous_amounts_exactly(self) -> None:
        """Akzeptanzkriterium "ohne gesetzte Einstellung exakt wie bisher": 0.0052/0.0003 sind die
        LITERALEN Werte der abgeloesten `remote_classification.py::COST_PER_IMAGE_USD` - bewusst
        ausgeschrieben und nicht aus der neuen Rechnung abgeleitet, sonst prueft dieser Test nach
        dem Umbau nur noch sich selbst. Eine Aenderung der Verbrauchsannahme verschiebt damit die
        Kostenanzeige des Regelbetriebs nicht unbemerkt.

        `abs=1e-9` statt `==`: die Assertion soll an einer fachlichen Aenderung scheitern, nicht am
        Float-Rauschen einer kuenftigen Annahmenpflege - ein einzelnes Token Unterschied liegt bei
        1e-6 und wird von dieser Toleranz weiterhin rot."""
        assert estimate_usd_per_image(ANTHROPIC_VISION_MODEL, "anthropic") == pytest.approx(
            0.0052, abs=1e-9
        )
        assert estimate_usd_per_image(MISTRAL_VISION_MODEL, "mistral") == pytest.approx(
            0.0003, abs=1e-9
        )

    def test_the_estimate_is_exactly_the_cost_of_the_assumed_usage(self) -> None:
        """"Kein neuer Rechenweg" (ADR 0059 Punkt 3): die Schaetzung ist `compute_cost_usd` ueber
        einer angenommenen statt einer gemessenen Tokenzahl."""
        assumed = ASSUMED_USAGE_BY_PROVIDER["anthropic"]

        expected = compute_cost_usd(
            ANTHROPIC_VISION_MODEL,
            TokenUsage(input_tokens=assumed.input_tokens, output_tokens=assumed.output_tokens),
        )

        assert estimate_usd_per_image(ANTHROPIC_VISION_MODEL, "anthropic") == expected

    def test_a_stronger_model_is_estimated_higher_than_the_default(self) -> None:
        """Der Defektnachweis in Zahlen: bei einer providergebundenen Schaetzung waeren beide
        Werte gleich."""
        stronger = VISION_MODELS_BY_PROVIDER["anthropic"][1]

        default_estimate = estimate_usd_per_image(ANTHROPIC_VISION_MODEL, "anthropic")
        stronger_estimate = estimate_usd_per_image(stronger, "anthropic")

        assert default_estimate is not None and stronger_estimate is not None
        assert stronger_estimate > default_estimate

    def test_mistral_stays_the_cheaper_provider_at_its_default_model(self) -> None:
        """Regressionsschutz gegen ein versehentlich vertauschtes Zahlenpaar (uebernommen aus dem
        abgeloesten TestCostPerImageUsd in test_remote_classification.py)."""
        anthropic = estimate_usd_per_image(ANTHROPIC_VISION_MODEL, "anthropic")
        mistral = estimate_usd_per_image(MISTRAL_VISION_MODEL, "mistral")

        assert anthropic is not None and mistral is not None
        assert 0 < mistral < anthropic

    def test_the_stronger_mistral_model_is_estimated_higher_than_its_default(self) -> None:
        """Dieselbe Aussage wie fuer Anthropic, jetzt fuer den zweiten Anbieter (Akzeptanz-
        kriterium "beide Anbieter werden gleich behandelt"): die Schaetzung folgt auch hier dem
        Modell. Bei einer providergebundenen Schaetzung waeren beide Werte gleich."""
        stronger = VISION_MODELS_BY_PROVIDER["mistral"][1]

        default_estimate = estimate_usd_per_image(MISTRAL_VISION_MODEL, "mistral")
        stronger_estimate = estimate_usd_per_image(stronger, "mistral")

        assert default_estimate is not None and stronger_estimate is not None
        assert stronger_estimate > default_estimate

    def test_a_different_model_of_the_same_provider_yields_a_different_estimate(self) -> None:
        """Der Kern der Story: die Schaetzung folgt dem MODELL, nicht dem Anbieter. Waere sie
        weiterhin providergebunden, kaeme hier zweimal derselbe Betrag heraus."""
        second_model = VISION_MODELS_BY_PROVIDER["anthropic"][1]

        default_estimate = estimate_usd_per_image(ANTHROPIC_VISION_MODEL, "anthropic")
        other_estimate = estimate_usd_per_image(second_model, "anthropic")

        assert default_estimate is not None and other_estimate is not None
        assert other_estimate != default_estimate

    def test_an_unpriced_model_yields_none_instead_of_a_silent_zero(self) -> None:
        """ADR 0059 Punkt 4: kein hinterlegter Preis heisst "kein Betrag", nicht "0" - ein
        kuenftiger Modellwechsel ohne Preispflege soll an der Schaetzung auffallen, statt still
        den alten Betrag weiterzuzeigen."""
        assert estimate_usd_per_image("ein-nie-bepreistes-modell", "anthropic") is None

    def test_an_unknown_provider_yields_none_instead_of_raising(self) -> None:
        assert estimate_usd_per_image(ANTHROPIC_VISION_MODEL, "openai") is None

    def test_every_selectable_model_actually_produces_an_amount(self) -> None:
        """Gegenprobe zum None-Pfad: bei gruener Registry-Invariante ist er unerreichbar - kein
        waehlbares Modell darf ohne Betrag dastehen."""
        for provider, models in VISION_MODELS_BY_PROVIDER.items():
            for model in models:
                estimate = estimate_usd_per_image(model, provider)

                assert estimate is not None and estimate > 0, (provider, model)


class TestTheModelIsAlwaysPassedIn:
    """Review-Fund (`review-tests`, Spec 0304): die Entkopplung aus ADR 0059 Punkt 7 haelt nur,
    solange das Modell wirklich hereingereicht werden MUSS. Ein Default auf die Modulkonstante
    stellte die aufgeloeste Kopplung wieder her - und ein Aufrufer, der das Modell vergisst, fiele
    dann nicht beim Typecheck auf, sondern erst in der Cloud-Rechnung."""

    def test_no_client_constructor_defaults_the_model(self) -> None:
        for client in (
            AnthropicLandmarkClient,
            MistralLandmarkClient,
            AnthropicCategoryClient,
            MistralCategoryClient,
        ):
            parameter = inspect.signature(client.__init__).parameters["model"]

            assert parameter.default is inspect.Parameter.empty, client.__name__

    def test_both_factories_require_the_model(self) -> None:
        for factory in (build_landmark_client, build_category_classification_client):
            parameter = inspect.signature(factory).parameters["model"]

            assert parameter.default is inspect.Parameter.empty, factory.__name__
