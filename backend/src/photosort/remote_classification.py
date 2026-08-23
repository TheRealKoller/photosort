from __future__ import annotations

import base64
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

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
# analog landmark.py, aber offenes 1-3-Label-Antwortschema statt eines festen Enums
# (REMOTE_CATEGORY_LABELS-Allow-Liste entfaellt ersatzlos). Nutzt dieselben, jetzt providerneutral
# gefuehrten Vision-Modelle wie landmark.py (cloud_vision.py) - kein neues Provider-Setting.

ANTHROPIC_CATEGORY_MODEL = ANTHROPIC_VISION_MODEL
MISTRAL_CATEGORY_MODEL = MISTRAL_VISION_MODEL

# Kurze, reine Klassifikationsantwort (bis zu drei kleine JSON-Objekte) - 256 bleibt ausreichend
# (ADR 0032 Punkt 3).
_MAX_RESPONSE_TOKENS = 256

MIN_REMOTE_LABELS_PER_PHOTO = 1
MAX_REMOTE_LABELS_PER_PHOTO = 3
# Defensive Obergrenze gegen eine entartete Modellantwort (ADR 0032 Punkt 3) - verhindert einen
# uebermaessig langen canonical_key/display_name, bevor resolve_canonical_label/_slugify aufgerufen
# wird (Security-Abschnitt der Spec, Punkt 3).
MAX_REMOTE_LABEL_LENGTH = 60

_PROMPT = (
    "Analysiere dieses Foto. Nenne 1 bis 3 kurze, praegnante deutsche Schlagworte, die den "
    "wesentlichen Inhalt beschreiben (z.B. Ereignis, Ort, Motiv, Tier - kein geschlossenes "
    "Vokabular, waehle frei passende Begriffe). Antworte AUSSCHLIESSLICH mit einem einzigen "
    "validen JSON-Objekt, ohne Markdown-Codeblock, ohne weiteren Text, exakt in dieser Form: "
    '{"labels": [{"label": "<Schlagwort>", "confidence": <Zahl zwischen 0 und 1>}, ...]} '
    "mit mindestens einem und hoechstens drei Eintraegen."
)


class RemoteCategoryClassificationApiError(Exception):
    """Fehler beim Aufruf der Vision-API fuer die Remote-Kategorie-Klassifizierung - analog
    LandmarkApiError. Sicherheitskritisches Muss-Kriterium: Meldungen betten NIEMALS den API-Key
    oder Base64-Bilddaten ein."""


@dataclass(frozen=True)
class CategoryLabelDetection:
    """Ein einzelnes, vom Vision-LLM geliefertes Roh-Label + Konfidenz (ADR 0032 Punkt 3) - ersetzt
    das fruehere CategoryDetection (einzelner Kategorie-Wert aus einem festen Enum)."""

    label: str
    confidence: float


class CategoryDetectionClientLike(Protocol):
    """Schmale, injizierbare Schnittstelle (analog LandmarkClientLike) - Rueckgabe ist jetzt eine
    Liste (1-3 Eintraege) statt eines einzelnen Werts."""

    async def classify(
        self, image_bytes: bytes, mime_type: str
    ) -> list[CategoryLabelDetection]: ...


