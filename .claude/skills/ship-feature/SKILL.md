---
name: ship-feature
description: Koordiniert auf oberster Ebene (Orchestrator/Hauptsession) die Nachbereitung eines `developer`-Subagenten-Laufs — den `review`-Orchestrator-Skill aufrufen, Findings per SendMessage zurückspielen, Pull Request eröffnen, Copilot-Review anfordern/auswerten. Nutze diesen Skill IMMER, wenn eine `developer`-Subagenten-Antwort mit dem wörtlichen Anker `## Blockiert: Architektur-Konsultation nötig` oder `## Abschlussbericht` zurückkommt (auch `## Abschlussbericht (Folgeauftrag: Findings behoben)`) — das ist der verbindliche Übergabepunkt, an dem `developer` selbst keine weitere Verschachtelungsebene an Subagenten und keinen GitHub-Zugriff hat. Nicht nutzen für die Umsetzung selbst (dafür `developer`) oder das Schärfen einer Idee zur Spec (dafür `spec-writer`).

---

# Ship Feature — Review, PR und Copilot-Review vom Orchestrator

Übernimmt genau die Verantwortung, die ein per Agent-Tool gestarteter `developer`-Subagent strukturell nicht selbst wahrnehmen kann: eine weitere Verschachtelungsebene an Subagenten (`architect` bei einer Planungslücke) und GitHub-Schreibzugriff (Push, PR-Erstellung, Copilot-Review). Die eigentliche Review-Prüfung übernimmt der Skill `review` (`.claude/skills/review/SKILL.md`) — dieser Skill hier ruft ihn nur auf und kümmert sich um alles davor und danach. `developer` bleibt für die Dauer dieses gesamten Ablaufs als offener Subagent ansprechbar (SendMessage), es wird für Folgeaufträge kein neuer Lauf gestartet, solange der Subagent noch erreichbar ist.

## Schritt 0: Trigger erkennen

Eine `developer`-Antwort löst diesen Skill aus, wenn sie einen der folgenden wörtlichen Anker enthält (Groß-/Kleinschreibung und Zeichensetzung exakt wie hier, keine sinngemäße Näherung; Format inkl. aller Feldnamen ausschließlich in `.claude/agents/developer.md` definiert — hier keine Kopie):

- `## Blockiert: Architektur-Konsultation nötig` → Schritt 1.
- `## Abschlussbericht` (Erstbericht, vor jedem Review) → Schritt 2.
- `## Abschlussbericht (Folgeauftrag: Findings behoben)` (nach einem SendMessage-Fix-Auftrag) → Schritt 5.

**Kein exakter Match, aber erkennbar gemeinter Abschluss** (z.B. Tippfehler, abweichende Formatierung, fehlendes Feld): nicht stillschweigend als "fertig, bereit für Review" werten. Lies den Bericht inhaltlich vollständig — wirkt er wie ein vollständiger Abschluss, frag beim `developer`-Subagenten per SendMessage kurz nach, ob es sich um den finalen Bericht handelt und bitte um die Korrektur des Ankers (kostet eine Nachricht, verhindert aber ein falsch interpretiertes Signal); wirkt er unvollständig oder unklar, frag stattdessen inhaltlich nach, was fehlt. Nie raten.

## Schritt 1: "Blockiert" behandeln

Format (Feldnamen `**Feature-Branch:**`, `**Grund:**`, `**Bisheriger Stand:**`) siehe `.claude/agents/developer.md`.

1. Ruf `architect` auf (Agent-Tool, `subagent_type: architect`, Standard-Modell — kein `model`-Parameter, wie bisher in `developer.md` Schritt 1 vorgesehen), im Vordergrund/`run_in_background: false`. Gib ihm den genannten Grund, den Spec-Bezug und den bisherigen Stand mit.
2. Gib das Ergebnis per `SendMessage` an denselben, weiterhin offenen `developer`-Subagenten zurück, der bei Schritt 1 seines Ablaufs fortfährt.
3. Schlägt `SendMessage` fehl (Subagenten-Fenster bereits geschlossen/Timeout): siehe Abschnitt "Recovery" unten.

