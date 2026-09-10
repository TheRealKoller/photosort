from __future__ import annotations

import ast
import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest

import photosort.cloud_vision as cloud_vision
from photosort.cloud_vision import (
    ANTHROPIC_API_VERSION,
    ANTHROPIC_MESSAGES_URL,
    ANTHROPIC_VISION_MODEL,
    MISTRAL_CHAT_COMPLETIONS_URL,
    MISTRAL_VISION_MODEL,
    VISION_MODELS_BY_PROVIDER,
    VISION_REQUEST_TIMEOUT_SECONDS,
    TokenUsage,
    anthropic_response_to_json,
    anthropic_usage_from_response,
    default_vision_model_for_provider,
    mistral_response_to_json,
    mistral_usage_from_response,
    provider_for_vision_model,
    raise_for_vision_api_status,
)

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, Akzeptanzkriterium
# "Module (Refactoring)": neues, providerneutrales cloud_vision.py, extrahiert aus landmark.py -
# von beiden Feature-Modulen (landmark.py, remote_classification.py) genutzt. Bestehende
# test_landmark.py-Faelle bleiben ohne Assertion-Aenderung gruen (siehe dortige Regressionstests,
# unveraendert) - diese Datei testet ausschliesslich die neu extrahierten, jetzt oeffentlichen
# Bausteine direkt.


class _FakeApiError(Exception):
    pass


def test_module_level_constants_are_provider_neutral_and_reusable() -> None:
    assert ANTHROPIC_MESSAGES_URL == "https://api.anthropic.com/v1/messages"
    assert ANTHROPIC_API_VERSION == "2023-06-01"
    assert MISTRAL_CHAT_COMPLETIONS_URL == "https://api.mistral.ai/v1/chat/completions"
    assert ANTHROPIC_VISION_MODEL
    assert MISTRAL_VISION_MODEL
    assert VISION_REQUEST_TIMEOUT_SECONDS > 0


class TestRaiseForVisionApiStatus:
    def test_success_response_raises_nothing(self) -> None:
        raise_for_vision_api_status(httpx.Response(200, json={}), "Anthropic", _FakeApiError)

    def test_error_response_raises_the_injected_error_class(self) -> None:
        with pytest.raises(_FakeApiError) as exc_info:
            raise_for_vision_api_status(
                httpx.Response(401, text="Unauthorized"), "Anthropic", _FakeApiError
            )
        assert "Anthropic" in str(exc_info.value)
        assert "401" in str(exc_info.value)


class TestAnthropicResponseToJson:
    def test_extracts_the_json_text_block(self) -> None:
        payload = {"content": [{"type": "text", "text": json.dumps({"a": 1})}]}
        assert anthropic_response_to_json(payload, _FakeApiError) == {"a": 1}

    def test_unexpected_shape_raises_the_injected_error_class(self) -> None:
        with pytest.raises(_FakeApiError):
            anthropic_response_to_json({"unexpected": True}, _FakeApiError)


class TestMistralResponseToJson:
    def test_extracts_the_json_content(self) -> None:
        payload = {"choices": [{"message": {"content": json.dumps({"a": 1})}}]}
        assert mistral_response_to_json(payload, _FakeApiError) == {"a": 1}

    def test_unexpected_shape_raises_the_injected_error_class(self) -> None:
        with pytest.raises(_FakeApiError):
            mistral_response_to_json({"unexpected": True}, _FakeApiError)


# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md Punkt 1: der reale Token-Verbrauch steht in JEDER Provider-Antwort und wurde bisher
# gelesen und verworfen. Die beiden Extraktoren unten sind der Messpunkt der Ist-Kostenerfassung -
# providerspezifische Feldnamen, providerneutrales Ergebnis (`TokenUsage`).


class TestTokenUsage:
    def test_is_frozen(self) -> None:
        usage = TokenUsage(input_tokens=1, output_tokens=2)

        with pytest.raises(AttributeError):
            usage.input_tokens = 5  # type: ignore[misc]


