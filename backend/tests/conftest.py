import os

# Muss vor jedem "photosort.*"-Import gesetzt werden: main.py verweigert den Start bei einem zu
# kurzen/Platzhalter-secret_key (siehe security-Startup-Guard, specs/features/0006-auth.md), und
# der Rate-Limiter soll in Tests ohne echtes Redis auskommen (architecture/0002-testkonzept.md).
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production-use")
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")

import socket  # noqa: E402
from collections.abc import AsyncIterator, Iterator  # noqa: E402
from typing import Any  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from photosort.api.deps import get_session  # noqa: E402
from photosort.db import Base, make_engine, make_session_factory  # noqa: E402
from photosort.main import app  # noqa: E402
from photosort.models import User  # noqa: E402
from photosort.rate_limit import limiter  # noqa: E402
from photosort.security import create_access_token, hash_password  # noqa: E402


class NetworkAccessInTestError(RuntimeError):
    """Ein Test hat versucht, eine echte Netzwerkverbindung aufzubauen.

    Eigene Klasse statt eines nackten `RuntimeError`: nur so kann ein Test die Sperre selbst
    pruefen, ohne auf eine Meldungszeichenkette zu zielen."""


@pytest.fixture(autouse=True)
def _no_network_access(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """SPERRE, keine Konvention: kein automatisierter Test erreicht je ein Netz
    (specs/features/0434-ortsnamen-fuer-events.md, Teststrategie).

    Gilt fuer JEDEN Test dieses Baums, nicht nur fuer die Ortsauflösung - jeder Fremddienst des
    Projekts (OpenCloud, beide Cloud-Vision-Anbieter, eine Ortsquelle) kommt injiziert herein und
    wird im Test durch ein Double oder einen `httpx.MockTransport` ersetzt. Ein Test, der
    stattdessen den echten Client baut, soll LAUT scheitern statt still hinauszugehen: ohne
    Sperre haengt er an einem fremden Dienst, kostet je nach Pfad Geld und gibt reale Daten ab.

    Gesperrt werden drei Wege, weil keiner die anderen abdeckt: `connect`, das ergebnis- statt
    ausnahmegetriebene `connect_ex` (ein Fehlschlag waere dort ein Rueckgabewert und ginge still
    durch) und `create_connection`, das seinen Socket selbst anlegt.

    UNBERUEHRT bleibt alles ohne echten Socket: `httpx.ASGITransport`/`MockTransport`, die
    In-Memory-SQLite und der `memory://`-Rate-Limiter."""

    def _verweigert(*args: Any, **kwargs: Any) -> Any:
        raise NetworkAccessInTestError(
            "Netzwerkzugriff aus einem automatisierten Test. Den betroffenen Fremddienst als "
            "Double oder ueber httpx.MockTransport injizieren, statt den echten Client zu bauen."
        )

    monkeypatch.setattr(socket.socket, "connect", _verweigert)
    monkeypatch.setattr(socket.socket, "connect_ex", _verweigert)
    monkeypatch.setattr(socket, "create_connection", _verweigert)
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Iterator[None]:
    # Der Limiter ist ein Modul-Singleton mit In-Memory-Storage (siehe rate_limit.py) - ohne
    # Reset zwischen Tests wuerden sich Login-Versuche verschiedener Testfaelle gegenseitig
    # beeinflussen, da alle denselben Client-IP-Schluessel benutzen.
    limiter.reset()
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = make_session_factory(engine)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authenticated_api_client(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> AsyncIterator[httpx.AsyncClient]:
    """Wie api_client, aber mit einem echten, gueltigen Bearer-Token fuer einen Testnutzer.

    get_current_user wird bewusst NICHT gemockt (anders als get_opencloud_client/
    get_job_enqueuer) - es ist interne, zu pruefende Logik, keine externe Abhaengigkeit
    (siehe architecture/0002-testkonzept.md, Abschnitt Auth).
    """
    user = User(username="testuser", password_hash=hash_password("irrelevant"))
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    token = create_access_token(user)
    api_client.headers["Authorization"] = f"Bearer {token}"
    yield api_client
