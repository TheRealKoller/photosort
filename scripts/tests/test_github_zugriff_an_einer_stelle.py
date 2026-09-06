"""Haelt fest, dass jeder GitHub-Zugriff des Ablaufs an genau einer Stelle steht.

Seit ADR 0059 gibt es dafuer einen einzigen Ort: `.claude/skills/github-access/SKILL.md`. Jede
andere Datei unter `.claude/**` und `CLAUDE.md` verweist ausschliesslich ueber die stabile
**Operations-ID** auf einen Zugriff, nie ueber einen Befehl oder einen Werkzeugnamen.

Die tragende Zusicherung dieser Datei ist damit eine **Abwesenheit** - und ein Abwesenheits-Test
ist per Konstruktion gruen, wenn er nichts sieht, auch dann, wenn er nichts sehen *kann*. Der
Aufwand liegt deshalb nicht im Muster, sondern im Selbstschutz (Testkonzept, Sektion
"Erweiterung fuer ADR 0059", Regel 3):

* **(a)** plausible Groessenordnung des Suchraums,
* **(b)** der erlaubte Ort *und* `CLAUDE.md` liegen nachweislich **im** Suchraum - `CLAUDE.md`
  liegt nicht unter `.claude/` und braucht einen zweiten Aufzaehlungszweig; ein stillschweigend
  nicht mitgelesenes `CLAUDE.md` ist der wahrscheinlichste Defekt dieses Tests,
* **(c)** eine Gegenprobe **je Musterfamilie** - eine Gegenprobe, die nur das `gh`-Muster belegt,
  sagt ueber `mcp__github__` nichts.

**Keine Zeilenanfangs-Verankerung.** Die Verankerung der Formpruefungen
(`test_issue_befehle_in_skills.py`, `test_board_befehle_in_skills.py`) existiert, um in einer
Datei, in der Befehle *legitim* sind, Aufruf von Erwaehnung zu trennen. Hier sind null Vorkommen
legitim; dieselbe Verankerung waere ein Loch. Am Bestand belegt sind genau zwei Formen, die eine
verankerte Suche durchliesse und die beide echte Verstoesse waeren: eine Prosa-Zeile, die mit
einem in Backticks gesetzten Kommandonamen *beginnt*, und eine Befehlsaufzaehlung mitten in einem
Fliesstext-Absatz.

**Das Muster ist generisch statt eine Verbliste.** Auflistender Lauf ueber den Suchraum vor der
Formulierung (Stand 2026-09-06, vor dem Umbau): `\\bgh [a-z][a-z-]*` liefert **88 Fundstellen in
12 Dateien** und genau **fuenf** Unterbefehlsformen (`gh issue` 18, `gh pr` 36, `gh api` 17,
`gh project` 15, `gh auth` 2) - und **null** Fliesstext-Fehlalarme, weil deutscher Fliesstext die
CLI als ``gh`` mit anliegendem Backtick schreibt (``gh``-Weg, ``gh``-Aufrufe), nie als "gh " plus
Kleinbuchstabe. Der Messwert steht hier, damit die naechste Aenderung ihn **nachrechnet** statt
ihn zu glauben. Eine Verbliste waere zudem loechrig: `gh auth status` ist exakt die von ADR 0059
verbotene Vorabmessung und entginge einer Alternation aus `issue|pr|project|api`.

**Regex-Falle derselben Klasse wie `--body`/`--body-file`:** `gh pr` ist ein Praefix von
`gh project`. Eine Alternation ohne Wortgrenze etikettierte jeden Board-Befehl als PR-Befehl -
die Aussage "ist ein GitHub-Aufruf" bliebe richtig, die Fundstellen-Meldung wuerde falsch.

Kein echtes `gh`, kein Netzwerk, keine MCP-Werkzeuge - gelesen werden ausschliesslich Dateien
dieses Repositories.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_WURZEL = Path(__file__).parents[2]

# Der eine erlaubte Ort. Jede andere Datei des Suchraums ist zugriffsfrei.
KATALOG = ".claude/skills/github-access/SKILL.md"

# `CLAUDE.md` liegt nicht unter `.claude/` - zweiter Aufzaehlungszweig, eigener Selbstschutz.
ZUSAETZLICHE_SUCHRAUM_DATEIEN = ("CLAUDE.md",)

# Selbstschutz (a): Eine kaputte Dateiaufzaehlung liesse den Test gruen werden, obwohl er nichts
# gesehen hat. Untergrenze bewusst weit unter dem Ist-Stand (22 Dateien) - sie faengt den
# Totalausfall, nicht jede geloeschte Datei.
MINDESTZAHL_DATEIEN_IM_SUCHRAUM = 15

_GH_AUFRUF = re.compile(r"\bgh (?P<unterbefehl>[a-z][a-z-]*)")
_MCP_WERKZEUG = re.compile(r"mcp__github__[a-z_]*")

# Nur fuer die *Meldung* gebraucht, nicht fuer die Erkennung (Vorbild: SCHREIBENDE_VERBEN in
# test_issue_befehle_in_skills.py). Ein unbekannter Unterbefehl ist entweder ein Tippfehler oder
# eine neue Befehlsform - beides gehoert in die Meldung, nicht in eine Filterliste.
BEKANNTE_UNTERBEFEHLE = frozenset({"issue", "pr", "project", "api", "auth"})

# --- Der Operationskatalog ---------------------------------------------------------------

# Die 17 Operations-IDs aus ADR 0059, Abschnitt 2, als geschlossene Menge. Der
# Buchhaltungs-Vorbehalt gegen Konstantenvergleiche gilt hier ausdruecklich nicht: Die Menge
# selbst *ist* die Zusage ("keine heute vorhandene Operation geht verloren"), und ihr stiller
# Verlust beim Umzug der sechs PR-Operationen aus `ship-feature` ist genau der Fehler, den die
# Story riskiert.
ERWARTETE_OPERATIONEN = frozenset(
    {
        "issue-anlegen",
        "issue-lesen",
        "issue-body-schreiben",
        "issue-titel-schreiben",
        "issue-kommentieren",
        "issue-verwerfen",
        "pr-erstellen",
        "pr-body-schreiben",
        "pr-verknuepfung-lesen",
        "copilot-review-anfordern",
        "pr-reviewstand-lesen",
        "pr-reviewkommentare-lesen",
        "pr-reviewkommentar-beantworten",
        "board-aufnahme",
        "board-status-setzen",
        "board-prioritaet-setzen",
        "board-status-und-prioritaet-lesen",
    }
)

# Projects (V2) spricht ausschliesslich GraphQL; eine REST-Entsprechung existiert nicht, und die
# MCP-Werkzeuge bieten dafuer keine Operation an. Diese vier haben deshalb genau einen Weg.
BOARD_OPERATIONEN = frozenset(
    {
        "board-aufnahme",
        "board-status-setzen",
        "board-prioritaet-setzen",
        "board-status-und-prioritaet-lesen",
    }
)

# Die drei *schreibenden* Board-Operationen. Nur sie hinterlassen bei einem Fehlschlag einen
# nachzuziehenden Zustand und tragen deshalb eine Nachhol-Zeile in `gh`-Form.
BOARD_SCHREIBOPERATIONEN = frozenset(
    {"board-aufnahme", "board-status-setzen", "board-prioritaet-setzen"}
)

LESENDE_OPERATIONEN = frozenset(
    {
        "issue-lesen",
        "pr-verknuepfung-lesen",
        "pr-reviewstand-lesen",
        "pr-reviewkommentare-lesen",
        "board-status-und-prioritaet-lesen",
    }
)

# Die eine Operation, fuer die kein MCP-Werkzeug belegt ist. Sie wird ausdruecklich als unbelegt
# gefuehrt statt mit einem geratenen Namen aufgefuellt: Ein unbelegter Weg im Katalog scheiterte
# still und verschoebe die Diagnose.
UNBELEGT = "pr-reviewkommentar-beantworten"
UNBELEGT_MARKIERUNG = "`mcp` unbelegt"

WEGE_VOKABULAR = ("mcp", "gh")

# Woertliche Kennzeichnung der Board-Operationen - als Eigenschaft der Umgebung, nicht als offene
# Aufgabe.
REMOTE_MARKIERUNG = "remote auf keinem Weg erreichbar"

# `owner`/`repo` stehen auf jedem Weg als Literal im Katalogtext. Auf dem `mcp`-Weg sind sie
# Pflichtparameter ohne Rueckfallwert - der stille Vorgabewert "Repository des
# Arbeitsverzeichnisses" entfaellt mit dem Wegwechsel.
ZIEL_LITERAL = "`owner` = `TheRealKoller`, `repo` = `photosort`"

AUSWERTUNGSGRENZE = "**Auswertungsgrenze:**"

_EINTRAG_KOPF = re.compile(r"^### `(?P<id>[^`\n]+)`", re.MULTILINE)
# Ein Eintragsblock endet an der naechsten Operation **oder** am naechsten `##`-Abschnitt. Ohne
# die zweite Grenze zoege der letzte Eintrag den gesamten Resttext der Datei in seinen Block und
# bestuende jede Block-Zusicherung (Ziel-Literal, Auswertungsgrenze, Nachhol-Zeile) zufaellig.
_ABSCHNITT = re.compile(r"^## ", re.MULTILINE)
_WEGE_ZEILE = re.compile(r"^\*\*Wege:\*\*(?P<rest>[^\n]*)$", re.MULTILINE)
_WEG_TOKEN = re.compile(r"`([a-z]+)`")
_KEBAB = re.compile(r"^[a-z]+(?:-[a-z]+)+$")

# --- Verweise auf Operationen ------------------------------------------------------------

# Erkennungsraum sind die vier geschlossenen Praefixe. Sie sind im Repository fuer nichts anderes
# belegt und tragen deshalb die Erkennung; ohne eine solche Namensraum-Regel gaelten `review-
# tests`, `ship-feature` oder `body-file` als Operationen. Der Namensraum ist damit reserviert:
# Wer ein anderes Kebab-Wort mit einem dieser Praefixe in Backticks setzt, wird hier rot - das ist
# gewollt, nicht durch eine Ausnahmeliste aufzuweichen.
ID_PRAEFIXE = ("issue-", "board-", "pr-", "copilot-")
_ID_VERWENDUNG = re.compile(r"`((?:issue|board|pr|copilot)-[a-z][a-z-]*)`")

# --- Erlaubnisstufen ---------------------------------------------------------------------

STUFE_MARKER = "**GitHub-Erlaubnisstufe:**"
STUFE_SCHREIBEND = "lesend und schreibend"
STUFE_LESEND = "nur lesend"
STUFE_KEINE = "kein GitHub-Zugriff"
STUFEN = (STUFE_SCHREIBEND, STUFE_LESEND, STUFE_KEINE)

# Eingefrorene Erwartungstabelle. Verglichen wird sie gegen den **entdeckten** Bestand
# (`git ls-files -- .claude`), nicht gegen eine gepflegte Liste: Ein kuenftig neu angelegter Skill
# kann sich der Einstufung so nicht dadurch entziehen, dass niemand an die Liste denkt - er wird
# rot. Die fuenf Perspektiven-Skills tragen bewusst "kein GitHub-Zugriff" statt "nur lesend": Ein
# Recht, das keiner von ihnen braucht, wird auch nicht eingeraeumt.
ERWARTETE_STUFEN: dict[str, str] = {
    ".claude/agents/architect.md": STUFE_KEINE,
    ".claude/agents/developer.md": STUFE_KEINE,
    ".claude/agents/requirements-engineer.md": STUFE_KEINE,
    ".claude/agents/research-engineer.md": STUFE_KEINE,
    ".claude/agents/security-engineer.md": STUFE_KEINE,
    ".claude/agents/test-engineer.md": STUFE_KEINE,
    ".claude/agents/ux-ui-designer.md": STUFE_KEINE,
    ".claude/skills/browse-app/SKILL.md": STUFE_KEINE,
    ".claude/skills/capture/SKILL.md": STUFE_SCHREIBEND,
    ".claude/skills/design-system/SKILL.md": STUFE_KEINE,
    ".claude/skills/github-access/SKILL.md": STUFE_SCHREIBEND,
    ".claude/skills/refinement/SKILL.md": STUFE_SCHREIBEND,
    ".claude/skills/review-architecture/SKILL.md": STUFE_KEINE,
    ".claude/skills/review-requirements/SKILL.md": STUFE_KEINE,
    ".claude/skills/review-security/SKILL.md": STUFE_KEINE,
    ".claude/skills/review-tests/SKILL.md": STUFE_KEINE,
    ".claude/skills/review-ux/SKILL.md": STUFE_KEINE,
    ".claude/skills/review/SKILL.md": STUFE_LESEND,
    ".claude/skills/ship-feature/SKILL.md": STUFE_SCHREIBEND,
    ".claude/skills/skiller/SKILL.md": STUFE_KEINE,
    ".claude/skills/spec-writer/SKILL.md": STUFE_SCHREIBEND,
}

# --- Schwacher Waechter gegen die Rueckkehr der Vorabmessung ------------------------------

# Bewusst **enumeriert** und je begruendet, kein freier Wortscan ueber "Cloud-Session"/"remote" -
# das waere Formulierungspolizei mit Falschmeldungen. Der Waechter ist ausdruecklich schwach: Er
# faengt die bekannten Mittel einer Vorabmessung, nicht die Eigenschaft "es wird nicht gemessen"
# (eine Laufzeiteigenschaft ohne Testgegenstand). Eine repo-seitige Gegenprobe hat er
# naturgemaess nicht - null legitime Vorkommen -, sein Positivfall ist deshalb synthetisch.
MESSBEGRIFFE = (
    "gh auth status",  # Probe-Aufruf, dessen einziger Zweck die Vorabmessung ist
    "gh api rate_limit",  # "antwortet GitHub ueberhaupt?" - dasselbe unter anderem Namen
    "CODESPACES",  # Schluss von einem Umgebungsmerkmal auf eine "Session-Art"
    "GITHUB_ACTIONS",  # dito
    "GH_TOKEN",  # dito, plus: eine Token-Variable gehoert nirgends in eine Anweisung
)


@dataclass(frozen=True)
class Fund:
    """Ein einzelnes Vorkommen eines GitHub-Zugriffs, so wie es in einer Datei steht."""

    datei: str
    zeile: int
    text: str
    familie: str

    @property
    def fundstelle(self) -> str:
        return f"{self.datei}:{self.zeile}"


def funde_aus_text(text: str, datei: str = "<text>") -> list[Fund]:
    """Reine Funktion: sammelt beide Musterfamilien eines Textes samt Fundstelle.

    Unverankert - im geprueften Raum ist **kein** Vorkommen legitim, auch keines mitten in einer
    Prosa-Zeile oder in Backticks am Zeilenanfang.
    """
    funde: list[Fund] = []
    for treffer in _GH_AUFRUF.finditer(text):
        funde.append(
            Fund(
                datei=datei,
                zeile=text.count("\n", 0, treffer.start()) + 1,
                text=treffer.group(0),
                familie="gh",
            )
        )
    for treffer in _MCP_WERKZEUG.finditer(text):
        funde.append(
            Fund(
                datei=datei,
                zeile=text.count("\n", 0, treffer.start()) + 1,
                text=treffer.group(0),
                familie="mcp",
            )
        )
    return sorted(funde, key=lambda f: (f.zeile, f.familie, f.text))


def _meldung(fund: Fund) -> str:
    if fund.familie == "gh":
        unterbefehl = fund.text.split(" ", 1)[1]
        zusatz = (
            ""
            if unterbefehl in BEKANNTE_UNTERBEFEHLE
            else " (unbekannter Unterbefehl - Tippfehler, oder dieser Test ist mitzuziehen)"
        )
        return f"{fund.fundstelle}: `{fund.text}`{zusatz}"
    return f"{fund.fundstelle}: `{fund.text}`"


def zugriffe_ausserhalb_des_katalogs(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: meldet jeden GitHub-Zugriff ausserhalb von `KATALOG`.

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
        if datei == KATALOG:
            continue
        befunde.extend(_meldung(fund) for fund in funde_aus_text(abbild[datei], datei))
    return befunde


def messbegriffe_im_abbild(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: meldet jedes Vorkommen eines enumerierten Messbegriffs.

    Ohne Ausnahme fuer `KATALOG`: Auch dort wird nicht vorab gemessen.
    """
    befunde: list[str] = []
    for datei in sorted(abbild):
        for nummer, zeile in enumerate(abbild[datei].split("\n"), start=1):
            for begriff in MESSBEGRIFFE:
                if begriff in zeile:
                    befunde.append(f"{datei}:{nummer}: {begriff!r}")
    return befunde


