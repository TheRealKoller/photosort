from __future__ import annotations

from pathlib import Path

from sqlalchemy import Connection, create_engine, inspect, text

from tests.support.migration import apply_migration

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, Akzeptanzkriterium
# "Naming-Migration": Zwei-Revisionen-Test (Zeile mit alten Spaltennamen VOR der Migration
# einfuegen, nach der Migration Wert unter neuen Namen lesen) - analog
# test_migration_criterion_scoring_pipeline.py, isoliert ueber genau diese eine Revision, ohne von
# der Postgres-only-Historie der uebrigen Migrationen abhaengig zu sein.

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "b3c4d5e6f7a8_remote_category_classification.py"
)


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration (Revision
    a2b3c4d5e6f7) - nur die von b3c4d5e6f7a8 tatsaechlich beruehrten Tabellen/Spalten."""
    connection.execute(
        text(
            "CREATE TABLE projects ("
            "id INTEGER PRIMARY KEY, cloud_landmark_detection_enabled BOOLEAN, "
            "cloud_landmark_consent_at DATETIME)"
        )
    )
    connection.execute(text("CREATE TABLE photos (id INTEGER PRIMARY KEY)"))
    connection.execute(
        text(
            "CREATE TABLE photo_scores ("
            "photo_id INTEGER PRIMARY KEY, sharpness FLOAT, exposure FLOAT, phash VARCHAR, "
            "duplicate_of INTEGER, cluster_key VARCHAR, suggested_status VARCHAR(20), "
            "computed_at DATETIME)"
        )
    )


def test_naming_migration_preserves_the_value_across_the_rename(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            connection.execute(
                text(
                    "INSERT INTO projects "
                    "(id, cloud_landmark_detection_enabled, cloud_landmark_consent_at) "
                    "VALUES (1, 1, '2026-01-01 00:00:00')"
                )
            )
            apply_migration(connection, "upgrade", path=_MIGRATION_PATH)

        with engine.begin() as connection:
            row = connection.execute(
                text(
                    "SELECT cloud_vision_detection_enabled, cloud_vision_consent_at "
                    "FROM projects WHERE id = 1"
                )
            ).fetchone()
        columns = {col["name"] for col in inspect(engine).get_columns("projects")}
    finally:
        engine.dispose()

    assert row == (1, "2026-01-01 00:00:00")
    assert "cloud_landmark_detection_enabled" not in columns
    assert "cloud_landmark_consent_at" not in columns


def test_migration_adds_category_override_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            apply_migration(connection, "upgrade", path=_MIGRATION_PATH)
        columns = {col["name"] for col in inspect(engine).get_columns("photo_scores")}
    finally:
        engine.dispose()

    assert "category_override" in columns


def test_migration_creates_the_three_new_tables(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            apply_migration(connection, "upgrade", path=_MIGRATION_PATH)

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        category_label_columns = {col["name"] for col in inspector.get_columns("category_labels")}
        detection_columns = {
            col["name"] for col in inspector.get_columns("photo_category_detections")
        }
        run_columns = {
            col["name"] for col in inspector.get_columns("remote_category_classification_runs")
        }
    finally:
        engine.dispose()

    assert {
        "category_labels",
        "photo_category_detections",
        "remote_category_classification_runs",
    } <= table_names
    assert category_label_columns == {
        "id",
        "canonical_key",
        "display_name",
        "embedding",
        "created_at",
    }
    assert detection_columns == {
        "id",
        "photo_id",
        "category_label_id",
        "raw_label",
        "confidence",
        "provider",
        "computed_at",
    }
    assert run_columns == {
        "id",
        "project_id",
        "status",
        "started_at",
        "finished_at",
        "photos_total",
        "photos_processed",
        "error_message",
        "last_progress_at",
    }


def test_downgrade_restores_the_original_columns_and_drops_the_new_tables(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            apply_migration(connection, "upgrade", path=_MIGRATION_PATH)
        with engine.begin() as connection:
            apply_migration(connection, "downgrade", path=_MIGRATION_PATH)

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        project_columns = {col["name"] for col in inspector.get_columns("projects")}
        photo_score_columns = {col["name"] for col in inspector.get_columns("photo_scores")}
    finally:
        engine.dispose()

    assert {
        "category_labels",
        "photo_category_detections",
        "remote_category_classification_runs",
    }.isdisjoint(table_names)
    assert "cloud_landmark_detection_enabled" in project_columns
    assert "cloud_landmark_consent_at" in project_columns
    assert "category_override" not in photo_score_columns
