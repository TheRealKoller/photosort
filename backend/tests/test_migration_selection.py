"""Die Migration des Auswahlvorschlags: zwei additive, nullbare Spalten.

`NULL` traegt in beiden Spalten Bedeutung - `projects.selection_target IS NULL` heisst "nicht
selbst eingestellt" (wirksam ist dann ein Zehntel der Bilderzahl), `photo_rankings.
selection_position IS NULL` heisst "gehoert nicht zum Vorschlag". Ein `server_default` machte aus
beidem stillschweigend eine Aussage; er wird deshalb an zwei Artefakten geprueft.

Der Rueckwaertsweg stellt die STRUKTUR wieder her, nie die Daten.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

from photosort.db import Base

_MIGRATION_FILENAME = "e7f8a9b0c1d2_auswahlvorschlag.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("selection_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die beiden
    beruehrten Tabellen."""
    connection.execute(
        text(
            "CREATE TABLE projects ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "name VARCHAR NOT NULL, "
            "opencloud_drive_id VARCHAR NOT NULL, "
            "opencloud_path VARCHAR NOT NULL, "
            "created_at DATETIME, "
            "cloud_vision_detection_enabled BOOLEAN NOT NULL, "
            "cloud_vision_consent_at DATETIME)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE photo_rankings ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "criterion_scoring_run_id INTEGER NOT NULL, "
            "photo_id INTEGER NOT NULL, "
            "event_id INTEGER NOT NULL, "
            "rank_score FLOAT, "
            "rank_position INTEGER, "
            "CONSTRAINT uq_photo_ranking_run_photo "
            "UNIQUE (criterion_scoring_run_id, photo_id))"
        )
    )


def _insert_existing_rows(connection: Connection) -> None:
    """Bestandszeilen, wie sie vor der Migration in der Datenbank stehen - die Datenlosigkeit der
    Migration ist eine ausgesprochene Zusage und braucht deshalb Zeilen, an denen sie brechen
    koennte."""
    for index in (1, 2):
        connection.execute(
            text(
                "INSERT INTO projects (id, name, opencloud_drive_id, opencloud_path, "
                "created_at, cloud_vision_detection_enabled, cloud_vision_consent_at) VALUES "
                f"({index}, 'Projekt {index}', 'drive-{index}', '/pfad/{index}', "
                "'2026-07-20 10:00:00', 0, NULL)"
            )
        )
    for index in (1, 2, 3):
        connection.execute(
            text(
                "INSERT INTO photo_rankings (criterion_scoring_run_id, photo_id, event_id, "
                f"rank_score, rank_position) VALUES (1, {index}, 1, 0.9, {index})"
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
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head."""
    module = _load_migration_module()

    assert module.down_revision == "d6e7f8a9b0c1"


def test_upgrade_adds_exactly_the_two_nullable_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        before_projects = set(_columns(connection, "projects"))
        before_rankings = set(_columns(connection, "photo_rankings"))
        _apply(connection, "upgrade")

        projects = _columns(connection, "projects")
        rankings = _columns(connection, "photo_rankings")

    assert set(projects) - before_projects == {"selection_target"}
    assert set(rankings) - before_rankings == {"selection_position"}
    assert projects["selection_target"]["nullable"]
    assert rankings["selection_position"]["nullable"]


def test_upgrade_leaves_no_server_default_on_either_column(tmp_path: Path) -> None:
    """Erstes der zwei Artefakte: die Spalten der migrierten Tabelle. Ein Default `0` oder `10`
    machte aus "nicht selbst eingestellt" bzw. "gehoert nicht zum Vorschlag" stillschweigend eine
    Aussage."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        projects = _columns(connection, "projects")
        rankings = _columns(connection, "photo_rankings")

    assert projects["selection_target"]["default"] is None
    assert rankings["selection_position"]["default"] is None


def test_an_insert_without_the_columns_stores_null_in_the_model_schema(tmp_path: Path) -> None:
    """Zweites der zwei Artefakte: das aus `Base.metadata` erzeugte Schema. Ein `server_default`
    am Modell wuerde von der Migration gar nicht erfasst und faellt nur hier auf."""
    engine = create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO projects (id, name, opencloud_drive_id, opencloud_path, "
                "cloud_vision_detection_enabled) VALUES (1, 'P', 'd', '/p', 0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO photo_rankings (criterion_scoring_run_id, photo_id, event_id) "
                "VALUES (1, 1, 1)"
            )
        )

    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT selection_target FROM projects")).scalar_one() is None
        )
        assert (
            connection.execute(text("SELECT selection_position FROM photo_rankings")).scalar_one()
            is None
        )


def test_upgrade_keeps_every_existing_row_and_fills_both_columns_with_null(
    tmp_path: Path,
) -> None:
    """Die Datenlosigkeit ist hier eine ausgesprochene Zusage: Bestandsprojekte und
    Bestands-Rangzeilen ueberstehen den Weg unveraendert und tragen danach in ALLEN Zeilen
    `NULL` - es gibt keine Migration, die einen Vorschlag rueckwirkend berechnet."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_rows(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        projects = connection.execute(
            text("SELECT id, name, selection_target FROM projects ORDER BY id")
        ).all()
        rankings = connection.execute(
            text(
                "SELECT photo_id, rank_position, selection_position FROM photo_rankings "
                "ORDER BY photo_id"
            )
        ).all()

    assert projects == [(1, "Projekt 1", None), (2, "Projekt 2", None)]
    assert rankings == [(1, 1, None), (2, 2, None), (3, 3, None)]


def test_downgrade_removes_both_columns_and_keeps_the_rows(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_rows(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        projects = _columns(connection, "projects")
        rankings = _columns(connection, "photo_rankings")
        project_rows = connection.execute(text("SELECT id, name FROM projects ORDER BY id")).all()
        ranking_rows = connection.execute(
            text("SELECT photo_id, rank_position FROM photo_rankings ORDER BY photo_id")
        ).all()

    assert "selection_target" not in projects
    assert "selection_position" not in rankings
    assert {"id", "name", "opencloud_drive_id", "opencloud_path"} <= set(projects)
    assert {"rank_score", "rank_position", "event_id"} <= set(rankings)
    assert project_rows == [(1, "Projekt 1"), (2, "Projekt 2")]
    assert ranking_rows == [(1, 1), (2, 2), (3, 3)]


def test_a_repeated_upgrade_brings_the_columns_back_empty(tmp_path: Path) -> None:
    """Der Rueckweg stellt die Struktur wieder her, nie die Daten: ein danach erneutes `upgrade()`
    liefert die Spalten LEER zurueck, nicht mit den vorherigen Plaetzen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_rows(connection)
        _apply(connection, "upgrade")
        connection.execute(text("UPDATE photo_rankings SET selection_position = 1"))
        connection.execute(text("UPDATE projects SET selection_target = 42"))
        _apply(connection, "downgrade")
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        targets = connection.execute(text("SELECT selection_target FROM projects")).scalars().all()
        positions = (
            connection.execute(text("SELECT selection_position FROM photo_rankings"))
            .scalars()
            .all()
        )

    assert targets == [None, None]
    assert positions == [None, None, None]
