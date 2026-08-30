from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

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
    Rating,
    RatingStatus,
    RemoteCategoryClassificationRun,
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


async def test_project_cloud_vision_consent_defaults(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.commit()

    result = await db_session.execute(select(Project).where(Project.id == project.id))
    stored = result.scalar_one()
    assert stored.cloud_vision_detection_enabled is False
    assert stored.cloud_vision_consent_at is None


async def test_project_cloud_vision_consent_can_be_enabled(db_session: AsyncSession) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    now = datetime.now(UTC)
    project.cloud_vision_detection_enabled = True
    project.cloud_vision_consent_at = now
    await db_session.commit()

    result = await db_session.execute(select(Project).where(Project.id == project.id))
    stored = result.scalar_one()
    assert stored.cloud_vision_detection_enabled is True
    assert stored.cloud_vision_consent_at is not None


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


# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
# specs/architecture/0002-testkonzept.md ab hier: Cascade-Tests fuer die drei neuen Tabellen
# (fine_labels, photo_fine_labels, remote_category_classification_runs) - Review-Fund
# (test-engineer): fehlten trotz explizitem Testkonzept-Verweis. Realer Codepfad, der das
# betrifft: worker.py::run_project_scan loescht Photo-Zeilen bei Rescan fuer entfernte Dateien -
# ein bereits remote-klassifiziertes Foto mit photo_fine_labels-Zeilen durchlaeuft diesen
# Pfad tatsaechlich.


async def test_deleting_photo_cascades_to_fine_label_rows_but_keeps_the_fine_label(
    db_session: AsyncSession,
) -> None:
    photo = await _make_photo(db_session)
    hund = FineLabel(canonical_key="hund", display_name="Hund", embedding=[0.1, 0.2])
    strand = FineLabel(canonical_key="strand", display_name="Strand", embedding=[0.3, 0.4])
    db_session.add_all([hund, strand])
    await db_session.flush()
    now = datetime.now(UTC)
    db_session.add_all(
        [
            PhotoFineLabel(
                photo_id=photo.id,
                fine_label_id=hund.id,
                raw_label="Hund",
                provider="anthropic",
                computed_at=now,
            ),
            PhotoFineLabel(
                photo_id=photo.id,
                fine_label_id=strand.id,
                raw_label="Strand",
                provider="anthropic",
                computed_at=now,
            ),
        ]
    )
    await db_session.commit()

    await db_session.delete(photo)
    await db_session.commit()

    detections = (await db_session.execute(select(PhotoFineLabel))).scalars().all()
    assert detections == []
    # fine_labels ist bewusst KEIN Cascade-Ziel (ADR 0032: projektuebergreifende Registry,
    # keine Fotoinhalte) - beide Eintraege bleiben nach dem Loeschen des einzigen referenzierenden
    # Fotos bestehen.
    remaining_labels = (await db_session.execute(select(FineLabel))).scalars().all()
    assert {label.canonical_key for label in remaining_labels} == {"hund", "strand"}


async def test_deleting_project_cascades_to_remote_category_classification_runs(
    db_session: AsyncSession,
) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()
    db_session.add(
        RemoteCategoryClassificationRun(project_id=project.id, status=ScanStatus.SUCCESS)
    )
    await db_session.commit()

    await db_session.delete(project)
    await db_session.commit()

    result = await db_session.execute(select(RemoteCategoryClassificationRun))
    assert result.scalars().all() == []


async def test_deleting_project_leaves_shared_fine_label_and_other_project_untouched(
    db_session: AsyncSession,
) -> None:
    # Zwei Projekte referenzieren denselben (projektuebergreifenden) fine_labels-Eintrag -
    # das Loeschen eines Projekts darf weder den geteilten Label-Eintrag noch den Foto-/Detection-
    # Bestand des ANDEREN Projekts beruehren (ADR 0032, Isolationsgarantie trotz geteilter
    # Registry).
    project_a = Project(name="Projekt A", opencloud_drive_id="d", opencloud_path="/a")
    project_b = Project(name="Projekt B", opencloud_drive_id="d", opencloud_path="/b")
    db_session.add_all([project_a, project_b])
    await db_session.flush()
    photo_a = await _make_photo(db_session, project_a)
    photo_b = await _make_photo(db_session, project_b)

    shared_label = FineLabel(canonical_key="hund", display_name="Hund", embedding=[0.1, 0.2])
    db_session.add(shared_label)
    await db_session.flush()
    now = datetime.now(UTC)
    db_session.add_all(
        [
            PhotoFineLabel(
                photo_id=photo_a.id,
                fine_label_id=shared_label.id,
                raw_label="Hund",
                provider="anthropic",
                computed_at=now,
            ),
            PhotoFineLabel(
                photo_id=photo_b.id,
                fine_label_id=shared_label.id,
                raw_label="hund",
                provider="mistral",
                computed_at=now,
            ),
        ]
    )
    await db_session.commit()

    await db_session.delete(project_a)
    await db_session.commit()

    remaining_labels = (await db_session.execute(select(FineLabel))).scalars().all()
    assert [label.canonical_key for label in remaining_labels] == ["hund"]

    remaining_photos = (await db_session.execute(select(Photo))).scalars().all()
    assert [p.id for p in remaining_photos] == [photo_b.id]

    remaining_detections = (
        (await db_session.execute(select(PhotoFineLabel))).scalars().all()
    )
    assert [d.photo_id for d in remaining_detections] == [photo_b.id]


# specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
# fehler-persistierung.md Punkt 2 ab hier: neue, schlanke Tabelle photo_cloud_vision_errors -
# erfasst ausschliesslich den letzten bekannten Fehlschlag je Foto x CloudVisionPhase, composite
# PK (photo_id, phase), kein Verlauf.


async def test_create_photo_cloud_vision_error(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)
    now = datetime.now(UTC)
    db_session.add(
        PhotoCloudVisionError(
            photo_id=photo.id,
            phase=CloudVisionPhase.LANDMARK,
            error_type="LandmarkApiError",
            error_message="Anthropic Vision API nicht erreichbar: timeout",
            attempted_at=now,
        )
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    stored = result.scalar_one()
    assert stored.phase == CloudVisionPhase.LANDMARK
    assert stored.error_type == "LandmarkApiError"
    assert stored.error_message == "Anthropic Vision API nicht erreichbar: timeout"
    # SQLite (Testumgebung) speichert DateTime-Spalten tz-naiv - vergleicht denselben Zeitpunkt,
    # nicht dieselbe tzinfo (analog test_worker_criterion_scoring.py-Konvention).
    assert stored.attempted_at == now.replace(tzinfo=None)


async def test_photo_cloud_vision_error_composite_pk_allows_both_phases_for_same_photo(
    db_session: AsyncSession,
) -> None:
    # (photo_id, phase) ist der Primary Key (ADR 0035 Punkt 2) - ein Foto kann fuer BEIDE Phasen
    # gleichzeitig eine Fehler-Zeile haben, kein Konflikt.
    photo = await _make_photo(db_session)
    now = datetime.now(UTC)
    db_session.add_all(
        [
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.LANDMARK,
                error_type="LandmarkApiError",
                error_message="Fehler A",
                attempted_at=now,
            ),
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.REMOTE_CATEGORY,
                error_type="RemoteCategoryClassificationApiError",
                error_message="Fehler B",
                attempted_at=now,
            ),
        ]
    )
    await db_session.commit()

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    rows = result.scalars().all()
    assert {row.phase for row in rows} == {
        CloudVisionPhase.LANDMARK,
        CloudVisionPhase.REMOTE_CATEGORY,
    }


