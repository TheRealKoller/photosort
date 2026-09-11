from __future__ import annotations

import asyncio
import json
import logging
import math
import time
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
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

# Staerkeres, ebenfalls vision-faehiges Modell desselben Anbieters - waehlbar, aber NICHT
# Voreinstellung (dieselbe Begruendung wie bei ANTHROPIC_VISION_MODEL_SONNET oben). Loest seit
# specs/features/0369-mistral-small-loest-ministral-8b-ab.md das mit Spec 0304 aufgenommene
# `ministral-8b-2512` ab - der erste Fall im Projekt, in dem ein waehlbarer Wert ZURUECKGENOMMEN
# statt ergaenzt wird. Der abgeloeste Wert ist samt Preiseintrag vollstaendig entfernt: eine
# bestehende `.env` mit `LANDMARK_MODEL=ministral-8b-2512` laesst Backend und Worker beim Start
# scheitern, und das ist beabsichtigt (kein Alias, keine Migrationszuordnung, kein stiller
# Modellwechsel - der abgerechnete Wert bliebe sonst vom konfigurierten entkoppelt).
#
# NAMENS-STOLPERSTEIN: "Small" bezeichnet hier das STAERKERE der beiden waehlbaren
# Mistral-Modelle - das ist Mistrals Produktnamensgebung ("Mistral Small 4", 119B Parameter,
# 6,5B aktiv), kein Vertipper und keine falsche Registry-Reihenfolge. Der Konstantenname folgt
# deshalb der FAMILIE (wie ANTHROPIC_VISION_MODEL_SONNET) statt der Parameterzahl; das fruehere
# `..._8B` waere fuer dieses Modell schlicht falsch.
#
# Modell-ID verifiziert gegen die offizielle Modellkarte
# (https://docs.mistral.ai/models/model-cards/mistral-small-4-0-26-03, abgerufen 2026-09-09;
# Release 2026-03-16). Bewusst die datierte ID und NICHT der gleitende Alias
# `mistral-small-latest` - der wanderte unter uns weg und machte jede Preisverifikation
# gegenstandslos. Preis siehe pricing.py (erstmals bei Mistral ASYMMETRISCH).
#
# VISION-FAEHIGKEIT - Belegkette mit offen dokumentierter Luecke (Entscheidung Daniels
# 2026-09-09; ab dieser Story gilt projektweit: ein waehlbares Modell braucht ZWEI belegte
# Tatsachen, verifizierten Token-Preis UND belegte Vision-Faehigkeit):
#   BELEGT - zwei erstparteiliche Quellen sagen ausdruecklich "accepts both text and image
#   inputs": die Ankuendigung https://mistral.ai/news/mistral-small-4/ und die offizielle
#   Modellkarte https://huggingface.co/mistralai/Mistral-Small-4-119B-2603 (beide abgerufen
#   2026-09-09).
#   LUECKE - https://docs.mistral.ai/capabilities/vision, die Seite, die die Bildeingabe ueber
#   /v1/chat/completions regelt, LISTET DAS MODELL ZUM ABRUFZEITPUNKT NICHT (2026-09-09). Sie ist
#   allerdings erkennbar einen Release-Zyklus veraltet (nennt Mistral Medium 3.1, waehrend die
#   Modelluebersicht bereits 3.5 fuehrt). Der Vermerk bleibt hier stehen, statt geglaettet zu
#   werden: die Faehigkeitsseite als Beleg zu zitieren, obwohl sie das Modell nicht fuehrt, waere
#   eine Falschaussage.
#   RISIKO - der plausible Ausfall ist laut, nicht still: ein Modell ohne Bildunterstuetzung
#   weist einen `image_url`-Content-Part mit 4xx zurueck, `raise_for_vision_api_status()` macht
#   daraus einen Fehler, der Aufruf zaehlt als `failed_calls` und ist in der Lauf-Bilanz sichtbar.
#   Der stille Fall (Bild angenommen, aber nur der Prompt bewertet) ist strukturell nicht
#   erkennbar; getragen wird er davon, dass Klassifizierungsergebnisse Vorschlaege in PhotoSorts
#   eigener Datenbank sind, der OpenCloud-Client ausschliesslich lesend arbeitet und ein Lauf
#   wiederholbar ist. `docs/setup.md` empfiehlt deshalb beim erstmaligen Umstellen einen kleinen
#   Probelauf mit Sichtpruefung.
MISTRAL_VISION_MODEL_SMALL = "mistral-small-2603"

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
    "mistral": (MISTRAL_VISION_MODEL, MISTRAL_VISION_MODEL_SMALL),
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


