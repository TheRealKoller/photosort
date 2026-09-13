from __future__ import annotations

import asyncio
import json
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn
from uuid import uuid4

import httpx
import numpy as np
import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import pricing, worker
from photosort.album_suitability import normalize_level
from photosort.cloud_vision import (
    VISION_MODELS_BY_PROVIDER,
    CloudRequestThrottle,
    ThrottleStats,
    TokenUsage,
    default_vision_model_for_provider,
)
from photosort.criteria import CRITERIA_REGISTRY
from photosort.landmark import (
    MAX_LANDMARK_NAME_LENGTH,
    AnthropicLandmarkClient,
    LandmarkApiError,
    LandmarkDetection,
)
from photosort.models import (
    ClassificationPhase,
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    Event,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoLandmarkDetection,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    PhotoRanking,
    PhotoScore,
    Project,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motif_strengths import load_effective_strengths, upsert_assessment
from photosort.motifs import MOTIF_REGISTRY
from photosort.pricing import compute_cost_usd
from photosort.quality import LOCAL_CORRECTION_SPAN
from photosort.thumbnails import display_path
from photosort.worker import _select_landmark_candidates, run_criterion_scoring, run_project_scoring
from tests.run_bookkeeping import assert_call_bookkeeping_invariant


async def _make_project(session: AsyncSession, *, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id=f"drive-{name}", opencloud_path=name)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_photo(
    session: AsyncSession,
    project: Project,
    path: str,
    etag: str,
    taken_at: datetime,
    *,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=etag,
        content_length=100,
        taken_at=taken_at,
        taken_at_original=taken_at,
        last_modified=taken_at,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _add_score(
    session: AsyncSession,
    photo: Photo,
    *,
    sharpness: float = 100.0,
    exposure: float = 0.0,
    cluster_key: str | None = "cluster-0",
    suggested_status: RatingStatus | None = None,
) -> PhotoScore:
    score = PhotoScore(
        photo_id=photo.id,
        sharpness=sharpness,
        exposure=exposure,
        cluster_key=cluster_key,
        suggested_status=suggested_status,
        computed_at=datetime.now(UTC),
    )
    session.add(score)
    await session.commit()
    return score


async def _add_successful_scoring_run(
    session: AsyncSession, project: Project, *, started_at: datetime | None = None
) -> ScoringRun:
    run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    if started_at is not None:
        run.started_at = started_at
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


def _write_display_variant(cache_dir: Path, photo: Photo, image: Image.Image) -> None:
    path = display_path(cache_dir, photo.id, photo.etag)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG")


def _flat_image(color: tuple[int, int, int] = (100, 100, 100), size: int = 160) -> Image.Image:
    return Image.new("RGB", (size, size), color=color)


class NoFaceDetector:
    """Faket den mediapipe FaceDetector so, dass nie ein Gesicht gefunden wird - der injizierte
    build_detector-Callable ersetzt worker.py::build_face_detector, kein echtes .tflite-Modell in
    Tests (Teststrategie-Abschnitt der Spec)."""

    def detect(self, image: object) -> object:
        return SimpleNamespace(detections=[])


def _no_face_detector() -> NoFaceDetector:
    return NoFaceDetector()


class NoAnimalDetector:
    """Faket den mediapipe ObjectDetector so, dass nie ein Tier gefunden wird - der injizierte
    build_animal_detector-Callable ersetzt worker.py::build_object_detector (specs/features/0038:
    build_object_detector darf wie build_face_detector NIE in einem automatisierten Test
    aufgerufen werden, kein echtes .tflite-Modell in Tests)."""

    def detect(self, image: object) -> object:
        return SimpleNamespace(detections=[])


def _no_animal_detector() -> NoAnimalDetector:
    return NoAnimalDetector()


class NoSceneLabels:
    """Faket den mediapipe ImageClassifier so, dass keine Szenen-Kategorie gefunden wird - der
    injizierte build_classifier-Callable ersetzt worker.py::build_scene_classifier
    (specs/features/0038: build_scene_classifier darf wie build_face_detector NIE in einem
    automatisierten Test aufgerufen werden, kein echtes .tflite-Modell in Tests)."""

    def classify(self, image: object) -> object:
        return SimpleNamespace(classifications=[SimpleNamespace(categories=[])])


def _no_scene_classifier() -> NoSceneLabels:
    return NoSceneLabels()


class NeutralAestheticsModel:
    """Faket das Keras-Modell so, dass eine neutrale, gleichverteilte NIMA-Ratingverteilung
    zurueckgegeben wird - der injizierte build_aesthetics-Callable ersetzt
    worker.py::build_aesthetics_model (specs/features/0038: build_aesthetics_model darf wie
    build_face_detector NIE in einem automatisierten Test aufgerufen werden, kein echtes
    tensorflow-Modell in Tests)."""

    def predict(self, batch: object) -> object:
        return np.array([[0.1] * 10], dtype="float32")


def _no_aesthetics_model() -> NeutralAestheticsModel:
    return NeutralAestheticsModel()


class NoFaceLandmarker:
    """Faket den mediapipe FaceLandmarker so, dass nie ein Gesicht gefunden wird - der injizierte
    build_landmarker-Callable ersetzt worker.py::build_face_landmarker (specs/features/0048-
    kompositions-kriterien-symmetrie-horizont-freiraum.md: build_face_landmarker darf wie
    build_face_detector NIE in einem automatisierten Test aufgerufen werden, kein echtes
    .task-Modell in Tests)."""

    def detect(self, image: object) -> object:
        return SimpleNamespace(face_landmarks=[], facial_transformation_matrixes=[])


def _no_face_landmarker() -> NoFaceLandmarker:
    return NoFaceLandmarker()


def _rotation_matrix_y(degrees_value: float) -> np.ndarray:
    # Analog test_classification.py::_rotation_matrix_y (Konvention siehe classification.py::
    # _yaw_degrees_from_rotation_matrix-Docstring) - kleine, bewusste Duplikation statt einer
    # Test-Utility-Abhaengigkeit zwischen zwei Testdateien.
    theta = math.radians(degrees_value)
    matrix = np.eye(4)
    matrix[0, 0] = math.cos(theta)
    matrix[0, 2] = math.sin(theta)
    matrix[2, 0] = -math.sin(theta)
    matrix[2, 2] = math.cos(theta)
    return matrix


class FaceLandmarkerStub:
    """Faket den mediapipe FaceLandmarker so, dass GENAU EIN Gesicht mit konfigurierbarer
    Blickrichtung gefunden wird (specs/features/0048) - analog AnimalDetectorStub/
    SceneClassifierStub."""

    def __init__(
        self,
        landmarks: list[tuple[float, float]] | None = None,
        matrix: np.ndarray | None = None,
    ) -> None:
        self._landmarks = landmarks if landmarks is not None else [(0.3, 0.2), (0.5, 0.8)]
        self._matrix = matrix if matrix is not None else np.eye(4)

    def detect(self, image: object) -> object:
        return SimpleNamespace(
            face_landmarks=[[SimpleNamespace(x=x, y=y) for x, y in self._landmarks]],
            facial_transformation_matrixes=[self._matrix],
        )


async def test_guard_fails_run_when_scoring_run_id_does_not_exist(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run_id=999,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.FAILED
    assert run.error_message is not None


async def test_guard_fails_run_when_scoring_run_id_is_stale(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # ADR 0021 Punkt 7 / Akzeptanzkriterium der Spec: ein Re-Scan/Re-Scoring waehrend der
    # Kuratierung erzeugt einen NEUEN erfolgreichen ScoringRun - ein Aufruf mit der ALTEN id wird
    # als stale abgelehnt, kein CriterionScoringRun-Erfolg auf veraltetem cluster_key-Stand.
    project = await _make_project(db_session)
    stale_run = await _add_successful_scoring_run(
        db_session, project, started_at=datetime(2023, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    )
    await _add_successful_scoring_run(
        db_session, project, started_at=datetime(2023, 1, 2, tzinfo=UTC).replace(tzinfo=None)
    )

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run_id=stale_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.FAILED


async def test_guard_fails_run_when_latest_scoring_run_is_not_successful(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    run_row = ScoringRun(project_id=project.id, status=ScanStatus.FAILED)
    db_session.add(run_row)
    await db_session.commit()
    await db_session.refresh(run_row)

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run_id=run_row.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.FAILED


async def test_writes_sharpness_and_exposure_criteria_from_existing_photo_score(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.1)
    _write_display_variant(tmp_path, photo, _flat_image())

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
    criteria = {
        c.criterion_key: c
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["sharpness"].value == 0.5  # 100.0 / 200.0 ceiling
    assert criteria["exposure"].value == 0.9  # 1.0 - 0.1
    assert criteria["content_landscape"].value > 0.9  # flat image
    assert criteria["content_people"].value == 0.0  # no face detector
    assert criteria["symmetrie"].value == 1.0  # flat image, keine Asymmetrie messbar


async def test_symmetrie_criterion_is_written_unconditionally_like_content_landscape(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md, ADR 0026: keine
    # Modell-/Detektor-Abhaengigkeit fuer symmetrie - wird wie content_landscape UNCONDITIONAL
    # berechnet, unabhaengig davon, ob irgendein Detektor/Modell erfolgreich gebaut wurde.
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    _write_display_variant(tmp_path, photo, _flat_image())

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
    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["symmetrie"] == 1.0


async def test_horizont_criterion_is_written_unconditionally_like_content_landscape(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # specs/features/0048-kompositions-kriterien-symmetrie-horizont-freiraum.md, ADR 0026 Punkt 2:
    # klassischer cv2-Algorithmus ohne trainiertes Modell - keine Detektor-Abhaengigkeit, wird wie
    # content_landscape/symmetrie UNCONDITIONAL berechnet. Ein voellig flaechiges Testbild hat
    # keine Kanten/Linien -> neutraler Fallback-Wert 0.5 (kein Kandidat gefunden).
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    _write_display_variant(tmp_path, photo, _flat_image())

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
    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["horizont"] == 0.5


async def test_upserts_existing_criterion_score_instead_of_duplicating(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=100.0, exposure=0.0)
    _write_display_variant(tmp_path, photo, _flat_image())

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
    # Zweiter Lauf mit geaenderten Rohwerten - der bestehende Wert wird ueberschrieben (Upsert),
    # keine zweite Zeile (UniqueConstraint(photo_id, criterion_key)).
    photo_score = (
        await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    ).scalar_one()
    photo_score.sharpness = 200.0
    await db_session.commit()

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

    rows = (
        (
            await db_session.execute(
                select(PhotoCriterionScore).where(
                    PhotoCriterionScore.photo_id == photo.id,
                    PhotoCriterionScore.criterion_key == "sharpness",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].value == 1.0  # 200.0 / 200.0 ceiling, geklemmt


async def test_only_considers_ausschuss_survivors(db_session: AsyncSession, tmp_path: Path) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    rejected = await _add_photo(
        db_session, project, "rejected.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, rejected, cluster_key=None, suggested_status=RatingStatus.REJECTED)
    _write_display_variant(tmp_path, rejected, _flat_image())

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
    assert run.photos_total == 0
    criteria = (
        (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == rejected.id)
            )
        )
        .scalars()
        .all()
    )
    assert criteria == []


async def test_best_effort_content_criteria_failure_does_not_fail_the_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    broken = await _add_photo(
        db_session, project, "broken.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, broken, sharpness=100.0, exposure=0.0)
    # broken.jpg hat KEINE lesbare display-Cache-Datei (fehlt) - Inhalts-Kriterien scheitern
    # best-effort, sharpness/exposure werden trotzdem geschrieben (kein erneuter Bildzugriff
    # noetig).

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
    criteria = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == broken.id)
            )
        ).scalars()
    }
    assert criteria == {"sharpness", "exposure"}


class AnimalDetectorStub:
    """Faket den mediapipe ObjectDetector so, dass GENAU EIN Tier gefunden wird (specs/features/
    0038) - analog NoAnimalDetector, aber mit einem echten Treffer statt einer leeren Liste."""

    def __init__(self, category: str = "dog", score: float = 0.9) -> None:
        self._category = category
        self._score = score

    def detect(self, image: object) -> object:
        return SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=[SimpleNamespace(category_name=self._category, score=self._score)],
                    bounding_box=SimpleNamespace(origin_x=10, origin_y=10, width=40, height=40),
                )
            ]
        )


def _animal_detector_stub() -> AnimalDetectorStub:
    return AnimalDetectorStub()


class SceneClassifierStub:
    """Faket den mediapipe ImageClassifier so, dass GENAU EINE (architekturbezogene) Kategorie
    gefunden wird - analog AnimalDetectorStub."""

    def __init__(self, category: str = "church", score: float = 0.8) -> None:
        self._category = category
        self._score = score

    def classify(self, image: object) -> object:
        return SimpleNamespace(
            classifications=[
                SimpleNamespace(
                    categories=[SimpleNamespace(category_name=self._category, score=self._score)]
                )
            ]
        )


def _scene_classifier_stub() -> SceneClassifierStub:
    return SceneClassifierStub()


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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
        _write_display_variant(tmp_path, photo, _flat_image())
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
    _write_display_variant(tmp_path, first, _flat_image())
    await _add_album_suitability(db_session, first)

    second = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 2, tzinfo=UTC)
    )
    await _add_score(db_session, second, cluster_key="cluster-b")
    _write_display_variant(tmp_path, second, _flat_image())
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
    import photosort.worker as worker_module

    monkeypatch.setattr(worker_module, "CRITERION_SCORING_COMMIT_BATCH_SIZE", 1)  # type: ignore[attr-defined]

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    for i in range(3):
        photo = await _add_photo(
            db_session, project, f"{i}.jpg", f"etag-{i}", datetime(2023, 1, 1, 0, i, tzinfo=UTC)
        )
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo, _flat_image())

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
    import photosort.worker as worker_module

    monkeypatch.setattr(worker_module, "CRITERION_SCORING_COMMIT_BATCH_SIZE", 1)  # type: ignore[attr-defined]
    sentinel = datetime(2030, 1, 1, 12, 0, 0)
    monkeypatch.setattr(worker_module, "_now_utc", lambda: sentinel)  # type: ignore[attr-defined]

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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
    _write_display_variant(tmp_path, photo, _flat_image())

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


# specs/features/0289-feste-kategorien.md, ADR 0049 ab hier: die Kategorie eines Fotos ist eine
# reine PRO-FOTO-Funktion ueber einem geschlossenen Set. Die frueher hier getesteten
# haeufigkeitsabhaengigen Faelle (derive_active_categories-Ein-Aufruf-Spy, "identischer tier-Score
# landet je nach Lauf in einer anderen Kategorie") sind mit der abgeloesten Aggregation
# ersatzlos entfallen - ihr fachlicher Kern ("welches Foto bekommt welche Kategorie") wird jetzt
# durch die Vereinigungs-/Herkunftsneutralitaets-Tests weiter unten abgedeckt.

# Beliebige, von der Standard-Testbildgroesse (160) abweichende Bildgroesse - dient als
# deterministischer Marker fuer "dieses Foto soll ein Tier enthalten", unabhaengig von der
# (nicht garantierten) DB-Verarbeitungsreihenfolge - robuster als ein reiner Aufruf-Counter im
# Fake-Detektor, der implizit von der Zeilenreihenfolge abhinge.
_ANIMAL_MARKER_SIZE = 168


def _animal_marked_image() -> Image.Image:
    # Textur statt einer flachen Farbe (Abgrenzung zu _flat_image): ein Marker-Foto soll NICHT
    # gleichzeitig ein anderes Signal ausloesen.
    from PIL import ImageDraw

    image = Image.new("RGB", (_ANIMAL_MARKER_SIZE, _ANIMAL_MARKER_SIZE), color=(30, 60, 120))
    draw = ImageDraw.Draw(image)
    for offset in range(0, _ANIMAL_MARKER_SIZE, 8):
        draw.line(
            (offset, 0, _ANIMAL_MARKER_SIZE - offset, _ANIMAL_MARKER_SIZE),
            fill=(220, 180, 90),
            width=2,
        )
    return image


class SizeGatedAnimalDetector:
    """Faket den mediapipe ObjectDetector so, dass NUR Bilder mit der Marker-Groesse
    (_ANIMAL_MARKER_SIZE) ein Tier liefern - ermoeglicht ein deterministisches Szenario (einige
    Fotos mit, einige ohne Tier) im selben Lauf."""

    def detect(self, image: object) -> object:
        if getattr(image, "width", None) == _ANIMAL_MARKER_SIZE:
            return SimpleNamespace(
                detections=[
                    SimpleNamespace(
                        categories=[SimpleNamespace(category_name="dog", score=0.9)],
                        bounding_box=SimpleNamespace(origin_x=10, origin_y=10, width=40, height=40),
                    )
                ]
            )
        return SimpleNamespace(detections=[])


def _size_gated_animal_detector() -> SizeGatedAnimalDetector:
    return SizeGatedAnimalDetector()


async def _add_photos_with_optional_animal_marker(
    session: AsyncSession, project: Project, tmp_path: Path, *, total: int, marked: int
) -> list[Photo]:
    photos = []
    for i in range(total):
        photo = await _add_photo(
            session, project, f"{i}.jpg", f"etag-{i}", datetime(2023, 1, 1, 0, i, tzinfo=UTC)
        )
        await _add_score(session, photo, sharpness=100.0, exposure=0.0)
        image = _animal_marked_image() if i < marked else _flat_image()
        _write_display_variant(tmp_path, photo, image)
        photos.append(photo)
    return photos


def _textured_image_below_landscape_threshold() -> Image.Image:
    # Abgrenzung zu _flat_image (siehe dortiger Kommentar zu content_landscape oben) - Textur
    # statt flacher Farbe, damit ohne SceneClassifierStub weder content_landscape noch gebaeude
    # die Vorfilterungs-Schwelle erreichen.
    from PIL import ImageDraw

    image = Image.new("RGB", (160, 160), color=(30, 60, 120))
    draw = ImageDraw.Draw(image)
    for offset in range(0, 160, 8):
        draw.line((offset, 0, 160 - offset, 160), fill=(220, 180, 90), width=2)
    return image


class RecordingLandmarkClient:
    """Fake LandmarkClientLike (Teststrategie-Abschnitt der Spec), zeichnet jeden detect()-Aufruf
    auf - der Aufrufnachweis selbst ist der eigentliche Testgegenstand, nicht nur "keine
    landmark-Zeile in der DB" (das waere auch bei einem defekten, aber tatsaechlich aufgerufenen
    Client wahr)."""

    def __init__(
        self, detection: LandmarkDetection | None = None, raise_error: bool = False
    ) -> None:
        self._detection = (
            detection
            if detection is not None
            else LandmarkDetection(name="Eiffelturm", confidence=0.9)
        )
        self._raise_error = raise_error
        self.calls: list[tuple[bytes, str]] = []
        # Review-Fund (ship-feature-Runde): kein bisheriger Fake bot aclose() an, der
        # worker.py::run_criterion_scoring's `getattr(landmark_client, "aclose", None)`-Zweig
        # nahm deshalb immer den None-Pfad - ein versehentlich falsch benannter/entfernter Aufruf
        # waere unbemerkt geblieben. Zaehlt Aufrufe statt nur bool, damit ein Doppel-Close
        # ebenfalls auffiele.
        self.aclose_calls = 0

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
        self.calls.append((image_bytes, mime_type))
        if self._raise_error:
            raise LandmarkApiError("simulierter Cloud-Fehler")
        return self._detection

    async def aclose(self) -> None:
        self.aclose_calls += 1


class ConcurrencyTrackingLandmarkClient:
    """Analog FakeOpenCloudClient.max_concurrent_downloads (test_worker_scan_project.py) - zaehlt
    gleichzeitig aktive detect()-Aufrufe, kein Wall-Clock-Timing-Assertion."""

    def __init__(self) -> None:
        self._active = 0
        self.max_concurrent = 0
        self.call_count = 0

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
        self.call_count += 1
        self._active += 1
        self.max_concurrent = max(self.max_concurrent, self._active)
        try:
            await asyncio.sleep(0.01)
            return LandmarkDetection(name="Eiffelturm", confidence=0.9)
        finally:
            self._active -= 1


class PerPhotoLandmarkClient:
    """Liefert unterschiedliche Detections/Fehler je Aufrufindex (analog PerPhotoCategoryClient
    in test_worker_remote_category_classification.py) - fuer Tests mit mehreren gleichzeitig
    fehlschlagenden Fotos im selben Nebenlaeufigkeits-Block."""

    def __init__(self, results: list[LandmarkDetection | Exception]) -> None:
        self._results = results
        self.calls = 0

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
        result = self._results[self.calls]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return result


class CancellingLandmarkClient:
    """Simuliert einen asyncio.CancelledError WAEHREND eines parallelen detect()-Aufrufs (ADR
    0025, analog DownloadRaisesCancelledErrorClient in test_worker_scan_project.py) -
    Regressionsnachweis, dass return_exceptions=True das CancelledError nicht verschluckt."""

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
        raise asyncio.CancelledError("simulierter Abbruch waehrend eines parallelen Cloud-Aufrufs")


def _failing_landmark_client_builder(model: str) -> NoReturn:
    pytest.fail("build_landmark_client darf bei deaktivierter Einwilligung nie aufgerufen werden")


class TestSelectLandmarkCandidates:
    """Reine, DB-freie Funktion (analog _classify_scan_entries) - isoliert testbar, inkl. dem
    Grenzfall exakt auf der Schwelle, ohne einen echten Kandidatenlauf aufzusetzen."""

    def test_below_both_thresholds_is_not_a_candidate(self) -> None:
        candidate_values = {1: {"landschaft": 0.0, "gebaeude": 0.0}}
        assert _select_landmark_candidates(candidate_values, set()) == []

    def test_landschaft_at_exactly_the_threshold_is_a_candidate_inclusive(self) -> None:
        # specs/features/0217, ADR 0047 Punkt 5: Vorfilterung auf `landschaft` statt
        # `content_landscape` UMGESTELLT (nicht ergaenzt).
        candidate_values = {1: {"landschaft": 0.01, "gebaeude": 0.0}}
        assert _select_landmark_candidates(candidate_values, set()) == [1]

    def test_gebaeude_at_exactly_the_threshold_is_a_candidate_inclusive(self) -> None:
        candidate_values = {1: {"landschaft": 0.0, "gebaeude": 0.01}}
        assert _select_landmark_candidates(candidate_values, set()) == [1]

    def test_just_below_landschaft_threshold_is_not_a_candidate(self) -> None:
        candidate_values = {1: {"landschaft": 0.009, "gebaeude": 0.0}}
        assert _select_landmark_candidates(candidate_values, set()) == []

    def test_a_high_content_landscape_value_alone_is_no_longer_a_candidate(self) -> None:
        assert _select_landmark_candidates({1: {"content_landscape": 1.0}}, set()) == []

    def test_missing_values_count_as_not_present(self) -> None:
        assert _select_landmark_candidates({1: {}}, set()) == []

    def test_already_scored_photo_is_excluded_even_if_it_would_pass_the_threshold(self) -> None:
        candidate_values = {1: {"landschaft": 0.9}}
        assert _select_landmark_candidates(candidate_values, {1}) == []


async def test_consent_disabled_by_default_never_calls_landmark_client_builder(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

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
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria_keys = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert "landmark" not in criteria_keys


async def test_consent_enabled_sends_a_landscape_photo_to_the_landmark_client(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    client = RecordingLandmarkClient(
        detection=LandmarkDetection(name="Eiffelturm", confidence=0.87)
    )

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert len(client.calls) == 1
    image_bytes, mime_type = client.calls[0]
    assert mime_type == "image/jpeg"
    assert image_bytes  # echte Bilddaten, kein leerer Platzhalter
    # Review-Fund (ship-feature-Runde): run_criterion_scoring muss einen vom Client angebotenen
    # aclose() tatsaechlich aufrufen (Ressourcen-Cleanup des echten httpx.AsyncClient), genau
    # einmal - kein Doppel-Close.
    assert client.aclose_calls == 1

    criteria = {
        c.criterion_key: c
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["landmark"].value == 0.87
    assert criteria["landmark"].source == CriterionSource.CLOUD

    detection_row = (
        await db_session.execute(
            select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
        )
    ).scalar_one()
    assert detection_row.name == "Eiffelturm"
    assert detection_row.confidence == 0.87
    # specs/features/0054-mistral-provider-option-cloud-landmark.md: unveraendertes
    # LANDMARK_PROVIDER (Default) -> "anthropic" wird atomar mit name/confidence persistiert.
    assert detection_row.provider == "anthropic"


# specs/features/0054-mistral-provider-option-cloud-landmark.md, decisions/0031-mistral-provider-
# option-cloud-landmark.md Punkt 5 ab hier: provider-Wert wird korrekt persistiert +
# Umschalt-Regressionstest (altes provider-Feld bleibt bei einem Providerwechsel unveraendert -
# das bestehende Skip-Verhalten fuer bereits gescorte Fotos, ADR 0025 Punkt 3, greift providerun-
# abhaengig weiterhin).


async def test_landmark_detection_row_persists_the_configured_provider(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "landmark_provider", "mistral")
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    client = RecordingLandmarkClient(detection=LandmarkDetection(name="Eiffelturm", confidence=0.9))

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    detection_row = (
        await db_session.execute(
            select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
        )
    ).scalar_one()
    assert detection_row.provider == "mistral"


async def test_provider_switch_between_runs_does_not_overwrite_the_stored_provider(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    first_client = RecordingLandmarkClient(
        detection=LandmarkDetection(name="Eiffelturm", confidence=0.87)
    )
    first_run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: first_client,
        use_cloud=True,
    )
    assert first_run.status == ScanStatus.SUCCESS
    assert len(first_client.calls) == 1

    # LANDMARK_PROVIDER wird "mitten im Projektverlauf" umgeschaltet (ADR 0031 Punkt 5) - das
    # bereits gescorte Foto bleibt aber ein Skip-Kandidat (existierende PhotoCriterionScore-Zeile),
    # der Client wird fuer dieses Foto also gar nicht erneut aufgerufen.
    monkeypatch.setattr(worker.settings, "landmark_provider", "mistral")
    second_client = RecordingLandmarkClient(
        detection=LandmarkDetection(name="Kolosseum", confidence=0.5)
    )
    second_run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: second_client,
        use_cloud=True,
    )

    assert second_run.status == ScanStatus.SUCCESS
    assert second_client.calls == []  # nicht erneut gesendet (bestehendes Skip-Verhalten)

    detection_row = (
        await db_session.execute(
            select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
        )
    ).scalar_one()
    # provider bleibt beim alten Wert stehen, wird nicht ueberschrieben (Akzeptanzkriterium).
    assert detection_row.provider == "anthropic"
    assert detection_row.name == "Eiffelturm"


async def test_photo_without_an_identified_landmark_name_gets_zero_score_and_no_detection_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    client = RecordingLandmarkClient(detection=LandmarkDetection(name=None, confidence=0.0))

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
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
    assert criteria["landmark"] == 0.0

    detections = (await db_session.execute(select(PhotoLandmarkDetection))).scalars().all()
    assert detections == []


async def test_vorfilterung_sends_photo_that_only_meets_the_gebaeude_threshold(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _textured_image_below_landscape_threshold())

    client = RecordingLandmarkClient()

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_scene_classifier_stub,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert len(client.calls) == 1


async def test_vorfilterung_does_not_send_photo_below_both_thresholds_empty_candidate_pool(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Zugleich der "leerer Kandidatenpool nach Vorfilterung"-Edge-Case der Teststrategie: das
    # einzige Foto des Laufs erreicht weder content_landscape noch gebaeude, LandmarkClientLike.
    # detect() wird nie aufgerufen, kein photo_landmark_detections-Eintrag.
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _textured_image_below_landscape_threshold())

    client = RecordingLandmarkClient()

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
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == []
    detections = (await db_session.execute(select(PhotoLandmarkDetection))).scalars().all()
    assert detections == []


async def test_skip_already_scored_photo_but_local_criteria_are_recomputed(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=50.0)
    _write_display_variant(tmp_path, photo, _flat_image())

    db_session.add(
        PhotoCriterionScore(
            photo_id=photo.id,
            criterion_key="landmark",
            value=0.42,
            source=CriterionSource.CLOUD,
            computed_at=datetime(2023, 1, 1),
        )
    )
    await db_session.commit()

    client = RecordingLandmarkClient()

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
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == []  # nicht erneut gesendet, obwohl die Vorfilterung erneut passen wuerde

    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["landmark"] == 0.42  # unveraendert stehen geblieben
    assert criteria["sharpness"] == 0.25  # 50.0 / 200.0 - trotzdem neu berechnet (nur landmark
    # ist die Ausnahme vom "jeder Lauf scort neu"-Grundsatz, kein versehentliches Ueberspringen
    # des gesamten Fotos).


async def test_failed_landmark_call_leaves_no_row_and_becomes_a_candidate_again_next_run(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    failing_client = RecordingLandmarkClient(raise_error=True)

    # Spec 0056/ADR 0034: der fehlgeschlagene Cloud-Aufruf muss genau einen WARNING-Log-Eintrag
    # erzeugen, bevor das bestehende continue greift.
    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        run = await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_landscape_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=lambda _model: failing_client,
            use_cloud=True,
        )

    assert run.status == ScanStatus.SUCCESS  # best-effort, kein Laufabbruch
    assert len(failing_client.calls) == 1
    # aclose() muss auch dann laufen, wenn der Cloud-Aufruf selbst fehlschlaegt (finally-Block).
    assert failing_client.aclose_calls == 1
    criteria_keys = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert "landmark" not in criteria_keys
    # Andere Kriterien dieses Fotos bleiben unberuehrt.
    assert "sharpness" in criteria_keys
    assert "content_landscape" in criteria_keys

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.name == "photosort.worker"
    assert record.levelno == logging.WARNING
    assert record.exc_info is None  # ADR 0034 Punkt 5: kein exc_info=True/Traceback.
    assert "LandmarkApiError" in record.message
    assert str(photo.id) in record.message
    assert photo.relative_path in record.message
    assert "landmark" in record.message.lower()

    succeeding_client = RecordingLandmarkClient()
    run2 = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: succeeding_client,
        use_cloud=True,
    )

    assert run2.status == ScanStatus.SUCCESS
    # kein landmark-Eintrag vorhanden -> automatisch erneut Kandidat (ersetzt einen dedizierten
    # Retry-Mechanismus, ADR 0025 Punkt 3).
    assert len(succeeding_client.calls) == 1


# specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
# fehler-persistierung.md Punkt 2/3 ab hier: worker.py::_record_cloud_vision_error/
# _clear_cloud_vision_error - eigene DB-Zustands-Tests, unabhaengig von der API-Sichtbarkeit
# (Teststrategie-Abschnitt der Spec).


async def test_failed_landmark_call_persists_a_cloud_vision_error_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    failing_client = RecordingLandmarkClient(raise_error=True)

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: failing_client,
        use_cloud=True,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    stored = result.scalar_one()
    assert stored.phase == CloudVisionPhase.LANDMARK
    assert stored.error_type == "LandmarkApiError"
    assert "simulierter Cloud-Fehler" in stored.error_message
    assert stored.attempted_at is not None


async def test_successful_landmark_call_after_a_previous_failure_clears_the_error_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: RecordingLandmarkClient(raise_error=True),
        use_cloud=True,
    )
    assert (
        await db_session.execute(
            select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
        )
    ).scalar_one_or_none() is not None

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: RecordingLandmarkClient(),
        use_cloud=True,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    assert result.scalar_one_or_none() is None


async def test_successful_landmark_call_without_a_name_still_clears_the_error_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # specs/architecture/0002-testkonzept.md ("Read-Time-Prioritaets-Kaskade..." fuer ADR 0035):
    # "Landmark-Erfolg ohne erkannten Namen (no_result) loescht eine vorher bestehende Fehler-
    # Zeile ebenfalls" - eigener Testfall, der das explizit vom Erfolgspfad MIT Namen (RESULT,
    # siehe test_successful_landmark_call_after_a_previous_failure_clears_the_error_row oben)
    # abgrenzt: hier bleibt die PhotoLandmarkDetection-Zeile bewusst aus (detection.name is None),
    # trotzdem muss die Fehler-Zeile geloescht werden - der Loesch-Aufruf haengt am erfolgreichen
    # Cloud-Aufruf selbst, nicht an der (bedingten) PhotoLandmarkDetection-Anlage.
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: RecordingLandmarkClient(raise_error=True),
        use_cloud=True,
    )
    assert (
        await db_session.execute(
            select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
        )
    ).scalar_one_or_none() is not None

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: RecordingLandmarkClient(
            detection=LandmarkDetection(name=None, confidence=0.0)
        ),
        use_cloud=True,
    )

    error_result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    assert error_result.scalar_one_or_none() is None

    detection_result = await db_session.execute(
        select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
    )
    assert detection_result.scalar_one_or_none() is None  # kein Name -> keine Detection-Zeile.

    criterion_result = await db_session.execute(
        select(PhotoCriterionScore).where(
            PhotoCriterionScore.photo_id == photo.id,
            PhotoCriterionScore.criterion_key == "landmark",
        )
    )
    assert criterion_result.scalar_one().value == 0.0  # no_result-Signal bleibt bestehen.


