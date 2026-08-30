from __future__ import annotations

import base64
import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

from photosort.categories import (
    MAX_FINE_LABELS_PER_PHOTO,
    MAX_REMOTE_CATEGORIES_PER_PHOTO,
    build_classification_prompt,
    is_known_category,
)
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
from photosort.label_embedding import LabelEmbedderLike

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
# decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 3/4: strukturell
# analog landmark.py. Seit specs/features/0289-feste-kategorien.md/ADR 0049 ist das
# Antwortschema wieder GESCHLOSSEN, aber anders als vor ADR 0032: das Modell nennt bis zu drei
# KANDIDATEN aus dem festen Set (categories.py), die endgueltige Auswahl trifft der Code
# (resolve_category). Frei formulierte Feinlabels bleiben als reine Zusatzinformation erhalten.

logger = logging.getLogger(__name__)

ANTHROPIC_CATEGORY_MODEL = ANTHROPIC_VISION_MODEL
MISTRAL_CATEGORY_MODEL = MISTRAL_VISION_MODEL

# Kurze, reine Klassifikationsantwort - 256 bleibt ausreichend (ADR 0032 Punkt 3): drei
# Set-Schluessel (je hoechstens ~8 Tokens) plus zwei kurze deutsche Feinlabels und das
# JSON-Geruest liegen zusammen deutlich unter 100 Ausgabe-Tokens; der mit Spec 0289 deutlich
# groessere Prompt waechst ausschliesslich auf der EINGABEseite.
_MAX_RESPONSE_TOKENS = 256

# Defensive Obergrenze gegen eine entartete Modellantwort (ADR 0032 Punkt 3) - verhindert einen
# uebermaessig langen canonical_key/display_name, BEVOR resolve_canonical_label/_slugify aufgerufen
# wird (Security-Abschnitt der Spec 0289, Punkt 3). Ein zu langes Label wird VERWORFEN, nicht
# gekuerzt: ein auf 60 Zeichen abgeschnittenes Label erzeugte sonst dauerhaft einen unbrauchbaren
# canonical_key in der projektuebergreifenden Registry, und zwei verschiedene Labels koennten auf
# denselben Slug fallen. Storage-/Degenerationsgrenze, KEINE Sanitisierungsmassnahme (dieselbe
# Einordnung wie die 500-Zeichen-Kappung aus Spec 0058).
MAX_FINE_LABEL_LENGTH = 60

# Laengenbegrenzung fuer den in der WARNING-Zeile mitgeloggten Rohwert (Security-Abschnitt der
# Spec 0289, Punkt 4) - zusammen mit dem %r-Format (repr escaped Zeilenumbrueche/Steuerzeichen
# sichtbar) die Absicherung gegen Log-Injection durch eine entartete Modellantwort.
_MAX_LOGGED_RAW_VALUE_LENGTH = 60


class RemoteCategoryClassificationApiError(Exception):
    """Fehler beim Aufruf der Vision-API fuer die Remote-Kategorie-Klassifizierung - analog
    LandmarkApiError. Sicherheitskritisches Muss-Kriterium: Meldungen betten NIEMALS den API-Key
    oder Base64-Bilddaten ein."""


@dataclass(frozen=True)
class RemoteClassification:
    """Die validierte Antwort des Vision-LLM fuer EIN Foto (specs/features/0289-feste-
    kategorien.md, Umsetzungsschritt 4) - ersetzt die fruehere `list[CategoryLabelDetection]`.

    `categories` enthaelt ausschliesslich bekannte Set-Keys (categories.py::CATEGORY_REGISTRY) in
    Erstnennungs-Reihenfolge, hoechstens MAX_REMOTE_CATEGORIES_PER_PHOTO - unbekannte Rohwerte
    sind bereits verworfen. Ein leeres Tupel ist ein GUELTIGES Ergebnis (das Modell hat nichts
    Bekanntes genannt) und wird ueber `resolve_category` zu `nicht_erkannt`, kein Fehler.

    `fine_labels` enthaelt die zeichensanierten, freien Feinlabels, hoechstens
    MAX_FINE_LABELS_PER_PHOTO. Konfidenzen entfallen ersatzlos (ADR 0049 Entwurfsentscheidung 7:
    sie dienten nur der entfallenen Score-Auswahl)."""

    categories: tuple[str, ...]
    fine_labels: tuple[str, ...]


