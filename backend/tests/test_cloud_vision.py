from __future__ import annotations

import json

import httpx
import pytest

from photosort.cloud_vision import (
    ANTHROPIC_API_VERSION,
    ANTHROPIC_MESSAGES_URL,
    ANTHROPIC_VISION_MODEL,
    MISTRAL_CHAT_COMPLETIONS_URL,
    MISTRAL_VISION_MODEL,
    VISION_REQUEST_TIMEOUT_SECONDS,
    anthropic_response_to_json,
    mistral_response_to_json,
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
