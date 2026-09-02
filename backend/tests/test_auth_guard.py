import re
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api import opencloud, projects, stats
from photosort.config import settings
from photosort.models import User
from photosort.security import ALGORITHM, create_access_token, hash_password


async def test_protected_endpoint_rejects_missing_token(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/projects")

    assert response.status_code == 401


async def test_protected_endpoint_accepts_valid_token(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.get("/projects")

    assert response.status_code == 200


async def test_protected_endpoint_rejects_expired_token(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    user = User(username="testuser", password_hash=hash_password("irrelevant"))
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    now = datetime.now(UTC)
    expired_token = jwt.encode(
        {
            "sub": str(user.id),
            "username": user.username,
            "iat": now - timedelta(days=31),
            "exp": now - timedelta(days=1),
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )

    response = await api_client.get(
        "/projects", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401


async def test_protected_endpoint_rejects_wrong_signature(api_client: httpx.AsyncClient) -> None:
    now = datetime.now(UTC)
    forged_token = jwt.encode(
        {"sub": "1", "username": "daniel", "iat": now, "exp": now + timedelta(days=30)},
        "totally-not-the-real-secret-key",
        algorithm=ALGORITHM,
    )

    response = await api_client.get(
        "/projects", headers={"Authorization": f"Bearer {forged_token}"}
    )

    assert response.status_code == 401


async def test_protected_endpoint_rejects_alg_none_token(api_client: httpx.AsyncClient) -> None:
    now = datetime.now(UTC)
    none_alg_token = jwt.encode(
        {"sub": "1", "username": "daniel", "iat": now, "exp": now + timedelta(days=30)},
        key="",
        algorithm="none",
    )

    response = await api_client.get(
        "/projects", headers={"Authorization": f"Bearer {none_alg_token}"}
    )

    assert response.status_code == 401


async def test_protected_endpoint_rejects_non_numeric_sub_claim(
    api_client: httpx.AsyncClient,
) -> None:
    now = datetime.now(UTC)
    malformed_token = jwt.encode(
        {"sub": "not-a-number", "username": "daniel", "iat": now, "exp": now + timedelta(days=30)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )

    response = await api_client.get(
        "/projects", headers={"Authorization": f"Bearer {malformed_token}"}
    )

    assert response.status_code == 401


async def test_protected_endpoint_rejects_token_for_deleted_user(
    api_client: httpx.AsyncClient,
) -> None:
    ghost_user = User(id=999999, username="ghost", password_hash="irrelevant")
    token = create_access_token(ghost_user)

    response = await api_client.get("/projects", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


async def test_health_remains_public(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200


async def test_login_remains_public(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/auth/login", json={"username": "unknown", "password": "wrong"}
    )

    assert response.status_code == 401  # nicht 401 wegen fehlendem Token, sondern falscher Login


def _protected_router_operations() -> list[tuple[str, str]]:
    # Direkt ueber die APIRouter-Objekte statt ueber app.routes iteriert - robuster gegenueber
    # FastAPI-internen Repraesentationen von eingebundenen Routern (_IncludedRouter u.ae.).
    operations: list[tuple[str, str]] = []
    # specs/features/0207-projekt-statistikseite.md: `stats.router` ist hier ergaenzt, sonst
    # gaelte die 401-Vollstaendigkeitsgarantie fuer den neuen Router nicht - und die Absicherung
    # eines kuenftigen zweiten Stats-Endpunkts haenge allein daran, dass niemand die Dependency
    # vergisst.
    for router in (projects.router, opencloud.router, stats.router):
        for route in router.routes:
            path = getattr(route, "path", "")
            # Platzhalter durch einen harmlosen konkreten Wert ersetzen, damit die Anfrage
            # sauber geroutet wird - der 401 muss unabhaengig vom Pfadparameter kommen.
            concrete_path = re.sub(r"\{[^}]+\}", "1", path)
            methods = getattr(route, "methods", None) or set()
            for method in methods:
                if method == "HEAD":
                    continue
                operations.append((method, concrete_path))
    return operations


@pytest.mark.parametrize("method,path", _protected_router_operations())
async def test_all_project_opencloud_and_stats_routes_require_token(
    api_client: httpx.AsyncClient, method: str, path: str
) -> None:
    response = await api_client.request(method, path)

    assert response.status_code == 401
