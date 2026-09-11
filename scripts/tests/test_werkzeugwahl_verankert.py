"""Haelt fest, dass die Werkzeugwahl bei Dateiarbeit an genau einem Ort verankert ist.

Seit ADR 0078 ("Dateiarbeit laeuft ueber die dedizierten Werkzeuge"; **nicht** ADR 0077, die von
einem anderen Gegenstand handelt) steht die Konvention als eigener Abschnitt
`## Werkzeugwahl bei Dateiarbeit` in
`CLAUDE.md` - zwischen `## Konventionen` und `## Doku-Pflege`, getragen von sieben Markerzeilen.
Keine andere Datei formuliert die Regel noch einmal; in `.claude/agents/developer.md` steht
ausschliesslich der zugehoerige **Ablaufschritt**, nicht die Regel.

Dieser Test sichert die **Verankerung**, ausdruecklich nicht die **Befolgung**. Eine gruene CI ist
hier keine Aussage darueber, mit welchem Werkzeug eine Zeile tatsaechlich geschrieben wurde - kein
Artefakt dieses Repositoriums zeichnet das auf, und jede Heuristik darueber (Commit-Muster,
Sitzungsprotokolle) waere gruen, ohne etwas zu wissen. Derselbe ehrliche Vorbehalt wie in
`test_setup_docs.py`.

Fuenf Zusicherungen:

1. **Verankerung in `CLAUDE.md`** - genau eine Ueberschrift an der richtigen Position; die sieben
   Marker je genau einmal, zeilenanfangs-verankert, mit nicht-leerem Inhalt; `**Grund:**` traegt
   mindestens 80 Zeichen; auf den Gegenfall-Marker folgen mindestens drei Listenpunkte; die
   `**Unberührt:**`-Zeile nennt `github-access` und `4.1`.
2. **Anti-Erosion fuer Haertungsregel 4.1** in `.claude/skills/github-access/SKILL.md`.
3. **Der Ablaufschritt in `developer.md`, Schritt 0.**
4. **Kein Marker ausserhalb des einen Abschnitts** im Suchraum `.claude/**` + `CLAUDE.md`.
5. **Markerzeilen innerhalb eines Codeblocks zaehlen nicht.**

**Zusicherung 5 ist nicht hypothetisch, sie ist am Bestand belegt.** Gemessen am 2026-09-11 fuehrt
`.claude/agents/developer.md` **zwei** zeilenanfangs-verankerte `**Grund:**`-Zeilen - beide
innerhalb der Codefences der Abschluss-Anker (`## Blockiert: …`), also Formatvorlagen und keine
Regelwiederholung. Ohne die Codefence-Behandlung waere Zusicherung 4 vom ersten Lauf an rot, und
der naheliegende Reparaturgriff waere eine Ausnahmeliste je Datei gewesen - eine, die spaeter
jeden echten Verstoss in derselben Datei mitgedeckt haette. Der Vollstaendigkeit halber: Eine
dritte Erwaehnung steht in `.claude/skills/ship-feature/SKILL.md`, dort mitten im Fliesstext in
Backticks. Sie ist keine *Markerzeile* und faellt schon an der Zeilenanfangs-Verankerung heraus.

**Die Verankerung ist hier der Schutz, nicht das Loch** - Gegenstueck zur umgekehrten Entscheidung
in `test_github_zugriff_an_einer_stelle.py`. Dort sind null Vorkommen legitim und eine Verankerung
waere eine Luecke; hier ist die *Form* die Zusicherung ("eine Zeile an fester Stelle mit eigenem
Marker"), und eine Erwaehnung im Fliesstext soll ausdruecklich frei bleiben.

**Normalisierung - gemessen, nicht angenommen** (2026-09-11, zweimal unabhaengig nachgerechnet;
die Werte bestaetigen ADR 0078 Abschnitt 8). **Nachzurechnen ist das mit den Bausteinen dieser
Datei selbst**, ohne Zusatzwerkzeug - `absatzweise_normalisiert(haertungsregel_block(
dateitext(KATALOG))).count(<nadel>)` gegen `dateitext(KATALOG).count(<nadel>)`. Das Wegwerf-
Skript, mit dem die Tabelle urspruenglich entstanden ist, ist bewusst **nicht** eingecheckt: Es
koennte nur dasselbe noch einmal, muesste aber mitgepflegt werden.

| Zeichenkette                                        | roh | normalisiert |
|-----------------------------------------------------|-----|--------------|
| `mit dem Schreib-Werkzeug angelegt`                 |   2 |            2 |
| `nie per Shell-Umleitung mit interpoliertem Inhalt` |   0 |            1 |
| ``Bodies **immer** über `--body-file` ``            |   1 |            1 |
| `Freitext ist immer ein abgegrenzter Wert, …`       |   1 |            1 |

Die zweite Zeichenkette hat im Bestand **null** rohe Treffer - sie steht dort ueber einen
Zeilenumbruch mit Folgeeinrueckung verteilt ("… mit interpoliertem\\n  Inhalt."). Deshalb wird
absatzweise normalisiert (`re.split(r"\\n\\s*\\n", …)`, dann `re.sub(r"\\s+", " ", …)`) und die
Nadeln werden **normalisiert hinterlegt**, nicht roh aus der Datei kopiert.

**Der Roh-Null-Befund steht hier als Kommentar und nicht als Assertion gegen die lebende Datei.**
Eine solche Assertion wuerde beim ersten legitimen Neuumbruch rot - also genau bei dem Ereignis,
das die Normalisierung absorbieren soll. Ausgeuebt wird die Normalisierung stattdessen an
**synthetischem** Text (siehe die Gegenproben unten); der Messwert steht hier, damit die naechste
Aenderung ihn nachrechnet statt ihn zu glauben.

**Absatzweise statt dateiweit:** Eine Normalisierung ueber Absatzgrenzen hinweg meldete einen in
zwei Absaetze zerrissenen Satz weiterhin als vorhanden. Am Bestand ergeben beide Varianten
dieselben Treffer (nachgerechnet) - die absatzweise ist also gratis strenger.

**Blockgebunden statt dateiweit, und das ist sicherheitsrelevant.**
`mit dem Schreib-Werkzeug angelegt` kommt in `github-access/SKILL.md` **zweimal** vor: einmal in
4.1 und einmal in der Operation `issue-body-schreiben`. Ueber die ganze Datei gesucht bliebe die
Zusicherung gruen, **wenn der gesamte 4.1-Block geloescht wuerde** - ein Waechter, der die
Loeschung der Regel, die er bewacht, nicht bemerkt, ist ein Scheintest. Gesucht wird deshalb
ausschliesslich ueber dem Block zwischen den Zeilenanfaengen `**4.1 ` und `**4.2 `.

**Zwei Zusicherungen ueber diesem Block, und ihre Trennung ist tragend.** Der tragende Satz
("Freitext ist immer ein abgegrenzter Wert, nie Teil der Aufrufstruktur") ist die **Regel
selbst** und wird an der **Ueberschriftszeile** geprueft - als Form, nicht als Vorkommen
irgendwo. Die drei Bullet-Zitate sind ihre `gh`-Konkretisierung und werden weiterhin ueber dem
Blockinhalt gesucht; fuer sie gibt es keine Zeile an fester Stelle.

Die Trennung ist am 2026-09-11 nach einem Copilot-Review nachgetragen worden, und der Befund war
berechtigt: Vorher stand der tragende Satz als vierte Nadel in derselben Blocksuche. Damit
verletzte diese Datei genau das Prinzip, das sie aus ADR 0061 zitiert - eine Suche ueber einen
Textblock kann "gilt" nicht von "galt einmal" unterscheiden. Eine Umschreibung der Ueberschrift
zu `**4.1 Freitext darf …**` samt historischem Zitat des alten Wortlauts weiter unten im Block
waere **gruen** geblieben und haette die Regel gleichzeitig weichgeschrieben - fuer die
wichtigste der vier Zusicherungen der Scheintest, gegen den die ganze Datei gebaut ist. Der Fall
steht jetzt als eigene Gegenprobe
(`test_der_alte_satz_im_fliesstext_rettet_eine_umgeschriebene_ueberschrift_nicht`), die
Gegenrichtung ebenfalls (`test_eine_neu_umbrochene_ueberschrift_gilt_weiterhin`).

**Mutationsprobe am echten Bestand, nach Gruen gefuehrt (2026-09-11).** Der Bestand ist nach der
Umsetzung sauber, der Test startet also gruen - ein Rot-Lauf davor belegt nichts. Tragend ist
allein die Probe danach; jede Mutation wurde gesetzt, der Lauf beobachtet und die Mutation
zurueckgenommen:

* je einen der **sieben** Marker aus `CLAUDE.md` entfernt - **7 von 7 rot**;
* je eine der drei `gh`-seitigen 4.1-Zeichenketten umformuliert, Fundstelle **im** Block -
  **3 von 3 rot**;
* die **Ueberschrift** von 4.1 umgeschrieben (`**4.1 Freitext darf in begruendeten Faellen …**`),
  Konkretisierungen unberuehrt - **rot**;
* dieselbe Umschreibung **plus** dem alten Wortlaut als historischem Zitat im Block - **rot**.
  Das ist der Fall aus dem Copilot-Review vom 2026-09-11: Vor der Trennung von Ueberschrifts- und
  Blockpruefung war er **gruen**, und er ist der Grund fuer `REGEL_UEBERSCHRIFT`;
* den gesamten 4.1-Block geloescht - **rot** (`ValueError: Blockgrenze(n) …`);
* die Fundstelle **ausserhalb** des Blocks geaendert (`issue-body-schreiben`, Zeile 196) -
  **gruen, und das ist richtig so**: Die Blockbindung schlaegt nur fuer 4.1 an, nicht fuer jede
  gleichlautende Stelle der Datei. Ohne diese Gegenrichtung waere nicht belegt, dass der
  Waechter den Block trifft statt die Datei;
* den Ablaufschritt aus `developer.md` Schritt 0 entfernt - **rot**;
* die Ueberschrift in `CLAUDE.md` umbenannt - **rot**;
* einen der drei Gegenfall-Listenpunkte gestrichen (3 -> 2) - **rot**;
* eine achte Markerzeile in `.claude/agents/architect.md` eingefuegt - **rot**.

**Ein Zwischenergebnis der Probe ist lehrreich genug, um hier zu stehen.** Der erste Anlauf
mutierte `mit dem Schreib-Werkzeug angelegt` mit `str.replace(…, 1)` und blieb **gruen** - weil
die *erste* Fundstelle der Datei (Zeile 196) in der Operation `issue-body-schreiben` liegt und
gar nicht im 4.1-Block (Zeile 529). Das ist kein Defekt, sondern die Blockbindung in ihrer
zweiten Richtung: eine Aenderung ausserhalb von 4.1 loest hier keinen Fehlalarm aus. Mit der
Fundstelle *innerhalb* des Blocks faerbte dieselbe Mutation rot. Wer die Probe wiederholt, achte
darauf, welche der beiden Fundstellen er anfasst - sonst belegt sie das Gegenteil dessen, was sie
zu belegen scheint.

**Bewusste Bruechigkeit, benannt.** Die 4.1-Literale sind eingefrorene Zitate. Eine *legitime*
Neuformulierung von 4.1 macht diesen Test rot und zwingt zum bewussten Nachziehen der Konstante.
Das ist kein Defekt, sondern der Zweck: Genau dieser Moment - 4.1 wird angefasst - ist der, in dem
jemand die Regel mit dem Argument "die neue Konvention deckt das ab" weichschreiben koennte.

**Was dieser Test ausdruecklich NICHT zusichert.** Er erkennt das **Verschwinden** von 4.1, nicht
ihre **Relativierung** durch einen spaeter eingefuegten Weichmacher-Halbsatz - ein solcher liesse
jeden Treffer bestehen. Eine Negativliste verbotener Formulierungen wird bewusst **nicht** gebaut:
unvollstaendig, fehlalarmanfaellig, und sie erzeugte genau das Sicherheitsgefuehl ohne
Absicherung, das ADR 0078 beim Hook ablehnt. Zweite Restschwaeche, ebenfalls offen: Die
Normalisierung ist blind fuer einen Umbruch *innerhalb* eines Wortes - kein Werkzeug im Projekt
bricht so um. Drittens nicht geprueft, je mit Absicht: die Reihenfolge der sieben Marker (sie
traegt keine Aussage), der Wortlaut der Gegenfaelle (das waere Formulierungspolizei) und die
Befolgung der Konvention.

Kein Netzwerk, keine MCP-Werkzeuge - gelesen werden ausschliesslich Dateien dieses Repositoriums.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

# --- Der eine Ort ------------------------------------------------------------------------

KONVENTIONSDATEI = "CLAUDE.md"
KATALOG = ".claude/skills/github-access/SKILL.md"
ABLAUFDATEI = ".claude/agents/developer.md"

UEBERSCHRIFT = "## Werkzeugwahl bei Dateiarbeit"
VORGAENGER = "## Konventionen"
NACHFOLGER = "## Doku-Pflege"

# Die sieben Markerzeilen. Jede deckt genau ein Akzeptanzkriterium ab; faellt eine bei einem
# kuenftigen Umbau weg, wird das Kriterium laut statt still ungueltig. Ihre **Reihenfolge** ist
# ausdruecklich frei - sie traegt keine Aussage, und eine Reihenfolge-Assertion erzeugte nur Rot
# bei kosmetischen Umbauten. Das ist der Unterschied zur Wege-Reihenfolge in `github-access`, wo
# "`mcp` vor `gh`" die Zusicherung *ist*.
MARKER = (
    "**Vorgabe:**",
    "**Grund:**",
    "**Shell ist die bessere Wahl bei:**",
    "**Bündelung:**",
    "**Vorrang:**",
    "**Hintergrund-Läufe:**",
    "**Unberührt:**",
)

GRUND_MARKER = "**Grund:**"

# Bewusst eine **schwache** Schranke, ausdruecklich als solche gefuehrt: Sie faengt den
# Platzhalter, nicht die schlechte Begruendung - dasselbe Konstruktionsprinzip wie
# MINDESTLAENGE_BEGRUENDUNG im ADR-0061-Waechter. 80 statt 20, weil diese Zeile zwei Gruende
# tragen muss (laut scheiterndes gegen still danebengreifendes Ersetzen, plus die
# Quoting-Fallen). Ob der Grund *der* Grund ist, entscheidet kein Muster - das ist
# Review-Kriterium.
MINDESTLAENGE_GRUND = 80

GEGENFALL_MARKER = "**Shell ist die bessere Wahl bei:**"

# Geprueft wird die **Zahl** der benannten Gegenfaelle, nicht ihr Wortlaut. Auf die drei
# konkreten Faelle per Stichwortsuche zu pruefen waere Formulierungspolizei und ginge beim ersten
# legitimen Umformulieren rot; die Zahl ist dagegen Form und faengt genau den Schaden, um den es
# geht - dass die Gegenfaelle bei einem Umbau zu "in begruendeten Faellen auch anders"
# eindampfen und die Regel damit still zum Verbot mit Feigenblatt wird.
MINDESTZAHL_GEGENFAELLE = 3

UNBERUEHRT_MARKER = "**Unberührt:**"

# Eine Abgrenzungszeile, die ihren Gegenstand nicht benennt, grenzt nichts ab. Zwei Literale sind
# die billigste Form, die das entscheidet. Bewusst **kein** `Abschnitt „…"`-Zitat, nur die
# Regelnummer: Ein solches Zitat muesste nach
# `test_github_zugriff_an_einer_stelle.py::test_jeder_zitierte_katalog_abschnitt_existiert`
# woertlich einer Katalogueberschrift entsprechen. Dass die Zeile 4.1 als **Verbot** darstellt
# und die Gegenfaelle namentlich ausschliesst, ist Review-Kriterium - kein Muster entscheidet das.
UNBERUEHRT_LITERALE = ("github-access", "4.1")

# --- Der Ablaufschritt in `developer.md` -------------------------------------------------

SCHRITT_NULL = "## Schritt 0: Vorbereitung"

# Zwei Literale: die Sache (isolierter Arbeitsstand) und das konkrete Mittel (Worktree). Ein
# Schritt, der keines von beiden nennt, ist keiner. Gemessen am 2026-09-11 enthielt
# `developer.md` **null** Vorkommen beider Woerter - der Schritt entsteht neu und hat keinen
# Bestandsschutz, der ihn zufaellig gruen hielte.
ARBEITSSTAND_LITERALE = ("Arbeitsstand", "Worktree")

# --- Anti-Erosion fuer Haertungsregel 4.1 ------------------------------------------------

BLOCK_START = "**4.1 "
BLOCK_ENDE = "**4.2 "

# Der tragende Satz - die Regel selbst. Er wird **an der Ueberschriftszeile** geprueft, nicht
# ueber dem Blockinhalt, und das ist kein Feinschliff:
#
# Ueber den Block gesucht kann eine Zeichenkette "gilt" nicht von "galt einmal" unterscheiden
# (die Lehre aus ADR 0061, die dieser Docstring selbst zitiert). Eine Umschreibung der
# Ueberschrift zu `**4.1 Freitext darf …**` samt einem Zitat des alten Satzes weiter unten im
# Fliesstext desselben Blocks liesse eine Blocksuche **gruen** - und schriebe die Regel
# gleichzeitig weich. Fuer die wichtigste der vier Zusicherungen waere das der Scheintest, gegen
# den die ganze Datei gebaut ist. Die Ueberschrift ist eine **Form**: eine Zeile an fester
# Stelle, die Fliesstext weder erfuellen noch ausloesen kann.
REGEL_UEBERSCHRIFT = "Freitext ist immer ein abgegrenzter Wert, nie Teil der Aufrufstruktur"

# Die drei `gh`-Konkretisierungen. Sie stehen als Aufzaehlung **im** Block und werden deshalb
# weiterhin ueber dem Blockinhalt gesucht - fuer sie gibt es keine Zeile an fester Stelle.
# Normalisiert hinterlegt, nicht roh aus der Datei kopiert (siehe Modul-Docstring).
HAERTUNGSREGEL_NADELN = (
    "mit dem Schreib-Werkzeug angelegt",
    "nie per Shell-Umleitung mit interpoliertem Inhalt",
    "Bodies **immer** über `--body-file`",
)

# Der Titeltext zwischen `**4.1 ` und dem schliessenden `**`. Ueber dem normalisierten ersten
# Absatz ausgewertet, damit ein legitimer Neuumbruch der Ueberschrift nichts bricht.
_REGEL_KOPF = re.compile(r"^\*\*4\.1 (?P<titel>.*?)\*\*", re.DOTALL)

# --- Selbstschutz ------------------------------------------------------------------------

# Untergrenzen weit unter dem Ist-Stand (7.615 bzw. 45.059 Zeichen am 2026-09-11). Ein leerer
# oder halb gelesener Suchraum wirft mit eigener Meldung, statt still als Nullbefund durchzugehen.
MINDESTGROESSE = {KONVENTIONSDATEI: 3_000, KATALOG: 20_000}

# Untergrenze weit unter dem Ist-Stand (24 Dateien) - sie faengt den Totalausfall der
# Dateiaufzaehlung, nicht jede geloeschte Datei.
MINDESTZAHL_DATEIEN_IM_SUCHRAUM = 15

ZUSAETZLICHE_SUCHRAUM_DATEIEN = (KONVENTIONSDATEI,)

_ABSCHNITT = re.compile(r"^## ", re.MULTILINE)
_ABSATZGRENZE = re.compile(r"\n\s*\n")
_WHITESPACE = re.compile(r"\s+")
_FENCE = ("```", "~~~")


# --- Reine Funktionen --------------------------------------------------------------------


def ohne_codebloecke(text: str) -> str:
    """Reine Funktion: leert jede Zeile innerhalb eines Codefence-Blocks.

    Geleert statt entfernt, damit Zeilennummern einer Fundstellen-Meldung weiterhin auf die
    echte Datei zeigen. Die Fence-Zeilen selbst werden mitgeleert - eine von ihnen koennte sonst
    nie ein Marker sein, aber die Symmetrie erspart einen Sonderfall.
    """
    ergebnis: list[str] = []
    offen = False
    for zeile in text.split("\n"):
        if zeile.lstrip().startswith(_FENCE):
            offen = not offen
            ergebnis.append("")
            continue
        ergebnis.append("" if offen else zeile)
    return "\n".join(ergebnis)


def abschnitt(text: str, ueberschrift: str) -> str:
    """Reine Funktion: der Abschnitt ab `ueberschrift` bis zur naechsten `## `-Zeile.

    Die Abschnittsgrenze ist bei einem Formtest ueber einen Markdown-Abschnitt der
    wahrscheinlichste stille Defekt: Greift sie nicht, zieht der Abschnitt den Rest der Datei in
    sich und besteht jede Marker-Zusicherung zufaellig. Sie bekommt deshalb eine eigene
    Assertion, keinen Kommentar.
    """
    kopf = re.search(rf"^{re.escape(ueberschrift)}\s*$", text, re.MULTILINE)
    if kopf is None:
        raise ValueError(
            f"Ueberschrift {ueberschrift!r} nicht gefunden. Ohne sie hat dieser Test keinen "
            "Anker - ein Nullbefund darf dann nicht als 'nichts zu beanstanden' durchgehen."
        )
    naechster = _ABSCHNITT.search(text, kopf.end())
    return text[kopf.start() : naechster.start() if naechster else len(text)]


def markerzeilen(text: str) -> dict[str, list[str]]:
    """Reine Funktion: je Marker der Inhalt jeder zeilenanfangs-verankerten Zeile."""
    gefunden: dict[str, list[str]] = {marker: [] for marker in MARKER}
    for zeile in text.split("\n"):
        for marker in MARKER:
            if zeile.startswith(marker):
                gefunden[marker].append(zeile[len(marker) :].strip())
    return gefunden


def gegenfaelle(text: str) -> int:
    """Reine Funktion: Zahl der Listenpunkte unmittelbar nach dem Gegenfall-Marker.

    "Unmittelbar" laesst genau eine Leerzeile zu (Markdown setzt sie ueblicherweise vor eine
    Liste) und endet am ersten Nicht-Listenpunkt. Eine Liste, die erst nach einem eingeschobenen
    Absatz kommt, gehoert nicht mehr zu diesem Marker.
    """
    zeilen = text.split("\n")
    for nummer, zeile in enumerate(zeilen):
        if not zeile.startswith(GEGENFALL_MARKER):
            continue
        anzahl = 0
        for folge in zeilen[nummer + 1 :]:
            if folge.lstrip().startswith("- "):
                anzahl += 1
            elif folge.strip() == "" and anzahl == 0:
                continue
            else:
                break
        return anzahl
    return 0


def verankerungs_verstoesse(text: str) -> list[str]:
    """Reine Funktion: die vollstaendige Formpruefung des `CLAUDE.md`-Abschnitts."""
    sichtbar = ohne_codebloecke(text)
    ueberschriften = [zeile for zeile in sichtbar.split("\n") if zeile.startswith("## ")]

    anzahl = ueberschriften.count(UEBERSCHRIFT)
    if anzahl != 1:
        return [
            f"{UEBERSCHRIFT!r} steht {anzahl} mal in {KONVENTIONSDATEI}, erwartet genau einmal. "
            "Zwei Fassungen derselben Konvention sind ein Widerspruch, null ist ein verlorener "
            "Ort."
        ]

    befunde: list[str] = []
    befunde.extend(_positions_verstoesse(ueberschriften))

    block = abschnitt(sichtbar, UEBERSCHRIFT)
    gefunden = markerzeilen(block)
    for marker in MARKER:
        inhalte = gefunden[marker]
        if len(inhalte) != 1:
            befunde.append(
                f"{marker} steht {len(inhalte)} mal im Abschnitt, erwartet genau einmal, "
                "zeilenanfangs-verankert. 'Genau einmal' statt 'mindestens einmal': Zwei "
                "Fassungen derselben Aussage verdecken sich sonst gegenseitig."
            )
        elif not inhalte[0]:
            befunde.append(f"{marker} traegt keinen Inhalt. Ein leerer Marker sichert nichts zu.")

    befunde.extend(_inhalts_verstoesse(gefunden, block))
    return befunde


def _positions_verstoesse(ueberschriften: list[str]) -> list[str]:
    """Reine Funktion: der Abschnitt steht zwischen `## Konventionen` und `## Doku-Pflege`.

    Die Position ist mitgeprueft, weil der Abschnitt sonst beim naechsten Umbau an eine Stelle
    rutschen kann, an der ihn niemand erwartet - und weil die Abschnittsgrenze dieses Tests an
    derselben Stelle festmacht.
    """
    befunde: list[str] = []
    for nachbar in (VORGAENGER, NACHFOLGER):
        if nachbar not in ueberschriften:
            befunde.append(
                f"{nachbar!r} fehlt in {KONVENTIONSDATEI}. Ohne beide Nachbarn ist die Position "
                f"von {UEBERSCHRIFT!r} nicht entscheidbar."
            )
    if befunde:
        return befunde

    stelle = ueberschriften.index(UEBERSCHRIFT)
    if not ueberschriften.index(VORGAENGER) < stelle < ueberschriften.index(NACHFOLGER):
        befunde.append(
            f"{UEBERSCHRIFT!r} steht nicht zwischen {VORGAENGER!r} und {NACHFOLGER!r}. "
            f"Reihenfolge ist: {ueberschriften}."
        )
    return befunde


def _inhalts_verstoesse(gefunden: dict[str, list[str]], block: str) -> list[str]:
    """Reine Funktion: die drei inhaltlichen Schranken hinter der reinen Marker-Form."""
    befunde: list[str] = []

    grund = gefunden[GRUND_MARKER][0] if len(gefunden[GRUND_MARKER]) == 1 else ""
    if len(grund) < MINDESTLAENGE_GRUND:
        befunde.append(
            f"{GRUND_MARKER} traegt {len(grund)} Zeichen, erwartet mindestens "
            f"{MINDESTLAENGE_GRUND}. Die Zeile muss zwei Gruende tragen (laut scheiterndes gegen "
            "still danebengreifendes Ersetzen, plus die Quoting-Fallen)."
        )

    anzahl = gegenfaelle(block)
    if anzahl < MINDESTZAHL_GEGENFAELLE:
        befunde.append(
            f"Auf {GEGENFALL_MARKER} folgen {anzahl} Listenpunkte, erwartet mindestens "
            f"{MINDESTZAHL_GEGENFAELLE}. Dampfen die Gegenfaelle ein, wird der Default still zum "
            "Verbot mit Feigenblatt."
        )

    unberuehrt = gefunden[UNBERUEHRT_MARKER][0] if len(gefunden[UNBERUEHRT_MARKER]) == 1 else ""
    fehlend = [literal for literal in UNBERUEHRT_LITERALE if literal not in unberuehrt]
    if fehlend:
        befunde.append(
            f"{UNBERUEHRT_MARKER} nennt {fehlend} nicht. Eine Abgrenzungszeile, die ihren "
            "Gegenstand nicht benennt, grenzt nichts ab."
        )
    return befunde


def ablaufschritt_verstoesse(text: str) -> list[str]:
    """Reine Funktion: Schritt 0 verlangt das Herstellen des isolierten Arbeitsstands.

    Ein Test nur auf die `**Hintergrund-Läufe:**`-Markerzeile liesse das Verschwinden dieses
    Ablaufschritts still durchgehen - und genau der ist der Teil, der in einem Hintergrund-Lauf
    tatsaechlich greift.
    """
    block = abschnitt(ohne_codebloecke(text), SCHRITT_NULL)
    fehlend = [literal for literal in ARBEITSSTAND_LITERALE if literal not in block]
    if not fehlend:
        return []
    return [
        f"{ABLAUFDATEI}, {SCHRITT_NULL}: {fehlend} kommt dort nicht vor. Der Ablaufschritt "
        "nennt die Sache (isolierter Arbeitsstand) und das Mittel (Worktree); ein Schritt, der "
        "keines von beiden nennt, ist keiner."
    ]


def absatzweise_normalisiert(text: str) -> str:
    """Reine Funktion: Whitespace je Absatz zu einem Leerzeichen, Absatzgrenzen bleiben.

    Absatzweise statt dateiweit: Eine Normalisierung ueber Absatzgrenzen hinweg meldete einen in
    zwei Absaetze zerrissenen Satz weiterhin als vorhanden.
    """
    absaetze = _ABSATZGRENZE.split(text)
    return "\n\n".join(_WHITESPACE.sub(" ", absatz).strip() for absatz in absaetze)


def haertungsregel_block(text: str) -> str:
    """Reine Funktion: der Block zwischen den Zeilenanfaengen `**4.1 ` und `**4.2 `.

    Ohne diese Bindung bliebe die Zusicherung gruen, wenn 4.1 vollstaendig geloescht wuerde - der
    zweite Treffer von `mit dem Schreib-Werkzeug angelegt` liegt in der Operation
    `issue-body-schreiben`.
    """
    start = re.search(rf"^{re.escape(BLOCK_START)}", text, re.MULTILINE)
    ende = re.search(rf"^{re.escape(BLOCK_ENDE)}", text, re.MULTILINE)
    if start is None or ende is None:
        fehlend = [
            grenze
            for grenze, treffer in ((BLOCK_START, start), (BLOCK_ENDE, ende))
            if treffer is None
        ]
        raise ValueError(
            f"Blockgrenze(n) {fehlend} nicht gefunden. Entweder ist Haertungsregel 4.1 "
            "verschwunden - dann ist genau das der Befund -, oder ihre Form hat sich geaendert, "
            "dann ist dieser Test mitzuziehen. Still nichts pruefen ist keine Option."
        )
    if ende.start() <= start.start():
        raise ValueError(
            f"{BLOCK_ENDE!r} steht vor {BLOCK_START!r}. Der Block waere leer oder negativ, und "
            "jede Nadel-Suche darueber bedeutungslos."
        )
    return text[start.start() : ende.start()]


def regeltitel(block: str) -> str:
    """Reine Funktion: der Titel zwischen `**4.1 ` und dem schliessenden `**`.

    Ueber dem **normalisierten ersten Absatz** ausgewertet: Die Ueberschrift darf legitim neu
    umbrechen, sie darf nur nicht etwas anderes sagen.
    """
    erster_absatz = _ABSATZGRENZE.split(block, maxsplit=1)[0]
    treffer = _REGEL_KOPF.match(_WHITESPACE.sub(" ", erster_absatz).strip())
    if treffer is None:
        raise ValueError(
            "Der 4.1-Block beginnt nicht mit einer abgeschlossenen `**4.1 …**`-Ueberschrift. "
            "Entweder ist die Auszeichnung kaputt, oder die Regel hat ihre Form verloren - in "
            "beiden Faellen darf hier kein stiller Nullbefund entstehen."
        )
    return treffer.group("titel")


def fehlende_nadeln(block: str) -> list[str]:
    """Reine Funktion: welche der drei `gh`-Konkretisierungen im Blockinhalt fehlen."""
    normalisiert = absatzweise_normalisiert(block)
    return [nadel for nadel in HAERTUNGSREGEL_NADELN if nadel not in normalisiert]


def erosions_befunde(block: str) -> list[str]:
    """Reine Funktion: die vollstaendige Anti-Erosions-Pruefung fuer Haertungsregel 4.1.

    Zwei getrennte Zusicherungen, und die Trennung ist der Kern: Die **Regel selbst** wird an
    ihrer Ueberschriftszeile geprueft (eine Form, kein Vorkommen), ihre drei `gh`-
    Konkretisierungen ueber dem Blockinhalt (dort gibt es keine feste Zeile).
    """
    befunde: list[str] = []

    titel = regeltitel(block)
    if REGEL_UEBERSCHRIFT not in titel:
        befunde.append(
            f"Die Ueberschrift von 4.1 traegt die Regel nicht mehr. Erwartet als Bestandteil: "
            f"{REGEL_UEBERSCHRIFT!r}; vorgefunden: {titel!r}. Ein Vorkommen desselben Satzes "
            "weiter unten im Block zaehlt hier ausdruecklich **nicht** - sonst liesse sich die "
            "Regel umschreiben und der alte Wortlaut daneben als Zitat stehen lassen."
        )

    fehlend = fehlende_nadeln(block)
    if fehlend:
        befunde.append(
            f"Die `gh`-Konkretisierung(en) {fehlend} stehen nicht mehr im 4.1-Block."
        )
    return befunde


def markerzeilen_ausserhalb(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: jede Markerzeile ausserhalb des einen erlaubten Abschnitts.

    Die zweite Haelfte von "ein Ort": Ohne sie ist die bewusste Abweichung vom
    `github-access`-Muster (keine Wiederholung in den Agenten-/Skill-Dateien) unbewacht - und sie
    zurueckzudrehen ist genau der naheliegende "Verbesserungs"-Griff eines spaeteren Umbaus.

    Ein leerer Suchraum ist ein Fehlerfall mit eigener Meldung, kein stiller Nullbefund.
    """
    if not abbild:
        raise ValueError(
            "0 Dateien im Suchraum: Damit ist 'genau ein Ort' ungeprueft. Entweder lief die "
            "Dateiaufzaehlung im falschen Arbeitsverzeichnis, oder sie ist kaputt - ein leerer "
            "Suchraum darf nie als 'nichts gefunden' durchgehen."
        )

    befunde: list[str] = []
    for datei in sorted(abbild):
        zeilen = ohne_codebloecke(abbild[datei]).split("\n")
        erlaubt = _erlaubte_zeilennummern(datei, zeilen)
        for nummer, zeile in enumerate(zeilen, start=1):
            if nummer in erlaubt:
                continue
            for marker in MARKER:
                if zeile.startswith(marker):
                    befunde.append(f"{datei}:{nummer}: {marker}")
    return befunde


