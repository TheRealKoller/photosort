"""Die feste, vorsichtige Regel, wann eine festgelegte Person auf einem Foto sicher erkannt ist.

REIN: kein Modell, keine Datenbank, keine Umgebung, keine `settings`. Die Entscheidungsfunktion
bekommt je verwertbarem Gesicht die Aehnlichkeiten zu den Personen, keine Merkmale. Ihr
vollstaendiger Importgraph enthaelt keinen Netzwerk-Client.

DIE KONSTANTEN SIND KEINE EINSTELLUNG - keine Umgebungsvariable, kein Endpunkt, keine Oberflaeche,
und sie werden nur hier zugewiesen (Waechter in `tests/test_person_matching.py`). Nach einer
falschen Benennung in der Abnahme wird verschaerft und erneut geprueft; gelockert wird nie ohne
eine neue, fehlerfreie Abnahme. Weil die Regel "genau ein Kandidat" unter Verschaerfung nicht
monoton ist, verlangt jede Verschaerfung eine vollstaendige neue Durchsicht.

ALLE VERGLEICHE, DIE ZU EINER BENENNUNG FUEHREN, STEHEN IN EINSCHLUSSFORM (`>=`): Eine
NaN-Aehnlichkeit erfuellt keinen davon und fuehrt damit nie zu einer Benennung. Eine Umstellung
auf `not <` kehrte genau das um.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

# Verwertbar ist ein Gesicht erst ab diesem Detektionswert und dieser kuerzeren Seite in Pixeln
# der Arbeitsfassung. Unverwertbare Gesichter werden weder benannt noch mitgezaehlt, und fuer sie
# entsteht kein Merkmal.
MIN_DETECTION_SCORE = 0.90
MIN_FACE_SIDE_PX = 100
# Kosinus zum Schwerpunkt der Referenzen, ab dem ein Gesicht Kandidat einer Person ist.
ACCEPT_SIMILARITY = 0.50
# Um so viel muss die Aehnlichkeit die zur anderen Person uebertreffen.
DISTINCT_MARGIN = 0.10
MAX_FACES_PER_PHOTO = 20
MAX_REFERENCES_PER_PERSON = 20

EMBEDDING_DIMENSION = 128
# Toleranzband der Norm eines gespeicherten Merkmals um 1. Binaer exakt (1/64), damit die Grenze
# des Bands selbst darstellbar ist.
NORM_TOLERANCE = 0.015625


@dataclass(frozen=True)
class StoredReference:
    model_key: str
    embedding: Sequence[float]


def is_usable(*, score: float, width: float, height: float) -> bool:
    return score >= MIN_DETECTION_SCORE and min(width, height) >= MIN_FACE_SIDE_PX


def validated_embedding(values: Sequence[float]) -> tuple[float, ...] | None:
    """Das Merkmal, wenn es 128 endliche Werte mit einer Norm im Toleranzband um 1 hat - sonst
    `None`. Ein NaN-, Inf- oder Nullvektor wird so nie gespeichert und geht in keinen Schwerpunkt
    ein."""
    if len(values) != EMBEDDING_DIMENSION:
        return None
    vector = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in vector):
        return None
    norm = math.sqrt(math.fsum(value * value for value in vector))
    if abs(norm - 1.0) <= NORM_TOLERANCE:
        return vector
    return None


def _normalized(vector: Sequence[float]) -> tuple[float, ...] | None:
    norm = math.sqrt(math.fsum(value * value for value in vector))
    if not norm > 0.0 or not math.isfinite(norm):
        return None
    return tuple(value / norm for value in vector)


def centroid(references: Iterable[StoredReference], *, model_key: str) -> tuple[float, ...] | None:
    """Der normierte Mittelwert der normierten Referenzen des aktuellen Modells.

    Referenzen eines anderen `model_key` fliessen nicht ein. Eine Person ohne gueltige Referenz
    hat keinen Schwerpunkt und ist damit nie Kandidat. Normiert wird vor dem Mitteln, damit keine
    Referenz allein ueber ihre Laenge mehr Gewicht bekommt."""
    usable: list[tuple[float, ...]] = []
    for reference in references:
        if reference.model_key != model_key or len(reference.embedding) != EMBEDDING_DIMENSION:
            continue
        # `None` auch bei NaN/Inf: deren Norm ist nicht endlich positiv.
        vector = _normalized(reference.embedding)
        if vector is not None:
            usable.append(vector)
    if not usable:
        return None
    mean = [math.fsum(column) / len(usable) for column in zip(*usable, strict=True)]
    return _normalized(mean)


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    norm_a = math.sqrt(math.fsum(value * value for value in a))
    norm_b = math.sqrt(math.fsum(value * value for value in b))
    if not (norm_a > 0.0 and norm_b > 0.0):
        return math.nan
    return math.fsum(x * y for x, y in zip(a, b, strict=True)) / (norm_a * norm_b)


def similarities_to(
    embedding: Sequence[float], centroids: Mapping[int, Sequence[float]]
) -> dict[int, float]:
    """Je Person mit Schwerpunkt die Aehnlichkeit dieses Gesichts. Lebt nur waehrend der
    Verarbeitung eines Fotos; kein Aufrufer speichert oder protokolliert sie."""
    return {person_id: cosine(embedding, center) for person_id, center in centroids.items()}


def _is_candidate(person_id: int, similarities: Mapping[int, float]) -> bool:
    similarity = similarities[person_id]
    if not similarity >= ACCEPT_SIMILARITY:
        return False
    return all(
        similarity - other >= DISTINCT_MARGIN
        for other_id, other in similarities.items()
        if other_id != person_id
    )


def decide_assignments(faces: Sequence[Mapping[int, float]]) -> frozenset[int]:
    """Die auf einem Foto sicher erkannten Personen.

    `faces` traegt je verwertbarem Gesicht die Aehnlichkeit zu jeder Person mit Schwerpunkt.
    Kandidat einer Person ist ein Gesicht, wenn es `ACCEPT_SIMILARITY` erreicht und die
    Aehnlichkeit zu jeder anderen Person um mindestens `DISTINCT_MARGIN` uebertrifft - damit ist
    jedes Gesicht hoechstens einer Person Kandidat. Erkannt ist eine Person nur, wenn GENAU EIN
    Gesicht ihr Kandidat ist; bei zweien ist eines sicher falsch."""
    candidates: dict[int, int] = {}
    for similarities in faces:
        for person_id in similarities:
            if _is_candidate(person_id, similarities):
                candidates[person_id] = candidates.get(person_id, 0) + 1
    return frozenset(person_id for person_id, count in candidates.items() if count == 1)


def conflicts_with_other_person(similarity_to_other: float) -> bool:
    """Ein neu gezeigtes Gesicht, das dem Schwerpunkt der ANDEREN Person die Annahmeschwelle
    erreicht, wird abgelehnt. Hier ist die sichere Richtung das Ablehnen: Eine NaN-Aehnlichkeit
    gilt deshalb als Konflikt."""
    return not similarity_to_other < ACCEPT_SIMILARITY
