from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.dialects import postgresql

# specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, Review-Fund an der eigenen
# Migration: Alle Migrationstests dieses Projekts laufen gegen SQLite (Testkonzept) - dort ist
# BOOLEAN kein eigener Typ, sondern INTEGER. Ein `server_default=sa.text("0")` auf einer
# Boolean-Spalte laeuft in SQLite deshalb anstandslos durch und bricht auf Postgres mit
#
#     DatatypeMismatch: column "..." is of type boolean but default expression is of type integer
#
# ab. Genau das ist passiert: der Backend-Container fuehrt `alembic upgrade head` VOR dem
# Serverstart aus (docker-compose.yml), der Container wurde dadurch nie gesund, und der
# CI-Job `docker-compose-check` fiel um - waehrend die vollstaendige SQLite-Testsuite gruen war.
#
# Diese Datei schliesst die Luecke fuer die Klasse von Fehlern, die SQLite strukturell nicht sehen
# kann, ohne dafuer eine echte Postgres-Instanz in die Testsuite zu holen: die Migration wird gegen
# einen Postgres-Dialekt im "mock mode" (`create_mock_engine`) ausgefuehrt, der das DDL erzeugt,
# ohne es auszufuehren. Geprueft wird das erzeugte SQL.
#
# Bewusste Abgrenzung: das ersetzt KEINEN echten Postgres-Lauf (Semantik, Sperrverhalten und
# Datenmigrationen bleiben ungeprueft - der Eintrag "Migrationsverhalten gegen echtes Postgres"
# unter "Bekannte Luecken" im Testkonzept bleibt bestehen). Es faengt genau die Dialekt-
# Renderfehler ab, die eine SQLite-basierte Testsuite prinzipbedingt durchlaesst.

_VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"


def _load(revision_filename: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"pg_ddl_{revision_filename}", _VERSIONS_DIR / revision_filename
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _render_postgres_ddl(revision_filename: str, direction: str = "upgrade") -> list[str]:
    """Fuehrt eine Migration gegen einen Postgres-Dialekt aus, der das DDL nur SAMMELT statt es
    auszufuehren (`create_mock_engine`) - kein Server, keine Verbindung, kein Schema-Zustand.

    Bewusst OHNE `as_sql=True` (den "offline mode" von `alembic upgrade --sql`): der schreibt das
    DDL in einen eigenen Ausgabepuffer statt es der Verbindung zu uebergeben, die Anweisungen
    kaemen hier also gar nicht an. Ueber die Mock-Verbindung laeuft jede Anweisung durch
    `_collect`. Reicht fuer reine Schema-Operationen wie diese; eine Migration mit Datenschritten
    (`SELECT`-abhaengige Logik) liesse sich so nicht rendern."""
    statements: list[str] = []
    dialect = postgresql.dialect()

    def _collect(sql: object, *args: object, **kwargs: object) -> None:
        statements.append(str(sql.compile(dialect=dialect)))  # type: ignore[attr-defined]

    mock_engine = sa.create_mock_engine("postgresql+psycopg://", _collect)

    module = _load(revision_filename)
    context = MigrationContext.configure(
        connection=mock_engine,  # type: ignore[arg-type]
        opts={"dialect": dialect},
    )
    with Operations.context(context):
        getattr(module, direction)()
    return statements


@pytest.fixture(scope="module")
def classification_run_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl("e2f3a4b5c6d7_classification_run_cloud_phase.py")


def test_boolean_column_default_is_rendered_as_a_boolean_literal(
    classification_run_upgrade_ddl: list[str],
) -> None:
    """DER Regressionstest zum Review-Fund: `DEFAULT 0` auf einer BOOLEAN-Spalte laeuft in SQLite
    durch und bricht Postgres. Erwartet wird ein Boolean-Literal (`false`), nicht `0`."""
    add_column = [
        statement for statement in classification_run_upgrade_ddl if "cloud_requested" in statement
    ]
    assert add_column, "kein ADD COLUMN fuer cloud_requested im gerenderten DDL gefunden"
    statement = add_column[0]

    assert "BOOLEAN" in statement.upper()
    assert "DEFAULT false" in statement
    # Die eigentliche Aussage: kein Integer-Literal als Boolean-Default.
    assert "DEFAULT 0" not in statement


def test_the_upgrade_renders_all_three_columns_for_postgres(
    classification_run_upgrade_ddl: list[str],
) -> None:
    rendered = " ".join(classification_run_upgrade_ddl)

    assert "phase" in rendered
    assert "cloud_requested" in rendered
    assert "cloud_error_message" in rendered


def test_the_downgrade_renders_for_postgres_too() -> None:
    """Ein `downgrade()`, das nur gegen SQLite gerendert wurde, kann denselben Dialektfehler
    tragen - hier ebenfalls einmal durch den Postgres-Dialekt geschickt."""
    statements = _render_postgres_ddl(
        "e2f3a4b5c6d7_classification_run_cloud_phase.py", direction="downgrade"
    )

    rendered = " ".join(statements)
    assert "DROP COLUMN" in rendered.upper()
    assert "cloud_error_message" in rendered
    assert "cloud_requested" in rendered
    assert "phase" in rendered


# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md Punkt 3: acht additive Kostenspalten. Auch hier kann SQLite die entscheidende Aussage
# strukturell nicht pruefen - es kennt keinen Unterschied zwischen INTEGER und DOUBLE PRECISION
# und wuerde einen unbeabsichtigten Server-Default klaglos akzeptieren.

_REMOTE_COST_REVISION = "f4a5b6c7d8e9_remote_cost_tracking.py"

_EXPECTED_INTEGER_COLUMNS = (
    "landmark_api_calls",
    "landmark_input_tokens",
    "landmark_output_tokens",
    "api_calls",
    "input_tokens",
    "output_tokens",
)
_EXPECTED_FLOAT_COLUMNS = ("landmark_cost_usd", "cost_usd")


@pytest.fixture(scope="module")
def remote_cost_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_REMOTE_COST_REVISION)


def _add_column_statement(ddl: list[str], column: str) -> str:
    matches = [
        statement
        for statement in ddl
        if "ADD COLUMN" in statement.upper() and f" {column} " in statement
    ]
    assert matches, f"kein ADD COLUMN fuer {column} im gerenderten DDL gefunden"
    assert len(matches) == 1, f"mehrdeutiges ADD COLUMN fuer {column}: {matches}"
    return matches[0]


def test_all_eight_cost_columns_are_added_for_postgres(
    remote_cost_upgrade_ddl: list[str],
) -> None:
    for column in _EXPECTED_INTEGER_COLUMNS + _EXPECTED_FLOAT_COLUMNS:
        _add_column_statement(remote_cost_upgrade_ddl, column)


def test_counter_columns_render_as_integer(remote_cost_upgrade_ddl: list[str]) -> None:
    for column in _EXPECTED_INTEGER_COLUMNS:
        assert "INTEGER" in _add_column_statement(remote_cost_upgrade_ddl, column).upper(), column


def test_amount_columns_render_as_double_precision(remote_cost_upgrade_ddl: list[str]) -> None:
    """`sa.Float()` rendert auf Postgres als `FLOAT` ohne Praezisionsangabe - laut PostgreSQL-
    Dokumentation gleichbedeutend mit DOUBLE PRECISION. Bewusst `sa.Float()` und nicht
    `sa.Double()`: es ist derselbe Typ, den alle uebrigen `Mapped[float]`-Spalten des Datenmodells
    erzeugen (rank_score, sharpness, confidence, ...), also kein Sondertyp fuer die Betraege.
    Entscheidend ist, dass es KEIN ganzzahliger Typ ist - ein Cent-Betrag wuerde sonst still auf
    0 gerundet, und SQLite koennte den Unterschied nicht sichtbar machen."""
    for column in _EXPECTED_FLOAT_COLUMNS:
        statement = _add_column_statement(remote_cost_upgrade_ddl, column).upper()
        assert "DOUBLE PRECISION" in statement or "FLOAT" in statement, column
        assert "INTEGER" not in statement, column


def test_no_cost_column_gets_a_server_default(remote_cost_upgrade_ddl: list[str]) -> None:
    """DIE eigentliche Aussage dieser Datei fuer diese Revision: der Python-seitige Modell-Default
    `0` darf NICHT zum Server-Default werden. Sonst bekaemen die Bestandszeilen `0` statt `NULL`,
    und "nicht erfasst" waere dauerhaft nicht mehr von "kostenlos" unterscheidbar (ADR 0051
    Punkt 3/5) - ein Fehler, den SQLite nicht sichtbar machen wuerde."""
    for column in _EXPECTED_INTEGER_COLUMNS + _EXPECTED_FLOAT_COLUMNS:
        statement = _add_column_statement(remote_cost_upgrade_ddl, column)
        assert "DEFAULT" not in statement.upper(), column


def test_the_remote_cost_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_REMOTE_COST_REVISION, direction="downgrade")

    rendered = " ".join(statements).upper()
    assert rendered.count("DROP COLUMN") == 8


# specs/features/0299-kategorie-konfidenz-anzeigen.md, ADR 0067 Punkt 3/4: zwei additive
# Konfidenzspalten. SQLite kann die entscheidende Aussage auch hier strukturell nicht pruefen - es
# kennt weder einen eigenen JSON-Typ noch den Unterschied zwischen INTEGER und DOUBLE PRECISION und
# wuerde einen unbeabsichtigten Server-Default klaglos akzeptieren. Genau der waere hier fatal:
# ein `DEFAULT 0` auf `category_confidence` gaebe jeder Bestandszeile die Aussage "das Modell war
# sich zu 0 % sicher" (Akzeptanzkriterium 9).

_CONFIDENCE_REVISION = "a3b4c5d6e7f8_kategorie_konfidenz.py"