def _category_labels_from_json(parsed: Any) -> list[CategoryLabelDetection]:
    """Providerneutrale, rein STRUKTURELLE Validierung der Roh-Antwort (ADR 0032 Punkt 3) - anders
    als beim frueheren REMOTE_CATEGORY_LABELS-Enum gibt es keine inhaltliche Allow-Liste mehr:
    (a) `labels` ist eine Liste mit MIN_REMOTE_LABELS_PER_PHOTO <= len <= MAX_REMOTE_LABELS_PER_
    PHOTO, (b) jedes Element hat ein nicht-leeres, getrimmtes `label` mit hoechstens
    MAX_REMOTE_LABEL_LENGTH Zeichen, (c) `confidence` ist zu float konvertierbar und wird auf
    [0, 1] geklemmt (identisches Muster zu landmark.py::_landmark_detection_from_json). Jede
    Verletzung -> RemoteCategoryClassificationApiError."""
    try:
        raw_labels = parsed["labels"]
    except (KeyError, TypeError) as exc:
        raise RemoteCategoryClassificationApiError(
            "Unerwartete Antwortstruktur der Vision-API-Antwort (fehlendes 'labels'-Feld)."
        ) from exc

    if not isinstance(raw_labels, list):
        raise RemoteCategoryClassificationApiError(
            "Unerwartete Antwortstruktur der Vision-API-Antwort ('labels' ist keine Liste)."
        )
    if not (MIN_REMOTE_LABELS_PER_PHOTO <= len(raw_labels) <= MAX_REMOTE_LABELS_PER_PHOTO):
        raise RemoteCategoryClassificationApiError(
            f"Unerwartete Anzahl Labels ({len(raw_labels)}), erwartet "
            f"{MIN_REMOTE_LABELS_PER_PHOTO}-{MAX_REMOTE_LABELS_PER_PHOTO}."
        )

    detections: list[CategoryLabelDetection] = []
    for raw in raw_labels:
        try:
            label = raw.get("label")
            confidence = float(raw.get("confidence", 0.0))
        except (AttributeError, TypeError, ValueError) as exc:
            raise RemoteCategoryClassificationApiError(
                "Unerwartete Antwortstruktur eines Label-Eintrags."
            ) from exc
        if not isinstance(label, str):
            raise RemoteCategoryClassificationApiError(
                "Unerwartete Antwortstruktur eines Label-Eintrags (label ist kein String)."
            )
        trimmed = label.strip()
        if not trimmed or len(trimmed) > MAX_REMOTE_LABEL_LENGTH:
            raise RemoteCategoryClassificationApiError(
                f"Label ist leer oder laenger als {MAX_REMOTE_LABEL_LENGTH} Zeichen."
            )
        clamped_confidence = max(0.0, min(1.0, confidence))
        detections.append(CategoryLabelDetection(label=trimmed, confidence=clamped_confidence))
    return detections


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

    async def classify(self, image_bytes: bytes, mime_type: str) -> list[CategoryLabelDetection]:
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
                        {"type": "text", "text": _PROMPT},
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
        return _category_labels_from_json(parsed)


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

    async def classify(self, image_bytes: bytes, mime_type: str) -> list[CategoryLabelDetection]:
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
                        {"type": "text", "text": _PROMPT},
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
        return _category_labels_from_json(parsed)


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
# Mistral (ministral-3b-2512): $0.10/MTok Input UND Output (docs.mistral.ai/models/
# ministral-3-3b-25-12, verifiziert 2026-08-23 - symmetrische Input-/Output-Preisgestaltung, anders
# als bei Anthropic). Mistral veroeffentlicht fuer dieses Modell KEINE offizielle Bild-Token-Formel
# (anders als Anthropic) - Schaetzung bleibt dokumentiert-unkalibriert basierend auf vergleichbarem
# Pixtral-Familien-Tiling-Verhalten (grobe Bandbreite 1000-4000 Bild-Tokens je nach Aufloesung/
# Kachelung) -> $0.0001-0.0004 Input, Output vernachlaessigbar (~$0.00001). Mittelwert $0.0003/Bild.
COST_PER_IMAGE_USD: dict[Literal["anthropic", "mistral"], float] = {
    "anthropic": 0.0045,
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
class CategoryLabelSnapshotEntry:
    """Ein Eintrag des In-Memory-Snapshots der `category_labels`-Tabelle (ADR 0032 Punkt 4/5) -
    worker.py::run_remote_category_classification laedt diesen Snapshot einmal zu Laufbeginn und
    reicht ihn (mutierbar) an resolve_canonical_label weiter; neu angelegte Eintraege werden sofort
    lokal ergaenzt (kein erneutes SELECT, keine Nebenlaeufigkeits-Race). Bewusst NICHT frozen
    (anders als CategoryLabelDetection) - worker.py setzt nach dem DB-Insert die echte `id` auf
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
    worker.py-Cache-Key-Bildung), keine neue Bibliothek."""
    slug = _SLUG_INVALID_CHARS.sub("_", text.casefold())
    return slug.strip("_")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Reine Vektor-Aehnlichkeitsfunktion (ADR 0032 Punkt 4, Schritt 3) - beide Embedding-Vektoren
    sind bereits L2-normiert (label_embedding.py::_mean_pool_and_normalize), das Skalarprodukt
    entspricht deshalb direkt der Kosinus-Aehnlichkeit, keine erneute Normierung noetig."""
    return sum(x * y for x, y in zip(a, b, strict=True))


def resolve_canonical_label(
    raw_label: str,
    existing_labels: list[CategoryLabelSnapshotEntry],
    embedder: LabelEmbedderLike,
) -> CategoryLabelSnapshotEntry:
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

    best_entry: CategoryLabelSnapshotEntry | None = None
    best_similarity = -1.0
    for entry in existing_labels:
        similarity = _cosine_similarity(vector, entry.embedding)
        if similarity > best_similarity:
            best_similarity = similarity
            best_entry = entry

    if best_entry is not None and best_similarity >= CATEGORY_LABEL_SIMILARITY_THRESHOLD:
        return best_entry

    new_entry = CategoryLabelSnapshotEntry(
        canonical_key=_slugify(normalized),
        display_name=raw_label,
        embedding=vector,
    )
    existing_labels.append(new_entry)
    return new_entry
