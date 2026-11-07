"""Die Endpunkte der Klassifizierungspruefung (Spec 0616, ADR 0139).

EIGENER ROUTER, EIGENE TABELLEN: dieser Lesepfad liest ausschliesslich die Prueftabellen und die
Fotos des Projekts - er schreibt keine Zeile einer bestehenden Tabelle (ADR 0139 Punkt 2).

SICHERHEIT (S2): Die Projektbindung ist eine UND-Bedingung in DERSELBEN Anweisung. `review_id`
wird zusammen mit `project_id` aufgeloest, `case_id` ueber den Join `cases -> reviews`. Eine fremde
oder erfundene Id ergibt `404` mit wortgleichem Text, nie `403` - ein `403` waere ein
Inhalts-Orakel. Es gibt keine Pruefungs-, Fall- oder Foto-Id aus Body oder Query.

SICHERHEIT (S10): Der Torwaechter haengt am ROUTER und zusaetzlich am Eintrag in
`tests/test_auth_guard.py::_protected_router_operations()`.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal, NamedTuple

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, StrictInt
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import (
    JobEnqueuer,
    get_current_user,
    get_job_enqueuer,
    get_session,
)
from photosort.classification_comparison import (
    DEFAULT_SAMPLE_SIZE,
    PURPOSES,
    PhotoComparison,
    compare_review,
    motif_present,
)
from photosort.cloud_vision import VISION_MODELS_BY_PROVIDER, provider_for_vision_model
from photosort.config import settings
from photosort.duplicates import survives_ausschuss
from photosort.eye_client import eye_service_is_healthy
from photosort.eye_mapping import MAPPINGS, MODEL_REVISION
from photosort.models import (
    ClassificationReview,
    ClassificationReviewCase,
    ClassificationReviewPurpose,
    ClassificationReviewResult,
    ClassificationReviewResultStrength,
    ClassificationReviewSide,
    ClassificationReviewSideKind,
    ClassificationReviewVerdict,
    ClassificationVerdict,
    Photo,
    PhotoScore,
    Project,
    ReviewPhase,
    ScanStatus,
    ScoringRun,
    User,
)
from photosort.motifs import MOTIF_REGISTRY
from photosort.pricing import estimate_usd_per_image

router = APIRouter(
    prefix="/projects/{project_id}/classification-reviews",
    tags=["classification-reviews"],
    dependencies=[Depends(get_current_user)],
)

# Die Pruefgraesse gilt JE ZWECK und wird hier NICHT still gekappt: eine gekappte Groesse waere
# eine andere Pruefung als die angefragte. Die Grenzen liefert `GET .../options`, damit die
# Oberflaeche keine eigene Kopie fuehrt.
SAMPLE_SIZE_MIN: Final = 1
SAMPLE_SIZE_MAX: Final = 200

# Die geschlossene Menge der Sperrgruende. `no_consent` steht VOR `no_api_key`: fehlt die
# Einwilligung, ist der Schluessel gleichgueltig, und die Oberflaeche nennt den Grund, den der
# Nutzer beheben kann.
UnavailableReason = Literal["no_consent", "no_api_key", "eye_disabled"]


class ReviewSampleSizeOut(BaseModel):
    default: int
    min: int
    max: int


class ReviewKindOptionOut(BaseModel):
    """Ein waehlbares Verfahren mit seinen Sperrgruenden - `available` ist genau dann wahr, wenn
    `unavailable_reasons` leer ist."""

    kind: ClassificationReviewSideKind
    available: bool
    unavailable_reasons: list[UnavailableReason]


class ReviewCloudModelOptionOut(BaseModel):
    provider: str
    model: str
    available: bool
    unavailable_reasons: list[UnavailableReason]


class ReviewEyeMappingOptionOut(BaseModel):
    """Eine waehlbare Eye-Fassung. Zwei Fassungen desselben Modells sind unterscheidbar, weil
    `MODEL_REVISION` und `eye_mapping_version` getrennt genannt werden."""

    eye_model_revision: str
    eye_mapping_version: str
    available: bool
    unavailable_reasons: list[UnavailableReason]


class ClassificationReviewOptionsOut(BaseModel):
    sample_size: ReviewSampleSizeOut
    kinds: list[ReviewKindOptionOut]
    cloud_models: list[ReviewCloudModelOptionOut]
    eye_mappings: list[ReviewEyeMappingOptionOut]


class ReviewSideEstimateOut(BaseModel):
    """Die Vorab-Schaetzung EINER Seite.

    Drei Zustaende, nie zwei: `0.0` heisst kostenfrei (Eye, lokal), `null` heisst "nicht
    schaetzbar" (kein Preis hinterlegt) - nie "kostenlos"."""

    kind: ClassificationReviewSideKind
    provider: str | None
    model: str | None
    photo_count: int
    price_per_image_usd: float | None
    estimated_cost_usd: float | None


class ClassificationReviewEstimateOut(BaseModel):
    photo_count: int
    a: ReviewSideEstimateOut
    b: ReviewSideEstimateOut


class ReviewSideIn(BaseModel):
    """Die Verfahrenswahl EINER Seite - geschlossene Eingabe (S6).

    Kein `provider`-Feld: der Anbieter folgt serverseitig aus dem Modell. `model` gilt nur fuer
    eine Cloud-Seite, `eye_mapping_version` nur fuer eine Eye-Seite; ein Wert am falschen Ort wird
    nicht gespeichert und ist damit wirkungslos, statt einen zweiten Weg zu oeffnen."""

    model_config = ConfigDict(extra="forbid")

    kind: ClassificationReviewSideKind
    model: str | None = None
    eye_mapping_version: str | None = None