class TestAnthropicUsageFromResponse:
    def test_reads_the_anthropic_field_names(self) -> None:
        usage = anthropic_usage_from_response(
            {"usage": {"input_tokens": 1590, "output_tokens": 42}}, ANTHROPIC_VISION_MODEL
        )

        assert usage == TokenUsage(input_tokens=1590, output_tokens=42)

    def test_ignores_additional_usage_fields(self) -> None:
        """Anthropic liefert zusaetzliche Cache-Felder mit - sie gehen die Ist-Rechnung nichts an
        (ADR 0051: Basis-Input/Output-Preise, kein Cache-Tarif im Spiel)."""
        usage = anthropic_usage_from_response(
            {
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                }
            },
            ANTHROPIC_VISION_MODEL,
        )

        assert usage == TokenUsage(input_tokens=10, output_tokens=20)

    def test_missing_usage_block_yields_none_and_exactly_one_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """ADR 0051 Punkt 1: eine erfolgreiche Klassifizierung darf NIEMALS daran scheitern, dass
        die Abrechnungsangabe fehlt."""
        with caplog.at_level(logging.WARNING, logger="photosort.cloud_vision"):
            usage = anthropic_usage_from_response({"content": []}, ANTHROPIC_VISION_MODEL)

        assert usage is None
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.WARNING

    def test_missing_single_field_yields_none_instead_of_raising(self) -> None:
        assert anthropic_usage_from_response(
            {"usage": {"input_tokens": 10}}, ANTHROPIC_VISION_MODEL
        ) is None

    def test_wrong_field_type_yields_none_instead_of_raising(self) -> None:
        assert anthropic_usage_from_response(
            {"usage": {"input_tokens": "viele", "output_tokens": 3}}, ANTHROPIC_VISION_MODEL
        ) is None

    def test_null_field_yields_none_instead_of_raising(self) -> None:
        assert anthropic_usage_from_response(
            {"usage": {"input_tokens": None, "output_tokens": 3}}, ANTHROPIC_VISION_MODEL
        ) is None

    def test_boolean_token_count_yields_none(self) -> None:
        """`isinstance(True, int)` ist in Python wahr - ohne eigenen Waechter wuerde `true` still
        als ein Token gezaehlt und als plausibler Abrechnungsbeleg ausgewiesen."""
        assert anthropic_usage_from_response(
            {"usage": {"input_tokens": True, "output_tokens": 3}}, ANTHROPIC_VISION_MODEL
        ) is None

    def test_negative_token_count_yields_none(self) -> None:
        """Eine negative Tokenzahl wuerde die Laufsumme (und damit den Betrag) VERKLEINERN - eine
        stille Untererfassung auf einer Seite zur Kostenkontrolle."""
        assert anthropic_usage_from_response(
            {"usage": {"input_tokens": 10, "output_tokens": -1}}, ANTHROPIC_VISION_MODEL
        ) is None

    def test_usage_block_of_wrong_shape_yields_none(self) -> None:
        assert anthropic_usage_from_response({"usage": "keine-map"}, ANTHROPIC_VISION_MODEL) is None

    def test_non_mapping_payload_yields_none(self) -> None:
        assert anthropic_usage_from_response(None, ANTHROPIC_VISION_MODEL) is None

    def test_does_not_accept_the_mistral_field_names(self) -> None:
        """Kreuz-Test (Teststrategie der Spec): die Feldnamen unterscheiden sich zwischen den
        Providern - ein versehentlich vertauschter Extraktor liefert sonst still 0 Tokens."""
        assert anthropic_usage_from_response(
            {"usage": {"prompt_tokens": 10, "completion_tokens": 20}}, ANTHROPIC_VISION_MODEL
        ) is None


