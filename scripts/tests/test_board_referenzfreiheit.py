"""Haelt fest, dass das geloeschte Board-Werkzeug in keiner verwalteten Datei mehr vorkommt.

Seit ADR 0057 gibt es kein eigenes Board-Werkzeug mehr: Der Board-Zugriff sind einzelne
`gh`-Befehle in den Skill-Dateien. Eine zurueckgebliebene Erwaehnung waere keine Kleinigkeit,
sondern eine Anweisung an einen Agenten, ein Programm aufzurufen, das es nicht mehr gibt.

Der Suchraum ist deshalb **alles, was Git verwaltet** (`git ls-files`) und nicht eine gepflegte
Liste von Verzeichnissen: Ein spaeter umbenannter oder neu angelegter Skill fiele aus einer
festen Liste heraus, und Fundstellen wie `scripts/tests/conftest.py` oder der Kommentar am
`demo-scripts`-Job in `.github/workflows/ci.yml` laegen von vornherein ausserhalb.

Gesucht wird byteweise nach beiden Schreibweisen: der Bindestrich-Form aus dem Dateinamen und
der Unterstrich-Form, die in Python-Bezeichnern zurueckbleibt. Byteweise deshalb, weil der
Suchraum Binaerdateien enthaelt (`scripts/demo_photos/`), an denen ein Textdekoder scheitern
wuerde.

Kein echtes `gh`, kein Netzwerk - gelesen werden ausschliesslich Dateien dieses Repositories.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

# Beide Schreibweisen: "gh-board" aus dem Dateinamen, "gh_board" aus Fixture-/Modulnamen.
MUSTER = (b"gh-board", b"gh_board")

# Genau drei Ausnahmen, per Pfadpraefix und je begruendet:
#   CHANGELOG.md - von release-please aus historischen Commit-Botschaften erzeugt, nicht von
#                  Hand pflegbar.
#   specs/       - ADRs und Feature-Specs beschreiben korrekt, was zu ihrer Zeit galt; ihre
#                  Erwaehnungen sind historisch richtig und bleiben stehen.
#   diese Datei  - sie fuehrt das Suchmuster selbst.
AUSNAHMEN = (
    "CHANGELOG.md",
    "specs/",
    "scripts/tests/test_board_referenzfreiheit.py",
)

# Selbstschutz: Eine kaputte Dateiaufzaehlung (falsches Arbeitsverzeichnis, leere Ausgabe)
# liesse den Test gruen werden, obwohl er nichts gesehen hat. Die Untergrenze ist bewusst weit
# unter dem Ist-Stand des Repositories gewaehlt - sie soll den Totalausfall fangen, nicht bei
# jedem geloeschten Dutzend Dateien rot werden.
MINDESTZAHL_VERWALTETER_DATEIEN = 100

# Gegenprobe fuer dasselbe Muster: Diese ADR erwaehnt das Werkzeug zwangslaeufig und liegt
# unter der Ausnahme `specs/`. Trifft das Muster hier nicht, ist die Nullmeldung oben kein
# Befund, sondern ein Defekt.
GEGENPROBE_PFAD = REPO_WURZEL / "specs" / "decisions" / "0057-board-lebenszyklus-nativ-statt-eigenbau.md"

GELOESCHTE_PFADE = ("scripts/gh-board.py", "scripts/tests/test_gh_board.py")


def fundstellen_im_abbild(abbild: Mapping[str, bytes]) -> list[str]:
    """Reine Funktion auf einem Pfad->Bytes-Abbild; meldet je Fund Pfad und Zeilennummer.

    Ein Fund ohne Fundstelle zwingt zum Nachsuchen, deshalb wird die Zeilennummer mitgefuehrt.
    Eine leere Aufzaehlung ist ein Fehlerfall mit eigener Meldung, kein stiller Nullbefund.
    """
    if not abbild:
        raise ValueError(
            "0 Dateien im Suchraum: Damit ist die Referenz-Freiheit ungeprueft. Entweder lief "
            "die Dateiaufzaehlung im falschen Arbeitsverzeichnis, oder sie ist kaputt - ein "
            "leerer Suchraum darf nie als 'nichts gefunden' durchgehen."
        )

    befunde: list[str] = []
    for pfad in sorted(abbild):
        if pfad.startswith(AUSNAHMEN):
            continue
        for nummer, zeile in enumerate(abbild[pfad].split(b"\n"), start=1):
            if any(muster in zeile for muster in MUSTER):
                befunde.append(f"{pfad}:{nummer}")
    return befunde


def verwaltete_dateien(wurzel: Path = REPO_WURZEL) -> list[str]:
    """Duenner Leser: die von Git verwalteten Pfade, nullbyte-getrennt (Leerzeichen im Namen)."""
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    return [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]


def abbild_des_repos(wurzel: Path = REPO_WURZEL) -> dict[str, bytes]:
    """Duenner Leser fuer den echten Repo-Zustand - byteweise, damit Binaerdateien nicht stoeren."""
    pfade = verwaltete_dateien(wurzel)
    return {pfad: (wurzel / pfad).read_bytes() for pfad in pfade if (wurzel / pfad).is_file()}


def test_keine_verwaltete_datei_erwaehnt_das_board_werkzeug_noch() -> None:
    abbild = abbild_des_repos()

    # Selbstschutz (a): plausible Groessenordnung statt eines leeren Suchraums.
    assert len(abbild) >= MINDESTZAHL_VERWALTETER_DATEIEN, (
        f"Nur {len(abbild)} verwaltete Dateien gefunden (erwartet: mindestens "
        f"{MINDESTZAHL_VERWALTETER_DATEIEN}). Die Aufzaehlung ist kaputt; ein Nullbefund dieses "
        "Tests waere dann bedeutungslos."
    )

    # Selbstschutz (b): Gegenprobe - dasselbe Muster trifft in der ausgenommenen ADR sehr wohl.
    assert fundstellen_im_abbild({"gegenprobe.md": GEGENPROBE_PFAD.read_bytes()}), (
        f"Das Suchmuster {MUSTER} findet nicht einmal in {GEGENPROBE_PFAD} etwas. Dann ist die "
        "Nullmeldung dieses Tests kein Befund, sondern ein defektes Muster."
    )

    befunde = fundstellen_im_abbild(abbild)

    assert not befunde, (
        "Das seit ADR 0057 geloeschte Board-Werkzeug wird noch erwaehnt: "
        f"{', '.join(befunde)}. Ausgenommen sind ausschliesslich {AUSNAHMEN} - jede andere "
        "Fundstelle weist einen Ablauf auf ein Programm, das es nicht mehr gibt."
    )


def test_das_werkzeug_und_seine_testdatei_existieren_nicht_mehr() -> None:
    """Faengt eine Wiederkehr, die dem Textmuster entginge, weil sie sich anders benennt."""
    vorhanden = [pfad for pfad in GELOESCHTE_PFADE if (REPO_WURZEL / pfad).exists()]

    assert not vorhanden, (
        f"Diese Pfade sollten mit ADR 0057 verschwunden sein, existieren aber noch: {vorhanden}."
    )


def test_beide_schreibweisen_werden_gefunden() -> None:
    abbild = {
        "docs/a.md": b"ruf python3 scripts/gh-board.py auf\n",
        "scripts/tests/b.py": b"def test(gh_board):\n    pass\n",
    }

    assert fundstellen_im_abbild(abbild) == ["docs/a.md:1", "scripts/tests/b.py:1"]


def test_die_meldung_nennt_pfad_und_zeilennummer() -> None:
    abbild = {"docs/a.md": b"Zeile eins\nZeile zwei\ngh-board.py\n"}

    assert fundstellen_im_abbild(abbild) == ["docs/a.md:3"]


@pytest.mark.parametrize(
    "pfad",
    [
        "CHANGELOG.md",
        "specs/decisions/0057-board-lebenszyklus-nativ-statt-eigenbau.md",
        "specs/features/0262-github-project-sync-tool-entfernen.md",
        "scripts/tests/test_board_referenzfreiheit.py",
    ],
)
def test_die_drei_ausnahmen_werden_uebergangen(pfad: str) -> None:
    assert fundstellen_im_abbild({pfad: b"gh-board.py und gh_board\n"}) == []


@pytest.mark.parametrize(
    "pfad",
    [
        "specifikationen/entwurf.md",  # beginnt zwar mit "spec", ist aber nicht specs/
        "docs/specs/uebersicht.md",  # specs/ nur als Teilpfad in der Mitte
        "scripts/tests/test_board_referenzfreiheit_kopie.py",
    ],
)
def test_ein_aehnlich_benannter_pfad_faellt_nicht_unter_die_ausnahmen(pfad: str) -> None:
    assert fundstellen_im_abbild({pfad: b"gh-board.py\n"}) == [f"{pfad}:1"]


def test_ein_leerer_suchraum_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Dateien"):
        fundstellen_im_abbild({})


def test_binaerdateien_stoeren_die_suche_nicht() -> None:
    """Byteweise statt textweise: an einer Bilddatei wuerde ein Dekoder abbrechen."""
    abbild = {"scripts/demo_photos/bild.jpg": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\xfe"}

    assert fundstellen_im_abbild(abbild) == []


def test_der_leser_findet_die_dateien_dieses_repositories() -> None:
    """Gegenprobe zum Leser selbst: er muss diese Testdatei sehen."""
    pfade = verwaltete_dateien()

    assert "scripts/tests/test_board_referenzfreiheit.py" in pfade
