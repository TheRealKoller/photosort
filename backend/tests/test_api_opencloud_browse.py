import httpx

from photosort.api.deps import get_opencloud_client
from photosort.main import app
from photosort.opencloud.client import Drive, OpenCloudError
from photosort.opencloud.webdav_xml import DavEntry


class FakeClient:
    def __init__(
        self, entries: list[DavEntry] | None = None, fail: OpenCloudError | None = None
    ) -> None:
        self._entries = entries or []
        self._fail = fail

    async def resolve_drive(self, name: str | None) -> Drive:
        if self._fail:
            raise self._fail
        return Drive(id="drive-1", name="Family", drive_type="project", webdav_url="https://x/dav/spaces/drive-1")

    async def list_folder(self, webdav_url: str, path: str, depth: str = "1") -> list[DavEntry]:
        if self._fail:
            raise self._fail
        return self._entries


def _entry(name: str, is_collection: bool) -> DavEntry:
    return DavEntry(
        href=f"/x/{name}",
        name=name,
        is_collection=is_collection,
        etag="e",
        last_modified=None,
        content_length=None,
    )


async def test_browse_returns_only_folders(authenticated_api_client: httpx.AsyncClient) -> None:
    fake = FakeClient(entries=[_entry("Sub", True), _entry("img.jpg", False)])
    app.dependency_overrides[get_opencloud_client] = lambda: fake

    response = await authenticated_api_client.get("/opencloud/browse", params={"path": "CostaRica"})

    assert response.status_code == 200
    assert response.json() == [{"name": "Sub", "path": "CostaRica/Sub"}]


async def test_browse_returns_400_on_opencloud_error(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    fake = FakeClient(fail=OpenCloudError("nicht erreichbar"))
    app.dependency_overrides[get_opencloud_client] = lambda: fake

    response = await authenticated_api_client.get("/opencloud/browse")

    assert response.status_code == 400
    assert response.json()["detail"] == "nicht erreichbar"
