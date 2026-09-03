"""Bindet den in docs/setup.md dokumentierten Setup-Script-Block an MIN_GH_VERSION.

Die Zielversion der gh-Installation existiert zwangsläufig an zwei Orten: als
`MIN_GH_VERSION` in scripts/gh-board.py (autoritativ) und als `GH_VERSION` im Setup-Script,
das ausserhalb des Repositories in der Weboberfläche der Cloud-Umgebung gepflegt wird. Die
dokumentierte Fassung dieses Scripts liegt in docs/setup.md - dieser Test haelt sie an der
Konstante fest, damit eine Anhebung von MIN_GH_VERSION ohne Nachziehen des Blocks sofort rot
wird statt still zu veralten.

Kein echtes `gh`, kein Netzwerk, kein Zugriff auf die Weboberfläche. Der letzte Uebergang -
dokumentierter Block in die Weboberfläche - bleibt ungesichert und ist in docs/setup.md als
Pflichtschritt benannt.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import ModuleType

SETUP_DOKU_PFAD = Path(__file__).parents[2] / "docs" / "setup.md"

# Zeilenanfangs-Anker: nur eine echte Zuweisung im Skript-Block zaehlt, keine Erwaehnung von
# GH_VERSION im Fliesstext ringsum (die es zwangsläufig gibt, weil der Block erklaert wird).
_GH_VERSION_ZUWEISUNG = re.compile(r'^GH_VERSION="([^"]+)"', re.MULTILINE)


def _gh_versionen(text: str) -> list[str]:
    return _GH_VERSION_ZUWEISUNG.findall(text)


def test_der_setup_block_weist_gh_version_genau_einmal_zu() -> None:
    """Kein Treffer und mehrere Treffer sind beide Fehlerfaelle - mit eigener Meldung."""
    treffer = _gh_versionen(SETUP_DOKU_PFAD.read_text(encoding="utf-8"))

    assert treffer, (
        'In docs/setup.md steht keine Zeile, die mit GH_VERSION="..." beginnt. Entweder '
        "fehlt der dokumentierte Setup-Script-Block, oder die Variable wurde umbenannt - "
        "dann ist dieser Test mitzuziehen, sonst ist die Bindung an MIN_GH_VERSION lautlos weg."
    )
    assert len(treffer) == 1, (
        f"docs/setup.md weist GH_VERSION {len(treffer)}-mal zu ({treffer}). Es darf genau "
        "einen Setup-Script-Block geben - bei mehreren ist nicht mehr entscheidbar, welcher "
        "in die Weboberfläche der Cloud-Umgebung gehoert."
    )


def test_die_dokumentierte_gh_version_entspricht_min_gh_version(gh_board: ModuleType) -> None:
    (dokumentiert,) = _gh_versionen(SETUP_DOKU_PFAD.read_text(encoding="utf-8"))

    assert dokumentiert == gh_board.MIN_GH_VERSION, (
        f"Der Setup-Script-Block in docs/setup.md installiert gh {dokumentiert}, "
        f"MIN_GH_VERSION in scripts/gh-board.py verlangt aber {gh_board.MIN_GH_VERSION}. "
        "Maßgeblich ist die Konstante: den Block in docs/setup.md nachziehen und den neuen "
        "Wortlaut zusaetzlich in das Setup-Script der Cloud-Umgebung uebertragen."
    )


def test_eine_erwaehnung_im_fliesstext_gilt_nicht_als_zuweisung() -> None:
    """Ohne Zeilenanfangs-Anker wuerde jede Prosa-Erwaehnung als zweiter Treffer zaehlen."""
    text = 'Der Block setzt GH_VERSION="9.9.9", passend zu MIN_GH_VERSION.\nGH_VERSION="2.72.0"\n'

    assert _gh_versionen(text) == ["2.72.0"]


def test_ein_zweiter_block_wird_als_zweiter_treffer_erkannt() -> None:
    text = 'GH_VERSION="2.72.0"\nirgendwas\nGH_VERSION="2.80.0"\n'

    assert _gh_versionen(text) == ["2.72.0", "2.80.0"]
