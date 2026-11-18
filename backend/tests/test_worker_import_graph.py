"""Der Import-Graph des Worker-Pakets (Spec 0647, ADR 0149) - statisch ueber den Syntaxbaum.

Warum AST und nicht echter Import: der Laufzeitimport zieht Detektoren, Cloud-Clients und Modelle
mit und waere im Testprozess bereits durch die Testdatei selbst verunreinigt (dasselbe Muster wie
`tests/import_closure.py`).

Geprueft wird der LAUFZEIT-Graph: ein `if TYPE_CHECKING:`-Block erzeugt keinen Import und damit
keinen Zyklus. Die beiden Phasen `landmark`/`local` lesen `ModelSet` genau so - nur der Typpruefer
sieht die Kante.
"""

from __future__ import annotations

import ast
import graphlib
from pathlib import Path

from tests.import_closure import SRC_DIR, package_files

_PAKET = "photosort.worker"

# Die acht Lauf-Einstiegspunkte, je einer je Lauf-Datei. Sieben davon sind die Coroutine hinter
# einem arq-Job, der achte ist der Cron des Fortschritts-Watchdogs.
_LAUF_EINSTIEGSPUNKTE = (
    "run_classification_review",
    "run_project_scan",
    "run_project_scoring",
    "run_classification",
    "run_export",
    "run_criterion_scoring",
    "run_remote_category_classification",
    "reap_stalled_runs",
)

# Die Lauf-Dateien und die fuenf Kriterien-Phasen - ausgeschrieben, damit eine neue Datei bewusst
# hier eingetragen werden muss, statt still unter die erlaubten Kanten zu fallen.
_LAUF_DATEIEN = (
    "classification",
    "classification_review",
    "criterion_scoring",
    "export",
    "remote_categories",
    "scan",
    "scoring",
    "stall_reaper",
)
_PHASEN = ("eye", "landmark", "local", "persons", "ranking")
_BASEN = ("_criterion", "_runs")

_ERLAUBTE_KANTEN = frozenset(
    # Der Einstiegspunkt importiert jedes Untermodul - daran haengt `import photosort.worker`.
    {(_PAKET, f"{_PAKET}.{name}") for name in _LAUF_DATEIEN}
    | {(_PAKET, f"{_PAKET}._criterion.{phase}") for phase in ("local", "ranking")}
    | {(_PAKET, f"{_PAKET}._runs")}
    # Jede Lauf-Datei und jede Phase darf die gemeinsame Schicht benutzen.
    | {
        (f"{_PAKET}.{name}", f"{_PAKET}._runs")
        for name in _LAUF_DATEIEN + tuple(f"_criterion.{phase}" for phase in _PHASEN)
    }
    # `landmark` und `local` schreiben Kriterienzeilen ueber die Basis - und benutzen keine
    # andere Phase. `eye`, `persons` und `ranking` brauchen die Basis nicht.
    | {
        (f"{_PAKET}.{name}", f"{_PAKET}._criterion")
        for name in ("_criterion.landmark", "_criterion.local", "criterion_scoring")
    }
    # Der Kriterien-Lauf orchestriert seine vier Phasen (die Eye-Phase nicht: sie liegt vor ihm).
    | {
        (f"{_PAKET}.criterion_scoring", f"{_PAKET}._criterion.{phase}")
        for phase in ("landmark", "local", "persons", "ranking")
    }
    # Der Prueflauf ist ein eigener Lauf: er benutzt die gemeinsame Schicht und die lokale
    # Kriterienphase, keinen anderen Lauf.
    | {
        (f"{_PAKET}.classification_review", f"{_PAKET}._runs"),
        (f"{_PAKET}.classification_review", f"{_PAKET}._criterion.local"),
    }
    # ... und der verkettete Klassifizierungslauf die beiden anderen Laeufe samt Eye-Phase.
    | {
        (f"{_PAKET}.classification", f"{_PAKET}.criterion_scoring"),
        (f"{_PAKET}.classification", f"{_PAKET}.remote_categories"),
        (f"{_PAKET}.classification", f"{_PAKET}._criterion.eye"),
    }
)


def _module_name(path: Path) -> str:
    """Der Modulname einer Quelldatei unter `src/`; `__init__.py` faellt auf das Paket zurueck."""
    parts = path.relative_to(SRC_DIR).with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _paketmodule() -> dict[str, Path]:
    return {_module_name(path): path for path in package_files(_PAKET)}


