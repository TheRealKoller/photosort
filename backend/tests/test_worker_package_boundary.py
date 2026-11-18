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


_API_PAKET = "photosort.api.photos"
_API_PAKETDATEI = SRC_DIR / "photosort" / "api" / "photos"


def _api_quelldateien() -> list[Path]:
    """Alle Dateien unter `src/photosort` AUSSERHALB des Pakets `api/photos`."""
    return sorted(
        path
        for path in (SRC_DIR / "photosort").rglob("*.py")
        if _API_PAKETDATEI not in path.parents
    )


def _api_untermodul_importe(tree: ast.AST) -> set[str]:
    """Importe, die ein UNTERMODUL von `photosort.api.photos` adressieren."""
    gefunden: set[str] = set()
    for knoten in ast.walk(tree):
        if isinstance(knoten, ast.Import):
            gefunden.update(
                alias.name for alias in knoten.names if alias.name.startswith(f"{_API_PAKET}.")
            )
        elif isinstance(knoten, ast.ImportFrom) and knoten.module is not None:
            if knoten.module.startswith(f"{_API_PAKET}."):
                gefunden.add(knoten.module)
    return gefunden


def test_the_source_tree_outside_the_photos_package_imports_no_submodule() -> None:
    """Dieselbe Grenze fuer die Endpunkte: `photosort.api.photos` ist von aussen ein Name, die
    sechs Gruppen-Router sind es nicht. Ein Aufrufer, der `photosort.api.photos.image` importiert,
    haengt an einer Ablage, die die naechste Umschichtung nicht ueberlebt."""
    treffer = {
        str(path.relative_to(SRC_DIR)): _api_untermodul_importe(ast.parse(path.read_text("utf-8")))
        for path in _api_quelldateien()
    }

    assert {datei: funde for datei, funde in treffer.items() if funde} == {}


def test_a_test_addresses_a_photos_submodule_only_to_rename_a_name() -> None:
    """Im Testbaum gilt dieselbe Beschraenkung wie beim Worker-Paket: ein Untermodul erscheint
    nur als Adresse eines Namens, genau eine Ebene tief."""
    module = {path.stem for path in _API_PAKETDATEI.rglob("*.py")}
    verstoesse: dict[str, list[str]] = {}
    for pfad in sorted(_TESTS.rglob("*.py")):
        tree = ast.parse(pfad.read_text(encoding="utf-8"))
        aliasse: set[str] = set()
        for knoten in ast.walk(tree):
            if isinstance(knoten, ast.ImportFrom) and knoten.module is not None:
                for alias in knoten.names:
                    if knoten.module.startswith(f"{_API_PAKET}."):
                        aliasse.add(alias.asname or alias.name)
                    elif knoten.module == _API_PAKET and alias.name in module:
                        aliasse.add(alias.asname or alias.name)
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


def test_every_imported_photos_name_is_offered_by_the_package() -> None:
    """Was irgendwo in `src/` und `backend/tests` per `from photosort.api.photos import <name>`
    geholt wird, steht in `__all__` und ist aufloesbar - sonst ist die Schnittstelle beim Split
    still geschrumpft."""
    import photosort.api.photos as photos

    beobachtet: set[str] = set()
    for wurzel in (SRC_DIR / "photosort", _TESTS):
        for pfad in wurzel.rglob("*.py"):
            for knoten in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
                if isinstance(knoten, ast.ImportFrom) and knoten.module == _API_PAKET:
                    beobachtet.update(alias.name for alias in knoten.names)
    beobachtet -= {pfad.stem for pfad in _API_PAKETDATEI.rglob("*.py")}

    assert beobachtet
    assert beobachtet <= set(photos.__all__), sorted(beobachtet - set(photos.__all__))
    assert all(hasattr(photos, name) for name in photos.__all__)


def test_the_photos_package_offers_the_entry_point_unchanged() -> None:
    """`main.py` bindet `photos.router` ein, `api/duplicate_decisions.py` importiert aus dem
    Paket: der Einstiegspunkt ist ein NAME am Paket, keine Datei."""
    import photosort.api.photos as photos

    assert type(photos.router).__name__ == "APIRouter"
    assert photos.router.dependencies == []


_API_GRUPPEN = frozenset(
    {"album_draft", "album_selection", "ausschuss", "draft_exchange", "duplicate_groups", "image"}
)
_API_GEMEINSAM = frozenset({"_conversion", "_reads"})


