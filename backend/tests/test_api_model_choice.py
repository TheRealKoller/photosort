"""Der Lese- und Schreibendpunkt der Modellwahl je Projekt (Spec 0383, ADR 0143 Punkt 2/4).

Der Katalog ist MENGENGLEICH zur Registry: was hier fehlt, ist nicht waehlbar, und was dort
steht, muss hier mit seinen fuenf Werten erscheinen. Der Schreibpfad nimmt ausschliesslich
geschlossene Eingaben an (S1) und laesst bei einem Fehlschlag JEDE der drei Spalten unveraendert.

Die Verfuegbarkeit eines Anbieters verlaesst den Server nur als Wahrheitswert (S4); ein
gespeichertes, aber entferntes Modell ist auf dem LESEPFAD `provider: null` und beim Ausloeser
bzw. der Schaetzung `409` - hier darf dieselbe unveraenderte Wahl weiter gespeichert werden.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_opencloud_client
from photosort.cloud_vision import (
    ANTHROPIC_VISION_MODEL,
    ANTHROPIC_VISION_MODEL_SONNET,
    MISTRAL_VISION_MODEL,
    VISION_MODELS_BY_PROVIDER,
)
from photosort.config import settings
from photosort.main import app
from photosort.models import (
    CategoryMethod,
    CriterionScoringRun,
    Project,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.opencloud.client import Drive
from photosort.pricing import MODEL_PRICING, estimate_usd_per_image
from photosort.security import create_access_token, hash_password


class FakeOpenCloudClient:
    async def resolve_drive(self, name: str | None) -> Drive:
        return Drive(
            id="drive-1",
            name="Family",
            drive_type="project",
            webdav_url="https://x/dav/spaces/drive-1",
        )

    async def list_folder(self, webdav_url: str, path: str, depth: str = "1") -> list[object]:
        return []


async def _create_project(client: httpx.AsyncClient) -> int:
    app.dependency_overrides[get_opencloud_client] = lambda: FakeOpenCloudClient()
    created = await client.post("/projects", json={"name": "Costa Rica", "opencloud_path": "A"})
    result: int = created.json()["id"]
    return result


async def _stored_project(session: AsyncSession, project_id: int) -> Project:
    project = await session.get(Project, project_id)
    assert project is not None
    return project


def _body(
    *,
    method: str = "cloud",
    category_model: str | None = ANTHROPIC_VISION_MODEL,
    landmark_model: str | None = None,
) -> dict[str, str | None]:
    return {
        "category_method": method,
        "category_model": category_model,
        "landmark_model": landmark_model,
    }


class TestTheEndpointsAreGuarded:
    @pytest.mark.parametrize("method", ["get", "put"])
    async def test_both_verbs_require_auth(
        self, api_client: httpx.AsyncClient, method: str
    ) -> None:
        kwargs = {"json": _body()} if method == "put" else {}
        response = await getattr(api_client, method)("/projects/1/model-choice", **kwargs)
        assert response.status_code == 401

    async def test_an_unknown_project_is_a_404(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        assert (await authenticated_api_client.get("/projects/999/model-choice")).status_code == 404

    async def test_put_on_an_unknown_project_is_a_404(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.put("/projects/999/model-choice", json=_body())
        assert response.status_code == 404


class TestTheCatalogue:
    async def test_the_catalogue_is_the_registry_in_order(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)

        body = (await authenticated_api_client.get(f"/projects/{project_id}/model-choice")).json()

        expected = [
            (provider, model)
            for provider, models in VISION_MODELS_BY_PROVIDER.items()
            for model in models
        ]
        assert [(entry["provider"], entry["model"]) for entry in body["cloud_models"]] == expected

    async def test_each_entry_carries_its_five_values(
        self,
        authenticated_api_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "cloud_vision_requests_per_minute", 17)
        project_id = await _create_project(authenticated_api_client)

        body = (await authenticated_api_client.get(f"/projects/{project_id}/model-choice")).json()

        entry = next(e for e in body["cloud_models"] if e["model"] == MISTRAL_VISION_MODEL)
        pricing = MODEL_PRICING[MISTRAL_VISION_MODEL]
        assert entry["provider"] == "mistral"
        assert entry["estimate_usd_per_image"] == pytest.approx(
            estimate_usd_per_image(MISTRAL_VISION_MODEL, "mistral"), abs=1e-9
        )
        assert entry["input_usd_per_mtok"] == pricing.input_usd_per_mtok
        assert entry["output_usd_per_mtok"] == pricing.output_usd_per_mtok
        assert entry["requests_per_minute"] == 17

    async def test_a_missing_price_is_null_and_never_zero(
        self,
        authenticated_api_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Edge Case 7: Katalogeintrag ohne `MODEL_PRICING` - Preis je Bild und beide Token-Preise
        `null`. Eine `0` behauptete Kostenfreiheit."""
        monkeypatch.delitem(MODEL_PRICING, ANTHROPIC_VISION_MODEL)
        project_id = await _create_project(authenticated_api_client)

        body = (await authenticated_api_client.get(f"/projects/{project_id}/model-choice")).json()

        entry = next(e for e in body["cloud_models"] if e["model"] == ANTHROPIC_VISION_MODEL)
        assert entry["estimate_usd_per_image"] is None
        assert entry["input_usd_per_mtok"] is None
        assert entry["output_usd_per_mtok"] is None

    async def test_the_key_availability_is_a_boolean_with_a_reason(
        self,
        authenticated_api_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-secret")
        monkeypatch.setattr(settings, "mistral_api_key", "")
        project_id = await _create_project(authenticated_api_client)

        body = (await authenticated_api_client.get(f"/projects/{project_id}/model-choice")).json()

        anthropic = next(e for e in body["cloud_models"] if e["provider"] == "anthropic")
        mistral = next(e for e in body["cloud_models"] if e["provider"] == "mistral")
        assert anthropic["available"] is True
        assert anthropic["unavailable_reasons"] == []
        assert mistral["available"] is False
        assert mistral["unavailable_reasons"] == ["no_api_key"]
        assert "sk-ant-secret" not in str(body)

    @pytest.mark.parametrize(("enabled", "reasons"), [(True, []), (False, ["eye_disabled"])])
    async def test_eye_availability_comes_from_the_switch(
        self,
        authenticated_api_client: httpx.AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        enabled: bool,
        reasons: list[str],
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", enabled)
        project_id = await _create_project(authenticated_api_client)

        body = (await authenticated_api_client.get(f"/projects/{project_id}/model-choice")).json()

        assert body["eye"] == {"available": enabled, "unavailable_reasons": reasons}


class TestTheCurrentChoice:
    async def test_a_project_without_its_own_choice_shows_the_installation_default(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        model = settings.resolved_landmark_model()

        body = (await authenticated_api_client.get(f"/projects/{project_id}/model-choice")).json()

        assert body["current"] == {
            "category_method": "cloud",
            "category_model": model,
            "category_provider": "anthropic",
            "category_is_default": True,
            "landmark_model": model,
            "landmark_provider": "anthropic",
            "landmark_is_default": True,
        }

    async def test_a_stored_choice_is_not_a_default_any_more(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        project = await _stored_project(db_session, project_id)
        project.category_model = MISTRAL_VISION_MODEL
        project.landmark_model = ANTHROPIC_VISION_MODEL_SONNET
        await db_session.commit()

        body = (await authenticated_api_client.get(f"/projects/{project_id}/model-choice")).json()

        assert body["current"]["category_provider"] == "mistral"
        assert body["current"]["category_model"] == MISTRAL_VISION_MODEL
        assert body["current"]["category_is_default"] is False
        assert body["current"]["landmark_provider"] == "anthropic"
        assert body["current"]["landmark_is_default"] is False

    async def test_eye_has_no_category_model(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        project = await _stored_project(db_session, project_id)
        project.category_method = CategoryMethod.EYE
        await db_session.commit()

        body = (await authenticated_api_client.get(f"/projects/{project_id}/model-choice")).json()

        assert body["current"]["category_method"] == "eye"
        assert body["current"]["category_model"] is None
        assert body["current"]["category_provider"] is None
        assert body["current"]["category_is_default"] is False

    async def test_a_removed_model_shows_its_id_without_provider(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Edge Case 2, Lesepfad: kein 409, sondern die ID mit `provider: null`."""
        project_id = await _create_project(authenticated_api_client)
        project = await _stored_project(db_session, project_id)
        project.category_model = "gibt-es-nicht-mehr"
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project_id}/model-choice")

        assert response.status_code == 200
        assert response.json()["current"]["category_model"] == "gibt-es-nicht-mehr"
        assert response.json()["current"]["category_provider"] is None


@pytest.fixture(autouse=True)
def _keys_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein waehlbares Modell braucht einen hinterlegten Schluessel - der Wert selbst wird nirgends
    ausgeliefert. Ohne diese Vorgabe waere jeder Schreibversuch eine `422`."""
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    monkeypatch.setattr(settings, "mistral_api_key", "sk-test")


class TestWritingTheChoice:
    async def test_the_choice_of_one_user_is_the_choice_of_the_other(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        api_client: httpx.AsyncClient,
    ) -> None:
        """AK 40 ("gilt fuer beide Nutzer der Installation"): die Wahl haengt am PROJEKT, nicht an
        der Person. Ein zweiter Nutzer mit eigenem Token liest nach dem `PUT` des ersten denselben
        Stand - dieser Fall wuerde gegen eine versehentlich `user_id`-gebundene Ablage bestehen."""
        project_id = await _create_project(authenticated_api_client)
        await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice",
            json=_body(category_model=MISTRAL_VISION_MODEL),
        )

        partner = User(username="partnerin", password_hash=hash_password("irrelevant"))
        db_session.add(partner)
        await db_session.commit()
        await db_session.refresh(partner)
        partner_token = create_access_token(partner)

        response = await api_client.get(
            f"/projects/{project_id}/model-choice",
            headers={"Authorization": f"Bearer {partner_token}"},
        )

        assert response.status_code == 200
        current = response.json()["current"]
        assert current["category_model"] == MISTRAL_VISION_MODEL
        assert current["category_provider"] == "mistral"
        assert current["category_is_default"] is False

    async def test_a_valid_choice_is_stored_and_answered(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice",
            json=_body(category_model=MISTRAL_VISION_MODEL, landmark_model=ANTHROPIC_VISION_MODEL),
        )

        assert response.status_code == 200
        assert response.json()["current"]["category_provider"] == "mistral"
        assert response.json()["current"]["category_model"] == MISTRAL_VISION_MODEL
        assert response.json()["current"]["landmark_model"] == ANTHROPIC_VISION_MODEL
        project = await _stored_project(db_session, project_id)
        assert project.category_method is CategoryMethod.CLOUD
        assert project.category_model == MISTRAL_VISION_MODEL
        assert project.landmark_model == ANTHROPIC_VISION_MODEL

    async def test_switching_to_eye_clears_the_category_model(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        project_id = await _create_project(authenticated_api_client)

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice", json=_body(method="eye", category_model=None)
        )

        assert response.status_code == 200
        project = await _stored_project(db_session, project_id)
        assert project.category_method is CategoryMethod.EYE
        assert project.category_model is None

    async def test_extra_fields_are_rejected(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S1: geschlossene Eingabe. Ein zusaetzliches Feld darf nicht still verschwinden."""
        project_id = await _create_project(authenticated_api_client)
        payload = _body() | {"provider": "mistral"}

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice", json=payload
        )

        assert response.status_code == 422
        project = await _stored_project(db_session, project_id)
        assert project.category_model is None

    async def test_a_missing_field_is_rejected(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice",
            json={"category_method": "cloud", "landmark_model": None},
        )

        assert response.status_code == 422

    async def test_a_model_outside_the_registry_is_rejected(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project_id = await _create_project(authenticated_api_client)

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice", json=_body(category_model="frei-erfunden")
        )

        assert response.status_code == 422
        project = await _stored_project(db_session, project_id)
        assert project.category_model is None

    async def test_the_same_removed_model_may_stay(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Edge Case 2: derselbe unveraenderte Wert an `PUT` ist `200` - sonst koennte ein Projekt
        mit entferntem Modell gar nicht mehr auf die neue Wahl umgestellt werden."""
        project_id = await _create_project(authenticated_api_client)
        project = await _stored_project(db_session, project_id)
        project.category_model = "gibt-es-nicht-mehr"
        await db_session.commit()

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice",
            json=_body(category_model="gibt-es-nicht-mehr"),
        )

        assert response.status_code == 200
        assert response.json()["current"]["category_provider"] is None

    async def test_a_provider_without_key_is_rejected_only_on_change(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "mistral_api_key", "")
        monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-secret")
        project_id = await _create_project(authenticated_api_client)

        rejected = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice", json=_body(category_model=MISTRAL_VISION_MODEL)
        )
        assert rejected.status_code == 422
        project = await _stored_project(db_session, project_id)
        assert project.category_model is None

    async def test_an_unchanged_provider_without_key_may_stay(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "mistral_api_key", "")
        project_id = await _create_project(authenticated_api_client)
        project = await _stored_project(db_session, project_id)
        project.category_model = MISTRAL_VISION_MODEL
        await db_session.commit()

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice", json=_body(category_model=MISTRAL_VISION_MODEL)
        )

        assert response.status_code == 200

    async def test_eye_is_rejected_while_the_installation_switch_is_off(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", False)
        project_id = await _create_project(authenticated_api_client)

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice", json=_body(method="eye", category_model=None)
        )

        assert response.status_code == 422
        project = await _stored_project(db_session, project_id)
        assert project.category_method is CategoryMethod.CLOUD

    async def test_eye_already_stored_may_stay_while_the_switch_is_off(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", False)
        project_id = await _create_project(authenticated_api_client)
        project = await _stored_project(db_session, project_id)
        project.category_method = CategoryMethod.EYE
        project.landmark_model = ANTHROPIC_VISION_MODEL
        await db_session.commit()

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice",
            json=_body(method="eye", category_model=None, landmark_model=ANTHROPIC_VISION_MODEL),
        )

        assert response.status_code == 200

    async def test_eye_with_a_category_model_is_rejected(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice", json=_body(method="eye")
        )

        assert response.status_code == 422

    async def test_cloud_with_the_installation_default_is_accepted_and_stored_as_null(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`cloud` ohne Modell ist die Installationsvorgabe und ausdruecklich speicherbar
        (ADR 0143 Punkt 6) - gespeichert wird `NULL`, und `category_is_default` sagt es."""
        project_id = await _create_project(authenticated_api_client)

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice",
            json=_body(category_model=None, landmark_model=None),
        )

        assert response.status_code == 200
        project = await _stored_project(db_session, project_id)
        assert project.category_method is CategoryMethod.CLOUD
        assert project.category_model is None
        assert project.landmark_model is None
        current = response.json()["current"]
        assert current["category_is_default"] is True
        assert current["landmark_is_default"] is True
        assert current["category_model"] == settings.resolved_landmark_model()

    async def test_the_unchanged_default_stays_accepted(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        """Ein unveraendert durchgereichtes `null` wird nicht neu geprueft - der Bestand bleibt
        auch dann schreibbar, wenn diese Installation gar keinen Cloud-Schluessel hat."""
        project_id = await _create_project(authenticated_api_client)
        body = _body(category_model=None, landmark_model=None)

        for _ in range(2):
            response = await authenticated_api_client.put(
                f"/projects/{project_id}/model-choice", json=body
            )
            assert response.status_code == 200

    async def test_the_way_back_from_eye_to_the_default_needs_no_api_key(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Der Rueckweg (ADR 0143 Punkt 6): nach der Eye-Wahl steht `category_model` auf `NULL`;
        ohne jeden Cloud-Schluessel muss die Vorgabe trotzdem speicherbar sein, sonst waere die
        Wahl eine Einbahnstrasse - und genau so sieht der Pruefstack aus."""
        monkeypatch.setattr(
            "photosort.api.model_choice.api_key_for_provider", lambda _provider: False
        )
        project_id = await _create_project(authenticated_api_client)
        project = await _stored_project(db_session, project_id)
        project.category_method = CategoryMethod.EYE
        project.category_model = None
        project.landmark_model = ANTHROPIC_VISION_MODEL
        await db_session.commit()

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice",
            json=_body(category_model=None, landmark_model=ANTHROPIC_VISION_MODEL),
        )

        assert response.status_code == 200
        project = await _stored_project(db_session, project_id)
        assert project.category_method is CategoryMethod.CLOUD
        assert project.category_model is None

    async def test_a_running_classification_blocks_the_change(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Edge Case 9: `409`, gespeicherte Wahl unveraendert - und die Meldung nennt die
        Modellwahl, nicht den Richtwert."""
        project_id = await _create_project(authenticated_api_client)
        scoring_run = ScoringRun(project_id=project_id, status=ScanStatus.SUCCESS)
        db_session.add(scoring_run)
        await db_session.commit()
        await db_session.refresh(scoring_run)
        db_session.add(
            CriterionScoringRun(
                project_id=project_id,
                scoring_run_id=scoring_run.id,
                status=ScanStatus.RUNNING,
                started_at=datetime.now(UTC),
            )
        )
        await db_session.commit()

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice", json=_body(category_model=MISTRAL_VISION_MODEL)
        )

        assert response.status_code == 409
        assert "Modellwahl" in response.json()["detail"]
        project = await _stored_project(db_session, project_id)
        assert project.category_model is None

    async def test_the_consent_columns_are_untouched(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S3: die Modellwahl erteilt und entzieht keine Einwilligung."""
        project_id = await _create_project(authenticated_api_client)
        await authenticated_api_client.put(
            f"/projects/{project_id}/cloud-vision-consent", json={"enabled": True}
        )
        before = await _stored_project(db_session, project_id)
        consent_before = (before.cloud_vision_detection_enabled, before.cloud_vision_consent_at)

        response = await authenticated_api_client.put(
            f"/projects/{project_id}/model-choice", json=_body(category_model=MISTRAL_VISION_MODEL)
        )

        assert response.status_code == 200
        db_session.expire_all()
        after = await _stored_project(db_session, project_id)
        assert (after.cloud_vision_detection_enabled, after.cloud_vision_consent_at) == (
            consent_before
        )


class TestProjectOutCarriesTheChoice:
    async def test_project_out_reports_the_resolved_choice(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        model = settings.resolved_landmark_model()

        body = (await authenticated_api_client.get(f"/projects/{project_id}")).json()

        assert body["model_choice"] == {
            "category_method": "cloud",
            "category_provider": "anthropic",
            "category_model": model,
            "landmark_provider": "anthropic",
            "landmark_model": model,
        }
        assert "eye_available" not in body

    async def test_the_list_endpoint_carries_it_too(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        project_id = await _create_project(authenticated_api_client)

        listed = (await authenticated_api_client.get("/projects")).json()

        entry = next(project for project in listed if project["id"] == project_id)
        assert entry["model_choice"]["category_method"] == "cloud"

    async def test_a_removed_model_is_shown_without_provider(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        project_id = await _create_project(authenticated_api_client)
        project = await _stored_project(db_session, project_id)
        project.category_model = "gibt-es-nicht-mehr"
        await db_session.commit()

        response = await authenticated_api_client.get(f"/projects/{project_id}")

        assert response.status_code == 200
        assert response.json()["model_choice"]["category_provider"] is None

    async def test_the_setting_is_not_read_through_the_database(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Die Antwort folgt der Installationsvorgabe, solange das Projekt keine eigene Wahl
        hat - und bleibt stehen, sobald eine gespeichert ist."""
        project_id = await _create_project(authenticated_api_client)
        first = (await authenticated_api_client.get(f"/projects/{project_id}")).json()
        assert first["model_choice"]["category_model"] == settings.resolved_landmark_model()

        project = await _stored_project(db_session, project_id)
        project.category_model = MISTRAL_VISION_MODEL
        await db_session.commit()
        monkeypatch.setattr(settings, "landmark_provider", "mistral")

        second = (await authenticated_api_client.get(f"/projects/{project_id}")).json()
        assert second["model_choice"]["category_provider"] == "mistral"
        assert second["model_choice"]["category_model"] == MISTRAL_VISION_MODEL


async def test_the_project_row_keeps_a_single_source_of_truth(
    authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Der `PUT` schreibt die drei Spalten in EINEM Commit; danach gibt es keine vierte Ablage."""
    project_id = await _create_project(authenticated_api_client)

    await authenticated_api_client.put(
        f"/projects/{project_id}/model-choice",
        json=_body(category_model=MISTRAL_VISION_MODEL, landmark_model=ANTHROPIC_VISION_MODEL),
    )

    project = (
        await db_session.execute(select(Project).where(Project.id == project_id))
    ).scalar_one()
    assert (project.category_method, project.category_model, project.landmark_model) == (
        CategoryMethod.CLOUD,
        MISTRAL_VISION_MODEL,
        ANTHROPIC_VISION_MODEL,
    )