def _ist_typpruefung(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def _runtime_importe(path: Path, paketmodule: dict[str, Path]) -> set[str]:
    """Die paketinternen Importe EINER Datei, ohne `if TYPE_CHECKING:`-Bloecke.

    `from photosort.worker._criterion import CriterionRunContext` zaehlt nur als Kante auf das
    Untermodul; ein Name, der selbst ein Modul ist (`from photosort.worker import scan`), zaehlt
    als Kante auf dieses Modul.
    """
    offen: list[ast.AST] = [ast.parse(path.read_text(encoding="utf-8"))]
    gefunden: set[str] = set()
    while offen:
        knoten = offen.pop()
        if isinstance(knoten, ast.If) and _ist_typpruefung(knoten.test):
            continue
        if isinstance(knoten, ast.Import):
            gefunden.update(alias.name for alias in knoten.names if alias.name.startswith(_PAKET))
        elif isinstance(knoten, ast.ImportFrom) and knoten.module is not None:
            if knoten.module.startswith(_PAKET):
                gefunden.add(knoten.module)
                gefunden.update(
                    f"{knoten.module}.{alias.name}"
                    for alias in knoten.names
                    if f"{knoten.module}.{alias.name}" in paketmodule
                )
        offen.extend(ast.iter_child_nodes(knoten))
    return gefunden


def _kanten() -> dict[str, set[str]]:
    paketmodule = _paketmodule()
    return {modul: _runtime_importe(pfad, paketmodule) for modul, pfad in paketmodule.items()}


def test_the_package_has_the_expected_files() -> None:
    """Gegenprobe gegen den Walker selbst: findet `package_files` nichts, waeren alle Aussagen
    dieser Datei leer erfuellt."""
    assert set(_paketmodule()) == {
        _PAKET,
        *{f"{_PAKET}.{name}" for name in _BASEN + _LAUF_DATEIEN},
        *{f"{_PAKET}._criterion.{phase}" for phase in _PHASEN},
    }


def test_the_import_graph_is_acyclic() -> None:
    """Kein Zyklus im Laufzeit-Graph: sonst haenge `import photosort.worker` von der
    Importreihenfolge ab, und ein Teilimport waere ein `ImportError` an einer Stelle, die mit der
    Ursache nichts zu tun hat."""
    graphlib.TopologicalSorter(_kanten()).prepare()


def test_only_the_chaining_run_imports_another_run() -> None:
    """GENAU EINE Lauf-Datei importiert eine andere: `classification.py` verkettet. Jede weitere
    Kante machte aus dem einen Einstiegspunkt wieder ein Netz, in dem ein Lauf einen zweiten
    startet - der Grund, aus dem `run_classification` und nicht `WorkerSettings` die Reihenfolge
    kennt."""
    paketmodule = _paketmodule()
    laufmodule = {f"{_PAKET}.{name}" for name in _LAUF_DATEIEN}
    kanten = {
        (quelle, ziel)
        for quelle in laufmodule
        for ziel in _runtime_importe(paketmodule[quelle], paketmodule)
        if ziel in laufmodule
    }

    assert kanten == {
        (f"{_PAKET}.classification", f"{_PAKET}.criterion_scoring"),
        (f"{_PAKET}.classification", f"{_PAKET}.remote_categories"),
    }


def test_every_entry_point_is_defined_exactly_once() -> None:
    """Jeder der acht Lauf-Einstiegspunkte steht in GENAU EINER Datei: eine zweite Definition
    waere ein zweiter Lauf unter demselben Namen, und der arq-Job zeigte auf eine beliebige."""
    gefunden: dict[str, list[str]] = {name: [] for name in _LAUF_EINSTIEGSPUNKTE}
    for modul, pfad in _paketmodule().items():
        for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.AsyncFunctionDef | ast.FunctionDef):
                if knoten.name in gefunden:
                    gefunden[knoten.name].append(modul)

    assert gefunden == {
        "run_project_scan": [f"{_PAKET}.scan"],
        "run_project_scoring": [f"{_PAKET}.scoring"],
        "run_classification": [f"{_PAKET}.classification"],
        "run_export": [f"{_PAKET}.export"],
        "run_criterion_scoring": [f"{_PAKET}.criterion_scoring"],
        "run_remote_category_classification": [f"{_PAKET}.remote_categories"],
        "reap_stalled_runs": [f"{_PAKET}.stall_reaper"],
        "run_classification_review": [f"{_PAKET}.classification_review"],
    }


def test_the_entry_point_reaches_every_submodule() -> None:
    """`import photosort.worker` zieht jedes Untermodul mit - das ist die Zusage, an der die
    Namensflaeche des Einstiegspunkts haengt.

    Nicht jede Datei wird direkt adressiert: die Phasen `eye`, `landmark`, `persons` stehen
    hinter ihren Laeufen. Erwartet wird deshalb die TRANSITIVE Erreichbarkeit vom Einstiegspunkt,
    nicht die Kante von der `__init__.py` aus.

    `_criterion` selbst ist die INNERE Basis (Run-Kontext, Kriterienzeilen) und bietet keinen
    Namen an, den der Einstiegspunkt fuehrt; sie wird deshalb nicht erwartet."""
    paketmodule = _paketmodule()
    kanten = _kanten()
    erreicht = {_PAKET}
    offen = [_PAKET]
    while offen:
        for ziel in kanten[offen.pop()]:
            if ziel in paketmodule and ziel not in erreicht:
                erreicht.add(ziel)
                offen.append(ziel)

    assert {modul for modul in paketmodule if modul not in (_PAKET, f"{_PAKET}._criterion")} <= (
        erreicht
    )


def test_the_edges_are_the_expected_ones() -> None:
    """Die Kantenmenge GLEICH, nicht als Teilmenge: eine neue Kante ist eine neue Abhaengigkeit
    zwischen zwei Laeufen und muss hier bewusst eingetragen werden."""
    gemessen = {(quelle, ziel) for quelle, ziele in _kanten().items() for ziel in ziele}

    assert gemessen == _ERLAUBTE_KANTEN
