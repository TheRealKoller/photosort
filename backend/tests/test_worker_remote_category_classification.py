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

from photosort import pricing, worker
from photosort.cloud_vision import VISION_MODEL_BY_PROVIDER, TokenUsage
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
    RemoteCategoryClassificationApiError,
    RemoteClassification,
)
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
        build_client=lambda: client,
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
        build_client=lambda: RecordingCategoryClient(classification),
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
        await db_session.execute(
            select(PhotoCategoryClassification).where(
                PhotoCategoryClassification.photo_id == photo.id
            )
        )
    ).scalars().all()
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
        await db_session.execute(
            select(PhotoFineLabel).where(PhotoFineLabel.photo_id == photo.id)
        )
    ).scalars().all()
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
        await db_session.execute(
            select(PhotoCategoryClassification).where(
                PhotoCategoryClassification.photo_id == photo.id
            )
        )
    ).scalars().one()
    assert classification.category_key == "nicht_erkannt"
    assert classification.detected_categories == []

    fine_labels = (
        await db_session.execute(
            select(PhotoFineLabel).where(PhotoFineLabel.photo_id == photo.id)
        )
    ).scalars().all()
    assert [row.raw_label for row in fine_labels] == ["Fabelwesen"]


async def test_a_photo_without_fine_labels_gets_a_classification_row_anyway(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    photo, _ = await _run_for_one_photo(
        db_session, tmp_path, RemoteClassification(categories=("tier",), fine_labels=())
    )

    assert (
        await db_session.execute(
            select(PhotoFineLabel).where(PhotoFineLabel.photo_id == photo.id)
        )
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
        await db_session.execute(
            select(PhotoFineLabel).where(PhotoFineLabel.photo_id == photo.id)
        )
    ).scalars().all()
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
            build_client=lambda: client,
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
            self, image_bytes: bytes, mime_type: str, photo_id: int
        ) -> RemoteClassification:
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
            self, image_bytes: bytes, mime_type: str, photo_id: int
        ) -> RemoteClassification:
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
        build_client=lambda: RecordingCategoryClient(),
        build_embedder=_fake_embedder,
    )
    await run_remote_category_classification(
        db_session,
        project_b,
        cache_dir=tmp_path,
        # Gleicher normalisierter Text ("Hund") -> exakter Fast-Path, dieselbe fine_labels-
        # Zeile wird wiederverwendet statt einer zweiten Registry-Zeile (ADR 0032 Punkt 2).
        build_client=lambda: RecordingCategoryClient(),
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
        build_client=lambda: client,
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
            build_client=lambda: RecordingCategoryClient(),
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
        VISION_MODEL_BY_PROVIDER[provider],
        TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )
    assert cost is not None
    return cost


async def _cost_setup(
    db_session: AsyncSession, tmp_path: Path, *, photo_count: int
) -> Project:
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
        db_session, project, tmp_path, build_client=lambda: client, build_embedder=_fake_embedder
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
        db_session, project, tmp_path, build_client=lambda: client, build_embedder=_fake_embedder
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
        db_session, project, tmp_path, build_client=lambda: client, build_embedder=_fake_embedder
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
        db_session, project, tmp_path, build_client=lambda: client, build_embedder=_fake_embedder
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
        build_client=lambda: PerPhotoCategoryClient([_classification_with_usage(1_000, 10)]),
        build_embedder=_fake_embedder,
    )
    assert first.api_calls == 1

    second = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda: PerPhotoCategoryClient([]),
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
        db_session, project, tmp_path, build_client=lambda: client, build_embedder=_fake_embedder
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
        db_session, project, tmp_path, build_client=lambda: client, build_embedder=_fake_embedder
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
    db_session.add(
        FineLabel(canonical_key="hund", display_name="Hund", embedding=[1.0, 0.0])
    )
    await db_session.commit()

    def _explode(**kwargs: object) -> NoReturn:
        raise RuntimeError("simulierter Fehler beim Laden des Feinlabel-Snapshots")

    monkeypatch.setattr(worker, "FineLabelSnapshotEntry", _explode)

    run = await run_remote_category_classification(
        db_session,
        project,
        tmp_path,
        build_client=lambda: PerPhotoCategoryClient([]),
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.FAILED
    assert run.error_message == "simulierter Fehler beim Laden des Feinlabel-Snapshots"
    assert "UnboundLocalError" not in (run.error_message or "")
    # Die Kostenspalten stehen auf 0 ("erfasst, keine Kosten"), nicht auf NULL: es hat
    # nachweislich kein Cloud-Aufruf stattgefunden.
    assert run.api_calls == 0
    assert run.cost_usd == 0
