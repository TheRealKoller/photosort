"""specs/features/0050-dateianzahl-im-ordner-browser.md, ADR decisions/0028-ordner-browser-
bilddatei-zaehlung.md: begrenzte, parallele Bilddatei-Zaehlung pro Unterordner. Testet
_count_images_up_to_limit isoliert (gemockte walk()) sowie gegen einen echten OpenCloudClient
(httpx.MockTransport, Anfragezaehler - einziger Weg, den Early-Exit-Netzwerkeffekt zu beweisen)
und den Endpunkt GET /opencloud/folder-counts End-to-End."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest

from photosort.api.deps import get_opencloud_client
from photosort.api.opencloud import FOLDER_COUNT_LIMIT, _count_images_up_to_limit, folder_counts
from photosort.main import app
from photosort.opencloud.client import Drive, OpenCloudClient, OpenCloudError
from photosort.opencloud.webdav_xml import DavEntry

WEBDAV_URL = "https://cloud.example.com/dav/spaces/storage-project-1$family-id"


def _entry(name: str, is_collection: bool = False) -> DavEntry:
    return DavEntry(
        href=f"/dav/spaces/x/CostaRica/{name}",
        name=name,
        is_collection=is_collection,
        etag="etag",
        last_modified=None,
        content_length=None,
    )


class _FakeWalkClient:
    """Minimaler Fake fuer _count_images_up_to_limit-Unit-Tests - kein echtes Netzwerk, nur eine
    frei konfigurierbare async-Generator-Funktion als client.walk()."""

    def __init__(self, walk_fn: object) -> None:
        self.walk = walk_fn


async def test_count_images_up_to_limit_counts_only_image_extensions() -> None:
    async def walk(
        webdav_url: str, root_path: str
    ) -> AsyncIterator[tuple[str, DavEntry]]:
        yield "CostaRica/img1.jpg", _entry("img1.jpg")
        yield "CostaRica/notes.txt", _entry("notes.txt")
        yield "CostaRica/img2.HEIC", _entry("img2.HEIC")

    client = _FakeWalkClient(walk)

    count, at_limit = await _count_images_up_to_limit(client, WEBDAV_URL, "CostaRica", limit=500)

    assert count == 2
    assert at_limit is False


async def test_count_images_up_to_limit_stops_consuming_once_limit_reached() -> None:
    # Pflicht-Nachweis (Akzeptanzkriterium): nach Erreichen des Limits werden keine weiteren
    # Eintraege mehr aus dem walk()-Generator konsumiert - hier durch einen Zaehler bewiesen, der
    # bei jedem gelieferten Eintrag hochzaehlt, unabhaengig davon, wie viele Eintraege insgesamt
    # verfuegbar waeren.
    consumed = 0

    async def walk(
        webdav_url: str, root_path: str
    ) -> AsyncIterator[tuple[str, DavEntry]]:
        nonlocal consumed
        for i in range(1000):
            consumed += 1
            yield f"CostaRica/img{i:04d}.jpg", _entry(f"img{i:04d}.jpg")

    client = _FakeWalkClient(walk)

    count, at_limit = await _count_images_up_to_limit(client, WEBDAV_URL, "CostaRica", limit=500)

    assert count == 500
    assert at_limit is True
    assert consumed == 500


async def test_count_images_up_to_limit_exactly_499_images_is_not_at_limit() -> None:
    async def walk(
        webdav_url: str, root_path: str
    ) -> AsyncIterator[tuple[str, DavEntry]]:
        for i in range(499):
            yield f"CostaRica/img{i:04d}.jpg", _entry(f"img{i:04d}.jpg")

    client = _FakeWalkClient(walk)

    count, at_limit = await _count_images_up_to_limit(
        client, WEBDAV_URL, "CostaRica", limit=FOLDER_COUNT_LIMIT
    )

    assert count == 499
    assert at_limit is False


async def test_count_images_up_to_limit_exactly_500_images_is_at_limit() -> None:
    async def walk(
        webdav_url: str, root_path: str
    ) -> AsyncIterator[tuple[str, DavEntry]]:
        for i in range(500):
            yield f"CostaRica/img{i:04d}.jpg", _entry(f"img{i:04d}.jpg")

    client = _FakeWalkClient(walk)

    count, at_limit = await _count_images_up_to_limit(
        client, WEBDAV_URL, "CostaRica", limit=FOLDER_COUNT_LIMIT
    )

    assert count == 500
    assert at_limit is True


async def test_count_images_up_to_limit_real_empty_folder_returns_zero_not_at_limit() -> None:
    # Echter Leerordner - separat getestet von "nur Nicht-Bild-Dateien" (unterschiedliche
    # Ursache, siehe Akzeptanzkriterium).
    async def walk(
        webdav_url: str, root_path: str
    ) -> AsyncIterator[tuple[str, DavEntry]]:
        return
        yield  # pragma: no cover - macht die Funktion zu einem Async-Generator

    client = _FakeWalkClient(walk)

    count, at_limit = await _count_images_up_to_limit(client, WEBDAV_URL, "CostaRica", limit=500)

    assert count == 0
    assert at_limit is False


async def test_count_images_up_to_limit_folder_with_only_non_images_returns_zero_not_at_limit() -> (
    None
):
    # Ordner mit ausschliesslich Nicht-Bild-Dateien - separat getestet vom echten Leerordner oben.
    async def walk(
        webdav_url: str, root_path: str
    ) -> AsyncIterator[tuple[str, DavEntry]]:
        yield "CostaRica/notes.txt", _entry("notes.txt")
        yield "CostaRica/video.mp4", _entry("video.mp4")

    client = _FakeWalkClient(walk)

    count, at_limit = await _count_images_up_to_limit(client, WEBDAV_URL, "CostaRica", limit=500)

    assert count == 0
    assert at_limit is False


ROOT_WITH_SUB_AND_TWO_IMAGES = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/dav/spaces/storage-project-1$family-id/CostaRica/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/></d:resourcetype><d:getetag>"root"</d:getetag></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/spaces/storage-project-1$family-id/CostaRica/Sub/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/></d:resourcetype><d:getetag>"sub"</d:getetag></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/spaces/storage-project-1$family-id/CostaRica/img001.jpg</d:href>
    <d:propstat>
      <d:prop><d:resourcetype></d:resourcetype><d:getetag>"img001"</d:getetag></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/spaces/storage-project-1$family-id/CostaRica/img002.jpg</d:href>
    <d:propstat>
      <d:prop><d:resourcetype></d:resourcetype><d:getetag>"img002"</d:getetag></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""


async def test_count_images_up_to_limit_sends_no_further_propfind_requests_once_limit_reached() -> (
    None
):
    # Kontrakt-Test gegen einen echten OpenCloudClient (httpx.MockTransport mit Anfragezaehler) -
    # der einzige Weg, den Early-Exit-Netzwerkeffekt tatsaechlich zu beweisen (Teststrategie-
    # Abschnitt der Spec): die root-Antwort enthaelt einen "Sub"-Unterordner UND (danach) genug
    # Bilddateien, um das Limit zu erreichen - walk() darf "Sub" wegen des Early-Exits NIE
    # anfragen.
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request.url.path.rstrip("/").endswith("/CostaRica"):
            return httpx.Response(207, content=ROOT_WITH_SUB_AND_TWO_IMAGES.encode())
        raise AssertionError(
            f"unerwartete PROPFIND-Anfrage an {request.url.path} - walk() haette nach "
            "Erreichen des Limits keine weitere Ebene mehr anfragen duerfen"
        )

    client = OpenCloudClient(
        base_url="https://cloud.example.com",
        username="daniel",
        app_token="s3cr3t-token",
        transport=httpx.MockTransport(handler),
    )

    count, at_limit = await _count_images_up_to_limit(client, WEBDAV_URL, "CostaRica", limit=2)

    assert count == 2
    assert at_limit is True
    assert request_count == 1


async def test_count_images_up_to_limit_preserves_cycle_protection_of_walk() -> None:
    # Akzeptanzkriterium: Zyklenschutz von walk() bleibt unter der neuen Konsumierung wirksam -
    # _count_images_up_to_limit haelt keinen eigenen visited-Zustand, verlaesst sich vollstaendig
    # auf walk(). Simuliert wie test_opencloud_client.py::
    # test_walk_terminates_when_a_child_entry_points_at_an_already_visited_path eine doppelte
    # "Sub"-Referenz in derselben Listing-Antwort.
    calls: list[str] = []

    async def fake_list_folder(
        webdav_url: str, path: str = "", depth: str = "1"
    ) -> list[DavEntry]:
        calls.append(path)
        if path == "CostaRica":
            return [_entry("Sub", is_collection=True), _entry("Sub", is_collection=True)]
        if path == "CostaRica/Sub":
            return [_entry("img.jpg", is_collection=False)]
        raise AssertionError(f"unexpected path {path}")

    client = OpenCloudClient(
        base_url="https://cloud.example.com",
        username="daniel",
        app_token="s3cr3t-token",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    client.list_folder = fake_list_folder  # type: ignore[method-assign]

    count, at_limit = await _count_images_up_to_limit(client, WEBDAV_URL, "CostaRica", limit=500)

    assert count == 1
    assert at_limit is False
    assert calls == ["CostaRica", "CostaRica/Sub"]


class FakeCountClient:
    """Fake fuer die Endpunkt-Integrationstests (GET /opencloud/folder-counts), analog dem
    FakeClient aus test_api_opencloud_browse.py, erweitert um ein konfigurierbares walk() pro
    Pfad und einen Aufrufzaehler fuer den Nebenlaeufigkeits-Nachweis."""

    def __init__(
        self,
        entries: list[DavEntry] | None = None,
        walk_results: dict[str, list[tuple[str, DavEntry]]] | None = None,
        fail_paths: set[str] | None = None,
        list_folder_fail: OpenCloudError | None = None,
        walk_delay: float = 0.0,
    ) -> None:
        self._entries = entries or []
        self._walk_results = walk_results or {}
        self._fail_paths = fail_paths or set()
        self._list_folder_fail = list_folder_fail
        self._walk_delay = walk_delay
        self._active_walks = 0
        self.max_concurrent_walks = 0

    async def resolve_drive(self, name: str | None) -> Drive:
        return Drive(id="drive-1", name="Family", drive_type="project", webdav_url=WEBDAV_URL)

    async def list_folder(self, webdav_url: str, path: str, depth: str = "1") -> list[DavEntry]:
        if self._list_folder_fail:
            raise self._list_folder_fail
        return self._entries

    async def walk(
        self, webdav_url: str, root_path: str
    ) -> AsyncIterator[tuple[str, DavEntry]]:
        self._active_walks += 1
        self.max_concurrent_walks = max(self.max_concurrent_walks, self._active_walks)
        try:
            if self._walk_delay:
                await asyncio.sleep(self._walk_delay)
            if root_path in self._fail_paths:
                raise OpenCloudError("Netzwerkfehler mitten in der Traversierung.")
            for item in self._walk_results.get(root_path, []):
                yield item
        finally:
            self._active_walks -= 1


async def test_folder_counts_endpoint_returns_counts_per_subfolder(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    fake = FakeCountClient(
        entries=[_entry("Sub1", True), _entry("Sub2", True), _entry("img.jpg", False)],
        walk_results={
            "CostaRica/Sub1": [("CostaRica/Sub1/a.jpg", _entry("a.jpg"))],
            "CostaRica/Sub2": [],
        },
    )
    app.dependency_overrides[get_opencloud_client] = lambda: fake

    response = await authenticated_api_client.get(
        "/opencloud/folder-counts", params={"path": "CostaRica"}
    )

    assert response.status_code == 200
    body = {item["path"]: item for item in response.json()}
    assert body == {
        "CostaRica/Sub1": {
            "path": "CostaRica/Sub1",
            "count": 1,
            "at_limit": False,
            "error": False,
        },
        "CostaRica/Sub2": {
            "path": "CostaRica/Sub2",
            "count": 0,
            "at_limit": False,
            "error": False,
        },
    }


async def test_folder_counts_endpoint_returns_400_on_listing_failure(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    fake = FakeCountClient(list_folder_fail=OpenCloudError("nicht erreichbar"))
    app.dependency_overrides[get_opencloud_client] = lambda: fake

    response = await authenticated_api_client.get("/opencloud/folder-counts")

    assert response.status_code == 400
    assert response.json()["detail"] == "nicht erreichbar"


async def test_folder_counts_endpoint_marks_only_the_failing_subfolder_as_error(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    fake = FakeCountClient(
        entries=[_entry("Good", True), _entry("Bad", True)],
        walk_results={"CostaRica/Good": [("CostaRica/Good/a.jpg", _entry("a.jpg"))]},
        fail_paths={"CostaRica/Bad"},
    )
    app.dependency_overrides[get_opencloud_client] = lambda: fake

    response = await authenticated_api_client.get(
        "/opencloud/folder-counts", params={"path": "CostaRica"}
    )

    assert response.status_code == 200
    body = {item["path"]: item for item in response.json()}
    assert body["CostaRica/Good"] == {
        "path": "CostaRica/Good",
        "count": 1,
        "at_limit": False,
        "error": False,
    }
    assert body["CostaRica/Bad"] == {
        "path": "CostaRica/Bad",
        "count": 0,
        "at_limit": False,
        "error": True,
    }
    # Kein Freitext-/Meldungsfeld - error=True transportiert kein str(exc) an den Client.
    assert set(body["CostaRica/Bad"].keys()) == {"path", "count", "at_limit", "error"}


@pytest.mark.parametrize(
    ("folder_count", "concurrency", "expected_max_concurrent"),
    [
        (5, 2, 2),
        (2, 4, 2),
        (4, 4, 4),
    ],
)
async def test_folder_counts_endpoint_respects_concurrency_limit(
    authenticated_api_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    folder_count: int,
    concurrency: int,
    expected_max_concurrent: int,
) -> None:
    from photosort import config

    monkeypatch.setattr(config.settings, "opencloud_folder_count_concurrency", concurrency)

    entries = [_entry(f"Sub{i}", True) for i in range(folder_count)]
    fake = FakeCountClient(entries=entries, walk_delay=0.02)
    app.dependency_overrides[get_opencloud_client] = lambda: fake

    response = await authenticated_api_client.get(
        "/opencloud/folder-counts", params={"path": "CostaRica"}
    )

    assert response.status_code == 200
    assert len(response.json()) == folder_count
    assert fake.max_concurrent_walks == expected_max_concurrent


async def test_folder_counts_repropagates_cancelled_error_from_a_single_subfolder_count() -> None:
    """Verifizierter Python-Async-Fallstrick (siehe worker.py::_process_scan_block, ADR 0020,
    test_worker_scan_project.py::
    test_scan_run_marked_failed_on_cancelled_error_from_a_parallel_download): ein CancelledError
    aus EINER einzelnen Zaehl-Coroutine wird von asyncio.gather(..., return_exceptions=True) NICHT
    als Exception abgefangen, sondern als gewoehnliches Ergebniselement durchgereicht - ohne
    explizite Pruefung wuerde der Abbruch faelschlich als error=True verschluckt statt zu
    propagieren. Ruft folder_counts() direkt auf (nicht ueber den ASGI-Stack) - Starlettes
    BaseHTTPMiddleware verschluckt ein durchschlagendes CancelledError sonst als eigenes,
    irrefuehrendes "No response returned"-RuntimeError, was hier nicht der zu pruefende Aspekt
    ist."""

    class _CancellingClient(FakeCountClient):
        async def walk(
            self, webdav_url: str, root_path: str
        ) -> AsyncIterator[tuple[str, DavEntry]]:
            if root_path == "CostaRica/Bad":
                raise asyncio.CancelledError("simulierter Abbruch waehrend einer Zaehlung")
                yield  # pragma: no cover - macht die Funktion zu einem Async-Generator
            async for item in super().walk(webdav_url, root_path):
                yield item

    fake = _CancellingClient(entries=[_entry("Bad", True)])

    with pytest.raises(asyncio.CancelledError):
        await folder_counts(path="CostaRica", client=fake)  # type: ignore[arg-type]


async def test_folder_counts_endpoint_requires_authentication(
    api_client: httpx.AsyncClient,
) -> None:
    # Gleicher router-weiter Torwaechter wie /opencloud/browse (Security-Abschnitt der Spec).
    response = await api_client.get("/opencloud/folder-counts")

    assert response.status_code == 401
