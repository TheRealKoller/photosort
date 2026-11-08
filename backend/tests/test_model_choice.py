"""Die Aufloesung der Modellwahl je Projekt (ADR 0143 Punkt 2).

Genau EINE Funktion loest die im Projekt gespeicherte Wahl zu Modell und Anbieter auf. Der
Anbieter kommt IMMER aus `cloud_vision.provider_for_vision_model` - nie aus einer Einstellung,
nie aus dem Projekt, nie aus einer Praefix-Heuristik. Ein gespeichertes Modell, das nicht mehr in
der Registry steht, ist ein `UnknownModelChoiceError` und kein stiller Rueckfall auf die
Installationsvorgabe.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from photosort import model_choice
from photosort.cloud_vision import (
    ANTHROPIC_VISION_MODEL,
    ANTHROPIC_VISION_MODEL_SONNET,
    MISTRAL_VISION_MODEL,
)
from photosort.config import settings
from photosort.model_choice import (
    UnknownModelChoiceError,
    describe_model_choice,
    resolve_model_choice,
)
from photosort.models import CategoryMethod, Project


def _project(
    *,
    category_method: CategoryMethod = CategoryMethod.CLOUD,
    category_model: str | None = None,
    landmark_model: str | None = None,
) -> Project:
    return Project(
        id=1,
        name="Projekt",
        opencloud_drive_id="drive",
        opencloud_path="/pfad",
        category_method=category_method,
        category_model=category_model,
        landmark_model=landmark_model,
    )


def test_null_models_resolve_to_the_installation_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "landmark_provider", "mistral")

    resolved = resolve_model_choice(_project())

    assert resolved.category_method is CategoryMethod.CLOUD
    assert resolved.category_model == MISTRAL_VISION_MODEL
    assert resolved.category_provider == "mistral"
    assert resolved.landmark_model == MISTRAL_VISION_MODEL
    assert resolved.landmark_provider == "mistral"
    assert resolved.category_is_default is True
    assert resolved.landmark_is_default is True


def test_a_stored_installation_default_is_not_a_default_any_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`NULL` und der ausdruecklich gespeicherte Vorgabewert sind DERSELBE Modellwert, aber nicht
    dieselbe Herkunft: nur so ist "zur vorherigen Wahl zurueckkehren" eindeutig."""
    monkeypatch.setattr(settings, "landmark_provider", "anthropic")

    resolved = resolve_model_choice(
        _project(category_model=ANTHROPIC_VISION_MODEL, landmark_model=ANTHROPIC_VISION_MODEL)
    )

    assert resolved.category_model == ANTHROPIC_VISION_MODEL
    assert resolved.landmark_model == ANTHROPIC_VISION_MODEL
    assert resolved.category_is_default is False
    assert resolved.landmark_is_default is False


def test_both_tasks_may_carry_models_of_different_providers() -> None:
    resolved = resolve_model_choice(
        _project(
            category_model=ANTHROPIC_VISION_MODEL_SONNET,
            landmark_model=MISTRAL_VISION_MODEL,
        )
    )

    assert resolved.category_model == ANTHROPIC_VISION_MODEL_SONNET
    assert resolved.category_provider == "anthropic"
    assert resolved.landmark_model == MISTRAL_VISION_MODEL
    assert resolved.landmark_provider == "mistral"


def test_eye_categorization_has_no_model_and_no_provider() -> None:
    resolved = resolve_model_choice(_project(category_method=CategoryMethod.EYE))

    assert resolved.category_method is CategoryMethod.EYE
    assert resolved.category_model is None
    assert resolved.category_provider is None
    assert resolved.category_is_default is False
    # Die Sehenswuerdigkeits-Erkennung bleibt eine Cloud-Wahl.
    assert resolved.landmark_model == settings.resolved_landmark_model()
    assert resolved.landmark_provider == settings.landmark_provider


def test_an_unknown_category_model_raises_instead_of_falling_back() -> None:
    with pytest.raises(UnknownModelChoiceError):
        resolve_model_choice(_project(category_model="gibt-es-nicht"))


def test_an_unknown_landmark_model_raises_instead_of_falling_back() -> None:
    with pytest.raises(UnknownModelChoiceError):
        resolve_model_choice(_project(landmark_model="gibt-es-nicht"))


def test_the_key_check_returns_a_boolean_and_never_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-secret")
    monkeypatch.setattr(settings, "mistral_api_key", "")

    assert model_choice.api_key_for_provider("anthropic") is True
    assert model_choice.api_key_for_provider("mistral") is False
    assert model_choice.api_key_for_provider("unbekannt") is False


async def test_the_check_constraint_forbids_eye_with_a_cloud_model(
    db_session: AsyncSession,
) -> None:
    project = _project(category_method=CategoryMethod.EYE, category_model=ANTHROPIC_VISION_MODEL)
    project.name = "Constraint"
    db_session.add(project)

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_a_fresh_project_is_cloud_without_models(db_session: AsyncSession) -> None:
    project = Project(name="Frisch", opencloud_drive_id="drive", opencloud_path="/pfad")
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    assert project.category_method is CategoryMethod.CLOUD
    assert project.category_model is None
    assert project.landmark_model is None


def test_the_read_path_describes_a_removed_model_without_raising() -> None:
    """`GET …/model-choice` und `ProjectOut` zeigen die ID mit `provider: null` - ein 409 waere
    hier falsch, denn der Nutzer muss den veralteten Wert SEHEN, um ihn aendern zu koennen."""
    view = describe_model_choice(_project(category_model="gibt-es-nicht", landmark_model="weg"))

    assert view.category_model == "gibt-es-nicht"
    assert view.category_provider is None
    assert view.landmark_model == "weg"
    assert view.landmark_provider is None
    assert view.category_is_default is False
    assert view.landmark_is_default is False


def test_the_read_path_reports_the_effective_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "landmark_provider", "mistral")

    view = describe_model_choice(_project())

    assert view.category_model == MISTRAL_VISION_MODEL
    assert view.category_provider == "mistral"
    assert view.landmark_model == MISTRAL_VISION_MODEL
    assert view.landmark_provider == "mistral"
    assert view.category_is_default is True
    assert view.landmark_is_default is True


def test_the_read_path_has_no_category_model_for_eye() -> None:
    view = describe_model_choice(
        _project(category_method=CategoryMethod.EYE, landmark_model=ANTHROPIC_VISION_MODEL)
    )

    assert view.category_method is CategoryMethod.EYE
    assert view.category_model is None
    assert view.category_provider is None
    assert view.category_is_default is False
    assert view.landmark_provider == "anthropic"