async def test_repeated_landmark_failures_upsert_the_same_error_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    class _RaisingClient:
        def __init__(self, message: str) -> None:
            self._message = message

        async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
            raise LandmarkApiError(self._message)

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: _RaisingClient("erster Fehlschlag"),
        use_cloud=True,
    )
    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: _RaisingClient("zweiter Fehlschlag"),
        use_cloud=True,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1  # Upsert, kein Verlauf (composite PK photo_id+phase).
    assert "zweiter Fehlschlag" in rows[0].error_message
    assert "erster Fehlschlag" not in rows[0].error_message


async def test_landmark_error_message_is_capped_at_500_characters(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    overlong_message = "x" * 600

    class _RaisingClient:
        async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
            raise LandmarkApiError(overlong_message)

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: _RaisingClient(),
        use_cloud=True,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    stored = result.scalar_one()
    assert len(stored.error_message) == 500
    assert stored.error_message == overlong_message[:500]


async def test_landmark_calls_are_limited_by_landmark_api_concurrency(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 2)
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)

    for index in range(5):
        photo = await _add_photo(
            db_session, project, f"p{index}.jpg", f"etag-{index}", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo, _flat_image())

    client = ConcurrencyTrackingLandmarkClient()

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.call_count == 5
    assert client.max_concurrent > 1
    assert client.max_concurrent <= 2


