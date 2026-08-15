from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from photosort.classification import (
    LANDSCAPE_UNIFORM_FRACTION_THRESHOLD,
    AnimalDetection,
    FaceBoundingBox,
    FaceDetectorLike,
    ObjectDetectorLike,
    compute_uniform_area_fraction,
    detect_animals,
    detect_person,
)
from photosort.models import CriterionSource

# specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md, decisions/0021-kriterien-
# datenmodell-kuratierungs-pipeline.md, Punkt 1: Kriterien-Registry + Normierungsfunktionen. Die
# konkrete Kriterien-LISTE ueber sharpness/exposure/content_people/content_landscape hinaus ist
# bewusst nicht Teil dieser Spec (siehe "Out of Scope") - Register-Erweiterung ist der einzige
# Aufwand fuer ein kuenftiges neues Kriterium, keine Migration.


@dataclass(frozen=True)
class CriterionDefinition:
    key: str
    display_name: str
    source: CriterionSource


CRITERIA_REGISTRY: dict[str, CriterionDefinition] = {
    "sharpness": CriterionDefinition("sharpness", "Schärfe", CriterionSource.LOCAL_HEURISTIC),
    "exposure": CriterionDefinition("exposure", "Belichtung", CriterionSource.LOCAL_HEURISTIC),
    "content_people": CriterionDefinition(
        "content_people", "Menschen erkannt", CriterionSource.LOCAL_ML
    ),
    "content_landscape": CriterionDefinition(
        "content_landscape", "Landschaft/Flächig", CriterionSource.LOCAL_HEURISTIC
    ),
    # specs/features/0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md ab hier:
    "tier": CriterionDefinition("tier", "Tier erkannt", CriterionSource.LOCAL_ML),
    "goldener_schnitt": CriterionDefinition(
        "goldener_schnitt", "Goldener Schnitt", CriterionSource.LOCAL_HEURISTIC
    ),
}

# Obergrenze fuer die Normierung der unbeschraenkten Laplace-Varianz-Skala (scoring.py::
# compute_sharpness) auf [0, 1] - technische Detailentscheidung der Umsetzung, nicht gegen einen
# echten Fotokorpus kalibriert (gleicher Kalibrierungs-Vorbehalt wie scoring.py::
# SHARPNESS_REJECT_THRESHOLD und classification.py::UNIFORM_TILE_VARIANCE_THRESHOLD). Werte
# darueber werden auf 1.0 geklemmt statt die Skala zu sprengen.
SHARPNESS_NORMALIZATION_CEILING = 200.0


def normalize_sharpness(raw_sharpness: float) -> float:
    """Bildet die unbeschraenkte, "hoeher = schaerfer"-Laplace-Varianz (scoring.py::
    compute_sharpness) auf [0, 1] ab - reine In-Memory-Transformation der bereits vorhandenen
    PhotoScore.sharpness-Rohwerte, kein erneuter Bildzugriff (Akzeptanzkriterium der Spec)."""
    return max(0.0, min(1.0, raw_sharpness / SHARPNESS_NORMALIZATION_CEILING))


def normalize_exposure(raw_exposure: float) -> float:
    """scoring.py::compute_exposure liefert den Anteil geclippter Pixel (0.0 = perfekt belichtet,
    1.0 = vollstaendig geclippt, bereits in [0, 1]) - "hoeher = besser" erfordert eine Invertierung,
    keine Skalen-Transformation."""
    return 1.0 - max(0.0, min(1.0, raw_exposure))


def content_people_from_faces(faces: list[FaceBoundingBox]) -> float:
    """Reine Score-Berechnung aus einer bereits vorhandenen FaceBoundingBox-Liste, OHNE eigene
    Detektion (Spec 0038: worker.py::_compute_content_criteria ruft detect_person nur EINMAL auf
    und nutzt das Ergebnis sowohl fuer content_people als auch fuer goldener_schnitt weiter, statt
    detect_person zweimal aufzurufen)."""
    return 1.0 if faces else 0.0


def compute_content_people(image: Image.Image, detector: FaceDetectorLike) -> float:
    """`content_people`-Kriterium (Akzeptanzkriterium der Spec: mind. zwei Inhalts-Kriterien,
    wiederverwendet aus classification.py). Score-Grundlage bleibt `bool(detect_person(...))`
    (Vorgriffs-Ergaenzung der Spec: detect_person liefert seit dieser Spec zwar bereits
    FaceBoundingBox-Listen fuer die kuenftige Goldener-Schnitt-Kriterien-Spec 0038, funktional
    aendert sich fuer dieses Kriterium hier nichts)."""
    return content_people_from_faces(detect_person(image, detector))


def compute_content_landscape(image: Image.Image) -> float:
    """`content_landscape`-Kriterium: der Uniform-Flaechen-Anteil (classification.py::
    compute_uniform_area_fraction) ist bereits auf [0, 1] normiert, "hoeher = flaechiger/eher
    Landschaft" - keine weitere Transformation noetig."""
    return compute_uniform_area_fraction(image)


