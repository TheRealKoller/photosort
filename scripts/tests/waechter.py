"""Gerüst für Wirkungsprüfungen: jeder Wächter ist eine reine Funktion `Bestand → Befunde`.

Grundlage ist ADR 0148: Eine Prüfung trägt eine Aussage (A), ein Protokoll (B) oder eine Form (C).
Formprüfungen fallen oder werden auf ihre Aussage gehoben; jede umgestellte Prüfung wird eine reine
Funktion über einem Abbild `pfad → text`, und die Fehlererkennung belegen Mutationen in genau einer
Liste (`mutationen.py`), nicht ein Negativtest je Muster.

Ein Befund nennt immer beides: den Ort `datei:zeile` **und** die verletzte Invariante. Den Satz
dazu führt die Invariantenmenge des jeweiligen Wächters — ohne ihn ist ein Befund eine Zeile ohne
Aussage.

**Der Bestand kommt aus `git ls-files`.** Ein Verzeichnislauf fände `.claude/worktrees/` und damit
jede Definition der parallelen Arbeitsstände mehrfach; eine ungetrackte Datei gehört nicht zum
Bestand. Normalisiert werden BOM und Zeilenenden an genau dieser einen Stelle, damit ein Bestand
mit CRLF dieselben Befunde liefert wie derselbe ohne.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_WURZEL = Path(__file__).parents[2]


@dataclass(frozen=True)
class Invariante:
    """Eine Aussage eines Wächters: stabile Kennung und der Satz, den ein Befund tragen muss."""

    id: str
    satz: str


@dataclass(frozen=True)
class Befund:
    """Ein einzelner Verstoß: Ort, verletzte Invariante und der konkrete Anlass."""

    ort: str
    invariante: str
    text: str

    @property
    def meldung(self) -> str:
        return f"{self.ort}: [{self.invariante}] {self.text}"


def zeile_an(text: str, position: int) -> int:
    """Die 1-basierte Zeilennummer der Zeichenposition."""
    return text.count("\n", 0, position) + 1


def befund(
    datei: str,
    zeile: int,
    invariante: str,
    text: str,
) -> Befund:
    """Ein Befund an `datei:zeile`."""
    return Befund(ort=f"{datei}:{zeile}", invariante=invariante, text=text)


def _normalisiere(text: str) -> str:
    """BOM und Zeilenenden vereinheitlichen — die einzige Stelle, an der das geschieht."""
    return text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


class Bestand(Mapping[str, str]):
    """Abbild `pfad → text` über dem getrackten Bestand, unveränderlich und normalisiert."""

    def __init__(self, dateien: Mapping[str, str]) -> None:
        self._dateien = {pfad: _normalisiere(text) for pfad, text in dateien.items()}

    def __getitem__(self, pfad: str) -> str:
        return self._dateien[pfad]

    def __iter__(self) -> Iterator[str]:
        return iter(self._dateien)

    def __len__(self) -> int:
        return len(self._dateien)

    def unter(self, *orte: str) -> dict[str, str]:
        """Die Dateien unter einem der angegebenen Pfadpräfixe; `CLAUDE.md` als ganzer Pfad."""
        return {
            pfad: text
            for pfad, text in self._dateien.items()
            if any(pfad == ort or pfad.startswith(f"{ort}/") for ort in orte)
        }

    def mit(self, pfad: str, text: str) -> Bestand:
        """Eine Kopie mit geändertem Text — Eingabe der Mutationsliste."""
        dateien = dict(self._dateien)
        dateien[pfad] = text
        return Bestand(dateien)

    def ohne(self, pfad: str) -> Bestand:
        dateien = dict(self._dateien)
        dateien.pop(pfad, None)
        return Bestand(dateien)

    def ersetze(self, alt: str, neu: str, datei: str | None = None) -> Bestand:
        """Ersetzt **genau ein** Vorkommen von `alt`; sonst ist der Eintrag unanwendbar."""
        treffer = [pfad for pfad, text in self._dateien.items() if alt in text]
        if datei is not None:
            treffer = [pfad for pfad in treffer if pfad == datei]
        if len(treffer) != 1:
            raise ValueError(
                f"Ersetzung greift nicht: {alt!r} kommt {len(treffer)}-mal vor "
                f"({sorted(treffer)}), erwartet genau einmal."
            )
        pfad = treffer[0]
        return self.mit(pfad, self._dateien[pfad].replace(alt, neu, 1))

    @classmethod
    def aus_arbeitsbaum(cls, wurzel: Path = REPO_WURZEL) -> Bestand:
        """Der Bestand aus `git ls-files` — die einzige I/O-Stelle, einmal je Lauf gelesen."""
        ergebnis = subprocess.run(
            ["git", "ls-files", "-z"], cwd=wurzel, capture_output=True, check=True
        )
        pfade = [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]
        if not pfade:
            raise ValueError(
                "0 Dateien im Bestand: `git ls-files` hat nichts geliefert. Ein leerer Bestand "
                "macht jede Prüfung leer wahr - das ist ein Befund über den Leser, nicht über "
                "das Repository."
            )
        dateien: dict[str, str] = {}
        for pfad in pfade:
            roh = (wurzel / pfad).read_bytes()
            try:
                dateien[pfad] = roh.decode("utf-8")
            except UnicodeDecodeError:
                continue
        return cls(dateien)


def ueberschriften(text: str) -> list[tuple[int, int, str]]:
    """Alle Überschriften einer Datei als `(zeile, ebene, titel)`."""
    kopf = []
    for nummer, zeile in enumerate(text.split("\n"), start=1):
        gestrichen = zeile.lstrip("#")
        if not zeile.startswith("#") or not gestrichen.startswith((" ", "\t")):
            continue
        ebene = len(zeile) - len(gestrichen)
        if 1 <= ebene <= 6:
            kopf.append((nummer, ebene, gestrichen.strip()))
    return kopf


def codebloecke(text: str) -> list[str]:
    """Die Inhalte aller mit ``` oder ~~~ umzäunten Blöcke, ohne die Zäune selbst."""
    bloecke: list[str] = []
    offen: str | None = None
    aktuell: list[str] = []
    for zeile in text.split("\n"):
        gestrichen = zeile.strip()
        if offen is None and gestrichen.startswith(("```", "~~~")):
            offen = gestrichen[:3]
            aktuell = []
            continue
        if offen is not None and gestrichen.startswith(offen):
            bloecke.append("\n".join(aktuell))
            offen = None
            aktuell = []
            continue
        if offen is not None:
            aktuell.append(zeile)
    return bloecke


def ohne_codebloecke(text: str) -> str:
    """Derselbe Text mit geleerten Codeblöcken — Zeilennummern bleiben gültig."""
    ausgabe: list[str] = []
    offen: str | None = None
    for zeile in text.split("\n"):
        gestrichen = zeile.strip()
        if offen is None and gestrichen.startswith(("```", "~~~")):
            offen = gestrichen[:3]
            ausgabe.append("")
            continue
        if offen is not None:
            if gestrichen.startswith(offen):
                offen = None
            ausgabe.append("")
            continue
        ausgabe.append(zeile)
    return "\n".join(ausgabe)


def wortgleiche_abschnitte(bestand: Bestand, marke: str) -> list[str]:
    """Dateien, in denen `marke` in einem Codeblock steht — eine Definition, keine Erwähnung."""
    return [
        pfad for pfad, text in sorted(bestand.items()) if any(marke in b for b in codebloecke(text))
    ]
