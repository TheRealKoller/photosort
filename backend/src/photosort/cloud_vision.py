from __future__ import annotations

import json
from typing import Any

import httpx

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
# decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 3: providerneutrale
# HTTP-/Parsing-Bausteine, extrahiert aus landmark.py (der ersten Cloud-Vision-Feature-Modul,
# decisions/0025/0031) - von landmark.py UND dem neuen remote_classification.py genutzt.
# Bewusst keine Feature-spezifische Logik hier (kein Prompt, kein Antwortschema-Parsing ueber die
# rohe JSON-Envelope hinaus) - das bleibt jeweils in landmark.py/remote_classification.py.

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

# specs/decisions/0031-mistral-provider-option-cloud-landmark.md Punkt 2: derselbe Endpunkt wie
# fuer reine Text-Completions, kein separater Vision-Pfad bei Mistral.
MISTRAL_CHAT_COMPLETIONS_URL = "https://api.mistral.ai/v1/chat/completions"

# Guenstigstes vision-faehiges Modell der Claude-Haiku-Reihe (ADR 0025: "kein Grund fuer ein
# teureres Modell bei dieser eng umrissenen Klassifikationsaufgabe") - providerneutral hier
# gefuehrt, weil sowohl landmark.py als auch remote_classification.py (ADR 0032) dasselbe,
# jeweils guenstigste vision-faehige Modell je Provider wiederverwenden, keine feature-spezifische
# Modellwahl.
ANTHROPIC_VISION_MODEL = "claude-haiku-4-5"

# Kleinstes/guenstigstes Modell der Ministral-3-Familie (ADR 0031 Punkt 2) - verifiziert gegen die
# offizielle Modelldokumentation (developer-Agent, 2026-08-23), siehe landmark.py-Historie.
MISTRAL_VISION_MODEL = "ministral-3b-2512"

# Modul-Konstante statt Settings-Feld (ADR 0025 Punkt 3: "reiner technischer Wert, kein
# Betriebsparameter") - grosszuegiger als der OpenCloud-Client-Default (30s), da Vision-LLM-
# Antwortzeiten tendenziell hoeher sind und beide Aufrufer Hintergrund-Jobs ohne wartenden Nutzer
# sind.
VISION_REQUEST_TIMEOUT_SECONDS = 60.0


def raise_for_vision_api_status(
    response: httpx.Response, provider_label: str, error_class: type[Exception]
) -> None:
    """Gemeinsame HTTP-Statuspruefung fuer beide Feature-Module (ADR 0025/0031, jetzt provider-
    UND feature-neutral) - `provider_label` ist reiner Meldungstext (z.B. "Anthropic"/"Mistral"),
    `error_class` die jeweils aufrufende, feature-eigene Exception-Klasse (LandmarkApiError bzw.
    RemoteCategoryClassificationApiError) - haelt `except LandmarkApiError`/
    `except RemoteCategoryClassificationApiError` an den jeweiligen Call-Sites unveraendert
    funktionsfaehig, ohne dass diese Funktion selbst eine der beiden Klassen kennen muss."""
    if response.status_code >= 400:
        raise error_class(
            f"{provider_label}-Anfrage fehlgeschlagen: "
            f"{response.status_code} {response.reason_phrase}"
        )


def anthropic_response_to_json(payload: Any, error_class: type[Exception]) -> Any:
    """Extrahiert das vom Vision-LLM gelieferte JSON-Objekt aus der Anthropic-spezifischen
    Response-Huelle (content-Blockliste mit type=="text") - providerspezifischer, aber feature-
    neutraler Teil (ADR 0025/0031/0032). Typvalidierung des extrahierten JSON-Inhalts selbst lebt
    NICHT hier, sondern jeweils feature-eigen in landmark.py/remote_classification.py."""
    try:
        content_blocks = payload["content"]
        text_block = next(block for block in content_blocks if block.get("type") == "text")
        return json.loads(text_block["text"])
    except (KeyError, TypeError, StopIteration, ValueError, json.JSONDecodeError) as exc:
        # Bewusst generische Meldung OHNE die rohe Antwort einzubetten (Sicherheits-Muss-
        # Kriterium: keine Base64-Bilddaten/kein Key in der Fehlermeldung).
        raise error_class(
            "Unerwartete Antwortstruktur der Anthropic Messages API."
        ) from exc


def mistral_response_to_json(payload: Any, error_class: type[Exception]) -> Any:
    """Extrahiert das vom Vision-LLM gelieferte JSON-Objekt aus der Mistral-spezifischen
    Response-Huelle (choices[0].message.content, Standard-Chat-Completion-Schema) - der
    providerspezifische Gegenpart zu anthropic_response_to_json oben."""
    try:
        text = payload["choices"][0]["message"]["content"]
        return json.loads(text)
    except (KeyError, TypeError, IndexError, ValueError, json.JSONDecodeError) as exc:
        raise error_class(
            "Unerwartete Antwortstruktur der Mistral Chat Completions API."
        ) from exc
