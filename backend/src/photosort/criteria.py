from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from photosort.classification import (
    FaceDetectorLike,
    LANDSCAPE_UNIFORM_FRACTION_THRESHOLD,
    compute_uniform_area_fraction,
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


def compute_content_people(image: Image.Image, detector: FaceDetectorLike) -> float:
    """`content_people`-Kriterium (Akzeptanzkriterium der Spec: mind. zwei Inhalts-Kriterien,
    wiederverwendet aus classification.py). Score-Grundlage bleibt `bool(detect_person(...))`
    (Vorgriffs-Ergaenzung der Spec: detect_person liefert seit dieser Spec zwar bereits
    FaceBoundingBox-Listen fuer die kuenftige Goldener-Schnitt-Kriterien-Spec 0038, funktional
    aendert sich fuer dieses Kriterium hier nichts)."""
    return 1.0 if detect_person(image, detector) else 0.0


def compute_content_landscape(image: Image.Image) -> float:
    """`content_landscape`-Kriterium: der Uniform-Flaechen-Anteil (classification.py::
    compute_uniform_area_fraction) ist bereits auf [0, 1] normiert, "hoeher = flaechiger/eher
    Landschaft" - keine weitere Transformation noetig."""
    return compute_uniform_area_fraction(image)


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
