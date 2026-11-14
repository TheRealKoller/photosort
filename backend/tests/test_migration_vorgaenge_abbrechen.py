"""Die Migration des Abbruchmerkers: sechs nullable Spalten `cancel_requested_at`, kein Backfill.

Die neuen Statuswerte `queued`/`cancelled` brauchen kein DDL (`native_enum=False`, ohne
CHECK-Constraint) - geprueft wird deshalb nur, dass beide Enums sie tragen.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

from photosort.models import (
    ClassificationReview,
    CriterionScoringRun,
    ExportRun,
    ExportRunStatus,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
)

_MIGRATION_FILENAME = "2be43c4b5fb7_vorgaenge_abbrechen.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)

_TABLES = (
    "scan_runs",
    "scoring_runs",
    "criterion_scoring_runs",
    "remote_category_classification_runs",
    "export_runs",
    "classification_reviews",
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("cancel_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    for table in _TABLES:
        connection.execute(
            text(
                f"CREATE TABLE {table} ("
                "id INTEGER NOT NULL PRIMARY KEY, "
                "status VARCHAR(20) NOT NULL)"
            )
        )
        connection.execute(text(f"INSERT INTO {table} (id, status) VALUES (1, 'RUNNING')"))


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _columns(connection: Connection, table: str) -> dict[str, dict[str, object]]:
    return {column["name"]: column for column in inspect(connection).get_columns(table)}


def test_revision_chains_onto_the_current_head() -> None:
    module = _load_migration_module()

    assert module.revision == "2be43c4b5fb7"
    assert module.down_revision == "8c0f0296e1cd"


def test_the_upgrade_adds_a_nullable_cancel_column_without_backfill(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = {table: _columns(connection, table) for table in _TABLES}
        values = {
            table: connection.execute(
                text(f"SELECT cancel_requested_at FROM {table} WHERE id = 1")
            ).scalar_one()
            for table in _TABLES
        }

    for table in _TABLES:
        assert set(columns[table]) == {"id", "status", "cancel_requested_at"}
        assert columns[table]["cancel_requested_at"]["nullable"] is True
        assert values[table] is None


def test_the_downgrade_drops_exactly_the_cancel_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

        columns = {table: _columns(connection, table) for table in _TABLES}
        rows = {
            table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            for table in _TABLES
        }

    for table in _TABLES:
        assert set(columns[table]) == {"id", "status"}
        assert rows[table] == 1


@pytest.mark.parametrize("enum", [ScanStatus, ExportRunStatus])
def test_both_status_enums_know_queued_and_cancelled(enum: type) -> None:
    assert enum("queued").name == "QUEUED"
    assert enum("cancelled").name == "CANCELLED"


@pytest.mark.parametrize(
    "model",
    [
        ScanRun,
        ScoringRun,
        CriterionScoringRun,
        RemoteCategoryClassificationRun,
        ExportRun,
        ClassificationReview,
    ],
)
def test_every_run_model_carries_the_cancel_column(model: type) -> None:
    column = model.__table__.columns["cancel_requested_at"]  # type: ignore[attr-defined]

    assert column.nullable is True
    assert column.default is None
    assert column.server_default is None
