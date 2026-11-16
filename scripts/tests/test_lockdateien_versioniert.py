"""Haelt die Lockdateien des Repositories als geschlossene, versionierte Menge.

Eine Lockdatei, die nur auf einem Rechner liegt, fixiert fuer alle anderen nichts. Zwei
Zusicherungen, die einander bedingen:

1. **Die versionierte Menge ist exakt.** `{backend/uv.lock, frontend/package-lock.json,
   e2e/package-lock.json, eye/package-lock.json}` - nicht mehr und nicht weniger. Ein fuenfter
   Paketsatz faerbt rot, bis er hier eingetragen ist; das ist die gewollte Reibung, denn der
   Eintrag ist die Entscheidung, diesen Satz zu fixieren.
2. **Nichts liegt unversioniert und nicht ignoriert da.** Eine still entstandene Lockdatei ist
   weder fixiert noch bewusst ausgenommen - sie sieht auf dem Entwicklungsrechner wie eine
   Fixierung aus und ist fuer CI und jeden frischen Klon keine.

Der Katalog der Namen ist bewusst geschlossen und deckt die Paketmanager der fuenf Baeume ab:
`uv` (Backend), `npm` (Frontend, e2e, eye) sowie die gebraeuchlichen Alternativen. `scripts/`
fuehrt bewusst **keine** Lockdatei: ein Entwicklungswerkzeug mit zwei Laufzeitabhaengigkeiten
(`httpx`) und einer Handvoll dev-Werkzeuge. Diese Asymmetrie ist damit eine benannte Entscheidung,
keine Ableitung aus diesem Test.

Gelesen wird `git ls-files -z`: `-z` trennt nullterminiert, damit ein Dateiname mit Leerzeichen
nicht zerfaellt. `--others --exclude-standard` ist die zweite Haelfte - eine Lockdatei existiert in
dem Moment, in dem sie angelegt wird, und genau dann soll die Pruefung laut sein, nicht erst nach
`git add`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

REPO_WURZEL = Path(__file__).parents[2]

# Die Namen, unter denen die Paketmanager der fuenf Baeume eine Aufloesung festhalten. Der Katalog
# ist geschlossen: Ein neuer Paketmanager kommt mit seinem Namen hierher, nicht als Sonderfall in
# die Pruefung.
LOCKDATEINAMEN = (
    "uv.lock",
    "poetry.lock",
    "Pipfile.lock",
    "pdm.lock",
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
)

# Der eine Stand, der gelten soll. Die Reihenfolge ist die der Leseordnung, nicht die eines Sets.
VERSIONIERTE_LOCKDATEIEN = (
    "backend/uv.lock",
    "frontend/package-lock.json",
    "e2e/package-lock.json",
    "eye/package-lock.json",
)


def ist_lockdatei(pfad: str) -> bool:
    """Reine Funktion: traegt der Basename einen der Katalognamen?"""
    return pfad.rpartition("/")[2] in LOCKDATEINAMEN


def lockdateien(pfade: Iterable[str]) -> set[str]:
    """Reine Funktion: die Lockdateien unter den Pfaden, repo-relativ."""
    return {pfad for pfad in pfade if ist_lockdatei(pfad)}


def git_pfade(*argumente: str, wurzel: Path = REPO_WURZEL) -> list[str]:
    """Duenner Leser: nullterminierte Git-Aufzaehlung im Repository."""
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", *argumente],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    return [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]


def versionierte_pfade(wurzel: Path = REPO_WURZEL) -> list[str]:
    return git_pfade("--cached", wurzel=wurzel)


def unversionierte_pfade(wurzel: Path = REPO_WURZEL) -> list[str]:
    """Neu angelegte, nicht ignorierte Pfade - der Zustand vor `git add`."""
    return git_pfade("--others", "--exclude-standard", wurzel=wurzel)


def _als_liste(pfade: Iterable[str]) -> str:
    return "\n".join(f"  {pfad}" for pfad in sorted(pfade)) or "  (keine)"


# --- Die eigentlichen Zusicherungen --------------------------------------------------------


def test_die_versionierte_lockmenge_ist_exakt() -> None:
    tatsaechlich = lockdateien(versionierte_pfade())

    fehlend = sorted(set(VERSIONIERTE_LOCKDATEIEN) - tatsaechlich)
    ueberzaehlig = sorted(tatsaechlich - set(VERSIONIERTE_LOCKDATEIEN))
    assert not (fehlend or ueberzaehlig), (
        "Die versionierte Lockmenge weicht vom festgelegten Stand ab. Fehlend:\n"
        f"{_als_liste(fehlend)}\nUeberzaehlig:\n{_als_liste(ueberzaehlig)}\n"
        "Eine fehlende Datei bedeutet: Dieser Paketsatz wird bei jedem Lauf neu aufgeloest. Eine "
        "ueberzaehlige bedeutet: Ein neuer Paketsatz ist entstanden - dann gehoert er bewusst "
        "hierher eingetragen, statt still mitzulaufen."
    )


def test_keine_lockdatei_liegt_unversioniert_und_nicht_ignoriert() -> None:
    befunde = lockdateien(unversionierte_pfade())

    assert not befunde, (
        "Lockdatei im Arbeitsbaum, aber nicht versioniert und nicht ignoriert:\n"
        f"{_als_liste(befunde)}\n"
        "Sie ist damit weder eine Fixierung noch bewusst ausgenommen. Entweder aufnehmen "
        "(`git add`) oder - falls sie nicht getragen werden soll - ausdruecklich ignorieren."
    )


def test_jeder_festgelegte_lockpfad_existiert() -> None:
    fehlend = [pfad for pfad in VERSIONIERTE_LOCKDATEIEN if not (REPO_WURZEL / pfad).is_file()]

    assert not fehlend, (
        "Im Katalog festgelegt, aber nicht vorhanden:\n"
        f"{_als_liste(fehlend)}\n"
        "Ein Eintrag ohne Datei haelt einen Paketsatz fest, den es nicht gibt."
    )


# --- Gegenproben an synthetischem Material -------------------------------------------------


def test_ein_fuenfter_paketsatz_ist_rot_bis_er_eingetragen_ist() -> None:
    pfade = [*VERSIONIERTE_LOCKDATEIEN, "design/penpot/package-lock.json"]

    assert lockdateien(pfade) - set(VERSIONIERTE_LOCKDATEIEN) == {
        "design/penpot/package-lock.json"
    }


def test_ein_dateiname_mit_leerzeichen_zerfaellt_nicht() -> None:
    assert lockdateien(["mein paket/uv.lock"]) == {"mein paket/uv.lock"}


def test_ein_gleichnamiger_katalogname_in_anderem_verzeichnis_zaehlt_mit() -> None:
    pfade = ["scripts/uv.lock", "backend/uv.lock", "docs/uv.lock.md"]

    assert lockdateien(pfade) == {"scripts/uv.lock", "backend/uv.lock"}


def test_ein_ignorierter_fremd_lock_ist_weder_versioniert_noch_befund(tmp_path: Path) -> None:
    """`--exclude-standard` traegt die bewusste Ausnahme - ohne sie waere sie ein Dauerbefund."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("ignoriert/\n", encoding="utf-8")
    (tmp_path / "ignoriert").mkdir()
    (tmp_path / "ignoriert" / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "uv.lock").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "backend/uv.lock"], cwd=tmp_path, check=True)

    assert lockdateien(versionierte_pfade(tmp_path)) == {"backend/uv.lock"}
    assert lockdateien(unversionierte_pfade(tmp_path)) == set()
