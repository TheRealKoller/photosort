from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from photosort.classification import (
    ANIMAL_CATEGORIES,
    SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD,
    FaceBoundingBox,
    FaceDetectorLike,
    FaceOrientation,
    ObjectDetection,
    SceneLabel,
    compute_symmetry_score,
    compute_uniform_area_fraction,
    detect_person,
)
from photosort.landmark import LandmarkDetection
from photosort.models import CriterionSource

# Kriterien-Registry und Normierungsfunktionen. Eine Registry-Erweiterung ist der einzige
# Aufwand für ein neues Kriterium - keine Migration.


@dataclass(frozen=True)
class CriterionDefinition:
    key: str
    display_name: str
    source: CriterionSource
    # Kategorie-Fähigkeit ist ein reines Registry-Attribut statt einer im Code gepflegten
    # Prioritätskette. Invariante, durch einen eigenen Registry-Test erzwungen:
    # category_eligible == (category_presence_threshold is not None) - reine
    # Qualitätskriterien (sharpness/exposure/goldener_schnitt/aesthetics) behalten den
    # Default False/None und können nie eine Kategorie bilden.
    category_eligible: bool = False
    category_presence_threshold: float | None = None
    # KEIN zweites Prioritätsattribut hier: welche Kategorie bei mehreren Kandidaten
    # gewinnt, entscheidet ausschließlich die feste Vorrangreihenfolge in
    # categories.py::CATEGORY_REGISTRY - ein Attribut daneben wäre eine konkurrierende,
    # driftende Quelle derselben Aussage.


# Schwelle, ab der content_people als "Gesicht erkannt" gilt (compute_content_people liefert
# nur 0.0/1.0, 0.5 trennt beide Fälle eindeutig) - zugleich die category_presence_threshold
# dieses Kriteriums: Wiederverwendung einer bestehenden Konstante, keine neue Kalibrierung.
_CONTENT_PEOPLE_DETECTED_THRESHOLD = 0.5

# Presence-Schwellen für tier/gebaeude: beide Scores sind entweder exakt 0.0 (nichts erkannt)
# oder liegen bereits oberhalb der jeweiligen detektoreigenen Konfidenzschwelle
# (classification.py) - diese Konstanten trennen nur "nichts erkannt" von "irgendetwas
# erkannt", sie sind keine zweite inhaltliche Kalibrierung.
_TIER_CATEGORY_PRESENCE_THRESHOLD = 0.01
_GEBAEUDE_CATEGORY_PRESENCE_THRESHOLD = 0.01

# Dieselbe Konstanten-Klasse wie oben - compute_fahrzeug_score/compute_essen_trinken_score
# liefern entweder exakt 0.0 (kein Allow-Listen-Treffer) oder einen Wert oberhalb von
# OBJECT_DETECTION_CONFIDENCE_THRESHOLD.
_FAHRZEUG_CATEGORY_PRESENCE_THRESHOLD = 0.01
_ESSEN_TRINKEN_CATEGORY_PRESENCE_THRESHOLD = 0.01

# Dieselbe Konstanten-Klasse wie oben - compute_landschaft_score liefert entweder exakt 0.0
# (kein Allow-Listen-Treffer über LANDSCHAFT_LABEL_MIN_CONFIDENCE) oder einen Wert oberhalb
# dieser Konfidenzschwelle.
_LANDSCHAFT_CATEGORY_PRESENCE_THRESHOLD = 0.01

