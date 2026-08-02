#!/usr/bin/env python3
"""Seeds a local OpenCloud demo container with a small set of bundled example photos.

Eigenstaendiges Dev-/Demo-Tooling, bewusst ausserhalb von backend/src/photosort/ (siehe
specs/features/0009-local-opencloud-demo-stack.md,
specs/decisions/0009-local-opencloud-demo-stack.md,
specs/decisions/0010-demo-seed-script-as-compose-service.md). Laeuft als eigener Compose-Service
(profile "seed") im selben Docker-Netzwerk wie der opencloud-demo-Container - siehe README.md.

Spricht denselben Graph-API-/WebDAV-Codepfad wie das Produktiv-Backend
(backend/src/photosort/opencloud/client.py) direkt per httpx an, nutzt aber bewusst KEINEN Import
von dort (eigenstaendiges Tool, kein Upload-Feature im Produktivcode - siehe ADR 0009).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})
DEFAULT_PHOTOS_DIR = Path(__file__).parent / "demo_photos"

# Standardwerte fuer die Warte-/Retry-Logik: 40 Versuche a 3s Wartezeit dazwischen ergeben ein
# Timeout von ca. 120s (AK aus specs/features/0009-local-opencloud-demo-stack.md: "innerhalb
# einer definierten Zeitspanne (z.B. 120s)").
DEFAULT_MAX_WAIT_ATTEMPTS = 40
DEFAULT_POLL_INTERVAL = 3.0

# Hostnamen, die als "eindeutig der lokale Demo-Container" gelten (Security-Muss-Kriterium,
# specs/architecture/0003-securitykonzept.md, Abschnitt "Docker-Compose-Netzwerk"):
# "opencloud-demo" ist der Servicename im gemeinsamen Compose-Netzwerk (siehe ADR 0010, der
# Normalfall bei Ausfuehrung als "seed"-Compose-Service); "localhost"/"127.0.0.1"/"::1" decken den
# seltener genutzten Fall ab, dass jemand das Skript direkt gegen den auf 127.0.0.1 gebundenen
# Host-Port startet (z.B. fuer einen manuellen Test ausserhalb von Docker).
_DEMO_HOSTS = frozenset({"opencloud-demo", "localhost", "127.0.0.1", "::1"})


class SeedError(Exception):
    """Raised for any unrecoverable failure while seeding the demo OpenCloud space."""


def validate_demo_base_url(base_url: str) -> None:
    """Bricht mit einer klaren SeedError ab, falls `base_url` nicht offensichtlich auf den
    lokalen OpenCloud-Demo-Container zeigt - verhindert, dass ein versehentlicher Lauf mit der
    produktiven .env (echte OPENCLOUD_BASE_URL) Fotos in einen echten Familien-Space schreibt
    (Security-Muss-Kriterium, specs/features/0009-local-opencloud-demo-stack.md)."""
    parsed = urlparse(base_url)
    # Review-Finding (Copilot): ohne explizite Port-Pruefung wuerde z.B. "http://localhost"
    # (impliziter Port 80) akzeptiert, obwohl die Fehlermeldung unten selbst einen Port verlangt -
    # koennte einen ganz anderen lokalen Dienst treffen statt des tatsaechlichen Demo-Containers.
    if parsed.scheme != "http" or parsed.hostname not in _DEMO_HOSTS or parsed.port is None:
        raise SeedError(
            f"'{base_url}' sieht nicht wie der lokale OpenCloud-Demo-Container aus (erwartet: "
            f"http://<{'|'.join(sorted(_DEMO_HOSTS))}>:<port>, Port explizit angegeben). Abbruch, "
            "um nicht versehentlich in einen echten OpenCloud-Space zu schreiben. Falls dies "
            "tatsaechlich der Demo-Container ist, den Hostnamen/Port pruefen bzw. _DEMO_HOSTS "
            "anpassen."
        )


async def wait_until_ready(
    client: httpx.AsyncClient,
    base_url: str,
    *,
    max_attempts: int = DEFAULT_MAX_WAIT_ATTEMPTS,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Wartet aktiv, bis der Demo-Container antwortet, statt sofort mit Verbindungsfehler
    abzubrechen (AK aus specs/features/0009-local-opencloud-demo-stack.md). Prueft schlicht
    Erreichbarkeit der Login-Seite (kein dokumentiert stabiler /health-Endpoint fuer dieses
    Deployment-Muster bekannt) - jeder Status < 500 gilt als "Server ist da und antwortet
    sinnvoll", auch 401/403/redirects."""
    last_error: str = "unbekannter Fehler"
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.get(base_url.rstrip("/") + "/")
            if response.status_code < 500:
                return
            last_error = f"Status {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)

        if attempt < max_attempts:
            await sleep(poll_interval)

    raise SeedError(
        f"OpenCloud-Demo-Container unter {base_url} nach {max_attempts} Versuchen "
        f"(je {poll_interval}s Abstand) nicht erreichbar - letzter Fehler: {last_error}."
    )


