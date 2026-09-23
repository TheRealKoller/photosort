from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import (
    JobEnqueuer,
    get_current_user,
    get_job_enqueuer,
    get_opencloud_client,
    get_session,
)
from photosort.classification_eta import remaining_seconds
from photosort.clock import now_utc
from photosort.cloud_vision import provider_for_vision_model
from photosort.config import settings
from photosort.criteria import LANDMARK_CANDIDATE_CRITERION_KEYS, is_landmark_candidate
from photosort.duplicates import has_open_suggestion, survives_ausschuss
from photosort.models import (
    ClassificationPhase,
    CloudVisionPhase,
    CriterionScoringRun,
    DuplicateDecision,
    FineLabel,
    MotifAssessmentSource,
    Photo,
    PhotoAlbumSuitability,
    PhotoCriterionScore,
    PhotoDuplicateDecision,
    PhotoFineLabel,
    PhotoMotifAssessment,
    PhotoScore,
    Project,
    RemoteCategoryClassificationRun,
    ScanRun,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.opencloud.client import OpenCloudClient, OpenCloudError
from photosort.photo_aggregates import (
    EMPTY_PHOTO_AGGREGATE,
    PhotoAggregate,
    photo_aggregate_for_project,
    photo_aggregates_by_project,
)
from photosort.pricing import estimate_usd_per_image
from photosort.project_deletion import collect_photo_cache_keys, delete_projects
from photosort.selection import effective_target
from photosort.thumbnails import delete_cached_variants
from photosort.worker import rebuild_run_selection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"], dependencies=[Depends(get_current_user)])


class ProjectCreate(BaseModel):
    name: str
    opencloud_path: str


class ProjectDelete(BaseModel):
    """Der Bestätigungs-Body von `DELETE /projects/{project_id}`.

    Die serverseitige Namenspruefung ist eine VORSATZ-, keine Autorisierungshuerde: der
    Projektname ist fuer beide Nutzer ueber `GET /projects` sichtbar. Sie wirkt gegen ein
    Versehen und gegen ein blind absetzendes Skript, das die Oberflaeche umgeht - eine rein
    clientseitige Bestaetigung waere wirkungslos.

    `max_length=500` wehrt nur absurde Payloads ab. Der Wert fliesst in keinen Pfad, keine
    Query-Konstruktion und keine Logzeile."""

    confirm_name: str = Field(max_length=500)


class ScanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ScanStatus
    started_at: datetime
    finished_at: datetime | None
    files_found: int
    # None solange die Enumerationsphase noch nicht abgeschlossen ist, unterschieden von 0
    # (leeres Projekt) - das Frontend muss `is not None`/`!= null` statt truthy pruefen.
    total_files: int | None
    photos_added: int
    photos_updated: int
    photos_removed: int
    files_skipped: int
    error_message: str | None


class ScoringRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Der Client (POST /classify) muss die id des ScoringRun kennen, dessen Stand er zu scoren
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
    # Ausschuss-Gate: None = noch nicht bestaetigt.
    gate_confirmed_at: datetime | None


class CloudPhaseSummaryOut(BaseModel):
    """Ein Cloud-Teilschritt EINES Klassifizierungslaufs - während des Laufs die
    Fortschrittsanzeige, danach die Bilanz. DERSELBE Datensatz zu zwei Zeitpunkten, nie eine
    zweite "Bilanz"-Struktur daneben: sie waere eine zweite Definition derselben Zahlen und
    driftete.

    Geschluesselt ueber `CloudVisionPhase` - dieselbe Schluesselung wie `CostByPurposeOut` der
    Statistikseite, damit "Landmark-Anteil" ueberall dasselbe Wort ist.

    Die beiden Zahlengruppen sind getrennt:
    - `photos_processed`/`failed_calls` bewegen sich LIVE (je asyncio.gather-Block committet),
    - `responses_used` (= `api_calls`), Tokens und `cost_usd` stehen erst am PHASENENDE fest und
      sind dann eingefroren.

    `cost_usd is None` heisst "kein Preis fuer dieses Modell hinterlegt ODER nicht erfasst", nie
    "kostenlos" - die `null`-Kette schlaegt bis in die Anzeige durch, kein `?? 0` im Pfad.
    `provider` wird aus `model` ABGELEITET (`cloud_vision.py::provider_for_vision_model`), nie aus
    der aktuellen Betriebseinstellung gelesen; `None` heisst "Modell nicht (mehr) in der
    Registry", und die Oberflaeche zeigt dann die Modell-ID allein statt einen
    Konfigurationshinweis."""

    purpose: CloudVisionPhase
    photos_total: int | None
    photos_processed: int | None
    failed_calls: int | None
    responses_used: int | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    model: str | None
    provider: str | None


class CriterionScoringRunSummary(BaseModel):
    """Kein top_n_per_cluster/candidates_total/suggestions_found: N ist beim Scoren nicht bekannt
    (wird erst beim Lesen angewendet), und der Job berechnet immer den vollen Rangfolge-Pool je
    Partition."""

    model_config = ConfigDict(from_attributes=True)

    status: ScanStatus
    started_at: datetime
    finished_at: datetime | None
    photos_total: int
    photos_processed: int
    error_message: str | None
    # Diese Zusammenfassung beschreibt den GESAMTEN Klassifizierungslauf, nicht nur seine
    # Kriterien-Phase - `phase` benennt den gerade laufenden Teilschritt (NULL = laeuft nicht
    # mehr), `cloud_requested`/`cloud_error_message` machen die Cloud-Beteiligung nachtraeglich
    # erkennbar.
    phase: ClassificationPhase | None
    cloud_requested: bool
    cloud_error_message: str | None
    # `cloud_phases` in AUSFUEHRUNGSREIHENFOLGE (remote_category, dann landmark); ein Eintrag
    # entsteht, sobald die Phase betreten wurde (Remote: Fremdschluessel gesetzt; Landmark:
    # `landmark_photos_total is not None`). Eine LEERE LISTE heisst "dieser Durchlauf hatte
    # keinen Cloud-Teilschritt" - der Anker fuer die entsprechende Aussage der Oberflaeche, statt
    # leerer Felder oder Nullwerte.
    #
    # `estimated_cost_usd` ist die am Lauf eingefrorene Start-Schaetzung.
    #
    # `cloud_cost_total_usd` faellt auf `None`, sobald EIN beteiligter Anteil `None` ist - die
    # Regel "unvollstaendig != 0" bleibt damit serverseitig an EINER Stelle (wie
    # `CostOut.total_usd`), statt in jeder Komponente einzeln zu leben.
    estimated_cost_usd: float | None
    cloud_phases: list[CloudPhaseSummaryOut]
    cloud_cost_total_usd: float | None
    # Die geschaetzte Restdauer GENAU DES Teilschritts, den `phase` nennt - in Sekunden, nicht als
    # Text: Die Spanne, die die Oberflaeche daraus macht, ist eine Darstellungsentscheidung
    # (ADR 0116 Punkt 4).
    #
    # EIN Feld, keines je Teilschritt und keines an `CloudPhaseSummaryOut`: Es laeuft zu jedem
    # Zeitpunkt genau einer, ein erledigter hat keine Restdauer und ein ausstehender keine
    # Messgrundlage.
    #
    # `null` heisst "noch nicht abschaetzbar", NIE "keine Restdauer" und nie "sofort fertig" -
    # die Oberflaeche schreibt dort sichtbar hin, dass die Angabe noch fehlt, statt ein leeres
    # Feld zu zeigen. `null` steht auch immer bei `ranking` (keine gezaehlte Menge) und bei jedem
    # beendeten Lauf.
    phase_remaining_seconds: float | None


class ClassificationEstimatePartOut(BaseModel):
    """Ein einzelner Cloud-Anteil der Vorab-Schätzung - Kategorie-Vorschläge bzw.
    Sehenswürdigkeits-Erkennung.

    `candidate_count is None` heisst "dieser Anteil ist nicht verlaesslich schaetzbar", NIE
    "null Fotos". Der Fall tritt beim Landmark-Anteil vor dem ersten erfolgreichen Durchlauf
    eines Projekts auf: dort gibt es keine gespeicherten Kriterien-Werte, aus denen sich
    Kandidaten ableiten ließen. Eine `0` an dieser Stelle behauptete Kostenfreiheit für einen
    Anteil, der gleich Geld kostet.

    `estimated_cost_usd is None` heisst "kein Preis hinterlegt ODER Anteil nicht schaetzbar" -
    dieselbe "`null` heißt unbekannt, nie kostenlos"-Linie wie bei `price_per_image_usd`."""

    candidate_count: int | None
    estimated_cost_usd: float | None


class ClassificationEstimateOut(BaseModel):
    """Die Schätzung deckt ALLE Cloud-Anteile ab, die die Checkbox freigibt, nicht nur die
    Kategorie-Klassifizierung. Sie funktioniert unabhängig vom Consent-Schalter (auch bei
    deaktiviertem Consent 200, kein 403) - die Kosten sollen VOR einer Consent-Entscheidung
    sichtbar sein.

    Die beiden Anteile sind eigene Objekte mit Fotoanzahl UND Betrag; kein Client leitet einen
    Betrag selbst ab, sonst entstuende ein zweiter Weg zu derselben Zahl ohne `null`-Semantik.

    `candidate_count` ist die Summe der BEKANNTEN Anteile und damit bei unbekanntem
    Landmark-Anteil ausdruecklich eine UNTERE SCHRANKE. Sie faellt nicht auf `null`: sonst saehe
    der Nutzer vor seinem ersten Durchlauf ueberhaupt keinen Betrag mehr, obwohl der
    Kategorie-Anteil bekannt ist."""

    candidate_count: int
    remote_categories: ClassificationEstimatePartOut
    landmark: ClassificationEstimatePartOut
    provider: str
    # Die Antwort sagt selbst, WORAUF sich die Schätzung bezieht: da die Modellwahl eine
    # Betriebseinstellung ist, benennt `provider` allein die Preisgrundlage nicht eindeutig.
    # Feldname `model` und nicht `model_id`: pydantic v2 schützt den Namensraum `model_` und
    # würde bei `model_id` warnen.
    model: str
    # `| None` heißt "für das eingestellte Modell ist kein Preis hinterlegt", nie ein stilles
    # `0.0` (dieselbe Semantik wie `pricing.py::compute_cost_usd`). Die Oberfläche weist diesen
    # Fall an der Schätzung als fehlende Kostenangabe aus, statt einen falschen Betrag zu zeigen.
    # Der Normalfall bleibt ein Betrag: dass jedes wählbare Modell einen Preis hat, ist per
    # Invariantentest erzwungen (tests/test_pricing.py).
    price_per_image_usd: float | None
    estimated_cost_usd: float | None


class CloudVisionConsentUpdate(BaseModel):
    enabled: bool


class CloudVisionConsentOut(BaseModel):
    cloud_vision_detection_enabled: bool
    cloud_vision_consent_at: datetime | None


class ClassifyRequest(BaseModel):
    """Kein top_n_per_cluster-Parameter, stattdessen `scoring_run_id`: der Client übergibt die
    id des ScoringRun, dessen Stand er beim Anzeigen von last_scoring_run gesehen hat, damit
    der Server einen zwischenzeitlichen Re-Scan/Re-Scoring als 409 ablehnen kann, statt auf
    einem veralteten cluster_key-Stand weiterzuarbeiten.

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
    # Die Fortschrittsanzeige liest AUSSCHLIESSLICH `last_criterion_scoring_run.cloud_phases`,
    # also den Fremdschlüssel DES LAUFS - niemals "die jüngste Remote-Zeile des Projekts".
    #
    # Globales Feature-Flag, nicht projektspezifisch - hier statt in einem eigenen Endpunkt
    # exponiert, damit das Frontend-Verfügbarkeitsgate proaktiv aus den ohnehin geladenen
    # Projektdaten dieser Seite ableitbar ist, statt erst nach einem fehlgeschlagenen 403.
    category_selection_enabled: bool
    # Projektweiter Einwilligungs-Schalter für produktive Cloud-Vision-Datenflüsse; er gated
    # BEIDE Cloud-Anteile. Hier statt in einem eigenen GET exponiert, damit ProjectSettingsPage
    # den Zustand aus den bereits geladenen Projektdaten lesen kann.
    cloud_vision_detection_enabled: bool
    cloud_vision_consent_at: datetime | None
    # ZWEI Felder, nicht eines: `selection_target` ist die EINGESTELLTE Zahl oder `null` ("nicht
    # selbst eingestellt"), `effective_selection_target` die wirksame. Das Frontend leitet die
    # zweite nicht selbst ab - die Ableitung lebt an genau einer Stelle
    # (`selection.py::effective_target`), und ein Feld, das beide Zustände mischte, machte "vom
    # System vorbelegt" von "selbst eingestellt" ununterscheidbar.
    selection_target: int | None
    effective_selection_target: int
    # Bestandszahlen des Projekts (ADR 0103): fuer die ganze Liste in EINER gruppierten Abfrage zu
    # haben, in konstanter Antwortgroesse, und damit auch im Zwei-Sekunden-Takt von
    # `useProjectQuery` tragbar. Die Kennzahlen von `GET /projects/{id}/stats` erfuellen das nicht
    # (zwei `os.stat` je Foto) und bleiben deshalb dort.
    #
    # `photo_count == 0` ist eine Aussage, die beiden `null` sind ihre Abwesenheit - das Frontend
    # unterscheidet sichtbar zwischen "0 Fotos" und dem Strich "keine Angabe".
    photo_count: int
    taken_at_earliest: datetime | None
    taken_at_latest: datetime | None


# SICHERHEIT (S3) - Obergrenze des Richtwerts, im Muster von `api/photos.py::MAX_QUERY_POSITION`:
# ein Pydantic-`int` ist unbeschraenkt, der Wert wird in eine INTEGER-Spalte geschrieben und geht
# in `⌈0,25·T⌉`/`⌈T/m⌉`/`T − m`; jenseits von 2^63 ergibt das unter SQLite einen `OverflowError`
# und damit eine 500 statt einer 422.
#
# AUSDRUECKLICH NICHT die Schranke gegen Ueberlast: Antwortgroesse und Rechenzeit saettigen beim
# auswahlfaehigen Bestand, nicht am Richtwert. Die Ueberlastschranke liegt in der
# Komplexitaetsklasse des Verfahrens (`selection.py::_assign_event`).
MAX_SELECTION_TARGET = 1_000_000

_SelectionTargetValue = Annotated[int, Field(ge=1, le=MAX_SELECTION_TARGET)]


class SelectionTargetUpdate(BaseModel):
    """`null` ist ein eigener ZULAESSIGER Wert - der Rueckweg zur Vorbelegung - und von "Feld
    fehlt" zu unterscheiden. Deshalb ohne Vorgabewert: ein fehlendes Feld ist eine `422`, kein
    stilles Zuruecksetzen.

    `0` ist kein Weg zur Vorbelegung (`ge=1`); zwei Wege zum selben Zustand waeren zwei Aussagen
    an einer Stelle."""

    target: _SelectionTargetValue | None


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


async def _cloud_phase_summaries(
    session: AsyncSession, run: CriterionScoringRun
) -> list[CloudPhaseSummaryOut]:
    """Die Cloud-Teilschritte GENAU DIESES Durchlaufs, in Ausführungsreihenfolge.

    Der Remote-Anteil kommt ueber den Fremdschluessel (`session.get`, ein
    Primaerschluessel-Zugriff), der Landmark-Anteil steht an der Lauf-Zeile selbst. Ein Eintrag
    entsteht, SOBALD die Phase betreten wurde: die Oberflaeche soll den Teilschritt sehen,
    WAEHREND er Geld ausgibt, nicht erst danach."""
    phases: list[CloudPhaseSummaryOut] = []

    if run.remote_category_classification_run_id is not None:
        remote_run = await session.get(
            RemoteCategoryClassificationRun, run.remote_category_classification_run_id
        )
        if remote_run is not None:
            phases.append(
                CloudPhaseSummaryOut(
                    purpose=CloudVisionPhase.REMOTE_CATEGORY,
                    photos_total=remote_run.photos_total,
                    photos_processed=remote_run.photos_processed,
                    failed_calls=remote_run.failed_calls,
                    responses_used=remote_run.api_calls,
                    input_tokens=remote_run.input_tokens,
                    output_tokens=remote_run.output_tokens,
                    cost_usd=remote_run.cost_usd,
                    model=remote_run.model,
                    provider=_provider_of(remote_run.model),
                )
            )

    # `landmark_photos_total is not None` ist der MARKER, ob es diesen Teilschritt in diesem Lauf
    # gab - `0` heisst "fand statt, ohne Kandidaten", `NULL` heisst "fand nicht statt". Deshalb
    # `is not None` und nicht truthy.
    if run.landmark_photos_total is not None:
        phases.append(
            CloudPhaseSummaryOut(
                purpose=CloudVisionPhase.LANDMARK,
                photos_total=run.landmark_photos_total,
                photos_processed=run.landmark_photos_processed,
                failed_calls=run.landmark_failed_calls,
                responses_used=run.landmark_api_calls,
                input_tokens=run.landmark_input_tokens,
                output_tokens=run.landmark_output_tokens,
                cost_usd=run.landmark_cost_usd,
                model=run.landmark_model,
                provider=_provider_of(run.landmark_model),
            )
        )

    return phases


def _provider_of(model: str | None) -> str | None:
    """Der Anbieter eines gespeicherten Modells - `None`, wenn kein Modell erfasst ist ODER es
    nicht (mehr) in der Registry steht. NIE `settings.landmark_provider`: die aktuelle
    Betriebseinstellung beschriebe sonst einen vergangenen Lauf, und eine historische
    Lauf-Antwort koennte die heutige Konfiguration preisgeben."""
    if model is None:
        return None
    return provider_for_vision_model(model)


def _cloud_cost_total(phases: list[CloudPhaseSummaryOut]) -> float | None:
    """Die Gesamtkosten des Durchlaufs - `None`, sobald EIN beteiligter Anteil `None` ist, und
    `None` ohne jeden Cloud-Teilschritt.

    Die Regel "unvollstaendig != 0" liegt damit serverseitig an EINER Stelle, wie bei
    `CostOut.total_usd` der Statistikseite. Nie ein `sum(... or 0)`: das tarnte einen Lauf mit
    unbekanntem Preisanteil als billiger, als er war."""
    if not phases:
        return None
    if any(phase.cost_usd is None for phase in phases):
        return None
    return sum(phase.cost_usd for phase in phases if phase.cost_usd is not None)


def _phase_progress(
    run: CriterionScoringRun, phases: list[CloudPhaseSummaryOut]
) -> tuple[int | None, int | None]:
    """Der Zaehler-/Nenner-Stand GENAU DES laufenden Teilschritts.

    Die Zuordnung "welcher Zaehler gehoert zu welchem Teilschritt" steht SERVERSEITIG; das
    Frontend bildet sie nicht nach (ADR 0116 Punkt 2). Die Landmark-Zahlen kommen aus der bereits
    gebauten `phases`-Liste und der Remote-Stand aus deren Eintrag - KEIN zusaetzlicher
    Datenbankzugriff je Projekt, der im Zwei-Sekunden-Takt des Pollings anfiele (ADR 0103
    Punkt 1).

    `ranking` liefert `(None, None)` und damit immer `null`: Der Teilschritt arbeitet ueber
    Partitionen und hat keine gezaehlte Menge (ADR 0116 Punkt 5).
    """
    if run.phase is ClassificationPhase.CRITERIA:
        return run.photos_processed, run.photos_total
    purpose = _CLOUD_PURPOSE_BY_PHASE.get(run.phase) if run.phase is not None else None
    if purpose is None:
        return None, None
    phase = next((entry for entry in phases if entry.purpose is purpose), None)
    if phase is None:
        return None, None
    return phase.photos_processed, phase.photos_total


# Die beiden Teilschritte, deren Fortschritt an einem Cloud-Eintrag haengt. `criteria` steht
# bewusst nicht hier (es zaehlt an der Lauf-Zeile), `ranking` hat gar keine Menge.
_CLOUD_PURPOSE_BY_PHASE: dict[ClassificationPhase, CloudVisionPhase] = {
    ClassificationPhase.REMOTE_CATEGORIES: CloudVisionPhase.REMOTE_CATEGORY,
    ClassificationPhase.LANDMARK: CloudVisionPhase.LANDMARK,
}


def _phase_remaining_seconds(
    run: CriterionScoringRun, phases: list[CloudPhaseSummaryOut]
) -> float | None:
    """Die Restdauer des laufenden Teilschritts, oder `null`.

    Die Statuspruefung steht VOR der Rechnung, und sie prueft NICHT allein `phase`: Der Zustand
    "beendet, aber `phase` nicht zurueckgesetzt" existiert am Bestand (Altzeilen). Ohne sie
    zaehlte eine laengst beendete Zeile weiter hoch, ohne dass etwas fehlschluege (AK8)."""
    if run.status is not ScanStatus.RUNNING or run.phase is None:
        return None
    processed, total = _phase_progress(run, phases)
    return remaining_seconds(
        phase_started_at=run.phase_started_at,
        now=now_utc(),
        processed=processed,
        total=total,
    )


async def _criterion_scoring_run_summary(
    session: AsyncSession, run: CriterionScoringRun
) -> CriterionScoringRunSummary:
    """FELDWEISE konstruiert, nie ueber `model_validate(run)`: `cloud_phases`,
    `cloud_cost_total_usd` und `phase_remaining_seconds` entstehen nicht an der Zeile, sondern aus
    ihr - eine nachtraegliche Zuweisung an ein validiertes Modell umginge die Validierung genau
    dieser Felder."""
    phases = await _cloud_phase_summaries(session, run)
    return CriterionScoringRunSummary(
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        photos_total=run.photos_total,
        photos_processed=run.photos_processed,
        error_message=run.error_message,
        phase=run.phase,
        cloud_requested=run.cloud_requested,
        cloud_error_message=run.cloud_error_message,
        estimated_cost_usd=run.estimated_cost_usd,
        cloud_phases=phases,
        cloud_cost_total_usd=_cloud_cost_total(phases),
        phase_remaining_seconds=_phase_remaining_seconds(run, phases),
    )


async def _has_successful_classification_run(session: AsyncSession, project_id: int) -> bool:
    """Gab es in DIESEM Projekt schon einen erfolgreich abgeschlossenen Klassifizierungslauf?

    Das Merkmal ist eine vorhandene Zeile, kein neuer Zustand: `status = success` belegt, dass
    Kriterien-Werte geschrieben wurden - und nur aus denen laesst sich der Landmark-Anteil der
    Schaetzung ableiten. Ein laufender oder fehlgeschlagener Lauf belegt das nicht."""
    result = await session.execute(
        select(
            exists().where(
                CriterionScoringRun.project_id == project_id,
                CriterionScoringRun.status == ScanStatus.SUCCESS,
            )
        )
    )
    return bool(result.scalar_one())


def _estimate_part(
    candidate_count: int | None, price_per_image_usd: float | None
) -> ClassificationEstimatePartOut:
    """Ein Anteil der Vorab-Schaetzung. Die ZWEIGREIHENFOLGE ist die Aussage und dieselbe wie
    für die Gesamtsumme, ergänzt um einen dritten Fall:

    1. Anteil unbekannt (`candidate_count is None`) -> Betrag `None`. Ueber eine unbekannte Menge
       laesst sich nichts sagen, auch nicht mit einem bekannten Preis.
    2. Null Kandidaten -> `0.0`. Der Betrag ist hier BEKANNT (es faellt nichts an, weil nichts
       verarbeitet wird), selbst wenn der Preis je Bild unbekannt ist.
    3. Kein Preis hinterlegt -> `None`, nie ein stilles `0.0`.
    """
    if candidate_count is None:
        return ClassificationEstimatePartOut(candidate_count=None, estimated_cost_usd=None)
    if candidate_count == 0:
        return ClassificationEstimatePartOut(candidate_count=0, estimated_cost_usd=0.0)
    if price_per_image_usd is None:
        return ClassificationEstimatePartOut(
            candidate_count=candidate_count, estimated_cost_usd=None
        )
    return ClassificationEstimatePartOut(
        candidate_count=candidate_count,
        estimated_cost_usd=candidate_count * price_per_image_usd,
    )


async def _count_remote_category_candidates(session: AsyncSession, project_id: int) -> int:
    """Ermittelt über dieselbe Kandidaten-Selektion wie der tatsächliche Lauf
    (worker.py::select_remote_category_candidates), als eigenstaendige kleine Query HIER
    dupliziert: die API-Schicht (reine HTTP-/Validierungs-/Lese-Zustaendigkeit) importiert
    worker.py nicht, sondern loest Jobs ausschliesslich ueber den stringbasierten JobEnqueuer
    aus. `api/photos.py` ist die eine bewusste Ausnahme davon.

    Ein einzelnes `COUNT` mit `NOT EXISTS`, komplett serverseitig ausgewertet - keine Zeile
    verlaesst die Datenbank, auch nicht bei einem grossen Projekt.

    SICHERHEITSAUFLAGE S15/S7: eine bewusste DUPLIKATION derselben Bedingung, und deshalb aendern
    sich beide Stellen in derselben PR. Das Kriterium ist ZUSAMMENGESETZT - eine Kopfzeile mit
    `source='cloud'` UND eine Albumtauglichkeitszeile; nicht das bloße Vorhandensein einer
    Kopfzeile (der Kriterien-Lauf schreibt lokale). Eine Schaetzung, die eine andere Menge zaehlt
    als der Lauf sendet, ist eine falsche Grundlage fuer die Freigabe einer kostenpflichtigen
    Aktion.

    Die Negation der KONJUNKTION wird per De Morgan zur DISJUNKTION: Kandidat ist, wem eines von
    beiden fehlt. Eine falsch geklammerte Negation (`~(a & b)` als `~a & ~b` gelesen) zaehlt still
    eine andere Menge - der Test prueft deshalb MENGENGLEICHHEIT gegen den Worker-Pfad ueber
    demselben Datenbestand, nicht zwei getrennt hingeschriebene Erwartungswerte."""
    cloud_assessed = exists().where(
        PhotoMotifAssessment.photo_id == Photo.id,
        PhotoMotifAssessment.source == MotifAssessmentSource.CLOUD,
    )
    album_rated = exists().where(PhotoAlbumSuitability.photo_id == Photo.id)
    result = await session.execute(
        select(func.count())
        .select_from(Photo)
        .join(PhotoScore, PhotoScore.photo_id == Photo.id)
        .where(
            Photo.project_id == project_id,
            # SICHERHEIT (S1 von Spec 0374): DASSELBE Praedikat wie im Lauf. Es folgt der Auswahl
            # nicht von selbst - dies ist eine eigene Anweisung, und sie muss dieselbe Menge
            # zaehlen, die der Lauf sendet.
            survives_ausschuss(),
            or_(~cloud_assessed, ~album_rated),
        )
    )
    return result.scalar_one()


async def _count_landmark_candidates(session: AsyncSession, project_id: int) -> int:
    """Der Landmark-Anteil der Kostenschätzung.

    Zaehlt Ausschuss-Ueberlebende, deren BEREITS GESPEICHERTE Kriterien-Werte
    `criteria.py::is_landmark_candidate` erfuellen und die noch keine `landmark`-Zeile haben -
    dieselbe reine Schwellenwert-Funktion, die auch der Live-Lauf ueber
    worker.py::_select_landmark_candidates nutzt (kein zweiter, auseinanderlaufender Grenzwert).

    STRUKTURELL EINE SCHAETZUNG, keine Vorausberechnung: die Landmark-Kandidaten des kommenden
    Laufs ergeben sich aus Kriterien-Werten, die genau dieser Lauf erst neu berechnet. Vor dem
    allerersten Lauf eines Projekts liegen gar keine Vorwerte vor und die Zahl ist 0; die
    Oberflaeche weist sie als Schaetzung aus.

    Die Schwellenwert-Pruefung laeuft in Python, nie als SQL-Ausdruck: `is_landmark_candidate`
    ist die geteilte Quelle der Wahrheit, eine SQL-Nachbildung der Schwellenwerte waere die
    zweite, auseinanderlaufende Stelle. Geladen werden nur die beiden relevanten
    Kriterien-Zeilen je Foto, nicht die vollen Fotos."""
    already_scored = (
        select(PhotoCriterionScore.photo_id)
        .join(Photo, Photo.id == PhotoCriterionScore.photo_id)
        .where(Photo.project_id == project_id, PhotoCriterionScore.criterion_key == "landmark")
    )
    rows = (
        await session.execute(
            select(
                PhotoCriterionScore.photo_id,
                PhotoCriterionScore.criterion_key,
                PhotoCriterionScore.value,
            )
            .join(Photo, Photo.id == PhotoCriterionScore.photo_id)
            .join(PhotoScore, PhotoScore.photo_id == Photo.id)
            .where(
                Photo.project_id == project_id,
                # SICHERHEIT (S1 von Spec 0374): dieselbe Begruendung wie eine Funktion weiter
                # oben. Der Sehenswuerdigkeits-Teilschritt wird vom Kriterien-Lauf gespeist, und
                # dessen Fotoauswahl traegt dasselbe Praedikat.
                survives_ausschuss(),
                PhotoCriterionScore.criterion_key.in_(LANDMARK_CANDIDATE_CRITERION_KEYS),
                PhotoCriterionScore.photo_id.not_in(already_scored),
            )
        )
    ).all()

    values_by_photo: dict[int, dict[str, float]] = {}
    for photo_id, criterion_key, value in rows:
        values_by_photo.setdefault(photo_id, {})[criterion_key] = value
    return sum(1 for values in values_by_photo.values() if is_landmark_candidate(values))


async def _to_project_out(
    session: AsyncSession, project: Project, aggregate: PhotoAggregate
) -> ProjectOut:
    """Das Aggregat kommt als PARAMETER herein, statt hier je Projekt nachgeladen zu werden:
    `list_projects` laedt es einmal fuer alle Projekte, die Einzeloperationen fuer genau eines.
    Ein Nachladen an dieser Stelle waere die Abfrage je Projekt, die ADR 0103 ausschliesst."""
    scan_run = await _latest_scan_run(session, project.id)
    scoring_run = await _latest_scoring_run(session, project.id)
    criterion_scoring_run = await _latest_criterion_scoring_run(session, project.id)
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
            await _criterion_scoring_run_summary(session, criterion_scoring_run)
            if criterion_scoring_run is not None
            else None
        ),
        category_selection_enabled=settings.category_selection_enabled,
        cloud_vision_detection_enabled=project.cloud_vision_detection_enabled,
        cloud_vision_consent_at=project.cloud_vision_consent_at,
        selection_target=project.selection_target,
        # DIESELBE Zahl, die die Antwort als `photo_count` ausweist - nicht eine zweite Zaehlung
        # daneben, die mit ihr auseinanderlaufen koennte.
        effective_selection_target=effective_target(
            project.selection_target, aggregate.photo_count
        ),
        photo_count=aggregate.photo_count,
        taken_at_earliest=aggregate.taken_at_earliest,
        taken_at_latest=aggregate.taken_at_latest,
    )


async def _to_single_project_out(session: AsyncSession, project: Project) -> ProjectOut:
    """Eine Antwort ueber GENAU EIN Projekt - derselbe Stapel-Helfer mit einelementiger Liste."""
    return await _to_project_out(
        session, project, await photo_aggregate_for_project(session, project.id)
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
    return await _to_single_project_out(session, project)


@router.get("", response_model=list[ProjectOut])
async def list_projects(session: AsyncSession = Depends(get_session)) -> list[ProjectOut]:
    """Die Bestandszahlen werden EINMAL fuer alle Projekte geladen, nicht je Projekt: die Zahl der
    Abfragen mit `min(photos.taken_at)` ist genau eine, unabhaengig von der Projektzahl."""
    projects = list((await session.execute(select(Project).order_by(Project.created_at))).scalars())
    aggregates = await photo_aggregates_by_project(session, [project.id for project in projects])
    return [
        await _to_project_out(session, project, aggregates.get(project.id, EMPTY_PHOTO_AGGREGATE))
        for project in projects
    ]


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: int, session: AsyncSession = Depends(get_session)) -> ProjectOut:
    project = await _get_project_or_404(project_id, session)
    return await _to_single_project_out(session, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    payload: ProjectDelete,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    """Löscht ein Projekt und alle PhotoSort-eigenen Daten daran. Die Original-Fotos auf
    OpenCloud bleiben unangetastet - PhotoSort greift dort ausschließlich lesend zu.

    Reihenfolge der Prüfungen: `404` -> `409` -> `400` -> Foto-Schluessel lesen ->
    Mengenloeschung + genau ein `commit()` -> best-effort Cache-Cleanup -> `204`. Die
    Foto-Schluessel muessen VOR der Zeilenloeschung gelesen werden; danach gibt es die Zeilen
    nicht mehr, aus denen sich die Cache-Pfade berechnen liessen.

    KEIN Owner-Check: jeder eingeloggte Nutzer darf jedes Projekt loeschen; Auth haengt am
    router-weiten `dependencies=[Depends(get_current_user)]`. `user` steht hier trotzdem als
    Parameter, weil die Erfolgs-Logzeile die `user.id` nennt - der zweite
    `Depends(get_current_user)` wird von FastAPI im selben Request zwischengespeichert, ist also
    kein zweiter Aufruf.
    """
    project = await _get_project_or_404(project_id, session)

    # Ein aktiver Lauf schreibt in genau die Zeilen, die gleich verschwinden. Alle VIER Lauftypen
    # - der Remote-Klassifizierungslauf gehoert zwingend dazu, er schreibt nach
    # photo_category_classifications/photo_fine_labels/fine_labels. Geprueft wird jeweils nur der
    # NEUESTE Lauf: ein nicht mehr aktueller RUNNING-Altlauf darf nicht dauerhaft blockieren (ein
    # haengengebliebener wird ohnehin vom Watchdog auf FAILED gesetzt).
    latest_runs = (
        await _latest_scan_run(session, project_id),
        await _latest_scoring_run(session, project_id),
        await _latest_criterion_scoring_run(session, project_id),
        await _latest_remote_category_classification_run(session, project_id),
    )
    if any(run is not None and run.status == ScanStatus.RUNNING for run in latest_runs):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fuer dieses Projekt laeuft gerade ein Vorgang. Warte, bis er fertig ist, "
            "und versuche es dann erneut.",
        )

    # `strip()` NUR serverseitig (die Oberflaeche vergleicht exakt): ein per curl
    # abgesetzter Name mit Zeilenumbruch soll nicht an einer unsichtbaren Kleinigkeit scheitern,
    # waehrend die getippte Bestaetigung ihre volle Reibung behaelt. Gross-/Kleinschreibung zaehlt.
    if payload.confirm_name.strip() != project.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Der eingegebene Name stimmt nicht mit dem Projektnamen ueberein.",
        )

    cache_keys = await collect_photo_cache_keys(session, [project_id])
    try:
        deleted_rows = await delete_projects(session, [project_id])
        await session.commit()
    except IntegrityError as exc:
        # Unter echtem Postgres moeglich, wenn ein Lauf nebenlaeufig in die gerade geloeschten
        # Zeilen schreibt. Das ist kein Serverfehler, sondern derselbe "jetzt nicht"-Fall wie der
        # 409-Waechter oben - und die Datenbankmeldung gehoert nicht in die Antwort.
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Das Projekt konnte nicht geloescht werden, weil gleichzeitig darauf "
            "geschrieben wurde. Versuche es erneut.",
        ) from exc

    # Erst NACH dem Commit und best-effort: Dateisystem-Operationen sind nicht Teil der
    # Transaktion, ein Dateifehler darf die verlangte Datenloeschung nicht nachtraeglich
    # zunichtemachen. Ueber to_thread, weil das bei mehreren tausend Fotos ebenso viele
    # unlink-Aufrufe sind, die die Event-Loop nicht blockieren duerfen.
    #
    # Der breite `except` ist die zweite Hälfte derselben Zusage: `delete_cached_variants` faengt
    # nur `OSError` JE DATEI ab. Alles darueber hinaus schluege sonst als `500` bis zum Client
    # durch, obwohl die Loeschung bereits committet ist und der Client sie folglich als
    # gescheitert laese. Der Fehlertext enthaelt den absoluten Cache-Pfad, also interne
    # Deployment-Struktur: er gehoert ins Log, nie in die Antwort.
    try:
        await asyncio.to_thread(delete_cached_variants, Path(settings.photo_cache_dir), cache_keys)
    except Exception:
        logger.warning(
            "Cache-Cleanup nach dem Loeschen von Projekt %s fehlgeschlagen - die Datenloeschung "
            "ist davon unberuehrt.",
            project_id,
            exc_info=True,
        )

    # SICHERHEIT: die einzige Spur eines vernichtenden Vorgangs. OHNE Projektnamen und ohne
    # Audit-Log-Feature: keine Tabelle, keine Oberfläche, keine Abfrage.
    logger.info(
        "Projekt geloescht: user_id=%s project_id=%s geloeschte_zeilen=%s",
        user.id,
        project_id,
        deleted_rows,
    )


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
    # Analog trigger_scan oben: derselbe router-weite
    # dependencies=[Depends(get_current_user)]-Torwaechter, keine Rollenunterscheidung zwischen
    # den beiden bekannten Nutzern.
    await _get_project_or_404(project_id, session)
    await enqueuer.enqueue_job("score_project", project_id)
    return {"status": "queued"}


@router.post("/{project_id}/confirm-ausschuss-gate", status_code=status.HTTP_200_OK)
async def confirm_ausschuss_gate(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Abschluss des Ausschuss-Schritts: uebernimmt ALLE offenen Vorschlaege und gibt den
    naechsten Schritt frei.

    `409` ohne erfolgreichen `ScoringRun`. Mit erfolgreichem Lauf schreibt der Aufruf in EINER
    Transaktion fuer jede Aufnahme mit `duplicates.py::has_open_suggestion` die Zeile `discard` und
    setzt danach `gate_confirmed_at`, falls es leer ist (Auflage S3): Ein halb geschriebener Bestand
    waere eine willkuerliche Teilmenge in der Menge, die den Homeserver verlaesst, und ein gesetzter
    Zeitstempel ohne die Uebernahme oeffnete den naechsten Schritt ohne sie.

    Ein LEERER offener Bestand ist kein Fehler und kein Nichtstun: Auch dann setzt der Aufruf den
    Zeitstempel (siehe die Bedingung unten). Er ist neben dem Autoset des Laufs der EINZIGE Setzer -
    ein Nutzer, der zuletzt alle Vorschlaege einzeln entschieden hat (AK6), stuende sonst ohne
    Abschluss-Aktion fest und der naechste Schritt bliebe dauerhaft gesperrt (M1, AK13).

    SICHERHEIT (S1): Die Menge bestimmt der SERVER, projektweit und in DERSELBEN Anweisung wie die
    Projektbindung - ein Aufruf ohne Body schriebe sonst `discard` ueber alle Projekte der Instanz.
    `has_open_suggestion` traegt selbst keine Projektbedingung; sie kommt allein aus dem Join auf
    `Photo`.

    SICHERHEIT (S2): Der Aufruf bleibt bodyfrei. Eine mitgeschickte Id-Liste wird nie gelesen. Ein
    Massen-`keep` gibt es nicht: Nur `discard` verkleinert den abfliessenden Bestand (ADR 0104
    Punkt 3, fail-closed) - die einzige Richtung, die ihn vergroesserte, waere zugleich ein
    Massen-Schreibweg auf beliebige Fotos.

    SICHERHEIT (S4): Bestehende Entscheidungszeilen bleiben unangetastet, und zwar durch die
    Auswahlbedingung statt durch Nachfilterung: Wer eine Zeile traegt, ist kein offener Vorschlag. Ein
    `discard` auf eine manuell behaltene Aufnahme waere deren stille Ruecknahme. Deshalb auch KEIN
    `DELETE` vor dem Schreiben - anders als beim Einzel- und Gruppenweg wird hier nie ueberschrieben.

    Wiederholter Aufruf ist idempotent (kein Fehler, kein zweiter Effekt, der Zeitstempel wird nie
    ueberschrieben); nach einem neuen Lauf schreibt er genau die dann offenen. Ein gleichzeitiger
    Einzel-Schreibvorgang auf dieselbe Aufnahme wird `409`, nie `500`: Der Primaerschluessel ist
    `photo_id`, und der `flush` VOR dem `commit` holt den Fehler an eine Stelle, an der er sich
    uebersetzen laesst. Projektweit, nicht personenbezogen: kein user_id-Bezug."""
    await _get_project_or_404(project_id, session)

    latest_scoring_run = await _latest_scoring_run(session, project_id)
    if latest_scoring_run is None or latest_scoring_run.status != ScanStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fuehre zuerst die Ausschuss-Erkennung erfolgreich aus.",
        )

    # EINE Anweisung, zwei UND-Glieder: die Projektbindung und der offene Vorschlag. Stuende die
    # Projektbedingung in einer zweiten Anweisung daneben, waere sie in einer Auswahl ohne sie
    # wirkungslos - und der Schreibweg traefe jeden offenen Vorschlag der ganzen Instanz.
    offene_ids = list(
        (
            await session.execute(
                select(Photo.id)
                .join(PhotoScore, PhotoScore.photo_id == Photo.id)
                .where(Photo.project_id == project_id, has_open_suggestion())
            )
        ).scalars()
    )

    if offene_ids:
        session.add_all(
            [
                PhotoDuplicateDecision(photo_id=photo_id, decision=DuplicateDecision.DISCARD)
                for photo_id in offene_ids
            ]
        )
        try:
            await session.flush()
        except IntegrityError:
            # Das schmale Fenster der Auflage S3: Die andere Sitzung hat zwischen unserer Auswahl
            # und unserem `INSERT` dieselbe Aufnahme entschieden. Der Primaerschluessel wirft; der
            # Rueckzug umfasst AUCH den Zeitstempel unten, der noch gar nicht gesetzt ist.
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Die Entscheidung zu dieser Duplikat-Gruppe wurde gerade veraendert. "
                    "Bitte erneut versuchen."
                ),
            ) from None

    if latest_scoring_run.gate_confirmed_at is None:
        latest_scoring_run.gate_confirmed_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()
    elif offene_ids:
        await session.commit()

    return {"status": "confirmed"}


