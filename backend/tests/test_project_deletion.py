"""specs/features/0044-projekte-loeschen.md / ADR 0062 - die beiden Metadaten-Tests.

Sie sind der Ersatz fuer die fehlende Fremdschluessel-Durchsetzung der Testdatenbank: die Suite
laeuft gegen SQLite In-Memory OHNE `PRAGMA foreign_keys=ON` (siehe conftest.py), eine falsche
Loeschreihenfolge faellt dort zur Laufzeit NICHT auf.

Beide leiten ihre Erwartung aus `Base.metadata` ab und wiederholen keine Tabellenliste - auch
keine Ausnahmeliste fuer `users`/`fine_labels`: die beiden sind Fremdschluessel-ELTERN und fallen
aus der Erreichbarkeitsableitung automatisch heraus.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.db import Base
from photosort.models import Project
from photosort.project_deletion import collect_photo_cache_keys, delete_projects
from tests.project_graph import (
    build_project_graph,
    count_rows,
    tables_reachable_from_projects,
)

_DELETE_TARGET = re.compile(r"\s*DELETE\s+FROM\s+\"?([a-z_]+)\"?", re.IGNORECASE)


@contextmanager
def _recorded_delete_targets() -> Iterator[list[str]]:
    """Die TATSAECHLICH abgesetzten DELETE-Anweisungen, in ihrer tatsaechlichen Reihenfolge.

    Bewusst ueber das `before_cursor_execute`-Ereignis der Engine und nicht ueber eine im Modul
    danebenstehende Konstante: eine Konstante und die ausgefuehrten Anweisungen driften, und
    geprueft gehoert, was das Modul tut."""
    targets: list[str] = []

    def _listener(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        match = _DELETE_TARGET.match(statement)
        if match is not None:
            targets.append(match.group(1))

    event.listen(Engine, "before_cursor_execute", _listener)
    try:
        yield targets
    finally:
        event.remove(Engine, "before_cursor_execute", _listener)


async def test_delete_projects_issues_statements_in_metadata_foreign_key_order(
    db_session: AsyncSession,
) -> None:
    """Loeschreihenfolge == `reversed(Base.metadata.sorted_tables)`, eingeschraenkt auf die von
    `projects` erreichbaren Tabellen plus `projects` selbst."""
    graph = await build_project_graph(db_session, "Costa Rica")
    relevant = tables_reachable_from_projects() | {Project.__tablename__}
    expected = [
        table.name for table in reversed(Base.metadata.sorted_tables) if table.name in relevant
    ]

    with _recorded_delete_targets() as targets:
        await delete_projects(db_session, [graph.project_id])

    assert targets == expected, (
        "Die Loeschreihenfolge in project_deletion.py weicht von der Fremdschluessel-Reihenfolge "
        "aus Base.metadata ab."
    )


async def test_delete_projects_covers_every_table_reachable_from_projects(
    db_session: AsyncSession,
) -> None:
    """Vollstaendigkeit: keine ueber einen Fremdschluessel am Projekt haengende Tabelle fehlt."""
    graph = await build_project_graph(db_session, "Costa Rica")
    expected = tables_reachable_from_projects()

    with _recorded_delete_targets() as targets:
        await delete_projects(db_session, [graph.project_id])

    missing = expected - set(targets)
    assert not missing, (
        f"project_deletion.py loescht diese am Projekt haengenden Tabellen nicht: "
        f"{sorted(missing)}"
    )
    assert set(targets) - expected == {Project.__tablename__}, (
        "project_deletion.py loescht eine Tabelle, die gar nicht am Projekt haengt."
    )


async def test_delete_projects_removes_every_row_of_the_given_project(
    db_session: AsyncSession,
) -> None:
    """Verhaltenstest gegen die echte In-Memory-DB: voller Datengraph zweier Projekte, Loeschung
    von Projekt A, danach Zeilenzaehlungen fuer beide."""
    kept = await build_project_graph(db_session, "Behalten")
    doomed = await build_project_graph(db_session, "Weg")
    await db_session.commit()

    await delete_projects(db_session, [doomed.project_id])
    await db_session.commit()

    for table_name in sorted(tables_reachable_from_projects()):
        assert await count_rows(db_session, table_name) == 1, (
            f"{table_name}: es sollte genau die Zeile von '{kept.project_name}' uebrig bleiben."
        )
    assert await count_rows(db_session, "projects") == 1
    # Projektuebergreifendes Vokabular und Nutzer bleiben unangetastet (ADR 0032).
    assert await count_rows(db_session, "fine_labels") == 1
    assert await count_rows(db_session, "users") == 1


async def test_delete_projects_without_ids_deletes_nothing(db_session: AsyncSession) -> None:
    kept = await build_project_graph(db_session, "Behalten")
    await db_session.commit()

    await delete_projects(db_session, [])
    await db_session.commit()

    assert await count_rows(db_session, "projects") == 1
    assert await count_rows(db_session, "photos") == 1
    assert kept.project_id is not None


async def test_delete_projects_returns_deleted_row_counts_per_table(
    db_session: AsyncSession,
) -> None:
    """Die Rueckgabe ist die Grundlage der INFO-Logzeile des Endpunkts."""
    graph = await build_project_graph(db_session, "Weg")
    await db_session.commit()

    deleted = await delete_projects(db_session, [graph.project_id])
    await db_session.commit()

    assert deleted["projects"] == 1
    assert deleted["photos"] == 1
    assert deleted["photo_rankings"] == 1
    assert set(deleted) == tables_reachable_from_projects() | {"projects"}


async def test_collect_photo_cache_keys_returns_id_and_etag_of_project_photos(
    db_session: AsyncSession,
) -> None:
    kept = await build_project_graph(db_session, "Behalten")
    doomed = await build_project_graph(db_session, "Weg")
    await db_session.commit()

    keys = await collect_photo_cache_keys(db_session, [doomed.project_id])

    assert keys == [(doomed.photo_id, doomed.photo_etag)]
    assert (kept.photo_id, kept.photo_etag) not in keys


async def test_collect_photo_cache_keys_without_ids_is_empty(db_session: AsyncSession) -> None:
    await build_project_graph(db_session, "Behalten")
    await db_session.commit()

    assert await collect_photo_cache_keys(db_session, []) == []
