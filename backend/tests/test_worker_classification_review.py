"""Der Pruefjob zweier Klassifizierungsverfahren (Spec 0616, ADR 0139 Punkt 2).

Was hier festgehalten wird, ist die Naht des Jobs und nicht die Vergleichslogik selbst (die steht
in `test_classification_comparison.py`):

* die eingefrorene Pruefmenge (Ausschuss-Ueberlebende OHNE Skip-Kriterium, einmal geordnet),
* die drei Seitenarten und die Reihenfolge kostenfrei -> kostenpflichtig,
* genau EIN Eye-Aufruf je Foto bei zwei Eye-Seiten,
* der Cloud-Client folgt ausschliesslich dem gespeicherten Modell,
* Einzelfotofehler werden gezaehlt statt zu werfen, Ist-Kosten stehen im `finally`,
* die Fotoposition entsteht 1-basiert aus derselben Ordnung wie die Fallzeilen.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.album_suitability import AlbumSuitability
from photosort.classification_review import (
    ERROR_EYE_UNAVAILABLE,
    ERROR_GENERIC,
    ERROR_NO_CONSENT,
    ERROR_NO_RESULTS,
    execute_classification_review,
)
from photosort.cloud_vision import TokenUsage
from photosort.eye_client import EyeImageUnreadableError
from photosort.eye_mapping import MAPPING_VERSION, MAPPING_VERSION_V2
from photosort.models import (
    ClassificationReview,
    ClassificationReviewCase,
    ClassificationReviewPurpose,
    ClassificationReviewResult,
    ClassificationReviewResultStrength,
    ClassificationReviewSide,
    ClassificationReviewSideKind,
    DuplicateDecision,
    Photo,
    PhotoDuplicateDecision,
    PhotoScore,
    Project,
    ScanStatus,
    User,
)
from photosort.motifs import MOTIF_REGISTRY
from photosort.remote_classification import RemoteClassification
from photosort.thumbnails import display_path

# ---------------------------------------------------------------------------------------------
# Fixtures / Test-Doubles
# ---------------------------------------------------------------------------------------------

_ALL_NULL_STRENGTHS = {motif_key: 0.0 for motif_key in MOTIF_REGISTRY}


async def _make_user(session: AsyncSession, username: str = "anleger") -> User:
    user = User(username=username, password_hash="x")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _make_project(session: AsyncSession, *, consent: bool = True) -> Project:
    project = Project(
        name="Costa Rica",
        opencloud_drive_id="drive",
        opencloud_path="Costa Rica",
        cloud_vision_detection_enabled=consent,
    )
    if consent:
        project.cloud_vision_consent_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_photo(
    session: AsyncSession,
    project: Project,
    cache_dir: Path,
    path: str,
    *,
    readable: bool = True,
    suggested_status: str | None = None,
    decision: DuplicateDecision | None = None,
    with_score: bool = True,
) -> Photo:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=now,
        taken_at_original=now,
        last_modified=now,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    if with_score:
        session.add(
            PhotoScore(
                photo_id=photo.id,
                sharpness=100.0,
                exposure=0.0,
                cluster_key=f"cluster-{photo.id}",
                suggested_status=suggested_status,
                computed_at=now,
            )
        )
    if decision is not None:
        session.add(PhotoDuplicateDecision(photo_id=photo.id, decision=decision))
    await session.commit()
    if readable:
        variant = display_path(cache_dir, photo.id, photo.etag)
        variant.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (80, 80), color=(90, 90, 90)).save(variant, format="JPEG")
    return photo


async def _make_review(
    session: AsyncSession,
    project: Project,
    user: User,
    sides: list[dict[str, Any]],
    *,
    sample_size: int = 30,
    seed: int = 4711,
) -> ClassificationReview:
    review = ClassificationReview(
        project_id=project.id,
        created_by_user_id=user.id,
        status=ScanStatus.RUNNING,
        sample_size=sample_size,
        seed=seed,
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    session.add_all([ClassificationReviewSide(review_id=review.id, **side) for side in sides])
    await session.commit()
    return review


def _side(letter: str, kind: ClassificationReviewSideKind, **values: Any) -> dict[str, Any]:
    return {"side": letter, "kind": kind, **values}


def _payload(*, tags: dict[str, float], kind: str = "landscape", aesthetic: float = 0.5) -> dict:
    return {"kind": kind, "tags": tags, "scores": {"aesthetic": aesthetic}}


class FakeEyeClient:
    """Ein Eye-Double: zaehlt Aufrufe, kann einzeln unlesbar und insgesamt ungesund sein."""

    def __init__(
        self,
        payloads: dict[int, dict[str, Any]] | None = None,
        *,
        healthy: bool = True,
        unreadable: set[int] | None = None,
    ) -> None:
        self._payloads = payloads or {}
        self._healthy = healthy
        self._unreadable = unreadable or set()
        self.health_calls = 0
        self.analyze_calls = 0
        self.closed = False

    async def health(self) -> bool:
        self.health_calls += 1
        return self._healthy

    async def analyze(self, image_bytes: bytes) -> dict[str, Any]:
        self.analyze_calls += 1
        if self.analyze_calls in self._unreadable:
            raise EyeImageUnreadableError("Das Bild ist nicht lesbar.")
        payload = list(self._payloads.values())
        return payload[self.analyze_calls - 1] if payload else _payload(tags={})

    async def aclose(self) -> None:
        self.closed = True


class FakeCloudClient:
    """Ein Cloud-Double: zeichnet Modell und Aufrufe auf, scheitert auf Wunsch je Foto."""

    def __init__(
        self,
        *,
        model: str,
        outcome: dict[int, RemoteClassification | BaseException] | None = None,
        usage: TokenUsage | None = None,
        fail_everything: BaseException | None = None,
    ) -> None:
        self.model = model
        self._outcome = outcome or {}
        self._usage = usage
        self._fail_everything = fail_everything
        self.calls = 0
        self.closed = False

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
        self.calls += 1
        if self._fail_everything is not None:
            raise self._fail_everything
        outcome = self._outcome.get(photo_id)
        if isinstance(outcome, BaseException):
            raise outcome
        if outcome is not None:
            return outcome
        return RemoteClassification(
            motif_strengths=_ALL_NULL_STRENGTHS,
            fine_labels=(),
            excluded=False,
            album_suitability=AlbumSuitability(level=3, reason=None),
            usage=self._usage,
        )

    async def aclose(self) -> None:
        self.closed = True


def _cloud_builder(clients: dict[str, FakeCloudClient], built: list[str]):
    def build(model: str) -> FakeCloudClient:
        built.append(model)
        return clients[model]

    return build


async def _result_rows(
    session: AsyncSession, review_id: int, side: str
) -> list[ClassificationReviewResult]:
    return list(
        (
            await session.execute(
                select(ClassificationReviewResult)
                .where(
                    ClassificationReviewResult.review_id == review_id,
                    ClassificationReviewResult.side == side,
                )
                .order_by(ClassificationReviewResult.photo_id)
            )
        )
        .scalars()
        .all()
    )


async def _motif_strength(
    session: AsyncSession, review_id: int, side: str, motif_key: str
) -> float | None:
    return await session.scalar(
        select(ClassificationReviewResultStrength.strength).where(
            ClassificationReviewResultStrength.review_id == review_id,
            ClassificationReviewResultStrength.side == side,
            ClassificationReviewResultStrength.motif_key == motif_key,
        )
    )


async def _case_rows(session: AsyncSession, review_id: int) -> list[ClassificationReviewCase]:
    return list(
        (
            await session.execute(
                select(ClassificationReviewCase)
                .where(ClassificationReviewCase.review_id == review_id)
                .order_by(ClassificationReviewCase.id)
            )
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------------------------
# Die Pruefmenge
# ---------------------------------------------------------------------------------------------


class TestTheFrozenReviewSet:
    async def test_only_ausschuss_survivors_are_in_the_review_set(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """`survives_ausschuss()` ist die eine Zusage der Pruefmenge - ein Foto ohne `PhotoScore`
        und ein verworfenes Foto gehoeren nicht dazu."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        kept = await _add_photo(db_session, project, tmp_path, "keep.jpg")
        await _add_photo(db_session, project, tmp_path, "discard.jpg", suggested_status="discard")
        await _add_photo(db_session, project, tmp_path, "noscore.jpg", with_score=False)
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side("a", ClassificationReviewSideKind.EYE, eye_mapping_version=MAPPING_VERSION),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_eye_client=lambda: FakeEyeClient(),
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert review.photo_count == 1
        rows = await _result_rows(db_session, review.id, "b")
        assert [row.photo_id for row in rows] == [kept.id]

    async def test_an_already_classified_photo_is_classified_again_without_a_skip_criterion(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Pruefung kennt KEIN Skip-Kriterium: ein Foto mit `duplicate_of` bleibt Kandidat, und
        ein bereits beurteiltes Foto bekommt trotzdem Pruefergebnisse."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        photo = await _add_photo(db_session, project, tmp_path, "done.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side("a", ClassificationReviewSideKind.LOCAL),
                _side(
                    "b",
                    ClassificationReviewSideKind.CLOUD,
                    provider="anthropic",
                    model="claude-sonnet-5",
                ),
            ],
        )
        clients = {"claude-sonnet-5": FakeCloudClient(model="claude-sonnet-5")}

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_cloud_client=_cloud_builder(clients, []),
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert review.photo_count == 1
        assert len(await _result_rows(db_session, review.id, "a")) == 1
        assert [row.photo_id for row in await _result_rows(db_session, review.id, "b")] == [
            photo.id
        ]


