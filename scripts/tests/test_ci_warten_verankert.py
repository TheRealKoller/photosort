"""Haelt die Verdrahtung des CI-Wartepunkts fest (Spec 0405, ADR 0091).

Der Ablauf wartet nach seinem letzten Push selbst auf das Ergebnis des CI-Laufs und bessert bei
Rot in engem Rahmen nach. Umgesetzt ist das **ausschliesslich als Text**: zwei Operationen im
Katalog `.claude/skills/github-access/SKILL.md`, je ein Ablaufschritt in `ship-feature` und
`ship-entwurf`, ein Folgeauftrag in `.claude/agents/developer.md`. Es entsteht kein Skript, keine
Schleife aus Einzelabfragen und kein eigenes Wiederholverfahren - das Warten deckt eine einzige
Befehlszeile vollstaendig ab.

Zugesichert wird deshalb ausschliesslich **Nachweisbares**:

1. **Kardinalitaet** - jedes Ablauf-Skill nennt den Wartepunkt genau einmal. „Genau ein
   Wartepunkt je Ablauf" ist ueber Prosa nicht pruefbar, ueber die Zahl der Fundstellen schon.
2. **Platzierung** ueber Zeichenoffsets - nach dem letzten Push des Laufs, vor dem Bericht.
3. **Form der einen Befehlszeile** im Katalog: `--watch`, `--fail-fast`, `--interval 30`,
   `timeout 540`, und **kein** `--required`.
4. **Geschlossenes Ergebnisvokabular** als Whitelist-**Gleichheit** ueber die Wertespalte der
   Ergebnistabelle: genau `gruen`, `rot`, `laeuft-noch`, `unbestimmt`. Ein fuenfter Wert faellt
   damit ebenso auf wie ein verschwundener - und `unbestimmt` ist der Wert, an dem die
   Fail-Closed-Zusage haengt.
5. **Einmaligkeit jeder Betriebszahl** im Suchraum `.claude/**`. Die Zahl kommt einmal vor, statt
   dass zwei Vorkommen auf Gleichheit geprueft werden: Was es nur einmal gibt, kann nicht driften.
6. **Exakte Feldmenge** von `pr-pruefstand-lesen` und **leere** Feldmenge von
   `pr-pruefstand-abwarten`. Die zweite ist die ungewoehnliche: Eine Auswertungsgrenze, deren
   Zusage das **Fehlen** jedes Feldes ist, gibt es im Katalog sonst nirgends. Sie traegt, dass aus
   dem blockierenden Aufruf weder Fremdtext noch ein Credential in Kontext oder Protokoll gelangt.
7. **Je eine Definitionsstelle** fuer den Berichtsblock `## CI-Ergebnis` (im Katalog) und fuer die
   beiden Anker des Folgeauftrags (in `developer.md`), bei **Anwesenheit** in den verbrauchenden
   Dateien. Zwei woertliche Abbilder desselben Formats driften.

**Was hier ausdruecklich NICHT gebaut wird: eine Abwesenheitspruefung auf Prosa.** Ein Pruefer,
der aus dem Fliesstext herausliest, dass ein unbestimmtes Ergebnis anhaelt, waere gruen, weil ein
Satz dasteht, und froere nebenbei die Formulierung ein; ein Pruefer, der „nirgends steht
*Warteskript*" verlangt, faerbte die Dokumentation rot, die er erzwingen soll (in Markdown ist der
erklaerende Satz nicht vom anweisenden zu trennen). Abwesenheit wird deshalb nur auf **Befehls-
und Formzeilen** geprueft: kein `--required` auf der Befehlszeile, kein Feldname in der
Auswertungsgrenze von `pr-pruefstand-abwarten`. Dass kein Wegwerf-Skript entsteht, ist ueber die
**Anwesenheit** des einen Wegs zugesichert, nicht ueber die Abwesenheit aller anderen.

Ebenfalls nicht zugesichert und deshalb Review-Kriterium: die Laufzeitentscheidungen selbst - dass
bei `rot` tatsaechlich nur reproduzierbar nachgebessert wird, dass die Pfadsperren eingehalten
werden, dass die Selbstmessung vor dem Push stattfindet. Der Waechter prueft die Verdrahtung,
nicht das Verhalten der Schleife im Fehlerfall.

**Regex-Falle derselben Klasse wie `--body`/`--body-file`:** `gh pr` ist ein Praefix von
`gh project`. Ein Muster ohne Wortgrenze etikettierte jeden Board-Befehl als Pruefstands-Befehl -
die Fundstellen-Meldung und mit ihr die Kardinalitaet der Befehlszeilen wuerde falsch.

**Mutationsprobe am echten Bestand, nach Gruen gefuehrt (2026-09-12).** Der Bestand ist nach der
Umsetzung sauber, der Test startet also gruen - ein Rot-Lauf davor belegt nichts, er faerbte rot,
weil der Text noch fehlt. Tragend ist allein die Probe danach; jede Mutation wurde gesetzt, der
Lauf beobachtet und die Mutation zurueckgenommen. **22 von 22 rot**, je Musterfamilie mindestens
einmal:

* *Befehlsform* (6): `--watch`, `--fail-fast` und das `timeout` je einzeln entfernt; das
  Wiederholintervall auf den Vorgabewert zurueckgedreht; `--required` ergaenzt; ein fuenftes Feld
  an die `--json`-Auswahl angehaengt. Der letzte ist der billigste hochwertige Nachweis der
  Praefix-Falle: `…,workflow,link` **enthaelt** die erwartete Zeichenkette und waere unter einem
  Substring-Vergleich gruen geblieben - deshalb der Vergleich des ganzen Optionswerts.
* *Vokabular* (2): `unbestimmt` geloescht; `laeuft-noch` in `pending` umbenannt.
* *Feldmengen* (2): `bucket` aus der Auswertungsgrenze von `pr-pruefstand-lesen` entfernt; ein
  Feldname in die **leere** Grenze von `pr-pruefstand-abwarten` eingesetzt.
* *Betriebszahlen* (2): `15 Minuten` ein zweites Mal in `ship-feature`, `timeout 540` ein zweites
  Mal in `developer.md` - beide faerbten genau ihren eigenen Parametrisierungsfall rot.
* *Kardinalitaet und Platzierung* (4): ein zweiter Wartepunkt in `ship-feature`; der Wartepunkt
  aus `ship-entwurf` entfernt; `pr-pruefstand-lesen` aus `ship-feature` entfernt; der ganze
  Schritt 9 vor Schritt 8 gezogen (die Offsetzusage, nicht der Wortlaut).
* *Definitionsstellen* (5): eine zweite umzaeunte Kopie des Berichtsblocks in `ship-entwurf`; das
  Feld „Art je Runde" aus der Definition entfernt; die Ueberschrift in `ship-entwurf` umbenannt;
  der „behoben"-Anker aus `developer.md` entfernt; der „blockiert"-Anker aus der Ausloeseliste von
  `ship-feature` entfernt.
* *Ein Ort fuer den Befehl* (1): die Befehlszeile zusaetzlich in einen Codeblock von
  `ship-feature` gesetzt.

**Die beiden geforderten Nicht-Reaktionen, die genauso zaehlen - beide blieben gruen:** eine
erklaerende Erwaehnung von ``gh pr checks`` im Fliesstext des Katalogs (der Katalog darf ueber
seinen eigenen Befehl reden, ohne einen zweiten abzusetzen), und eine **dritte** Datei, die den
Berichtsblock als Inline-Code *zitiert*, statt ihn umzaeunt zu definieren (der Pruefer friert
keine Dateiliste ein, er verbietet eine zweite Definition). Wer ein Muster aendert, wiederholt
diese Probe, statt sie zu glauben.

**Selbstschutz** wie bei den uebrigen Repo-Konsistenztests, weil die Haelfte der Zusagen hier
Mengen- und Formaussagen ueber gelesenen Text sind: Untergrenze fuer den Suchraum, Nachweis der
vier tragenden Dateien **im** Suchraum, plausible Mindestlaenge je Datei, Existenz jeder
Ueberschrift, an der ein Offsetvergleich haengt, Gegenprobe je Musterfamilie und lautes Scheitern
bei leerem Suchraum.

Kein echtes `gh`, kein Netzwerk, keine MCP-Werkzeuge - gelesen werden ausschliesslich Dateien
dieses Repositoriums.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

# --- Die vier tragenden Dateien ----------------------------------------------------------

KATALOG = ".claude/skills/github-access/SKILL.md"
SHIP_FEATURE = ".claude/skills/ship-feature/SKILL.md"
SHIP_ENTWURF = ".claude/skills/ship-entwurf/SKILL.md"
DEVELOPER = ".claude/agents/developer.md"

TRAGENDE_DATEIEN = (KATALOG, SHIP_FEATURE, SHIP_ENTWURF, DEVELOPER)

# Untergrenzen bewusst weit unter dem Ist-Stand. Ein leergelaufener oder falsch gelesener Text
# liesse jede Mengen- und Formaussage darueber zufaellig bestehen.
MINDESTLAENGE = {KATALOG: 20_000, SHIP_FEATURE: 10_000, SHIP_ENTWURF: 10_000, DEVELOPER: 10_000}

# Untergrenze weit unter dem Ist-Stand (24 Dateien) - sie faengt den Totalausfall der
# Dateiaufzaehlung, nicht jede geloeschte Datei.
MINDESTZAHL_DATEIEN_IM_SUCHRAUM = 15

ZUSAETZLICHE_SUCHRAUM_DATEIEN = ("CLAUDE.md",)

# --- 1./2. Der Wartepunkt: Kardinalitaet und Platzierung ---------------------------------

# Der Wartepunkt ist die blockierende Operation. Erkannt wird sie als Inline-Code, also genau in
# der Form, in der ein Ablauf-Skill auf einen GitHub-Zugriff verweisen darf (ADR 0061).
WARTEPUNKT = "`pr-pruefstand-abwarten`"
BELEG_OPERATION = "`pr-pruefstand-lesen`"

# Je Ablauf-Skill die beiden Marken, zwischen denen der Wartepunkt liegen muss: die Ueberschrift
# des Schritts, der den letzten Push des Laufs enthaelt bzw. ihm folgt, ohne selbst zu pushen -
# und die Ueberschrift des Berichts. Ueber Zeichenoffsets statt ueber einen Abschnittsleser: Der
# Bericht traegt selbst eine eingezaeunte `##`-Zeile, an der ein Abschnittsleser schnitte.
ABLAUF_MARKEN: dict[str, tuple[str, str]] = {
    SHIP_FEATURE: (
        "## Schritt 8: Finalisierung im selben PR (vor dem Merge)",
        "## Abschlussbericht an den Nutzer",
    ),
    SHIP_ENTWURF: (
        "## Schritt 7: Board-Rücklesen — nur mit Story",
        "## Bericht an Daniel",
    ),
}

# --- 3. Die eine Befehlszeile ------------------------------------------------------------

# Wortgrenze zwingend: `gh pr` ist ein Praefix von `gh project`.
_PRUEFSTAND_BEFEHL = re.compile(r"\bgh pr checks\b")

# Die blockierende Zeile traegt diese vier Marken - und `--required` nicht. Das `--required`
# filterte, solange kein Check in der Branch Protection als erforderlich eingetragen ist, alles
# weg; die Pruefung waere leer wahr, und ein roter Lauf ginge als gruen durch.
BLOCKIERENDE_MARKEN = ("--watch", "--fail-fast", "--interval 30", "timeout 540")
VERBOTENE_OPTION = "--required"

# Die nicht blockierende Zeile traegt die Feldauswahl - dieselben vier Felder wie ihre
# Auswertungsgrenze, damit die Verengung strukturell und nicht nur nachtraeglich stattfindet.
#
# Verglichen wird der **ganze** Wert hinter `--json`, nicht ein Vorkommen darin: Dieselbe
# Praefix-Falle wie bei `--body`/`--body-file`. Ein angehaengtes fuenftes Feld
# (`…,workflow,link`) enthielte die erwartete Zeichenkette weiterhin, und die Verengung waere
# lautlos aufgeweicht.
LESE_FELDER = "bucket,name,state,workflow"
LESE_MARKE = f"--json {LESE_FELDER}"
_JSON_OPTION = re.compile(r"--json\s+(\S+)")

ERWARTETE_ZAHL_BEFEHLSZEILEN = 2

# --- 4. Das geschlossene Ergebnisvokabular ------------------------------------------------

ERGEBNIS_TABELLENKOPF = "| Ergebniswert | Entsteht aus | Folge |"
ERWARTETE_ERGEBNISWERTE = ("gruen", "rot", "laeuft-noch", "unbestimmt")

_ERGEBNIS_ZEILE = re.compile(r"^\|\s*`([^`|]+)`\s*\|")

# --- 5. Die Betriebszahlen ----------------------------------------------------------------

# Jede Zahl in der Form, in der sie im Katalog steht - nicht als blosse Ziffer. Eine Ziffer allein
# waere im Anweisungsraum vielfach belegt (`alle 20-30s`, Schrittnummern, Projektnummer 8), und
# die Einmaligkeitszusage waere von Anfang an rot aus einem Grund, der mit ihrem Gegenstand nichts
# zu tun hat. Gezaehlt wird deshalb die Zahl **samt ihrer Einheit bzw. ihres Optionsnamens**.
BETRIEBSZAHLEN = (
    "timeout 540",  # Einzelaufruf, unter der 600-Sekunden-Deckelung der Werkzeugumgebung
    "--interval 30",  # Wiederholintervall
    "15 Minuten",  # Wartefenster je Lauf
    "120 Sekunden",  # Anlaufschonfrist nach dem Push
    "2 Nachbesserungsrunden",  # Obergrenze der Nachbesserung
)

# --- 6. Die beiden Feldmengen -------------------------------------------------------------

AUSWERTUNGSGRENZE = "**Auswertungsgrenze:**"

# Bewusst dieselbe Form und derselbe Leser wie in `test_github_zugriff_an_einer_stelle.py`, dort
# noch einmal hinterlegt statt importiert: Zwei Testmodule, die einander importieren, scheitern
# gemeinsam, sobald eines umbenannt wird - dieselbe Entscheidung wie beim ID-Erkenner in
# `test_ship_entwurf_skill.py`.
_AUSWERTUNGSGRENZE_ZEILE = re.compile(r"^\*\*Auswertungsgrenze:\*\*(?P<rest>[^\n]*)$", re.MULTILINE)
_BACKTICK_TOKEN = re.compile(r"`([^`\n]+)`")

ERWARTETE_FELDMENGEN: dict[str, tuple[str, ...]] = {
    "pr-pruefstand-lesen": ("bucket", "name", "state", "workflow"),
    "pr-pruefstand-abwarten": (),
}

_EINTRAG_KOPF = "### `{}`"

# --- 7. Berichtsblock und Anker -----------------------------------------------------------

BERICHTSBLOCK = "## CI-Ergebnis"
BERICHTSBLOCK_FELDER = ("**Endstand:**", "**Nachbesserungsrunden:**", "**Art je Runde:**")

ANKER_BEHOBEN = "## Abschlussbericht (Folgeauftrag: CI-Fehlschlag behoben)"
ANKER_BLOCKIERT = "## Blockiert: CI-Fehlschlag außerhalb der zulässigen Klasse"
NEUE_ANKER = (ANKER_BEHOBEN, ANKER_BLOCKIERT)

_CODEBLOCK = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)


# --- Duenne Leser --------------------------------------------------------------------------


def dateitext(pfad: str, wurzel: Path = REPO_WURZEL) -> str:
    return (wurzel / pfad).read_text(encoding="utf-8")


def katalogtext() -> str:
    return dateitext(KATALOG)


def suchraum(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: alles unter `.claude/` **plus** `CLAUDE.md`.

    Ueber `git ls-files` statt `rglob`, damit nicht verwaltete Arbeitskopien - etwa ein Worktree
    unterhalb von `.claude/` - nicht in den Suchraum geraten. Aus einem Haupt-Checkout heraus
    saehe `rglob` die Betriebszahlen sonst in jedem parallelen Arbeitsbaum erneut, und die
    Einmaligkeitszusage waere rot aus einem Grund, der mit ihrem Gegenstand nichts zu tun hat.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", "--", ".claude", *ZUSAETZLICHE_SUCHRAUM_DATEIEN],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    pfade = [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]
    return {pfad: (wurzel / pfad).read_text(encoding="utf-8") for pfad in pfade}


# --- Reine Funktionen ----------------------------------------------------------------------


def codebloecke(text: str) -> list[str]:
    """Reine Funktion: die Inhalte aller mit ``` umzaeunten Bloecke."""
    return _CODEBLOCK.findall(text)


def befehlszeilen(text: str) -> list[str]:
    """Reine Funktion: die Pruefstands-Befehlszeilen **innerhalb** der Codebloecke.

    Die Beschraenkung auf Codebloecke ist die geforderte Nicht-Reaktion: Eine erklaerende
    Erwaehnung des Befehls im Fliesstext des Katalogs ist keine Befehlszeile und darf den
    Formpruefer nicht ausloesen.
    """
    return [
        zeile.strip()
        for block in codebloecke(text)
        for zeile in block.split("\n")
        if _PRUEFSTAND_BEFEHL.search(zeile)
    ]


def form_befunde(zeilen: list[str]) -> list[str]:
    """Reine Funktion: die vollstaendige Formpruefung der Pruefstands-Befehlszeilen."""
    if len(zeilen) != ERWARTETE_ZAHL_BEFEHLSZEILEN:
        return [
            f"{len(zeilen)} Pruefstands-Befehlszeilen gefunden ({zeilen}), erwartet genau "
            f"{ERWARTETE_ZAHL_BEFEHLSZEILEN}: die blockierende und die lesende. Eine dritte ist "
            "eine zweite Wahrheit ueber das Warten, keine ist gar keine."
        ]

    befunde: list[str] = []
    blockierend = [zeile for zeile in zeilen if "--watch" in zeile]
    if len(blockierend) != 1:
        befunde.append(
            f"{len(blockierend)} der Befehlszeilen tragen `--watch`, erwartet genau eine. Ohne "
            "sie wartet nichts; mit zweien wartet der Ablauf zweimal."
        )
        return befunde

    fehlend = [marke for marke in BLOCKIERENDE_MARKEN if marke not in blockierend[0]]
    if fehlend:
        befunde.append(
            f"Der blockierenden Befehlszeile fehlt/fehlen {fehlend}: {blockierend[0]!r}. Ohne "
            "`--fail-fast` laeuft das Fenster nach dem ersten Fehlschlag weiter, ohne "
            "`--interval 30` entscheidet der Vorgabewert, und ohne das `timeout` scheitert der "
            "Aufruf an der Deckelung der Werkzeugumgebung statt an seiner eigenen Grenze."
        )

    mit_verbotener = [zeile for zeile in zeilen if VERBOTENE_OPTION in zeile]
    if mit_verbotener:
        befunde.append(
            f"{VERBOTENE_OPTION} steht auf einer Pruefstands-Befehlszeile: {mit_verbotener}. "
            "Solange kein Check in der Branch Protection als erforderlich eingetragen ist, "
            "filtert die Option alles weg - die Pruefung waere leer wahr, und ein roter Lauf "
            "ginge als gruen durch."
        )

    lesend = [zeile for zeile in zeilen if zeile not in blockierend]
    gewaehlte_felder = [
        treffer.group(1) for zeile in lesend for treffer in _JSON_OPTION.finditer(zeile)
    ]
    if gewaehlte_felder != [LESE_FELDER]:
        befunde.append(
            f"Die lesende Befehlszeile waehlt {gewaehlte_felder} statt genau [{LESE_FELDER!r}]: "
            f"{lesend}. Die Feldmenge ist die Sicherheitszusage dieser Operation und wird "
            "strukturell verengt, nicht erst bei der Auswertung - ein angehaengtes fuenftes Feld "
            "zoege weiteren fremdbeschreibbaren Text in einen Kontext, der unmittelbar danach "
            "Code aendert und pusht."
        )
    return befunde


def ergebniswerte(text: str) -> tuple[str, ...]:
    """Reine Funktion: die Wertespalte der Ergebnistabelle, in Tabellenreihenfolge.

    Gelesen wird ausschliesslich die **erste** Zelle je Zeile. Die zweite Spalte fuehrt selbst
    Backticks (`pr-pruefstand-lesen`, `bucket == fail`); ohne diese Grenze zoege jedes davon in
    das Vokabular - dieselbe Falle wie bei der Auswertungsgrenze, nur eine Spalte weiter.
    """
    beginn = text.find(ERGEBNIS_TABELLENKOPF)
    if beginn == -1:
        raise ValueError(
            f"Tabellenkopf {ERGEBNIS_TABELLENKOPF!r} nicht gefunden. Entweder ist die "
            "Ergebnistabelle verschwunden - dann ist genau das der Befund -, oder ihre Form hat "
            "sich geaendert, dann ist dieser Test mitzuziehen. Still nichts pruefen ist keine "
            "Option."
        )
    werte: list[str] = []
    for zeile in text[beginn:].split("\n")[1:]:
        if not zeile.startswith("|"):
            break
        treffer = _ERGEBNIS_ZEILE.match(zeile)
        if treffer is not None:
            werte.append(treffer.group(1).strip())
    return tuple(werte)


def eintragsblock(text: str, operation: str) -> str:
    """Reine Funktion: der Rumpf eines `###`-Katalogeintrags bis zur naechsten Ueberschrift."""
    kopf = _EINTRAG_KOPF.format(operation)
    beginn = text.find(kopf)
    if beginn == -1:
        raise ValueError(
            f"Katalogeintrag {kopf!r} nicht gefunden. Ohne den Eintrag ist jede Zusage ueber "
            "seine Form leer wahr."
        )
    rest = text[beginn + len(kopf) :]
    grenzen = [stelle for stelle in (rest.find("\n### "), rest.find("\n## ")) if stelle != -1]
    return rest if not grenzen else rest[: min(grenzen)]


