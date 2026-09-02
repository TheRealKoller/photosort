from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md Punkt 3: rein additive Migration - je vier Kostenspalten an criterion_scoring_runs und
# remote_category_classification_runs, keine Datenmigration. Isoliert ueber genau diese eine
# Revision, ohne von der vollen Migrationshistorie abzuhaengen (Muster der bestehenden
# test_migration_*.py).

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "f4a5b6c7d8e9_remote_cost_tracking.py"
)

_LANDMARK_COLUMNS = {
    "landmark_api_calls",
    "landmark_input_tokens",
    "landmark_output_tokens",
    "landmark_cost_usd",
}
_REMOTE_CATEGORY_COLUMNS = {"api_calls", "input_tokens", "output_tokens", "cost_usd"}


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("remote_cost_tracking_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration (Revision
    e2f3a4b5c6d7) - nur die beiden tatsaechlich beruehrten Run-Tabellen, reduziert auf die
    Spalten, die die Tests brauchen."""
    connection.execute(
        text(
            "CREATE TABLE criterion_scoring_runs ("
            "id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, "
            "scoring_run_id INTEGER NOT NULL, status VARCHAR(20) NOT NULL)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE remote_category_classification_runs ("
            "id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, status VARCHAR(20) NOT NULL)"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def test_revision_chains_onto_the_current_head() -> None:
    module = _load_migration_module()

    assert module.down_revision == "e2f3a4b5c6d7"


def test_migration_adds_all_eight_cost_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")

        inspector = inspect(engine)
        criterion_columns = {c["name"] for c in inspector.get_columns("criterion_scoring_runs")}
        remote_columns = {
            c["name"] for c in inspector.get_columns("remote_category_classification_runs")
        }
    finally:
        engine.dispose()

    assert _LANDMARK_COLUMNS <= criterion_columns
    assert _REMOTE_CATEGORY_COLUMNS <= remote_columns


def test_all_eight_columns_are_nullable(tmp_path: Path) -> None:
    """`NULL` = "nicht erfasst" ist die tragende Semantik dieser Migration (ADR 0051 Punkt 3) -
    eine NOT-NULL-Spalte wuerde sie unmoeglich machen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")

        inspector = inspect(engine)
        nullable_by_name = {
            (table, c["name"]): c["nullable"]
            for table in ("criterion_scoring_runs", "remote_category_classification_runs")
            for c in inspector.get_columns(table)
        }
    finally:
        engine.dispose()

    for column in _LANDMARK_COLUMNS:
        assert nullable_by_name[("criterion_scoring_runs", column)], column
    for column in _REMOTE_CATEGORY_COLUMNS:
        assert nullable_by_name[("remote_category_classification_runs", column)], column


def test_existing_rows_keep_null_instead_of_zero(tmp_path: Path) -> None:
    """DER Kern dieser Migration: Bestandszeilen behalten `NULL`, NICHT `0` - sonst waere "nicht
    erfasst" nicht mehr von "kostenlos" unterscheidbar, und die Statistikseite wuerde fuer
    Altlaeufe "0,00 USD" ohne jeden Vorbehalt behaupten (ADR 0051 Punkt 5)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            connection.execute(
                text(
                    "INSERT INTO criterion_scoring_runs (id, project_id, scoring_run_id, status) "
                    "VALUES (1, 1, 1, 'success')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO remote_category_classification_runs (id, project_id, status) "
                    "VALUES (1, 1, 'success')"
                )
            )
            _apply(connection, "upgrade")

        with engine.begin() as connection:
            criterion_row = connection.execute(
                text(
                    "SELECT landmark_api_calls, landmark_input_tokens, landmark_output_tokens, "
                    "landmark_cost_usd FROM criterion_scoring_runs WHERE id = 1"
                )
            ).one()
            remote_row = connection.execute(
                text(
                    "SELECT api_calls, input_tokens, output_tokens, cost_usd "
                    "FROM remote_category_classification_runs WHERE id = 1"
                )
            ).one()
    finally:
        engine.dispose()

    assert list(criterion_row) == [None, None, None, None]
    assert list(remote_row) == [None, None, None, None]


def test_downgrade_removes_the_eight_columns_again(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")
            _apply(connection, "downgrade")

        inspector = inspect(engine)
        criterion_columns = {c["name"] for c in inspector.get_columns("criterion_scoring_runs")}
        remote_columns = {
            c["name"] for c in inspector.get_columns("remote_category_classification_runs")
        }
    finally:
        engine.dispose()

    assert _LANDMARK_COLUMNS.isdisjoint(criterion_columns)
    assert _REMOTE_CATEGORY_COLUMNS.isdisjoint(remote_columns)
    # Der uebrige Datenbestand bleibt unberuehrt - der downgrade ist verlustbehaftet, aber
    # schema-vollstaendig umkehrbar.
    assert {"id", "project_id", "scoring_run_id", "status"} <= criterion_columns
    assert {"id", "project_id", "status"} <= remote_columns
