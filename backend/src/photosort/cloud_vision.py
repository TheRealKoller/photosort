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

# Providerneutrale HTTP-/Parsing-Bausteine, gemeinsam genutzt von landmark.py und
# remote_classification.py. Bewusst KEINE feature-spezifische Logik hier - kein Prompt, kein
# Antwortschema-Parsing über die rohe JSON-Hülle hinaus; das bleibt in den beiden Feature-Modulen.

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

logger = logging.getLogger(__name__)

# Derselbe Endpunkt wie für reine Text-Completions - bei Mistral gibt es keinen separaten
# Vision-Pfad.
MISTRAL_CHAT_COMPLETIONS_URL = "https://api.mistral.ai/v1/chat/completions"

# Günstigstes vision-fähiges Modell der Claude-Haiku-Reihe und damit die VOREINSTELLUNG des
# Anbieters (erstes Element in VISION_MODELS_BY_PROVIDER unten). Providerneutral hier geführt:
# beide Feature-Module verwenden dasselbe Modell je Anbieter, es gibt keine feature-spezifische
# Modellwahl.
ANTHROPIC_VISION_MODEL = "claude-haiku-4-5"

# Stärkeres, ebenfalls vision-fähiges Modell desselben Anbieters - wählbar, aber NICHT
# Voreinstellung; die bleibt das jeweils günstigste vision-fähige Modell je Anbieter. Modell-ID
# und Vision-Fähigkeit verifiziert gegen die offizielle Modellübersicht
# (https://platform.claude.com/docs/en/about-claude/models/overview, abgerufen 2026-09-06:
# "All current models support text and image input"), Preis siehe pricing.py.
ANTHROPIC_VISION_MODEL_SONNET = "claude-sonnet-5"

# Kleinstes/günstigstes Modell der Ministral-3-Familie, verifiziert gegen die offizielle
# Modelldokumentation (2026-08-23) - die Voreinstellung dieses Anbieters.
MISTRAL_VISION_MODEL = "ministral-3b-2512"

# Stärkeres, ebenfalls vision-fähiges Modell desselben Anbieters - wählbar, aber NICHT
# Voreinstellung.
#
# NAMENS-STOLPERSTEIN: "Small" bezeichnet hier das STÄRKERE der beiden wählbaren Mistral-Modelle -
# das ist Mistrals Produktnamensgebung ("Mistral Small 4", 119B Parameter, 6,5B aktiv), kein
# Vertipper und keine falsche Registry-Reihenfolge. Der Konstantenname folgt deshalb der FAMILIE
# (wie ANTHROPIC_VISION_MODEL_SONNET) statt der Parameterzahl.
#
# Modell-ID verifiziert gegen die offizielle Modellkarte
# (https://docs.mistral.ai/models/model-cards/mistral-small-4-0-26-03, abgerufen 2026-09-09).
# Bewusst die datierte ID und NICHT der gleitende Alias `mistral-small-latest` - der wanderte
# unter uns weg und machte jede Preisverifikation gegenstandslos.
#
# VISION-FÄHIGKEIT - Belegkette mit offen dokumentierter Lücke. Ein wählbares Modell braucht zwei
# belegte Tatsachen: verifizierten Token-Preis UND belegte Vision-Fähigkeit.
#   BELEGT - zwei erstparteiliche Quellen sagen ausdrücklich "accepts both text and image inputs":
#   https://mistral.ai/news/mistral-small-4/ und die Modellkarte
#   https://huggingface.co/mistralai/Mistral-Small-4-119B-2603 (beide abgerufen 2026-09-09).
#   LÜCKE - https://docs.mistral.ai/capabilities/vision, die Seite, die die Bildeingabe über
#   /v1/chat/completions regelt, LISTET DAS MODELL ZUM ABRUFZEITPUNKT NICHT (2026-09-09). Sie ist
#   erkennbar einen Release-Zyklus veraltet. Der Vermerk bleibt stehen, statt geglättet zu werden:
#   die Fähigkeitsseite als Beleg zu zitieren, obwohl sie das Modell nicht führt, wäre eine
#   Falschaussage.
#   RISIKO - der plausible Ausfall ist laut, nicht still: ein Modell ohne Bildunterstützung weist
#   einen `image_url`-Content-Part mit 4xx zurück, `raise_for_vision_api_status()` macht daraus
#   einen Fehler, der Aufruf zählt als `failed_calls` und ist in der Lauf-Bilanz sichtbar. Der
#   stille Fall (Bild angenommen, aber nur der Prompt bewertet) ist strukturell nicht erkennbar;
#   getragen wird er davon, dass Klassifizierungsergebnisse Vorschläge in PhotoSorts eigener
#   Datenbank sind, der OpenCloud-Client ausschließlich lesend arbeitet und ein Lauf wiederholbar
#   ist. `docs/setup.md` empfiehlt beim erstmaligen Umstellen einen Probelauf mit Sichtprüfung.
MISTRAL_VISION_MODEL_SMALL = "mistral-small-2603"

