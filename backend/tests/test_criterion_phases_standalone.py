"""Die fuenf Kriterien-Phasen einzeln (Spec 0647, ADR 0149 Punkt 4).

Die Zusage lautet: jede Phase ist eine EINHEIT, die ohne die uebrigen Phasen laeuft, und jede
bekommt genau die Modelle, die sie braucht. Geprueft wird das statisch ueber den Syntaxbaum (die
Phasen brauchen fuer einen echten Aufruf Datenbank, Projekt und Lauf - was sie dabei an MODELLEN
anfassen, ist aber am Quelltext exakt ablesbar), plus eine Laufzeitprobe fuer den `ModelSet`
selbst: seine Builder sind Vorgabewerte und werden erst beim Aufruf gebaut, nie beim Konstruieren.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from collections.abc import Callable
from dataclasses import fields
from pathlib import Path

import pytest

from photosort.worker.criterion_scoring import ModelSet
from tests.import_closure import SRC_DIR

_PAKET = "photosort.worker"
_PHASEN = (
    "run_local_phase",
    "run_landmark_phase",
    "run_eye_phase",
    "recognize_persons",
    "build_grouping_and_rankings",
)

# Je Phase: die Datei, in der sie steht.
_PHASENDATEI = {
    "run_local_phase": f"{_PAKET}._criterion.local",
    "run_landmark_phase": f"{_PAKET}._criterion.landmark",
    "run_eye_phase": f"{_PAKET}._criterion.eye",
    "recognize_persons": f"{_PAKET}._criterion.persons",
    "build_grouping_and_rankings": f"{_PAKET}._criterion.ranking",
}

# Je Phase: die Modell-Builder, die sie aus dem Modellsatz LIEST. Eine Phase, die einen fremden
# Builder zieht, waere keine Einheit mehr - und ein Patch an ihrem Modulnamen traefe sie nicht.
_GELESENE_BUILDER = {
    "run_local_phase": {
        "build_detector",
        "build_animal_detector",
        "build_classifier",
        "build_aesthetics",
        "build_landmarker",
    },
    "run_landmark_phase": {"build_landmark_client", "build_embedder"},
    "run_eye_phase": set(),
    "recognize_persons": set(),
    "build_grouping_and_rankings": set(),
}

# Je Phase: die Parameter, ueber die sie ihre Modelle bekommt. Eye, Personen und Rangfolge tragen
# ihren Builder als eigenen Parameter; die beiden Kriterien-Phasen bekommen den Modellsatz.
_MODELLPARAMETER = {
    "run_local_phase": {"models"},
    "run_landmark_phase": {"models"},
    "run_eye_phase": {"build_client"},
    "recognize_persons": {"build_analyzer"},
    "build_grouping_and_rankings": {"build_place_resolver", "build_landmark_gazetteer"},
}

# Die zehn Builder des Modellsatzes, ausgeschrieben: ein elfter ist eine neue Modellart im Lauf.
_BUILDER = (
    "build_detector",
    "build_animal_detector",
    "build_classifier",
    "build_aesthetics",
    "build_landmarker",
    "build_landmark_client",
    "build_place_resolver",
    "build_landmark_gazetteer",
    "build_embedder",
    "build_face_analyzer",
)


def _datei(module: str) -> Path:
    return SRC_DIR / Path(*module.split(".")).with_suffix(".py")


def _funktionen(module: str) -> dict[str, ast.AsyncFunctionDef | ast.FunctionDef]:
    tree = ast.parse(_datei(module).read_text(encoding="utf-8"))
    return {
        knoten.name: knoten
        for knoten in ast.walk(tree)
        if isinstance(knoten, ast.AsyncFunctionDef | ast.FunctionDef)
    }


def test_the_model_set_has_exactly_the_ten_builders() -> None:
    """Der Modellsatz ist die EINE Stelle, an der "welche Modelle ein Lauf baut" steht. Zehn
    Builder sind zehn Patch-Punkte; ein elfter muss hier bewusst eingetragen werden."""
    assert [feld.name for feld in fields(ModelSet)] == list(_BUILDER)


def test_a_model_set_of_failing_builders_is_constructed_without_a_call() -> None:
    """Die Builder sind Vorgabewerte und binden beim `def` - sie werden beim KONSTRUIEREN nicht
    aufgerufen. Genau deshalb kann ein Test einen Modellsatz bauen, in dem jeder Builder
    `pytest.fail` ist: keine Phase, die ein Modell nicht braucht, loest ihn aus."""
    models = ModelSet(**{feld.name: _fail(feld.name) for feld in fields(ModelSet)})

    assert all(callable(getattr(models, name)) for name in _BUILDER)
    with pytest.raises(pytest.fail.Exception, match="build_embedder"):
        models.build_embedder()


def _fail(name: str) -> Callable[..., None]:
    def builder(*_args: object) -> None:
        pytest.fail(f"Builder {name} wurde benutzt, obwohl die Phase ihn nicht braucht.")

    return builder


def test_every_phase_is_callable_from_its_own_module() -> None:
    """Jede Phase steht in ihrer EIGENEN Datei und ist von dort importierbar, ohne dass die
    Orchestrierung mitkommt - sonst waere sie nicht einzeln pruefbar."""
    for name, module in _PHASENDATEI.items():
        funktion = getattr(importlib.import_module(module), name)

        assert funktion.__module__ == module
        assert inspect.iscoroutinefunction(funktion)
        assert set(inspect.signature(funktion).parameters) >= _MODELLPARAMETER[name]


def test_no_phase_reads_a_model_it_does_not_take() -> None:
    """Die gelesenen Builder GLEICH der erwarteten Menge: eine Phase, die einen fremden Builder
    zieht, baut ein Modell, das ihr Aufrufer nicht vorgesehen hat."""
    for name, module in _PHASENDATEI.items():
        quelltext = _datei(module).read_text(encoding="utf-8")
        gelesen = {
            knoten.attr
            for knoten in ast.walk(ast.parse(quelltext))
            if isinstance(knoten, ast.Attribute)
            and isinstance(knoten.value, ast.Name)
            and knoten.value.id == "models"
            and knoten.attr in _BUILDER
        }

        assert gelesen == _GELESENE_BUILDER[name], f"{module} liest {sorted(gelesen)}"


def test_no_phase_names_another_phase() -> None:
    """Keine Phase nennt eine andere: die Reihenfolge kennt die Orchestrierung, nicht die
    Phasen. Eine Kante zwischen zwei Phasen machte aus dem einen Lauf wieder ein Netz."""
    for name, module in _PHASENDATEI.items():
        quelltext = _datei(module).read_text(encoding="utf-8")
        genannt = {
            knoten.id for knoten in ast.walk(ast.parse(quelltext)) if isinstance(knoten, ast.Name)
        }

        assert genannt & (set(_PHASEN) - {name}) == set(), module


def test_the_orchestrator_calls_every_phase_exactly_once() -> None:
    """Die Verkettung ist EINE Stelle: `run_criterion_scoring` ruft jede seiner vier Phasen genau
    einmal, `run_classification` die Eye-Phase genau einmal. Zwei Aufrufe im selben Lauf waeren
    zwei Teilschritte unter demselben Phasennamen."""
    gerufen = {
        **_rufe(_funktion(f"{_PAKET}.criterion_scoring", "run_criterion_scoring")),
        **_rufe(_funktion(f"{_PAKET}.classification", "run_classification")),
    }

    assert gerufen == {
        "run_local_phase": 1,
        "run_landmark_phase": 1,
        "recognize_persons": 1,
        "build_grouping_and_rankings": 1,
        "run_eye_phase": 1,
    }


def _funktion(module: str, name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    return _funktionen(module)[name]


def _rufe(funktion: ast.AsyncFunctionDef | ast.FunctionDef) -> dict[str, int]:
    """Zaehlt die Aufrufe der fuenf Phasennamen im Koerper EINER Funktion."""
    gezaehlt: dict[str, int] = {}
    for knoten in ast.walk(funktion):
        if isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name):
            if knoten.func.id in _PHASEN:
                gezaehlt[knoten.func.id] = gezaehlt.get(knoten.func.id, 0) + 1
    return gezaehlt


def test_the_ranking_phase_gets_no_modelset() -> None:
    """Die Rangfolge braucht ORTS-Aufloeser, keine Bildmodelle - sie bekommt zwei Fabriken statt
    des Modellsatzes. Ein `ModelSet` an dieser Stelle waere ein stiller zweiter Bauweg."""
    quelle = _datei(f"{_PAKET}._criterion.ranking").read_text(encoding="utf-8")

    assert "ModelSet" not in quelle
