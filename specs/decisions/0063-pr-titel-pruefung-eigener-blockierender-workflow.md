# 0063 - PR-Titel-Prüfung als eigener, blockierender Workflow statt externer Action

**Status:** Accepted
**Datum:** 2026-09-07

## Kontext

Das Repository squasht Pull Requests mit `COMMIT_OR_PR_TITLE` — der PR-Titel wird damit zum Titel des Merge-Commits auf `main`. `release-please` (ADR [`0008`](./0008-automated-semver-releases.md)) wertet genau diese Commit-Titel aus. Trägt ein Titel kein Conventional-Commit-Präfix, kann der Parser den Commit nicht lesen und übergeht ihn **still**: keine Fehlermeldung, kein rotes Signal, kein Changelog-Eintrag, kein Versions-Bump. Vier der letzten sechzig Merges auf `main` trugen kein Präfix (`Cloud-Modell je Anbieter wählbar …`, `Projektnavigation in der Kopfzeile …`, `Dark Utility Register Stufe 2 …`, `Board-Lebenszyklus nativ …`); drei davon fehlen dauerhaft im Changelog.

ADR [`0060`](./0060-release-pr-merge-von-hand-auto-merge-entfaellt.md) hat diesen Defekt beim Aufräumen des Release-Workflows ausdrücklich gesehen und ebenso ausdrücklich **nicht** mitentschieden ("eigene Fehlerklasse: Commit-Titel-Konvention, nicht Workflow-Syntax"). Diese ADR holt das nach.

Prüft heute niemand. Der Titel entsteht an zwei Stellen — im Ablauf über den Skill `ship-feature` (Operation `pr-erstellen`), und von Hand über die GitHub-Oberfläche. Eine Regel, die nur im Ablauf steht, deckt den zweiten Fall nicht ab; eine Regel, die nur dokumentiert ist, hat dieselbe Halbwertszeit wie der Kommentar, der über 40 Läufe hinweg niemanden erreicht hat (ADR 0060).

## Entscheidung

### 1. Eigener Workflow, nicht ein Job in `ci.yml`

`.github/workflows/pr-titel.yml`, ein einziger Job. `ci.yml` bleibt unverändert.

Grund ist der Trigger: Damit ein korrigierter Titel ohne weiteren Handgriff erneut geprüft wird, muss der Ereignistyp `edited` dabei sein. `ci.yml` läuft heute auf `pull_request` ohne `types:` — das sind implizit `opened`, `synchronize`, `reopened`. Ein `edited` dort zu ergänzen, ließe bei **jeder** Titel- oder Body-Bearbeitung den gesamten Prüfsatz neu laufen (backend, frontend, e2e, docker-compose-check, demo-scripts — Größenordnung: viele Minuten Rechenzeit für eine Textänderung). Der getrennte Workflow kostet dagegen wenige Sekunden.

Trigger:

```yaml
on:
  pull_request:
    types: [opened, edited, reopened, synchronize]
```

`synchronize` ist **nicht** optional, obwohl ein neuer Commit den Titel nicht ändert: Required Status Checks werden pro Head-SHA ausgewertet. Ohne `synchronize` bliebe der Check nach jedem weiteren Push auf `Expected — waiting for status to be reported` stehen und blockierte den PR dauerhaft, statt ihn freizugeben.

`pull_request_target` ist ausgeschlossen — das Repository ist public, und das Verbot ist das schärfste Muss-Kriterium aus Spec 0008, maschinell gehalten von `scripts/tests/test_release_workflow_ohne_selbstmerge.py` (Zusicherung 4d, gilt repo-weit für jeden Workflow). Der Check braucht keinerlei Secret und keinen Schreibzugriff; `permissions: {}` genügt.

### 2. Eigene Prüfung, keine externe Action

Kein `amannn/action-semantic-pull-request`, kein anderes Fremdpaket. Die gesamte Logik ist ein einziger erweiterter regulärer Ausdruck, geprüft mit `grep -E`.

Das ist bewusst die **umgekehrte** Abwägung wie in ADR 0008, wo der Eigenbau zu Recht verworfen wurde — und der Unterschied ist der Umfang: `release-please` trägt Conventional-Commit-Parsing, Changelog-Gruppierung, Pre-1.0-Bump-Regeln und Release-PR-Wiedererkennung; ein Eigenbau hätte all das schlechter nachgebaut. Hier steht dem eine Zeile Regex gegenüber. Eine neue externe Dauerabhängigkeit dafür wäre unverhältnismäßig: sie brächte Drittanbieter-JavaScript in den PR-Kontext, ein zu pflegendes SHA-Pinning und eine Fehlermeldung, die sich nur begrenzt anpassen lässt — während der Nutzen (AK 4: die Meldung sagt, was fehlt und was zulässig ist) gerade an der frei formulierbaren Meldung hängt.