class ReviewCreate(BaseModel):
    """Der Koerper des Anlegens. KEIN Betrags-, Preis-, Anbieter- oder Kostenfeld (S8): die
    Schaetzung entsteht serverseitig und wird eingefroren.

    `sample_size` ist PFLICHT und `StrictInt` (S9): `"30"` und `true` sind Typfehler, nicht die
    Zahl 30 und die Zahl 1 - die Vorgabe 30 ist eine Vorbelegung der Oberflaeche, kein stiller
    Ersatzwert des Servers. Die GRENZEN 1…200 stehen dagegen absichtlich nicht im Schema: die
    Ablehnungsreihenfolge der Spec stellt diesen `422` ANS ENDE (nach `403`/`404`/`409`/`503`),
    und ein `Field(ge=…, le=…)` antwortete schon vor dem Handler."""

    model_config = ConfigDict(extra="forbid")

    a: ReviewSideIn
    b: ReviewSideIn
    sample_size: StrictInt


class ReviewCreatedOut(BaseModel):
    id: int
    status: ScanStatus


@dataclass(frozen=True)
class ResolvedSide:
    """Eine validierte Seite: die Herkunft, wie sie GESPEICHERT wird (S6).

    `provider` folgt aus dem Modell, nie aus dem Client; `eye_model_revision` ist die gepinnte
    Modellrevision der Fassung."""

    side: str
    kind: ClassificationReviewSideKind
    provider: str | None
    model: str | None
    eye_model_revision: str | None
    eye_mapping_version: str | None

    def origin(self) -> tuple[str, str | None, str | None, str | None, str | None]:
        """Die Herkunftsmerkmale, in denen sich zwei Seiten unterscheiden MUESSEN."""
        return (
            str(self.kind),
            self.provider,
            self.model,
            self.eye_model_revision,
            self.eye_mapping_version,
        )


class ReviewUserOut(BaseModel):
    """Der Nutzer als AUSDRUECKLICHE Projektion auf zwei Spalten (Muster
    `api/photos.py::_participants`): nie `model_validate(User)`, `password_hash` erreicht keinen
    Lesepfad (S1)."""

    user_id: int
    username: str


class ReviewSideOut(BaseModel):
    """Herkunft UND Kosten einer Seite. Die Herkunft ist gespeichert, nicht abgeleitet: eine
    spaeter hinzugefuegte Eye-Fassung aendert eine bestehende Pruefung nicht.

    `estimated_cost_usd` ist der beim Anlegen eingefrorene Beleg, `cost_usd` die Ist-Kosten des
    Jobs - `null` heisst "nicht erfasst" und wird von `0.0` (kostenfrei) unterschieden."""

    kind: ClassificationReviewSideKind
    provider: str | None
    model: str | None
    eye_model_revision: str | None
    eye_mapping_version: str | None
    estimated_cost_usd: float | None
    cost_usd: float | None


class ReviewSidesOut(BaseModel):
    a: ReviewSideOut
    b: ReviewSideOut


class ReviewPurposeCountsOut(BaseModel):
    """Eine Zaehlung MIT ihrer Einheit: `motifs`, `excluded_document` und `album_level` zaehlen
    Fotos, `motif_feature` zaehlt (Foto, Motiv)-Paare (ADR 0139 Punkt 1). `presented` ist die Zahl
    der tatsaechlich vorgelegten Faelle = `min(Pruefgraesse, abweichend)`."""

    unit: Literal["photo", "pair"]
    compared: int
    matching: int
    deviating: int
    presented: int


class ReviewVerdictCountsOut(BaseModel):
    """Die vier Urteile plus `open`. `open` ist die Zahl der Faelle OHNE Urteil - die einzige
    Zahl, die der Server berechnet und die Oberflaeche nur formuliert."""

    a_better: int
    b_better: int
    both_ok: int
    both_wrong: int
    open: int


class ReviewListItemOut(BaseModel):
    """Eine Zeile der Liste. `case_count`/`case_open` tragen den Stand („{n} von {m} Fällen
    offen"); `case_count == 0` heisst "keine Abweichungen"."""

    id: int
    created_at: datetime
    created_by: ReviewUserOut
    status: ScanStatus
    phase: ReviewPhase | None
    sides: ReviewSidesOut
    case_count: int
    case_open: int


class ReviewDetailOut(BaseModel):
    """Status, Fortschritt, Herkunft, Zaehlungen und Urteile EINER Pruefung.

    Die Zaehlungen entstehen beim Lesen aus den Ergebnissen - mit derselben Funktion, die die
    Stichprobe gezogen hat (`compare_review`), damit Uebersicht und Fallliste nicht
    auseinandergehen."""

    id: int
    created_at: datetime
    created_by: ReviewUserOut
    status: ScanStatus
    phase: ReviewPhase | None
    sample_size: int
    seed: int
    photo_count: int
    photos_processed: int
    unclassifiable_photo_count: int
    finished_at: datetime | None
    error_message: str | None
    sides: ReviewSidesOut
    counts_by_purpose: dict[ClassificationReviewPurpose, ReviewPurposeCountsOut]
    verdict_counts: ReviewVerdictCountsOut
    verdicts_by_purpose: dict[ClassificationReviewPurpose, ReviewVerdictCountsOut]


class ReviewCaseSideOut(BaseModel):
    """Die Rohwerte EINER Seite in einem Fall - nur die seines Zwecks.

    `null` heisst "diese Seite trifft dazu keine Aussage", nie `false` oder `0`. Bei `motifs` ist
    die PraesenzMENGE der Rohwert (sie ist es, die der Vergleich vergleicht), bei `motif_feature`
    die ungerundete Staerke samt serverseitig entschiedener Praesenz - die Grenze steht damit
    einmal im Server (`selection.motif_is_present`) und nicht ein zweites Mal in der Oberflaeche."""

    motifs: list[str] | None = None
    present: bool | None = None
    strength: float | None = None
    excluded_document: bool | None = None
    album_level: int | None = None


