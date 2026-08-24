from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import worker
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCriterionScore,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
)
from photosort.worker import reassign_photo_category

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt 7:
# sofortige Wirkung des Overrides - gezielte Partitions-Neusortierung statt vollem Re-Scoring.


async def _make_project(session: AsyncSession) -> Project:
    project = Project(name="Costa Rica", opencloud_drive_id="drive-1", opencloud_path="p")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_photo(session: AsyncSession, project: Project, path: str) -> Photo:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag="etag",
        content_length=1,
        taken_at=now,
        last_modified=now,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _add_criterion_scoring_run(
    session: AsyncSession, project: Project
) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.commit()
    await session.refresh(scoring_run)
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _add_criterion_score(
    session: AsyncSession, photo: Photo, criterion_key: str, value: float
) -> None:
    session.add(
        PhotoCriterionScore(
            photo_id=photo.id,
            criterion_key=criterion_key,
            value=value,
            source=CriterionSource.LOCAL_HEURISTIC,
            computed_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def _add_ranking(
    session: AsyncSession,
    run: CriterionScoringRun,
    photo: Photo,
    *,
    cluster_key: str,
    category_key: str,
    rank_score: float,
    rank_position: int,
) -> PhotoRanking:
    ranking = PhotoRanking(
        criterion_scoring_run_id=run.id,
        photo_id=photo.id,
        cluster_key=cluster_key,
        category_key=category_key,
        rank_score=rank_score,
        rank_position=rank_position,
    )
    session.add(ranking)
    await session.commit()
    await session.refresh(ranking)
    return ranking


async def test_no_op_when_the_new_category_key_matches_the_current_one(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)
    photo = await _add_photo(db_session, project, "a.jpg")
    await _add_ranking(
        db_session,
        run,
        photo,
        cluster_key="c1",
        category_key="people",
        rank_score=1.0,
        rank_position=1,
    )

    calls: list[object] = []
    original_rank_photos = worker.rank_photos

    def spy(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return original_rank_photos(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(worker, "rank_photos", spy)
    await reassign_photo_category(db_session, run.id, photo.id, "c1", "people")

    assert calls == []
    ranking = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.photo_id == photo.id)
        )
    ).scalar_one()
    assert ranking.category_key == "people"


async def test_moving_a_photo_recomputes_rank_in_both_partitions(
    db_session: AsyncSession,
) -> None:
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)

    # Partition A ("people"): zwei Fotos.
    photo_a1 = await _add_photo(db_session, project, "a1.jpg")
    await _add_criterion_score(db_session, photo_a1, "sharpness", 0.9)
    ranking_a1 = await _add_ranking(
        db_session,
        run,
        photo_a1,
        cluster_key="c1",
        category_key="people",
        rank_score=0.9,
        rank_position=1,
    )
    photo_a2 = await _add_photo(db_session, project, "a2.jpg")
    await _add_criterion_score(db_session, photo_a2, "sharpness", 0.5)
    ranking_a2 = await _add_ranking(
        db_session,
        run,
        photo_a2,
        cluster_key="c1",
        category_key="people",
        rank_score=0.5,
        rank_position=2,
    )

    # Partition B ("landscape"): ein Foto - wird gleich um photo_a2 erweitert.
    photo_b1 = await _add_photo(db_session, project, "b1.jpg")
    await _add_criterion_score(db_session, photo_b1, "sharpness", 0.3)
    ranking_b1 = await _add_ranking(
        db_session,
        run,
        photo_b1,
        cluster_key="c1",
        category_key="landscape",
        rank_score=0.3,
        rank_position=1,
    )

    await reassign_photo_category(db_session, run.id, photo_a2.id, "c1", "landscape")

    await db_session.refresh(ranking_a1)
    await db_session.refresh(ranking_a2)
    await db_session.refresh(ranking_b1)

    # Partition A hat jetzt nur noch photo_a1 - bleibt Rang 1.
    assert ranking_a1.category_key == "people"
    assert ranking_a1.rank_position == 1

    # Partition B hat jetzt photo_b1 (0.3) und photo_a2 (0.5) - photo_a2 hat den hoeheren Score,
    # gewinnt also Rang 1, photo_b1 rueckt auf Rang 2.
    assert ranking_a2.category_key == "landscape"
    assert ranking_a2.rank_position == 1
    assert ranking_b1.rank_position == 2


async def test_no_matching_ranking_row_is_a_safe_no_op(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    run = await _add_criterion_scoring_run(db_session, project)
    # Kein PhotoRanking fuer photo_id=999 im Lauf - defensiver No-op statt Exception (die
    # eigentliche 404/409-Validierung lebt am API-Endpunkt, nicht hier).
    await reassign_photo_category(db_session, run.id, 999, "c1", "people")
