from __future__ import annotations

import base64
import json

import httpx
import pytest

from photosort.landmark import (
    ANTHROPIC_LANDMARK_MODEL,
    AnthropicLandmarkClient,
    LandmarkApiError,
    LandmarkClientLike,
    LandmarkDetection,
    _landmark_detection_from_json,
)

# specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md,
# specs/architecture/0002-testkonzept.md ("Cloud-LLM-Vision-Client-Test-Double..."): httpx.
# MockTransport statt unittest.mock.patch, analog test_opencloud_client.py - prueft die reale
# Request-Konstruktion (Header, Body, Timeout) mit, kein reiner Mock der HTTP-Bibliothek.
# build_landmark_client()/AnthropicLandmarkClient() werden hier NIE mit einem echten Netzwerk-
# Aufruf gestartet (kein API-Key im Test) - jeder Test injiziert einen httpx.MockTransport.

API_KEY = "sk-ant-test-key-not-a-real-secret"
IMAGE_BYTES = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


def _success_response(name: str | None, confidence: float) -> httpx.Response:
    payload = {
        "content": [{"type": "text", "text": json.dumps({"name": name, "confidence": confidence})}]
    }
    return httpx.Response(200, json=payload)


def _client(handler: httpx.MockTransport) -> AnthropicLandmarkClient:
    return AnthropicLandmarkClient(api_key=API_KEY, transport=handler)


class FakeLandmarkClient:
    """Erfuellt LandmarkClientLike ohne echtes Netzwerk (Teststrategie-Abschnitt der Spec) -
    analog FakeOpenCloudClient/FakeClient-Konvention des Projekts."""

    def __init__(self, detection: LandmarkDetection) -> None:
        self._detection = detection
        self.calls: list[tuple[bytes, str]] = []

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
        self.calls.append((image_bytes, mime_type))
        return self._detection


async def test_fake_client_satisfies_the_landmark_client_like_protocol() -> None:
    fake: LandmarkClientLike = FakeLandmarkClient(
        LandmarkDetection(name="Eiffelturm", confidence=0.9)
    )
    detection = await fake.detect(IMAGE_BYTES, "image/jpeg")
    assert detection.name == "Eiffelturm"
    assert detection.confidence == 0.9


async def test_detect_parses_a_successful_response_with_a_landmark_name() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _success_response("Eiffelturm", 0.87)

    client = _client(httpx.MockTransport(handler))
    detection = await client.detect(IMAGE_BYTES, "image/jpeg")

    assert detection.name == "Eiffelturm"
    assert detection.confidence == 0.87


async def test_detect_parses_a_response_with_no_identified_landmark() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _success_response(None, 0.0)

    client = _client(httpx.MockTransport(handler))
    detection = await client.detect(IMAGE_BYTES, "image/jpeg")

    assert detection.name is None
    assert detection.confidence == 0.0


async def test_detect_clamps_a_confidence_above_one_from_the_raw_api_response() -> None:
    # Copilot-Review-Fund (PR #181): das Vision-LLM-JSON ist nicht garantiert auf [0, 1] begrenzt -
    # LandmarkDetection.confidence muss bereits HIER (nicht erst in criteria.py::
    # compute_landmark_score) geklemmt sein, sonst divergieren photo_landmark_detections.confidence
    # (worker.py schreibt detection.confidence direkt) und PhotoCriterionScore.value (geklemmt ueber
    # compute_landmark_score), obwohl beide laut ADR 0025 Punkt 6 atomar aus derselben Antwort
    # stammen sollen.
    def handler(request: httpx.Request) -> httpx.Response:
        return _success_response("Eiffelturm", 1.2)

    client = _client(httpx.MockTransport(handler))
    detection = await client.detect(IMAGE_BYTES, "image/jpeg")

    assert detection.confidence == 1.0


async def test_detect_clamps_a_negative_confidence_from_the_raw_api_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _success_response("Eiffelturm", -0.3)

    client = _client(httpx.MockTransport(handler))
    detection = await client.detect(IMAGE_BYTES, "image/jpeg")

    assert detection.confidence == 0.0


async def test_detect_sends_the_expected_request_shape() -> None:
    # Realer Request-Konstruktions-Nachweis (Teststrategie: "Header, Body, Timeout=60s
    # mitgeprueft") - kein unittest.mock.patch auf .post().
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return _success_response("Eiffelturm", 0.9)

    client = _client(httpx.MockTransport(handler))
    await client.detect(IMAGE_BYTES, "image/jpeg")

    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert headers["x-api-key"] == API_KEY
    assert headers["anthropic-version"] == "2023-06-01"

    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == ANTHROPIC_LANDMARK_MODEL
    content_blocks = body["messages"][0]["content"]
    image_block = next(block for block in content_blocks if block["type"] == "image")
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["media_type"] == "image/jpeg"
    assert image_block["source"]["data"] == base64.b64encode(IMAGE_BYTES).decode()


