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
from photosort.places import landmark_place_cell, sanitize_place_name

# Isoliertes Modul - haelt den synchronen criteria.py-Vertrag aller sieben lokalen Kriterien
# unangetastet. Direkter httpx-REST-Aufruf gegen die Anthropic Messages API, KEIN
# anthropic-Python-SDK - exakt das Muster von opencloud/client.py (eigene Exception-Klasse,
# httpx.AsyncClient, httpx.MockTransport-testbar).
#
# URLs, Modell-IDs, Timeout und die Response-Huellen-Helfer liegen providerneutral in
# cloud_vision.py; hier stehen nur re-exportierte Aliase.
#
# Die Modellwahl wirkt auf beide Cloud-Anteile einheitlich, nie zwei Modelle nebeneinander. Das
# Modell kommt als Konstruktor-Parameter herein und wird durchgereicht.
LANDMARK_REQUEST_TIMEOUT_SECONDS = VISION_REQUEST_TIMEOUT_SECONDS

# Kurze, reine Klassifikationsantwort - kein Grund fuer ein hohes max_tokens (nur ein kleines
# JSON-Objekt wird erwartet).
_MAX_RESPONSE_TOKENS = 256

# Sicherheits-Muss-Kriterium: Obergrenze eines verwendbaren Sehenswuerdigkeit-Namens. Wie
# `MAX_FINE_LABEL_LENGTH` eine DEGENERATIONSGRENZE, keine Sanitisierungsmassnahme - und wie dort
# wird VERWORFEN statt abgeschnitten: `events.py::LandmarkChangeSignal` vergleicht exakt, ein
# abgeschnittener Name fuehrte zwei verschiedene Sehenswuerdigkeiten in einem Event zusammen.
# Das Event faellt dann auf die Koordinatenstufe zurueck.
#
# 80 statt der 60 des Feinlabel-Pfads: Sehenswuerdigkeitsnamen sind laenger.
MAX_LANDMARK_NAME_LENGTH = 80

# DIE EINE GRENZE fuer jede Verwendung des Namens (ADR 0107 Punkt 1): ab hier gilt ein Treffer als
# sicher genug, `>=` und inklusiv. `criteria.py` liest sie von HIER als
# `CRITERIA_REGISTRY["landmark"].presence_threshold`, und die Importrichtung ist erzwungen -
# `criteria.py` importiert bereits aus diesem Modul, umgekehrt entstuende ein Zyklus. Solange der
# Wert an zwei Stellen geschrieben werden koennte, koennten Bewertung und Name auseinanderlaufen;
# genau das war der Ausgangszustand.
#
# Dokumentiert-unkalibriert (gleiche Klasse wie SHARPNESS_NORMALIZATION_CEILING, es gibt keinen
# Fotokorpus im Repo). Gegen das beobachtete Ueberidentifikations-Risiko des Vision-LLM ist sie die
# strukturelle, aber womoeglich nicht ausreichende Gegenmassnahme - ob sie steigen muss, entscheidet
# die Abnahme an einer echten Reise.
LANDMARK_CONFIDENCE_THRESHOLD = 0.5

_PROMPT = (
    "Analysiere dieses Foto. Ist eine bekannte oder auch weniger bekannte Sehenswuerdigkeit/ein "
    "Wahrzeichen zu erkennen? Antworte AUSSCHLIESSLICH mit einem einzigen validen JSON-Objekt, "
    "ohne Markdown-Codeblock, ohne weiteren Text, exakt in dieser Form: "
    '{"name": "<Name der Sehenswuerdigkeit oder null>", "confidence": <Zahl zwischen 0 und 1>}. '
    'Ist keine Sehenswuerdigkeit erkennbar, setze "name" auf null und "confidence" auf 0.'
)


class LandmarkApiError(Exception):
    """Fehler beim Aufruf der Anthropic Messages API (Netzwerk, 4xx/5xx, unerwartete
    Antwortstruktur) - analog OpenCloudError. SICHERHEIT: Meldungen betten NIEMALS den API-Key oder
    Base64-Bilddaten ein, nur Statuscode/Reason-Phrase bzw. eine generische
    Strukturbeschreibung."""