def _erlaubte_zeilennummern(datei: str, zeilen: list[str]) -> set[int]:
    """Reine Funktion: die 1-basierten Zeilennummern des einen erlaubten Abschnitts."""
    if datei != KONVENTIONSDATEI:
        return set()
    start = next(
        (stelle for stelle, zeile in enumerate(zeilen) if zeile.rstrip() == UEBERSCHRIFT), None
    )
    if start is None:
        return set()
    ende = next(
        (stelle for stelle in range(start + 1, len(zeilen)) if zeilen[stelle].startswith("## ")),
        len(zeilen),
    )
    return set(range(start + 1, ende + 1))


# --- Duenne Leser ------------------------------------------------------------------------


def suchraum(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: alles unter `.claude/` **plus** `CLAUDE.md`.

    Ueber `git ls-files` statt `rglob`, damit nicht verwaltete Arbeitskopien nicht in den
    Suchraum geraten. `CLAUDE.md` liegt nicht unter `.claude/` und braucht einen zweiten
    Aufzaehlungszweig - ein stillschweigend nicht mitgelesenes `CLAUDE.md` waere hier der
    wahrscheinlichste Defekt, weil der eine erlaubte Ort genau dort liegt.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", "--", ".claude", *ZUSAETZLICHE_SUCHRAUM_DATEIEN],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    pfade = [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]
    return {pfad: (wurzel / pfad).read_text(encoding="utf-8") for pfad in pfade}


def dateitext(pfad: str, wurzel: Path = REPO_WURZEL) -> str:
    """Duenner Leser fuer eine einzelne Datei des Repositoriums."""
    return (wurzel / pfad).read_text(encoding="utf-8")


# --- Selbstschutz (a): der Suchraum ist wirklich gelesen worden ---------------------------


@pytest.mark.parametrize("pfad", sorted(MINDESTGROESSE))
def test_die_geprueften_dateien_sind_plausibel_gross(pfad: str) -> None:
    """Ein leerer oder halb gelesener Suchraum wirft, statt still gruen zu sein."""
    zeichen = len(dateitext(pfad))

    assert zeichen >= MINDESTGROESSE[pfad], (
        f"{pfad} hat nur {zeichen} Zeichen (erwartet: mindestens {MINDESTGROESSE[pfad]}). "
        "Entweder ist die Datei verstuemmelt, oder der Leser liest die falsche - in beiden "
        "Faellen sagt ein Nullbefund dieses Tests nichts."
    )


def test_der_suchraum_hat_eine_plausible_groesse() -> None:
    dateien = suchraum()

    assert len(dateien) >= MINDESTZAHL_DATEIEN_IM_SUCHRAUM, (
        f"Nur {len(dateien)} Dateien im Suchraum (erwartet: mindestens "
        f"{MINDESTZAHL_DATEIEN_IM_SUCHRAUM}). Die Aufzaehlung ist kaputt; ein Nullbefund dieses "
        "Tests waere dann bedeutungslos."
    )


def test_beide_geprueften_dateien_liegen_im_suchraum() -> None:
    dateien = suchraum()

    assert KONVENTIONSDATEI in dateien, (
        f"{KONVENTIONSDATEI} fehlt im Suchraum. Es liegt nicht unter `.claude/` und braucht "
        "einen eigenen Aufzaehlungszweig - der eine erlaubte Ort liegt genau dort."
    )
    assert ABLAUFDATEI in dateien, f"{ABLAUFDATEI} fehlt im Suchraum."


# --- Selbstschutz (b): die Abschnittsgrenze greift wirklich -------------------------------


def test_die_abschnittsgrenze_endet_am_naechsten_abschnitt() -> None:
    """Der wahrscheinlichste stille Defekt dieses Tests, deshalb eine eigene Assertion.

    Ohne sie zoege der Abschnitt bei kaputter Grenze den Rest der Datei in sich und bestuende
    jede Marker-Zusicherung zufaellig.
    """
    text = dateitext(KONVENTIONSDATEI)
    block = abschnitt(ohne_codebloecke(text), UEBERSCHRIFT)

    assert len(block) < len(text), (
        "Der extrahierte Abschnitt ist so lang wie die ganze Datei. Die Abschnittsgrenze greift "
        "nicht; jede Marker-Zusicherung bestuende danach zufaellig."
    )
    assert NACHFOLGER not in block, (
        f"Der extrahierte Abschnitt enthaelt {NACHFOLGER!r}. Er endet nicht am naechsten `## `."
    )
    assert block.startswith(UEBERSCHRIFT)


def test_der_haertungsregel_block_ist_ein_echter_ausschnitt() -> None:
    """Dieselbe Klasse von Selbstschutz fuer die zweite Abschnittsgrenze."""
    text = dateitext(KATALOG)
    block = haertungsregel_block(text)

    assert len(block) < len(text)
    assert block.startswith(BLOCK_START)
    assert BLOCK_ENDE not in block


# --- Die eigentlichen Zusicherungen -------------------------------------------------------


def test_die_konvention_ist_in_claude_md_verankert() -> None:
    befunde = verankerungs_verstoesse(dateitext(KONVENTIONSDATEI))

    assert not befunde, f"Verankerungs-Verstoss/-verstoesse in {KONVENTIONSDATEI}: " + "; ".join(
        befunde
    )


def test_haertungsregel_4_1_behaelt_ihre_absolute_form() -> None:
    """Anti-Erosion: blockgebunden, absatzweise normalisiert, die Regel an der Ueberschrift."""
    befunde = erosions_befunde(haertungsregel_block(dateitext(KATALOG)))

    assert not befunde, (
        f"Haertungsregel 4.1 in {KATALOG}: {' '.join(befunde)} "
        "Neben der weicheren Werkzeugwahl-Konvention steht 4.1 unveraendert als **Verbot** - der "
        "realistische Schadensweg ist nicht ihre Umgehung, sondern ihre spaetere Subsumtion "
        "unter den weicheren Default ('die neue Konvention deckt das ab'). Ist die "
        "Neuformulierung beabsichtigt, wird HAERTUNGSREGEL_NADELN bewusst nachgezogen - genau "
        "dieser Moment soll eine Entscheidung sein und kein Nebenprodukt."
    )


def test_schritt_0_des_developer_ablaufs_stellt_den_arbeitsstand_her() -> None:
    befunde = ablaufschritt_verstoesse(dateitext(ABLAUFDATEI))

    assert not befunde, "; ".join(befunde)


def test_keine_markerzeile_ausserhalb_des_einen_abschnitts() -> None:
    befunde = markerzeilen_ausserhalb(suchraum())

    assert not befunde, (
        f"Markerzeile(n) ausserhalb von '{KONVENTIONSDATEI} / {UEBERSCHRIFT}': "
        f"{'; '.join(befunde)}. Die Konvention gilt fuer alle Dateien identisch; eine zweite "
        "Fassung transportiert keine Information, sondern eine Quelle, die driften kann. In "
        "andere Dateien wandert nur Ablauf-Logik, nie die Regel."
    )


# --- Gegenproben an synthetischem Text ----------------------------------------------------

_ABSCHNITT_VORLAGE = "\n".join(
    [
        "# Titel",
        "",
        VORGAENGER,
        "",
        "- Ein Punkt.",
        "",
        UEBERSCHRIFT,
        "",
        "{marker}",
        "",
        NACHFOLGER,
        "",
        "Text danach.",
        "",
    ]
)


def _vollstaendige_marker(
    grund: str = "x" * MINDESTLAENGE_GRUND, gegenfaelle_zahl: int = MINDESTZAHL_GEGENFAELLE
) -> str:
    zeilen = []
    for marker in MARKER:
        if marker == GRUND_MARKER:
            zeilen.append(f"{marker} {grund}")
        elif marker == GEGENFALL_MARKER:
            zeilen.append(f"{marker} diesen Faellen:")
            zeilen.append("")
            zeilen.extend(f"- Fall {nummer}." for nummer in range(gegenfaelle_zahl))
        elif marker == UNBERUEHRT_MARKER:
            zeilen.append(f"{marker} Haertungsregel 4.1 in `github-access` bleibt ein Verbot.")
        else:
            zeilen.append(f"{marker} Inhalt.")
        zeilen.append("")
    return "\n".join(zeilen)


def test_die_erwartete_form_gilt_nicht_als_verstoss() -> None:
    text = _ABSCHNITT_VORLAGE.format(marker=_vollstaendige_marker())

    assert verankerungs_verstoesse(text) == []


def test_eine_fehlende_ueberschrift_wird_gemeldet() -> None:
    befunde = verankerungs_verstoesse(f"# Titel\n\n{VORGAENGER}\n\n{NACHFOLGER}\n")

    assert len(befunde) == 1
    assert "0 mal" in befunde[0]


def test_eine_doppelte_ueberschrift_wird_gemeldet() -> None:
    text = _ABSCHNITT_VORLAGE.format(marker=_vollstaendige_marker()) + f"\n{UEBERSCHRIFT}\n"

    befunde = verankerungs_verstoesse(text)

    assert len(befunde) == 1
    assert "2 mal" in befunde[0]


def test_eine_falsche_position_wird_gemeldet() -> None:
    """Der Abschnitt hinter `## Doku-Pflege` ist formal vollstaendig und trotzdem falsch."""
    text = "\n".join(
        [
            "# Titel",
            "",
            VORGAENGER,
            "",
            NACHFOLGER,
            "",
            UEBERSCHRIFT,
            "",
            _vollstaendige_marker(),
        ]
    )

    befunde = verankerungs_verstoesse(text)

    assert len(befunde) == 1
    assert "steht nicht zwischen" in befunde[0]


@pytest.mark.parametrize("fehlender", MARKER)
def test_ein_fehlender_marker_wird_gemeldet(fehlender: str) -> None:
    vollstaendig = _vollstaendige_marker()
    ohne = "\n".join(
        zeile for zeile in vollstaendig.split("\n") if not zeile.startswith(fehlender)
    )

    befunde = verankerungs_verstoesse(_ABSCHNITT_VORLAGE.format(marker=ohne))

    assert any(befund.startswith(f"{fehlender} steht 0 mal") for befund in befunde), befunde


def test_ein_doppelter_marker_wird_gemeldet() -> None:
    """'Genau einmal' statt 'mindestens einmal': zwei Fassungen verdecken sich gegenseitig."""
    doppelt = _vollstaendige_marker() + "\n**Vorrang:** Eine zweite, abweichende Fassung.\n"

    befunde = verankerungs_verstoesse(_ABSCHNITT_VORLAGE.format(marker=doppelt))

    assert len(befunde) == 1
    assert befunde[0].startswith("**Vorrang:** steht 2 mal")


def test_ein_leerer_marker_wird_gemeldet() -> None:
    leer = _vollstaendige_marker().replace("**Vorgabe:** Inhalt.", "**Vorgabe:**")

    befunde = verankerungs_verstoesse(_ABSCHNITT_VORLAGE.format(marker=leer))

    assert any("traegt keinen Inhalt" in befund for befund in befunde), befunde


def test_ein_zu_kurzer_grund_wird_gemeldet() -> None:
    text = _ABSCHNITT_VORLAGE.format(marker=_vollstaendige_marker(grund="Weil."))

    befunde = verankerungs_verstoesse(text)

    assert len(befunde) == 1
    assert GRUND_MARKER in befunde[0]
    assert "5 Zeichen" in befunde[0]


def test_zwei_gegenfaelle_statt_drei_werden_gemeldet() -> None:
    text = _ABSCHNITT_VORLAGE.format(marker=_vollstaendige_marker(gegenfaelle_zahl=2))

    befunde = verankerungs_verstoesse(text)

    assert len(befunde) == 1
    assert "2 Listenpunkte" in befunde[0]


def test_eine_liste_hinter_einem_eingeschobenen_absatz_zaehlt_nicht() -> None:
    """Sonst genuegte irgendeine Liste weiter unten im Abschnitt."""
    block = "\n".join(
        [
            f"{GEGENFALL_MARKER} diesen Faellen:",
            "",
            "Ein eingeschobener Absatz.",
            "",
            "- Fall 1.",
            "- Fall 2.",
            "- Fall 3.",
        ]
    )

    assert gegenfaelle(block) == 0


@pytest.mark.parametrize("fehlendes", UNBERUEHRT_LITERALE)
def test_eine_unberuehrt_zeile_ohne_ihren_gegenstand_wird_gemeldet(fehlendes: str) -> None:
    zeile = f"{UNBERUEHRT_MARKER} Haertungsregel 4.1 in `github-access` bleibt ein Verbot."
    text = _ABSCHNITT_VORLAGE.format(
        marker=_vollstaendige_marker().replace(zeile, zeile.replace(fehlendes, "…"))
    )

    befunde = verankerungs_verstoesse(text)

    assert len(befunde) == 1
    assert "grenzt nichts ab" in befunde[0]


def test_ein_marker_im_codeblock_zaehlt_nicht_als_marker() -> None:
    """Am Bestand belegt: `developer.md` fuehrt zwei `**Grund:**`-Zeilen in Codefences."""
    text = "```\n**Vorgabe:** Nur eine Formatvorlage.\n**Grund:** <konkret>\n```\n"

    assert markerzeilen(ohne_codebloecke(text)) == {marker: [] for marker in MARKER}


def test_ein_marker_ausserhalb_eines_codeblocks_zaehlt_weiterhin() -> None:
    """Gegenprobe zur Codefence-Behandlung - sonst leerte sie stillschweigend alles."""
    text = "```\n**Grund:** <konkret>\n```\n\n**Vorgabe:** Die echte Regel.\n"

    assert markerzeilen(ohne_codebloecke(text))["**Vorgabe:**"] == ["Die echte Regel."]


def test_ein_marker_in_einer_anderen_datei_wird_gemeldet() -> None:
    abbild = {
        KONVENTIONSDATEI: _ABSCHNITT_VORLAGE.format(marker=_vollstaendige_marker()),
        ".claude/agents/architect.md": "Text\n**Vorgabe:** Dieselbe Regel noch einmal.\n",
    }

    befunde = markerzeilen_ausserhalb(abbild)

    assert befunde == [".claude/agents/architect.md:2: **Vorgabe:**"]


def test_ein_marker_in_claude_md_ausserhalb_des_abschnitts_wird_gemeldet() -> None:
    """Die zweite Haelfte der Abwesenheit: auch dieselbe Datei darf es nur einmal sagen."""
    abbild = {
        KONVENTIONSDATEI: _ABSCHNITT_VORLAGE.format(marker=_vollstaendige_marker())
        + "\n**Vorgabe:** Noch einmal, hinter `## Doku-Pflege`.\n"
    }

    befunde = markerzeilen_ausserhalb(abbild)

    assert len(befunde) == 1
    assert befunde[0].endswith(": **Vorgabe:**")


def test_der_erlaubte_abschnitt_wird_uebergangen() -> None:
    abbild = {KONVENTIONSDATEI: _ABSCHNITT_VORLAGE.format(marker=_vollstaendige_marker())}

    assert markerzeilen_ausserhalb(abbild) == []


def test_eine_erwaehnung_im_fliesstext_zaehlt_nicht_als_markerzeile() -> None:
    """Am Bestand belegt: `ship-feature/SKILL.md` nennt `**Grund:**` mitten in einer Zeile."""
    abbild = {
        ".claude/skills/ship-feature/SKILL.md": (
            "Format (Feldnamen `**Feature-Branch:**`, `**Grund:**`) siehe `developer.md`.\n"
        )
    }

    assert markerzeilen_ausserhalb(abbild) == []


def test_ein_leerer_suchraum_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Dateien"):
        markerzeilen_ausserhalb({})


def test_eine_fehlende_ueberschrift_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"nicht gefunden"):
        abschnitt("# Titel\n\nNur Prosa.\n", UEBERSCHRIFT)