@dataclass(frozen=True)
class Katalogeintrag:
    """Eine Operation des Katalogs: ihre ID, ihre geordneten Wege und ihr Textblock."""

    id: str
    wege: tuple[str, ...]
    block: str


def katalog_aus_text(text: str) -> list[Katalogeintrag]:
    """Reine Funktion: liest die Operationen aus dem Katalogtext.

    Ein Eintrag ist eine `### `<id>``-Ueberschrift; sein Block reicht bis zur naechsten. Die
    Wege stehen in einer eigenen Zeile `**Wege:** `mcp`, `gh`` - eine feste, maschinell lesbare
    Form statt Prosa, weil "in dieser Reihenfolge" sonst nicht pruefbar waere.
    """
    koepfe = list(_EINTRAG_KOPF.finditer(text))
    if not koepfe:
        raise ValueError(
            "0 Katalogeintraege gefunden. Entweder ist der Katalog leer, oder seine "
            "Eintragsform hat sich geaendert - dann ist dieser Test mitzuziehen, sonst prueft "
            "er lautlos nichts mehr."
        )

    eintraege: list[Katalogeintrag] = []
    for nummer, kopf in enumerate(koepfe):
        grenzen = [len(text)]
        if nummer + 1 < len(koepfe):
            grenzen.append(koepfe[nummer + 1].start())
        naechster_abschnitt = _ABSCHNITT.search(text, kopf.end())
        if naechster_abschnitt:
            grenzen.append(naechster_abschnitt.start())
        block = text[kopf.start() : min(grenzen)]
        wege_zeile = _WEGE_ZEILE.search(block)
        wege = (
            tuple(_WEG_TOKEN.findall(wege_zeile.group("rest"))) if wege_zeile else ()
        )
        eintraege.append(Katalogeintrag(id=kopf.group("id"), wege=wege, block=block))
    return eintraege


