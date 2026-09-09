from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_opencloud_client
from photosort.cloud_vision import VISION_MODELS_BY_PROVIDER
from photosort.config import settings
from photosort.main import app
from photosort.models import (
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCategoryClassification,
    PhotoCriterionScore,
    PhotoScore,
    RatingStatus,
    ScanStatus,
    ScoringRun,
)
from photosort.opencloud.client import Drive, OpenCloudError
from photosort.opencloud.webdav_xml import DavEntry
from photosort.pricing import estimate_usd_per_image

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, Akzeptanzkriterium
# "Kostenschätzung", fortgeschrieben von specs/features/0296-klassifizierung-ein-ausloeser-cloud-
# checkbox.md (ADR 0050 Punkt 5): die Schätzung deckt seither BEIDE Cloud-Anteile ab, die die
# Checkbox am Auslöser freigibt — Kategorie-Klassifizierung UND Sehenswürdigkeits-Erkennung.
# Die Auslöse-Tests leben seit derselben Spec in test_api_criterion_scoring.py::TestClassify —
# es gibt nur noch einen Auslöser.


class FakeOpenCloudClient:
    def __init__(self, fail: OpenCloudError | None = None) -> None:
        self._fail = fail

    async def resolve_drive(self, name: str | None) -> Drive:
        if self._fail:
            raise self._fail
        return Drive(
            id="drive-1", name="Family", drive_type="project", webdav_url="https://x/dav/spaces/drive-1"
        )

    async def list_folder(self, webdav_url: str, path: str, depth: str = "1") -> list[DavEntry]:
        if self._fail:
            raise self._fail
        return []


async def _create_project(client: httpx.AsyncClient) -> int:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await client.post("/projects", json={"name": "Costa Rica", "opencloud_path": "A"})
    result: int = created.json()["id"]
    return result


async def _add_photo_candidate(
    session: AsyncSession, project_id: int, path: str, *, rejected: bool = False
) -> Photo:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    photo = Photo(
        project_id=project_id,
        relative_path=path,
        etag="etag",
        content_length=1,
        taken_at=now,
        last_modified=now,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=100.0,
            exposure=0.0,
            cluster_key="cluster-0",
            suggested_status=RatingStatus.REJECTED if rejected else None,
            computed_at=now,
        )
    )
    await session.commit()
    return photo