# Confidence-Schwelle des Vision-LLM, ab der ein Foto als "Sehenswürdigkeit erkannt" gilt -
# zugleich Vorfilterungs-Schwelle für content_landscape/gebaeude in
# worker.py::run_criterion_scoring. Dokumentiert-unkalibriert (gleiche Klasse wie
# SHARPNESS_NORMALIZATION_CEILING/UNIFORM_TILE_VARIANCE_THRESHOLD, es gibt keinen Fotokorpus
# im Repo zur Kalibrierung). Gegen das bekannte, beobachtete Überidentifikations-Risiko des
# Vision-LLM ist diese Schwelle die strukturelle, aber womöglich nicht ausreichende
# Gegenmaßnahme.
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
    # Reines Ranking-Signal, NICHT kategoriefähig - compute_uniform_area_fraction misst
    # Texturarmut ("Flächigkeit"), keine Landschaft. Die echte, inhaltsbasierte
    # Landschafts-Erkennung liegt im Kriterium "landschaft" unten.
    "content_landscape": CriterionDefinition(
        "content_landscape",
        "Flächigkeit",
        CriterionSource.LOCAL_HEURISTIC,
    ),
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
    # Echte, inhaltsbasierte Landschafts-Erkennung aus DERSELBEN Szenen-Klassifikation wie
    # gebaeude - keine zusätzliche Inferenz, kein neues Modell-Asset.
    "landschaft": CriterionDefinition(
        "landschaft",
        "Landschaft erkannt",
        CriterionSource.LOCAL_ML,
        category_eligible=True,
        category_presence_threshold=_LANDSCHAFT_CATEGORY_PRESENCE_THRESHOLD,
    ),
    # Drei weitere, voneinander unabhängige Kompositions-Ranking-Signale (analog
    # goldener_schnitt/aesthetics) - alle drei category_eligible=False, also reine
    # Ranking-Signale und keine Kuratierungs-Kategorien.
    "symmetrie": CriterionDefinition(
        "symmetrie", "Symmetrie", CriterionSource.LOCAL_HEURISTIC
    ),
    "horizont": CriterionDefinition(
        "horizont", "Horizont-Neigung", CriterionSource.LOCAL_HEURISTIC
    ),
    "freiraum": CriterionDefinition(
        "freiraum", "Freiraum/Fluchtrichtung", CriterionSource.LOCAL_ML
    ),
    # Die einzige CriterionSource.CLOUD-Zeile im Kriterien-Scoring-Pfad.
    "landmark": CriterionDefinition(
        "landmark",
        "Sehenswürdigkeit",
        CriterionSource.CLOUD,
        category_eligible=True,
        category_presence_threshold=_LANDMARK_CATEGORY_PRESENCE_THRESHOLD,
    ),
    # Zwei weitere lokale Inhalts-Kriterien aus DERSELBEN COCO-Detektorausgabe wie `tier` -
    # keine zusätzliche Inferenz, kein neues Modell-Asset.
    "fahrzeug": CriterionDefinition(
        "fahrzeug",
        "Fahrzeug erkannt",
        CriterionSource.LOCAL_ML,
        category_eligible=True,
        category_presence_threshold=_FAHRZEUG_CATEGORY_PRESENCE_THRESHOLD,
    ),
    "essen_trinken": CriterionDefinition(
        "essen_trinken",
        "Essen erkannt",
        CriterionSource.LOCAL_ML,
        category_eligible=True,
        category_presence_threshold=_ESSEN_TRINKEN_CATEGORY_PRESENCE_THRESHOLD,
    ),
}

# Obergrenze fuer die Normierung der unbeschraenkten Laplace-Varianz-Skala (scoring.py::
# compute_sharpness) auf [0, 1] - technische Detailentscheidung der Umsetzung, nicht gegen einen
# echten Fotokorpus kalibriert (gleicher Kalibrierungs-Vorbehalt wie scoring.py::
# SHARPNESS_REJECT_THRESHOLD und classification.py::UNIFORM_TILE_VARIANCE_THRESHOLD). Werte
# darueber werden auf 1.0 geklemmt statt die Skala zu sprengen.
SHARPNESS_NORMALIZATION_CEILING = 200.0


def normalize_sharpness(raw_sharpness: float) -> float:
    """Bildet die unbeschränkte, "höher = schärfer"-Laplace-Varianz (scoring.py::
    compute_sharpness) auf [0, 1] ab - reine In-Memory-Transformation der bereits
    vorhandenen PhotoScore.sharpness-Rohwerte, kein erneuter Bildzugriff."""
    return max(0.0, min(1.0, raw_sharpness / SHARPNESS_NORMALIZATION_CEILING))


