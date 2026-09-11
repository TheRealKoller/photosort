r"""Verhaltenstests fuer `scripts/format.sh` gegen synthetische Spielplaetze.

Geprueft wird ein Bash-Skript mit echter Verzweigungslogik (ADR 0080 Abschnitt 12, Spec 0400
Abschnitt 9): Es liest den `ruff`-Pin aus der `pyproject.toml` je Python-Baum, parst die Ausgabe
von `ruff --version`, vergleicht beides und prueft `node_modules` in beiden TypeScript-Baeumen.
Das Formatieren selbst ist Fremdverhalten und wird ausdruecklich nicht nachgebildet - geprueft
werden die **Vorbedingungen** und die **Aufrufe**, die daraus folgen.

**Der tragende Fall ist der stille** (Spec 0400, Abschnitt 10, Regel 5): Liefert die
Pin-Extraktion den Leerstring und die Versionsextraktion ebenfalls, dann besteht ein naiver
Vergleich `"" == ""` - und das Skript formatiert mit der falschen Version genau den Diff, den es
verhindern soll.

**Und er wird nur von einem einzigen Test dieses Moduls wirklich gestellt**, naemlich
`test_leerer_pin_und_leere_versionsausgabe_bestehen_nicht_gegeneinander`. Das ist keine
Feinheit, sondern an einer Mutationsprobe gemessen (2026-09-11): Mit allen drei Waechtern aus
dem Skript entfernt blieben die naheliegenden Faelle - fehlender Pin, mehrdeutiger Pin, unlesbare
`ruff --version`-Ausgabe - saemtlich **gruen**, weil bei jedem von ihnen nur EINE Seite leer ist
und der Lauf am Unterschied gegen die nicht-leere Gegenseite abbricht. Wer diese Datei erweitert:
Ein Leerstring-Fall, der die Gegenseite gefuellt laesst, prueft den stillen Fall nicht.

**Bauform der Spielplaetze.** Ein Spielplatz ist ein temporaeres Verzeichnis mit derselben
Struktur wie das Repositorium (`scripts/format.sh`, beide `pyproject.toml`, beide
`package.json`, beide `node_modules/`), aber ohne jeden echten Inhalt. Das Skript leitet die vier
Baeume aus seinem **eigenen Ablageort** ab; genau das macht diese Bauform moeglich und wird
deshalb mitgeprueft. `ruff` und `npm` liegen als aufzeichnende Attrappen auf dem `PATH` - sie
schreiben ihr Arbeitsverzeichnis und ihre Argumente in eine Protokolldatei, statt etwas zu tun.
Kein Netzwerk, kein echtes `npm`, kein `bats-core`/`shunit2` (Testkonzept, Sektion "Bash-Skript
mit echter Verzweigung").

**Umgebungsisolierung.** Jeder Unterprozess bekommt ein vollstaendig gesetztes Environment mit
einem `PATH`, der ausschliesslich auf das Attrappenverzeichnis und die Systemverzeichnisse zeigt
- ein echtes `ruff` aus Daniels `~/.local/bin` liesse sonst die Versionsfaelle aus dem falschen
Grund gruen werden. Jeder Aufruf traegt ein Timeout; ein haengendes Skript ist in CI ein
Stundenjob, kein roter Test.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]
SKRIPT_REPO_RELATIV = "scripts/format.sh"
SKRIPT_PFAD = REPO_WURZEL / SKRIPT_REPO_RELATIV

PYTHON_BAEUME = ("backend", "scripts")
TS_BAEUME = ("frontend", "e2e")

GEPINNTE_VERSION = "0.16.4"
ZEITGRENZE_SEKUNDEN = 60

# Selbstschutz gegen einen leeren Suchraum: Ein Skripttext von 0 wirksamen Zeilen liesse jede
# statische Abwesenheitspruefung unten vakuum-gruen werden.
MINDESTZAHL_WIRKSAMER_ZEILEN = 20


# --- Attrappen ---------------------------------------------------------------------------------

# Die Attrappen protokollieren "<Arbeitsverzeichnis>|<Programm>|<Argumente>" je Aufruf. Das
# Arbeitsverzeichnis ist die eigentliche Zusicherung: Es belegt, dass das Skript den Formatierer
# **im jeweiligen Baum** aufruft und nicht viermal in der Wurzel.
_ATTRAPPE = """#!/usr/bin/env bash
printf '%s|{name}|%s\\n' "$PWD" "$*" >> "$FORMAT_SH_PROTOKOLL"
{koerper}
"""

_RUFF_KOERPER = """
if [ "${1:-}" = "--version" ]; then
  printf '%s\\n' "$FORMAT_SH_RUFF_AUSGABE"