@pytest.fixture(scope="module")
def confidence_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_CONFIDENCE_REVISION)


def test_both_confidence_columns_are_added_for_postgres(
    confidence_upgrade_ddl: list[str],
) -> None:
    for column in ("detected_category_confidences", "category_confidence"):
        _add_column_statement(confidence_upgrade_ddl, column)


def test_the_scalar_confidence_renders_as_a_floating_point_type(
    confidence_upgrade_ddl: list[str],
) -> None:
    """`sa.Float()` rendert auf Postgres als `FLOAT` (laut PostgreSQL-Dokumentation
    gleichbedeutend mit DOUBLE PRECISION) - entscheidend ist, dass es KEIN ganzzahliger Typ ist:
    eine Konfidenz von 0.92 wuerde sonst still auf 0 oder 1 gerundet, und SQLite koennte den
    Unterschied nicht sichtbar machen."""
    statement = _add_column_statement(confidence_upgrade_ddl, "category_confidence").upper()

    assert "DOUBLE PRECISION" in statement or "FLOAT" in statement
    assert "INTEGER" not in statement


def test_the_confidence_mapping_renders_as_json(confidence_upgrade_ddl: list[str]) -> None:
    statement = _add_column_statement(
        confidence_upgrade_ddl, "detected_category_confidences"
    ).upper()

    assert "JSON" in statement


def test_neither_confidence_column_gets_a_server_default(
    confidence_upgrade_ddl: list[str],
) -> None:
    """DIE eigentliche Aussage dieser Datei fuer diese Revision (Akzeptanzkriterium 9): kein
    Server-Default. Sonst bekaemen Bestandszeilen `0`/`{}` statt `NULL`, und "nicht erhoben" waere
    dauerhaft nicht mehr von "das Modell war sich zu 0 % sicher" zu unterscheiden."""
    for column in ("detected_category_confidences", "category_confidence"):
        statement = _add_column_statement(confidence_upgrade_ddl, column)
        assert "DEFAULT" not in statement.upper(), column


def test_the_confidence_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_CONFIDENCE_REVISION, direction="downgrade")

    rendered = " ".join(statements).upper()
    assert rendered.count("DROP COLUMN") == 2


# specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-vier-
# teilschritte-und-laufeigene-cloud-bilanz.md Punkt 2/3/5: fuenf additive Spalten plus ein
# FREMDSCHLUESSEL auf criterion_scoring_runs, eine Spalte auf remote_category_classification_runs.
#
# Neu gegenueber allen bisherigen Revisionen dieser Datei: der Fremdschluessel. Unter SQLite
# entsteht er ausschliesslich ueber den Tabellen-Neuaufbau von `batch_alter_table` und ist dort
# von einer reinen Spaltenpruefung nicht zu unterscheiden; unter Postgres ist er ein eigenes
# `ALTER TABLE ... ADD CONSTRAINT`. Nur der Postgres-Renderpfad zeigt, ob der Constraint seinen
# EXPLIZITEN NAMEN traegt - und ohne ihn ist der Rueckwaertsweg der Migration nicht ausfuehrbar.

_TRANSPARENCY_REVISION = "b8c9d0e1f2a3_classification_run_transparency.py"

_EXPECTED_TRANSPARENCY_INTEGER_COLUMNS = (
    "landmark_photos_total",
    "landmark_photos_processed",
    "landmark_failed_calls",
    "remote_category_classification_run_id",
    "failed_calls",
)
_EXPECTED_TRANSPARENCY_FLOAT_COLUMNS = ("estimated_cost_usd",)
_EXPECTED_FK_NAME = "fk_criterion_scoring_runs_remote_category_classification_run_id"


@pytest.fixture(scope="module")
def transparency_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_TRANSPARENCY_REVISION)


def test_all_six_transparency_columns_are_added_for_postgres(
    transparency_upgrade_ddl: list[str],
) -> None:
    for column in _EXPECTED_TRANSPARENCY_INTEGER_COLUMNS + _EXPECTED_TRANSPARENCY_FLOAT_COLUMNS:
        _add_column_statement(transparency_upgrade_ddl, column)


def test_the_live_counters_render_as_integer(transparency_upgrade_ddl: list[str]) -> None:
    for column in _EXPECTED_TRANSPARENCY_INTEGER_COLUMNS:
        assert "INTEGER" in _add_column_statement(transparency_upgrade_ddl, column).upper(), column


def test_the_frozen_estimate_renders_as_a_floating_point_type(
    transparency_upgrade_ddl: list[str],
) -> None:
    """Wie bei den Ist-Betraegen: entscheidend ist, dass es KEIN ganzzahliger Typ ist - eine
    Schaetzung im Zehntelcent-Bereich wuerde sonst still auf 0 gerundet, und SQLite koennte den
    Unterschied nicht sichtbar machen."""
    statement = _add_column_statement(transparency_upgrade_ddl, "estimated_cost_usd").upper()

    assert "DOUBLE PRECISION" in statement or "FLOAT" in statement
    assert "INTEGER" not in statement


def test_no_transparency_column_gets_a_server_default(
    transparency_upgrade_ddl: list[str],
) -> None:
    """Ein `server_default='0'` an `landmark_photos_total` loeschte den Marker "dieser Teilschritt
    fand statt" unumkehrbar; an `estimated_cost_usd` behauptete er eine Kostenaussage, die niemand
    getroffen hat. SQLite koennte beides nicht sichtbar machen."""
    for column in _EXPECTED_TRANSPARENCY_INTEGER_COLUMNS + _EXPECTED_TRANSPARENCY_FLOAT_COLUMNS:
        statement = _add_column_statement(transparency_upgrade_ddl, column)
        assert "DEFAULT" not in statement.upper(), column


def test_the_foreign_key_is_created_under_its_explicit_name(
    transparency_upgrade_ddl: list[str],
) -> None:
    """Security-Muss der Spec: ein per `batch_alter_table` UNBENANNT angelegter Fremdschluessel
    ist im `downgrade()` unter SQLite nicht droppbar (`drop_constraint` braucht einen Namen), und
    `Base.metadata` traegt keine `naming_convention`, aus der einer entstuende. Unter Postgres ist
    der Name im gerenderten DDL direkt sichtbar - hier wird er festgenagelt."""
    constraint_statements = [
        statement
        for statement in transparency_upgrade_ddl
        if "ADD CONSTRAINT" in statement.upper() and "FOREIGN KEY" in statement.upper()
    ]
    assert len(constraint_statements) == 1, transparency_upgrade_ddl
    statement = constraint_statements[0]

    assert _EXPECTED_FK_NAME in statement
    assert "remote_category_classification_runs" in statement


def test_the_transparency_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_TRANSPARENCY_REVISION, direction="downgrade")

    rendered = " ".join(statements).upper()
    assert rendered.count("DROP COLUMN") == 6
    assert _EXPECTED_FK_NAME.upper() in rendered
    assert "DROP CONSTRAINT" in rendered


# specs/features/0300-nebenkategorien.md, decisions/0069 Punkt 9: eine Boolean-Spalte mit einem
# Server-Default, der unmittelbar danach wieder verschwindet, plus ein Constraint-TAUSCH. SQLite
# kann davon strukturell nichts pruefen: es kennt kein BOOLEAN (ein `DEFAULT 1` liefe dort
# klaglos durch und braeche Postgres mit DatatypeMismatch), und der Constraint-Tausch entsteht
# dort ausschliesslich ueber den Tabellen-Neuaufbau von `batch_alter_table` - nur der
# Postgres-Renderpfad zeigt die beiden benannten `ALTER TABLE`-Anweisungen einzeln.
#
# Bewusst nur `upgrade()` (Teststrategie der Spec): `downgrade()` beginnt mit einem `DELETE` -
# einer Datenanweisung, die der Mock-Renderpfad nicht sinnvoll abbildet. Ihr Verhalten prueft
# test_migration_nebenkategorien.py gegen eine echte (SQLite-)Datenbank.

_SECONDARY_CATEGORIES_REVISION = "c9d0e1f2a3b4_nebenkategorien.py"


@pytest.fixture(scope="module")
def secondary_categories_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_SECONDARY_CATEGORIES_REVISION)


def test_the_is_primary_column_renders_as_boolean_with_a_boolean_default(
    secondary_categories_upgrade_ddl: list[str],
) -> None:
    """Der Default versorgt den Altbestand - er muss ein BOOLEAN-Literal sein, kein Integer.
    `DEFAULT 1` liefe unter SQLite durch und liesse den Backend-Container auf Postgres beim
    `alembic upgrade head` sterben (derselbe Fund wie bei `cloud_requested`)."""
    statement = _add_column_statement(secondary_categories_upgrade_ddl, "is_primary")

    assert "BOOLEAN" in statement.upper()
    assert "NOT NULL" in statement.upper()
    assert "DEFAULT true" in statement
    assert "DEFAULT 1" not in statement


def test_the_server_default_is_dropped_again_after_the_backfill(
    secondary_categories_upgrade_ddl: list[str],
) -> None:
    """DIE eigentliche Aussage dieser Revision (Akzeptanzkriterium 25): der Default hat genau eine
    Aufgabe und darf sie nicht ueberleben. Bliebe er stehen, erzeugte ein Schreibpfad, der
    `is_primary` vergisst, still eine ZWEITE Hauptkategorie - und die Spalte traegt genau die
    Invariante, die das verhindern soll."""
    rendered = " ".join(secondary_categories_upgrade_ddl).upper()

    assert "ALTER COLUMN IS_PRIMARY DROP DEFAULT" in rendered


