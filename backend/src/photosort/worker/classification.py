"""Der eine verkettete Klassifizierungs-Job - die einzige Stelle, an der die Phasen
verkettet sind."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import photosort.worker._runs as runs
from photosort.aesthetics import AestheticsModelLike, build_aesthetics_model
from photosort.classification import (
    FaceDetectorLike,
    FaceLandmarkerLike,
    ObjectDetectorLike,
    SceneClassifierLike,
    build_face_detector,
    build_face_landmarker,
    build_object_detector,
    build_scene_classifier,
)
from photosort.config import settings
from photosort.db import async_session_factory
from photosort.eye_client import EyeClientLike, build_eye_client
from photosort.face_analysis import FaceAnalyzerLike, build_face_analyzer
from photosort.label_embedding import LabelEmbedderLike, build_label_embedder
from photosort.landmark import LandmarkClientLike, build_landmark_client
from photosort.model_choice import resolve_model_choice
from photosort.models import (
    ClassificationMode,
    ClassificationPhase,
    CriterionScoringRun,
    Project,
    RemoteCategoryClassificationRun,
    ScanStatus,
)
from photosort.remote_classification import (
    CategoryDetectionClientLike,
    build_category_classification_client,
)
from photosort.run_cancel import RunCancelled, watch_cancel_requests
from photosort.worker._criterion.eye import run_eye_phase
from photosort.worker.criterion_scoring import run_criterion_scoring, start_criterion_scoring_run
from photosort.worker.remote_categories import run_remote_category_classification


def _resolve_launch_mode(
    mode: ClassificationMode | None, use_cloud: bool | None
) -> ClassificationMode:
    """Der gewaehlte Weg (`cloud`, `eye`, `local`). Fehlt er, wird er aus dem alten `use_cloud`
    abgeleitet - ein Aufrufer, der die Signatur noch nicht kennt, verliert dadurch nichts.
    WIDERSPRECHEN sich beide, ist das ein Programmierfehler und kein stiller Vorrang:
    `use_cloud=False` mit `mode="cloud"` waere ein Lauf, der Geld ausgibt, obwohl der Aufrufer
    "kein Cloud" gesagt hat."""
    if mode is None:
        return ClassificationMode.CLOUD if use_cloud else ClassificationMode.LOCAL
    if use_cloud is not None and use_cloud != (mode is ClassificationMode.CLOUD):
        raise ValueError("mode und use_cloud widersprechen sich; der Weg wird nicht geraten.")
    return mode


async def _take_over_or_start_classification_run(
    session: AsyncSession,
    project: Project,
    scoring_run_id: int,
    *,
    run_id: int | None,
    mode: ClassificationMode,
    cloud_requested: bool,
    estimated_cost_usd: float | None,
) -> CriterionScoringRun | None:
    """Uebernimmt die von der API angelegte, wartende Zeile (`None`, wenn sie in der Warteschlange
    abgebrochen wurde) oder legt den Lauf an.

    Der Lauf-Datensatz wird VOR der ersten Phase angelegt und an run_criterion_scoring
    durchgereicht: sonst zeigte `last_criterion_scoring_run` waehrend der Remote-Phase noch auf den
    Lauf davor und die Oberflaeche haette keinen Anker fuer den laufenden Vorgang."""
    if run_id is not None:
        return await runs.take_over_queued_run(session, CriterionScoringRun, run_id)
    return await start_criterion_scoring_run(
        session,
        project,
        scoring_run_id,
        cloud_requested=cloud_requested,
        estimated_cost_usd=estimated_cost_usd,
        mode=mode,
    )


def _initial_phase(cloud_active: bool, mode: ClassificationMode) -> ClassificationPhase:
    """Die ERSTE Phase des Laufs - ueber denselben Weg wie jede spaetere gesetzt, statt als
    Konstruktor-Schluesselwort mitzulaufen. Sonst entkaeme genau sie der Bindung an `set_phase`, und
    die erste Phase JEDES Laufs - bei einem Lauf ohne Cloud die laengste - zeigte dauerhaft "wird
    noch ermittelt", schweigend."""
    if cloud_active:
        return ClassificationPhase.REMOTE_CATEGORIES
    if mode is ClassificationMode.EYE:
        # Die Eye-Phase ist der ERSTE Teilschritt dieses Laufs, nicht ein Zwischenschritt: die
        # Anzeige soll nicht "Kriterien" behaupten, waehrend der Dienst rechnet.
        return ClassificationPhase.EYE
    return ClassificationPhase.CRITERIA


