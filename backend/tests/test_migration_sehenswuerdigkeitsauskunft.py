"""Die rein ADDITIVE Migration der Sehenswürdigkeitsauskunft: Tabelle `landmark_place_lookups`.

Zwei Zusagen stehen hier als geprueftes Verhalten und nicht als Absicht: Es wird NICHTS nachgezogen
und NICHTS geloescht - bestehende Zeilen und bestehende Tabellen ueberleben beide Richtungen
unveraendert - und die Tabelle traegt KEINE Entfernung, KEIN Pruefergebnis und kein `event_id`
(S1). Die Punktliste ist NICHT nullbar und darf leer sein: nur so sind die drei Zustaende der
Auskunft (nie nachgeschlagen / ohne Fund / mit Fund) auseinanderzuhalten (ADR 0123 Punkt 2).
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "2c5472d41548_sehenswuerdigkeitsauskunft.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "sehenswuerdigkeitsauskunft_migration", _MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - das
    Fremdschluessel-Elternteil `projects` und eine Tabelle, die unveraendert ueberleben muss."""
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
            "CREATE TABLE landmark_names ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "project_id INTEGER NOT NULL, "
            "normalized_name VARCHAR NOT NULL, "
            "display_name VARCHAR NOT NULL)"
        )
    )


def _insert_existing_landmark_name(connection: Connection) -> None:
    connection.execute(
        text(
            "INSERT INTO landmark_names (id, project_id, normalized_name, display_name) "
            "VALUES (1, 1, 'eiffelturm', 'Eiffelturm')"
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

    assert module.down_revision == "c5bc9a02c3c2"


def test_upgrade_creates_the_landmark_place_lookups_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        inspector = inspect(connection)
        assert "landmark_place_lookups" in inspector.get_table_names()
        columns = {
            column["name"]: column for column in inspector.get_columns("landmark_place_lookups")
        }

    assert set(columns) == {"id", "project_id", "folded_name", "points", "looked_up_at"}
    for required in ("project_id", "folded_name", "points", "looked_up_at"):
        assert not columns[required]["nullable"], required


def test_the_points_are_required_but_may_be_empty(tmp_path: Path) -> None:
    """ADR 0123 Punkt 2: Fiele „nie nachgeschlagen" mit „nachgeschlagen, ohne Fund" zusammen,
    verwuerfe ein Lauf ohne Datensatz jeden Namen. Die Spalte ist deshalb NICHT nullbar."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        connection.execute(
            text(
                "INSERT INTO landmark_place_lookups "
                "(id, project_id, folded_name, points, looked_up_at) "
                "VALUES (1, 1, 'stonehenge', '[]', '2026-09-24 10:00:00')"
            )
        )
        stored = connection.execute(
            text("SELECT points FROM landmark_place_lookups WHERE id = 1")
        ).scalar_one()

    assert stored == "[]"


def test_upgrade_binds_the_lookup_to_its_project_with_a_real_foreign_key(tmp_path: Path) -> None:
    """S2: Die Projektbindung ohne Rueckfall. Eine bloss LOGISCHE Spalte fiele still aus der
    Erreichbarkeitspruefung der Projektloeschung heraus."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        foreign_keys = inspect(connection).get_foreign_keys("landmark_place_lookups")

    assert [(fk["referred_table"], fk["constrained_columns"]) for fk in foreign_keys] == [
        ("projects", ["project_id"])
    ]


def test_upgrade_keeps_one_lookup_per_project_and_name(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        constraints = inspect(connection).get_unique_constraints("landmark_place_lookups")

    assert [c["column_names"] for c in constraints] == [["project_id", "folded_name"]]


def test_the_table_carries_no_distance_no_result_and_no_event_id(tmp_path: Path) -> None:
    """S1: Wäre eine Entfernung abgelegt, wäre aus einer Namensauskunft eine persistierte
    Aufenthaltsaussage geworden - mit feinerer Körnung als `PLACE_CELL_DIGITS = 2` sie zusichert."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        inspector = inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("landmark_place_lookups")}
        foreign_keys = inspector.get_foreign_keys("landmark_place_lookups")

    assert not columns & {
        "distance",
        "distance_meters",
        "event_id",
        "photo_id",
        "cell_lat",
        "cell_lon",
        "is_plausible",
        "confirmed",
    }
    assert all(fk["referred_table"] != "events" for fk in foreign_keys)


def test_upgrade_changes_nothing_existing(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_landmark_name(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, normalized_name, display_name FROM landmark_names")
        ).all()

    assert rows == [(1, "eiffelturm", "Eiffelturm")]


def test_downgrade_removes_the_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        assert "landmark_place_lookups" not in inspect(connection).get_table_names()


def test_existing_rows_survive_the_downgrade_too(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_landmark_name(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT id, normalized_name FROM landmark_names")).all()

    assert rows == [(1, "eiffelturm")]
