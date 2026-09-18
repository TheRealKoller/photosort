"""Der Formwaechter gegen jede Schreibform in einem Syntaxbaum - geteilt von allen Tests, die
"dieses Modul schreibt nichts" festhalten.

Bewusst kein `test_*`-Modul (wird nicht eingesammelt): `test_place_probe.py` und
`test_event_probe.py` brauchen ihn gemeinsam (Muster `import_closure.py`). Eine zweite Fassung
liefe auseinander, und ein Waechter, der etwas anderes prueft als der danebenstehende, ist kein
Waechter.

Die Mikrotests je Schreibform und die Positiv-Gegenproben stehen in
`test_place_probe.py::TestTheWriteGuardItself`: Ohne sie sagte ein leeres Ergebnis am echten Modul
nichts - ein Waechter, der nichts erkennt, ist immer gruen.
"""

from __future__ import annotations

import ast

# Die Schreibformen, gegen die der Waechter antritt. Attributaufrufe (`session.add(...)`) und
# blanke Namen (`insert(...)` aus einem `from sqlalchemy import insert`) getrennt, weil `delete`
# in beiden Formen vorkommt und nur die Kombination beide Wege deckt.
_WRITING_METHODS = frozenset({"add", "add_all", "merge", "delete", "commit", "flush"})
_WRITING_CONSTRUCTORS = frozenset({"insert", "update", "delete"})
_WRITING_NAMES = _WRITING_METHODS | _WRITING_CONSTRUCTORS
_DML_KEYWORDS = ("insert ", "update ", "delete ", "drop ", "alter ", "create ", "truncate ")


def write_statements(tree: ast.AST) -> list[str]:
    """Jede SCHREIBFORM in einem Syntaxbaum, als lesbare Liste.

    Bewusst ueber die FORM statt ueber ein Verhalten: ein Laufvergleich allein bestuende gegen
    einen Schreibpfad, den die Testlage nicht betritt (ein Zweig hinter einem nicht gesetzten
    Schalter, ein Fehlerpfad). Umgekehrt bestuende dieser Waechter allein gegen ein Modul, das
    ueber eine Hilfsfunktion schreibt - deshalb tragen beide zusammen, keiner allein.

    ANGEWANDT WIRD ER JE MODUL, nie ueber einen Import-Graphen: ueber die Import-Huelle eines
    Messkommandos schluege er auf `events.py`, `selection.py` und `geonames.py` an (gleichnamige
    Sammlungs-Methoden, falsch positiv) und wuerde dann entschaerft - und mit ihm die Zusage."""
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in _WRITING_NAMES:
            # Auch die Attributform der Konstruktoren (`sa.insert(...)`): ein Import unter Alias
            # waere sonst der stille Weg an diesem Waechter vorbei. Der Preis ist, dass ein
            # geprueftes Modul auf die gleichnamigen Sammlungs-Methoden (`set.add`,
            # `dict.update`) verzichten muss - eine kleine Auflage gegen eine lueckenlose Zusage.
            found.append(f"{node.func.attr}()")
        elif isinstance(node.func, ast.Name) and node.func.id in _WRITING_CONSTRUCTORS:
            found.append(f"{node.func.id}()")
        elif isinstance(node.func, ast.Name) and node.func.id == "text":
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    lowered = argument.value.lstrip().lower()
                    if lowered.startswith(_DML_KEYWORDS):
                        found.append("text(<DML>)")
    return found