class TestMistralUsageFromResponse:
    def test_reads_the_mistral_field_names(self) -> None:
        usage = mistral_usage_from_response(
            {"usage": {"prompt_tokens": 1200, "completion_tokens": 33}}, MISTRAL_VISION_MODEL
        )

        assert usage == TokenUsage(input_tokens=1200, output_tokens=33)

    def test_missing_usage_block_yields_none_and_exactly_one_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="photosort.cloud_vision"):
            usage = mistral_usage_from_response({"choices": []}, MISTRAL_VISION_MODEL)

        assert usage is None
        assert len(caplog.records) == 1

    def test_wrong_field_type_yields_none_instead_of_raising(self) -> None:
        assert mistral_usage_from_response(
            {"usage": {"prompt_tokens": {}, "completion_tokens": 1}}, MISTRAL_VISION_MODEL
        ) is None

    def test_does_not_accept_the_anthropic_field_names(self) -> None:
        assert mistral_usage_from_response(
            {"usage": {"input_tokens": 10, "output_tokens": 20}}, MISTRAL_VISION_MODEL
        ) is None


class TestUsageWarningLeaksNothing:
    """Sicherheits-Muss-Kriterium der Spec 0207 (Abschnitt Security Punkt 4, Muster ADR 0034
    Punkt 5): die WARNING-Zeile enthaelt ausschliesslich feste Meldung, `type(exc).__name__` und
    die Modell-ID - NIE die Rohantwort. Die Provider-Antwort traegt die Modellaussage ueber den
    Bildinhalt eines Familienfotos und im Fehlerfall potenziell ein Echo des Requests
    (Base64-Bilddaten) sowie Header (API-Key)."""

    _SECRET_KEY = "sk-ant-superheimlich-1234567890"
    _BASE64_ECHO = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"

    def _poisoned_payload(self) -> dict[str, object]:
        return {
            "usage": {"input_tokens": ["kaputt"], "output_tokens": 1},
            "error": {
                "message": f"upstream rejected: x-api-key={self._SECRET_KEY}",
                "echo": f"data:image/jpeg;base64,{self._BASE64_ECHO}",
            },
            "content": [{"type": "text", "text": "Ein Kind am Strand von Sylt"}],
        }

    def test_anthropic_warning_contains_neither_raw_response_nor_secrets(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="photosort.cloud_vision"):
            assert (
                anthropic_usage_from_response(self._poisoned_payload(), ANTHROPIC_VISION_MODEL)
                is None
            )

        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert self._SECRET_KEY not in logged
        assert self._BASE64_ECHO not in logged
        assert "Strand von Sylt" not in logged
        assert "upstream rejected" not in logged
        # Erlaubt und erwuenscht: Modell-ID und Exception-Typname als Diagnosehilfe.
        assert ANTHROPIC_VISION_MODEL in logged
        assert "TypeError" in logged
        assert caplog.records[0].exc_info is None

    def test_mistral_warning_contains_neither_raw_response_nor_secrets(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        payload = self._poisoned_payload()
        payload["usage"] = {"prompt_tokens": ["kaputt"], "completion_tokens": 1}

        with caplog.at_level(logging.WARNING, logger="photosort.cloud_vision"):
            assert mistral_usage_from_response(payload, MISTRAL_VISION_MODEL) is None

        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert self._SECRET_KEY not in logged
        assert self._BASE64_ECHO not in logged
        assert "Strand von Sylt" not in logged
        assert MISTRAL_VISION_MODEL in logged


# specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, decisions/0059-modellwahl-je-anbieter-
# und-modellgebundene-kostenschaetzung.md Punkt 2 ab hier: die kuratierte Registry der waehlbaren
# Modelle je Anbieter loest die fruehere 1:1-Zuordnung `VISION_MODEL_BY_PROVIDER` ab.


class TestVisionModelsByProvider:
    def test_every_configurable_provider_has_at_least_one_model(self) -> None:
        assert set(VISION_MODELS_BY_PROVIDER) == {"anthropic", "mistral"}
        for models in VISION_MODELS_BY_PROVIDER.values():
            assert models

    def test_the_registry_entries_are_ordered_immutable_tuples(self) -> None:
        """Geordnetes Tupel statt Menge (ADR 0059 Punkt 2): die Reihenfolge traegt die Aussage
        "erstes Element = Voreinstellung des Anbieters"."""
        for models in VISION_MODELS_BY_PROVIDER.values():
            assert isinstance(models, tuple)

    def test_no_model_id_is_offered_under_two_providers(self) -> None:
        """Ein doppelt gefuehrtes Modell machte die anbieterbezogene Startvalidierung sinnlos und
        die Verbrauchsannahme je Anbieter mehrdeutig."""
        all_models = [model for models in VISION_MODELS_BY_PROVIDER.values() for model in models]

        assert len(all_models) == len(set(all_models))

    def test_the_first_entry_is_the_unchanged_default_of_each_provider(self) -> None:
        """Akzeptanzkriterium "ohne gesetzte Einstellung exakt wie bisher": die Voreinstellung
        bleibt das bisher fest verdrahtete Modell.

        Bewusst gegen die AUSGESCHRIEBENEN Modell-IDs statt gegen `ANTHROPIC_VISION_MODEL`/
        `MISTRAL_VISION_MODEL` (Fund `test-engineer`): ein Vergleich mit der Konstante waere
        tautologisch und bliebe gruen, wenn jemand ihren WERT aendert - genau die stille
        Verschiebung, die dieses Akzeptanzkriterium ausschliessen soll."""
        assert VISION_MODELS_BY_PROVIDER["anthropic"][0] == "claude-haiku-4-5"
        assert VISION_MODELS_BY_PROVIDER["mistral"][0] == "ministral-3b-2512"
        # Gegenprobe, dass die Konstanten dieselbe Aussage tragen.
        assert VISION_MODELS_BY_PROVIDER["anthropic"][0] == ANTHROPIC_VISION_MODEL
        assert VISION_MODELS_BY_PROVIDER["mistral"][0] == MISTRAL_VISION_MODEL

    def test_at_least_one_provider_offers_a_real_choice(self) -> None:
        """Akzeptanzkriterium: eine Auswahl mit nur einer Moeglichkeit je Anbieter erfuellt die
        Story nicht."""
        assert any(len(models) >= 2 for models in VISION_MODELS_BY_PROVIDER.values())

    def test_the_mistral_registry_is_exactly_the_curated_pair(self) -> None:
        """specs/features/0369-mistral-small-loest-ministral-8b-ab.md, K1/K2/K3: VOLLE
        Tupel-Gleichheit statt zweier Anwesenheits-Assertionen.

        Der erste Fall im Projekt, in dem ein waehlbarer Wert ZURUECKGENOMMEN statt ergaenzt wird
        - und damit der Punkt, an dem eine Teilmengen-/Anwesenheitspruefung nicht mehr genuegt:
        `in` haette das abgeloeste `ministral-8b-2512` nie herausgezwungen, und `>= 2` haelt auch
        bei drei Modellen. Eine Assertion pinnt hier gleichzeitig die Waehlbarkeit des neuen
        Modells (K1), das Verschwinden des alten (K2), die unveraenderte Voreinstellung an
        Position 0 (K3) und die Reihenfolge "Voreinstellung zuerst".

        Bewusst gegen die AUSGESCHRIEBENEN Modell-IDs statt gegen `MISTRAL_VISION_MODEL`/
        `MISTRAL_VISION_MODEL_SMALL` (bestehende Absicht aus Spec 0304): ein Vergleich mit den
        Konstanten waere tautologisch und bliebe gruen, wenn jemand ihren WERT aendert."""
        assert VISION_MODELS_BY_PROVIDER["mistral"] == (
            "ministral-3b-2512",
            "mistral-small-2603",
        )

    def test_both_providers_offer_the_same_kind_of_choice(self) -> None:
        """Akzeptanzkriterium "beide Anbieter werden gleich behandelt; es entsteht kein Sonderweg
        fuer nur einen von beiden" - die Wahlmoeglichkeit selbst darf nicht bei einem Anbieter
        haengenbleiben."""
        for provider, models in VISION_MODELS_BY_PROVIDER.items():
            assert len(models) >= 2, provider


class TestDefaultVisionModelForProvider:
    def test_it_returns_the_first_registry_entry(self) -> None:
        assert default_vision_model_for_provider("anthropic") == ANTHROPIC_VISION_MODEL
        assert default_vision_model_for_provider("mistral") == MISTRAL_VISION_MODEL

    def test_an_unknown_provider_falls_back_to_its_own_name(self) -> None:
        """Wortgleich uebernommene Rueckfallregel der abgeloesten `vision_model_for_provider`
        (ADR 0059 Punkt 2): das Ergebnis ist dann eine Modell-ID, die `MODEL_PRICING` nicht kennt,
        und der Lauf wird als "nicht erfasst" ausgewiesen - statt einen laufenden Cloud-Job mit
        einem KeyError abzubrechen."""
        assert default_vision_model_for_provider("openai") == "openai"

    def test_every_vision_model_constant_is_offered_in_the_registry(self) -> None:
        """Gegenrichtung zur Preis-Invariante in test_pricing.py (Review-Fund `review-tests`):
        dort wird geprueft, dass jedes WAEHLBARE Modell einen Preis hat. Hier die andere Richtung -
        eine `*_VISION_MODEL`-Konstante, die in keiner Registry steht, waere ein Modell, das im
        Code existiert, aber niemand einstellen kann; typischer Zwischenstand, wenn jemand die
        Konstante ergaenzt und die Registry vergisst."""
        constants = {
            value
            for name, value in vars(cloud_vision).items()
            if "VISION_MODEL" in name and isinstance(value, str)
        }
        selectable = {model for models in VISION_MODELS_BY_PROVIDER.values() for model in models}

        assert constants, "keine *VISION_MODEL*-Konstante in cloud_vision.py gefunden"
        assert constants <= selectable


class TestProviderForVisionModel:
    """specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-
    vier-teilschritte-und-laufeigene-cloud-bilanz.md Punkt 6: die Lauf-Zeilen speichern das
    MODELL, die Bilanz nennt Modell UND Anbieter. Die fehlende Haelfte entsteht aus einer reinen
    Rueckwaertssuche ueber die Registry - nicht aus einer weiteren Spalte und nie aus
    `settings.landmark_provider`."""

    @pytest.mark.parametrize(
        "provider,model",
        [
            (provider, model)
            for provider, models in VISION_MODELS_BY_PROVIDER.items()
            for model in models
        ],
    )
    def test_every_registered_model_resolves_to_its_provider(
        self, provider: str, model: str
    ) -> None:
        """Parametrisiert AUS der Registry, nie abgeschrieben: ein kuenftig ergaenztes Modell ist
        damit automatisch mitgeprueft."""
        assert provider_for_vision_model(model) == provider

    def test_an_unknown_model_yields_none_not_a_guess(self) -> None:
        """Ein Modell, das nicht (mehr) in der Registry steht - Altlauf, entferntes Modell -
        liefert `None`. Die Oberflaeche zeigt dann die Modell-ID allein, statt einen Anbieter zu
        raten; ein geratener Anbieter waere eine Behauptung ueber einen vergangenen Lauf."""
        assert provider_for_vision_model("ein-laengst-entferntes-modell") is None

    def test_the_function_does_not_read_the_configuration(self) -> None:
        """Abwesenheits-Assertion, zwei Gruende in einem:

        1. Fachlich (ADR 0059): die AKTUELLE Betriebseinstellung sagt nichts darueber, womit ein
           VERGANGENER Lauf gerechnet hat - genau die Verwechslung, die ADR 0059 behoben hat.
        2. Strukturell (ADR 0059 Punkt 2): `config.py` importiert dieses Modul (der Validator
           braucht die Registry). Ein Import in die Gegenrichtung erzeugte einen Importzyklus.

        Geprueft ueber den AST statt ueber den Rohtext: die Modul-Kommentare NENNEN
        `photosort.config` ausdruecklich (als Verbot), eine Textsuche wuerde daran haengenbleiben
        und damit die Dokumentation der Regel bestrafen.
        """
        tree = ast.parse(Path(cloud_vision.__file__).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)

        assert not any(name.startswith("photosort") for name in imported), imported


# ---------------------------------------------------------------------------
# specs/features/0382-cloud-rate-limits-aussitzen.md, decisions/0074-cloud-vision-schrittmacher-
# je-anbieter-und-wiederholung-nur-bei-429.md ab hier: Schrittmacher (CloudRequestThrottle),
# Wartezeit-Ermittlung (retry_after_seconds) und der eine neue Sende-/Wiederholungspfad
# (post_vision_request), durch den seitdem ALLE vier Cloud-Aufrufstellen gehen.
# ---------------------------------------------------------------------------


class _RecordingSleep:
    """Aufzeichnender Ersatz fuer `asyncio.sleep` - macht Wartezeiten zu einer Liste erwarteter
    Zahlen (Teststrategie der Spec 0382, Abschnitt 1: "beide ohne echte Wartezeit"). Das
    `await asyncio.sleep(0)` haelt den Ablauf ein echter Abgabepunkt an den Event-Loop, damit die
    Nebenlaeufigkeits-Faelle (asyncio.gather) ueberhaupt verschraenken KOENNEN - genau das macht
    den Atomaritaetsnachweis unten aussagekraeftig."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        await asyncio.sleep(0)


class _AdvancingClock:
    """Fortschreitende Uhr: ihr `sleep` addiert die Wartezeit auf `now`, und der Test darf `now`
    selbst weiterstellen (Teststrategie der Spec 0382, Abschnitt 1, Double (b))."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now
        self.calls: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)
        self.now += seconds
        await asyncio.sleep(0)


