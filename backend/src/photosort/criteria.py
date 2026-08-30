from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from photosort.classification import (
    LANDSCAPE_UNIFORM_FRACTION_THRESHOLD,
    SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD,
    AnimalDetection,
    FaceBoundingBox,
    FaceDetectorLike,
    FaceOrientation,
    SceneLabel,
    compute_symmetry_score,
    compute_uniform_area_fraction,
    detect_person,
)
from photosort.landmark import LandmarkDetection
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
    # specs/features/0045-kategorien-aus-statistiken-ableiten.md, decisions/0023-dynamische-
    # kategorie-ableitung-aus-kriterien-haeufigkeit.md: Kategorie-Faehigkeit ist ein reines
    # Registry-Attribut statt einer im Code gepflegten Prioritaetskette. Invariante (durch einen
    # eigenen Registry-Test erzwungen): category_eligible == (category_presence_threshold is not
    # None) - reine Qualitaetskriterien (sharpness/exposure/goldener_schnitt/aesthetics) behalten
    # den Default False/None und koennen nie eine Kategorie bilden.
    category_eligible: bool = False
    category_presence_threshold: float | None = None


# Schwelle, ab der content_people als "Gesicht erkannt" gilt (compute_content_people liefert nur
# 0.0/1.0, 0.5 trennt beide Faelle eindeutig) - zugleich die category_presence_threshold dieses
# Kriteriums (ADR 0023, Punkt 2: Wiederverwendung bestehender Konstanten, keine neue Kalibrierung).
_CONTENT_PEOPLE_DETECTED_THRESHOLD = 0.5

# Presence-Schwellen fuer tier/gebaeude (ADR 0023, Punkt 2): beide Scores sind entweder exakt 0.0
# (nichts erkannt) oder liegen bereits oberhalb der jeweiligen Detektor-eigenen
# Konfidenzschwelle (ANIMAL_DETECTION_CONFIDENCE_THRESHOLD/SCENE_CLASSIFICATION_CONFIDENCE_
# THRESHOLD, classification.py) - diese Konstanten trennen nur "nichts erkannt" von "irgendetwas
# erkannt", keine zweite inhaltliche Kalibrierung.
_TIER_CATEGORY_PRESENCE_THRESHOLD = 0.01
_GEBAEUDE_CATEGORY_PRESENCE_THRESHOLD = 0.01

# specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR decisions/0025-cloud-
# landmark-erkennung.md Punkt 2: Confidence-Schwelle des Vision-LLM, ab der ein Foto als
# "Sehenswuerdigkeit erkannt" gilt - zugleich Vorfilterungs-Schwelle fuer content_landscape/
# gebaeude in worker.py::run_criterion_scoring (Wiederverwendung derselben Registry-Werte).
# Dokumentiert-unkalibriert (gleiche Klasse wie SHARPNESS_NORMALIZATION_CEILING/
# LANDSCAPE_UNIFORM_FRACTION_THRESHOLD, kein Fotokorpus im Repo zur Kalibrierung) - ADR 0025
# benennt zusaetzlich ein bekanntes, beobachtetes Ueberidentifikations-Risiko (siehe ADR Punkt 1),
# gegen das diese Schwelle die strukturelle, aber ggf. nicht ausreichende Gegenmassnahme ist.
_LANDMARK_CATEGORY_PRESENCE_THRESHOLD = 0.5