fi
exit "${FORMAT_SH_RUFF_EXIT:-0}"
"""

_NPM_KOERPER = """
exit 0
"""


def _schreibe_ausfuehrbar(pfad: Path, inhalt: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(inhalt, encoding="utf-8")
    pfad.chmod(pfad.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _pyproject(pin_zeile: str | None) -> str:
    """Eine `pyproject.toml`, die nur so viel traegt, wie das Skript liest."""
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


# --- Spielplatz --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Spielplatz:
    wurzel: Path
    protokoll: Path
    env: dict[str, str]

    @property
    def skript(self) -> Path:
        return self.wurzel / SKRIPT_REPO_RELATIV

    def aufrufe(self) -> list[tuple[str, str, str]]:
        """Alle Attrappen-Aufrufe als (Baum, Programm, Argumente)."""
        if not self.protokoll.exists():
            return []
        ergebnis: list[tuple[str, str, str]] = []
        for zeile in self.protokoll.read_text(encoding="utf-8").splitlines():
            if not zeile.strip():
                continue
            arbeitsverzeichnis, programm, argumente = zeile.split("|", 2)
            baum = str(Path(arbeitsverzeichnis).resolve().relative_to(self.wurzel.resolve()))
            ergebnis.append((baum, programm, argumente))
        return ergebnis

    def formatierlaeufe(self) -> list[tuple[str, str]]:
        """Nur die Aufrufe, die tatsaechlich etwas umschreiben wuerden."""
        return [
            (baum, programm)
            for baum, programm, argumente in self.aufrufe()
            if (programm == "ruff" and argumente.startswith("format"))
            or (programm == "npm" and argumente == "run format")
        ]


def baue_spielplatz(
    wurzel: Path,
    *,
    pin_je_baum: dict[str, str | None] | None = None,
    ruff_ausgabe: str = f"ruff {GEPINNTE_VERSION}",
    ruff_exit: int = 0,
    node_modules_je_baum: dict[str, bool] | None = None,
    venv_ruff_ausgabe_je_baum: dict[str, str] | None = None,
) -> Spielplatz:
    pin_je_baum = pin_je_baum or {}
    node_modules_je_baum = node_modules_je_baum or {}
    venv_ruff_ausgabe_je_baum = venv_ruff_ausgabe_je_baum or {}

    wurzel.mkdir(parents=True, exist_ok=True)
    protokoll = wurzel / "attrappen.log"
    attrappen_verzeichnis = wurzel / "attrappen"

    shutil.copy2(SKRIPT_PFAD, _vorbereitet(wurzel / SKRIPT_REPO_RELATIV))
    (wurzel / SKRIPT_REPO_RELATIV).chmod(0o755)

    for baum in PYTHON_BAEUME:
        pin = pin_je_baum.get(baum, f'"ruff=={GEPINNTE_VERSION}",')
        _vorbereitet(wurzel / baum / "pyproject.toml").write_text(_pyproject(pin), encoding="utf-8")
        ausgabe = venv_ruff_ausgabe_je_baum.get(baum)
        if ausgabe is not None:
            _schreibe_ausfuehrbar(
                wurzel / baum / ".venv" / "bin" / "ruff",
                _ATTRAPPE.format(name="ruff", koerper=_RUFF_KOERPER).replace(
                    '"$FORMAT_SH_RUFF_AUSGABE"', f'"{ausgabe}"'
                ),
            )

    for baum in TS_BAEUME:
        _vorbereitet(wurzel / baum / "package.json").write_text(
            '{\n  "name": "probe",\n  "scripts": { "format": "prettier --write ." }\n}\n',
            encoding="utf-8",
        )
        if node_modules_je_baum.get(baum, True):
            (wurzel / baum / "node_modules" / ".bin").mkdir(parents=True, exist_ok=True)

    _schreibe_ausfuehrbar(
        attrappen_verzeichnis / "ruff", _ATTRAPPE.format(name="ruff", koerper=_RUFF_KOERPER)
    )
    _schreibe_ausfuehrbar(
        attrappen_verzeichnis / "npm", _ATTRAPPE.format(name="npm", koerper=_NPM_KOERPER)
    )

    env = {
        "PATH": f"{attrappen_verzeichnis}:/usr/bin:/bin",
        "HOME": str(wurzel),
        "FORMAT_SH_PROTOKOLL": str(protokoll),
        "FORMAT_SH_RUFF_AUSGABE": ruff_ausgabe,
        "FORMAT_SH_RUFF_EXIT": str(ruff_exit),
        "LC_ALL": "C",
    }
    return Spielplatz(wurzel=wurzel, protokoll=protokoll, env=env)


def _vorbereitet(pfad: Path) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    return pfad


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
def fabrik(tmp_path: Path) -> Iterator[Callable[..., Spielplatz]]:
    zaehler = {"n": 0}

    def bauen(**kwargs: object) -> Spielplatz:
        zaehler["n"] += 1
        return baue_spielplatz(tmp_path / f"spielplatz{zaehler['n']}", **kwargs)  # type: ignore[arg-type]

    yield bauen


# --- 1. Das Skript selbst ----------------------------------------------------------------------


def skripttext() -> str:
    return SKRIPT_PFAD.read_text(encoding="utf-8")


def wirksamer_skripttext() -> str:
    """Ganzzeilige Kommentare zu Leerzeilen, alles andere unberuehrt.

    Zwingend fuer die Abwesenheitspruefungen unten: Der Kopfkommentar des Skripts benennt genau
    das, was im Skriptkoerper nicht vorkommen darf (Stiloptionen, `eval`), und wuerde die
    Pruefung sonst mit der Dokumentation rot machen, die sie erzwingen soll.
    """
    return "\n".join(
        "" if zeile.lstrip().startswith("#") else zeile for zeile in skripttext().splitlines()
    )


def test_das_skript_existiert_und_ist_ausfuehrbar() -> None:
    assert SKRIPT_PFAD.is_file(), (
        f"{SKRIPT_REPO_RELATIV} fehlt. docs/setup.md nennt den Pfad woertlich, und die "
        "CI-Formatpruefung ist ohne einen lokalen Befehl, der sie beheben kann, eine Sackgasse."
    )
    assert os.access(SKRIPT_PFAD, os.X_OK), (
        f"{SKRIPT_REPO_RELATIV} ist nicht ausfuehrbar (Modus "
        f"{SKRIPT_PFAD.stat().st_mode & 0o777:o}). Das Ausfuehrungsbit ist Teil des Commits."
    )


def test_das_skript_bricht_bei_fehlern_ab_statt_weiterzulaufen() -> None:
    text = wirksamer_skripttext()
    assert len(text.strip().splitlines()) >= MINDESTZAHL_WIRKSAMER_ZEILEN, (
        "Zu wenige wirksame Zeilen im Skript - die Abwesenheitspruefungen dieses Moduls waeren "
        "vakuum-gruen."
    )
    assert "set -euo pipefail" in text, (
        "Sicherheitskonzept S4: Ohne 'set -euo pipefail' laeuft das Skript nach einem "
        "fehlgeschlagenen Teilschritt weiter und hinterlaesst einen halb formatierten Baum."
    )


def test_das_skript_setzt_den_gelesenen_pin_nie_in_eine_ausfuehrung_ein() -> None:
    """Sicherheitskonzept S4: Der Wert wird ausschliesslich verglichen."""
    text = wirksamer_skripttext()
    for verboten in ("eval ", "eval\t", "uvx ", "pip install", "uv pip"):
        assert verboten not in text, (
            f"{SKRIPT_REPO_RELATIV} enthaelt {verboten!r}. Der aus der pyproject.toml gelesene "
            "Wert darf nur verglichen werden - nie in eine Kommandozeile, nie in eine "
            "Installation."
        )


def test_das_skript_fuehrt_keine_stiloptionen_und_keine_dateilisten() -> None:
    """ADR 0080 Abschnitt 12: reine Bequemlichkeit, keine zweite Quelle der Wahrheit."""
    text = wirksamer_skripttext()
    for verboten in (
        "--line-length",
        "--config",
        "printWidth",
        "singleQuote",
        "--no-semi",
        "--ignore-path",
    ):
        assert verboten not in text, (
            f"{SKRIPT_REPO_RELATIV} enthaelt {verboten!r}. Der Geltungsbereich und der Stil "
            "stehen in den Konfigurationsdateien; eine zweite Angabe hier koennte von der "
            "CI-Pruefung abweichen, ohne dass es auffaellt."
        )


# --- 2. Der gute Fall --------------------------------------------------------------------------


def test_bei_passender_version_und_vorhandenem_node_modules_laufen_alle_vier_baeume(
    fabrik: Callable[..., Spielplatz],
) -> None:
    spielplatz = fabrik()
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code == 0, ergebnis.meldung
    assert spielplatz.formatierlaeufe() == [
        ("backend", "ruff"),
        ("scripts", "ruff"),
        ("frontend", "npm"),
        ("e2e", "npm"),
    ], (
        "Erwartet wird je Baum genau ein Formatierlauf, im jeweiligen Baum als "
        f"Arbeitsverzeichnis. Protokoll: {spielplatz.aufrufe()}"
    )


def test_das_skript_findet_die_baeume_ueber_seinen_ablageort_nicht_ueber_das_cwd(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """Aufrufbar aus jedem Verzeichnis - sonst formatiert es je nach cwd verschiedene Baeume."""
    spielplatz = fabrik()
    fremdes_verzeichnis = spielplatz.wurzel / "backend"
    ergebnis = laufe(spielplatz, cwd=fremdes_verzeichnis)

    assert ergebnis.exit_code == 0, ergebnis.meldung
    assert len(spielplatz.formatierlaeufe()) == 4, spielplatz.aufrufe()


# --- 3. Die ruff-Version je Baum ---------------------------------------------------------------


def test_eine_abweichende_ruff_version_bricht_ab(fabrik: Callable[..., Spielplatz]) -> None:
    spielplatz = fabrik(ruff_ausgabe="ruff 0.16.1")
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code != 0, ergebnis.meldung
    assert "0.16.1" in ergebnis.meldung and GEPINNTE_VERSION in ergebnis.meldung, (
        "Die Meldung muss beide Versionen nennen - gefundene und erwartete -, sonst weiss der "
        f"Aufrufer nicht, was er zu tun hat. Meldung: {ergebnis.meldung!r}"
    )
    assert "install" in ergebnis.meldung.lower(), (
        "Die Meldung muss den Handgriff nennen, der den Zustand behebt (Neuinstallation der "
        f"Entwicklungsabhaengigkeiten). Meldung: {ergebnis.meldung!r}"
    )


def test_die_version_wird_je_baum_gegen_die_eigene_venv_geprueft(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """Der Fall, der im Repositorium real vorlag: .venv aelter als der Pin, PATH aktuell."""
    spielplatz = fabrik(venv_ruff_ausgabe_je_baum={"scripts": "ruff 0.16.1"})
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code != 0, (
        "Die .venv des Baums traegt 0.16.1, der PATH 0.16.4. Wird nur der PATH geprueft, "
        f"formatiert das Skript mit der falschen Version. Meldung: {ergebnis.meldung!r}"
    )
    assert "scripts" in ergebnis.meldung, (
        f"Die Meldung muss den betroffenen Baum nennen. Meldung: {ergebnis.meldung!r}"
    )


@pytest.mark.parametrize(
    ("pin_zeile", "warum"),
    [
        (None, "kein ruff-Eintrag in der pyproject.toml"),
        ('"ruff>=0.7",', "offene untere Schranke statt exakter Angabe"),
        ('"ruff",', "nackter Eintrag ohne jeden Operator"),
        ('"ruff==0.16.*",', "Wildcard statt exakter Angabe"),
    ],
)
def test_ein_unlesbarer_pin_bricht_ab_statt_leer_gegen_leer_zu_vergleichen(
    fabrik: Callable[..., Spielplatz], pin_zeile: str | None, warum: str
) -> None:
    """Der stille Fall: `"" == ""` besteht, und das Skript formatiert mit irgendeiner Version."""
    spielplatz = fabrik(pin_je_baum={"backend": pin_zeile})
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code != 0, (
        f"{warum}: Die Pin-Extraktion liefert nichts Verwertbares. Ein Vergleich von Leerstring "
        f"gegen Leerstring besteht - und genau dann formatiert das Skript mit der falschen "
        f"Version den Diff, den es verhindern soll. Meldung: {ergebnis.meldung!r}"
    )
    assert "backend/pyproject.toml" in ergebnis.meldung, (
        f"Die Meldung muss den Pfad nennen, an dem der Pin fehlt. Meldung: {ergebnis.meldung!r}"
    )
    assert '"ruff==' in ergebnis.meldung, (
        "Die Meldung muss die erwartete Form nennen und damit belegen, dass der Abbruch am "
        "unlesbaren Pin haengt - nicht zufaellig an einem Versionsunterschied, der nur deshalb "
        f"auffiel, weil die andere Seite gerade nicht leer war. Meldung: {ergebnis.meldung!r}"
    )
    assert spielplatz.formatierlaeufe() == [], spielplatz.aufrufe()


def test_leerer_pin_und_leere_versionsausgabe_bestehen_nicht_gegeneinander(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """Der stille Fall in Reinform - und der einzige Test, der ihn wirklich stellt.

    Die beiden Nachbartests darueber und darunter fangen ihn NICHT: Ist nur eine der beiden
    Seiten leer, bricht auch ein naiver Entwurf ab, naemlich am Versionsunterschied gegen die
    jeweils nicht-leere Gegenseite. Erst wenn **beide** Extraktionen nichts liefern, besteht der
    Vergleich `"" == ""`, und das Skript formatiert mit einer voellig unbekannten Version genau
    den Diff, den es verhindern soll. Am Entwurf gemessen (Mutationsprobe, 2026-09-11): Ohne
    diesen Fall bleiben alle Leerstring-Tests dieses Moduls gruen, obwohl saemtliche drei
    Waechter aus dem Skript entfernt sind.
    """
    # BEIDE Python-Baeume ohne Pin: Bliebe einer stehen, braeche der Lauf an dessen
    # nicht-leerem Pin gegen die leere Versionsangabe ab - und der Test waere aus dem
    # falschen Grund gruen, waehrend der stille Fall ungeprueft bliebe.
    spielplatz = fabrik(pin_je_baum={"backend": None, "scripts": None}, ruff_ausgabe="")
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code != 0, (
        "Pin und gemessene Version sind beide leer. Ein roher Vergleich besteht - und das "
        f"Skript formatiert. Meldung: {ergebnis.meldung!r}"
    )
    assert spielplatz.formatierlaeufe() == [], spielplatz.aufrufe()


def test_ein_mehrdeutiger_pin_bricht_ab(fabrik: Callable[..., Spielplatz]) -> None:
    spielplatz = fabrik(pin_je_baum={"backend": '"ruff==0.16.4",\n    "ruff==0.17.0",'})
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code != 0, (
        "Zwei ruff-Angaben in derselben Datei: Welche gilt, ist nicht entscheidbar. Ein Skript, "
        f"das sich die erste greift, waehlt still. Meldung: {ergebnis.meldung!r}"
    )
    assert spielplatz.formatierlaeufe() == [], spielplatz.aufrufe()


@pytest.mark.parametrize(
    ("ausgabe", "warum"),
    [
        ("", "ruff --version schweigt"),
        ("ruff", "Ausgabe ohne Versionsnummer"),
        ("Fehler: Modul nicht gefunden", "Fremdausgabe statt Versionszeile"),
    ],
)
def test_eine_unlesbare_versionsausgabe_bricht_ab(
    fabrik: Callable[..., Spielplatz], ausgabe: str, warum: str
) -> None:
    """Die zweite Haelfte des stillen Falls - diesmal ist die gemessene Seite leer."""
    spielplatz = fabrik(ruff_ausgabe=ausgabe)
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code != 0, (
        f"{warum}: Ohne verwertbare Versionsangabe ist der Vergleich bedeutungslos. "
        f"Meldung: {ergebnis.meldung!r}"
    )
    assert spielplatz.formatierlaeufe() == [], spielplatz.aufrufe()


def test_ein_fehlgeschlagenes_ruff_version_bricht_ab(fabrik: Callable[..., Spielplatz]) -> None:
    spielplatz = fabrik(ruff_exit=127)
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code != 0, ergebnis.meldung
    assert spielplatz.formatierlaeufe() == [], spielplatz.aufrufe()


# --- 4. node_modules in den TypeScript-Baeumen -------------------------------------------------


@pytest.mark.parametrize("fehlender_baum", TS_BAEUME)
def test_fehlendes_node_modules_bricht_mit_dem_hinweis_auf_npm_ci_ab(
    fabrik: Callable[..., Spielplatz], fehlender_baum: str
) -> None:
    spielplatz = fabrik(node_modules_je_baum={fehlender_baum: False})
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code != 0, ergebnis.meldung
    assert "npm ci" in ergebnis.meldung, (
        "Die Meldung muss den Handgriff woertlich nennen - und zwar 'npm ci', nicht "
        f"'npm install': Das Lockfile ist die Fixierung. Meldung: {ergebnis.meldung!r}"
    )
    assert fehlender_baum in ergebnis.meldung, (
        f"Die Meldung muss den betroffenen Baum nennen. Meldung: {ergebnis.meldung!r}"
    )


# --- 5. Kein halb formatierter Stand -----------------------------------------------------------


def test_eine_verletzte_vorbedingung_im_letzten_baum_verhindert_jeden_formatierlauf(
    fabrik: Callable[..., Spielplatz],
) -> None:
    """Alle Vorbedingungen zuerst, erst danach der erste schreibende Aufruf.

    Ohne diese Reihenfolge haette der Aufrufer nach dem Abbruch einen Baum mit formatiertem
    Backend und unformatiertem Frontend - und keinen Hinweis darauf, wie weit es gekommen ist.
    """
    spielplatz = fabrik(node_modules_je_baum={"e2e": False})
    ergebnis = laufe(spielplatz)

    assert ergebnis.exit_code != 0, ergebnis.meldung
    assert spielplatz.formatierlaeufe() == [], (
        "Die Vorbedingung des letzten Baums ist verletzt, trotzdem wurde bereits formatiert. "
        f"Protokoll: {spielplatz.aufrufe()}"
    )


# --- 6. Der echte Bestand ----------------------------------------------------------------------


def test_der_echte_pin_steht_in_beiden_python_baeumen_exakt_und_gleich() -> None:
    """Gegenprobe gegen die Synthetik: Am echten Bestand findet dasselbe Muster den Pin."""
    import re
    import tomllib

    gefunden: dict[str, str] = {}
    for baum in PYTHON_BAEUME:
        pfad = REPO_WURZEL / baum / "pyproject.toml"
        daten = tomllib.loads(pfad.read_text(encoding="utf-8"))
        eintraege = [
            eintrag
            for eintrag in daten["project"]["optional-dependencies"]["dev"]
            if re.match(r"^ruff\s*[=<>~!]", eintrag) or eintrag.strip() == "ruff"
        ]
        assert len(eintraege) == 1, f"{baum}/pyproject.toml: {eintraege}"
        treffer = re.fullmatch(r"ruff\s*==\s*(\d+\.\d+(?:\.\d+)?)", eintraege[0])
        assert treffer is not None, (
            f"{baum}/pyproject.toml nennt {eintraege[0]!r} - keine exakte Angabe. "
            "Eine offene Schranke fixiert nichts (gemessen: drei verschiedene ruff-Versionen in "
            "drei lokalen Umgebungen desselben Repositoriums unter derselben >=0.7-Angabe)."
        )
        gefunden[baum] = treffer.group(1)

    assert len(set(gefunden.values())) == 1, (
        f"Die beiden Python-Baeume nennen verschiedene ruff-Versionen: {gefunden}. Dann "
        "formatieren sie verschieden, und einer der beiden CI-Jobs wird rot."
    )
