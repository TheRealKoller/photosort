import ast
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
    Event,
    FinalSelectionDecision,
    FineLabel,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoFineLabel,
    PhotoLandmarkDetection,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    PhotoRanking,
    PhotoScore,
    PlaceLookup,
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
from tests.event_rows import event_id_of_run, event_of_run


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

    rating = Rating(photo_id=photo.id, user_id=user.id, status=RatingStatus.ALBUM_WORTHY)
    db_session.add(rating)
    await db_session.commit()

    result = await db_session.execute(select(Rating).where(Rating.photo_id == photo.id))
    stored = result.scalar_one()
    assert stored.status == RatingStatus.ALBUM_WORTHY
    # Zwei unabhaengige Angaben: die Albumentscheidung sagt nichts ueber das Kennzeichen, und
    # ohne gesetzten Wert ist es `False` - nie `None` in einer nicht-nullbaren Spalte.
    assert stored.favorite is False
    assert stored.updated_at is not None


async def test_create_rating_with_only_the_favorite_marker(db_session: AsyncSession) -> None:
    """`status IS NULL` heisst "keine Albumentscheidung" und ist ein gueltiger Zustand, sobald
    das Kennzeichen die Zeile traegt."""
    photo, user = await _make_photo_and_user(db_session)

    db_session.add(Rating(photo_id=photo.id, user_id=user.id, favorite=True))
    await db_session.commit()

    stored = (
        await db_session.execute(select(Rating).where(Rating.photo_id == photo.id))
    ).scalar_one()
    assert stored.status is None
    assert stored.favorite is True


async def test_rating_unique_per_photo_and_user(db_session: AsyncSession) -> None:
    photo, user = await _make_photo_and_user(db_session)

    db_session.add(Rating(photo_id=photo.id, user_id=user.id, status=RatingStatus.ALBUM_WORTHY))
    await db_session.commit()

    db_session.add(Rating(photo_id=photo.id, user_id=user.id, status=RatingStatus.REJECTED))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_deleting_photo_cascades_to_ratings(db_session: AsyncSession) -> None:
    photo, user = await _make_photo_and_user(db_session)
    db_session.add(Rating(photo_id=photo.id, user_id=user.id, status=RatingStatus.ALBUM_WORTHY))
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
    assert stored.rank_position == 1


async def _make_ranked_photo(
    db_session: AsyncSession,
) -> tuple[CriterionScoringRun, Photo]:
    """Ein Lauf mit einem Foto und dessen EINER Rangzeile."""
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
            rank_score=0.9,
            rank_position=1,
        )
    )
    await db_session.commit()
    return run, photo


async def test_photo_ranking_unique_per_run_and_photo(db_session: AsyncSession) -> None:
    """specs/features/0427-motive-mit-staerke.md, PR 3: der Constraint ist von
    `(Lauf, Foto, Kategorie)` zurueck auf `(Lauf, Foto)` gewandert - ein Foto steht pro Lauf in
    GENAU EINER Zeile, und eine zweite wird von der Datenbank abgewiesen.

    Das ist die Datenmodell-Haelfte der Aussage "die Partition ist allein das Event": ohne den
    Constraint koennte ein Schreibpfad wieder mehrere Zeilen je Foto anlegen, und `PhotoOut.ranking`
    (ein Feld, keine Liste) zeigte stillschweigend eine beliebige davon."""
    run, photo = await _make_ranked_photo(db_session)

    db_session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            event_id=await event_id_of_run(db_session, run),
            rank_score=0.1,
            rank_position=2,
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
            rank_score=0.9,
            rank_position=1,
        )
    )
    await db_session.commit()
    return run, photo


async def _count_photo_rankings(db_session: AsyncSession) -> int:
    return (await db_session.execute(select(func.count()).select_from(PhotoRanking))).scalar_one()


async def _count_events(db_session: AsyncSession) -> int:
    return (await db_session.execute(select(func.count()).select_from(Event))).scalar_one()


async def test_deleting_criterion_scoring_run_cascades_to_photo_rankings(
    db_session: AsyncSession,
) -> None:
    """specs/features/0044-projekte-loeschen.md, AK "Voraussetzung (Cascade-Fix)", Run-Seite.

    Assertion bewusst als ZEILENZAEHLUNG und nicht als "es ist keine Ausnahme geflogen": die
    Zeilenzahl nennt auch die verwaiste Zeile, die ein fehlender Fremdschluessel selbst mit
    gesetztem `PRAGMA foreign_keys=ON` nicht meldet."""
    run, _photo = await _make_ranking_graph(db_session)
    assert await _count_photo_rankings(db_session) == 1

    await db_session.delete(run)
    await db_session.commit()

    assert await _count_photo_rankings(db_session) == 0


async def test_deleting_criterion_scoring_run_cascades_to_events(
    db_session: AsyncSession,
) -> None:
    """Das Event ist der dritte Elternteil von `PhotoRanking` (`photo_rankings.event_id`).

    SQLAlchemy leitet die Loeschreihenfolge von Tabellen aus RELATIONSHIPS ab, nicht aus
    Fremdschluesseln: ohne `CriterionScoringRun.events` bliebe die Event-Zeile nach dem Loeschen
    des Laufs stehen (und der Flush liefe mit gesetztem Pragma in eine Fremdschluesselverletzung)."""
    run, _photo = await _make_ranking_graph(db_session)
    assert await _count_events(db_session) == 1

    await db_session.delete(run)
    await db_session.commit()

    assert await _count_events(db_session) == 0


async def test_deleting_event_cascades_to_photo_rankings(db_session: AsyncSession) -> None:
    """Die zweite Kante derselben Kaskade: `Event.rankings` muss die Rangzeilen mitnehmen, sonst
    blieben sie als verwaiste Zeilen stehen."""
    run, _photo = await _make_ranking_graph(db_session)
    event = await event_of_run(db_session, run)
    assert await _count_photo_rankings(db_session) == 1

    await db_session.delete(event)
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