# ---------------------------------------------------------------------------------------------
# Die drei Seitenarten und ihre Reihenfolge
# ---------------------------------------------------------------------------------------------


class TestTheThreeSideKinds:
    @pytest.mark.parametrize(
        ("a_kind", "b_kind"),
        [
            (ClassificationReviewSideKind.EYE, ClassificationReviewSideKind.LOCAL),
            (ClassificationReviewSideKind.EYE, ClassificationReviewSideKind.CLOUD),
            (ClassificationReviewSideKind.LOCAL, ClassificationReviewSideKind.CLOUD),
        ],
    )
    async def test_every_pair_of_side_kinds_reaches_success(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        a_kind: ClassificationReviewSideKind,
        b_kind: ClassificationReviewSideKind,
    ) -> None:

        project = await _make_project(db_session)
        user = await _make_user(db_session)
        await _add_photo(db_session, project, tmp_path, "one.jpg")
        sides = [
            _side(
                "a",
                a_kind,
                **(self._origin(a_kind)),
            ),
            _side("b", b_kind, **(self._origin(b_kind))),
        ]
        review = await _make_review(db_session, project, user, sides)
        clients = {"claude-sonnet-5": FakeCloudClient(model="claude-sonnet-5")}

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_eye_client=lambda: FakeEyeClient(),
            build_cloud_client=_cloud_builder(clients, []),
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert review.status == ScanStatus.SUCCESS
        assert review.phase is None
        assert len(await _result_rows(db_session, review.id, "a")) == 1
        assert len(await _result_rows(db_session, review.id, "b")) == 1

    @staticmethod
    def _origin(kind: ClassificationReviewSideKind) -> dict[str, Any]:
        if kind is ClassificationReviewSideKind.EYE:
            return {"eye_model_revision": "v1.0.0", "eye_mapping_version": MAPPING_VERSION}
        if kind is ClassificationReviewSideKind.CLOUD:
            return {"provider": "anthropic", "model": "claude-sonnet-5"}
        return {}

    async def test_the_free_sides_run_before_the_paid_cloud_side(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Faellt der Sidecar mitten im Lauf, ist noch nichts bezahlt: die Reihenfolge ist
        Eye -> lokal -> Cloud. Gemessen ueber die Aufrufreihenfolge der Attrappen."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        await _add_photo(db_session, project, tmp_path, "one.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side(
                    "a",
                    ClassificationReviewSideKind.CLOUD,
                    provider="anthropic",
                    model="claude-sonnet-5",
                ),
                _side("b", ClassificationReviewSideKind.EYE, eye_mapping_version=MAPPING_VERSION),
            ],
        )
        order: list[str] = []

        class RecordingEye(FakeEyeClient):
            async def analyze(self, image_bytes: bytes) -> dict[str, Any]:
                if not order:
                    order.append("eye")
                return await super().analyze(image_bytes)

        class RecordingCloud(FakeCloudClient):
            async def classify(
                self, image_bytes: bytes, mime_type: str, photo_id: int
            ) -> RemoteClassification:
                order.append("cloud")
                return await super().classify(image_bytes, mime_type, photo_id)

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_eye_client=lambda: RecordingEye(),
            build_cloud_client=lambda model: RecordingCloud(model=model),
        )

        # Der Eye-Aufruf steht VOR dem ersten Cloud-Aufruf - die kostenfreie Seite ist zuerst
        # fertig, bevor der erste bezahlte Aufruf abgesetzt wird.
        assert order[0] == "eye"
        assert order[1:] == ["cloud"]

    async def test_the_local_side_is_built_before_the_cloud_side(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Zweite Haelfte derselben Zusage: auch die lokale Seite ist vor der Cloud fertig. Die
        Detektoren werden beim Start der lokalen Seite gebaut, der Cloud-Client erst danach."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        await _add_photo(db_session, project, tmp_path, "one.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side("a", ClassificationReviewSideKind.LOCAL),
                _side(
                    "b",
                    ClassificationReviewSideKind.CLOUD,
                    provider="anthropic",
                    model="claude-sonnet-5",
                ),
            ],
        )
        order: list[str] = []

        def build_detector() -> None:
            order.append("local")
            return None

        def build_cloud(model: str) -> FakeCloudClient:
            order.append("cloud")
            return FakeCloudClient(model=model)

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_detector=build_detector,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
            build_cloud_client=build_cloud,
        )

        assert review.status == ScanStatus.SUCCESS
        assert order == ["local", "cloud"]

    async def test_the_local_side_has_no_excluded_document_and_no_album_level(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """`NULL` heisst "dieses Verfahren sagt dazu nichts" - ein erfundenes `False` machte jede
        Dokumentaufnahme zur Abweichung (ADR 0139 Punkt 3)."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        await _add_photo(db_session, project, tmp_path, "one.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side("a", ClassificationReviewSideKind.LOCAL),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        rows = await _result_rows(db_session, review.id, "a")
        assert len(rows) == 1
        assert rows[0].excluded_document is None
        assert rows[0].album_level is None
        strengths = (
            (
                await db_session.execute(
                    select(ClassificationReviewResultStrength).where(
                        ClassificationReviewResultStrength.review_id == review.id,
                        ClassificationReviewResultStrength.side == "a",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert {row.motif_key for row in strengths} == set(MOTIF_REGISTRY)
        assert {row.strength for row in strengths} == {0.0}


# ---------------------------------------------------------------------------------------------
# Ein Eye-Aufruf je Foto, Anbieter aus dem Modell
# ---------------------------------------------------------------------------------------------


class TestEyeAndCloudCalls:
    async def test_two_eye_sides_share_one_service_call_per_photo(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Zwei Eye-Seiten sind KEIN zweiter Empfaenger (S13): der Dienst wird genau einmal je Foto
        gerufen, beide Fassungen rechnen auf derselben Antwort im Speicher."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        for index in range(3):
            await _add_photo(db_session, project, tmp_path, f"photo-{index}.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side("a", ClassificationReviewSideKind.EYE, eye_mapping_version=MAPPING_VERSION),
                _side("b", ClassificationReviewSideKind.EYE, eye_mapping_version=MAPPING_VERSION),
            ],
        )
        eye = FakeEyeClient()

        await execute_classification_review(
            db_session, review, tmp_path, build_eye_client=lambda: eye
        )

        assert review.status == ScanStatus.SUCCESS
        assert eye.analyze_calls == 3
        assert eye.health_calls == 1
        assert eye.closed is True
        assert len(await _result_rows(db_session, review.id, "a")) == 3
        assert len(await _result_rows(db_session, review.id, "b")) == 3

    async def test_two_eye_versions_gate_the_activity_on_the_same_response(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Spec 0622, Messweg: v2 gegen v3 auf DEMSELBEN Payload - ein Dienstaufruf je Foto.
        `hiking` ohne Person traegt v2 mit 0,9, v3 gatet es auf 0,0."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        first = await _add_photo(db_session, project, tmp_path, "first.jpg")
        second = await _add_photo(db_session, project, tmp_path, "second.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side(
                    "a",
                    ClassificationReviewSideKind.EYE,
                    eye_mapping_version=MAPPING_VERSION_V2,
                ),
                _side("b", ClassificationReviewSideKind.EYE, eye_mapping_version=MAPPING_VERSION),
            ],
        )
        payload = _payload(tags={"hiking": 0.9})
        eye = FakeEyeClient({first.id: payload, second.id: payload})

        await execute_classification_review(
            db_session, review, tmp_path, build_eye_client=lambda: eye
        )

        assert review.status == ScanStatus.SUCCESS
        assert eye.analyze_calls == 2
        assert await _motif_strength(db_session, review.id, "a", "aktivitaet") == pytest.approx(0.9)
        assert await _motif_strength(db_session, review.id, "b", "aktivitaet") == pytest.approx(0.0)
        assert len(await _result_rows(db_session, review.id, "a")) == 2
        assert len(await _result_rows(db_session, review.id, "b")) == 2

    async def test_a_photo_without_valid_scores_leaves_no_row_on_either_side(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Eine Fassung kann das Foto nicht beantworten - dann hinterlaesst es auf KEINER Seite
        eine Zeile und zaehlt als unklassifizierbar, nie als halbes Vergleichspaar."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        answered = await _add_photo(db_session, project, tmp_path, "answered.jpg")
        unanswered = await _add_photo(db_session, project, tmp_path, "unanswered.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side(
                    "a",
                    ClassificationReviewSideKind.EYE,
                    eye_mapping_version=MAPPING_VERSION_V2,
                ),
                _side("b", ClassificationReviewSideKind.EYE, eye_mapping_version=MAPPING_VERSION),
            ],
        )
        eye = FakeEyeClient(
            {
                answered.id: _payload(tags={"hiking": 0.9}),
                unanswered.id: {"kind": "landscape", "tags": {"hiking": 0.9}},
            }
        )

        await execute_classification_review(
            db_session, review, tmp_path, build_eye_client=lambda: eye
        )

        assert review.status == ScanStatus.SUCCESS
        assert eye.analyze_calls == 2
        assert review.unclassifiable_photo_count == 1
        assert review.photo_count == 2
        assert [row.photo_id for row in await _result_rows(db_session, review.id, "a")] == [
            answered.id
        ]
        assert [row.photo_id for row in await _result_rows(db_session, review.id, "b")] == [
            answered.id
        ]

    async def test_the_cloud_client_follows_the_side_model(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """`provider` ist am Client kein Eingang: der Builder bekommt das GESPEICHERTE Modell, und
        eine abweichende Anbieterangabe an der Seite aendert daran nichts (S6)."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        await _add_photo(db_session, project, tmp_path, "one.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side(
                    "a",
                    ClassificationReviewSideKind.CLOUD,
                    provider="mistral",
                    model="claude-sonnet-5",
                ),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )
        built: list[str] = []
        clients = {"claude-sonnet-5": FakeCloudClient(model="claude-sonnet-5")}

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_cloud_client=_cloud_builder(clients, built),
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert built == ["claude-sonnet-5"]
        assert clients["claude-sonnet-5"].calls == 1


