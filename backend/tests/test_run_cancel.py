"""Der kooperative Abbruch: Merker-Lesung, Kontext-Token und unterbrechbare Wartezeiten.

Kein Test wartet auf die Wanduhr. Der Test-`sleep` des Schrittmachers blockiert auf einem
`asyncio.Event`, das nie freigegeben wird - endet das Warten trotzdem, hat der Abbruch es beendet.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.cloud_vision as cloud_vision
from photosort.db import make_session_factory
from photosort.models import Project, ScanRun, ScanStatus
from photosort.run_cancel import (
    CancelToken,
    RunCancelled,
    cancel_requested,
    current_cancel_token,
    watch_cancel_requests,
)


class _BlockingSleep:
    """Ein `sleep`, der erst endet, wenn der Test ihn freigibt - zaehlt begonnene Wartezeiten."""

    def __init__(self) -> None:
        self.calls: list[float] = []
        self.release = asyncio.Event()
        self.entered = asyncio.Event()

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        self.entered.set()
        await self.release.wait()


class _ApiError(Exception):
    pass


class _CountingTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        entry = self._responses[min(len(self.requests) - 1, len(self._responses) - 1)]
        return httpx.Response(entry.status_code, headers=entry.headers, request=request)


async def _scan_run(session: AsyncSession) -> ScanRun:
    project = Project(name="Costa Rica", opencloud_drive_id="drive-1", opencloud_path="/a")
    session.add(project)
    await session.flush()
    run = ScanRun(project_id=project.id, status=ScanStatus.RUNNING)
    session.add(run)
    await session.commit()
    return run


class TestCancelRequested:
    async def test_is_false_without_a_request(self, db_session: AsyncSession) -> None:
        run = await _scan_run(db_session)

        assert await cancel_requested(db_session, run) is False

    async def test_reads_the_flag_fresh_from_the_database(self, db_session: AsyncSession) -> None:
        """Gesetzt von einer ZWEITEN Session - der Stand im Objekt der ersten bleibt alt."""
        run = await _scan_run(db_session)
        other_factory = make_session_factory(db_session.bind)
        async with other_factory() as other:
            other_run = await other.get(ScanRun, run.id)
            assert other_run is not None
            other_run.cancel_requested_at = datetime(2030, 1, 1)
            await other.commit()

        assert run.cancel_requested_at is None
        assert await cancel_requested(db_session, run) is True


class TestTheThrottleWaitIsInterruptible:
    async def test_a_cancel_ends_the_throttle_wait_without_finishing_it(self) -> None:
        sleep = _BlockingSleep()
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=60.0, clock=lambda: 0.0, sleep=sleep
        )
        token = CancelToken()
        reset = current_cancel_token.set(token)
        try:
            await throttle.acquire()
            waiting = asyncio.create_task(throttle.acquire())
            await sleep.entered.wait()
            token.event.set()

            with pytest.raises(RunCancelled):
                await waiting
        finally:
            current_cancel_token.reset(reset)

        assert sleep.calls == [60.0]
        assert not sleep.release.is_set()

    async def test_an_already_requested_cancel_does_not_start_the_wait(self) -> None:
        sleep = _BlockingSleep()
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=60.0, clock=lambda: 0.0, sleep=sleep
        )
        token = CancelToken()
        token.event.set()
        reset = current_cancel_token.set(token)
        try:
            await throttle.acquire()
            with pytest.raises(RunCancelled):
                await throttle.acquire()
        finally:
            current_cancel_token.reset(reset)

        assert sleep.calls == []

    async def test_without_a_token_the_wait_runs_to_its_end(self) -> None:
        sleep = _BlockingSleep()
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=60.0, clock=lambda: 0.0, sleep=sleep
        )
        await throttle.acquire()
        waiting = asyncio.create_task(throttle.acquire())
        await sleep.entered.wait()
        sleep.release.set()

        await waiting

        assert sleep.calls == [60.0]

    async def test_a_worker_cancellation_still_passes_through_the_wait(self) -> None:
        """Timeout und Shutdown bleiben ein `CancelledError` - nie in `RunCancelled` gewandelt."""
        sleep = _BlockingSleep()
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=60.0, clock=lambda: 0.0, sleep=sleep
        )
        reset = current_cancel_token.set(CancelToken())
        try:
            await throttle.acquire()
            waiting = asyncio.create_task(throttle.acquire())
            await sleep.entered.wait()
            waiting.cancel()

            with pytest.raises(asyncio.CancelledError):
                await waiting
        finally:
            current_cancel_token.reset(reset)


class TestTheRetryWaitIsInterruptible:
    async def test_a_cancel_during_the_429_wait_sends_no_further_request(self) -> None:
        sleep = _BlockingSleep()
        throttle = cloud_vision.CloudRequestThrottle(
            min_interval_seconds=0.0, clock=lambda: 0.0, sleep=sleep
        )
        transport = _CountingTransport([httpx.Response(429), httpx.Response(200)])
        token = CancelToken()
        reset = current_cancel_token.set(token)
        try:
            async with httpx.AsyncClient(transport=transport) as client:
                posting = asyncio.create_task(
                    cloud_vision.post_vision_request(
                        client,
                        cloud_vision.ANTHROPIC_ENDPOINT,
                        {"model": "irrelevant"},
                        error_class=_ApiError,
                        throttle=throttle,
                    )
                )
                await sleep.entered.wait()
                token.event.set()

                with pytest.raises(RunCancelled):
                    await posting
        finally:
            current_cancel_token.reset(reset)

        assert len(transport.requests) == 1


class TestWatchCancelRequests:
    async def test_the_watcher_sets_the_event_once_the_flag_is_written(
        self, db_session: AsyncSession
    ) -> None:
        run = await _scan_run(db_session)
        factory = make_session_factory(db_session.bind)

        async with watch_cancel_requests(factory, ScanRun, run.id, interval_seconds=0.0) as token:
            assert current_cancel_token.get() is token
            assert not token.event.is_set()
            run.cancel_requested_at = datetime(2030, 1, 1)
            await db_session.commit()
            await asyncio.wait_for(token.event.wait(), timeout=5)

        assert current_cancel_token.get() is None

    async def test_the_token_is_cleared_after_the_run_even_on_an_error(
        self, db_session: AsyncSession
    ) -> None:
        run = await _scan_run(db_session)
        factory = make_session_factory(db_session.bind)

        with pytest.raises(ValueError):
            async with watch_cancel_requests(factory, ScanRun, run.id, interval_seconds=0.0):
                raise ValueError("Lauf scheitert")

        assert current_cancel_token.get() is None
