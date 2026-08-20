from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from photosort.api.deps import get_current_user, get_opencloud_client
from photosort.config import settings
from photosort.opencloud.client import IMAGE_EXTENSIONS, OpenCloudClient, OpenCloudError

router = APIRouter(
    prefix="/opencloud", tags=["opencloud"], dependencies=[Depends(get_current_user)]
)

# Reiner Anzeige-/UX-Wert ohne betriebliche Tuning-Notwendigkeit (specs/features/0050-dateianzahl-
# im-ordner-browser.md, ADR decisions/0028-ordner-browser-bilddatei-zaehlung.md Punkt 5) - anders
# als settings.opencloud_folder_count_concurrency deshalb eine Modul-Konstante statt eines
# Settings-Felds, analog worker.py::SCAN_COMMIT_BATCH_SIZE.
FOLDER_COUNT_LIMIT = 500


class BrowseEntry(BaseModel):
    name: str
    path: str


class FolderCountOut(BaseModel):
    """Bewusst kein Freitext-/Meldungsfeld (Security-Abschnitt der Spec) - error=True
    transportiert kein str(exc) an den Client."""

    path: str
    count: int
    at_limit: bool
    error: bool


@router.get("/browse", response_model=list[BrowseEntry])
async def browse_folder(
    path: str = "",
    client: OpenCloudClient = Depends(get_opencloud_client),
) -> list[BrowseEntry]:
    try:
        drive = await client.resolve_drive(settings.opencloud_drive_name or None)
        entries = await client.list_folder(drive.webdav_url, path)
    except OpenCloudError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    base = path.strip("/")
    return [
        BrowseEntry(name=entry.name, path=f"{base}/{entry.name}".strip("/"))
        for entry in entries
        if entry.is_collection
    ]


async def _count_images_up_to_limit(
    client: OpenCloudClient, webdav_url: str, path: str, limit: int
) -> tuple[int, bool]:
    """Konsumiert client.walk() (bestehende BFS-Traversierung mit Zyklenschutz, Endpunkt-lokale
    Geschaeftslogik, siehe ADR decisions/0028 Punkt 1) und zaehlt nur Bilddateien
    (IMAGE_EXTENSIONS). Bricht die async-for-Schleife ab, sobald limit erreicht ist - walk() ist
    ein Async-Generator,
    der ab diesem Punkt keine weiteren PROPFIND-Anfragen mehr stellt (echter Early-Exit auf
    Netzwerkebene, kein "erst alles traversieren und danach kappen"). Haelt bewusst keinen eigenen
    visited-Zustand - der Zyklenschutz von walk() bleibt dadurch unveraendert wirksam."""
    count = 0
    async for relative_path, _entry in client.walk(webdav_url, path):
        extension = os.path.splitext(relative_path)[1].lower()
        if extension not in IMAGE_EXTENSIONS:
            continue
        count += 1
        if count >= limit:
            return count, True
    return count, False


async def _count_subfolder(
    client: OpenCloudClient, webdav_url: str, path: str, semaphore: asyncio.Semaphore
) -> tuple[int, bool]:
    async with semaphore:
        return await _count_images_up_to_limit(client, webdav_url, path, FOLDER_COUNT_LIMIT)


@router.get("/folder-counts", response_model=list[FolderCountOut])
async def folder_counts(
    path: str = "",
    client: OpenCloudClient = Depends(get_opencloud_client),
) -> list[FolderCountOut]:
    try:
        drive = await client.resolve_drive(settings.opencloud_drive_name or None)
        entries = await client.list_folder(drive.webdav_url, path)
    except OpenCloudError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    base = path.strip("/")
    subfolder_paths = [
        f"{base}/{entry.name}".strip("/") for entry in entries if entry.is_collection
    ]

    # Serverseitige Gesamt-Nebenlaeufigkeit ueber ALLE Unterordner-Zaehlungen dieses Requests
    # hinweg (nicht pro Unterordner) - der eigentliche Grund fuer den Batch- statt
    # Einzel-Request-Endpunkt (ADR decisions/0028 Punkt 2).
    semaphore = asyncio.Semaphore(settings.opencloud_folder_count_concurrency)
    raw_results = await asyncio.gather(
        *(
            _count_subfolder(client, drive.webdav_url, subfolder_path, semaphore)
            for subfolder_path in subfolder_paths
        ),
        return_exceptions=True,
    )

    # Verifizierter Python-Async-Fallstrick (siehe worker.py::_process_scan_block, ADR 0020):
    # return_exceptions=True faengt ein CancelledError einer einzelnen Kind-Coroutine NICHT als
    # Exception ab, sondern reicht es als gewoehnliches Ergebniselement durch - das muss weiterhin
    # propagieren (z.B. bei einem echten Request-Abbruch), statt als error=True verschluckt zu
    # werden.
    for raw_result in raw_results:
        if isinstance(raw_result, asyncio.CancelledError):
            raise raw_result

    results: list[FolderCountOut] = []
    for subfolder_path, raw_result in zip(subfolder_paths, raw_results, strict=True):
        if isinstance(raw_result, BaseException):
            # Einzelner Unterordner-Zaehlfehler (z.B. Netzwerkfehler mitten in dessen
            # Traversierung) blockiert weder die uebrigen Zaehler noch die Gesamtantwort (ADR
            # decisions/0028 Punkt 4) - nur das vorgelagerte Listing oben liefert einen echten 400.
            results.append(
                FolderCountOut(path=subfolder_path, count=0, at_limit=False, error=True)
            )
            continue
        count, at_limit = raw_result
        results.append(
            FolderCountOut(path=subfolder_path, count=count, at_limit=at_limit, error=False)
        )
    return results
