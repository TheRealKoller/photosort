from __future__ import annotations

import inspect

import pytest

from photosort import landmark, remote_classification
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

    def test_both_factories_pull_the_process_wide_throttle_of_the_derived_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die beiden Factories laufen in keinem automatisierten Test (echtes Secret, echter
        Netzwerkversuch). Belegt wird die Wirkung mit gepatchten Client-Klassen: was die Factory
        baut, traegt den Schrittmacher des aus dem Modell abgeleiteten Anbieters - als Sentinel.

        BEIDE leiten den Anbieter aus dem uebergebenen Modell ab (ADR 0143 Punkt 2; fuer den
        Kategorie-Client schon seit ADR 0139 Punkt 4). Keine der beiden Factories liest
        `settings.landmark_provider`: der beschriebe den Installationsanbieter statt der Wahl des
        Projekts.
        """
        sentinel = object()
        gebaut: list[tuple[str, dict[str, object]]] = []

        def aufzeichnend(name: str) -> type:
            def __init__(self: object, **kwargs: object) -> None:
                gebaut.append((name, kwargs))

            return type(name, (), {"__init__": __init__})

        for modul, namen in (
            (landmark, ("AnthropicLandmarkClient", "MistralLandmarkClient")),
            (remote_classification, ("AnthropicCategoryClient", "MistralCategoryClient")),
        ):
            for name in namen:
                monkeypatch.setattr(modul, name, aufzeichnend(name))
            monkeypatch.setattr(modul, "throttle_for_provider", lambda provider: sentinel)

        model = next(iter(VISION_MODELS_BY_PROVIDER["mistral"]))
        build_landmark_client(model)
        build_category_classification_client(model)

        assert [name for name, _ in gebaut] == [
            "MistralLandmarkClient",
            "MistralCategoryClient",
        ]
        assert gebaut[0][1]["throttle"] is sentinel
        assert gebaut[1][1]["throttle"] is sentinel