def form_verstoesse(eintraege: list[Katalogeintrag]) -> list[str]:
    """Reine Funktion: prueft ID-Form, Wege-Vokabular und die feste Reihenfolge."""
    befunde: list[str] = []
    for eintrag in eintraege:
        if not _KEBAB.match(eintrag.id):
            befunde.append(f"{eintrag.id!r}: keine kebab-case-ID.")
        unbekannt = [weg for weg in eintrag.wege if weg not in WEGE_VOKABULAR]
        if unbekannt:
            befunde.append(
                f"{eintrag.id}: unbekannte(r) Weg(e) {unbekannt}. Das Vokabular ist "
                f"geschlossen: {list(WEGE_VOKABULAR)}."
            )
        if not eintrag.wege:
            befunde.append(
                f"{eintrag.id}: keine Wege genannt. Jede Operation nennt ihre Wege als "
                "geordnete Liste - eine Operation ohne Weg ist nicht ausfuehrbar."
            )
        if len(set(eintrag.wege)) != len(eintrag.wege):
            befunde.append(f"{eintrag.id}: derselbe Weg mehrfach genannt ({list(eintrag.wege)}).")
        if "mcp" in eintrag.wege and "gh" in eintrag.wege:
            if eintrag.wege.index("mcp") > eintrag.wege.index("gh"):
                befunde.append(
                    f"{eintrag.id}: `gh` steht vor `mcp`. Wo beide Wege existieren, steht "
                    "`mcp` vorn (ADR 0059, Abschnitt 2)."
                )
        if eintrag.id in BOARD_OPERATIONEN and eintrag.wege != ("gh",):
            befunde.append(
                f"{eintrag.id}: Wege {list(eintrag.wege)} statt genau ['gh']. Projects (V2) "
                "spricht ausschliesslich GraphQL; es gibt dort keinen zweiten Weg."
            )
        if eintrag.id in BOARD_OPERATIONEN and REMOTE_MARKIERUNG not in eintrag.block:
            befunde.append(
                f"{eintrag.id}: fuehrt die woertliche Kennzeichnung {REMOTE_MARKIERUNG!r} "
                "nicht. Ohne sie erscheint eine Eigenschaft der Umgebung als offene Aufgabe."
            )
        if eintrag.id == UNBELEGT and UNBELEGT_MARKIERUNG not in eintrag.block:
            befunde.append(
                f"{eintrag.id}: fuehrt die woertliche Markierung {UNBELEGT_MARKIERUNG!r} nicht. "
                "Ein unbelegter Weg wird ausgewiesen, nie mit einem geratenen Werkzeugnamen "
                "aufgefuellt."
            )
        if ZIEL_LITERAL not in eintrag.block:
            befunde.append(
                f"{eintrag.id}: nennt {ZIEL_LITERAL} nicht. Auf dem `mcp`-Weg sind owner/repo "
                "Pflichtparameter ohne Rueckfallwert - der stille Vorgabewert 'Repository des "
                "Arbeitsverzeichnisses' entfaellt."
            )
        if eintrag.id in LESENDE_OPERATIONEN and AUSWERTUNGSGRENZE not in eintrag.block:
            befunde.append(
                f"{eintrag.id}: nennt keine {AUSWERTUNGSGRENZE} Jede lesende Operation nennt "
                "ihre Feldmenge als Obergrenze der Auswertung."
            )
    return befunde


