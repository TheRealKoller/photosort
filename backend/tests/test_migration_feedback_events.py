"""Die Migration des Ereignis-Logs: die neue Tabelle `feedback_events` (Spec 0432, ADR 0100).

DATENLOS in beide Richtungen - vor dieser Story gibt es keine Ereigniszeilen, und kein
Migrationsschritt leitet welche aus dem Bestand ab. Das Log haelt, DASS korrigiert wurde; der
Bestand haelt nur den heutigen Stand und traegt die Information nicht.

`event_id` traegt KEINEN Fremdschluessel, obwohl die Spalte wie eine Referenz aussieht:
`worker.py::rebuild_run_grouping` loescht die `Event`-Zeilen eines Laufs und legt sie neu an. Ein
echter Fremdschluessel hielte den Neuaufbau an oder risse Log-Zeilen mit - beides braeche die
Append-only-Zusage. Die vier Nachweise dieser Zusage stehen verteilt: am Modell und als
AST-Waechter in `test_feedback_event_model.py`, an der gerenderten Postgres-DDL in
`test_postgres_ddl_compatibility.py`, als Verhaltensfall ueber `rebuild_run_grouping` in
`test_feedback_log.py`. Hier steht die Migrationshaelfte des ersten - der Vollstaendigkeit der
Fremdschluesselmenge an der migrierten Tabelle.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

_MIGRATION_FILENAME = "b1c2d3e4f5a6_feedback_events.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)

_TABLE = "feedback_events"

# Der vollstaendige Spaltensatz, als GLEICHHEIT geprueft und nicht als Teilmenge: Jede spaeter
# ergaenzte Spalte ist eine Aussage, die das Log bisher nicht traegt - insbesondere jede, die
# Bilddaten oder Fremdtext hereinbraechte (L8).
_EXPECTED_COLUMNS = {
    "id",
    "project_id",
    "user_id",
    "photo_id",
    "kind",
    "occurred_at",
    "weight",
    "criterion_scoring_run_id",
    "event_id",
    "replaced_photo_id",
    "motif_key",
    "motif_strength",
    "level",
    "replaced_level",
    "quality",
    "replaced_quality",
}

# Nullbarkeit je Spalte, einzeln festgelegt statt aus dem Modell abgeleitet: `user_id` nullable
# ist die Zusage "keine Zuschreibung" der gemeinsamen Entscheidung (S9), die eingefrorenen Zahlen
# nullable die Zusage "ein Foto ohne Modellbewertung erzeugt trotzdem ein Ereignis" (L4).
_NULLABLE_COLUMNS = {
    "user_id",
    "criterion_scoring_run_id",
    "event_id",
    "replaced_photo_id",
    "motif_key",
    "motif_strength",
    "level",
    "replaced_level",
    "quality",
    "replaced_quality",
}


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("feedback_events_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - genau die vier
    Tabellen, auf die ein Fremdschluessel dieser Tabelle zeigt. `events` steht bewusst NICHT
    dabei: Auf sie zeigt keiner, und genau das ist die Zusage."""
    connection.execute(
        text("CREATE TABLE projects (id INTEGER NOT NULL PRIMARY KEY, name VARCHAR NOT NULL)")
    )
    connection.execute(
        text("CREATE TABLE users (id INTEGER NOT NULL PRIMARY KEY, username VARCHAR NOT NULL)")
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
            "CREATE TABLE criterion_scoring_runs ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "project_id INTEGER NOT NULL)"
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
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head (Spec 0431). Die
    Kette selbst prueft `test_migration_chain.py`."""
    module = _load_migration_module()

    assert module.down_revision == "a1b2c3d4e5f6"


def test_the_upgrade_creates_the_table_with_exactly_the_expected_columns(tmp_path: Path) -> None:
    """GLEICHHEIT der Spaltenmenge, nicht Teilmenge - siehe `_EXPECTED_COLUMNS`."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, _TABLE)

    assert set(columns) == _EXPECTED_COLUMNS