def ausgewertete_felder(block: str) -> tuple[str, ...]:
    """Reine Funktion: die Feldnamen einer Auswertungsgrenze, in Fundreihenfolge.

    Gelesen wird ausschliesslich der Teil **vor** dem Gedankenstrich; dahinter steht Prosa, die
    ihrerseits Backticks fuehrt. Eine leere Rueckgabe ist hier ein zulaessiges Ergebnis und die
    Zusage von `pr-pruefstand-abwarten` - deshalb ist die fehlende Zeile ein **lauter** Fehler
    und nicht einfach die leere Menge.
    """
    treffer = _AUSWERTUNGSGRENZE_ZEILE.search(block)
    if treffer is None:
        raise ValueError(
            f"Keine {AUSWERTUNGSGRENZE}-Zeile im Block. Ohne sie ist 'leere Feldmenge' von "
            "'keine Aussage' nicht zu unterscheiden, und die Zusage waere leer wahr."
        )
    rest = treffer.group("rest")
    if "—" not in rest:
        raise ValueError(
            f"Die {AUSWERTUNGSGRENZE}-Zeile fuehrt keinen Gedankenstrich. Die Katalogform ist "
            "'<Feldmenge> — <Erlaeuterung>'; ohne den Strich ist Feldmenge nicht von "
            "Erlaeuterung zu trennen."
        )
    return tuple(_BACKTICK_TOKEN.findall(rest.split("—")[0]))


