from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

# specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, decisions/0059-modellwahl-je-anbieter-
# und-modellgebundene-kostenschaetzung.md Punkt 6: rein additive Migration - je eine Modellspalte
# an criterion_scoring_runs und remote_category_classification_runs, keine Datenmigration.
# Isoliert ueber genau diese eine Revision, ohne von der vollen Migrationshistorie abzuhaengen
# (Muster der bestehenden test_migration_*.py).

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "5ab22032843c_run_vision_model.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("run_vision_model_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration (Revision
    f4a5b6c7d8e9) - nur die beiden beruehrten Run-Tabellen, reduziert auf die Spalten, die die
    Tests brauchen."""
    connection.execute(
        text(
            "CREATE TABLE criterion_scoring_runs ("
            "id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, "
            "scoring_run_id INTEGER NOT NULL, status VARCHAR(20) NOT NULL, "
            "landmark_cost_usd FLOAT)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE remote_category_classification_runs ("
            "id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, status VARCHAR(20) NOT NULL, "
            "cost_usd FLOAT)"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def test_revision_chains_onto_the_cost_tracking_head() -> None:
    module = _load_migration_module()

    assert module.down_revision == "f4a5b6c7d8e9"


def test_migration_adds_both_model_columns(tmp_path: Path) -> None:
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

    assert "landmark_model" in criterion_columns
    assert "model" in remote_columns


def test_both_columns_are_nullable(tmp_path: Path) -> None:
    """`NULL` = "nicht erfasst" ist die tragende Semantik (ADR 0059 Punkt 6) - eine
    NOT-NULL-Spalte machte sie unmoeglich."""
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

    assert nullable_by_name[("criterion_scoring_runs", "landmark_model")]
    assert nullable_by_name[("remote_category_classification_runs", "model")]


def test_existing_rows_keep_null_instead_of_a_default_model(tmp_path: Path) -> None:
    """DER Kern dieser Migration: Bestandszeilen behalten `NULL`. Ein `server_default` mit dem
    damaligen Voreinstellungs-Modell waere eine Behauptung ueber die Vergangenheit, die diese
    Migration nicht belegen kann - und sie waere unumkehrbar, weil "nicht erfasst" danach nicht
    mehr von "mit genau diesem Modell gelaufen" zu unterscheiden waere."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            connection.execute(
                text(
                    "INSERT INTO criterion_scoring_runs "
                    "(id, project_id, scoring_run_id, status) VALUES (1, 1, 1, 'success')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO remote_category_classification_runs "
                    "(id, project_id, status) VALUES (1, 1, 'success')"
                )
            )
            _apply(connection, "upgrade")

        with engine.connect() as connection:
            criterion_model = connection.execute(
                text("SELECT landmark_model FROM criterion_scoring_runs WHERE id = 1")
            ).scalar_one()
            remote_model = connection.execute(
                text("SELECT model FROM remote_category_classification_runs WHERE id = 1")
            ).scalar_one()
    finally:
        engine.dispose()

    assert criterion_model is None
    assert remote_model is None


def test_downgrade_removes_both_columns_again(tmp_path: Path) -> None:
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

    assert "landmark_model" not in criterion_columns
    assert "model" not in remote_columns
    # Die Kostenspalten der Vorgaenger-Revision bleiben unberuehrt.
    assert "landmark_cost_usd" in criterion_columns
    assert "cost_usd" in remote_columns
