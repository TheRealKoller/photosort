from __future__ import annotations

import base64
import hashlib
import logging
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

import httpx

from photosort.categories import (
    MAX_FINE_LABELS_PER_PHOTO,
    MAX_REMOTE_CATEGORIES_PER_PHOTO,
    build_classification_prompt,
    is_known_category,
)
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
from photosort.label_embedding import LabelEmbedderLike

# Strukturell analog landmark.py. Das Antwortschema ist GESCHLOSSEN: das Modell nennt bis zu drei
# KANDIDATEN aus dem festen Set (categories.py), die endgueltige Auswahl trifft der Code
# (resolve_category). Frei formulierte Feinlabels bleiben als reine Zusatzinformation erhalten.

logger = logging.getLogger(__name__)

# Das Modell kommt als Konstruktor-Parameter herein, nie aus einer Modulkonstante.

# Kurze, reine Klassifikationsantwort: eine vollbesetzte Antwort (drei Kategorie-Objekte mit
# Konfidenz plus zwei kurze deutsche Feinlabels und das JSON-Geruest) liegt ueberschlaegig bei
# 80-100 Ausgabe-Tokens; der deutlich groessere Prompt waechst ausschliesslich auf der
# EINGABEseite. 256 behaelt damit klare Reserve und ist ausdruecklich NICHT anzuheben - die Grenze
# ist keine reine Kostenschranke, sie begrenzt zugleich die Menge an Fremdtext, die je Foto
# geparst und potenziell geloggt werden kann. Beide Groessen sind in
# tests/test_remote_classification.py festgehalten.
_MAX_RESPONSE_TOKENS = 256

# Defensive Obergrenze gegen eine entartete Modellantwort - verhindert einen uebermaessig langen
# canonical_key/display_name, BEVOR resolve_canonical_label/_slugify aufgerufen wird
# (Sicherheits-Muss-Kriterium). Ein zu langes Label wird VERWORFEN, nicht gekuerzt: ein auf 60
# Zeichen abgeschnittenes Label erzeugte sonst dauerhaft einen unbrauchbaren canonical_key in der
# projektuebergreifenden Registry, und zwei verschiedene Labels koennten auf denselben Slug fallen.
# Storage-/Degenerationsgrenze, KEINE Sanitisierungsmassnahme.
MAX_FINE_LABEL_LENGTH = 60

# Laengenbegrenzung fuer den in der WARNING-Zeile mitgeloggten Rohwert (Sicherheits-Muss-Kriterium)
# - zusammen mit dem %r-Format (repr escaped Zeilenumbrueche/Steuerzeichen sichtbar) die Absicherung
# gegen Log-Injection durch eine entartete Modellantwort.
_MAX_LOGGED_RAW_VALUE_LENGTH = 60

# Sicherheits-Muss-Kriterium: FESTE Grund-Tokens statt des Rohwerts. Fuer einen verworfenen
# Kategorieschluessel traegt der Rohwert echten Diagnosewert (er zeigt ein Vokabular, das der
# Prompt nicht gesetzt hat) - fuer eine verworfene Konfidenz liegt er praktisch vollstaendig in der
# FEHLERKLASSE: "kein Zahlentyp" bzw. "ausserhalb [0,1]" sagt alles fuer eine
# Prompt-/Schemakorrektur Noetige, die konkrete `1.7` nichts darueber hinaus. Damit enthaelt die
# Zeile ueberhaupt keinen Fremdtext und die Log-Injection-Frage stellt sich nicht.
_CONFIDENCE_REASON_NOT_NUMERIC = "nicht_numerisch"
_CONFIDENCE_REASON_OUT_OF_RANGE = "ausserhalb_intervall"

# Sentinel fuer "das Antwort-Objekt nennt gar kein `confidence`-Feld" - unterscheidbar von einem
# geliefertem `null`. `None` taugt dafuer nicht: es ist selbst ein moeglicher (und dann verworfener)
# Modellwert.
_NO_CONFIDENCE = object()


