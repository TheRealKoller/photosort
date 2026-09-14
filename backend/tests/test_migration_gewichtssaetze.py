"""Die Migration der Gewichtsfassungen: `quality_weight_sets`, `quality_weight_entries` und der
Fassungsbezug an der Lauf-Zeile (Spec 0432, ADR 0100).

DATENLOS, und das ist hier eine eigene Zusage: Die Migration schreibt KEINE Vorgabefassung ein.
Ohne eine einzige Zeile gelten die Startwerte aus `quality.py`; ein eingeschriebener Vorgabewert
waere von einer uebernommenen Anpassung nicht mehr zu unterscheiden, und "zurueck auf die
Startwerte" hiesse danach "zurueck auf eine Fassung, die jemand uebernommen hat".

`criterion_key` traegt KEINEN Fremdschluessel - derselbe Grund wie bei
`photo_criterion_scores.criterion_key`: Ein neues Kriterium erzwingt nie eine Migration. Geprueft
wird das zusammen mit der Gegenhaelfte (`set_id` traegt sehr wohl einen), sonst bestuende die
Aussage auch fuer eine Tabelle ganz ohne Fremdschluessel.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

_MIGRATION_FILENAME = "c5d6e7f8a9b0_gewichtssaetze.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)

_SETS = "quality_weight_sets"
_ENTRIES = "quality_weight_entries"
_RUNS = "criterion_scoring_runs"
_RUN_COLUMN = "quality_weight_set_id"

# GLEICHHEIT der Spaltenmenge, nicht Teilmenge: Jede spaeter ergaenzte Spalte ist eine Aussage,
# die die Fassung bisher nicht traegt - insbesondere jede Bindung an ein Projekt oder einen
# Nutzer als GELTUNGSBEREICH (der Gewichtssatz gilt global, G1).
_EXPECTED_SET_COLUMNS = {
    "id",
    "created_at",
    "created_by_user_id",
    "origin",
    "based_on_event_id",
    "reverts_set_id",
}
_EXPECTED_ENTRY_COLUMNS = {"id", "set_id", "criterion_key", "weight"}

_NULLABLE_SET_COLUMNS = {"based_on_event_id", "reverts_set_id"}


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("gewichtssaetze_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration: die Nutzertabelle
    (auf sie zeigt der Urheber der Fassung) und die Lauf-Tabelle, die die neue Spalte bekommt."""
    connection.execute(
        text("CREATE TABLE users (id INTEGER NOT NULL PRIMARY KEY, username VARCHAR NOT NULL)")
    )
    connection.execute(
        text(
            f"CREATE TABLE {_RUNS} ("  # noqa: S608
            "id INTEGER NOT NULL PRIMARY KEY, "
            "project_id INTEGER NOT NULL)"
        )
    )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _upgraded(tmp_path: Path) -> Connection:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    connection = engine.connect()
    transaction = connection.begin()
    _create_pre_migration_schema(connection)
    _apply(connection, "upgrade")
    transaction.commit()
    return connection


def _columns(connection: Connection, table: str) -> dict[str, dict[str, object]]:
    return {column["name"]: column for column in inspect(connection).get_columns(table)}


