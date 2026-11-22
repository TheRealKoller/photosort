"""Der Abbruch-Endzustand und sein Vorrang vor `FAILED` auf allen Fehlerpfaden.

Ist `cancel_requested_at` gesetzt, endet ein Lauf `CANCELLED` - auch wenn danach eine Ausnahme
fliegt, ein `CancelledError` (Timeout, Shutdown) eintrifft oder der Fehlerpfad aus anderem Grund
laeuft. Der Merker wird dafuer frisch aus der Datenbank gelesen, nicht aus dem geladenen Objekt.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import event, update
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.db import make_session_factory
from photosort.models import (
    ClassificationPhase,
    ClassificationReview,
    CriterionScoringRun,
    ExportRun,
    ExportRunStatus,
    Project,
    RemoteCategoryClassificationRun,
    ReviewPhase,
    ScanRun,
    ScanStatus,
    ScoringRun,
)
from photosort.worker import classification_review
from photosort.worker._runs import fail_export_run, fail_run, finish_cancelled
from tests.project_graph import get_or_create_user
from tests.support import make_project as _project


async def _request_cancel_from_another_session(session: AsyncSession, run: object) -> None:
    """Setzt den Merker ueber eine ZWEITE Session - wie die API es tut."""
    factory = make_session_factory(session.bind)
    async with factory() as other:
        other_run = await other.get(type(run), run.id)  # type: ignore[attr-defined]
        assert other_run is not None
        other_run.cancel_requested_at = datetime(2030, 1, 1)
        await other.commit()


async def _criterion_run(session: AsyncSession, project: Project) -> CriterionScoringRun:
    scoring = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring.id,
        status=ScanStatus.RUNNING,
        phase=ClassificationPhase.CRITERIA,
    )
    session.add(run)
    await session.commit()
    return run


async def test_finish_cancelled_writes_the_end_state_and_keeps_the_phase(
    db_session: AsyncSession,
) -> None:
    project = await _project(db_session)
    run = await _criterion_run(db_session, project)
    run.photos_processed = 3
    await db_session.commit()

    await finish_cancelled(db_session, run)

    assert run.status == ScanStatus.CANCELLED
    assert run.finished_at is not None
    assert run.error_message is None
    assert run.phase == ClassificationPhase.CRITERIA
    assert run.photos_processed == 3


async def test_finish_cancelled_discards_uncommitted_changes(db_session: AsyncSession) -> None:
    project = await _project(db_session)
    run = ScanRun(project_id=project.id, status=ScanStatus.RUNNING, files_found=2)
    db_session.add(run)
    await db_session.commit()
    run.files_found = 99

    await finish_cancelled(db_session, run)

    assert run.status == ScanStatus.CANCELLED
    assert run.files_found == 2


async def test_finish_cancelled_never_overwrites_an_end_state(db_session: AsyncSession) -> None:
    project = await _project(db_session)
    run = ScanRun(project_id=project.id, status=ScanStatus.SUCCESS)
    db_session.add(run)
    await db_session.commit()

    await finish_cancelled(db_session, run)

    assert run.status == ScanStatus.SUCCESS
    assert run.finished_at is None


async def test_finish_cancelled_handles_the_export_enum(db_session: AsyncSession) -> None:
    project = await _project(db_session)
    run = ExportRun(
        project_id=project.id, status=ExportRunStatus.RUNNING, target_path="X", exported_count=4
    )
    db_session.add(run)
    await db_session.commit()

    await finish_cancelled(db_session, run)

    assert run.status == ExportRunStatus.CANCELLED
    assert run.target_path == "X"
    assert run.exported_count == 4


async def test_finish_cancelled_writes_the_end_state_in_one_conditional_statement(
    db_session: AsyncSession,
) -> None:
    """Spec 0641 S7: Jeder Uebergang in einen Endzustand ist ein bedingtes UPDATE. Der hier
    geprueft hat GENAU EINE Anweisung auf `scan_runs` zur Folge - mit der Bedingung in der
    WHERE-Klausel, nicht mit einem vorher gelesenen Zustand im Python-Code. Nur so kann der
    Watchdog nicht dazwischenkommen und den Lauf nachtraeglich `FAILED` schreiben."""
    project = await _project(db_session)
    run = ScanRun(project_id=project.id, status=ScanStatus.RUNNING)
    db_session.add(run)
    await db_session.commit()

    statements: list[str] = []

    def record(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    engine = db_session.bind.sync_engine  # type: ignore[union-attr]
    event.listen(engine, "before_cursor_execute", record)
    try:
        await finish_cancelled(db_session, run)
    finally:
        event.remove(engine, "before_cursor_execute", record)

    updates = [s for s in statements if s.lstrip().upper().startswith("UPDATE SCAN_RUNS")]
    assert len(updates) == 1, updates
    (statement,) = updates
    where = statement.split(" WHERE ", 1)[1]
    assert "status IN" in where
    assert "error_message" in statement
    assert "finished_at" in statement
    # `phase` bleibt unberuehrt: der Teilschritt gehoert dem abgebrochenen Lauf.
    assert "phase" not in statement


async def test_a_second_completion_never_turns_cancelled_into_failed(
    db_session: AsyncSession,
) -> None:
    """Zwei Abschluesse derselben Zeile: der erste gewinnt. Der zweite - hier der bedingte
    Endzustand des Watchdogs - trifft keine Zeile mehr, weil `cancelled` kein aktiver Zustand
    ist."""
    project = await _project(db_session)
    run = ScanRun(project_id=project.id, status=ScanStatus.RUNNING)
    db_session.add(run)
    await db_session.commit()

    await finish_cancelled(db_session, run)
    finished_at = run.finished_at

    await finish_cancelled(db_session, run)
    await db_session.execute(
        update(ScanRun)
        .where(ScanRun.id == run.id, ScanRun.status.in_((ScanStatus.QUEUED, ScanStatus.RUNNING)))
        .values(status=ScanStatus.FAILED, error_message="Lauf haengt")
    )
    await db_session.commit()
    await db_session.refresh(run)

    assert run.status == ScanStatus.CANCELLED
    assert run.error_message is None
    assert run.finished_at == finished_at


@pytest.mark.parametrize("model", [ScanRun, ScoringRun, RemoteCategoryClassificationRun])
async def test_fail_run_with_a_requested_cancel_ends_cancelled(
    db_session: AsyncSession, model: type
) -> None:
    project = await _project(db_session)
    run = model(project_id=project.id, status=ScanStatus.RUNNING)
    db_session.add(run)
    await db_session.commit()
    await _request_cancel_from_another_session(db_session, run)

    await fail_run(db_session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown).")

    assert run.status == ScanStatus.CANCELLED
    assert run.error_message is None


async def test_fail_run_without_a_cancel_still_fails(db_session: AsyncSession) -> None:
    project = await _project(db_session)
    run = await _criterion_run(db_session, project)

    await fail_run(db_session, run, "boom")

    assert run.status == ScanStatus.FAILED
    assert run.error_message == "boom"
    assert run.phase is None


async def test_fail_run_keeps_the_phase_of_a_cancelled_classification(
    db_session: AsyncSession,
) -> None:
    project = await _project(db_session)
    run = await _criterion_run(db_session, project)
    await _request_cancel_from_another_session(db_session, run)

    await fail_run(db_session, run, "boom")

    assert run.status == ScanStatus.CANCELLED
    assert run.phase == ClassificationPhase.CRITERIA


async def test_fail_export_run_with_a_requested_cancel_ends_cancelled(
    db_session: AsyncSession,
) -> None:
    project = await _project(db_session)
    run = ExportRun(project_id=project.id, status=ExportRunStatus.RUNNING)
    db_session.add(run)
    await db_session.commit()
    await _request_cancel_from_another_session(db_session, run)

    await fail_export_run(db_session, run, "boom")

    assert run.status == ExportRunStatus.CANCELLED
    assert run.error_message is None


async def test_the_review_fail_path_with_a_requested_cancel_ends_cancelled(
    db_session: AsyncSession,
) -> None:
    project = await _project(db_session)
    user = await get_or_create_user(db_session)
    review = ClassificationReview(
        project_id=project.id,
        created_by_user_id=user.id,
        status=ScanStatus.RUNNING,
        phase=ReviewPhase.SIDE_B,
        sample_size=10,
        seed=1,
    )
    db_session.add(review)
    await db_session.commit()
    await _request_cancel_from_another_session(db_session, review)

    await classification_review.fail_review(
        db_session, review, classification_review.ERROR_CANCELLED
    )

    assert review.status == ScanStatus.CANCELLED
    assert review.error_message is None
    assert review.phase == ReviewPhase.SIDE_B
