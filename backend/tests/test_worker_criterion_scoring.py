from __future__ import annotations

import asyncio
import logging
import math
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import worker
from photosort.categories import CATEGORY_NOT_RECOGNIZED, is_known_category
from photosort.landmark import LandmarkApiError, LandmarkDetection
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    FineLabel,
    Photo,
    PhotoCategoryClassification,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoFineLabel,
    PhotoLandmarkDetection,
    PhotoRanking,
    PhotoScore,
    Project,
    RatingStatus,
    ScanStatus,
    ScoringRun,
)
from photosort.thumbnails import display_path
from photosort.worker import _select_landmark_candidates, run_criterion_scoring, run_project_scoring


async def _make_project(session: AsyncSession, *, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id=f"drive-{name}", opencloud_path=name)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_photo(
    session: AsyncSession, project: Project, path: str, etag: str, taken_at: datetime
) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=etag,
        content_length=100,
        taken_at=taken_at,
        last_modified=taken_at,
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
        build_detector=_no_face_detector,
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
        build_detector=_no_face_detector,
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
    stub = FaceLandmarkerStub(
        landmarks=[(0.05, 0.1), (0.15, 0.3)], matrix=_rotation_matrix_y(20.0)
    )

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
        build_detector=_no_face_detector,
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

    stub = FaceLandmarkerStub(
        landmarks=[(0.05, 0.1), (0.15, 0.3)], matrix=_rotation_matrix_y(20.0)
    )

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


async def test_goldener_schnitt_is_written_when_both_detections_succeed_even_without_a_subject(
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
    # dokumentierter niedriger Fallback-Wert (0.0), kein fehlendes Kriterium.
    assert criteria["goldener_schnitt"] == 0.0


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
    # (gleicher cluster_key, keines erfuellt ein aktives Kriterium -> Catch-all). Seit
    # specs/features/0217 ist das der Auffangkorb statt der frueheren Kategorie "landscape" (seit
    # specs/features/0289-feste-kategorien.md heisst er `nicht_erkannt`, nicht mehr "unerkannt"):
    # ein
    # flaechiges Bild ohne Landschaftslabel ist keine Landschaft (AK1).
    assert len(rankings) == 3
    by_photo = {r.photo_id: r for r in rankings}
    assert {by_photo[p.id].category_key for p in photos} == {CATEGORY_NOT_RECOGNIZED}
    assert {by_photo[p.id].cluster_key for p in photos} == {"cluster-0"}
    positions = sorted(r.rank_position for r in rankings)
    assert positions == [1, 2, 3]
    # Hoehere Schaerfe -> hoeherer rank_score -> rank_position 1.
    assert by_photo[photos[2].id].rank_position == 1


async def test_partitions_are_isolated_by_cluster_and_category(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    cluster_a = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, cluster_a, cluster_key="cluster-a")
    _write_display_variant(tmp_path, cluster_a, _flat_image())

    cluster_b = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 2, tzinfo=UTC)
    )
    await _add_score(db_session, cluster_b, cluster_key="cluster-b")
    _write_display_variant(tmp_path, cluster_b, _flat_image())

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
    # Beide Cluster haben je genau 1 Foto -> je rank_position 1, unabhaengig voneinander.
    assert {r.rank_position for r in rankings} == {1}
    assert {r.cluster_key for r in rankings} == {"cluster-a", "cluster-b"}


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


