from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

# specs/features/0299-kategorie-konfidenz-anzeigen.md, decisions/0067-modellkonfidenz-je-kategorie-
# anzeige-und-auswertung.md Punkt 3/4: rein additive Migration - zwei nullable Spalten an
# photo_category_classifications, keine Datenmigration, KEIN Backfill. Isoliert ueber genau diese
# eine Revision, ohne von der vollen Migrationshistorie abzuhaengen (Muster der bestehenden
# test_migration_*.py).

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "a3b4c5d6e7f8_kategorie_konfidenz.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("kategorie_konfidenz_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die eine
    beruehrte Tabelle, reduziert auf die Spalten, die die Tests brauchen."""
    connection.execute(
        text(
            "CREATE TABLE photo_category_classifications ("
            "photo_id INTEGER PRIMARY KEY, category_key VARCHAR NOT NULL, "
            "detected_categories JSON NOT NULL, provider VARCHAR NOT NULL, "
            "computed_at DATETIME NOT NULL)"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def test_revision_chains_onto_the_current_head() -> None:
    module = _load_migration_module()

    assert module.down_revision == "5ab22032843c"


def test_migration_adds_both_confidence_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")

        columns = {c["name"] for c in inspect(engine).get_columns("photo_category_classifications")}
    finally:
        engine.dispose()

    assert "detected_category_confidences" in columns
    assert "category_confidence" in columns


def test_both_columns_are_nullable(tmp_path: Path) -> None:
    """`NULL` = "nicht erhoben" ist die tragende Semantik (ADR 0067 Punkt 3) - eine
    NOT-NULL-Spalte machte sie unmoeglich."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")

        nullable_by_name = {
            c["name"]: c["nullable"]
            for c in inspect(engine).get_columns("photo_category_classifications")
        }
    finally:
        engine.dispose()

    assert nullable_by_name["detected_category_confidences"]
    assert nullable_by_name["category_confidence"]


def test_existing_rows_keep_null_instead_of_a_zero_confidence(tmp_path: Path) -> None:
    """DER Kern dieser Migration und zugleich Akzeptanzkriterium 9: Bestandszeilen behalten
    dauerhaft `NULL`. Ein `server_default` von `0` bzw. `{}` waere eine Behauptung ueber eine
    Modellantwort, die es nie gab - und "nicht erhoben" waere danach nicht mehr von "das Modell war
    sich zu 0 % sicher" zu unterscheiden."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            connection.execute(
                text(
                    "INSERT INTO photo_category_classifications "
                    "(photo_id, category_key, detected_categories, provider, computed_at) "
                    "VALUES (1, 'tier', '[\"tier\"]', 'anthropic', '2026-01-01 00:00:00')"
                )
            )
            _apply(connection, "upgrade")

        with engine.connect() as connection:
            mapping, scalar = connection.execute(
                text(
                    "SELECT detected_category_confidences, category_confidence "
                    "FROM photo_category_classifications WHERE photo_id = 1"
                )
            ).one()
    finally:
        engine.dispose()

    assert mapping is None
    assert scalar is None


def test_downgrade_removes_both_columns_again(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")
            _apply(connection, "downgrade")

        columns = {c["name"] for c in inspect(engine).get_columns("photo_category_classifications")}
    finally:
        engine.dispose()

    assert "detected_category_confidences" not in columns
    assert "category_confidence" not in columns
    # Die Bestandsspalten bleiben unberuehrt - die Umkehrung ist verlustbehaftet, aber
    # schema-vollstaendig.
    assert "detected_categories" in columns
    assert "category_key" in columns
