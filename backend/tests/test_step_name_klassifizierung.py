"""specs/features/0566-ablauf-uebersicht.md - der dritte Schritt heisst an jeder sichtbaren Stelle
"Klassifizierung".

Mechanischer Beleg ueber den Syntaxbaum: Keine Zeichenkette in `backend/src/photosort` traegt den
alten Namen - ausgenommen Docstrings und Kommentare (nie sichtbar; Kommentare erreicht der
Syntaxbaum gar nicht) sowie die reinen Betreiber-CLIs `*_probe.py` ohne Oberflaeche. Eine Suche
ueber den Quelltext statt ueber den Syntaxbaum fiele auf Kommentare herein.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parent.parent / "src" / "photosort"

# Jede Schreibweise mit anderem Bindestrich (auch weichem Trennstrich) oder Leerraum, jede
# Zusammensetzung, und der fruehere Stand-Zeilen-Wortlaut.
_OLD_NAME = re.compile(r"Kriterien[-\u2010\u2011\u00ad\s]*Bewertung|Kategorie-Bewertung", re.I)


def _docstring_nodes(tree: ast.Module) -> set[int]:
    owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, owners) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                found.add(id(first.value))
    return found


def _offending_strings(source: str) -> list[str]:
    tree = ast.parse(source)
    docstrings = _docstring_nodes(tree)
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and _OLD_NAME.search(node.value)
    ]


def test_no_string_in_the_backend_carries_the_old_step_name() -> None:
    files = [path for path in _SOURCE_ROOT.rglob("*.py") if not path.name.endswith("_probe.py")]
    assert len(files) > 20, "kein Quellbaum gefunden - stimmt der Pfad?"

    hits = {
        str(path.relative_to(_SOURCE_ROOT)): found
        for path in files
        if (found := _offending_strings(path.read_text(encoding="utf-8")))
    }

    assert hits == {}


def test_the_check_finds_the_old_name_in_every_string_form_but_not_in_comments() -> None:
    """Gegenprobe: dieselbe Pruefung schlaegt an Literal, f-String-Teil, zusammengesetzter und
    abweichender Schreibweise an - und schweigt bei Kommentar und Docstring."""
    source = (
        '"""Kriterien-Bewertung im Docstring zaehlt nicht."""\n'
        "# Kriterien-Bewertung im Kommentar zaehlt nicht.\n"
        'a = "Kriterien-Bewertung abgebrochen"\n'
        'b = f"Die {1}. Kriterien\u2011Bewertung"\n'
        'c = "Kriterienbewertung"\n'
        'd = "Kategorie-Bewertung laeuft"\n'
        "def f():\n"
        '    """Kriterien Bewertung im Funktions-Docstring zaehlt nicht."""\n'
        '    return "Zur kriterien bewertung"\n'
    )

    assert sorted(_offending_strings(source)) == [
        ". Kriterien\u2011Bewertung",
        "Kategorie-Bewertung laeuft",
        "Kriterien-Bewertung abgebrochen",
        "Kriterienbewertung",
        "Zur kriterien bewertung",
    ]
