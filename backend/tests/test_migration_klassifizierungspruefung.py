"""Spec 0616 / ADR 0139 - die sechs Tabellen der Klassifizierungspruefung.

Rein additiv: keine bestehende Tabelle wird gelesen, umgeschrieben oder ergaenzt. Fuenf Aussagen
tragen mehr als die reine Spaltenform:

* Der Teilschritt `phase` ist NULLABLE - `NULL` heisst "der Lauf ist beendet", und ein
  abgeschlossener Lauf muss das sagen koennen.
* `excluded_document` und `album_level` einer Ergebniszeile sind NULLABLE - `NULL` heisst "dieses
  Verfahren sagt dazu nichts", und ein erfundenes `false` machte jede Dokumentaufnahme zur
  Abweichung.
* `classification_review_cases.photo_position` ist NOT NULL: die laufende Nummer wird GESPEICHERT,
  nicht abgeleitet.
* Der Fall ist eindeutig je Pruefung, Foto, Zweck und Merkmal.
* Das Urteil hat den FALL als Primaerschluessel - genau eines je Fall, nicht eines je Nutzer.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

_MIGRATION_FILENAME = "44ba5fe0184a_klassifizierungspruefung.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)

_NEW_TABLES = (
    "classification_reviews",
    "classification_review_sides",
    "classification_review_results",
    "classification_review_result_strengths",
    "classification_review_cases",
    "classification_review_verdicts",
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "klassifizierungspruefung_migration", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die Tabellen,
    auf die die neuen Fremdschluessel zeigen."""
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
            "CREATE TABLE users ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "username VARCHAR NOT NULL, "
            "password_hash VARCHAR NOT NULL)"
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

    assert module.revision == "44ba5fe0184a"
    assert module.down_revision == "8cf920dd03b4"


def test_every_review_table_exists_after_the_upgrade(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        assert set(_NEW_TABLES) <= set(inspect(connection).get_table_names())


def test_the_review_header_carries_the_run_state_and_the_frozen_sample(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, "classification_reviews")

        assert {
            "id",
            "project_id",
            "created_by_user_id",
            "status",
            "phase",
            "sample_size",
            "seed",
            "photo_count",
            "photos_processed",
            "unclassifiable_photo_count",
            "started_at",
            "finished_at",
            "last_progress_at",
            "error_message",
        } == set(columns)
        assert columns["phase"]["nullable"] is True
        assert columns["finished_at"]["nullable"] is True
        assert columns["error_message"]["nullable"] is True
        assert columns["sample_size"]["nullable"] is False


def test_a_side_is_keyed_by_review_and_letter_and_keeps_its_origin(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        table = inspect(connection)
        assert table.get_pk_constraint("classification_review_sides")["constrained_columns"] == [
            "review_id",
            "side",
        ]
        columns = _columns(connection, "classification_review_sides")
        assert {
            "review_id",
            "side",
            "kind",
            "provider",
            "model",
            "eye_model_revision",
            "eye_mapping_version",
            "estimated_cost_usd",
            "api_calls",
            "failed_calls",
            "input_tokens",
            "output_tokens",
            "cost_usd",
        } == set(columns)
        # Die Herkunft ist beim Anlegen GESPEICHERT; "nicht erfasst" ist NULL, nicht 0.
        for nullable in (
            "provider",
            "model",
            "eye_model_revision",
            "eye_mapping_version",
            "estimated_cost_usd",
            "cost_usd",
        ):
            assert columns[nullable]["nullable"] is True


def test_the_results_keep_a_missing_statement_as_null(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, "classification_review_results")
        assert columns["excluded_document"]["nullable"] is True
        assert columns["album_level"]["nullable"] is True
        assert inspect(connection).get_pk_constraint("classification_review_results")[
            "constrained_columns"
        ] == ["review_id", "side", "photo_id"]
        assert inspect(connection).get_pk_constraint("classification_review_result_strengths")[
            "constrained_columns"
        ] == ["review_id", "side", "photo_id", "motif_key"]


def test_a_case_is_unique_per_review_photo_purpose_and_motif(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        unique = [
            constraint
            for constraint in inspect(connection).get_unique_constraints(
                "classification_review_cases"
            )
            if constraint["column_names"] == ["review_id", "photo_id", "purpose", "motif_key"]
        ]
        assert len(unique) == 1
        columns = _columns(connection, "classification_review_cases")
        assert columns["photo_position"]["nullable"] is False
        assert columns["motif_key"]["nullable"] is True


def test_a_verdict_is_keyed_by_the_case(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        assert inspect(connection).get_pk_constraint("classification_review_verdicts")[
            "constrained_columns"
        ] == ["case_id"]


def test_the_downgrade_drops_all_six_tables(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

        remaining = set(inspect(connection).get_table_names())
        assert remaining.isdisjoint(_NEW_TABLES)
        assert {"projects", "users", "photos"} <= remaining
