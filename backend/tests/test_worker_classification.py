from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn

import numpy as np
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
        return SimpleNamespace(
            detections=[], face_landmarks=[], facial_transformation_matrixes=[]
        )


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
                SimpleNamespace(
                    categories=[SimpleNamespace(category_name="valley", score=0.7)]
                )
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


def _exploding_category_client_builder() -> NoReturn:
    ExplodingClient("Der Remote-Kategorie-Client")
    raise AssertionError("unreachable")


def _exploding_landmark_client_builder() -> NoReturn:
    ExplodingClient("Der Landmark-Client")
    raise AssertionError("unreachable")


def _failing_landmark_client_builder() -> NoReturn:
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
        build_category_client=lambda: RecordingCategoryClient(),
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
        build_category_client=lambda: RecordingCategoryClient(),
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
        build_category_client=lambda: PhaseObservingClient(),
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
        build_category_client=lambda: RecordingCategoryClient(
            RemoteClassification(categories=("landschaft",), fine_labels=())
        ),
        build_landmark_client=lambda: landmark_client,
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
        build_category_client=lambda: RecordingCategoryClient(),
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
        build_category_client=lambda: RecordingCategoryClient(),
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
        build_category_client=lambda: RecordingCategoryClient(
            RemoteClassification(categories=("landschaft",), fine_labels=())
        ),
        build_landmark_client=lambda: RecordingLandmarkClient(raise_error=True),
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
        build_category_client=lambda: RecordingCategoryClient(),
        build_landmark_client=lambda: RecordingLandmarkClient(),
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
        build_category_client=lambda: RecordingCategoryClient(),
    )

    classification = (
        await db_session.execute(
            select(PhotoCategoryClassification).where(
                PhotoCategoryClassification.photo_id == photo.id
            )
        )
    ).scalar_one()
    assert classification.category_key == "tier"
