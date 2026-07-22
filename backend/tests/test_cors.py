import httpx
import pytest

from photosort.config import settings
from photosort.main import app


async def test_allowed_origin_receives_access_control_allow_origin_header() -> None:
    # Sicherheits-Haertung (specs/features/0005-minimal-project-frontend.md,
    # architecture/0003-securitykonzept.md): ohne CORSMiddleware koennte jede beliebige Website
    # Anfragen an die API stellen; die konfigurierte Frontend-Origin muss aber weiterhin
    # funktionieren, sobald sie aus dem Browser die API aufruft.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health", headers={"Origin": "http://localhost:5173"}
        )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_disallowed_origin_does_not_receive_access_control_allow_origin_header() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health", headers={"Origin": "https://evil.example.com"}
        )

    assert "access-control-allow-origin" not in response.headers


async def test_preflight_request_for_allowed_origin_is_permitted() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/projects",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_cors_does_not_allow_credentials() -> None:
    # Bearer-Token-Transport statt Cookies (decisions/0005-auth-implementation.md) - kein
    # allow_credentials noetig, siehe architecture/0003-securitykonzept.md.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health", headers={"Origin": "http://localhost:5173"}
        )

    assert "access-control-allow-credentials" not in response.headers


def test_settings_expose_the_origins_actually_wired_into_the_middleware() -> None:
    assert "http://localhost:5173" in settings.cors_allowed_origins_list()


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://localhost:8080"])
async def test_both_default_dev_origins_are_allowed(origin: str) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health", headers={"Origin": origin})

    assert response.headers["access-control-allow-origin"] == origin
