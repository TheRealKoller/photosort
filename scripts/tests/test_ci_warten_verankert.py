"""Der CI-Wartepunkt: blockierend, endlich, ohne Filter, ohne Pipe - Zahlen tragen nichts.

`timeout 540` ist eine Betriebszahl und darf sich aendern; `--watch`, ein endliches `timeout`,
das Fehlen von `--required` und der Verzicht auf eine Pipe tragen die Aussage. Gelesen wird der
Befehl selbst, nicht sein Satz daneben: Ein umformulierter Abschnitt bleibt gruen, ein
entfernter Wartepunkt wird rot.
"""

from __future__ import annotations

import re

from waechter import Befund, Bestand, Invariante, befund, codebloecke

KATALOG = ".claude/skills/github-access/SKILL.md"
WARTEN = "pr-pruefstand-abwarten"
LESEN = "pr-pruefstand-lesen"
FELDAUSWAHL = "bucket,name,state,workflow"
ENTWICKLER = ".claude/agents/developer.md"
ANKER = (
    "## Abschlussbericht (Folgeauftrag: CI-Fehlschlag behoben)",
    "## Blockiert: CI-Fehlschlag außerhalb der zulässigen Klasse",
)

INVARIANTEN = (
    Invariante(
        "pruefstand-blockierend",
        "Der Wartepunkt wartet blockierend (`--watch`), ist endlich begrenzt, filtert nicht auf "
        "erforderliche Checks, laeuft nicht durch eine Pipe und liest die Feldauswahl als ganzen "
        "Optionswert.",
    ),
    Invariante(
        "anker-protokoll",
        "Beide CI-Anker sind als Ueberschrift genau einmal definiert - ein Ablauf liest sie.",
    ),
)
INVARIANTEN_IDS = frozenset(invariante.id for invariante in INVARIANTEN)

_ENDLICH = re.compile(r"^timeout\s+\d+\s+\S")
_JSON = re.compile(r"--json\s+(?P<wert>\S+)")


def _zeile(text: str, ausschnitt: str) -> int:
    """Zeile des Ausschnitts, sonst 1 - der Befund soll auf die Stelle zeigen, nicht ins Leere."""
    position = text.find(ausschnitt) if ausschnitt else -1
    return 1 if position < 0 else text.count("\n", 0, position) + 1


def _abschnitt(text: str, kennung: str) -> str:
    """Der Katalogabschnitt `### \\`<kennung>\\`` bis zur naechsten Ueberschrift derselben Ebene."""
    beginn = text.find(f"### `{kennung}`")
    if beginn == -1:
        return ""
    rest = text[beginn:]
    ende = rest.find("\n### ", 1)
    return rest if ende == -1 else rest[:ende]


def _befehle(abschnitt: str) -> list[str]:
    return [
        zeile.strip()
        for block in codebloecke(abschnitt)
        for zeile in block.split("\n")
        if "gh pr checks" in zeile
    ]


def _warten(bestand: Bestand) -> list[Befund]:
    if KATALOG not in bestand:
        return [
            Befund(
                ort="Bestand",
                invariante="pruefstand-blockierend",
                text=f"{KATALOG} fehlt - der Wartepunkt waere nicht pruefbar.",
            )
        ]
    text = bestand[KATALOG]
    befunde: list[Befund] = []
    block = _abschnitt(text, WARTEN)
    zeilen = [zeile for zeile in _befehle(block) if "--watch" in zeile]
    if len(zeilen) != 1:
        return [
            befund(
                KATALOG,
                _zeile(text, block),
                "pruefstand-blockierend",
                f"{len(zeilen)} blockierende Wartebefehle in `{WARTEN}` - erwartet genau einer.",
            )
        ]
    wartezeile = zeilen[0]
    ort = _zeile(text, wartezeile)
    if not _ENDLICH.match(wartezeile):
        befunde.append(
            befund(
                KATALOG,
                ort,
                "pruefstand-blockierend",
                f"kein endliches `timeout` vor dem Wartebefehl: {wartezeile!r}.",
            )
        )
    if "--required" in wartezeile:
        befunde.append(
            befund(
                KATALOG,
                ort,
                "pruefstand-blockierend",
                "`--required` filtert auf erforderliche Checks, solange keine eingetragen sind.",
            )
        )
    if "|" in wartezeile:
        befunde.append(
            befund(
                KATALOG,
                ort,
                "pruefstand-blockierend",
                f"der Wartebefehl laeuft durch eine Pipe: {wartezeile!r}.",
            )
        )

    lesezeilen = _befehle(_abschnitt(text, LESEN))
    if len(lesezeilen) != 1:
        befunde.append(
            befund(
                KATALOG,
                _zeile(text, f"### `{LESEN}`"),
                "pruefstand-blockierend",
                f"{len(lesezeilen)} lesende Befehle in `{LESEN}` - erwartet genau einer.",
            )
        )
        return befunde
    leseort = _zeile(text, lesezeilen[0])
    treffer = _JSON.search(lesezeilen[0])
    wert = treffer.group("wert") if treffer else ""
    if wert != FELDAUSWAHL:
        befunde.append(
            befund(
                KATALOG,
                leseort,
                "pruefstand-blockierend",
                f"die Feldauswahl der Lesezeile ist {wert!r} statt {FELDAUSWAHL!r}.",
            )
        )
    if "|" in lesezeilen[0]:
        befunde.append(
            befund(
                KATALOG,
                leseort,
                "pruefstand-blockierend",
                f"der lesende Befehl laeuft durch eine Pipe: {lesezeilen[0]!r}.",
            )
        )
    return befunde


def _anker(bestand: Bestand) -> list[Befund]:
    if ENTWICKLER not in bestand:
        return [
            Befund(
                ort="Bestand",
                invariante="anker-protokoll",
                text=f"{ENTWICKLER} fehlt - die Anker waeren nicht pruefbar.",
            )
        ]
    text = bestand[ENTWICKLER]
    zeilen = [zeile.strip() for zeile in text.split("\n")]
    befunde: list[Befund] = []
    for anker in ANKER:
        if zeilen.count(anker) == 1:
            continue
        kern = re.split(r" \(| außerhalb", anker)[0]
        befunde.append(
            befund(
                ENTWICKLER,
                _zeile(text, kern),
                "anker-protokoll",
                f"Anker {anker!r} ist {zeilen.count(anker)}-mal als Ueberschrift definiert - "
                "erwartet genau einmal.",
            )
        )
    return befunde


def pruefe(bestand: Bestand) -> list[Befund]:
    """`pruefstand-blockierend` und `anker-protokoll` ueber einem Bestand."""
    return _warten(bestand) + _anker(bestand)


def test_der_bestand_wartet_blockierend_und_endlich() -> None:
    """Der lebende Bestand haelt beide Invarianten; Verletzungen belegt `mutationen.py`."""
    befunde = pruefe(Bestand.aus_arbeitsbaum())

    assert not befunde, "Wartepunkt-Befunde: " + "; ".join(f.meldung for f in befunde)
