"""Die Fassung der Eye-Uebersetzung je Ergebniszeile.

Additiv, eine Spalte. Zwei Aussagen tragen mehr als die reine Spaltenform:

* Bestehende Zeilen erhalten `eye-4.2.3/v1` - sie sind alle mit v1 entstanden - und behalten
  jede andere Spalte unveraendert.
* Danach ist `mapping_version` NOT NULL **ohne** bleibenden Default: der `server_default`
  dient nur dem Nachtragen. Ein Schreibpfad, der die Spalte vergisst, scheitert laut, statt still
  "v1" zu behaupten.
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

_MIGRATION_FILENAME = "5c7633e53257_eye_mapping_version.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("eye_mapping_version_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Der Stand von `photo_eye_results` unmittelbar VOR dieser Migration, mit einer Altzeile."""
    connection.execute(text("CREATE TABLE photos (id INTEGER NOT NULL PRIMARY KEY)"))
    connection.execute(
        text(
            "CREATE TABLE photo_eye_results ("
            "photo_id INTEGER NOT NULL PRIMARY KEY REFERENCES photos (id), "
            "excluded_document BOOLEAN NOT NULL, "
            "album_level INTEGER NOT NULL, "
            "model_revision VARCHAR NOT NULL, "
            "computed_at DATETIME NOT NULL, "
            "CONSTRAINT ck_photo_eye_results_album_level CHECK (album_level BETWEEN 1 AND 5))"
        )
    )
    connection.execute(text("INSERT INTO photos (id) VALUES (1), (2)"))
    connection.execute(
        text(
            "INSERT INTO photo_eye_results "
            "(photo_id, excluded_document, album_level, model_revision, computed_at) "
            "VALUES (1, 1, 4, 'v1.0.0', '2026-11-01 10:00:00')"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _columns(connection: Connection) -> dict[str, dict[str, object]]:
    return {
        column["name"]: column for column in inspect(connection).get_columns("photo_eye_results")
    }


def test_revision_chains_onto_the_current_head() -> None:
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head. Die Kette selbst
    prueft `test_migration_chain.py`."""
    module = _load_migration_module()

    assert module.revision == "5c7633e53257"
    assert module.down_revision == "44ba5fe0184a"


def test_an_existing_row_gets_v1_and_keeps_every_other_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        row = connection.execute(
            text(
                "SELECT photo_id, excluded_document, album_level, model_revision, computed_at, "
                "mapping_version FROM photo_eye_results"
            )
        ).one()

    assert tuple(row) == (1, 1, 4, "v1.0.0", "2026-11-01 10:00:00", "eye-4.2.3/v1")


def test_the_column_is_not_null_without_a_lasting_default(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        column = _columns(connection)["mapping_version"]

    assert column["nullable"] is False
    assert column["default"] is None


def test_an_insert_without_a_version_fails(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text(
                "INSERT INTO photo_eye_results "
                "(photo_id, excluded_document, album_level, model_revision, computed_at) "
                "VALUES (2, 0, 3, 'v1.0.0', '2026-11-02 10:00:00')"
            )
        )


def test_the_album_level_constraint_survives_the_table_rebuild(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        checks = inspect(connection).get_check_constraints("photo_eye_results")

    assert any("album_level" in check["sqltext"] for check in checks)


def test_the_downgrade_drops_the_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")
        columns = _columns(connection)
        count = connection.execute(text("SELECT COUNT(*) FROM photo_eye_results")).scalar_one()

    assert "mapping_version" not in columns
    assert set(columns) == {
        "photo_id",
        "excluded_document",
        "album_level",
        "model_revision",
        "computed_at",
    }
    assert count == 1
