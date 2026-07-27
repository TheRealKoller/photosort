from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import Photo, Project, Rating, RatingStatus, User
from photosort.security import create_access_token, hash_password


async def _make_project(session: AsyncSession) -> Project:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _make_photo(session: AsyncSession, project: Project, path: str = "a.jpg") -> Photo:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag="etag-1",
        content_length=100,
        taken_at=now,
        last_modified=now,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _make_second_user(session: AsyncSession) -> tuple[User, str]:
    user = User(username="other-user", password_hash=hash_password("irrelevant"))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, create_access_token(user)


async def test_put_rating_creates_new_rating(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "favorite"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["photo_id"] == photo.id
    assert body["status"] == "favorite"

    result = await db_session.execute(select(Rating).where(Rating.photo_id == photo.id))
    stored = result.scalar_one()
    assert stored.status == RatingStatus.FAVORITE


async def test_put_rating_overwrites_existing_rating_without_creating_a_second_row(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    await authenticated_api_client.put(f"/photos/{photo.id}/rating", json={"status": "favorite"})
    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "rejected"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    result = await db_session.execute(select(Rating).where(Rating.photo_id == photo.id))
    stored = result.scalars().all()
    assert len(stored) == 1
    assert stored[0].status == RatingStatus.REJECTED


async def test_put_rating_returns_404_for_unknown_photo(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.put("/photos/999/rating", json={"status": "favorite"})

    assert response.status_code == 404


async def test_put_rating_rejects_invalid_status(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "not-a-real-status"}
    )

    assert response.status_code == 422


async def test_put_rating_requires_auth(
    db_session: AsyncSession, api_client: httpx.AsyncClient
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await api_client.put(f"/photos/{photo.id}/rating", json={"status": "favorite"})

    assert response.status_code == 401


async def test_put_rating_never_overwrites_another_users_rating(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Security-Muss-Kriterium (specs/features/0002): user_id kommt ausschliesslich aus dem
    JWT, nie aus Body/Query - sonst koennte Nutzer A die Bewertung von Nutzer B ueberschreiben."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    other_user, other_token = await _make_second_user(db_session)
    db_session.add(Rating(photo_id=photo.id, user_id=other_user.id, status=RatingStatus.FAVORITE))
    await db_session.commit()

    await authenticated_api_client.put(f"/photos/{photo.id}/rating", json={"status": "rejected"})

    result = await db_session.execute(
        select(Rating).where(Rating.photo_id == photo.id, Rating.user_id == other_user.id)
    )
    other_rating = result.scalar_one()
    assert other_rating.status == RatingStatus.FAVORITE


async def test_delete_rating_resets_to_unrated(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    await authenticated_api_client.put(f"/photos/{photo.id}/rating", json={"status": "favorite"})

    response = await authenticated_api_client.delete(f"/photos/{photo.id}/rating")

    assert response.status_code == 204
    result = await db_session.execute(select(Rating).where(Rating.photo_id == photo.id))
    assert result.scalars().all() == []


async def test_delete_rating_is_idempotent_when_no_rating_exists(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await authenticated_api_client.delete(f"/photos/{photo.id}/rating")

    assert response.status_code == 204


async def test_delete_rating_returns_404_for_unknown_photo(
    authenticated_api_client: httpx.AsyncClient,
) -> None:
    response = await authenticated_api_client.delete("/photos/999/rating")

    assert response.status_code == 404


async def test_delete_rating_requires_auth(
    db_session: AsyncSession, api_client: httpx.AsyncClient
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await api_client.delete(f"/photos/{photo.id}/rating")

    assert response.status_code == 401
