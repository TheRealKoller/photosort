from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_job_enqueuer, get_opencloud_client
from photosort.config import settings
from photosort.main import app
from photosort.models import CriterionScoringRun, ScanStatus, ScoringRun
from photosort.opencloud.client import Drive, OpenCloudError
from photosort.opencloud.webdav_xml import DavEntry


class FakeOpenCloudClient:
    def __init__(self, fail: OpenCloudError | None = None) -> None:
        self._fail = fail

    async def resolve_drive(self, name: str | None) -> Drive:
        if self._fail:
            raise self._fail
        return Drive(id="drive-1", name="Family", drive_type="project", webdav_url="https://x/dav/spaces/drive-1")

    async def list_folder(self, webdav_url: str, path: str, depth: str = "1") -> list[DavEntry]:
        if self._fail:
            raise self._fail
        return []


class FakeEnqueuer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, function: str, *args: Any) -> None:
        self.calls.append((function, args))


async def _create_project(client: httpx.AsyncClient) -> int:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await client.post("/projects", json={"name": "Costa Rica", "opencloud_path": "A"})
    result: int = created.json()["id"]
    return result


async def _add_successful_scoring_run(
    session: AsyncSession,
    project_id: int,
    *,
    suggestions_found: int = 1,
    started_at: datetime | None = None,
) -> ScoringRun:
    run = ScoringRun(
        project_id=project_id, status=ScanStatus.SUCCESS, suggestions_found=suggestions_found
    )
    if started_at is not None:
        run.started_at = started_at
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


class TestConfirmAusschussGate:
    async def test_requires_auth(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post("/projects/1/confirm-ausschuss-gate")
        assert response.status_code == 401

    async def test_returns_404_for_unknown_project(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.post("/projects/999/confirm-ausschuss-gate")
        assert response.status_code == 404

    async def test_returns_409_without_a_successful_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )

        assert response.status_code == 409

    async def test_confirms_the_gate(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, project_id)

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )

        assert response.status_code == 200
        detail = await authenticated_api_client.get(f"/projects/{project_id}")
        assert detail.json()["last_scoring_run"]["gate_confirmed_at"] is not None

    async def test_is_idempotent(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_successful_scoring_run(db_session, project_id)

        first = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )
        first_detail = await authenticated_api_client.get(f"/projects/{project_id}")
        first_timestamp = first_detail.json()["last_scoring_run"]["gate_confirmed_at"]

        second = await authenticated_api_client.post(
            f"/projects/{project_id}/confirm-ausschuss-gate"
        )
        second_detail = await authenticated_api_client.get(f"/projects/{project_id}")

        assert first.status_code == 200
        assert second.status_code == 200
        assert second_detail.json()["last_scoring_run"]["gate_confirmed_at"] == first_timestamp


class TestScoreCriteria:
    async def test_requires_auth(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post(
            "/projects/1/score-criteria", json={"scoring_run_id": 1}
        )
        assert response.status_code == 401

    async def test_returns_404_for_unknown_project(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            "/projects/999/score-criteria", json={"scoring_run_id": 1}
        )

        assert response.status_code == 404

    async def test_returns_403_when_feature_flag_disabled(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "category_selection_enabled", False)
        project_id = await _create_project(authenticated_api_client)
        run = await _add_successful_scoring_run(db_session, project_id, suggestions_found=0)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/score-criteria", json={"scoring_run_id": run.id}
        )

        assert response.status_code == 403

    async def test_returns_409_without_a_successful_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/score-criteria", json={"scoring_run_id": 1}
        )

        assert response.status_code == 409

    async def test_returns_409_without_a_confirmed_gate(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        run = await _add_successful_scoring_run(db_session, project_id, suggestions_found=1)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/score-criteria", json={"scoring_run_id": run.id}
        )

        assert response.status_code == 409

    async def test_returns_409_for_a_stale_scoring_run_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        stale_run = await _add_successful_scoring_run(
            db_session,
            project_id,
            suggestions_found=0,
            started_at=datetime(2023, 1, 1, tzinfo=UTC).replace(tzinfo=None),
        )
        await authenticated_api_client.post(f"/projects/{project_id}/confirm-ausschuss-gate")
        # Re-Scan/Re-Scoring waehrend der Kuratierung -> neuer erfolgreicher ScoringRun.
        await _add_successful_scoring_run(
            db_session,
            project_id,
            suggestions_found=0,
            started_at=datetime(2023, 1, 2, tzinfo=UTC).replace(tzinfo=None),
        )
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/score-criteria", json={"scoring_run_id": stale_run.id}
        )

        assert response.status_code == 409

    async def test_enqueues_job_when_gate_confirmed(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        run = await _add_successful_scoring_run(db_session, project_id, suggestions_found=0)
        await authenticated_api_client.post(f"/projects/{project_id}/confirm-ausschuss-gate")
        fake_enqueuer = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/score-criteria", json={"scoring_run_id": run.id}
        )

        assert response.status_code == 202
        assert fake_enqueuer.calls == [("score_criteria", (project_id, run.id))]

    async def test_auto_confirmed_gate_allows_the_request(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Leerer Ausschuss (suggestions_found=0) -> Gate laut Worker automatisch bestaetigt, kein
        # expliziter confirm-ausschuss-gate-Aufruf noetig, um score-criteria zu starten.
        project_id = await _create_project(authenticated_api_client)
        scoring_run = ScoringRun(
            project_id=project_id,
            status=ScanStatus.SUCCESS,
            suggestions_found=0,
        )
        db_session.add(scoring_run)
        await db_session.flush()
        scoring_run.gate_confirmed_at = datetime.now(UTC).replace(tzinfo=None)
        await db_session.commit()
        await db_session.refresh(scoring_run)
        fake_enqueuer = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/score-criteria", json={"scoring_run_id": scoring_run.id}
        )

        assert response.status_code == 202


class TestProjectOutCriterionScoringRun:
    async def test_has_no_last_criterion_scoring_run_before_any_score_criteria_call(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)

        detail = await authenticated_api_client.get(f"/projects/{project_id}")

        assert detail.json()["last_criterion_scoring_run"] is None

    async def test_reports_last_criterion_scoring_run_progress(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        scoring_run = await _add_successful_scoring_run(db_session, project_id)
        run = CriterionScoringRun(
            project_id=project_id,
            scoring_run_id=scoring_run.id,
            status=ScanStatus.RUNNING,
            photos_total=10,
            photos_processed=4,
        )
        db_session.add(run)
        await db_session.commit()

        detail = await authenticated_api_client.get(f"/projects/{project_id}")

        last_run = detail.json()["last_criterion_scoring_run"]
        assert last_run["status"] == "running"
        assert last_run["photos_total"] == 10
        assert last_run["photos_processed"] == 4