class RemoteCategoryClassificationApiError(Exception):
    """Fehler beim Aufruf der Vision-API fuer die Remote-Kategorie-Klassifizierung - analog
    LandmarkApiError. Sicherheitskritisches Muss-Kriterium: Meldungen betten NIEMALS den API-Key
    oder Base64-Bilddaten ein."""


@dataclass(frozen=True)
class RemoteClassification:
    """Die validierte Antwort des Vision-LLM fuer EIN Foto.

    `categories` enthaelt ausschliesslich bekannte Set-Keys (categories.py::CATEGORY_REGISTRY) in
    Erstnennungs-Reihenfolge, hoechstens MAX_REMOTE_CATEGORIES_PER_PHOTO - unbekannte Rohwerte
    sind bereits verworfen. Ein leeres Tupel ist ein GUELTIGES Ergebnis (das Modell hat nichts
    Bekanntes genannt) und wird ueber `resolve_category` zu `nicht_erkannt`, kein Fehler.

    `fine_labels` enthaelt die zeichensanierten, freien Feinlabels, hoechstens
    MAX_FINE_LABELS_PER_PHOTO.

    `category_confidences` ist die Selbsteinschaetzung des Modells je Kandidat - eine ABBILDUNG
    `category_key -> Wert in [0, 1]`, kein positionsparalleles Array: der Wert haengt am Schluessel
    und ueberlebt jede Umsortierung. Sie ist eine TEILmenge von `categories` (Invariante
    `set(category_confidences) <= set(categories)`), darf leer sein, und ihr Fehlen an einem
    Schluessel heisst "keine Angabe", nie `0.0`. Sie beeinflusst die Kategorieauswahl an keiner
    Stelle."""

    categories: tuple[str, ...]
    fine_labels: tuple[str, ...]
    # Der reale Token-Verbrauch DIESES Aufrufs (analog LandmarkDetection.usage). `None` heisst
    # "nicht ermittelbar", nicht "keine Kosten".
    usage: TokenUsage | None = None
    # `MappingProxyType({})` statt `field(default_factory=dict)`: die Zusage von `frozen=True` gilt
    # sonst nur fuer die REFERENZ, nicht fuer den Inhalt - genau wie bei den beiden Tupel-Feldern
    # oben soll auch diese Struktur nach dem Bau unveraenderlich sein. Als Default unbedenklich,
    # weil ein `MappingProxyType` (anders als ein `{}`) gar nicht mutierbar ist und deshalb nicht
    # die klassische Falle des veraenderlichen Default-Arguments traegt.
    category_confidences: Mapping[str, float] = MappingProxyType({})


class CategoryDetectionClientLike(Protocol):
    """Schmale, injizierbare Schnittstelle (analog LandmarkClientLike).

    `photo_id` ist eine technische Detailentscheidung dieser Umsetzung (die WARNING-Zeile traegt
    den einzelnen verworfenen Wert PLUS photo_id): der Parser sitzt innerhalb von `classify`, kennt
    das Foto sonst aber nicht. Der Wert wird ausschliesslich fuer diese Logzeile benutzt, nie an
    die API gesendet."""

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification: ...


def _log_discarded_category(photo_id: int, raw: object) -> None:
    """Ein verworfener, unbekannter Kategoriewert (eine Zeile, WARNING, kein exc_info/Traceback -
    der Lauf bleibt erfolgreich, das ist erwartetes Best-effort-Verhalten).

    Security-Muss-Kriterien: geloggt wird AUSSCHLIESSLICH der einzelne verworfene Wert plus
    photo_id - nie die vollstaendige API-Antwort, nie der Request-Body, nie Base64-Bilddaten, nie
    der API-Key. Der Rohwert geht laengenbegrenzt und ueber %r (repr) ins Log, nie roh ueber %s:
    ein mehrzeiliger Modellwert koennte sonst gefaelschte Logzeilen erzeugen. Kein Log-Flooding
    moeglich - pro Foto koennen hoechstens so viele Werte verworfen werden, wie die Antwortliste
    Eintraege hat."""
    text = raw if isinstance(raw, str) else repr(raw)
    if len(text) > _MAX_LOGGED_RAW_VALUE_LENGTH:
        text = text[:_MAX_LOGGED_RAW_VALUE_LENGTH] + "..."
    logger.warning(
        "remote_category: unbekannter Kategoriewert verworfen photo_id=%s wert=%r", photo_id, text
    )


