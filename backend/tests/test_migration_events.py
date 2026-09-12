from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

# Die einzige Migration dieses Projekts, die DATEN LOESCHT: `photo_rankings` wird vollstaendig
# geleert. Altlaeufe bekommen keine Events - die Kuratierung zeigt fuer sie nichts, bis sie neu
# berechnet werden. Genau deshalb ist `event_id` NOT NULL und es gibt keinen Ausnahmezweig im
# Lesepfad.
#
# Die Lauf-Zeilen (`criterion_scoring_runs`) bleiben unangetastet: sie tragen die Ist-Kosten der
# Cloud-Aufrufe, und die sind nicht wiederherstellbar. Rangzeilen sind es (erneuter Lauf, lokale
# Rechenzeit, kein Geld).

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / "f5a6b7c8d9e0_events.py"
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("events_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die beiden
    beruehrten Tabellen."""
    connection.execute(
        text(
            "CREATE TABLE criterion_scoring_runs ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "project_id INTEGER NOT NULL, "
            "scoring_run_id INTEGER NOT NULL, "
            "status VARCHAR(20) NOT NULL, "
            "estimated_cost_usd FLOAT)"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE photo_rankings ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "criterion_scoring_run_id INTEGER NOT NULL, "
            "photo_id INTEGER NOT NULL, "
            "cluster_key VARCHAR NOT NULL, "
            "category_key VARCHAR NOT NULL, "
            "rank_score FLOAT NOT NULL, "
            "rank_position INTEGER NOT NULL, "
            "is_primary BOOLEAN NOT NULL, "
            "CONSTRAINT uq_photo_ranking_run_photo_category "
            "UNIQUE (criterion_scoring_run_id, photo_id, category_key))"
        )
    )


def _insert_legacy_run(connection: Connection, *, run_id: int, ranking_rows: int) -> None:
    connection.execute(
        text(
            "INSERT INTO criterion_scoring_runs "
            "(id, project_id, scoring_run_id, status, estimated_cost_usd) VALUES "
            f"({run_id}, 1, 1, 'success', 1.25)"
        )
    )
    for index in range(ranking_rows):
        connection.execute(
            text(
                "INSERT INTO photo_rankings (criterion_scoring_run_id, photo_id, cluster_key, "
                "category_key, rank_score, rank_position, is_primary) VALUES "
                f"({run_id}, {index + 1}, 'cluster-0', 'landschaft', 0.9, {index + 1}, 1)"
            )
        )


def _apply(connection: Connection, direction: str) -> None:
    module = _load_migration_module()
    context = MigrationContext.configure(connection)
    with Operations.context(context):
        getattr(module, direction)()


def test_revision_chains_onto_the_current_head() -> None:
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head."""
    module = _load_migration_module()

    assert module.down_revision == "d1e2f3a4b5c6"


def test_upgrade_creates_the_events_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        inspector = inspect(connection)
        assert "events" in inspector.get_table_names()
        columns = {column["name"]: column for column in inspector.get_columns("events")}

    assert set(columns) == {
        "id",
        "criterion_scoring_run_id",
        "position",
        "started_at",
        "ended_at",
        "landmark_name",
        "place_kind",
        "place_lat",
        "place_lon",
    }
    for required in ("criterion_scoring_run_id", "position", "started_at", "ended_at"):
        assert not columns[required]["nullable"], required
    for optional in ("landmark_name", "place_kind", "place_lat", "place_lon"):
        assert columns[optional]["nullable"], optional


def test_upgrade_binds_events_to_their_run_with_a_real_foreign_key(tmp_path: Path) -> None:
    """Eine bloss LOGISCHE Spalte fiele still aus der Erreichbarkeitspruefung der Projektloeschung
    heraus, und unter Postgres entstuenden verwaiste Zeilen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        foreign_keys = inspect(connection).get_foreign_keys("events")

    assert [(fk["referred_table"], fk["constrained_columns"]) for fk in foreign_keys] == [
        ("criterion_scoring_runs", ["criterion_scoring_run_id"])
    ]


def test_upgrade_keeps_position_unique_per_run(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        constraints = inspect(connection).get_unique_constraints("events")

    assert [c["column_names"] for c in constraints] == [["criterion_scoring_run_id", "position"]]


def test_upgrade_replaces_cluster_key_with_a_not_null_event_id(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        columns = {c["name"]: c for c in inspect(connection).get_columns("photo_rankings")}

    assert "cluster_key" not in columns
    assert "event_id" in columns
    assert not columns["event_id"]["nullable"]


def test_upgrade_deletes_every_ranking_row_of_the_old_runs(tmp_path: Path) -> None:
    """Daniels Entscheidung: Altlaeufe werden ENTWERTET, nicht nachgezogen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_run(connection, run_id=1, ranking_rows=3)
        _insert_legacy_run(connection, run_id=2, ranking_rows=2)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        remaining = connection.execute(text("SELECT COUNT(*) FROM photo_rankings")).scalar_one()

    assert remaining == 0


def test_upgrade_leaves_the_run_rows_untouched(tmp_path: Path) -> None:
    """Die Lauf-Zeilen tragen die nicht wiederherstellbaren Ist-Kosten der Cloud-Aufrufe."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_run(connection, run_id=1, ranking_rows=3)
        _insert_legacy_run(connection, run_id=2, ranking_rows=2)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, estimated_cost_usd FROM criterion_scoring_runs ORDER BY id")
        ).all()

    assert rows == [(1, 1.25), (2, 1.25)]


def test_upgrade_creates_no_events_for_the_old_runs(tmp_path: Path) -> None:
    """KEIN Nachziehen bestehender Gruppen und KEINE Namen aus `photo_landmark_detections`."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_run(connection, run_id=1, ranking_rows=3)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM events")).scalar_one() == 0


def test_upgrade_leaves_no_orphaned_ranking_row(tmp_path: Path) -> None:
    """Die eigentliche Zusage hinter der Loeschung: keine Rangzeile ohne ihr Event."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_run(connection, run_id=1, ranking_rows=3)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        orphans = connection.execute(
            text(
                "SELECT COUNT(*) FROM photo_rankings r "
                "LEFT JOIN events e ON e.id = r.event_id WHERE e.id IS NULL"
            )
        ).scalar_one()

    assert orphans == 0


def test_downgrade_restores_the_old_column_shape(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        inspector = inspect(connection)
        columns = {c["name"] for c in inspector.get_columns("photo_rankings")}
        assert "events" not in inspector.get_table_names()

    assert "cluster_key" in columns
    assert "event_id" not in columns


def test_downgrade_does_not_bring_the_deleted_rows_back(tmp_path: Path) -> None:
    """FESTGESCHRIEBENES Verhalten, kein Versehen: die Loeschung ist nicht rueckholbar. Der
    Rueckwaertsweg stellt die SPALTENFORM wieder her, nicht die Daten."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_run(connection, run_id=1, ranking_rows=3)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM photo_rankings")).scalar_one() == 0
        assert (
            connection.execute(text("SELECT COUNT(*) FROM criterion_scoring_runs")).scalar_one()
            == 1
        )


def test_the_module_documents_the_irreversible_deletion() -> None:
    """Die Nicht-Rueckholbarkeit steht im Migrationsmodul selbst - sie ist die einzige ihrer Art
    im Projekt und darf niemanden im Betrieb ueberraschen."""
    source = _MIGRATION_PATH.read_text(encoding="utf-8")

    assert "downgrade" in source
    assert "photo_rankings" in source
    assert any(
        marker in source.lower() for marker in ("nicht zurueck", "nicht wiederher", "unumkehrbar")
    )