def vorkommen(abbild: Mapping[str, str], zeichenkette: str) -> list[str]:
    """Reine Funktion: je Datei mit Fundstelle `<datei> (<n>x)`.

    Ein leerer Suchraum ist ein Fehlerfall mit eigener Meldung, kein stiller Nullbefund.
    """
    if not abbild:
        raise ValueError(
            "0 Dateien im Suchraum: Ein leerer Suchraum darf nie als 'genau einmal gefunden' "
            "durchgehen."
        )
    return [
        f"{name} ({inhalt.count(zeichenkette)}x)"
        for name, inhalt in sorted(abbild.items())
        if zeichenkette in inhalt
    ]


def gesamtzahl(abbild: Mapping[str, str], zeichenkette: str) -> int:
    """Reine Funktion: die Summe aller Vorkommen im Suchraum."""
    if not abbild:
        raise ValueError(
            "0 Dateien im Suchraum: Ein leerer Suchraum darf nie als 'genau einmal gefunden' "
            "durchgehen."
        )
    return sum(inhalt.count(zeichenkette) for inhalt in abbild.values())


def definitionsstellen(abbild: Mapping[str, str], ueberschrift: str) -> list[str]:
    """Reine Funktion: Dateien, die `ueberschrift` **in einem Codeblock** fuehren.

    Ein umzaeunter Block ist eine Definition - er zeigt die Form. Eine Erwaehnung als Inline-Code
    ist ein Verweis und zaehlt hier ausdruecklich nicht mit.
    """
    if not abbild:
        raise ValueError(
            "0 Dateien im Suchraum: Ein leerer Suchraum darf nie als 'genau eine "
            "Definitionsstelle' durchgehen."
        )
    return [
        name
        for name, inhalt in sorted(abbild.items())
        if any(ueberschrift in block for block in codebloecke(inhalt))
    ]


def offset(text: str, literal: str) -> int:
    """Reine Funktion: der Zeichenoffset eines Literals; -1, wenn es fehlt."""
    return text.find(literal)


# --- Selbstschutz --------------------------------------------------------------------------


def test_der_suchraum_hat_eine_plausible_groesse() -> None:
    dateien = suchraum()

    assert len(dateien) >= MINDESTZAHL_DATEIEN_IM_SUCHRAUM, (
        f"Nur {len(dateien)} Dateien im Suchraum (erwartet: mindestens "
        f"{MINDESTZAHL_DATEIEN_IM_SUCHRAUM}). Die Aufzaehlung ist kaputt; die "
        "Einmaligkeitszusage waere dann bedeutungslos."
    )


@pytest.mark.parametrize("pfad", TRAGENDE_DATEIEN)
def test_jede_tragende_datei_liegt_im_suchraum_und_ist_plausibel_gross(pfad: str) -> None:
    """Ohne diesen Waechter prueft der Test einen Raum, in dem sein Gegenstand nicht vorkommt."""
    dateien = suchraum()

    assert pfad in dateien, (
        f"{pfad} liegt nicht im Suchraum. Dann sagt jede Mengenaussage dieses Tests ueber diese "
        "Datei nichts - und ihr Wegfall faellt nirgends auf."
    )
    assert len(dateien[pfad]) >= MINDESTLAENGE[pfad], (
        f"{pfad} hat nur {len(dateien[pfad])} Zeichen (erwartet: mindestens "
        f"{MINDESTLAENGE[pfad]}). Entweder ist die Datei verstuemmelt, oder der Leser liest die "
        "falsche."
    )


