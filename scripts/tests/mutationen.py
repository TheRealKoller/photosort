"""Die Mutationsliste: je tragender Invariante ein herbeigefuehrter Verstoss.

Ein Waechter ohne Mutation fuer eine seiner Invarianten ist nicht belegt - er koennte
bedingungslos gruen sein. Diese Datei ist der einzige Ort, an dem ein Verstoss gegen eine
Invariante beschrieben steht; die Pruefung selbst wendet die Eintraege an, statt Negativtests zu
pflegen.

Zwei Listen, zwei Aussagen:

- `MUTATIONEN` bricht genau eine Invariante und muss einen Befund mit genau dieser Kennung
  erzeugen.
- `UMFORMIERUNGEN` schreibt denselben Inhalt anders - anderer Wortlaut, andere Form, dieselbe
  Aussage - und muss gruen bleiben. Das ist die Gegenprobe gegen einen Waechter, der nur seinen
  eigenen Wortlaut wiedererkennt.

Jeder Eintrag nennt `datei`, `alt` und `neu`; `alt` muss im Bestand genau einmal vorkommen, sonst
ist der Eintrag unanwendbar und die Pruefung scheitert laut.
"""

from __future__ import annotations

from dataclasses import dataclass

KATALOG = ".claude/skills/github-access/SKILL.md"
REFINEMENT = ".claude/skills/refinement/SKILL.md"
SKILLER = ".claude/skills/skiller/SKILL.md"
DEVELOPER = ".claude/agents/developer.md"


@dataclass(frozen=True)
class Mutation:
    """Ein herbeigefuehrter Verstoss: eine Ersetzung und die Invariante, die er brechen muss."""

    name: str
    waechter: str
    datei: str
    alt: str
    neu: str
    invariante: str


@dataclass(frozen=True)
class Umformulierung:
    """Derselbe Inhalt in anderer Form - die Ersetzungen zusammen muessen gruen bleiben."""

    name: str
    waechter: str
    aenderungen: tuple[tuple[str, str, str], ...]


