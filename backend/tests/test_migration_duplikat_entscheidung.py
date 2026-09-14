"""Die Migration der Ausschuss-Entscheidung: die neue Tabelle `photo_duplicate_decisions`.

DATENLOS in beide Richtungen - es gibt vor dieser Story keine Entscheidungszeilen, und kein
Migrationsschritt berechnet rueckwirkend etwas. Ein bestehendes Projekt behaelt damit genau den
Ausschuss, den sein letzter Lauf vorgeschlagen hat.

DIE SPALTE SPEICHERT DEN ENUM-NAMEN, NICHT SEINEN WERT: In `photo_duplicate_decisions.decision`
steht `'KEEP'`, nicht `'keep'`. `SQLEnum(DuplicateDecision, native_enum=False)` legt ohne
`values_callable` den `.name` ab, auch bei einem `enum.StrEnum` mit kleingeschriebenem `.value` -
dieselbe Eigenschaft, die `tests/test_migration_albumentscheidung.py` fuer `ratings.status`
festhaelt. Sie steht hier fest, weil das Ueberlebenden-Praedikat (Auflage S2) POSITIV auf `keep`
vergleicht: Liefe die Modellseite eines Tages auf den kleingeschriebenen Wert um, verglichen
Bestandszeilen und Praedikat gegen verschiedene Schreibweisen, und jede `keep`-Entscheidung fiele
still aus dem Ueberlebendenbestand.

Der Fremdschluessel ist Pflicht, nicht Geschmack (Auflage S11): Die Loeschzusage prueft
Erreichbarkeit ueber die Kanten in `Base.metadata`, eine bloss logische Spalte fiele still aus der
Pruefung heraus.
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
from photosort.models import DuplicateDecision, PhotoDuplicateDecision

_MIGRATION_FILENAME = "d7e8f9a0b1c2_duplikat_entscheidung.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)

_TABLE = "photo_duplicate_decisions"


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "duplikat_entscheidung_migration", _MIGRATION_PATH
    )
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

    assert module.down_revision == "c5d6e7f8a9b0"


def test_the_upgrade_creates_the_table_with_exactly_two_columns(tmp_path: Path) -> None:
    """GLEICHHEIT der Spaltenmenge, nicht Teilmenge: Die Abwesenheit jedes Nutzerbezugs ist eine
    Zusage dieser Tabelle (ADR 0104 Punkt 2) - eine spaeter ergaenzte `user_id`- oder
    `decided_by`-Spalte muss hier auffallen. Es gibt auch kein `updated_at`: Die Story kennt keine
    Anzeige und keine Sortierung nach dem Zeitpunkt der Entscheidung."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, _TABLE)

    assert set(columns) == {"photo_id", "decision"}


def test_the_photo_id_is_primary_key_and_foreign_key_under_a_written_out_name(
    tmp_path: Path,
) -> None:
    """Auflage S11. "Hoechstens eine Entscheidung je Foto" ist damit STRUKTURELL wahr, ohne eigenen
    Unique-Constraint - und genau darauf beruht, dass ein wiederholtes `PUT` ueberschreibt statt in
    eine 500 zu laufen. Der Name ist ausgeschrieben, weil `Base.metadata` keine
    `naming_convention` traegt und ein unbenannter Fremdschluessel unter SQLite im `downgrade()`
    nicht droppbar waere."""
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
    assert foreign_keys[0]["name"] == "fk_photo_duplicate_decisions_photo_id"


