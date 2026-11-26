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

OPERATIONEN = ".claude/skills/github-access/operationen"
ISSUE_ANLEGEN = f"{OPERATIONEN}/issue-anlegen.md"
ISSUE_LESEN = f"{OPERATIONEN}/issue-lesen.md"
ISSUE_LISTE_LESEN = f"{OPERATIONEN}/issue-liste-lesen.md"
ISSUE_KOMMENTIEREN = f"{OPERATIONEN}/issue-kommentieren.md"
ISSUE_VERWERFEN = f"{OPERATIONEN}/issue-verwerfen.md"
PR_PRUEFSTAND_ABWARTEN = f"{OPERATIONEN}/pr-pruefstand-abwarten.md"
PR_PRUEFSTAND_LESEN = f"{OPERATIONEN}/pr-pruefstand-lesen.md"
BOARD_AUFNAHME = f"{OPERATIONEN}/board-aufnahme.md"
BOARD_STATUS_SETZEN = f"{OPERATIONEN}/board-status-setzen.md"
KATALOG_UEBERSICHT = ".claude/skills/github-access/SKILL.md"
REFINEMENT = ".claude/skills/refinement/SKILL.md"
SKILLER = ".claude/skills/skiller/SKILL.md"

CI = ".github/workflows/ci.yml"
CI_PYTEST_BEFEHL = (
    "pytest -n auto --cov=photosort --cov-report= "
    "--splits ${{ strategy.job-total }} --group ${{ matrix.shard }} "
    "--splitting-algorithm=least_duration"
)
CI_TEST_SCHRITT = (
    "      - name: Test (pytest, Shard ${{ matrix.shard }} von ${{ strategy.job-total }})\n"
    "        env:\n"
    "          COVERAGE_FILE: .coverage.shard-${{ matrix.shard }}\n"
    f"        run: {CI_PYTEST_BEFEHL}"
)
CI_GATE_BEFEHL = (
    "python -m coverage combine && python -m coverage report --show-missing --fail-under=80"
)
DOCKERIGNORE = "backend/.dockerignore"
DOCKERFILE = "backend/Dockerfile"
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
        datei=ISSUE_VERWERFEN,
        alt="## `issue-verwerfen` — Issue ohne Umsetzung schließen",
        neu=(
            "## `issue-verwerfen` — Issue ohne Umsetzung schließen\n"
            "\n"
            "## `issue-archivieren` — ein Issue archivieren"
        ),
        invariante="katalog-geschlossen",
    ),
    Mutation(
        name="uebersicht-zeile-zeigt-auf-fremde-datei",
        waechter="katalog",
        datei=KATALOG_UEBERSICHT,
        alt=(
            "| `issue-anlegen` | ein Story-Issue anlegen | "
            "[`operationen/issue-anlegen.md`](operationen/issue-anlegen.md) |"
        ),
        neu=(
            "| `issue-anlegen` | ein Story-Issue anlegen | "
            "[`operationen/issue-lesen.md`](operationen/issue-lesen.md) |"
        ),
        invariante="uebersicht-vollstaendig",
    ),
    Mutation(
        name="weg-ausserhalb-des-vokabulars",
        waechter="katalog",
        datei=ISSUE_ANLEGEN,
        alt="## `issue-anlegen` — ein Story-Issue anlegen\n\n**Wege:** `mcp`, `gh`",
        neu="## `issue-anlegen` — ein Story-Issue anlegen\n\n**Wege:** `mcp`, `ssh`",
        invariante="wege-geschlossen",
    ),
    Mutation(
        name="weg-ohne-beleg",
        waechter="katalog",
        datei=PR_PRUEFSTAND_LESEN,
        alt="## `pr-pruefstand-lesen` — den Stand der Checks einmal lesen\n\n**Wege:** `gh`",
        neu="## `pr-pruefstand-lesen` — den Stand der Checks einmal lesen\n\n**Wege:** `mcp`, `gh`",
        invariante="wege-belegt",
    ),
    Mutation(
        name="board-weg-mit-mcp",
        waechter="katalog",
        datei=BOARD_AUFNAHME,
        alt="## `board-aufnahme` — ein Issue ins Projekt aufnehmen\n\n**Wege:** `gh`",
        neu="## `board-aufnahme` — ein Issue ins Projekt aufnehmen\n\n**Wege:** `gh`, `mcp`",
        invariante="wege-board",
    ),
    Mutation(
        name="ziel-nicht-als-literal",
        waechter="katalog",
        datei=ISSUE_VERWERFEN,
        alt="## `issue-verwerfen` — Issue ohne Umsetzung schließen",
        neu=(
            "## `issue-verwerfen` — Issue ohne Umsetzung schließen\n"
            "\n"
            "## `issue-archivieren` — ein Issue archivieren\n"
            "\n"
            "**Wege:** `mcp`, `gh`\n"
            "**Ziel (auf jedem Weg als Literal):** `owner` = `TheRealKoller`, `repo` = `fotos`"
        ),
        invariante="ziel-literal",
    ),
    Mutation(
        name="feld-zuviel-in-der-grenze",
        waechter="katalog",
        datei=ISSUE_LISTE_LESEN,
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
        datei=ISSUE_LESEN,
        alt="**Auswertungsgrenze:** `body`, `title`, `labels`, `state`, `author` — und nichts sonst.",
        neu=(
            "**Auswertungsgrenze:** `body`, `title`, `labels`, `state`, `author`, `comments` — "
            "und nichts sonst."
        ),
        invariante="kommentar-pfad",
    ),
    Mutation(
        name="coverage-schwelle-gesenkt",
        waechter="ci",
        datei=CI,
        alt=CI_GATE_BEFEHL,
        neu=(
            "python -m coverage combine && python -m coverage report --show-missing --fail-under=70"
        ),
        invariante="coverage-schwelle",
    ),
    Mutation(
        name="schwelle-am-shard",
        waechter="ci",
        datei=CI,
        alt=f"        run: {CI_PYTEST_BEFEHL}",
        neu=f"        run: {CI_PYTEST_BEFEHL} --cov-fail-under=80",
        invariante="coverage-schwelle",
    ),
    Mutation(
        name="aggregator-ohne-always",
        waechter="ci",
        datei=CI,
        alt="  backend:\n    needs: [backend-test]\n    if: always()\n",
        neu="  backend:\n    needs: [backend-test]\n",
        invariante="coverage-schwelle",
    ),
    Mutation(
        name="shard-nicht-in-needs",
        waechter="ci",
        datei=CI,
        alt="  backend:\n    needs: [backend-test]\n",
        neu="  backend:\n    needs: []\n",
        invariante="coverage-schwelle",
    ),
    Mutation(
        name="splits-fest",
        waechter="ci",
        datei=CI,
        alt="--splits ${{ strategy.job-total }}",
        neu="--splits 8",
        invariante="testmenge-vollstaendig",
    ),
    Mutation(
        name="matrix-luecke",
        waechter="ci",
        datei=CI,
        alt="        shard: [1, 2, 3, 4, 5, 6, 7, 8]",
        neu="        shard: [1, 2, 3, 5, 6, 7, 8]",
        invariante="testmenge-vollstaendig",
    ),
    Mutation(
        name="auswahl-per-k",
        waechter="ci",
        datei=CI,
        alt="--splitting-algorithm=least_duration",
        neu='--splitting-algorithm=least_duration -k "not slow"',
        invariante="testmenge-vollstaendig",
    ),
    Mutation(
        name="playwright-shard-fest",
        waechter="ci",
        datei=CI,
        alt="--shard=${{ matrix.shard }}/${{ strategy.job-total }}",
        neu="--shard=1/1",
        invariante="testmenge-vollstaendig",
    ),
    Mutation(
        name="required-kontext-umbenannt",
        waechter="ci",
        datei=CI,
        alt="  backend:\n",
        neu="  backend-ci:\n",
        invariante="required-kontext-stabil",
    ),
    Mutation(
        name="cache-schreibpfad-ohne-fork",
        waechter="ci",
        datei=CI,
        alt="      - name: Image-Cache-Schreibpfad bestimmen\n        run: |\n",
        neu=(
            "      - name: Image-Cache-Schreibpfad bestimmen\n"
            "        with:\n"
            "          cache_to: type=gha\n"
            "        run: |\n"
        ),
        invariante="cache-und-artefakte",
    ),
    Mutation(
        name="cache-schreibliteral-am-build",
        waechter="ci",
        datei=CI,
        alt=(
            "          set: |\n"
            "            *.cache-from=type=gha,scope=photosort-images\n"
            "            ${{ env.CACHE_BAKE_SCHREIBEN }}\n"
        ),
        neu=(
            "          set: |\n"
            "            *.cache-from=type=gha,scope=photosort-images\n"
            "            *.cache-to=type=gha,scope=photosort-images,mode=min\n"
            "            ${{ env.CACHE_BAKE_SCHREIBEN }}\n"
        ),
        invariante="cache-und-artefakte",
    ),
    Mutation(
        name="download-mit-run-id",
        waechter="ci",
        datei=CI,
        alt="          pattern: coverage-shard-*\n",
        neu="          run-id: 123\n          pattern: coverage-shard-*\n",
        invariante="cache-und-artefakte",
    ),
    Mutation(
        name="modell-asset-im-kontext",
        waechter="ci",
        datei=DOCKERIGNORE,
        alt="src/photosort/assets/label_embedder.onnx\n",
        neu="# src/photosort/assets/label_embedder.onnx\n",
        invariante="modell-assets-geprueft",
    ),
    Mutation(
        name="download-nach-dem-projekt-install",
        waechter="ci",
        datei=DOCKERFILE,
        alt="RUN pip install --no-cache-dir --no-deps .\n",
        neu=(
            "RUN pip install --no-cache-dir --no-deps .\nRUN python scripts/fetch_model_assets.py\n"
        ),
        invariante="modell-assets-geprueft",
    ),
    Mutation(
        name="qualitaet-nicht-ausgefuehrt",
        waechter="ci",
        datei=CI,
        alt="      - name: Type check (mypy)\n        run: mypy src",
        neu="      - name: Type check (mypy)\n        run: echo mypy src",
        invariante="qualitaet-laeuft",
    ),
    Mutation(
        name="tests-nicht-ausgefuehrt",
        waechter="ci",
        datei=CI,
        alt=f"        run: {CI_PYTEST_BEFEHL}",
        neu="        run: echo pytest",
        invariante="tests-je-baum",
    ),
    Mutation(
        name="schritt-ueberspringbar",
        waechter="ci",
        datei=CI,
        alt=CI_TEST_SCHRITT,
        neu=(
            "      - name: Test (pytest, Shard ${{ matrix.shard }} von ${{ strategy.job-total }})\n"
            "        continue-on-error: true\n"
            "        env:\n"
            "          COVERAGE_FILE: .coverage.shard-${{ matrix.shard }}\n"
            f"        run: {CI_PYTEST_BEFEHL}"
        ),
        invariante="nicht-ueberspringbar",
    ),
    Mutation(
        name="pr-ausloeser-entfernt",
        waechter="ci",
        datei=CI,
        alt="on:\n  push:\n    branches: [main]\n  pull_request:",
        neu="on:\n  push:\n    branches: [main]",
        invariante="pr-ausloeser",
    ),
    Mutation(
        name="inline-freitext-statt-datei",
        waechter="befehle",
        datei=ISSUE_ANLEGEN,
        alt=(
            'gh issue create --repo TheRealKoller/photosort --title "$(cat <titel-datei>)" '
            "--body-file <body-datei> <label-schalter>"
        ),
        neu=(
            'gh issue create --repo TheRealKoller/photosort --title "$(cat <titel-datei>)" '
            '--body "Inline-Text" <label-schalter>'
        ),
        invariante="freitext-nur-als-datei",
    ),
    Mutation(
        name="fremdes-ziel",
        waechter="befehle",
        datei=ISSUE_KOMMENTIEREN,
        alt="gh issue comment <NNN> --repo TheRealKoller/photosort --body-file <pfad>",
        neu="gh issue comment <NNN> --repo Fremder/photosort --body-file <pfad>",
        invariante="ziel-geschlossen",
    ),
    Mutation(
        name="ready-wert-verloren",
        waechter="befehle",
        datei=REFINEMENT,
        alt="- `board-status-setzen` mit Wert `Ready`",
        neu="- `board-status-setzen` mit Wert `Done`",
        invariante="reihenfolge-ausfuehrung",
    ),
    Mutation(
        name="board-wert-nicht-in-der-optionsmenge",
        waechter="board",
        datei=BOARD_STATUS_SETZEN,
        alt='--field "Status" --value "<Wert>"\n```',
        neu='--field "Status" --value "In progress"\n```',
        invariante="board-werte",
    ),
    Mutation(
        name="wartepunkt-ohne-zeitgrenze",
        waechter="warten",
        datei=PR_PRUEFSTAND_ABWARTEN,
        alt="timeout 540 gh pr checks <MMM>",
        neu="gh pr checks <MMM>",
        invariante="pruefstand-blockierend",
    ),
    Mutation(
        name="anker-umbenannt",
        waechter="warten",
        datei=DEVELOPER,
        alt="## Blockiert: CI-Fehlschlag außerhalb der zulässigen Klasse",
        neu="## Blockiert: CI-Fehlschlag außerhalb der bekannten Klasse",
        invariante="anker-protokoll",
    ),
    Mutation(
        name="grenze-nicht-leer",
        waechter="katalog",
        datei=PR_PRUEFSTAND_ABWARTEN,
        alt=(
            "**Auswertungsgrenze:** keine Felder — ausgewertet wird ausschließlich der "
            "Ergebniswert aus der"
        ),
        neu=(
            "**Auswertungsgrenze:** `bucket` — ausgewertet wird ausschließlich der Ergebniswert "
            "aus der"
        ),
        invariante="lesende-grenze",
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
                BOARD_AUFNAHME,
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
    Umformulierung(
        name="ci-testschritt-anders-benannt",
        waechter="ci",
        aenderungen=(
            (
                CI,
                "      - name: Test (pytest, Shard ${{ matrix.shard }} von ${{ strategy.job-total }})\n",
                "      - name: Backend-Tests fuer Shard ${{ matrix.shard }}\n",
            ),
        ),
    ),
    Umformulierung(
        name="ci-always-als-ausdruck",
        waechter="ci",
        aenderungen=(
            (
                CI,
                "  backend:\n    needs: [backend-test]\n    if: always()\n",
                "  backend:\n    needs: [backend-test]\n    if: ${{ always() }}\n",
            ),
        ),
    ),
    Umformulierung(
        name="ci-needs-als-blockliste",
        waechter="ci",
        aenderungen=(
            (
                CI,
                "  backend:\n    needs: [backend-test]\n",
                "  backend:\n    needs:\n      - backend-test\n",
            ),
        ),
    ),
    Umformulierung(
        name="ci-splits-ohne-leerzeichen",
        waechter="ci",
        aenderungen=(
            (
                CI,
                "--splits ${{ strategy.job-total }} --group ${{ matrix.shard }}",
                "--splits=${{strategy.job-total}} --group=${{matrix.shard}}",
            ),
        ),
    ),
    Umformulierung(
        name="board-wert-ohne-anfuehrungszeichen",
        waechter="board",
        aenderungen=(
            (
                BOARD_STATUS_SETZEN,
                '--field "Status" --value "<Wert>"\n```',
                "--field Status --value <Wert>\n```",
            ),
        ),
    ),
    Umformulierung(
        name="wartepunkt-mit-anderen-zahlen",
        waechter="warten",
        aenderungen=(
            (
                PR_PRUEFSTAND_ABWARTEN,
                "timeout 540 gh pr checks <MMM> --repo TheRealKoller/photosort --watch "
                "--fail-fast --interval 30 >/dev/null 2>&1",
                "timeout 300 gh pr checks <MMM> --repo TheRealKoller/photosort --watch "
                "--fail-fast --interval 60 >/dev/null 2>&1",
            ),
        ),
    ),
    Umformulierung(
        name="titelzeile-andere-satzstellung",
        waechter="befehle",
        aenderungen=(
            (
                REFINEMENT,
                "- `issue-titel-schreiben`",
                "- `issue-titel-schreiben` — den geschärften Titel am Issue setzen",
            ),
        ),
    ),
    Umformulierung(
        name="ci-zusatzjob-und-umbenannt",
        waechter="ci",
        aenderungen=(
            (
                CI,
                "  frontend:\n",
                "  zusatz:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo zusatz\n\n"
                "  frontend:\n",
            ),
            (
                CI,
                "      - name: Test (pytest, Shard ${{ matrix.shard }} von ${{ strategy.job-total }})\n",
                "      - name: Backend-Tests\n",
            ),
        ),
    ),
)