class ReviewCaseOut(BaseModel):
    """Ein vorgelegter Fall mit Urteil und dessen Schreiber (Projektion auf zwei Spalten)."""

    id: int
    photo_position: int
    purpose: ClassificationReviewPurpose
    motif_key: str | None
    a: ReviewCaseSideOut
    b: ReviewCaseSideOut
    verdict: ClassificationVerdict | None
    updated_by: ReviewUserOut | None
    updated_at: datetime | None


class ReviewCasesOut(BaseModel):
    cases: list[ReviewCaseOut]


class ReviewVerdictIn(BaseModel):
    """Ein Urteil, geschlossen: der Wert ist ein `Literal`, ein unbekannter ist `422` aus dem
    Schema - vor dem Handler."""

    model_config = ConfigDict(extra="forbid")

    verdict: ClassificationVerdict


class ReviewVerdictOut(BaseModel):
    """Das Urteil nach dem Schreiben. Ein erneutes Setzen DESSELBEN Urteils aendert nichts: dann
    bleibt auch der genannte Schreiber der fruehere."""

    case_id: int
    verdict: ClassificationVerdict
    updated_by: ReviewUserOut
    updated_at: datetime


async def _get_project_or_404(project_id: int, session: AsyncSession) -> Project:
    """Wortgleich mit `api/projects.py::_get_project_or_404`."""
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
    return project


def _api_key_for_provider(provider: str) -> str:
    """Der hinterlegte Schluessel eines Anbieters - leer heisst "keiner hinterlegt".

    Ausdrueckliche Zuordnung statt `getattr(settings, f"{provider}_api_key")`: die Registry der
    Modelle ist erweiterbar, die Namen der Secret-Felder sind es nicht. Ein neuer Anbieter ohne
    Eintrag hier ist damit schlicht nicht waehlbar, statt versehentlich mit leerem Schluessel
    aufzulaufen. Es wird nur die ANWESENHEIT geprueft, der Wert verlaesst diese Funktion nie."""
    if provider == "anthropic":
        return settings.anthropic_api_key
    if provider == "mistral":
        return settings.mistral_api_key
    return ""


def _cloud_reasons(*, consent_enabled: bool, provider: str) -> list[UnavailableReason]:
    """Die Sperrgruende einer Cloud-Wahl in fester Reihenfolge: `no_consent` vor `no_api_key`."""
    reasons: list[UnavailableReason] = []
    if not consent_enabled:
        reasons.append("no_consent")
    if not _api_key_for_provider(provider):
        reasons.append("no_api_key")
    return reasons


def _eye_reasons() -> list[UnavailableReason]:
    return [] if settings.eye_enabled else ["eye_disabled"]


def _cloud_model_option(
    provider: str, model: str, *, consent_enabled: bool
) -> ReviewCloudModelOptionOut:
    reasons = _cloud_reasons(consent_enabled=consent_enabled, provider=provider)
    return ReviewCloudModelOptionOut(
        provider=provider,
        model=model,
        available=not reasons,
        unavailable_reasons=reasons,
    )


def _options_out(project: Project) -> ClassificationReviewOptionsOut:
    """Reine Funktion ueber Projekt und Betriebseinstellungen - kein Datenbankzugriff.

    `local` ist immer waehlbar: es braucht weder Einwilligung noch Schluessel noch Dienst."""
    consent = project.cloud_vision_detection_enabled
    eye_reasons = _eye_reasons()
    # Cloud ist als ART waehlbar, sobald Einwilligung UND mindestens ein Anbieterschluessel
    # vorliegen - WELCHE Modelle dann offen sind, sagt `cloud_models` je Modell.
    cloud_reasons = _cloud_reasons(
        consent_enabled=consent,
        provider=next(
            (name for name in VISION_MODELS_BY_PROVIDER if _api_key_for_provider(name)), ""
        ),
    )
    kinds = [
        ReviewKindOptionOut(
            kind=ClassificationReviewSideKind.CLOUD,
            available=not cloud_reasons,
            unavailable_reasons=cloud_reasons,
        ),
        ReviewKindOptionOut(
            kind=ClassificationReviewSideKind.EYE,
            available=not eye_reasons,
            unavailable_reasons=eye_reasons,
        ),
        ReviewKindOptionOut(
            kind=ClassificationReviewSideKind.LOCAL,
            available=True,
            unavailable_reasons=[],
        ),
    ]
    cloud_models = [
        _cloud_model_option(provider, model, consent_enabled=consent)
        for provider, models in VISION_MODELS_BY_PROVIDER.items()
        for model in models
    ]
    eye_mappings = [
        ReviewEyeMappingOptionOut(
            eye_model_revision=MODEL_REVISION,
            eye_mapping_version=version,
            available=not eye_reasons,
            unavailable_reasons=list(eye_reasons),
        )
        for version in MAPPINGS
    ]
    return ClassificationReviewOptionsOut(
        sample_size=ReviewSampleSizeOut(
            default=DEFAULT_SAMPLE_SIZE, min=SAMPLE_SIZE_MIN, max=SAMPLE_SIZE_MAX
        ),
        kinds=kinds,
        cloud_models=cloud_models,
        eye_mappings=eye_mappings,
    )


def _review_photo_ids(project_id: int) -> Select[tuple[int]]:
    """Die Pruefmenge als SQL-Fassung: alle Ausschuss-Ueberlebenden des Projekts, OHNE
    Skip-Kriterium - `survives_ausschuss()` setzt den inneren Join auf `PhotoScore` voraus."""
    return (
        select(Photo.id)
        .join(PhotoScore, PhotoScore.photo_id == Photo.id)
        .where(Photo.project_id == project_id, survives_ausschuss())
    )


async def _review_photo_count(session: AsyncSession, project_id: int) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(_review_photo_ids(project_id).subquery())
        )
    ).scalar_one()