def verwendete_ids(abbild: Mapping[str, str]) -> dict[str, list[str]]:
    """Reine Funktion: sammelt je verwendeter Operations-ID ihre Fundstellen."""
    fundstellen: dict[str, list[str]] = {}
    for datei in sorted(abbild):
        for nummer, zeile in enumerate(abbild[datei].split("\n"), start=1):
            for treffer in _ID_VERWENDUNG.finditer(zeile):
                fundstellen.setdefault(treffer.group(1), []).append(f"{datei}:{nummer}")
    return fundstellen


def stufen_verstoesse(abbild: Mapping[str, str], erwartung: Mapping[str, str]) -> list[str]:
    """Reine Funktion: jede Datei traegt **genau eine** Stufe, und zwar die erwartete.

    "Genau eine" statt "mindestens eine": Zwei Stufen in einer Datei sind ein Widerspruch und
    muessen laut auffallen, statt sich gegenseitig zu verdecken.
    """
    befunde: list[str] = []
    for datei in sorted(erwartung):
        if datei not in abbild:
            befunde.append(f"{datei}: erwartet, aber nicht im entdeckten Bestand.")
            continue
        text = abbild[datei]
        getragen = [stufe for stufe in STUFEN if f"{STUFE_MARKER} {stufe}" in text]
        if len(getragen) != 1:
            befunde.append(
                f"{datei}: traegt {len(getragen)} Erlaubnisstufen ({getragen}), erwartet genau "
                f"eine in der Form '{STUFE_MARKER} <Stufe>'."
            )
            continue
        if getragen[0] != erwartung[datei]:
            befunde.append(
                f"{datei}: traegt {getragen[0]!r}, erwartet {erwartung[datei]!r}."
            )
    return befunde


