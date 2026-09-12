from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

import httpx
import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import pricing, worker
from photosort.categories import CATEGORY_NOT_RECOGNIZED
from photosort.cloud_vision import (
    VISION_MODELS_BY_PROVIDER,
    CloudRequestThrottle,
    TokenUsage,
    default_vision_model_for_provider,
)
from photosort.label_embedding import LabelEmbedderLike
from photosort.models import (
    CloudVisionPhase,
    FineLabel,
    Photo,
    PhotoCategoryClassification,
    PhotoCloudVisionError,
    PhotoFineLabel,
    PhotoScore,
    Project,
    RatingStatus,
    RemoteCategoryClassificationRun,
    ScanStatus,
)
from photosort.pricing import compute_cost_usd
from photosort.remote_classification import (
    AnthropicCategoryClient,
    RemoteCategoryClassificationApiError,
    RemoteClassification,
)
from photosort.thumbnails import display_path
from photosort.worker import run_remote_category_classification, select_remote_category_candidates
from tests.run_bookkeeping import assert_call_bookkeeping_invariant

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


async def _add_photo(session: AsyncSession, project: Project, path: str, etag: str) -> Photo:
    now = datetime(2023, 1, 1, tzinfo=UTC)
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=etag,
        content_length=100,
        taken_at=now,
        taken_at_original=now,
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


_DEFAULT_CLASSIFICATION = RemoteClassification(categories=("tier",), fine_labels=("Hund",))


class RecordingCategoryClient:
    def __init__(
        self,
        classification: RemoteClassification | None = None,
        raise_error: bool = False,
    ) -> None:
        self._classification = (
            classification if classification is not None else _DEFAULT_CLASSIFICATION
        )
        self._raise_error = raise_error
        self.calls: list[tuple[bytes, str, int]] = []
        self.aclose_calls = 0

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
        self.calls.append((image_bytes, mime_type, photo_id))
        if self._raise_error:
            raise RuntimeError("simulierter Cloud-Fehler")
        return self._classification

    async def aclose(self) -> None:
        self.aclose_calls += 1


class PerPhotoCategoryClient:
    """Liefert unterschiedliche Ergebnisse/Fehler je Aufrufindex - fuer Best-effort-
    Isolationstests."""

    def __init__(self, results: list[RemoteClassification | Exception]) -> None:
        self._results = results
        self.calls = 0

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
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

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
        self.call_count += 1
        self._active += 1
        self.max_concurrent = max(self.max_concurrent, self._active)
        try:
            await asyncio.sleep(0.01)
            return _DEFAULT_CLASSIFICATION
        finally:
            self._active -= 1


class CancellingCategoryClient:
    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
        raise asyncio.CancelledError("simulierter Abbruch")


