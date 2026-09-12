"""specs/features/0426-zeitversatz-je-kamera.md, Umsetzungsschritt 1 - Muster
`test_migration_events.py`.

Drei Stellen, an denen das bestehende Migrations-Muster nicht reicht und dieser Satz deshalb
mehr tut als die Spaltenform zu pruefen:

* Die Bestandszeilen im nachgebauten Vor-Schema tragen JE EINEN EIGENEN `taken_at`-Wert. Mit
  gleichen Werten bestuende eine Migration, die eine Konstante eintraegt, jeden Test.
* Der `server_default` von `camera_probed` ist ZWEI Artefakte (Migration und Modell) und braucht
  zwei Assertions - die Migrationsseite steht im Postgres-Renderpfad
  (`test_postgres_ddl_compatibility.py`), die Modellseite in `test_models.py`.
* `fk_photos_camera_id` ist nur im Postgres-Render sichtbar; ohne den expliziten Namen ist der
  `downgrade` nicht ausfuehrbar.
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
    / "a6b7c8d9e0f1_kamera_zeitversatz.py"
)

# Zwei Bestandszeilen mit VERSCHIEDENEN Zeitstempeln - siehe Modul-Docstring.
_EXISTING_PHOTOS = (
    (1, "2026-07-20 10:00:00"),
    (2, "2026-08-01 18:45:12"),
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("kamera_zeitversatz_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die beiden
    beruehrten Tabellen."""
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
            "CREATE TABLE photos ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "project_id INTEGER NOT NULL, "
            "relative_path VARCHAR NOT NULL, "
            "etag VARCHAR NOT NULL, "
            "content_length INTEGER NOT NULL, "
            "taken_at DATETIME NOT NULL, "
            "gps_lat FLOAT, "
            "gps_lon FLOAT, "
            "last_modified DATETIME NOT NULL, "
            "CONSTRAINT uq_photo_project_path UNIQUE (project_id, relative_path))"
        )
    )


def _insert_legacy_photos(connection: Connection) -> None:
    connection.execute(
        text(
            "INSERT INTO projects (id, name, opencloud_drive_id, opencloud_path) "
            "VALUES (1, 'Costa Rica', 'drive-1', '/CostaRica')"
        )
    )
    for photo_id, taken_at in _EXISTING_PHOTOS:
        connection.execute(
            text(
                "INSERT INTO photos (id, project_id, relative_path, etag, content_length, "
                "taken_at, last_modified) VALUES "
                f"({photo_id}, 1, 'img{photo_id}.jpg', 'etag-{photo_id}', 100, "
                f"'{taken_at}', '{taken_at}')"
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

    assert module.down_revision == "f5a6b7c8d9e0"


def test_upgrade_creates_the_project_cameras_table(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        inspector = inspect(connection)
        assert "project_cameras" in inspector.get_table_names()
        columns = {column["name"]: column for column in inspector.get_columns("project_cameras")}

    assert set(columns) == {"id", "project_id", "make", "model", "offset_minutes"}
    for required in ("project_id", "make", "model", "offset_minutes"):
        assert not columns[required]["nullable"], required


def test_upgrade_binds_a_camera_to_its_project_with_a_real_foreign_key(tmp_path: Path) -> None:
    """Eine bloss LOGISCHE Spalte fiele still aus der Erreichbarkeitspruefung der Projektloeschung
    heraus, und unter Postgres entstuenden verwaiste Zeilen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        foreign_keys = inspect(connection).get_foreign_keys("project_cameras")

    assert [(fk["referred_table"], fk["constrained_columns"]) for fk in foreign_keys] == [
        ("projects", ["project_id"])
    ]


def test_upgrade_keeps_make_and_model_unique_per_project(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        constraints = inspect(connection).get_unique_constraints("project_cameras")

    assert [c["column_names"] for c in constraints] == [["project_id", "make", "model"]]


def test_upgrade_adds_the_three_photo_columns(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        columns = {c["name"]: c for c in inspect(connection).get_columns("photos")}

    assert not columns["taken_at_original"]["nullable"]
    assert columns["camera_id"]["nullable"]
    assert not columns["camera_probed"]["nullable"]


def test_upgrade_binds_a_photo_to_its_camera_with_a_real_foreign_key(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        foreign_keys = inspect(connection).get_foreign_keys("photos")

    assert ("project_cameras", ["camera_id"]) in [
        (fk["referred_table"], fk["constrained_columns"]) for fk in foreign_keys
    ]


def test_upgrade_copies_every_existing_row_from_its_own_taken_at(tmp_path: Path) -> None:
    """DER tragende Datenfall: je Zeile IHR EIGENER Wert, nicht eine tabellenweite Konstante.
    Die Kopie entsteht zu einem Zeitpunkt, an dem es noch keinen Versatz gibt - sie ist damit
    beweisbar der aufgezeichnete Wert."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_photos(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, taken_at, taken_at_original FROM photos ORDER BY id")
        ).all()

    assert [(row[0], row[1]) for row in rows] == list(_EXISTING_PHOTOS)
    for _photo_id, taken_at, taken_at_original in rows:
        assert taken_at_original == taken_at


def test_upgrade_marks_existing_rows_as_not_yet_probed(tmp_path: Path) -> None:
    """`false` fuer den Bestand - genau diese Zeilen holt der naechste Scan nach."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_photos(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        probed = connection.execute(text("SELECT camera_probed FROM photos ORDER BY id")).all()

    assert [row[0] for row in probed] == [0, 0]


def test_upgrade_leaves_the_camera_of_existing_rows_unset(tmp_path: Path) -> None:
    """KEIN Backfill der Kamera - dafuer gaebe es in der Migration kein EXIF."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_photos(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT COUNT(*) FROM photos WHERE camera_id IS NOT NULL")
            ).scalar_one()
            == 0
        )
        assert connection.execute(text("SELECT COUNT(*) FROM project_cameras")).scalar_one() == 0


