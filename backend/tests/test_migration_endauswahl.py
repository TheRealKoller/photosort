"""Die Migration der Endauswahl: die neue Tabelle `final_selection_decisions`.

DATENLOS in beide Richtungen - es gibt vor dieser Story keine Entscheidungszeilen, und kein
Migrationsschritt berechnet rueckwirkend etwas. Die Endauswahl eines bestehenden Projekts ist damit
genau die Schnittmenge der beiden Entwuerfe.

DIE ZWEI ARTEFAKTE fuer `included` (Zusicherung 17): Unter SQLite ist BOOLEAN ein INTEGER, ein
versehentliches `server_default=sa.text("0")` bliebe ohne die gerenderte Postgres-DDL unsichtbar
(die steht in `test_postgres_ddl_compatibility.py`), und die Modellseite allein zu vergessen faellt
erst produktiv auf. Geprueft wird deshalb HIER an der migrierten Tabelle UND am aus
`Base.metadata` erzeugten Schema.

Der Fremdschluessel ist Pflicht, nicht Geschmack: Die Loeschzusage prueft Erreichbarkeit ueber die
Kanten in `Base.metadata`, eine bloss logische Spalte fiele still aus der Pruefung heraus.
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

from photosort.db import Base

_MIGRATION_FILENAME = "a1b2c3d4e5f6_endauswahl.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)

_TABLE = "final_selection_decisions"


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("endauswahl_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur `photos`, weil
    der Fremdschluessel darauf zeigt."""
    connection.execute(
        text(
            "CREATE TABLE photos ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "project_id INTEGER NOT NULL, "
            "relative_path VARCHAR NOT NULL, "
            "etag VARCHAR NOT NULL, "
            "content_length INTEGER NOT NULL, "
            "taken_at DATETIME NOT NULL, "
            "taken_at_original DATETIME NOT NULL, "
            "last_modified DATETIME NOT NULL)"
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

    assert module.down_revision == "f6a7b8c9d0e1"


def test_the_upgrade_creates_the_table_with_exactly_three_columns(tmp_path: Path) -> None:
    """GLEICHHEIT der Spaltenmenge, nicht Teilmenge: Die Abwesenheit jedes Nutzerbezugs ist die
    Zusage dieser Tabelle (ADR 0099 Punkt 3) - eine spaeter ergaenzte `user_id`- oder
    `decided_by`-Spalte muss hier auffallen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, _TABLE)

    assert set(columns) == {"photo_id", "included", "updated_at"}


def test_the_photo_id_is_primary_key_and_foreign_key_under_a_written_out_name(
    tmp_path: Path,
) -> None:
    """ "Hoechstens eine Entscheidung je Foto" ist damit STRUKTURELL wahr, ohne eigenen
    Unique-Constraint. Der Name ist ausgeschrieben, weil `Base.metadata` keine
    `naming_convention` traegt, aus der einer entstuende - und ein unbenannter Fremdschluessel
    unter SQLite im `downgrade()` nicht droppbar waere."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        inspector = inspect(connection)
        primary_key = inspector.get_pk_constraint(_TABLE)
        foreign_keys = inspector.get_foreign_keys(_TABLE)

    assert primary_key["constrained_columns"] == ["photo_id"]
    assert len(foreign_keys) == 1
    assert foreign_keys[0]["constrained_columns"] == ["photo_id"]
    assert foreign_keys[0]["referred_table"] == "photos"
    assert foreign_keys[0]["referred_columns"] == ["id"]
    assert foreign_keys[0]["name"] == "fk_final_selection_decisions_photo_id"


def test_the_migrated_table_has_included_not_null_without_a_default(tmp_path: Path) -> None:
    """Erstes der beiden Artefakte (Zusicherung 17). Ein Vorgabewert erfaende eine Entscheidung,
    die niemand getroffen hat - und die Abwesenheit der Zeile heisst "unentschieden"."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, _TABLE)

    assert not columns["included"]["nullable"]
    assert columns["included"]["default"] is None


def test_the_updated_at_column_is_a_naive_timestamp_with_a_server_default(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, _TABLE)

    assert not columns["updated_at"]["nullable"]
    assert columns["updated_at"]["default"] is not None
    assert "TIMEZONE" not in str(columns["updated_at"]["type"]).upper()


def test_an_insert_without_included_fails_in_the_model_schema(tmp_path: Path) -> None:
    """Zweites der beiden Artefakte (Zusicherung 17): das aus `Base.metadata` erzeugte Schema.
    Ein am Modell gesetzter Default wuerde von der Migration gar nicht erfasst und faellt nur hier
    auf - beide muessen dieselbe DDL lesen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                text(f"INSERT INTO {_TABLE} (photo_id) VALUES (1)")  # noqa: S608
            )


def test_both_values_round_trip_through_the_model_schema(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text(f"INSERT INTO {_TABLE} (photo_id, included) VALUES (1, 1), (2, 0)")  # noqa: S608
        )

    with engine.connect() as connection:
        rows = connection.execute(
            text(f"SELECT photo_id, included FROM {_TABLE} ORDER BY photo_id")  # noqa: S608
        ).all()

    assert rows == [(1, 1), (2, 0)]


def test_a_second_decision_for_the_same_photo_is_structurally_impossible(tmp_path: Path) -> None:
    """Der Primaerschluessel IST die Zusage "hoechstens eine Entscheidung je Foto" - es gibt
    daneben keinen Unique-Constraint, der sie noch einmal traegt."""
    engine = create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text(f"INSERT INTO {_TABLE} (photo_id, included) VALUES (1, 1)")  # noqa: S608
        )

    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                text(f"INSERT INTO {_TABLE} (photo_id, included) VALUES (1, 0)")  # noqa: S608
            )


def test_the_downgrade_drops_the_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        connection.execute(
            text(
                f"INSERT INTO {_TABLE} (photo_id, included, updated_at) "  # noqa: S608
                "VALUES (1, 1, '2026-09-13 10:00:00')"
            )
        )
        _apply(connection, "downgrade")

        tables = set(inspect(connection).get_table_names())

    assert _TABLE not in tables


def test_the_downgrade_docstring_names_the_loss_of_every_joint_decision() -> None:
    """Die Struktur wird wiederhergestellt, nie die Daten - wer den Rueckwaertsweg aufruft, liest
    am Artefakt selbst, was er verliert."""
    module = _load_migration_module()
    docstrings = f"{module.__doc__ or ''}\n{module.downgrade.__doc__ or ''}".lower()

    assert "verlust" in docstrings or "verloren" in docstrings or "verliert" in docstrings
    assert "entscheidung" in docstrings
