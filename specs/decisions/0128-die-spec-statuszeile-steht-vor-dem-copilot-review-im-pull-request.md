# 0128 - Die Spec-Statuszeile steht vor dem Copilot-Review im Pull Request, und `ci.yml` bricht den überholten Lauf ab

**Status:** Accepted
**Datum:** 2026-10-01
**Bezug:** GitHub-Issue [`#414`](https://github.com/TheRealKoller/photosort/issues/414), zugehörige
Feature-Spec `specs/features/0414-*.md`, `.claude/skills/ship-feature/SKILL.md` (Schritt 6–8),
`.github/workflows/ci.yml`

**Löst teilweise ab (jeweils benannt):**

- [`decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md`](./0042-pre-merge-finalisierung-statt-nachzieh-pr.md)
  — **Abschnitt 3** (Zeitpunkt nach Review **und Copilot-Auswertung**, gebündelt mit dem letzten
  Push) und aus **Abschnitt 1** die Festlegung, die Statuszeile sei der letzte Commit des
  Feature-Branches. Abschnitt 1 im Übrigen (Statuszeile im Feature-PR selbst, vor dem Merge, kein
  Nachzieh-PR) und Abschnitt 5 bleiben in Kraft.
- [`decisions/0063-abgleich-mit-main-als-getestetes-lokales-skript-merge-statt-rebase.md`](./0063-abgleich-mit-main-als-getestetes-lokales-skript-merge-statt-rebase.md)
  — aus **Abschnitt 6, zweiter Punkt,** „vor dem Setzen der Spec-Statuszeile" und der
  „Finalisierungs-Commit" im gebündelten Push. Der zweite Abgleich bleibt erste Handlung von
  Schritt 8.

**Berührt außerdem (keine Ablösung):** ADR
[`0057`](./0057-board-lebenszyklus-nativ-statt-eigenbau.md) führt in ihrem Löst-ab-Eintrag zu 0042
Abschnitt 3 als gültig; maßgeblich ist der Teil-Vermerk an 0042. ADR
[`0092`](./0092-ci-ergebnis-abwarten-und-begrenzt-nachbessern.md) bleibt unverändert: Gewartet wird
nach dem letzten Push des Laufs, der jetzt in Schritt 8 liegt, nicht mehr in einer Finalisierung.

## Kontext

Copilot prüft den Diff, der bei seiner Anforderung im Pull Request steht. Steht die Statuszeile dort
noch auf `Accepted`, meldet er in genau dem PR, der die Spec umsetzt, eine Spec ohne Umsetzung —
ein Befund ohne Fehler, der trotzdem bewertet und beantwortet werden muss.

Die Statuszeile braucht die PR-Nummer, die erst `pr-erstellen` liefert. Die Eröffnung löst einen
Lauf von `ci.yml` aus (`pull_request`, Typ `opened`), jeder spätere Push auf den Branch einen
weiteren (`synchronize`). Ein Statuscommit zwischen Eröffnung und Copilot-Anforderung ist ein
zusätzlicher Push.

## Entscheidung

### 1. Die Statuszeile entsteht unmittelbar nach der Eröffnung, vor dem Copilot-Review

Reihenfolge in `ship-feature` Schritt 6: Abgleich mit `main` → Push → `pr-erstellen` →
`pr-verknuepfung-lesen` → `**Status:** Implemented ([PR #MMM](…/pull/MMM))` setzen, committen,
pushen → Board-Wert zurücklesen. Erst danach `copilot-review-anfordern` (Schritt 7).

- **Vor** der Statuszeile steht die Verknüpfungsprüfung: Closing-Referenz auf das Story-Issue und
  Basis `main`. Schlägt sie fehl, wird nichts geschrieben; Fehlerpfade wie bisher.
- **Zwischen `pr-erstellen` und dem Push der Statuszeile** liegt kein Warten, kein Subagent und
  keine Review. Bei Verletzung läuft der Lauf der Eröffnung womöglich vollständig durch, bevor
  Abschnitt 3 ihn abbrechen kann, und zählt dann als Durchlauf.
- **Nach** der Review-Runde (Schritte 3–5): Ein ungereviewter Stand wird nie als umgesetzt geführt.
  Copilot-Fixes danach lassen die Zeile stehen; sie sagt aus, dass dieser PR die Spec umsetzt, und
  wirksam wird sie ausschließlich durch seinen Merge.
- Entfällt das Copilot-Review (reiner Doku-/Spec-PR), steht die Zeile an derselben Stelle.

### 2. Die Statuszeile lebt bis zum Merge nur im Feature-Branch

Kein Schreiben auf `main`, kein eigener PR, kein Board- oder Issue-Zugriff dafür. Schritt 8 setzt
keine Statuszeile mehr: Erste Handlung ist der Abgleich mit `main`; Merge-Commit, ein etwaiger
Konflikt-Fix und noch nicht gepushte Fix-Commits gehen in **einem** Push hinaus. Hat Schritt 8
nichts zu pushen, entfällt der Push, und der Lauf der Statuszeile ist der, auf den Schritt 9 wartet.

### 3. `ci.yml` bricht den Lauf eines überholten PR-Stands ab

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: true
```

- **Gilt für** `pull_request`-Läufe: je PR höchstens ein laufender Lauf; ein Push auf den Branch
  bricht den Lauf des vorigen Stands ab. Der Schlüssel ist die von GitHub vergebene PR-Nummer, nie
  Branchname oder Titel.
- **Gilt nicht für** Pushes auf `main`: Dort fällt die Gruppe auf `github.run_id` zurück und ist je
  Lauf eindeutig — kein `main`-Lauf bricht einen anderen ab.
- **Bei Verletzung** (Block fehlt oder gruppiert nicht je PR) läuft der Lauf der Eröffnung voll
  durch, und jeder Feature-PR kostet einen vollständigen CI-Durchlauf mehr als vor dieser ADR.

### 4. Zählweise: ein Durchlauf ist ein Lauf von `ci.yml` mit Ergebnis

Ein Durchlauf der automatischen Prüfungen ist ein Lauf von `ci.yml`, der für einen Stand ein
Ergebnis liefert (grün oder rot). Ein nach Abschnitt 3 abgebrochener Lauf liefert keines und zählt
nicht. Damit gilt je `ship-feature`-Lauf:

- vorher: Eröffnung + Push aus Schritt 8, der wegen des Finalisierungscommits **immer** stattfand;
- jetzt: Statuszeile (der Eröffnungslauf bricht ab) + Push aus Schritt 8 **nur**, wenn Abgleich oder
  Fixes etwas zu pushen haben.

Pushes dazwischen (Copilot-Fixes aus Schritt 7, CI-Nachbesserungen aus Schritt 9) sind in beiden
Fassungen gleich. Die Zahl der Durchläufe sinkt oder bleibt gleich; sie steigt in keinem Fall.

`pr-titel.yml` ist nicht Teil dieser Zählung: Die Titelprüfung liest kein Repository, dauert
Sekunden und läuft bei jedem `synchronize` — durch den Statuspush einmal je PR mehr.

### 5. Wird der PR ohne Merge geschlossen, wird die Zeile zurückgenommen

`main` führt die Spec ohnehin weiter als `Accepted` (Abschnitt 2). Auf dem Branch nimmt die
Sitzung, die den Abschluss ohne Merge behandelt, die Zeile per eigenem Commit auf `Accepted`
zurück und pusht ihn, solange der Branch auf dem Remote existiert; ist er gelöscht, genügt der
lokale Commit. Das Zurücksetzen der Board-Karte auf `In Progress` bleibt unverändert. Wird der PR
wieder geöffnet, entsteht die Zeile erneut nach Abschnitt 1.

## Verworfene Alternativen

- **Eröffnung als Entwurf, CI erst bei `ready_for_review`:** braucht eine neue Katalogoperation,
  ein `if:` an jedem Job von `ci.yml` und einen zusätzlichen Ereignistyp; übersprungene Jobs melden
  sich gegenüber geforderten Checks als erfolgreich.
- **PR-Nummer vorhersagen:** Issues und PRs teilen sich einen Nummernraum, parallele Sitzungen legen
  Issues an. Ein Fehlgriff kostet einen Korrekturcommit und damit den Lauf, der gespart werden soll.
- **`[skip ci]` im Statuscommit:** Der Squash-Merge übernimmt die Commit-Nachrichten in den
  Merge-Commit auf `main` und unterdrückt dort die Push-Workflows (CI, release-please); ohne
  späteren Push fehlen am Kopf des PRs die geforderten Checks.
- **`opened` aus den Auslösern von `ci.yml` streichen:** PRs ohne Folgepush (release-please,
  Entwurfs-PRs aus `ship-entwurf`) bekämen keinen CI-Lauf.

## Konsequenzen

- **`.github/workflows/ci.yml`:** `concurrency`-Block aus Abschnitt 3 auf oberster Ebene.
- **`.claude/skills/ship-feature/SKILL.md`:** Verknüpfungsprüfung und Statuszeile wandern aus
  Schritt 8 in Schritt 6; Schritt 7 fordert nach dem Statuspush an; Schritt 8 wird Abgleich und
  letzter Push; der Abschnitt zum PR ohne Merge nimmt die Zeile verbindlich zurück.
- **`.claude/agents/developer.md`, `docs/ai-workflow.md`:** Beschreibung der Reihenfolge nachziehen.
- **`scripts/tests/`:** die Reihenfolge-Zusagen zu `ship-feature` Schritt 6/8 und die Überschrift
  des Wartepunkt-Vergleichs folgen der neuen Gliederung.
- **Kein Effekt auf `docs/architecture.md`/`docs/setup.md`/Root-`README.md`** — Prozess-Tooling ohne
  Bezug zu PhotoSorts Laufzeitsystem oder Datenmodell.
