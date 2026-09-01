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
