from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

# specs/features/0289-feste-kategorien.md, Teststrategie Abschnitt 6: Muster von
# test_migration_remote_category_classification.py (Revision isoliert per importlib laden,
# Vor-Schema minimal in einer Datei-SQLite nachbauen, upgrade()/downgrade() ueber
# Operations.context). NEU und fuer dieses Projekt erstmalig: diese Revision enthaelt
# DATENVERAENDERNDE Schritte, nicht nur Schemaaenderungen - Schema-Assertions allein reichen hier
# nicht, jeder der beiden Datenschritte bekommt einen eigenen Test.

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "d5e6f7a8b9c0_feste_kategorien.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("feste_kategorien_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration (Revision
    c2d3e4f5a6b7) - nur die von d5e6f7a8b9c0 tatsaechlich beruehrten Tabellen/Spalten."""
    connection.execute(text("CREATE TABLE photos (id INTEGER PRIMARY KEY)"))
    connection.execute(
        text(
            "CREATE TABLE photo_scores ("
            "photo_id INTEGER PRIMARY KEY, sharpness FLOAT, exposure FLOAT, phash VARCHAR, "
            "duplicate_of INTEGER, cluster_key VARCHAR, suggested_status VARCHAR(20), "
            "computed_at DATETIME, category_override VARCHAR)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE category_labels ("
            "id INTEGER PRIMARY KEY, canonical_key VARCHAR NOT NULL, "
            "display_name VARCHAR NOT NULL, embedding JSON NOT NULL, created_at DATETIME, "
            "CONSTRAINT uq_category_label_canonical_key UNIQUE (canonical_key))"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE photo_category_detections ("
            "id INTEGER PRIMARY KEY, photo_id INTEGER NOT NULL, "
            "category_label_id INTEGER NOT NULL, raw_label VARCHAR NOT NULL, "
            "confidence FLOAT NOT NULL, provider VARCHAR NOT NULL, computed_at DATETIME NOT NULL, "
            "CONSTRAINT uq_category_detection_photo_label UNIQUE (photo_id, category_label_id), "
            "FOREIGN KEY(photo_id) REFERENCES photos (id), "
            "FOREIGN KEY(category_label_id) REFERENCES category_labels (id))"
        )
    )


def _apply_upgrade(connection: Connection) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        module.upgrade()


def _apply_downgrade(connection: Connection) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        module.downgrade()


def _insert_fine_label_row(connection: Connection) -> None:
    connection.execute(
        text(
            "INSERT INTO category_labels (id, canonical_key, display_name, embedding) "
            "VALUES (1, 'hund', 'Hund', '[0.1, 0.2]')"
        )
    )


def _insert_photo_detection_row(connection: Connection) -> None:
    connection.execute(text("INSERT INTO photos (id) VALUES (1)"))
    connection.execute(
        text(
            "INSERT INTO photo_category_detections "
            "(id, photo_id, category_label_id, raw_label, confidence, provider, computed_at) "
            "VALUES (1, 1, 1, 'Hund', 0.9, 'anthropic', '2026-01-01 00:00:00')"
        )
    )


class TestSchema:
    def test_creates_photo_category_classifications_with_the_expected_columns(
        self, tmp_path: Path
    ) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _apply_upgrade(connection)
            inspector = inspect(engine)
            columns = {col["name"] for col in inspector.get_columns("photo_category_classifications")}
            pk = inspector.get_pk_constraint("photo_category_classifications")
        finally:
            engine.dispose()

        assert columns == {
            "photo_id",
            "category_key",
            "detected_categories",
            "provider",
            "computed_at",
        }
        assert pk["constrained_columns"] == ["photo_id"]

    def test_renames_both_tables_and_the_foreign_key_column(self, tmp_path: Path) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _apply_upgrade(connection)
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            columns = {col["name"] for col in inspector.get_columns("photo_fine_labels")}
            constraint_names = {
                c["name"] for c in inspector.get_unique_constraints("photo_fine_labels")
            }
        finally:
            engine.dispose()

        assert "fine_labels" in table_names
        assert "photo_fine_labels" in table_names
        assert "category_labels" not in table_names
        assert "photo_category_detections" not in table_names
        assert "fine_label_id" in columns
        assert "category_label_id" not in columns
        assert "uq_fine_label_photo_label" in constraint_names

    def test_confidence_column_is_gone(self, tmp_path: Path) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _apply_upgrade(connection)
            columns = {col["name"] for col in inspect(engine).get_columns("photo_fine_labels")}
        finally:
            engine.dispose()

        assert "confidence" not in columns

    def test_the_rename_preserves_the_fine_label_registry_values(self, tmp_path: Path) -> None:
        """Bestehendes Zwei-Revisionen-Muster: Zeile mit alten Namen VOR der Migration einfuegen,
        danach dieselben Werte unter den neuen Namen lesen."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _insert_fine_label_row(connection)
                _apply_upgrade(connection)

            with engine.begin() as connection:
                row = connection.execute(
                    text("SELECT canonical_key, display_name, embedding FROM fine_labels")
                ).fetchone()
        finally:
            engine.dispose()

        assert row == ("hund", "Hund", "[0.1, 0.2]")


