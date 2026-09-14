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

from photosort.api.ratings import album_decision_kind
from photosort.models import (
    FeedbackEvent,
    FeedbackEventKind,
    Photo,
    Project,
    Rating,
    RatingStatus,
    User,
)
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


# --- Die Antwort benennt den Nutzer der Zeile ---------------------------------------------------


async def test_the_write_answer_names_the_user_of_the_row(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`user_id` steht in der Antwort, weil die Entwurfsansicht den geschriebenen Zustand in ihre
    bereits geladene Liste einsetzt, statt sie neu zu laden (Spec 0430): Ein Eintrag von
    `PhotoOut.ratings[]` traegt `user_id`, und die Alternative waere eine im Client ERFUNDENE Id
    in einer zwischengespeicherten Antwort.

    Der Wert stammt ausschliesslich aus `current_user`, nie aus Body oder Query (Auflage S7)."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    own_user_id = await _own_user_id(db_session)

    written = await authenticated_api_client.put(
        f"/photos/{photo.id}/rating", json={"status": "album_worthy"}
    )
    assert written.json()["user_id"] == own_user_id

    favorited = await authenticated_api_client.put(
        f"/photos/{photo.id}/favorite", json={"favorite": True}
    )
    assert favorited.json()["user_id"] == own_user_id

    await assert_no_empty_rating_rows(db_session)


async def test_the_write_answer_of_the_other_user_names_the_other_user(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Die Gegenprobe: Derselbe Aufruf unter einem anderen Token nennt die ANDERE Id - ein fest
    verdrahteter Wert bestuende den Fall darueber."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    other_user, other_token = await _make_second_user(db_session)

    own_authorization = authenticated_api_client.headers["Authorization"]
    authenticated_api_client.headers["Authorization"] = f"Bearer {other_token}"
    try:
        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/rating", json={"status": "rejected"}
        )
    finally:
        authenticated_api_client.headers["Authorization"] = own_authorization

    assert response.json()["user_id"] == other_user.id
    assert response.json()["user_id"] != await _own_user_id(db_session)

    await assert_no_empty_rating_rows(db_session)


# --- Das Ereignis-Log (Spec 0432) ---------------------------------------------------------------
#
# Diese drei Endpunkte laufen durch DIESELBE Schreibstelle, und genau daraus entsteht die
# gefaehrliche Lage: Mit `record=True` als Vorgabewert zeichnete `PUT /photos/{id}/favorite` die
# Auszeichnung als Favorit als Korrektur auf. Das entscheidende Praedikat ist der WECHSEL DES
# STATUS, nicht der Schreibvorgang an der Zeile.


async def _stored_kinds(session: AsyncSession) -> list[FeedbackEventKind]:
    """Die aufgezeichneten Arten in ihrer Reihenfolge - und die ist die aufsteigende `id`, nie
    `occurred_at`."""
    session.expire_all()
    return [
        kind
        for kind in (
            await session.execute(select(FeedbackEvent.kind).order_by(FeedbackEvent.id))
        ).scalars()
    ]


def test_the_transition_rule_maps_every_status_change_to_exactly_one_kind() -> None:
    """Die Uebergangsregel als REINE Funktion, DB-frei geprueft. Sie liegt neben
    `write_own_rating` und nicht im Endpunkt: Drei Endpunkte durchlaufen sie, und eine je
    Endpunkt wiederholte Abbildung waere drei Stellen, die auseinanderlaufen koennen."""
    assert album_decision_kind(None, RatingStatus.ALBUM_WORTHY) is FeedbackEventKind.PHOTO_INCLUDED
    assert album_decision_kind(None, RatingStatus.REJECTED) is FeedbackEventKind.PHOTO_REMOVED
    assert (
        album_decision_kind(RatingStatus.ALBUM_WORTHY, RatingStatus.REJECTED)
        is FeedbackEventKind.PHOTO_REMOVED
    )
    assert album_decision_kind(RatingStatus.REJECTED, None) is FeedbackEventKind.DECISION_WITHDRAWN


def test_the_transition_rule_yields_nothing_when_the_status_does_not_move() -> None:
    """DIE tragende Haelfte: Eine Wiederholung ist keine Korrektur, und die Story misst
    Korrekturen. Auch "nichts zurueckgenommen" (`None` -> `None`) ist keine."""
    assert album_decision_kind(None, None) is None
    assert album_decision_kind(RatingStatus.REJECTED, RatingStatus.REJECTED) is None
    assert album_decision_kind(RatingStatus.ALBUM_WORTHY, RatingStatus.ALBUM_WORTHY) is None


async def test_no_event_without_a_real_status_change(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """DREI HAELFTEN IN EINEM FALL, und die mittlere ist die gefaehrliche.

    Getrennt geschrieben bestuende jede Haelfte auch bei einer Umsetzung, die IMMER oder NIE
    aufzeichnet - erst nebeneinander schliessen sie beide aus."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    # Die Ids VOR der ersten `expire_all()`-Messung festhalten: danach loeste jeder
    # Attributzugriff am ORM-Objekt ein Nachladen aus.
    photo_id = photo.id

    # (1) Erster Schreibvorgang: ein echter Wechsel -> genau ein Ereignis.
    await authenticated_api_client.put(
        f"/photos/{photo_id}/rating", json={"status": "album_worthy"}
    )
    assert await _stored_kinds(db_session) == [FeedbackEventKind.PHOTO_INCLUDED]

    # (2) Derselbe Status erneut gesetzt -> KEIN weiteres Ereignis.
    await authenticated_api_client.put(
        f"/photos/{photo_id}/rating", json={"status": "album_worthy"}
    )
    assert await _stored_kinds(db_session) == [FeedbackEventKind.PHOTO_INCLUDED]

    # (3) Nur das Favoriten-Kennzeichen umgeschaltet -> KEIN Ereignis. Der Favorit wirkt nach ADR
    # 0098 nicht auf den Entwurf und ist damit keine Aussage ueber einen Modellfehler.
    await authenticated_api_client.put(f"/photos/{photo_id}/favorite", json={"favorite": True})
    await authenticated_api_client.put(f"/photos/{photo_id}/favorite", json={"favorite": False})
    assert await _stored_kinds(db_session) == [FeedbackEventKind.PHOTO_INCLUDED]

    # (4) Ein ANDERER Status -> genau ein weiteres Ereignis.
    await authenticated_api_client.put(f"/photos/{photo_id}/rating", json={"status": "rejected"})
    assert await _stored_kinds(db_session) == [
        FeedbackEventKind.PHOTO_INCLUDED,
        FeedbackEventKind.PHOTO_REMOVED,
    ]

    await assert_no_empty_rating_rows(db_session)


async def test_a_withdrawn_decision_adds_an_event_and_leaves_the_first_one_untouched(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """L6: Das Ruecknahme-Ereignis kommt HINZU, das urspruengliche bleibt wortgleich stehen, und
    die Fallzahl verringert sich dadurch NICHT.

    Die beiden naheliegenden Fehler - das erste Ereignis loeschen, oder die Ruecknahme abziehen -
    liefern beide eine plausible Zahl, und keiner von beiden roetet einen Fall, der nur das
    Vorhandensein des Ruecknahme-Ereignisses prueft."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    # Die Ids VOR der ersten `expire_all()`-Messung festhalten: danach loeste jeder
    # Attributzugriff am ORM-Objekt ein Nachladen aus.
    photo_id = photo.id

    await authenticated_api_client.put(f"/photos/{photo_id}/rating", json={"status": "rejected"})
    db_session.expire_all()
    first = (await db_session.execute(select(FeedbackEvent))).scalar_one()
    first_snapshot = (first.id, first.kind, first.photo_id, first.user_id, first.occurred_at)

    await authenticated_api_client.delete(f"/photos/{photo_id}/rating")

    db_session.expire_all()
    rows = (
        (await db_session.execute(select(FeedbackEvent).order_by(FeedbackEvent.id))).scalars().all()
    )
    assert [row.kind for row in rows] == [
        FeedbackEventKind.PHOTO_REMOVED,
        FeedbackEventKind.DECISION_WITHDRAWN,
    ]
    assert (
        rows[0].id,
        rows[0].kind,
        rows[0].photo_id,
        rows[0].user_id,
        rows[0].occurred_at,
    ) == first_snapshot
    assert len(rows) == 2

    await assert_no_empty_rating_rows(db_session)


async def test_withdrawing_a_decision_that_never_existed_records_nothing(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Eine nicht vorhandene Entscheidung zurueckzunehmen ist keine Korrektur (L1). Der Endpunkt
    ist idempotent und antwortet weiterhin `204`."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    # Die Ids VOR der ersten `expire_all()`-Messung festhalten: danach loeste jeder
    # Attributzugriff am ORM-Objekt ein Nachladen aus.
    photo_id = photo.id

    response = await authenticated_api_client.delete(f"/photos/{photo_id}/rating")

    assert response.status_code == 204
    assert await _stored_kinds(db_session) == []

    await assert_no_empty_rating_rows(db_session)


async def test_the_withdrawal_that_deletes_the_row_still_records_its_event(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der Zweig, in dem die Bewertungszeile dabei VERSCHWINDET (kein Favorit daneben). Er kehrt
    in `write_own_rating` frueher zurueck als der gewoehnliche - eine Aufzeichnung, die erst nach
    dem `flush` steht, faellt hier lautlos aus, und ausgerechnet die Ruecknahme ist der Handgriff,
    den der Bestand danach nicht mehr zeigt."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    # Die Ids VOR der ersten `expire_all()`-Messung festhalten: danach loeste jeder
    # Attributzugriff am ORM-Objekt ein Nachladen aus.
    photo_id = photo.id
    await authenticated_api_client.put(
        f"/photos/{photo_id}/rating", json={"status": "album_worthy"}
    )

    await authenticated_api_client.delete(f"/photos/{photo_id}/rating")

    assert await _stored_rating(db_session, photo_id, await _own_user_id(db_session)) is None
    assert await _stored_kinds(db_session) == [
        FeedbackEventKind.PHOTO_INCLUDED,
        FeedbackEventKind.DECISION_WITHDRAWN,
    ]

    await assert_no_empty_rating_rows(db_session)


async def test_the_event_carries_the_project_and_the_writing_user(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`project_id` kommt aus dem bereits geladenen `Photo`, `user_id` ausschliesslich aus
    `current_user` - nie aus Body oder Query (dieselbe Auflage wie fuer die Bewertungszeile
    selbst)."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project)
    # Die Ids VOR der ersten `expire_all()`-Messung festhalten: danach loeste jeder
    # Attributzugriff am ORM-Objekt ein Nachladen aus.
    project_id, photo_id = project.id, photo.id
    own_user_id = await _own_user_id(db_session)

    await authenticated_api_client.put(f"/photos/{photo_id}/rating", json={"status": "rejected"})

    db_session.expire_all()
    stored = (await db_session.execute(select(FeedbackEvent))).scalar_one()
    assert stored.project_id == project_id
    assert stored.photo_id == photo_id
    assert stored.user_id == own_user_id

    await assert_no_empty_rating_rows(db_session)
