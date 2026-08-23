from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

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
from photosort.config import settings

# specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, decisions/0025-cloud-
# landmark-erkennung.md: erste tatsaechlich produktive Cloud-Abhaengigkeit im Kriterien-Scoring-
# Pfad. Isoliertes Modul (ADR 0025 Punkt 2) - haelt den bestehenden synchronen criteria.py-Vertrag
# aller sieben lokalen Kriterien unangetastet. Direkter httpx-REST-Aufruf gegen die Anthropic
# Messages API, KEIN anthropic-Python-SDK (ADR 0025 Punkt 1, Minimalismus-Prinzip ADR 0006) -
# exakt das Muster von opencloud/client.py (eigene Exception-Klasse, httpx.AsyncClient,
# httpx.MockTransport-testbar).
#
# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt 3:
# URLs/Modell-IDs/Timeout/Response-Parsing-Envelope-Helfer sind seitdem nach cloud_vision.py
# extrahiert (providerneutral, jetzt von landmark.py UND remote_classification.py genutzt) - die
# bisherigen Namen bleiben hier als re-exportierte Aliase bestehen (Regressionspflicht der Spec:
# "Bestehende test_landmark.py-Faelle bleiben ohne Assertion-Aenderung gruen").
ANTHROPIC_LANDMARK_MODEL = ANTHROPIC_VISION_MODEL
MISTRAL_LANDMARK_MODEL = MISTRAL_VISION_MODEL
LANDMARK_REQUEST_TIMEOUT_SECONDS = VISION_REQUEST_TIMEOUT_SECONDS

# Kurze, reine Klassifikationsantwort - kein Grund fuer ein hohes max_tokens (nur ein kleines
# JSON-Objekt wird erwartet).
_MAX_RESPONSE_TOKENS = 256

_PROMPT = (
    "Analysiere dieses Foto. Ist eine bekannte oder auch weniger bekannte Sehenswuerdigkeit/ein "
    "Wahrzeichen zu erkennen? Antworte AUSSCHLIESSLICH mit einem einzigen validen JSON-Objekt, "
    "ohne Markdown-Codeblock, ohne weiteren Text, exakt in dieser Form: "
    '{"name": "<Name der Sehenswuerdigkeit oder null>", "confidence": <Zahl zwischen 0 und 1>}. '
    "Ist keine Sehenswuerdigkeit erkennbar, setze \"name\" auf null und \"confidence\" auf 0."
)


class LandmarkApiError(Exception):
    """Fehler beim Aufruf der Anthropic Messages API (Netzwerk, 4xx/5xx, unerwartete
    Antwortstruktur) - analog OpenCloudError. Sicherheitskritisches Muss-Kriterium der Spec:
    Meldungen betten NIEMALS den API-Key oder Base64-Bilddaten ein, nur Statuscode/Reason-Phrase
    bzw. eine generische Strukturbeschreibung (analog opencloud/client.py::_raise_for_status)."""


@dataclass(frozen=True)
class LandmarkDetection:
    """Ergebnis eines einzelnen Sehenswuerdigkeit-Erkennungsversuchs (ADR 0025 Punkt 2).
    `name` ist `None`, wenn keine Sehenswuerdigkeit identifiziert wurde - dann bleibt `confidence`
    bedeutungslos (per Konvention 0.0, aber nicht zu pruefen)."""

    name: str | None
    confidence: float


class LandmarkClientLike(Protocol):
    """Schmale, injizierbare Schnittstelle (ADR 0025 Punkt 2) - erlaubt ein Test-Double ohne
    echtes Netzwerk/Secret (Teststrategie-Abschnitt der Spec 0047), analog FaceDetectorLike/
    OpenCloudScanClient."""

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection: ...


def _landmark_detection_from_json(parsed: Any) -> LandmarkDetection:
    """Providerneutrale Extraktion von name/confidence aus dem bereits geparsten JSON-Objekt
    (specs/decisions/0031-mistral-provider-option-cloud-landmark.md Punkt 2, Refactoring des
    frueheren _parse_detection) - wird von beiden Clients nach ihrer jeweils providerspezifischen
    Extraktion des rohen JSON-Texts aus ihrer unterschiedlichen Response-Huelle aufgerufen."""
    try:
        name = parsed.get("name")
        confidence = float(parsed.get("confidence", 0.0))
    except (AttributeError, TypeError, ValueError) as exc:
        # Bewusst generische, providerneutrale Meldung (kein Provider-Name mehr bekannt an dieser
        # Stelle) - analog der Begruendung in cloud_vision.py::anthropic_response_to_json.
        raise LandmarkApiError("Unerwartete Antwortstruktur der Vision-API-Antwort.") from exc
    if name is not None and not isinstance(name, str):
        raise LandmarkApiError("Unerwartete Antwortstruktur der Vision-API-Antwort.")
    # Copilot-Review-Fund (PR #181): das Vision-LLM-JSON ist nicht garantiert auf [0, 1] begrenzt -
    # geklemmt bereits HIER (an der Quelle), nicht erst in criteria.py::compute_landmark_score.
    # worker.py::_upsert_landmark_detection schreibt detection.confidence UNVERAENDERT nach
    # photo_landmark_detections - ohne dieses Klemmen wuerde dieser Wert von dem separat
    # geklemmten PhotoCriterionScore.value abweichen koennen, obwohl beide laut ADR 0025 Punkt 6
    # atomar aus derselben API-Antwort stammen sollen. compute_landmark_score klemmt zusaetzlich
    # weiterhin defensiv (bewusste Redundanz, kein Widerspruch).
    clamped_confidence = max(0.0, min(1.0, confidence))
    return LandmarkDetection(name=name, confidence=clamped_confidence)


