from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from types import TracebackType
from typing import Any
from urllib.parse import quote, unquote, urlparse
from xml.etree import ElementTree

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


# specs/features/0050-dateianzahl-im-ordner-browser.md: umgezogen von worker.py::_IMAGE_EXTENSIONS
# (dort ehemals privat) - api/opencloud.py darf worker.py nicht importieren (zieht dessen schwere
# mediapipe-/tensorflow-Abhaengigkeiten in den API-Request-Pfad, siehe ADR
# decisions/0028-ordner-browser-bilddatei-zaehlung.md Punkt 3), client.py ist dagegen der bereits
# heute gemeinsame, leichte Baustein fuer beide Konsumenten.
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}


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
    raw_segments = [segment for segment in path.strip("/").split("/") if segment]
    # Security-Haertung (specs/features/0005-minimal-project-frontend.md,
    # architecture/0003-securitykonzept.md): ohne diese Pruefung wuerde ein "..''-Segment aus
    # dem vorgesehenen Projekt-Wurzelverzeichnis herauslaufen und andere, ueber WebDAV
    # erreichbare Bereiche des Namespace ansprechen, als die Anwendung vorsieht. Betrifft jeden
    # Aufrufer mit nutzergesteuertem Pfad (list_folder/get_range/walk), da alle ueber _join laufen.
    if any(segment == ".." for segment in raw_segments):
        raise OpenCloudError(f"Ungültiger Pfad: '{path}' enthält nicht erlaubte '..'-Segmente.")
    segments = [quote(segment) for segment in raw_segments]
    return "/".join([base, *segments]) if segments else base


def _raise_for_status(response: httpx.Response, *, not_found_message: str | None = None) -> None:
    if response.status_code == 404 and not_found_message:
        raise OpenCloudError(not_found_message)
    if response.status_code >= 400:
        raise OpenCloudError(
            f"OpenCloud-Anfrage fehlgeschlagen: {response.status_code} {response.reason_phrase}"
        )


