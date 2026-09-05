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
4. Board-Fähigkeit einmal messen — hier und nicht erst in Schritt 6, weil der PR-Body aus Schritt 6.3 den Abschnitt `## Lokal nachzuholen` mitbringen muss, falls etwas ausgelassen wird:

   ```bash
   python3 scripts/gh-board.py capabilities
   ```

   Auswertung und Verhalten stehen vollständig in `.claude/skills/github-board/SKILL.md`, Abschnitt „Board nicht erreichbar" — hier nicht wiederholen. Betroffen sind in diesem Skill `set-status Review` (Schritt 6.4), `finalize` (Schritt 8) und ein etwaiges `set-status In Progress` vor dem `developer`-Start. Push, PR-Eröffnung, Copilot-Runde und Review laufen davon unberührt weiter.

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
2. Push den Feature-Branch (`git push -u origin <branch>`), nicht `main`. Unverändert, unabhängig davon, ob der Branch von `developer` selbst oder bereits vorher von `spec-writer` mitsamt Spec-Commit angelegt wurde (ADR [`decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md`](../../../specs/decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md)) — in beiden Fällen liegt zu diesem Zeitpunkt ein lokal vollständiger, committeter Branch vor, der als Ganzes gepusht wird; der Spec-Commit landet dadurch im selben PR wie die Implementierung, nicht in einem separaten.
3. Eröffne einen PR mit `gh pr create`. Halte dich an eine vorhandene `.github/pull_request_template.md`, sonst mindestens: Bezug zur Spec/zum Issue, kurze Zusammenfassung (Was und Warum), Testplan/was geprüft wurde.

   **Pflicht, kein Platzhalter zum Stehenlassen:** Der PR-**Body** enthält die ausgefüllte Zeile `Closes #<Issue-Nummer>` (die Vorlage bringt sie mit `#NNN` mit). Die Issue-Nummer ist bei neuen Specs identisch mit der Spec-Nummer; bei Altspecs `0001`–`0065` steht sie in der `**Bezug:**`-Zeile der Spec-Datei. Nur diese Zeile erzeugt die strukturierte Verknüpfung zwischen PR und Issue (beidseitig sichtbar als "Linked issues"/"Linked pull requests") und lässt GitHub das Issue beim Merge nach `main` selbst schließen; ein bloßer Fließtext-Verweis erzeugt nur einen Timeline-Eintrag. Fehlt sie, bricht die Finalisierung in Schritt 8 ab.

   Das Keyword gehört ausschließlich in den Body — **nie** in eine Commit-Nachricht und **nie** in den PR-Titel: Das Repo squasht mit `COMMIT_MESSAGES` und `COMMIT_OR_PR_TITLE`, beide Texte wandern in Merge-Commit, Changelog und den Body des release-please-PRs, wo das Keyword beim nächsten Release-Merge erneut ausgewertet würde.

   Direkt nach dem Eröffnen prüfbar, ohne auf den Merge zu warten: `gh pr view <PR-Nummer> --json closingIssuesReferences` muss einen Eintrag mit der Issue-Nummer und dem Repository `TheRealKoller`/`photosort` zeigen.
