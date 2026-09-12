import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api import projects as projects_api
from photosort.api.deps import get_job_enqueuer, get_opencloud_client
from photosort.cloud_vision import VISION_MODELS_BY_PROVIDER
from photosort.config import settings
from photosort.main import app
from photosort.models import (
    ClassificationPhase,
    CriterionScoringRun,
    Photo,
    PhotoRanking,
    PhotoScore,
    Project,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.opencloud.client import Drive, OpenCloudError
from photosort.opencloud.webdav_xml import DavEntry
from photosort.security import create_access_token, hash_password
from photosort.thumbnails import display_path, thumbnail_path
from tests.project_graph import (
    ProjectGraph,
    build_project_graph,
    count_rows,
    tables_reachable_from_projects,
)


class FakeOpenCloudClient:
    def __init__(self, fail: OpenCloudError | None = None) -> None:
        self._fail = fail

    async def resolve_drive(self, name: str | None) -> Drive:
        if self._fail:
            raise self._fail
        return Drive(
            id="drive-1",
            name="Family",
            drive_type="project",
            webdav_url="https://x/dav/spaces/drive-1",
        )

    async def list_folder(self, webdav_url: str, path: str, depth: str = "1") -> list[DavEntry]:
        if self._fail:
            raise self._fail
        return []


class FakeEnqueuer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, function: str, *args: Any) -> None:
        self.calls.append((function, args))


async def _create_project(client: httpx.AsyncClient, name: str = "Costa Rica") -> int:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await client.post("/projects", json={"name": name, "opencloud_path": name})
    project_id: int = created.json()["id"]
    return project_id


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


# specs/features/0044-projekte-loeschen.md - DELETE /projects/{project_id} ab hier.
#
# WICHTIG fuer jede Assertion hier: die Suite laeuft gegen SQLite OHNE PRAGMA foreign_keys=ON
# (conftest.py). Fremdschluessel werden dort nicht durchgesetzt - jede Lösch-Zusage wird deshalb
# ueber ZEILENZAEHLUNGEN geprueft, nie ueber einen erwarteten IntegrityError oder ein "es ist kein
# Fehler geflogen" (Teststrategie der Spec; das Pragma selbst laeuft als eigenes Issue #350).

DEPENDENT_TABLES = sorted(tables_reachable_from_projects())


async def _add_run(
    session: AsyncSession,
    graph: ProjectGraph,
    run_kind: str,
    status: ScanStatus,
    *,
    minutes_ago: int,
) -> None:
    """Ein zusaetzlicher Lauf des gewuenschten Typs mit explizitem `started_at`.

    Explizit, weil der 409-Waechter ausschliesslich den jeweils NEUESTEN Lauf ansieht - mit dem
    server-seitigen `now()`-Default waeren zwei im selben Test angelegte Laeufe zeitgleich und die
    Reihenfolge unbestimmt."""
    started_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=minutes_ago)
    if run_kind == "scan":
        session.add(ScanRun(project_id=graph.project_id, status=status, started_at=started_at))
    elif run_kind == "scoring":
        session.add(ScoringRun(project_id=graph.project_id, status=status, started_at=started_at))
    elif run_kind == "criterion_scoring":
        session.add(
            CriterionScoringRun(
                project_id=graph.project_id,
                scoring_run_id=graph.scoring_run_id,
                status=status,
                started_at=started_at,
            )
        )
    elif run_kind == "remote_category":
        session.add(
            RemoteCategoryClassificationRun(
                project_id=graph.project_id, status=status, started_at=started_at
            )
        )
    else:  # pragma: no cover - Tippfehler im Parametersatz
        raise AssertionError(f"unbekannter Lauftyp: {run_kind}")
    await session.flush()


async def _delete_project(
    client: httpx.AsyncClient, project_id: int, confirm_name: str
) -> httpx.Response:
    # httpx.AsyncClient.delete() nimmt keinen Body entgegen - deshalb ueber request().
    return await client.request(
        "DELETE", f"/projects/{project_id}", json={"confirm_name": confirm_name}
    )


async def _row_counts(session: AsyncSession) -> dict[str, int]:
    return {name: await count_rows(session, name) for name in DEPENDENT_TABLES}


