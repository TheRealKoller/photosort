from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from photosort.cloud_vision import (
    ANTHROPIC_API_VERSION,
    ANTHROPIC_ENDPOINT,
    MISTRAL_ENDPOINT,
    VISION_REQUEST_TIMEOUT_SECONDS,
    CloudRequestThrottle,
    TokenUsage,
    _sanitize_label_text,
    anthropic_response_to_json,
    anthropic_usage_from_response,
    mistral_response_to_json,
    mistral_usage_from_response,
    post_vision_request,
)
from photosort.cloud_vision_throttle import throttle_for_provider
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
# specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, ADR 0059 Punkt 7: die frueheren
# Aliase ANTHROPIC_LANDMARK_MODEL/MISTRAL_LANDMARK_MODEL sind ersatzlos entfallen. Sie waren
# Platzhalter fuer eine moegliche spaetere Entkopplung der Modellwahl je Cloud-Zweck; Spec 0304
# entscheidet diese Frage ausdruecklich in die andere Richtung ("wirkt auf beide Cloud-Anteile
# einheitlich; nicht zwei Modelle nebeneinander"). Das Modell kommt jetzt als Konstruktor-
# Parameter herein und wird durchgereicht.
LANDMARK_REQUEST_TIMEOUT_SECONDS = VISION_REQUEST_TIMEOUT_SECONDS

# Kurze, reine Klassifikationsantwort - kein Grund fuer ein hohes max_tokens (nur ein kleines
# JSON-Objekt wird erwartet).
_MAX_RESPONSE_TOKENS = 256

# specs/features/0051-gps-landmark-cluster-bildung.md, Security-Abschnitt 1 (Muss-Kriterium c):
# Obergrenze eines verwendbaren Sehenswuerdigkeit-Namens. Wie `MAX_FINE_LABEL_LENGTH` eine
# DEGENERATIONSGRENZE, keine Sanitisierungsmassnahme - und wie dort wird VERWORFEN statt
# abgeschnitten: `scoring.py::refine_clusters_by_landmark` vergleicht exakt, ein abgeschnittener
# Name fuehrte zwei verschiedene Sehenswuerdigkeiten in einem Cluster zusammen (dieselbe
# Begruendung wie die Slug-Kollision bei den Feinlabels). Der Cluster faellt dann auf die
# Koordinatenstufe zurueck.
#
# 80 statt der 60 des Feinlabel-Pfads, weil echte Sehenswuerdigkeitsnamen laenger sind
# ("Kathedrale von Santiago de Compostela").
MAX_LANDMARK_NAME_LENGTH = 80

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
    # specs/features/0207-projekt-statistikseite.md, ADR 0051 Punkt 1: der reale Token-Verbrauch
    # DIESES Aufrufs, den worker.py ueber alle erfolgreichen Aufrufe der Phase summiert. MIT
    # Default - dadurch bleiben alle bestehenden Test-Doubles und die LandmarkClientLike-Signatur
    # unveraendert. `None` heisst "nicht ermittelbar" (fehlender/kaputter usage-Block, ADR 0051
    # Punkt 1): der Aufruf traegt dann nichts zur Tokensumme bei, wird aber trotzdem als
    # stattgefundener Aufruf gezaehlt.
    usage: TokenUsage | None = None


class LandmarkClientLike(Protocol):
    """Schmale, injizierbare Schnittstelle (ADR 0025 Punkt 2) - erlaubt ein Test-Double ohne
    echtes Netzwerk/Secret (Teststrategie-Abschnitt der Spec 0047), analog FaceDetectorLike/
    OpenCloudScanClient."""

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection: ...