class CategoryDetectionClientLike(Protocol):
    """Schmale, injizierbare Schnittstelle (analog LandmarkClientLike).

    `photo_id` ist eine technische Detailentscheidung dieser Umsetzung (Spec 0289,
    Security-Abschnitt Punkt 4 verlangt "der einzelne verworfene Wert PLUS photo_id" in der
    WARNING-Zeile): der Parser sitzt innerhalb von `classify`, kennt das Foto sonst aber nicht.
    Der Wert wird ausschliesslich fuer diese Logzeile benutzt, nie an die API gesendet."""

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification: ...


def _log_discarded_category(photo_id: int, raw: object) -> None:
    """Ein verworfener, unbekannter Kategoriewert (ADR-0034-Muster: eine Zeile, WARNING, kein
    exc_info/Traceback - der Lauf bleibt erfolgreich, das ist erwartetes Best-effort-Verhalten).

    Security-Muss-Kriterien (Spec 0289, Abschnitt 4): geloggt wird AUSSCHLIESSLICH der einzelne
    verworfene Wert plus photo_id - nie die vollstaendige API-Antwort, nie der Request-Body, nie
    Base64-Bilddaten, nie der API-Key. Der Rohwert geht laengenbegrenzt und ueber %r (repr) ins
    Log, nie roh ueber %s: ein mehrzeiliger Modellwert koennte sonst gefaelschte Logzeilen
    erzeugen. Kein Log-Flooding moeglich - pro Foto koennen hoechstens so viele Werte verworfen
    werden, wie die Antwortliste Eintraege hat."""
    text = raw if isinstance(raw, str) else repr(raw)
    if len(text) > _MAX_LOGGED_RAW_VALUE_LENGTH:
        text = text[:_MAX_LOGGED_RAW_VALUE_LENGTH] + "..."
    logger.warning(
        "remote_category: unbekannter Kategoriewert verworfen photo_id=%s wert=%r", photo_id, text
    )


def _sanitize_label_text(raw: str) -> str:
    """Zeichensanitisierung eines frei formulierten Feinlabels (Security-Abschnitt der Spec 0289,
    Punkt 3) - laeuft VOR der Laengenpruefung und vor resolve_canonical_label/_slugify.

    Entfernt alle Unicode-Steuer- und Formatzeichen (Kategorien `Cc`/`Cf`: `\x00`,
    Zero-Width-Zeichen wie U+200B, Bidi-Overrides wie U+202E) und zieht Whitespace-Folgen zu einem
    einzelnen Leerzeichen zusammen. Steuerzeichen, die selbst Whitespace SIND (Zeilenumbruch,
    Tabulator, Wagenruecklauf), werden dabei durch ein Leerzeichen ersetzt statt ersatzlos
    entfernt - sonst verschmoelzen zwei Woerter ueber einen Zeilenumbruch hinweg zu einem
    (`str.split()` behandelt auch NBSP
    und andere Unicode-Leerzeichen als Whitespace); fuehrende/abschliessende Leerzeichen
    entfallen dabei mit.

    Bewusst eine BLACKLIST (Steuerzeichen), keine Zeichen-Whitelist (Entscheidung 1 der Spec):
    Feinlabels sind freier deutscher Text, eine Whitelist aus Buchstaben/Ziffern/Leerzeichen/
    Bindestrich wuerde legitime Labels beschaedigen. Escapetes Rendering im Frontend schuetzt
    gegen XSS, aber weder gegen optische Verfaelschung der Oberflaeche durch Bidi-/Zero-Width-
    Zeichen noch gegen mehrzeilige Logeintraege - genau diese Luecke schliesst diese Funktion.
    Nachruestbar an genau dieser einen Stelle, falls sich die Blacklist als zu schwach erweist."""
    without_controls = "".join(
        (" " if char.isspace() else "")
        if unicodedata.category(char) in ("Cc", "Cf")
        else char
        for char in raw
    )
    return " ".join(without_controls.split())


