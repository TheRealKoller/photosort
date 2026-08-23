from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import worker
from photosort.label_embedding import LabelEmbedderLike
from photosort.models import (
    CategoryLabel,
    Photo,
    PhotoCategoryDetection,
    PhotoScore,
    Project,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanStatus,
)
from photosort.remote_classification import CategoryLabelDetection
from photosort.thumbnails import display_path
from photosort.worker import run_remote_category_classification

# specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
# decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md Punkt 5: eigenstaendiger
# Job, strukturell analog run_criterion_scoring's landmark-Phase, aber ohne Kandidatenpool-
# Vorfilter (kompletter Ausschuss-Ueberlebender-Bestand statt eines Vorfilter-Ergebnisses).


async def _make_project(session: AsyncSession, *, name: str = "Costa Rica") -> Project:
    project = Project(name=name, opencloud_drive_id=f"drive-{name}", opencloud_path=name)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_photo(
    session: AsyncSession, project: Project, path: str, etag: str
) -> Photo:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=etag,
        content_length=100,
        taken_at=now,
        last_modified=now,
    )
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return photo


async def _add_score(
    session: AsyncSession,
    photo: Photo,
    *,
    suggested_status: RatingStatus | None = None,
) -> PhotoScore:
    score = PhotoScore(
        photo_id=photo.id,
        sharpness=100.0,
        exposure=0.0,
        cluster_key="cluster-0",
        suggested_status=suggested_status,
        computed_at=datetime.now(UTC),
    )
    session.add(score)
    await session.commit()
    return score


def _write_display_variant(cache_dir: Path, photo: Photo) -> None:
    path = display_path(cache_dir, photo.id, photo.etag)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (160, 160), color=(100, 100, 100)).save(path, format="JPEG")


class FakeLabelEmbedder:
    """Deterministisches, aber NICHT konstantes Test-Double: bildet jeden (bereits normalisierten)
    Text ueber einen Hash auf einen Punkt am Einheitskreis ab - unterschiedliche Texte erhalten
    dadurch mit hoher Wahrscheinlichkeit deutlich unterschiedliche Vektoren (Kosinus-Aehnlichkeit
    weit unter CATEGORY_LABEL_SIMILARITY_THRESHOLD), waehrend ein konstanter Fake alle Labels
    faelschlich auf denselben kanonischen Eintrag zusammenfallen liesse."""

    def embed(self, text: str) -> list[float]:
        import hashlib
        import math

        digest = hashlib.sha256(text.encode()).digest()
        angle = (int.from_bytes(digest[:4], "big") / 2**32) * 2 * math.pi
        return [math.cos(angle), math.sin(angle)]


def _fake_embedder() -> LabelEmbedderLike:
    return FakeLabelEmbedder()


def _failing_embedder_builder() -> NoReturn:
    raise RuntimeError("simulierter Modell-Ladefehler")


class RecordingCategoryClient:
    def __init__(
        self,
        detections: list[CategoryLabelDetection] | None = None,
        raise_error: bool = False,
    ) -> None:
        self._detections = (
            detections
            if detections is not None
            else [CategoryLabelDetection(label="Hund", confidence=0.9)]
        )
        self._raise_error = raise_error
        self.calls: list[tuple[bytes, str]] = []
        self.aclose_calls = 0

    async def classify(self, image_bytes: bytes, mime_type: str) -> list[CategoryLabelDetection]:
        self.calls.append((image_bytes, mime_type))
        if self._raise_error:
            raise RuntimeError("simulierter Cloud-Fehler")
        return self._detections

    async def aclose(self) -> None:
        self.aclose_calls += 1


class PerPhotoCategoryClient:
    """Liefert unterschiedliche Detections/Fehler je Aufrufindex - fuer Best-effort-
    Isolationstests."""

    def __init__(self, results: list[list[CategoryLabelDetection] | Exception]) -> None:
        self._results = results
        self.calls = 0

    async def classify(self, image_bytes: bytes, mime_type: str) -> list[CategoryLabelDetection]:
        result = self._results[self.calls]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return result