# specs/features/0426-zeitversatz-je-kamera.md / decisions/0090 - die projekteigene Kamerazeile
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
    """Der Kern von ADR 0090, Punkt 2: dieselbe Kamera in zwei Projekten sind ZWEI Zeilen mit
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


# Die beiden - und nur die beiden - Schreibstellen auf `Photo.taken_at` (ADR 0090, Punkt 1).
_ALLOWED_TAKEN_AT_WRITERS = frozenset({"worker.py", "api/cameras.py"})

_TAKEN_AT = "taken_at"


def _writes_taken_at(source: str) -> bool:
    """Ob dieses Modul `taken_at` einer BESTEHENDEN Zeile schreibt - ueber den Syntaxbaum, nicht
    ueber ein Suchmuster.

    DREI Schreibformen, weil die beiden erlaubten Stellen zwei VERSCHIEDENE benutzen und die
    dritte im Projekt naheliegt:

    1. Attributzuweisung `photo.taken_at = ...` (`worker.py::_process_scan_block`).
    2. `taken_at` als Schluessel eines Dict-Literals - die Form des gebuendelten Bulk-Updates
       `session.execute(update(Photo), [{"id": ..., "taken_at": ...}])` (`api/cameras.py`).
    3. `taken_at` als Schluesselwort eines `.values(...)`-Aufrufs - die dritte im Projekt
       naheliegende Form fuer ein Massenupdate, heute an keiner Stelle verwendet.

    AUSDRUECKLICH NICHT gezaehlt wird das Konstruktor-Schluesselwort `Photo(taken_at=...)`: eine
    neu angelegte Zeile setzt beide Zeitwerte gemeinsam, und `taken_at_original` ist NOT NULL ohne
    Default - ein Anlegen ohne beide Werte scheitert laut. Die gefaehrliche Handlung ist das
    VERSCHIEBEN einer bestehenden Zeile.

    BEKANNTE GRENZE: Ein dynamisch gebauter Spaltenname (`{spalte: wert}` mit `spalte` als
    Variable) ist statisch nicht erkennbar. Dagegen steht `assert_time_offset_invariant` in den
    Verhaltenstests, nicht dieser Waechter."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign | ast.AugAssign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr == _TAKEN_AT:
                    return True
        elif isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value == _TAKEN_AT:
                    return True
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "values" and any(
                keyword.arg == _TAKEN_AT for keyword in node.keywords
            ):
                return True
    return False


def test_exactly_the_two_known_modules_write_taken_at() -> None:
    """STRUKTURELLER Waechter, kein Verhaltenstest: Die Invariante
    `taken_at == taken_at_original + offset_minutes` haengt daran, dass es GENAU ZWEI
    Schreibstellen gibt, beide ueber `cameras.py::shifted`. Eine dritte Schreibstelle roetet
    KEINEN Verhaltenstest, solange sie den Wert irgendwie setzt - sie faellt nur hier auf, und
    `assert_time_offset_invariant` laeuft nur in Faellen, die eine neue Stelle nicht kennen.

    Geprueft wird GLEICHHEIT, nicht Teilmenge, und das ist der Kern des Selbstschutzes: Findet der
    Waechter eine der erlaubten Stellen NICHT mehr, prueft er fuer sie nichts - genau so blieb er
    zuvor gruen, obwohl er die Bulk-Update-Form von `api/cameras.py` gar nicht sah. Wer eine
    Schreibstelle absichtlich entfernt, zieht die Liste bewusst nach."""
    source_root = Path(photosort.__file__).resolve().parent
    writers = {
        str(path.relative_to(source_root))
        for path in source_root.rglob("*.py")
        if _writes_taken_at(path.read_text(encoding="utf-8"))
    }

    assert writers == set(_ALLOWED_TAKEN_AT_WRITERS), (
        "Die Menge der Module, die `Photo.taken_at` schreiben, weicht von den genau zwei "
        f"erlaubten ab ({sorted(_ALLOWED_TAKEN_AT_WRITERS)}). Zu viel: "
        f"{sorted(writers - set(_ALLOWED_TAKEN_AT_WRITERS))}; nicht mehr gefunden: "
        f"{sorted(set(_ALLOWED_TAKEN_AT_WRITERS) - writers)}"
    )


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param("photo.taken_at = corrected", id="attributzuweisung"),
        pytest.param('rows.append({"id": 1, "taken_at": corrected})', id="dict-schluessel"),
        pytest.param(
            "session.execute(update(Photo).values(taken_at=corrected))", id="values-aufruf"
        ),
    ],
)
def test_the_guard_sees_every_write_form_it_claims_to_cover(snippet: str) -> None:
    """Selbstschutz zum Selbstschutz: Der Waechter oben ist nur so gut wie die Formen, die er
    tatsaechlich erkennt - und genau daran ist er zuvor gescheitert. Jede der drei Formen wird
    hier einzeln nachgewiesen, statt sich darauf zu verlassen, dass der Bestand sie alle
    enthaelt (er enthaelt die `values()`-Form nicht)."""
    assert _writes_taken_at(snippet)


def test_the_guard_ignores_a_constructor_keyword() -> None:
    """Die Gegenprobe zur Abgrenzung: ein ANLEGEN ist keine Schreibstelle im Sinne der
    Invariante - sonst waere `demo_state.py` ein Befund, obwohl es beide Zeitwerte gemeinsam
    setzt."""
    assert not _writes_taken_at("photo = Photo(taken_at=now, taken_at_original=now)")


def test_the_guard_ignores_reading_the_column() -> None:
    """Zweite Gegenprobe: das LESEN der Spalte (Sortierung, Auswahl, Vergleich) ist der
    Regelfall und darf nie als Schreibstelle zaehlen."""
    assert not _writes_taken_at("select(Photo.id).order_by(Photo.taken_at)")
    assert not _writes_taken_at("if photo.taken_at == other.taken_at_original: pass")


# specs/features/0429-auswahl-richtwert-und-mischung.md: die EINE Schreibstelle auf
# `PhotoRanking.selection_position`.
_ALLOWED_SELECTION_POSITION_WRITERS = frozenset({"worker.py"})

_SELECTION_POSITION = "selection_position"


