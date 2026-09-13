"""Die drei Schreibendpunkte auf der Bewertungszeile.

INVARIANTE UEBER ALLEN FAELLEN DIESER DATEI: Es gibt keine Zeile mit
`status IS NULL AND favorite IS FALSE`. `assert_no_empty_rating_rows` laeuft als Nachsatz JEDES
Falls - nicht nur dort, wo jemand daran gedacht hat. Eine solche Zeile waere auf keinem Lesepfad
als Fehler erkennbar: sie liest sich wie eine Bewertung ohne Inhalt, unterdrueckt zugleich
`PhotoOut.suggestion` und macht das Foto dauerhaft "bewertet", ohne dass ein Handgriff der
Oberflaeche sie wieder entfernen koennte.
"""

from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import Photo, Project, Rating, RatingStatus, User
from photosort.security import create_access_token, hash_password


async def assert_no_empty_rating_rows(session: AsyncSession) -> None:
    """Der Nachsatz jedes Falls dieser Datei - siehe Modul-Docstring."""
    session.expire_all()
    empty = (
        (
            await session.execute(
                select(Rating).where(Rating.status.is_(None), Rating.favorite.is_(False))
            )
        )
        .scalars()
        .all()
    )
    assert empty == [], f"leere Bewertungszeile(n) uebrig: {[row.id for row in empty]}"


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
        taken_at_original=now,
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


async def _stored_rating(session: AsyncSession, photo_id: int, user_id: int) -> Rating | None:
    session.expire_all()
    return (
        await session.execute(
            select(Rating).where(Rating.photo_id == photo_id, Rating.user_id == user_id)
        )
    ).scalar_one_or_none()


async def _own_user_id(session: AsyncSession) -> int:
    """Der Nutzer des `authenticated_api_client` - der erste angelegte Bestandsnutzer."""
    return (await session.execute(select(User.id).order_by(User.id).limit(1))).scalar_one()


# --- PUT /photos/{id}/rating: die Albumentscheidung ---------------------------------------------


async def test_put_rating_creates_new_rating(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "album_worthy"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["photo_id"] == photo.id
    assert body["status"] == "album_worthy"
    assert body["favorite"] is False

    result = await db_session.execute(select(Rating).where(Rating.photo_id == photo.id))
    stored = result.scalar_one()
    assert stored.status == RatingStatus.ALBUM_WORTHY
    assert stored.favorite is False

    await assert_no_empty_rating_rows(db_session)


async def test_put_rating_overwrites_existing_rating_without_creating_a_second_row(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "album_worthy"}
    )
    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "rejected"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    result = await db_session.execute(select(Rating).where(Rating.photo_id == photo.id))
    stored = result.scalars().all()
    assert len(stored) == 1
    assert stored[0].status == RatingStatus.REJECTED

    await assert_no_empty_rating_rows(db_session)


async def test_put_rating_leaves_the_favorite_marker_untouched(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Auflage S7, erste Haelfte: Der Endpunkt schreibt GENAU SEIN FELD. Ein gemeinsamer
    Schreibpfad aus einem teilbefuellten Modell setzte hier das Kennzeichen still zurueck."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    await authenticated_api_client.put(f"/photos/{photo.id}/favorite", json={"favorite": True})

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "rejected"}
    )

    assert response.status_code == 200
    assert response.json()["favorite"] is True
    stored = await _stored_rating(db_session, photo.id, await _own_user_id(db_session))
    assert stored is not None
    assert stored.favorite is True
    assert stored.status == RatingStatus.REJECTED

    await assert_no_empty_rating_rows(db_session)


async def test_put_rating_returns_404_for_unknown_photo(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    response = await authenticated_api_client.put(
        "/photos/999/rating", json={"status": "album_worthy"}
    )

    assert response.status_code == 404

    await assert_no_empty_rating_rows(db_session)


async def test_put_rating_rejects_invalid_status(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "not-a-real-status"}
    )

    assert response.status_code == 422

    await assert_no_empty_rating_rows(db_session)


async def test_put_rating_rejects_the_status_that_left_the_vocabulary(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`favorite` ist kein Bewertungsstatus mehr. Ein stehengebliebener Aufrufer bekommt `422`
    statt still eine Albumentscheidung zu schreiben, die er nicht gemeint hat."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "favorite"}
    )

    assert response.status_code == 422
    assert await _stored_rating(db_session, photo.id, await _own_user_id(db_session)) is None

    await assert_no_empty_rating_rows(db_session)


async def test_put_rating_rejects_a_null_status(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Auflage S8: `null` ist KEIN zulaessiger Body-Wert, sondern ausschliesslich das Ergebnis
    von `DELETE`. Waere er zulaessig, entstuende die verbotene Zeile ueber den regulaeren
    Schreibweg."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": None}
    )

    assert response.status_code == 422

    await assert_no_empty_rating_rows(db_session)


