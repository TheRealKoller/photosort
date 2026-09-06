from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import (
    JobEnqueuer,
    get_current_user,
    get_job_enqueuer,
    get_opencloud_client,
    get_session,
)
from photosort.config import settings
from photosort.criteria import LANDMARK_CANDIDATE_CRITERION_KEYS, is_landmark_candidate
from photosort.models import (
    ClassificationPhase,
    CriterionScoringRun,
    FineLabel,
    Photo,
    PhotoCategoryClassification,
    PhotoCriterionScore,
    PhotoFineLabel,
    PhotoScore,
    Project,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
)
from photosort.opencloud.client import OpenCloudClient, OpenCloudError
from photosort.pricing import estimate_usd_per_image

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(get_current_user)])


class ProjectCreate(BaseModel):
    name: str
    opencloud_path: str


class ScanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ScanStatus
    started_at: datetime
    finished_at: datetime | None
    files_found: int
    # specs/features/0036-scan-performance-zweiphasig-parallel.md: None solange die
    # Enumerationsphase noch nicht abgeschlossen ist, unterscheidet sich bewusst von 0 (leeres
    # Projekt) - das Frontend muss `is not None`/`!= null` statt truthy pruefen (ADR 0020).
    total_files: int | None
    photos_added: int
    photos_updated: int
    photos_removed: int
    files_skipped: int
    error_message: str | None


class ScoringRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Additiv (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md): der Client
    # (POST /classify) muss die id des ScoringRun kennen, dessen Stand er zu scoren
    # beabsichtigt, damit der Server einen zwischenzeitlichen Re-Scan/Re-Scoring erkennen kann
    # (409-Staleness-Guard, siehe trigger_classify unten).
    id: int
    status: ScanStatus
    started_at: datetime
    finished_at: datetime | None
    photos_total: int
    photos_processed: int
    suggestions_found: int
    error_message: str | None
    # Ausschuss-Gate (specs/features/0037): None = noch nicht bestaetigt.
    gate_confirmed_at: datetime | None


class CriterionScoringRunSummary(BaseModel):
    """Ersetzt TopSelectionRunSummary (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
    backfill.md) - kein top_n_per_cluster/candidates_total/suggestions_found mehr: N ist beim
    Scoren nicht mehr bekannt (wird erst beim Lesen angewendet), und der Job waehlt keine Top-N
    mehr aus, sondern berechnet immer den vollen Rangfolge-Pool je Partition."""

    model_config = ConfigDict(from_attributes=True)

    status: ScanStatus
    started_at: datetime
    finished_at: datetime | None
    photos_total: int
    photos_processed: int
    error_message: str | None
    # specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, ADR 0050 Punkt 3: diese
    # Zusammenfassung beschreibt seit Spec 0296 den GESAMTEN Klassifizierungslauf, nicht mehr nur
    # seine Kriterien-Phase - `phase` benennt den gerade laufenden Teilschritt (NULL = laeuft nicht
    # mehr), `cloud_requested`/`cloud_error_message` machen die Cloud-Beteiligung nachtraeglich
    # erkennbar (Akzeptanzkriterien "Fehlerverhalten").
    phase: ClassificationPhase | None
    cloud_requested: bool
    cloud_error_message: str | None


class RemoteCategoryClassificationRunSummary(BaseModel):
    """specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032
    Punkt 6: Run-Tracking analog CriterionScoringRunSummary, aber ohne scoring_run_id/Gate-Bezug
    (dieser Job ist unabhaengig von einem Ausschuss-Gate/ScoringRun)."""

    model_config = ConfigDict(from_attributes=True)

    status: ScanStatus
    started_at: datetime
    finished_at: datetime | None
    photos_total: int
    photos_processed: int
    error_message: str | None