async def test_multiple_simultaneously_failing_landmark_calls_each_log_their_own_photo(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Spec 0056/ADR 0034, Edge Case "mehrere gleichzeitig fehlschlagende Fotos in einem Block":
    # jede Message muss ihr eigenes photo.id referenzieren, keine Vertauschung durch die parallele
    # zip(block_ids, results, strict=True)-Zuordnung. Bisher fehlte fuer die Landmark-Phase ein
    # Test mit MEHREREN gleichzeitigen Fehlschlaegen im selben Block, nur Einzelfehlschlag war
    # abgedeckt (test_failed_landmark_call_leaves_no_row_and_becomes_a_candidate_again_next_run).
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)

    photo_a = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo_a)
    _write_display_variant(tmp_path, photo_a, _flat_image())
    photo_b = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo_b)
    _write_display_variant(tmp_path, photo_b, _flat_image())
    photo_c = await _add_photo(
        db_session, project, "c.jpg", "etag-c", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo_c)
    _write_display_variant(tmp_path, photo_c, _flat_image())

    client = PerPhotoLandmarkClient(
        [
            LandmarkApiError("Fehler fuer a"),
            LandmarkDetection(name="Eiffelturm", confidence=0.9),
            LandmarkApiError("Fehler fuer c"),
        ]
    )

    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        run = await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_landscape_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=lambda _model: client,
            use_cloud=True,
        )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == 3
    assert len(caplog.records) == 2
    messages = [record.message for record in caplog.records]
    assert any(
        str(photo_a.id) in message and photo_a.relative_path in message for message in messages
    )
    assert any(
        str(photo_c.id) in message and photo_c.relative_path in message for message in messages
    )
    assert not any(str(photo_b.id) in message for message in messages)


async def test_cancelled_error_from_a_parallel_landmark_call_propagates_and_fails_the_run(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    # Spec 0056/ADR 0034: ein CancelledError durchlaeuft die separate, dem continue-Loop
    # vorgelagerte Propagations-Schleife und erreicht die neuen logger.warning(...)-Aufrufe
    # strukturell nie - ein Lauf-Abbruch ist keine best-effort-Situation.
    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        with pytest.raises(asyncio.CancelledError):
            await run_criterion_scoring(
                db_session,
                project,
                scoring_run.id,
                cache_dir=tmp_path,
                build_detector=_no_face_detector,
                build_animal_detector=_no_animal_detector,
                build_classifier=_landscape_scene_classifier,
                build_aesthetics=_no_aesthetics_model,
                build_landmarker=_no_face_landmarker,
                build_landmark_client=lambda _model: CancellingLandmarkClient(),
                use_cloud=True,
            )

    assert len(caplog.records) == 0

    result = await db_session.execute(
        select(CriterionScoringRun).where(CriterionScoringRun.project_id == project.id)
    )
    run_row = result.scalars().first()
    assert run_row is not None
    assert run_row.status == ScanStatus.FAILED


# specs/features/0289-feste-kategorien.md, Umsetzungsschritt 5 ab hier: lokale Signale und
# Remote-Kategorien sind zwei Zulieferer EINER Kandidatenmenge - die abgeloesten
# _merge_remote_category_labels-Tests (Remote-Label als Pseudo-Kriterium, Spezifitaets-Vorrang)
# sind hier durch Vereinigungs- und Herkunftsneutralitaets-Tests ersetzt, nicht ersatzlos
# entfallen.


# --- specs/features/0217-landschaft-erkennung-spezifitaets-vorrang.md, ADR decisions/0047 ---


class CountingSceneClassifier:
    """Zaehlt classify()-Aufrufe UND liefert dabei konfigurierbare Labels - Ein-Aufruf-Nachweis
    fuer AK8 der Spec 0217 ("keine zusaetzlichen Kosten pro Foto"): aus DERSELBEN Modellausgabe
    entstehen gebaeude UND landschaft. Anders als CountingDetector (Spec 0038) ist dieser
    Aufrufzaehler der Testnachweis eines Akzeptanzkriteriums und darf nicht als redundant
    gestrichen werden (Testkonzept, Regel 2 zu ADR 0047)."""

    def __init__(self, categories: list[tuple[str, float]] | None = None) -> None:
        self.call_count = 0
        self._categories = categories if categories is not None else [("valley", 0.7)]

    def classify(self, image: object) -> object:
        self.call_count += 1
        return SimpleNamespace(
            classifications=[
                SimpleNamespace(
                    categories=[
                        SimpleNamespace(category_name=name, score=score)
                        for name, score in self._categories
                    ]
                )
            ]
        )


def _landscape_scene_classifier() -> SceneClassifierStub:
    """Szenen-Klassifikator-Stub mit einem Allow-Listen-Landschaftslabel (exakte Schreibweise wie
    in der Label-Datei des gebuendelten Modells, siehe criteria.py::LANDSCAPE_SCENE_CATEGORIES)."""
    return SceneClassifierStub(category="valley", score=0.8)


class SingleFaceDetector:
    """Faket den mediapipe FaceDetector so, dass GENAU EIN Gesicht gefunden wird - noetig fuer den
    End-to-End-Nachweis, dass ein Remote-Schlagwort gegen content_people=1.0 gewinnt (AK3)."""

    def detect(self, image: object) -> object:
        return SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=[SimpleNamespace(score=0.9)],
                    bounding_box=SimpleNamespace(origin_x=10, origin_y=10, width=40, height=40),
                )
            ]
        )


def _single_face_detector() -> SingleFaceDetector:
    return SingleFaceDetector()


async def _criteria_of(session: AsyncSession, photo: Photo) -> dict[str, float]:
    return {
        c.criterion_key: c.value
        for c in (
            await session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }


async def test_classify_scene_is_called_exactly_once_per_photo_for_both_criteria(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # AK8 (Pflichttest, Spy): GENAU EIN classify()-Aufruf pro Foto, aus dem BEIDE Kriterien
    # entstehen - das Kostenkriterium der Story.
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "alps.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())
    classifier = CountingSceneClassifier([("valley", 0.7), ("church", 0.9)])

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=lambda: classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    assert classifier.call_count == 1
    criteria = await _criteria_of(db_session, photo)
    assert criteria["landschaft"] == pytest.approx(0.7)
    assert criteria["gebaeude"] == pytest.approx(0.9)


def test_landschaft_is_part_of_the_image_analysis_criterion_keys() -> None:
    assert "landschaft" in worker._IMAGE_ANALYSIS_CRITERION_KEYS
    assert worker._IMAGE_ANALYSIS_CRITERION_SOURCES["landschaft"] == CriterionSource.LOCAL_ML


async def test_a_failing_landschaft_score_leaves_gebaeude_untouched(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Best-effort in BEIDE Richtungen (Testkonzept, Regel 3 zu ADR 0047): scheitert die
    # Score-Berechnung des einen Kriteriums, muss das andere aus derselben Modellausgabe trotzdem
    # geschrieben werden - die try/except-Granularitaet ist damit testbestimmt.
    def _boom(labels: object) -> float:
        raise RuntimeError("Landschafts-Score kaputt")

    monkeypatch.setattr(worker, "compute_landschaft_score", _boom)

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "church.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_scene_classifier_stub,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = await _criteria_of(db_session, photo)
    assert "landschaft" not in criteria
    assert criteria["gebaeude"] == pytest.approx(0.8)


async def test_a_failing_gebaeude_score_leaves_landschaft_untouched(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(labels: object) -> float:
        raise RuntimeError("Gebaeude-Score kaputt")

    monkeypatch.setattr(worker, "compute_gebaeude_score", _boom)

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "valley.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = await _criteria_of(db_session, photo)
    assert "gebaeude" not in criteria
    assert criteria["landschaft"] == pytest.approx(0.8)


async def test_a_failing_scene_classification_leaves_both_criteria_unwritten(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    class BrokenSceneClassifier:
        def classify(self, image: object) -> object:
            raise RuntimeError("Modell-Ladefehler")

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=BrokenSceneClassifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = await _criteria_of(db_session, photo)
    assert "gebaeude" not in criteria
    assert "landschaft" not in criteria
    # Ein Kriterium ohne Abhaengigkeit zur Szenen-Klassifikation bleibt unberuehrt.
    assert "content_landscape" in criteria


async def test_a_flat_photo_without_a_landscape_label_scores_no_landschaft(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """AK1/AK5 von Spec 0217, seit Spec 0427 ohne Kategoriebegriff: ein hoher
    `content_landscape`-Wert (Flaechigkeit) macht aus einem Foto keine Landschaft - `landschaft`
    bleibt genau 0.0.

    Die beiden Assertions gehoeren zusammen in EINEN Fall: getrennt bestuende jede auch dann,
    wenn die Flaechigkeit stillschweigend zur Landschafts-Erkennung geworden waere."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "wall.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())

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
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    # Das Foto bekommt trotzdem GENAU EINE Rangzeile - "nichts erkannt" ist kein Grund, aus der
    # Rangfolge zu fallen.
    (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalar_one()
    criteria = await _criteria_of(db_session, photo)
    assert criteria["content_landscape"] > 0.5
    assert criteria["landschaft"] == 0.0


async def test_a_flat_photo_without_a_landscape_label_triggers_no_cloud_call_anymore(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Kostensenkung als eigener Testfall (Testkonzept, Regel 2 zu ADR 0047): ein Foto, das NUR die
    # weggefallene content_landscape-Bedingung erfuellte, verlaesst den Homeserver nicht mehr.
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    project.cloud_vision_consent_at = datetime.now(UTC)
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "wall.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())
    client = RecordingLandmarkClient()

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
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == []


async def test_a_recognised_landscape_photo_is_still_sent_to_the_landmark_client(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    project.cloud_vision_consent_at = datetime.now(UTC)
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "valley.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image())
    client = RecordingLandmarkClient()

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert len(client.calls) == 1


# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md ab hier: die IST-Kostenerfassung der Landmark-Phase. Der Worker summiert Aufrufe und
# Tokens ueber die ERFOLGREICHEN Ergebnisse und schreibt sie zusammen mit dem einmal berechneten
# Betrag an die Lauf-Zeile - im `finally`-Block der Cloud-Phase, nicht erst vor `status=success`.


async def _landmark_cost_setup(
    db_session: AsyncSession, tmp_path: Path, *, photo_count: int, name: str = "Costa Rica"
) -> tuple[Project, ScoringRun, list[Photo]]:
    project = await _make_project(db_session, name=name)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photos = []
    for index in range(photo_count):
        photo = await _add_photo(
            db_session,
            project,
            f"{name}-{index}.jpg",
            f"etag-{name}-{index}",
            datetime(2023, 1, 1, tzinfo=UTC),
        )
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo, _flat_image())
        photos.append(photo)
    return project, scoring_run, photos


async def _run_with_landmark_client(
    db_session: AsyncSession,
    project: Project,
    scoring_run: ScoringRun,
    tmp_path: Path,
    client: object,
    *,
    use_cloud: bool = True,
    run: CriterionScoringRun | None = None,
) -> CriterionScoringRun:
    return await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        run=run,
        use_cloud=use_cloud,
    )


def _detection_with_usage(input_tokens: int, output_tokens: int) -> LandmarkDetection:
    return LandmarkDetection(
        name="Eiffelturm",
        confidence=0.9,
        usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _expected_cost(input_tokens: int, output_tokens: int) -> float:
    cost = compute_cost_usd(
        default_vision_model_for_provider("anthropic"),
        TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )
    assert cost is not None
    return cost


async def test_landmark_costs_are_summed_over_all_successful_calls(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=3)
    client = PerPhotoLandmarkClient(
        [
            _detection_with_usage(1_000, 10),
            _detection_with_usage(2_000, 20),
            _detection_with_usage(3_000, 30),
        ]
    )

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.SUCCESS
    assert run.landmark_api_calls == 3
    assert run.landmark_input_tokens == 6_000
    assert run.landmark_output_tokens == 60
    assert run.landmark_cost_usd == pytest.approx(_expected_cost(6_000, 60))


async def test_a_partially_failing_landmark_phase_only_counts_the_successful_calls(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """ADR 0051 Punkt 6: ein fehlgeschlagener Aufruf liefert keinen auswertbaren `usage`-Block und
    traegt deshalb weder Tokens noch einen Aufruf bei - die dokumentierte, bewusst getragene
    Untererfassung. Die Fehler-Zeilen entstehen unabhaengig davon weiter (ADR 0035)."""
    project, scoring_run, photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=3)
    client = PerPhotoLandmarkClient(
        [
            LandmarkApiError("Fehler fuer a"),
            _detection_with_usage(2_000, 20),
            LandmarkApiError("Fehler fuer c"),
        ]
    )

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.SUCCESS
    assert run.landmark_api_calls == 1
    assert run.landmark_input_tokens == 2_000
    assert run.landmark_output_tokens == 20
    assert run.landmark_cost_usd == pytest.approx(_expected_cost(2_000, 20))

    errors = (
        (
            await db_session.execute(
                select(PhotoCloudVisionError).where(
                    PhotoCloudVisionError.phase == CloudVisionPhase.LANDMARK
                )
            )
        )
        .scalars()
        .all()
    )
    assert {error.photo_id for error in errors} == {photos[0].id, photos[2].id}


async def test_a_result_without_usage_still_counts_as_an_api_call(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Verbindliche Festlegung der Spec: `api_calls` zaehlt jeden stattgefundenen Aufruf, auch
    ohne `usage`-Block (Tokenbeitrag dann 0). Sonst entstuende die stille Kombination
    "api_calls == 0 bei real erfolgten Aufrufen" - und `api_calls > 0` ist zugleich der Ausloeser
    fuer Befund (b) des Unvollstaendigkeits-Hinweises."""
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=2)
    client = PerPhotoLandmarkClient(
        [
            LandmarkDetection(name="Eiffelturm", confidence=0.9),  # ohne usage
            _detection_with_usage(1_000, 10),
        ]
    )

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.SUCCESS
    assert run.landmark_api_calls == 2
    assert run.landmark_input_tokens == 1_000
    assert run.landmark_output_tokens == 10


async def test_an_unpriced_model_records_tokens_but_no_amount(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0051 Punkt 2: ein nicht bepreistes Modell liefert `None` statt eines stillen `0.0` -
    der Lauf faellt dadurch als Erfassungsluecke auf, statt sich als kostenlos zu tarnen. Der
    gemessene Verbrauch bleibt trotzdem erhalten und ist spaeter nachrechenbar."""
    monkeypatch.setattr(pricing, "MODEL_PRICING", {})
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)])

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.SUCCESS
    assert run.landmark_api_calls == 1
    assert run.landmark_input_tokens == 1_000
    assert run.landmark_output_tokens == 10
    assert run.landmark_cost_usd is None


async def test_a_run_without_any_cloud_usage_records_zero_not_null(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """ "Erfasst, keine Kosten angefallen" - das ist etwas anderes als "nicht erfasst" (`NULL`),
    und nur diese Unterscheidung haelt den Unvollstaendigkeits-Hinweis fehlalarmfrei."""
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=False,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.landmark_api_calls == 0
    assert run.landmark_input_tokens == 0
    assert run.landmark_output_tokens == 0
    assert run.landmark_cost_usd == 0


async def test_costs_survive_a_run_that_fails_after_the_landmark_block(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DER Grund fuer das Schreiben im `finally`-Block: ein Lauf, der nach der Cloud-Phase
    scheitert, hat das Geld bereits ausgegeben. Wuerden die Summen erst vor `status=success`
    geschrieben, waere der Betrag `0` - und wegen `0` statt `NULL` nicht einmal als Luecke
    erkennbar."""
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)])

    def _explode(*args: object, **kwargs: object) -> NoReturn:
        raise RuntimeError("simulierter Fehlschlag nach der Cloud-Phase")

    monkeypatch.setattr(worker, "rank_photos", _explode)

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.FAILED
    assert run.landmark_api_calls == 1
    assert run.landmark_input_tokens == 1_000
    assert run.landmark_output_tokens == 10
    assert run.landmark_cost_usd == pytest.approx(_expected_cost(1_000, 10))


async def test_a_second_run_only_carries_its_own_costs(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die Kosten haengen am LAUF, nicht am Projekt - die Projektsumme entsteht erst beim Lesen
    durch Aufsummieren der Laeufe (ADR 0051 Punkt 3/4)."""
    project, scoring_run, photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    first = await _run_with_landmark_client(
        db_session,
        project,
        scoring_run,
        tmp_path,
        PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)]),
    )
    assert first.landmark_api_calls == 1

    # Zweiter Lauf: das Foto hat bereits einen landmark-Kriterienwert und ist damit kein Kandidat
    # mehr - kein neuer Aufruf, keine neuen Kosten, aber ausdruecklich `0` statt `NULL`.
    second = await _run_with_landmark_client(
        db_session, project, scoring_run, tmp_path, PerPhotoLandmarkClient([])
    )

    assert second.id != first.id
    assert second.landmark_api_calls == 0
    assert second.landmark_input_tokens == 0
    assert second.landmark_output_tokens == 0
    assert second.landmark_cost_usd == 0
    assert first.landmark_api_calls == 1
    assert first.landmark_cost_usd == pytest.approx(_expected_cost(1_000, 10))


async def test_the_landmark_client_is_still_closed_exactly_once_when_costs_are_written(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = RecordingLandmarkClient(detection=_detection_with_usage(1_000, 10))

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.landmark_api_calls == 1
    assert client.aclose_calls == 1


async def test_landmark_costs_use_the_configured_provider_model(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Betrag haengt am tatsaechlich genutzten Modell - bei Mistral ist derselbe Verbrauch
    deutlich guenstiger als bei Anthropic."""
    monkeypatch.setattr(worker.settings, "landmark_provider", "mistral")
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000_000, 0)])

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    expected = compute_cost_usd(
        default_vision_model_for_provider("mistral"), TokenUsage(1_000_000, 0)
    )
    assert expected is not None
    assert run.landmark_cost_usd == pytest.approx(expected)
    assert run.landmark_cost_usd != pytest.approx(_expected_cost(1_000_000, 0))


# specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, decisions/0059-modellwahl-je-anbieter-
# und-modellgebundene-kostenschaetzung.md Punkt 6/7 ab hier: das eingestellte Modell wird
# durchgereicht, abgerechnet und je Lauf persistiert. Alle Faelle benutzen bewusst ein NICHT
# voreingestelltes Modell - bei der Voreinstellung stimmten alle drei Stellen auch dann ueberein,
# wenn drei getrennte Lesevorgaenge stattfaenden, und der Test haette keine Trennschaerfe.

_STRONGER_ANTHROPIC_MODEL = VISION_MODELS_BY_PROVIDER["anthropic"][1]


async def test_the_landmark_phase_builds_its_client_with_the_configured_model(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "landmark_model", _STRONGER_ANTHROPIC_MODEL)
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)])
    received: list[str] = []

    def build(model: str) -> object:
        received.append(model)
        return client

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=build,
        use_cloud=True,
    )

    assert received == [_STRONGER_ANTHROPIC_MODEL]