class SubjectBoxLike(Protocol):
    """Schmale strukturelle Schnittstelle, die compute_golden_ratio_score fuer ein Kompositions-
    Subjekt braucht - sowohl FaceBoundingBox (classification.py) als auch die kuenftige
    AnimalDetection (Spec 0038, Tier-Kriterium) erfuellen sie, ohne dass criteria.py eine harte
    Abhaengigkeit auf den Tier-Erkennungscode braucht (Reihenfolge der Spec: Goldener Schnitt vor
    Tier implementiert). Als Nur-Lese-Properties (statt einfacher Attribut-Annotationen)
    deklariert, damit auch @dataclass(frozen=True)-Implementierungen (FaceBoundingBox) den
    Vertrag strukturell erfuellen - mypy --strict wertet einfache Attribut-Annotationen in einem
    Protocol als lese-/schreibbar, was ein unveraenderliches Dataclass-Feld nicht erfuellen kann."""

    @property
    def x_center(self) -> float: ...
    @property
    def y_center(self) -> float: ...
    @property
    def width(self) -> float: ...
    @property
    def height(self) -> float: ...


# Die vier Drittel-Schnittpunkte der Drittelregel/des Goldenen Schnitts (Architektur-Abschnitt der
# Spec 0038: "Distanz des/der Subjekt-Zentren zu den vier Drittel-Schnittpunkten"). Ursprung oben
# links, normiert auf [0, 1] wie FaceBoundingBox.
_GOLDEN_RATIO_THIRD_POINTS: tuple[tuple[float, float], ...] = (
    (1 / 3, 1 / 3),
    (2 / 3, 1 / 3),
    (1 / 3, 2 / 3),
    (2 / 3, 2 / 3),
)

# Groesstmoeglicher Abstand eines Punkts im Einheitsquadrat zu seinem naechstgelegenen
# Drittel-Schnittpunkt - liegt an den vier Bildecken (z.B. (0,0) -> naechster Punkt (1/3,1/3)),
# Abstand dort ist sqrt(2)/3. Dient als Nenner, um die raueumliche Distanz auf [0, 1] zu normieren
# (technische Detailentscheidung der Umsetzung, geometrisch exakt hergeleitet, keine
# Kalibrierungsfrage wie bei den uebrigen SCHWELLWERT-Konstanten dieses Moduls).
_GOLDEN_RATIO_MAX_DISTANCE = math.sqrt(2) / 3


def _bounding_box_area(box: SubjectBoxLike) -> float:
    return box.width * box.height


def _largest_by_area[T: SubjectBoxLike](boxes: Sequence[T]) -> T:
    # Eigene kleine generische Hilfsfunktion statt max(boxes, key=_bounding_box_area) direkt am
    # Aufrufort - mypy --strict kann den Rueckgabetyp von max() sonst nicht praezise an den
    # jeweils konkreten Sequenztyp (list[FaceBoundingBox] vs. Sequence[SubjectBoxLike]) binden,
    # wenn `key` als Protocol-Parameter typisiert ist (bekannte mypy-Ungenauigkeit bei
    # max()-Ueberladungen mit Protocol-Argumenten).
    return max(boxes, key=_bounding_box_area)


def _select_primary_subject(
    faces: list[FaceBoundingBox], animals: Sequence[SubjectBoxLike]
) -> SubjectBoxLike | None:
    """Waehlt EIN Subjekt-Zentrum fuer die Kompositions-Bewertung (Akzeptanzkriterium der Spec:
    "getestete, dokumentierte Auswahlregel, keine implizite/zufaellige Auswahl der ersten
    Bounding-Box"). Regel: erkannte Gesichter haben grundsaetzlich Vorrang vor Tier-Erkennungen
    (Menschen sind fuer Daniel/seine Frau typischerweise das relevantere Kompositions-Subjekt,
    ADR 0022 Punkt 4: Tier nur als Fallback "falls kein Gesicht erkannt wurde"); bei mehreren
    Kandidaten derselben Art gewinnt die groesste Bounding-Box-Flaeche (Prominenz-Mass, konsistent
    mit der in ADR 0022 Punkt 1 fuer den Tier-Score gewaehlten Flaechen-Gewichtung)."""
    if faces:
        return _largest_by_area(faces)
    if animals:
        return _largest_by_area(animals)
    return None


