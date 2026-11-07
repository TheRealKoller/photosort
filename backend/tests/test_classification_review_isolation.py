"""Die Isolation des Prueflaufs (Spec 0616, AC "Isolation" und Edge Case 1).

ZWEI Waechter, keiner traegt allein (Muster `test_place_probe.py::TestTheProbeIsReadOnly`):

- STRUKTUR: der Syntaxbaum des Job-Moduls sagt, welche Modelle dort ueberhaupt als Schreibziel
  stehen KANN. Er bestuende gegen einen Schreibpfad, den die Testlage nicht betritt (Fehlerzweig,
  nicht gesetzter Schalter) - deshalb steht er hier nicht allein.
- VERHALTEN: ein vollstaendiger Bestandsvergleich aller geltenden Tabellen vor und nach einem
  echten Lauf. Er bestuende gegen einen Schreibweg ueber eine Hilfsfunktion, die der
  Syntaxtest nicht als Modellkonstruktor erkennt.

Beide tragen einen Rot-Nachweis (`TestTheStructureGuardItself`): ein Waechter, der nichts
erkennt, ist immer gruen.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.api.projects import _build_classification_estimate
from photosort.classification_review import ERROR_MESSAGES, execute_classification_review
from photosort.db import Base
from photosort.eye_mapping import MAPPING_VERSION
from photosort.models import ClassificationReviewSideKind, PhotoScore, Project, ScanStatus
from photosort.thumbnails import display_path
from photosort.worker import select_remote_category_candidates
from tests.import_closure import module_file
from tests.project_graph import build_project_graph, get_or_create_user
from tests.test_worker_classification_review import (
    FakeEyeClient,
    _add_photo,
    _make_review,
    _payload,
    _side,
)
from tests.write_guard import write_statements

JOB_MODULE = "photosort.classification_review"

# Edge Case 1 der Spec: "geltende Ergebnisse, Fotozustand und die Lauftabellen (samt
# api_calls/failed_calls/cost_usd) bleiben Zeile fuer Zeile unveraendert". Die Liste ist
# absichtlich die Vollmenge der Tabellen, die ein normaler Klassifizierungslauf schreibt - nicht
# nur die, die dieser Job theoretisch anfassen koennte.
GELTENDE_TABELLEN: tuple[str, ...] = (
    "projects",
    "photos",
    "scan_runs",
    "scoring_runs",
    "criterion_scoring_runs",
    "remote_category_classification_runs",
    "photo_scores",
    "photo_criterion_scores",
    "photo_rankings",
    "photo_cloud_vision_errors",
    "photo_motif_assessments",
    "photo_motif_strengths",
    "photo_motif_corrections",
    "photo_album_suitability",
    "photo_eye_results",
    "photo_eye_motif_strengths",
    "photo_eye_fine_labels",
    "photo_local_motif_snapshots",
    "photo_local_motif_snapshot_strengths",
)


# ---------------------------------------------------------------------------------------------
# Der Strukturwaechter
# ---------------------------------------------------------------------------------------------

# Lauf-, Phasen- und Auswahlfunktionen, ueber die der Prueflauf die geltenden Ergebnisse
# anfassen koennte. Die Liste ist eine DENY-Liste: der Job darf diese Namen nirgends aufrufen
# und nirgends importieren - auch nicht ueber eine Attrappe (`module.upsert_assessment`).
VERBOTENE_NAMEN: frozenset[str] = frozenset(
    {
        "upsert_assessment",
        "run_classification",
        "run_criterion_scoring",
        "run_remote_category_classification",
        "_run_eye_phase",
        "select_remote_category_candidates",
        "_build_classification_estimate",
        "_build_grouping_and_rankings",
        "_rebuild_run_selection",
        "build_events",
        "assign_place_names",
    }
)

# Die Schreibformen, die ein Commit braucht. `write_statements` liefert `add()`, `add_all()` und
# `commit()` fuer dieses Modul - jedes `delete`/`update`/`insert`/`text(<DML>)` faellt hier auf.
ERLAUBTE_SCHREIBFORMEN = frozenset({"add()", "add_all()", "commit()"})


def _module_tree(module: str) -> ast.Module:
    path = module_file(module)
    assert path is not None, f"Modul {module} nicht gefunden"
    return ast.parse(path.read_text(encoding="utf-8"))


def _review_model_names() -> frozenset[str]:
    """Die sechs Pruefmodelle - ABGELEITET aus dem Mapper-Register, nicht abgeschrieben.

    Eine Zeichenkettenliste waere eine zweite Wahrheit neben `models.py`; sie liefe still
    auseinander, sobald dort eine Tabelle umbenannt wird."""
    return frozenset(
        mapper.class_.__name__
        for mapper in Base.registry.mappers
        if mapper.local_table.name.startswith("classification_review")
    )


def _imported_model_names(tree: ast.AST) -> frozenset[str]:
    """Die Namen, die das Modul ueberhaupt aus `photosort.models` hereinholt."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "photosort.models":
            names.update(alias.name for alias in node.names)
    return frozenset(names)


