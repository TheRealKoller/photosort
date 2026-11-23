"""Kooperativer Abbruch des Scans: Uebernahme des wartenden Laufs und Pruefpunkte je Block.

Der Abbruch wird nie ueber Zeit ausgeloest, sondern ueber einen Haken im Fake-Client: nach dem
n-ten Download setzt eine ZWEITE Session den Merker - wie die API es tut.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import worker
from photosort.db import make_session_factory
from photosort.models import Photo, ScanRun, ScanStatus
from photosort.opencloud.webdav_xml import DavEntry
from photosort.worker import run_project_scan
from photosort.worker import scan as worker_scan
from tests.support import FakeOpenCloudClient, scan_entry
from tests.support import make_project as _project

MODIFIED = datetime(2023, 8, 15, 10, 0, tzinfo=UTC)


def _entries(count: int) -> list[tuple[str, DavEntry]]:
    return [
        (f"CostaRica/img{i:03}.png", scan_entry(f"img{i:03}.png", f"etag-{i}", MODIFIED))
        for i in range(count)
    ]


def _cancelling_client(session: AsyncSession, count: int, after: int) -> FakeOpenCloudClient:
    factory = make_session_factory(session.bind)

    async def on_download(relative_path: str) -> None:
        if len(client.download_requests) == after:
            async with factory() as other:
                await other.execute(
                    update(ScanRun).values(cancel_requested_at=datetime(2030, 1, 1))
                )
                await other.commit()

    client = FakeOpenCloudClient(entries=_entries(count), on_download=on_download)
    return client


async def test_a_cancel_finishes_the_running_block_and_starts_no_further_one(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "scan_download_concurrency", 2)
    project = await _project(db_session)
    client = _cancelling_client(db_session, count=6, after=1)

    scan_run = await run_project_scan(db_session, client, project, None, cache_dir=tmp_path)

    assert scan_run.status == ScanStatus.CANCELLED
    assert scan_run.error_message is None
    # Der laufende Block (2 Fotos) wird fertig, danach kein Download mehr.
    assert len(client.download_requests) == 2
    assert scan_run.files_found == 2
    assert scan_run.total_files == 6
    photos = (await db_session.execute(select(Photo))).scalars().all()
    assert len(photos) == 2


async def test_a_cancelled_scan_removes_no_vanished_photos_and_cleans_no_cache(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "scan_download_concurrency", 1)
    project = await _project(db_session)
    db_session.add(
        Photo(
            project_id=project.id,
            relative_path="CostaRica/gone.jpg",
            etag="etag",
            content_length=10,
            taken_at=MODIFIED,
            taken_at_original=MODIFIED,
            last_modified=MODIFIED,
        )
    )
    await db_session.commit()
    cleanups: list[Path] = []

    async def _recording_cleanup(session: AsyncSession, cache_dir: Path) -> None:
        cleanups.append(cache_dir)

    monkeypatch.setattr(worker_scan, "cleanup_orphaned_cache", _recording_cleanup)
    client = _cancelling_client(db_session, count=3, after=1)

    scan_run = await run_project_scan(db_session, client, project, None, cache_dir=tmp_path)

    assert scan_run.status == ScanStatus.CANCELLED
    assert scan_run.photos_removed == 0
    paths = {p.relative_path for p in (await db_session.execute(select(Photo))).scalars()}
    assert "CostaRica/gone.jpg" in paths
    assert cleanups == []


async def test_a_queued_scan_is_taken_over(db_session: AsyncSession, tmp_path: Path) -> None:
    project = await _project(db_session)
    queued = ScanRun(project_id=project.id, status=ScanStatus.QUEUED)
    db_session.add(queued)
    await db_session.commit()

    scan_run = await run_project_scan(
        db_session,
        FakeOpenCloudClient(entries=_entries(1)),
        project,
        None,
        tmp_path,
        run_id=queued.id,
    )

    assert scan_run is not None
    assert scan_run.id == queued.id
    assert scan_run.status == ScanStatus.SUCCESS
    assert len((await db_session.execute(select(ScanRun))).scalars().all()) == 1


async def test_a_scan_cancelled_while_waiting_does_no_work(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _project(db_session)
    queued = ScanRun(
        project_id=project.id,
        status=ScanStatus.CANCELLED,
        cancel_requested_at=datetime(2030, 1, 1),
    )
    db_session.add(queued)
    await db_session.commit()
    client = FakeOpenCloudClient(entries=_entries(2))

    result = await run_project_scan(db_session, client, project, None, tmp_path, run_id=queued.id)

    assert result is None
    assert client.download_requests == []
    await db_session.refresh(queued)
    assert queued.status == ScanStatus.CANCELLED
