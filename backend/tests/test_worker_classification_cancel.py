"""Kooperativer Abbruch des Klassifizierungslaufs: Phasen, Bloecke und das Warten auf die Cloud.

Die Cloud-Doubles werfen `RunCancelled` dort, wo der echte Client eine unterbrochene Wartezeit
geworfen haette - das ist genau der Wert, den `sleep_unless_cancelled` liefert.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker as worker
from photosort.models import (
    CriterionScoringRun,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoRanking,
    RemoteCategoryClassificationRun,
    ScanStatus,
)
from photosort.remote_classification import RemoteClassification
from photosort.run_cancel import RunCancelled
from tests.test_worker_classification import (
    RecordingCategoryClient,
    _add_candidate_photo,
    _add_successful_scoring_run,
    _fake_embedder,
    _LandscapeSceneLabels,
    _make_project,
    _NeutralAesthetics,
    _NoDetections,
    _NoSceneLabels,
)


class _CancellingCategoryClient(RecordingCategoryClient):
    """Antwortet einmal, danach kommt der Abbruch aus der Wartezeit."""

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
        if self.calls:
            raise RunCancelled
        return await super().classify(image_bytes, mime_type, photo_id)


class _CancellingLandmarkClient:
    def __init__(self) -> None:
        self.calls = 0

    async def detect(self, image_bytes: bytes, mime_type: str, hint: object) -> object:
        self.calls += 1
        if self.calls > 1:
            raise RunCancelled
        from photosort.landmark import LandmarkDetection

        return LandmarkDetection(name="Kölner Dom", confidence=0.9)


def _builders(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "build_detector": _NoDetections,
        "build_animal_detector": _NoDetections,
        "build_classifier": _NoSceneLabels,
        "build_aesthetics": _NeutralAesthetics,
        "build_landmarker": _NoDetections,
        "build_embedder": _fake_embedder,
        # Ohne diese Bindung baute die Remote-Phase den ECHTEN Client: kein Test darf das.
        "build_category_client": lambda model: RecordingCategoryClient(),
    }
    kwargs.update(overrides)
    return kwargs


async def _project_with_photos(
    session: AsyncSession, cache_dir: Path, count: int, *, cloud_consent: bool
) -> tuple[object, object]:
    project = await _make_project(session, cloud_consent=cloud_consent)
    scoring_run = await _add_successful_scoring_run(session, project)
    for index in range(count):
        await _add_candidate_photo(session, project, f"img{index}.jpg", cache_dir)
    return project, scoring_run


async def test_a_cancelled_landmark_block_ends_the_run_without_a_cloud_error(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 1)
    project, scoring_run = await _project_with_photos(db_session, tmp_path, 3, cloud_consent=True)
    client = _CancellingLandmarkClient()

    run = await worker.run_classification(
        db_session,
        project,  # type: ignore[arg-type]
        scoring_run.id,  # type: ignore[attr-defined]
        tmp_path,
        use_cloud=True,
        build_landmark_client=lambda model: client,
        **_builders(build_classifier=_LandscapeSceneLabels),  # type: ignore[arg-type]
    )

    assert run is not None
    assert run.status == ScanStatus.CANCELLED
    assert run.error_message is None
    # Ein Aufruf ist belegt, der abgebrochene zweite zaehlt nirgends als Fehlschlag.
    assert run.landmark_api_calls == 1
    assert run.landmark_failed_calls == 0
    assert run.landmark_photos_processed == 1
    errors = (await db_session.execute(select(PhotoCloudVisionError))).scalars().all()
    assert errors == []
    # Kein Ranking: der unterbrochene Lauf bleibt ein Teilstand.
    assert (await db_session.execute(select(PhotoRanking))).scalars().all() == []
    criterions = (await db_session.execute(select(PhotoCriterionScore))).scalars().all()
    assert criterions


async def test_a_cancelled_remote_block_skips_the_criteria_phase(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, scoring_run = await _project_with_photos(db_session, tmp_path, 2, cloud_consent=True)
    client = _CancellingCategoryClient()

    run = await worker.run_classification(
        db_session,
        project,  # type: ignore[arg-type]
        scoring_run.id,  # type: ignore[attr-defined]
        tmp_path,
        use_cloud=True,
        **_builders(build_category_client=lambda model: client),  # type: ignore[arg-type]
    )

    assert run is not None
    assert run.status == ScanStatus.CANCELLED
    assert run.error_message is None
    remote_run = (await db_session.execute(select(RemoteCategoryClassificationRun))).scalar_one()
    assert remote_run.status == ScanStatus.CANCELLED
    assert remote_run.error_message is None
    assert remote_run.photos_processed == 1
    assert remote_run.failed_calls == 0
    # Die Kriterien-Phase hat nie begonnen.
    assert (await db_session.execute(select(PhotoCriterionScore))).scalars().all() == []


async def test_a_queued_classification_run_is_taken_over(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, scoring_run = await _project_with_photos(db_session, tmp_path, 1, cloud_consent=False)
    queued = CriterionScoringRun(
        project_id=project.id,  # type: ignore[attr-defined]
        scoring_run_id=scoring_run.id,  # type: ignore[attr-defined]
        status=ScanStatus.QUEUED,
    )
    db_session.add(queued)
    await db_session.commit()

    run = await worker.run_classification(
        db_session,
        project,  # type: ignore[arg-type]
        scoring_run.id,  # type: ignore[attr-defined]
        tmp_path,
        run_id=queued.id,
        use_cloud=False,
        **_builders(),  # type: ignore[arg-type]
    )

    assert run is not None
    assert run.id == queued.id
    assert run.status == ScanStatus.SUCCESS
    assert len((await db_session.execute(select(CriterionScoringRun))).scalars().all()) == 1


async def test_a_classification_run_cancelled_while_waiting_does_no_work(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, scoring_run = await _project_with_photos(db_session, tmp_path, 2, cloud_consent=True)
    queued = CriterionScoringRun(
        project_id=project.id,  # type: ignore[attr-defined]
        scoring_run_id=scoring_run.id,  # type: ignore[attr-defined]
        status=ScanStatus.CANCELLED,
        cancel_requested_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    db_session.add(queued)
    await db_session.commit()
    client = _CancellingCategoryClient()

    result = await worker.run_classification(
        db_session,
        project,  # type: ignore[arg-type]
        scoring_run.id,  # type: ignore[attr-defined]
        tmp_path,
        run_id=queued.id,
        use_cloud=True,
        **_builders(build_category_client=lambda model: client),  # type: ignore[arg-type]
    )

    assert result is None
    assert client.calls == []
    await db_session.refresh(queued)
    assert queued.status == ScanStatus.CANCELLED
