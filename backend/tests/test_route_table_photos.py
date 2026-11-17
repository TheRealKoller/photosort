"""Die Routentabelle der Aufnahmen-Ansicht, eingefroren (Spec 0647, Zusicherungen S1-S3).

Die Aufteilung von `api/photos.py` in ein Paket darf die HTTP-Schnittstelle nicht verschieben:
dieselben zwoelf Operationen, gleiche Methode, gleicher Pfad, gleicher Erfolgs-Statuscode, gleiches
Antwortschema und dieselbe Reihenfolge. Die Reihenfolge ist Teil der Zusage, nicht Kosmetik: eine
statische Route hinter `…/{project_id}/…` faengt sonst den falschen Handler, und die Antwort sieht
plausibel aus.

Warum der Schnappschuss aus `create_app().openapi()` kommt und nicht aus `router.routes`: seit
FastAPI 0.162.1 liefert `include_router` ein `_IncludedRouter`-Objekt ohne `routes`. Eine
Parametrisierung ueber `photos.router.routes` waere leer und der Test still gruen. Dieselbe Ursache
steht hinter `test_auth_guard._protected_router_operations()`, das `photos.router` bewusst NICHT
fuehrt - der Vollstaendigkeitsnachweis fuer die Absicherung steht deshalb hier, am Syntaxbaum.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from photosort.main import create_app
from tests.import_closure import package_files

_PHOTOS_TAG = "photos"

# Die zwoelf Operationen in Registrierungsreihenfolge, je `(Methode, Pfad, Erfolgs-Statuscode,
# Schemaname unqualifiziert)`. `None` steht fuer eine Antwort ohne Antwortschema (`FileResponse`,
# `204`). Ein Eintrag, der aus der Anwendung heraus waechst, prueft nur noch sich selbst - die
# Liste ist Gegenstand der Zusage.
_ROUTES: tuple[tuple[str, str, str, str | None], ...] = (
    ("get", "/projects/{project_id}/album-draft", "200", "AlbumDraftOut"),
    ("get", "/projects/{project_id}/photos", "200", "PhotoListOut"),
    ("get", "/projects/{project_id}/album-selection", "200", "AlbumSelectionOut"),
    ("get", "/projects/{project_id}/duplicate-groups", "200", "DuplicateGroupIndexOut"),
    ("get", "/projects/{project_id}/duplicate-groups/{photo_id}", "200", "DuplicateGroupOut"),
    ("get", "/projects/{project_id}/ausschuss", "200", "AusschussOut"),
    ("get", "/projects/{project_id}/draft-alternatives", "200", "DraftAlternativesOut"),
    ("post", "/projects/{project_id}/draft/exchange", "200", "DraftExchangeOut"),
    ("post", "/projects/{project_id}/draft/exchange/undo", "200", "DraftExchangeUndoOut"),
    ("get", "/photos/{photo_id}/image", "200", None),
    ("put", "/photos/{photo_id}/motif-corrections/{motif_key}", "200", "MotifCorrectionOut"),
    ("delete", "/photos/{photo_id}/motif-corrections/{motif_key}", "204", None),
)

_ROUTER_MODULE = "photosort.api.photos"


@pytest.fixture(scope="module")
def openapi_schema() -> dict[str, Any]:
    schema: dict[str, Any] = create_app().openapi()
    return schema


def _observed(schema: dict[str, Any]) -> tuple[tuple[str, str, str, str | None], ...]:
    """Die Operationen der Aufnahmen-Ansicht aus der Anwendung, in ihrer Reihenfolge."""
    observed: list[tuple[str, str, str, str | None]] = []
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if operation.get("tags") != [_PHOTOS_TAG]:
                continue
            success = next(code for code in operation["responses"] if code.startswith("2"))
            content = operation["responses"][success].get("content", {})
            schema_name: str | None = None
            if content:
                reference = next(iter(content.values()))["schema"].get("$ref")
                schema_name = None if reference is None else reference.rsplit("/", 1)[-1]
            observed.append((method, path, success, schema_name))
    return tuple(observed)


def _package_trees() -> list[tuple[Path, ast.Module]]:
    return [
        (path, ast.parse(path.read_text(encoding="utf-8")))
        for path in package_files(_ROUTER_MODULE)
    ]


def _handler_nodes() -> list[tuple[Path, ast.AsyncFunctionDef | ast.FunctionDef]]:
    """Jede Funktion, die der Paket-Router als Endpunkt dekoriert - ueber den Syntaxbaum."""
    handlers: list[tuple[Path, ast.AsyncFunctionDef | ast.FunctionDef]] = []
    for path, tree in _package_trees():
        for node in tree.body:
            if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
                continue
            if any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "router"
                for decorator in node.decorator_list
            ):
                handlers.append((path, node))
    return handlers


def _has_auth_dependency(node: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    defaults = [*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)]
    return any(
        isinstance(default, ast.Call)
        and isinstance(default.func, ast.Name)
        and default.func.id == "Depends"
        and default.args
        and isinstance(default.args[0], ast.Name)
        and default.args[0].id == "get_current_user"
        for default in defaults
    )


def _router_calls() -> tuple[list[Path], list[Path]]:
    """Die `APIRouter(...)`- und `include_router(...)`-Aufrufe des Pakets, je Datei."""
    routers: list[Path] = []
    inclusions: list[Path] = []
    for path, tree in _package_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "APIRouter":
                routers.append(path)
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "include_router":
                inclusions.append(path)
    return routers, inclusions


class TestTheRouteTableIsFrozen:
    def test_the_frozen_list_holds_the_twelve_operations(self) -> None:
        """Selbstschutz: eine leergelaufene Liste prueft nichts, und die Sollzahl ist selbst die
        Zusage (S3)."""
        assert len(_ROUTES) == 12
        assert len({path for _method, path, _code, _schema in _ROUTES}) == 11

    def test_the_operations_come_in_the_expected_order(
        self, openapi_schema: dict[str, Any]
    ) -> None:
        """Die eigentliche Zusage: Reihenfolge UND Inhalt. Ein Vergleich als Menge liesse genau
        die Vertauschung durch, die eine statische Route hinter einem Pfadparameter verdeckt."""
        assert _observed(openapi_schema) == _ROUTES

    def test_every_operation_keeps_its_photos_tag(self, openapi_schema: dict[str, Any]) -> None:
        """Der Tag traegt die gemeinsame Gruppe; er haengt am Aggregat-Router und nicht an einer
        Endpunktdatei. Faellt er weg, verschwindet die Ansicht aus der Dokumentation."""
        for _method, path, _code, _schema in _ROUTES:
            for operation in openapi_schema["paths"][path].values():
                assert operation.get("tags") == [_PHOTOS_TAG], path


class TestEveryHandlerKeepsItsAuthDependency:
    def test_the_package_has_exactly_the_twelve_handlers(self) -> None:
        """Selbstschutz: eine verschwundene Endpunktfunktion faellt sonst durch, weil die
        Parametrisierung unten kuerzer wird statt rot."""
        assert len(_handler_nodes()) == len(_ROUTES)

    def test_every_decorated_handler_depends_on_the_authenticated_user(self) -> None:
        """S1: die Absicherung der Aufnahmen-Ansicht haengt NUR an diesem Parameter. Ein beim
        Verschieben verlorener Parameter ist still oeffentlich: kein Fehler, keine 401, nur
        Daten."""
        missing = [
            f"{path.name}::{node.name}"
            for path, node in _handler_nodes()
            if not _has_auth_dependency(node)
        ]

        assert missing == []

    def test_no_router_secures_its_operations_for_all_of_them(self) -> None:
        """S2: alle sechs Gruppen-Router und das Aggregat tragen `dependencies == []`. Ohne diesen
        Teil waere S1 durch eine routerweite Absicherung scheinbar erfuellbar - und die
        Fehlerreihenfolge (401 vor 422) aenderte sich still."""
        routers, inclusions = _router_calls()

        # Selbstschutz gegen einen Waechter, der nichts ansieht: sechs Gruppen + Aggregat bzw.
        # sechs Einbindungen.
        assert len(routers) == 7
        assert len(inclusions) == 6

        for path, tree in _package_trees():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                named = (
                    isinstance(node.func, ast.Name) and node.func.id == "APIRouter"
                ) or (isinstance(node.func, ast.Attribute) and node.func.attr == "include_router")
                if not named:
                    continue
                assert all(keyword.arg != "dependencies" for keyword in node.keywords), (
                    f"{path.name}: routerweite Absicherung statt je Endpunkt",
                    node.lineno,
                )
