from __future__ import annotations

import ast
import asyncio
import base64
import json

import httpx
import pytest

from photosort.cloud_vision import (
    ANTHROPIC_VISION_MODEL,
    MISTRAL_VISION_MODEL,
    CloudRequestThrottle,
    TokenUsage,
)
from photosort.criteria import CRITERIA_REGISTRY, compute_landmark_score
from photosort.landmark import (
    LANDMARK_CONFIDENCE_THRESHOLD,
    MAX_LANDMARK_NAME_LENGTH,
    AnthropicLandmarkClient,
    LandmarkApiError,
    LandmarkClientLike,
    LandmarkDetection,
    MistralLandmarkClient,
    PlaceHint,
    _landmark_detection_from_json,
    place_hint_for,
    usable_landmark_name,
)
from photosort.places import landmark_place_cell
from tests.import_closure import module_file

# specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md,
# specs/architecture/0002-testkonzept.md ("Cloud-LLM-Vision-Client-Test-Double..."): httpx.
# MockTransport statt unittest.mock.patch, analog test_opencloud_client.py - prueft die reale
# Request-Konstruktion (Header, Body, Timeout) mit, kein reiner Mock der HTTP-Bibliothek.
# build_landmark_client()/AnthropicLandmarkClient() werden hier NIE mit einem echten Netzwerk-
# Aufruf gestartet (kein API-Key im Test) - jeder Test injiziert einen httpx.MockTransport.

API_KEY = "sk-ant-test-key-not-a-real-secret"
IMAGE_BYTES = b"\xff\xd8\xff\xe0fake-jpeg-bytes"


# specs/features/0382-cloud-rate-limits-aussitzen.md: der Schrittmacher ist an beiden
# Client-Klassen ein Pflicht-Schluesselwortparameter OHNE Default. Die Bestandsfaelle bekommen
# deshalb einen wirkungslosen (`min_interval_seconds=0.0` heisst "kein Schrittmacher") - sie
# aendern sich sonst inhaltlich nicht.


def _no_throttle() -> CloudRequestThrottle:
    return CloudRequestThrottle(min_interval_seconds=0.0)


def _recording_throttle(waits: list[float]) -> CloudRequestThrottle:
    """Kein Mindestabstand, aber jede Wiederholungs-Wartezeit als Zahl in `waits` - und ohne eine
    einzige echte Sekunde Wartezeit (`post_vision_request` wartet ausschliesslich ueber DIESEN
    `sleep`)."""

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    return CloudRequestThrottle(min_interval_seconds=0.0, clock=lambda: 0.0, sleep=sleep)


def _success_response(name: str | None, confidence: float) -> httpx.Response:
    payload = {
        "content": [{"type": "text", "text": json.dumps({"name": name, "confidence": confidence})}]
    }
    return httpx.Response(200, json=payload)


def _client(
    handler: httpx.MockTransport, throttle: CloudRequestThrottle | None = None
) -> AnthropicLandmarkClient:
    return AnthropicLandmarkClient(
        api_key=API_KEY,
        model=ANTHROPIC_VISION_MODEL,
        transport=handler,
        throttle=throttle or _no_throttle(),
    )


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
    assert body["model"] == ANTHROPIC_VISION_MODEL
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
        api_key=API_KEY,
        model=ANTHROPIC_VISION_MODEL,
        transport=httpx.MockTransport(lambda r: _success_response("x", 0.1)),
        throttle=_no_throttle(),
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
        api_key=API_KEY,
        model=ANTHROPIC_VISION_MODEL,
        transport=httpx.MockTransport(lambda r: _success_response("x", 0.1)),
        throttle=_no_throttle(),
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


# specs/features/0054-mistral-provider-option-cloud-landmark.md, decisions/0031-mistral-provider-
# option-cloud-landmark.md Punkt 2 ab hier: MistralLandmarkClient, exakt analog dem obigen
# AnthropicLandmarkClient-Testblock (httpx.MockTransport, kein echtes Netzwerk/Secret).

