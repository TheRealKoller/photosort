---
name: ship-feature
description: Koordiniert auf oberster Ebene (Orchestrator/Hauptsession) die Nachbereitung eines `developer`-Subagenten-Laufs — den `review`-Orchestrator-Skill aufrufen, Findings per SendMessage zurückspielen, Pull Request eröffnen, Copilot-Review anfordern/auswerten. Nutze diesen Skill IMMER, wenn eine `developer`-Subagenten-Antwort mit dem wörtlichen Anker `## Blockiert: Architektur-Konsultation nötig` oder `## Abschlussbericht` zurückkommt (auch `## Abschlussbericht (Folgeauftrag: Findings behoben)`) — das ist der verbindliche Übergabepunkt, an dem `developer` selbst keine weitere Verschachtelungsebene an Subagenten und keinen GitHub-Zugriff hat. Nicht nutzen für die Umsetzung selbst (dafür `developer`) oder das Schärfen einer Idee zur Spec (dafür `spec-writer`).

---

# Ship Feature — Review, PR und Copilot-Review vom Orchestrator

**GitHub-Erlaubnisstufe:** lesend und schreibend

Übernimmt genau die Verantwortung, die ein per Agent-Tool gestarteter `developer`-Subagent strukturell nicht selbst wahrnehmen kann: eine weitere Verschachtelungsebene an Subagenten (`architect` bei einer Planungslücke) und GitHub-Schreibzugriff (Push, PR-Erstellung, Copilot-Review). Die eigentliche Review-Prüfung übernimmt der Skill `review` (`.claude/skills/review/SKILL.md`) — dieser Skill hier ruft ihn nur auf und kümmert sich um alles davor und danach. `developer` bleibt für die Dauer dieses gesamten Ablaufs als offener Subagent ansprechbar (SendMessage), es wird für Folgeaufträge kein neuer Lauf gestartet, solange der Subagent noch erreichbar ist.

**Jeder GitHub-Zugriff läuft über eine Operation des Skills `github-access`.** Lade ihn einmal über das Skill-Werkzeug, an deinem ersten GitHub-Berührungspunkt (das ist Schritt 6), und arbeite danach für den Rest des Laufs mit dem geladenen Katalog. Dieser Skill hier nennt ausschließlich Operations-IDs und die Ablauf-Logik drumherum — wann eine Operation läuft, unter welcher Bedingung, wie ihr Ergebnis ausgewertet wird. Rein lokales `git` (`git status`, `git log`, `git diff`, `git push`) ist davon unberührt und steht weiterhin hier.

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
2. Push den Feature-Branch (`git push -u origin <branch>`), nicht `main`. Unverändert, unabhängig davon, ob der Branch von `developer` selbst oder bereits vorher von `spec-writer` mitsamt Spec-Commit angelegt wurde (ADR [`decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md`](../../../specs/decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md)) — in beiden Fällen liegt zu diesem Zeitpunkt ein lokal vollständiger, committeter Branch vor, der als Ganzes gepusht wird; der Spec-Commit landet dadurch im selben PR wie die Implementierung, nicht in einem separaten.
3. Eröffne einen PR: Operation `pr-erstellen`. Halte dich an eine vorhandene `.github/pull_request_template.md`, sonst mindestens: Bezug zur Spec/zum Issue, kurze Zusammenfassung (Was und Warum), Testplan/was geprüft wurde.

   **Pflicht, kein Platzhalter zum Stehenlassen:** Der PR-**Body** enthält die ausgefüllte Zeile `Closes #<Issue-Nummer>` (die Vorlage bringt sie mit `#NNN` mit). Die Issue-Nummer ist bei neuen Specs identisch mit der Spec-Nummer; bei Altspecs `0001`–`0065` steht sie in der `**Bezug:**`-Zeile der Spec-Datei. Nur diese Zeile erzeugt die strukturierte Verknüpfung zwischen PR und Issue (beidseitig sichtbar als "Linked issues"/"Linked pull requests") und lässt GitHub das Issue beim Merge nach `main` selbst schließen; ein bloßer Fließtext-Verweis erzeugt nur einen Timeline-Eintrag. Fehlt sie, bricht die Finalisierung in Schritt 8 ab.

   Das Keyword gehört ausschließlich in den Body — **nie** in eine Commit-Nachricht und **nie** in den PR-Titel: Das Repo squasht mit `COMMIT_MESSAGES` und `COMMIT_OR_PR_TITLE`, beide Texte wandern in Merge-Commit, Changelog und den Body des release-please-PRs, wo das Keyword beim nächsten Release-Merge erneut ausgewertet würde.

   Direkt nach dem Eröffnen prüfbar, ohne auf den Merge zu warten: `pr-verknuepfung-lesen` muss einen Eintrag mit der Issue-Nummer und dem Repository dieser Story zeigen.