@dataclass(frozen=True)
class LandmarkDetection:
    """Ergebnis eines einzelnen Sehenswuerdigkeit-Erkennungsversuchs.
    `name` ist `None`, wenn keine Sehenswuerdigkeit identifiziert wurde - dann bleibt `confidence`
    bedeutungslos (per Konvention 0.0, aber nicht zu pruefen)."""

    name: str | None
    confidence: float
    # Der reale Token-Verbrauch DIESES Aufrufs, den worker.py ueber alle erfolgreichen Aufrufe der
    # Phase summiert. `None` heisst "nicht ermittelbar" (fehlender/kaputter usage-Block): der
    # Aufruf traegt dann nichts zur Tokensumme bei, wird aber trotzdem als stattgefundener Aufruf
    # gezaehlt.
    usage: TokenUsage | None = None


@dataclass(frozen=True)
class PlaceHint:
    """Die grobe Ortsangabe, die zusammen mit dem Foto hinausgeht - GENAU EINE der beiden Stufen.

    `locality` ist der aufgeloeste, sanitierte Ortsname; `cell` das auf
    `places.LANDMARK_PLACE_CELL_DIGITS` gerundete Zahlenpaar. Dass nie beide zugleich gesetzt sind,
    ist strukturell durchgesetzt und nicht bloss dokumentiert: eine Doppelbelegung waere der stille
    Weg, auf dem die Namensstufe ihre Schonung verloere und das Zahlenpaar zusaetzlich hinausginge.
    "Keine Angabe" wird als `None` STATT dieses Objekts ausgedrueckt, damit es nicht zwei
    Darstellungen derselben Abwesenheit gibt.

    Der Vorrat ist bewusst geschlossen: kein Viertel, keine Region, kein Land, kein
    zusammengesetzter Anzeigename, keine weitere Zeichenkette aus der Datenbank (ADR 0106 Punkt 6,
    S2/S4)."""

    locality: str | None = None
    cell: tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if (self.locality is None) == (self.cell is None):
            raise ValueError("Ein PlaceHint traegt genau eine Stufe: Ortsname ODER Zelle.")


def place_hint_for(
    locality: str | None, gps_lat: float | None, gps_lon: float | None
) -> PlaceHint | None:
    """Die Stufenwahl der Ortsangabe an genau EINER Stelle (ADR 0106 Punkt 2).

    Ortsname, sonst grobe Koordinate, sonst nichts. Beide Stufen sind dauerhaft; die
    Koordinatenstufe ist kein Uebergangszustand bis zu einer besseren Namensaufloesung, sie greift
    bevorzugt dort, wo sich kein Ortsname aufloesen liess.

    `locality` ist bereits das Ergebnis von `places.usable_locality` - es gibt keine zweite Fassung
    von "ein Ortsname gilt als aufgeloest" (S2). Er laeuft hier dennoch ein weiteres Mal durch
    `sanitize_place_name`: Das ist der AUSGEHENDE Rand, und er verlaesst sich nicht auf die
    Sanitisierung am Schreibrand. Ueberlebt der Name sie nicht, greift die Koordinatenstufe - ein
    unbrauchbarer Name macht das Foto nicht ortlos.

    OHNE eigene gemessene Koordinate gibt es GAR KEINEN Hinweis, und damit strukturell auch keinen
    Ortsnamen: der Name stammt aus der Zelle des Fotos. Eine ueber `events.py::infer_locations`
    uebernommene Koordinate erreicht diese Funktion nie (S3) - eine Schaetzung truege Ortsdaten auch
    fuer Aufnahmen hinaus, die selbst nie eine hatten. Das Fehlen ist kein Fehlerfall: das Foto wird
    unveraendert erkannt."""
    if gps_lat is None or gps_lon is None:
        return None
    name = sanitize_place_name(locality)
    if name is not None:
        return PlaceHint(locality=name)
    return PlaceHint(cell=landmark_place_cell(gps_lat, gps_lon))


class LandmarkClientLike(Protocol):
    """Schmale, injizierbare Schnittstelle - erlaubt ein Test-Double ohne echtes Netzwerk/Secret,
    analog FaceDetectorLike/OpenCloudScanClient."""

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection: ...


