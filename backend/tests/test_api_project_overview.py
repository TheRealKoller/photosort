"""specs/features/0566-ablauf-uebersicht.md - der Merker "Ablaufuebersicht gesehen".

`GET`/`PUT /projects/{project_id}/overview-seen`, je Person und Projekt. Die Person kommt allein
aus dem Token (S2), keine Antwort nennt den Zustand der anderen Person (S3), ein unbekanntes
Projekt ist `404` und nie `500` (S4).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_opencloud_client
from photosort.db import Base
from photosort.main import app
from photosort.models import Project, ProjectOverviewSeen, User
from photosort.security import create_access_token, hash_password
from tests.project_graph import build_project_graph
from tests.test_api_projects import FakeOpenCloudClient


def _url(project_id: int | str) -> str:
    return f"/projects/{project_id}/overview-seen"


async def _user(session: AsyncSession, username: str) -> User:
    user = User(username=username, password_hash=hash_password("irrelevant"))
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _project(session: AsyncSession, name: str) -> int:
    project = Project(name=name, opencloud_drive_id="drive-1", opencloud_path=f"/{name}")
    session.add(project)
    await session.commit()
    return project.id


@asynccontextmanager
async def _client_for(user: User) -> AsyncIterator[httpx.AsyncClient]:
    """Ein eigener Client mit frisch ausgestelltem Token - ein zweites Geraet derselben Person
    bzw. die andere Person. Die Sitzungsueberschreibung des `api_client` gilt app-weit."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {create_access_token(user)}"},
    ) as client:
        yield client


async def _rows(session: AsyncSession) -> set[tuple[int, int]]:
    result = await session.execute(
        select(ProjectOverviewSeen.user_id, ProjectOverviewSeen.project_id)
    )
    return {(user_id, project_id) for user_id, project_id in result.all()}


async def _seen(client: httpx.AsyncClient, project_id: int) -> bool:
    response = await client.get(_url(project_id))
    assert response.status_code == 200
    seen: bool = response.json()["seen"]
    return seen


# --- Zugriffsschutz (S1) -----------------------------------------------------------------------