def _imported_names(tree: ast.AST) -> frozenset[str]:
    """Alle per `from ... import` hereingeholten Namen, egal aus welchem Modul."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.name for alias in node.names)
    return frozenset(names)


def _constructor_name(node: ast.AST) -> str | None:
    """Der Modellname eines Ausdrucks, der als Schreibziel taugt (`Foo(...)` oder `Foo`)."""
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _write_targets(tree: ast.AST) -> frozenset[str]:
    """Jeder Name, der in einem `add`/`add_all`-Aufruf als Ziel auftaucht."""
    targets: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.attr
            if isinstance(func, ast.Attribute)
            else func.id
            if isinstance(func, ast.Name)
            else None
        )
        if name not in {"add", "add_all"}:
            continue
        for argument in node.args:
            elements = (
                list(argument.elts) if isinstance(argument, (ast.List, ast.Tuple)) else [argument]
            )
            for element in elements:
                constructor = _constructor_name(element)
                if constructor is not None:
                    targets.add(constructor)
    return frozenset(targets)


def _called_names(tree: ast.AST) -> frozenset[str]:
    """Jeder aufgerufene Name - Attributform und blanke Form gleich behandelt."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            names.add(func.attr)
        elif isinstance(func, ast.Name):
            names.add(func.id)
    return frozenset(names)


def _stringified_foreign_exceptions(tree: ast.AST) -> list[str]:
    """`str(...)` auf eine gefangene Ausnahme, die NICHT die eigene `_ReviewAbort` ist.

    `str(abort)` ist der zugelassene Weg: `_ReviewAbort` traegt bereits einen Satz aus der
    geschlossenen Menge. `str(exc)` eines fremden Systems ist genau das, was S7 verbietet."""
    own: set[str] = set()
    foreign: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or node.name is None:
            continue
        type_name = _constructor_name(node.type) if node.type is not None else None
        (own if type_name == "_ReviewAbort" else foreign).add(node.name)

    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "str"):
            continue
        for argument in node.args:
            if isinstance(argument, ast.Name) and argument.id in foreign:
                found.append(f"str({argument.id})")
    return found


def _fail_asserts_the_closed_set(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != "_fail":
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Assert):
                continue
            test = inner.test
            if (
                isinstance(test, ast.Compare)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Name)
                and test.comparators[0].id == "ERROR_MESSAGES"
            ):
                return True
    return False


