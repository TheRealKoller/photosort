"""Die Migration der Albumentscheidung: `status` wird nullable, `favorite` zieht daneben.

Anders als die Migration des Auswahlvorschlags ist diese hier NICHT datenlos: Sie konvertiert die
Bestandszeilen (`status='FAVORITE'` -> `favorite=true, status=NULL`), damit kein Lesepfad auf einen
Wert ausserhalb des neuen Vorrats trifft. Beide Richtungen brauchen deshalb Zeilen, an denen sie
brechen koennen.

DIE SPALTE TRAEGT DEN ENUM-NAMEN, NICHT SEINEN WERT - `'FAVORITE'`, nicht `'favorite'`.
`SQLEnum(RatingStatus, native_enum=False)` speichert ohne `values_callable` den `.name`, auch bei
einem `enum.StrEnum`, dessen `.value` kleingeschrieben ist. Der Testaufbau unten fuegt deshalb
GROSS geschriebene Werte ein; ein kleingeschriebener Aufbau laesst jede Konvertierung ins Leere
laufen und den Fall trotzdem gruen werden. Die Annahme wird nicht geglaubt, sondern in
`test_the_column_stores_the_enum_name_not_its_value` am lebenden Modell GEMESSEN - driftet das
Verhalten von SQLAlchemy oder die Spaltenkonfiguration, zeigt dieser Fall auf die Literale hier.

Der Rueckwaertsweg stellt die STRUKTUR wieder her, nie die Daten - er LOESCHT die Zeilen ohne
Albumentscheidung, weil das alte Schema sie nicht darstellen kann. Der Fall dazu heisst nach dem
Verlust, nicht nach der Struktur.
"""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Connection, create_engine, inspect, text

from photosort.db import Base
from photosort.models import Rating, RatingStatus

_MIGRATION_FILENAME = "f6a7b8c9d0e1_albumentscheidung.py"
_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent / "alembic" / "versions" / _MIGRATION_FILENAME
)


