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
