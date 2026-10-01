"""Die sieben Personen-Endpunkte und `PhotoOut.persons`/der Personenfilter (S1-S9).

Der Analyzer kommt ueber die ueberschreibbare Dependency `get_face_analyzer` - die echten Modelle
laufen hier nie (Sperre in `conftest.py`). Merkmale sind Basisvektoren fern jeder Schwelle.
"""

from __future__ import annotations

import asyncio
import io
import math
import re
import sqlite3
import threading
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import persons as persons_module
from photosort.api import persons as persons_api
from photosort.api.persons import get_face_analyzer
from photosort.config import settings
from photosort.db import Base
from photosort.face_analysis import MODEL_KEY, FaceBox
from photosort.main import app
from photosort.models import (
    CriterionScoringRun,
    Event,
    FeedbackEvent,
    MotifAssessmentSource,
    Person,
    PersonReference,
    Photo,
    PhotoMotifStrength,
    PhotoPersonCorrection,
    PhotoPersonDetection,
    PhotoRanking,
    Project,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motif_strengths import upsert_assessment
from photosort.persons import create_person, set_correction
from photosort.security import create_access_token, hash_password
from photosort.worker import rebuild_run_selection
from tests.face_fakes import (
    SENTINEL_TEXT,
    Color,
    FakeFaceAnalyzer,
    face_box,
    face_embedding,
    write_display_variant,
)
from tests.person_stack import PersonStack, person_stack

NOW = datetime(2026, 9, 27, 12, 0, 0)
RED: Color = (220, 20, 20)
GREEN: Color = (20, 220, 20)
TWO_FACES = [face_embedding(0), face_embedding(1)]


class Lay:
    def __init__(self, session: AsyncSession, cache_dir: Path) -> None:
        self.session = session
        self.cache_dir = cache_dir

    async def project(self, name: str = "Reise") -> Project:
        project = Project(name=name, opencloud_drive_id="d", opencloud_path=f"/{name}")
        self.session.add(project)
        await self.session.flush()
        return project

    async def photo(self, project: Project, name: str, color: Color | None = RED) -> Photo:
        photo = Photo(
            project_id=project.id,
            relative_path=f"{project.name}/{name}.jpg",
            etag=f"etag-{project.name}-{name}",
            content_length=1,
            taken_at=NOW,
            taken_at_original=NOW,
            last_modified=NOW,
        )
        self.session.add(photo)
        await self.session.flush()
        if color is not None:
            write_display_variant(self.cache_dir, photo.id, photo.etag, color)
        return photo


@pytest.fixture
def analyzer() -> FakeFaceAnalyzer:
    return FakeFaceAnalyzer({RED: TWO_FACES, GREEN: [face_embedding(0)]})


@pytest_asyncio.fixture
async def client(
    authenticated_api_client: httpx.AsyncClient,
    analyzer: FakeFaceAnalyzer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path))
    app.dependency_overrides[get_face_analyzer] = lambda: analyzer
    yield authenticated_api_client


@pytest.fixture
def lay(db_session: AsyncSession, tmp_path: Path) -> Lay:
    return Lay(db_session, tmp_path)


async def _user(session: AsyncSession) -> User:
    return (await session.execute(select(User).where(User.username == "testuser"))).scalar_one()


async def _count(session: AsyncSession, model: Any) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def _define(session: AsyncSession, name: str, axis: int, photo: Photo) -> Person:
    user = await _user(session)
    person = await create_person(
        session,
        name=name,
        embedding=face_embedding(axis),
        face_box=face_box(axis),
        model_key=MODEL_KEY,
        photo_id=photo.id,
        user_id=user.id,
    )
    await session.commit()
    return person


# --- POST /persons ------------------------------------------------------------------------------


