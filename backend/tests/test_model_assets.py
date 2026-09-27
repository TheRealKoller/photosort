"""Manifest und Ladeprogramm der geladenen Modell-Assets (Auflage S13).

Das Manifest `model_assets.py` ist die einzige Stelle, an der Hash, Groesse und Bezugsadresse
einer nicht eingecheckten Modelldatei stehen. Das Ladeprogramm `backend/scripts/
fetch_model_assets.py` laeuft hier nur mit eingeschleustem Oeffner; die Netzsperre aus
`conftest.py` gilt unveraendert.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import re
import urllib.request
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from photosort.model_assets import (
    ASSETS_DIR,
    FACE_DETECTOR,
    FACE_RECOGNIZER,
    LABEL_EMBEDDER_ONNX,
    MODEL_ASSETS,
    ModelAsset,
)
from tests.import_closure import SRC_DIR

BACKEND_DIR = Path(__file__).resolve().parents[1]
FETCH_SCRIPT = BACKEND_DIR / "scripts" / "fetch_model_assets.py"

_PINNED_URL = re.compile(r"\Ahttps://huggingface\.co/[^/]+/[^/]+/resolve/[0-9a-f]{40}/[^?#]+\Z")


def _fetch_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fetch_model_assets", FETCH_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestTheManifest:
    def test_it_lists_the_label_embedder_and_both_face_models(self) -> None:
        assert {asset.filename for asset in MODEL_ASSETS} == {
            "label_embedder.onnx",
            "face_detection_yunet_2023mar.onnx",
            "face_recognition_sface_2021dec.onnx",
        }

    @pytest.mark.parametrize("asset", MODEL_ASSETS, ids=lambda asset: asset.filename)
    def test_every_entry_is_pinned_to_a_fixed_revision_over_https(self, asset: ModelAsset) -> None:
        assert _PINNED_URL.match(asset.url), asset.url
        assert "/resolve/main/" not in asset.url
        assert re.fullmatch(r"[0-9a-f]{64}", asset.sha256)
        assert asset.size > 0
        assert "/" not in asset.filename

    def test_the_manifest_hashes_and_urls_stand_nowhere_else_in_the_source_tree(self) -> None:
        """S13: Hash und URL sind Konstanten des Manifests, keine zweite Stelle fuehrt sie."""
        pinned = {asset.sha256 for asset in MODEL_ASSETS} | {asset.url for asset in MODEL_ASSETS}
        naming = sorted(
            path.relative_to(SRC_DIR).as_posix()
            for path in SRC_DIR.rglob("*.py")
            if any(value in path.read_text(encoding="utf-8") for value in pinned)
        )

        assert naming == ["photosort/model_assets.py"]

    def test_the_manifest_reads_neither_environment_nor_settings(self) -> None:
        tree = ast.parse((SRC_DIR / "photosort" / "model_assets.py").read_text(encoding="utf-8"))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}

        assert imported <= {"__future__", "dataclasses", "pathlib"}

    def test_the_label_embedder_takes_its_file_from_the_manifest(self) -> None:
        from photosort.label_embedding import LABEL_EMBEDDER_ONNX_PATH

        assert LABEL_EMBEDDER_ONNX_PATH == ASSETS_DIR / LABEL_EMBEDDER_ONNX.filename


class TestTheDownloadedAssets:
    """Integritaet gegen das Manifest - Muster `TestLabelEmbedderAssets`."""

    @pytest.mark.parametrize(
        "asset", (FACE_DETECTOR, FACE_RECOGNIZER), ids=lambda asset: asset.filename
    )
    def test_the_file_matches_the_manifest(self, asset: ModelAsset) -> None:
        content = (ASSETS_DIR / asset.filename).read_bytes()

        assert len(content) == asset.size
        assert hashlib.sha256(content).hexdigest() == asset.sha256


class _Response(io.BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _asset(content: bytes, *, url: str | None = None, sha256: str | None = None) -> ModelAsset:
    return ModelAsset(
        filename="modell.onnx",
        url=url or "https://huggingface.co/owner/repo/resolve/" + "a" * 40 + "/modell.onnx",
        size=len(content),
        sha256=sha256 or hashlib.sha256(content).hexdigest(),
    )


def _recording_opener(content: bytes) -> tuple[list[str], Callable[[str, float], Any]]:
    calls: list[str] = []

    def open_url(url: str, timeout: float) -> _Response:
        calls.append(url)
        return _Response(content)

    return calls, open_url


class TestTheLoader:
    def test_a_correct_file_already_present_makes_no_request(self, tmp_path: Path) -> None:
        fetch = _fetch_module()
        content = b"gewichte"
        (tmp_path / "modell.onnx").write_bytes(content)
        calls, open_url = _recording_opener(content)

        assert fetch.fetch_asset(_asset(content), tmp_path, open_url=open_url) is False

        assert calls == []

    def test_a_correct_download_lands_at_the_target_and_leaves_no_temporary_file(
        self, tmp_path: Path
    ) -> None:
        fetch = _fetch_module()
        content = b"gewichte"
        calls, open_url = _recording_opener(content)

        assert fetch.fetch_asset(_asset(content), tmp_path, open_url=open_url) is True

        assert (tmp_path / "modell.onnx").read_bytes() == content
        assert sorted(path.name for path in tmp_path.iterdir()) == ["modell.onnx"]
        assert len(calls) == 1

    def test_a_wrong_hash_leaves_no_file_at_the_target(self, tmp_path: Path) -> None:
        fetch = _fetch_module()
        _, open_url = _recording_opener(b"manipuliert")
        asset = _asset(b"manipuliert", sha256="0" * 64)

        with pytest.raises(fetch.AssetFetchError):
            fetch.fetch_asset(asset, tmp_path, open_url=open_url)

        assert list(tmp_path.iterdir()) == []

    def test_a_wrong_hash_replaces_no_existing_file(self, tmp_path: Path) -> None:
        """Erst nach bestandener Pruefung wird ersetzt - eine vorhandene, falsche Datei bleibt
        nicht halb ueberschrieben zurueck, sie bleibt unberuehrt."""
        fetch = _fetch_module()
        (tmp_path / "modell.onnx").write_bytes(b"alt")
        _, open_url = _recording_opener(b"manipuliert")

        with pytest.raises(fetch.AssetFetchError):
            fetch.fetch_asset(_asset(b"x", sha256="0" * 64), tmp_path, open_url=open_url)

        assert (tmp_path / "modell.onnx").read_bytes() == b"alt"
        assert sorted(path.name for path in tmp_path.iterdir()) == ["modell.onnx"]

    def test_more_bytes_than_the_manifest_size_are_refused(self, tmp_path: Path) -> None:
        fetch = _fetch_module()
        asset = _asset(b"gewichte")
        _, open_url = _recording_opener(b"gewichte und noch mehr")

        with pytest.raises(fetch.AssetFetchError):
            fetch.fetch_asset(asset, tmp_path, open_url=open_url)

        assert list(tmp_path.iterdir()) == []

    def test_an_http_url_is_refused_before_any_request(self, tmp_path: Path) -> None:
        fetch = _fetch_module()
        calls, open_url = _recording_opener(b"gewichte")
        asset = _asset(b"gewichte", url="http://huggingface.co/owner/repo/resolve/x/modell.onnx")

        with pytest.raises(fetch.AssetFetchError):
            fetch.fetch_asset(asset, tmp_path, open_url=open_url)

        assert calls == []
        assert list(tmp_path.iterdir()) == []

    def test_a_redirect_to_another_scheme_is_refused(self) -> None:
        fetch = _fetch_module()
        handler = fetch.HttpsOnlyRedirectHandler()
        request = urllib.request.Request("https://huggingface.co/a")

        with pytest.raises(fetch.AssetFetchError):
            handler.redirect_request(request, None, 302, "Found", {}, "http://cdn.example/a")

    def test_a_redirect_within_https_is_followed(self) -> None:
        fetch = _fetch_module()
        handler = fetch.HttpsOnlyRedirectHandler()
        request = urllib.request.Request("https://huggingface.co/a")

        followed = handler.redirect_request(
            request, None, 302, "Found", {}, "https://cdn.example/a"
        )

        assert followed is not None
        assert followed.full_url == "https://cdn.example/a"

    def test_main_exits_non_zero_and_names_the_file_on_a_mismatch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fetch = _fetch_module()
        _, open_url = _recording_opener(b"manipuliert")

        exit_code = fetch.main(
            target_dir=tmp_path, assets=(_asset(b"x", sha256="0" * 64),), open_url=open_url
        )

        assert exit_code != 0
        assert "modell.onnx" in capsys.readouterr().err
        assert list(tmp_path.iterdir()) == []

    def test_main_takes_its_assets_from_the_manifest(self) -> None:
        fetch = _fetch_module()

        assert [asset.filename for asset in fetch.manifest_assets()] == [
            asset.filename for asset in MODEL_ASSETS
        ]

    def test_no_application_module_imports_the_loader(self) -> None:
        """S13: Kein Anwendungsmodul laedt selbst oder importiert das Ladeprogramm. Ueber den
        Syntaxbaum, nicht per Substring - ein Kommentar darf das Ladeprogramm nennen."""
        importing = sorted(
            path.name
            for path in SRC_DIR.rglob("*.py")
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if (
                isinstance(node, ast.Import)
                and any("fetch_model_assets" in alias.name for alias in node.names)
            )
            or (isinstance(node, ast.ImportFrom) and "fetch_model_assets" in (node.module or ""))
        )

        assert importing == []