async def _add_classification_run(
    session: AsyncSession, project_id: int, status: ScanStatus = ScanStatus.SUCCESS
) -> CriterionScoringRun:
    """specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-
    vier-teilschritte-und-laufeigene-cloud-bilanz.md Punkt 7: der Landmark-Anteil der Schaetzung
    ist `null`, solange im Projekt KEIN erfolgreich abgeschlossener Klassifizierungslauf
    existiert. Ein Lauf ist damit die neue Vorbedingung jedes Testfalls, der eine Landmark-Zahl
    erwartet."""
    scoring_run = ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.commit()
    await session.refresh(scoring_run)
    run = CriterionScoringRun(
        project_id=project_id, scoring_run_id=scoring_run.id, status=status
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _add_criterion_score(
    session: AsyncSession, photo: Photo, criterion_key: str, value: float
) -> None:
    session.add(
        PhotoCriterionScore(
            photo_id=photo.id,
            criterion_key=criterion_key,
            value=value,
            source=CriterionSource.LOCAL_HEURISTIC,
            computed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
    )
    await session.commit()


class TestEstimateEndpoint:
    async def test_requires_auth(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.get("/projects/1/classify/estimate")
        assert response.status_code == 401

    async def test_returns_404_for_unknown_project(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.get(
            "/projects/999/classify/estimate"
        )
        assert response.status_code == 404

    async def test_zero_candidates_returns_200_with_zero_cost(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)

        response = await authenticated_api_client.get(
            f"/projects/{project_id}/classify/estimate"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["candidate_count"] == 0
        assert body["estimated_cost_usd"] == 0.0

    async def test_works_regardless_of_consent(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        # Consent bleibt deaktiviert (Default) - trotzdem 200, kein 403 (Akzeptanzkriterium).
        project_id = await _create_project(authenticated_api_client)

        response = await authenticated_api_client.get(
            f"/projects/{project_id}/classify/estimate"
        )

        assert response.status_code == 200

    async def test_counts_candidates_and_computes_the_cost(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_photo_candidate(db_session, project_id, "a.jpg")
        await _add_photo_candidate(db_session, project_id, "b.jpg")
        await _add_photo_candidate(db_session, project_id, "c.jpg", rejected=True)

        response = await authenticated_api_client.get(
            f"/projects/{project_id}/classify/estimate"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["candidate_count"] == 2
        assert body["remote_categories"]["candidate_count"] == 2
        # Spec 0348/ADR 0068 Punkt 7: ohne einen erfolgreich abgeschlossenen Lauf ist der
        # Landmark-Anteil `null` = "nicht verlaesslich schaetzbar", nicht `0`. Die frueher hier
        # stehende `0` behauptete Kostenfreiheit fuer einen Anteil, der gleich Geld kostet.
        assert body["landmark"]["candidate_count"] is None
        assert body["landmark"]["estimated_cost_usd"] is None
        assert body["provider"] == settings.landmark_provider
        assert body["model"] == settings.resolved_landmark_model()
        price = estimate_usd_per_image(
            settings.resolved_landmark_model(), settings.landmark_provider
        )
        assert price is not None
        assert body["price_per_image_usd"] == price
        assert body["estimated_cost_usd"] == 2 * price

    async def test_excludes_already_classified_photos_from_the_candidate_count(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        # Review-Fund (test-engineer): der "bereits klassifiziert"-Ausschluss
        # (_count_remote_category_candidates, api/projects.py) war bisher nur indirekt ueber den
        # Worker-Unit-Test (select_remote_category_candidates) abgedeckt, nicht auf API-Ebene.
        project_id = await _create_project(authenticated_api_client)
        candidate = await _add_photo_candidate(db_session, project_id, "a.jpg")
        already_classified = await _add_photo_candidate(db_session, project_id, "b.jpg")

        # specs/features/0289-feste-kategorien.md: "bereits klassifiziert" haengt seit dieser
        # Spec an der 1:1-Klassifikations-Zeile, nicht mehr an einer Feinlabel-Zeile.
        db_session.add(
            PhotoCategoryClassification(
                photo_id=already_classified.id,
                category_key="tier",
                detected_categories=["tier"],
                provider="anthropic",
                computed_at=datetime(2023, 1, 1, tzinfo=UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.get(
            f"/projects/{project_id}/classify/estimate"
        )

        assert response.status_code == 200
        assert response.json()["candidate_count"] == 1
        # Nur der noch nicht klassifizierte Kandidat zaehlt mit - reine Regressionsabsicherung
        # gegen ein versehentlich vertauschtes Filterkriterium.
        assert candidate.id != already_classified.id


class TestLandmarkShareOfTheEstimate:
    """specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, Akzeptanzkriterium
    "Die Schätzung umfasst alle Cloud-Anteile, die die Checkbox freigibt — nicht nur die
    Kategorie-Klassifizierung"."""

    async def test_counts_photos_over_the_landmark_threshold(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_classification_run(db_session, project_id)
        landmark_candidate = await _add_photo_candidate(db_session, project_id, "a.jpg")
        await _add_criterion_score(db_session, landmark_candidate, "landschaft", 1.0)
        below_threshold = await _add_photo_candidate(db_session, project_id, "b.jpg")
        await _add_criterion_score(db_session, below_threshold, "landschaft", 0.0)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["landmark"]["candidate_count"] == 1
        assert body["remote_categories"]["candidate_count"] == 2
        assert body["candidate_count"] == 3
        price = estimate_usd_per_image(
            settings.resolved_landmark_model(), settings.landmark_provider
        )
        assert price is not None
        assert body["estimated_cost_usd"] == 3 * price

    async def test_a_building_photo_is_a_landmark_candidate_too(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_classification_run(db_session, project_id)
        photo = await _add_photo_candidate(db_session, project_id, "a.jpg")
        await _add_criterion_score(db_session, photo, "gebaeude", 1.0)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["landmark"]["candidate_count"] == 1

    async def test_excludes_photos_that_already_have_a_landmark_score(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Dieselbe Skip-Regel wie im Live-Lauf (worker.py::_select_landmark_candidates): ein
        bereits gescortes Foto wird kein zweites Mal an die Cloud geschickt und darf die
        Schaetzung deshalb auch nicht erhoehen."""
        project_id = await _create_project(authenticated_api_client)
        await _add_classification_run(db_session, project_id)
        photo = await _add_photo_candidate(db_session, project_id, "a.jpg")
        await _add_criterion_score(db_session, photo, "landschaft", 1.0)
        await _add_criterion_score(db_session, photo, "landmark", 0.8)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["landmark"]["candidate_count"] == 0

    async def test_excludes_rejected_photos(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_classification_run(db_session, project_id)
        rejected = await _add_photo_candidate(db_session, project_id, "a.jpg", rejected=True)
        await _add_criterion_score(db_session, rejected, "landschaft", 1.0)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["landmark"]["candidate_count"] == 0

    async def test_counts_a_photo_of_another_project_separately(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_classification_run(db_session, project_id)
        app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
        other_id = (
            await authenticated_api_client.post(
                "/projects", json={"name": "Island", "opencloud_path": "B"}
            )
        ).json()["id"]
        other_photo = await _add_photo_candidate(db_session, other_id, "a.jpg")
        await _add_criterion_score(db_session, other_photo, "landschaft", 1.0)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["landmark"]["candidate_count"] == 0
        assert body["candidate_count"] == 0


class TestTheEstimateFollowsTheConfiguredModel:
    """specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, ADR 0059 Punkt 3/4: die
    Schaetzung haengt am eingestellten MODELL, nicht mehr am Anbieter."""

    async def test_the_default_estimate_still_matches_the_previous_constant(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Akzeptanzkriterium "ohne gesetzte Einstellung exakt wie bisher", auf API-Ebene gegen den
        LITERALEN Altwert der abgeloesten `COST_PER_IMAGE_USD["anthropic"]` gepinnt - ohne diesen
        Anker prueft die API-Ebene nach dem Umbau nur noch sich selbst."""
        project_id = await _create_project(authenticated_api_client)
        await _add_photo_candidate(db_session, project_id, "a.jpg")

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["model"] == "claude-haiku-4-5"
        assert body["price_per_image_usd"] == pytest.approx(0.0052, abs=1e-9)
        assert body["estimated_cost_usd"] == pytest.approx(0.0052, abs=1e-9)

    async def test_a_configured_non_default_model_changes_the_price(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        stronger = VISION_MODELS_BY_PROVIDER["anthropic"][1]
        monkeypatch.setattr(settings, "landmark_model", stronger)
        project_id = await _create_project(authenticated_api_client)
        await _add_photo_candidate(db_session, project_id, "a.jpg")

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["model"] == stronger
        assert body["price_per_image_usd"] > 0.0052

    async def test_an_unpriced_model_yields_null_amounts_instead_of_zero(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SECURITY-MUSS-KRITERIUM (Spec 0304): `null` schlaegt unverfaelscht durch, kein `?? 0`.
        Ein stilles "0,00 $" waere die gefaehrlichste aller Anzeigen - es behauptete
        Kostenfreiheit.

        Der Zustand ist per Konfiguration unerreichbar (Registry-Invariante in test_pricing.py) -
        deshalb ausdruecklich ueber den Monkeypatch-Bypass erzeugt. Der Pfad wird trotzdem
        gebaut und geprueft, weil eine Absicherung, die ausschliesslich aus einem Test besteht,
        mit diesem Test verschwindet (ADR 0059 Punkt 4)."""
        monkeypatch.setattr(settings, "landmark_model", "ein-nie-bepreistes-modell")
        project_id = await _create_project(authenticated_api_client)
        await _add_photo_candidate(db_session, project_id, "a.jpg")

        response = await authenticated_api_client.get(
            f"/projects/{project_id}/classify/estimate"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["model"] == "ein-nie-bepreistes-modell"
        assert body["price_per_image_usd"] is None
        assert body["estimated_cost_usd"] is None
        # Die Kandidatenzahl bleibt korrekt - sie ist bekannt, nur der Preis ist es nicht.
        assert body["candidate_count"] == 1

    async def test_zero_candidates_yield_zero_even_without_a_known_price(
        self,
        authenticated_api_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Die KOMBINATION der beiden Sonderfaelle darueber (Copilot-Fund, PR #341): kein
        hinterlegter Preis UND null Kandidaten.

        `null` heisst "wir wissen nicht, was das kostet" - bei null Kandidaten wissen wir es aber
        sehr wohl: es faellt nichts an, weil nichts verarbeitet wird. Der Preis JE BILD bleibt
        deshalb `null` (er ist tatsaechlich unbekannt), die Summe ist `0.0`. Die Zusage
        "candidate_count=0 liefert estimated_cost_usd=0.0, kein Sonderfall" aus dem Docstring des
        Endpunkts gilt ohne Ausnahme - sonst haengt sie unausgesprochen daran, dass ein Preis
        gepflegt ist."""
        monkeypatch.setattr(settings, "landmark_model", "ein-nie-bepreistes-modell")
        project_id = await _create_project(authenticated_api_client)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["candidate_count"] == 0
        assert body["price_per_image_usd"] is None
        assert body["estimated_cost_usd"] == 0.0

    async def test_zero_candidates_still_yield_zero_not_null(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        """`0.0` heisst "nichts zu bezahlen", `null` heisst "unbekannt" - die beiden duerfen nie
        zusammenfallen."""
        project_id = await _create_project(authenticated_api_client)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["candidate_count"] == 0
        assert body["estimated_cost_usd"] == 0.0
        assert body["estimated_cost_usd"] is not None


class TestTheLandmarkShareIsUnknownBeforeTheFirstRun:
    """specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-
    vier-teilschritte-und-laufeigene-cloud-bilanz.md Punkt 7.

    Vor dem ersten Durchlauf eines Projekts gibt es keine gespeicherten Kriterien-Werte, aus denen
    sich Landmark-Kandidaten ableiten liessen. Die bisherige `0` behauptete dort Kostenfreiheit
    fuer einen Anteil, der gleich Geld kostet. `null` heisst "unbekannt", nie "kostenlos" -
    dieselbe Semantik, die `price_per_image_usd` seit ADR 0059 Punkt 4 traegt.

    Merkmal ist die Existenz eines `CriterionScoringRun` mit `status = success` im Projekt: ein
    laufender oder fehlgeschlagener Durchlauf gilt ausdruecklich nicht als stattgefunden
    (geschaerftes Akzeptanzkriterium)."""

    async def test_no_run_at_all_means_unknown(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        photo = await _add_photo_candidate(db_session, project_id, "a.jpg")
        await _add_criterion_score(db_session, photo, "landschaft", 1.0)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["landmark"]["candidate_count"] is None

    @pytest.mark.parametrize(
        "status", [ScanStatus.FAILED, ScanStatus.RUNNING], ids=["fehlgeschlagen", "laufend"]
    )
    async def test_an_unfinished_run_does_not_count_as_a_durchlauf(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        status: ScanStatus,
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_classification_run(db_session, project_id, status=status)
        photo = await _add_photo_candidate(db_session, project_id, "a.jpg")
        await _add_criterion_score(db_session, photo, "landschaft", 1.0)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["landmark"]["candidate_count"] is None

    async def test_a_successful_run_unlocks_the_share_even_when_it_is_zero(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Nach einem erfolgreichen Lauf ist `0` eine ANDERE Aussage als `null`: "es gibt gerade
        keine Landmark-Kandidaten" statt "wir wissen es nicht"."""
        project_id = await _create_project(authenticated_api_client)
        await _add_classification_run(db_session, project_id)
        await _add_photo_candidate(db_session, project_id, "a.jpg")

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["landmark"]["candidate_count"] == 0
        assert body["landmark"]["estimated_cost_usd"] == 0.0

    async def test_a_successful_run_in_another_project_does_not_unlock_the_share(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Pflichtfall jeder projektskopierten Abfrage - ohne ihn bestuende die Abfrage auch ohne
        `WHERE project_id = ...`."""
        project_id = await _create_project(authenticated_api_client)
        app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
        other_id = (
            await authenticated_api_client.post(
                "/projects", json={"name": "Island", "opencloud_path": "B"}
            )
        ).json()["id"]
        await _add_classification_run(db_session, other_id)
        photo = await _add_photo_candidate(db_session, project_id, "a.jpg")
        await _add_criterion_score(db_session, photo, "landschaft", 1.0)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["landmark"]["candidate_count"] is None

    async def test_the_total_is_the_sum_of_the_known_shares_only(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Bei unbekanntem Landmark-Anteil ist `candidate_count` ausdruecklich eine UNTERE
        SCHRANKE und `estimated_cost_usd` ein Betrag (keine `null`) - waehrend
        `landmark.estimated_cost_usd` `null` bleibt. Wuerde die Gesamtsumme hier auf `null`
        fallen, saehe der Nutzer vor seinem ersten Durchlauf ueberhaupt keinen Betrag mehr."""
        project_id = await _create_project(authenticated_api_client)
        await _add_photo_candidate(db_session, project_id, "a.jpg")
        await _add_photo_candidate(db_session, project_id, "b.jpg")
        price = estimate_usd_per_image(
            settings.resolved_landmark_model(), settings.landmark_provider
        )
        assert price is not None

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["candidate_count"] == 2
        assert body["estimated_cost_usd"] == pytest.approx(2 * price)
        assert body["remote_categories"]["estimated_cost_usd"] == pytest.approx(2 * price)
        assert body["landmark"]["estimated_cost_usd"] is None


class TestTheBranchOrderPerShare:
    """Die Reihenfolge der Zweige ist die Aussage (Copilot-Fund PR #341), und sie gilt jetzt JE
    ANTEIL: `candidate_count == 0` zuerst -> `0.0`; dann `price is None` -> `None`; dazu neu
    "Anteil unbekannt" -> `None`."""

    async def test_zero_candidates_yield_zero_for_the_share(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_classification_run(db_session, project_id)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["remote_categories"] == {"candidate_count": 0, "estimated_cost_usd": 0.0}
        assert body["landmark"] == {"candidate_count": 0, "estimated_cost_usd": 0.0}

    async def test_zero_candidates_beat_a_missing_price(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Bei null Kandidaten ist der Betrag BEKANNT - es faellt nichts an, weil nichts
        verarbeitet wird - auch wenn der Preis je Bild unbekannt ist."""
        monkeypatch.setattr(settings, "landmark_model", "ein-nie-bepreistes-modell")
        project_id = await _create_project(authenticated_api_client)
        await _add_classification_run(db_session, project_id)

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["price_per_image_usd"] is None
        assert body["remote_categories"]["estimated_cost_usd"] == 0.0
        assert body["landmark"]["estimated_cost_usd"] == 0.0

    async def test_a_missing_price_yields_null_for_a_non_empty_share(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "landmark_model", "ein-nie-bepreistes-modell")
        project_id = await _create_project(authenticated_api_client)
        await _add_classification_run(db_session, project_id)
        await _add_photo_candidate(db_session, project_id, "a.jpg")

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["remote_categories"]["candidate_count"] == 1
        assert body["remote_categories"]["estimated_cost_usd"] is None
        assert body["estimated_cost_usd"] is None

    async def test_an_unknown_share_yields_null_regardless_of_the_price(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        await _add_photo_candidate(db_session, project_id, "a.jpg")

        body = (
            await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
        ).json()

        assert body["price_per_image_usd"] is not None
        assert body["landmark"]["candidate_count"] is None
        assert body["landmark"]["estimated_cost_usd"] is None


async def test_the_two_flat_candidate_fields_are_gone(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Abwesenheits-Assertion zum Umbau von `ClassificationEstimateOut`: die beiden Flachfelder
    gehen in den Anteils-Objekten AUF, sie stehen nicht zusaetzlich daneben. Zwei Wege zu
    derselben Zahl, von denen einer die `null`-Semantik nicht kennt, waeren genau der Zustand,
    den ADR 0068 Punkt 7 beseitigt."""
    project_id = await _create_project(authenticated_api_client)
    await _add_photo_candidate(db_session, project_id, "a.jpg")

    body = (
        await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
    ).json()

    assert "remote_category_candidate_count" not in body
    assert "landmark_candidate_count" not in body
    assert set(body) == {
        "candidate_count",
        "remote_categories",
        "landmark",
        "provider",
        "model",
        "price_per_image_usd",
        "estimated_cost_usd",
    }
