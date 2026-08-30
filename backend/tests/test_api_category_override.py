from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.criteria import CATEGORY_UNRECOGNIZED
from photosort.models import (
    CategoryLabel,
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCategoryDetection,
    PhotoCriterionScore,
    PhotoRanking,
    PhotoScore,
    Project,
    ScanStatus,
    ScoringRun,
)

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, Akzeptanzkriterium
# "Manuelle Übernahme (Override) mit sofortiger Wirkung".


async def _make_project(session: AsyncSession) -> Project:
    project = Project(name="Costa Rica", opencloud_drive_id="d", opencloud_path="/a")
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _make_photo(session: AsyncSession, project: Project, path: str) -> Photo:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag="etag",
        content_length=1,
        taken_at=now,
        last_modified=now,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _add_score(
    session: AsyncSession, photo: Photo, *, category_override: str | None = None
) -> PhotoScore:
    score = PhotoScore(
        photo_id=photo.id,
        sharpness=100.0,
        exposure=0.0,
        cluster_key="cluster-0",
        category_override=category_override,
        computed_at=datetime.now(UTC),
    )
    session.add(score)
    await session.commit()
    return score


async def _make_criterion_scoring_run(
    session: AsyncSession, project: Project
) -> CriterionScoringRun:
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.flush()
    run = CriterionScoringRun(
        project_id=project.id, scoring_run_id=scoring_run.id, status=ScanStatus.SUCCESS
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
    rank_score: float = 0.5,
    rank_position: int = 1,
) -> PhotoRanking:
    ranking = PhotoRanking(
        criterion_scoring_run_id=run.id,
        photo_id=photo.id,
        cluster_key=cluster_key,
        category_key=category_key,
        rank_score=rank_score,
        rank_position=rank_position,
    )
    session.add(ranking)
    await session.commit()
    await session.refresh(ranking)
    return ranking


async def _add_category_label(
    session: AsyncSession, *, canonical_key: str = "hund", display_name: str = "Hund"
) -> CategoryLabel:
    label = CategoryLabel(
        canonical_key=canonical_key, display_name=display_name, embedding=[1.0, 0.0]
    )
    session.add(label)
    await session.commit()
    await session.refresh(label)
    return label


async def _add_category_detection(
    session: AsyncSession, photo: Photo, label: CategoryLabel, *, confidence: float = 0.9
) -> None:
    session.add(
        PhotoCategoryDetection(
            photo_id=photo.id,
            category_label_id=label.id,
            raw_label=label.display_name,
            confidence=confidence,
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await session.commit()


class TestPutCategoryOverride:
    async def test_requires_auth(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.put("/photos/1/category-override", json={"category_key": "x"})
        assert response.status_code == 401

    async def test_returns_404_for_unknown_photo(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.put(
            "/photos/999/category-override", json={"category_key": "hund"}
        )
        assert response.status_code == 404

    async def test_returns_409_without_a_ranking_row_in_the_current_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "hund"}
        )

        assert response.status_code == 409

    async def test_returns_409_for_a_category_key_that_is_not_a_candidate_for_this_photo(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_ranking(db_session, run, photo)

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "unbekannt"}
        )

        assert response.status_code == 409

    async def test_returns_409_for_a_canonical_key_detected_on_a_different_photo(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Security-Muss-Kriterium (Spec-Abschnitt Security, Punkt 3): Cross-Photo-Isolation - ein
        canonical_key, der real existiert (fuer ein ANDERES Foto erkannt), aber fuer DIESES Foto
        keine photo_category_detections-Zeile hat, wird trotzdem abgelehnt."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        label = await _add_category_label(db_session)
        other_photo = await _make_photo(db_session, project, "other.jpg")
        await _add_score(db_session, other_photo)
        await _add_category_detection(db_session, other_photo, label)

        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_ranking(db_session, run, photo)

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "hund"}
        )

        assert response.status_code == 409

    async def test_accepts_a_remote_canonical_key_detected_on_this_photo(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        label = await _add_category_label(db_session)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_category_detection(db_session, photo, label)
        await _add_ranking(db_session, run, photo, category_key=CATEGORY_UNRECOGNIZED)

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "hund"}
        )

        assert response.status_code == 200
        assert response.json() == {"photo_id": photo.id, "category_key": "hund"}

        ranking = (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.photo_id == photo.id)
            )
        ).scalar_one()
        assert ranking.category_key == "hund"

        score = await db_session.get(PhotoScore, photo.id)
        assert score is not None
        assert score.category_override == "hund"

    async def test_accepts_a_locally_qualifying_criterion_key(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="content_people",
                value=1.0,
                source=CriterionSource.LOCAL_ML,
                computed_at=datetime.now(UTC),
            )
        )
        await db_session.commit()
        await _add_ranking(db_session, run, photo, category_key=CATEGORY_UNRECOGNIZED)

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "people"}
        )

        assert response.status_code == 200
        assert response.json()["category_key"] == "people"

    async def test_takes_effect_immediately_without_a_new_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        label = await _add_category_label(db_session)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_category_detection(db_session, photo, label)
        await _add_ranking(db_session, run, photo, category_key=CATEGORY_UNRECOGNIZED)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 5}
        )
        assert {item["ranking"]["category_key"] for item in response.json()["items"]} == {
            CATEGORY_UNRECOGNIZED
        }

        await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "hund"}
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 5}
        )
        assert response.json()["items"][0]["ranking"]["category_key"] == "hund"


