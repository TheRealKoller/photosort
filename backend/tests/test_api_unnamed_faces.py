"""`GET /projects/{id}/unnamed-faces` - "Ohne Namen" auf Anfrage, seitenweise, ohne zu schreiben.

Aufbau aus `tests/person_stack.py`: dateibasierte SQLite, je Anfrage eine eigene Sitzung,
`get_session` und `get_session_factory` auf derselben Engine. Der Analyzer ist der Fake aus
`tests/face_fakes.py`; er erkennt ein Foto an der Vollfarbe seiner Display-Variante.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import sqlite3
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from PIL import Image
from sqlalchemy import select

from photosort.api import persons as persons_api
from photosort.config import settings
from photosort.db import Base
from photosort.face_analysis import FaceBox
from photosort.main import app
from photosort.models import PhotoPersonCorrection, PhotoPersonDetection
from photosort.person_matching import MAX_FACES_PER_PHOTO
from tests.face_fakes import (
    BOX_SENTINEL_TEXT,
    Color,
    FakeFaceAnalyzer,
    face_box,
    face_embedding,
    sentinel_box,
)
from tests.person_stack import NOW, PersonStack, person_stack

MAX_ID = 1_000_000_000
PAGE = persons_api.UNNAMED_PAGE_MAX_PHOTOS
ANCHOR: Color = (240, 240, 20)
RED: Color = (220, 20, 20)
GREEN: Color = (20, 220, 20)
BLUE: Color = (20, 20, 220)
UNKNOWN = [face_embedding(10), face_embedding(11), face_embedding(12)]


@pytest.fixture
def analyzer() -> FakeFaceAnalyzer:
    return FakeFaceAnalyzer(
        {ANCHOR: [face_embedding(0), face_embedding(1)], RED: UNKNOWN, GREEN: [], BLUE: UNKNOWN}
    )


@pytest_asyncio.fixture
async def stack(
    tmp_path: Path, analyzer: FakeFaceAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[PersonStack]:
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path / "cache"))
    async for built in person_stack(tmp_path, analyzer):
        yield built


async def _page(
    stack: PersonStack, project_id: int, after_id: int = 0, max_photos: int | None = None
) -> dict[str, Any]:
    params: dict[str, int] = {"after_id": after_id}
    if max_photos is not None:
        params["max_photos"] = max_photos
    response = await stack.client.get(f"/projects/{project_id}/unnamed-faces", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def _all_pages(stack: PersonStack, project_id: int) -> list[dict[str, Any]]:
    pages = [await _page(stack, project_id)]
    while pages[-1]["next_after_id"] is not None:
        pages.append(await _page(stack, project_id, pages[-1]["next_after_id"]))
    return pages


def _faces(page: dict[str, Any]) -> list[tuple[int, int]]:
    return [(face["photo_id"], face["face_index"]) for face in page["faces"]]


async def _anchored(stack: PersonStack) -> tuple[int, int]:
    """Anna und Berta, festgelegt auf einem Foto eines eigenen Anker-Projekts."""
    anchor_project = await stack.project("Anker")
    anchor = await stack.photo(anchor_project, "anker", ANCHOR)
    return await stack.define("Anna", 0, anchor), await stack.define("Berta", 1, anchor)


async def _detect(stack: PersonStack, photo_id: int, person_id: int, box: FaceBox | None) -> None:
    async with stack.factory() as session:
        session.add(
            PhotoPersonDetection(
                photo_id=photo_id,
                person_id=person_id,
                computed_at=NOW,
                face_box_x=None if box is None else box.x,
                face_box_y=None if box is None else box.y,
                face_box_width=None if box is None else box.width,
                face_box_height=None if box is None else box.height,
            )
        )
        await session.commit()


async def _table_snapshot(stack: PersonStack) -> dict[str, list[tuple[Any, ...]]]:
    async with stack.factory() as session:
        return {
            table.name: sorted(
                (tuple(row) for row in (await session.execute(select(table))).all()), key=repr
            )
            for table in Base.metadata.sorted_tables
        }


# --- Menge je Foto ----------------------------------------------------------------------------


async def test_the_set_per_photo_follows_the_rule_of_the_assigned_face(stack: PersonStack) -> None:
    anna, berta = await _anchored(stack)
    project = await stack.project()
    names = ["erkannt-mit-box", "erkannt-ohne-box", "ganzes-foto", "entfernt", "zwei-personen"]
    photos = {name: await stack.photo(project, name, RED) for name in names}
    await _detect(stack, photos["erkannt-mit-box"], anna, face_box(0))
    await _detect(stack, photos["erkannt-ohne-box"], anna, None)
    await _detect(stack, photos["entfernt"], anna, face_box(1))
    await _detect(stack, photos["zwei-personen"], anna, face_box(0))
    await _detect(stack, photos["zwei-personen"], berta, face_box(2))
    await stack.client.put(
        f"/photos/{photos['ganzes-foto']}/persons/{anna}", json={"applies": True}
    )
    await stack.client.put(f"/photos/{photos['entfernt']}/persons/{anna}", json={"applies": False})

    [page] = await _all_pages(stack, project)

    by_photo: dict[int, list[int]] = {photo: [] for photo in photos.values()}
    for photo_id, index in _faces(page):
        by_photo[photo_id].append(index)
    assert by_photo == {
        photos["erkannt-mit-box"]: [1, 2],
        photos["erkannt-ohne-box"]: [0, 1, 2],
        photos["ganzes-foto"]: [0, 1, 2],
        photos["entfernt"]: [0, 1, 2],
        photos["zwei-personen"]: [1],
    }


async def test_the_listing_and_the_assigned_faces_make_up_the_detail_view(
    stack: PersonStack, analyzer: FakeFaceAnalyzer
) -> None:
    """Differenzprobe: je Foto ist die Auflistung vereinigt mit den zugeordneten Indizes die Menge
    aus `GET /photos/{id}/faces`, disjunkt - auch bei 21 Gesichtern, von denen beide 20 kennen."""
    anna, _ = await _anchored(stack)
    analyzer.faces_by_color = {
        **analyzer.faces_by_color,
        GREEN: [face_embedding(20 + index) for index in range(MAX_FACES_PER_PHOTO + 1)],
    }
    analyzer.boxes_by_color = {
        GREEN: [
            FaceBox(x=0.04 * index, y=0.0, width=0.03, height=0.03)
            for index in range(MAX_FACES_PER_PHOTO + 1)
        ]
    }
    project = await stack.project()
    few = await stack.photo(project, "wenige", RED)
    many = await stack.photo(project, "viele", GREEN)
    await _detect(stack, few, anna, face_box(1))

    [page] = await _all_pages(stack, project)

    for photo_id, assigned in ((few, {1}), (many, set())):
        detail = {
            entry["index"] for entry in (await stack.client.get(f"/photos/{photo_id}/faces")).json()
        }
        listed = {index for listed_photo, index in _faces(page) if listed_photo == photo_id}
        assert listed | assigned == detail
        assert listed.isdisjoint(assigned)
    assert len([face for face in _faces(page) if face[0] == many]) == MAX_FACES_PER_PHOTO


async def test_a_rejected_photo_is_listed(stack: PersonStack) -> None:
    project = await stack.project()
    rejected = await stack.photo(project, "ausschuss", RED, rejected=True)

    [page] = await _all_pages(stack, project)

    assert {photo_id for photo_id, _ in _faces(page)} == {rejected}


# --- Projektbindung, Seiten, Cursor -------------------------------------------------------------


async def test_a_page_never_contains_a_photo_of_another_project(stack: PersonStack) -> None:
    """Verzahnte Ids: A 1, 3, 5 und B 2, 4. Auch ein `after_id` direkt vor einem fremden Foto."""
    a = await stack.project("A")
    b = await stack.project("B")
    a_ids, b_ids = [], []
    for index in range(5):
        if index % 2 == 0:
            a_ids.append(await stack.photo(a, f"a{index}", RED))
        else:
            b_ids.append(await stack.photo(b, f"b{index}", RED))

    [page] = await _all_pages(stack, a)
    from_before_foreign = await _page(stack, a, after_id=a_ids[0])

    assert {photo_id for photo_id, _ in _faces(page)} == set(a_ids)
    assert (page["photos_done"], page["photos_total"]) == (3, 3)
    assert {photo_id for photo_id, _ in _faces(from_before_foreign)} == set(a_ids[1:])
    assert from_before_foreign["photos_done"] == 3


async def test_twenty_five_photos_give_a_page_of_24_and_one_of_1(stack: PersonStack) -> None:
    project = await stack.project()
    ids = [await stack.photo(project, f"p{index}", GREEN) for index in range(PAGE + 1)]

    pages = await _all_pages(stack, project)

    assert [page["next_after_id"] for page in pages] == [ids[PAGE - 1], None]
    assert [page["photos_done"] for page in pages] == [PAGE, PAGE + 1]
    assert {page["photos_total"] for page in pages} == {PAGE + 1}


async def test_exactly_24_photos_give_one_page_without_an_empty_follow_up(
    stack: PersonStack,
) -> None:
    project = await stack.project()
    for index in range(PAGE):
        await stack.photo(project, f"p{index}", GREEN)

    pages = await _all_pages(stack, project)

    assert len(pages) == 1
    assert pages[0]["next_after_id"] is None


@pytest.mark.parametrize(("third", "photos_on_page"), [(8, 3), (7, 4)], ids=["48", "47"])
async def test_the_page_ends_with_the_photo_reaching_48_faces(
    stack: PersonStack, analyzer: FakeFaceAnalyzer, third: int, photos_on_page: int
) -> None:
    # Ein fuenftes Foto dahinter, damit es in beiden Faellen eine Folgeseite gibt.
    colors: list[Color] = [(200, 0, 0), (0, 200, 0), (0, 0, 200), (200, 200, 0), (0, 0, 0)]
    counts = [20, 20, third, 5, 1]
    analyzer.faces_by_color = {
        color: [face_embedding(10 + index) for index in range(count)]
        for color, count in zip(colors, counts, strict=True)
    }
    analyzer.boxes_by_color = {
        color: [FaceBox(x=0.04 * index, y=0.0, width=0.03, height=0.03) for index in range(count)]
        for color, count in zip(colors, counts, strict=True)
    }
    project = await stack.project()
    ids = [await stack.photo(project, f"p{index}", color) for index, color in enumerate(colors)]

    page = await _page(stack, project)

    assert {photo_id for photo_id, _ in _faces(page)} == set(ids[:photos_on_page])
    assert page["next_after_id"] == ids[photos_on_page - 1]
    assert len(page["faces"]) == sum(counts[:photos_on_page])


async def test_after_id_is_exclusive_and_a_deleted_id_continues_with_the_next(
    stack: PersonStack,
) -> None:
    project = await stack.project()
    first = await stack.photo(project, "a", RED)
    gone = await stack.photo(project, "b", RED)
    last = await stack.photo(project, "c", RED)
    async with stack.factory() as session:
        await session.execute(
            persons_api.Photo.__table__.delete().where(persons_api.Photo.id == gone)
        )
        await session.commit()

    after_first = await _page(stack, project, after_id=first)
    after_gone = await _page(stack, project, after_id=gone)

    assert {photo_id for photo_id, _ in _faces(after_first)} == {last}
    assert {photo_id for photo_id, _ in _faces(after_gone)} == {last}


async def test_the_single_query_gives_exactly_that_photo_or_the_next_one(
    stack: PersonStack,
) -> None:
    project = await stack.project()
    ids = [await stack.photo(project, f"p{index}", RED) for index in range(4)]

    single = await _page(stack, project, after_id=ids[1] - 1, max_photos=1)
    async with stack.factory() as session:
        await session.execute(
            persons_api.Photo.__table__.delete().where(persons_api.Photo.id == ids[1])
        )
        await session.commit()
    after_delete = await _page(stack, project, after_id=ids[1] - 1, max_photos=1)

    assert {photo_id for photo_id, _ in _faces(single)} == {ids[1]}
    assert single["photos_done"] == 2
    assert single["next_after_id"] == ids[1]
    assert {photo_id for photo_id, _ in _faces(after_delete)} == {ids[2]}


async def test_a_project_without_photos(stack: PersonStack) -> None:
    project = await stack.project()

    page = await _page(stack, project)

    assert page == {
        "faces": [],
        "not_ready_photo_ids": [],
        "next_after_id": None,
        "photos_done": 0,
        "photos_total": 0,
    }


async def test_every_face_appears_exactly_once_over_all_pages(
    stack: PersonStack, analyzer: FakeFaceAnalyzer
) -> None:
    analyzer.shuffle = True
    project = await stack.project()
    for index in range(60):
        await stack.photo(project, f"p{index}", RED if index % 2 else BLUE)

    pages = await _all_pages(stack, project)

    faces = [face for page in pages for face in _faces(page)]
    assert len(faces) == 60 * len(UNKNOWN)
    assert faces == sorted(set(faces))


# --- Grenzen und Auth -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [{"after_id": -1}, {"after_id": MAX_ID + 1}, {"max_photos": 0}, {"max_photos": PAGE + 1}],
    ids=["after-negativ", "after-zu-gross", "max-null", "max-25"],
)
async def test_parameters_out_of_bounds_are_422(stack: PersonStack, params: dict[str, int]) -> None:
    project = await stack.project()

    response = await stack.client.get(f"/projects/{project}/unnamed-faces", params=params)

    assert response.status_code == 422


@pytest.mark.parametrize("project_id", ["0", str(MAX_ID + 1)])
async def test_a_project_id_out_of_bounds_is_422(stack: PersonStack, project_id: str) -> None:
    response = await stack.client.get(f"/projects/{project_id}/unnamed-faces")

    assert response.status_code == 422


async def test_an_unknown_project_is_404_without_a_model_call(
    stack: PersonStack, analyzer: FakeFaceAnalyzer
) -> None:
    response = await stack.client.get("/projects/4711/unnamed-faces")

    assert response.status_code == 404
    assert analyzer.calls == []


async def test_the_listing_of_unnamed_faces_requires_a_token(stack: PersonStack) -> None:
    project = await stack.project()

    response = await stack.client.get(
        f"/projects/{project}/unnamed-faces", headers={"Authorization": ""}
    )

    assert response.status_code == 401


# --- Nicht bereit -----------------------------------------------------------------------------


async def test_three_causes_make_a_photo_not_ready_and_the_rest_stays_complete(
    stack: PersonStack, analyzer: FakeFaceAnalyzer
) -> None:
    analyzer.failing = frozenset({BLUE})
    project = await stack.project()
    fine = await stack.photo(project, "gut", RED)
    missing = await stack.photo(project, "ohne-variante", None)
    unreadable = await stack.photo(project, "kaputt", None)
    throwing = await stack.photo(project, "wirft", BLUE)
    async with stack.factory() as session:
        photo = await session.get(persons_api.Photo, unreadable)
        assert photo is not None
        path = persons_api.variant_path(stack.cache_dir, photo.id, photo.etag, "display")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"kein bild")

    page = await _page(stack, project)

    assert sorted(page["not_ready_photo_ids"]) == sorted([missing, unreadable, throwing])
    assert _faces(page) == [(fine, index) for index in range(len(UNKNOWN))]
    # Ohne Variante kein Modellaufruf: gut und wirft, sonst nichts.
    assert len([call for call in analyzer.calls if call[0] == "detect"]) == 2


# --- Nichts ueber Unbekannte ------------------------------------------------------------------


async def test_a_full_listing_leaves_every_table_and_every_file_as_it_was(
    stack: PersonStack, analyzer: FakeFaceAnalyzer, tmp_path: Path
) -> None:
    await _anchored(stack)
    project = await stack.project()
    for index in range(PAGE + 3):
        await stack.photo(project, f"p{index}", RED)
    tables_before = await _table_snapshot(stack)
    files_before = sorted(str(path) for path in tmp_path.rglob("*") if path.suffix != ".db-journal")

    await _all_pages(stack, project)
    single = await _page(stack, project, after_id=0, max_photos=1)

    assert await _table_snapshot(stack) == tables_before
    assert (
        sorted(str(path) for path in tmp_path.rglob("*") if path.suffix != ".db-journal")
        == files_before
    )
    assert [call for call in analyzer.calls if call[0] == "embed"] == []
    assert single["faces"]


async def test_there_is_no_process_cache_a_second_listing_detects_again(
    stack: PersonStack, analyzer: FakeFaceAnalyzer
) -> None:
    project = await stack.project()
    ready = [await stack.photo(project, f"p{index}", RED) for index in range(5)]
    await stack.photo(project, "ohne", None)

    await _all_pages(stack, project)
    await _all_pages(stack, project)

    assert len([call for call in analyzer.calls if call[0] == "detect"]) == 2 * len(ready)


async def test_no_box_of_an_unknown_face_is_stored_logged_or_answered(
    stack: PersonStack, analyzer: FakeFaceAnalyzer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="photosort")
    anna, _ = await _anchored(stack)
    analyzer.boxes_by_color = {RED: [sentinel_box(0), sentinel_box(1), sentinel_box(2)]}
    project = await stack.project()
    photo = await stack.photo(project, "a", RED)

    response = await stack.client.get(f"/projects/{project}/unnamed-faces")

    assert BOX_SENTINEL_TEXT not in repr(await _table_snapshot(stack))
    assert BOX_SENTINEL_TEXT not in caplog.text
    assert BOX_SENTINEL_TEXT not in response.text

    # Gegenprobe: Nach der Zuordnung von Gesicht 1 steht dessen Box in den Korrekturen und nur
    # dort, und die Boxen der Gesichter 0 und 2 stehen nirgends - sonst waere die Suche leer.
    assigned = await stack.client.post(
        f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 1}
    )
    assert assigned.status_code == 201
    snapshot = await _table_snapshot(stack)
    holders = {name for name, rows in snapshot.items() if repr(sentinel_box(1).x) in repr(rows)}
    assert holders == {"photo_person_corrections"}
    assert repr(sentinel_box(0).x) not in repr(snapshot)
    assert repr(sentinel_box(2).x) not in repr(snapshot)


async def test_the_log_carries_only_type_and_photo_id(
    stack: PersonStack, analyzer: FakeFaceAnalyzer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="photosort")
    analyzer.failing = frozenset({BLUE})
    analyzer.boxes_by_color = {RED: [sentinel_box(0), sentinel_box(1), sentinel_box(2)]}
    project = await stack.project()
    await stack.photo(project, "a", RED)
    throwing = await stack.photo(project, "b", BLUE)

    response = await stack.client.get(f"/projects/{project}/unnamed-faces")

    assert "RuntimeError" in caplog.text
    assert str(throwing) in caplog.text
    assert BOX_SENTINEL_TEXT not in caplog.text
    assert "/9j/" not in caplog.text
    assert response.json()["faces"][0]["crop_jpeg"][:8] not in caplog.text
    assert str(stack.cache_dir) not in caplog.text
    assert "p1/" not in caplog.text


# --- Antwortform ------------------------------------------------------------------------------


async def test_the_answer_has_exactly_its_keys_and_an_uncached_jpeg_crop(
    stack: PersonStack,
) -> None:
    project = await stack.project()
    await stack.photo(project, "a", RED)
    empty_project = await stack.project("Leer")

    response = await stack.client.get(f"/projects/{project}/unnamed-faces")
    empty = await stack.client.get(f"/projects/{empty_project}/unnamed-faces")

    body = response.json()
    assert set(body) == {
        "faces",
        "not_ready_photo_ids",
        "next_after_id",
        "photos_done",
        "photos_total",
    }
    assert all(set(face) == {"photo_id", "face_index", "crop_jpeg"} for face in body["faces"])
    crop = base64.b64decode(body["faces"][0]["crop_jpeg"], validate=True)
    assert crop[:3] == b"\xff\xd8\xff"
    with Image.open(io.BytesIO(crop)) as image:
        assert image.format == "JPEG"
        assert max(image.size) <= 160
        assert not image.getexif()
    for answer in (response, empty):
        assert answer.headers["cache-control"] == "no-store"
        assert answer.headers["x-content-type-options"] == "nosniff"
        assert "etag" not in answer.headers


def test_the_schemas_carry_exactly_their_fields() -> None:
    assert set(persons_api.UnnamedFaceOut.model_fields) == {"photo_id", "face_index", "crop_jpeg"}
    assert set(persons_api.UnnamedFacesPageOut.model_fields) == {
        "faces",
        "not_ready_photo_ids",
        "next_after_id",
        "photos_done",
        "photos_total",
    }


async def test_both_users_get_byte_identical_answers(stack: PersonStack) -> None:
    project = await stack.project()
    await stack.photo(project, "a", RED)
    token = await stack.second_user_token()

    mine = await stack.client.get(f"/projects/{project}/unnamed-faces")
    theirs = await stack.client.get(
        f"/projects/{project}/unnamed-faces", headers={"Authorization": f"Bearer {token}"}
    )

    assert mine.content == theirs.content


# --- Executor, Verbindungen, frische Boxen ------------------------------------------------------


def _model_thread_gate(
    analyzer: FakeFaceAnalyzer, first: Color
) -> tuple[threading.Event, asyncio.Event, list[Color]]:
    """Haelt das `detect` des Fotos der Farbe `first` am Modell-Thread fest, bis `release`
    gesetzt ist. `paused` wird im Event-Loop gesetzt, sobald es haengt."""
    loop = asyncio.get_running_loop()
    release = threading.Event()
    paused = asyncio.Event()
    order: list[Color] = []

    def on_detect(color: Color) -> None:
        order.append(color)

    def before_return(color: Color) -> None:
        if color == first and not release.is_set():
            loop.call_soon_threadsafe(paused.set)
            assert release.wait(timeout=10)

    analyzer.on_detect = on_detect
    analyzer.before_detect_returns = before_return
    return release, paused, order


async def test_an_assignment_waits_for_at_most_one_photo_of_a_running_listing(
    stack: PersonStack, analyzer: FakeFaceAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rot gegen eine Umsetzung, die eine ganze Seite als EINEN Auftrag abgibt."""
    colors: list[Color] = [(200, 0, 0), (0, 200, 0), (0, 0, 200), (200, 0, 200), (0, 200, 200)]
    analyzer.faces_by_color = {**analyzer.faces_by_color, **{color: UNKNOWN for color in colors}}
    anna, _ = await _anchored(stack)
    project = await stack.project()
    for index, color in enumerate(colors):
        await stack.photo(project, f"p{index}", color)
    target_project = await stack.project("Ziel")
    target = await stack.photo(target_project, "ziel", ANCHOR)
    release, paused, order = _model_thread_gate(analyzer, colors[0])
    original = persons_api._on_model_thread

    async def signalling(executor: Any, call: Any, *args: Any) -> Any:
        running = asyncio.ensure_future(original(executor, call, *args))
        if call is persons_api._embedding_at:
            await asyncio.sleep(0)
            release.set()
        return await running

    monkeypatch.setattr(persons_api, "_on_model_thread", signalling)

    async def assign() -> httpx.Response:
        await paused.wait()
        return await stack.client.post(
            f"/persons/{anna}/references", json={"photo_id": target, "face_index": 0}
        )

    listing, assigned = await asyncio.gather(
        stack.client.get(f"/projects/{project}/unnamed-faces"), assign()
    )

    assert listing.status_code == 200
    assert assigned.status_code == 201, assigned.text
    assert order == [colors[0], ANCHOR, *colors[1:]]
    assert {thread for method, thread in analyzer.calls}.pop().startswith("gesichter")
    assert len({thread for _, thread in analyzer.calls}) == 1


