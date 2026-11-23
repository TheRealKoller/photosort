"""Foto-API: Auflistung, Standardreihenfolge, Kamerafilter, korrigierte Zeit, Seitenverhaeltnis auf
jedem Lesepfad.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.models import (
    DuplicateDecision,
    PhotoDuplicateDecision,
    PhotoScore,
    Rating,
    RatingStatus,
    User,
)
from tests.support.api_photos import (
    _add_ranking,
    _by_id,
    _decide,
    _default_event,
    _draft,
    _listing,
    _make_camera,
    _make_criterion_scoring_run,
    _make_photo,
    _make_photo_of_camera,
    _make_project,
    _make_second_user,
    _recorded_select_statements,
    _selection,
)


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
    me = (await db_session.execute(select(User).where(User.username == "testuser"))).scalar_one()
    db_session.add(
        Rating(photo_id=photo.id, user_id=me.id, status=RatingStatus.ALBUM_WORTHY, favorite=True)
    )
    db_session.add(Rating(photo_id=photo.id, user_id=other_user.id, status=RatingStatus.REJECTED))
    await db_session.commit()

    response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

    assert response.status_code == 200
    ratings = response.json()["items"][0]["ratings"]
    by_username = {r["username"]: (r["status"], r["favorite"]) for r in ratings}
    assert by_username == {
        "testuser": ("album_worthy", True),
        "other-user": ("rejected", False),
    }


async def test_list_photos_reports_a_rating_row_that_carries_only_the_favorite_marker(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`status` ist in `ratings[]` nullable geworden: eine reine Favoritenzeile traegt `null`
    als Albumentscheidung und trotzdem `favorite: true`."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    me = (await db_session.execute(select(User).where(User.username == "testuser"))).scalar_one()
    db_session.add(Rating(photo_id=photo.id, user_id=me.id, status=None, favorite=True))
    await db_session.commit()

    response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

    assert response.status_code == 200
    assert response.json()["items"][0]["ratings"] == [
        {"user_id": me.id, "username": "testuser", "status": None, "favorite": True}
    ]


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
    await authenticated_api_client.put(
        f"/photos/{rated.id}/rating", json={"status": "album_worthy"}
    )

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "unrated"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [unrated.id]
    assert body["total"] == 1


async def test_unrated_keeps_a_photo_that_carries_only_the_favorite_marker(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Zusicherung 17, zweite der drei Lesestellen: "unbewertet" heisst ab jetzt "KEINE
    ALBUMENTSCHEIDUNG", nicht "keine Zeile". Kodiert als Zeilenvorhandensein fiele das nur als
    Favorit markierte Foto still aus dem Filter."""
    project = await _make_project(db_session)
    only_favorite = await _make_photo(
        db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC)
    )
    decided = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
    await authenticated_api_client.put(
        f"/photos/{only_favorite.id}/favorite", json={"favorite": True}
    )
    await authenticated_api_client.put(
        f"/photos/{decided.id}/rating", json={"status": "album_worthy"}
    )

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "unrated"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [only_favorite.id]
    assert body["total"] == 1