async def test_the_client_the_billing_and_the_persisted_model_are_one_and_the_same_value(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Identitaetsaussage von ADR 0059 Punkt 7 in einem Test: der Wert, mit dem der Client
    gebaut wurde, ist derselbe, mit dem gerechnet und den die Laufzeile festhaelt. Sie ersetzt den
    mit den Modell-Aliasen entfallenen Waechtertest aus test_pricing.py - geprueft wird jetzt das
    tatsaechliche Laufzeitverhalten statt der Gleichheit zweier Literale."""
    monkeypatch.setattr(worker.settings, "landmark_model", _STRONGER_ANTHROPIC_MODEL)
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000_000, 0)])
    received: list[str] = []

    def build(model: str) -> object:
        received.append(model)
        return client

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=build,
        use_cloud=True,
    )

    expected_cost = compute_cost_usd(_STRONGER_ANTHROPIC_MODEL, TokenUsage(1_000_000, 0))
    assert expected_cost is not None
    assert received == [_STRONGER_ANTHROPIC_MODEL]
    assert run.landmark_model == _STRONGER_ANTHROPIC_MODEL
    assert run.landmark_cost_usd == pytest.approx(expected_cost)
    # Gegenprobe: mit dem Voreinstellungs-Modell waere der Betrag ein anderer - der Test haette
    # sonst nicht gezeigt, dass wirklich das EINGESTELLTE Modell gerechnet wurde.
    assert run.landmark_cost_usd != pytest.approx(_expected_cost(1_000_000, 0))


async def test_a_run_without_a_cloud_phase_leaves_the_model_column_null(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """`NULL` heisst "nicht erfasst" - ein eingetragenes Modell behauptete Cloud-Nutzung, wo keine
    stattfand (dieselbe Semantik wie bei `landmark_cost_usd`)."""
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)])

    run = await _run_with_landmark_client(
        db_session, project, scoring_run, tmp_path, client, use_cloud=False
    )

    assert run.landmark_model is None


async def test_the_model_column_survives_a_run_that_fails_after_the_landmark_block(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Spalte wird im selben `finally` und Commit geschrieben wie der eingefrorene Betrag -
    ein Lauf, der spaeter scheitert, hat das Geld bereits ausgegeben und muss erklaerbar bleiben."""
    monkeypatch.setattr(worker.settings, "landmark_model", _STRONGER_ANTHROPIC_MODEL)
    project, scoring_run, _photos = await _landmark_cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoLandmarkClient([_detection_with_usage(1_000, 10)])
    monkeypatch.setattr(worker, "rank_photos", _raise_after_landmark_phase, raising=True)

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.FAILED
    assert run.landmark_model == _STRONGER_ANTHROPIC_MODEL


def _raise_after_landmark_phase(*args: object, **kwargs: object) -> NoReturn:
    raise RuntimeError("Kriterien-Phase scheitert nach dem Cloud-Anteil")


# --------------------------------------------------------------------------------------------
# specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-vier-
# teilschritte-und-laufeigene-cloud-bilanz.md Punkt 2: die LIVE-Zaehler der Landmark-Phase.
#
# Grundmuster aller Tests hier: der Landmark-Client schnappschuesst bei JEDEM Aufruf den Zustand
# der Lauf-Zeile. Assertiert wird ueber die Schnappschussliste, nicht ueber den Endzustand - "der
# Fortschritt bewegt sich waehrend des Laufs mit" ist am Endzustand grundsaetzlich nicht
# nachweisbar.
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _LandmarkSnapshot:
    phase: ClassificationPhase | None
    photos_total: int | None
    photos_processed: int | None
    failed_calls: int | None
    api_calls: int | None
    model: str | None
    cost_usd: float | None
    last_progress_at: datetime


def _snapshot(run: CriterionScoringRun) -> _LandmarkSnapshot:
    return _LandmarkSnapshot(
        phase=run.phase,
        photos_total=run.landmark_photos_total,
        photos_processed=run.landmark_photos_processed,
        failed_calls=run.landmark_failed_calls,
        api_calls=run.landmark_api_calls,
        model=run.landmark_model,
        cost_usd=run.landmark_cost_usd,
        last_progress_at=run.last_progress_at,
    )


class SnapshottingLandmarkClient:
    """Wie PerPhotoLandmarkClient, zeichnet zusaetzlich vor JEDEM Aufruf den Zustand der
    Lauf-Zeile auf. Die Zeile wird dem Test vorab uebergeben (`run=`-Parameter von
    run_criterion_scoring) - sonst haette der Client waehrend des Laufs keinen Zugriff auf sie."""

    def __init__(
        self, run: CriterionScoringRun, results: list[LandmarkDetection | Exception]
    ) -> None:
        self._run = run
        self._results = results
        self.snapshots: list[_LandmarkSnapshot] = []

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
        self.snapshots.append(_snapshot(self._run))
        result = self._results[len(self.snapshots) - 1]
        if isinstance(result, Exception):
            raise result
        return result


async def _prepared_run(
    session: AsyncSession, project: Project, scoring_run: ScoringRun
) -> CriterionScoringRun:
    """Legt die Lauf-Zeile VOR dem Aufruf an und reicht sie ueber `run=` hinein - dasselbe, was
    run_classification produktiv tut (ADR 0050 Punkt 3). Der Test bekommt damit eine Referenz auf
    genau die Zeile, die der Lauf fortschreibt."""
    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=ScanStatus.RUNNING,
        cloud_requested=True,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


def _unbuildable_landmark_client_builder(model: str) -> NoReturn:
    raise RuntimeError("simulierter Modell-Ladefehler")


class TestLandmarkPhaseLiveCounters:
    """ADR 0068 Punkt 2 - die drei Zahlen, die die Story WAEHREND eines Cloud-Teilschritts
    verlangt: Fortschritt, abgesetzte Aufrufe, Fehlschlaege."""

    async def test_the_counters_are_set_to_zero_when_the_phase_is_entered(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`0` und nicht `None`: `NULL` heisst "Phase nicht betreten", `0` heisst "betreten,
        noch nichts passiert". Ohne das Setzen beim Betreten waere der Marker
        `landmark_photos_total` erst am Phasenende da - die Oberflaeche saehe den Teilschritt
        genau dann nicht, wenn er laeuft."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        run = await _prepared_run(db_session, project, scoring_run)
        client = SnapshottingLandmarkClient(run, [_detection_with_usage(10, 1)] * 3)

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        first = client.snapshots[0]
        assert first.photos_total == 3
        assert first.photos_processed == 0
        assert first.failed_calls == 0
        assert first.phase is ClassificationPhase.LANDMARK

    async def test_the_processed_counter_grows_block_by_block(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DER Nachweis "der Fortschritt bewegt sich mit" (geschaerftes Akzeptanzkriterium:
        Fortschreibung mindestens einmal je parallel abgearbeitetem Aufruf-Block)."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        run = await _prepared_run(db_session, project, scoring_run)
        client = SnapshottingLandmarkClient(run, [_detection_with_usage(10, 1)] * 3)

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        assert [snapshot.photos_processed for snapshot in client.snapshots] == [0, 1, 2]
        assert run.landmark_photos_processed == 3

    async def test_the_live_counters_are_committed_at_every_block_end_not_only_at_the_end(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Eine Attributaenderung ist noch keine Sichtbarkeit: die Oberflaeche pollt ueber eine
        ANDERE Verbindung und sieht ausschliesslich Committetes. Ohne diesen Test bliebe "die
        pollende Oberflaeche sieht den Fortschritt" unbelegt."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        run = await _prepared_run(db_session, project, scoring_run)
        committed: list[tuple[int | None, int | None]] = []
        real_commit = db_session.commit

        async def _recording_commit() -> None:
            await real_commit()
            committed.append((run.landmark_photos_processed, run.landmark_failed_calls))

        monkeypatch.setattr(db_session, "commit", _recording_commit)
        client = SnapshottingLandmarkClient(
            run,
            [
                _detection_with_usage(10, 1),
                LandmarkApiError("simulierter Cloud-Fehler"),
                _detection_with_usage(10, 1),
            ],
        )

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        assert (1, 0) in committed
        assert (2, 1) in committed
        assert (3, 1) in committed

    async def test_last_progress_at_advances_during_the_landmark_phase(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DER geschlossene Watchdog-Defekt: bis hierher hatte die Landmark-Phase keinen einzigen
        Commit-Punkt vor dem `finally`, und `reap_stalled_runs` setzte einen Lauf mit mehr als
        STALL_THRESHOLD (15 min) Landmark-Arbeit auf FAILED - OHNE die Coroutine abzubrechen. Der
        Lauf rief danach unveraendert weiter kostenpflichtig beim Anbieter an, waehrend die
        Oberflaeche "fehlgeschlagen" sagte.

        Bewusst KEIN zweiter Testfall in test_worker_reap_stalled_runs.py: `reap_stalled_runs`
        liest ausschliesslich `last_progress_at`, ein Test dort verdoppelte diese Zusage."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        ticks = iter(datetime(2030, 1, 1, 12, 0, second) for second in range(0, 60))
        monkeypatch.setattr(worker, "_now_utc", lambda: next(ticks))

        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        run = await _prepared_run(db_session, project, scoring_run)
        client = SnapshottingLandmarkClient(run, [_detection_with_usage(10, 1)] * 3)

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        stamps = [snapshot.last_progress_at for snapshot in client.snapshots]
        assert stamps == sorted(stamps)
        assert stamps[-1] > stamps[0], (
            "last_progress_at hat sich waehrend der Landmark-Phase nicht bewegt - ein "
            "arbeitender Lauf sieht damit fuer reap_stalled_runs aus wie ein stehender."
        )

    async def test_failed_single_calls_are_counted_while_the_run_is_still_going(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Eigenes Akzeptanzkriterium: "Fehlgeschlagene Einzelaufrufe sind BEREITS WAEHREND des
        Laufs erkennbar, nicht erst nach seinem Abschluss"."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=4
        )
        run = await _prepared_run(db_session, project, scoring_run)
        client = SnapshottingLandmarkClient(
            run,
            [
                _detection_with_usage(10, 1),
                LandmarkApiError("simulierter Cloud-Fehler"),
                _detection_with_usage(10, 1),
                _detection_with_usage(10, 1),
            ],
        )

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        assert [snapshot.failed_calls for snapshot in client.snapshots] == [0, 0, 1, 1]

    async def test_the_model_is_written_at_the_phase_start_while_the_amount_is_not(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Beide Haelften der ADR-Zusage in EINEM Test (ADR 0068 Punkt 6): Modell/Anbieter stehen
        schon WAEHREND des Teilschritts da (sonst koennte die laufende Anzeige nicht sagen, wohin
        die Aufrufe gehen), der BETRAG bleibt am Phasenende eingefroren (ADR 0051 Punkt 4).

        Der Sentinel-Modellwert kommt aus einer NICHT voreingestellten Einstellung - mit dem
        Default waere die Assertion tautologisch (der Wert stuende dann auch bei einem falsch
        gelesenen `settings` da)."""
        stronger = VISION_MODELS_BY_PROVIDER["anthropic"][1]
        monkeypatch.setattr(worker.settings, "landmark_model", stronger)
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=2
        )
        run = await _prepared_run(db_session, project, scoring_run)
        client = SnapshottingLandmarkClient(run, [_detection_with_usage(1_000, 10)] * 2)

        await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client, run=run)

        first = client.snapshots[0]
        assert first.model == stronger
        assert first.api_calls == 0
        assert first.cost_usd == 0
        assert run.landmark_api_calls == 2
        assert run.landmark_cost_usd is not None and run.landmark_cost_usd > 0

    @pytest.mark.parametrize(
        "use_cloud,consent,photo_count",
        [
            pytest.param(False, True, 1, id="cloud-checkbox-aus"),
            pytest.param(True, False, 1, id="einwilligung-aus"),
            pytest.param(True, True, 0, id="keine-fotos"),
        ],
    )
    async def test_an_untouched_landmark_phase_leaves_null_not_zero(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        use_cloud: bool,
        consent: bool,
        photo_count: int,
    ) -> None:
        """Die Vierfeldertafel additiver Lauf-Spalten (ADR 0051 Punkt 3): `NULL` heisst "Phase
        nicht betreten", `0` heisst "betreten, nichts passiert". Ohne die Unterscheidung koennte
        die Bilanz einen Lauf ohne Cloud-Teilschritt nicht von einem mit leerer Kandidatenmenge
        trennen und zeigte fuer beide dieselben Nullzeilen."""
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=photo_count
        )
        project.cloud_vision_detection_enabled = consent
        await db_session.commit()

        run = await _run_with_landmark_client(
            db_session,
            project,
            scoring_run,
            tmp_path,
            RecordingLandmarkClient(),
            use_cloud=use_cloud,
        )

        assert run.landmark_photos_total is None
        assert run.landmark_photos_processed is None
        assert run.landmark_failed_calls is None
        assert_call_bookkeeping_invariant(run)

    async def test_an_unbuildable_client_leaves_the_counters_null_too(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Der vierte NULL-Fall: die Phase wird betreten, der Client ist aber nicht
        konstruierbar - es findet kein einziger Aufruf statt, also gibt es auch nichts zu
        zaehlen."""
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=1
        )

        run = await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_landscape_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=_unbuildable_landmark_client_builder,
            use_cloud=True,
        )

        assert run.landmark_photos_total is None
        assert run.landmark_failed_calls is None
        assert_call_bookkeeping_invariant(run)

    async def test_an_entered_phase_without_candidates_counts_zero_not_null(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die ANDERE Haelfte der Vierfeldertafel, und der Fall, der sich am leichtesten mit den
        vier NULL-Faellen darueber verwechseln laesst: Fotos sind da, die Einwilligung liegt vor,
        der Client ist gebaut - nur ist unter den bewerteten Fotos kein Landmark-Kandidat (hier:
        kein Landschaftslabel, also greift `is_landmark_candidate` nicht).

        Die Phase HAT stattgefunden. `0` ist deshalb die richtige Aussage und `NULL` waere
        falsch: die Bilanz zeigt den Teilschritt als durchlaufen, mit null gesendeten Fotos,
        statt ihn zu verschweigen. Ohne diesen Testfall waere die Grenze zwischen "gab es nicht"
        und "gab es, nichts zu tun" genau an der Stelle unbelegt, an der die API entscheidet, ob
        der Lauf ueberhaupt einen Landmark-Eintrag bekommt (`landmark_photos_total is not None`).
        """
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=1
        )
        client = RecordingLandmarkClient()

        run = await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            # Kein Landschaftslabel -> leere Kandidatenmenge, OBWOHL die Phase betreten wurde.
            build_classifier=_no_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=lambda _model: client,
            use_cloud=True,
        )

        assert client.calls == []
        assert run.landmark_photos_total == 0
        assert run.landmark_photos_processed == 0
        assert run.landmark_failed_calls == 0
        assert_call_bookkeeping_invariant(run)


class TestLandmarkCallBookkeepingInvariant:
    """ADR 0068 Punkt 2: `photos_processed == api_calls + failed_calls` - die Klammer, die den
    laufend fortgeschriebenen Zaehler und die eingefrorene Kosten-Buchfuehrung zusammenhaelt."""

    async def test_all_calls_successful(self, db_session: AsyncSession, tmp_path: Path) -> None:
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        client = PerPhotoLandmarkClient([_detection_with_usage(10, 1)] * 3)

        run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

        assert run.landmark_photos_processed == 3
        assert run.landmark_failed_calls == 0
        assert_call_bookkeeping_invariant(run)

    async def test_mixed_success_and_failure(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=3
        )
        client = PerPhotoLandmarkClient(
            [
                _detection_with_usage(10, 1),
                LandmarkApiError("simulierter Cloud-Fehler"),
                _detection_with_usage(10, 1),
            ]
        )

        run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

        assert run.landmark_photos_processed == 3
        assert run.landmark_api_calls == 2
        assert run.landmark_failed_calls == 1
        assert_call_bookkeeping_invariant(run)

    async def test_every_call_failed(self, db_session: AsyncSession, tmp_path: Path) -> None:
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=2
        )
        client = PerPhotoLandmarkClient([LandmarkApiError("a"), LandmarkApiError("b")])

        run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

        assert run.landmark_photos_processed == 2
        assert run.landmark_api_calls == 0
        assert run.landmark_failed_calls == 2
        assert_call_bookkeeping_invariant(run)

    async def test_a_run_that_fails_after_the_cloud_phase_keeps_the_invariant(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Erweiterung von test_costs_survive_a_run_that_fails_after_the_landmark_block: das Geld
        war ausgegeben, also muss auch die Zaehler-Bilanz stimmen."""
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=2
        )
        client = PerPhotoLandmarkClient(
            [_detection_with_usage(1_000, 10), LandmarkApiError("simulierter Cloud-Fehler")]
        )

        def _explode(*args: object, **kwargs: object) -> NoReturn:
            raise RuntimeError("simulierter Fehlschlag nach der Cloud-Phase")

        monkeypatch.setattr(worker, "rank_photos", _explode)

        run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

        assert run.status == ScanStatus.FAILED
        assert_call_bookkeeping_invariant(run)

    async def test_a_cancelled_block_counts_neither_as_processed_nor_as_an_api_call(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die Implementierungsvorgabe, die aus der Invariante folgt: der Live-Zaehler wird AM
        BLOCKENDE fortgeschrieben, nie beim Betreten. Wuerde er beim Betreten hochgezaehlt,
        stuende nach einem Abbruch mitten im Block ein `processed` da, dem weder ein Aufruf noch
        ein Fehlschlag gegenuebersteht."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=2
        )
        run = await _prepared_run(db_session, project, scoring_run)

        with pytest.raises(asyncio.CancelledError):
            await _run_with_landmark_client(
                db_session,
                project,
                scoring_run,
                tmp_path,
                CancellingLandmarkClient(),
                run=run,
            )

        assert run.landmark_photos_processed == 0
        assert run.landmark_api_calls == 0

    async def test_the_invariant_is_not_claimed_for_a_run_cancelled_inside_a_block(
        self, db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Die Ausnahme wird ausdruecklich festgehalten statt beim ersten Abbruch-Testfall
        stillschweigend gestrichen zu werden: die Invariante gilt fuer VOLLSTAENDIG abgearbeitete
        Bloecke. Nach einem Abbruch mitten im ersten Block ist sie hier trivialerweise erfuellt,
        weil gar kein Block fertig wurde - der Testfall haelt genau das fest, statt die
        Erwartung spaeter kommentarlos zu streichen."""
        monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
        project, scoring_run, _photos = await _landmark_cost_setup(
            db_session, tmp_path, photo_count=2
        )
        run = await _prepared_run(db_session, project, scoring_run)

        with pytest.raises(asyncio.CancelledError):
            await _run_with_landmark_client(
                db_session,
                project,
                scoring_run,
                tmp_path,
                CancellingLandmarkClient(),
                run=run,
            )

        assert run.landmark_failed_calls == 0
        assert_call_bookkeeping_invariant(run)


def _throttle_recording_waits(waits: list[float]) -> CloudRequestThrottle:
    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    return CloudRequestThrottle(min_interval_seconds=0.0, clock=lambda: 0.0, sleep=sleep)


def _landmark_success_transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[index]

    return httpx.MockTransport(handler)


def _landmark_ok(name: str, confidence: float) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "content": [
                {"type": "text", "text": json.dumps({"name": name, "confidence": confidence})}
            ]
        },
    )


class TestTheLandmarkPhaseSitsOutARateLimit:
    """K9: ein Lauf, dessen Fotos heute wegen der Drosselung ohne Ergebnis blieben, liefert danach
    fuer dieselben Fotos ein Ergebnis - und bei einem dauerhaft drosselnden Anbieter bleibt es
    beim heutigen Verhalten. Erst der Kontrast belegt die Zusage."""

    async def _run(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        transport: httpx.MockTransport,
        throttle: CloudRequestThrottle,
    ) -> tuple[CriterionScoringRun, Photo]:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        await db_session.commit()
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo, _flat_image())

        client = AnthropicLandmarkClient(
            api_key="sk-test-not-a-real-secret",
            model=default_vision_model_for_provider("anthropic"),
            transport=transport,
            throttle=throttle,
        )
        run = await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_landscape_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=lambda _model: client,
            use_cloud=True,
        )
        return run, photo

    async def test_a_429_followed_by_a_200_still_produces_the_result_row(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        waits: list[float] = []
        run, photo = await self._run(
            db_session,
            tmp_path,
            _landmark_success_transport([httpx.Response(429), _landmark_ok("Eiffelturm", 0.87)]),
            _throttle_recording_waits(waits),
        )

        assert run.status == ScanStatus.SUCCESS
        assert run.landmark_failed_calls == 0
        detection_row = (
            await db_session.execute(
                select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
            )
        ).scalar_one()
        assert detection_row.name == "Eiffelturm"
        errors = (
            (
                await db_session.execute(
                    select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
                )
            )
            .scalars()
            .all()
        )
        assert errors == []
        assert waits == [2.0]

    async def test_a_permanent_429_keeps_todays_behaviour(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        waits: list[float] = []
        run, photo = await self._run(
            db_session,
            tmp_path,
            _landmark_success_transport([httpx.Response(429)]),
            _throttle_recording_waits(waits),
        )

        assert run.status == ScanStatus.SUCCESS
        assert run.landmark_failed_calls == 1
        rows = (
            (
                await db_session.execute(
                    select(PhotoLandmarkDetection).where(
                        PhotoLandmarkDetection.photo_id == photo.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert rows == []
        error_row = (
            await db_session.execute(
                select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
            )
        ).scalar_one()
        assert "429" in error_row.error_message
        assert waits == [2.0, 4.0, 8.0, 16.0]


class TestTheLandmarkPhaseSummarisesItsThrottling:
    """K8: je Cloud-Teilschritt HOECHSTENS EINE WARNING-Zusammenfassung, und nur, wenn in DIESEM
    Teilschritt tatsaechlich gewartet wurde."""

    async def _run(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        throttle: CloudRequestThrottle,
        monkeypatch: pytest.MonkeyPatch,
    ) -> CriterionScoringRun:
        # Etablierte Konvention (vgl. test_worker_reap_stalled_runs.py): Worker und injizierter
        # Client muessen DENSELBEN Schrittmacher sehen, sonst misst die Zusammenfassung nichts.
        monkeypatch.setattr(worker, "throttle_for_provider", lambda _provider: throttle)
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        await db_session.commit()
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo, _flat_image())

        client = AnthropicLandmarkClient(
            api_key="sk-test-not-a-real-secret",
            model=default_vision_model_for_provider("anthropic"),
            transport=_landmark_success_transport(
                [httpx.Response(429), _landmark_ok("Eiffelturm", 0.87)]
            ),
            throttle=throttle,
        )
        return await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_landscape_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=lambda _model: client,
            use_cloud=True,
        )

    async def test_without_any_waiting_no_line_is_written(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Zugleich der Grund, warum alle BESTEHENDEN Worker-Tests still bleiben: sie arbeiten mit
        Test-Doubles und beruehren den Schrittmacher nie."""
        throttle = _throttle_recording_waits([])
        monkeypatch.setattr(worker, "throttle_for_provider", lambda _provider: throttle)
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        await db_session.commit()
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo, _flat_image())
        client = RecordingLandmarkClient(
            detection=LandmarkDetection(name="Eiffelturm", confidence=0.87)
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            run = await run_criterion_scoring(
                db_session,
                project,
                scoring_run.id,
                cache_dir=tmp_path,
                build_detector=_no_face_detector,
                build_animal_detector=_no_animal_detector,
                build_classifier=_landscape_scene_classifier,
                build_aesthetics=_no_aesthetics_model,
                build_landmarker=_no_face_landmarker,
                build_landmark_client=lambda _model: client,
                use_cloud=True,
            )

        assert run.status == ScanStatus.SUCCESS
        assert [record for record in caplog.records if record.name == "photosort.worker"] == []

    async def test_after_waiting_exactly_one_summary_line_is_written(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        throttle = _throttle_recording_waits([])

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            run = await self._run(db_session, tmp_path, throttle, monkeypatch)

        assert run.status == ScanStatus.SUCCESS
        # Gefiltert auf den Worker-Logger: der Client-Logger (photosort.cloud_vision) schreibt im
        # selben Lauf seine eigene Zeile JE WIEDERHOLUNG - das ist K8s andere Haelfte und hier
        # nicht der Gegenstand.
        records = [record for record in caplog.records if record.name == "photosort.worker"]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        message = records[0].getMessage()
        assert "landmark" in message
        assert "anthropic" in message
        # Genau EINE Wiederholung - Singular. Bewusst mit dem Folgewort assertiert:
        # `"1 Wiederholung" in "1 Wiederholungen"` waere sonst auch beim Plural wahr.
        assert "1 Wiederholung nach 429" in message
        assert "2.0" in message  # summierte Wiederholungs-Wartezeit

    async def test_the_summary_reports_only_the_difference_of_this_phase(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Die Zaehler sind PROZESSWEIT. Ohne diesen Fall schriebe der zweite Cloud-Teilschritt
        sich die Wartezeit des ersten zu und waere bei einem einzelnen Teilschritt trotzdem
        gruen."""
        throttle = _throttle_recording_waits([])
        # Zaehlerstand VOR dem Teilschritt kuenstlich ungleich null.
        throttle.record_retry_wait(41.0)
        throttle.record_retry_wait(1.0)

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            await self._run(db_session, tmp_path, throttle, monkeypatch)

        records = [record for record in caplog.records if record.name == "photosort.worker"]
        assert len(records) == 1
        message = records[0].getMessage()
        # Die Zeile meldet die EINE Wiederholung dieses Teilschritts, nicht alle drei des
        # Prozesses - und nicht die 42.0 s, die vor dem Teilschritt bereits auf dem prozessweiten
        # Zaehler standen.
        assert "42.0" not in message
        # Genau EINE Wiederholung - Singular. Bewusst mit dem Folgewort assertiert:
        # `"1 Wiederholung" in "1 Wiederholungen"` waere sonst auch beim Plural wahr.
        assert "1 Wiederholung nach 429" in message
        assert "2.0 s Wartezeit" in message


class TestLogCloudVisionThrottling:
    """Reine Unit-Faelle des Helfers mit handgebauten ThrottleStats."""

    def test_it_stays_silent_without_any_waiting(self, caplog: pytest.LogCaptureFixture) -> None:
        stats = ThrottleStats(
            delayed_requests=0, total_delay_seconds=0.0, retries=0, total_retry_wait_seconds=0.0
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            worker._log_cloud_vision_throttling("landmark", "anthropic", stats)

        assert caplog.records == []

    def test_a_queued_request_alone_already_yields_a_line(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        stats = ThrottleStats(
            delayed_requests=3, total_delay_seconds=4.5, retries=0, total_retry_wait_seconds=0.0
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            worker._log_cloud_vision_throttling("remote_category", "mistral", stats)

        assert len(caplog.records) == 1
        message = caplog.records[0].getMessage()
        assert "remote_category" in message
        assert "mistral" in message
        assert "3 Anfragen eingereiht" in message
        assert "4.5" in message
        # Null Wiederholungen ist im Deutschen ebenfalls Plural.
        assert "0 Wiederholungen nach 429" in message

    def test_both_counts_are_singular_for_exactly_one(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Copilot-Review-Fund (PR #385), auf BEIDE Zahlwoerter erweitert: "1 Anfragen"/"1
        Wiederholungen" laesen sich falsch. Diese Zeile ist der einzige Traeger der Zusage "eine
        ungewoehnlich lange Laufzeit ist im Lauf-Protokoll erklaerbar" - und genau EINE
        Wiederholung ist der haeufigste Fall, den man dort antrifft."""
        stats = ThrottleStats(
            delayed_requests=1, total_delay_seconds=1.5, retries=1, total_retry_wait_seconds=2.0
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            worker._log_cloud_vision_throttling("landmark", "anthropic", stats)

        message = caplog.records[0].getMessage()
        assert "1 Anfrage eingereiht" in message
        assert "1 Wiederholung nach 429" in message
        assert "Anfragen eingereiht" not in message
        assert "Wiederholungen" not in message

    def test_both_counts_are_plural_for_more_than_one(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        stats = ThrottleStats(
            delayed_requests=2, total_delay_seconds=3.0, retries=4, total_retry_wait_seconds=30.0
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            worker._log_cloud_vision_throttling("landmark", "anthropic", stats)

        message = caplog.records[0].getMessage()
        assert "2 Anfragen eingereiht" in message
        assert "4 Wiederholungen nach 429" in message

    def test_the_line_names_the_throttle_as_provider_wide(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Restrisiko (b) der Spec: `ThrottleStats.since()` liest prozessweite Zaehler - bei zwei
        gleichzeitigen Jobs enthaelt die Zusammenfassung des einen Laufs die Wartezeiten des
        anderen. Eine Zahl, die etwas anderes misst als ihr Label verspricht, schwaecht die
        Lauf-/Kostentransparenz, der das Sicherheitskonzept die Rolle eines
        Erkennungsmechanismus zuschreibt."""
        stats = ThrottleStats(
            delayed_requests=1, total_delay_seconds=1.0, retries=1, total_retry_wait_seconds=2.0
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            worker._log_cloud_vision_throttling("landmark", "anthropic", stats)

        assert "anbieterweit" in caplog.records[0].getMessage()


# ADR 0087 Punkt 3: die Sehenswuerdigkeit ist ein TRENNSIGNAL, kein Gruppierungsmerkmal. Die
# Namen kommen aus `photo_landmark_detections`, NICHT aus einer laufinternen Abbildung der
# Cloud-Antworten - das Signal wirkt damit auch in einem Lauf ohne Cloud-Phase.


async def _add_landmark_detection(
    session: AsyncSession, photo: Photo, name: str, *, confidence: float = 0.9
) -> PhotoLandmarkDetection:
    """Eine Zeile, wie sie ein FRUEHERER Lauf hinterlassen hat - bewusst ohne jeden Cloud-Aufruf
    in diesem Test."""
    row = PhotoLandmarkDetection(
        photo_id=photo.id,
        name=name,
        confidence=confidence,
        provider="anthropic",
        computed_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    return row


async def _run_without_cloud(
    session: AsyncSession, project: Project, scoring_run_id: int, cache_dir: Path
) -> CriterionScoringRun:
    return await run_criterion_scoring(
        session,
        project,
        scoring_run_id,
        cache_dir=cache_dir,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )


async def _event_ids_by_photo(session: AsyncSession, run_id: int) -> dict[int, set[int]]:
    rows = (
        await session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run_id)
        )
    ).scalars()
    event_ids: dict[int, set[int]] = {}
    for row in rows:
        event_ids.setdefault(row.photo_id, set()).add(row.event_id)
    return event_ids


async def _events_of_run(session: AsyncSession, run_id: int) -> list[Event]:
    return list(
        (
            await session.execute(
                select(Event)
                .where(Event.criterion_scoring_run_id == run_id)
                .order_by(Event.position)
            )
        )
        .scalars()
        .all()
    )


async def test_the_landmark_signal_works_in_a_run_without_any_cloud_phase(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """DER ROT-ANKER dieser Sektion: Einwilligung aus, keine Cloud-Phase, die Namen liegen NUR aus
    einem frueheren Lauf in `photo_landmark_detections`. Das Trennsignal muss trotzdem greifen.
    Eine Umsetzung, die die Namen aus einer laufinternen Abbildung der Cloud-Antworten liest, ist
    hier rot und sonst nirgends."""
    project = await _make_project(db_session)
    assert project.cloud_vision_detection_enabled is False
    scoring_run = await _add_successful_scoring_run(db_session, project)
    eiffel = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    trocadero = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
    )
    for photo in (eiffel, trocadero):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        _write_display_variant(tmp_path, photo, _flat_image())
    await _add_landmark_detection(db_session, eiffel, "Eiffelturm")
    await _add_landmark_detection(db_session, trocadero, "Trocadero")

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    assert run.status == ScanStatus.SUCCESS
    event_ids = await _event_ids_by_photo(db_session, run.id)
    assert event_ids[eiffel.id] != event_ids[trocadero.id]
    events = await _events_of_run(db_session, run.id)
    assert [(e.position, e.landmark_name) for e in events] == [
        (1, "Eiffelturm"),
        (2, "Trocadero"),
    ]


async def test_the_event_building_never_mutates_photo_score_cluster_key(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """DIVERGENZ-REGRESSIONSTEST (Ownership-Grenze): `PhotoRanking.event_id` weicht von der
    Phase-A-Gliederung ab UND `PhotoScore.cluster_key` wird in derselben Pruefung explizit als
    unveraendert nachgewiesen. Die Divergenz beider Felder ist gewollt."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    eiffel = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    trocadero = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
    )
    for photo in (eiffel, trocadero):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        _write_display_variant(tmp_path, photo, _flat_image())
    await _add_landmark_detection(db_session, eiffel, "Eiffelturm")
    await _add_landmark_detection(db_session, trocadero, "Trocadero")

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    event_ids = await _event_ids_by_photo(db_session, run.id)
    assert event_ids[eiffel.id] != event_ids[trocadero.id]
    scores = {s.photo_id: s for s in (await db_session.execute(select(PhotoScore))).scalars()}
    assert scores[eiffel.id].cluster_key == "cluster-0"
    assert scores[trocadero.id].cluster_key == "cluster-0"


async def test_without_any_landmark_row_all_photos_share_one_event(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """BACKWARD COMPATIBILITY: ohne Namen, ohne Koordinaten und ohne Zeitluecke bleibt es bei
    einem einzigen Event."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    await _add_score(db_session, photo, cluster_key="cluster-0")
    _write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    events = await _events_of_run(db_session, run.id)
    assert [e.position for e in events] == [1]
    assert events[0].landmark_name is None
    assert events[0].place_kind is None


async def test_a_landmark_row_for_a_photo_without_a_candidate_row_has_no_effect(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Eine Zeile zu einem Foto, das am Ausschuss-Gate haengengeblieben ist, trennt nichts - es
    liegt gar nicht in der Kandidatenmenge."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    survivor = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    rejected = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
    )
    await _add_score(db_session, survivor, cluster_key="cluster-0")
    await _add_score(
        db_session, rejected, cluster_key="cluster-0", suggested_status=RatingStatus.REJECTED
    )
    for photo in (survivor, rejected):
        _write_display_variant(tmp_path, photo, _flat_image())
    await _add_landmark_detection(db_session, survivor, "Eiffelturm")
    await _add_landmark_detection(db_session, rejected, "Trocadero")

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    event_ids = await _event_ids_by_photo(db_session, run.id)
    assert len(await _events_of_run(db_session, run.id)) == 1
    assert rejected.id not in event_ids


async def test_landmark_rows_of_mixed_origin_both_take_effect_in_one_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Foto A hat seine Zeile aus einem FRUEHEREN Lauf, Foto B bekommt sie in DIESEM. Beide Namen
    wirken - das belegt zugleich die Reihenfolge: gelesen wird NACH der Cloud-Phase, sonst fehlte
    B."""
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    older = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    fresh = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
    )
    for photo in (older, fresh):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        _write_display_variant(tmp_path, photo, _flat_image())
    # A: Ergebnis aus einem FRUEHEREN Lauf - Detection-Zeile plus die zugehoerige
    # `landmark`-Kriterienzeile, denn genau an ihr haengt das Skip-Verhalten aus ADR 0025 Punkt 3.
    await _add_landmark_detection(db_session, older, "Alexanderplatz")
    db_session.add(
        PhotoCriterionScore(
            photo_id=older.id,
            criterion_key="landmark",
            value=0.9,
            source=CriterionSource.CLOUD,
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    client = RecordingLandmarkClient(detection=LandmarkDetection(name="Zugspitze", confidence=0.8))
    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    # Nur B geht in die Cloud - A wird wegen seiner Bestandszeile uebersprungen (ADR 0025 Punkt 3).
    assert len(client.calls) == 1
    events = await _events_of_run(db_session, run.id)
    assert [(e.position, e.landmark_name) for e in events] == [
        (1, "Alexanderplatz"),
        (2, "Zugspitze"),
    ]


async def test_the_partition_ranking_uses_the_event(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Nachweis, dass die PARTITIONSBILDUNG das Event nutzt: ohne die Trennung laegen beide Fotos
    in derselben Partition und truegen die Positionen 1 und 2; mit ihr ist jedes Foto
    Erstplatziertes seiner eigenen Partition."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    eiffel = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    trocadero = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
    )
    for photo in (eiffel, trocadero):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        _write_display_variant(tmp_path, photo, _flat_image())
        await _add_album_suitability(db_session, photo)
    await _add_landmark_detection(db_session, eiffel, "Eiffelturm")
    await _add_landmark_detection(db_session, trocadero, "Trocadero")

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    positions = {
        row.photo_id: row.rank_position
        for row in (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        ).scalars()
    }
    assert positions == {eiffel.id: 1, trocadero.id: 1}


async def test_partitions_are_formed_over_the_event_alone(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Der Partitionsschluessel IST die `event_id` - zwei Fotos DESSELBEN Events bilden eine
    Partition und tragen die Positionen 1 und 2.

    Die Gegenprobe steht im Fall darueber (zwei Events, beide Fotos auf Position 1): getrennt
    bestuende jeder von beiden auch dann, wenn die Partition eine ganz andere Groesse haette."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photos = [
        await _add_photo(
            db_session,
            project,
            f"{index}.jpg",
            f"etag-{index}",
            datetime(2023, 1, 1, 10, index, tzinfo=UTC),
        )
        for index in range(2)
    ]
    for photo in photos:
        await _add_score(db_session, photo, cluster_key="cluster-0")
        _write_display_variant(tmp_path, photo, _flat_image())
        await _add_album_suitability(db_session, photo)

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    rows = list(
        (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        ).scalars()
    )
    assert len({row.event_id for row in rows}) == 1
    assert sorted(row.rank_position for row in rows) == [1, 2]


async def test_the_run_persists_its_events_with_position_and_time_span(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    first = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    second = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 30, tzinfo=UTC)
    )
    # Zwei Stunden spaeter: eigenes Event ueber die Zeitluecke.
    third = await _add_photo(
        db_session, project, "c.jpg", "etag-c", datetime(2023, 1, 1, 13, 0, tzinfo=UTC)
    )
    for photo in (first, second, third):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        _write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    events = await _events_of_run(db_session, run.id)
    assert [e.position for e in events] == [1, 2]
    assert (events[0].started_at, events[0].ended_at) == (first.taken_at, second.taken_at)
    assert (events[1].started_at, events[1].ended_at) == (third.taken_at, third.taken_at)
    assert events[0].ended_at <= events[1].started_at


async def test_the_event_place_comes_from_measured_coordinates(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session,
        project,
        "a.jpg",
        "etag-a",
        datetime(2023, 1, 1, 10, 0, tzinfo=UTC),
        gps_lat=48.858370,
        gps_lon=2.294481,
    )
    await _add_score(db_session, photo, cluster_key="cluster-0")
    _write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    [event] = await _events_of_run(db_session, run.id)
    assert event.place_kind == "coordinate"
    # GERUNDET geschrieben, nie in voller Praezision.
    assert (event.place_lat, event.place_lon) == (48.86, 2.29)


async def test_an_event_without_any_measured_coordinate_has_no_place(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die uebernommenen Orte bestimmen die Grenzen mit, speisen den Ortsbezug aber nie."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    anchor = await _add_photo(
        db_session,
        project,
        "anchor.jpg",
        "etag-anchor",
        datetime(2023, 1, 1, 10, 0, tzinfo=UTC),
        gps_lat=48.85,
        gps_lon=2.29,
    )
    await _add_score(
        db_session, anchor, cluster_key="cluster-0", suggested_status=RatingStatus.REJECTED
    )
    candidate = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 1, tzinfo=UTC)
    )
    await _add_score(db_session, candidate, cluster_key="cluster-0")
    for photo in (anchor, candidate):
        _write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    [event] = await _events_of_run(db_session, run.id)
    assert event.place_kind is None
    assert (event.place_lat, event.place_lon) == (None, None)


async def test_a_rejected_photo_anchors_the_inherited_location(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die Inferenzbasis ist das GANZE Projekt, nicht die Kandidatenmenge: zwei weit
    auseinanderliegende, AUSSORTIERTE Anker trennen die beiden koordinatenlosen Kandidaten. Ohne
    die projektweite Bezugsmenge waeren beide ortslos und laegen in einem Event."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    for index, (lat, minute) in enumerate(((48.0, 0), (49.0, 2))):
        anchor = await _add_photo(
            db_session,
            project,
            f"anchor-{index}.jpg",
            f"etag-anchor-{index}",
            datetime(2023, 1, 1, 10, minute, tzinfo=UTC),
            gps_lat=lat,
            gps_lon=2.0,
        )
        await _add_score(
            db_session, anchor, cluster_key="cluster-0", suggested_status=RatingStatus.REJECTED
        )
        _write_display_variant(tmp_path, anchor, _flat_image())
    candidates = [
        await _add_photo(
            db_session,
            project,
            f"{index}.jpg",
            f"etag-{index}",
            datetime(2023, 1, 1, 10, minute, tzinfo=UTC),
        )
        for index, minute in enumerate((0, 2))
    ]
    for photo in candidates:
        await _add_score(db_session, photo, cluster_key="cluster-0")
        _write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    assert len(await _events_of_run(db_session, run.id)) == 2


async def test_the_inference_base_is_bound_to_the_project(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """SICHERHEIT (M5): die Bindung an `Photo.project_id` steht im Worker ausgeschrieben. Ohne sie
    erbte ein Foto Koordinaten aus einem FREMDEN Projekt und die Event-Grenzen in Projekt A
    haengten an Fotos aus Projekt B."""
    foreign = await _make_project(db_session, name="Fremd")
    for index, lat in enumerate((48.0, 49.0)):
        await _add_photo(
            db_session,
            foreign,
            f"f-{index}.jpg",
            f"etag-f-{index}",
            datetime(2023, 1, 1, 10, index * 2, tzinfo=UTC),
            gps_lat=lat,
            gps_lon=2.0,
        )

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    for index, minute in enumerate((0, 2)):
        photo = await _add_photo(
            db_session,
            project,
            f"{index}.jpg",
            f"etag-{index}",
            datetime(2023, 1, 1, 10, minute, tzinfo=UTC),
        )
        await _add_score(db_session, photo, cluster_key="cluster-0")
        _write_display_variant(tmp_path, photo, _flat_image())

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    assert len(await _events_of_run(db_session, run.id)) == 1


async def test_an_unsanitised_legacy_name_does_not_split_against_its_sanitised_twin(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Altbestand aus Spec 0047: eine Zeile traegt unsanierten Rohtext (Zero-Width-Zeichen), eine
    zweite denselben Namen sauber. Ohne Sanitisierung im LESEPFAD waeren das zwei verschiedene
    Namen und das Event zerfiele in zwei Teile, die dieselbe Sehenswuerdigkeit meinen."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    legacy = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    clean = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
    )
    for photo in (legacy, clean):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        _write_display_variant(tmp_path, photo, _flat_image())
    await _add_landmark_detection(db_session, legacy, "Eiffel​turm")
    await _add_landmark_detection(db_session, clean, "Eiffelturm")

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    events = await _events_of_run(db_session, run.id)
    assert [(e.position, e.landmark_name) for e in events] == [(1, "Eiffelturm")]


async def test_an_overlong_legacy_name_is_discarded_and_causes_no_split(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Verworfen statt abgeschnitten: fuer dieses Foto gilt "kein Name", es loest keine Grenze aus
    und der Name landet nicht in `events.landmark_name`."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    overlong = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    normal = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
    )
    for photo in (overlong, normal):
        await _add_score(db_session, photo, cluster_key="cluster-0")
        _write_display_variant(tmp_path, photo, _flat_image())
    await _add_landmark_detection(db_session, overlong, "A" * (MAX_LANDMARK_NAME_LENGTH + 1))
    await _add_landmark_detection(db_session, normal, "Eiffelturm")

    run = await _run_without_cloud(db_session, project, scoring_run.id, tmp_path)

    events = await _events_of_run(db_session, run.id)
    assert [(e.position, e.landmark_name) for e in events] == [(1, "Eiffelturm")]


# specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 4: der Kriterien-Lauf schreibt je Foto
# eine LOKALE Kopfzeile samt Stärkevektor. Rein additiv - die bestehende Kategorieableitung läuft
# unverändert daneben weiter (Ablösung erst in PR 3).
#
# Der tragende Fall dieses Abschnitts ist
# `test_a_small_face_weakens_the_people_motif_without_touching_content_people`: getrennt
# geschrieben bestünden beide Assertions auch dann, wenn die alte Präsenz-Berechnung
# stillschweigend zur neuen geworden ist - und damit wären Rangfolge und
# Landmark-Kandidatenwahl mitverändert.

_MOTIF_TEST_IMAGE_SIZE = 160


class SizedFaceDetector:
    """Faket den mediapipe FaceDetector so, dass GENAU EIN Gesicht mit konfigurierbarer
    Boxgroesse (in Pixeln des 160x160-Testbilds) gefunden wird - analog AnimalDetectorStub, aber
    mit steuerbarer FLAECHE: die Flaechengewichtung der Motivstaerken ist genau daran zu messen."""

    def __init__(self, size_px: int) -> None:
        self._size_px = size_px

    def detect(self, image: object) -> object:
        return SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=[SimpleNamespace(score=0.9)],
                    bounding_box=SimpleNamespace(
                        origin_x=0, origin_y=0, width=self._size_px, height=self._size_px
                    ),
                )
            ]
        )


class SizedAnimalDetector:
    """Wie AnimalDetectorStub, aber mit konfigurierbarer Boxgroesse - fuer den
    Monotonie-Nachweis der Flaechengewichtung."""

    def __init__(self, size_px: int) -> None:
        self._size_px = size_px

    def detect(self, image: object) -> object:
        return SimpleNamespace(
            detections=[
                SimpleNamespace(
                    categories=[SimpleNamespace(category_name="dog", score=0.9)],
                    bounding_box=SimpleNamespace(
                        origin_x=0, origin_y=0, width=self._size_px, height=self._size_px
                    ),
                )
            ]
        )


async def _motif_strengths_of(session: AsyncSession, photo: Photo) -> dict[str, float]:
    rows = (
        await session.execute(
            select(PhotoMotifStrength).where(PhotoMotifStrength.photo_id == photo.id)
        )
    ).scalars()
    return {row.motif_key: row.strength for row in rows}


async def _criterion_values_of(session: AsyncSession, photo: Photo) -> dict[str, float]:
    rows = (
        await session.execute(
            select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
        )
    ).scalars()
    return {row.criterion_key: row.value for row in rows}


async def _one_photo_run(
    db_session: AsyncSession,
    tmp_path: Path,
    *,
    build_detector: object = _no_face_detector,
    build_animal_detector: object = _no_animal_detector,
    build_classifier: object = _no_scene_classifier,
) -> tuple[CriterionScoringRun, Photo]:
    project = await _make_project(db_session, name=f"Projekt {uuid4()}")
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", f"etag-{uuid4()}", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))
    # Der Regelfall seit Spec 0428: ein Ausschuss-Ueberlebender traegt die Modellbewertung aus
    # dem Cloud-Teilschritt, und erst damit entsteht ueberhaupt ein Qualitaetswert.
    await _add_album_suitability(db_session, photo)

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=build_detector,  # type: ignore[arg-type]
        build_animal_detector=build_animal_detector,  # type: ignore[arg-type]
        build_classifier=build_classifier,  # type: ignore[arg-type]
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )
    return run, photo


async def test_a_criterion_run_writes_a_local_motif_assessment_header(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    run, photo = await _one_photo_run(db_session, tmp_path)

    assert run.status == ScanStatus.SUCCESS
    header = await db_session.get(PhotoMotifAssessment, photo.id)
    assert header is not None
    assert header.source == MotifAssessmentSource.LOCAL
    assert header.provider is None
    assert header.excluded_document is False
    assert header.computed_at is not None


async def test_the_local_header_carries_all_eight_motifs(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    _run, photo = await _one_photo_run(db_session, tmp_path)

    assert set(await _motif_strengths_of(db_session, photo)) == set(MOTIF_REGISTRY)


async def test_a_photo_without_any_detection_still_gets_a_header_with_eight_zeroes(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Sonst gilt das Foto als „noch nicht klassifiziert", obwohl es beurteilt wurde - und die
    Oberflaeche zeigte einen Satz statt der Liste."""
    _run, photo = await _one_photo_run(db_session, tmp_path)

    assert set((await _motif_strengths_of(db_session, photo)).values()) == {0.0}
    assert await db_session.get(PhotoMotifAssessment, photo.id) is not None


async def test_the_two_locally_unassessable_motifs_stay_at_zero_after_a_real_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """`aktivitaet` und `detail_stimmung` sind ohne Cloud-Aussage strukturell nicht erreichbar -
    die bewusst akzeptierte Grenze der lokalen Grundlage, kein Fehlerfall."""
    _run, photo = await _one_photo_run(
        db_session,
        tmp_path,
        build_detector=lambda: SizedFaceDetector(size_px=120),
        build_animal_detector=lambda: SizedAnimalDetector(size_px=140),
        build_classifier=_landscape_scene_classifier,
    )

    strengths = await _motif_strengths_of(db_session, photo)

    assert strengths["aktivitaet"] == 0.0
    assert strengths["detail_stimmung"] == 0.0


async def test_a_small_face_weakens_the_people_motif_without_touching_content_people(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """DER Fall, der die Flaechengewichtung von der bestehenden Praesenz-Berechnung trennt: EIN
    Aufbau, ZWEI Assertions. Ein kleines Gesicht ergibt eine Menschen-Staerke < 1.0, und
    `content_people` desselben Fotos ist weiter GENAU 1.0.

    Getrennt geschrieben bestuenden beide Assertions auch dann, wenn die alte Praesenz-Berechnung
    stillschweigend zur neuen geworden ist - und damit waeren Rangfolge (rank_score ueber
    `content_people`) und Landmark-Kandidatenwahl mitveraendert, ohne dass ein Test darueber
    brach."""
    # 16 von 160 Pixeln Kantenlaenge -> 1 % der Bildflaeche, deutlich unter dem
    # Saettigungsanteil von `menschen`.
    _run, photo = await _one_photo_run(
        db_session, tmp_path, build_detector=lambda: SizedFaceDetector(size_px=16)
    )

    strengths = await _motif_strengths_of(db_session, photo)
    criteria = await _criterion_values_of(db_session, photo)

    assert 0.0 < strengths["menschen"] < 1.0
    assert criteria["content_people"] == 1.0


async def test_a_full_frame_face_saturates_the_people_motif(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Gegenprobe zum Fall oben - ohne sie bestuende auch eine Berechnung, die nie 1.0
    erreicht."""
    _run, photo = await _one_photo_run(
        db_session,
        tmp_path,
        build_detector=lambda: SizedFaceDetector(size_px=_MOTIF_TEST_IMAGE_SIZE),
    )

    assert (await _motif_strengths_of(db_session, photo))["menschen"] == 1.0


@pytest.mark.parametrize(("smaller_px", "larger_px"), [(16, 40), (40, 60)])
async def test_a_larger_animal_yields_a_higher_animal_motif_strength(
    db_session: AsyncSession, tmp_path: Path, smaller_px: int, larger_px: int
) -> None:
    """Ein bildfuellender Hund ergibt eine hohe Tier-Staerke, ein Hund am Bildrand eine niedrige -
    gemessen am LAUF, nicht nur an der reinen Funktion."""
    _run, small_photo = await _one_photo_run(
        db_session, tmp_path, build_animal_detector=lambda: SizedAnimalDetector(smaller_px)
    )
    small = (await _motif_strengths_of(db_session, small_photo))["tiere"]

    _run2, large_photo = await _one_photo_run(
        db_session, tmp_path, build_animal_detector=lambda: SizedAnimalDetector(larger_px)
    )
    large = (await _motif_strengths_of(db_session, large_photo))["tiere"]

    assert 0.0 < small < large


async def test_the_animal_confidence_alone_does_not_raise_the_animal_motif(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Gegenprobe zur Monotonie: die bloße Anwesenheit wirkt nicht. Das `tier`-KRITERIUM traegt
    weiter die Konfidenz - die MOTIVSTAERKE die Flaeche."""
    _run, photo = await _one_photo_run(
        db_session, tmp_path, build_animal_detector=lambda: SizedAnimalDetector(size_px=8)
    )

    criteria = await _criterion_values_of(db_session, photo)
    strengths = await _motif_strengths_of(db_session, photo)

    assert criteria["tier"] == 0.9
    assert strengths["tiere"] < 0.1


async def test_the_scene_confidence_feeds_the_landscape_motif_unweighted(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Die Szenen-Klassifikation liefert keine Boxen - ihre Konfidenz ist bereits eine Aussage
    ueber das ganze Bild, und es gibt dort keine Flaechengewichtung zu berechnen."""
    _run, photo = await _one_photo_run(
        db_session, tmp_path, build_classifier=_landscape_scene_classifier
    )

    assert (await _motif_strengths_of(db_session, photo))["landschaft"] == pytest.approx(0.8)


async def test_the_architecture_confidence_feeds_the_building_motif(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    _run, photo = await _one_photo_run(
        db_session, tmp_path, build_classifier=_scene_classifier_stub
    )

    strengths = await _motif_strengths_of(db_session, photo)

    assert strengths["bauwerk_sehenswuerdigkeit"] == pytest.approx(0.8)


async def test_a_recognised_landmark_strengthens_the_building_motif(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Eine erkannte Sehenswuerdigkeit ist kein eigenes Motiv: sie VERSTAERKT „Bauwerk und
    Sehenswuerdigkeit". Der Wert entsteht erst in der Landmark-Phase - die lokale Kopfzeile muss
    also NACH ihr geschrieben werden, sonst fehlte der gerade bezahlte Beitrag."""
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))
    client = RecordingLandmarkClient(LandmarkDetection(name="Tal-Kapelle", confidence=0.95))

    run = await _run_with_landmark_client(db_session, project, scoring_run, tmp_path, client)

    assert run.status == ScanStatus.SUCCESS
    assert client.calls, (
        "der Landmark-Aufruf muss stattgefunden haben, sonst prueft der Fall nichts"
    )
    criteria = await _criterion_values_of(db_session, photo)
    strengths = await _motif_strengths_of(db_session, photo)
    # Der Szenen-Stub liefert `valley` (0.8) fuer `landschaft`, `gebaeude` bleibt 0.0 - der
    # Bauwerk-Wert kann also nur aus der Sehenswuerdigkeit kommen.
    assert criteria["landmark"] == pytest.approx(0.95)
    assert criteria.get("gebaeude", 0.0) == 0.0
    assert strengths["bauwerk_sehenswuerdigkeit"] == pytest.approx(0.95)


async def test_a_local_run_does_not_overwrite_an_existing_cloud_header(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Liegt eine Modellaussage vor, bestimmt allein sie die Motivstaerken - Herkunft,
    Zeitstempel und alle acht Werte bleiben unveraendert. Ohne diesen Fall bestuende auch ein
    bedingungsloses Ueberschreiben."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))
    cloud_time = datetime(2026, 9, 1, 8, 0, 0)
    cloud_vector = dict.fromkeys(MOTIF_REGISTRY, 0.0) | {"aktivitaet": 0.77, "menschen": 0.33}
    await upsert_assessment(
        db_session,
        photo.id,
        source=MotifAssessmentSource.CLOUD,
        strengths=cloud_vector,
        excluded_document=False,
        provider="anthropic",
        computed_at=cloud_time,
    )
    await db_session.commit()

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=lambda: SizedFaceDetector(size_px=_MOTIF_TEST_IMAGE_SIZE),
        build_animal_detector=lambda: SizedAnimalDetector(size_px=_MOTIF_TEST_IMAGE_SIZE),
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    header = await db_session.get(PhotoMotifAssessment, photo.id)
    assert header is not None
    assert header.source == MotifAssessmentSource.CLOUD
    assert header.provider == "anthropic"
    assert header.computed_at == cloud_time
    assert await _motif_strengths_of(db_session, photo) == cloud_vector


async def test_a_correction_survives_the_criterion_run_and_still_wins(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Korrigieren, danach klassifizieren: die Korrekturzeile haengt an keinem Lauf und greift
    bereits im ersten."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))
    user = User(username="daniel", password_hash="hashed-value")
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        PhotoMotifCorrection(photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=True)
    )
    await db_session.commit()

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

    assert len((await db_session.execute(select(PhotoMotifCorrection))).scalars().all()) == 1
    effective = (await load_effective_strengths(db_session, [photo.id]))[photo.id]
    assert effective["menschen"].strength == 1.0
    assert effective["menschen"].correction is True
    # Die gespeicherte Zahl bleibt die Beurteilung des Laufs - die Korrektur wirkt im Lesepfad.
    assert (await _motif_strengths_of(db_session, photo))["menschen"] == 0.0


async def test_the_area_fractions_never_become_a_criterion_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Keine neue Kriterien-Spalte und keine persistierte Box: die Flaechenanteile leben
    ausschliesslich im Lauf und gehen in die Staerke ein."""
    _run, photo = await _one_photo_run(
        db_session,
        tmp_path,
        build_detector=lambda: SizedFaceDetector(size_px=40),
        build_animal_detector=lambda: SizedAnimalDetector(size_px=40),
        build_classifier=_landscape_scene_classifier,
    )

    written = set(await _criterion_values_of(db_session, photo))

    assert written <= set(CRITERIA_REGISTRY), f"unbekannte Kriterien-Schluessel: {written}"


async def test_a_photo_gets_its_motif_strengths_and_exactly_one_ranking_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Beides in EINEM Fall: derselbe Lauf schreibt den Staerkevektor UND genau eine Rangzeile.

    Getrennt geschrieben bestuende jede Haelfte auch dann, wenn der Ranking-Teilschritt wieder
    eine Zeile je Motiv anlegte - die Zahl der Zeilen waere in einem reinen Staerketest
    unsichtbar, und der Unique-Constraint griffe nur bei zwei Zeilen desselben PAARES."""
    _run, photo = await _one_photo_run(
        db_session, tmp_path, build_animal_detector=_animal_detector_stub
    )

    ranking = (
        await db_session.execute(select(PhotoRanking).where(PhotoRanking.photo_id == photo.id))
    ).scalar_one()
    strengths = await _motif_strengths_of(db_session, photo)

    assert ranking.rank_position == 1
    assert set(strengths) == set(MOTIF_REGISTRY)
    assert strengths["tiere"] > 0.0


async def test_a_photo_whose_display_variant_is_missing_still_gets_a_header(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Best-effort wie ueberall im Lauf: ohne Bilddatei gibt es keine Detektion, aber das Foto ist
    beurteilt - acht Nullen, kein fehlender Vektor."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)

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
    assert await db_session.get(PhotoMotifAssessment, photo.id) is not None
    assert set((await _motif_strengths_of(db_session, photo)).values()) == {0.0}


async def test_a_second_run_replaces_the_local_vector_without_duplicating_rows(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))

    for detector_size in (16, _MOTIF_TEST_IMAGE_SIZE):
        await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=lambda size=detector_size: SizedFaceDetector(size),  # type: ignore[misc]
            build_animal_detector=_no_animal_detector,
            build_classifier=_no_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
        )

    strengths = await _motif_strengths_of(db_session, photo)

    assert len(strengths) == len(MOTIF_REGISTRY)
    assert strengths["menschen"] == 1.0


async def test_an_ausschuss_photo_gets_no_motif_header(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Der Lauf beurteilt genau die Ausschuss-Ueberlebenden - ein aussortiertes Foto bleibt ohne
    Kopfzeile und damit „noch nicht klassifiziert"."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    survivor = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
    )
    rejected = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 0, 5, tzinfo=UTC)
    )
    await _add_score(db_session, survivor)
    await _add_score(db_session, rejected, suggested_status=RatingStatus.REJECTED)
    for photo in (survivor, rejected):
        _write_display_variant(tmp_path, photo, _flat_image(size=_MOTIF_TEST_IMAGE_SIZE))

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

    assert await db_session.get(PhotoMotifAssessment, survivor.id) is not None
    assert await db_session.get(PhotoMotifAssessment, rejected.id) is None


# specs/features/0428-albumtauglichkeit-vom-modell.md, Schritt 6: `_compute_content_criteria`
# unterscheidet ab hier zwei Faelle, die vorher beide `0.0` ergaben - NICHT MESSBAR (die Detektion
# lief, das Foto traegt das Merkmal nicht) und NICHT BERECHENBAR (Detektor fehlte, Ausnahme,
# Bild unlesbar). Nur der erste landet in `not_measurable`.


class BrokenFaceDetectorForContent:
    def detect(self, image: object) -> NoReturn:
        raise RuntimeError("simulierter Detektorfehler")


class BrokenLandmarkerForContent:
    def detect(self, image: object) -> NoReturn:
        raise RuntimeError("simulierter Landmarker-Fehler")


async def _add_album_suitability(
    session: AsyncSession, photo: Photo, *, level: int = 4
) -> PhotoAlbumSuitability:
    """Die Zeile, die der (hier nicht laufende) Cloud-Teilschritt geschrieben haette - Grundlage
    des Qualitaetswerts."""
    row = PhotoAlbumSuitability(
        photo_id=photo.id,
        level=level,
        reason="Modellbegruendung",
        provider="anthropic",
        computed_at=datetime.now(UTC),
    )
    session.add(row)
    await session.commit()
    return row


async def _criterion_row(
    session: AsyncSession, photo: Photo, criterion_key: str
) -> PhotoCriterionScore | None:
    return (
        await session.execute(
            select(PhotoCriterionScore).where(
                PhotoCriterionScore.photo_id == photo.id,
                PhotoCriterionScore.criterion_key == criterion_key,
            )
        )
    ).scalar_one_or_none()


async def _rankings_of(session: AsyncSession, run_id: int) -> list[PhotoRanking]:
    return list(
        (
            await session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run_id)
            )
        )
        .scalars()
        .all()
    )


class TestWhatIsNotMeasurable:
    def _content(
        self,
        cache_dir: Path,
        photo: Photo,
        *,
        face_detector: object | None,
        face_landmarker: object | None,
        animal_detector: object | None = None,
    ) -> worker.ContentCriteria:
        return worker._compute_content_criteria(
            cache_dir,
            photo,
            face_detector,  # type: ignore[arg-type]
            animal_detector if animal_detector is not None else NoAnimalDetector(),  # type: ignore[arg-type]
            NoSceneLabels(),  # type: ignore[arg-type]
            NeutralAestheticsModel(),  # type: ignore[arg-type]
            face_landmarker,  # type: ignore[arg-type]
        )

    async def test_a_ran_detection_without_the_feature_marks_both_criteria_not_measurable(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Detektion lief und fand nichts: `goldener_schnitt` ohne Subjekt und `freiraum` ohne
        Gesicht liefern KEINEN Wert statt `0.0` - ein Foto ohne Personen wird nicht mehr fuer
        das abgewertet, was ihm fehlt."""
        project = await _make_project(db_session)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
        )
        _write_display_variant(tmp_path, photo, _flat_image())

        content = self._content(
            tmp_path,
            photo,
            face_detector=NoFaceDetector(),
            face_landmarker=NoFaceLandmarker(),
        )

        assert "goldener_schnitt" not in content.values
        assert "freiraum" not in content.values
        assert content.not_measurable == frozenset({"goldener_schnitt", "freiraum"})

    async def test_a_missing_detector_is_not_the_same_as_not_measurable(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """NICHT BERECHENBAR: der Detektor stand nicht zur Verfuegung. Das Kriterium bleibt
        ungeschrieben UND ausserhalb von `not_measurable` - ein Infrastrukturproblem darf keinen
        gueltigen Messwert eines frueheren Laufs vernichten."""
        project = await _make_project(db_session)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
        )
        _write_display_variant(tmp_path, photo, _flat_image())

        content = self._content(tmp_path, photo, face_detector=None, face_landmarker=None)

        assert "goldener_schnitt" not in content.values
        assert "freiraum" not in content.values
        assert content.not_measurable == frozenset()

    async def test_a_throwing_detector_is_not_the_same_as_not_measurable(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _make_project(db_session)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
        )
        _write_display_variant(tmp_path, photo, _flat_image())

        content = self._content(
            tmp_path,
            photo,
            face_detector=BrokenFaceDetectorForContent(),
            face_landmarker=BrokenLandmarkerForContent(),
        )

        assert content.not_measurable == frozenset()

    async def test_a_measured_feature_is_a_value_and_not_in_the_not_measurable_set(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _make_project(db_session)
        photo = await _add_photo(
            db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
        )
        _write_display_variant(tmp_path, photo, _flat_image())

        content = self._content(
            tmp_path,
            photo,
            face_detector=SingleFaceDetector(),
            face_landmarker=FaceLandmarkerStub(matrix=_rotation_matrix_y(30.0)),
        )

        assert "goldener_schnitt" in content.values
        assert "freiraum" in content.values
        assert content.not_measurable == frozenset()

    async def test_an_unreadable_cache_file_marks_nothing_not_measurable(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """DER gefaehrlichste Fall, und er traegt keinen Kriteriennamen: fehlt die
        `display`-Cache-Datei oder ist sie unlesbar, verlaesst die Funktion sich frueh. Waere
        `not_measurable` dort voreingestellt ("alles, was nicht in `values` steht"), loeschte der
        Lauf den GESAMTEN Kriteriensatz des Fotos - lautlos."""
        project = await _make_project(db_session)
        missing = await _add_photo(
            db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
        )
        broken = await _add_photo(
            db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, tzinfo=UTC)
        )
        broken_path = display_path(tmp_path, broken.id, broken.etag)
        broken_path.parent.mkdir(parents=True, exist_ok=True)
        broken_path.write_bytes(b"kein JPEG")

        for photo in (missing, broken):
            content = self._content(
                tmp_path,
                photo,
                face_detector=NoFaceDetector(),
                face_landmarker=NoFaceLandmarker(),
            )

            assert content.values == {}
            assert content.not_measurable == frozenset(), photo.relative_path


# specs/features/0428-albumtauglichkeit-vom-modell.md, Schritt 9: der Ranking-Teilschritt bildet
# den Qualitaetswert aus Modellstufe und lokaler Korrektur, schreibt `NULL` fuer ein Foto ohne
# Modellbewertung - und der Kriterien-Lauf LOESCHT eine Altzeile, die nicht mehr messbar ist.


async def _prepare_photo(
    session: AsyncSession, tmp_path: Path, *, image: Image.Image | None = None
) -> tuple[Project, ScoringRun, Photo]:
    project = await _make_project(session)
    scoring_run = await _add_successful_scoring_run(session, project)
    photo = await _add_photo(session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC))
    await _add_score(session, photo)
    _write_display_variant(tmp_path, photo, image if image is not None else _flat_image())
    return project, scoring_run, photo


async def _add_stale_criterion(
    session: AsyncSession, photo: Photo, criterion_key: str
) -> PhotoCriterionScore:
    """Eine Altzeile aus einem frueheren Lauf - genau der Wert, den die abgeloeste
    `0.0`-Setzung hinterlassen hat."""
    row = PhotoCriterionScore(
        photo_id=photo.id,
        criterion_key=criterion_key,
        value=0.0,
        source=CriterionSource.LOCAL_HEURISTIC,
        computed_at=datetime(2020, 1, 1, tzinfo=UTC).replace(tzinfo=None),
    )
    session.add(row)
    await session.commit()
    return row


class TestTheStaleRowOfANoLongerMeasurableCriterion:
    """Der gefaehrlichste Umbau dieser Story: "nicht messbar" LOESCHT eine Altzeile, "nicht
    berechenbar" laesst sie unberuehrt. Beide Haelften stehen bewusst in EINEM Fall mit einer
    Assertion darauf, dass sich die beiden Datenbankzustaende UNTERSCHEIDEN muessen - getrennt
    geschrieben bestuenden sie auch ein `_delete_criterion`, das immer oder nie loescht, und genau
    das ist der naheliegende Fehler."""

    async def _run(
        self,
        session: AsyncSession,
        project: Project,
        scoring_run: ScoringRun,
        tmp_path: Path,
        *,
        detector: object,
        landmarker: object,
    ) -> None:
        await run_criterion_scoring(
            session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=lambda: detector,  # type: ignore[arg-type,return-value]
            build_animal_detector=_no_animal_detector,
            build_classifier=_no_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=lambda: landmarker,  # type: ignore[arg-type,return-value]
        )

    @pytest.mark.parametrize(
        ("criterion_key", "detector", "landmarker"),
        [
            ("goldener_schnitt", NoFaceDetector(), NoFaceLandmarker()),
            ("freiraum", NoFaceDetector(), NoFaceLandmarker()),
        ],
    )
    async def test_not_measurable_deletes_the_stale_row_while_not_computable_keeps_it(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        criterion_key: str,
        detector: object,
        landmarker: object,
    ) -> None:
        measurable_project, measurable_run, measured_photo = await _prepare_photo(
            db_session, tmp_path
        )
        await _add_stale_criterion(db_session, measured_photo, criterion_key)
        broken_project = await _make_project(db_session, name="Zweitprojekt")
        broken_run = await _add_successful_scoring_run(db_session, broken_project)
        broken_photo = await _add_photo(
            db_session, broken_project, "b.jpg", "etag-2", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, broken_photo)
        _write_display_variant(tmp_path, broken_photo, _flat_image())
        stale_of_broken = await _add_stale_criterion(db_session, broken_photo, criterion_key)
        stale_value, stale_source, stale_time = (
            stale_of_broken.value,
            stale_of_broken.source,
            stale_of_broken.computed_at,
        )

        # (1) NICHT MESSBAR: die Detektion lief, das Merkmal fehlt.
        await self._run(
            db_session,
            measurable_project,
            measurable_run,
            tmp_path,
            detector=detector,
            landmarker=landmarker,
        )
        # (2) NICHT BERECHENBAR: der Detektor stand gar nicht zur Verfuegung.
        await self._run(
            db_session,
            broken_project,
            broken_run,
            tmp_path,
            detector=BrokenFaceDetectorForContent(),
            landmarker=BrokenLandmarkerForContent(),
        )

        deleted = await _criterion_row(db_session, measured_photo, criterion_key)
        kept = await _criterion_row(db_session, broken_photo, criterion_key)
        # DIE tragende Assertion: die beiden Zustaende muessen sich unterscheiden.
        assert (deleted is None) != (kept is None), criterion_key
        assert deleted is None, criterion_key
        assert kept is not None, criterion_key
        assert (kept.value, kept.source, kept.computed_at) == (
            stale_value,
            stale_source,
            stale_time,
        ), "Ein Infrastrukturproblem darf keinen gueltigen Messwert veraendern."

    async def test_a_measurable_feature_writes_a_value_and_deletes_nothing(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project, scoring_run, photo = await _prepare_photo(db_session, tmp_path)
        await _add_stale_criterion(db_session, photo, "goldener_schnitt")

        await self._run(
            db_session,
            project,
            scoring_run,
            tmp_path,
            detector=SingleFaceDetector(),
            landmarker=FaceLandmarkerStub(matrix=_rotation_matrix_y(30.0)),
        )

        for criterion_key in ("goldener_schnitt", "freiraum"):
            row = await _criterion_row(db_session, photo, criterion_key)
            assert row is not None, criterion_key

    async def test_two_consecutive_runs_leave_no_resurrected_row_behind(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """`_delete_criterion` raeumt die Zeile UND den In-Memory-Cache ab: ein spaeteres
        `_upsert_criterion` im selben Lauf darf kein verwaistes ORM-Objekt wiederbeleben, und der
        zweite Lauf darf die Zeile nicht aus dem Cache heraus neu anlegen."""
        project, scoring_run, photo = await _prepare_photo(db_session, tmp_path)
        await _add_stale_criterion(db_session, photo, "goldener_schnitt")
        await _add_stale_criterion(db_session, photo, "freiraum")

        for _ in range(2):
            await self._run(
                db_session,
                project,
                scoring_run,
                tmp_path,
                detector=NoFaceDetector(),
                landmarker=NoFaceLandmarker(),
            )

        assert await _criterion_row(db_session, photo, "goldener_schnitt") is None
        assert await _criterion_row(db_session, photo, "freiraum") is None
        # Der Lauf hat trotzdem gearbeitet - sonst bestuende dieser Fall auch ein No-op.
        assert await _criterion_row(db_session, photo, "sharpness") is not None


class TestTheQualityScoreOfTheRankingStep:
    async def _run(
        self, session: AsyncSession, project: Project, scoring_run: ScoringRun, tmp_path: Path
    ) -> CriterionScoringRun:
        return await run_criterion_scoring(
            session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_no_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
        )

    async def test_a_photo_with_a_model_level_gets_a_score_inside_its_level_band(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project, scoring_run, photo = await _prepare_photo(db_session, tmp_path)
        await _add_album_suitability(db_session, photo, level=4)

        run = await self._run(db_session, project, scoring_run, tmp_path)

        rankings = await _rankings_of(db_session, run.id)
        assert len(rankings) == 1
        score = rankings[0].rank_score
        assert score is not None
        assert abs(score - normalize_level(4)) <= LOCAL_CORRECTION_SPAN
        assert rankings[0].rank_position == 1

    async def test_a_photo_without_a_model_level_carries_null_but_keeps_its_event(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Kein stiller Rueckfall auf einen lokal gebildeten Wert - und trotzdem faellt das Foto
        nicht aus der Gliederung: es behaelt seine Event-Zugehoerigkeit und bleibt im einsehbaren
        Vorrat."""
        project, scoring_run, photo = await _prepare_photo(db_session, tmp_path)

        run = await self._run(db_session, project, scoring_run, tmp_path)

        rankings = await _rankings_of(db_session, run.id)
        assert [entry.photo_id for entry in rankings] == [photo.id]
        assert rankings[0].rank_score is None
        assert rankings[0].rank_position is None
        assert rankings[0].event_id is not None

    async def test_the_rank_positions_are_gapless_over_the_rated_subset(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die unbewerteten Fotos stehen mit `NULL` daneben und verschieben die Zaehlung der
        bewerteten nicht - sonst entstuende eine Rangfolge mit Luecken."""
        project = await _make_project(db_session)
        scoring_run = await _add_successful_scoring_run(db_session, project)
        photos = []
        for index in range(4):
            photo = await _add_photo(
                db_session,
                project,
                f"{index}.jpg",
                f"etag-{index}",
                datetime(2023, 1, 1, 0, index, tzinfo=UTC),
            )
            await _add_score(db_session, photo)
            _write_display_variant(tmp_path, photo, _flat_image())
            photos.append(photo)
        await _add_album_suitability(db_session, photos[0], level=5)
        await _add_album_suitability(db_session, photos[2], level=2)

        run = await self._run(db_session, project, scoring_run, tmp_path)

        rankings = await _rankings_of(db_session, run.id)
        rated = {
            entry.photo_id: entry.rank_position
            for entry in rankings
            if entry.rank_position is not None
        }
        unrated = [entry for entry in rankings if entry.rank_position is None]
        assert sorted(rated.values()) == [1, 2]
        assert rated[photos[0].id] == 1
        assert rated[photos[2].id] == 2
        assert {entry.photo_id for entry in unrated} == {photos[1].id, photos[3].id}
        assert all(entry.rank_score is None for entry in unrated)

    async def test_without_cloud_approval_nothing_is_rated_and_the_local_values_are_identical(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """ "Kein stiller Rueckfall": eine Assertion NUR auf `NULL` bestuende auch, wenn der lokale
        Pfad nebenbei etwas anderes gerechnet haette. Deshalb die Gleichheit der lokalen
        Kriterienwerte gegen denselben Bestand MIT Bewertung - und dazu, dass ohne Freigabe keine
        einzige Albumtauglichkeitszeile entsteht."""
        without = await _prepare_photo(db_session, tmp_path)
        assert without[0].cloud_vision_detection_enabled is False
        with_project = await _make_project(db_session, name="Mit Freigabe")
        with_project.cloud_vision_detection_enabled = True
        await db_session.commit()
        with_run = await _add_successful_scoring_run(db_session, with_project)
        with_photo = await _add_photo(
            db_session, with_project, "a.jpg", "etag-2", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, with_photo)
        _write_display_variant(tmp_path, with_photo, _flat_image())
        await _add_album_suitability(db_session, with_photo, level=3)

        run_without = await self._run(db_session, without[0], without[1], tmp_path)
        await self._run(db_session, with_project, with_run, tmp_path)

        rankings_without = await _rankings_of(db_session, run_without.id)
        assert all(entry.rank_score is None for entry in rankings_without)
        assert all(entry.rank_position is None for entry in rankings_without)
        assert all(entry.event_id is not None for entry in rankings_without)
        assert (
            await db_session.execute(
                select(func.count())
                .select_from(PhotoAlbumSuitability.__table__)
                .where(PhotoAlbumSuitability.photo_id == without[2].id)
            )
        ).scalar_one() == 0
        assert await _criteria_of(db_session, without[2]) == await _criteria_of(
            db_session, with_photo
        )