def sanitize_landmark_name(raw: object) -> str | None:
    """Der einzige Weg, auf dem ein Sehenswuerdigkeit-Name in PhotoSort verwendbar wird
    (Sicherheits-Muss-Kriterium). Bricht in
    tests/test_landmark.py::TestLandmarkNameSanitisation, acht Faelle.

    Zeichensanitisierung mit DERSELBEN Funktion wie der Feinlabel-Pfad
    (`cloud_vision.py::_sanitize_label_text`, nicht mit einer zweiten Fassung davon), danach die
    Laengengrenze. `None` heisst "kein verwendbarer Name" - Nicht-String, leer nach der
    Sanitisierung, oder laenger als `MAX_LANDMARK_NAME_LENGTH`.

    Die Funktion wird an ZWEI Stellen angewandt: an der Quelle in `_landmark_detection_from_json`
    unten UND beim Lesen der bereits persistierten Zeilen in `worker.py::_landmark_names`, aus dem
    `events.landmark_name` entsteht. Die Begruendung fuer die doppelte Anwendung steht dort - sie
    deckt den unsanierten Altbestand in `photo_landmark_detections`, fuer den es keinen
    kostenlosen Migrationsweg gibt."""
    if not isinstance(raw, str):
        return None
    sanitized = _sanitize_label_text(raw)
    if not sanitized or len(sanitized) > MAX_LANDMARK_NAME_LENGTH:
        return None
    return sanitized


def usable_landmark_name(
    name: object, confidence: float, canonical_name: object = None
) -> str | None:
    """Der Name, den eine Erkennungszeile fuer die Anzeige hergibt - oder `None`.

    GRENZE ZUERST, danach die Sanitisierung: Ein Treffer unterhalb von
    `LANDMARK_CONFIDENCE_THRESHOLD` ergibt keinen verwendbaren Namen, gleich wie einwandfrei er
    geschrieben ist. `None` heisst "kein verwendbarer Name" und ist von "nie erkannt" NICHT zu
    unterscheiden: es entsteht kein Anzeigezustand und kein Hinweis auf die verworfene Vermutung,
    das Foto faellt auf Ortsname bzw. Koordinate zurueck.

    Ueber die Verwendbarkeit entscheidet damit die LESESTELLE, nicht die Schreibstelle (ADR 0107
    Punkt 2): Die Erkennungszeile bleibt unveraendert vollstaendig - die Antwort ist bezahlt - und
    eine spaetere Aenderung der Grenze wirkt beim naechsten Neuaufbau der Gruppierung, ohne einen
    einzigen erneuten Cloud-Aufruf.

    Der KANONISCHE Name schlaegt den Rohnamen (ADR 0107 Punkt 5); eine Zeile ohne kanonischen Namen
    verhaelt sich exakt wie vor dem Register. SICHERHEIT (S9): `sanitize_landmark_name` wirkt auf
    den zurueckgegebenen Wert, GLEICH ob kanonischer Name oder Rohname - die Altbestandsdeckung
    darf nicht dadurch entfallen, dass ein neues Feld daneben tritt. Uebersteht der kanonische Name
    die Sanitisierung nicht, faellt der Aufruf auf den Rohnamen zurueck."""
    if confidence < LANDMARK_CONFIDENCE_THRESHOLD:
        return None
    return sanitize_landmark_name(canonical_name) or sanitize_landmark_name(name)


def _landmark_detection_from_json(
    parsed: Any, usage: TokenUsage | None = None
) -> LandmarkDetection:
    """Providerneutrale Extraktion von name/confidence aus dem bereits geparsten JSON-Objekt -
    wird von beiden Clients nach ihrer jeweils providerspezifischen Extraktion des rohen
    JSON-Texts aus ihrer unterschiedlichen Response-Huelle aufgerufen."""
    try:
        name = parsed.get("name")
        confidence = float(parsed.get("confidence", 0.0))
    except (AttributeError, TypeError, ValueError) as exc:
        # Generische, providerneutrale Meldung - an dieser Stelle ist kein Provider-Name mehr
        # bekannt.
        raise LandmarkApiError("Unerwartete Antwortstruktur der Vision-API-Antwort.") from exc
    if name is not None and not isinstance(name, str):
        raise LandmarkApiError("Unerwartete Antwortstruktur der Vision-API-Antwort.")
    # Sicherheits-Muss-Kriterium: Sanitisierung und Laengengrenze AN DER QUELLE. Solange der Name
    # nirgends gerendert wurde, ging er als Rohwert in die Datenbank - mit dem Rendern in der
    # Event-Ueberschrift faellt dieser Schutz weg. Ein zu langer Name wird GANZ verworfen, nie
    # abgeschnitten: `events.py::LandmarkChangeSignal` vergleicht exakt, ein abgeschnittener Name
    # fuehrte zwei verschiedene Sehenswuerdigkeiten in einem Event zusammen.
    name = sanitize_landmark_name(name)
    # Das Vision-LLM-JSON ist nicht garantiert auf [0, 1] begrenzt - geklemmt bereits HIER (an der
    # Quelle), nicht erst in criteria.py::compute_landmark_score.
    # worker.py::_upsert_landmark_detection schreibt detection.confidence UNVERAENDERT nach
    # photo_landmark_detections - ohne dieses Klemmen koennte dieser Wert von dem separat
    # geklemmten PhotoCriterionScore.value abweichen, obwohl beide atomar aus derselben API-Antwort
    # stammen sollen. compute_landmark_score klemmt zusaetzlich defensiv (bewusste Redundanz).
    clamped_confidence = max(0.0, min(1.0, confidence))
    return LandmarkDetection(name=name, confidence=clamped_confidence, usage=usage)