class AnthropicLandmarkClient:
    """Echte, httpx-basierte Implementierung von LandmarkClientLike (ADR 0025 Punkt 2) - direkter
    REST-Aufruf gegen die Anthropic Messages API, kein anthropic-SDK. `transport` ist injizierbar
    (httpx.MockTransport in Tests, analog OpenCloudClient) - `build_landmark_client()` unten
    laeuft dagegen NIE in einem automatisierten Test (echtes Secret + echter Netzwerkversuch)."""

    def __init__(
        self,
        api_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = LANDMARK_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._client = httpx.AsyncClient(
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
                "content-type": "application/json",
            },
            transport=transport,
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
        body = {
            "model": ANTHROPIC_LANDMARK_MODEL,
            "max_tokens": _MAX_RESPONSE_TOKENS,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": base64.b64encode(image_bytes).decode(),
                            },
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        }
        try:
            response = await self._client.post(ANTHROPIC_MESSAGES_URL, json=body)
        except httpx.HTTPError as exc:
            # Kein embed von exc-Details ueber den httpx-eigenen Fehlertext hinaus - httpx-
            # Exceptions enthalten weder den API-Key (der lebt nur in den Request-Headern, nicht
            # in der Exception) noch die Base64-Bilddaten.
            raise LandmarkApiError(f"Anthropic Vision API nicht erreichbar: {exc}") from exc

        raise_for_vision_api_status(response, "Anthropic", LandmarkApiError)
        parsed = anthropic_response_to_json(response.json(), LandmarkApiError)
        return _landmark_detection_from_json(parsed)


class MistralLandmarkClient:
    """Echte, httpx-basierte Implementierung von LandmarkClientLike (ADR 0031 Punkt 2), exakt
    analog AnthropicLandmarkClient - direkter REST-Aufruf gegen die Mistral Chat Completions API,
    kein Mistral-SDK. `transport` ist injizierbar (httpx.MockTransport in Tests) -
    `build_landmark_client()` unten laeuft dagegen NIE in einem automatisierten Test (echtes
    Secret + echter Netzwerkversuch)."""

    def __init__(
        self,
        api_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = LANDMARK_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._client = httpx.AsyncClient(
            headers={
                # Abweichend von Anthropics x-api-key+anthropic-version-Kombination (ADR 0031
                # Punkt 2) - Bearer-Token-Auth.
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
            transport=transport,
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
        body = {
            "model": MISTRAL_LANDMARK_MODEL,
            "max_tokens": _MAX_RESPONSE_TOKENS,
            # Nativer JSON-Mode (ADR 0031 Punkt 2) - Mistral unterstuetzt das, Anthropic nicht
            # (dort bleibt die bestehende reine Prompt-Anweisung unveraendert).
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            # WICHTIG (ADR 0031 Punkt 2): image_url ist bei Mistral ein FLACHER
                            # String (Data-URI), KEIN verschachteltes {"url": "..."}-Objekt wie im
                            # OpenAI-Schema - Verwechslungsgefahr, bewusst 1:1 aus dem
                            # Mistral-Cookbook uebernommen.
                            "image_url": (
                                f"data:{mime_type};base64,"
                                f"{base64.b64encode(image_bytes).decode()}"
                            ),
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        }
        try:
            response = await self._client.post(MISTRAL_CHAT_COMPLETIONS_URL, json=body)
        except httpx.HTTPError as exc:
            # Kein embed von exc-Details ueber den httpx-eigenen Fehlertext hinaus - httpx-
            # Exceptions enthalten weder den API-Key noch die Base64-Bilddaten.
            raise LandmarkApiError(f"Mistral Chat Completions API nicht erreichbar: {exc}") from exc

        raise_for_vision_api_status(response, "Mistral", LandmarkApiError)
        parsed = mistral_response_to_json(response.json(), LandmarkApiError)
        return _landmark_detection_from_json(parsed)


def build_landmark_client() -> LandmarkClientLike:
    """Dispatch-Factory zwischen AnthropicLandmarkClient (unveraendert, weiterhin Default) und
    MistralLandmarkClient je nach settings.landmark_provider (ADR 0031 Punkt 3). Analog
    build_face_detector/build_aesthetics_model: laeuft NIE in einem automatisierten Test (echtes
    Secret + echter Netzwerkversuch, Teststrategie-Abschnitt der Spec 0047/0054 - ein
    versehentlicher Aufruf in CI muesste als harter Fehlschlag auffallen)."""
    if settings.landmark_provider == "mistral":
        mistral_client: LandmarkClientLike = MistralLandmarkClient(
            api_key=settings.mistral_api_key
        )
        return mistral_client
    anthropic_client: LandmarkClientLike = AnthropicLandmarkClient(
        api_key=settings.anthropic_api_key
    )
    return anthropic_client