## Schritt 2: "Abschlussbericht" behandeln — Branch-/Diff-Verifikation

Format (alle Feldnamen) ausschließlich in `.claude/agents/developer.md` definiert. Bevor überhaupt eine Review-Entscheidung getroffen wird, verifiziere den gemeldeten Stand selbst — der Bericht dient nur der Nachvollziehbarkeit/Plausibilisierung, nicht als alleinige Quelle:

1. `git branch --show-current` gegen den im Bericht genannten `**Feature-Branch:**` abgleichen. Bei Abweichung `git checkout <gemeldeter-branch>`.
2. `git status` muss sauber sein. Ist das nicht der Fall, obwohl der Bericht "sauber, alles committet" behauptet, das nicht stillschweigend ignorieren — im Bericht vermerken und den `developer`-Subagenten per SendMessage auf die Diskrepanz hinweisen, bevor es weitergeht.
3. `git diff --name-only main...HEAD` **selbst erneut ausführen** — das ist die verbindliche Quelle für die folgende Review-Runde, nicht die im Bericht unter "Betroffene Dateien" gelistete Liste. Weicht die selbst ermittelte Liste sichtbar von der gemeldeten ab, das im späteren Findings-Bericht vermerken statt kommentarlos zu verwerfen.

## Schritt 3: `review`-Orchestrator aufrufen

Ruf den Skill `review` auf (`.claude/skills/review/SKILL.md`). Er verifiziert Branch/Diff selbst noch einmal, wertet die Perspektiven-Trigger-Tabelle aus (dort geführt, synchron zu ADR 0040 Teil 2 — keine Kopie dieser Tabelle hier), ruft die zutreffenden `review-*`-Skills (`review-tests`, `review-requirements`, `review-security`, `review-architecture`, `review-ux`) **nacheinander in der Hauptsession** auf (kein Subagent, kein `model`-Parameter mehr nötig — es gibt keine Pro-Perspektive-Modellzuweisung mehr, siehe ADR 0040 Teil 2), protokolliert je Perspektive "gelaufen / geskippt (welcher Trigger)" und gibt eine konsolidierte Findings-Liste (Muss-Fix vs. Diskussion getrennt) zurück.

Warte auf die vollständige Rückgabe des `review`-Skills, bevor du weitermachst.

## Schritt 4: Findings per SendMessage zurückspielen

Übernimm das vom `review`-Skill gelieferte Protokoll (alle fünf Perspektiven, gelaufen ja/nein mit Trigger-Begründung, Findings-Kurzfassung je gelaufener Perspektive) unverändert für den späteren Abschlussbericht an den Nutzer.

Gibt es Muss-Fix-Findings: Schick die konsolidierte Findings-Liste per `SendMessage` an denselben, weiterhin offenen `developer`-Subagenten (nicht an einen neuen Lauf) — er arbeitet sie über seinen Folgeauftrag "Findings beheben" ab, wiederholt seinen Qualitätscheck, committet, und antwortet mit dem Folgebericht `## Abschlussbericht (Folgeauftrag: Findings behoben)`.

Gibt es keine Muss-Fix-Findings (nur Diskussionspunkte oder gar keine Findings): direkt weiter zu Schritt 6 (PR-Erstellung), kein SendMessage nötig.

Schlägt `SendMessage` fehl: siehe Abschnitt "Recovery" unten.

## Schritt 5: Folgebericht auswerten

Format (Feldnamen `**Feature-Branch:**`, `**Commit-Stand:**`, Abschnitte "Behobene Findings" / "Bewusst nicht behoben" / "Tests & Codequalität") siehe `.claude/agents/developer.md`.

