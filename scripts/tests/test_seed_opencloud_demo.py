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
            "http://localhost",  # Review-Finding (Copilot): kein Port -> impliziter Port 80,
            "http://opencloud-demo",  # koennte versehentlich einen anderen lokalen Dienst treffen
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
            client,
            "http://opencloud-demo:9200",
            max_attempts=5,
            poll_interval=3.0,
            sleep=fake_sleep,
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
                client,
                "http://opencloud-demo:9200",
                max_attempts=3,
                poll_interval=0,
                sleep=_no_sleep,
            )
        await client.aclose()


_DRIVES_PAYLOAD = {
    # Shape empirisch gegen den echten opencloud-demo-Container verifiziert (manueller Smoke-Test
    # dieser Spec): "webDavUrl" liegt unter "root", NICHT auf oberster Ebene des Drive-Objekts -
    # bewusst abweichend von der (fehlerhaften) Annahme in
    # backend/src/photosort/opencloud/client.py::list_drives, siehe Abschlussbericht/Rueckfrage.
    "value": [
        {
            "id": "project-space-id",
            "name": "Projects",
            "driveType": "project",
            "root": {"webDavUrl": "http://opencloud-demo:9200/dav/spaces/project-space-id"},
        },
        {
            "id": "alan-personal-id",
            "name": "Alan Shepard",
            "driveType": "personal",
            "root": {"webDavUrl": "http://opencloud-demo:9200/dav/spaces/alan-personal-id"},
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

    async def test_raises_seed_error_for_non_object_payload(self, seed_module) -> None:
        # Analoger Copilot-Review-Fund im Backend-Client (PR #12): ein Nicht-Objekt an oberster
        # Ebene der Antwort liesse payload.get(...) mit AttributeError abbrechen.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=["unexpected", "array"], request=request)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(seed_module.SeedError):
            await seed_module.fetch_drives(client, "http://opencloud-demo:9200")
        await client.aclose()

    async def test_raises_seed_error_for_null_value_field(self, seed_module) -> None:
        # Analoger Copilot-Review-Fund im Backend-Client (PR #12): ein vorhandenes, aber explizit
        # auf null gesetztes "value"-Feld umgeht den .get()-Default und liess list(None) mit
        # einem rohen TypeError abbrechen.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"value": None}, request=request)

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

    def test_raises_seed_error_when_root_webdav_url_missing(self, seed_module) -> None:
        """Review-Finding test-engineer: ein unerwartet fehlendes root/webDavUrl-Feld (genau das
        Feld, das sich beim Smoke-Test schon einmal als verschachtelt herausstellte) sollte eine
        klare SeedError ergeben statt einer rohen KeyError."""
        malformed_drives = [{"id": "x", "name": "Broken", "driveType": "personal"}]
        with pytest.raises(seed_module.SeedError):
            seed_module.resolve_drive_webdav_url(malformed_drives, None)

    def test_drive_webdav_url_raises_seed_error_for_non_dict_item(self, seed_module) -> None:
        """Copilot-Review-Fund auf PR #12 (analoger Fund im Backend-Client): drive.get(...) im
        except-Zweig wuerde bei einem Nicht-dict-Eintrag (z.B. ein String/int in payload["value"])
        mit AttributeError abbrechen und den beabsichtigten SeedError maskieren."""
        with pytest.raises(seed_module.SeedError):
            seed_module._drive_webdav_url("not-a-dict")

    def test_raises_seed_error_for_non_dict_entry_in_drives_list(self, seed_module) -> None:
        """Zweiter Copilot-Review-Fund auf PR #12 (analog im Backend-Client behoben): ein
        Nicht-dict-Eintrag in der drives-Liste liess vorher einen rohen AttributeError aus
        drive.get(...) in resolve_drive_webdav_url() selbst durchschlagen, bevor
        _drive_webdav_url() ueberhaupt erreicht wurde."""
        drives = ["not-a-dict", *_DRIVES_PAYLOAD["value"]]
        url = seed_module.resolve_drive_webdav_url(drives, None)
        assert url  # findet weiterhin ein gueltiges Drive, statt an "not-a-dict" abzubrechen

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

    async def test_transport_error_raises_seed_error_not_raw_httpx_error(self, seed_module) -> None:
        """Review-Finding test-engineer: MKCOL sollte wie upload_photo/fetch_drives einen
        httpx.HTTPError in eine SeedError uebersetzen statt roh durchzureichen."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

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


class TestSeedOrchestration:
    """End-to-end-Ablauf (Warten -> Space aufloesen -> Ordner anlegen -> Fotos hochladen), AK aus
    specs/features/0009-local-opencloud-demo-stack.md."""

    def _photos_dir(self, tmp_path: Path) -> Path:
        photos_dir = tmp_path / "photos"
        photos_dir.mkdir()
        (photos_dir / "demo-01.jpg").write_bytes(b"new-photo")
        (photos_dir / "demo-02.jpg").write_bytes(b"existing-photo")
        return photos_dir

    async def test_full_run_uploads_and_skips(self, seed_module, tmp_path: Path) -> None:
        calls: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            if request.url.path == "/":
                return httpx.Response(200, request=request)
            if request.url.path == "/graph/v1.0/me/drives":
                return httpx.Response(200, json=_DRIVES_PAYLOAD, request=request)
            if request.method == "MKCOL":
                return httpx.Response(201, request=request)
            if request.method == "HEAD" and request.url.path.endswith("demo-01.jpg"):
                return httpx.Response(404, request=request)
            if request.method == "PUT" and request.url.path.endswith("demo-01.jpg"):
                return httpx.Response(201, request=request)
            if request.method == "HEAD" and request.url.path.endswith("demo-02.jpg"):
                return httpx.Response(200, request=request)  # existiert schon
            raise AssertionError(f"unerwarteter Request: {request.method} {request.url.path}")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            result = await seed_module.seed(
                base_url="http://opencloud-demo:9200",
                username="alan",
                app_token="demo",
                drive_name=None,
                folder_name="PhotoSort Demo",
                photos_dir=self._photos_dir(tmp_path),
                client=client,
            )
        finally:
            await client.aclose()

        assert result.uploaded == ["demo-01.jpg"]
        assert result.skipped == ["demo-02.jpg"]
        assert result.failed == []

    async def test_rejects_non_demo_url_before_any_network_call(
        self, seed_module, tmp_path: Path
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("es haette gar kein Request rausgehen duerfen")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(seed_module.SeedError):
                await seed_module.seed(
                    base_url="https://cloud.example.com",
                    username="alan",
                    app_token="demo",
                    drive_name=None,
                    folder_name="PhotoSort Demo",
                    photos_dir=self._photos_dir(tmp_path),
                    client=client,
                )
        finally:
            await client.aclose()

    async def test_fails_fast_when_no_photos_bundled(self, seed_module, tmp_path: Path) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("es haette gar kein Request rausgehen duerfen")

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(seed_module.SeedError):
                await seed_module.seed(
                    base_url="http://opencloud-demo:9200",
                    username="alan",
                    app_token="demo",
                    drive_name=None,
                    folder_name="PhotoSort Demo",
                    photos_dir=empty_dir,
                    client=client,
                )
        finally:
            await client.aclose()


class TestMain:
    def test_exits_zero_on_full_success(self, seed_module, tmp_path: Path, monkeypatch) -> None:
        photos_dir = tmp_path / "photos"
        photos_dir.mkdir()
        (photos_dir / "demo-01.jpg").write_bytes(b"content")

        async def fake_seed(**kwargs):
            return seed_module.SeedResult(uploaded=["demo-01.jpg"], skipped=[], failed=[])

        monkeypatch.setattr(seed_module, "seed", fake_seed)

        exit_code = seed_module.main(["--photos-dir", str(photos_dir)])

        assert exit_code == 0

    def test_exits_nonzero_on_seed_error(self, seed_module, monkeypatch) -> None:
        async def fake_seed(**kwargs):
            raise seed_module.SeedError("boom")

        monkeypatch.setattr(seed_module, "seed", fake_seed)

        exit_code = seed_module.main([])

        assert exit_code == 1

    def test_exits_nonzero_when_everything_failed(self, seed_module, monkeypatch) -> None:
        async def fake_seed(**kwargs):
            return seed_module.SeedResult(uploaded=[], skipped=[], failed=["demo-01.jpg"])

        monkeypatch.setattr(seed_module, "seed", fake_seed)

        exit_code = seed_module.main([])

        assert exit_code == 1

    def test_defaults_match_demo_container(self, seed_module) -> None:
        args = seed_module.build_arg_parser().parse_args([])
        assert args.base_url == "http://opencloud-demo:9200"
        assert args.username == "alan"
        assert args.app_token == "demo"
        assert args.folder_name == "PhotoSort Demo"

    def test_forwards_cli_args_unchanged_to_seed(self, seed_module, monkeypatch) -> None:
        """Findet z.B. einen Bug wie username=args.app_token, den ein reines
        "wirft nicht"-Assertion nicht aufdecken wuerde (Review-Finding test-engineer)."""
        captured: dict = {}

        async def fake_seed(**kwargs):
            captured.update(kwargs)
            return seed_module.SeedResult(uploaded=["x"], skipped=[], failed=[])

        monkeypatch.setattr(seed_module, "seed", fake_seed)

        seed_module.main(
            [
                "--base-url",
                "http://opencloud-demo:9999",
                "--username",
                "the-user",
                "--app-token",
                "the-token",
                "--drive-name",
                "the-drive",
                "--folder-name",
                "the-folder",
                "--photos-dir",
                "/some/dir",
                "--max-wait-attempts",
                "7",
                "--poll-interval",
                "1.5",
            ]
        )

        assert captured["base_url"] == "http://opencloud-demo:9999"
        assert captured["username"] == "the-user"
        assert captured["app_token"] == "the-token"
        assert captured["drive_name"] == "the-drive"
        assert captured["folder_name"] == "the-folder"
        assert str(captured["photos_dir"]) == "/some/dir"
        assert captured["max_wait_attempts"] == 7
        assert captured["poll_interval"] == 1.5

    def test_empty_drive_name_env_becomes_none(self, seed_module) -> None:
        """docker-compose.demo.yml setzt OPENCLOUD_DRIVE_NAME als leeren String
        (${OPENCLOUD_DRIVE_NAME:-}), damit resolve_drive_webdav_url automatisch das
        persoenliche Drive waehlt statt nach einem leeren Namen zu suchen."""
        # Simuliert das Compose-Verhalten direkt ueber os.environ, ohne echten Prozessstart.
        import os

        old = os.environ.get("OPENCLOUD_DRIVE_NAME")
        os.environ["OPENCLOUD_DRIVE_NAME"] = ""
        try:
            args = seed_module.build_arg_parser().parse_args([])
        finally:
            if old is None:
                os.environ.pop("OPENCLOUD_DRIVE_NAME", None)
            else:
                os.environ["OPENCLOUD_DRIVE_NAME"] = old

        assert args.drive_name is None