async def fetch_drives(client: httpx.AsyncClient, base_url: str) -> list[dict]:
    """Graph-API-Space-Liste - derselbe Codepfad wie OpenCloudClient.list_drives (AK aus
    specs/features/0009-local-opencloud-demo-stack.md), eigenstaendig implementiert (kein Import
    aus backend/src/photosort, siehe ADR 0009)."""
    try:
        response = await client.get(f"{base_url.rstrip('/')}/graph/v1.0/me/drives")
    except httpx.HTTPError as exc:
        raise SeedError(f"OpenCloud nicht erreichbar: {exc}") from exc
    if response.status_code >= 400:
        raise SeedError(
            f"Graph-API-Space-Liste fehlgeschlagen: {response.status_code} {response.reason_phrase}"
        )
    payload = response.json()
    return list(payload.get("value", []))


def _drive_webdav_url(drive: Any) -> str:
    # Empirisch gegen den echten opencloud-demo-Container verifiziert (manueller Smoke-Test
    # dieser Spec, siehe Abschlussbericht): die Graph-API liefert "webDavUrl" verschachtelt unter
    # "root", nicht auf oberster Ebene des Drive-Objekts.
    #
    # drive ist bewusst nicht als dict typisiert: jede unerwartete Struktur (drive selbst kein
    # dict, "root" kein dict, fehlendes "webDavUrl") wird gleichwertig behandelt - ein
    # KeyError/TypeError hier soll immer als SeedError propagieren (siehe auch das analoge Muster
    # in backend/src/photosort/opencloud/client.py, Fund aus dem Copilot-Review von PR #12).
    try:
        return str(drive["root"]["webDavUrl"])
    except (KeyError, TypeError) as exc:
        raise SeedError(
            "Unerwartete Antwortstruktur eines OpenCloud-Spaces in der Graph-API-Antwort "
            "(fehlendes 'root.webDavUrl'-Feld)."
        ) from exc


def _drive_name(drive: Any) -> Any:
    return drive.get("name") if isinstance(drive, dict) else None


def _drive_type(drive: Any) -> Any:
    return drive.get("driveType") if isinstance(drive, dict) else None


def resolve_drive_webdav_url(drives: list[dict], drive_name: str | None) -> str:
    """Waehlt den Ziel-Space: bei explizitem Namen exaktes Match, sonst das persoenliche Drive des
    Demo-Nutzers (driveType == "personal"), sonst das erste vorhandene Drive - analog zur Absicht
    von OpenCloudClient.resolve_drive, aber eigenstaendig implementiert (siehe ADR 0009). Nutzt
    _drive_name()/_drive_type() statt drive.get(...) direkt, damit ein Nicht-dict-Eintrag in
    "drives" (z.B. ein String/int) hier nicht mit einem rohen AttributeError abbricht, sondern
    beim eigentlichen Ziel-Match einfach nicht passt und weiter unten regulaer als SeedError
    endet."""
    if not drives:
        raise SeedError("Keine OpenCloud-Spaces gefunden.")

    if drive_name:
        for drive in drives:
            if _drive_name(drive) == drive_name:
                return _drive_webdav_url(drive)
        raise SeedError(f"OpenCloud-Space '{drive_name}' wurde nicht gefunden.")

    for drive in drives:
        if _drive_type(drive) == "personal":
            return _drive_webdav_url(drive)
    return _drive_webdav_url(drives[0])


def _folder_url(webdav_url: str, folder_name: str) -> str:
    return f"{webdav_url.rstrip('/')}/{quote(folder_name)}"


def _file_url(webdav_url: str, folder_name: str, filename: str) -> str:
    return f"{_folder_url(webdav_url, folder_name)}/{quote(filename)}"


async def ensure_folder(client: httpx.AsyncClient, webdav_url: str, folder_name: str) -> None:
    """Legt den Demo-Ordner per WebDAV MKCOL an. Idempotent (AK "erneutes Ausfuehren ... erzeugt
    keine Duplikate"): ein 405 (Method Not Allowed) bedeutet laut WebDAV-Spezifikation, dass die
    Ressource bereits existiert - kein Fehler, kein erneuter Anlegeversuch noetig."""
    try:
        response = await client.request("MKCOL", _folder_url(webdav_url, folder_name))
    except httpx.HTTPError as exc:
        raise SeedError(f"Anlegen des Demo-Ordners '{folder_name}' fehlgeschlagen: {exc}") from exc
    if response.status_code == 201 or response.status_code == 405:
        return
    raise SeedError(
        f"Anlegen des Demo-Ordners '{folder_name}' fehlgeschlagen: "
        f"{response.status_code} {response.reason_phrase}"
    )


async def upload_photo(
    client: httpx.AsyncClient, webdav_url: str, folder_name: str, filename: str, content: bytes
) -> str:
    """Laedt ein einzelnes Beispielfoto per WebDAV PUT hoch. Idempotent (AK "erneutes Ausfuehren
    ... erzeugt keine Duplikate"): existiert die Datei bereits (HEAD 200), wird sie uebersprungen
    statt erneut hochgeladen. Ein einzelner fehlgeschlagener Upload bricht den Gesamtlauf nicht ab
    (siehe architecture/0002-testkonzept.md) - der Aufrufer sammelt die Ergebnisse pro Datei und
    entscheidet ueber den Gesamterfolg."""
    url = _file_url(webdav_url, folder_name, filename)
    try:
        head_response = await client.head(url)
        if head_response.status_code == 200:
            return "skipped"

        put_response = await client.put(url, content=content)
        if put_response.status_code in (200, 201, 204):
            return "uploaded"
        return "failed"
    except httpx.HTTPError:
        return "failed"


