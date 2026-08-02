import base64

import httpx
import pytest

from photosort.opencloud.client import OpenCloudClient, OpenCloudError, _join

DRIVES_RESPONSE = {
    "value": [
        {
            "id": "storage-users-1$personal-id",
            "name": "Daniel",
            "driveType": "personal",
            "root": {
                "webDavUrl": "https://cloud.example.com/dav/spaces/storage-users-1$personal-id"
            },
        },
        {
            "id": "storage-project-1$family-id",
            "name": "Family",
            "driveType": "project",
            "root": {
                "webDavUrl": "https://cloud.example.com/dav/spaces/storage-project-1$family-id"
            },
        },
    ]
}

ROOT_PROPFIND = """<?xml version="1.0"?>
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
      <d:prop>
        <d:resourcetype></d:resourcetype>
        <d:getetag>"img001"</d:getetag>
        <d:getlastmodified>Mon, 28 Aug 2023 20:45:03 GMT</d:getlastmodified>
        <d:getcontentlength>1000</d:getcontentlength>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""

SUB_PROPFIND = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/dav/spaces/storage-project-1$family-id/CostaRica/Sub/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/></d:resourcetype><d:getetag>"sub"</d:getetag></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/dav/spaces/storage-project-1$family-id/CostaRica/Sub/img002.jpg</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype></d:resourcetype>
        <d:getetag>"img002"</d:getetag>
        <d:getlastmodified>Mon, 28 Aug 2023 20:46:03 GMT</d:getlastmodified>
        <d:getcontentlength>2000</d:getcontentlength>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""

WEBDAV_URL = "https://cloud.example.com/dav/spaces/storage-project-1$family-id"


def _client(handler: httpx.MockTransport) -> OpenCloudClient:
    return OpenCloudClient(
        base_url="https://cloud.example.com",
        username="daniel",
        app_token="s3cr3t-token",
        transport=handler,
    )


async def test_list_drives_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/graph/v1.0/me/drives"
        return httpx.Response(200, json=DRIVES_RESPONSE)

    client = _client(httpx.MockTransport(handler))
    drives = await client.list_drives()

    assert [d.name for d in drives] == ["Daniel", "Family"]
    assert drives[1].webdav_url == "https://cloud.example.com/dav/spaces/storage-project-1$family-id"


async def test_list_drives_raises_opencloud_error_for_missing_root_webdav_url() -> None:
    # Regressionstest: die reale Graph-API liefert "webDavUrl" verschachtelt unter "root" statt
    # auf oberster Ebene des Drive-Objekts (siehe specs/roadmap.md, "[Bug bestaetigt]"-Eintrag
    # 2026-08-02, empirisch gegen einen echten opencloud-rolling-Container verifiziert - der
    # frueher hier verwendete flache DRIVES_RESPONSE-Fixture spiegelte eine falsche, nie real
    # existierende Antwortstruktur und liess den Bug im Testlauf unentdeckt). Eine unerwartete
    # Struktur (fehlendes "root" oder "webDavUrl") muss als OpenCloudError statt als roher
    # KeyError propagieren, sonst faengt api/opencloud.py::browse_folder ihn nicht ab und der
    # Client bekommt einen 500er ohne CORS-Header statt einer verstaendlichen 400-Fehlermeldung.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"value": [{"id": "x", "name": "Broken", "driveType": "personal"}]},
        )

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(OpenCloudError):
        await client.list_drives()


async def test_list_drives_raises_opencloud_error_for_non_dict_item() -> None:
    # Zweiter Copilot-Review-Fund auf PR #12: ein Nicht-dict-Eintrag in payload["value"] (z.B. ein
    # String/int) liess vorher einen rohen TypeError aus "item[\"id\"]" durchschlagen, statt als
    # OpenCloudError abgefangen zu werden - _drive_from_graph_api_item() umschliesst jetzt die
    # gesamte Drive-Konstruktion, nicht nur den root.webDavUrl-Zugriff.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": ["not-a-dict"]})

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(OpenCloudError):
        await client.list_drives()


async def test_list_drives_raises_opencloud_error_for_non_object_payload() -> None:
    # Dritter Copilot-Review-Fund: liefert die Graph-API kein JSON-Objekt auf oberster Ebene
    # (z.B. ein Array statt {"value": [...]}), wuerde payload.get(...) mit AttributeError
    # abbrechen statt einer verstaendlichen OpenCloudError.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["unexpected", "top-level", "array"])

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(OpenCloudError):
        await client.list_drives()


async def test_list_drives_raises_opencloud_error_for_null_value_field() -> None:
    # Vierter Copilot-Review-Fund: ein vorhandenes, aber explizit auf null gesetztes "value"-Feld
    # liess payload.get("value", []) den Default umgehen (der Key existiert ja) und lieferte
    # None zurueck - "for item in None" brach dann mit einem rohen TypeError ab statt einer
    # OpenCloudError.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"value": None})

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(OpenCloudError):
        await client.list_drives()


async def test_network_failure_is_wrapped_as_opencloud_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(OpenCloudError):
        await client.list_drives()


async def test_invalid_base_url_is_wrapped_as_opencloud_error() -> None:
    client = OpenCloudClient(base_url="", username="daniel", app_token="s3cr3t-token")

    with pytest.raises(OpenCloudError):
        await client.list_drives()


async def test_authorization_header_uses_basic_auth() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        return httpx.Response(200, json=DRIVES_RESPONSE)

    client = _client(httpx.MockTransport(handler))
    await client.list_drives()

    expected = "Basic " + base64.b64encode(b"daniel:s3cr3t-token").decode()
    assert seen["authorization"] == expected


async def test_resolve_drive_by_name() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=DRIVES_RESPONSE)

    client = _client(httpx.MockTransport(handler))
    drive = await client.resolve_drive("Family")

    assert drive.id == "storage-project-1$family-id"


async def test_resolve_drive_raises_for_unknown_name() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=DRIVES_RESPONSE)

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(OpenCloudError):
        await client.resolve_drive("Nonexistent")


async def test_list_folder_filters_out_self_entry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PROPFIND"
        assert request.headers["depth"] == "1"
        return httpx.Response(
            207, content=ROOT_PROPFIND.encode(), headers={"content-type": "application/xml"}
        )

    client = _client(httpx.MockTransport(handler))
    entries = await client.list_folder(WEBDAV_URL, "CostaRica")

    names = {e.name for e in entries}
    assert names == {"Sub", "img001.jpg"}


async def test_list_folder_raises_on_404() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(OpenCloudError):
        await client.list_folder(WEBDAV_URL, "DoesNotExist")


async def test_walk_recurses_into_subfolders() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.rstrip("/").endswith("/CostaRica"):
            return httpx.Response(207, content=ROOT_PROPFIND.encode())
        if request.url.path.rstrip("/").endswith("/Sub"):
            return httpx.Response(207, content=SUB_PROPFIND.encode())
        raise AssertionError(f"unexpected path {request.url.path}")

    client = _client(httpx.MockTransport(handler))
    results = [item async for item in client.walk(WEBDAV_URL, "CostaRica")]

    relative_paths = {relative_path for relative_path, _entry in results}
    assert relative_paths == {"CostaRica/img001.jpg", "CostaRica/Sub/img002.jpg"}


def test_join_builds_url_from_plain_segments() -> None:
    assert _join(WEBDAV_URL, "CostaRica/Sub") == f"{WEBDAV_URL}/CostaRica/Sub"


def test_join_returns_base_for_empty_path() -> None:
    assert _join(WEBDAV_URL, "") == WEBDAV_URL


def test_join_rejects_parent_traversal_segment() -> None:
    # Security-Haertung (specs/features/0005-minimal-project-frontend.md, Muss-Kriterium):
    # ohne diesen Fix wuerde ein "../"-Segment aus dem konfigurierten Projekt-Wurzelverzeichnis
    # herauslaufen und andere, ueber WebDAV erreichbare Bereiche ansprechen.
    with pytest.raises(OpenCloudError):
        _join(WEBDAV_URL, "../secret")


def test_join_rejects_parent_traversal_segment_in_the_middle_of_the_path() -> None:
    with pytest.raises(OpenCloudError):
        _join(WEBDAV_URL, "CostaRica/../../secret")


async def test_list_folder_rejects_path_with_parent_traversal_segment() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be sent for a rejected path")

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(OpenCloudError):
        await client.list_folder(WEBDAV_URL, "../secret")


async def test_get_range_rejects_path_with_parent_traversal_segment() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be sent for a rejected path")

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(OpenCloudError):
        await client.get_range(WEBDAV_URL, "../secret", length=10)


async def test_get_range_sends_range_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["range"] = request.headers["range"]
        return httpx.Response(206, content=b"partial-bytes")

    client = _client(httpx.MockTransport(handler))
    content = await client.get_range(WEBDAV_URL, "CostaRica/img001.jpg", length=1024)

    assert seen["range"] == "bytes=0-1023"
    assert content == b"partial-bytes"


async def test_download_returns_full_content_without_range_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["has_range"] = str("range" in request.headers)
        return httpx.Response(200, content=b"full-file-bytes")

    client = _client(httpx.MockTransport(handler))
    content = await client.download(WEBDAV_URL, "CostaRica/img001.jpg")

    assert seen["has_range"] == "False"
    assert content == b"full-file-bytes"


async def test_download_rejects_path_with_parent_traversal_segment() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be sent for a rejected path")

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(OpenCloudError):
        await client.download(WEBDAV_URL, "../secret")


async def test_download_raises_on_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client(httpx.MockTransport(handler))

    with pytest.raises(OpenCloudError):
        await client.download(WEBDAV_URL, "CostaRica/img001.jpg")
