# 0414 - Umsetzungsstand steht vor dem Copilot-Review im Pull Request

**Status:** Accepted
**Erstellt:** 2026-10-01
**Bezug:** [Issue #414](https://github.com/TheRealKoller/photosort/issues/414), ADR [`0128`](../decisions/0128-die-spec-statuszeile-steht-vor-dem-copilot-review-im-pull-request.md)

**Umfang:** über dem Richtwert von rund 200 Zeilen, weil die Spec die neue Schrittfolge von
`ship-feature` einzeln festlegt, die Code, Ablauftext und zwei pinnende Tests gleichlautend tragen
müssen.

## Ziel

Im Copilot-Review eines Feature-Pull-Requests taucht wiederholt der Befund auf, die Spec-Datei führe
den Umsetzungsstand noch als nicht umgesetzt, obwohl genau dieser Pull Request die Umsetzung ist.
Das ist ein Artefakt der Reihenfolge: Die Statuszeile wird erst nach dem Copilot-Review gesetzt.
Jedes Auftreten muss trotzdem geprüft, bewertet und beantwortet werden.

Der Stand soll bereits geschrieben sein, wenn das Copilot-Review angefordert wird. Er steht dann
ausschließlich in dem Pull Request, der gerade geprüft wird; außerhalb dieses Branches bleibt die
Spec bis zum Merge unverändert nicht umgesetzt.

## User Story

Als Prüfer eines Feature-Pull-Requests möchte ich, dass der Umsetzungsstand der Spec bereits
geschrieben ist, wenn das Copilot-Review angefordert wird, damit ich keine wiederkehrenden
Scheinbefunde mehr bewerten und beantworten muss.

## Akzeptanzkriterien

- [ ] **AK 1:** Wenn `copilot-review-anfordern` aufgerufen wird, führt die Spec im Head des Feature-PRs `**Status:** Implemented ([PR #<MMM>](https://github.com/TheRealKoller/photosort/pull/<MMM>))`. <MMM> ist die Nummer genau dieses PRs. Prüfbar an `ship-feature`: Setzen, Committen und Pushen der Zeile stehen vor der Copilot-Anforderung. Entfällt das Copilot-Review (reiner Doku-/Spec-PR), wird die Zeile an derselben Stelle gesetzt.
- [ ] **AK 2:** Bis zum Merge entsteht die Statuszeile ausschließlich durch Commit und Push auf den Feature-Branch. Kein Schritt schreibt dafür auf `main`, öffnet einen weiteren PR oder greift dafür auf Board oder Issue zu.
- [ ] **AK 3:** Die Zeile wird erst gesetzt, wenn drei Dinge vorliegen: die Review-Runde (Schritte 3–5) ist abgeschlossen, der PR ist eröffnet, und `pr-verknuepfung-lesen` hat die Closing-Referenz auf das Story-Issue und die Basis `main` bestätigt. Bei „falscher Basis-Branch“ wird keine Zeile gesetzt. Vorgezogen wird sie nur gegenüber dem Copilot-Review.
- [ ] **AK 4:** Je `ship-feature`-Lauf ist die Zahl der abgeschlossenen `ci`-Läufe (Ergebnis grün oder rot) nicht größer als in der bisherigen Reihenfolge. Ein durch `cancel-in-progress` abgebrochener Lauf zählt nicht. Ein zusätzlicher `pr-titel`-Lauf ist zulässig. Es entsteht kein zusätzlicher PR. Prüfbar: `ci.yml` trägt auf oberster Ebene genau einen Block mit `group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}` und `cancel-in-progress: true`. Am Umsetzungs-PR endet der Lauf der Eröffnung mit `cancelled`.
- [ ] **AK 5:** Wird ein PR ohne Merge geschlossen, setzt die Sitzung die Statuszeile auf dem Branch per eigenem Commit auf `**Status:** Accepted` zurück. Sie pusht ihn, solange der Remote-Branch existiert; sonst genügt der lokale Commit. Die Karte geht auf `In Progress`. `main` hat die Zeile nie geführt.
- [ ] **AK 6:** ADR 0042 und ADR 0063 tragen je einen `**Teilweise abgelöst:**`-Vermerk mit Verweis auf ADR 0128. ADR 0128 begründet die Reihenfolge, die Zählweise, den `concurrency`-Block und die Rücknahme.
- [ ] **AK 7:** `ship-feature` (Schritte 6–9, Ausnahmefall, Abschlussbericht), `developer.md` und `docs/ai-workflow.md` beschreiben die neue Reihenfolge. `**Status:** Implemented` steht in `ship-feature` genau einmal, und zwar in Schritt 6. Keine dieser Dateien beschreibt mehr, dass die Statuszeile nach dem Copilot-Review oder in Schritt 8 gesetzt wird.

## Datenmodell-Bezug

Keiner.

## Architektur / Umsetzung

**Ansatz (ADR [`0128`](../decisions/0128-die-spec-statuszeile-steht-vor-dem-copilot-review-im-pull-request.md)):** Die `**Status:**`-Zeile wird in `ship-feature` direkt nach der PR-Eröffnung und der Prüfung der Verknüpfung gesetzt, committet und gepusht, und erst danach wird `copilot-review-anfordern` aufgerufen. Damit der zusätzliche Push keinen zusätzlichen CI-Durchlauf erzeugt, bekommt `ci.yml` einen `concurrency`-Block je PR mit `cancel-in-progress`. Der Push der Statuszeile bricht so den Lauf der Eröffnung ab. Schritt 8 setzt keine Statuszeile mehr, sondern macht nur noch den Abgleich mit `main` und den letzten Push.

### Betroffene Dateien

- `.github/workflows/ci.yml`: ein `concurrency`-Block auf oberster Ebene (zwischen `permissions` und `jobs`), wörtlich:
  ```yaml
  concurrency:
    group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}
    cancel-in-progress: true
  ```
  Dazu ein kurzer Kommentar mit der Regel: was gilt (je PR höchstens ein laufender Lauf), wofür (`pull_request`; Pushes auf `main` fallen auf `run_id` zurück und brechen nie ab) und was bei Verletzung passiert (der Lauf der Eröffnung läuft voll durch, also ein CI-Durchlauf mehr je PR). Keine Ausdrücke in `run:`-Blöcken, kein Titel und kein Branchname im Schlüssel.
- `.claude/skills/ship-feature/SKILL.md`: Schritte 6, 7, 8 und 9 sowie der Abschlussbericht (Details unten).
- `.claude/agents/developer.md:209`: Statt „einmal als erste Handlung vor der Finalisierung“ heißt es künftig „einmal als erste Handlung von Schritt 8, vor dem letzten Push“.
- `docs/ai-workflow.md:58–62`: Tabellenzeilen 6, 7, 7b und 8 an die neue Reihenfolge anpassen (Zeile 6 setzt zusätzlich die Statuszeile; Zeile 7 läuft „nach dem Push der Statuszeile“; Zeile 7b ist nur noch Abgleich + letzter Push).
- `scripts/tests/test_main_abgleich_verdrahtung.py`, `scripts/tests/test_ci_warten_verankert.py` (siehe „Pinnende Tests“).
- ADR 0042 und 0063 haben ihren Teil-Vermerk schon (architect). Keine Änderung an `docs/architecture.md`, `docs/setup.md` oder dem Root-`README.md`.

### Neue Reihenfolge in `ship-feature`

**Schritt 6** (Überschrift bleibt):
1. Reste committen (unverändert).
2. `scripts/merge-main-into-branch.sh`, danach `scripts/nummern.py pruefen` und die Nachprüfung (unverändert).
3. `git push -u origin <branch>` (unverändert).
4. `pr-erstellen` mit Titel und `Closes #NNN` (unverändert). Der Satz „Fehlt sie, bricht die Finalisierung in Schritt 8 ab“ verweist künftig auf 6.5.
5. **Neu hier (vorher 8.2):** Verknüpfung prüfen mit `pr-verknuepfung-lesen`, mit beiden Fehlerfällen unverändert. „Nicht verknüpft“ heißt: Body per `pr-body-schreiben` nachziehen und erneut prüfen. „Falscher Basis-Branch“ heißt: anhalten, an Daniel melden, keine Statuszeile. Die bisherige Zeile „Direkt nach dem Eröffnen prüfbar …“ aus 6.4 geht darin auf.
6. **Neu hier (vorher 8.3/8.4):** `**Status:** Implemented ([PR #<MMM>](https://github.com/TheRealKoller/photosort/pull/<MMM>))` setzen, committen mit `chore(specs): Spec NNNN finalisieren (PR #<MMM>)` und mit `git push` pushen. **Zwischen 6.4 und diesem Push gibt es kein Warten, keinen Subagenten und keine Review.** Der Grund gehört als Satz dazu: sonst läuft der Lauf der Eröffnung womöglich durch, bevor er abgebrochen wird.
7. Board-Wert zurücklesen (vorher 6.5; inhaltlich unverändert). Der Satz „Der Spec-Status wird hier nicht gesetzt …“ entfällt ersatzlos.

**Schritt 7:** In 7.1 wird „direkt nach dem Eröffnen des PR in Schritt 6“ zu „direkt nach dem Push der Statuszeile (Schritt 6.6)“. Der Rest bleibt unverändert, auch 7.5 und 7.6.

**Schritt 8** bekommt die neue Überschrift „## Schritt 8: Abgleich mit `main` und letzter Push (vor dem Merge)“:
1. `scripts/merge-main-into-branch.sh` als **erste** Handlung, Auswertung wie bisher.
2. Merge-Commit, einen etwaigen Konflikt-Fix und noch nicht gepushte Fix-Commits in **einem** `git push` hinausschicken. Ist nichts zu pushen, gibt es keinen Push.
3. Freigabe und Merge macht Daniel (unverändert).

Nicht mehr in Schritt 8: das „Wann … nach Copilot … Nie früher“, die Verknüpfungsprüfung, die Statuszeile und der Finalisierungscommit. Der Absatz „Was hier ausdrücklich nicht passiert“ (kein Issue-Schließen, kein `Done`) bleibt, sinngemäß.

**PR ohne Merge geschlossen** (bleibt am Ende von Schritt 8): Board auf `In Progress` wie bisher. **Zusätzlich verbindlich** (statt „falls bereits Implemented … zurücknehmen“): Die Statuszeile auf dem Branch per eigenem Commit auf `**Status:** Accepted` zurücksetzen, Vorschlag `chore(specs): Spec NNNN Status zurücknehmen (PR #<MMM> ohne Merge geschlossen)`. Pushen, solange der Branch auf dem Remote existiert; ist er gelöscht, reicht der lokale Commit. Wird der PR wieder geöffnet, wird die Statuszeile nach 6.6 erneut gesetzt.

**Ausnahmefall:** Statt „ohne Schritt 8 gemergt“ heißt es künftig „gemergt, bevor Schritt 6.6 lief“.

**Schritt 9:** In Zeile 175 wird „nach dem letzten Push (Schritt 8.4)“ zu „nach dem letzten Push des Laufs (Schritt 8.2 oder, wenn Schritt 8 nichts pusht, Schritt 6.6 bzw. 7.5)“.

**Abschlussbericht** (Zeile 202): „Ergebnis der Finalisierung aus Schritt 8“ wird zu „Statuszeile aus Schritt 6.6“.

### Wie AK 4 eingehalten wird

- **Zählweise (ADR 0128 §4):** Ein Durchlauf ist ein Lauf von `ci.yml`, der für einen Stand ein Ergebnis liefert (grün oder rot). Ein durch `cancel-in-progress` abgebrochener Lauf liefert keines und zählt nicht.
- **Bisher:** Lauf bei der Eröffnung plus Lauf beim Push aus Schritt 8. Der Push aus Schritt 8 fand wegen des Finalisierungscommits **immer** statt.
- **Neu:** Der Lauf der Eröffnung wird abgebrochen, es zählt der Lauf der Statuszeile. Dazu kommt ein Lauf aus Schritt 8 **nur dann**, wenn der Abgleich oder Fixes etwas zu pushen haben.
- Pushes dazwischen (7.5 und die Nachbesserung in Schritt 9) sind in beiden Fassungen gleich. Die Zahl sinkt also oder bleibt gleich, steigt aber nie.
- Ein zusätzlicher PR entsteht nicht.
- Restrisiko: Braucht die Zeit von 6.4 bis 6.6 länger als ein CI-Lauf, läuft der Eröffnungslauf durch. Dagegen steht die Regel „kein Warten“ in 6.6.
- Nicht Teil der Zählung ist `pr-titel.yml`: Es läuft ohne Checkout, braucht Sekunden und läuft bei jedem `synchronize`. Durch den Push der Statuszeile kommt ein Titel-Lauf je PR hinzu. Die ADR sagt das offen.

### Wie AK 5 eingehalten wird

- Auf `main` steht die Statuszeile nie vor dem Merge (AK 2): kein Push auf `main`, kein separater PR, kein Board- oder Issue-Zugriff für die Statuszeile.
- Wird der PR ohne Merge geschlossen, nimmt die Sitzung die Zeile auf dem Branch per Commit zurück (siehe oben), und das Board kehrt auf `In Progress` zurück. Danach führt keine Stelle die Spec als umgesetzt.

### Umgang mit den pinnenden Tests (anpassen, nicht neu festnageln)

- `test_main_abgleich_verdrahtung.py`:
  - `test_der_zweite_aufruf_ist_die_erste_handlung_in_schritt_acht` (Z. 844–853): In Schritt 8 fehlen künftig `pr-verknuepfung-lesen` und `**Status:**`, `.index` würde mit `ValueError` scheitern. Der Test sichert künftig zu: Das Skript steht in Schritt 8 genau einmal und **vor** dem `git push` des Abschnitts.
  - Docstring Z. 28–30 und Z. 66–67 sowie die Marken Z. 175–176 entsprechend nachziehen. `MARKE_VERKNUEPFUNG` und `MARKE_STATUSZEILE` wandern in eine Reihenfolge-Zusage für Schritt 6.
  - `test_der_erste_aufruf_steht_nach_dem_commit_und_vor_dem_push` bleibt gültig, weil `index` das erste `committen` bzw. `git push -u origin` findet. Deshalb pusht 6.6 mit schlichtem `git push`, nicht mit `-u origin`.
- `test_ci_warten_verankert.py` Z. 135: Die Marke `ABLAUF_MARKEN[SHIP_FEATURE][0]` bekommt die neue Überschrift von Schritt 8.
- Neue Regressionsfälle (Auswahl und Form beim test-engineer), Vorschlag:
  - In Schritt 6 gilt die Offset-Reihenfolge `pr-erstellen` < `pr-verknuepfung-lesen` < `**Status:**`.
  - Der Offset der Statuszeile liegt vor `copilot-review-anfordern` in Schritt 7 (AK 1).
  - Schritt 8 enthält kein `**Status:**` (AK 7).
  - `ci.yml` führt die `concurrency`-Gruppe mit `github.event.pull_request.number`, dem Rückfall `github.run_id` und `cancel-in-progress: true`. Vorbild ist `test_die_concurrency_gruppe_haengt_an_der_pr_nummer` in `test_pr_titel_pruefung.py`.
  - Gegenproben an mutiertem Text, wie in diesen Dateien üblich.
- Nach der `ci.yml`-Änderung `test_signaturpruefung_je_paketsatz.py` laufen lassen (liest `ci.yml` ohne YAML-Bibliothek nach Jobs).

**Reihenfolge der Umsetzung:**
1. `ci.yml` mit Test.
2. `ship-feature` mit den Reihenfolge-Tests.
3. `developer.md` und `docs/ai-workflow.md`.
4. Den vollen `scripts/`-Testlauf.

## UI/UX

nicht relevant — keine sichtbare Oberfläche; die Änderung betrifft ausschließlich den
Entwicklungsablauf und die CI-Konfiguration.

## Security

**Sicherheitsrelevant, schmal.** Kein Anwendungscode, kein Endpunkt, kein Secret, keine neue Abhängigkeit, keine neue Leseoperation. Geschützt werden zwei Dinge: das Merge-Gate „CI grün vor Merge“ und die Integrität des KI-gesteuerten Ablaufs. Auslöser ist `.github/workflows/ci.yml`. Alles Übrige sind Schreibhandlungen von `ship-feature`, deren Inhalt der Ablauf selbst bildet und die nur an eine andere Stelle rücken.

**1. `concurrency` in `ci.yml`: Das Gate scheitert weiterhin geschlossen.**

- *Schlüssel:* `github.workflow` und `github.event.pull_request.number` legt GitHub fest. Ein PR-Autor kann keinen der beiden Werte frei wählen. Der Ausdruck steht im `concurrency`-Block und nicht in `run:`, deshalb ist keine Script-Injection möglich. Mit `github.head_ref` oder dem Titel wäre das anders: Bei einem Fork-PR ist der Branchname frei wählbar. Zwei Forks mit dem Branch `main` landeten dann in derselben Gruppe, und ein Fork könnte sich den Branchnamen eines PRs von Daniel geben. Die Gruppen `ci-<N>` und `PR-Titel-<N>` kollidieren nicht. Pushes auf `main` fallen auf `github.run_id` zurück und brechen nie einen anderen Lauf ab.
- *Ein abgebrochener Lauf gilt nie als bestanden.* Er gehört zum überholten Commit. Die geforderten Checks werden am Head-Commit gemessen, und dort verlangt die Branch Protection (`strict`, `enforce_admins`) ein erfolgreiches Ergebnis. `pr-pruefstand-abwarten` wertet `bucket == cancel` als `unbestimmt`, der Ablauf hält dann an und meldet. Jeder Abbruch, der den Head-Commit selbst trifft, blockiert den Merge und gibt ihn nicht frei. Das gilt für einen Re-run eines alten Stands, für Schließen und Wiederöffnen am selben Commit und für eine fremde Gruppenkollision.
- *Neu ist: Der Lauf eines offenen PRs lässt sich von außen abbrechen.* Das betrifft die Verfügbarkeit, nicht die Integrität. Ein `pull_request`-Lauf eines Fork-PRs nimmt `ci.yml` aus dem Stand des Forks, und Concurrency-Gruppen gelten repositoryweit (laut GitHub-Doku, nicht gemessen). Ein Fork-PR, dessen Workflow laufen darf, kann deshalb `group: ci-<N>` setzen und den Lauf von PR `<N>` abbrechen. Ein falsches Grün entsteht dabei nicht, weil seine Checks am Commit des Forks hängen. Die Folge ist ein Halt in Schritt 9 und ein erneuter Lauf. Das ist dieselbe Klasse wie bei der bestehenden Gruppe `PR-Titel-<N>` (Sicherheitskonzept, „PR-Titel-Prüfung“, Punkt 7). Eine zusätzliche Gegenmaßnahme ist nicht vorgesehen.
- *Ein Abbruch hinterlässt nichts.* Die Runner werden von GitHub gehostet und sind flüchtig. `ci.yml` verwendet kein `secrets.*`, und `permissions: contents: read` bleibt unverändert.

**2. Statuszeile vor dem Copilot-Review: kein neuer Lesekanal, Copilot-Text steuert nichts.**

- Der Statuscommit wird vollständig vom Ablauf selbst gebildet. Er enthält die Spec-Nummer und die PR-Nummer aus `pr-erstellen` dieses Laufs, geprüft gegen `^[0-9]+$`. Die URL wird aus dieser Nummer gebildet, Owner und Repo stehen als Literal darin (Härtungsregel 4.2). Kein Wert stammt aus PR-Body, Check-Namen oder Reviewtext.
- Die Verknüpfungsprüfung (6.5) bleibt vorgeschaltet. Ist der Basis-Branch falsch, entsteht weder ein Commit noch ein Push.
- Zwischen 6.4 und 6.6 prüft niemand. Für Schritt 8 galt das bisher genauso, neu ist nur der Zeitpunkt. Der Branch ist öffentlich, deshalb ist der Commit pfadgenau, damit nichts unbeabsichtigt mitgeht (S3).
- Copilot liest danach einen Diff mit einer zusätzlichen Zeile. `pr-reviewkommentare-lesen` bleibt die einzige Stelle, an der Fremdtext gelesen wird. Diese Ausnahme gibt es schon, sie bleibt unverändert. Nach 6.6 ändert sich die Zeile nur noch über die Rücknahme, und auch dafür ist ein Copilot-Kommentar nie der Auslöser (Härtungsregel 4.3).
- Wirksam wird die Zeile erst mit dem Merge, und den gibt allein Daniel frei. Das frühere Setzen schwächt also kein Gate.

**3. Rücknahme, wenn der PR ohne Merge geschlossen wird**

- Ein Push auf den Branch eines geschlossenen PRs löst keinen CI-Lauf aus. `pull_request` feuert für geschlossene PRs nicht, und `push` gilt nur für `main`.
- *Risiko:* Ein schlichtes `git push` legt einen auf dem Remote gelöschten Branch wieder an. Hat Daniel den Branch bewusst gelöscht, etwa weil er etwas nicht Öffentliches enthielt, würde die Rücknahme ihn erneut veröffentlichen. Dagegen steht S5.
- Auslöser ist der festgestellte Zustand des PRs mit dieser Nummer oder Daniels Meldung, nie ein Kommentar- oder Reviewtext.

**Sicherheitskonzept: Vermerk im Umsetzungs-PR.** Er kommt als neuer Punkt unter „GitHub-Repository-Zugriff“, direkt nach „Workflow-Berechtigungen“. Die Kopfzeile „Letzte Aktualisierung“ wird nachgezogen.

> - **Abbruch überholter PR-Läufe in `ci.yml`** (ADR [`0128`](../decisions/0128-die-spec-statuszeile-steht-vor-dem-copilot-review-im-pull-request.md), Spec 0414): `concurrency` auf oberster Ebene, Gruppe `${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}`, `cancel-in-progress: true`. Der Schlüssel besteht nur aus Werten, die GitHub vergibt, nie aus Branchname oder Titel, denn `head_ref` ist bei Fork-PRs frei wählbar. Ein abgebrochener Lauf gilt nie als bestanden: Die Branch Protection verlangt am Head-Commit Erfolg, und `pr-pruefstand-abwarten` wertet `bucket == cancel` als `unbestimmt`. Restrisiko für die Verfügbarkeit: Ein Fork-PR, dessen Workflow laufen darf, kann in seiner eigenen `ci.yml` denselben Gruppennamen setzen und den Lauf eines offenen PRs abbrechen. Das Gate scheitert dann geschlossen, ein erneuter Lauf behebt es. Es ist dieselbe Klasse wie bei `pr-titel.yml`, Punkt 7.

**Muss-Kriterien:**

- **S1:** Der Block steht wörtlich wie in ADR 0128 §3 auf oberster Ebene. Der Schlüssel besteht nur aus `github.workflow`, `github.event.pull_request.number` und `github.run_id`. Kein `head_ref`, kein `ref`, kein Titel, kein Ausdruck in `run:`. Die Auslöser (`push: main`, `pull_request` ohne `types`) und `permissions: contents: read` bleiben unverändert. Kein `pull_request_target`.
- **S2:** Dass ein abgebrochener Lauf nicht als grün gilt, bleibt an beiden Stellen unverändert. Die Branch Protection wird nicht angefasst. `pr-pruefstand-abwarten` wertet `bucket == cancel` weiterhin als `unbestimmt`, und `--required` kommt nicht hinzu.
- **S3:** Der Statuscommit ist pfadgenau: `git add <Spec-Pfad>`, nie `-A` und nie `-a`. Er ändert genau eine Zeile, die `**Status:**`-Zeile der Spec, also `git diff --cached --numstat` = `1	1	<Spec-Pfad>`. Die Nachricht bildet der Ablauf selbst, sie enthält kein Closing-Keyword.
- **S4:** Die Statuszeile entsteht erst, nachdem 6.5 bestanden ist. Die PR-Nummer stammt nur aus `pr-erstellen` dieses Laufs, wird gegen `^[0-9]+$` geprüft, und die URL wird daraus gebildet (Härtungsregel 4.2). Kein Fremdtext aus Review, Check-Namen oder PR-Body gelangt in die Spec oder den Commit (Härtungsregel 4.3).
- **S5:** Die Rücknahme pusht nur, wenn der Branch auf dem Remote noch existiert. Geprüft wird über den Exit-Code von `git ls-remote --exit-code --heads origin <branch>`, die Ausgabe wird verworfen. Der Branch wird nie neu angelegt, es gibt kein `--force` und keinen Push auf `main`. Der Commit ist pfadgenau wie in S3.
- **S6:** Der Umsetzungs-PR wird sicherheitlich reviewt, denn sein Diff enthält `.github/workflows/ci.yml`.

## Teststrategie

Kein Anwendungscode. Ein neuer Wächter kommt unter `scripts/tests/` hinzu (Job `demo-scripts`, kein
Coverage-Gate). Zwei bestehende Wächter werden angepasst, nicht neu festgenagelt. Danach läuft die volle
`scripts/`-Suite einmal, u. a. `test_signaturpruefung_je_paketsatz.py` (liest `ci.yml` nach Jobs),
`test_verweisnummern_in_markdown.py` und `test_dokumentnummern_eindeutig.py`.

| AK | Prüfform |
|---|---|
| 1 | statisch: Reihenfolge in `ship-feature`; Beobachtung am Umsetzungs-PR |
| 2 | Dokumentdurchsicht: kein Schreiben auf `main`, kein zweiter PR, kein Board-/Issue-Zugriff für die Zeile |
| 3 | statisch: Zeile in Schritt 6 nach `pr-erstellen` und `pr-verknuepfung-lesen`; Review der Fehlerpfade |
| 4 | statisch: `concurrency`-Block in `ci.yml`; Beobachtung am Umsetzungs-PR |
| 5 | Dokumentdurchsicht der Rücknahme am Ende von Schritt 8 |
| 6 | Dokumentdurchsicht (ADR 0128, Teil-Vermerke 0042/0063); Verweisnummern über die bestehende Suite |
| 7 | statisch: Einmaligkeit und Ort der Statuszeile, Überschrift Schritt 8; Dokumentdurchsicht der Fundstellen |

**Neu: `scripts/tests/test_statuszeile_vor_copilot_review.py`.** Das Modul hat eigene dünne Leser und
importiert nichts aus Nachbarmodulen. Reihenfolgen werden über Zeichenoffsets geprüft:
- `**Status:** Implemented` steht in `ship-feature` genau einmal, und zwar in `## Schritt 6`.
- In Schritt 6 gilt: `` `pr-erstellen` `` < `` `pr-verknuepfung-lesen` `` < Statuszeile < ein folgendes `git push`.
- Das erste `` `copilot-review-anfordern` `` der Datei liegt hinter der Statuszeile.
- In `ci.yml` steht genau ein `concurrency:`, auf oberster Ebene. Sein `group:` lautet wortgleich
  `${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}`, und im selben
  Block steht `cancel-in-progress: true`.
- Gegenproben:
  - Offsetvergleich an synthetischem Text in beide Richtungen.
  - `**Status:** Accepted` (die Rücknahme) zählt nicht; eine zweite `Implemented`-Zeile wird gemeldet.
  - Am zur Laufzeit mutierten echten `ci.yml` wird jede dieser Mutationen rot: Rückfall entfernt,
    Block unter einen Job eingerückt, `false`.
  - Eine Kommentarzeile, die `concurrency:` nennt, bleibt grün.
  - Eine leere oder fehlende Datei scheitert laut.

**Angepasst:**
- `test_main_abgleich_verdrahtung.py`: Der Schritt-8-Test sichert künftig zu, dass das Skript dort genau
  einmal steht und vor dem ersten `git push` des Abschnitts. `MARKE_VERKNUEPFUNG` und `MARKE_STATUSZEILE`
  entfallen, Docstring-Punkt 5 wird nachgezogen. Der datierte Mutationsnachweis vom 2026-09-08 bleibt stehen.
- `test_ci_warten_verankert.py`: `ABLAUF_MARKEN[SHIP_FEATURE][0]` bekommt die neue Überschrift von Schritt 8.

**Beobachtung am Umsetzungs-PR (gehört in den PR-Body):**
- `gh run list --workflow ci.yml --branch <branch>` zeigt: Der Lauf der Eröffnung endet `cancelled`,
  der Lauf des Statuscommits liefert ein Ergebnis.
- In der Timeline liegt der Statuscommit vor der Copilot-Anforderung, und Copilot meldet keine Spec ohne
  Umsetzung.
- Bis das im PR-Body steht, bleiben AK 4 und der Beobachtungsteil von AK 1 offen.

**Edge Cases:**
- Reiner Doku-PR ohne Copilot: Die Zeile steht trotzdem in 6.6.
- „Nicht verknüpft“: erst den Body nachziehen und erneut prüfen, dann die Zeile setzen.
- „Falscher Basis-Branch“: keine Zeile, also nichts zurückzunehmen.
- Schritt 8 hat nichts zu pushen: kein Push; der Wartepunkt-Offset bleibt gültig.
- Copilot-Fixes (7.5) brechen einen noch laufenden Statuslauf ab. Das ist gewollt.
- Zwei Merges kurz nacheinander auf `main`: Die Gruppe fällt auf `run_id` zurück, kein Abbruch.
- Die Zeit zwischen 6.4 und 6.6 ist länger als ein CI-Lauf: Dann zählt der Eröffnungslauf
  (Restrisiko nach ADR 0128 §1). Dagegen steht nur die Regel „kein Warten“.
- PR ohne Merge geschlossen und Remote-Branch gelöscht: Der lokale Rücknahmecommit genügt.
  Wird der PR wieder geöffnet, wird die Zeile nach 6.6 neu gesetzt.
- release-please-PR ohne Folgepush: Der Eröffnungslauf läuft voll durch. Deshalb bleibt `opened` Auslöser.

**Mutationsnachweis nach Grün** (steht im Docstring des neuen Moduls). Jede Mutation muss rot werden:
Statuszeile zurück in Schritt 8, zweite Setz-Anweisung in Schritt 8, `copilot-review-anfordern` vor die
Zeile gezogen, `git push` hinter der Zeile entfernt, dazu die drei `ci.yml`-Mutationen.
Nicht-Reaktion: Die Rücknahme mit `**Status:** Accepted` in Schritt 8 bleibt grün.

## Entscheidungen

- `architect`, `test-engineer` und `security-engineer` konsultiert.
- `ux-ui-designer` nicht konsultiert (Schritt 2): keine sichtbare Oberfläche; der Diff betrifft
  ausschließlich Skill-, Agenten-, ADR-, Doku-, Test- und Workflow-Dateien.
- Zählweise für AK 4, von Daniel entschieden (2026-10-01): Gemessen werden abgeschlossene Läufe von
  `ci.yml`; ein durch `cancel-in-progress` abgebrochener Lauf zählt nicht, ein zusätzlicher
  `pr-titel`-Lauf ist hinnehmbar.
- `concurrency` in `ci.yml` statt Draft-Eröffnung oder Vorhersage der PR-Nummer (ADR 0128,
  verworfene Alternativen).
- `**Status:** Implemented` steht in `ship-feature` genau einmal, in Schritt 6; die Rücknahme in
  Schritt 8 führt `**Status:** Accepted`. Daraus folgt der Test „Einmaligkeit plus Ort" statt
  „Schritt 8 ohne `**Status:**`".
- Ein eigenes Testmodul je ADR (`test_statuszeile_vor_copilot_review.py`), statt die Marken in
  `test_main_abgleich_verdrahtung.py` zu verschieben.
- Die Rücknahme (AK 5) bekommt keinen dauerhaften Test, nur Dokumentdurchsicht.
- Dieser Umsetzungs-PR läuft bereits nach der neuen Reihenfolge; die Beobachtung zu AK 1 und AK 4
  steht im PR-Body.

## Offene Fragen

- keine

## Out of Scope

- Andere Befunde, die aus dem Ablauf selbst stammen könnten.
- Der Widerspruch zwischen `ship-feature` 7.5 („Nach Fixes: erneuter Push") und der Bündelung in
  Schritt 8; die Zählung aus ADR 0128 §4 gilt unter beiden Lesarten.
