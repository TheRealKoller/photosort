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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api import classification_reviews as reviews_api
from photosort.api.deps import get_job_enqueuer
from photosort.cloud_vision import ANTHROPIC_VISION_MODEL, MISTRAL_VISION_MODEL
from photosort.config import settings
from photosort.eye_mapping import MAPPING_VERSION, MAPPINGS, MODEL_REVISION
from photosort.main import app
from photosort.models import (
    ClassificationReview,
    ClassificationReviewSide,
    ClassificationReviewSideKind,
    DuplicateDecision,
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    Project,
    RatingStatus,
    ScanStatus,
    ScoringRun,
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


async def _add_successful_run(
    session: AsyncSession, project: Project, *, gate_confirmed: bool = True
) -> ScoringRun:
    run = ScoringRun(
        project_id=project.id,
        status=ScanStatus.SUCCESS,
        suggestions_found=0,
        started_at=_MOMENT,
    )
    if gate_confirmed:
        run.gate_confirmed_at = _MOMENT
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


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


def _local() -> dict[str, Any]:
    return {"kind": "local"}


def _eye(version: str = MAPPING_VERSION) -> dict[str, Any]:
    return {"kind": "eye", "eye_mapping_version": version}


def _cloud(model: str = ANTHROPIC_VISION_MODEL) -> dict[str, Any]:
    return {"kind": "cloud", "model": model}


_OMITTED: Any = object()


def _body(
    a: dict[str, Any], b: dict[str, Any], *, sample_size: Any = 30, **extra: Any
) -> dict[str, Any]:
    """Der Koerper einer Pruefung; `sample_size` faehrt mit, weil S9 es als Pflichtfeld fuehrt.
    `_OMITTED` laesst es weg - nur der Test auf das fehlende Feld braucht das."""
    body: dict[str, Any] = {"a": a, "b": b, **extra}
    if sample_size is not _OMITTED:
        body["sample_size"] = sample_size
    return body


async def _healthy() -> bool:
    return True


async def _unhealthy() -> bool:
    return False


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


class TestCreate:
    async def _ready_project(
        self, session: AsyncSession, *, consent: bool = False, photos: int = 2
    ) -> Project:
        project = await _make_project(session, consent=consent)
        await _add_successful_run(session, project)
        for index in range(photos):
            await _add_photo(session, project, f"keep-{index}.jpg")
        return project

    async def test_creates_the_review_and_enqueues_the_job(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        monkeypatch.setattr(reviews_api, "eye_service_is_healthy", _healthy)
        project = await self._ready_project(db_session)
        fake = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_eye(), _local(), sample_size=17)
        )

        assert response.status_code == 201
        review_id = response.json()["id"]
        assert response.json()["status"] == "running"
        assert fake.calls == [("run_classification_review", (review_id,))]
        review = await db_session.get(ClassificationReview, review_id)
        assert review is not None
        assert review.status == ScanStatus.RUNNING
        assert review.phase is None
        assert review.sample_size == 17
        assert review.photo_count == 2
        assert 0 <= review.seed < 2**31

    async def test_the_creator_comes_from_the_token(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        monkeypatch.setattr(reviews_api, "eye_service_is_healthy", _healthy)
        project = await self._ready_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_eye(), _local())
        )

        review = await db_session.get(ClassificationReview, response.json()["id"])
        assert review is not None
        creator = await db_session.execute(select(User.id).where(User.username == "testuser"))
        assert review.created_by_user_id == creator.scalar_one()

    async def test_the_origin_and_the_estimate_are_stored_at_the_side(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """S6/S8: der Anbieter folgt aus dem Modell, `eye_model_revision` ist die gepinnte
        Fassung, und der Betrag wird AN DER SEITE eingefroren - er ist der Stand beim Anlegen."""
        monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
        project = await self._ready_project(db_session, consent=True, photos=4)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_cloud(), _local())
        )

        sides = {
            side.side: side
            for side in (
                await db_session.execute(
                    select(ClassificationReviewSide).where(
                        ClassificationReviewSide.review_id == response.json()["id"]
                    )
                )
            ).scalars()
        }
        assert sides["a"].kind is ClassificationReviewSideKind.CLOUD
        assert sides["a"].provider == "anthropic"
        assert sides["a"].model == ANTHROPIC_VISION_MODEL
        assert sides["a"].eye_mapping_version is None
        assert sides["a"].estimated_cost_usd == pytest.approx(
            4 * estimate_usd_per_image(ANTHROPIC_VISION_MODEL, "anthropic")
        )
        assert sides["b"].kind is ClassificationReviewSideKind.LOCAL
        assert sides["b"].provider is None
        assert sides["b"].estimated_cost_usd == 0.0

    async def test_an_eye_side_stores_the_pinned_revision(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        monkeypatch.setattr(reviews_api, "eye_service_is_healthy", _healthy)
        project = await self._ready_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_eye(), _local())
        )

        side = (
            await db_session.execute(
                select(ClassificationReviewSide).where(
                    ClassificationReviewSide.review_id == response.json()["id"],
                    ClassificationReviewSide.side == "a",
                )
            )
        ).scalar_one()
        assert side.eye_model_revision == MODEL_REVISION
        assert side.eye_mapping_version == MAPPING_VERSION

    async def test_the_feature_switch_comes_first(
        self, authenticated_api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "category_selection_enabled", False)
        monkeypatch.setattr(settings, "eye_enabled", False)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            "/projects/999/classification-reviews", json=_body(_eye(), _local())
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Diese Funktion ist derzeit nicht aktiviert."

    async def test_the_eye_switch_is_second(
        self, authenticated_api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Das Projekt 999 existiert nicht, trotzdem `403`: die Antwort verraet nichts ueber den
        Bestand, und der eigene Satz ist vom Consent-`403` unterscheidbar."""
        monkeypatch.setattr(settings, "eye_enabled", False)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            "/projects/999/classification-reviews", json=_body(_eye(), _local())
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Die Eye-Auswertung ist nicht aktiviert."

    async def test_the_eye_switch_does_not_block_a_local_review(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", False)
        monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
        project = await self._ready_project(db_session, consent=True)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_cloud(), _local())
        )

        assert response.status_code == 201

    async def test_an_unknown_project_is_404(
        self, authenticated_api_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            "/projects/999/classification-reviews", json=_body(_local(), _eye())
        )

        assert response.status_code == 404

    async def test_without_a_successful_scoring_run_is_409(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_local(), _local())
        )

        assert response.status_code == 409

    async def test_without_the_confirmed_gate_is_409(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await _make_project(db_session)
        await _add_successful_run(db_session, project, gate_confirmed=False)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_local(), _local())
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "Bestaetige zuerst das Ausschuss-Gate."

    async def test_a_running_review_is_409(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        monkeypatch.setattr(reviews_api, "eye_service_is_healthy", _healthy)
        project = await self._ready_project(db_session)
        user = await _make_user(db_session)
        await _make_review(db_session, project, user, status=ScanStatus.RUNNING)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_eye(), _local())
        )

        assert response.status_code == 409

    async def test_a_finished_review_does_not_block_a_new_one(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        monkeypatch.setattr(reviews_api, "eye_service_is_healthy", _healthy)
        project = await self._ready_project(db_session)
        user = await _make_user(db_session)
        await _make_review(db_session, project, user, status=ScanStatus.FAILED)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_eye(), _local())
        )

        assert response.status_code == 201

    async def test_cloud_without_consent_is_403_after_the_gate_checks(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """Die Reihenfolge ist beobachtbar: ohne Ausschusslauf kommt `409`, obwohl auch die
        Einwilligung fehlt."""
        project = await _make_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_cloud(), _local())
        )

        assert response.status_code == 409

    async def test_cloud_without_consent_on_a_ready_project_is_403(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await self._ready_project(db_session, consent=False)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_cloud(), _local())
        )

        assert response.status_code == 403

    async def test_an_unhealthy_eye_service_is_503_and_changes_nothing(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Der Gesundheitscheck steht VOR dem Einreihen: keine Zeile, kein Job, kein Job, der
        garantiert scheitert."""
        monkeypatch.setattr(settings, "eye_enabled", True)
        monkeypatch.setattr(reviews_api, "eye_service_is_healthy", _unhealthy)
        project = await self._ready_project(db_session)
        fake = FakeEnqueuer()
        app.dependency_overrides[get_job_enqueuer] = lambda: fake

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_eye(), _local(), sample_size=201)
        )

        assert response.status_code == 503
        assert fake.calls == []
        count = await db_session.execute(
            select(ClassificationReview).where(ClassificationReview.project_id == project.id)
        )
        assert count.scalars().all() == []

    async def test_two_identical_sides_are_422(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project = await self._ready_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_local(), _local())
        )

        assert response.status_code == 422

    async def test_two_eye_sides_with_the_same_version_are_422(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        monkeypatch.setattr(reviews_api, "eye_service_is_healthy", _healthy)
        project = await self._ready_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(_url(project.id), json=_body(_eye(), _eye()))

        assert response.status_code == 422

    async def test_two_cloud_sides_with_the_same_model_are_422(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
        project = await self._ready_project(db_session, consent=True)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_cloud(), _cloud())
        )

        assert response.status_code == 422

    async def test_an_unknown_model_is_422(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project = await self._ready_project(db_session, consent=True)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_cloud("unbekannt"), _local())
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "Unbekanntes Modell."

    async def test_a_known_model_without_its_key_is_422(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Bekannt, aber nicht ausfuehrbar: die Wahl ist valide, nur nicht bedienbar - und ein
        Lauf ohne Schluessel scheiterte garantiert, also wird er nicht eingereiht."""
        monkeypatch.setattr(settings, "anthropic_api_key", "")
        project = await self._ready_project(db_session, consent=True)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_cloud(), _local())
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "Fuer dieses Modell ist kein API-Schluessel hinterlegt."

    async def test_an_unknown_eye_version_is_422(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        monkeypatch.setattr(reviews_api, "eye_service_is_healthy", _healthy)
        project = await self._ready_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_eye("eye-9.9.9/v1"), _local())
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "Unbekannte Eye-Fassung."

    async def test_an_eye_side_without_a_version_is_422(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        monkeypatch.setattr(reviews_api, "eye_service_is_healthy", _healthy)
        project = await self._ready_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body({"kind": "eye"}, _local())
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("sample_size", [0, 201, -5])
    async def test_a_sample_size_out_of_bounds_is_422(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
        sample_size: int,
    ) -> None:
        project = await self._ready_project(db_session, consent=True)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_cloud(), _local(), sample_size=sample_size)
        )

        assert response.status_code == 422
        assert "Pruefgraesse" in response.json()["detail"]

    @pytest.mark.parametrize("size", [1, 200])
    async def test_the_bounds_are_inclusive(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
        size: int,
    ) -> None:
        monkeypatch.setattr(settings, "eye_enabled", True)
        monkeypatch.setattr(reviews_api, "eye_service_is_healthy", _healthy)
        project = await self._ready_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_local(), _eye(), sample_size=size)
        )

        assert response.status_code == 201

    @pytest.mark.parametrize("sample_size", ["30", 30.5, True, None, _OMITTED])
    async def test_a_wrongly_typed_sample_size_is_a_schema_422(
        self,
        authenticated_api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
        sample_size: Any,
    ) -> None:
        """S9: `StrictInt` - `"30"` und `true` werden NICHT zu 30 und 1, und ein fehlendes Feld
        bleibt ein Fehler; die Vorgabe 30 ist eine Vorbelegung der Oberflaeche."""
        monkeypatch.setattr(settings, "eye_enabled", True)
        monkeypatch.setattr(reviews_api, "eye_service_is_healthy", _healthy)
        project = await self._ready_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_local(), _eye(), sample_size=sample_size)
        )

        assert response.status_code == 422

    async def test_an_extra_body_field_is_rejected(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        """S8: kein Betrags-, Preis- oder Kostenfeld - ein mitgeschickter Betrag ist ein Fehler,
        kein stiller Vorschlag."""
        project = await self._ready_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id), json=_body(_local(), _eye(), estimated_cost_usd=0.0)
        )

        assert response.status_code == 422

    async def test_an_extra_side_field_is_rejected(
        self, authenticated_api_client: httpx.AsyncClient, db_session: AsyncSession
    ) -> None:
        project = await self._ready_project(db_session)
        app.dependency_overrides[get_job_enqueuer] = lambda: FakeEnqueuer()

        response = await authenticated_api_client.post(
            _url(project.id),
            json=_body(
                {"kind": "cloud", "model": ANTHROPIC_VISION_MODEL, "provider": "mistral"}, _local()
            ),
        )

        assert response.status_code == 422

    async def test_the_create_requires_a_token(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post(_url(1), json=_body(_local(), _eye()))

        assert response.status_code == 401
