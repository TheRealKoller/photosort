"""Die rein ADDITIVE Migration der Personen (Spec 0292, ADR 0126 Punkt 6): vier Tabellen und
zwei Zaehlerspalten an `criterion_scoring_runs`.

Geprueft am nachgebauten Schema-Stand unmittelbar davor, wie alle `test_migration_*.py`. Die
Aussagen hier sind die strukturellen: hoechstens zwei Personen, kein Name doppelt, echte
Fremdschluessel auf `persons`, keine Kante von einer Referenz zu Foto oder Projekt, und die
Spaltensaetze der beiden Foto-Tabellen ohne jeden Wert, jede Box und jedes Merkmal.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, Engine, create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError

from photosort.db import enable_sqlite_foreign_keys

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / "1f4027405ea5_personen.py"
)
_NEW_TABLES = (
    "persons",
    "person_references",
    "photo_person_detections",
    "photo_person_corrections",
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("personen_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Die Fremdschluessel-Eltern `photos`/`users` und `criterion_scoring_runs` mit einer
    Bestandszeile, deren neue Zaehler `NULL` bleiben muessen."""
    connection.execute(text("CREATE TABLE users (id INTEGER NOT NULL PRIMARY KEY)"))
    connection.execute(text("CREATE TABLE photos (id INTEGER NOT NULL PRIMARY KEY)"))
    connection.execute(
        text(
            "CREATE TABLE criterion_scoring_runs ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "photos_total INTEGER NOT NULL)"
        )
    )
    connection.execute(text("INSERT INTO users (id) VALUES (1)"))
    connection.execute(text("INSERT INTO photos (id) VALUES (1)"))
    connection.execute(text("INSERT INTO criterion_scoring_runs (id, photos_total) VALUES (1, 7)"))


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


@pytest.fixture
def upgraded(tmp_path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
    # Erst NACH dem Upgrade: die Durchsetzung soll die neuen Fremdschluessel pruefen, nicht den
    # Tabellenumbau der Migration selbst.
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    engine.dispose()
    return engine


def test_the_revision_chains_onto_the_current_head() -> None:
    module = _load_migration_module()

    assert module.revision == "1f4027405ea5"
    assert module.down_revision == "2c5472d41548"


def test_upgrade_creates_the_four_tables_with_exactly_their_columns(upgraded: Engine) -> None:
    with upgraded.connect() as connection:
        inspector = inspect(connection)
        columns = {
            table: {column["name"] for column in inspector.get_columns(table)}
            for table in _NEW_TABLES
        }

    assert columns == {
        "persons": {"id", "slot", "name", "name_key", "created_at"},
        "person_references": {"id", "person_id", "embedding", "model_key", "created_at"},
        "photo_person_detections": {"photo_id", "person_id", "computed_at"},
        "photo_person_corrections": {
            "id",
            "photo_id",
            "person_id",
            "user_id",
            "applies",
            "updated_at",
        },
    }


def test_the_constraints_are_named(upgraded: Engine) -> None:
    with upgraded.connect() as connection:
        inspector = inspect(connection)
        checks = {check["name"] for check in inspector.get_check_constraints("persons")}
        unique_persons = {
            (constraint["name"], tuple(constraint["column_names"]))
            for constraint in inspector.get_unique_constraints("persons")
        }
        unique_corrections = {
            (constraint["name"], tuple(constraint["column_names"]))
            for constraint in inspector.get_unique_constraints("photo_person_corrections")
        }

    assert "ck_persons_slot" in checks
    assert unique_persons == {
        ("uq_persons_slot", ("slot",)),
        ("uq_persons_name_key", ("name_key",)),
    }
    # OHNE `user_id`: die zuletzt geschriebene Korrektur gilt fuer beide Nutzer.
    assert unique_corrections == {
        ("uq_photo_person_correction_photo_person", ("photo_id", "person_id"))
    }


def test_every_person_id_carries_a_real_foreign_key(upgraded: Engine) -> None:
    with upgraded.connect() as connection:
        inspector = inspect(connection)
        edges = {
            (table, fk["referred_table"], tuple(fk["constrained_columns"]))
            for table in _NEW_TABLES
            for fk in inspector.get_foreign_keys(table)
        }

    assert edges == {
        ("person_references", "persons", ("person_id",)),
        ("photo_person_detections", "photos", ("photo_id",)),
        ("photo_person_detections", "persons", ("person_id",)),
        ("photo_person_corrections", "photos", ("photo_id",)),
        ("photo_person_corrections", "persons", ("person_id",)),
        ("photo_person_corrections", "users", ("user_id",)),
    }


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO persons (id, slot, name, name_key) VALUES (3, 3, 'Dritte', 'dritte')",
        "INSERT INTO persons (id, slot, name, name_key) VALUES (3, 1, 'Berta', 'berta')",
        "INSERT INTO persons (id, slot, name, name_key) VALUES (3, 2, 'ANNA', 'anna')",
    ],
    ids=["dritter-slot", "slot-doppelt", "name-doppelt"],
)
def test_at_most_two_persons_and_no_name_twice(upgraded: Engine, statement: str) -> None:
    with upgraded.begin() as connection:
        connection.execute(
            text("INSERT INTO persons (id, slot, name, name_key) VALUES (1, 1, 'Anna', 'anna')")
        )

    with pytest.raises(IntegrityError), upgraded.begin() as connection:
        connection.execute(text(statement))


def test_a_detection_for_an_unknown_person_is_refused(upgraded: Engine) -> None:
    with pytest.raises(IntegrityError), upgraded.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO photo_person_detections (photo_id, person_id, computed_at) "
                "VALUES (1, 99, '2026-09-27 10:00:00')"
            )
        )


def test_existing_runs_keep_null_person_counters(upgraded: Engine) -> None:
    with upgraded.connect() as connection:
        row = connection.execute(
            text(
                "SELECT photos_total, persons_photos_total, persons_photos_processed "
                "FROM criterion_scoring_runs WHERE id = 1"
            )
        ).one()

    assert tuple(row) == (7, None, None)


def test_downgrade_removes_tables_and_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        run_columns = {column["name"] for column in inspector.get_columns("criterion_scoring_runs")}
        row = connection.execute(text("SELECT id, photos_total FROM criterion_scoring_runs")).one()

    assert tables.isdisjoint(_NEW_TABLES)
    assert run_columns == {"id", "photos_total"}
    assert tuple(row) == (1, 7)