def sanitize_landmark_name(raw: object) -> str | None:
    """Der einzige Weg, auf dem ein Sehenswuerdigkeit-Name in PhotoSort verwendbar wird
    (specs/features/0051-gps-landmark-cluster-bildung.md, Security-Abschnitt 1).

    Zeichensanitisierung mit DERSELBEN Funktion wie der Feinlabel-Pfad
    (`cloud_vision.py::_sanitize_label_text`, nicht mit einer zweiten Fassung davon), danach die
    Laengengrenze. `None` heisst "kein verwendbarer Name" - Nicht-String, leer nach der
    Sanitisierung, oder laenger als `MAX_LANDMARK_NAME_LENGTH`.

    Die Funktion wird an ZWEI Stellen angewandt: an der Quelle in `_landmark_detection_from_json`
    unten UND im Lesepfad, der `PhotoOut.cluster_place.landmark_name` befuellt. Die Begruendung
    fuer die doppelte Anwendung steht an der Lesestelle in `api/photos.py` - sie deckt den
    unsanierten Altbestand aus Spec 0047, fuer den es keinen kostenlosen Migrationsweg gibt."""
    if not isinstance(raw, str):
        return None
    sanitized = _sanitize_label_text(raw)
    if not sanitized or len(sanitized) > MAX_LANDMARK_NAME_LENGTH:
        return None
    return sanitized


def _landmark_detection_from_json(
    parsed: Any, usage: TokenUsage | None = None
) -> LandmarkDetection:
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
    # specs/features/0051-gps-landmark-cluster-bildung.md, Security-Abschnitt 1 (Muss-Kriterium
    # a/c): Sanitisierung und Laengengrenze AN DER QUELLE. Unter Spec 0047 ("kein UI-Verweis in
    # v1") ging der Name als Rohwert in die Datenbank - mit dem Rendern in der Cluster-Ueberschrift
    # faellt dieser Schutz weg. Ein zu langer Name wird GANZ verworfen, nie abgeschnitten:
    # `scoring.py::refine_clusters_by_landmark` vergleicht exakt, ein abgeschnittener Name fuehrte
    # zwei verschiedene Sehenswuerdigkeiten in einem Cluster zusammen.
    name = sanitize_landmark_name(name)
    # Copilot-Review-Fund (PR #181): das Vision-LLM-JSON ist nicht garantiert auf [0, 1] begrenzt -
    # geklemmt bereits HIER (an der Quelle), nicht erst in criteria.py::compute_landmark_score.
    # worker.py::_upsert_landmark_detection schreibt detection.confidence UNVERAENDERT nach
    # photo_landmark_detections - ohne dieses Klemmen wuerde dieser Wert von dem separat
    # geklemmten PhotoCriterionScore.value abweichen koennen, obwohl beide laut ADR 0025 Punkt 6
    # atomar aus derselben API-Antwort stammen sollen. compute_landmark_score klemmt zusaetzlich
    # weiterhin defensiv (bewusste Redundanz, kein Widerspruch).
    clamped_confidence = max(0.0, min(1.0, confidence))
    return LandmarkDetection(name=name, confidence=clamped_confidence, usage=usage)


