"""Personendaten und Netzwerk-Clients bleiben getrennt, in beide Richtungen (S6).

`config.py` importiert `cloud_vision`; die Huelle jedes Moduls, das `models`, `db` oder `config`
erreicht, enthaelt damit den Cloud-Client. Transitiv pruefbar ist deshalb nur: die reinen
Personenmodule erreichen nichts davon, und die Cloud-Module erreichen kein Personenmodul. Fuer die
Module mit Datenbankbezug gilt die Aussage je Modul ueber die direkten Importe. Die
Verbindungsstelle beider Seiten ist `worker.py`; dort traegt der Nutzlast-Nachweis in
`test_worker_persons.py`, kein Graph.

`model_assets.py` ist rein, aber KEIN Personenmodul: Es ist das gemeinsame Manifest aller geladenen
Modelldateien, und `label_embedding.py` liest daraus - es liegt deshalb erlaubt im Graphen von
`remote_classification`.
"""

from __future__ import annotations

import ast

import pytest

from tests.import_closure import import_closure, imported_root_packages, module_file

PURE_MODULES = (
    "photosort.face_analysis",
    "photosort.person_matching",
    "photosort.model_assets",
)
PERSON_MODULES = (
    "photosort.face_analysis",
    "photosort.person_matching",
    "photosort.persons",
    "photosort.api.persons",
    "photosort.person_probe",
)
DATABASE_BOUND_PERSON_MODULES = (
    "photosort.persons",
    "photosort.api.persons",
    "photosort.person_probe",
)
NETWORK_MODULES = (
    "photosort.cloud_vision",
    "photosort.landmark",
    "photosort.remote_classification",
)
FORBIDDEN_FOR_PURE = (
    "photosort.models",
    "photosort.db",
    "photosort.config",
    *NETWORK_MODULES,
)
CLOUD_SIDE = (*NETWORK_MODULES, "photosort.classification_prompt")


@pytest.mark.parametrize("module", PURE_MODULES)
def test_a_pure_person_module_reaches_neither_database_nor_network(module: str) -> None:
    closure = import_closure(module)

    assert closure.isdisjoint(FORBIDDEN_FOR_PURE), sorted(closure & set(FORBIDDEN_FOR_PURE))
    assert "httpx" not in {root for entry in closure for root in imported_root_packages(entry)}


@pytest.mark.parametrize("module", DATABASE_BOUND_PERSON_MODULES)
def test_a_database_bound_person_module_imports_no_network_client_directly(module: str) -> None:
    direct = _direct_imports(module)

    assert "httpx" not in imported_root_packages(module)
    assert direct.isdisjoint(NETWORK_MODULES), sorted(direct & set(NETWORK_MODULES))


def _direct_imports(module: str) -> set[str]:
    path = module_file(module)
    assert path is not None, module
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


@pytest.mark.parametrize("module", CLOUD_SIDE)
def test_no_cloud_module_reaches_a_person_module(module: str) -> None:
    closure = import_closure(module)

    assert closure.isdisjoint(PERSON_MODULES), sorted(closure & set(PERSON_MODULES))


def test_the_walker_finds_the_network_client_where_it_is() -> None:
    """Gegenprobe Personen -> Netz: ohne sie bestuende die Zusage auch bei einem Walker, der gar
    nichts findet."""
    assert "photosort.cloud_vision" in import_closure("photosort.config")
    assert "httpx" in imported_root_packages("photosort.cloud_vision")


def test_the_walker_finds_person_modules_where_they_are() -> None:
    """Gegenprobe Cloud -> Personen: `worker.py` verbindet beide Seiten."""
    closure = import_closure("photosort.worker")

    assert "photosort.face_analysis" in closure
    assert "photosort.cloud_vision" in closure
