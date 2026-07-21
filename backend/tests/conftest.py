import os

# Muss vor jedem "photosort.*"-Import gesetzt werden: main.py verweigert den Start bei einem zu
# kurzen/Platzhalter-secret_key (siehe security-Startup-Guard, specs/features/0006-auth.md), und
# der Rate-Limiter soll in Tests ohne echtes Redis auskommen (architecture/0002-testkonzept.md).
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production-use")
os.environ.setdefault("RATE_LIMIT_STORAGE_URI", "memory://")

from collections.abc import AsyncIterator, Iterator  # noqa: E402

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
