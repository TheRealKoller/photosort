from __future__ import annotations

import importlib.util
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS_DIR = Path(__file__).parent.parent
REPO_WURZEL = _SCRIPTS_DIR.parent

# Das Skript traegt bewusst einen Bindestrich im Dateinamen ("seed-opencloud-demo.py", siehe
# specs/features/0009-local-opencloud-demo-stack.md) - kein gueltiger Python-Modulname, daher per
# Pfad statt per "import" geladen. Der Loader liegt hier in conftest.py statt in einem Testmodul,
# weil Fixtures aus einem Testmodul modul-lokal sind und mehrere Testmodule dasselbe Skript
# brauchen.
_SEED_SCRIPT_PATH = _SCRIPTS_DIR / "seed-opencloud-demo.py"


def _load_module(module_name: str, script_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def seed_module() -> ModuleType:
    return _load_module("seed_opencloud_demo", _SEED_SCRIPT_PATH)


# --- Spielplaetze fuer die Verhaltenstests der Bash-Skripte unter scripts/ ----------------------
#
# Hier statt in einem Testmodul, weil zwei Module denselben Aufbau brauchen (test_format_sh.py
# und test_check_sh.py) und eine Fixture aus einem Testmodul modul-lokal ist - derselbe Grund wie
# beim Skript-Loader oben.
#
# **Bauart.** Ein Spielplatz ist ein temporaeres Verzeichnis mit derselben Struktur wie das
# Repositorium (das zu pruefende Skript, beide pyproject.toml, beide package.json, beide
# node_modules/), aber ohne jeden echten Inhalt. Die Skripte leiten ihre vier Baeume aus ihrem
# **eigenen Ablageort** ab; genau das macht diese Bauart moeglich. `ruff`, `npm` und `mypy`
# liegen als aufzeichnende Attrappen auf dem PATH - sie schreiben Arbeitsverzeichnis, Herkunft
# und Argumente in eine Protokolldatei, statt etwas zu tun.
#
# **Umgebungsisolierung.** Jeder Unterprozess bekommt ein vollstaendig gesetztes Environment mit
# einem PATH, der ausschliesslich auf das Attrappenverzeichnis und die Systemverzeichnisse zeigt
# - ein echtes `ruff` aus Daniels ~/.local/bin liesse sonst die Versionsfaelle aus dem falschen
# Grund gruen werden. Jeder Aufruf traegt ein Timeout; ein haengendes Skript ist in CI ein
# Stundenjob, kein roter Test.

SKRIPT_FORMAT_SH = "scripts/format.sh"
SKRIPT_CHECK_SH = "scripts/check.sh"

PYTHON_BAEUME = ("backend", "scripts")
TS_BAEUME = ("frontend", "e2e")

GEPINNTE_VERSION = "0.16.4"
ZEITGRENZE_SEKUNDEN = 60

# Die npm-Skripte, die die echten package.json der beiden TypeScript-Baeume fuehren, soweit
# format.sh oder check.sh sie aufrufen.
NPM_SKRIPTE_JE_BAUM: dict[str, tuple[str, ...]] = {
    "frontend": ("format", "format:check", "lint", "typecheck"),
    "e2e": ("format", "format:check", "typecheck"),
}


def _attrappe(name: str, *, versions_ausdruck: str | None = None) -> str:
    """Eine aufzeichnende Attrappe fuer ein Werkzeug.

    Protokollzeile: `<Arbeitsverzeichnis>|<Programm>|<aufgerufener Pfad>|<Argumente>`. Das
    Arbeitsverzeichnis belegt, dass das Skript im jeweiligen Baum aufruft und nicht viermal in
    der Wurzel; der aufgerufene Pfad belegt, dass Phase 2 dasselbe Binary nimmt, dessen Version
    Phase 1 geprueft hat.

    `versions_ausdruck` schaltet die `--version`-Antwort frei (nur `ruff` kennt sie). Er wird
    **als Bash-Ausdruck** eingesetzt: `"$SPIELPLATZ_RUFF_AUSGABE"` fuer die Attrappe auf dem
    PATH, eine literale Zeichenkette fuer eine Attrappe in `<baum>/.venv/bin/`, die bewusst
    etwas anderes meldet als der PATH.

    `SPIELPLATZ_BEFUNDE` steuert, welcher einzelne Pruefaufruf mit 1 endet - Schluesselform
    `[<baum>|<programm>|<argumente>]`. Ohne Treffer endet jeder Aufruf mit 0.
    """
    zeilen = [
        "#!/usr/bin/env bash",
        "printf '%s|" + name + '|%s|%s\\n\' "$PWD" "$0" "$*" >> "$SPIELPLATZ_PROTOKOLL"',
    ]
    if versions_ausdruck is not None:
        zeilen += [
            'if [ "${1:-}" = "--version" ]; then',
            "  printf '%s\\n' " + versions_ausdruck,
            '  exit "${SPIELPLATZ_RUFF_EXIT:-0}"',
            "fi",
        ]
    zeilen += [
        'schluessel="${PWD##*/}|' + name + '|$*"',
        'case "${SPIELPLATZ_BEFUNDE:-}" in',
        '  *"[$schluessel]"*) exit 1 ;;',
        "esac",
        "exit 0",
        "",
    ]
    return "\n".join(zeilen)


def _schreibe_ausfuehrbar(pfad: Path, inhalt: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(inhalt, encoding="utf-8")
    pfad.chmod(pfad.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _pyproject(pin_zeile: str | None) -> str:
    """Eine `pyproject.toml`, die nur so viel traegt, wie die Skripte lesen."""
    dev = ['    "pytest>=8.3",']
    if pin_zeile is not None:
        dev.append(f"    {pin_zeile}")
    zeilen = [
        "[project]",
        'name = "probe"',
        'version = "0.0.0"',
        "",
        "[project.optional-dependencies]",
        "dev = [",
        *dev,
        "]",
        "",
        "[tool.ruff]",
        "line-length = 100",
        "",
        "# Auskommentiert und damit unwirksam - ein Leser, der den Rohtext greppt, faellt hierauf",
        "# herein: ",
        '#     "ruff==9.9.9",',
        "",
        "[tool.ruff.format]",
        'exclude = ["*.md"]',
        "",
    ]
    return "\n".join(zeilen)


def _package_json(skripte: Sequence[str], koeder: Sequence[str] = ()) -> str:
    """Eine `package.json`, die nur die Skriptnamen traegt.

    `koeder` landen als Schluessel in `devDependencies` - also **ausserhalb** des
    `scripts`-Blocks. Ein Leser, der die ganze Datei nach dem Namen durchsucht, statt den
    `scripts`-Block abzugrenzen, haelt ein entferntes Skript dann faelschlich fuer vorhanden.
    """
    abhaengigkeiten = [*koeder, "prettier"]
    zeilen = ["{", '  "name": "probe",', '  "private": true,', '  "scripts": {']
    for stelle, skript in enumerate(skripte):
        komma = "," if stelle < len(skripte) - 1 else ""
        zeilen.append(f'    "{skript}": "echo {skript}"{komma}')
    zeilen += ["  },", '  "devDependencies": {']
    for stelle, paket in enumerate(abhaengigkeiten):
        komma = "," if stelle < len(abhaengigkeiten) - 1 else ""
        zeilen.append(f'    "{paket}": "1.0.0"{komma}')
    zeilen += ["  }", "}", ""]
    return "\n".join(zeilen)


@dataclass(frozen=True)
class Spielplatz:
    wurzel: Path
    protokoll: Path
    env: dict[str, str]
    skript_relativ: str

    @property
    def skript(self) -> Path:
        return self.wurzel / self.skript_relativ

    def rohe_aufrufe(self) -> list[tuple[str, str, str, str]]:
        """Alle Attrappen-Aufrufe als (Baum, Programm, aufgerufener Pfad, Argumente)."""
        if not self.protokoll.exists():
            return []
        ergebnis: list[tuple[str, str, str, str]] = []
        for zeile in self.protokoll.read_text(encoding="utf-8").splitlines():
            if not zeile.strip():
                continue
            arbeitsverzeichnis, programm, pfad, argumente = zeile.split("|", 3)
            baum = str(Path(arbeitsverzeichnis).resolve().relative_to(self.wurzel.resolve()))
            ergebnis.append((baum, programm, pfad, argumente))
        return ergebnis

    def aufrufe(self) -> list[tuple[str, str, str]]:
        """Alle Attrappen-Aufrufe als (Baum, Programm, Argumente)."""
        return [(baum, programm, argumente) for baum, programm, _, argumente in self.rohe_aufrufe()]

    def pruefaufrufe(self) -> list[tuple[str, str, str]]:
        """Alle Aufrufe ausser den Vorbedingungs-Abfragen (`--version`)."""
        return [
            (baum, programm, argumente)
            for baum, programm, argumente in self.aufrufe()
            if argumente != "--version"
        ]

    def herkunft(self, baum: str, programm: str) -> list[str]:
        """Die aufgerufenen Binaerpfade je (Baum, Programm), ohne `--version`-Abfragen."""
        return [
            pfad
            for gemessener_baum, gemessenes_programm, pfad, argumente in self.rohe_aufrufe()
            if gemessener_baum == baum
            and gemessenes_programm == programm
            and argumente != "--version"
        ]

    def formatierlaeufe(self) -> list[tuple[str, str]]:
        """Nur die Aufrufe, die tatsaechlich etwas umschreiben wuerden.

        `ruff format` **ohne** `--check` und `npm run format` **ohne** `:check` - die beiden
        Formen, die Dateien anfassen. Die pruefenden Geschwister (`ruff format --check .`,
        `npm run format:check`) zaehlen hier ausdruecklich nicht mit; genau daran haengt die
        Zusicherung, dass `check.sh` nie schreibt.
        """
        ergebnis: list[tuple[str, str]] = []
        for baum, programm, argumente in self.aufrufe():
            felder = argumente.split()
            schreibt = (
                programm == "ruff" and felder[:1] == ["format"] and "--check" not in felder
            ) or (programm == "npm" and felder[:2] == ["run", "format"])
            if schreibt:
                ergebnis.append((baum, programm))
        return ergebnis


def _vorbereitet(pfad: Path) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    return pfad


def baue_spielplatz(
    wurzel: Path,
    *,
    skript: str = SKRIPT_FORMAT_SH,
    attrappen: Sequence[str] = ("ruff", "npm"),
    pin_je_baum: dict[str, str | None] | None = None,
    ruff_ausgabe: str = f"ruff {GEPINNTE_VERSION}",
    ruff_exit: int = 0,
    node_modules_je_baum: dict[str, bool] | None = None,
    venv_ruff_ausgabe_je_baum: dict[str, str] | None = None,
    npm_skripte_je_baum: dict[str, tuple[str, ...]] | None = None,
    befunde: Sequence[tuple[str, str, str]] = (),
) -> Spielplatz:
    pin_je_baum = pin_je_baum or {}
    node_modules_je_baum = node_modules_je_baum or {}
    venv_ruff_ausgabe_je_baum = venv_ruff_ausgabe_je_baum or {}
    npm_skripte_je_baum = npm_skripte_je_baum or {}

    wurzel.mkdir(parents=True, exist_ok=True)
    protokoll = wurzel / "attrappen.log"
    attrappen_verzeichnis = wurzel / "attrappen"

    shutil.copy2(REPO_WURZEL / skript, _vorbereitet(wurzel / skript))
    (wurzel / skript).chmod(0o755)

    for baum in PYTHON_BAEUME:
        pin = pin_je_baum.get(baum, f'"ruff=={GEPINNTE_VERSION}",')
        _vorbereitet(wurzel / baum / "pyproject.toml").write_text(_pyproject(pin), encoding="utf-8")
        ausgabe = venv_ruff_ausgabe_je_baum.get(baum)
        if ausgabe is not None:
            _schreibe_ausfuehrbar(
                wurzel / baum / ".venv" / "bin" / "ruff",
                _attrappe("ruff", versions_ausdruck=f'"{ausgabe}"'),
            )

    for baum in TS_BAEUME:
        vorgabe = NPM_SKRIPTE_JE_BAUM[baum]
        skripte = npm_skripte_je_baum.get(baum, vorgabe)
        koeder = tuple(name for name in vorgabe if name not in skripte)
        _vorbereitet(wurzel / baum / "package.json").write_text(
            _package_json(skripte, koeder), encoding="utf-8"
        )
        if node_modules_je_baum.get(baum, True):
            (wurzel / baum / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)

    for name in attrappen:
        versions_ausdruck = '"$SPIELPLATZ_RUFF_AUSGABE"' if name == "ruff" else None
        _schreibe_ausfuehrbar(
            attrappen_verzeichnis / name, _attrappe(name, versions_ausdruck=versions_ausdruck)
        )

    env = {
        "PATH": f"{attrappen_verzeichnis}:/usr/bin:/bin",
        "HOME": str(wurzel),
        "SPIELPLATZ_PROTOKOLL": str(protokoll),
        "SPIELPLATZ_RUFF_AUSGABE": ruff_ausgabe,
        "SPIELPLATZ_RUFF_EXIT": str(ruff_exit),
        "SPIELPLATZ_BEFUNDE": "".join(
            f"[{baum}|{programm}|{argumente}]" for baum, programm, argumente in befunde
        ),
        "LC_ALL": "C",
    }
    return Spielplatz(wurzel=wurzel, protokoll=protokoll, env=env, skript_relativ=skript)


@dataclass(frozen=True)
class Ergebnis:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def meldung(self) -> str:
        return f"{self.stdout}\n{self.stderr}"


def laufe(spielplatz: Spielplatz, *, cwd: Path | None = None) -> Ergebnis:
    fertig = subprocess.run(
        [str(spielplatz.skript)],
        cwd=str(cwd or spielplatz.wurzel),
        env=spielplatz.env,
        capture_output=True,
        text=True,
        timeout=ZEITGRENZE_SEKUNDEN,
    )
    return Ergebnis(fertig.returncode, fertig.stdout, fertig.stderr)


@pytest.fixture
def spielplatz_fabrik(tmp_path: Path) -> Iterator[Callable[..., Spielplatz]]:
    """Baut beliebig viele Spielplaetze je Test, jeden in einem eigenen Unterverzeichnis."""
    zaehler = {"n": 0}

    def bauen(**kwargs: object) -> Spielplatz:
        zaehler["n"] += 1
        return baue_spielplatz(tmp_path / f"spielplatz{zaehler['n']}", **kwargs)  # type: ignore[arg-type]

    yield bauen
