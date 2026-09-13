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

from photosort.classification_prompt import build_classification_prompt
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
from photosort.motifs import MOTIF_REGISTRY, is_motif_key

# Strukturell analog landmark.py. Das Antwortschema ist GESCHLOSSEN: das Modell nennt fuer JEDEN
# der acht Motivschluessel (motifs.py::MOTIF_REGISTRY) eine Staerke in [0, 1] plus einen
# Wahrheitswert fuer den Dokument-/Screenshot-Ausschluss. Es waehlt kein Motiv aus und ordnet
# keines - es gibt keine Kandidatenliste und keine Vorrangreihenfolge mehr. Frei formulierte
# Feinlabels bleiben als reine Zusatzinformation erhalten.

logger = logging.getLogger(__name__)

# Obergrenze der Feinlabels je Foto - hier, weil dieses Modul der einzige Leser ist: es schreibt
# den Wert ueber `build_classification_prompt(max_fine_labels=...)` in den Prompt UND kuerzt die
# geparste Antwort gegen dieselbe Konstante, Prompt und Validierung koennen damit nicht
# auseinanderlaufen.
#
# Bewusst NICHT in `motifs.py`: Feinlabels sind kein Motiv. Der Prompt-Bau nimmt den Wert deshalb
# als Parameter entgegen, statt ihn zu importieren - das Motivregister soll nichts ueber die
# Antwortform des Anbieters wissen.
MAX_FINE_LABELS_PER_PHOTO = 2

# Das Modell kommt als Konstruktor-Parameter herein, nie aus einer Modulkonstante.

# Kurze, reine Klassifikationsantwort: eine vollbesetzte Antwort (acht Schluessel-Zahl-Paare plus
# das Ausschluss-Feld, zwei kurze deutsche Feinlabels und das JSON-Geruest) liegt bei rund 257
# Zeichen und damit ueberschlaegig bei 110 Ausgabe-Tokens kompakt bzw. 145 bei einer
# eingerueckten Antwort; der deutlich groessere Prompt waechst ausschliesslich auf der
# EINGABEseite. 384 behaelt damit klare Reserve - die Grenze ist keine reine Kostenschranke, sie
# begrenzt zugleich die Menge an Fremdtext, die je Foto geparst und potenziell geloggt werden
# kann. Beim Anheben gehoeren drei Dinge zusammen nachgezogen: dieser Kommentar, der Waechtertest
# in tests/test_remote_classification.py und
# pricing.py::ASSUMED_USAGE_BY_PROVIDER.output_tokens, das gegen die vollbesetzte Antwort neu
# herzuleiten ist. Die Reserve-Invariante `Schranke >= 2 x Annahme` ist dabei einzuhalten, nicht
# der Annahme anzupassen.
_MAX_RESPONSE_TOKENS = 384

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

# Sicherheitsauflage S11: FESTE Grund-Tokens statt des Rohwerts. Fuer einen verworfenen
# MOTIVSCHLUESSEL traegt der Rohwert echten Diagnosewert (er zeigt ein Vokabular, das der Prompt
# nicht gesetzt hat) - fuer eine verworfene Staerke und fuer ein verworfenes `excluded` liegt er
# praktisch vollstaendig in der FEHLERKLASSE: "kein Zahlentyp" bzw. "ausserhalb [0,1]" bzw. "kein
# Wahrheitswert" sagt alles fuer eine Prompt-/Schemakorrektur Noetige, die konkrete `1.7` nichts
# darueber hinaus. Damit enthaelt die Zeile ueberhaupt keinen Fremdtext und die
# Log-Injection-Frage stellt sich nicht.
_STRENGTH_REASON_NOT_NUMERIC = "nicht_numerisch"
_STRENGTH_REASON_OUT_OF_RANGE = "ausserhalb_intervall"
_EXCLUDED_REASON_NOT_BOOL = "kein_wahrheitswert"

# Sentinel fuer "das Antwort-Objekt nennt gar kein `excluded`-Feld" - unterscheidbar von einem
# gelieferten `null`. `None` taugt dafuer nicht: es ist selbst ein moeglicher (und dann
# verworfener) Modellwert. Ein FEHLENDES Feld wird still zu `false`, ein geliefertes, aber
# unbrauchbares einmal protokolliert.
_NO_VALUE = object()