async def test_photo_cloud_vision_error_duplicate_phase_for_same_photo_conflicts(
    db_session: AsyncSession,
) -> None:
    # Kein Verlauf (ADR 0035 Punkt 2): eine zweite Zeile fuer dasselbe (photo_id, phase) verletzt
    # den Composite-PK - ein erneuter Fehlschlag muss stattdessen ueber ein Upsert
    # (worker.py::_record_cloud_vision_error) die bestehende Zeile aktualisieren, nicht eine neue
    # Zeile einfuegen.
    photo = await _make_photo(db_session)
    now = datetime.now(UTC)
    db_session.add(
        PhotoCloudVisionError(
            photo_id=photo.id,
            phase=CloudVisionPhase.LANDMARK,
            error_type="LandmarkApiError",
            error_message="Fehler A",
            attempted_at=now,
        )
    )
    await db_session.commit()

    db_session.add(
        PhotoCloudVisionError(
            photo_id=photo.id,
            phase=CloudVisionPhase.LANDMARK,
            error_type="LandmarkApiError",
            error_message="Fehler B",
            attempted_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_deleting_photo_cascades_to_cloud_vision_errors(db_session: AsyncSession) -> None:
    # Vorsorglich ergaenzt (specs/architecture/0002-testkonzept.md, siehe test_deleting_photo_
    # cascades_to_landmark_detection oben) - Photo.cloud_vision_errors braucht
    # cascade="all, delete-orphan".
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoCloudVisionError(
            photo_id=photo.id,
            phase=CloudVisionPhase.REMOTE_CATEGORY,
            error_type="RemoteCategoryClassificationApiError",
            error_message="Fehler",
            attempted_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    await db_session.delete(photo)
    await db_session.commit()

    result = await db_session.execute(select(PhotoCloudVisionError))
    assert result.scalars().all() == []


async def test_photo_cloud_vision_error_has_the_expected_columns(
    db_session: AsyncSession,
) -> None:
    # Migrations-Nachweis der Teststrategie ("neue Tabelle per inspect() verifiziert"), analog
    # test_photo_landmark_detection_has_a_provider_column oben.
    def _get_columns(sync_session: Session) -> set[str]:
        bind = sync_session.get_bind()
        return {col["name"] for col in inspect(bind).get_columns("photo_cloud_vision_errors")}

    columns = await db_session.run_sync(_get_columns)
    assert columns == {"photo_id", "phase", "error_type", "error_message", "attempted_at"}


# specs/features/0289-feste-kategorien.md, Umsetzungsschritt 3a ab hier: die neue 1:1-Tabelle
# photo_category_classifications - haelt die remote ermittelte Kategorie samt VALIDIERTER
# Kandidatenliste und ist zugleich das Erfolgssignal der Remote-Phase.


async def test_photo_category_classification_is_one_to_one_and_round_trips(
    db_session: AsyncSession,
) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoCategoryClassification(
            photo_id=photo.id,
            category_key="menschen",
            detected_categories=["menschen", "landschaft"],
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    db_session.expunge_all()

    stored = (
        await db_session.execute(select(PhotoCategoryClassification))
    ).scalars().one()
    assert stored.photo_id == photo.id
    assert stored.category_key == "menschen"
    assert stored.detected_categories == ["menschen", "landschaft"]
    assert stored.provider == "anthropic"


async def test_a_second_classification_row_for_the_same_photo_is_rejected(
    db_session: AsyncSession,
) -> None:
    # photo_id ist Primary Key (kein separates id+Unique-Paar) - ein zweiter Lauf ueber dasselbe
    # Foto darf strukturell keine zweite Zeile erzeugen.
    photo = await _make_photo(db_session)
    now = datetime.now(UTC)
    db_session.add(
        PhotoCategoryClassification(
            photo_id=photo.id,
            category_key="tier",
            detected_categories=["tier"],
            provider="anthropic",
            computed_at=now,
        )
    )
    await db_session.commit()

    db_session.add(
        PhotoCategoryClassification(
            photo_id=photo.id,
            category_key="menschen",
            detected_categories=["menschen"],
            provider="anthropic",
            computed_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_deleting_photo_cascades_to_its_category_classification(
    db_session: AsyncSession,
) -> None:
    # Realer Codepfad: worker.py::run_project_scan loescht Photo-Zeilen bei Rescan fuer entfernte
    # Dateien - ein bereits remote-klassifiziertes Foto durchlaeuft diesen Pfad tatsaechlich.
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoCategoryClassification(
            photo_id=photo.id,
            category_key="nicht_erkannt",
            detected_categories=[],
            provider="mistral",
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    await db_session.delete(photo)
    await db_session.commit()

    remaining = (await db_session.execute(select(PhotoCategoryClassification))).scalars().all()
    assert remaining == []