def _estimate_part(photo_count: int, price_per_image_usd: float | None) -> float | None:
    """Ein Anteil der Vorab-Schaetzung mit der Dreizweigregel von
    `api/projects.py::_estimate_part`: null Fotos -> `0.0` (der Betrag ist bekannt, selbst ohne
    Preis), kein Preis hinterlegt -> `null`, nie ein stilles `0.0`. Die MENGE ist hier immer
    bekannt - sie stammt aus einer Zaehlung, nicht aus einer Bedingung."""
    if photo_count == 0:
        return 0.0
    if price_per_image_usd is None:
        return None
    return photo_count * price_per_image_usd


def _side_estimate(
    kind: ClassificationReviewSideKind,
    model: str | None,
    photo_count: int,
) -> ReviewSideEstimateOut:
    """Eye und lokal sind kostenfrei (`0.0`), eine Cloud-Seite kostet Fotozahl x Preis je Bild.
    Der Anbieter folgt ausschliesslich aus dem Modell (S6) - ein Anbieterfeld gibt es nicht."""
    if kind is not ClassificationReviewSideKind.CLOUD:
        return ReviewSideEstimateOut(
            kind=kind,
            provider=None,
            model=None,
            photo_count=photo_count,
            price_per_image_usd=0.0,
            estimated_cost_usd=0.0,
        )
    provider = provider_for_vision_model(model) if model is not None else None
    price = estimate_usd_per_image(model, provider) if provider is not None and model else None
    return ReviewSideEstimateOut(
        kind=kind,
        provider=provider,
        model=model,
        photo_count=photo_count,
        price_per_image_usd=price,
        estimated_cost_usd=_estimate_part(photo_count, price),
    )


@router.get("/options", response_model=ClassificationReviewOptionsOut)
async def get_options(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> ClassificationReviewOptionsOut:
    """Waehlbare Verfahren, Modelle und Eye-Fassungen samt Sperrgruenden.

    SICHERHEIT (S7): die Gruende sind feste Tokens, keine Variablennamen und keine Werte - die
    Antwort nennt nicht, WELCHER Schluessel fehlt."""
    project = await _get_project_or_404(project_id, session)
    return _options_out(project)


@router.get("/estimate", response_model=ClassificationReviewEstimateOut)
async def get_estimate(
    project_id: int,
    a_kind: ClassificationReviewSideKind,
    b_kind: ClassificationReviewSideKind,
    a_model: str | None = None,
    b_model: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> ClassificationReviewEstimateOut:
    """Die Kostenvorschau vor dem Start: die Groesse der Pruefmenge x Preis je Bild, je Seite.

    Serverseitig gerechnet, aus derselben Zaehlung wie das Anlegen - ein vom Client geliefertes
    Betragsfeld existiert nicht (S8). Ein unbekanntes Modell liefert `null` statt eines Fehlers:
    die Vorschau ist ein Lesepfad, und `null` heisst "nicht schaetzbar"."""
    await _get_project_or_404(project_id, session)
    photo_count = await _review_photo_count(session, project_id)
    return ClassificationReviewEstimateOut(
        photo_count=photo_count,
        a=_side_estimate(a_kind, a_model, photo_count),
        b=_side_estimate(b_kind, b_model, photo_count),
    )


async def _latest_scoring_run(session: AsyncSession, project_id: int) -> ScoringRun | None:
    """Wortgleich mit `api/projects.py::_latest_scoring_run` - die Vorbedingung ist dieselbe wie
    fuer `POST .../classify`."""
    result = await session.execute(
        select(ScoringRun)
        .where(ScoringRun.project_id == project_id)
        .order_by(ScoringRun.started_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def _reject_while_a_review_runs(session: AsyncSession, project_id: int) -> None:
    """`409`, solange die NEUESTE Pruefung des Projekts laeuft.

    Nur der neueste Lauf zaehlt (Muster `delete_project`): ein haengengebliebener Altlauf blockiert
    nicht dauerhaft, der Watchdog setzt ihn ohnehin auf `FAILED`."""
    latest = (
        await session.execute(
            select(ClassificationReview.status)
            .where(ClassificationReview.project_id == project_id)
            .order_by(ClassificationReview.started_at.desc(), ClassificationReview.id.desc())
            .limit(1)
        )
    ).first()
    if latest is not None and latest[0] == ScanStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Es laeuft bereits eine Pruefung. Warte, bis sie beendet ist.",
        )


def _resolve_side(side_in: ReviewSideIn, letter: str) -> ResolvedSide:
    """Validiert EINE Seite gegen die geschlossene Wahl (S6) und legt ihre Herkunft fest.

    Alle Ablehnungen hier sind `422` und stehen im Handler, nicht im Schema: die Reihenfolge der
    Spec verlangt sie NACH `403`/`404`/`409`/`503`."""
    kind = side_in.kind
    if kind is ClassificationReviewSideKind.EYE:
        version = side_in.eye_mapping_version
        if version is None or version not in MAPPINGS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unbekannte Eye-Fassung.",
            )
        return ResolvedSide(
            side=letter,
            kind=kind,
            provider=None,
            model=None,
            eye_model_revision=MODEL_REVISION,
            eye_mapping_version=version,
        )
    if kind is ClassificationReviewSideKind.CLOUD:
        model = side_in.model
        provider = provider_for_vision_model(model) if model is not None else None
        if model is None or provider is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unbekanntes Modell.",
            )
        if not _api_key_for_provider(provider):
            # Kein Schluessel heisst nicht "unbekannt": die Wahl ist bekannt, aber nicht
            # ausfuehrbar - und ein Lauf ohne Schluessel scheiterte garantiert.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Fuer dieses Modell ist kein API-Schluessel hinterlegt.",
            )
        return ResolvedSide(
            side=letter,
            kind=kind,
            provider=provider,
            model=model,
            eye_model_revision=None,
            eye_mapping_version=None,
        )
    # Lokal: ohne Sehenswuerdigkeits-Beitrag, ohne Modell und ohne Fassung.
    return ResolvedSide(
        side=letter,
        kind=kind,
        provider=None,
        model=None,
        eye_model_revision=None,
        eye_mapping_version=None,
    )


