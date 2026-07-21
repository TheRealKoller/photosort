import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import User
from photosort.security import hash_password


async def _create_user(session: AsyncSession, username: str, password: str) -> User:
    user = User(username=username, password_hash=hash_password(password))
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def test_login_with_correct_credentials_returns_token(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session, "daniel", "correct horse battery staple")
    await db_session.commit()

    response = await api_client.post(
        "/auth/login", json={"username": "daniel", "password": "correct horse battery staple"}
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["access_token"], str) and body["access_token"] != ""
    assert body["token_type"] == "bearer"


async def test_login_with_wrong_password_returns_401(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session, "daniel", "correct horse battery staple")
    await db_session.commit()

    response = await api_client.post(
        "/auth/login", json={"username": "daniel", "password": "wrong password"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Ungültige Anmeldedaten"


async def test_login_with_unknown_username_returns_identical_401(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session, "daniel", "correct horse battery staple")
    await db_session.commit()

    wrong_password_response = await api_client.post(
        "/auth/login", json={"username": "daniel", "password": "wrong password"}
    )
    unknown_user_response = await api_client.post(
        "/auth/login", json={"username": "unknown-user", "password": "wrong password"}
    )

    assert unknown_user_response.status_code == wrong_password_response.status_code == 401
    assert unknown_user_response.json() == wrong_password_response.json()


async def test_login_with_unknown_username_still_runs_dummy_verification(
    api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake_verify_dummy_password(password: str) -> None:
        calls.append(password)

    monkeypatch.setattr(
        "photosort.api.auth.verify_dummy_password", fake_verify_dummy_password
    )

    response = await api_client.post(
        "/auth/login", json={"username": "unknown-user", "password": "some-password"}
    )

    assert response.status_code == 401
    assert calls == ["some-password"]


async def test_login_rejects_username_over_max_length(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/auth/login", json={"username": "x" * 129, "password": "irrelevant"}
    )

    assert response.status_code == 422


async def test_login_rejects_password_over_max_length(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/auth/login", json={"username": "daniel", "password": "x" * 129}
    )

    assert response.status_code == 422


async def test_login_rate_limits_after_five_attempts_per_ip(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    await _create_user(db_session, "daniel", "correct horse battery staple")
    await db_session.commit()

    for _ in range(5):
        response = await api_client.post(
            "/auth/login", json={"username": "daniel", "password": "wrong"}
        )
        assert response.status_code == 401

    sixth_response = await api_client.post(
        "/auth/login", json={"username": "daniel", "password": "wrong"}
    )

    assert sixth_response.status_code == 429
