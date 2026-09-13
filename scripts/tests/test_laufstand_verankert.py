r"""Haelt die Verankerung des Laufstands fest - Ausgabepflicht im Lauf, Lesepflicht in der Auskunft.

Gegenstand ist Markdown, das ein Modell zur Laufzeit interpretiert: `.claude/agents/developer.md`
gibt einen Block `## Laufstand` in seine eigene Ausgabe, `.claude/skills/laufstand/SKILL.md` liest
ihn von aussen. Kein Mechanismus dieses Repositoriums konsumiert diesen Block - er entsteht und
vergeht in einem Ausgabefenster. Zugesichert wird hier deshalb ausschliesslich **Nachweisbares**:
dass die Anweisung dasteht, an welcher Stelle sie dasteht, und dass sie nur an einer Stelle steht.

Neun Zusicherungen, je Akzeptanzkriterium der Spec getrennt, damit ein Ausfall benennt, *welche*
verschwunden ist:

1. **Der Block ist definiert** - eingezaeunt in `developer.md`, genau einmal in dieser Form.
2. **Drei Zustaende als geschlossene Menge** (Gleichheit, nicht Teilmenge) plus die
   Kardinalitaetszusage im Block selbst.
3. **Die drei Ausgabezeitpunkte abschnittsgebunden**, nicht dateiweit: zwei Fundstellen in
   Schritt 2, mindestens eine in **jedem** `## Folgeauftrag:`-Abschnitt - plus die **Zahl** dieser
   Abschnitte, sonst entzieht sich ein kuenftiger Abschnitt der Pflicht, indem ihn niemand
   eintraegt.
4. **Die Erstausgabe steht vor dem Rot-Schritt** - ueber Zeichenoffsets, nicht ueber eine
   Formulierung.
5. **Einmaligkeit der Definition** ueber den Suchraum `.claude/**` + `docs/**` + `specs/**`.
6. **Keine Ausgabepflicht in einer anderen Agenten-Datei** - der Geltungsbereich ist der
   Umsetzungslauf.
7. **Jeder `git`-Aufruf der Auskunft stammt aus einer geschlossenen Menge** von drei lesenden
   Formen, mit dem gemessenen Pfad als **einem** gequoteten Argument.
8. **Das `SendMessage`-Verbot** als Anwesenheit plus Ort jedes Vorkommens des Tokens.
9. **Die vier Saetze fuer den Fall ohne abrufbaren Stand**, die Auswahl ueber die `branch`-Zeile,
   beide Arbeitsort-Faelle, die Verweigerung fuer fremde Laeufe, und die eine echte
   Datenabhaengigkeit `ListAgents` -> `TaskOutput`.

**Was hier bewusst NICHT gebaut wird:** ein Pruefer, der aus Prosa herausliest, dass der Lauf den
Block tatsaechlich ausgibt, und eine Heuristik ueber Sitzungsprotokolle. Beide waeren gruen, ohne
etwas zu wissen - schaedlicher als kein Test, weil sie die benannte offene Flanke zudeckten. Dass
der Block zur Laufzeit erscheint und im endlichen Ausgabefenster ankommt, zeigt allein der erste
reale Umsetzungslauf nach dem Merge (`specs/architecture/0002-testkonzept.md`, Punkt 11 und
"Bekannte Luecken").

**Zwei Zusicherungen haben konstruktionsbedingt keinen Rot-Schritt.** Die Einmaligkeit (5) und die
Abwesenheit in den uebrigen Agenten-Dateien (6) sind vom ersten Lauf an gruen, weil es die zweite
Stelle nie gab. Ein kuenstlich herbeigefuehrtes Rot belegte dort nichts; der Nachweis laeuft
ueber die Gegenprobe in **beide** Richtungen an synthetischem Text und ueber die Mutation unten.

**Mutationsprobe am echten Bestand, nach Gruen gefuehrt (2026-09-13), jede Mutation danach
zurueckgenommen.** 17 gesetzt, 17 rot - je die erwartete Zusicherung:

* Anker im Codeblock umbenannt; ein vierter Zustand `[blockiert]` ergaenzt; der
  Kardinalitaetssatz entfernt - **3 von 3 rot** (1, 2).
* Der Erstausgabe-Absatz samt Codefence hinter die Rot-Grün-Refactor-Liste verschoben, Zahl der
  Fundstellen unveraendert - **rot** (4). Genau der Fall, den eine Zaehlung allein nicht faengt.
* Die Ausgabe-Anweisung aus einem der drei Folgeauftraege entfernt; ein vierter
  Folgeauftrags-Abschnitt ergaenzt - **2 von 2 rot** (3).
* `## Laufstand` in `architect.md` einmal als Prosa und einmal als Codeblock ergaenzt - **2 von 2
  rot**, und **je die richtige** Zusicherung: die Prosa-Fundstelle roetet (6), die eingezaeunte
  (5). Die Trennung ist der Beleg, dass die Codefence-Behandlung greift statt pauschal zu leeren.
* `--porcelain` an einer Fundstelle entfernt; `git add -A` in den Befehlsblock gesetzt; die
  Anfuehrungszeichen um `<Arbeitsort>` entfernt - **3 von 3 rot** (7). Die dritte ist die
  teuerste: Sie sieht wie Kosmetik aus und gibt die Quoting-Auflage des Sicherheitskonzepts auf.
* `SendMessage` in Schritt 1 erwaehnt, Verbotsabschnitt unberuehrt - **rot** (8). Eine reine
  Anwesenheitspruefung des Verbots waere hier **gruen** geblieben.
* Einen der vier Saetze aus `## Kein abrufbarer Schrittstand` entfernt; `branch refs/heads/`
  durch die `worktree`-Zeile ersetzt; einen Zustand aus der Antwortvorlage entfernt; `TaskOutput`
  vor `ListAgents` gezogen; ein Schreibwerkzeug genannt - **5 von 5 rot** (9, 2, 7).

**Und die beiden Nicht-Reaktionen, die genauso zaehlen** (sie duerfen **nicht** rot werden):
eine dritte Prosa-Erwaehnung von `## Laufstand` in einer Doku-Datei - der Pruefer verbietet eine
zweite *Definition*, keine Erwaehnung; ein Codefence mit einer Zustandszeile ohne Anker in
`architect.md` - ein Formatzitat ist keine Ausgabepflicht. Ohne diese Gegenrichtung waere nicht
belegt, dass die Pruefer ihren Gegenstand treffen statt jede Datei, die das Wort kennt.

Wer ein Muster aendert, wiederholt diese Probe, statt sie zu glauben.

Kein Netzwerk, kein GitHub, kein echtes git ausser `git ls-files`: gelesen werden ausschliesslich
die von Git verwalteten Dateien dieses Repositoriums.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

DEVELOPER_PFAD = ".claude/agents/developer.md"
SKILL_PFAD = ".claude/skills/laufstand/SKILL.md"

# --- Der Block selbst ----------------------------------------------------------------------

# Die Ueberschrift des Blocks. Ausschliesslich in `developer.md` als eingezaeunter Codeblock
# definiert - wie die uebrigen Anker dieses Laufs. Eine zweite Definitionsstelle waere ein
# zweites Abbild desselben Formats, und zwei Abbilder driften.
ANKER = "## Laufstand"

# Die drei Zustaende als **geschlossene** Menge. Verglichen wird auf Gleichheit, nicht auf
# Teilmenge: Ein vierter Zustand ("blockiert", "uebersprungen") macht die Auskunft unentscheidbar,
# und ein fehlender dritter laesst "offen" und "erledigt" ununterscheidbar werden.
ZUSTANDSMARKER = frozenset({"erledigt", "in Arbeit", "offen"})

# Der Satz, der die Kardinalitaet innerhalb des Blocks traegt. Ohne ihn ist der Block eine Liste
# von Zeilen, aus der niemand ablesen kann, welcher Schritt gerade laeuft.
EINER_IN_ARBEIT = "genau einer in Arbeit"

# Jede Listenzeile des Blocks fuehrt ihren Zustand in eckigen Klammern. Gelesen werden nur die
# Listenzeilen - eine Klammer im Fliesstext des Blocks ist kein Zustandsmarker.
_ZUSTANDSZEILE = re.compile(r"^\s*-\s*\[([^\]\n]+)\]", re.MULTILINE)

# --- Die drei Ausgabezeitpunkte, abschnittsgebunden ------------------------------------------

SCHRITT_ZWEI = "## Schritt 2"

# Der Ordnungsmarker fuer AK 2. Die Erstausgabe steht **vor** dem Rot-Schritt, nicht hinter dem
# Commit der ersten Einheit: Ein gerade gestarteter Lauf zeigt damit den vollstaendigen Plan mit
# dem ersten Schritt in Arbeit; ohne diese Reihenfolge waere "gerade gestartet" von
# "steckengeblieben" nicht zu unterscheiden.
MARKE_ROT = "**Rot:**"

# Genau zwei Anweisungen in Schritt 2: einmal vor dem ersten Rot, einmal nach jeder
# abgeschlossenen Einheit. Gezaehlt wird ueber den **codefence-freien** Abschnitt - die
# Definition des Blocks steht selbst in einem Fence und ist keine Anweisung.
AUSGABEN_IN_SCHRITT_ZWEI = 2

_FOLGEAUFTRAG = re.compile(r"^## Folgeauftrag:[^\n]*$", re.MULTILINE)

# Gemessen am Bestand (2026-09-13): `Findings beheben`, `CI-Fehlschlag beheben`,
# `Abgleich mit main`. Die Zahl steht hier, damit ein **kuenftiger** Abschnitt sich der
# Ausgabepflicht nicht dadurch entzieht, dass niemand daran denkt, ihn einzutragen: Ein vierter
# Folgeauftrag faerbt diesen Test rot und zwingt zur bewussten Entscheidung, statt still eine
# Luecke zu lassen. Sie stand bei Abfassung der Spec bei drei und ist zuletzt gewachsen.
ERWARTETE_FOLGEAUFTRAEGE = 3

# --- Die Auskunft: was sie liest, und was sie nicht anfasst ----------------------------------

# AK 4, Whitelist statt Blacklist. Eine Verbotsliste (`git add`, `git commit`, `git push`, …)
# verbietet nur, was sie benennt; die geschlossene Menge faengt auch den Befehl, an den beim
# Schreiben der Liste niemand gedacht hat. Der Platzhalter `<Arbeitsort>` steht bewusst in
# doppelten Anfuehrungszeichen: Damit ist die Quoting-Auflage aus dem Sicherheitskonzept
# (`<pfad>` als **ein** Argument, nie Bestandteil einer zusammengesetzten Kommandozeile) Teil
# der geprueften Form und nicht nur eine Absichtserklaerung im Fliesstext.
ERLAUBTE_GIT_FORMEN = (
    re.compile(r"^git worktree list --porcelain$"),
    re.compile(r'^git -C "<Arbeitsort>" log(?: .+)?$'),
    re.compile(r'^git -C "<Arbeitsort>" status --short$'),
)

# Ein Aufruf ist `git`, gefolgt von Leerraum und dem Rest bis zum naechsten Backtick oder
# Zeilenende. `git` allein in Backticks (`lokales `git``) ist kein Aufruf und faellt an der
# Leerraum-Forderung heraus - sonst waere jede Erwaehnung des Wortes ein Befund.
_GIT_AUFRUF = re.compile(r"\bgit\s+[^\n`]*")

# AK 4, zweite Haelfte. `SendMessage` landet im Kontext des Laufs und verbraucht einen seiner
# Zuege - das ist eine Veraenderung des Laufs, keine Beobachtung. Zugesichert wird die
# **Anwesenheit** des Verbots plus der **Ort** jedes Vorkommens: Ein Verbot muss sein Objekt
# nennen, und ein Textpruefer kann eine Warnung nicht von einer Anweisung unterscheiden -
# ausser ueber die Stelle, an der sie steht.
SENDMESSAGE = "SendMessage"
VERBOTSABSCHNITT = "## `SendMessage` ist als Statuskanal untersagt"

# Schreibende Werkzeuge nennt die Auskunft nirgends. Sie liest, und zwar ausschliesslich.
SCHREIBWERKZEUGE = ("Write", "Edit", "NotebookEdit")
_SCHREIBWERKZEUG = re.compile(r"\b(?:" + "|".join(SCHREIBWERKZEUGE) + r")\b")

# AK 5: beide Faelle **und** beide Verbote, je einzeln zugesichert. Als Summe geprueft bliebe
# offen, welcher der vier Saetze verschwunden ist - und die vier tragen verschiedene Schaeden.
FALLSAETZE = (
    "Es läuft kein Umsetzungslauf",
    "Das abrufbare Ausgabefenster enthält keinen `## Laufstand`-Block",
)
VERBOTSSAETZE = (
    "Ein Commit-Stand wird nie als Schrittstand ausgegeben",
    "Keine frühere Auskunft wird als aktuelle wiederholt",
)

# AK 6: der Arbeitsort wird gemessen, nicht gemeldet - und zwar an der `branch`-Zeile, nie am
# Verzeichnisnamen. Die kurze Form `git worktree list` ist Praefix der langen; ohne
# `--porcelain` ist die Ausgabe nicht zeilenweise zerlegbar und der Abgleich gegen die
# `branch`-Zeile faellt aus.
WORKTREE_BEFEHL = "git worktree list"
PORCELAIN = "--porcelain"
BRANCH_ZEILE = "branch refs/heads/"
HAUPT_CHECKOUT_FALL = "Arbeitet der Lauf im Haupt-Checkout"
NIRGENDS_AUSGECHECKT_FALL = "Ist der Branch in keinem Arbeitsbaum ausgecheckt"

# AK 8, zweite Haelfte: die Auskunft antwortet fuer einen Umsetzungslauf und verweigert sie
# sonst, statt aus fremder Ausgabe etwas herauszulesen, was dort nicht in fester Form steht.
VERWEIGERUNG = "Für jeden anderen Lauf wird die Auskunft verweigert"

# Die einzige echte Datenabhaengigkeit der drei Lesewege: Ohne die Kennung aus `ListAgents` gibt
# es kein Fenster abzurufen. Die Position der git-Messung traegt dagegen keine Aussage und wird
# ausdruecklich **nicht** eingefroren.
QUELLE_LAEUFE = "ListAgents"
QUELLE_FENSTER = "TaskOutput"

# --- Selbstschutz --------------------------------------------------------------------------

# Untergrenzen weit unter dem Ist-Stand (2026-09-13: 251 Markdown-Dateien im Suchraum, 7
# Agenten-Dateien, 21.000 bzw. 8.000 Zeichen in den beiden gelesenen Dateien). Sie fangen den
# Totalausfall der Aufzaehlung, nicht jede geloeschte Datei: Ein leer oder halb gelesener
# Suchraum darf nie als "genau einmal gefunden" oder "nirgends gefunden" durchgehen.
MINDESTZAHL_DATEIEN_IM_SUCHRAUM = 150
MINDESTZAHL_AGENTEN_DATEIEN = 7
MINDESTGROESSE = {DEVELOPER_PFAD: 10_000, SKILL_PFAD: 3_000}

SUCHRAUM_ORTE = (".claude", "docs", "specs")

_ABSCHNITT = re.compile(r"^## ", re.MULTILINE)
_FENCE = ("```", "~~~")


# --- Reine Funktionen ----------------------------------------------------------------------


def ohne_codebloecke(text: str) -> str:
    """Reine Funktion: leert jede Zeile innerhalb eines Codefence-Blocks.

    Geleert statt entfernt, damit gemeldete Zeilennummern weiterhin auf die echte Datei zeigen.
    Zwingend vor jeder Prosa- und jeder Abwesenheitspruefung: Die **Definition** des Blocks steht
    selbst in einem Codefence und traegt den Anker; ohne diese Behandlung zaehlte sie als
    Anweisung mit und jede Fundstellenzahl waere um eins daneben.
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


