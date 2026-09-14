"""Die rein ADDITIVE Migration des Namensregisters: Tabelle `landmark_names`, Spalte
`photo_landmark_detections.canonical_name`.

Zwei Zusagen stehen hier als geprueftes Verhalten und nicht als Absicht: Es wird NICHTS nachgezogen
- `canonical_name` ist nach dem `upgrade` ueberall `NULL`, auch bei Zeilen mit hoher Konfidenz -
und es wird NICHTS geloescht; bestehende `photo_landmark_detections`-Zeilen ueberleben beide
Richtungen unveraendert. Die bereits erteilten Cloud-Einwilligungen bleiben ebenfalls unberuehrt
(Daniel, 2026-09-14).
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "a8b9c0d1e2f3_namensregister.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("namensregister_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die drei
    Tabellen, auf die sie sich bezieht."""
    connection.execute(
        text(
            "CREATE TABLE projects ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "name VARCHAR NOT NULL, "
            "opencloud_drive_id VARCHAR NOT NULL, "
            "opencloud_path VARCHAR NOT NULL, "
            "cloud_vision_detection_enabled BOOLEAN NOT NULL DEFAULT 0)"
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
    connection.execute(
        text(
            "CREATE TABLE photo_landmark_detections ("
            "photo_id INTEGER NOT NULL PRIMARY KEY, "
            "name VARCHAR NOT NULL, "
            "confidence FLOAT NOT NULL, "
            "computed_at DATETIME NOT NULL, "
            "provider VARCHAR NOT NULL DEFAULT 'anthropic')"
        )
    )


def _insert_legacy_detection(
    connection: Connection, *, photo_id: int, name: str, confidence: float
) -> None:
    connection.execute(
        text(
            "INSERT INTO photo_landmark_detections "
            "(photo_id, name, confidence, computed_at, provider) VALUES "
            f"({photo_id}, '{name}', {confidence}, '2026-09-14 10:00:00', 'anthropic')"
        )
    )


def _insert_project(connection: Connection, *, project_id: int, consent: int) -> None:
    connection.execute(
        text(
            "INSERT INTO projects "
            "(id, name, opencloud_drive_id, opencloud_path, cloud_vision_detection_enabled) "
            f"VALUES ({project_id}, 'Reise', 'drive', '/Reise', {consent})"
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

    assert module.down_revision == "e3f4a5b6c7d8"


def test_upgrade_creates_the_landmark_names_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        inspector = inspect(connection)
        assert "landmark_names" in inspector.get_table_names()
        columns = {column["name"]: column for column in inspector.get_columns("landmark_names")}

    assert set(columns) == {
        "id",
        "project_id",
        "normalized_name",
        "display_name",
        "embedding",
        "locality",
        "created_at",
    }
    for required in ("project_id", "normalized_name", "display_name", "embedding"):
        assert not columns[required]["nullable"], required
    assert columns["locality"]["nullable"]


def test_upgrade_binds_the_register_to_its_project_with_a_real_foreign_key(tmp_path: Path) -> None:
    """S8: Der Fremdschluessel ist ECHT und NOT NULL. Ohne ihn waere die Tabelle ein reiner
    Fremdschluessel-Elternteil, fiele aus `tests/project_graph.py::tables_reachable_from_projects`
    heraus, und BEIDE Vollstaendigkeitstests der Projektloeschung prueften sie stillschweigend
    nicht mehr."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        foreign_keys = inspect(connection).get_foreign_keys("landmark_names")

    assert [(fk["referred_table"], fk["constrained_columns"]) for fk in foreign_keys] == [
        ("projects", ["project_id"])
    ]


def test_upgrade_keeps_one_entry_per_project_and_normalised_name(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        constraints = inspect(connection).get_unique_constraints("landmark_names")

    assert [c["column_names"] for c in constraints] == [["project_id", "normalized_name"]]


def test_the_same_name_in_two_projects_is_two_rows_but_twice_in_one_is_rejected(
    tmp_path: Path,
) -> None:
    """`project_id` steht IM Constraint: Dieselbe Sehenswuerdigkeit in einem zweiten Projekt ist
    eine eigene Zeile und wird nie mit der ersten zusammengefuehrt (S8)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_project(connection, project_id=1, consent=1)
        _insert_project(connection, project_id=2, consent=0)
        _apply(connection, "upgrade")

    insert = text(
        "INSERT INTO landmark_names (project_id, normalized_name, display_name, embedding) "
        "VALUES (:project_id, 'zugspitze', 'Zugspitze', '[1.0, 0.0]')"
    )
    with engine.begin() as connection:
        connection.execute(insert, {"project_id": 1})
        connection.execute(insert, {"project_id": 2})

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(insert, {"project_id": 1})


def test_upgrade_adds_a_nullable_canonical_name_to_the_detections(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        columns = {
            c["name"]: c for c in inspect(connection).get_columns("photo_landmark_detections")
        }

    assert "canonical_name" in columns
    assert columns["canonical_name"]["nullable"]


def test_upgrade_leaves_canonical_name_null_for_every_existing_row(tmp_path: Path) -> None:
    """KEIN Nachziehen frueherer Erkennungslaeufe ist eine gepruefte Zusage, keine Auslassung: auch
    die Zeile weit OBERHALB der Konfidenzgrenze bekommt keinen kanonischen Namen. Ohne die Spalte
    verhaelt sich eine Altzeile exakt wie zuvor."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_detection(connection, photo_id=1, name="Eiffelturm", confidence=0.95)
        _insert_legacy_detection(connection, photo_id=2, name="Vermutung", confidence=0.2)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT photo_id, canonical_name FROM photo_landmark_detections ORDER BY photo_id")
        ).all()

    assert rows == [(1, None), (2, None)]


def test_upgrade_keeps_every_existing_detection_row(tmp_path: Path) -> None:
    """Rein additiv heisst auch: keine Zeile faellt weg und kein bestehender Wert aendert sich -
    insbesondere wird keine unsichere Zeile geloescht. Die Antwort ist bezahlt."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_detection(connection, photo_id=1, name="Eiffelturm", confidence=0.95)
        _insert_legacy_detection(connection, photo_id=2, name="Vermutung", confidence=0.2)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT photo_id, name, confidence, provider FROM photo_landmark_detections "
                "ORDER BY photo_id"
            )
        ).all()

    assert rows == [(1, "Eiffelturm", 0.95, "anthropic"), (2, "Vermutung", 0.2, "anthropic")]


def test_an_already_granted_cloud_consent_is_never_reset(tmp_path: Path) -> None:
    """Bereits erteilte Einwilligungen bleiben gueltig (Daniel, 2026-09-14) - die aktualisierte
    Oberflaechen-Aussage traegt das allein. Die Migration fasst die Spalte nicht an."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_project(connection, project_id=1, consent=1)
        _insert_project(connection, project_id=2, consent=0)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, cloud_vision_detection_enabled FROM projects ORDER BY id")
        ).all()

    assert rows == [(1, 1), (2, 0)]


def test_downgrade_removes_both_the_table_and_the_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        inspector = inspect(connection)
        assert "landmark_names" not in inspector.get_table_names()
        assert "canonical_name" not in {
            c["name"] for c in inspector.get_columns("photo_landmark_detections")
        }


def test_the_existing_detection_rows_survive_the_downgrade_too(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_detection(connection, photo_id=1, name="Eiffelturm", confidence=0.95)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT photo_id, name, confidence FROM photo_landmark_detections")
        ).all()

    assert rows == [(1, "Eiffelturm", 0.95)]
