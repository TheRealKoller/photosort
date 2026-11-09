"""Die Migration der Albumstufen-Quelle am Lauf: eine additive Spalte an `criterion_scoring_runs`.

`album_level_source` ist NOT NULL mit bleibendem `server_default 'cloud'` - jeder fruehere Lauf las
`photo_album_suitability`, Altzeilen tragen damit wahrheitsgemaess `cloud`. Der Rueckweg entfernt
die Spalte.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

_MIGRATION_FILENAME = "6299223059c8_album_level_source.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("album_level_source_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration."""
    connection.execute(
        text(
            "CREATE TABLE criterion_scoring_runs ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "project_id INTEGER NOT NULL, "
            "scoring_run_id INTEGER NOT NULL, "
            "status VARCHAR(20) NOT NULL, "
            "mode VARCHAR(20))"
        )
    )


def _insert_existing_run(connection: Connection, *, run_id: int = 1) -> None:
    connection.execute(
        text(
            "INSERT INTO criterion_scoring_runs (id, project_id, scoring_run_id, status, mode) "
            f"VALUES ({run_id}, 1, 1, 'success', NULL)"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _columns(connection: Connection) -> dict[str, dict[str, object]]:
    return {
        column["name"]: column
        for column in inspect(connection).get_columns("criterion_scoring_runs")
    }


def test_revision_chains_onto_the_current_head() -> None:
    module = _load_migration_module()

    assert module.revision == "6299223059c8"
    assert module.down_revision == "43a3afeb7312"


def test_an_existing_run_reads_cloud_after_the_upgrade(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_run(connection)
        _apply(connection, "upgrade")

        source = connection.execute(
            text("SELECT album_level_source FROM criterion_scoring_runs WHERE id = 1")
        ).scalar_one()

    assert source == "cloud"


def test_the_column_is_not_null_with_a_lasting_cloud_default(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection)
        _insert_existing_run(connection, run_id=7)
        source = connection.execute(
            text("SELECT album_level_source FROM criterion_scoring_runs WHERE id = 7")
        ).scalar_one()

    assert columns["album_level_source"]["nullable"] is False
    assert "cloud" in str(columns["album_level_source"]["default"])
    assert source == "cloud"


def test_the_downgrade_drops_the_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_run(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

        columns = _columns(connection)
        count = connection.execute(text("SELECT COUNT(*) FROM criterion_scoring_runs")).scalar_one()

    assert "album_level_source" not in columns
    assert count == 1
