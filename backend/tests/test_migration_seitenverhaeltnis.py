from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

# specs/features/0489-fotouebersicht-ohne-beschnitt.md, decisions/0110-seitenverhaeltnis-als-
# serverdatum-und-rasterkachel-neben-der-fotokarte.md: EINE rein additive, NULLABLE Spalte an
# `photos`, KEIN Backfill und KEIN server_default. Isoliert ueber genau diese eine Revision, ohne
# von der vollen Migrationshistorie abzuhaengen (Muster der bestehenden test_migration_*.py).
#
# Warum kein server_default die eigentliche Aussage ist: `NULL` heisst "nicht bekannt" und ist ein
# regulaerer Zustand (ADR 0110 Punkt 1) - genau er steuert die Nachhol-Runde, die beim naechsten
# Projekt-Scan ueber `aspect_ratio IS NULL` laeuft. Ein Default machte jede Bestandszeile zu einer
# BEKANNTEN Angabe; die Nachhol-Runde faende nichts mehr, und jedes Bestandsfoto zeigte dauerhaft
# ein erfundenes Verhaeltnis, ohne dass irgendetwas fehlschluege.

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "bcc517b1ab22_seitenverhaeltnis.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("seitenverhaeltnis_migration", _MIGRATION_PATH)
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
            "'2026-09-14 10:00:00', '2026-09-14 10:00:00')"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def test_revision_chains_onto_the_current_head() -> None:
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head. Beide Kennungen
    kommen aus `scripts/nummern.py migration`, nie aus einem eigenen Blick ins Verzeichnis."""
    module = _load_migration_module()

    assert module.revision == "bcc517b1ab22"
    assert module.down_revision == "a8b9c0d1e2f3"


def test_upgrade_adds_the_nullable_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")

        columns = {c["name"]: c for c in inspect(engine).get_columns("photos")}
    finally:
        engine.dispose()

    assert "aspect_ratio" in columns
    assert columns["aspect_ratio"]["nullable"]
    assert columns["aspect_ratio"]["default"] is None


def test_an_existing_row_survives_with_null(tmp_path: Path) -> None:
    """Kein Backfill: Bestandszeilen behalten `NULL` und werden damit von der Nachhol-Runde
    beim naechsten Projekt-Scan gefunden."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _insert_legacy_row(connection, row_id=1)
            _apply(connection, "upgrade")

        with engine.connect() as connection:
            rows = connection.execute(text("SELECT id, aspect_ratio FROM photos")).all()
    finally:
        engine.dispose()

    assert rows == [(1, None)]


def test_the_column_holds_a_fractional_ratio(tmp_path: Path) -> None:
    """Der Typ muss ein Gleitkommatyp sein: eine ganzzahlige Spalte machte aus 0.667 (Hochformat)
    eine 0 und aus 1.5 (Querformat) eine 1 - jedes Hochformat verschwaende, und das Raster
    rechnete mit einer unbrauchbaren Breite, ohne dass irgendetwas fehlschluege."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")
            _insert_legacy_row(connection, row_id=1)
            connection.execute(text("UPDATE photos SET aspect_ratio = 0.6666666 WHERE id = 1"))

        with engine.connect() as connection:
            ratio = connection.execute(
                text("SELECT aspect_ratio FROM photos WHERE id = 1")
            ).scalar_one()
    finally:
        engine.dispose()

    assert ratio == 0.6666666


def test_after_the_upgrade_an_insert_without_a_ratio_still_works(tmp_path: Path) -> None:
    """Nullable UND ohne Default - ein Schreibpfad, der gar kein Verhaeltnis kennt (nicht
    dekodierbares Bild), muss weiterhin schreiben koennen und erzeugt `NULL`."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")
            _insert_legacy_row(connection, row_id=7)

        with engine.connect() as connection:
            ratio = connection.execute(
                text("SELECT aspect_ratio FROM photos WHERE id = 7")
            ).scalar_one()
    finally:
        engine.dispose()

    assert ratio is None


def test_downgrade_removes_the_column_and_keeps_the_row(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _insert_legacy_row(connection, row_id=1)
            _apply(connection, "upgrade")
            connection.execute(text("UPDATE photos SET aspect_ratio = 1.5"))
            _apply(connection, "downgrade")

        columns = {c["name"] for c in inspect(engine).get_columns("photos")}
        with engine.connect() as connection:
            remaining = connection.execute(text("SELECT id FROM photos")).all()
    finally:
        engine.dispose()

    assert "aspect_ratio" not in columns
    # Die Zeile selbst ueberlebt den Rueckwaertsweg - nur ihr Verhaeltnis ist weg.
    assert remaining == [(1,)]
