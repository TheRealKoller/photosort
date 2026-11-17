"""Keine Funktion der beiden Pakete ueber 200 Zeilen (Spec 0647, Zusicherung AK5).

Die Zerlegung der beiden frueheren Monolith-Module in Pakete ist eine Ablage-Aenderung, die ein
Verhaltenstest nicht bemerkt: Ein Rueckfall in eine 643-Zeilen-Funktion antwortet byte-gleich und
ist gruen. Die Zusage ist deshalb selbst die Messung - gezaehlt wird im Syntaxbaum, je Funktion,
gemessen von der ersten Dekoratorzeile bis `end_lineno`.

Verschachtelte Funktionen werden nicht mitgezaehlt: Sie sind Teil ihrer umgebenden Funktion, und
ihre Laenge stuende zweimal in der Bilanz. Was zaehlt, ist die Einheit, die jemand beim Lesen als
"diese Funktion ist zu gross" bezeichnet.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.import_closure import package_files

_LIMIT = 200
_PACKAGES = ("photosort.worker", "photosort.api.photos")


def _measured_functions() -> list[tuple[str, str, int]]:
    """Je Funktion `(Datei, Name, Zeilen)`; Dekoratoren zaehlen mit, verschachtelte nicht."""
    measured: list[tuple[str, str, int]] = []
    for module in _PACKAGES:
        for path in package_files(module):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                if any(
                    isinstance(parent, ast.FunctionDef | ast.AsyncFunctionDef)
                    for parent in ast.walk(tree)
                    if parent is not node and node in ast.walk(parent)
                ):
                    continue
                start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
                measured.append(
                    (
                        str(path.relative_to(Path(__file__).resolve().parents[1] / "src")),
                        node.name,
                        node.end_lineno - start + 1,
                    )
                )
    return measured


_FUNCTIONS = _measured_functions()


class TestNoFunctionGrowsBackIntoAMonolith:
    def test_the_measurement_covers_both_packages(self) -> None:
        """Selbstschutz (a): eine leergelaufene Messung besteht jede Obergrenze. Beide Pakete
        muessen Dateien beitragen, und zwar mehr als eine Handvoll Funktionen."""
        files = {datei for datei, _name, _length in _FUNCTIONS}
        packages = {datei.split("/")[1] for datei in files}

        assert packages == {"worker", "api"}
        assert len(_FUNCTIONS) > 40

    def test_the_measurement_sees_synchronous_and_asynchronous_functions(self) -> None:
        """Selbstschutz (b): nur `async def` zu zaehlen liesse jede synchrone Hilfsfunktion
        durchfallen - gerade die Umwandlung in `_conversion.py` ist synchron."""
        quelle = _FUNCTIONS
        tree = ast.parse(
            (
                Path(__file__).resolve().parent.parent
                / "src"
                / "photosort"
                / "api"
                / "photos"
                / "_conversion.py"
            ).read_text(encoding="utf-8")
        )
        synchron = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and not isinstance(node, ast.AsyncFunctionDef)
        }

        assert synchron
        assert synchron <= {name for _datei, name, _length in quelle}

    @pytest.mark.parametrize(
        ("datei", "name", "length"),
        _FUNCTIONS,
        ids=[f"{datei}::{name}" for datei, name, _length in _FUNCTIONS],
    )
    def test_no_function_exceeds_the_limit(self, datei: str, name: str, length: int) -> None:
        assert length <= _LIMIT, f"{datei}::{name} hat {length} Zeilen (Grenze {_LIMIT})"
