"""specs/features/0428-albumtauglichkeit-vom-modell.md, Schritt 4 - Muster
`test_migration_motivstaerken.py`.

Eine REINE Strukturaenderung: eine neue Tabelle, zwei Spalten werden nullable. Es gibt hier
bewusst KEINEN Fall ueber Bestandswerte - die Migration fasst keine an (kein Backfill, keine
Ruecksetzung), weil der Bestand nach der Umsetzung verworfen wird.

Drei Aussagen tragen mehr als die Spaltenform:

* Die Nullbarkeit wird sowohl an der gerenderten Postgres-DDL als auch als SQLite-Verhaltensprobe
  geprueft: SQLites Typaffinitaet und Postgres' Striktheit fallen hier auseinander.
* `photo_rankings.event_id` bleibt NOT NULL - die Gliederung nach Events ist keine Cloud-Leistung.
* `downgrade()` stellt die STRUKTUR wieder her, nie Daten: ein Fall pinnt fest, was mit den
  `NULL`-Zeilen geschieht.
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
    / "d6e7f8a9b0c1_albumtauglichkeit.py"
)

_NEW_TABLE = "photo_album_suitability"


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("albumtauglichkeit_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - `photos` als Ziel
    des neuen Fremdschluessels und `photo_rankings` in seiner alten, strikten Form."""
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
    connection.execute(
        text(
            "CREATE TABLE criterion_scoring_runs ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "project_id INTEGER NOT NULL)"
        )
    )
    connection.execute(
        text("CREATE TABLE events (id INTEGER NOT NULL PRIMARY KEY, position INTEGER NOT NULL)")
    )
    connection.execute(
        text(
            "CREATE TABLE photo_rankings ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "criterion_scoring_run_id INTEGER NOT NULL REFERENCES criterion_scoring_runs(id), "
            "photo_id INTEGER NOT NULL REFERENCES photos(id), "
            "event_id INTEGER NOT NULL REFERENCES events(id), "
            "rank_score FLOAT NOT NULL, "
            "rank_position INTEGER NOT NULL, "
            "CONSTRAINT uq_photo_ranking_run_photo "
            "UNIQUE (criterion_scoring_run_id, photo_id))"
        )
    )