def _log_discarded_confidence(photo_id: int, reason: str) -> None:
    """Schwesterfunktion zu `_log_discarded_category` fuer einen verworfenen KONFIDENZwert
    (Sicherheits-Muss-Kriterium) - eine Zeile, WARNING, kein exc_info: der Lauf bleibt
    erfolgreich, das Foto behaelt seine Kategorie.

    Geloggt werden ausschliesslich `photo_id` und eines der beiden festen Grund-Tokens, NIE der
    Rohwert, nie die vollstaendige Antwort, nie der Kategorie-Key, nie Bilddaten. Kein
    Log-Flooding moeglich: je Foto koennen hoechstens so viele Werte verworfen werden, wie die
    Antwortliste Eintraege hat (und die ist ueber `_MAX_RESPONSE_TOKENS` begrenzt)."""
    logger.warning(
        "remote_category: Konfidenzwert verworfen photo_id=%s grund=%s", photo_id, reason
    )


def _confidence_from_raw(raw: object, photo_id: int) -> float | None:
    """Die Selbsteinschaetzung des Modells zu EINEM Kandidaten - `None` heisst "keine brauchbare
    Zahl".

    Uebernommen wird ausschliesslich ein echter Zahlentyp im Band `0.0 <= v <= 1.0`. Drei
    Feinheiten, jede mit einer konkreten Ausfallfolge:

    - `isinstance(raw, bool)` wird EXPLIZIT ausgeschlossen, bevor auf `int` geprueft wird:
      `isinstance(True, int)` ist `True`, `"confidence": true` erschiene sonst als "100 % sicher" -
      die staerkste Aussage, die das Produkt kennt, erfunden aus einem Nicht-Wert.
    - Die Bereichspruefung ist als Vergleich geschrieben, damit `NaN`/`±Infinity` DURCHFALLEN
      (`0.0 <= nan <= 1.0` ist `False`). Pythons `json` parst beide Literale standardmaessig, und
      beide Provider-Pfade nutzen `json.loads` mit Standardeinstellungen. Ein durchgelassenes
      `NaN` liesse ueber Starlettes `allow_nan=False` die GESAMTE Listenantwort mit `ValueError`
      scheitern (nicht nur den einen Eintrag), und PostgreSQL lehnt dasselbe Literal bereits beim
      Schreiben der JSON-Spalte ab - verfuegbarkeitswirksam, nicht nur unsauber.
    - VERWORFEN, nicht geklemmt - bewusst anders als `landmark.py::_landmark_detection_from_json`.
      `1.4 -> 1.0` waere eine Aussage, die das Modell nie getroffen hat; und ein spaeteres Klemmen
      (`if v > 1.0: v = 1.0`) liesse `NaN` wieder durch, weil der Vergleich `False` ergibt.
    """
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        _log_discarded_confidence(photo_id, _CONFIDENCE_REASON_NOT_NUMERIC)
        return None
    value = float(raw)
    if not 0.0 <= value <= 1.0:
        _log_discarded_confidence(photo_id, _CONFIDENCE_REASON_OUT_OF_RANGE)
        return None
    return value


