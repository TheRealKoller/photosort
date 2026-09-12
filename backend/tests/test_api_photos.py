from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.categories import CATEGORY_NOT_RECOGNIZED
from photosort.config import settings
from photosort.criteria import CRITERIA_REGISTRY
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Event,
    FineLabel,
    Photo,
    PhotoCategoryClassification,
    PhotoCriterionScore,
    PhotoFineLabel,
    PhotoLandmarkDetection,
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
from photosort.security import create_access_token, hash_password
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


async def _add_ranking(
    session: AsyncSession,
    run: CriterionScoringRun,
    photo: Photo,
    *,
    event: Event | None = None,
    category_key: str = "landscape",
    rank_score: float,
    rank_position: int,
    is_primary: bool = True,
) -> None:
    """specs/features/0300-nebenkategorien.md: `is_primary` ist pflichtig - der Default `True`
    haelt alle bestehenden Aufrufe bei ihrer bisherigen Bedeutung (eine Zugehoerigkeit je Foto,
    und die ist die Hauptzeile).

    Ohne `event` faellt die Zeile in das eine Vorgabe-Event des Laufs - dieselbe Rolle, die frueher
    der Vorgabewert `cluster_key="cluster-0"` hatte."""
    event_row = await _default_event(session, run) if event is None else event
    session.add(
        PhotoRanking(
            criterion_scoring_run_id=run.id,
            photo_id=photo.id,
            event_id=event_row.id,
            category_key=category_key,
            rank_score=rank_score,
            rank_position=rank_position,
            is_primary=is_primary,
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
        [ranking] = body["items"][0]["rankings"]
        # partition_size ist die GROESSE DER GESAMTEN Partition (hier 3 Fotos), nicht die
        # angeforderte top_n_per_category=2 - "Rang M von N" soll immer den vollen Pool zeigen
        # (Architektur-Abschnitt der Spec 0040).
        assert ranking == {
            "event_id": (await _default_event(db_session, run)).id,
            "category_key": "landscape",
            "rank_score": 0.9,
            "rank_position": 1,
            "partition_size": 3,
            "is_primary": True,
            # Im Kuratierungsmodus traegt jede ausgewaehlte Zugehoerigkeit ihren Platz in der um
            # die eigenen Ablehnungen bereinigten Auswahl (specs/features/0300-nebenkategorien.md).
            "curation_position": 1,
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
            db_session,
            run,
            landscape_photo,
            category_key="landscape",
            rank_score=0.9,
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

    async def test_rejecting_a_photo_does_not_change_the_selection(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Gegenteil-Test des frueheren `test_backfill_shows_next_best_photo_after_rejecting_
        the_top_one` (specs/features/0357-voller-bildvorrat-kuratierung.md, ADR 0071
        Entscheidung 1): derselbe Aufbau, umgekehrte Erwartung. Nach dem Verwerfen des
        Top-Fotos rueckt NICHTS nach - das verworfene Foto bleibt an seiner Position.

        Geprueft als vollstaendiger Listenvergleich (Ids in Reihenfolge), nicht als blosses
        "das Foto ist noch da": ein Vorhandensein-Test bliebe auch dann gruen, wenn hinter dem
        Foto die Liste umsortiert wuerde."""
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
        assert [item["id"] for item in after.json()["items"]] == [first.id]
        [item] = after.json()["items"]
        [ranking] = item["rankings"]
        assert (ranking["rank_position"], ranking["curation_position"]) == (1, 1)

    async def test_a_rejected_photo_stays_in_the_selection_with_its_rating(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Zweite Haelfte von ADR 0071 Entscheidung 3: das verworfene Foto verschwindet nicht,
        sondern traegt seinen Zustand dort, wo er im Produkt immer steht - in `ratings[]`. Die
        Kuratierungsansicht leitet die Kachel-Darstellung ausschliesslich daraus ab
        (`utils/ownRating.ts::ownRatingStatus`), es gibt kein eigenes Antwortfeld dafuer."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(db_session, run, photo, rank_score=0.9, rank_position=1)

        await authenticated_api_client.put(
            f"/photos/{photo.id}/rating", json={"status": "rejected"}
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 1}
        )

        [item] = response.json()["items"]
        assert item["id"] == photo.id
        assert [r["status"] for r in item["ratings"]] == ["rejected"]

    async def test_response_is_independent_of_the_asking_user(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Gegenteil-Test der frueheren `test_rejection_filter_is_scoped_to_the_current_user`
        und `test_curation_position_is_scoped_to_the_rejections_of_the_asking_user`
        (specs/features/0357-voller-bildvorrat-kuratierung.md, ADR 0071 Entscheidung 1): der
        Zwei-Nutzer-Aufbau bleibt, aber statt der Verschiedenheit wird jetzt die GLEICHHEIT
        zugesichert.

        Ohne diesen Fall bliebe die neue Zusage ("die Auswahl haengt nur noch vom Lauf ab, nicht
        mehr vom Betrachter") die einzige des Endpunkts ohne Beleg - ein versehentlich
        stehengebliebener nutzerabhaengiger Join faellt durch jeden Ein-Nutzer-Test."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, first, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, second, rank_score=0.5, rank_position=2)

        other_user = await _make_second_user(db_session)
        # Der zweite Nutzer verwirft das Top-Foto - fuer BEIDE Sichten muss das folgenlos sein.
        db_session.add(
            Rating(photo_id=first.id, user_id=other_user.id, status=RatingStatus.REJECTED)
        )
        await db_session.commit()

        async def selection(client: httpx.AsyncClient) -> tuple[list[int], dict[int, int | None]]:
            response = await client.get(
                f"/projects/{project.id}/photos", params={"top_n_per_category": 2}
            )
            assert response.status_code == 200
            items = response.json()["items"]
            return (
                [item["id"] for item in items],
                {item["id"]: item["rankings"][0]["curation_position"] for item in items},
            )

        own_view = await selection(authenticated_api_client)

        # DIESELBE Anfrage, anderer Nutzer. Nur der Bearer-Token wechselt (und wird danach
        # zurueckgesetzt), damit derselbe ASGI-Transport und dieselbe Sitzung benutzt werden.
        own_authorization = authenticated_api_client.headers["Authorization"]
        authenticated_api_client.headers["Authorization"] = (
            f"Bearer {create_access_token(other_user)}"
        )
        try:
            other_view = await selection(authenticated_api_client)
        finally:
            authenticated_api_client.headers["Authorization"] = own_authorization

        assert own_view == other_view
        assert own_view == ([first.id, second.id], {first.id: 1, second.id: 2})

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
        assert item["rankings"] != []
        assert [c["criterion_key"] for c in item["criterion_scores"]] == ["sharpness"]


class TestCurationCandidates:
    """Weitere Kandidaten einer Partition auf Abruf
    (specs/features/0357-voller-bildvorrat-kuratierung.md, ADR 0071 Entscheidung 5):
    `GET /projects/{id}/curation-candidates` liefert die Zugehoerigkeiten EINER Partition
    mit `rank_position > after_rank`, aufsteigend, als `PhotoListOut`."""

    @staticmethod
    async def _partition(
        session: AsyncSession,
        project: Project,
        run: CriterionScoringRun,
        size: int,
        *,
        event_position: int = 1,
        category_key: str = "landschaft",
    ) -> list[Photo]:
        photos = []
        for index in range(size):
            photo = await _make_photo(
                session, project, f"p{index}-{project.id}.jpg", datetime(2023, 1, 1, tzinfo=UTC)
            )
            await _add_ranking(
                session,
                run,
                photo,
                event=await _default_event(session, run, position=event_position),
                category_key=category_key,
                rank_score=1.0 - index / 100,
                rank_position=index + 1,
            )
            photos.append(photo)
        return photos

    async def test_returns_the_memberships_after_the_given_rank_in_ascending_order(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 28, erste Haelfte."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._partition(db_session, project, run, 5)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={
                "event_id": (await _default_event(db_session, run)).id,
                "category_key": "landschaft",
                "after_rank": 2,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body["items"]] == [p.id for p in photos[2:]]
        assert body["total"] == 3

    async def test_total_is_the_remaining_partition_and_ignores_limit_and_offset(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 28, zweite Haelfte, und Akzeptanzkriterium 27: `total` ist
        `max(partition_size - after_rank, 0)` und damit UNABHAENGIG von `limit`/`offset` - ein aus
        `len(items)` gebildetes `total` waere auf der ersten Seite nicht davon zu unterscheiden.
        Die ZWEITE Seite ist der Pflichtfall: sie wird mit dem richtigen Offset angefordert."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._partition(db_session, project, run, 5)
        event_id = (await _default_event(db_session, run)).id

        async def page(limit: int, offset: int) -> tuple[list[int], int]:
            response = await authenticated_api_client.get(
                f"/projects/{project.id}/curation-candidates",
                params={
                    "event_id": event_id,
                    "category_key": "landschaft",
                    "after_rank": 1,
                    "limit": limit,
                    "offset": offset,
                },
            )
            assert response.status_code == 200
            body = response.json()
            return [item["id"] for item in body["items"]], body["total"]

        first_page = await page(limit=2, offset=0)
        second_page = await page(limit=2, offset=2)

        assert first_page == ([photos[1].id, photos[2].id], 4)
        assert second_page == ([photos[3].id, photos[4].id], 4)

    async def test_rejected_photos_are_included_with_their_ratings(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 29: auch hier ist "verworfen" ein Anzeigezustand, kein
        Filterkriterium - das Foto bleibt in der Liste und traegt seinen Zustand in `ratings[]`."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photos = await self._partition(db_session, project, run, 3)
        await authenticated_api_client.put(
            f"/photos/{photos[2].id}/rating", json={"status": "rejected"}
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={
                "event_id": (await _default_event(db_session, run)).id,
                "category_key": "landschaft",
                "after_rank": 1,
            },
        )

        items = response.json()["items"]
        assert [item["id"] for item in items] == [photos[1].id, photos[2].id]
        assert {item["id"]: [r["status"] for r in item["ratings"]] for item in items} == {
            photos[1].id: [],
            photos[2].id: ["rejected"],
        }

    async def test_curation_position_is_set_only_for_the_requested_membership(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 30: `curation_position` traegt NUR die angefragte Zugehoerigkeit -
        sonst erschiene das nachgeladene Foto zusaetzlich unter seinen anderen Kategorien, in
        denen niemand aufgeklappt hat."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(
            db_session, run, photo, category_key="landschaft", rank_score=0.9, rank_position=2
        )
        await _add_ranking(
            db_session,
            run,
            photo,
            category_key="tier",
            rank_score=0.9,
            rank_position=1,
            is_primary=False,
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={
                "event_id": (await _default_event(db_session, run)).id,
                "category_key": "landschaft",
                "after_rank": 1,
            },
        )

        [item] = response.json()["items"]
        assert {r["category_key"]: r["curation_position"] for r in item["rankings"]} == {
            "landschaft": 2,
            "tier": None,
        }

    async def test_empty_without_a_successful_criterion_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 31, erster Rand: 200 mit leerem `PhotoListOut`, kein Fehler."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project, status=ScanStatus.FAILED)
        await self._partition(db_session, project, run, 3)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={
                "event_id": (await _default_event(db_session, run)).id,
                "category_key": "landschaft",
                "after_rank": 0,
            },
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    @pytest.mark.parametrize(
        ("event_id_offset", "category_key", "after_rank"),
        [
            pytest.param(4200, "landschaft", 0, id="unbekannte-event-id"),
            pytest.param(0, "gibtsnicht", 0, id="unbekannter-category-key"),
            pytest.param(0, "landschaft", 3, id="after_rank-gleich-partitionsgroesse"),
            pytest.param(0, "landschaft", 99, id="after_rank-jenseits-der-partition"),
        ],
    )
    async def test_empty_at_the_silent_edges(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        event_id_offset: int,
        category_key: str,
        after_rank: int,
    ) -> None:
        """Akzeptanzkriterium 31: unbekannte `event_id`, unbekannter `category_key` und
        `after_rank >= partition_size` sind allesamt 200 mit leerer Liste, kein Fehler - und
        deshalb genau die Faelle, die ohne eigenen Testfall auch dann "bestehen", wenn der
        Endpunkt aus einem ganz anderen Grund nichts findet. Die Gegenprobe steht im ersten
        Testfall dieser Klasse: derselbe Aufbau liefert bei richtigen Schluesseln Eintraege."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        await self._partition(db_session, project, run, 3)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={
                "event_id": (await _default_event(db_session, run)).id + event_id_offset,
                "category_key": category_key,
                "after_rank": after_rank,
            },
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    async def test_unknown_project_returns_404(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        """Akzeptanzkriterium 32, erster Teil."""
        response = await authenticated_api_client.get(
            "/projects/9999/curation-candidates",
            params={"event_id": 1, "category_key": "landschaft"},
        )

        assert response.status_code == 404

    async def test_requires_authentication(
        self, api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 32, zweiter Teil, und Security-Muss-Kriterium 2 der Spec:
        `api/photos.py` verzichtet bewusst auf eine Router-weite Auth-Dependency (Kopfkommentar
        der Datei) - ein neuer Endpunkt, der `Depends(get_current_user)` vergisst, ist STILL
        OEFFENTLICH: kein Fehler, keine 401, nur Daten. Genau dagegen steht dieser Testfall."""
        project = await _make_project(db_session)

        response = await api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={"event_id": 1, "category_key": "landschaft"},
        )

        assert response.status_code == 401

    async def test_keys_of_another_project_return_nothing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 32, dritter Teil, und Security-Muss-Kriterium 2 der Spec:
        `PhotoRanking` traegt keine `project_id`. Die einzige Projektbindung ist
        `criterion_scoring_run_id`, abgeleitet aus dem PFADPARAMETER."""
        own = await _make_project(db_session, name="Eigenes")
        foreign = await _make_project(db_session, name="Fremdes")
        own_run = await _make_criterion_scoring_run(db_session, own)
        foreign_run = await _make_criterion_scoring_run(db_session, foreign)
        # Beide Projekte tragen denselben `category_key`.
        await self._partition(db_session, own, own_run, 2)
        foreign_photos = await self._partition(db_session, foreign, foreign_run, 4)

        # Bewusst die Event-Id des FREMDEN Laufs: sie ist ein globaler Surrogatschluessel und
        # identifiziert unter `/projects/{eigenes}/...` eindeutig fremde Rangzeilen.
        response = await authenticated_api_client.get(
            f"/projects/{own.id}/curation-candidates",
            params={
                "event_id": (await _default_event(db_session, foreign_run)).id,
                "category_key": "landschaft",
                "after_rank": 1,
            },
        )

        body = response.json()
        assert {item["id"] for item in body["items"]}.isdisjoint({p.id for p in foreign_photos})
        # Die Zaehlabfrage hinter `total` traegt dasselbe Praedikat - sonst spiegelte sie die
        # Groesse der Fremdpartition zurueck.
        assert body == {"items": [], "total": 0}

    async def test_only_the_latest_successful_run_is_the_reference(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 33: ein aelterer Lauf mit abweichenden Raengen wirkt sich nicht
        aus - Bezugslauf ist derselbe wie in der Hauptabfrage."""
        project = await _make_project(db_session)
        old_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 1, 1, tzinfo=UTC)
        )
        new_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2024, 1, 1, tzinfo=UTC)
        )
        taken_at = datetime(2023, 1, 1, tzinfo=UTC)
        photos = [
            await _make_photo(db_session, project, f"p{index}.jpg", taken_at) for index in range(4)
        ]
        # Derselbe Partitionsschluessel in beiden Laeufen, mit ABWEICHENDEN Raengen: der aeltere
        # Lauf fuehrt die ersten beiden Fotos, der neuere die letzten beiden.
        for run, (first, second) in ((old_run, photos[:2]), (new_run, photos[2:])):
            for position, photo in enumerate((first, second), start=1):
                await _add_ranking(
                    db_session,
                    run,
                    photo,
                    category_key="landschaft",
                    rank_score=1.0 - position / 10,
                    rank_position=position,
                )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={
                "event_id": (await _default_event(db_session, run)).id,
                "category_key": "landschaft",
                "after_rank": 1,
            },
        )

        body = response.json()
        assert [item["id"] for item in body["items"]] == [photos[3].id]
        # `total` kommt aus der Partitionsgroesse - auch sie zaehlt nur den neuen Lauf.
        assert body["total"] == 1

    @pytest.mark.parametrize(
        "params",
        [
            pytest.param({"after_rank": -1}, id="negatives-after_rank"),
            pytest.param({"after_rank": 2**63}, id="after_rank-jenseits-der-obergrenze"),
            pytest.param({"offset": -1}, id="negatives-offset"),
            pytest.param({"offset": 2**63}, id="offset-jenseits-der-obergrenze"),
            pytest.param({"limit": 0}, id="limit-unter-der-untergrenze"),
            pytest.param({"limit": 201}, id="limit-ueber-der-obergrenze"),
            pytest.param({"event_id": 0}, id="event_id-unter-der-untergrenze"),
            pytest.param({"event_id": 2**63}, id="event_id-jenseits-der-obergrenze"),
            pytest.param({"category_key": "x" * 300}, id="category_key-zu-lang"),
        ],
    )
    async def test_rejects_query_parameters_outside_their_bounds(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        params: dict[str, object],
    ) -> None:
        """Security-Punkte 3 und 4 der Spec: `limit` wie im Standard-Listing (`ge=1, le=200`),
        `after_rank`/`offset`/`event_id` mit Unter- UND Obergrenze (ein Pydantic-`int` ist
        unbeschraenkt und landet direkt im SQL-Vergleich; unter SQLite wirft ein Wert jenseits von
        2^63 einen `OverflowError` und damit eine 500 statt einer leeren Liste), dazu eine
        `max_length` auf dem verbliebenen freien Schluesselparameter."""
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={"event_id": 1, "category_key": "landschaft", **params},
        )

        assert response.status_code == 422

    async def test_requires_both_partition_keys(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Beide Schluessel sind pflichtig - ohne sie ist gar keine Partition adressiert, und ein
        Default waere eine stille Auswahl irgendeiner."""
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(f"/projects/{project.id}/curation-candidates")

        assert response.status_code == 422


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

    async def test_remote_category_result_comes_from_the_classification_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/features/0289-feste-kategorien.md: das Erfolgssignal der Remote-Phase ist seit
        # dieser Spec die PRAESENZ der 1:1-Klassifikations-Zeile (vorher: mindestens eine
        # Feinlabel-Zeile, deren computed_at defensiv per max() gewaehlt wurde) - `attempted_at`
        # ist damit eindeutig, ohne Aggregation ueber mehrere Zeilen.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="tier",
                detected_categories=["tier"],
                provider="anthropic",
                computed_at=datetime(2023, 6, 1, tzinfo=UTC),
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
        assert entry["attempted_at"].startswith("2023-06-01")

    async def test_remote_category_result_also_for_a_photo_without_any_fine_label(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Ein Foto, fuer das das Modell nichts Bekanntes nennen konnte, ist trotzdem erfolgreich
        # verarbeitet - es darf nicht weiterhin als "noch nicht gelaufen" erscheinen.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="nicht_erkannt",
                detected_categories=[],
                provider="anthropic",
                computed_at=datetime(2023, 6, 1, tzinfo=UTC),
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
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="tier",
                detected_categories=["tier"],
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
    """specs/features/0055, auf das feste Set umgestellt in specs/features/0289-feste-
    kategorien.md: `PhotoOut.fine_labels`/`remote_category`/`category_override`/
    `category_candidates`."""

    async def test_fine_labels_is_an_empty_list_when_none_exist(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        item = response.json()["items"][0]
        # Leere Liste, nicht null (analog `ratings`/`criterion_scores`).
        assert item["fine_labels"] == []
        assert item["remote_category"] is None
        assert item["category_override"] is None
        assert item["category_candidates"] == []

    async def test_the_old_remote_category_labels_field_is_gone(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Feld-UMBENENNUNG, nicht Ergaenzung: ein Client, der noch das alte Feld liest, soll das
        # sofort merken statt still eine leere Liste zu bekommen.
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert "remote_category_labels" not in response.json()["items"][0]

    async def test_fine_labels_reflect_the_persisted_rows_without_a_confidence_field(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        label = FineLabel(canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0])
        db_session.add(label)
        await db_session.flush()
        db_session.add(
            PhotoFineLabel(
                photo_id=photo.id,
                fine_label_id=label.id,
                raw_label="Hund",
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["fine_labels"] == [
            {
                "canonical_key": "hund",
                "display_name": "Hund",
                "raw_label": "Hund",
                "provider": "anthropic",
            }
        ]

    async def test_remote_category_and_candidates_come_from_the_classification_row(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="tier",
                detected_categories=["tier", "landschaft"],
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        item = response.json()["items"][0]
        assert item["remote_category"] == "tier"
        assert item["category_candidates"] == [
            {
                "category_key": "tier",
                "origin": "remote",
                "provider": "anthropic",
                "confidence": None,
            },
            {
                "category_key": "landschaft",
                "origin": "remote",
                "provider": "anthropic",
                "confidence": None,
            },
        ]

    async def test_candidates_no_longer_carry_a_score_field(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Negative Assertion auf die SCHLUESSELMENGE (nicht nur auf die Werte): die Auswahl
        # entscheidet seit Spec 0289 die feste Vorrangreihenfolge, ein angezeigter Zahlenwert ohne
        # Wirkung waere irrefuehrend.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="tier",
                detected_categories=["tier"],
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        candidate = response.json()["items"][0]["category_candidates"][0]
        # `confidence` ist seit specs/features/0299-kategorie-konfidenz-anzeigen.md dazugekommen -
        # es ist ausdruecklich KEINE Wiederkehr von `score`: die Zahl beeinflusst keine Auswahl
        # und keine Sortierung, sie ist die Selbsteinschaetzung des Modells (ADR 0067 Punkt 1).
        assert set(candidate) == {"category_key", "origin", "provider", "confidence"}
        assert "score" not in candidate

    async def test_local_qualifying_criterion_becomes_a_set_category_candidate(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # `content_people` bildet ueber LOCAL_CATEGORY_SIGNALS den Set-Key `menschen` - nicht mehr
        # den frueheren, generisch aus dem Kriterien-Key abgeleiteten Wert "people".
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

        assert response.json()["items"][0]["category_candidates"] == [
            {
                "category_key": "menschen",
                "origin": "local",
                "provider": None,
                "confidence": None,
            }
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
                category_override="sport_aktivitaet",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["category_override"] == "sport_aktivitaet"

    async def test_the_read_path_tolerates_a_legacy_override_outside_the_set(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Defense in Depth (Security-Abschnitt der Spec 0289, Punkt 2): der SCHREIBpfad ist ab
        dieser Spec geschlossen, der Datenbestand erst nach Migrationsschritt (d) - ein Altwert
        ausserhalb des Sets darf im Lesepfad keinen 500er erzeugen, sondern wird unveraendert
        durchgereicht (das Frontend stellt ihn ueber seinen generischen Fallback dar)."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=1.0,
                exposure=0.0,
                category_override="unerkannt",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.status_code == 200
        assert response.json()["items"][0]["category_override"] == "unerkannt"

    async def test_candidates_are_sorted_in_registry_display_order(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # `menschen` steht in der Anzeigereihenfolge der Registry vor `landschaft` - unabhaengig
        # von der Reihenfolge, in der die Kandidaten entstanden sind.
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
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="landschaft",
                detected_categories=["landschaft"],
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        candidates = response.json()["items"][0]["category_candidates"]
        assert [c["category_key"] for c in candidates] == ["menschen", "landschaft"]

    async def test_a_key_that_is_both_local_and_remote_appears_once_as_local(
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
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="menschen",
                detected_categories=["menschen"],
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["category_candidates"] == [
            {
                "category_key": "menschen",
                "origin": "local",
                "provider": None,
                "confidence": None,
            }
        ]


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
        assert items[first.id]["rankings"] == [
            {
                "event_id": (await _default_event(db_session, run)).id,
                "category_key": "landscape",
                "rank_score": 0.9,
                "rank_position": 1,
                "partition_size": 2,
                "is_primary": True,
                # Ohne angeforderte Auswahl traegt jede Zugehoerigkeit `null`
                # (specs/features/0300-nebenkategorien.md, Akzeptanzkriterium 23).
                "curation_position": None,
            }
        ]
        assert items[second.id]["rankings"][0]["rank_position"] == 2

    async def test_default_listing_rankings_are_empty_without_criterion_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """specs/features/0300-nebenkategorien.md: `rankings` ist eine LEERE LISTE, nie `null` -
        analog `ratings`. Der Client muss keinen zweiten Leerzustand unterscheiden."""
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["rankings"] == []

    async def test_partition_size_is_isolated_per_project_in_default_listing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Security-Review-Fund: kein dedizierter Cross-Project-Isolationstest fuer den neuen,
        # im Default-Listing-Zweig befuellten partition_size/RankingOut-Pfad - beide Projekte
        # nutzen absichtlich denselben `category_key` ("landscape"),
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
        assert item["rankings"][0]["partition_size"] == 1


class TestMultipleCategoryMemberships:
    """specs/features/0300-nebenkategorien.md, Umsetzungsschritt 6: aus `PhotoOut.ranking` wird
    `PhotoOut.rankings`. Jede Lesestelle bekommt eine Vorbedingung mit MEHREREN Zeilen je Foto -
    das ist die eigentliche Bug-Klasse dieser Story (`scalar_one_or_none()` wirft ab der zweiten
    Zeile, ein `dict[photo_id, ...]` verliert still)."""

    async def test_rankings_list_the_primary_row_first_then_registry_display_order(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Festgelegte Reihenfolge (ADR 0069 Punkt 7): sonst flackerte die Anzeige mit der
        Zeilenreihenfolge der Datenbank. `tier` steht in der Registry VOR `landschaft`, die
        Hauptzeile `landschaft` trotzdem an erster Stelle."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        # Bewusst in "falscher" Reihenfolge angelegt.
        await _add_ranking(
            db_session,
            run,
            photo,
            category_key="tier",
            rank_score=0.9,
            rank_position=1,
            is_primary=False,
        )
        await _add_ranking(
            db_session,
            run,
            photo,
            category_key="menschen",
            rank_score=0.9,
            rank_position=1,
            is_primary=False,
        )
        await _add_ranking(
            db_session,
            run,
            photo,
            category_key="landschaft",
            rank_score=0.9,
            rank_position=1,
            is_primary=True,
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        [item] = response.json()["items"]
        assert [(r["category_key"], r["is_primary"]) for r in item["rankings"]] == [
            ("landschaft", True),
            ("menschen", False),
            ("tier", False),
        ]

    async def test_a_photo_in_two_partitions_appears_only_once_in_items(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 11: in der API kommt ein Foto trotz mehrerer Zugehoerigkeiten
        HOECHSTENS EINMAL in `items` vor - welche seiner Zugehoerigkeiten zur Auswahl gehoeren,
        steht an den einzelnen `rankings`-Eintraegen."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(
            db_session, run, photo, category_key="landschaft", rank_score=0.9, rank_position=1
        )
        await _add_ranking(
            db_session,
            run,
            photo,
            category_key="tier",
            rank_score=0.9,
            rank_position=1,
            is_primary=False,
        )

        for params in ({"top_n_per_category": 3}, {}):
            response = await authenticated_api_client.get(
                f"/projects/{project.id}/photos", params=params
            )
            ids = [item["id"] for item in response.json()["items"]]
            assert ids == [photo.id]
            assert len(ids) == len(set(ids))

        curated = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 3}
        )
        [item] = curated.json()["items"]
        assert {r["category_key"]: r["curation_position"] for r in item["rankings"]} == {
            "landschaft": 1,
            "tier": 1,
        }

    async def test_top_n_still_applies_per_partition(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 12: `top_n` wirkt unveraendert JE PARTITION, und das `row_number()`
        zaehlt Neben- wie Hauptzeilen mit."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        best = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        guest = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(
            db_session, run, best, category_key="landschaft", rank_score=0.9, rank_position=1
        )
        # Der Gast steht in `landschaft` NUR als Nebenkategorie - und belegt trotzdem einen der
        # angeforderten Plaetze.
        await _add_ranking(
            db_session,
            run,
            guest,
            category_key="landschaft",
            rank_score=0.5,
            rank_position=2,
            is_primary=False,
        )
        await _add_ranking(
            db_session, run, guest, category_key="tier", rank_score=0.5, rank_position=1
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 1}
        )

        rankings_by_photo = {
            item["id"]: {r["category_key"]: r["curation_position"] for r in item["rankings"]}
            for item in response.json()["items"]
        }
        # `landschaft` liefert genau EINEN Vorschlag - der Gast auf Platz 2 faellt heraus, seine
        # eigene Hauptkategorie bleibt davon unberuehrt.
        assert rankings_by_photo[best.id] == {"landschaft": 1}
        assert rankings_by_photo[guest.id] == {"landschaft": None, "tier": 1}

    async def test_curation_position_is_null_or_equal_to_rank_position(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Gegenteil-Test des frueheren `test_curation_position_is_smaller_than_rank_position_
        behind_a_rejected_photo` (specs/features/0357-voller-bildvorrat-kuratierung.md, ADR 0071
        Entscheidung 2): derselbe Aufbau - ein verworfenes Foto auf Platz 1 - mit der
        Zusammenfall-Invariante als Erwartung.

        `curation_position` ist ab hier ENTWEDER `null` ODER gleich `rank_position`; ihre
        verbliebene Aufgabe ist allein die Unterscheidung "gehoert diese Zugehoerigkeit zur
        Auswahl?". Die Invariante ist als Testfall notwendig, damit die naechste Aenderung die
        Redundanz nicht als Fehler liest und das falsche der beiden Felder entfernt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        first = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        second = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(db_session, run, first, rank_score=0.9, rank_position=1)
        await _add_ranking(db_session, run, second, rank_score=0.5, rank_position=2)

        await authenticated_api_client.put(
            f"/photos/{first.id}/rating", json={"status": "rejected"}
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 1}
        )

        items = response.json()["items"]
        rankings = [ranking for item in items for ranking in item["rankings"]]
        assert rankings != []
        for ranking in rankings:
            assert ranking["curation_position"] in (None, ranking["rank_position"])

        # Auch hinter dem verworfenen Foto: es bleibt Platz 1 der Auswahl, das zweite Foto
        # rueckt NICHT auf Platz 1 nach und faellt bei `top_n=1` schlicht heraus.
        by_photo = {item["id"]: item["rankings"][0]["curation_position"] for item in items}
        assert by_photo == {first.id: 1}

    async def test_partition_size_counts_secondary_rows_too(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 16, zweite Haelfte: die Partitionsgroesse ("von N" im Popover) zaehlt
        ALLE Zeilen der Partition - dort steht ein Foto mit Nebenzugehoerigkeit tatsaechlich."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        owner = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        guest = await _make_photo(db_session, project, "b.jpg", datetime(2023, 1, 2, tzinfo=UTC))
        await _add_ranking(
            db_session, run, owner, category_key="landschaft", rank_score=0.9, rank_position=1
        )
        await _add_ranking(
            db_session, run, guest, category_key="tier", rank_score=0.5, rank_position=1
        )
        await _add_ranking(
            db_session,
            run,
            guest,
            category_key="landschaft",
            rank_score=0.5,
            rank_position=2,
            is_primary=False,
        )

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        items = {item["id"]: item for item in response.json()["items"]}
        sizes = {r["category_key"]: r["partition_size"] for r in items[guest.id]["rankings"]}
        assert sizes == {"tier": 1, "landschaft": 2}


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


class TestCategoryConfidenceFields:
    """specs/features/0299-kategorie-konfidenz-anzeigen.md, Umsetzungsschritt 4:
    `CategoryCandidateOut.confidence` und `PhotoOut.category_confidence`."""

    async def test_a_candidate_carries_the_model_confidence_for_its_key(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="tier",
                detected_categories=["tier", "landschaft"],
                detected_category_confidences={"tier": 0.92, "landschaft": 0.41},
                category_confidence=0.92,
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        item = response.json()["items"][0]
        assert item["category_candidates"] == [
            {
                "category_key": "tier",
                "origin": "remote",
                "provider": "anthropic",
                "confidence": 0.92,
            },
            {
                "category_key": "landschaft",
                "origin": "remote",
                "provider": "anthropic",
                "confidence": 0.41,
            },
        ]
        assert item["category_confidence"] == 0.92

    async def test_a_candidate_without_a_model_number_carries_null_not_zero(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="tier",
                detected_categories=["tier", "landschaft"],
                detected_category_confidences={"tier": 0.5},
                category_confidence=0.5,
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        candidates = response.json()["items"][0]["category_candidates"]
        landschaft = next(c for c in candidates if c["category_key"] == "landschaft")
        assert landschaft["confidence"] is None

    async def test_a_purely_local_candidate_has_no_number(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 8: `null`, nie `0.0` - es gibt zu diesem Schluessel gar keine
        Modellaussage."""
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

        item = response.json()["items"][0]
        assert item["category_candidates"] == [
            {
                "category_key": "menschen",
                "origin": "local",
                "provider": None,
                "confidence": None,
            }
        ]
        assert item["category_confidence"] is None

    async def test_the_number_follows_the_key_not_the_origin_label(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 8, zweite Haelfte / ADR 0067 Punkt 2: ein Schluessel, den ein lokales
        Signal UND das Modell nennen, erscheint als `origin="local"` (die spezifischere
        Herkunftsaussage) - behaelt aber die Modellzahl, denn es GIBT eine Modellaussage zu diesem
        Schluessel."""
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
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="menschen",
                detected_categories=["menschen"],
                detected_category_confidences={"menschen": 0.77},
                category_confidence=0.77,
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["category_candidates"] == [
            {
                "category_key": "menschen",
                "origin": "local",
                "provider": None,
                "confidence": 0.77,
            }
        ]

    async def test_zero_is_delivered_as_zero_not_as_null(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="tier",
                detected_categories=["tier"],
                detected_category_confidences={"tier": 0.0},
                category_confidence=0.0,
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        item = response.json()["items"][0]
        assert item["category_confidence"] == 0.0
        assert item["category_confidence"] is not None
        assert item["category_candidates"][0]["confidence"] == 0.0

    async def test_an_old_row_without_confidences_delivers_null_everywhere(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium 9: eine Zeile aus der Zeit vor der Migration traegt `NULL` - der
        Lesepfad braucht dafuer keine Sonderbehandlung."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key="tier",
                detected_categories=["tier"],
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        item = response.json()["items"][0]
        assert item["category_confidence"] is None
        assert item["category_candidates"][0]["confidence"] is None

    async def test_category_confidence_is_the_number_of_the_remote_category(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Eigenes Feld statt clientseitiger Ableitung aus der Kandidatenliste: `remote_category`
        kann `nicht_erkannt` sein und steht dann gar nicht in `detected_categories`."""
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        db_session.add(
            PhotoCategoryClassification(
                photo_id=photo.id,
                category_key=CATEGORY_NOT_RECOGNIZED,
                detected_categories=[],
                detected_category_confidences={},
                category_confidence=None,
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        item = response.json()["items"][0]
        assert item["remote_category"] == CATEGORY_NOT_RECOGNIZED
        assert item["category_confidence"] is None
        assert item["category_candidates"] == []

    async def test_a_photo_without_any_classification_row_has_no_number(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _make_photo(db_session, project, "a.jpg", datetime(2023, 1, 1, tzinfo=UTC))

        response = await authenticated_api_client.get(f"/projects/{project.id}/photos")

        assert response.json()["items"][0]["category_confidence"] is None


# ---------------------------------------------------------------------------------------------
# specs/features/0051-gps-landmark-cluster-bildung.md, ADR 0072 Entscheidung 1/7: ZWEI additive
# Antwortfelder, beide zur Anfragezeit ueber den VOLLSTAENDIGEN Cluster des Bezugslaufs berechnet
# und nirgends persistiert.
#
# `PhotoOut.location`      - der Ort DIESES Fotos, volle EXIF-Praezision, `source` "exif"/"derived"
# `PhotoOut.cluster_place` - der bereits AUFGELOESTE Ort des CLUSTERS, auf jedem Foto desselben
#                            Clusters identisch, gerundete Koordinate bzw. Sehenswuerdigkeit-Name
#
# Die Bezugsmenge ist ausdruecklich NICHT die Antwort: die Kuratierungsansicht liefert je Partition
# nur `rank_position <= topN`, die nachgeladenen Kandidaten laufen ueber eine eigene Abfrage und
# fliessen nie zurueck. Eine Herleitung ueber die Fotos der Antwort waere nicht "springend",
# sondern DAUERHAFT falsch.


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
        """Ein Event mit 11 Fotos, dessen tragendes Foto auf `rank_position` 11 liegt - also
        ausserhalb jeder realistischen Top-N-Antwort."""
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
            )
        anchor = await _make_photo_at(
            db_session, project, "anchor.jpg", base + timedelta(minutes=11), gps=anchor_gps
        )
        await _add_ranking(
            db_session, run, anchor, event=event_row, rank_score=0.01, rank_position=11
        )
        return project, run, anchor

    async def test_the_only_coordinate_reaches_photos_that_outrank_it(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """ROT-ANKER: das EINZIGE koordinatentragende Foto liegt auf Rang 11, abgefragt wird mit
        `top_n_per_category=3`. Eine Herleitung ueber die Fotos der Antwort lieferte hier `null`."""
        project, _run, _anchor = await self._seed_event_with_a_deep_anchor(
            db_session, anchor_gps=_EIFFEL
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 3}
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

    async def test_both_fields_are_field_equal_across_photos_and_curation_candidates(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Der direkte "springt nicht"-Nachweis: dasselbe Foto einmal ueber das Standard-Listing
        und einmal ueber den Nachlade-Endpunkt."""
        project, run, anchor = await self._seed_event_with_a_deep_anchor(
            db_session, anchor_gps=_LOUVRE, shallow_gps=_EIFFEL
        )
        event_row = await _default_event(db_session, run)

        listing = await authenticated_api_client.get(f"/projects/{project.id}/photos")
        candidates = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={
                "event_id": event_row.id,
                "category_key": "landscape",
                "after_rank": 10,
            },
        )

        assert candidates.status_code == 200
        from_listing = {item["id"]: item for item in listing.json()["items"]}[anchor.id]
        [from_candidates] = candidates.json()["items"]
        assert from_candidates["id"] == anchor.id
        assert from_candidates["location"] == from_listing["location"]
        assert from_candidates["event"] == from_listing["event"]

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
            for ranking in item["rankings"]:
                events_by_id.setdefault(ranking["event_id"], []).append(item["event"])
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
        curation = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 1}
        )

        assert listing.json()["items"][0]["event"] == curation.json()["items"][0]["event"]

    async def test_the_event_does_not_depend_on_the_requested_top_n(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nummer und Zeitspanne stehen im Event, nicht in einer Aggregation ueber die sichtbaren
        Fotos - `top_n_per_category=1` und `=10` liefern denselben Wert."""
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
                db_session, run, photo, event=event_row, rank_score=0.9, rank_position=index + 1
            )

        narrow = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 1}
        )
        wide = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 10}
        )

        assert narrow.json()["items"][0]["event"] == wide.json()["items"][0]["event"]

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

        [ranking] = response.json()["items"][0]["rankings"]
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


class TestCurationCandidatesEventId:
    """Der Query-Parameter wird von einem Freitextschluessel zu einer Objekt-Id."""

    async def _setup(
        self, db_session: AsyncSession, *, photos: int = 3
    ) -> tuple[Project, CriterionScoringRun, Event]:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        event_row = await _make_event(db_session, run, position=1)
        for index in range(photos):
            photo = await _make_photo(
                db_session, project, f"{index}.jpg", datetime(2023, 1, 1, 10, index, tzinfo=UTC)
            )
            await _add_ranking(
                db_session,
                run,
                photo,
                event=event_row,
                category_key="landschaft",
                rank_score=1.0 - index / 10,
                rank_position=index + 1,
            )
        return project, run, event_row

    async def test_the_partition_is_addressed_by_event_id(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project, _run, event_row = await self._setup(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={
                "event_id": event_row.id,
                "category_key": "landschaft",
                "after_rank": 1,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    @pytest.mark.parametrize(
        "event_id",
        [pytest.param(0, id="null"), pytest.param(-1, id="negativ")],
    )
    async def test_an_event_id_below_one_is_rejected(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        event_id: int,
    ) -> None:
        """SICHERHEIT (M3): `ge=1` plus Typpruefung ist enger als die frueheren `max_length=200`
        eines Freitextschluessels."""
        project, _run, _event = await self._setup(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={"event_id": event_id, "category_key": "landschaft"},
        )

        assert response.status_code == 422

    async def test_a_non_numeric_event_id_is_rejected(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project, _run, _event = await self._setup(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={"event_id": "cluster-0", "category_key": "landschaft"},
        )

        assert response.status_code == 422

    async def test_an_event_id_beyond_the_upper_bound_is_rejected(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT (M3): ohne Obergrenze erzeugte ein Wert jenseits von 2^63 unter SQLite einen
        `OverflowError` und damit eine 500 statt einer leeren Liste."""
        project, _run, _event = await self._setup(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={"event_id": 2**63 + 1, "category_key": "landschaft"},
        )

        assert response.status_code == 422

    async def test_an_event_id_of_a_foreign_project_yields_nothing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """SICHERHEIT (M1): Akzeptanzkriterium der Spec - `items: []` UND `total: 0`, und keine
        Rueckspiegelung des uebergebenen Werts."""
        foreign_project = await _make_project(db_session, name="Fremd")
        foreign_run = await _make_criterion_scoring_run(db_session, foreign_project)
        foreign_event = await _make_event(db_session, foreign_run, position=1)
        for index in range(3):
            photo = await _make_photo(
                db_session,
                foreign_project,
                f"f{index}.jpg",
                datetime(2023, 1, 1, 10, index, tzinfo=UTC),
            )
            await _add_ranking(
                db_session,
                foreign_run,
                photo,
                event=foreign_event,
                category_key="landschaft",
                rank_score=0.9,
                rank_position=index + 1,
            )
        project, _run, _event = await self._setup(db_session)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={"event_id": foreign_event.id, "category_key": "landschaft"},
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}

    async def test_an_event_id_of_an_older_run_yields_nothing(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        older_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2023, 1, 1, tzinfo=UTC)
        )
        older_event = await _make_event(db_session, older_run, position=1)
        photo = await _make_photo(db_session, project, "old.jpg", datetime(2023, 1, 1, tzinfo=UTC))
        await _add_ranking(
            db_session,
            older_run,
            photo,
            event=older_event,
            category_key="landschaft",
            rank_score=0.9,
            rank_position=1,
        )
        newer_run = await _make_criterion_scoring_run(
            db_session, project, started_at=datetime(2024, 1, 1, tzinfo=UTC)
        )
        newer_event = await _make_event(db_session, newer_run, position=1)
        newer_photo = await _make_photo(
            db_session, project, "new.jpg", datetime(2024, 1, 1, tzinfo=UTC)
        )
        await _add_ranking(
            db_session,
            newer_run,
            newer_photo,
            event=newer_event,
            category_key="landschaft",
            rank_score=0.9,
            rank_position=1,
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/curation-candidates",
            params={"event_id": older_event.id, "category_key": "landschaft"},
        )

        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0}


# ---------------------------------------------------------------------------------------------
# specs/features/0426-zeitversatz-je-kamera.md, Umsetzungsschritt 7: die drei neuen
# PhotoOut-Felder und der camera_id-Filter. `taken_at` liefert ab hier die KORRIGIERTE Zeit -
# derselbe Feldname, neue Bedeutung (ADR 0089, Punkt 1).


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
