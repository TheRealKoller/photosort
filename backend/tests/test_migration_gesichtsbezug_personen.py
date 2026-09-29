"""Die Migration des Gesichtsbezugs: je eine Box an Erkennung und Korrektur, dazu die Kante
Korrektur -> Referenz.

Geprueft am Schema-Stand unmittelbar davor, der hier ueber die Vorgaenger-Revision selbst entsteht.
Die Aussagen sind die strukturellen: exakte Spaltensaetze, `person_references` ohne Foto- und
Projektspalte, benannte Einschraenkungen, ein Fremdschluessel ohne DB-Aktion und ein Downgrade,
der den Bestand an Zeilen haelt.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, Engine, create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError

from photosort.db import enable_sqlite_foreign_keys

_VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"
_PREVIOUS = _VERSIONS / "1f4027405ea5_personen.py"
_MIGRATION = _VERSIONS / "b0814fc600bf_gesichtsbezug_personen.py"
_BOX = {"face_box_x", "face_box_y", "face_box_width", "face_box_height"}
_DETECTION_BEFORE = {"photo_id", "person_id", "computed_at"}
_CORRECTION_BEFORE = {"id", "photo_id", "person_id", "user_id", "applies", "updated_at"}
_REFERENCE_COLUMNS = {"id", "person_id", "embedding", "model_key", "created_at"}
_VECTOR = "[" + ", ".join(["1.0"] + ["0.0"] * 127) + "]"


def _load(path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _apply(connection: Connection, path: Path, direction: str) -> None:
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(_load(path), direction)()


def _create_pre_migration_schema(connection: Connection) -> None:
    """Die Eltern der Vorgaenger-Revision, dann diese selbst, dann ein Bestand: eine Person mit
    Referenz, eine Erkennung und eine Korrektur."""
    connection.execute(text("CREATE TABLE users (id INTEGER NOT NULL PRIMARY KEY)"))
    connection.execute(text("CREATE TABLE photos (id INTEGER NOT NULL PRIMARY KEY)"))
    connection.execute(
        text("CREATE TABLE criterion_scoring_runs (id INTEGER NOT NULL PRIMARY KEY)")
    )
    _apply(connection, _PREVIOUS, "upgrade")
    connection.execute(text("INSERT INTO users (id) VALUES (1)"))
    connection.execute(text("INSERT INTO photos (id) VALUES (1), (2), (3)"))
    connection.execute(
        text("INSERT INTO persons (id, slot, name, name_key) VALUES (1, 1, 'Anna', 'anna')")
    )
    connection.execute(
        text(
            "INSERT INTO person_references (id, person_id, embedding, model_key) "
            f"VALUES (1, 1, '{_VECTOR}', 'm'), (2, 1, '{_VECTOR}', 'm')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO photo_person_detections (photo_id, person_id, computed_at) "
            "VALUES (1, 1, '2026-09-28 10:00:00')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO photo_person_corrections (id, photo_id, person_id, user_id, applies) "
            "VALUES (1, 1, 1, 1, 1)"
        )
    )


@pytest.fixture
def upgraded(tmp_path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, _MIGRATION, "upgrade")
    # Erst NACH dem Upgrade: Die Durchsetzung soll die neue Kante pruefen, nicht den
    # Tabellenumbau der Migration selbst.
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    engine.dispose()
    return engine


def _columns(connection: Connection, table: str) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns(table)}


def test_the_revision_chains_onto_the_persons_revision() -> None:
    module = _load(_MIGRATION)

    assert module.revision == "b0814fc600bf"
    assert module.down_revision == "1f4027405ea5"


def test_upgrade_adds_exactly_the_box_and_the_reference_edge(upgraded: Engine) -> None:
    with upgraded.connect() as connection:
        detections = _columns(connection, "photo_person_detections")
        corrections = _columns(connection, "photo_person_corrections")
        references = _columns(connection, "person_references")

    assert detections == _DETECTION_BEFORE | _BOX
    assert corrections == _CORRECTION_BEFORE | _BOX | {"reference_id"}
    # Keine Foto- und keine Projektspalte: Eine Projektloeschung erreicht die Referenz nicht.
    assert references == _REFERENCE_COLUMNS


def test_existing_rows_keep_no_box_and_no_reference(upgraded: Engine) -> None:
    with upgraded.connect() as connection:
        detection = connection.execute(
            text(
                "SELECT face_box_x, face_box_y, face_box_width, face_box_height "
                "FROM photo_person_detections"
            )
        ).one()
        correction = connection.execute(
            text(
                "SELECT face_box_x, face_box_y, face_box_width, face_box_height, reference_id "
                "FROM photo_person_corrections"
            )
        ).one()

    assert tuple(detection) == (None, None, None, None)
    assert tuple(correction) == (None, None, None, None, None)


def test_the_reference_edge_is_a_named_foreign_key_and_unique(upgraded: Engine) -> None:
    with upgraded.connect() as connection:
        inspector = inspect(connection)
        edges = {
            (fk["name"], fk["referred_table"], tuple(fk["constrained_columns"]))
            for fk in inspector.get_foreign_keys("photo_person_corrections")
        }
        uniques = {
            (constraint["name"], tuple(constraint["column_names"]))
            for constraint in inspector.get_unique_constraints("photo_person_corrections")
        }
        checks = {
            table: {check["name"] for check in inspector.get_check_constraints(table)}
            for table in ("photo_person_detections", "photo_person_corrections")
        }

    assert (
        "fk_photo_person_corrections_reference_id",
        "person_references",
        ("reference_id",),
    ) in edges
    assert uniques == {
        ("uq_photo_person_correction_photo_person", ("photo_id", "person_id")),
        ("uq_photo_person_corrections_reference_id", ("reference_id",)),
    }
    assert checks == {
        "photo_person_detections": {"ck_photo_person_detections_face_box"},
        "photo_person_corrections": {
            "ck_photo_person_corrections_face_box",
            "ck_photo_person_corrections_face_requires_applies",
            "ck_photo_person_corrections_reference_requires_face",
        },
    }


def _box(x: str = "0.25", y: str = "0.25", width: str = "0.5", height: str = "0.5") -> str:
    return f"{x}, {y}, {width}, {height}"


_CORRECTION_INSERT = (
    "INSERT INTO photo_person_corrections "
    "(photo_id, person_id, user_id, applies, face_box_x, face_box_y, face_box_width, "
    "face_box_height, reference_id) VALUES "
)
_DETECTION_INSERT = (
    "INSERT INTO photo_person_detections "
    "(photo_id, person_id, computed_at, face_box_x, face_box_y, face_box_width, face_box_height) "
    "VALUES "
)


@pytest.mark.parametrize(
    "statement",
    [
        _CORRECTION_INSERT + "(2, 1, 1, 1, 0.25, 0.25, 0.5, NULL, NULL)",
        _DETECTION_INSERT + "(2, 1, '2026-09-28', 0.25, NULL, 0.5, 0.5)",
        _CORRECTION_INSERT + f"(2, 1, 1, 1, {_box(x=str(1.0 + 2**-20))}, NULL)",
        _DETECTION_INSERT + f"(2, 1, '2026-09-28', {_box(y='-0.0001')})",
        _CORRECTION_INSERT + f"(2, 1, 1, 1, {_box(width='0')}, NULL)",
        _DETECTION_INSERT + f"(2, 1, '2026-09-28', {_box(height='0')})",
        _CORRECTION_INSERT + f"(2, 1, 1, 1, {_box(width='1.0000001')}, NULL)",
        _CORRECTION_INSERT + f"(2, 1, 1, 0, {_box()}, NULL)",
        _CORRECTION_INSERT + "(2, 1, 1, 1, NULL, NULL, NULL, NULL, 1)",
        _CORRECTION_INSERT + f"(2, 1, 1, 1, {_box()}, 99)",
    ],
    ids=[
        "drei-von-vier-korrektur",
        "drei-von-vier-erkennung",
        "x-ueber-eins",
        "y-unter-null",
        "breite-null",
        "hoehe-null-erkennung",
        "breite-ueber-eins",
        "box-ohne-applies",
        "referenz-ohne-box",
        "referenz-unbekannt",
    ],
)
def test_a_row_violating_a_constraint_is_refused(upgraded: Engine, statement: str) -> None:
    with pytest.raises(IntegrityError), upgraded.begin() as connection:
        connection.execute(text(statement))


@pytest.mark.parametrize(
    "statement",
    [
        _CORRECTION_INSERT + f"(2, 1, 1, 1, {_box(x='1.0', width='1')}, 1)",
        _DETECTION_INSERT + f"(2, 1, '2026-09-28', {_box(x='0', y='1.0', height='1')})",
        _CORRECTION_INSERT + f"(2, 1, 1, 1, {_box()}, NULL)",
    ],
    ids=["grenzen-korrektur", "grenzen-erkennung", "box-ohne-referenz"],
)
def test_a_row_at_the_bounds_is_accepted(upgraded: Engine, statement: str) -> None:
    with upgraded.begin() as connection:
        connection.execute(text(statement))


def test_one_reference_belongs_to_at_most_one_correction(upgraded: Engine) -> None:
    with upgraded.begin() as connection:
        connection.execute(text(_CORRECTION_INSERT + f"(2, 1, 1, 1, {_box()}, 1)"))

    with pytest.raises(IntegrityError), upgraded.begin() as connection:
        connection.execute(text(_CORRECTION_INSERT + f"(3, 1, 1, 1, {_box()}, 1)"))


def test_a_linked_reference_cannot_be_deleted_directly(upgraded: Engine) -> None:
    """Ohne DB-Aktion am Fremdschluessel: Wer eine Referenz loescht, ohne die Kante zu leeren,
    scheitert laut statt still."""
    with upgraded.begin() as connection:
        connection.execute(text(_CORRECTION_INSERT + f"(2, 1, 1, 1, {_box()}, 1)"))

    with pytest.raises(IntegrityError), upgraded.begin() as connection:
        connection.execute(text("DELETE FROM person_references WHERE id = 1"))
    with upgraded.begin() as connection:
        connection.execute(text("DELETE FROM person_references WHERE id = 2"))


def test_downgrade_with_boxes_and_edges_keeps_every_row(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, _MIGRATION, "upgrade")
        connection.execute(
            text(
                "UPDATE photo_person_corrections SET face_box_x = 0.25, face_box_y = 0.25, "
                "face_box_width = 0.5, face_box_height = 0.5, reference_id = 1"
            )
        )
        connection.execute(text(_DETECTION_INSERT + f"(2, 1, '2026-09-28', {_box()})"))
        _apply(connection, _MIGRATION, "downgrade")

    with engine.connect() as connection:
        detections = _columns(connection, "photo_person_detections")
        corrections = _columns(connection, "photo_person_corrections")
        counts = {
            table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            for table in (
                "photo_person_detections",
                "photo_person_corrections",
                "person_references",
            )
        }

    assert detections == _DETECTION_BEFORE
    assert corrections == _CORRECTION_BEFORE
    assert counts == {
        "photo_person_detections": 2,
        "photo_person_corrections": 1,
        "person_references": 2,
    }