MISTRAL_API_KEY = "mistral-test-key-not-a-real-secret"


def _mistral_success_response(name: str | None, confidence: float) -> httpx.Response:
    payload = {
        "choices": [{"message": {"content": json.dumps({"name": name, "confidence": confidence})}}]
    }
    return httpx.Response(200, json=payload)


def _mistral_client(
    handler: httpx.MockTransport, throttle: CloudRequestThrottle | None = None
) -> MistralLandmarkClient:
    return MistralLandmarkClient(
        api_key=MISTRAL_API_KEY,
        model=MISTRAL_VISION_MODEL,
        transport=handler,
        throttle=throttle or _no_throttle(),
    )


async def test_mistral_detect_parses_a_successful_response_with_a_landmark_name() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _mistral_success_response("Eiffelturm", 0.87)

    client = _mistral_client(httpx.MockTransport(handler))
    detection = await client.detect(IMAGE_BYTES, "image/jpeg")

    assert detection.name == "Eiffelturm"
    assert detection.confidence == 0.87


async def test_mistral_detect_parses_a_response_with_no_identified_landmark() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _mistral_success_response(None, 0.0)

    client = _mistral_client(httpx.MockTransport(handler))
    detection = await client.detect(IMAGE_BYTES, "image/jpeg")

    assert detection.name is None
    assert detection.confidence == 0.0


async def test_mistral_detect_clamps_a_confidence_above_one_from_the_raw_api_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _mistral_success_response("Eiffelturm", 1.2)

    client = _mistral_client(httpx.MockTransport(handler))
    detection = await client.detect(IMAGE_BYTES, "image/jpeg")

    assert detection.confidence == 1.0


async def test_mistral_detect_clamps_a_negative_confidence_from_the_raw_api_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _mistral_success_response("Eiffelturm", -0.3)

    client = _mistral_client(httpx.MockTransport(handler))
    detection = await client.detect(IMAGE_BYTES, "image/jpeg")

    assert detection.confidence == 0.0


async def test_mistral_detect_sends_the_expected_request_shape() -> None:
    # Realer Request-Konstruktions-Nachweis, analog test_detect_sends_the_expected_request_shape
    # oben - prueft insbesondere die beiden ADR-0031-Muss-Kriterien: Authorization: Bearer statt
    # x-api-key, und image_url als FLACHER String (keine Verwechslung mit dem verschachtelten
    # OpenAI-Schema {"url": ...}).
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return _mistral_success_response("Eiffelturm", 0.9)

    client = _mistral_client(httpx.MockTransport(handler))
    await client.detect(IMAGE_BYTES, "image/jpeg")

    assert seen["url"] == "https://api.mistral.ai/v1/chat/completions"
    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert headers["authorization"] == f"Bearer {MISTRAL_API_KEY}"
    assert "x-api-key" not in headers

    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == MISTRAL_VISION_MODEL
    assert body["response_format"] == {"type": "json_object"}
    content_blocks = body["messages"][0]["content"]
    image_block = next(block for block in content_blocks if block["type"] == "image_url")
    # ADR 0031 Punkt 2: bei Mistral ist image_url ein FLACHER String (Data-URI), KEIN
    # verschachteltes {"url": "..."}-Objekt wie im OpenAI-Schema.
    expected_data_uri = f"data:image/jpeg;base64,{base64.b64encode(IMAGE_BYTES).decode()}"
    assert image_block["image_url"] == expected_data_uri
    assert isinstance(image_block["image_url"], str)