def test_both_unique_constraints_are_named_in_the_swap(
    secondary_categories_upgrade_ddl: list[str],
) -> None:
    """Beide Constraints BENANNT (ADR 0069 Punkt 9): `Base.metadata` traegt keine
    `naming_convention`, aus der ein Name entstuende, und ein unbenannter Constraint ist unter
    SQLite nicht droppbar."""
    rendered = " ".join(secondary_categories_upgrade_ddl)

    assert "DROP CONSTRAINT uq_photo_ranking_run_photo" in rendered
    assert "ADD CONSTRAINT uq_photo_ranking_run_photo_category UNIQUE" in rendered
    assert "criterion_scoring_run_id, photo_id, category_key" in rendered


# specs/features/0051-gps-landmark-cluster-bildung.md, decisions/0072-ortsbezogene-cluster-
# anzeigeort-als-antwortableitung.md: zwei additive Koordinatenspalten. SQLite kann beide
# entscheidenden Aussagen strukturell nicht pruefen - es kennt keinen Unterschied zwischen INTEGER
# und DOUBLE PRECISION (eine ganzzahlige Spalte machte aus 48.858093 ein 48, ohne dass irgendetwas
# fehlschluege) und akzeptiert einen unbeabsichtigten Server-Default klaglos. `DEFAULT 0` waere
# hier keine harmlose Null, sondern eine GUELTIGE Koordinate im Golf von Guinea an jeder
# Bestandszeile.

_GPS_REVISION = "d1e2f3a4b5c6_gps_koordinaten.py"


@pytest.fixture(scope="module")
def gps_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_GPS_REVISION)


def test_both_gps_columns_are_added_for_postgres(gps_upgrade_ddl: list[str]) -> None:
    for column in ("gps_lat", "gps_lon"):
        _add_column_statement(gps_upgrade_ddl, column)


def test_both_gps_columns_render_as_a_floating_point_type(gps_upgrade_ddl: list[str]) -> None:
    for column in ("gps_lat", "gps_lon"):
        statement = _add_column_statement(gps_upgrade_ddl, column).upper()
        assert "DOUBLE PRECISION" in statement or "FLOAT" in statement, column
        assert "INTEGER" not in statement, column


def test_neither_gps_column_gets_a_server_default(gps_upgrade_ddl: list[str]) -> None:
    """DIE eigentliche Aussage dieser Revision: kein Server-Default und keine NOT-NULL-Bedingung.
    "Kein Ort bekannt" muss `NULL` bleiben - `0.0` ist eine Ortsangabe, keine Abwesenheit."""
    for column in ("gps_lat", "gps_lon"):
        statement = _add_column_statement(gps_upgrade_ddl, column).upper()
        assert "DEFAULT" not in statement, column
        assert "NOT NULL" not in statement, column


def test_the_gps_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_GPS_REVISION, direction="downgrade")

    rendered = " ".join(statements).upper()
    assert rendered.count("DROP COLUMN") == 2


# specs/features/0425-events-statt-zeitcluster.md, decisions/0087-event-als-persistierte-einheit-
# und-trennsignale-als-liste.md: neue Tabelle `events` mit ECHTEM Fremdschluessel und
# `UniqueConstraint(run, position)`, dazu der Spaltentausch an `photo_rankings`.
#
# Unter SQLite entstehen Fremdschluessel und Unique-Constraint ausschliesslich ueber den
# Tabellen-Neuaufbau von `batch_alter_table` und sind dort von einer reinen Spaltenpruefung nicht
# zu unterscheiden. Unter Postgres steht beides im gerenderten DDL.

_EVENTS_REVISION = "f5a6b7c8d9e0_events.py"


@pytest.fixture(scope="module")
def events_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_EVENTS_REVISION)


def test_the_events_table_is_created_for_postgres(events_upgrade_ddl: list[str]) -> None:
    create = [s for s in events_upgrade_ddl if "CREATE TABLE EVENTS" in s.upper()]

    assert create, "kein CREATE TABLE events im gerenderten DDL gefunden"
    rendered = create[0].upper()
    for column in ("POSITION", "STARTED_AT", "ENDED_AT", "LANDMARK_NAME", "PLACE_KIND"):
        assert column in rendered, column


def test_the_event_coordinates_render_as_a_floating_point_type(
    events_upgrade_ddl: list[str],
) -> None:
    """Ein ganzzahliger Typ machte aus 48.86 die Zahl 48 - eine Ortsverschiebung von rund 95 km,
    die SQLite nicht sichtbar machen koennte."""
    [create] = [s for s in events_upgrade_ddl if "CREATE TABLE EVENTS" in s.upper()]

    for line in create.splitlines():
        if "place_lat" in line or "place_lon" in line:
            assert "DOUBLE PRECISION" in line.upper() or "FLOAT" in line.upper(), line
            assert "INTEGER" not in line.upper(), line


def test_the_event_run_binding_is_a_real_foreign_key(events_upgrade_ddl: list[str]) -> None:
    """Eine bloss logische Spalte fiele still aus der Erreichbarkeitspruefung der Projektloeschung
    heraus, und unter Postgres entstuenden verwaiste Zeilen."""
    [create] = [s for s in events_upgrade_ddl if "CREATE TABLE EVENTS" in s.upper()]

    assert "FOREIGN KEY(criterion_scoring_run_id) REFERENCES criterion_scoring_runs (id)" in create
    assert "fk_events_criterion_scoring_run_id" in create


def test_the_event_position_is_unique_per_run(events_upgrade_ddl: list[str]) -> None:
    [create] = [s for s in events_upgrade_ddl if "CREATE TABLE EVENTS" in s.upper()]

    assert "CONSTRAINT uq_event_run_position UNIQUE (criterion_scoring_run_id, position)" in create


def test_the_ranking_rows_are_deleted_before_the_not_null_column_arrives(
    events_upgrade_ddl: list[str],
) -> None:
    """Die Reihenfolge ist die Migration: eine NOT-NULL-Spalte laesst sich einer nicht-leeren
    Tabelle nur mit einem Ersatzwert hinzufuegen, und jede Event-Id waere erfunden."""
    rendered = [s.upper() for s in events_upgrade_ddl]
    delete_index = next(i for i, s in enumerate(rendered) if "DELETE FROM PHOTO_RANKINGS" in s)
    add_index = next(i for i, s in enumerate(rendered) if "ADD COLUMN EVENT_ID" in s)

    assert delete_index < add_index


def test_the_new_ranking_column_is_not_null_and_a_real_foreign_key(
    events_upgrade_ddl: list[str],
) -> None:
    rendered = " ".join(events_upgrade_ddl)

    assert "ADD COLUMN event_id INTEGER NOT NULL" in rendered
    assert "fk_photo_rankings_event_id" in rendered
    assert "FOREIGN KEY(event_id) REFERENCES events (id)" in rendered


def test_the_old_partition_column_is_dropped(events_upgrade_ddl: list[str]) -> None:
    rendered = " ".join(events_upgrade_ddl).upper()

    assert "DROP COLUMN CLUSTER_KEY" in rendered


def test_the_events_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_EVENTS_REVISION, direction="downgrade")

    rendered = " ".join(statements).upper()
    assert "DROP TABLE EVENTS" in rendered
    assert "ADD COLUMN CLUSTER_KEY" in rendered
    assert "DROP COLUMN EVENT_ID" in rendered


def test_the_events_downgrade_drops_the_temporary_default_again() -> None:
    """Der `server_default` beim Wiederanlegen ist VORUEBERGEHEND - er fuellt unter SQLite beim
    Tabellen-Neuaufbau die Zeilen, die nach dem `upgrade` entstanden sind. Unter Postgres gibt es
    keinen Neuaufbau: dort ist sein Entfernen eine eigene `ALTER COLUMN ... DROP DEFAULT`, und nur
    sie trennt den Endzustand vom Ausgangszustand aus `c1d2e3f4a5b6`.

    Die Reihenfolge ist Teil der Aussage: ein `DROP DEFAULT` VOR dem `ADD COLUMN` liefe ins
    Leere."""
    rendered = [s.upper() for s in _render_postgres_ddl(_EVENTS_REVISION, direction="downgrade")]

    add_index = next(i for i, s in enumerate(rendered) if "ADD COLUMN CLUSTER_KEY" in s)
    drop_default_index = next(
        i for i, s in enumerate(rendered) if "ALTER COLUMN CLUSTER_KEY DROP DEFAULT" in s
    )

    assert add_index < drop_default_index


# specs/features/0426-zeitversatz-je-kamera.md, Umsetzungsschritt 1: `project_cameras` plus drei
# Spalten an `photos`. Drei Aussagen kann SQLite strukturell nicht pruefen - der Boolean-Default
# von `camera_probed` (dort ist BOOLEAN nur INTEGER), der Zeitstempeltyp von
# `taken_at_original` und der EXPLIZITE Fremdschluesselname, ohne den der Rueckweg nicht
# ausfuehrbar ist.

_CAMERA_REVISION = "a6b7c8d9e0f1_kamera_zeitversatz.py"


@pytest.fixture(scope="module")
def camera_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_CAMERA_REVISION)


def test_the_probed_marker_default_is_rendered_as_a_boolean_literal(
    camera_upgrade_ddl: list[str],
) -> None:
    """Dieselbe Falle wie bei `cloud_requested` oben: `DEFAULT 0` auf einer BOOLEAN-Spalte laeuft
    in SQLite durch und bricht Postgres mit `DatatypeMismatch` ab - der Backend-Container fuehrt
    `alembic upgrade head` VOR dem Serverstart aus und wuerde nie gesund."""
    add_column = [s for s in camera_upgrade_ddl if "camera_probed" in s]
    assert add_column, "kein ADD COLUMN fuer camera_probed im gerenderten DDL gefunden"
    statement = add_column[0]

    assert "BOOLEAN" in statement.upper()
    assert "DEFAULT false" in statement
    assert "DEFAULT 0" not in statement


