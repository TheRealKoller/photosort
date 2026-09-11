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
