from __future__ import annotations

import ast
import asyncio
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
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


def _response_with_headers(headers: dict[str, str]) -> httpx.Response:
    return httpx.Response(429, headers=headers)


class TestRetryAfterSeconds:
    """K2: die Anbieterangabe zur Wartezeit - in beiden vom HTTP-Standard erlaubten Formen.
    "Nicht auswertbar" ist ausdruecklich KEIN Fehler, sondern "keine Angabe"."""

    def test_integer_seconds_are_read(self) -> None:
        assert cloud_vision.retry_after_seconds(
            _response_with_headers({"Retry-After": "30"})
        ) == pytest.approx(30.0)

    @pytest.mark.parametrize("raw", ["nan", "NaN", "inf", "-inf", "Infinity"])
    def test_non_finite_values_are_no_information(self, raw: str) -> None:
        """Sicherheits-Muss-Kriterium der Spec 0382 (Punkt 2a): `float("nan")`/`float("inf")`
        PARSEN ERFOLGREICH. Ohne `math.isfinite` fielen beide Zeit-Deckel lautlos aus -
        `min(float("nan"), 60.0)` liefert `nan`, und `nan > budget` ist immer False."""
        response = _response_with_headers({"Retry-After": raw})
        assert cloud_vision.retry_after_seconds(response) is None

    @pytest.mark.parametrize("raw", ["0", "-5", "-0.5"])
    def test_zero_or_negative_is_no_information(self, raw: str) -> None:
        """Punkt 2c: niemals eine negative Zahl zurueckgeben - die Gefahr ist nicht
        `asyncio.sleep(-5)` (das kehrt sofort zurueck), sondern ein negativer Summand, der das
        Restbudget VERGROESSERT."""
        response = _response_with_headers({"Retry-After": raw})
        assert cloud_vision.retry_after_seconds(response) is None

    @pytest.mark.parametrize("raw", ["", "   ", "bald", "1,5", "9" * 5000])
    def test_missing_empty_or_unparsable_values_are_no_information(self, raw: str) -> None:
        """Punkt 2b: die Funktion traegt KEINE Exception aus dem Header nach aussen -
        `parsedate_to_datetime("garbage")` wirft `ValueError`, eine sehr lange Ziffernfolge
        laeuft in die `sys.set_int_max_str_digits`-Grenze bzw. auf `inf`."""
        response = _response_with_headers({"Retry-After": raw})
        assert cloud_vision.retry_after_seconds(response) is None

    def test_a_missing_header_is_no_information(self) -> None:
        assert cloud_vision.retry_after_seconds(_response_with_headers({})) is None

    def test_retry_after_ms_is_deliberately_ignored(self) -> None:
        """ADR 0074 Entscheidung 5: `retry-after-ms` wird bewusst NICHT ausgewertet."""
        assert (
            cloud_vision.retry_after_seconds(_response_with_headers({"retry-after-ms": "500"}))
            is None
        )

    def test_an_http_date_in_the_future_is_read_against_the_injected_now(self) -> None:
        now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)
        target = format_datetime(now + timedelta(seconds=45), usegmt=True)

        result = cloud_vision.retry_after_seconds(
            _response_with_headers({"Retry-After": target}), now=now
        )

        assert result == pytest.approx(45.0)

    def test_an_http_date_in_the_past_is_no_information(self) -> None:
        now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)
        target = format_datetime(now - timedelta(seconds=45), usegmt=True)

        assert (
            cloud_vision.retry_after_seconds(
                _response_with_headers({"Retry-After": target}), now=now
            )
            is None
        )

    def test_a_naive_http_date_is_read_as_utc(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Der Fall braucht eine VERSTELLTE Prozess-Zeitzone: auf einer UTC-Maschine waere eine
        Implementierung, die ein zonenloses Datum als ORTSZEIT liest, sonst zufaellig gruen."""
        monkeypatch.setenv("TZ", "Asia/Tokyo")
        time.tzset()
        try:
            now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=UTC)
            # Zonenloses Datum (kein "GMT"-Suffix) - genau 45 s nach `now`, in UTC gelesen.
            naive = "Thu, 10 Sep 2026 12:00:45"

            result = cloud_vision.retry_after_seconds(
                _response_with_headers({"Retry-After": naive}), now=now
            )

            assert result == pytest.approx(45.0)
        finally:
            monkeypatch.undo()
            time.tzset()

    def test_a_naive_reference_time_is_treated_as_utc_as_well(self) -> None:
        now = datetime(2026, 9, 10, 12, 0, 0)
        target = format_datetime(datetime(2026, 9, 10, 12, 0, 20, tzinfo=UTC), usegmt=True)

        result = cloud_vision.retry_after_seconds(
            _response_with_headers({"Retry-After": target}), now=now
        )

        assert result == pytest.approx(20.0)

    def test_without_an_injected_now_the_current_time_is_used(self) -> None:
        target = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)

        result = cloud_vision.retry_after_seconds(_response_with_headers({"Retry-After": target}))

        assert result is not None
        assert 25.0 <= result <= 30.0


def _no_throttle(sleep: _RecordingSleep | None = None) -> cloud_vision.CloudRequestThrottle:
    """Schrittmacher ohne Mindestabstand und mit aufzeichnendem `sleep` - die Bauform, mit der
    die Integrationsfaelle von `post_vision_request` konstruieren: keine Einreihung (die wird
    getrennt geprueft), aber jede Wiederholungs-Wartezeit als Zahl in einer Liste."""
    return cloud_vision.CloudRequestThrottle(
        min_interval_seconds=0.0, clock=lambda: 0.0, sleep=sleep or _RecordingSleep()
    )


class _SequenceTransport(httpx.AsyncBaseTransport):
    """MockTransport-Ersatz mit Antwortliste und Aufrufzaehler. Ein Listeneintrag ist entweder
    eine `httpx.Response` oder eine zu werfende Exception; ist die Liste erschoepft, wird der
    letzte Eintrag wiederholt (der "dauerhaft 429"-Fall)."""

    def __init__(self, responses: list[httpx.Response | Exception]) -> None:
        self._responses = responses
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        index = min(len(self.requests) - 1, len(self._responses) - 1)
        entry = self._responses[index]
        if isinstance(entry, Exception):
            raise entry
        return httpx.Response(
            entry.status_code, headers=entry.headers, content=entry.content, request=request
        )


def _ok(payload: dict[str, object] | None = None) -> httpx.Response:
    return httpx.Response(200, json=payload or {"ok": True})


def _rate_limited(retry_after: str | None = None, **kwargs: object) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(429, headers=headers, **kwargs)  # type: ignore[arg-type]


class TestVisionEndpoints:
    """Die anbieterspezifischen Endpunkt-Tatsachen als je ein Konstantenwert - die Meldungstexte
    und Statuslabels bleiben dabei WORTGLEICH zu den bisher an den vier Aufrufstellen
    eingebetteten (Regressionspflicht der Spec 0382)."""

    def test_the_anthropic_endpoint_carries_the_unchanged_facts(self) -> None:
        assert cloud_vision.ANTHROPIC_ENDPOINT.url == ANTHROPIC_MESSAGES_URL
        assert cloud_vision.ANTHROPIC_ENDPOINT.provider == "anthropic"
        assert cloud_vision.ANTHROPIC_ENDPOINT.status_label == "Anthropic"
        assert cloud_vision.ANTHROPIC_ENDPOINT.unreachable_label == "Anthropic Vision API"

    def test_the_mistral_endpoint_carries_the_unchanged_facts(self) -> None:
        assert cloud_vision.MISTRAL_ENDPOINT.url == MISTRAL_CHAT_COMPLETIONS_URL
        assert cloud_vision.MISTRAL_ENDPOINT.provider == "mistral"
        assert cloud_vision.MISTRAL_ENDPOINT.status_label == "Mistral"
        assert cloud_vision.MISTRAL_ENDPOINT.unreachable_label == "Mistral Chat Completions API"

    def test_the_endpoint_providers_match_the_model_registry(self) -> None:
        providers = {
            cloud_vision.ANTHROPIC_ENDPOINT.provider,
            cloud_vision.MISTRAL_ENDPOINT.provider,
        }
        assert providers == set(VISION_MODELS_BY_PROVIDER)


class TestPostVisionRequest:
    """K1/K3/K5/K7/K8: der EINE Sende- und Wiederholungspfad, durch den alle vier Aufrufstellen
    gehen (K6)."""

    async def _post(
        self,
        transport: _SequenceTransport,
        throttle: cloud_vision.CloudRequestThrottle,
    ) -> httpx.Response:
        async with httpx.AsyncClient(transport=transport) as client:
            return await cloud_vision.post_vision_request(
                client,
                cloud_vision.ANTHROPIC_ENDPOINT,
                {"model": "irrelevant"},
                error_class=_FakeApiError,
                throttle=throttle,
            )

    async def test_a_success_on_the_first_attempt_sends_exactly_once(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        transport = _SequenceTransport([_ok({"hello": "world"})])
        sleep = _RecordingSleep()

        with caplog.at_level(logging.WARNING, logger="photosort.cloud_vision"):
            response = await self._post(transport, _no_throttle(sleep))

        assert response.json() == {"hello": "world"}
        assert len(transport.requests) == 1
        assert sleep.calls == []
        assert caplog.records == []

    async def test_a_429_followed_by_a_200_returns_the_200(self) -> None:
        """K1/K9: folgt auf ein `429` ein `200`, ist dessen Ergebnis das Ergebnis des Aufrufs -
        das Foto wird nicht uebersprungen."""
        transport = _SequenceTransport([_rate_limited(), _ok({"hello": "world"})])
        sleep = _RecordingSleep()

        response = await self._post(transport, _no_throttle(sleep))

        assert response.status_code == 200
        assert response.json() == {"hello": "world"}
        assert len(transport.requests) == 2
        assert sleep.calls == [2.0]

    async def test_a_permanent_429_gives_up_after_five_attempts(self) -> None:
        """K1/K3: hoechstens fuenf Versuche insgesamt, Staffel `2, 4, 8, 16` - und am Ende die
        UEBERGEBENE Fehlerklasse mit dem `429` im Text (dieselbe Meldung wie heute, aus
        `raise_for_vision_api_status`)."""
        transport = _SequenceTransport([_rate_limited()])
        sleep = _RecordingSleep()

        with pytest.raises(_FakeApiError) as excinfo:
            await self._post(transport, _no_throttle(sleep))

        assert "429" in str(excinfo.value)
        assert len(transport.requests) == 5
        assert sleep.calls == [2.0, 4.0, 8.0, 16.0]

    async def test_a_provider_hint_beats_the_backoff_ladder(self) -> None:
        transport = _SequenceTransport([_rate_limited("5"), _ok()])
        sleep = _RecordingSleep()

        await self._post(transport, _no_throttle(sleep))

        assert sleep.calls == [5.0]

    async def test_the_ladder_hangs_on_the_attempt_counter_not_on_its_own_use(self) -> None:
        """K3 (Anmerkung der Spec): eine einzelne Anbieterangabe dazwischen setzt die Staffel
        NICHT zurueck - "ohne / 5 / ohne" ergibt `2, 5, 8`, nicht `2, 5, 4`. Sonst koennte ein
        Anbieter mit einer einzigen kleinen Angabe die gesamte Staffel flachhalten."""
        transport = _SequenceTransport(
            [_rate_limited(), _rate_limited("5"), _rate_limited(), _ok()]
        )
        sleep = _RecordingSleep()

        await self._post(transport, _no_throttle(sleep))

        assert sleep.calls == [2.0, 5.0, 8.0]

    async def test_a_single_wait_is_capped(self) -> None:
        """K3: ein Anbieter, der mehr als 60 s verlangt, bekommt sie nicht."""
        transport = _SequenceTransport([_rate_limited("1200"), _ok()])
        sleep = _RecordingSleep()

        await self._post(transport, _no_throttle(sleep))

        assert sleep.calls == [60.0]

    async def test_an_exhausted_budget_gives_up_instead_of_waiting_a_shortened_time(self) -> None:
        """K7: reicht das Restbudget fuer die geforderte Wartezeit nicht, wird SOFORT aufgegeben
        statt gekuerzt gewartet - eine halbe Wartezeit fuehrt auf denselben `429` und verbrennt
        eine Anfrage. Drei Anfragen statt fuenf, Summe exakt das Budget."""
        transport = _SequenceTransport([_rate_limited("60")])
        sleep = _RecordingSleep()

        with pytest.raises(_FakeApiError):
            await self._post(transport, _no_throttle(sleep))

        assert sleep.calls == [60.0, 60.0]
        assert sum(sleep.calls) == pytest.approx(cloud_vision.VISION_RETRY_BUDGET_SECONDS)
        assert len(transport.requests) == 3

    @pytest.mark.parametrize("status_code", [500, 502, 529, 401, 403, 400, 404])
    async def test_no_other_status_is_ever_retried(self, status_code: int) -> None:
        """K5 und Sicherheits-Muss-Kriterium der Spec 0382 (Punkt 3): die Wiederholungsbedingung
        ist exakt `== 429`. Ein weiter gefasstes Praedikat zoege Anthropics `529` und jedes `5xx`
        mit hinein - und, sicherheitlich relevanter, auch `401`/`403`: eine Wiederholung nach
        ungueltigen oder gesperrten Zugangsdaten sendet denselben API-Key fuenfmal gegen einen
        Endpunkt, der ihn gerade abgelehnt hat."""
        transport = _SequenceTransport([httpx.Response(status_code)])
        sleep = _RecordingSleep()

        with pytest.raises(_FakeApiError):
            await self._post(transport, _no_throttle(sleep))

        assert len(transport.requests) == 1
        assert sleep.calls == []

    @pytest.mark.parametrize(
        "exc",
        [
            httpx.ConnectError("Connection refused"),
            httpx.ReadTimeout("timed out"),
        ],
    )
    async def test_a_network_error_is_never_retried(self, exc: Exception) -> None:
        transport = _SequenceTransport([exc])
        sleep = _RecordingSleep()

        with pytest.raises(_FakeApiError) as excinfo:
            await self._post(transport, _no_throttle(sleep))

        assert "Anthropic Vision API nicht erreichbar" in str(excinfo.value)
        assert len(transport.requests) == 1
        assert sleep.calls == []

    async def test_every_attempt_goes_through_the_throttle(self) -> None:
        """K4: vor JEDEM Absenden - erster Versuch wie jede Wiederholung. Bei eingefrorener Uhr
        und `min_interval > 0` reiht sich der erste nicht ein (er wartet nie), die vier
        Wiederholungen schon."""
        transport = _SequenceTransport([_rate_limited()])
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=1.0, clock=lambda: 0.0, sleep=_RecordingSleep()
        )

        with pytest.raises(_FakeApiError):
            await self._post(transport, throttle)

        assert len(transport.requests) == 5
        assert throttle.stats().delayed_requests == 4
        assert throttle.stats().retries == 4
        assert throttle.stats().total_retry_wait_seconds == pytest.approx(30.0)

    async def test_a_cancellation_during_the_wait_is_not_turned_into_the_error_class(self) -> None:
        """K7: ein Abbruch (`asyncio.CancelledError` aus `JOB_TIMEOUT_SECONDS` oder einem
        Worker-Shutdown) laeuft durch den Wartevorgang HINDURCH und wird NICHT in die
        feature-eigene Fehlerklasse umgewandelt - sonst waere der Job unabbrechbar."""

        async def cancelling_sleep(seconds: float) -> None:
            raise asyncio.CancelledError

        transport = _SequenceTransport([_rate_limited()])
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=0.0, clock=lambda: 0.0, sleep=cancelling_sleep
        )

        with pytest.raises(asyncio.CancelledError):
            await self._post(transport, throttle)

    async def test_each_retry_logs_exactly_one_warning_line(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """K8: je Wiederholung EINE WARNING-Zeile mit Anbieter, Versuchszaehler, gewarteter Zeit
        und deren Herkunft."""
        transport = _SequenceTransport([_rate_limited(), _rate_limited("5"), _ok()])

        with caplog.at_level(logging.WARNING, logger="photosort.cloud_vision"):
            await self._post(transport, _no_throttle())

        assert len(caplog.records) == 2
        assert all(record.levelno == logging.WARNING for record in caplog.records)
        first, second = (record.getMessage() for record in caplog.records)
        assert "anthropic" in first
        assert "2.0" in first
        assert "Staffel" in first
        assert "5.0" in second
        assert "Anbieterangabe" in second

    async def test_the_log_line_leaks_neither_the_raw_header_nor_the_response_body(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Sicherheits-Muss-Kriterium der Spec 0382 (Punkt 4): in `post_vision_request` liegen der
        Request-Body (die base64-kodierten Bilddaten) und der Key-tragende Client im selben
        Sichtbereich wie die neue Zeile. Erlaubt sind ausschliesslich das `provider`-Feld des
        eigenen Konstantenwerts, der Versuchszaehler, die bereits geparste und gedeckelte
        Wartezeit und ein festes Literal fuer deren Herkunft - der ROHE Headerwert ist zugleich
        die einzige Log-Injection-Flaeche des Features und bleibt draussen."""
        transport = _SequenceTransport(
            [
                _rate_limited("voellig-kaputt-4711", json={"marker": "GEHEIM-4712"}),
                _ok(),
            ]
        )

        with caplog.at_level(logging.WARNING, logger="photosort.cloud_vision"):
            await self._post(transport, _no_throttle())

        assert "2.0" in caplog.text
        assert "4711" not in caplog.text
        assert "GEHEIM-4712" not in caplog.text
        assert "Retry-After" not in caplog.text
        assert "retry-after" not in caplog.text.lower()

    async def test_it_never_follows_a_redirect(self) -> None:
        """Sicherheits-Muss-Kriterium der Spec 0382 (Punkt 7): kein `follow_redirects`, kein `3xx`
        als wiederholbar - sonst gingen API-Key und Bilddaten an ein vom Anbieter benanntes
        fremdes Ziel. Genau EINE Anfrage, und zwar an die Endpunkt-Konstante; die Weiterleitung
        wird unveraendert an die Aufrufstelle zurueckgegeben, wo ihre Antwortstruktur wie jede
        andere unerwartete zum gewohnten best-effort-Skip fuehrt."""
        sleep = _RecordingSleep()
        transport = _SequenceTransport(
            [httpx.Response(302, headers={"Location": "https://example.invalid/anders"})]
        )

        response = await self._post(transport, _no_throttle(sleep))

        assert response.status_code == 302
        assert len(transport.requests) == 1
        assert str(transport.requests[0].url) == ANTHROPIC_MESSAGES_URL
        assert sleep.calls == []

    async def test_the_body_is_sent_as_json_to_the_endpoint_url(self) -> None:
        transport = _SequenceTransport([_ok()])

        async with httpx.AsyncClient(transport=transport) as client:
            await cloud_vision.post_vision_request(
                client,
                cloud_vision.MISTRAL_ENDPOINT,
                {"model": "m", "messages": []},
                error_class=_FakeApiError,
                throttle=_no_throttle(),
            )

        request = transport.requests[0]
        assert str(request.url) == MISTRAL_CHAT_COMPLETIONS_URL
        assert json.loads(request.content) == {"model": "m", "messages": []}


class TestWaitBudgetStaysUnderTheStallThreshold:
    """K7 als INVARIANTENTEST (Bauform wie die Registry-Preistabelle-Invariante in
    test_pricing.py): der Test importiert `STALL_THRESHOLD` aus `worker.py` und die vier
    Konstanten aus `cloud_vision.py`. Im Produktivcode gibt es diese Verbindung bewusst NICHT -
    `cloud_vision.py` darf `worker.py` nicht importieren."""

    # Benannter Sicherheitsabstand: was zwischen dem schlimmsten Wartefall und der Schwelle des
    # Fortschritts-Watchdogs mindestens frei bleiben muss.
    SAFETY_MARGIN_SECONDS = 300.0

    def _worst_case_seconds(self) -> float:
        return (
            cloud_vision.VISION_RETRY_BUDGET_SECONDS
            + cloud_vision.VISION_MAX_RATE_LIMIT_ATTEMPTS * VISION_REQUEST_TIMEOUT_SECONDS
        )

    def test_the_worst_case_stays_under_the_stall_threshold(self) -> None:
        from photosort.worker import STALL_THRESHOLD

        assert (
            self._worst_case_seconds() + self.SAFETY_MARGIN_SECONDS
            < STALL_THRESHOLD.total_seconds()
        )

    def test_the_worst_case_is_nailed_to_the_documented_420_seconds(self) -> None:
        """Sonst verschoebe ein Anheben einer Konstante die Rechnung STILL, waehrend Spec, ADR und
        docs/architecture.md weiter 420 s behaupten."""
        assert self._worst_case_seconds() == pytest.approx(420.0)

    def test_the_full_backoff_ladder_fits_into_the_budget(self) -> None:
        """Sonst waere die zugesagte Versuchszahl auf dem staffelgetriebenen Pfad (Mistrals
        Normalfall, dort ist kein `Retry-After` dokumentiert) unerreichbar."""
        ladder = [
            cloud_vision.VISION_INITIAL_RETRY_WAIT_SECONDS * 2**step
            for step in range(cloud_vision.VISION_MAX_RATE_LIMIT_ATTEMPTS - 1)
        ]
        assert ladder == [2.0, 4.0, 8.0, 16.0]
        assert sum(ladder) <= cloud_vision.VISION_RETRY_BUDGET_SECONDS

    def test_the_caps_are_internally_consistent(self) -> None:
        assert (
            cloud_vision.VISION_MAX_SINGLE_WAIT_SECONDS
            <= cloud_vision.VISION_RETRY_BUDGET_SECONDS
        )
        assert cloud_vision.VISION_MAX_RATE_LIMIT_ATTEMPTS >= 1
        assert cloud_vision.VISION_INITIAL_RETRY_WAIT_SECONDS > 0

    def test_for_the_default_settings_the_queueing_of_a_full_block_fits_as_well(self) -> None:
        """Restrisiko (c) der Spec: eine sehr kleine Rate zusammen mit erhoehter `*_CONCURRENCY`
        kann die Einreihung eines Blocks ueber die Schwelle heben. Fuer die VOREINSTELLUNGEN ist
        das ausgeschlossen - und dieser Test haelt es so fest, damit ein spaeteres Absenken einer
        Voreinstellung nicht still daran vorbeilaeuft.

        Dieser Test darf `config.py`/`cloud_vision_throttle.py` importieren; der Produktivcode in
        `cloud_vision.py` darf das nicht."""
        from photosort.cloud_vision_throttle import build_throttles
        from photosort.config import Settings
        from photosort.worker import STALL_THRESHOLD

        settings = Settings()
        concurrency = max(
            settings.landmark_api_concurrency,
            settings.remote_category_classification_concurrency,
        )
        slowest_interval = max(
            throttle.min_interval_seconds for throttle in build_throttles(settings).values()
        )
        queueing = (concurrency - 1) * slowest_interval

        assert (
            queueing + self._worst_case_seconds() + self.SAFETY_MARGIN_SECONDS
            < STALL_THRESHOLD.total_seconds()
        )