def _categories_from_json(
    raw_categories: list[Any], photo_id: int
) -> tuple[tuple[str, ...], Mapping[str, float]]:
    """Verbindliche Verarbeitungsreihenfolge: trimmen -> leere Werte verwerfen -> unbekannte Werte
    verwerfen (+ genau ein WARNING je Wert) -> deduplizieren unter Erhalt der
    Erstnennungs-Reihenfolge -> ZULETZT kuerzen. Zuerst zu kuerzen wuerde gueltige Werte hinter
    ungueltigen verlieren.

    Der EINE Durchlauf liefert ein PAAR (Kandidaten + Konfidenz-Abbildung) statt nur der
    Kandidaten, und nie zwei getrennte Funktionen: Dedup und Kappung koennten sonst zwischen beiden
    Rueckgaben auseinanderlaufen.

    Ein Eintrag darf ein Objekt mit `key` (optional `confidence`) ODER ein blanker String sein -
    der String-Fall liefert eine Kategorie OHNE Zahl. Alles andere geht durch denselben
    Verwerfen-Pfad, kein stiller Zweig daneben.

    Security-Muss-Kriterium: die Konfidenz-Abbildung wird ERST NACH Schluesselvalidierung, Dedup
    und Kappung auf die verbliebenen Schluessel gefiltert. Ihre Schluessel sind ein zweiter
    Persistenzkanal - entstuende sie vor oder unabhaengig von der Validierung, wanderte
    unvalidierter Fremdtext ueber sie in API-Antwort und UI. Invariante:
    `set(confidences) <= set(categories)`."""
    accepted: list[str] = []
    confidences: dict[str, float] = {}
    for raw in raw_categories:
        if isinstance(raw, str):
            raw_key: object = raw
            raw_confidence: object = _NO_CONFIDENCE
        elif isinstance(raw, dict):
            raw_key = raw.get("key")
            # `_NO_CONFIDENCE` statt `None`: ein FEHLENDER Schluessel ist der erwartete Regelfall
            # (das Modell kann sich nicht einschaetzen) und wird still hingenommen, ein explizites
            # `"confidence": null` ist dagegen ein gelieferter, unbrauchbarer Wert und wird wie
            # jeder andere verworfene Wert einmal protokolliert.
            raw_confidence = raw.get("confidence", _NO_CONFIDENCE)
        else:
            _log_discarded_category(photo_id, raw)
            continue

        if not isinstance(raw_key, str):
            # Nur der KEY-Anteil ins Log, nie der ganze Eintrag: der Konfidenzwert gehoert nicht
            # in eine Logzeile.
            _log_discarded_category(photo_id, raw_key)
            continue
        trimmed = raw_key.strip()
        if not trimmed or not is_known_category(trimmed):
            _log_discarded_category(photo_id, raw_key)
            continue
        if trimmed in accepted:
            # Erstnennung gewinnt - fuer den Schluessel UND fuer die Zahl. Die Konfidenz der
            # Zweitnennung wird gar nicht erst bewertet (also auch nicht protokolliert): der
            # Eintrag als Ganzes ist bereits verworfen.
            continue
        accepted.append(trimmed)
        if raw_confidence is not _NO_CONFIDENCE:
            confidence = _confidence_from_raw(raw_confidence, photo_id)
            if confidence is not None:
                confidences[trimmed] = confidence

    categories = tuple(accepted[:MAX_REMOTE_CATEGORIES_PER_PHOTO])
    return categories, MappingProxyType(
        {key: confidences[key] for key in categories if key in confidences}
    )


def _fine_labels_from_json(raw_labels: list[Any]) -> tuple[str, ...]:
    """Dieselbe Reihenfolge wie `_categories_from_json`, aber mit Zeichensanitisierung statt einer
    Set-Whitelist: sanitisieren -> leere/zu lange Werte verwerfen -> deduplizieren (Erstnennung
    gewinnt) -> ZULETZT kuerzen. Verworfene Feinlabels werden NICHT geloggt: anders als bei einem
    unbekannten Kategoriewert (der auf ein Prompt-/Set-Problem hindeutet) ist ein leeres oder
    entartetes Feinlabel ohne Diagnosewert, und der Wert selbst waere genau der Fremdtext, der aus
    dem Log herauszuhalten ist."""
    accepted: list[str] = []
    for raw in raw_labels:
        if not isinstance(raw, str):
            continue
        sanitized = _sanitize_label_text(raw)
        if not sanitized or len(sanitized) > MAX_FINE_LABEL_LENGTH:
            continue
        if sanitized in accepted:
            continue
        accepted.append(sanitized)
    return tuple(accepted[:MAX_FINE_LABELS_PER_PHOTO])