async def _run_remote_category_phase(
    session: AsyncSession,
    project: Project,
    run: CriterionScoringRun,
    cache_dir: Path,
    *,
    build_category_client: Callable[[str], CategoryDetectionClientLike],
    build_embedder: Callable[[], LabelEmbedderLike],
    category_model: str | None,
    session_factory: async_sessionmaker[AsyncSession],
) -> bool:
    """Phase "remote_categories" - `True`, wenn der uebergeordnete Lauf weiterlaeuft, `False`, wenn
    er hier endet (Abbruch in der Phase).

    Die Remote-Zeile entsteht hier, und der Fremdschluessel wird VOR dem ersten Cloud-Aufruf
    committet - sonst haette die pollende Oberflaeche waehrend der gesamten Remote-Phase keinen
    Anker fuer den Teilschritt, der gerade Geld ausgibt."""
    remote_run = RemoteCategoryClassificationRun(project_id=project.id, status=ScanStatus.RUNNING)
    session.add(remote_run)
    await session.commit()
    await session.refresh(remote_run)
    run.remote_category_classification_run_id = remote_run.id
    await session.commit()

    try:
        async with watch_cancel_requests(session_factory, CriterionScoringRun, run.id):
            remote_run = await run_remote_category_classification(
                session,
                project,
                cache_dir,
                build_client=build_category_client,
                build_embedder=build_embedder,
                run=remote_run,
                parent_run=run,
                model=category_model,
            )
    except asyncio.CancelledError:
        # Schicht 1 des Fortschritts-Watchdogs: run_remote_category_classification faellt seine
        # EIGENE Zeile bereits ab und wirft weiter - ohne diesen Zweig bliebe der uebergeordnete
        # CriterionScoringRun, den run_classification vor Phase 1 anlegt, bis zum naechsten
        # Cron-Tick auf RUNNING stehen.
        await runs.fail_run(session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown).")
        raise
    if remote_run.status == ScanStatus.CANCELLED:
        # Die Remote-Phase hat den Abbruchwunsch bemerkt und ihren Teilstand committet; dieser
        # Lauf endet mit, statt in die Kriterien-Phase zu starten.
        await runs.finish_cancelled(session, run)
        return False
    if remote_run.status == ScanStatus.FAILED:
        # fail_run hat die Session zurueckgerollt und damit JEDES Objekt darin expired - anders als
        # ein commit() (die Session laeuft mit expire_on_commit=False, siehe db.py). Ohne diese
        # beiden refresh()-Aufrufe loeste der naechste Attributzugriff einen impliziten Lazy-Load
        # ausserhalb eines aktiven greenlet-Kontexts aus (MissingGreenlet): `run.cloud_error_message`
        # unmittelbar hier, `project.cloud_vision_detection_enabled`/`project.id` gleich darauf in
        # run_criterion_scoring, das auf derselben Session weiterlaeuft.
        await session.refresh(run)
        await session.refresh(project)
        runs.append_cloud_error(
            run, f"Remote-Kategorisierung fehlgeschlagen: {remote_run.error_message}"
        )
        await session.commit()
    return True


