"""Die Modellwahl eines Projekts als eigener Lese- und Schreibendpunkt (Spec 0383).

Der Router ist bewusst schlank: er validiert die GESCHLOSSENE Eingabe (keine freie Modell-ID, S1),
prueft die Verfuegbarkeit nur als Wahrheitswert (S4) und schreibt die drei Spalten in EINEM
Commit. Die Aufloesung selbst lebt in `photosort.model_choice` - hier entsteht kein zweiter Weg
zu Modell und Anbieter.

Zwei Fehlerzeiten, bewusst getrennt:

- Der Laufpfad (`resolve_model_choice`) wirft bei einem entfernten Modell; Ausloeser und
  Schaetzung antworten `409`.
- Dieser Lesepfad (`describe_model_choice`) wirft nicht: er zeigt die gespeicherte ID mit
  `provider: null`, sonst koennte der Nutzer den veralteten Wert nicht sehen und aendern.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.deps import get_current_user, get_session
from photosort.api.projects import _reject_while_a_criterion_run_is_active
from photosort.cloud_vision import VISION_MODELS_BY_PROVIDER, provider_for_vision_model
from photosort.config import settings
from photosort.model_choice import api_key_for_provider, describe_model_choice
from photosort.models import CategoryMethod, Project
from photosort.pricing import MODEL_PRICING, estimate_usd_per_image

router = APIRouter(
    prefix="/projects", tags=["model-choice"], dependencies=[Depends(get_current_user)]
)


class CloudModelOut(BaseModel):
    """Ein waehlbarer Katalogeintrag der Registry mit den fuenf Werten der Oberflaeche.

    `estimate_usd_per_image`, `input_usd_per_mtok` und `output_usd_per_mtok` sind `None`, wenn
    kein Preis gepflegt ist - nie `0` (eine `0` behauptete Kostenfreiheit). `available` ist die
    Anwesenheit des Schluessels als WAHRHEITSWERT; der Wert selbst verlaesst den Server nie."""

    provider: str
    model: str
    estimate_usd_per_image: float | None
    input_usd_per_mtok: float | None
    output_usd_per_mtok: float | None
    # Die einzige ausgelieferte Betriebsgroesse (S4) - bewusst je ANBIETER, weil der
    # Schrittmacher prozessweit je Anbieter zaehlt.
    requests_per_minute: int
    available: bool
    unavailable_reasons: list[Literal["no_api_key"]]


class EyeAvailabilityOut(BaseModel):
    """Eye ist keine Modellwahl, sondern eine Methode: verfuegbar oder in dieser Installation
    abgeschaltet. Die Einwilligung ist hier ausdruecklich KEIN Grund - sie greift erst beim Lauf."""

    available: bool
    unavailable_reasons: list[Literal["eye_disabled"]]


class ModelChoiceCurrentOut(BaseModel):
    """Die WIRKSAME Wahl des Projekts, so wie die Oberflaeche sie markiert.

    `*_is_default` unterscheidet `NULL` (Installationsvorgabe, folgt spaeteren Aenderungen) von
    einem ausdruecklich gespeicherten Wert. `provider` ist `None` bei Eye und bei einem Modell,
    das nicht mehr in der Registry steht - kein geratener Empfaenger."""

    category_method: CategoryMethod
    category_model: str | None
    category_provider: str | None
    category_is_default: bool
    landmark_model: str
    landmark_provider: str | None
    landmark_is_default: bool


class ModelChoiceOut(BaseModel):
    current: ModelChoiceCurrentOut
    cloud_models: list[CloudModelOut]
    eye: EyeAvailabilityOut


class ModelChoiceIn(BaseModel):
    """Die geschlossene Eingabe des Schreibendpunkts (S1).

    `extra="forbid"`: ein zusaetzliches Feld ist ein `422` und verschwindet nicht still. Beide
    Modellfelder sind PFLICHT (auch als `null`), damit ein Wechsel auf Eye das Kategorisierungs-
    modell ausdruecklich leert statt es als Altlast stehen zu lassen."""

    model_config = ConfigDict(extra="forbid")

    category_method: CategoryMethod
    category_model: str | None
    landmark_model: str | None


async def _get_project_or_404(project_id: int, session: AsyncSession) -> Project:
    """Wortgleich mit `api/projects.py::_get_project_or_404`."""
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden.")
    return project


def _cloud_model(provider: str, model: str) -> CloudModelOut:
    pricing = MODEL_PRICING.get(model)
    available = api_key_for_provider(provider)
    return CloudModelOut(
        provider=provider,
        model=model,
        estimate_usd_per_image=estimate_usd_per_image(model, provider),
        input_usd_per_mtok=None if pricing is None else pricing.input_usd_per_mtok,
        output_usd_per_mtok=None if pricing is None else pricing.output_usd_per_mtok,
        requests_per_minute=settings.resolved_cloud_vision_requests_per_minute(provider),
        available=available,
        unavailable_reasons=[] if available else ["no_api_key"],
    )


def _model_choice_out(project: Project) -> ModelChoiceOut:
    current = describe_model_choice(project)
    eye_available = settings.eye_enabled
    return ModelChoiceOut(
        current=ModelChoiceCurrentOut(
            category_method=current.category_method,
            category_model=current.category_model,
            category_provider=current.category_provider,
            category_is_default=current.category_is_default,
            landmark_model=current.landmark_model,
            landmark_provider=current.landmark_provider,
            landmark_is_default=current.landmark_is_default,
        ),
        cloud_models=[
            _cloud_model(provider, model)
            for provider, models in VISION_MODELS_BY_PROVIDER.items()
            for model in models
        ],
        eye=EyeAvailabilityOut(
            available=eye_available,
            unavailable_reasons=[] if eye_available else ["eye_disabled"],
        ),
    )


def _reject_unusable_model(new: str | None, stored: str | None) -> None:
    """Ein GEAENDERTER Wert muss in der Registry stehen und einen Schluessel haben; derselbe
    bereits gespeicherte Wert darf bleiben (sonst liesse sich ein Projekt mit entferntem Modell
    gar nicht mehr umstellen). Der Schluessel selbst wird nie genannt noch geloggt."""
    if new is None or new == stored:
        return
    provider = provider_for_vision_model(new)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Das gewählte Modell ist nicht wählbar.",
        )
    if not api_key_for_provider(provider):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Für {provider} ist kein API-Schlüssel hinterlegt.",
        )


@router.get("/{project_id}/model-choice", response_model=ModelChoiceOut)
async def get_model_choice(
    project_id: int, session: AsyncSession = Depends(get_session)
) -> ModelChoiceOut:
    """Der Katalog plus die gespeicherte Wahl. Rein lesend, ohne Netz und ohne Schluesselwert."""
    project = await _get_project_or_404(project_id, session)
    return _model_choice_out(project)


@router.put("/{project_id}/model-choice", response_model=ModelChoiceOut)
async def put_model_choice(
    project_id: int,
    payload: ModelChoiceIn,
    session: AsyncSession = Depends(get_session),
) -> ModelChoiceOut:
    """Setzt die Wahl je Taetigkeit - alle drei Spalten in EINEM Commit.

    Reihenfolge der Pruefungen: `404` -> `409` (laufende Klassifizierung) -> `422` -> schreiben.
    Bei einem Fehler aendert sich NICHTS; der Handler schreibt ausschliesslich
    `category_method`/`category_model`/`landmark_model` und fasst die Einwilligungs-Spalten
    nicht an (S3)."""
    project = await _get_project_or_404(project_id, session)
    await _reject_while_a_criterion_run_is_active(
        session,
        project_id,
        afterwards="Die Modellwahl kann danach geändert werden.",
    )

    if payload.category_method is CategoryMethod.EYE:
        if payload.category_model is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Eye hat kein Kategorisierungsmodell.",
            )
        if payload.category_method is not project.category_method and not settings.eye_enabled:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Eye ist in dieser Installation abgeschaltet.",
            )

    # `cloud` mit `category_model=None` ist ausdruecklich erlaubt: das ist die
    # Installationsvorgabe und der Rueckweg aus Eye, und beides braucht keinen Schluessel
    # (ADR 0143 Punkt 6). Gespeichert wird dann `NULL`, und `category_is_default` sagt es.

    _reject_unusable_model(payload.category_model, project.category_model)
    _reject_unusable_model(payload.landmark_model, project.landmark_model)

    project.category_method = payload.category_method
    project.category_model = payload.category_model
    project.landmark_model = payload.landmark_model
    await session.commit()
    await session.refresh(project)

    return _model_choice_out(project)