class RemoteCategoryClassificationApiError(Exception):
    """Fehler beim Aufruf der Vision-API fuer die Remote-Kategorie-Klassifizierung - analog
    LandmarkApiError. Sicherheitskritisches Muss-Kriterium: Meldungen betten NIEMALS den API-Key
    oder Base64-Bilddaten ein."""


@dataclass(frozen=True)
class RemoteClassification:
    """Die validierte Antwort des Vision-LLM fuer EIN Foto.

    `motif_strengths` ist der STAERKEVEKTOR: eine Abbildung `motif_key -> Wert in [0, 1]` mit
    GENAU den acht Schluesseln von `motifs.py::MOTIF_REGISTRY`, in Registry-Reihenfolge. Der
    Vektor ist vollstaendig oder er existiert nicht - ein Motiv, das die Antwort nicht nennt oder
    fuer das sie keine brauchbare Zahl liefert, steht mit `0.0` darin. Acht Nullen sind ein
    GUELTIGES Ergebnis ("nichts deutlich erkannt") und kein Fehler; sie unterscheiden sich vom
    Zustand "noch nicht klassifiziert" dadurch, dass dieser gar keine Kopfzeile hat.

    Kein positionsparalleles Array: der Wert haengt am Schluessel und ueberlebt jede Umsortierung.
    Unbekannte Rohschluessel sind bereits verworfen - hier landet kein unvalidierter Fremdtext,
    denn die Schluessel sind ein zweiter Persistenzkanal in API-Antwort und UI.

    `excluded` ist die Antwort des Modells auf die Frage, ob das Foto eine Dokument-, Text- oder
    Bildschirmabbildung ist. Nur ein echter `bool` wird uebernommen, sonst `False`. Der Ausschluss
    nimmt ein Foto aus JEDER Motivauswahl und ist von Hand nicht korrigierbar; die Staerken
    bleiben daneben unveraendert gespeichert.

    `fine_labels` enthaelt die zeichensanierten, freien Feinlabels, hoechstens
    MAX_FINE_LABELS_PER_PHOTO - der einzige verbliebene Fremdtext-Kanal dieser Antwort."""

    # `Mapping` statt `dict` als Annotation UND `MappingProxyType` als das, was der Parser
    # hineingibt: die Zusage von `frozen=True` gilt sonst nur fuer die REFERENZ, nicht fuer den
    # Inhalt - genau wie beim Tupel-Feld darunter soll auch diese Struktur nach dem Bau
    # unveraenderlich sein. Die Annotation allein deckt nur den Typecheck; den Laufzeitschutz
    # liefert `_motif_strengths_from_json`.
    motif_strengths: Mapping[str, float]
    fine_labels: tuple[str, ...]
    excluded: bool = False
    # Der reale Token-Verbrauch DIESES Aufrufs (analog LandmarkDetection.usage). `None` heisst
    # "nicht ermittelbar", nicht "keine Kosten".
    usage: TokenUsage | None = None


class CategoryDetectionClientLike(Protocol):
    """Schmale, injizierbare Schnittstelle (analog LandmarkClientLike).

    `photo_id` ist eine technische Detailentscheidung dieser Umsetzung (die WARNING-Zeile traegt
    den einzelnen verworfenen Wert PLUS photo_id): der Parser sitzt innerhalb von `classify`, kennt
    das Foto sonst aber nicht. Der Wert wird ausschliesslich fuer diese Logzeile benutzt, nie an
    die API gesendet."""

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification: ...


def _log_discarded_motif_key(photo_id: int, raw: object) -> None:
    """Ein verworfener, unbekannter Motivschluessel (eine Zeile, WARNING, kein exc_info/Traceback -
    der Lauf bleibt erfolgreich, das ist erwartetes Best-effort-Verhalten).

    Security-Muss-Kriterien: geloggt wird AUSSCHLIESSLICH der einzelne verworfene Wert plus
    photo_id - nie die vollstaendige API-Antwort, nie der Request-Body, nie Base64-Bilddaten, nie
    der API-Key. Der Rohwert geht laengenbegrenzt und ueber %r (repr) ins Log, nie roh ueber %s:
    ein mehrzeiliger Modellwert koennte sonst gefaelschte Logzeilen erzeugen. Kein Log-Flooding
    moeglich - pro Foto koennen hoechstens so viele Werte verworfen werden, wie die Antwort
    Eintraege hat (und die ist ueber `_MAX_RESPONSE_TOKENS` begrenzt)."""
    text = raw if isinstance(raw, str) else repr(raw)
    if len(text) > _MAX_LOGGED_RAW_VALUE_LENGTH:
        text = text[:_MAX_LOGGED_RAW_VALUE_LENGTH] + "..."
    logger.warning(
        "remote_category: unbekannter Motivschluessel verworfen photo_id=%s wert=%r",
        photo_id,
        text,
    )


