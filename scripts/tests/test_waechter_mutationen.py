"""Die Mutationspruefung: jede Invariante wird einmal gebrochen und einmal umformuliert.

Sieben Aussagen in einem Modul:

1. Ueber dem unmutierten Bestand ist jeder Waechter gruen.
2. Eine Umformulierung mit gleicher Aussage bleibt gruen.
3. Jede Mutation erzeugt einen Befund mit ihrer deklarierten Invariante, und der Befund sitzt im
   geaenderten Bereich - nicht irgendwo sonst.
4. Die Mutationsliste deckt jede Invariante jedes Waechters ab und nennt keine unbekannte.
5. Jede Ersetzung greift genau einmal; sonst waere der Eintrag unanwendbar.
6. Ein leerer Bestand ist fuer jeden Waechter rot, und der Leser scheitert laut bei 0 Dateien -
   ein leerer Bestand macht sonst jede Pruefung leer wahr.
7. BOM und CRLF aendern keinen Befund.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from mutationen import MUTATIONEN, UMFORMIERUNGEN, Mutation
from test_ci_wirkung import INVARIANTEN as CI_INVARIANTEN
from test_ci_wirkung import pruefe as ci_pruefe
from test_github_zugriff_an_einer_stelle import INVARIANTEN, pruefe
from waechter import Bestand, zeile_an

BESTAND = Bestand.aus_arbeitsbaum()

WÆCHTER = {"ci": ci_pruefe, "katalog": pruefe}
INVARIANTEN_JE_WÆCHTER = {
    "ci": {invariante.id for invariante in CI_INVARIANTEN},
    "katalog": {invariante.id for invariante in INVARIANTEN},
}


def _anwenden(bestand: Bestand, datei: str, alt: str, neu: str) -> Bestand:
    """Eine Ersetzung anwenden; `Bestand.ersetze` scheitert laut, wenn `alt` nicht genau einmal da ist."""
    return bestand.ersetze(alt, neu, datei=datei)


def _geaenderter_bereich(text: str, alt: str, neu: str) -> tuple[int, int]:
    """Erste und letzte Zeile des geaenderten Bereichs, 1-basiert."""
    beginn = zeile_an(text, text.index(alt))
    return beginn, beginn + len(neu.split("\n")) - 1


def _liegt_im_bereich(befund_ort: str, mutation: Mutation, bereich: tuple[int, int]) -> bool:
    datei, _, nummer = befund_ort.rpartition(":")
    if datei != mutation.datei or not nummer.isdigit():
        return False
    beginn, ende = bereich
    return beginn <= int(nummer) <= ende


@pytest.mark.parametrize("waechter", sorted(WÆCHTER))
def test_der_unmutierte_bestand_ist_gruen(waechter: str) -> None:
    """Ein Waechter, der schon ohne Mutation rot ist, belegt nichts."""
    befunde = WÆCHTER[waechter](BESTAND)

    assert not befunde, "Befunde im unmutierten Bestand: " + "; ".join(
        befund.meldung for befund in befunde
    )


@pytest.mark.parametrize("fall", UMFORMIERUNGEN, ids=[fall.name for fall in UMFORMIERUNGEN])
def test_umformulierung_bleibt_gruen(fall: object) -> None:
    """Gleiche Aussage, anderer Wortlaut: der Waechter erkennt den Inhalt, nicht seine Form."""
    bestand = BESTAND
    for datei, alt, neu in fall.aenderungen:
        bestand = _anwenden(bestand, datei, alt, neu)

    befunde = WÆCHTER[fall.waechter](bestand)

    assert not befunde, f"Umformulierung '{fall.name}' wurde rot: " + "; ".join(
        befund.meldung for befund in befunde
    )


@pytest.mark.parametrize("mutation", MUTATIONEN, ids=[eintrag.name for eintrag in MUTATIONEN])
def test_jede_mutation_erzeugt_ihren_befund(mutation: Mutation) -> None:
    """Bricht die Mutation die deklarierte Invariante, sitzt der Befund im geaenderten Bereich."""
    mutiert = _anwenden(BESTAND, mutation.datei, mutation.alt, mutation.neu)
    befunde = WÆCHTER[mutation.waechter](mutiert)
    eigene = [befund for befund in befunde if befund.invariante == mutation.invariante]
    bereich = _geaenderter_bereich(BESTAND[mutation.datei], mutation.alt, mutation.neu)

    assert eigene, (
        f"Mutation '{mutation.name}' erzeugt keinen Befund zur Invariante "
        f"'{mutation.invariante}'. Befunde: {[befund.meldung for befund in befunde]}"
    )
    assert any(_liegt_im_bereich(befund.ort, mutation, bereich) for befund in eigene), (
        f"Mutation '{mutation.name}': kein Befund zu '{mutation.invariante}' im geaenderten "
        f"Bereich {mutation.datei}:{bereich[0]}-{bereich[1]} - "
        f"{[befund.ort for befund in eigene]}"
    )


@pytest.mark.parametrize("waechter", sorted(WÆCHTER))
def test_mutationen_und_invarianten_decken_sich(waechter: str) -> None:
    """Je Invariante mindestens eine Mutation, und keine Mutation gegen eine unbekannte Invariante."""
    deklariert = {m.invariante for m in MUTATIONEN if m.waechter == waechter}

    assert deklariert <= INVARIANTEN_JE_WÆCHTER[waechter], (
        f"{waechter}: Mutationen nennen unbekannte Invarianten "
        f"{sorted(deklariert - INVARIANTEN_JE_WÆCHTER[waechter])}."
    )
    assert INVARIANTEN_JE_WÆCHTER[waechter] <= deklariert, (
        f"{waechter}: ohne Mutation sind {sorted(INVARIANTEN_JE_WÆCHTER[waechter] - deklariert)}."
    )


@pytest.mark.parametrize(
    "datei,alt",
    [(mutation.datei, mutation.alt) for mutation in MUTATIONEN]
    + [(datei, alt) for fall in UMFORMIERUNGEN for datei, alt, _ in fall.aenderungen],
)
def test_jede_ersetzung_greift_genau_einmal(datei: str, alt: str) -> None:
    """Ein mehrdeutiger Anker macht den Eintrag unanwendbar; das faellt hier auf, nicht im Mutationslauf."""
    assert BESTAND[datei].count(alt) == 1, f"{datei}: {alt[:60]!r} kommt nicht genau einmal vor."


def test_leerer_bestand_ist_fuer_jeden_waechter_rot() -> None:
    """Eine leere Eingabe darf nie gruen sein - ein Befund oder ein lauter Fehler."""
    leer = Bestand({})

    for waechter, funktion in sorted(WÆCHTER.items()):
        try:
            befunde = funktion(leer)
        except ValueError:
            continue
        assert befunde, f"{waechter} ist ueber einem leeren Bestand gruen."


def test_der_leser_scheitert_laut_bei_null_dateien(tmp_path: Path) -> None:
    """`git ls-files` in einem leeren Repository ist ein Befund ueber den Leser, kein leerer Bestand."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    with pytest.raises(ValueError, match="0 Dateien"):
        Bestand.aus_arbeitsbaum(tmp_path)


def test_bom_und_crlf_aendern_keinen_befund() -> None:
    """Zeilenenden und ein BOM sind Form der Datei, nicht Inhalt des Bestands."""
    roh = {pfad: "\ufeff" + text.replace("\n", "\r\n") for pfad, text in BESTAND.items()}
    mutation = next(m for m in MUTATIONEN if m.name == "ziel-nicht-als-literal")

    assert [b.meldung for b in pruefe(Bestand(roh))] == [b.meldung for b in pruefe(BESTAND)]
    assert [
        b.meldung
        for b in pruefe(Bestand(roh).ersetze(mutation.alt, mutation.neu, datei=mutation.datei))
    ] == [
        b.meldung for b in pruefe(BESTAND.ersetze(mutation.alt, mutation.neu, datei=mutation.datei))
    ]
