"""Haelt fest, dass geloeschte bzw. umbenannte Namen in keiner verwalteten Datei mehr vorkommen.

Zwei Faelle derselben Bauart:

* Seit ADR 0057 gibt es kein eigenes Board-Werkzeug mehr (`gh-board`). Eine zurueckgebliebene
  Erwaehnung waere keine Kleinigkeit, sondern eine Anweisung an einen Agenten, ein Programm
  aufzurufen, das es nicht mehr gibt.
* Seit ADR 0059 heisst der Skill `github-access` statt `github-board`. Ein zurueckgebliebener
  Verweis zeigte auf ein Verzeichnis, das es nicht mehr gibt - und der Skill ist ab jetzt die
  *einzige* Stelle mit einem GitHub-Zugriff, ein toter Verweis darauf trifft also jeden Ablauf.

Die beiden Muster kollidieren nicht: `github-board` enthaelt `gh-board` **nicht** als Teilstring
(zwischen "gh" und "-board" steht "ub"), und umgekehrt ebenso wenig. Es gibt daher keine
Fundstelle, die faelschlich der jeweils anderen Regel zugeschlagen wuerde.

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

# Beide Schreibweisen des Werkzeugs ("gh-board" aus dem Dateinamen, "gh_board" aus
# Fixture-/Modulnamen) plus der alte Skill-Name.
MUSTER = (b"gh-board", b"gh_board", b"github-board")

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

# Gegenprobe **je Musterfamilie**: Jede der beiden ADRs erwaehnt den von ihr abgeschafften Namen
# zwangslaeufig und liegt unter der Ausnahme `specs/`. Trifft ein Muster in seiner eigenen ADR
# nicht, ist die Nullmeldung oben kein Befund, sondern ein Defekt. Eine Gegenprobe, die nur
# `gh-board` belegt, sagt ueber `github-board` nichts.
GEGENPROBEN: dict[bytes, Path] = {
    b"gh-board": (
        REPO_WURZEL / "specs" / "decisions" / "0057-board-lebenszyklus-nativ-statt-eigenbau.md"
    ),
    b"github-board": (
        REPO_WURZEL
        / "specs"
        / "decisions"
        / "0059-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md"
    ),
}

# Das Suchmuster oben liest Datei-*Inhalte*. Ein wieder angelegtes Verzeichnis, dessen
# Dateien den alten Namen nirgends im Text nennen, entginge ihm deshalb vollstaendig - der
# Pfad selbst muss eigens geprueft werden.
GELOESCHTE_PFADE = (
    "scripts/gh-board.py",
    "scripts/tests/test_gh_board.py",
    ".claude/skills/github-board",
)


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


def test_keine_verwaltete_datei_erwaehnt_die_alten_namen_noch() -> None:
    abbild = abbild_des_repos()

    # Selbstschutz (a): plausible Groessenordnung statt eines leeren Suchraums.
    assert len(abbild) >= MINDESTZAHL_VERWALTETER_DATEIEN, (
        f"Nur {len(abbild)} verwaltete Dateien gefunden (erwartet: mindestens "
        f"{MINDESTZAHL_VERWALTETER_DATEIEN}). Die Aufzaehlung ist kaputt; ein Nullbefund dieses "
        "Tests waere dann bedeutungslos."
    )

    # Selbstschutz (b): Gegenprobe je Musterfamilie - jedes Muster trifft in seiner eigenen,
    # ausgenommenen ADR sehr wohl.
    for muster, pfad in GEGENPROBEN.items():
        assert muster in pfad.read_bytes(), (
            f"Das Suchmuster {muster!r} findet nicht einmal in {pfad} etwas. Dann ist die "
            "Nullmeldung dieses Tests fuer dieses Muster kein Befund, sondern ein Defekt."
        )

    befunde = fundstellen_im_abbild(abbild)

    assert not befunde, (
        f"Ein abgeschaffter Name ({MUSTER}) wird noch erwaehnt: {', '.join(befunde)}. "
        f"Ausgenommen sind ausschliesslich {AUSNAHMEN} - jede andere Fundstelle weist einen "
        "Ablauf auf ein Programm bzw. ein Verzeichnis, das es nicht mehr gibt."
    )


def test_die_verschwundenen_pfade_existieren_nicht_mehr() -> None:
    """Faengt eine Wiederkehr, die dem Textmuster entginge, weil sie nur im Pfad steht."""
    vorhanden = [pfad for pfad in GELOESCHTE_PFADE if (REPO_WURZEL / pfad).exists()]

    assert not vorhanden, (
        f"Diese Pfade sollten mit ADR 0057 bzw. ADR 0059 verschwunden sein, existieren aber "
        f"noch: {vorhanden}."
    )


def test_der_neue_skill_pfad_existiert() -> None:
    """Gegenprobe: Ohne ihn waere der Test oben leer wahr - alles verschwunden, nichts ersetzt."""
    assert (REPO_WURZEL / ".claude" / "skills" / "github-access" / "SKILL.md").is_file()


def test_alle_schreibweisen_werden_gefunden() -> None:
    abbild = {
        "docs/a.md": b"ruf python3 scripts/gh-board.py auf\n",
        "docs/c.md": b"siehe .claude/skills/github-board/SKILL.md\n",
        "scripts/tests/b.py": b"def test(gh_board):\n    pass\n",
    }

    assert fundstellen_im_abbild(abbild) == [
        "docs/a.md:1",
        "docs/c.md:1",
        "scripts/tests/b.py:1",
    ]


def test_der_neue_skill_name_gilt_nicht_als_fundstelle() -> None:
    """Regex-Falle derselben Klasse wie `--body`/`--body-file`: `github-access` ist der Zielname."""
    abbild = {"docs/a.md": b"siehe .claude/skills/github-access/SKILL.md\n"}

    assert fundstellen_im_abbild(abbild) == []


def test_die_beiden_muster_kollidieren_nicht() -> None:
    """`github-board` enthaelt `gh-board` nicht als Teilstring - zwischen beiden steht "ub"."""
    assert b"gh-board" not in b"github-board"
    assert b"github-board" not in b"gh-board"


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
