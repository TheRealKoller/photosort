"""Doppelgaenger, die gemeinsam wurden.

`FakeEnqueuer` traegt alle bisherigen Zusagen der drei Fassungen: die Aufrufe als
`(funktion, positionsargumente)` UND die Schluesselwort-Argumente getrennt. Wer nur die Aufrufe
prueft, liest weiter nur `calls`; das zusaetzlich mitgeschriebene `keywords` aendert keine Zusage.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from photosort.opencloud.client import Drive, OpenCloudError
from photosort.opencloud.webdav_xml import DavEntry

DRIVE = Drive(
    id="drive-1",
    name="Family",
    drive_type="project",
    webdav_url="https://x/dav/spaces/drive-1",
)


class FakeEnqueuer:
    """Zaehlt Einreihungen, statt sie auszufuehren."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.keywords: list[dict[str, Any]] = []

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((function, args))
        self.keywords.append(kwargs)


class FakeOpenCloudClient:
    """OpenCloud-Client-Doppelgaenger fuer API- und Scan-Tests.

    Die API-Seite braucht nur `resolve_drive`/`list_folder`, die Scan-Seite zusaetzlich
    `walk`/`get_range`/`download`; dieselbe Klasse traegt beides, damit es genau eine Fassung
    gibt. `fail` laesst jede Netzoperation mit dem uebergebenen Fehler scheitern.
    """

    def __init__(
        self,
        entries: list[tuple[str, DavEntry]] | None = None,
        *,
        drive: Drive | None = None,
        fail: OpenCloudError | None = None,
        file_contents: dict[str, bytes] | None = None,
        download_delay: float = 0.0,
        on_download: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._entries = [] if entries is None else entries
        self._drive = DRIVE if drive is None else drive
        self._fail = fail
        self._file_contents = {} if file_contents is None else file_contents
        self._download_delay = download_delay
        self._on_download = on_download
        self.range_requests: list[str] = []
        self.download_requests: list[str] = []
        # Nachweis echter Nebenlaeufigkeit ohne Wall-Clock-Assertion (Spec 0036): zaehlt, wie
        # viele `download()`-Aufrufe gleichzeitig "in Flight" waren.
        self._active_downloads = 0
        self.max_concurrent_downloads = 0

    async def resolve_drive(self, name: str | None) -> Drive:
        if self._fail:
            raise self._fail
        return self._drive

    async def list_folder(self, webdav_url: str, path: str, depth: str = "1") -> list[DavEntry]:
        if self._fail:
            raise self._fail
        return []

    async def walk(self, webdav_url: str, root_path: str) -> AsyncIterator[tuple[str, DavEntry]]:
        for item in self._entries:
            yield item

    async def get_range(self, webdav_url: str, relative_path: str, length: int) -> bytes:
        self.range_requests.append(relative_path)
        return self._file_contents.get(relative_path, b"")

    async def download(self, webdav_url: str, relative_path: str) -> bytes:
        self.download_requests.append(relative_path)
        self._active_downloads += 1
        self.max_concurrent_downloads = max(self.max_concurrent_downloads, self._active_downloads)
        try:
            if self._download_delay:
                await asyncio.sleep(self._download_delay)
            if self._on_download is not None:
                await self._on_download(relative_path)
            return self._file_contents.get(relative_path, b"")
        finally:
            self._active_downloads -= 1
