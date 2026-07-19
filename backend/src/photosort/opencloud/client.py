from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from types import TracebackType
from typing import Any
from urllib.parse import quote, unquote, urlparse

import httpx

from photosort.opencloud.webdav_xml import DavEntry, parse_multistatus

_PROPFIND_BODY = (
    b'<?xml version="1.0"?>'
    b'<d:propfind xmlns:d="DAV:">'
    b"<d:prop>"
    b"<d:resourcetype/><d:getetag/><d:getlastmodified/><d:getcontentlength/>"
    b"</d:prop>"
    b"</d:propfind>"
)


class OpenCloudError(Exception):
    """Raised for any failure talking to OpenCloud (auth, network, missing folder, ...)."""


@dataclass(frozen=True)
class Drive:
    id: str
    name: str
    drive_type: str
    webdav_url: str


def _join(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    segments = [quote(segment) for segment in path.strip("/").split("/") if segment]
    return "/".join([base, *segments]) if segments else base


def _raise_for_status(response: httpx.Response, *, not_found_message: str | None = None) -> None:
    if response.status_code == 404 and not_found_message:
        raise OpenCloudError(not_found_message)
    if response.status_code >= 400:
        raise OpenCloudError(
            f"OpenCloud-Anfrage fehlgeschlagen: {response.status_code} {response.reason_phrase}"
        )


class OpenCloudClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        app_token: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            auth=(username, app_token), transport=transport, timeout=timeout
        )

    async def __aenter__(self) -> OpenCloudClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise OpenCloudError(f"OpenCloud nicht erreichbar: {exc}") from exc

    async def list_drives(self) -> list[Drive]:
        response = await self._send("GET", f"{self._base_url}/graph/v1.0/me/drives")
        _raise_for_status(response)
        payload = response.json()
        return [
            Drive(
                id=item["id"],
                name=item["name"],
                drive_type=item.get("driveType", ""),
                webdav_url=item["webDavUrl"],
            )
            for item in payload.get("value", [])
        ]

    async def resolve_drive(self, name: str | None) -> Drive:
        drives = await self.list_drives()
        if not drives:
            raise OpenCloudError("Keine OpenCloud-Spaces gefunden.")

        if name:
            for drive in drives:
                if drive.name == name:
                    return drive
            raise OpenCloudError(f"OpenCloud-Space '{name}' wurde nicht gefunden.")

        for drive in drives:
            if drive.drive_type == "personal":
                return drive
        return drives[0]

    async def list_folder(
        self, webdav_url: str, path: str = "", depth: str = "1"
    ) -> list[DavEntry]:
        target_url = _join(webdav_url, path)
        response = await self._send(
            "PROPFIND",
            target_url,
            headers={"Depth": depth, "Content-Type": "application/xml"},
            content=_PROPFIND_BODY,
        )
        _raise_for_status(
            response, not_found_message=f"Ordner '{path}' wurde auf OpenCloud nicht gefunden."
        )

        entries = parse_multistatus(response.content)
        target_path = unquote(urlparse(target_url).path).rstrip("/")
        return [entry for entry in entries if unquote(entry.href).rstrip("/") != target_path]

    async def walk(
        self, webdav_url: str, root_path: str
    ) -> AsyncIterator[tuple[str, DavEntry]]:
        queue: deque[str] = deque([root_path.strip("/")])
        while queue:
            current = queue.popleft()
            for entry in await self.list_folder(webdav_url, current):
                child_relative = f"{current}/{entry.name}" if current else entry.name
                if entry.is_collection:
                    queue.append(child_relative)
                else:
                    yield child_relative, entry

    async def get_range(self, webdav_url: str, relative_path: str, length: int) -> bytes:
        url = _join(webdav_url, relative_path)
        response = await self._send("GET", url, headers={"Range": f"bytes=0-{length - 1}"})
        _raise_for_status(response)
        return response.content
