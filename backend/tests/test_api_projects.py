from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_job_enqueuer, get_opencloud_client
from photosort.main import app
from photosort.models import ScanStatus, ScoringRun
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


async def test_create_project(authenticated_api_client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()

    response = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "CostaRica"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Costa Rica"
    assert body["opencloud_drive_id"] == "drive-1"
    assert body["last_scan"] is None


async def test_create_project_rejects_invalid_folder(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient(
        fail=OpenCloudError("Ordner nicht gefunden")
    )

    response = await authenticated_api_client.post(
        "/projects", json={"name": "X", "opencloud_path": "Nope"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Ordner nicht gefunden"


async def test_create_project_rejects_duplicate_name(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()

    first = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    assert first.status_code == 201

    second = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "B"}
    )
    assert second.status_code == 409


async def test_list_and_get_project(authenticated_api_client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    project_id = created.json()["id"]

    listing = await authenticated_api_client.get("/projects")
    assert len(listing.json()) == 1

    detail = await authenticated_api_client.get(f"/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == project_id


async def test_get_project_returns_404_for_unknown_id(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.get("/projects/999")

    assert response.status_code == 404


async def test_trigger_scan_enqueues_job(authenticated_api_client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    project_id = created.json()["id"]

    fake_enqueuer = FakeEnqueuer()
    app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

    response = await authenticated_api_client.post(f"/projects/{project_id}/scan")

    assert response.status_code == 202
    assert fake_enqueuer.calls == [("scan_project", (project_id,))]


async def test_trigger_scan_returns_404_for_unknown_project(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    fake_enqueuer = FakeEnqueuer()
    app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

    response = await authenticated_api_client.post("/projects/999/scan")

    assert response.status_code == 404
    assert fake_enqueuer.calls == []


async def test_get_project_has_no_last_scoring_run_before_any_score_call(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )

    assert created.json()["last_scoring_run"] is None


async def test_trigger_score_enqueues_job(authenticated_api_client: httpx.AsyncClient) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    project_id = created.json()["id"]

    fake_enqueuer = FakeEnqueuer()
    app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

    response = await authenticated_api_client.post(f"/projects/{project_id}/score")

    assert response.status_code == 202
    assert fake_enqueuer.calls == [("score_project", (project_id,))]


async def test_trigger_score_returns_404_for_unknown_project(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    fake_enqueuer = FakeEnqueuer()
    app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

    response = await authenticated_api_client.post("/projects/999/score")

    assert response.status_code == 404
    assert fake_enqueuer.calls == []


async def test_trigger_score_requires_auth(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/projects/1/score")

    assert response.status_code == 401


async def test_get_project_reports_last_scoring_run_progress(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    project_id = created.json()["id"]

    scoring_run = ScoringRun(
        project_id=project_id,
        status=ScanStatus.RUNNING,
        photos_total=10,
        photos_processed=4,
    )
    db_session.add(scoring_run)
    await db_session.commit()

    detail = await authenticated_api_client.get(f"/projects/{project_id}")

    assert detail.status_code == 200
    last_scoring_run = detail.json()["last_scoring_run"]
    assert last_scoring_run["status"] == "running"
    assert last_scoring_run["photos_total"] == 10
    assert last_scoring_run["photos_processed"] == 4