class TestTheJobWritesNothingElse:
    def test_the_allowlist_comes_from_the_module_import(self) -> None:
        """Die Allowlist ist der Schnitt aus Modellimport und den sechs Pruefmodellen - keine
        Zeichenkettenliste. Gegenprobe: sie ist nicht leer und enthaelt nur Pruefmodelle."""
        allowlist = _imported_model_names(_module_tree(JOB_MODULE)) & _review_model_names()

        assert allowlist
        assert allowlist <= _review_model_names()
        # Das Verdict-Modell fehlt zu Recht: der Job schreibt keine Urteile, die kommen aus der
        # Oberflaeche (Stufe 5).
        assert "ClassificationReviewVerdict" not in allowlist

    def test_every_write_target_is_a_review_model(self) -> None:
        tree = _module_tree(JOB_MODULE)
        allowlist = _imported_model_names(tree) & _review_model_names()
        targets = _write_targets(tree)

        assert targets, "kein einziges Schreibziel gefunden - der Waechter misst nichts"
        assert targets <= allowlist, sorted(targets - allowlist)

    def test_no_other_writing_form_is_used(self) -> None:
        """Kein `delete`, `update`, `insert`, `merge` und kein `text(<DML>)`: die Formen, mit
        denen ein Lauf an den Modellkonstruktoren vorbei schreiben koennte."""
        assert set(write_statements(_module_tree(JOB_MODULE))) <= ERLAUBTE_SCHREIBFORMEN

    def test_no_run_phase_or_selection_function_is_called(self) -> None:
        assert _called_names(_module_tree(JOB_MODULE)) & VERBOTENE_NAMEN == frozenset()

    def test_no_run_phase_or_selection_function_is_imported(self) -> None:
        assert _imported_names(_module_tree(JOB_MODULE)) & VERBOTENE_NAMEN == frozenset()

    def test_error_message_only_takes_the_closed_set(self) -> None:
        tree = _module_tree(JOB_MODULE)

        assert _fail_asserts_the_closed_set(tree)
        assert _stringified_foreign_exceptions(tree) == []
        # Und die Menge ist nicht leer - sonst waere jede Zusicherung oben trivial.
        assert ERROR_MESSAGES


class TestTheStructureGuardItself:
    """Rot-Nachweis: jede Zusage oben wird an einem VERSTOSSENDEN Schnipsel rot."""

    @pytest.mark.parametrize(
        ("snippet", "targets"),
        [
            ("session.add(Photo(id=1))", {"Photo"}),
            ("session.add_all([Photo(id=1), Foo(id=2)])", {"Photo", "Foo"}),
            ("await session.add(row)", {"row"}),
            ("model.insert(Photo)", set()),
        ],
    )
    def test_a_write_target_is_recognised(self, snippet: str, targets: set[str]) -> None:
        assert set(_write_targets(ast.parse(snippet))) == targets

    def test_a_foreign_model_fails_the_allowlist(self) -> None:
        """Genau der Fall, den der echte Lauf nicht zeigt: ein Schreibziel ausserhalb der sechs."""
        foreign = _write_targets(ast.parse("session.add(Photo(id=1))"))
        assert foreign & _review_model_names() == frozenset()

    @pytest.mark.parametrize(
        "snippet",
        [
            "await run_classification(session, 1)",
            "await worker._run_eye_phase(session, review)",
            "await store.upsert_assessment(session, row)",
            "ids = await select_remote_category_candidates(session, 1)",
        ],
    )
    def test_a_forbidden_call_is_recognised(self, snippet: str) -> None:
        assert _called_names(ast.parse(snippet)) & VERBOTENE_NAMEN

    def test_a_forbidden_import_is_recognised(self) -> None:
        tree = ast.parse("from photosort.worker import upsert_assessment")

        assert _imported_names(tree) & VERBOTENE_NAMEN == {"upsert_assessment"}

    def test_a_stringified_foreign_exception_is_recognised(self) -> None:
        snippet = """
try:
    await call()
except OSError as exc:
    raise RuntimeError(str(exc))
"""

        assert _stringified_foreign_exceptions(ast.parse(snippet)) == ["str(exc)"]

    def test_the_own_abort_may_be_stringified(self) -> None:
        snippet = """
try:
    await call()
except _ReviewAbort as abort:
    await _fail(session, review, str(abort))
"""

        assert _stringified_foreign_exceptions(ast.parse(snippet)) == []

    def test_a_foreign_writing_form_is_recognised(self) -> None:
        assert write_statements(ast.parse("await session.execute(text('DELETE FROM photos'))"))


# ---------------------------------------------------------------------------------------------
# Der Verhaltenswaechter
# ---------------------------------------------------------------------------------------------