4. Setz direkt danach das Board-Statusfeld der Spec auf `Review` (ADR [`decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md`](../../../specs/decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md), Abschnitt 4):

   ```bash
   python3 scripts/gh-board.py set-status --issue <Issue-Nummer> --status Review
   ```

   Die Issue-Nummer ist bei neuen Specs identisch mit der Spec-Nummer (`specs/features/0262-*.md` gehört zu Issue #262); bei Altspecs `0001`–`0065` steht sie in der `**Bezug:**`-Zeile der Spec-Datei.

   **Meldet die Messung aus Schritt 2.4 `status-review` als blockiert**, wird dieser Aufruf **nicht** abgesetzt und der Ablauf läuft trotzdem weiter (der PR existiert, das ist der wichtigere Teil). Der PR-Body aus 6.3 trägt dann zusätzlich den Abschnitt `## Lokal nachzuholen` — mit Schrittname, Nachhol-Befehl und dem festen Begründungssatz aus `.claude/skills/github-board/SKILL.md`, **ohne** `detail`, `note` oder irgendeine `gh`-Meldung. Dasselbe gilt für `abschluss-finalisieren` aus Schritt 8; beide Einträge stehen dann in einem gemeinsamen Abschnitt. Ist der PR-Body zu diesem Zeitpunkt bereits geschrieben, wird er einmal per `gh pr edit <PR-Nummer> --body-file <datei>` nachgezogen (nie über die Kommandozeile). Trägt auch dieser Kanal in dieser Umgebung nicht, bleibt es beim Chat-Bericht — und der sagt ausdrücklich, dass er der einzige Träger ist.

   Ein früherer, verfrühter `Implemented`-Bump des Spec-Status direkt nach der PR-Erstellung entfällt ersatzlos (ADR 0037, Abschnitt 4) — die eigentliche Finalisierung (Spec-Datei-Status auf `Implemented`) passiert erst in Schritt 8, nach Review und Copilot-Auswertung, aber noch **vor** dem Merge im selben PR.

## Schritt 7: Copilot-Review anfordern und auswerten

Jeder PR mit mindestens einer Code-Datei im Diff (mind. eine Datei unter `backend/src`, `backend/tests`, `frontend/src`, `frontend/tests` oder Äquivalent) bekommt zusätzlich zur Review-Runde aus Schritt 3 ein automatisiertes Copilot-Review — feste Projektkonvention (`CLAUDE.md`), kein optionaler Schritt. **Ausnahme:** Ändert der PR ausschließlich Doku-/Spec-Dateien (`specs/`, `docs/`, `*.md`, reine Config-Kommentare) ohne jede Code-Datei, entfällt dieser gesamte Schritt (kein Anfordern, kein Warten, kein Auswerten) — im Abschlussbericht an den Nutzer kurz vermerken, dass Schritt 7 aus diesem Grund übersprungen wurde. Diese Nicht-Code-Definition ist **wortgleich identisch** mit dem Skip-Trigger von `review-tests` (siehe `.claude/skills/review-tests/SKILL.md`, Abschnitt "Wann dieser Skill übersprungen wird") — beide Stellen bei künftigen Änderungen synchron halten.

1. **Anfordern:** `gh pr edit <PR-Nummer> --add-reviewer "@copilot"` direkt nach dem Eröffnen des PR in Schritt 6 (nur falls die obige Bedingung zutrifft).
2. **Warten:** Copilot braucht üblicherweise ein bis wenige Minuten. Poll in angemessenen Abständen (z.B. alle 20-30s, mit vernünftigem Timeout statt endlos) `gh pr view <PR-Nummer> --json reviewRequests,reviews` — fertig ist es, sobald `reviewRequests` keinen Copilot-Eintrag mehr enthält bzw. `reviews` einen Eintrag mit `author.login == "copilot-pull-request-reviewer"` zeigt. Nicht selbst raten/simulieren, was das Review ergibt.
3. **Kommentare holen:** `gh api repos/<owner>/<repo>/pulls/<PR-Nummer>/comments --paginate` liefert die Inline-Findings (Autor `Copilot`).
4. **Bewerten wie jeden anderen Review-Fund:** Jeden Kommentar am tatsächlichen Code prüfen (lesen, nicht nur den Kommentartext glauben) — echtes Problem oder Fehlalarm/bereits abgedeckt? Bei echten Findings: per `SendMessage` an denselben, weiterhin offenen `developer`-Subagenten zur Behebung geben (Test zuerst, falls eine Testlücke der Grund war, dann Fix, dann Commit — gleicher Maßstab wie Schritt 4/5), warten auf den Folgebericht. Bei Fehlalarmen: kurz im Abschlussbericht an den Nutzer begründen, warum kein Fix nötig war, statt kommentarlos zu ignorieren.
5. **Nach Fixes:** erneuter Push (kein neuer PR nötig, derselbe Branch).
6. **Antworten:** Auf jeden Copilot-Kommentar per `gh api repos/<owner>/<repo>/pulls/<PR-Nummer>/comments/<comment-id>/replies -f body="..."` kurz antworten — was gefixt wurde (mit Commit-Referenz) oder warum bewusst nicht.

## Schritt 8: Finalisierung im selben PR (vor dem Merge)

Regelweg: Der Spec-Status wird **im Feature-PR selbst** auf `Implemented` gesetzt, nicht in einem Nachzieh-PR nach dem Merge. Ohne diesen Schritt entsteht genau das separate Zwei-Zeilen-PR, das eine komplette CI-Pipeline für eine reine Metadaten-Änderung kostet.

**Wann:** sobald die Review-Runde (Schritt 3–5) und das Copilot-Review (Schritt 7) ausgewertet und alle Muss-Fix-Findings behoben sind — und zwar **gebündelt mit dem Push dieser letzten Fixes** (erst finalisieren, dann beide Commits in einem `git push`), damit kein zusätzlicher CI-Lauf entsteht. Gab es keine Fixes mehr, ist es ein eigener, letzter Commit auf dem Feature-Branch. Nie früher: ein noch nicht reviewter Stand darf nie als umgesetzt geführt werden.

1. Finalisieren (`NNNN` = Spec-Nummer, `<PR-Nummer>` = der PR aus Schritt 6):

   ```bash
   python3 scripts/gh-board.py finalize --spec NNNN --pr-number <PR-Nummer>
   ```

   Erwartete Ausgabe: `{"spec_number": ..., "issue_number": ..., "pr_number": ..., "status_line": "Implemented ([PR #NNN](...))", "status": "Done"}`. Der Aufruf schreibt die `**Status:**`-Zeile der Spec-Datei um und setzt danach den Endzustand auf dem Board (Spalte `Done`, Issue geschlossen). Bei einer Altspec `0001`–`0065` zusätzlich `--issue <Issue-Nummer>` angeben.

2. Ein `{"error": "..."}` **nicht** ignorieren und **nicht** umgehen (z.B. durch manuelles Editieren der Status-Zeile): Meldung unverändert an Daniel weitergeben. Eine bereits umgeschriebene Spec-Datei muss dafür **nicht** zurückgenommen werden — derselbe Aufruf ist unverändert wiederholbar, solange die bereits geschriebene Statuszeile exakt die ist, die er erneut schreiben würde (gleiche Spec, gleicher PR). Ein bereits geschlossenes Issue ist ebenfalls kein Fehler mehr. Bricht der Aufruf mit "Zustand 'closed'" ab, ist der PR ohne Merge geschlossen worden — dann wird gar nicht finalisiert.

   **Fehlerfall "nicht verknüpft":** Meldet der Aufruf, dass `closingIssuesReferences` keinen passenden Eintrag enthält, fehlt die Closing-Zeile aus Schritt 6.3 im PR-Body (oder sie nennt die falsche Nummer). Dann den Body nachziehen — Body in eine temporäre Datei schreiben, Zeile ergänzen, `gh pr edit <PR-Nummer> --body-file <datei>` (nie über die Kommandozeile) — und `finalize` unverändert wiederholen. Der Abbruch passiert vor jedem Schreibzugriff: Spec-Datei und Board sind unangetastet, es ist nichts zurückzunehmen. Meldet er stattdessen, der PR ziele nicht auf den Default-Branch, ist der PR gegen den falschen Basis-Branch eröffnet worden — das ist ein Fall für Daniel, nicht für eine Korrektur nebenbei. Nennt die Meldung ein zu altes `gh` (Feld unbekannt; die verlangte Mindestversion nennt die Meldung selbst, gepflegt als Konstante `MIN_GH_VERSION` in `scripts/gh-board.py`), ist es ein Werkzeugproblem und **kein** Beleg für eine fehlende Verknüpfung — dann `gh` aktualisieren statt eine Zeile nachzutragen, die längst da ist.

   **Meldet die Messung aus Schritt 2.4 `abschluss-finalisieren` als blockiert**, ist davon nur der **Board-Anteil** betroffen. Der `finalize`-Aufruf wird trotzdem abgesetzt: Er schreibt die `**Status:**`-Zeile der Spec-Datei, **bevor** er das Board berührt, und scheitert erst danach — die Statuszeile landet damit noch im Feature-PR. Der erwartete Fehlschlag am Board-Anteil ist dann **keine** Meldung an Daniel im üblichen Sinn, sondern ein als ausgelassen gemeldeter Schritt: `Done` und der daran hängende Issue-Abschluss kommen mit demselben, unverändert wiederholbaren Befehl in den Abschnitt `## Lokal nachzuholen` (PR-Body und Chat-Bericht). Weiter geht es mit Punkt 3.

3. Die geänderte Spec-Datei (`specs/features/NNNN-*.md`) committen, Konvention: `chore(specs): Spec NNNN finalisieren (PR #<PR-Nummer>)`, und zusammen mit ggf. noch offenen Fix-Commits pushen.

4. Danach übernimmt Daniel: Freigabe und Merge. **Kein** automatisches Mergen durch dich.

**Wird der PR wider Erwarten nicht gemergt** (Branch verworfen): Board-Spalte und Issue-Zustand stehen dann auf `Done`/geschlossen, obwohl `main` die Spec weiter als `Accepted` führt. Es gibt keinen Lauf mehr, der das automatisch aus der Datei zurückrechnet — den Board-Wert in dem Fall gezielt zurücksetzen (`set-status --issue <NNN> --status Todo`), das Issue auf GitHub wieder öffnen und Daniel darauf hinweisen.

**Ausnahmefall (nicht Regelweg):** Wurde ein PR ohne diesen Schritt gemergt (Merge außerhalb des üblichen Ablaufs, abgebrochene Session), finalisiert derselbe Aufruf **ohne** `--pr-number` nachträglich — er sucht dann den gemergten, das Issue schließenden PR selbst (siehe `.claude/skills/github-board/SKILL.md`). Die dabei entstehende lokale Änderung braucht dann doch ein kleines Folge-PR. Genau das soll dieser Schritt vermeiden.

## Recovery: `SendMessage` schlägt fehl

Ist das Subagenten-Fenster des `developer`-Laufs bereits geschlossen (z.B. Timeout, Sitzung beendet) und `SendMessage` liefert keine Antwort/schlägt sichtbar fehl — insbesondere relevant bei der ggf. längeren Wartezeit bis zum Copilot-Review in Schritt 7 —, nicht stillschweigend scheitern lassen und nicht die gesammelten Findings verwerfen:

1. Findings/offene Punkte (aus Review-Runde und/oder Copilot) vollständig schriftlich festhalten, bevor irgendetwas anderes passiert.
2. Aktuellen Branch-/Commit-Stand prüfen (`git status`, `git log -1`) — der bisherige Fortschritt bleibt im Feature-Branch erhalten, unabhängig vom Subagenten-Fenster.
3. Neuen `developer`-Lauf starten (Agent-Tool, `subagent_type: developer`, Standard-Modell), diesmal mit explizitem Kontext-Reload im Prompt: Spec-Nummer/-Pfad, exakter Feature-Branch-Name (Hinweis, dass er bereits existiert und weiterverwendet werden soll, nicht neu von `main` abgezweigt wird), sowie die vollständige Liste der in Schritt 1 dieses Recovery-Abschnitts festgehaltenen, noch offenen Findings. Der neue Lauf beginnt effektiv beim Folgeauftrag "Findings beheben" (siehe `developer.md`) mit bereits vorhandenem Branch, nicht bei dessen Schritt 0.
4. Danach normal mit Schritt 5 dieses Skills weitermachen (Folgebericht auswerten).

## Abschlussbericht an den Nutzer

Nach Abschluss (PR eröffnet, Copilot-Review ausgewertet oder aus genanntem Grund übersprungen, Spec im PR finalisiert) fasse für den Nutzer zusammen: PR-Link, Ergebnis der Finalisierung aus Schritt 8 (Statuszeile bzw. Fehlermeldung), das vom `review`-Skill gelieferte Protokoll (alle fünf Perspektiven, gelaufen ja/nein mit Begründung, Findings-Kurzfassung inkl. behobener/bewusst nicht behobener), Copilot-Ergebnis (falls gelaufen), sowie jede Stelle, an der du selbst eine technische Detailentscheidung getroffen hast (z.B. bei einem nicht-exakten Anker-Match oder einem SendMessage-Recovery-Fall).

Wurde wegen `board_reachable: false` ein Board-Schritt ausgelassen, trägt der Bericht zusätzlich denselben Abschnitt, der auch im PR-Body steht:

```markdown
## Lokal nachzuholen

Dieser Schritt wurde ausgelassen, weil sich das Projekt-Board in dieser Umgebung nicht auflösen
ließ (gemessen mit `python3 scripts/gh-board.py capabilities`). Die Befehle sind unverändert
wiederholbar und lokal nachzuholen.

- `status-review`: `python3 scripts/gh-board.py set-status --issue NNN --status Review`
- `abschluss-finalisieren`: `python3 scripts/gh-board.py finalize --spec NNNN --pr-number MMM`
```

Im Chat — und **nur** dort — kommt das Feld `detail` der Messung dazu, damit Daniel die Ursache sieht. In den PR-Body gelangt es nicht.
