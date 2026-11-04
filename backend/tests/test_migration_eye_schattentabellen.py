"""Spec 0609 / ADR 0138 - die Eye-Schattentabellen und der Laufmodus.

Rein additiv plus drei NULLABLE Spalten an `criterion_scoring_runs`: keine bestehende Zeile wird
gefasst, kein Bestand umgeschrieben. Fuenf Aussagen tragen mehr als die reine Spaltenform:

* `photo_eye_results.excluded_document` ist NOT NULL **ohne** jeden Default, weder Python- noch
  server-seitig - derselbe Grund wie bei `photo_motif_assessments`: ein Schreibpfad, der die
  Spalte vergisst, soll laut an der Bedingung scheitern statt still ein Foto aus jeder
  Motivauswahl zu nehmen.
* `album_level` ist auf 1..5 begrenzt, nicht nur ein Integer.
* Die Kindzeilen haengen an `photo_eye_results`, die Schnappschuss-Staerken an
  `photo_local_motif_snapshots` - beide also an einer Kopfzeile, nicht direkt am Foto.
* `criterion_scoring_runs.mode` ist NULLABLE: Altzeilen bleiben `NULL` und werden nie
  nachtraeglich einem Weg zugeschlagen. `eye_photos_total`/`_processed` sind ebenfalls NULLABLE,
  `NULL` heisst "Phase lief nicht" (Muster `persons_*`).
* Der Rueckweg nimmt alle fuenf Tabellen und die drei Spalten wieder weg - Daten gehen dabei
  verloren, und der Docstring sagt das.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

_MIGRATION_FILENAME = "8cf920dd03b4_eye_schattentabellen.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)

_NEW_TABLES = (
    "photo_eye_results",
    "photo_eye_motif_strengths",
    "photo_eye_fine_labels",
    "photo_local_motif_snapshots",
    "photo_local_motif_snapshot_strengths",
)

_RUN_COLUMNS = ("mode", "eye_photos_total", "eye_photos_processed")


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("eye_schattentabellen_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die Tabellen,
    auf die die neuen Spalten und Fremdschluessel zeigen."""
    connection.execute(
        text(
            "CREATE TABLE projects ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "name VARCHAR NOT NULL, "
            "opencloud_drive_id VARCHAR NOT NULL, "
            "opencloud_path VARCHAR NOT NULL)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE photos ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "project_id INTEGER NOT NULL, "
            "relative_path VARCHAR NOT NULL)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE criterion_scoring_runs (id INTEGER NOT NULL PRIMARY KEY, status VARCHAR)"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _columns(connection: Connection, table: str) -> dict[str, dict[str, object]]:
    return {column["name"]: column for column in inspect(connection).get_columns(table)}


def test_revision_chains_onto_the_current_head() -> None:
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head. Die Kette selbst
    prueft `test_migration_chain.py`."""
    module = _load_migration_module()

    assert module.down_revision == "0b9d6f8d620b"


def test_the_upgrade_creates_photo_eye_results_with_exactly_the_expected_columns(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, "photo_eye_results")

    assert set(columns) == {
        "photo_id",
        "excluded_document",
        "album_level",
        "model_revision",
        "computed_at",
    }


def test_the_exclusion_of_photo_eye_results_is_not_null_and_has_no_default(
    tmp_path: Path,
) -> None:
    """Der Ausschluss ist eine ENTSCHEIDUNG, kein Vorgabewert: `NULL` waere "nicht beurteilt", und
    ein Default naehme still jedes Foto aus jeder Motivauswahl (Spec 0609, S8)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, "photo_eye_results")

    assert not columns["excluded_document"]["nullable"]
    assert columns["excluded_document"]["default"] is None


def test_album_level_is_constrained_to_one_through_five(tmp_path: Path) -> None:
    """`album_level` ist die Eye-Albumstufe 1..5. Ein freier Integer liesse 0 oder 7 zu, und die
    Anzeige muesste an jeder Stelle erneut raten, was ein Wert bedeutet."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        checks = inspect(connection).get_check_constraints("photo_eye_results")

    assert any("album_level" in check["sqltext"] for check in checks)


def test_every_shadow_table_exists_after_the_upgrade(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        tables = set(inspect(connection).get_table_names())

    assert set(_NEW_TABLES) <= tables


def test_the_run_gains_the_mode_and_the_eye_counters(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, "criterion_scoring_runs")

    for column in _RUN_COLUMNS:
        assert column in columns
        # NULLABLE: Altzeilen bleiben ohne Weg und ohne Zaehler, nie nachtraeglich zugeordnet.
        assert columns[column]["nullable"]


def test_the_downgrade_drops_the_tables_and_the_run_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

        tables = set(inspect(connection).get_table_names())
        run_columns = _columns(connection, "criterion_scoring_runs")

    for table in _NEW_TABLES:
        assert table not in tables
    for column in _RUN_COLUMNS:
        assert column not in run_columns