# --- Gegenproben zur Normalisierung, an synthetischem Text --------------------------------

# Die Nadel `nie per Shell-Umleitung mit interpoliertem Inhalt` hat im Bestand **null** rohe
# Treffer (gemessen 2026-09-11) - sie steht dort ueber einen Zeilenumbruch mit zweistelliger
# Folgeeinrueckung verteilt. Dieser Befund ist bewusst **keine** Assertion gegen die lebende
# Datei: Er wuerde beim ersten legitimen Neuumbruch rot, also genau bei dem Ereignis, das die
# Normalisierung absorbieren soll. Ausgeuebt wird sie deshalb hier, an nachgebautem Text.
_UMBROCHEN = (
    "- Auf dem `gh`-Weg: Bodies **immer** über `--body-file`, Titel über `--title`;\n"
    "  beide Dateien mit dem Schreib-Werkzeug angelegt, nie per Shell-Umleitung mit "
    "interpoliertem\n"
    "  Inhalt. Die doppelten Anführungszeichen bleiben tragend.\n"
)


def test_eine_nadel_ueber_umbruch_und_einrueckung_wird_erst_normalisiert_gefunden() -> None:
    nadel = "nie per Shell-Umleitung mit interpoliertem Inhalt"

    assert nadel not in _UMBROCHEN
    assert nadel in absatzweise_normalisiert(_UMBROCHEN)