def _load_migration_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("albumentscheidung_migration", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_migration_schema(connection: Connection) -> None:
    """Minimaler Nachbau des Schema-Stands unmittelbar VOR dieser Migration - nur die beiden
    beruehrten Tabellen. `ratings.status` ist dort NOT NULL und traegt drei Werte."""
    connection.execute(
        text(
            "CREATE TABLE ratings ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "photo_id INTEGER NOT NULL, "
            "user_id INTEGER NOT NULL, "
            "status VARCHAR(20) NOT NULL, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, "
            "CONSTRAINT uq_rating_photo_user UNIQUE (photo_id, user_id))"
        )
    )
    connection.execute(
        text(
            "CREATE TABLE photo_scores ("
            "photo_id INTEGER NOT NULL PRIMARY KEY, "
            "sharpness FLOAT NOT NULL, "
            "exposure FLOAT NOT NULL, "
            "phash VARCHAR, "
            "duplicate_of INTEGER, "
            "cluster_key VARCHAR, "
            "suggested_status VARCHAR(20), "
            "computed_at DATETIME NOT NULL)"
        )
    )


def _insert_existing_rows(connection: Connection) -> None:
    """ALLE DREI Bestandswerte nebeneinander in EINEM Aufbau - getrennte Aufbauten bestuenden auch
    bei einer Konvertierung, die pauschal jede Zeile anfasst oder gar keine.

    GROSS geschrieben, weil die Spalte den Enum-NAMEN traegt (siehe Modul-Docstring). Die letzte
    Zeile traegt die Kleinschreibung: sie kann aus dem Anwendungscode nicht entstehen - jede
    Schreibstelle laeuft ueber das ORM -, aber die Konvertierung ist einmalig und nach dem Deploy
    nicht nachholbar, und ihr Fehlschlag ist eine 500 auf jeder Fotoliste. Der Fall haelt die
    Unempfindlichkeit gegen die Schreibweise fest, die die Migration deshalb bewusst mitbringt."""
    for rating_id, (photo_id, user_id, status_value) in enumerate(
        [(1, 1, "FAVORITE"), (2, 1, "ALBUM_WORTHY"), (3, 1, "REJECTED"), (1, 2, "favorite")],
        start=1,
    ):
        connection.execute(
            text(
                "INSERT INTO ratings (id, photo_id, user_id, status, updated_at) VALUES "
                f"({rating_id}, {photo_id}, {user_id}, '{status_value}', "
                "'2026-09-01 10:00:00')"
            )
        )


def _insert_existing_scores(connection: Connection) -> None:
    """`photo_scores.suggested_status` teilt sich die Enum-KLASSE mit `ratings.status` (Auflage
    S11) - eine Bestandszeile mit `'FAVORITE'` wuerfe nach dem Schrumpfen des Enums beim Lesen
    einen `LookupError`, also eine 500 auf jeder Fotoliste, die dieses Foto enthaelt."""
    for photo_id, suggested in ((1, "FAVORITE"), (2, "REJECTED"), (3, None)):
        value = "NULL" if suggested is None else f"'{suggested}'"
        connection.execute(
            text(
                "INSERT INTO photo_scores (photo_id, sharpness, exposure, suggested_status, "
                f"computed_at) VALUES ({photo_id}, 0.5, 0.5, {value}, '2026-09-01 10:00:00')"
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
    """`down_revision` gegen den zum Umsetzungszeitpunkt TATSAECHLICHEN Head."""
    module = _load_migration_module()

    assert module.down_revision == "e7f8a9b0c1d2"


def test_the_column_stores_the_enum_name_not_its_value(tmp_path: Path) -> None:
    """DIE ANNAHME, AUF DER JEDES LITERAL DIESER DATEI UND DER MIGRATION STEHT - gemessen statt
    geglaubt.

    `RatingStatus` ist ein `enum.StrEnum` mit kleingeschriebenen Werten; in der Spalte landet
    trotzdem der NAME. Wer das verwechselt, schreibt eine Migration, deren `WHERE` nie trifft: Sie
    laeuft fehlerfrei durch, konvertiert nichts, und der erste Lesepfad danach wirft einen
    `LookupError` - eine 500 auf jeder Fotoliste, die das Foto enthaelt. Genau dieser Fehler steht
    unbemerkt auch in `c1d2e3f4a5b6_criterion_scoring_pipeline.py`.

    Der Fall ist bewusst an `REJECTED` gehaengt und nicht an `FAVORITE`: Nur ein noch lebender
    Enum-Eintrag laesst sich am Modell messen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            Rating.__table__.insert().values(
                id=1, photo_id=1, user_id=1, status=RatingStatus.REJECTED, favorite=False
            )
        )
        stored = connection.execute(text("SELECT status FROM ratings")).scalar_one()

    assert stored == "REJECTED"
    assert stored != RatingStatus.REJECTED.value
    assert stored == RatingStatus.REJECTED.name


def test_upgrade_converts_all_three_existing_status_values_side_by_side(tmp_path: Path) -> None:
    """Der eine Fall mit allen drei Bestandswerten: `favorite` wandert in die Spalte und laesst
    `status` leer, die beiden Albumentscheidungen bleiben WORTGLEICH stehen und bekommen
    `favorite=false`."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_rows(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, status, favorite FROM ratings ORDER BY id")
        ).all()

    assert rows == [
        (1, None, 1),
        (2, "ALBUM_WORTHY", 0),
        (3, "REJECTED", 0),
        # Die kleingeschriebene Zeile aus `_insert_existing_rows` - ebenfalls konvertiert.
        (4, None, 1),
    ]


def test_after_the_upgrade_status_carries_nothing_outside_the_new_vocabulary(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_rows(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        values = {
            row[0] for row in connection.execute(text("SELECT DISTINCT status FROM ratings")).all()
        }

    assert values == {None, "ALBUM_WORTHY", "REJECTED"}


def test_upgrade_clears_a_photo_score_suggestion_outside_the_new_vocabulary(
    tmp_path: Path,
) -> None:
    """Auflage S11: `photo_scores.suggested_status` wird in DERSELBEN Migration mitgefuehrt.
    `'REJECTED'` bleibt unangetastet - konvertiert wird ausschliesslich der entfallene Wert."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _insert_existing_scores(connection)
        _apply(connection, "upgrade")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT photo_id, suggested_status FROM photo_scores ORDER BY photo_id")
        ).all()

    assert rows == [(1, None), (2, "REJECTED"), (3, None)]


def test_upgrade_makes_status_nullable_and_favorite_not_null(tmp_path: Path) -> None:
    """Erstes der beiden Artefakte fuer `favorite IS NOT NULL`: die Spalten der migrierten
    Tabelle."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        before = set(_columns(connection, "ratings"))
        _apply(connection, "upgrade")

        ratings = _columns(connection, "ratings")

    assert set(ratings) - before == {"favorite"}
    assert ratings["status"]["nullable"]
    assert not ratings["favorite"]["nullable"]


def test_upgrade_keeps_the_unique_constraint_across_the_table_rebuild(tmp_path: Path) -> None:
    """`batch_alter_table` baut die Tabelle unter SQLite NEU auf - ein dabei verlorener
    Unique-Constraint faellt sonst erst produktiv auf, als zweite Bewertungszeile desselben
    Nutzers zu demselben Foto."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")

        constraints = {
            constraint["name"]
            for constraint in inspect(connection).get_unique_constraints("ratings")
        }

    assert "uq_rating_photo_user" in constraints


def test_an_insert_without_favorite_stores_false_in_the_model_schema(tmp_path: Path) -> None:
    """Zweites der beiden Artefakte: das aus `Base.metadata` erzeugte Schema. Ein am Modell
    fehlender `server_default` wuerde von der Migration gar nicht erfasst und faellt nur hier auf -
    beide muessen dieselbe DDL lesen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO ratings (id, photo_id, user_id, status) VALUES (1, 1, 1, 'REJECTED')")
        )

    with engine.connect() as connection:
        assert connection.execute(text("SELECT favorite FROM ratings")).scalar_one() == 0


def test_the_model_schema_allows_a_row_without_an_album_decision(tmp_path: Path) -> None:
    """`status IS NULL` heisst "keine Albumentscheidung" und muss am MODELL erlaubt sein, nicht
    nur an der migrierten Tabelle."""
    engine = create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO ratings (id, photo_id, user_id, status, favorite) "
                "VALUES (1, 1, 1, NULL, 1)"
            )
        )

    with engine.connect() as connection:
        assert connection.execute(text("SELECT status FROM ratings")).scalar_one() is None