def _writes_selection_position(source: str) -> bool:
    """Ob dieses Modul `selection_position` setzt - ueber den Syntaxbaum, nicht ueber ein
    Suchmuster.

    VIER Schreibformen, eine mehr als beim `taken_at`-Waechter: Attributzuweisung, Dict-Schluessel,
    `.values(...)`-Schluesselwort und das KONSTRUKTOR-Schluesselwort `PhotoRanking(
    selection_position=…)`.

    Die vierte Form ist hier eine BEWUSSTE Abweichung. Beim `taken_at`-Waechter zaehlt das
    Anlegen einer Zeile ausdruecklich nicht, weil es harmlos ist; hier ist es die gefaehrliche
    Handlung. `demo_state.py` legt `PhotoRanking`-Zeilen selbst an, und ein dort gesetzter Platz
    waere eine ZWEITE Vergaberegel neben dem Verfahren - mit demselben Ergebnis-Aussehen und ohne
    roten Test."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign | ast.AugAssign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr == _SELECTION_POSITION:
                    return True
        elif isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value == _SELECTION_POSITION:
                    return True
        elif isinstance(node, ast.Call):
            if any(keyword.arg == _SELECTION_POSITION for keyword in node.keywords):
                return True
    return False


def test_exactly_the_one_known_module_writes_selection_position() -> None:
    """STRUKTURELLER Waechter: Der Auswahlvorschlag entsteht an GENAU EINER Stelle. Eine zweite
    Vergaberegel roetet keinen Verhaltenstest - sie liefert eine andere, plausibel aussehende
    Auswahl, und genau das ist die Fehlerklasse dieses Verfahrens.

    Geprueft wird GLEICHHEIT, nicht Teilmenge: findet der Waechter die erlaubte Stelle nicht mehr,
    prueft er fuer sie nichts."""
    source_root = Path(photosort.__file__).resolve().parent
    writers = {
        str(path.relative_to(source_root))
        for path in source_root.rglob("*.py")
        if _writes_selection_position(path.read_text(encoding="utf-8"))
    }

    assert writers == set(_ALLOWED_SELECTION_POSITION_WRITERS), (
        "Die Menge der Module, die `PhotoRanking.selection_position` schreiben, weicht von der "
        f"genau einen erlaubten ab ({sorted(_ALLOWED_SELECTION_POSITION_WRITERS)}). Zu viel: "
        f"{sorted(writers - set(_ALLOWED_SELECTION_POSITION_WRITERS))}; nicht mehr gefunden: "
        f"{sorted(set(_ALLOWED_SELECTION_POSITION_WRITERS) - writers)}"
    )


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param("row.selection_position = place", id="attributzuweisung"),
        pytest.param('rows.append({"id": 1, "selection_position": 2})', id="dict-schluessel"),
        pytest.param(
            "session.execute(update(PhotoRanking).values(selection_position=place))",
            id="values-aufruf",
        ),
        pytest.param(
            "session.add(PhotoRanking(photo_id=1, selection_position=2))",
            id="konstruktor-schluesselwort",
        ),
    ],
)
def test_the_selection_guard_sees_every_write_form_it_claims_to_cover(snippet: str) -> None:
    """Der Waechter ist nur so gut wie die Formen, die er tatsaechlich erkennt - jede der vier
    wird hier einzeln nachgewiesen, statt sich darauf zu verlassen, dass der Bestand sie alle
    enthaelt."""
    assert _writes_selection_position(snippet)


def test_the_selection_guard_ignores_reading_and_comparing() -> None:
    """Zwei Gegenproben: Lesen und Vergleichen zaehlen nie. Ohne sie waere jeder Lesepfad
    (api/photos.py) ein Befund."""
    assert not _writes_selection_position(
        "select(PhotoRanking.photo_id).order_by(PhotoRanking.selection_position)"
    )
    assert not _writes_selection_position("if ranking.selection_position is not None: pass")


def test_the_selection_guard_finds_nothing_in_a_module_without_the_column() -> None:
    """Positiv-Gegenprobe gegen die LEERE Fundmenge: ein Waechter, der nie etwas findet, bestuende
    jede Zusage."""
    assert not _writes_selection_position("x = 1\ndef f(a): return a\n")


# specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 2: die drei Motiv-Tabellen. Vier
# Aussagen brechen ohne eigenen Fall stillschweigend - die Lauf-Unabhaengigkeit der Korrektur, das
# fehlende Default am Ausschluss-Flag, die Richtung des Staerke-Fremdschluessels und die beiden
# Kaskaden am Foto.


async def _make_assessed_photo(
    db_session: AsyncSession, *, strength: float = 0.9
) -> tuple[Photo, User]:
    photo, user = await _make_photo_and_user(db_session)
    db_session.add(
        PhotoMotifAssessment(
            photo_id=photo.id,
            source=MotifAssessmentSource.CLOUD,
            excluded_document=False,
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    db_session.add(PhotoMotifStrength(photo_id=photo.id, motif_key="menschen", strength=strength))
    await db_session.flush()
    return photo, user


async def test_create_photo_motif_assessment(db_session: AsyncSession) -> None:
    photo, _user = await _make_assessed_photo(db_session)
    await db_session.commit()

    stored = (
        await db_session.execute(
            select(PhotoMotifAssessment).where(PhotoMotifAssessment.photo_id == photo.id)
        )
    ).scalar_one()

    assert stored.source == MotifAssessmentSource.CLOUD
    assert stored.provider == "anthropic"
    assert stored.excluded_document is False


async def test_photo_motif_assessment_is_one_to_one_with_photo(db_session: AsyncSession) -> None:
    photo, _user = await _make_assessed_photo(db_session)
    await db_session.commit()

    db_session.add(
        PhotoMotifAssessment(
            photo_id=photo.id,
            source=MotifAssessmentSource.LOCAL,
            excluded_document=False,
            computed_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_photo_motif_assessment_requires_an_explicit_exclusion_flag(
    db_session: AsyncSession,
) -> None:
    """`excluded_document` ist NOT NULL und traegt bewusst KEINEN Default: ein Schreibpfad, der
    die Spalte vergisst, soll laut scheitern statt still ein Foto aus JEDER Motivauswahl zu
    nehmen - und von Hand ist der Ausschluss nicht korrigierbar."""
    photo = await _make_photo(db_session)

    db_session.add(
        PhotoMotifAssessment(
            photo_id=photo.id,
            source=MotifAssessmentSource.CLOUD,
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


def test_the_exclusion_flag_carries_neither_a_python_nor_a_server_default() -> None:
    """Die Gegenprobe zur Verhaltensprobe oben, und die eigentliche Zusage: ein spaeter
    ergaenztes `default=False` machte den Fall oben gruen, ohne dass etwas anderes brach - und
    jeder Schreibpfad, der die Spalte vergisst, schloesse das Foto dann still aus."""
    column = PhotoMotifAssessment.__table__.c.excluded_document

    assert column.nullable is False
    assert column.default is None
    assert column.server_default is None


async def test_deleting_photo_cascades_to_motif_assessment_and_strengths(
    db_session: AsyncSession,
) -> None:
    photo, _user = await _make_assessed_photo(db_session)
    await db_session.commit()

    await db_session.delete(photo)
    await db_session.commit()

    assert (await db_session.execute(select(PhotoMotifAssessment))).scalars().all() == []
    assert (await db_session.execute(select(PhotoMotifStrength))).scalars().all() == []


async def test_photo_motif_strength_unique_per_photo_and_motif_key(
    db_session: AsyncSession,
) -> None:
    photo, _user = await _make_assessed_photo(db_session)
    await db_session.commit()

    db_session.add(PhotoMotifStrength(photo_id=photo.id, motif_key="menschen", strength=0.1))
    with pytest.raises(IntegrityError):
        await db_session.commit()


def test_a_motif_strength_hangs_on_the_assessment_and_not_on_the_photo() -> None:
    """Eine Staerke kann ohne Kopfzeile nicht existieren - der Fremdschluessel zeigt deshalb auf
    `photo_motif_assessments.photo_id` und NICHT auf `photos.id`. Auch mit durchgesetztem
    `PRAGMA foreign_keys=ON` (Spec 0350) faellt sie nur dort auf, wo der eingetragene Wert
    zufaellig kein Foto trifft - die Richtung selbst ist eine Strukturaussage und wird deshalb
    am Fremdschluessel gelesen."""
    targets = {
        foreign_key.column.table.name for foreign_key in PhotoMotifStrength.__table__.foreign_keys
    }

    assert targets == {"photo_motif_assessments"}


async def test_create_photo_motif_correction(db_session: AsyncSession) -> None:
    photo, user = await _make_assessed_photo(db_session)

    db_session.add(
        PhotoMotifCorrection(
            photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=False
        )
    )
    await db_session.commit()

    stored = (await db_session.execute(select(PhotoMotifCorrection))).scalar_one()

    assert stored.applies is False
    assert stored.user_id == user.id
    assert stored.updated_at is not None


async def test_photo_motif_correction_unique_per_photo_and_motif_key_without_the_user(
    db_session: AsyncSession,
) -> None:
    """Der Unique-Constraint lautet `(photo_id, motif_key)` OHNE `user_id`: die Korrektur ist eine
    Aussage ueber das FOTO. Mit `user_id` im Constraint entstuenden zwei widersprueckliche Zeilen
    fuer dasselbe Paar, und welche gilt, entschiede die Sortierung."""
    photo, user = await _make_assessed_photo(db_session)
    other = User(username="partnerin", password_hash="hashed-value")
    db_session.add(other)
    await db_session.flush()
    db_session.add(
        PhotoMotifCorrection(photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=True)
    )
    await db_session.commit()

    db_session.add(
        PhotoMotifCorrection(
            photo_id=photo.id, user_id=other.id, motif_key="menschen", applies=False
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


def test_a_motif_correction_references_no_run_at_all() -> None:
    """Maschinell statt als Behauptung: die Korrektur haengt AUSSCHLIESSLICH an `photos` und
    `users`. Ein Fremdschluessel auf einen Lauf machte sie zu einem Lauf-Artefakt, und sie ginge
    beim naechsten Klassifizierungslauf verloren - die Feedback-Story haette dann kein Signal."""
    targets = {
        foreign_key.column.table.name for foreign_key in PhotoMotifCorrection.__table__.foreign_keys
    }

    assert targets == {"photos", "users"}


async def test_deleting_photo_cascades_to_motif_corrections_but_keeps_the_user(
    db_session: AsyncSession,
) -> None:
    photo, user = await _make_assessed_photo(db_session)
    db_session.add(
        PhotoMotifCorrection(photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=True)
    )
    await db_session.commit()

    await db_session.delete(photo)
    await db_session.commit()

    assert (await db_session.execute(select(PhotoMotifCorrection))).scalars().all() == []
    assert (await db_session.execute(select(User))).scalars().all() != []


async def test_a_classification_run_does_not_remove_a_correction(db_session: AsyncSession) -> None:
    """Das `cascade` haengt am FOTO, nicht an der Kopfzeile: verschwindet die Kopfzeile (neue
    Grundlage), bleibt die Korrektur."""
    photo, user = await _make_assessed_photo(db_session)
    db_session.add(
        PhotoMotifCorrection(photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=True)
    )
    await db_session.commit()

    assessment = await db_session.get(PhotoMotifAssessment, photo.id)
    assert assessment is not None
    await db_session.delete(assessment)
    await db_session.commit()

    assert len((await db_session.execute(select(PhotoMotifCorrection))).scalars().all()) == 1


def test_both_motif_unique_constraints_carry_an_explicit_name() -> None:
    """Ohne expliziten Namen ist der Constraint unter Postgres nicht droppbar, und
    `Base.metadata` traegt keine `naming_convention`, aus der einer entstuende."""
    strength_names = {
        constraint.name
        for constraint in PhotoMotifStrength.__table__.constraints
        if constraint.name is not None and constraint.name.startswith("uq_")
    }
    correction_names = {
        constraint.name
        for constraint in PhotoMotifCorrection.__table__.constraints
        if constraint.name is not None and constraint.name.startswith("uq_")
    }

    assert strength_names == {"uq_motif_strength_photo_key"}
    assert correction_names == {"uq_motif_correction_photo_key"}


# specs/features/0428-albumtauglichkeit-vom-modell.md ab hier: die Albumtauglichkeit haengt an
# `photos` und nicht an der Motiv-Kopfzeile (ADR 0095, Abschnitt 6), und `photo_rankings` traegt
# ab hier `NULL` fuer ein Foto ohne Modellurteil.


async def test_create_photo_album_suitability(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoAlbumSuitability(
            photo_id=photo.id,
            level=4,
            reason="Alle schauen in die Kamera.",
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    stored = (
        await db_session.execute(
            select(PhotoAlbumSuitability).where(PhotoAlbumSuitability.photo_id == photo.id)
        )
    ).scalar_one()
    assert stored.level == 4
    assert stored.reason == "Alle schauen in die Kamera."
    assert stored.provider == "anthropic"


async def test_photo_album_suitability_is_one_to_one_with_photo(db_session: AsyncSession) -> None:
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoAlbumSuitability(
            photo_id=photo.id,
            level=3,
            reason=None,
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    db_session.add(
        PhotoAlbumSuitability(
            photo_id=photo.id,
            level=5,
            reason=None,
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_photo_album_suitability_reason_may_be_absent(db_session: AsyncSession) -> None:
    """Ohne brauchbare Begruendung steht dort `NULL`, nie eine leere Zeichenkette."""
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoAlbumSuitability(
            photo_id=photo.id, level=2, provider="anthropic", computed_at=datetime.now(UTC)
        )
    )
    await db_session.commit()

    stored = await db_session.get(PhotoAlbumSuitability, photo.id)
    assert stored is not None
    assert stored.reason is None


async def test_deleting_photo_cascades_to_album_suitability(db_session: AsyncSession) -> None:
    """Sonst ueberleben Aussagen ueber die Bildguete geloeschter Familienfotos ihr Foto (S13)."""
    photo = await _make_photo(db_session)
    db_session.add(
        PhotoAlbumSuitability(
            photo_id=photo.id, level=2, provider="anthropic", computed_at=datetime.now(UTC)
        )
    )
    await db_session.commit()

    await db_session.delete(photo)
    await db_session.commit()

    assert (await db_session.execute(select(PhotoAlbumSuitability))).scalars().all() == []


async def test_a_photo_ranking_without_a_model_verdict_carries_null_but_keeps_its_event(
    db_session: AsyncSession,
) -> None:
    """`NULL` heisst "kein Qualitaetswert, weil keine Modellbewertung". Die Gliederung nach Events
    ist dagegen KEINE Cloud-Leistung: `event_id` bleibt gesetzt, das Foto bleibt im einsehbaren
    Vorrat."""
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
    event_id = await event_id_of_run(db_session, run)

    db_session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            event_id=event_id,
            rank_score=None,
            rank_position=None,
        )
    )
    await db_session.commit()

    stored = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalar_one()
    assert stored.rank_score is None
    assert stored.rank_position is None
    assert stored.event_id == event_id


def test_the_criterion_value_column_stays_not_null() -> None:
    """Ein nicht messbares Kriterium wird GELOESCHT, nicht auf `NULL` gesetzt - sonst traegt die
    Spalte zwei verschiedene Aussagen ("nicht messbar" und "Wert unbekannt"), und jeder Leser
    braeuchte einen Sonderzweig dafuer."""
    assert PhotoCriterionScore.__table__.columns["value"].nullable is False


def test_the_two_ranking_columns_are_nullable_but_the_event_is_not() -> None:
    columns = PhotoRanking.__table__.columns

    assert columns["rank_score"].nullable is True
    assert columns["rank_position"].nullable is True
    assert columns["event_id"].nullable is False


class TestTheSingleDraftStaysUntouchedByTheFinalSelection:
    """specs/features/0431-endauswahl-gemeinsam.md, Nachweisstellen 1 und 2 von sieben.

    Die Endauswahl ist eine Ebene UEBER beiden Entwuerfen, nicht daneben. Story 6 sagt fuer den
    Einzelentwurf zu, dass neben der Bewertung keine zweite, daneben liegende Auswahlebene
    entsteht - beide Faelle hier pruefen GLEICHHEIT der Spaltenmenge bzw. des Wertevorrats, nicht
    Teilmenge: Eine spaeter ergaenzte Spalte oder ein spaeter ergaenzter Enum-Wert waere genau die
    zweite Ebene und roetet sonst nichts."""

    def test_the_rating_table_gains_no_column(self) -> None:
        assert set(Rating.__table__.columns.keys()) == {
            "id",
            "photo_id",
            "user_id",
            "status",
            "favorite",
            "updated_at",
        }

    def test_the_rating_status_vocabulary_stays_the_album_decision(self) -> None:
        assert {status.value for status in RatingStatus} == {"album_worthy", "rejected"}

    def test_the_decision_table_carries_no_user_reference(self) -> None:
        """ADR 0099 Punkt 3: Es gibt keine Spalte, in der ein Nutzerbezug stehen koennte - weder
        `user_id` noch `decided_by` noch eine Lauf-Bindung. Die Trennung ist strukturell."""
        assert set(FinalSelectionDecision.__table__.columns.keys()) == {
            "photo_id",
            "included",
            "updated_at",
        }

    def test_the_decision_table_has_exactly_one_foreign_key_and_it_points_at_photos(self) -> None:
        foreign_keys = {
            (key.parent.name, key.column.table.name)
            for key in FinalSelectionDecision.__table__.foreign_keys
        }

        assert foreign_keys == {("photo_id", "photos")}

    def test_the_included_column_is_not_null_and_carries_no_default(self) -> None:
        """Die Abwesenheit der Zeile heisst "unentschieden" (Auflage S4). Ein Vorgabewert erfaende
        eine Entscheidung, die niemand getroffen hat - und es gibt keinen Weg zurueck."""
        column = FinalSelectionDecision.__table__.columns["included"]

        assert column.nullable is False
        assert column.default is None
        assert column.server_default is None


# specs/features/0431-endauswahl-gemeinsam.md, Nachweisstelle 3 von sieben: Die Funktionen des
# EINZELENTWURFS nennen die gemeinsame Entscheidung nicht.
#
# DIE EINHEIT IST DER FUNKTIONSRUMPF, NICHT DIE DATEI, und das ist keine Feinheit: `_to_photo_out`
# und `album_selection` liegen im selben Modul wie `_draft_photo_ids` und `draft_alternatives`, und
# die drei Endauswahl-Felder stehen auf ALLEN Lesepfaden - ein Waechter auf Dateiebene waere
# deshalb entweder dauerhaft rot oder so weit gefasst, dass er nichts zusichert.
#
# Gemessen wird ausschliesslich der MODELLNAME, nicht der Lader `_final_selection_decisions`:
# `draft_alternatives` und `list_photos` MUESSEN ihn aufrufen, weil die Felder auch dort stehen.
# Was ihnen untersagt ist, ist der direkte Zugriff auf die Tabelle - der waere der Anfang einer
# zweiten Auswahlebene IM Einzelentwurf.
_DECISION_MODEL = "FinalSelectionDecision"

# Jede Stelle, die den Modellnamen nennen DARF - je Eintrag `<pfad>::<funktion>`. Geprueft wird
# GLEICHHEIT: Findet der Waechter eine erlaubte Stelle nicht mehr, prueft er fuer sie nichts.
_ALLOWED_DECISION_MODEL_READERS = frozenset(
    {
        "api/photos.py::_final_selection_decisions",
        "api/photos.py::album_selection",
        "api/album_decisions.py::_existing_decision",
        "api/album_decisions.py::set_album_decision",
        "project_deletion.py::delete_projects",
        # Der Dissens-Block des Demo-Seeders. Er schreibt Entscheidungszeilen und ist damit ein
        # erlaubter Leser - er beruehrt den Einzelentwurf nicht, sondern die Ebene darueber.
        "demo_state.py::_seed_final_selection_dissent",
        # Der Ereignis-Log-Block des Demo-Seeders (Spec 0432). Er LIEST die geschriebenen
        # Entscheidungen, um je Zeile ein Ereignis abzulegen - aus dem tatsaechlichen Bestand statt
        # aus einer zweiten Indexliste daneben, die mit dem Vorschlag driften wuerde. Er aendert
        # keine Entscheidungszeile und beruehrt den Einzelentwurf nicht.
        "demo_state.py::_seed_feedback_events",
    }
)


def _functions_naming_the_decision_model(source: str) -> set[str]:
    """Die Funktionen dieses Moduls, die `FinalSelectionDecision` nennen - ueber den Syntaxbaum,
    nicht ueber eine Textsuche.

    DREI erkannte Leseformen, alle drei am Bestand vertreten: der Attributzugriff
    (`FinalSelectionDecision.photo_id`), der Konstruktoraufruf und der blosse Name als Argument
    (`aliased(FinalSelectionDecision)`, `session.get(FinalSelectionDecision, …)`). Alle drei sind
    im Syntaxbaum derselbe `ast.Name` - genau deshalb ist der Baum hier das richtige Werkzeug.

    Eine verschachtelte Funktion wird ihrer umgebenden ZUGERECHNET (der Teilbaum wird vollstaendig
    durchlaufen) und zusaetzlich unter ihrem eigenen Namen gefuehrt: Ein Zugriff, der sich in einen
    lokalen Helfer zurueckzieht, soll nicht aus der Messung fallen."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if any(
            isinstance(child, ast.Name) and child.id == _DECISION_MODEL for child in ast.walk(node)
        ):
            found.add(node.name)
    return found