async def test_reading_the_marker_requires_a_token(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(_url(1))

    assert response.status_code == 401


async def test_writing_the_marker_requires_a_token(api_client: httpx.AsyncClient) -> None:
    response = await api_client.put(_url(1))

    assert response.status_code == 401


# --- Person und Projekt (S2) -------------------------------------------------------------------


async def test_an_unmarked_project_is_not_seen(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    daniel = await _user(db_session, "daniel")
    project_id = await _project(db_session, "Costa Rica")

    async with _client_for(daniel) as client:
        response = await client.get(_url(project_id))

    assert response.status_code == 200
    assert response.json() == {"seen": False}


async def test_the_marker_applies_to_exactly_this_person_and_this_project(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Matrix Person x Projekt: A merkt P - gesehen ist nur (A, P), nicht (B, P) und (A, Q)."""
    person_a = await _user(db_session, "person-a")
    person_b = await _user(db_session, "person-b")
    project_p = await _project(db_session, "P")
    project_q = await _project(db_session, "Q")

    async with _client_for(person_a) as client_a, _client_for(person_b) as client_b:
        assert (await client_a.put(_url(project_p))).status_code == 204

        matrix = {
            ("A", "P"): await _seen(client_a, project_p),
            ("A", "Q"): await _seen(client_a, project_q),
            ("B", "P"): await _seen(client_b, project_p),
            ("B", "Q"): await _seen(client_b, project_q),
        }

    assert matrix == {("A", "P"): True, ("A", "Q"): False, ("B", "P"): False, ("B", "Q"): False}


async def test_another_device_of_the_same_person_sees_the_marker(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Geraetewechsel: ein zweiter Client mit eigenem, frisch ausgestelltem Token."""
    daniel = await _user(db_session, "daniel")
    project_id = await _project(db_session, "Costa Rica")

    async with _client_for(daniel) as laptop:
        assert (await laptop.put(_url(project_id))).status_code == 204
    async with _client_for(daniel) as phone:
        assert await _seen(phone, project_id) is True


async def test_the_marker_of_the_other_person_does_not_leak(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Hat B eine Zeile, liefert `GET` fuer A trotzdem `seen: false`; ein `PUT` von A laesst den
    Zustand von B unveraendert."""
    person_a = await _user(db_session, "person-a")
    person_b = await _user(db_session, "person-b")
    project_id = await _project(db_session, "P")
    db_session.add(ProjectOverviewSeen(user_id=person_b.id, project_id=project_id))
    await db_session.commit()
    a_id, b_id = person_a.id, person_b.id

    async with _client_for(person_a) as client_a:
        assert await _seen(client_a, project_id) is False
        assert (await client_a.put(_url(project_id))).status_code == 204

    assert await _rows(db_session) == {(a_id, project_id), (b_id, project_id)}


async def test_a_smuggled_user_id_changes_nothing(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """S2: Kein Body-Modell und kein Query-Parameter - ein mitgeschicktes `user_id` schreibt
    trotzdem nur die Zeile der angemeldeten Person."""
    person_a = await _user(db_session, "person-a")
    person_b = await _user(db_session, "person-b")
    project_id = await _project(db_session, "P")
    a_id, b_id = person_a.id, person_b.id

    async with _client_for(person_a) as client_a:
        response = await client_a.put(
            _url(project_id), params={"user_id": b_id}, json={"user_id": b_id}
        )
        assert response.status_code == 204
    async with _client_for(person_b) as client_b:
        assert (await client_b.get(_url(project_id), params={"user_id": a_id})).json() == {
            "seen": False
        }

    assert await _rows(db_session) == {(a_id, project_id)}


async def test_the_answer_carries_nothing_but_the_flag(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """S3: genau `{"seen": bool}` - kein Nutzer, kein Zeitstempel."""
    daniel = await _user(db_session, "daniel")
    project_id = await _project(db_session, "P")

    async with _client_for(daniel) as client:
        await client.put(_url(project_id))
        body = (await client.get(_url(project_id))).json()

    assert body == {"seen": True}


async def test_a_new_project_is_unseen_for_both_persons(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Anlegen zaehlt nicht als Sehen: Das Projekt, das B anlegt, ist fuer A und B ungesehen."""
    person_a = await _user(db_session, "person-a")
    person_b = await _user(db_session, "person-b")
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()

    async with _client_for(person_b) as client_b, _client_for(person_a) as client_a:
        created = await client_b.post("/projects", json={"name": "Neu", "opencloud_path": "Neu"})
        assert created.status_code == 201
        project_id = created.json()["id"]

        assert await _seen(client_b, project_id) is False
        assert await _seen(client_a, project_id) is False


# --- Rueckgabewerte und unbekanntes Projekt (S4) -----------------------------------------------


async def test_writing_twice_is_idempotent(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    daniel = await _user(db_session, "daniel")
    project_id = await _project(db_session, "P")
    daniel_id = daniel.id

    async with _client_for(daniel) as client:
        first = await client.put(_url(project_id))
        second = await client.put(_url(project_id))

    assert (first.status_code, second.status_code) == (204, 204)
    assert first.content == b""
    assert await _rows(db_session) == {(daniel_id, project_id)}


@pytest.mark.parametrize("method", ["get", "put"])
async def test_an_unknown_project_is_404(
    api_client: httpx.AsyncClient, db_session: AsyncSession, method: str
) -> None:
    daniel = await _user(db_session, "daniel")

    async with _client_for(daniel) as client:
        response = await getattr(client, method)(_url(999))

    assert response.status_code == 404
    assert response.json() == {"detail": "Projekt nicht gefunden."}
    assert await _rows(db_session) == set()


@pytest.mark.parametrize("method", ["get", "put"])
async def test_a_deleted_project_is_404(
    api_client: httpx.AsyncClient, db_session: AsyncSession, method: str
) -> None:
    daniel = await _user(db_session, "daniel")
    project_id = await _project(db_session, "Weg")
    async with _client_for(daniel) as client:
        assert (await client.put(_url(project_id))).status_code == 204
        deleted = await client.request(
            "DELETE", f"/projects/{project_id}", json={"confirm_name": "Weg"}
        )
        assert deleted.status_code == 204

        response = await getattr(client, method)(_url(project_id))

    assert response.status_code == 404
    assert await _rows(db_session) == set()


@pytest.mark.parametrize("method", ["get", "put"])
async def test_a_non_integer_project_id_is_422(
    api_client: httpx.AsyncClient, db_session: AsyncSession, method: str
) -> None:
    daniel = await _user(db_session, "daniel")

    async with _client_for(daniel) as client:
        response = await getattr(client, method)(_url("abc"))

    assert response.status_code == 422


async def test_reading_never_creates_a_row(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    daniel = await _user(db_session, "daniel")
    project_id = await _project(db_session, "P")

    async with _client_for(daniel) as client:
        await client.get(_url(project_id))
        await client.get(_url(project_id))

    assert await _rows(db_session) == set()


# --- Gleichzeitiges Schreiben (S4) -------------------------------------------------------------


def _interleave_before_insert(
    monkeypatch: pytest.MonkeyPatch,
    session: AsyncSession,
    write: Callable[[AsyncSession], Any],
) -> dict[str, int]:
    """Setzt zwischen der Pruefung "Zeile vorhanden?" und dem Einfuegen eine ECHTE, committete
    Zwischenschreibung ab - genau das Fenster, in dem ein zweiter Tab oder eine Projektloeschung
    zuschlaegt. `calls` belegt, dass das Fenster betreten wurde."""
    calls = {"count": 0}
    original_get = AsyncSession.get

    async def _get_then_write(self: AsyncSession, entity: Any, ident: Any, **kwargs: Any) -> Any:
        found = await original_get(self, entity, ident, **kwargs)
        if entity is ProjectOverviewSeen and found is None and calls["count"] == 0:
            calls["count"] += 1
            await write(session)
            await session.commit()
        return found

    monkeypatch.setattr(AsyncSession, "get", _get_then_write)
    return calls


async def test_a_concurrent_second_tab_ends_in_204_and_one_row(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    daniel = await _user(db_session, "daniel")
    project_id = await _project(db_session, "P")
    daniel_id = daniel.id

    async def _second_tab(session: AsyncSession) -> None:
        session.add(ProjectOverviewSeen(user_id=daniel_id, project_id=project_id))

    calls = _interleave_before_insert(monkeypatch, db_session, _second_tab)
    async with _client_for(daniel) as client:
        response = await client.put(_url(project_id))
    monkeypatch.undo()

    assert calls["count"] == 1, "das Fenster zwischen Pruefung und Einfuegen wurde nicht betreten"
    assert response.status_code == 204
    assert await _rows(db_session) == {(daniel_id, project_id)}


async def test_a_concurrent_project_deletion_ends_in_404(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    daniel = await _user(db_session, "daniel")
    project_id = await _project(db_session, "Weg")

    async def _delete_project(session: AsyncSession) -> None:
        await session.execute(delete(Project).where(Project.id == project_id))

    calls = _interleave_before_insert(monkeypatch, db_session, _delete_project)
    async with _client_for(daniel) as client:
        response = await client.put(_url(project_id))
    monkeypatch.undo()

    assert calls["count"] == 1, "das Fenster zwischen Pruefung und Einfuegen wurde nicht betreten"
    assert response.status_code == 404
    assert await _rows(db_session) == set()


# --- Aendert nichts am Projekt -----------------------------------------------------------------


async def _snapshot(session: AsyncSession) -> dict[str, list[tuple[Any, ...]]]:
    snapshot: dict[str, list[tuple[Any, ...]]] = {}
    for table in Base.metadata.sorted_tables:
        rows = (await session.execute(select(table))).all()
        snapshot[table.name] = sorted((tuple(row) for row in rows), key=repr)
    return snapshot


async def test_marking_changes_nothing_but_the_one_row(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Oeffnen und Schliessen aendern nichts am Projekt: Einzige Differenz aller Tabellen ist
    eine Zeile in `project_overview_seen`."""
    graph = await build_project_graph(db_session, "Costa Rica")
    daniel = await _user(db_session, "daniel")
    await db_session.commit()
    daniel_id = daniel.id
    before = await _snapshot(db_session)

    async with _client_for(daniel) as client:
        assert (await client.put(_url(graph.project_id))).status_code == 204
    db_session.expire_all()
    after = await _snapshot(db_session)

    changed = {name for name in before if before[name] != after[name]}
    assert changed == {"project_overview_seen"}
    added = set(after["project_overview_seen"]) - set(before["project_overview_seen"])
    assert added == {(daniel_id, graph.project_id)}
    assert len(after["project_overview_seen"]) == len(before["project_overview_seen"]) + 1


def test_the_table_has_no_column_that_could_expire() -> None:
    """ "Anderer Tag": Die Spaltenmenge ist exakt `{user_id, project_id}`."""
    columns = {column.name for column in ProjectOverviewSeen.__table__.columns}

    assert columns == {"user_id", "project_id"}
