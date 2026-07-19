from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from photosort.api.deps import get_opencloud_client
from photosort.config import settings
from photosort.opencloud.client import OpenCloudClient, OpenCloudError

router = APIRouter(prefix="/opencloud", tags=["opencloud"])


class BrowseEntry(BaseModel):
    name: str
    path: str


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