# Die kuratierte Auswahl der wählbaren Modelle je Anbieter.
#
# Geordnetes Tupel statt Menge: die Reihenfolge trägt eine Aussage - das ERSTE Element ist die
# Voreinstellung des Anbieters, also der Wert, der ohne gesetztes `LANDMARK_MODEL` gilt.
#
# Diese Registry ist die EINZIGE Quelle dafür, was wählbar ist: `config.py` validiert
# `LANDMARK_MODEL` beim Prozessstart dagegen, es gibt keinen Pfad, über den eine beliebige
# Modellbezeichnung an einen Anbieter geschickt würde - keine freie Eingabe.
#
# ACHTUNG - IMPORTRICHTUNG: `config.py` importiert dieses Modul (der Validator braucht die
# Registry). Dieses Modul darf `photosort.config` deshalb NIEMALS importieren, sonst entsteht ein
# Importzyklus. Ein Bedarf danach ist der Anlass, die Registry in ein eigenes,
# abhängigkeitsfreies Modul zu ziehen - nicht den Zyklus zu bauen.
#
# Ein Modell, dessen Preis nicht gegen die offizielle Anbieterdokumentation verifiziert werden
# konnte, gehört NICHT hierher: ein wählbares Modell ohne gepflegten Preis wäre ein wählbarer
# Zustand ohne Kostenabsicherung. Die Vollständigkeit gegenüber `pricing.py::MODEL_PRICING` ist
# per Invariantentest erzwungen (tests/test_pricing.py).
VISION_MODELS_BY_PROVIDER: dict[str, tuple[str, ...]] = {
    "anthropic": (ANTHROPIC_VISION_MODEL, ANTHROPIC_VISION_MODEL_SONNET),
    "mistral": (MISTRAL_VISION_MODEL, MISTRAL_VISION_MODEL_SMALL),
}


def default_vision_model_for_provider(provider: str) -> str:
    """Voreinstellungs-Modell eines Provider-Schlüssels (erstes Registry-Element).

    Ein hier unbekannter Provider fällt bewusst auf seinen eigenen Namen zurück statt zu werfen:
    das Ergebnis ist dann eine Modell-ID, die `pricing.py::MODEL_PRICING` nicht kennt, und der
    Lauf wird als "nicht erfasst" ausgewiesen - ein neuer Provider ohne Preispflege fällt damit
    auf, statt einen laufenden Cloud-Job mit einem KeyError abzubrechen. Durch das `Literal` auf
    `Settings.landmark_provider` ist dieser Rückfall heute unerreichbar."""
    models = VISION_MODELS_BY_PROVIDER.get(provider)
    if not models:
        return provider
    return models[0]


def provider_for_vision_model(model: str) -> str | None:
    """Der Anbieter, zu dem eine Modell-ID gehört - die Rückrichtung von
    `default_vision_model_for_provider`.

    Die Lauf-Zeilen speichern das MODELL, nicht den Anbieter; die Lauf-Bilanz nennt beides. Die
    fehlende Hälfte entsteht hier aus einer reinen Rückwärtssuche über die Registry - NICHT aus
    einer weiteren Spalte und **niemals** aus `settings.landmark_provider`: die aktuelle
    Betriebseinstellung sagt nichts darüber, womit ein vergangener Lauf gerechnet hat. So kann
    eine historische Lauf-Antwort strukturell nicht die heutige Konfiguration preisgeben.

    `None` (statt eines Rückfalls) bei einem Modell, das nicht (mehr) in der Registry steht -
    Altlauf, entferntes Modell: die Oberfläche zeigt dann die Modell-ID allein, statt einen
    Anbieter zu raten. Ein geratener Anbieter wäre eine Behauptung über die Vergangenheit, die
    diese Funktion nicht belegen kann.

    Rein wie der Rest dieses Moduls: kein `photosort.config`-Import (`config.py` importiert dieses
    Modul, die Gegenrichtung erzeugte einen Importzyklus)."""
    for provider, models in VISION_MODELS_BY_PROVIDER.items():
        if model in models:
            return provider
    return None