def _log_discarded_strength(photo_id: int, reason: str) -> None:
    """Schwesterfunktion zu `_log_discarded_motif_key` fuer eine verworfene STAERKE
    (Sicherheitsauflage S11) - eine Zeile, WARNING, kein exc_info: der Lauf bleibt erfolgreich,
    das Motiv steht mit `0.0` im Vektor.

    Geloggt werden ausschliesslich `photo_id` und eines der beiden festen Grund-Tokens, NIE der
    Rohwert, nie die vollstaendige Antwort, nie der Motivschluessel, nie Bilddaten."""
    logger.warning("remote_category: Motivstaerke verworfen photo_id=%s grund=%s", photo_id, reason)


def _log_discarded_exclusion(photo_id: int) -> None:
    """Dieselbe Form fuer ein geliefertes, aber nicht als Wahrheitswert brauchbares `excluded`
    (Sicherheitsauflage S11). Ein FEHLENDES Feld ist keine entartete Aussage und wird nicht
    protokolliert."""
    logger.warning(
        "remote_category: Ausschluss-Angabe verworfen photo_id=%s grund=%s",
        photo_id,
        _EXCLUDED_REASON_NOT_BOOL,
    )


def _strength_from_raw(raw: object, photo_id: int) -> float | None:
    """Die Staerke EINES Motivs - `None` heisst "keine brauchbare Zahl", der Aufrufer setzt dann
    `0.0`.

    Uebernommen wird ausschliesslich ein echter Zahlentyp im Band `0.0 <= v <= 1.0`
    (Sicherheitsauflage S9). Drei Feinheiten, jede mit einer konkreten Ausfallfolge:

    - `isinstance(raw, bool)` wird EXPLIZIT ausgeschlossen, bevor auf `int` geprueft wird:
      `isinstance(True, int)` ist `True`, `"menschen": true` erschiene sonst als die staerkste
      Aussage, die das Produkt kennt, erfunden aus einem Nicht-Wert.
    - Die Bereichspruefung ist als Vergleich geschrieben, damit `NaN`/`±Infinity` DURCHFALLEN
      (`0.0 <= nan <= 1.0` ist `False`). Pythons `json` parst beide Literale standardmaessig, und
      beide Provider-Pfade nutzen `json.loads` mit Standardeinstellungen. Ein durchgelassenes
      `NaN` legte die GESAMTE Fotoliste des Projekts auf `500`: `strength` ist eine
      `double precision`-Spalte (PostgreSQL nimmt `NaN` an) und Starlette rendert mit
      `allow_nan=False`. Die Pruefung gehoert deshalb HIER an den Parser, nicht an die
      Datenbankschicht.
    - VERWORFEN, nicht geklemmt - bewusst anders als `landmark.py::_landmark_detection_from_json`.
      `1.4 -> 1.0` waere eine Aussage, die das Modell nie getroffen hat; und ein spaeteres Klemmen
      (`if v > 1.0: v = 1.0`) liesse `NaN` wieder durch, weil der Vergleich `False` ergibt.
    """
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        _log_discarded_strength(photo_id, _STRENGTH_REASON_NOT_NUMERIC)
        return None
    value = float(raw)
    if not 0.0 <= value <= 1.0:
        _log_discarded_strength(photo_id, _STRENGTH_REASON_OUT_OF_RANGE)
        return None
    return value


