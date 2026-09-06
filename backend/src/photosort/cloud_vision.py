from __future__ import annotations

import json
import logging
from dataclasses import dataclass
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

logger = logging.getLogger(__name__)

# specs/decisions/0031-mistral-provider-option-cloud-landmark.md Punkt 2: derselbe Endpunkt wie
# fuer reine Text-Completions, kein separater Vision-Pfad bei Mistral.
MISTRAL_CHAT_COMPLETIONS_URL = "https://api.mistral.ai/v1/chat/completions"

# Guenstigstes vision-faehiges Modell der Claude-Haiku-Reihe (ADR 0025: "kein Grund fuer ein
# teureres Modell bei dieser eng umrissenen Klassifikationsaufgabe") - providerneutral hier
# gefuehrt, weil sowohl landmark.py als auch remote_classification.py (ADR 0032) dasselbe
# vision-faehige Modell je Provider wiederverwenden, keine feature-spezifische Modellwahl.
# Seit specs/features/0304-cloud-modell-je-anbieter-waehlbar.md die VOREINSTELLUNG des Anbieters,
# nicht mehr sein einziges Modell (siehe VISION_MODELS_BY_PROVIDER unten).
ANTHROPIC_VISION_MODEL = "claude-haiku-4-5"

# Staerkeres, ebenfalls vision-faehiges Modell desselben Anbieters (Spec 0304) - waehlbar, aber
# NICHT Voreinstellung: ADR 0025/ADR 0031 Punkt 2 ("jeweils guenstigstes vision-faehiges Modell je
# Anbieter") bleibt als Voreinstellung unangetastet, die Story aendert ausdruecklich nur die
# Waehlbarkeit. Modell-ID und Vision-Faehigkeit verifiziert gegen die offizielle Modelluebersicht
# (https://platform.claude.com/docs/en/about-claude/models/overview, abgerufen 2026-09-06:
# "All current models support text and image input"), Preis siehe pricing.py.
ANTHROPIC_VISION_MODEL_SONNET = "claude-sonnet-5"

# Kleinstes/guenstigstes Modell der Ministral-3-Familie (ADR 0031 Punkt 2) - verifiziert gegen die
# offizielle Modelldokumentation (developer-Agent, 2026-08-23), siehe landmark.py-Historie.
# Ebenfalls seit Spec 0304 die Voreinstellung des Anbieters, nicht mehr sein einziges Modell.
MISTRAL_VISION_MODEL = "ministral-3b-2512"

# specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, decisions/0059-modellwahl-je-anbieter-
# und-modellgebundene-kostenschaetzung.md Punkt 2: die KURATIERTE AUSWAHL der waehlbaren Modelle je
# Anbieter - Nachfolger der frueheren 1:1-Zuordnung `VISION_MODEL_BY_PROVIDER` (Spec 0207/ADR 0051
# Punkt 2), die genau ein fest verdrahtetes Modell je Anbieter kannte.
#
# Geordnetes Tupel statt Menge (ADR 0059 Punkt 2): die Reihenfolge traegt eine Aussage - das ERSTE
# Element ist die Voreinstellung des Anbieters, also der Wert, der ohne gesetztes `LANDMARK_MODEL`
# gilt. Dieselbe Bauform wie die uebrigen Registries des Projekts (CATEGORY_REGISTRY,
# CRITERION_REGISTRY).
#
# Diese Registry ist die EINZIGE Quelle dafuer, was waehlbar ist: `config.py` validiert
# `LANDMARK_MODEL` beim Prozessstart dagegen, es gibt keinen Pfad, ueber den eine beliebige
# Modellbezeichnung an einen Anbieter geschickt wuerde (Akzeptanzkriterium "keine freie Eingabe").
#
# ACHTUNG - IMPORTRICHTUNG (ADR 0059 Punkt 2): `config.py` importiert dieses Modul (der Validator
# braucht die Registry). Dieses Modul darf `photosort.config` deshalb NIEMALS importieren, sonst
# entsteht ein Importzyklus. Ein Bedarf danach ist der Anlass, die Registry in ein eigenes,
# abhaengigkeitsfreies Modul zu ziehen - nicht den Zyklus zu bauen.
#
# Ein Modell, dessen Preis nicht gegen die offizielle Anbieterdokumentation verifiziert werden
# konnte, gehoert NICHT hierher (ADR 0059 Punkt 5): ein waehlbares Modell ohne gepflegten Preis
# waere ein waehlbarer Zustand ohne Kostenabsicherung. Die Vollstaendigkeit gegenueber
# `pricing.py::MODEL_PRICING` ist per Invariantentest erzwungen (tests/test_pricing.py).
VISION_MODELS_BY_PROVIDER: dict[str, tuple[str, ...]] = {
    "anthropic": (ANTHROPIC_VISION_MODEL, ANTHROPIC_VISION_MODEL_SONNET),
    "mistral": (MISTRAL_VISION_MODEL,),
}