# Modul-Konstante statt Settings-Feld: reiner technischer Wert, kein Betriebsparameter.
# Großzügiger als der OpenCloud-Client-Default (30s), da Vision-LLM-Antwortzeiten tendenziell höher
# sind und beide Aufrufer Hintergrund-Jobs ohne wartenden Nutzer sind.
VISION_REQUEST_TIMEOUT_SECONDS = 60.0


def raise_for_vision_api_status(
    response: httpx.Response, provider_label: str, error_class: type[Exception]
) -> None:
    """Gemeinsame HTTP-Statusprüfung für beide Feature-Module, provider- und featureneutral.

    `provider_label` ist reiner Meldungstext (z.B. "Anthropic"/"Mistral"), `error_class` die
    jeweils aufrufende, feature-eigene Exception-Klasse - so bleibt `except …ApiError` an den
    Call-Sites funktionsfähig, ohne dass diese Funktion eine der Klassen kennen muss."""
    if response.status_code >= 400:
        raise error_class(
            f"{provider_label}-Anfrage fehlgeschlagen: "
            f"{response.status_code} {response.reason_phrase}"
        )


def anthropic_response_to_json(payload: Any, error_class: type[Exception]) -> Any:
    """Extrahiert das vom Vision-LLM gelieferte JSON-Objekt aus der Anthropic-spezifischen
    Response-Hülle (content-Blockliste mit type=="text") - providerspezifischer, aber
    featureneutraler Teil. Die Typvalidierung des extrahierten JSON-Inhalts lebt NICHT hier,
    sondern feature-eigen in landmark.py/remote_classification.py."""
    try:
        content_blocks = payload["content"]
        text_block = next(block for block in content_blocks if block.get("type") == "text")
        return json.loads(text_block["text"])
    except (KeyError, TypeError, StopIteration, ValueError, json.JSONDecodeError) as exc:
        # SICHERHEIT: bewusst generische Meldung OHNE die rohe Antwort - keine Base64-Bilddaten
        # und kein Key in der Fehlermeldung.
        raise error_class(
            "Unerwartete Antwortstruktur der Anthropic Messages API."
        ) from exc


def mistral_response_to_json(payload: Any, error_class: type[Exception]) -> Any:
    """Extrahiert das vom Vision-LLM gelieferte JSON-Objekt aus der Mistral-spezifischen
    Response-Hülle (choices[0].message.content, Standard-Chat-Completion-Schema) - der
    providerspezifische Gegenpart zu anthropic_response_to_json oben, mit derselben
    Sicherheitsauflage an der Fehlermeldung."""
    try:
        text = payload["choices"][0]["message"]["content"]
        return json.loads(text)
    except (KeyError, TypeError, IndexError, ValueError, json.JSONDecodeError) as exc:
        raise error_class(
            "Unerwartete Antwortstruktur der Mistral Chat Completions API."
        ) from exc


# Ab hier: der REALE Token-Verbrauch, den beide Provider in jeder Antwort mitliefern. Er
# existiert genau einmal, im Moment der Antwort, und ist danach unwiederbringlich - deshalb sitzt
# der Messpunkt hier, unmittelbar an der Antwort, und nicht weiter oben im Aufrufpfad.


@dataclass(frozen=True)
class TokenUsage:
    """Providerneutraler Token-Verbrauch EINES Cloud-Vision-Aufrufs - das gemeinsame Ziel der
    beiden providerspezifischen Extraktoren unten. Frozen: ein Messwert, kein veränderlicher
    Zustand.

    Die Feldnamen folgen bewusst der Anthropic-Benennung (input/output), nicht der
    Mistral-Benennung (prompt/completion) - "Eingabe/Ausgabe" ist die providerneutrale
    Begrifflichkeit, in der auch die Preistabelle (pricing.py::ModelPricing) geführt wird."""

    input_tokens: int
    output_tokens: int