def test_exactly_the_expected_columns_are_nullable(tmp_path: Path) -> None:
    """Nullbarkeit je Spalte, in BEIDE Richtungen geprueft: Eine faelschlich nullable
    `project_id` liesse eine Ereigniszeile entstehen, die die Projektloeschung nicht findet; ein
    faelschlich pflichtiges `level` wiese jedes Foto ohne Modellbewertung ab (L4)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, _TABLE)

    nullable = {name for name, column in columns.items() if column["nullable"]}
    assert nullable == _NULLABLE_COLUMNS


def test_the_event_id_column_carries_no_foreign_key_while_the_others_do(tmp_path: Path) -> None:
    """An der MIGRIERTEN Tabelle haengt kein Fremdschluessel auf `events` - und die uebrigen
    Verweisspalten tragen sehr wohl einen. Die zweite Haelfte ist nicht Beiwerk: Ohne sie
    bestuende die Aussage auch fuer eine Tabelle ganz ohne Fremdschluessel."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        foreign_keys = inspect(connection).get_foreign_keys(_TABLE)

    constrained = {tuple(key["constrained_columns"]): key["referred_table"] for key in foreign_keys}
    assert constrained == {
        ("project_id",): "projects",
        ("user_id",): "users",
        ("photo_id",): "photos",
        ("replaced_photo_id",): "photos",
        ("criterion_scoring_run_id",): "criterion_scoring_runs",
    }
    assert "events" not in constrained.values()


def test_the_project_id_is_indexed(tmp_path: Path) -> None:
    """Die Diagnose liest projektuebergreifend, die Projektloeschung dagegen genau ueber diese
    Spalte - und sie laeuft ueber ein Log, das mit jeder Korrektur waechst."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        indexes = inspect(connection).get_indexes(_TABLE)

    assert any(index["column_names"] == ["project_id"] for index in indexes)


def test_the_kind_column_is_a_string_enum_without_a_native_type(tmp_path: Path) -> None:
    """`native_enum=False`: Ein neuer `kind`-Wert erzwingt sonst unter Postgres eine
    Typmigration, waehrend SQLite sie nie verlangt - der Unterschied faellt erst produktiv auf."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, _TABLE)

    assert "VARCHAR" in str(columns["kind"]["type"]).upper()
    assert not columns["kind"]["nullable"]


def test_the_weight_column_defaults_to_one_on_the_server(tmp_path: Path) -> None:
    """Der Vorgabewert steht am Server, nicht nur am Modell: Eine ueber rohes SQL eingefuegte
    Zeile traegt sonst kein Gewicht, und die Ableitung multiplizierte mit `NULL`."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        connection.execute(
            text(
                f"INSERT INTO {_TABLE} (project_id, photo_id, kind) "  # noqa: S608
                "VALUES (1, 1, 'photo_included')"
            )
        )

        weight = connection.execute(
            text(f"SELECT weight FROM {_TABLE}")  # noqa: S608
        ).scalar_one()

    assert weight == 1.0


def test_the_downgrade_drops_the_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        connection.execute(
            text(
                f"INSERT INTO {_TABLE} (project_id, photo_id, kind, occurred_at) "  # noqa: S608
                "VALUES (1, 1, 'photo_included', '2026-09-13 10:00:00')"
            )
        )
        _apply(connection, "downgrade")

        tables = set(inspect(connection).get_table_names())

    assert _TABLE not in tables


def test_the_downgrade_docstring_names_the_loss_of_every_recorded_correction() -> None:
    """Die Struktur wird wiederhergestellt, nie die Daten - und hier gibt es keine zweite Stelle,
    an der die Ereignisse stuenden: Der Bestand haelt den heutigen Stand, nicht den Verlauf."""
    module = _load_migration_module()
    docstrings = f"{module.__doc__ or ''}\n{module.downgrade.__doc__ or ''}".lower()

    assert "verlust" in docstrings or "verloren" in docstrings or "verliert" in docstrings
    assert "korrektur" in docstrings
