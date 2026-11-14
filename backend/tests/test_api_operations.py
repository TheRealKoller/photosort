"""Spec 0641: die Vorgangsuebersicht und der Abbruch laufender und wartender Laeufe."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_job_enqueuer
from photosort.main import app
from photosort.models import (
    ClassificationReview,
    CriterionScoringRun,
    ExportRun,
    ExportRunStatus,
    Project,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)

_NOW = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)


class FakeEnqueuer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.keywords: list[dict[str, Any]] = []

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((function, args))
        self.keywords.append(kwargs)


async def _project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id="drive-1", opencloud_path=f"/{name}")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _user(session: AsyncSession) -> User:
    user = User(username="pruefer", password_hash="x")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _add_run(session: AsyncSession, model: type[Any], **fields: Any) -> Any:
    fields.setdefault("last_progress_at", _NOW)
    run = model(**fields)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


def _url(project_id: int) -> str:
    return f"/projects/{project_id}/operations"


async def test_an_unknown_project_is_a_404(authenticated_api_client: httpx.AsyncClient) -> None:
    response = await authenticated_api_client.get(_url(999))
    assert response.status_code == 404


async def test_a_project_without_open_operations_lists_nothing(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    await _add_run(db_session, ScanRun, project_id=project.id, status=ScanStatus.SUCCESS)

    response = await authenticated_api_client.get(_url(project.id))

    assert response.status_code == 200
    assert response.json() == {"operations": []}


async def test_lists_the_newest_open_run_per_kind(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    waiting = await _add_run(db_session, ScanRun, project_id=project.id, status=ScanStatus.QUEUED)
    export = await _add_run(
        db_session, ExportRun, project_id=project.id, status=ExportRunStatus.RUNNING
    )
    await _add_run(db_session, ScoringRun, project_id=project.id, status=ScanStatus.SUCCESS)

    response = await authenticated_api_client.get(_url(project.id))

    assert response.status_code == 200
    assert response.json()["operations"] == [
        {
            "kind": "scan",
            "run_id": waiting.id,
            "label": "Scan",
            "status": "queued",
            "cancel_requested": False,
        },
        {
            "kind": "export",
            "run_id": export.id,
            "label": "Export",
            "status": "running",
            "cancel_requested": False,
        },
    ]


async def test_lists_all_open_reviews(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    user = await _user(db_session)
    for status in (ScanStatus.QUEUED, ScanStatus.RUNNING):
        await _add_run(
            db_session,
            ClassificationReview,
            project_id=project.id,
            created_by_user_id=user.id,
            status=status,
            sample_size=30,
            seed=4711,
        )

    response = await authenticated_api_client.get(_url(project.id))

    assert [entry["kind"] for entry in response.json()["operations"]] == ["review", "review"]


async def test_cancelling_a_waiting_run_ends_it_immediately(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    waiting = await _add_run(db_session, ScanRun, project_id=project.id, status=ScanStatus.QUEUED)

    response = await authenticated_api_client.post(f"{_url(project.id)}/scan/{waiting.id}/cancel")

    assert response.status_code == 200
    assert response.json() == {
        "kind": "scan",
        "run_id": waiting.id,
        "status": "cancelled",
        "outcome": "cancel_requested",
    }
    await db_session.refresh(waiting)
    assert waiting.status == ScanStatus.CANCELLED
    assert waiting.cancel_requested_at is not None
    assert waiting.finished_at is not None
    assert waiting.error_message is None


async def test_cancelling_a_running_run_sets_only_the_marker(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    running = await _add_run(
        db_session, ScoringRun, project_id=project.id, status=ScanStatus.RUNNING
    )

    response = await authenticated_api_client.post(
        f"{_url(project.id)}/ausschuss/{running.id}/cancel"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["outcome"] == "cancel_requested"
    await db_session.refresh(running)
    assert running.status == ScanStatus.RUNNING
    assert running.cancel_requested_at is not None
    assert running.finished_at is None


async def test_a_second_cancel_and_a_finished_run_are_already_finished(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    waiting = await _add_run(db_session, ScanRun, project_id=project.id, status=ScanStatus.QUEUED)
    finished = await _add_run(db_session, ScanRun, project_id=project.id, status=ScanStatus.SUCCESS)

    first = await authenticated_api_client.post(f"{_url(project.id)}/scan/{waiting.id}/cancel")
    second = await authenticated_api_client.post(f"{_url(project.id)}/scan/{waiting.id}/cancel")
    after_end = await authenticated_api_client.post(f"{_url(project.id)}/scan/{finished.id}/cancel")

    assert first.json()["outcome"] == "cancel_requested"
    assert second.status_code == 200
    assert second.json() == {
        "kind": "scan",
        "run_id": waiting.id,
        "status": "cancelled",
        "outcome": "already_finished",
    }
    assert after_end.status_code == 200
    assert after_end.json()["outcome"] == "already_finished"
    assert after_end.json()["status"] == "success"


async def test_an_unknown_run_and_a_foreign_run_are_a_404(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    mine = await _project(db_session)
    other = await _project(db_session, name="Panama")
    foreign = await _add_run(db_session, ScanRun, project_id=other.id, status=ScanStatus.RUNNING)

    unknown = await authenticated_api_client.post(f"{_url(mine.id)}/scan/999/cancel")
    cross_project = await authenticated_api_client.post(f"{_url(mine.id)}/scan/{foreign.id}/cancel")

    assert unknown.status_code == 404
    assert cross_project.status_code == 404
    await db_session.refresh(foreign)
    assert foreign.cancel_requested_at is None


async def test_cancelling_the_classification_marks_the_cloud_phase_too(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    scoring_run = await _add_run(
        db_session, ScoringRun, project_id=project.id, status=ScanStatus.SUCCESS
    )
    remote = await _add_run(
        db_session,
        RemoteCategoryClassificationRun,
        project_id=project.id,
        status=ScanStatus.RUNNING,
    )
    criterion = await _add_run(
        db_session,
        CriterionScoringRun,
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=ScanStatus.RUNNING,
        remote_category_classification_run_id=remote.id,
    )

    response = await authenticated_api_client.post(
        f"{_url(project.id)}/classification/{criterion.id}/cancel"
    )

    assert response.status_code == 200
    await db_session.refresh(criterion)
    await db_session.refresh(remote)
    assert criterion.cancel_requested_at is not None
    assert criterion.status == ScanStatus.RUNNING
    assert remote.cancel_requested_at is not None


async def test_cancel_all_cancels_every_open_operation_of_this_project(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    mine = await _project(db_session)
    other = await _project(db_session, name="Panama")
    waiting = await _add_run(db_session, ScanRun, project_id=mine.id, status=ScanStatus.QUEUED)
    export = await _add_run(
        db_session, ExportRun, project_id=mine.id, status=ExportRunStatus.RUNNING
    )
    foreign = await _add_run(db_session, ScanRun, project_id=other.id, status=ScanStatus.RUNNING)

    response = await authenticated_api_client.post(f"{_url(mine.id)}/cancel-all")

    assert response.status_code == 200
    assert {(entry["kind"], entry["run_id"]) for entry in response.json()["cancelled"]} == {
        ("scan", waiting.id),
        ("export", export.id),
    }
    await db_session.refresh(waiting)
    await db_session.refresh(export)
    await db_session.refresh(foreign)
    assert waiting.status == ScanStatus.CANCELLED
    assert export.cancel_requested_at is not None
    assert foreign.cancel_requested_at is None


async def test_cancel_all_without_open_operations_returns_an_empty_list(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)

    response = await authenticated_api_client.post(f"{_url(project.id)}/cancel-all")

    assert response.status_code == 200
    assert response.json() == {"cancelled": []}


async def test_the_scan_trigger_creates_the_waiting_row_and_names_it_to_the_job(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    fake = FakeEnqueuer()
    app.dependency_overrides[get_job_enqueuer] = lambda: fake

    response = await authenticated_api_client.post(f"/projects/{project.id}/scan")

    assert response.status_code == 202
    runs = (await db_session.execute(select(ScanRun))).scalars().all()
    assert [run.status for run in runs] == [ScanStatus.QUEUED]
    assert fake.calls == [("scan_project", (project.id,))]
    assert fake.keywords == [{"run_id": runs[0].id}]


async def test_the_export_trigger_without_a_selection_creates_no_run(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    fake = FakeEnqueuer()
    app.dependency_overrides[get_job_enqueuer] = lambda: fake

    response = await authenticated_api_client.post(f"/projects/{project.id}/export")

    assert response.status_code == 202
    assert response.json() == {"status": "queued"}
    assert (await db_session.execute(select(ExportRun))).scalars().all() == []
    assert fake.calls == []


async def test_a_waiting_run_blocks_deleting_the_project(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _project(db_session)
    await _add_run(db_session, ScanRun, project_id=project.id, status=ScanStatus.QUEUED)

    response = await authenticated_api_client.request(
        "DELETE", f"/projects/{project.id}", json={"confirm_name": project.name}
    )

    assert response.status_code == 409


@pytest.mark.parametrize("status", [ScanStatus.QUEUED, ScanStatus.CANCELLED])
async def test_a_waiting_classification_run_has_no_remaining_time(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, status: ScanStatus
) -> None:
    project = await _project(db_session)
    scoring_run = await _add_run(
        db_session, ScoringRun, project_id=project.id, status=ScanStatus.SUCCESS
    )
    await _add_run(
        db_session,
        CriterionScoringRun,
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=status,
        phase=None,
        photos_total=10,
        photos_processed=10,
    )

    response = await authenticated_api_client.get(f"/projects/{project.id}")

    summary = response.json()["last_criterion_scoring_run"]
    assert summary["status"] == status
    assert summary["phase_remaining_seconds"] is None


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("GET", "/projects/0/operations"),
        ("GET", f"/projects/{2**63}/operations"),
        ("POST", f"/projects/{2**63}/operations/cancel-all"),
        ("POST", f"/projects/{2**63}/operations/scan/1/cancel"),
    ],
)
async def test_the_path_ids_are_bounded_before_they_reach_the_database(
    authenticated_api_client: httpx.AsyncClient, method: str, url: str
) -> None:
    """Jenseits von 2^63 antwortete die Datenbank mit `500`; die Grenze steht deshalb deklarativ im
    Pfad, nicht als Pruefung im Rumpf."""
    response = await authenticated_api_client.request(method, url)

    assert response.status_code == 422


async def test_cancelling_in_an_unknown_project_is_a_404(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    response = await authenticated_api_client.post("/projects/999/operations/scan/1/cancel")

    assert response.status_code == 404
    assert response.json()["detail"] == "Projekt nicht gefunden."


async def test_the_cancel_log_names_the_project(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ankersatz S12: jede Abbruch-Zeile nennt Projekt, Art, Lauf und Ergebnis."""
    project = await _project(db_session)
    waiting = await _add_run(db_session, ScanRun, project_id=project.id, status=ScanStatus.QUEUED)

    with caplog.at_level(logging.INFO, logger="photosort.api.operations"):
        await authenticated_api_client.post(f"{_url(project.id)}/scan/{waiting.id}/cancel")

    line = next(
        record.getMessage() for record in caplog.records if "wartenden Laufs" in record.getMessage()
    )
    assert f"project_id={project.id}" in line
    assert "kind=scan" in line
    assert f"run_id={waiting.id}" in line
    assert "outcome=cancel_requested" in line