def codebloecke(text: str) -> list[str]:
    """Reine Funktion: alle mit ``` eingezaeunten Bloecke - dort steht eine Definition."""
    return re.findall(r"^```[^\n]*\n(.*?)^```", text, re.MULTILINE | re.DOTALL)


def abschnitt(text: str, ueberschrift: str) -> str:
    """Reine Funktion: der Abschnitt ab `ueberschrift` bis zur naechsten `## `-Zeile.

    Die Abschnittsgrenze ist bei einem Formtest ueber Markdown der wahrscheinlichste stille
    Defekt: Greift sie nicht, zieht der Abschnitt den Rest der Datei in sich und besteht jede
    Zusicherung zufaellig. Sie bekommt deshalb eine eigene Assertion, keinen Kommentar.
    """
    kopf = re.search(rf"^{re.escape(ueberschrift)}", text, re.MULTILINE)
    if kopf is None:
        raise ValueError(
            f"Ueberschrift {ueberschrift!r} nicht gefunden. Ohne sie hat dieser Test keinen "
            "Anker - ein Nullbefund darf dann nicht als 'nichts zu beanstanden' durchgehen."
        )
    naechster = _ABSCHNITT.search(text, kopf.end())
    return text[kopf.start() : naechster.start() if naechster else len(text)]


