from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    Photo,
    PhotoCategory,
    PhotoScore,
    Project,
    RatingStatus,
    ScanStatus,
    ScoringRun,
)
from photosort.thumbnails import display_path
from photosort.worker import run_project_scoring, run_top_selection


async def _make_project(session: AsyncSession) -> Project:
    project = Project(name="Costa Rica", opencloud_drive_id="drive-1", opencloud_path="CostaRica")
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
    cluster_key: str,
    local_quality_score: float,
    suggested_status: RatingStatus | None = None,
) -> PhotoScore:
    score = PhotoScore(
        photo_id=photo.id,
        sharpness=100.0,
        exposure=0.0,
        cluster_key=cluster_key,
        local_quality_score=local_quality_score,
        suggested_status=suggested_status,
        computed_at=datetime.now(UTC),
    )
    session.add(score)
    await session.commit()
    return score


async def _add_successful_scoring_run(session: AsyncSession, project: Project) -> ScoringRun:
    run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(run)
    await session.commit()
    return run


def _write_display_variant(cache_dir: Path, photo: Photo, image: Image.Image) -> None:
    path = display_path(cache_dir, photo.id, photo.etag)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG")


def _flat_image(color: tuple[int, int, int] = (100, 100, 100), size: int = 160) -> Image.Image:
    # Ohne "Gesicht" (FakeFaceDetector unten) faellt eine komplett flaeche Flaeche ueber die
    # Prioritaetskette von classify_category auf LANDSCAPE.
    return Image.new("RGB", (size, size), color=color)


def _textured_image(size: int = 160) -> Image.Image:
    # Ohne "Gesicht" und ohne hohen Uniform-Flaechen-Anteil -> DETAIL (Fallback).
    image = Image.new("RGB", (size, size), color=(30, 60, 120))
    draw = ImageDraw.Draw(image)
    for offset in range(0, size, 8):
        draw.line((offset, 0, size - offset, size), fill=(220, 180, 90), width=2)
    return image


class NoFaceDetector:
    """Faket den mediapipe FaceDetector so, dass detect_person() nie ein Gesicht findet - der
    injizierte build_detector-Callable ersetzt worker.py::build_face_detector, kein echtes
    .tflite-Modell in Tests (Teststrategie-Abschnitt der Spec)."""

    def detect(self, image: object) -> object:
        return SimpleNamespace(detections=[])


def _no_face_detector() -> NoFaceDetector:
    return NoFaceDetector()


async def test_guard_fails_run_when_no_scoring_run_exists(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)

    run = await run_top_selection(
        db_session,
        project,
        top_n_per_cluster=3,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
    )

    assert run.status == ScanStatus.FAILED
    assert run.error_message is not None


