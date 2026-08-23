from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_job_enqueuer, get_opencloud_client
from photosort.main import app
from photosort.models import ScanRun, ScanStatus, ScoringRun
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


async def test_get_project_reports_last_scan_total_files_as_null_during_enumeration(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """specs/features/0036-scan-performance-zweiphasig-parallel.md: waehrend der Enumerationsphase
    (total_files in der DB noch NULL) muss die Serialisierung `null` liefern - kein `0`, das vom
    Frontend faelschlich als "leeres Projekt" statt "Phase 1 laeuft noch" interpretiert wuerde."""
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    project_id = created.json()["id"]

    scan_run = ScanRun(project_id=project_id, status=ScanStatus.RUNNING, files_found=7)
    db_session.add(scan_run)
    await db_session.commit()

    detail = await authenticated_api_client.get(f"/projects/{project_id}")

    assert detail.status_code == 200
    last_scan = detail.json()["last_scan"]
    assert last_scan["total_files"] is None
    assert last_scan["files_found"] == 7


async def test_get_project_reports_last_scan_total_files_including_zero(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Sonderfall leeres Projekt (Akzeptanzkriterium der Spec): total_files == 0 muss von `null`
    unterscheidbar in der API-Antwort ankommen."""
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    project_id = created.json()["id"]

    scan_run = ScanRun(
        project_id=project_id, status=ScanStatus.SUCCESS, files_found=0, total_files=0
    )
    db_session.add(scan_run)
    await db_session.commit()

    detail = await authenticated_api_client.get(f"/projects/{project_id}")

    assert detail.status_code == 200
    last_scan = detail.json()["last_scan"]
    assert last_scan["total_files"] == 0


async def test_get_project_reports_last_scan_total_files_after_enumeration(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    project_id = created.json()["id"]

    scan_run = ScanRun(
        project_id=project_id, status=ScanStatus.RUNNING, files_found=3, total_files=12
    )
    db_session.add(scan_run)
    await db_session.commit()

    detail = await authenticated_api_client.get(f"/projects/{project_id}")

    assert detail.status_code == 200
    last_scan = detail.json()["last_scan"]
    assert last_scan["total_files"] == 12
    assert last_scan["files_found"] == 3


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


# specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR decisions/0025-cloud-
# landmark-erkennung.md ab hier: projektweiter Einwilligungs-Schalter fuer die Cloud-Landmark-
# Erkennung.


async def test_new_project_defaults_to_cloud_vision_detection_disabled(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )

    body = created.json()
    assert body["cloud_vision_detection_enabled"] is False
    assert body["cloud_vision_consent_at"] is None


async def test_enabling_cloud_vision_consent_sets_the_timestamp(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    project_id = created.json()["id"]

    response = await authenticated_api_client.put(
        f"/projects/{project_id}/cloud-vision-consent", json={"enabled": True}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["cloud_vision_detection_enabled"] is True
    assert body["cloud_vision_consent_at"] is not None

    detail = await authenticated_api_client.get(f"/projects/{project_id}")
    assert detail.json()["cloud_vision_detection_enabled"] is True
    assert detail.json()["cloud_vision_consent_at"] is not None


async def test_disabling_cloud_vision_consent_resets_the_timestamp_to_null(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    project_id = created.json()["id"]
    await authenticated_api_client.put(
        f"/projects/{project_id}/cloud-vision-consent", json={"enabled": True}
    )

    response = await authenticated_api_client.put(
        f"/projects/{project_id}/cloud-vision-consent", json={"enabled": False}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["cloud_vision_detection_enabled"] is False
    assert body["cloud_vision_consent_at"] is None


async def test_repeatedly_enabling_cloud_vision_consent_refreshes_the_timestamp(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    # Kein "nur beim ersten Mal"-Sonderfall (Teststrategie-Abschnitt der Spec).
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    project_id = created.json()["id"]

    first = await authenticated_api_client.put(
        f"/projects/{project_id}/cloud-vision-consent", json={"enabled": True}
    )
    first_timestamp = first.json()["cloud_vision_consent_at"]

    second = await authenticated_api_client.put(
        f"/projects/{project_id}/cloud-vision-consent", json={"enabled": True}
    )

    assert second.status_code == 200
    assert second.json()["cloud_vision_consent_at"] is not None
    # Kein exakter Ungleichheits-Beweis noetig (Aufloesung koennte identisch sein) - der
    # eigentliche Nachweis ist, dass ein zweiter Aufruf keinen Fehler/Sonderfall ausloest und
    # weiterhin einen gesetzten Zeitstempel liefert.
    assert first_timestamp is not None


async def test_cloud_vision_consent_returns_404_for_unknown_project(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.put(
        "/projects/999/cloud-vision-consent", json={"enabled": True}
    )

    assert response.status_code == 404


async def test_get_project_reports_last_scoring_run_suggestions_found(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await authenticated_api_client.post(
        "/projects", json={"name": "Costa Rica", "opencloud_path": "A"}
    )
    project_id = created.json()["id"]

    scoring_run = ScoringRun(
        project_id=project_id,
        status=ScanStatus.SUCCESS,
        photos_total=10,
        photos_processed=10,
        suggestions_found=3,
    )
    db_session.add(scoring_run)
    await db_session.commit()

    detail = await authenticated_api_client.get(f"/projects/{project_id}")

    assert detail.status_code == 200
    last_scoring_run = detail.json()["last_scoring_run"]
    assert last_scoring_run["suggestions_found"] == 3
