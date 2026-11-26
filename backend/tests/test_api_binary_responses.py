"""Die drei Binaerendpunkte: Beschreibung ohne behaupteten JSON-Koerper, Kopfzeilen am Handler.

`response_class` dokumentiert den Antworttyp - die Handler bauen ihr `FileResponse`/`Response`
weiterhin selbst. Fuer `GET /photos/{photo_id}/image` fehlte bisher ein Kopfzeilen-Test; ohne ihn
faellt ein verlorenes `nosniff` an keiner Stelle auf.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.config import settings
from photosort.main import create_app
from photosort.thumbnails import thumbnail_path
from tests.project_graph import build_project_graph

BINAER = (
    ("/photos/{photo_id}/image", "get"),
    ("/photos/{photo_id}/faces/{index}/image", "get"),
    ("/projects/{project_id}/classification-reviews/{review_id}/export", "get"),
)


def _spec() -> dict[str, Any]:
    spec: dict[str, Any] = create_app().openapi()
    return spec


@pytest.mark.parametrize(("pfad", "methode"), BINAER)
def test_the_description_declares_no_json_body(pfad: str, methode: str) -> None:
    for status_code, antwort in _spec()["paths"][pfad][methode]["responses"].items():
        if str(status_code).startswith("2"):
            assert "content" not in antwort or antwort["content"] == {}, (pfad, status_code)


async def test_the_photo_image_is_jpeg_with_nosniff(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path))
    graph = await build_project_graph(db_session, "Weg")
    thumbnail_path(tmp_path, graph.photo_id, graph.photo_etag).write_bytes(b"jpeg-bytes")
    await db_session.commit()

    antwort = await authenticated_api_client.get(
        f"/photos/{graph.photo_id}/image", params={"variant": "thumbnail"}
    )

    assert antwort.status_code == 200
    assert antwort.headers["content-type"] == "image/jpeg"
    assert antwort.headers["x-content-type-options"] == "nosniff"
    assert antwort.content == b"jpeg-bytes"