def provider_for_vision_model(model: str) -> str | None:
    """Der Anbieter, zu dem eine Modell-ID gehoert - die Rueckrichtung von
    `default_vision_model_for_provider` (specs/features/0348-klassifizierungs-transparenz.md,
    decisions/0068-klassifizierungslauf-vier-teilschritte-und-laufeigene-cloud-bilanz.md Punkt 6).

    Die Lauf-Zeilen speichern seit ADR 0059 Punkt 6 das MODELL, nicht den Anbieter; die
    Lauf-Bilanz nennt beides. Die fehlende Haelfte entsteht hier aus einer reinen Rueckwaertssuche
    ueber die Registry - NICHT aus einer weiteren Spalte und **niemals** aus
    `settings.landmark_provider`: die aktuelle Betriebseinstellung sagt nichts darueber, womit ein
    vergangener Lauf gerechnet hat. Genau diese Verwechslung hat ADR 0059 behoben, und
    sicherheitlich kann eine historische Lauf-Antwort damit strukturell nicht die heutige
    Konfiguration preisgeben.

    `None` (statt eines Rueckfalls) bei einem Modell, das nicht (mehr) in der Registry steht -
    Altlauf, entferntes Modell: die Oberflaeche zeigt dann die Modell-ID allein, statt einen
    Anbieter zu raten. Ein geratener Anbieter waere eine Behauptung ueber die Vergangenheit, die
    diese Funktion nicht belegen kann.

    Rein wie der Rest dieses Moduls: kein `photosort.config`-Import (`config.py` importiert dieses
    Modul, die Gegenrichtung erzeugte einen Importzyklus - ADR 0059 Punkt 2)."""
    for provider, models in VISION_MODELS_BY_PROVIDER.items():
        if model in models:
            return provider
    return None


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
        raise error_class("Unerwartete Antwortstruktur der Anthropic Messages API.") from exc


def mistral_response_to_json(payload: Any, error_class: type[Exception]) -> Any:
    """Extrahiert das vom Vision-LLM gelieferte JSON-Objekt aus der Mistral-spezifischen
    Response-Huelle (choices[0].message.content, Standard-Chat-Completion-Schema) - der
    providerspezifische Gegenpart zu anthropic_response_to_json oben."""
    try:
        text = payload["choices"][0]["message"]["content"]
        return json.loads(text)
    except (KeyError, TypeError, IndexError, ValueError, json.JSONDecodeError) as exc:
        raise error_class("Unerwartete Antwortstruktur der Mistral Chat Completions API.") from exc


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


def _sanitize_label_text(raw: str) -> str:
    """Zeichensanitisierung eines frei formulierten, von einem Vision-Modell erzeugten Textes
    (Security-Abschnitt der Spec 0289, Punkt 3).

    LIEGT SEIT specs/features/0051-gps-landmark-cluster-bildung.md HIER statt in
    remote_classification.py: sie wird inzwischen von BEIDEN Cloud-Pfaden gebraucht - vom
    Feinlabel-Pfad (`remote_classification.py::_fine_labels_from_json`, vor der Laengenpruefung
    und vor resolve_canonical_label/_slugify) und vom Sehenswuerdigkeit-Pfad
    (`landmark.py::sanitize_landmark_name`). Das Sicherheitskonzept verlangt ausdruecklich
    DIESELBE Funktion, nicht eine zweite Fassung davon, und `cloud_vision.py` ist bereits die
    providerneutrale gemeinsame Schicht beider Pfade.

    Entfernt alle Unicode-Steuer- und Formatzeichen (Kategorien `Cc`/`Cf`: `\x00`,
    Zero-Width-Zeichen wie U+200B, Bidi-Overrides wie U+202E) und zieht Whitespace-Folgen zu einem
    einzelnen Leerzeichen zusammen. Steuerzeichen, die selbst Whitespace SIND (Zeilenumbruch,
    Tabulator, Wagenruecklauf), werden dabei durch ein Leerzeichen ersetzt statt ersatzlos
    entfernt - sonst verschmoelzen zwei Woerter ueber einen Zeilenumbruch hinweg zu einem
    (`str.split()` behandelt auch NBSP
    und andere Unicode-Leerzeichen als Whitespace); fuehrende/abschliessende Leerzeichen
    entfallen dabei mit.

    Bewusst eine BLACKLIST (Steuerzeichen), keine Zeichen-Whitelist (Entscheidung 1 der Spec
    0289): der Text ist freier deutscher Text, eine Whitelist aus Buchstaben/Ziffern/Leerzeichen/
    Bindestrich wuerde legitime Werte beschaedigen. Escapetes Rendering im Frontend schuetzt
    gegen XSS, aber weder gegen optische Verfaelschung der Oberflaeche durch Bidi-/Zero-Width-
    Zeichen noch gegen mehrzeilige Logeintraege - genau diese Luecke schliesst diese Funktion.
    Nachruestbar an genau dieser einen Stelle, falls sich die Blacklist als zu schwach erweist."""
    without_controls = "".join(
        (" " if char.isspace() else "") if unicodedata.category(char) in ("Cc", "Cf") else char
        for char in raw
    )
    return " ".join(without_controls.split())