def test_revision_chains_onto_the_current_head() -> None:
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head - die Revision des
    Ereignis-Logs aus Teil 1 derselben Spec. Die Kette selbst prueft `test_migration_chain.py`."""
    module = _load_migration_module()

    assert module.down_revision == "b1c2d3e4f5a6"


def test_the_upgrade_creates_the_set_table_with_exactly_the_expected_columns(
    tmp_path: Path,
) -> None:
    with _upgraded(tmp_path) as connection:
        columns = _columns(connection, _SETS)

    assert set(columns) == _EXPECTED_SET_COLUMNS


def test_the_upgrade_creates_the_entry_table_with_exactly_the_expected_columns(
    tmp_path: Path,
) -> None:
    with _upgraded(tmp_path) as connection:
        columns = _columns(connection, _ENTRIES)

    assert set(columns) == _EXPECTED_ENTRY_COLUMNS


def test_exactly_the_expected_set_columns_are_nullable(tmp_path: Path) -> None:
    """In BEIDE Richtungen: Ein faelschlich nullbares `created_by_user_id` liesse eine Fassung
    ohne Urheber entstehen, ein faelschlich pflichtiges `reverts_set_id` machte jede erste
    Fassung unschreibbar."""
    with _upgraded(tmp_path) as connection:
        columns = _columns(connection, _SETS)

    nullable = {name for name, column in columns.items() if column["nullable"]}
    assert nullable == _NULLABLE_SET_COLUMNS


def test_no_entry_column_is_nullable(tmp_path: Path) -> None:
    """Ein Eintrag ohne Kriterium oder ohne Gewicht traegt keine Aussage - und ein `NULL`-Gewicht
    liefe im Lesepfad in dieselbe Vergiftung wie ein `NaN` (S12)."""
    with _upgraded(tmp_path) as connection:
        columns = _columns(connection, _ENTRIES)

    assert {name for name, column in columns.items() if column["nullable"]} == set()


def test_the_criterion_key_carries_no_foreign_key_while_the_set_binding_does(
    tmp_path: Path,
) -> None:
    """Freier String aus demselben Grund wie bei `photo_criterion_scores`: Ein neues Kriterium
    erzwingt nie eine Migration. Die zweite Haelfte steht im SELBEN Fall - ohne sie bestuende die
    Aussage auch fuer eine Tabelle ganz ohne Fremdschluessel."""
    with _upgraded(tmp_path) as connection:
        foreign_keys = inspect(connection).get_foreign_keys(_ENTRIES)

    constrained = {tuple(key["constrained_columns"]): key["referred_table"] for key in foreign_keys}
    assert constrained == {("set_id",): _SETS}


def test_the_set_and_criterion_pair_is_unique(tmp_path: Path) -> None:
    """Zwei Gewichte fuer dasselbe Kriterium in derselben Fassung waeren zwei Wahrheiten; welche
    gilt, entschiede die Zeilenreihenfolge."""
    with _upgraded(tmp_path) as connection:
        constraints = inspect(connection).get_unique_constraints(_ENTRIES)

    assert [
        constraint["column_names"] for constraint in constraints if constraint["name"] is not None
    ] == [["set_id", "criterion_key"]]


def test_the_revert_reference_points_at_the_set_table_itself(tmp_path: Path) -> None:
    """Zurueckgesetzt wird nie durch Loeschen, sondern durch eine NEUE Fassung, die auf ihre
    Vorgaengerin zeigt - die Kette bleibt dadurch lueckenlos (G10)."""
    with _upgraded(tmp_path) as connection:
        foreign_keys = inspect(connection).get_foreign_keys(_SETS)

    constrained = {tuple(key["constrained_columns"]): key["referred_table"] for key in foreign_keys}
    assert constrained == {("created_by_user_id",): "users", ("reverts_set_id",): _SETS}


def test_the_anchor_column_carries_no_foreign_key(tmp_path: Path) -> None:
    """`based_on_event_id` ist ein ZUSTIMMUNGS-TOKEN, kein Objektverweis (S6): Es wird nie zu
    einer Zeile aufgeloest und muss den Wert `0` fuer "leeres Log" tragen koennen, auf den kein
    Fremdschluessel zeigt."""
    with _upgraded(tmp_path) as connection:
        foreign_keys = inspect(connection).get_foreign_keys(_SETS)

    assert all("based_on_event_id" not in key["constrained_columns"] for key in foreign_keys)


def test_the_run_row_gets_a_nullable_reference_to_the_used_set(tmp_path: Path) -> None:
    """`NULL` heisst "Startwerte oder Altzeile" - jeder bereits gelaufene Kriterienlauf hat mit
    den Startwerten gerechnet, und es gibt keine Fassung, auf die er zeigen koennte."""
    with _upgraded(tmp_path) as connection:
        columns = _columns(connection, _RUNS)
        foreign_keys = inspect(connection).get_foreign_keys(_RUNS)

    assert columns[_RUN_COLUMN]["nullable"]
    assert any(
        key["constrained_columns"] == [_RUN_COLUMN] and key["referred_table"] == _SETS
        for key in foreign_keys
    )


def test_the_upgrade_writes_no_default_weight_set(tmp_path: Path) -> None:
    """DIE Zusage dieser Migration (G1): Ohne eine einzige Zeile gelten die Startwerte aus
    `quality.py`. Ein eingeschriebener Vorgabewert waere von einer uebernommenen Anpassung nicht
    mehr zu unterscheiden."""
    with _upgraded(tmp_path) as connection:
        sets = connection.execute(text(f"SELECT COUNT(*) FROM {_SETS}")).scalar_one()  # noqa: S608
        entries = connection.execute(
            text(f"SELECT COUNT(*) FROM {_ENTRIES}")  # noqa: S608
        ).scalar_one()

    assert (sets, entries) == (0, 0)


def test_the_downgrade_drops_both_tables_and_the_run_column(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        connection.execute(
            text(
                f"INSERT INTO {_SETS} (created_by_user_id, origin) "  # noqa: S608
                "VALUES (1, 'feedback')"
            )
        )
        connection.execute(
            text(
                f"INSERT INTO {_ENTRIES} (set_id, criterion_key, weight) "  # noqa: S608
                "VALUES (1, 'sharpness', 1.2)"
            )
        )
        _apply(connection, "downgrade")

        tables = set(inspect(connection).get_table_names())
        run_columns = set(_columns(connection, _RUNS))

    assert _SETS not in tables
    assert _ENTRIES not in tables
    assert _RUN_COLUMN not in run_columns


def test_the_downgrade_docstring_names_the_loss_of_the_adjusted_weights() -> None:
    """Die Struktur wird wiederhergestellt, nie die Daten: Nach dem Rueckweg rechnet jeder Lauf
    wieder mit den Startwerten, ohne dass irgendetwas das als Verlust ausweist."""
    module = _load_migration_module()
    docstrings = f"{module.__doc__ or ''}\n{module.downgrade.__doc__ or ''}".lower()

    assert "verlust" in docstrings or "verloren" in docstrings or "verliert" in docstrings
    assert "gewicht" in docstrings
