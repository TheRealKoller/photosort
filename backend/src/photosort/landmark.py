from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from photosort.config import settings

# specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, decisions/0025-cloud-
# landmark-erkennung.md: erste tatsaechlich produktive Cloud-Abhaengigkeit im Kriterien-Scoring-
# Pfad. Isoliertes Modul (ADR 0025 Punkt 2) - haelt den bestehenden synchronen criteria.py-Vertrag
# aller sieben lokalen Kriterien unangetastet. Direkter httpx-REST-Aufruf gegen die Anthropic
# Messages API, KEIN anthropic-Python-SDK (ADR 0025 Punkt 1, Minimalismus-Prinzip ADR 0006) -
# exakt das Muster von opencloud/client.py (eigene Exception-Klasse, httpx.AsyncClient,
# httpx.MockTransport-testbar).

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

# Guenstigstes vision-faehiges Modell der Claude-Haiku-Reihe (ADR 0025: "kein Grund fuer ein
# teureres Modell bei dieser eng umrissenen Klassifikationsaufgabe", exakte Modell-ID eine
# technische Detailentscheidung des developer-Agenten beim TDD-Einstieg).
ANTHROPIC_LANDMARK_MODEL = "claude-haiku-4-5"

# Kurze, reine Klassifikationsantwort - kein Grund fuer ein hohes max_tokens (nur ein kleines
# JSON-Objekt wird erwartet).
_MAX_RESPONSE_TOKENS = 256

# Modul-Konstante statt Settings-Feld (ADR 0025 Punkt 3: "reiner technischer Wert, kein
# Betriebsparameter wie scan_download_concurrency") - grosszuegiger als der OpenCloud-Client-
# Default (30s), da Vision-LLM-Antwortzeiten tendenziell hoeher sind und der Lauf ein Hintergrund-
# Job ohne wartenden Nutzer ist.
LANDMARK_REQUEST_TIMEOUT_SECONDS = 60.0

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


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code >= 400:
        raise LandmarkApiError(
            f"Anthropic-Anfrage fehlgeschlagen: {response.status_code} {response.reason_phrase}"
        )


def _parse_detection(payload: Any) -> LandmarkDetection:
    try:
        content_blocks = payload["content"]
        text_block = next(block for block in content_blocks if block.get("type") == "text")
        parsed = json.loads(text_block["text"])
        name = parsed.get("name")
        confidence = float(parsed.get("confidence", 0.0))
    except (KeyError, TypeError, StopIteration, ValueError, json.JSONDecodeError) as exc:
        # Bewusst generische Meldung OHNE die rohe Antwort einzubetten (Sicherheits-Muss-
        # Kriterium: keine Base64-Bilddaten/kein Key in der Fehlermeldung - die rohe Antwort
        # selbst enthaelt zwar keine dieser Werte, aber eine feste, generische Meldung ist hier
        # bewusst konsistent mit dem Rest des Moduls, analog opencloud/client.py::
        # _drive_from_graph_api_item).
        raise LandmarkApiError(
            "Unerwartete Antwortstruktur der Anthropic Messages API."
        ) from exc
    if name is not None and not isinstance(name, str):
        raise LandmarkApiError("Unerwartete Antwortstruktur der Anthropic Messages API.")
    return LandmarkDetection(name=name, confidence=confidence)


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

        _raise_for_status(response)
        return _parse_detection(response.json())


def build_landmark_client() -> LandmarkClientLike:
    """Factory fuer die echte AnthropicLandmarkClient-Instanz (ADR 0025 Punkt 2) - liest
    settings.anthropic_api_key. Analog build_face_detector/build_aesthetics_model: laeuft NIE in
    einem automatisierten Test (echtes Secret + echter Netzwerkversuch, Teststrategie-Abschnitt
    der Spec 0047 - ein versehentlicher Aufruf in CI muesste als harter Fehlschlag auffallen)."""
    client: LandmarkClientLike = AnthropicLandmarkClient(api_key=settings.anthropic_api_key)
    return client