def eingestufte_dateien(abbild: Mapping[str, str]) -> list[str]:
    """Reine Funktion: der einstufungspflichtige Bestand - jede `SKILL.md`, jede Agenten-Datei."""
    return sorted(
        datei
        for datei in abbild
        if datei.endswith("/SKILL.md") or datei.startswith(".claude/agents/")
    )


def suchraum(wurzel: Path = REPO_WURZEL) -> dict[str, str]:
    """Duenner Leser: alles unter `.claude/` **plus** `CLAUDE.md`.

    Ueber `git ls-files` statt `rglob`, damit nicht verwaltete Arbeitskopien nicht in den
    Suchraum geraten. `CLAUDE.md` kommt als zweiter Zweig dazu - es liegt nicht unter `.claude/`
    und faellt sonst lautlos heraus.
    """
    ergebnis = subprocess.run(
        ["git", "ls-files", "-z", "--", ".claude", *ZUSAETZLICHE_SUCHRAUM_DATEIEN],
        cwd=wurzel,
        capture_output=True,
        check=True,
    )
    pfade = [pfad.decode("utf-8") for pfad in ergebnis.stdout.split(b"\0") if pfad]
    return {pfad: (wurzel / pfad).read_text(encoding="utf-8") for pfad in pfade}


def katalogtext(wurzel: Path = REPO_WURZEL) -> str:
    """Duenner Leser fuer den einen erlaubten Ort."""
    return (wurzel / KATALOG).read_text(encoding="utf-8")


# --- Selbstschutz ------------------------------------------------------------------------


def test_der_suchraum_hat_eine_plausible_groesse() -> None:
    """Selbstschutz (a): Eine kaputte Aufzaehlung darf nicht als Nullbefund durchgehen."""
    dateien = suchraum()

    assert len(dateien) >= MINDESTZAHL_DATEIEN_IM_SUCHRAUM, (
        f"Nur {len(dateien)} Dateien im Suchraum (erwartet: mindestens "
        f"{MINDESTZAHL_DATEIEN_IM_SUCHRAUM}). Die Aufzaehlung ist kaputt; ein Nullbefund dieses "
        "Tests waere dann bedeutungslos."
    )


def test_der_erlaubte_ort_liegt_im_suchraum() -> None:
    """Selbstschutz (b): Wird das Verzeichnis erneut umbenannt, meldet es dieser Test."""
    assert KATALOG in suchraum(), (
        f"{KATALOG} liegt nicht im Suchraum. Dann prueft der Abwesenheits-Test einen Raum, in "
        "dem der Katalog gar nicht vorkommt - und seine Nullmeldung sagt nichts."
    )


def test_claude_md_liegt_im_suchraum() -> None:
    """Selbstschutz (b), zweiter Zweig: `CLAUDE.md` liegt nicht unter `.claude/`."""
    dateien = suchraum()

    assert "CLAUDE.md" in dateien, (
        "CLAUDE.md fehlt im Suchraum. Es liegt nicht unter `.claude/` und braucht einen eigenen "
        "Aufzaehlungszweig - ein stillschweigend nicht mitgelesenes CLAUDE.md ist der "
        "wahrscheinlichste Defekt dieses Tests."
    )


def test_die_gegenprobe_traegt_je_musterfamilie() -> None:
    """Selbstschutz (c): Eine Gegenprobe nur fuer `gh` sagt ueber `mcp__github__` nichts."""
    funde = funde_aus_text(katalogtext(), KATALOG)
    familien = {fund.familie for fund in funde}

    assert "gh" in familien, (
        f"Das `gh`-Muster trifft nicht einmal in {KATALOG}. Dann ist die Nullmeldung des "
        "Abwesenheits-Tests kein Befund, sondern ein defektes Muster."
    )
    assert "mcp" in familien, (
        f"Das `mcp__github__`-Muster trifft nicht einmal in {KATALOG}. Ohne ein einziges "
        "Vorkommen im Repository ist dieses Muster nie ausgeuebt, und ein Tippfehler darin "
        "(`mcp_github_`) bliebe dauerhaft gruen."
    )


# --- Die eigentliche Zusicherung ---------------------------------------------------------


def test_kein_github_zugriff_ausserhalb_des_katalogs() -> None:
    befunde = zugriffe_ausserhalb_des_katalogs(suchraum())

    assert not befunde, (
        "GitHub-Zugriff ausserhalb von "
        f"{KATALOG}: {'; '.join(befunde)}. Andere Dateien verweisen ausschliesslich ueber die "
        "Operations-ID auf einen Zugriff - nie ueber einen Befehl oder einen Werkzeugnamen."
    )


def test_kein_messbegriff_im_suchraum() -> None:
    """Schwacher, ausdruecklich als schwach gefuehrter Waechter gegen die Vorabmessung."""
    befunde = messbegriffe_im_abbild(suchraum())

    assert not befunde, (
        f"Enumerierte(r) Messbegriff(e) gefunden: {'; '.join(befunde)}. Ein vorhandener Weg wird "
        "versucht, nie vorab beurteilt; aus keinem Umgebungsmerkmal wird auf eine Session-Art "
        "geschlossen."
    )


def test_der_katalog_fuehrt_genau_die_erwarteten_operationen() -> None:
    eintraege = katalog_aus_text(katalogtext())
    ids = [eintrag.id for eintrag in eintraege]

    doppelte = sorted({wert for wert in ids if ids.count(wert) > 1})
    assert not doppelte, f"Operation(en) mehrfach im Katalog: {doppelte}."
    assert set(ids) == ERWARTETE_OPERATIONEN, (
        f"Fehlend: {sorted(ERWARTETE_OPERATIONEN - set(ids))}; "
        f"unerwartet: {sorted(set(ids) - ERWARTETE_OPERATIONEN)}. Der Katalog ist geschlossen - "
        "keine heute vorhandene Operation geht verloren, und keine kommt unbemerkt dazu."
    )
    assert len(ids) == 17