class TestDataStepC:
    """Datenschritt (c): `DELETE FROM photo_fine_labels`, aber `fine_labels` BLEIBT."""

    def test_photo_fine_labels_are_deleted_but_the_registry_survives(
        self, tmp_path: Path
    ) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _insert_fine_label_row(connection)
                _insert_photo_detection_row(connection)
                _apply_upgrade(connection)

            with engine.begin() as connection:
                detection_count = connection.execute(
                    text("SELECT count(*) FROM photo_fine_labels")
                ).scalar_one()
                registry_rows = connection.execute(
                    text("SELECT canonical_key FROM fine_labels")
                ).scalars().all()
        finally:
            engine.dispose()

        assert detection_count == 0
        # Der eigentliche Punkt dieses Tests: ein versehentliches `DELETE FROM fine_labels` wuerde
        # die projektuebergreifende Vokabular-Registry vernichten und fiele sonst nicht auf.
        assert list(registry_rows) == ["hund"]


class TestDataStepD:
    """Datenschritt (d): `UPDATE photo_scores SET category_override = NULL` - Pflichtschritt."""

    def test_every_category_override_is_cleared(self, tmp_path: Path) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                connection.execute(
                    text(
                        "INSERT INTO photo_scores (photo_id, sharpness, exposure, phash, "
                        "cluster_key, computed_at, category_override) VALUES "
                        "(1, 0.5, 0.6, 'ab', 'c1', '2026-01-01 00:00:00', 'unerkannt'), "
                        "(2, 0.7, 0.8, 'cd', 'c2', '2026-01-02 00:00:00', NULL)"
                    )
                )
                _apply_upgrade(connection)

            with engine.begin() as connection:
                rows = connection.execute(
                    text(
                        "SELECT photo_id, sharpness, exposure, phash, cluster_key, computed_at, "
                        "category_override FROM photo_scores ORDER BY photo_id"
                    )
                ).fetchall()
        finally:
            engine.dispose()

        # Beide Overrides sind NULL - und alle uebrigen Spalten beider Zeilen unveraendert
        # (Nachweis, dass das UPDATE nicht mehr anfasst als genau eine Spalte).
        assert rows == [
            (1, 0.5, 0.6, "ab", "c1", "2026-01-01 00:00:00", None),
            (2, 0.7, 0.8, "cd", "c2", "2026-01-02 00:00:00", None),
        ]


class TestDowngrade:
    def test_downgrade_restores_the_previous_schema(self, tmp_path: Path) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _apply_upgrade(connection)
            with engine.begin() as connection:
                _apply_downgrade(connection)
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            columns = {col["name"] for col in inspector.get_columns("photo_category_detections")}
        finally:
            engine.dispose()

        assert "category_labels" in table_names
        assert "photo_category_detections" in table_names
        assert "fine_labels" not in table_names
        assert "photo_fine_labels" not in table_names
        assert "photo_category_classifications" not in table_names
        assert "category_label_id" in columns
        assert "confidence" in columns

    def test_downgrade_does_not_bring_the_deleted_data_back(self, tmp_path: Path) -> None:
        """Bewusst festgehaltene EINBAHNSTRASSE (Spec 0289, Teststrategie 6): die in (c)/(d)
        geloeschten Daten sind nicht rekonstruierbar. Das ist keine Schwaeche, sondern die von der
        Spec akzeptierte Konsequenz - als Test festgehalten, damit niemand sie spaeter fuer einen
        Bug haelt."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _insert_fine_label_row(connection)
                _insert_photo_detection_row(connection)
                connection.execute(
                    text(
                        "INSERT INTO photo_scores (photo_id, sharpness, exposure, computed_at, "
                        "category_override) VALUES (1, 0.5, 0.6, '2026-01-01 00:00:00', 'tier')"
                    )
                )
                _apply_upgrade(connection)
            with engine.begin() as connection:
                _apply_downgrade(connection)

            with engine.begin() as connection:
                detection_count = connection.execute(
                    text("SELECT count(*) FROM photo_category_detections")
                ).scalar_one()
                override = connection.execute(
                    text("SELECT category_override FROM photo_scores WHERE photo_id = 1")
                ).scalar_one()
        finally:
            engine.dispose()

        assert detection_count == 0
        assert override is None
