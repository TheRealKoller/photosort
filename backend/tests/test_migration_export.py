"""Die Migration des Exports: die beiden Tabellen `export_runs` und `export_photos`.

DATENLOS in beide Richtungen - vor dieser Story gibt es keine Laeufe. Die beiden Tabellen sind
der Nachweis "wann wurde welche Auswahl wohin exportiert" (ADR 0136 Punkt 3).

DIE ZUSAGEN, die hier strukturell geprueft werden:
- `export_runs` traegt KEIN `user_id` (das Ergebnis gehoert dem Projekt, wie bei
  `final_selection_decisions`) - die GLEICHHEIT der Spaltenmenge, nicht Teilmenge.
- `export_photos.photo_id` ist NULLABLE (ein geloeschtes Foto laesst den Schnappschuss stehen).
- `export_photos.error` ist NULLABLE (der Einzelfehler eines `COPY`).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Connection, create_engine, inspect, text

from tests.support.migration import apply_migration, load_migration_module

_MIGRATION_FILENAME = "0b9d6f8d620b_export.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)

_RUN_TABLE = "export_runs"
_PHOTO_TABLE = "export_photos"


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - `projects` und
    `photos`, weil die Fremdschluessel darauf zeigen."""
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
            "taken_at_original DATETIME NOT NULL)"
        )
    )


def _columns(connection: Connection, table: str) -> dict[str, dict[str, object]]:
    return {column["name"]: column for column in inspect(connection).get_columns(table)}


def test_revision_chains_onto_the_current_head() -> None:
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head. Die Kette selbst
    prueft `test_migration_chain.py`."""
    module = load_migration_module(_MIGRATION_PATH)

    assert module.down_revision == "1d3dbfdde02e"


def test_the_upgrade_creates_export_runs_with_exactly_the_expected_columns(
    tmp_path: Path,
) -> None:
    """GLEICHHEIT der Spaltenmenge, nicht Teilmenge: Die Abwesenheit jedes Nutzerbezugs ist die
    Zusage dieser Tabelle (ADR 0136 Punkt 3) - eine spaeter ergaenzte `user_id`-Spalte muss hier
    auffallen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        apply_migration(connection, "upgrade", path=_MIGRATION_PATH)

        columns = _columns(connection, _RUN_TABLE)

    assert set(columns) == {
        "id",
        "project_id",
        "status",
        "started_at",
        "finished_at",
        "target_path",
        "photo_count",
        "exported_count",
        "failed_count",
        "error_message",
        "last_progress_at",
    }


def test_the_upgrade_creates_export_photos_with_exactly_the_expected_columns(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        apply_migration(connection, "upgrade", path=_MIGRATION_PATH)

        columns = _columns(connection, _PHOTO_TABLE)

    assert set(columns) == {"id", "export_run_id", "photo_id", "relative_path", "error"}


def test_export_photos_photo_id_is_nullable(tmp_path: Path) -> None:
    """Der Schnappschuss haengt am LAUF, nicht am Foto - ein geloeschtes Foto laesst die Zeile
    mit `photo_id = NULL` stehen (ADR 0136 Punkt 3)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        apply_migration(connection, "upgrade", path=_MIGRATION_PATH)

        columns = _columns(connection, _PHOTO_TABLE)

    assert columns["photo_id"]["nullable"]


def test_export_photos_error_is_nullable(tmp_path: Path) -> None:
    """Der Einzelfehler eines `COPY` ist der Regelfall seiner Abwesenheit - `NULL` heisst "ohne
    Fehler uebertragen"."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        apply_migration(connection, "upgrade", path=_MIGRATION_PATH)

        columns = _columns(connection, _PHOTO_TABLE)

    assert columns["error"]["nullable"]


def test_the_downgrade_drops_both_tables(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        apply_migration(connection, "upgrade", path=_MIGRATION_PATH)
        apply_migration(connection, "downgrade", path=_MIGRATION_PATH)

        tables = set(inspect(connection).get_table_names())

    assert _RUN_TABLE not in tables
    assert _PHOTO_TABLE not in tables
