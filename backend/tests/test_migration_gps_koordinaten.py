from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

# specs/features/0051-gps-landmark-cluster-bildung.md, decisions/0072-ortsbezogene-cluster-
# anzeigeort-als-antwortableitung.md: zwei rein additive, NULLABLE Spalten an `photos`, KEIN
# Backfill und KEIN server_default. Isoliert ueber genau diese eine Revision, ohne von der vollen
# Migrationshistorie abzuhaengen (Muster der bestehenden test_migration_*.py).
#
# Warum kein server_default die eigentliche Aussage ist: `0.0` waere eine gueltige Koordinate
# (Golf von Guinea) - ein Default machte aus "kein Ort bekannt" flaechendeckend "Null Island" und
# risse jedes Cluster auf, in dem eine Bestandszeile liegt. "Kein Ort" MUSS `NULL` bleiben.

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "d1e2f3a4b5c6_gps_koordinaten.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("gps_koordinaten_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die eine
    beruehrte Tabelle mit den Spalten, die der Test tatsaechlich beschreibt."""
    connection.execute(
        text(
            "CREATE TABLE photos ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "project_id INTEGER NOT NULL, "
            "relative_path VARCHAR NOT NULL, "
            "etag VARCHAR NOT NULL, "
            "content_length INTEGER NOT NULL, "
            "taken_at DATETIME NOT NULL, "
            "last_modified DATETIME NOT NULL)"
        )
    )


def _insert_legacy_row(connection: Connection, *, row_id: int) -> None:
    connection.execute(
        text(
            "INSERT INTO photos (id, project_id, relative_path, etag, content_length, "
            "taken_at, last_modified) VALUES "
            f"({row_id}, 1, 'a/b-{row_id}.jpg', 'etag-{row_id}', 123, "
            "'2026-07-20 10:00:00', '2026-07-20 10:00:00')"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def test_revision_chains_onto_the_current_head() -> None:
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head, nicht gegen den in
    der Spec genannten (Teststrategie der Spec)."""
    module = _load_migration_module()

    assert module.down_revision == "c9d0e1f2a3b4"


def test_upgrade_adds_both_nullable_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")

        columns = {c["name"]: c for c in inspect(engine).get_columns("photos")}
    finally:
        engine.dispose()

    for column in ("gps_lat", "gps_lon"):
        assert column in columns
        assert columns[column]["nullable"], column


def test_an_existing_row_survives_with_null_in_both_columns(tmp_path: Path) -> None:
    """Kein Backfill (Daniels Entscheidung, siehe Spec "Out of Scope"): Bestandszeilen behalten
    `NULL` in beiden Spalten. Ein `server_default` von `0.0` waere hier fatal - er ist eine
    GUELTIGE Koordinate und keine Abwesenheitsmarkierung."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _insert_legacy_row(connection, row_id=1)
            _apply(connection, "upgrade")

        with engine.connect() as connection:
            rows = connection.execute(text("SELECT id, gps_lat, gps_lon FROM photos")).all()
    finally:
        engine.dispose()

    assert rows == [(1, None, None)]


def test_after_the_upgrade_an_insert_without_coordinates_still_works(tmp_path: Path) -> None:
    """Beide Spalten sind nullable UND ohne Default - ein Schreibpfad, der gar keine Koordinate
    kennt (Nicht-JPEG, EXIF ohne GPS), muss weiterhin schreiben koennen und erzeugt `NULL`."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")
            _insert_legacy_row(connection, row_id=7)

        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT gps_lat, gps_lon FROM photos WHERE id = 7")
            ).one()
    finally:
        engine.dispose()

    assert row == (None, None)


def test_the_columns_hold_a_full_precision_coordinate(tmp_path: Path) -> None:
    """Der Typ muss ein Gleitkommatyp sein: eine ganzzahlige Spalte machte aus 48.858093 ein
    `48` und damit aus einer Adresse eine Region - ohne dass irgendetwas fehlschluege."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")
            _insert_legacy_row(connection, row_id=1)
            connection.execute(
                text("UPDATE photos SET gps_lat = 48.858093, gps_lon = 2.294694 WHERE id = 1")
            )

        with engine.connect() as connection:
            lat, lon = connection.execute(
                text("SELECT gps_lat, gps_lon FROM photos WHERE id = 1")
            ).one()
    finally:
        engine.dispose()

    assert lat == 48.858093
    assert lon == 2.294694


def test_downgrade_removes_both_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _insert_legacy_row(connection, row_id=1)
            _apply(connection, "upgrade")
            connection.execute(text("UPDATE photos SET gps_lat = 48.85, gps_lon = 2.29"))
            _apply(connection, "downgrade")

        columns = {c["name"] for c in inspect(engine).get_columns("photos")}
        with engine.connect() as connection:
            remaining = connection.execute(text("SELECT id FROM photos")).all()
    finally:
        engine.dispose()

    assert "gps_lat" not in columns
    assert "gps_lon" not in columns
    # Die Zeile selbst ueberlebt den Rueckwaertsweg - nur ihre Koordinaten sind weg.
    assert remaining == [(1,)]