CRITERIA_REGISTRY: dict[str, CriterionDefinition] = {
    "sharpness": CriterionDefinition("sharpness", "Schärfe", CriterionSource.LOCAL_HEURISTIC),
    "exposure": CriterionDefinition("exposure", "Belichtung", CriterionSource.LOCAL_HEURISTIC),
    "content_people": CriterionDefinition(
        "content_people",
        "Menschen erkannt",
        CriterionSource.LOCAL_ML,
        category_eligible=True,
        category_presence_threshold=_CONTENT_PEOPLE_DETECTED_THRESHOLD,
    ),
    "content_landscape": CriterionDefinition(
        "content_landscape",
        "Landschaft/Flächig",
        CriterionSource.LOCAL_HEURISTIC,
        category_eligible=True,
        category_presence_threshold=LANDSCAPE_UNIFORM_FRACTION_THRESHOLD,
    ),
    # specs/features/0038-vier-zusaetzliche-kriterien-tier-gebaeude-schnitt-aesthetik.md ab hier:
    "tier": CriterionDefinition(
        "tier",
        "Tier erkannt",
        CriterionSource.LOCAL_ML,
        category_eligible=True,
        category_presence_threshold=_TIER_CATEGORY_PRESENCE_THRESHOLD,
    ),
    "goldener_schnitt": CriterionDefinition(
        "goldener_schnitt", "Goldener Schnitt", CriterionSource.LOCAL_HEURISTIC
    ),
    "gebaeude": CriterionDefinition(
        "gebaeude",
        "Gebäude erkannt",
        CriterionSource.LOCAL_ML,
        category_eligible=True,
        category_presence_threshold=_GEBAEUDE_CATEGORY_PRESENCE_THRESHOLD,
    ),
    "aesthetics": CriterionDefinition("aesthetics", "Ästhetik", CriterionSource.LOCAL_ML),
    # specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md ab hier: drei
    # weitere, davon unabhaengige Kompositions-Ranking-Signale (analog goldener_schnitt/
    # aesthetics) - alle drei category_eligible=False (reine Ranking-Signale, keine neuen
    # Kuratierungs-Kategorien, ADR 0026).
    "symmetrie": CriterionDefinition(
        "symmetrie", "Symmetrie", CriterionSource.LOCAL_HEURISTIC
    ),
    "horizont": CriterionDefinition(
        "horizont", "Horizont-Neigung", CriterionSource.LOCAL_HEURISTIC
    ),
    "freiraum": CriterionDefinition(
        "freiraum", "Freiraum/Fluchtrichtung", CriterionSource.LOCAL_ML
    ),
    # specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR 0025: erste
    # tatsaechlich produktive CriterionSource.CLOUD-Zeile im Kriterien-Scoring-Pfad.
    "landmark": CriterionDefinition(
        "landmark",
        "Sehenswürdigkeit",
        CriterionSource.CLOUD,
        category_eligible=True,
        category_presence_threshold=_LANDMARK_CATEGORY_PRESENCE_THRESHOLD,
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
    """`content_people`-Kriterium (Akzeptanzkriterium der Spec 0037: mind. zwei Inhalts-Kriterien,
    wiederverwendet aus classification.py). Score-Grundlage bleibt `bool(detect_person(...))`
    (Vorgriffs-Ergaenzung der Spec 0037: detect_person liefert seit dieser Spec zwar bereits
    FaceBoundingBox-Listen fuer die kuenftige Goldener-Schnitt-Kriterien-Spec 0038, funktional
    aendert sich fuer dieses Kriterium hier nichts).

    Hinweis (Spec 0038, Review-Nachtrag 2026-08-15): worker.py::_compute_content_criteria ruft
    diese Funktion seit Spec 0038 NICHT mehr direkt auf, sondern detect_person +
    content_people_from_faces getrennt (um die bereits erkannten faces auch fuer goldener_schnitt
    wiederzuverwenden, ohne detect_person zweimal aufzurufen). compute_content_people bleibt
    trotzdem als eigenstaendige, weiterhin getestete Einheit bestehen (Spec-0037-Vertrag, nicht
    Teil des Scopes dieser Spec, hier entfernt zu werden) - reiner Delegations-Wrapper um
    content_people_from_faces, kein doppelt gepflegter Logikpfad."""
    return content_people_from_faces(detect_person(image, detector))


def compute_content_landscape(image: Image.Image) -> float:
    """`content_landscape`-Kriterium: der Uniform-Flaechen-Anteil (classification.py::
    compute_uniform_area_fraction) ist bereits auf [0, 1] normiert, "hoeher = flaechiger/eher
    Landschaft" - keine weitere Transformation noetig."""
    return compute_uniform_area_fraction(image)


def compute_symmetrie_score(image: Image.Image) -> float:
    """`symmetrie`-Kriterium (specs/features/0048-kompositions-kriterien-symmetrie-horizont-
    freiraum.md, ADR 0026 Punkt 1): reiner Namens-/Modul-Wrapper um classification.py::
    compute_symmetry_score (bereits auf [0, 1] normiert) - kein eigener Algorithmus hier, analog
    compute_content_landscape -> compute_uniform_area_fraction."""
    return compute_symmetry_score(image)


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
    Kompositions-Analyse").

    Bewusst eine reine Funktion OHNE eigenen detect_person/detect_animals-Aufruf (anders als ein
    frueherer Entwurf mit einer zusaetzlichen `compute_golden_ratio(image, ...)`-Wrapper-Funktion,
    Review-Fund: totes Produktionscode-Fragment, siehe Commit-Historie) - worker.py::
    _compute_content_criteria ruft detect_person/detect_animals bereits fuer content_people/tier
    auf und reicht die Ergebnislisten hier direkt durch (ein zusaetzlicher detect()-Aufruf pro
    Foto waere angesichts des in ADR 0022 dokumentierten Compute-Overhead-Risikos unnoetig). Der
    Wiederverwendungsnachweis (Akzeptanzkriterium der Spec: "Spy/Aufrufzaehler statt
    Reimplementierung") liegt deshalb konsequent auf Worker-Integrationsebene, siehe
    test_worker_criterion_scoring.py::
    test_detect_person_and_detect_animals_are_each_called_at_most_once_per_photo."""
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


# Kuratierte Allow-Liste architekturbezogener ImageNet-1k-Klassen (ADR 0022 Punkt 2) - die acht
# im Architektur-Abschnitt der Spec 0038 explizit genannten Klassen plus eine kleine, ebenfalls
# gut belegte Erweiterung ("u.a." in der Spec) verwandter ImageNet-Architektur-Synsets. Technische
# Detailentscheidung der Umsetzung (die Spec selbst laesst die genaue Liste bewusst offen) - siehe
# Modul-Kommentar in classification.py fuer die Begruendung, warum die Filterung HIER und nicht in
# classify_scene selbst passiert. Dokumentierte, bewusst akzeptierte Luecke (AK-Pflicht der Spec,
# ADR 0022 Punkt 2): ImageNet hat kaum Innenraum-Klassen, `living_room`/`kitchen`/`office` werden
# strukturell nicht erkannt - nur Aussenarchitektur wird zuverlaessig erfasst.
#
# BEFUND (developer, 2026-08-30, bei der fuer LANDSCAPE_SCENE_CATEGORIES unten verpflichtenden
# Verifikation gegen die Label-Datei des gebuendelten Modells aufgefallen, siehe dort): die
# Label-Datei schreibt mehrteilige Klassennamen mit LEERZEICHEN, nicht mit Unterstrich - die vier
# Eintraege "bell_cote"/"suspension_bridge"/"triumphal_arch" (Label-Datei: "bell cote",
# "suspension bridge", "triumphal arch") und "lighthouse" (Label-Datei: "beacon") koennen deshalb
# nie matchen. Bewusst in dieser Spec NICHT korrigiert: specs/features/0217 AK2 verlangt
# ausdruecklich, dass sich das gebaeude-Verhalten durch diese Aenderung NICHT verschiebt - eine
# Korrektur waere eine eigenstaendige Verhaltensaenderung ausserhalb des Story-Scopes und gehoert
# in ein eigenes Ticket.
ARCHITECTURE_CATEGORIES = frozenset(
    {
        "church",
        "castle",
        "palace",
        "dome",
        "library",
        "lighthouse",
        "barn",
        "mosque",
        "monastery",
        "bell_cote",
        "boathouse",
        "obelisk",
        "stupa",
        "triumphal_arch",
        "viaduct",
        "suspension_bridge",
    }
)


def compute_gebaeude_score(labels: Sequence[SceneLabel]) -> float:
    """`gebaeude`-Kriterium (ADR 0022 Punkt 2): Score = Konfidenz des besten Treffers INNERHALB
    der ARCHITECTURE_CATEGORIES-Allow-Liste, 0.0 falls keiner der uebergebenen `labels` in der
    Allow-Liste enthalten ist - auch bei hoher Modell-Konfidenz einer nicht-architekturbezogenen
    Kategorie (Akzeptanzkriterium der Spec 0038: "Nachweis, dass tatsaechlich die Allow-Liste
    filtert und nicht nur die rohe Modell-Konfidenz durchgereicht wird").

    specs/features/0217, ADR 0046 Punkt 1 (verpflichtend, sonst stille Verhaltensaenderung):
    zusaetzlich zur Allow-Liste wird die inhaltliche Konfidenzschwelle
    SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD (0.5) HIER explizit durchgesetzt. classify_scene
    liefert seit dieser Spec bereits ab der niedrigeren SCENE_LABEL_MIN_CONFIDENCE (0.2), damit
    compute_landschaft_score den fuer natuerliche Szenen noetigen Spielraum bekommt - ohne diesen
    Filter wuerde das gebaeude-Kriterium diese Absenkung stillschweigend mit uebernehmen."""
    allowed = [
        label
        for label in labels
        if label.category in ARCHITECTURE_CATEGORIES
        and label.confidence >= SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD
    ]
    if not allowed:
        return 0.0
    return max(label.confidence for label in allowed)


# Kuratierte Allow-Liste natuerlicher ImageNet-1k-Szenenklassen (specs/features/0217, ADR 0046
# Punkt 1) - dasselbe Muster wie ARCHITECTURE_CATEGORIES oben, ebenfalls ohne modell-ladenden
# Test.
#
# VERIFIZIERT (developer, 2026-08-30, einmalige Pflicht laut ADR 0046 Punkt 1): die exakte
# Schreibweise stammt aus der im gebuendelten Modell-Asset selbst mitgelieferten Label-Datei
# `labels_without_background.txt` in backend/src/photosort/assets/efficientnet_lite0.tflite (die
# .tflite-Datei enthaelt ihre Metadaten als angehaengtes ZIP-Archiv). Die zehn hier gelisteten
# Klassen sind die Indizes 970 und 972-980 der ImageNet-1k-Label-Liste, also GENAU die
# natuerlichen Szenenklassen des Vokabulars. Schreibweise mit LEERZEICHEN, nicht mit Unterstrich
# ("coral reef", nicht "coral_reef") - so steht es in der Label-Datei, und genau diesen String
# liefert mediapipe als `category_name`.
#
# Dokumentierte, bewusst akzeptierte Luecke (ADR 0046 Punkt 1, AK-Pflicht): ImageNet-1k kennt
# KEINE Klassen fuer Wald, Wiese oder Feld - solche Landschaften werden strukturell nicht als
# `landschaft` erkannt und landen im "nicht erkannt"-Zustand. Eine Nachkalibrierung bleibt eine
# reine Listen-/Konstanten-Aenderung ohne Architektur-Eingriff.
LANDSCAPE_SCENE_CATEGORIES = frozenset(
    {
        "alp",
        "cliff",
        "coral reef",
        "geyser",
        "lakeside",
        "promontory",
        "sandbar",
        "seashore",
        "valley",
        "volcano",
    }
)

# Inhaltliche Konfidenzschwelle des landschaft-Kriteriums (ADR 0046 Punkt 1) - bewusst deutlich
# niedriger als SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD (0.5, gebaeude): ein Landschaftsfoto
# verteilt seine Modellkonfidenz typischerweise ueber mehrere benachbarte Szenenklassen ("alp"/
# "valley"/"promontory" am selben Bergpanorama), eine Architektur-Klasse dagegen konzentriert sie.
# Dokumentierte, nicht gegen einen Fotokorpus kalibrierte Setzung (gleiche Klasse wie
# CATEGORY_ACTIVE_THRESHOLD_FRACTION), austauschbar ohne Architektur-Aenderung.
LANDSCHAFT_LABEL_MIN_CONFIDENCE = 0.25


def compute_landschaft_score(labels: Sequence[SceneLabel]) -> float:
    """`landschaft`-Kriterium (specs/features/0217, ADR 0046 Punkt 1): Score = Konfidenz des
    besten Labels, das SOWOHL in LANDSCAPE_SCENE_CATEGORIES liegt ALS AUCH
    >= LANDSCHAFT_LABEL_MIN_CONFIDENCE ist, sonst 0.0.

    Reine Funktion ohne eigenen classify_scene-Aufruf (Trennung analog compute_gebaeude_score/
    compute_tier_score): worker.py::_compute_content_criteria ruft classify_scene GENAU EINMAL
    pro Foto auf und reicht dieselbe Label-Liste an compute_gebaeude_score UND diese Funktion
    weiter - dasselbe Wiederverwendungsmuster wie detect_person -> content_people +
    goldener_schnitt (Spec 0038). Der Ein-Aufruf-Nachweis (Akzeptanzkriterium AK8 der Spec 0217:
    keine zusaetzlichen Kosten pro Foto) liegt deshalb auf Worker-Integrationsebene, siehe
    test_worker_criterion_scoring.py."""
    allowed = [
        label
        for label in labels
        if label.category in LANDSCAPE_SCENE_CATEGORIES
        and label.confidence >= LANDSCHAFT_LABEL_MIN_CONFIDENCE
    ]
    if not allowed:
        return 0.0
    return max(label.confidence for label in allowed)


def is_landmark_candidate(values: dict[str, float]) -> bool:
    """Reine Schwellenwert-Pruefung fuer die landmark-Vorfilterung (specs/features/0058-cloud-
    vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-fehler-persistierung.md
    Punkt 4) - extrahiert aus worker.py::_select_landmark_candidates (dort bleibt nur noch das
    Skip-bereits-gescorter-Fotos-Verhalten, worker-spezifisch). Ein Foto ist Kandidat, wenn
    content_landscape ODER gebaeude die jeweils registrierte category_presence_threshold erreicht
    (`>=`, inklusiv, dieselben Registry-Werte wie derive_active_categories/derive_category_key).
    Fehlende Werte gelten als 0.0 (kein Sonderfall, analog derive_active_categories). Von
    _select_landmark_candidates (Live-Lauf) UND api/photos.py::_cloud_vision_status_out
    (Read-Time-Ableitung) gemeinsam genutzt - verhindert ein Auseinanderlaufen beider Stellen bei
    einer kuenftigen Schwellenwert-Aenderung."""
    landscape_threshold = CRITERIA_REGISTRY["content_landscape"].category_presence_threshold
    gebaeude_threshold = CRITERIA_REGISTRY["gebaeude"].category_presence_threshold
    assert landscape_threshold is not None
    assert gebaeude_threshold is not None
    return (
        values.get("content_landscape", 0.0) >= landscape_threshold
        or values.get("gebaeude", 0.0) >= gebaeude_threshold
    )


def compute_landmark_score(detection: LandmarkDetection) -> float:
    """`landmark`-Kriterium (specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md,
    ADR decisions/0025-cloud-landmark-erkennung.md Punkt 2): reine, synchrone, netzwerkfreie
    Funktion (Akzeptanzkriterium der Spec) - der eigentliche Netzwerk-/Cloud-Aufruf lebt
    ausschliesslich in landmark.py, NICHT hier. Kein identifizierter Name -> 0.0 (kein
    Sehenswuerdigkeits-Signal, unabhaengig von einer theoretisch trotzdem gelieferten confidence -
    ohne Namen ist der Wert bedeutungslos). Sonst die vom Vision-LLM gelieferte Konfidenz, auf
    [0, 1] geklemmt (defensiv, falls das Modell je einen Wert ausserhalb des Bereichs liefert)."""
    if detection.name is None:
        return 0.0
    return max(0.0, min(1.0, detection.confidence))


# specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md, ADR 0026 Punkt 3:
# Deadzone um einen frontalen Blick (Yaw nahe 0) - kein klares Richtungssignal, ein nahezu
# frontaler Blick sagt nichts darueber aus, ob rechts oder links mehr Freiraum "in Blickrichtung"
# noetig waere. Unkalibriert dokumentiert (gleiche Klasse wie SHARPNESS_NORMALIZATION_CEILING/
# LANDSCAPE_UNIFORM_FRACTION_THRESHOLD, kein Fotokorpus im Repo zur Kalibrierung).
FREIRAUM_YAW_DEADZONE_DEGREES = 10.0


def compute_freiraum_score(orientation: FaceOrientation | None) -> float:
    """`freiraum`-Kriterium (ADR 0026 Punkt 3): reine Score-Berechnung aus einer bereits
    vorhandenen FaceOrientation, OHNE eigenen detect_face_orientation-Aufruf (Trennung analog
    compute_tier_score/compute_gebaeude_score) - worker.py::_compute_content_criteria ruft
    detect_face_orientation genau einmal auf und reicht das Ergebnis hier durch.

    Drei bewusst unterschiedliche Fallback-Werte (ADR 0026, "Begruendung": "bedeutet die
    Abwesenheit eines Signals ein schlechtes Foto, oder nur ein nicht messbares?" - jeder Fall
    einzeln beantwortet, kein einheitliches Schema):
    1. Kein Gesicht erkannt (`orientation is None`) -> 0.0 (niedrig, NICHT neutral) - analog
       goldener_schnitt: dieses Kriterium bewertet fundamental die Rahmung eines Subjekts, ohne
       jedes Subjekt gibt es keinen positiven Kompositionswert.
    2. Nahezu frontaler Blick (`|yaw| < FREIRAUM_YAW_DEADZONE_DEGREES`) -> 0.5 (neutral) - kein
       klares Richtungssignal. Der Vergleich ist bewusst `<`, NICHT `<=` (AK der Spec 0048): Yaw
       EXAKT an der Deadzone-Grenze zaehlt als AUSSERHALB, nicht als neutral.
    3. Sonst: `score = clip(looking_space / (looking_space + opposite_space), 0, 1)` -
       `looking_space` ist der verfuegbare Bildraum auf der Seite, der das Gesicht zugewandt ist
       (Vorzeichenkonvention siehe FaceOrientation.yaw_degrees-Docstring in classification.py:
       positiver Yaw -> Blick Richtung steigendem x -> looking_space = 1 - max_x, negativer Yaw ->
       looking_space = min_x), `opposite_space` die jeweilige Gegenseite. Zusaetzlicher 0-Schutz
       (AK der Spec 0048, gleiche Argumentationsklasse wie die Deadzone): fuellt das Gesicht die
       VOLLE Bildbreite (`min_x == 0`, `max_x == 1`), sind beide Raeume 0 - neutraler Fallback
       0.5 statt ZeroDivisionError."""
    if orientation is None:
        return 0.0
    if abs(orientation.yaw_degrees) < FREIRAUM_YAW_DEADZONE_DEGREES:
        return 0.5

    if orientation.yaw_degrees > 0:
        looking_space = 1.0 - orientation.max_x
        opposite_space = orientation.min_x
    else:
        looking_space = orientation.min_x
        opposite_space = 1.0 - orientation.max_x

    total_space = looking_space + opposite_space
    if total_space <= 0:
        return 0.5
    return max(0.0, min(1.0, looking_space / total_space))


CATEGORY_DETAIL = "detail"

# Anteil der Kandidaten-Fotos eines Laufs, ab dem ein category_eligible-Kriterium als "aktiv" gilt
# (ADR 0023, Punkt 2) - 15%, hoch genug um reines Rauschen (2-3 Zufallstreffer) in einem
# mittelgrossen Projekt zu vermeiden, niedrig genug um einen thematisch relevanten, aber nicht
# dominanten Anteil zuverlaessig eine eigene Kategorie ausloesen zu lassen. Dokumentierte, nicht
# gegen einen echten Fotokorpus kalibrierte Setzung (gleiche Klasse wie SHARPNESS_NORMALIZATION_
# CEILING/LANDSCAPE_UNIFORM_FRACTION_THRESHOLD), austauschbar ohne Architektur-Aenderung.
CATEGORY_ACTIVE_THRESHOLD_FRACTION = 0.15


# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, decisions/0032-
# remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 1: gleiche Konstanten-Klasse wie
# _TIER_CATEGORY_PRESENCE_THRESHOLD/_GEBAEUDE_CATEGORY_PRESENCE_THRESHOLD - ein vom Vision-LLM
# gelieferter Wert ist bereits eine "erkannt"-Aussage, dieser Schwellwert trennt nur "vorhanden"
# von "fehlender Eintrag" (candidate_values.get(key, 0.0)), keine zweite Konfidenzkalibrierung.
DYNAMIC_LABEL_PRESENCE_THRESHOLD = 0.01


def derive_active_categories(
    candidate_values: dict[int, dict[str, float]],
    threshold_fraction: float = CATEGORY_ACTIVE_THRESHOLD_FRACTION,
    dynamic_keys: frozenset[str] = frozenset(),
) -> frozenset[str]:
    """Reine Aggregationsfunktion (Akzeptanzkriterium der Spec 0045): ermittelt EINMAL pro Lauf,
    projektweit ueber ALLE Kandidaten-Fotos (nicht pro cluster_key, ADR 0023 Punkt 2), welche
    category_eligible-Kriterien im jeweiligen Lauf ueberhaupt eine eigene Kategorie bilden duerfen.
    Ein Kriterium gilt als aktiv, wenn der Anteil der Kandidaten-Fotos, deren Wert die jeweilige
    category_presence_threshold erreicht/ueberschreitet (inklusiver Vergleich in beide
    Richtungen), >= threshold_fraction ist. Fehlende Werte fuer einzelne Fotos (best-effort-
    Kriterium fuer dieses Foto nicht berechenbar) zaehlen als "nicht vorhanden", kein Sonderfall.
    Kein DB-/IO-Zugriff, keine Exception bei einem leeren Kandidatenpool.

    `dynamic_keys` (specs/features/0055, ADR 0032 Punkt 1): zur Laufzeit entdeckte Remote-Label-
    Pseudo-Keys (`f"remote:{canonical_key}"`) - werden an derselben Haeufigkeitsschwelle gemessen
    wie die registrierten lokalen Kriterien, aber gegen DYNAMIC_LABEL_PRESENCE_THRESHOLD statt
    einer registrierten category_presence_threshold (es gibt keine CriterionDefinition fuer sie).
    Default `frozenset()` - bestehende Aufrufer/Tests ohne dynamic_keys bleiben unveraendert."""
    total = len(candidate_values)
    if total == 0:
        return frozenset()

    active: set[str] = set()
    for criterion_key, definition in CRITERIA_REGISTRY.items():
        if not definition.category_eligible or definition.category_presence_threshold is None:
            continue
        threshold = definition.category_presence_threshold
        present_count = sum(
            1
            for values in candidate_values.values()
            if values.get(criterion_key, 0.0) >= threshold
        )
        if (present_count / total) >= threshold_fraction:
            active.add(criterion_key)

    for key in dynamic_keys:
        present_count = sum(
            1
            for values in candidate_values.values()
            if values.get(key, 0.0) >= DYNAMIC_LABEL_PRESENCE_THRESHOLD
        )
        if (present_count / total) >= threshold_fraction:
            active.add(key)

    return frozenset(active)


def derive_category_key(
    criterion_values: dict[str, float],
    active_criteria: frozenset[str],
    dynamic_keys: frozenset[str] = frozenset(),
) -> str:
    """Weist EIN Foto einer Kategorie zu (Akzeptanzkriterium der Spec 0045, ADR 0023 Punkt 3):
    prueft nur noch gegen die fuer den Lauf ermittelte aktive Menge (derive_active_categories),
    nicht mehr gegen eine fest codierte Prioritaetskette. Erfuellt ein Foto mehrere aktive
    Kriterien gleichzeitig (Wert >= der jeweiligen category_presence_threshold), gewinnt der
    hoechste normierte Score; bei exakt gleichem Score entscheidet die alphabetische Reihenfolge
    des VOLLEN (inkl. "remote:"-Praefix) criterion_key (deterministisch, testbar). Kein erfuelltes
    aktives Kriterium -> Catch-all CATEGORY_DETAIL. category_key wird generisch aus dem
    gewinnenden criterion_key gebildet (`removeprefix("content_")`, bzw. symmetrisch
    `removeprefix("remote:")` fuer dynamische Keys, ADR 0032 Punkt 1) - liefert fuer
    Bestandskriterien identische Werte wie bisher ("people"/"landscape"), fuer tier/gebaeude/
    Remote-Label automatisch die richtigen Keys, ohne manuelles Mapping (ADR 0023 Punkt 4).

    `dynamic_keys` (specs/features/0055, ADR 0032 Punkt 1): Pseudo-Keys aus `active_criteria`, die
    NICHT in CRITERIA_REGISTRY stehen - werden gegen DYNAMIC_LABEL_PRESENCE_THRESHOLD statt einer
    registrierten category_presence_threshold geprueft. Default `frozenset()` - bestehende
    Aufrufer/Tests ohne dynamic_keys bleiben unveraendert."""
    qualifying: list[str] = []
    for criterion_key in active_criteria:
        if criterion_key in dynamic_keys:
            threshold = DYNAMIC_LABEL_PRESENCE_THRESHOLD
        else:
            definition = CRITERIA_REGISTRY.get(criterion_key)
            if definition is None or definition.category_presence_threshold is None:
                continue
            threshold = definition.category_presence_threshold
        value = criterion_values.get(criterion_key, 0.0)
        if value >= threshold:
            qualifying.append(criterion_key)

    if not qualifying:
        return CATEGORY_DETAIL

    winner = min(qualifying, key=lambda key: (-criterion_values.get(key, 0.0), key))
    if winner.startswith("remote:"):
        return winner.removeprefix("remote:")
    return winner.removeprefix("content_")
