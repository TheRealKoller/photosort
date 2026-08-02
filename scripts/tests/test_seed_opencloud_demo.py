from __future__ import annotations

from pathlib import Path

import httpx
import pytest


async def _no_sleep(_seconds: float) -> None:
    """Ersetzt asyncio.sleep in Tests - kein echtes Warten, aber Aufrufe zaehlbar ueber Closure."""


class TestValidateDemoBaseUrl:
    """AK aus specs/features/0009-local-opencloud-demo-stack.md: die Ziel-OPENCLOUD_BASE_URL wird
    vor dem Schreiben gegen ein erwartetes Demo-Muster geprueft, damit ein versehentlicher Lauf
    gegen die produktive .env keine Fotos in einen echten Familien-Space schreibt."""

    @pytest.mark.parametrize(
        "base_url",
        [
            "http://opencloud-demo:9200",
            "http://localhost:9200",
            "http://127.0.0.1:9200",
            "http://localhost:9200/",
        ],
    )
    def test_accepts_known_demo_hosts(self, seed_module, base_url: str) -> None:
        seed_module.validate_demo_base_url(base_url)  # muss NICHT werfen

    @pytest.mark.parametrize(
        "base_url",
        [
            "https://cloud.example.com",
            "http://cloud.example.com:9200",
            "https://opencloud-demo:9200",  # falsches Schema trotz erlaubtem Host
            "http://192.168.1.50:9200",
            "not-a-url",
            "",
        ],
    )
    def test_rejects_non_demo_hosts(self, seed_module, base_url: str) -> None:
        with pytest.raises(seed_module.SeedError):
            seed_module.validate_demo_base_url(base_url)


