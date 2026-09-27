"""Laedt die Modelldateien aus dem Manifest `src/photosort/model_assets.py` und prueft sie.

Aufruf im Ordner `backend/` (Image-Build, CI, Bare-Metal-Setup)::

    python scripts/fetch_model_assets.py

Zusagen (Spec 0292, Auflage S13):

* Nur Standardbibliothek. Das Manifest wird ueber seinen Dateipfad gelesen, nicht ueber das
  installierte Paket - das Programm laeuft vor `pip install .`.
* Nur `https`, auch bei Umleitungen; eine Umleitung auf ein anderes Schema bricht ab. Sonst koennte
  ein Vermittler auf dem Pfad die Uebertragung auf Klartext herabstufen.
* Gelesen wird hoechstens die im Manifest genannte Groesse, mit Timeout.
* Geschrieben wird in eine temporaere Datei im Zielverzeichnis; an den Zielpfad kommt sie erst nach
  bestandener Groessen- und SHA256-Pruefung per `os.replace`. Bei Abweichung wird die temporaere
  Datei geloescht und mit Exit != 0 abgebrochen, ohne Fallback - eine vorhandene Datei am Zielpfad
  bleibt dann unberuehrt.
* Liegt die Datei bereits mit passendem Hash vor, entsteht keine Anfrage.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import tempfile
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, BinaryIO

BACKEND_DIR = Path(__file__).resolve().parents[1]
MANIFEST_PATH = BACKEND_DIR / "src" / "photosort" / "model_assets.py"
TIMEOUT_SECONDS = 60.0
_CHUNK_BYTES = 1024 * 1024

OpenUrl = Callable[[str, float], Any]


class AssetFetchError(Exception):
    """Ein Asset konnte nicht geladen oder nicht bestaetigt werden."""


class HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Folgt einer Umleitung nur, wenn ihr Ziel wieder `https` ist."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        if not newurl.startswith("https://"):
            raise AssetFetchError("Umleitung auf ein anderes Schema als https abgewiesen.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open_https(url: str, timeout: float) -> Any:
    opener = urllib.request.build_opener(HttpsOnlyRedirectHandler())
    return opener.open(url, timeout=timeout)


def _load_manifest() -> ModuleType:
    spec = importlib.util.spec_from_file_location("photosort_model_assets", MANIFEST_PATH)
    if spec is None or spec.loader is None:
        raise AssetFetchError(f"Manifest nicht lesbar: {MANIFEST_PATH}")
    module = importlib.util.module_from_spec(spec)
    # `dataclasses` sucht die Klasse beim Aufbau in `sys.modules`.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def manifest_assets() -> tuple[Any, ...]:
    return tuple(_load_manifest().MODEL_ASSETS)


def default_target_dir() -> Path:
    return Path(_load_manifest().ASSETS_DIR)


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_bounded(source: BinaryIO, target: BinaryIO, limit: int) -> tuple[int, str]:
    """Kopiert hoechstens `limit + 1` Bytes - das eine Byte mehr weist eine zu grosse Antwort
    nach, ohne sie ganz zu lesen."""
    digest = hashlib.sha256()
    copied = 0
    while copied <= limit:
        chunk = source.read(min(_CHUNK_BYTES, limit + 1 - copied))
        if not chunk:
            break
        digest.update(chunk)
        target.write(chunk)
        copied += len(chunk)
    return copied, digest.hexdigest()


def fetch_asset(asset: Any, target_dir: Path, *, open_url: OpenUrl = _open_https) -> bool:
    """Stellt ein Asset am Zielpfad sicher. `True` heisst geladen, `False` schon vorhanden."""
    target = target_dir / asset.filename
    if target.is_file() and _sha256_of(target) == asset.sha256:
        return False
    if not asset.url.startswith("https://"):
        raise AssetFetchError(f"{asset.filename}: nur https ist zulaessig.")

    target_dir.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(dir=target_dir, prefix=f".{asset.filename}.")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as written, open_url(asset.url, TIMEOUT_SECONDS) as response:
            size, sha256 = _copy_bounded(response, written, asset.size)
        if size != asset.size or sha256 != asset.sha256:
            raise AssetFetchError(
                f"{asset.filename}: Groesse oder SHA256 weicht vom Manifest ab, verworfen."
            )
        # `mkstemp` legt 0600 an; das Image liest die Datei unter einem anderen Nutzer.
        temporary.chmod(0o644)
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return True


def main(
    *,
    target_dir: Path | None = None,
    assets: Sequence[Any] | None = None,
    open_url: OpenUrl = _open_https,
) -> int:
    directory = target_dir if target_dir is not None else default_target_dir()
    for asset in assets if assets is not None else manifest_assets():
        try:
            loaded = fetch_asset(asset, directory, open_url=open_url)
        except (AssetFetchError, OSError) as exc:
            print(f"Fehler: {asset.filename}: {exc}", file=sys.stderr)
            return 1
        state = "geladen und geprueft" if loaded else "liegt bereits geprueft vor"
        print(f"{asset.filename}: {state}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