@router.post("", response_model=ReviewCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_review(
    project_id: int,
    payload: ReviewCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    enqueuer: JobEnqueuer = Depends(get_job_enqueuer),
) -> ReviewCreatedOut:
    """Legt eine Pruefung an und reiht den Job ein.

    Die REIHENFOLGE der Ablehnungen ist Teil der Zusage (Spec 0616):

    1. `403`, wenn der Feature-Schalter aus ist.
    2. `403`, wenn eine Seite Eye ist und `EYE_ENABLED` aus ist - VOR jedem Projektzugriff, damit
       die Antwort nichts ueber die Existenz eines Projekts verraet.
    3. `404` bei unbekanntem Projekt.
    4. die drei `409` (kein erfolgreicher Ausschusslauf, Gate nicht bestaetigt, Pruefung laeuft).
    5. `403`, wenn eine Seite Cloud ist und die Projekteinwilligung fehlt.
    6. `503`, wenn eine Seite Eye ist und der Dienst nicht gesund antwortet - VOR dem Einreihen:
       ein eingereihter Job scheiterte garantiert, und ein stiller Rueckfall auf ein anderes
       Verfahren waere schlimmer als die sichtbare Ablehnung.
    7. `422` (zwei gleiche Seiten, unbekanntes Modell, unbekannte Fassung, Groesse ausserhalb
       1…200) - erst hier, weil die Spec diese Ablehnung ans Ende stellt.

    Danach: Schaetzung je Seite serverseitig berechnen, an der Seite EINFRIEREN, Zeile und Job
    schreiben (S8). Kein Client-Feld traegt einen Betrag."""
    if not settings.category_selection_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diese Funktion ist derzeit nicht aktiviert.",
        )
    eye_requested = (
        payload.a.kind is ClassificationReviewSideKind.EYE
        or payload.b.kind is ClassificationReviewSideKind.EYE
    )
    if eye_requested and not settings.eye_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Die Eye-Auswertung ist nicht aktiviert.",
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
    await _reject_while_a_review_runs(session, project_id)

    cloud_requested = (
        payload.a.kind is ClassificationReviewSideKind.CLOUD
        or payload.b.kind is ClassificationReviewSideKind.CLOUD
    )
    if cloud_requested and not project.cloud_vision_detection_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Die Cloud-Seite ist ohne Einwilligung im Projekt nicht ausfuehrbar.",
        )
    if eye_requested and not await eye_service_is_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Die Eye-Auswertung ist derzeit nicht erreichbar. Die Pruefung wurde nicht "
            "gestartet und es wurde nichts veraendert.",
        )

    if not SAMPLE_SIZE_MIN <= payload.sample_size <= SAMPLE_SIZE_MAX:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Die Pruefgraesse muss zwischen {SAMPLE_SIZE_MIN} und {SAMPLE_SIZE_MAX} "
            "liegen.",
        )
    sides = [_resolve_side(payload.a, "a"), _resolve_side(payload.b, "b")]
    if sides[0].origin() == sides[1].origin():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Die beiden Seiten sind gleich. Waehle zwei unterschiedliche Verfahren.",
        )

    photo_count = await _review_photo_count(session, project_id)
    review = ClassificationReview(
        project_id=project_id,
        created_by_user_id=current_user.id,
        status=ScanStatus.RUNNING,
        phase=None,
        sample_size=payload.sample_size,
        seed=random.randrange(2**31),
        photo_count=photo_count,
    )
    session.add(review)
    await session.flush()
    session.add_all(
        [
            ClassificationReviewSide(
                review_id=review.id,
                side=side.side,
                kind=side.kind,
                provider=side.provider,
                model=side.model,
                eye_model_revision=side.eye_model_revision,
                eye_mapping_version=side.eye_mapping_version,
                estimated_cost_usd=_side_estimate(
                    side.kind, side.model, photo_count
                ).estimated_cost_usd,
            )
            for side in sides
        ]
    )
    await session.commit()

    # NACH dem Commit: ein Job, der die Zeile nicht faende, scheiterte sofort.
    await enqueuer.enqueue_job("run_classification_review", review.id)
    return ReviewCreatedOut(id=review.id, status=ScanStatus.RUNNING)


# ---------------------------------------------------------------------------------------------
# Lesepfad: Seiten, Zaehlungen und die gespeicherten Faelle
# ---------------------------------------------------------------------------------------------

_PURPOSE_ORDER: Final[dict[str, int]] = {purpose: index for index, purpose in enumerate(PURPOSES)}
_MOTIF_ORDER: Final[dict[str, int]] = {
    motif_key: index for index, motif_key in enumerate(MOTIF_REGISTRY)
}
# Die Einheit je Zweck - eine Quelle fuer Detail und Export: `motif_feature` zaehlt PAARE, die
# drei uebrigen FOTOS (ADR 0139 Punkt 1).
_UNIT_BY_PURPOSE: Final[dict[str, Literal["photo", "pair"]]] = {
    "motifs": "photo",
    "motif_feature": "pair",
    "excluded_document": "photo",
    "album_level": "photo",
}

_SIDE_COLUMNS = (
    ClassificationReviewSide.kind,
    ClassificationReviewSide.provider,
    ClassificationReviewSide.model,
    ClassificationReviewSide.eye_model_revision,
    ClassificationReviewSide.eye_mapping_version,
    ClassificationReviewSide.estimated_cost_usd,
    ClassificationReviewSide.cost_usd,
)


def _side_out(
    kind: ClassificationReviewSideKind,
    provider: str | None,
    model: str | None,
    eye_model_revision: str | None,
    eye_mapping_version: str | None,
    estimated_cost_usd: float | None,
    cost_usd: float | None,
) -> ReviewSideOut:
    return ReviewSideOut(
        kind=kind,
        provider=provider,
        model=model,
        eye_model_revision=eye_model_revision,
        eye_mapping_version=eye_mapping_version,
        estimated_cost_usd=estimated_cost_usd,
        cost_usd=cost_usd,
    )