async def test_guard_fails_run_when_latest_scoring_run_is_not_successful(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    db_session.add(ScoringRun(project_id=project.id, status=ScanStatus.FAILED))
    await db_session.commit()

    run = await run_top_selection(
        db_session,
        project,
        top_n_per_cluster=3,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
    )

    assert run.status == ScanStatus.FAILED


async def test_marks_top_photo_of_a_single_photo_cluster_album_worthy(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, cluster_key="cluster-0", local_quality_score=10.0)
    _write_display_variant(tmp_path, photo, _flat_image())

    run = await run_top_selection(
        db_session,
        project,
        top_n_per_cluster=1,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.suggestions_found == 1
    score = (
        await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    ).scalar_one()
    assert score.suggested_status == RatingStatus.ALBUM_WORTHY
    assert score.category == PhotoCategory.LANDSCAPE


async def test_only_considers_candidates_without_an_existing_suggested_status(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    await _add_successful_scoring_run(db_session, project)
    rejected_photo = await _add_photo(
        db_session, project, "rejected.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(
        db_session,
        rejected_photo,
        cluster_key="cluster-0",
        local_quality_score=100.0,
        suggested_status=RatingStatus.REJECTED,
    )
    _write_display_variant(tmp_path, rejected_photo, _flat_image())

    run = await run_top_selection(
        db_session,
        project,
        top_n_per_cluster=1,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.suggestions_found == 0
    score = (
        await db_session.execute(
            select(PhotoScore).where(PhotoScore.photo_id == rejected_photo.id)
        )
    ).scalar_one()
    assert score.suggested_status == RatingStatus.REJECTED
    assert score.category is None


async def test_best_effort_classification_failure_does_not_fail_the_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    await _add_successful_scoring_run(db_session, project)
    broken = await _add_photo(
        db_session, project, "broken.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, broken, cluster_key="cluster-0", local_quality_score=10.0)
    working = await _add_photo(
        db_session, project, "ok.jpg", "etag-2", datetime(2023, 1, 1, 0, 1, tzinfo=UTC)
    )
    await _add_score(db_session, working, cluster_key="cluster-0", local_quality_score=5.0)
    # broken.jpg hat KEINE lesbare display-Cache-Datei (fehlt oder kaputt) - analog
    # scoring.py::_compute_photo_metrics-Verhalten.
    _write_display_variant(tmp_path, working, _flat_image())

    run = await run_top_selection(
        db_session,
        project,
        top_n_per_cluster=2,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
    )

    assert run.status == ScanStatus.SUCCESS
    scores = {
        s.photo_id: s for s in (await db_session.execute(select(PhotoScore))).scalars()
    }
    assert scores[broken.id].category is None
    assert scores[broken.id].suggested_status is None
    assert scores[working.id].category == PhotoCategory.LANDSCAPE
    assert scores[working.id].suggested_status == RatingStatus.ALBUM_WORTHY


async def test_candidate_pool_is_capped_per_cluster_formula(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # top_n_per_cluster=1 -> Pool-Groesse = min(cluster_size, max(1*3, 6)) = min(8, 6) = 6.
    # Die zwei Fotos mit der niedrigsten local_quality_score duerfen nicht einmal klassifiziert
    # werden (Kandidatenpool-Deckelung, Akzeptanzkriterium der Spec).
    project = await _make_project(db_session)
    await _add_successful_scoring_run(db_session, project)
    photos = []
    for i in range(8):
        photo = await _add_photo(
            db_session, project, f"{i}.jpg", f"etag-{i}", datetime(2023, 1, 1, 0, i, tzinfo=UTC)
        )
        await _add_score(db_session, photo, cluster_key="cluster-0", local_quality_score=float(i))
        _write_display_variant(tmp_path, photo, _flat_image())
        photos.append(photo)

    await run_top_selection(
        db_session,
        project,
        top_n_per_cluster=1,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
    )

    scores = {
        s.photo_id: s for s in (await db_session.execute(select(PhotoScore))).scalars()
    }
    # Die beiden Fotos mit der niedrigsten Qualitaet (i=0, i=1) liegen ausserhalb des
    # 6er-Kandidatenpools und bleiben unklassifiziert.
    assert scores[photos[0].id].category is None
    assert scores[photos[1].id].category is None
    assert scores[photos[7].id].category is not None


async def test_category_is_recomputed_on_every_run_no_skip_mechanism(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, cluster_key="cluster-0", local_quality_score=10.0)
    _write_display_variant(tmp_path, photo, _flat_image())

    await run_top_selection(
        db_session,
        project,
        top_n_per_cluster=1,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
    )
    score = (
        await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    ).scalar_one()
    assert score.category == PhotoCategory.LANDSCAPE

    # Zweiter Lauf mit anderem Bildinhalt (texturiert statt flaech) unter derselben etag - die
    # Kategorie muss sich aendern, kein Reuse-Tracking (Akzeptanzkriterium der Spec).
    # suggested_status wird hier direkt zurueckgesetzt statt ueber einen vollen
    # run_project_scoring-Durchlauf zu simulieren, dass zwischen beiden Laeufen bereits ein neuer
    # Phase-A-Lauf stattgefunden hat (dessen Reset-Verhalten ist bereits separat in
    # test_rescoring_resets_album_worthy_suggestions abgedeckt) - sonst wuerde das bereits
    # ALBUM_WORTHY markierte Foto beim zweiten Aufruf gar nicht mehr als Kandidat betrachtet.
    score.suggested_status = None
    await db_session.commit()
    _write_display_variant(tmp_path, photo, _textured_image())
    await run_top_selection(
        db_session,
        project,
        top_n_per_cluster=1,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
    )
    score_after = (
        await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    ).scalar_one()
    assert score_after.category == PhotoCategory.DETAIL


async def test_rescoring_resets_album_worthy_suggestions(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, cluster_key="cluster-0", local_quality_score=10.0)
    _write_display_variant(tmp_path, photo, _flat_image())

    await run_top_selection(
        db_session,
        project,
        top_n_per_cluster=1,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
    )
    score = (
        await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    ).scalar_one()
    assert score.suggested_status == RatingStatus.ALBUM_WORTHY

    await run_project_scoring(db_session, project, cache_dir=tmp_path)

    score_after_rescore = (
        await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    ).scalar_one()
    assert score_after_rescore.suggested_status is None


async def test_progress_is_committed_periodically(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import photosort.worker as worker_module

    monkeypatch.setattr(worker_module, "TOP_SELECTION_COMMIT_BATCH_SIZE", 1)

    project = await _make_project(db_session)
    await _add_successful_scoring_run(db_session, project)
    for i in range(3):
        photo = await _add_photo(
            db_session, project, f"{i}.jpg", f"etag-{i}", datetime(2023, 1, 1, 0, i, tzinfo=UTC)
        )
        await _add_score(db_session, photo, cluster_key="cluster-0", local_quality_score=float(i))
        _write_display_variant(tmp_path, photo, _flat_image())

    run = await run_top_selection(
        db_session,
        project,
        top_n_per_cluster=1,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
    )

    assert run.candidates_total == 3
    assert run.candidates_processed == 3
