"""Kooperativer Abbruch des Ausschusslaufs: Uebernahme, Pruefpunkt je Commit-Batch und kein Gate.

Der Abbruch kommt aus einem Haken an der Metrik-Berechnung (dem Element des Laufs): nach dem n-ten
Foto setzt eine ZWEITE Session den Merker.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker as worker_module
from photosort.db import make_session_factory
from photosort.models import PhotoScore, Project, ScanRun, ScanStatus, ScoringRun
from photosort.worker import _runs as worker_runs
from photosort.worker import scoring as worker_scoring
from tests.test_worker_score_project import (
    _add_photo,
    _blurry_photo_image,
    _make_project,
    _write_display_variant,
)


async def _blurry_photos(session: AsyncSession, project: Project, cache: Path, count: int) -> None:
    for index in range(count):
        photo = await _add_photo(
            session, project, f"{index}.jpg", f"etag-{index}", datetime(2023, 1, 1, tzinfo=UTC)
        )
        _write_display_variant(cache, photo, _blurry_photo_image())


def _cancel_after(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, after: int
) -> list[float]:
    """Ersetzt die Schaerfe-Berechnung durch eine zaehlende Huelle, die nach dem n-ten Foto den
    Merker ueber eine zweite Session setzt."""
    original = worker_scoring.compute_sharpness
    calls: list[float] = []
    factory = make_session_factory(session.bind)

    def _counting(image: Image.Image) -> float:
        value = original(image)
        calls.append(value)
        if len(calls) == after:
            # Synchroner Haken in der synchronen Metrik-Berechnung: der Merker wird ueber die
            # Ereignisschleife des Tests gesetzt, bevor der naechste Pruefpunkt liest.
            pending.append(after)
        return value

    pending: list[int] = []
    original_check = worker_runs._raise_if_cancel_requested

    async def _check(check_session: AsyncSession, run: object) -> None:
        if pending:
            pending.clear()
            async with factory() as other:
                await other.execute(
                    update(ScoringRun).values(cancel_requested_at=datetime(2030, 1, 1))
                )
                await other.commit()
        await original_check(check_session, run)  # type: ignore[arg-type]

    monkeypatch.setattr(worker_scoring, "compute_sharpness", _counting)
    monkeypatch.setattr(worker_runs, "_raise_if_cancel_requested", _check)
    return calls


async def test_a_cancel_stops_at_the_next_batch_and_confirms_nothing(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker_scoring, "SCORE_COMMIT_BATCH_SIZE", 2)
    project = await _make_project(db_session)
    await _blurry_photos(db_session, project, tmp_path, 6)
    calls = _cancel_after(db_session, monkeypatch, after=1)

    scoring_run = await worker_module.run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run is not None
    assert scoring_run.status == ScanStatus.CANCELLED
    assert scoring_run.error_message is None
    # Der angefangene Batch (2 Fotos) wird fertig, danach kein Foto mehr.
    assert len(calls) == 2
    assert scoring_run.photos_processed == 2
    assert scoring_run.photos_total == 6
    assert scoring_run.gate_confirmed_at is None
    assert scoring_run.suggestions_found == 0
    scores = (await db_session.execute(select(PhotoScore))).scalars().all()
    assert len(scores) == 2
    # Kein Clustering: kein Vorschlag aus diesem Lauf.
    assert all(score.suggested_status is None for score in scores)


async def test_a_cancel_after_the_last_photo_still_skips_the_gate(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rennen: Abbruch nach dem letzten Element, vor dem Abschluss - `cancelled`, kein Gate."""
    monkeypatch.setattr(worker_scoring, "SCORE_COMMIT_BATCH_SIZE", 10)
    project = await _make_project(db_session)
    await _blurry_photos(db_session, project, tmp_path, 2)
    _cancel_after(db_session, monkeypatch, after=2)

    scoring_run = await worker_module.run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert scoring_run is not None
    assert scoring_run.status == ScanStatus.CANCELLED
    assert scoring_run.photos_processed == 2
    assert scoring_run.gate_confirmed_at is None