def test_jede_operation_haelt_die_verbindliche_form() -> None:
    befunde = form_verstoesse(katalog_aus_text(katalogtext()))

    assert not befunde, "Katalog-Formverstoss/-verstoesse: " + "; ".join(befunde)


def test_der_katalog_nennt_mindestens_ein_mcp_werkzeug_literal() -> None:
    """Ohne ein einziges Vorkommen waere das `mcp__github__`-Muster nie ausgeuebt."""
    treffer = _MCP_WERKZEUG.findall(katalogtext())

    assert treffer, (
        "Der Katalog nennt keinen literalen `mcp__github__…`-Hinweis. Der `mcp`-Weg ist auf "
        "Operationsebene normiert, der beobachtete Werkzeugname steht als Hinweis daneben - "
        "ohne ihn fehlt die Gegenprobe fuer diese Musterfamilie."
    )


def test_keine_operation_liest_issue_kommentare() -> None:
    """Eigenschaft des Vokabulars, nicht eine Feldliste: Was es nicht gibt, ruft niemand auf."""
    eintraege = katalog_aus_text(katalogtext())

    mit_kommentaren = sorted(
        eintrag.id for eintrag in eintraege if "kommentare" in eintrag.id and "lesen" in eintrag.id
    )
    assert mit_kommentaren == ["pr-reviewkommentare-lesen"], (
        f"Kommentar-lesende Operation(en) im Katalog: {mit_kommentaren}. Einzige zulaessige "
        "Ausnahme ist `pr-reviewkommentare-lesen` - die Copilot-Findings am eigenen Pull "
        "Request."
    )

    fremde_grenzen = [
        eintrag.id
        for eintrag in eintraege
        if eintrag.id != "pr-reviewkommentare-lesen"
        for zeile in eintrag.block.split("\n")
        if zeile.startswith(AUSWERTUNGSGRENZE) and "omment" in zeile
    ]
    assert not fremde_grenzen, (
        f"Auswertungsgrenze mit Kommentar-Feld: {fremde_grenzen}. Kommentare sind der einzige "
        "Kanal, ueber den ein Dritter Text an ein bestehendes Issue anhaengen kann."
    )


def test_die_drei_schreibenden_board_operationen_fuehren_eine_nachhol_zeile() -> None:
    """Der Befehl zieht aus den vier Ablauf-Skills hierher - die Zusicherung wandert mit.

    Bewusst nur die drei *schreibenden*: Ein ausgebliebener Lesezugriff hinterlaesst keinen
    nachzuziehenden Zustand. `board-status-und-prioritaet-lesen` sagt das im Katalog
    ausdruecklich, statt eine sinnlose Zeile zu fuehren - siehe den folgenden Test.
    """
    eintraege = {eintrag.id: eintrag for eintrag in katalog_aus_text(katalogtext())}

    fehlend = []
    for operation in sorted(BOARD_SCHREIBOPERATIONEN):
        muster = re.compile(rf"^- `{re.escape(operation)}`: `gh project item-[a-z]+ ", re.MULTILINE)
        if not muster.search(eintraege[operation].block):
            fehlend.append(operation)

    assert not fehlend, (
        f"Ohne Nachhol-Zeile in `gh`-Form: {fehlend}. Nachdem die Befehlszeile aus den vier "
        "Ablauf-Skills hierher gezogen ist, ist dies der einzige Ort, an dem sie noch steht."
    )


def test_die_lesende_board_operation_begruendet_ihre_fehlende_nachhol_zeile() -> None:
    eintraege = {eintrag.id: eintrag for eintrag in katalog_aus_text(katalogtext())}

    assert "keine Nachhol-Zeile" in eintraege["board-status-und-prioritaet-lesen"].block, (
        "`board-status-und-prioritaet-lesen` fuehrt keine Nachhol-Zeile und sagt auch nicht, "
        "warum. Eine stille Auslassung ist von einer vergessenen Zeile nicht unterscheidbar."
    )


def test_jede_verwendete_operations_id_existiert_im_katalog() -> None:
    """Einseitig: Die Gegenrichtung wird ausdruecklich nicht geprueft.

    Operationen wie `issue-kommentieren` werden auf Zuruf gebraucht; eine beidseitige Pruefung
    zwaenge zum Ausduennen eines bewusst vollstaendigen Katalogs.
    """
    katalog_ids = {eintrag.id for eintrag in katalog_aus_text(katalogtext())}
    fundstellen = verwendete_ids(suchraum())

    unbekannt = {
        kennung: stellen
        for kennung, stellen in sorted(fundstellen.items())
        if kennung not in katalog_ids
    }
    assert not unbekannt, (
        f"Verweis(e) ins Leere: {unbekannt}. Die Praefixe {list(ID_PRAEFIXE)} sind fuer "
        "Operations-IDs reserviert - ein vertippter Verweis faellt sonst erst auf, wenn eine "
        "Story daran haengt."
    )


def test_der_erkennungsraum_findet_die_operationen_ueberhaupt() -> None:
    """Ein leerer Erkennungsraum liesse den Integritaetstest leer wahr werden."""
    fundstellen = verwendete_ids(suchraum())

    assert len(fundstellen) >= 10, (
        f"Nur {len(fundstellen)} verschiedene Operations-IDs im Suchraum gefunden. Entweder "
        "verweisen die Ablauf-Skills nicht mehr ueber IDs, oder der Erkennungsraum ist kaputt."
    )