# specs/features/0382-cloud-rate-limits-aussitzen.md, decisions/0074-cloud-vision-schrittmacher-
# je-anbieter-und-wiederholung-nur-bei-429.md ab hier: Verteilung (Schrittmacher) und
# Wiederholung bei HTTP 429 - der EINE Ort, durch den seitdem alle vier Cloud-Aufrufstellen
# senden (ADR 0074 Entscheidung 1). Bewusst hier und nicht in landmark.py/remote_classification.py:
# ADR 0032 Punkt 3 hat dieses Modul genau fuer providerneutrale HTTP-Bausteine angelegt.
#
# Dieses Modul bleibt KONFIGURATIONSFREI (es darf photosort.config nicht importieren, ADR 0059
# Punkt 2 - die Gegenrichtung existiert bereits fuer den LANDMARK_MODEL-Validator). Der
# MECHANISMUS steht deshalb hier, die prozessweiten INSTANZEN leben in cloud_vision_throttle.py.


@dataclass(frozen=True)
class ThrottleStats:
    """Zaehlerstand EINES Schrittmachers (ADR 0074 Entscheidung 8) - reine Zahlen, nie eine
    Antwort und nie ein Headerwert (Sicherheits-Muss-Kriterium der Spec 0382, Punkt 4). Frozen wie
    TokenUsage daneben: ein Messwert, kein veraenderlicher Zustand.

    Die Zaehler sind PROZESSWEIT (eine Instanz je Anbieter, von beiden Cloud-Teilschritten und
    mehreren gleichzeitigen Laeufen geteilt). Fuer eine Aussage ueber einen einzelnen Teilschritt
    ist deshalb ausschliesslich die DIFFERENZ zweier Schnappschuesse brauchbar - siehe `since`."""

    delayed_requests: int
    total_delay_seconds: float
    retries: int
    total_retry_wait_seconds: float

    def since(self, previous: ThrottleStats) -> ThrottleStats:
        """Der Zuwachs gegenueber einem frueheren Schnappschuss.

        Geklemmt auf `>= 0`: die Zaehler eines prozessweiten Schrittmachers wachsen zwar
        monoton, aber eine negative Zahl in einer Logzeile ("-3 Anfragen eingereiht") waere ein
        stiller Aussagefehler statt eines auffallenden Fehlschlags."""
        return ThrottleStats(
            delayed_requests=max(0, self.delayed_requests - previous.delayed_requests),
            total_delay_seconds=max(0.0, self.total_delay_seconds - previous.total_delay_seconds),
            retries=max(0, self.retries - previous.retries),
            total_retry_wait_seconds=max(
                0.0, self.total_retry_wait_seconds - previous.total_retry_wait_seconds
            ),
        )