def _classification_from_json(
    parsed: Any, photo_id: int, usage: TokenUsage | None = None
) -> RemoteClassification:
    """Providerneutrale Validierung der Roh-Antwort - **strukturell hart, inhaltlich tolerant**:

    STRUKTURELL HART (jeweils RemoteCategoryClassificationApiError, das Foto wird auf Worker-Ebene
    best-effort uebersprungen): die Antwort ist kein JSON-Objekt, `categories` fehlt, `categories`
    ist keine Liste, oder `fine_labels` ist vorhanden aber keine Liste. Eine durch
    _MAX_RESPONSE_TOKENS abgeschnittene Antwort landet ueber denselben Pfad hier - nie bei einem
    teilweise geparsten Datensatz.

    INHALTLICH TOLERANT: unbekannte Kategoriewerte und entartete Feinlabels werden VERWORFEN statt
    abgelehnt. Der wichtigste Grenzfall: sind ALLE Kategoriewerte
    unbekannt, ist das KEIN Fehler - das Ergebnis ist ein leeres Kategorien-Tupel, das ueber
    `resolve_category` zu `nicht_erkannt` wird, und die Feinlabels desselben Fotos bleiben
    erhalten. `fine_labels` ist optional (fehlender Schluessel -> leeres Tupel), `categories`
    nicht."""
    if not isinstance(parsed, dict):
        raise RemoteCategoryClassificationApiError(
            "Unerwartete Antwortstruktur der Vision-API-Antwort (kein JSON-Objekt)."
        )

    try:
        raw_categories = parsed["categories"]
    except KeyError as exc:
        raise RemoteCategoryClassificationApiError(
            "Unerwartete Antwortstruktur der Vision-API-Antwort (fehlendes 'categories'-Feld)."
        ) from exc
    if not isinstance(raw_categories, list):
        raise RemoteCategoryClassificationApiError(
            "Unerwartete Antwortstruktur der Vision-API-Antwort ('categories' ist keine Liste)."
        )

    raw_fine_labels = parsed.get("fine_labels", [])
    if not isinstance(raw_fine_labels, list):
        raise RemoteCategoryClassificationApiError(
            "Unerwartete Antwortstruktur der Vision-API-Antwort ('fine_labels' ist keine Liste)."
        )

    categories, category_confidences = _categories_from_json(raw_categories, photo_id)
    return RemoteClassification(
        categories=categories,
        fine_labels=_fine_labels_from_json(raw_fine_labels),
        usage=usage,
        category_confidences=category_confidences,
    )