@router.post("/{project_id}/classify", status_code=status.HTTP_202_ACCEPTED)
async def trigger_classify(
    project_id: int,
    payload: ClassifyRequest,
    session: AsyncSession = Depends(get_session),
    enqueuer: JobEnqueuer = Depends(get_job_enqueuer),
) -> dict[str, str]:
    """Der EINE Auslöser der Klassifizierung. Der ausgelöste Job verkettet beide Cloud-Phasen
    mit der Kriterien- und der Rangfolge-Phase (worker.py::run_classification).

    Vorbedingungen: `403` wenn das Feature-Flag aus ist, `404` bei unbekanntem Projekt, `409`
    ohne erfolgreichen `ScoringRun`, `409` ohne bestätigtes Gate, `409` bei veraltetem
    `scoring_run_id`-Bezug (Re-Scan/Re-Scoring während der Kuratierung). `403`, wenn
    `use_cloud=true` ohne projektweite Einwilligung angefragt wird - ein Client, der
    Cloud-Verarbeitung ohne Einwilligung anfordert, soll das erfahren, statt still auf "lokal"
    herunterzufallen. Diese Pruefung ist die sprechende Frueh-Rueckmeldung, NICHT das
    Sicherheitsnetz: das eigentliche Gate ist die Konjunktion
    `use_cloud and project.cloud_vision_detection_enabled`, ausgewertet im Worker unmittelbar vor
    der Client-Konstruktion.

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

    # Die Schätzung, mit der dieser Lauf startet, wird HIER serverseitig berechnet und als
    # Job-Argument durchgereicht - mit denselben Helfern, die `GET .../classify/estimate`
    # benutzt: kein neuer Rechenweg, keine dritte Kopie der Kandidaten-Zaehlung im Worker.
    #
    # SICHERHEIT: die Zahl entsteht ausschliesslich aus Datenbankzaehlungen und der validierten
    # Betriebseinstellung. `ClassifyRequest` traegt bewusst KEIN Betrags-, Kosten-, Modell- oder
    # Anbieterfeld - ein vom Client geliefertes Geldfeld wanderte sonst ungeprueft in die
    # Buchfuehrung. Bei `use_cloud=false` wird `None` gereicht (und `NULL` gespeichert), nicht
    # `0.0`: ein Lauf ohne Cloud hat keine Kostenschaetzung.
    estimated_cost_usd: float | None = None
    if payload.use_cloud:
        estimated_cost_usd = (
            await _build_classification_estimate(session, project_id)
        ).estimated_cost_usd

    await enqueuer.enqueue_job(
        "classify", project_id, payload.scoring_run_id, payload.use_cloud, estimated_cost_usd
    )
    return {"status": "queued"}


@router.put("/{project_id}/cloud-vision-consent", response_model=CloudVisionConsentOut)
async def set_cloud_vision_consent(
    project_id: int,
    payload: CloudVisionConsentUpdate,
    session: AsyncSession = Depends(get_session),
) -> CloudVisionConsentOut:
    """Setzt die projektweite Cloud-Vision-Einwilligung.

    `PUT` statt `POST`, da ein Zustand gesetzt und kein Job ausgelöst wird. SICHERHEIT: hängt am
    router-weiten Auth-Torwächter, ein zusätzlicher `Depends(get_current_user)` ist hier nicht
    nötig. Setzt synchron `cloud_vision_consent_at` (Zeitstempel bei Aktivierung, `NULL` bei
    Deaktivierung) - kein "nur beim ersten Mal"-Sonderfall, ein wiederholtes Aktivieren
    aktualisiert den Zeitstempel jedes Mal erneut.

    Es ist DER EINE Schalter für beide Cloud-Anteile, kein zweiter, granularerer daneben.
    """
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


async def _reject_while_a_criterion_run_is_active(session: AsyncSession, project_id: int) -> None:
    """`409`, solange der Kriterien-Lauf dieses Projekts laeuft.

    ENGER als `api/cameras.py::_reject_while_a_run_is_active`, das auch den Scan erfasst: nur
    dieser Lauftyp schreibt `selection_position`, der Scan nicht.

    Der laufende Lauf liest den Richtwert am Ende seiner Phase `RANKING`. Ohne diesen Waechter
    schreibt der Endpunkt den neuen Wert, waehrend der Lauf noch mit dem alten rechnet - Ergebnis
    ist ein Vorschlag nach altem Richtwert unter einer Oberflaeche, die den neuen anzeigt. Die
    Abweichung heilt erst beim naechsten Ausloeser und ist bis dahin nirgends als Fehler sichtbar.

    Geprueft wird nur der NEUESTE Lauf (Muster `delete_project`), damit ein haengengebliebener
    Altlauf nicht dauerhaft blockiert - ein solcher wird ohnehin vom Watchdog auf FAILED
    gesetzt."""
    latest = (
        (
            await session.execute(
                select(CriterionScoringRun.status)
                .where(CriterionScoringRun.project_id == project_id)
                .order_by(CriterionScoringRun.started_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if latest == ScanStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Fuer dieses Projekt laeuft gerade eine Kriterien-Bewertung. Der Richtwert "
            "kann danach gesetzt werden.",
        )


@router.put("/{project_id}/selection-target", response_model=ProjectOut)
async def set_selection_target(
    project_id: int,
    payload: SelectionTargetUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    """Setzt den Richtwert des Auswahlvorschlags und rechnet den Vorschlag daraufhin neu.

    `PUT` statt `POST`, da ein Zustand gesetzt und kein Job ausgelöst wird. `target: null` setzt
    auf die Vorbelegung zurück - die Vorbelegung selbst wird nie in die Spalte geschrieben.

    Der Neuaufbau läuft SYNCHRON in derselben Transaktion (Muster
    `api/cameras.py::set_camera_time_offset` → `rebuild_run_grouping`): er rechnet ausschließlich
    aus persistierten Zeilen, ohne Cloud-Aufruf und ohne Bildverarbeitung. Events und Rangzeilen
    bleiben unangetastet.

    Reihenfolge der Prüfungen: `404` → `409` → schreiben. SICHERHEIT: der Endpunkt hängt am
    router-weiten Auth-Torwächter; weder `target` noch ein Query-Parameter steuert je eine Lauf-,
    Event- oder Foto-Id bei - die Projektbindung kommt ausschließlich aus dem Pfadparameter."""
    project = await _get_project_or_404(project_id, session)
    await _reject_while_a_criterion_run_is_active(session, project_id)

    project.selection_target = payload.target
    await rebuild_run_selection(session, project_id)
    await session.commit()
    await session.refresh(project)

    return await _to_single_project_out(session, project)


@router.get("/{project_id}/classify/estimate", response_model=ClassificationEstimateOut)
async def estimate_classification(
    project_id: int, session: AsyncSession = Depends(get_session)
) -> ClassificationEstimateOut:
    """Die Vorab-Kostenschätzung des Klassifizierungslaufs, über BEIDE Cloud-Anteile - die
    Checkbox am Auslöser gibt beide frei.

    Funktioniert UNABHÄNGIG vom Consent-Schalter (auch bei deaktiviertem Consent 200, kein 403) -
    der Nutzer soll die Kosten VOR einer Consent-Entscheidung sehen können. `candidate_count=0`
    liefert 200 mit estimated_cost_usd=0.0, kein Sonderfall.

    Die beiden Anteile werden getrennt ausgewiesen, und "nicht schätzbar" ist ein eigener Wert
    (`null`) statt einer `0`."""
    await _get_project_or_404(project_id, session)

    return await _build_classification_estimate(session, project_id)


async def _build_classification_estimate(
    session: AsyncSession, project_id: int
) -> ClassificationEstimateOut:
    """Die Schaetzung selbst, ohne HTTP-Anteil - geteilt zwischen `GET .../classify/estimate` und
    `POST .../classify`.

    Genau EIN Rechenweg fuer die Zahl, die angezeigt und die am Lauf eingefroren wird: eine
    zweite Kopie liefe mit der ersten auseinander, und dann verglichen Bilanz und Vorschau zwei
    verschiedene Groessen miteinander. Der Ausloese-Endpunkt hat sein 404 zu diesem Zeitpunkt
    bereits selbst geworfen, deshalb keine zweite Projektpruefung hier."""
    remote_category_candidate_count = await _count_remote_category_candidates(session, project_id)
    # Der Landmark-Anteil ist NICHT SCHAETZBAR, solange im Projekt kein erfolgreich
    # abgeschlossener Klassifizierungslauf existiert - vor dem ersten Lauf gibt es keine
    # gespeicherten Kriterien-Werte, aus denen sich Kandidaten ableiten liessen, und
    # `_count_landmark_candidates` liefert dort strukturell `0`. Diese `0` als Tatsache
    # anzuzeigen behauptet Kostenfreiheit fuer einen Anteil, der gleich Geld kostet.
    #
    # Ein laufender oder fehlgeschlagener Durchlauf gilt ausdruecklich nicht als stattgefunden:
    # erst ein `success` belegt, dass Kriterien-Werte geschrieben wurden.
    landmark_candidate_count: int | None = None
    if await _has_successful_classification_run(session, project_id):
        landmark_candidate_count = await _count_landmark_candidates(session, project_id)
    provider = settings.landmark_provider
    # Die Schätzung hängt am tatsächlich EINGESTELLTEN Modell, nicht am Anbieter - ein
    # Modellwechsel kann sie damit nicht unbemerkt falsch machen.
    model = settings.resolved_landmark_model()
    price_per_image_usd = estimate_usd_per_image(model, provider)
    # Die Summe der BEKANNTEN Anteile - bei unbekanntem Landmark-Anteil ausdruecklich eine
    # UNTERE SCHRANKE. Ueber ein `is not None`, nie ueber ein `or 0`: die Regel "unbekannt ist
    # nicht null" gilt in diesem Modul durchgaengig.
    candidate_count = remote_category_candidate_count
    if landmark_candidate_count is not None:
        candidate_count += landmark_candidate_count
    return ClassificationEstimateOut(
        candidate_count=candidate_count,
        remote_categories=_estimate_part(remote_category_candidate_count, price_per_image_usd),
        landmark=_estimate_part(landmark_candidate_count, price_per_image_usd),
        provider=provider,
        model=model,
        price_per_image_usd=price_per_image_usd,
        # Reihenfolge der Zweige ist die Aussage: null Kandidaten zuerst. `null` heisst
        # "unbekannt" - bei null Kandidaten ist der Betrag aber bekannt, es faellt nichts an,
        # weil nichts verarbeitet wird. Der Preis JE BILD bleibt daneben korrekt `null`.
        # Andersherum haengt die Zusage des Docstrings ("candidate_count=0 liefert 0.0, kein
        # Sonderfall") unausgesprochen daran, dass ein Preis gepflegt ist.
        #
        # Kein neuer Rechenweg fuer die Gesamtsumme: dieselbe Multiplikation wie je Anteil, nur
        # ueber die Summe der bekannten Anteile, mit der Grobheit "ein Preis je Bild fuer beide
        # Cloud-Anteile".
        estimated_cost_usd=(
            0.0
            if candidate_count == 0
            else (None if price_per_image_usd is None else candidate_count * price_per_image_usd)
        ),
    )


class FineLabelCountOut(BaseModel):
    """Ein Feinlabel samt seiner Häufigkeit IN DIESEM PROJEKT.

    SICHERHEIT: `display_name` ist freier, extern erzeugter LLM-Text (zeichensaniert beim
    Übernehmen der Modellantwort) - im Frontend ausschließlich als regulärer Textknoten zu
    rendern."""

    canonical_key: str
    display_name: str
    photo_count: int


@router.get("/{project_id}/fine-labels", response_model=list[FineLabelCountOut])
async def list_fine_labels(
    project_id: int, session: AsyncSession = Depends(get_session)
) -> list[FineLabelCountOut]:
    """Haeufigste Feinlabels dieses Projekts, absteigend nach `photo_count`, Tie-Break
    `canonical_key` aufsteigend.

    Zweck: sichtbar machen, welche Kategorie im festen Set gegebenenfalls fehlt - das Set ist per
    Produktentscheidung geschlossen, aber nicht fuer immer festgelegt, und diese Liste ist der
    Aenderungspfad.

    SICHERHEIT: `fine_labels` ist bewusst eine
    PROJEKTUEBERGREIFENDE Vokabular-Registry (siehe models.py::FineLabel) - die Zaehlung MUSS
    deshalb ueber `photo_fine_labels -> photos.project_id` joinen. Ein globales
    `SELECT ... FROM fine_labels` wuerde Label-Haeufigkeiten ANDERER Projekte ausliefern.
    Vokabular-Eintraege ohne Foto im angefragten Projekt erscheinen durch den Join implizit nicht
    (photo_count > 0). Ein leeres Projekt liefert `200` mit leerer Liste; eine unbekannte
    project_id laeuft ueber `_get_project_or_404` in ein `404` (keine Objekt-ID-Enumeration ueber
    ein leeres 200). Ein Eigentuemer-Vergleich ist bewusst NICHT implementiert - das Auth-Modell
    kennt kein Rollen-/Eigentuemermodell, beide Nutzer sehen
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
            .order_by(
                func.count(func.distinct(PhotoFineLabel.photo_id)).desc(),
                FineLabel.canonical_key.asc(),
            )
        )
    ).all()

    return [
        FineLabelCountOut(
            canonical_key=canonical_key, display_name=display_name, photo_count=photo_count
        )
        for canonical_key, display_name, photo_count in rows
    ]