async def test_the_listing_holds_no_connection_while_the_model_runs(
    stack: PersonStack, analyzer: FakeFaceAnalyzer
) -> None:
    project = await stack.project()
    await stack.photo(project, "a", RED)
    await stack.photo(project, "b", BLUE)
    release, paused, _ = _model_thread_gate(analyzer, BLUE)
    checkouts_before = stack.pool.checkouts

    listing = asyncio.ensure_future(stack.client.get(f"/projects/{project}/unnamed-faces"))
    await paused.wait()
    held_while_detecting = stack.pool.held
    borrowed_so_far = stack.pool.checkouts - checkouts_before
    release.set()
    response = await listing

    assert response.status_code == 200
    assert held_while_detecting == 0
    # Gegenprobe: Zwischen den Fotos wurde nachweislich ausgeliehen - der Zaehler misst.
    assert borrowed_so_far >= 3


async def test_assigned_boxes_are_read_fresh_for_every_photo(
    stack: PersonStack, analyzer: FakeFaceAnalyzer, tmp_path: Path
) -> None:
    """Waehrend `detect` von Foto 1 entsteht auf Foto 2 eine Korrektur mit Box. In DERSELBEN Seite
    fehlt dieses Gesicht bereits - rot gegen ein Vorab-Lesen der Boxen je Seite."""
    anna, _ = await _anchored(stack)
    project = await stack.project()
    first = await stack.photo(project, "a", RED)
    second = await stack.photo(project, "b", BLUE)
    box = face_box(0)
    database = tmp_path / "personen.db"

    def write_on_first(color: Color) -> None:
        if color != RED:
            return
        connection = sqlite3.connect(database)
        connection.execute(
            "INSERT INTO photo_person_corrections (photo_id, person_id, user_id, applies, "
            "updated_at, face_box_x, face_box_y, face_box_width, face_box_height) "
            "VALUES (?, ?, ?, 1, '2026-09-28 12:00:00', ?, ?, ?, ?)",
            (second, anna, stack.user_id, box.x, box.y, box.width, box.height),
        )
        connection.commit()
        connection.close()

    analyzer.on_detect = write_on_first

    page = await _page(stack, project)

    assert [index for photo_id, index in _faces(page) if photo_id == second] == [1, 2]
    assert [index for photo_id, index in _faces(page) if photo_id == first] == [0, 1, 2]
    assert await stack.count(PhotoPersonCorrection) == 3


