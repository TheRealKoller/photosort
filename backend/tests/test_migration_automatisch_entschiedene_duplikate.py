"""Die Migration der automatisch entschiedenen Duplikatgruppen (ADR 0146 Punkt 2/3).

Drei additive Spalten: `photos.pixel_count` (nullable, KEIN Backfill), `photos.pixel_count_probed`
und `photo_scores.auto_decided` (beide NOT NULL mit bleibendem `server_default false`). Der
Rueckweg entfernt genau diese drei Spalten.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

_MIGRATION_FILENAME = "8c0f0296e1cd_automatisch_entschiedene_duplikate.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("auto_decided_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration."""
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
            "CREATE TABLE photo_scores ("
            "photo_id INTEGER NOT NULL PRIMARY KEY, "
            "sharpness FLOAT NOT NULL, "
            "exposure FLOAT NOT NULL)"
        )
    )


def _insert_existing_rows(connection: Connection) -> None:
    connection.execute(
        text("INSERT INTO photos (id, project_id, relative_path) VALUES (1, 1, 'a.jpg')")
    )
    connection.execute(
        text("INSERT INTO photo_scores (photo_id, sharpness, exposure) VALUES (1, 10.0, 0.0)")
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _columns(connection: Connection, table: str) -> dict[str, dict[str, object]]:
    return {column["name"]: column for column in inspect(connection).get_columns(table)}


def test_revision_chains_onto_the_current_head() -> None:
    module = _load_migration_module()

    assert module.revision == "8c0f0296e1cd"
    assert module.down_revision == "6299223059c8"


def test_the_upgrade_adds_exactly_the_three_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        photo_columns = _columns(connection, "photos")
        score_columns = _columns(connection, "photo_scores")

    assert set(photo_columns) == {
        "id",
        "project_id",
        "relative_path",
        "pixel_count",
        "pixel_count_probed",
    }
    assert set(score_columns) == {"photo_id", "sharpness", "exposure", "auto_decided"}


def test_an_existing_photo_stays_unknown_and_the_marks_start_false(tmp_path: Path) -> None:
    """Kein Backfill: Die Aufloesung eines Bestandsfotos ist UNBEKANNT, nicht 0 - und der Merker
    faellt auf `false`, damit kein Bestand ohne Lauf als automatisch entschieden gilt."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_rows(connection)
        _apply(connection, "upgrade")

        pixel_count, probed = connection.execute(
            text("SELECT pixel_count, pixel_count_probed FROM photos WHERE id = 1")
        ).one()
        (auto_decided,) = connection.execute(
            text("SELECT auto_decided FROM photo_scores WHERE photo_id = 1")
        ).one()

    assert pixel_count is None
    assert probed in (0, False)
    assert auto_decided in (0, False)


def test_both_marks_are_not_null_with_a_lasting_false_default(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        photo_columns = _columns(connection, "photos")
        score_columns = _columns(connection, "photo_scores")

    assert photo_columns["pixel_count"]["nullable"] is True
    assert photo_columns["pixel_count_probed"]["nullable"] is False
    assert str(photo_columns["pixel_count_probed"]["default"]).lower() in {"false", "0"}
    assert score_columns["auto_decided"]["nullable"] is False
    assert str(score_columns["auto_decided"]["default"]).lower() in {"false", "0"}


def test_the_downgrade_drops_exactly_the_three_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_rows(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

        photo_columns = _columns(connection, "photos")
        score_columns = _columns(connection, "photo_scores")
        photos = connection.execute(text("SELECT COUNT(*) FROM photos")).scalar_one()
        scores = connection.execute(text("SELECT COUNT(*) FROM photo_scores")).scalar_one()

    assert set(photo_columns) == {"id", "project_id", "relative_path"}
    assert set(score_columns) == {"photo_id", "sharpness", "exposure"}
    assert (photos, scores) == (1, 1)