4. **Lies den Board-Wert einmal zurück — setz ihn nicht.** `Review` schreibt GitHub selbst, ausgelöst durch die `Closes #NNN`-Zeile aus 6.3 (Workflow `Pull request linked to issue`). Lies ihn mit `board-status-und-prioritaet-lesen`; ausgewertet wird der Knoten mit `project.number == 8`, nie schlicht `nodes[0]`.

   Dieser Schritt existiert, weil sich mit dem Übergang auf native Workflows die Richtung des Fehlers umdreht: Ein versehentlich deaktivierter Workflow schreibt **gar nichts**, und eine Karte, die auf `In Progress` liegen bleibt, ist von einer Karte, an der gerade gearbeitet wird, nicht zu unterscheiden. Der Zustand der Workflows ist per API nicht überwachbar — das Zurücklesen ist der einzige Nachweis, dass der Übergang stattgefunden hat.

   - **Steht `Review`:** nichts zu tun, im Abschlussbericht einzeilig vermerken.
   - **Steht etwas anderes:** GitHub verarbeitet die Verknüpfung asynchron, unmittelbar nach `pr-erstellen` kann der alte Wert noch stehen. Deshalb **einmal** kurz warten (wenige Sekunden) und ein zweites Mal lesen, bevor daraus ein Befund wird — sonst meldet jeder Lauf einen Fehlschlag, den es nicht gibt.
   - **Steht auch dann nicht `Review`** (oder scheitert der Lesebefehl selbst): Der Übergang ist ausgeblieben, in aller Regel, weil der Workflow im Projekt deaktiviert wurde. Den Wert **nicht** stillschweigend selbst nachsetzen — das verdeckte genau die Ursache, die dieser Schritt sichtbar machen soll. Stattdessen `board-status-setzen` mit Wert `Review` in den Abschnitt `## Lokal nachzuholen` (PR-Body und Chat-Bericht), mit der Nachhol-Zeile aus dem Katalogeintrag. Regeln zu Form und Inhalt dieses Abschnitts vollständig im Skill `github-access` — hier nicht wiederholen. Ist der PR-Body zu diesem Zeitpunkt bereits geschrieben, wird er einmal per `pr-body-schreiben` nachgezogen.

   Ein früherer, verfrühter `Implemented`-Bump des Spec-Status direkt nach der PR-Erstellung entfällt ersatzlos — die Finalisierung passiert erst in Schritt 8, nach Review und Copilot-Auswertung, aber noch **vor** dem Merge im selben PR.

## Schritt 7: Copilot-Review anfordern und auswerten

Jeder PR mit mindestens einer Code-Datei im Diff (mind. eine Datei unter `backend/src`, `backend/tests`, `frontend/src`, `frontend/tests` oder Äquivalent) bekommt zusätzlich zur Review-Runde aus Schritt 3 ein automatisiertes Copilot-Review — feste Projektkonvention (`CLAUDE.md`), kein optionaler Schritt. **Ausnahme:** Ändert der PR ausschließlich Doku-/Spec-Dateien (`specs/`, `docs/`, `*.md`, reine Config-Kommentare) ohne jede Code-Datei, entfällt dieser gesamte Schritt (kein Anfordern, kein Warten, kein Auswerten) — im Abschlussbericht an den Nutzer kurz vermerken, dass Schritt 7 aus diesem Grund übersprungen wurde. Diese Nicht-Code-Definition ist **wortgleich identisch** mit dem Skip-Trigger von `review-tests` (siehe `.claude/skills/review-tests/SKILL.md`, Abschnitt "Wann dieser Skill übersprungen wird") — beide Stellen bei künftigen Änderungen synchron halten.