async def test_mistral_detect_raises_landmark_api_error_on_4xx_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="unauthorized")

    client = _mistral_client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_mistral_detect_raises_landmark_api_error_on_5xx_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    client = _mistral_client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_mistral_network_failure_is_wrapped_as_landmark_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    client = _mistral_client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_mistral_detect_raises_landmark_api_error_on_malformed_json_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    client = _mistral_client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_mistral_detect_raises_landmark_api_error_on_missing_choices_field() -> None:
    # Edge Case 1 der Teststrategie: Mistral-Response ohne erwartetes choices/message/content-Feld.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = _mistral_client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_mistral_detect_raises_landmark_api_error_on_empty_choices_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    client = _mistral_client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_mistral_detect_raises_landmark_api_error_when_name_is_not_a_string() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        text = json.dumps({"name": 42, "confidence": 0.5})
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})

    client = _mistral_client(httpx.MockTransport(handler))

    with pytest.raises(LandmarkApiError):
        await client.detect(IMAGE_BYTES, "image/jpeg")


async def test_mistral_aclose_closes_the_underlying_http_client() -> None:
    client = MistralLandmarkClient(
        api_key=MISTRAL_API_KEY,
        model=MISTRAL_VISION_MODEL,
        transport=httpx.MockTransport(lambda r: _mistral_success_response("x", 0.1)),
        throttle=_no_throttle(),
    )
    await client.aclose()
    assert client._client.is_closed  # Whitebox-Konfigurationsnachweis


async def test_mistral_timeout_is_applied_to_the_underlying_http_client() -> None:
    client = MistralLandmarkClient(
        api_key=MISTRAL_API_KEY,
        model=MISTRAL_VISION_MODEL,
        transport=httpx.MockTransport(lambda r: _mistral_success_response("x", 0.1)),
        throttle=_no_throttle(),
    )
    assert client._client.timeout.read == 60.0  # Whitebox-Konfigurationsnachweis, geteilte
    # LANDMARK_REQUEST_TIMEOUT_SECONDS-Konstante (Akzeptanzkriterium der Spec, keine eigene)


def test_mistral_error_message_never_embeds_the_api_key_or_base64_image_data() -> None:
    # Mistral-Variante von test_error_message_never_embeds_the_api_key_or_base64_image_data oben
    # (Nice-to-have-Fund security-engineer, ship-feature-Review-Runde) - dasselbe Sicherheits-
    # Muss-Kriterium der Spec ("identisch zum Anthropic-Client") jetzt direkt mit MISTRAL_API_KEY
    # demonstriert statt nur ueber die gemeinsame _raise_for_status-Codepfad-Identitaet gefolgert.
    encoded_image = base64.b64encode(IMAGE_BYTES).decode()
    error = LandmarkApiError("Mistral-Anfrage fehlgeschlagen: 401 Unauthorized")
    assert MISTRAL_API_KEY not in str(error)
    assert encoded_image not in str(error)


# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md Punkt 1: `LandmarkDetection.usage` traegt den realen Token-Verbrauch des Aufrufs bis
# zum Worker. Das Feld hat einen Default (`None`) - alle bestehenden Test-Doubles und die
# Protocol-Signatur bleiben dadurch unveraendert (Bestandsschutz, siehe Test unten).


class TestLandmarkDetectionUsage:
    def test_can_be_constructed_without_usage(self) -> None:
        """Bestandsschutz: jede bestehende Konstruktion ohne `usage` bleibt gueltig."""
        detection = LandmarkDetection(name="Eiffelturm", confidence=0.9)

        assert detection.usage is None

    def test_carries_the_usage_when_given(self) -> None:
        detection = LandmarkDetection(
            name=None, confidence=0.0, usage=TokenUsage(input_tokens=1590, output_tokens=12)
        )

        assert detection.usage == TokenUsage(input_tokens=1590, output_tokens=12)


