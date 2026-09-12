from __future__ import annotations

import asyncio
import hashlib
import inspect
import math
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import photosort.worker as worker
from photosort.cloud_vision import VISION_MODELS_BY_PROVIDER
from photosort.label_embedding import LabelEmbedderLike
from photosort.landmark import LandmarkApiError, LandmarkDetection
from photosort.models import (
    ClassificationPhase,
    CriterionScoringRun,
    CriterionSource,
    Photo,
    PhotoCategoryClassification,
    PhotoCriterionScore,
    PhotoRanking,
    PhotoScore,
    Project,
    RemoteCategoryClassificationRun,
    ScanStatus,
    ScoringRun,
)
from photosort.remote_classification import RemoteClassification
from photosort.thumbnails import display_path
from photosort.worker import run_classification

# specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, decisions/0050-verketteter-
# klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md: EIN verketteter Lauf statt zweier
# getrennt ausgeloester Laeufe, mit laufbezogener Cloud-Freigabe.
#
# Die Tests der beiden EINZELNEN Phasen leben unveraendert in test_worker_criterion_scoring.py und
# test_worker_remote_category_classification.py - hier geht es ausschliesslich um das Zusammen-
# spiel: Reihenfolge, Cloud-Gate, Fehlerweitergabe, Phasen-/Lauf-Zustand.


# --------------------------------------------------------------------------------------------
# Fixtures / Test-Doubles
# --------------------------------------------------------------------------------------------


async def _make_project(
    session: AsyncSession, *, name: str = "Costa Rica", cloud_consent: bool = False
) -> Project:
    project = Project(
        name=name,
        opencloud_drive_id=f"drive-{name}",
        opencloud_path=name,
        cloud_vision_detection_enabled=cloud_consent,
    )
    if cloud_consent:
        project.cloud_vision_consent_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _add_successful_scoring_run(session: AsyncSession, project: Project) -> ScoringRun:
    run = ScoringRun(project_id=project.id, status=ScanStatus.SUCCESS)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def _add_candidate_photo(
    session: AsyncSession, project: Project, path: str, cache_dir: Path
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
            cluster_key="cluster-0",
            suggested_status=None,
            computed_at=now,
        )
    )
    await session.commit()

    variant = display_path(cache_dir, photo.id, photo.etag)
    variant.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (160, 160), color=(100, 100, 100)).save(variant, format="JPEG")
    return photo


class _NoDetections:
    """Deckt FaceDetector/ObjectDetector/FaceLandmarker ab - keiner der drei findet je etwas, die
    echten Builder duerfen in Tests NIE laufen (specs/features/0038/0048)."""

    def detect(self, image: object) -> object:
        return SimpleNamespace(detections=[], face_landmarks=[], facial_transformation_matrixes=[])


class _NoSceneLabels:
    def classify(self, image: object) -> object:
        return SimpleNamespace(classifications=[SimpleNamespace(categories=[])])


class _LandscapeSceneLabels:
    """Liefert eine Landschafts-Szene, damit `landschaft` die category_presence_threshold erreicht
    und das Foto damit ueberhaupt Landmark-Kandidat wird (criteria.py::is_landmark_candidate) -
    ohne das laeuft die Landmark-Phase mangels Kandidaten leer, unabhaengig vom Cloud-Gate."""

    def classify(self, image: object) -> object:
        return SimpleNamespace(
            classifications=[
                SimpleNamespace(categories=[SimpleNamespace(category_name="valley", score=0.7)])
            ]
        )


class _NeutralAesthetics:
    def predict(self, batch: object) -> object:
        return np.array([[0.1] * 10], dtype="float32")


class _FakeLabelEmbedder:
    """Deterministisch, aber nicht konstant (analog test_worker_remote_category_classification.py):
    unterschiedliche Texte erhalten deutlich unterschiedliche Vektoren."""

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        angle = (int.from_bytes(digest[:4], "big") / 2**32) * 2 * math.pi
        return [math.cos(angle), math.sin(angle)]


def _fake_embedder() -> LabelEmbedderLike:
    return _FakeLabelEmbedder()