1. **Anfordern:** `copilot-review-anfordern` direkt nach dem Eröffnen des PR in Schritt 6 (nur falls die obige Bedingung zutrifft).
2. **Warten:** Copilot braucht üblicherweise ein bis wenige Minuten. Poll in angemessenen Abständen (z.B. alle 20-30s, mit vernünftigem Timeout statt endlos) `pr-reviewstand-lesen` — fertig ist es, sobald der Copilot-Eintrag aus `reviewRequests` verschwunden bzw. in `reviews` aufgetaucht ist (maßgeblicher Anmeldename und Auswertungsgrenze stehen im Katalogeintrag). Nicht selbst raten/simulieren, was das Review ergibt.
3. **Kommentare holen:** `pr-reviewkommentare-lesen` liefert die Inline-Findings am eigenen PR.
4. **Bewerten wie jeden anderen Review-Fund:** Jeden Kommentar am tatsächlichen Code prüfen (lesen, nicht nur den Kommentartext glauben) — echtes Problem oder Fehlalarm/bereits abgedeckt? Bei echten Findings: per `SendMessage` an denselben, weiterhin offenen `developer`-Subagenten zur Behebung geben (Test zuerst, falls eine Testlücke der Grund war, dann Fix, dann Commit — gleicher Maßstab wie Schritt 4/5), warten auf den Folgebericht. Bei Fehlalarmen: kurz im Abschlussbericht an den Nutzer begründen, warum kein Fix nötig war, statt kommentarlos zu ignorieren.
5. **Nach Fixes:** erneuter Push (kein neuer PR nötig, derselbe Branch).
6. **Antworten:** Auf jeden Copilot-Kommentar mit `pr-reviewkommentar-beantworten` kurz antworten — was gefixt wurde (mit Commit-Referenz) oder warum bewusst nicht.

## Schritt 8: Finalisierung im selben PR (vor dem Merge)

Regelweg: Der Spec-Status wird **im Feature-PR selbst** auf `Implemented` gesetzt, nicht in einem Nachzieh-PR nach dem Merge. Ohne diesen Schritt entsteht genau das separate Zwei-Zeilen-PR, das eine komplette CI-Pipeline für eine reine Metadaten-Änderung kostet.

**Wann:** sobald die Review-Runde (Schritt 3–5) und das Copilot-Review (Schritt 7) ausgewertet und alle Muss-Fix-Findings behoben sind — und zwar **gebündelt mit dem Push dieser letzten Fixes** (erst finalisieren, dann beide Commits in einem `git push`), damit kein zusätzlicher CI-Lauf entsteht. Gab es keine Fixes mehr, ist es ein eigener, letzter Commit auf dem Feature-Branch. Nie früher: ein noch nicht reviewter Stand darf nie als umgesetzt geführt werden.

**Was hier ausdrücklich *nicht* passiert:** kein Schließen des Issues, kein Setzen von `Done`. Beides erledigt GitHub beim Merge — das Keyword `Closes #NNN` schließt das Issue, der Workflow `Item closed` zieht die Karte auf `Done`. Ein vorgezogenes `Done` würde eine Story als erledigt führen, die noch nicht in `main` ist.

1. **Verknüpfung prüfen** mit `pr-verknuepfung-lesen`, für die PR-Nummer aus Schritt 6:

   Erwartet: `closingIssuesReferences` enthält einen Eintrag mit der Issue-Nummer dieser Story, und `baseRefName` ist `main`. Erst wenn beides zutrifft, wird finalisiert — die Statuszeile `Implemented` ist eine Aussage über einen PR, der das Issue tatsächlich schließen wird.

   **Fehlerfall „nicht verknüpft":** Es fehlt die Closing-Zeile aus Schritt 6.3 im PR-Body (oder sie nennt die falsche Nummer). Dann den Body nachziehen — Body in eine temporäre Datei schreiben, Zeile ergänzen, `pr-body-schreiben` — und die Prüfung wiederholen. Es ist nichts zurückzunehmen: Die Prüfung steht **vor** jedem Schreibzugriff. Danach lohnt ein erneutes Zurücklesen des Board-Werts aus 6.4, denn erst mit der Verknüpfung kann der Workflow greifen.

   **Fehlerfall „falscher Basis-Branch":** Ist `baseRefName` nicht `main`, ist der PR gegen den falschen Branch eröffnet worden. Das ist ein Fall für Daniel, nicht für eine Korrektur nebenbei — nicht finalisieren, melden.

2. **Die `**Status:**`-Zeile der Spec-Datei** (`specs/features/NNNN-*.md`) lokal auf die finale Form setzen:

   ```
   **Status:** Implemented ([PR #<MMM>](https://github.com/TheRealKoller/photosort/pull/<MMM>))
   ```

   Eine rein lokale Textänderung mit dem Editier-Werkzeug — kein Board-Zugriff, kein Netzwerk, nichts, was fehlschlagen könnte.

3. Die geänderte Spec-Datei committen, Konvention: `chore(specs): Spec NNNN finalisieren (PR #<MMM>)`, und zusammen mit ggf. noch offenen Fix-Commits pushen.

4. Danach übernimmt Daniel: Freigabe und Merge. **Kein** automatisches Mergen durch dich.

