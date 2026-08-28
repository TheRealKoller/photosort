from __future__ import annotations

import asyncio
import logging
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
    CloudVisionPhase,
    Photo,
    PhotoCategoryDetection,
    PhotoCloudVisionError,
    PhotoScore,
    Project,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanStatus,
)
from photosort.remote_classification import CategoryLabelDetection
from photosort.thumbnails import display_path
from photosort.worker import run_remote_category_classification, select_remote_category_candidates

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
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
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

    # Spec 0056/ADR 0034: genau ein WARNING-Record fuer das fehlgeschlagene Foto, keiner fuer das
    # erfolgreiche (AK4: keine Erfolgsprotokollierung).
    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
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

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.name == "photosort.worker"
    assert record.levelno == logging.WARNING
    assert record.exc_info is None  # ADR 0034 Punkt 5: kein exc_info=True/Traceback.
    assert "RuntimeError" in record.message
    assert str(failing_photo.id) in record.message
    assert failing_photo.relative_path in record.message
    assert str(succeeding_photo.id) not in record.message


# specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
# fehler-persistierung.md Punkt 2/3 ab hier: worker.py::_record_cloud_vision_error/
# _clear_cloud_vision_error - eigene DB-Zustands-Tests, unabhaengig von der API-Sichtbarkeit
# (Teststrategie-Abschnitt der Spec), analog test_worker_criterion_scoring.py.


async def test_failed_remote_category_call_persists_a_cloud_vision_error_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    client = RecordingCategoryClient(raise_error=True)

    await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: client,
        build_embedder=_fake_embedder,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    stored = result.scalar_one()
    assert stored.phase == CloudVisionPhase.REMOTE_CATEGORY
    assert stored.error_type == "RuntimeError"
    assert "simulierter Cloud-Fehler" in stored.error_message
    assert stored.attempted_at is not None


async def test_successful_remote_category_call_after_a_previous_failure_clears_the_error_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: RecordingCategoryClient(raise_error=True),
        build_embedder=_fake_embedder,
    )
    assert (
        await db_session.execute(
            select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
        )
    ).scalar_one_or_none() is not None

    await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: RecordingCategoryClient(),
        build_embedder=_fake_embedder,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    assert result.scalar_one_or_none() is None


async def test_repeated_remote_category_failures_upsert_the_same_error_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    class _RaisingClient:
        def __init__(self, message: str) -> None:
            self._message = message

        async def classify(
            self, image_bytes: bytes, mime_type: str
        ) -> list[CategoryLabelDetection]:
            raise RuntimeError(self._message)

    await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: _RaisingClient("erster Fehlschlag"),
        build_embedder=_fake_embedder,
    )
    await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: _RaisingClient("zweiter Fehlschlag"),
        build_embedder=_fake_embedder,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1  # Upsert, kein Verlauf (composite PK photo_id+phase).
    assert "zweiter Fehlschlag" in rows[0].error_message
    assert "erster Fehlschlag" not in rows[0].error_message


async def test_remote_category_error_message_is_capped_at_500_characters(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    overlong_message = "x" * 600

    class _RaisingClient:
        async def classify(
            self, image_bytes: bytes, mime_type: str
        ) -> list[CategoryLabelDetection]:
            raise RuntimeError(overlong_message)

    await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda: _RaisingClient(),
        build_embedder=_fake_embedder,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    stored = result.scalar_one()
    assert len(stored.error_message) == 500
    assert stored.error_message == overlong_message[:500]


async def test_empty_candidate_pool_succeeds_trivially(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()

    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        run = await run_remote_category_classification(
            db_session,
            project,
            cache_dir=tmp_path,
            build_client=_failing_client_builder,
            build_embedder=_fake_embedder,
        )

    assert run.status == ScanStatus.SUCCESS
    assert run.photos_total == 0
    # Spec 0056/ADR 0034: nur Fehler werden geloggt, ein erfolgreich durchgelaufener Gesamtlauf
    # erzeugt keinen Log-Eintrag.
    assert len(caplog.records) == 0


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
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    # Spec 0056/ADR 0034: ein CancelledError durchlaeuft die separate, dem continue-Loop
    # vorgelagerte Propagations-Schleife und erreicht die neuen logger.warning(...)-Aufrufe
    # strukturell nie - ein Lauf-Abbruch ist keine best-effort-Situation.
    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        with pytest.raises(asyncio.CancelledError):
            await run_remote_category_classification(
                db_session,
                project,
                cache_dir=tmp_path,
                build_client=lambda: CancellingCategoryClient(),
                build_embedder=_fake_embedder,
            )

    assert len(caplog.records) == 0

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


async def test_select_remote_category_candidates_excludes_rejected_and_already_classified(
    db_session: AsyncSession,
) -> None:
    """Dediziert getestete, wiederverwendbare Kandidaten-Selektion (auch von GET .../estimate
    genutzt, api/projects.py) - identisch zu der bereits ueber run_remote_category_classification
    indirekt getesteten Logik, hier isoliert."""
    project = await _make_project(db_session)
    survivor = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, survivor)
    rejected = await _add_photo(db_session, project, "b.jpg", "etag-2")
    await _add_score(db_session, rejected, suggested_status=RatingStatus.REJECTED)
    already_classified = await _add_photo(db_session, project, "c.jpg", "etag-3")
    await _add_score(db_session, already_classified)
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
    await db_session.commit()

    candidates = await select_remote_category_candidates(db_session, project.id)

    assert [photo.id for photo in candidates] == [survivor.id]


async def test_select_remote_category_candidates_returns_empty_list_for_no_photos(
    db_session: AsyncSession,
) -> None:
    project = await _make_project(db_session)
    assert await select_remote_category_candidates(db_session, project.id) == []
