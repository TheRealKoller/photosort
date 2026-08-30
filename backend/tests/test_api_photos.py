from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.config import settings
from photosort.criteria import CRITERIA_REGISTRY
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCriterionScore,
    PhotoRanking,
    PhotoScore,
    Project,
    Rating,
    RatingStatus,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.security import hash_password
from photosort.thumbnails import display_path, thumbnail_path


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
    db_session.add(Rating(photo_id=photo.id, user_id=other_user.id, status=RatingStatus.FAVORITE))
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
    session: AsyncSession, project: Project, *, status: ScanStatus = ScanStatus.SUCCESS
) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=status
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _add_ranking(
    session: AsyncSession,
    run: CriterionScoringRun,
    photo: Photo,
    *,
    cluster_key: str = "cluster-0",
    category_key: str = "landscape",
    rank_score: float,
    rank_position: int,
) -> None:
    session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            cluster_key=cluster_key,
            category_key=category_key,
            rank_score=rank_score,
            rank_position=rank_position,
        )
    )
    await session.commit()


class TestTopNPerCategory:
    """Kategorie-Kuratierung + Backfill (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
    backfill.md)."""

    async def test_returns_top_n_per_partition_with_ranking_details(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        third = await _make_photo(db_session, project, "c.jpg", datetime(2023, 1, 3, tzinfo=UTC))
        await _add_ranking(db_session, run, first, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, second, rank_score=0.5, rank_position=2)
        await _add_ranking(db_session, run, third, rank_score=0.1, rank_position=3)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 2}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert [item["id"] for item in body["items"]] == [first.id, second.id]
        ranking = body["items"][0]["ranking"]
        # partition_size ist die GROESSE DER GESAMTEN Partition (hier 3 Fotos), nicht die
        # angeforderte top_n_per_category=2 - "Rang M von N" soll immer den vollen Pool zeigen
        # (Architektur-Abschnitt der Spec 0040).
        assert ranking == {
            "cluster_key": "cluster-0",
            "category_key": "landscape",
            "rank_score": 0.9,
            "rank_position": 1,
            "partition_size": 3,
        }

    async def test_partitions_are_independent(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        landscape_photo = await _make_photo(
            db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC)
        )
        people_photo = await _make_photo(
            db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC)
        )
        await _add_ranking(
            db_session, run, landscape_photo, category_key="landscape", rank_score=0.9,
            rank_position=1,
        )
        await _add_ranking(
            db_session, run, people_photo, category_key="people", rank_score=0.1, rank_position=1
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 1}
        )

        assert {item["id"] for item in response.json()["items"]} == {
            landscape_photo.id,
            people_photo.id,
        }

    async def test_fewer_than_n_candidates_returns_fewer_without_error(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        only = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, only, rank_score=0.9, rank_position=1)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 5}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == only.id

    async def test_backfill_shows_next_best_photo_after_rejecting_the_top_one(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Kernfall der Spec: nach REJECTED des aktuell sichtbaren Top-Fotos liefert ein erneuter
        # Abruf automatisch das naechstbeste, bisher nicht gezeigte Foto DERSELBEN Partition -
        # reiner Query-Effekt, kein Backfill-Endpoint, kein aktives "Nachruecken" im Server-Code.
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, first, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, second, rank_score=0.5, rank_position=2)

        before = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 1}
        )
        assert [item["id"] for item in before.json()["items"]] == [first.id]

        await authenticated_api_client.put(
            f"/photos/{first.id}/rating", json={"status": "rejected"}
        )

        after = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 1}
        )
        assert [item["id"] for item in after.json()["items"]] == [second.id]

    async def test_rejection_filter_is_scoped_to_the_current_user(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Personenbezug (Akzeptanzkriterium der Spec): ein von Nutzer A abgelehntes Foto bleibt
        # fuer Nutzer B sichtbar, solange der es nicht selbst ablehnt.
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)
        other_user = await _make_second_user(db_session)
        db_session.add(
            Rating(photo_id=photo.id, user_id=other_user.id, status=RatingStatus.REJECTED)
        )
        await db_session.commit()

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 1}
        )

        assert [item["id"] for item in response.json()["items"]] == [photo.id]

    async def test_empty_before_any_successful_criterion_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 3}
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    async def test_rejects_top_n_per_category_outside_valid_range(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 11}
        )

        assert response.status_code == 422

    async def test_includes_criterion_scores_alongside_ranking(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Test-Review-Fund: criterion_scores und ranking wurden bisher nur je einzeln getestet,
        # nie im selben (top_n_per_category-)Zweig kombiniert - _to_photo_out setzt aber beide in
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
            f"/projects/{project.id}/photos", params={"top_n_per_category": 1}
        )

        item = response.json()["items"][0]
        assert item["ranking"] is not None
        assert [c["criterion_key"] for c in item["criterion_scores"]] == ["sharpness"]


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
                "category_eligible": False,
            },
            {
                "criterion_key": "content_people",
                "display_name": "Menschen erkannt",
                "value": 1.0,
                "source": "local_ml",
                "category_eligible": True,
            },
        ]

    async def test_content_landscape_is_exposed_as_a_non_category_quality_criterion(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/features/0217, ADR 0046 Punkt 1: content_landscape heisst in den
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
                "category_eligible": False,
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
                "category_eligible": False,
            }
        ]

    async def test_category_eligible_matches_registry_for_every_criterion(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md,
        # Architektur-Entscheidung 1: das ausgelieferte Flag ist keine zweite Wahrheit, sondern
        # exakt `CriterionDefinition.category_eligible`. Ein einziger Registry-weiter Test statt
        # einer Parametrisierung pro Key - welche Kriterien kategoriefaehig SIND, nagelt bereits
        # test_criteria.py::test_exactly_five_content_criteria_are_category_eligible fest.
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
        assert {c["criterion_key"]: c["category_eligible"] for c in criterion_scores} == {
            key: definition.category_eligible for key, definition in CRITERIA_REGISTRY.items()
        }


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
        # specs/features/0217, ADR 0046 Punkt 5: die Read-Time-Ableitung folgt derselben
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
        threshold = CRITERIA_REGISTRY["landschaft"].category_presence_threshold
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
        threshold = CRITERIA_REGISTRY["gebaeude"].category_presence_threshold
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

    async def test_remote_category_result_uses_the_latest_computed_at_of_several_detections(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Edge Case der Teststrategie: mehrere PhotoCategoryDetection-Zeilen desselben Fotos mit
        # potenziell unterschiedlichem computed_at (defensiv max()).
        from photosort.models import CategoryLabel, PhotoCategoryDetection

        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        label_a = CategoryLabel(canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0])
        label_b = CategoryLabel(canonical_key="strand", display_name="Strand", embedding=[0.0, 1.0])
        db_session.add_all([label_a, label_b])
        await db_session.flush()
        db_session.add_all(
            [
                PhotoCategoryDetection(
                    photo_id=photo.id,
                    category_label_id=label_a.id,
                    raw_label="Hund",
                    confidence=0.9,
                    provider="anthropic",
                    computed_at=datetime(2023, 1, 1, tzinfo=UTC),
                ),
                PhotoCategoryDetection(
                    photo_id=photo.id,
                    category_label_id=label_b.id,
                    raw_label="Strand",
                    confidence=0.8,
                    provider="anthropic",
                    computed_at=datetime(2023, 6, 1, tzinfo=UTC),
                ),
            ]
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        entry = next(
            e
            for e in response.json()["items"][0]["cloud_vision_status"]
            if e["phase"] == "remote_category"
        )
        assert entry["status"] == "result"
        assert entry["attempted_at"].startswith("2023-06-01")

    async def test_remote_category_result_persists_even_after_consent_is_disabled_again(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/architecture/0002-testkonzept.md ("Read-Time-Prioritaets-Kaskade..." fuer ADR
        # 0035): "Erfolgssignal vorhanden UND Consent nachtraeglich deaktiviert -> weiterhin
        # result/no_result (Rang 1 vor Rang 3)" - Remote-Kategorie-Pendant zu
        # test_landmark_result_persists_even_after_consent_is_disabled_again oben.
        from photosort.models import CategoryLabel, PhotoCategoryDetection

        project = await _make_project(db_session)
        assert project.cloud_vision_detection_enabled is False
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        label = CategoryLabel(canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0])
        db_session.add(label)
        await db_session.flush()
        db_session.add(
            PhotoCategoryDetection(
                photo_id=photo.id,
                category_label_id=label.id,
                raw_label="Hund",
                confidence=0.9,
                provider="anthropic",
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


class TestRemoteCategoryFields:
    """specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md:
    `PhotoOut.remote_category_labels`/`category_override`/`category_candidates`."""

    async def test_remote_category_labels_is_empty_list_when_none_exist(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        item = response.json()["items"][0]
        assert item["remote_category_labels"] == []
        assert item["category_override"] is None
        assert item["category_candidates"] == []

    async def test_remote_category_labels_and_candidates_reflect_persisted_detections(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        from photosort.models import CategoryLabel, PhotoCategoryDetection

        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        label = CategoryLabel(canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0])
        db_session.add(label)
        await db_session.flush()
        db_session.add(
            PhotoCategoryDetection(
                photo_id=photo.id,
                category_label_id=label.id,
                raw_label="Hund",
                confidence=0.9,
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        item = response.json()["items"][0]
        assert item["remote_category_labels"] == [
            {
                "canonical_key": "hund",
                "display_name": "Hund",
                "raw_label": "Hund",
                "confidence": 0.9,
                "provider": "anthropic",
            }
        ]
        assert item["category_candidates"] == [
            {"category_key": "hund", "origin": "remote", "score": 0.9, "provider": "anthropic"}
        ]

    async def test_local_qualifying_criterion_becomes_a_category_candidate(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="content_people",
                value=1.0,
                source=CriterionSource.LOCAL_ML,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        candidates = response.json()["items"][0]["category_candidates"]
        assert candidates == [
            {"category_key": "people", "origin": "local", "score": 1.0, "provider": None}
        ]

    async def test_non_qualifying_local_criterion_is_not_a_candidate(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="content_people",
                value=0.0,
                source=CriterionSource.LOCAL_ML,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["category_candidates"] == []

    async def test_category_override_reflects_the_photo_score_field(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=1.0,
                exposure=0.0,
                category_override="urlaub",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["category_override"] == "urlaub"

    async def test_candidates_are_sorted_by_score_descending(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        from photosort.models import CategoryLabel, PhotoCategoryDetection

        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="content_people",
                value=0.6,
                source=CriterionSource.LOCAL_ML,
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        label = CategoryLabel(canonical_key="strand", display_name="Strand", embedding=[1.0, 0.0])
        db_session.add(label)
        await db_session.flush()
        db_session.add(
            PhotoCategoryDetection(
                photo_id=photo.id,
                category_label_id=label.id,
                raw_label="Strand",
                confidence=0.9,
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        candidates = response.json()["items"][0]["category_candidates"]
        assert [c["category_key"] for c in candidates] == ["strand", "people"]


class TestDefaultListingRanking:
    """Bewertungsdetails-Info-Popover (specs/features/0040): `RankingOut` wird jetzt auch im
    Standard-Listing-Zweig befuellt (bisher nur bei `top_n_per_category`), damit Grid-/
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
            "cluster_key": "cluster-0",
            "category_key": "landscape",
            "rank_score": 0.9,
            "rank_position": 1,
            "partition_size": 2,
        }
        assert items[second.id]["ranking"]["rank_position"] == 2

    async def test_default_listing_ranking_is_null_without_criterion_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["ranking"] is None

    async def test_partition_size_is_isolated_per_project_in_default_listing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Security-Review-Fund: kein dedizierter Cross-Project-Isolationstest fuer den neuen,
        # im Default-Listing-Zweig befuellten partition_size/RankingOut-Pfad - beide Projekte
        # nutzen absichtlich dieselben cluster_key/category_key-Werte ("cluster-0"/"landscape"),
        # damit ein etwaiges fehlendes project_id-Scoping in _partition_sizes/
        # _latest_successful_criterion_scoring_run_id sichtbar wuerde (Partition-Groesse 3 statt 1).
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
