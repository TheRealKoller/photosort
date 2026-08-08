from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    Photo,
    PhotoCategory,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanRun,
    ScanStatus,
    ScoringRun,
    TopSelectionRun,
    User,
)


async def test_create_project(db_session: AsyncSession) -> None:
    project = Project(
        name="Costa Rica", opencloud_drive_id="drive-1", opencloud_path="/Urlaub/CostaRica"
    )
    db_session.add(project)
    await db_session.commit()

    result = await db_session.execute(select(Project).where(Project.name == "Costa Rica"))
    stored = result.scalar_one()
    assert stored.opencloud_path == "/Urlaub/CostaRica"


async def test_project_name_is_unique(db_session: AsyncSession) -> None:
    db_session.add(Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a"))
    await db_session.commit()

    db_session.add(Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/b"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_photo_unique_per_project_and_path(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    now = datetime.now(UTC)
    db_session.add(
        Photo(
            project_id=project.id,
            relative_path="img001.jpg",
            etag="etag-1",
            content_length=123,
            taken_at=now,
            last_modified=now,
        )
    )
    await db_session.commit()

    db_session.add(
        Photo(
            project_id=project.id,
            relative_path="img001.jpg",
            etag="etag-2",
            content_length=456,
            taken_at=now,
            last_modified=now,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_scan_run_defaults(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    scan_run = ScanRun(project_id=project.id, status=ScanStatus.RUNNING)
    db_session.add(scan_run)
    await db_session.commit()

    result = await db_session.execute(select(ScanRun).where(ScanRun.project_id == project.id))
    stored = result.scalar_one()
    assert stored.status == ScanStatus.RUNNING
    assert stored.files_found == 0
    assert stored.photos_added == 0
    assert stored.error_message is None


async def test_create_user(db_session: AsyncSession) -> None:
    user = User(username="daniel", password_hash="hashed-value")
    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.username == "daniel"))
    stored = result.scalar_one()
    assert stored.password_hash == "hashed-value"
    assert stored.created_at is not None


async def test_user_username_is_unique(db_session: AsyncSession) -> None:
    db_session.add(User(username="daniel", password_hash="a"))
    await db_session.commit()

    db_session.add(User(username="daniel", password_hash="b"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def _make_photo_and_user(db_session: AsyncSession) -> tuple[Photo, User]:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    now = datetime.now(UTC)
    photo = Photo(
        project_id=project.id,
        relative_path="img001.jpg",
        etag="etag-1",
        content_length=123,
        taken_at=now,
        last_modified=now,
    )
    user = User(username="daniel", password_hash="hashed-value")
    db_session.add_all([photo, user])
    await db_session.flush()
    return photo, user


async def test_create_rating(db_session: AsyncSession) -> None:
    photo, user = await _make_photo_and_user(db_session)

    rating = Rating(photo_id=photo.id, user_id=user.id, status=RatingStatus.FAVORITE)
    db_session.add(rating)
    await db_session.commit()

    result = await db_session.execute(select(Rating).where(Rating.photo_id == photo.id))
    stored = result.scalar_one()
    assert stored.status == RatingStatus.FAVORITE
    assert stored.updated_at is not None


async def test_rating_unique_per_photo_and_user(db_session: AsyncSession) -> None:
    photo, user = await _make_photo_and_user(db_session)

    db_session.add(Rating(photo_id=photo.id, user_id=user.id, status=RatingStatus.FAVORITE))
    await db_session.commit()

    db_session.add(Rating(photo_id=photo.id, user_id=user.id, status=RatingStatus.REJECTED))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_deleting_photo_cascades_to_ratings(db_session: AsyncSession) -> None:
    photo, user = await _make_photo_and_user(db_session)
    db_session.add(Rating(photo_id=photo.id, user_id=user.id, status=RatingStatus.FAVORITE))
    await db_session.commit()

    await db_session.delete(photo)
    await db_session.commit()

    result = await db_session.execute(select(Rating))
    assert result.scalars().all() == []


async def _make_photo(db_session: AsyncSession, project: Project | None = None) -> Photo:
    if project is None:
        project = Project(
            name=f"Project {uuid4()}", opencloud_drive_id="d", opencloud_path="/a"
        )
        db_session.add(project)
        await db_session.flush()

    now = datetime.now(UTC)
    photo = Photo(
        project_id=project.id,
        relative_path=f"img-{uuid4()}.jpg",
        etag="etag-1",
        content_length=123,
        taken_at=now,
        last_modified=now,
    )
    db_session.add(photo)
    await db_session.flush()
    return photo


async def test_scoring_run_defaults(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.RUNNING)
    db_session.add(scoring_run)
    await db_session.commit()

    result = await db_session.execute(
        select(ScoringRun).where(ScoringRun.project_id == project.id)
    )
    stored = result.scalar_one()
    assert stored.status == ScanStatus.RUNNING
    assert stored.photos_total == 0
    assert stored.photos_processed == 0
    assert stored.error_message is None


async def test_create_photo_score(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)

    score = PhotoScore(
        photo_id=photo.id,
        sharpness=42.0,
        exposure=0.1,
        phash="0" * 16,
        computed_at=datetime.now(UTC),
    )
    db_session.add(score)
    await db_session.commit()

    result = await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    stored = result.scalar_one()
    assert stored.sharpness == 42.0
    assert stored.duplicate_of is None
    assert stored.cluster_key is None
    assert stored.local_quality_score is None
    assert stored.suggested_status is None


async def test_photo_score_is_one_to_one_with_photo(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoScore(photo_id=photo.id, sharpness=1.0, exposure=0.0, computed_at=datetime.now(UTC))
    )
    await db_session.commit()

    db_session.add(
        PhotoScore(photo_id=photo.id, sharpness=2.0, exposure=0.0, computed_at=datetime.now(UTC))
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_deleting_photo_cascades_to_photo_score(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoScore(photo_id=photo.id, sharpness=1.0, exposure=0.0, computed_at=datetime.now(UTC))
    )
    await db_session.commit()

    await db_session.delete(photo)
    await db_session.commit()

    result = await db_session.execute(select(PhotoScore))
    assert result.scalars().all() == []


async def test_photo_score_category_defaults_to_none(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoScore(photo_id=photo.id, sharpness=1.0, exposure=0.0, computed_at=datetime.now(UTC))
    )
    await db_session.commit()

    result = await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    assert result.scalar_one().category is None


async def test_photo_score_category_can_be_set(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=1.0,
            exposure=0.0,
            category=PhotoCategory.LANDSCAPE,
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    result = await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    assert result.scalar_one().category == PhotoCategory.LANDSCAPE


async def test_top_selection_run_defaults(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    run = TopSelectionRun(project_id=project.id, status=ScanStatus.RUNNING, top_n_per_cluster=3)
    db_session.add(run)
    await db_session.commit()

    result = await db_session.execute(
        select(TopSelectionRun).where(TopSelectionRun.project_id == project.id)
    )
    stored = result.scalar_one()
    assert stored.status == ScanStatus.RUNNING
    assert stored.top_n_per_cluster == 3
    assert stored.candidates_total == 0
    assert stored.candidates_processed == 0
    assert stored.suggestions_found == 0
    assert stored.error_message is None


async def test_deleting_project_cascades_to_top_selection_runs(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()
    db_session.add(
        TopSelectionRun(project_id=project.id, status=ScanStatus.SUCCESS, top_n_per_cluster=3)
    )
    await db_session.commit()

    await db_session.delete(project)
    await db_session.commit()

    result = await db_session.execute(select(TopSelectionRun))
    assert result.scalars().all() == []


async def test_photo_score_duplicate_of_references_another_photo(db_session: AsyncSession) -> None:
    kept = await _make_photo(db_session)
    loser = await _make_photo(db_session)
    db_session.add(
        PhotoScore(
            photo_id=loser.id,
            sharpness=1.0,
            exposure=0.0,
            duplicate_of=kept.id,
            suggested_status=RatingStatus.REJECTED,
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    result = await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == loser.id))
    stored = result.scalar_one()
    assert stored.duplicate_of == kept.id
    assert stored.suggested_status == RatingStatus.REJECTED
