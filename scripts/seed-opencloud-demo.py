#!/usr/bin/env python3
"""Seeds a local OpenCloud demo container with a small set of bundled example photos.

Eigenstaendiges Dev-/Demo-Tooling, bewusst ausserhalb von backend/src/photosort/ (siehe
specs/features/0009-local-opencloud-demo-stack.md, specs/decisions/0009-local-opencloud-demo-stack.md,
specs/decisions/0010-demo-seed-script-as-compose-service.md). Laeuft als eigener Compose-Service
(profile "seed") im selben Docker-Netzwerk wie der opencloud-demo-Container - siehe README.md.

Spricht denselben Graph-API-/WebDAV-Codepfad wie das Produktiv-Backend
(backend/src/photosort/opencloud/client.py) direkt per httpx an, nutzt aber bewusst KEINEN Import
von dort (eigenstaendiges Tool, kein Upload-Feature im Produktivcode - siehe ADR 0009).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from urllib.parse import quote, urlparse

import httpx

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
    if parsed.scheme != "http" or parsed.hostname not in _DEMO_HOSTS:
        raise SeedError(
            f"'{base_url}' sieht nicht wie der lokale OpenCloud-Demo-Container aus (erwartet: "
            f"http://<{'|'.join(sorted(_DEMO_HOSTS))}>:<port>). Abbruch, um nicht versehentlich "
            "in einen echten OpenCloud-Space zu schreiben. Falls dies tatsaechlich der "
            "Demo-Container ist, den Hostnamen pruefen bzw. _DEMO_HOSTS anpassen."
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


def resolve_drive_webdav_url(drives: list[dict], drive_name: str | None) -> str:
    """Waehlt den Ziel-Space: bei explizitem Namen exaktes Match, sonst das persoenliche Drive des
    Demo-Nutzers (driveType == "personal"), sonst das erste vorhandene Drive - analog zu
    OpenCloudClient.resolve_drive, aber eigenstaendig implementiert (siehe ADR 0009)."""
    if not drives:
        raise SeedError("Keine OpenCloud-Spaces gefunden.")

    if drive_name:
        for drive in drives:
            if drive.get("name") == drive_name:
                return str(drive["webDavUrl"])
        raise SeedError(f"OpenCloud-Space '{drive_name}' wurde nicht gefunden.")

    for drive in drives:
        if drive.get("driveType") == "personal":
            return str(drive["webDavUrl"])
    return str(drives[0]["webDavUrl"])


def _folder_url(webdav_url: str, folder_name: str) -> str:
    return f"{webdav_url.rstrip('/')}/{quote(folder_name)}"


def _file_url(webdav_url: str, folder_name: str, filename: str) -> str:
    return f"{_folder_url(webdav_url, folder_name)}/{quote(filename)}"


async def ensure_folder(client: httpx.AsyncClient, webdav_url: str, folder_name: str) -> None:
    """Legt den Demo-Ordner per WebDAV MKCOL an. Idempotent (AK "erneutes Ausfuehren ... erzeugt
    keine Duplikate"): ein 405 (Method Not Allowed) bedeutet laut WebDAV-Spezifikation, dass die
    Ressource bereits existiert - kein Fehler, kein erneuter Anlegeversuch noetig."""
    response = await client.request("MKCOL", _folder_url(webdav_url, folder_name))
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