# --- Abbruch bei getrennter Verbindung ----------------------------------------------------------


async def _call_directly(
    stack: PersonStack, project: int, *, disconnect_after_first: bool, analyzer: FakeFaceAnalyzer
) -> list[dict[str, Any]]:
    """Die App als ASGI-App mit eigenem `receive`: erst die (leere) Anfrage, danach blockiert es,
    bis `on_detect` das erste Foto meldet - dann `http.disconnect`."""
    loop = asyncio.get_running_loop()
    first_seen = asyncio.Event()

    def on_detect(color: Color) -> None:
        loop.call_soon_threadsafe(first_seen.set)

    analyzer.on_detect = on_detect
    requested = False

    async def receive() -> dict[str, Any]:
        nonlocal requested
        if not requested:
            requested = True
            return {"type": "http.request", "body": b"", "more_body": False}
        if disconnect_after_first:
            await first_seen.wait()
        else:
            await asyncio.Event().wait()
        return {"type": "http.disconnect"}

    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    token = stack.client.headers["Authorization"].encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": f"/projects/{project}/unnamed-faces",
        "raw_path": f"/projects/{project}/unnamed-faces".encode(),
        "query_string": b"",
        "headers": [(b"host", b"test"), (b"authorization", token)],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }
    await app(scope, receive, send)
    return sent