Zweiter, gleichrangiger Grund: **Testbarkeit.** Der Regex steht als Shell-Variable in der Workflow-Datei und wird von `scripts/tests/` von dort **ausgelesen und mit demselben `grep -E` gegen Positiv-/Negativ-Beispiele laufen gelassen** — geprüft wird das Artefakt, das tatsächlich läuft, ohne zweite Kopie des Musters, die driften könnte. Bei einer externen Action wäre nur die YAML statisch prüfbar, das Verhalten selbst gar nicht. Das entspricht dem etablierten Muster der Nachbartests in diesem Verzeichnis (textbasiert, ohne YAML-Bibliothek, mit Gegenproben und Selbstschutz gegen einen leeren Suchraum).

### 3. Der Titel geht über `env:`, nie in den Skripttext

```yaml
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
```

und im Skript ausschließlich als `"$PR_TITLE"`. Ein `${{ github.event.pull_request.title }}` direkt im `run:`-Block wäre die klassische Script-Injection: Der Titel ist auf einem public Repository von jedem Fork-Autor frei wählbarer Text, und GitHub setzt den Ausdruck vor dem Ausführen wörtlich in das Skript ein. Diese Regel wird von den Tests festgehalten, nicht nur kommentiert.

Der Job verwendet **kein** `actions/checkout`. Er braucht kein Repository-Dateisystem — und führt damit keine einzige Zeile aus dem Pull Request aus.

### 4. Zulässige Präfixe: zehn Typen, Scope und Breaking-Marker erlaubt

```
^(build|chore|ci|docs|feat|fix|perf|refactor|revert|test)(\([^()]+\))?!?: [^[:space:]]
```

Am Bestand ausgemessen (`git log origin/main --first-parent`, letzte 80 Merges): 76 Titel bestehen, abgelehnt werden **genau die vier** bekannten Titel ohne Präfix. Ebenfalls geprüft: `feat!:`, `feat(frontend)!:`, `chore(deps-dev):` (Dependabot), `chore(main): release 0.37.0` (release-please) und der von GitHub beim Squash angehängte ` (#341)`-Suffix bestehen; `fix:kein Leerzeichen`, `fix: ` (leere Beschreibung), `Feat:` (Großschreibung) und `wip:` werden abgelehnt.

Die Typenmenge geht über die sechs aus `CLAUDE.md` (`feat`, `fix`, `docs`, `refactor`, `test`, `chore`) hinaus und ergänzt `build`, `ci`, `perf`, `revert`. Grund: `ci:` wird auf `main` bereits verwendet — die engere Liste würde einen etablierten, korrekten Titel ab sofort ablehnen. Alle vier Ergänzungen versteht `release-please` nativ (`perf` ist releasable, die übrigen drei werden sauber als nicht-releasable eingeordnet); keine davon vergrößert die Changelog-Lücke, um die es hier geht. **`CLAUDE.md` wird im selben PR auf diese zehn Typen erweitert** — die Liste dort und der Regex hier werden von einem Test gegeneinander gehalten, damit sie nicht auseinanderlaufen.

Scopes sind erlaubt (`feat(frontend):` ist im Bestand die Regel, nicht die Ausnahme) und bewusst permissiv gefasst (`[^()]+`) — der Scope ist für `release-please` nicht bedeutungstragend, und eine enge Zeichenliste erzeugte nur Fehlalarme. Der Breaking-Marker `!` ist zugelassen, weil er der einzige Weg zu einem MAJOR-Bump ist.

### 5. Was diese Entscheidung ausdrücklich **nicht** zusichert

- **Keinen lückenlosen Changelog.** Ein `chore:`- oder `docs:`-Titel ist korrekt geformt und erscheint trotzdem nicht im Changelog — das ist gewolltes Verhalten von `release-please`. Zugesichert ist, dass jede Änderung **klassifiziert** wird, statt still durchzufallen; ob die Klassifikation inhaltlich passt, bleibt eine menschliche Entscheidung beim Schreiben des Titels.
- **Keinen Schutz gegen böswillige Umgehung.** Bei `pull_request`-Triggern stammt die ausgeführte Workflow-Datei aus dem Merge-Stand des PRs — ein PR kann seine eigene Prüfung ändern. Das gilt für jeden Check dieses Repositories gleichermaßen (auch für `backend`/`frontend`) und ist hier kein neuer Umstand. Der Check ist ein Schutz gegen Versehen, nicht gegen einen Angreifer mit Schreibzugriff.
- **Keine Prüfung der Commit-Nachrichten** innerhalb eines PRs. Beim Squash zählt allein der Titel; die Einzel-Commits landen im Body des Merge-Commits und lösen keinen Release aus.

### 6. Der Merge wird erst durch einen Required Status Check verhindert

Ein Workflow allein macht einen PR nicht unmergebar. Wirksam wird die Zusage erst, wenn der Job-Name als Kontext in `required_status_checks.contexts` der Branch Protection auf `main` steht (heute: `backend`, `frontend`, `docker-compose-check`, `e2e`, `demo-scripts`). Das ist eine Repository-Einstellung außerhalb des Codes, für die es im Operationskatalog `github-access` bewusst keine Operation gibt und die kein Agent dieses Projekts setzt — **Daniel setzt sie von Hand**, wie zuletzt bei `demo-scripts` (Spec 0178).