def test_the_recorded_time_is_a_timestamp_without_zone_and_not_null(
    camera_upgrade_ddl: list[str],
) -> None:
    """`taken_at_original` muss dieselbe Form haben wie `taken_at` - zonenlos (ADR 0090, Punkt 4)
    und am Ende NOT NULL."""
    add_column = [s for s in camera_upgrade_ddl if "taken_at_original" in s and "ADD COLUMN" in s]
    assert add_column, "kein ADD COLUMN fuer taken_at_original im gerenderten DDL gefunden"

    assert "TIMESTAMP" in add_column[0].upper()
    assert "WITH TIME ZONE" not in add_column[0].upper()

    rendered = " ".join(camera_upgrade_ddl).upper()
    assert "ALTER COLUMN TAKEN_AT_ORIGINAL SET NOT NULL" in rendered


def test_the_photo_camera_foreign_key_carries_its_explicit_name(
    camera_upgrade_ddl: list[str],
) -> None:
    """Nur im Postgres-Render sichtbar - und ohne den Namen ist das `drop_constraint` des
    `downgrade` nicht ausfuehrbar."""
    rendered = " ".join(camera_upgrade_ddl)

    assert "fk_photos_camera_id" in rendered
    assert "FOREIGN KEY(camera_id) REFERENCES project_cameras (id)" in rendered


def test_the_offset_column_is_an_integer(camera_upgrade_ddl: list[str]) -> None:
    """SQLite kennt keinen Unterschied zwischen INTEGER und DOUBLE PRECISION - der Versatz ist
    eine vorzeichenbehaftete Ganzzahl Minuten, kein Gleitkommawert."""
    create_table = [s for s in camera_upgrade_ddl if "CREATE TABLE project_cameras" in s]
    assert create_table, "kein CREATE TABLE fuer project_cameras im gerenderten DDL gefunden"

    assert "offset_minutes INTEGER DEFAULT '0' NOT NULL" in create_table[0]


def test_the_camera_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_CAMERA_REVISION, direction="downgrade")

    rendered = " ".join(statements)
    upper = rendered.upper()
    assert "DROP TABLE PROJECT_CAMERAS" in upper
    assert "DROP COLUMN TAKEN_AT_ORIGINAL" in upper
    assert "DROP COLUMN CAMERA_ID" in upper
    assert "DROP COLUMN CAMERA_PROBED" in upper
    assert "fk_photos_camera_id" in rendered


def test_the_camera_downgrade_writes_the_times_back_before_dropping_the_column() -> None:
    """Die REIHENFOLGE ist die eigentliche Aussage des Rueckwegs: steht das `UPDATE` nach dem
    `DROP COLUMN`, liest es eine Spalte, die es nicht mehr gibt - und die aufgezeichneten Zeiten
    sind unwiederbringlich fort."""
    rendered = [s.upper() for s in _render_postgres_ddl(_CAMERA_REVISION, direction="downgrade")]

    update_index = next(
        i for i, s in enumerate(rendered) if "UPDATE PHOTOS SET TAKEN_AT = TAKEN_AT_ORIGINAL" in s
    )
    drop_index = next(i for i, s in enumerate(rendered) if "DROP COLUMN TAKEN_AT_ORIGINAL" in s)

    assert update_index < drop_index


# specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 3: die drei Motiv-Tabellen. Vier
# Aussagen kann SQLite strukturell nicht pruefen - der FLIESSKOMMA-Typ der Staerke (dort ist
# INTEGER von DOUBLE PRECISION nicht zu unterscheiden, und eine Integer-Spalte schnitte jede
# Staerke auf 0 oder 1 ab), der BOOLEAN-Typ der beiden Wahrheitswerte, das fehlende Default am
# Ausschluss-Flag und die BENANNTEN Unique-Constraints, ohne die der Rueckweg nicht ausfuehrbar
# ist.

_MOTIF_REVISION = "b7c8d9e0f1a2_motivstaerken.py"


@pytest.fixture(scope="module")
def motif_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_MOTIF_REVISION)


def test_the_strength_column_is_a_floating_point_column(motif_upgrade_ddl: list[str]) -> None:
    """DER Fall, den die SQLite-Suite nicht sehen kann: dort ist der Unterschied zwischen INTEGER
    und DOUBLE PRECISION keiner. Unter Postgres schnitte eine Integer-Spalte jede Staerke auf 0
    oder 1 ab - und die gesamte Story bestuende aus genau zwei Werten."""
    create_table = [s for s in motif_upgrade_ddl if "CREATE TABLE photo_motif_strengths" in s]
    assert create_table, "kein CREATE TABLE fuer photo_motif_strengths im gerenderten DDL gefunden"

    assert "strength FLOAT NOT NULL" in create_table[0]
    assert "strength INTEGER" not in create_table[0]


def test_both_truth_values_are_rendered_as_boolean_columns(motif_upgrade_ddl: list[str]) -> None:
    rendered = " ".join(motif_upgrade_ddl)

    assert "excluded_document BOOLEAN NOT NULL" in rendered
    assert "applies BOOLEAN NOT NULL" in rendered


def test_the_exclusion_flag_is_rendered_without_any_default(motif_upgrade_ddl: list[str]) -> None:
    """Ein `DEFAULT false` machte einen Schreibpfad, der die Spalte vergisst, still erfolgreich -
    und nahm das Foto aus jeder Motivauswahl, ohne Korrekturmoeglichkeit."""
    create_table = [s for s in motif_upgrade_ddl if "CREATE TABLE photo_motif_assessments" in s]
    assert create_table, "kein CREATE TABLE fuer photo_motif_assessments gefunden"

    assert "excluded_document BOOLEAN NOT NULL," in create_table[0]
    assert "excluded_document BOOLEAN DEFAULT" not in create_table[0]


def test_both_unique_constraints_carry_their_explicit_name(motif_upgrade_ddl: list[str]) -> None:
    rendered = " ".join(motif_upgrade_ddl)

    assert "CONSTRAINT uq_motif_strength_photo_key UNIQUE (photo_id, motif_key)" in rendered
    assert "CONSTRAINT uq_motif_correction_photo_key UNIQUE (photo_id, motif_key)" in rendered


def test_the_correction_constraint_does_not_include_the_user(motif_upgrade_ddl: list[str]) -> None:
    """Die Aussage gehoert zum FOTO. Mit `user_id` im Constraint entstuenden zwei
    widersprueckliche Zeilen fuer dasselbe Paar, und welche gilt, entschiede die Sortierung."""
    rendered = " ".join(motif_upgrade_ddl)

    assert "uq_motif_correction_photo_key UNIQUE (photo_id, motif_key, user_id)" not in rendered


def test_the_strength_foreign_key_points_at_the_header(motif_upgrade_ddl: list[str]) -> None:
    rendered = " ".join(motif_upgrade_ddl)

    assert "fk_photo_motif_strengths_photo_id" in rendered
    assert "FOREIGN KEY(photo_id) REFERENCES photo_motif_assessments (photo_id)" in rendered


def test_the_three_timestamps_are_zoneless(motif_upgrade_ddl: list[str]) -> None:
    """Alle Zeitstempel des Projekts sind zonenlos (ADR 0090, Punkt 4)."""
    rendered = " ".join(motif_upgrade_ddl).upper()

    assert "COMPUTED_AT TIMESTAMP WITHOUT TIME ZONE NOT NULL" in rendered
    assert "UPDATED_AT TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL" in rendered
    assert "WITH TIME ZONE" not in rendered


def test_the_motif_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_MOTIF_REVISION, direction="downgrade")

    rendered = " ".join(statements).upper()
    assert "DROP TABLE PHOTO_MOTIF_CORRECTIONS" in rendered
    assert "DROP TABLE PHOTO_MOTIF_STRENGTHS" in rendered
    assert "DROP TABLE PHOTO_MOTIF_ASSESSMENTS" in rendered


def test_the_motif_downgrade_drops_the_strengths_before_their_header() -> None:
    """Die REIHENFOLGE ist die Aussage des Rueckwegs: die Staerkezeilen haengen an der Kopfzeile.
    Umgekehrt bricht der Rueckweg an einer echten Datenbank an der Fremdschluesselbedingung ab -
    unter SQLite faellt das nicht auf."""
    rendered = [s.upper() for s in _render_postgres_ddl(_MOTIF_REVISION, direction="downgrade")]

    strength_index = next(
        i for i, s in enumerate(rendered) if "DROP TABLE PHOTO_MOTIF_STRENGTHS" in s
    )
    header_index = next(
        i for i, s in enumerate(rendered) if "DROP TABLE PHOTO_MOTIF_ASSESSMENTS" in s
    )

    assert strength_index < header_index


def test_the_upgrade_touches_no_existing_table() -> None:
    """Rein additiv - kein `ALTER TABLE`, kein `UPDATE`, kein `DELETE`. Ein versehentlich
    mitgenommener Schritt an der Kategorie-Welt gehoerte in eine andere PR."""
    rendered = " ".join(_render_postgres_ddl(_MOTIF_REVISION)).upper()

    assert "ALTER TABLE" not in rendered
    assert "UPDATE " not in rendered
    assert "DELETE " not in rendered


# specs/features/0427-motive-mit-staerke.md, PR 3 Schritt 2 samt Sicherheitsauflage S17: die
# Loeschung der ueberzaehligen Rangzeilen muss dem Constraint-Tausch VORAUSGEHEN, sonst ist der
# Weg an einer nicht-leeren Datenbank nicht ausfuehrbar.
#
# Genau diese Zusage ist ueber die SQLite-Probe NICHT haltbar: dort entsteht der Constraint-Tausch
# ausschliesslich ueber den Tabellen-Neuaufbau von `batch_alter_table`, der die falsche Reihenfolge
# verzeiht - der Test waere dort unerfuellbar rot oder dauerhaft gruen. Unter Postgres stehen die
# Anweisungen einzeln und in ihrer echten Reihenfolge. Die DATENWIRKUNG derselben Anweisung bleibt
# der SQLite-Probe in test_migration_kategorien_abloesung.py.

