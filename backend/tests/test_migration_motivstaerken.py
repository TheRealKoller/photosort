"""specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 3 - Muster
`test_migration_kamera_zeitversatz.py`.

Rein additiv: drei neue Tabellen, keine bestehende Spalte wird angefasst. Zwei Aussagen tragen
mehr als die Spaltenform:

* Nach `upgrade()` sind alle drei Tabellen LEER. Es gibt keinen Backfill aus
  `detected_category_confidences` - eine solche Ableitung wäre eine Modellaussage, die das Modell
  nie getroffen hat, und ein automatischer Lauf wären ungefragte Cloud-Kosten.
* Der Rückweg stellt die STRUKTUR wieder her, nie Daten. Ein Bestand an Motivstärken ist nach
  `downgrade()` fort, und das ist festgeschriebenes Verhalten.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "b7c8d9e0f1a2_motivstaerken.py"
)

_NEW_TABLES = (
    "photo_motif_assessments",
    "photo_motif_strengths",
    "photo_motif_corrections",
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("motivstaerken_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die drei
    Tabellen, auf die die neuen Fremdschluessel zeigen."""
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
            "CREATE TABLE users ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "username VARCHAR NOT NULL, "
            "password_hash VARCHAR NOT NULL)"
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


def _insert_legacy_rows(connection: Connection) -> None:
    """Ein Bestandsfoto samt Nutzer - genau der Zustand, in dem die Migration KEINE Motivzeile
    erzeugen darf."""
    connection.execute(
        text(
            "INSERT INTO projects (id, name, opencloud_drive_id, opencloud_path) "
            "VALUES (1, 'Costa Rica', 'drive-1', '/CostaRica')"
        )
    )
    connection.execute(
        text("INSERT INTO users (id, username, password_hash) VALUES (1, 'daniel', 'hash')")
    )
    connection.execute(
        text(
            "INSERT INTO photos (id, project_id, relative_path, etag, content_length, taken_at, "
            "taken_at_original, last_modified) VALUES "
            "(1, 1, 'img1.jpg', 'etag-1', 100, '2026-07-20 10:00:00', "
            "'2026-07-20 10:00:00', '2026-07-20 10:00:00')"
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

    assert module.down_revision == "a6b7c8d9e0f1"


def test_upgrade_creates_all_three_tables(tmp_path: Path) -> None:
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        table_names = set(inspect(connection).get_table_names())

    for table_name in _NEW_TABLES:
        assert table_name in table_names, table_name


def test_the_assessment_header_is_one_row_per_photo(tmp_path: Path) -> None:
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        inspector = inspect(connection)
        columns = {
            column["name"]: column for column in inspector.get_columns("photo_motif_assessments")
        }
        primary_key = inspector.get_pk_constraint("photo_motif_assessments")

    assert set(columns) == {
        "photo_id",
        "source",
        "excluded_document",
        "provider",
        "computed_at",
    }
    assert primary_key["constrained_columns"] == ["photo_id"]
    assert columns["provider"]["nullable"] is True
    for required in ("source", "excluded_document", "computed_at"):
        assert not columns[required]["nullable"], required


def test_the_exclusion_flag_has_no_default_at_all(tmp_path: Path) -> None:
    """Ein Schreibpfad, der die Spalte vergisst, soll laut an der NOT-NULL-Bedingung scheitern
    statt still ein Foto aus jeder Motivauswahl zu nehmen."""
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        column = next(
            column
            for column in inspect(connection).get_columns("photo_motif_assessments")
            if column["name"] == "excluded_document"
        )

    assert column["default"] is None


def test_the_strength_row_points_at_the_header_and_not_at_the_photo(tmp_path: Path) -> None:
    """Eine Staerke kann ohne Kopfzeile nicht existieren."""
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        foreign_keys = inspect(connection).get_foreign_keys("photo_motif_strengths")

    assert [key["referred_table"] for key in foreign_keys] == ["photo_motif_assessments"]
    assert foreign_keys[0]["referred_columns"] == ["photo_id"]


def test_the_correction_row_points_at_the_photo_and_the_user_and_at_no_run(
    tmp_path: Path,
) -> None:
    """Lauf-Unabhaengigkeit auch im Schema: keine Kante auf eine Lauf-Tabelle."""
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        foreign_keys = inspect(connection).get_foreign_keys("photo_motif_corrections")

    assert {key["referred_table"] for key in foreign_keys} == {"photos", "users"}


def test_both_unique_constraints_exist_and_exclude_the_user(tmp_path: Path) -> None:
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        inspector = inspect(connection)
        strength = inspector.get_unique_constraints("photo_motif_strengths")
        correction = inspector.get_unique_constraints("photo_motif_corrections")

    assert [(c["name"], c["column_names"]) for c in strength] == [
        ("uq_motif_strength_photo_key", ["photo_id", "motif_key"])
    ]
    assert [(c["name"], c["column_names"]) for c in correction] == [
        ("uq_motif_correction_photo_key", ["photo_id", "motif_key"])
    ]


def test_all_three_tables_are_empty_after_the_upgrade(tmp_path: Path) -> None:
    """KEIN Backfill: Bestandsfotos erhalten Motivstaerken erst bei einem Lauf, den der Nutzer
    selbst ausloest - es entstehen keine ungefragten Cloud-Kosten, und ein Foto ohne Kopfzeile ist
    genau das, was die Oberflaeche als "noch nicht klassifiziert" zeigt."""
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM photos")).scalar_one() == 1
        for table_name in _NEW_TABLES:
            count = connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
            assert count == 0, table_name


def test_the_upgrade_leaves_the_existing_photo_row_untouched(tmp_path: Path) -> None:
    """Rein additiv: keine bestehende Spalte wird angefasst."""
    engine = _upgraded_engine(tmp_path)

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT relative_path, taken_at FROM photos WHERE id = 1")
        ).one()
        photo_columns = {column["name"] for column in inspect(connection).get_columns("photos")}

    assert row.relative_path == "img1.jpg"
    assert str(row.taken_at).startswith("2026-07-20 10:00:00")
    assert photo_columns == {
        "id",
        "project_id",
        "relative_path",
        "etag",
        "content_length",
        "taken_at",
        "taken_at_original",
        "last_modified",
    }


def test_a_written_vector_survives_a_round_trip_through_the_new_tables(tmp_path: Path) -> None:
    """Die Tabellen sind tatsaechlich beschreibbar - Spaltenform allein sagt darueber nichts."""
    engine = _upgraded_engine(tmp_path)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO photo_motif_assessments "
                "(photo_id, source, excluded_document, provider, computed_at) "
                "VALUES (1, 'cloud', 0, 'anthropic', '2026-09-12 10:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO photo_motif_strengths (photo_id, motif_key, strength) "
                "VALUES (1, 'menschen', 0.75)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO photo_motif_corrections "
                "(photo_id, user_id, motif_key, applies, updated_at) "
                "VALUES (1, 1, 'menschen', 0, '2026-09-12 11:00:00')"
            )
        )

    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT strength FROM photo_motif_strengths WHERE photo_id = 1")
            ).scalar_one()
            == 0.75
        )


def test_the_downgrade_removes_all_three_tables_again(tmp_path: Path) -> None:
    engine = _upgraded_engine(tmp_path)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO photo_motif_assessments "
                "(photo_id, source, excluded_document, provider, computed_at) "
                "VALUES (1, 'local', 0, NULL, '2026-09-12 10:00:00')"
            )
        )

    with engine.begin() as connection:
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        table_names = set(inspect(connection).get_table_names())

    for table_name in _NEW_TABLES:
        assert table_name not in table_names, table_name
    assert "photos" in table_names


def test_the_downgrade_leaves_the_photo_rows_in_place(tmp_path: Path) -> None:
    """Der Rueckweg stellt STRUKTUR wieder her, nie Daten - aber er nimmt auch keine mit, die ihn
    nichts angeht."""
    engine = _upgraded_engine(tmp_path)

    with engine.begin() as connection:
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM photos")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 1