async def _review_or_404(
    project_id: int, review_id: int, session: AsyncSession
) -> ClassificationReview:
    """Die Projektbindung als UND-Bedingung in DERSELBEN Anweisung (S2): eine Pruefung eines
    anderen Projekts ist `404` mit demselben Text wie eine erfundene Id."""
    review = (
        await session.execute(
            select(ClassificationReview).where(
                ClassificationReview.id == review_id,
                ClassificationReview.project_id == project_id,
            )
        )
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pruefung nicht gefunden."
        )
    return review


async def _sides_for_review(session: AsyncSession, review_id: int) -> dict[str, ReviewSideOut]:
    rows = (
        await session.execute(
            select(ClassificationReviewSide.side, *_SIDE_COLUMNS).where(
                ClassificationReviewSide.review_id == review_id
            )
        )
    ).all()
    return {side: _side_out(*values) for side, *values in rows}


async def _sides_by_review(
    session: AsyncSession, project_id: int
) -> dict[int, dict[str, ReviewSideOut]]:
    """Die Seiten ALLER Pruefungen eines Projekts in EINER Abfrage - die Liste braucht sie je
    Zeile, und eine Abfrage je Zeile waere eine Abfrage je Pruefung."""
    rows = (
        await session.execute(
            select(
                ClassificationReviewSide.review_id, ClassificationReviewSide.side, *_SIDE_COLUMNS
            )
            .join(
                ClassificationReview,
                ClassificationReview.id == ClassificationReviewSide.review_id,
            )
            .where(ClassificationReview.project_id == project_id)
        )
    ).all()
    sides: dict[int, dict[str, ReviewSideOut]] = defaultdict(dict)
    for review_id, side, *values in rows:
        sides[review_id][side] = _side_out(*values)
    return sides


@dataclass(frozen=True)
class _Statement:
    """Die Aussage EINER Seite zu EINEM Foto - dieselbe Form, die der Job verglichen hat."""

    strengths: dict[str, float]
    excluded_document: bool | None
    album_level: int | None


async def _load_statements(
    session: AsyncSession, review_id: int
) -> dict[str, dict[int, _Statement]]:
    """Ergebnisse und Staerken einer Pruefung, je Seite und Foto.

    Eigene Fassung statt Griff in `classification_review._load_statements`: die privaten Namen des
    Jobs sind kein Vertrag der API. Die Regel ist dieselbe - eine fehlende Ergebniszeile heisst
    "keine Aussage". Ein `None` fuehrt dazu, dass der Zweck nicht verglichen wird."""
    results = (
        (
            await session.execute(
                select(ClassificationReviewResult).where(
                    ClassificationReviewResult.review_id == review_id
                )
            )
        )
        .scalars()
        .all()
    )
    strengths: dict[tuple[str, int], dict[str, float]] = {}
    for strength_row in (
        (
            await session.execute(
                select(ClassificationReviewResultStrength).where(
                    ClassificationReviewResultStrength.review_id == review_id
                )
            )
        )
        .scalars()
        .all()
    ):
        strengths.setdefault((strength_row.side, strength_row.photo_id), {})[
            strength_row.motif_key
        ] = strength_row.strength

    statements: dict[str, dict[int, _Statement]] = {"a": {}, "b": {}}
    for result_row in results:
        statements[result_row.side][result_row.photo_id] = _Statement(
            strengths=strengths.get((result_row.side, result_row.photo_id), {}),
            excluded_document=result_row.excluded_document,
            album_level=result_row.album_level,
        )
    return statements


def _comparisons(statements: dict[str, dict[int, _Statement]]) -> list[PhotoComparison]:
    """Die Vergleichszeilen je Foto, in aufsteigender `photo_id`-Reihenfolge.

    Die Reihenfolge ist die der eingefrorenen Pruefmenge (`photo_id` aufsteigend), damit dieselbe
    Funktion auf derselben Eingabe dieselbe Stichprobe zieht."""
    comparisons: list[PhotoComparison] = []
    for photo_id in sorted(set(statements["a"]) | set(statements["b"])):
        side_a = statements["a"].get(photo_id)
        side_b = statements["b"].get(photo_id)
        comparisons.append(
            PhotoComparison(
                photo_id=photo_id,
                a_motifs=side_a.strengths if side_a is not None else None,
                b_motifs=side_b.strengths if side_b is not None else None,
                a_excluded_document=(side_a.excluded_document if side_a is not None else None),
                b_excluded_document=(side_b.excluded_document if side_b is not None else None),
                a_album_level=side_a.album_level if side_a is not None else None,
                b_album_level=side_b.album_level if side_b is not None else None,
            )
        )
    return comparisons


def _presented_by_purpose(rows: Iterable[ClassificationReviewPurpose]) -> dict[str, int]:
    presented = {purpose: 0 for purpose in PURPOSES}
    for purpose in rows:
        presented[purpose.value] += 1
    return presented


def _verdict_counts(verdicts: Iterable[ClassificationVerdict | None]) -> dict[str, int]:
    """Die vier Urteile plus `open` - `open` ist die Zahl der Faelle ohne Urteil."""
    counts = {"a_better": 0, "b_better": 0, "both_ok": 0, "both_wrong": 0, "open": 0}
    for verdict in verdicts:
        counts["open" if verdict is None else verdict.value] += 1
    return counts


class _CaseRow(NamedTuple):
    """Eine gespeicherte Fallzeile samt Urteil und dessen Schreiber (Projektion auf zwei
    Spalten)."""

    case: ClassificationReviewCase
    verdict: ClassificationVerdict | None
    user_id: int | None
    username: str | None
    updated_at: datetime | None


