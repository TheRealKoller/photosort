"""Die Bilanz hat einen mechanischen Traeger: `waechter_aussagen.json`.

Vier Aussagen, ein Test:

1. Die aktive Menge ist **gleich** der aus den Modulen gelesenen - beide Richtungen. Faellt ein
   Modul mitsamt seinen Mutationseintraegen, faellt auch dieser Test.
2. Jede aktive Klasse ist A oder B; C ist die Klasse der gefallenen Pruefungen.
3. Jede entfernte Pruefung ist im Testbaum **nicht mehr vorhanden** - sonst behauptet die Bilanz
   eine Loeschung, die nicht stattfand - und nennt einen Satz.
4. Jede genannte Traegerin existiert als `def test_...` im Baum, sonst steht ein `grund` da.

Dazu eine Untergrenze der aktiven Aussagen, bewusst unter dem Ist-Stand: sie faengt den
Massenverlust, den kein Einzeleintrag verraet. Was die Bilanz nicht kann: den GitHub-Verlauf
pruefen - die Decke ist der Diff.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from test_board_befehle_in_skills import INVARIANTEN as BOARD
from test_ci_warten_verankert import INVARIANTEN as WARTEN
from test_ci_wirkung import INVARIANTEN as CI
from test_frontend_typen import INVARIANTEN as FRONTEND_TYPEN
from test_github_zugriff_an_einer_stelle import INVARIANTEN as KATALOG
from test_issue_befehle_in_skills import INVARIANTEN as BEFEHLE

TESTS = Path(__file__).parent
BILANZ = TESTS / "waechter_aussagen.json"
MODULE = {
    "scripts/tests/test_github_zugriff_an_einer_stelle.py": KATALOG,
    "scripts/tests/test_ci_wirkung.py": CI,
    "scripts/tests/test_issue_befehle_in_skills.py": BEFEHLE,
    "scripts/tests/test_board_befehle_in_skills.py": BOARD,
    "scripts/tests/test_ci_warten_verankert.py": WARTEN,
    "scripts/tests/test_frontend_typen.py": FRONTEND_TYPEN,
}
MINDESTZAHL_AKTIV = 18
TESTFUNKTION = re.compile(r"^def (?P<name>test_[a-z0-9_]+)\(", re.MULTILINE)
PRUEFUNG = re.compile(r"^scripts/tests/(?P<datei>test_[a-z0-9_]+\.py)::(?P<name>test_[a-z0-9_]+)$")

BILANZ_INHALT = json.loads(BILANZ.read_text(encoding="utf-8"))


def _testfunktionen() -> dict[str, set[str]]:
    """Alle `test_...`-Funktionen je Datei im Testbaum."""
    return {
        pfad.name: {treffer.group("name") for treffer in TESTFUNKTION.finditer(pfad.read_text())}
        for pfad in TESTS.glob("test_*.py")
    }


def test_die_aktive_menge_deckt_sich_mit_den_modulen() -> None:
    """Beide Richtungen: keine Invariante ohne Bilanzzeile, keine Bilanzzeile ohne Invariante."""
    bilanziert = {(eintrag["modul"], eintrag["invariante"]) for eintrag in BILANZ_INHALT["aktiv"]}
    gelesen = {
        (modul, invariante.id)
        for modul, invarianten in MODULE.items()
        for invariante in invarianten
    }

    assert bilanziert == gelesen, (
        f"nur bilanziert: {sorted(bilanziert - gelesen)}; "
        f"nur gelesen: {sorted(gelesen - bilanziert)}"
    )


def test_jede_aktive_aussage_hat_klasse_a_oder_b() -> None:
    """Klasse C ist die Klasse der gefallenen Pruefung - sie traegt keine Aussage mehr."""
    falsch = [eintrag for eintrag in BILANZ_INHALT["aktiv"] if eintrag["klasse"] not in {"A", "B"}]

    assert not falsch, f"aktive Aussagen mit Klasse C oder unbekannt: {falsch}"


def test_die_aktive_menge_unterschreitet_die_untergrenze_nicht() -> None:
    """Ein Massenverlust faellt hier auf, bevor ihn ein Einzeleintrag verraet."""
    aktiv = BILANZ_INHALT["aktiv"]

    assert len(aktiv) >= MINDESTZAHL_AKTIV, (
        f"nur {len(aktiv)} aktive Aussagen, Untergrenze {MINDESTZAHL_AKTIV}."
    )


def test_jede_entfernte_pruefung_ist_wirklich_weg_und_hat_einen_satz() -> None:
    """Eine Bilanzzeile ueber eine noch vorhandene Pruefung waere eine Behauptung ohne Deckung."""
    vorhanden = _testfunktionen()
    befunde: list[str] = []
    for eintrag in BILANZ_INHALT["entfernt"]:
        treffer = PRUEFUNG.match(eintrag["pruefung"])
        if treffer is None:
            befunde.append(f"unlesbare Pruefung {eintrag['pruefung']!r}")
            continue
        if not eintrag["satz"].strip():
            befunde.append(f"{eintrag['pruefung']}: kein Satz")
        if treffer.group("name") in vorhanden.get(treffer.group("datei"), set()):
            befunde.append(f"{eintrag['pruefung']}: existiert noch im Testbaum")

    assert not befunde, "Bilanz-Befunde: " + "; ".join(befunde)


def test_jede_genannte_traegerin_existiert_oder_es_steht_ein_grund_da() -> None:
    """Ein Traeger ohne Testfunktion ist ein Verweis ins Leere; ohne Grund bleibt die Pruefung offen."""
    vorhanden = _testfunktionen()
    alle = set().union(*vorhanden.values())
    befunde = [
        f"{eintrag['pruefung']}: Traeger {eintrag['traeger']!r} fehlt und kein Grund"
        for eintrag in BILANZ_INHALT["entfernt"]
        if not (eintrag["traeger"] in alle or eintrag["grund"].strip())
    ]

    assert not befunde, "Bilanz-Befunde: " + "; ".join(befunde)
