from __future__ import annotations

from pathlib import Path

from sqlalchemy import Connection, create_engine, inspect, text

from tests.support.migration import apply_migration

# specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, decisions/0050-verketteter-
# klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md Punkt 3: rein additive Migration - drei
# neue Spalten auf criterion_scoring_runs, keine Datenmigration. Isoliert ueber genau diese eine
# Revision, ohne von der vollen Migrationshistorie abzuhaengen (analog
# test_migration_cloud_vision_errors.py).

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "e2f3a4b5c6d7_classification_run_cloud_phase.py"
)


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration (Revision
    d5e6f7a8b9c0) - nur die von e2f3a4b5c6d7 tatsaechlich beruehrte Tabelle
    criterion_scoring_runs, reduziert auf die Spalten, die die Tests brauchen."""
    connection.execute(
        text(
            "CREATE TABLE criterion_scoring_runs ("
            "id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, "
            "scoring_run_id INTEGER NOT NULL, status VARCHAR(20) NOT NULL)"
        )
    )


def test_migration_adds_the_three_classification_run_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            apply_migration(connection, "upgrade", path=_MIGRATION_PATH)

        columns = {col["name"] for col in inspect(engine).get_columns("criterion_scoring_runs")}
    finally:
        engine.dispose()

    assert {"phase", "cloud_requested", "cloud_error_message"} <= columns


def test_existing_rows_get_cloud_requested_false_and_no_phase(tmp_path: Path) -> None:
    """Altzeilen aus der Zeit der getrennten Ausloesung: `cloud_requested=false` ist die Antwort,
    die nichts Falsches verspricht (die Frage ist nachtraeglich nicht beantwortbar), `phase=NULL`
    heisst "laeuft nicht mehr" (Spec 0296, Datenmodell-Bezug)."""
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
            apply_migration(connection, "upgrade", path=_MIGRATION_PATH)

        with engine.begin() as connection:
            row = connection.execute(
                text(
                    "SELECT phase, cloud_requested, cloud_error_message "
                    "FROM criterion_scoring_runs WHERE id = 1"
                )
            ).one()
    finally:
        engine.dispose()

    assert row.phase is None
    assert not row.cloud_requested
    assert row.cloud_error_message is None


def test_downgrade_removes_the_three_columns_again(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            apply_migration(connection, "upgrade", path=_MIGRATION_PATH)
            apply_migration(connection, "downgrade", path=_MIGRATION_PATH)

        columns = {col["name"] for col in inspect(engine).get_columns("criterion_scoring_runs")}
    finally:
        engine.dispose()

    assert {"phase", "cloud_requested", "cloud_error_message"}.isdisjoint(columns)
    assert {"id", "project_id", "scoring_run_id", "status"} <= columns