async def _case_rows(session: AsyncSession, review_id: int) -> list[_CaseRow]:
    """Die gespeicherten Faelle mit Urteil und dessen Schreiber in EINER Abfrage.

    Der Schreiber kommt als ausdrueckliche Projektion (`users.id`, `users.username`) - nie als
    geladenes `User`-Objekt (S1)."""
    rows = (
        await session.execute(
            select(
                ClassificationReviewCase,
                ClassificationReviewVerdict.verdict,
                User.id,
                User.username,
                ClassificationReviewVerdict.updated_at,
            )
            .outerjoin(
                ClassificationReviewVerdict,
                ClassificationReviewVerdict.case_id == ClassificationReviewCase.id,
            )
            .outerjoin(User, User.id == ClassificationReviewVerdict.updated_by_user_id)
            .where(ClassificationReviewCase.review_id == review_id)
        )
    ).all()
    return [
        _CaseRow(
            case=row[0],
            verdict=row[1],
            user_id=row[2],
            username=row[3],
            updated_at=row[4],
        )
        for row in rows
    ]


def _sort_cases(rows: Sequence[_CaseRow]) -> list[_CaseRow]:
    """Sortierung der Fallliste: `(photo_position, Zweck, Merkmal)` - Zweck in der Reihenfolge aus
    `PURPOSES`, Merkmal in Registry-Ordnung (ADR 0139 Punkt 3)."""
    return sorted(
        rows,
        key=lambda row: (
            row.case.photo_position,
            _PURPOSE_ORDER[row.case.purpose.value],
            _MOTIF_ORDER[row.case.motif_key] if row.case.motif_key is not None else -1,
        ),
    )


def _case_side(
    statement: _Statement | None,
    purpose: ClassificationReviewPurpose,
    motif_key: str | None,
) -> ReviewCaseSideOut:
    """Die Rohwerte einer Seite fuer den Zweck des Falls. `None` (keine Aussage) bleibt `None`."""
    if statement is None:
        return ReviewCaseSideOut()
    if purpose is ClassificationReviewPurpose.MOTIFS:
        return ReviewCaseSideOut(
            motifs=[key for key in MOTIF_REGISTRY if motif_present(statement.strengths, key)]
        )
    if purpose is ClassificationReviewPurpose.MOTIF_FEATURE:
        assert motif_key is not None
        return ReviewCaseSideOut(
            present=motif_present(statement.strengths, motif_key),
            strength=statement.strengths.get(motif_key),
        )
    if purpose is ClassificationReviewPurpose.EXCLUDED_DOCUMENT:
        return ReviewCaseSideOut(excluded_document=statement.excluded_document)
    return ReviewCaseSideOut(album_level=statement.album_level)


def _case_out(row: _CaseRow, statements: dict[str, dict[int, _Statement]]) -> ReviewCaseOut:
    case, verdict, user_id, username, updated_at = row
    return ReviewCaseOut(
        id=case.id,
        photo_position=case.photo_position,
        purpose=case.purpose,
        motif_key=case.motif_key,
        a=_case_side(statements["a"].get(case.photo_id), case.purpose, case.motif_key),
        b=_case_side(statements["b"].get(case.photo_id), case.purpose, case.motif_key),
        verdict=verdict,
        updated_by=(
            ReviewUserOut(user_id=user_id, username=username)
            if user_id is not None and username is not None
            else None
        ),
        updated_at=updated_at,
    )


def _sides_out(sides: dict[str, ReviewSideOut]) -> ReviewSidesOut:
    """Beide Seiten eines Laufs. Eine fehlende Seite ist kein Lesefehler des Clients, sondern ein
    unfertiger Lauf - sie wird dann als Seite ohne Herkunft gemeldet, nie stillschweigend als die
    andere Seite."""
    empty = ReviewSideOut(
        kind=ClassificationReviewSideKind.LOCAL,
        provider=None,
        model=None,
        eye_model_revision=None,
        eye_mapping_version=None,
        estimated_cost_usd=None,
        cost_usd=None,
    )
    return ReviewSidesOut(a=sides.get("a", empty), b=sides.get("b", empty))


