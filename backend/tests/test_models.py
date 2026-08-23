from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCriterionScore,
    PhotoLandmarkDetection,
    PhotoRanking,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanRun,
    ScanStatus,
    ScoringRun,
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
    # Watchdog-Spalte (specs/features/0034-scan-haenger-fortschritts-watchdog.md): analog zu
    # started_at server-seitig defaultet, damit ein frisch angelegter Lauf sofort einen
    # last_progress_at-Wert hat und nicht als sofortiger Stillstand gilt.
    assert stored.last_progress_at is not None
    # specs/features/0036-scan-performance-zweiphasig-parallel.md: total_files defaultet auf None
    # (nicht 0) - unterscheidet "Enumerationsphase noch nicht abgeschlossen" explizit von "Projekt
    # enthaelt 0 Dateien" (ADR 0020, Punkt 6).
    assert stored.total_files is None


async def test_scan_run_total_files_distinguishes_none_from_zero(db_session: AsyncSession) -> None:
    """specs/features/0036: total_files=0 (leeres Projekt, Phase 1 abgeschlossen) muss von
    total_files=None (Phase 1 noch nicht abgeschlossen) unterscheidbar bleiben - insbesondere darf
    eine `is not None`-Pruefung nicht durch eine truthy-Pruefung ersetzt werden koennen, die 0
    faelschlich als "noch nicht abgeschlossen" behandeln wuerde."""
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    scan_run = ScanRun(project_id=project.id, status=ScanStatus.RUNNING, total_files=0)
    db_session.add(scan_run)
    await db_session.commit()

    result = await db_session.execute(select(ScanRun).where(ScanRun.project_id == project.id))
    stored = result.scalar_one()
    assert stored.total_files == 0
    assert stored.total_files is not None


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
    assert stored.last_progress_at is not None
    # Ausschuss-Gate (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md):
    # additiv, defaultet auf None (nicht bestaetigt) - kein server_default noetig, ein frischer
    # Lauf startet immer ungate-bestaetigt.
    assert stored.gate_confirmed_at is None


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


async def test_create_photo_criterion_score(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)

    score = PhotoCriterionScore(
        photo_id=photo.id,
        criterion_key="sharpness",
        value=0.8,
        source=CriterionSource.LOCAL_HEURISTIC,
        computed_at=datetime.now(UTC),
    )
    db_session.add(score)
    await db_session.commit()

    result = await db_session.execute(
        select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
    )
    stored = result.scalar_one()
    assert stored.criterion_key == "sharpness"
    assert stored.value == 0.8
    assert stored.source == CriterionSource.LOCAL_HEURISTIC


