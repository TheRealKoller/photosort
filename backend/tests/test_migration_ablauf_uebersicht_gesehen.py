"""Die Migration des Merkers "Ablaufuebersicht gesehen": die Tabelle `project_overview_seen`.

Eine Zeile je Person und Projekt; ihre Abwesenheit heisst "nicht gesehen". Die Migration
schreibt keine Zeile - bestehende Projekte gelten damit fuer beide Personen als ungesehen.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

_MIGRATION_FILENAME = "1d3dbfdde02e_ablauf_uebersicht_gesehen.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)

_TABLE = "project_overview_seen"


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("ablauf_uebersicht_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die beiden
    Tabellen, auf die die Fremdschluessel zeigen."""
    connection.execute(
        text(
            "CREATE TABLE users (id INTEGER NOT NULL PRIMARY KEY, username VARCHAR NOT NULL, "
            "password_hash VARCHAR NOT NULL)"
        )
    )
    connection.execute(
        text("CREATE TABLE projects (id INTEGER NOT NULL PRIMARY KEY, name VARCHAR NOT NULL)")
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _migrated(tmp_path: Path) -> tuple[object, Connection]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    connection = engine.connect()
    _create_pre_migration_schema(connection)
    _apply(connection, "upgrade")
    return engine, connection


def test_revision_chains_onto_the_current_head() -> None:
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head. Die Kette selbst
    prueft `test_migration_chain.py`."""
    module = _load_migration_module()

    assert module.revision == "1d3dbfdde02e"
    assert module.down_revision == "b0814fc600bf"


def test_the_upgrade_creates_the_table_with_exactly_the_two_key_columns(tmp_path: Path) -> None:
    """GLEICHHEIT der Spaltenmenge: Ohne Zeitstempel gibt es nichts, was verfallen koennte - ein
    einmal geschlossener Ablauf bleibt auch an einem anderen Tag geschlossen."""
    _, connection = _migrated(tmp_path)
    with connection:
        columns = {column["name"] for column in inspect(connection).get_columns(_TABLE)}

    assert columns == {"user_id", "project_id"}


def test_both_columns_form_the_primary_key_and_carry_named_foreign_keys(tmp_path: Path) -> None:
    _, connection = _migrated(tmp_path)
    with connection:
        inspector = inspect(connection)
        primary_key = inspector.get_pk_constraint(_TABLE)
        foreign_keys = {fk["name"]: fk for fk in inspector.get_foreign_keys(_TABLE)}

    assert sorted(primary_key["constrained_columns"]) == ["project_id", "user_id"]
    assert set(foreign_keys) == {
        "fk_project_overview_seen_user_id",
        "fk_project_overview_seen_project_id",
    }
    assert foreign_keys["fk_project_overview_seen_user_id"]["referred_table"] == "users"
    assert foreign_keys["fk_project_overview_seen_user_id"]["constrained_columns"] == ["user_id"]
    assert foreign_keys["fk_project_overview_seen_project_id"]["referred_table"] == "projects"
    assert foreign_keys["fk_project_overview_seen_project_id"]["constrained_columns"] == [
        "project_id"
    ]


def test_the_upgrade_writes_no_row(tmp_path: Path) -> None:
    """Bestehende Projekte zaehlen als ungesehen: Die Migration legt keine Zeile an."""
    _, connection = _migrated(tmp_path)
    with connection:
        count = connection.execute(text(f"SELECT COUNT(*) FROM {_TABLE}")).scalar_one()  # noqa: S608

    assert count == 0


def test_a_second_row_for_the_same_person_and_project_is_structurally_impossible(
    tmp_path: Path,
) -> None:
    _, connection = _migrated(tmp_path)
    with connection:
        connection.execute(text(f"INSERT INTO {_TABLE} (user_id, project_id) VALUES (1, 1)"))  # noqa: S608
        with pytest.raises(IntegrityError):
            connection.execute(text(f"INSERT INTO {_TABLE} (user_id, project_id) VALUES (1, 1)"))  # noqa: S608


def test_the_downgrade_drops_the_table(tmp_path: Path) -> None:
    _, connection = _migrated(tmp_path)
    with connection:
        _apply(connection, "downgrade")
        tables = set(inspect(connection).get_table_names())

    assert _TABLE not in tables
