from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from photosort.config import settings


class Base(DeclarativeBase):
    pass


def enable_sqlite_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
    """Setzt `PRAGMA foreign_keys=ON` fuer JEDE neue DBAPI-Verbindung einer SQLite-Engine.

    SQLite setzt Fremdschluessel nur bei gesetztem Pragma durch, und zwar JE VERBINDUNG; Postgres
    setzt sie immer durch. Ohne diesen Handler waere die Testdatenbank nachsichtiger als die
    Zieldatenbank: eine fehlende ORM-Kaskade, eine falsche Loeschreihenfolge und eine verwaiste
    Kindzeile blieben unsichtbar (Spec 0350, ADR 0122).

    Bewusst eine benannte, oeffentliche Funktion statt eines Lambdas: `tests/test_seed.py` baut
    seine synchrone Engine selbst und schliesst denselben Handler an, damit die Durchsetzung
    suiteweit ueber den EINEN Punkt laeuft. Die Migrationstests bauen ihre reduzierte Schemastufe
    weiterhin ohne Handler - das ist der Zweck ihrer Ausnahme."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_engine(database_url: str) -> AsyncEngine:
    engine = create_async_engine(database_url)
    # Nur SQLite braucht den Handler; eine Postgres-Engine bliebe sonst mit einem `connect`-Handler
    # versehen, der ein SQLite-Pragma absetzt.
    if engine.dialect.name == "sqlite":
        event.listen(engine.sync_engine, "connect", enable_sqlite_foreign_keys)
    return engine


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


engine = make_engine(settings.database_url)
async_session_factory = make_session_factory(engine)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