MUTATIONEN: tuple[Mutation, ...] = (
    Mutation(
        name="neue-operation-definiert",
        waechter="katalog",
        datei=KATALOG,
        alt="### `issue-verwerfen` — Issue ohne Umsetzung schließen",
        neu=(
            "### `issue-verwerfen` — Issue ohne Umsetzung schließen\n"
            "\n"
            "### `issue-archivieren` — ein Issue archivieren"
        ),
        invariante="katalog-geschlossen",
    ),
    Mutation(
        name="weg-ausserhalb-des-vokabulars",
        waechter="katalog",
        datei=KATALOG,
        alt="### `issue-anlegen` — ein Story-Issue anlegen\n\n**Wege:** `mcp`, `gh`",
        neu="### `issue-anlegen` — ein Story-Issue anlegen\n\n**Wege:** `mcp`, `ssh`",
        invariante="wege-geschlossen",
    ),
    Mutation(
        name="weg-ohne-beleg",
        waechter="katalog",
        datei=KATALOG,
        alt="### `pr-pruefstand-lesen` — den Stand der Checks einmal lesen\n\n**Wege:** `gh`",
        neu="### `pr-pruefstand-lesen` — den Stand der Checks einmal lesen\n\n**Wege:** `mcp`, `gh`",
        invariante="wege-belegt",
    ),
    Mutation(
        name="board-weg-mit-mcp",
        waechter="katalog",
        datei=KATALOG,
        alt="### `board-aufnahme` — ein Issue ins Projekt aufnehmen\n\n**Wege:** `gh`",
        neu="### `board-aufnahme` — ein Issue ins Projekt aufnehmen\n\n**Wege:** `gh`, `mcp`",
        invariante="wege-board",
    ),
    Mutation(
        name="ziel-nicht-als-literal",
        waechter="katalog",
        datei=KATALOG,
        alt="### `issue-verwerfen` — Issue ohne Umsetzung schließen",
        neu=(
            "### `issue-verwerfen` — Issue ohne Umsetzung schließen\n"
            "\n"
            "### `issue-archivieren` — ein Issue archivieren\n"
            "\n"
            "**Wege:** `mcp`, `gh`\n"
            "**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `fotos`"
        ),
        invariante="ziel-literal",
    ),
    Mutation(
        name="feld-zuviel-in-der-grenze",
        waechter="katalog",
        datei=KATALOG,
        alt="**Auswertungsgrenze:** `number`, `labels`, `state`, `author` — und nichts sonst.",
        neu=(
            "**Auswertungsgrenze:** `number`, `labels`, `state`, `author`, `title` — und nichts "
            "sonst."
        ),
        invariante="lesende-grenze",
    ),
    Mutation(
        name="zitat-ohne-abschnitt",
        waechter="katalog",
        datei=REFINEMENT,
        alt="Abschnitt „Ein Fehlschlag bleibt sichtbar",
        neu="Abschnitt „Ein Fehlschlag bleibt bestehen",
        invariante="verweis-abschnitt",
    ),
    Mutation(
        name="unbekannte-operations-id",
        waechter="katalog",
        datei=REFINEMENT,
        alt="(`board-prioritaet-setzen`, `board-status-setzen`)",
        neu="(`board-prioritaet-setzen`, `board-status-setze`)",
        invariante="id-verwendung",
    ),
    Mutation(
        name="gh-ausserhalb-des-katalogs",
        waechter="katalog",
        datei=SKILLER,
        alt="# Skiller — schneller Skill-Ersteller",
        neu=(
            "# Skiller — schneller Skill-Ersteller\n\ngh issue list --repo TheRealKoller/photosort"
        ),
        invariante="zugriff-nur-im-katalog",
    ),
    Mutation(
        name="messbegriff-im-anweisungsraum",
        waechter="katalog",
        datei=SKILLER,
        alt="# Skiller — schneller Skill-Ersteller",
        neu="# Skiller — schneller Skill-Ersteller\n\nEin Lauf erbt `GH_TOKEN`.",
        invariante="messbegriffe",
    ),
    Mutation(
        name="erlaubnisstufe-anders-als-entschieden",
        waechter="katalog",
        datei=DEVELOPER,
        alt="**GitHub-Erlaubnisstufe:** keins",
        neu="**GitHub-Erlaubnisstufe:** lesend",
        invariante="erlaubnisstufe",
    ),
    Mutation(
        name="kommentarfeld-in-der-grenze",
        waechter="katalog",
        datei=KATALOG,
        alt="**Auswertungsgrenze:** `body`, `title`, `labels`, `state`, `author` — und nichts sonst.",
        neu=(
            "**Auswertungsgrenze:** `body`, `title`, `labels`, `state`, `author`, `comments` — "
            "und nichts sonst."
        ),
        invariante="kommentar-pfad",
    ),
)


UMFORMIERUNGEN: tuple[Umformulierung, ...] = (
    Umformulierung(
        name="erlaubnisstufe-in-langform",
        waechter="katalog",
        aenderungen=(
            (
                REFINEMENT,
                "**GitHub-Erlaubnisstufe:** schreibend",
                "**GitHub-Erlaubnisstufe:** schreibend — jeder GitHub-Zugriff läuft über die "
                "Operationen des Skills `github-access`.",
            ),
        ),
    ),
    Umformulierung(
        name="kein-mcp-begruendung-umformuliert",
        waechter="katalog",
        aenderungen=(
            (
                KATALOG,
                "**Kein `mcp`-Weg:** Die MCP-Werkzeuge bieten für Projects (V2) keine Operation "
                "an —\ngemessen, nicht vermutet: Projects V2 spricht ausschließlich GraphQL, und "
                "im\nWerkzeugkasten liegt nichts, was diese Operation ausführen könnte.\n"
                "**Diese Operation ist remote auf keinem Weg erreichbar** — Eigenschaft der "
                "Umgebung, keine offene",
                "**Kein `mcp`-Weg:** Für Projects (V2) gibt es kein MCP-Werkzeug — gemessen: die "
                "Schnittstelle spricht ausschließlich GraphQL, und im Werkzeugkasten liegt dazu "
                "nichts.\n**Diese Operation ist remote auf keinem Weg erreichbar** — Eigenschaft "
                "der Umgebung, keine offene",
            ),
        ),
    ),
)