async def run_classification(
    session: AsyncSession,
    project: Project,
    scoring_run_id: int,
    cache_dir: Path,
    *,
    run_id: int | None = None,
    mode: ClassificationMode | None = None,
    use_cloud: bool | None = None,
    estimated_cost_usd: float | None = None,
    category_model: str | None = None,
    landmark_model: str | None = None,
    build_detector: Callable[[], FaceDetectorLike] = build_face_detector,
    build_animal_detector: Callable[[], ObjectDetectorLike] = build_object_detector,
    build_classifier: Callable[[], SceneClassifierLike] = build_scene_classifier,
    build_aesthetics: Callable[[], AestheticsModelLike] = build_aesthetics_model,
    build_landmarker: Callable[[], FaceLandmarkerLike] = build_face_landmarker,
    build_landmark_client: Callable[[str], LandmarkClientLike] = build_landmark_client,
    build_category_client: Callable[
        [str], CategoryDetectionClientLike
    ] = build_category_classification_client,
    build_embedder: Callable[[], LabelEmbedderLike] = build_label_embedder,
    build_face_analyzer: Callable[[], FaceAnalyzerLike] = build_face_analyzer,
    build_eye_client: Callable[[], EyeClientLike] = build_eye_client,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
) -> CriterionScoringRun | None:
    """Der EINE, verkettete Klassifizierungslauf: "remote_categories" (nur bei mode=cloud und
    aktiver Cloud-Nutzung) -> "eye" (nur bei mode=eye) -> "criteria" (immer; inklusive
    Landmark-Teilphase bei mode=cloud mit Einwilligung oder bei mode=eye MIT Einwilligung).

    `mode` ist der gewaehlte Weg (`cloud`, `eye`, `local`); Ableitung aus `use_cloud` und der
    Fehler bei widersprechender Angabe stehen in `_resolve_launch_mode`.

    Die Reihenfolge ist der eigentliche Zweck dieser Funktion: `run_criterion_scoring` liest die
    Remote-Ergebnisse ueber `_remote_category_evidence` aus der Datenbank und kann sie nur dann in
    die Kategorieableitung einrechnen, wenn sie bereits geschrieben sind.

    "Aktive Cloud-Nutzung" ist die Konjunktion `use_cloud and
    project.cloud_vision_detection_enabled`: die laufbezogene Checkbox kann eine fehlende
    projektweite Einwilligung nie ersetzen, nur eine vorhandene fuer diesen einen Lauf ungenutzt
    lassen. Ist sie falsch, wird run_remote_category_classification GAR NICHT ERST aufgerufen - es
    entsteht dann auch kein RemoteCategoryClassificationRun.

    Der Lauf-Datensatz (`CriterionScoringRun`) wird HIER angelegt, vor der ersten Phase, und an
    run_criterion_scoring durchgereicht: sonst zeigte `last_criterion_scoring_run` waehrend der
    Remote-Phase noch auf den Lauf davor und die Oberflaeche haette keinen Anker fuer den laufenden
    Vorgang.

    Ein Fehlschlag der Cloud-Phase bricht den Lauf NICHT ab: der lokale Bewertungsanteil ist der
    Kern des Laufs und laeuft vollstaendig durch, die Fehlermeldung wandert in
    `cloud_error_message`.

    Zusaetze: Der `RemoteCategoryClassificationRun` wird HIER angelegt und hineingereicht, und sein
    Fremdschluessel steht an der Lauf-Zeile, BEVOR Phase 1 startet. Damit ist die Zuordnung
    "welcher Remote-Lauf gehoert zu diesem Durchlauf" ein Schluessel statt einer Sortierung -
    noetig, weil die Bilanz einen GELDBETRAG einem bestimmten Durchlauf zuschreibt.
    `estimated_cost_usd` ist die im Ausloese-Endpunkt serverseitig berechnete Schaetzung dieses
    Laufs; sie wird hier nur DURCHGEREICHT und gespeichert, NIE neu gerechnet - die Modulgrenze
    "API zaehlt fuer die Schaetzung, Worker selektiert fuer den Lauf" bleibt bestehen, und sie ist
    ein BELEG, keine Eingabe.

    `category_model`/`landmark_model` sind die im Ausloeser aufgeloesten Modelle der beiden
    Taetigkeiten; `None` laesst die Phase die Installationsvorgabe aufloesen.

    Mit `run_id` uebernimmt der Lauf die von der API angelegte, wartende Zeile (None, wenn sie in
    der Warteschlange abgebrochen wurde). `session_factory` speist den Abbruch-Beobachter, der die
    Wartezeiten der Cloud-Drosselung unterbricht; sie ist injizierbar, damit ein Test denselben
    Datenbestand beobachtet."""
    mode = _resolve_launch_mode(mode, use_cloud)

    # Cloud-Kontakt heisst: mode=cloud ODER (mode=eye UND projektweite Einwilligung) - nur dann
    # laeuft die Sehenswuerdigkeits-Phase, und nur dann ist `cloud_requested` wahr. Der
    # Remote-Kategorie-Client wird ausschliesslich unter mode=cloud gebaut.
    cloud_active = mode is ClassificationMode.CLOUD and project.cloud_vision_detection_enabled
    cloud_requested = mode is ClassificationMode.CLOUD or (
        mode is ClassificationMode.EYE and project.cloud_vision_detection_enabled
    )

    run = await _take_over_or_start_classification_run(
        session,
        project,
        scoring_run_id,
        run_id=run_id,
        mode=mode,
        cloud_requested=cloud_requested,
        estimated_cost_usd=estimated_cost_usd,
    )
    if run is None:
        return None
    runs.set_phase(run, _initial_phase(cloud_active, mode))
    await session.commit()
    # Phasengrenzen sind Pruefpunkte: ein Abbruch zwischen zwei Phasen beginnt die naechste nicht
    # mehr. Innerhalb einer Phase pruefen deren Bloecke selbst.
    if await runs.finish_if_cancel_requested(session, run):
        return run

    if cloud_active and not await _run_remote_category_phase(
        session,
        project,
        run,
        cache_dir,
        build_category_client=build_category_client,
        build_embedder=build_embedder,
        category_model=category_model,
        session_factory=session_factory,
    ):
        return run

    if await runs.finish_if_cancel_requested(session, run):
        return run

    # Phase "eye": sie liegt VOR der Kriterien-Phase, damit Rangfolge, Events und
    # Auswahlvorschlag desselben Laufs den WIRKSAMEN Vektor lesen. Ein Fehlschlag beendet den Lauf
    # hier: es gibt keinen Rueckfall auf Cloud oder "nur lokal", und geschrieben ist nichts (die
    # Phase committet ihre Ergebnisse erst am Ende).
    if mode is ClassificationMode.EYE:
        try:
            await run_eye_phase(session, run, project, cache_dir, build_client=build_eye_client)
        except RunCancelled:
            await runs.finish_cancelled(session, run)
            return run
        except asyncio.CancelledError:
            await runs.fail_run(
                session, run, "Lauf abgebrochen (Job-Timeout oder Worker-Shutdown)."
            )
            raise
        except Exception:
            await runs.fail_run(
                session,
                run,
                "Eye-Auswertung fehlgeschlagen; es wurde nichts uebernommen.",
            )
            return run

    if await runs.finish_if_cancel_requested(session, run):
        return run
    async with watch_cancel_requests(session_factory, CriterionScoringRun, run.id):
        return await run_criterion_scoring(
            session,
            project,
            scoring_run_id,
            cache_dir,
            build_detector,
            build_animal_detector,
            build_classifier,
            build_aesthetics,
            build_landmarker,
            build_landmark_client,
            build_embedder=build_embedder,
            run=run,
            # Die Landmark-Phase haengt an der Cloud-FREIGABE, nicht am Weg: bei mode=eye MIT
            # Einwilligung laeuft sie (dann kostet der Lauf genau die Sehenswuerdigkeits-Erkennung),
            # ohne Einwilligung nie.
            use_cloud=cloud_requested,
            landmark_model=landmark_model,
            build_face_analyzer=build_face_analyzer,
        )


