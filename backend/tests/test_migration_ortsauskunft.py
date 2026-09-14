"""Die rein ADDITIVE Migration der Ortsauskunft: Tabelle `place_lookups`, Spalte
`events.place_name`.

Zwei Zusagen stehen hier als geprueftes Verhalten und nicht als Absicht: Es wird NICHTS
nachgezogen - `events.place_name` ist nach dem `upgrade` ueberall `NULL`, auch bei Zeilen mit
`landmark_name` - und es wird NICHTS geloescht; bestehende `events`-Zeilen ueberleben beide
Richtungen unveraendert.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / "d7e8f9a0b1c2_ortsauskunft.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("ortsauskunft_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die beiden
    Tabellen, auf die sie sich bezieht."""
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
            "CREATE TABLE events ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "criterion_scoring_run_id INTEGER NOT NULL, "
            "position INTEGER NOT NULL, "
            "started_at DATETIME NOT NULL, "
            "ended_at DATETIME NOT NULL, "
            "landmark_name VARCHAR, "
            "place_kind VARCHAR, "
            "place_lat FLOAT, "
            "place_lon FLOAT)"
        )
    )


def _insert_legacy_event(
    connection: Connection, *, event_id: int, landmark_name: str | None
) -> None:
    name = "NULL" if landmark_name is None else f"'{landmark_name}'"
    connection.execute(
        text(
            "INSERT INTO events (id, criterion_scoring_run_id, position, started_at, ended_at, "
            "landmark_name, place_kind, place_lat, place_lon) VALUES "
            f"({event_id}, 1, {event_id}, '2026-09-14 10:00:00', '2026-09-14 11:00:00', "
            f"{name}, 'coordinate', 47.51, 11.09)"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def test_revision_chains_onto_the_current_head() -> None:
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head."""
    module = _load_migration_module()

    assert module.down_revision == "c5d6e7f8a9b0"


def test_upgrade_creates_the_place_lookups_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        inspector = inspect(connection)
        assert "place_lookups" in inspector.get_table_names()
        columns = {column["name"]: column for column in inspector.get_columns("place_lookups")}

    assert set(columns) == {
        "id",
        "project_id",
        "cell_lat",
        "cell_lon",
        "neighbourhood",
        "locality",
        "region",
        "country",
        "matched_level",
        "source",
        "resolved_at",
    }
    for required in ("project_id", "cell_lat", "cell_lon", "source", "resolved_at"):
        assert not columns[required]["nullable"], required
    for optional in ("neighbourhood", "locality", "region", "country", "matched_level"):
        assert columns[optional]["nullable"], optional


def test_upgrade_binds_the_lookup_to_its_project_with_a_real_foreign_key(tmp_path: Path) -> None:
    """Die Lebensdauer-Bindung der dauerhaftesten Ortsspur des Systems (S6). Eine bloss LOGISCHE
    Spalte fiele still aus der Erreichbarkeitspruefung der Projektloeschung heraus."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        foreign_keys = inspect(connection).get_foreign_keys("place_lookups")

    assert [(fk["referred_table"], fk["constrained_columns"]) for fk in foreign_keys] == [
        ("projects", ["project_id"])
    ]


def test_upgrade_keeps_one_lookup_per_project_and_cell(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        constraints = inspect(connection).get_unique_constraints("place_lookups")

    assert [c["column_names"] for c in constraints] == [["project_id", "cell_lat", "cell_lon"]]


def test_upgrade_adds_a_nullable_place_name_to_events(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        columns = {c["name"]: c for c in inspect(connection).get_columns("events")}

    assert "place_name" in columns
    assert columns["place_name"]["nullable"]


def test_upgrade_leaves_place_name_null_for_every_existing_row(tmp_path: Path) -> None:
    """KEIN Nachziehen bestehender Laeufe ist eine gepruefte Zusage, keine Auslassung: auch die
    Zeile MIT `landmark_name` bekommt keinen Ortsnamen - er ersetzt eine Sehenswuerdigkeit nie."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_event(connection, event_id=1, landmark_name=None)
        _insert_legacy_event(connection, event_id=2, landmark_name="Eiffelturm")
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT id, place_name FROM events ORDER BY id")).all()

    assert rows == [(1, None), (2, None)]


def test_upgrade_keeps_every_existing_event_row(tmp_path: Path) -> None:
    """Rein additiv heisst auch: keine Zeile faellt weg und kein bestehender Wert aendert sich."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_event(connection, event_id=1, landmark_name="Eiffelturm")
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, position, landmark_name, place_kind, place_lat FROM events")
        ).all()

    assert rows == [(1, 1, "Eiffelturm", "coordinate", 47.51)]


def test_downgrade_removes_both_the_table_and_the_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        inspector = inspect(connection)
        assert "place_lookups" not in inspector.get_table_names()
        assert "place_name" not in {c["name"] for c in inspector.get_columns("events")}


def test_the_existing_event_rows_survive_the_downgrade_too(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_event(connection, event_id=1, landmark_name=None)
        _insert_legacy_event(connection, event_id=2, landmark_name="Eiffelturm")
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT id, landmark_name FROM events ORDER BY id")).all()

    assert rows == [(1, None), (2, "Eiffelturm")]