class RecordingCategoryClient:
    def __init__(self, classification: RemoteClassification | None = None) -> None:
        self._classification = classification or RemoteClassification(
            categories=("tier",), fine_labels=("Hund",)
        )
        self.calls: list[int] = []

    async def classify(
        self, image_bytes: bytes, mime_type: str, photo_id: int
    ) -> RemoteClassification:
        self.calls.append(photo_id)
        return self._classification


class RecordingLandmarkClient:
    def __init__(self, raise_error: bool = False) -> None:
        self.calls = 0
        self._raise_error = raise_error

    async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
        self.calls += 1
        if self._raise_error:
            raise LandmarkApiError("simulierter Cloud-Fehler")
        return LandmarkDetection(name="Kölner Dom", confidence=0.9)


class ExplodingClient:
    """Ein Client, dessen blosse KONSTRUKTION den Test zum Scheitern bringt - so wird "es wurde
    gar nicht erst versucht" zu einer beweisbaren Aussage statt zu einer Zaehlerbeobachtung."""

    def __init__(self, label: str) -> None:
        raise AssertionError(
            f"{label} wurde konstruiert, obwohl kein einziger Cloud-Aufruf stattfinden darf"
        )


def _exploding_category_client_builder(model: str) -> NoReturn:
    ExplodingClient("Der Remote-Kategorie-Client")
    raise AssertionError("unreachable")


def _exploding_landmark_client_builder(model: str) -> NoReturn:
    ExplodingClient("Der Landmark-Client")
    raise AssertionError("unreachable")


def _failing_landmark_client_builder(model: str) -> NoReturn:
    raise RuntimeError("simulierter Modell-Ladefehler")


async def _run(
    session: AsyncSession,
    project: Project,
    scoring_run: ScoringRun,
    cache_dir: Path,
    *,
    use_cloud: bool,
    build_category_client: object = None,
    build_landmark_client: object = None,
    build_classifier: object = _NoSceneLabels,
) -> CriterionScoringRun:
    """Ruft run_classification mit durchgaengig gefakten lokalen Modellen auf - die echten
    build_*-Funktionen duerfen in keinem automatisierten Test laufen."""
    kwargs = {}
    if build_category_client is not None:
        kwargs["build_category_client"] = build_category_client
    if build_landmark_client is not None:
        kwargs["build_landmark_client"] = build_landmark_client
    return await run_classification(
        session,
        project,
        scoring_run.id,
        cache_dir,
        use_cloud=use_cloud,
        build_detector=_NoDetections,
        build_animal_detector=_NoDetections,
        build_classifier=build_classifier,  # type: ignore[arg-type]
        build_aesthetics=_NeutralAesthetics,
        build_landmarker=_NoDetections,
        build_embedder=_fake_embedder,
        **kwargs,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------------------------
# Verkettung: eine Ausloesung, beide Phasen, Remote-Ergebnis wirkt im SELBEN Lauf
# --------------------------------------------------------------------------------------------


async def test_remote_results_reach_the_category_of_the_same_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """DAS Kern-Akzeptanzkriterium (Spec 0296, "Ein Ausloeser"): die Cloud-Anteile laufen so
    frueh, dass ihre Ergebnisse noch im selben Durchlauf in die Kategorie-Vorschlaege einfliessen -
    ein zweiter, manuell angestossener Lauf ist dafuer nicht mehr noetig.

    Geprueft wird das am ERGEBNIS (die PhotoRanking-Zeile dieses Laufs traegt die remote ermittelte
    Kategorie), nicht an einer Aufrufreihenfolge: die lokalen Signale erkennen hier nichts
    ("nicht_erkannt" waere das Ergebnis ohne die Remote-Phase)."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(),
    )

    assert run.status == ScanStatus.SUCCESS
    ranking = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalar_one()
    assert ranking.photo_id == photo.id
    assert ranking.category_key == "tier"


async def test_a_single_trigger_produces_both_run_records(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(),
    )

    remote_runs = (
        (await db_session.execute(select(RemoteCategoryClassificationRun))).scalars().all()
    )
    criterion_runs = (await db_session.execute(select(CriterionScoringRun))).scalars().all()
    assert len(remote_runs) == 1
    assert len(criterion_runs) == 1
    assert remote_runs[0].status == ScanStatus.SUCCESS


async def test_the_run_record_reports_phase_and_cloud_request(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """AC "Waehrend des Durchlaufs ist erkennbar, welcher Teilschritt gerade laeuft": `phase`
    traegt den Teilschritt und ist nach dem Lauf wieder NULL (= laeuft nicht mehr)."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)
    observed_phases: list[ClassificationPhase | None] = []

    class PhaseObservingClient(RecordingCategoryClient):
        async def classify(
            self, image_bytes: bytes, mime_type: str, photo_id: int
        ) -> RemoteClassification:
            run = (await db_session.execute(select(CriterionScoringRun))).scalar_one()
            observed_phases.append(run.phase)
            return await super().classify(image_bytes, mime_type, photo_id)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: PhaseObservingClient(),
    )

    assert observed_phases == [ClassificationPhase.REMOTE_CATEGORIES]
    assert run.phase is None
    assert run.cloud_requested is True
    assert run.cloud_error_message is None


