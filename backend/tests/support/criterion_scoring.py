"""Gemeinsame Bausteine der Kriterien-Lauf-Tests (frueher Modul-Hilfen von
test_worker_criterion_scoring.py).
"""

from __future__ import annotations

import asyncio
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

from photosort.landmark import (
    LandmarkApiError,
    LandmarkDetection,
    PlaceHint,
)
from photosort.models import (
    CriterionScoringRun,
    DuplicateDecision,
    Photo,
    PhotoAlbumSuitability,
    PhotoCriterionScore,
    PhotoDuplicateDecision,
    PhotoScore,
    Project,
    RatingStatus,
    ScoringRun,
)
from photosort.worker import run_criterion_scoring
from tests.support import add_photo, add_scoring_run


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
    return await add_photo(
        session,
        project,
        path,
        etag=etag,
        taken_at=taken_at,
        gps_lat=gps_lat,
        gps_lon=gps_lon,
    )


async def _add_score(
    session: AsyncSession,
    photo: Photo,
    *,
    sharpness: float = 100.0,
    exposure: float = 0.0,
    cluster_key: str | None = "cluster-0",
    suggested_status: RatingStatus | None = None,
    duplicate_of: int | None = None,
    duplicate_decision: DuplicateDecision | None = None,
) -> PhotoScore:
    score = PhotoScore(
        photo_id=photo.id,
        sharpness=sharpness,
        exposure=exposure,
        cluster_key=cluster_key,
        suggested_status=suggested_status,
        duplicate_of=duplicate_of,
        computed_at=datetime.now(UTC),
    )
    session.add(score)
    if duplicate_decision is not None:
        session.add(PhotoDuplicateDecision(photo_id=photo.id, decision=duplicate_decision))
    await session.commit()
    return score


async def _add_successful_scoring_run(
    session: AsyncSession, project: Project, *, started_at: datetime | None = None
) -> ScoringRun:
    return await add_scoring_run(session, project, started_at=started_at)


def _flat_image(color: tuple[int, int, int] = (100, 100, 100), size: int = 160) -> Image.Image:
    return Image.new("RGB", (size, size), color=color)


class NoFaceDetector:
    """Faket den mediapipe FaceDetector so, dass nie ein Gesicht gefunden wird - der injizierte
    build_detector-Callable ersetzt den Builder aus classification.py, kein echtes .tflite-Modell in
    Tests (Teststrategie-Abschnitt der Spec)."""

    def detect(self, image: object) -> object:
        return SimpleNamespace(detections=[])


def _no_face_detector() -> NoFaceDetector:
    return NoFaceDetector()


class NoAnimalDetector:
    """Faket den mediapipe ObjectDetector so, dass nie ein Tier gefunden wird - der injizierte
    build_animal_detector-Callable ersetzt den Builder aus classification.py (specs/features/0038:
    build_object_detector darf wie build_face_detector NIE in einem automatisierten Test
    aufgerufen werden, kein echtes .tflite-Modell in Tests)."""

    def detect(self, image: object) -> object:
        return SimpleNamespace(detections=[])


def _no_animal_detector() -> NoAnimalDetector:
    return NoAnimalDetector()


class NoSceneLabels:
    """Faket den mediapipe ImageClassifier so, dass keine Szenen-Kategorie gefunden wird - der
    injizierte build_classifier-Callable ersetzt den Builder aus classification.py
    (specs/features/0038: build_scene_classifier darf wie build_face_detector NIE in einem
    automatisierten Test aufgerufen werden, kein echtes .tflite-Modell in Tests)."""

    def classify(self, image: object) -> object:
        return SimpleNamespace(classifications=[SimpleNamespace(categories=[])])


def _no_scene_classifier() -> NoSceneLabels:
    return NoSceneLabels()


class NeutralAestheticsModel:
    """Faket das Keras-Modell so, dass eine neutrale, gleichverteilte NIMA-Ratingverteilung
    zurueckgegeben wird - der injizierte build_aesthetics-Callable ersetzt
    den Builder aus aesthetics.py (specs/features/0038: build_aesthetics_model darf wie
    build_face_detector NIE in einem automatisierten Test aufgerufen werden, kein echtes
    tensorflow-Modell in Tests)."""

    def predict(self, batch: object) -> object:
        return np.array([[0.1] * 10], dtype="float32")