def _usage_from_response(
    payload: Any, model: str, input_key: str, output_key: str
) -> TokenUsage | None:
    """Gemeinsame, defensive Extraktion für beide Provider - unterscheidet sich zwischen ihnen
    ausschließlich in den beiden Feldnamen.

    Liefert `None` statt zu werfen: ein fehlender oder strukturell unerwarteter `usage`-Block ist
    KEIN Fehler - eine erfolgreiche Klassifizierung darf niemals daran scheitern, dass die
    Abrechnungsangabe fehlt. Der Aufruf trägt dann nichts zur Kostensumme bei; sichtbar wird die
    Lücke über die WARNING-Zeile hier UND nutzerseitig über Befund (b) des
    Unvollständigkeits-Hinweises, da worker.py die Aufrufzahl unabhängig vom Tokenbeitrag
    hochzählt.

    SICHERHEIT: die Logzeile enthält ausschließlich eine feste Meldung, `type(exc).__name__` und
    die Modell-ID. Verboten sind `payload`/`repr(payload)`/`response.text`/`response.json()`/
    `response.headers` und `exc_info=True` - die Provider-Antwort trägt die Modellaussage über den
    BILDINHALT eines Familienfotos und im Fehlerfall potenziell ein Echo des Requests
    (Base64-Bilddaten) sowie Header (API-Key)."""
    try:
        usage = payload["usage"]
        input_tokens = usage[input_key]
        output_tokens = usage[output_key]
        # Bewusst strikt auf int/bool-freie Ganzzahlen geprüft statt int(...) zu erzwingen: ein
        # Gleitkomma-/String-Wert wäre hier ein struktureller Bruch der Provider-Zusage, kein zu
        # rettender Sonderfall - und ein still gerundeter Wert wäre als Abrechnungsbeleg wertlos.
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
    """Liest `usage.input_tokens`/`usage.output_tokens` aus der Anthropic-Antworthülle.

    Zusätzliche Felder (Cache-Zähler) werden bewusst ignoriert: die Ist-Rechnung kennt nur
    Basis-Input/-Output-Preise (pricing.py), kein Cache-Tarifmodell - das Projekt setzt kein
    Prompt-Caching ein."""
    return _usage_from_response(payload, model, "input_tokens", "output_tokens")


def mistral_usage_from_response(payload: Any, model: str) -> TokenUsage | None:
    """Liest `usage.prompt_tokens`/`usage.completion_tokens` aus der Mistral-Antworthülle - die
    providerspezifisch ABWEICHENDEN Feldnamen sind der einzige Unterschied zum Anthropic-Gegenpart
    oben (OpenAI-kompatibles Chat-Completion-Schema)."""
    return _usage_from_response(payload, model, "prompt_tokens", "completion_tokens")


def _sanitize_label_text(raw: str) -> str:
    """Zeichensanitisierung eines frei formulierten, von einem Vision-Modell erzeugten Textes.

    SICHERHEIT: BEIDE Cloud-Pfade müssen DIESELBE Funktion benutzen, nicht eine zweite Fassung
    davon - der Feinlabel-Pfad (`remote_classification.py::_fine_labels_from_json`, vor der
    Längenprüfung und vor resolve_canonical_label/_slugify) und der Sehenswürdigkeit-Pfad
    (`landmark.py::sanitize_landmark_name`). Deshalb liegt sie hier, in der providerneutralen
    gemeinsamen Schicht.

    Entfernt alle Unicode-Steuer- und Formatzeichen (Kategorien `Cc`/`Cf`: `\x00`,
    Zero-Width-Zeichen wie U+200B, Bidi-Overrides wie U+202E) und zieht Whitespace-Folgen zu einem
    einzelnen Leerzeichen zusammen. Steuerzeichen, die selbst Whitespace SIND (Zeilenumbruch,
    Tabulator, Wagenrücklauf), werden dabei durch ein Leerzeichen ersetzt statt ersatzlos entfernt
    - sonst verschmölzen zwei Wörter über einen Zeilenumbruch hinweg zu einem; führende und
    abschließende Leerzeichen entfallen mit.

    Bewusst eine BLACKLIST (Steuerzeichen), keine Zeichen-Whitelist: der Text ist freier deutscher
    Text, eine Whitelist aus Buchstaben/Ziffern/Leerzeichen/Bindestrich würde legitime Werte
    beschädigen. Escapetes Rendering im Frontend schützt gegen XSS, aber weder gegen optische
    Verfälschung der Oberfläche durch Bidi-/Zero-Width-Zeichen noch gegen mehrzeilige
    Logeinträge - genau diese Lücke schließt diese Funktion. Nachrüstbar an genau dieser einen
    Stelle, falls sich die Blacklist als zu schwach erweist."""
    without_controls = "".join(
        (" " if char.isspace() else "") if unicodedata.category(char) in ("Cc", "Cf") else char
        for char in raw
    )
    return " ".join(without_controls.split())