def test_no_photo_endpoint_group_imports_another_group() -> None:
    """Die sechs Themengruppen der Aufnahmen-Ansicht importieren einander nicht; gemeinsam
    Genutztes kommt aus `_conversion`/`_reads`. Ein Querimport waere der Anfang einer neuen
    Sammelstelle: die Gruppen waeren dann nur noch Etiketten ueber einem verteilten Modul."""
    dateien = {pfad.stem for pfad in _API_PAKETDATEI.glob("*.py")}
    assert dateien == _API_GRUPPEN | _API_GEMEINSAM | {"__init__"}, (
        "Die Aufzaehlung der Gruppen ist nicht die Dateiliste des Pakets - neue Datei eintragen "
        "oder Gruppe zuordnen."
    )

    querimporte: dict[str, list[str]] = {}
    for gruppe in sorted(_API_GRUPPEN):
        tree = ast.parse((_API_PAKETDATEI / f"{gruppe}.py").read_text(encoding="utf-8"))
        ziele: set[str] = set()
        for knoten in ast.walk(tree):
            if isinstance(knoten, ast.ImportFrom) and knoten.module is not None:
                if knoten.module.startswith(f"{_API_PAKET}."):
                    ziele.add(knoten.module.rsplit(".", 1)[1])
                elif knoten.level and knoten.module in _API_GRUPPEN:
                    ziele.add(knoten.module)
        if ziele & _API_GRUPPEN:
            querimporte[gruppe] = sorted(ziele & _API_GRUPPEN)

    assert querimporte == {}


def _paket_aliasse(tree: ast.AST, paket: str) -> set[str]:
    """Die Namen, unter denen eine Testdatei das PAKET selbst haelt (`import photosort.worker as w`)."""
    return {
        alias.asname or alias.name.split(".")[0]
        for knoten in ast.walk(tree)
        if isinstance(knoten, ast.Import)
        for alias in knoten.names
        if alias.name == paket
    }


def _fremde_paket_patches(tree: ast.AST, paket: str, eigene: set[str]) -> list[str]:
    """Die Namen, die eine Testdatei auf dem PAKET umhaengt, obwohl `__init__.py` sie nur bindet."""
    aliasse = _paket_aliasse(tree, paket)
    return sorted(
        knoten.args[1].value
        for knoten in ast.walk(tree)
        if isinstance(knoten, ast.Call)
        and isinstance(knoten.func, ast.Attribute)
        and knoten.func.attr == "setattr"
        and len(knoten.args) >= 2
        and isinstance(knoten.args[0], ast.Name)
        and knoten.args[0].id in aliasse
        and isinstance(knoten.args[1], ast.Constant)
        and isinstance(knoten.args[1].value, str)
        and knoten.args[1].value not in eigene
    )


def test_a_test_patches_no_name_through_the_package() -> None:
    """Ein Patch auf dem Paket trifft nur, was `__init__.py` SELBST definiert (den Einstiegspunkt).
    Ein geteilter Name aus `_runs` oder eine Funktion eines Untermoduls wird dort nur gebunden: der
    Patch waere still wirkungslos, weil jeder Aufrufer seine eigene Bindung nachschlaegt. Gepatcht
    wird deshalb an der Nachschlagestelle (ADR 0149 Punkt 3)."""
    probe = ast.parse(
        "import photosort.worker as w\nmonkeypatch.setattr(w, 'set_phase', lambda *a, **k: None)\n"
    )
    assert _fremde_paket_patches(probe, _PAKET, set()) == ["set_phase"]

    verstoesse: dict[str, list[str]] = {}
    gelesen = False
    for paket, paketdatei in ((_PAKET, _PAKETDATEI), (_API_PAKET, _API_PAKETDATEI)):
        eigene = {
            knoten.name
            for knoten in ast.parse((paketdatei / "__init__.py").read_text(encoding="utf-8")).body
            if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        for pfad in sorted(_TESTS.rglob("*.py")):
            tree = ast.parse(pfad.read_text(encoding="utf-8"))
            gelesen = gelesen or bool(_paket_aliasse(tree, paket))
            fremd = _fremde_paket_patches(tree, paket, eigene)
            if fremd:
                verstoesse[f"{pfad.name}:{paket}"] = fremd

    assert gelesen
    assert verstoesse == {}