class TestAnthropicClientFillsUsage:
    async def test_detect_reports_the_token_usage_of_the_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [
                        {"type": "text", "text": json.dumps({"name": "Dom", "confidence": 0.8})}
                    ],
                    "usage": {"input_tokens": 1590, "output_tokens": 12},
                },
            )

        detection = await _client(httpx.MockTransport(handler)).detect(IMAGE_BYTES, "image/jpeg")

        assert detection.name == "Dom"
        assert detection.usage == TokenUsage(input_tokens=1590, output_tokens=12)

    async def test_a_response_without_usage_still_yields_a_successful_detection(self) -> None:
        """ADR 0051 Punkt 1: eine fehlende Abrechnungsangabe darf die Erkennung nie scheitern
        lassen - das Ergebnis bleibt gueltig, nur `usage` ist `None`."""

        def handler(request: httpx.Request) -> httpx.Response:
            return _success_response("Dom", 0.8)

        detection = await _client(httpx.MockTransport(handler)).detect(IMAGE_BYTES, "image/jpeg")

        assert detection.name == "Dom"
        assert detection.usage is None


class TestMistralClientFillsUsage:
    async def test_detect_reports_the_token_usage_of_the_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": json.dumps({"name": "Dom", "confidence": 0.8})}}
                    ],
                    # Mistral benennt die Felder anders als Anthropic - genau das ist die Stelle,
                    # an der eine Verwechslung still 0 Tokens erzeugen wuerde.
                    "usage": {"prompt_tokens": 1200, "completion_tokens": 9},
                },
            )

        client = _mistral_client(httpx.MockTransport(handler))
        detection = await client.detect(IMAGE_BYTES, "image/jpeg")

        assert detection.usage == TokenUsage(input_tokens=1200, output_tokens=9)

    async def test_a_response_without_usage_still_yields_a_successful_detection(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": json.dumps({"name": None, "confidence": 0.0})}}
                    ]
                },
            )

        client = _mistral_client(httpx.MockTransport(handler))
        detection = await client.detect(IMAGE_BYTES, "image/jpeg")

        assert detection.name is None
        assert detection.usage is None


# specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, ADR 0059 Punkt 7 ab hier: das Modell
# ist ein durchgereichter Konstruktor-Parameter statt einer im Client gelesenen Modulkonstante.


class TestConfiguredModelReachesTheRequest:
    def test_the_anthropic_client_sends_the_model_it_was_built_with(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": '{"name": null, "confidence": 0.0}'}],
                },
            )

        client = AnthropicLandmarkClient(
            api_key="test",
            model="ein-anderes-modell",
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )

        asyncio.run(client.detect(IMAGE_BYTES, "image/jpeg"))

        assert captured["model"] == "ein-anderes-modell"

    def test_the_mistral_client_sends_the_model_it_was_built_with(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{"name": null, "confidence": 0.0}'}}],
                },
            )

        client = MistralLandmarkClient(
            api_key="test",
            model="ein-anderes-modell",
            transport=httpx.MockTransport(handler),
            throttle=_no_throttle(),
        )

        asyncio.run(client.detect(IMAGE_BYTES, "image/jpeg"))

        assert captured["model"] == "ein-anderes-modell"


# specs/features/0382-cloud-rate-limits-aussitzen.md, K1/K5/K6: beide Landmark-Clients senden
# seitdem ueber cloud_vision.py::post_vision_request. Je Client ein PAAR - "429 dann 200" und
# "dauerhaft 429" -, weil erst der Kontrast die Zusage der Story belegt.