class TestDeleteCategoryOverride:
    async def test_requires_auth(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.delete("/photos/1/category-override")
        assert response.status_code == 401

    async def test_returns_404_for_unknown_photo(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.delete("/photos/999/category-override")
        assert response.status_code == 404

    async def test_is_idempotent_without_an_active_override(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)

        response = await authenticated_api_client.delete(f"/photos/{photo.id}/category-override")

        assert response.status_code == 204

    async def test_clears_the_override_and_restores_the_automatically_derived_category(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo, category_override="hund")
        db_session.add(
            PhotoCriterionScore(
                photo_id=photo.id,
                criterion_key="content_people",
                value=1.0,
                source=CriterionSource.LOCAL_ML,
                computed_at=datetime.now(UTC),
            )
        )
        await db_session.commit()
        # Override wurde bereits auf "hund" gesetzt - die zugehoerige PhotoRanking-Zeile
        # widerspiegelt das (wie nach einem echten PUT-Aufruf).
        await _add_ranking(db_session, run, photo, category_key="hund")

        response = await authenticated_api_client.delete(f"/photos/{photo.id}/category-override")

        assert response.status_code == 204

        score = await db_session.get(PhotoScore, photo.id)
        assert score is not None
        assert score.category_override is None

        ranking = (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.photo_id == photo.id)
            )
        ).scalar_one()
        # content_people ist bei EINEM Kandidaten automatisch aktiv (100% Praesenz) -> "people".
        assert ranking.category_key == "people"

    async def test_reset_without_any_recognised_content_falls_back_to_unrecognized(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # specs/features/0217 AK5/AK9: ein verwaister Override auf einen Wert, den die Ableitung
        # nie mehr erzeugt ("detail"), bleibt bis zur Ruecknahme bestehen - danach landet das Foto
        # im expliziten "nicht erkannt"-Zustand statt in einer erfundenen Kategorie.
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo, category_override="detail")
        await _add_ranking(db_session, run, photo, category_key="detail")

        before = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 5}
        )
        assert {item["ranking"]["category_key"] for item in before.json()["items"]} == {"detail"}

        response = await authenticated_api_client.delete(f"/photos/{photo.id}/category-override")

        assert response.status_code == 204
        ranking = (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.photo_id == photo.id)
            )
        ).scalar_one()
        assert ranking.category_key == CATEGORY_UNRECOGNIZED

    async def test_is_idempotent_when_called_twice(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo, category_override="hund")
        await _add_ranking(db_session, run, photo, category_key="hund")

        first = await authenticated_api_client.delete(f"/photos/{photo.id}/category-override")
        second = await authenticated_api_client.delete(f"/photos/{photo.id}/category-override")

        assert first.status_code == 204
        assert second.status_code == 204