def test_jede_skill_und_agenten_datei_traegt_genau_ihre_erlaubnisstufe() -> None:
    abbild = suchraum()
    entdeckt = eingestufte_dateien(abbild)

    assert entdeckt == sorted(ERWARTETE_STUFEN), (
        f"Der entdeckte Bestand weicht von der eingefrorenen Erwartungstabelle ab. Neu: "
        f"{sorted(set(entdeckt) - set(ERWARTETE_STUFEN))}; verschwunden: "
        f"{sorted(set(ERWARTETE_STUFEN) - set(entdeckt))}. Eine neue Datei kann sich der "
        "Einstufung nicht dadurch entziehen, dass niemand an die Tabelle denkt."
    )

    befunde = stufen_verstoesse(abbild, ERWARTETE_STUFEN)

    assert not befunde, "Erlaubnisstufen-Verstoss/-verstoesse: " + "; ".join(befunde)


def test_die_fuenf_perspektiven_skills_tragen_kein_github_zugriff() -> None:
    """Nicht "nur lesend": Ein Recht, das keiner von ihnen braucht, wird nicht eingeraeumt."""
    perspektiven = [
        f".claude/skills/review-{name}/SKILL.md"
        for name in ("architecture", "requirements", "security", "tests", "ux")
    ]

    assert [ERWARTETE_STUFEN[pfad] for pfad in perspektiven] == [STUFE_KEINE] * 5
    assert ERWARTETE_STUFEN[".claude/skills/review/SKILL.md"] == STUFE_LESEND


# --- Gegenproben an synthetischem Text ---------------------------------------------------


@pytest.mark.parametrize(
    "zeile",
    [
        "gh pr view 42 --json closingIssuesReferences",
        "Nicht erlaubt: `gh pr create` oder `gh pr merge`.",
        "  - `status-review`: `gh project item-edit 8 --owner TheRealKoller`",
        "`gh issue create` wird dafuer nicht wiederholt.",
        "Erst `gh auth status` abzusetzen ist genau die verbotene Vorabmessung.",
        "Ruf mcp__github__create_issue auf.",
        "Der Aufruf `mcp__github__get_issue` liefert mehr Felder als noetig.",
    ],
)
def test_ein_zugriff_wird_an_beliebiger_stelle_der_zeile_gefunden(zeile: str) -> None:
    """Unverankert: Beide am Bestand belegten Umgehungsformen muessen auffallen."""
    assert funde_aus_text(zeile + "\n", "skill.md")


@pytest.mark.parametrize(
    "zeile",
    [
        "Der `gh`-Weg ist der zweite.",
        "Hoechstens lesende `gh`-Aufrufe sind erlaubt.",
        "GitHub-Zugriff, gleich ueber welchen Weg.",
        "Fuehr `board-status-setzen` aus.",
        "Ein MCP-Werkzeug ist kein roher API-Aufruf.",
        "mcp_github_create_issue",
    ],
)
def test_prosa_ueber_den_zugriff_gilt_nicht_als_zugriff(zeile: str) -> None:
    """Deutscher Fliesstext schreibt die CLI mit anliegendem Backtick, nie als 'gh ' plus Wort."""
    assert funde_aus_text(zeile + "\n", "skill.md") == []


def test_gh_pr_wird_nicht_mit_gh_project_verwechselt() -> None:
    """`gh pr` ist ein Praefix von `gh project` - ohne Wortgrenze waere die Meldung falsch."""
    funde = funde_aus_text("gh project item-edit 8\ngh pr view 42\n", "skill.md")

    assert [fund.text for fund in funde] == ["gh project", "gh pr"]


def test_der_katalog_selbst_wird_uebergangen() -> None:
    abbild = {KATALOG: "gh pr view 42\nmcp__github__get_pull_request\n"}

    assert zugriffe_ausserhalb_des_katalogs(abbild) == []


def test_eine_andere_datei_wird_nicht_uebergangen() -> None:
    abbild = {
        KATALOG: "gh pr view 42\n",
        ".claude/skills/review/SKILL.md": "Text\ngh pr merge 42\n",
    }

    befunde = zugriffe_ausserhalb_des_katalogs(abbild)

    assert len(befunde) == 1
    assert befunde[0].startswith(".claude/skills/review/SKILL.md:2:")


def test_ein_unbekannter_unterbefehl_wird_als_solcher_gemeldet() -> None:
    befunde = zugriffe_ausserhalb_des_katalogs({"CLAUDE.md": "gh repo clone x\n"})

    assert len(befunde) == 1
    assert "unbekannter Unterbefehl" in befunde[0]


def test_ein_leerer_suchraum_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Dateien"):
        zugriffe_ausserhalb_des_katalogs({})


def test_ein_katalog_ohne_eintrag_scheitert_laut_statt_still() -> None:
    with pytest.raises(ValueError, match=r"0 Katalogeintraege"):
        katalog_aus_text("# Ueberschrift\n\nNur Prosa.\n")


@pytest.mark.parametrize("begriff", MESSBEGRIFFE)
def test_jeder_enumerierte_messbegriff_wird_gefunden(begriff: str) -> None:
    """Positivfall synthetisch - im Repository gibt es null legitime Vorkommen."""
    befunde = messbegriffe_im_abbild({".claude/skills/x/SKILL.md": f"Vorher {begriff} nachher\n"})

    assert befunde == [f".claude/skills/x/SKILL.md:1: {begriff!r}"]


_BLOCK = (
    "### `{id}` — Beschreibung\n\n"
    "**Wege:** {wege}\n"
    f"**Ziel (auf jedem Weg als Literal):** {ZIEL_LITERAL}\n\n"
)


def test_die_erwartete_eintragsform_gilt_nicht_als_verstoss() -> None:
    text = _BLOCK.format(id="issue-anlegen", wege="`mcp`, `gh`")

    eintraege = katalog_aus_text(text)

    assert [(e.id, e.wege) for e in eintraege] == [("issue-anlegen", ("mcp", "gh"))]
    assert form_verstoesse(eintraege) == []


