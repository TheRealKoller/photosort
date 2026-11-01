"""Haelt die Form des backend-Jobs in `.github/workflows/ci.yml` fest (Spec 0603, ADR 0137).

Die Beschleunigung selbst ist eine Messung aus dem Actions-Protokoll, kein automatisiertes
Gate. Dieser Test traegt stattdessen den TDD-Zwang: Er liest den echten Dateizustand von
`ci.yml` und `backend/pyproject.toml` und schlaegt laut fehl, sobald die tragenden Formen
driftend — der Testschritt ohne `-n auto` oder mit aufgeweichtem Coverage-Gate, der
`pytest-xdist`-dev-Eintrag, der `uv`-Cache-Schritt, die Job-Schluesselmenge oder die
Pruefschrittfolge. Es wird kein Test entfernt oder geaendert.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

CI_PFAD = ".github/workflows/ci.yml"
PYPROJECT_PFAD = "backend/pyproject.toml"

# (i) Der Testschritt: parallelisiert, Coverage-Gate unveraendert, Name unveraendert.
TEST_SCHRITT_NAME = "Test (pytest, coverage gate 80%)"
EXPECTED_TEST_RUN = "pytest -n auto --cov=photosort --cov-report=term-missing --cov-fail-under=80"

# (ii) Die dev-Dependency, die die Parallelisierung traegt.
PYTEST_XDIST_EINTRAG = '"pytest-xdist>=3.6"'

# (iii) Der zweite Cache-Schritt: uv-Wheel-Cache, direkt vor `Install dependencies`.
UV_CACHE_PFAD = "~/.cache/uv"
UV_CACHE_KEY = "uv-cache-${{ hashFiles('backend/pyproject.toml') }}"

# Der vollstaendige uv-Cache-Schritt, wie er in ci.yml steht (Einrueckung gehoert zur Form).
_UV_CACHE_SCHRITT = (
    "      - uses: actions/cache@v4\n"
    "        with:\n"
    f"          path: {UV_CACHE_PFAD}\n"
    f"          key: {UV_CACHE_KEY}\n"
)
# Direkt vor `Install dependencies` heisst: die key:-Zeile endet, die naechste Zeile ist der
# Install-Schritt. Eine Blankzeile oder ein anderer Schritt dazwischen waere eine Verschiebung.
UV_CACHE_VOR_INSTALL = _UV_CACHE_SCHRITT + "      - name: Install dependencies"

# (iv) Die Job-Schluesselmenge von ci.yml — exakt, nicht "mindestens".
JOB_SCHLUESSEL = ("backend", "frontend", "demo-scripts", "docker-compose-check", "e2e")

# (v) Die Pruefschritte des backend-Jobs in fester Reihenfolge, (Name, run). Die Spec zaehlt
# sie in den Akzeptanzkriterien als (Formatierung, Lint, Typpruefung, Tests) — vier Schritte;
# das Coverage-Gate ist Teil des Testschritts, kein eigener.
PRUEFSCHRITTE = (
    ("Formatierung pruefen (ruff format)", "ruff format --check --output-format=github ."),
    ("Lint (ruff)", "ruff check ."),
    ("Type check (mypy)", "mypy src"),
    ("Test (pytest, coverage gate 80%)", EXPECTED_TEST_RUN),
)

# --- Duenne Leser --------------------------------------------------------------------------


def dateitext(pfad: str, wurzel: Path = REPO_WURZEL) -> str:
    """Duenner Leser; eine fehlende Datei scheitert laut (FileNotFoundError)."""
    return (wurzel / pfad).read_text(encoding="utf-8")


def ci_text(wurzel: Path = REPO_WURZEL) -> str:
    return dateitext(CI_PFAD, wurzel)


def pyproject_text(wurzel: Path = REPO_WURZEL) -> str:
    return dateitext(PYPROJECT_PFAD, wurzel)


# --- Reine Funktionen -----------------------------------------------------------------------

# Ein Job-Schluessel ist ein 2-Space-eingerueckter Schluessel mit leerem Wert (Mapping). Die
# Job-Eigenschaften (`runs-on`, `defaults`, `steps`) stehen 4-Space-eingerueckt und fallen damit
# nicht unter dieses Muster; `push:`/`pull_request:` unter `on:` liegen vor dem `jobs:`-Abschnitt
# und werden durch die Abschnittsgrenze ausgeschlossen.
_TOP_KEY = re.compile(r"^  (?P<key>[a-z][a-z0-9-]*):$", re.MULTILINE)
_JOBS_KOPF = re.compile(r"^jobs:[ \t]*$", re.MULTILINE)


def job_schluessel(text: str) -> tuple[str, ...]:
    """Die Job-Schluessel unter `jobs:`, in Dateireihenfolge; laut, wenn `jobs:` fehlt."""
    m = _JOBS_KOPF.search(text)
    if m is None:
        raise ValueError("jobs:-Abschnitt nicht gefunden")
    return tuple(mm.group("key") for mm in _TOP_KEY.finditer(text[m.end() :]))


def backend_job(text: str) -> str:
    """Der Text des backend-Jobs, ab der Zeile nach `  backend:` bis zum naechsten Job-Schluessel."""
    m = re.search(r"^  backend:\n", text, re.MULTILINE)
    if m is None:
        raise ValueError("backend-Job nicht gefunden")
    rest = text[m.end() :]
    naechster = _TOP_KEY.search(rest)
    return rest[: naechster.start()] if naechster else rest


_SCHRITT = re.compile(r"^      - ", re.MULTILINE)


def schritte(job: str) -> list[str]:
    """Die Schrittbloecke des Jobs (je ab `      - `); laut, wenn keine Schritte."""
    bloecke = _SCHRITT.split(job)[1:]
    if not bloecke:
        raise ValueError("Job ohne Schritte")
    return bloecke


_NAME = re.compile(r"^\s*name:\s*([^\n]+?)\s*$", re.MULTILINE)
_RUN = re.compile(r"^\s*run:\s*([^\n]+?)\s*$", re.MULTILINE)
_USES = re.compile(r"^\s*uses:\s*(\S+)\s*$", re.MULTILINE)


def schritt_name(block: str) -> str | None:
    m = _NAME.search(block)
    return m.group(1) if m else None


def schritt_run(block: str) -> str | None:
    m = _RUN.search(block)
    return m.group(1) if m else None


def schritt_uses(block: str) -> str | None:
    m = _USES.search(block)
    return m.group(1) if m else None


def pytest_run(job: str) -> str:
    """Die run:-Zeile des Testschritts; laut, wenn der Schritt oder sein run: fehlt."""
    for block in schritte(job):
        if schritt_name(block) == TEST_SCHRITT_NAME:
            run = schritt_run(block)
            if run is None:
                raise ValueError("Test-Schritt ohne run:")
            return run
    raise ValueError(f"Schritt {TEST_SCHRITT_NAME!r} nicht gefunden")


def cache_bloecke(job: str) -> list[str]:
    """Die Bloecke aller actions/cache@v4-Schritte, in Dateireihenfolge."""
    return [block for block in schritte(job) if schritt_uses(block) == "actions/cache@v4"]


def pruefschritte(job: str) -> list[tuple[str, str]]:
    """(Name, run) der Pruefschritte in Dateireihenfolge; laut, wenn einer fehlt."""
    erwartete_namen = {name for name, _ in PRUEFSCHRITTE}
    paare = [(name, run) for name, run in benannte_schritte(job) if name in erwartete_namen]
    fehlend = erwartete_namen - {name for name, _ in paare}
    if fehlend:
        raise ValueError("fehlende Pruefschritte: " + ", ".join(sorted(fehlend)))
    return paare


def benannte_schritte(job: str) -> list[tuple[str, str]]:
    """(name, run)-Paare aller Schritte mit einem name:, in Dateireihenfolge."""
    paare = []
    for block in schritte(job):
        name = schritt_name(block)
        if name is not None:
            paare.append((name, schritt_run(block) or ""))
    return paare


def dev_block(text: str) -> str:
    """Der Inhalt der dev-Liste unter [project.optional-dependencies]; laut, wenn sie fehlt."""
    m = re.search(
        r"\[project\.optional-dependencies\][ \t]*\ndev[ \t]*=[ \t]*\[(.*?)\]",
        text,
        re.DOTALL,
    )
    if m is None:
        raise ValueError("dev-Extra nicht gefunden")
    return m.group(1)


def _job(*schritte: tuple[str, str]) -> str:
    """Baut einen Job-Rumpf aus (name, run)-Paaren fuer die Gegenproben."""
    return "".join(f"      - name: {name}\n        run: {run}\n" for name, run in schritte)


# --- (i) Testschritt ------------------------------------------------------------------------


def test_der_testschritt_parallelisiert_mit_unveraendertem_coverage_gate() -> None:
    run = pytest_run(backend_job(ci_text()))
    assert run == EXPECTED_TEST_RUN, (
        f"Testschritt traegt {run!r}, erwartet {EXPECTED_TEST_RUN!r} "
        f"(`-n auto` plus unveraendertes `--cov=photosort --cov-report=term-missing "
        f"--cov-fail-under=80`)."
    )


# --- (ii) dev-Dependency --------------------------------------------------------------------


def test_pytest_xdist_steht_im_dev_extra() -> None:
    block = dev_block(pyproject_text())
    assert PYTEST_XDIST_EINTRAG in block, (
        f"{PYTEST_XDIST_EINTRAG} fehlt unter [project.optional-dependencies] dev."
    )


# --- (iii) uv-Cache-Schritt -----------------------------------------------------------------


def test_der_uv_cache_steht_mit_richtigem_pfad_und_schluessel_direkt_vor_install_dependencies() -> (
    None
):
    job = backend_job(ci_text())
    assert UV_CACHE_VOR_INSTALL in job, (
        "Der uv-Cache-Schritt fehlt, traegt einen falschen Pfad/Schluessel oder steht nicht "
        "direkt vor 'Install dependencies'."
    )
    assert len(cache_bloecke(job)) >= 2, (
        "Es fehlt ein actions/cache@v4-Schritt: der Modell-Asset-Cache und der uv-Cache "
        "muessen beide vorhanden sein."
    )


# --- (iv) Job-Schluesselmenge --------------------------------------------------------------


def test_die_job_schluesselmenge_ist_exakt() -> None:
    assert job_schluessel(ci_text()) == JOB_SCHLUESSEL, (
        f"Job-Schluessel weichen ab: {job_schluessel(ci_text())!r}, erwartet {JOB_SCHLUESSEL!r}."
    )


# --- (v) Pruefschrittfolge ------------------------------------------------------------------


def test_alle_pruefschritte_sind_vorhanden_und_ungekuerzt() -> None:
    folge = pruefschritte(backend_job(ci_text()))
    assert folge == list(PRUEFSCHRITTE), (
        f"Pruefschritte weichen ab: {folge!r}, erwartet {list(PRUEFSCHRITTE)!r}."
    )


# --- Gegenproben je Regel -------------------------------------------------------------------


def test_die_erwartete_testschrittform_gilt_nicht_als_verstoss() -> None:
    job = f"      - name: {TEST_SCHRITT_NAME}\n        run: {EXPECTED_TEST_RUN}\n"
    assert pytest_run(job) == EXPECTED_TEST_RUN


@pytest.mark.parametrize(
    ("bezeichnung", "run"),
    [
        ("ohne -n auto", "pytest --cov=photosort --cov-report=term-missing --cov-fail-under=80"),
        (
            "aufgeweichtes Gate",
            "pytest -n auto --cov=photosort --cov-report=term-missing --cov-fail-under=70",
        ),
        ("ohne --cov", "pytest -n auto --cov-report=term-missing --cov-fail-under=80"),
    ],
)
def test_jede_abweichung_der_testschrittform_wird_erkannt(bezeichnung: str, run: str) -> None:
    job = f"      - name: {TEST_SCHRITT_NAME}\n        run: {run}\n"
    assert pytest_run(job) != EXPECTED_TEST_RUN, bezeichnung


def test_ein_umbenannter_testschritt_wird_erkannt() -> None:
    job = f"      - name: Test (pytest)\n        run: {EXPECTED_TEST_RUN}\n"
    with pytest.raises(ValueError, match=r"nicht gefunden"):
        pytest_run(job)


def test_ein_fehlender_testschritt_scheitert_laut() -> None:
    with pytest.raises(ValueError, match=r"nicht gefunden"):
        pytest_run("      - name: Lint (ruff)\n        run: ruff check .\n")


@pytest.mark.parametrize(
    "dev_inhalt",
    [
        '    "pytest>=8.3",\n    "pytest-cov>=6.0",\n',
        '    "pytest-xdist>=3.5",\n',
    ],
)
def test_ein_dev_extra_ohne_den_eintrag_wird_erkannt(dev_inhalt: str) -> None:
    assert PYTEST_XDIST_EINTRAG not in dev_inhalt


def test_ein_dev_extra_mit_dem_eintrag_ist_kein_befund() -> None:
    assert PYTEST_XDIST_EINTRAG in '    "pytest-xdist>=3.6",\n'


@pytest.mark.parametrize(
    ("bezeichnung", "schritt"),
    [
        ("falscher Pfad", "          path: ~/.cache/pip\n"),
        ("falscher Schluessel", "          key: uv-cache-${{ hashFiles('backend/uv.lock') }}\n"),
    ],
)
def test_ein_mutierter_uv_cache_schritt_wird_erkannt(bezeichnung: str, schritt: str) -> None:
    mutiert = (
        "      - uses: actions/cache@v4\n"
        "        with:\n" + schritt + "      - name: Install dependencies\n"
    )
    assert UV_CACHE_VOR_INSTALL not in mutiert, bezeichnung


def test_ein_uv_cache_der_nicht_direkt_vor_install_dependencies_steht_wird_erkannt() -> None:
    mutiert = _UV_CACHE_SCHRITT + "      - name: Install uv\n      - name: Install dependencies\n"
    assert UV_CACHE_VOR_INSTALL not in mutiert


def test_eine_zusaetzliche_job_schluesselmenge_wird_erkannt() -> None:
    text = "jobs:\n  backend:\n  frontend:\n  demo-scripts:\n  docker-compose-check:\n  e2e:\n  extra:\n"
    assert job_schluessel(text) != JOB_SCHLUESSEL


def test_eine_verkuerzte_job_schluesselmenge_wird_erkannt() -> None:
    text = "jobs:\n  backend:\n  frontend:\n  demo-scripts:\n  docker-compose-check:\n"
    assert job_schluessel(text) != JOB_SCHLUESSEL


def test_eine_entfernte_pruefschrittfolge_scheitert_laut() -> None:
    job = _job(
        ("Lint (ruff)", "ruff check ."),
        ("Type check (mypy)", "mypy src"),
        (TEST_SCHRITT_NAME, EXPECTED_TEST_RUN),
    )
    with pytest.raises(ValueError, match=r"fehlende Pruefschritte"):
        pruefschritte(job)


def test_ein_abgeschwaechter_pruefschritt_wird_erkannt() -> None:
    job = _job(
        ("Formatierung pruefen (ruff format)", "ruff format --check --output-format=github ."),
        ("Lint (ruff)", "ruff check ."),
        ("Type check (mypy)", "mypy src"),
        (TEST_SCHRITT_NAME, EXPECTED_TEST_RUN),
    )
    assert pruefschritte(job) == list(PRUEFSCHRITTE)

    abgeschwaecht = _job(
        ("Formatierung pruefen (ruff format)", "ruff format --check --output-format=github ."),
        ("Lint (ruff)", "ruff check ."),
        ("Type check (mypy)", "mypy src"),
        (
            TEST_SCHRITT_NAME,
            "pytest -n auto --cov=photosort --cov-report=term-missing --cov-fail-under=70",
        ),
    )
    assert pruefschritte(abgeschwaecht) != list(PRUEFSCHRITTE)


# --- Selbstschutz ---------------------------------------------------------------------------


def test_eine_fehlende_datei_scheitert_laut(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ci_text(tmp_path)


def test_ein_fehlender_jobs_abschnitt_scheitert_laut() -> None:
    with pytest.raises(ValueError, match=r"jobs:"):
        job_schluessel("name: ci\non: push\n")


def test_ein_fehlender_backend_job_scheitert_laut() -> None:
    with pytest.raises(ValueError, match=r"backend"):
        backend_job("jobs:\n  frontend:\n")
