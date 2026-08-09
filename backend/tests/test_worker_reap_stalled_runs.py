from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker as worker_module
from photosort.db import make_session_factory
from photosort.models import Project, ScanRun, ScanStatus, ScoringRun, TopSelectionRun
from photosort.worker import reap_stalled_runs

# Fortschritts-Watchdog (specs/features/0034-scan-haenger-fortschritts-watchdog.md, ADR 0019),
# Schicht 2: reap_stalled_runs braucht keinen echten arq-Scheduler/Redis - wird als gewoehnliche
# Coroutine direkt aufgerufen (Teststrategie-Abschnitt der Spec), mit einer an die
# In-Memory-SQLite-Testdatenbank gebundenen session_factory statt der produktiven
# async_session_factory (analog zu run_top_selection's build_detector-Parameter).

_SENTINEL_NOW = datetime(2030, 1, 1, 12, 0, 0)


@pytest.fixture(autouse=True)
def _freeze_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker_module, "_now_utc", lambda: _SENTINEL_NOW)


async def _make_project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id="drive-1", opencloud_path="CostaRica")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def test_reaps_scan_run_stalled_beyond_threshold(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    stalled = ScanRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    db_session.add(stalled)
    await db_session.commit()
    await db_session.refresh(stalled)

    session_factory = make_session_factory(db_session.bind)
    reaped = await reap_stalled_runs({}, session_factory=session_factory)

    assert reaped == 1
    await db_session.refresh(stalled)
    assert stalled.status == ScanStatus.FAILED
    assert stalled.error_message
    assert "15 Minuten" in stalled.error_message


async def test_stall_message_reflects_the_configured_threshold(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Copilot-Review-Fund (PR #67): die Fehlermeldung leitet die genannte Minutenzahl aus
    STALL_THRESHOLD ab statt sie hart zu codieren - passt sich also automatisch an, statt bei
    einer kuenftigen Anpassung von STALL_THRESHOLD unbemerkt auseinanderzudriften."""
    monkeypatch.setattr(worker_module, "STALL_THRESHOLD", timedelta(minutes=30))
    project = await _make_project(db_session)
    stalled = ScanRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=45),
    )
    db_session.add(stalled)
    await db_session.commit()

    session_factory = make_session_factory(db_session.bind)
    await reap_stalled_runs({}, session_factory=session_factory)

    await db_session.refresh(stalled)
    assert stalled.error_message
    assert "30 Minuten" in stalled.error_message
    assert "15 Minuten" not in stalled.error_message


async def test_does_not_reap_scan_run_within_threshold(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    active = ScanRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=5),
    )
    db_session.add(active)
    await db_session.commit()
    await db_session.refresh(active)

    session_factory = make_session_factory(db_session.bind)
    reaped = await reap_stalled_runs({}, session_factory=session_factory)

    assert reaped == 0
    await db_session.refresh(active)
    assert active.status == ScanStatus.RUNNING


async def test_does_not_reap_scan_run_exactly_at_threshold_boundary(
    db_session: AsyncSession,
) -> None:
    """Akzeptanzkriterium der Spec: last_progress_at genau 15:00 alt zaehlt NICHT als stalled -
    nur STRIKT aelter."""
    project = await _make_project(db_session)
    boundary = ScanRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=15),
    )
    db_session.add(boundary)
    await db_session.commit()
    await db_session.refresh(boundary)

    session_factory = make_session_factory(db_session.bind)
    reaped = await reap_stalled_runs({}, session_factory=session_factory)

    assert reaped == 0
    await db_session.refresh(boundary)
    assert boundary.status == ScanStatus.RUNNING


async def test_reaps_stalled_scoring_run(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    stalled = ScoringRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    db_session.add(stalled)
    await db_session.commit()
    await db_session.refresh(stalled)

    session_factory = make_session_factory(db_session.bind)
    reaped = await reap_stalled_runs({}, session_factory=session_factory)

    assert reaped == 1
    await db_session.refresh(stalled)
    assert stalled.status == ScanStatus.FAILED


async def test_reaps_stalled_top_selection_run(db_session: AsyncSession) -> None:
    project = await _make_project(db_session)
    stalled = TopSelectionRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        top_n_per_cluster=3,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    db_session.add(stalled)
    await db_session.commit()
    await db_session.refresh(stalled)

    session_factory = make_session_factory(db_session.bind)
    reaped = await reap_stalled_runs({}, session_factory=session_factory)

    assert reaped == 1
    await db_session.refresh(stalled)
    assert stalled.status == ScanStatus.FAILED


async def test_reaps_stalled_runs_of_different_types_independently(
    db_session: AsyncSession,
) -> None:
    """Akzeptanzkriterium der Spec: reap_stalled_runs behandelt alle drei Tabellen unabhaengig
    voneinander."""
    project = await _make_project(db_session)
    stalled_scan = ScanRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    stalled_scoring = ScoringRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    stalled_top_selection = TopSelectionRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        top_n_per_cluster=3,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    db_session.add_all([stalled_scan, stalled_scoring, stalled_top_selection])
    await db_session.commit()

    session_factory = make_session_factory(db_session.bind)
    reaped = await reap_stalled_runs({}, session_factory=session_factory)

    assert reaped == 3
    for run in (stalled_scan, stalled_scoring, stalled_top_selection):
        await db_session.refresh(run)
        assert run.status == ScanStatus.FAILED


async def test_does_not_touch_a_run_already_failed_via_layer_one(db_session: AsyncSession) -> None:
    """Ein Lauf, der zwischen zwei Cron-Ticks bereits ueber Schicht 1 (Exception-Pfad) auf FAILED
    gesetzt wurde, wird vom naechsten reap_stalled_runs-Tick nicht erneut angefasst (Query filtert
    auf status=RUNNING)."""
    project = await _make_project(db_session)
    already_failed = ScanRun(
        project_id=project.id,
        status=ScanStatus.FAILED,
        error_message="Lauf abgebrochen (Job-Timeout oder Worker-Shutdown).",
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    db_session.add(already_failed)
    await db_session.commit()
    await db_session.refresh(already_failed)
    original_error_message = already_failed.error_message

    session_factory = make_session_factory(db_session.bind)
    reaped = await reap_stalled_runs({}, session_factory=session_factory)

    assert reaped == 0
    await db_session.refresh(already_failed)
    assert already_failed.error_message == original_error_message


async def test_error_reaping_one_run_does_not_block_others(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Akzeptanzkriterium der Spec: ein Fehler bei einer Zeile blockiert die Bereinigung der
    uebrigen nicht."""
    project = await _make_project(db_session)
    stalled_a = ScanRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    stalled_b = ScanRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    db_session.add_all([stalled_a, stalled_b])
    await db_session.commit()

    original_fail_run = worker_module._fail_run
    call_count = {"n": 0}

    async def flaky_fail_run(session: AsyncSession, run: object, message: str) -> None:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated failure reaping one row")
        await original_fail_run(session, run, message)  # type: ignore[arg-type]

    monkeypatch.setattr(worker_module, "_fail_run", flaky_fail_run)

    session_factory = make_session_factory(db_session.bind)
    reaped = await reap_stalled_runs({}, session_factory=session_factory)

    assert reaped == 1
    # db_session haelt stalled_a/stalled_b bereits im Identity-Map-Cache (aus dem add_all/commit
    # oben) - ein erneutes select() auf DERSELBEN Session wuerde diese gecachten (veralteten)
    # Python-Objekte zurueckgeben, nicht den frischen, von der ANDEREN Session (reap_stalled_runs)
    # committeten Zustand widerspiegeln. Explizites refresh() erzwingt den echten Roundtrip -
    # analog zum bereits etablierten Testmuster in test_worker_scan_project.py
    # (test_scan_commits_files_found_progress_before_final_commit_at_production_batch_size).
    await db_session.refresh(stalled_a)
    await db_session.refresh(stalled_b)
    assert sorted([stalled_a.status, stalled_b.status]) == sorted(
        [ScanStatus.RUNNING, ScanStatus.FAILED]
    )


async def test_error_selecting_one_table_does_not_block_others(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Akzeptanzkriterium der Spec: ein Fehler bei einer TABELLE (nicht nur bei einer einzelnen
    Zeile) blockiert die Bereinigung der uebrigen nicht - hier schlaegt bereits das SELECT fuer
    ScanRun fehl, ScoringRun wird trotzdem bereinigt."""
    project = await _make_project(db_session)
    stalled_scan = ScanRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    stalled_scoring = ScoringRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    db_session.add_all([stalled_scan, stalled_scoring])
    await db_session.commit()

    original_execute = AsyncSession.execute

    async def flaky_execute(self: AsyncSession, statement: object, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if "scan_runs" in str(statement):
            raise RuntimeError("simulated table-level failure")
        return await original_execute(self, statement, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(AsyncSession, "execute", flaky_execute)

    session_factory = make_session_factory(db_session.bind)
    reaped = await reap_stalled_runs({}, session_factory=session_factory)

    monkeypatch.undo()  # nicht laenger patchen, bevor db_session fuer die Assertions genutzt wird

    assert reaped == 1
    await db_session.refresh(stalled_scan)
    await db_session.refresh(stalled_scoring)
    assert stalled_scan.status == ScanStatus.RUNNING
    assert stalled_scoring.status == ScanStatus.FAILED


async def test_error_selecting_scoring_runs_does_not_block_the_other_tables(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pendant zu test_error_selecting_one_table_does_not_block_others fuer ScoringRun - deckt
    denselben (bewusst dreifach duplizierten, nicht generisch geloopten - ADR 0019) Code-Pfad fuer
    die zweite der drei Tabellen ab (test-engineer-Review-Fund, Spec 0034)."""
    project = await _make_project(db_session)
    stalled_scan = ScanRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    stalled_scoring = ScoringRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    stalled_top_selection = TopSelectionRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        top_n_per_cluster=3,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    db_session.add_all([stalled_scan, stalled_scoring, stalled_top_selection])
    await db_session.commit()

    original_execute = AsyncSession.execute

    async def flaky_execute(self: AsyncSession, statement: object, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if "scoring_runs" in str(statement):
            raise RuntimeError("simulated table-level failure")
        return await original_execute(self, statement, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(AsyncSession, "execute", flaky_execute)

    session_factory = make_session_factory(db_session.bind)
    reaped = await reap_stalled_runs({}, session_factory=session_factory)

    monkeypatch.undo()

    assert reaped == 2
    await db_session.refresh(stalled_scan)
    await db_session.refresh(stalled_scoring)
    await db_session.refresh(stalled_top_selection)
    assert stalled_scan.status == ScanStatus.FAILED
    assert stalled_scoring.status == ScanStatus.RUNNING
    assert stalled_top_selection.status == ScanStatus.FAILED


async def test_error_selecting_top_selection_runs_does_not_block_the_other_tables(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drittes Pendant, fuer TopSelectionRun - schliesst die Coverage-Luecke fuer alle drei
    (bewusst duplizierten) SELECT-except-Bloecke vollstaendig (test-engineer-Review-Fund, Spec
    0034)."""
    project = await _make_project(db_session)
    stalled_scan = ScanRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    stalled_top_selection = TopSelectionRun(
        project_id=project.id,
        status=ScanStatus.RUNNING,
        top_n_per_cluster=3,
        last_progress_at=_SENTINEL_NOW - timedelta(minutes=20),
    )
    db_session.add_all([stalled_scan, stalled_top_selection])
    await db_session.commit()

    original_execute = AsyncSession.execute

    async def flaky_execute(self: AsyncSession, statement: object, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if "top_selection_runs" in str(statement):
            raise RuntimeError("simulated table-level failure")
        return await original_execute(self, statement, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(AsyncSession, "execute", flaky_execute)

    session_factory = make_session_factory(db_session.bind)
    reaped = await reap_stalled_runs({}, session_factory=session_factory)

    monkeypatch.undo()

    assert reaped == 1
    await db_session.refresh(stalled_scan)
    await db_session.refresh(stalled_top_selection)
    assert stalled_scan.status == ScanStatus.FAILED
    assert stalled_top_selection.status == ScanStatus.RUNNING
