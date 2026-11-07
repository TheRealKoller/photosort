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
from dataclasses import dataclass
from typing import Final, Literal

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
from photosort.classification_comparison import DEFAULT_SAMPLE_SIZE
from photosort.cloud_vision import VISION_MODELS_BY_PROVIDER, provider_for_vision_model
from photosort.config import settings
from photosort.duplicates import survives_ausschuss
from photosort.eye_client import eye_service_is_healthy
from photosort.eye_mapping import MAPPINGS, MODEL_REVISION
from photosort.models import (
    ClassificationReview,
    ClassificationReviewSide,
    ClassificationReviewSideKind,
    Photo,
    PhotoScore,
    Project,
    ScanStatus,
    ScoringRun,
    User,
)
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