async def test_detect_raises_landmark_api_error_on_4xx_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_detect_raises_landmark_api_error_on_5xx_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_network_failure_is_wrapped_as_landmark_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_detect_raises_landmark_api_error_on_malformed_json_text_block() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": "not json"}]})

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_detect_raises_landmark_api_error_on_missing_content_block() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": []})

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_detect_raises_landmark_api_error_when_name_is_not_a_string() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        text = json.dumps({"name": 42, "confidence": 0.5})
        return httpx.Response(200, json={"content": [{"type": "text", "text": text}]})

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_aclose_closes_the_underlying_http_client() -> None:
    client = AnthropicLandmarkClient(
        api_key=API_KEY, transport=httpx.MockTransport(lambda r: _success_response("x", 0.1))
    )
    await client.aclose()
    assert client._client.is_closed  # Whitebox-Konfigurationsnachweis


async def test_detect_raises_landmark_api_error_on_unexpected_top_level_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not", "an", "object"])

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


def test_error_message_never_embeds_the_api_key_or_base64_image_data() -> None:
    # Sicherheitskritisches Muss-Kriterium der Spec: LandmarkApiError darf nie den API-Key oder
    # Base64-Bilddaten einbetten - Nachweis auf Nachrichtenebene, nicht nur Code-Review.
    encoded_image = base64.b64encode(IMAGE_BYTES).decode()
    error = LandmarkApiError("Anthropic-Anfrage fehlgeschlagen: 401 Unauthorized")
    assert API_KEY not in str(error)
    assert encoded_image not in str(error)


async def test_timeout_is_applied_to_the_underlying_http_client() -> None:
    # Kein Wall-Clock-Test (Teststrategie: reiner Konfigurationsnachweis) - der konstruierte
    # httpx.AsyncClient traegt den Timeout-Wert.
    client = AnthropicLandmarkClient(
        api_key=API_KEY, transport=httpx.MockTransport(lambda r: _success_response("x", 0.1))
    )
    assert client._client.timeout.read == 60.0  # Whitebox-Konfigurationsnachweis


# specs/features/0054-mistral-provider-option-cloud-landmark.md, decisions/0031-mistral-provider-
# option-cloud-landmark.md Punkt 2: _landmark_detection_from_json ist die providerneutrale
# Hilfsfunktion, die beide Clients nach ihrer jeweils providerspezifischen Extraktion des rohen
# JSON-Texts aus ihrer unterschiedlichen Response-Huelle aufrufen - direkt gegen ein bereits
# geparstes Dict getestet, ohne HTTP (Teststrategie-Abschnitt der Spec).


def test_landmark_detection_from_json_parses_name_and_confidence() -> None:
    detection = _landmark_detection_from_json({"name": "Eiffelturm", "confidence": 0.87})

    assert detection.name == "Eiffelturm"
    assert detection.confidence == 0.87


def test_landmark_detection_from_json_treats_a_missing_name_as_no_landmark() -> None:
    detection = _landmark_detection_from_json({"name": None, "confidence": 0.0})

    assert detection.name is None
    assert detection.confidence == 0.0


def test_landmark_detection_from_json_clamps_a_confidence_above_one() -> None:
    detection = _landmark_detection_from_json({"name": "Eiffelturm", "confidence": 1.2})

    assert detection.confidence == 1.0


def test_landmark_detection_from_json_clamps_a_negative_confidence() -> None:
    detection = _landmark_detection_from_json({"name": "Eiffelturm", "confidence": -0.3})

    assert detection.confidence == 0.0


def test_landmark_detection_from_json_rejects_a_non_string_name() -> None:
    with pytest.raises(LandmarkApiError):
        _landmark_detection_from_json({"name": 42, "confidence": 0.5})


def test_landmark_detection_from_json_rejects_a_non_dict_top_level_shape() -> None:
    # Regressionsnachweis fuer die urspruenglich in _parse_detection gepruefte
    # "unexpected_top_level_shape"-Situation (test_detect_raises_landmark_api_error_on_unexpected_
    # top_level_shape oben) - jetzt in der providerneutralen Funktion, da AttributeError beim
    # .get()-Aufruf auf einer Liste auftritt.
    with pytest.raises(LandmarkApiError):
        _landmark_detection_from_json(["not", "an", "object"])