def _motif_strengths_from_json(raw_motifs: dict[Any, Any], photo_id: int) -> Mapping[str, float]:
    """Der vollstaendige Achter-Vektor aus der Roh-Abbildung der Antwort.

    Verbindliche Verarbeitungsreihenfolge: unbekannten Schluessel verwerfen (+ genau ein WARNING,
    die Zahl wird dann gar nicht erst bewertet) -> Zahl pruefen (+ genau ein WARNING je verworfener
    Zahl) -> ZULETZT den Vektor in Registry-Reihenfolge aufbauen und nicht genannte Motive mit
    `0.0` fuellen.

    Der Aufbau laeuft ueber `MOTIF_REGISTRY`, nicht ueber die Schluessel der Antwort: das ist die
    Stelle, an der die Reihenfolge des Vektors vom Modell UNABHAENGIG wird und an der unmoeglich
    ein unvalidierter Fremdschluessel in die Ausgabe geraet. Die Schluessel sind ein zweiter
    Persistenzkanal in API-Antwort und UI (Sicherheitsauflage S8/S9).

    Kein Trimmen und keine Normalisierung des Eingabeschluessels - `is_motif_key` ist eine reine
    Mitgliedschaftspruefung im geschlossenen Achter-Schluesselraum, und `EXCLUSION_KEY` ist
    ausdruecklich kein gueltiger Wert."""
    accepted: dict[str, float] = {}
    for raw_key, raw_value in raw_motifs.items():
        if not isinstance(raw_key, str) or not is_motif_key(raw_key):
            _log_discarded_motif_key(photo_id, raw_key)
            continue
        strength = _strength_from_raw(raw_value, photo_id)
        if strength is None:
            continue
        accepted[raw_key] = strength
    return MappingProxyType({key: accepted.get(key, 0.0) for key in MOTIF_REGISTRY})


def _excluded_from_json(raw: object, photo_id: int) -> bool:
    """Der Ausschluss-Wahrheitswert (Sicherheitsauflage S10).

    Uebernommen wird NUR ein echter `bool`, sonst `False`. Kein `bool(...)` auf einen Fremdwert
    und keine Umdeutung von `1`, `"true"` oder `"ja"` - jeder nicht-leere Fremdwert fuehrte sonst
    zum Ausschluss. Das ist die Stelle mit dem groessten Hebel dieses Parsers: ein einziger Wert
    nimmt ein Foto aus JEDER Motivauswahl, und von Hand korrigierbar ist das nicht - der Rueckweg
    ist allein ein erneuter, kostenpflichtiger Lauf."""
    if raw is _NO_VALUE:
        return False
    if isinstance(raw, bool):
        return raw
    _log_discarded_exclusion(photo_id)
    return False


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
    best-effort uebersprungen): die Antwort ist kein JSON-Objekt, `motifs` fehlt, `motifs` ist
    kein JSON-Objekt, oder `fine_labels` ist vorhanden aber keine Liste. Eine durch
    _MAX_RESPONSE_TOKENS abgeschnittene Antwort landet ueber denselben Pfad hier - nie bei einem
    teilweise geparsten Datensatz.

    INHALTLICH TOLERANT: unbekannte Motivschluessel, unbrauchbare Zahlen, ein unbrauchbares
    `excluded` und entartete Feinlabels werden VERWORFEN statt abgelehnt. Der wichtigste
    Grenzfall: sind ALLE Schluessel unbekannt, ist das KEIN Fehler - das Ergebnis ist der
    Achter-Vektor mit acht Nullen, und die Feinlabels desselben Fotos bleiben erhalten.
    `fine_labels` und `excluded` sind optional, `motifs` nicht."""
    if not isinstance(parsed, dict):
        raise RemoteCategoryClassificationApiError(
            "Unerwartete Antwortstruktur der Vision-API-Antwort (kein JSON-Objekt)."
        )

    try:
        raw_motifs = parsed["motifs"]
    except KeyError as exc:
        raise RemoteCategoryClassificationApiError(
            "Unerwartete Antwortstruktur der Vision-API-Antwort (fehlendes 'motifs'-Feld)."
        ) from exc
    if not isinstance(raw_motifs, dict):
        raise RemoteCategoryClassificationApiError(
            "Unerwartete Antwortstruktur der Vision-API-Antwort ('motifs' ist kein Objekt)."
        )

    raw_fine_labels = parsed.get("fine_labels", [])
    if not isinstance(raw_fine_labels, list):
        raise RemoteCategoryClassificationApiError(
            "Unerwartete Antwortstruktur der Vision-API-Antwort ('fine_labels' ist keine Liste)."
        )

    return RemoteClassification(
        motif_strengths=_motif_strengths_from_json(raw_motifs, photo_id),
        fine_labels=_fine_labels_from_json(raw_fine_labels),
        excluded=_excluded_from_json(parsed.get("excluded", _NO_VALUE), photo_id),
        usage=usage,
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
                        {
                            "type": "text",
                            "text": build_classification_prompt(
                                max_fine_labels=MAX_FINE_LABELS_PER_PHOTO
                            ),
                        },
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
                        {
                            "type": "text",
                            "text": build_classification_prompt(
                                max_fine_labels=MAX_FINE_LABELS_PER_PHOTO
                            ),
                        },
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