# Ab hier: Verteilung (Schrittmacher) und Wiederholung bei HTTP 429 - der EINE Ort, durch den
# alle vier Cloud-Aufrufstellen senden.
#
# Dieses Modul bleibt KONFIGURATIONSFREI (es darf photosort.config nicht importieren, die
# Gegenrichtung existiert bereits für den LANDMARK_MODEL-Validator). Der MECHANISMUS steht deshalb
# hier, die prozessweiten INSTANZEN leben in cloud_vision_throttle.py.


@dataclass(frozen=True)
class ThrottleStats:
    """Zählerstand EINES Schrittmachers - SICHERHEIT: reine Zahlen, nie eine Antwort und nie ein
    Headerwert. Frozen wie TokenUsage daneben: ein Messwert, kein veränderlicher Zustand.

    Die Zähler sind PROZESSWEIT (eine Instanz je Anbieter, von beiden Cloud-Teilschritten und
    mehreren gleichzeitigen Läufen geteilt). Für eine Aussage über einen einzelnen Teilschritt ist
    deshalb ausschließlich die DIFFERENZ zweier Schnappschüsse brauchbar - siehe `since`."""

    delayed_requests: int
    total_delay_seconds: float
    retries: int
    total_retry_wait_seconds: float

    def since(self, previous: ThrottleStats) -> ThrottleStats:
        """Der Zuwachs gegenüber einem früheren Schnappschuss.

        Geklemmt auf `>= 0`: die Zähler eines prozessweiten Schrittmachers wachsen zwar monoton,
        aber eine negative Zahl in einer Logzeile ("-3 Anfragen eingereiht") wäre ein stiller
        Aussagefehler statt eines auffallenden Fehlschlags."""
        return ThrottleStats(
            delayed_requests=max(0, self.delayed_requests - previous.delayed_requests),
            total_delay_seconds=max(0.0, self.total_delay_seconds - previous.total_delay_seconds),
            retries=max(0, self.retries - previous.retries),
            total_retry_wait_seconds=max(
                0.0, self.total_retry_wait_seconds - previous.total_retry_wait_seconds
            ),
        )