async def classify(
    ctx: dict[str, Any],
    project_id: int,
    scoring_run_id: int,
    use_cloud: bool | None,
    estimated_cost_usd: float | None = None,
    *,
    run_id: int | None = None,
    mode: str | None = None,
    category_model: str | None = None,
    landmark_model: str | None = None,
) -> int | None:
    """Der einzige Klassifizierungs-Job.

    `estimated_cost_usd` ist die im Ausloese-Endpunkt berechnete Schaetzung. Der Default `None` ist
    verbindlich - ein bereits eingereihter Job traegt das Argument nicht und darf nicht an der
    Signaturaenderung scheitern.

    `use_cloud` bleibt der VIERTE POSITIONSPARAMETER vom Typ `bool | None`, `mode` ist
    keyword-only. Fehlt `mode`, wird er aus `use_cloud` abgeleitet (`True` -> cloud, sonst local).
    Ein ALTER Worker kennt die Parameter nicht und verwirft den Job sichtbar mit `TypeError` - er
    liest `"eye"` also nie als Cloud-Freigabe.

    `category_model`/`landmark_model` sind die im Ausloeser aufgeloesten Modelle. Fehlt eines,
    loest der Job selbst ueber `resolve_model_choice` auf - derselbe Weg wie im Ausloeser, kein
    Rueckfall auf einen geratenen Wert. Ein nicht mehr waehlbares Modell wirft dort
    `UnknownModelChoiceError` und laesst den Lauf sichtbar scheitern.

    `run_id` ist die von der API angelegte, wartende Zeile; ohne sie legt der Lauf sie selbst an.
    Ist die Zeile in der Warteschlange abgebrochen worden, endet der Job ohne jede Arbeit."""
    async with async_session_factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        effective_mode = (
            ClassificationMode(mode)
            if mode is not None
            else ClassificationMode.CLOUD
            if use_cloud
            else ClassificationMode.LOCAL
        )
        # Aufgeloest wird nur, was WIRKLICH fehlt: bei `eye` ist `category_model is None` der
        # Regelfall, und ein Eye-Job, der beide Modelle mitbringt, darf nicht an einem inzwischen
        # aus der Registry gefallenen Landmark-Modell des Projekts scheitern.
        needs_category_model = (
            effective_mode is not ClassificationMode.EYE and category_model is None
        )
        needs_landmark_model = landmark_model is None
        if needs_category_model or needs_landmark_model:
            resolved = resolve_model_choice(project)
            if needs_category_model:
                category_model = resolved.category_model
            if needs_landmark_model:
                landmark_model = resolved.landmark_model

        run = await run_classification(
            session,
            project,
            scoring_run_id,
            cache_dir=Path(settings.photo_cache_dir),
            run_id=run_id,
            # `mode` ist die genauere Aussage: liegt er vor, wird `use_cloud` NICHT mitgegeben -
            # sonst meldete der Widerspruchs-Check einen Konflikt, den nur die Ableitung erzeugt.
            mode=ClassificationMode(mode) if mode is not None else None,
            use_cloud=None if mode is not None else use_cloud,
            estimated_cost_usd=estimated_cost_usd,
            category_model=category_model,
            landmark_model=landmark_model,
        )
        return run.id if run is not None else None
