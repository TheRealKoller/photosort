"""Spec 0609 / ADR 0138 Punkt 4 und 6 - die Eye-Phase im Klassifizierungslauf.

Was hier festgehalten wird, ist die NAHT zwischen Sidecar und Datenbank und nicht die Abbildung
selbst (die steht in test_eye_mapping.py):

* Schattenzeilen entstehen fuer JEDES ueberlebende, lesbare Foto - auch fuer Fotos mit
  Cloud-Kopfzeile, deren Cloud-Ergebnis dabei unberuehrt bleibt.
* Die Rangfolge setzt `upsert_assessment` durch; die Phase entscheidet sie nicht selbst.
* Ein Fehlschlag des Dienstes laesst NICHTS zurueck: keine Schattenzeile, keine Promotion.
* Ein einzelnes unlesbares Bild ist dagegen kein Fehlschlag des Laufs.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker as worker
from photosort.models import (
    ClassificationMode,
    ClassificationPhase,
    CriterionScoringRun,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoEyeFineLabel,
    PhotoEyeMotifStrength,
    PhotoEyeResult,
    PhotoFineLabel,
    PhotoLocalMotifSnapshot,
    PhotoMotifAssessment,
    PhotoMotifStrength,
    PhotoScore,
    Project,
    ScanStatus,
    ScoringRun,
)
from photosort.motif_strengths import upsert_assessment
from photosort.motifs import MOTIF_REGISTRY
from photosort.thumbnails import display_path
from photosort.worker import run_classification

# ---------------------------------------------------------------------------------------------
# Fixtures / Test-Doubles
# ---------------------------------------------------------------------------------------------


async def _make_project(session: AsyncSession, *, consent: bool = False) -> Project:
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


async def _add_run(session: AsyncSession, project: Project) -> ScoringRun:
    scoring_run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(scoring_run)
    await session.commit()
    await session.refresh(scoring_run)
    return scoring_run


async def _add_photo(
    session: AsyncSession, project: Project, path: str, cache_dir: Path, *, readable: bool = True
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
    session.add(
        PhotoScore(
            photo_id=photo.id,
            sharpness=100.0,
            exposure=0.0,
            cluster_key=f"cluster-{photo.id}",
            suggested_status=None,
            computed_at=now,
        )
    )
    await session.commit()
    if readable:
        variant = display_path(cache_dir, photo.id, photo.etag)
        variant.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (160, 160), color=(100, 100, 100)).save(variant, format="JPEG")
    return photo


def _payload(
    *,
    confidences: dict[str, float] | None = None,
    kind: str = "landscape",
    aesthetic: float = 0.5,
) -> dict[str, Any]:
    return {
        "model": "eye-4.2.3",
        "kind": kind,
        "confidences": {"mountain": 0.91, "sky": 0.7, "dog": 0.66}
        if confidences is None
        else confidences,
        "scores": {"aesthetic": aesthetic, "keeper": 0.6, "cover": 0.3},
        "faces": [],
        "pets": [],
        "details": {"layout": {"shot": {"wide": 0.8, "close_up": 0.2}}},
    }


class FakeEyeClient:
    """Zeichnet Aufrufe auf und kann an einer beliebigen Stelle scheitern."""

    def __init__(
        self,
        payloads: dict[int, dict[str, Any]] | None = None,
        *,
        healthy: bool = True,
        fail_at: int | None = None,
        fail_with: BaseException | None = None,
    ) -> None:
        self._payloads = payloads or {}
        self._healthy = healthy
        self._fail_at = fail_at
        self._fail_with = fail_with
        self.health_calls = 0
        self.analyze_calls = 0
        self.closed = False
        self.max_active = 0
        self._active = 0

    async def health(self) -> bool:
        self.health_calls += 1
        return self._healthy

    async def analyze(self, image_bytes: bytes) -> dict[str, Any]:
        self.analyze_calls += 1
        self._active += 1
        self.max_active = max(self.max_active, self._active)
        try:
            await asyncio.sleep(0)
            if self._fail_at is not None and self.analyze_calls == self._fail_at:
                raise self._fail_with or RuntimeError("Eye weg")
            # Der Reihenfolge nach, nicht nach Foto-ID: der Test kennt die Aufrufreihenfolge.
            payload = list(self._payloads.values())[self.analyze_calls - 1]
            return payload
        finally:
            self._active -= 1

    async def aclose(self) -> None:
        self.closed = True


class ExplodingEyeClient:
    def __init__(self) -> None:
        raise AssertionError("Der Eye-Client wurde gebaut, obwohl Eye nicht laufen darf")


def _exploding_eye_builder() -> NoReturn:
    ExplodingEyeClient()
    raise AssertionError("unreachable")


class _NoDetections:
    def detect(self, image: object) -> object:
        return SimpleNamespace(detections=[], face_landmarks=[], facial_transformation_matrixes=[])


class _NoSceneLabels:
    def classify(self, image: object) -> object:
        return SimpleNamespace(classifications=[SimpleNamespace(categories=[])])


class _NeutralAesthetics:
    def predict(self, batch: object) -> object:
        return np.array([[0.1] * 10], dtype="float32")


class _AngularEmbedder:
    def embed(self, text: str) -> list[float]:
        return [1.0, float(len(text))]


async def _run(
    session: AsyncSession,
    project: Project,
    scoring_run: ScoringRun,
    cache_dir: Path,
    *,
    mode: ClassificationMode | str | None = ClassificationMode.EYE,
    use_cloud: bool | None = None,
    client: object | None = None,
) -> CriterionScoringRun:
    return await run_classification(
        session,
        project,
        scoring_run.id,
        cache_dir,
        mode=ClassificationMode(mode) if isinstance(mode, str) else mode,
        use_cloud=use_cloud,
        build_detector=_NoDetections,
        build_animal_detector=_NoDetections,
        build_classifier=_NoSceneLabels,  # type: ignore[arg-type]
        build_aesthetics=_NeutralAesthetics,  # type: ignore[arg-type]
        build_landmarker=_NoDetections,
        build_embedder=_AngularEmbedder,  # type: ignore[arg-type]
        build_eye_client=(lambda: client) if client is not None else _exploding_eye_builder,  # type: ignore[arg-type]
    )


async def _eye_rows(session: AsyncSession, photo_id: int) -> tuple[PhotoEyeResult, list[float]]:
    result = await session.get(PhotoEyeResult, photo_id)
    assert result is not None
    strengths = (
        (
            await session.execute(
                select(PhotoEyeMotifStrength)
                .where(PhotoEyeMotifStrength.photo_id == photo_id)
                .order_by(PhotoEyeMotifStrength.motif_key)
            )
        )
        .scalars()
        .all()
    )
    return result, [row.strength for row in strengths]


# ---------------------------------------------------------------------------------------------
# Der Schattensatz
# ---------------------------------------------------------------------------------------------


async def test_every_readable_photo_gets_the_full_shadow_set(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    photo = await _add_photo(db_session, project, "a.jpg", tmp_path)
    client = FakeEyeClient({photo.id: _payload()})

    run = await _run(db_session, project, scoring_run, tmp_path, client=client)

    assert run.status is ScanStatus.SUCCESS
    assert run.mode is ClassificationMode.EYE
    assert run.eye_photos_total == 1
    assert run.eye_photos_processed == 1
    assert client.health_calls == 1
    assert client.closed is True

    result, strengths = await _eye_rows(db_session, photo.id)
    assert result.model_revision == "v1.0.0"
    assert result.album_level == 3
    assert result.excluded_document is False
    # Acht Zeilen, immer - was Eye nicht nennt, steht mit 0.0 da.
    assert len(strengths) == len(MOTIF_REGISTRY) == 8

    labels = (
        await db_session.execute(
            select(PhotoEyeFineLabel.label, PhotoEyeFineLabel.confidence)
            .where(PhotoEyeFineLabel.photo_id == photo.id)
            .order_by(PhotoEyeFineLabel.confidence.desc())
        )
    ).all()
    assert [label for label, _ in labels] == ["mountain", "sky", "dog"]


async def test_the_promotion_writes_the_eye_header_when_no_cloud_header_exists(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    photo = await _add_photo(db_session, project, "a.jpg", tmp_path)
    client = FakeEyeClient({photo.id: _payload(confidences={"mountain": 0.9})})

    await _run(db_session, project, scoring_run, tmp_path, client=client)

    header = await db_session.get(PhotoMotifAssessment, photo.id)
    assert header is not None
    assert header.source is MotifAssessmentSource.EYE
    assert header.provider is None
    assert header.computed_at is not None
    strengths = {
        row.motif_key: row.strength
        for row in (
            await db_session.execute(
                select(PhotoMotifStrength).where(PhotoMotifStrength.photo_id == photo.id)
            )
        ).scalars()
    }
    assert strengths["landschaft"] == pytest.approx(0.9)
    assert strengths["menschen"] == pytest.approx(0.0)


async def test_a_cloud_header_stays_and_the_shadow_stands_beside_it(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    photo = await _add_photo(db_session, project, "a.jpg", tmp_path)
    cloud_at = datetime(2024, 5, 1)
    await upsert_assessment(
        db_session,
        photo.id,
        source=MotifAssessmentSource.CLOUD,
        strengths={key: 0.0 for key in MOTIF_REGISTRY} | {"tiere": 0.8},
        excluded_document=False,
        provider="openai",
        computed_at=cloud_at,
    )
    await db_session.commit()

    client = FakeEyeClient({photo.id: _payload(confidences={"dog": 0.95})})
    run = await _run(db_session, project, scoring_run, tmp_path, client=client)

    header = await db_session.get(PhotoMotifAssessment, photo.id)
    assert header is not None
    assert header.source is MotifAssessmentSource.CLOUD
    assert header.provider == "openai"
    assert header.computed_at == cloud_at
    cloud_strengths = {
        row.motif_key: row.strength
        for row in (
            await db_session.execute(
                select(PhotoMotifStrength).where(PhotoMotifStrength.photo_id == photo.id)
            )
        ).scalars()
    }
    assert cloud_strengths["tiere"] == pytest.approx(0.8)

    result, strengths = await _eye_rows(db_session, photo.id)
    assert result.model_revision == "v1.0.0"
    assert any(value == pytest.approx(0.95) for value in strengths)
    assert run.eye_photos_processed == 1


async def test_a_local_header_is_replaced_and_its_vector_survives_as_snapshot(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    photo = await _add_photo(db_session, project, "a.jpg", tmp_path)
    local_vector = {key: 0.0 for key in MOTIF_REGISTRY} | {"landschaft": 0.4}
    await upsert_assessment(
        db_session,
        photo.id,
        source=MotifAssessmentSource.LOCAL,
        strengths=local_vector,
        excluded_document=False,
        provider=None,
        computed_at=datetime(2024, 5, 1),
    )
    await db_session.commit()

    client = FakeEyeClient({photo.id: _payload(confidences={"mountain": 0.9})})
    await _run(db_session, project, scoring_run, tmp_path, client=client)

    header = await db_session.get(PhotoMotifAssessment, photo.id)
    assert header is not None
    assert header.source is MotifAssessmentSource.EYE
    snapshot = (
        await db_session.execute(
            select(PhotoLocalMotifSnapshot).where(PhotoLocalMotifSnapshot.photo_id == photo.id)
        )
    ).scalar_one()
    assert snapshot.excluded_document is False


# ---------------------------------------------------------------------------------------------
# Grenzen: unlesbares Bild, Fehlschlag, Abbruch, Reihenfolge
# ---------------------------------------------------------------------------------------------


async def test_an_unreadable_display_variant_is_skipped_not_fatal(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    readable = await _add_photo(db_session, project, "a.jpg", tmp_path)
    broken = await _add_photo(db_session, project, "b.jpg", tmp_path, readable=False)
    client = FakeEyeClient({readable.id: _payload()})

    run = await _run(db_session, project, scoring_run, tmp_path, client=client)

    assert run.status is ScanStatus.SUCCESS
    assert run.eye_photos_total == 2
    assert run.eye_photos_processed == 1
    assert client.analyze_calls == 1
    assert await db_session.get(PhotoEyeResult, broken.id) is None


async def test_an_image_the_service_cannot_decode_is_skipped_not_fatal(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    first = await _add_photo(db_session, project, "a.jpg", tmp_path)
    broken = await _add_photo(db_session, project, "b.jpg", tmp_path)
    third = await _add_photo(db_session, project, "c.jpg", tmp_path)
    client = FakeEyeClient(
        {first.id: _payload(), broken.id: _payload(), third.id: _payload()},
        fail_at=2,
        fail_with=worker.EyeImageUnreadableError("Das Bild ist nicht lesbar."),
    )

    run = await _run(db_session, project, scoring_run, tmp_path, client=client)

    assert run.status is ScanStatus.SUCCESS
    assert run.eye_photos_total == 3
    assert run.eye_photos_processed == 2
    assert client.analyze_calls == 3
    assert await db_session.get(PhotoEyeResult, broken.id) is None
    broken_header = await db_session.get(PhotoMotifAssessment, broken.id)
    assert broken_header is None or broken_header.source is not MotifAssessmentSource.EYE
    assert (
        await db_session.execute(
            select(func.count())
            .select_from(PhotoEyeMotifStrength)
            .where(PhotoEyeMotifStrength.photo_id == broken.id)
        )
    ).scalar_one() == 0
    for promoted in (first, third):
        header = await db_session.get(PhotoMotifAssessment, promoted.id)
        assert header is not None
        assert header.source is MotifAssessmentSource.EYE
        assert await db_session.get(PhotoEyeResult, promoted.id) is not None


async def test_a_transport_error_fails_the_run_without_writing_anything(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    first = await _add_photo(db_session, project, "a.jpg", tmp_path)
    await _add_photo(db_session, project, "b.jpg", tmp_path)
    client = FakeEyeClient(
        {first.id: _payload()}, fail_at=2, fail_with=worker.EyeServiceUnavailableError("weg")
    )

    run = await _run(db_session, project, scoring_run, tmp_path, client=client)

    assert run.status is ScanStatus.FAILED
    assert run.error_message == "Eye-Auswertung fehlgeschlagen; es wurde nichts uebernommen."
    assert run.phase is None
    # Das ERSTE Foto war schon analysiert - trotzdem steht nichts in der Datenbank: die Phase
    # schreibt ihre Ergebnisse erst am Ende, in einer Transaktion.
    assert (
        await db_session.execute(select(func.count()).select_from(PhotoEyeResult))
    ).scalar_one() == 0
    assert (
        await db_session.execute(select(func.count()).select_from(PhotoMotifAssessment))
    ).scalar_one() == 0


async def test_an_unhealthy_service_fails_before_the_first_photo(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    await _add_photo(db_session, project, "a.jpg", tmp_path)
    client = FakeEyeClient({}, healthy=False)

    run = await _run(db_session, project, scoring_run, tmp_path, client=client)

    assert run.status is ScanStatus.FAILED
    assert client.analyze_calls == 0
    assert (
        await db_session.execute(select(func.count()).select_from(PhotoEyeResult))
    ).scalar_one() == 0


async def test_a_mapping_error_fails_the_run(db_session: AsyncSession, tmp_path: Path) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    photo = await _add_photo(db_session, project, "a.jpg", tmp_path)
    broken = _payload()
    del broken["scores"]
    client = FakeEyeClient({photo.id: broken})

    run = await _run(db_session, project, scoring_run, tmp_path, client=client)

    assert run.status is ScanStatus.FAILED
    assert await db_session.get(PhotoEyeResult, photo.id) is None


async def test_a_cancellation_fails_the_run_and_propagates(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    await _add_photo(db_session, project, "a.jpg", tmp_path)
    client = FakeEyeClient({}, fail_at=1, fail_with=asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await _run(db_session, project, scoring_run, tmp_path, client=client)

    stored = (
        await db_session.execute(
            select(CriterionScoringRun).where(CriterionScoringRun.scoring_run_id == scoring_run.id)
        )
    ).scalar_one()
    assert stored.status is ScanStatus.FAILED
    assert stored.phase is None


async def test_the_photos_are_analyzed_one_at_a_time(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    first = await _add_photo(db_session, project, "a.jpg", tmp_path)
    second = await _add_photo(db_session, project, "b.jpg", tmp_path)
    client = FakeEyeClient({first.id: _payload(), second.id: _payload()})

    await _run(db_session, project, scoring_run, tmp_path, client=client)

    assert client.analyze_calls == 2
    assert client.max_active == 1


async def test_the_eye_phase_leaves_album_suitability_and_cloud_labels_untouched(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    photo = await _add_photo(db_session, project, "a.jpg", tmp_path)
    client = FakeEyeClient({photo.id: _payload()})

    await _run(db_session, project, scoring_run, tmp_path, client=client)

    assert (
        await db_session.execute(select(func.count()).select_from(PhotoAlbumSuitability))
    ).scalar_one() == 0
    assert (
        await db_session.execute(select(func.count()).select_from(PhotoFineLabel))
    ).scalar_one() == 0


async def test_the_eye_phase_runs_before_the_criteria_phase(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    photo = await _add_photo(db_session, project, "a.jpg", tmp_path)
    seen: list[ClassificationPhase | None] = []
    original = worker._set_phase

    def recording(run: CriterionScoringRun, phase: ClassificationPhase | None) -> None:
        seen.append(phase)
        original(run, phase)

    monkeypatch.setattr(worker, "_set_phase", recording)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        client=FakeEyeClient({photo.id: _payload()}),
    )

    assert run.status is ScanStatus.SUCCESS
    assert seen[0] is ClassificationPhase.EYE
    assert ClassificationPhase.CRITERIA in seen
    assert seen[-1] is None


# ---------------------------------------------------------------------------------------------
# Der Weg: mode, Signatur, Ableitung
# ---------------------------------------------------------------------------------------------


async def test_eye_without_consent_requests_no_cloud(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    photo = await _add_photo(db_session, project, "a.jpg", tmp_path)

    run = await _run(
        db_session, project, scoring_run, tmp_path, client=FakeEyeClient({photo.id: _payload()})
    )

    assert run.cloud_requested is False
    assert run.mode is ClassificationMode.EYE


async def test_eye_with_consent_requests_the_landmark_phase(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session, consent=True)
    scoring_run = await _add_run(db_session, project)
    photo = await _add_photo(db_session, project, "a.jpg", tmp_path)

    run = await _run(
        db_session, project, scoring_run, tmp_path, client=FakeEyeClient({photo.id: _payload()})
    )

    assert run.cloud_requested is True
    assert run.mode is ClassificationMode.EYE


@pytest.mark.parametrize("mode", [ClassificationMode.LOCAL, ClassificationMode.CLOUD])
async def test_the_eye_phase_is_not_built_for_other_ways(
    db_session: AsyncSession, tmp_path: Path, mode: ClassificationMode
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    await _add_photo(db_session, project, "a.jpg", tmp_path)

    # Der Builder wirft - ein Aufruf beweise damit, dass Eye in diesem Modus nie gebaut wird.
    run = await _run(db_session, project, scoring_run, tmp_path, mode=mode)

    assert run.status is ScanStatus.SUCCESS
    assert run.mode is mode
    # NULL heisst "kein Eye-Lauf" - 0 hiesse "Eye lief ueber null Fotos".
    assert run.eye_photos_total is None
    assert run.eye_photos_processed is None


async def test_the_old_use_cloud_flag_still_derives_the_mode(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)
    await _add_photo(db_session, project, "a.jpg", tmp_path)

    run = await _run(db_session, project, scoring_run, tmp_path, mode=None, use_cloud=True)

    assert run.mode is ClassificationMode.CLOUD


async def test_mode_and_use_cloud_must_not_contradict(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_run(db_session, project)

    with pytest.raises(ValueError):
        await _run(
            db_session,
            project,
            scoring_run,
            tmp_path,
            mode=ClassificationMode.CLOUD,
            use_cloud=False,
        )


def test_the_job_keeps_use_cloud_as_fourth_positional_and_mode_as_keyword() -> None:
    parameters = list(worker.classify.__code__.co_varnames[: worker.classify.__code__.co_argcount])
    assert parameters[:4] == ["ctx", "project_id", "scoring_run_id", "use_cloud"]
    assert worker.classify.__kwdefaults__ is not None
    assert "mode" in worker.classify.__kwdefaults__
    assert worker.classify.__kwdefaults__["mode"] is None