def test_the_downgrade_deletes_every_row_without_an_album_decision(tmp_path: Path) -> None:
    """DER DATENVERLUST, nach dem dieser Fall heisst: Eine reine Favoritenzeile wird auf dem
    Rueckweg zu `status='FAVORITE'` und bleibt; eine Zeile, die nach dem Rueckweg WEDER
    Albumentscheidung NOCH Kennzeichen traegt, kann das alte Schema nicht darstellen und wird
    GELOESCHT. Ohne diese Loeschung scheiterte der `NOT NULL`-Aufbau mitten im Rueckwaertsweg.

    Die Schreibweise ist hier mitgeprueft und keine Nebensache: Der Rueckweg schreibt einen Wert,
    den das WIEDERHERGESTELLTE alte Enum lesen koennen muss - ein `'favorite'` waere dort genauso
    unbekannt wie ein `'FAVORITE'` im neuen."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.begin() as connection:
        _create_pre_migration_schema(connection)
        _apply(connection, "upgrade")
        for rating_id, (photo_id, status_value, favorite) in enumerate(
            [
                (1, None, 1),  # reiner Favorit -> wird wieder 'FAVORITE'
                (2, "ALBUM_WORTHY", 1),  # beides -> behaelt die Albumentscheidung
                (3, "REJECTED", 0),  # unveraendert
                (4, None, 0),  # verbotene Zeile -> wird geloescht
            ],
            start=1,
        ):
            status_sql = "NULL" if status_value is None else f"'{status_value}'"
            connection.execute(
                text(
                    "INSERT INTO ratings (id, photo_id, user_id, status, favorite, updated_at) "
                    f"VALUES ({rating_id}, {photo_id}, 1, {status_sql}, {favorite}, "
                    "'2026-09-01 10:00:00')"
                )
            )
        _apply(connection, "downgrade")

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT id, status FROM ratings ORDER BY id")).all()
        columns = _columns(connection, "ratings")

    assert rows == [(1, "FAVORITE"), (2, "ALBUM_WORTHY"), (3, "REJECTED")]
    assert "favorite" not in columns
    assert not columns["status"]["nullable"]


def test_the_downgrade_docstring_names_the_data_loss() -> None:
    """Die Zusage aus Auflage S12 steht am Artefakt selbst, nicht nur in der Spec: Wer den
    Rueckwaertsweg aufruft, liest dort, was er verliert."""
    module = _load_migration_module()
    docstrings = f"{module.__doc__ or ''}\n{module.downgrade.__doc__ or ''}".lower()

    assert "verlust" in docstrings or "verliert" in docstrings
    assert "geloescht" in docstrings or "loescht" in docstrings