def test_eine_geloeschte_nadel_wird_auch_normalisiert_nicht_gefunden() -> None:
    """Sonst faende die Normalisierung irgendwann alles."""
    ohne = _UMBROCHEN.replace("nie per Shell-Umleitung mit interpoliertem\n  Inhalt.", "")

    assert "nie per Shell-Umleitung mit interpoliertem Inhalt" not in absatzweise_normalisiert(
        ohne
    )


def test_ein_ueber_zwei_absaetze_zerrissener_satz_gilt_nicht_als_vorhanden() -> None:
    """Der Grund fuer absatzweise statt dateiweit: dateiweit bliebe er 'vorhanden'."""
    zerrissen = "nie per Shell-Umleitung mit\n\ninterpoliertem Inhalt.\n"
    nadel = "nie per Shell-Umleitung mit interpoliertem Inhalt"

    assert nadel not in absatzweise_normalisiert(zerrissen)
    assert nadel in _WHITESPACE.sub(" ", zerrissen)


def test_eine_geloeschte_4_1_wird_bemerkt_obwohl_die_nadel_anderswo_steht() -> None:
    """Der Grund fuer die Blockbindung, an synthetischem Text ausgeuebt.

    `mit dem Schreib-Werkzeug angelegt` steht im Bestand zweimal - der zweite Treffer liegt in
    der Operation `issue-body-schreiben`. Dateiweit gesucht bliebe die Zusicherung gruen, wenn
    der gesamte 4.1-Block geloescht wuerde.
    """
    ohne_4_1 = (
        "### `issue-body-schreiben`\n\n"
        "Die Datei wird mit dem Schreib-Werkzeug angelegt.\n\n"
        "## Die vier Härtungsregeln, wegunabhängig\n\n"
        "**4.2 Jeder Wert, der einen Aufruf steuert.**\n"
    )

    with pytest.raises(ValueError, match=r"Blockgrenze"):
        haertungsregel_block(ohne_4_1)

    # Dateiweit waere genau dieser Text ohne Befund - das ist der Scheintest, den die
    # Blockbindung verhindert.
    assert "mit dem Schreib-Werkzeug angelegt" in absatzweise_normalisiert(ohne_4_1)


