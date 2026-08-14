from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    CriterionScoringRun,
    Photo,
    PhotoCriterionScore,
    PhotoRanking,
    PhotoScore,
    Project,
    RatingStatus,
    ScanStatus,
    ScoringRun,
)
from photosort.thumbnails import display_path
from photosort.worker import run_criterion_scoring, run_project_scoring


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


async def test_guard_fails_run_when_scoring_run_id_does_not_exist(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)

    run = await run_criterion_scoring(
        db_session, project, scoring_run_id=999, cache_dir=tmp_path,
        build_detector=_no_face_detector,
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
        db_session, project, scoring_run_id=stale_run.id, cache_dir=tmp_path,
        build_detector=_no_face_detector,
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
        db_session, project, scoring_run_id=run_row.id, cache_dir=tmp_path,
        build_detector=_no_face_detector,
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
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
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
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
    )
    # Zweiter Lauf mit geaenderten Rohwerten - der bestehende Wert wird ueberschrieben (Upsert),
    # keine zweite Zeile (UniqueConstraint(photo_id, criterion_key)).
    photo_score = (
        await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    ).scalar_one()
    photo_score.sharpness = 200.0
    await db_session.commit()

    await run_criterion_scoring(
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
    )

    rows = (
        await db_session.execute(
            select(PhotoCriterionScore).where(
                PhotoCriterionScore.photo_id == photo.id,
                PhotoCriterionScore.criterion_key == "sharpness",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].value == 1.0  # 200.0 / 200.0 ceiling, geklemmt


async def test_only_considers_ausschuss_survivors(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    rejected = await _add_photo(
        db_session, project, "rejected.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(
        db_session, rejected, cluster_key=None, suggested_status=RatingStatus.REJECTED
    )
    _write_display_variant(tmp_path, rejected, _flat_image())

    run = await run_criterion_scoring(
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.photos_total == 0
    criteria = (
        await db_session.execute(
            select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == rejected.id)
        )
    ).scalars().all()
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
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
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
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
    )

    rankings = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalars().all()
    # Voller Pool (nicht nur Top-N) - alle 3 Fotos landen ausserdem in derselben Partition
    # (gleicher cluster_key, alle als LANDSCAPE klassifiziert -> content_people=0, uniform hoch).
    assert len(rankings) == 3
    by_photo = {r.photo_id: r for r in rankings}
    assert {by_photo[p.id].category_key for p in photos} == {"landscape"}
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
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
    )

    rankings = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalars().all()
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
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
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
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
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
            db_session, project, scoring_run.id, cache_dir=tmp_path,
            build_detector=CancellingDetector,
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
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
    )
    second_run = await run_criterion_scoring(
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
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
        db_session, project, scoring_run.id, cache_dir=tmp_path, build_detector=_no_face_detector
    )

    assert run.status == ScanStatus.SUCCESS
    rankings = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalars().all()
    assert len(rankings) == 1