def blockdefinitionen(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: jede Datei, die den Anker **in einem Codeblock** fuehrt.

    Ein Codeblock mit dem Anker ist eine Definition des Formats; eine Erwaehnung im Fliesstext
    (in Backticks, als Verweis) ist keine und bleibt ausdruecklich frei.
    """
    if not abbild:
        raise ValueError(
            "0 Dateien im Suchraum: Ein leerer Suchraum darf nie als 'genau eine "
            "Definitionsstelle' durchgehen."
        )
    return sorted(
        datei
        for datei, inhalt in abbild.items()
        if any(ANKER in block for block in codebloecke(inhalt))
    )


def formatblock(text: str) -> str:
    """Reine Funktion: der eine Codeblock, der den Anker traegt.

    Wirft, wenn es keinen oder mehr als einen gibt - beides macht jede Aussage ueber "den" Block
    bedeutungslos, und ein stiller Nullbefund waere hier die schlechteste Antwort.
    """
    kandidaten = [block for block in codebloecke(text) if ANKER in block]
    if len(kandidaten) != 1:
        raise ValueError(
            f"{len(kandidaten)} Codebloecke mit {ANKER!r} in der Datei, erwartet genau einer. "
            "Ohne genau einen Block ist nicht entscheidbar, welche Form gilt."
        )
    return kandidaten[0]


def zustaende(block: str) -> list[str]:
    """Reine Funktion: die Zustandsmarker der Listenzeilen, in Fundreihenfolge."""
    return [treffer.strip() for treffer in _ZUSTANDSZEILE.findall(block)]


def formatverstoesse(block: str) -> list[str]:
    """Reine Funktion: die vollstaendige Formpruefung des Blocks."""
    befunde: list[str] = []

    gefunden = set(zustaende(block))
    if gefunden != set(ZUSTANDSMARKER):
        befunde.append(
            f"Der Block fuehrt die Zustaende {sorted(gefunden)}, erwartet genau "
            f"{sorted(ZUSTANDSMARKER)}. Geprueft wird Gleichheit, nicht Teilmenge: Ein vierter "
            "Zustand macht die Auskunft unentscheidbar, ein fehlender dritter laesst zwei "
            "Zustaende ununterscheidbar werden."
        )
    if EINER_IN_ARBEIT not in block:
        befunde.append(
            f"Der Block traegt {EINER_IN_ARBEIT!r} nicht. Ohne diese Kardinalitaet ist er eine "
            "Liste von Zeilen, aus der niemand ablesen kann, welcher Schritt gerade laeuft."
        )
    return befunde


def folgeauftrags_abschnitte(text: str) -> dict[str, str]:
    """Reine Funktion: je `## Folgeauftrag:`-Ueberschrift ihr Abschnittstext.

    Ausgewertet ueber den codefence-freien Text: Die Abschluss-Anker der Folgeauftraege stehen
    selbst in Codefences und sind Formatvorlagen, keine Ueberschriften des Ablaufs.
    """
    sichtbar = ohne_codebloecke(text)
    abschnitte: dict[str, str] = {}
    for kopf in _FOLGEAUFTRAG.finditer(sichtbar):
        naechster = _ABSCHNITT.search(sichtbar, kopf.end())
        ende = naechster.start() if naechster else len(sichtbar)
        abschnitte[kopf.group(0).strip()] = sichtbar[kopf.start() : ende]
    return abschnitte


def ausgabepflicht_ausserhalb(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: jede Agenten-Datei ausser `developer.md`, die den Anker nennt.

    Der Geltungsbereich der Pflicht ist ausschliesslich der Umsetzungslauf. Die kurzen
    Konsultationslaeufe bleiben unberuehrt - eine dort eingesickerte Ausgabepflicht waere eine
    zweite, nie gelesene Fortschrittsquelle.
    """
    if len(abbild) < MINDESTZAHL_AGENTEN_DATEIEN:
        raise ValueError(
            f"Nur {len(abbild)} Agenten-Dateien gefunden (erwartet mindestens "
            f"{MINDESTZAHL_AGENTEN_DATEIEN}). Die Aufzaehlung ist kaputt; eine Nullmeldung waere "
            "dann bedeutungslos."
        )
    befunde: list[str] = []
    for datei in sorted(abbild):
        if datei == DEVELOPER_PFAD:
            continue
        sichtbar = ohne_codebloecke(abbild[datei])
        for nummer, zeile in enumerate(sichtbar.split("\n"), start=1):
            if ANKER in zeile:
                befunde.append(f"{datei}:{nummer}")
    return befunde


def git_aufrufe(text: str) -> list[str]:
    """Reine Funktion: jeder `git`-Aufruf des Textes, normalisiert."""
    gefunden = []
    for treffer in _GIT_AUFRUF.finditer(text):
        aufruf = re.sub(r"\s+", " ", treffer.group(0)).strip().rstrip(".,;:)")
        if aufruf != "git":
            gefunden.append(aufruf)
    return gefunden


def unerlaubte_git_aufrufe(text: str) -> list[str]:
    """Reine Funktion: jeder `git`-Aufruf ausserhalb der geschlossenen Menge.

    Ein Text ohne jeden Aufruf ist ein Fehlerfall mit eigener Meldung: Die Auskunft **besteht**
    aus diesen drei Messungen; null Aufrufe hiessen, dass der Leser die falsche Datei liest oder
    die Messung verschwunden ist - in beiden Faellen waere eine Nullmeldung bedeutungslos.
    """
    aufrufe = git_aufrufe(text)
    if not aufrufe:
        raise ValueError(
            "0 `git`-Aufrufe im Text. Die Auskunft besteht aus den drei Messungen; ohne sie ist "
            "eine Nullmeldung dieser Whitelist bedeutungslos."
        )
    return [
        aufruf
        for aufruf in aufrufe
        if not any(muster.match(aufruf) for muster in ERLAUBTE_GIT_FORMEN)
    ]


def worktree_ohne_porcelain(text: str) -> list[str]:
    """Reine Funktion: jede `git worktree list`-Fundstelle ohne `--porcelain`."""
    return [
        aufruf
        for aufruf in git_aufrufe(text)
        if aufruf.startswith(WORKTREE_BEFEHL) and PORCELAIN not in aufruf
    ]


def sendmessage_ausserhalb_des_verbots(text: str) -> list[int]:
    """Reine Funktion: die Zeilennummern jedes `SendMessage` ausserhalb des Verbotsabschnitts.

    Ueber Offsets statt ueber eine Formulierung: "wird nicht als Statuskanal benutzt" ist als
    Prosa nicht pruefbar, der **Ort** jedes Vorkommens dagegen schon. Steht das Token irgendwo
    sonst im Skilltext, ist dort eine Verwendung entstanden - oder mindestens eine zweite,
    driftende Fassung des Verbots.
    """
    block = abschnitt(text, VERBOTSABSCHNITT)
    beginn = text.index(block)
    grenzen = range(beginn, beginn + len(block))
    return [
        text[: treffer.start()].count("\n") + 1
        for treffer in re.finditer(re.escape(SENDMESSAGE), text)
        if treffer.start() not in grenzen
    ]


def antwortvorlage(text: str) -> str:
    """Reine Funktion: der eine Codeblock der Antwortvorlage - erkannt am Zustandsmarker.

    Nicht am Anker erkannt: Die Vorlage traegt ihn bewusst **nicht**, sonst waere sie eine
    zweite Definitionsstelle des Blockformats.
    """
    kandidaten = [block for block in codebloecke(text) if "[in Arbeit]" in block]
    if len(kandidaten) != 1:
        raise ValueError(
            f"{len(kandidaten)} Codebloecke mit einer Zustandszeile, erwartet genau einer. Ohne "
            "genau eine Antwortvorlage ist nicht entscheidbar, welche Form die Auskunft hat."
        )
    return kandidaten[0]


# --- Duenne Leser --------------------------------------------------------------------------


def suchraum(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: alle von Git verwalteten `.md` unter `.claude/`, `docs/` und `specs/`.

    Ueber `git ls-files` statt `rglob`: Unterhalb von `.claude/worktrees/` liegen ausgecheckte
    Arbeitsbaeume dieses Repositoriums. Ein Verzeichnislauf faende die Definition dort noch
    einmal je Arbeitsbaum und machte die Einmaligkeitspruefung aus einem Grund rot, der mit
    ihrem Gegenstand nichts zu tun hat - und in CI (frischer Klon) faellt das nie auf.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", "--", *SUCHRAUM_ORTE],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    pfade = [roh.decode("utf-8") for roh in ergebnis.stdout.split(b"\0") if roh]
    return {
        pfad: (wurzel / pfad).read_text(encoding="utf-8")
        for pfad in pfade
        if pfad.endswith(".md") and (wurzel / pfad).is_file()
    }


def agenten_dateien(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: die Agenten-Dateien - der Geltungsbereich der Ausgabepflicht."""
    return {
        pfad: inhalt
        for pfad, inhalt in suchraum(wurzel).items()
        if pfad.startswith(".claude/agents/")
    }


def dateitext(pfad: str, wurzel: Path = REPO_WURZEL) -> str:
    return (wurzel / pfad).read_text(encoding="utf-8")


# --- Selbstschutz ----------------------------------------------------------------------------


@pytest.mark.parametrize("pfad", sorted(MINDESTGROESSE))
def test_die_geprueften_dateien_sind_plausibel_gross(pfad: str) -> None:
    """Ein leerer oder halb gelesener Text liesse jede Abwesenheitszusage leer wahr werden."""
    zeichen = len(dateitext(pfad))

    assert zeichen >= MINDESTGROESSE[pfad], (
        f"{pfad} hat nur {zeichen} Zeichen (erwartet mindestens {MINDESTGROESSE[pfad]}). "
        "Entweder ist die Datei verstuemmelt, oder der Leser liest die falsche - in beiden "
        "Faellen sagt ein Nullbefund dieses Moduls nichts."
    )


def test_der_suchraum_hat_eine_plausible_groesse() -> None:
    dateien = suchraum()

    assert len(dateien) >= MINDESTZAHL_DATEIEN_IM_SUCHRAUM, (
        f"Nur {len(dateien)} Markdown-Dateien im Suchraum (erwartet mindestens "
        f"{MINDESTZAHL_DATEIEN_IM_SUCHRAUM}). Die Aufzaehlung ist kaputt; eine Aussage ueber "
        "Einmaligkeit waere dann bedeutungslos."
    )
    assert DEVELOPER_PFAD in dateien, f"{DEVELOPER_PFAD} liegt nicht im Suchraum."


def test_ein_leerer_suchraum_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Dateien im Suchraum"):
        blockdefinitionen({})


def test_eine_leere_agentenliste_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"Agenten-Dateien"):
        ausgabepflicht_ausserhalb({DEVELOPER_PFAD: "Text"})


# --- AK 1/AK 3: der Block ist definiert, und zwar in genau einer Form -------------------------


def test_der_block_ist_in_developer_md_als_codeblock_definiert() -> None:
    """AK 1: eingezaeunt, genau einmal in dieser Datei."""
    block = formatblock(dateitext(DEVELOPER_PFAD))

    assert block.lstrip().startswith(ANKER), (
        f"Der Codeblock beginnt nicht mit {ANKER!r}, sondern mit {block.lstrip()[:40]!r}. Der "
        "Anker ist die erste Zeile der Ausgabe; steht er weiter unten, findet ihn niemand."
    )


def test_der_block_kennt_genau_die_drei_zustaende() -> None:
    """AK 3: geschlossene Menge, plus die Kardinalitaetszusage im Block selbst."""
    befunde = formatverstoesse(formatblock(dateitext(DEVELOPER_PFAD)))

    assert not befunde, "; ".join(befunde)


def test_die_blockdefinition_steht_ausschliesslich_in_developer_md() -> None:
    """AK 7: keine zweite Datei fuehrt eine Kopie - zwei Abbilder desselben Formats driften."""
    stellen = blockdefinitionen(suchraum())

    assert stellen == [DEVELOPER_PFAD], (
        f"Der Block {ANKER!r} wird in {stellen} als Codeblock gefuehrt, erwartet ausschliesslich "
        f"in {DEVELOPER_PFAD}. Eine Erwaehnung im Fliesstext ist davon unberuehrt und bleibt "
        "ausdruecklich frei; eine zweite eingezaeunte Fassung ist eine zweite Quelle."
    )


# --- AK 1/AK 2: die drei Ausgabezeitpunkte, je an ihrem Ort -----------------------------------


def test_schritt_2_verlangt_die_ausgabe_zweimal() -> None:
    """AK 1: einmal vor dem ersten Rot, einmal nach jeder abgeschlossenen Einheit.

    Abschnittsgebunden statt dateiweit: Eine dateiweite Zaehlung waere auch dann erfuellt, wenn
    beide Anweisungen in einem Folgeauftrag stuenden und der eigentliche TDD-Zyklus keine
    Ausgabe mehr verlangte.
    """
    schritt = abschnitt(ohne_codebloecke(dateitext(DEVELOPER_PFAD)), SCHRITT_ZWEI)
    gefunden = schritt.count(ANKER)

    assert gefunden == AUSGABEN_IN_SCHRITT_ZWEI, (
        f"{gefunden} Ausgabe-Anweisungen in {SCHRITT_ZWEI}, erwartet "
        f"{AUSGABEN_IN_SCHRITT_ZWEI} (vor dem ersten Rot-Schritt und nach jeder abgeschlossenen "
        "Einheit). Gezaehlt wird ueber den codefence-freien Abschnitt; die Definition des Blocks "
        "steht selbst in einem Fence und zaehlt nicht mit."
    )


def test_die_erstausgabe_steht_vor_dem_rot_schritt() -> None:
    """AK 2, ueber Zeichenoffsets statt ueber eine Formulierung."""
    schritt = abschnitt(ohne_codebloecke(dateitext(DEVELOPER_PFAD)), SCHRITT_ZWEI)
    erste = schritt.index(ANKER)
    rot = schritt.index(MARKE_ROT)
    zweite = schritt.index(ANKER, erste + len(ANKER))

    assert erste < rot, (
        f"Die erste Ausgabe-Anweisung steht hinter {MARKE_ROT!r}. Ein gerade gestarteter Lauf "
        "zeigte dann noch keinen Plan, und 'gerade gestartet' waere von 'steckengeblieben' nicht "
        "zu unterscheiden."
    )
    assert rot < zweite, (
        "Die zweite Ausgabe-Anweisung steht vor dem Rot-Schritt. Sie gehoert an das Ende des "
        "Zyklus - sie meldet eine abgeschlossene Einheit."
    )


def test_jeder_folgeauftrag_verlangt_die_ausgabe_zu_seinem_beginn() -> None:
    """AK 1, dritter Zeitpunkt - je Abschnitt einzeln, nicht als Summe."""
    abschnitte = folgeauftrags_abschnitte(dateitext(DEVELOPER_PFAD))

    ohne = sorted(kopf for kopf, text in abschnitte.items() if ANKER not in text)

    assert not ohne, (
        f"Diese Folgeauftrags-Abschnitte verlangen keine Ausgabe des Blocks: {ohne}. Der letzte "
        "sichtbare Stand behauptete dort 'alles fertig', waehrend noch gearbeitet wird - genau "
        "die Falschauskunft, gegen die der Block gebaut ist."
    )


def test_die_zahl_der_folgeauftraege_ist_zugesichert() -> None:
    """Ohne diese Zusage entzieht sich ein kuenftiger Abschnitt der Pflicht, indem ihn niemand
    eintraegt."""
    abschnitte = folgeauftrags_abschnitte(dateitext(DEVELOPER_PFAD))

    assert len(abschnitte) == ERWARTETE_FOLGEAUFTRAEGE, (
        f"{len(abschnitte)} Folgeauftrags-Abschnitte in {DEVELOPER_PFAD} "
        f"({sorted(abschnitte)}), erwartet {ERWARTETE_FOLGEAUFTRAEGE}. Kommt ein Abschnitt dazu, "
        "gehoert die Ausgabe-Anweisung hinein und diese Zahl nachgezogen - beides bewusst, nicht "
        "als Nebenprodukt."
    )


# --- AK 8: der Geltungsbereich ist der Umsetzungslauf, sonst niemand --------------------------


def test_keine_andere_agenten_datei_traegt_die_ausgabepflicht() -> None:
    befunde = ausgabepflicht_ausserhalb(agenten_dateien())

    assert not befunde, (
        f"{ANKER!r} steht in {befunde}. Die Pflicht gilt ausschliesslich fuer den "
        "Umsetzungslauf; die kurzen Konsultationslaeufe bleiben unberuehrt. Eine zweite Quelle "
        "des Fortschritts hat bei der ersten Abweichung keine."
    )


# --- Gegenproben an synthetischem Text --------------------------------------------------------

_ECHTER_BLOCK = (
    "## Laufstand\n\n"
    "**Spec:** <NNNN> — <Kurztitel>\n\n"
    "- [erledigt] <Teilschritt 1>\n"
    "- [in Arbeit] <Teilschritt 2>\n"
    "- [offen] <Teilschritt 3>\n\n"
    "Jeder Teilschritt eine Zeile, genau einer in Arbeit, der Plan jedes Mal vollständig.\n"
)


def test_die_erwartete_blockform_gilt_nicht_als_verstoss() -> None:
    assert formatverstoesse(_ECHTER_BLOCK) == []


def test_ein_vierter_zustand_wird_gemeldet() -> None:
    """Gegenprobe zur Gleichheit: Eine Teilmengenpruefung liesse genau das durch."""
    befunde = formatverstoesse(_ECHTER_BLOCK + "- [blockiert] <Teilschritt 4>\n")

    assert len(befunde) == 1
    assert "blockiert" in befunde[0]


def test_ein_fehlender_zustand_wird_gemeldet() -> None:
    ohne = _ECHTER_BLOCK.replace("- [erledigt] <Teilschritt 1>\n", "")

    befunde = formatverstoesse(ohne)

    assert len(befunde) == 1
    assert "erledigt" in befunde[0]


def test_ein_block_ohne_die_kardinalitaet_wird_gemeldet() -> None:
    ohne = _ECHTER_BLOCK.replace(EINER_IN_ARBEIT, "die Reihenfolge steht fest")

    befunde = formatverstoesse(ohne)

    assert len(befunde) == 1
    assert EINER_IN_ARBEIT in befunde[0]


def test_eine_klammer_im_fliesstext_ist_kein_zustandsmarker() -> None:
    """Sonst zoege jede eckige Klammer des Blocks in die Zustandsmenge."""
    mit_fliesstext = _ECHTER_BLOCK + "\nEine Anmerkung [in Klammern] zaehlt hier nicht mit.\n"

    assert formatverstoesse(mit_fliesstext) == []


def test_eine_erwaehnung_im_fliesstext_ist_keine_definition() -> None:
    """Gegenprobe zur Methodik: Nur ein eingezaeunter Block definiert."""
    abbild = {
        "a.md": f"Der Lauf gibt den Block `{ANKER}` aus.",
        "b.md": f"Text\n\n```\n{ANKER}\n\n- [offen] Schritt\n```\n",
    }

    assert blockdefinitionen(abbild) == ["b.md"]


def test_zwei_definitionsstellen_werden_beide_gemeldet() -> None:
    block = f"```\n{ANKER}\n```\n"

    assert blockdefinitionen({"a.md": block, "b.md": block}) == ["a.md", "b.md"]


def test_mehrere_bloecke_in_einer_datei_scheitern_laut_statt_still() -> None:
    text = f"```\n{ANKER}\n```\n\n```\n{ANKER}\n```\n"

    with pytest.raises(ValueError, match=r"2 Codebloecke"):
        formatblock(text)


def test_ein_anker_in_einer_anderen_agenten_datei_wird_gemeldet() -> None:
    abbild = {
        DEVELOPER_PFAD: f"```\n{ANKER}\n```\n",
        ".claude/agents/architect.md": f"Zeile\nGib den Block {ANKER} aus.\n",
        ".claude/agents/requirements-engineer.md": "Text\n",
        ".claude/agents/research-engineer.md": "Text\n",
        ".claude/agents/security-engineer.md": "Text\n",
        ".claude/agents/test-engineer.md": "Text\n",
        ".claude/agents/ux-ui-designer.md": "Text\n",
    }

    assert ausgabepflicht_ausserhalb(abbild) == [".claude/agents/architect.md:2"]


def test_ein_anker_im_codeblock_einer_anderen_agenten_datei_zaehlt_nicht() -> None:
    """Die Gegenrichtung: Ein Formatzitat in einem Codefence ist keine Anweisung.

    Ohne diese Behandlung waere die Abwesenheitspruefung an der eigenen Dokumentation rot - und
    der naheliegende Reparaturgriff waere eine Ausnahmeliste je Datei gewesen, die spaeter jeden
    echten Verstoss in derselben Datei mitgedeckt haette.
    """
    abbild = {
        DEVELOPER_PFAD: f"```\n{ANKER}\n```\n",
        ".claude/agents/architect.md": f"Text\n\n```\n{ANKER}\n```\n",
        ".claude/agents/requirements-engineer.md": "Text\n",
        ".claude/agents/research-engineer.md": "Text\n",
        ".claude/agents/security-engineer.md": "Text\n",
        ".claude/agents/test-engineer.md": "Text\n",
        ".claude/agents/ux-ui-designer.md": "Text\n",
    }

    assert ausgabepflicht_ausserhalb(abbild) == []


# --- AK 3/AK 4/AK 5/AK 6/AK 8: die Auskunft ---------------------------------------------------


def test_die_antwortvorlage_kennt_dieselben_drei_zustaende() -> None:
    """AK 3: dieselbe geschlossene Menge in Blockformat **und** Antwortvorlage.

    Ohne diese zweite Haelfte koennte die Auskunft drei Zustaende lesen und zwei wiedergeben -
    "offen" und "erledigt" zusammengefasst waeren genau die Auskunft, die nichts sagt.
    """
    gefunden = set(zustaende(antwortvorlage(dateitext(SKILL_PFAD))))

    assert gefunden == set(ZUSTANDSMARKER), (
        f"Die Antwortvorlage fuehrt {sorted(gefunden)}, erwartet genau {sorted(ZUSTANDSMARKER)}."
    )


def test_jeder_git_aufruf_der_auskunft_stammt_aus_der_geschlossenen_menge() -> None:
    """AK 4: Whitelist, nicht Blacklist - inklusive der Quoting-Form des gemessenen Pfades."""
    befunde = unerlaubte_git_aufrufe(dateitext(SKILL_PFAD))

    assert not befunde, (
        f"`git`-Aufruf(e) ausserhalb der geschlossenen Menge: {befunde}. Erlaubt sind "
        "ausschliesslich die drei lesenden Formen; der gemessene Pfad geht als **ein** in "
        "doppelte Anfuehrungszeichen gefasstes Argument, nie als Bestandteil einer "
        "zusammengesetzten Kommandozeile."
    )


def test_die_auskunft_nennt_kein_schreibendes_werkzeug() -> None:
    """AK 4: ein reiner Lesevorgang - sie schreibt keine Datei und setzt keinen Commit ab."""
    befunde = sorted(set(_SCHREIBWERKZEUG.findall(dateitext(SKILL_PFAD))))

    assert not befunde, (
        f"Die Auskunft nennt {befunde}. Sie ist ein Lesevorgang; ein genanntes Schreibwerkzeug "
        "ist entweder eine Verwendung oder eine Einladung dazu."
    )


def test_das_sendmessage_verbot_steht_da_und_gilt_ueberall() -> None:
    """AK 4: Anwesenheit des Verbots plus Ort jedes Vorkommens des Tokens."""
    text = dateitext(SKILL_PFAD)

    assert VERBOTSABSCHNITT in text, (
        f"Der Abschnitt {VERBOTSABSCHNITT!r} fehlt. Ohne ihn steht das Verbot nirgends, und "
        "'keine Antwort' wuerde vom Regelfall zur Ausnahme."
    )

    befunde = sendmessage_ausserhalb_des_verbots(text)

    assert not befunde, (
        f"{SENDMESSAGE!r} steht in Zeile(n) {befunde} ausserhalb des Verbotsabschnitts. Jede "
        "Nachricht landet im Kontext des Laufs und verbraucht einen seiner Zuege - das "
        "veraendert ihn, statt ihn zu beobachten."
    )


@pytest.mark.parametrize("satz", FALLSAETZE)
def test_beide_faelle_ohne_abrufbaren_stand_sind_benannt(satz: str) -> None:
    """AK 5: die beiden Faelle werden unterschieden, nicht zu einem 'kein Stand' verschmolzen."""
    assert satz in dateitext(SKILL_PFAD), (
        f"{satz!r} steht nicht in {SKILL_PFAD}. Ein gerade gestarteter Lauf und ein Lauf, dessen "
        "Block aus dem endlichen Fenster gefallen ist, sind verschiedene Auskuenfte."
    )


@pytest.mark.parametrize("satz", VERBOTSSAETZE)
def test_beide_verbote_gegen_eine_erfundene_auskunft_stehen_da(satz: str) -> None:
    """AK 5: Eine veraltete oder erfundene Antwort ist schlechter als keine."""
    assert satz in dateitext(SKILL_PFAD), (
        f"{satz!r} steht nicht in {SKILL_PFAD}. Sie saehe aus wie eine Auskunft und liesse einen "
        "steckengebliebenen Lauf fuer einen laufenden durchgehen."
    )


def test_der_arbeitsort_wird_ueber_die_branch_zeile_gemessen() -> None:
    """AK 6: `--porcelain` an jeder Fundstelle, und der Abgleich gegen die `branch`-Zeile."""
    text = dateitext(SKILL_PFAD)
    ohne_porcelain = worktree_ohne_porcelain(text)

    assert not ohne_porcelain, (
        f"`{WORKTREE_BEFEHL}` ohne `{PORCELAIN}`: {ohne_porcelain}. Die kurze Form ist Praefix "
        "der langen; ohne sie ist die Ausgabe nicht zeilenweise zerlegbar."
    )
    assert BRANCH_ZEILE in text, (
        f"{BRANCH_ZEILE!r} steht nicht in {SKILL_PFAD}. Am Bestand belegt: Verzeichnisnamen "
        "tragen die Branch-Angabe nicht - eine Auswahl ueber den Namen misst am falschen Baum "
        "und liefert eine Auskunft, die richtig aussieht."
    )


@pytest.mark.parametrize("fall", (HAUPT_CHECKOUT_FALL, NIRGENDS_AUSGECHECKT_FALL))
def test_beide_arbeitsort_faelle_sind_benannt(fall: str) -> None:
    """AK 6: nicht jeder Lauf arbeitet in einem eigenen Arbeitsbaum, und keiner muss es."""
    assert fall in dateitext(SKILL_PFAD), f"{fall!r} steht nicht in {SKILL_PFAD}."


def test_die_auskunft_verweigert_sich_fuer_jeden_anderen_lauf() -> None:
    """AK 8: kein Herauslesen aus einer Ausgabe, die den Block nicht in fester Form fuehrt."""
    assert VERWEIGERUNG in dateitext(SKILL_PFAD), (
        f"{VERWEIGERUNG!r} steht nicht in {SKILL_PFAD}. Die Ausgabepflicht gilt nur fuer den "
        "Umsetzungslauf; aus einer fremden Ausgabe einen Stand zu deuten waere geraten."
    )


def test_die_kennung_wird_vor_dem_fenster_gelesen() -> None:
    """Die einzige echte Datenabhaengigkeit der drei Lesewege, ueber Zeichenoffsets.

    Die Position der git-Messung traegt dagegen keine Aussage und wird ausdruecklich nicht
    eingefroren - eine Reihenfolgezusage ueber alle drei waere eine erfundene Ordnung.
    """
    text = ohne_codebloecke(dateitext(SKILL_PFAD))

    assert text.index(QUELLE_LAEUFE) < text.index(QUELLE_FENSTER), (
        f"{QUELLE_FENSTER} steht vor {QUELLE_LAEUFE}. Ohne die Kennung des Laufs gibt es kein "
        "Fenster abzurufen."
    )


# --- Gegenproben zur Auskunft, an synthetischem Text ------------------------------------------

_ERLAUBTE_AUFRUFE = (
    "git worktree list --porcelain",
    'git -C "<Arbeitsort>" log --oneline origin/main..HEAD',
    'git -C "<Arbeitsort>" log -1 --format=%cr',
    'git -C "<Arbeitsort>" status --short',
)


@pytest.mark.parametrize("aufruf", _ERLAUBTE_AUFRUFE)
def test_die_drei_erlaubten_formen_bleiben_gruen(aufruf: str) -> None:
    assert unerlaubte_git_aufrufe(f"Text mit `{aufruf}` darin.") == []


@pytest.mark.parametrize(
    "aufruf",
    [
        "git add .",
        'git -C "<Arbeitsort>" commit -m "Zwischenstand"',
        "git push origin HEAD",
        "git checkout feature/0449-laufstand-auf-abruf",
        "git worktree add /tmp/probe feature/0449-laufstand-auf-abruf",
        "git worktree list",
        "git -C <Arbeitsort> status --short",
        'git -C "$ARBEITSORT" status --short',
        'git -C "<Arbeitsort>" status --short && rm -rf /tmp/probe',
    ],
)
def test_jeder_aufruf_ausserhalb_der_menge_wird_gemeldet(aufruf: str) -> None:
    """Gegenprobe je Familie: schreibende Befehle, fehlendes `--porcelain`, verlorene
    Quotierung, zusammengesetzte Kommandozeile."""
    assert unerlaubte_git_aufrufe(f"Text mit `{aufruf}` darin.")


def test_eine_erwaehnung_des_wortes_git_ist_kein_aufruf() -> None:
    """Der wahrscheinlichste Selbst-Rotfall: Die Datei redet ueber `git`, ohne es aufzurufen."""
    text = "Lokales `git` bleibt unberührt. Gemessen wird mit `git worktree list --porcelain`."

    assert git_aufrufe(text) == ["git worktree list --porcelain"]


def test_ein_text_ohne_jeden_aufruf_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 `git`-Aufrufe"):
        unerlaubte_git_aufrufe("Die Auskunft misst gar nichts mehr.")


def test_ein_worktree_list_ohne_porcelain_wird_gemeldet() -> None:
    assert worktree_ohne_porcelain("Ruf `git worktree list` auf.") == ["git worktree list"]


_VERBOTSVORLAGE = (
    "# laufstand\n\n"
    "## Schritt 1\n\n"
    "Lies die Kennung.\n\n"
    f"{VERBOTSABSCHNITT}\n\n"
    f"`{SENDMESSAGE}` ist als Statuskanal untersagt: Die Nachricht landet im Kontext des Laufs.\n\n"
    "## Schritt 2\n\n"
    "Miss den Arbeitsort.\n"
)


def test_ein_sendmessage_nur_im_verbotsabschnitt_bleibt_gruen() -> None:
    assert sendmessage_ausserhalb_des_verbots(_VERBOTSVORLAGE) == []


def test_ein_sendmessage_ausserhalb_des_verbotsabschnitts_wird_gemeldet() -> None:
    """Gegenprobe zur Ortsbindung - eine reine Anwesenheitspruefung liesse genau das durch."""
    umgebaut = _VERBOTSVORLAGE.replace(
        "Miss den Arbeitsort.", f"Frag den Lauf notfalls per `{SENDMESSAGE}`."
    )

    assert sendmessage_ausserhalb_des_verbots(umgebaut) == [13]


def test_eine_antwortvorlage_ohne_zustandszeile_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Codebloecke"):
        antwortvorlage("```\nNur Prosa im Block.\n```\n")


_FOLGEAUFTRAGS_VORLAGE = (
    "## Schritt 2: TDD-Zyklus\n\n"
    f"Gib den Block `{ANKER}` aus.\n\n"
    f"1. {MARKE_ROT} Schreibe einen Test.\n"
    f"2. Melden: Gib den Block `{ANKER}` erneut aus.\n\n"
    "## Folgeauftrag: Findings beheben\n\n"
    f"Gib zu Beginn den Block `{ANKER}` aus.\n\n"
    "```\n"
    "## Abschlussbericht (Folgeauftrag: Findings behoben)\n"
    "```\n\n"
    "## Folgeauftrag: Abgleich mit `main`\n\n"
    f"Gib zu Beginn den Block `{ANKER}` aus.\n"
)


def test_die_vorlage_erfuellt_beide_zaehlungen() -> None:
    """Gegenprobe zur Methodik an synthetischem Text - die erwartete Form bleibt gruen."""
    schritt = abschnitt(ohne_codebloecke(_FOLGEAUFTRAGS_VORLAGE), SCHRITT_ZWEI)
    abschnitte = folgeauftrags_abschnitte(_FOLGEAUFTRAGS_VORLAGE)

    assert schritt.count(ANKER) == AUSGABEN_IN_SCHRITT_ZWEI
    assert schritt.index(ANKER) < schritt.index(MARKE_ROT)
    assert sorted(abschnitte) == [
        "## Folgeauftrag: Abgleich mit `main`",
        "## Folgeauftrag: Findings beheben",
    ]
    assert all(ANKER in text for text in abschnitte.values())


def test_ein_folgeauftrag_ohne_ausgabe_wird_gemeldet() -> None:
    ohne = _FOLGEAUFTRAGS_VORLAGE.replace(
        f"## Folgeauftrag: Abgleich mit `main`\n\nGib zu Beginn den Block `{ANKER}` aus.\n",
        "## Folgeauftrag: Abgleich mit `main`\n\nLoese die Konflikte auf.\n",
    )

    abschnitte = folgeauftrags_abschnitte(ohne)

    assert [kopf for kopf, text in abschnitte.items() if ANKER not in text] == [
        "## Folgeauftrag: Abgleich mit `main`"
    ]


def test_ein_abschluss_anker_im_codefence_ist_kein_folgeauftrags_abschnitt() -> None:
    """Der wahrscheinlichste Zaehlfehler: Die Abschluss-Anker nennen 'Folgeauftrag' selbst."""
    abschnitte = folgeauftrags_abschnitte(_FOLGEAUFTRAGS_VORLAGE)

    assert len(abschnitte) == 2, (
        "Ein `## Abschlussbericht (Folgeauftrag: …)` in einem Codefence ist eine Formatvorlage, "
        "kein Abschnitt des Ablaufs."
    )


def test_eine_ausgabe_in_schritt_3_zaehlt_nicht_zu_schritt_2() -> None:
    """Die Abschnittsgrenze traegt auch hier - sonst genuegte eine Erwaehnung irgendwo."""
    text = (
        "## Schritt 2: TDD-Zyklus\n\n"
        f"Gib den Block `{ANKER}` aus.\n\n"
        f"1. {MARKE_ROT} Schreibe einen Test.\n\n"
        "## Schritt 3: Codequalität\n\n"
        f"Und hier noch einmal `{ANKER}`.\n"
    )

    schritt = abschnitt(ohne_codebloecke(text), SCHRITT_ZWEI)

    assert schritt.count(ANKER) == 1


def test_der_abschnittsleser_schneidet_an_der_naechsten_ueberschrift() -> None:
    text = "## Schritt 2\nA\n\n## Schritt 3\nB\n"

    assert abschnitt(text, "## Schritt 2").strip() == "## Schritt 2\nA"
    assert "B" not in abschnitt(text, "## Schritt 2")


def test_eine_fehlende_ueberschrift_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"nicht gefunden"):
        abschnitt("# Titel\n\nNur Prosa.\n", "## Schritt 2")
