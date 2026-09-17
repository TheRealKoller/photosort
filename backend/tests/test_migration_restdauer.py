from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

# specs/features/0481-restdauer-klassifizierungslauf.md, decisions/0116-restdauer-als-
# servermessung-spanne-im-frontend-keine-gesamtrestzeit.md Punkt 1: EINE rein additive, NULLABLE
# Spalte an `criterion_scoring_runs`, KEIN Backfill und KEIN server_default. Isoliert ueber genau
# diese eine Revision, ohne von der vollen Migrationshistorie abzuhaengen (Muster der bestehenden
# test_migration_*.py).
#
# Die Aussage des fehlenden Backfills: `phase_started_at IS NULL` heisst "kein Beginn bekannt" und
# ist ein regulaerer Zustand, kein Fehler. Genau er entsteht bei einem Lauf, der zum Zeitpunkt der
# Migration bereits laeuft und `phase` schon traegt - er zeigt bis zum naechsten Teilschritt keine
# Restdauer. Ein server_default machte daraus einen erfundenen Beginn, und die Restdauer dieses
# Laufs waere um die gesamte bisherige Laufzeit zu klein, ohne dass irgendetwas fehlschluege.

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / "c5bc9a02c3c2_restdauer.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("restdauer_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die eine
    beruehrte Tabelle mit den Spalten, die der Test tatsaechlich beschreibt."""
    connection.execute(
        text(
            "CREATE TABLE criterion_scoring_runs ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "project_id INTEGER NOT NULL, "
            "scoring_run_id INTEGER NOT NULL, "
            "status VARCHAR(20) NOT NULL, "
            "started_at DATETIME NOT NULL, "
            "finished_at DATETIME, "
            "photos_total INTEGER NOT NULL, "
            "photos_processed INTEGER NOT NULL, "
            "last_progress_at DATETIME NOT NULL, "
            "phase VARCHAR(20))"
        )
    )


def _insert_running_row_with_a_phase(connection: Connection, *, row_id: int) -> None:
    """Genau der von ADR 0116 benannte Bestandszustand: ein Lauf, der WAEHREND der Migration
    laeuft und `phase` bereits traegt - nicht irgendeine Altzeile."""
    connection.execute(
        text(
            "INSERT INTO criterion_scoring_runs (id, project_id, scoring_run_id, status, "
            "started_at, photos_total, photos_processed, last_progress_at, phase) VALUES "
            f"({row_id}, 1, 1, 'running', '2026-09-17 10:00:00', 40, 12, "
            "'2026-09-17 10:05:00', 'criteria')"
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

    assert module.revision == "c5bc9a02c3c2"
    assert module.down_revision == "bcc517b1ab22"


def test_upgrade_adds_the_nullable_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")

        columns = {c["name"]: c for c in inspect(engine).get_columns("criterion_scoring_runs")}
    finally:
        engine.dispose()

    assert "phase_started_at" in columns
    assert columns["phase_started_at"]["nullable"]
    assert columns["phase_started_at"]["default"] is None


def test_a_running_row_with_a_phase_survives_with_null(tmp_path: Path) -> None:
    """Kein Backfill: Der bereits laufende Lauf behaelt seinen Teilschritt und bekommt KEINEN
    erfundenen Beginn. Er faellt damit in den regulaeren `null`-Zweig der Restdauer."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _insert_running_row_with_a_phase(connection, row_id=1)
            _apply(connection, "upgrade")

        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT id, status, phase, phase_started_at FROM criterion_scoring_runs")
            ).all()
    finally:
        engine.dispose()

    assert rows == [(1, "running", "criteria", None)]


def test_after_the_upgrade_an_insert_without_the_column_still_works(tmp_path: Path) -> None:
    """Nullable UND ohne Default - ein Schreibpfad, der noch keinen Teilschritt kennt (die frisch
    angelegte Lauf-Zeile), muss weiterhin schreiben koennen und erzeugt `NULL`."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")
            _insert_running_row_with_a_phase(connection, row_id=7)

        with engine.connect() as connection:
            stored = connection.execute(
                text("SELECT phase_started_at FROM criterion_scoring_runs WHERE id = 7")
            ).scalar_one()
    finally:
        engine.dispose()

    assert stored is None


def test_the_column_holds_a_timestamp(tmp_path: Path) -> None:
    """Ein Zeitstempeltyp, kein Text: Die Restdauer rechnet mit der Differenz zu `now`, und eine
    Textspalte lieferte beim Lesen einen `str`, gegen den sich keine Zeit subtrahieren laesst."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _apply(connection, "upgrade")
            _insert_running_row_with_a_phase(connection, row_id=1)
            connection.execute(
                text(
                    "UPDATE criterion_scoring_runs SET phase_started_at = '2026-09-17 10:04:30' "
                    "WHERE id = 1"
                )
            )

        columns = {c["name"]: c for c in inspect(engine).get_columns("criterion_scoring_runs")}
        with engine.connect() as connection:
            stored = connection.execute(
                text("SELECT phase_started_at FROM criterion_scoring_runs WHERE id = 1")
            ).scalar_one()
    finally:
        engine.dispose()

    assert "DATETIME" in str(columns["phase_started_at"]["type"]).upper()
    assert stored == "2026-09-17 10:04:30"


def test_downgrade_removes_the_column_and_keeps_the_row(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    try:
        with engine.begin() as connection:
            _create_pre_migration_schema(connection)
            _insert_running_row_with_a_phase(connection, row_id=1)
            _apply(connection, "upgrade")
            connection.execute(
                text("UPDATE criterion_scoring_runs SET phase_started_at = '2026-09-17 10:04:30'")
            )
            _apply(connection, "downgrade")

        columns = {c["name"] for c in inspect(engine).get_columns("criterion_scoring_runs")}
        with engine.connect() as connection:
            remaining = connection.execute(
                text("SELECT id, phase FROM criterion_scoring_runs")
            ).all()
    finally:
        engine.dispose()

    assert "phase_started_at" not in columns
    # Die Zeile selbst ueberlebt den Rueckwaertsweg - nur ihr Phasenbeginn ist weg.
    assert remaining == [(1, "criteria")]