def test_the_migrated_table_has_decision_not_null_without_a_default(tmp_path: Path) -> None:
    """Auflage S12: Die Abwesenheit der Zeile heisst "nicht entschieden". Ein Vorgabewert erfaende
    eine Entscheidung, die niemand getroffen hat - und diese Entscheidung bestimmt, was den
    Homeserver verlaesst."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        columns = _columns(connection, _TABLE)

    assert not columns["decision"]["nullable"]
    assert columns["decision"]["default"] is None


def test_an_insert_without_decision_fails_in_the_model_schema(tmp_path: Path) -> None:
    """Das aus `Base.metadata` erzeugte Schema, zweite Haelfte der Zusage oben: Ein am MODELL
    gesetzter Default wuerde von der Migration gar nicht erfasst und faellt nur hier auf."""
    engine = create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text(f"INSERT INTO {_TABLE} (photo_id) VALUES (1)"))  # noqa: S608


def test_the_column_stores_the_enum_name_not_its_value(tmp_path: Path) -> None:
    """Die Schreibweise, gegen die das Ueberlebenden-Praedikat spaeter vergleicht - gemessen am
    aus `Base.metadata` erzeugten Schema statt behauptet.

    Ein Umstieg auf `values_callable` (kleingeschriebene Werte) ist zulaessig, aber nie
    stillschweigend: Bestandszeilen traegen dann die alte Schreibweise, und eine `keep`-Zeile
    fiele ohne Konvertierungsschritt aus dem Ueberlebendenbestand."""
    engine = create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            PhotoDuplicateDecision.__table__.insert(),
            [
                {"photo_id": 1, "decision": DuplicateDecision.KEEP},
                {"photo_id": 2, "decision": DuplicateDecision.DISCARD},
            ],
        )

    with engine.connect() as connection:
        rows = connection.execute(
            text(f"SELECT photo_id, decision FROM {_TABLE} ORDER BY photo_id")  # noqa: S608
        ).all()

    assert rows == [(1, "KEEP"), (2, "DISCARD")]


def test_both_values_round_trip_through_the_model_schema(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                f"INSERT INTO {_TABLE} (photo_id, decision) "  # noqa: S608
                "VALUES (1, 'KEEP'), (2, 'DISCARD')"
            )
        )

    with engine.connect() as connection:
        rows = connection.execute(
            PhotoDuplicateDecision.__table__.select().order_by(PhotoDuplicateDecision.photo_id)
        ).all()

    assert [row.decision for row in rows] == [DuplicateDecision.KEEP, DuplicateDecision.DISCARD]


def test_a_second_decision_for_the_same_photo_is_structurally_impossible(tmp_path: Path) -> None:
    """Der Primaerschluessel IST die Zusage "hoechstens eine Entscheidung je Foto" - es gibt
    daneben keinen Unique-Constraint, der sie noch einmal traegt."""
    engine = create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text(f"INSERT INTO {_TABLE} (photo_id, decision) VALUES (1, 'KEEP')")  # noqa: S608
        )

    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    f"INSERT INTO {_TABLE} (photo_id, decision) VALUES (1, 'DISCARD')"  # noqa: S608
                )
            )


def test_the_upgrade_touches_no_data_at_all() -> None:
    """Kein Backfill: Ein bestehendes Projekt behaelt genau den Ausschuss, den sein letzter Lauf
    vorgeschlagen hat. Ein eingeschriebener Vorgabewert waere von einer getroffenen Entscheidung
    nicht mehr zu unterscheiden."""
    module = _load_migration_module()
    quelle = _MIGRATION_PATH.read_text(encoding="utf-8")

    assert module.upgrade is not None
    for anweisung in ("INSERT ", "UPDATE ", "DELETE "):
        assert anweisung not in quelle.upper()


def test_the_downgrade_drops_the_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        connection.execute(
            text(f"INSERT INTO {_TABLE} (photo_id, decision) VALUES (1, 'KEEP')")  # noqa: S608
        )
        _apply(connection, "downgrade")

        tables = set(inspect(connection).get_table_names())

    assert _TABLE not in tables


def test_the_downgrade_docstring_names_the_loss_of_every_decision() -> None:
    """Die Struktur wird wiederhergestellt, nie die Daten - wer den Rueckwaertsweg aufruft, liest
    am Artefakt selbst, was er verliert. Hier wiegt das schwerer als bei einer Anzeigetabelle: Mit
    den Zeilen faellt jede ausdrueckliche Herausnahme aus dem Cloud-Bestand fort."""
    module = _load_migration_module()
    docstrings = f"{module.__doc__ or ''}\n{module.downgrade.__doc__ or ''}".lower()

    assert "verlust" in docstrings or "verloren" in docstrings or "verliert" in docstrings
    assert "entscheidung" in docstrings