class TestTheLandmarkClientsSitOutARateLimit:
    def _responses(self, responses: list[httpx.Response]) -> httpx.MockTransport:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            index = min(calls["n"], len(responses) - 1)
            calls["n"] += 1
            return responses[index]

        return httpx.MockTransport(handler)

    async def test_anthropic_retries_a_429_and_returns_the_following_result(self) -> None:
        waits: list[float] = []
        transport = self._responses([httpx.Response(429), _success_response("Eiffelturm", 0.87)])
        client = _client(transport, _recording_throttle(waits))

        detection = await client.detect(IMAGE_BYTES, "image/jpeg")

        assert detection.name == "Eiffelturm"
        assert detection.confidence == pytest.approx(0.87)
        assert waits == [2.0]

    async def test_anthropic_gives_up_after_five_attempts_on_a_permanent_429(self) -> None:
        waits: list[float] = []
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(429)

        client = _client(httpx.MockTransport(handler), _recording_throttle(waits))

        with pytest.raises(LandmarkApiError) as excinfo:
            await client.detect(IMAGE_BYTES, "image/jpeg")

        assert "429" in str(excinfo.value)
        assert len(requests) == 5
        assert waits == [2.0, 4.0, 8.0, 16.0]

    async def test_mistral_retries_a_429_and_returns_the_following_result(self) -> None:
        waits: list[float] = []
        transport = self._responses(
            [httpx.Response(429), _mistral_success_response("Kolosseum", 0.75)]
        )
        client = _mistral_client(transport, _recording_throttle(waits))

        detection = await client.detect(IMAGE_BYTES, "image/jpeg")

        assert detection.name == "Kolosseum"
        assert detection.confidence == pytest.approx(0.75)
        assert waits == [2.0]

    async def test_mistral_gives_up_after_five_attempts_on_a_permanent_429(self) -> None:
        waits: list[float] = []
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(429)

        client = _mistral_client(httpx.MockTransport(handler), _recording_throttle(waits))

        with pytest.raises(LandmarkApiError) as excinfo:
            await client.detect(IMAGE_BYTES, "image/jpeg")

        assert "429" in str(excinfo.value)
        assert len(requests) == 5
        assert waits == [2.0, 4.0, 8.0, 16.0]

    async def test_a_401_is_still_never_retried(self) -> None:
        """K5: der bestehende best-effort-Skip bleibt unveraendert - genau EIN HTTP-Versuch."""
        waits: list[float] = []
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(401)

        client = _client(httpx.MockTransport(handler), _recording_throttle(waits))

        with pytest.raises(LandmarkApiError):
            await client.detect(IMAGE_BYTES, "image/jpeg")

        assert len(requests) == 1
        assert waits == []


# ---------------------------------------------------------------------------------------------
# specs/features/0051-gps-landmark-cluster-bildung.md, Security-Abschnitt 1 / Sicherheitskonzept
# "Standortdaten": `PhotoLandmarkDetection.name` verlaesst mit dieser Spec erstmals die API und
# wird in einer Cluster-Ueberschrift gerendert. Unter Spec 0047 ("kein UI-Verweis in v1") ging er
# als ROHWERT aus der Modellantwort in die Datenbank - `_landmark_detection_from_json` prueft nur
# `isinstance(name, str)`. Ab hier: Sanitisierung AN DER QUELLE mit derselben Funktion wie der
# Feinlabel-Pfad, plus eine Laengengrenze mit VERWERFEN statt Abschneiden.


class TestLandmarkNameSanitisation:
    def test_control_and_format_characters_are_stripped_at_the_source(self) -> None:
        """Escapetes Rendering im Frontend schuetzt gegen XSS, aber weder gegen optische
        Verfaelschung durch Bidi-/Zero-Width-Zeichen noch gegen mehrzeilige Logeintraege."""
        detection = _landmark_detection_from_json({"name": "Eiffel‮turm​", "confidence": 0.9})

        assert detection.name == "Eiffelturm"

    def test_whitespace_runs_are_collapsed_at_the_source(self) -> None:
        detection = _landmark_detection_from_json(
            {"name": "  Kathedrale\n\tvon   Santiago  ", "confidence": 0.9}
        )

        assert detection.name == "Kathedrale von Santiago"

    def test_a_name_that_is_empty_after_sanitisation_becomes_none(self) -> None:
        detection = _landmark_detection_from_json({"name": "​‮", "confidence": 0.9})

        assert detection.name is None

    def test_a_name_beyond_the_length_limit_is_discarded_not_truncated(self) -> None:
        """VERWERFEN, nie Abschneiden (Muss-Kriterium): `refine_clusters_by_landmark` vergleicht
        exakt - ein abgeschnittener Name fuehrte zwei verschiedene Sehenswuerdigkeiten in EINEM
        Cluster zusammen (dieselbe Begruendung wie die Slug-Kollision bei den Feinlabels)."""
        too_long = "A" * (MAX_LANDMARK_NAME_LENGTH + 1)

        detection = _landmark_detection_from_json({"name": too_long, "confidence": 0.9})

        assert detection.name is None

    def test_a_name_exactly_at_the_length_limit_is_kept(self) -> None:
        exactly = "A" * MAX_LANDMARK_NAME_LENGTH

        detection = _landmark_detection_from_json({"name": exactly, "confidence": 0.9})

        assert detection.name == exactly

    def test_the_limit_is_generous_enough_for_a_real_landmark_name(self) -> None:
        """80 statt der 60 des Feinlabel-Pfads, weil echte Sehenswuerdigkeitsnamen laenger sind."""
        detection = _landmark_detection_from_json(
            {"name": "Kathedrale von Santiago de Compostela", "confidence": 0.9}
        )

        assert detection.name == "Kathedrale von Santiago de Compostela"

    def test_an_ordinary_name_passes_through_unchanged(self) -> None:
        detection = _landmark_detection_from_json({"name": "Zugspitze", "confidence": 0.42})

        assert detection.name == "Zugspitze"
        assert detection.confidence == 0.42

    def test_an_explicit_null_name_stays_none(self) -> None:
        detection = _landmark_detection_from_json({"name": None, "confidence": 0.0})

        assert detection.name is None


