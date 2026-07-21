from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

import jwt
from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.config import settings
from photosort.db import get_session
from photosort.models import User
from photosort.opencloud.client import OpenCloudClient
from photosort.security import decode_access_token

__all__ = [
    "get_session",
    "get_opencloud_client",
    "get_job_enqueuer",
    "get_current_user",
    "JobEnqueuer",
]

_bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht authentifiziert.")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise _unauthorized() from exc

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _unauthorized() from exc

    user = await session.get(User, user_id)
    if user is None:
        raise _unauthorized()

    return user


async def get_opencloud_client() -> AsyncIterator[OpenCloudClient]:
    client = OpenCloudClient(
        settings.opencloud_base_url, settings.opencloud_username, settings.opencloud_app_token
    )
    try:
        yield client
    finally:
        await client.aclose()


class JobEnqueuer(Protocol):
    async def enqueue_job(self, function: str, *args: Any) -> Any: ...


_pool: ArqRedis | None = None


async def get_job_enqueuer() -> JobEnqueuer:
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _pool