class AnthropicCategoryClient:
    """Echte, httpx-basierte Implementierung von CategoryDetectionClientLike, strukturell analog
    AnthropicLandmarkClient. `transport` ist injizierbar (httpx.MockTransport in Tests) -
    `build_category_classification_client()` unten laeuft NIE in einem automatisierten Test (echtes
    Secret + echter Netzwerkversuch)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = VISION_REQUEST_TIMEOUT_SECONDS,
        *,
        throttle: CloudRequestThrottle,
    ) -> None:
        # PFLICHTPARAMETER ohne Default, Begruendung wortgleich zu
        # landmark.py::AnthropicLandmarkClient. Dasselbe gilt fuer den Schrittmacher: ein Aufrufer,
        # der ihn vergisst, fiele nicht beim Typecheck auf, sondern erst an der Anfragerate des
        # Anbieters.
        self._model = model
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

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
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
                        {"type": "text", "text": build_classification_prompt()},
                    ],
                }
            ],
        }
        # Derselbe Sende- und Wiederholungspfad, den auch die beiden Landmark-Clients benutzen.
        # Meldungstexte und Statuslabel stecken in ANTHROPIC_ENDPOINT.
        response = await post_vision_request(
            self._client,
            ANTHROPIC_ENDPOINT,
            body,
            error_class=RemoteCategoryClassificationApiError,
            throttle=self._throttle,
        )
        payload = response.json()
        parsed = anthropic_response_to_json(payload, RemoteCategoryClassificationApiError)
        return _classification_from_json(
            parsed, photo_id, anthropic_usage_from_response(payload, self._model)
        )


class MistralCategoryClient:
    """Echte, httpx-basierte Implementierung von CategoryDetectionClientLike, exakt analog
    MistralLandmarkClient."""

    def __init__(
        self,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = VISION_REQUEST_TIMEOUT_SECONDS,
        *,
        throttle: CloudRequestThrottle,
    ) -> None:
        self._model = model
        self._throttle = throttle
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json",
            },
            transport=transport,
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
        body = {
            "model": self._model,
            "max_tokens": _MAX_RESPONSE_TOKENS,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": (
                                f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode()}"
                            ),
                        },
                        {"type": "text", "text": build_classification_prompt()},
                    ],
                }
            ],
        }
        # Begruendung wortgleich zu AnthropicCategoryClient.classify oben.
        response = await post_vision_request(
            self._client,
            MISTRAL_ENDPOINT,
            body,
            error_class=RemoteCategoryClassificationApiError,
            throttle=self._throttle,
        )
        payload = response.json()
        parsed = mistral_response_to_json(payload, RemoteCategoryClassificationApiError)
        return _classification_from_json(
            parsed, photo_id, mistral_usage_from_response(payload, self._model)
        )


def build_category_classification_client(model: str) -> CategoryDetectionClientLike:
    """Dispatch-Factory zwischen AnthropicCategoryClient (Default) und MistralCategoryClient je
    nach settings.landmark_provider (KEIN eigenes Provider-Setting - derselbe Schalter wie fuer
    landmark). Laeuft NIE in einem automatisierten Test (echtes Secret + echter Netzwerkversuch),
    analog build_landmark_client/build_face_detector.

    `model` ist ein Parameter (Begruendung wortgleich zu landmark.py::build_landmark_client) - und
    es ist DASSELBE Modell wie dort, weil `LANDMARK_MODEL` wie `LANDMARK_PROVIDER` fuer beide
    Cloud-Anteile gilt: nie zwei unterschiedliche Modelle nebeneinander."""
    # DERSELBE prozessweite Schrittmacher, den auch build_landmark_client() zieht - beide
    # Cloud-Teilschritte teilen sich einen je Anbieter.
    throttle = throttle_for_provider(settings.landmark_provider)
    if settings.landmark_provider == "mistral":
        mistral_client: CategoryDetectionClientLike = MistralCategoryClient(
            api_key=settings.mistral_api_key, model=model, throttle=throttle
        )
        return mistral_client
    anthropic_client: CategoryDetectionClientLike = AnthropicCategoryClient(
        api_key=settings.anthropic_api_key, model=model, throttle=throttle
    )
    return anthropic_client


# Dokumentiert-unkalibrierter Startwert - gleiche Klasse wie
# CATEGORY_ACTIVE_THRESHOLD_FRACTION/SHARPNESS_NORMALIZATION_CEILING: es gibt keinen Foto- oder
# Label-Korpus im Repository, gegen den er kalibriert werden koennte.
CATEGORY_LABEL_SIMILARITY_THRESHOLD = 0.78


@dataclass
class FineLabelSnapshotEntry:
    """Ein Eintrag des In-Memory-Snapshots der `fine_labels`-Tabelle -
    worker.py::run_remote_category_classification laedt diesen Snapshot einmal zu Laufbeginn und
    reicht ihn (mutierbar) an resolve_canonical_label weiter; neu angelegte Eintraege werden sofort
    lokal ergaenzt (kein erneutes SELECT, keine Nebenlaeufigkeits-Race). Bewusst NICHT frozen
    (anders als RemoteClassification) - worker.py setzt nach dem DB-Insert die echte `id` auf
    genau dieser Instanz nach."""

    canonical_key: str
    display_name: str
    embedding: list[float]
    id: int | None = None


def _normalize_label_text(raw: str) -> str:
    """Reine String-Normalisierung (Schritt 1) - kein Modell-Aufruf. NFKC deckt u.a.
    Ligaturen/Kompatibilitaetszeichen ab (z.B. "ﬁsch" -> "fisch"), casefold ist eine aggressivere,
    unicode-bewusste Kleinschreibung als .lower()."""
    return unicodedata.normalize("NFKC", raw).strip().casefold()


_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    """Bildet einen URL-/Key-sicheren Slug (Schritt 4): casefoldet defensiv zusaetzlich selbst
    (funktioniert damit unabhaengig davon, ob der Aufrufer bereits normalisiert hat),
    Sonderzeichen/Leerzeichen zu `_`, doppelte `_` reduziert, fuehrende/abschliessende `_`
    entfernt - eine reine Textfunktion, keine neue Bibliothek.

    Hash-Fallback: `_SLUG_INVALID_CHARS` matcht nur a-z/0-9 als gueltig - ein rein
    nicht-lateinisches Rohlabel (z.B. japanisch/chinesisch, ein vom offenen Remote-Vokabular
    explizit nicht ausgeschlossener Fall) wuerde sonst zu einem leeren String slugifien. Zwei
    verschiedene solche Label wuerden dann denselben (leeren) canonical_key produzieren und an
    UniqueConstraint(fine_labels.canonical_key) scheitern - ein Verfuegbarkeitsrisiko, das den
    ganzen Batch-Lauf abbricht statt nur das eine betroffene Foto zu ueberspringen (best-effort
    ohne Retry gilt pro Foto, nicht fuer eine IntegrityError beim Label-Anlegen).
    Deterministischer SHA256-Praefix, nie ein Zufallswert - derselbe Rohtext liefert bei einem
    Wiederholungslauf denselben Slug, kein Duplikat-Risiko."""
    slug = _SLUG_INVALID_CHARS.sub("_", text.casefold()).strip("_")
    if slug:
        return slug
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"label_{digest}"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Reine Vektor-Aehnlichkeitsfunktion (Schritt 3) - beide Embedding-Vektoren sind bereits
    L2-normiert (label_embedding.py::_mean_pool_and_normalize), das Skalarprodukt entspricht
    deshalb direkt der Kosinus-Aehnlichkeit, keine erneute Normierung noetig."""
    return sum(x * y for x, y in zip(a, b, strict=True))


