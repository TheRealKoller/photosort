import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import photosort
from photosort.models import (
    ClassificationPhase,
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
    ProjectCamera,
    Rating,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)
from tests.event_rows import event_id_of_run


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
            taken_at_original=now,
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
            taken_at_original=now,
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
        taken_at_original=now,
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
        project = Project(name=f"Project {uuid4()}", opencloud_drive_id="d", opencloud_path="/a")
        db_session.add(project)
        await db_session.flush()

    now = datetime.now(UTC)
    photo = Photo(
        project_id=project.id,
        relative_path=f"img-{uuid4()}.jpg",
        etag="etag-1",
        content_length=123,
        taken_at=now,
        taken_at_original=now,
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

    result = await db_session.execute(select(ScoringRun).where(ScoringRun.project_id == project.id))
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
    # specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md: fail-closed Defaults -
    # ein Lauf, dem niemand ausdruecklich Cloud-Nutzung mitgibt, hat keine angefordert.
    assert stored.phase is None
    assert stored.cloud_requested is False
    assert stored.cloud_error_message is None


async def test_criterion_scoring_run_stores_phase_and_cloud_fields(
    db_session: AsyncSession,
) -> None:
    """specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, Datenmodell-Bezug:
    `phase` wird als StrEnum-Wert gespeichert und typisiert zurueckgelesen."""
    project = Project(name="Island", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    db_session.add(scoring_run)
    await db_session.flush()

    db_session.add(
        CriterionScoringRun(
            project_id=project.id,
            scoring_run_id=scoring_run.id,
            status=ScanStatus.RUNNING,
            phase=ClassificationPhase.REMOTE_CATEGORIES,
            cloud_requested=True,
            cloud_error_message="Remote-Kategorisierung fehlgeschlagen: boom",
        )
    )
    await db_session.commit()

    stored = (
        await db_session.execute(
            select(CriterionScoringRun).where(CriterionScoringRun.project_id == project.id)
        )
    ).scalar_one()
    assert stored.phase is ClassificationPhase.REMOTE_CATEGORIES
    assert stored.cloud_requested is True
    assert stored.cloud_error_message == "Remote-Kategorisierung fehlgeschlagen: boom"


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
        event_id=await event_id_of_run(db_session, run),
        category_key="landscape",
        rank_score=0.9,
        rank_position=1,
        is_primary=True,
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
    assert stored.is_primary is True


async def _make_ranked_photo(
    db_session: AsyncSession,
) -> tuple[CriterionScoringRun, Photo]:
    """Ein Lauf mit einem Foto und dessen HAUPTZEILE - die Vorbedingung aller
    Mehrfachzugehoerigkeits-Faelle."""
    project = Project(name=f"Project {uuid4()}", opencloud_drive_id="d", opencloud_path="/a")
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
            event_id=await event_id_of_run(db_session, run),
            category_key="menschen",
            rank_score=0.9,
            rank_position=1,
            is_primary=True,
        )
    )
    await db_session.commit()
    return run, photo


async def test_photo_ranking_unique_per_run_photo_and_category(
    db_session: AsyncSession,
) -> None:
    """specs/features/0300-nebenkategorien.md, Akzeptanzkriterium 20: der Constraint ist von
    `(Lauf, Foto)` auf `(Lauf, Foto, Kategorie)` gewandert - eine zweite Zeile mit gleichem
    Tripel wird weiterhin abgewiesen."""
    run, photo = await _make_ranked_photo(db_session)

    db_session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            event_id=await event_id_of_run(db_session, run),
            category_key="menschen",
            rank_score=0.1,
            rank_position=2,
            is_primary=False,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_the_same_photo_may_appear_in_a_second_category_of_the_same_run(
    db_session: AsyncSession,
) -> None:
    """Die Kernaussage der Spec 0300 auf Datenmodell-Ebene: ein Foto steht pro Lauf hoechstens
    einmal JE KATEGORIE - aber in mehreren Kategorien."""
    run, photo = await _make_ranked_photo(db_session)

    db_session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            event_id=await event_id_of_run(db_session, run),
            category_key="tier",
            rank_score=0.9,
            rank_position=1,
            is_primary=False,
        )
    )
    await db_session.commit()

    rows = (
        (
            await db_session.execute(
                select(PhotoRanking)
                .where(PhotoRanking.photo_id == photo.id)
                .order_by(PhotoRanking.category_key)
            )
        )
        .scalars()
        .all()
    )
    assert [(row.category_key, row.is_primary) for row in rows] == [
        ("menschen", True),
        ("tier", False),
    ]
    # `rank_score` ist ueber alle Zugehoerigkeitszeilen eines Fotos identisch (ADR 0069 Punkt 4).
    assert {row.rank_score for row in rows} == {0.9}