class ClassificationEstimateOut(BaseModel):
    """specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, ADR 0050 Punkt 5 -
    Nachfolger von ClassifyCategoriesRemoteEstimateOut: die Schaetzung deckt jetzt ALLE
    Cloud-Anteile ab, die die Checkbox freigibt, nicht nur die Kategorie-Klassifizierung.
    Funktioniert weiterhin unabhaengig vom Consent-Schalter (auch bei deaktiviertem Consent 200,
    kein 403) - die Kosten sollen VOR einer Consent-Entscheidung sichtbar sein.

    `candidate_count` ist die Summe der beiden Einzelanteile und bleibt damit die eine Zahl, die
    das Frontend anzeigt; die beiden Einzelfelder machen nachvollziehbar, woraus sie sich
    zusammensetzt."""

    candidate_count: int
    remote_category_candidate_count: int
    landmark_candidate_count: int
    provider: str
    # specs/features/0304-cloud-modell-je-anbieter-waehlbar.md, decisions/0059-modellwahl-je-
    # anbieter-und-modellgebundene-kostenschaetzung.md Punkt 4: die Antwort sagt selbst, WORAUF
    # sich die Schaetzung bezieht. Seit die Modellwahl eine Betriebseinstellung ist, benennt
    # `provider` allein die Preisgrundlage nicht mehr eindeutig - genau die Verwechslung, die
    # diese Spec behebt. Feldname `model` und nicht `model_id`: pydantic v2 schuetzt den
    # Namensraum `model_` und wuerde bei `model_id` warnen.
    model: str
    # `| None` heisst "fuer das eingestellte Modell ist kein Preis hinterlegt", nie ein stilles
    # `0.0` (ADR 0059 Punkt 4, dieselbe Semantik wie `pricing.py::compute_cost_usd`). Die
    # Oberflaeche weist diesen Fall an der Schaetzung als fehlende Kostenangabe aus, statt einen
    # falschen Betrag zu zeigen - die Schaetzung ist seit Spec 0296 die einzige verbliebene
    # Absicherung vor der kostenpflichtigen Aktion, ein falscher Betrag waere schlimmer als
    # keiner. Der Normalfall bleibt ein Betrag: dass jedes waehlbare Modell einen Preis hat, ist
    # per Invariantentest erzwungen (tests/test_pricing.py) - dieser Pfad ist die zweite
    # Verteidigungslinie, nicht der Regelfall.
    price_per_image_usd: float | None
    estimated_cost_usd: float | None


class CloudVisionConsentUpdate(BaseModel):
    enabled: bool


class CloudVisionConsentOut(BaseModel):
    cloud_vision_detection_enabled: bool
    cloud_vision_consent_at: datetime | None


class ClassifyRequest(BaseModel):
    """specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md: kein
    top_n_per_cluster-Parameter (ersetzt durch `scoring_run_id` - der Client uebergibt die
    id des ScoringRun, dessen Stand er beim Anzeigen von last_scoring_run gesehen hat, damit der
    Server einen zwischenzeitlichen Re-Scan/Re-Scoring als 409 ablehnen kann, statt auf einem
    veralteten cluster_key-Stand weiterzuarbeiten - siehe Edge Cases der Spec).

    specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, ADR 0050 Punkt 2:
    `use_cloud` ist die laufbezogene Cloud-Freigabe (die Checkbox am Ausloeser). Sie erteilt
    KEINE Einwilligung - die bleibt ausschliesslich `PUT .../cloud-vision-consent` - sondern
    entscheidet nur, ob die vorhandene Einwilligung fuer genau diesen Lauf genutzt wird. Kein
    Default: der Client soll sich sichtbar entscheiden muessen, statt in eine Voreinstellung zu
    laufen, die Kosten verursacht."""

    scoring_run_id: int
    use_cloud: bool


class ProjectOut(BaseModel):
    id: int
    name: str
    opencloud_drive_id: str
    opencloud_path: str
    created_at: datetime
    last_scan: ScanSummary | None = None
    last_scoring_run: ScoringRunSummary | None = None
    last_criterion_scoring_run: CriterionScoringRunSummary | None = None
    # specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032
    # Punkt 6: analog last_criterion_scoring_run.
    last_remote_category_classification_run: RemoteCategoryClassificationRunSummary | None = None
    # Globales Feature-Flag, nicht projektspezifisch (specs/features/0024-top-photo-selection-
    # category-mix.md, weiterhin verwendet fuer POST /classify seit Spec 0296) - hier statt
    # in einem neuen Endpunkt exponiert: technische Detailentscheidung der Umsetzung, damit das
    # Frontend-Verfuegbarkeitsgate proaktiv aus den ohnehin bereits geladenen Projektdaten dieser
    # Seite ableiten kann (UI/UX-Abschnitt der Spec), statt erst nach einem fehlgeschlagenen 403.
    category_selection_enabled: bool
    # Projektweiter Einwilligungs-Schalter fuer produktive Cloud-Vision-Datenfluesse (urspruenglich
    # nur die Cloud-Sehenswuerdigkeit-Erkennung, specs/features/0047-sehenswuerdigkeit-erkennung-
    # cloud-vision-api.md, decisions/0025-cloud-landmark-erkennung.md Punkt 5, umbenannt seit
    # specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt
    # 2 Migration a) - hier statt in einem eigenen GET exponiert, damit ProjectSettingsPage den
    # aktuellen Zustand aus den bereits geladenen Projektdaten lesen kann. Gated seitdem sowohl
    # `landmark` als auch die neue Remote-Kategorie-Klassifizierung.
    cloud_vision_detection_enabled: bool
    cloud_vision_consent_at: datetime | None