class AnthropicLandmarkClient:
    """Echte, httpx-basierte Implementierung von LandmarkClientLike (ADR 0025 Punkt 2) - direkter
    REST-Aufruf gegen die Anthropic Messages API, kein anthropic-SDK. `transport` ist injizierbar
    (httpx.MockTransport in Tests, analog OpenCloudClient) - `build_landmark_client()` unten
    laeuft dagegen NIE in einem automatisierten Test (echtes Secret + echter Netzwerkversuch)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = LANDMARK_REQUEST_TIMEOUT_SECONDS,
        *,
        throttle: CloudRequestThrottle,
    ) -> None:
        # PFLICHTPARAMETER ohne Default (Spec 0304/ADR 0059 Punkt 7, Fund `test-engineer`):
        # ein Default auf die Modulkonstante stellte genau die Kopplung wieder her, die diese
        # Spec aufloest - ein Aufrufer, der das Modell vergisst, fiele nicht beim Typecheck auf,
        # sondern erst in der Cloud-Rechnung.
        self._model = model
        # specs/features/0382-cloud-rate-limits-aussitzen.md, K6: der Schrittmacher ebenfalls als
        # PFLICHT-SCHLUESSELWORTPARAMETER ohne Default, dieselbe Begruendung wie beim Modell - ein
        # Aufrufer, der ihn vergisst, fiele nicht beim Typecheck auf, sondern erst an der
        # Anfragerate des Anbieters.
        self._throttle = throttle
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
            "model": self._model,
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
        # specs/features/0382-cloud-rate-limits-aussitzen.md, K6: EIN Aufruf statt des bisher
        # viermal abgeschriebenen post/except/raise_for_status-Blocks. Verteilung ueber den
        # Schrittmacher und Wiederholung bei 429 liegen damit strukturell an genau einer Stelle,
        # nicht in vier gepflegten Kopien. Meldungstexte und Statuslabel sind unveraendert (sie
        # stecken jetzt in ANTHROPIC_ENDPOINT), der Fehlerpfad des Workers bleibt derselbe.
        response = await post_vision_request(
            self._client,
            ANTHROPIC_ENDPOINT,
            body,
            error_class=LandmarkApiError,
            throttle=self._throttle,
        )
        payload = response.json()
        parsed = anthropic_response_to_json(payload, LandmarkApiError)
        return _landmark_detection_from_json(
            parsed, anthropic_usage_from_response(payload, self._model)
        )


class MistralLandmarkClient:
    """Echte, httpx-basierte Implementierung von LandmarkClientLike (ADR 0031 Punkt 2), exakt
    analog AnthropicLandmarkClient - direkter REST-Aufruf gegen die Mistral Chat Completions API,
    kein Mistral-SDK. `transport` ist injizierbar (httpx.MockTransport in Tests) -
    `build_landmark_client()` unten laeuft dagegen NIE in einem automatisierten Test (echtes
    Secret + echter Netzwerkversuch)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = LANDMARK_REQUEST_TIMEOUT_SECONDS,
        *,
        throttle: CloudRequestThrottle,
    ) -> None:
        self._model = model
        # Pflicht-Schluesselwortparameter ohne Default, Begruendung wortgleich zu
        # AnthropicLandmarkClient oben.
        self._throttle = throttle
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
            "model": self._model,
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
        # Spec 0382, K6 - Begruendung wortgleich zu AnthropicLandmarkClient.detect oben.
        response = await post_vision_request(
            self._client,
            MISTRAL_ENDPOINT,
            body,
            error_class=LandmarkApiError,
            throttle=self._throttle,
        )
        payload = response.json()
        parsed = mistral_response_to_json(payload, LandmarkApiError)
        return _landmark_detection_from_json(
            parsed, mistral_usage_from_response(payload, self._model)
        )


def build_landmark_client(model: str) -> LandmarkClientLike:
    """Dispatch-Factory zwischen AnthropicLandmarkClient (unveraendert, weiterhin Default) und
    MistralLandmarkClient je nach settings.landmark_provider (ADR 0031 Punkt 3). Analog
    build_face_detector/build_aesthetics_model: laeuft NIE in einem automatisierten Test (echtes
    Secret + echter Netzwerkversuch, Teststrategie-Abschnitt der Spec 0047/0054 - ein
    versehentlicher Aufruf in CI muesste als harter Fehlschlag auffallen).

    `model` ist seit specs/features/0304-cloud-modell-je-anbieter-waehlbar.md (ADR 0059 Punkt 7)
    ein Parameter statt einer hier gelesenen Modulkonstante: der Aufrufer loest das Modell EINMAL
    je Cloud-Phase auf und benutzt denselben Wert fuer Client-Bau, Kostenrechnung und Modellspalte
    des Laufs - "angezeigt = abgerechnet = tatsaechlich aufgerufen" wird dadurch strukturell wahr
    statt durch drei zufaellig uebereinstimmende Lesevorgaenge derselben globalen `settings`."""
    # specs/features/0382-cloud-rate-limits-aussitzen.md, K4: der PROZESSWEITE Schrittmacher des
    # eingestellten Anbieters - dieselbe Instanz, die auch
    # build_category_classification_client() zieht. Beide Cloud-Teilschritte und mehrere
    # gleichzeitig laufende Jobs teilen sich dadurch einen Schrittmacher je Anbieter; der
    # Anbieter sieht ohnehin nur eine einzige Quelle.
    throttle = throttle_for_provider(settings.landmark_provider)
    if settings.landmark_provider == "mistral":
        mistral_client: LandmarkClientLike = MistralLandmarkClient(
            api_key=settings.mistral_api_key, model=model, throttle=throttle
        )
        return mistral_client
    anthropic_client: LandmarkClientLike = AnthropicLandmarkClient(
        api_key=settings.anthropic_api_key, model=model, throttle=throttle
    )
    return anthropic_client
