from __future__ import annotations

import json
import logging

import httpx
import pytest

from photosort.cloud_vision import (
    ANTHROPIC_API_VERSION,
    ANTHROPIC_MESSAGES_URL,
    ANTHROPIC_VISION_MODEL,
    MISTRAL_CHAT_COMPLETIONS_URL,
    MISTRAL_VISION_MODEL,
    VISION_REQUEST_TIMEOUT_SECONDS,
    TokenUsage,
    anthropic_response_to_json,
    anthropic_usage_from_response,
    mistral_response_to_json,
    mistral_usage_from_response,
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