@pytest.mark.parametrize(
    "ueberschrift", sorted({m for marken in ABLAUF_MARKEN.values() for m in marken})
)
def test_jede_ueberschrift_eines_offsetvergleichs_existiert(ueberschrift: str) -> None:
    """Sonst bestuenden die Platzierungsvergleiche nach der naechsten Umbenennung leer."""
    gefunden = [pfad for pfad in ABLAUF_MARKEN if ueberschrift in dateitext(pfad)]

    assert gefunden, (
        f"Die Ueberschrift {ueberschrift!r} steht in keinem der beiden Ablauf-Skills. Wandert "
        "der Inhalt woandershin, wandert die Zusicherung mit - still darf sie nicht ausfallen."
    )


# --- 1./2. Kardinalitaet und Platzierung des Wartepunkts ----------------------------------


@pytest.mark.parametrize("pfad", sorted(ABLAUF_MARKEN))
def test_jeder_ablauf_nennt_den_wartepunkt_genau_einmal(pfad: str) -> None:
    """„Genau ein Wartepunkt je Ablauf" - die pruefbare Fassung ist die Fundstellenzahl."""
    anzahl = dateitext(pfad).count(WARTEPUNKT)

    assert anzahl == 1, (
        f"{pfad} nennt {WARTEPUNKT} {anzahl}-mal, erwartet genau einmal. Ein zweiter Wartepunkt "
        "wartet auf einen Stand, den der naechste Push ohnehin ueberschreibt; null Wartepunkte "
        "heisst, der Ablauf trifft ueber den CI-Stand gar keine Aussage mehr."
    )


@pytest.mark.parametrize("pfad", sorted(ABLAUF_MARKEN))
def test_jeder_ablauf_holt_den_beleg_fuer_rot(pfad: str) -> None:
    """`rot` wird nie aus einem Exit-Code allein geschlossen - der Beleg braucht die Leseoperation."""
    assert BELEG_OPERATION in dateitext(pfad), (
        f"{pfad} nennt {BELEG_OPERATION} nicht. Exit `1` von `gh` ist zweideutig (Fehlschlag vs. "
        "'noch kein Check gemeldet'); ohne den Beleg aus dieser Operation entstuende `rot` aus "
        "einem Exit-Code allein, und der Ablauf besserte an einem Lauf nach, der gar nicht "
        "fehlgeschlagen ist."
    )


@pytest.mark.parametrize("pfad", sorted(ABLAUF_MARKEN))
def test_der_wartepunkt_steht_nach_dem_letzten_push_und_vor_dem_bericht(pfad: str) -> None:
    """Platzierung ueber Zeichenoffsets statt ueber eine Formulierung."""
    text = dateitext(pfad)
    vorher, nachher = ABLAUF_MARKEN[pfad]

    vor = offset(text, vorher)
    punkt = offset(text, WARTEPUNKT)
    nach = offset(text, nachher)

    assert -1 not in (vor, punkt, nach), (
        f"{pfad}: Eine der drei Marken fehlt (Offsets: {vorher!r} {vor}, Wartepunkt {punkt}, "
        f"{nachher!r} {nach})."
    )
    assert vor < punkt < nach, (
        f"{pfad}: Die Reihenfolge stimmt nicht ({vorher!r} {vor}, Wartepunkt {punkt}, "
        f"{nachher!r} {nach}). Gewartet wird nach dem letzten Push des Laufs - frueher kostete "
        "es Wartezeit fuer ein Ergebnis, das der naechste Push ueberschreibt - und vor dem "
        "Bericht, weil der Bericht den Endstand fuehrt."
    )