def normalize_exposure(raw_exposure: float) -> float:
    """scoring.py::compute_exposure liefert den Anteil geclippter Pixel (0.0 = perfekt belichtet,
    1.0 = vollstaendig geclippt, bereits in [0, 1]) - "hoeher = besser" erfordert eine Invertierung,
    keine Skalen-Transformation."""
    return 1.0 - max(0.0, min(1.0, raw_exposure))


def content_people_from_faces(faces: list[FaceBoundingBox]) -> float:
    """Reine Score-Berechnung aus einer bereits vorhandenen FaceBoundingBox-Liste, OHNE
    eigene Detektion: worker.py::_compute_content_criteria ruft detect_person nur EINMAL
    auf und nutzt das Ergebnis für content_people wie für goldener_schnitt weiter."""
    return 1.0 if faces else 0.0


def compute_content_people(image: Image.Image, detector: FaceDetectorLike) -> float:
    """`content_people`-Kriterium, Score-Grundlage `bool(detect_person(...))`.

    Reiner Delegations-Wrapper um content_people_from_faces, kein zweiter Logikpfad:
    worker.py::_compute_content_criteria ruft diese Funktion NICHT auf, sondern
    detect_person + content_people_from_faces getrennt, um die bereits erkannten faces auch
    für goldener_schnitt zu nutzen. Die Funktion bleibt als eigenständige, getestete
    Einheit bestehen."""
    return content_people_from_faces(detect_person(image, detector))


def compute_content_landscape(image: Image.Image) -> float:
    """`content_landscape`-Kriterium: der Uniform-Flaechen-Anteil (classification.py::
    compute_uniform_area_fraction) ist bereits auf [0, 1] normiert, "hoeher = flaechiger/eher
    Landschaft" - keine weitere Transformation noetig."""
    return compute_uniform_area_fraction(image)


def compute_symmetrie_score(image: Image.Image) -> float:
    """`symmetrie`-Kriterium: reiner Namens-/Modul-Wrapper um
    classification.py::compute_symmetry_score (bereits auf [0, 1] normiert) - kein eigener
    Algorithmus hier, analog compute_content_landscape -> compute_uniform_area_fraction."""
    return compute_symmetry_score(image)


class SubjectBoxLike(Protocol):
    """Schmale strukturelle Schnittstelle, die compute_golden_ratio_score für ein
    Kompositions-Subjekt braucht - sowohl FaceBoundingBox (classification.py) als auch
    ObjectDetection erfüllen sie, ohne dass criteria.py eine harte Abhängigkeit auf den
    Erkennungscode braucht. Als Nur-Lese-Properties (statt einfacher
    Attribut-Annotationen) deklariert, damit auch @dataclass(frozen=True)-Implementierungen
    den Vertrag strukturell erfüllen - mypy --strict wertet einfache Attribut-Annotationen
    in einem Protocol als lese- UND schreibbar, was ein unveränderliches Dataclass-Feld
    nicht erfüllen kann."""

    @property
    def x_center(self) -> float: ...
    @property
    def y_center(self) -> float: ...
    @property
    def width(self) -> float: ...
    @property
    def height(self) -> float: ...


# Die vier Drittel-Schnittpunkte der Drittelregel/des Goldenen Schnitts. Ursprung oben links,
# normiert auf [0, 1] wie FaceBoundingBox.
_GOLDEN_RATIO_THIRD_POINTS: tuple[tuple[float, float], ...] = (
    (1 / 3, 1 / 3),
    (2 / 3, 1 / 3),
    (1 / 3, 2 / 3),
    (2 / 3, 2 / 3),
)

