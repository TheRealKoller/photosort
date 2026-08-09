from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from photosort import worker
from photosort.models import Project, ScanRun, ScanStatus


async def _make_project(session: AsyncSession) -> Project:
    project = Project(name="Costa Rica", opencloud_drive_id="drive-1", opencloud_path="CostaRica")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def test_fail_run_result_is_immediately_readable_without_a_fresh_query(
    db_session: AsyncSession,
) -> None:
    """Copilot-Review-Fund (PR #67): _fail_run rief bisher nur session.rollback() gefolgt von
    session.commit() auf, ohne den Run danach zu refreshen. session.rollback() expired alle
    Objekte der Session (siehe Kommentare in den *_marked_failed_on_cancelled_error-Tests in
    test_worker_scan_project.py/test_worker_score_project.py/test_worker_top_selection.py) - ein
    direkter Attributzugriff DANACH (z.B. run.id in scan_project/score_project/select_top_photos,
    die den Rueckgabewert von run_project_scan/run_project_scoring/run_top_selection unmittelbar
    weiterverwenden) wuerde dadurch einen impliziten Lazy-Load ausserhalb eines aktiven
    greenlet-Kontexts ausloesen und mit sqlalchemy.exc.MissingGreenlet fehlschlagen -
    session.refresh(run) am Ende von _fail_run behebt das zuverlaessig."""
    project = await _make_project(db_session)
    scan_run = ScanRun(project_id=project.id, status=ScanStatus.RUNNING)
    db_session.add(scan_run)
    await db_session.commit()
    await db_session.refresh(scan_run)

    await worker._fail_run(db_session, scan_run, "boom")

    # Bewusst OHNE weiteren await/DB-Roundtrip zwischen dem _fail_run-Aufruf und dem
    # Attributzugriff - genau das Muster, das scan_project/score_project/select_top_photos nach
    # run_project_scan/run_project_scoring/run_top_selection anwenden (sofortiges `run.id`).
    assert scan_run.id is not None
    assert scan_run.status == ScanStatus.FAILED
    assert scan_run.error_message == "boom"