async def test_a_person_is_created_with_its_first_reference(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()

    response = await client.post(
        "/persons", json={"name": " Anna ", "photo_id": photo.id, "face_index": 0}
    )

    assert response.status_code == 201
    assert set(response.json()) == {"person", "learned", "photo_persons"}
    body = response.json()
    assert set(body["person"]) == {"id", "name", "reference_count"}
    assert body["person"]["name"] == "Anna"
    assert body["person"]["reference_count"] == 1
    assert body["learned"] is True
    assert body["photo_persons"] == [
        {"person_id": body["person"]["id"], "origin": "corrected", "face": "shown"}
    ]
    assert await _count(db_session, PhotoPersonCorrection) == 1


async def test_a_refused_face_leaves_no_person(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()

    response = await client.post(
        "/persons", json={"name": "Anna", "photo_id": photo.id, "face_index": 5}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == persons_module.FaceNotFound.detail
    assert await _count(db_session, Person) == 0
    assert await _count(db_session, PersonReference) == 0


async def test_the_third_person_and_a_look_alike_are_refused(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()
    await _define(db_session, "Anna", 0, photo)
    photo_id = photo.id

    look_alike = await client.post(
        "/persons", json={"name": "Berta", "photo_id": photo_id, "face_index": 0}
    )
    second = await client.post(
        "/persons", json={"name": "Berta", "photo_id": photo_id, "face_index": 1}
    )
    third = await client.post(
        "/persons", json={"name": "Clara", "photo_id": photo_id, "face_index": 1}
    )

    assert look_alike.status_code == 409
    assert look_alike.json()["detail"] == persons_module.ResemblesOtherPerson.detail
    assert second.status_code == 201
    assert third.status_code == 409
    assert third.json()["detail"] == persons_module.PersonLimitReached.detail


@pytest.mark.parametrize(
    ("first", "second"), [("Anna", "ANNA"), ("Straße", "STRASSE"), ("\u00e9", "e\u0301")]
)
async def test_a_duplicate_name_is_409(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession, first: str, second: str
) -> None:
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()
    await _define(db_session, first, 0, photo)

    response = await client.post(
        "/persons", json={"name": second, "photo_id": photo.id, "face_index": 1}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == persons_module.DuplicatePersonName.detail


@pytest.mark.parametrize("bypass", ["slot", "name"])
async def test_the_constraint_behind_a_bypassed_precheck_gives_409_not_500(
    client: httpx.AsyncClient,
    lay: Lay,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    bypass: str,
) -> None:
    """Die Vorabpruefung umgangen, als liefe gleichzeitig eine zweite Anlage: der Constraint auf
    `slot` bzw. `name_key` greift und wird `409`."""
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()
    await _define(db_session, "Anna", 0, photo)

    async def no_slots_taken(session: AsyncSession) -> set[int]:
        return set()

    async def no_name_taken(session: AsyncSession, name_key: str) -> bool:
        return False

    monkeypatch.setattr(persons_module, "_name_taken", no_name_taken)
    if bypass == "slot":
        monkeypatch.setattr(persons_module, "_taken_slots", no_slots_taken)
    name = "Berta" if bypass == "slot" else "ANNA"

    response = await client.post(
        "/persons", json={"name": name, "photo_id": photo.id, "face_index": 1}
    )

    assert response.status_code == 409
    assert await _count(db_session, Person) == 1


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "x" * 41,
        "Anna\u202e",
        "An\u200bna",
        "An\u0000na",
        "An\u2028na",
        "An\tna",
        "An\u0007na",
        "An\u00adna",
        "An\u2029na",
        "x" * 201,
    ],
)
async def test_an_invalid_name_is_422(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession, name: str
) -> None:
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()

    response = await client.post(
        "/persons", json={"name": name, "photo_id": photo.id, "face_index": 0}
    )

    assert response.status_code == 422
    assert await _count(db_session, Person) == 0


async def test_forty_code_points_after_nfc_are_allowed(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()

    response = await client.post(
        "/persons", json={"name": "e\u0301" * 40, "photo_id": photo.id, "face_index": 0}
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    "body",
    [
        {"name": "Anna", "photo_id": 1, "face_index": 0, "user_id": 2},
        {"name": "Anna", "photo_id": 1, "face_index": 0, "embedding": [1.0]},
        {"name": "Anna", "photo_id": 1, "face_index": -1},
        {"name": "Anna", "photo_id": 1, "face_index": 20},
        {"name": "Anna", "photo_id": 0, "face_index": 0},
        {"name": "Anna", "photo_id": 1_000_000_001, "face_index": 0},
    ],
    ids=["user_id", "zusatzfeld", "index-negativ", "index-20", "foto-0", "foto-zu-gross"],
)
async def test_bounded_and_closed_input(
    client: httpx.AsyncClient, db_session: AsyncSession, body: dict[str, Any]
) -> None:
    response = await client.post("/persons", json=body)

    assert response.status_code == 422
    assert await _count(db_session, Person) == 0


async def test_without_display_variant_404_and_no_model_call(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession, analyzer: FakeFaceAnalyzer
) -> None:
    photo = await lay.photo(await lay.project(), "a", color=None)
    await db_session.commit()

    created = await client.post(
        "/persons", json={"name": "Anna", "photo_id": photo.id, "face_index": 0}
    )
    faces = await client.get(f"/photos/{photo.id}/faces")
    image = await client.get(f"/photos/{photo.id}/faces/0/image")

    for response in (created, faces, image):
        assert response.status_code == 404
        assert response.json()["detail"] == "Bild wird noch verarbeitet."
    assert analyzer.calls == []


# --- POST /persons/{id}/references ----------------------------------------------------------


async def test_a_reference_assigns_writes_no_feedback_event_and_only_names_at_the_cap(
    client: httpx.AsyncClient,
    lay: Lay,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An der Obergrenze `learned: false` statt `409`: benannt, gezeigt, aber nicht gelernt."""
    project = await lay.project()
    anchor = await lay.photo(project, "anker")
    other = await lay.photo(project, "b", GREEN)
    third = await lay.photo(project, "c", GREEN)
    await db_session.commit()
    anna = await _define(db_session, "Anna", 0, anchor)
    monkeypatch.setattr(persons_module, "MAX_REFERENCES_PER_PERSON", 2)
    project_id, other_id, third_id, anna_id = project.id, other.id, third.id, anna.id

    added = await client.post(
        f"/persons/{anna_id}/references", json={"photo_id": other_id, "face_index": 0}
    )
    capped = await client.post(
        f"/persons/{anna_id}/references", json={"photo_id": third_id, "face_index": 0}
    )

    assert added.status_code == 201
    assert set(added.json()) == {"person", "learned", "photo_persons"}
    assert added.json()["learned"] is True
    assert added.json()["person"]["reference_count"] == 2
    assert capped.status_code == 201
    assert capped.json()["learned"] is False
    assert capped.json()["person"]["reference_count"] == 2
    assert capped.json()["photo_persons"] == [
        {"person_id": anna_id, "origin": "corrected", "face": "assigned"}
    ]
    assert await _count(db_session, PersonReference) == 2
    listing = (await client.get(f"/projects/{project_id}/photos")).json()["items"]
    by_id = {item["id"]: item["persons"] for item in listing}
    assert by_id[other_id] == [{"person_id": anna_id, "origin": "corrected", "face": "shown"}]
    assert await _count(db_session, FeedbackEvent) == 0


async def test_the_motif_correction_in_the_same_lay_does_write_an_event(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    """Gegenprobe zu "kein Nacharbeits-Ereignis": derselbe Aufbau, eine Motivkorrektur."""
    project = await lay.project()
    photo = await lay.photo(project, "a")
    from photosort.models import MotifAssessmentSource, PhotoMotifAssessment

    db_session.add(
        PhotoMotifAssessment(
            photo_id=photo.id,
            source=MotifAssessmentSource.LOCAL,
            excluded_document=False,
            computed_at=NOW,
        )
    )
    await db_session.flush()
    db_session.add(PhotoMotifStrength(photo_id=photo.id, motif_key="menschen", strength=0.2))
    await db_session.commit()

    response = await client.put(
        f"/photos/{photo.id}/motif-corrections/menschen", json={"applies": True}
    )

    assert response.status_code == 200
    assert await _count(db_session, FeedbackEvent) == 1


async def test_the_stored_face_is_the_one_listed_under_the_index(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession, analyzer: FakeFaceAnalyzer
) -> None:
    """Der Fake liefert bei jedem zweiten Aufruf die umgekehrte Reihenfolge: gespeichert wird das
    Gesicht, das die Auflistung unter diesem Index zeigte."""
    analyzer.shuffle = True
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()

    listed = (await client.get(f"/photos/{photo.id}/faces")).json()
    await client.post("/persons", json={"name": "Anna", "photo_id": photo.id, "face_index": 1})

    stored = (await db_session.execute(select(PersonReference.embedding))).scalar_one()
    assert [entry["index"] for entry in listed] == [0, 1]
    assert stored == pytest.approx(face_embedding(1))


# --- GET /photos/{id}/faces und der Ausschnitt ----------------------------------------------


async def test_faces_carry_only_index_and_box_and_at_most_twenty(
    client: httpx.AsyncClient,
    lay: Lay,
    db_session: AsyncSession,
    analyzer: FakeFaceAnalyzer,
) -> None:
    analyzer.faces_by_color = {RED: [face_embedding(index) for index in range(25)]}
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()

    response = await client.get(f"/photos/{photo.id}/faces")

    assert response.status_code == 200
    assert len(response.json()) == 20
    assert all(set(entry) == {"index", "box"} for entry in response.json())
    assert SENTINEL_TEXT not in response.text


async def test_the_crop_is_an_uncached_jpeg_and_nothing_is_stored(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession, tmp_path: Path
) -> None:
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()
    before = sorted(path.name for path in tmp_path.rglob("*"))

    response = await client.get(f"/photos/{photo.id}/faces/1/image")
    beyond = await client.get(f"/photos/{photo.id}/faces/2/image")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    with Image.open(io.BytesIO(response.content)) as crop:
        assert crop.format == "JPEG"
    assert beyond.status_code == 404
    assert sorted(path.name for path in tmp_path.rglob("*")) == before


async def test_two_requests_run_on_one_thread_never_overlapping(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession, analyzer: FakeFaceAnalyzer
) -> None:
    analyzer.delay_seconds = 0.05
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()

    await asyncio.gather(
        client.get(f"/photos/{photo.id}/faces"), client.get(f"/photos/{photo.id}/faces")
    )

    threads = {name for method, name in analyzer.calls if method == "detect"}
    assert len(threads) == 1
    assert next(iter(threads)).startswith("gesichter")
    (first_start, first_end), (second_start, _) = sorted(analyzer.spans)
    assert second_start >= first_end


# --- GET /persons, DELETE ------------------------------------------------------------------------


async def test_get_persons_by_slot_counting_only_the_current_model(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()
    anna = await _define(db_session, "Anna", 0, photo)
    berta = await _define(db_session, "Berta", 1, photo)
    db_session.add(PersonReference(person_id=anna.id, embedding=[1.0], model_key="alt"))
    await db_session.commit()

    response = await client.get("/persons")

    assert response.json() == [
        {"id": anna.id, "name": "Anna", "reference_count": 1},
        {"id": berta.id, "name": "Berta", "reference_count": 1},
    ]
    assert SENTINEL_TEXT not in response.text


async def test_delete_is_204_then_404(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()
    anna = await _define(db_session, "Anna", 0, photo)

    assert (await client.delete(f"/persons/{anna.id}")).status_code == 204
    assert (await client.delete(f"/persons/{anna.id}")).status_code == 404
    assert await _count(db_session, PersonReference) == 0


# --- PUT /photos/{id}/persons/{pid} ---------------------------------------------------------


async def test_put_returns_the_effective_list_and_the_last_writer_wins(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    project = await lay.project()
    anchor = await lay.photo(project, "anker")
    photo = await lay.photo(project, "b")
    await db_session.commit()
    anna = await _define(db_session, "Anna", 0, anchor)
    db_session.add(PhotoPersonDetection(photo_id=photo.id, person_id=anna.id, computed_at=NOW))
    partner = User(username="partnerin", password_hash=hash_password("x"))
    db_session.add(partner)
    await db_session.commit()

    removed = await client.put(f"/photos/{photo.id}/persons/{anna.id}", json={"applies": False})
    assert removed.status_code == 200
    assert removed.json() == []
    client.headers["Authorization"] = f"Bearer {create_access_token(partner)}"
    added = await client.put(f"/photos/{photo.id}/persons/{anna.id}", json={"applies": True})

    assert added.json() == [{"person_id": anna.id, "origin": "corrected", "face": None}]
    assert "user_id" not in added.text
    rows = (
        (
            await db_session.execute(
                select(PhotoPersonCorrection).where(PhotoPersonCorrection.photo_id == photo.id)
            )
        )
        .scalars()
        .all()
    )
    await db_session.refresh(rows[0])
    assert [(row.applies, row.user_id) for row in rows] == [(True, partner.id)]
    assert await _count(db_session, FeedbackEvent) == 0


async def test_put_for_an_unknown_person_is_404_and_a_smuggled_field_422(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    photo = await lay.photo(await lay.project(), "a")
    await db_session.commit()

    unknown = await client.put(f"/photos/{photo.id}/persons/99", json={"applies": True})
    smuggled = await client.put(
        f"/photos/{photo.id}/persons/99", json={"applies": True, "user_id": 3}
    )

    assert unknown.status_code == 404
    assert smuggled.status_code == 422


async def test_the_write_endpoints_require_a_token(api_client: httpx.AsyncClient) -> None:
    for method, path in (
        ("post", "/persons"),
        ("put", "/photos/1/persons/1"),
        ("get", "/photos/1/faces/0/image"),
    ):
        assert (await api_client.request(method, path, json={})).status_code == 401


# --- PhotoOut.persons und der Filter ------------------------------------------------------------


async def _matrix(lay: Lay, db_session: AsyncSession) -> tuple[Project, dict[str, int], int, int]:
    """Erkennung {nein, ja} x Korrektur {keine, true, false}, fuer Anna; Berta auf zwei Fotos."""
    project = await lay.project()
    anchor_project = await lay.project("Anker")
    anchor = await lay.photo(anchor_project, "anker")
    names = ["leer", "hand", "entfernt-ohne", "erkannt", "erkannt-hand", "erkannt-entfernt"]
    photos = {name: await lay.photo(project, name) for name in names}
    await db_session.commit()
    anna = await _define(db_session, "Anna", 0, anchor)
    berta = await _define(db_session, "Berta", 1, anchor)
    user = await _user(db_session)
    for name in ("erkannt", "erkannt-hand", "erkannt-entfernt"):
        db_session.add(
            PhotoPersonDetection(photo_id=photos[name].id, person_id=anna.id, computed_at=NOW)
        )
    for name, applies in (
        ("hand", True),
        ("entfernt-ohne", False),
        ("erkannt-hand", True),
        ("erkannt-entfernt", False),
    ):
        await set_correction(
            db_session,
            photo_id=photos[name].id,
            person_id=anna.id,
            applies=applies,
            user_id=user.id,
        )
    for name in ("erkannt", "entfernt-ohne"):
        db_session.add(
            PhotoPersonDetection(photo_id=photos[name].id, person_id=berta.id, computed_at=NOW)
        )
    await db_session.commit()
    return project, {name: photo.id for name, photo in photos.items()}, anna.id, berta.id


async def test_the_filter_shows_exactly_the_photos_carrying_the_name(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    project, ids, anna, berta = await _matrix(lay, db_session)
    base = f"/projects/{project.id}/photos"

    everything = (await client.get(base)).json()["items"]
    only_anna = (await client.get(base, params={"person_id": anna})).json()["items"]
    both = (await client.get(base, params=[("person_id", anna), ("person_id", berta)])).json()
    twice = (await client.get(base, params=[("person_id", anna), ("person_id", anna)])).json()

    carrying = {
        item["id"]
        for item in everything
        if any(entry["person_id"] == anna for entry in item["persons"])
    }
    assert (
        {item["id"] for item in only_anna}
        == carrying
        == {ids["hand"], ids["erkannt"], ids["erkannt-hand"]}
    )
    assert {item["id"] for item in both["items"]} == {ids["erkannt"]}
    assert twice["total"] == len(only_anna)
    origins = {item["id"]: item["persons"] for item in everything}
    assert origins[ids["erkannt"]] == [
        {"person_id": anna, "origin": "recognized", "face": None},
        {"person_id": berta, "origin": "recognized", "face": None},
    ]
    assert origins[ids["erkannt-entfernt"]] == []
    assert all(
        set(entry) == {"person_id", "origin", "face"}
        for item in everything
        for entry in item["persons"]
    )


def test_the_photo_person_schema_is_exactly_id_origin_and_face() -> None:
    """Jeder Lesepfad (Liste, Entwurf, Detail, PUT) baut `PhotoPersonOut`; `face` ist ein
    Aufzaehlungswert - eine gespeicherte Box verlaesst die Datenbank ueber keine Antwort."""
    from photosort.api.persons import PhotoPersonOut

    assert set(PhotoPersonOut.model_fields) == {"person_id", "origin", "face"}


async def test_the_filter_combines_with_the_rating_filter(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    project, ids, anna, _ = await _matrix(lay, db_session)
    await client.put(f"/photos/{ids['erkannt']}/rating", json={"status": "album_worthy"})

    response = await client.get(
        f"/projects/{project.id}/photos",
        params={"person_id": anna, "rating_status": "album_worthy"},
    )

    assert {item["id"] for item in response.json()["items"]} <= {ids["erkannt"]}


@pytest.mark.parametrize(
    "params",
    [
        [("person_id", 1), ("person_id", 1), ("person_id", 2)],
        [("person_id", 0)],
        [("person_id", -1)],
        [("person_id", 1_000_000_001)],
        [("person_id", 1), ("draft", "true")],
    ],
    ids=["drei-werte", "null", "negativ", "zu-gross", "mit-entwurf"],
)
async def test_the_filter_is_bounded(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession, params: list[Any]
) -> None:
    project = await lay.project()
    await db_session.commit()

    response = await client.get(f"/projects/{project.id}/photos", params=params)

    assert response.status_code == 422


async def test_an_unknown_person_id_gives_an_empty_list(
    client: httpx.AsyncClient, lay: Lay, db_session: AsyncSession
) -> None:
    project, _, _, _ = await _matrix(lay, db_session)

    response = await client.get(f"/projects/{project.id}/photos", params={"person_id": 4711})

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


# --- Laufzusammenfassung --------------------------------------------------------------------


def _run_row(**fields: Any) -> Any:
    from photosort.models import ClassificationPhase, CriterionScoringRun, ScanStatus

    defaults: dict[str, Any] = {
        "status": ScanStatus.RUNNING,
        "phase": ClassificationPhase.PERSONS,
        "phase_started_at": NOW,
        "started_at": NOW,
        "cloud_requested": False,
        "photos_total": 9,
        "photos_processed": 9,
        "persons_photos_total": None,
        "persons_photos_processed": None,
    }
    defaults.update(fields)
    return CriterionScoringRun(project_id=1, scoring_run_id=1, **defaults)


def test_the_persons_phase_counts_on_its_own_counters() -> None:
    from photosort.api.projects import _phase_progress

    assert _phase_progress(_run_row(persons_photos_total=8, persons_photos_processed=3), []) == (
        3,
        8,
    )
    assert _phase_progress(_run_row(), []) == (None, None)


def test_the_remaining_time_of_the_persons_phase_uses_its_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from photosort.api import projects

    monkeypatch.setattr(projects, "now_utc", lambda: NOW.replace(minute=1))
    counted = _run_row(persons_photos_total=8, persons_photos_processed=4)

    assert projects._phase_remaining_seconds(counted, []) is not None
    assert projects._phase_remaining_seconds(_run_row(), []) is None


async def test_the_summary_carries_null_or_the_count(db_session: AsyncSession) -> None:
    """Zwilling: `null` heisst "lief nicht", eine Zahl heisst "lief"."""
    from photosort.api.projects import _criterion_scoring_run_summary
    from photosort.models import ScanStatus

    finished = {"status": ScanStatus.SUCCESS, "phase": None, "phase_started_at": None}
    without = await _criterion_scoring_run_summary(db_session, _run_row(**finished))
    counted = await _criterion_scoring_run_summary(
        db_session, _run_row(**finished, persons_photos_total=5, persons_photos_processed=5)
    )

    assert (without.persons_photos_total, without.persons_photos_processed) == (None, None)
    assert (counted.persons_photos_total, counted.persons_photos_processed) == (5, 5)


# --- Spec 0551: neue Abweisungen, Ruecknahme, Zusammenspiel -----------------------------------

ANCHOR: Color = (240, 240, 20)
BLUE: Color = (20, 20, 220)
THREE: Color = (120, 20, 120)


@pytest.fixture
def stack_analyzer() -> FakeFaceAnalyzer:
    return FakeFaceAnalyzer(
        {
            ANCHOR: TWO_FACES,
            RED: [face_embedding(10)],
            GREEN: [face_embedding(11), face_embedding(12)],
            BLUE: [face_embedding(13)],
            THREE: [face_embedding(14), face_embedding(15), face_embedding(16)],
        }
    )


@pytest_asyncio.fixture
async def stack(
    tmp_path: Path, stack_analyzer: FakeFaceAnalyzer, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[PersonStack]:
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path / "cache"))
    async for built in person_stack(tmp_path, stack_analyzer):
        yield built


async def _two_persons(stack: PersonStack) -> tuple[int, int]:
    """Anna und Berta, festgelegt auf einem Foto eines eigenen Anker-Projekts - mit einpraegsamen
    Namen, nach denen in den Meldungen gesucht wird."""
    anchor = await stack.photo(await stack.project("Anker"), "anker", ANCHOR)
    return await stack.define("Annabell-Merkname", 0, anchor), await stack.define(
        "Bertrude-Merkname", 1, anchor
    )


async def _stack_snapshot(stack: PersonStack) -> dict[str, list[tuple[Any, ...]]]:
    async with stack.factory() as session:
        return {
            model.__tablename__: sorted(
                (tuple(row) for row in (await session.execute(select(model.__table__))).all()),
                key=repr,
            )
            for model in (Person, PersonReference, PhotoPersonDetection, PhotoPersonCorrection)
        }


async def _detect_on(stack: PersonStack, photo_id: int, person_id: int, index: int) -> None:
    box = face_box(index)
    async with stack.factory() as session:
        session.add(
            PhotoPersonDetection(
                photo_id=photo_id,
                person_id=person_id,
                computed_at=NOW,
                face_box_x=box.x,
                face_box_y=box.y,
                face_box_width=box.width,
                face_box_height=box.height,
            )
        )
        await session.commit()


async def _boxes_on(stack: PersonStack, photo_id: int) -> list[tuple[int, float | None]]:
    async with stack.factory() as session:
        rows = await session.execute(
            select(PhotoPersonCorrection.person_id, PhotoPersonCorrection.face_box_x).where(
                PhotoPersonCorrection.photo_id == photo_id,
                PhotoPersonCorrection.face_box_x.is_not(None),
            )
        )
        return [(person_id, x) for person_id, x in rows.all()]


async def _references_of(stack: PersonStack, person_id: int) -> int:
    async with stack.factory() as session:
        return (
            await session.execute(
                select(func.count())
                .select_from(PersonReference)
                .where(PersonReference.person_id == person_id)
            )
        ).scalar_one()


async def test_a_second_face_of_the_person_on_the_photo_is_refused_before_the_model(
    stack: PersonStack, stack_analyzer: FakeFaceAnalyzer
) -> None:
    anna, _ = await _two_persons(stack)
    photo = await stack.photo(await stack.project(), "a", GREEN)
    first = await stack.client.post(
        f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0}
    )
    assert first.status_code == 201
    before = await _stack_snapshot(stack)
    stack_analyzer.calls.clear()

    second = await stack.client.post(
        f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 1}
    )

    assert second.status_code == 409
    assert second.json()["detail"] == persons_module.FaceAlreadyAssignedOnPhoto.detail
    assert stack_analyzer.calls == []
    assert await _stack_snapshot(stack) == before


async def test_a_recognised_box_of_the_same_person_does_not_block(stack: PersonStack) -> None:
    anna, _ = await _two_persons(stack)
    photo = await stack.photo(await stack.project(), "a", GREEN)
    await _detect_on(stack, photo, anna, 0)

    response = await stack.client.post(
        f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 1}
    )

    assert response.status_code == 201
    assert response.json()["photo_persons"] == [
        {"person_id": anna, "origin": "corrected", "face": "shown"}
    ]


async def _learn_more(stack: PersonStack, person_id: int, count: int, *, face_index: int) -> None:
    """Weitere gezeigte Gesichter derselben Achse: Der Schwerpunkt bleibt dann so nah an ihr,
    dass ein neu gelerntes fremdes Gesicht der Person nicht "gleicht"."""
    project = await stack.project(f"Lernen-{person_id}")
    for index in range(count):
        photo = await stack.photo(project, f"l{index}", ANCHOR)
        response = await stack.client.post(
            f"/persons/{person_id}/references", json={"photo_id": photo, "face_index": face_index}
        )
        assert response.status_code == 201, response.text


@pytest.mark.parametrize("bound_by", ["korrektur", "erkennung"])
async def test_the_face_of_the_other_person_on_this_photo_is_refused(
    stack: PersonStack, bound_by: str
) -> None:
    anna, berta = await _two_persons(stack)
    await _learn_more(stack, anna, 2, face_index=0)
    photo = await stack.photo(await stack.project(), "a", GREEN)
    if bound_by == "korrektur":
        assert (
            await stack.client.post(
                f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0}
            )
        ).status_code == 201
    else:
        await _detect_on(stack, photo, anna, 0)
    before = await _stack_snapshot(stack)

    response = await stack.client.post(
        f"/persons/{berta}/references", json={"photo_id": photo, "face_index": 0}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == persons_module.FaceAssignedToOtherPerson.detail
    assert "Merkname" not in response.text
    assert await _stack_snapshot(stack) == before


async def test_the_other_persons_face_is_also_refused_when_defining(stack: PersonStack) -> None:
    anchor = await stack.photo(await stack.project("Anker"), "anker", ANCHOR)
    anna = await stack.define("Annabell-Merkname", 0, anchor)
    photo = await stack.photo(await stack.project(), "a", GREEN)
    await _detect_on(stack, photo, anna, 0)

    response = await stack.client.post(
        "/persons", json={"name": "Clara", "photo_id": photo, "face_index": 0}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == persons_module.FaceAssignedToOtherPerson.detail
    assert await stack.count(Person) == 1


async def test_the_stored_box_belongs_to_the_face_whose_embedding_is_stored(
    stack: PersonStack, stack_analyzer: FakeFaceAnalyzer
) -> None:
    """Merkmal und Box aus DEMSELBEN Detektionslauf, auch wenn der Detektor umordnet."""
    stack_analyzer.shuffle = True
    stack_analyzer.boxes_by_color = {THREE: [face_box(0), face_box(1), face_box(2)]}
    anna, _ = await _two_persons(stack)
    photo = await stack.photo(await stack.project(), "a", THREE)

    for _ in range(2):
        await stack.client.get(f"/photos/{photo}/faces")
    response = await stack.client.post(
        f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 2}
    )

    assert response.status_code == 201
    async with stack.factory() as session:
        stored = (
            await session.execute(
                select(PersonReference.embedding)
                .join(
                    PhotoPersonCorrection, PhotoPersonCorrection.reference_id == PersonReference.id
                )
                .where(PhotoPersonCorrection.photo_id == photo)
            )
        ).scalar_one()
    assert stored == pytest.approx(face_embedding(16))
    assert await _boxes_on(stack, photo) == [(anna, face_box(2).x)]


async def test_a_non_finite_box_behind_the_adapter_is_409_without_writing(
    stack: PersonStack, stack_analyzer: FakeFaceAnalyzer
) -> None:
    stack_analyzer.boxes_by_color = {RED: [FaceBox(x=math.nan, y=0.2, width=0.15, height=0.3)]}
    anna, _ = await _two_persons(stack)
    photo = await stack.photo(await stack.project(), "a", RED)
    before = await _stack_snapshot(stack)

    response = await stack.client.post(
        f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == persons_module.InvalidEmbedding.detail
    assert await _stack_snapshot(stack) == before


@pytest.mark.parametrize("field", ["face_box_x", "box"])
async def test_a_box_from_the_client_is_422(stack: PersonStack, field: str) -> None:
    anna, _ = await _two_persons(stack)
    photo = await stack.photo(await stack.project(), "a", RED)

    response = await stack.client.post(
        f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0, field: 0.5}
    )

    assert response.status_code == 422


async def test_the_revocation_removes_name_and_reference_and_frees_the_face(
    stack: PersonStack,
) -> None:
    anna, _ = await _two_persons(stack)
    project = await stack.project()
    photo = await stack.photo(project, "a", GREEN)
    await _detect_on(stack, photo, anna, 0)
    await stack.client.post(
        f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 1}
    )
    counted = {
        entry["id"]: entry["reference_count"]
        for entry in (await stack.client.get("/persons")).json()
    }

    revoked = await stack.client.put(f"/photos/{photo}/persons/{anna}", json={"applies": False})
    listing = await stack.client.get(f"/projects/{project}/unnamed-faces")

    assert revoked.status_code == 200
    assert revoked.json() == []
    after = {
        entry["id"]: entry["reference_count"]
        for entry in (await stack.client.get("/persons")).json()
    }
    assert after[anna] == counted[anna] - 1
    # Auch die erkannte Box haelt das Gesicht nicht mehr: Die Korrektur `false` geht vor.
    assert [(face["photo_id"], face["face_index"]) for face in listing.json()["faces"]] == [
        (photo, 0),
        (photo, 1),
    ]


async def test_the_person_filter_is_the_group_including_rejected_photos(
    stack: PersonStack,
) -> None:
    """Gleiche Menge wie bisher: ohne Bewertungsfilter, Reihenfolge `(taken_at, id)`, `total`,
    auch im Ausschuss; ein Foto mit beiden Namen steht in beiden Abfragen."""
    anna, berta = await _two_persons(stack)
    project = await stack.project()
    late = await stack.photo(project, "spaet", RED, taken_at=datetime(2026, 9, 29))
    early = await stack.photo(project, "frueh", RED, rejected=True, taken_at=datetime(2026, 9, 1))
    both = await stack.photo(project, "beide", GREEN, taken_at=datetime(2026, 9, 15))
    await stack.photo(project, "keiner", RED)
    await _detect_on(stack, late, anna, 0)
    await _detect_on(stack, early, anna, 0)
    await _detect_on(stack, both, anna, 0)
    await _detect_on(stack, both, berta, 1)

    for_anna = (
        await stack.client.get(f"/projects/{project}/photos", params={"person_id": anna})
    ).json()
    for_berta = (
        await stack.client.get(f"/projects/{project}/photos", params={"person_id": berta})
    ).json()

    assert [item["id"] for item in for_anna["items"]] == [early, both, late]
    assert for_anna["total"] == 3
    assert [item["id"] for item in for_berta["items"]] == [both]


async def test_changes_from_either_view_show_everywhere_on_the_next_load(
    stack: PersonStack,
) -> None:
    anna, _ = await _two_persons(stack)
    project = await stack.project()
    photo = await stack.photo(project, "a", GREEN)

    await stack.client.post(
        f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0}
    )
    filtered = (
        await stack.client.get(f"/projects/{project}/photos", params={"person_id": anna})
    ).json()
    listing = (await stack.client.get(f"/projects/{project}/unnamed-faces")).json()
    assert [item["id"] for item in filtered["items"]] == [photo]
    assert [item["persons"] for item in filtered["items"]] == [
        [{"person_id": anna, "origin": "corrected", "face": "shown"}]
    ]
    assert [(face["photo_id"], face["face_index"]) for face in listing["faces"]] == [(photo, 1)]

    # Umgekehrt: ein Entfernen aus der Detailansicht ist beim naechsten Laden der Auflistung da.
    await stack.client.put(f"/photos/{photo}/persons/{anna}", json={"applies": False})
    filtered = (
        await stack.client.get(f"/projects/{project}/photos", params={"person_id": anna})
    ).json()
    listing = (await stack.client.get(f"/projects/{project}/unnamed-faces")).json()
    assert filtered["items"] == []
    assert len(listing["faces"]) == 2


async def test_assigning_defining_removing_and_revoking_touch_nothing_else(
    stack: PersonStack,
) -> None:
    """Zwilling in der Zeit: Bewertungen, Motive, Statistik, Rangzeilen und Auswahlvorschlag
    stehen vor und nach allen vier Handlungen gleich, und kein Nacharbeits-Ereignis entsteht."""
    anchor = await stack.photo(await stack.project("Anker"), "anker", ANCHOR)
    anna = await stack.define("Anna", 0, anchor)
    project = await stack.project()
    photo = await stack.photo(project, "a", GREEN)
    other = await stack.photo(project, "b", BLUE)
    await stack.client.put(f"/photos/{photo}/rating", json={"status": "album_worthy"})
    person_tables = {
        "persons",
        "person_references",
        "photo_person_detections",
        "photo_person_corrections",
    }

    async def everything_else() -> tuple[Any, ...]:
        async with stack.factory() as session:
            tables = {
                table.name: sorted(
                    (tuple(row) for row in (await session.execute(select(table))).all()),
                    key=repr,
                )
                for table in Base.metadata.sorted_tables
                if table.name not in person_tables
            }
        stats = (await stack.client.get(f"/projects/{project}/stats")).json()
        items = (await stack.client.get(f"/projects/{project}/photos")).json()["items"]
        return tables, stats, [{**item, "persons": None} for item in items]

    before = await everything_else()
    await stack.client.post(
        f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0}
    )
    await stack.client.post("/persons", json={"name": "Berta", "photo_id": other, "face_index": 0})
    await stack.client.put(f"/photos/{other}/persons/{anna}", json={"applies": True})
    await stack.client.put(f"/photos/{other}/persons/{anna}", json={"applies": False})
    await stack.client.put(f"/photos/{photo}/persons/{anna}", json={"applies": False})

    assert await everything_else() == before


_WITHOUT_PERSON = {"leader": 1, "runner_up": 2, "weak": None}
_WITH_PERSON_ON_WEAK = {"leader": 1, "runner_up": None, "weak": 2}


class _DraftLay:
    """Ein erfolgreicher Lauf mit einem Event und von Hand gesetzten Vorschlagsplaetzen. `leader`
    und `runner_up` tragen Motiv `a`, `weak` (eine Vollfarbe mit einem Gesicht) traegt nichts und
    hat den schwaechsten Rang: Ein Neuaufbau gibt Platz 2 an `weak`, sobald dort eine wirksame
    Person steht, sonst an `runner_up`."""

    async def build(self, stack: PersonStack, stale: dict[str, int | None]) -> _DraftLay:
        self.stack = stack
        self.project = await stack.project()
        self.photos = {
            "leader": await stack.photo(self.project, "leader", None, taken_at=NOW),
            "runner_up": await stack.photo(
                self.project, "runner_up", None, taken_at=NOW + timedelta(minutes=30)
            ),
            "weak": await stack.photo(self.project, "weak", RED, taken_at=NOW + timedelta(hours=1)),
        }
        async with stack.factory() as session:
            # Zwei Plaetze: die Vorbelegung gaebe drei Fotos nur einen.
            project = await session.get(Project, self.project)
            assert project is not None
            project.selection_target = 2
            scoring_run = ScoringRun(
                project_id=self.project, status=ScanStatus.SUCCESS, started_at=NOW
            )
            session.add(scoring_run)
            await session.flush()
            run = CriterionScoringRun(
                project_id=self.project,
                scoring_run_id=scoring_run.id,
                status=ScanStatus.SUCCESS,
                started_at=NOW,
                finished_at=NOW,
                last_progress_at=NOW,
            )
            session.add(run)
            await session.flush()
            event = Event(
                criterion_scoring_run_id=run.id,
                position=1,
                started_at=NOW,
                ended_at=NOW + timedelta(hours=1),
            )
            session.add(event)
            await session.flush()
            self.run = run.id
            for role, rank in (("leader", 0.9), ("runner_up", 0.8), ("weak", 0.1)):
                await upsert_assessment(
                    session,
                    self.photos[role],
                    source=MotifAssessmentSource.CLOUD,
                    strengths={"a": 0.0 if role == "weak" else 1.0},
                    excluded_document=False,
                    provider="testanbieter",
                    computed_at=NOW,
                )
                session.add(
                    PhotoRanking(
                        criterion_scoring_run_id=run.id,
                        photo_id=self.photos[role],
                        event_id=event.id,
                        rank_score=rank,
                        rank_position=1,
                        selection_position=stale[role],
                    )
                )
            await session.commit()
        return self

    async def draft(self) -> dict[str, int | None]:
        async with self.stack.factory() as session:
            rows = await session.execute(
                select(PhotoRanking.photo_id, PhotoRanking.selection_position).where(
                    PhotoRanking.criterion_scoring_run_id == self.run
                )
            )
            positions = {photo_id: position for photo_id, position in rows.all()}
        return {role: positions[photo_id] for role, photo_id in self.photos.items()}

    async def rebuild(self) -> None:
        async with self.stack.factory() as session:
            await rebuild_run_selection(session, self.project)
            await session.commit()


@pytest.mark.parametrize(
    ("action", "anna_on_weak_before", "stale", "rebuilt"),
    [
        pytest.param("zuordnen", False, _WITHOUT_PERSON, _WITH_PERSON_ON_WEAK, id="put-zuordnung"),
        pytest.param("festlegen", False, _WITHOUT_PERSON, _WITH_PERSON_ON_WEAK, id="post-person"),
        pytest.param("referenz", False, _WITHOUT_PERSON, _WITH_PERSON_ON_WEAK, id="post-referenz"),
        pytest.param("loeschen", True, _WITH_PERSON_ON_WEAK, _WITHOUT_PERSON, id="delete-person"),
        pytest.param("filtern", True, _WITHOUT_PERSON, _WITH_PERSON_ON_WEAK, id="get-filter"),
    ],
)
async def test_no_person_endpoint_moves_the_draft_but_the_next_rebuild_does(
    stack: PersonStack,
    action: str,
    anna_on_weak_before: bool,
    stale: dict[str, int | None],
    rebuilt: dict[str, int | None],
) -> None:
    """Lage: ein veralteter Vorschlag, den ein Neuaufbau aendern wuerde. Der Endpunkt laesst ihn
    stehen, der Neuaufbau danach aendert ihn - das Paar steht in einem Fall, weil die erste
    Haelfte allein auch bei einem Vorschlag bestuende, der Personen nie liest."""
    anchor = await stack.photo(await stack.project("Anker"), "anker", ANCHOR)
    anna = await stack.define("Anna", 0, anchor)
    lay = await _DraftLay().build(stack, stale)
    weak = lay.photos["weak"]
    if anna_on_weak_before:
        await _detect_on(stack, weak, anna, 0)

    if action == "zuordnen":
        response = await stack.client.put(f"/photos/{weak}/persons/{anna}", json={"applies": True})
    elif action == "festlegen":
        response = await stack.client.post(
            "/persons", json={"name": "Berta", "photo_id": weak, "face_index": 0}
        )
    elif action == "referenz":
        response = await stack.client.post(
            f"/persons/{anna}/references", json={"photo_id": weak, "face_index": 0}
        )
    elif action == "loeschen":
        response = await stack.client.delete(f"/persons/{anna}")
    else:
        response = await stack.client.get(
            f"/projects/{lay.project}/photos", params={"person_id": anna}
        )

    assert response.is_success, response.text
    assert await lay.draft() == stale

    await lay.rebuild()

    assert await lay.draft() == rebuilt


# --- Die Schreibsperre ------------------------------------------------------------------------


class RecordingLock:
    """Ersatz fuer `_person_write_lock`, der meldet, sobald jemand an ihr wartet."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.waiting = asyncio.Event()

    async def __aenter__(self) -> None:
        if self._lock.locked():
            self.waiting.set()
        await self._lock.acquire()

    async def __aexit__(self, *exc: object) -> None:
        self._lock.release()


class Gate:
    """Haelt den ERSTEN Aufruf von `persons.assigned_face_boxes` fest - im kritischen Abschnitt -,
    bis die zweite Anfrage entweder die Pruefungen betreten hat (Umsetzung ohne Sperre) oder an der
    Sperre wartet. Beides ist beobachtet, keine Wartezeit."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, lock: RecordingLock | None) -> None:
        self.calls = 0
        self.second_entered = asyncio.Event()
        self.first_held = asyncio.Event()
        self.held_connections: list[int] = []
        self._lock = lock
        original = persons_module.assigned_face_boxes

        async def gated(session: AsyncSession, photo_ids: Any, **kwargs: Any) -> Any:
            self.calls += 1
            if self.calls == 1:
                self.first_held.set()
                await self._wait_for_the_second()
            else:
                self.second_entered.set()
            return await original(session, photo_ids, **kwargs)

        monkeypatch.setattr(persons_module, "assigned_face_boxes", gated)

    async def _wait_for_the_second(self) -> None:
        waiters = [asyncio.ensure_future(self.second_entered.wait())]
        if self._lock is not None:
            waiters.append(asyncio.ensure_future(self._lock.waiting.wait()))
        done, pending = await asyncio.wait(waiters, timeout=10, return_when=asyncio.FIRST_COMPLETED)
        for waiter in pending:
            waiter.cancel()
        assert done, "die zweite Anfrage kam nie an"


@pytest.fixture
def recording_lock(monkeypatch: pytest.MonkeyPatch) -> RecordingLock:
    lock = RecordingLock()
    monkeypatch.setattr(persons_api, "_person_write_lock", lock)
    return lock


async def _second_after_first_is_held(gate: Gate, call: Any) -> httpx.Response:
    await gate.first_held.wait()
    response: httpx.Response = await call()
    return response


async def test_the_same_face_for_both_persons_at_once_gives_one_201_and_one_409(
    stack: PersonStack, recording_lock: RecordingLock, monkeypatch: pytest.MonkeyPatch
) -> None:
    anna, berta = await _two_persons(stack)
    await _learn_more(stack, anna, 2, face_index=0)
    await _learn_more(stack, berta, 2, face_index=1)
    photo = await stack.photo(await stack.project(), "a", RED)
    references_before = await stack.count(PersonReference)
    gate = Gate(monkeypatch, recording_lock)

    first, second = await asyncio.gather(
        stack.client.post(f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0}),
        _second_after_first_is_held(
            gate,
            lambda: stack.client.post(
                f"/persons/{berta}/references", json={"photo_id": photo, "face_index": 0}
            ),
        ),
    )

    assert sorted([first.status_code, second.status_code]) == [201, 409]
    refused = first if first.status_code == 409 else second
    assert refused.json()["detail"] == persons_module.FaceAssignedToOtherPerson.detail
    assert len(await _boxes_on(stack, photo)) == 1
    assert await stack.count(PersonReference) == references_before + 1


async def test_two_assignments_at_the_cap_minus_one_learn_exactly_once(
    stack: PersonStack, recording_lock: RecordingLock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Obergrenze minus eins, zwei gleichzeitige Zuordnungen: genau die Obergrenze an Referenzen,
    und eine der beiden antwortet `learned: false`."""
    anna, _ = await _two_persons(stack)
    monkeypatch.setattr(persons_module, "MAX_REFERENCES_PER_PERSON", 2)
    project = await stack.project()
    one = await stack.photo(project, "a", RED)
    two = await stack.photo(project, "b", BLUE)
    gate = Gate(monkeypatch, recording_lock)

    first, second = await asyncio.gather(
        stack.client.post(f"/persons/{anna}/references", json={"photo_id": one, "face_index": 0}),
        _second_after_first_is_held(
            gate,
            lambda: stack.client.post(
                f"/persons/{anna}/references", json={"photo_id": two, "face_index": 0}
            ),
        ),
    )

    assert (first.status_code, second.status_code) == (201, 201)
    assert sorted([first.json()["learned"], second.json()["learned"]]) == [False, True]
    assert await _references_of(stack, anna) == 2


async def test_two_definitions_at_once_with_one_person_create_exactly_one(
    stack: PersonStack, recording_lock: RecordingLock, monkeypatch: pytest.MonkeyPatch
) -> None:
    anchor = await stack.photo(await stack.project("Anker"), "anker", ANCHOR)
    await stack.define("Anna", 0, anchor)
    project = await stack.project()
    one = await stack.photo(project, "a", RED)
    two = await stack.photo(project, "b", BLUE)
    gate = Gate(monkeypatch, recording_lock)

    first, second = await asyncio.gather(
        stack.client.post("/persons", json={"name": "Berta", "photo_id": one, "face_index": 0}),
        _second_after_first_is_held(
            gate,
            lambda: stack.client.post(
                "/persons", json={"name": "Clara", "photo_id": two, "face_index": 0}
            ),
        ),
    )

    assert sorted([first.status_code, second.status_code]) == [201, 409]
    assert await stack.count(Person) == 2


async def test_a_revocation_racing_an_assignment_ends_in_a_serial_order(
    stack: PersonStack, recording_lock: RecordingLock
) -> None:
    """Nie bleibt eine Referenz, deren Korrektur keine Box traegt, und nie eine Box ohne
    `applies`: Jede Referenz der Person haengt an einer Korrektur mit Box."""
    anna, _ = await _two_persons(stack)
    photo = await stack.photo(await stack.project(), "a", GREEN)
    assert (
        await stack.client.post(
            f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0}
        )
    ).status_code == 201

    await asyncio.gather(
        stack.client.put(f"/photos/{photo}/persons/{anna}", json={"applies": False}),
        stack.client.post(f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 1}),
    )

    async with stack.factory() as session:
        linked = (
            await session.execute(
                select(func.count())
                .select_from(PhotoPersonCorrection)
                .where(
                    PhotoPersonCorrection.person_id == anna,
                    PhotoPersonCorrection.reference_id.is_not(None),
                    PhotoPersonCorrection.face_box_x.is_not(None),
                    PhotoPersonCorrection.applies.is_(True),
                )
            )
        ).scalar_one()
    assert await _references_of(stack, anna) == linked


async def test_a_correction_box_written_during_detect_is_seen_by_the_repeated_check(
    stack: PersonStack, stack_analyzer: FakeFaceAnalyzer, tmp_path: Path
) -> None:
    """Erste Linie: Die Vorpruefung wird unter der Sperre wiederholt."""
    anna, _ = await _two_persons(stack)
    photo = await stack.photo(await stack.project(), "a", GREEN)
    foreign = face_box(1)
    references_before = await stack.count(PersonReference)

    def write_meanwhile(color: Color) -> None:
        if color != GREEN:
            return
        connection = sqlite3.connect(tmp_path / "personen.db")
        connection.execute(
            "INSERT INTO photo_person_corrections (photo_id, person_id, user_id, applies, "
            "updated_at, face_box_x, face_box_y, face_box_width, face_box_height) "
            "VALUES (?, ?, ?, 1, '2026-09-28 12:00:00', ?, ?, ?, ?)",
            (photo, anna, stack.user_id, foreign.x, foreign.y, foreign.width, foreign.height),
        )
        connection.commit()
        connection.close()

    stack_analyzer.on_detect = write_meanwhile

    response = await stack.client.post(
        f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == persons_module.FaceAlreadyAssignedOnPhoto.detail
    assert await _boxes_on(stack, photo) == [(anna, foreign.x)]
    assert await stack.count(PersonReference) == references_before


async def test_deleting_a_person_racing_an_assignment_leaves_no_row_of_her(
    stack: PersonStack, recording_lock: RecordingLock, monkeypatch: pytest.MonkeyPatch
) -> None:
    anna, _ = await _two_persons(stack)
    photo = await stack.photo(await stack.project(), "a", RED)
    gate = Gate(monkeypatch, recording_lock)

    assigned, deleted = await asyncio.gather(
        stack.client.post(f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0}),
        _second_after_first_is_held(gate, lambda: stack.client.delete(f"/persons/{anna}")),
    )

    assert deleted.status_code == 204
    assert assigned.status_code in (201, 404)
    async with stack.factory() as session:
        for model in (PhotoPersonCorrection, PhotoPersonDetection):
            remaining = (
                await session.execute(
                    select(func.count()).select_from(model).where(model.person_id == anna)
                )
            ).scalar_one()
            assert remaining == 0, model.__tablename__
    assert await _references_of(stack, anna) == 0
    assert await stack.count(Person) == 1


def _hold_detect(analyzer: FakeFaceAnalyzer, color: Color) -> tuple[threading.Event, asyncio.Event]:
    loop = asyncio.get_running_loop()
    release = threading.Event()
    paused = asyncio.Event()

    def before_return(seen: Color) -> None:
        if seen == color and not release.is_set():
            loop.call_soon_threadsafe(paused.set)
            assert release.wait(timeout=10)

    analyzer.before_detect_returns = before_return
    return release, paused


async def test_the_model_never_runs_under_the_lock(
    stack: PersonStack, stack_analyzer: FakeFaceAnalyzer
) -> None:
    """Waehrend ein `detect` angehalten ist, laeuft ein PUT einer anderen Person durch."""
    anna, berta = await _two_persons(stack)
    photo = await stack.photo(await stack.project(), "a", RED)
    release, paused = _hold_detect(stack_analyzer, RED)

    assignment = asyncio.ensure_future(
        stack.client.post(f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0})
    )
    await paused.wait()
    put = await stack.client.put(f"/photos/{photo}/persons/{berta}", json={"applies": True})
    release.set()

    assert put.status_code == 200
    assert (await assignment).status_code == 201


async def test_no_connection_is_held_during_the_model_call_or_waiting_for_the_lock(
    stack: PersonStack,
    stack_analyzer: FakeFaceAnalyzer,
    recording_lock: RecordingLock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anna, berta = await _two_persons(stack)
    project = await stack.project()
    photo = await stack.photo(project, "a", RED)
    other = await stack.photo(project, "b", BLUE)
    release, paused = _hold_detect(stack_analyzer, RED)
    checkouts = stack.pool.checkouts

    single = asyncio.ensure_future(
        stack.client.post(f"/persons/{anna}/references", json={"photo_id": photo, "face_index": 0})
    )
    await paused.wait()
    held_during_model = stack.pool.held
    borrowed_before_model = stack.pool.checkouts - checkouts
    release.set()
    assert (await single).status_code == 201

    # Die zweite Zuordnung wartet an der Sperre, waehrend die erste im kritischen Abschnitt
    # festgehalten ist: genau deren Verbindung ist ausgeliehen.
    gate = Gate(monkeypatch, recording_lock)
    observed: list[int] = []
    original_wait = gate._wait_for_the_second

    async def measuring_wait() -> None:
        await original_wait()
        observed.append(stack.pool.held)

    monkeypatch.setattr(gate, "_wait_for_the_second", measuring_wait)
    first, second = await asyncio.gather(
        stack.client.post(
            f"/persons/{berta}/references", json={"photo_id": other, "face_index": 0}
        ),
        _second_after_first_is_held(
            gate,
            lambda: stack.client.post(
                f"/persons/{anna}/references", json={"photo_id": other, "face_index": 0}
            ),
        ),
    )

    assert held_during_model == 0
    assert borrowed_before_model > 0
    assert recording_lock.waiting.is_set()
    assert observed == [1]
    assert sorted([first.status_code, second.status_code]) == [201, 409]


async def test_every_write_records_the_calling_user_after_the_connection_was_released(
    stack: PersonStack,
) -> None:
    """Ueber den echten API-Weg, je Nutzer einmal: Zuordnung, Festlegung und Ruecknahme schreiben
    die `user_id` des Aufrufers und enden nie in `500`."""
    anchor = await stack.photo(await stack.project("Anker"), "anker", ANCHOR)
    anna = await stack.define("Anna", 0, anchor)
    project = await stack.project()
    photos = [
        await stack.photo(project, f"p{index}", color)
        for index, color in enumerate((RED, BLUE, GREEN))
    ]
    partner_token = await stack.second_user_token()
    async with stack.factory() as session:
        partner_id = (
            await session.execute(select(User.id).where(User.username == "partnerin"))
        ).scalar_one()

    async def writer(photo_id: int) -> int | None:
        async with stack.factory() as session:
            return (
                await session.execute(
                    select(PhotoPersonCorrection.user_id).where(
                        PhotoPersonCorrection.photo_id == photo_id
                    )
                )
            ).scalar_one_or_none()

    for token, user_id in ((None, stack.user_id), (partner_token, partner_id)):
        headers = {} if token is None else {"Authorization": f"Bearer {token}"}
        assigned = await stack.client.post(
            f"/persons/{anna}/references",
            json={"photo_id": photos[0], "face_index": 0},
            headers=headers,
        )
        assert assigned.status_code == 201
        assert await writer(photos[0]) == user_id
        revoked = await stack.client.put(
            f"/photos/{photos[0]}/persons/{anna}", json={"applies": False}, headers=headers
        )
        assert revoked.status_code == 200
        assert await writer(photos[0]) == user_id
        if token is None:
            defined = await stack.client.post(
                "/persons", json={"name": "Berta", "photo_id": photos[1], "face_index": 0}
            )
            assert defined.status_code == 201
            assert await writer(photos[1]) == user_id


_REPO = Path(__file__).resolve().parents[2]


def test_the_backend_runs_as_exactly_one_api_process() -> None:
    """Voraussetzung der Schreibsperre: kein `--workers`, kein `WEB_CONCURRENCY`."""
    files = [_REPO / "backend" / "Dockerfile", *sorted(_REPO.glob("docker-compose*.yml"))]
    texts = {path.name: path.read_text(encoding="utf-8") for path in files}

    for name, text in texts.items():
        assert "--workers" not in text, name
        assert "WEB_CONCURRENCY" not in text, name
    # Gegenprobe: Der Waechter findet den Startaufruf dort, wo er steht - sonst waere er leer.
    for name in ("Dockerfile", "docker-compose.yml"):
        assert re.search(r"uvicorn[\"', ]+photosort\.main:app", texts[name]), name