class CloudRequestThrottle:
    """Schrittmacher: hält einen MINDESTABSTAND zwischen zwei Anfragen an denselben Anbieter.

    Bewusst KEIN Token-Bucket: ein Bucket erlaubt genau den Stoß, der den `429` auslöst -
    Anthropic dokumentiert selbst, eine Minutenrate könne sekundengenau durchgesetzt werden.

    `clock`/`sleep` sind Konstruktor-Parameter (Voreinstellungen `time.monotonic`/`asyncio.sleep`).
    Ohne sie wäre weder diese Klasse noch `post_vision_request` ohne echte Wartezeit testbar -
    `post_vision_request` wartet ausdrücklich AUSSCHLIESSLICH über den `sleep` dieses Objekts, es
    gibt keinen zweiten Zeitgeber im Pfad.

    `min_interval_seconds=0.0` ist ein gültiger Wert und bedeutet "kein Schrittmacher"; das ist
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
        """Der gehaltene Mindestabstand - lesbar herausgegeben für den Invariantentest, der die
        Einreihung eines vollen Anfrage-Blocks gegen worker.py::STALL_THRESHOLD rechnet."""
        return self._min_interval_seconds

    @property
    def sleep(self) -> Callable[[float], Awaitable[None]]:
        """Der Zeitgeber dieses Schrittmachers - lesbar herausgegeben, damit
        `post_vision_request` seine Wiederholungs-Wartezeiten über DENSELBEN Zeitgeber nimmt."""
        return self._sleep

    async def acquire(self) -> None:
        """Reiht die aufrufende Anfrage ein - vor JEDEM Absenden, erster Versuch wie jede
        Wiederholung.

        Die Reservierung ist bewusst SPERRENFREI und muss es bleiben: zwischen dem Lesen und dem
        Zurückschreiben von `_next_free` steht kein `await`, dadurch ist der Abschnitt im
        Einzel-Loop von asyncio atomar. Stünde dort eines, bekämen mehrere gleichzeitige Aufrufer
        denselben Startzeitpunkt und der Schrittmacher wäre wirkungslos - genau das prüft der
        `asyncio.gather`-Fall in test_cloud_vision.py nach."""
        now = self._clock()
        start = max(now, self._next_free)
        self._next_free = start + self._min_interval_seconds
        wait = start - now
        if wait > 0:
            self._delayed_requests += 1
            self._total_delay_seconds += wait
            # SICHERHEIT: KEIN Abfangen von BaseException hier oder beim Aufrufer - ein
            # verschlucktes CancelledError machte den Job unabbrechbar.
            await self._sleep(wait)

    def record_retry_wait(self, seconds: float) -> None:
        """Bucht eine Wiederholungs-Wartezeit von `post_vision_request` ein. Die beiden
        Wiederholungs-Zähler leben hier und nicht im Aufrufer, weil `ThrottleStats` sie sonst
        nicht führen könnte - der Worker liest ausschließlich diesen einen Zählerstand ab."""
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
    """Die vom Anbieter angegebene Wartezeit in Sekunden - oder `None` für "keine Angabe".

    Beide vom HTTP-Standard erlaubten Formen werden gelesen: Ganzzahl-Sekunden und HTTP-Datum.
    `retry-after-ms` wird bewusst NICHT ausgewertet.

    "Nicht auswertbar" ist ausdrücklich KEIN Fehler, sondern "keine Angabe" - der Aufrufer fällt
    dann auf die verdoppelnde Staffel zurück. Das ist bei Mistral der eingeplante Normalfall, dort
    ist kein `Retry-After` dokumentiert.

    SICHERHEIT - fünf Muss-Kriterien, jedes testseitig abgedeckt:
    (a) `math.isfinite` VOR jeder Verwendung - `float("nan")`/`float("inf")` parsen erfolgreich und
        sind "keine Angabe", nicht ein großer Wert. Nachgestellt: `min(float("nan"), 60.0)` liefert
        `nan` (die Argumentreihenfolge entscheidet!), und `nan > budget` ist immer `False` - die
        Deckelung per `min(...)` ersetzt die Prüfung also NICHT, ohne sie fielen beide Zeit-Deckel
        des Aufrufers lautlos aus.
    (b) Es trägt KEINE Exception aus dem Header nach außen. Der Wert ist eine Eingabe von außen und
        unterliegt derselben Validierungspflicht wie jeder Request-Body; ein `ValueError` aus
        `parsedate_to_datetime` oder aus der `sys.set_int_max_str_digits`-Grenze ist "keine
        Angabe", kein Fehlerpfad. Deshalb hier bewusst breit `except Exception` - und ausdrücklich
        NIEMALS `BaseException`, sonst verschluckte diese Funktion ein `CancelledError`.
    (c) Rückgabe ist `> 0` oder `None`, NIE eine negative Zahl. Die Gefahr ist nicht
        `asyncio.sleep(-5)` (das kehrt sofort zurück), sondern ein negativer Summand, der das
        Restbudget des Aufrufers vergrößern würde.
    (d) Ein naives Datum ohne Zeitzone wird als UTC gelesen, nie als Ortszeit des Prozesses.
    (e) Rückgabetyp `float | None` - niemals ein durchgereichter String.

    `now` ist ausschließlich für die Tests injizierbar: ohne einen festen Bezugszeitpunkt wären die
    HTTP-Datum-Fälle nur mit einem Toleranzfenster prüfbar."""
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
        # (d): zonenlos heißt UTC. `astimezone()` läse es als ORTSZEIT des Prozesses - auf einer
        # UTC-Maschine fällt der Unterschied nicht auf, im Betrieb schon.
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
    """Die anbieterspezifischen Tatsachen EINES Cloud-Vision-Endpunkts, gebündelt - damit
    `post_vision_request` providerneutral bleiben kann und trotzdem die gewohnten Meldungstexte
    erzeugt.

    `status_label` und `unreachable_label` sind reiner Meldungstext; für sie gilt die verifizierte
    Sanierung der Fehlermeldung: kein Key, keine Bilddaten, keine Query-Parameter.

    `provider` ist der Schlüssel der Schrittmacher-Registry (cloud_vision_throttle.py) und das
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