async def test_photo_ranking_requires_an_explicit_is_primary(db_session: AsyncSession) -> None:
    """Akzeptanzkriterium 25: die Spalte hat weder Python- noch Server-Default - ein Schreibpfad,
    der sie vergisst, faellt auf, statt still eine zweite Hauptkategorie zu erzeugen."""
    run, photo = await _make_ranked_photo(db_session)

    db_session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            event_id=await event_id_of_run(db_session, run),
            category_key="tier",
            rank_score=0.9,
            rank_position=1,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def _make_ranking_graph(db_session: AsyncSession) -> tuple[CriterionScoringRun, Photo]:
    """Ein Kuratierungslauf mit genau einer PhotoRanking-Zeile - der kleinste Aufbau, an dem
    beide Elternseiten (Run und Foto) je einmal geloescht werden koennen."""
    project = Project(name=f"Project {uuid4()}", opencloud_drive_id="d", opencloud_path="/a")
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
            event_id=await event_id_of_run(db_session, run),
            category_key="landscape",
            rank_score=0.9,
            rank_position=1,
            is_primary=True,
        )
    )
    await db_session.commit()
    return run, photo


async def _count_photo_rankings(db_session: AsyncSession) -> int:
    return (await db_session.execute(select(func.count()).select_from(PhotoRanking))).scalar_one()


async def test_deleting_criterion_scoring_run_cascades_to_photo_rankings(
    db_session: AsyncSession,
) -> None:
    """specs/features/0044-projekte-loeschen.md, AK "Voraussetzung (Cascade-Fix)", Run-Seite.

    Assertion bewusst als ZEILENZAEHLUNG und nicht als "es ist keine Ausnahme geflogen": die
    Suite laeuft gegen SQLite OHNE `PRAGMA foreign_keys=ON` (siehe conftest.py), eine fehlende
    Kaskade erzeugt dort keinen IntegrityError, sondern verwaiste Zeilen."""
    run, _photo = await _make_ranking_graph(db_session)
    assert await _count_photo_rankings(db_session) == 1

    await db_session.delete(run)
    await db_session.commit()

    assert await _count_photo_rankings(db_session) == 0


async def test_deleting_photo_cascades_to_photo_rankings(db_session: AsyncSession) -> None:
    """specs/features/0044-projekte-loeschen.md, AK "Voraussetzung (Cascade-Fix)", Foto-Seite.

    Das ist der Re-Scan-Defekt aus worker.py::run_project_scan: verschwindet ein Foto auf
    OpenCloud, loescht der Scan die Photo-Zeile - ohne diese Relationship bleibt ihre
    photo_rankings-Zeile stehen (und scheitert unter echtem Postgres am Fremdschluessel)."""
    _run, photo = await _make_ranking_graph(db_session)
    assert await _count_photo_rankings(db_session) == 1

    await db_session.delete(photo)
    await db_session.commit()

    assert await _count_photo_rankings(db_session) == 0


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

    remaining_detections = (await db_session.execute(select(PhotoFineLabel))).scalars().all()
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

    stored = (await db_session.execute(select(PhotoCategoryClassification))).scalars().one()
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


# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md Punkt 3: je vier additive Kostenspalten an den beiden Run-Tabellen. Alle acht sind
# NULLABLE mit Python-seitigem Default `0` - exakt das `ScanRun.total_files`-Idiom: `NULL` heisst
# "nicht erfasst" (Zeile aus der Zeit vor der Migration), `0` heisst "erfasst, es sind keine
# Kosten angefallen". Ohne diese Unterscheidung waere ein Altlauf nicht mehr von einem
# kostenlosen Lauf zu trennen - und genau darauf beruht der Unvollstaendigkeits-Hinweis der
# Statistikseite (ADR 0051 Punkt 5).

_LANDMARK_COST_COLUMNS = (
    "landmark_api_calls",
    "landmark_input_tokens",
    "landmark_output_tokens",
    "landmark_cost_usd",
)
_REMOTE_CATEGORY_COST_COLUMNS = (
    "api_calls",
    "input_tokens",
    "output_tokens",
    "cost_usd",
)


async def _criterion_scoring_run(db_session: AsyncSession, **kwargs: object) -> CriterionScoringRun:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    db_session.add(scoring_run)
    await db_session.flush()
    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=ScanStatus.RUNNING,
        **kwargs,  # type: ignore[arg-type]
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    return run


async def test_new_criterion_scoring_run_starts_with_zero_landmark_cost_columns(
    db_session: AsyncSession,
) -> None:
    run = await _criterion_scoring_run(db_session)

    for column in _LANDMARK_COST_COLUMNS:
        assert getattr(run, column) == 0, column


async def test_criterion_scoring_run_landmark_cost_columns_stay_nullable(
    db_session: AsyncSession,
) -> None:
    """`NULL` muss fuer alle vier Spalten darstellbar bleiben - genau so sehen die Altlaeufe aus,
    die die Migration zuruecklaesst. Waere die Spalte NOT NULL, waere "nicht erfasst" nicht mehr
    von "kostenlos" unterscheidbar (ADR 0051 Punkt 3/5).

    Der Python-Default `0` greift beim INSERT, deshalb wird der Altzustand hier per UPDATE
    hergestellt - dasselbe Ergebnis wie eine Bestandszeile nach `alembic upgrade`."""
    table = CriterionScoringRun.__table__
    for column in _LANDMARK_COST_COLUMNS:
        assert table.columns[column].nullable, column

    run = await _criterion_scoring_run(db_session)
    for column in _LANDMARK_COST_COLUMNS:
        setattr(run, column, None)
    await db_session.commit()
    await db_session.refresh(run)

    for column in _LANDMARK_COST_COLUMNS:
        assert getattr(run, column) is None, column


async def test_criterion_scoring_run_stores_real_landmark_cost_values(
    db_session: AsyncSession,
) -> None:
    run = await _criterion_scoring_run(
        db_session,
        landmark_api_calls=7,
        landmark_input_tokens=11_130,
        landmark_output_tokens=84,
        landmark_cost_usd=0.01155,
    )

    assert run.landmark_api_calls == 7
    assert run.landmark_input_tokens == 11_130
    assert run.landmark_output_tokens == 84
    assert run.landmark_cost_usd == pytest.approx(0.01155)


async def test_new_remote_category_classification_run_starts_with_zero_cost_columns(
    db_session: AsyncSession,
) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()
    run = RemoteCategoryClassificationRun(project_id=project.id, status=ScanStatus.RUNNING)
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    for column in _REMOTE_CATEGORY_COST_COLUMNS:
        assert getattr(run, column) == 0, column


