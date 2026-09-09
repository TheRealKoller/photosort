from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

# specs/features/0300-nebenkategorien.md, decisions/0069-nebenkategorien-mehrfachzugehoerigkeit-
# und-konfidenzgewichtete-rangfolge.md Punkt 9: eine additive Spalte, ein GETAUSCHTER Constraint,
# KEIN Backfill. Isoliert ueber genau diese eine Revision, ohne von der vollen Migrationshistorie
# abzuhaengen (Muster der bestehenden test_migration_*.py).

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "c9d0e1f2a3b4_nebenkategorien.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("nebenkategorien_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die eine
    beruehrte Tabelle, mit dem BENANNTEN alten Unique-Constraint (so, wie ihn Revision
    c1d2e3f4a5b6 anlegt)."""
    connection.execute(
        text(
            "CREATE TABLE photo_rankings ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "criterion_scoring_run_id INTEGER NOT NULL, "
            "photo_id INTEGER NOT NULL, "
            "cluster_key VARCHAR NOT NULL, "
            "category_key VARCHAR NOT NULL, "
            "rank_score FLOAT NOT NULL, "
            "rank_position INTEGER NOT NULL, "
            "CONSTRAINT uq_photo_ranking_run_photo "
            "UNIQUE (criterion_scoring_run_id, photo_id))"
        )
    )


def _insert_legacy_row(connection: Connection, *, row_id: int, category_key: str) -> None:
    connection.execute(
        text(
            "INSERT INTO photo_rankings "
            "(id, criterion_scoring_run_id, photo_id, cluster_key, category_key, rank_score, "
            "rank_position) VALUES "
            f"({row_id}, 1, 1, 'cluster-0', '{category_key}', 0.9, 1)"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _unique_constraint_names(engine_url_target: object) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspect(engine_url_target).get_unique_constraints(  # type: ignore[arg-type]
            "photo_rankings"
        )
        if constraint["name"] is not None
    }


def test_revision_chains_onto_the_current_head() -> None:
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head, nicht gegen den in
    der Spec genannten (Teststrategie der Spec)."""
    module = _load_migration_module()

    assert module.down_revision == "b8c9d0e1f2a3"


def test_upgrade_adds_the_is_primary_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")

        columns = {c["name"]: c for c in inspect(engine).get_columns("photo_rankings")}
    finally:
        engine.dispose()

    assert "is_primary" in columns
    assert not columns["is_primary"]["nullable"]


def test_an_existing_row_becomes_the_primary_row_of_its_photo(tmp_path: Path) -> None:
    """Akzeptanzkriterium 18: jede bestehende Zeile IST die Hauptzeile ihres Fotos - das ist die
    bis hierhin geltende Invariante, keine Schaetzung. Die Migration schreibt keine neuen Zeilen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _insert_legacy_row(connection, row_id=1, category_key="tier")
            _apply(connection, "upgrade")

        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT id, is_primary FROM photo_rankings")
            ).all()
    finally:
        engine.dispose()

    assert rows == [(1, True)]


def test_after_the_upgrade_an_insert_without_is_primary_fails(tmp_path: Path) -> None:
    """Akzeptanzkriterium 25, erste Haelfte: nach `upgrade()` traegt `is_primary` KEINEN
    `server_default` mehr. Bliebe er stehen, erzeugte ein Schreibpfad, der die Spalte vergisst,
    still eine zweite Hauptkategorie - und die Spalte traegt genau die Invariante, die das
    verhindern soll."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")

        with pytest.raises((IntegrityError, OperationalError)):
            with engine.begin() as connection:
                _insert_legacy_row(connection, row_id=1, category_key="tier")
    finally:
        engine.dispose()


def test_after_the_upgrade_the_same_photo_may_appear_in_a_second_category(
    tmp_path: Path,
) -> None:
    """DER Beweis, dass der alte Constraint wirklich weg ist (Teststrategie der Spec): das vorher
    VERBOTENE Insert (gleicher Lauf + Foto, andere Kategorie) muss gelingen. Ein reiner
    Namensvergleich bliebe gruen, wenn `drop_constraint` unter SQLite still nichts taete."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")
            connection.execute(
                text(
                    "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, "
                    "cluster_key, category_key, rank_score, rank_position, is_primary) VALUES "
                    "(1, 1, 1, 'cluster-0', 'menschen', 0.9, 1, 1)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, "
                    "cluster_key, category_key, rank_score, rank_position, is_primary) VALUES "
                    "(2, 1, 1, 'cluster-0', 'tier', 0.9, 2, 0)"
                )
            )

        with engine.connect() as connection:
            count = connection.execute(text("SELECT count(*) FROM photo_rankings")).scalar_one()
    finally:
        engine.dispose()

    assert count == 2


def test_after_the_upgrade_the_same_photo_may_not_appear_twice_in_one_category(
    tmp_path: Path,
) -> None:
    """Akzeptanzkriterium 20: der NEUE Constraint greift - eine zweite Zeile mit gleichem
    (Lauf, Foto, Kategorie) wird von der Datenbank abgewiesen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")
            connection.execute(
                text(
                    "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, "
                    "cluster_key, category_key, rank_score, rank_position, is_primary) VALUES "
                    "(1, 1, 1, 'cluster-0', 'tier', 0.9, 1, 1)"
                )
            )

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, "
                        "cluster_key, category_key, rank_score, rank_position, is_primary) VALUES "
                        "(2, 1, 1, 'cluster-0', 'tier', 0.1, 2, 0)"
                    )
                )
    finally:
        engine.dispose()


def test_upgrade_swaps_the_named_constraints(tmp_path: Path) -> None:
    """Beide Constraints sind BENANNT - `Base.metadata` traegt keine `naming_convention`, und ein
    unbenannter Constraint ist unter SQLite nicht droppbar (dieselbe Falle wie in Revision
    b8c9d0e1f2a3)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")

        names = _unique_constraint_names(engine)
    finally:
        engine.dispose()

    assert "uq_photo_ranking_run_photo_category" in names
    assert "uq_photo_ranking_run_photo" not in names


def test_downgrade_removes_the_secondary_rows_and_restores_the_old_constraint(
    tmp_path: Path,
) -> None:
    """Akzeptanzkriterium 25, zweite Haelfte: `downgrade()` laeuft an einer Datenbank MIT
    Nebenzeilen fehlerfrei - es loescht sie zuerst, sonst verletzte der alte Constraint die
    vorhandenen Daten."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")
            connection.execute(
                text(
                    "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, "
                    "cluster_key, category_key, rank_score, rank_position, is_primary) VALUES "
                    "(1, 1, 1, 'cluster-0', 'menschen', 0.9, 1, 1), "
                    "(2, 1, 1, 'cluster-0', 'tier', 0.9, 2, 0)"
                )
            )
            _apply(connection, "downgrade")

        columns = {c["name"] for c in inspect(engine).get_columns("photo_rankings")}
        names = _unique_constraint_names(engine)
        with engine.connect() as connection:
            remaining = connection.execute(
                text("SELECT id, category_key FROM photo_rankings")
            ).all()
    finally:
        engine.dispose()

    assert "is_primary" not in columns
    assert "uq_photo_ranking_run_photo" in names
    assert "uq_photo_ranking_run_photo_category" not in names
    # Nur die Hauptzeile bleibt - und zwar unveraendert.
    assert remaining == [(1, "menschen")]