def default_vision_model_for_provider(provider: str) -> str:
    """Voreinstellungs-Modell eines Provider-Schluessels (erstes Registry-Element). Ein hier
    unbekannter Provider faellt bewusst auf seinen eigenen Namen zurueck statt zu werfen: das
    Ergebnis ist dann eine Modell-ID, die `pricing.py::MODEL_PRICING` nicht kennt, und der Lauf
    wird als "nicht erfasst" ausgewiesen (ADR 0051 Punkt 2) - ein neuer Provider ohne Preispflege
    faellt damit auf, statt einen laufenden Cloud-Job mit einem KeyError abzubrechen.

    Durch das `Literal` auf `Settings.landmark_provider` ist dieser Rueckfall heute unerreichbar -
    genau deshalb kostet er nichts und bleibt wortgleich erhalten (ADR 0059 Punkt 2)."""
    models = VISION_MODELS_BY_PROVIDER.get(provider)
    if not models:
        return provider
    return models[0]


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


# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md Punkt 1 ab hier: der REALE Token-Verbrauch, den beide Provider in jeder Antwort
# mitliefern - bis zu dieser Spec gelesen und verworfen. Er existiert genau einmal, im Moment der
# Antwort, und ist danach unwiederbringlich; deshalb sitzt der Messpunkt hier, unmittelbar an der
# Antwort, und nicht irgendwo weiter oben im Aufrufpfad.


@dataclass(frozen=True)
class TokenUsage:
    """Providerneutraler Token-Verbrauch EINES Cloud-Vision-Aufrufs (ADR 0051 Punkt 1) - das
    gemeinsame Ziel der beiden providerspezifischen Extraktoren unten. Frozen wie
    LandmarkDetection/RemoteClassification: ein Messwert, kein veraenderlicher Zustand.

    Die Feldnamen folgen bewusst der Anthropic-Benennung (input/output), nicht der Mistral-
    Benennung (prompt/completion) - "Eingabe/Ausgabe" ist die providerneutrale Begrifflichkeit,
    in der auch die Preistabelle (pricing.py::ModelPricing) gefuehrt wird."""

    input_tokens: int
    output_tokens: int


def _usage_from_response(
    payload: Any, model: str, input_key: str, output_key: str
) -> TokenUsage | None:
    """Gemeinsame, defensive Extraktion fuer beide Provider - unterscheidet sich zwischen ihnen
    ausschliesslich in den beiden Feldnamen.

    Liefert `None` statt zu werfen (ADR 0051 Punkt 1): ein fehlender oder strukturell unerwarteter
    `usage`-Block ist KEIN Fehler - eine erfolgreiche Klassifizierung darf niemals daran
    scheitern, dass die Abrechnungsangabe fehlt. Der Aufruf traegt dann nichts zur Kostensumme
    bei; sichtbar wird die Luecke ueber die WARNING-Zeile hier UND (nutzerseitig) ueber Befund (b)
    des Unvollstaendigkeits-Hinweises (ADR 0051 Punkt 5), da worker.py die Aufrufzahl unabhaengig
    vom Tokenbeitrag hochzaehlt.

    Sicherheits-Muss-Kriterium (Spec 0207, Security Punkt 4, Muster ADR 0034 Punkt 5): die
    Logzeile enthaelt ausschliesslich eine feste Meldung, `type(exc).__name__` und die Modell-ID.
    Verboten sind `payload`/`repr(payload)`/`response.text`/`response.json()`/`response.headers`
    und `exc_info=True` - die Provider-Antwort traegt die Modellaussage ueber den BILDINHALT eines
    Familienfotos und im Fehlerfall potenziell ein Echo des Requests (Base64-Bilddaten) sowie
    Header (API-Key)."""
    try:
        usage = payload["usage"]
        input_tokens = usage[input_key]
        output_tokens = usage[output_key]
        # Bewusst strikt auf int/bool-freie Ganzzahlen geprueft statt int(...) zu erzwingen: ein
        # Gleitkomma-/String-Wert an dieser Stelle waere ein struktureller Bruch der
        # Provider-Zusage, kein zu rettender Sonderfall - und ein still gerundeter Wert waere als
        # Abrechnungsbeleg wertlos.
        if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
            raise TypeError("Token-Zaehler ist keine Ganzzahl")
        if isinstance(input_tokens, bool) or isinstance(output_tokens, bool):
            raise TypeError("Token-Zaehler ist ein Boolean")
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Token-Zaehler ist negativ")
        return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        logger.warning(
            "Verbrauchsangabe der Vision-Antwort nicht auswertbar (model=%s): %s",
            model,
            type(exc).__name__,
        )
        return None


def anthropic_usage_from_response(payload: Any, model: str) -> TokenUsage | None:
    """Liest `usage.input_tokens`/`usage.output_tokens` aus der Anthropic-Antworthuelle.

    Zusaetzliche Felder (Cache-Zaehler) werden bewusst ignoriert: die Ist-Rechnung dieser ADR
    kennt nur Basis-Input/-Output-Preise (pricing.py), kein Cache-Tarifmodell - das Projekt setzt
    kein Prompt-Caching ein."""
    return _usage_from_response(payload, model, "input_tokens", "output_tokens")


def mistral_usage_from_response(payload: Any, model: str) -> TokenUsage | None:
    """Liest `usage.prompt_tokens`/`usage.completion_tokens` aus der Mistral-Antworthuelle - die
    providerspezifisch ABWEICHENDEN Feldnamen sind der einzige Unterschied zum Anthropic-Gegenpart
    oben (OpenAI-kompatibles Chat-Completion-Schema)."""
    return _usage_from_response(payload, model, "prompt_tokens", "completion_tokens")