async def test_list_photos_filters_by_own_rating_status(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    album_worthy = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    rejected = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
    await authenticated_api_client.put(
        f"/photos/{album_worthy.id}/rating", json={"status": "album_worthy"}
    )
    await authenticated_api_client.put(f"/photos/{rejected.id}/rating", json={"status": "rejected"})

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "album_worthy"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [album_worthy.id]


async def test_the_favorite_filter_reads_the_column_not_the_status(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der Filtereintrag bleibt, seine Quelle wechselt: `favorite` ist kein Status mehr. Der
    Aufbau enthaelt bewusst ein Foto, das BEIDES traegt - eine Abbildung, die weiterhin ueber
    `status` filtert, liefert es hier nicht."""
    project = await _make_project(db_session)
    only_favorite = await _make_photo(
        db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC)
    )
    both = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
    only_album = await _make_photo(db_session, project, "c.jpg", datetime(2023, 1, 3, tzinfo=UTC))
    await authenticated_api_client.put(
        f"/photos/{only_favorite.id}/favorite", json={"favorite": True}
    )
    await authenticated_api_client.put(f"/photos/{both.id}/favorite", json={"favorite": True})
    await authenticated_api_client.put(f"/photos/{both.id}/rating", json={"status": "rejected"})
    await authenticated_api_client.put(
        f"/photos/{only_album.id}/rating", json={"status": "album_worthy"}
    )

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "favorite"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [only_favorite.id, both.id]


async def test_list_photos_filter_is_scoped_to_own_rating_not_others(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Filter "unbewertet" darf nicht durch die Bewertung des ANDEREN Nutzers beeinflusst
    werden - jeder Nutzer filtert ausschliesslich nach der eigenen Bewertung
    (specs/features/0002)."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    other_user = await _make_second_user(db_session)
    db_session.add(
        Rating(
            photo_id=photo.id,
            user_id=other_user.id,
            status=RatingStatus.ALBUM_WORTHY,
            favorite=True,
        )
    )
    await db_session.commit()

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "unrated"}
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [photo.id]


async def test_the_favorite_filter_is_scoped_to_the_own_marker_not_the_others(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Auflage S6 am Filter: Das Kennzeichen des ANDEREN Nutzers ist sichtbar, aber nie das
    eigene."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    other_user = await _make_second_user(db_session)
    db_session.add(Rating(photo_id=photo.id, user_id=other_user.id, favorite=True))
    await db_session.commit()

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "favorite"}
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


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


async def test_list_photos_filters_by_suggested_includes_photo_without_own_rating(
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

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "suggested"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [photo.id]
    assert body["total"] == 1


async def test_list_photos_filters_by_suggested_excludes_photo_with_own_rating(
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
    await authenticated_api_client.put(f"/photos/{photo.id}/rating", json={"status": "rejected"})

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "suggested"}
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_list_photos_filters_by_suggested_excludes_photo_without_score(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "suggested"}
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_list_photos_filters_by_suggested_excludes_score_without_suggested_status(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    db_session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=1.0,
            exposure=0.2,
            computed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.commit()

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "suggested"}
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_list_photos_filters_by_suggested_includes_photo_with_other_users_rating(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Multi-User-Fall der Spec: das Rating eines ANDEREN Nutzers darf den suggested-Filter des
    eigenen Nutzers nicht beeinflussen - nur die eigene Bewertung entscheidet."""
    project = await _make_project(db_session)
    photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    other_user = await _make_second_user(db_session)
    db_session.add(
        Rating(photo_id=photo.id, user_id=other_user.id, status=RatingStatus.ALBUM_WORTHY)
    )
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

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "suggested"}
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [photo.id]


async def test_the_suggestion_survives_a_rating_row_that_carries_only_the_favorite_marker(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Zusicherung 17, erste der drei Lesestellen: `has_own_rating` in `to_photo_out` liest
    kuenftig die eigene ALBUMENTSCHEIDUNG, nicht das Vorhandensein der Zeile. Kodiert als
    Zeilenvorhandensein verschwaende der Ausschuss-Vorschlag, sobald jemand das Foto als
    Favorit markiert - ohne Meldung und ohne Weg zurueck.

    Geprueft wird BEIDES in einem Fall: die Anzeige (`PhotoOut.suggestion`) und der Filterzweig
    `rating_status=suggested`. Sie sind bewusst doppelt implementiert (Python-Praedikat vs.
    SQL-WHERE); eine nur halb nachgezogene Aenderung liesse den Paritaetsfall reissen."""
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
    await authenticated_api_client.put(f"/photos/{photo.id}/favorite", json={"favorite": True})

    unfiltered = await authenticated_api_client.get(f"/projects/{project.id}/photos")
    filtered = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "suggested"}
    )

    assert unfiltered.json()["items"][0]["suggestion"] is not None
    assert [item["id"] for item in filtered.json()["items"]] == [photo.id]


async def test_the_suggestion_disappears_once_an_album_decision_exists(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Die Kehrseite des Falls darueber - sonst bestuende er auch bei einer Umsetzung, die den
    Vorschlag nie unterdrueckt."""
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

    unfiltered = await authenticated_api_client.get(f"/projects/{project.id}/photos")
    filtered = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "suggested"}
    )

    assert unfiltered.json()["items"][0]["suggestion"] is None
    assert filtered.json() == {"items": [], "total": 0}