def resolve_canonical_label(
    raw_label: str,
    existing_labels: list[FineLabelSnapshotEntry],
    embedder: LabelEmbedderLike,
) -> FineLabelSnapshotEntry:
    """Reine, DB-freie Funktion - loest ein einzelnes Roh-Label auf einen kanonischen Eintrag auf:
    (1) exakter Normalisierungs-Fast-Path (KEIN embed()-Aufruf), (2) Kosinus-Aehnlichkeits-Fallback
    gegen ALLE `existing_labels` (`>=` CATEGORY_LABEL_SIMILARITY_THRESHOLD, inklusiv), (3) sonst
    ein neuer kanonischer Eintrag, der `existing_labels` sofort (in-place) ergaenzt - verhindert
    Duplikat-Anlage bei zwei sehr aehnlichen neuen Labeln innerhalb desselben Laufs."""
    normalized = _normalize_label_text(raw_label)

    for entry in existing_labels:
        if _normalize_label_text(entry.display_name) == normalized:
            return entry

    vector = embedder.embed(normalized)

    best_entry: FineLabelSnapshotEntry | None = None
    best_similarity = -1.0
    for entry in existing_labels:
        similarity = _cosine_similarity(vector, entry.embedding)
        if similarity > best_similarity:
            best_similarity = similarity
            best_entry = entry

    if best_entry is not None and best_similarity >= CATEGORY_LABEL_SIMILARITY_THRESHOLD:
        return best_entry

    new_entry = FineLabelSnapshotEntry(
        canonical_key=_slugify(normalized),
        display_name=raw_label,
        embedding=vector,
    )
    existing_labels.append(new_entry)
    return new_entry