class TestCloudRequestThrottle:
    """K4: Mindestabstand zwischen zwei Anfragen an denselben Anbieter - kein Token-Bucket, kein
    Stoss (ADR 0074 Entscheidung 2)."""

    async def test_the_first_request_never_waits(self) -> None:
        sleep = _RecordingSleep()
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=1.0, clock=lambda: 0.0, sleep=sleep
        )

        await throttle.acquire()

        assert sleep.calls == []
        assert throttle.stats().delayed_requests == 0

    async def test_the_second_request_waits_exactly_one_interval(self) -> None:
        sleep = _RecordingSleep()
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=1.5, clock=lambda: 0.0, sleep=sleep
        )

        await throttle.acquire()
        await throttle.acquire()

        assert sleep.calls == [1.5]
        assert throttle.stats().delayed_requests == 1
        assert throttle.stats().total_delay_seconds == pytest.approx(1.5)

    async def test_it_does_not_brake_retroactively(self) -> None:
        """Ist zwischen zwei Aufrufen mehr als `min_interval` vergangen, wartet der zweite NICHT -
        der Schrittmacher holt eine bereits verstrichene Pause nicht nach."""
        clock = _AdvancingClock()
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=1.0, clock=clock, sleep=clock.sleep
        )

        await throttle.acquire()
        clock.now += 10.0
        await throttle.acquire()

        assert clock.calls == []
        assert throttle.stats().delayed_requests == 0

    async def test_a_zero_interval_means_no_throttling_at_all(self) -> None:
        """`min_interval_seconds=0.0` ist ein GUELTIGER Wert - die Bauform, mit der die
        bestehenden Client-Tests konstruieren. Kein `sleep`-Aufruf, kein Zaehlerstand."""
        sleep = _RecordingSleep()
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=0.0, clock=lambda: 0.0, sleep=sleep
        )

        for _ in range(5):
            await throttle.acquire()

        assert sleep.calls == []
        assert throttle.stats().delayed_requests == 0
        assert throttle.stats().total_delay_seconds == 0.0

    async def test_five_concurrent_acquires_are_spaced_without_a_duplicate(self) -> None:
        """Sperrenfreiheit/Atomaritaet (Entwurfsentscheidung 2 der Spec): zwischen dem Lesen und
        dem Zurueckschreiben des naechsten freien Zeitpunkts darf KEIN `await` stehen. Genau
        dieser Fall wird rot, wenn doch eines dort steht - dann bekaemen mehrere gleichzeitige
        Aufrufer denselben Startzeitpunkt.

        Der erste der fuenf Aufrufer ist der `0 x min_interval`-Fall: er wartet gar nicht und
        erzeugt deshalb keinen `sleep`-Aufruf. Aufgezeichnet werden die vier uebrigen."""
        sleep = _RecordingSleep()
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=2.0, clock=lambda: 0.0, sleep=sleep
        )

        await asyncio.gather(*(throttle.acquire() for _ in range(5)))

        assert sorted(sleep.calls) == [2.0, 4.0, 6.0, 8.0]
        assert len(set(sleep.calls)) == len(sleep.calls)
        assert throttle.stats().delayed_requests == 4

    async def test_a_cancellation_from_the_sleep_propagates_unchanged(self) -> None:
        """K7: ein Abbruch (JOB_TIMEOUT_SECONDS/Worker-Shutdown) laeuft durch den Wartevorgang
        HINDURCH - `acquire()` faengt kein `BaseException`."""

        async def cancelling_sleep(seconds: float) -> None:
            raise asyncio.CancelledError

        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=1.0, clock=lambda: 0.0, sleep=cancelling_sleep
        )

        await throttle.acquire()
        with pytest.raises(asyncio.CancelledError):
            await throttle.acquire()


