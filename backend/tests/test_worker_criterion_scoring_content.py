"""Kriterien-Lauf: Inhaltskriterien (Tier, Landschaft, Gesicht) bis zum Ende-zu-Ende-Lauf."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CriterionScoringRun,
    PhotoCriterionScore,
    PhotoRanking,
    ScanStatus,
)
from photosort.worker import _runs as worker_runs
from photosort.worker import run_criterion_scoring, run_project_scoring
from photosort.worker._criterion import local as worker_local
from tests.support import make_project as _make_project
from tests.support import write_display_variant
from tests.support.criterion_scoring import (
    FaceLandmarkerStub,
    NoFaceDetector,
    NoFaceLandmarker,
    SingleFaceDetector,
    _add_album_suitability,
    _add_photo,
    _add_score,
    _add_successful_scoring_run,
    _animal_detector_stub,
    _flat_image,
    _no_aesthetics_model,
    _no_animal_detector,
    _no_face_detector,
    _no_face_landmarker,
    _no_scene_classifier,
    _rotation_matrix_y,
    _scene_classifier_stub,
)


class CountingDetector:
    """Zaehlt Aufrufe von detect() - Wiederverwendungsnachweis (Akzeptanzkriterium der Spec 0038:
    detect_person/detect_objects werden je Foto hoechstens einmal aufgerufen und fuer mehrere
    davon abhaengige Kriterien wiederverwendet, statt fuer jedes Kriterium erneut zu
    detektieren)."""

    def __init__(self) -> None:
        self.call_count = 0

    def detect(self, image: object) -> object:
        self.call_count += 1
        return SimpleNamespace(detections=[])


async def test_tier_criterion_is_written_when_an_animal_is_detected(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "dog.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_animal_detector_stub,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["tier"] == 0.9


async def test_a_failing_model_builder_does_not_fail_the_run_or_unrelated_criteria(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Copilot-Review-Fund (PR #88): anders als ein detect()-Aufruf, der WAEHREND der Foto-
    # Schleife fehlschlaegt (siehe die uebrigen best-effort-Tests), simuliert dieser Test einen
    # Fehlschlag des BUILDERS selbst (z.B. fehlendes/defektes Modell-Asset) - passiert VOR der
    # Schleife, einmalig fuer den gesamten Lauf. sharpness/exposure/content_landscape duerfen
    # trotzdem fuer JEDES Foto geschrieben werden, nur die vom fehlgeschlagenen Face-Detector
    # abhaengigen Kriterien (content_people/goldener_schnitt) bleiben ungeschrieben.
    def _broken_face_detector_builder() -> NoFaceDetector:
        raise RuntimeError("Modell-Asset fehlt/ist defekt")

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_broken_face_detector_builder,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        # Ein Landmarker, der tatsaechlich ein Gesicht findet: seit Spec 0428 ist `freiraum` ohne
        # erkanntes Gesicht NICHT MESSBAR und bliebe auch ohne jeden Fehler ungeschrieben - die
        # Aussage "haengt am eigenen Builder, nicht an build_detector" braeuchte dann keinen Wert.
        build_landmarker=lambda: FaceLandmarkerStub(matrix=_rotation_matrix_y(30.0)),
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert "content_people" not in criteria
    assert "goldener_schnitt" not in criteria
    assert "sharpness" in criteria
    assert "exposure" in criteria
    assert "content_landscape" in criteria
    assert "tier" in criteria  # haengt nicht vom Face-Detector-Builder ab
    assert "gebaeude" in criteria
    assert "aesthetics" in criteria
    assert "symmetrie" in criteria  # haengt von keinem Detektor/Modell ab
    assert "horizont" in criteria  # haengt von keinem Detektor/Modell ab
    # haengt vom eigenen face_landmarker-Builder ab, nicht von build_detector.
    assert "freiraum" in criteria


async def test_tier_criterion_best_effort_failure_does_not_fail_the_run_or_other_criteria(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Eigener Fehlerfall-Testlauf spezifisch fuer "tier" (Akzeptanzkriterium der Spec: "Je
    # Kriterium mindestens ein eigener Fehlerfall-Testlauf, nicht nur ein generischer").
    class BrokenAnimalDetector:
        def detect(self, image: object) -> object:
            raise RuntimeError("Modell-Ladefehler")

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=BrokenAnimalDetector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    # tier, fahrzeug, essen_trinken UND goldener_schnitt haengen alle von detect_objects ab,
    # bleiben also alle ungeschrieben - content_people/content_landscape/gebaeude (haengen nicht
    # von detect_objects ab) werden trotzdem geschrieben, der Lauf endet regulaer
    # (specs/features/0289-feste-kategorien.md, Teststrategie 7).
    assert "tier" not in criteria
    assert "fahrzeug" not in criteria
    assert "essen_trinken" not in criteria
    assert "goldener_schnitt" not in criteria
    assert "content_people" in criteria
    assert "content_landscape" in criteria
    assert "gebaeude" in criteria


async def test_gebaeude_criterion_is_written_when_an_architecture_label_is_detected(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "church.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_scene_classifier_stub,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["gebaeude"] == 0.8


async def test_gebaeude_criterion_best_effort_failure_does_not_fail_the_run_or_other_criteria(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Eigener Fehlerfall-Testlauf spezifisch fuer "gebaeude" (Akzeptanzkriterium der Spec: "Je
    # Kriterium mindestens ein eigener Fehlerfall-Testlauf, nicht nur ein generischer").
    class BrokenSceneClassifier:
        def classify(self, image: object) -> object:
            raise RuntimeError("Modell-Ladefehler")

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        # Ein Gesicht im Bild: seit Spec 0428 ist `goldener_schnitt` ohne Subjekt NICHT
        # MESSBAR und bliebe auch ohne den hier gepruueften Fehler ungeschrieben.
        build_detector=_single_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=BrokenSceneClassifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    # gebaeude haengt NICHT von detect_person/detect_objects ab - ein Fehler dort darf weder
    # goldener_schnitt (unbetroffen) noch tier/content_people mit sich reissen.
    assert "gebaeude" not in criteria
    assert "goldener_schnitt" in criteria
    assert "tier" in criteria
    assert "content_people" in criteria
    assert "aesthetics" in criteria  # haengt nicht von classify_scene ab


async def test_aesthetics_criterion_is_written_from_the_model_prediction(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    class HighRatingAestheticsModel:
        def predict(self, batch: object) -> object:
            return np.array([[0.0] * 8 + [0.1, 0.9]], dtype="float32")  # Erwartungswert nahe 10

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=HighRatingAestheticsModel,
        build_landmarker=_no_face_landmarker,
    )

    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["aesthetics"] > 0.95


async def test_aesthetics_criterion_best_effort_failure_does_not_fail_the_run_or_other_criteria(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Eigener Fehlerfall-Testlauf spezifisch fuer "aesthetics" (Akzeptanzkriterium der Spec: "Je
    # Kriterium mindestens ein eigener Fehlerfall-Testlauf, nicht nur ein generischer").
    class BrokenAestheticsModel:
        def predict(self, batch: object) -> object:
            raise RuntimeError("Modell-Ladefehler")

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        # Ein Gesicht im Bild: seit Spec 0428 ist `goldener_schnitt` ohne Subjekt NICHT
        # MESSBAR und bliebe auch ohne den hier gepruueften Fehler ungeschrieben.
        build_detector=_single_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=BrokenAestheticsModel,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert "aesthetics" not in criteria
    assert "gebaeude" in criteria
    assert "tier" in criteria
    assert "content_people" in criteria
    assert "goldener_schnitt" in criteria


async def test_freiraum_criterion_is_written_when_a_face_is_detected(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    # Gesicht weit links im Bild, nach rechts (steigendes x) gedreht -> viel Freiraum in
    # Blickrichtung (looking_space = 1 - 0.15 = 0.85, opposite_space = 0.05).
    stub = FaceLandmarkerStub(landmarks=[(0.05, 0.1), (0.15, 0.3)], matrix=_rotation_matrix_y(20.0))

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=lambda: stub,
    )

    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["freiraum"] == pytest.approx(0.85 / 0.9)


async def test_freiraum_criterion_best_effort_failure_does_not_fail_the_run_or_other_criteria(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Eigener Fehlerfall-Testlauf spezifisch fuer "freiraum" (Akzeptanzkriterium der Spec: "Je
    # Kriterium mindestens ein eigener Fehlerfall-Testlauf, nicht nur ein generischer") - der
    # detect()-Aufruf WAEHREND der Foto-Schleife schlaegt fehl (nicht der Builder selbst).
    class BrokenFaceLandmarker:
        def detect(self, image: object) -> object:
            raise RuntimeError("Modell-Ladefehler")

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        # Ein Gesicht im Bild: seit Spec 0428 ist `goldener_schnitt` ohne Subjekt NICHT
        # MESSBAR und bliebe auch ohne den hier gepruueften Fehler ungeschrieben.
        build_detector=_single_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=BrokenFaceLandmarker,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    # freiraum haengt NICHT von detect_person/detect_objects/build_aesthetics/build_classifier ab
    # - ein Fehler des eigenstaendigen face_landmarker darf keines der uebrigen Kriterien
    # mitreissen (ADR 0026 Punkt 3: eigenstaendiger, zusaetzlicher Modellaufruf).
    assert "freiraum" not in criteria
    assert "content_people" in criteria
    assert "goldener_schnitt" in criteria
    assert "tier" in criteria
    assert "gebaeude" in criteria
    assert "aesthetics" in criteria
    assert "symmetrie" in criteria
    assert "horizont" in criteria


async def test_freiraum_criterion_is_unaffected_by_a_failing_face_detector(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Umkehr-Test zu test_freiraum_criterion_best_effort_failure_does_not_fail_the_run_or_other_
    # criteria (test-engineer-Review-Fund): macht die "eigenstaendiger Modellaufruf, kein Ersatz"-
    # Eigenschaft aus ADR 0026 Punkt 3 in BEIDE Richtungen nachweisbar - ein fehlschlagender
    # face_detector darf freiraum (haengt nur vom eigenstaendigen face_landmarker ab) nicht
    # beeintraechtigen, exakt spiegelbildlich zum bereits bestehenden Test in der anderen
    # Richtung (fehlschlagender face_landmarker beeintraechtigt content_people/goldener_schnitt
    # nicht).
    class BrokenFaceDetector:
        def detect(self, image: object) -> object:
            raise RuntimeError("Modell-Ladefehler")

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    stub = FaceLandmarkerStub(landmarks=[(0.05, 0.1), (0.15, 0.3)], matrix=_rotation_matrix_y(20.0))

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=BrokenFaceDetector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=lambda: stub,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    # content_people/goldener_schnitt haengen vom (hier fehlgeschlagenen) face_detector ab und
    # bleiben ungeschrieben - freiraum haengt ausschliesslich vom eigenstaendigen face_landmarker
    # ab und wird trotzdem mit dem korrekten Wert geschrieben.
    assert "content_people" not in criteria
    assert "goldener_schnitt" not in criteria
    assert criteria["freiraum"] == pytest.approx(0.85 / 0.9)


async def test_freiraum_builder_failure_does_not_fail_the_run_or_unrelated_criteria(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Analog test_a_failing_model_builder_does_not_fail_the_run_or_unrelated_criteria, aber
    # spezifisch fuer den face_landmarker-Builder - schlaegt VOR der Foto-Schleife fehl.
    def _broken_face_landmarker_builder() -> NoFaceLandmarker:
        raise RuntimeError("Modell-Asset fehlt/ist defekt")

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_broken_face_landmarker_builder,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert "freiraum" not in criteria
    assert "content_people" in criteria
    assert "sharpness" in criteria
    assert "exposure" in criteria


async def test_goldener_schnitt_best_effort_failure_when_face_detection_fails(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Eigener, von der Tier-Fehlerfall-Variante UNTERSCHIEDLICHER Ausloeser (Face- statt
    # Animal-Detektor) - goldener_schnitt haengt von BEIDEN Detektionen ab, faellt also auch bei
    # einem reinen Face-Detector-Fehler aus, obwohl der Animal-Detektor erfolgreich war.
    class BrokenFaceDetector:
        def detect(self, image: object) -> object:
            raise RuntimeError("Modell-Ladefehler")

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=BrokenFaceDetector,
        build_animal_detector=_animal_detector_stub,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert "content_people" not in criteria
    assert "goldener_schnitt" not in criteria
    assert "tier" in criteria  # haengt nur vom (hier funktionierenden) Animal-Detektor ab


async def test_goldener_schnitt_is_left_out_when_both_detections_succeed_without_a_subject(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    # Weder Gesicht noch Tier erkannt (beide Detektoren liefern erfolgreich eine leere Liste) -
    # seit Spec 0428 heisst das NICHT MESSBAR: das Kriterium wird weggelassen statt als
    # schlechter Wert (0.0) geschrieben. "sharpness" steht daneben und zeigt, dass der Lauf
    # ueberhaupt Kriterien geschrieben hat.
    assert "goldener_schnitt" not in criteria
    assert "sharpness" in criteria


async def test_detect_person_and_detect_objects_are_each_called_at_most_once_per_photo(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Wiederverwendungsnachweis via Spy/Aufrufzaehler (Akzeptanzkriterium der Spec 0038, weiterhin
    # VERBINDLICH nach specs/features/0289-feste-kategorien.md): content_people UND
    # goldener_schnitt teilen sich EINEN detect_person-Aufruf; tier, fahrzeug, essen_trinken UND
    # goldener_schnitt teilen sich EINEN detect_objects-Aufruf - obwohl seit Spec 0289 DREI
    # Kriterien plus goldener_schnitt an der Objekt-Ausgabe haengen, laeuft der COCO-Detektor
    # weiterhin genau einmal pro Foto.
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    write_display_variant(tmp_path, photo, _flat_image())

    face_detector = CountingDetector()
    animal_detector = CountingDetector()

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=lambda: face_detector,
        build_animal_detector=lambda: animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert face_detector.call_count == 1
    assert animal_detector.call_count == 1


async def test_photo_rankings_contain_the_full_candidate_pool_per_partition(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photos = []
    for i in range(3):
        photo = await _add_photo(
            db_session, project, f"{i}.jpg", f"etag-{i}", datetime(2023, 1, 1, 0, i, tzinfo=UTC)
        )
        await _add_score(db_session, photo, sharpness=float(50 + i * 20), exposure=0.0)
        write_display_variant(tmp_path, photo, _flat_image())
        # Seit Spec 0428 traegt nur ein Foto MIT Modellbewertung einen Qualitaetswert - ohne sie
        # stuende in beiden Rangspalten `NULL`, und dieser Fall pruefte die Partitionierung nicht
        # mehr.
        await _add_album_suitability(db_session, photo)
        photos.append(photo)

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    rankings = (
        (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    # Voller Pool (nicht nur Top-N) - alle 3 Fotos landen ausserdem in derselben Partition
    # (gleiches Event), und jedes steht in GENAU EINER Zeile.
    assert len(rankings) == 3
    by_photo = {r.photo_id: r for r in rankings}
    assert len(by_photo) == 3
    assert len({by_photo[p.id].event_id for p in photos}) == 1
    positions = sorted(r.rank_position for r in rankings)
    assert positions == [1, 2, 3]
    # Hoehere Schaerfe -> hoeherer rank_score -> rank_position 1.
    assert by_photo[photos[2].id].rank_position == 1


async def test_partitions_are_isolated_by_event(db_session: AsyncSession, tmp_path: Path) -> None:
    """Einen Tag auseinander - Zeitluecke UND Kalendertagsgrenze trennen die beiden Fotos in zwei
    Events, und jedes ist Erstplatziertes seiner eigenen Partition."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    first = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, first, cluster_key="cluster-a")
    write_display_variant(tmp_path, first, _flat_image())
    await _add_album_suitability(db_session, first)

    second = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 2, tzinfo=UTC)
    )
    await _add_score(db_session, second, cluster_key="cluster-b")
    write_display_variant(tmp_path, second, _flat_image())
    await _add_album_suitability(db_session, second)

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    rankings = (
        (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    # Beide Events haben je genau 1 Foto -> je rank_position 1, unabhaengig voneinander.
    assert {r.rank_position for r in rankings} == {1}
    assert len({r.event_id for r in rankings}) == 2


async def test_progress_is_committed_periodically(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: object
) -> None:

    monkeypatch.setattr(worker_local, "CRITERION_SCORING_COMMIT_BATCH_SIZE", 1)  # type: ignore[attr-defined]

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    for i in range(3):
        photo = await _add_photo(
            db_session, project, f"{i}.jpg", f"etag-{i}", datetime(2023, 1, 1, 0, i, tzinfo=UTC)
        )
        await _add_score(db_session, photo)
        write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.photos_total == 3
    assert run.photos_processed == 3


async def test_criterion_scoring_updates_last_progress_at_at_each_checkpoint(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: object
) -> None:

    monkeypatch.setattr(worker_local, "CRITERION_SCORING_COMMIT_BATCH_SIZE", 1)  # type: ignore[attr-defined]
    sentinel = datetime(2030, 1, 1, 12, 0, 0)
    monkeypatch.setattr(worker_runs, "now_utc", lambda: sentinel)  # type: ignore[attr-defined]

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.last_progress_at == sentinel


async def test_run_marked_failed_on_cancelled_error(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Schicht 1 des Fortschritts-Watchdogs (specs/features/0034-scan-haenger-fortschritts-
    watchdog.md, ADR 0019), Pendant fuer den neuen Job - detector.detect wirft mitten in der
    Kriterien-Schleife asyncio.CancelledError, propagiert unveraendert."""

    class CancellingDetector:
        def detect(self, image: object) -> object:
            raise asyncio.CancelledError()

    project = await _make_project(db_session)
    project_id = project.id
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    try:
        await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=CancellingDetector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_no_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
        )
        raised = False
    except asyncio.CancelledError:
        raised = True

    assert raised
    run = (
        await db_session.execute(
            select(CriterionScoringRun).where(CriterionScoringRun.project_id == project_id)
        )
    ).scalar_one()
    assert run.status == ScanStatus.FAILED
    assert run.error_message


async def test_rescoring_does_not_overwrite_ratings(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """ADR 0021 Punkt 7: bereits vom Nutzer gesetzte Rating-Zeilen ueberleben ein Re-Scoring
    unverandert - der Job hat gar keinen Schreibzugriff auf ratings, dieser Test dokumentiert das
    strukturell (kein Rating-Import/-Code in run_criterion_scoring)."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    first_run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )
    second_run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert first_run.status == ScanStatus.SUCCESS
    assert second_run.status == ScanStatus.SUCCESS
    assert first_run.id != second_run.id


async def test_end_to_end_with_run_project_scoring(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Integrationsnachweis: run_project_scoring (Phase A) gefolgt von run_criterion_scoring auf
    demselben, tatsaechlich zurueckgegebenen scoring_run.id - kein manuell konstruierter
    ScoringRun."""
    project = await _make_project(db_session)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    write_display_variant(tmp_path, photo, _flat_image())

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)
    assert scoring_run.gate_confirmed_at is not None  # keine Duplikate/Unschaerfe -> Auto-Gate

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.SUCCESS
    rankings = (
        (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rankings) == 1


def _single_face_detector() -> SingleFaceDetector:
    return SingleFaceDetector()