# Größtmöglicher Abstand eines Punkts im Einheitsquadrat zu seinem nächstgelegenen
# Drittel-Schnittpunkt - liegt an den vier Bildecken (z.B. (0,0) -> nächster Punkt
# (1/3,1/3)), der Abstand dort ist sqrt(2)/3. Dient als Nenner, um die räumliche Distanz auf
# [0, 1] zu normieren: geometrisch exakt hergeleitet, keine Kalibrierungsfrage wie bei den
# übrigen SCHWELLWERT-Konstanten dieses Moduls.
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
    """Wählt EIN Subjekt-Zentrum für die Kompositions-Bewertung - eine dokumentierte,
    getestete Auswahlregel statt der impliziten Auswahl der ersten Bounding-Box.

    Erkannte Gesichter haben grundsätzlich Vorrang vor Tier-Erkennungen (ein Tier ist nur
    der Rückfall, falls kein Gesicht erkannt wurde); bei mehreren Kandidaten derselben Art
    gewinnt die größte Bounding-Box-Fläche - dasselbe Prominenz-Maß wie beim Tier-Score."""
    if faces:
        return _largest_by_area(faces)
    if animals:
        return _largest_by_area(animals)
    return None


def compute_golden_ratio_score(
    faces: list[FaceBoundingBox], animals: Sequence[SubjectBoxLike] = ()
) -> float:
    """`goldener_schnitt`-Kriterium: reine geometrische Heuristik ohne eigenes ML-Modell,
    wiederverwendet ausschließlich Positionsdaten aus bereits vorhandenen Detektionen - kein
    neuer Bildverarbeitungsschritt. Bewertet, wie nah das primäre Subjekt (siehe
    _select_primary_subject) an einem der vier Drittel-Schnittpunkte liegt, invers auf
    [0, 1] normiert über _GOLDEN_RATIO_MAX_DISTANCE. Eine Horizont-Linien-Erkennung ist
    bewusst nicht umgesetzt.

    Bewusst eine reine Funktion OHNE eigenen detect_person/detect_objects-Aufruf:
    worker.py::_compute_content_criteria ruft beide bereits für content_people/tier auf und
    reicht die Ergebnislisten hier durch - ein zusätzlicher detect()-Aufruf je Foto wäre
    reiner Compute-Overhead. Der Wiederverwendungsnachweis liegt deshalb auf
    Worker-Integrationsebene, siehe test_worker_criterion_scoring.py::
    test_detect_person_and_detect_objects_are_each_called_at_most_once_per_photo.

    `animals` bekommt AUSSCHLIESSLICH Tier-Erkennungen - der Aufrufer filtert die geweitete
    detect_objects-Ausgabe über `animal_detections()`, damit kein Auto und kein Teller zum
    Kompositions-Subjekt wird."""
    subject = _select_primary_subject(faces, animals)
    if subject is None:
        # Dokumentierter, niedriger (nicht neutraler) Fallback-Wert: ohne erkennbares Subjekt
        # gibt es kein Kompositions-Signal. 0.0 statt eines "neutralen" 0.5 vermeidet, ein
        # diesbezüglich nicht messbares Foto positiv zu werten. Bewusst kein Fehler und
        # bewusst kein nachgerüsteter Bildverarbeitungsschritt.
        return 0.0
    distance = min(
        math.sqrt((subject.x_center - tx) ** 2 + (subject.y_center - ty) ** 2)
        for tx, ty in _GOLDEN_RATIO_THIRD_POINTS
    )
    return max(0.0, min(1.0, 1.0 - distance / _GOLDEN_RATIO_MAX_DISTANCE))


def animal_detections(objects: Sequence[ObjectDetection]) -> list[ObjectDetection]:
    """Filtert eine ungefilterte `detect_objects`-Ausgabe auf ANIMAL_CATEGORIES,
    reihenfolgetreu.

    Bewusst eine EIGENE, benannte Funktion statt eines Inline-Comprehensions an zwei
    Stellen: der Allow-Listen-Filter ist nicht Teil von `detect_objects`, und der
    Verhaltenserhalt für `compute_golden_ratio_score` ("kein Auto, kein Teller als
    Kompositions-Subjekt") hängt genau daran - so ist er an einer benannten Funktion
    testbar, nicht nur am Ergebnis eines Konsumenten."""
    return [detection for detection in objects if detection.category in ANIMAL_CATEGORIES]


