"""Statischer Import-Graph des Quellbaums - geteilt von allen Tests, die "dieses Modul ist von
der laufenden Anwendung aus nicht erreichbar" festhalten.

Bewusst kein `test_*`-Modul (wird nicht eingesammelt): der Walker wird von
`test_demo_state.py` und `test_place_probe.py` gemeinsam gebraucht (Muster `project_graph.py`).
Eine zweite Fassung liefe auseinander, und ein Waechter, der etwas anderes laeuft als der
danebenstehende, ist kein Waechter.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"


def module_file(module: str) -> Path | None:
    """Die Quelldatei eines `photosort.*`-Moduls, oder `None` fuer alles ausserhalb des Baums."""
    relative = module.replace(".", "/")
    for candidate in (SRC_DIR / f"{relative}.py", SRC_DIR / relative / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def import_closure(entry_module: str) -> set[str]:
    """Statischer Import-Graph des Quellbaums ab `entry_module`, auf `photosort.*` beschraenkt.

    Bewusst per AST statt per echtem Import: der Laufzeit-Import von `photosort.main` zieht
    mediapipe/onnxruntime mit und waere nur in einem Subprozess aussagekraeftig (`sys.modules` ist
    im Testprozess bereits durch die Testdatei selbst verunreinigt)."""
    seen: set[str] = set()
    pending = [entry_module]
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        path = module_file(module)
        if path is None:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                pending.extend(
                    alias.name for alias in node.names if alias.name.startswith("photosort")
                )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                if node.module.startswith("photosort"):
                    pending.append(node.module)
                    # "from photosort.api import projects" - der Name kann ein Untermodul sein.
                    pending.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return seen


def imported_root_packages(module: str) -> set[str]:
    """Die WURZELNAMEN aller Importe EINES Moduls - `photosort.*` eingeschlossen.

    Getrennt von `import_closure` oben, weil die Frage eine andere ist: dort "welche eigenen
    Module haengen daran", hier "welche fremden Pakete beruehrt diese Datei ueberhaupt". Ein
    Modul ohne Quelldatei liefert die leere Menge."""
    path = module_file(module)
    if path is None:
        return set()
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots
