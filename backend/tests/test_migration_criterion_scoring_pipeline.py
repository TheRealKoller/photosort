from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

# specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md: erste nicht-additive
# Migration im Projekt (Spalten-/Tabellen-Drop) - "alembic upgrade" laeuft bewusst NICHT ueber
# die volle Historie in der Testsuite (siehe test_seed.py-Kommentar: fruehere Migrationen nutzen
# sa.text('now()'), ein Postgres-only-Literal, das unter sqlite bei einem tatsaechlichen INSERT
# fehlschlaegt - genau deshalb laeuft "alembic upgrade head" produktiv nur gegen echtes Postgres,
# siehe die separate docker-compose-CI-Functional-Checks fuer Spec 0013). Dieser Test laedt
# STATTDESSEN ausschliesslich das upgrade()/downgrade() dieser EINEN neuen Revision und wendet es
# ueber einen echten Alembic-Operations-Kontext auf ein minimal nachgebautes "vorher"-Schema an
# (nur die von dieser Migration beruehrten Tabellen/Spalten) - testet exakt die DDL dieser
# Migration, ohne von der Postgres-only-Historie der uebrigen Migrationen abhaengig zu sein.

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "c1d2e3f4a5b6_criterion_scoring_pipeline.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "criterion_scoring_pipeline_migration", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration (Revision
    a7b8c9d0e1f2) - nur die von c1d2e3f4a5b6 tatsaechlich beruehrten Tabellen/Spalten, keine
    Fremdschluessel-Durchsetzung noetig (sqlite erzwingt FKs standardmaessig ohnehin nicht)."""
    connection.execute(text("CREATE TABLE projects (id INTEGER PRIMARY KEY)"))
    connection.execute(text("CREATE TABLE photos (id INTEGER PRIMARY KEY)"))
    connection.execute(
        text(
            "CREATE TABLE scoring_runs ("
            "id INTEGER PRIMARY KEY, project_id INTEGER, status VARCHAR(20), "
            "started_at DATETIME, finished_at DATETIME, photos_total INTEGER, "
            "photos_processed INTEGER, error_message VARCHAR, suggestions_found INTEGER, "
            "last_progress_at DATETIME)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE photo_scores ("
            "photo_id INTEGER PRIMARY KEY, sharpness FLOAT, exposure FLOAT, phash VARCHAR, "
            "duplicate_of INTEGER, cluster_key VARCHAR, suggested_status VARCHAR(20), "
            "computed_at DATETIME, category VARCHAR(20), local_quality_score FLOAT)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE top_selection_runs ("
            "id INTEGER PRIMARY KEY, project_id INTEGER, status VARCHAR(20), "
            "started_at DATETIME, finished_at DATETIME, top_n_per_cluster INTEGER, "
            "candidates_total INTEGER, candidates_processed INTEGER, suggestions_found INTEGER, "
            "error_message VARCHAR, last_progress_at DATETIME)"
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


def test_migration_drops_photo_score_category_and_local_quality_score(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply_upgrade(connection)

        columns = {col["name"] for col in inspect(engine).get_columns("photo_scores")}
    finally:
        engine.dispose()

    assert "category" not in columns
    assert "local_quality_score" not in columns
    # Restspalten bleiben unveraendert erhalten (Akzeptanzkriterium der Spec) - kein
    # Kollateral-Drop benachbarter Spalten.
    assert columns == {
        "photo_id",
        "sharpness",
        "exposure",
        "phash",
        "duplicate_of",
        "cluster_key",
        "suggested_status",
        "computed_at",
    }


def test_migration_drops_top_selection_runs_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply_upgrade(connection)

        table_names = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert "top_selection_runs" not in table_names


def test_migration_creates_new_tables_and_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply_upgrade(connection)

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        scoring_run_columns = {col["name"] for col in inspector.get_columns("scoring_runs")}
        criterion_score_columns = {
            col["name"] for col in inspector.get_columns("photo_criterion_scores")
        }
        criterion_run_columns = {
            col["name"] for col in inspector.get_columns("criterion_scoring_runs")
        }
        ranking_columns = {col["name"] for col in inspector.get_columns("photo_rankings")}
    finally:
        engine.dispose()

    assert {"photo_criterion_scores", "criterion_scoring_runs", "photo_rankings"} <= table_names
    assert "gate_confirmed_at" in scoring_run_columns
    assert criterion_score_columns == {
        "id",
        "photo_id",
        "criterion_key",
        "value",
        "source",
        "computed_at",
    }
    assert criterion_run_columns == {
        "id",
        "project_id",
        "scoring_run_id",
        "status",
        "started_at",
        "finished_at",
        "photos_total",
        "photos_processed",
        "error_message",
        "last_progress_at",
    }
    assert ranking_columns == {
        "id",
        "criterion_scoring_run_id",
        "photo_id",
        "cluster_key",
        "category_key",
        "rank_score",
        "rank_position",
    }


def test_downgrade_restores_the_dropped_columns_and_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply_upgrade(connection)
        with engine.begin() as connection:
            _apply_downgrade(connection)

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        photo_score_columns = {col["name"] for col in inspector.get_columns("photo_scores")}
    finally:
        engine.dispose()

    assert "top_selection_runs" in table_names
    assert {"photo_criterion_scores", "criterion_scoring_runs", "photo_rankings"}.isdisjoint(
        table_names
    )
    assert {"category", "local_quality_score"} <= photo_score_columns
