from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.criteria import CRITERIA_REGISTRY
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Event,
    FinalSelectionDecision,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCriterionScore,
    PhotoLandmarkDetection,
    PhotoMotifAssessment,
    PhotoMotifCorrection,
    PhotoMotifStrength,
    PhotoRanking,
    PhotoScore,
    Project,
    ProjectCamera,
    Rating,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motif_strengths import upsert_assessment
from photosort.motifs import MOTIF_REGISTRY
from photosort.security import create_access_token, hash_password
from photosort.selection import MOTIF_PRESENCE_THRESHOLD


async def _make_project(session: AsyncSession, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id="d", opencloud_path="/a")
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
        taken_at_original=taken_at,
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
    """Zusicherung 17, erste der drei Lesestellen: `has_own_rating` in `_to_photo_out` liest
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
    Docstring in api/photos.py."""
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
    Python-has_suggestion) ab."""
    project = await _make_project(db_session)
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
    expected_ids = {
        item["id"] for item in unfiltered.json()["items"] if item["suggestion"] is not None
    }
    actual_ids = {item["id"] for item in filtered.json()["items"]}
    assert expected_ids == actual_ids
    assert actual_ids == {suggested_no_rating.id}


async def _make_criterion_scoring_run(
    session: AsyncSession,
    project: Project,
    *,
    status: ScanStatus = ScanStatus.SUCCESS,
    started_at: datetime | None = None,
) -> CriterionScoringRun:
    """`started_at` bleibt normalerweise beim Server-Default (`now()`). Es ist ausdruecklich zu
    setzen, sobald ein Test ZWEI Laeufe desselben Projekts unterscheiden muss: unter SQLite hat
    `CURRENT_TIMESTAMP` Sekundenaufloesung, und zwei unmittelbar nacheinander angelegte Laeufe
    bekaemen sonst denselben Zeitstempel - "der letzte erfolgreiche Lauf" waere dann nicht
    eindeutig bestimmt."""
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id,
        scoring_run_id=scoring_run.id,
        status=status,
        **({} if started_at is None else {"started_at": started_at}),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _make_event(
    session: AsyncSession,
    run: CriterionScoringRun,
    *,
    position: int = 1,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    landmark_name: str | None = None,
    place_kind: str | None = None,
    place_lat: float | None = None,
    place_lon: float | None = None,
) -> Event:
    """Ein Event eines Laufs. Die Zeitgrenzen sind zonenlos wie `Photo.taken_at` selbst."""
    default = datetime(2023, 1, 1, 10, 0)
    event_row = Event(
        criterion_scoring_run_id=run.id,
        position=position,
        started_at=default if started_at is None else started_at,
        ended_at=default if ended_at is None else ended_at,
        landmark_name=landmark_name,
        place_kind=place_kind,
        place_lat=place_lat,
        place_lon=place_lon,
    )
    session.add(event_row)
    await session.commit()
    await session.refresh(event_row)
    return event_row


_DEFAULT_EVENT_POSITION = 1


async def _default_event(
    session: AsyncSession, run: CriterionScoringRun, *, position: int = _DEFAULT_EVENT_POSITION
) -> Event:
    """Das Event, in das jede Rangzeile ohne ausdrueckliche Angabe faellt - angelegt beim ersten
    Bedarf, danach wiederverwendet (`UniqueConstraint(run, position)` wiese eine zweite Anlage
    ab)."""
    existing = (
        await session.execute(
            select(Event).where(
                Event.criterion_scoring_run_id == run.id, Event.position == position
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    return await _make_event(session, run, position=position)


# Sentinel fuer `_add_ranking(selection_position=…)`: "der Vorschlag spiegelt die Rangfolge".
# `None` ist dort ein eigener, bedeutungstragender Wert ("gehoert nicht zum Vorschlag") und taugt
# deshalb nicht als Vorgabewert.
_MIRRORS_RANK = object()


async def _add_ranking(
    session: AsyncSession,
    run: CriterionScoringRun,
    photo: Photo,
    *,
    event: Event | None = None,
    rank_score: float | None,
    rank_position: int | None,
    selection_position: int | None | object = _MIRRORS_RANK,
) -> None:
    """Ein Foto steht je Lauf in GENAU EINER Rangzeile - die Partition ist allein das Event
    (Spec 0427, PR 3).

    Ohne `event` faellt die Zeile in das eine Vorgabe-Event des Laufs.

    `selection_position` spiegelt ohne Angabe die Rangfolge: die meisten Faelle brauchen bloss
    IRGENDEINEN Vorschlag als Vehikel. Jeder Aufbau, in dem Platz und Rang auseinanderfallen oder
    in dem ein Foto ausdruecklich NICHT zum Vorschlag gehoert, sagt es ausgeschrieben."""
    event_row = await _default_event(session, run) if event is None else event
    session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            event_id=event_row.id,
            rank_score=rank_score,
            rank_position=rank_position,
            selection_position=(
                rank_position if selection_position is _MIRRORS_RANK else selection_position
            ),
        )
    )
    await session.commit()


class TestTheDraft:
    """Der Entwurfsmodus `draft=true` (ADR 0098): der Endpunkt liefert den Entwurf DES
    ANFRAGENDEN NUTZERS - `Vorschlag(letzter erfolgreicher Lauf) ∪ Aufgenommen(u)`, ohne
    Ablehnungsfilter.

    Er ist ABGELEITET und nirgends gespeichert; die Auswahlregel selbst ist ein LAUF-ARTEFAKT und
    wird hier nicht wiederholt (tests/test_selection.py)."""

    @staticmethod
    async def _rate(
        session: AsyncSession, photo: Photo, status: RatingStatus, user: User | None = None
    ) -> None:
        """Die eigene Albumentscheidung - ohne `user` die des Nutzers der Client-Fixture."""
        owner = (
            user
            if user is not None
            else (
                await session.execute(select(User).where(User.username == "testuser"))
            ).scalar_one()
        )
        session.add(Rating(photo_id=photo.id, user_id=owner.id, status=status))
        await session.commit()

    async def test_returns_the_drafted_photos_with_ranking_details(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        third = await _make_photo(db_session, project, "c.jpg", datetime(2023, 1, 3, tzinfo=UTC))
        await _add_ranking(db_session, run, first, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, second, rank_score=0.5, rank_position=2)
        # Bewertet, im einsehbaren Vorrat - aber nicht im Vorschlag und nicht aufgenommen.
        await _add_ranking(
            db_session, run, third, rank_score=0.1, rank_position=3, selection_position=None
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert [item["id"] for item in body["items"]] == [first.id, second.id]
        ranking = body["items"][0]["ranking"]
        # partition_size ist die GROESSE DER GESAMTEN Partition (hier 3 Fotos), nicht die des
        # Entwurfs - "Rang M von N" soll immer den vollen Pool zeigen (Spec 0040).
        assert ranking == {
            "event_id": (await _default_event(db_session, run)).id,
            "rank_score": 0.9,
            "rank_position": 1,
            "proposed": True,
            "partition_size": 3,
            # Im Entwurfsmodus traegt jedes gelieferte Foto seinen Platz in der ANGEZEIGTEN
            # Auswahl seines Events - lueckenlos ab 1 ueber die gelieferte Reihenfolge.
            "curation_position": 1,
        }

    async def test_a_proposed_and_taken_photo_appears_exactly_once(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 1: Der Entwurf ist eine VEREINIGUNG, keine Verkettung. Ein Foto, das der
        Lauf vorschlaegt UND das der Nutzer aufgenommen hat, erfuellt beide Bedingungen - eine
        Implementierung, die zwei Mengen aneinanderhaengt, liefert es zweimal, und die Ansicht
        zeigte dieselbe Kachel doppelt, ohne dass irgendetwas rot wuerde."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        both = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, both, rank_score=0.9, rank_position=1)
        await self._rate(db_session, both, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        body = response.json()
        assert [item["id"] for item in body["items"]] == [both.id]
        assert body["total"] == 1

    async def test_a_taken_photo_without_a_proposal_joins_the_draft(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        proposed = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        taken = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, proposed, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, taken, rank_score=0.1, rank_position=2, selection_position=None
        )
        await self._rate(db_session, taken, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        items = {item["id"]: item for item in response.json()["items"]}
        assert set(items) == {proposed.id, taken.id}
        # Zwei Herkuenfte, EIN Anzeigezustand - unterscheidbar allein ueber `proposed`.
        assert items[proposed.id]["ranking"]["proposed"] is True
        assert items[taken.id]["ranking"]["proposed"] is False

    async def test_a_rejected_photo_that_was_never_proposed_stays_out(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der fehlende Ablehnungsfilter darf nicht zum fehlenden Filter werden: ein gestrichenes
        Foto, das weder im Vorschlag steht noch je aufgenommen wurde, gehoert nicht in den
        Entwurf."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        proposed = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        rejected = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, proposed, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, rejected, rank_score=0.1, rank_position=2, selection_position=None
        )
        await self._rate(db_session, rejected, RatingStatus.REJECTED)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        assert [item["id"] for item in response.json()["items"]] == [proposed.id]

    async def test_only_untouched_places_follow_the_new_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 3: „Nur unangefasste Plaetze werden neu befuellt" ist erst ueber ZWEI Laeufe
        sichtbar, und die drei Fotos gehoeren in EINEN Fall - getrennt geschrieben bestuenden die
        Haelften auch bei einer Implementierung, die immer oder nie den neuen Lauf gewinnen
        laesst.

        Lauf 1 schlaegt `dropped` vor, sonst nichts. Der Nutzer streicht `dropped` und nimmt
        `taken` auf. Lauf 2 schlaegt danach `untouched` NEU vor und `dropped` ERNEUT - und genau
        das ist der Pruefstein: Der unangefasste Platz folgt dem neuen Lauf, die beiden
        angefassten behalten ihre Entscheidung, statt sich vom neuen Vorschlag zurueckstellen zu
        lassen."""
        project = await _make_project(db_session)
        first_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 5, 1, 10, 0)
        )
        untouched = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC)
        )
        dropped = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        taken = await _make_photo(db_session, project, "c.jpg", datetime(2023, 1, 3, tzinfo=UTC))
        await _add_ranking(db_session, first_run, dropped, rank_score=0.9, rank_position=1)
        for photo, position in ((untouched, 2), (taken, 3)):
            await _add_ranking(
                db_session,
                first_run,
                photo,
                rank_score=1.0 - position / 10,
                rank_position=position,
                selection_position=None,
            )

        await self._rate(db_session, dropped, RatingStatus.REJECTED)
        await self._rate(db_session, taken, RatingStatus.ALBUM_WORTHY)

        before = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )
        # Nach Lauf 1: das Vorgeschlagene (gestrichen, als Anzeigezustand) und das Aufgenommene.
        assert [item["id"] for item in before.json()["items"]] == [dropped.id, taken.id]

        second_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 5, 2, 10, 0)
        )
        second_event = await _make_event(db_session, second_run, position=1)
        for photo, position in ((untouched, 1), (dropped, 2)):
            await _add_ranking(
                db_session,
                second_run,
                photo,
                event=second_event,
                rank_score=1.0 - position / 10,
                rank_position=position,
                selection_position=position,
            )
        # Lauf 2 fuehrt das Aufgenommene nur noch als Kandidaten - es bleibt trotzdem im Entwurf.
        await _add_ranking(
            db_session,
            second_run,
            taken,
            event=second_event,
            rank_score=0.1,
            rank_position=3,
            selection_position=None,
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        items = {item["id"]: item for item in response.json()["items"]}
        assert set(items) == {untouched.id, dropped.id, taken.id}
        # Der unangefasste Platz folgt Lauf 2 - vorher war er nicht dabei.
        assert untouched.id not in {item["id"] for item in before.json()["items"]}
        assert items[untouched.id]["ranking"]["proposed"] is True
        assert items[untouched.id]["ratings"] == []
        # Das Gestrichene bleibt gestrichen, obwohl Lauf 2 es erneut vorschlaegt - der neue
        # Vorschlag setzt keine getroffene Entscheidung zurueck.
        assert items[dropped.id]["ranking"]["proposed"] is True
        assert [r["status"] for r in items[dropped.id]["ratings"]] == ["rejected"]
        # Das Aufgenommene bleibt, obwohl Lauf 2 es nicht mehr vortraegt.
        assert items[taken.id]["ranking"]["proposed"] is False
        assert [r["status"] for r in items[taken.id]["ratings"]] == ["album_worthy"]

    async def test_the_order_is_event_position_then_taken_at_then_photo_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 4: Der Sortierschluessel muss TOTAL sein - ein unvollstaendiges `ORDER BY`
        ist unter SQLite zufaellig stabil und unter Postgres nicht.

        Die Zeilen werden in GESCHUETTELTER Reihenfolge eingefuegt, das spaeter angelegte Event
        steht chronologisch VOR dem frueher angelegten, und zwei Fotos teilen sich dieselbe
        Aufnahmezeit (der Gleichstand, den erst die `photo_id` bricht). Geprueft wird die
        VOLLSTAENDIGE Id-Folge, nicht bloss die Mitgliedschaft."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        later_event = await _make_event(db_session, run, position=2)
        earlier_event = await _make_event(db_session, run, position=1)

        same_moment = datetime(2023, 1, 2, 9, 0, tzinfo=UTC)
        # Anlagereihenfolge: absichtlich weder die Soll- noch die Zeitreihenfolge.
        late_in_later = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 5, tzinfo=UTC)
        )
        tie_second = await _make_photo(db_session, project, "b.jpg", same_moment)
        early_in_earlier = await _make_photo(
            db_session, project, "c.jpg", datetime(2023, 1, 1, tzinfo=UTC)
        )
        tie_first = await _make_photo(db_session, project, "d.jpg", same_moment)
        early_in_later = await _make_photo(
            db_session, project, "e.jpg", datetime(2023, 1, 4, tzinfo=UTC)
        )

        for photo, event_row, position in (
            (late_in_later, later_event, 1),
            (tie_second, earlier_event, 2),
            (early_in_earlier, earlier_event, 3),
            (tie_first, earlier_event, 4),
            (early_in_later, later_event, 5),
        ):
            await _add_ranking(
                db_session,
                run,
                photo,
                event=event_row,
                rank_score=1.0 - position / 10,
                rank_position=position,
                selection_position=position,
            )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        # Der Gleichstand bricht ueber die kleinere `photo_id` - `tie_first` wurde VOR
        # `tie_second` angelegt und traegt deshalb die kleinere Id.
        assert tie_first.id > tie_second.id
        assert [item["id"] for item in response.json()["items"]] == [
            early_in_earlier.id,
            tie_second.id,
            tie_first.id,
            early_in_later.id,
            late_in_later.id,
        ]

    async def test_the_order_inside_an_event_is_chronological_not_the_selection_position(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Aufbau laesst Vorschlagsplatz und Aufnahmezeit AUSEINANDERFALLEN: das zeitlich
        fruehere Foto steht auf Platz 2 des Vorschlags. Nach `selection_position` sortiert stuende
        die Liste umgekehrt - und ein aufgenommenes Bild ohne Platz stets am Gruppenende, statt
        an seiner Stelle."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        early = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        late = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(
            db_session, run, late, rank_score=0.9, rank_position=1, selection_position=1
        )
        await _add_ranking(
            db_session, run, early, rank_score=0.2, rank_position=2, selection_position=2
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        items = response.json()["items"]
        assert [item["id"] for item in items] == [early.id, late.id]
        # `curation_position` numeriert die GELIEFERTE Reihenfolge des Events, lueckenlos ab 1 -
        # nicht die `selection_position` und nicht die `rank_position`.
        assert [item["ranking"]["curation_position"] for item in items] == [1, 2]
        assert [item["ranking"]["rank_position"] for item in items] == [2, 1]

    async def test_a_taken_photo_without_a_ranking_row_is_placed_by_its_time(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein im Ausschuss-Schritt aussortiertes Foto hat NIE eine Rangzeile bekommen. Nimmt der
        Nutzer es im Raster auf, erscheint es trotzdem im Entwurf - eingeordnet ueber
        `events.py::event_for_time`."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 8, 0),
            ended_at=datetime(2023, 1, 1, 9, 0),
        )
        second_event = await _make_event(
            db_session,
            run,
            position=2,
            started_at=datetime(2023, 1, 1, 14, 0),
            ended_at=datetime(2023, 1, 1, 15, 0),
        )
        anchor = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 8, 30, tzinfo=UTC)
        )
        await _add_ranking(
            db_session, run, anchor, event=first_event, rank_score=0.9, rank_position=1
        )
        # Nie bewertet, nie eingeordnet - aber vom Nutzer aufgenommen.
        discarded = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 14, 30, tzinfo=UTC)
        )
        await self._rate(db_session, discarded, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        items = {item["id"]: item for item in response.json()["items"]}
        assert set(items) == {anchor.id, discarded.id}
        assert items[discarded.id]["event"]["id"] == second_event.id
        # Ohne Rangzeile gibt es keine Rangaussage - und ausdruecklich keinen erfundenen Platz.
        assert items[discarded.id]["ranking"] is None

    async def test_the_time_assignment_reads_the_corrected_taken_at(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 13: Ein gesetzter Kameraversatz ist der einzige Fall, der `taken_at` von
        `taken_at_original` trennt. Die Zuordnung liest die KORRIGIERTE Zeit - die aufgezeichnete
        zeigte hier auf das erste Event."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 8, 0),
            ended_at=datetime(2023, 1, 1, 9, 0),
        )
        second_event = await _make_event(
            db_session,
            run,
            position=2,
            started_at=datetime(2023, 1, 1, 14, 0),
            ended_at=datetime(2023, 1, 1, 15, 0),
        )
        anchor = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 8, 30, tzinfo=UTC)
        )
        await _add_ranking(
            db_session, run, anchor, event=first_event, rank_score=0.9, rank_position=1
        )
        shifted = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 8, 40, tzinfo=UTC)
        )
        # Zonenlos wie die Spalte selbst - `taken_at_original` bleibt bei 8:40 stehen.
        shifted.taken_at = datetime(2023, 1, 1, 14, 40)
        await db_session.commit()
        await self._rate(db_session, shifted, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[shifted.id]["event"]["id"] == second_event.id

    async def test_the_ranking_row_beats_the_time_assignment(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 14: Ordnet der neue Lauf ein aufgenommenes Foto einem ANDEREN Event zu,
        steht es dort - nicht dort, wohin seine Zeit zeigte."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 8, 0),
            ended_at=datetime(2023, 1, 1, 9, 0),
        )
        second_event = await _make_event(
            db_session,
            run,
            position=2,
            started_at=datetime(2023, 1, 1, 14, 0),
            ended_at=datetime(2023, 1, 1, 15, 0),
        )
        # Die Zeit zeigt mitten in das ZWEITE Event, die Rangzeile sagt das ERSTE.
        moved = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 14, 30, tzinfo=UTC)
        )
        await _add_ranking(
            db_session,
            run,
            moved,
            event=first_event,
            rank_score=0.9,
            rank_position=1,
            selection_position=None,
        )
        await self._rate(db_session, moved, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        [item] = response.json()["items"]
        assert item["event"]["id"] == first_event.id
        assert item["event"]["id"] != second_event.id

    async def test_the_time_assignment_costs_no_query_per_photo(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S14: Die Zuordnung der rangzeilenlosen Fotos laeuft in EINEM Durchgang ueber die
        einmal geladene Eventliste. Ein N+1-Muster erzeugte hier eine Abfrage je aufgenommenem
        Foto - der Unterschied zwischen einer Handvoll Abfragen und mehreren tausend, ausgeloest
        durch normale Benutzung, ohne dass ein Parameter das begrenzte."""
        small = await _make_project(db_session, name="klein")
        large = await _make_project(db_session, name="gross")
        base = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        for project, count in ((small, 2), (large, 20)):
            run = await _make_criterion_scoring_run(db_session, project)
            anchor = await _make_photo(db_session, project, f"{project.name}-anchor.jpg", base)
            await _add_ranking(db_session, run, anchor, rank_score=0.9, rank_position=1)
            for index in range(count):
                photo = await _make_photo(
                    db_session,
                    project,
                    f"{project.name}-{index}.jpg",
                    base + timedelta(minutes=index + 1),
                )
                await self._rate(db_session, photo, RatingStatus.ALBUM_WORTHY)

        with _recorded_select_statements() as small_statements:
            small_response = await authenticated_api_client.get(
                f"/projects/{small.id}/photos", params={"draft": "true"}
            )
        with _recorded_select_statements() as large_statements:
            large_response = await authenticated_api_client.get(
                f"/projects/{large.id}/photos", params={"draft": "true"}
            )

        assert len(small_response.json()["items"]) == 3
        assert len(large_response.json()["items"]) == 21
        assert len(small_statements) == len(large_statements)

    async def test_every_event_of_the_draft_is_represented(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Entwurf spannt ueber die Events: zwei Events mit je einem Platz liefern zwei
        Fotos, nicht eines."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(db_session, run, position=1)
        second_event = await _make_event(db_session, run, position=2)
        first_photo = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC)
        )
        second_photo = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC)
        )
        await _add_ranking(
            db_session, run, first_photo, event=first_event, rank_score=0.9, rank_position=1
        )
        await _add_ranking(
            db_session, run, second_photo, event=second_event, rank_score=0.1, rank_position=1
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        assert {item["id"] for item in response.json()["items"]} == {
            first_photo.id,
            second_photo.id,
        }

    async def test_a_small_draft_returns_fewer_without_error(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        only = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, only, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == only.id

    async def test_a_run_without_a_draft_answers_empty(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Bestandslauf: seine Rangzeilen tragen ueberall `NULL`, es gibt keine Migration, die
        den Vorschlag rueckwirkend berechnet. Ohne eigene Aufnahme bleibt der Entwurf leer."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(
            db_session, run, photo, rank_score=0.9, rank_position=1, selection_position=None
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        assert response.json() == {"items": [], "total": 0}

    async def test_limit_and_offset_stay_without_effect_in_the_draft_mode(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 19 (Sicherheitsauflage S4/S14): `limit`/`offset` duerfen in diesem Zweig
        nicht HALB wirken. Ein abgeschnittener Entwurf, den die Ansicht als vollstaendig ausweist,
        ist ein Zustand, den keine Anzeige als fehlerhaft erkennt - und der Kopfbereich naennte
        dann eine Ist-Anzahl, die es nicht gibt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        for index in range(4):
            photo = await _make_photo(
                db_session, project, f"{index}.jpg", datetime(2023, 1, 1 + index, tzinfo=UTC)
            )
            await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=index + 1)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos",
            params={"draft": "true", "limit": 1, "offset": 2},
        )

        assert response.json()["total"] == 4
        assert len(response.json()["items"]) == 4

    async def test_without_the_draft_mode_the_default_listing_answers(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`draft=false` ist der Vorgabewert und kein zweiter Modus: die Antwort ist das
        gewoehnliche Listing, und `curation_position` traegt dort `null`."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "false"}
        )

        assert response.json()["items"][0]["ranking"]["curation_position"] is None

    @pytest.mark.parametrize("value", ["true", "false"])
    async def test_the_old_selection_parameter_fails_loudly_in_both_settings(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, value: str
    ) -> None:
        """Zusicherung 20: Der abgeschaffte Parameter scheitert LAUT, in BEIDEN Belegungen. Der
        zweite ist der gefaehrlichere - `selection=false` ist heute ein gueltiger Aufruf und fiele
        sonst still in den Listing-Zweig, ohne dass irgendwo ein Fehler sichtbar wuerde."""
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"selection": value}
        )

        assert response.status_code == 422

    async def test_rejecting_a_photo_does_not_change_the_draft(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nach dem Streichen des Top-Fotos rueckt NICHTS nach - das gestrichene Foto bleibt an
        seiner Position und traegt seinen Zustand.

        Geprueft als vollstaendiger Listenvergleich (Ids in Reihenfolge), nicht als blosses
        "das Foto ist noch da": ein Vorhandensein-Test bliebe auch dann gruen, wenn hinter dem
        Foto die Liste umsortiert wuerde."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, first, rank_score=0.9, rank_position=1)
        # Im Vorrat, aber nicht im Vorschlag - das ist das Foto, das frueher nachgerueckt waere.
        await _add_ranking(
            db_session, run, second, rank_score=0.5, rank_position=2, selection_position=None
        )

        before = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )
        assert [item["id"] for item in before.json()["items"]] == [first.id]

        await authenticated_api_client.put(
            f"/photos/{first.id}/rating", json={"status": "rejected"}
        )

        after = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )
        assert [item["id"] for item in after.json()["items"]] == [first.id]
        [item] = after.json()["items"]
        ranking = item["ranking"]
        assert (ranking["rank_position"], ranking["curation_position"]) == (1, 1)

    async def test_a_rejected_photo_stays_in_the_draft_with_its_rating(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Das gestrichene Foto verschwindet nicht, sondern traegt seinen Zustand dort, wo er im
        Produkt immer steht - in `ratings[]`. Die Entwurfsansicht leitet die Kachel-Darstellung
        ausschliesslich daraus ab (`utils/ownRating.ts::ownRatingStatus`), es gibt kein eigenes
        Antwortfeld dafuer."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        await authenticated_api_client.put(
            f"/photos/{photo.id}/rating", json={"status": "rejected"}
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        [item] = response.json()["items"]
        assert item["id"] == photo.id
        assert [r["status"] for r in item["ratings"]] == ["rejected"]

    async def test_the_response_depends_on_the_asking_user(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die UMGEKEHRTE Zusage des frueheren `test_response_is_independent_of_the_asking_user`
        (ADR 0071 Entscheidung 1, mit ADR 0098 abgeloest): Seit der Entwurf je Nutzer entsteht,
        haengt die ANTWORTMENGE am anfragenden Nutzer - derselbe Aufbau, umgekehrte Erwartung.

        Beide Richtungen in EINEM Fall: Das von B aufgenommene Foto erscheint nicht im Entwurf von
        A, und das von B gestrichene bleibt in A's Entwurf. Ein Ein-Nutzer-Test sieht keine von
        beiden."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        proposed = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        other_choice = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC)
        )
        await _add_ranking(db_session, run, proposed, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, other_choice, rank_score=0.5, rank_position=2, selection_position=None
        )

        other_user = await _make_second_user(db_session)
        # B nimmt ein Foto auf, das der Lauf nicht vorschlaegt, und streicht das vorgeschlagene.
        await self._rate(db_session, other_choice, RatingStatus.ALBUM_WORTHY, other_user)
        await self._rate(db_session, proposed, RatingStatus.REJECTED, other_user)

        async def draft(client: httpx.AsyncClient) -> list[int]:
            response = await client.get(f"/projects/{project.id}/photos", params={"draft": "true"})
            assert response.status_code == 200
            return [item["id"] for item in response.json()["items"]]

        own_view = await draft(authenticated_api_client)

        # DIESELBE Anfrage, anderer Nutzer. Nur der Bearer-Token wechselt (und wird danach
        # zurueckgesetzt), damit derselbe ASGI-Transport und dieselbe Sitzung benutzt werden.
        own_authorization = authenticated_api_client.headers["Authorization"]
        authenticated_api_client.headers["Authorization"] = (
            f"Bearer {create_access_token(other_user)}"
        )
        try:
            other_view = await draft(authenticated_api_client)
        finally:
            authenticated_api_client.headers["Authorization"] = own_authorization

        assert own_view != other_view
        assert own_view == [proposed.id]
        assert other_view == [proposed.id, other_choice.id]

    async def test_empty_before_any_successful_criterion_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ohne erfolgreichen Lauf ist der Entwurf leer - AUCH dann, wenn der Nutzer bereits
        Fotos aufgenommen hat. Der Entwurf ist Vorschlag ∪ Aufnahmen, und ohne Lauf gibt es weder
        Vorschlag noch Events, in die etwas einzuordnen waere."""
        project = await _make_project(db_session)
        taken = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await self._rate(db_session, taken, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    async def test_a_run_without_events_keeps_the_draft_empty(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein erfolgreicher Lauf OHNE Events: es gibt keine Spanne, in die ein aufgenommenes Foto
        einzuordnen waere. Die Ausfallrichtung ist "nicht zeigen", nie eine erfundene Gruppe."""
        project = await _make_project(db_session)
        await _make_criterion_scoring_run(db_session, project)
        taken = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await self._rate(db_session, taken, RatingStatus.ALBUM_WORTHY)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        assert response.json() == {"items": [], "total": 0}

    @pytest.mark.parametrize("value", [2, 11])
    async def test_the_old_top_n_parameter_does_not_exist_any_more(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, value: int
    ) -> None:
        """Der Nachfolger von `test_rejects_top_n_per_event_outside_valid_range`, und bewusst
        keine blosse Umbenennung: geprueft wird, dass der Parameter GAR NICHT MEHR existiert -
        auch ein frueher gueltiger Wert endet in `422`. Ein Uebergangsweg mit beiden Parametern
        waere eine zweite Auswahlregel."""
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_event": value}
        )

        assert response.status_code == 422

    async def test_includes_criterion_scores_alongside_ranking(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Test-Review-Fund: criterion_scores und ranking wurden bisher nur je einzeln getestet,
        # nie im selben Entwurfszweig kombiniert - _to_photo_out setzt aber beide in
        # derselben Funktion.
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="sharpness",
                value=0.5,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        item = response.json()["items"][0]
        assert item["ranking"] is not None
        assert [c["criterion_key"] for c in item["criterion_scores"]] == ["sharpness"]


class TestTheProposedFlag:
    """`RankingOut.proposed` ist `selection_position IS NOT NULL` des letzten erfolgreichen Laufs:
    LAUF-GLOBAL (kein Nutzerbezug) und auf ALLEN Lesepfaden befuellt, nicht nur im Entwurfsmodus.

    Es ist die einzige Auskunft darueber, ob der Lauf ein Foto vortraegt - ohne sie muesste die
    Oberflaeche sie aus `curation_position` nachbauen, und die gibt es nur im Entwurfszweig."""

    async def test_the_listing_carries_proposed_for_both_states(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        proposed = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        candidate = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC)
        )
        await _add_ranking(db_session, run, proposed, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, candidate, rank_score=0.5, rank_position=2, selection_position=None
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[proposed.id]["ranking"]["proposed"] is True
        assert items[candidate.id]["ranking"]["proposed"] is False

    async def test_the_alternatives_endpoint_carries_the_same_field(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Feldgleichheit ueber die Lesepfade: derselbe Wert desselben Fotos, einmal ueber das
        Listing und einmal ueber den Alternativen-Endpunkt. Ein je Zweig getrennt gesetztes Feld
        liefe genau hier auseinander."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, first, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, second, rank_score=0.5, rank_position=2, selection_position=None
        )

        listing = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        alternatives = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={
                "event_id": (await _default_event(db_session, run)).id,
                "photo_id": first.id,
            },
        )

        from_listing = {item["id"]: item["ranking"]["proposed"] for item in listing.json()["items"]}
        [alternative_item] = alternatives.json()["items"]
        assert alternative_item["id"] == second.id
        assert alternative_item["ranking"]["proposed"] == from_listing[second.id] is False

    async def test_proposed_is_run_global_and_not_user_dependent(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die MENGE der Antwort haengt im Entwurfszweig am anfragenden Nutzer, dieses Feld
        ausdruecklich NICHT: es sagt, was der LAUF vortraegt. Der zweite Nutzer bewertet das Foto
        gegenlaeufig - beide Sichten tragen trotzdem denselben Wert."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other_user = await _make_second_user(db_session)
        db_session.add(
            Rating(photo_id=photo.id, user_id=other_user.id, status=RatingStatus.REJECTED)
        )
        await db_session.commit()

        own = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        own_authorization = authenticated_api_client.headers["Authorization"]
        authenticated_api_client.headers["Authorization"] = (
            f"Bearer {create_access_token(other_user)}"
        )
        try:
            other = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        finally:
            authenticated_api_client.headers["Authorization"] = own_authorization

        assert own.json()["items"][0]["ranking"]["proposed"] is True
        assert other.json()["items"][0]["ranking"]["proposed"] is True


class TestDraftAlternatives:
    """Die Alternativen zu EINEM Bild des Entwurfs (ADR 0098 Punkt 5):
    `GET /projects/{id}/draft-alternatives?event_id=…&photo_id=…` liefert die Fotos dieses Events
    im letzten erfolgreichen Lauf ABZUEGLICH des Entwurfs des anfragenden Nutzers - gestrichene
    sind also enthalten, denn genau daraus folgt die Umkehrbarkeit des Austauschs.

    Der Endpunkt ersetzt `GET /projects/{id}/curation-candidates` uebernehmend; dieser Block ist
    dessen umgeschriebener Testblock und behaelt jede seiner Sicherheitszusagen."""

    @staticmethod
    async def _rate(
        session: AsyncSession, photo: Photo, status: RatingStatus, user: User | None = None
    ) -> None:
        """Die eigene Albumentscheidung - ohne `user` die des Nutzers der Client-Fixture."""
        owner = (
            user
            if user is not None
            else (
                await session.execute(select(User).where(User.username == "testuser"))
            ).scalar_one()
        )
        session.add(Rating(photo_id=photo.id, user_id=owner.id, status=status))
        await session.commit()

    @staticmethod
    async def _candidates(
        session: AsyncSession,
        project: Project,
        run: CriterionScoringRun,
        size: int,
        *,
        event: Event | None = None,
        proposed: int = 0,
    ) -> list[Photo]:
        """`size` Fotos mit Rangzeile in EINEM Event, absteigender Qualitaet.

        Die ersten `proposed` gehoeren zum Vorschlag des Laufs (und damit zum Entwurf jedes
        Nutzers, der sie nicht gestrichen hat); die uebrigen sind Alternativen."""
        event_row = await _default_event(session, run) if event is None else event
        photos = []
        for index in range(size):
            photo = await _make_photo(
                session,
                project,
                f"p{index}-{project.id}.jpg",
                datetime(2023, 1, 1, 10, index, tzinfo=UTC),
            )
            await _add_ranking(
                session,
                run,
                photo,
                event=event_row,
                rank_score=1.0 - index / 100,
                rank_position=index + 1,
                selection_position=index + 1 if index < proposed else None,
            )
            photos.append(photo)
        return photos

    async def _get(
        self,
        client: httpx.AsyncClient,
        project: Project,
        **params: object,
    ) -> httpx.Response:
        return await client.get(f"/projects/{project.id}/draft-alternatives", params=params)

    async def test_returns_the_photos_of_the_event_that_are_not_in_the_own_draft(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Regelfall und die Gegenprobe zu jedem Leerfall dieser Klasse: dasselbe Event, das
        unten nichts liefert, liefert hier Eintraege."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 5, proposed=2)

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=photos[0].id,
        )

        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body["items"]] == [p.id for p in photos[2:]]
        assert body["total"] == 3

    async def test_a_rejected_photo_is_in_the_draft_and_among_the_alternatives(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 2 - EIN Fall fuer beide Endpunkte, nicht zwei.

        Ein gestrichenes Foto des Vorschlags bleibt im Entwurfszweig stehen (mit `rejected` in
        `ratings[]`, Streichen ist ein Anzeigezustand) UND steht zugleich unter den Alternativen
        seines Events - erst daraus folgt, dass ein Austausch umkehrbar ist. Zwei getrennte Faelle
        waeren beide gruen, wenn ein gemeinsamer Helfer eine der beiden Seiten falsch bedient."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 3, proposed=2)
        rejected, kept = photos[0], photos[1]
        await self._rate(db_session, rejected, RatingStatus.REJECTED)

        draft = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )
        alternatives = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=kept.id,
        )

        draft_items = draft.json()["items"]
        assert [item["id"] for item in draft_items] == [rejected.id, kept.id]
        assert [
            r["status"]
            for item in draft_items
            if item["id"] == rejected.id
            for r in item["ratings"]
        ] == ["rejected"]
        assert [item["id"] for item in alternatives.json()["items"]] == [rejected.id, photos[2].id]

    async def test_an_own_taken_photo_is_no_alternative_but_one_taken_by_the_other_user_is(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Abgezogen wird der Entwurf DES ANFRAGENDEN Nutzers. Die Aufnahme des anderen Nutzers
        gehoert nicht dazu - sonst verschwaende sie aus der eigenen Auswahl, ohne dass eine
        Anzeige das benennt (Auflage S6)."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 4, proposed=1)
        other_user = await _make_second_user(db_session)
        await self._rate(db_session, photos[1], RatingStatus.ALBUM_WORTHY)
        await self._rate(db_session, photos[2], RatingStatus.ALBUM_WORTHY, other_user)

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=photos[0].id,
        )

        assert [item["id"] for item in response.json()["items"]] == [photos[2].id, photos[3].id]

    async def test_a_photo_without_a_ranking_row_is_no_alternative(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein im Ausschuss-Schritt aussortiertes Foto hat keine Rangzeile und erscheint deshalb
        nicht unter den Alternativen - auch dann nicht, wenn seine Zeit mitten im Event liegt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 2, proposed=1)
        await _make_photo(
            db_session, project, "ausschuss.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        )

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=photos[0].id,
        )

        assert [item["id"] for item in response.json()["items"]] == [photos[1].id]

    async def test_the_order_is_the_one_of_order_alternatives(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Sortierung des Endpunkts ist die der reinen Funktion, gegen einen Aufbau geprueft,
        dessen Sollreihenfolge sich SOWOHL von der `photo_id`- als auch von der
        `rank_position`-Folge unterscheidet - sonst bestuende der Fall auch ohne jede Sortierung.

        Bezugsbild traegt `menschen`. Erwartet: erst die Traeger desselben Motivs nach Qualitaet
        absteigend (`None` zuletzt), dann der Fremde - obwohl der Fremde die hoechste Qualitaet
        des Aufbaus hat."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _default_event(db_session, run)
        reference = await _make_photo(
            db_session, project, "ref.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        )
        await _add_ranking(
            db_session, run, reference, event=event_row, rank_score=1.0, rank_position=1
        )
        await _assess_photo(db_session, reference, strengths={"menschen": 1.0})

        # Anlagereihenfolge = Id-Reihenfolge; `rank_position` folgt der Qualitaet. Die
        # Sollreihenfolge ist eine dritte.
        weak_shared = await _make_photo(
            db_session, project, "weak.jpg", datetime(2023, 1, 1, 10, 1, tzinfo=UTC)
        )
        stranger = await _make_photo(
            db_session, project, "stranger.jpg", datetime(2023, 1, 1, 10, 2, tzinfo=UTC)
        )
        strong_shared = await _make_photo(
            db_session, project, "strong.jpg", datetime(2023, 1, 1, 10, 3, tzinfo=UTC)
        )
        unrated_shared = await _make_photo(
            db_session, project, "unrated.jpg", datetime(2023, 1, 1, 10, 4, tzinfo=UTC)
        )
        for photo, score, position, motif in (
            (stranger, 0.9, 2, "landschaft"),
            (strong_shared, 0.5, 3, "menschen"),
            (weak_shared, 0.2, 4, "menschen"),
            (unrated_shared, None, None, "menschen"),
        ):
            await _add_ranking(
                db_session,
                run,
                photo,
                event=event_row,
                rank_score=score,
                rank_position=position,
                selection_position=None,
            )
            await _assess_photo(db_session, photo, strengths={motif: 1.0})

        response = await self._get(
            authenticated_api_client, project, event_id=event_row.id, photo_id=reference.id
        )

        order = [item["id"] for item in response.json()["items"]]
        assert order == [strong_shared.id, weak_shared.id, unrated_shared.id, stranger.id]
        assert order != sorted(order)
        assert order != [stranger.id, strong_shared.id, weak_shared.id, unrated_shared.id]

    async def test_temporal_proximity_is_not_a_sorting_criterion(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 8 am Endpunkt: ein zeitlich unmittelbar benachbarter Kandidat geringerer
        Qualitaet bleibt HINTER dem Stunden entfernten hoeherer Qualitaet. Die reine Funktion
        kennt gar keine Zeit (`test_selection.py`); dieser Fall haelt fest, dass der Endpunkt sie
        auch nicht heimlich nachtraegt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _default_event(db_session, run)
        reference = await _make_photo(
            db_session, project, "ref.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        )
        near = await _make_photo(
            db_session, project, "near.jpg", datetime(2023, 1, 1, 10, 1, tzinfo=UTC)
        )
        far = await _make_photo(
            db_session, project, "far.jpg", datetime(2023, 1, 1, 15, 0, tzinfo=UTC)
        )
        await _add_ranking(
            db_session, run, reference, event=event_row, rank_score=1.0, rank_position=1
        )
        for photo, score, position in ((far, 0.9, 2), (near, 0.1, 3)):
            await _add_ranking(
                db_session,
                run,
                photo,
                event=event_row,
                rank_score=score,
                rank_position=position,
                selection_position=None,
            )

        response = await self._get(
            authenticated_api_client, project, event_id=event_row.id, photo_id=reference.id
        )

        assert [item["id"] for item in response.json()["items"]] == [far.id, near.id]

    async def test_a_candidate_without_a_quality_score_is_delivered_and_selectable(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein Kandidat ohne Modellbewertung ist ein gueltiger, waehlbarer Zustand: er steht in
        der Antwort und traegt `rank_score: null` statt herauszufallen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _default_event(db_session, run)
        photos = await self._candidates(db_session, project, run, 1, proposed=1)
        unrated = await _make_photo(
            db_session, project, "unrated.jpg", datetime(2023, 1, 1, 10, 9, tzinfo=UTC)
        )
        await _add_ranking(
            db_session,
            run,
            unrated,
            event=event_row,
            rank_score=None,
            rank_position=None,
            selection_position=None,
        )

        response = await self._get(
            authenticated_api_client, project, event_id=event_row.id, photo_id=photos[0].id
        )

        items = response.json()["items"]
        assert [item["id"] for item in items] == [unrated.id]
        assert items[0]["ranking"]["rank_score"] is None

    async def test_total_is_the_remaining_set_and_ignores_limit_and_offset(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`total` ist die RESTMENGE nach Abzug des eigenen Entwurfs und damit unabhaengig von
        `limit`/`offset` - ein aus `len(items)` gebildetes `total` waere auf der ersten Seite
        nicht davon zu unterscheiden. Die ZWEITE Seite ist der Pflichtfall."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 5, proposed=1)
        event_id = (await _default_event(db_session, run)).id

        async def page(limit: int, offset: int) -> tuple[list[int], int]:
            response = await self._get(
                authenticated_api_client,
                project,
                event_id=event_id,
                photo_id=photos[0].id,
                limit=limit,
                offset=offset,
            )
            assert response.status_code == 200
            body = response.json()
            return [item["id"] for item in body["items"]], body["total"]

        assert await page(limit=2, offset=0) == ([photos[1].id, photos[2].id], 4)
        assert await page(limit=2, offset=2) == ([photos[3].id, photos[4].id], 4)

    async def test_empty_without_a_successful_criterion_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Erster stiller Rand: 200 mit leerem `PhotoListOut`, kein Fehler."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project, status=ScanStatus.FAILED)
        photos = await self._candidates(db_session, project, run, 3, proposed=1)

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=photos[0].id,
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    async def test_an_unresolvable_photo_id_yields_an_empty_list_without_reflecting_it(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S3: `photo_id` wird AUSSCHLIESSLICH ueber eine Rangzeile desselben Laufs UND
        desselben Events aufgeloest, nie ueber `session.get(Photo, …)`. Scheitert das, ist die
        Antwort 200 mit leerer Liste und `total: 0`, auf demselben Antwortpfad wie eine leere
        Trefferliste - ein abweichender Statuscode oder ein Fehlertext waere ein Existenz-Orakel
        ueber fremde Ids, und die Sortierung haengt allein an diesem Bild."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._candidates(db_session, project, run, 3, proposed=1)
        other_event = await _make_event(db_session, run, position=2)

        unknown = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=photos[-1].id + 4200,
        )
        # Dasselbe Foto, aber ein Event, in dem es keine Rangzeile hat: die Aufloesung traegt
        # BEIDE Praedikate, nicht nur das des Laufs.
        wrong_event = await self._get(
            authenticated_api_client,
            project,
            event_id=other_event.id,
            photo_id=photos[0].id,
        )

        for response in (unknown, wrong_event):
            assert response.status_code == 200
            assert response.json() == {"items": [], "total": 0}
        assert str(photos[-1].id + 4200) not in unknown.text

    async def test_a_photo_of_the_project_without_a_ranking_row_does_not_resolve(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Gegenprobe zu `session.get(Photo, …)`: ein Foto DESSELBEN Projekts, das im Lauf
        keine Rangzeile hat, loest nicht auf - eine Aufloesung ueber die Fototabelle waere hier
        gruen und liesse ein fremdes Bild die eigene Antwort ordnen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        await self._candidates(db_session, project, run, 2, proposed=1)
        unranked = await _make_photo(
            db_session, project, "ohne-rang.jpg", datetime(2023, 1, 1, 10, 7, tzinfo=UTC)
        )

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, run)).id,
            photo_id=unranked.id,
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    async def test_unknown_project_returns_404(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.get(
            "/projects/9999/draft-alternatives", params={"event_id": 1, "photo_id": 1}
        )

        assert response.status_code == 404

    async def test_requires_authentication(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S1: `api/photos.py` verzichtet bewusst auf eine Router-weite Auth-Dependency,
        und `_protected_router_operations()` in `test_auth_guard.py` fuehrt diesen Router nicht -
        fuer ihn gibt es KEIN Vollstaendigkeitsnetz. Ein neuer Endpunkt, der
        `Depends(get_current_user)` vergisst, ist STILL OEFFENTLICH: kein Fehler, keine 401, nur
        Daten. Genau dagegen steht dieser Testfall."""
        project = await _make_project(db_session)

        response = await api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": 1, "photo_id": 1},
        )

        assert response.status_code == 401

    async def test_keys_of_another_project_return_nothing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 21, erste Haelfte, und Auflage S2: `PhotoRanking` traegt keine
        `project_id`, und `event_id` ist ein globaler Surrogatschluessel - eine Id aus Projekt B
        identifiziert unter `/projects/A/…` eindeutig FREMDE Rangzeilen. Die einzige
        Projektbindung ist `criterion_scoring_run_id` aus dem PFADPARAMETER."""
        own = await _make_project(db_session, name="Eigenes")
        foreign = await _make_project(db_session, name="Fremdes")
        own_run = await _make_criterion_scoring_run(db_session, own)
        foreign_run = await _make_criterion_scoring_run(db_session, foreign)
        await self._candidates(db_session, own, own_run, 2, proposed=1)
        foreign_photos = await self._candidates(db_session, foreign, foreign_run, 4, proposed=1)

        response = await self._get(
            authenticated_api_client,
            own,
            event_id=(await _default_event(db_session, foreign_run)).id,
            photo_id=foreign_photos[0].id,
        )

        body = response.json()
        assert {item["id"] for item in body["items"]}.isdisjoint({p.id for p in foreign_photos})
        # `total` MITGEPRUEFT: eine Zaehlabfrage ohne Lauf-Praedikat lieferte eine plausible Zahl
        # zu einer leeren Liste, und nichts wuerde rot.
        assert body == {"items": [], "total": 0}

    async def test_only_the_latest_successful_run_is_the_reference(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 21, zweite Haelfte: eine `event_id` aus einem AELTEREN Lauf desselben
        Projekts liefert 200 mit leerer Liste UND `total: 0`."""
        project = await _make_project(db_session)
        old_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 1, 1, tzinfo=UTC)
        )
        old_photos = await self._candidates(db_session, project, old_run, 3, proposed=1)
        new_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2024, 1, 1, tzinfo=UTC)
        )
        new_event = await _make_event(db_session, new_run, position=1)
        for position, photo in enumerate(old_photos[:2], start=1):
            await _add_ranking(
                db_session,
                new_run,
                photo,
                event=new_event,
                rank_score=1.0 - position / 10,
                rank_position=position,
                selection_position=1 if position == 1 else None,
            )

        response = await self._get(
            authenticated_api_client,
            project,
            event_id=(await _default_event(db_session, old_run)).id,
            photo_id=old_photos[0].id,
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    async def test_the_replaced_endpoint_is_gone(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`GET /projects/{id}/curation-candidates` entfaellt ERSATZLOS (ADR 0098 Punkt 5). Ohne
        diesen Fall waere sowohl ein vergessener Wegfall als auch ein stehengebliebener
        Uebergangsweg unsichtbar - und zwei Wege auf dieselbe Menge waeren zwei Reihenfolgen."""
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates", params={"event_id": 1}
        )

        assert response.status_code == 404


class TestCriterionScores:
    """Bewertungsdetails-Info-Popover (specs/features/0040-bewertungsdetails-info-popover.md):
    `PhotoOut.criterion_scores` exponiert die bereits vorhandenen `PhotoCriterionScore`-Zeilen."""

    async def test_includes_criterion_scores_in_registry_order(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        computed_at = datetime(2023, 1, 1, tzinfo=UTC)
        # Bewusst NICHT in Registry-Reihenfolge (sharpness, exposure, content_people,
        # content_landscape) eingefuegt - die Response muss trotzdem in Registry-Reihenfolge
        # sortieren (Akzeptanzkriterium 7 der Spec).
        db_session.add_all(
            [
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key="content_people",
                    value=1.0,
                    source=CriterionSource.LOCAL_ML,
                    computed_at=computed_at,
                ),
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key="sharpness",
                    value=0.734,
                    source=CriterionSource.LOCAL_HEURISTIC,
                    computed_at=computed_at,
                ),
            ]
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        criterion_scores = response.json()["items"][0]["criterion_scores"]
        assert criterion_scores == [
            {
                "criterion_key": "sharpness",
                "display_name": "Schärfe",
                "value": 0.734,
                "source": "local_heuristic",
                "has_presence_threshold": False,
            },
            {
                "criterion_key": "content_people",
                "display_name": "Menschen erkannt",
                "value": 1.0,
                "source": "local_ml",
                "has_presence_threshold": True,
            },
        ]

    async def test_content_landscape_is_exposed_as_a_non_category_quality_criterion(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/features/0217, ADR 0047 Punkt 1: content_landscape heisst in den
        # Bewertungsdetails "Flächigkeit" und ist nicht mehr kategorie-faehig - dadurch wandert es
        # im Frontend automatisch vom Block "Kategorien" in den Block "Qualität" (Spec 0209
        # partitioniert allein nach diesem Flag, kein Frontend-Sonderfall).
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="content_landscape",
                value=0.8,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["criterion_scores"] == [
            {
                "criterion_key": "content_landscape",
                "display_name": "Flächigkeit",
                "value": 0.8,
                "source": "local_heuristic",
                "has_presence_threshold": False,
            }
        ]

    async def test_criterion_scores_is_empty_list_when_none_exist(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["criterion_scores"] == []

    async def test_missing_criterion_is_omitted_not_filled_with_placeholder(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Best-effort-Luecke (Akzeptanzkriterium 8): nur `sharpness` wurde berechnet, `exposure`
        # fehlt - die Antwort darf `exposure` weder mit 0 noch einem Platzhalter auffuellen.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="sharpness",
                value=0.5,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        criterion_scores = response.json()["items"][0]["criterion_scores"]
        assert [c["criterion_key"] for c in criterion_scores] == ["sharpness"]

    async def test_unknown_criterion_key_falls_back_to_key_as_display_name(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Defensiv gegen Registry-/Daten-Drift (Architektur-Abschnitt der Spec): ein
        # criterion_key, der (nicht mehr) in CRITERIA_REGISTRY steht, wird trotzdem angezeigt,
        # mit dem rohen Key als display_name. `category_eligible` faellt dabei auf False zurueck
        # (Registry-Default) - im Frontend landet die Zeile damit im Qualitaets-Block
        # (specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md,
        # Akzeptanzkriterium 9).
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="future_criterion",
                value=0.3,
                source=CriterionSource.CLOUD,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        criterion_scores = response.json()["items"][0]["criterion_scores"]
        assert criterion_scores == [
            {
                "criterion_key": "future_criterion",
                "display_name": "future_criterion",
                "value": 0.3,
                "source": "cloud",
                "has_presence_threshold": False,
            }
        ]

    async def test_has_presence_threshold_matches_the_registry_for_every_criterion(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md,
        # Architektur-Entscheidung 1: das ausgelieferte Flag ist keine zweite Wahrheit, sondern
        # exakt `presence_threshold is not None`. Ein einziger Registry-weiter Test statt einer
        # Parametrisierung pro Key - WELCHE Kriterien eine Schwelle tragen, nagelt bereits
        # test_criteria.py::test_exactly_these_seven_content_criteria_carry_a_presence_threshold
        # fest.
        #
        # Die SCHWELLE selbst geht ausdruecklich nicht in die Antwort: sie ist die
        # Vorfilter-Grenze des Cloud-Aufrufs, keine Anzeigehilfe.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        computed_at = datetime(2023, 1, 1, tzinfo=UTC)
        db_session.add_all(
            [
                PhotoCriterionScore(
                    photo_id=photo.id,
                    criterion_key=key,
                    value=0.5,
                    source=CriterionSource.LOCAL_HEURISTIC,
                    computed_at=computed_at,
                )
                for key in CRITERIA_REGISTRY
            ]
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        criterion_scores = response.json()["items"][0]["criterion_scores"]
        assert {c["criterion_key"]: c["has_presence_threshold"] for c in criterion_scores} == {
            key: definition.presence_threshold is not None
            for key, definition in CRITERIA_REGISTRY.items()
        }
        assert all("presence_threshold" not in c for c in criterion_scores)


class TestCloudVisionStatus:
    """specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-
    attempt-fehler-persistierung.md: `PhotoOut.cloud_vision_status` - immer genau 2 Eintraege in
    fester Reihenfolge [landmark, remote_category], Prioritaets-Kaskade ueber 5 Raenge je Phase.
    """

    async def test_always_returns_exactly_two_entries_in_fixed_order(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        status_list = response.json()["items"][0]["cloud_vision_status"]
        assert [entry["phase"] for entry in status_list] == ["landmark", "remote_category"]

    async def test_photo_without_any_score_row_is_not_candidate_for_both_phases_with_consent(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # ADR 0035/Spec 0058, Akzeptanzkriterium: ein Foto ganz ohne PhotoScore-Zeile ->
        # not_candidate (NICHT not_run) fuer beide Phasen, sobald Consent aktiv ist.
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        status_list = response.json()["items"][0]["cloud_vision_status"]
        assert {entry["phase"]: entry["status"] for entry in status_list} == {
            "landmark": "not_candidate",
            "remote_category": "not_candidate",
        }

    async def test_default_consent_disabled_wins_over_not_candidate_for_both_phases(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Explizit bindender Ueberschneidungsfall der Spec: consent_disabled UND not_candidate
        # gleichzeitig zutreffend -> consent_disabled gewinnt.
        project = await _make_project(db_session)
        assert project.cloud_vision_detection_enabled is False
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        status_list = response.json()["items"][0]["cloud_vision_status"]
        assert {entry["phase"]: entry["status"] for entry in status_list} == {
            "landmark": "consent_disabled",
            "remote_category": "consent_disabled",
        }

    async def test_landmark_result_when_a_landmark_detection_row_exists(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        from photosort.models import PhotoLandmarkDetection

        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoLandmarkDetection(
                photo_id=photo.id,
                name="Eiffelturm",
                confidence=0.9,
                computed_at=datetime(2023, 6, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "result"
        assert entry["attempted_at"] is not None
        assert entry["error_message"] is None

    async def test_landmark_no_result_when_criterion_score_exists_without_detection_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Datenanomalie-Regressionstest (Teststrategie-Abschnitt der Spec): ein POSITIVER Wert
        # (nicht nur 0.0) ohne PhotoLandmarkDetection-Zeile muss trotzdem no_result liefern - die
        # Kaskade prueft die PRAESENZ der Score-Zeile, nicht den konkreten Wert.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="landmark",
                value=0.7,
                source=CriterionSource.CLOUD,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "no_result"
        assert entry["attempted_at"] is not None

    async def test_landmark_error_status_includes_message_and_timestamp(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        from photosort.models import CloudVisionPhase, PhotoCloudVisionError

        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.LANDMARK,
                error_type="LandmarkApiError",
                error_message="Anthropic Vision API nicht erreichbar: timeout",
                attempted_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "error"
        assert entry["error_message"] == "Anthropic Vision API nicht erreichbar: timeout"
        assert entry["attempted_at"] is not None

    async def test_landmark_error_persists_even_after_consent_is_disabled_again(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Explizit bindender Ueberschneidungsfall der Spec: error UND Consent inzwischen
        # deaktiviert -> error bleibt bestehen (Consent ist bereits Default False hier).
        from photosort.models import CloudVisionPhase, PhotoCloudVisionError

        project = await _make_project(db_session)
        assert project.cloud_vision_detection_enabled is False
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.LANDMARK,
                error_type="LandmarkApiError",
                error_message="Fehler",
                attempted_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "error"

    async def test_landmark_result_persists_even_after_consent_is_disabled_again(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/architecture/0002-testkonzept.md ("Read-Time-Prioritaets-Kaskade..." fuer ADR
        # 0035): "Erfolgssignal vorhanden UND Consent nachtraeglich deaktiviert -> weiterhin
        # result/no_result (Rang 1 vor Rang 3)" - explizit bindender Ueberschneidungsfall,
        # spiegelbildlich zu test_landmark_error_persists_even_after_consent_is_disabled_again
        # oben (dort Rang 2 vor Rang 3).
        from photosort.models import PhotoLandmarkDetection

        project = await _make_project(db_session)
        assert project.cloud_vision_detection_enabled is False
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoLandmarkDetection(
                photo_id=photo.id,
                name="Eiffelturm",
                confidence=0.9,
                computed_at=datetime(2023, 6, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "result"

    async def test_landmark_success_wins_over_an_orphaned_error_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Edge Case der Teststrategie: verwaiste Fehler-Zeile trotz vorhandenem Erfolgssignal -
        # die Kaskade muss trotzdem korrekt "result" liefern (Erfolg schlaegt Fehler, ADR 0035
        # Punkt 1).
        from photosort.models import CloudVisionPhase, PhotoCloudVisionError, PhotoLandmarkDetection

        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoLandmarkDetection(
                photo_id=photo.id,
                name="Eiffelturm",
                confidence=0.9,
                computed_at=datetime(2023, 6, 1, tzinfo=UTC),
            )
        )
        db_session.add(
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.LANDMARK,
                error_type="LandmarkApiError",
                error_message="veraltete Fehler-Zeile",
                attempted_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "result"

    async def test_landmark_not_candidate_when_no_local_criterion_reaches_the_threshold(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="content_landscape",
                value=0.0,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "not_candidate"

    async def test_landmark_not_candidate_for_an_old_run_with_only_a_content_landscape_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/features/0217, ADR 0047 Punkt 5: die Read-Time-Ableitung folgt derselben
        # umgestellten Vorfilterung wie der Lauf - eine Zeile aus einem ALTEN Lauf (nur
        # content_landscape, hoher Wert) macht ein Foto nicht mehr zum Kandidaten.
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="content_landscape",
                value=1.0,
                source=CriterionSource.LOCAL_HEURISTIC,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "not_candidate"

    async def test_landmark_not_run_when_the_landschaft_criterion_reaches_the_threshold(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        threshold = CRITERIA_REGISTRY["landschaft"].presence_threshold
        assert threshold is not None
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="landschaft",
                value=threshold,
                source=CriterionSource.LOCAL_ML,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "not_run"

    async def test_landmark_not_run_when_a_local_criterion_reaches_the_threshold(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        threshold = CRITERIA_REGISTRY["gebaeude"].presence_threshold
        assert threshold is not None
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="gebaeude",
                value=threshold,
                source=CriterionSource.LOCAL_ML,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "landmark"
        )
        assert entry["status"] == "not_run"

    async def test_remote_category_result_comes_from_the_cloud_header(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Spec 0427, PR 2 Schritt 2: das Erfolgssignal der Remote-Phase ist ab hier die
        # Kopfzeile mit `source='cloud'` - der Marker ist mit dem Schreibpfad umgezogen.
        # `attempted_at` bleibt eindeutig, ohne Aggregation ueber mehrere Zeilen.
        # Spec 0428, S6: dazu gehoert ab hier die Albumtauglichkeitszeile - dieselbe Bedingung wie
        # in Auswahl und Schaetzung.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _assess_photo(
            db_session, photo, computed_at=datetime(2023, 6, 1, 12, 0, 0), strengths={"tiere": 0.8}
        )
        await _rate_album_suitability(db_session, photo)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "result"
        assert entry["attempted_at"].startswith("2023-06-01")

    async def test_remote_category_result_also_for_a_photo_where_nothing_was_recognized(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Ein Foto, auf dem das Modell nichts deutlich erkannt hat, ist trotzdem erfolgreich
        # verarbeitet - es darf nicht weiterhin als "noch nicht gelaufen" erscheinen. Acht Nullen
        # sind eine BEURTEILUNG und nicht die Abwesenheit einer.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _assess_photo(db_session, photo)
        await _rate_album_suitability(db_session, photo)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "result"

    async def test_a_cloud_header_without_a_level_stays_an_open_candidate(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Sicherheitsauflage S6 auf dem LESEpfad: das Skip-Kriterium ist zusammengesetzt, und
        dieser Status macht es sichtbar. Meldete er hier `result`, waere ein Foto, das seine Stufe
        wiederholt unbrauchbar liefert und deshalb bei JEDEM Lauf erneut gesendet wird, in der
        Oberflaeche als erledigt ausgewiesen - waehrend dasselbe Foto in Auswahl und Schaetzung
        wieder Kandidat ist."""
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=100.0,
                exposure=0.0,
                cluster_key="c",
                suggested_status=None,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()
        await _assess_photo(db_session, photo)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "not_run"

    async def test_a_local_header_alone_is_not_a_remote_category_result(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Sicherheitsauflage S14 auf dem LESEpfad: der Kriterien-Lauf schreibt lokale
        Kopfzeilen. Sie sind kein Erfolgssignal der Cloud-Phase - ein Foto mit lokaler Grundlage
        hat noch keinen Cloud-Aufruf gesehen und ist weiterhin Kandidat."""
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=100.0,
                exposure=0.0,
                cluster_key="c",
                suggested_status=None,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()
        await _assess_photo(db_session, photo, source=MotifAssessmentSource.LOCAL, provider=None)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "not_run"

    async def test_remote_category_result_persists_even_after_consent_is_disabled_again(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/architecture/0002-testkonzept.md ("Read-Time-Prioritaets-Kaskade..." fuer ADR
        # 0035): "Erfolgssignal vorhanden UND Consent nachtraeglich deaktiviert -> weiterhin
        # result/no_result (Rang 1 vor Rang 3)" - Remote-Kategorie-Pendant zu
        # test_landmark_result_persists_even_after_consent_is_disabled_again oben.
        project = await _make_project(db_session)
        assert project.cloud_vision_detection_enabled is False
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _assess_photo(db_session, photo, strengths={"tiere": 0.8})
        await _rate_album_suitability(db_session, photo)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "result"

    async def test_remote_category_error_status_includes_message_and_timestamp(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        from photosort.models import CloudVisionPhase, PhotoCloudVisionError

        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCloudVisionError(
                photo_id=photo.id,
                phase=CloudVisionPhase.REMOTE_CATEGORY,
                error_type="RemoteCategoryClassificationApiError",
                error_message="Fehler beim Klassifizieren",
                attempted_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "error"
        assert entry["error_message"] == "Fehler beim Klassifizieren"

    async def test_remote_category_not_candidate_when_photo_was_rejected(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=1.0,
                exposure=0.0,
                suggested_status=RatingStatus.REJECTED,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "not_candidate"

    async def test_remote_category_not_run_when_photo_is_an_ausschuss_survivor(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=1.0,
                exposure=0.0,
                suggested_status=None,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "not_run"


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
        # project_id-Scoping in _partition_sizes/_latest_successful_criterion_scoring_run_id
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


async def _make_photo_at(
    session: AsyncSession,
    project: Project,
    path: str,
    taken_at: datetime,
    *,
    gps: tuple[float, float] | None = None,
) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=taken_at,
        taken_at_original=taken_at,
        last_modified=taken_at,
        gps_lat=None if gps is None else gps[0],
        gps_lon=None if gps is None else gps[1],
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _add_landmark(session: AsyncSession, photo: Photo, name: str) -> None:
    session.add(
        PhotoLandmarkDetection(
            photo_id=photo.id,
            name=name,
            confidence=0.9,
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await session.commit()


@contextmanager
def _recorded_select_statements() -> Iterator[list[str]]:
    """Die TATSAECHLICH abgesetzten SELECT-Anweisungen (Muster aus test_project_deletion.py).

    Bewusst ueber das `before_cursor_execute`-Ereignis der Engine und nicht ueber eine daneben
    gepflegte Zahl: eine Konstante und die ausgefuehrten Anweisungen driften, und geprueft gehoert,
    was der Endpunkt tut."""
    statements: list[str] = []

    def _listener(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(Engine, "before_cursor_execute", _listener)
    try:
        yield statements
    finally:
        event.remove(Engine, "before_cursor_execute", _listener)


_EIFFEL = (48.858093, 2.294694)
# Rund 40 m vom Eiffelturm entfernt - FAELLT AUF DIESELBE gerundete Stelle (2 Nachkommastellen).
_EIFFEL_40_M = (48.858450, 2.294694)
# Trocadero, rund 700 m entfernt - ein anderer ORT, aber (verifiziert) dieselbe gerundete Stelle
# wie der Eiffelturm: 500 m Trennabstand und ~1,1 km Rundungsraster sind bewusst verschieden grob.
# Fuer die Nachbarschaftstests der Herleitung ist genau das richtig; fuer "Mehrere Orte" nicht.
_TROCADERO = (48.862000, 2.288500)
# Ein Ort auf einem ANDEREN Kontinent (Sydney). Fuer den Nachweis der Ortsuebernahme unter einem
# gesetzten Versatz ist genau diese Weite richtig: erbt ein Kamerafoto den falschen Anker, ist das
# Ergebnis unuebersehbar falsch und nicht bloss um ein paar Meter verschoben - dieselbe Deutlichkeit,
# die der Zielabsatz der Spec beschreibt ("der Ort eines ganz anderen Moments").
_SYDNEY = (-33.856800, 151.215300)
# Louvre - eine tatsaechlich ANDERE gerundete Stelle (48.86, 2.34 statt 48.86, 2.29). Der
# Unterschied zu _TROCADERO ist der eigentliche Testgegenstand des "multiple"-Falls: dort wird die
# GERUNDETE Stelle verglichen, nicht der Rohwert.
_LOUVRE = (48.860611, 2.337644)


class TestPhotoLocationAndClusterPlace:
    async def test_a_photo_with_its_own_coordinate_reports_source_exif_in_full_precision(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """VOLLE EXIF-Praezision, keine serverseitige Rundung (Daniels Entscheidung) - die
        Rundung auf zwei Nachkommastellen liegt allein in `cluster_place`, weil dort dieselbe Zahl
        ueber "coordinate" vs. "multiple" entscheidet."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC), gps=_EIFFEL
        )
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        [item] = response.json()["items"]
        assert item["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "exif",
        }

    async def test_a_photo_without_a_coordinate_inherits_the_nearest_one_in_its_cluster(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        anchor = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), gps=_EIFFEL
        )
        blind = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
        )
        await _add_ranking(db_session, run, anchor, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, blind, rank_score=0.5, rank_position=2)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[anchor.id]["location"]["source"] == "exif"
        assert items[blind.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "derived",
        }

    async def test_the_derived_coordinate_comes_from_the_temporally_nearest_neighbour(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        far = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), gps=_EIFFEL
        )
        blind = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 50, tzinfo=UTC)
        )
        near = await _make_photo_at(
            db_session, project, "c.jpg", datetime(2023, 1, 1, 10, 55, tzinfo=UTC), gps=_TROCADERO
        )
        for index, photo in enumerate((far, blind, near), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[blind.id]["location"]["lat"] == _TROCADERO[0]
        assert items[blind.id]["location"]["source"] == "derived"

    # specs/features/0426-zeitversatz-je-kamera.md, Akzeptanzkriterium 5: die ORTSUEBERNAHME ist
    # die vierte Lesestelle der Aufnahmezeit und braucht ihren eigenen Nachweis an einem
    # Datensatz, dessen Ergebnis mit gesetztem Versatz ANDERS ausfaellt als mit der
    # aufgezeichneten Zeit.
    #
    # Gefuehrt wird der Nachweis am AUFRUFER, nicht an `infer_locations`: die reine Funktion
    # kennt den Versatz nicht: sie bekommt `taken_at` uebergeben. Die Entscheidung, WELCHE
    # Spalte die Inferenzbasis speist, liegt hier (`_event_and_location_by_photo_id`) und in
    # `worker.py::_build_grouping_and_rankings` - genau dort waere ein Umbau auf
    # `taken_at_original` plausibel formuliert und fachlich falsch.
    async def _inheritance_fixture(
        self, db_session: AsyncSession, *, offset_minutes: int
    ) -> tuple[Project, Photo]:
        """Zwei Anker mit VERSCHIEDENEN Koordinaten und ein Kamerafoto ohne eigene Koordinate,
        dessen zeitlich naechster Anker vom Versatz abhaengt.

        Aufgezeichnet 10:00 - naechster Anker ist der um 09:00 (eine Stunde gegen vier). Mit
        +180 Minuten liegt die wirksame Zeit auf 13:00 - naechster Anker ist der um 13:00."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        camera = await _make_camera(
            db_session, project, "Canon", "EOS 5D", offset_minutes=offset_minutes
        )
        early = await _make_photo_at(
            db_session, project, "frueh.jpg", datetime(2023, 1, 1, 9, 0), gps=_EIFFEL
        )
        late = await _make_photo_at(
            db_session, project, "spaet.jpg", datetime(2023, 1, 1, 13, 0), gps=_SYDNEY
        )
        blind = await _make_photo_of_camera(
            db_session, project, "kamera.jpg", datetime(2023, 1, 1, 10, 0), camera
        )
        for index, photo in enumerate((early, blind, late), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)
        return project, blind

    async def test_without_an_offset_the_camera_photo_inherits_the_earlier_anchor(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project, blind = await self._inheritance_fixture(db_session, offset_minutes=0)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[blind.id]["location"]["lat"] == _EIFFEL[0]
        assert items[blind.id]["location"]["source"] == "derived"

    async def test_an_offset_switches_the_inherited_place_to_the_other_anchor(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """DER Defekt, den die Story behebt (Zielabsatz): ein Kamerafoto ohne eigenen Ort erbt bei
        falsch gehender Uhr den Ort eines ganz anderen Moments. Faellt dieser Fall weg, kann ein
        Umbau die Inferenzbasis auf `taken_at_original` umstellen, ohne dass ein Test roetet."""
        project, blind = await self._inheritance_fixture(db_session, offset_minutes=180)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        # Mit der AUFGEZEICHNETEN Zeit (10:00) waere es der Eiffelturm-Anker - der Unterschied
        # zwischen beiden Faellen ist ausschliesslich der Versatz.
        assert items[blind.id]["location"]["lat"] == _SYDNEY[0]
        assert items[blind.id]["location"]["lon"] == _SYDNEY[1]
        assert items[blind.id]["location"]["source"] == "derived"

    async def test_an_exactly_equidistant_neighbour_is_resolved_towards_the_earlier_one(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Deterministischer Tie-Break: bei zwei gleich weit entfernten Nachbarn gewinnt der
        FRUEHERE Zeitpunkt. Ohne feste Regel haengt die angezeigte Koordinate an der
        Zeilenreihenfolge der Datenbank."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        earlier = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), gps=_EIFFEL
        )
        blind = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 10, tzinfo=UTC)
        )
        later = await _make_photo_at(
            db_session, project, "c.jpg", datetime(2023, 1, 1, 10, 20, tzinfo=UTC), gps=_TROCADERO
        )
        for index, photo in enumerate((earlier, blind, later), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[blind.id]["location"]["lat"] == _EIFFEL[0]

    async def test_an_identical_timestamp_is_resolved_towards_the_smaller_photo_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        same_moment = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        first = await _make_photo_at(db_session, project, "a.jpg", same_moment, gps=_EIFFEL)
        second = await _make_photo_at(db_session, project, "b.jpg", same_moment, gps=_TROCADERO)
        blind = await _make_photo_at(db_session, project, "c.jpg", same_moment)
        for index, photo in enumerate((first, second, blind), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert min(first.id, second.id) == first.id
        assert items[blind.id]["location"]["lat"] == _EIFFEL[0]

    async def test_a_photo_earlier_than_every_anchor_inherits_the_first_one(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Randfall "vor allen Ankern" - die Einfuegestelle ist 0, und es gibt keinen frueheren
        Nachbarn, gegen den abgewogen werden koennte. Ohne eigenen Fall bliebe genau der Zweig
        ungeprueft, der bei einer Umstellung der Suche als erstes bricht."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        blind = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        )
        nearest = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 5, tzinfo=UTC), gps=_EIFFEL
        )
        farther = await _make_photo_at(
            db_session, project, "c.jpg", datetime(2023, 1, 1, 11, 0, tzinfo=UTC), gps=_LOUVRE
        )
        for index, photo in enumerate((blind, nearest, farther), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[blind.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "derived",
        }

    async def test_a_photo_later_than_every_anchor_inherits_the_last_one(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der gespiegelte Randfall: die Einfuegestelle liegt hinter dem letzten Anker."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        farther = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), gps=_LOUVRE
        )
        nearest = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 55, tzinfo=UTC), gps=_EIFFEL
        )
        blind = await _make_photo_at(
            db_session, project, "c.jpg", datetime(2023, 1, 1, 11, 0, tzinfo=UTC)
        )
        for index, photo in enumerate((farther, nearest, blind), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[blind.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "derived",
        }

    async def test_duplicate_anchor_timestamps_still_resolve_to_the_smaller_photo_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zwei Anker auf DEMSELBEN Zeitpunkt plus ein spaeterer dritter - der Fall, der die
        Sortier-Voraussetzung der Suche tatsaechlich beansprucht: die Ankerliste ist nach
        `(taken_at, photo_id)` sortiert, und die Suche darf nur den ERSTEN der beiden gleichen
        Zeitstempel treffen. Der bestehende Gleichstand-Test kommt ohne einen dritten, spaeteren
        Anker aus und wuerde eine falsche Einfuegestelle deshalb nicht bemerken."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        same_moment = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        first = await _make_photo_at(db_session, project, "a.jpg", same_moment, gps=_EIFFEL)
        second = await _make_photo_at(db_session, project, "b.jpg", same_moment, gps=_TROCADERO)
        later = await _make_photo_at(
            db_session, project, "c.jpg", datetime(2023, 1, 1, 10, 30, tzinfo=UTC), gps=_LOUVRE
        )
        blind = await _make_photo_at(db_session, project, "d.jpg", same_moment)
        for index, photo in enumerate((first, second, later, blind), start=1):
            await _add_ranking(db_session, run, photo, rank_score=1.0 / index, rank_position=index)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert first.id < second.id < later.id
        assert items[blind.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "derived",
        }

    async def test_both_fields_are_null_when_nothing_carries_a_location_at_all(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """KEIN Objekt aus lauter `null`-Feldern - `null` heisst "kein Ort"."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo_at(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        [item] = response.json()["items"]
        assert item["location"] is None
        assert item["event"]["place"] is None

    async def test_location_is_null_while_the_event_place_is_set_for_a_name_only_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die `null`-Abgrenzung getrennt fuer BEIDE Felder: ein Event mit einem Namen, aber ohne
        jede Koordinate, hat einen Ort - kein Foto hat trotzdem einen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session, run, position=1, landmark_name="Eiffelturm", place_kind="landmark"
        )
        photo = await _make_photo_at(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        [item] = response.json()["items"]
        assert item["location"] is None
        assert item["event"]["place"] == {
            "kind": "landmark",
            "landmark_name": "Eiffelturm",
            "lat": None,
            "lon": None,
        }

    async def test_the_only_anchor_may_be_a_rejected_photo_without_a_ranking_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """VERSCHAERFTER ROT-ANKER: die Bezugsmenge der Ortsherleitung ist das GANZE PROJEKT, nicht
        die Kandidatenmenge. Der einzige Anker ist hier ein am Ausschuss-Gate haengengebliebenes
        Foto ohne jede Rangzeile - unter der frueheren, clusterweiten Herleitung blieb das
        koordinatenlose Foto `null`."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        gated = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC), gps=_EIFFEL
        )
        blind = await _make_photo_at(
            db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
        )
        await _add_ranking(db_session, run, blind, rank_score=0.5, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[gated.id]["location"]["source"] == "exif"
        # Das aussortierte Foto hat keine Rangzeile und damit kein Event - seinen ORT vererbt es
        # trotzdem.
        assert items[gated.id]["event"] is None
        assert items[blind.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "derived",
        }


# Die Stufenentscheidung selbst (Name -> eine gerundete Zelle -> mehrere Orte -> kein Ortsbezug),
# die Rundung und die `-0.0`-Normalisierung leben seit Spec 0425 in `events.py` und werden dort
# DB-frei geprueft (tests/test_events.py::TestEventPlace). Die Namenshaertung liegt an der
# Schreibstelle (tests/test_worker_criterion_scoring.py, unsanierter und zu langer Altname). Hier
# bleibt, was nur der Endpunkt zeigen kann.


class TestEventIsNotAnAnswerStatement:
    async def _seed_event_with_a_deep_anchor(
        self,
        db_session: AsyncSession,
        *,
        anchor_gps: tuple[float, float] | None = None,
        shallow_gps: tuple[float, float] | None = None,
        landmark_name: str | None = None,
    ) -> tuple[Project, CriterionScoringRun, Photo]:
        """Ein Event mit 11 Fotos, dessen tragendes Foto auf `rank_position` 11 liegt und NICHT
        zum Vorschlag gehoert - also ausserhalb der Auswahl-Antwort. Der Vorschlag umfasst die
        drei bestplatzierten Fotos."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session,
            run,
            position=1,
            landmark_name=landmark_name,
            place_kind=None if landmark_name is None else "landmark",
        )
        base = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        for index in range(1, 11):
            shallow = await _make_photo_at(
                db_session,
                project,
                f"shallow-{index}.jpg",
                base + timedelta(minutes=index),
                gps=shallow_gps,
            )
            await _add_ranking(
                db_session,
                run,
                shallow,
                event=event_row,
                rank_score=1.0 / index,
                rank_position=index,
                selection_position=index if index <= 3 else None,
            )
        anchor = await _make_photo_at(
            db_session, project, "anchor.jpg", base + timedelta(minutes=11), gps=anchor_gps
        )
        await _add_ranking(
            db_session,
            run,
            anchor,
            event=event_row,
            rank_score=0.01,
            rank_position=11,
            selection_position=None,
        )
        return project, run, anchor

    async def test_the_only_coordinate_reaches_photos_that_outrank_it(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ROT-ANKER: das EINZIGE koordinatentragende Foto liegt auf Rang 11 und steht nicht im
        Vorschlag. Eine Herleitung ueber die Fotos der Antwort lieferte hier `null`."""
        project, _run, _anchor = await self._seed_event_with_a_deep_anchor(
            db_session, anchor_gps=_EIFFEL
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        items = response.json()["items"]
        assert len(items) == 3
        for item in items:
            assert item["location"] == {
                "lat": _EIFFEL[0],
                "lon": _EIFFEL[1],
                "source": "derived",
            }

    async def test_the_event_does_not_change_between_limit_one_and_sixty(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project, _run, _anchor = await self._seed_event_with_a_deep_anchor(
            db_session, anchor_gps=_LOUVRE, shallow_gps=_EIFFEL, landmark_name="Eiffelturm"
        )

        narrow = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"limit": 1}
        )
        wide = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"limit": 60}
        )

        assert narrow.json()["items"][0]["event"] == wide.json()["items"][0]["event"]

    async def test_both_fields_are_field_equal_across_photos_and_draft_alternatives(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der direkte "springt nicht"-Nachweis: dasselbe Foto einmal ueber das Standard-Listing
        und einmal ueber den Alternativen-Endpunkt. Das tragende Foto liegt ausserhalb des
        Vorschlags und ist damit genau dort eine Alternative."""
        project, run, anchor = await self._seed_event_with_a_deep_anchor(
            db_session, anchor_gps=_LOUVRE, shallow_gps=_EIFFEL
        )
        event_row = await _default_event(db_session, run)

        listing = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        from_listing = {item["id"]: item for item in listing.json()["items"]}
        # Bezugsbild ist ein vorgeschlagenes Foto desselben Events - der Regelfall des Austauschs.
        reference_id = next(
            item["id"] for item in from_listing.values() if item["ranking"]["proposed"]
        )

        alternatives = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event_row.id, "photo_id": reference_id},
        )

        assert alternatives.status_code == 200
        by_id = {item["id"]: item for item in alternatives.json()["items"]}
        assert by_id[anchor.id]["location"] == from_listing[anchor.id]["location"]
        assert by_id[anchor.id]["event"] == from_listing[anchor.id]["event"]

    async def test_the_event_is_identical_on_every_photo_of_an_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nach `event_id` gruppiert geprueft, nicht stichprobenweise an einem Foto: das ist die
        Zusicherung, aus der die Frontend-Seite ihre Berechtigung zieht, den Wert aus einem
        BELIEBIGEN Foto des Events zu lesen. `location` DARF je Foto verschieden sein, `event`
        nicht."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(db_session, run, position=1, place_kind="multiple")
        second_event = await _make_event(
            db_session, run, position=2, landmark_name="Trocadero", place_kind="landmark"
        )
        base = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        for index in range(1, 4):
            photo = await _make_photo_at(
                db_session,
                project,
                f"a-{index}.jpg",
                base + timedelta(minutes=index),
                gps=_EIFFEL if index == 1 else None,
            )
            await _add_ranking(
                db_session,
                run,
                photo,
                event=first_event,
                rank_score=1.0 / index,
                rank_position=index,
            )
        for index in range(1, 3):
            photo = await _make_photo_at(
                db_session,
                project,
                f"b-{index}.jpg",
                base + timedelta(hours=5, minutes=index),
                gps=_TROCADERO,
            )
            await _add_ranking(
                db_session,
                run,
                photo,
                event=second_event,
                rank_score=1.0 / index,
                rank_position=index,
            )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        events_by_id: dict[int, list[object]] = {}
        for item in response.json()["items"]:
            events_by_id.setdefault(item["ranking"]["event_id"], []).append(item["event"])
        assert set(events_by_id) == {first_event.id, second_event.id}
        for event_id, seen in events_by_id.items():
            assert len(seen) > 1, event_id
            assert all(entry == seen[0] for entry in seen), event_id


