# 0269 - `spec-writer` legt den Feature-Branch an — ein PR pro Story statt getrenntem Spec-PR

**Status:** Accepted
**Erstellt:** 2026-08-30
**Bezug:** [GitHub-Issue #269](https://github.com/TheRealKoller/photosort/issues/269) (Refinement bereits vor dieser Spec-Erstellung abgeschlossen), [`decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md`](../decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md) (neue ADR dieser Spec)

## Ziel

Wenn ein Issue umgesetzt werden soll und noch keine Spec existiert, wird aktuell zunächst ein eigener Branch/PR nur für die neue Spec-Datei benötigt — weil die anschließende Implementierung zwingend einen komplett neuen Branch von `main` anlegt und deshalb die Spec vorher schon auf `main` gemergt sein muss. Das erzeugt für jedes neue Feature einen zusätzlichen, rein dokumentarischen PR-Zyklus (samt vollständigem CI-Lauf) ohne echten Mehrwert — bei Issue #218 live beobachtet. Historisch lief das bei vergleichbaren Prozess-Features (Issue #240/PR #261, Issue #262/PR #267) bereits anders: Spec-Commit und Implementierung liefen dort zusammen auf einem einzigen Branch/PR. Ziel ist, zu diesem einfacheren Ablauf zurückzukehren.

## User Story

Als Daniel möchte ich, dass für ein Issue ohne bestehende Spec direkt ein einziger Feature-Branch mit anschließend genau einem Pull Request entsteht (Spec-Commit und Implementierung zusammen), damit kein separater, rein dokumentarischer Zwischen-PR für die Spec-Datei mehr nötig ist.

## Akzeptanzkriterien

- [x] Wird ein Issue ohne bestehende Spec umgesetzt, entsteht dafür genau ein Feature-Branch, auf dem sowohl der Spec-Commit als auch alle folgenden Implementierungs-Commits liegen — kein separater Spec-only-Branch.
- [x] Für diesen gesamten Vorgang (Spec + Implementierung) entsteht genau ein Pull Request, nicht zwei. Der Branch wird erst zusammen mit der fertigen, reviewten Implementierung gepusht und der PR erst zu diesem Zeitpunkt eröffnet — kein vorab gepushter oder eröffneter Zwischenstand nur für die Spec.
- [x] Existiert für ein Issue bereits eine akzeptierte Spec unabhängig von diesem Ablauf, funktioniert die Umsetzung weiterhin unverändert (Fallback: ein neuer Branch wird wie bisher angelegt, falls noch keiner existiert).
- [x] Der bei Issue #218 beobachtete Ablauf (separater Spec-Branch + eigener Spec-PR, gefolgt von einem zweiten, unabhängigen Feature-Branch für die Implementierung) tritt für neu geschärfte Storys nicht mehr auf.

(Alle vier Kriterien direkt bei der Umsetzung dieser Spec erfüllt — diese Spec selbst wurde bereits nach dem neuen Ablauf erstellt: Feature-Branch `feature/0269-spec-writer-legt-feature-branch-an` zuerst angelegt, dieser Spec-Commit sowie die Skill-/Agent-/ADR-Änderungen darauf committet, kein Zwischen-Push.)

## Datenmodell-Bezug

Keine Änderung — reines Entwicklungsprozess-Tooling (KI-Workflow-Skills), kein Bezug zu `docs/architecture.md`.

## Architektur / Umsetzung

`architect`-Konsultation, 2026-08-30. Vollständige Begründung in der neuen ADR [`0045`](../decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md) (Accepted). Prozess-/Workflow-Änderung an den KI-Skills selbst, kein PhotoSort-Anwendungscode betroffen — die Änderungen wurden direkt im Rahmen dieser Konsultation umgesetzt, ohne den `developer`-TDD-Zyklus zu durchlaufen (reine Prompt-/Skill-Textänderungen ohne testbaren Code, analog zu den bisherigen Prozess-ADRs 0036/0037/0039/0040/0042).

**Betroffene Dateien (bereits umgesetzt):**
- `.claude/skills/spec-writer/SKILL.md` (Schritt 4, jetzt "Feature-Branch anlegen, Feature-Spec committen, Board-Spalte setzen"): neue Vorbedingung — Git-Ausgangszustand prüfen (uncommittete Änderungen klären, analog `developer.md` Schritt 0 Punkt 3), von aktuellem `main` abzweigen, dann `git checkout -b feature/<NNNN>-<kurzer-slug>` (`NNNN` = vierstellige Spec-/Issue-Nummer, `<kurzer-slug>` identisch zum Dateinamen der Spec). Die neue Spec-Datei wird direkt auf diesem Branch lokal committet (Conventional Commits, z.B. `docs(specs): Spec NNNN anlegen (Issue #NNN)`) — kein Push, keine PR-Eröffnung an dieser Stelle. Der Branch-Name wird im Abschlussbericht explizit genannt (`**Feature-Branch:** feature/<NNNN>-<kurzer-slug>, bereits angelegt, Spec-Commit liegt bereits darauf`) zur Weitergabe in den späteren `developer`-Start-Prompt.
- `.claude/agents/developer.md` (Schritt 0, Punkt 4, jetzt "Feature-Branch übernehmen oder neu anlegen"): unterscheidet ausschließlich anhand der expliziten Prompt-Angabe — Branch genannt → `git checkout <branch>` (kein neuer Branch, kein eigenes Erkennen/Raten); kein Branch genannt → wie bisher neuer Branch von `main` (Fallback für ältere Specs ohne Vorab-Branch oder einen Ablauf ohne vorherigen `spec-writer`-Durchlauf). Zusätzlich ergänzt (Review-Fund `test-engineer`): Schlägt `git checkout <branch>` fehl (Branch lokal nicht vorhanden), wird **nicht** stillschweigend auf einen neuen Branch ausgewichen (das würde den bereits committeten Spec-Commit verwaisen lassen) — stattdessen AskUserQuestion.
- `.claude/skills/ship-feature/SKILL.md` (Schritt 6.2): klarstellender Satz ohne Logikänderung — der Push (`git push -u origin <branch>`) funktioniert unverändert unabhängig davon, ob der lokale Branch von `spec-writer` (mit Spec-Commit) oder von `developer` selbst angelegt wurde.

**Übergabemechanismus:** reiner Freitext zwischen zwei Schritten derselben Orchestrator-Session (kein neuer struktureller Mechanismus nötig) — `spec-writer` nennt den Branch-Namen im Abschlussbericht, die Session gibt ihn wortgleich in den `developer`-Start-Prompt.

**Kein Effekt auf** `docs/architecture.md`, `docs/setup.md`, Root-`README.md`, `docs/ai-workflow.md` (reines Entwicklungsprozess-Tooling ohne PhotoSort-System-/Datenmodell-Bezug, gleiche Einordnung wie ADR 0037/0042) sowie `specs/README.md` (Nummerierungsschema/Spec-Lebenszyklus unverändert).

## UI/UX

`ux-ui-designer` nicht konsultiert (Schritt 2): reines Entwicklungsprozess-Tooling (Git-Branch-/PR-Mechanik der KI-Workflow-Skills) ohne jede sichtbare Oberfläche für die beiden PhotoSort-Endnutzer — nicht relevant.

## Security

`security-engineer` nicht konsultiert (Schritt 3): reines Entwicklungsprozess-Tooling, keine neue externe Eingabe, keine Auth-/Berechtigungs-Änderung, keine Datenmodell-Änderung, keine veränderte Datensichtbarkeit zwischen den beiden PhotoSort-Endnutzern — nicht relevant.

## Teststrategie

`test-engineer`-Konsultation, 2026-08-30. Reines Prozess-/Steuerungslogik-Feature ohne PhotoSort-Anwendungscode — kein `pytest`/`vitest`-Zugriffspunkt, TDD-Zyklus entfällt (wie ADR 0036/0037/0039/0040/0041/0042). `specs/architecture/0002-testkonzept.md` wurde im Rahmen dieser Konsultation um einen neuen **Punkt 9** in der Sektion "Agenten-Steuerungslogik selbst" ergänzt (nach Punkt 8, strukturell verwandt aber ein eigener Mechanismus: eine unverankerte, einfachere Freitext-Übergabe zwischen einem Hauptsession-Skill und einem noch nicht gestarteten Subagenten statt der in Punkt 8 behandelten verankerten Rückgabe zwischen einem laufenden Subagenten und der Hauptsession).

**Verifikationsmuster (Testkonzept Punkt 9):**
1. **Statischer Konsistenz-Check:** Das Branch-Namensschema `feature/<NNNN>-<kurzer-slug>` muss wortgleich zwischen `spec-writer/SKILL.md` Schritt 4 und dem Fallback in `developer.md` Schritt 0 Punkt 4 sein (verifiziert: ist es).
2. **Synthetische Trockenlauf-Szenarien** (an einem Wegwerf-Branch nachzustellen bei künftigen Änderungen an dieser Logik):
   - Regelfall: `spec-writer` legt Branch + Spec-Commit real an; `developer` wird mit dem genannten Branch-Namen aufgerufen → checkt exakt diesen Branch aus, kein zweiter Branch, Spec-Commit bleibt erhalten.
   - AK-Grenzfall "kein Vorab-Branch": `developer` ohne Branch-Angabe aufgerufen → legt wie bisher neuen Branch von `main` an, identisches Namensschema.
   - AK-Grenzfall "kein `spec-writer`-Durchlauf": unabhängig akzeptierte Spec ohne vorherigen `spec-writer`-Aufruf → verhält sich identisch zum vorigen Fall.
   - End-to-End (AK1+2): `git diff --name-only main...HEAD` am Ende umfasst Spec- und Implementierungs-Commits; `ship-feature` erzeugt genau einen PR.
3. **Laufende Beobachtung:** `review-tests` prüft bei jedem aus `spec-writer` hervorgegangenen Feature-Branch, dass genau ein PR mit dem übernommenen Branch entstanden ist (kein separater Spec-PR mehr).

Kein neues CI-Gate, kein neues Testframework — konsistent mit allen bisherigen reinen Prozess-Features.

**Bekannter Beobachtungspunkt (kein Blocker):** `developer.md` beschrieb ursprünglich kein Verhalten für einen fehlschlagenden `git checkout <branch>` (Branch lokal nicht vorhanden, z.B. bei abweichender Arbeitsumgebung des Subagenten) — in dieser Spec bereits nachgeschärft (siehe "Architektur / Umsetzung": AskUserQuestion statt stillem Ausweichen auf einen neuen Branch).

## Entscheidungen

- **architect konsultiert (Schritt 1):** konkreter Bezug zu `spec-writer/SKILL.md`, `developer.md`, `ship-feature/SKILL.md` — kein Skip möglich. Hat die Änderungen direkt umgesetzt (reine Prompt-/Skill-Textänderungen ohne testbaren Code, kein `developer`-TDD-Zyklus nötig).
- **Neue ADR 0045:** hält die bisher nirgends explizit festgehaltene, aber faktisch prozessprägende Verhaltensannahme "developer branch immer neu von main" jetzt explizit fest und ersetzt sie — analog zum Muster der bestehenden Prozess-ADRs 0036/0037/0039/0040/0042.
- **Push/PR erst am Ende (Rahmenentscheidung aus dem Refinement-Gespräch):** keine offene Frage mehr bei `spec-writer`/`architect` — der Branch existiert bis `ship-feature` ausschließlich lokal.
- **Explizite Prompt-Angabe statt Erkennungslogik in `developer`:** ein gedächtnisloser Subagent kann einen passenden Branch nicht zuverlässig von main erkennen — die Verantwortung bleibt bei der orchestrierenden Session.
- **ux-ui-designer nicht konsultiert (Schritt 2):** reines Entwicklungsprozess-Tooling ohne sichtbare Oberfläche.
- **security-engineer nicht konsultiert (Schritt 3):** kein neuer externer Eingabe-/Auth-/Datenmodell-Bezug, keine veränderte Datensichtbarkeit zwischen den beiden Nutzern.
- **test-engineer-Review-Fund nachgeschärft:** `developer.md` behandelt jetzt explizit den Fehlerfall eines nicht auffindbaren, genannten Branches (AskUserQuestion statt stillem Fallback).
- **`docs/architecture.md`/`docs/ai-workflow.md`/`specs/README.md` unverändert:** reines Entwicklungsprozess-Tooling, betrifft keinen dort dokumentierten Abschnitt.

## Offene Fragen

Keine — das Refinement-Gespräch (Issue #269, Status `Ready`) sowie die technischen Konsultationen in dieser Spec haben alle Unklarheiten geklärt.

## Out of Scope

- Ein dedizierter, strukturierter Übergabemechanismus (Datei, `SendMessage`) zwischen `spec-writer` und `developer` für den Branch-Namen — reiner Freitext innerhalb derselben Orchestrator-Session reicht, da beide Aufrufe ohnehin von derselben Session ausgehen.
- Automatisierte Erkennung eines passenden Branches durch `developer` selbst (z.B. Namenskonvention-Matching) — bewusst nicht gewählt, da ein gedächtnisloser Subagent das nur raten könnte.
- Änderung des Copilot-Review- oder Board-Status-Ablaufs in `ship-feature` — unverändert, da strukturell unabhängig davon, wer den Branch ursprünglich angelegt hat.