_ECHTER_BLOCK = (
    "**4.1 Freitext ist immer ein abgegrenzter Wert, nie Teil der Aufrufstruktur.**\n\n"
    "- Auf dem `gh`-Weg: Bodies **immer** über `--body-file`; beide Dateien mit dem\n"
    "  Schreib-Werkzeug angelegt, nie per Shell-Umleitung mit interpoliertem Inhalt.\n"
)


def test_eine_umformulierte_nadel_im_block_wird_gemeldet() -> None:
    weichgeschrieben = _ECHTER_BLOCK.replace(
        "nie per Shell-Umleitung mit interpoliertem Inhalt",
        "moeglichst nicht per Shell-Umleitung",
    )

    assert fehlende_nadeln(_ECHTER_BLOCK) == []
    assert fehlende_nadeln(weichgeschrieben) == [
        "nie per Shell-Umleitung mit interpoliertem Inhalt"
    ]
    assert erosions_befunde(_ECHTER_BLOCK) == []


def test_eine_umgeschriebene_ueberschrift_wird_gemeldet() -> None:
    """Die Regel selbst weichgeschrieben, die Konkretisierungen unberuehrt."""
    befunde = erosions_befunde(
        _ECHTER_BLOCK.replace(
            "**4.1 Freitext ist immer ein abgegrenzter Wert, nie Teil der Aufrufstruktur.**",
            "**4.1 Freitext soll möglichst ein abgegrenzter Wert sein.**",
        )
    )

    assert len(befunde) == 1
    assert "Ueberschrift von 4.1" in befunde[0]


