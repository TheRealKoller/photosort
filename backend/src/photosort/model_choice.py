"""Die EINE Aufloesung der Modellwahl je Projekt und Taetigkeit (ADR 0143 Punkt 2).

Das Projekt speichert die Wahl je Taetigkeit; dieses Modul loest sie zu Modell und Anbieter auf.
Ausloeser, Schaetzung und Job benutzen dieselbe Funktion, damit "angezeigt = aufgerufen =
abgerechnet" strukturell gilt und nicht aus drei zufaellig gleichen Lesevorgaengen besteht.

Der Anbieter kommt IMMER aus `cloud_vision.provider_for_vision_model(model)` - nie aus
`settings.landmark_provider`, nie aus dem Projekt, nie aus einer Praefix-Heuristik. Ein
gespeichertes Modell, das nicht mehr in der Registry steht, wirft `UnknownModelChoiceError`: es
gibt keinen stillen Rueckfall, sonst ginge ein Foto an einen anderen Empfaenger als angezeigt.
"""

from __future__ import annotations

from dataclasses import dataclass

from photosort.cloud_vision import provider_for_vision_model
from photosort.config import settings
from photosort.models import CategoryMethod, Project


class UnknownModelChoiceError(Exception):
    """Ein gespeichertes Modell steht nicht mehr in `VISION_MODELS_BY_PROVIDER`.

    Ausloeser und Schaetzung antworten darauf mit `409`; Lesepfade zeigen die Modell-ID mit
    `provider: null`. Ein Rueckfall auf die Installationsvorgabe waere ein stiller Wechsel des
    Empfaengers."""


@dataclass(frozen=True)
class ResolvedModelChoice:
    """Die wirksame Wahl eines Projekts, je Taetigkeit samt Anbieter.

    `category_model`/`category_provider` sind bei Eye `None` - Eye liefert keine Modell-ID und
    keinen Anbieter. `*_is_default` sagt, ob der Wert aus der Installationsvorgabe stammt
    (`NULL` in der Spalte) statt aus einer ausdruecklich gespeicherten Wahl."""

    category_method: CategoryMethod
    category_model: str | None
    category_provider: str | None
    landmark_model: str
    landmark_provider: str
    category_is_default: bool
    landmark_is_default: bool


@dataclass(frozen=True)
class ModelChoiceView:
    """Dieselbe Wahl fuer LESEPFAEDE - mit einer anderen Fehlerzeit.

    Ein gespeichertes Modell, das nicht mehr in der Registry steht, bleibt hier als ID stehen und
    traegt `provider: None`: `GET …/model-choice` und `ProjectOut` werfen nicht, sie zeigen. Der
    Laufpfad daneben (`resolve_model_choice`) wirft `UnknownModelChoiceError` - ein Foto darf
    nicht an einen anderen Empfaenger gehen als angezeigt, eine ANZEIGE aber darf einen
    veralteten Wert benennen."""

    category_method: CategoryMethod
    category_model: str | None
    category_provider: str | None
    landmark_model: str
    landmark_provider: str | None
    category_is_default: bool
    landmark_is_default: bool


def api_key_for_provider(provider: str) -> bool:
    """Ist fuer diesen Anbieter ein Schluessel hinterlegt?

    Ausdrueckliche Zuordnung statt `getattr(settings, f"{provider}_api_key")`: die Registry der
    Modelle ist erweiterbar, die Namen der Secret-Felder sind es nicht. Es wird nur die
    ANWESENHEIT geprueft, der Wert verlaesst diese Funktion nie - weder Antwort noch Fehlertext
    noch Log tragen Schluessel, Praefix, Laenge oder Variablenname."""
    if provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if provider == "mistral":
        return bool(settings.mistral_api_key)
    return False


def _provider_or_raise(model: str) -> str:
    provider = provider_for_vision_model(model)
    if provider is None:
        raise UnknownModelChoiceError(f"Unbekanntes Vision-Modell: {model!r}")
    return provider


def _stored_values(project: Project) -> tuple[str | None, bool, str, bool]:
    """Die wirksamen Werte OHNE Anbieter-Aufloesung - die eine Stelle, die `NULL` zur
    Installationsvorgabe macht. Geteilt von Lauf- und Lesepfad, damit beide nie auseinanderlaufen."""
    if project.category_method is CategoryMethod.EYE:
        category_model: str | None = None
        category_is_default = False
    else:
        category_model = project.category_model or settings.resolved_landmark_model()
        category_is_default = project.category_model is None
    landmark_model = project.landmark_model or settings.resolved_landmark_model()
    return category_model, category_is_default, landmark_model, project.landmark_model is None


def resolve_model_choice(project: Project) -> ResolvedModelChoice:
    """Die wirksame Wahl eines Projekts - einmal je Auslösung, danach durchgereicht.

    `NULL` in `category_model`/`landmark_model` heisst Installationsvorgabe und wird hier zum
    konkreten Modellwert. Ein ausdruecklich gespeicherter Wert folgt einer spaeteren Aenderung der
    Vorgabe nicht; nur `NULL` folgt ihr."""
    category_model, category_is_default, landmark_model, landmark_is_default = _stored_values(
        project
    )
    category_provider = None if category_model is None else _provider_or_raise(category_model)

    return ResolvedModelChoice(
        category_method=project.category_method,
        category_model=category_model,
        category_provider=category_provider,
        landmark_model=landmark_model,
        landmark_provider=_provider_or_raise(landmark_model),
        category_is_default=category_is_default,
        landmark_is_default=landmark_is_default,
    )


def describe_model_choice(project: Project) -> ModelChoiceView:
    """Die wirksame Wahl fuer LESEPFAEDE - ohne zu werfen (siehe `ModelChoiceView`)."""
    category_model, category_is_default, landmark_model, landmark_is_default = _stored_values(
        project
    )
    return ModelChoiceView(
        category_method=project.category_method,
        category_model=category_model,
        category_provider=(
            None if category_model is None else provider_for_vision_model(category_model)
        ),
        landmark_model=landmark_model,
        landmark_provider=provider_for_vision_model(landmark_model),
        category_is_default=category_is_default,
        landmark_is_default=landmark_is_default,
    )
