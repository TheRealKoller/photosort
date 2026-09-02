from __future__ import annotations

import logging
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import worker
from photosort.models import Photo, Project, ScanRun, ScanStatus


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


# Review-Fund (ship-feature-Runde zu Spec 0207): derselbe Gedanke wie bei _fail_run oben, eine
# Ebene frueher. Die Ist-Kosten beider Cloud-Phasen werden in einem `finally`-Block committet,
# also auch waehrend eine Exception nach oben laeuft. Scheitert genau dieses Commit, wuerde seine
# eigene Exception die urspruengliche ERSETZEN - und der eigentliche Fehlergrund waere weder im
# Log noch in `run.error_message` erkennbar. Das ist real erreichbar: nach einem fehlgeschlagenen
# `flush()` (z.B. IntegrityError im Klassifizierungs-Block) wirft `commit()` einen
# PendingRollbackError.


async def _put_session_into_failed_transaction_state(session: AsyncSession) -> None:
    """Erzeugt genau den Zustand, in dem `commit()` mit PendingRollbackError scheitert: ein
    fehlgeschlagener `flush()` durch eine verletzte Unique-Bedingung."""
    project = await _make_project(session)
    now = datetime(2023, 1, 1)
    for _ in range(2):
        session.add(
            Photo(
                project_id=project.id,
                relative_path="a.jpg",
                etag="etag-1",
                content_length=1,
                taken_at=now,
                last_modified=now,
            )
        )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_commit_phase_costs_never_replaces_the_original_exception(
    db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    await _put_session_into_failed_transaction_state(db_session)

    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        await worker._commit_phase_costs(db_session)

    assert len(caplog.records) == 1
    assert "PendingRollbackError" in caplog.records[0].getMessage()


async def test_commit_phase_costs_leaves_the_session_usable(db_session: AsyncSession) -> None:
    """Nach dem gescheiterten Commit muss `_fail_run` noch arbeiten koennen - es setzt den Lauf
    auf FAILED und committet erneut."""
    await _put_session_into_failed_transaction_state(db_session)

    await worker._commit_phase_costs(db_session)

    # Frisch gelesen statt ueber das (durch das Rollback expirte) Objekt von oben - ein lesender
    # Attributzugriff darauf loeste sonst einen Lazy-Load ausserhalb des greenlet-Kontexts aus.
    project = (await db_session.execute(select(Project))).scalars().one()
    run = ScanRun(project_id=project.id, status=ScanStatus.RUNNING)
    db_session.add(run)
    # Wie im Produktivpfad: die Lauf-Zeile ist laengst committet, bevor die Cloud-Phase startet -
    # _fail_run beginnt mit einem rollback() und braucht eine persistente Zeile.
    await db_session.commit()

    await worker._fail_run(db_session, run, "urspruenglicher Fehler")

    assert run.status == ScanStatus.FAILED
    assert run.error_message == "urspruenglicher Fehler"


async def test_commit_phase_costs_commits_normally_when_nothing_is_wrong(
    db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    project = await _make_project(db_session)
    run = ScanRun(project_id=project.id, status=ScanStatus.RUNNING, files_skipped=7)
    db_session.add(run)

    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        await worker._commit_phase_costs(db_session)

    assert caplog.records == []
    stored = (
        await db_session.execute(select(ScanRun).where(ScanRun.project_id == project.id))
    ).scalar_one()
    assert stored.files_skipped == 7


# Copilot-Review-Fund (PR #311): auch das `rollback()` im except-Zweig war ungeschuetzt. Wirft es
# selbst - Verbindungsabbruch, InterfaceError, also genau die Lage, in der schon das commit()
# gescheitert ist -, verliesse diese Exception den Helfer und ersetzte die urspruengliche im
# umgebenden `finally`. Damit waere exakt die Maskierung zurueck, gegen die der Helfer gebaut
# wurde, nur eine Ebene tiefer.


class _SessionWithBrokenConnection:
    """Minimaler Stub statt einer echten Session: der Zustand "auch das Rollback scheitert" ist
    mit einer echten SQLite-Session nicht herstellbar (er entsteht erst bei einer abgerissenen
    Verbindung zu einem echten Server)."""

    def __init__(self, *, rollback_fails: bool = True) -> None:
        self.commit_calls = 0
        self.rollback_calls = 0
        self._rollback_fails = rollback_fails

    async def commit(self) -> None:
        self.commit_calls += 1
        raise OperationalError("COMMIT", {}, Exception("Verbindung abgerissen"))

    async def rollback(self) -> None:
        self.rollback_calls += 1
        if self._rollback_fails:
            raise InterfaceError("ROLLBACK", {}, Exception("Verbindung abgerissen"))


async def test_commit_phase_costs_swallows_a_failing_rollback_too(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = _SessionWithBrokenConnection()

    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        await worker._commit_phase_costs(session)  # type: ignore[arg-type]

    assert session.commit_calls == 1
    assert session.rollback_calls == 1
    # Zwei Zeilen: der gescheiterte Commit und das ebenfalls gescheiterte Aufraeumen - beides
    # bleibt sichtbar, nur eben im Log statt als Exception.
    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 2
    assert any("OperationalError" in message for message in messages)
    assert any("InterfaceError" in message for message in messages)


async def test_an_original_exception_survives_a_completely_broken_session() -> None:
    """Die eigentliche Zusage des Helfers, im echten Aufrufkontext geprueft: er steht in einem
    `finally`, waehrend eine Exception nach oben laeuft - und darf sie unter keinen Umstaenden
    ersetzen."""
    session = _SessionWithBrokenConnection()

    with pytest.raises(RuntimeError, match="urspruenglicher Fehler"):
        try:
            raise RuntimeError("urspruenglicher Fehler")
        finally:
            await worker._commit_phase_costs(session)  # type: ignore[arg-type]