# --- 3. Die eine Befehlszeile -------------------------------------------------------------


def test_die_pruefstands_befehlszeilen_halten_ihre_form() -> None:
    befunde = form_befunde(befehlszeilen(katalogtext()))

    assert not befunde, "Formverstoss/-verstoesse der Pruefstands-Befehlszeilen: " + "; ".join(
        befunde
    )


def test_die_befehlszeilen_stehen_ausschliesslich_im_katalog() -> None:
    """ADR 0061: Der Katalog ist der einzige Ort, an dem ein GitHub-Befehl steht."""
    abbild = suchraum()
    traeger = sorted(name for name, inhalt in abbild.items() if _PRUEFSTAND_BEFEHL.search(inhalt))

    assert traeger == [KATALOG], (
        f"Der Pruefstands-Befehl steht in {traeger}, erwartet ausschliesslich in {KATALOG}. Ein "
        "Ablauf-Skill nennt die Operations-ID, nie die Befehlsform - sonst gibt es zwei "
        "Wahrheiten ueber denselben Aufruf."
    )


# --- 4. Das geschlossene Ergebnisvokabular -------------------------------------------------


def test_das_ergebnisvokabular_ist_geschlossen_und_vollstaendig() -> None:
    """Gleichheit, nicht Teilmenge: Ein fuenfter Wert faellt auf, ein verschwundener auch."""
    werte = ergebniswerte(katalogtext())

    assert werte == ERWARTETE_ERGEBNISWERTE, (
        f"Ergebnisvokabular {list(werte)} statt {list(ERWARTETE_ERGEBNISWERTE)}. Es ist "
        "geschlossen und vierwertig: `gruen` entsteht ausschliesslich aus Exit 0, `rot` nie aus "
        "einem Exit-Code allein, und jeder nicht zugeordnete Fall ist `unbestimmt` und haelt den "
        "Ablauf an. Faellt `unbestimmt` weg, faellt die Fail-Closed-Zusage mit ihm."
    )


# --- 5. Die Einmaligkeit jeder Betriebszahl ------------------------------------------------


@pytest.mark.parametrize("zahl", BETRIEBSZAHLEN)
def test_jede_betriebszahl_kommt_im_anweisungsraum_genau_einmal_vor(zahl: str) -> None:
    """Was es nur einmal gibt, kann nicht driften - deshalb Einmaligkeit statt Gleichheit."""
    abbild = suchraum()
    stellen = vorkommen(abbild, zahl)

    assert stellen == [f"{KATALOG} (1x)"], (
        f"Die Betriebszahl {zahl!r} steht an {stellen} statt ausschliesslich einmal in "
        f"{KATALOG}. Eine zweite Fassung driftet; laeuft ein Fenster regelmaessig ab, obwohl der "
        "Lauf gesund ist, wird die Zahl an ihrer einen Stelle erhoeht, nicht je Ablauf."
    )
    assert gesamtzahl(abbild, zahl) == 1


# --- 6. Die beiden Feldmengen --------------------------------------------------------------


@pytest.mark.parametrize("operation", sorted(ERWARTETE_FELDMENGEN))
def test_jede_pruefstands_operation_haelt_ihre_feldmenge_exakt(operation: str) -> None:
    """Exakt, nicht "mindestens" - und fuer den blockierenden Aufruf ist die Zusage die **leere**
    Menge.

    Eine Auswertungsgrenze ohne ein einziges Feld gibt es im Katalog sonst nirgends. Sie ist
    nicht die Auslassung einer Zeile, sondern ihre Aussage: Aus dem blockierenden Aufruf wird
    ausschliesslich der Ergebniswert gelesen, seine Ausgabe wird verworfen. Stuende dort ein
    Feldname, waere aus dem Aufruf, der bewusst nichts liest, einer geworden, der liest - und
    zwar an der Stelle des Ablaufs, die unmittelbar danach Code aendert und pusht.
    """
    felder = ausgewertete_felder(eintragsblock(katalogtext(), operation))

    assert felder == ERWARTETE_FELDMENGEN[operation], (
        f"{operation}: Auswertungsgrenze {list(felder)} statt "
        f"{list(ERWARTETE_FELDMENGEN[operation])}."
    )


# --- 7. Je eine Definitionsstelle ----------------------------------------------------------


def test_der_berichtsblock_ist_ausschliesslich_im_katalog_definiert() -> None:
    stellen = definitionsstellen(suchraum(), BERICHTSBLOCK)

    assert stellen == [KATALOG], (
        f"Der Berichtsblock {BERICHTSBLOCK!r} wird in {stellen} als Format-Block gefuehrt, "
        f"erwartet ausschliesslich in {KATALOG}. Zwei Abbilder desselben Formats driften; beide "
        "Ablaeufe verweisen ueber die Ueberschrift, ohne die Feldnamen zu wiederholen."
    )


@pytest.mark.parametrize("feld", BERICHTSBLOCK_FELDER)
def test_die_definition_des_berichtsblocks_fuehrt_alle_drei_felder(feld: str) -> None:
    """Was nicht dasteht, schreibt der Lauf auch nicht."""
    bloecke = [block for block in codebloecke(katalogtext()) if BERICHTSBLOCK in block]

    assert len(bloecke) == 1, (
        f"{KATALOG} fuehrt {len(bloecke)} umzaeunte Bloecke mit {BERICHTSBLOCK!r}, erwartet "
        "genau einen."
    )
    assert feld in bloecke[0], (
        f"Das Feld {feld!r} fehlt in der Definition von {BERICHTSBLOCK!r}. Der Block traegt den "
        "Endstand, die Zahl der Nachbesserungsrunden und die Art je Runde - fehlt eines, ist der "
        "Bericht ueber den CI-Stand unvollstaendig, ohne dass etwas rot wird."
    )