async def test_photo_criterion_score_unique_per_photo_and_criterion_key(
    db_session: AsyncSession,
) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoCriterionScore(
            photo_id=photo.id,
            criterion_key="sharpness",
            value=0.8,
            source=CriterionSource.LOCAL_HEURISTIC,
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    db_session.add(
        PhotoCriterionScore(
            photo_id=photo.id,
            criterion_key="sharpness",
            value=0.5,
            source=CriterionSource.LOCAL_HEURISTIC,
            computed_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_deleting_photo_cascades_to_criterion_scores(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoCriterionScore(
            photo_id=photo.id,
            criterion_key="sharpness",
            value=0.8,
            source=CriterionSource.LOCAL_HEURISTIC,
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    await db_session.delete(photo)
    await db_session.commit()

    result = await db_session.execute(select(PhotoCriterionScore))
    assert result.scalars().all() == []


async def test_criterion_scoring_run_defaults(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    db_session.add(scoring_run)
    await db_session.flush()

    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.RUNNING
    )
    db_session.add(run)
    await db_session.commit()

    result = await db_session.execute(
        select(CriterionScoringRun).where(CriterionScoringRun.project_id == project.id)
    )
    stored = result.scalar_one()
    assert stored.status == ScanStatus.RUNNING
    assert stored.scoring_run_id == scoring_run.id
    assert stored.photos_total == 0
    assert stored.photos_processed == 0
    assert stored.error_message is None
    assert stored.last_progress_at is not None


async def test_deleting_project_cascades_to_criterion_scoring_runs(
    db_session: AsyncSession,
) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    db_session.add(scoring_run)
    await db_session.flush()
    db_session.add(
        CriterionScoringRun(
            project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
        )
    )
    await db_session.commit()

    await db_session.delete(project)
    await db_session.commit()

    result = await db_session.execute(select(CriterionScoringRun))
    assert result.scalars().all() == []


async def test_create_photo_ranking(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    db_session.add(scoring_run)
    await db_session.flush()
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    db_session.add(run)
    await db_session.flush()
    photo = await _make_photo(db_session, project)

    ranking = PhotoRanking(
        criterion_scoring_run_id=run.id,
        photo_id=photo.id,
        cluster_key="cluster-0",
        category_key="landscape",
        rank_score=0.9,
        rank_position=1,
    )
    db_session.add(ranking)
    await db_session.commit()

    result = await db_session.execute(
        select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
    )
    stored = result.scalar_one()
    assert stored.photo_id == photo.id
    assert stored.category_key == "landscape"
    assert stored.rank_position == 1


async def test_photo_ranking_unique_per_run_and_photo(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    db_session.add(scoring_run)
    await db_session.flush()
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
    )
    db_session.add(run)
    await db_session.flush()
    photo = await _make_photo(db_session, project)
    db_session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            cluster_key="cluster-0",
            category_key="landscape",
            rank_score=0.9,
            rank_position=1,
        )
    )
    await db_session.commit()

    db_session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            cluster_key="cluster-0",
            category_key="landscape",
            rank_score=0.1,
            rank_position=2,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


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


# specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR decisions/0025-cloud-
# landmark-erkennung.md Punkt 5/6 ab hier: projektweiter Einwilligungs-Schalter + neue,
# dedizierte Tabelle fuer den erkannten Landmark-Namen.


async def test_project_cloud_landmark_consent_defaults(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.commit()

    result = await db_session.execute(select(Project).where(Project.id == project.id))
    stored = result.scalar_one()
    assert stored.cloud_landmark_detection_enabled is False
    assert stored.cloud_landmark_consent_at is None


async def test_project_cloud_landmark_consent_can_be_enabled(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    now = datetime.now(UTC)
    project.cloud_landmark_detection_enabled = True
    project.cloud_landmark_consent_at = now
    await db_session.commit()

    result = await db_session.execute(select(Project).where(Project.id == project.id))
    stored = result.scalar_one()
    assert stored.cloud_landmark_detection_enabled is True
    assert stored.cloud_landmark_consent_at is not None


async def test_create_photo_landmark_detection(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoLandmarkDetection(
            photo_id=photo.id,
            name="Eiffelturm",
            confidence=0.87,
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
    )
    stored = result.scalar_one()
    assert stored.name == "Eiffelturm"
    assert stored.confidence == 0.87


async def test_photo_landmark_detection_is_one_to_one_with_photo(
    db_session: AsyncSession,
) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoLandmarkDetection(
            photo_id=photo.id, name="Eiffelturm", confidence=0.87, computed_at=datetime.now(UTC)
        )
    )
    await db_session.commit()

    db_session.add(
        PhotoLandmarkDetection(
            photo_id=photo.id, name="Kolosseum", confidence=0.5, computed_at=datetime.now(UTC)
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_deleting_photo_cascades_to_landmark_detection(db_session: AsyncSession) -> None:
    # Vorsorglich ergaenzt (specs/architecture/0002-testkonzept.md): exakt diese Art Luecke
    # (fehlende Cascade-Relationship auf einer neuen Kind-Tabelle) trat bei Spec 0044 bereits
    # real auf.
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoLandmarkDetection(
            photo_id=photo.id, name="Eiffelturm", confidence=0.87, computed_at=datetime.now(UTC)
        )
    )
    await db_session.commit()

    await db_session.delete(photo)
    await db_session.commit()

    result = await db_session.execute(select(PhotoLandmarkDetection))
    assert result.scalars().all() == []


# specs/features/0054-mistral-provider-option-cloud-landmark.md, decisions/0031-mistral-provider-
# option-cloud-landmark.md Punkt 5 ab hier: neue additive Spalte photo_landmark_detections.provider
# - verhindert, dass die Herkunft bereits gescorter Fotos bei einem spaeteren Umschalten von
# LANDMARK_PROVIDER stillschweigend unklar wird.


async def test_photo_landmark_detection_provider_defaults_to_anthropic(
    db_session: AsyncSession,
) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoLandmarkDetection(
            photo_id=photo.id, name="Eiffelturm", confidence=0.87, computed_at=datetime.now(UTC)
        )
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
    )
    assert result.scalar_one().provider == "anthropic"


async def test_photo_landmark_detection_provider_can_be_set_to_mistral(
    db_session: AsyncSession,
) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoLandmarkDetection(
            photo_id=photo.id,
            name="Eiffelturm",
            confidence=0.87,
            computed_at=datetime.now(UTC),
            provider="mistral",
        )
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
    )
    assert result.scalar_one().provider == "mistral"


async def test_photo_landmark_detection_has_a_provider_column(db_session: AsyncSession) -> None:
    # Migrations-Nachweis der Teststrategie ("neue Spalte per inspect() verifiziert") - schema
    # wird hier ueber Base.metadata.create_all() (conftest.py::db_session) aus den Models erzeugt,
    # nicht ueber die echte Alembic-Migration; inspect() bestaetigt trotzdem, dass die Spalte
    # tatsaechlich als eigene DB-Spalte existiert statt nur als Python-Attribut.
    def _get_columns(sync_session: Session) -> set[str]:
        bind = sync_session.get_bind()
        return {col["name"] for col in inspect(bind).get_columns("photo_landmark_detections")}

    columns = await db_session.run_sync(_get_columns)
    assert "provider" in columns