class TestPlaceRunBinding:
    async def test_a_foreign_project_contributes_neither_location_nor_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT, Pflichtfall (M1 und M5 in EINEM Aufbau): die Ortsherleitung haengt an
        `Photo.project_id`, die Event-Abfrage am Lauf-Praedikat. Faellt eine der beiden Bindungen
        weg, erbt das Foto eine fremde Koordinate bzw. bekommt ein fremdes Event."""
        project_a = await _make_project(db_session, name="A")
        project_b = await _make_project(db_session, name="B")
        run_a = await _make_criterion_scoring_run(db_session, project_a)
        run_b = await _make_criterion_scoring_run(db_session, project_b)
        event_a = await _make_event(db_session, run_a, position=1)
        event_b = await _make_event(
            db_session, run_b, position=1, landmark_name="Eiffelturm", place_kind="landmark"
        )
        blind = await _make_photo_at(
            db_session, project_a, "a.jpg", datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        )
        await _add_ranking(db_session, run_a, blind, event=event_a, rank_score=0.9, rank_position=1)
        foreign = await _make_photo_at(
            db_session, project_b, "b.jpg", datetime(2023, 1, 1, 10, 1, tzinfo=UTC), gps=_EIFFEL
        )
        await _add_ranking(
            db_session, run_b, foreign, event=event_b, rank_score=0.9, rank_position=1
        )

        response = await authenticated_api_client.get(f"/projects/{project_a.id}/photos")

        [item] = response.json()["items"]
        assert item["location"] is None
        assert item["event"]["place"] is None
        assert item["event"]["id"] == event_a.id

    async def test_an_older_run_of_the_same_project_contributes_no_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Dieselbe Bindung greift auch INNERHALB eines Projekts: Rangzeilen eines aelteren Laufs
        beschreiben eine andere Gliederung."""
        project = await _make_project(db_session)
        old_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 1, 1, tzinfo=UTC)
        )
        new_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 6, 1, tzinfo=UTC)
        )
        old_event = await _make_event(
            db_session, old_run, position=1, landmark_name="Eiffelturm", place_kind="landmark"
        )
        new_event = await _make_event(db_session, new_run, position=1)
        photo = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 5, tzinfo=UTC)
        )
        await _add_ranking(
            db_session, old_run, photo, event=old_event, rank_score=0.5, rank_position=1
        )
        await _add_ranking(
            db_session, new_run, photo, event=new_event, rank_score=0.5, rank_position=1
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        [item] = response.json()["items"]
        assert item["event"]["id"] == new_event.id
        assert item["event"]["place"] is None

    async def test_without_a_successful_run_only_the_own_coordinate_remains(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ausfallrichtung "nichts anzeigen", nie "aus irgendeinem Lauf herleiten": ohne Bezugslauf
        gibt es kein Event. Der ORT bleibt - er haengt am Projekt, nicht am Lauf."""
        project = await _make_project(db_session)
        photo = await _make_photo_at(
            db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC), gps=_EIFFEL
        )
        await _make_photo_at(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        assert items[photo.id]["location"] == {
            "lat": _EIFFEL[0],
            "lon": _EIFFEL[1],
            "source": "exif",
        }
        assert items[photo.id]["event"] is None


class TestPlaceQueryCount:
    async def test_the_place_derivation_costs_a_fixed_number_of_queries(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Eine FESTE Zahl Abfragen pro Anfrage, nicht eine pro Foto: die Abfrageanzahl muss
        zwischen 2 und 20 Fotos GLEICH bleiben."""
        small = await _make_project(db_session, name="klein")
        large = await _make_project(db_session, name="gross")
        base = datetime(2023, 1, 1, 10, 0, tzinfo=UTC)
        for project, count in ((small, 2), (large, 20)):
            run = await _make_criterion_scoring_run(db_session, project)
            for index in range(1, count + 1):
                photo = await _make_photo_at(
                    db_session,
                    project,
                    f"{project.name}-{index}.jpg",
                    base + timedelta(minutes=index),
                    gps=_EIFFEL if index == 1 else None,
                )
                await _add_ranking(
                    db_session, run, photo, rank_score=1.0 / index, rank_position=index
                )

        with _recorded_select_statements() as small_statements:
            small_response = await authenticated_api_client.get(f"/projects/{small.id}/photos")
        with _recorded_select_statements() as large_statements:
            large_response = await authenticated_api_client.get(f"/projects/{large.id}/photos")

        assert small_response.status_code == large_response.status_code == 200
        assert len(small_response.json()["items"]) == 2
        assert len(large_response.json()["items"]) == 20
        assert len(small_statements) == len(large_statements)


# ---------------------------------------------------------------------------------------------
# specs/features/0425-events-statt-zeitcluster.md, ADR 0087 Entscheidung 6: `PhotoOut.event`
# ersetzt `cluster_place`, `RankingOut.event_id` ersetzt `cluster_key`, und der Query-Parameter
# der Kuratierung wird von einem Freitextschluessel zu einer Objekt-Id.


class TestPhotoEvent:
    """Das Event in der Antwort - auf jedem Foto desselben Events FELDGLEICH."""

    async def test_every_photo_of_one_event_carries_the_identical_event_object(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session,
            run,
            position=3,
            started_at=datetime(2023, 1, 1, 10, 30),
            ended_at=datetime(2023, 1, 1, 11, 45),
            landmark_name="Eiffelturm",
            place_kind="landmark",
        )
        for index in range(3):
            photo = await _make_photo(
                db_session, project, f"{index}.jpg", datetime(2023, 1, 1, 10, index, tzinfo=UTC)
            )
            await _add_ranking(
                db_session, run, photo, event=event_row, rank_score=0.9, rank_position=index + 1
            )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        events = [item["event"] for item in response.json()["items"]]
        assert len(events) == 3
        assert all(event == events[0] for event in events)
        assert events[0] == {
            "id": event_row.id,
            "position": 3,
            "started_at": "2023-01-01T10:30:00",
            "ended_at": "2023-01-01T11:45:00",
            "place": {"kind": "landmark", "landmark_name": "Eiffelturm", "lat": None, "lon": None},
        }

    async def test_the_event_is_identical_across_both_read_paths(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein je Query-Modus divergierendes `PhotoOut` waere die zweite, driftende Abbildung."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(db_session, run, position=1)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        listing = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        draft = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        assert listing.json()["items"][0]["event"] == draft.json()["items"][0]["event"]

    async def test_the_event_is_the_same_with_and_without_the_draft_mode(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Nachfolger von `test_the_event_does_not_depend_on_the_requested_top_n`: den
        Leseparameter, dessen Einfluss jener Fall ausschloss, gibt es nicht mehr. Nummer und
        Zeitspanne stehen weiterhin im Event, nicht in einer Aggregation ueber die sichtbaren
        Fotos - und der Aufbau sorgt dafuer, dass die beiden Antworten VERSCHIEDEN viele Fotos
        enthalten."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 8, 0),
            ended_at=datetime(2023, 1, 1, 18, 0),
        )
        for index in range(3):
            photo = await _make_photo(
                db_session, project, f"{index}.jpg", datetime(2023, 1, 1, 10, index, tzinfo=UTC)
            )
            await _add_ranking(
                db_session,
                run,
                photo,
                event=event_row,
                rank_score=0.9,
                rank_position=index + 1,
                selection_position=1 if index == 0 else None,
            )

        listing = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        draft = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        assert len(listing.json()["items"]) == 3
        assert len(draft.json()["items"]) == 1
        assert listing.json()["items"][0]["event"] == draft.json()["items"][0]["event"]

    async def test_a_photo_without_a_ranking_row_has_no_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["event"] is None

    async def test_the_ranking_carries_the_event_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(db_session, run, position=1)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        ranking = response.json()["items"][0]["ranking"]
        assert ranking["event_id"] == event_row.id
        assert "cluster_key" not in ranking

    @pytest.mark.parametrize(
        ("place_kind", "landmark_name", "lat", "lon", "expected"),
        [
            pytest.param(
                "coordinate",
                None,
                48.86,
                2.29,
                {"kind": "coordinate", "landmark_name": None, "lat": 48.86, "lon": 2.29},
                id="koordinate",
            ),
            pytest.param(
                "multiple",
                None,
                None,
                None,
                {"kind": "multiple", "landmark_name": None, "lat": None, "lon": None},
                id="mehrere-orte",
            ),
            pytest.param(None, None, None, None, None, id="kein-ortsbezug"),
        ],
    )
    async def test_the_place_mirrors_the_stored_kind(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        place_kind: str | None,
        landmark_name: str | None,
        lat: float | None,
        lon: float | None,
        expected: dict[str, Any] | None,
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(
            db_session,
            run,
            position=1,
            landmark_name=landmark_name,
            place_kind=place_kind,
            place_lat=lat,
            place_lon=lon,
        )
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["event"]["place"] == expected

    async def test_an_unknown_place_kind_does_not_break_the_answer(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT (M8): Mitgliedschaftspruefung statt blindem Cast - sonst legt ein einzelner
        Datenfehler die gesamte Listenantwort auf 500."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(db_session, run, position=1, place_kind="galaxie")
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, event=event_row, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        assert response.json()["items"][0]["event"]["place"] is None

    async def test_the_event_of_a_foreign_run_is_never_attached(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT (M1): `event_id` ist ein GLOBALER Surrogatschluessel; die Event-Abfrage
        traegt das Lauf-Praedikat ausgeschrieben."""
        foreign_project = await _make_project(db_session, name="Fremd")
        foreign_run = await _make_criterion_scoring_run(db_session, foreign_project)
        foreign_event = await _make_event(
            db_session, foreign_run, position=1, landmark_name="Geheim", place_kind="landmark"
        )

        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(
            db_session, run, photo, event=foreign_event, rank_score=0.9, rank_position=1
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        assert response.json()["items"][0]["event"] is None


class TestDraftAlternativesKeys:
    """Die beiden fremdgesteuerten Id-Parameter des Alternativen-Endpunkts, deklarativ begrenzt
    (Auflage S4) - `event_id` adressiert das Event, `photo_id` das Bezugsbild.

    Umgeschriebener Nachfolger des Blocks, der dieselbe Zusage am Vorgaenger-Endpunkt hielt: dort
    war `event_id` gerade vom Freitextschluessel zur Objekt-Id geworden. Die Mengen- und
    Bindungszusagen stehen in `TestDraftAlternatives`; hier stehen ausschliesslich die Parameter
    selbst."""

    async def _setup(
        self, db_session: AsyncSession, *, photos: int = 3
    ) -> tuple[Project, CriterionScoringRun, Event, list[Photo]]:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(db_session, run, position=1)
        created = []
        for index in range(photos):
            photo = await _make_photo(
                db_session, project, f"{index}.jpg", datetime(2023, 1, 1, 10, index, tzinfo=UTC)
            )
            await _add_ranking(
                db_session,
                run,
                photo,
                event=event_row,
                rank_score=1.0 - index / 10,
                rank_position=index + 1,
                selection_position=1 if index == 0 else None,
            )
            created.append(photo)
        return project, run, event_row, created

    async def test_the_event_and_the_reference_are_addressed_by_their_ids(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Gegenprobe zu jedem 422 dieser Klasse: mit gueltigen Werten liefert derselbe
        Aufbau Eintraege."""
        project, _run, event_row, photos = await self._setup(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event_row.id, "photo_id": photos[0].id},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    @pytest.mark.parametrize(
        "params",
        [
            pytest.param({"event_id": 0}, id="event_id-null"),
            pytest.param({"event_id": -1}, id="event_id-negativ"),
            pytest.param({"event_id": 2**63 + 1}, id="event_id-jenseits-der-obergrenze"),
            pytest.param({"event_id": "cluster-0"}, id="event_id-nicht-numerisch"),
            pytest.param({"photo_id": 0}, id="photo_id-null"),
            pytest.param({"photo_id": -1}, id="photo_id-negativ"),
            pytest.param({"photo_id": 2**63 + 1}, id="photo_id-jenseits-der-obergrenze"),
            pytest.param({"photo_id": "erstes"}, id="photo_id-nicht-numerisch"),
            pytest.param({"offset": -1}, id="negatives-offset"),
            pytest.param({"offset": 2**63}, id="offset-jenseits-der-obergrenze"),
            pytest.param({"limit": 0}, id="limit-unter-der-untergrenze"),
            pytest.param({"limit": 201}, id="limit-ueber-der-obergrenze"),
        ],
    )
    async def test_rejects_query_parameters_outside_their_bounds(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        params: dict[str, object],
    ) -> None:
        """Auflage S4: Grenzen an ALLEN vier Parametern, deklarativ und VOR jeder Verwendung.

        `ge=1` plus Typpruefung ist enger als jede `max_length`; ohne Obergrenze erzeugte ein Wert
        jenseits von 2^63 unter SQLite einen `OverflowError` und damit eine 500 statt einer leeren
        Liste. `limit <= 200` deckelt zugleich die schwere Hydratation ueber `_photos_by_id` mit
        ihren `selectinload`s. Der bei 422 von FastAPI zurueckgespiegelte Rohwert wird
        ausschliesslich als React-Textknoten gerendert, nie geloggt."""
        project, _run, event_row, photos = await self._setup(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event_row.id, "photo_id": photos[0].id, **params},
        )

        assert response.status_code == 422

    @pytest.mark.parametrize(
        "keys",
        [
            pytest.param((), id="beide-fehlen"),
            pytest.param(("event_id",), id="photo_id-fehlt"),
            pytest.param(("photo_id",), id="event_id-fehlt"),
        ],
    )
    async def test_both_keys_are_required(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        keys: tuple[str, ...],
    ) -> None:
        """Beide Schluessel sind pflichtig: ohne `event_id` ist gar kein Event adressiert, ohne
        `photo_id` gibt es keinen Bezugspunkt, an dem die Reihenfolge haengt. Ein Vorgabewert
        waere in beiden Faellen die stille Wahl irgendeines."""
        project, _run, event_row, photos = await self._setup(db_session)
        available = {"event_id": event_row.id, "photo_id": photos[0].id}

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={key: available[key] for key in keys},
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------------------------
# specs/features/0426-zeitversatz-je-kamera.md, Umsetzungsschritt 7: die drei neuen
# PhotoOut-Felder und der camera_id-Filter. `taken_at` liefert ab hier die KORRIGIERTE Zeit -
# derselbe Feldname, neue Bedeutung (ADR 0090, Punkt 1).


async def _make_camera(
    session: AsyncSession, project: Project, make: str, model: str, *, offset_minutes: int = 0
) -> ProjectCamera:
    camera = ProjectCamera(
        project_id=project.id, make=make, model=model, offset_minutes=offset_minutes
    )
    session.add(camera)
    await session.commit()
    await session.refresh(camera)
    return camera


async def _make_photo_of_camera(
    session: AsyncSession,
    project: Project,
    path: str,
    taken_at_original: datetime,
    camera: ProjectCamera | None,
) -> Photo:
    offset = 0 if camera is None else camera.offset_minutes
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=taken_at_original + timedelta(minutes=offset),
        taken_at_original=taken_at_original,
        camera_id=None if camera is None else camera.id,
        camera_probed=True,
        last_modified=taken_at_original,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


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


# specs/features/0427-motive-mit-staerke.md, PR 1 Schritt 5: die beiden ADDITIVEN Felder
# `motif_assessment` und `motifs`. Die Kategoriefelder bleiben in dieser PR unberuehrt daneben
# stehen.
#
# Der tragende Nachweis ist das PAAR in `TestTheFourPhotoStates`: derselbe Aufbau ohne Kopfzeile
# und mit einer Kopfzeile, deren acht Staerken alle 0.0 sind, mit einer Assertion darauf, dass die
# beiden Antworten VERSCHIEDEN sind. Der Fehlerpfad ist ein `?? 0` oder eine leere Standardliste:
# acht Nullzeilen statt eines Satzes.


async def _assess_photo(
    session: AsyncSession,
    photo: Photo,
    *,
    source: MotifAssessmentSource = MotifAssessmentSource.CLOUD,
    provider: str | None = "anthropic",
    excluded_document: bool = False,
    strengths: dict[str, float] | None = None,
    computed_at: datetime | None = None,
) -> None:
    vector = dict.fromkeys(MOTIF_REGISTRY, 0.0)
    if strengths is not None:
        vector.update(strengths)
    await upsert_assessment(
        session,
        photo.id,
        source=source,
        strengths=vector,
        excluded_document=excluded_document,
        provider=provider,
        computed_at=computed_at or datetime(2026, 9, 12, 10, 0, 0),
    )
    await session.commit()


class TestTheAlbumSuitabilityInThePhotoOut:
    """specs/features/0428-albumtauglichkeit-vom-modell.md, Schritt 10: die Modellaussage wird
    ausgeliefert, und die beiden Rangfelder sind nullable geworden."""

    async def test_a_rated_photo_carries_level_and_reason(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _rate_album_suitability(db_session, photo, level=2, reason="Augen geschlossen.")

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["album_suitability"] == {"level": 2, "reason": "Augen geschlossen."}

    async def test_a_photo_without_a_row_carries_null(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die ABWESENHEIT ist "noch nicht bewertet" - unterscheidbar von der niedrigsten
        Stufe."""
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["album_suitability"] is None

    async def test_a_missing_reason_is_null_and_not_an_empty_string(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _rate_album_suitability(db_session, photo, level=5, reason=None)

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["album_suitability"] == {"level": 5, "reason": None}

    async def test_the_reason_is_delivered_verbatim_without_any_interpretation(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Fremdtext wird auf dem Lesepfad nicht noch einmal angefasst - saniert und gekappt
        wurde er EINMAL, am Parser. Eine zweite Fassung der Regel hier waere die zweite
        Pflegestelle."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _rate_album_suitability(db_session, photo, reason="<b>fett</b> & 'roh'")

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["album_suitability"]["reason"] == "<b>fett</b> & 'roh'"


class TestARankingRowWithoutAModelVerdict:
    async def test_both_rank_fields_are_null_while_the_event_stays(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=None, rank_position=None)

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["ranking"]["rank_score"] is None
        assert item["ranking"]["rank_position"] is None
        assert item["ranking"]["event_id"] == (await _default_event(db_session, run)).id

    async def test_a_score_of_zero_survives_as_a_real_value(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`0.0` ist ein GUELTIGER Qualitaetswert (schlechteste Modellstufe, schlechteste lokale
        Messung) - ein Falsyness-Filter auf dem Weg nach draussen verloere ihn lautlos."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.0, rank_position=1)

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["ranking"]["rank_score"] == 0.0
        assert item["ranking"]["rank_score"] is not None

    async def test_an_unrated_photo_is_not_part_of_the_draft(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein Foto ohne Qualitaetswert erscheint NICHT im Entwurf - und die Partitionsgroesse
        beschreibt dieselbe Menge, die die Auswahl zeigt. Beides in einem Fall: eine Groesse, die
        die unbewerteten mitzaehlt, machte "Rang 1 von 2" aus einer Partition mit genau einem
        einsehbaren Foto."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        rated = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        unrated = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, rated, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, unrated, rank_score=None, rank_position=None)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        body = response.json()
        assert [item["id"] for item in body["items"]] == [rated.id]
        assert body["total"] == 1
        assert body["items"][0]["ranking"]["partition_size"] == 1


async def _rate_album_suitability(
    session: AsyncSession,
    photo: Photo,
    *,
    level: int = 4,
    reason: str | None = "Alle schauen in die Kamera.",
    computed_at: datetime | None = None,
) -> None:
    session.add(
        PhotoAlbumSuitability(
            photo_id=photo.id,
            level=level,
            reason=reason,
            provider="anthropic",
            computed_at=computed_at or datetime(2026, 9, 13, 10, 0, 0),
        )
    )
    await session.commit()


async def _first_photo_out(client: httpx.AsyncClient, project: Project) -> dict[str, Any]:
    response = await client.get(f"/projects/{project.id}/photos")
    assert response.status_code == 200
    items: list[dict[str, Any]] = response.json()["items"]
    assert len(items) == 1
    return items[0]


class TestTheAdditiveMotifFields:
    async def test_a_photo_with_an_assessment_carries_the_header(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, computed_at=datetime(2026, 9, 12, 10, 0, 0))

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motif_assessment"] == {
            "source": "cloud",
            "provider": "anthropic",
            "excluded_document": False,
            "computed_at": "2026-09-12T10:00:00",
        }

    async def test_a_local_assessment_reports_its_basis_without_a_provider(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Dass eine Auswahl auf der schwaecheren Grundlage beruht, ist erkennbar: die Antwort
        nennt die Grundlage."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, source=MotifAssessmentSource.LOCAL, provider=None)

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motif_assessment"]["source"] == "local"
        assert item["motif_assessment"]["provider"] is None

    async def test_the_list_carries_all_eight_motifs_in_registry_order(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo)

        item = await _first_photo_out(authenticated_api_client, project)

        assert [entry["key"] for entry in item["motifs"]] == list(MOTIF_REGISTRY)

    async def test_the_list_carries_eight_entries_even_with_incomplete_strength_rows(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ein halb gefuellter Vektor darf die Liste nicht verkuerzen - sonst wechselten die
        Zeilen von Foto zu Foto ihre Position, und acht gleichnamige Korrekturschalter laden zum
        Fehlklick ein."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        db_session.add(
            PhotoMotifAssessment(
                photo_id=photo.id,
                source=MotifAssessmentSource.CLOUD,
                excluded_document=False,
                provider="anthropic",
                computed_at=datetime(2026, 9, 12, 10, 0, 0),
            )
        )
        await db_session.flush()
        db_session.add(PhotoMotifStrength(photo_id=photo.id, motif_key="menschen", strength=0.6))
        await db_session.commit()

        item = await _first_photo_out(authenticated_api_client, project)

        assert [entry["key"] for entry in item["motifs"]] == list(MOTIF_REGISTRY)
        by_key = {entry["key"]: entry for entry in item["motifs"]}
        assert by_key["menschen"]["strength"] == pytest.approx(0.6)
        assert by_key["tiere"]["strength"] == 0.0
        assert by_key["tiere"]["correction"] is None

    async def test_a_building_is_strong_and_people_are_weak_and_not_the_other_way_round(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Sichtbar im Ergebnis: ein Foto, auf dem das Modell ein Bauwerk deutlich und Menschen
        nur schwach erkennt, wird als Bauwerk stark und als Menschen schwach GEFUEHRT."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(
            db_session,
            photo,
            strengths={"bauwerk_sehenswuerdigkeit": 0.9, "menschen": 0.2},
        )

        by_key = {
            entry["key"]: entry["strength"]
            for entry in (await _first_photo_out(authenticated_api_client, project))["motifs"]
        }

        assert by_key["bauwerk_sehenswuerdigkeit"] == pytest.approx(0.9)
        assert by_key["menschen"] == pytest.approx(0.2)
        assert by_key["bauwerk_sehenswuerdigkeit"] > by_key["menschen"]

    async def test_a_correction_wins_over_the_model_number_in_the_response(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Antwort traegt die WIRKSAME Staerke - das Frontend rechnet nichts nach."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, strengths={"menschen": 0.9})
        user = (await db_session.execute(select(User))).scalars().first()
        assert user is not None
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=False
            )
        )
        await db_session.commit()

        by_key = {
            entry["key"]: entry
            for entry in (await _first_photo_out(authenticated_api_client, project))["motifs"]
        }

        assert by_key["menschen"]["strength"] == 0.0
        assert by_key["menschen"]["correction"] is False

    async def test_an_excluded_photo_keeps_its_strengths_in_the_response(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Ausschluss gewinnt, die Staerken bleiben gespeichert und werden nicht auf 0
        gesetzt - der Lesehelfer weist das Foto ueber `excluded_document` als ausgeschlossen
        aus."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, excluded_document=True, strengths={"menschen": 0.9})

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motif_assessment"]["excluded_document"] is True
        by_key = {entry["key"]: entry["strength"] for entry in item["motifs"]}
        assert by_key["menschen"] == pytest.approx(0.9)

    async def test_not_a_single_category_field_is_left_in_the_response(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die NEGATIVE Haelfte der Abloesung an der Antwort selbst (Spec 0427, PR 3 Schritt 4).

        Ein stehengebliebenes Feld waere fuer jeden Positivtest der Motivfelder unsichtbar: es
        traegt dann dauerhaft `null` bzw. `[]`, bricht keinen Test und lehrt das Frontend eine
        Aussage, die das Produkt nicht mehr macht."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo)

        item = await _first_photo_out(authenticated_api_client, project)

        for field in (
            "remote_category",
            "category_confidence",
            "category_override",
            "category_candidates",
            "rankings",
        ):
            assert field not in item, field
        assert "ranking" in item


class TestTheMotifPresenceFlag:
    """`MotifStrengthOut.present` - die Aussage des Servers, ob ein Foto ein Motiv TRAEGT.

    Die Grenze wohnt in `selection.py` und verlaesst das Backend nie als Zahl; die Motivmischung
    der Entwurfsansicht liest ausschliesslich dieses Ja/Nein."""

    async def test_the_threshold_is_inclusive_at_the_boundary(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 27, erste Haelfte: Die Staerke EXAKT an der Grenze traegt das Motiv, knapp
        darunter nicht. Der Zahlwert der Grenze steht in KEINEM Testfall - geprueft wird an der
        Grenze selbst, wie sie das Backend fuehrt."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(
            db_session,
            photo,
            strengths={
                "menschen": MOTIF_PRESENCE_THRESHOLD,
                "tiere": MOTIF_PRESENCE_THRESHOLD - 0.01,
            },
        )

        by_key = {
            entry["key"]: entry
            for entry in (await _first_photo_out(authenticated_api_client, project))["motifs"]
        }

        assert by_key["menschen"]["present"] is True
        assert by_key["tiere"]["present"] is False

    async def test_a_correction_decides_the_flag_in_both_directions(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 27, zweite Haelfte: `present` entsteht aus DERSELBEN wirksamen Staerke wie
        `strength` - eine Korrektur nimmt ein starkes Motiv weg und holt ein schwaches herein.
        Beide Richtungen in einem Fall; eine Implementierung, die die MODELLzahl liest, faellt
        genau hier."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, photo, strengths={"menschen": 0.9, "tiere": 0.1})
        user = (await db_session.execute(select(User))).scalars().first()
        assert user is not None
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=False
            )
        )
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="tiere", applies=True
            )
        )
        await db_session.commit()

        by_key = {
            entry["key"]: entry
            for entry in (await _first_photo_out(authenticated_api_client, project))["motifs"]
        }

        assert (by_key["menschen"]["strength"], by_key["menschen"]["present"]) == (0.0, False)
        assert by_key["tiere"]["present"] is True
        assert by_key["tiere"]["strength"] > 0.0

    async def test_a_missing_strength_row_is_zero_and_absent(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 27, dritte Haelfte: Eine fehlende Zeile ergibt `0.0` UND `false` - die
        beiden Felder entstehen aus derselben lokalen Groesse, auch im Ergaenzungszweig."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        db_session.add(
            PhotoMotifAssessment(
                photo_id=photo.id,
                source=MotifAssessmentSource.CLOUD,
                excluded_document=False,
                provider="anthropic",
                computed_at=datetime(2026, 9, 12, 10, 0, 0),
            )
        )
        await db_session.flush()
        db_session.add(PhotoMotifStrength(photo_id=photo.id, motif_key="menschen", strength=0.9))
        await db_session.commit()

        by_key = {
            entry["key"]: entry
            for entry in (await _first_photo_out(authenticated_api_client, project))["motifs"]
        }

        assert (by_key["tiere"]["strength"], by_key["tiere"]["present"]) == (0.0, False)
        assert by_key["menschen"]["present"] is True

    async def test_a_photo_without_an_assessment_carries_no_entry_and_thus_no_flag(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Acht Eintraege mit `present: false` waeren wieder "nichts erkannt" statt "nicht
        klassifiziert" - die Liste bleibt LEER."""
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motifs"] == []

    async def test_present_is_identical_in_the_listing_and_in_the_draft(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Feldgleichheit ueber die Lesepfade, wie bei `proposed`: Ein je Zweig getrennt gesetztes
        Feld liefe genau hier auseinander, und die Motivmischung naennte dann je nach Ansicht
        andere Motive."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        await _assess_photo(db_session, photo, strengths={"menschen": 0.9, "tiere": 0.1})

        listing = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        draft = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"draft": "true"}
        )

        assert listing.json()["items"][0]["motifs"] == draft.json()["items"][0]["motifs"]
        by_key = {entry["key"]: entry["present"] for entry in draft.json()["items"][0]["motifs"]}
        assert (by_key["menschen"], by_key["tiere"]) == (True, False)


class TestTheFourPhotoStates:
    async def test_a_photo_without_an_assessment_carries_no_motif_entry_at_all(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die KARDINALITAET Null, nicht eine Textsuche: der Hinweissatz kann ueber acht
        Nullzeilen stehen, und dann ist er gruen und falsch."""
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motif_assessment"] is None
        assert item["motifs"] == []

    async def test_not_yet_classified_and_nothing_recognised_are_different_responses(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """DAS PAAR. Derselbe Aufbau, einmal ohne Kopfzeile und einmal mit einer Kopfzeile, deren
        acht Staerken alle 0.0 sind - und die Assertion darauf, dass die beiden Antworten
        VERSCHIEDEN sind. Ohne sie machte ein `?? 0` im Lesepfad aus "noch nicht klassifiziert"
        acht Nullzeilen, und kein anderer Test brach."""
        unassessed_project = await _make_project(db_session, name="Ohne Kopfzeile")
        await _make_photo(db_session, unassessed_project, "a.jpg", datetime(2023, 1, 1))
        assessed_project = await _make_project(db_session, name="Mit Kopfzeile")
        assessed = await _make_photo(db_session, assessed_project, "b.jpg", datetime(2023, 1, 1))
        await _assess_photo(db_session, assessed, source=MotifAssessmentSource.LOCAL, provider=None)

        unassessed_item = await _first_photo_out(authenticated_api_client, unassessed_project)
        assessed_item = await _first_photo_out(authenticated_api_client, assessed_project)

        assert unassessed_item["motif_assessment"] is None
        assert assessed_item["motif_assessment"] is not None
        assert len(unassessed_item["motifs"]) == 0
        assert len(assessed_item["motifs"]) == len(MOTIF_REGISTRY)
        assert {entry["strength"] for entry in assessed_item["motifs"]} == {0.0}
        assert unassessed_item["motifs"] != assessed_item["motifs"]

    async def test_a_correction_on_a_photo_without_an_assessment_stays_invisible_in_the_list(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Korrektur ist gespeichert, aber es gibt noch keine Zeile, an der sie haengen
        koennte - die Liste bleibt leer, statt eine einzelne Zeile zu erfinden."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        user = (await db_session.execute(select(User))).scalars().first()
        assert user is not None
        db_session.add(
            PhotoMotifCorrection(
                photo_id=photo.id, user_id=user.id, motif_key="menschen", applies=True
            )
        )
        await db_session.commit()

        item = await _first_photo_out(authenticated_api_client, project)

        assert item["motifs"] == []


class TestTheMotifStrengthsAreLoadedInOneQuery:
    async def test_one_strength_query_regardless_of_the_photo_count(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Kein Query je Foto: dieselbe Auflage wie bei `camera`/`criterion_scores`."""
        project = await _make_project(db_session)
        for index in range(6):
            photo = await _make_photo(
                db_session, project, f"p{index}.jpg", datetime(2023, 1, 1) + timedelta(hours=index)
            )
            await _assess_photo(db_session, photo)

        with _recorded_select_statements() as statements:
            response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        strength_selects = [s for s in statements if "photo_motif_strengths" in s.lower()]
        assert len(strength_selects) == 1, strength_selects


# specs/features/0431-endauswahl-gemeinsam.md: die drei additiven `PhotoOut`-Felder der
# Endauswahl und der neue Leseendpunkt.
#
# DIE FIXTURE-FALLE DIESER STORY: `conftest.py::authenticated_api_client` seedet genau EINEN
# Nutzer. Bei einem Nutzer ist jedes vorgeschlagene, unangefasste Foto in der Endauswahl und
# NICHTS ist strittig. Jeder Fall, dessen Aussage "alle einig" oder "strittig" lautet, legt den
# zweiten Nutzer deshalb AUSDRUECKLICH ueber `_make_second_user` an - sonst ist er inhaltsleer und
# trotzdem gruen.


async def _me(session: AsyncSession) -> User:
    """Der EINE Nutzer, den `authenticated_api_client` seedet."""
    return (await session.execute(select(User).where(User.username == "testuser"))).scalar_one()


async def _rate(
    session: AsyncSession,
    photo: Photo,
    user: User,
    status: RatingStatus | None,
    *,
    favorite: bool = False,
) -> None:
    """Die Albumentscheidung EINES Nutzers. `status=None` mit `favorite=True` ist die reine
    Favoritenzeile - eine Zeile OHNE Aussage ueber die Albumzugehoerigkeit (Zusicherung 5)."""
    existing = (
        await session.execute(
            select(Rating).where(Rating.photo_id == photo.id, Rating.user_id == user.id)
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(Rating(photo_id=photo.id, user_id=user.id, status=status, favorite=favorite))
    else:
        existing.status = status
        existing.favorite = favorite
    await session.commit()
    # NUR die Bewertungssammlung dieses Fotos verwerfen, nicht die ganze Sitzung: Test und
    # Anwendung teilen sich hier EINE Sitzung (`conftest.py`), waehrend jede echte Anfrage ihre
    # eigene bekommt. Eine bereits geladene Sammlung bliebe sonst stehen - die Zeile oben wird
    # ueber `photo_id` angelegt und nicht ueber die Beziehung, also feuert kein Backref-Ereignis.
    # Ein pauschales `expire_all()` verboete danach jeden Zugriff auf `photo.id` (synchrones
    # Nachladen, `MissingGreenlet`).
    session.expire(photo, ["ratings"])


async def _decide(session: AsyncSession, photo: Photo, included: bool) -> None:
    """Die gemeinsame Entscheidung des Projekts - ohne jeden Nutzerbezug."""
    existing = await session.get(FinalSelectionDecision, photo.id)
    if existing is None:
        session.add(FinalSelectionDecision(photo_id=photo.id, included=included))
    else:
        existing.included = included
    await session.commit()


def assert_selection_invariants(item: dict[str, Any]) -> None:
    """Zusicherung 3, als NACHSATZ JEDES Falls und nicht nur dort, wo jemand daran gedacht hat.

    Drei Aussagen: nie `contested` und `in_final_selection` zugleich; `contested` impliziert, dass
    keine Entscheidung vorliegt; liegt eine vor, ist sie die Zugehoerigkeit. Der Bruch zeigt sich
    typischerweise in einem ANDEREN Aufbau als dem, der ihn verursacht hat."""
    decision = item["final_selection_decision"]

    assert not (item["contested"] and item["in_final_selection"]), item["id"]
    if item["contested"]:
        assert decision is None, item["id"]
    if decision is not None:
        assert item["in_final_selection"] is decision, item["id"]


def assert_invariants_everywhere(items: list[dict[str, Any]]) -> None:
    for item in items:
        assert_selection_invariants(item)


async def _listing(client: httpx.AsyncClient, project: Project) -> list[dict[str, Any]]:
    response = await client.get(f"/projects/{project.id}/photos")
    assert response.status_code == 200
    items: list[dict[str, Any]] = response.json()["items"]
    assert_invariants_everywhere(items)
    return items


async def _draft(client: httpx.AsyncClient, project: Project) -> list[dict[str, Any]]:
    response = await client.get(f"/projects/{project.id}/photos", params={"draft": "true"})
    assert response.status_code == 200
    items: list[dict[str, Any]] = response.json()["items"]
    assert_invariants_everywhere(items)
    return items


def _selection_fields(item: dict[str, Any]) -> tuple[bool | None, bool, bool]:
    return (item["final_selection_decision"], item["in_final_selection"], item["contested"])


def _by_id(items: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {item["id"]: item for item in items}


class TestTheThreeFinalSelectionFieldsOnTheListing:
    """Die Regel aus ADR 0099, beobachtet am Standard-Listing. Sie lebt in genau einer reinen
    Funktion; hier wird geprueft, dass der Lesepfad sie mit den RICHTIGEN Eingaengen fuettert."""

    async def test_an_untouched_proposed_photo_is_in_the_final_selection_for_both_users(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ "Bilder, die in beiden Entwuerfen stehen, sind OHNE ZUTUN Teil der Endauswahl." Der
        zweite Nutzer ist ausdruecklich angelegt - ohne ihn saesse die Aussage im Leeren."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        await _make_second_user(db_session)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, True, False)

    async def test_a_photo_struck_by_one_of_two_users_is_contested_and_not_in_the_selection(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ "Ein strittiges Bild, ueber das noch nicht gemeinsam entschieden wurde, gehoert NICHT
        zur Endauswahl." Automatische Zugehoerigkeit gibt es allein bei Einigkeit."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, RatingStatus.REJECTED)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, False, True)

    async def test_a_proposed_photo_taken_by_one_and_untouched_by_the_other_stays_agreed(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 4 am Lesepfad: Bei einem VORGESCHLAGENEN Foto zaehlen die STREICHUNGEN.
        Eine Umsetzung, die hier `taken` zaehlt, liest "strittig" - und das Foto verschwaende aus
        der Endauswahl, ohne dass jemand es angefasst haette."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, RatingStatus.ALBUM_WORTHY)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, True, False)

    async def test_an_unproposed_photo_taken_by_only_one_user_is_contested(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die andere Haelfte von Zusicherung 4: Bei einem NICHT vorgeschlagenen Foto zaehlen die
        AUFNAHMEN. Eine Umsetzung, die hier `user_count - rejected` zaehlt, liest "einig drin"."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(
            db_session, run, photo, rank_score=0.9, rank_position=1, selection_position=None
        )
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, RatingStatus.ALBUM_WORTHY)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, False, True)

    async def test_a_pure_favorite_row_of_the_other_user_leaves_a_proposed_photo_agreed(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 5: ZEILENVORHANDENSEIN IST KEINE AUSSAGE. Seit ADR 0098 kann eine Zeile
        allein den Favoriten tragen; wer ueber die Existenz der Zeile zaehlt statt ueber
        `Rating.status`, macht aus einer Auszeichnung eine Streichung."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, None, favorite=True)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, True, False)

    async def test_with_a_single_user_every_proposed_photo_is_in_and_nothing_is_contested(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 6: `n` ist der NUTZERBESTAND, und der Beweis dafuer ist `n = 1`. Ein
        hartkodiertes `== 2` liefert hier flaechendeckend `in_final_selection: false`."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, True, False)

    async def test_a_decision_overrides_the_consensus_in_both_directions(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 1: EINIGKEIT IST EINE VORBELEGUNG, KEINE SPERRE. Eine Umsetzung, die den
        Konsenszweig VOR die Entscheidung stellt, besteht jeden anderen Fall."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        await _make_second_user(db_session)

        await _decide(db_session, photo, False)
        removed = await _listing(authenticated_api_client, project)
        await _decide(db_session, photo, True)
        restored = await _listing(authenticated_api_client, project)

        assert _selection_fields(removed[0]) == (False, False, False)
        assert _selection_fields(restored[0]) == (True, True, False)


class TestTheThreeFieldsStandOnEveryReadPath:
    async def test_listing_and_draft_report_the_same_three_values(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 11 (Muster `test_present_is_identical_in_the_listing_and_in_the_draft`):
        Ein je Query-Modus getrennt gesetztes Feld liefe genau hier auseinander - und die eine
        Ansicht naennte ein Foto als Teil des Albums, das die andere weglaesst."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, RatingStatus.REJECTED)

        listing = await _listing(authenticated_api_client, project)
        draft = await _draft(authenticated_api_client, project)

        assert _selection_fields(listing[0]) == _selection_fields(draft[0])
        assert _selection_fields(draft[0]) == (None, False, True)

    async def test_the_alternatives_endpoint_reports_them_too(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der dritte Lesepfad. Ein hier vergessener Aufrufer wirft keine Ausnahme und liefert
        keinen Fehlercode - er antwortet `in_final_selection: false` fuer jedes Foto, plausibel
        und still (Auflage S9)."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event = await _default_event(db_session, run)
        reference = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1))
        alternative = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2))
        await _add_ranking(db_session, run, reference, rank_score=0.9, rank_position=1)
        await _add_ranking(
            db_session, run, alternative, rank_score=0.5, rank_position=2, selection_position=None
        )
        await _decide(db_session, alternative, True)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/draft-alternatives",
            params={"event_id": event.id, "photo_id": reference.id},
        )

        assert response.status_code == 200
        items = response.json()["items"]
        assert_invariants_everywhere(items)
        assert _selection_fields(items[0]) == (True, True, False)

    async def test_a_photo_without_any_run_still_carries_the_three_fields(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ohne erfolgreichen Lauf gibt es keinen Vorschlag - die Felder stehen trotzdem, und ein
        von niemandem angefasstes Foto ist dann in keinem Entwurf und damit nicht in der
        Endauswahl."""
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _make_second_user(db_session)

        items = await _listing(authenticated_api_client, project)

        assert _selection_fields(items[0]) == (None, False, False)


async def _selection(
    client: httpx.AsyncClient, project: Project, *, expect: int = 200
) -> dict[str, Any]:
    response = await client.get(f"/projects/{project.id}/album-selection")
    assert response.status_code == expect
    body: dict[str, Any] = response.json()
    if expect == 200:
        assert_invariants_everywhere(body["items"])
    return body


class TestTheAlbumSelectionCandidateSet:
    """Zusicherung 9: Die Kandidatenmenge ist ein ODER DREIER Praedikate, und jedes braucht einen
    Fall, der NUR ueber es hereinkommt. Dazu die Gegenprobe und der Fall, der Kandidaten- von
    Antwortmenge trennt - ohne ihn ist eine Umsetzung, die den Zustandsfilter ganz weglaesst, in
    allen uebrigen Faellen gruen."""

    async def test_a_photo_enters_solely_through_its_selection_position(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        body = await _selection(authenticated_api_client, project)

        assert [item["id"] for item in body["items"]] == [photo.id]

    async def test_a_photo_enters_solely_through_its_decision_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Weder vorgeschlagen noch bewertet - allein die Entscheidungszeile holt es herein
        (Zusicherung 10). Ohne sie waere die Entscheidung entgegen dem Akzeptanzkriterium nicht
        mehr aenderbar, weil das Bild aus beiden Sichten verschwaende."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        carrier = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, carrier, rank_score=0.9, rank_position=1)
        lonely = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
        await _decide(db_session, lonely, False)

        body = await _selection(authenticated_api_client, project)

        by_id = _by_id(body["items"])
        assert lonely.id in by_id
        assert _selection_fields(by_id[lonely.id]) == (False, False, False)

    async def test_a_photo_enters_solely_through_a_rating_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        carrier = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, carrier, rank_score=0.9, rank_position=1)
        taken = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
        other = await _make_second_user(db_session)
        await _rate(db_session, taken, other, RatingStatus.ALBUM_WORTHY)

        body = await _selection(authenticated_api_client, project)

        by_id = _by_id(body["items"])
        assert taken.id in by_id
        assert _selection_fields(by_id[taken.id]) == (None, False, True)

    async def test_a_photo_that_meets_none_of_the_three_predicates_does_not_appear(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Gegenprobe. Ohne sie waere eine Umsetzung, die schlicht alle Fotos des Projekts
        liefert, in jedem der drei Faelle oben gruen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        carrier = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, carrier, rank_score=0.9, rank_position=1)
        stranger = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
        await _add_ranking(
            db_session, run, stranger, rank_score=0.2, rank_position=2, selection_position=None
        )
        await _make_second_user(db_session)

        body = await _selection(authenticated_api_client, project)

        assert stranger.id not in _by_id(body["items"])

    async def test_a_photo_struck_by_everyone_is_a_candidate_and_still_does_not_appear(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Fall, der KANDIDATEN- von ANTWORTMENGE trennt: Das Foto kommt ueber zwei der drei
        Praedikate herein und faellt am Zustandsfilter wieder heraus. Der Weg zurueck fuehrt ueber
        den Einzelentwurf, in dem es weiterhin steht."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        me = await _me(db_session)
        other = await _make_second_user(db_session)
        await _rate(db_session, photo, me, RatingStatus.REJECTED)
        await _rate(db_session, photo, other, RatingStatus.REJECTED)

        body = await _selection(authenticated_api_client, project)

        assert body["items"] == []


class TestTheAlbumSelectionResponseShape:
    async def test_participants_carry_every_user_sorted_by_id_and_only_two_fields(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 13 / Auflage S8: JEDER Nutzer, auch der ohne jede Bewertung - aus
        `ratings[]` abgeleitet fehlte genau der, den die Story ausdruecklich als "kein Sonderfall"
        benennt. Und genau ZWEI Felder: Dies ist der erste Endpunkt, der den vollstaendigen
        Kontenbestand ausliefert; ein `model_validate(User)` schoebe den Passwort-Hash in eine
        Antwort, die im Browser beider Nutzer und in jedem Cache landet."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        me = await _me(db_session)
        other = await _make_second_user(db_session)

        body = await _selection(authenticated_api_client, project)

        assert body["participants"] == [
            {"user_id": me.id, "username": "testuser"},
            {"user_id": other.id, "username": "other-user"},
        ]
        for participant in body["participants"]:
            assert set(participant) == {"user_id", "username"}

    async def test_the_response_carries_no_total(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Menge wird als GANZES geliefert, wie der Entwurfszweig. Ein `total == len(items)`
        lueede dazu ein, etwas zu blaettern, das nicht geblaettert wird."""
        project = await _make_project(db_session)
        await _make_criterion_scoring_run(db_session, project)

        body = await _selection(authenticated_api_client, project)

        assert set(body) == {"participants", "has_proposal", "items"}

    async def test_the_curation_position_is_null_on_this_endpoint(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 16: Eine Zahl waere eine Rangaussage ueber eine Menge, die keinen Rang
        kennt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        for index in range(3):
            photo = await _make_photo(
                db_session, project, f"p{index}.jpg", datetime(2023, 1, 1, 10, index)
            )
            await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=index + 1)

        body = await _selection(authenticated_api_client, project)

        assert len(body["items"]) == 3
        for item in body["items"]:
            assert item["ranking"]["curation_position"] is None

    async def test_an_unknown_project_is_a_404(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        await _make_project(db_session)

        response = await authenticated_api_client.get("/projects/999999/album-selection")

        assert response.status_code == 404

    async def test_the_endpoint_requires_a_token(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)

        response = await api_client.get(f"/projects/{project.id}/album-selection")

        assert response.status_code == 401


class TestTheTwoEmptyStatesAreSeparate:
    """Zusicherung 12: `has_proposal` trennt die beiden Leerzustaende, die die Story GETRENNT
    verlangt. Ein Fall, der nur die leere Liste prueft, laesst sie zusammenfallen - die Oberflaeche
    schickt den Nutzer dann in die Pipeline, obwohl dort nichts zu tun ist."""

    async def test_without_any_successful_run_the_flag_is_false_but_participants_are_filled(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _make_second_user(db_session)

        body = await _selection(authenticated_api_client, project)

        assert body["has_proposal"] is False
        assert body["items"] == []
        assert len(body["participants"]) == 2

    async def test_a_successful_run_without_a_single_selection_position_is_also_false(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Lauf war erfolgreich und hat trotzdem nichts vorgeschlagen - derselbe Leerzustand
        wie "noch kein Lauf", weil in beiden Faellen ein Lauf fehlt, der etwas vorschlaegt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(
            db_session, run, photo, rank_score=0.9, rank_position=1, selection_position=None
        )

        body = await _selection(authenticated_api_client, project)

        assert body["has_proposal"] is False

    async def test_a_single_selection_position_makes_it_true(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        body = await _selection(authenticated_api_client, project)

        assert body["has_proposal"] is True


class TestTheDecisionSurvivesBothWaysOfChange:
    """Zusicherung 2. BEIDE Richtungen im SELBEN Fall - getrennt geschrieben besteht jede Haelfte
    auch bei einer Umsetzung, die die Entscheidung immer oder nie gewinnen laesst."""

    async def test_a_decision_survives_a_later_draft_change_in_both_directions(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """einig -> uneins UND uneins -> einig lassen `final_selection_decision` und
        `in_final_selection` unveraendert, `contested` bleibt `false`."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other = await _make_second_user(db_session)
        await _decide(db_session, photo, True)

        agreed = _by_id((await _selection(authenticated_api_client, project))["items"])
        await _rate(db_session, photo, other, RatingStatus.REJECTED)
        divided = _by_id((await _selection(authenticated_api_client, project))["items"])
        await _rate(db_session, photo, other, None)
        reunited = _by_id((await _selection(authenticated_api_client, project))["items"])

        assert _selection_fields(agreed[photo.id]) == (True, True, False)
        assert _selection_fields(divided[photo.id]) == (True, True, False)
        assert _selection_fields(reunited[photo.id]) == (True, True, False)

    async def test_a_decision_survives_a_new_run_that_drops_the_photo_from_the_proposal(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die zweite Haelfte: ein NEUER Vorschlagslauf, der das Foto nicht mehr traegt. Die Zeile
        haengt am Foto und an keinem Lauf - genau deshalb ueberlebt sie ihn."""
        project = await _make_project(db_session)
        first = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2026, 1, 1, 10, 0)
        )
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, first, photo, rank_score=0.9, rank_position=1)
        await _make_second_user(db_session)
        await _decide(db_session, photo, True)

        before = _by_id((await _selection(authenticated_api_client, project))["items"])

        second = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2026, 1, 2, 10, 0)
        )
        await _make_event(
            db_session,
            second,
            position=1,
            started_at=datetime(2023, 1, 1, 9, 0),
            ended_at=datetime(2023, 1, 1, 11, 0),
        )
        await _add_ranking(
            db_session, second, photo, rank_score=0.4, rank_position=1, selection_position=None
        )

        after = _by_id((await _selection(authenticated_api_client, project))["items"])

        assert _selection_fields(before[photo.id]) == (True, True, False)
        assert _selection_fields(after[photo.id]) == (True, True, False)


class TestThePlacementOfTheFinalSelection:
    async def test_a_new_run_moves_the_decided_photo_to_its_new_event(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 14: Die RANGZEILE hat Vorrang vor der Zeitzuordnung."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first_event = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 9, 0),
            ended_at=datetime(2023, 1, 1, 11, 0),
        )
        second_event = await _make_event(
            db_session,
            run,
            position=2,
            started_at=datetime(2023, 1, 2, 9, 0),
            ended_at=datetime(2023, 1, 2, 11, 0),
        )
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(
            db_session, run, photo, event=second_event, rank_score=0.9, rank_position=1
        )

        body = await _selection(authenticated_api_client, project)

        assert _by_id(body["items"])[photo.id]["event"]["id"] == second_event.id
        assert first_event.id != second_event.id

    async def test_the_draft_and_the_final_selection_order_the_same_photos_identically(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 15: `_place_in_events` wird von BEIDEN Zweigen aufgerufen, nicht zweimal
        geschrieben. Das Paar gehoert in EINEN Fall - zweimal geschrieben ordneten Entwurf und
        Endauswahl dieselben Fotos verschieden, sichtbar, ohne dass eine Pruefung rot wuerde."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        late_event = await _make_event(
            db_session,
            run,
            position=2,
            started_at=datetime(2023, 1, 2, 9, 0),
            ended_at=datetime(2023, 1, 2, 11, 0),
        )
        early_event = await _make_event(
            db_session,
            run,
            position=1,
            started_at=datetime(2023, 1, 1, 9, 0),
            ended_at=datetime(2023, 1, 1, 11, 0),
        )
        late = await _make_photo(db_session, project, "c.jpg", datetime(2023, 1, 2, 10, 0))
        early_second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
        early_first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        for photo, photo_event in (
            (late, late_event),
            (early_second, early_event),
            (early_first, early_event),
        ):
            await _add_ranking(
                db_session, run, photo, event=photo_event, rank_score=0.5, rank_position=1
            )

        draft = await _draft(authenticated_api_client, project)
        selection = await _selection(authenticated_api_client, project)

        expected = [early_first.id, early_second.id, late.id]
        assert [item["id"] for item in draft] == expected
        assert [item["id"] for item in selection["items"]] == expected
        assert [item["event"]["id"] for item in selection["items"]] == [
            early_event.id,
            early_event.id,
            late_event.id,
        ]


class TestTheFinalSelectionIsBoundToItsProject:
    async def test_a_decided_photo_of_another_project_never_enters_the_answer(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S2: Zwei der drei Quellen sind PROJEKTBLIND - `final_selection_decisions` hat
        nur `photo_id`, `Rating` nur `(photo_id, user_id)`. Ein in die ODER-Verknuepfung
        gerutschtes Projektpraedikat ist syntaktisch unauffaellig und liesse jedes jemals bewertete
        oder entschiedene Foto ALLER Projekte herein - kohaerent aussehende Fremddaten statt einer
        erkennbar falschen Menge. Und das ist die Menge, die der Export nimmt."""
        mine = await _make_project(db_session, "Meins")
        theirs = await _make_project(db_session, "Fremd")
        my_run = await _make_criterion_scoring_run(db_session, mine)
        my_photo = await _make_photo(db_session, mine, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, my_run, my_photo, rank_score=0.9, rank_position=1)

        other = await _make_second_user(db_session)
        foreign_decided = await _make_photo(
            db_session, theirs, "x.jpg", datetime(2023, 1, 1, 10, 0)
        )
        foreign_rated = await _make_photo(db_session, theirs, "y.jpg", datetime(2023, 1, 1, 10, 5))
        await _decide(db_session, foreign_decided, True)
        await _rate(db_session, foreign_rated, other, RatingStatus.ALBUM_WORTHY)

        body = await _selection(authenticated_api_client, mine)

        assert [item["id"] for item in body["items"]] == [my_photo.id]

    async def test_a_ranking_of_another_projects_run_never_enters_the_answer(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der Rangzweig haengt zusaetzlich am `criterion_scoring_run_id` des letzten
        erfolgreichen Laufs DIESES Projekts - `PhotoRanking` traegt keine `project_id`."""
        mine = await _make_project(db_session, "Meins")
        theirs = await _make_project(db_session, "Fremd")
        my_run = await _make_criterion_scoring_run(db_session, mine)
        their_run = await _make_criterion_scoring_run(db_session, theirs)
        my_photo = await _make_photo(db_session, mine, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, my_run, my_photo, rank_score=0.9, rank_position=1)
        foreign = await _make_photo(db_session, theirs, "x.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, their_run, foreign, rank_score=0.9, rank_position=1)

        body = await _selection(authenticated_api_client, mine)

        assert [item["id"] for item in body["items"]] == [my_photo.id]


class TestTheDenominatorComesFromTheSameRead:
    async def test_the_participant_count_is_the_denominator_of_the_rule(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Auflage S8: `user_count` stammt aus DERSELBEN Leseoperation wie `participants`. Gingen
        beide auseinander, behauptete die Ansicht Einigkeit ueber zwei Teilnehmer, waehrend die
        Regel ueber drei rechnet - die Endauswahl waere kleiner als die Anzeige sie zeigt, ohne
        dass ein Feld der Antwort widerspruechlich aussieht.

        Der Nachweis laeuft ueber den entarteten Fall: Mit genau EINEM Teilnehmer ist jedes
        vorgeschlagene, unangefasste Foto drin; mit ZWEI und einer Streichung ist es strittig."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        alone = await _selection(authenticated_api_client, project)

        other = await _make_second_user(db_session)
        await _rate(db_session, photo, other, RatingStatus.REJECTED)
        together = await _selection(authenticated_api_client, project)

        assert len(alone["participants"]) == 1
        assert _selection_fields(_by_id(alone["items"])[photo.id]) == (None, True, False)
        assert len(together["participants"]) == 2
        assert _selection_fields(_by_id(together["items"])[photo.id]) == (None, False, True)


class TestTheThreeFieldsAreIdenticalOnAllFourReadPaths:
    async def test_the_same_photo_reports_the_same_three_values_everywhere(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zusicherung 11, vollstaendig: Listing, Entwurfszweig, Alternativen-Endpunkt und der
        neue Endpunkt fuer DASSELBE Foto."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event = await _default_event(db_session, run)
        reference = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        subject = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 1, 10, 30))
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
        values = {
            "listing": _selection_fields(listing[subject.id]),
            "alternatives": _selection_fields(alternative_items[subject.id]),
            "selection": _selection_fields(selection[subject.id]),
        }
        assert set(values.values()) == {(True, True, False)}, values
        # Der Entwurfszweig fuehrt dieses Foto bewusst NICHT (niemand hat es aufgenommen) - die
        # Feldgleichheit gilt fuer das Bezugsbild, das in allen vier Antworten steht.
        assert _selection_fields(draft[reference.id]) == _selection_fields(listing[reference.id])


class TestTheSingleDraftStaysUntouchedByAJointDecision:
    """Die "Spannung, die aufzuloesen ist": Story 6 sagt zu, dass neben der Bewertung KEINE zweite,
    daneben liegende Auswahlebene entsteht. Die Endauswahl ist eine Ebene UEBER beiden Entwuerfen -
    hier sind die Verhaltensnachweise dafuer, in beide Richtungen."""

    async def test_a_joint_decision_changes_neither_the_draft_nor_any_ratings(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nachweisstelle 4: Verglichen wird die vollstaendige ID-FOLGE und `total`, nicht die
        Menge - eine Umordnung waere sonst unsichtbar. Dazu die `ratings[]` BEIDER Nutzer."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = []
        for index in range(3):
            photo = await _make_photo(
                db_session, project, f"p{index}.jpg", datetime(2023, 1, 1, 10, index)
            )
            await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=index + 1)
            photos.append(photo)
        other = await _make_second_user(db_session)
        await _rate(db_session, photos[1], other, RatingStatus.REJECTED)

        before = await _draft(authenticated_api_client, project)
        before_total = (
            await authenticated_api_client.get(
                f"/projects/{project.id}/photos", params={"draft": "true"}
            )
        ).json()["total"]

        await _decide(db_session, photos[1], False)
        await _decide(db_session, photos[0], False)

        after = await _draft(authenticated_api_client, project)
        after_total = (
            await authenticated_api_client.get(
                f"/projects/{project.id}/photos", params={"draft": "true"}
            )
        ).json()["total"]

        assert [item["id"] for item in after] == [item["id"] for item in before]
        assert after_total == before_total
        assert [item["ratings"] for item in after] == [item["ratings"] for item in before]

    async def test_a_draft_change_leaves_an_existing_joint_decision_untouched(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nachweisstelle 5, die GEGENRICHTUNG, die Nachweisstelle 4 nicht abdeckt: Nach einer
        Aenderung der Albumentscheidung eines Nutzers sind die drei Felder unveraendert."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        me = await _me(db_session)
        await _make_second_user(db_session)
        await _decide(db_session, photo, False)

        before = _by_id(await _listing(authenticated_api_client, project))
        await _rate(db_session, photo, me, RatingStatus.ALBUM_WORTHY)
        after = _by_id(await _listing(authenticated_api_client, project))

        assert _selection_fields(before[photo.id]) == (False, False, False)
        assert _selection_fields(after[photo.id]) == (False, False, False)

    async def test_the_alternatives_response_is_identical_before_and_after_a_joint_decision(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nachweisstelle 6: Antwortmenge UND Reihenfolge des Alternativen-Endpunkts sind vor und
        nach einer gemeinsamen Entscheidung identisch."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event = await _default_event(db_session, run)
        reference = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, 10, 0))
        await _add_ranking(db_session, run, reference, rank_score=0.9, rank_position=1)
        alternatives = []
        for index in range(3):
            photo = await _make_photo(
                db_session, project, f"alt{index}.jpg", datetime(2023, 1, 1, 11, index)
            )
            await _add_ranking(
                db_session,
                run,
                photo,
                rank_score=0.5 - index * 0.1,
                rank_position=index + 2,
                selection_position=None,
            )
            alternatives.append(photo)
        await _make_second_user(db_session)

        async def _alternative_ids() -> list[int]:
            response = await authenticated_api_client.get(
                f"/projects/{project.id}/draft-alternatives",
                params={"event_id": event.id, "photo_id": reference.id},
            )
            assert response.status_code == 200
            return [item["id"] for item in response.json()["items"]]

        before = await _alternative_ids()
        await _decide(db_session, alternatives[1], True)
        await _decide(db_session, alternatives[2], False)
        after = await _alternative_ids()

        assert before
        assert after == before