def compute_tier_score(objects: Sequence[ObjectDetection]) -> float:
    """`tier`-Kriterium: Score = Konfidenz des PROMINENTESTEN erkannten Tieres (bereits in
    [0, 1], da detect_objects nur oberhalb von OBJECT_DETECTION_CONFIDENCE_THRESHOLD
    liefert).

    Aggregationsregel bei mehreren erkannten Tieren, dokumentiert und getestet statt
    stillschweigend: die größte Bounding-Box-Fläche gewinnt, NICHT die höchste Konfidenz -
    ein kleines, aber sehr sicher erkanntes Tier am Bildrand soll nicht über ein
    großflächig präsentes Tier mit etwas niedrigerer Konfidenz gewinnen (konsistent mit
    _select_primary_subject).

    Die Funktion bekommt die UNGEFILTERTE Objektliste und setzt den
    ANIMAL_CATEGORIES-Filter SELBST durch (über `animal_detections`) - ohne diesen Schritt
    würde die Konfidenz eines Autos zum Tier-Score (eigener Regressionstest)."""
    animals = animal_detections(objects)
    if not animals:
        return 0.0
    return _largest_by_area(animals).confidence


# Kuratierte Allow-Listen der COCO-80-Klassen für die beiden Objekt-Kriterien - dasselbe
# Muster wie ARCHITECTURE_CATEGORIES/LANDSCAPE_SCENE_CATEGORIES, ebenfalls ohne
# modell-ladenden Test.
#
# VERIFIZIERT (2026-08-30): die exakte Schreibweise stammt aus der im gebündelten
# Modell-Asset mitgelieferten Label-Datei `labelmap.txt` in
# backend/src/photosort/assets/efficientdet_lite0.tflite (die .tflite-Datei enthält ihre
# Metadaten als angehängtes ZIP-Archiv). Mehrteilige COCO-Klassennamen stehen dort mit
# LEERZEICHEN ("hot dog", "wine glass"), nicht mit Unterstrich - genau diesen String liefert
# mediapipe als `category_name`.
VEHICLE_CATEGORIES = frozenset(
    {"bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat"}
)

# Bewusst OHNE `cup`/`bottle`/`bowl` und ohne Besteck (`fork`/`knife`/`spoon`): diese Klassen
# kommen zu haeufig beilaeufig in Raum- und Personenszenen vor und wuerden `essen_trinken` sonst
# massenhaft falsch ausloesen (eigener parametrisierter Testfall haelt die Auswahl fest).
# `wine glass` bleibt drin - ein Weinglas ist im Gegensatz zur generischen Tasse ein
# hinreichend eindeutiges Getraenke-Signal.
FOOD_CATEGORIES = frozenset(
    {
        "banana",
        "apple",
        "sandwich",
        "orange",
        "broccoli",
        "carrot",
        "hot dog",
        "pizza",
        "donut",
        "cake",
        "wine glass",
    }
)


def _allow_listed_confidence_maximum(
    objects: Sequence[ObjectDetection], allowed: frozenset[str]
) -> float:
    """Geteilte Aggregationsregel von compute_fahrzeug_score/compute_essen_trinken_score:
    Konfidenz-Maximum INNERHALB der jeweiligen Allow-Liste, 0.0 ohne Treffer - identisches
    Muster zu compute_gebaeude_score/compute_landschaft_score, hier als eine Funktion statt
    zweier Kopien (die Allow-Liste ist der einzige Unterschied). Keine zweite
    Konfidenzschwelle: detect_objects liefert bereits nur Erkennungen oberhalb von
    OBJECT_DETECTION_CONFIDENCE_THRESHOLD."""
    hits = [detection.confidence for detection in objects if detection.category in allowed]
    if not hits:
        return 0.0
    return max(hits)


def compute_fahrzeug_score(objects: Sequence[ObjectDetection]) -> float:
    """`fahrzeug`-Kriterium: Allow-Listen-gefiltertes Konfidenz-Maximum über
    VEHICLE_CATEGORIES. Reine Funktion ohne eigenen detect()-Aufruf -
    worker.py::_compute_content_criteria ruft `detect_objects` GENAU EINMAL pro Foto auf und
    reicht dieselbe Objektliste an `tier`, `fahrzeug`, `essen_trinken` UND
    `goldener_schnitt` weiter."""
    return _allow_listed_confidence_maximum(objects, VEHICLE_CATEGORIES)


