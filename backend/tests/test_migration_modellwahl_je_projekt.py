"""Die Migration der Modellwahl je Projekt: drei additive Spalten und ein Check-Constraint.

`category_method` ist NOT NULL mit `server_default 'cloud'` - Bestandsprojekte laufen damit
unveraendert ueber die Cloud, ohne Datenwanderung. `category_model` und `landmark_model` sind
nullbar; `NULL` heisst "Installationsvorgabe".

Der Check-Constraint `ck_projects_category_model_requires_cloud` macht die Zeile "Eye mit
Cloud-Modell" unmoeglich. Der Rueckwaertsweg entfernt Spalten und Constraint; Daten gehen dabei
verloren.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

_MIGRATION_FILENAME = "43a3afeb7312_modellwahl_je_projekt.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("modellwahl_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration."""
    connection.execute(
        text(
            "CREATE TABLE projects ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "name VARCHAR NOT NULL, "
            "opencloud_drive_id VARCHAR NOT NULL, "
            "opencloud_path VARCHAR NOT NULL, "
            "created_at DATETIME, "
            "cloud_vision_detection_enabled BOOLEAN NOT NULL, "
            "cloud_vision_consent_at DATETIME, "
            "selection_target INTEGER)"
        )
    )


def _insert_existing_project(connection: Connection, *, project_id: int = 1) -> None:
    connection.execute(
        text(
            "INSERT INTO projects (id, name, opencloud_drive_id, opencloud_path, created_at, "
            "cloud_vision_detection_enabled, cloud_vision_consent_at, selection_target) VALUES "
            f"({project_id}, 'Projekt {project_id}', 'drive-{project_id}', '/pfad/{project_id}', "
            "'2026-07-20 10:00:00', 0, NULL, NULL)"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _columns(connection: Connection) -> dict[str, dict[str, object]]:
    return {column["name"]: column for column in inspect(connection).get_columns("projects")}


def _check_constraints(connection: Connection) -> dict[str, str]:
    return {
        check["name"]: check["sqltext"]
        for check in inspect(connection).get_check_constraints("projects")
    }


def test_revision_chains_onto_the_current_head() -> None:
    module = _load_migration_module()

    assert module.revision == "43a3afeb7312"
    assert module.down_revision == "5c7633e53257"


def test_an_existing_project_stays_on_cloud_without_a_model(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_project(connection)
        _apply(connection, "upgrade")

        row = connection.execute(
            text(
                "SELECT category_method, category_model, landmark_model FROM projects WHERE id = 1"
            )
        ).one()

    assert tuple(row) == ("cloud", None, None)


def test_the_method_is_not_null_with_a_lasting_cloud_default(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection)
        connection.execute(
            text(
                "INSERT INTO projects (id, name, opencloud_drive_id, opencloud_path, created_at, "
                "cloud_vision_detection_enabled, cloud_vision_consent_at, selection_target) VALUES "
                "(7, 'Ohne Wahl', 'drive', '/pfad', '2026-07-20 10:00:00', 0, NULL, NULL)"
            )
        )
        method = connection.execute(
            text("SELECT category_method FROM projects WHERE id = 7")
        ).scalar_one()

    assert columns["category_method"]["nullable"] is False
    assert columns["category_method"]["default"] is not None
    assert "cloud" in str(columns["category_method"]["default"])
    assert columns["category_model"]["nullable"] is True
    assert columns["category_model"]["default"] is None
    assert columns["landmark_model"]["nullable"] is True
    assert columns["landmark_model"]["default"] is None
    assert method == "cloud"


def test_eye_with_a_cloud_model_is_rejected_by_the_constraint(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_project(connection)
        _apply(connection, "upgrade")

        checks = _check_constraints(connection)
        connection.execute(
            text("UPDATE projects SET category_method = 'eye', landmark_model = 'x' WHERE id = 1")
        )
        try:
            connection.execute(
                text("UPDATE projects SET category_model = 'claude-haiku-4-5' WHERE id = 1")
            )
        except IntegrityError:
            rejected = True
        else:
            rejected = False

    assert "ck_projects_category_model_requires_cloud" in checks
    assert rejected is True


def test_a_cloud_method_with_a_model_is_accepted(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_project(connection)
        _apply(connection, "upgrade")

        connection.execute(
            text("UPDATE projects SET category_model = 'claude-haiku-4-5' WHERE id = 1")
        )
        row = connection.execute(
            text("SELECT category_method, category_model FROM projects WHERE id = 1")
        ).one()

    assert tuple(row) == ("cloud", "claude-haiku-4-5")


def test_the_downgrade_drops_the_columns_and_the_constraint(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_project(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

        columns = _columns(connection)
        checks = _check_constraints(connection)
        count = connection.execute(text("SELECT COUNT(*) FROM projects")).scalar_one()

    assert "category_method" not in columns
    assert "category_model" not in columns
    assert "landmark_model" not in columns
    assert "ck_projects_category_model_requires_cloud" not in checks
    assert count == 1
