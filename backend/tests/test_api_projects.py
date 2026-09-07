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
from photosort.config import settings
from photosort.main import app
from photosort.models import (
    CriterionScoringRun,
    Photo,
    PhotoRanking,
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
        session.add(
            ScanRun(project_id=graph.project_id, status=status, started_at=started_at)
        )
    elif run_kind == "scoring":
        session.add(
            ScoringRun(project_id=graph.project_id, status=status, started_at=started_at)
        )
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
    authenticated_api_client.headers["Authorization"] = (
        f"Bearer {create_access_token(other)}"
    )

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
        record for record in caplog.records
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