async def test_list_photos_filters_by_suggested_mixes_reasons_without_split(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Spec-Akzeptanzkriterium: der suggested-Filter deckt beide Ausschuss-Vorschlagsarten
    (Duplikat/geringe Qualitaet) gemeinsam ab, keine serverseitige Unterteilung nach reason. Der
    fruehere dritte "top_pick"-Fall (Spec 0024) ist mit Spec 0037 entfallen - siehe SuggestionOut-
    Docstring in api/photos/."""
    project = await _make_project(db_session)
    duplicate = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    low_quality = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
    db_session.add_all(
        [
            PhotoScore(
                photo_id=duplicate.id,
                sharpness=1.0,
                exposure=0.2,
                duplicate_of=low_quality.id,
                suggested_status=RatingStatus.REJECTED,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            ),
            PhotoScore(
                photo_id=low_quality.id,
                sharpness=1.0,
                exposure=0.2,
                suggested_status=RatingStatus.REJECTED,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            ),
        ]
    )
    await db_session.commit()

    response = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "suggested"}
    )

    assert response.status_code == 200
    assert {item["id"] for item in response.json()["items"]} == {duplicate.id, low_quality.id}


async def test_list_photos_suggested_filter_matches_has_suggestion_parity(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Paritaets-Test (Architektur-Abschnitt der Spec): die Menge der IDs mit
    rating_status=suggested muss exakt der Menge der IDs entsprechen, fuer die im ungefilterten
    Aufruf suggestion != null ist - sichert die bewusste Doppelimplementierung (SQL-WHERE vs.
    Python-has_suggestion) ab.

    specs/features/0374-duplikate-vergleichen.md ERWEITERT diesen Fall um die dritte Menge: die
    Ausschuss-Ueberlebenden. "Ueberlebender" und "offener Vorschlag" sind NICHT komplementaer -
    eine mit `Ausschuss` entschiedene Aufnahme ist weder das eine noch das andere. Eine Umsetzung,
    die "offener Vorschlag" als `NOT ueberlebt` schreibt, liefert plausible, falsche Listen, und
    das faellt nur nebeneinander auf."""
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    # Praefix _ statt eigenem Namen: nur zur Vollstaendigkeit der Fallmatrix angelegt (Foto ganz
    # ohne PhotoScore), keine eigene Assertion darauf noetig.
    await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
    unsuggested_score = await _make_photo(
        db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC)
    )
    suggested_no_rating = await _make_photo(
        db_session, project, "c.jpg", datetime(2023, 1, 3, tzinfo=UTC)
    )
    suggested_with_own_rating = await _make_photo(
        db_session, project, "d.jpg", datetime(2023, 1, 4, tzinfo=UTC)
    )
    # Die beiden entschiedenen Faelle: Sie sind KEIN offener Vorschlag mehr, und sie liegen auf
    # verschiedenen Seiten des Ueberlebendenbestands.
    kept_duplicate = await _make_photo(
        db_session, project, "e.jpg", datetime(2023, 1, 5, tzinfo=UTC)
    )
    discarded = await _make_photo(db_session, project, "f.jpg", datetime(2023, 1, 6, tzinfo=UTC))
    db_session.add_all(
        [
            PhotoScore(
                photo_id=unsuggested_score.id,
                sharpness=1.0,
                exposure=0.2,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            ),
            PhotoScore(
                photo_id=suggested_no_rating.id,
                sharpness=1.0,
                exposure=0.2,
                suggested_status=RatingStatus.REJECTED,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            ),
            PhotoScore(
                photo_id=suggested_with_own_rating.id,
                sharpness=1.0,
                exposure=0.2,
                suggested_status=RatingStatus.ALBUM_WORTHY,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            ),
            PhotoScore(
                photo_id=kept_duplicate.id,
                sharpness=1.0,
                exposure=0.2,
                suggested_status=RatingStatus.REJECTED,
                duplicate_of=unsuggested_score.id,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            ),
            PhotoDuplicateDecision(photo_id=kept_duplicate.id, decision=DuplicateDecision.KEEP),
            PhotoScore(
                photo_id=discarded.id,
                sharpness=1.0,
                exposure=0.2,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            ),
            PhotoDuplicateDecision(photo_id=discarded.id, decision=DuplicateDecision.DISCARD),
        ]
    )
    await db_session.commit()
    await authenticated_api_client.put(
        f"/photos/{suggested_with_own_rating.id}/rating", json={"status": "album_worthy"}
    )

    unfiltered = await authenticated_api_client.get(f"/projects/{project.id}/photos")
    filtered = await authenticated_api_client.get(
        f"/projects/{project.id}/photos", params={"rating_status": "suggested"}
    )

    assert unfiltered.status_code == 200
    assert filtered.status_code == 200
    items = unfiltered.json()["items"]
    expected_ids = {item["id"] for item in items if item["suggestion"] is not None}
    actual_ids = {item["id"] for item in filtered.json()["items"]}
    assert expected_ids == actual_ids

    # Die dritte Menge, in DEMSELBEN Fall: die Ausschuss-Ueberlebenden, abgelesen an der
    # Kandidaten-Anzeige der Remote-Klassifizierung. `not_candidate` ist genau der Rang, den die
    # Kaskade fuer eine nicht ueberlebende Aufnahme vergibt - die Einwilligung steht dafuer oben
    # auf `True`, sonst gewaenne `consent_disabled` und die Aussage waere nicht ablesbar.
    def _ist_ueberlebender(item: dict[str, Any]) -> bool:
        return any(
            eintrag["phase"] == "remote_category" and eintrag["status"] != "not_candidate"
            for eintrag in item["cloud_vision_status"]
        )

    ueberlebende = {item["id"] for item in items if _ist_ueberlebender(item)}
    assert ueberlebende == {unsuggested_score.id, kept_duplicate.id}
    # Die Aussage, die eine komplementaer gebaute Umsetzung verfehlte: die verworfene Aufnahme
    # steht in KEINER der beiden Mengen.
    assert discarded.id not in ueberlebende
    assert discarded.id not in expected_ids
    assert actual_ids == {suggested_no_rating.id}


