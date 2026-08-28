from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

# specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
# fehler-persistierung.md Punkt 2: additive Migration - neue Tabelle photo_cloud_vision_errors,
# composite PK (photo_id, phase), kein Verlauf. Isoliert ueber genau diese eine Revision, ohne von
# der vollen Migrationshistorie abzuhaengen (analog
# test_migration_remote_category_classification.py).

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "c2d3e4f5a6b7_cloud_vision_errors.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("cloud_vision_errors_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration (Revision
    b3c4d5e6f7a8) - nur die von c2d3e4f5a6b7 tatsaechlich beruehrte Tabelle photos."""
    connection.execute(text("CREATE TABLE photos (id INTEGER PRIMARY KEY)"))


def _apply_upgrade(connection: Connection) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        module.upgrade()


def _apply_downgrade(connection: Connection) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        module.downgrade()


def test_migration_creates_the_photo_cloud_vision_errors_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply_upgrade(connection)

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        columns = {col["name"] for col in inspector.get_columns("photo_cloud_vision_errors")}
        pk_constraint = inspector.get_pk_constraint("photo_cloud_vision_errors")
    finally:
        engine.dispose()

    assert "photo_cloud_vision_errors" in table_names
    assert columns == {"photo_id", "phase", "error_type", "error_message", "attempted_at"}
    assert set(pk_constraint["constrained_columns"]) == {"photo_id", "phase"}


def test_migration_allows_inserting_a_row(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            connection.execute(text("INSERT INTO photos (id) VALUES (1)"))
            _apply_upgrade(connection)
            connection.execute(
                text(
                    "INSERT INTO photo_cloud_vision_errors "
                    "(photo_id, phase, error_type, error_message, attempted_at) "
                    "VALUES (1, 'landmark', 'LandmarkApiError', 'boom', '2026-01-01 00:00:00')"
                )
            )
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    "SELECT photo_id, phase, error_type, error_message, attempted_at "
                    "FROM photo_cloud_vision_errors"
                )
            ).fetchone()
    finally:
        engine.dispose()

    assert row == (1, "landmark", "LandmarkApiError", "boom", "2026-01-01 00:00:00")


def test_downgrade_drops_the_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply_upgrade(connection)
        with engine.begin() as connection:
            _apply_downgrade(connection)

        table_names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert "photo_cloud_vision_errors" not in table_names