def _categories_from_json(raw_categories: list[Any], photo_id: int) -> tuple[str, ...]:
    """Verbindliche Verarbeitungsreihenfolge (Spec 0289, Teststrategie 5): trimmen -> leere Werte
    verwerfen -> unbekannte Werte verwerfen (+ genau ein WARNING je Wert) -> deduplizieren unter
    Erhalt der Erstnennungs-Reihenfolge -> ZULETZT kuerzen. Zuerst zu kuerzen wuerde gueltige
    Werte hinter ungueltigen verlieren."""
    accepted: list[str] = []
    for raw in raw_categories:
        if not isinstance(raw, str):
            _log_discarded_category(photo_id, raw)
            continue
        trimmed = raw.strip()
        if not trimmed or not is_known_category(trimmed):
            _log_discarded_category(photo_id, raw)
            continue
        if trimmed in accepted:
            continue
        accepted.append(trimmed)
    return tuple(accepted[:MAX_REMOTE_CATEGORIES_PER_PHOTO])


def _fine_labels_from_json(raw_labels: list[Any]) -> tuple[str, ...]:
    """Dieselbe Reihenfolge wie `_categories_from_json`, aber mit Zeichensanitisierung statt einer
    Set-Whitelist: sanitisieren -> leere/zu lange Werte verwerfen -> deduplizieren (Erstnennung
    gewinnt) -> ZULETZT kuerzen. Verworfene Feinlabels werden NICHT geloggt: anders als bei einem
    unbekannten Kategoriewert (der auf ein Prompt-/Set-Problem hindeutet) ist ein leeres oder
    entartetes Feinlabel ohne Diagnosewert, und der Wert selbst waere genau der Fremdtext, den
    Punkt 4 des Security-Abschnitts aus dem Log heraushalten will."""
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