async def test_a_queued_scoring_run_is_taken_over(db_session: AsyncSession, tmp_path: Path) -> None:
    project = await _make_project(db_session)
    await _blurry_photos(db_session, project, tmp_path, 1)
    queued = ScoringRun(project_id=project.id, status=ScanStatus.QUEUED)
    db_session.add(queued)
    await db_session.commit()

    scoring_run = await worker_module.run_project_scoring(
        db_session, project, cache_dir=tmp_path, run_id=queued.id
    )

    assert scoring_run is not None
    assert scoring_run.id == queued.id
    assert scoring_run.status == ScanStatus.SUCCESS
    assert len((await db_session.execute(select(ScoringRun))).scalars().all()) == 1


async def test_a_scoring_run_cancelled_while_waiting_resets_nothing(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    photo = await _add_photo(db_session, project, "a.jpg", "etag", datetime(2023, 1, 1, tzinfo=UTC))
    db_session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=50.0,
            exposure=0.5,
            computed_at=datetime(2023, 1, 1),
            auto_decided=True,
        )
    )
    queued = ScoringRun(
        project_id=project.id,
        status=ScanStatus.CANCELLED,
        cancel_requested_at=datetime(2030, 1, 1),
    )
    db_session.add(queued)
    await db_session.commit()

    result = await worker_module.run_project_scoring(
        db_session, project, cache_dir=tmp_path, run_id=queued.id
    )

    assert result is None
    score = (await db_session.execute(select(PhotoScore))).scalar_one()
    assert score.auto_decided is True
    await db_session.refresh(queued)
    assert queued.status == ScanStatus.CANCELLED


async def test_a_cancel_of_one_run_leaves_the_other_of_the_same_project_running(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AK „Einzeln": zwei Laeufe desselben Projekts - hier Scan und Ausschuss. Abgebrochen wird
    NUR der Scan (ueber eine zweite Session, wie die API es tut); der Ausschuss laeuft zu Ende,
    und sein Zaehler endet ueber dem Stand zum Abbruchzeitpunkt."""
    project = await _make_project(db_session)
    await _blurry_photos(db_session, project, tmp_path, 4)
    scan = ScanRun(project_id=project.id, status=ScanStatus.RUNNING)
    scoring = ScoringRun(project_id=project.id, status=ScanStatus.RUNNING)
    db_session.add_all([scan, scoring])
    await db_session.commit()

    stand_at_abort: list[int] = []
    factory = make_session_factory(db_session.bind)
    original = worker_scoring.compute_sharpness
    calls: list[float] = []
    pending: list[int] = []

    def _counting(image: Image.Image) -> float:
        value = original(image)
        calls.append(value)
        if len(calls) == 1:
            pending.append(1)
        return value

    original_check = worker_runs._raise_if_cancel_requested

    async def _check(check_session: AsyncSession, run: object) -> None:
        if pending:
            pending.clear()
            async with factory() as other:
                await other.execute(
                    update(ScanRun)
                    .where(ScanRun.id == scan.id)
                    .values(cancel_requested_at=datetime(2030, 1, 1))
                )
                stand_at_abort.append(
                    (
                        await other.execute(
                            select(ScoringRun.photos_processed).where(ScoringRun.id == scoring.id)
                        )
                    ).scalar_one()
                )
                await other.commit()
        await original_check(check_session, run)

    monkeypatch.setattr(worker_scoring, "compute_sharpness", _counting)
    monkeypatch.setattr(worker_runs, "_raise_if_cancel_requested", _check)

    result = await worker_module.run_project_scoring(db_session, project, cache_dir=tmp_path)

    assert result is not None
    assert stand_at_abort, "der Abbruch des Scans muss waehrend des Ausschusslaufs passiert sein"
    assert result.status == ScanStatus.SUCCESS
    assert result.cancel_requested_at is None
    assert len(calls) == 4
    assert result.photos_processed == 4
    # Der andere Lauf endet UEBER dem Stand zum Abbruchzeitpunkt - er wurde nicht mitbeendet.
    assert result.photos_processed > stand_at_abort[0]
    await db_session.refresh(scan)
    assert scan.cancel_requested_at is not None
    assert scan.status == ScanStatus.RUNNING
