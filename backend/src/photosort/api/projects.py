from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
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
from photosort.models import (
    CriterionScoringRun,
    Photo,
    PhotoCategoryDetection,
    PhotoScore,
    Project,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
)
from photosort.opencloud.client import OpenCloudClient, OpenCloudError
from photosort.remote_classification import COST_PER_IMAGE_USD

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
    # (POST /score-criteria) muss die id des ScoringRun kennen, dessen Stand er zu scoren
    # beabsichtigt, damit der Server einen zwischenzeitlichen Re-Scan/Re-Scoring erkennen kann
    # (409-Staleness-Guard, siehe trigger_score_criteria unten).
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


class ClassifyCategoriesRemoteEstimateOut(BaseModel):
    """specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032
    Punkt 6.1: Kostenschaetzung vor dem Lauf - funktioniert unabhaengig vom Consent-Schalter (auch
    bei deaktiviertem Consent 200, kein 403)."""

    candidate_count: int
    provider: str
    price_per_image_usd: float
    estimated_cost_usd: float


class CloudVisionConsentUpdate(BaseModel):
    enabled: bool


class CloudVisionConsentOut(BaseModel):
    cloud_vision_detection_enabled: bool
    cloud_vision_consent_at: datetime | None


class ScoreCriteriaRequest(BaseModel):
    """specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md: kein
    top_n_per_cluster-Parameter mehr (ersetzt durch `scoring_run_id` - der Client uebergibt die
    id des ScoringRun, dessen Stand er beim Anzeigen von last_scoring_run gesehen hat, damit der
    Server einen zwischenzeitlichen Re-Scan/Re-Scoring als 409 ablehnen kann, statt auf einem
    veralteten cluster_key-Stand weiterzuarbeiten - siehe Edge Cases der Spec)."""

    scoring_run_id: int


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
    # category-mix.md, weiterhin verwendet fuer POST /score-criteria seit Spec 0037) - hier statt
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
    kleine Query HIER dupliziert statt worker.py zu importieren - api/projects.py (der uvicorn-
    Prozess) importiert bislang keinen Code aus worker.py, um dessen schwere ML-Importkette
    (mediapipe/tensorflow/onnxruntime ueber classification.py/aesthetics.py/label_embedding.py)
    nicht in den API-Importpfad zu ziehen (identisches Entkopplungsprinzip wie bei classification.py
    selbst, siehe dortiger Modul-Kommentar) - obwohl beide Prozesse im selben Docker-Image laufen,
    bliebe der uvicorn-Start sonst unnoetig langsamer."""
    photo_ids = (
        await session.execute(
            select(Photo.id)
            .join(PhotoScore, PhotoScore.photo_id == Photo.id)
            .where(Photo.project_id == project_id, PhotoScore.suggested_status.is_(None))
        )
    ).scalars().all()
    if not photo_ids:
        return 0
    already_classified_ids = set(
        (
            await session.execute(
                select(PhotoCategoryDetection.photo_id).where(
                    PhotoCategoryDetection.photo_id.in_(photo_ids)
                )
            )
        ).scalars()
    )
    return len([photo_id for photo_id in photo_ids if photo_id not in already_classified_ids])


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


@router.post("/{project_id}/score-criteria", status_code=status.HTTP_202_ACCEPTED)
async def trigger_score_criteria(
    project_id: int,
    payload: ScoreCriteriaRequest,
    session: AsyncSession = Depends(get_session),
    enqueuer: JobEnqueuer = Depends(get_job_enqueuer),
) -> dict[str, str]:
    """specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md (ersetzt /select-top):
    `403` wenn das Feature-Flag aus ist, `409` ohne erfolgreichen `ScoringRun`, `409` ohne
    bestaetigtes Gate, `409` bei veraltetem `scoring_run_id`-Bezug (Re-Scan/Re-Scoring waehrend
    der Kuratierung) - kein `top_n_per_cluster`-Parameter mehr (N wird erst beim Lesen
    angewendet). Legt selbst KEINE CriterionScoringRun-Zeile an - das erledigt der Job beim
    tatsaechlichen Start (run_criterion_scoring in worker.py), identisches Muster wie
    trigger_scan/trigger_score oben."""
    if not settings.category_selection_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diese Funktion ist derzeit nicht aktiviert.",
        )

    await _get_project_or_404(project_id, session)

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
            "lade das Projekt neu und starte die Kriterien-Bewertung erneut.",
        )

    await enqueuer.enqueue_job("score_criteria", project_id, payload.scoring_run_id)
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


@router.get(
    "/{project_id}/classify-categories-remote/estimate",
    response_model=ClassifyCategoriesRemoteEstimateOut,
)
async def estimate_classify_categories_remote(
    project_id: int, session: AsyncSession = Depends(get_session)
) -> ClassifyCategoriesRemoteEstimateOut:
    """specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
    Akzeptanzkriterium "Kostenschätzung": funktioniert UNABHAENGIG vom Consent-Schalter (auch bei
    deaktiviertem Consent 200, kein 403) - der Nutzer soll die Kosten VOR einer Consent-
    Entscheidung sehen koennen. `candidate_count=0` liefert weiterhin 200 mit
    estimated_cost_usd=0.0 (kein Sonderfall)."""
    await _get_project_or_404(project_id, session)

    candidate_count = await _count_remote_category_candidates(session, project_id)
    provider = settings.landmark_provider
    price_per_image_usd = COST_PER_IMAGE_USD[provider]
    return ClassifyCategoriesRemoteEstimateOut(
        candidate_count=candidate_count,
        provider=provider,
        price_per_image_usd=price_per_image_usd,
        estimated_cost_usd=candidate_count * price_per_image_usd,
    )


@router.post("/{project_id}/classify-categories-remote", status_code=status.HTTP_202_ACCEPTED)
async def trigger_classify_categories_remote(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    enqueuer: JobEnqueuer = Depends(get_job_enqueuer),
) -> dict[str, str]:
    """specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md,
    Akzeptanzkriterium "Remote-Klassifizierungs-Lauf": `403` ohne Consent, `409` ohne aktuellen
    erfolgreichen `ScoringRun` (dieselbe Vorbedingung wie score-criteria - der Kandidatenpool
    basiert auf `PhotoScore.suggested_status`, das braucht einen erfolgreichen Scan+Scoring-
    Durchlauf), sonst `202`. Legt selbst KEINE RemoteCategoryClassificationRun-Zeile an - das
    erledigt der Job beim tatsaechlichen Start (identisches Muster wie trigger_score_criteria)."""
    project = await _get_project_or_404(project_id, session)

    if not project.cloud_vision_detection_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cloud-Bilderkennung ist fuer dieses Projekt nicht aktiviert.",
        )

    latest_scoring_run = await _latest_scoring_run(session, project_id)
    if latest_scoring_run is None or latest_scoring_run.status != ScanStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fuehre zuerst die Ausschuss-Erkennung erfolgreich aus.",
        )

    await enqueuer.enqueue_job("classify_categories_remote", project_id)
    return {"status": "queued"}
