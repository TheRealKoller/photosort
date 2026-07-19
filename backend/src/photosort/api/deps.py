from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from photosort.config import settings
from photosort.db import get_session
from photosort.opencloud.client import OpenCloudClient

__all__ = ["get_session", "get_opencloud_client", "get_job_enqueuer", "JobEnqueuer"]


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
