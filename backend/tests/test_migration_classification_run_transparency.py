from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

# specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-vier-
# teilschritte-und-laufeigene-cloud-bilanz.md Punkt 2/3/5: rein additive Migration - fuenf neue
# Spalten plus ein FREMDSCHLUESSEL auf criterion_scoring_runs, eine neue Spalte auf
# remote_category_classification_runs. Kein server_default, kein Backfill, keine Datenmigration.
# Isoliert ueber genau diese eine Revision, ohne von der vollen Migrationshistorie abzuhaengen
# (Muster: test_migration_classification_run_cloud_phase.py).

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "b8c9d0e1f2a3_classification_run_transparency.py"
)

_NEW_CRITERION_SCORING_RUN_COLUMNS = {
    "landmark_photos_total",
    "landmark_photos_processed",
    "landmark_failed_calls",
    "estimated_cost_usd",
    "remote_category_classification_run_id",
}


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "classification_run_transparency_migration", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration (Revision
    a3b4c5d6e7f8) - nur die beiden tatsaechlich beruehrten Tabellen, reduziert auf die Spalten,
    die die Tests brauchen. `remote_category_classification_runs` muss dabei existieren, sonst
    haette der neue Fremdschluessel kein Ziel."""
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


def test_upgrade_adds_the_five_columns_and_the_foreign_key_to_criterion_scoring_runs(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply_upgrade(connection)

        columns = {col["name"] for col in inspect(engine).get_columns("criterion_scoring_runs")}
    finally:
        engine.dispose()

    assert _NEW_CRITERION_SCORING_RUN_COLUMNS <= columns


def test_upgrade_adds_failed_calls_to_remote_category_classification_runs(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply_upgrade(connection)

        columns = {
            col["name"]
            for col in inspect(engine).get_columns("remote_category_classification_runs")
        }
    finally:
        engine.dispose()

    assert "failed_calls" in columns


def test_no_new_column_has_a_server_default(tmp_path: Path) -> None:
    """Ein `server_default='0'` an `landmark_photos_total` loeschte den MARKER "dieser Teilschritt
    fand statt" unumkehrbar (ADR 0068 Punkt 2: `NULL` = Phase nicht betreten, `0` = betreten und
    nichts zu tun). Jede Bestandszeile saehe danach aus wie ein Lauf mit leerer Landmark-Phase,
    und die Bilanz zeigte fuer Altlaeufe erfundene Nullwerte statt "nicht erfasst". Dasselbe gilt
    fuer `estimated_cost_usd`: ein `0.0` behauptete eine Kostenschaetzung, die niemand getroffen
    hat."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply_upgrade(connection)

        inspector = inspect(engine)
        defaults = {
            col["name"]: col["default"]
            for col in inspector.get_columns("criterion_scoring_runs")
            if col["name"] in _NEW_CRITERION_SCORING_RUN_COLUMNS
        }
        defaults.update(
            {
                col["name"]: col["default"]
                for col in inspector.get_columns("remote_category_classification_runs")
                if col["name"] == "failed_calls"
            }
        )
    finally:
        engine.dispose()

    assert set(defaults) == _NEW_CRITERION_SCORING_RUN_COLUMNS | {"failed_calls"}
    assert all(default is None for default in defaults.values()), defaults


def test_existing_rows_keep_null_in_every_new_column(tmp_path: Path) -> None:
    """Kein Backfill: eine Zeile aus der Zeit vor dieser Revision hat die Landmark-Phase nie mit
    Live-Zaehlern erfasst und trug nie eine eingefrorene Schaetzung. `NULL` ist dafuer die einzige
    ehrliche Antwort - die Oberflaeche sagt daraufhin "keine Cloud-Bilanz erfasst"."""
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
            _apply_upgrade(connection)

        with engine.begin() as connection:
            criterion_row = connection.execute(
                text(
                    "SELECT landmark_photos_total, landmark_photos_processed, "
                    "landmark_failed_calls, estimated_cost_usd, "
                    "remote_category_classification_run_id "
                    "FROM criterion_scoring_runs WHERE id = 1"
                )
            ).one()
            remote_row = connection.execute(
                text("SELECT failed_calls FROM remote_category_classification_runs WHERE id = 1")
            ).one()
    finally:
        engine.dispose()

    assert all(value is None for value in criterion_row)
    assert remote_row.failed_calls is None


def test_the_foreign_key_targets_remote_category_classification_runs(tmp_path: Path) -> None:
    """Unter SQLite entsteht ein nachtraeglich hinzugefuegter Fremdschluessel AUSSCHLIESSLICH
    ueber `batch_alter_table` (Tabellen-Neuaufbau) - ein vergessener `batch`-Block liesse die
    Spalte entstehen und die Kante fehlen, ohne dass eine Spaltenpruefung das saehe."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply_upgrade(connection)

        foreign_keys = inspect(engine).get_foreign_keys("criterion_scoring_runs")
    finally:
        engine.dispose()

    matching = [
        fk
        for fk in foreign_keys
        if fk["constrained_columns"] == ["remote_category_classification_run_id"]
    ]
    assert len(matching) == 1, foreign_keys
    assert matching[0]["referred_table"] == "remote_category_classification_runs"
    assert matching[0]["referred_columns"] == ["id"]
    # Security-Muss der Spec: ein UNBENANNTER Constraint ist im downgrade() unter SQLite nicht
    # droppbar - der Rueckwaertsweg der Migration waere nicht ausfuehrbar.
    assert matching[0]["name"]


def test_downgrade_removes_every_new_column_and_the_foreign_key(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply_upgrade(connection)
            _apply_downgrade(connection)

        inspector = inspect(engine)
        criterion_columns = {col["name"] for col in inspector.get_columns("criterion_scoring_runs")}
        remote_columns = {
            col["name"] for col in inspector.get_columns("remote_category_classification_runs")
        }
        foreign_keys = inspector.get_foreign_keys("criterion_scoring_runs")
    finally:
        engine.dispose()

    assert _NEW_CRITERION_SCORING_RUN_COLUMNS.isdisjoint(criterion_columns)
    assert "failed_calls" not in remote_columns
    assert {"id", "project_id", "scoring_run_id", "status"} <= criterion_columns
    assert foreign_keys == []
