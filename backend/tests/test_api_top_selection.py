from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_job_enqueuer, get_opencloud_client
from photosort.config import settings
from photosort.main import app
from photosort.models import ScanStatus, ScoringRun, TopSelectionRun
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


async def test_select_top_requires_auth(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/projects/1/select-top", json={"top_n_per_cluster": 3})

    assert response.status_code == 401


async def test_select_top_returns_404_for_unknown_project(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

    response = await authenticated_api_client.post(
        "/projects/999/select-top", json={"top_n_per_cluster": 3}
    )

    assert response.status_code == 404


async def test_select_top_returns_403_when_feature_flag_disabled(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "category_selection_enabled", False)
    project_id = await _create_project(authenticated_api_client)
    db_session.add(ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS))
    await db_session.commit()
    app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

    response = await authenticated_api_client.post(
        f"/projects/{project_id}/select-top", json={"top_n_per_cluster": 3}
    )

    assert response.status_code == 403


async def test_select_top_returns_403_before_404_for_an_unknown_project_when_flag_disabled(
    authenticated_api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Test-Engineer-Review-Fund (Nice-to-have, dokumentiertes Verhalten statt Fix): der
    # Feature-Flag-Check laeuft VOR dem Projekt-Existenz-Check (trigger_select_top prueft
    # settings.category_selection_enabled zuerst) - eine unbekannte project_id liefert bei
    # deaktiviertem Flag deshalb 403 statt 404. Das folgt woertlich der im Architektur-Abschnitt
    # der Spec genannten Pruefreihenfolge ("403 ... 409 ... sonst") und verraet nichts
    # Projektspezifisches (das Flag ist global, nicht projektbezogen) - keine Aenderung noetig,
    # nur bislang untestete Kombination.
    monkeypatch.setattr(settings, "category_selection_enabled", False)
    app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

    response = await authenticated_api_client.post(
        "/projects/999999/select-top", json={"top_n_per_cluster": 3}
    )

    assert response.status_code == 403


async def test_select_top_allows_request_with_default_feature_flag(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    # Explizit den Default (True) mitgetestet, nicht nur den False-Fall (Teststrategie-Abschnitt
    # der Spec).
    assert settings.category_selection_enabled is True
    project_id = await _create_project(authenticated_api_client)
    db_session.add(ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS))
    await db_session.commit()
    app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

    response = await authenticated_api_client.post(
        f"/projects/{project_id}/select-top", json={"top_n_per_cluster": 3}
    )

    assert response.status_code == 202


async def test_select_top_returns_409_without_successful_scoring_run(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    project_id = await _create_project(authenticated_api_client)
    app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

    response = await authenticated_api_client.post(
        f"/projects/{project_id}/select-top", json={"top_n_per_cluster": 3}
    )

    assert response.status_code == 409


async def test_select_top_returns_409_when_latest_scoring_run_failed(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project_id = await _create_project(authenticated_api_client)
    db_session.add(ScoringRun(project_id=project_id, status=ScanStatus.FAILED))
    await db_session.commit()
    app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

    response = await authenticated_api_client.post(
        f"/projects/{project_id}/select-top", json={"top_n_per_cluster": 3}
    )

    assert response.status_code == 409


async def test_select_top_enqueues_job_with_top_n_per_cluster(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project_id = await _create_project(authenticated_api_client)
    db_session.add(ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS))
    await db_session.commit()
    fake_enqueuer = FakeEnqueuer()
    app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

    response = await authenticated_api_client.post(
        f"/projects/{project_id}/select-top", json={"top_n_per_cluster": 5}
    )

    assert response.status_code == 202
    assert fake_enqueuer.calls == [("select_top_photos", (project_id, 5))]


@pytest.mark.parametrize("top_n_per_cluster", [0, 11, -1])
async def test_select_top_rejects_top_n_per_cluster_outside_valid_range(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    top_n_per_cluster: int,
) -> None:
    project_id = await _create_project(authenticated_api_client)
    db_session.add(ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS))
    await db_session.commit()
    app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

    response = await authenticated_api_client.post(
        f"/projects/{project_id}/select-top", json={"top_n_per_cluster": top_n_per_cluster}
    )

    assert response.status_code == 422


async def test_project_out_exposes_category_selection_enabled_flag(
    authenticated_api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # UI/UX-Abschnitt der Spec: das Verfuegbarkeitsgate im Frontend muss proaktiv aus bereits
    # geladenen Projektdaten abgeleitet werden koennen, statt erst nach einem fehlgeschlagenen
    # 403-Request - dafuer muss das Feature-Flag ueberhaupt irgendwo in der API sichtbar sein.
    # Technische Detailentscheidung der Umsetzung: auf ProjectOut, da das ohnehin die bereits
    # geladenen Projektdaten dieser Seite sind (kein neuer Endpunkt fuer einen einzelnen globalen
    # Konfigurationswert).
    project_id = await _create_project(authenticated_api_client)

    default_detail = await authenticated_api_client.get(f"/projects/{project_id}")
    assert default_detail.json()["category_selection_enabled"] is True

    monkeypatch.setattr(settings, "category_selection_enabled", False)
    disabled_detail = await authenticated_api_client.get(f"/projects/{project_id}")
    assert disabled_detail.json()["category_selection_enabled"] is False


async def test_project_out_has_no_last_top_selection_run_before_any_select_top_call(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    project_id = await _create_project(authenticated_api_client)

    detail = await authenticated_api_client.get(f"/projects/{project_id}")

    assert detail.json()["last_top_selection_run"] is None


async def test_project_out_reports_last_top_selection_run_progress(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project_id = await _create_project(authenticated_api_client)
    run = TopSelectionRun(
        project_id=project_id,
        status=ScanStatus.RUNNING,
        top_n_per_cluster=3,
        candidates_total=10,
        candidates_processed=4,
    )
    db_session.add(run)
    await db_session.commit()

    detail = await authenticated_api_client.get(f"/projects/{project_id}")

    last_top_selection_run = detail.json()["last_top_selection_run"]
    assert last_top_selection_run["status"] == "running"
    assert last_top_selection_run["top_n_per_cluster"] == 3
    assert last_top_selection_run["candidates_total"] == 10
    assert last_top_selection_run["candidates_processed"] == 4


async def test_project_out_reports_last_top_selection_run_suggestions_found(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project_id = await _create_project(authenticated_api_client)
    run = TopSelectionRun(
        project_id=project_id,
        status=ScanStatus.SUCCESS,
        top_n_per_cluster=3,
        candidates_total=10,
        candidates_processed=10,
        suggestions_found=6,
    )
    db_session.add(run)
    await db_session.commit()

    detail = await authenticated_api_client.get(f"/projects/{project_id}")

    assert detail.json()["last_top_selection_run"]["suggestions_found"] == 6
