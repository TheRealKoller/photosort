"""Die drei Kategorie-Specs und die drei Kategorie-ADRs tragen den Status `Superseded`.

„Die bisherigen Festlegungen sind ausdrücklich abgelöst und nicht stillschweigend umgangen" ist
ein Akzeptanzkriterium von [`specs/features/0427-motive-mit-staerke.md`](../../specs/features/0427-motive-mit-staerke.md).
Ohne diesen Test ist es eine Behauptung im Pull-Request-Text: der Code kann vollständig abgelöst
sein, während die Specs weiter `Implemented` melden - und der nächste Leser findet dort eine
Festlegung, die das Produkt nicht mehr trägt, ohne jeden Hinweis darauf.

**Gemessen wird die Statuszeile UND der Verweis.** Ein `Superseded` ohne Nachfolgenummer schickt
den Leser auf eine Suche, die er nicht abschließen kann; eine Nachfolgenummer ohne `Superseded`
liest sich wie ein Querverweis unter Gleichen. Beide Hälften stehen deshalb in einem Fall je
Dokument - getrennt bestünde jede auch dann, wenn die andere fehlte.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import REPO_WURZEL

# Die drei Feature-Specs, deren Festlegungen mit Spec 0427 vollständig entfallen: das feste
# Kategorien-Set samt Vorrangreihenfolge, die angezeigte Kategoriekonfidenz und die
# Nebenkategorien.
_ABGELOESTE_SPECS = (
    "specs/features/0289-feste-kategorien.md",
    "specs/features/0299-kategorie-konfidenz-anzeigen.md",
    "specs/features/0300-nebenkategorien.md",
)

# Die drei zugehörigen ADRs. Sie tragen ihren `Superseded`-Vermerk bereits seit ADR 0091 und
# stehen hier, damit ein späteres redaktionelles Aufräumen sie nicht still zurückstuft.
_ABGELOESTE_ADRS = (
    "specs/decisions/0049-festes-kategorien-set-mit-vorrangreihenfolge-und-freien-feinlabels.md",
    "specs/decisions/0067-modellkonfidenz-je-kategorie-anzeige-und-auswertung.md",
    "specs/decisions/0069-nebenkategorien-mehrfachzugehoerigkeit-und-konfidenzgewichtete-rangfolge.md",
)


def _statuszeile(relativer_pfad: str) -> str:
    pfad = REPO_WURZEL / relativer_pfad
    assert pfad.exists(), relativer_pfad
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        if zeile.startswith("**Status:**"):
            return zeile
    raise AssertionError(f"keine Statuszeile in {relativer_pfad}")


@pytest.mark.parametrize("relativer_pfad", _ABGELOESTE_SPECS)
def test_die_abgeloeste_spec_ist_superseded_und_nennt_0427(relativer_pfad: str) -> None:
    zeile = _statuszeile(relativer_pfad)

    assert "Superseded" in zeile, zeile
    assert "0427" in zeile, zeile


@pytest.mark.parametrize("relativer_pfad", _ABGELOESTE_ADRS)
def test_die_abgeloeste_adr_ist_superseded_und_nennt_0091(relativer_pfad: str) -> None:
    """Die ADRs verweisen auf ADR 0091 (die Architekturentscheidung), nicht auf die Spec - so
    zeigt die Kette Entscheidung→Entscheidung und Story→Story."""
    zeile = _statuszeile(relativer_pfad)

    assert "Superseded" in zeile, zeile
    assert "0091" in zeile, zeile


def test_die_ablosende_spec_selbst_ist_nicht_superseded() -> None:
    """Wirksamkeitsbeleg der Suche: fände `_statuszeile` die Zeile nicht oder immer dieselbe,
    wären die Fälle oben aus dem falschen Grund grün."""
    zeile = _statuszeile("specs/features/0427-motive-mit-staerke.md")

    assert "Superseded" not in zeile, zeile