class TestThrottleStats:
    def test_since_returns_the_difference(self) -> None:
        before = cloud_vision.ThrottleStats(
            delayed_requests=3,
            total_delay_seconds=6.0,
            retries=1,
            total_retry_wait_seconds=2.0,
        )
        after = cloud_vision.ThrottleStats(
            delayed_requests=5,
            total_delay_seconds=10.0,
            retries=4,
            total_retry_wait_seconds=30.0,
        )

        diff = after.since(before)

        assert diff == cloud_vision.ThrottleStats(
            delayed_requests=2,
            total_delay_seconds=4.0,
            retries=3,
            total_retry_wait_seconds=28.0,
        )

    def test_since_never_returns_negative_values(self) -> None:
        """Die Zaehler sind prozessweit; ein Schnappschuss, der (wie auch immer) juenger ist als
        der spaetere Abruf, darf keine negative "gewartete Zeit" in eine Logzeile tragen."""
        early = cloud_vision.ThrottleStats(
            delayed_requests=0, total_delay_seconds=0.0, retries=0, total_retry_wait_seconds=0.0
        )
        later = cloud_vision.ThrottleStats(
            delayed_requests=7, total_delay_seconds=9.0, retries=2, total_retry_wait_seconds=4.0
        )

        diff = early.since(later)

        assert diff == cloud_vision.ThrottleStats(
            delayed_requests=0, total_delay_seconds=0.0, retries=0, total_retry_wait_seconds=0.0
        )

    async def test_the_retry_counters_come_from_the_throttle(self) -> None:
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=0.0, clock=lambda: 0.0, sleep=_RecordingSleep()
        )
        before = throttle.stats()

        throttle.record_retry_wait(2.0)
        throttle.record_retry_wait(4.0)

        diff = throttle.stats().since(before)
        assert diff.retries == 2
        assert diff.total_retry_wait_seconds == pytest.approx(6.0)
