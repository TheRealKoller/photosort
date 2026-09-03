"""Bindet den in docs/setup.md dokumentierten Setup-Script-Block an MIN_GH_VERSION.

Die Zielversion der `gh`-Installation existiert zwangslaeufig an zwei Orten: als `MIN_GH_VERSION`
in scripts/gh-board.py (autoritativ) und als `GH_VERSION` im Setup-Script der Cloud-Umgebung, das
ausserhalb des Repositories in einer Weboberflaeche gepflegt wird. Die dokumentierte Fassung
dieses Scripts liegt in docs/setup.md - dieser Test haelt sie an der Konstante fest, damit eine
Anhebung von MIN_GH_VERSION ohne Nachziehen des Blocks sofort rot wird statt still zu veralten.

**Was diese Tests ausdruecklich NICHT zusichern:** dass der gepruefte Block je in die
Weboberflaeche der Cloud-Umgebung uebertragen wurde, und erst recht nicht, dass in irgendeiner
Umgebung tatsaechlich ein `gh` liegt. Eine gruene CI ist hier keine Aussage ueber eine
Remote-Session - dieser letzte Uebergang bleibt Handarbeit und ist in docs/setup.md als
Pflichtschritt benannt. Kein echtes `gh`, kein Netzwerk, keine Installation.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import ModuleType

import pytest

SETUP_DOKU_PFAD = Path(__file__).parents[2] / "docs" / "setup.md"

# Zeilenanfangs-Anker (re.MULTILINE): nur eine echte Zuweisung zaehlt, keine Erwaehnung von
# GH_VERSION im Fliesstext ringsum (den es zwangslaeufig gibt, weil der Block erklaert wird) und
# keine auskommentierte Zeile. Toleriert werden die gleichwertigen Schreibweisen ("...", '...',
# ohne Anfuehrungszeichen) sowie nachlaufender Leerraum/Kommentar - an einer
# Anfuehrungszeichen-Variante darf keine CI scheitern. Erzwungen bleibt das dreiteilige
# Versionsformat: GH_VERSION="2.72" ergibt null Treffer und damit einen lauten Fehlschlag statt
# eines stillen Ungleich-Vergleichs.
_GH_VERSION_ZUWEISUNG = re.compile(
    r"""^GH_VERSION=(?P<q>["']?)(?P<version>\d+\.\d+\.\d+)(?P=q)""", re.MULTILINE
)


def gh_version_aus_text(text: str) -> str:
    """Liest genau eine GH_VERSION-Zuweisung; null und mehrere Treffer sind Fehlerfaelle."""
    treffer = [t.group("version") for t in _GH_VERSION_ZUWEISUNG.finditer(text)]

    if not treffer:
        raise ValueError(
            "0 Treffer: keine Zeile beginnt mit GH_VERSION=<x.y.z>. Entweder fehlt der "
            "dokumentierte Setup-Script-Block, oder die Variable/das Versionsformat hat sich "
            "geaendert - dann ist dieser Test mitzuziehen, sonst ist die Bindung an "
            "MIN_GH_VERSION lautlos weg."
        )
    if len(treffer) > 1:
        raise ValueError(
            f"{len(treffer)} Treffer ({', '.join(treffer)}): GH_VERSION wird mehrfach "
            "zugewiesen. Es darf genau einen Setup-Script-Block geben - bei mehreren ist nicht "
            "mehr entscheidbar, welcher in die Weboberflaeche der Cloud-Umgebung gehoert."
        )
    return treffer[0]


def gh_version_aus_doku(pfad: Path = SETUP_DOKU_PFAD) -> str:
    """Duenner Leser fuer die echte Datei - Umlaute/Gedankenstriche, daher utf-8 ausdruecklich."""
    try:
        return gh_version_aus_text(pfad.read_text(encoding="utf-8"))
    except ValueError as fehler:
        raise ValueError(f"{pfad}: {fehler}") from fehler


# Fuer die Zeichenvorrats-Pruefung wird der Block ausgeschnitten statt die Datei gescannt:
# docs/setup.md ist deutsche Prosa und fuehrt reichlich Nicht-ASCII (Umlaute, Gedankenstriche).
# Geprueft wird ausschliesslich die Kopiervorlage, die von Hand in ein Webformular wandert und
# dort als Root laeuft. Der Filter auf "GH_VERSION=" trennt sie von den uebrigen Codebloecken
# der Datei; eine allgemeine Block-Erkennung entsteht dadurch ausdruecklich nicht.
_BASH_BLOCK = re.compile(r"```bash\n(.*?)```", re.DOTALL)

# Zeilenumbruch und Tabulator sind der einzige erlaubte Steuerzeichen-Vorrat eines Shell-Blocks.
_ERLAUBTER_LEERRAUM = ("\n", "\t")


def setup_script_block_aus_text(text: str) -> str:
    """Schneidet den einen ```bash-Block aus, der GH_VERSION zuweist."""
    treffer = [block for block in _BASH_BLOCK.findall(text) if "GH_VERSION=" in block]

    if not treffer:
        raise ValueError(
            "0 Treffer: kein ```bash-Block enthaelt eine GH_VERSION-Zuweisung. Damit ist der "
            "Zeichenvorrat der Kopiervorlage ungeprueft - entweder fehlt der Block, oder die "
            "Fence-/Sprachauszeichnung hat sich geaendert."
        )
    if len(treffer) > 1:
        raise ValueError(
            f"{len(treffer)} Treffer: mehrere ```bash-Bloecke weisen GH_VERSION zu. Es darf "
            "genau eine Kopiervorlage geben - bei mehreren ist nicht mehr entscheidbar, welche "
            "in die Weboberflaeche der Cloud-Umgebung gehoert."
        )
    return treffer[0]


def setup_script_block_aus_doku(pfad: Path = SETUP_DOKU_PFAD) -> str:
    try:
        return setup_script_block_aus_text(pfad.read_text(encoding="utf-8"))
    except ValueError as fehler:
        raise ValueError(f"{pfad}: {fehler}") from fehler


def nicht_ascii_verstoesse(block: str) -> list[str]:
    """Meldet je Verstoss Position, Zeile, Zeichen und Codepoint.

    Eine rote Zeile ohne Codepoint ist bei unsichtbaren Zeichen wertlos - man sieht im
    Fehlerbericht sonst genau das, was man auch in der Datei nicht sieht.
    """
    verstoesse = []
    for position, zeichen in enumerate(block):
        if zeichen in _ERLAUBTER_LEERRAUM or 0x20 <= ord(zeichen) <= 0x7E:
            continue
        zeile = block.count("\n", 0, position) + 1
        verstoesse.append(f"Position {position} (Zeile {zeile}): {zeichen!r} U+{ord(zeichen):04X}")
    return verstoesse


def test_die_dokumentierte_gh_version_entspricht_min_gh_version(gh_board: ModuleType) -> None:
    dokumentiert = gh_version_aus_doku()

    assert dokumentiert == gh_board.MIN_GH_VERSION, (
        f"Der Setup-Script-Block in {SETUP_DOKU_PFAD} installiert gh {dokumentiert}, "
        f"MIN_GH_VERSION in scripts/gh-board.py verlangt aber {gh_board.MIN_GH_VERSION}. "
        "Massgeblich ist die Konstante: den Block in docs/setup.md nachziehen und den neuen "
        "Wortlaut zusaetzlich in das Setup-Script der Cloud-Umgebung uebertragen."
    )


def test_ein_verschwundener_block_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        gh_version_aus_text("Hier steht Prosa, aber kein Setup-Script-Block.\n")


def test_ein_zweiter_block_scheitert_und_die_meldung_nennt_beide_werte() -> None:
    with pytest.raises(ValueError, match=r"2 Treffer \(2\.72\.0, 2\.80\.0\)"):
        gh_version_aus_text('GH_VERSION="2.72.0"\nirgendwas\nGH_VERSION="2.80.0"\n')


def test_die_meldung_nennt_die_gelesene_datei(tmp_path: Path) -> None:
    leere_doku = tmp_path / "setup.md"
    leere_doku.write_text("kein Block\n", encoding="utf-8")

    with pytest.raises(ValueError, match=re.escape(str(leere_doku))):
        gh_version_aus_doku(leere_doku)


def test_eine_erwaehnung_im_fliesstext_gilt_nicht_als_zuweisung() -> None:
    """Ohne Zeilenanfangs-Anker wuerde jede Prosa-Erwaehnung als zweiter Treffer zaehlen."""
    text = 'Der Block setzt GH_VERSION="9.9.9" - passend zu MIN_GH_VERSION.\nGH_VERSION="2.72.0"\n'

    assert gh_version_aus_text(text) == "2.72.0"


def test_eine_auskommentierte_zuweisung_zaehlt_nicht_mit() -> None:
    text = '# GH_VERSION="9.9.9"  (alt)\nGH_VERSION="2.72.0"\n'

    assert gh_version_aus_text(text) == "2.72.0"


@pytest.mark.parametrize(
    "zeile",
    [
        'GH_VERSION="2.72.0"',
        "GH_VERSION='2.72.0'",
        "GH_VERSION=2.72.0",
        'GH_VERSION="2.72.0"   # Zielversion',
    ],
)
def test_gleichwertige_schreibweisen_werden_toleriert(zeile: str) -> None:
    assert gh_version_aus_text(f"set -euo pipefail\n{zeile}\n") == "2.72.0"


@pytest.mark.parametrize("zeile", ['GH_VERSION="2.72"', 'GH_VERSION="latest"', "GH_VERSION="])
def test_ein_unvollstaendiges_versionsformat_ist_ein_lauter_fehlschlag(zeile: str) -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        gh_version_aus_text(f"{zeile}\n")


def test_der_dokumentierte_block_enthaelt_ausschliesslich_druckbares_ascii() -> None:
    """Der Block ist ein Kopiervorlagen-Angriffsziel: gerendert gelesen, als Root ausgefuehrt."""
    verstoesse = nicht_ascii_verstoesse(setup_script_block_aus_doku())

    assert not verstoesse, (
        f"Der Setup-Script-Block in {SETUP_DOKU_PFAD} enthaelt Zeichen ausserhalb des "
        f"druckbaren ASCII: {'; '.join(verstoesse)}. Unsichtbare Steuer-, Bidi- oder "
        "Nullbreiten-Zeichen ueberstehen Kopieren und Einfuegen und koennen im gerenderten "
        "Text verborgene Anweisungen tragen - der Block wird von Hand in ein Webformular "
        "uebertragen und laeuft dort als Root."
    )


def test_der_ausgeschnittene_block_ist_der_setup_script_block() -> None:
    """docs/setup.md fuehrt mehrere ```bash-Bloecke - geprueft wird genau dieser eine."""
    block = setup_script_block_aus_doku()

    assert block.startswith("set -euo pipefail\n")
    assert "install -m 0755" in block


@pytest.mark.parametrize(
    ("zeichen", "codepoint"),
    [
        ("\u200b", "U+200B"),  # Zero-Width Space
        ("\u202e", "U+202E"),  # Right-to-Left Override
        ("\u00a0", "U+00A0"),  # Non-Breaking Space
        ("\x1b", "U+001B"),  # ESC, Beginn jeder ANSI-Sequenz
        ("\u2014", "U+2014"),  # Gedankenstrich, harmlos gemeint und trotzdem ein Verstoss
    ],
)
def test_ein_unsichtbares_zeichen_wird_mit_position_und_codepoint_gemeldet(
    zeichen: str, codepoint: str
) -> None:
    verstoesse = nicht_ascii_verstoesse(f'GH_VERSION="2.72.0"{zeichen}\ngh --version\n')

    assert len(verstoesse) == 1
    assert codepoint in verstoesse[0]
    assert "Position 19" in verstoesse[0]
    assert "Zeile 1" in verstoesse[0]


def test_zeilenumbruch_und_tabulator_gelten_nicht_als_verstoss() -> None:
    assert nicht_ascii_verstoesse("set -euo pipefail\n\tgh --version\n") == []


def test_ein_fehlender_bash_block_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        setup_script_block_aus_text("Nur Prosa, kein Codeblock.\n")


def test_ein_bash_block_ohne_gh_version_zaehlt_nicht_als_kopiervorlage() -> None:
    with pytest.raises(ValueError, match=r"0 Treffer"):
        setup_script_block_aus_text("```bash\ndocker compose up --build\n```\n")


def test_ein_zweiter_kopiervorlagen_block_scheitert_laut() -> None:
    text = '```bash\nGH_VERSION="2.72.0"\n```\ntext\n```bash\nGH_VERSION="2.80.0"\n```\n'

    with pytest.raises(ValueError, match=r"2 Treffer"):
        setup_script_block_aus_text(text)


def test_die_meldung_der_block_extraktion_nennt_die_gelesene_datei(tmp_path: Path) -> None:
    leere_doku = tmp_path / "setup.md"
    leere_doku.write_text("kein Block\n", encoding="utf-8")

    with pytest.raises(ValueError, match=re.escape(str(leere_doku))):
        setup_script_block_aus_doku(leere_doku)