def _classification_from_json(parsed: Any, photo_id: int) -> RemoteClassification:
    """Providerneutrale Validierung der Roh-Antwort (specs/features/0289-feste-kategorien.md,
    Umsetzungsschritt 4) - **strukturell hart, inhaltlich tolerant**:

    STRUKTURELL HART (jeweils RemoteCategoryClassificationApiError, das Foto wird auf Worker-Ebene
    best-effort uebersprungen): die Antwort ist kein JSON-Objekt, `categories` fehlt, `categories`
    ist keine Liste, oder `fine_labels` ist vorhanden aber keine Liste. Eine durch
    _MAX_RESPONSE_TOKENS abgeschnittene Antwort landet ueber denselben Pfad hier - nie bei einem
    teilweise geparsten Datensatz.

    INHALTLICH TOLERANT (ADR-0034-Muster): unbekannte Kategoriewerte und entartete Feinlabels
    werden VERWORFEN statt abgelehnt. Der wichtigste Grenzfall: sind ALLE Kategoriewerte
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

    return RemoteClassification(
        categories=_categories_from_json(raw_categories, photo_id),
        fine_labels=_fine_labels_from_json(raw_fine_labels),
    )


class AnthropicCategoryClient:
    """Echte, httpx-basierte Implementierung von CategoryDetectionClientLike (ADR 0032 Punkt 3),
    strukturell analog AnthropicLandmarkClient. `transport` ist injizierbar (httpx.MockTransport in
    Tests) - `build_category_classification_client()` unten laeuft NIE in einem automatisierten
    Test (echtes Secret + echter Netzwerkversuch)."""

    def __init__(
        self,
        api_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = VISION_REQUEST_TIMEOUT_SECONDS,
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

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
        body = {
            "model": ANTHROPIC_CATEGORY_MODEL,
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
        try:
            response = await self._client.post(ANTHROPIC_MESSAGES_URL, json=body)
        except httpx.HTTPError as exc:
            raise RemoteCategoryClassificationApiError(
                f"Anthropic Vision API nicht erreichbar: {exc}"
            ) from exc

        raise_for_vision_api_status(
            response, "Anthropic", RemoteCategoryClassificationApiError
        )
        parsed = anthropic_response_to_json(response.json(), RemoteCategoryClassificationApiError)
        return _classification_from_json(parsed, photo_id)


class MistralCategoryClient:
    """Echte, httpx-basierte Implementierung von CategoryDetectionClientLike (ADR 0032 Punkt 3),
    exakt analog MistralLandmarkClient."""

    def __init__(
        self,
        api_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = VISION_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
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
            "model": MISTRAL_CATEGORY_MODEL,
            "max_tokens": _MAX_RESPONSE_TOKENS,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": (
                                f"data:{mime_type};base64,"
                                f"{base64.b64encode(image_bytes).decode()}"
                            ),
                        },
                        {"type": "text", "text": build_classification_prompt()},
                    ],
                }
            ],
        }
        try:
            response = await self._client.post(MISTRAL_CHAT_COMPLETIONS_URL, json=body)
        except httpx.HTTPError as exc:
            raise RemoteCategoryClassificationApiError(
                f"Mistral Chat Completions API nicht erreichbar: {exc}"
            ) from exc

        raise_for_vision_api_status(response, "Mistral", RemoteCategoryClassificationApiError)
        parsed = mistral_response_to_json(response.json(), RemoteCategoryClassificationApiError)
        return _classification_from_json(parsed, photo_id)


def build_category_classification_client() -> CategoryDetectionClientLike:
    """Dispatch-Factory zwischen AnthropicCategoryClient (Default) und MistralCategoryClient je
    nach settings.landmark_provider (ADR 0032 Punkt 3: KEIN neues Provider-Setting - derselbe
    Schalter wie fuer landmark). Laeuft NIE in einem automatisierten Test (echtes Secret + echter
    Netzwerkversuch), analog build_landmark_client/build_face_detector."""
    if settings.landmark_provider == "mistral":
        mistral_client: CategoryDetectionClientLike = MistralCategoryClient(
            api_key=settings.mistral_api_key
        )
        return mistral_client
    anthropic_client: CategoryDetectionClientLike = AnthropicCategoryClient(
        api_key=settings.anthropic_api_key
    )
    return anthropic_client


# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, Akzeptanzkriterium
# "Kostenschätzung", ADR 0032 Punkt 8: dokumentiert-unkalibrierte Konstante je Provider - developer
# hat die Werte gegen die tatsaechliche Preisliste verifiziert (2026-08-23), statt der reinen
# ADR-Schaetzung blind zu vertrauen:
#
# Anthropic (claude-haiku-4-5): $1.00/MTok Input, $5.00/MTok Output (offizielle Preisliste,
# Stand 2026-08-23 - deckt sich mit dem bereits in der ADR zitierten Preisverhaeltnis). Bild-
# Token-Formel laut offizieller Anthropic-Dokumentation: tokens ≈ (breite_px * hoehe_px) / 750
# (verifiziert gegen den bekannten Referenzwert 1092x1092px ≈ 1590 Tokens: 1092*1092/750 ≈ 1590
# ✓). Die
# `display`-Cache-Variante ist auf DISPLAY_MAX_SIZE=2048px lange Kante begrenzt (thumbnails.py,
# Seitenverhaeltnis erhalten) - fuer ein typisches 3:2-/4:3-Landschaftsfoto an dieser Obergrenze
# ergeben sich ca. 3700-4200 Bild-Tokens (2048x1365 bzw. 2048x1536), viele reale Quellfotos sind
# aber kleiner als 2048px lange Kante (kein Hochskalieren) und verbrauchen entsprechend weniger.
# Reprae­sentativer Mittelwert ~3900 Bild-Tokens -> $0.0039 Input; Output (JSON-Array mit 1-3
# Objekten, ADR-Schaetzung 80-160 Tokens, Mittelwert 120) -> $0.0006. Summe gerundet $0.0045/Bild.
#
# Bewusste, begruendete Abweichung vom ADR-0032-Schaetzbereich ($0,0020-0,0028/Bild) - kein
# stillschweigendes Abweichen (Review-Fund, requirements-engineer): der ADR-Bereich stuetzt sich
# laut ADR-Text auf einen "unveraendert" aus der Vorfassung uebernommenen Bildtoken-Anteil von ca.
# $0,0016 - das entspricht rechnerisch genau dem in der ADR selbst als Referenzwert zitierten
# 1092x1092px-Beispiel (1092*1092/750 ≈ 1590 Tokens * $1/MTok ≈ $0,0016), NICHT der tatsaechlich
# in diesem Feature versendeten Bildquelle. Real verschickt wird ausschliesslich die
# `display`-Cache-Variante mit einer Obergrenze von 2048px langer Kante (siehe oben) - ein
# typisches Landschaftsfoto an dieser Obergrenze braucht mit ca. 3900 Tokens gut 2,4x so viele
# Bild-Tokens wie das 1092px-Referenzbeispiel. Die ADR-Schaetzgrundlage war damit nicht falsch
# gerechnet, sondern basierte auf einer kleineren, nicht repraesentativen Bildaufloesung als der
# tatsaechlich implementierten Bildquelle - der hier verwendete, hoehere Wert ist die gegen die
# reale Bildquelle nachgerechnete Korrektur, keine Abweichung vom eigentlichen ADR-Rechenweg
# (gleiche Preise/gleiche Formel, andere - jetzt korrekte - Eingangsaufloesung).
#
# Mistral (ministral-3b-2512): $0.10/MTok Input UND Output (docs.mistral.ai/models/
# ministral-3-3b-25-12, verifiziert 2026-08-23 - symmetrische Input-/Output-Preisgestaltung, anders
# als bei Anthropic). Mistral veroeffentlicht fuer dieses Modell KEINE offizielle Bild-Token-Formel
# (anders als Anthropic) - Schaetzung bleibt dokumentiert-unkalibriert basierend auf vergleichbarem
# Pixtral-Familien-Tiling-Verhalten (grobe Bandbreite 1000-4000 Bild-Tokens je nach Aufloesung/
# Kachelung) -> $0.0001-0.0004 Input, Output vernachlaessigbar (~$0.00001). Mittelwert $0.0003/Bild.
#
# NEUVERIFIKATION (developer, 2026-08-30, Pflicht aus dem Security-Abschnitt der Spec 0289 Punkt 8
# / ADR 0032 Punkt 8): der aus CATEGORY_REGISTRY erzeugte Prompt (categories.py::
# build_classification_prompt) ersetzt das frühere ~120-Token-Literal durch 13 Kategorie-Bloecke
# mit Definition und Negativabgrenzung - gemessen an der erzeugten Zeichenzahl (~3400 Zeichen)
# und der ueblichen Faustregel ~4 Zeichen/Token fuer deutschen Text liegt der Prompt bei grob
# 850-900 Tokens, also rund +700 Input-Tokens gegenueber dem alten Wortlaut. Das deckt sich mit
# der in der Spec genannten Bandbreite (+500-700 Tokens).
#
# Anthropic: +700 Input-Tokens * $1.00/MTok = +$0.0007/Bild -> 0.0045 + 0.0007 = $0.0052,
# gerundet 0.0052. Preise unveraendert gegenueber der Verifikation vom 2026-08-23
# (claude-haiku-4-5: $1.00/MTok Input, $5.00/MTok Output); der Ausgabe-Anteil sinkt sogar leicht
# (Set-Schluessel statt frei formulierter Schlagworte mit Konfidenzzahlen), das wird hier bewusst
# NICHT eingerechnet - die Schaetzung soll die Kosten eher ueber- als unterschaetzen, weil sie die
# Grundlage einer bewussten Freigabe durch Daniel ist.
#
# Mistral: +700 Input-Tokens * $0.10/MTok = +$0.00007/Bild - unterhalb der vierten
# Nachkommastelle, in der diese Konstante gefuehrt wird. Der Wert bleibt deshalb bei 0.0003; die
# Groessenordnung (Bild-Tokens dominieren) ist unveraendert.
COST_PER_IMAGE_USD: dict[Literal["anthropic", "mistral"], float] = {
    "anthropic": 0.0052,
    "mistral": 0.0003,
}

# Dokumentiert-unkalibrierter Startwert (developer verifiziert/kalibriert mit ein paar echten
# Test-Label-Paaren wie "Hund"/"Hunde"/"dog" vs. "Katze"/"Hund" vor dem Festschreiben - gleiche
# Klasse wie CATEGORY_ACTIVE_THRESHOLD_FRACTION/SHARPNESS_NORMALIZATION_CEILING, kein
# Fotokorpus/Label-Korpus im Repo zur Kalibrierung). Stichprobe gegen die echten Assets vor dem
# Commit (test_label_embedding.py::TestRealAssetOutputDimension) ergab Kosinus-Aehnlichkeiten von
# 0.92-0.99 fuer "Hund"/"Hunde"/"dog" und < 0.4 fuer "Katze"/"Strand" - 0.78 liegt komfortabel
# zwischen beiden Gruppen.
CATEGORY_LABEL_SIMILARITY_THRESHOLD = 0.78


@dataclass
class FineLabelSnapshotEntry:
    """Ein Eintrag des In-Memory-Snapshots der `fine_labels`-Tabelle (ADR 0032 Punkt 4/5, in
    specs/features/0289-feste-kategorien.md mit der Tabelle umbenannt) -
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
    """Reine String-Normalisierung (ADR 0032 Punkt 4, Schritt 1) - kein Modell-Aufruf. NFKC deckt
    u.a. Ligaturen/Kompatibilitaetszeichen ab (z.B. "ﬁsch" -> "fisch"), casefold ist eine
    aggressivere, unicode-bewusste Kleinschreibung als .lower()."""
    return unicodedata.normalize("NFKC", raw).strip().casefold()