@pytest.mark.parametrize("pfad", sorted(ABLAUF_MARKEN))
def test_beide_ablaeufe_fuehren_den_berichtsblock(pfad: str) -> None:
    assert BERICHTSBLOCK in dateitext(pfad), (
        f"{pfad} nennt {BERICHTSBLOCK!r} nicht. Der Block ist die einzige Stelle, an der ein "
        "abgeschlossener Lauf eine Aussage ueber den CI-Stand traegt."
    )


@pytest.mark.parametrize("anker", NEUE_ANKER)
def test_beide_anker_stehen_wortgleich_in_developer_md(anker: str) -> None:
    assert anker in dateitext(DEVELOPER), (
        f"Der Anker {anker!r} fehlt in {DEVELOPER}. Er ist der verbindliche Uebergabepunkt an "
        "den Orchestrator; ohne ihn bleibt die Nachbesserung unbemerkt."
    )


@pytest.mark.parametrize("anker", NEUE_ANKER)
def test_die_ankerdefinition_steht_ausschliesslich_in_developer_md(anker: str) -> None:
    """Einzige Definitionsstelle - `ship-feature` verweist funktional, kopiert nicht."""
    stellen = definitionsstellen(suchraum(), anker)

    assert stellen == [DEVELOPER], (
        f"Der Anker {anker!r} wird in {stellen} als Format-Block gefuehrt. Zwei Abbilder "
        "desselben Formats driften; die Feldnamen stehen ausschliesslich in developer.md."
    )


@pytest.mark.parametrize("anker", NEUE_ANKER)
def test_ship_feature_nennt_beide_anker_in_seiner_trigger_liste(anker: str) -> None:
    """Ein Anker, den die Ausloeseliste nicht kennt, loest nichts aus."""
    text = dateitext(SHIP_FEATURE)
    schritt_null = text[offset(text, "## Schritt 0") : offset(text, "## Schritt 1")]

    assert anker in schritt_null, (
        f"Schritt 0 von ship-feature kennt den Anker {anker!r} nicht - eine developer-Antwort "
        "mit diesem Anker loeste den Skill dann nicht aus."
    )


# --- Gegenproben je Musterfamilie, an synthetischem Text -----------------------------------


def test_der_befehlserkenner_verwechselt_gh_pr_nicht_mit_gh_project() -> None:
    """`gh pr` ist ein Praefix von `gh project` - ohne Wortgrenze waere die Zaehlung falsch."""
    assert not _PRUEFSTAND_BEFEHL.search("gh project item-edit 8 --owner TheRealKoller")
    assert not _PRUEFSTAND_BEFEHL.search("gh pr view 42 --json checks")
    assert _PRUEFSTAND_BEFEHL.search("gh pr checks 42 --repo TheRealKoller/photosort")


def test_eine_erwaehnung_im_fliesstext_ist_keine_befehlszeile() -> None:
    """Die geforderte Nicht-Reaktion: Der Katalog darf ueber seinen eigenen Befehl reden."""
    text = "Der Aufruf `gh pr checks` wartet bis zum Endstand.\n\nEin zweiter Absatz.\n"

    assert befehlszeilen(text) == []


_BLOCKIEREND = (
    "timeout 540 gh pr checks <MMM> --repo TheRealKoller/photosort "
    "--watch --fail-fast --interval 30 >/dev/null 2>&1"
)
_LESEND = f"gh pr checks <MMM> --repo TheRealKoller/photosort {LESE_MARKE}"


def _probe(*zeilen: str) -> str:
    return "```bash\n" + "\n".join(zeilen) + "\n```\n"


def test_die_erwartete_befehlsform_gilt_nicht_als_verstoss() -> None:
    assert form_befunde(befehlszeilen(_probe(_BLOCKIEREND, _LESEND))) == []


@pytest.mark.parametrize(
    ("bezeichnung", "zeilen"),
    [
        ("ohne --watch", (_BLOCKIEREND.replace(" --watch", ""), _LESEND)),
        ("ohne --fail-fast", (_BLOCKIEREND.replace(" --fail-fast", ""), _LESEND)),
        ("ohne --interval 30", (_BLOCKIEREND.replace(" --interval 30", ""), _LESEND)),
        ("Vorgabeintervall", (_BLOCKIEREND.replace("--interval 30", "--interval 10"), _LESEND)),
        ("ohne timeout", (_BLOCKIEREND.replace("timeout 540 ", ""), _LESEND)),
        ("mit --required", (f"{_BLOCKIEREND} --required", _LESEND)),
        ("ohne Feldauswahl", (_BLOCKIEREND, _LESEND.replace(f" {LESE_MARKE}", ""))),
        ("fuenftes Feld", (_BLOCKIEREND, _LESEND.replace(LESE_MARKE, f"{LESE_MARKE},link"))),
        ("dritte Zeile", (_BLOCKIEREND, _LESEND, _LESEND)),
        ("keine Zeile", ()),
    ],
)
def test_jede_abweichung_der_befehlsform_wird_gemeldet(
    bezeichnung: str, zeilen: tuple[str, ...]
) -> None:
    """Gegenprobe je Bauregel - eine Nullmeldung oben ist sonst kein Befund, sondern ein Defekt."""
    assert form_befunde(befehlszeilen(_probe(*zeilen))), bezeichnung


_TABELLE = "\n".join(
    [
        ERGEBNIS_TABELLENKOPF,
        "|---|---|---|",
        "| `gruen` | Exit `0`, und sonst nichts | regulaer |",
        "| `rot` | Exit ≠ 0 **und** `pr-pruefstand-lesen` zeigt `bucket == fail` | Nachbesserung |",
        "| `laeuft-noch` | Exit `124` des `timeout`-Aufrufs, oder Exit `8` | erneut |",
        "| `unbestimmt` | alles andere | anhalten |",
        "",
        "Prosa danach, mit `unbestimmt` und `gruen` in Backticks.",
    ]
)


def test_der_tabellenleser_liest_ausschliesslich_die_erste_spalte() -> None:
    """Sonst zoege jedes Backtick-Wort der zweiten Spalte ins Vokabular."""
    assert ergebniswerte(_TABELLE) == ERWARTETE_ERGEBNISWERTE