def compute_essen_trinken_score(objects: Sequence[ObjectDetection]) -> float:
    """`essen_trinken`-Kriterium: Allow-Listen-gefiltertes Konfidenz-Maximum über
    FOOD_CATEGORIES - Muster wie compute_fahrzeug_score."""
    return _allow_listed_confidence_maximum(objects, FOOD_CATEGORIES)


# Kuratierte Allow-Liste architekturbezogener ImageNet-1k-Klassen - technische
# Detailentscheidung der Umsetzung; siehe den Modul-Kommentar in classification.py dazu,
# warum die Filterung HIER und nicht in classify_scene selbst passiert. Dokumentierte,
# bewusst akzeptierte Lücke: ImageNet hat kaum Innenraum-Klassen, `living_room`/`kitchen`/
# `office` werden strukturell nicht erkannt - nur Außenarchitektur wird zuverlässig erfasst.
#
# BEFUND (2026-08-30, bei der Verifikation von LANDSCAPE_SCENE_CATEGORIES unten
# aufgefallen): die Label-Datei schreibt mehrteilige Klassennamen mit LEERZEICHEN, nicht mit
# Unterstrich - die Einträge "bell_cote"/"suspension_bridge"/"triumphal_arch" (Label-Datei:
# "bell cote", "suspension bridge", "triumphal arch") und "lighthouse" (Label-Datei:
# "beacon") können deshalb nie matchen. Bewusst NICHT hier korrigiert: eine Korrektur wäre
# eine Verhaltensänderung am gebaeude-Kriterium und gehört in eine eigene Story.
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
    """`gebaeude`-Kriterium: Score = Konfidenz des besten Treffers INNERHALB der
    ARCHITECTURE_CATEGORIES-Allow-Liste, 0.0 falls keiner der übergebenen `labels` in der
    Allow-Liste enthalten ist - auch bei hoher Modell-Konfidenz einer nicht
    architekturbezogenen Kategorie. Es wird tatsächlich die Allow-Liste gefiltert, nicht
    die rohe Modell-Konfidenz durchgereicht.

    Zusätzlich zur Allow-Liste wird die inhaltliche Konfidenzschwelle
    SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD (0.5) HIER explizit durchgesetzt, und das ist
    verpflichtend: classify_scene liefert bereits ab der niedrigeren
    SCENE_LABEL_MIN_CONFIDENCE (0.2), damit compute_landschaft_score den für natürliche
    Szenen nötigen Spielraum bekommt - ohne diesen Filter übernähme das gebaeude-Kriterium
    diese Absenkung stillschweigend mit."""
    allowed = [
        label
        for label in labels
        if label.category in ARCHITECTURE_CATEGORIES
        and label.confidence >= SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD
    ]
    if not allowed:
        return 0.0
    return max(label.confidence for label in allowed)


# Kuratierte Allow-Liste natürlicher ImageNet-1k-Szenenklassen - dasselbe Muster wie
# ARCHITECTURE_CATEGORIES oben, ebenfalls ohne modell-ladenden Test.
#
# VERIFIZIERT (2026-08-30): die exakte Schreibweise stammt aus der im gebündelten
# Modell-Asset mitgelieferten Label-Datei `labels_without_background.txt` in
# backend/src/photosort/assets/efficientnet_lite0.tflite (die .tflite-Datei enthält ihre
# Metadaten als angehängtes ZIP-Archiv). Die zehn Klassen sind die Indizes 970 und 972-980
# der ImageNet-1k-Label-Liste, also GENAU die natürlichen Szenenklassen des Vokabulars.
# Schreibweise mit LEERZEICHEN, nicht mit Unterstrich ("coral reef", nicht "coral_reef") -
# so steht es in der Label-Datei, und genau diesen String liefert mediapipe als
# `category_name`.
#
# Dokumentierte, bewusst akzeptierte Lücke: ImageNet-1k kennt KEINE Klassen für Wald, Wiese
# oder Feld - solche Landschaften werden strukturell nicht als `landschaft` erkannt und
# landen im "nicht erkannt"-Zustand. Eine Nachkalibrierung bleibt eine reine
# Listen-/Konstanten-Änderung ohne Architektur-Eingriff.
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