class AnthropicLandmarkClient:
    """Echte, httpx-basierte Implementierung von LandmarkClientLike - direkter REST-Aufruf gegen
    die Anthropic Messages API, kein anthropic-SDK. `transport` ist injizierbar
    (httpx.MockTransport in Tests, analog OpenCloudClient) - `build_landmark_client()` unten laeuft
    dagegen NIE in einem automatisierten Test (echtes Secret + echter Netzwerkversuch)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = LANDMARK_REQUEST_TIMEOUT_SECONDS,
        *,
        throttle: CloudRequestThrottle,
    ) -> None:
        # PFLICHTPARAMETER ohne Default: ein Default auf die Modulkonstante stellte genau die
        # Kopplung zwischen Modellwahl und Client wieder her - ein Aufrufer, der das Modell
        # vergisst, fiele nicht beim Typecheck auf, sondern erst in der Cloud-Rechnung.
        self._model = model
        # Der Schrittmacher ebenfalls als PFLICHT-SCHLUESSELWORTPARAMETER ohne Default, dieselbe
        # Begruendung wie beim Modell - ein Aufrufer, der ihn vergisst, fiele nicht beim Typecheck
        # auf, sondern erst an der Anfragerate des Anbieters.
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
        # Verteilung ueber den Schrittmacher und Wiederholung bei 429 liegen strukturell an genau
        # einer Stelle, nie in einer Kopie je Client. Meldungstexte und Statuslabel stecken in
        # ANTHROPIC_ENDPOINT.
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
    """Echte, httpx-basierte Implementierung von LandmarkClientLike, exakt analog
    AnthropicLandmarkClient - direkter REST-Aufruf gegen die Mistral Chat Completions API, kein
    Mistral-SDK. `transport` ist injizierbar (httpx.MockTransport in Tests) -
    `build_landmark_client()` unten laeuft dagegen NIE in einem automatisierten Test (echtes Secret
    + echter Netzwerkversuch)."""

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
                # Abweichend von Anthropics x-api-key+anthropic-version-Kombination -
                # Bearer-Token-Auth.
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
            # Nativer JSON-Mode - Mistral unterstuetzt das, Anthropic nicht (dort traegt allein
            # die Prompt-Anweisung).
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            # WICHTIG: image_url ist bei Mistral ein FLACHER String (Data-URI), KEIN
                            # verschachteltes {"url": "..."}-Objekt wie im OpenAI-Schema.
                            "image_url": (
                                f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode()}"
                            ),
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        }
        # Begruendung wortgleich zu AnthropicLandmarkClient.detect oben.
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
    """Dispatch-Factory zwischen AnthropicLandmarkClient (Default) und MistralLandmarkClient je
    nach settings.landmark_provider. Analog build_face_detector/build_aesthetics_model: laeuft NIE
    in einem automatisierten Test (echtes Secret + echter Netzwerkversuch - ein versehentlicher
    Aufruf in CI muesste als harter Fehlschlag auffallen).

    `model` ist ein Parameter statt einer hier gelesenen Modulkonstante: der Aufrufer loest das
    Modell EINMAL je Cloud-Phase auf und benutzt denselben Wert fuer Client-Bau, Kostenrechnung und
    Modellspalte des Laufs - "angezeigt = abgerechnet = tatsaechlich aufgerufen" wird dadurch
    strukturell wahr statt durch drei zufaellig uebereinstimmende Lesevorgaenge derselben globalen
    `settings`."""
    # Der PROZESSWEITE Schrittmacher des eingestellten Anbieters - dieselbe Instanz, die auch
    # build_category_classification_client() zieht. Beide Cloud-Teilschritte und mehrere
    # gleichzeitig laufende Jobs teilen sich dadurch einen Schrittmacher je Anbieter; der Anbieter
    # sieht ohnehin nur eine einzige Quelle.
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
