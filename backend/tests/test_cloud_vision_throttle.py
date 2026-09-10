from __future__ import annotations

import inspect

import pytest

from photosort.cloud_vision import (
    DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER,
    VISION_MODELS_BY_PROVIDER,
    CloudRequestThrottle,
)
from photosort.cloud_vision_throttle import build_throttles, throttle_for_provider
from photosort.config import Settings
from photosort.landmark import (
    AnthropicLandmarkClient,
    MistralLandmarkClient,
    build_landmark_client,
)
from photosort.remote_classification import (
    AnthropicCategoryClient,
    MistralCategoryClient,
    build_category_classification_client,
)

# specs/features/0382-cloud-rate-limits-aussitzen.md, decisions/0074-cloud-vision-schrittmacher-
# je-anbieter-und-wiederholung-nur-bei-429.md Entscheidung 3: die prozessweiten Schrittmacher-
# Instanzen, genau eine je Anbieter - geteilt von beiden Cloud-Teilschritten und von mehreren
# gleichzeitig laufenden Jobs.
#
# KEIN Test ruft hier `acquire()` auf einer REGISTRY-Instanz auf: sie ist prozessweit und traegt
# ihren Zustand ueber die gesamte pytest-Sitzung. Geprueft wird ueber die reine Bau-Funktion mit
# einer handgebauten `Settings` (Auflage 2 der Teststrategie der Spec 0382 - ohne sie waere die
# Registry nur ueber `importlib.reload` pruefbar).


class TestBuildThrottles:
    def test_it_builds_one_throttle_per_known_provider(self) -> None:
        throttles = build_throttles(Settings(_env_file=None))

        assert set(throttles) == set(DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER)
        assert all(isinstance(value, CloudRequestThrottle) for value in throttles.values())

    @pytest.mark.parametrize(("provider", "expected"), [("anthropic", 1.0), ("mistral", 1.5)])
    def test_the_interval_is_derived_from_the_resolved_rate(
        self, provider: str, expected: float
    ) -> None:
        """60 Anfragen/Minute = 1 Anfrage pro Sekunde, 40 = 1 Anfrage alle 1,5 Sekunden - dieselben
        Zahlen wie in `docs/setup.md` (K10)."""
        throttles = build_throttles(Settings(_env_file=None))

        assert throttles[provider].min_interval_seconds == pytest.approx(expected)

    def test_a_configured_rate_overrides_both_provider_defaults(self) -> None:
        throttles = build_throttles(Settings(_env_file=None, cloud_vision_requests_per_minute=120))

        assert throttles["anthropic"].min_interval_seconds == pytest.approx(0.5)
        assert throttles["mistral"].min_interval_seconds == pytest.approx(0.5)

    @pytest.mark.parametrize("provider", ["anthropic", "mistral"])
    def test_no_interval_is_zero_and_nothing_divides_by_zero(self, provider: str) -> None:
        """Sicherheits-Muss-Kriterium der Spec 0382 (Punkt 6): `cloud_vision_throttle.py` darf
        beim Import nicht werfen. Die Instanzen entstehen zur Modul-Importzeit aus `60 / rate`;
        eine aufgeloeste `0` waere ein ZeroDivisionError beim Prozessstart von Backend UND
        Worker."""
        throttles = build_throttles(Settings(_env_file=None))

        assert throttles[provider].min_interval_seconds > 0

    def test_it_is_a_pure_function_over_a_settings_object(self) -> None:
        """Zwei Aufrufe liefern getrennte Instanzen - die prozessweite Registry unten ist die
        EINE Anwendung dieser Funktion, nicht ihre einzige moegliche."""
        first = build_throttles(Settings(_env_file=None))
        second = build_throttles(Settings(_env_file=None))

        assert first["anthropic"] is not second["anthropic"]


class TestThrottleForProvider:
    def test_repeated_lookups_return_the_very_same_instance(self) -> None:
        """K4: es gibt GENAU EINE Instanz je Anbieter und Prozess - beide Cloud-Teilschritte und
        mehrere gleichzeitig laufende Laeufe teilen sie sich."""
        assert throttle_for_provider("anthropic") is throttle_for_provider("anthropic")
        assert throttle_for_provider("mistral") is throttle_for_provider("mistral")

    def test_the_two_providers_do_not_share_a_throttle(self) -> None:
        assert throttle_for_provider("anthropic") is not throttle_for_provider("mistral")

    def test_an_unknown_provider_is_a_key_error(self) -> None:
        """Direkter Dict-Zugriff, kein stiller Rueckfall: durch das `Literal` auf
        `Settings.landmark_provider` ist dieser Fall unerreichbar, und genau deshalb soll er laut
        scheitern statt sich eine Voreinstellung auszudenken."""
        with pytest.raises(KeyError):
            throttle_for_provider("openai")


class TestTheProviderDefaults:
    def test_they_cover_exactly_the_selectable_providers(self) -> None:
        assert set(DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER) == set(VISION_MODELS_BY_PROVIDER)

    def test_every_default_is_documented_with_its_source(self) -> None:
        """Belegpflicht analog ADR 0059 Punkt 5 (Modellpreise): jede Voreinstellung traegt Quelle
        und Abrufdatum im Kommentar - bei Mistral ausdruecklich samt der offen bleibenden
        Beleglucke. Geprueft wird nur, DASS die Tabelle kommentiert ist; der Inhalt der Herleitung
        ist eine Aussage ueber fremde Systeme und gehoert in ADR 0074."""
        import photosort.cloud_vision as cloud_vision

        source = inspect.getsource(cloud_vision)
        table_start = source.index("DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER")
        preceding = source[:table_start]

        assert "2026-09-10" in preceding
        assert "0074" in preceding


class TestTheThrottleIsAlwaysPassedIn:
    """K6, Bauform analog `TestTheModelIsAlwaysPassedIn` in test_pricing.py: der Schrittmacher ist
    an allen vier Client-Klassen ein Schluesselwortparameter OHNE Default. Ein Default (etwa auf
    einen frisch gebauten, wirkungslosen Schrittmacher) hoehlte die Zusage der Story aus - ein
    Aufrufer, der ihn vergisst, fiele nicht beim Typecheck auf, sondern erst an der Anfragerate
    des Anbieters."""

    def test_no_client_constructor_defaults_the_throttle(self) -> None:
        for client in (
            AnthropicLandmarkClient,
            MistralLandmarkClient,
            AnthropicCategoryClient,
            MistralCategoryClient,
        ):
            parameter = inspect.signature(client.__init__).parameters["throttle"]

            assert parameter.default is inspect.Parameter.empty, client.__name__
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, client.__name__

    def test_both_factories_pull_the_process_wide_throttle(self) -> None:
        """Die beiden Factories laufen in keinem automatisierten Test (echtes Secret, echter
        Netzwerkversuch) - abgesichert ist ihr Durchreichen deshalb als Quelltext-Verankerung
        plus `mypy --strict`."""
        for factory in (build_landmark_client, build_category_classification_client):
            source = inspect.getsource(factory)

            assert "throttle_for_provider(settings.landmark_provider)" in source, factory.__name__
            assert "throttle=throttle" in source, factory.__name__