async def _snapshot(session: AsyncSession) -> dict[str, list[tuple[Any, ...]]]:
    """Jede Zeile jeder geltenden Tabelle, in Primaerschluessel-Reihenfolge."""
    snapshot: dict[str, list[tuple[Any, ...]]] = {}
    for name in GELTENDE_TABELLEN:
        table = Base.metadata.tables[name]
        order = list(table.primary_key.columns) or list(table.columns)
        rows = (await session.execute(select(table).order_by(*order))).all()
        snapshot[name] = [tuple(row) for row in rows]
    return snapshot


def _differences(
    before: dict[str, list[tuple[Any, ...]]], after: dict[str, list[tuple[Any, ...]]]
) -> list[str]:
    return sorted(name for name in GELTENDE_TABELLEN if before[name] != after[name])


async def _project_with_two_photos(
    session: AsyncSession, name: str, cache_dir: Path
) -> tuple[Project, list[int]]:
    """Der Projektgraph (eine Zeile in jeder abhaengigen Tabelle) plus ein zweites, noch
    unbewertetes Foto - damit ein Prueflauf mindestens eine Abweichung findet und der
    Bestandsvergleich nicht an einer leeren Fallliste stillschweigend besteht."""
    graph = await build_project_graph(session, name)
    project = await session.get(Project, graph.project_id)
    assert project is not None
    # Der Graph legt selbst keine Bilddatei an - ohne die `display`-Variante ueberspringt die
    # Eye-Seite das Foto, und der Bestandsvergleich masse einen halben Lauf.
    variant = display_path(cache_dir, graph.photo_id, graph.photo_etag)
    variant.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 80), color=(70, 70, 70)).save(variant, format="JPEG")
    candidate = await _add_photo(session, project, cache_dir, "kandidat.jpg")
    return project, [graph.photo_id, candidate.id]


def _review_sides() -> list[dict[str, Any]]:
    # Eye gegen lokal: die eine Seite sieht `people`, die andere nur das lokale Modell - so
    # entsteht mindestens ein Motiv-Fall, und die Pruefung schreibt in ihre eigenen Tabellen.
    return [
        _side("a", ClassificationReviewSideKind.EYE, eye_mapping_version=MAPPING_VERSION),
        _side("b", ClassificationReviewSideKind.LOCAL),
    ]