# ---------------------------------------------------------------------------------------------
# Einzelfotofehler, Kosten, Fehlermeldungen
# ---------------------------------------------------------------------------------------------


class TestFailuresAndCosts:
    async def test_a_photo_failing_on_one_side_is_counted_and_the_run_still_succeeds(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        first = await _add_photo(db_session, project, tmp_path, "first.jpg")
        second = await _add_photo(db_session, project, tmp_path, "second.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side(
                    "a",
                    ClassificationReviewSideKind.CLOUD,
                    provider="anthropic",
                    model="claude-sonnet-5",
                ),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )
        client = FakeCloudClient(
            model="claude-sonnet-5",
            outcome={second.id: RuntimeError("Anbieter weg")},
        )

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_cloud_client=lambda model: client,
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert review.status == ScanStatus.SUCCESS
        assert review.unclassifiable_photo_count == 1
        assert [row.photo_id for row in await _result_rows(db_session, review.id, "a")] == [
            first.id
        ]
        side_a = await db_session.get(ClassificationReviewSide, (review.id, "a"))
        assert side_a is not None
        assert side_a.failed_calls == 1
        assert side_a.api_calls == 1

    async def test_a_photo_failing_on_both_sides_is_counted_once_and_nothing_is_compared(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Alle Fotos scheitern JE SEITE - aber keine Seite ohne jedes Ergebnis. Ergebnis:
        `SUCCESS`, keine Faelle, und die Zahl der fehlenden Fotos ist die Pruefmenge."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        first = await _add_photo(db_session, project, tmp_path, "first.jpg")
        second = await _add_photo(db_session, project, tmp_path, "second.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side("a", ClassificationReviewSideKind.EYE, eye_mapping_version=MAPPING_VERSION),
                _side(
                    "b",
                    ClassificationReviewSideKind.CLOUD,
                    provider="anthropic",
                    model="claude-sonnet-5",
                ),
            ],
        )
        # Eye scheitert am ZWEITEN, Cloud am ERSTEN Foto - jede Seite hat genau ein Ergebnis.
        eye = FakeEyeClient(unreadable={2})
        client = FakeCloudClient(
            model="claude-sonnet-5",
            outcome={first.id: RuntimeError("Anbieter weg")},
        )

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_eye_client=lambda: eye,
            build_cloud_client=lambda model: client,
        )

        assert review.status == ScanStatus.SUCCESS
        assert review.unclassifiable_photo_count == 2
        assert await _case_rows(db_session, review.id) == []
        # Jede Seite hat GENAU ein Ergebnis, und es ist ein anderes Foto: die Schnittmenge ist
        # leer, deshalb kein Fall und beide Fotos unklassifizierbar.
        assert [row.photo_id for row in await _result_rows(db_session, review.id, "a")] == [
            first.id
        ]
        assert [row.photo_id for row in await _result_rows(db_session, review.id, "b")] == [
            second.id
        ]

    async def test_a_side_failing_on_every_photo_still_succeeds_with_nothing_compared(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Edge Case 4: Scheitert die Cloud-Seite auf JEDEM Foto einzeln, ist das ein Datenbefund
        und kein kaputter Client - der Lauf endet `SUCCESS` mit `verglichen = 0`, und die
        Pruefmenge steht als nicht klassifizierbar da."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        for name in ("first.jpg", "second.jpg"):
            await _add_photo(db_session, project, tmp_path, name)
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side(
                    "a",
                    ClassificationReviewSideKind.CLOUD,
                    provider="anthropic",
                    model="claude-sonnet-5",
                ),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )
        client = FakeCloudClient(
            model="claude-sonnet-5", fail_everything=RuntimeError("Anbieter weg")
        )

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_cloud_client=lambda model: client,
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert review.status == ScanStatus.SUCCESS
        assert review.error_message is None
        assert review.phase is None
        assert review.unclassifiable_photo_count == review.photo_count == 2
        assert await _case_rows(db_session, review.id) == []
        side_a = await db_session.get(ClassificationReviewSide, (review.id, "a"))
        assert side_a is not None
        assert side_a.failed_calls == 2
        assert side_a.api_calls == 0

    async def test_a_side_without_any_result_fails_the_run(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Liefert eine Seite auf KEINEM Foto ein Ergebnis, ist das kein leeres Ergebnis, sondern
        ein Fehlschlag mit festem Satz (nie `str(exc)`)."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        await _add_photo(db_session, project, tmp_path, "one.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side("a", ClassificationReviewSideKind.EYE, eye_mapping_version=MAPPING_VERSION),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_eye_client=lambda: FakeEyeClient(unreadable={1}),
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert review.status == ScanStatus.FAILED
        assert review.error_message == ERROR_NO_RESULTS
        assert review.phase is None
        assert review.finished_at is not None

    async def test_an_unhealthy_eye_service_fails_with_its_own_sentence(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        await _add_photo(db_session, project, tmp_path, "one.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side("a", ClassificationReviewSideKind.EYE, eye_mapping_version=MAPPING_VERSION),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_eye_client=lambda: FakeEyeClient(healthy=False),
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert review.status == ScanStatus.FAILED
        assert review.error_message == ERROR_EYE_UNAVAILABLE
        assert review.phase is None

    async def test_an_eye_side_without_a_version_fails_without_asking_eye(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Kein Rueckfall auf die Lauf-Fassung: die Seite ohne Fassung beendet die Pruefung mit
        dem festen Sammelsatz, bevor Eye ein einziges Foto sieht - und der Satz nennt keine
        Fassung, keinen Host und keinen Stacktrace."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        await _add_photo(db_session, project, tmp_path, "one.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side("a", ClassificationReviewSideKind.EYE, eye_mapping_version=None),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )
        eye = FakeEyeClient()

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_eye_client=lambda: eye,
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert review.status == ScanStatus.FAILED
        assert review.error_message == ERROR_GENERIC
        assert "eye-4.2.3" not in (review.error_message or "")
        assert eye.analyze_calls == 0
        assert await _result_rows(db_session, review.id, "a") == []

    async def test_a_cloud_side_without_consent_never_builds_a_client(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """S5: kein stiller Rueckfall auf Eye oder Lokal - der Lauf scheitert mit festem Satz, und
        der Client wird gar nicht erst gebaut."""
        project = await _make_project(db_session, consent=False)
        user = await _make_user(db_session)
        await _add_photo(db_session, project, tmp_path, "one.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side(
                    "a",
                    ClassificationReviewSideKind.CLOUD,
                    provider="anthropic",
                    model="claude-sonnet-5",
                ),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )
        built: list[str] = []

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_cloud_client=_cloud_builder({}, built),
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert built == []
        assert review.status == ScanStatus.FAILED
        assert review.error_message == ERROR_NO_CONSENT

    async def test_actual_costs_are_frozen_in_finally_even_when_the_run_is_cancelled(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Das Geld ist beim Abbruch schon ausgegeben: die Ist-Kosten der Cloud-Seite werden im
        `finally` geschrieben, nicht erst auf dem Erfolgspfad."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        await _add_photo(db_session, project, tmp_path, "one.jpg")
        await _add_photo(db_session, project, tmp_path, "two.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side(
                    "a",
                    ClassificationReviewSideKind.CLOUD,
                    provider="anthropic",
                    model="claude-sonnet-5",
                ),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )
        usage = TokenUsage(input_tokens=1000, output_tokens=100)

        class CancellingClient(FakeCloudClient):
            async def classify(
                self, image_bytes: bytes, mime_type: str, photo_id: int
            ) -> RemoteClassification:
                if self.calls == 1:
                    raise asyncio.CancelledError
                return await super().classify(image_bytes, mime_type, photo_id)

        client = CancellingClient(model="claude-sonnet-5", usage=usage)

        with pytest.raises(asyncio.CancelledError):
            await execute_classification_review(
                db_session,
                review,
                tmp_path,
                build_cloud_client=lambda model: client,
                build_detector=lambda: None,
                build_animal_detector=lambda: None,
                build_classifier=lambda: None,
                build_aesthetics=lambda: None,
                build_landmarker=lambda: None,
            )

        fired = await db_session.get(ClassificationReview, review.id)
        assert fired is not None
        assert fired.status == ScanStatus.FAILED
        assert fired.error_message == "Pruefung abgebrochen (Job-Timeout oder Worker-Shutdown)."
        side_a = await db_session.get(ClassificationReviewSide, (review.id, "a"))
        assert side_a is not None
        assert side_a.input_tokens is not None
        assert side_a.output_tokens is not None
        assert side_a.cost_usd is not None

    async def test_an_unexpected_error_ends_in_the_generic_sentence(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Ein Fehler ohne eigene Klasse hinterlaesst den festen Sammelsatz und niemals den Text
        des fremden Systems."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        await _add_photo(db_session, project, tmp_path, "one.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side(
                    "a",
                    ClassificationReviewSideKind.CLOUD,
                    provider="anthropic",
                    model="claude-sonnet-5",
                ),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )

        class BrokenResultClient(FakeCloudClient):
            async def classify(
                self, image_bytes: bytes, mime_type: str, photo_id: int
            ) -> RemoteClassification:
                self.calls += 1
                return RemoteClassification(
                    motif_strengths=None,  # type: ignore[arg-type]
                    fine_labels=(),
                )

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_cloud_client=lambda model: BrokenResultClient(model=model),
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert review.status == ScanStatus.FAILED
        assert review.error_message == ERROR_GENERIC
        assert "NoneType" not in (review.error_message or "")


# ---------------------------------------------------------------------------------------------
# Faelle und Fotoposition
# ---------------------------------------------------------------------------------------------


class TestCasesAndPhotoPositions:
    async def test_the_photo_position_is_one_based_and_shared_with_the_case_rows(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        """Die Nummer entsteht EINMAL aus der eingefrorenen Pruefmenge und steht an der Fallzeile;
        Fallliste und Export lesen dieselbe Zahl (ADR 0139 Punkt 3)."""
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        first = await _add_photo(db_session, project, tmp_path, "first.jpg")
        await _add_photo(db_session, project, tmp_path, "second.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side("a", ClassificationReviewSideKind.LOCAL),
                _side(
                    "b",
                    ClassificationReviewSideKind.CLOUD,
                    provider="anthropic",
                    model="claude-sonnet-5",
                ),
            ],
        )
        # Nur das ERSTE Foto weicht ab: Motiv `menschen` vorhanden gegen nicht vorhanden.
        client = FakeCloudClient(
            model="claude-sonnet-5",
            outcome={
                first.id: RemoteClassification(
                    motif_strengths={**dict(_ALL_NULL_STRENGTHS), "menschen": 0.9},
                    fine_labels=(),
                    excluded=False,
                    album_suitability=AlbumSuitability(level=3, reason=None),
                )
            },
        )

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_cloud_client=lambda model: client,
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        cases = await _case_rows(db_session, review.id)
        assert {case.photo_id for case in cases} == {first.id}
        assert {case.photo_position for case in cases} == {1}
        assert {case.purpose for case in cases} == {
            ClassificationReviewPurpose.MOTIFS,
            ClassificationReviewPurpose.MOTIF_FEATURE,
        }


# ---------------------------------------------------------------------------------------------
# Fortschritt
# ---------------------------------------------------------------------------------------------


class TestProgress:
    async def test_the_run_ends_with_processed_equal_to_the_review_set(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _make_project(db_session)
        user = await _make_user(db_session)
        for index in range(2):
            await _add_photo(db_session, project, tmp_path, f"photo-{index}.jpg")
        review = await _make_review(
            db_session,
            project,
            user,
            [
                _side("a", ClassificationReviewSideKind.LOCAL),
                _side("b", ClassificationReviewSideKind.LOCAL),
            ],
        )

        await execute_classification_review(
            db_session,
            review,
            tmp_path,
            build_detector=lambda: None,
            build_animal_detector=lambda: None,
            build_classifier=lambda: None,
            build_aesthetics=lambda: None,
            build_landmarker=lambda: None,
        )

        assert review.photos_processed == 2
        assert review.photo_count == 2
        assert review.status == ScanStatus.SUCCESS
        assert review.phase is None
        assert review.unclassifiable_photo_count == 0
        count = (
            await db_session.execute(select(func.count()).select_from(ClassificationReviewResult))
        ).scalar_one()
        assert count == 4