# Die VOREINSTELLUNG der Anfragerate je Anbieter - der Wert, der ohne gesetztes
# `CLOUD_VISION_REQUESTS_PER_MINUTE` gilt.
#
# Warum HIER und nicht in cloud_vision_throttle.py, wo die Instanzen leben: `config.py` löst die
# Rate auf (`resolved_cloud_vision_requests_per_minute`) und müsste die Tabelle sonst aus
# cloud_vision_throttle.py importieren - dem Modul, das seinerseits `config.py` importiert, um die
# Instanzen zu bauen. Das wäre ein Importzyklus. Die Tabelle gehört damit in dasselbe
# konfigurationsfreie Modul wie VISION_MODELS_BY_PROVIDER daneben.
#
# BELEGPFLICHT je Voreinstellung - Quelle und Abrufdatum, Recherchestand 2026-09-10; die
# vollständige Herleitung beider Zahlen steht in ADR 0074:
#   anthropic: 60/min (1 Anfrage/s). Erstparteilich dokumentiert sind für die niedrigste
#     VERÖFFENTLICHTE Stufe ("Start") 1.000 RPM; die Voreinstellung liegt bewusst weit darunter,
#     weil dieselbe Doku neue Organisationen in einer Evaluation-Stufe "with limits below the
#     standard limits shown on this page" (Zahlen nicht veröffentlicht) startet und eine
#     Minutenrate sekundengenau durchgesetzt werden kann.
#   mistral: 40/min (1 Anfrage alle 1,5 s). NICHT ERSTPARTEILICH BELEGBAR - Mistral veröffentlicht
#     keine Zahlen mehr je Tarif und verweist ausschließlich auf das Admin-Panel des eigenen
#     Kontos; der frühere Hilfeartikel liefert seit dem Recherchestand 404. Eine begründete
#     Setzung, keine belegte Grenze - und genau der Fall, für den die Betriebsvariable existiert.
#     Die Beleglücke bleibt hier stehen, statt geglättet zu werden.
#
# Bewusst VORSICHTIG: eine zu vorsichtige Voreinstellung macht einen Lauf langsamer und ist über
# die Variable zu heben; eine zu großzügige führt genau den Zustand herbei, den der Schrittmacher
# abschafft. Der verlässliche Wert für ein konkretes Konto steht nur im Admin-Panel des
# Anbieters - `docs/setup.md` sagt, wo er nachzusehen ist.
#
# Die Tabelle deckt genau die Anbieter von `Settings.landmark_provider` ab (per Test erzwungen):
# ein neuer Anbieter ohne Eintrag wäre ein KeyError beim Prozessstart.
DEFAULT_REQUESTS_PER_MINUTE_BY_PROVIDER: dict[str, int] = {
    "anthropic": 60,
    "mistral": 40,
}


# Die Lauf-Zeitgrenze wird NICHT abgefragt, sondern durch ein hart gedeckeltes Wartebudget
# eingehalten. Der Wartevorgang sitzt im HTTP-Client und hat KEINEN Session-Zugriff -
# `last_progress_at` von hier zu schreiben verbietet sich.
#
# Modulkonstanten und ausdrücklich KEINE Settings-Felder: sie hängen nicht an einer Kontostufe des
# Betreibers, sondern an der Watchdog-Rechnung unten - und sind damit gerade keine Werte, die ohne
# Kenntnis dieser Rechnung verstellt werden sollten. Die einzige Betriebsvariable ist die RATE
# (CLOUD_VISION_REQUESTS_PER_MINUTE).
#
# Schlimmster Fall je Anfrage: 120 s Warten + 5 x 60 s (VISION_REQUEST_TIMEOUT_SECONDS) = 420 s
# gegen worker.py::STALL_THRESHOLD von 15 Minuten. Diese Rechnung ist als Invariantentest
# festgeschrieben (tests/test_cloud_vision.py) - im Produktivcode gibt es die Verbindung bewusst
# nicht, cloud_vision.py darf worker.py nicht importieren.
VISION_MAX_RATE_LIMIT_ATTEMPTS = 5  # Versuche INSGESAMT, nicht Wiederholungen
VISION_RETRY_BUDGET_SECONDS = 120.0  # summierte Wartezeit EINER Anfrage
VISION_MAX_SINGLE_WAIT_SECONDS = 60.0  # je einzelnem Wartevorgang
VISION_INITIAL_RETRY_WAIT_SECONDS = 2.0  # Startwert der verdoppelnden Staffel