Sie kann erst **nach** dem Merge des Umsetzungs-PRs gesetzt werden: Ein geforderter Kontext, den noch kein Lauf meldet, blockiert jeden offenen PR dauerhaft mit `Expected — waiting for status to be reported`.

Daraus folgt eine Ehrlichkeitspflicht für die Spec: Das Akzeptanzkriterium "der Merge wird tatsächlich verhindert" gilt **als offen**, bis der Kontext gesetzt ist — nicht als erfüllt, weil der Workflow läuft und rot werden kann. Dieselbe Trennung wie im Testkonzept zwischen Konfiguration und Nachweis-Lauf.

## Begründung

- **Getrennter Workflow:** Der einzige Ereignistyp, der AK 5 trägt (`edited`), ist zugleich der teuerste, wenn er den vollen Prüfsatz auslöst. Trennung kostet eine Datei und spart bei jeder Titelkorrektur Minuten Rechenzeit.
- **Eigenbau statt Action:** Verhältnismäßigkeit (eine Zeile Regex gegen eine Dauerabhängigkeit) plus zwei konkrete Anforderungen, die der Eigenbau besser erfüllt: eine frei formulierte deutsche Fehlermeldung (AK 4) und ein Test, der das real laufende Muster prüft statt eine Kopie davon.
- **Zehn statt sechs Typen:** Am Bestand belegt (`ci:` ist in Gebrauch). Eine Prüfung, die korrekte Praxis ablehnt, wird umgangen oder aufgeweicht — beides schlechter, als die Liste einmal bewusst zu weiten.
- **`env:` statt Inline-Ausdruck:** Der PR-Titel ist auf einem public Repository frei wählbarer Fremdtext; das ist die Standard-Angriffsfläche für Script-Injection in Actions. Die Gegenmaßnahme kostet nichts und wird testgehalten, weil ein Kommentar sie nicht hält.
- **Kein `actions/checkout`:** Der Job führt dadurch nichts aus dem PR aus und läuft in Sekunden.

## Konsequenzen

- Neue Datei `.github/workflows/pr-titel.yml` — der dritte Workflow des Repositories. `scripts/tests/test_release_workflow_ohne_selbstmerge.py` prüft `MINDESTZAHL_WORKFLOWS >= 2` und eine Teilmenge, bleibt also grün; sein repo-weites `pull_request_target`- und Selbst-Merge-Verbot erstreckt sich ab sofort mit auf die neue Datei (gewollt).
- **Manueller Schritt für Daniel nach dem Merge:** den neuen Job-Namen in `required_status_checks.contexts` aufnehmen. Bis dahin ist die Prüfung sichtbar, aber nicht bindend. Gehört in den Abschnitt `## Lokal nachzuholen` des PRs und danach als verifizierter Wert in [`../architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md) (Sektion "GitHub-Repository-Zugriff"), wo die Kontext-Liste als Baseline gepflegt wird.
- **Preis dieses Gates:** Ab dann kann ein Tippfehler im PR-Titel einen Merge blockieren — auch bei einem dringenden Fix. Die Korrektur ist ein Klick plus ein Workflow-Lauf von Sekunden; das ist bewusst getragen.
- **`CLAUDE.md` ändert sich** (Typenliste auf zehn erweitert, PR-Konvention um die Titelregel ergänzt). Das ist die Projektverfassung — die Erweiterung ist Daniel gegenüber ausdrücklich zu benennen, nicht nebenbei mitzunehmen.
- Die Titelregel steht danach an vier Stellen (`CLAUDE.md`, PR-Vorlage, `github-access`/`pr-erstellen`, `ship-feature`), analog zur bestehenden `Closes #NNN`-Regel, die ebenfalls mehrfach steht. Nur die Präfixliste selbst wird testgebunden gehalten; die Prosa nicht.
- **Falle beim Umsetzen:** Das `gh api`-Kommando zum Setzen der Branch Protection darf **nicht** in `CLAUDE.md` oder eine Datei unter `.claude/` geschrieben werden — dort ist jeder `gh`-Aufruf außerhalb des Operationskatalogs verboten (ADR [`0061`](./0061-ein-ort-fuer-jeden-github-zugriff-wege-in-fester-reihenfolge.md), gehalten von `scripts/tests/test_github_zugriff_an_einer_stelle.py`). Es gehört in die Feature-Spec bzw. den PR-Body; `specs/` liegt außerhalb jenes Suchraums. Der Operationskatalog bekommt **keine** achtzehnte Operation.
- `docs/architecture.md` bleibt unberührt: weder Systemarchitektur noch Datenmodell ändern sich, das Dokument beschreibt keine CI-Workflows.