async def test_put_rating_requires_auth(
    db_session: AsyncSession, api_client: httpx.AsyncClient
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await api_client.put(f"/photos/{photo.id}/rating", json={"status": "album_worthy"})

    assert response.status_code == 401

    await assert_no_empty_rating_rows(db_session)


async def test_put_rating_never_overwrites_another_users_rating(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Auflage S7: `user_id` kommt ausschliesslich aus dem JWT, nie aus Body/Query - sonst
    koennte Nutzer A die Zeile von Nutzer B ueberschreiben (Broken Object-Level
    Authorization)."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    other_user, _ = await _make_second_user(db_session)
    db_session.add(
        Rating(photo_id=photo.id, user_id=other_user.id, status=RatingStatus.ALBUM_WORTHY)
    )
    await db_session.commit()

    await authenticated_api_client.put(f"/photos/{photo.id}/rating", json={"status": "rejected"})

    other_rating = await _stored_rating(db_session, photo.id, other_user.id)
    assert other_rating is not None
    assert other_rating.status == RatingStatus.ALBUM_WORTHY

    await assert_no_empty_rating_rows(db_session)


# --- DELETE /photos/{id}/rating: nur die Albumentscheidung zuruecknehmen ------------------------


async def test_delete_rating_resets_to_unrated(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "album_worthy"}
    )

    response = await authenticated_api_client.delete(f"/photos/{photo.id}/rating")

    assert response.status_code == 204
    result = await db_session.execute(select(Rating).where(Rating.photo_id == photo.id))
    assert result.scalars().all() == []

    await assert_no_empty_rating_rows(db_session)


async def test_delete_rating_keeps_a_row_that_still_carries_the_favorite_marker(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Zusicherung 15: `DELETE` nimmt NUR `status` zurueck. Die naive Zeilenloeschung verliert
    den Favoriten ohne jede Meldung."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    await authenticated_api_client.put(f"/photos/{photo.id}/favorite", json={"favorite": True})
    await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "album_worthy"}
    )

    response = await authenticated_api_client.delete(f"/photos/{photo.id}/rating")

    assert response.status_code == 204
    stored = await _stored_rating(db_session, photo.id, await _own_user_id(db_session))
    assert stored is not None
    assert stored.status is None
    assert stored.favorite is True

    await assert_no_empty_rating_rows(db_session)


