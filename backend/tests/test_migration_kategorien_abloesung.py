from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

# specs/features/0427-motive-mit-staerke.md, PR 3 Schritt 2: ZWEI Migrationen, in dieser
# Reihenfolge - erst Spalten und Constraint, dann die Tabelle. Isoliert ueber genau diese beiden
# Revisionen, ohne von der vollen Migrationshistorie abzuhaengen (Muster der bestehenden
# test_migration_*.py).
#
# Die REIHENFOLGE INNERHALB von `upgrade()` (Datenloeschung vor Constraint-Tausch) ist hier NICHT
# haltbar: SQLite baut die Tabelle in `batch_alter_table` neu auf und verzeiht die falsche
# Reihenfolge, der Test waere dauerhaft gruen. Sie steht als Index-Vergleich auf der gerenderten
# Postgres-DDL in test_postgres_ddl_compatibility.py. Hier steht die DATENWIRKUNG derselben
# Anweisung.

_VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"

_COLUMNS_REVISION = "c3d4e5f6a7b8_kategoriespalten_entfallen.py"
_TABLE_REVISION = "c4d5e6f7a8b9_kategorietabelle_entfaellt.py"


def _load(revision_filename: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"abloesung_{revision_filename}", _VERSIONS_DIR / revision_filename
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _apply(connection: Connection, revision_filename: str, direction: str) -> None:
    module = _load(revision_filename)
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR der Spalten-Revision - nur die drei
    beruehrten Tabellen, mit dem BENANNTEN Unique-Constraint aus Revision c9d0e1f2a3b4."""
    connection.execute(
        text(
            "CREATE TABLE photo_rankings ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "criterion_scoring_run_id INTEGER NOT NULL, "
            "photo_id INTEGER NOT NULL, "
            "event_id INTEGER NOT NULL, "
            "category_key VARCHAR NOT NULL, "
            "rank_score FLOAT NOT NULL, "
            "rank_position INTEGER NOT NULL, "
            "is_primary BOOLEAN NOT NULL, "
            "CONSTRAINT uq_photo_ranking_run_photo_category "
            "UNIQUE (criterion_scoring_run_id, photo_id, category_key))"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE photo_scores ("
            "photo_id INTEGER NOT NULL PRIMARY KEY, "
            "sharpness FLOAT NOT NULL, "
            "exposure FLOAT NOT NULL, "
            "computed_at DATETIME NOT NULL, "
            "category_override VARCHAR)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE photo_category_classifications ("
            "photo_id INTEGER NOT NULL PRIMARY KEY, "
            "category_key VARCHAR NOT NULL, "
            "detected_categories JSON NOT NULL, "
            "detected_category_confidences JSON, "
            "category_confidence FLOAT, "
            "provider VARCHAR NOT NULL, "
            "computed_at DATETIME NOT NULL)"
        )
    )


def _insert_ranking(
    connection: Connection,
    *,
    row_id: int,
    run_id: int = 1,
    photo_id: int = 1,
    category_key: str,
    is_primary: bool,
    rank_position: int = 1,
) -> None:
    connection.execute(
        text(
            "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, event_id, "
            "category_key, rank_score, rank_position, is_primary) VALUES "
            "(:id, :run_id, :photo_id, 7, :category_key, 0.9, :rank_position, :is_primary)"
        ),
        {
            "id": row_id,
            "run_id": run_id,
            "photo_id": photo_id,
            "category_key": category_key,
            "rank_position": rank_position,
            "is_primary": is_primary,
        },
    )


def _unique_constraint_names(target: object) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspect(target).get_unique_constraints(  # type: ignore[arg-type]
            "photo_rankings"
        )
        if constraint["name"] is not None
    }


class TestTheRevisionChain:
    def test_the_columns_revision_chains_onto_the_current_head(self) -> None:
        """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head (die
        Motivstaerken-Revision aus PR 1), nicht gegen den in der Spec genannten."""
        assert _load(_COLUMNS_REVISION).down_revision == "b7c8d9e0f1a2"

    def test_the_table_revision_chains_onto_the_columns_revision(self) -> None:
        """Die festgeschriebene Reihenfolge der beiden Migrationen: Spalten/Constraint zuerst,
        dann die Tabelle."""
        assert _load(_TABLE_REVISION).down_revision == "c3d4e5f6a7b8"


class TestTheColumnsUpgrade:
    def test_the_three_columns_are_gone(self, tmp_path: Path) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _apply(connection, _COLUMNS_REVISION, "upgrade")

            ranking_columns = {c["name"] for c in inspect(engine).get_columns("photo_rankings")}
            score_columns = {c["name"] for c in inspect(engine).get_columns("photo_scores")}
        finally:
            engine.dispose()

        assert "category_key" not in ranking_columns
        assert "is_primary" not in ranking_columns
        assert "category_override" not in score_columns

    def test_the_constraint_is_swapped_back_under_its_old_name(self, tmp_path: Path) -> None:
        """Beide Constraints BENANNT: `Base.metadata` traegt keine `naming_convention`, und ein
        unbenannter Constraint ist unter SQLite nicht droppbar."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _apply(connection, _COLUMNS_REVISION, "upgrade")

            names = _unique_constraint_names(engine)
        finally:
            engine.dispose()

        assert "uq_photo_ranking_run_photo" in names
        assert "uq_photo_ranking_run_photo_category" not in names

    def test_after_the_upgrade_a_photo_may_not_appear_twice_in_one_run(
        self, tmp_path: Path
    ) -> None:
        """DER Beweis, dass der neue Constraint wirklich greift - ein reiner Namensvergleich
        bliebe gruen, wenn `create_unique_constraint` unter SQLite still nichts taete."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _apply(connection, _COLUMNS_REVISION, "upgrade")
                connection.execute(
                    text(
                        "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, "
                        "event_id, rank_score, rank_position) VALUES (1, 1, 1, 7, 0.9, 1)"
                    )
                )

            with pytest.raises(IntegrityError):
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "INSERT INTO photo_rankings (id, criterion_scoring_run_id, photo_id, "
                            "event_id, rank_score, rank_position) VALUES (2, 1, 1, 7, 0.1, 2)"
                        )
                    )
        finally:
            engine.dispose()

    def test_the_secondary_rows_of_a_photo_are_deleted(self, tmp_path: Path) -> None:
        """Sicherheitsauflage S17, erste Haelfte: ohne die Loeschung verletzte der
        wiederhergestellte Constraint die vorhandenen Daten und die Migration waere an einer
        echten Datenbank nicht ausfuehrbar. Es bleibt die HAUPTzeile - nicht irgendeine."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                # Die Nebenzeile traegt hier die NIEDRIGERE id: eine Loeschung, die schlicht die
                # erste Zeile je Paar behaelt, wuerde die falsche behalten.
                _insert_ranking(
                    connection, row_id=1, category_key="tier", is_primary=False, rank_position=2
                )
                _insert_ranking(
                    connection, row_id=2, category_key="menschen", is_primary=True, rank_position=1
                )
                _apply(connection, _COLUMNS_REVISION, "upgrade")

            with engine.connect() as connection:
                rows = connection.execute(text("SELECT id FROM photo_rankings")).all()
        finally:
            engine.dispose()

        assert rows == [(2,)]

    def test_two_primary_rows_of_one_photo_are_reduced_to_one(self, tmp_path: Path) -> None:
        """Sicherheitsauflage S17, die eigentliche Aussage: die Loeschung muss "hoechstens eine
        Zeile je (Lauf, Foto)" HERSTELLEN, nicht voraussetzen.

        `WHERE is_primary = false` allein setzte voraus, dass es je Lauf und Foto nie zwei
        Hauptzeilen gibt - eine Eigenschaft, die im Bestand nur der Schreibpfad und eine unter
        SQLite wirkungslose Sperre schuetzten. Traegt die echte Datenbank ein solches Paar, bricht
        der Constraint-Tausch mitten in der Migration ab."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _insert_ranking(
                    connection, row_id=1, category_key="menschen", is_primary=True, rank_position=1
                )
                _insert_ranking(
                    connection, row_id=2, category_key="tier", is_primary=True, rank_position=1
                )
                _apply(connection, _COLUMNS_REVISION, "upgrade")

            with engine.connect() as connection:
                rows = connection.execute(text("SELECT id FROM photo_rankings")).all()
        finally:
            engine.dispose()

        assert rows == [(1,)]

    def test_rows_of_different_photos_and_runs_survive(self, tmp_path: Path) -> None:
        """Die Gegenprobe zur Loeschung: sie raeumt je (Lauf, Foto) auf und nicht die Tabelle."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _insert_ranking(
                    connection, row_id=1, photo_id=1, category_key="menschen", is_primary=True
                )
                _insert_ranking(
                    connection, row_id=2, photo_id=2, category_key="tier", is_primary=True
                )
                _insert_ranking(
                    connection,
                    row_id=3,
                    run_id=2,
                    photo_id=1,
                    category_key="landschaft",
                    is_primary=True,
                )
                _apply(connection, _COLUMNS_REVISION, "upgrade")

            with engine.connect() as connection:
                rows = connection.execute(
                    text("SELECT id FROM photo_rankings ORDER BY id")
                ).all()
        finally:
            engine.dispose()

        assert rows == [(1,), (2,), (3,)]

    def test_the_rank_score_of_a_surviving_row_is_untouched(self, tmp_path: Path) -> None:
        """Die Migration loescht Zeilen; sie rechnet keine Raenge neu. Der naechste
        Kriterien-Lauf tut das."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _insert_ranking(
                    connection, row_id=1, category_key="menschen", is_primary=True, rank_position=4
                )
                _apply(connection, _COLUMNS_REVISION, "upgrade")

            with engine.connect() as connection:
                row = connection.execute(
                    text("SELECT rank_score, rank_position, event_id FROM photo_rankings")
                ).one()
        finally:
            engine.dispose()

        assert row == (0.9, 4, 7)


class TestTheColumnsDowngrade:
    """Sicherheitsauflage S18: der Rueckwaertsweg stellt STRUKTUR wieder her, nie Daten. Ohne
    einen Fall, der die LEERHEIT der wiederhergestellten Spalten zusichert, liest sich die
    unterlassene Rueckfuellung wie ein Versehen."""

    def test_the_three_columns_exist_again(self, tmp_path: Path) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _apply(connection, _COLUMNS_REVISION, "upgrade")
                _apply(connection, _COLUMNS_REVISION, "downgrade")

            ranking_columns = {c["name"] for c in inspect(engine).get_columns("photo_rankings")}
            score_columns = {c["name"] for c in inspect(engine).get_columns("photo_scores")}
            names = _unique_constraint_names(engine)
        finally:
            engine.dispose()

        assert "category_key" in ranking_columns
        assert "is_primary" in ranking_columns
        assert "category_override" in score_columns
        assert "uq_photo_ranking_run_photo_category" in names
        assert "uq_photo_ranking_run_photo" not in names

    def test_the_restored_columns_carry_no_category_data(self, tmp_path: Path) -> None:
        """DIE Aussage dieser Klasse: keine Kategorie kehrt zurueck. `category_key` steht leer,
        `category_override` steht auf NULL - die Datenbank ist strukturell gueltig und jedes Foto
        ist kategorielos."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _insert_ranking(
                    connection, row_id=1, category_key="menschen", is_primary=True
                )
                connection.execute(
                    text(
                        "INSERT INTO photo_scores (photo_id, sharpness, exposure, computed_at, "
                        "category_override) VALUES (1, 0.5, 0.5, '2026-09-12 10:00:00', 'tier')"
                    )
                )
                _apply(connection, _COLUMNS_REVISION, "upgrade")
                _apply(connection, _COLUMNS_REVISION, "downgrade")

            with engine.connect() as connection:
                ranking = connection.execute(
                    text("SELECT category_key, is_primary FROM photo_rankings")
                ).one()
                override = connection.execute(
                    text("SELECT category_override FROM photo_scores")
                ).one()
        finally:
            engine.dispose()

        assert ranking == ("", True)
        assert override == (None,)

    def test_no_temporary_server_default_survives_the_downgrade(self, tmp_path: Path) -> None:
        """Der Default hat genau eine Aufgabe - die NOT-NULL-Bedingung des Altbestands zu
        erfuellen - und darf sie nicht ueberleben. Bliebe er stehen, erzeugte ein Schreibpfad, der
        `is_primary` vergisst, im alten Schema still eine zweite Hauptkategorie."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _apply(connection, _COLUMNS_REVISION, "upgrade")
                _apply(connection, _COLUMNS_REVISION, "downgrade")

            columns = {c["name"]: c for c in inspect(engine).get_columns("photo_rankings")}
        finally:
            engine.dispose()

        assert columns["is_primary"]["default"] is None
        assert columns["category_key"]["default"] is None


class TestTheTableRevision:
    def test_the_upgrade_drops_the_classification_table(self, tmp_path: Path) -> None:
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                _apply(connection, _TABLE_REVISION, "upgrade")

            tables = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

        assert "photo_category_classifications" not in tables

    def test_the_upgrade_drops_the_table_even_with_rows_in_it(self, tmp_path: Path) -> None:
        """Der Datenverlust ist eine getroffene Entscheidung (Spec-Abschnitt "Entscheidungen"):
        die bereits bezahlten Kategoriekonfidenzen frueherer Cloud-Laeufe gehen dabei verloren.
        Die Migration haelt nicht an und sichert nichts weg."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                connection.execute(
                    text(
                        "INSERT INTO photo_category_classifications (photo_id, category_key, "
                        "detected_categories, provider, computed_at) VALUES "
                        "(1, 'menschen', '[\"menschen\"]', 'anthropic', '2026-09-12 10:00:00')"
                    )
                )
                _apply(connection, _TABLE_REVISION, "upgrade")

            tables = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

        assert "photo_category_classifications" not in tables

    def test_the_downgrade_recreates_the_table_empty(self, tmp_path: Path) -> None:
        """Sicherheitsauflage S18 fuer die zweite Revision: die Tabelle existiert wieder UND ist
        leer. Sie wird aus nichts rekonstruiert."""
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        try:
            with engine.begin() as connection:
                _create_pre_migration_schema(connection)
                connection.execute(
                    text(
                        "INSERT INTO photo_category_classifications (photo_id, category_key, "
                        "detected_categories, provider, computed_at) VALUES "
                        "(1, 'menschen', '[\"menschen\"]', 'anthropic', '2026-09-12 10:00:00')"
                    )
                )
                _apply(connection, _TABLE_REVISION, "upgrade")
                _apply(connection, _TABLE_REVISION, "downgrade")

            columns = {c["name"] for c in inspect(engine).get_columns("photo_category_classifications")}
            with engine.connect() as connection:
                count = connection.execute(
                    text("SELECT count(*) FROM photo_category_classifications")
                ).scalar_one()
        finally:
            engine.dispose()

        assert count == 0
        assert columns == {
            "photo_id",
            "category_key",
            "detected_categories",
            "detected_category_confidences",
            "category_confidence",
            "provider",
            "computed_at",
        }