def _no_aesthetics_model() -> NeutralAestheticsModel:
    return NeutralAestheticsModel()


class NoFaceLandmarker:
    """Faket den mediapipe FaceLandmarker so, dass nie ein Gesicht gefunden wird - der injizierte
    build_landmarker-Callable ersetzt den Builder aus classification.py (specs/features/0048-
    kompositions-kriterien-symmetrie-horizont-freiraum.md: build_face_landmarker darf wie
    build_face_detector NIE in einem automatisierten Test aufgerufen werden, kein echtes
    .task-Modell in Tests)."""

    def detect(self, image: object) -> object:
        return SimpleNamespace(face_landmarks=[], facial_transformation_matrixes=[])


def _no_face_landmarker() -> NoFaceLandmarker:
    return NoFaceLandmarker()


def _rotation_matrix_y(degrees_value: float) -> np.ndarray:
    # Analog test_classification.py::_rotation_matrix_y (Konvention siehe classification.py::
    # yaw_degrees_from_rotation_matrix-Docstring) - kleine, bewusste Duplikation statt einer
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
        # specs/features/0469: die Ortsangabe JE AUFRUF, getrennt von `calls` gefuehrt - die
        # bestehenden Faelle pruefen dort Bildbytes und MIME-Typ und sollen davon unberuehrt
        # bleiben.
        self.hints: list[PlaceHint | None] = []
        # Review-Fund (ship-feature-Runde): kein bisheriger Fake bot aclose() an, der
        # `run_criterion_scoring`'s `getattr(landmark_client, "aclose", None)`-Zweig
        # nahm deshalb immer den None-Pfad - ein versehentlich falsch benannter/entfernter Aufruf
        # waere unbemerkt geblieben. Zaehlt Aufrufe statt nur bool, damit ein Doppel-Close
        # ebenfalls auffiele.
        self.aclose_calls = 0

    async def detect(
        self, image_bytes: bytes, mime_type: str, hint: PlaceHint | None
    ) -> LandmarkDetection:
        self.calls.append((image_bytes, mime_type))
        self.hints.append(hint)
        if self._raise_error:
            raise LandmarkApiError("simulierter Cloud-Fehler")
        return self._detection

    async def aclose(self) -> None:
        self.aclose_calls += 1


class PerPhotoLandmarkClient:
    """Liefert unterschiedliche Detections/Fehler je Aufrufindex (analog PerPhotoCategoryClient
    in test_worker_remote_category_classification.py) - fuer Tests mit mehreren gleichzeitig
    fehlschlagenden Fotos im selben Nebenlaeufigkeits-Block."""

    def __init__(self, results: list[LandmarkDetection | Exception]) -> None:
        self._results = results
        self.calls = 0

    async def detect(
        self, image_bytes: bytes, mime_type: str, hint: PlaceHint | None
    ) -> LandmarkDetection:
        result = self._results[self.calls]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return result


class CancellingLandmarkClient:
    """Simuliert einen asyncio.CancelledError WAEHREND eines parallelen detect()-Aufrufs (ADR
    0025, analog DownloadRaisesCancelledErrorClient in test_worker_scan_project.py) -
    Regressionsnachweis, dass return_exceptions=True das CancelledError nicht verschluckt."""

    async def detect(
        self, image_bytes: bytes, mime_type: str, hint: PlaceHint | None
    ) -> LandmarkDetection:
        raise asyncio.CancelledError("simulierter Abbruch waehrend eines parallelen Cloud-Aufrufs")


def _failing_landmark_client_builder(model: str) -> NoReturn:
    pytest.fail("build_landmark_client darf bei deaktivierter Einwilligung nie aufgerufen werden")


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


async def _criteria_of(session: AsyncSession, photo: Photo) -> dict[str, float]:
    return {
        c.criterion_key: c.value
        for c in (
            await session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }


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