def test_gh_vor_mcp_wird_gemeldet() -> None:
    befunde = form_verstoesse(
        katalog_aus_text(_BLOCK.format(id="issue-anlegen", wege="`gh`, `mcp`"))
    )

    assert len(befunde) == 1
    assert "steht vor" in befunde[0]


def test_ein_unbekannter_weg_wird_gemeldet() -> None:
    befunde = form_verstoesse(
        katalog_aus_text(_BLOCK.format(id="issue-anlegen", wege="`mcp`, `gh`, `graphql`"))
    )

    assert len(befunde) == 1
    assert "graphql" in befunde[0]


def test_eine_board_operation_mit_zweitem_weg_wird_gemeldet() -> None:
    text = (
        _BLOCK.format(id="board-status-setzen", wege="`mcp`, `gh`")
        + f"{REMOTE_MARKIERUNG}\n"
    )

    befunde = form_verstoesse(katalog_aus_text(text))

    assert len(befunde) == 1
    assert "statt genau ['gh']" in befunde[0]


def test_eine_board_operation_ohne_remote_kennzeichnung_wird_gemeldet() -> None:
    befunde = form_verstoesse(
        katalog_aus_text(_BLOCK.format(id="board-status-setzen", wege="`gh`"))
    )

    assert len(befunde) == 1
    assert REMOTE_MARKIERUNG in befunde[0]


def test_eine_operation_ohne_ziel_literal_wird_gemeldet() -> None:
    text = "### `issue-anlegen` — Beschreibung\n\n**Wege:** `mcp`, `gh`\n"

    befunde = form_verstoesse(katalog_aus_text(text))

    assert len(befunde) == 1
    assert "owner" in befunde[0]


def test_eine_lesende_operation_ohne_auswertungsgrenze_wird_gemeldet() -> None:
    befunde = form_verstoesse(
        katalog_aus_text(_BLOCK.format(id="issue-lesen", wege="`mcp`, `gh`"))
    )

    assert len(befunde) == 1
    assert AUSWERTUNGSGRENZE in befunde[0]


def test_die_unbelegte_operation_ohne_markierung_wird_gemeldet() -> None:
    befunde = form_verstoesse(katalog_aus_text(_BLOCK.format(id=UNBELEGT, wege="`gh`")))

    assert len(befunde) == 1
    assert UNBELEGT_MARKIERUNG in befunde[0]


@pytest.mark.parametrize(
    ("zeile", "erwartet"),
    [
        ("Fuehr `issue-body-schreiben` aus.", ["issue-body-schreiben"]),
        ("`board-status-setzen` mit Wert `Ready`.", ["board-status-setzen"]),
        ("Danach `pr-erstellen` und `copilot-review-anfordern`.",
         ["pr-erstellen", "copilot-review-anfordern"]),
        ("Der Skill `review-tests` ist keine Operation.", []),
        ("`ship-feature` ebenfalls nicht.", []),
        ("Ein Platzhalter wie `<issue-url>` ist keine ID.", []),
    ],
)
def test_der_erkennungsraum_trennt_ids_von_anderen_kebab_woertern(
    zeile: str, erwartet: list[str]
) -> None:
    assert list(verwendete_ids({"skill.md": zeile})) == erwartet


def test_eine_vertippte_id_faellt_auf() -> None:
    fundstellen = verwendete_ids({".claude/skills/x/SKILL.md": "Fuehr `issue-body-schreibn` aus."})

    assert fundstellen == {"issue-body-schreibn": [".claude/skills/x/SKILL.md:1"]}


def test_zwei_stufen_in_einer_datei_werden_gemeldet() -> None:
    abbild = {
        "a.md": f"{STUFE_MARKER} {STUFE_LESEND}\n{STUFE_MARKER} {STUFE_KEINE}\n",
    }

    befunde = stufen_verstoesse(abbild, {"a.md": STUFE_LESEND})

    assert len(befunde) == 1
    assert "traegt 2 Erlaubnisstufen" in befunde[0]


def test_eine_fehlende_stufe_wird_gemeldet() -> None:
    befunde = stufen_verstoesse({"a.md": "Kein Marker.\n"}, {"a.md": STUFE_LESEND})

    assert len(befunde) == 1
    assert "traegt 0 Erlaubnisstufen" in befunde[0]


def test_eine_falsche_stufe_wird_gemeldet() -> None:
    abbild = {"a.md": f"{STUFE_MARKER} {STUFE_SCHREIBEND}\n"}

    befunde = stufen_verstoesse(abbild, {"a.md": STUFE_KEINE})

    assert len(befunde) == 1
    assert STUFE_KEINE in befunde[0]


def test_lesend_und_schreibend_zaehlt_nicht_als_nur_lesend() -> None:
    """Regex-Falle derselben Klasse wie `--body`/`--body-file`: Teilworte der Stufennamen."""
    abbild = {"a.md": f"{STUFE_MARKER} {STUFE_SCHREIBEND}\n"}

    assert stufen_verstoesse(abbild, {"a.md": STUFE_SCHREIBEND}) == []


def test_der_leser_findet_beide_zweige_des_suchraums() -> None:
    """Gegenprobe zum Leser selbst - er muss beide Aufzaehlungszweige liefern."""
    dateien = suchraum()

    assert any(pfad.startswith(".claude/") for pfad in dateien)
    assert "CLAUDE.md" in dateien


def test_ein_eintragsblock_endet_am_naechsten_abschnitt() -> None:
    """Sonst zoege der letzte Eintrag den Resttext der Datei in seinen Block."""
    text = (
        _BLOCK.format(id="board-status-setzen", wege="`gh`")
        + f"{REMOTE_MARKIERUNG}\n\n## Die vier Haertungsregeln\n\n"
        + AUSWERTUNGSGRENZE
        + " comments\n"
    )

    eintraege = katalog_aus_text(text)

    assert len(eintraege) == 1
    assert "Haertungsregeln" not in eintraege[0].block
    assert form_verstoesse(eintraege) == []
