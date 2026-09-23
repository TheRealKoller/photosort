"""specs/features/0350-fremdschluessel-testsuite.md / ADR 0122 - die Durchsetzung wird belegt,
nicht behauptet.

SQLite setzt Fremdschluessel nur bei gesetztem `PRAGMA foreign_keys` durch, und zwar JE
DBAPI-VERBINDUNG. Dieses Modul prueft (AK1, AK2):

- das Pragma unmittelbar an einer ueber `make_engine` gebauten Engine - auch auf einer zweiten,
  gleichzeitig offenen Verbindung derselben Engine (der Punkt der "je Verbindung"-Auflage);
- die Ablehnung einer verwaisten Kindzeile samt Gegenprobe OHNE Pragma, damit der Nachweis nicht
  an einer Behauptung haengt;
- dass die Nicht-SQLite-Engine den `connect`-Handler nicht traegt;
- und als Quelltext-Waechter, dass `create_async_engine` ausserhalb von `db.py` nicht vorkommt und
  die Dateien, die eine Engine selbst bauen, genau die Allowliste sind.

Die Allowliste ist TRAGEND und keine blosse Momentaufnahme: jede weitere async-Engine entstuende
an der Durchsetzung vorbei, ohne dass ein Verhaltenstest das bemerkte, und die Migrationstests
bauen ihren reduzierten Schemastand bewusst OHNE Pragma nach - eine Kategorie-Ausnahme wuerde
ihnen das nehmen. Deshalb steht hier `test_foreign_keys.py` selbst NICHT in der Liste, und die
Gegenprobe entfernt den Handler statt eine zweite Engine zu bauen.
"""

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.db import (
    Base,
    enable_sqlite_foreign_keys,
    make_engine,
    make_session_factory,
)
from photosort.models import Event

_BACKEND_WURZEL = Path(__file__).resolve().parent.parent
_ZEITPUNKT = datetime(2024, 1, 1)


def _kindzeile_ohne_elternteil() -> Event:
    """Ein Event ohne `criterion_scoring_runs`-Zeile.

    `Event` traegt genau EINE verletzbare Zusicherung: `criterion_scoring_run_id` ist der einzige
    Fremdschluessel und die einzige Spalte ohne Default, alle uebrigen NOT-NULL-Spalten
    (`position`, `started_at`, `ended_at`) sind gefuellt. Ohne Pragma ist die Zeile gueltig,
    mit Pragma nicht."""
    return Event(
        criterion_scoring_run_id=999_999,
        position=1,
        started_at=_ZEITPUNKT,
        ended_at=_ZEITPUNKT,
    )


def _engine_bauende_dateien(aufrufe: frozenset[str]) -> set[str]:
    """Die Dateien unter `backend/`, die selbst eine Engine bauen - ueber einen der genannten
    Aufrufe.

    Ueber den Syntaxbaum statt per Textsuche: ein Treffer in einem Kommentar oder Docstring ist
    keine gebaute Engine."""
    treffer: set[str] = set()
    for pfad in _BACKEND_WURZEL.rglob("*.py"):
        if ".venv" in pfad.parts:
            continue
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if (
                isinstance(knoten, ast.Call)
                and isinstance(knoten.func, ast.Name)
                and knoten.func.id in aufrufe
            ):
                treffer.add(str(pfad.relative_to(_BACKEND_WURZEL)))
    return treffer


_ENGINE_AUFRUFE = frozenset({"create_engine", "create_async_engine"})


async def test_make_engine_enforces_foreign_keys_on_every_connection(tmp_path: Path) -> None:
    """AK1(a): `PRAGMA foreign_keys` liefert `1` - auf der ersten UND auf einer zweiten,
    gleichzeitig offenen Verbindung derselben Engine.

    Beide Verbindungen sind bewusst gleichzeitig offen: nacheinander geoeffnete Verbindungen
    kaemen aus dem Pool zurueck und waeren dieselbe DBAPI-Verbindung - die Zusage lautet aber
    "je Verbindung", und genau das prueft nur eine zweite, wirklich neue Verbindung."""
    engine = make_engine(f"sqlite+aiosqlite:///{tmp_path / 'fk.db'}")
    try:
        async with engine.connect() as erste, engine.connect() as zweite:
            assert (await erste.exec_driver_sql("PRAGMA foreign_keys")).scalar() == 1
            assert (await zweite.exec_driver_sql("PRAGMA foreign_keys")).scalar() == 1
    finally:
        await engine.dispose()