**Wird der PR ohne Merge geschlossen** (Branch verworfen): Das Issue bleibt offen — es hing am Keyword, das nur beim Merge greift —, aber die Karte steht seit der PR-Verknüpfung auf `Review` und behauptet dort eine Prüfung, die es nicht mehr gibt. Diesen einen Übergang setzt die Session selbst zurück, weil GitHub für ein geschlossenes, nicht gemergtes PR keinen Workflow kennt: `board-status-setzen` mit Wert `In Progress`.

`In Progress` und nicht `Ready`: Die Spec existiert, der Branch existiert, die Arbeit ist begonnen. Führt die Spec-Datei auf dem Branch bereits `Implemented`, gehört das ebenfalls zurückgenommen — dieser Stand ist nicht ausgeliefert. Daniel darauf hinweisen.

**Ausnahmefall (nicht Regelweg):** Wurde ein PR ohne Schritt 8 gemergt (Merge außerhalb des üblichen Ablaufs, abgebrochene Session), ist am Board nichts zu tun — Issue und Karte haben ihren Endzustand über das Keyword und den `Item closed`-Workflow bereits erreicht. Offen bleibt allein die `**Status:**`-Zeile der Spec-Datei in `main`; sie braucht dann doch ein kleines Folge-PR. Genau das soll dieser Schritt vermeiden.

## Recovery: `SendMessage` schlägt fehl

Ist das Subagenten-Fenster des `developer`-Laufs bereits geschlossen (z.B. Timeout, Sitzung beendet) und `SendMessage` liefert keine Antwort/schlägt sichtbar fehl — insbesondere relevant bei der ggf. längeren Wartezeit bis zum Copilot-Review in Schritt 7 —, nicht stillschweigend scheitern lassen und nicht die gesammelten Findings verwerfen:

1. Findings/offene Punkte (aus Review-Runde und/oder Copilot) vollständig schriftlich festhalten, bevor irgendetwas anderes passiert.
2. Aktuellen Branch-/Commit-Stand prüfen (`git status`, `git log -1`) — der bisherige Fortschritt bleibt im Feature-Branch erhalten, unabhängig vom Subagenten-Fenster.
3. Neuen `developer`-Lauf starten (Agent-Tool, `subagent_type: developer`, Standard-Modell), diesmal mit explizitem Kontext-Reload im Prompt: Spec-Nummer/-Pfad, exakter Feature-Branch-Name (Hinweis, dass er bereits existiert und weiterverwendet werden soll, nicht neu von `main` abgezweigt wird), sowie die vollständige Liste der in Schritt 1 dieses Recovery-Abschnitts festgehaltenen, noch offenen Findings. Der neue Lauf beginnt effektiv beim Folgeauftrag "Findings beheben" (siehe `developer.md`) mit bereits vorhandenem Branch, nicht bei dessen Schritt 0.
4. Danach normal mit Schritt 5 dieses Skills weitermachen (Folgebericht auswerten).

## Abschlussbericht an den Nutzer

Nach Abschluss (PR eröffnet, Copilot-Review ausgewertet oder aus genanntem Grund übersprungen, Spec im PR finalisiert) fasse für den Nutzer zusammen: PR-Link, Ergebnis der Finalisierung aus Schritt 8 (Statuszeile bzw. Fehlermeldung), das vom `review`-Skill gelieferte Protokoll (alle fünf Perspektiven, gelaufen ja/nein mit Begründung, Findings-Kurzfassung inkl. behobener/bewusst nicht behobener), Copilot-Ergebnis (falls gelaufen), sowie jede Stelle, an der du selbst eine technische Detailentscheidung getroffen hast (z.B. bei einem nicht-exakten Anker-Match oder einem SendMessage-Recovery-Fall).

Blieb ein nativer Übergang aus oder schlug eine Board-Operation fehl, trägt der Bericht zusätzlich denselben Abschnitt, der auch im PR-Body steht — je Zeile die Operations-ID und die Nachhol-Zeile aus ihrem Katalogeintrag:

```markdown
## Lokal nachzuholen

Dieser Schritt ist fehlgeschlagen und wurde nicht nachgeholt. Die Befehle sind unverändert
wiederholbar und lokal nachzuholen.

- <Operations-ID>: <Nachhol-Zeile aus dem Katalogeintrag, mit den Nummern dieses Laufs>
```

Im Chat — und **nur** dort — kommt die wörtliche Fehlermeldung des **zuletzt** versuchten Wegs bzw. der tatsächlich vorgefundene Board-Wert dazu, damit Daniel die Ursache sieht. In den PR-Body gelangt beides nicht; dort steht ausschließlich selbst erzeugter Inhalt (Skill `github-access`, Regel 4.3).