class TestTheDraftFunctionsNeverTouchTheJointDecision:
    def test_exactly_the_known_functions_name_the_decision_model(self) -> None:
        """DIE Zusage: Weder `_draft_photo_ids` noch `draft_alternatives` steht in der Fundmenge.
        Eine dort eingefuegte Abfrage auf `final_selection_decisions` roetet keinen
        Verhaltenstest - der Entwurf saehe weiter richtig aus, waehrend er eine zweite Ebene
        bekommt."""
        source_root = Path(photosort.__file__).resolve().parent
        readers = {
            f"{path.relative_to(source_root)}::{function}"
            for path in source_root.rglob("*.py")
            for function in _functions_naming_the_decision_model(path.read_text(encoding="utf-8"))
        }

        assert readers == set(_ALLOWED_DECISION_MODEL_READERS), (
            "Die Menge der Funktionen, die `FinalSelectionDecision` nennen, weicht von den "
            f"erlaubten ab ({sorted(_ALLOWED_DECISION_MODEL_READERS)}). Zu viel: "
            f"{sorted(readers - set(_ALLOWED_DECISION_MODEL_READERS))}; nicht mehr gefunden: "
            f"{sorted(set(_ALLOWED_DECISION_MODEL_READERS) - readers)}"
        )

    def test_the_found_set_is_not_empty(self) -> None:
        """Positiv-Gegenprobe: Ein Waechter, der nichts findet, besteht jede Zusage. Die
        Fundmenge oben muss die Stellen tatsaechlich TREFFEN, nicht bloss die verbotenen
        verfehlen."""
        assert _ALLOWED_DECISION_MODEL_READERS
        source = (
            Path(photosort.__file__).resolve().parent / "api" / "album_decisions.py"
        ).read_text(encoding="utf-8")

        assert "set_album_decision" in _functions_naming_the_decision_model(source)

    @pytest.mark.parametrize(
        "snippet",
        [
            pytest.param(
                "def f():\n    return FinalSelectionDecision.photo_id", id="attributzugriff"
            ),
            pytest.param(
                "def f():\n    return FinalSelectionDecision(photo_id=1, included=True)",
                id="konstruktor",
            ),
            pytest.param("def f():\n    return aliased(FinalSelectionDecision)", id="argument"),
        ],
    )
    def test_the_guard_sees_every_read_form_it_claims_to_cover(self, snippet: str) -> None:
        """Selbstschutz zum Selbstschutz: Der Waechter ist nur so gut wie die Formen, die er
        tatsaechlich erkennt - jede wird einzeln nachgewiesen, statt sich darauf zu verlassen,
        dass der Bestand sie alle enthaelt."""
        assert _functions_naming_the_decision_model(snippet) == {"f"}

    def test_the_guard_ignores_the_mere_mention_in_a_comment_or_docstring(self) -> None:
        """Die Gegenprobe, die eine Textsuche NICHT bestuende: Ein Kommentar, der erklaert, warum
        der Entwurfszweig die Tabelle gerade nicht liest, ist kein Zugriff - und ein Wortverbot
        verboete genau diese Begruendung."""
        snippet = (
            "def f():\n"
            '    """Liest ausdruecklich KEINE FinalSelectionDecision."""\n'
            "    # FinalSelectionDecision gehoert hier nicht her.\n"
            "    return None\n"
        )

        assert _functions_naming_the_decision_model(snippet) == set()

    def test_the_guard_ignores_the_loader_that_every_read_path_must_call(self) -> None:
        """Die Abgrenzung, auf der die ganze Messung steht: `_final_selection_decisions` ist der
        PFLICHTIGE Aufruf jedes Lesepfads - die drei Felder stehen ueberall. Zaehlte er als
        Zugriff, waere der Waechter dauerhaft rot."""
        snippet = "async def f():\n    return await _final_selection_decisions(session, ids)"

        assert _functions_naming_the_decision_model(snippet) == set()