async def test_a_child_row_without_a_parent_is_rejected_only_with_the_pragma(
    db_session: AsyncSession,
) -> None:
    """AK2: Der Nachweis haengt nicht an einer Behauptung, und die Ablehnung kommt nachweislich
    vom Pragma.

    Zwei Richtungen im selben Test: die `db_session`-Fixture (Engine ueber `make_engine`) weist die
    verwaiste Zeile ab und hinterlaesst sie nicht; dieselbe Anlage OHNE Pragma geht durch und
    hinterlaesst genau die verwaiste Zeile."""
    # Richtung 1: mit Pragma. `rollback()` danach, sonst bliebe die Session im Fehlerzustand.
    db_session.add(_kindzeile_ohne_elternteil())
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
    assert (await db_session.execute(select(func.count()).select_from(Event))).scalar_one() == 0

    # Richtung 2: Gegenprobe ohne Pragma. Hier wird der EINE Unterschied zurueckgenommen -
    # derselbe Handler, dieselbe Funktion, nur nicht mehr registriert. Eine zweite Engine ueber
    # `create_engine` waere ein zweiter Bauplatz und wuerde die tragende Allowliste unten
    # aufweichen; das Entfernen des Handlers isoliert das Pragma schaerfer als Ursache.
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    event.remove(engine.sync_engine, "connect", enable_sqlite_foreign_keys)
    assert not event.contains(engine.sync_engine, "connect", enable_sqlite_foreign_keys)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with make_session_factory(engine)() as ohne_pragma:
            ohne_pragma.add(_kindzeile_ohne_elternteil())
            await ohne_pragma.commit()
            assert (
                await ohne_pragma.execute(select(func.count()).select_from(Event))
            ).scalar_one() == 1
    finally:
        await engine.dispose()


def test_the_fk_handler_is_not_registered_for_a_non_sqlite_engine() -> None:
    """AK1(c): Nicht-SQLite-Engines bleiben unangetastet - eine Postgres-Engine traegt den
    `connect`-Handler nicht.

    Die Engine wird nur konstruiert, nie verbunden: der Test braucht keine erreichbare Datenbank."""
    engine = make_engine("postgresql+psycopg://user:pw@localhost:5432/photosort")

    assert engine.dialect.name == "postgresql"
    assert not event.contains(engine.sync_engine, "connect", enable_sqlite_foreign_keys)


def test_create_async_engine_exists_only_in_db_py() -> None:
    """AK1(b), erste Haelfte: `create_async_engine` kommt ausschliesslich in `db.py` vor.

    Jede weitere async-Engine entstuende an `make_engine` und damit an der FK-Durchsetzung vorbei,
    ohne dass ein Verhaltenstest das bemerkte."""
    assert _engine_bauende_dateien(frozenset({"create_async_engine"})) == {"src/photosort/db.py"}


def _gehoert_zur_allowlist(pfad: str) -> bool:
    return (
        pfad in {"src/photosort/db.py", "tests/test_seed.py"}
        or pfad.startswith("tests/test_migration_")
        and pfad.endswith(".py")
    )


def test_the_files_building_their_own_engine_are_exactly_the_allowlist() -> None:
    """AK1(b), zweite Haelfte: Dateien, die eine Engine selbst bauen, liegen genau in der
    Allowliste `{db.py, tests/test_seed.py, tests/test_migration_*.py}` - keine ausserhalb.

    Die Allowliste ist eine KATEGORIE und keine Aufzaehlung: nicht jede Migrationstest-Datei baut
    eine Engine (`tests/test_migration_chain.py` etwa prueft die Revisionskette ohne eigene), aber
    jede, die eine baut, faellt unter sie und bleibt ohne Pragma. `tests/test_seed.py` gehoert
    dazu, weil es seine synchrone Engine selbst baut und das Pragma ueber DENSELBEN Handler setzt.

    Die zweite Zusicherung ist die Gegenrichtung: die beiden namentlichen Eintraege bauen
    tatsaechlich eine. Ohne sie waere die Durchsetzung an einer der beiden Stellen verschwunden -
    die Allowliste allein meldete das nicht."""
    bauende = _engine_bauende_dateien(_ENGINE_AUFRUFE)

    assert all(_gehoert_zur_allowlist(pfad) for pfad in bauende), sorted(bauende)
    assert {"src/photosort/db.py", "tests/test_seed.py"} <= bauende
