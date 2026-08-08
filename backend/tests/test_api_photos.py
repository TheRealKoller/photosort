from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.config import settings
from photosort.models import Photo, PhotoCategory, PhotoScore, Project, Rating, RatingStatus, User
from photosort.security import hash_password
from photosort.thumbnails import display_path, thumbnail_path


async def _make_project(session: AsyncSession) -> Project:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _make_photo(
    session: AsyncSession, project: Project, path: str, taken_at: datetime
) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag="etag-1",
        content_length=100,
        taken_at=taken_at,
        last_modified=taken_at,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _make_second_user(session: AsyncSession) -> User:
    user = User(username="other-user", password_hash=hash_password("irrelevant"))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def test_list_photos_returns_photos_ordered_by_taken_at(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    later = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
    earlier = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

    response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [earlier.id, later.id]


async def test_list_photos_includes_ratings_of_all_users(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    other_user = await _make_second_user(db_session)

    # Der eigene Nutzer der authenticated_api_client-Fixture ist "testuser".
    me = (
        await db_session.execute(select(User).where(User.username == "testuser"))
    ).scalar_one()
    db_session.add(Rating(photo_id=photo.id, user_id=me.id, status=RatingStatus.FAVORITE))
    db_session.add(Rating(photo_id=photo.id, user_id=other_user.id, status=RatingStatus.REJECTED))
    await db_session.commit()

    response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

    assert response.status_code == 200
    ratings = response.json()["items"][0]["ratings"]
    by_username = {r["username"]: r["status"] for r in ratings}
    assert by_username == {"testuser": "favorite", "other-user": "rejected"}


async def test_list_photos_includes_suggestion_when_no_own_rating_exists(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    other = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
    db_session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=1.0,
            exposure=0.2,
            duplicate_of=other.id,
            suggested_status=RatingStatus.REJECTED,
            computed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.commit()

    response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()["items"]}
    suggestion = by_id[photo.id]["suggestion"]
    assert suggestion["status"] == "rejected"
    assert suggestion["reason"] == "duplicate"
    assert suggestion["duplicate_of"] == other.id
    assert by_id[other.id]["suggestion"] is None


async def test_suggestion_reason_is_low_quality_without_duplicate_of(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    db_session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=1.0,
            exposure=0.2,
            suggested_status=RatingStatus.REJECTED,
            computed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.commit()

    response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

    suggestion = response.json()["items"][0]["suggestion"]
    assert suggestion["reason"] == "low_quality"
    assert suggestion["duplicate_of"] is None


async def test_suggestion_reason_is_top_pick_for_album_worthy_status(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    # specs/features/0024-top-photo-selection-category-mix.md: ALBUM_WORTHY wird ausschliesslich
    # vom neuen select_top_photos-Job gesetzt (Phase A setzt praktisch nur REJECTED) - reason muss
    # in diesem Fall "top_pick" sein, nicht "low_quality"/"duplicate".
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    db_session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=1.0,
            exposure=0.2,
            local_quality_score=5.0,
            category=PhotoCategory.LANDSCAPE,
            suggested_status=RatingStatus.ALBUM_WORTHY,
            computed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.commit()

    response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

    suggestion = response.json()["items"][0]["suggestion"]
    assert suggestion["status"] == "album_worthy"
    assert suggestion["reason"] == "top_pick"
    assert suggestion["category"] == "landscape"


async def test_suggestion_category_is_null_when_not_classified(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    db_session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=1.0,
            exposure=0.2,
            suggested_status=RatingStatus.REJECTED,
            computed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.commit()

    response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

    assert response.json()["items"][0]["suggestion"]["category"] is None


async def test_list_photos_hides_suggestion_once_own_rating_exists(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Akzeptanzkriterium der Spec: suggestion ist null, sobald der anfragende Nutzer eine eigene
    Rating-Zeile fuer dieses Foto hat - auch wenn PhotoScore weiterhin einen Vorschlag traegt."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    db_session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=1.0,
            exposure=0.2,
            suggested_status=RatingStatus.REJECTED,
            computed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.commit()
    await authenticated_api_client.put(f"/photos/{photo.id}/rating", json={"status": "rejected"})

    response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

    assert response.json()["items"][0]["suggestion"] is None


async def test_list_photos_suggestion_is_null_without_suggested_status(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Ein PhotoScore ohne suggested_status (regulaerer Fall der Spec: "Alle uebrigen Fotos ...
    suggested_status bleibt fuer sie None") darf keine sichtbare suggestion erzeugen."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    db_session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=100.0,
            exposure=0.0,
            local_quality_score=100.0,
            cluster_key="cluster-0",
            computed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.commit()

    response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

    assert response.json()["items"][0]["suggestion"] is None


async def test_list_photos_filters_by_own_unrated(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    rated = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    unrated = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
    await authenticated_api_client.put(f"/photos/{rated.id}/rating", json={"status": "favorite"})

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "unrated"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [unrated.id]
    assert body["total"] == 1


async def test_list_photos_filters_by_own_rating_status(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    favorite = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    rejected = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
    await authenticated_api_client.put(f"/photos/{favorite.id}/rating", json={"status": "favorite"})
    await authenticated_api_client.put(f"/photos/{rejected.id}/rating", json={"status": "rejected"})

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "favorite"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [favorite.id]


async def test_list_photos_filter_is_scoped_to_own_rating_not_others(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Filter "unbewertet" darf nicht durch die Bewertung des ANDEREN Nutzers beeinflusst
    werden - jeder Nutzer filtert ausschliesslich nach der eigenen Bewertung
    (specs/features/0002)."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    other_user = await _make_second_user(db_session)
    db_session.add(Rating(photo_id=photo.id, user_id=other_user.id, status=RatingStatus.FAVORITE))
    await db_session.commit()

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "unrated"}
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [photo.id]


async def test_list_photos_pagination(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    for i in range(5):
        await _make_photo(db_session, project, f"{i}.jpg", datetime(2023, 1, i + 1, tzinfo=UTC))

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"limit": 2, "offset": 2}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    assert body["items"][0]["relative_path"] == "2.jpg"


async def test_list_photos_returns_empty_list_when_filter_matches_nothing(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "favorite"}
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_list_photos_returns_404_for_unknown_project(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.get("/projects/999/photos")

    assert response.status_code == 404


async def test_list_photos_requires_auth(
    db_session: AsyncSession, api_client: httpx.AsyncClient
) -> None:
    project = await _make_project(db_session)

    response = await api_client.get(f"/projects/{project.id}/photos")

    assert response.status_code == 401


async def test_get_photo_image_returns_cached_thumbnail_bytes(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path))
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    thumbnail_path(tmp_path, photo.id, photo.etag).write_bytes(b"fake-thumbnail-bytes")

    response = await authenticated_api_client.get(
        f"/photos/{photo.id}/image", params={"variant": "thumbnail"}
    )

    assert response.status_code == 200
    assert response.content == b"fake-thumbnail-bytes"
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_get_photo_image_returns_display_variant(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path))
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    display_path(tmp_path, photo.id, photo.etag).write_bytes(b"fake-display-bytes")

    response = await authenticated_api_client.get(
        f"/photos/{photo.id}/image", params={"variant": "display"}
    )

    assert response.status_code == 200
    assert response.content == b"fake-display-bytes"


async def test_get_photo_image_returns_404_when_not_yet_generated(
    authenticated_api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "photo_cache_dir", str(tmp_path))
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

    response = await authenticated_api_client.get(
        f"/photos/{photo.id}/image", params={"variant": "thumbnail"}
    )

    assert response.status_code == 404


async def test_get_photo_image_returns_404_for_unknown_photo(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.get(
        "/photos/999/image", params={"variant": "thumbnail"}
    )

    assert response.status_code == 404


async def test_get_photo_image_rejects_invalid_variant(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

    response = await authenticated_api_client.get(
        f"/photos/{photo.id}/image", params={"variant": "../../etc/passwd"}
    )

    assert response.status_code == 422


async def test_get_photo_image_requires_auth(
    db_session: AsyncSession, api_client: httpx.AsyncClient
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

    response = await api_client.get(f"/photos/{photo.id}/image", params={"variant": "thumbnail"})

    assert response.status_code == 401
