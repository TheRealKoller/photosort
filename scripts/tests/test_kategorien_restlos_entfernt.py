"""Die NEGATIVE Haelfte der Kategorie-Abloesung (specs/features/0427-motive-mit-staerke.md, PR 3).

Jeder Positivtest der Motivstaerken bleibt gruen, wenn daneben ein Kategorie-Rest stehen bleibt:
eine ungenutzte Spalte, ein Antwortfeld mit dauerhaftem `null`, ein Helfer ohne Aufrufer. Genau
das faengt diese Datei - und zwar UEBER BEIDE BAEUME, weil kein Testlauf des einen den anderen
sieht: die Backend-Suite kennt `frontend/src/` nicht, und `vitest` kennt `backend/src/` nicht.

**Zwei Zusicherungen, verschiedene Gegenstaende.**

1. Keine Datei des Produktivcodes nennt einen der sechs abgeloesten Begriffe. Gemeldet werden
   Datei UND Zeile - ein blosser Namensvergleich ohne Ort liesse den Leser suchen.
2. Die beiden Anzeigebaender der Statistik haben genau zwei Leser, und keiner davon liegt im
   Auswahl- oder Rangfolgepfad. Die Baender sind eine ANZEIGEKONVENTION der Statistiktabelle und
   ausdruecklich keine Zugehoerigkeitsschwelle; ein Leser im Auswahlpfad brachte die Schwelle
   zurueck, die diese Story abschafft, und kein Verhaltenstest der Auswahl wuerde davon rot.

**Gemessen wird der Produktivcode, nicht die Tests.** `backend/tests/` nennt die alten Schluessel
weiterhin (die vier historischen Migrationstests bauen ihren Vorher-Schema-Stand von Hand auf,
und die Abbildungstabelle der dreizehn abgeloesten Kategorieschluessel steht als eingefrorener
historischer Stand in `test_motifs.py`). Unter `frontend/src/` liegen Tests neben dem Code; sie
sind deshalb hier mit erfasst - eine Testdatei, die einen entfallenen Schluessel noch nennt,
prueft entweder nichts mehr oder ein Feld, das es nicht mehr gibt.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import REPO_WURZEL

# Die sechs Begriffe der Abloesung. Jeder steht fuer eine Sache, die es nicht mehr gibt:
#
#   category_key            - die Kategoriespalte der Rangzeile und der Kategorietabelle
#   is_primary              - die Haupt-/Nebenzeilen-Unterscheidung
#   category_override       - die dauerhafte manuelle Uebersteuerung
#   nicht_erkannt           - die Auffangkategorie
#   precedence              - die feste Vorrangreihenfolge
#   CONFIDENCE_RANK_PENALTY - die Konfidenz-Daempfung des Sortierschluessels
_ABGELOESTE_BEGRIFFE = (
    "category_key",
    "is_primary",
    "category_override",
    "nicht_erkannt",
    "precedence",
    "CONFIDENCE_RANK_PENALTY",
)

# Die beiden Anzeigebaender. Als Namen gesucht und nicht als Zahl: die Werte stehen als Bruch
# (`2 / 3`) genau einmal im Repositorium, und eine Zahlensuche traefe jeden Zufallswert mit.
_BANDKONSTANTEN = ("MOTIF_STRENGTH_BAND_STRONG", "MOTIF_STRENGTH_BAND_MEDIUM")

# Die EINZIGEN beiden Module, die die Baender lesen durften: die Registry, die sie definiert, und
# die beiden Antwortbausteine, die sie ausliefern. Kein Modul der Auswahl (`worker.py`,
# `ranking.py`, `motif_strengths.py`, `criteria.py`, `scoring.py`, `events.py`,
# `api/photos.py`) steht hier.
_ERLAUBTE_BANDLESER = frozenset(
    {
        "backend/src/photosort/motifs.py",
        "backend/src/photosort/api/motifs.py",
        "backend/src/photosort/api/stats.py",
    }
)


def _produktivdateien() -> list[Path]:
    """Der Produktivcode beider Baeume: Python unter `backend/src/photosort/`, TypeScript und
    TSX unter `frontend/src/`."""
    backend = sorted((REPO_WURZEL / "backend" / "src" / "photosort").rglob("*.py"))
    frontend = sorted(
        pfad
        for endung in ("*.ts", "*.tsx", "*.css")
        for pfad in (REPO_WURZEL / "frontend" / "src").rglob(endung)
    )
    dateien = [pfad for pfad in backend + frontend if "__pycache__" not in pfad.parts]
    assert dateien, "keine Produktivdateien gefunden - stimmt der Pfad?"
    return dateien


def _relativ(pfad: Path) -> str:
    return pfad.relative_to(REPO_WURZEL).as_posix()


def _fundstellen(begriff: str) -> list[str]:
    treffer: list[str] = []
    for pfad in _produktivdateien():
        for nummer, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), start=1):
            if begriff in zeile:
                treffer.append(f"{_relativ(pfad)}:{nummer}: {zeile.strip()}")
    return treffer


@pytest.mark.parametrize("begriff", _ABGELOESTE_BEGRIFFE)
def test_kein_produktivmodul_nennt_einen_abgeloesten_begriff(begriff: str) -> None:
    fundstellen = _fundstellen(begriff)

    assert not fundstellen, "\n".join(
        [f"'{begriff}' ist mit Spec 0427 (PR 3) entfallen, steht aber noch an:", *fundstellen]
    )


def test_beide_baeume_werden_tatsaechlich_durchsucht() -> None:
    """Wirksamkeitsbeleg der Suche selbst: waere einer der beiden Pfade falsch, lieferte
    `_produktivdateien()` nur den anderen Baum, und jeder Fall oben bliebe aus dem falschen Grund
    gruen."""
    gefunden = {_relativ(pfad) for pfad in _produktivdateien()}

    assert "backend/src/photosort/motifs.py" in gefunden
    assert "frontend/src/api/motifs.ts" in gefunden


@pytest.mark.parametrize("konstante", _BANDKONSTANTEN)
def test_nur_die_registry_und_die_antwortbausteine_lesen_die_baender(konstante: str) -> None:
    """Die Baender sind eine Anzeigehilfe der Statistiktabelle, keine Zugehoerigkeitsschwelle.

    Ein Leser im Auswahl- oder Rangfolgepfad ist der eine Fehler, den kein Verhaltenstest der
    Auswahl zeigt: die Auswahl liefe weiter, nur eben mit einer Schwelle."""
    leser = {
        _relativ(pfad)
        for pfad in _produktivdateien()
        if konstante in pfad.read_text(encoding="utf-8")
    }

    assert leser <= _ERLAUBTE_BANDLESER, (
        f"'{konstante}' ist eine Anzeigekonvention der Statistik und darf nur in "
        f"{sorted(_ERLAUBTE_BANDLESER)} vorkommen - gefunden in {sorted(leser - _ERLAUBTE_BANDLESER)}"
    )


def test_das_frontend_bezieht_die_baender_aus_der_antwort() -> None:
    """Die POSITIVE Haelfte derselben Aussage: die Grenzen reisen ueber das Antwortfeld
    `strength_bands` ins Frontend, statt dort zu stehen.

    Die parametrisierte Pruefung oben deckt nur ab, dass die Registry-NAMEN im Frontend nicht
    vorkommen - sie bliebe auch dann gruen, wenn dort `0.67` als Zahl stuende. Dieser Fall ist
    der Beleg, dass die Information tatsaechlich fliesst; `0.67` hier und `2/3` im Backend sind
    nicht derselbe Wert, und kein Anzeigefall traefe die Differenz."""
    leser = {
        _relativ(pfad)
        for pfad in _produktivdateien()
        if "frontend/src" in _relativ(pfad) and "strength_bands" in pfad.read_text(encoding="utf-8")
    }

    assert leser, "keine Frontend-Datei liest `strength_bands` - woher kommen die Bandgrenzen?"