class TestWaitUntilReady:
    """AK aus specs/features/0009-local-opencloud-demo-stack.md: das Skript wartet aktiv auf den
    Demo-Container statt sofort mit Verbindungsfehler abzubrechen (Container braucht nach dem
    Start eine Weile, bis er antwortet)."""

    async def test_succeeds_after_container_becomes_reachable(self, seed_module) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise httpx.ConnectError("connection refused", request=request)
            return httpx.Response(200, request=request)

        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await seed_module.wait_until_ready(
            client, "http://opencloud-demo:9200", max_attempts=5, poll_interval=3.0, sleep=fake_sleep
        )
        await client.aclose()

        assert attempts == 3
        assert sleeps == [3.0, 3.0]  # zwei Wartezyklen zwischen den drei Versuchen

    async def test_treats_server_error_as_not_ready_yet(self, seed_module) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                return httpx.Response(503, request=request)
            return httpx.Response(200, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await seed_module.wait_until_ready(
            client, "http://opencloud-demo:9200", max_attempts=5, poll_interval=0, sleep=_no_sleep
        )
        await client.aclose()

        assert attempts == 2

    async def test_gives_up_after_max_attempts(self, seed_module) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(seed_module.SeedError, match="nicht erreichbar"):
            await seed_module.wait_until_ready(
                client, "http://opencloud-demo:9200", max_attempts=3, poll_interval=0, sleep=_no_sleep
            )
        await client.aclose()


_DRIVES_PAYLOAD = {
    "value": [
        {
            "id": "project-space-id",
            "name": "Projects",
            "driveType": "project",
            "webDavUrl": "http://opencloud-demo:9200/dav/spaces/project-space-id",
        },
        {
            "id": "alan-personal-id",
            "name": "Alan Shepard",
            "driveType": "personal",
            "webDavUrl": "http://opencloud-demo:9200/dav/spaces/alan-personal-id",
        },
    ]
}


class TestFetchDrives:
    """Nutzt denselben Graph-API-Codepfad wie OpenCloudClient.list_drives (AK aus
    specs/features/0009-local-opencloud-demo-stack.md), aber eigenstaendig implementiert (kein
    Import aus backend/src/photosort, siehe ADR 0009)."""

    async def test_returns_parsed_drives_on_success(self, seed_module) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/graph/v1.0/me/drives"
            return httpx.Response(200, json=_DRIVES_PAYLOAD, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        drives = await seed_module.fetch_drives(client, "http://opencloud-demo:9200")
        await client.aclose()

        assert drives == _DRIVES_PAYLOAD["value"]

    async def test_raises_seed_error_on_http_failure(self, seed_module) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(seed_module.SeedError):
            await seed_module.fetch_drives(client, "http://opencloud-demo:9200")
        await client.aclose()


class TestResolveDriveWebdavUrl:
    def test_picks_personal_drive_when_no_name_given(self, seed_module) -> None:
        url = seed_module.resolve_drive_webdav_url(_DRIVES_PAYLOAD["value"], None)
        assert url == "http://opencloud-demo:9200/dav/spaces/alan-personal-id"

    def test_picks_drive_by_exact_name(self, seed_module) -> None:
        url = seed_module.resolve_drive_webdav_url(_DRIVES_PAYLOAD["value"], "Projects")
        assert url == "http://opencloud-demo:9200/dav/spaces/project-space-id"

    def test_raises_when_named_drive_not_found(self, seed_module) -> None:
        with pytest.raises(seed_module.SeedError, match="nicht gefunden"):
            seed_module.resolve_drive_webdav_url(_DRIVES_PAYLOAD["value"], "Does Not Exist")

    def test_raises_when_no_drives_at_all(self, seed_module) -> None:
        with pytest.raises(seed_module.SeedError):
            seed_module.resolve_drive_webdav_url([], None)

    def test_falls_back_to_first_drive_without_personal_type(self, seed_module) -> None:
        drives = [_DRIVES_PAYLOAD["value"][0]]  # nur das "project"-Drive, kein "personal"
        url = seed_module.resolve_drive_webdav_url(drives, None)
        assert url == "http://opencloud-demo:9200/dav/spaces/project-space-id"


_WEBDAV_URL = "http://opencloud-demo:9200/dav/spaces/alan-personal-id"


class TestEnsureFolder:
    """AK "Idempotenz": erneutes Ausfuehren gegen einen bereits geseedeten Container bricht nicht
    ab (specs/features/0009-local-opencloud-demo-stack.md)."""

    async def test_creates_folder_via_mkcol(self, seed_module) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(201, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await seed_module.ensure_folder(client, _WEBDAV_URL, "PhotoSort Demo")
        await client.aclose()

        assert len(requests) == 1
        assert requests[0].method == "MKCOL"
        assert requests[0].url.path == "/dav/spaces/alan-personal-id/PhotoSort Demo"

    async def test_existing_folder_is_not_an_error(self, seed_module) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(405, request=request)  # WebDAV: Ordner existiert bereits

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await seed_module.ensure_folder(client, _WEBDAV_URL, "PhotoSort Demo")  # darf nicht werfen
        await client.aclose()

    async def test_other_failure_raises(self, seed_module) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(seed_module.SeedError):
            await seed_module.ensure_folder(client, _WEBDAV_URL, "PhotoSort Demo")
        await client.aclose()


class TestUploadPhoto:
    """AK "Idempotenz" fuer Dateien: existiert eine Datei bereits, wird sie uebersprungen statt
    dupliziert (Testkonzept-Ergaenzung, architecture/0002-testkonzept.md)."""

    async def test_uploads_new_file(self, seed_module) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.method)
            if request.method == "HEAD":
                return httpx.Response(404, request=request)
            assert request.method == "PUT"
            assert request.url.path == "/dav/spaces/alan-personal-id/PhotoSort Demo/demo-01.jpg"
            assert request.content == b"fake-jpeg-bytes"
            return httpx.Response(201, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        outcome = await seed_module.upload_photo(
            client, _WEBDAV_URL, "PhotoSort Demo", "demo-01.jpg", b"fake-jpeg-bytes"
        )
        await client.aclose()

        assert outcome == "uploaded"
        assert calls == ["HEAD", "PUT"]

    async def test_skips_existing_file_without_reupload(self, seed_module) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.method)
            return httpx.Response(200, request=request)  # HEAD: Datei existiert bereits

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        outcome = await seed_module.upload_photo(
            client, _WEBDAV_URL, "PhotoSort Demo", "demo-01.jpg", b"fake-jpeg-bytes"
        )
        await client.aclose()

        assert outcome == "skipped"
        assert calls == ["HEAD"]  # kein PUT, kein Duplikat

    async def test_failed_upload_is_reported_not_raised(self, seed_module) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "HEAD":
                return httpx.Response(404, request=request)
            return httpx.Response(500, request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        outcome = await seed_module.upload_photo(
            client, _WEBDAV_URL, "PhotoSort Demo", "demo-01.jpg", b"fake-jpeg-bytes"
        )
        await client.aclose()

        assert outcome == "failed"


class TestDiscoverDemoPhotos:
    def test_returns_sorted_image_files(self, seed_module, tmp_path: Path) -> None:
        (tmp_path / "b.jpg").write_bytes(b"b")
        (tmp_path / "a.jpg").write_bytes(b"a")
        (tmp_path / "c.png").write_bytes(b"c")
        (tmp_path / "readme.txt").write_bytes(b"not a photo")  # muss ignoriert werden

        photos = seed_module.discover_demo_photos(tmp_path)

        assert [p.name for p in photos] == ["a.jpg", "b.jpg", "c.png"]

    def test_raises_when_no_photos_found(self, seed_module, tmp_path: Path) -> None:
        with pytest.raises(seed_module.SeedError, match="[Kk]eine"):
            seed_module.discover_demo_photos(tmp_path)

    def test_raises_when_directory_missing(self, seed_module, tmp_path: Path) -> None:
        with pytest.raises(seed_module.SeedError):
            seed_module.discover_demo_photos(tmp_path / "does-not-exist")