class TestDefaultListingRanking:
    """Bewertungsdetails-Info-Popover (specs/features/0040): `RankingOut` wird auch im
    Standard-Listing-Zweig befuellt (nicht nur im Auswahlmodus), damit Grid-/
    Detailansicht ebenfalls Rang-Score/-Position zeigen koennen."""

    async def test_default_listing_includes_ranking_and_partition_size(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, first, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, second, rank_score=0.5, rank_position=2)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        items = {item["id"]: item for item in response.json()["items"]}
        assert items[first.id]["ranking"] == {
            "event_id": (await _default_event(db_session, run)).id,
            "rank_score": 0.9,
            "rank_position": 1,
            # Lauf-global und deshalb AUCH hier, ohne jede angeforderte Auswahl.
            "proposed": True,
            "partition_size": 2,
            # Ohne angeforderte Auswahl bleibt die Position `null`.
            "curation_position": None,
        }
        assert items[second.id]["ranking"]["rank_position"] == 2

    async def test_the_ranking_is_null_without_a_criterion_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`ranking` ist EIN Feld, seit ein Foto je Lauf in genau einer Zeile steht - ohne Lauf
        also `null` und nicht eine leere Liste. Der Client unterscheidet einen Zustand, nicht
        zwei."""
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["ranking"] is None

    async def test_partition_size_is_isolated_per_project_in_default_listing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Security-Review-Fund: kein dedizierter Cross-Project-Isolationstest fuer den im
        # Default-Listing-Zweig befuellten partition_size/RankingOut-Pfad - ein etwaiges fehlendes
        # project_id-Scoping in partition_sizes/latest_successful_criterion_scoring_run_id
        # wuerde hier sichtbar (Partition-Groesse 3 statt 1).
        other_project = await _make_project(db_session, name="Other Trip")
        other_run = await _make_criterion_scoring_run(db_session, other_project)
        for index in range(3):
            other_photo = await _make_photo(
                db_session,
                other_project,
                f"other-{index}.jpg",
                datetime(2023, 1, index + 1, tzinfo=UTC),
            )
            await _add_ranking(
                db_session, other_run, other_photo, rank_score=0.5, rank_position=index + 1
            )

        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        [item] = response.json()["items"]
        assert item["ranking"]["partition_size"] == 1


class TestTheCorrectedTimeInThePhotoResponse:
    async def test_a_corrected_photo_carries_all_three_fields(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        camera = await _make_camera(db_session, project, "Canon", "EOS 5D", offset_minutes=-120)
        recorded = datetime(2026, 8, 12, 14, 32)
        await _make_photo_of_camera(db_session, project, "a.jpg", recorded, camera)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        item = response.json()["items"][0]
        assert item["taken_at"] == (recorded - timedelta(minutes=120)).isoformat()
        assert item["taken_at_original"] == recorded.isoformat()
        assert item["time_offset_minutes"] == -120
        assert item["camera"] == {"id": camera.id, "label": "Canon EOS 5D"}

    async def test_an_uncorrected_photo_reports_offset_zero(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`0` heisst "nicht korrigiert" - die Oberflaeche zeigt dann weder Kennzeichnung noch
        zweite Zeile."""
        project = await _make_project(db_session)
        camera = await _make_camera(db_session, project, "Canon", "EOS 5D")
        recorded = datetime(2026, 8, 12, 14, 32)
        await _make_photo_of_camera(db_session, project, "a.jpg", recorded, camera)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        item = response.json()["items"][0]
        assert item["time_offset_minutes"] == 0
        assert item["taken_at"] == item["taken_at_original"] == recorded.isoformat()

    async def test_a_photo_without_a_determinable_camera_reports_null_and_zero(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        recorded = datetime(2026, 8, 12, 14, 32)
        await _make_photo_of_camera(db_session, project, "a.jpg", recorded, None)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        item = response.json()["items"][0]
        assert item["camera"] is None
        assert item["time_offset_minutes"] == 0
        assert item["taken_at"] == item["taken_at_original"] == recorded.isoformat()

    async def test_the_sql_ordering_follows_the_corrected_time(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Sortierung liegt in SQL ueber `Photo.taken_at` und aendert sich damit OHNE eine
        Zeile Codeaenderung, sobald ein Versatz gesetzt ist."""
        project = await _make_project(db_session)
        camera = await _make_camera(db_session, project, "Canon", "EOS 5D", offset_minutes=-180)
        # Aufgezeichnet SPAETER, wirksam FRUEHER als das kameralose Foto.
        await _make_photo_of_camera(
            db_session, project, "kamera.jpg", datetime(2026, 8, 12, 14, 0), camera
        )
        await _make_photo_of_camera(
            db_session, project, "handy.jpg", datetime(2026, 8, 12, 13, 0), None
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert [item["relative_path"] for item in response.json()["items"]] == [
            "kamera.jpg",
            "handy.jpg",
        ]


class TestTheCameraFilter:
    async def test_it_returns_only_the_photos_of_that_camera(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        canon = await _make_camera(db_session, project, "Canon", "EOS 5D")
        phone = await _make_camera(db_session, project, "Apple", "iPhone 15")
        recorded = datetime(2026, 8, 12, 14, 32)
        await _make_photo_of_camera(db_session, project, "a.jpg", recorded, canon)
        await _make_photo_of_camera(db_session, project, "b.jpg", recorded, phone)
        await _make_photo_of_camera(db_session, project, "c.jpg", recorded, None)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"camera_id": canon.id}
        )

        assert response.status_code == 200
        assert [item["relative_path"] for item in response.json()["items"]] == ["a.jpg"]
        assert response.json()["total"] == 1

    async def test_a_camera_of_another_project_yields_an_empty_list(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT: `camera_id` ist ein weiteres PRAEDIKAT neben `Photo.project_id`, nie eine
        vorgeschaltete Aufloesung - eine fremde Id trifft damit kein Foto, statt die Fotos des
        fremden Projekts zu listen."""
        project = await _make_project(db_session, "Costa Rica")
        other = await _make_project(db_session, "Norwegen")
        foreign = await _make_camera(db_session, other, "Canon", "EOS 5D")
        recorded = datetime(2026, 8, 12, 14, 32)
        await _make_photo_of_camera(db_session, other, "b.jpg", recorded, foreign)
        await _make_photo_of_camera(db_session, project, "a.jpg", recorded, None)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"camera_id": foreign.id}
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    @pytest.mark.parametrize("camera_id", [0, -1, 2_000_000_000])
    async def test_an_out_of_range_camera_id_is_rejected_by_validation(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        camera_id: int,
    ) -> None:
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"camera_id": camera_id}
        )

        assert response.status_code == 422

    async def test_the_camera_is_loaded_in_one_query_regardless_of_the_photo_count(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        camera = await _make_camera(db_session, project, "Canon", "EOS 5D")
        recorded = datetime(2026, 8, 12, 14, 32)
        for index in range(6):
            await _make_photo_of_camera(db_session, project, f"p{index}.jpg", recorded, camera)

        with _recorded_select_statements() as statements:
            response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        camera_selects = [s for s in statements if "project_cameras" in s.lower()]
        assert len(camera_selects) == 1, camera_selects


class TestTheAspectRatioOnEveryReadPath:
    """specs/features/0489-fotouebersicht-ohne-beschnitt.md, ADR 0110 Punkt 1: `aspect_ratio`
    steht auf ALLEN Lesepfaden, nicht nur auf dem der Rasteransicht. Ein je Abfragemodus
    verschiedenes `PhotoOut` waere eine zweite, driftende Abbildung desselben Fotos."""

    async def test_the_same_photo_reports_the_same_ratio_on_all_four_paths_here(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event = await _default_event(db_session, run)
        reference = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        subject = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
        subject.aspect_ratio = 0.75
        await db_session.commit()
        await _add_ranking(db_session, run, reference, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, subject, rank_score=0.5, rank_position=2, selection_position=None
        )
        await _make_second_user(db_session)
        await _decide(db_session, subject, True)

        listing = _by_id(await _listing(authenticated_api_client, project))
        draft = _by_id(await _draft(authenticated_api_client, project))
        alternatives = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event.id, "photo_id": reference.id},
        )
        selection = _by_id((await _selection(authenticated_api_client, project))["items"])

        assert alternatives.status_code == 200
        alternative_items = _by_id(alternatives.json()["items"])
        assert listing[subject.id]["aspect_ratio"] == 0.75
        assert alternative_items[subject.id]["aspect_ratio"] == 0.75
        assert selection[subject.id]["aspect_ratio"] == 0.75
        # Der Entwurfszweig fuehrt `subject` nicht (niemand hat es aufgenommen) - fuer das
        # Bezugsbild steht das Feld dort ebenso.
        assert draft[reference.id]["aspect_ratio"] is None

    async def test_a_photo_without_a_known_ratio_reports_null_and_breaks_nothing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`NULL` ist ein regulaerer Zustand (ADR 0110 Punkt 1): Jeder Lesepfad antwortet dafuer
        fehlerfrei, statt das Feld wegzulassen oder einen Fehler zu erzeugen."""
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        items = await _listing(authenticated_api_client, project)

        assert items[0]["aspect_ratio"] is None
