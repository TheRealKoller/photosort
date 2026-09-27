from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

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
        self.list_calls = 0

    async def resolve_drive(self, name: str | None) -> Drive:
        if self._fail:
            raise self._fail
        return Drive(
            id="drive-1",
            name="Family",
            drive_type="project",
            webdav_url="https://x/dav/spaces/drive-1",
        )

    async def list_folder(self, webdav_url: str, path: str, depth: str = "1") -> list[DavEntry]:
        self.list_calls += 1
        if self._fail:
            raise self._fail
        return self._entries


def _entry(name: str, is_collection: bool, last_modified: datetime | None = None) -> DavEntry:
    return DavEntry(
        href=f"/x/{name}",
        name=name,
        is_collection=is_collection,
        etag="e",
        last_modified=last_modified,
        content_length=None,
    )


async def test_browse_returns_only_folders(authenticated_api_client: httpx.AsyncClient) -> None:
    fake = FakeClient(entries=[_entry("Sub", True), _entry("img.jpg", False)])
    app.dependency_overrides[get_opencloud_client] = lambda: fake

    response = await authenticated_api_client.get("/opencloud/browse", params={"path": "CostaRica"})

    assert response.status_code == 200
    assert response.json() == [{"name": "Sub", "path": "CostaRica/Sub", "modified_at": None}]


async def test_browse_returns_the_modification_time_from_the_listing(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    fake = FakeClient(
        entries=[
            _entry("Sub", True, datetime(2023, 8, 28, 20, 45, 10, tzinfo=UTC)),
            _entry("Leer", True, None),
        ]
    )
    app.dependency_overrides[get_opencloud_client] = lambda: fake

    response = await authenticated_api_client.get("/opencloud/browse", params={"path": "CostaRica"})

    assert response.status_code == 200
    assert response.json() == [
        {"name": "Sub", "path": "CostaRica/Sub", "modified_at": "2023-08-28T20:45:10Z"},
        {"name": "Leer", "path": "CostaRica/Leer", "modified_at": None},
    ]
    # Das Datum kommt aus derselben PROPFIND-Antwort wie das Listing selbst.
    assert fake.list_calls == 1


async def test_browse_marks_a_date_without_zone_as_utc(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    # RFC 1123 mit "-0000" parst ohne Zeitzone; ohne Offset laese der Browser den Wert als Ortszeit.
    fake = FakeClient(
        entries=[_entry("Sub", True, parsedate_to_datetime("Mon, 28 Aug 2023 20:45:10 -0000"))]
    )
    app.dependency_overrides[get_opencloud_client] = lambda: fake

    response = await authenticated_api_client.get("/opencloud/browse")

    assert response.status_code == 200
    assert response.json() == [
        {"name": "Sub", "path": "Sub", "modified_at": "2023-08-28T20:45:10Z"}
    ]


async def test_browse_returns_400_on_opencloud_error(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    fake = FakeClient(fail=OpenCloudError("nicht erreichbar"))
    app.dependency_overrides[get_opencloud_client] = lambda: fake

    response = await authenticated_api_client.get("/opencloud/browse")

    assert response.status_code == 400
    assert response.json()["detail"] == "nicht erreichbar"