async def _latest_scan_run(session: AsyncSession, project_id: int) -> ScanRun | None:
    result = await session.execute(
        select(ScanRun)
        .where(ScanRun.project_id == project_id)
        .order_by(ScanRun.started_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _latest_scoring_run(session: AsyncSession, project_id: int) -> ScoringRun | None:
    result = await session.execute(
        select(ScoringRun)
        .where(ScoringRun.project_id == project_id)
        .order_by(ScoringRun.started_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _latest_criterion_scoring_run(
    session: AsyncSession, project_id: int
) -> CriterionScoringRun | None:
    result = await session.execute(
        select(CriterionScoringRun)
        .where(CriterionScoringRun.project_id == project_id)
        .order_by(CriterionScoringRun.started_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _latest_remote_category_classification_run(
    session: AsyncSession, project_id: int
) -> RemoteCategoryClassificationRun | None:
    result = await session.execute(
        select(RemoteCategoryClassificationRun)
        .where(RemoteCategoryClassificationRun.project_id == project_id)
        .order_by(RemoteCategoryClassificationRun.started_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _count_remote_category_candidates(session: AsyncSession, project_id: int) -> int:
    """specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
    Akzeptanzkriterium "Kostenschätzung": "ermittelt über dieselbe Kandidaten-Selektion wie der
    tatsächliche Lauf" (worker.py::select_remote_category_candidates). Bewusst als eigenstaendige,
    kleine Query HIER dupliziert statt worker.py zu importieren - haelt die API-Schicht (reine
    HTTP-/Validierungs-/Lese-Zustaendigkeit) unabhaengig von der Worker-Schicht (Job-Ausfuehrung),
    identisches Modulgrenzen-Prinzip wie die uebrigen api/*.py-Dateien, die Jobs ausschliesslich
    ueber den stringbasierten JobEnqueuer ausloesen statt worker.py-Funktionen direkt zu
    importieren. (Ein direkter Import waere technisch unproblematisch - mediapipe/tensorflow/
    onnxruntime werden in classification.py/aesthetics.py/label_embedding.py durchgaengig lokal
    innerhalb der jeweiligen build_*()-Funktion importiert, nicht auf Modulebene - reiner
    Architektur-Klarheitsgrund, siehe api/photos.py fuer die eine bewusste Ausnahme, wo die Spec
    einen synchronen Aufruf im selben Request verlangt.)

    Copilot-Review-Fund (PR #201): vorher zwei getrennte SELECTs (alle Kandidaten-`photo_id`s nach
    Python laden, dann ein zweites SELECT + Python-seitiger Filter) - bei einem grossen Projekt
    unnoetig viel Speicher/IO, gerade weil die Kostenschaetzung eager beim Laden der
    Kuratierungs-Seite ausgefuehrt wird. Jetzt ein einzelnes `COUNT` mit `NOT EXISTS`, komplett
    serverseitig ausgewertet - keine Zeile verlaesst die Datenbank."""
    already_classified = exists().where(PhotoCategoryClassification.photo_id == Photo.id)
    result = await session.execute(
        select(func.count())
        .select_from(Photo)
        .join(PhotoScore, PhotoScore.photo_id == Photo.id)
        .where(
            Photo.project_id == project_id,
            PhotoScore.suggested_status.is_(None),
            ~already_classified,
        )
    )
    return result.scalar_one()


async def _count_landmark_candidates(session: AsyncSession, project_id: int) -> int:
    """Der Landmark-Anteil der Kostenschaetzung (specs/features/0296-klassifizierung-ein-ausloeser-
    cloud-checkbox.md, decisions/0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-
    freigabe.md Punkt 5).

    Zaehlt Ausschuss-Ueberlebende, deren BEREITS GESPEICHERTE Kriterien-Werte
    `criteria.py::is_landmark_candidate` erfuellen und die noch keine `landmark`-Zeile haben -
    dieselbe reine Schwellenwert-Funktion, die auch der Live-Lauf ueber
    worker.py::_select_landmark_candidates nutzt (kein zweiter, auseinanderlaufender Grenzwert).

    STRUKTURELL EINE SCHAETZUNG, keine Vorausberechnung (ADR 0050 Punkt 5): die Landmark-
    Kandidaten des kommenden Laufs ergeben sich aus Kriterien-Werten, die genau dieser Lauf erst
    neu berechnet. Vor dem allerersten Lauf eines Projekts liegen gar keine Vorwerte vor und die
    Zahl ist 0. Das ist bewusst so - die Zahl ist in der Oberflaeche als Schaetzung ausgewiesen,
    und ein Foto, das schon einmal Landmark-Kandidat war, bleibt es in aller Regel. Die Alternative
    (den Landmark-Anteil gar nicht schaetzen) haette die Schaetzung erneut nur einen Teil der
    freigegebenen Kosten abdecken lassen - genau der Mangel, den Spec 0296 behebt.

    Die Schwellenwert-Pruefung laeuft bewusst in Python statt als SQL-Ausdruck: `is_landmark_
    candidate` ist die geteilte Quelle der Wahrheit, und eine SQL-Nachbildung der Schwellenwerte
    waere genau die zweite, auseinanderlaufende Stelle, die criteria.py vermeiden soll. Geladen
    werden dafuer nur die beiden relevanten Kriterien-Zeilen je Foto, nicht die vollen Fotos."""
    already_scored = (
        select(PhotoCriterionScore.photo_id)
        .join(Photo, Photo.id == PhotoCriterionScore.photo_id)
        .where(Photo.project_id == project_id, PhotoCriterionScore.criterion_key == "landmark")
    )
    rows = (
        await session.execute(
            select(PhotoCriterionScore.photo_id, PhotoCriterionScore.criterion_key,
                   PhotoCriterionScore.value)
            .join(Photo, Photo.id == PhotoCriterionScore.photo_id)
            .join(PhotoScore, PhotoScore.photo_id == Photo.id)
            .where(
                Photo.project_id == project_id,
                PhotoScore.suggested_status.is_(None),
                PhotoCriterionScore.criterion_key.in_(LANDMARK_CANDIDATE_CRITERION_KEYS),
                PhotoCriterionScore.photo_id.not_in(already_scored),
            )
        )
    ).all()

    values_by_photo: dict[int, dict[str, float]] = {}
    for photo_id, criterion_key, value in rows:
        values_by_photo.setdefault(photo_id, {})[criterion_key] = value
    return sum(1 for values in values_by_photo.values() if is_landmark_candidate(values))


async def _to_project_out(session: AsyncSession, project: Project) -> ProjectOut:
    scan_run = await _latest_scan_run(session, project.id)
    scoring_run = await _latest_scoring_run(session, project.id)
    criterion_scoring_run = await _latest_criterion_scoring_run(session, project.id)
    remote_category_run = await _latest_remote_category_classification_run(session, project.id)
    return ProjectOut(
        id=project.id,
        name=project.name,
        opencloud_drive_id=project.opencloud_drive_id,
        opencloud_path=project.opencloud_path,
        created_at=project.created_at,
        last_scan=ScanSummary.model_validate(scan_run) if scan_run is not None else None,
        last_scoring_run=(
            ScoringRunSummary.model_validate(scoring_run) if scoring_run is not None else None
        ),
        last_criterion_scoring_run=(
            CriterionScoringRunSummary.model_validate(criterion_scoring_run)
            if criterion_scoring_run is not None
            else None
        ),
        last_remote_category_classification_run=(
            RemoteCategoryClassificationRunSummary.model_validate(remote_category_run)
            if remote_category_run is not None
            else None
        ),
        category_selection_enabled=settings.category_selection_enabled,
        cloud_vision_detection_enabled=project.cloud_vision_detection_enabled,
        cloud_vision_consent_at=project.cloud_vision_consent_at,
    )


async def _get_project_or_404(project_id: int, session: AsyncSession) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    client: OpenCloudClient = Depends(get_opencloud_client),
) -> ProjectOut:
    try:
        drive = await client.resolve_drive(settings.opencloud_drive_name or None)
        await client.list_folder(drive.webdav_url, payload.opencloud_path)
    except OpenCloudError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    project = Project(
        name=payload.name,
        opencloud_drive_id=drive.id,
        opencloud_path=payload.opencloud_path,
    )
    session.add(project)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Projekt '{payload.name}' existiert bereits.",
        ) from exc

    await session.refresh(project)
    return await _to_project_out(session, project)


@router.get("", response_model=list[ProjectOut])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[ProjectOut]:
    result = await session.execute(select(Project).order_by(Project.created_at))
    return [await _to_project_out(session, project) for project in result.scalars()]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int, session: AsyncSession = Depends(get_session)
) -> ProjectOut:
    project = await _get_project_or_404(project_id, session)
    return await _to_project_out(session, project)


@router.post("/{project_id}/scan", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    enqueuer: JobEnqueuer = Depends(get_job_enqueuer),
) -> dict[str, str]:
    await _get_project_or_404(project_id, session)
    await enqueuer.enqueue_job("scan_project", project_id)
    return {"status": "queued"}


@router.post("/{project_id}/score", status_code=status.HTTP_202_ACCEPTED)
async def trigger_score(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    enqueuer: JobEnqueuer = Depends(get_job_enqueuer),
) -> dict[str, str]:
    # Analog trigger_scan oben (specs/features/0003-automatic-best-photo-selection.md): derselbe
    # Router-weite dependencies=[Depends(get_current_user)]-Torwaechter, keine Rollenunterscheidung
    # zwischen den beiden bekannten Nutzern - Muss-Kriterium aus dem Security-Abschnitt der Spec.
    await _get_project_or_404(project_id, session)
    await enqueuer.enqueue_job("score_project", project_id)
    return {"status": "queued"}


@router.post("/{project_id}/confirm-ausschuss-gate", status_code=status.HTTP_200_OK)
async def confirm_ausschuss_gate(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Ausschuss-Gate (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md): `409`
    ohne erfolgreichen `ScoringRun`; setzt bei vorhandenem erfolgreichem `ScoringRun`
    `gate_confirmed_at`; wiederholter Aufruf ist idempotent (kein Fehler, kein zweiter Effekt -
    ein bereits gesetzter Zeitstempel wird nicht ueberschrieben). Projektweit, nicht
    personenbezogen (kein user_id-Bezug, siehe Security-Abschnitt der Spec, konsistent mit
    ScanRun/ScoringRun/CriterionScoringRun)."""
    await _get_project_or_404(project_id, session)

    latest_scoring_run = await _latest_scoring_run(session, project_id)
    if latest_scoring_run is None or latest_scoring_run.status != ScanStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fuehre zuerst die Ausschuss-Erkennung erfolgreich aus.",
        )

    if latest_scoring_run.gate_confirmed_at is None:
        latest_scoring_run.gate_confirmed_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()

    return {"status": "confirmed"}


@router.post("/{project_id}/classify", status_code=status.HTTP_202_ACCEPTED)
async def trigger_classify(
    project_id: int,
    payload: ClassifyRequest,
    session: AsyncSession = Depends(get_session),
    enqueuer: JobEnqueuer = Depends(get_job_enqueuer),
) -> dict[str, str]:
    """Der EINE Ausloeser der Klassifizierung (specs/features/0296-klassifizierung-ein-ausloeser-
    cloud-checkbox.md, decisions/0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-
    freigabe.md Punkt 5) - ersetzt `POST .../score-criteria` UND
    `POST .../classify-categories-remote` ersatzlos. Der ausgeloeste Job verkettet beide Phasen
    (worker.py::run_classification), die frueher bekannte Reihenfolge-Regel entfaellt damit.

    Vorbedingungen unveraendert von score-criteria uebernommen: `403` wenn das Feature-Flag aus
    ist, `404` bei unbekanntem Projekt, `409` ohne erfolgreichen `ScoringRun`, `409` ohne
    bestaetigtes Gate, `409` bei veraltetem `scoring_run_id`-Bezug (Re-Scan/Re-Scoring waehrend
    der Kuratierung). NEU: `403`, wenn `use_cloud=true` ohne projektweite Einwilligung angefragt
    wird - ein Client, der Cloud-Verarbeitung ohne Einwilligung anfordert, soll das erfahren,
    statt still auf "lokal" herunterzufallen. Diese Pruefung ist die sprechende Frueh-
    rueckmeldung, NICHT das Sicherheitsnetz: das eigentliche Gate ist die Konjunktion
    `use_cloud and project.cloud_vision_detection_enabled`, ausgewertet im Worker unmittelbar vor
    der Client-Konstruktion (ADR 0050 Punkt 2).

    Legt selbst KEINE CriterionScoringRun-Zeile an - das erledigt der Job beim tatsaechlichen
    Start (run_classification in worker.py), identisches Muster wie trigger_scan/trigger_score."""
    if not settings.category_selection_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diese Funktion ist derzeit nicht aktiviert.",
        )

    project = await _get_project_or_404(project_id, session)

    latest_scoring_run = await _latest_scoring_run(session, project_id)
    if latest_scoring_run is None or latest_scoring_run.status != ScanStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fuehre zuerst die Ausschuss-Erkennung erfolgreich aus.",
        )
    if latest_scoring_run.gate_confirmed_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bestaetige zuerst das Ausschuss-Gate.",
        )
    if payload.scoring_run_id != latest_scoring_run.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Der Ausschuss wurde zwischenzeitlich neu ermittelt (Re-Scan/Re-Scoring) - "
            "lade das Projekt neu und starte die Klassifizierung erneut.",
        )
    if payload.use_cloud and not project.cloud_vision_detection_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cloud-Bilderkennung ist fuer dieses Projekt nicht aktiviert.",
        )

    await enqueuer.enqueue_job(
        "classify", project_id, payload.scoring_run_id, payload.use_cloud
    )
    return {"status": "queued"}


@router.put("/{project_id}/cloud-vision-consent", response_model=CloudVisionConsentOut)
async def set_cloud_vision_consent(
    project_id: int,
    payload: CloudVisionConsentUpdate,
    session: AsyncSession = Depends(get_session),
) -> CloudVisionConsentOut:
    """specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md, ADR
    decisions/0025-cloud-landmark-erkennung.md Punkt 5: `PUT` statt `POST`, da ein Zustand
    gesetzt wird statt ein Job ausgeloest (Vorbild: `PUT /photos/{id}/rating`, nicht
    `POST /projects/{id}/score`). Haengt am bestehenden router-weiten Auth-Torwaechter (Muss-
    Kriterium der Spec, kein zusaetzlicher `Depends(get_current_user)` hier noetig). Setzt
    synchron `cloud_vision_consent_at` (Zeitstempel bei Aktivierung, `NULL` bei Deaktivierung) -
    kein "nur beim ersten Mal"-Sonderfall, ein wiederholtes Aktivieren aktualisiert den
    Zeitstempel jedes Mal erneut.

    Umbenannt von `cloud-landmark-consent` (specs/features/0055-remote-kategorie-klassifizierung-
    mit-kostenschaetzung.md, ADR 0032 Punkt 2 Migration a): derselbe Schalter gated seitdem
    zusaetzlich die neue Remote-Kategorie-Klassifizierung (worker.py::
    run_remote_category_classification) - kein zweiter, granularerer Consent-Schalter."""
    project = await _get_project_or_404(project_id, session)

    project.cloud_vision_detection_enabled = payload.enabled
    project.cloud_vision_consent_at = (
        datetime.now(UTC).replace(tzinfo=None) if payload.enabled else None
    )
    await session.commit()
    await session.refresh(project)

    return CloudVisionConsentOut(
        cloud_vision_detection_enabled=project.cloud_vision_detection_enabled,
        cloud_vision_consent_at=project.cloud_vision_consent_at,
    )


@router.get("/{project_id}/classify/estimate", response_model=ClassificationEstimateOut)
async def estimate_classification(
    project_id: int, session: AsyncSession = Depends(get_session)
) -> ClassificationEstimateOut:
    """specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, ADR 0050 Punkt 5 -
    Nachfolger von `GET .../classify-categories-remote/estimate`: die Schaetzung deckt jetzt BEIDE
    Cloud-Anteile ab, weil die Checkbox am Ausloeser beide freigibt.

    Funktioniert weiterhin UNABHAENGIG vom Consent-Schalter (auch bei deaktiviertem Consent 200,
    kein 403) - der Nutzer soll die Kosten VOR einer Consent-Entscheidung sehen koennen.
    `candidate_count=0` liefert weiterhin 200 mit estimated_cost_usd=0.0 (kein Sonderfall)."""
    await _get_project_or_404(project_id, session)

    remote_category_candidate_count = await _count_remote_category_candidates(session, project_id)
    landmark_candidate_count = await _count_landmark_candidates(session, project_id)
    candidate_count = remote_category_candidate_count + landmark_candidate_count
    provider = settings.landmark_provider
    # Spec 0304: die Schaetzung haengt am tatsaechlich EINGESTELLTEN Modell, nicht mehr am
    # Anbieter - ein Modellwechsel kann sie damit nicht mehr unbemerkt falsch machen.
    model = settings.resolved_landmark_model()
    price_per_image_usd = estimate_usd_per_image(model, provider)
    return ClassificationEstimateOut(
        candidate_count=candidate_count,
        remote_category_candidate_count=remote_category_candidate_count,
        landmark_candidate_count=landmark_candidate_count,
        provider=provider,
        model=model,
        price_per_image_usd=price_per_image_usd,
        estimated_cost_usd=(
            None if price_per_image_usd is None else candidate_count * price_per_image_usd
        ),
    )


class FineLabelCountOut(BaseModel):
    """Ein Feinlabel samt seiner Haeufigkeit IN DIESEM PROJEKT (specs/features/0289-feste-
    kategorien.md, Umsetzungsschritt 6). `display_name` ist freier, extern erzeugter LLM-Text
    (zeichensaniert beim Uebernehmen der Modellantwort) - im Frontend ausschliesslich als
    regulaerer Textknoten zu rendern."""

    canonical_key: str
    display_name: str
    photo_count: int


@router.get("/{project_id}/fine-labels", response_model=list[FineLabelCountOut])
async def list_fine_labels(
    project_id: int, session: AsyncSession = Depends(get_session)
) -> list[FineLabelCountOut]:
    """Haeufigste Feinlabels dieses Projekts, absteigend nach `photo_count`, Tie-Break
    `canonical_key` aufsteigend (specs/features/0289-feste-kategorien.md).

    Zweck: sichtbar machen, welche Kategorie im festen Set gegebenenfalls fehlt - das Set ist per
    Produktentscheidung geschlossen, aber nicht fuer immer festgelegt, und diese Liste ist der
    Aenderungspfad.

    SECURITY-MUSS-KRITERIUM (Spec 0289, Abschnitt 1): `fine_labels` ist bewusst eine
    PROJEKTUEBERGREIFENDE Vokabular-Registry (siehe models.py::FineLabel) - die Zaehlung MUSS
    deshalb ueber `photo_fine_labels -> photos.project_id` joinen. Ein globales
    `SELECT ... FROM fine_labels` wuerde Label-Haeufigkeiten ANDERER Projekte ausliefern.
    Vokabular-Eintraege ohne Foto im angefragten Projekt erscheinen durch den Join implizit nicht
    (photo_count > 0). Ein leeres Projekt liefert `200` mit leerer Liste; eine unbekannte
    project_id laeuft ueber `_get_project_or_404` in ein `404` (keine Objekt-ID-Enumeration ueber
    ein leeres 200). Ein Eigentuemer-Vergleich ist bewusst NICHT implementiert - das Auth-Modell
    (decisions/0003-auth-model.md) kennt kein Rollen-/Eigentuemermodell, beide Nutzer sehen
    dieselben Projekte; ein hier neu erfundener Ownership-Check waere eine stillschweigende
    Aenderung des Auth-Modells."""
    await _get_project_or_404(project_id, session)

    rows = (
        await session.execute(
            select(
                FineLabel.canonical_key,
                FineLabel.display_name,
                func.count(func.distinct(PhotoFineLabel.photo_id)).label("photo_count"),
            )
            .join(PhotoFineLabel, PhotoFineLabel.fine_label_id == FineLabel.id)
            .join(Photo, Photo.id == PhotoFineLabel.photo_id)
            .where(Photo.project_id == project_id)
            .group_by(FineLabel.id, FineLabel.canonical_key, FineLabel.display_name)
            .order_by(func.count(func.distinct(PhotoFineLabel.photo_id)).desc(),
                      FineLabel.canonical_key.asc())
        )
    ).all()

    return [
        FineLabelCountOut(
            canonical_key=canonical_key, display_name=display_name, photo_count=photo_count
        )
        for canonical_key, display_name, photo_count in rows
    ]