class TestOneMeasureForEveryUseOfTheName:
    """specs/features/0469, ADR 0107 Punkt 1: Bewertung und Name messen an DEMSELBEN Wert.

    Bisher war ein erkannter Name an zwei verschieden strengen Massstaeben gemessen - fuer die
    Bewertung zaehlte er erst ab der registrierten Konfidenzschwelle, als Gruppenname erschien er
    unabhaengig davon. Geprueft wird nicht die Gleichheit zweier Literale, sondern die
    UEBEREINSTIMMUNG der beiden Verbraucher ueber den ganzen Wertebereich."""

    def test_the_registry_reads_the_threshold_from_the_landmark_module(self) -> None:
        assert CRITERIA_REGISTRY["landmark"].presence_threshold == LANDMARK_CONFIDENCE_THRESHOLD

    def test_the_numeric_value_itself_is_unchanged(self) -> None:
        """Geaendert wird die Gleichheit des Massstabs, nicht seine Hoehe (Spec 0469, Out of
        Scope). Ob er steigen muss, entscheidet die Abnahme an einer echten Reise."""
        assert LANDMARK_CONFIDENCE_THRESHOLD == 0.5

    def test_criteria_no_longer_carries_a_landmark_threshold_literal_of_its_own(self) -> None:
        """Der Waechter gegen den Rueckfall: Solange der Wert an zwei Stellen GESCHRIEBEN werden
        kann, kann er auch auseinanderlaufen - und der Fall darueber bestuende weiter, bis jemand
        genau eine der beiden Stellen aendert."""
        path = module_file("photosort.criteria")
        assert path is not None
        tree = ast.parse(path.read_text(encoding="utf-8"))

        landmark_literals = [
            ast.unparse(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, int | float)
            and any(
                isinstance(target, ast.Name) and "LANDMARK" in target.id.upper()
                for target in node.targets
            )
        ]

        assert landmark_literals == []

    @pytest.mark.parametrize(
        "confidence",
        [
            0.0,
            0.1,
            LANDMARK_CONFIDENCE_THRESHOLD - 0.01,
            LANDMARK_CONFIDENCE_THRESHOLD,
            LANDMARK_CONFIDENCE_THRESHOLD + 0.01,
            0.9,
            1.0,
        ],
    )
    def test_score_verdict_and_name_verdict_agree_for_every_confidence(
        self, confidence: float
    ) -> None:
        """Die eigentliche Zusage, als Tabelle ueber die Grenze hinweg: fuer JEDEN Konfidenzwert
        sagen Bewertung und Name dasselbe."""
        detection = LandmarkDetection(name="Zugspitze", confidence=confidence)
        threshold = CRITERIA_REGISTRY["landmark"].presence_threshold
        assert threshold is not None

        counts_as_present = compute_landmark_score(detection) >= threshold
        has_a_usable_name = usable_landmark_name("Zugspitze", confidence) is not None

        assert counts_as_present == has_a_usable_name