def test_an_insert_without_the_probed_column_succeeds(tmp_path: Path) -> None:
    """Der `server_default` wirkt auch fuer NEUE Zeilen - ein Schreibpfad, der die Spalte nicht
    nennt, bricht nicht."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_photos(connection)
        _apply(connection, "upgrade")
        connection.execute(
            text(
                "INSERT INTO photos (id, project_id, relative_path, etag, content_length, "
                "taken_at, taken_at_original, last_modified) VALUES "
                "(3, 1, 'img3.jpg', 'etag-3', 100, "
                "'2026-08-02 09:00:00', '2026-08-02 09:00:00', '2026-08-02 09:00:00')"
            )
        )

    with engine.connect() as connection:
        probed = connection.execute(
            text("SELECT camera_probed FROM photos WHERE id = 3")
        ).scalar_one()

    assert probed == 0


def test_an_insert_without_the_offset_column_succeeds(tmp_path: Path) -> None:
    """Eine neu auftauchende Kamera beginnt bei `0` - der Default liegt in der DDL, nicht nur im
    Modell."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_photos(connection)
        _apply(connection, "upgrade")
        connection.execute(
            text(
                "INSERT INTO project_cameras (id, project_id, make, model) "
                "VALUES (1, 1, 'Canon', 'EOS 5D')"
            )
        )

    with engine.connect() as connection:
        offset = connection.execute(
            text("SELECT offset_minutes FROM project_cameras WHERE id = 1")
        ).scalar_one()

    assert offset == 0


def test_downgrade_writes_the_recorded_times_back_into_taken_at(tmp_path: Path) -> None:
    """DIE Zusage des Rueckwegs: `taken_at_original` ist die einzige Kopie der aufgezeichneten
    Zeit. Ohne das Zurueckschreiben behielte die Datenbank die KORRIGIERTEN Zeiten, und die
    aufgezeichneten waeren unwiederbringlich fort."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_photos(connection)
        _apply(connection, "upgrade")
        # Ein gesetzter Versatz, wie ihn der Endpunkt schreibt: `taken_at` traegt ab jetzt die
        # KORRIGIERTE Zeit, `taken_at_original` unveraendert die aufgezeichnete.
        connection.execute(
            text(
                "INSERT INTO project_cameras (id, project_id, make, model, offset_minutes) "
                "VALUES (1, 1, 'Canon', 'EOS 5D', -120)"
            )
        )
        connection.execute(
            text(
                "UPDATE photos SET camera_id = 1, camera_probed = 1, "
                "taken_at = datetime(taken_at_original, '-120 minutes')"
            )
        )
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT id, taken_at FROM photos ORDER BY id")).all()

    assert [(row[0], row[1]) for row in rows] == list(_EXISTING_PHOTOS)


def test_downgrade_restores_the_old_column_shape(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_photos(connection)
        _apply(connection, "upgrade")
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        inspector = inspect(connection)
        columns = {c["name"] for c in inspector.get_columns("photos")}
        assert "project_cameras" not in inspector.get_table_names()

    assert "taken_at_original" not in columns
    assert "camera_id" not in columns
    assert "camera_probed" not in columns
    assert "taken_at" in columns


def test_downgrade_does_not_bring_the_offsets_back(tmp_path: Path) -> None:
    """FESTGESCHRIEBENES Verhalten, kein Versehen: der Rueckweg stellt die rohen Zeiten und die
    Spaltenform wieder her, nicht die Einstellungen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_legacy_photos(connection)
        _apply(connection, "upgrade")
        connection.execute(
            text(
                "INSERT INTO project_cameras (id, project_id, make, model, offset_minutes) "
                "VALUES (1, 1, 'Canon', 'EOS 5D', -120)"
            )
        )
        _apply(connection, "downgrade")
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM project_cameras")).scalar_one() == 0


def test_the_module_documents_the_irreversible_loss_of_the_offsets() -> None:
    """Die Nicht-Rueckholbarkeit steht im Migrationsmodul selbst - sie darf niemanden im Betrieb
    ueberraschen."""
    source = _MIGRATION_PATH.read_text(encoding="utf-8")

    assert "downgrade" in source
    assert "taken_at_original" in source
    assert any(
        marker in source.lower() for marker in ("nicht zurueck", "nicht wiederher", "unumkehrbar")
    )
