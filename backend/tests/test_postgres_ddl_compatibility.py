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
        statement
        for statement in classification_run_upgrade_ddl
        if "cloud_requested" in statement
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