_CATEGORY_COLUMNS_REVISION = "c3d4e5f6a7b8_kategoriespalten_entfallen.py"
_CATEGORY_TABLE_REVISION = "c4d5e6f7a8b9_kategorietabelle_entfaellt.py"


@pytest.fixture(scope="module")
def category_columns_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_CATEGORY_COLUMNS_REVISION)


def test_the_row_deletion_precedes_the_constraint_swap(
    category_columns_upgrade_ddl: list[str],
) -> None:
    """DIE Aussage dieser Revision (S17): Index-Vergleich zweier Anweisungen. Das `DELETE` auf
    `photo_rankings` steht VOR dem `DROP CONSTRAINT`/`ADD CONSTRAINT`-Paar."""
    rendered = [statement.upper() for statement in category_columns_upgrade_ddl]

    delete_index = next(
        (i for i, s in enumerate(rendered) if "DELETE FROM PHOTO_RANKINGS" in s), None
    )
    swap_index = next(
        (
            i
            for i, s in enumerate(rendered)
            if "ADD CONSTRAINT UQ_PHOTO_RANKING_RUN_PHOTO " in s
            or "ADD CONSTRAINT UQ_PHOTO_RANKING_RUN_PHOTO(" in s
        ),
        None,
    )
    assert delete_index is not None, rendered
    assert swap_index is not None, rendered

    assert delete_index < swap_index


def test_the_deletion_does_not_merely_drop_the_secondary_rows(
    category_columns_upgrade_ddl: list[str],
) -> None:
    """Die zweite Haelfte von S17: `WHERE is_primary = false` allein SETZT die Nachbedingung
    VORAUS, statt sie herzustellen. Die Anweisung muss je (Lauf, Foto) auswaehlen, welche eine
    Zeile bleibt - erkennbar an der Partitionierung ueber genau dieses Paar."""
    deletes = [
        statement
        for statement in category_columns_upgrade_ddl
        if "DELETE FROM photo_rankings" in statement
    ]
    assert len(deletes) == 1, category_columns_upgrade_ddl
    statement = deletes[0]

    assert "PARTITION BY criterion_scoring_run_id, photo_id" in statement
    assert statement.upper().count("WHERE IS_PRIMARY = FALSE") == 0


def test_both_unique_constraints_are_named_in_the_swap_back(
    category_columns_upgrade_ddl: list[str],
) -> None:
    rendered = " ".join(category_columns_upgrade_ddl)

    assert "DROP CONSTRAINT uq_photo_ranking_run_photo_category" in rendered
    assert "ADD CONSTRAINT uq_photo_ranking_run_photo " in rendered


def test_all_three_columns_are_dropped_for_postgres(
    category_columns_upgrade_ddl: list[str],
) -> None:
    rendered = " ".join(category_columns_upgrade_ddl)

    assert "DROP COLUMN category_key" in rendered
    assert "DROP COLUMN is_primary" in rendered
    assert "DROP COLUMN category_override" in rendered


def test_the_restored_boolean_default_of_the_downgrade_is_a_boolean_literal() -> None:
    """Derselbe Dialektfehler wie bei `cloud_requested`/`is_primary`: ein `DEFAULT 1` auf einer
    BOOLEAN-Spalte laeuft unter SQLite durch und laesst den Backend-Container auf Postgres beim
    `alembic upgrade head` sterben - hier im RUECKWEG, den nur dieser Renderpfad sieht."""
    statement = _add_column_statement(
        _render_postgres_ddl(_CATEGORY_COLUMNS_REVISION, direction="downgrade"), "is_primary"
    )

    assert "BOOLEAN" in statement.upper()
    assert "DEFAULT true" in statement
    assert "DEFAULT 1" not in statement


def test_the_downgrade_drops_both_temporary_server_defaults_again() -> None:
    """Die Defaults versorgen die NOT-NULL-Bedingung des Altbestands und duerfen sie nicht
    ueberleben (S18: Struktur, nie Daten)."""
    rendered = " ".join(
        _render_postgres_ddl(_CATEGORY_COLUMNS_REVISION, direction="downgrade")
    ).upper()

    assert "ALTER COLUMN IS_PRIMARY DROP DEFAULT" in rendered
    assert "ALTER COLUMN CATEGORY_KEY DROP DEFAULT" in rendered


def test_the_table_revision_drops_the_classification_table() -> None:
    rendered = " ".join(_render_postgres_ddl(_CATEGORY_TABLE_REVISION)).upper()

    assert "DROP TABLE PHOTO_CATEGORY_CLASSIFICATIONS" in rendered


def test_the_table_revision_downgrade_renders_for_postgres_too() -> None:
    """Der Rueckweg legt die Tabelle LEER wieder an - kein `INSERT`, keine Rekonstruktion."""
    statements = _render_postgres_ddl(_CATEGORY_TABLE_REVISION, direction="downgrade")

    rendered = " ".join(statements).upper()
    assert "CREATE TABLE PHOTO_CATEGORY_CLASSIFICATIONS" in rendered
    assert "JSON" in rendered
    assert "INSERT " not in rendered


# specs/features/0428-albumtauglichkeit-vom-modell.md: eine neue Tabelle plus zwei Spalten, die
# nullable werden. Die Nullbarkeit ist genau die Klasse von Aussage, die SQLite nicht traegt: dort
# baut `batch_alter_table` die Tabelle nach, unter Postgres muss ein `DROP NOT NULL` entstehen.
# Nur der `upgrade()` wird gerendert - der `downgrade()` traegt einen DATENschritt (`DELETE`), und
# ein reiner Renderpfad kann den nicht ausfuehren (siehe `_render_postgres_ddl`).

_ALBUM_SUITABILITY_REVISION = "d6e7f8a9b0c1_albumtauglichkeit.py"


@pytest.fixture(scope="module")
def album_suitability_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_ALBUM_SUITABILITY_REVISION)


def test_the_album_suitability_table_renders_with_its_key_and_nullability(
    album_suitability_upgrade_ddl: list[str],
) -> None:
    create = [
        statement
        for statement in album_suitability_upgrade_ddl
        if "CREATE TABLE" in statement.upper() and "photo_album_suitability" in statement
    ]
    assert create, "kein CREATE TABLE fuer photo_album_suitability gefunden"
    statement = create[0]

    assert "PRIMARY KEY (photo_id)" in statement
    assert "FOREIGN KEY(photo_id) REFERENCES photos (id)" in statement
    assert "level INTEGER NOT NULL" in statement
    assert "provider VARCHAR NOT NULL" in statement
    assert "computed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL" in statement
    # Die eigentliche Aussage der Spalte: ohne brauchbare Begruendung steht dort `NULL`.
    assert "reason VARCHAR, " in statement


def test_both_ranking_columns_get_a_drop_not_null_and_the_event_does_not(
    album_suitability_upgrade_ddl: list[str],
) -> None:
    rendered = " ".join(album_suitability_upgrade_ddl).upper()

    assert "ALTER TABLE PHOTO_RANKINGS ALTER COLUMN RANK_SCORE DROP NOT NULL" in rendered
    assert "ALTER TABLE PHOTO_RANKINGS ALTER COLUMN RANK_POSITION DROP NOT NULL" in rendered
    assert "EVENT_ID" not in rendered


def test_the_upgrade_touches_no_data_at_all(album_suitability_upgrade_ddl: list[str]) -> None:
    """Reine Strukturaenderung: kein Backfill, keine Ruecksetzung der Bestandswerte."""
    rendered = " ".join(album_suitability_upgrade_ddl).upper()

    assert "INSERT " not in rendered
    assert "UPDATE " not in rendered
    assert "DELETE " not in rendered


# specs/features/0429-auswahl-richtwert-und-mischung.md: die zwei additiven Spalten des
# Auswahlvorschlags. `NULL` traegt in beiden Bedeutung ("nicht selbst eingestellt" /
# "gehoert nicht zum Vorschlag") - ein `server_default` machte daraus stillschweigend eine
# Aussage, und SQLite koennte den Unterschied nicht sichtbar machen.

_SELECTION_REVISION = "e7f8a9b0c1d2_auswahlvorschlag.py"


@pytest.fixture(scope="module")
def selection_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_SELECTION_REVISION)


def test_both_selection_columns_render_as_nullable_integers(
    selection_upgrade_ddl: list[str],
) -> None:
    for table, column in (
        ("projects", "selection_target"),
        ("photo_rankings", "selection_position"),
    ):
        statement = _add_column_statement(selection_upgrade_ddl, column)
        assert table in statement, column
        assert "INTEGER" in statement.upper(), column
        assert "NOT NULL" not in statement.upper(), column


def test_neither_selection_column_gets_a_server_default(
    selection_upgrade_ddl: list[str],
) -> None:
    for column in ("selection_target", "selection_position"):
        assert "DEFAULT" not in _add_column_statement(selection_upgrade_ddl, column).upper()


def test_the_selection_upgrade_touches_no_data_at_all(selection_upgrade_ddl: list[str]) -> None:
    """Kein Backfill: es gibt keine Migration, die den Vorschlag rueckwirkend berechnet."""
    rendered = " ".join(selection_upgrade_ddl).upper()

    assert "INSERT " not in rendered
    assert "UPDATE " not in rendered
    assert "DELETE " not in rendered


def test_the_selection_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_SELECTION_REVISION, direction="downgrade")

    rendered = " ".join(statements)
    assert rendered.upper().count("DROP COLUMN") == 2
    assert "selection_position" in rendered
    assert "selection_target" in rendered


