"""Board-Schreibzugriffe: genau ein Feld, Wert aus der Optionsmenge, geschlossene Literale.

Seit ADR 0057 prueft kein Board-Werkzeug mehr einen Statuswert vor dem Schreiben. Ein Tippfehler
in `--value "In progress"` faellt sonst erst zur Laufzeit auf - mitten in einer laufenden Session.
Diese Aussage bleibt deshalb: sie traegt eine Haertungsregel, nicht die Schreibweise der
Befehlszeile. Projektnummer und Owner sind geschlossene Literale, unquotierte Werte werden
gelesen statt uebersprungen.
"""

from __future__ import annotations

import re

from waechter import Befund, Bestand, Invariante, befund

PROJEKT_NUMMER = "8"
PROJEKT_OWNER = "TheRealKoller"
SUCHRAUM = (".claude", "CLAUDE.md")

ERLAUBTE_WERTE: dict[str, frozenset[str]] = {
    "Status": frozenset({"Unrefined", "Ready", "In Progress", "Review", "Done", "<Wert>"}),
    "Priorität": frozenset({"Hoch", "Mittel", "Niedrig", "<Hoch|Mittel|Niedrig>"}),
}

INVARIANTEN = (
    Invariante(
        "board-werte",
        "Jeder Board-Schreibzugriff nennt genau ein Feld und einen Wert aus der Optionsmenge; "
        "Projektnummer und Owner sind geschlossene Literale.",
    ),
)
INVARIANTEN_IDS = frozenset(invariante.id for invariante in INVARIANTEN)

_AUFRUF = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?:`[^`\n]*`:[ \t]*)?[`$]?[ \t]*(?P<befehl>gh project item-[a-z]+[^\n]*)",
    re.MULTILINE,
)
_PROJEKT = re.compile(r"gh project item-[a-z]+\s+(\S+)")
_OWNER = re.compile(r"--owner[ =](\S+)")
_FELD = re.compile(r"""--field\s+(?:"([^"]*)"|'([^']*)'|([^\s"'`]+))""")
_WERT = re.compile(r"""--value\s+(?:"([^"]*)"|'([^']*)'|([^\s"'`]+))""")


def _erste(treffer: re.Match[str]) -> str:
    return next(gruppe for gruppe in treffer.groups() if gruppe is not None)


def _befunde(datei: str, zeile: int, befehl: str) -> list[Befund]:
    befunde: list[Befund] = []
    projekt = _PROJEKT.search(befehl)
    if projekt is None or projekt.group(1) != PROJEKT_NUMMER:
        befunde.append(
            befund(
                datei,
                zeile,
                "board-werte",
                f"Projektnummer {projekt.group(1) if projekt else None!r} statt "
                f"{PROJEKT_NUMMER!r}.",
            )
        )
    owner = _OWNER.search(befehl)
    if owner is None or owner.group(1) != PROJEKT_OWNER:
        befunde.append(
            befund(
                datei,
                zeile,
                "board-werte",
                f"Owner {owner.group(1) if owner else None!r} statt {PROJEKT_OWNER!r}.",
            )
        )
    if "item-add" in befehl:
        return befunde  # die Aufnahme schreibt kein Feld
    felder = [_erste(treffer) for treffer in _FELD.finditer(befehl)]
    werte = [_erste(treffer) for treffer in _WERT.finditer(befehl)]
    if len(felder) != 1 or len(werte) != 1:
        befunde.append(
            befund(
                datei,
                zeile,
                "board-werte",
                f"{len(felder)} Feld(er) und {len(werte)} Wert(e) - erwartet genau eins je.",
            )
        )
        return befunde
    feld, wert = felder[0], werte[0]
    if feld not in ERLAUBTE_WERTE:
        befunde.append(
            befund(
                datei,
                zeile,
                "board-werte",
                f"Feld {feld!r} ist keines der Board-Felder {sorted(ERLAUBTE_WERTE)}.",
            )
        )
    elif wert not in ERLAUBTE_WERTE[feld]:
        befunde.append(
            befund(
                datei,
                zeile,
                "board-werte",
                f"Wert {wert!r} ist keine Option des Felds {feld!r} "
                f"({sorted(ERLAUBTE_WERTE[feld])}).",
            )
        )
    return befunde


def aufrufe(datei: str, text: str) -> list[tuple[int, str]]:
    return [
        (text.count("\n", 0, treffer.start()) + 1, treffer.group("befehl").strip())
        for treffer in _AUFRUF.finditer(text)
    ]


def pruefe(bestand: Bestand) -> list[Befund]:
    """Alle Board-Schreibzugriffe im Suchraum gegen die Optionsmengen."""
    befunde: list[Befund] = []
    anzahl = 0
    for datei in sorted(bestand):
        if not any(datei == ort or datei.startswith(f"{ort}/") for ort in SUCHRAUM):
            continue
        for zeile, befehl in aufrufe(datei, bestand[datei]):
            anzahl += 1
            befunde.extend(_befunde(datei, zeile, befehl))
    if anzahl == 0:
        befunde.append(
            Befund(
                ort="Bestand",
                invariante="board-werte",
                text="kein Board-Schreibzugriff im Suchraum - die Wertpruefung waere leer wahr.",
            )
        )
    return befunde


def test_der_bestand_nennt_nur_gueltige_felder_und_werte() -> None:
    """Der lebende Bestand haelt `board-werte`; Verletzungen belegt `mutationen.py`."""
    befunde = pruefe(Bestand.aus_arbeitsbaum())

    assert not befunde, "Board-Befunde: " + "; ".join(f.meldung for f in befunde)