class CloudRequestThrottle:
    """Schrittmacher: haelt einen MINDESTABSTAND zwischen zwei Anfragen an denselben Anbieter.

    Bewusst KEIN Token-Bucket (ADR 0074 Entscheidung 2): ein Bucket erlaubt genau den Stoss, der
    den `429` ausloest - Anthropic dokumentiert selbst, eine Minutenrate koenne sekundengenau
    durchgesetzt werden.

    `clock`/`sleep` sind Konstruktor-Parameter (Voreinstellungen `time.monotonic`/`asyncio.sleep`).
    Ohne sie waere weder diese Klasse noch `post_vision_request` ohne echte Wartezeit testbar -
    `post_vision_request` wartet ausdruecklich AUSSCHLIESSLICH ueber den `sleep` dieses Objekts
    (Auflage 1 der Teststrategie der Spec 0382), es gibt keinen zweiten Zeitgeber im Pfad.

    `min_interval_seconds=0.0` ist ein gueltiger Wert und bedeutet "kein Schrittmacher"; das ist
    die Bauform, mit der die Client-Tests konstruieren."""

    def __init__(
        self,
        min_interval_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._min_interval_seconds = min_interval_seconds
        self._clock = clock
        self._sleep = sleep
        # `-inf` statt `clock()`: der erste Aufruf wartet dadurch nie, ohne dass beim BAU der
        # Instanz (Importzeit von cloud_vision_throttle.py) schon die Uhr gelesen werden muesste.
        self._next_free = float("-inf")
        self._delayed_requests = 0
        self._total_delay_seconds = 0.0
        self._retries = 0
        self._total_retry_wait_seconds = 0.0

    @property
    def min_interval_seconds(self) -> float:
        """Der gehaltene Mindestabstand - lesbar herausgegeben fuer den Invariantentest, der die
        Einreihung eines vollen Anfrage-Blocks gegen worker.py::STALL_THRESHOLD rechnet."""
        return self._min_interval_seconds

    @property
    def sleep(self) -> Callable[[float], Awaitable[None]]:
        """Der Zeitgeber dieses Schrittmachers - lesbar herausgegeben, damit
        `post_vision_request` seine Wiederholungs-Wartezeiten ueber DENSELBEN Zeitgeber nimmt
        (Auflage 1 der Teststrategie der Spec 0382)."""
        return self._sleep

    async def acquire(self) -> None:
        """Reiht die aufrufende Anfrage ein - vor JEDEM Absenden, erster Versuch wie jede
        Wiederholung (K4).

        Die Reservierung ist bewusst SPERRENFREI und muss es bleiben: zwischen dem Lesen und dem
        Zurueckschreiben von `_next_free` steht kein `await`, dadurch ist der Abschnitt im
        Einzel-Loop von asyncio atomar. Stuende dort eines, bekaemen mehrere gleichzeitige
        Aufrufer denselben Startzeitpunkt und der Schrittmacher waere wirkungslos - genau das
        prueft der `asyncio.gather`-Fall in test_cloud_vision.py nach."""
        now = self._clock()
        start = max(now, self._next_free)
        self._next_free = start + self._min_interval_seconds
        wait = start - now
        if wait > 0:
            self._delayed_requests += 1
            self._total_delay_seconds += wait
            # KEIN Abfangen von BaseException hier oder beim Aufrufer (Sicherheits-Muss-Kriterium
            # der Spec 0382, Punkt 5): ein verschlucktes CancelledError machte den Job
            # unabbrechbar (ADR 0068 Punkt 2).
            await self._sleep(wait)

    def record_retry_wait(self, seconds: float) -> None:
        """Bucht eine Wiederholungs-Wartezeit von `post_vision_request` ein. Die beiden
        Wiederholungs-Zaehler leben hier und nicht im Aufrufer, weil `ThrottleStats` sie sonst
        nicht fuehren koennte - der Worker liest ausschliesslich diesen einen Zaehlerstand ab."""
        self._retries += 1
        self._total_retry_wait_seconds += seconds

    def stats(self) -> ThrottleStats:
        return ThrottleStats(
            delayed_requests=self._delayed_requests,
            total_delay_seconds=self._total_delay_seconds,
            retries=self._retries,
            total_retry_wait_seconds=self._total_retry_wait_seconds,
        )


def retry_after_seconds(response: httpx.Response, *, now: datetime | None = None) -> float | None:
    """Die vom Anbieter angegebene Wartezeit in Sekunden - oder `None` fuer "keine Angabe" (K2).

    Beide vom HTTP-Standard erlaubten Formen werden gelesen: Ganzzahl-Sekunden und HTTP-Datum.
    `retry-after-ms` wird bewusst NICHT ausgewertet (ADR 0074 Entscheidung 5).

    "Nicht auswertbar" ist ausdruecklich KEIN Fehler, sondern "keine Angabe" - der Aufrufer faellt
    dann auf die verdoppelnde Staffel zurueck. Das ist bei Mistral der eingeplante Normalfall, dort
    ist kein `Retry-After` dokumentiert.

    SICHERHEITS-MUSS-KRITERIEN der Spec 0382 (Punkt 2), jedes testseitig abgedeckt:
    (a) `math.isfinite` VOR jeder Verwendung - `float("nan")`/`float("inf")` parsen erfolgreich und
        sind "keine Angabe", nicht ein grosser Wert. Nachgestellt (Python 3.12):
        `min(float("nan"), 60.0)` liefert `nan` (die Argumentreihenfolge entscheidet!), und
        `nan > budget` ist immer `False` - die Deckelung per `min(...)` ersetzt die Pruefung also
        NICHT, ohne sie fielen beide Zeit-Deckel des Aufrufers lautlos aus.
    (b) Es traegt KEINE Exception aus dem Header nach aussen. Der Wert ist eine Eingabe von aussen
        und unterliegt derselben Validierungspflicht wie jeder Request-Body; ein `ValueError` aus
        `parsedate_to_datetime` oder aus der `sys.set_int_max_str_digits`-Grenze ist "keine
        Angabe", kein Fehlerpfad. Deshalb hier bewusst breit `except Exception` - und ausdruecklich
        NIEMALS `BaseException`, sonst verschluckte diese Funktion ein `CancelledError`.
    (c) Rueckgabe ist `> 0` oder `None`, NIE eine negative Zahl. Die Gefahr ist nicht
        `asyncio.sleep(-5)` (das kehrt sofort zurueck), sondern ein negativer Summand, der das
        Restbudget des Aufrufers vergroessern wuerde.
    (d) Ein naives Datum ohne Zeitzone wird als UTC gelesen, nie als Ortszeit des Prozesses.
    (e) Rueckgabetyp `float | None` - niemals ein durchgereichter String.

    `now` ist ausschliesslich fuer die Tests injizierbar (Auflage 2 der Teststrategie der Spec
    0382): ohne einen festen Bezugszeitpunkt waeren die HTTP-Datum-Faelle nur mit einem
    Toleranzfenster pruefbar."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None

    try:
        seconds = float(raw)
    except Exception:
        seconds = None
    if seconds is not None:
        if not math.isfinite(seconds) or seconds <= 0:
            return None
        return seconds

    try:
        target = parsedate_to_datetime(raw)
    except Exception:
        return None
    if target is None:
        return None
    if target.tzinfo is None:
        # (d): zonenlos heisst UTC. `astimezone()` laese es als ORTSZEIT des Prozesses - auf einer
        # UTC-Maschine faellt der Unterschied nicht auf, im Betrieb schon.
        target = target.replace(tzinfo=UTC)

    reference = now if now is not None else datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)

    delta = (target - reference).total_seconds()
    if not math.isfinite(delta) or delta <= 0:
        return None
    return delta


@dataclass(frozen=True)
class VisionEndpoint:
    """Die anbieterspezifischen Tatsachen EINES Cloud-Vision-Endpunkts, gebuendelt - damit
    `post_vision_request` providerneutral bleiben kann und trotzdem die gewohnten Meldungstexte
    erzeugt.

    `status_label` und `unreachable_label` sind reiner Meldungstext und bleiben WORTGLEICH zu den
    bisher an den vier Aufrufstellen eingebetteten Fassungen (Regressionspflicht der Spec 0382):
    bestehende Assertions in test_landmark.py/test_remote_classification.py bleiben dadurch ohne
    Aenderung gruen, und die in ADR 0035 Punkt 3 verifizierte Sanierung der Fehlermeldung (kein
    Key, keine Bilddaten, keine Query-Parameter) gilt unveraendert.

    `provider` ist der Schluessel der Schrittmacher-Registry (cloud_vision_throttle.py) und das
    EINZIGE Feld, das in eine Logzeile gehen darf."""

    url: str
    provider: str
    status_label: str
    unreachable_label: str


ANTHROPIC_ENDPOINT = VisionEndpoint(
    url=ANTHROPIC_MESSAGES_URL,
    provider="anthropic",
    status_label="Anthropic",
    unreachable_label="Anthropic Vision API",
)

MISTRAL_ENDPOINT = VisionEndpoint(
    url=MISTRAL_CHAT_COMPLETIONS_URL,
    provider="mistral",
    status_label="Mistral",
    unreachable_label="Mistral Chat Completions API",
)


# specs/features/0382-cloud-rate-limits-aussitzen.md, decisions/0074-cloud-vision-schrittmacher-
# je-anbieter-und-wiederholung-nur-bei-429.md Entscheidung 7: die VOREINSTELLUNG der Anfragerate
# je Anbieter - der Wert, der ohne gesetztes `CLOUD_VISION_REQUESTS_PER_MINUTE` gilt.
#
# Warum HIER und nicht in cloud_vision_throttle.py, wo die Instanzen leben: `config.py` loest die
# Rate auf (`resolved_cloud_vision_requests_per_minute`) und muesste die Tabelle sonst aus
# cloud_vision_throttle.py importieren - das Modul, das seinerseits `config.py` importiert, um die
# Instanzen zu bauen. Das waere ein Importzyklus. Die Tabelle gehoert damit in dasselbe
# konfigurationsfreie Modul wie VISION_MODELS_BY_PROVIDER daneben, das aus genau demselben Grund
# hier steht und dieselbe Rolle fuer `LANDMARK_MODEL` spielt (ADR 0059 Punkt 2).
#
# Belegpflicht analog ADR 0059 Punkt 5 (Modellpreise), Recherchestand 2026-09-10 - die
# vollstaendige Herleitung beider Zahlen steht in ADR 0074 Entscheidung 7:
#   anthropic: 60/min (1 Anfrage/s). Erstparteilich dokumentiert sind fuer die niedrigste
#     VEROEFFENTLICHTE Stufe ("Start") 1.000 RPM; die Voreinstellung liegt bewusst weit darunter,
#     weil dieselbe Doku neue Organisationen in einer Evaluation-Stufe "with limits below the
#     standard limits shown on this page" (Zahlen nicht veroeffentlicht) startet und eine
#     Minutenrate sekundengenau durchgesetzt werden kann.
#   mistral: 40/min (1 Anfrage alle 1,5 s). NICHT ERSTPARTEILICH BELEGBAR - Mistral veroeffentlicht
#     keine Zahlen mehr je Tarif und verweist ausschliesslich auf das Admin-Panel des eigenen
#     Kontos; der fruehere Hilfeartikel liefert seit dem Recherchestand 404. Eine begruendete
#     Setzung, keine belegte Grenze - und genau der Fall, fuer den die Betriebsvariable existiert.
#     Die Beleglucke bleibt hier stehen, statt geglaettet zu werden.
#
# Bewusst VORSICHTIG: eine zu vorsichtige Voreinstellung macht einen Lauf langsamer und ist ueber
# die Variable zu heben; eine zu grosszuegige fuehrt genau den Zustand herbei, den Spec 0382
# abschafft. Der verlaessliche Wert fuer ein konkretes Konto steht nur im Admin-Panel des
# Anbieters - `docs/setup.md` sagt, wo er nachzusehen ist.
#
# Die Tabelle deckt genau die Anbieter von `Settings.landmark_provider` ab (per Test erzwungen):
# ein neuer Anbieter ohne Eintrag waere ein KeyError beim Prozessstart.
DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER: dict[str, int] = {
    "anthropic": 60,
    "mistral": 40,
}


# ADR 0074 Entscheidung 6/7: die Lauf-Zeitgrenze wird NICHT abgefragt, sondern durch ein hart
# gedeckeltes Wartebudget eingehalten. Der Wartevorgang sitzt im HTTP-Client und hat KEINEN
# Session-Zugriff - `last_progress_at` von hier zu schreiben verbietet sich (siehe Docstring von
# worker.py::_detect_landmark_for_photo: "bewusst OHNE Session-Zugriff, damit mehrere Aufrufe
# sicher parallel per asyncio.gather laufen koennen").
#
# Modulkonstanten und ausdruecklich KEINE Settings-Felder (ADR 0074 Entscheidung 7): sie haengen
# nicht an einer Kontostufe des Betreibers, sondern an der Watchdog-Rechnung unten - und sind
# damit gerade keine Werte, die ohne Kenntnis dieser Rechnung verstellt werden sollten. Die
# einzige neue Betriebsvariable ist die RATE (CLOUD_VISION_REQUESTS_PER_MINUTE).
#
# Schlimmster Fall je Anfrage: 120 s Warten + 5 x 60 s (VISION_REQUEST_TIMEOUT_SECONDS) = 420 s
# gegen worker.py::STALL_THRESHOLD von 15 Minuten. Diese Rechnung ist als Invariantentest
# festgeschrieben (tests/test_cloud_vision.py) - im Produktivcode gibt es die Verbindung bewusst
# nicht, cloud_vision.py darf worker.py nicht importieren.
VISION_MAX_RATE_LIMIT_ATTEMPTS = 5  # Versuche INSGESAMT, nicht Wiederholungen
VISION_RETRY_BUDGET_SECONDS = 120.0  # summierte Wartezeit EINER Anfrage
VISION_MAX_SINGLE_WAIT_SECONDS = 60.0  # je einzelnem Wartevorgang
VISION_INITIAL_RETRY_WAIT_SECONDS = 2.0  # Startwert der verdoppelnden Staffel

# Feste Literale fuer die Herkunft der Wartezeit in der Logzeile (Sicherheits-Muss-Kriterium der
# Spec 0382, Punkt 4: nie der rohe Headerwert, nur ein festes Literal).
_WAIT_SOURCE_PROVIDER = "Anbieterangabe"
_WAIT_SOURCE_LADDER = "Staffel"


async def post_vision_request(
    client: httpx.AsyncClient,
    endpoint: VisionEndpoint,
    body: Any,
    *,
    error_class: type[Exception],
    throttle: CloudRequestThrottle,
) -> httpx.Response:
    """Der EINE Sende- und Wiederholungspfad aller vier Cloud-Aufrufstellen (K6, ADR 0074
    Entscheidung 1) - Verteilung ueber den Schrittmacher, Wiederholung ausschliesslich bei `429`.

    Vor JEDEM Absenden (erster Versuch wie jede Wiederholung, K4) reiht sich die Anfrage in den
    Schrittmacher ein. Antwortet der Anbieter mit `429`, wird DIESELBE Anfrage nach einer
    Wartezeit erneut gestellt: die Angabe des Anbieters (`Retry-After`) schlaegt die verdoppelnde
    Staffel `2, 4, 8, 16 s`, beides gedeckelt auf `VISION_MAX_SINGLE_WAIT_SECONDS` und gemeinsam
    auf `VISION_RETRY_BUDGET_SECONDS`. Reicht das Restbudget nicht, wird SOFORT aufgegeben statt
    gekuerzt gewartet - eine halbe Wartezeit fuehrt auf denselben `429` und verbrennt eine
    Anfrage.

    JEDER ANDERE Fehlschlag fuehrt ohne jede Wiederholung und mit genau einem HTTP-Versuch zum
    gewohnten best-effort-Skip (K5, ADR 0025 Punkt 3/ADR 0032 Punkt 5 unveraendert):
    Netzwerkfehler, Zeitueberschreitung, `5xx` einschliesslich Anthropics `529`, `401`, `403`,
    jeder andere `4xx`. Die Wiederholungsbedingung ist deshalb exakt `== 429` und ausdruecklich
    kein `>= 429`, kein "4xx", kein `in range(...)` (Sicherheits-Muss-Kriterium der Spec 0382,
    Punkt 3): eine Wiederholung nach `401`/`403` sendete denselben API-Key fuenfmal gegen einen
    Endpunkt, der ihn gerade abgelehnt hat - das Muster, das anbieterseitige Missbrauchserkennung
    ausloest, und es kann per Definition nicht gelingen.

    Gewartet wird AUSSCHLIESSLICH ueber den `sleep` des Schrittmachers, nie ueber ein eigenes
    `asyncio.sleep` (Auflage 1 der Teststrategie der Spec 0382) - es gibt genau einen Zeitgeber in
    diesem Pfad, und er ist injizierbar.

    Gefangen wird ausschliesslich `Exception` (hier sogar nur `httpx.HTTPError`), NIEMALS
    `BaseException`, und es gibt weder ein nacktes `except:` noch ein `contextlib.suppress` noch
    ein `asyncio.shield` um den Wartevorgang (Sicherheits-Muss-Kriterium der Spec 0382, Punkt 5):
    `asyncio.sleep` ist damit ein echter Abbruchpunkt fuer `JOB_TIMEOUT_SECONDS` und den
    Worker-Shutdown. Ein verschlucktes `CancelledError` machte den Job unabbrechbar und liefe in
    genau den Zustand, den ADR 0068 Punkt 2 beschreibt (die Oberflaeche sagt "fehlgeschlagen",
    der Lauf ruft weiter kostenpflichtig an).

    `follow_redirects` wird ausdruecklich NICHT gesetzt und kein `3xx` als wiederholbar behandelt
    (Sicherheits-Muss-Kriterium der Spec 0382, Punkt 7) - sonst gingen API-Key und Bilddaten an
    ein vom Anbieter benanntes fremdes Ziel. `httpx` folgt per Voreinstellung keiner Weiterleitung.

    Nach erschoepftem Budget endet der Pfad dort, wo er heute schon endet: bei
    `raise_for_vision_api_status`, das die uebergebene, feature-eigene Fehlerklasse mit dem `429`
    im Text wirft. Es braucht dafuer keine neue Fehlerklasse und keine Aenderung am Fehlerpfad des
    Workers."""
    attempt = 0
    budget_remaining = VISION_RETRY_BUDGET_SECONDS
    while True:
        attempt += 1
        await throttle.acquire()
        try:
            response = await client.post(endpoint.url, json=body)
        except httpx.HTTPError as exc:
            # Kein embed von exc-Details ueber den httpx-eigenen Fehlertext hinaus - httpx-
            # Exceptions enthalten weder den API-Key (der lebt nur in den Request-Headern) noch
            # die Base64-Bilddaten. Wortgleich zu den vier bisherigen Aufrufstellen.
            raise error_class(f"{endpoint.unreachable_label} nicht erreichbar: {exc}") from exc

        if response.status_code != 429:
            break
        if attempt >= VISION_MAX_RATE_LIMIT_ATTEMPTS:
            break

        provider_wait = retry_after_seconds(response)
        if provider_wait is not None:
            wait = min(provider_wait, VISION_MAX_SINGLE_WAIT_SECONDS)
            source = _WAIT_SOURCE_PROVIDER
        else:
            # Die Staffel haengt am VERSUCHSZAEHLER, nicht daran, wie oft sie bisher gegriffen hat
            # (K3): eine einzelne Anbieterangabe dazwischen setzt sie nicht zurueck - sonst
            # koennte ein Anbieter mit einer einzigen kleinen Angabe die gesamte Staffel
            # flachhalten.
            wait = min(
                VISION_INITIAL_RETRY_WAIT_SECONDS * 2 ** (attempt - 1),
                VISION_MAX_SINGLE_WAIT_SECONDS,
            )
            source = _WAIT_SOURCE_LADDER
        if wait > budget_remaining:
            break
        budget_remaining -= wait

        # K8: genau EINE Zeile je Wiederholung. Erlaubt sind ausschliesslich das `provider`-Feld
        # des EIGENEN Konstantenwerts, der Versuchszaehler, die bereits geparste und gedeckelte
        # Wartezeit und ein festes Literal fuer deren Herkunft. Verboten (Sicherheits-Muss-
        # Kriterium der Spec 0382, Punkt 4): `body`, `json=...`, das httpx.Request-Objekt,
        # `client.headers`, `response.headers`, `response.text`, `response.json()` und der ROHE
        # Retry-After-Wert - letzterer ist zugleich die einzige Log-Injection-Flaeche des
        # Features, und indem nur die geparste Zahl in die Zeile geht, ist sie strukturell
        # geschlossen statt gefiltert.
        logger.warning(
            "Cloud-Vision-Anfrage gedrosselt (%s): Versuch %s von %s, %.1f s Wartezeit (%s)",
            endpoint.provider,
            attempt,
            VISION_MAX_RATE_LIMIT_ATTEMPTS,
            wait,
            source,
        )
        throttle.record_retry_wait(wait)
        await throttle.sleep(wait)

    raise_for_vision_api_status(response, endpoint.status_label, error_class)
    return response