class TestUsableLandmarkName:
    """Die EINE Stelle, an der aus einer Erkennungszeile ein verwendbarer Name wird (ADR 0107
    Punkt 2). `None` heisst "kein verwendbarer Name" und ist von "nie erkannt" nicht zu
    unterscheiden."""

    def test_exactly_on_the_threshold_is_usable_inclusive(self) -> None:
        """`>=`, inklusiv - derselbe Vergleichssinn wie `presence_threshold`."""
        assert usable_landmark_name("Zugspitze", LANDMARK_CONFIDENCE_THRESHOLD) == "Zugspitze"

    def test_just_below_the_threshold_is_no_name_even_if_it_is_flawless(self) -> None:
        assert usable_landmark_name("Zugspitze", LANDMARK_CONFIDENCE_THRESHOLD - 0.01) is None

    def test_above_the_threshold_an_unusable_name_is_still_no_name(self) -> None:
        """Die Grenze steht VOR der Sanitisierung, aber sie ersetzt sie nicht."""
        assert usable_landmark_name("A" * (MAX_LANDMARK_NAME_LENGTH + 1), 0.99) is None

    def test_the_threshold_is_checked_before_the_sanitisation(self) -> None:
        """Beide Gruende fuehren zu DEMSELBEN Ergebnis - ein unsicherer Treffer mit unbrauchbarem
        Namen erzeugt keinen zweiten Zustand."""
        assert usable_landmark_name("A" * (MAX_LANDMARK_NAME_LENGTH + 1), 0.0) is None

    def test_a_name_is_sanitised_on_the_way_out(self) -> None:
        assert usable_landmark_name("Eiffel‮turm​", 0.9) == "Eiffelturm"

    def test_a_missing_name_is_no_name(self) -> None:
        assert usable_landmark_name(None, 0.99) is None

    def test_the_canonical_name_wins_over_the_raw_one(self) -> None:
        """ADR 0107 Punkt 5: Die Lesestelle nimmt den kanonischen Namen, sonst den Rohnamen."""
        assert usable_landmark_name("Eiffel Tower", 0.9, "Eiffelturm") == "Eiffelturm"

    def test_a_row_without_a_canonical_name_behaves_exactly_as_before(self) -> None:
        """Kein Nachziehen von Altbestand: ohne einen kanonischen Namen verhaelt sich eine
        Altzeile wie heute."""
        assert usable_landmark_name("Eiffelturm", 0.9, None) == "Eiffelturm"

    def test_a_canonical_name_that_fails_sanitisation_falls_back_to_the_raw_one(self) -> None:
        assert usable_landmark_name("Eiffelturm", 0.9, "​‮") == "Eiffelturm"

    def test_the_canonical_name_does_not_survive_a_confidence_below_the_threshold(self) -> None:
        assert usable_landmark_name("Eiffel Tower", 0.1, "Eiffelturm") is None

    def test_the_canonical_name_is_sanitised_too(self) -> None:
        """SICHERHEIT (S9): `sanitize_landmark_name` wirkt auf den zurueckgegebenen Wert, GLEICH
        ob kanonischer Name oder Rohname - die Altbestandsdeckung darf nicht dadurch entfallen,
        dass ein neues Feld daneben tritt."""
        assert usable_landmark_name("Eiffel Tower", 0.9, "Eiffel‮turm") == "Eiffelturm"