async def test_a_local_run_records_that_no_cloud_was_requested(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """AC "Nach einem solchen Durchlauf ist erkennbar, dass das Ergebnis ohne Cloud-Anreicherung
    entstanden ist" - `cloud_requested=False` ist genau dieses Signal fuer die Oberflaeche."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    run = await run_classification(
        db_session,
        project,
        scoring_run.id,
        tmp_path,
        use_cloud=False,
        build_detector=_NoDetections,
        build_animal_detector=_NoDetections,
        build_classifier=_NoSceneLabels,
        build_aesthetics=_NeutralAesthetics,
        build_landmarker=_NoDetections,
        build_category_client=_exploding_category_client_builder,
        build_landmark_client=_exploding_landmark_client_builder,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.cloud_requested is False
    assert run.phase is None


# --------------------------------------------------------------------------------------------
# Cloud-Gate (Sicherheits-Muss-Kriterien der Spec)
# --------------------------------------------------------------------------------------------


async def test_no_cloud_call_at_all_when_the_checkbox_is_unchecked(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """SICHERHEITS-MUSS-KRITERIUM (Spec 0296): "Ist die Checkbox abgewaehlt, findet im gesamten
    Durchlauf kein einziger Cloud-Aufruf statt - auch nicht die Sehenswuerdigkeits-Erkennung".
    Beide Client-Builder wuerden hier beim blossen Konstruieren den Test zum Scheitern bringen -
    das Projekt hat ausdruecklich Consent, nur die laufbezogene Freigabe fehlt."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)
    # Ueber der landschaft-Schwelle -> waere ohne das Gate ein Landmark-Kandidat.
    db_session.add(
        PhotoCriterionScore(
            photo_id=photo.id,
            criterion_key="landschaft",
            value=1.0,
            source=CriterionSource.LOCAL_ML,
            computed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
    )
    await db_session.commit()

    run = await run_classification(
        db_session,
        project,
        scoring_run.id,
        tmp_path,
        use_cloud=False,
        build_detector=_NoDetections,
        build_animal_detector=_NoDetections,
        build_classifier=_NoSceneLabels,
        build_aesthetics=_NeutralAesthetics,
        build_landmarker=_NoDetections,
        build_category_client=_exploding_category_client_builder,
        build_landmark_client=_exploding_landmark_client_builder,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    # Keine Remote-Phase -> gar kein RemoteCategoryClassificationRun.
    assert (await db_session.execute(select(RemoteCategoryClassificationRun))).scalars().all() == []
    assert (
        await db_session.execute(
            select(PhotoCriterionScore).where(PhotoCriterionScore.criterion_key == "landmark")
        )
    ).scalars().all() == []


async def test_no_cloud_call_when_the_project_consent_is_missing(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """SICHERHEITS-MUSS-KRITERIUM (Spec 0296, Bedrohung 1): das Gate ist eine KONJUNKTION - die
    laufbezogene Checkbox kann eine fehlende projektweite Einwilligung nie ersetzen."""
    project = await _make_project(db_session, cloud_consent=False)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    run = await run_classification(
        db_session,
        project,
        scoring_run.id,
        tmp_path,
        use_cloud=True,
        build_detector=_NoDetections,
        build_animal_detector=_NoDetections,
        build_classifier=_NoSceneLabels,
        build_aesthetics=_NeutralAesthetics,
        build_landmarker=_NoDetections,
        build_category_client=_exploding_category_client_builder,
        build_landmark_client=_exploding_landmark_client_builder,
        build_embedder=_fake_embedder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert (await db_session.execute(select(RemoteCategoryClassificationRun))).scalars().all() == []
    # `cloud_requested` spiegelt die ANFRAGE, nicht das Ergebnis der Gate-Auswertung - die
    # Oberflaeche kommt an den Grund ueber cloud_vision_detection_enabled.
    assert run.cloud_requested is True


async def test_the_landmark_phase_runs_when_the_checkbox_is_checked(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Gegenprobe zum Gate-Test: bei angewaehlter Checkbox UND vorhandener Einwilligung laeuft die
    Sehenswuerdigkeits-Erkennung wie bisher mit."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)
    landmark_client = RecordingLandmarkClient()

    await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(
            RemoteClassification(categories=("landschaft",), fine_labels=())
        ),
        build_landmark_client=lambda _model: landmark_client,
        build_classifier=_LandscapeSceneLabels,
    )

    landmark_scores = (
        (
            await db_session.execute(
                select(PhotoCriterionScore).where(
                    PhotoCriterionScore.photo_id == photo.id,
                    PhotoCriterionScore.criterion_key == "landmark",
                )
            )
        )
        .scalars()
        .all()
    )
    assert landmark_client.calls == 1
    assert len(landmark_scores) == 1


# --------------------------------------------------------------------------------------------
# Fehlerverhalten: Cloud-Anteil scheitert, lokaler Anteil laeuft trotzdem vollstaendig durch
# --------------------------------------------------------------------------------------------


async def test_a_failing_remote_phase_does_not_stop_the_local_scoring(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """AC "Fehlerverhalten": "Scheitert ein Cloud-Anteil, wird der Fehler sichtbar gemeldet und der
    lokale Bewertungsanteil laeuft trotzdem vollstaendig durch"."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    # Ein NICHT KONSTRUIERBARER Client liesse die Remote-Phase erfolgreich, aber wirkungslos enden
    # (bestehendes Best-effort-Verhalten, ADR 0032 Punkt 5) - fuer einen echten FAILED-Zustand
    # muss die Phase selbst durchbrechen. Ein Embedder, der beim Aufloesen eines Feinlabels wirft,
    # tut genau das: der Fehler liegt ausserhalb der per-Foto-Best-effort-Absicherung.
    class ExplodingSnapshotEmbedder:
        def embed(self, text: str) -> list[float]:
            raise RuntimeError("Embedder-Laufzeitfehler")

    run = await run_classification(
        db_session,
        project,
        scoring_run.id,
        tmp_path,
        use_cloud=True,
        build_detector=_NoDetections,
        build_animal_detector=_NoDetections,
        build_classifier=_NoSceneLabels,
        build_aesthetics=_NeutralAesthetics,
        build_landmarker=_NoDetections,
        build_category_client=lambda _model: RecordingCategoryClient(),
        build_landmark_client=_failing_landmark_client_builder,
        build_embedder=lambda: ExplodingSnapshotEmbedder(),
    )

    # Der lokale Anteil ist vollstaendig: PhotoRanking-Zeile fuer das Foto vorhanden.
    ranking = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalar_one()
    assert ranking.photo_id == photo.id
    assert run.status == ScanStatus.SUCCESS
    # Der Fehler ist laufweit gemeldet (AC "wird der Fehler sichtbar gemeldet").
    assert run.cloud_error_message is not None
    assert "Remote-Kategorisierung fehlgeschlagen" in run.cloud_error_message


async def test_an_unbuildable_landmark_client_is_reported(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """ADR 0050 Punkt 4: dieser Fall war bisher vollstaendig stumm - eine nicht konstruierbare
    Sehenswuerdigkeits-Erkennung liess den Lauf wortlos ohne sie durchlaufen."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(),
        build_landmark_client=_failing_landmark_client_builder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.cloud_error_message is not None
    assert "Sehenswuerdigkeits-Erkennung nicht verfuegbar" in run.cloud_error_message


async def test_failing_landmark_calls_are_summarised_not_listed(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """ADR 0050 Punkt 4: Zaehl-Zusammenfassung auf Laufebene statt N Einzelmeldungen - die
    Einzelfehler bleiben pro Foto ueber photo_cloud_vision_errors abrufbar."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(
            RemoteClassification(categories=("landschaft",), fine_labels=())
        ),
        build_landmark_client=lambda _model: RecordingLandmarkClient(raise_error=True),
        build_classifier=_LandscapeSceneLabels,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.cloud_error_message == "Sehenswuerdigkeits-Erkennung: 1 von 1 Fotos fehlgeschlagen."
    # Der lokale Anteil bleibt vollstaendig.
    ranking = (
        await db_session.execute(
            select(PhotoRanking).where(PhotoRanking.criterion_scoring_run_id == run.id)
        )
    ).scalar_one()
    assert ranking.photo_id == photo.id


async def test_a_clean_cloud_run_reports_no_cloud_error(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(),
        build_landmark_client=lambda _model: RecordingLandmarkClient(),
    )

    assert run.cloud_error_message is None


async def test_remote_classification_rows_are_written_before_the_criteria_phase(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Regressionsschutz fuer die Reihenfolge selbst: waere die Kriterien-Phase zuerst gelaufen,
    gaebe es zum Zeitpunkt von _remote_category_candidates noch keine Klassifikations-Zeile."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    photo = await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(),
    )

    classification = (
        await db_session.execute(
            select(PhotoCategoryClassification).where(
                PhotoCategoryClassification.photo_id == photo.id
            )
        )
    ).scalar_one()
    assert classification.category_key == "tier"


async def test_a_cancelled_remote_phase_fails_the_whole_run_immediately(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Schicht 1 des Fortschritts-Watchdogs (ADR 0019) fuer den mit der Verkettung neu entstandenen
    Fall: bricht der Job waehrend Phase 1 ab (Job-Timeout/Worker-Shutdown), darf der bereits
    angelegte uebergeordnete Lauf nicht bis zum naechsten Cron-Tick auf RUNNING stehen bleiben."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    class CancellingCategoryClient:
        async def classify(
            self, image_bytes: bytes, mime_type: str, photo_id: int
        ) -> RemoteClassification:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _run(
            db_session,
            project,
            scoring_run,
            tmp_path,
            use_cloud=True,
            build_category_client=lambda _model: CancellingCategoryClient(),
        )

    run = (await db_session.execute(select(CriterionScoringRun))).scalar_one()
    assert run.status == ScanStatus.FAILED
    assert run.phase is None
    assert run.error_message == "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown)."


# specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, Akzeptanzkriterium "Die Einstellung
# wirkt auf beide Cloud-Anteile einheitlich; es entstehen nicht zwei unterschiedliche Modelle
# nebeneinander" (Review-Fund `review-tests`: die Einzelphasen-Tests belegen je Phase das richtige
# Modell, aber nicht, dass BEIDE Phasen desselben Laufs dasselbe bekommen - genau die Aussage des
# Kriteriums).


async def test_both_cloud_phases_of_one_run_get_the_same_configured_model(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stronger = VISION_MODELS_BY_PROVIDER["anthropic"][1]
    monkeypatch.setattr(worker.settings, "landmark_model", stronger)
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)
    seen: dict[str, str] = {}

    def build_category(model: str) -> object:
        seen["category"] = model
        return RecordingCategoryClient()

    def build_landmark(model: str) -> object:
        seen["landmark"] = model
        return RecordingLandmarkClient()

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=build_category,
        build_landmark_client=build_landmark,
    )

    assert run.status == ScanStatus.SUCCESS
    assert seen == {"category": stronger, "landmark": stronger}


async def test_a_purely_local_run_resolves_no_model_at_all(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Gegenprobe zum Security-Muss-Kriterium "kein einziger Cloud-Aufruf im gesamten Durchlauf":
    ohne Cloud-Nutzung wird keine der beiden Factories aufgerufen, also auch kein Modell an einen
    Anbieter gereicht - und die Modellspalte des Laufs bleibt NULL."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=False,
        build_category_client=_exploding_category_client_builder,
        build_landmark_client=_exploding_landmark_client_builder,
    )

    assert run.status == ScanStatus.SUCCESS
    assert run.landmark_model is None


# --------------------------------------------------------------------------------------------
# specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-vier-
# teilschritte-und-laufeigene-cloud-bilanz.md Punkt 1: die VIER benannten Teilschritte.
#
# Beobachtet wird die tatsaechlich durchlaufene FOLGE als Liste - vier Einzelasserts ("irgendwann
# stand `phase` auf landmark") belegten die Monotonie nicht, und genau sie ist die Aussage: ein
# Zuruecksetzen auf `criteria` nach der Landmark-Phase liesse die Anzeige rueckwaerts laufen.
# --------------------------------------------------------------------------------------------


class _PhaseRecorder:
    """Sammelt Phasenwerte und faltet unmittelbare Wiederholungen zusammen - beobachtet wird pro
    Foto/pro Aufruf, die Aussage ist aber die Abfolge, nicht die Aufrufzahl."""

    def __init__(self) -> None:
        self.sequence: list[str | None] = []

    def record(self, phase: ClassificationPhase | None) -> None:
        value = phase.value if phase is not None else None
        if not self.sequence or self.sequence[-1] != value:
            self.sequence.append(value)


async def _current_phase(session: AsyncSession) -> ClassificationPhase | None:
    run = (await session.execute(select(CriterionScoringRun))).scalar_one()
    return run.phase


def _phase_observing_scene_classifier(session: AsyncSession, recorder: _PhaseRecorder) -> object:
    """Beobachtungspunkt der KRITERIEN-Phase: der Szenen-Klassifikator laeuft je Foto innerhalb
    der lokalen Foto-Schleife. Ohne ihn haette diese Phase gar keinen Beobachtungspunkt - sie
    ruft keinen Client auf."""

    class _Observing(_LandscapeSceneLabels):
        def classify(self, image: object) -> object:
            # `_compute_content_criteria` laeuft synchron; der Phasenwert steht am selben
            # In-Memory-Objekt, das die Schleife fortschreibt - kein DB-Roundtrip noetig.
            run = next(
                obj for obj in session.identity_map.values() if isinstance(obj, CriterionScoringRun)
            )
            recorder.record(run.phase)
            return super().classify(image)

    return _Observing()


async def test_the_phase_sequence_of_a_cloud_run_is_monotone(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)
    recorder = _PhaseRecorder()

    class _PhaseObservingCategoryClient(RecordingCategoryClient):
        async def classify(
            self, image_bytes: bytes, mime_type: str, photo_id: int
        ) -> RemoteClassification:
            recorder.record(await _current_phase(db_session))
            return await super().classify(image_bytes, mime_type, photo_id)

    class _PhaseObservingLandmarkClient(RecordingLandmarkClient):
        async def detect(self, image_bytes: bytes, mime_type: str) -> LandmarkDetection:
            recorder.record(await _current_phase(db_session))
            return await super().detect(image_bytes, mime_type)

    real_rank_photos = worker.rank_photos

    def _observing_rank_photos(*args: object, **kwargs: object) -> object:
        # Der Ranking-Teilschritt hat keinen Client - der Spy auf rank_photos ist sein einziger
        # Beobachtungspunkt WAEHREND der Ausfuehrung.
        run = next(
            obj for obj in db_session.identity_map.values() if isinstance(obj, CriterionScoringRun)
        )
        recorder.record(run.phase)
        return real_rank_photos(*args, **kwargs)

    monkeypatch.setattr(worker, "rank_photos", _observing_rank_photos)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: _PhaseObservingCategoryClient(
            RemoteClassification(categories=("landschaft",), fine_labels=())
        ),
        build_landmark_client=lambda _model: _PhaseObservingLandmarkClient(),
        build_classifier=lambda: _phase_observing_scene_classifier(db_session, recorder),
    )
    recorder.record(run.phase)

    assert recorder.sequence == ["remote_categories", "criteria", "landmark", "ranking", None]


async def test_a_run_without_cloud_keeps_the_order_and_skips_both_cloud_phases(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)
    recorder = _PhaseRecorder()

    real_rank_photos = worker.rank_photos

    def _observing_rank_photos(*args: object, **kwargs: object) -> object:
        run = next(
            obj for obj in db_session.identity_map.values() if isinstance(obj, CriterionScoringRun)
        )
        recorder.record(run.phase)
        return real_rank_photos(*args, **kwargs)

    monkeypatch.setattr(worker, "rank_photos", _observing_rank_photos)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=False,
        build_category_client=_exploding_category_client_builder,
        build_landmark_client=_exploding_landmark_client_builder,
        build_classifier=lambda: _phase_observing_scene_classifier(db_session, recorder),
    )
    recorder.record(run.phase)

    assert recorder.sequence == ["criteria", "ranking", None]


async def test_the_ranking_step_no_longer_reports_the_landmark_phase(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DER Regressionstest fuer die Existenz des vierten Werts (ADR 0068 Punkt 1): ohne `ranking`
    bliebe `phase` waehrend der Kategorieableitung/rank_photos auf `landmark` stehen - die Anzeige
    behauptete dann Cloud-Aufrufe, die nicht mehr stattfinden, bei 100 % Fortschritt."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)
    observed: list[ClassificationPhase | None] = []

    real_rank_photos = worker.rank_photos

    def _observing_rank_photos(*args: object, **kwargs: object) -> object:
        run = next(
            obj for obj in db_session.identity_map.values() if isinstance(obj, CriterionScoringRun)
        )
        observed.append(run.phase)
        return real_rank_photos(*args, **kwargs)

    monkeypatch.setattr(worker, "rank_photos", _observing_rank_photos)

    await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(
            RemoteClassification(categories=("landschaft",), fine_labels=())
        ),
        build_landmark_client=lambda _model: RecordingLandmarkClient(),
        build_classifier=_LandscapeSceneLabels,
    )

    assert observed, "rank_photos wurde gar nicht aufgerufen - der Test prueft dann nichts."
    assert all(phase is ClassificationPhase.RANKING for phase in observed), observed


async def test_a_failed_run_leaves_no_phase_behind(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_fail_run` nullt `phase` - haelt fest, dass auch der neue Ranking-Zweig darueber laeuft und
    ein gescheiterter Lauf nicht dauerhaft als "laeuft gerade" dasteht."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    def _explode(*args: object, **kwargs: object) -> NoReturn:
        raise RuntimeError("simulierter Fehlschlag im Ranking-Teilschritt")

    monkeypatch.setattr(worker, "rank_photos", _explode)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(),
        build_landmark_client=lambda _model: RecordingLandmarkClient(),
    )

    assert run.status == ScanStatus.FAILED
    assert run.phase is None


# --------------------------------------------------------------------------------------------
# specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-vier-
# teilschritte-und-laufeigene-cloud-bilanz.md Punkt 3: Fremdschluessel statt Sortier-Heuristik.
#
# "Die juengste Remote-Zeile des Projekts" schriebe einem Lauf OHNE Cloud-Phase den Geldbetrag
# des Laufs davor zu. Bei einer Anzeige, die einen Betrag einem Durchlauf zuschreibt, ist das
# falsch - nicht nur ungenau.
# --------------------------------------------------------------------------------------------


async def test_a_cloud_run_links_its_own_remote_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(),
    )

    remote_run = (await db_session.execute(select(RemoteCategoryClassificationRun))).scalars().one()
    assert run.remote_category_classification_run_id == remote_run.id


async def test_the_link_exists_before_the_first_remote_call(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Der Fremdschluessel wird VOR dem Start von Phase 1 gesetzt und committet - die Oberflaeche
    braucht den Anker bereits waehrend der Remote-Phase, sonst zeigte sie den gerade laufenden
    Cloud-Teilschritt genau dann nicht, wenn er Geld ausgibt."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)
    observed: list[int | None] = []

    class _LinkObservingClient(RecordingCategoryClient):
        async def classify(
            self, image_bytes: bytes, mime_type: str, photo_id: int
        ) -> RemoteClassification:
            run = (await db_session.execute(select(CriterionScoringRun))).scalar_one()
            observed.append(run.remote_category_classification_run_id)
            return await super().classify(image_bytes, mime_type, photo_id)

    await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: _LinkObservingClient(),
    )

    remote_run = (await db_session.execute(select(RemoteCategoryClassificationRun))).scalars().one()
    assert observed == [remote_run.id]


async def test_a_run_without_a_cloud_phase_links_no_remote_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """DIE zweite Haelfte ist der eigentliche Testfall: im selben Projekt liegt eine AELTERE,
    FREMDE Remote-Zeile. Ohne sie bestuende der Test auch bei leerer Datenbank - und genau dieser
    Fall ist der Grund fuer die Umkehr von ADR 0050 Punkt 3: die Heuristik "juengste Remote-Zeile
    des Projekts" haette diesem Lauf die Zahlen des Laufs davor zugeschrieben."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)
    foreign_remote_run = RemoteCategoryClassificationRun(
        project_id=project.id,
        status=ScanStatus.SUCCESS,
        api_calls=42,
        cost_usd=1.23,
    )
    db_session.add(foreign_remote_run)
    await db_session.commit()

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=False,
        build_category_client=_exploding_category_client_builder,
        build_landmark_client=_exploding_landmark_client_builder,
    )

    assert run.remote_category_classification_run_id is None


async def test_two_consecutive_runs_each_carry_their_own_remote_run(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    first = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(),
    )
    await _add_candidate_photo(db_session, project, "b.jpg", tmp_path)
    second = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=True,
        build_category_client=lambda _model: RecordingCategoryClient(),
    )

    assert first.id != second.id
    assert first.remote_category_classification_run_id is not None
    assert second.remote_category_classification_run_id is not None
    assert (
        first.remote_category_classification_run_id != second.remote_category_classification_run_id
    )


# --------------------------------------------------------------------------------------------
# ADR 0068 Punkt 5: die Schaetzung, mit der ein Lauf gestartet wurde, wird am Lauf eingefroren.
# --------------------------------------------------------------------------------------------


async def test_the_start_estimate_is_frozen_on_the_run_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Ohne das Einfrieren ist "die tatsaechlichen Kosten sind gegen die Schaetzung einordenbar"
    nach dem Lauf unerfuellbar: die Schaetzung rechnet ueber den noch OFFENEN Kandidatenbestand,
    den genau dieser Lauf gerade abgearbeitet hat - unmittelbar danach schaetzt derselbe Endpunkt
    nahe null."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    run = await run_classification(
        db_session,
        project,
        scoring_run.id,
        tmp_path,
        use_cloud=True,
        estimated_cost_usd=2.5,
        build_detector=_NoDetections,
        build_animal_detector=_NoDetections,
        build_classifier=_NoSceneLabels,
        build_aesthetics=_NeutralAesthetics,
        build_landmarker=_NoDetections,
        build_embedder=_fake_embedder,
        build_category_client=lambda _model: RecordingCategoryClient(),
    )

    assert run.estimated_cost_usd == pytest.approx(2.5)


async def test_a_run_without_a_passed_estimate_stores_null_not_zero(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """`NULL`, nicht `0.0` (Security-Muss der Spec): ein Lauf ohne Cloud hat keine
    Kostenschaetzung, und `0.0` waere eine Aussage, die niemand getroffen hat - dieselbe
    "null heisst unbekannt, nie kostenlos"-Linie wie bei `price_per_image_usd`."""
    project = await _make_project(db_session, cloud_consent=True)
    scoring_run = await _add_successful_scoring_run(db_session, project)
    await _add_candidate_photo(db_session, project, "a.jpg", tmp_path)

    run = await _run(
        db_session,
        project,
        scoring_run,
        tmp_path,
        use_cloud=False,
        build_category_client=_exploding_category_client_builder,
        build_landmark_client=_exploding_landmark_client_builder,
    )

    assert run.estimated_cost_usd is None


def test_the_classify_job_argument_has_a_default() -> None:
    """Ein zum Deployment-Zeitpunkt bereits eingereihter arq-Job traegt das neue Argument nicht -
    ohne Default scheiterte er an der Signaturaenderung, nach einem kostenpflichtigen Lauf, dessen
    Ergebnis niemand mehr sieht."""
    parameter = inspect.signature(worker.classify).parameters["estimated_cost_usd"]

    assert parameter.default is None