async def test_a_single_animal_photo_gets_the_tier_category_regardless_of_frequency(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Kernverhaltensaenderung gegenueber Spec 0045/ADR 0023 (bewusst, nicht versehentlich): EIN
    einziges Tier-Foto unter 30 bekommt jetzt `tier` - frueher waere es an der
    15%-Haeufigkeitsschwelle gescheitert und im Auffangkorb gelandet. Die Zuordnung ist damit
    unabhaengig davon, welche anderen Fotos im Projekt liegen (Akzeptanzkriterium "vorhersehbar,
    projektuebergreifend gleich")."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photos = await _add_photos_with_optional_animal_marker(
        db_session, project, tmp_path, total=30, marked=1
    )

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_size_gated_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
    )

    assert run.status == ScanStatus.SUCCESS
    rankings = {
        r.photo_id: r.category_key
        for r in (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        ).scalars()
    }
    assert rankings[photos[0].id] == "tier"
    assert rankings[photos[1].id] == CATEGORY_NOT_RECOGNIZED


async def test_every_written_category_key_belongs_to_the_fixed_set(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Kompakteste Absicherung des Kern-Akzeptanzkriteriums (Teststrategie 7): ein lauf-weiter
    Test ueber ALLE geschriebenen category_key-Werte, nicht ueber ein einzelnes Foto."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_photos_with_optional_animal_marker(
        db_session, project, tmp_path, total=6, marked=3
    )

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_size_gated_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    rankings = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalars().all()
    assert rankings
    assert all(is_known_category(r.category_key) for r in rankings)


async def test_a_run_without_remote_classification_only_uses_the_local_six_or_the_catch_all(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Akzeptanzkriterium: ohne aktivierte Remote-Kategorisierung wird nur die lokal bestimmbare
    Teilmenge vergeben - keine der uebrigen sechs Kategorien darf auftauchen. Assertion ueber ALLE
    geschriebenen Werte eines Laufs, nicht ueber ein einzelnes Foto."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_photos_with_optional_animal_marker(
        db_session, project, tmp_path, total=6, marked=3
    )

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_single_face_detector,
        build_animal_detector=_size_gated_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    rankings = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalars().all()
    locally_reachable = {
        "menschen",
        "tier",
        "essen_trinken",
        "fahrzeug",
        "gebaeude_bauwerk",
        "landschaft",
        CATEGORY_NOT_RECOGNIZED,
    }
    assert {r.category_key for r in rankings} <= locally_reachable


async def test_existing_behavior_is_unchanged_when_frequency_threshold_is_still_met(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Bestandsverhalten-Regression (Akzeptanzkriterium der Spec 0045), seit specs/features/0217
    # auf das echte Inhalts-Kriterium umgestellt: ein Projekt, in dem `landschaft` die
    # 15%-Schwelle erreicht (hier: alle Fotos tragen ein Allow-Listen-Landschaftslabel), liefert
    # unveraendert einen einheitlichen, aus dem Kriterium abgeleiteten category_key.
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photos = []
    for i in range(5):
        photo = await _add_photo(
            db_session, project, f"{i}.jpg", f"etag-{i}", datetime(2023, 1, 1, 0, i, tzinfo=UTC)
        )
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo, _flat_image())
        photos.append(photo)

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
    assert {r.category_key for r in rankings} == {"landschaft"}


async def test_empty_candidate_pool_does_not_crash_category_derivation(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Leerer Kandidatenpool (Akzeptanzkriterium der Spec: derive_active_categories({}) darf
    # keinen ZeroDivisionError werfen) - kein einziges Foto passiert das Ausschuss-Gate.
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    rejected = await _add_photo(
        db_session, project, "rejected.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, rejected, cluster_key=None, suggested_status=RatingStatus.REJECTED)
    _write_display_variant(tmp_path, rejected, _flat_image())

    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
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
    assert rankings == []
    # Spec 0056/ADR 0034: nur Fehler werden geloggt, ein erfolgreich durchgelaufener Gesamtlauf
    # erzeugt keinen Log-Eintrag.
    assert len(caplog.records) == 0


# specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR decisions/0025-cloud-
# landmark-erkennung.md ab hier: erste tatsaechlich produktive CriterionSource.CLOUD-Anbindung im
# Kriterien-Scoring-Pfad. Kein `unittest.mock.patch` - build_landmark_client ist injizierbar
# (Teststrategie-Abschnitt der Spec), analog build_detector/build_animal_detector/...


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
        raise asyncio.CancelledError(
            "simulierter Abbruch waehrend eines parallelen Cloud-Aufrufs"
        )


def _failing_landmark_client_builder() -> NoReturn:
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
        build_landmark_client=lambda: client,
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

    client = RecordingLandmarkClient(
        detection=LandmarkDetection(name="Eiffelturm", confidence=0.9)
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
        build_landmark_client=lambda: client,
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
        build_landmark_client=lambda: first_client,
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
        build_landmark_client=lambda: second_client,
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
        build_landmark_client=lambda: client,
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
        build_landmark_client=lambda: client,
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
        build_landmark_client=lambda: client,
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
        build_landmark_client=lambda: client,
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
            build_landmark_client=lambda: failing_client,
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
        build_landmark_client=lambda: succeeding_client,
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
        build_landmark_client=lambda: failing_client,
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
        build_landmark_client=lambda: RecordingLandmarkClient(raise_error=True),
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
        build_landmark_client=lambda: RecordingLandmarkClient(),
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
        build_landmark_client=lambda: RecordingLandmarkClient(raise_error=True),
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
        build_landmark_client=lambda: RecordingLandmarkClient(
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
        build_landmark_client=lambda: _RaisingClient("erster Fehlschlag"),
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
        build_landmark_client=lambda: _RaisingClient("zweiter Fehlschlag"),
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
        build_landmark_client=lambda: _RaisingClient(),
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
        build_landmark_client=lambda: client,
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
            build_landmark_client=lambda: client,
            use_cloud=True,
        )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == 3
    assert len(caplog.records) == 2
    messages = [record.message for record in caplog.records]
    assert any(str(photo_a.id) in message and photo_a.relative_path in message
               for message in messages)
    assert any(str(photo_c.id) in message and photo_c.relative_path in message
               for message in messages)
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
                build_landmark_client=lambda: CancellingLandmarkClient(),
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


async def _add_classification(
    session: AsyncSession, photo: Photo, *categories: str
) -> None:
    session.add(
        PhotoCategoryClassification(
            photo_id=photo.id,
            category_key=categories[0] if categories else CATEGORY_NOT_RECOGNIZED,
            detected_categories=list(categories),
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def _run_and_collect_categories(
    db_session: AsyncSession,
    project: Project,
    scoring_run_id: int,
    tmp_path: Path,
    **builders: object,
) -> dict[int, str]:
    kwargs: dict[str, object] = {
        "build_detector": _no_face_detector,
        "build_animal_detector": _no_animal_detector,
        "build_classifier": _no_scene_classifier,
        "build_aesthetics": _no_aesthetics_model,
        "build_landmarker": _no_face_landmarker,
        "build_landmark_client": _failing_landmark_client_builder,
    }
    kwargs.update(builders)
    run = await run_criterion_scoring(
        db_session, project, scoring_run_id, cache_dir=tmp_path, **kwargs  # type: ignore[arg-type]
    )
    assert run.status == ScanStatus.SUCCESS
    return {
        r.photo_id: r.category_key
        for r in (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        ).scalars()
    }


async def test_local_and_remote_candidates_go_into_one_set(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Nachweis fuer "ein gemeinsames Set, keine zwei Kategoriewelten": ein Foto mit dem LOKALEN
    Signal `tier` und der REMOTE-Kategorie `menschen` bekommt `menschen` (kleinere precedence) -
    dasselbe Foto ohne Klassifikations-Zeile bekommt `tier`."""
    project = await _make_project(db_session, name="Mit Remote")
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _animal_marked_image())
    await _add_classification(db_session, photo, "menschen")

    with_remote = await _run_and_collect_categories(
        db_session,
        project,
        scoring_run.id,
        tmp_path,
        build_animal_detector=_size_gated_animal_detector,
    )
    assert with_remote[photo.id] == "menschen"

    other = await _make_project(db_session, name="Ohne Remote")
    other_run = await _add_successful_scoring_run(db_session, other)
    other_photo = await _add_photo(
        db_session, other, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, other_photo)
    _write_display_variant(tmp_path, other_photo, _animal_marked_image())

    without_remote = await _run_and_collect_categories(
        db_session,
        other,
        other_run.id,
        tmp_path,
        build_animal_detector=_size_gated_animal_detector,
    )
    assert without_remote[other_photo.id] == "tier"


async def _add_fine_labels(session: AsyncSession, photo: Photo, *raw_labels: str) -> None:
    """Legt Feinlabel-Zeilen am Foto an (Vokabular-Eintrag + Zuordnung), so wie sie
    worker.py::run_remote_category_classification schreibt."""
    for raw_label in raw_labels:
        fine_label = FineLabel(
            canonical_key=raw_label.lower(), display_name=raw_label, embedding=[0.0] * 384
        )
        session.add(fine_label)
        await session.flush()
        session.add(
            PhotoFineLabel(
                photo_id=photo.id,
                fine_label_id=fine_label.id,
                raw_label=raw_label,
                provider="anthropic",
                computed_at=datetime.now(UTC),
            )
        )
    await session.commit()


async def test_fine_labels_do_not_change_the_derived_category_or_add_groups(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Akzeptanzkriterium: "Feinlabels gehen nicht in `resolve_category` ein; ein Lauf mit
    Feinlabels erzeugt in der Kuratierung keine zusaetzlichen Gruppen gegenueber demselben Lauf
    ohne Feinlabels."

    Der Nachweis muss hier auf Integrationsebene stehen und nicht nur strukturell aus
    `derive_photo_category` folgen: die Ableitung liest die `photo_fine_labels`-Tabelle heute
    schlicht nicht, und genau diese Nicht-Verdrahtung ist es, die ein spaeterer Umbau ("nehmen wir
    die Feinlabels doch als Kandidaten dazu") still aufheben wuerde. Die Feinlabels sind bewusst
    so gewaehlt, dass sie als Kandidaten das Ergebnis TATSAECHLICH kippen wuerden: der
    canonical_key "menschen" hat eine KLEINERE `precedence` als das lokal erkannte `tier` und
    gewaenne die Vorrangaufloesung. Ein Feinlabel mit groesserer precedence (etwa "fahrzeug")
    machte den Test tautologisch - er bliebe auch dann gruen, wenn Feinlabels eingespeist wuerden.
    """
    project = await _make_project(db_session, name="Mit Feinlabels")
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _animal_marked_image())
    await _add_fine_labels(db_session, photo, "Menschen", "Urlaub")

    with_fine_labels = await _run_and_collect_categories(
        db_session,
        project,
        scoring_run.id,
        tmp_path,
        build_animal_detector=_size_gated_animal_detector,
    )

    other = await _make_project(db_session, name="Ohne Feinlabels")
    other_run = await _add_successful_scoring_run(db_session, other)
    other_photo = await _add_photo(
        db_session, other, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, other_photo)
    _write_display_variant(tmp_path, other_photo, _animal_marked_image())

    without_fine_labels = await _run_and_collect_categories(
        db_session,
        other,
        other_run.id,
        tmp_path,
        build_animal_detector=_size_gated_animal_detector,
    )

    # Gleiche Kategorie trotz der Feinlabels - und vor allem: dieselbe MENGE an Kategorien, also
    # keine zusaetzliche Gruppe in der Kuratierung.
    assert with_fine_labels[photo.id] == "tier"
    assert set(with_fine_labels.values()) == set(without_fine_labels.values())


async def test_the_origin_of_a_candidate_does_not_change_the_result(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Akzeptanzkriterium "Herkunftsneutralitaet": dieselbe Kandidatenmenge (`tier`), einmal rein
    lokal und einmal rein remote erzeugt, fuehrt zur selben Kategorie."""
    local_project = await _make_project(db_session, name="Lokal")
    local_run = await _add_successful_scoring_run(db_session, local_project)
    local_photo = await _add_photo(
        db_session, local_project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, local_photo)
    _write_display_variant(tmp_path, local_photo, _animal_marked_image())

    local_result = await _run_and_collect_categories(
        db_session,
        local_project,
        local_run.id,
        tmp_path,
        build_animal_detector=_size_gated_animal_detector,
    )

    remote_project = await _make_project(db_session, name="Remote")
    remote_run = await _add_successful_scoring_run(db_session, remote_project)
    remote_photo = await _add_photo(
        db_session, remote_project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, remote_photo)
    _write_display_variant(
        tmp_path, remote_photo, _textured_image_below_landscape_threshold()
    )
    await _add_classification(db_session, remote_photo, "tier")

    remote_result = await _run_and_collect_categories(
        db_session, remote_project, remote_run.id, tmp_path
    )

    assert local_result[local_photo.id] == remote_result[remote_photo.id] == "tier"


async def test_a_photo_without_any_candidate_lands_in_the_catch_all(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _textured_image_below_landscape_threshold())

    result = await _run_and_collect_categories(db_session, project, scoring_run.id, tmp_path)

    assert result[photo.id] == CATEGORY_NOT_RECOGNIZED


async def test_a_remote_classification_of_not_recognized_loses_against_a_local_signal(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Edge Case der Spec: `nicht_erkannt` steht ausserhalb der Vorrangreihenfolge und verliert
    # gegen jede echte Kategorie - auch wenn es der einzige REMOTE-Kandidat ist.
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _animal_marked_image())
    await _add_classification(db_session, photo, CATEGORY_NOT_RECOGNIZED)

    result = await _run_and_collect_categories(
        db_session,
        project,
        scoring_run.id,
        tmp_path,
        build_animal_detector=_size_gated_animal_detector,
    )

    assert result[photo.id] == "tier"


async def test_category_override_wins_over_the_automatically_derived_category_key(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Bestandstest (Werte auf das feste Set umgestellt): der Override wird VOR jeder Ableitung
    # angewendet und ueberlebt einen vollen Lauf.
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    score = await _add_score(db_session, photo)
    score.category_override = "kunst_kreatives"
    await db_session.commit()
    _write_display_variant(tmp_path, photo, _animal_marked_image())

    result = await _run_and_collect_categories(
        db_session,
        project,
        scoring_run.id,
        tmp_path,
        build_animal_detector=_size_gated_animal_detector,
    )

    assert result[photo.id] == "kunst_kreatives"


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


async def test_a_flat_photo_without_a_landscape_label_ends_up_unrecognized(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # AK1/AK5: hoher content_landscape-Wert, aber kein Allow-Listen-Label -> der Auffangkorb
    # (`nicht_erkannt`) statt der frueheren Kategorie "landscape".
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

    ranking = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalar_one()
    assert ranking.category_key == CATEGORY_NOT_RECOGNIZED
    criteria = await _criteria_of(db_session, photo)
    assert criteria["content_landscape"] > 0.5
    assert criteria["landschaft"] == 0.0


async def test_recognised_landscape_photos_form_the_landschaft_category(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # AK2 (der bisher gut funktionierende Fall verschlechtert sich nicht): ueberwiegend
    # Allow-Listen-Landschaftslabels aktivieren die Kategorie, die Fotos landen dort.
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    for index in range(4):
        photo = await _add_photo(
            db_session, project, f"p{index}.jpg", f"etag-{index}", datetime(2023, 1, 1, tzinfo=UTC)
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

    rankings = (
        (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rankings) == 4
    assert {r.category_key for r in rankings} == {"landschaft"}


async def test_a_remote_category_wins_against_content_people_by_precedence(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Nachfolger des Spezifitaets-Vorrang-Tests aus Spec 0217/ADR 0047 Punkt 2: die Entscheidung
    # faellt jetzt ueber die feste Vorrangreihenfolge, nicht ueber eine Spezifitaets-Stufe.
    # `dokument_screenshot` (precedence 1) schlaegt `menschen` (precedence 3), obwohl das Foto ein
    # erkanntes Gesicht traegt (content_people = 1.0).
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo, _textured_image_below_landscape_threshold())
    await _add_classification(db_session, photo, "dokument_screenshot")

    result = await _run_and_collect_categories(
        db_session,
        project,
        scoring_run.id,
        tmp_path,
        build_detector=_single_face_detector,
    )

    assert result[photo.id] == "dokument_screenshot"


@pytest.mark.parametrize("override", ["unerkannt", "landscape", "gegenstand"])
async def test_a_manual_override_on_a_no_longer_derivable_key_survives_a_full_run(
    db_session: AsyncSession, tmp_path: Path, override: str
) -> None:
    # AK9 der Spec 0217, weiterhin gueltig: ein Override bleibt bitgenau erhalten und wird VOR
    # jeder Ableitung angewendet - auch bei einem ALTWERT aus der Laufhistorie ("unerkannt",
    # "landscape"), den weder die Ableitung noch der Override-Endpunkt heute noch erzeugen wuerde
    # (Lesepfad-Toleranz, Security-Abschnitt der Spec 0289 Punkt 2).
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    score = await _add_score(db_session, photo)
    score.category_override = override
    await db_session.commit()
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

    ranking = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalar_one()
    assert ranking.category_key == override
    await db_session.refresh(score)
    assert score.category_override == override


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
        build_landmark_client=lambda: client,
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
        build_landmark_client=lambda: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert len(client.calls) == 1
