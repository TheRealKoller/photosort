from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.categories import CATEGORY_NOT_RECOGNIZED, CATEGORY_REGISTRY
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCategoryClassification,
    PhotoCriterionScore,
    PhotoRanking,
    PhotoScore,
    Project,
    ScanStatus,
    ScoringRun,
)

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, Akzeptanzkriterium
# "Manuelle Übernahme (Override) mit sofortiger Wirkung" - mit specs/features/0289-feste-
# kategorien.md ausdrueckliche VERHALTENSUMKEHR: die frueher hier getesteten 409-Faelle
# ("category_key ist kein Kandidat dieses Fotos", "canonical_key eines ANDEREN Fotos") sind zu
# POSITIVEN Faellen umgeschrieben, nicht geloescht - sonst bliebe die Aufhebung der
# Kandidaten-Bindung untestiert, und eine Implementierung, die die alte Pruefung stehen laesst,
# fiele nicht auf. An ihre Stelle tritt die STAERKERE Whitelist gegen das geschlossene 13er-Set
# (422 statt 409).


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
    category_key: str = CATEGORY_NOT_RECOGNIZED,
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


async def _add_classification(session: AsyncSession, photo: Photo, *categories: str) -> None:
    session.add(
        PhotoCategoryClassification(
            photo_id=photo.id,
            category_key=categories[0] if categories else CATEGORY_NOT_RECOGNIZED,
            detected_categories=list(categories),
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await session.commit()


async def _add_content_people(session: AsyncSession, photo: Photo, value: float = 1.0) -> None:
    session.add(
        PhotoCriterionScore(
            photo_id=photo.id,
            criterion_key="content_people",
            value=value,
            source=CriterionSource.LOCAL_ML,
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
            "/photos/999/category-override", json={"category_key": "tier"}
        )
        assert response.status_code == 404

    async def test_returns_409_without_a_ranking_row_in_the_current_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "tier"}
        )

        assert response.status_code == 409

    async def test_a_photo_with_a_classification_but_no_ranking_row_still_returns_409(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Edge Case 11 der Spec 0289: die Klassifikations-Zeile ersetzt die Rangfolgen-Zeile nicht.
        project = await _make_project(db_session)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_classification(db_session, photo, "tier")

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "tier"}
        )

        assert response.status_code == 409

    async def test_accepts_a_set_key_that_is_not_a_candidate_for_this_photo(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """VERHALTENSUMKEHR (specs/features/0289-feste-kategorien.md): frueher `409`, jetzt `200` -
        die manuelle Uebersteuerung bietet alle 13 Eintraege an, UNABHAENGIG davon, was fuer dieses
        Foto erkannt wurde. Vorgaenger dieses Tests:
        test_returns_409_for_a_category_key_that_is_not_a_candidate_for_this_photo."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_ranking(db_session, run, photo)

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "kunst_kreatives"}
        )

        assert response.status_code == 200
        assert response.json() == {"photo_id": photo.id, "category_key": "kunst_kreatives"}
        ranking = (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.photo_id == photo.id)
            )
        ).scalar_one()
        assert ranking.category_key == "kunst_kreatives"

    async def test_accepts_a_set_key_that_was_only_detected_on_a_different_photo(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Vorgaenger: test_returns_409_for_a_canonical_key_detected_on_a_different_photo. Die
        frueher hier abgesicherte Cross-Photo-Isolation ist mit dem geschlossenen Set
        gegenstandslos geworden - ein Set-Key ist kein fremder Fotobezug, und die Whitelist ist
        strikt staerker als die abgeloeste foto-skopierte Existenzpruefung."""
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        other_photo = await _make_photo(db_session, project, "other.jpg")
        await _add_score(db_session, other_photo)
        await _add_classification(db_session, other_photo, "tier")

        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_ranking(db_session, run, photo)

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "tier"}
        )

        assert response.status_code == 200

    async def test_returns_422_for_a_key_outside_the_set(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_ranking(db_session, run, photo)

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "einhorn"}
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("legacy_key", ["unerkannt", "detail", "landscape", "people"])
    async def test_returns_422_for_a_legacy_key_from_the_run_history(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        legacy_key: str,
    ) -> None:
        # Benannter Fall der Spec (Edge Case 10): ein Altwert aus der Laufhistorie wird NICHT
        # stillschweigend akzeptiert.
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_ranking(db_session, run, photo)

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": legacy_key}
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("key", ["  tier", "tier  ", "TIER", "Tier"])
    async def test_does_not_normalize_the_incoming_key(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, key: str
    ) -> None:
        # Security-Muss-Kriterium (Spec 0289, Punkt 2): reine Mitgliedschaftspruefung, KEINE
        # Normalisierung (kein strip()/casefold()) - der Client schickt den Key exakt so zurueck,
        # wie GET /categories ihn geliefert hat.
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_ranking(db_session, run, photo)

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": key}
        )

        assert response.status_code == 422

    async def test_a_rejected_key_leaves_no_trace_in_the_database(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Die Pruefung greift VOR jeder Schreibaktion (Security-Abschnitt Punkt 2), nicht erst
        # beim Bauen der Antwort.
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_ranking(db_session, run, photo, category_key="tier")

        await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "einhorn"}
        )

        score = await db_session.get(PhotoScore, photo.id)
        assert score is not None
        assert score.category_override is None
        ranking = (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.photo_id == photo.id)
            )
        ).scalar_one()
        assert ranking.category_key == "tier"

    async def test_not_recognized_is_a_valid_override_value(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Akzeptanzkriterium: "Nicht erkannt" ist in der manuellen Override-Auswahl waehlbar.
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_ranking(db_session, run, photo, category_key="tier")

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override",
            json={"category_key": CATEGORY_NOT_RECOGNIZED},
        )

        assert response.status_code == 200
        score = await db_session.get(PhotoScore, photo.id)
        assert score is not None
        assert score.category_override == CATEGORY_NOT_RECOGNIZED

    @pytest.mark.parametrize("key", list(CATEGORY_REGISTRY))
    async def test_every_one_of_the_thirteen_set_entries_is_accepted(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession, key: str
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_ranking(db_session, run, photo, category_key="gegenstand")

        response = await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": key}
        )

        assert response.status_code == 200
        assert response.json()["category_key"] == key

    async def test_takes_effect_immediately_without_a_new_scoring_run(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo)
        await _add_ranking(db_session, run, photo, category_key=CATEGORY_NOT_RECOGNIZED)

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 5}
        )
        assert {item["ranking"]["category_key"] for item in response.json()["items"]} == {
            CATEGORY_NOT_RECOGNIZED
        }

        await authenticated_api_client.put(
            f"/photos/{photo.id}/category-override", json={"category_key": "tier"}
        )

        response = await authenticated_api_client.get(
            f"/projects/{project.id}/photos", params={"top_n_per_category": 5}
        )
        assert response.json()["items"][0]["ranking"]["category_key"] == "tier"


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

    async def test_clears_the_override_and_restores_the_derived_local_category(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Bestandstest, auf Set-Keys umgestellt: die Rekonstruktion nutzt DIESELBE Ableitung wie
        # der Lauf (worker.py::derive_photo_category) - `content_people` bildet `menschen`.
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo, category_override="kunst_kreatives")
        await _add_content_people(db_session, photo)
        await _add_ranking(db_session, run, photo, category_key="kunst_kreatives")

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
        assert ranking.category_key == "menschen"

    async def test_the_reconstruction_also_takes_the_remote_candidates_into_account(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Lokal `menschen`, remote `sport_aktivitaet` - die Rekonstruktion muss BEIDE Zulieferer
        # beruecksichtigen und ueber die Vorrangreihenfolge entscheiden (sport_aktivitaet gewinnt).
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo, category_override="gegenstand")
        await _add_content_people(db_session, photo)
        await _add_classification(db_session, photo, "sport_aktivitaet")
        await _add_ranking(db_session, run, photo, category_key="gegenstand")

        await authenticated_api_client.delete(f"/photos/{photo.id}/category-override")

        ranking = (
            await db_session.execute(
                select(PhotoRanking).where(PhotoRanking.photo_id == photo.id)
            )
        ).scalar_one()
        assert ranking.category_key == "sport_aktivitaet"

    async def test_reset_without_any_recognised_content_falls_back_to_not_recognized(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Ein verwaister Override auf einen Altwert, den die Ableitung nie mehr erzeugt
        # ("detail"), bleibt bis zur Ruecknahme bestehen - danach landet das Foto im expliziten
        # "nicht erkannt"-Zustand statt in einer erfundenen Kategorie.
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
        assert ranking.category_key == CATEGORY_NOT_RECOGNIZED

    async def test_is_idempotent_when_called_twice(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        run = await _make_criterion_scoring_run(db_session, project)
        photo = await _make_photo(db_session, project, "a.jpg")
        await _add_score(db_session, photo, category_override="tier")
        await _add_ranking(db_session, run, photo, category_key="tier")

        first = await authenticated_api_client.delete(f"/photos/{photo.id}/category-override")
        second = await authenticated_api_client.delete(f"/photos/{photo.id}/category-override")

        assert first.status_code == 204
        assert second.status_code == 204