class TestThePlaceHintHasTwoStagesAndAPrecedence:
    """ADR 0106 Punkt 2: Ortsname, sonst grobe Koordinate, sonst nichts - die Stufenwahl an genau
    EINER Stelle.

    Beide Stufen sind dauerhaft; die Koordinatenstufe ist kein Uebergangszustand bis zu einer
    besseren Namensaufloesung."""

    def test_a_resolved_locality_wins_over_the_coordinate(self) -> None:
        hint = place_hint_for("Garmisch-Partenkirchen", 47.49, 11.09)

        assert hint is not None
        assert hint.locality == "Garmisch-Partenkirchen"

    def test_the_coordinate_does_not_ride_along_with_a_resolved_locality(self) -> None:
        """Die Stufen sind ein ENTWEDER-ODER. Steht der Name, geht das Zahlenpaar nicht zusaetzlich
        hinaus - sonst waere die Namensstufe keine Schonung, sondern eine Ergaenzung."""
        hint = place_hint_for("Garmisch-Partenkirchen", 47.49, 11.09)

        assert hint is not None
        assert hint.cell is None

    def test_without_a_resolvable_locality_the_coordinate_stage_takes_over(self) -> None:
        """Nicht "nichts": Der Fall ist genau der, fuer den die Koordinatenstufe da ist - eine
        Antwort auf Regionsebene gilt als "kein Name aufgeloest"."""
        hint = place_hint_for(None, 47.49, 11.09)

        assert hint is not None
        assert hint.locality is None
        assert hint.cell == landmark_place_cell(47.49, 11.09)

    def test_a_locality_that_fails_sanitisation_falls_through_to_the_coordinate(self) -> None:
        """Ein Ortsdatensatz ist von Dritten beschreibbar. Ein unbrauchbarer Name ist kein Name -
        und macht das Foto nicht ortlos."""
        hint = place_hint_for("​‮", 47.49, 11.09)

        assert hint is not None
        assert hint.locality is None
        assert hint.cell == landmark_place_cell(47.49, 11.09)

    def test_the_locality_is_sanitised_on_the_way_out(self) -> None:
        """S4 (c): Hinaus geht der EINE sanitierte Name. Die Sanitisierung am Schreibrand deckt den
        Bestand; der ausgehende Rand verlaesst sich nicht darauf."""
        hint = place_hint_for("Garmisch‮-Partenkirchen​", 47.49, 11.09)

        assert hint is not None
        assert hint.locality == "Garmisch-Partenkirchen"

    def test_a_photo_without_a_measured_coordinate_gets_no_hint_at_all(self) -> None:
        """Und damit STRUKTURELL auch keinen Ortsnamen: Der Name stammt aus der Zelle des Fotos,
        und ohne Koordinate gibt es keine. Das Fehlen ist kein Fehlerfall - das Foto wird
        unveraendert erkannt."""
        assert place_hint_for("Garmisch-Partenkirchen", None, None) is None

    @pytest.mark.parametrize(
        ("lat", "lon"), [(47.49, None), (None, 11.09)], ids=["nur-breite", "nur-laenge"]
    )
    def test_half_a_coordinate_is_no_coordinate(self, lat: float | None, lon: float | None) -> None:
        assert place_hint_for(None, lat, lon) is None

    def test_the_coordinate_stage_is_coarsened_never_the_measured_value(self) -> None:
        """Die Zelle, die das System verlaesst - nie feiner (S1)."""
        hint = place_hint_for(None, 47.4912345, 11.0987654)

        assert hint is not None
        assert hint.cell == (47.5, 11.1)

    def test_a_hint_never_carries_both_stages_at_once(self) -> None:
        """Die Invariante ist strukturell durchgesetzt, nicht bloss dokumentiert: eine von Hand
        gebaute Doppelbelegung waere sonst der stille Weg, auf dem beide Stufen zugleich
        hinausgingen."""
        with pytest.raises(ValueError):
            PlaceHint(locality="Garmisch-Partenkirchen", cell=(47.5, 11.1))

    def test_a_hint_never_carries_neither_stage(self) -> None:
        """ "Nichts" wird als `None` ausgedrueckt, nie als leerer Hinweis - sonst gaebe es zwei
        Darstellungen derselben Abwesenheit."""
        with pytest.raises(ValueError):
            PlaceHint()
