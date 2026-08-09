from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFilter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    Photo,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.scoring import SHARPNESS_REJECT_THRESHOLD
from photosort.security import hash_password
from photosort.thumbnails import display_path
from photosort.worker import run_project_scoring


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


def _write_display_variant(cache_dir: Path, photo: Photo, image: Image.Image) -> None:
    path = display_path(cache_dir, photo.id, photo.etag)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="JPEG")


def _sharp_photo_image(seed: int = 0, size: int = 200) -> Image.Image:
    # Genuegend Struktur/Kontrast, um deutlich oberhalb von SHARPNESS_REJECT_THRESHOLD zu liegen.
    image = Image.new("RGB", (size, size), color=(20 + seed, 40, 80))
    draw = ImageDraw.Draw(image)
    draw.ellipse((10, 10, size - 10, size - 10), fill=(230, 200, 100))
    draw.rectangle((size // 2, 0, size, size // 2), fill=(30, 200, 30))
    draw.line((0, 0, size, size), fill=(255, 0, 0), width=3)
    return image


def _blurry_photo_image(size: int = 200) -> Image.Image:
    # Vollstaendig schwarz (nicht nur eine beliebige flaeche Farbe): Pillows Kernel-Filter behaelt
    # am Bildrand den unveraenderten Originalwert (kein Zero-Padding, siehe scoring.py-Tests) -
    # bei Farbe 0 faellt dieser Randeffekt weg und die Laplace-Varianz ist tatsaechlich minimal,
    # weit unterhalb von SHARPNESS_REJECT_THRESHOLD.
    return Image.new("RGB", (size, size), color=(0, 0, 0))


def _slightly_blurred(image: Image.Image) -> Image.Image:
    # Gleicher dHash-Cluster (Hamming-Distanz 0, siehe Testkommentar unten), aber deutlich
    # niedrigere Laplace-Varianz - simuliert die leicht unschaerfere Aufnahme einer Burst-Serie.
    return image.filter(ImageFilter.GaussianBlur(radius=1.0))


def _distinct_photo_image(variant: int, size: int = 200) -> Image.Image:
    """Erzeugt deutlich unterschiedliche (nicht als Duplikat erkannte) Testfotos - im Gegensatz zu
    _sharp_photo_image(seed=...), das nur die Hintergrundfarbe leicht variiert und damit fuer die
    Duplikaterkennung faelschlich als "nahezu identisch" gilt. Fuer Tests gedacht, die
    ausschliesslich das Zeitfenster-Clustering pruefen wollen, ohne von der Duplikaterkennung
    beeinflusst zu werden."""
    colors = [(20, 40, 200), (200, 40, 20), (20, 200, 40)]
    image = Image.new("RGB", (size, size), color=colors[variant % len(colors)])
    draw = ImageDraw.Draw(image)
    if variant % 3 == 0:
        draw.ellipse((10, 10, size - 10, size - 10), fill=(230, 200, 100))
        draw.line((0, 0, size, size), fill=(255, 255, 255), width=5)
    elif variant % 3 == 1:
        draw.rectangle((10, 10, size - 10, size - 10), fill=(10, 10, 10))
        draw.line((size, 0, 0, size), fill=(255, 255, 255), width=5)
    else:
        draw.polygon([(size // 2, 0), (size, size), (0, size)], fill=(250, 250, 10))
        draw.rectangle((0, 0, size // 3, size // 3), fill=(0, 0, 0))
    return image


async def test_scoring_run_success_scores_photo(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    _write_display_variant(tmp_path, photo, _sharp_photo_image())

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run.status == ScanStatus.SUCCESS
    assert scoring_run.photos_total == 1
    assert scoring_run.photos_processed == 1

    score = (
        await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    ).scalar_one()
    assert score.sharpness > 0
    assert score.phash is not None
    assert score.suggested_status is None
    assert score.local_quality_score is not None
    assert score.cluster_key is not None
    assert score.duplicate_of is None


async def test_scoring_run_rejects_photo_below_sharpness_threshold(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    photo = await _add_photo(
        db_session, project, "blurry.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    _write_display_variant(tmp_path, photo, _blurry_photo_image())

    await run_project_scoring(db_session, project, cache_dir=tmp_path)

    score = (
        await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    ).scalar_one()
    assert score.sharpness < SHARPNESS_REJECT_THRESHOLD
    assert score.suggested_status == RatingStatus.REJECTED
    assert score.local_quality_score is None
    assert score.cluster_key is None
    assert score.duplicate_of is None


async def test_scoring_run_marks_duplicate_cluster_loser_and_keeps_sharper_winner(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    base_image = _sharp_photo_image()
    winner = await _add_photo(
        db_session, project, "burst1.jpg", "etag-1", datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)
    )
    loser = await _add_photo(
        db_session, project, "burst2.jpg", "etag-2", datetime(2023, 1, 1, 10, 0, 1, tzinfo=UTC)
    )
    # Winner bekommt das schaerfere Original, Loser eine leicht unschaerfere Variante desselben
    # Motivs (gleicher dHash-Cluster, siehe _slightly_blurred) - simuliert eine Burst-Aufnahme.
    _write_display_variant(tmp_path, winner, base_image)
    _write_display_variant(tmp_path, loser, _slightly_blurred(base_image))

    await run_project_scoring(db_session, project, cache_dir=tmp_path)

    scores = {
        s.photo_id: s
        for s in (await db_session.execute(select(PhotoScore))).scalars()
    }
    assert scores[winner.id].duplicate_of is None
    assert scores[winner.id].suggested_status is None
    assert scores[loser.id].duplicate_of == winner.id
    assert scores[loser.id].suggested_status == RatingStatus.REJECTED


async def test_scoring_run_counts_no_suggestions_when_nothing_stands_out(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    _write_display_variant(tmp_path, photo, _sharp_photo_image())

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run.suggestions_found == 0


async def test_scoring_run_counts_blurry_photo_as_suggestion(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    photo = await _add_photo(
        db_session, project, "blurry.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    _write_display_variant(tmp_path, photo, _blurry_photo_image())

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run.suggestions_found == 1


async def test_scoring_run_counts_duplicate_cluster_loser_as_suggestion(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    base_image = _sharp_photo_image()
    winner = await _add_photo(
        db_session, project, "burst1.jpg", "etag-1", datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)
    )
    loser = await _add_photo(
        db_session, project, "burst2.jpg", "etag-2", datetime(2023, 1, 1, 10, 0, 1, tzinfo=UTC)
    )
    _write_display_variant(tmp_path, winner, base_image)
    _write_display_variant(tmp_path, loser, _slightly_blurred(base_image))

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run.suggestions_found == 1


async def test_scoring_run_counts_mix_of_blurry_and_duplicate_suggestions(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    base_image = _sharp_photo_image()
    winner = await _add_photo(
        db_session, project, "burst1.jpg", "etag-1", datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC)
    )
    loser = await _add_photo(
        db_session, project, "burst2.jpg", "etag-2", datetime(2023, 1, 1, 10, 0, 1, tzinfo=UTC)
    )
    blurry = await _add_photo(
        db_session, project, "blurry.jpg", "etag-3", datetime(2023, 1, 1, 11, 0, 0, tzinfo=UTC)
    )
    _write_display_variant(tmp_path, winner, base_image)
    _write_display_variant(tmp_path, loser, _slightly_blurred(base_image))
    _write_display_variant(tmp_path, blurry, _blurry_photo_image())

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run.suggestions_found == 2


async def test_scoring_run_marked_failed_keeps_suggestions_found_at_default(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import photosort.worker as worker_module

    monkeypatch.setattr(worker_module, "SCORE_COMMIT_BATCH_SIZE", 1)

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected clustering failure")

    monkeypatch.setattr(worker_module, "assign_duplicate_clusters", _boom)

    project = await _make_project(db_session)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    _write_display_variant(tmp_path, photo, _sharp_photo_image())

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run.status == ScanStatus.FAILED
    assert scoring_run.suggestions_found == 0


async def test_scoring_run_suggestions_found_not_persisted_when_final_commit_fails(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Copilot-Review-Fund (PR #38): suggestions_found wird VOR dem finalen Erfolgs-Commit
    gesetzt (worker.py). Faellt genau dieser Commit fehl, greift derselbe bereits etablierte
    Rollback-Mechanismus wie fuer photos_processed (session.rollback() expired das ORM-Objekt,
    der noch nicht committete In-Memory-Wert geht verloren, der anschliessende FAILED-Commit
    schreibt daher keinen len(rejected_ids)-Teilstand) - kein Sonderfall noetig."""
    project = await _make_project(db_session)
    photo = await _add_photo(
        db_session, project, "blurry.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    _write_display_variant(tmp_path, photo, _blurry_photo_image())

    original_commit = db_session.commit
    call_count = {"n": 0}

    async def flaky_commit() -> None:
        call_count["n"] += 1
        # Commit-Reihenfolge fuer einen Einzelfoto-Lauf: 1) ScoringRun anlegen (RUNNING),
        # 2) photos_total setzen, 3) photos_processed nach der Verarbeitungsschleife,
        # 4) der finale Erfolgs-Commit (status=SUCCESS, suggestions_found gesetzt) - genau
        # dieser soll hier fehlschlagen.
        if call_count["n"] == 4:
            raise RuntimeError("simulated final commit failure")
        await original_commit()

    monkeypatch.setattr(db_session, "commit", flaky_commit)

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run.status == ScanStatus.FAILED
    assert scoring_run.suggestions_found == 0


async def test_scoring_run_skips_photo_without_readable_display_cache(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    await _add_photo(db_session, project, "missing.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC))

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run.status == ScanStatus.SUCCESS
    assert scoring_run.photos_total == 1
    assert scoring_run.photos_processed == 1
    scores = (await db_session.execute(select(PhotoScore))).scalars().all()
    assert scores == []


async def test_scoring_run_skips_undecodable_display_cache_without_failing(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    photo = await _add_photo(
        db_session, project, "broken.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    path = display_path(tmp_path, photo.id, photo.etag)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a real jpeg")

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run.status == ScanStatus.SUCCESS
    assert scoring_run.photos_processed == 1
    scores = (await db_session.execute(select(PhotoScore))).scalars().all()
    assert scores == []


async def test_scoring_run_commits_progress_periodically(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neues Testmuster (Teststrategie-Abschnitt der Spec): Batch-Konstante fuer
    Zwischen-Commits klein setzen, um granulares Fortschritts-Commit-Verhalten mit wenigen
    Testfotos zu pruefen, statt echte 25+ Testfotos anzulegen."""
    import photosort.worker as worker_module

    monkeypatch.setattr(worker_module, "SCORE_COMMIT_BATCH_SIZE", 2)

    project = await _make_project(db_session)
    for i in range(5):
        photo = await _add_photo(
            db_session,
            project,
            f"{i}.jpg",
            f"etag-{i}",
            datetime(2023, 1, 1, 10, i, tzinfo=UTC),
        )
        _write_display_variant(tmp_path, photo, _sharp_photo_image(seed=i))

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run.photos_total == 5
    assert scoring_run.photos_processed == 5


async def test_rescoring_overwrites_existing_photo_scores_without_touching_ratings(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    user = User(username="testuser", password_hash=hash_password("irrelevant"))
    db_session.add(user)
    await db_session.flush()
    db_session.add(Rating(photo_id=photo.id, user_id=user.id, status=RatingStatus.FAVORITE))
    await db_session.commit()

    _write_display_variant(tmp_path, photo, _blurry_photo_image())
    await run_project_scoring(db_session, project, cache_dir=tmp_path)
    first_score = (
        await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id))
    ).scalar_one()
    assert first_score.suggested_status == RatingStatus.REJECTED

    # Zweiter Lauf: Foto ist jetzt (neues, scharfes Bild unter derselber etag/Pfad) nicht mehr
    # unscharf -> die PhotoScore-Zeile wird vollstaendig ueberschrieben, nicht als zweite Zeile
    # angelegt.
    _write_display_variant(tmp_path, photo, _sharp_photo_image())
    await run_project_scoring(db_session, project, cache_dir=tmp_path)

    scores = (
        (await db_session.execute(select(PhotoScore).where(PhotoScore.photo_id == photo.id)))
        .scalars()
        .all()
    )
    assert len(scores) == 1
    assert scores[0].suggested_status is None

    ratings = (await db_session.execute(select(Rating))).scalars().all()
    assert len(ratings) == 1
    assert ratings[0].status == RatingStatus.FAVORITE


async def test_scoring_run_marked_failed_leaves_committed_progress_untouched(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import photosort.worker as worker_module

    monkeypatch.setattr(worker_module, "SCORE_COMMIT_BATCH_SIZE", 1)

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected clustering failure")

    monkeypatch.setattr(worker_module, "assign_duplicate_clusters", _boom)

    project = await _make_project(db_session)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    _write_display_variant(tmp_path, photo, _sharp_photo_image())

    scoring_run = await run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run.status == ScanStatus.FAILED
    assert scoring_run.error_message == "unexpected clustering failure"
    # photos_processed wurde bereits vor dem Fehler committet (Zwischen-Commit-Batch=1) und bleibt
    # erhalten - kein Rollback des bereits Verarbeiteten (Akzeptanzkriterium der Spec).
    assert scoring_run.photos_processed == 1


async def test_scoring_run_marked_failed_on_cancelled_error(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Schicht 1 des Fortschritts-Watchdogs (specs/features/0034-scan-haenger-fortschritts-
    watchdog.md, ADR 0019), Pendant zu test_scan_run_marked_failed_on_cancelled_error - hier aus
    der Verarbeitungsschleife (nicht walk()) heraus ausgeloest: compute_sharpness wirft mitten in
    _compute_photo_metrics asyncio.CancelledError, was dessen eigener `except Exception`-Block
    NICHT abfaengt (BaseException seit Python 3.8) - die Exception propagiert bis in
    run_project_scoring durch.

    project_id wird VOR dem Aufruf gelesen und als lokale Variable verwendet (nicht project.id
    danach): session.rollback() in _fail_run expired alle Objekte der Session - ein direkter
    project.id-Zugriff DANACH wuerde einen impliziten Lazy-Load ausloesen, der ausserhalb des
    von SQLAlchemy fuer Async-Sessions vorausgesetzten greenlet-Kontexts mit
    sqlalchemy.exc.MissingGreenlet fehlschlaegt (kein Bug dieser Spec, sondern ein bekanntes
    SQLAlchemy-Async-Verhalten - see auch die anderen beiden Cancelled-Error-Tests, die aus
    genau diesem Grund denselben lokalen project_id-Zwischenwert verwenden)."""
    import photosort.worker as worker_module

    def _boom(*args: object, **kwargs: object) -> float:
        raise asyncio.CancelledError()

    monkeypatch.setattr(worker_module, "compute_sharpness", _boom)

    project = await _make_project(db_session)
    project_id = project.id
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    _write_display_variant(tmp_path, photo, _sharp_photo_image())

    with pytest.raises(asyncio.CancelledError):
        await run_project_scoring(db_session, project, cache_dir=tmp_path)

    scoring_run = (
        await db_session.execute(select(ScoringRun).where(ScoringRun.project_id == project_id))
    ).scalar_one()
    assert scoring_run.status == ScanStatus.FAILED
    assert scoring_run.error_message


async def test_time_clustering_groups_photos_within_gap(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    close_a = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
    )
    close_b = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
    )
    far = await _add_photo(
        db_session, project, "c.jpg", "etag-c", datetime(2023, 1, 1, 20, 0, tzinfo=UTC)
    )
    for i, photo in enumerate([close_a, close_b, far]):
        _write_display_variant(tmp_path, photo, _distinct_photo_image(i))

    await run_project_scoring(db_session, project, cache_dir=tmp_path)

    scores = {
        s.photo_id: s for s in (await db_session.execute(select(PhotoScore))).scalars()
    }
    assert scores[close_a.id].cluster_key == scores[close_b.id].cluster_key
    assert scores[far.id].cluster_key != scores[close_a.id].cluster_key