Verifiziere Branch/Status/Diff erneut mechanisch wie in Schritt 2 (dieselben drei Prüfungen). Findings, die laut Bericht "bewusst nicht behoben" wurden: kurz eigenständig plausibilisieren (nicht blind übernehmen) — wirkt die Begründung tragfähig, akzeptieren und im späteren PR-Bericht vermerken; wirkt sie nicht tragfähig, per SendMessage nachfragen/insistieren, bevor es weitergeht.

Kein eigener erneuter Testlauf durch den Orchestrator (bewusste Rollenteilung: TDD bleibt bei `developer`, Testqualität wird vom `review-tests`-Skill geprüft) — "Tests & Codequalität: grün" im Bericht wird als Aussage übernommen, nicht selbst nachgestellt.

Nach Bestätigung geht es weiter zu Schritt 6 (PR-Erstellung) bzw., falls die Findings aus einer Copilot-Runde (Schritt 7) stammten, zurück in den Copilot-Ablauf (erneuter Push statt neuem PR).

## Schritt 6: Commit, Push, Pull Request

1. Falls seit dem letzten Zwischencommit noch uncommittete Änderungen bestehen: committen, mit der im Projekt üblichen Commit-Konvention (siehe `CLAUDE.md`, Conventional Commits).
2. Push den Feature-Branch (`git push -u origin <branch>`), nicht `main`.
3. Eröffne einen PR mit `gh pr create`. Halte dich an eine vorhandene `.github/pull_request_template.md`, sonst mindestens: Bezug zur Spec/zum Issue, kurze Zusammenfassung (Was und Warum), Testplan/was geprüft wurde.
4. Setz direkt danach das Board-Statusfeld der Spec auf `Review` (ADR [`decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md`](../../../specs/decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md), Abschnitt 4):

   ```bash
   PYTHONPATH=scripts/github-project-sync/src python3 -m github_project_sync --only NNNN --runtime-status "Review" --pr-number <PR-Nummer>
   ```

   Ein früherer, verfrühter `Implemented`-Bump des Spec-Status direkt nach der PR-Erstellung entfällt ersatzlos (ADR 0037, Abschnitt 4) — die eigentliche Finalisierung (Spec-Datei-Status auf `Implemented`) übernimmt seit ADR 0037 die automatische PR-Merge-Erkennung beim nächsten regulären `github-project-sync`-Lauf, siehe `.claude/skills/github-project-sync/SKILL.md` (Fall `finalized_from_pr`).

## Schritt 7: Copilot-Review anfordern und auswerten

Jeder PR mit mindestens einer Code-Datei im Diff (mind. eine Datei unter `backend/src`, `backend/tests`, `frontend/src`, `frontend/tests` oder Äquivalent) bekommt zusätzlich zur Review-Runde aus Schritt 3 ein automatisiertes Copilot-Review — feste Projektkonvention (`CLAUDE.md`), kein optionaler Schritt. **Ausnahme:** Ändert der PR ausschließlich Doku-/Spec-Dateien (`specs/`, `docs/`, `*.md`, reine Config-Kommentare) ohne jede Code-Datei, entfällt dieser gesamte Schritt (kein Anfordern, kein Warten, kein Auswerten) — im Abschlussbericht an den Nutzer kurz vermerken, dass Schritt 7 aus diesem Grund übersprungen wurde. Diese Nicht-Code-Definition ist **wortgleich identisch** mit dem Skip-Trigger von `review-tests` (siehe `.claude/skills/review-tests/SKILL.md`, Abschnitt "Wann dieser Skill übersprungen wird") — beide Stellen bei künftigen Änderungen synchron halten.