async def test_delete_project_without_photos_or_runs_returns_204(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    response = await _delete_project(authenticated_api_client, project.id, "Costa Rica")

    assert response.status_code == 204
    assert response.content == b""
    assert (await authenticated_api_client.get(f"/projects/{project.id}")).status_code == 404


async def test_delete_project_removes_rows_of_all_dependent_tables(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    graph = await build_project_graph(db_session, "Weg")

    response = await _delete_project(authenticated_api_client, graph.project_id, "Weg")

    assert response.status_code == 204
    # Tabellenweise ausgeschrieben, damit die Fehlermeldung die vergessene Tabelle nennt.
    assert await count_rows(db_session, "photos") == 0
    assert await count_rows(db_session, "scan_runs") == 0
    assert await count_rows(db_session, "scoring_runs") == 0
    assert await count_rows(db_session, "criterion_scoring_runs") == 0
    assert await count_rows(db_session, "remote_category_classification_runs") == 0
    assert await count_rows(db_session, "ratings") == 0
    assert await count_rows(db_session, "photo_scores") == 0
    assert await count_rows(db_session, "photo_criterion_scores") == 0
    assert await count_rows(db_session, "photo_rankings") == 0
    assert await count_rows(db_session, "photo_landmark_detections") == 0
    assert await count_rows(db_session, "photo_fine_labels") == 0
    assert await count_rows(db_session, "photo_category_classifications") == 0
    assert await count_rows(db_session, "photo_cloud_vision_errors") == 0
    assert await count_rows(db_session, "project_cameras") == 0
    assert await count_rows(db_session, "projects") == 0


async def test_delete_project_keeps_shared_fine_label_and_the_deleting_user(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`fine_labels` ist projektuebergreifendes Vokabular (ADR 0032) und ueberlebt, solange ein
    anderes Projekt darauf zeigt. `users` bleibt ohnehin unangetastet."""
    kept = await build_project_graph(db_session, "Behalten")
    doomed = await build_project_graph(db_session, "Weg")
    assert kept.fine_label_id == doomed.fine_label_id

    response = await _delete_project(authenticated_api_client, doomed.project_id, "Weg")

    assert response.status_code == 204
    assert await count_rows(db_session, "fine_labels") == 1
    assert await count_rows(db_session, "photo_fine_labels") == 1
    assert await count_rows(db_session, "users") >= 1


async def test_delete_project_leaves_rows_of_another_project_untouched(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Eine falsch gesetzte where-Bedingung ist der naheliegendste Fehler dieser Bauform und ohne
    zweites Projekt im Test unsichtbar."""
    await build_project_graph(db_session, "Behalten")
    doomed = await build_project_graph(db_session, "Weg")

    response = await _delete_project(authenticated_api_client, doomed.project_id, "Weg")

    assert response.status_code == 204
    for table_name in DEPENDENT_TABLES:
        assert await count_rows(db_session, table_name) == 1, table_name
    assert await count_rows(db_session, "projects") == 1


async def test_delete_project_returns_404_for_unknown_id(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await _delete_project(authenticated_api_client, 9999, "egal")

    assert response.status_code == 404
    assert response.json()["detail"]


async def test_delete_project_twice_returns_404_the_second_time(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Bewusst nicht idempotent-204: ein zweites DELETE auf eine bereits geloeschte ID ist 404."""
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    first = await _delete_project(authenticated_api_client, project.id, "Costa Rica")
    assert first.status_code == 204
    second = await _delete_project(authenticated_api_client, project.id, "Costa Rica")

    assert second.status_code == 404


@pytest.mark.parametrize("run_kind", ["scan", "scoring", "criterion_scoring", "remote_category"])
async def test_delete_project_returns_409_while_a_run_is_active(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, run_kind: str
) -> None:
    graph = await build_project_graph(db_session, "Weg")
    await _add_run(db_session, graph, run_kind, ScanStatus.RUNNING, minutes_ago=0)
    before = await _row_counts(db_session)

    response = await _delete_project(authenticated_api_client, graph.project_id, "Weg")

    assert response.status_code == 409
    assert response.json()["detail"]
    assert (await authenticated_api_client.get(f"/projects/{graph.project_id}")).status_code == 200
    # Nicht bloss "kein 204": die Zeilenzahlen ALLER dreizehn Tabellen sind unveraendert.
    assert await _row_counts(db_session) == before
    assert await count_rows(db_session, "projects") == 1


@pytest.mark.parametrize("run_kind", ["scan", "scoring", "criterion_scoring", "remote_category"])
async def test_delete_project_ignores_an_outdated_running_run(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, run_kind: str
) -> None:
    """Nur der JEWEILS NEUESTE Lauf zaehlt - ein aelterer RUNNING-Altlauf hinter einem neueren
    SUCCESS blockiert nicht. Das ist der einzige Fall, der `_latest_*` von "irgendein RUNNING"
    unterscheidet."""
    graph = await build_project_graph(db_session, "Weg")
    await _add_run(db_session, graph, run_kind, ScanStatus.RUNNING, minutes_ago=30)
    await _add_run(db_session, graph, run_kind, ScanStatus.SUCCESS, minutes_ago=1)

    response = await _delete_project(authenticated_api_client, graph.project_id, "Weg")

    assert response.status_code == 204
    assert await count_rows(db_session, "projects") == 0


async def test_delete_project_accepts_the_exact_name(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = Project(name="Costa Rica 2019", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    response = await _delete_project(authenticated_api_client, project.id, "Costa Rica 2019")

    assert response.status_code == 204


@pytest.mark.parametrize(
    "confirm_name", ["costa rica", "COSTA RICA", "Costa", "Costa Rica 2019", ""]
)
async def test_delete_project_rejects_a_mismatching_name_with_400(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, confirm_name: str
) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    response = await _delete_project(authenticated_api_client, project.id, confirm_name)

    assert response.status_code == 400
    assert response.json()["detail"]
    assert await count_rows(db_session, "projects") == 1


async def test_delete_project_trims_surrounding_whitespace_of_the_confirmation(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Bewusste Asymmetrie zur Oberflaeche: serverseitig wird getrimmt, clientseitig nicht. Ohne
    eigenen Testfall sieht das wie ein Fehler aus und wuerde beim naechsten Aufraeumen auf einer
    der beiden Seiten "korrigiert"."""
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    response = await _delete_project(authenticated_api_client, project.id, "  Costa Rica\n")

    assert response.status_code == 204


@pytest.mark.parametrize(
    "payload",
    [{}, {"confirm_name": None}, {"confirm_name": 42}, {"confirm_name": "x" * 501}],
    ids=["missing", "null", "wrong-type", "too-long"],
)
async def test_delete_project_rejects_an_invalid_body_with_422(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, payload: dict[str, Any]
) -> None:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.flush()

    response = await authenticated_api_client.request(
        "DELETE", f"/projects/{project.id}", json=payload
    )

    assert response.status_code == 422
    assert await count_rows(db_session, "projects") == 1


async def test_delete_project_leaves_no_partial_state_when_a_statement_fails(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die pruefbare Form der Zusage "in einer Transaktion"."""
    await build_project_graph(db_session, "Weg")
    await db_session.commit()
    graph_id = (
        await db_session.execute(select(Project.id).where(Project.name == "Weg"))
    ).scalar_one()
    before = await _row_counts(db_session)

    async def _boom(session: AsyncSession, project_ids: Any) -> dict[str, int]:
        await session.execute(delete(PhotoRanking))
        raise RuntimeError("mittendrin kaputt")

    monkeypatch.setattr(projects_api, "delete_projects", _boom)

    # Eigener Transport mit raise_app_exceptions=False: sonst reicht die ASGI-Schicht die
    # Ausnahme an den Test durch, statt die 500 zu liefern, die ein echter Client saehe. Die
    # dependency_overrides der Fixture gelten weiter.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers=authenticated_api_client.headers
    ) as client:
        response = await client.request(
            "DELETE", f"/projects/{graph_id}", json={"confirm_name": "Weg"}
        )

    assert response.status_code == 500
    # In der Anwendung erledigt das der Kontextmanager in db.py::get_session; die Test-Fixture
    # reicht dieselbe Session durch und braucht den Rollback deshalb ausgeschrieben.
    await db_session.rollback()
    assert await _row_counts(db_session) == before
    assert await count_rows(db_session, "projects") == 1


async def test_delete_project_answers_a_concurrent_integrity_error_with_409(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unter echtem Postgres moeglich, wenn ein Lauf nebenlaeufig in die gerade geloeschten Zeilen
    schreibt - in der SQLite-Suite strukturell nicht ausloesbar, deshalb monkeypatched."""
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    db_session.add(project)
    await db_session.commit()

    async def _integrity_error(session: AsyncSession, project_ids: Any) -> dict[str, int]:
        raise IntegrityError("DELETE", {}, Exception("FOREIGN KEY constraint failed"))

    monkeypatch.setattr(projects_api, "delete_projects", _integrity_error)

    response = await _delete_project(authenticated_api_client, project.id, "Costa Rica")

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail
    assert "FOREIGN KEY" not in detail


async def test_delete_project_has_no_owner_check(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Bewusste Produktentscheidung: jeder eingeloggte Nutzer darf jedes Projekt loeschen."""
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    other = User(username="andere", password_hash=hash_password("irrelevant"))
    db_session.add_all([project, other])
    await db_session.flush()
    await db_session.refresh(other)
    authenticated_api_client.headers["Authorization"] = f"Bearer {create_access_token(other)}"

    response = await _delete_project(authenticated_api_client, project.id, "Costa Rica")

    assert response.status_code == 204


async def test_delete_project_logs_exactly_one_info_line_without_the_project_name(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    graph = await build_project_graph(db_session, "Geheimprojekt")
    user_id = (
        await db_session.execute(select(User.id).where(User.username == "testuser"))
    ).scalar_one()

    with caplog.at_level(logging.INFO, logger="photosort.api.projects"):
        response = await _delete_project(
            authenticated_api_client, graph.project_id, "Geheimprojekt"
        )

    assert response.status_code == 204
    info_lines = [
        record
        for record in caplog.records
        if record.levelno == logging.INFO and record.name == "photosort.api.projects"
    ]
    assert len(info_lines) == 1
    message = info_lines[0].getMessage()
    assert str(graph.project_id) in message
    assert str(user_id) in message
    assert "photo_rankings" in message
    # Negativ-Assertion: ohne sie ist die Zusage "ohne Projektnamen" unbewiesen.
    assert "Geheimprojekt" not in message


async def test_delete_project_removes_both_cached_variants(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path))
    graph = await build_project_graph(db_session, "Weg")
    # Die erwarteten Pfade UNABHAENGIG vom Endpunkt und VOR dem Request berechnen - das deckt eine
    # falsche Lesereihenfolge (Schluessel erst nach der Zeilenloeschung gelesen) implizit mit ab.
    thumb = thumbnail_path(tmp_path, graph.photo_id, graph.photo_etag)
    display = display_path(tmp_path, graph.photo_id, graph.photo_etag)
    thumb.write_bytes(b"thumb")
    display.write_bytes(b"display")

    response = await _delete_project(authenticated_api_client, graph.project_id, "Weg")

    assert response.status_code == 204
    assert not thumb.exists()
    assert not display.exists()


async def test_delete_project_succeeds_when_no_cache_file_was_ever_written(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path))
    graph = await build_project_graph(db_session, "Weg")

    response = await _delete_project(authenticated_api_client, graph.project_id, "Weg")

    assert response.status_code == 204


async def test_delete_project_keeps_204_and_continues_after_a_cache_unlink_error(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Die eigentliche Zusage ist die zweite Haelfte: die Datei des ZWEITEN Fotos ist trotzdem
    weg. Deshalb braucht der Aufbau zwei Fotos."""
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path))
    graph = await build_project_graph(db_session, "Weg")
    second = Photo(
        project_id=graph.project_id,
        relative_path="Weg/img002.jpg",
        etag="etag-zwei",
        content_length=99,
        taken_at=datetime.now(UTC).replace(tzinfo=None),
        taken_at_original=datetime.now(UTC).replace(tzinfo=None),
        last_modified=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(second)
    await db_session.flush()
    doomed = thumbnail_path(tmp_path, graph.photo_id, graph.photo_etag)
    doomed.write_bytes(b"thumb")
    survivor = thumbnail_path(tmp_path, second.id, second.etag)
    survivor.write_bytes(b"thumb")
    original_unlink = Path.unlink

    def _failing_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == doomed:
            raise OSError("Nur-Lese-Dateisystem")
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", _failing_unlink)

    with caplog.at_level(logging.WARNING):
        response = await _delete_project(authenticated_api_client, graph.project_id, "Weg")

    assert response.status_code == 204
    assert doomed.is_file()
    assert not survivor.exists()
    assert str(doomed) in caplog.text
    # Der Cache-Pfad gehoert ins Log, nie in die Antwort.
    assert response.content == b""


async def test_delete_project_leaves_a_foreign_cache_file_alone(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Ohne diesen Test ist "kein glob, kein rmtree" (ADR 0062 Punkt 5) nur eine
    Absichtserklaerung."""
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path))
    graph = await build_project_graph(db_session, "Weg")
    thumbnail_path(tmp_path, graph.photo_id, graph.photo_etag).write_bytes(b"thumb")
    foreign = tmp_path / "fremde-familien-datei_thumbnail.jpg"
    foreign.write_bytes(b"nicht anfassen")

    response = await _delete_project(authenticated_api_client, graph.project_id, "Weg")

    assert response.status_code == 204
    assert foreign.is_file()


async def test_delete_project_keeps_204_when_the_cache_cleanup_raises_a_non_oserror(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Copilot-Fund (PR #351): `delete_cached_variants` faengt nur `OSError` JE DATEI ab - alles
    andere (und alles, was aus `to_thread` selbst kommt) schlug bis zum Client durch, als `500`,
    obwohl die Loeschung laengst committet war. Die Zusage "Cleanup-Fehler aendern die 204 nicht"
    galt damit nur fuer einen Teil der moeglichen Fehler."""
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path))
    graph = await build_project_graph(db_session, "Weg")

    def _boom(cache_dir: Path, photos: Any) -> None:
        raise RuntimeError("Cache-Volume abgeraucht")

    monkeypatch.setattr(projects_api, "delete_cached_variants", _boom)

    with caplog.at_level(logging.WARNING, logger="photosort.api.projects"):
        response = await _delete_project(authenticated_api_client, graph.project_id, "Weg")

    assert response.status_code == 204
    assert await count_rows(db_session, "projects") == 0
    assert await count_rows(db_session, "photos") == 0
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    # Der Fehlertext gehoert ins Log, nie in die Antwort.
    assert response.content == b""


# --------------------------------------------------------------------------------------------
# specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-vier-
# teilschritte-und-laufeigene-cloud-bilanz.md Punkt 4: die laufeigene Cloud-Bilanz an der
# Run-Zusammenfassung - waehrend des Laufs die Fortschrittsanzeige, danach die Bilanz. Derselbe
# Datensatz zu zwei Zeitpunkten, keine zweite Struktur, kein neuer Endpunkt.
# --------------------------------------------------------------------------------------------


async def _apply_explicit_nulls(session: AsyncSession, run: Any, nulls: dict[str, Any]) -> None:
    """Setzt Spalten NACH dem Insert auf `NULL`.

    Noetig, weil SQLAlchemy ein im Konstruktor uebergebenes `None` beim INSERT als "nimm den
    Python-Default" behandelt - `landmark_cost_usd=None` landete dort also als `0`, und genau der
    Unterschied zwischen `NULL` ("kein Preis hinterlegt") und `0` ("nichts angefallen") ist der
    Gegenstand dieser Testfaelle. Ein UPDATE schreibt `NULL` dagegen woertlich."""
    if not nulls:
        return
    for key in nulls:
        setattr(run, key, None)
    await session.commit()
    await session.refresh(run)


async def _add_criterion_scoring_run(
    session: AsyncSession, project_id: int, **fields: Any
) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.commit()
    await session.refresh(scoring_run)
    nulls = {key: value for key, value in fields.items() if value is None}
    run = CriterionScoringRun(
        project_id=project_id,
        scoring_run_id=scoring_run.id,
        status=fields.pop("status", ScanStatus.SUCCESS),
        **{key: value for key, value in fields.items() if value is not None},
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    await _apply_explicit_nulls(session, run, nulls)
    return run


async def _add_remote_run(
    session: AsyncSession, project_id: int, **fields: Any
) -> RemoteCategoryClassificationRun:
    nulls = {key: value for key, value in fields.items() if value is None}
    run = RemoteCategoryClassificationRun(
        project_id=project_id,
        status=fields.pop("status", ScanStatus.SUCCESS),
        **{key: value for key, value in fields.items() if value is not None},
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    await _apply_explicit_nulls(session, run, nulls)
    return run


async def _cloud_phases(client: httpx.AsyncClient, project_id: int) -> list[dict[str, Any]]:
    body = (await client.get(f"/projects/{project_id}")).json()
    phases: list[dict[str, Any]] = body["last_criterion_scoring_run"]["cloud_phases"]
    return phases


async def test_cloud_phases_is_empty_for_a_run_without_any_cloud_step(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Leere LISTE, nicht `null` und keine erfundenen Nullzeilen: "dieser Durchlauf hatte keinen
    Cloud-Teilschritt" ist eine Aussage, und die Oberflaeche haengt genau daran ihre Erklaerung
    auf."""
    project_id = await _create_project(authenticated_api_client)
    await _add_criterion_scoring_run(db_session, project_id, cloud_requested=False)

    assert await _cloud_phases(authenticated_api_client, project_id) == []


async def test_a_landmark_phase_without_candidates_is_shown_not_hidden(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Das Gegenstueck zum Test darueber, und die Stelle, an der die Vierfeldertafel sichtbar
    wird: `landmark_photos_total == 0` heisst "der Teilschritt lief, es war nichts zu tun" - er
    bekommt seinen Eintrag. Nur `NULL` heisst "gab es nicht" und laesst ihn weg.

    Die Unterscheidung ist keine Formsache: Ein weggelassener Teilschritt liest sich wie ein
    uebersprungener, und die Oberflaeche zeigt ihn dann als `skipped` an, obwohl er stattgefunden
    hat."""
    project_id = await _create_project(authenticated_api_client)
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        cloud_requested=True,
        landmark_photos_total=0,
        landmark_photos_processed=0,
        landmark_failed_calls=0,
        landmark_api_calls=0,
        landmark_cost_usd=0.0,
        landmark_model="claude-haiku-4-5",
    )

    phases = await _cloud_phases(authenticated_api_client, project_id)

    assert [phase["purpose"] for phase in phases] == ["landmark"]
    assert phases[0]["photos_total"] == 0
    assert phases[0]["photos_processed"] == 0
    assert phases[0]["failed_calls"] == 0


async def test_cloud_phases_lists_remote_category_before_landmark(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Feste Reihenfolge = Ausfuehrungsreihenfolge. Die Fixture gibt beiden Phasen ABSICHTLICH
    unterschiedliche Zahlen - bei gleichen Werten waere eine Vertauschung unsichtbar."""
    project_id = await _create_project(authenticated_api_client)
    remote = await _add_remote_run(
        db_session,
        project_id,
        photos_total=7,
        photos_processed=7,
        failed_calls=1,
        api_calls=6,
        input_tokens=600,
        output_tokens=60,
        cost_usd=0.6,
        model="claude-haiku-4-5",
    )
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        cloud_requested=True,
        remote_category_classification_run_id=remote.id,
        landmark_photos_total=3,
        landmark_photos_processed=3,
        landmark_failed_calls=0,
        landmark_api_calls=3,
        landmark_input_tokens=300,
        landmark_output_tokens=30,
        landmark_cost_usd=0.3,
        landmark_model="claude-haiku-4-5",
    )

    phases = await _cloud_phases(authenticated_api_client, project_id)

    assert [phase["purpose"] for phase in phases] == ["remote_category", "landmark"]
    assert phases[0]["photos_total"] == 7
    assert phases[0]["responses_used"] == 6
    assert phases[0]["failed_calls"] == 1
    assert phases[1]["photos_total"] == 3
    assert phases[1]["responses_used"] == 3
    assert phases[1]["failed_calls"] == 0


async def test_only_the_remote_phase_appears_as_soon_as_it_was_entered(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Merkmal der Remote-Phase ist der gesetzte FREMDSCHLUESSEL - er steht seit ADR 0068 Punkt 3
    bereits vor dem ersten Cloud-Aufruf da."""
    project_id = await _create_project(authenticated_api_client)
    remote = await _add_remote_run(db_session, project_id, status=ScanStatus.RUNNING)
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        status=ScanStatus.RUNNING,
        cloud_requested=True,
        remote_category_classification_run_id=remote.id,
    )

    phases = await _cloud_phases(authenticated_api_client, project_id)

    assert [phase["purpose"] for phase in phases] == ["remote_category"]


async def test_only_the_landmark_phase_appears_as_soon_as_it_was_entered(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Merkmal der Landmark-Phase ist `landmark_photos_total is not None` - `NULL` heisst "diese
    Phase fand nicht statt", `0` heisst "fand statt, ohne Kandidaten"."""
    project_id = await _create_project(authenticated_api_client)
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        cloud_requested=True,
        landmark_photos_total=0,
        landmark_photos_processed=0,
        landmark_failed_calls=0,
    )

    phases = await _cloud_phases(authenticated_api_client, project_id)

    assert [phase["purpose"] for phase in phases] == ["landmark"]
    assert phases[0]["photos_total"] == 0


async def test_a_running_phase_reports_live_counters_and_no_amount_yet(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der Punkt der ganzen Struktur: waehrend des Laufs bewegen sich `photos_processed` und
    `failed_calls`, waehrend `responses_used` und der Betrag noch auf dem Anfangsstand stehen -
    die Kosten-Buchfuehrung wird erst am Phasenende eingefroren."""
    project_id = await _create_project(authenticated_api_client)
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        status=ScanStatus.RUNNING,
        phase=ClassificationPhase.LANDMARK,
        cloud_requested=True,
        landmark_photos_total=10,
        landmark_photos_processed=4,
        landmark_failed_calls=1,
        landmark_api_calls=0,
        landmark_cost_usd=0.0,
        landmark_model="claude-haiku-4-5",
    )

    phases = await _cloud_phases(authenticated_api_client, project_id)

    assert phases[0]["photos_processed"] == 4
    assert phases[0]["failed_calls"] == 1
    assert phases[0]["responses_used"] == 0
    assert phases[0]["model"] == "claude-haiku-4-5"
    assert phases[0]["provider"] == "anthropic"


async def test_an_unpriced_phase_reports_null_not_zero(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SECURITY-MUSS (Spec 0348): `null` schlaegt unverfaelscht durch, kein `?? 0` / `or 0.0`
    irgendwo im Pfad. Ein stilles "0,00 USD" tarnte einen unerwarteten, kostenpflichtigen Lauf
    als kostenlos."""
    project_id = await _create_project(authenticated_api_client)
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        cloud_requested=True,
        landmark_photos_total=2,
        landmark_photos_processed=2,
        landmark_failed_calls=0,
        landmark_api_calls=2,
        landmark_cost_usd=None,
        landmark_model="ein-nie-bepreistes-modell",
    )

    body = (await authenticated_api_client.get(f"/projects/{project_id}")).json()
    run = body["last_criterion_scoring_run"]

    assert run["cloud_phases"][0]["cost_usd"] is None
    assert run["cloud_cost_total_usd"] is None


async def test_the_total_is_null_as_soon_as_one_share_is_null(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Die Regel "unvollstaendig != 0" bleibt SERVERSEITIG an einer Stelle (wie
    `CostOut.total_usd`) - sonst muesste jede Komponente sie einzeln kennen und eine davon
    vergaesse sie."""
    project_id = await _create_project(authenticated_api_client)
    remote = await _add_remote_run(
        db_session,
        project_id,
        photos_total=1,
        photos_processed=1,
        failed_calls=0,
        api_calls=1,
        cost_usd=0.5,
        model="claude-haiku-4-5",
    )
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        cloud_requested=True,
        remote_category_classification_run_id=remote.id,
        landmark_photos_total=1,
        landmark_photos_processed=1,
        landmark_failed_calls=0,
        landmark_api_calls=1,
        landmark_cost_usd=None,
        landmark_model="ein-nie-bepreistes-modell",
    )

    body = (await authenticated_api_client.get(f"/projects/{project_id}")).json()

    assert body["last_criterion_scoring_run"]["cloud_cost_total_usd"] is None


async def test_the_total_sums_the_known_amounts(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project_id = await _create_project(authenticated_api_client)
    remote = await _add_remote_run(
        db_session,
        project_id,
        photos_total=1,
        photos_processed=1,
        failed_calls=0,
        api_calls=1,
        cost_usd=0.5,
        model="claude-haiku-4-5",
    )
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        cloud_requested=True,
        remote_category_classification_run_id=remote.id,
        landmark_photos_total=1,
        landmark_photos_processed=1,
        landmark_failed_calls=0,
        landmark_api_calls=1,
        landmark_cost_usd=0.25,
        landmark_model="claude-haiku-4-5",
        estimated_cost_usd=1.0,
    )

    run = (await authenticated_api_client.get(f"/projects/{project_id}")).json()[
        "last_criterion_scoring_run"
    ]

    assert run["cloud_cost_total_usd"] == pytest.approx(0.75)
    assert run["estimated_cost_usd"] == pytest.approx(1.0)


async def test_the_provider_is_derived_from_the_stored_model(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """ADR 0068 Punkt 6: NIE aus `settings.landmark_provider` - die aktuelle Betriebseinstellung
    sagt nichts darueber, womit ein vergangener Lauf gerechnet hat, und eine historische
    Lauf-Antwort kann so strukturell nicht die heutige Konfiguration preisgeben."""
    project_id = await _create_project(authenticated_api_client)
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        cloud_requested=True,
        landmark_photos_total=1,
        landmark_photos_processed=1,
        landmark_failed_calls=0,
        landmark_api_calls=1,
        landmark_cost_usd=0.1,
        landmark_model=VISION_MODELS_BY_PROVIDER["mistral"][0],
    )

    phases = await _cloud_phases(authenticated_api_client, project_id)

    assert phases[0]["provider"] == "mistral"
    assert settings.landmark_provider != "mistral"


async def test_an_unknown_model_leaves_the_provider_null(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project_id = await _create_project(authenticated_api_client)
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        cloud_requested=True,
        landmark_photos_total=1,
        landmark_photos_processed=1,
        landmark_failed_calls=0,
        landmark_model="ein-laengst-entferntes-modell",
    )

    phases = await _cloud_phases(authenticated_api_client, project_id)

    assert phases[0]["model"] == "ein-laengst-entferntes-modell"
    assert phases[0]["provider"] is None


async def test_a_withdrawn_model_keeps_its_frozen_amount_and_loses_its_provider(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """specs/features/0369-mistral-small-loest-ministral-8b-ab.md, K7: der Altlauf-Fall mit der
    TATSAECHLICH zurueckgenommenen Modell-ID.

    Der Test darueber belegt dieselbe Regel an einer erfundenen ID; ab dieser Story ist der
    `None`-Zweig kein hypothetischer mehr, sondern der regulaere Zustand jedes Laufs, der mit
    `ministral-8b-2512` gerechnet hat (S10). Zwei Aussagen in einem Fall:

    1. Modellangabe UND eingefrorener Betrag bleiben WOERTLICH stehen - sie kommen aus den
       Lauf-Spalten (ADR 0051 Punkt 4) und werden nicht gegen die heutige `MODEL_PRICING`
       nachgerechnet. Ein solcher Lesepfad verwandelte eine erfasste Kostenangabe in "nicht
       erfasst" (S11); deshalb ist `landmark_cost_usd` hier bewusst GESETZT.
    2. Der abgeleitete Anbieter ist `null` - kein Rueckfall auf `settings.landmark_provider`,
       keine Praefix-Heuristik `ministral-*` -> `mistral`, keine Schattenregistry (S9/ADR 0068
       Punkt 6). Ein geratener Anbieter waere eine Behauptung ueber die Vergangenheit, die der
       Code nicht belegen kann - und gaebe die heutige Betriebseinstellung preis."""
    project_id = await _create_project(authenticated_api_client)
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        cloud_requested=True,
        landmark_photos_total=3,
        landmark_photos_processed=3,
        landmark_failed_calls=0,
        landmark_api_calls=3,
        landmark_cost_usd=0.00135,
        landmark_model="ministral-8b-2512",
    )

    phases = await _cloud_phases(authenticated_api_client, project_id)

    assert phases[0]["model"] == "ministral-8b-2512"
    assert phases[0]["cost_usd"] == pytest.approx(0.00135)
    assert phases[0]["provider"] is None


async def test_the_response_carries_no_further_configuration_fields(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """SECURITY-MUSS (Spec 0348): die Antwort waechst um genau die aufgezaehlten Felder und um
    KEIN weiteres - keine Basis-URLs, keine `*_concurrency`-Werte, kein "API-Key gesetzt ja/nein",
    kein Umgebungsvariablenname, kein Pfad."""
    project_id = await _create_project(authenticated_api_client)
    await _add_criterion_scoring_run(
        db_session,
        project_id,
        cloud_requested=True,
        landmark_photos_total=1,
        landmark_photos_processed=1,
        landmark_failed_calls=0,
    )

    run = (await authenticated_api_client.get(f"/projects/{project_id}")).json()[
        "last_criterion_scoring_run"
    ]

    assert set(run) == {
        "status",
        "started_at",
        "finished_at",
        "photos_total",
        "photos_processed",
        "error_message",
        "phase",
        "cloud_requested",
        "cloud_error_message",
        "estimated_cost_usd",
        "cloud_phases",
        "cloud_cost_total_usd",
    }
    assert set(run["cloud_phases"][0]) == {
        "purpose",
        "photos_total",
        "photos_processed",
        "failed_calls",
        "responses_used",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "model",
        "provider",
    }


async def test_project_out_no_longer_exposes_last_remote_category_classification_run(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Ersetzt `test_project_out_exposes_last_remote_category_classification_run` (bisher in
    test_api_classification_estimate.py).

    Die Frage des gestrichenen Tests - "zeigt die API die Remote-Zahlen an?" - wird ab jetzt von
    den `test_cloud_phases_*`-Faellen oben gestellt, und zwar besser: sie haengen an dem
    Fremdschluessel des jeweiligen Durchlaufs statt an der juengsten Remote-Zeile des Projekts.
    Zwei Wege zu derselben Zeile, von denen einer die falsche treffen kann, sind genau der
    Zustand, den ADR 0068 Punkt 3 beseitigt."""
    project_id = await _create_project(authenticated_api_client)
    await _add_remote_run(db_session, project_id, photos_total=5, photos_processed=5)

    body = (await authenticated_api_client.get(f"/projects/{project_id}")).json()

    assert "last_remote_category_classification_run" not in body


class TestTheRunEstimateReachesTheJob:
    """ADR 0068 Punkt 5: die Schaetzung wird SERVERSEITIG im Ausloese-Endpunkt berechnet und als
    Job-Argument durchgereicht - nie vom Client mitgeschickt (ungepruefter Geldwert ueber die
    Vertrauensgrenze) und nie im Worker neu gerechnet (dritte Kopie der Kandidaten-Zaehlung)."""

    async def _prepare(
        self, client: httpx.AsyncClient, session: AsyncSession, *, photo_count: int
    ) -> tuple[int, int]:
        project_id = await _create_project(client)
        project = await session.get(Project, project_id)
        assert project is not None
        project.cloud_vision_detection_enabled = True
        scoring_run = ScoringRun(
            project_id=project_id,
            status=ScanStatus.SUCCESS,
            suggestions_found=1,
            gate_confirmed_at=datetime.now(UTC).replace(tzinfo=None),
        )
        session.add(scoring_run)
        await session.commit()
        await session.refresh(scoring_run)
        now = datetime(2023, 1, 1, tzinfo=UTC)
        for index in range(photo_count):
            photo = Photo(
                project_id=project_id,
                relative_path=f"{index}.jpg",
                etag=f"etag-{index}",
                content_length=1,
                taken_at=now,
                taken_at_original=now,
                last_modified=now,
            )
            session.add(photo)
            await session.commit()
            await session.refresh(photo)
            session.add(
                PhotoScore(
                    photo_id=photo.id,
                    sharpness=100.0,
                    exposure=0.0,
                    cluster_key="cluster-0",
                    suggested_status=None,
                    computed_at=now,
                )
            )
        await session.commit()
        return project_id, scoring_run.id

    async def test_the_estimate_of_the_run_is_forwarded_to_the_job(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der erwartete Wert wird AUS `GET .../classify/estimate` gelesen, nicht im Test
        nachgerechnet: eine Nachrechnung waere eine zweite Kopie derselben Formel und liefe mit
        ihr auseinander, ohne dass etwas rot wuerde."""
        project_id, scoring_run_id = await self._prepare(
            authenticated_api_client, db_session, photo_count=3
        )
        expected = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()["estimated_cost_usd"]
        assert expected is not None and expected > 0
        fake_enqueuer = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify",
            json={"scoring_run_id": scoring_run_id, "use_cloud": True},
        )

        assert response.status_code == 202
        assert fake_enqueuer.calls == [("classify", (project_id, scoring_run_id, True, expected))]

    async def test_a_local_run_forwards_none_and_stores_null(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`NULL`, nicht `0.0`: ein Lauf ohne Cloud hat keine Kostenschaetzung, und `0.0` waere
        eine Aussage, die niemand getroffen hat."""
        project_id, scoring_run_id = await self._prepare(
            authenticated_api_client, db_session, photo_count=3
        )
        fake_enqueuer = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify",
            json={"scoring_run_id": scoring_run_id, "use_cloud": False},
        )

        assert response.status_code == 202
        assert fake_enqueuer.calls == [("classify", (project_id, scoring_run_id, False, None))]

    async def test_the_request_body_cannot_influence_the_stored_estimate(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SECURITY-MUSS (Spec 0348): pydantic ignoriert unbekannte Felder heute STILL - ohne
        diesen Test fiele eine spaetere versehentliche Aufnahme von `estimated_cost_usd` ins
        `ClassifyRequest`-Schema niemandem auf, und ein vom Client geliefertes Geldfeld wanderte
        ungeprueft in die Buchfuehrung."""
        project_id, scoring_run_id = await self._prepare(
            authenticated_api_client, db_session, photo_count=3
        )
        expected = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()["estimated_cost_usd"]
        fake_enqueuer = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake_enqueuer

        response = await authenticated_api_client.post(
            f"/projects/{project_id}/classify",
            json={
                "scoring_run_id": scoring_run_id,
                "use_cloud": True,
                "estimated_cost_usd": 999_999.0,
                "cost_usd": 999_999.0,
                "model": "ein-untergeschobenes-modell",
                "provider": "ein-untergeschobener-anbieter",
            },
        )

        assert response.status_code == 202
        assert fake_enqueuer.calls == [("classify", (project_id, scoring_run_id, True, expected))]
