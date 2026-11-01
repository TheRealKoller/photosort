"""Die Export-Endpunkte (Spec 0263): Preview, Ausloeser (202), Detail samt Fehlerliste.

Der Ausloeser nimmt KEIN `current_user` entgegen - seine Authentifizierung ist an der Signatur
nicht sichtbar. Deshalb traegt jeder Endpunkt hier seinen eigenen, pfadbenannten 401-Fall (Auflage
S1), zusaetzlich zum Eintrag in `test_auth_guard.py::_protected_router_operations()`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_job_enqueuer
from photosort.main import app
from photosort.models import (
    CriterionScoringRun,
    ExportPhoto,
    ExportRun,
    ExportRunStatus,
    FinalSelectionDecision,
    Photo,
    Project,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.security import create_access_token, hash_password


class FakeEnqueuer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def enqueue_job(self, function: str, *args: object) -> None:
        self.calls.append((function, args))


async def _project_with_one_included_photo(session: AsyncSession) -> tuple[Project, Photo]:
    project = Project(name="Costa Rica", opencloud_drive_id="drive-1", opencloud_path="/a")
    session.add(project)
    await session.flush()
    now = datetime(2023, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    photo = Photo(
        project_id=project.id,
        relative_path="a.jpg",
        etag="etag-1",
        content_length=100,
        taken_at=now,
        taken_at_original=now,
        last_modified=now,
    )
    session.add(photo)
    await session.flush()
    # Ohne erfolgreichen Kriterien-Lauf gibt es weder Vorschlag noch Einigkeit - die Endauswahl
    # ist leer (dieselbe Ableitung wie `album_selection`). Deshalb der Lauf als Grundlage.
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    session.add(
        CriterionScoringRun(
            project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
        )
    )
    session.add(FinalSelectionDecision(photo_id=photo.id, included=True))
    await session.commit()
    return project, photo


async def _add_export_run(
    session: AsyncSession, project_id: int, *, status: ExportRunStatus = ExportRunStatus.SUCCESS
) -> ExportRun:
    run = ExportRun(
        project_id=project_id,
        status=status,
        target_path="PhotoSort-Export/Costa Rica 2026-11-01 12-00-00.000000",
        photo_count=1,
        exported_count=1,
        failed_count=0,
    )
    session.add(run)
    await session.flush()
    session.add(ExportPhoto(export_run_id=run.id, photo_id=None, relative_path="a.jpg"))
    await session.commit()
    await session.refresh(run)
    return run


class TestAuth:
    @pytest.mark.parametrize(
        "method,path",
        [
            pytest.param("GET", "/projects/1/export-preview", id="preview"),
            pytest.param("POST", "/projects/1/export", id="ausloeser"),
            pytest.param("GET", "/projects/1/exports/1", id="detail"),
        ],
    )
    async def test_each_endpoint_rejects_a_missing_token(
        self, api_client: httpx.AsyncClient, method: str, path: str
    ) -> None:
        """Auflage S1, der EIGENE pfadbenannte Nachweis - die dreifache Sicherung des Ausloesers
        ohne `current_user`."""
        response = await api_client.request(method, path)

        assert response.status_code == 401


async def test_export_preview_returns_the_included_count(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project, _photo = await _project_with_one_included_photo(db_session)

    response = await authenticated_api_client.get(f"/projects/{project.id}/export-preview")

    assert response.status_code == 200
    assert response.json() == {"photo_count": 1}


async def test_export_preview_returns_404_for_an_unknown_project(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.get("/projects/999999/export-preview")

    assert response.status_code == 404


async def test_trigger_export_enqueues_the_job_and_returns_202(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project, _photo = await _project_with_one_included_photo(db_session)
    enqueuer = FakeEnqueuer()
    app.dependency_overrides[get_job_enqueuer] = lambda: enqueuer

    response = await authenticated_api_client.post(f"/projects/{project.id}/export")

    assert response.status_code == 202
    assert enqueuer.calls == [("export_project", (project.id,))]


async def test_trigger_export_returns_404_for_an_unknown_project(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    enqueuer = FakeEnqueuer()
    app.dependency_overrides[get_job_enqueuer] = lambda: enqueuer

    response = await authenticated_api_client.post("/projects/999999/export")

    assert response.status_code == 404
    assert enqueuer.calls == []


async def test_get_export_run_returns_the_run_with_its_failed_photos(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project, _photo = await _project_with_one_included_photo(db_session)
    run = await _add_export_run(db_session, project.id)

    response = await authenticated_api_client.get(f"/projects/{project.id}/exports/{run.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == run.id
    assert body["status"] == "success"
    assert body["target_path"] == "PhotoSort-Export/Costa Rica 2026-11-01 12-00-00.000000"
    assert body["failed_photos"] == []


async def test_get_export_run_lists_only_the_failed_photos(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project, _photo = await _project_with_one_included_photo(db_session)
    run = ExportRun(project_id=project.id, status=ExportRunStatus.SUCCESS, photo_count=2)
    db_session.add(run)
    await db_session.flush()
    db_session.add_all(
        [
            ExportPhoto(export_run_id=run.id, relative_path="ok.jpg"),
            ExportPhoto(export_run_id=run.id, relative_path="kaputt.jpg", error="COPY kaputt"),
        ]
    )
    await db_session.commit()

    response = await authenticated_api_client.get(f"/projects/{project.id}/exports/{run.id}")

    assert response.status_code == 200
    assert response.json()["failed_photos"] == [
        {"relative_path": "kaputt.jpg", "error": "COPY kaputt"}
    ]


async def test_get_export_run_hides_a_run_of_another_project(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project, _photo = await _project_with_one_included_photo(db_session)
    other = Project(name="Anderes", opencloud_drive_id="drive-1", opencloud_path="/b")
    db_session.add(other)
    await db_session.flush()
    run = await _add_export_run(db_session, other.id)

    response = await authenticated_api_client.get(f"/projects/{project.id}/exports/{run.id}")

    assert response.status_code == 404


async def test_last_export_run_is_exposed_on_the_project(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project, _photo = await _project_with_one_included_photo(db_session)
    run = await _add_export_run(db_session, project.id)

    response = await authenticated_api_client.get(f"/projects/{project.id}")

    assert response.status_code == 200
    body = response.json()["last_export_run"]
    assert body["id"] == run.id
    assert body["status"] == "success"
    assert body["photo_count"] == 1
    assert body["target_path"] == "PhotoSort-Export/Costa Rica 2026-11-01 12-00-00.000000"


async def test_both_users_trigger_and_read_the_same_run(
    authenticated_api_client: httpx.AsyncClient,
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Das Ergebnis gehoert dem PROJEKT: der zweite Nutzer liest denselben Lauf (ADR 0136 Punkt 3,
    `export_runs` ohne `user_id`)."""
    project, _photo = await _project_with_one_included_photo(db_session)
    run = await _add_export_run(db_session, project.id)

    partner = User(username="partner", password_hash=hash_password("irrelevant"))
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)
    partner_token = create_access_token(partner)

    response = await api_client.get(
        f"/projects/{project.id}/exports/{run.id}",
        headers={"Authorization": f"Bearer {partner_token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == run.id


async def test_an_export_run_without_a_user_id_is_the_rule(db_session: AsyncSession) -> None:
    """Strukturell: es gibt keine Spalte, in der ein Nutzerbezug stehen koennte."""
    assert "user_id" not in ExportRun.__table__.columns.keys()