# specs/features/0430-album-entwurf-je-nutzer.md: `ratings.status` wird nullable, `favorite` zieht
# als eigene Boolean-Spalte daneben. Zwei Dinge, die SQLite strukturell nicht sehen kann: der
# Boolean-Default (dort kein eigener Typ) und ein `ALTER COLUMN`, das SQLite gar nicht kennt und
# das `batch_alter_table` dort durch einen Tabellenneuaufbau ersetzt - auf Postgres muss daraus
# echtes `ALTER ... ALTER COLUMN ... DROP NOT NULL` werden.

_ALBUM_DECISION_REVISION = "f6a7b8c9d0e1_albumentscheidung.py"


@pytest.fixture(scope="module")
def album_decision_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_ALBUM_DECISION_REVISION)


def test_the_favorite_column_renders_as_not_null_boolean_with_a_boolean_default(
    album_decision_upgrade_ddl: list[str],
) -> None:
    statement = _add_column_statement(album_decision_upgrade_ddl, "favorite")

    assert "ratings" in statement
    assert "BOOLEAN" in statement.upper()
    assert "NOT NULL" in statement.upper()
    assert "DEFAULT false" in statement
    # Die eigentliche Aussage: kein Integer-Literal als Boolean-Default.
    assert "DEFAULT 0" not in statement


def test_the_status_column_loses_its_not_null_for_postgres(
    album_decision_upgrade_ddl: list[str],
) -> None:
    """`NULL` heisst "keine Albumentscheidung" - ohne diese Anweisung traegt Postgres die alte
    `NOT NULL`-Bedingung weiter, und jedes `DELETE .../rating` auf eine Favoritenzeile endete in
    einer 500."""
    rendered = " ".join(album_decision_upgrade_ddl).upper()

    assert "ALTER COLUMN STATUS DROP NOT NULL" in rendered


def test_the_album_decision_upgrade_converts_both_coupled_columns(
    album_decision_upgrade_ddl: list[str],
) -> None:
    """Die Konvertierung ist der Zweck dieser Migration und muss auch auf Postgres ankommen -
    beide Spalten, `ratings.status` UND die ueber dieselbe Enum-Klasse gekoppelte
    `photo_scores.suggested_status` (Auflage S11).

    GEPRUEFT WIRD AUSDRUECKLICH DIE SCHREIBWEISE: Die Spalten tragen den Enum-NAMEN
    (`'FAVORITE'`). Ein `WHERE` auf den kleingeschriebenen `.value` traefe keine Zeile - die
    Migration liefe fehlerfrei durch und konvertierte nichts."""
    rendered = " ".join(album_decision_upgrade_ddl)

    assert (
        "UPDATE ratings SET favorite = true, status = NULL WHERE upper(status) = 'FAVORITE'"
        in rendered
    )
    assert (
        "UPDATE photo_scores SET suggested_status = NULL "
        "WHERE upper(suggested_status) = 'FAVORITE'" in rendered
    )
    assert "'favorite'" not in rendered


def test_the_album_decision_downgrade_renders_for_postgres_too() -> None:
    """Der Rueckwaertsweg traegt hier mehr als ein `DROP COLUMN`: zwei Datenschritte und ein
    `SET NOT NULL`. Die REIHENFOLGE ist tragend - wird die Spalte vor der Ruecksicherung
    entfernt, ist der Favorit fort, und ohne das vorangehende `DELETE` scheitert der
    `NOT NULL`-Aufbau."""
    statements = _render_postgres_ddl(_ALBUM_DECISION_REVISION, direction="downgrade")

    rendered = " ".join(statements)
    # Der Rueckweg schreibt einen Wert, den das WIEDERHERGESTELLTE alte Enum lesen koennen muss.
    assert "'favorite'" not in rendered
    positions = [
        rendered.index("UPDATE ratings SET status = 'FAVORITE'"),
        rendered.index("DELETE FROM ratings WHERE status IS NULL"),
        rendered.upper().index("ALTER COLUMN STATUS SET NOT NULL"),
        rendered.upper().index("DROP COLUMN FAVORITE"),
    ]

    assert positions == sorted(positions)


# specs/features/0431-endauswahl-gemeinsam.md: die neue Tabelle `final_selection_decisions`.
# `included` ist eine BOOLEAN-Spalte OHNE Default - und genau diese Abwesenheit ist unter SQLite
# nicht pruefbar: dort ist BOOLEAN ein INTEGER, ein versehentliches `server_default=sa.text("0")`
# liefe klaglos durch und fiele erst auf Postgres um. Die zweite Haelfte des Nachweises (ein
# `INSERT` ohne die Spalte gegen das aus `Base.metadata` erzeugte Schema) steht in
# `test_migration_endauswahl.py`.

_FINAL_SELECTION_REVISION = "a1b2c3d4e5f6_endauswahl.py"


@pytest.fixture(scope="module")
def final_selection_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_FINAL_SELECTION_REVISION)


def _create_table_statement(ddl: list[str], table: str) -> str:
    # VERANKERT am `CREATE TABLE <name> (` und nicht am blossen Vorkommen des Namens: Der Name
    # einer Tabelle steht auch in der `REFERENCES`-Zeile jeder anderen, die auf sie zeigt - eine
    # Suche nach dem Namen allein liefert dann zwei Treffer und faellt ausgerechnet dort um, wo
    # zwei Tabellen einer Migration aufeinander verweisen.
    marker = f"CREATE TABLE {table} ("
    matches = [statement for statement in ddl if marker in statement]
    assert matches, f"kein CREATE TABLE fuer {table} im gerenderten DDL gefunden"
    assert len(matches) == 1, f"mehrdeutiges CREATE TABLE fuer {table}: {matches}"
    return matches[0]


def test_the_included_column_renders_as_not_null_boolean_without_any_default(
    final_selection_upgrade_ddl: list[str],
) -> None:
    """DIE Aussage dieses Blocks (Zusicherung 17): Die Abwesenheit der Zeile heisst
    "unentschieden" - ein Default erfaende eine Entscheidung, die niemand getroffen hat."""
    statement = _create_table_statement(final_selection_upgrade_ddl, "final_selection_decisions")
    included_line = next(
        line for line in statement.splitlines() if line.strip().startswith("included")
    )

    assert "BOOLEAN" in included_line.upper()
    assert "NOT NULL" in included_line.upper()
    assert "DEFAULT" not in included_line.upper()


def test_the_primary_key_and_the_foreign_key_both_sit_on_photo_id(
    final_selection_upgrade_ddl: list[str],
) -> None:
    """Beide auf derselben Spalte: "hoechstens eine Entscheidung je Foto" braucht dadurch keinen
    eigenen Unique-Constraint, und der echte Fremdschluessel haelt die Tabelle in der
    Erreichbarkeitspruefung der Projektloeschung."""
    statement = _create_table_statement(final_selection_upgrade_ddl, "final_selection_decisions")

    assert "PRIMARY KEY (photo_id)" in statement
    assert "CONSTRAINT fk_final_selection_decisions_photo_id FOREIGN KEY(photo_id)" in statement
    assert "REFERENCES photos (id)" in statement


def test_the_table_carries_no_user_reference_at_all(
    final_selection_upgrade_ddl: list[str],
) -> None:
    """ADR 0099 Punkt 3: Es gibt keine Spalte, in der ein Nutzerbezug stehen koennte - die
    Trennung von den beiden Entwuerfen ist strukturell, nicht zugesichert."""
    statement = _create_table_statement(final_selection_upgrade_ddl, "final_selection_decisions")

    assert "user_id" not in statement
    assert "decided_by" not in statement
    assert "users" not in statement


def test_the_final_selection_upgrade_touches_no_data_at_all(
    final_selection_upgrade_ddl: list[str],
) -> None:
    """Kein Backfill: Die Endauswahl eines bestehenden Projekts ist die Schnittmenge der beiden
    Entwuerfe, und keine Migration rechnet sie rueckwirkend aus."""
    rendered = " ".join(final_selection_upgrade_ddl).upper()

    assert "INSERT " not in rendered
    assert "UPDATE " not in rendered
    assert "DELETE " not in rendered


def test_the_final_selection_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_FINAL_SELECTION_REVISION, direction="downgrade")

    rendered = " ".join(statements)
    assert "DROP TABLE" in rendered.upper()
    assert "final_selection_decisions" in rendered


# specs/features/0432-diagnose-und-gewichte-aus-der-nacharbeit.md, ADR 0100: das append-only
# Ereignis-Log. Hier steht der ZWEITE der vier Nachweise dafuer, dass `event_id` wie eine Referenz
# AUSSIEHT und keine ist. Er gehoert an die gerenderte Postgres-DDL, weil die Suite gegen SQLite
# ohne `PRAGMA foreign_keys=ON` laeuft: Ein spaeter ergaenzter Fremdschluessel auf `events` fiele
# dort zur Laufzeit nicht auf, und `rebuild_run_grouping` - das die `events`-Zeilen eines Laufs
# loescht und neu anlegt - risse dann entweder Log-Zeilen mit oder bliebe stehen.

_FEEDBACK_EVENTS_REVISION = "b1c2d3e4f5a6_feedback_events.py"


@pytest.fixture(scope="module")
def feedback_events_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_FEEDBACK_EVENTS_REVISION)


def test_the_event_id_renders_without_a_foreign_key_while_the_others_render_with_one(
    feedback_events_upgrade_ddl: list[str],
) -> None:
    """ZWEITER der vier Nachweise. Die zweite Haelfte steht im SELBEN Fall: Ohne sie bestuende die
    Aussage auch fuer eine Tabelle ganz ohne Fremdschluessel."""
    statement = _create_table_statement(feedback_events_upgrade_ddl, "feedback_events")

    assert "event_id INTEGER" in statement
    assert "REFERENCES events" not in statement
    assert "FOREIGN KEY(event_id)" not in statement

    assert "FOREIGN KEY(photo_id) REFERENCES photos (id)" in statement
    assert "FOREIGN KEY(replaced_photo_id) REFERENCES photos (id)" in statement
    assert "FOREIGN KEY(project_id) REFERENCES projects (id)" in statement
    assert "FOREIGN KEY(user_id) REFERENCES users (id)" in statement
    assert (
        "FOREIGN KEY(criterion_scoring_run_id) REFERENCES criterion_scoring_runs (id)" in statement
    )