@router.get("", response_model=list[ReviewListItemOut])
async def list_reviews(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[ReviewListItemOut]:
    """Alle Pruefungen des Projekts, neueste zuerst.

    Drei Abfragen statt einer je Zeile: Pruefungen samt Anleger, alle Seiten des Projekts, die
    Zahl der Faelle und der offenen Urteile je Pruefung."""
    await _get_project_or_404(project_id, session)
    review_rows = (
        await session.execute(
            select(
                ClassificationReview.id,
                ClassificationReview.started_at,
                ClassificationReview.status,
                ClassificationReview.phase,
                User.id,
                User.username,
            )
            .join(User, User.id == ClassificationReview.created_by_user_id)
            .where(ClassificationReview.project_id == project_id)
            .order_by(ClassificationReview.started_at.desc(), ClassificationReview.id.desc())
        )
    ).all()
    sides = await _sides_by_review(session, project_id)
    case_rows = (
        await session.execute(
            select(
                ClassificationReviewCase.review_id,
                func.count(),
                func.count(ClassificationReviewVerdict.case_id),
            )
            .join(
                ClassificationReview,
                ClassificationReview.id == ClassificationReviewCase.review_id,
            )
            .outerjoin(
                ClassificationReviewVerdict,
                ClassificationReviewVerdict.case_id == ClassificationReviewCase.id,
            )
            .where(ClassificationReview.project_id == project_id)
            .group_by(ClassificationReviewCase.review_id)
        )
    ).all()
    case_counts = {review_id: (total, total - decided) for review_id, total, decided in case_rows}
    return [
        ReviewListItemOut(
            id=review_id,
            created_at=started_at,
            created_by=ReviewUserOut(user_id=user_id, username=username),
            status=review_status,
            phase=phase,
            sides=_sides_out(sides[review_id]),
            case_count=case_counts.get(review_id, (0, 0))[0],
            case_open=case_counts.get(review_id, (0, 0))[1],
        )
        for review_id, started_at, review_status, phase, user_id, username in review_rows
    ]


@router.get("/{review_id}", response_model=ReviewDetailOut)
async def get_review(
    project_id: int,
    review_id: int,
    session: AsyncSession = Depends(get_session),
) -> ReviewDetailOut:
    """Status, Fortschritt, Herkunft, Zaehlungen je Zweck und Urteilszahlen einer Pruefung.

    Die Zaehlungen entstehen beim Lesen mit `compare_review` - derselben Funktion, die die
    Stichprobe gezogen hat. `presented` stammt dagegen aus den GESPEICHERTEN Faellen: eine
    spaetere Aenderung der Ergebnistabellen kann die vorgelegte Auswahl nicht rueckwirkend
    verschieben."""
    review = await _review_or_404(project_id, review_id, session)
    statements = await _load_statements(session, review_id)
    comparison = compare_review(
        _comparisons(statements), seed=review.seed, limit=review.sample_size
    )
    rows = await _case_rows(session, review_id)
    presented = _presented_by_purpose(row.case.purpose for row in rows)
    creator_id, creator_name = (
        await session.execute(
            select(User.id, User.username).where(User.id == review.created_by_user_id)
        )
    ).one()
    return ReviewDetailOut(
        id=review.id,
        created_at=review.started_at,
        created_by=ReviewUserOut(user_id=creator_id, username=creator_name),
        status=review.status,
        phase=review.phase,
        sample_size=review.sample_size,
        seed=review.seed,
        photo_count=review.photo_count,
        photos_processed=review.photos_processed,
        unclassifiable_photo_count=review.unclassifiable_photo_count,
        finished_at=review.finished_at,
        error_message=review.error_message,
        sides=_sides_out(await _sides_for_review(session, review_id)),
        counts_by_purpose={
            ClassificationReviewPurpose(purpose): ReviewPurposeCountsOut(
                unit=_UNIT_BY_PURPOSE[purpose],
                compared=counts.compared,
                matching=counts.matching,
                deviating=counts.deviating,
                presented=presented[purpose],
            )
            for purpose, counts in comparison.counts.items()
        },
        verdict_counts=ReviewVerdictCountsOut(**_verdict_counts(row.verdict for row in rows)),
        verdicts_by_purpose={
            ClassificationReviewPurpose(purpose): ReviewVerdictCountsOut(
                **_verdict_counts(row.verdict for row in rows if row.case.purpose.value == purpose)
            )
            for purpose in PURPOSES
        },
    )


@router.get("/{review_id}/cases", response_model=ReviewCasesOut)
async def get_review_cases(
    project_id: int,
    review_id: int,
    session: AsyncSession = Depends(get_session),
) -> ReviewCasesOut:
    """Die vorgelegten Faelle, sortiert nach `(photo_position, Zweck, Merkmal)`.

    IMMER `200`: eine laufende Pruefung hat noch keine Faelle (sie entstehen in ihrem letzten
    Teilschritt), und eine fehlgeschlagene zeigt die bis dahin geschriebenen - eine leere Liste ist
    hier ein Zustand, kein Fehler."""
    await _review_or_404(project_id, review_id, session)
    statements = await _load_statements(session, review_id)
    rows = _sort_cases(await _case_rows(session, review_id))
    return ReviewCasesOut(cases=[_case_out(row, statements) for row in rows])


@router.put("/{review_id}/cases/{case_id}/verdict", response_model=ReviewVerdictOut)
async def put_case_verdict(
    project_id: int,
    review_id: int,
    case_id: int,
    payload: ReviewVerdictIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ReviewVerdictOut:
    """Setzt oder aendert das EINE Urteil eines Falls (Upsert, letzter Schreiber gewinnt).

    Reihenfolge: das `422` eines unbekannten Urteilswerts kommt aus dem Schema (vor dem Handler),
    dann `404` (Pruefung oder Fall unbekannt, Projektbindung in derselben Anweisung), dann `409`
    (Pruefung nicht `SUCCESS`). Ein erneutes Setzen DESSELBEN Urteils schreibt nichts - der
    genannte Schreiber bleibt dann der fruehere, weil sich nichts geaendert hat."""
    case = (
        await session.execute(
            select(ClassificationReviewCase, ClassificationReview.status)
            .join(
                ClassificationReview,
                ClassificationReview.id == ClassificationReviewCase.review_id,
            )
            .where(
                ClassificationReviewCase.id == case_id,
                ClassificationReviewCase.review_id == review_id,
                ClassificationReview.project_id == project_id,
            )
        )
    ).first()
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fall nicht gefunden.")
    case_row, review_status = case
    if review_status != ScanStatus.SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Urteile sind nur an einer abgeschlossenen Pruefung moeglich.",
        )

    existing = await session.get(ClassificationReviewVerdict, case_row.id)
    if existing is not None and existing.verdict == payload.verdict:
        writer_id, writer_name = (
            await session.execute(
                select(User.id, User.username).where(User.id == existing.updated_by_user_id)
            )
        ).one()
        return ReviewVerdictOut(
            case_id=case_row.id,
            verdict=existing.verdict,
            updated_by=ReviewUserOut(user_id=writer_id, username=writer_name),
            updated_at=existing.updated_at,
        )

    now = datetime.now(UTC).replace(tzinfo=None)
    if existing is None:
        session.add(
            ClassificationReviewVerdict(
                case_id=case_row.id,
                verdict=payload.verdict,
                updated_by_user_id=current_user.id,
                updated_at=now,
            )
        )
    else:
        existing.verdict = payload.verdict
        existing.updated_by_user_id = current_user.id
        existing.updated_at = now
    await session.commit()
    return ReviewVerdictOut(
        case_id=case_row.id,
        verdict=payload.verdict,
        updated_by=ReviewUserOut(user_id=current_user.id, username=current_user.username),
        updated_at=now,
    )