def test_der_alte_satz_im_fliesstext_rettet_eine_umgeschriebene_ueberschrift_nicht() -> None:
    """Genau das Loch, das eine Suche ueber den Blockinhalt offen liesse.

    Die Regel ist umgeschrieben, ihr frueherer Wortlaut steht als historisches Zitat daneben -
    eine Blocksuche faende ihn und bliebe gruen. Die Ueberschrift-Form faellt darauf nicht
    herein.
    """
    umgebaut = (
        "**4.1 Freitext darf in begründeten Fällen Teil der Aufrufstruktur sein.**\n\n"
        "Bis 2026-09-11 lautete die Regel: „Freitext ist immer ein abgegrenzter Wert, nie Teil\n"
        "der Aufrufstruktur.\"\n\n"
        "- Auf dem `gh`-Weg: Bodies **immer** über `--body-file`; beide Dateien mit dem\n"
        "  Schreib-Werkzeug angelegt, nie per Shell-Umleitung mit interpoliertem Inhalt.\n"
    )

    # Die drei Konkretisierungen stehen unveraendert da - eine reine Blocksuche waere hier still.
    assert fehlende_nadeln(umgebaut) == []
    assert REGEL_UEBERSCHRIFT in absatzweise_normalisiert(umgebaut)

    befunde = erosions_befunde(umgebaut)

    assert len(befunde) == 1
    assert "Ueberschrift von 4.1" in befunde[0]