def test_the_weight_default_renders_as_a_float_literal_on_a_float_column(
    feedback_events_upgrade_ddl: list[str],
) -> None:
    """SQLite kennt keinen Unterschied zwischen INTEGER und DOUBLE PRECISION und akzeptiert jeden
    Default klaglos - der Multiplikator der Ableitung muss ein Fliesskommawert bleiben."""
    statement = _create_table_statement(feedback_events_upgrade_ddl, "feedback_events")

    assert "weight FLOAT DEFAULT '1.0' NOT NULL" in statement


def test_the_kind_column_renders_without_a_native_enum_type(
    feedback_events_upgrade_ddl: list[str],
) -> None:
    """Ohne `native_enum=False` legte Postgres einen echten Enum-Typ an, und jeder weitere
    `kind`-Wert braeuchte dort eine Typmigration, die SQLite nie verlangt."""
    rendered = " ".join(feedback_events_upgrade_ddl)
    statement = _create_table_statement(feedback_events_upgrade_ddl, "feedback_events")

    assert "CREATE TYPE" not in rendered.upper()
    assert "VARCHAR(32)" in statement


def test_the_feedback_events_upgrade_touches_no_data_at_all(
    feedback_events_upgrade_ddl: list[str],
) -> None:
    """Kein Backfill, und es gaebe auch nichts zu backfillen: Der Bestand haelt den heutigen
    Stand, nicht den Verlauf - eine zurueckgenommene Korrektur hinterlaesst dort keine Spur."""
    rendered = " ".join(feedback_events_upgrade_ddl).upper()

    assert "INSERT " not in rendered
    assert "UPDATE " not in rendered
    assert "DELETE " not in rendered


def test_the_feedback_events_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_FEEDBACK_EVENTS_REVISION, direction="downgrade")

    rendered = " ".join(statements)
    assert "DROP TABLE" in rendered.upper()
    assert "DROP INDEX" in rendered.upper()
    assert "feedback_events" in rendered


# PR 3 derselben Spec: die beiden Gewichtstabellen und der Fassungsbezug an der Lauf-Zeile. Drei
# Klassen von Fehlern, die SQLite strukturell nicht sehen kann, haengen hier: der native Enum-Typ
# (`origin`), ein versehentlicher `server_default` auf der Gewichtsspalte (SQLite kennt keinen
# Unterschied zwischen INTEGER und DOUBLE PRECISION), und der ohne Namen nicht loesbare
# Fremdschluessel der neuen Laufspalte.

_WEIGHT_SETS_REVISION = "c5d6e7f8a9b0_gewichtssaetze.py"


@pytest.fixture(scope="module")
def weight_sets_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_WEIGHT_SETS_REVISION)


def test_the_origin_renders_without_a_native_enum_type(
    weight_sets_upgrade_ddl: list[str],
) -> None:
    """Ohne `native_enum=False` legte Postgres einen echten Enum-Typ an, und jeder weitere
    Herkunftswert braeuchte dort eine Typmigration, die SQLite nie verlangt."""
    rendered = " ".join(weight_sets_upgrade_ddl)
    statement = _create_table_statement(weight_sets_upgrade_ddl, "quality_weight_sets")

    assert "CREATE TYPE" not in rendered.upper()
    assert "VARCHAR(16)" in statement


def test_the_weight_column_renders_as_a_floating_point_column_without_any_default(
    weight_sets_upgrade_ddl: list[str],
) -> None:
    """KEIN `server_default`: Ein Vorgabegewicht erfaende einen Wert, den niemand uebernommen hat,
    und ein Integer-Default auf einer Gleitkommaspalte faellt unter SQLite nie auf."""
    statement = _create_table_statement(weight_sets_upgrade_ddl, "quality_weight_entries")
    weight_line = next(line for line in statement.splitlines() if line.strip().startswith("weight"))

    assert "FLOAT" in weight_line.upper()
    assert "NOT NULL" in weight_line.upper()
    assert "DEFAULT" not in weight_line.upper()


def test_the_criterion_key_renders_without_a_foreign_key_while_the_set_binding_renders_with_one(
    weight_sets_upgrade_ddl: list[str],
) -> None:
    """Beide Haelften im SELBEN Fall - ohne die zweite bestuende die Aussage auch fuer eine
    Tabelle ganz ohne Fremdschluessel."""
    statement = _create_table_statement(weight_sets_upgrade_ddl, "quality_weight_entries")

    assert "FOREIGN KEY(criterion_key)" not in statement
    assert "FOREIGN KEY(set_id) REFERENCES quality_weight_sets (id)" in statement


def test_the_anchor_renders_without_a_foreign_key_while_the_author_renders_with_one(
    weight_sets_upgrade_ddl: list[str],
) -> None:
    """`based_on_event_id` ist ein Zustimmungs-Token (S6) und traegt bei leerem Log den Wert `0` -
    ein Fremdschluessel wiese ihn unter Postgres ab, waehrend SQLite ohne
    `PRAGMA foreign_keys=ON` klaglos schriebe."""
    statement = _create_table_statement(weight_sets_upgrade_ddl, "quality_weight_sets")

    assert "FOREIGN KEY(based_on_event_id)" not in statement
    assert "FOREIGN KEY(created_by_user_id) REFERENCES users (id)" in statement
    assert "FOREIGN KEY(reverts_set_id) REFERENCES quality_weight_sets (id)" in statement


def test_the_creation_timestamp_is_zoneless(weight_sets_upgrade_ddl: list[str]) -> None:
    """Alle Zeitstempel des Projekts sind zonenlos (ADR 0090, Punkt 4)."""
    rendered = " ".join(weight_sets_upgrade_ddl).upper()

    assert "CREATED_AT TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL" in rendered
    assert "WITH TIME ZONE" not in rendered


def test_the_run_column_is_added_with_its_explicitly_named_foreign_key(
    weight_sets_upgrade_ddl: list[str],
) -> None:
    """Der Name ist nicht Kosmetik: Ein unbenannt angelegter Constraint ist im `downgrade()` unter
    SQLite nicht droppbar, und der Rueckwaertsweg waere ohne ihn nicht ausfuehrbar."""
    statement = _add_column_statement(weight_sets_upgrade_ddl, "quality_weight_set_id")
    rendered = " ".join(weight_sets_upgrade_ddl)

    assert "criterion_scoring_runs" in statement
    assert "INTEGER" in statement.upper()
    assert "NOT NULL" not in statement.upper()
    assert "fk_criterion_scoring_runs_quality_weight_set_id" in rendered
    assert "REFERENCES quality_weight_sets (id)" in rendered


def test_the_weight_sets_upgrade_touches_no_data_at_all(
    weight_sets_upgrade_ddl: list[str],
) -> None:
    """DIE Zusage dieser Migration: Ohne eine einzige Zeile gelten die Startwerte aus
    `quality.py`. Ein eingeschriebener Vorgabewert waere von einer uebernommenen Anpassung nicht
    mehr zu unterscheiden."""
    rendered = " ".join(weight_sets_upgrade_ddl).upper()

    assert "INSERT " not in rendered
    assert "UPDATE " not in rendered
    assert "DELETE " not in rendered


def test_the_weight_sets_downgrade_renders_for_postgres_too() -> None:
    """Die REIHENFOLGE ist tragend: erst der Fremdschluessel der Laufspalte, dann die Spalte, dann
    die Eintraege, dann die Fassungen - andersherum haengt ein Fremdschluessel in der Luft."""
    statements = _render_postgres_ddl(_WEIGHT_SETS_REVISION, direction="downgrade")

    rendered = " ".join(statements)
    positions = [
        rendered.index("DROP CONSTRAINT fk_criterion_scoring_runs_quality_weight_set_id"),
        rendered.upper().index("DROP COLUMN QUALITY_WEIGHT_SET_ID"),
        rendered.index("DROP TABLE quality_weight_entries"),
        rendered.index("DROP TABLE quality_weight_sets"),
    ]

    assert positions == sorted(positions)


# specs/features/0374-duplikate-vergleichen.md: die neue Tabelle `photo_duplicate_decisions`.
# Zwei Klassen von Fehlern haengen hier, die SQLite strukturell nicht sehen kann: der native
# Enum-Typ (ohne `native_enum=False` legte Postgres einen echten Typ an, und jeder weitere Wert
# brauchte kuenftig eine Migration statt nur einen Eintrag im Python-Enum) und ein
# unbeabsichtigter Server-Default auf `decision` - unter SQLite bliebe beides unsichtbar, waehrend
# der Backend-Container `alembic upgrade head` VOR dem Serverstart ausfuehrt.

_DUPLICATE_DECISION_REVISION = "e3f4a5b6c7d8_duplikat_entscheidung.py"


@pytest.fixture(scope="module")
def duplicate_decision_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_DUPLICATE_DECISION_REVISION)


def test_the_decision_column_renders_as_a_plain_varchar_without_a_native_enum_type(
    duplicate_decision_upgrade_ddl: list[str],
) -> None:
    """Unter SQLite ist jeder Enum ein VARCHAR - ein Auseinanderlaufen von Modell- und
    Migrationsseite bliebe dort bis zur Produktion unsichtbar. Ein echter Postgres-Enum-Typ
    verlangte fuer jeden kuenftigen Wert ein `ALTER TYPE`."""
    statement = _create_table_statement(duplicate_decision_upgrade_ddl, "photo_duplicate_decisions")
    decision_line = next(
        line for line in statement.splitlines() if line.strip().startswith("decision")
    )

    assert "VARCHAR(16)" in decision_line.upper()
    assert "NOT NULL" in decision_line.upper()
    # Auflage S12: Die Abwesenheit der Zeile heisst "nicht entschieden".
    assert "DEFAULT" not in decision_line.upper()
    # Kein DB-seitiger Wertevorrat - die Spalte ist eine Zeichenkette, und genau deshalb prueft das
    # Ueberlebenden-Praedikat POSITIV auf `keep` statt negativ auf `discard` (Auflage S2).
    assert "CHECK" not in statement.upper()