class ConcurrencyTrackingCategoryClient:
    def __init__(self) -> None:
        self._active = 0
        self.max_concurrent = 0
        self.call_count = 0

    async def classify(self, image_bytes: bytes, mime_type: str) -> list[CategoryLabelDetection]:
        self.call_count += 1
        self._active += 1
        self.max_concurrent = max(self.max_concurrent, self._active)
        try:
            await asyncio.sleep(0.01)
            return [CategoryLabelDetection(label="Hund", confidence=0.9)]
        finally:
            self._active -= 1


class CancellingCategoryClient:
    async def classify(self, image_bytes: bytes, mime_type: str) -> list[CategoryLabelDetection]:
        raise asyncio.CancelledError("simulierter Abbruch")


def _failing_client_builder() -> NoReturn:
    pytest.fail("build_category_classification_client darf ohne Consent nie aufgerufen werden")


async def test_consent_disabled_by_default_never_calls_the_client_builder(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=_failing_client_builder,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    detections = (await db_session.execute(select(PhotoCategoryDetection))).scalars().all()
    assert detections == []


async def test_enabling_consent_unlocks_the_remote_category_client(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    client = RecordingCategoryClient()

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert len(client.calls) == 1
    assert client.aclose_calls == 1


async def test_full_candidate_pool_has_no_pre_filter_unlike_landmark(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    for index in range(3):
        photo = await _add_photo(db_session, project, f"p{index}.jpg", f"etag-{index}")
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo)

    client = RecordingCategoryClient()

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.photos_total == 3
    assert len(client.calls) == 3


async def test_rejected_photos_are_not_candidates(db_session: AsyncSession, tmp_path: Path) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    survivor = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, survivor)
    _write_display_variant(tmp_path, survivor)
    rejected = await _add_photo(db_session, project, "b.jpg", "etag-2")
    await _add_score(db_session, rejected, suggested_status=RatingStatus.REJECTED)
    _write_display_variant(tmp_path, rejected)

    client = RecordingCategoryClient()

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.photos_total == 1
    assert len(client.calls) == 1


async def test_already_classified_photos_are_skipped_on_a_repeat_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    already_classified = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, already_classified)
    _write_display_variant(tmp_path, already_classified)
    label = CategoryLabel(canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0])
    db_session.add(label)
    await db_session.flush()
    db_session.add(
        PhotoCategoryDetection(
            photo_id=already_classified.id,
            category_label_id=label.id,
            raw_label="Hund",
            confidence=0.9,
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    new_candidate = await _add_photo(db_session, project, "b.jpg", "etag-2")
    await _add_score(db_session, new_candidate)
    _write_display_variant(tmp_path, new_candidate)
    await db_session.commit()

    client = RecordingCategoryClient()

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.photos_total == 1
    assert len(client.calls) == 1


async def test_a_successful_call_writes_one_to_three_detection_rows_unconditionally(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    client = RecordingCategoryClient(
        detections=[
            CategoryLabelDetection(label="Hund", confidence=0.9),
            CategoryLabelDetection(label="Strand", confidence=0.5),
        ]
    )

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    detections = (
        await db_session.execute(
            select(PhotoCategoryDetection).where(PhotoCategoryDetection.photo_id == photo.id)
        )
    ).scalars().all()
    assert len(detections) == 2
    assert run.photos_processed == 1


async def test_two_raw_labels_with_the_same_canonical_key_keep_the_higher_confidence(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    # FakeLabelEmbedder liefert fuer JEDEN Text denselben Vektor -> "Hund" und "hund" (exakter
    # Fast-Path) UND ein drittes, andersartiges Label wuerden alle auf denselben kanonischen
    # Eintrag aufloesen, wenn sie normalisiert identisch sind. Hier bewusst zwei Roh-Label, die
    # bereits ueber den exakten NFKC+casefold-Fast-Path zusammenfallen ("Hund"/"hund").
    client = RecordingCategoryClient(
        detections=[
            CategoryLabelDetection(label="Hund", confidence=0.4),
            CategoryLabelDetection(label="hund", confidence=0.9),
        ]
    )

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    detections = (
        await db_session.execute(
            select(PhotoCategoryDetection).where(PhotoCategoryDetection.photo_id == photo.id)
        )
    ).scalars().all()
    assert len(detections) == 1
    assert detections[0].confidence == 0.9


async def test_best_effort_error_isolation_does_not_abort_the_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    failing_photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, failing_photo)
    _write_display_variant(tmp_path, failing_photo)
    succeeding_photo = await _add_photo(db_session, project, "b.jpg", "etag-2")
    await _add_score(db_session, succeeding_photo)
    _write_display_variant(tmp_path, succeeding_photo)

    client = PerPhotoCategoryClient(
        [RuntimeError("boom"), [CategoryLabelDetection(label="Hund", confidence=0.9)]]
    )

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    detections = (await db_session.execute(select(PhotoCategoryDetection))).scalars().all()
    assert len(detections) == 1


async def test_empty_candidate_pool_succeeds_trivially(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=_failing_client_builder,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.photos_total == 0


async def test_calls_are_limited_by_the_concurrency_setting(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "remote_category_classification_concurrency", 2)
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    for index in range(5):
        photo = await _add_photo(db_session, project, f"p{index}.jpg", f"etag-{index}")
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo)

    client = ConcurrencyTrackingCategoryClient()

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.call_count == 5
    assert client.max_concurrent > 1
    assert client.max_concurrent <= 2


async def test_cancelled_error_propagates_and_fails_the_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    with pytest.raises(asyncio.CancelledError):
        await run_remote_category_classification(
            db_session,
            project,
            cache_dir=tmp_path,
            build_client=lambda: CancellingCategoryClient(),
            build_embedder=_fake_embedder,
        )

    # Kein Filter auf project.id (nur ein Projekt in diesem Test) - project ist nach der oben von
    # _fail_run ausgeloesten session.rollback() best-effort abgelaufen; ein direkter Attributzugriff
    # ausserhalb eines aktiven Session-await-Kontexts wuerde sonst denselben MissingGreenlet-
    # Fallstrick ausloesen, den _fail_run fuer `run` bereits per session.refresh(run) vermeidet
    # (siehe worker.py::_fail_run-Kommentar) - hier reicht die ungefilterte Abfrage aus.
    run_row = (
        await db_session.execute(select(RemoteCategoryClassificationRun))
    ).scalars().first()
    assert run_row is not None
    assert run_row.status == ScanStatus.FAILED


async def test_embedder_build_failure_leaves_the_run_successful_with_nothing_processed(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    client = RecordingCategoryClient()

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: client,
        build_embedder=_failing_embedder_builder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == []
    detections = (await db_session.execute(select(PhotoCategoryDetection))).scalars().all()
    assert detections == []


async def test_a_new_canonical_label_is_reused_across_two_projects(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project_a = await _make_project(db_session, name="Projekt A")
    project_a.cloud_vision_detection_enabled = True
    project_b = await _make_project(db_session, name="Projekt B")
    project_b.cloud_vision_detection_enabled = True
    await db_session.commit()

    photo_a = await _add_photo(db_session, project_a, "a.jpg", "etag-1")
    await _add_score(db_session, photo_a)
    _write_display_variant(tmp_path, photo_a)
    photo_b = await _add_photo(db_session, project_b, "b.jpg", "etag-2")
    await _add_score(db_session, photo_b)
    _write_display_variant(tmp_path, photo_b)

    await run_remote_category_classification(
        db_session,
        project_a,
        cache_dir=tmp_path,
        build_client=lambda: RecordingCategoryClient(),
        build_embedder=_fake_embedder,
    )
    await run_remote_category_classification(
        db_session,
        project_b,
        cache_dir=tmp_path,
        # Gleicher normalisierter Text ("Hund") -> exakter Fast-Path, dieselbe category_labels-
        # Zeile wird wiederverwendet statt einer zweiten Registry-Zeile (ADR 0032 Punkt 2).
        build_client=lambda: RecordingCategoryClient(),
        build_embedder=_fake_embedder,
    )

    labels = (await db_session.execute(select(CategoryLabel))).scalars().all()
    assert len(labels) == 1

    detections = (await db_session.execute(select(PhotoCategoryDetection))).scalars().all()
    assert {d.photo_id for d in detections} == {photo_a.id, photo_b.id}
