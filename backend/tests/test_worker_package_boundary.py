"""Die Paketgrenze des Workers (Spec 0647, ADR 0149 Punkt 2 und 6).

Seit dem Split ist `photosort.worker` ein Paket mit 15 Dateien. Die Grenze, die den Split
ueberhaupt traegt: von AUSSEN sieht man nur `photosort.worker` und die Namen, die es anbietet -
keine Datei dahinter. Sonst haengt jeder Aufrufer an einer Ablage, die sich beim naechsten
Aufteilen wieder aendert.

Dazu die zweite Haelfte: die Tests duerfen eine Datei des Pakets ansprechen, um einen Namen
umzuhaengen (Patch-Ziel) - aber sie laufen nicht durch sie hindurch.
"""

from __future__ import annotations

import ast
from pathlib import Path

import photosort.worker as worker
from tests.import_closure import SRC_DIR

_PAKET = "photosort.worker"
_PAKETDATEI = SRC_DIR / "photosort" / "worker"
_TESTS = Path(__file__).resolve().parent


def _quelldateien() -> list[Path]:
    """Alle Dateien unter `src/photosort` AUSSERHALB des Worker-Pakets."""
    return sorted(
        path for path in (SRC_DIR / "photosort").rglob("*.py") if _PAKETDATEI not in path.parents
    )


def _untermodul_importe(tree: ast.AST) -> set[str]:
    """Importe, die ein UNTERMODUL des Pakets adressieren (`photosort.worker.<etwas>`)."""
    gefunden: set[str] = set()
    for knoten in ast.walk(tree):
        if isinstance(knoten, ast.Import):
            gefunden.update(
                alias.name for alias in knoten.names if alias.name.startswith(f"{_PAKET}.")
            )
        elif isinstance(knoten, ast.ImportFrom) and knoten.module is not None:
            if knoten.module.startswith(f"{_PAKET}."):
                gefunden.add(knoten.module)
    return gefunden


def test_the_source_tree_outside_the_package_imports_no_submodule() -> None:
    """Kein Modul ausserhalb des Pakets importiert eine Datei des Pakets: aufgerufen wird
    `photosort.worker`, nicht `photosort.worker.scan`."""
    treffer = {
        str(path.relative_to(SRC_DIR)): _untermodul_importe(ast.parse(path.read_text("utf-8")))
        for path in _quelldateien()
    }

    assert {datei: funde for datei, funde in treffer.items() if funde} == {}


def _untermodul_aliasse(tree: ast.AST) -> set[str]:
    """Die Namen, unter denen eine Testdatei ein Untermodul des Pakets anspricht."""
    module = {path.stem for path in _PAKETDATEI.rglob("*.py")} | {"_criterion"}
    aliasse: set[str] = set()
    for knoten in ast.walk(tree):
        if isinstance(knoten, ast.ImportFrom) and knoten.module is not None:
            for alias in knoten.names:
                if knoten.module.startswith(f"{_PAKET}."):
                    aliasse.add(alias.asname or alias.name)
                elif knoten.module == _PAKET and alias.name in module:
                    aliasse.add(alias.asname or alias.name)
    return aliasse


def test_a_test_addresses_a_submodule_only_to_rename_a_name() -> None:
    """In `backend/tests` erscheint ein Untermodul nur als Adresse eines Namens: jeder Zugriff
    geht GENAU eine Ebene tief (`datei.name`) - kein Durchgriff in eine Struktur dahinter und
    kein Aufruf der Datei selbst."""
    verstoesse: dict[str, list[str]] = {}
    for pfad in sorted(_TESTS.rglob("*.py")):
        tree = ast.parse(pfad.read_text(encoding="utf-8"))
        aliasse = _untermodul_aliasse(tree)
        if not aliasse:
            continue
        tiefen = {
            knoten.attr
            for knoten in ast.walk(tree)
            if isinstance(knoten, ast.Attribute)
            and isinstance(knoten.value, ast.Attribute)
            and isinstance(knoten.value.value, ast.Name)
            and knoten.value.value.id in aliasse
        }
        if tiefen:
            verstoesse[pfad.name] = sorted(tiefen)

    assert verstoesse == {}


def test_every_imported_worker_name_is_offered_by_the_package() -> None:
    """Die beobachtete Namensmenge: was irgendwo in `src/` und `backend/tests` per
    `from photosort.worker import <name>` geholt wird, steht in `__all__` und ist aufloesbar.
    Ein Name, den nur die Datei dahinter kennt, waere wieder eine Ablage-Abhaengigkeit."""
    beobachtet: set[str] = set()
    for wurzel in (SRC_DIR / "photosort", _TESTS):
        for pfad in wurzel.rglob("*.py"):
            for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
                if isinstance(knoten, ast.ImportFrom) and knoten.module == _PAKET:
                    beobachtet.update(alias.name for alias in knoten.names)
    beobachtet -= {pfad.stem for pfad in _PAKETDATEI.rglob("*.py")} | {"_criterion"}

    assert beobachtet
    assert beobachtet <= set(worker.__all__), sorted(beobachtet - set(worker.__all__))
    assert all(hasattr(worker, name) for name in worker.__all__)


def test_the_package_offers_the_entry_point_unchanged() -> None:
    """Der Startbefehl `python -m arq photosort.worker.WorkerSettings` bleibt: der Einstiegspunkt
    ist ein NAME am Paket, keine Datei."""
    assert hasattr(worker, "WorkerSettings")
    assert worker.WorkerSettings.__module__ == _PAKET