def test_eine_neu_umbrochene_ueberschrift_gilt_weiterhin() -> None:
    """Gegenrichtung: Der Titel darf umbrechen, er darf nur nichts anderes sagen."""
    umbrochen = (
        "**4.1 Freitext ist immer ein abgegrenzter Wert, nie Teil\n"
        "der Aufrufstruktur.**\n"
        "Kein Text, den der Ablauf nicht selbst erzeugt hat, wird verkettet.\n\n"
        "- Auf dem `gh`-Weg: Bodies **immer** über `--body-file`; beide Dateien mit dem\n"
        "  Schreib-Werkzeug angelegt, nie per Shell-Umleitung mit interpoliertem Inhalt.\n"
    )

    assert erosions_befunde(umbrochen) == []


def test_ein_block_ohne_abgeschlossene_ueberschrift_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"Ueberschrift"):
        regeltitel("**4.1 Freitext ist immer ein abgegrenzter Wert\n\nohne Abschluss.\n")


def test_eine_verdrehte_blockgrenze_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"steht vor"):
        haertungsregel_block("**4.2 Zweite Regel.**\n\n**4.1 Erste Regel.**\n")


# --- Gegenproben zum Ablaufschritt --------------------------------------------------------


@pytest.mark.parametrize("fehlendes", ARBEITSSTAND_LITERALE)
def test_ein_schritt_0_ohne_den_arbeitsstand_wird_gemeldet(fehlendes: str) -> None:
    text = (
        f"{SCHRITT_NULL}\n\n"
        "1. Konventionen bestaetigen.\n"
        "2. Vor der ersten Repo-Aenderung den isolierten Arbeitsstand herstellen (Worktree).\n\n"
        "## Schritt 1: Umsetzungsplan\n"
    )

    befunde = ablaufschritt_verstoesse(text.replace(fehlendes, "…"))

    assert len(befunde) == 1
    assert fehlendes in befunde[0]


def test_ein_arbeitsstand_hinter_schritt_0_zaehlt_nicht() -> None:
    """Die Abschnittsgrenze traegt auch hier - sonst genuegte eine Erwaehnung irgendwo."""
    text = (
        f"{SCHRITT_NULL}\n\n"
        "1. Konventionen bestaetigen.\n\n"
        "## Schritt 1: Umsetzungsplan\n\n"
        "Der Worktree als isolierter Arbeitsstand kommt erst hier vor.\n"
    )

    assert ablaufschritt_verstoesse(text)