1. **Anfordern:** `gh pr edit <PR-Nummer> --add-reviewer "@copilot"` direkt nach dem Eröffnen des PR in Schritt 6 (nur falls die obige Bedingung zutrifft).
2. **Warten:** Copilot braucht üblicherweise ein bis wenige Minuten. Poll in angemessenen Abständen (z.B. alle 20-30s, mit vernünftigem Timeout statt endlos) `gh pr view <PR-Nummer> --json reviewRequests,reviews` — fertig ist es, sobald `reviewRequests` keinen Copilot-Eintrag mehr enthält bzw. `reviews` einen Eintrag mit `author.login == "copilot-pull-request-reviewer"` zeigt. Nicht selbst raten/simulieren, was das Review ergibt.
3. **Kommentare holen:** `gh api repos/<owner>/<repo>/pulls/<PR-Nummer>/comments --paginate` liefert die Inline-Findings (Autor `Copilot`).
4. **Bewerten wie jeden anderen Review-Fund:** Jeden Kommentar am tatsächlichen Code prüfen (lesen, nicht nur den Kommentartext glauben) — echtes Problem oder Fehlalarm/bereits abgedeckt? Bei echten Findings: per `SendMessage` an denselben, weiterhin offenen `developer`-Subagenten zur Behebung geben (Test zuerst, falls eine Testlücke der Grund war, dann Fix, dann Commit — gleicher Maßstab wie Schritt 4/5), warten auf den Folgebericht. Bei Fehlalarmen: kurz im Abschlussbericht an den Nutzer begründen, warum kein Fix nötig war, statt kommentarlos zu ignorieren.
5. **Nach Fixes:** erneuter Push (kein neuer PR nötig, derselbe Branch).
6. **Antworten:** Auf jeden Copilot-Kommentar per `gh api repos/<owner>/<repo>/pulls/<PR-Nummer>/comments/<comment-id>/replies -f body="..."` kurz antworten — was gefixt wurde (mit Commit-Referenz) oder warum bewusst nicht.

## Recovery: `SendMessage` schlägt fehl

Ist das Subagenten-Fenster des `developer`-Laufs bereits geschlossen (z.B. Timeout, Sitzung beendet) und `SendMessage` liefert keine Antwort/schlägt sichtbar fehl — insbesondere relevant bei der ggf. längeren Wartezeit bis zum Copilot-Review in Schritt 7 —, nicht stillschweigend scheitern lassen und nicht die gesammelten Findings verwerfen:

1. Findings/offene Punkte (aus Review-Runde und/oder Copilot) vollständig schriftlich festhalten, bevor irgendetwas anderes passiert.
2. Aktuellen Branch-/Commit-Stand prüfen (`git status`, `git log -1`) — der bisherige Fortschritt bleibt im Feature-Branch erhalten, unabhängig vom Subagenten-Fenster.
3. Neuen `developer`-Lauf starten (Agent-Tool, `subagent_type: developer`, Standard-Modell), diesmal mit explizitem Kontext-Reload im Prompt: Spec-Nummer/-Pfad, exakter Feature-Branch-Name (Hinweis, dass er bereits existiert und weiterverwendet werden soll, nicht neu von `main` abgezweigt wird), sowie die vollständige Liste der in Schritt 1 dieses Recovery-Abschnitts festgehaltenen, noch offenen Findings. Der neue Lauf beginnt effektiv beim Folgeauftrag "Findings beheben" (siehe `developer.md`) mit bereits vorhandenem Branch, nicht bei dessen Schritt 0.
4. Danach normal mit Schritt 5 dieses Skills weitermachen (Folgebericht auswerten).

## Abschlussbericht an den Nutzer

Nach Abschluss (PR eröffnet, Copilot-Review ausgewertet oder aus genanntem Grund übersprungen) fasse für den Nutzer zusammen: PR-Link, das vom `review`-Skill gelieferte Protokoll (alle fünf Perspektiven, gelaufen ja/nein mit Begründung, Findings-Kurzfassung inkl. behobener/bewusst nicht behobener), Copilot-Ergebnis (falls gelaufen), sowie jede Stelle, an der du selbst eine technische Detailentscheidung getroffen hast (z.B. bei einem nicht-exakten Anker-Match oder einem SendMessage-Recovery-Fall).