class TestPlaceLookupIsBoundToItsProject:
    """`place_lookups` ist die DAUERHAFTESTE Ortsspur des Systems (S6): lauf-unabhaengig, und
    ihre Lebensdauer haengt allein am Projekt."""

    async def test_a_second_row_for_the_same_cell_of_the_same_project_is_rejected(
        self, db_session: AsyncSession
    ) -> None:
        project = Project(name=f"Projekt {uuid4()}", opencloud_drive_id="d", opencloud_path="/a")
        db_session.add(project)
        await db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        db_session.add(
            PlaceLookup(
                project_id=project.id,
                cell_lat=47.51,
                cell_lon=11.09,
                locality="Garmisch-Partenkirchen",
                matched_level="locality",
                source="geonames",
                resolved_at=now,
            )
        )
        await db_session.commit()

        db_session.add(
            PlaceLookup(
                project_id=project.id,
                cell_lat=47.51,
                cell_lon=11.09,
                locality="Anderswo",
                matched_level="locality",
                source="geonames",
                resolved_at=now,
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()

    async def test_the_same_cell_in_a_second_project_is_a_row_of_its_own(
        self, db_session: AsyncSession
    ) -> None:
        """Die Auskunft des einen Projekts wird fuer das andere NIE gelesen - sie darf deshalb
        auch nicht am Constraint des ersten scheitern."""
        first = Project(name=f"Projekt {uuid4()}", opencloud_drive_id="d", opencloud_path="/a")
        second = Project(name=f"Projekt {uuid4()}", opencloud_drive_id="d", opencloud_path="/b")
        db_session.add_all([first, second])
        await db_session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        db_session.add_all(
            [
                PlaceLookup(
                    project_id=first.id,
                    cell_lat=47.51,
                    cell_lon=11.09,
                    locality="Garmisch-Partenkirchen",
                    matched_level="locality",
                    source="geonames",
                    resolved_at=now,
                ),
                PlaceLookup(
                    project_id=second.id,
                    cell_lat=47.51,
                    cell_lon=11.09,
                    locality="Garmisch-Partenkirchen",
                    matched_level="locality",
                    source="geonames",
                    resolved_at=now,
                ),
            ]
        )
        await db_session.commit()

        stored = (
            (await db_session.execute(select(PlaceLookup).order_by(PlaceLookup.project_id)))
            .scalars()
            .all()
        )
        assert [row.project_id for row in stored] == sorted([first.id, second.id])

    def test_the_project_column_carries_a_real_foreign_key(self) -> None:
        """Eine bloss logische Spalte fiele still aus der Erreichbarkeitspruefung der
        Projektloeschung heraus - und mit ihr die Zusage, dass die Ortsspur mit dem Projekt
        verschwindet."""
        column = inspect(PlaceLookup).columns["project_id"]

        assert not column.nullable
        assert {fk.target_fullname for fk in column.foreign_keys} == {"projects.id"}

    def test_every_name_level_is_nullable_on_its_own(self) -> None:
        """Eine unbrauchbare Stufe wird `NULL`, nie die ganze Antwort verworfen (S7) - und eine
        Antwort OHNE brauchbare Ebene ist eine Zeile mit leeren Namensstufen, kein Fehlen."""
        columns = inspect(PlaceLookup).columns

        for level in ("neighbourhood", "locality", "region", "country", "matched_level"):
            assert columns[level].nullable, level
        assert not columns["source"].nullable


async def test_event_place_name_is_nullable_and_defaults_to_none(
    db_session: AsyncSession,
) -> None:
    """Der Name eines Events ist ein LAUF-Artefakt: `NULL` heisst "kein aufgeloester Ortsname",
    und ein Altlauf bleibt genau dort."""
    project = Project(name=f"Projekt {uuid4()}", opencloud_drive_id="d", opencloud_path="/a")
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

    now = datetime.now(UTC).replace(tzinfo=None)
    event = Event(criterion_scoring_run_id=run.id, position=1, started_at=now, ended_at=now)
    db_session.add(event)
    await db_session.commit()

    stored = (await db_session.execute(select(Event).where(Event.id == event.id))).scalar_one()
    assert stored.place_name is None
    assert inspect(Event).columns["place_name"].nullable


# specs/features/0481-restdauer-klassifizierungslauf.md, decisions/0116-restdauer-als-
# servermessung-spanne-im-frontend-keine-gesamtrestzeit.md Punkt 1: `phase` und
# `phase_started_at` werden AUSSCHLIESSLICH GEMEINSAM gesetzt, ueber genau eine Funktion.
_ALLOWED_PHASE_WRITER_FUNCTIONS = frozenset({"_set_phase"})
_ALLOWED_PHASE_WRITER_MODULES = frozenset({"worker.py"})

_PHASE = "phase"
_PHASE_STARTED_AT = "phase_started_at"
# Die Zeilenklasse, deren Konstruktor-Schluesselwort zaehlt. AUSGESCHRIEBEN und exakt verglichen:
# `PhotoCloudVisionError(phase=…)` und `CloudVisionStatusOut(phase=…)` fuehren eine gleichnamige
# Spalte eines ANDEREN Modells und sind keine Schreibstelle im Sinne dieser Bindung.
_PHASE_ROW_CLASS = "CriterionScoringRun"
# Ein Schreibzugriff ausserhalb jeder Funktion - er faellt ueber die Gleichheitspruefung unten
# auf, statt unbemerkt keiner Funktion zugeordnet zu werden.
_MODULE_LEVEL = "<modulebene>"


def _is_phase_write(node: ast.AST, field: str) -> bool:
    """Ob DIESER Knoten `field` an einer `CriterionScoringRun`-Zeile setzt.

    VIER Schreibformen, verglichen ueber `ast.Attribute.attr` bzw. das Schluesselwort - nie ueber
    ein Textmuster: `"phase"` als Teilstring traefe `phase_started_at`, `cloud_phases` und
    `CloudVisionPhase` gleich mit.

    1. Attributzuweisung `run.phase = ...`.
    2. `phase` als Schluessel eines Dict-Literals (die Form eines gebuendelten Bulk-Updates).
    3. `phase` als Schluesselwort eines `.values(...)`-Aufrufs.
    4. Das KONSTRUKTOR-Schluesselwort `CriterionScoringRun(phase=...)`.

    Die vierte Form ist eine BEWUSSTE Abweichung vom `taken_at`-Waechter, der das Anlegen einer
    Zeile ausdruecklich nicht zaehlt. Hier ist gerade das Anlegen die gefaehrliche Stelle: Die
    ERSTE Phase jedes Laufs wurde vor dieser Spec als Konstruktor-Schluesselwort gesetzt. Bliebe
    sie es, entkaeme genau sie der Bindung - und die gesamte erste Phase jedes Laufs zeigte
    dauerhaft "wird noch ermittelt", schweigend und ohne roten Test."""
    if isinstance(node, ast.Assign | ast.AugAssign | ast.AnnAssign):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return any(isinstance(target, ast.Attribute) and target.attr == field for target in targets)
    if isinstance(node, ast.Dict):
        return any(isinstance(key, ast.Constant) and key.value == field for key in node.keys)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "values":
            return any(keyword.arg == field for keyword in node.keywords)
        if isinstance(node.func, ast.Name) and node.func.id == _PHASE_ROW_CLASS:
            return any(keyword.arg == field for keyword in node.keywords)
    return False


def _functions_writing(source: str, field: str) -> set[str]:
    """Die Namen der Funktionen dieses Quelltexts, die `field` setzen - Modulebene als eigener,
    nicht stiller Eintrag.

    Feiner als der Modulwaechter unten, und das ist der Punkt: Waeren nur die MODULE geprueft,
    duerfte eine beliebige zweite Funktion in `worker.py` die Phase setzen, ohne den Zeitstempel
    mitzufuehren - der Modulwaechter bliebe gruen."""
    found: set[str] = set()

    def descend(node: ast.AST, enclosing: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                descend(child, child.name)
                continue
            if _is_phase_write(child, field):
                found.add(enclosing)
            descend(child, enclosing)

    descend(ast.parse(source), _MODULE_LEVEL)
    return found


def _writes_a_phase_field(source: str) -> bool:
    return bool(_functions_writing(source, _PHASE) or _functions_writing(source, _PHASE_STARTED_AT))


def _worker_source() -> str:
    return (Path(photosort.__file__).resolve().parent / "worker.py").read_text(encoding="utf-8")


def test_exactly_one_function_writes_the_phase() -> None:
    """STRUKTURELLER Waechter: Eine zweite Schreibstelle auf `phase` roetet KEINEN
    Verhaltenstest - sie setzt den Teilschritt weiterhin richtig und laesst nur den Zeitstempel
    stehen. Die Restdauer rechnet dann den Beginn des vorigen Teilschritts gegen den Fortschritt
    des aktuellen und ist zu gross, ohne Fehlermeldung.

    Geprueft wird GLEICHHEIT, nicht Teilmenge: Findet der Waechter die erlaubte Stelle nicht mehr,
    prueft er fuer sie nichts - so bliebe er gruen, nachdem die Bindung ausgebaut wurde."""
    writers = _functions_writing(_worker_source(), _PHASE)

    assert writers == set(_ALLOWED_PHASE_WRITER_FUNCTIONS), (
        "Die Menge der Funktionen in worker.py, die `CriterionScoringRun.phase` setzen, weicht "
        f"von der genau einen erlaubten ab ({sorted(_ALLOWED_PHASE_WRITER_FUNCTIONS)}). Zu viel: "
        f"{sorted(writers - set(_ALLOWED_PHASE_WRITER_FUNCTIONS))}; nicht mehr gefunden: "
        f"{sorted(set(_ALLOWED_PHASE_WRITER_FUNCTIONS) - writers)}"
    )


def test_exactly_one_function_writes_the_phase_start() -> None:
    """Dieselbe Pruefung fuer die zweite Spalte. Sie steht EINZELN da, weil die erste allein auch
    gegen ein `_set_phase` bestuende, das `phase_started_at` gar nicht mehr anfasst - dann gaebe
    es schlicht keine zweite Schreibstelle, und die erste Zusicherung bliebe gruen."""
    writers = _functions_writing(_worker_source(), _PHASE_STARTED_AT)

    assert writers == set(_ALLOWED_PHASE_WRITER_FUNCTIONS), (
        "Die Menge der Funktionen in worker.py, die `CriterionScoringRun.phase_started_at` "
        f"setzen, weicht von der genau einen erlaubten ab "
        f"({sorted(_ALLOWED_PHASE_WRITER_FUNCTIONS)}). Zu viel: "
        f"{sorted(writers - set(_ALLOWED_PHASE_WRITER_FUNCTIONS))}; nicht mehr gefunden: "
        f"{sorted(set(_ALLOWED_PHASE_WRITER_FUNCTIONS) - writers)}"
    )


def test_the_one_phase_writer_sets_both_columns() -> None:
    """Die dritte Zusicherung, und die eigentliche Bindung: DIESELBE Funktion setzt beide. Ohne
    sie waeren die beiden Mengen oben auch dann erfuellt, wenn sie leer waeren."""
    source = _worker_source()

    assert _ALLOWED_PHASE_WRITER_FUNCTIONS <= _functions_writing(source, _PHASE)
    assert _ALLOWED_PHASE_WRITER_FUNCTIONS <= _functions_writing(source, _PHASE_STARTED_AT)


def test_exactly_the_one_known_module_writes_a_phase_field() -> None:
    """PAKETWEIT, nicht nur modulintern: Ohne diese Pruefung wanderte die Schreibstelle nach
    `api/projects.py` oder `demo_state.py` ab, und der Funktionswaechter oben bliebe gruen, weil
    er nur `worker.py` liest.

    Der Suchraum wird GEMESSEN (`rglob`), nicht gelistet - eine neu hinzukommende Datei ist sonst
    von Anfang an unsichtbar."""
    source_root = Path(photosort.__file__).resolve().parent
    writers = {
        str(path.relative_to(source_root))
        for path in source_root.rglob("*.py")
        if _writes_a_phase_field(path.read_text(encoding="utf-8"))
    }

    assert writers == set(_ALLOWED_PHASE_WRITER_MODULES), (
        "Die Menge der Module, die `CriterionScoringRun.phase`/`phase_started_at` schreiben, "
        f"weicht von der genau einen erlaubten ab ({sorted(_ALLOWED_PHASE_WRITER_MODULES)}). Zu "
        f"viel: {sorted(writers - set(_ALLOWED_PHASE_WRITER_MODULES))}; nicht mehr gefunden: "
        f"{sorted(set(_ALLOWED_PHASE_WRITER_MODULES) - writers)}"
    )


@pytest.mark.parametrize(
    "snippet",
    [
        pytest.param("def f():\n    run.phase = value", id="attributzuweisung"),
        pytest.param('def f():\n    rows.append({"id": 1, "phase": value})', id="dict-schluessel"),
        pytest.param(
            "def f():\n    session.execute(update(CriterionScoringRun).values(phase=value))",
            id="values-aufruf",
        ),
        pytest.param(
            "def f():\n    session.add(CriterionScoringRun(project_id=1, phase=value))",
            id="konstruktor-schluesselwort",
        ),
    ],
)
def test_the_phase_guard_sees_every_write_form_it_claims_to_cover(snippet: str) -> None:
    """Der Waechter ist nur so gut wie die Formen, die er tatsaechlich erkennt - jede der vier
    wird hier EINZELN nachgewiesen, statt sich darauf zu verlassen, dass der Bestand sie alle
    enthaelt (er enthaelt die Dict- und die `values()`-Form nicht)."""
    assert _functions_writing(snippet, _PHASE) == {"f"}


def test_the_phase_guard_sees_the_start_column_in_the_same_forms() -> None:
    """Dieselben Formen fuer die zweite Spalte - der Vergleich laeuft ueber den Feldnamen, nicht
    ueber ein Muster, und muss deshalb fuer beide gleich greifen."""
    assert _functions_writing("def f():\n    run.phase_started_at = now", _PHASE_STARTED_AT) == {
        "f"
    }
    assert _functions_writing(
        "def f():\n    session.add(CriterionScoringRun(phase_started_at=now))", _PHASE_STARTED_AT
    ) == {"f"}


def test_the_phase_guard_does_not_confuse_the_two_columns() -> None:
    """`phase_started_at` enthaelt `phase` als Teilstring. Ein Textmuster zaehlte die
    Zeitstempel-Zuweisung als Phasen-Schreibstelle mit, und der Waechter waere in beiden
    Richtungen blind."""
    assert _functions_writing("def f():\n    run.phase_started_at = now", _PHASE) == set()
    assert _functions_writing("def f():\n    run.phase = value", _PHASE_STARTED_AT) == set()


def test_the_phase_guard_ignores_a_constructor_of_another_model() -> None:
    """Gegenprobe: `PhotoCloudVisionError` und `CloudVisionStatusOut` fuehren eine gleichnamige
    Spalte. Zaehlten sie mit, waeren `worker.py::_record_cloud_vision_error` und `api/photos.py`
    Befunde - und der Waechter waere nur noch abzuschalten."""
    assert (
        _functions_writing(
            "def f():\n    return PhotoCloudVisionError(photo_id=1, phase=phase)", _PHASE
        )
        == set()
    )
    assert (
        _functions_writing(
            "def f():\n    return CloudVisionStatusOut(phase=phase, status=status)", _PHASE
        )
        == set()
    )


def test_the_phase_guard_ignores_a_parameter_or_a_local_variable() -> None:
    """Gegenprobe: ein gleichnamiger Funktionsparameter und eine gleichnamige lokale Variable
    sind keine Spaltenzuweisung. `worker.py` fuehrt beides."""
    assert _functions_writing("def f(phase: str) -> None:\n    pass", _PHASE) == set()
    assert _functions_writing("def f():\n    phase = compute()", _PHASE) == set()


def test_the_phase_guard_ignores_reading_the_columns() -> None:
    """Gegenprobe: Lesen zaehlt nie - sonst waere jeder Lesepfad (`api/projects.py`) ein Befund."""
    assert (
        _functions_writing("def f():\n    return select(CriterionScoringRun.phase)", _PHASE)
        == set()
    )
    assert (
        _functions_writing("def f():\n    if run.phase is None: return run.phase", _PHASE) == set()
    )
    assert (
        _functions_writing(
            "def f():\n    return CriterionScoringRunSummary(phase=run.phase)", _PHASE
        )
        == set()
    )


async def test_criterion_scoring_run_phase_start_is_nullable_and_defaults_to_none(
    db_session: AsyncSession,
) -> None:
    """Der Beginn des laufenden Teilschritts. `NULL` heisst "kein laufender Teilschritt"
    (beendet, abgebrochen, oder Altzeile), NIE "gerade begonnen"."""
    project = Project(name=f"Projekt {uuid4()}", opencloud_drive_id="d", opencloud_path="/a")
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

    stored = (
        await db_session.execute(
            select(CriterionScoringRun).where(CriterionScoringRun.id == run.id)
        )
    ).scalar_one()
    assert stored.phase_started_at is None
    assert inspect(CriterionScoringRun).columns["phase_started_at"].nullable
    assert CriterionScoringRun.__table__.c.phase_started_at.server_default is None