async def test_remote_category_classification_run_cost_columns_stay_nullable(
    db_session: AsyncSession,
) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()
    run = RemoteCategoryClassificationRun(project_id=project.id, status=ScanStatus.SUCCESS)
    db_session.add(run)
    await db_session.commit()

    table = RemoteCategoryClassificationRun.__table__
    for column in _REMOTE_CATEGORY_COST_COLUMNS:
        assert table.columns[column].nullable, column
        setattr(run, column, None)
    await db_session.commit()
    await db_session.refresh(run)

    for column in _REMOTE_CATEGORY_COST_COLUMNS:
        assert getattr(run, column) is None, column


# --- specs/features/0299-kategorie-konfidenz-anzeigen.md, ADR 0067 Punkt 4 --------------------


async def test_a_classification_row_persists_both_confidence_columns(
    db_session: AsyncSession,
) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoCategoryClassification(
            photo_id=photo.id,
            category_key="menschen",
            detected_categories=["menschen", "landschaft"],
            detected_category_confidences={"menschen": 0.92, "landschaft": 0.41},
            category_confidence=0.92,
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    db_session.expunge_all()

    stored = (await db_session.execute(select(PhotoCategoryClassification))).scalars().one()
    assert stored.detected_category_confidences == {"menschen": 0.92, "landschaft": 0.41}
    assert stored.category_confidence == 0.92


async def test_both_confidence_columns_default_to_none_without_a_backfill(
    db_session: AsyncSession,
) -> None:
    """Akzeptanzkriterium 9: `NULL` heisst "nicht erhoben", `0.0` hiesse "das Modell war sich zu
    0 % sicher". Eine Zeile ohne Angabe muss ohne Zutun `NULL` bleiben - deshalb kein
    Python-Default `{}`/`0.0` und (siehe Migration) kein `server_default`."""
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoCategoryClassification(
            photo_id=photo.id,
            category_key="menschen",
            detected_categories=["menschen"],
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    db_session.expunge_all()

    stored = (await db_session.execute(select(PhotoCategoryClassification))).scalars().one()
    assert stored.detected_category_confidences is None
    assert stored.category_confidence is None


async def test_an_empty_confidence_mapping_is_distinguishable_from_none(
    db_session: AsyncSession,
) -> None:
    """`{}` heisst "erhoben, das Modell hat keine brauchbare Zahl geliefert" - ein anderer Zustand
    als "nicht erhoben"."""
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoCategoryClassification(
            photo_id=photo.id,
            category_key="menschen",
            detected_categories=["menschen"],
            detected_category_confidences={},
            category_confidence=None,
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    db_session.expunge_all()

    stored = (await db_session.execute(select(PhotoCategoryClassification))).scalars().one()
    assert stored.detected_category_confidences == {}
    assert stored.detected_category_confidences is not None
    assert stored.category_confidence is None


def test_classification_phase_lists_the_four_steps_in_execution_order() -> None:
    """specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-
    vier-teilschritte-und-laufeigene-cloud-bilanz.md Punkt 1: die REIHENFOLGE traegt die Aussage,
    nicht nur die Menge - deshalb ein Tupelvergleich statt einer Mengengleichheit. Ein Umsortieren
    (z.B. `landmark` nach `ranking`) liesse die Fortschrittsanzeige rueckwaerts laufen, ohne dass
    eine Mengenpruefung das saehe."""
    assert tuple(phase.value for phase in ClassificationPhase) == (
        "remote_categories",
        "criteria",
        "landmark",
        "ranking",
    )


def test_every_classification_phase_value_fits_the_column_length() -> None:
    """Die Spalte ist ein `VARCHAR(20)` ohne DB-seitige Pruefeinschraenkung (ADR 0068 Punkt 1:
    deshalb braucht ein neuer Enum-Wert KEINE Migration). Genau deshalb ist die Laengengrenze die
    einzige verbliebene Schranke - ein laengerer Wert wuerde unter Postgres beim Schreiben
    abbrechen, waehrend SQLite ihn stillschweigend annaehme."""
    column_length = CriterionScoringRun.__table__.c.phase.type.length
    assert column_length == 20
    assert max(len(phase.value) for phase in ClassificationPhase) <= column_length


# specs/features/0426-zeitversatz-je-kamera.md / decisions/0088 - die projekteigene Kamerazeile
# und die drei neuen photos-Spalten.


async def _project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id="drive-1", opencloud_path=f"/{name}")
    session.add(project)
    await session.flush()
    return project


async def test_a_new_project_camera_starts_without_an_offset(db_session: AsyncSession) -> None:
    """Eine Kamera ohne je gesetzten Wert hat den Versatz `0` - auch eine, die erst bei einem
    spaeteren Scan hinzukommt."""
    project = await _project(db_session)
    camera = ProjectCamera(project_id=project.id, make="Canon", model="EOS 5D")
    db_session.add(camera)
    await db_session.flush()
    await db_session.refresh(camera)

    assert camera.offset_minutes == 0


async def test_the_same_make_and_model_may_not_repeat_within_one_project(
    db_session: AsyncSession,
) -> None:
    project = await _project(db_session)
    db_session.add(ProjectCamera(project_id=project.id, make="Canon", model="EOS 5D"))
    await db_session.flush()
    db_session.add(ProjectCamera(project_id=project.id, make="Canon", model="EOS 5D"))

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_the_same_camera_may_exist_once_per_project(db_session: AsyncSession) -> None:
    """Der Kern von ADR 0088, Punkt 2: dieselbe Kamera in zwei Projekten sind ZWEI Zeilen mit
    getrennten Versaetzen - "der Versatz gilt nur in diesem Projekt" ist damit strukturell wahr."""
    first = await _project(db_session, "Costa Rica")
    second = await _project(db_session, "Norwegen")
    db_session.add_all(
        [
            ProjectCamera(project_id=first.id, make="Canon", model="EOS 5D", offset_minutes=-120),
            ProjectCamera(project_id=second.id, make="Canon", model="EOS 5D"),
        ]
    )
    await db_session.flush()

    offsets = (
        await db_session.execute(
            select(ProjectCamera.project_id, ProjectCamera.offset_minutes).order_by(
                ProjectCamera.project_id
            )
        )
    ).all()

    assert offsets == [(first.id, -120), (second.id, 0)]


async def test_deleting_a_project_cascades_to_its_cameras(db_session: AsyncSession) -> None:
    project = await _project(db_session)
    db_session.add(ProjectCamera(project_id=project.id, make="Canon", model="EOS 5D"))
    await db_session.flush()

    await db_session.delete(project)
    await db_session.flush()

    assert (
        await db_session.execute(select(func.count()).select_from(ProjectCamera.__table__))
    ).scalar_one() == 0


async def test_a_photo_without_a_camera_is_a_regular_state(db_session: AsyncSession) -> None:
    """`camera_id IS NULL` heisst "Kamera nicht bestimmbar" und ist kein Fehler; `camera_probed`
    faellt ohne Angabe auf `False`."""
    project = await _project(db_session)
    now = datetime.now(UTC).replace(tzinfo=None)
    photo = Photo(
        project_id=project.id,
        relative_path="img001.jpg",
        etag="etag-1",
        content_length=100,
        taken_at=now,
        taken_at_original=now,
        last_modified=now,
    )
    db_session.add(photo)
    await db_session.flush()
    await db_session.refresh(photo)

    assert photo.camera_id is None
    assert photo.camera_probed is False


async def test_the_probed_marker_carries_the_same_server_default_as_the_migration(
    db_session: AsyncSession,
) -> None:
    """Die MODELLSEITE des `server_default` - die Migrationsseite steht im Postgres-Renderpfad
    (`test_postgres_ddl_compatibility.py`). Zwei Artefakte, zwei Assertions: fehlt diese hier,
    bleibt alles gruen und der erste Schreibpfad, der die Spalte nicht nennt, bricht produktiv.

    Geprueft wird gegen das aus `Base.metadata` erzeugte Schema, also mit einem `INSERT`, der die
    Spalte ausdruecklich NICHT nennt."""
    assert Photo.__table__.c.camera_probed.server_default is not None

    project = await _project(db_session)
    now = datetime.now(UTC).replace(tzinfo=None)
    await db_session.execute(
        Photo.__table__.insert().values(
            project_id=project.id,
            relative_path="img001.jpg",
            etag="etag-1",
            content_length=100,
            taken_at=now,
            taken_at_original=now,
            last_modified=now,
        )
    )

    probed = (
        await db_session.execute(select(Photo.camera_probed).where(Photo.project_id == project.id))
    ).scalar_one()

    assert probed is False


async def test_the_recorded_time_has_no_default_and_must_be_written_explicitly(
    db_session: AsyncSession,
) -> None:
    """`taken_at_original` ist die EINZIGE Kopie der aufgezeichneten Zeit, und ein unveraendertes
    Foto wird nie wieder aus EXIF gelesen. Ein Schreibpfad, der die Spalte vergisst, muss deshalb
    LAUT an der NOT-NULL-Bedingung scheitern statt still einen falschen Wert zu erben - genau
    dafuer traegt sie weder Python- noch server-seitig einen Default."""
    assert Photo.__table__.c.taken_at_original.server_default is None
    assert not Photo.__table__.c.taken_at_original.nullable

    project = await _project(db_session)
    now = datetime.now(UTC).replace(tzinfo=None)

    with pytest.raises(IntegrityError):
        await db_session.execute(
            Photo.__table__.insert().values(
                project_id=project.id,
                relative_path="img001.jpg",
                etag="etag-1",
                content_length=100,
                taken_at=now,
                last_modified=now,
            )
        )


_TAKEN_AT_ASSIGNMENT = re.compile(r"\.taken_at\s*=(?!=)")

# Die beiden - und nur die beiden - Schreibstellen auf `Photo.taken_at` (ADR 0088, Punkt 1).
_ALLOWED_TAKEN_AT_WRITERS = frozenset({"worker.py", "api/cameras.py"})


def test_no_module_beyond_the_two_known_ones_assigns_to_taken_at() -> None:
    """STRUKTURELLER Waechter, kein Verhaltenstest: Die Invariante
    `taken_at == taken_at_original + offset_minutes` haengt daran, dass es GENAU ZWEI
    Schreibstellen gibt, beide ueber `cameras.py::shifted`. Eine dritte Schreibstelle roetet
    KEINEN Verhaltenstest, solange sie den Wert irgendwie setzt - sie faellt nur hier auf.

    Gezaehlt werden ATTRIBUTZUWEISUNGEN (`irgendwas.taken_at = ...`), nicht die
    Konstruktor-Schluesselwoerter `Photo(taken_at=...)`: eine neu angelegte Zeile setzt beide
    Zeitwerte gemeinsam, das Verschieben einer BESTEHENDEN Zeile ist die gefaehrliche Handlung.

    Die zweite Assertion ist der Selbstschutz: findet das Suchmuster gar nichts mehr (umbenannte
    Spalte, andere Schreibweise), bestuende der Waechter leer und pruefte nichts."""
    source_root = Path(photosort.__file__).resolve().parent
    writers = {
        str(path.relative_to(source_root))
        for path in source_root.rglob("*.py")
        if _TAKEN_AT_ASSIGNMENT.search(path.read_text(encoding="utf-8"))
    }

    assert writers <= set(_ALLOWED_TAKEN_AT_WRITERS), (
        "Diese Module weisen Photo.taken_at zu, obwohl es nur zwei Schreibstellen geben darf "
        f"({sorted(_ALLOWED_TAKEN_AT_WRITERS)}): "
        f"{sorted(writers - set(_ALLOWED_TAKEN_AT_WRITERS))}"
    )
    assert writers, (
        "Der Waechter findet keine einzige Zuweisung an `taken_at` mehr - das Suchmuster passt "
        "nicht mehr zum Code, und der Waechter prueft nichts."
    )