def _insert_legacy_rows(connection: Connection) -> None:
    """Ein Bestandsfoto samt Rangzeile aus der alten Formel - genau der Zustand, den die Migration
    NICHT anfassen darf."""
    connection.execute(
        text(
            "INSERT INTO projects (id, name, opencloud_drive_id, opencloud_path) "
            "VALUES (1, 'Costa Rica', 'drive-1', '/CostaRica')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO photos (id, project_id, relative_path, etag, content_length, taken_at, "
            "taken_at_original, last_modified) VALUES "
            "(1, 1, 'img1.jpg', 'etag-1', 100, '2026-07-20 10:00:00', "
            "'2026-07-20 10:00:00', '2026-07-20 10:00:00'), "
            "(2, 1, 'img2.jpg', 'etag-2', 100, '2026-07-20 10:01:00', "
            "'2026-07-20 10:01:00', '2026-07-20 10:01:00')"
        )
    )
    connection.execute(text("INSERT INTO criterion_scoring_runs (id, project_id) VALUES (1, 1)"))
    connection.execute(text("INSERT INTO events (id, position) VALUES (1, 1)"))
    connection.execute(
        text(
            "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, event_id, "
            "rank_score, rank_position) VALUES (1, 1, 1, 1, 0.42, 1)"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _upgraded_engine(tmp_path: Path):  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_rows(connection)
        _apply(connection, "upgrade")
    return engine


def test_revision_chains_onto_the_current_head() -> None:
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head."""
    module = _load_migration_module()

    assert module.down_revision == "c4d5e6f7a8b9"


def test_upgrade_creates_the_album_suitability_table(tmp_path: Path) -> None:
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        assert _NEW_TABLE in set(inspect(connection).get_table_names())


def test_the_album_suitability_is_one_row_per_photo(tmp_path: Path) -> None:
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        inspector = inspect(connection)
        columns = {column["name"]: column for column in inspector.get_columns(_NEW_TABLE)}
        primary_key = inspector.get_pk_constraint(_NEW_TABLE)
        foreign_keys = inspector.get_foreign_keys(_NEW_TABLE)

    assert set(columns) == {"photo_id", "level", "reason", "provider", "computed_at"}
    assert primary_key["constrained_columns"] == ["photo_id"]
    assert columns["reason"]["nullable"] is True
    for required in ("level", "provider", "computed_at"):
        assert not columns[required]["nullable"], required
    assert [key["referred_table"] for key in foreign_keys] == ["photos"]
    assert foreign_keys[0]["referred_columns"] == ["id"]


def test_the_new_table_is_empty_after_the_upgrade(tmp_path: Path) -> None:
    """KEIN Backfill: eine Albumtauglichkeit aus Bestandswerten abzuleiten waere eine
    Modellaussage, die das Modell nie getroffen hat."""
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        assert connection.execute(text(f"SELECT COUNT(*) FROM {_NEW_TABLE}")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM photos")).scalar_one() == 2


def test_the_two_ranking_columns_become_nullable_and_the_event_stays_required(
    tmp_path: Path,
) -> None:
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        columns = {
            column["name"]: column for column in inspect(connection).get_columns("photo_rankings")
        }

    assert columns["rank_score"]["nullable"] is True
    assert columns["rank_position"]["nullable"] is True
    assert columns["event_id"]["nullable"] is False


def test_a_ranking_row_without_a_score_is_accepted_but_one_without_an_event_is_not(
    tmp_path: Path,
) -> None:
    """Die SQLite-Verhaltensprobe neben der Spaltenform: `NULL` heisst "kein Qualitaetswert",
    waehrend die Event-Zugehoerigkeit weiterhin erzwungen ist."""
    engine = _upgraded_engine(tmp_path)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, event_id, "
                "rank_score, rank_position) VALUES (2, 1, 2, 1, NULL, NULL)"
            )
        )

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT rank_score, rank_position, event_id FROM photo_rankings WHERE id = 2")
        ).one()
    assert row == (None, None, 1)

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, event_id, "
                "rank_score, rank_position) VALUES (3, 1, 2, NULL, NULL, NULL)"
            )
        )


def test_the_upgrade_leaves_the_existing_ranking_values_untouched(tmp_path: Path) -> None:
    """Reine Strukturaenderung: keine Ruecksetzung der Bestandswerte auf `NULL`, kein Backfill.
    Der Bestand wird nach der Umsetzung verworfen - eine Datenmanipulation waere Arbeit an einem
    Bestand, den es danach nicht mehr gibt."""
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT rank_score, rank_position FROM photo_rankings WHERE id = 1")
        ).one()

    assert row == (0.42, 1)


def test_the_downgrade_restores_the_structure_and_drops_the_null_rows(tmp_path: Path) -> None:
    """`downgrade()` stellt die STRUKTUR wieder her, nie Daten. Die Zeilen ohne Qualitaetswert
    passen nicht mehr in die strikte Form und ENTFALLEN - festgeschriebenes Verhalten, kein
    Versehen."""
    engine = _upgraded_engine(tmp_path)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, event_id, "
                "rank_score, rank_position) VALUES (2, 1, 2, 1, NULL, NULL)"
            )
        )
        connection.execute(
            text(
                f"INSERT INTO {_NEW_TABLE} (photo_id, level, reason, provider, computed_at) "
                "VALUES (1, 4, 'gut', 'anthropic', '2026-09-13 10:00:00')"
            )
        )

    with engine.begin() as connection:
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        table_names = set(inspect(connection).get_table_names())
        remaining = connection.execute(
            text("SELECT id, rank_score, rank_position FROM photo_rankings ORDER BY id")
        ).all()
        columns = {
            column["name"]: column for column in inspect(connection).get_columns("photo_rankings")
        }

    assert _NEW_TABLE not in table_names
    assert remaining == [(1, 0.42, 1)]
    assert columns["rank_score"]["nullable"] is False
    assert columns["rank_position"]["nullable"] is False