async def test_a_review_leaves_every_valid_table_unchanged(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    project, photo_ids = await _project_with_two_photos(db_session, "Isolation", tmp_path)
    user = await get_or_create_user(db_session)
    review = await _make_review(db_session, project, user, _review_sides())
    eye = FakeEyeClient(
        payloads={
            photo_ids[0]: _payload(tags={"people": 0.9}),
            photo_ids[1]: _payload(tags={}),
        }
    )
    before = await _snapshot(db_session)

    await execute_classification_review(
        db_session,
        review,
        tmp_path,
        project=project,
        build_eye_client=lambda: eye,
        build_detector=lambda: None,
        build_animal_detector=lambda: None,
        build_classifier=lambda: None,
        build_aesthetics=lambda: None,
        build_landmarker=lambda: None,
    )

    after = await _snapshot(db_session)

    assert review.status == ScanStatus.SUCCESS
    assert review.phase is None
    # Der Lauf hat tatsaechlich etwas getan - sonst waere die Gleichheit unten leer.
    assert review.photos_processed == 2
    # Der Bestand ist gefuellt - eine Gleichheit zweier leerer Listen bewiese nichts.
    assert before["photos"] and before["photo_scores"]
    assert before["photo_eye_motif_strengths"] and before["photo_local_motif_snapshots"]
    assert _differences(before, after) == []
    assert eye.analyze_calls == 2


async def test_the_snapshot_comparison_goes_red_on_a_changed_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Rot-Nachweis des Verhaltenswaechters: eine einzige geaenderte Zeile faellt auf. Ohne ihn
    bestuende `_differences(...) == []` auch bei einem Vergleich, der gar nichts vergleicht."""
    await _project_with_two_photos(db_session, "Rotnachweis", tmp_path)
    before = await _snapshot(db_session)

    score = (await db_session.execute(select(PhotoScore))).scalars().first()
    assert score is not None
    score.sharpness = 0.0
    await db_session.commit()

    after = await _snapshot(db_session)
    assert _differences(before, after) == ["photo_scores"]


async def test_a_review_changes_neither_the_estimate_nor_the_candidate_set(
    db_session: AsyncSession, authenticated_api_client: httpx.AsyncClient, tmp_path: Path
) -> None:
    """Edge Case 1, zweiter Teil: `GET /projects/{id}`, `GET .../classify/estimate` und die
    Kandidatenmenge sind danach dieselben. `estimated_cost_usd` aus der Schaetzung ist genau der
    Betrag, den der Ausloeser an den Enqueuer gibt (api/projects.py::trigger_classify)."""
    project, _photo_ids = await _project_with_two_photos(db_session, "Schaetzung", tmp_path)
    project_id = project.id
    user = await get_or_create_user(db_session)
    review = await _make_review(db_session, project, user, _review_sides())

    project_before = (await authenticated_api_client.get(f"/projects/{project_id}")).json()
    estimate_before = (
        await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
    ).json()
    candidates_before = {
        photo.id for photo in await select_remote_category_candidates(db_session, project_id)
    }

    await execute_classification_review(
        db_session,
        review,
        tmp_path,
        project=project,
        build_eye_client=lambda: FakeEyeClient(),
        build_detector=lambda: None,
        build_animal_detector=lambda: None,
        build_classifier=lambda: None,
        build_aesthetics=lambda: None,
        build_landmarker=lambda: None,
    )

    assert review.status == ScanStatus.SUCCESS
    project_after = (await authenticated_api_client.get(f"/projects/{project_id}")).json()
    estimate_after = (
        await authenticated_api_client.get(f"/projects/{project_id}/classify/estimate")
    ).json()
    candidates_after = {
        photo.id for photo in await select_remote_category_candidates(db_session, project_id)
    }

    assert project_after == project_before
    assert estimate_after == estimate_before
    assert candidates_after == candidates_before
    assert candidates_after  # sonst verglichen sich zwei leere Mengen


async def test_a_normal_run_after_a_review_behaves_like_one_without_a_review(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """Gegentest ueber zwei gleiche Projekte: nur eines bekommt eine Pruefung. Danach muessen
    Kostenschaetzung und Kandidatenmenge beider Projekte gleich sein - die Pruefung darf den
    naechsten normalen Lauf nicht veraendern."""
    with_review, ids_a = await _project_with_two_photos(db_session, "MitPruefung", tmp_path)
    without_review, _ids_b = await _project_with_two_photos(db_session, "OhnePruefung", tmp_path)
    # Die IDs VOR dem Lauf festhalten: der abschliessende Commit laesst die Objekte ablaufen,
    # und ein Attributzugriff danach laedt synchron nach (MissingGreenlet).
    with_review_id = with_review.id
    without_review_id = without_review.id
    user = await get_or_create_user(db_session)
    review = await _make_review(db_session, with_review, user, _review_sides())

    await execute_classification_review(
        db_session,
        review,
        tmp_path,
        project=with_review,
        build_eye_client=lambda: FakeEyeClient(
            payloads={
                ids_a[0]: _payload(tags={"people": 0.9}),
                ids_a[1]: _payload(tags={}),
            }
        ),
        build_detector=lambda: None,
        build_animal_detector=lambda: None,
        build_classifier=lambda: None,
        build_aesthetics=lambda: None,
        build_landmarker=lambda: None,
    )

    with_review = await db_session.get(Project, with_review_id)
    without_review = await db_session.get(Project, without_review_id)
    assert with_review is not None and without_review is not None
    estimate_a = (
        await _build_classification_estimate(db_session, with_review, mode="cloud")
    ).model_dump()
    estimate_b = (
        await _build_classification_estimate(db_session, without_review, mode="cloud")
    ).model_dump()
    candidates_a = {
        photo.relative_path
        for photo in await select_remote_category_candidates(db_session, with_review.id)
    }
    candidates_b = {
        photo.relative_path
        for photo in await select_remote_category_candidates(db_session, without_review.id)
    }

    assert review.status == ScanStatus.SUCCESS
    assert review.phase is None
    assert estimate_a == estimate_b
    assert candidates_a == candidates_b
    assert candidates_a == {"kandidat.jpg"}