def compute_golden_ratio_score(
    faces: list[FaceBoundingBox], animals: Sequence[SubjectBoxLike] = ()
) -> float:
    """`goldener_schnitt`-Kriterium (Spec 0038): reine geometrische Heuristik ohne eigenes
    ML-Modell, wiederverwendet ausschliesslich Positionsdaten aus bereits vorhandenen Detektionen
    (`detect_person`/eine kuenftige Tier-Erkennung, ADR 0022 Punkt 4) - kein neuer
    Bildverarbeitungsschritt. Bewertet, wie nah das primaere Subjekt (siehe
    _select_primary_subject) an einem der vier Drittel-Schnittpunkte liegt, invers auf [0, 1]
    normiert ueber _GOLDEN_RATIO_MAX_DISTANCE. Horizont-Linien-Erkennung ist bewusst nicht
    umgesetzt (Out-of-Scope der Spec: "keine neuen Bildverarbeitungsschritte fuer die
    Kompositions-Analyse")."""
    subject = _select_primary_subject(faces, animals)
    if subject is None:
        # Dokumentierter, niedriger (nicht neutraler) Fallback-Wert (Akzeptanzkriterium der Spec)
        # - ohne erkennbares Subjekt gibt es kein Kompositions-Signal; 0.0 statt eines
        # "neutralen" 0.5 vermeidet, ein diesbezueglich nicht messbares Foto positiv zu werten.
        # Kein Fehler/keine Exception (bewusste Entscheidung, kein neuer Bildverarbeitungsschritt
        # wie eine Horizont-Erkennung wird dafuer nachgerüstet).
        return 0.0
    distance = min(
        math.sqrt((subject.x_center - tx) ** 2 + (subject.y_center - ty) ** 2)
        for tx, ty in _GOLDEN_RATIO_THIRD_POINTS
    )
    return max(0.0, min(1.0, 1.0 - distance / _GOLDEN_RATIO_MAX_DISTANCE))


def compute_golden_ratio(
    image: Image.Image, face_detector: FaceDetectorLike, animal_detector: ObjectDetectorLike
) -> float:
    """Registrierte `goldener_schnitt`-Kriterien-Funktion: ruft detect_person/detect_animals
    WIEDER auf, statt Erkennung neu zu implementieren (Akzeptanzkriterium der Spec:
    "Wiederverwendungsnachweis ... ueber Spy/Aufrufzaehler statt Reimplementierung", siehe
    test_criteria.py::TestComputeGoldenRatioReusesDetection). worker.py::run_criterion_scoring
    ruft diese Funktion bewusst NICHT direkt auf, sondern verwendet die dort ohnehin fuer
    content_people/tier bereits berechneten Detektionslisten weiter (compute_golden_ratio_score
    direkt) - ein zusaetzlicher detect()-Aufruf pro Foto und Detektortyp waere angesichts des in
    ADR 0022 dokumentierten Compute-Overhead-Risikos unnoetig. Diese Funktion bleibt trotzdem als
    eigenstaendig test- und aufrufbare Einheit bestehen (z.B. fuer einen isolierten
    goldener_schnitt-Nachtrag-Lauf)."""
    faces = detect_person(image, face_detector)
    animals = detect_animals(image, animal_detector)
    return compute_golden_ratio_score(faces, animals)


def compute_tier_score(animals: Sequence[AnimalDetection]) -> float:
    """`tier`-Kriterium (ADR 0022 Punkt 1): Score = Konfidenz des PROMINENTESTEN erkannten Tieres
    (bereits in [0, 1], da detect_animals nur oberhalb von ANIMAL_DETECTION_CONFIDENCE_THRESHOLD
    liefert). Aggregationsregel bei mehreren erkannten Tieren (Akzeptanzkriterium der Spec: "muss
    dokumentiert UND getestet sein, keine stillschweigende Auswahl") - die groesste Bounding-Box-
    Flaeche gewinnt, NICHT die hoechste Konfidenz: ein kleines, aber sehr sicher erkanntes Tier am
    Bildrand soll nicht automatisch ueber ein grossflaechig im Bild praesentes Tier mit etwas
    niedrigerer Konfidenz gewinnen (konsistent mit der Subjekt-Auswahl in
    _select_primary_subject/compute_golden_ratio_score)."""
    if not animals:
        return 0.0
    return _largest_by_area(animals).confidence


# Schwelle, ab der content_people als "Gesicht erkannt" gilt (compute_content_people liefert nur
# 0.0/1.0, 0.5 trennt beide Faelle eindeutig).
_CONTENT_PEOPLE_DETECTED_THRESHOLD = 0.5

CATEGORY_PEOPLE = "people"
CATEGORY_LANDSCAPE = "landscape"
CATEGORY_DETAIL = "detail"


def derive_category_key(criterion_values: dict[str, float]) -> str:
    """Deterministische Prioritaetskette (Akzeptanzkriterium der Spec, analog zur bisherigen
    classify_category-Kette): Menschen erkannt -> "people"; sonst hoher Uniform-Flaechen-Anteil ->
    "landscape"; sonst -> "detail" (Fallback). Jetzt datengetrieben aus bereits berechneten
    Kriterien-Werten statt eines hart codierten Einzelaufrufs - fehlt ein Kriterium (best-effort
    fehlgeschlagene Berechnung), faellt die Kette einfach auf die naechste Stufe durch, kein
    Crash."""
    if criterion_values.get("content_people", 0.0) >= _CONTENT_PEOPLE_DETECTED_THRESHOLD:
        return CATEGORY_PEOPLE
    if criterion_values.get("content_landscape", 0.0) >= LANDSCAPE_UNIFORM_FRACTION_THRESHOLD:
        return CATEGORY_LANDSCAPE
    return CATEGORY_DETAIL