async def test_a_disconnect_stops_the_listing_after_the_running_photo(
    stack: PersonStack, analyzer: FakeFaceAnalyzer, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    project = await stack.project()
    for index in range(5):
        await stack.photo(project, f"p{index}", RED)

    sent = await _call_directly(stack, project, disconnect_after_first=True, analyzer=analyzer)

    assert len([call for call in analyzer.calls if call[0] == "detect"]) == 1
    [start] = [message for message in sent if message["type"] == "http.response.start"]
    assert start["status"] == 204
    assert b"".join(message.get("body", b"") for message in sent) == b""
    assert "ERROR" not in {record.levelname for record in caplog.records}
    assert not [
        task
        for task in asyncio.all_tasks()
        if task.get_name() == persons_api.DISCONNECT_WATCHER_NAME
    ]


async def test_without_a_disconnect_all_five_photos_are_listed(
    stack: PersonStack, analyzer: FakeFaceAnalyzer
) -> None:
    project = await stack.project()
    for index in range(5):
        await stack.photo(project, f"p{index}", RED)

    sent = await _call_directly(stack, project, disconnect_after_first=False, analyzer=analyzer)

    assert len([call for call in analyzer.calls if call[0] == "detect"]) == 5
    [start] = [message for message in sent if message["type"] == "http.response.start"]
    assert start["status"] == 200