def discover_demo_photos(photos_dir: Path) -> list[Path]:
    """Findet die mitgelieferten Beispielfotos (scripts/demo_photos/ standardmaessig, siehe
    Architektur-Abschnitt der Spec) - sortiert fuer ein deterministisches Upload-/Test-Verhalten."""
    if not photos_dir.is_dir():
        raise SeedError(f"Foto-Verzeichnis '{photos_dir}' existiert nicht.")
    photos = sorted(
        p for p in photos_dir.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
    )
    if not photos:
        raise SeedError(f"Keine Beispielfotos in '{photos_dir}' gefunden.")
    return photos


@dataclass
class SeedResult:
    uploaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


async def seed(
    *,
    base_url: str,
    username: str,
    app_token: str,
    drive_name: str | None,
    folder_name: str,
    photos_dir: Path,
    max_wait_attempts: int = DEFAULT_MAX_WAIT_ATTEMPTS,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    client: httpx.AsyncClient | None = None,
) -> SeedResult:
    """Orchestriert den vollstaendigen Seed-Lauf: URL-Sicherheitscheck -> Fotos lokal
    ermitteln (fail-fast, bevor ueberhaupt ein Request rausgeht) -> auf Container warten ->
    Ziel-Space aufloesen -> Ordner anlegen -> Fotos hochladen (siehe Akzeptanzkriterien,
    specs/features/0009-local-opencloud-demo-stack.md).

    `client` ist fuer Tests injizierbar (httpx.MockTransport); ohne Angabe wird ein echter,
    Basic-Auth-authentifizierter Client erzeugt und am Ende wieder geschlossen."""
    validate_demo_base_url(base_url)
    photos = discover_demo_photos(photos_dir)

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(auth=(username, app_token), timeout=30.0)

    try:
        await wait_until_ready(
            client,
            base_url,
            max_attempts=max_wait_attempts,
            poll_interval=poll_interval,
            sleep=sleep,
        )
        drives = await fetch_drives(client, base_url)
        webdav_url = resolve_drive_webdav_url(drives, drive_name)
        await ensure_folder(client, webdav_url, folder_name)

        result = SeedResult()
        for photo in photos:
            outcome = await upload_photo(
                client, webdav_url, folder_name, photo.name, photo.read_bytes()
            )
            getattr(result, outcome).append(photo.name)
        return result
    finally:
        if owns_client:
            await client.aclose()


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI-/Env-Var-Schnittstelle. Nutzt bewusst dieselben Env-Var-Namen wie das Backend
    (OPENCLOUD_BASE_URL/OPENCLOUD_USERNAME/OPENCLOUD_APP_TOKEN/OPENCLOUD_DRIVE_NAME, siehe
    backend/src/photosort/config.py) - Defaults passen zum Demo-Container laut .env.demo.example
    und zur Ausfuehrung als eigener Compose-Service im selben Docker-Netzwerk (ADR 0010), sodass
    das Skript ohne jede manuelle Konfiguration laeuft."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default=os.environ.get("OPENCLOUD_BASE_URL", "http://opencloud-demo:9200")
    )
    parser.add_argument("--username", default=os.environ.get("OPENCLOUD_USERNAME", "alan"))
    parser.add_argument("--app-token", default=os.environ.get("OPENCLOUD_APP_TOKEN", "demo"))
    parser.add_argument(
        "--drive-name", default=os.environ.get("OPENCLOUD_DRIVE_NAME") or None
    )
    parser.add_argument("--folder-name", default="PhotoSort Demo")
    parser.add_argument("--photos-dir", default=str(DEFAULT_PHOTOS_DIR))
    parser.add_argument("--max-wait-attempts", type=int, default=DEFAULT_MAX_WAIT_ATTEMPTS)
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        result = asyncio.run(
            seed(
                base_url=args.base_url,
                username=args.username,
                app_token=args.app_token,
                drive_name=args.drive_name,
                folder_name=args.folder_name,
                photos_dir=Path(args.photos_dir),
                max_wait_attempts=args.max_wait_attempts,
                poll_interval=args.poll_interval,
            )
        )
    except SeedError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1

    print(
        f"Hochgeladen: {len(result.uploaded)}, "
        f"uebersprungen (bereits vorhanden): {len(result.skipped)}, "
        f"fehlgeschlagen: {len(result.failed)}"
    )
    if result.failed:
        print(f"Fehlgeschlagene Dateien: {', '.join(result.failed)}", file=sys.stderr)
    if not result.uploaded and not result.skipped:
        print(
            "FEHLER: keine einzige Datei erfolgreich hochgeladen oder bereits vorhanden.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
