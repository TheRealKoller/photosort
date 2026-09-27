"""Die sieben Personen-Endpunkte und `PhotoOut.persons`/der Personenfilter (S1-S9).

Der Analyzer kommt ueber die ueberschreibbare Dependency `get_face_analyzer` - die echten Modelle
laufen hier nie (Sperre in `conftest.py`). Merkmale sind Basisvektoren fern jeder Schwelle.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import persons as persons_module
from photosort.api.persons import get_face_analyzer
from photosort.config import settings
from photosort.face_analysis import MODEL_KEY
from photosort.main import app
from photosort.models import (
    FeedbackEvent,
    Person,
    PersonReference,
    Photo,
    PhotoMotifStrength,
    PhotoPersonCorrection,
    PhotoPersonDetection,
    Project,
    User,
)
from photosort.persons import create_person, set_correction
from photosort.security import create_access_token, hash_password
from tests.face_fakes import (
    SENTINEL_TEXT,
    Color,
    FakeFaceAnalyzer,
    face_embedding,
    write_display_variant,
)

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
    assert set(response.json()) == {"id", "name", "reference_count"}
    assert response.json()["name"] == "Anna"
    assert response.json()["reference_count"] == 1
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


async def test_a_reference_assigns_writes_no_feedback_event_and_is_capped(
    client: httpx.AsyncClient,
    lay: Lay,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = await lay.project()
    anchor = await lay.photo(project, "anker")
    other = await lay.photo(project, "b", GREEN)
    await db_session.commit()
    anna = await _define(db_session, "Anna", 0, anchor)
    monkeypatch.setattr(persons_module, "MAX_REFERENCES_PER_PERSON", 2)
    project_id, other_id, anna_id = project.id, other.id, anna.id

    added = await client.post(
        f"/persons/{anna_id}/references", json={"photo_id": other_id, "face_index": 0}
    )
    capped = await client.post(
        f"/persons/{anna_id}/references", json={"photo_id": other_id, "face_index": 0}
    )

    assert added.status_code == 201
    assert added.json()["reference_count"] == 2
    assert capped.status_code == 409
    assert capped.json()["detail"] == persons_module.ReferenceLimitReached.detail
    listing = (await client.get(f"/projects/{project_id}/photos")).json()["items"]
    by_id = {item["id"]: item["persons"] for item in listing}
    assert by_id[other_id] == [{"person_id": anna_id, "origin": "corrected"}]
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

    assert added.json() == [{"person_id": anna.id, "origin": "corrected"}]
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
        {"person_id": anna, "origin": "recognized"},
        {"person_id": berta, "origin": "recognized"},
    ]
    assert origins[ids["erkannt-entfernt"]] == []
    assert all(
        set(entry) == {"person_id", "origin"} for item in everything for entry in item["persons"]
    )


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
