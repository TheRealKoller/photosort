"""Kooperativer Abbruch des Prueflaufs: Pruefpunkte je Foto und je Cloud-Block, keine Faelle.

Der Abbruch kommt aus dem Double selbst: ab dem n-ten Aufruf wirft es `RunCancelled` - genau den
Wert, den eine unterbrochene Drosselungswartezeit geliefert haette.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.db as db_module
from photosort.eye_mapping import MAPPING_VERSION
from photosort.models import (
    ClassificationReviewCase,
    ClassificationReviewResult,
    ClassificationReviewSide,
    ClassificationReviewSideKind,
    ScanStatus,
)
from photosort.run_cancel import RunCancelled
from photosort.worker.classification_review import (
    execute_classification_review,
    run_classification_review,
)
from tests.test_worker_classification_review import (
    FakeCloudClient,
    FakeEyeClient,
    _add_photo,
    _make_project,
    _make_review,
    _make_user,
    _payload,
    _side,
)

_LOCAL_BUILDERS = {
    "build_detector": lambda: None,
    "build_animal_detector": lambda: None,
    "build_classifier": lambda: None,
    "build_aesthetics": lambda: None,
    "build_landmarker": lambda: None,
}


class _CancellingEyeClient(FakeEyeClient):
    """Zaehlt Versuche: der zweite endet in der unterbrochenen Wartezeit."""

    def __init__(self, payloads: dict[int, dict]) -> None:
        super().__init__(payloads)
        self.attempts = 0

    async def analyze(self, image_bytes: bytes) -> dict:
        self.attempts += 1
        if self.attempts > 1:
            raise RunCancelled
        return await super().analyze(image_bytes)


class _CancellingCloudClient(FakeCloudClient):
    def __init__(self, *, model: str) -> None:
        super().__init__(model=model)
        self.attempts = 0

    async def classify(self, image_bytes: bytes, mime_type: str, photo_id: int):  # type: ignore[no-untyped-def]
        self.attempts += 1
        if self.attempts > 1:
            raise RunCancelled
        return await super().classify(image_bytes, mime_type, photo_id)


async def test_a_cancel_stops_the_eye_side_after_the_running_photo(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    user = await _make_user(db_session)
    photos = [await _add_photo(db_session, project, tmp_path, f"{i}.jpg") for i in range(4)]
    review = await _make_review(
        db_session,
        project,
        user,
        [
            _side("a", ClassificationReviewSideKind.EYE, eye_mapping_version=MAPPING_VERSION),
            _side("b", ClassificationReviewSideKind.LOCAL),
        ],
    )
    client = _CancellingEyeClient({photo.id: _payload(tags={"Mensch": 0.5}) for photo in photos})

    result = await execute_classification_review(
        db_session,
        review,
        tmp_path,
        build_eye_client=lambda: client,
        **_LOCAL_BUILDERS,  # type: ignore[arg-type]
    )

    assert result.status == ScanStatus.CANCELLED
    assert result.error_message is None
    # Die Eye-Seite schreibt erst am Phasenende: die Speicher-Analyse des angefangenen Fotos
    # faellt mit dem Rollback des Endzustands weg, und der Lauf behaelt seinen Teilschritt.
    results = (
        (
            await db_session.execute(
                select(ClassificationReviewResult).where(
                    ClassificationReviewResult.review_id == review.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert results == []
    assert client.attempts == 2
    assert result.phase is not None
    assert (await db_session.execute(select(ClassificationReviewCase))).scalars().all() == []


async def test_a_cancel_in_a_cloud_block_writes_no_cases_and_no_error(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    user = await _make_user(db_session)
    for index in range(4):
        await _add_photo(db_session, project, tmp_path, f"{index}.jpg")
    review = await _make_review(
        db_session,
        project,
        user,
        [
            _side("a", ClassificationReviewSideKind.LOCAL),
            _side(
                "b",
                ClassificationReviewSideKind.CLOUD,
                provider="anthropic",
                model="claude-sonnet-5",
            ),
        ],
    )

    result = await execute_classification_review(
        db_session,
        review,
        tmp_path,
        build_cloud_client=lambda model: _CancellingCloudClient(model=model),
        **_LOCAL_BUILDERS,  # type: ignore[arg-type]
    )

    assert result.status == ScanStatus.CANCELLED
    assert result.error_message is None
    cloud_side = (
        await db_session.execute(
            select(ClassificationReviewSide).where(
                ClassificationReviewSide.review_id == review.id,
                ClassificationReviewSide.kind == ClassificationReviewSideKind.CLOUD.value,
            )
        )
    ).scalar_one()
    # Ein abgebrochener Aufruf ist kein Fehlschlag und kostet auch nicht.
    assert cloud_side.failed_calls == 0
    assert cloud_side.api_calls == 1
    assert (await db_session.execute(select(ClassificationReviewCase))).scalars().all() == []


async def test_the_job_takes_over_a_queued_review_and_skips_a_cancelled_one(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = await _make_project(db_session)
    user = await _make_user(db_session)
    await _add_photo(db_session, project, tmp_path, "one.jpg")
    review = await _make_review(
        db_session,
        project,
        user,
        [_side("a", ClassificationReviewSideKind.LOCAL)],
    )
    review.status = ScanStatus.CANCELLED
    review.cancel_requested_at = datetime(2030, 1, 1, tzinfo=UTC)
    await db_session.commit()
    monkeypatch.setattr(db_module, "async_session_factory", lambda: _SameSession(db_session))

    result = await run_classification_review({}, review.id)

    assert result is None
    await db_session.refresh(review)
    assert review.status == ScanStatus.CANCELLED


class _SameSession:
    """Die Session des Tests statt einer neuen - der Job laeuft in derselben Datenbank."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *args: object) -> None:
        return None