# Inhaltliche Konfidenzschwelle des landschaft-Kriteriums - bewusst deutlich niedriger als
# SCENE_CLASSIFICATION_CONFIDENCE_THRESHOLD (0.5, gebaeude): ein Landschaftsfoto verteilt
# seine Modellkonfidenz typischerweise über mehrere benachbarte Szenenklassen ("alp"/
# "valley"/"promontory" am selben Bergpanorama), eine Architektur-Klasse konzentriert sie.
# Dokumentierte, nicht gegen einen Fotokorpus kalibrierte Setzung, austauschbar ohne
# Architektur-Änderung.
LANDSCHAFT_LABEL_MIN_CONFIDENCE = 0.25


def compute_landschaft_score(labels: Sequence[SceneLabel]) -> float:
    """`landschaft`-Kriterium: Score = Konfidenz des besten Labels, das SOWOHL in
    LANDSCAPE_SCENE_CATEGORIES liegt ALS AUCH >= LANDSCHAFT_LABEL_MIN_CONFIDENCE ist,
    sonst 0.0.

    Reine Funktion ohne eigenen classify_scene-Aufruf (Trennung analog
    compute_gebaeude_score/compute_tier_score): worker.py::_compute_content_criteria ruft
    classify_scene GENAU EINMAL pro Foto auf und reicht dieselbe Label-Liste an
    compute_gebaeude_score UND diese Funktion weiter - es entstehen keine zusätzlichen
    Kosten je Foto. Der Ein-Aufruf-Nachweis liegt deshalb auf Worker-Integrationsebene,
    siehe test_worker_criterion_scoring.py."""
    allowed = [
        label
        for label in labels
        if label.category in LANDSCAPE_SCENE_CATEGORIES
        and label.confidence >= LANDSCHAFT_LABEL_MIN_CONFIDENCE
    ]
    if not allowed:
        return 0.0
    return max(label.confidence for label in allowed)


# Genau die Kriterien, die is_landmark_candidate unten auswertet - exportiert, damit die
# API-seitige Kostenschätzung (api/projects.py::_count_landmark_candidates) nur diese Zeilen
# laden muss, ohne die Schlüssel ein zweites Mal zu kennen. Wer hier etwas ergänzt, MUSS es
# auch in is_landmark_candidate tun; der gemeinsame Test in test_criteria.py hält beide
# Stellen zusammen.
LANDMARK_CANDIDATE_CRITERION_KEYS: tuple[str, ...] = ("landschaft", "gebaeude")


def is_landmark_candidate(values: dict[str, float]) -> bool:
    """Reine Schwellenwert-Prüfung für die landmark-Vorfilterung.

    Ein Foto ist Kandidat, wenn `landschaft` ODER `gebaeude` die jeweils registrierte
    category_presence_threshold erreicht (`>=`, inklusiv, dieselben Registry-Werte wie die
    übrige Presence-Auswertung). Fehlende Werte gelten als 0.0, kein Sonderfall. Von
    worker.py::_select_landmark_candidates (Live-Lauf) UND
    api/photos.py::_cloud_vision_status_out (Read-Time-Ableitung) gemeinsam genutzt -
    verhindert ein Auseinanderlaufen beider Stellen bei einer Schwellenwert-Änderung.

    SICHERHEIT: Das ist die Stelle an der Vertrauensgrenze - sie entscheidet, welche Fotos
    den Homeserver in Richtung des externen Vision-Anbieters verlassen dürfen. Der
    Vorfilter bleibt rein lokal und VOR jedem Cloud-Aufruf. Geprüft wird `landschaft` statt
    `content_landscape`: inhaltlich das, was der Filter ausdrücken soll ("auf dem Foto ist
    eine Landschaft oder ein Gebäude zu sehen"); die beiden Kandidatenmengen stehen in
    KEINEM Teilmengen-Verhältnis zueinander."""
    landschaft_threshold = CRITERIA_REGISTRY["landschaft"].category_presence_threshold
    gebaeude_threshold = CRITERIA_REGISTRY["gebaeude"].category_presence_threshold
    assert landschaft_threshold is not None
    assert gebaeude_threshold is not None
    return (
        values.get("landschaft", 0.0) >= landschaft_threshold
        or values.get("gebaeude", 0.0) >= gebaeude_threshold
    )


