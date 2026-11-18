"""Die lokale Kriterienphase: die bildbasierten Kriterien je Foto, ihre Zeilen und die lokale
Motiv-Kopfzeile."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

import photosort.worker._runs as runs
from photosort.aesthetics import AestheticsModelLike, compute_aesthetics
from photosort.classification import (
    ANIMAL_CATEGORIES,
    FaceBoundingBox,
    FaceDetectorLike,
    FaceLandmarkerLike,
    ObjectDetection,
    ObjectDetectorLike,
    SceneClassifierLike,
    SceneLabel,
    classify_scene,
    detect_face_orientation,
    detect_objects,
    detect_person,
)
from photosort.criteria import (
    CRITERIA_REGISTRY,
    FOOD_CATEGORIES,
    VEHICLE_CATEGORIES,
    allow_listed_area_fraction,
    animal_detections,
    bounding_box_area_fraction,
    compute_content_landscape,
    compute_essen_trinken_score,
    compute_fahrzeug_score,
    compute_freiraum_score,
    compute_gebaeude_score,
    compute_golden_ratio_score,
    compute_landschaft_score,
    compute_symmetrie_score,
    compute_tier_score,
    content_people_from_faces,
    normalize_exposure,
    normalize_sharpness,
)
from photosort.horizon import compute_horizon_tilt_score
from photosort.models import CriterionSource, MotifAssessmentSource, Photo
from photosort.motif_strengths import upsert_assessment
from photosort.motifs import local_motif_strengths
from photosort.thumbnails import variant_path
from photosort.worker._criterion import (
    CriterionRunContext,
    delete_criterion,
    upsert_criterion,
)

if TYPE_CHECKING:
    from photosort.worker.criterion_scoring import ModelSet


# Analog SCORE_COMMIT_BATCH_SIZE, fuer CriterionScoringRun.photos_processed. Kleiner als
# SCORE_COMMIT_BATCH_SIZE, da mediapipe-Inferenz (content_people-Kriterium) pro Foto eine spuerbare
# Laufzeit hat - ein grober Batch von 25 wuerde den Live-Fortschritt bei typischen
# Ausschuss-Überlebenden-Mengen faktisch einfrieren. Modul-Konstante statt Default-Parameterwert,
# damit Tests sie per monkeypatch.setattr(worker, "CRITERION_SCORING_COMMIT_BATCH_SIZE", ...)
# verkleinern koennen.
CRITERION_SCORING_COMMIT_BATCH_SIZE = 5


# Die von compute_content_criteria best-effort berechneten Kriterien-Keys - eine Liste statt
# einzelner if-Blöcke im Aufrufer, damit ein weiteres bildbasiertes Kriterium keine Kopie des
# Upsert-Codes braucht. Die zugehoerige CriterionSource wird bewusst NICHT hier dupliziert, sondern
# direkt aus criteria.py::CRITERIA_REGISTRY abgeleitet - eine Aenderung an der Registry (z.B. ein
# Kriterium wechselt von local_heuristic zu local_ml) bleibt so automatisch konsistent, ohne dass
# diese Stelle separat nachgepflegt werden muss.
#
# Das ist die Menge der bildbasiert berechneten Kriterien fuer die Upsert-Buchhaltung und eine
# fachlich ANDERE als "traegt ein `presence_threshold`" (welche Kriterien eine Inhaltsaussage
# treffen): hier stehen auch goldener_schnitt/aesthetics, die keine treffen. Die beiden Mengen nie
# gleichsetzen.
IMAGE_ANALYSIS_CRITERION_KEYS: tuple[str, ...] = (
    "content_people",
    "content_landscape",
    "tier",
    "goldener_schnitt",
    "gebaeude",
    # Zweites Kriterium aus derselben Szenen-Klassifikation, siehe compute_content_criteria.
    "landschaft",
    "aesthetics",
    # Zwei weitere Kriterien aus DERSELBEN COCO-Detektorausgabe wie `tier` (siehe
    # compute_content_criteria).
    "fahrzeug",
    "essen_trinken",
    # Kompositions-Ranking-Signale ab hier.
    "symmetrie",
    "horizont",
    "freiraum",
)


IMAGE_ANALYSIS_CRITERION_SOURCES: dict[str, CriterionSource] = {
    key: CRITERIA_REGISTRY[key].source for key in IMAGE_ANALYSIS_CRITERION_KEYS
}


@dataclass(frozen=True)
class ContentCriteria:
    """Das Ergebnis der bildbasierten Analyse EINES Fotos: die Kriterien-Werte und die
    Flaechenanteile je Allow-Liste.

    Die Flaechenanteile sind KEIN Kriterium: sie bekommen keine Registry-Zeile, keine
    Datenbankspalte und keinen Eintrag in `IMAGE_ANALYSIS_CRITERION_KEYS`. Sie sind eine
    Zwischengroesse auf dem Weg zur Motivstaerke (motifs.py::local_motif_strengths) und leben nur
    fuer die Dauer des Laufs - die Bounding-Boxen selbst werden nirgends persistiert.

    Geschluesselt sind sie mit dem KRITERIEN-Schluessel, dessen Allow-Liste sie ausgemessen haben
    (`content_people`, `tier`, `fahrzeug`, `essen_trinken`) - so gibt es keine zweite
    Schluesselmenge, die gegen `criteria.py` driften koennte.

    `not_measurable` traegt AUSSCHLIESSLICH die Kriterien, deren Detektion tatsaechlich LIEF und
    das Merkmal nicht fand - "nicht messbar". Es ist ausdruecklich KEIN Komplement von `values`:
    ein Kriterium, das mangels Detektor oder wegen einer Ausnahme gar nicht berechnet wurde
    ("nicht berechenbar"), fehlt in BEIDEN Mengen. Der Unterschied entscheidet ueber Loeschen
    oder Behalten einer Altzeile - eine Voreinstellung "alles, was nicht in `values` steht"
    loeschte beim Frühausstieg unten den gesamten Kriteriensatz eines Fotos."""

    values: dict[str, float]
    area_fractions: dict[str, float]
    not_measurable: frozenset[str] = frozenset()


def compute_content_criteria(
    cache_dir: Path,
    photo: Photo,
    face_detector: FaceDetectorLike | None,
    animal_detector: ObjectDetectorLike | None,
    scene_classifier: SceneClassifierLike | None,
    aesthetics_model: AestheticsModelLike | None,
    face_landmarker: FaceLandmarkerLike | None,
) -> ContentCriteria:
    """Best-effort wie scoring.py::_compute_photo_metrics: JEDES hier berechnete Kriterium
    hat sein EIGENES try/except - ein einzelner fehlgeschlagener Berechnungsversuch
    (fehlende/defekte display-Cache-Datei, Modell-Ladefehler in genau einem Detektor) darf
    weder den gesamten Lauf noch die ÜBRIGEN, unabhängig berechenbaren Kriterien desselben
    Fotos mit sich reißen; je Kriterium gibt es dafür einen eigenen Fehlerfall-Testlauf. Das
    betroffene Kriterium bleibt für dieses Foto einfach ungeschrieben (kein Platzhalterwert
    wie 0). Die fünf Detektoren/Modelle sind bewusst `| None` typisiert: schlug der
    zugehörige
    `try_build`-Aufruf im Aufrufer bereits fehl, wird das betroffene Kriterium (bzw. die davon
    abhaengigen) hier einfach uebersprungen, statt mit einem ungueltigen Objekt eine Exception zu
    provozieren, die erst durch das try/except unten "zufaellig" richtig behandelt wuerde.

    detect_person/detect_objects werden je HOECHSTENS einmal aufgerufen und fuer mehrere davon
    abhaengige Kriterien wiederverwendet (content_people+goldener_schnitt bzw.
    tier+fahrzeug+essen_trinken+goldener_schnitt) - kein zweiter, teurer detect()-Aufruf pro Foto
    und Detektortyp. goldener_schnitt wird nur dann berechnet,
    wenn BEIDE zugrunde liegenden Detektionen (auch mit leerem Ergebnis) erfolgreich waren - ein
    fehlgeschlagener Detektor darf nicht stillschweigend als "kein Subjekt gefunden" interpretiert
    werden, das waere ein unentdeckter Fehler statt eines ungeschriebenen Kriteriums."""
    path = variant_path(cache_dir, photo.id, photo.etag, "display")
    if not path.is_file():
        return ContentCriteria(values={}, area_fractions={})
    try:
        with Image.open(path) as opened:
            opened.load()
            image: Image.Image = opened
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
    except Exception:
        return ContentCriteria(values={}, area_fractions={})

    values: dict[str, float] = {}
    # "Die Detektion lief, das Merkmal fehlt" - gefuellt AUSSCHLIESSLICH dort, wo der Detektor ein
    # Ergebnis geliefert hat und die Score-Funktion `None` zurueckgibt. Nie als Komplement von
    # `values` gebildet: der Fruehausstieg oben verlaesst die Funktion mit zwei LEEREN Mengen,
    # und ein Komplement haette dort jedes Kriterium des Fotos als "nicht messbar" ausgewiesen.
    not_measurable: set[str] = set()
    # Die Flaechenanteile je Allow-Liste, aus DENSELBEN Detektionen wie die Scores darunter - kein
    # zweiter Detektoraufruf. Jede Berechnung hat ihr eigenes try/except wie die Scores: ein
    # Fehlschlag laesst genau diesen Anteil ungeschrieben (das Motiv bleibt bei 0), statt den
    # gesamten Lauf oder die uebrigen Anteile mitzureissen.
    area_fractions: dict[str, float] = {}

    faces: list[FaceBoundingBox] | None = None
    if face_detector is not None:
        try:
            faces = detect_person(image, face_detector)
            values["content_people"] = content_people_from_faces(faces)
        except Exception:
            faces = None
        if faces is not None:
            try:
                # AUSDRUECKLICH getrennt von `content_people`: das Kriterium bleibt die
                # 0.0/1.0-Praesenz (Rangfolge und Landmark-Kandidatenwahl haengen daran), der
                # Anteil ist die zusaetzliche Groesse fuer die Motivstaerke.
                area_fractions["content_people"] = bounding_box_area_fraction(faces)
            except Exception:
                pass

    # EIN detect_objects-Aufruf speist drei Kriterien plus goldener_schnitt. Die Objekt-Erkennung
    # und JEDE der drei Score-Berechnungen haben ein EIGENES try/except - ein Fehler in einer
    # Score-Funktion darf die beiden anderen nicht mitreißen (wie bei gebaeude/landschaft unten).
    objects: list[ObjectDetection] | None = None
    if animal_detector is not None:
        try:
            objects = detect_objects(image, animal_detector)
        except Exception:
            objects = None
        if objects is not None:
            try:
                values["tier"] = compute_tier_score(objects)
            except Exception:
                pass
            try:
                values["fahrzeug"] = compute_fahrzeug_score(objects)
            except Exception:
                pass
            try:
                values["essen_trinken"] = compute_essen_trinken_score(objects)
            except Exception:
                pass
            # Dieselbe eine Detektorausgabe, drei Allow-Listen, drei Flaechenanteile - dieselben
            # Klassenmengen wie die drei Scores darueber.
            for criterion_key, allowed in (
                ("tier", ANIMAL_CATEGORIES),
                ("fahrzeug", VEHICLE_CATEGORIES),
                ("essen_trinken", FOOD_CATEGORIES),
            ):
                try:
                    area_fractions[criterion_key] = allow_listed_area_fraction(objects, allowed)
                except Exception:
                    pass

    try:
        values["content_landscape"] = compute_content_landscape(image)
    except Exception:
        pass

    # Keine Modell-/Detektor-Abhaengigkeit - wie content_landscape UNCONDITIONAL berechnet.
    try:
        values["symmetrie"] = compute_symmetrie_score(image)
    except Exception:
        pass

    # klassischer cv2-Algorithmus ohne trainiertes Modell - ebenfalls
    # UNCONDITIONAL berechnet, kein injizierbarer Detektor/Builder noetig.
    try:
        values["horizont"] = compute_horizon_tilt_score(image)
    except Exception:
        pass

    # classify_scene wird GENAU EINMAL pro Foto aufgerufen, dieselbe Label-Liste speist gebaeude UND
    # landschaft (Wiederverwendungsmuster wie detect_person -> content_people + goldener_schnitt) -
    # keine zusaetzlichen Kosten pro Foto. Die Label-Ermittlung und jede der beiden
    # Score-Berechnungen haben ein EIGENES try/except - ein Fehler in einer Score-Funktion darf das
    # jeweils andere Kriterium nicht mitreissen.
    if scene_classifier is not None:
        scene_labels: list[SceneLabel] | None = None
        try:
            scene_labels = classify_scene(image, scene_classifier)
        except Exception:
            scene_labels = None
        if scene_labels is not None:
            try:
                values["gebaeude"] = compute_gebaeude_score(scene_labels)
            except Exception:
                pass
            try:
                values["landschaft"] = compute_landschaft_score(scene_labels)
            except Exception:
                pass

    if aesthetics_model is not None:
        try:
            values["aesthetics"] = compute_aesthetics(image, aesthetics_model)
        except Exception:
            pass

    if faces is not None and objects is not None:
        try:
            # Nur die TIER-Erkennungen sind Kompositions-Subjekt-Kandidaten - kein Auto,
            # kein Teller.
            golden_ratio = compute_golden_ratio_score(faces, animal_detections(objects))
            # BEIDE Detektionen liefen (das sichern die `is not None` oben): ein `None` heisst
            # hier "kein Subjekt im Bild", also NICHT MESSBAR - und nicht "nicht berechenbar".
            if golden_ratio is None:
                not_measurable.add("goldener_schnitt")
            else:
                values["goldener_schnitt"] = golden_ratio
        except Exception:
            pass

    # EIGENSTAENDIGER, zusaetzlicher Modellaufruf neben dem obigen face_detector - kein Ersatz,
    # content_people/goldener_schnitt bleiben unveraendert auf dem bestehenden face_detector.
    if face_landmarker is not None:
        try:
            freiraum = compute_freiraum_score(detect_face_orientation(image, face_landmarker))
            # Die Detektion lief - ein `None` heisst "kein Gesicht erkannt", also NICHT MESSBAR.
            # Wirft `detect_face_orientation` dagegen, greift das `except` und das Kriterium
            # landet in KEINER der beiden Mengen ("nicht berechenbar").
            if freiraum is None:
                not_measurable.add("freiraum")
            else:
                values["freiraum"] = freiraum
        except Exception:
            pass

    return ContentCriteria(
        values=values, area_fractions=area_fractions, not_measurable=frozenset(not_measurable)
    )


async def run_local_phase(context: CriterionRunContext, models: ModelSet) -> None:
    """DIE lokale Kriterienphase: sharpness/exposure immer, die bildbasierten Inhalts-Kriterien
    best-effort, periodisch zwischen-committet.

    Jeder Modell-Builder bekommt ueber `runs.try_build` sein eigenes try/except, KEINER laeuft
    ungeschuetzt: ein Fehlschlag eines einzelnen Builders (fehlendes/defektes
    .tflite-/.hdf5-Asset, mediapipe-/tensorflow-Laufzeitproblem) markierte sonst den GESAMTEN Lauf
    als FAILED, obwohl die Kriterien pro Foto bewusst best-effort behandelt werden. Schlaegt einer
    fehl, bleibt der zugehoerige Detektor/Klassifikator/das Modell None, `compute_content_criteria`
    ueberspringt dann NUR die davon abhaengigen Kriterien (siehe dortige `if ... is not None`-
    Waechter) - sharpness/exposure und alle anderen, unabhaengig berechenbaren Kriterien werden
    trotzdem geschrieben."""
    session = context.session
    run = context.run
    has_rows = bool(context.rows)
    detector = runs.try_build(models.build_detector) if has_rows else None
    animal_detector = runs.try_build(models.build_animal_detector) if has_rows else None
    scene_classifier = runs.try_build(models.build_classifier) if has_rows else None
    aesthetics_model = runs.try_build(models.build_aesthetics) if has_rows else None
    face_landmarker = runs.try_build(models.build_landmarker) if has_rows else None
    processed = 0
    for photo, score in context.rows:
        if processed % CRITERION_SCORING_COMMIT_BATCH_SIZE == 0:
            # Pruefpunkt je Batch: was bis hier committet ist, bleibt; der Rest entfaellt.
            await runs.raise_if_cancel_requested(session, run)
        values: dict[str, float] = {}

        sharpness_value = normalize_sharpness(score.sharpness)
        upsert_criterion(
            context, photo.id, "sharpness", sharpness_value, CriterionSource.LOCAL_HEURISTIC
        )
        values["sharpness"] = sharpness_value

        exposure_value = normalize_exposure(score.exposure)
        upsert_criterion(
            context, photo.id, "exposure", exposure_value, CriterionSource.LOCAL_HEURISTIC
        )
        values["exposure"] = exposure_value

        # KEIN assert-is-not-None hier: jeder der fuenf Builder ist ueber try_build best-effort
        # abgesichert und kann legitim None sein - compute_content_criteria ueberspringt die davon
        # abhaengigen Kriterien dann selbst, statt dass ein fehlgeschlagener Builder den gesamten
        # Lauf abbricht.
        content = compute_content_criteria(
            context.cache_dir,
            photo,
            detector,
            animal_detector,
            scene_classifier,
            aesthetics_model,
            face_landmarker,
        )
        for criterion_key, source in IMAGE_ANALYSIS_CRITERION_SOURCES.items():
            if criterion_key in content.values:
                upsert_criterion(
                    context, photo.id, criterion_key, content.values[criterion_key], source
                )
                values[criterion_key] = content.values[criterion_key]

        # NUR `not_measurable` - "die Detektion lief, das Merkmal fehlt". Ein mangels Detektor oder
        # wegen einer Ausnahme unberechnetes Kriterium steht dort nicht und behaelt seine Altzeile.
        for criterion_key in content.not_measurable:
            await delete_criterion(context, photo.id, criterion_key)

        context.candidate_values[photo.id] = values
        context.area_fractions_by_photo_id[photo.id] = content.area_fractions

        processed += 1
        if processed % CRITERION_SCORING_COMMIT_BATCH_SIZE == 0:
            run.photos_processed = processed
            # Fortschritts-Watchdog (Schicht 2) - analog run_project_scan.
            run.last_progress_at = runs.now_utc()
            await session.commit()

    run.photos_processed = processed
    await session.commit()


async def write_local_motif_header(context: CriterionRunContext) -> None:
    """DIE LOKALE MOTIV-KOPFZEILE. Ihre Stelle ist NACH der Landmark-Phase, und das ist keine
    Kosmetik: `bauwerk_sehenswuerdigkeit` ist lokal `max(Szenen-Konfidenz,
    Sehenswuerdigkeits-Konfidenz)`, und der zweite Wert entsteht erst dort. Vor der Phase
    geschrieben fehlte der gerade bezahlte Beitrag im Vektor.

    `upsert_assessment` setzt die Regel selbst durch: eine vorhandene Cloud-Grundlage bleibt
    unberuehrt, eine lokale wird ersetzt. `excluded_document` ist hier immer `False` - den
    Ausschluss beantwortet allein das Modell, die lokale Erkennung hat dazu keine Aussage."""
    for photo_id, criterion_values in context.candidate_values.items():
        await upsert_assessment(
            context.session,
            photo_id,
            source=MotifAssessmentSource.LOCAL,
            strengths=local_motif_strengths(
                criterion_values, context.area_fractions_by_photo_id.get(photo_id, {})
            ),
            excluded_document=False,
            provider=None,
            computed_at=context.now,
        )
    await context.session.commit()