def _drive_from_graph_api_item(item: Any) -> Drive:
    # Baut ein einzelnes Drive-Objekt aus einem Eintrag der Graph-API-Antwort
    # (GET /graph/v1.0/me/drives, Feld "value"). "webDavUrl" liegt dabei verschachtelt unter
    # "root", nicht auf oberster Ebene des Drive-Objekts - empirisch gegen einen echten
    # OpenCloud-Server verifiziert (siehe specs/roadmap.md, "[Bug bestaetigt]"-Eintrag
    # 2026-08-02; dieselbe Struktur wird bereits in
    # scripts/seed-opencloud-demo.py::_drive_webdav_url korrekt gehandhabt).
    #
    # item ist bewusst nicht als dict[str, Any] typisiert: die gesamte Funktion behandelt jede
    # unerwartete Struktur (item selbst kein dict, fehlende Pflichtfelder, "root" kein dict) als
    # gleichwertigen Fall - ein KeyError/TypeError/AttributeError an irgendeiner Stelle hier soll
    # immer als OpenCloudError propagieren, nie als roher, von api/opencloud.py::browse_folder
    # unabgefangener Python-Fehler (der sonst zu einem 500 ohne CORS-Header fuehrt, siehe PR
    # #12).
    try:
        return Drive(
            id=item["id"],
            name=item["name"],
            drive_type=item.get("driveType", ""),
            webdav_url=str(item["root"]["webDavUrl"]),
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise OpenCloudError(
            "Unerwartete Antwortstruktur eines OpenCloud-Spaces in der Graph-API-Antwort "
            "(GET /graph/v1.0/me/drives)."
        ) from exc


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
        try:
            raw_drives = payload.get("value", [])
        except AttributeError as exc:
            # payload selbst ist kein JSON-Objekt (z.B. ein Array/String an oberster Ebene) -
            # .get() existiert dann nicht.
            raise OpenCloudError(
                "Unerwartete Antwortstruktur der Graph-API-Space-Liste "
                "(GET /graph/v1.0/me/drives)."
            ) from exc
        if not isinstance(raw_drives, list):
            # "value" ist zwar vorhanden, aber kein Array (z.B. explizit null oder eine Zahl) -
            # payload.get("value", []) liefert bei einem vorhandenen, aber null-wertigen Key den
            # Default NICHT (der greift nur bei fehlendem Key), das wuerde die Iteration unten
            # sonst mit einem rohen TypeError statt einer verstaendlichen OpenCloudError
            # abbrechen lassen.
            raise OpenCloudError(
                "Unerwartete Antwortstruktur der Graph-API-Space-Liste "
                "(GET /graph/v1.0/me/drives): 'value' ist kein Array."
            )
        return [_drive_from_graph_api_item(item) for item in raw_drives]

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

        # Terminierungs-Fix (specs/features/0023-scan-fortschritt-batch-groesse-fix.md): eine
        # unerwartete/kaputte WebDAV-Antwort (z.B. abgeschnittenes XML-Tag, nicht-numerischer
        # content-length, unparsbares Datum in _parse_last_modified) darf hier nicht als roher
        # ParseError/ValueError/TypeError propagieren - sonst laeuft die Exception ungefangen bis
        # in worker.py::run_project_scan durch, dessen (frueher zu enger) Fehlerbehandlungs-Block
        # den zugehoerigen ScanRun dann dauerhaft auf "running" stehen laesst. Analog zum
        # bestehenden Muster in _drive_from_graph_api_item (gleiche Datei).
        try:
            entries = parse_multistatus(response.content)
        except (ElementTree.ParseError, ValueError, TypeError) as exc:
            raise OpenCloudError(
                f"Unerwartete/kaputte WebDAV-Antwort beim Auflisten von '{path}'."
            ) from exc
        target_path = unquote(urlparse(target_url).path).rstrip("/")
        return [entry for entry in entries if unquote(entry.href).rstrip("/") != target_path]

    async def walk(
        self, webdav_url: str, root_path: str
    ) -> AsyncIterator[tuple[str, DavEntry]]:
        # Zyklenschutz (specs/features/0034-scan-haenger-fortschritts-watchdog.md, ADR 0019):
        # ohne dieses Set wuerde ein (hypothetischer) Zyklus in der WebDAV-Verzeichnisstruktur
        # (ein Kind-Ordner-Eintrag verweist auf einen bereits besuchten Pfad) denselben Pfad
        # immer wieder in die BFS-Queue einreihen - files_found/last_progress_at wuerden dabei
        # laufend "fortschreiten", ohne dass Schicht 2 (reap_stalled_runs) einen echten Stillstand
        # erkennen wuerde. child_relative wird VOR dem queue.append geprueft, nicht erst beim
        # Dequeuen - so wird auch eine doppelte Referenz innerhalb DERSELBEN Listing-Antwort
        # abgefangen.
        start = root_path.strip("/")
        visited: set[str] = {start}
        queue: deque[str] = deque([start])
        while queue:
            current = queue.popleft()
            for entry in await self.list_folder(webdav_url, current):
                child_relative = f"{current}/{entry.name}" if current else entry.name
                if entry.is_collection:
                    if child_relative in visited:
                        continue
                    visited.add(child_relative)
                    queue.append(child_relative)
                else:
                    yield child_relative, entry

    async def get_range(self, webdav_url: str, relative_path: str, length: int) -> bytes:
        url = _join(webdav_url, relative_path)
        response = await self._send("GET", url, headers={"Range": f"bytes=0-{length - 1}"})
        _raise_for_status(response)
        return response.content

    async def download(self, webdav_url: str, relative_path: str) -> bytes:
        """Full-file download, used by the worker for thumbnail generation (specs/features/0002-
        manual-categorization.md) - get_range's partial content isn't reliably enough for a
        complete image."""
        url = _join(webdav_url, relative_path)
        response = await self._send("GET", url)
        _raise_for_status(response)
        return response.content
