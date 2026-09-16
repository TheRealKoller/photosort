#!/usr/bin/env python3
"""Erkennt den Block `## Blockiert: Produktentscheidung nötig` in einem Bericht und prueft ihn.

Aufruf an der **vorlegenden** Stelle, nachdem der Rueckgabewert eines Laufs als Datei
materialisiert wurde:

    scripts/produktentscheidung.py <berichtsdatei>

Ausgaenge, einzeln zu unterscheiden und nie als Sammelzweig:

* `0`  - Block gefunden und wohlgeformt. Auf stdout steht er als JSON-Objekt; **daraus** wird
         vorgelegt, nicht aus dem umgebenden Fliesstext.
* `1`  - kein Block im Bericht. Kein Fehler: Der Bericht wird behandelt wie jeder andere.
* `2`  - Block gefunden, aber Befund. Es wird **nichts** vorgelegt; die Befunde stehen auf stderr
         und gehoeren in den Bericht an Daniel.
* `30` - Vorbedingung (Datei fehlt, nicht lesbar, kein UTF-8). Nie wie `1` behandeln: "nicht
         gemessen" ist nicht "kein Block".

**Warum das mechanisch geschieht und nicht durch Hinsehen** (Spec 0454, S4): Eine
Optionsbeschriftung wird ueberflogen, nicht gelesen. Bidi-Overrides und Zero-Width-Zeichen sind
genau die Klasse Zeichen, die im Kontext eines Modells unsichtbar ist - ein U+202E dreht die
Anzeige einer Option um, und der Klick trifft etwas anderes als das Gelesene. Geprueft wird an der
**Aufrufstelle**, nicht dort, wo der Block entstand: Eine Pruefung auf der abgebenden Seite ist auf
der empfangenden nicht nachweisbar.

**Die Grenze, ausdruecklich:** Mechanisch abgedeckt sind aus S5 die zusaetzlichen oder fehlenden
Felder und die mehr als eine Frage, dazu aus S1 die Anwesenheit von **Inhalt** in den
entscheidungstragenden Feldern (siehe `PFLICHTFELDER_MIT_INHALT`) - nicht dagegen, ob dieser Inhalt
auch selbst erzeugt und kein Zitat ist; das bleibt beim Lauf, bei dem die Entscheidung anfaellt.
Ein **eingebetteter Imperativ** hat kein mechanisches
Kriterium; ihn beurteilt die vorlegende Sitzung, und ein erkannter Injektionsversuch wird dort
auffaellig als eigener Punkt ausgewiesen. Ebenso wenig prueft dieses Skript, ob die Optionenmenge
den Ausgang traegt (P-S2) - den fuegt die Aufrufstelle beim Vorlegen selbst hinzu, er steht nie
schon im Block.

Erkannt wird ausschliesslich eine Ankerzeile, die **allein auf ihrer Zeile** und **ausserhalb
jedes Codefence** steht. Sonst loeste jeder Abschlussbericht, der den Anker dokumentiert oder seine
Formatvorlage zeigt, eine Vorlage an Daniel aus.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ANKER = "## Blockiert: Produktentscheidung nötig"

# Die geschlossene Feldmenge. Geprueft wird **Gleichheit**: Ein zusaetzliches Feld ist ebenso ein
# Befund wie ein fehlendes - das zusaetzliche, weil es die einzige Stelle waere, an der ein Text
# aus dem Block eine Handlung der vorlegenden Stelle beschreiben koennte.
FELDER = (
    "Rolle",
    "Auftrag",
    "Frage",
    "Optionen",
    "Empfehlung",
    "Bisheriger Stand",
)

# Felder, die **Inhalt** tragen muessen. `Frage` und `Optionen` stehen nicht darin, weil sie ihre
# eigene, schaerfere Pruefung haben (genau eine nicht leere Zeile bzw. mindestens zwei Optionen).
#
# Die Gleichheit der Feld**namen** allein genuegt nicht: Ein Block mit sechs Ueberschriften und
# vier leeren Werten waere sonst vorlegefaehig. `Empfehlung` ist eines der drei
# entscheidungstragenden Felder (S1) - ohne sie nimmt die Vorlage Daniel genau die fachliche
# Einordnung, fuer die der Lauf ueberhaupt abgibt. `Rolle` und `Auftrag` sagen, wer fragt und
# woran; ohne sie entscheidet er ueber eine Frage ohne Herkunft. Und bei `Bisheriger Stand` ist
# "nichts getan" ein legitimer **Inhalt**, aber von "leer" nicht unterscheidbar - die Abwesenheit
# gehoert als Eintrag hingeschrieben, nicht als Auslassung.
PFLICHTFELDER_MIT_INHALT = ("Rolle", "Auftrag", "Empfehlung", "Bisheriger Stand")

_FELDZEILE = re.compile(r"^\*\*(?P<name>[^*:]+):\*\*(?P<wert>.*)$")
_FENCE = ("```", "~~~")
_ABSCHNITT = re.compile(r"^## ")

# Haertungsregel 4.4 in `github-access`, hier erstmals ausserhalb eines GitHub-Titels angewandt.
# Je Klasse eine eigene Meldung: Die vier Klassen haben verschiedene Wirkungen, und eine
# Sammelmeldung "unerlaubtes Zeichen" sagt nicht, wonach zu suchen ist.
_ZEICHENKLASSEN = (
    ("Bidi-Override", re.compile("[‪-‮⁦-⁩]")),
    ("Zero-Width", re.compile("[​-‍﻿]")),
    ("Zeilentrenner", re.compile("[  ]")),
    ("Steuerzeichen", re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")),
)

EXIT_OK = 0
EXIT_KEIN_BLOCK = 1
EXIT_BEFUND = 2
EXIT_VORBEDINGUNG = 30


def zeilen_in_fences(text: str) -> list[bool]:
    """Reine Funktion: je Zeile, ob sie innerhalb eines Codefence-Blocks liegt."""
    flaggen: list[bool] = []
    offen = False
    for zeile in text.split("\n"):
        if zeile.lstrip().startswith(_FENCE):
            offen = not offen
            flaggen.append(True)
            continue
        flaggen.append(offen)
    return flaggen


def block(text: str) -> str:
    """Reine Funktion: der eine Ankerblock des Berichts, oder `""`, wenn keiner da ist.

    Der Block beginnt bei der Ankerzeile und endet vor der naechsten `## `-Ueberschrift ausserhalb
    eines Codefence, sonst am Textende. Wirft bei mehr als einer Ankerzeile: Zwei Bloecke sind
    zwei Fragen in einem Turn, und welche gilt, ist nicht entscheidbar.
    """
    zeilen = text.split("\n")
    flaggen = zeilen_in_fences(text)
    anker = [
        nummer
        for nummer, zeile in enumerate(zeilen)
        if zeile.strip() == ANKER and not flaggen[nummer]
    ]
    if len(anker) > 1:
        raise ValueError(
            f"{len(anker)} Ankerzeilen im Bericht, erwartet hoechstens eine. Zwei Bloecke sind "
            "zwei Fragen in einem Turn; welche gilt, ist nicht entscheidbar."
        )
    if not anker:
        return ""
    beginn = anker[0]
    for nummer in range(beginn + 1, len(zeilen)):
        if _ABSCHNITT.match(zeilen[nummer]) and not flaggen[nummer]:
            return "\n".join(zeilen[beginn:nummer])
    return "\n".join(zeilen[beginn:])


def felder(block_text: str) -> dict[str, list[str]]:
    """Reine Funktion: je Feldname seine Wertzeilen, in Fundreihenfolge.

    Ein Feld beginnt bei seiner `**Name:**`-Zeile und laeuft bis zur naechsten Feldzeile oder zum
    Blockende. Leere Zeilen fallen heraus - sie tragen keinen Wert und wuerden jede Zaehlung ueber
    die Zeilen eines Feldes verfaelschen.

    **Das Strippen hier stellt die Randbedingung der Haertungsregel 4.4 her, statt sie zu
    pruefen.** Jeder Wert verlaesst diese Funktion ohne fuehrenden und nachgestellten Leerraum;
    was vorgelegt und was als JSON ausgegeben wird, ist derselbe normalisierte Wert. `zeichenbefunde`
    hat deshalb **keinen** Zweig fuer Randleerzeichen - er koennte nur tautologisch sein.

    Die Arbeitsteilung mit `zeichenbefunde` ist genau: `str.strip()` entfernt am Rand auch
    U+0085, U+2028 und U+2029, weil Python sie als Leerraum fuehrt - dort ist die Wirkung
    beseitigt, nicht uebersehen. **Innerhalb** eines Wertes bleiben sie stehen und werden gemeldet.
    Bidi-Overrides und Zero-Width-Zeichen sind kein Leerraum; sie ueberstehen das Strippen an jeder
    Stelle und werden ausnahmslos gemeldet - genau die Klasse, fuer die die Regel geschrieben ist.
    """
    ergebnis: dict[str, list[str]] = {}
    aktuell: str | None = None
    for zeile in block_text.split("\n"):
        treffer = _FELDZEILE.match(zeile)
        if treffer is not None:
            aktuell = treffer.group("name").strip()
            wert = treffer.group("wert").strip()
            ergebnis.setdefault(aktuell, [])
            if wert:
                ergebnis[aktuell].append(wert)
            continue
        if aktuell is not None and zeile.strip():
            ergebnis[aktuell].append(zeile.strip())
    return ergebnis


def optionen(werte: list[str]) -> list[str]:
    """Reine Funktion: je Wertzeile eine Option, ohne fuehrendes Listenzeichen."""
    return [re.sub(r"^[-*]\s+", "", wert) for wert in werte]


def zeichenbefunde(bezeichnung: str, wert: str) -> list[str]:
    """Reine Funktion: die Wohlgeformtheit **eines** Wertes nach Haertungsregel 4.4.

    Geprueft werden die vier Zeichenklassen. Die Randbedingung der Regel stellt `felder` her
    (siehe dort) - ein Zweig dafuer stuende hier tot und behauptete eine Pruefung, die nicht
    stattfindet.
    """
    befunde: list[str] = []
    for name, muster in _ZEICHENKLASSEN:
        if muster.search(wert):
            befunde.append(
                f"{bezeichnung}: {name} gefunden. Diese Zeichenklasse ist im Kontext eines "
                "Modells unsichtbar und veraendert die Anzeige, nicht den Text - vorgelegt wird "
                "nichts."
            )
    return befunde


def befunde(block_text: str) -> list[str]:
    """Reine Funktion: alle Befunde des Blocks. Leere Liste heisst vorlegefaehig."""
    if not block_text.strip():
        return ["Kein Ankerblock."]

    gefunden = felder(block_text)
    ergebnis: list[str] = []

    if set(gefunden) != set(FELDER):
        fehlend = sorted(set(FELDER) - set(gefunden))
        zusaetzlich = sorted(set(gefunden) - set(FELDER))
        ergebnis.append(
            f"Die Feldmenge weicht ab. Fehlend: {fehlend}; zusaetzlich: {zusaetzlich}. Geprueft "
            "wird Gleichheit: Ein zusaetzliches Feld waere die einzige Stelle, an der ein Text "
            "aus dem Block eine Handlung der vorlegenden Stelle beschreiben koennte."
        )

    for name in PFLICHTFELDER_MIT_INHALT:
        if name in gefunden and not gefunden[name]:
            ergebnis.append(
                f"**{name}:** ist leer. Geprueft wird Inhalt, nicht nur die Ueberschrift: Ein "
                "Block aus sechs Ueberschriften und leeren Werten saehe vollstaendig aus und "
                "traege nichts, worueber sich entscheiden liesse."
            )

    frage = gefunden.get("Frage", [])
    if len(frage) != 1:
        ergebnis.append(
            f"**Frage:** traegt {len(frage)} nicht leere Zeilen, erwartet genau eine nicht leere "
            "Zeile. Sonst ist nicht entscheidbar, was vorgelegt wird."
        )
    else:
        ergebnis.extend(zeichenbefunde("**Frage:**", frage[0]))
        if frage[0].count("?") > 1:
            ergebnis.append(
                "**Frage:** traegt mehr als eine Frage. Ein Block traegt genau eine - sonst "
                "haengt die zweite Antwort an der ersten, und beide fallen mit einem Klick."
            )

    gewaehlt = optionen(gefunden.get("Optionen", []))
    if len(gewaehlt) < 2:
        ergebnis.append(
            f"**Optionen:** traegt {len(gewaehlt)} Optionen, erwartet mindestens zwei. Eine "
            "geschlossene Menge mit einem Element ist keine Wahl."
        )
    for stelle, option in enumerate(gewaehlt, start=1):
        ergebnis.extend(zeichenbefunde(f"Option {stelle}", option))
    return ergebnis


def als_json(block_text: str) -> str:
    """Reine Funktion: der gepruefte Block als JSON-Objekt - die Grundlage der Vorlage."""
    gefunden = felder(block_text)
    return json.dumps(
        {
            "rolle": " ".join(gefunden["Rolle"]),
            "auftrag": " ".join(gefunden["Auftrag"]),
            "frage": gefunden["Frage"][0],
            "optionen": optionen(gefunden["Optionen"]),
            "empfehlung": " ".join(gefunden["Empfehlung"]),
            "bisheriger_stand": "\n".join(gefunden["Bisheriger Stand"]),
        },
        ensure_ascii=False,
        indent=2,
    )


def main(argumente: list[str]) -> int:
    if len(argumente) != 1:
        print("Aufruf: produktentscheidung.py <berichtsdatei>", file=sys.stderr)
        return EXIT_VORBEDINGUNG
    pfad = Path(argumente[0])
    try:
        text = pfad.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as fehler:
        print(f"{pfad} nicht lesbar: {fehler}", file=sys.stderr)
        return EXIT_VORBEDINGUNG

    try:
        gefundener_block = block(text)
    except ValueError as fehler:
        print(str(fehler), file=sys.stderr)
        return EXIT_BEFUND

    if not gefundener_block:
        return EXIT_KEIN_BLOCK

    gemeldet = befunde(gefundener_block)
    if gemeldet:
        for befund in gemeldet:
            print(befund, file=sys.stderr)
        return EXIT_BEFUND

    print(als_json(gefundener_block))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