def test_der_tabellenleser_endet_an_der_ersten_nicht_tabellenzeile() -> None:
    """Sonst zaehlte Prosa hinter der Tabelle mit."""
    werte = ergebniswerte(_TABELLE + "\n| `spaeter` | eine zweite Tabelle | nein |\n")

    assert werte == ERWARTETE_ERGEBNISWERTE


@pytest.mark.parametrize(
    ("bezeichnung", "mutiert"),
    [
        ("fuenfter Wert", _TABELLE.replace("| `rot` |", "| `fast-gruen` | x | y |\n| `rot` |")),
        ("verschwundener Wert", _TABELLE.replace("| `unbestimmt` | alles andere | anhalten |", "")),
        ("umbenannter Wert", _TABELLE.replace("`laeuft-noch`", "`pending`")),
    ],
)
def test_jede_mutation_des_vokabulars_faellt_auf(bezeichnung: str, mutiert: str) -> None:
    assert ergebniswerte(mutiert) != ERWARTETE_ERGEBNISWERTE, bezeichnung


def test_eine_fehlende_ergebnistabelle_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"Tabellenkopf"):
        ergebniswerte("### `pr-pruefstand-abwarten`\n\nNur Prosa.\n")


def test_eine_leere_feldmenge_ist_ein_ergebnis_eine_fehlende_zeile_ein_fehler() -> None:
    """Die Unterscheidung, an der die Zusage des blockierenden Aufrufs haengt."""
    leer = "**Auswertungsgrenze:** keine Felder — ausgewertet wird allein der Ergebniswert.\n"

    assert ausgewertete_felder(leer) == ()

    with pytest.raises(ValueError, match=r"Keine"):
        ausgewertete_felder("### `pr-pruefstand-abwarten`\n\nNur Prosa.\n")


def test_ein_feldname_in_der_leeren_grenze_faellt_auf() -> None:
    """Die einzige Abwesenheitszusage dieser Familie - auf einer Formzeile, nicht auf Prosa."""
    mit_feld = "**Auswertungsgrenze:** `bucket` — ausgewertet wird allein der Ergebniswert.\n"

    assert ausgewertete_felder(mit_feld) == ("bucket",)


def test_prosa_hinter_dem_gedankenstrich_zaehlt_nicht_zur_feldmenge() -> None:
    text = "**Auswertungsgrenze:** keine Felder — die Ausgabe wird mit `>/dev/null` verworfen.\n"

    assert ausgewertete_felder(text) == ()


def test_eine_grenzzeile_ohne_gedankenstrich_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"Gedankenstrich"):
        ausgewertete_felder("**Auswertungsgrenze:** `bucket`, `state`\n")


def test_der_eintragsleser_endet_an_der_naechsten_ueberschrift() -> None:
    """Ohne die Grenze zoege der Eintrag den Resttext der Datei in sich."""
    probe = "### `pr-pruefstand-abwarten`\nInhalt A\n\n### `pr-pruefstand-lesen`\nInhalt B\n"

    assert eintragsblock(probe, "pr-pruefstand-abwarten").strip() == "Inhalt A"
    assert eintragsblock(probe, "pr-pruefstand-lesen").strip() == "Inhalt B"


def test_ein_fehlender_eintrag_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"nicht gefunden"):
        eintragsblock("# Titel\n\nNur Prosa.\n", "pr-pruefstand-abwarten")


def test_der_definitionsleser_trennt_zaun_von_erwaehnung() -> None:
    """Eine dritte Datei, die den Block **zitiert**, ist keine zweite Definitionsstelle."""
    abbild = {
        KATALOG: f"```markdown\n{BERICHTSBLOCK}\n\n**Endstand:** <Wert>\n```\n",
        SHIP_FEATURE: f"Der Bericht führt den Block `{BERICHTSBLOCK}` (Form im Katalog).\n",
        DEVELOPER: f"Siehe auch {BERICHTSBLOCK} im Katalog.\n",
    }

    assert definitionsstellen(abbild, BERICHTSBLOCK) == [KATALOG]


def test_eine_zweite_definitionsstelle_wuerde_gemeldet() -> None:
    abbild = {
        KATALOG: f"```markdown\n{BERICHTSBLOCK}\n```\n",
        SHIP_ENTWURF: f"```markdown\n{BERICHTSBLOCK}\n```\n",
    }

    assert definitionsstellen(abbild, BERICHTSBLOCK) == [KATALOG, SHIP_ENTWURF]


@pytest.mark.parametrize(
    ("probe", "erwartet_gueltig"),
    [
        ("PUSH...WARTEN...BERICHT", True),
        ("WARTEN...PUSH...BERICHT", False),
        ("PUSH...BERICHT...WARTEN", False),
    ],
)
def test_der_offsetvergleich_unterscheidet_beide_richtungen(
    probe: str, erwartet_gueltig: bool
) -> None:
    """Gegenprobe zur Methodik selbst - sie ist die Zusicherung, nicht der Wortlaut."""
    vor, punkt, nach = (offset(probe, marke) for marke in ("PUSH", "WARTEN", "BERICHT"))

    assert (vor < punkt < nach) is erwartet_gueltig


def test_eine_zweite_fundstelle_einer_betriebszahl_wuerde_gemeldet() -> None:
    abbild = {KATALOG: "timeout 540\n", SHIP_FEATURE: "auch timeout 540\n"}

    assert vorkommen(abbild, "timeout 540") == [f"{KATALOG} (1x)", f"{SHIP_FEATURE} (1x)"]


def test_zwei_fundstellen_in_derselben_datei_werden_gezaehlt() -> None:
    """Eine Datei-Liste allein genuegt nicht: Auch zweimal in einer Datei ist zweimal."""
    abbild = {KATALOG: "timeout 540\nund noch einmal timeout 540\n"}

    assert vorkommen(abbild, "timeout 540") == [f"{KATALOG} (2x)"]
    assert gesamtzahl(abbild, "timeout 540") == 2


@pytest.mark.parametrize("leser", [vorkommen, gesamtzahl, definitionsstellen])
def test_ein_leerer_suchraum_scheitert_laut_statt_still(leser: object) -> None:
    with pytest.raises(ValueError, match=r"0 Dateien im Suchraum"):
        leser({}, "egal")  # type: ignore[operator]
