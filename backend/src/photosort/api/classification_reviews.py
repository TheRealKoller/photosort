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

from typing import Final, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.classification_comparison import DEFAULT_SAMPLE_SIZE
from photosort.cloud_vision import VISION_MODELS_BY_PROVIDER, provider_for_vision_model
from photosort.config import settings
from photosort.duplicates import survives_ausschuss
from photosort.eye_mapping import MAPPINGS, MODEL_REVISION
from photosort.models import (
    ClassificationReviewSideKind,
    Photo,
    PhotoScore,
    Project,
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
