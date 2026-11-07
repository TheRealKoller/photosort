"""Die Pruef-API: Options, Schaetzung, Anlegen, Liste, Detail, Faelle, Urteil, Export.

Was hier festgehalten wird, ist der Vertrag der Endpunkte (Spec 0616, ADR 0139):

* die REIHENFOLGE der Ablehnungen beim Anlegen (`403` Feature-Schalter -> `403` Eye -> `404` ->
  `409` -> `403` Einwilligung -> `503` -> `422`), weil sie Teil der Zusage ist und ein spaeterer
  Schalter sie leicht umdreht,
* die Projektbindung als UND-Bedingung in derselben Anweisung: eine fremde Id ist `404`, nie
  `403` (S2),
* die Positivliste des Exports samt Formwaechter und Marker-Technik (S3),
* ein gemeinsames Urteil je Fall, letzter Schreiber gewinnt (S1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.cloud_vision import ANTHROPIC_VISION_MODEL, MISTRAL_VISION_MODEL
from photosort.config import settings
from photosort.eye_mapping import MAPPINGS, MODEL_REVISION
from photosort.models import (
    ClassificationReview,
    DuplicateDecision,
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    Project,
    RatingStatus,
    ScanStatus,
    User,
)
from photosort.pricing import estimate_usd_per_image

_MOMENT = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC).replace(tzinfo=None)


class FakeEnqueuer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> None:
        self.calls.append((function, args))


async def _make_user(session: AsyncSession, username: str = "anleger") -> User:
    user = User(username=username, password_hash="x")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _make_project(
    session: AsyncSession, *, consent: bool = False, name: str = "Costa Rica"
) -> Project:
    project = Project(
        name=name,
        opencloud_drive_id=f"drive-{name}",
        opencloud_path=name,
        cloud_vision_detection_enabled=consent,
    )
    if consent:
        project.cloud_vision_consent_at = _MOMENT
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_photo(
    session: AsyncSession,
    project: Project,
    path: str,
    *,
    suggested_status: RatingStatus | None = None,
    decision: DuplicateDecision | None = None,
    with_score: bool = True,
) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=1,
        taken_at=_MOMENT,
        taken_at_original=_MOMENT,
        last_modified=_MOMENT,
    )
    session.add(photo)
    await session.flush()
    if with_score:
        session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=100.0,
                exposure=0.0,
                suggested_status=suggested_status,
                computed_at=_MOMENT,
            )
        )
    if decision is not None:
        session.add(PhotoDuplicateDecision(photo_id=photo.id, decision=decision))
    await session.commit()
    await session.refresh(photo)
    return photo


async def _make_review(
    session: AsyncSession,
    project: Project,
    user: User,
    *,
    status: ScanStatus = ScanStatus.SUCCESS,
    sample_size: int = 30,
    seed: int = 4711,
) -> ClassificationReview:
    review = ClassificationReview(
        project_id=project.id,
        created_by_user_id=user.id,
        status=status,
        sample_size=sample_size,
        seed=seed,
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


def _url(project_id: int, suffix: str = "") -> str:
    return f"/projects/{project_id}/classification-reviews{suffix}"


class TestOptions:
    async def test_the_defaults_offer_local_only(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Ohne Einwilligung, ohne Schluessel und ohne Eye bleibt nur die lokale Seite waehlbar -
        mit den beiden Gruenden in der festgelegten Reihenfolge."""
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(_url(project.id, "/options"))

        assert response.status_code == 200
        kinds = {entry["kind"]: entry for entry in response.json()["kinds"]}
        assert kinds["cloud"] == {
            "kind": "cloud",
            "available": False,
            "unavailable_reasons": ["no_consent", "no_api_key"],
        }
        assert kinds["eye"] == {
            "kind": "eye",
            "available": False,
            "unavailable_reasons": ["eye_disabled"],
        }
        assert kinds["local"] == {
            "kind": "local",
            "available": True,
            "unavailable_reasons": [],
        }

    async def test_the_sample_size_bounds_come_from_the_server(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)

        payload = (await authenticated_api_client.get(_url(project.id, "/options"))).json()

        assert payload["sample_size"] == {"default": 30, "min": 1, "max": 200}

    async def test_consent_without_any_key_offers_no_cloud_model(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, consent=True)

        payload = (await authenticated_api_client.get(_url(project.id, "/options"))).json()

        assert [entry["model"] for entry in payload["cloud_models"]]
        for entry in payload["cloud_models"]:
            assert entry["available"] is False
            assert entry["unavailable_reasons"] == ["no_api_key"]

    async def test_a_key_opens_only_its_own_provider(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
        project = await _make_project(db_session, consent=True)

        payload = (await authenticated_api_client.get(_url(project.id, "/options"))).json()

        by_provider: dict[str, set[bool]] = {}
        for entry in payload["cloud_models"]:
            assert entry["provider"] in {"anthropic", "mistral"}
            by_provider.setdefault(entry["provider"], set()).add(entry["available"])
        assert by_provider == {"anthropic": {True}, "mistral": {False}}
        kinds = {entry["kind"]: entry for entry in payload["kinds"]}
        assert kinds["cloud"]["available"] is True
        assert MISTRAL_VISION_MODEL not in {
            entry["model"] for entry in payload["cloud_models"] if entry["available"]
        }

    async def test_the_eye_switch_opens_the_mapping_versions(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        project = await _make_project(db_session)

        payload = (await authenticated_api_client.get(_url(project.id, "/options"))).json()

        assert [entry["eye_mapping_version"] for entry in payload["eye_mappings"]] == list(MAPPINGS)
        for entry in payload["eye_mappings"]:
            assert entry["eye_model_revision"] == MODEL_REVISION
            assert entry["available"] is True
            assert entry["unavailable_reasons"] == []
        kinds = {entry["kind"]: entry for entry in payload["kinds"]}
        assert kinds["eye"]["available"] is True

    async def test_the_names_of_the_option_payload_are_closed(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """`unavailable_reasons` sind feste Tokens, keine Variablennamen und keine Werte (S7)."""
        project = await _make_project(db_session)

        payload = (await authenticated_api_client.get(_url(project.id, "/options"))).json()

        assert set(payload) == {"sample_size", "kinds", "cloud_models", "eye_mappings"}
        for entry in payload["cloud_models"]:
            assert set(entry) == {"provider", "model", "available", "unavailable_reasons"}
        for entry in payload["eye_mappings"]:
            assert set(entry) == {
                "eye_model_revision",
                "eye_mapping_version",
                "available",
                "unavailable_reasons",
            }

    async def test_an_unknown_project_is_404(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.get(_url(999, "/options"))

        assert response.status_code == 404

    async def test_the_options_require_a_token(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.get(_url(1, "/options"))

        assert response.status_code == 401


class TestEstimate:
    async def test_eye_and_local_are_free(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            _url(project.id, "/estimate?a_kind=eye&b_kind=local")
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["a"]["estimated_cost_usd"] == 0.0
        assert payload["b"]["estimated_cost_usd"] == 0.0
        assert payload["a"]["price_per_image_usd"] == 0.0

    async def test_the_estimate_names_an_unknown_project(
        self, authenticated_api_client: httpx.AsyncClient
    ) -> None:
        response = await authenticated_api_client.get(
            "/projects/999/classification-reviews/estimate?a_kind=local&b_kind=local"
        )

        assert response.status_code == 404

    async def test_a_cloud_side_costs_the_count_times_the_price_per_image(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, consent=True)
        for index in range(3):
            await _add_photo(db_session, project, f"keep-{index}.jpg")

        payload = (
            await authenticated_api_client.get(
                _url(
                    project.id,
                    f"/estimate?a_kind=cloud&b_kind=local&a_model={ANTHROPIC_VISION_MODEL}",
                )
            )
        ).json()

        price = estimate_usd_per_image(ANTHROPIC_VISION_MODEL, "anthropic")
        assert payload["photo_count"] == 3
        assert payload["a"]["model"] == ANTHROPIC_VISION_MODEL
        assert payload["a"]["provider"] == "anthropic"
        assert payload["a"]["price_per_image_usd"] == pytest.approx(price)
        assert payload["a"]["estimated_cost_usd"] == pytest.approx(3 * price)

    async def test_the_review_set_excludes_the_ausschuss(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Pruefmenge sind die Ausschuss-Ueberlebenden - ohne Skip-Kriterium, aber ein
        verworfener Vorschlag ist kein Ueberlebender."""
        project = await _make_project(db_session)
        await _add_photo(db_session, project, "keep.jpg")
        await _add_photo(
            db_session, project, "rejected.jpg", suggested_status=RatingStatus.REJECTED
        )
        await _add_photo(db_session, project, "kept-by-user.jpg", decision=DuplicateDecision.KEEP)

        payload = (
            await authenticated_api_client.get(
                _url(project.id, "/estimate?a_kind=local&b_kind=eye")
            )
        ).json()

        assert payload["photo_count"] == 2

    async def test_an_unknown_model_is_not_estimable(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session, consent=True)
        await _add_photo(db_session, project, "keep.jpg")

        payload = (
            await authenticated_api_client.get(
                _url(project.id, "/estimate?a_kind=cloud&b_kind=local&a_model=unbekannt")
            )
        ).json()

        assert payload["a"]["provider"] is None
        assert payload["a"]["price_per_image_usd"] is None
        assert payload["a"]["estimated_cost_usd"] is None

    async def test_an_empty_review_set_costs_zero_even_without_a_price(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Dreizweigregel: null Fotos ist ein BEKANNTER Betrag, auch wenn kein Preis hinterlegt
        ist - "nicht schaetzbar" ist etwas anderes als "es faellt nichts an"."""
        project = await _make_project(db_session, consent=True)

        payload = (
            await authenticated_api_client.get(
                _url(project.id, "/estimate?a_kind=cloud&b_kind=local&a_model=unbekannt")
            )
        ).json()

        assert payload["photo_count"] == 0
        assert payload["a"]["estimated_cost_usd"] == 0.0

    async def test_an_unknown_kind_is_rejected_by_the_schema(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)

        response = await authenticated_api_client.get(
            _url(project.id, "/estimate?a_kind=cloud2&b_kind=local")
        )

        assert response.status_code == 422