# SICHERHEIT: feste Literale für die Herkunft der Wartezeit in der Logzeile - nie der rohe
# Headerwert, nur ein festes Literal.
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
    """Der EINE Sende- und Wiederholungspfad aller vier Cloud-Aufrufstellen - Verteilung über den
    Schrittmacher, Wiederholung ausschließlich bei `429`.

    Vor JEDEM Absenden (erster Versuch wie jede Wiederholung) reiht sich die Anfrage in den
    Schrittmacher ein. Antwortet der Anbieter mit `429`, wird DIESELBE Anfrage nach einer Wartezeit
    erneut gestellt: die Angabe des Anbieters (`Retry-After`) schlägt die verdoppelnde Staffel
    `2, 4, 8, 16 s`, beides gedeckelt auf `VISION_MAX_SINGLE_WAIT_SECONDS` und gemeinsam auf
    `VISION_RETRY_BUDGET_SECONDS`. Reicht das Restbudget nicht, wird SOFORT aufgegeben statt
    gekürzt gewartet - eine halbe Wartezeit führt auf denselben `429` und verbrennt eine Anfrage.

    JEDER ANDERE Fehlschlag führt ohne jede Wiederholung und mit genau einem HTTP-Versuch zum
    gewohnten best-effort-Skip: Netzwerkfehler, Zeitüberschreitung, `5xx` einschließlich
    Anthropics `529`, `401`, `403`, jeder andere `4xx`. SICHERHEIT: die Wiederholungsbedingung ist
    deshalb exakt `== 429` und ausdrücklich kein `>= 429`, kein "4xx", kein `in range(...)` - eine
    Wiederholung nach `401`/`403` sendete denselben API-Key fünfmal gegen einen Endpunkt, der ihn
    gerade abgelehnt hat; das Muster löst anbieterseitige Missbrauchserkennung aus und kann per
    Definition nicht gelingen.

    Gewartet wird AUSSCHLIESSLICH über den `sleep` des Schrittmachers, nie über ein eigenes
    `asyncio.sleep` - es gibt genau einen Zeitgeber in diesem Pfad, und er ist injizierbar.

    SICHERHEIT: Gefangen wird ausschließlich `Exception` (hier sogar nur `httpx.HTTPError`),
    NIEMALS `BaseException`, und es gibt weder ein nacktes `except:` noch ein
    `contextlib.suppress` noch ein `asyncio.shield` um den Wartevorgang. `asyncio.sleep` ist damit
    ein echter Abbruchpunkt für `JOB_TIMEOUT_SECONDS` und den Worker-Shutdown. Ein verschlucktes
    `CancelledError` machte den Job unabbrechbar: die Oberfläche sagt "fehlgeschlagen", der Lauf
    ruft weiter kostenpflichtig an.

    SICHERHEIT: `follow_redirects` wird ausdrücklich NICHT gesetzt und kein `3xx` als wiederholbar
    behandelt - sonst gingen API-Key und Bilddaten an ein vom Anbieter benanntes fremdes Ziel.
    `httpx` folgt per Voreinstellung keiner Weiterleitung.

    Nach erschöpftem Budget endet der Pfad bei `raise_for_vision_api_status`, das die übergebene,
    feature-eigene Fehlerklasse mit dem `429` im Text wirft - keine eigene Fehlerklasse, keine
    Änderung am Fehlerpfad des Workers."""
    attempt = 0
    budget_remaining = VISION_RETRY_BUDGET_SECONDS
    while True:
        attempt += 1
        await throttle.acquire()
        try:
            response = await client.post(endpoint.url, json=body)
        except httpx.HTTPError as exc:
            # SICHERHEIT: kein Einbetten von exc-Details über den httpx-eigenen Fehlertext
            # hinaus - httpx-Exceptions enthalten weder den API-Key (der lebt nur in den
            # Request-Headern) noch die Base64-Bilddaten.
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
            # Die Staffel hängt am VERSUCHSZÄHLER, nicht daran, wie oft sie bisher gegriffen
            # hat: eine einzelne Anbieterangabe dazwischen setzt sie nicht zurück - sonst könnte
            # ein Anbieter mit einer einzigen kleinen Angabe die gesamte Staffel flachhalten.
            wait = min(
                VISION_INITIAL_RETRY_WAIT_SECONDS * 2 ** (attempt - 1),
                VISION_MAX_SINGLE_WAIT_SECONDS,
            )
            source = _WAIT_SOURCE_LADDER
        if wait > budget_remaining:
            break
        budget_remaining -= wait

        # SICHERHEIT: genau EINE Zeile je Wiederholung. Erlaubt sind ausschließlich das
        # `provider`-Feld des EIGENEN Konstantenwerts, der Versuchszähler, die bereits geparste
        # und gedeckelte Wartezeit und ein festes Literal für deren Herkunft. Verboten: `body`,
        # `json=...`, das httpx.Request-Objekt, `client.headers`, `response.headers`,
        # `response.text`, `response.json()` und der ROHE Retry-After-Wert - letzterer ist die
        # einzige Log-Injection-Fläche des Features, und indem nur die geparste Zahl in die Zeile
        # geht, ist sie strukturell geschlossen statt gefiltert.
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