async def test_delete_rating_is_idempotent_when_no_rating_exists(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await authenticated_api_client.delete(f"/photos/{photo.id}/rating")

    assert response.status_code == 204

    await assert_no_empty_rating_rows(db_session)


async def test_delete_rating_is_idempotent_on_a_row_without_an_album_decision(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Zweimal hintereinander auf eine reine Favoritenzeile: `204`, und die Zeile steht danach
    unveraendert - der zweite Aufruf darf sie nicht als "leer" einsammeln."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    await authenticated_api_client.put(f"/photos/{photo.id}/favorite", json={"favorite": True})

    first = await authenticated_api_client.delete(f"/photos/{photo.id}/rating")
    second = await authenticated_api_client.delete(f"/photos/{photo.id}/rating")

    assert (first.status_code, second.status_code) == (204, 204)
    stored = await _stored_rating(db_session, photo.id, await _own_user_id(db_session))
    assert stored is not None
    assert stored.favorite is True

    await assert_no_empty_rating_rows(db_session)


async def test_delete_rating_returns_404_for_unknown_photo(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    response = await authenticated_api_client.delete("/photos/999/rating")

    assert response.status_code == 404

    await assert_no_empty_rating_rows(db_session)


async def test_delete_rating_requires_auth(
    db_session: AsyncSession, api_client: httpx.AsyncClient
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await api_client.delete(f"/photos/{photo.id}/rating")

    assert response.status_code == 401

    await assert_no_empty_rating_rows(db_session)


async def test_delete_rating_never_touches_another_users_row(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    other_user, _ = await _make_second_user(db_session)
    db_session.add(
        Rating(photo_id=photo.id, user_id=other_user.id, status=RatingStatus.ALBUM_WORTHY)
    )
    await db_session.commit()

    await authenticated_api_client.delete(f"/photos/{photo.id}/rating")

    other_rating = await _stored_rating(db_session, photo.id, other_user.id)
    assert other_rating is not None
    assert other_rating.status == RatingStatus.ALBUM_WORTHY

    await assert_no_empty_rating_rows(db_session)


# --- PUT /photos/{id}/favorite: das Kennzeichen, unabhaengig ------------------------------------


async def test_put_favorite_creates_a_row_without_an_album_decision(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/favorite", json={"favorite": True}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["photo_id"] == photo.id
    assert body["favorite"] is True
    assert body["status"] is None

    stored = await _stored_rating(db_session, photo.id, await _own_user_id(db_session))
    assert stored is not None
    assert stored.status is None
    assert stored.favorite is True

    await assert_no_empty_rating_rows(db_session)


async def test_put_favorite_leaves_the_album_decision_untouched(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Auflage S7, zweite Haelfte - der stille Verlust, dessentwegen die Trennung ueberhaupt
    entsteht: Das Markieren als Favorit darf die Albumentscheidung nicht zuruecksetzen."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "album_worthy"}
    )

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/favorite", json={"favorite": True}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "album_worthy"
    stored = await _stored_rating(db_session, photo.id, await _own_user_id(db_session))
    assert stored is not None
    assert stored.status == RatingStatus.ALBUM_WORTHY
    assert stored.favorite is True

    await assert_no_empty_rating_rows(db_session)


async def test_put_favorite_false_deletes_the_row_when_nothing_else_remains(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Auflage S8: Die Loeschung der leergewordenen Zeile steht an EINER Stelle, die alle drei
    Endpunkte durchlaufen - auch dieser."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    await authenticated_api_client.put(f"/photos/{photo.id}/favorite", json={"favorite": True})

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/favorite", json={"favorite": False}
    )

    assert response.status_code == 200
    assert response.json()["favorite"] is False
    assert await _stored_rating(db_session, photo.id, await _own_user_id(db_session)) is None

    await assert_no_empty_rating_rows(db_session)


async def test_put_favorite_false_keeps_a_row_that_carries_an_album_decision(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    await authenticated_api_client.put(f"/photos/{photo.id}/rating", json={"status": "rejected"})
    await authenticated_api_client.put(f"/photos/{photo.id}/favorite", json={"favorite": True})

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/favorite", json={"favorite": False}
    )

    assert response.status_code == 200
    stored = await _stored_rating(db_session, photo.id, await _own_user_id(db_session))
    assert stored is not None
    assert stored.status == RatingStatus.REJECTED
    assert stored.favorite is False

    await assert_no_empty_rating_rows(db_session)


async def test_put_favorite_false_on_an_untouched_photo_creates_nothing(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der Weg, auf dem die verbotene Zeile am naechsten liegt: ein Ausschalten ohne
    vorhandene Zeile darf keine leere anlegen."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/favorite", json={"favorite": False}
    )

    assert response.status_code == 200
    assert await _stored_rating(db_session, photo.id, await _own_user_id(db_session)) is None

    await assert_no_empty_rating_rows(db_session)


async def test_put_favorite_is_idempotent(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    first = await authenticated_api_client.put(
        f"/photos/{photo.id}/favorite", json={"favorite": True}
    )
    second = await authenticated_api_client.put(
        f"/photos/{photo.id}/favorite", json={"favorite": True}
    )

    assert (first.status_code, second.status_code) == (200, 200)
    rows = (
        (
            await db_session.execute(
                select(Rating)
                .where(Rating.photo_id == photo.id)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1

    await assert_no_empty_rating_rows(db_session)


async def test_put_favorite_returns_404_for_unknown_photo(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Auflage S1: eigener Nachweis je Endpunkt - fuer diesen Router gibt es kein
    Vollstaendigkeitsnetz in `test_auth_guard.py`."""
    response = await authenticated_api_client.put("/photos/999/favorite", json={"favorite": True})

    assert response.status_code == 404

    await assert_no_empty_rating_rows(db_session)


async def test_put_favorite_requires_auth(
    db_session: AsyncSession, api_client: httpx.AsyncClient
) -> None:
    """Auflage S1: Beide Router tragen bewusst KEINE router-weite `dependencies`-Liste, und
    `_protected_router_operations()` fuehrt sie nicht - ein vergessener `current_user`-Parameter
    waere hier still oeffentlich."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await api_client.put(f"/photos/{photo.id}/favorite", json={"favorite": True})

    assert response.status_code == 401
    # Nicht nur der Statuscode: ein "401 nach dem Schreiben" waere kein Schutz.
    db_session.expire_all()
    assert (await db_session.execute(select(Rating))).scalars().all() == []

    await assert_no_empty_rating_rows(db_session)


async def test_put_favorite_rejects_a_missing_body_field(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)

    response = await authenticated_api_client.put(f"/photos/{photo.id}/favorite", json={})

    assert response.status_code == 422

    await assert_no_empty_rating_rows(db_session)


async def test_put_favorite_never_overwrites_another_users_row(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der BOLA-Fall am neuen Endpunkt: `user_id` stammt ausschliesslich aus `current_user`.
    Der andere Nutzer traegt hier ausdruecklich BEIDE Felder gesetzt - eine Aufsuchbedingung
    ohne `user_id` traefe seine Zeile und raeumte sie beim Ausschalten ganz weg."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    other_user, _ = await _make_second_user(db_session)
    db_session.add(
        Rating(
            photo_id=photo.id,
            user_id=other_user.id,
            status=RatingStatus.ALBUM_WORTHY,
            favorite=True,
        )
    )
    await db_session.commit()

    response = await authenticated_api_client.put(
        f"/photos/{photo.id}/favorite", json={"favorite": False}
    )

    assert response.status_code == 200
    other_rating = await _stored_rating(db_session, photo.id, other_user.id)
    assert other_rating is not None
    assert other_rating.status == RatingStatus.ALBUM_WORTHY
    assert other_rating.favorite is True

    await assert_no_empty_rating_rows(db_session)