def _failing_client_builder(model: str) -> NoReturn:
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
    detections = (await db_session.execute(select(PhotoFineLabel))).scalars().all()
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
        build_client=lambda _model: client,
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
        build_client=lambda _model: client,
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
        build_client=lambda _model: client,
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
    # specs/features/0289-feste-kategorien.md: das Skip-Kriterium ist seit dieser Spec die
    # 1:1-Klassifikations-Zeile, nicht mehr eine Feinlabel-Zeile - ein Foto mit Kategorie, aber
    # ohne Feinlabel, gilt als erledigt.
    db_session.add(
        PhotoCategoryClassification(
            photo_id=already_classified.id,
            category_key="tier",
            detected_categories=["tier"],
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
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.photos_total == 1
    assert len(client.calls) == 1


async def _run_for_one_photo(
    db_session: AsyncSession,
    tmp_path: Path,
    classification: RemoteClassification,
) -> tuple[Photo, RemoteCategoryClassificationRun]:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda _model: RecordingCategoryClient(classification),
        build_embedder=_fake_embedder,
    )
    return photo, run


async def test_a_successful_call_writes_exactly_one_classification_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    photo, run = await _run_for_one_photo(
        db_session,
        tmp_path,
        RemoteClassification(categories=("landschaft", "menschen"), fine_labels=("Hund",)),
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.photos_processed == 1
    rows = (
        (
            await db_session.execute(
                select(PhotoCategoryClassification).where(
                    PhotoCategoryClassification.photo_id == photo.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    # `menschen` gewinnt gegen `landschaft` (kleinere precedence) - die Zeile haelt das bereits
    # AUFGELOESTE Ergebnis, nicht die Rohantwort.
    assert rows[0].category_key == "menschen"
    # `detected_categories` haelt die VALIDIERTE Kandidatenliste (Security-Muss-Kriterium: nie die
    # Rohliste des Modells).
    assert rows[0].detected_categories == ["landschaft", "menschen"]


async def test_a_successful_call_writes_up_to_two_fine_label_rows(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    photo, run = await _run_for_one_photo(
        db_session,
        tmp_path,
        RemoteClassification(categories=("tier",), fine_labels=("Hund", "Strand")),
    )

    assert run.status == ScanStatus.SUCCESS
    rows = (
        (
            await db_session.execute(
                select(PhotoFineLabel).where(PhotoFineLabel.photo_id == photo.id)
            )
        )
        .scalars()
        .all()
    )
    assert {row.raw_label for row in rows} == {"Hund", "Strand"}


async def test_fine_labels_are_written_even_when_the_category_is_not_recognized(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Direktes Akzeptanzkriterium der Spec 0289: Feinlabels werden AUCH DANN festgehalten, wenn
    die Kategorie "Nicht erkannt" lautet - sie sind eigenstaendige Zusatzinformation, keine
    Beigabe zu einer erfolgreichen Kategorisierung."""
    photo, run = await _run_for_one_photo(
        db_session,
        tmp_path,
        RemoteClassification(categories=(), fine_labels=("Fabelwesen",)),
    )

    assert run.status == ScanStatus.SUCCESS
    classification = (
        (
            await db_session.execute(
                select(PhotoCategoryClassification).where(
                    PhotoCategoryClassification.photo_id == photo.id
                )
            )
        )
        .scalars()
        .one()
    )
    assert classification.category_key == "nicht_erkannt"
    assert classification.detected_categories == []

    fine_labels = (
        (
            await db_session.execute(
                select(PhotoFineLabel).where(PhotoFineLabel.photo_id == photo.id)
            )
        )
        .scalars()
        .all()
    )
    assert [row.raw_label for row in fine_labels] == ["Fabelwesen"]


async def test_a_photo_without_fine_labels_gets_a_classification_row_anyway(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    photo, _ = await _run_for_one_photo(
        db_session, tmp_path, RemoteClassification(categories=("tier",), fine_labels=())
    )

    assert (
        await db_session.execute(select(PhotoFineLabel).where(PhotoFineLabel.photo_id == photo.id))
    ).scalars().all() == []
    assert (
        await db_session.execute(
            select(PhotoCategoryClassification).where(
                PhotoCategoryClassification.photo_id == photo.id
            )
        )
    ).scalars().one().category_key == "tier"


async def test_two_fine_labels_with_the_same_canonical_key_write_only_one_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Zwei Roh-Label, die bereits ueber den exakten NFKC+casefold-Fast-Path zusammenfallen
    # ("Hund"/"hund") - der UniqueConstraint(photo_id, fine_label_id) darf dabei nicht brechen.
    photo, run = await _run_for_one_photo(
        db_session,
        tmp_path,
        RemoteClassification(categories=("tier",), fine_labels=("Hund", "hund")),
    )

    assert run.status == ScanStatus.SUCCESS
    rows = (
        (
            await db_session.execute(
                select(PhotoFineLabel).where(PhotoFineLabel.photo_id == photo.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    # Erstnennung gewinnt (ein Konfidenz-Vergleich ist mit dem Wegfall der Konfidenzen
    # gegenstandslos geworden).
    assert rows[0].raw_label == "Hund"


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
        [RuntimeError("boom"), RemoteClassification(categories=("tier",), fine_labels=("Hund",))]
    )

    # Spec 0056/ADR 0034: genau ein WARNING-Record fuer das fehlgeschlagene Foto, keiner fuer das
    # erfolgreiche (AK4: keine Erfolgsprotokollierung).
    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        run = await run_remote_category_classification(
            db_session,
            project,
            cache_dir=tmp_path,
            build_client=lambda _model: client,
            build_embedder=_fake_embedder,
        )

    assert run.status == ScanStatus.SUCCESS
    detections = (await db_session.execute(select(PhotoFineLabel))).scalars().all()
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
        build_client=lambda _model: client,
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
        build_client=lambda _model: RecordingCategoryClient(raise_error=True),
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
        build_client=lambda _model: RecordingCategoryClient(),
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
            self, image_bytes: bytes, mime_type: str, photo_id: int
        ) -> RemoteClassification:
            raise RuntimeError(self._message)

    await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda _model: _RaisingClient("erster Fehlschlag"),
        build_embedder=_fake_embedder,
    )
    await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda _model: _RaisingClient("zweiter Fehlschlag"),
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
            self, image_bytes: bytes, mime_type: str, photo_id: int
        ) -> RemoteClassification:
            raise RuntimeError(overlong_message)

    await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda _model: _RaisingClient(),
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
        build_client=lambda _model: client,
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
                build_client=lambda _model: CancellingCategoryClient(),
                build_embedder=_fake_embedder,
            )

    assert len(caplog.records) == 0

    # Kein Filter auf project.id (nur ein Projekt in diesem Test) - project ist nach der oben von
    # _fail_run ausgeloesten session.rollback() best-effort abgelaufen; ein direkter Attributzugriff
    # ausserhalb eines aktiven Session-await-Kontexts wuerde sonst denselben MissingGreenlet-
    # Fallstrick ausloesen, den _fail_run fuer `run` bereits per session.refresh(run) vermeidet
    # (siehe worker.py::_fail_run-Kommentar) - hier reicht die ungefilterte Abfrage aus.
    run_row = (await db_session.execute(select(RemoteCategoryClassificationRun))).scalars().first()
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
        build_client=lambda _model: client,
        build_embedder=_failing_embedder_builder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == []
    detections = (await db_session.execute(select(PhotoFineLabel))).scalars().all()
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
        build_client=lambda _model: RecordingCategoryClient(),
        build_embedder=_fake_embedder,
    )
    await run_remote_category_classification(
        db_session,
        project_b,
        cache_dir=tmp_path,
        # Gleicher normalisierter Text ("Hund") -> exakter Fast-Path, dieselbe fine_labels-
        # Zeile wird wiederverwendet statt einer zweiten Registry-Zeile (ADR 0032 Punkt 2).
        build_client=lambda _model: RecordingCategoryClient(),
        build_embedder=_fake_embedder,
    )

    labels = (await db_session.execute(select(FineLabel))).scalars().all()
    assert len(labels) == 1

    rows = (await db_session.execute(select(PhotoFineLabel))).scalars().all()
    assert {row.photo_id for row in rows} == {photo_a.id, photo_b.id}


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
    db_session.add(
        PhotoCategoryClassification(
            photo_id=already_classified.id,
            category_key="tier",
            detected_categories=["tier"],
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


async def test_a_structurally_invalid_response_skips_only_that_photo(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """specs/features/0289-feste-kategorien.md, Teststrategie 7: eine strukturell ungueltige
    Antwort (fehlendes/nicht-listenfoermiges `categories`, kein JSON-Objekt, abgeschnittene
    Antwort) laeuft ueber den bestehenden RemoteCategoryClassificationApiError-Pfad - das Foto
    wird best-effort uebersprungen, die uebrigen Fotos werden weiterverarbeitet, der Lauf endet
    regulaer."""
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    broken = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, broken)
    _write_display_variant(tmp_path, broken)
    intact = await _add_photo(db_session, project, "b.jpg", "etag-2")
    await _add_score(db_session, intact)
    _write_display_variant(tmp_path, intact)

    client = PerPhotoCategoryClient(
        [
            RemoteCategoryClassificationApiError("fehlendes 'categories'-Feld"),
            RemoteClassification(categories=("tier",), fine_labels=()),
        ]
    )

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    rows = (await db_session.execute(select(PhotoCategoryClassification))).scalars().all()
    assert [row.photo_id for row in rows] == [intact.id]


async def test_a_second_run_does_not_create_a_second_classification_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    for _ in range(2):
        run = await run_remote_category_classification(
            db_session,
            project,
            cache_dir=tmp_path,
            build_client=lambda _model: RecordingCategoryClient(),
            build_embedder=_fake_embedder,
        )
        assert run.status == ScanStatus.SUCCESS

    rows = (await db_session.execute(select(PhotoCategoryClassification))).scalars().all()
    assert len(rows) == 1


# specs/features/0207-projekt-statistikseite.md, decisions/0051-ist-kostenerfassung-remote-
# laeufe.md ab hier: dieselbe Ist-Kostenerfassung wie in der Landmark-Phase, hier ohne Praefix -
# dieser Lauf hat genau einen Zweck.


def _classification_with_usage(input_tokens: int, output_tokens: int) -> RemoteClassification:
    return RemoteClassification(
        categories=("tier",),
        fine_labels=("Hund",),
        usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def _expected_cost(input_tokens: int, output_tokens: int, provider: str = "anthropic") -> float:
    cost = compute_cost_usd(
        default_vision_model_for_provider(provider),
        TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )
    assert cost is not None
    return cost


async def _cost_setup(db_session: AsyncSession, tmp_path: Path, *, photo_count: int) -> Project:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    for index in range(photo_count):
        photo = await _add_photo(db_session, project, f"{index}.jpg", f"etag-{index}")
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo)
    return project


async def test_costs_are_summed_over_all_successful_classifications(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _cost_setup(db_session, tmp_path, photo_count=3)
    client = PerPhotoCategoryClient(
        [
            _classification_with_usage(1_000, 10),
            _classification_with_usage(2_000, 20),
            _classification_with_usage(3_000, 30),
        ]
    )

    run = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.api_calls == 3
    assert run.input_tokens == 6_000
    assert run.output_tokens == 60
    assert run.cost_usd == pytest.approx(_expected_cost(6_000, 60))


async def test_a_partially_failing_run_only_counts_the_successful_calls(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _cost_setup(db_session, tmp_path, photo_count=3)
    client = PerPhotoCategoryClient(
        [
            RemoteCategoryClassificationApiError("Fehler 1"),
            _classification_with_usage(2_000, 20),
            RemoteCategoryClassificationApiError("Fehler 2"),
        ]
    )

    run = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.api_calls == 1
    assert run.input_tokens == 2_000
    assert run.output_tokens == 20
    assert run.cost_usd == pytest.approx(_expected_cost(2_000, 20))


async def test_a_classification_without_usage_still_counts_as_an_api_call(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _cost_setup(db_session, tmp_path, photo_count=2)
    client = PerPhotoCategoryClient(
        [
            RemoteClassification(categories=("tier",), fine_labels=()),  # ohne usage
            _classification_with_usage(1_000, 10),
        ]
    )

    run = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )

    assert run.api_calls == 2
    assert run.input_tokens == 1_000
    assert run.output_tokens == 10


async def test_an_unpriced_model_records_tokens_but_no_amount(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pricing, "MODEL_PRICING", {})
    project = await _cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoCategoryClient([_classification_with_usage(1_000, 10)])

    run = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )

    assert run.api_calls == 1
    assert run.input_tokens == 1_000
    assert run.cost_usd is None


async def test_an_early_return_without_cloud_consent_records_zero_not_null(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Frueher Erfolgs-Rueckweg (Cloud aus): "erfasst, keine Kosten angefallen", nicht "nicht
    erfasst"."""
    project = await _make_project(db_session)
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    run = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=_failing_client_builder,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.api_calls == 0
    assert run.input_tokens == 0
    assert run.output_tokens == 0
    assert run.cost_usd == 0


async def test_an_early_return_without_candidates_records_zero_not_null(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()

    run = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=_failing_client_builder,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.api_calls == 0
    assert run.cost_usd == 0


async def test_a_second_run_without_new_candidates_carries_no_costs(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Prueft zugleich, dass die Projektsumme spaeter ueber die Laeufe SUMMIERT werden muss und
    nicht der letzte Lauf gelesen werden darf - der zweite Lauf hier kostet nichts."""
    project = await _cost_setup(db_session, tmp_path, photo_count=1)
    first = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: PerPhotoCategoryClient([_classification_with_usage(1_000, 10)]),
        build_embedder=_fake_embedder,
    )
    assert first.api_calls == 1

    second = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: PerPhotoCategoryClient([]),
        build_embedder=_fake_embedder,
    )

    assert second.id != first.id
    assert second.api_calls == 0
    assert second.cost_usd == 0
    assert first.api_calls == 1
    assert first.cost_usd == pytest.approx(_expected_cost(1_000, 10))


async def test_the_category_client_is_still_closed_exactly_once_when_costs_are_written(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _cost_setup(db_session, tmp_path, photo_count=1)
    client = RecordingCategoryClient(classification=_classification_with_usage(1_000, 10))

    run = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )

    assert run.api_calls == 1
    assert client.aclose_calls == 1


async def test_costs_use_the_configured_provider_model(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "landmark_provider", "mistral")
    project = await _cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoCategoryClient([_classification_with_usage(1_000_000, 0)])

    run = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )

    assert run.cost_usd == pytest.approx(_expected_cost(1_000_000, 0, provider="mistral"))
    assert run.cost_usd != pytest.approx(_expected_cost(1_000_000, 0))


# Review-Fund (ship-feature-Runde zu Spec 0207): der `finally`-Block der Cloud-Phase darf die
# URSPRUENGLICHE Exception unter keinen Umstaenden ersetzen - genau dann braucht man eine
# brauchbare Diagnose. Zwei Wege dorthin sind moeglich und beide hier festgeschrieben: ein noch
# nicht gebundener Zaehler (UnboundLocalError) und ein fehlschlagendes Commit der Kostenspalten.


async def test_a_failure_before_the_counters_keeps_the_original_error_message(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wirft eine Anweisung zwischen `try:` und der Zaehlerinitialisierung - realistisch ein
    DB-Fehler beim Laden des Feinlabel-Snapshots -, laeuft der `finally`-Block trotzdem los. Sind
    die Zaehler dort noch ungebunden, ersetzt ein `UnboundLocalError` die Originalmeldung."""
    project = await _cost_setup(db_session, tmp_path, photo_count=1)
    db_session.add(FineLabel(canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0]))
    await db_session.commit()

    def _explode(**kwargs: object) -> NoReturn:
        raise RuntimeError("simulierter Fehler beim Laden des Feinlabel-Snapshots")

    monkeypatch.setattr(worker, "FineLabelSnapshotEntry", _explode)

    run = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: PerPhotoCategoryClient([]),
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.FAILED
    assert run.error_message == "simulierter Fehler beim Laden des Feinlabel-Snapshots"
    assert "UnboundLocalError" not in (run.error_message or "")
    # Die Kostenspalten stehen auf 0 ("erfasst, keine Kosten"), nicht auf NULL: es hat
    # nachweislich kein Cloud-Aufruf stattgefunden.
    assert run.api_calls == 0
    assert run.cost_usd == 0


# specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, ADR 0059 Punkt 6/7 ab hier - Gegenpart
# zu den gleichnamigen Faellen der Landmark-Phase in test_worker_criterion_scoring.py. Auch hier
# bewusst mit einem NICHT voreingestellten Modell, sonst haette der Test keine Trennschaerfe.

_STRONGER_ANTHROPIC_MODEL = VISION_MODELS_BY_PROVIDER["anthropic"][1]


async def test_the_client_the_billing_and_the_persisted_model_are_one_and_the_same_value(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "landmark_model", _STRONGER_ANTHROPIC_MODEL)
    project = await _cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoCategoryClient([_classification_with_usage(1_000_000, 0)])
    received: list[str] = []

    def build(model: str) -> object:
        received.append(model)
        return client

    run = await run_remote_category_classification(
        db_session, project, tmp_path, build_client=build, build_embedder=_fake_embedder
    )

    expected_cost = compute_cost_usd(_STRONGER_ANTHROPIC_MODEL, TokenUsage(1_000_000, 0))
    assert expected_cost is not None
    assert received == [_STRONGER_ANTHROPIC_MODEL]
    assert run.model == _STRONGER_ANTHROPIC_MODEL
    assert run.cost_usd == pytest.approx(expected_cost)
    assert run.cost_usd != pytest.approx(_expected_cost(1_000_000, 0))


async def test_the_default_setting_persists_the_unchanged_default_model(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Akzeptanzkriterium "ohne gesetzte Einstellung exakt wie bisher" auf der Persistenzebene."""
    project = await _cost_setup(db_session, tmp_path, photo_count=1)
    client = PerPhotoCategoryClient([_classification_with_usage(1_000, 10)])

    run = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )

    assert run.model == default_vision_model_for_provider("anthropic")


async def test_an_earlier_run_keeps_its_model_when_a_later_run_uses_another(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Akzeptanzkriterien "Wechsel ohne Datenverlust ruecknehmbar" und "aus welchem Modell ein
    durchgefuehrter Lauf entstanden ist, bleibt nachtraeglich erkennbar": ein Modellwechsel wirkt
    ausschliesslich auf kuenftige Aufrufe, er schreibt keine Vergangenheit um."""
    project = await _cost_setup(db_session, tmp_path, photo_count=2)
    first = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: PerPhotoCategoryClient([_classification_with_usage(1_000, 10)]),
        build_embedder=_fake_embedder,
    )
    first_model = first.model

    monkeypatch.setattr(worker.settings, "landmark_model", _STRONGER_ANTHROPIC_MODEL)
    second = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: PerPhotoCategoryClient([_classification_with_usage(1_000, 10)]),
        build_embedder=_fake_embedder,
    )

    await db_session.refresh(first)
    assert first_model == default_vision_model_for_provider("anthropic")
    assert first.model == first_model
    assert second.model == _STRONGER_ANTHROPIC_MODEL


# --- specs/features/0299-kategorie-konfidenz-anzeigen.md, Umsetzungsschritt 3 -----------------


async def test_the_classification_row_persists_the_confidence_mapping(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    photo, run = await _run_for_one_photo(
        db_session,
        tmp_path,
        RemoteClassification(
            categories=("landschaft", "menschen"),
            fine_labels=(),
            category_confidences={"landschaft": 0.31, "menschen": 0.87},
        ),
    )

    assert run.status == ScanStatus.SUCCESS
    row = (
        (
            await db_session.execute(
                select(PhotoCategoryClassification).where(
                    PhotoCategoryClassification.photo_id == photo.id
                )
            )
        )
        .scalars()
        .one()
    )
    assert row.detected_category_confidences == {"landschaft": 0.31, "menschen": 0.87}


async def test_the_scalar_follows_the_resolved_category_not_the_highest_number(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """DER aufdeckende Fall (Teststrategie der Spec 0299): die Vorrangreihenfolge waehlt einen
    ANDEREN Kandidaten als den mit der hoechsten Konfidenz. `menschen` (precedence 3) gewinnt gegen
    `landschaft` (precedence 10), obwohl `landschaft` die groessere Zahl traegt - der Skalar muss
    dem aufgeloesten Schluessel folgen, nicht dem Maximum."""
    photo, _ = await _run_for_one_photo(
        db_session,
        tmp_path,
        RemoteClassification(
            categories=("landschaft", "menschen"),
            fine_labels=(),
            category_confidences={"landschaft": 0.99, "menschen": 0.12},
        ),
    )

    row = (
        (
            await db_session.execute(
                select(PhotoCategoryClassification).where(
                    PhotoCategoryClassification.photo_id == photo.id
                )
            )
        )
        .scalars()
        .one()
    )
    assert row.category_key == "menschen"
    assert row.category_confidence == 0.12


async def test_the_scalar_is_none_when_the_resolved_category_has_no_number(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Eine nicht leere Abbildung ohne Eintrag fuer die aufgeloeste Kategorie: der Skalar bleibt
    `None`, nie `0.0`."""
    photo, _ = await _run_for_one_photo(
        db_session,
        tmp_path,
        RemoteClassification(
            categories=("landschaft", "menschen"),
            fine_labels=(),
            category_confidences={"landschaft": 0.7},
        ),
    )

    row = (
        (
            await db_session.execute(
                select(PhotoCategoryClassification).where(
                    PhotoCategoryClassification.photo_id == photo.id
                )
            )
        )
        .scalars()
        .one()
    )
    assert row.category_key == "menschen"
    assert row.category_confidence is None
    assert row.detected_category_confidences == {"landschaft": 0.7}


async def test_a_not_recognized_photo_has_no_number_on_either_side(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """`nicht_erkannt` steht gar nicht in `detected_categories` - beide Seiten bleiben leer bzw.
    `None`, und die Zeile entsteht trotzdem (Erfolgssignal der Remote-Phase)."""
    photo, run = await _run_for_one_photo(
        db_session, tmp_path, RemoteClassification(categories=(), fine_labels=())
    )

    assert run.status == ScanStatus.SUCCESS
    row = (
        (
            await db_session.execute(
                select(PhotoCategoryClassification).where(
                    PhotoCategoryClassification.photo_id == photo.id
                )
            )
        )
        .scalars()
        .one()
    )
    assert row.category_key == CATEGORY_NOT_RECOGNIZED
    assert row.detected_category_confidences == {}
    assert row.category_confidence is None


async def test_a_classification_without_any_confidence_writes_an_empty_mapping(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Ein Modell, das die neue Anweisung ignoriert: die Kategorie bleibt gueltig, die Abbildung ist
    leer (`{}` = "erhoben, keine brauchbare Zahl"), der Skalar `None`. Der Lauf scheitert nicht und
    das Foto wird nicht uebersprungen (Best-effort, Akzeptanzkriterium 10)."""
    photo, run = await _run_for_one_photo(
        db_session, tmp_path, RemoteClassification(categories=("tier",), fine_labels=("Hund",))
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.photos_processed == 1
    row = (
        (
            await db_session.execute(
                select(PhotoCategoryClassification).where(
                    PhotoCategoryClassification.photo_id == photo.id
                )
            )
        )
        .scalars()
        .one()
    )
    assert row.detected_category_confidences == {}
    assert row.category_confidence is None


async def test_the_invariant_holds_for_every_written_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """ADR 0067 Punkt 4: `category_confidence == detected_category_confidences.get(category_key)`
    - die einzige Rechtfertigung der bewusst redundanten Spiegelspalte. Ueber ALLE im Lauf
    erzeugten Zeilen geprueft, nicht nur ueber eine."""
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    for index in range(3):
        photo = await _add_photo(db_session, project, f"{index}.jpg", f"etag-{index}")
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo)
    await db_session.commit()

    client = PerPhotoCategoryClient(
        [
            RemoteClassification(
                categories=("tier",), fine_labels=(), category_confidences={"tier": 0.55}
            ),
            RemoteClassification(
                categories=("landschaft", "menschen"),
                fine_labels=(),
                category_confidences={"landschaft": 0.9},
            ),
            RemoteClassification(categories=("menschen",), fine_labels=()),
        ]
    )

    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    rows = (await db_session.execute(select(PhotoCategoryClassification))).scalars().all()
    assert len(rows) == 3
    for row in rows:
        mapping = row.detected_category_confidences or {}
        assert row.category_confidence == mapping.get(row.category_key)
        # Die Abbildung traegt nie einen Schluessel ausserhalb der Kandidatenliste.
        assert set(mapping) <= set(row.detected_categories)


async def test_a_repeat_run_leaves_an_old_row_without_confidences_untouched(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Akzeptanzkriterium 9: auch ein erneuter Lauf fuellt den Altbestand nicht nach - der Worker
    ueberspringt jedes Foto mit vorhandener Klassifizierungszeile (Kostenschutz)."""
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)
    db_session.add(
        PhotoCategoryClassification(
            photo_id=photo.id,
            category_key="tier",
            detected_categories=["tier"],
            provider="anthropic",
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    client = RecordingCategoryClient(
        RemoteClassification(
            categories=("tier",), fine_labels=(), category_confidences={"tier": 0.9}
        )
    )
    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == []
    row = (await db_session.execute(select(PhotoCategoryClassification))).scalars().one()
    assert row.detected_category_confidences is None
    assert row.category_confidence is None


# --------------------------------------------------------------------------------------------
# specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-vier-
# teilschritte-und-laufeigene-cloud-bilanz.md Punkt 2/6: Live-Zaehler der Fehlschlaege und
# Modell-Fruehschreibung - das Gegenstueck zur Landmark-Phase in
# test_worker_criterion_scoring.py.
# --------------------------------------------------------------------------------------------


class SnapshottingCategoryClient:
    """Zeichnet vor JEDEM Aufruf den Zustand der Lauf-Zeile auf. Die Zeile wird dem Client ueber
    den `run`-Parameter von run_remote_category_classification vorab uebergeben - sonst haette er
    waehrend des Laufs keinen Zugriff darauf."""

    def __init__(
        self,
        run: RemoteCategoryClassificationRun,
        results: list[RemoteClassification | Exception],
    ) -> None:
        self._run = run
        self._results = results
        self.snapshots: list[tuple[int | None, int | None, int | None, str | None]] = []

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
        self.snapshots.append(
            (
                self._run.photos_processed,
                self._run.failed_calls,
                self._run.api_calls,
                self._run.model,
            )
        )
        result = self._results[len(self.snapshots) - 1]
        if isinstance(result, Exception):
            raise result
        return result


async def _prepared_remote_run(
    session: AsyncSession, project: Project
) -> RemoteCategoryClassificationRun:
    run = RemoteCategoryClassificationRun(project_id=project.id, status=ScanStatus.RUNNING)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def test_failed_calls_are_written_at_the_existing_block_commit_point(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0068 Punkt 2: `failed_calls` wandert an den bereits vorhandenen Block-Commit-Punkt
    (`photos_processed`/`last_progress_at`), NICHT in den `finally` - die Story verlangt die Zahl
    WAEHREND des Laufs, nicht erst nach seinem Abschluss."""
    monkeypatch.setattr(worker.settings, "remote_category_classification_concurrency", 1)
    project = await _cost_setup(db_session, tmp_path, photo_count=3)
    run = await _prepared_remote_run(db_session, project)
    client = SnapshottingCategoryClient(
        run,
        [
            _classification_with_usage(1_000, 10),
            RemoteCategoryClassificationApiError("simulierter Cloud-Fehler"),
            _classification_with_usage(1_000, 10),
        ],
    )

    result = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
        run=run,
    )

    assert [snapshot[1] for snapshot in client.snapshots] == [0, 0, 1]
    assert result.failed_calls == 1


async def test_the_model_is_written_before_the_first_classification_call(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR 0068 Punkt 6: Modell (und damit der abgeleitete Anbieter) stehen schon WAEHREND des
    Teilschritts da, der BETRAG bleibt am Phasenende eingefroren. Der Sentinel-Modellwert kommt
    aus einer nicht voreingestellten Einstellung, sonst waere die Assertion tautologisch."""
    stronger = VISION_MODELS_BY_PROVIDER["anthropic"][1]
    monkeypatch.setattr(worker.settings, "landmark_model", stronger)
    monkeypatch.setattr(worker.settings, "remote_category_classification_concurrency", 1)
    project = await _cost_setup(db_session, tmp_path, photo_count=2)
    run = await _prepared_remote_run(db_session, project)
    client = SnapshottingCategoryClient(run, [_classification_with_usage(1_000, 10)] * 2)

    result = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
        run=run,
    )

    first_processed, first_failed, first_api_calls, first_model = client.snapshots[0]
    assert first_model == stronger
    assert first_processed == 0
    assert first_failed == 0
    assert first_api_calls == 0
    assert result.api_calls == 2
    assert result.cost_usd is not None and result.cost_usd > 0


async def test_a_passed_run_is_reused_and_no_second_row_is_created(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """ADR 0068 Punkt 3: run_classification legt die Remote-Zeile selbst an und reicht sie
    hinein, damit der Fremdschluessel schon vor dem ersten Aufruf steht. Wuerde diese Funktion
    trotzdem eine eigene Zeile anlegen, zeigte der Fremdschluessel auf eine leere Karteileiche."""
    project = await _cost_setup(db_session, tmp_path, photo_count=1)
    run = await _prepared_remote_run(db_session, project)

    result = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: PerPhotoCategoryClient([_classification_with_usage(1_000, 10)]),
        build_embedder=_fake_embedder,
        run=run,
    )

    assert result.id == run.id
    rows = (await db_session.execute(select(RemoteCategoryClassificationRun))).scalars().all()
    assert len(rows) == 1


async def test_a_direct_call_still_creates_its_own_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Der Direktaufruf (Tests, kuenftige Aufrufer) legt die Zeile weiterhin selbst an - der neue
    Parameter ist ein Angebot, keine Vorbedingung."""
    project = await _cost_setup(db_session, tmp_path, photo_count=1)

    result = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda _model: PerPhotoCategoryClient([_classification_with_usage(1_000, 10)]),
        build_embedder=_fake_embedder,
    )

    rows = (await db_session.execute(select(RemoteCategoryClassificationRun))).scalars().all()
    assert [row.id for row in rows] == [result.id]


class TestRemoteCallBookkeepingInvariant:
    """ADR 0068 Punkt 2: `photos_processed == api_calls + failed_calls`, hier fuer die
    Remote-Kategorie-Phase."""

    async def test_all_calls_successful(self, db_session: AsyncSession, tmp_path: Path) -> None:
        project = await _cost_setup(db_session, tmp_path, photo_count=3)
        client = PerPhotoCategoryClient([_classification_with_usage(1_000, 10)] * 3)

        run = await run_remote_category_classification(
            db_session,
            project,
            tmp_path,
            build_client=lambda _model: client,
            build_embedder=_fake_embedder,
        )

        assert run.failed_calls == 0
        assert_call_bookkeeping_invariant(run)

    async def test_mixed_success_and_failure(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        project = await _cost_setup(db_session, tmp_path, photo_count=3)
        client = PerPhotoCategoryClient(
            [
                _classification_with_usage(1_000, 10),
                RemoteCategoryClassificationApiError("simulierter Cloud-Fehler"),
                _classification_with_usage(1_000, 10),
            ]
        )

        run = await run_remote_category_classification(
            db_session,
            project,
            tmp_path,
            build_client=lambda _model: client,
            build_embedder=_fake_embedder,
        )

        assert run.api_calls == 2
        assert run.failed_calls == 1
        assert_call_bookkeeping_invariant(run)

    async def test_every_call_failed(self, db_session: AsyncSession, tmp_path: Path) -> None:
        project = await _cost_setup(db_session, tmp_path, photo_count=2)
        client = PerPhotoCategoryClient(
            [
                RemoteCategoryClassificationApiError("a"),
                RemoteCategoryClassificationApiError("b"),
            ]
        )

        run = await run_remote_category_classification(
            db_session,
            project,
            tmp_path,
            build_client=lambda _model: client,
            build_embedder=_fake_embedder,
        )

        assert run.api_calls == 0
        assert run.failed_calls == 2
        assert_call_bookkeeping_invariant(run)

    @pytest.mark.parametrize("consent", [True, False], ids=["ohne-kandidaten", "ohne-consent"])
    async def test_an_untouched_phase_leaves_failed_calls_null(
        self, db_session: AsyncSession, tmp_path: Path, consent: bool
    ) -> None:
        """`NULL` statt `0`: die Phase wurde nicht betreten. Die Bilanz sagt daraufhin "kein
        Cloud-Teilschritt", statt eine leere Nullzeile zu zeigen."""
        project = await _cost_setup(db_session, tmp_path, photo_count=0 if consent else 1)
        project.cloud_vision_detection_enabled = consent
        await db_session.commit()

        run = await run_remote_category_classification(
            db_session,
            project,
            tmp_path,
            build_client=lambda _model: PerPhotoCategoryClient([]),
            build_embedder=_fake_embedder,
        )

        assert run.failed_calls is None
        assert_call_bookkeeping_invariant(run)


async def test_counting_failures_adds_no_log_line_with_provider_raw_text(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Security-Muss der Spec 0348: das Zaehlen der Fehlschlaege greift auf die
    `asyncio.gather(return_exceptions=True)`-Ergebnisliste zu und darf dabei KEINE neue Logzeile
    einfuehren, die Rohtext einer Provider-Antwort transportiert.

    Es gilt unveraendert die Regel aus ADR 0034 Punkt 5: feste Meldung plus
    `type(exc).__name__` - eine Provider-Antwort kann die Modellaussage ueber ein Familienfoto,
    im Fehlerfall Base64-Bilddaten und ein Key-Echo enthalten. Geprueft wird deshalb NEGATIV: der
    Ausnahmetext selbst taucht in keiner Logzeile auf, und keine Zeile traegt einen
    Exception-Stacktrace (`exc_info=True`)."""
    secret_marker = "GEHEIM-BASE64-ECHO-4711"
    project = await _cost_setup(db_session, tmp_path, photo_count=2)
    client = PerPhotoCategoryClient(
        [
            RemoteCategoryClassificationApiError(secret_marker),
            _classification_with_usage(1_000, 10),
        ]
    )

    with caplog.at_level(logging.DEBUG, logger="photosort"):
        run = await run_remote_category_classification(
            db_session,
            project,
            tmp_path,
            build_client=lambda _model: client,
            build_embedder=_fake_embedder,
        )

    assert run.failed_calls == 1
    # Die BESTEHENDE Fehlerzeile (ADR 0034) traegt `str(exc)` bewusst - sie ist an der
    # Konstruktionsstelle sanitiert und nicht Gegenstand dieser Story. Neu hinzugekommen sein
    # darf keine weitere Zeile mit diesem Text und keine mit Stacktrace.
    lines_with_marker = [
        record for record in caplog.records if secret_marker in record.getMessage()
    ]
    assert len(lines_with_marker) == 1, [record.getMessage() for record in caplog.records]
    assert all(record.exc_info is None for record in caplog.records)


# specs/features/0382-cloud-rate-limits-aussitzen.md, K8/K9 ab hier - der zweite Cloud-
# Teilschritt, strukturell analog zur Landmark-Phase in test_worker_criterion_scoring.py. Ueber
# die vorhandene Factory-Injektion wird ausnahmsweise ein ECHTER Client mit httpx.MockTransport
# hereingereicht: ein Fake-Double abstrahierte genau die Schicht weg, um die es geht.


def _throttle_recording_waits(waits: list[float]) -> CloudRequestThrottle:
    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    return CloudRequestThrottle(min_interval_seconds=0.0, clock=lambda: 0.0, sleep=sleep)


def _category_transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        index = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        return responses[index]

    return httpx.MockTransport(handler)


def _category_ok() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"categories": ["tier"], "fine_labels": ["Hund"]}),
                }
            ]
        },
    )


async def _run_with_real_category_client(
    db_session: AsyncSession,
    tmp_path: Path,
    transport: httpx.MockTransport,
    throttle: CloudRequestThrottle,
) -> tuple[RemoteCategoryClassificationRun, Photo]:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
    await _add_score(db_session, photo)
    _write_display_variant(tmp_path, photo)

    client = AnthropicCategoryClient(
        api_key="sk-test-not-a-real-secret",
        model=default_vision_model_for_provider("anthropic"),
        transport=transport,
        throttle=throttle,
    )
    run = await run_remote_category_classification(
        db_session,
        project,
        cache_dir=tmp_path,
        build_client=lambda _model: client,
        build_embedder=_fake_embedder,
    )
    return run, photo


class TestTheRemoteCategoryPhaseSitsOutARateLimit:
    async def test_a_429_followed_by_a_200_still_produces_the_result_row(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        waits: list[float] = []
        run, photo = await _run_with_real_category_client(
            db_session,
            tmp_path,
            _category_transport([httpx.Response(429), _category_ok()]),
            _throttle_recording_waits(waits),
        )

        assert run.status == ScanStatus.SUCCESS
        assert run.failed_calls == 0
        rows = (
            (
                await db_session.execute(
                    select(PhotoCategoryClassification).where(
                        PhotoCategoryClassification.photo_id == photo.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        errors = (
            (
                await db_session.execute(
                    select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
                )
            )
            .scalars()
            .all()
        )
        assert errors == []
        assert waits == [2.0]

    async def test_a_permanent_429_keeps_todays_behaviour(
        self, db_session: AsyncSession, tmp_path: Path
    ) -> None:
        waits: list[float] = []
        run, photo = await _run_with_real_category_client(
            db_session,
            tmp_path,
            _category_transport([httpx.Response(429)]),
            _throttle_recording_waits(waits),
        )

        assert run.status == ScanStatus.SUCCESS
        assert run.failed_calls == 1
        rows = (
            (
                await db_session.execute(
                    select(PhotoCategoryClassification).where(
                        PhotoCategoryClassification.photo_id == photo.id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert rows == []
        error_row = (
            await db_session.execute(
                select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
            )
        ).scalar_one()
        assert "429" in error_row.error_message
        assert waits == [2.0, 4.0, 8.0, 16.0]


class TestTheRemoteCategoryPhaseSummarisesItsThrottling:
    async def test_without_any_waiting_no_line_is_written(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        throttle = _throttle_recording_waits([])
        monkeypatch.setattr(worker, "throttle_for_provider", lambda _provider: throttle)
        project = await _make_project(db_session)
        project.cloud_vision_detection_enabled = True
        await db_session.commit()
        photo = await _add_photo(db_session, project, "a.jpg", "etag-1")
        await _add_score(db_session, photo)
        _write_display_variant(tmp_path, photo)
        client = PerPhotoCategoryClient(
            [RemoteClassification(categories=("tier",), fine_labels=("Hund",))]
        )

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            run = await run_remote_category_classification(
                db_session,
                project,
                cache_dir=tmp_path,
                build_client=lambda _model: client,
                build_embedder=_fake_embedder,
            )

        assert run.status == ScanStatus.SUCCESS
        assert [record for record in caplog.records if record.name == "photosort.worker"] == []

    async def test_after_waiting_exactly_one_summary_line_is_written(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        throttle = _throttle_recording_waits([])
        monkeypatch.setattr(worker, "throttle_for_provider", lambda _provider: throttle)

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            run, _photo = await _run_with_real_category_client(
                db_session,
                tmp_path,
                _category_transport([httpx.Response(429), _category_ok()]),
                throttle,
            )

        assert run.status == ScanStatus.SUCCESS
        records = [record for record in caplog.records if record.name == "photosort.worker"]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        message = records[0].getMessage()
        assert "remote_category" in message
        assert "anthropic" in message
        # Genau EINE Wiederholung - Singular. Bewusst mit dem Folgewort assertiert:
        # `"1 Wiederholung" in "1 Wiederholungen"` waere sonst auch beim Plural wahr.
        assert "1 Wiederholung nach 429" in message
        assert "2.0 s Wartezeit" in message

    async def test_the_summary_reports_only_the_difference_of_this_phase(
        self,
        db_session: AsyncSession,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ohne diesen Fall schriebe der zweite Cloud-Teilschritt sich die Wartezeit des ersten zu
        und waere bei einem einzelnen Teilschritt trotzdem gruen."""
        throttle = _throttle_recording_waits([])
        throttle.record_retry_wait(41.0)
        throttle.record_retry_wait(1.0)
        monkeypatch.setattr(worker, "throttle_for_provider", lambda _provider: throttle)

        with caplog.at_level(logging.WARNING, logger="photosort.worker"):
            await _run_with_real_category_client(
                db_session,
                tmp_path,
                _category_transport([httpx.Response(429), _category_ok()]),
                throttle,
            )

        records = [record for record in caplog.records if record.name == "photosort.worker"]
        assert len(records) == 1
        message = records[0].getMessage()
        assert "42.0" not in message
        # Genau EINE Wiederholung - Singular. Bewusst mit dem Folgewort assertiert:
        # `"1 Wiederholung" in "1 Wiederholungen"` waere sonst auch beim Plural wahr.
        assert "1 Wiederholung nach 429" in message
        assert "2.0 s Wartezeit" in message
