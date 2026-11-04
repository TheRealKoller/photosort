"""Spec 0609 / ADR 0138 - die HTTP-Grenze zum Eye-Sidecar gegen einen `httpx.MockTransport`."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

import httpx
import pytest

from photosort.eye_client import (
    EYE_MAX_RESPONSE_BYTES,
    EyeHttpClient,
    EyeImageUnreadableError,
    EyeServiceUnavailableError,
)

CHUNK = 64 * 1024


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> EyeHttpClient:
    return EyeHttpClient("http://eye.test", transport=httpx.MockTransport(handler))


class _CountingBody:
    """Ein Antwortkoerper aus gleich grossen Chunks, der mitzaehlt, wie viele gezogen wurden."""

    def __init__(self, chunks: int, *, explode_after: int | None = None) -> None:
        self._chunks = chunks
        self._explode_after = explode_after
        self.pulled = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for _ in range(self._chunks):
            if self._explode_after is not None and self.pulled >= self._explode_after:
                raise AssertionError("Der Koerper wurde ueber den Deckel hinaus gelesen")
            self.pulled += 1
            yield b"x" * CHUNK


async def test_analyze_returns_the_parsed_object() -> None:
    client = _client(lambda request: httpx.Response(200, json={"kind": "landscape"}))

    assert await client.analyze(b"\xff\xd8\xff") == {"kind": "landscape"}
    await client.aclose()


async def test_analyze_sends_the_jpeg_bytes_to_analyze() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        seen["content_type"] = request.headers["content-type"]
        seen["body"] = request.content
        return httpx.Response(200, json={})

    client = _client(handler)
    await client.analyze(b"\xff\xd8\xff")
    await client.aclose()

    assert seen == {
        "path": "/analyze",
        "method": "POST",
        "content_type": "image/jpeg",
        "body": b"\xff\xd8\xff",
    }


async def test_a_body_over_the_cap_fails() -> None:
    chunks = EYE_MAX_RESPONSE_BYTES // CHUNK + 1
    body = _CountingBody(chunks)
    client = _client(lambda request: httpx.Response(200, content=body))

    with pytest.raises(EyeServiceUnavailableError, match="zu viel geliefert"):
        await client.analyze(b"\xff\xd8\xff")
    await client.aclose()


async def test_the_body_is_not_read_past_the_cap() -> None:
    within_cap = EYE_MAX_RESPONSE_BYTES // CHUNK
    body = _CountingBody(within_cap + 50, explode_after=within_cap + 1)
    client = _client(lambda request: httpx.Response(200, content=body))

    with pytest.raises(EyeServiceUnavailableError, match="zu viel geliefert"):
        await client.analyze(b"\xff\xd8\xff")
    await client.aclose()

    assert body.pulled == within_cap + 1


async def test_a_non_200_status_is_rejected_without_reading_the_body() -> None:
    body = _CountingBody(1)
    client = _client(lambda request: httpx.Response(500, content=body))

    with pytest.raises(EyeServiceUnavailableError, match="abgelehnt"):
        await client.analyze(b"\xff\xd8\xff")
    await client.aclose()

    assert body.pulled == 0


async def test_a_422_is_an_unreadable_image_not_a_service_failure() -> None:
    client = _client(
        lambda request: httpx.Response(422, json={"error": "Das Bild ist nicht lesbar."})
    )

    with pytest.raises(EyeImageUnreadableError) as caught:
        await client.analyze(b"\xff\xd8\xff")
    await client.aclose()

    assert not isinstance(caught.value, EyeServiceUnavailableError)


@pytest.mark.parametrize("status", [400, 413, 415, 500, 503])
async def test_every_other_rejection_stays_a_service_failure(status: int) -> None:
    client = _client(lambda request: httpx.Response(status, json={"error": "x"}))

    with pytest.raises(EyeServiceUnavailableError, match="abgelehnt"):
        await client.analyze(b"\xff\xd8\xff")
    await client.aclose()


@pytest.mark.parametrize("content", [b"kein json", b"[1, 2]"])
async def test_an_unreadable_body_fails(content: bytes) -> None:
    client = _client(lambda request: httpx.Response(200, content=content))

    with pytest.raises(EyeServiceUnavailableError, match="nicht lesbar"):
        await client.analyze(b"\xff\xd8\xff")
    await client.aclose()


async def test_a_transport_error_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("weg", request=request)

    client = _client(handler)

    with pytest.raises(EyeServiceUnavailableError, match="nicht erreichbar"):
        await client.analyze(b"\xff\xd8\xff")
    await client.aclose()


@pytest.mark.parametrize(("status", "healthy"), [(200, True), (503, False)])
async def test_health_judges_only_the_status_and_never_reads_the_body(
    status: int, healthy: bool
) -> None:
    body = _CountingBody(1)
    client = _client(lambda request: httpx.Response(status, content=body))

    assert await client.health() is healthy
    await client.aclose()

    assert body.pulled == 0


async def test_health_is_false_on_a_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("weg", request=request)

    client = _client(handler)

    assert await client.health() is False
    await client.aclose()