def test_the_decision_primary_key_and_foreign_key_both_sit_on_photo_id(
    duplicate_decision_upgrade_ddl: list[str],
) -> None:
    """Auflage S11: Beide auf derselben Spalte - "hoechstens eine Entscheidung je Foto" braucht
    dadurch keinen eigenen Unique-Constraint, und der echte Fremdschluessel haelt die Tabelle in
    der Erreichbarkeitspruefung der Projektloeschung."""
    statement = _create_table_statement(duplicate_decision_upgrade_ddl, "photo_duplicate_decisions")

    assert "PRIMARY KEY (photo_id)" in statement
    assert "CONSTRAINT fk_photo_duplicate_decisions_photo_id FOREIGN KEY(photo_id)" in statement
    assert "REFERENCES photos (id)" in statement


def test_the_duplicate_decision_table_carries_no_user_reference_at_all(
    duplicate_decision_upgrade_ddl: list[str],
) -> None:
    """ADR 0104 Punkt 2: Die Entscheidung ist projektweit. Es gibt keine Spalte, in der ein
    Nutzerbezug stehen koennte - die Abwesenheit ist strukturell, nicht bloss zugesichert."""
    statement = _create_table_statement(duplicate_decision_upgrade_ddl, "photo_duplicate_decisions")

    assert "user_id" not in statement
    assert "decided_by" not in statement
    assert "users" not in statement


def test_the_duplicate_decision_upgrade_touches_no_data_at_all(
    duplicate_decision_upgrade_ddl: list[str],
) -> None:
    rendered = " ".join(duplicate_decision_upgrade_ddl).upper()
    assert "INSERT " not in rendered
    assert "UPDATE " not in rendered
    assert "DELETE " not in rendered


def test_the_duplicate_decision_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_DUPLICATE_DECISION_REVISION, direction="downgrade")

    rendered = " ".join(statements)
    assert "DROP TABLE photo_duplicate_decisions" in rendered


# specs/features/0434-ortsnamen-fuer-events.md, Teil 2: die Ortsauskunft. Zwei Fehlerklassen
# haengen hier, die SQLite strukturell nicht zeigt - die Gleitkomma-Spalten des Zellschluessels
# (dort sind INTEGER und DOUBLE PRECISION dasselbe, und genau an diesen beiden Werten haengt der
# Treffer eines abgelegten Eintrags) und der mehrspaltige `UniqueConstraint`, der die
# Wiederverwendung der Auskunft traegt.

_ORTSAUSKUNFT_REVISION = "d7e8f9a0b1c2_ortsauskunft.py"


@pytest.fixture(scope="module")
def ortsauskunft_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_ORTSAUSKUNFT_REVISION)


def test_the_cell_key_renders_as_two_float_columns(ortsauskunft_upgrade_ddl: list[str]) -> None:
    """Der Schluessel der Auskunft IST das gerundete Zahlenpaar - eine Ganzzahlspalte machte aus
    jeder Zelle denselben Eintrag."""
    statement = _create_table_statement(ortsauskunft_upgrade_ddl, "place_lookups")

    for column in ("cell_lat", "cell_lon"):
        line = next(line for line in statement.splitlines() if line.strip().startswith(column))
        assert "FLOAT" in line.upper() or "DOUBLE PRECISION" in line.upper(), line
        assert "NOT NULL" in line.upper(), line
        assert "DEFAULT" not in line.upper(), line


def test_the_unique_constraint_spans_project_and_both_cell_columns(
    ortsauskunft_upgrade_ddl: list[str],
) -> None:
    """Dieselbe Zelle in einem ZWEITEN Projekt ist eine eigene Zeile - der Constraint traegt
    `project_id` deshalb mit, und die Auskunft des einen Projekts wird fuer das andere nie
    gelesen (S6)."""
    statement = _create_table_statement(ortsauskunft_upgrade_ddl, "place_lookups")

    assert "UNIQUE (project_id, cell_lat, cell_lon)" in statement
    assert "FOREIGN KEY(project_id) REFERENCES projects (id)" in statement


def test_the_resolution_timestamp_is_zoneless(ortsauskunft_upgrade_ddl: list[str]) -> None:
    """Alle Zeitstempel des Projekts sind zonenlos (ADR 0090, Punkt 4)."""
    statement = _create_table_statement(ortsauskunft_upgrade_ddl, "place_lookups").upper()

    assert "RESOLVED_AT TIMESTAMP WITHOUT TIME ZONE NOT NULL" in statement
    assert "WITH TIME ZONE" not in statement


def test_the_event_column_is_added_nullable_and_without_a_default(
    ortsauskunft_upgrade_ddl: list[str],
) -> None:
    statement = _add_column_statement(ortsauskunft_upgrade_ddl, "place_name").upper()

    assert "VARCHAR" in statement
    assert "NOT NULL" not in statement
    assert "DEFAULT" not in statement


def test_the_ortsauskunft_upgrade_touches_no_data_at_all(
    ortsauskunft_upgrade_ddl: list[str],
) -> None:
    """Rein additiv: kein Nachziehen bestehender Laeufe, keine Datenloeschung."""
    rendered = " ".join(ortsauskunft_upgrade_ddl).upper()
    assert "INSERT " not in rendered
    assert "UPDATE " not in rendered
    assert "DELETE " not in rendered


def test_the_ortsauskunft_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_ORTSAUSKUNFT_REVISION, direction="downgrade")
    rendered = " ".join(statements).upper()

    assert "DROP COLUMN PLACE_NAME" in rendered
    assert "DROP TABLE PLACE_LOOKUPS" in rendered


# specs/features/0469-verlaessliche-sehenswuerdigkeitsnamen.md: das Namensregister. Die
# Fehlerklasse, die SQLite hier strukturell nicht zeigt, ist die JSON-Spalte des
# Einbettungsvektors - unter SQLite ist sie schlicht TEXT, unter Postgres ein eigener Typ - und der
# `server_default=func.now()` auf einer zonenlosen Zeitstempelspalte.

_NAMENSREGISTER_REVISION = "a8b9c0d1e2f3_namensregister.py"


@pytest.fixture(scope="module")
def namensregister_upgrade_ddl() -> list[str]:
    return _render_postgres_ddl(_NAMENSREGISTER_REVISION)


def test_the_embedding_renders_as_a_json_column(namensregister_upgrade_ddl: list[str]) -> None:
    statement = _create_table_statement(namensregister_upgrade_ddl, "landmark_names").upper()

    assert "EMBEDDING JSON NOT NULL" in statement


def test_the_register_is_bound_to_its_project_and_unique_per_normalised_name(
    namensregister_upgrade_ddl: list[str],
) -> None:
    """S8: echter Fremdschluessel, NOT NULL - und `project_id` IM Constraint, damit dieselbe
    Sehenswuerdigkeit in einem zweiten Projekt eine eigene Zeile ist."""
    statement = _create_table_statement(namensregister_upgrade_ddl, "landmark_names")

    assert "project_id INTEGER NOT NULL" in statement
    assert "UNIQUE (project_id, normalized_name)" in statement
    assert "FOREIGN KEY(project_id) REFERENCES projects (id)" in statement


def test_the_register_timestamp_is_zoneless(namensregister_upgrade_ddl: list[str]) -> None:
    """Alle Zeitstempel des Projekts sind zonenlos (ADR 0090, Punkt 4)."""
    statement = _create_table_statement(namensregister_upgrade_ddl, "landmark_names").upper()

    assert "CREATED_AT TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL" in statement
    assert "WITH TIME ZONE" not in statement


def test_the_locality_stays_nullable(namensregister_upgrade_ddl: list[str]) -> None:
    """Der Ortsname wirkt als SPERRE und nie als Schluessel - er darf fehlen, und genau dann
    entscheidet die Aehnlichkeit allein."""
    statement = _create_table_statement(namensregister_upgrade_ddl, "landmark_names")

    assert "locality VARCHAR, \n" in statement or "locality VARCHAR," in statement
    assert "locality VARCHAR NOT NULL" not in statement


def test_the_canonical_name_column_is_added_nullable_and_without_a_default(
    namensregister_upgrade_ddl: list[str],
) -> None:
    statement = _add_column_statement(namensregister_upgrade_ddl, "canonical_name").upper()

    assert "VARCHAR" in statement
    assert "NOT NULL" not in statement
    assert "DEFAULT" not in statement


def test_the_namensregister_upgrade_touches_no_data_at_all(
    namensregister_upgrade_ddl: list[str],
) -> None:
    """Rein additiv: kein Nachziehen frueherer Erkennungslaeufe, keine Datenloeschung - und
    insbesondere kein Zuruecksetzen einer erteilten Cloud-Einwilligung."""
    rendered = " ".join(namensregister_upgrade_ddl).upper()
    assert "INSERT " not in rendered
    assert "UPDATE " not in rendered
    assert "DELETE " not in rendered


def test_the_namensregister_downgrade_renders_for_postgres_too() -> None:
    statements = _render_postgres_ddl(_NAMENSREGISTER_REVISION, direction="downgrade")
    rendered = " ".join(statements).upper()

    assert "DROP COLUMN CANONICAL_NAME" in rendered
    assert "DROP TABLE LANDMARK_NAMES" in rendered
