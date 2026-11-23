"""Kriterien-Lauf: Auswahl der Sehenswuerdigkeits-Kandidaten, Einwilligung, Szenen-Klassifikator
genau einmal je Foto.
(Aufgeteilt aus test_worker_criterion_scoring.py, Spec 0651.)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import worker
from photosort.landmark import (
    LandmarkApiError,
    LandmarkDetection,
    PlaceHint,
)
from photosort.models import (
    CloudVisionPhase,
    CriterionScoringRun,
    CriterionSource,
    PhotoCloudVisionError,
    PhotoCriterionScore,
    PhotoLandmarkDetection,
    PhotoRanking,
    ScanStatus,
)
from photosort.worker import run_criterion_scoring
from photosort.worker._criterion import local as worker_local
from photosort.worker._criterion.landmark import select_landmark_candidates
from tests.support import make_project as _make_project
from tests.support import write_display_variant
from tests.support.criterion_scoring import (
    CancellingLandmarkClient,
    PerPhotoLandmarkClient,
    RecordingLandmarkClient,
    _add_photo,
    _add_score,
    _add_successful_scoring_run,
    _criteria_of,
    _failing_landmark_client_builder,
    _flat_image,
    _landscape_scene_classifier,
    _no_aesthetics_model,
    _no_animal_detector,
    _no_face_detector,
    _no_face_landmarker,
    _no_scene_classifier,
    _scene_classifier_stub,
)


def _textured_image_below_landscape_threshold() -> Image.Image:
    # Abgrenzung zu _flat_image (siehe dortiger Kommentar zu content_landscape oben) - Textur
    # statt flacher Farbe, damit ohne SceneClassifierStub weder content_landscape noch gebaeude
    # die Vorfilterungs-Schwelle erreichen.
    from PIL import ImageDraw

    image = Image.new("RGB", (160, 160), color=(30, 60, 120))
    draw = ImageDraw.Draw(image)
    for offset in range(0, 160, 8):
        draw.line((offset, 0, 160 - offset, 160), fill=(220, 180, 90), width=2)
    return image


class ConcurrencyTrackingLandmarkClient:
    """Analog FakeOpenCloudClient.max_concurrent_downloads (test_worker_scan_project.py) - zaehlt
    gleichzeitig aktive detect()-Aufrufe, kein Wall-Clock-Timing-Assertion."""

    def __init__(self) -> None:
        self._active = 0
        self.max_concurrent = 0
        self.call_count = 0

    async def detect(
        self, image_bytes: bytes, mime_type: str, hint: PlaceHint | None
    ) -> LandmarkDetection:
        self.call_count += 1
        self._active += 1
        self.max_concurrent = max(self.max_concurrent, self._active)
        try:
            await asyncio.sleep(0.01)
            return LandmarkDetection(name="Eiffelturm", confidence=0.9)
        finally:
            self._active -= 1


class TestSelectLandmarkCandidates:
    """Reine, DB-freie Funktion (analog classify_scan_entries) - isoliert testbar, inkl. dem
    Grenzfall exakt auf der Schwelle, ohne einen echten Kandidatenlauf aufzusetzen."""

    def test_below_both_thresholds_is_not_a_candidate(self) -> None:
        candidate_values = {1: {"landschaft": 0.0, "gebaeude": 0.0}}
        assert select_landmark_candidates(candidate_values, set()) == []

    def test_landschaft_at_exactly_the_threshold_is_a_candidate_inclusive(self) -> None:
        # specs/features/0217, ADR 0047 Punkt 5: Vorfilterung auf `landschaft` statt
        # `content_landscape` UMGESTELLT (nicht ergaenzt).
        candidate_values = {1: {"landschaft": 0.01, "gebaeude": 0.0}}
        assert select_landmark_candidates(candidate_values, set()) == [1]

    def test_gebaeude_at_exactly_the_threshold_is_a_candidate_inclusive(self) -> None:
        candidate_values = {1: {"landschaft": 0.0, "gebaeude": 0.01}}
        assert select_landmark_candidates(candidate_values, set()) == [1]

    def test_just_below_landschaft_threshold_is_not_a_candidate(self) -> None:
        candidate_values = {1: {"landschaft": 0.009, "gebaeude": 0.0}}
        assert select_landmark_candidates(candidate_values, set()) == []

    def test_a_high_content_landscape_value_alone_is_no_longer_a_candidate(self) -> None:
        assert select_landmark_candidates({1: {"content_landscape": 1.0}}, set()) == []

    def test_missing_values_count_as_not_present(self) -> None:
        assert select_landmark_candidates({1: {}}, set()) == []

    def test_already_scored_photo_is_excluded_even_if_it_would_pass_the_threshold(self) -> None:
        candidate_values = {1: {"landschaft": 0.9}}
        assert select_landmark_candidates(candidate_values, {1}) == []


async def test_consent_disabled_by_default_never_calls_landmark_client_builder(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria_keys = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert "landmark" not in criteria_keys


async def test_consent_enabled_sends_a_landscape_photo_to_the_landmark_client(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    client = RecordingLandmarkClient(
        detection=LandmarkDetection(name="Eiffelturm", confidence=0.87)
    )

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert len(client.calls) == 1
    image_bytes, mime_type = client.calls[0]
    assert mime_type == "image/jpeg"
    assert image_bytes  # echte Bilddaten, kein leerer Platzhalter
    # Review-Fund (ship-feature-Runde): run_criterion_scoring muss einen vom Client angebotenen
    # aclose() tatsaechlich aufrufen (Ressourcen-Cleanup des echten httpx.AsyncClient), genau
    # einmal - kein Doppel-Close.
    assert client.aclose_calls == 1

    criteria = {
        c.criterion_key: c
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["landmark"].value == 0.87
    assert criteria["landmark"].source == CriterionSource.CLOUD

    detection_row = (
        await db_session.execute(
            select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
        )
    ).scalar_one()
    assert detection_row.name == "Eiffelturm"
    assert detection_row.confidence == 0.87
    # specs/features/0054-mistral-provider-option-cloud-landmark.md: unveraendertes
    # LANDMARK_PROVIDER (Default) -> "anthropic" wird atomar mit name/confidence persistiert.
    assert detection_row.provider == "anthropic"


# specs/features/0054-mistral-provider-option-cloud-landmark.md, decisions/0031-mistral-provider-
# option-cloud-landmark.md Punkt 5 ab hier: provider-Wert wird korrekt persistiert +
# Umschalt-Regressionstest (altes provider-Feld bleibt bei einem Providerwechsel unveraendert -
# das bestehende Skip-Verhalten fuer bereits gescorte Fotos, ADR 0025 Punkt 3, greift providerun-
# abhaengig weiterhin).
async def test_landmark_detection_row_persists_the_configured_provider(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "landmark_provider", "mistral")
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    client = RecordingLandmarkClient(detection=LandmarkDetection(name="Eiffelturm", confidence=0.9))

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    detection_row = (
        await db_session.execute(
            select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
        )
    ).scalar_one()
    assert detection_row.provider == "mistral"


async def test_provider_switch_between_runs_does_not_overwrite_the_stored_provider(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    first_client = RecordingLandmarkClient(
        detection=LandmarkDetection(name="Eiffelturm", confidence=0.87)
    )
    first_run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: first_client,
        use_cloud=True,
    )
    assert first_run.status == ScanStatus.SUCCESS
    assert len(first_client.calls) == 1

    # LANDMARK_PROVIDER wird "mitten im Projektverlauf" umgeschaltet (ADR 0031 Punkt 5) - das
    # bereits gescorte Foto bleibt aber ein Skip-Kandidat (existierende PhotoCriterionScore-Zeile),
    # der Client wird fuer dieses Foto also gar nicht erneut aufgerufen.
    monkeypatch.setattr(worker.settings, "landmark_provider", "mistral")
    second_client = RecordingLandmarkClient(
        detection=LandmarkDetection(name="Kolosseum", confidence=0.5)
    )
    second_run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: second_client,
        use_cloud=True,
    )

    assert second_run.status == ScanStatus.SUCCESS
    assert second_client.calls == []  # nicht erneut gesendet (bestehendes Skip-Verhalten)

    detection_row = (
        await db_session.execute(
            select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
        )
    ).scalar_one()
    # provider bleibt beim alten Wert stehen, wird nicht ueberschrieben (Akzeptanzkriterium).
    assert detection_row.provider == "anthropic"
    assert detection_row.name == "Eiffelturm"


async def test_photo_without_an_identified_landmark_name_gets_zero_score_and_no_detection_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    client = RecordingLandmarkClient(detection=LandmarkDetection(name=None, confidence=0.0))

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["landmark"] == 0.0

    detections = (await db_session.execute(select(PhotoLandmarkDetection))).scalars().all()
    assert detections == []


async def test_vorfilterung_sends_photo_that_only_meets_the_gebaeude_threshold(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _textured_image_below_landscape_threshold())

    client = RecordingLandmarkClient()

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_scene_classifier_stub,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert len(client.calls) == 1


async def test_vorfilterung_does_not_send_photo_below_both_thresholds_empty_candidate_pool(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Zugleich der "leerer Kandidatenpool nach Vorfilterung"-Edge-Case der Teststrategie: das
    # einzige Foto des Laufs erreicht weder content_landscape noch gebaeude, LandmarkClientLike.
    # detect() wird nie aufgerufen, kein photo_landmark_detections-Eintrag.
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _textured_image_below_landscape_threshold())

    client = RecordingLandmarkClient()

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == []
    detections = (await db_session.execute(select(PhotoLandmarkDetection))).scalars().all()
    assert detections == []


async def test_skip_already_scored_photo_but_local_criteria_are_recomputed(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo, sharpness=50.0)
    write_display_variant(tmp_path, photo, _flat_image())

    db_session.add(
        PhotoCriterionScore(
            photo_id=photo.id,
            criterion_key="landmark",
            value=0.42,
            source=CriterionSource.CLOUD,
            computed_at=datetime(2023, 1, 1),
        )
    )
    await db_session.commit()

    client = RecordingLandmarkClient()

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == []  # nicht erneut gesendet, obwohl die Vorfilterung erneut passen wuerde

    criteria = {
        c.criterion_key: c.value
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert criteria["landmark"] == 0.42  # unveraendert stehen geblieben
    assert criteria["sharpness"] == 0.25  # 50.0 / 200.0 - trotzdem neu berechnet (nur landmark

    # ist die Ausnahme vom "jeder Lauf scort neu"-Grundsatz, kein versehentliches Ueberspringen
    # des gesamten Fotos).


async def test_failed_landmark_call_leaves_no_row_and_becomes_a_candidate_again_next_run(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    failing_client = RecordingLandmarkClient(raise_error=True)

    # Spec 0056/ADR 0034: der fehlgeschlagene Cloud-Aufruf muss genau einen WARNING-Log-Eintrag
    # erzeugen, bevor das bestehende continue greift.
    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        run = await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_landscape_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=lambda _model: failing_client,
            use_cloud=True,
        )

    assert run.status == ScanStatus.SUCCESS  # best-effort, kein Laufabbruch
    assert len(failing_client.calls) == 1
    # aclose() muss auch dann laufen, wenn der Cloud-Aufruf selbst fehlschlaegt (finally-Block).
    assert failing_client.aclose_calls == 1
    criteria_keys = {
        c.criterion_key
        for c in (
            await db_session.execute(
                select(PhotoCriterionScore).where(PhotoCriterionScore.photo_id == photo.id)
            )
        ).scalars()
    }
    assert "landmark" not in criteria_keys
    # Andere Kriterien dieses Fotos bleiben unberuehrt.
    assert "sharpness" in criteria_keys
    assert "content_landscape" in criteria_keys

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.name == "photosort.worker"
    assert record.levelno == logging.WARNING
    assert record.exc_info is None  # ADR 0034 Punkt 5: kein exc_info=True/Traceback.
    assert "LandmarkApiError" in record.message
    assert str(photo.id) in record.message
    assert photo.relative_path in record.message
    assert "landmark" in record.message.lower()

    succeeding_client = RecordingLandmarkClient()
    run2 = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: succeeding_client,
        use_cloud=True,
    )

    assert run2.status == ScanStatus.SUCCESS
    # kein landmark-Eintrag vorhanden -> automatisch erneut Kandidat (ersetzt einen dedizierten
    # Retry-Mechanismus, ADR 0025 Punkt 3).
    assert len(succeeding_client.calls) == 1


# specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
# fehler-persistierung.md Punkt 2/3 ab hier: worker/_runs.py::record_cloud_vision_error/
# clear_cloud_vision_error - eigene DB-Zustands-Tests, unabhaengig von der API-Sichtbarkeit
# (Teststrategie-Abschnitt der Spec).
async def test_failed_landmark_call_persists_a_cloud_vision_error_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    failing_client = RecordingLandmarkClient(raise_error=True)

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: failing_client,
        use_cloud=True,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    stored = result.scalar_one()
    assert stored.phase == CloudVisionPhase.LANDMARK
    assert stored.error_type == "LandmarkApiError"
    assert "simulierter Cloud-Fehler" in stored.error_message
    assert stored.attempted_at is not None


async def test_successful_landmark_call_after_a_previous_failure_clears_the_error_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: RecordingLandmarkClient(raise_error=True),
        use_cloud=True,
    )
    assert (
        await db_session.execute(
            select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
        )
    ).scalar_one_or_none() is not None

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: RecordingLandmarkClient(),
        use_cloud=True,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    assert result.scalar_one_or_none() is None


async def test_successful_landmark_call_without_a_name_still_clears_the_error_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # specs/architecture/0002-testkonzept.md ("Read-Time-Prioritaets-Kaskade..." fuer ADR 0035):
    # "Landmark-Erfolg ohne erkannten Namen (no_result) loescht eine vorher bestehende Fehler-
    # Zeile ebenfalls" - eigener Testfall, der das explizit vom Erfolgspfad MIT Namen (RESULT,
    # siehe test_successful_landmark_call_after_a_previous_failure_clears_the_error_row oben)
    # abgrenzt: hier bleibt die PhotoLandmarkDetection-Zeile bewusst aus (detection.name is None),
    # trotzdem muss die Fehler-Zeile geloescht werden - der Loesch-Aufruf haengt am erfolgreichen
    # Cloud-Aufruf selbst, nicht an der (bedingten) PhotoLandmarkDetection-Anlage.
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: RecordingLandmarkClient(raise_error=True),
        use_cloud=True,
    )
    assert (
        await db_session.execute(
            select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
        )
    ).scalar_one_or_none() is not None

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: RecordingLandmarkClient(
            detection=LandmarkDetection(name=None, confidence=0.0)
        ),
        use_cloud=True,
    )

    error_result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    assert error_result.scalar_one_or_none() is None

    detection_result = await db_session.execute(
        select(PhotoLandmarkDetection).where(PhotoLandmarkDetection.photo_id == photo.id)
    )
    assert detection_result.scalar_one_or_none() is None  # kein Name -> keine Detection-Zeile.

    criterion_result = await db_session.execute(
        select(PhotoCriterionScore).where(
            PhotoCriterionScore.photo_id == photo.id,
            PhotoCriterionScore.criterion_key == "landmark",
        )
    )
    assert criterion_result.scalar_one().value == 0.0  # no_result-Signal bleibt bestehen.


async def test_repeated_landmark_failures_upsert_the_same_error_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    class _RaisingClient:
        def __init__(self, message: str) -> None:
            self._message = message

        async def detect(
            self, image_bytes: bytes, mime_type: str, hint: PlaceHint | None
        ) -> LandmarkDetection:
            raise LandmarkApiError(self._message)

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: _RaisingClient("erster Fehlschlag"),
        use_cloud=True,
    )
    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: _RaisingClient("zweiter Fehlschlag"),
        use_cloud=True,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1  # Upsert, kein Verlauf (composite PK photo_id+phase).
    assert "zweiter Fehlschlag" in rows[0].error_message
    assert "erster Fehlschlag" not in rows[0].error_message


async def test_landmark_error_message_is_capped_at_500_characters(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    overlong_message = "x" * 600

    class _RaisingClient:
        async def detect(
            self, image_bytes: bytes, mime_type: str, hint: PlaceHint | None
        ) -> LandmarkDetection:
            raise LandmarkApiError(overlong_message)

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: _RaisingClient(),
        use_cloud=True,
    )

    result = await db_session.execute(
        select(PhotoCloudVisionError).where(PhotoCloudVisionError.photo_id == photo.id)
    )
    stored = result.scalar_one()
    assert len(stored.error_message) == 500
    assert stored.error_message == overlong_message[:500]


async def test_landmark_calls_are_limited_by_landmark_api_concurrency(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(worker.settings, "landmark_api_concurrency", 2)
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)

    for index in range(5):
        photo = await _add_photo(
            db_session, project, f"p{index}.jpg", f"etag-{index}", datetime(2023, 1, 1, tzinfo=UTC)
        )
        await _add_score(db_session, photo)
        write_display_variant(tmp_path, photo, _flat_image())

    client = ConcurrencyTrackingLandmarkClient()

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.call_count == 5
    assert client.max_concurrent > 1
    assert client.max_concurrent <= 2


async def test_multiple_simultaneously_failing_landmark_calls_each_log_their_own_photo(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Spec 0056/ADR 0034, Edge Case "mehrere gleichzeitig fehlschlagende Fotos in einem Block":
    # jede Message muss ihr eigenes photo.id referenzieren, keine Vertauschung durch die parallele
    # zip(block_ids, results, strict=True)-Zuordnung. Bisher fehlte fuer die Landmark-Phase ein
    # Test mit MEHREREN gleichzeitigen Fehlschlaegen im selben Block, nur Einzelfehlschlag war
    # abgedeckt (test_failed_landmark_call_leaves_no_row_and_becomes_a_candidate_again_next_run).
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)

    photo_a = await _add_photo(
        db_session, project, "a.jpg", "etag-a", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo_a)
    write_display_variant(tmp_path, photo_a, _flat_image())
    photo_b = await _add_photo(
        db_session, project, "b.jpg", "etag-b", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo_b)
    write_display_variant(tmp_path, photo_b, _flat_image())
    photo_c = await _add_photo(
        db_session, project, "c.jpg", "etag-c", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo_c)
    write_display_variant(tmp_path, photo_c, _flat_image())

    client = PerPhotoLandmarkClient(
        [
            LandmarkApiError("Fehler fuer a"),
            LandmarkDetection(name="Eiffelturm", confidence=0.9),
            LandmarkApiError("Fehler fuer c"),
        ]
    )

    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        run = await run_criterion_scoring(
            db_session,
            project,
            scoring_run.id,
            cache_dir=tmp_path,
            build_detector=_no_face_detector,
            build_animal_detector=_no_animal_detector,
            build_classifier=_landscape_scene_classifier,
            build_aesthetics=_no_aesthetics_model,
            build_landmarker=_no_face_landmarker,
            build_landmark_client=lambda _model: client,
            use_cloud=True,
        )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == 3
    # Spec 0529: ohne Sehenswuerdigkeitsauszug meldet sich die Ortsprüfung einmal zusaetzlich
    # (fail-closed) - hier zaehlen nur die Worker-Zeilen der fehlgeschlagenen Cloud-Aufrufe.
    worker_records = [record for record in caplog.records if record.name == "photosort.worker"]
    assert len(worker_records) == 2
    messages = [record.message for record in worker_records]
    assert any(
        str(photo_a.id) in message and photo_a.relative_path in message for message in messages
    )
    assert any(
        str(photo_c.id) in message and photo_c.relative_path in message for message in messages
    )
    assert not any(str(photo_b.id) in message for message in messages)


async def test_cancelled_error_from_a_parallel_landmark_call_propagates_and_fails_the_run(
    db_session: AsyncSession, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    # Spec 0056/ADR 0034: ein CancelledError durchlaeuft die separate, dem continue-Loop
    # vorgelagerte Propagations-Schleife und erreicht die neuen logger.warning(...)-Aufrufe
    # strukturell nie - ein Lauf-Abbruch ist keine best-effort-Situation.
    with caplog.at_level(logging.WARNING, logger="photosort.worker"):
        with pytest.raises(asyncio.CancelledError):
            await run_criterion_scoring(
                db_session,
                project,
                scoring_run.id,
                cache_dir=tmp_path,
                build_detector=_no_face_detector,
                build_animal_detector=_no_animal_detector,
                build_classifier=_landscape_scene_classifier,
                build_aesthetics=_no_aesthetics_model,
                build_landmarker=_no_face_landmarker,
                build_landmark_client=lambda _model: CancellingLandmarkClient(),
                use_cloud=True,
            )

    assert len(caplog.records) == 0

    result = await db_session.execute(
        select(CriterionScoringRun).where(CriterionScoringRun.project_id == project.id)
    )
    run_row = result.scalars().first()
    assert run_row is not None
    assert run_row.status == ScanStatus.FAILED


# specs/features/0289-feste-kategorien.md, Umsetzungsschritt 5 ab hier: lokale Signale und
# Remote-Kategorien sind zwei Zulieferer EINER Kandidatenmenge - die abgeloesten
# _merge_remote_category_labels-Tests (Remote-Label als Pseudo-Kriterium, Spezifitaets-Vorrang)
# sind hier durch Vereinigungs- und Herkunftsneutralitaets-Tests ersetzt, nicht ersatzlos
# entfallen.


# --- specs/features/0217-landschaft-erkennung-spezifitaets-vorrang.md, ADR decisions/0047 ---
class CountingSceneClassifier:
    """Zaehlt classify()-Aufrufe UND liefert dabei konfigurierbare Labels - Ein-Aufruf-Nachweis
    fuer AK8 der Spec 0217 ("keine zusaetzlichen Kosten pro Foto"): aus DERSELBEN Modellausgabe
    entstehen gebaeude UND landschaft. Anders als CountingDetector (Spec 0038) ist dieser
    Aufrufzaehler der Testnachweis eines Akzeptanzkriteriums und darf nicht als redundant
    gestrichen werden (Testkonzept, Regel 2 zu ADR 0047)."""

    def __init__(self, categories: list[tuple[str, float]] | None = None) -> None:
        self.call_count = 0
        self._categories = categories if categories is not None else [("valley", 0.7)]

    def classify(self, image: object) -> object:
        self.call_count += 1
        return SimpleNamespace(
            classifications=[
                SimpleNamespace(
                    categories=[
                        SimpleNamespace(category_name=name, score=score)
                        for name, score in self._categories
                    ]
                )
            ]
        )


async def test_classify_scene_is_called_exactly_once_per_photo_for_both_criteria(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # AK8 (Pflichttest, Spy): GENAU EIN classify()-Aufruf pro Foto, aus dem BEIDE Kriterien
    # entstehen - das Kostenkriterium der Story.
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "alps.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())
    classifier = CountingSceneClassifier([("valley", 0.7), ("church", 0.9)])

    await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=lambda: classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    assert classifier.call_count == 1
    criteria = await _criteria_of(db_session, photo)
    assert criteria["landschaft"] == pytest.approx(0.7)
    assert criteria["gebaeude"] == pytest.approx(0.9)


def test_landschaft_is_part_of_the_image_analysis_criterion_keys() -> None:
    assert "landschaft" in worker_local.IMAGE_ANALYSIS_CRITERION_KEYS
    assert worker_local.IMAGE_ANALYSIS_CRITERION_SOURCES["landschaft"] == CriterionSource.LOCAL_ML


async def test_a_failing_landschaft_score_leaves_gebaeude_untouched(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Best-effort in BEIDE Richtungen (Testkonzept, Regel 3 zu ADR 0047): scheitert die
    # Score-Berechnung des einen Kriteriums, muss das andere aus derselben Modellausgabe trotzdem
    # geschrieben werden - die try/except-Granularitaet ist damit testbestimmt.
    def _boom(labels: object) -> float:
        raise RuntimeError("Landschafts-Score kaputt")

    monkeypatch.setattr(worker_local, "compute_landschaft_score", _boom)

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "church.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_scene_classifier_stub,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = await _criteria_of(db_session, photo)
    assert "landschaft" not in criteria
    assert criteria["gebaeude"] == pytest.approx(0.8)


async def test_a_failing_gebaeude_score_leaves_landschaft_untouched(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(labels: object) -> float:
        raise RuntimeError("Gebaeude-Score kaputt")

    monkeypatch.setattr(worker_local, "compute_gebaeude_score", _boom)

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "valley.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = await _criteria_of(db_session, photo)
    assert "gebaeude" not in criteria
    assert criteria["landschaft"] == pytest.approx(0.8)


async def test_a_failing_scene_classification_leaves_both_criteria_unwritten(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    class BrokenSceneClassifier:
        def classify(self, image: object) -> object:
            raise RuntimeError("Modell-Ladefehler")

    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "a.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=BrokenSceneClassifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    criteria = await _criteria_of(db_session, photo)
    assert "gebaeude" not in criteria
    assert "landschaft" not in criteria
    # Ein Kriterium ohne Abhaengigkeit zur Szenen-Klassifikation bleibt unberuehrt.
    assert "content_landscape" in criteria


async def test_a_flat_photo_without_a_landscape_label_scores_no_landschaft(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """AK1/AK5 von Spec 0217, seit Spec 0427 ohne Kategoriebegriff: ein hoher
    `content_landscape`-Wert (Flaechigkeit) macht aus einem Foto keine Landschaft - `landschaft`
    bleibt genau 0.0.

    Die beiden Assertions gehoeren zusammen in EINEN Fall: getrennt bestuende jede auch dann,
    wenn die Flaechigkeit stillschweigend zur Landschafts-Erkennung geworden waere."""
    project = await _make_project(db_session)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "wall.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=_failing_landmark_client_builder,
        use_cloud=True,
    )

    # Das Foto bekommt trotzdem GENAU EINE Rangzeile - "nichts erkannt" ist kein Grund, aus der
    # Rangfolge zu fallen.
    (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalar_one()
    criteria = await _criteria_of(db_session, photo)
    assert criteria["content_landscape"] > 0.5
    assert criteria["landschaft"] == 0.0


async def test_a_flat_photo_without_a_landscape_label_triggers_no_cloud_call_anymore(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    # Kostensenkung als eigener Testfall (Testkonzept, Regel 2 zu ADR 0047): ein Foto, das NUR die
    # weggefallene content_landscape-Bedingung erfuellte, verlaesst den Homeserver nicht mehr.
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    project.cloud_vision_consent_at = datetime.now(UTC)
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "wall.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())
    client = RecordingLandmarkClient()

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_no_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert client.calls == []


async def test_a_recognised_landscape_photo_is_still_sent_to_the_landmark_client(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session)
    project.cloud_vision_detection_enabled = True
    project.cloud_vision_consent_at = datetime.now(UTC)
    await db_session.commit()
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_photo(
        db_session, project, "valley.jpg", "etag-1", datetime(2023, 1, 1, tzinfo=UTC)
    )
    await _add_score(db_session, photo)
    write_display_variant(tmp_path, photo, _flat_image())
    client = RecordingLandmarkClient()

    run = await run_criterion_scoring(
        db_session,
        project,
        scoring_run.id,
        cache_dir=tmp_path,
        build_detector=_no_face_detector,
        build_animal_detector=_no_animal_detector,
        build_classifier=_landscape_scene_classifier,
        build_aesthetics=_no_aesthetics_model,
        build_landmarker=_no_face_landmarker,
        build_landmark_client=lambda _model: client,
        use_cloud=True,
    )

    assert run.status == ScanStatus.SUCCESS
    assert len(client.calls) == 1
