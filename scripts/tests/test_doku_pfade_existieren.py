"""Kein Pfadverweis in lebender Doku zeigt auf eine nicht mehr existierende Datei (Spec 0647, AK8).

Die Aufteilung der beiden grossen Backend-Module in Pakete hat rund 130 Verweise in lebenden
Dokumenten und Code-Doku-Bloecken entwurzelt. Ein Verweis auf eine geloeschte Datei faellt bei keiner
anderen Pruefung auf: kein Import, kein Typfehler, kein Verhaltenstest liest Doku.

**Geprueft wird der Pfad, nicht der blosse Name.** Ein Token mit `/` ist ein Pfad; er muss aufloesbar
sein - direkt unter einer Quellwurzel oder ueber eine Verzeichniskette, die es im Repo gibt. So wird
`api/ratings.py` gegen `backend/src/photosort/api/` aufgeloest, waehrend `src/utils/utils.py` als
Verweis auf ein fremdes Repository ungeprueft bleibt: kein Verzeichnis dieses Repos endet auf
`src/utils`. Ein nackter Dateiname ist kein Pfad und bleibt ungeprueft.

**Zwei Namen sind dagegen auch nackt verboten** - sie sind durch diese Story zu Paketen geworden.

Gelesen werden nur lebende Stellen: `docs/architecture.md`, `specs/architecture/*.md`, Docstrings und
Kommentare unter `backend/src`, Docstrings unter `backend/tests`. Abgeschlossene Feature-Specs,
Entscheidungen und das Aenderungsprotokoll sind Historie und werden nicht gelesen.

**`_VORBESTEHEND` ist der gemessene Altbestand vom Stand vor dieser Story**, nicht eine Freigabe fuer
neue Verweise: Die Gleichheit unten ist in beide Richtungen geprueft, ein neuer toter Verweis macht
den Test rot und ein reparierter Altverweis zwingt zur Zeile. Alle acht Eintraege benennen eine
Entfernung, die aelter ist als diese Spec; keiner davon liegt unter `worker/` oder `api/photos/`.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

from conftest import REPO_WURZEL

_SRC = REPO_WURZEL / "backend" / "src"
_TESTS = REPO_WURZEL / "backend" / "tests"

# Die Quellwurzeln, gegen die ein Pfad-Token aufgeloest wird.
_WURZELN = (
    REPO_WURZEL,
    _SRC / "photosort",
    _SRC / "photosort" / "api",
    _TESTS,
    REPO_WURZEL / "scripts",
    REPO_WURZEL / "frontend" / "src",
)

# Diese Datei muss ihre eigenen Suchbegriffe nennen duerfen.
_SELBST = Path(__file__).resolve()

_PFAD = re.compile(r"(?<![\w/.\-])((?:[\w.\-]+/)+[\w.\-]+\.py)(?:::([A-Za-z_]\w*))?")
_VERBOTEN = ("worker.py", "api/photos.py")
_AUSGESCHLOSSEN = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "artifacts"}

_VORBESTEHEND = frozenset(
    {
        "api/categories.py",
        "api/classification_reviews.py::set_verdict",
        "api/duplicate_decisions.py::_has_open_suggestion",
        "api/ratings.py::_drop_when_empty",
        "api/ratings.py::_write_own_rating",
        "backend/src/photosort/category_diff.py",
        "scripts/gh-board.py",
        "scripts/tests/test_gh_board.py",
    }
)


def _verzeichnisse() -> list[Path]:
    return [
        pfad
        for pfad in REPO_WURZEL.rglob("*")
        if pfad.is_dir() and not (_AUSGESCHLOSSEN & set(pfad.relative_to(REPO_WURZEL).parts))
    ]


def _docstrings(quelle: str) -> list[str]:
    return [
        ast.get_docstring(knoten, clean=False) or ""
        for knoten in ast.walk(ast.parse(quelle))
        if isinstance(knoten, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _kommentare(quelle: str) -> list[str]:
    return [
        token.string
        for token in tokenize.generate_tokens(io.StringIO(quelle).readline)
        if token.type == tokenize.COMMENT
    ]


def _doku_texte() -> list[tuple[str, str]]:
    """Dokumente und Code-Doku-Stellen: (Ort, Text)."""
    stellen = [
        (str(pfad.relative_to(REPO_WURZEL)), pfad.read_text(encoding="utf-8"))
        for pfad in [
            REPO_WURZEL / "docs" / "architecture.md",
            *sorted((REPO_WURZEL / "specs" / "architecture").glob("*.md")),
        ]
    ]

    for pfad in sorted(_SRC.rglob("*.py")):
        if pfad.resolve() != _SELBST:
            quelle = pfad.read_text(encoding="utf-8")
            doku = _docstrings(quelle) + _kommentare(quelle)
            stellen.append((str(pfad.relative_to(REPO_WURZEL)), "\n".join(doku)))

    for pfad in sorted(_TESTS.rglob("*.py")):
        if pfad.resolve() != _SELBST:
            doku = _docstrings(pfad.read_text(encoding="utf-8"))
            stellen.append((str(pfad.relative_to(REPO_WURZEL)), "\n".join(doku)))

    return stellen


def _pfad_tokens(text: str) -> list[tuple[str, str | None]]:
    """Pfad-Token mit optionalem `::name`. Ein Glied vor dem letzten darf nicht selbst auf `.py`
    enden: `a.py/b.py` ist eine Aufzaehlung, kein Pfad."""
    return [
        (pfad, name)
        for pfad, name in _PFAD.findall(text)
        if not any(glied.endswith(".py") for glied in pfad.split("/")[:-1])
    ]


def _aufloesen(token: str, verzeichnisse: list[Path]) -> list[Path]:
    """Die Dateien, auf die ein Pfad-Token zeigen kann: direkt unter einer Wurzel oder ueber eine
    Verzeichniskette dieses Repos."""
    eltern, name = token.rsplit("/", 1)
    treffer = [wurzel / token for wurzel in _WURZELN if (wurzel / token).is_file()]
    treffer += [
        verzeichnis / name
        for verzeichnis in verzeichnisse
        if verzeichnis.as_posix().endswith(f"/{eltern}") and (verzeichnis / name).is_file()
    ]
    return sorted(set(treffer))


def _kennt_den_namen(datei: Path, name: str) -> bool:
    for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if knoten.name == name:
                return True
        elif isinstance(knoten, ast.Assign):
            if any(isinstance(ziel, ast.Name) and ziel.id == name for ziel in knoten.targets):
                return True
        elif isinstance(knoten, ast.AnnAssign):
            if isinstance(knoten.target, ast.Name) and knoten.target.id == name:
                return True
    return False


def _tote_verweise() -> dict[str, list[str]]:
    verzeichnisse = _verzeichnisse()
    tot: dict[str, list[str]] = {}
    for ort, text in _doku_texte():
        for pfad, name in _pfad_tokens(text):
            dateien = _aufloesen(pfad, verzeichnisse)
            token = f"{pfad}::{name}" if name else pfad
            if not dateien or (
                name and not any(_kennt_den_namen(datei, name) for datei in dateien)
            ):
                tot.setdefault(token, []).append(ort)
    return {token: sorted(set(orte)) for token, orte in tot.items()}


def test_no_living_document_names_a_vanished_source_file() -> None:
    """Jedes Pfad-Token in lebender Doku zeigt auf eine existierende Datei, und ein `::name`
    existiert dort als Top-Level-Definition."""
    assert set(_tote_verweise()) == set(_VORBESTEHEND)


def test_the_two_split_modules_are_named_nowhere() -> None:
    """Die beiden frueheren Einzeldateien existieren nicht mehr; eine Nennung ohne Pfad ist genauso
    ein Verweis ins Leere wie eine mit."""
    treffer = {
        ort: sorted({begriff for begriff in _VERBOTEN if begriff in text})
        for ort, text in _doku_texte()
    }

    assert {ort: begriffe for ort, begriffe in treffer.items() if begriffe} == {}