def compute_landmark_score(detection: LandmarkDetection) -> float:
    """`landmark`-Kriterium: reine, synchrone, netzwerkfreie Funktion - der eigentliche
    Netzwerk-/Cloud-Aufruf lebt ausschließlich in landmark.py, NICHT hier. Kein
    identifizierter Name -> 0.0 (kein Sehenswürdigkeits-Signal, unabhängig von einer
    theoretisch trotzdem gelieferten confidence - ohne Namen ist der Wert bedeutungslos).
    Sonst die vom Vision-LLM gelieferte Konfidenz, auf [0, 1] geklemmt - defensiv, falls das
    Modell je einen Wert außerhalb des Bereichs liefert."""
    if detection.name is None:
        return 0.0
    return max(0.0, min(1.0, detection.confidence))


# Deadzone um einen frontalen Blick (Yaw nahe 0) - kein klares Richtungssignal, ein nahezu
# frontaler Blick sagt nichts darüber aus, ob rechts oder links mehr Freiraum "in
# Blickrichtung" nötig wäre. Unkalibriert dokumentiert (gleiche Klasse wie
# SHARPNESS_NORMALIZATION_CEILING, es gibt keinen Fotokorpus im Repo zur Kalibrierung).
FREIRAUM_YAW_DEADZONE_DEGREES = 10.0


def compute_freiraum_score(orientation: FaceOrientation | None) -> float:
    """`freiraum`-Kriterium: reine Score-Berechnung aus einer bereits vorhandenen
    FaceOrientation, OHNE eigenen detect_face_orientation-Aufruf (Trennung analog
    compute_tier_score/compute_gebaeude_score) - worker.py::_compute_content_criteria ruft
    detect_face_orientation genau einmal auf und reicht das Ergebnis hier durch.

    Drei bewusst UNTERSCHIEDLICHE Fallback-Werte, jeder Fall einzeln beantwortet statt nach
    einem einheitlichen Schema - bedeutet die Abwesenheit eines Signals ein schlechtes Foto
    oder nur ein nicht messbares?
    1. Kein Gesicht erkannt (`orientation is None`) -> 0.0 (niedrig, NICHT neutral) - analog
       goldener_schnitt: dieses Kriterium bewertet die Rahmung eines Subjekts, ohne jedes
       Subjekt gibt es keinen positiven Kompositionswert.
    2. Nahezu frontaler Blick (`|yaw| < FREIRAUM_YAW_DEADZONE_DEGREES`) -> 0.5 (neutral) -
       kein klares Richtungssignal. Der Vergleich ist bewusst `<`, NICHT `<=`: ein Yaw EXAKT
       an der Deadzone-Grenze zählt als AUSSERHALB, nicht als neutral.
    3. Sonst: `score = clip(looking_space / (looking_space + opposite_space), 0, 1)` -
       `looking_space` ist der verfügbare Bildraum auf der dem Gesicht zugewandten Seite
       (Vorzeichenkonvention siehe FaceOrientation.yaw_degrees-Docstring in
       classification.py: positiver Yaw -> Blick Richtung steigendem x ->
       looking_space = 1 - max_x, negativer Yaw -> looking_space = min_x), `opposite_space`
       die Gegenseite. Zusätzlicher 0-Schutz, gleiche Argumentationsklasse wie die
       Deadzone: füllt das Gesicht die VOLLE Bildbreite (`min_x == 0`, `max_x == 1`), sind
       beide Räume 0 - neutraler Fallback 0.5 statt ZeroDivisionError."""
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