_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    """Bildet einen URL-/Key-sicheren Slug (ADR 0032 Punkt 4, Schritt 4): casefoldet defensiv
    zusaetzlich selbst (funktioniert damit unabhaengig davon, ob der Aufrufer bereits normalisiert
    hat), Sonderzeichen/Leerzeichen zu `_`, doppelte `_` reduziert, fuehrende/abschliessende `_`
    entfernt - dieselbe Klasse einfacher, reiner Textfunktion wie andernorts im Projekt (z.B.
    worker.py-Cache-Key-Bildung), keine neue Bibliothek.

    Hash-Fallback (Review-Fund, security-engineer): `_SLUG_INVALID_CHARS` matcht nur
    a-z/0-9 als gueltig - ein rein nicht-lateinisches Rohlabel (z.B. japanisch/chinesisch, ein vom
    offenen Remote-Vokabular (ADR 0032) explizit nicht ausgeschlossener Fall) wuerde sonst zu
    einem leeren String slugifien. Zwei verschiedene solche Label wuerden dann denselben (leeren)
    canonical_key produzieren und an UniqueConstraint(fine_labels.canonical_key) scheitern -
    ein Verfuegbarkeitsrisiko, das den ganzen Batch-Lauf abbricht statt nur das eine betroffene
    Foto zu ueberspringen (ADR 0032 Punkt 5: best-effort ohne Retry gilt pro Foto, nicht fuer eine
    IntegrityError beim Label-Anlegen). Deterministischer SHA256-Praefix statt Zufallswert -
    derselbe Rohtext liefert bei einem Wiederholungslauf denselben Slug, kein Duplikat-Risiko."""
    slug = _SLUG_INVALID_CHARS.sub("_", text.casefold()).strip("_")
    if slug:
        return slug
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"label_{digest}"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Reine Vektor-Aehnlichkeitsfunktion (ADR 0032 Punkt 4, Schritt 3) - beide Embedding-Vektoren
    sind bereits L2-normiert (label_embedding.py::_mean_pool_and_normalize), das Skalarprodukt
    entspricht deshalb direkt der Kosinus-Aehnlichkeit, keine erneute Normierung noetig."""
    return sum(x * y for x, y in zip(a, b, strict=True))


def resolve_canonical_label(
    raw_label: str,
    existing_labels: list[FineLabelSnapshotEntry],
    embedder: LabelEmbedderLike,
) -> FineLabelSnapshotEntry:
    """Reine, DB-freie Funktion (ADR 0032 Punkt 4) - loest ein einzelnes Roh-Label auf einen
    kanonischen Eintrag auf: (1) exakter Normalisierungs-Fast-Path (KEIN embed()-Aufruf), (2)
    Kosinus-Aehnlichkeits-Fallback gegen ALLE `existing_labels` (`>=` CATEGORY_LABEL_SIMILARITY_
    THRESHOLD, inklusiv), (3) sonst ein neuer kanonischer Eintrag, der `existing_labels` sofort
    (in-place) ergaenzt - verhindert Duplikat-Anlage bei zwei sehr aehnlichen neuen Labeln
    innerhalb desselben Laufs (Teststrategie-Abschnitt der Spec)."""
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
