"""Der eine Lesepunkt der zaehlenden Albumstufe (Spec 0621, ADR 0144).

Jede Lage mit zwei Quellen ist so gebaut, dass sie unterscheiden KANN: Cloud- und Eye-Stufe eines
Fotos liegen auseinander und ordnen die beiden Fotos umgekehrt. Bei gleichen Stufen bestuende
"zaehlt nur die Quelle" auch gegen einen Rueckfall oder gegen "liest immer Cloud".
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession

from photosort.album_stage import load_album_levels
from photosort.models import (
    CategoryMethod,
    Photo,
    PhotoAlbumSuitability,
    PhotoEyeResult,
    Project,
)
from tests.import_closure import SRC_DIR, imported_root_packages, module_file

_NOW = datetime(2026, 11, 8, tzinfo=UTC)


@contextmanager
def _recorded_select_statements() -> Iterator[list[str]]:
    """Die TATSAECHLICH abgesetzten SELECTs (Muster aus test_api_photos.py)."""
    statements: list[str] = []

    def _listener(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(Engine, "before_cursor_execute", _listener)
    try:
        yield statements
    finally:
        event.remove(Engine, "before_cursor_execute", _listener)


async def _photo(session: AsyncSession, project: Project, path: str) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path=path,
        etag=f"etag-{path}",
        content_length=100,
        taken_at=_NOW,
        taken_at_original=_NOW,
        last_modified=_NOW,
    )
    session.add(photo)
    await session.flush()
    return photo


def _cloud(photo: Photo, level: int) -> PhotoAlbumSuitability:
    return PhotoAlbumSuitability(
        photo_id=photo.id, level=level, reason="Modelltext", provider="anthropic", computed_at=_NOW
    )


def _eye(photo: Photo, level: int) -> PhotoEyeResult:
    return PhotoEyeResult(
        photo_id=photo.id,
        excluded_document=False,
        album_level=level,
        model_revision="rev",
        mapping_version="v2",
        computed_at=_NOW,
    )


async def _two_source_lay(session: AsyncSession) -> dict[str, int]:
    """`both_a`/`both_b` tragen beide Stufen, umgekehrt geordnet; `cloud_only`/`eye_only` je nur
    eine."""
    project = Project(name="Zwei Quellen", opencloud_drive_id="d", opencloud_path="/p")
    session.add(project)
    await session.flush()
    both_a = await _photo(session, project, "a.jpg")
    both_b = await _photo(session, project, "b.jpg")
    cloud_only = await _photo(session, project, "c.jpg")
    eye_only = await _photo(session, project, "e.jpg")
    session.add_all(
        [
            _cloud(both_a, 5),
            _eye(both_a, 1),
            _cloud(both_b, 1),
            _eye(both_b, 5),
            _cloud(cloud_only, 4),
            _eye(eye_only, 2),
        ]
    )
    await session.commit()
    return {
        "both_a": both_a.id,
        "both_b": both_b.id,
        "cloud_only": cloud_only.id,
        "eye": eye_only.id,
    }


async def test_cloud_counts_only_the_cloud_level(db_session: AsyncSession) -> None:
    ids = await _two_source_lay(db_session)

    levels = await load_album_levels(db_session, CategoryMethod.CLOUD, ids.values())

    assert levels == {ids["both_a"]: 5, ids["both_b"]: 1, ids["cloud_only"]: 4}


async def test_eye_counts_only_the_eye_level(db_session: AsyncSession) -> None:
    ids = await _two_source_lay(db_session)

    levels = await load_album_levels(db_session, CategoryMethod.EYE, ids.values())

    assert levels == {ids["both_a"]: 1, ids["both_b"]: 5, ids["eye"]: 2}


async def test_the_lay_can_tell_the_sources_apart(db_session: AsyncSession) -> None:
    """Vorbedingung der Leitregel: beide Quellen ordnen dieselben zwei Fotos umgekehrt."""
    ids = await _two_source_lay(db_session)
    pair = (ids["both_a"], ids["both_b"])

    cloud = await load_album_levels(db_session, CategoryMethod.CLOUD, pair)
    eye = await load_album_levels(db_session, CategoryMethod.EYE, pair)

    assert (cloud[pair[0]] > cloud[pair[1]]) and (eye[pair[0]] < eye[pair[1]])


async def test_only_the_requested_ids_are_read(db_session: AsyncSession) -> None:
    ids = await _two_source_lay(db_session)

    assert await load_album_levels(db_session, CategoryMethod.CLOUD, [ids["both_a"]]) == {
        ids["both_a"]: 5
    }
    assert await load_album_levels(db_session, CategoryMethod.EYE, [ids["both_b"]]) == {
        ids["both_b"]: 5
    }


@pytest.mark.parametrize("source", list(CategoryMethod))
async def test_an_empty_input_issues_no_query(
    db_session: AsyncSession, source: CategoryMethod
) -> None:
    await _two_source_lay(db_session)

    with _recorded_select_statements() as statements:
        levels = await load_album_levels(db_session, source, [])

    assert levels == {}
    assert statements == []


@pytest.mark.parametrize("source", list(CategoryMethod))
async def test_a_non_empty_input_is_measured_by_the_recorder(
    db_session: AsyncSession, source: CategoryMethod
) -> None:
    """Gegenprobe zum Leerfall: der Rekorder sieht die Abfrage, sobald es eine gibt."""
    ids = await _two_source_lay(db_session)

    with _recorded_select_statements() as statements:
        await load_album_levels(db_session, source, [ids["both_a"]])

    assert len(statements) == 1


def _own_imports(module: str) -> set[str]:
    """Die `photosort.*`-Module, die EIN Modul selbst importiert (ohne Huelle): `models` zieht
    ueber Konstanten bereits `cloud_vision` mit, ohne einen Client zu bauen - der Abschluss waere
    dafuer die falsche Frage."""
    path = module_file(module)
    assert path is not None
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return names


class TestTheModuleStaysADatabaseReadPath:
    """Security S1/S5: das Modul importiert keinen Netzwerk-, Vision- oder Eye-Client."""

    _FORBIDDEN_OWN_MODULES = frozenset(
        {
            "photosort.eye_client",
            "photosort.cloud_vision",
            "photosort.landmark",
            "photosort.worker",
            "photosort.remote_classification",
        }
    )

    def test_no_client_module_is_imported(self) -> None:
        assert not (_own_imports("photosort.album_stage") & self._FORBIDDEN_OWN_MODULES)

    def test_no_network_package_is_imported(self) -> None:
        assert not (
            imported_root_packages("photosort.album_stage")
            & {"httpx", "requests", "anthropic", "mistralai", "socket", "urllib"}
        )

    def test_the_walker_sees_the_models_import(self) -> None:
        # Gegenprobe: ohne sie bestuenden beide Zusagen auch bei einem Walker, der nichts findet.
        assert "photosort.models" in _own_imports("photosort.album_stage")
        assert "photosort.eye_client" in _own_imports("photosort.worker")
        assert "sqlalchemy" in imported_root_packages("photosort.album_stage")


# --- Strukturwaechter: wo die Stufenspalten gelesen werden ----------------------------------

# (Datei relativ zu `src/photosort`, umschliessende Funktion). Jede weitere Lesestelle ist eine
# zweite Quelle der zaehlenden Stufe und wuerde beim Verfahrenswechsel still die falsche Tabelle
# lesen. `demo_state._seed_feedback_events` baut die Demo-Feedbackereignisse und bleibt laut
# Spec 0621 unveraendert.
_ALLOWED_LEVEL_READERS = frozenset(
    {
        ("album_stage.py", "load_album_levels"),
        ("demo_state.py", "_seed_feedback_events"),
    }
)
_LEVEL_COLUMNS = frozenset({("PhotoAlbumSuitability", "level"), ("PhotoEyeResult", "album_level")})


def _level_reads(tree: ast.AST) -> set[str]:
    """Die umschliessenden Funktionen jeder Klassenattribut-Lesestelle einer Stufenspalte
    (`PhotoAlbumSuitability.level`, `PhotoEyeResult.album_level`); `<module>` ausserhalb jeder
    Funktion."""
    found: set[str] = set()

    def visit(node: ast.AST, scope: str) -> None:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            scope = node.name
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and (node.value.id, node.attr) in _LEVEL_COLUMNS
        ):
            found.add(scope)
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree, "<module>")
    return found


def _all_level_readers() -> set[tuple[str, str]]:
    package = SRC_DIR / "photosort"
    return {
        (path.relative_to(package).as_posix(), scope)
        for path in sorted(package.rglob("*.py"))
        for scope in _level_reads(ast.parse(path.read_text(encoding="utf-8")))
    }


def test_the_level_columns_are_read_only_at_the_fixed_places() -> None:
    assert _all_level_readers() == _ALLOWED_LEVEL_READERS


def test_the_guard_recognises_a_level_read_inside_a_function() -> None:
    """Positiv-Gegenprobe: ein Waechter, der nichts erkennt, ist immer gruen."""
    snippet = (
        "async def sneaky(session):\n"
        "    return select(PhotoEyeResult.album_level)\n"
        "def other():\n"
        "    return PhotoAlbumSuitability.level\n"
        "def harmless(row):\n"
        "    return row.level, PhotoAlbumSuitability.reason\n"
    )

    assert _level_reads(ast.parse(snippet)) == {"sneaky", "other"}


def test_the_guard_scans_real_source_files() -> None:
    package = SRC_DIR / "photosort"
    assert (package / "album_stage.py").is_file()
    assert len(list(Path(package).rglob("*.py"))) > 10
