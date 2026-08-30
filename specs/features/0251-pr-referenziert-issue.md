# 0251 - Pull Request referenziert sein Issue

**Status:** Accepted
**Erstellt:** 2026-08-30
**Bezug:** GitHub-Issue [`#251`](https://github.com/TheRealKoller/photosort/issues/251) ("pr sollte issue referenzieren"), ADR [`0046`](../decisions/0046-pr-issue-verknuepfung-closing-keyword.md)

## Ziel

Wenn ein GitHub-Issue durch einen Pull Request umgesetzt wird, soll der Zusammenhang zwischen beiden für Daniel jederzeit nachvollziehbar sein, ohne dass er nach dem Merge manuell nacharbeiten muss. Aktuell ist im PR bzw. im Board nicht auf einen Blick erkennbar, welches Issue ein bestimmter PR umsetzt, und das zugehörige Issue bleibt nach dem Merge offen, bis es von Hand geschlossen wird.

Ein Feature-PR nennt sein Issue heute nur als Fließtext (`- Issue: #209` aus `.github/pull_request_template.md`). Das erzeugt in GitHub lediglich einen Cross-Reference-Eintrag in der Issue-Timeline, **keine** strukturierte Verknüpfung. Als Nebenwirkung ist der bereits gebaute Ausnahmepfad von `gh-board.py finalize` (Nachzug nach einem Merge außerhalb des üblichen Ablaufs, ADR [`0042`](../decisions/0042-pre-merge-finalisierung-statt-nachzieh-pr.md)) seit seiner Einführung funktionsunfähig: Er löst den PR über `closedByPullRequestsReferences` auf, ein Feld, das ausschließlich durch Closing-Keywords befüllt wird und für das zuletzt gemergte Issue #209 `[]` liefert. Die Verknüpfung ist damit keine reine Bequemlichkeit, sondern die fehlende Voraussetzung eines schon getroffenen Entwurfs.

## User Story

Als Daniel möchte ich, dass ein Pull Request erkennbar mit dem Issue verknüpft ist, das er umsetzt, und dass dieses Issue nach dem Merge automatisch als erledigt markiert wird, damit ich den Bezug zwischen geleisteter Arbeit und ursprünglicher Anforderung jederzeit nachvollziehen kann, ohne das manuell nachpflegen zu müssen.

## Akzeptanzkriterien

- [ ] **Verknüpfung sichtbar:** Ein PR, der ein Issue umsetzt, ist über GitHubs eigene Verknüpfung mit ihm verbunden — der PR führt das Issue unter "Linked issues", das Issue den PR unter "Linked pull requests". Maschinell prüfbar am offenen PR: `gh pr view <PR> --json closingIssuesReferences` enthält einen Eintrag mit der Issue-Nummer und passendem Repository (`TheRealKoller`/`photosort`). Hergestellt wird die Verknüpfung über die Zeile `Closes #NNN` im PR-**Body**, ausgefüllt bei der PR-Eröffnung.
- [ ] **Kein manueller Nachlauf:** Wird ein solcher PR nach `main` gemergt, ohne dass das Issue vorher geschlossen wurde, schließt GitHub es beim Merge selbst. Im Regelweg (Pre-Merge-Finalisierung) ist es bereits geschlossen, und der Merge ändert daran nichts. In beiden Fällen ist nach dem Merge kein Handgriff am Issue nötig.
- [ ] **Durchgesetzt statt erbeten, und ohne Kollision mit ADR 0037:** `gh-board.py finalize --pr-number` bricht mit `{"error": ...}` und Exit-Code 1 ab, wenn `closingIssuesReferences` keinen repo-qualifiziert passenden Eintrag zur Issue-Nummer enthält oder der PR nicht auf den Default-Branch zielt — und zwar bevor die Spec-Datei geschrieben und bevor der erste Board-Zugriff erfolgt ist, auch der lesende. Nach dem Nachtragen der Verknüpfung ist derselbe Aufruf erfolgreich wiederholbar.
- [ ] **Board-Status bleibt einschreibig:** Das Board-Status-Feld schreibt weiterhin ausschließlich `gh-board.py` — die nativen Workflows `Item closed`, `Pull request merged` und `Pull request linked to issue` des Projekts "PhotoSort Roadmap" sind zum Zeitpunkt des ersten gemergten PRs mit Closing-Keyword nachweislich deaktiviert. (Manueller Rollout-Schritt durch Daniel, siehe "Rollout".)
- [ ] **Ausgenommen bleibt ausgenommen:** PRs ohne Issue-Bezug (Doku-/Chore-PRs, release-please, Dependabot) lassen die Zeile weg und werden von keinem Mechanismus blockiert — `finalize` läuft für sie gar nicht, und es gibt bewusst keine repo-weite CI-Prüfung. Umgekehrt gilt: Weder eine Commit-Nachricht des Feature-Branches noch der PR-Titel enthält ein Closing-Keyword (das Repo squasht mit `COMMIT_MESSAGES` **und** `COMMIT_OR_PR_TITLE`, beides landet im Changelog und im release-please-PR).

## Datenmodell-Bezug

Keine Änderung am Anwendungs-Datenmodell. Berührt werden ausschließlich GitHub-Metadaten (PR-Body, Issue-Zustand, Board-Status-Feld) und die Spec-Datei im Repository. Kein Effekt auf [`docs/architecture.md`](../../docs/architecture.md) oder [`docs/setup.md`](../../docs/setup.md) — reines Prozess-Tooling.

## Architektur / Umsetzung

Vollständig festgelegt in ADR [`0046`](../decisions/0046-pr-issue-verknuepfung-closing-keyword.md). Kurzfassung:

Die Verknüpfung entsteht über **genau einen** Mechanismus: die Zeile `Closes #NNN` im **Body** des Pull Requests, ausgefüllt bei der PR-Eröffnung (`ship-feature`, Schritt 6.3). GitHub zeigt daraufhin beidseitig eine strukturierte Verknüpfung ("Linked issues" am PR, "Linked pull requests" am Issue) und schließt das Issue beim Merge nach `main` automatisch — ein Mechanismus für beide Anforderungen. Eine zusätzliche Development-Verknüpfung wird nicht eingeführt; sie entsteht bereits aus dem Keyword, und separat herstellbar wäre sie ohnehin nicht (GraphQL kennt nur `createLinkedBranch` für Branches, keine PR↔Issue-Mutation). Der Weg über `gh issue develop` wurde verworfen, weil er einen Branch auf dem Remote verlangt und damit ADR [`0045`](../decisions/0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md) (Feature-Branch bleibt bis `ship-feature` rein lokal) ohne Gegenwert umkehren würde.

Das Keyword gehört **nicht** in Commit-Nachrichten: Das Repository squasht mit `squash_merge_commit_message = COMMIT_MESSAGES`, das Keyword landete sonst im Merge-Commit, im Changelog und im Body des release-please-Release-PRs.

Damit die Regel nicht nur eine Bitte in einer Vorlage bleibt, verifiziert `gh-board.py finalize --pr-number` die Verknüpfung an der einzigen Stelle, die ohnehin mit dem offenen PR spricht — und fragt dafür **GitHub**, statt den PR-Body selbst zu parsen. Maßgeblich ist `closingIssuesReferences` aus dem bereits abgesetzten `gh pr view` (Abfrage wird von `state,url` auf `state,url,baseRefName,closingIssuesReferences` erweitert, kein zusätzlicher API-Aufruf): GitHubs eigenes Parse-Ergebnis. Akzeptiert wird der PR, wenn die Liste einen repo-qualifiziert passenden Eintrag zur Issue-Nummer enthält und `baseRefName` der Default-Branch ist; sonst bricht `finalize` mit `{"error": ...}` ab — vor dem Umschreiben der Spec-Datei und vor jedem Board-Zugriff, also wiederholbar nach einem `gh pr edit --body-file`.

Der Grund für diese Quelle ist die Fehlerrichtung: Gefährlich ist der falsch-positive Fall (wir akzeptieren, GitHub verknüpft nicht) — nach dem Merge ist er nicht mehr reparabel. Ein eigener Regex kann ihn prinzipiell nicht ausschließen, weil er GitHubs Parser nur nachbilden könnte (Keyword in HTML-Kommentar/Code-Fence/Blockquote/PR-Titel, Schreibweisen- und Referenzformvarianten wie `#123`, `owner/repo#123`, volle URL — teils undokumentiert und einseitig änderbar). Dass diese Divergenz nicht theoretisch ist, zeigt ein Gegenbeispiel aus der Praxis: `microsoft/vscode` PR #332863 nennt seine Issues ausschließlich als volle URLs und liefert trotzdem korrekt fünf Einträge in `closingIssuesReferences` — ein `#NNN`-Regex hätte dort falsch-negativ geurteilt. `closingIssuesReferences` schließt die falsch-positive Richtung per Konstruktion aus. Nebeneffekt: Der von außen befüllbare PR-Body wird gar nicht mehr eingelesen.

Akzeptiert werden dabei auch Issues, die ohne Keyword manuell über die Development-Seitenleiste verknüpft wurden (`gh pr view --json` kann `excludeUserLinked` nicht übergeben): Geprüft wird die Zusicherung "GitHub schließt dieses Issue beim Merge", nicht die Form ihrer Herstellung — eine Verengung würde einen funktional korrekten Zustand ablehnen und wieder einen eigenen Begriff von Verknüpfung einführen. Der verbindliche Herstellungsweg bleibt die Textzeile im PR-Body.

Der Pfad **ohne** `--pr-number` braucht keine eigene Prüfung — er findet den PR über `closedByPullRequestsReferences` am Issue, also über dieselbe von GitHub gepflegte Verknüpfung aus der Gegenrichtung. Das Werkzeug hat danach an keiner Stelle mehr einen eigenen Begriff davon, was als Verknüpfung zählt. Eine repo-weite CI-Prüfung wird bewusst nicht gebaut: Sie müsste die Ausnahme für PRs ohne Issue-Bezug heuristisch erraten und würde fremde PRs (release-please, Dependabot) blockieren, für die die Regel nie gedacht war.

Das Board-Status-Feld bleibt alleinige Domäne von `scripts/gh-board.py` (ADR [`0037`](../decisions/0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md), Abschnitt 5). Weil das Keyword GitHub erstmals in die Lage versetzt, ein Issue selbstständig zu schließen, wird der aktuell aktive native Workflow `Item closed` einmalig abgeschaltet. Der Regelweg bleibt dadurch unverändert ohne GitHub-Automatik: `finalize` setzt vor dem Merge `Done` und schließt das Issue, das Keyword ist beim Merge ein No-op. Erst im Ausnahmefall (Merge ohne vorherige Finalisierung) schließt GitHub das Issue selbst — und der nachgezogene `finalize`-Aufruf findet den PR dann über eben diese Verknüpfung.

### Betroffene/neue Dateien

- `.github/pull_request_template.md`: `- Issue: #` wird durch die Closing-Zeile ersetzt, dazu ein HTML-Kommentar mit Zweck und Ausnahmefall ("PR ohne Issue-Bezug — Zeile löschen"). Der Kommentar enthält hinter einem `#` keine Ziffernfolge; die Vorlage stützt sich nicht auf die undokumentierte Annahme, GitHub werte Keywords in HTML-Kommentaren nicht aus.
- `.claude/skills/ship-feature/SKILL.md`: Schritt 6.3 verlangt das ausgefüllte Keyword (Issue-Nummer = Spec-Nummer bei neuen Specs, bei Altspecs `0001`–`0065` aus der `**Bezug:**`-Zeile); Schritt 8 bekommt den neuen Fehlerfall (fehlende Verknüpfung → `gh pr edit --body-file` nachziehen, `finalize` wiederholen) in die dort schon beschriebene `{"error": ...}`-Behandlung.
- `.claude/skills/github-board/SKILL.md`: `finalize`-Beschreibung um die neue Vorbedingung ergänzt, inkl. Begründung, warum der Pfad ohne `--pr-number` sie nicht separat prüft (gleiche Datenquelle, Gegenrichtung).
- `scripts/gh-board.py`: `get_pull_request()` holt `state,url,baseRefName,closingIssuesReferences` statt `state,url` (Rückgabetyp weitet sich von `dict[str, str]` auf `dict[str, Any]` — relevant für `mypy --strict`); `_resolve_pull_request()` prüft im `--pr-number`-Zweig repo-qualifiziert gegen die Issue-Nummer plus Default-Branch, vor jedem Schreibzugriff; neue Modul-Konstanten neben `DEFAULT_OWNER` für Repository-Name und Default-Branch. Der PR-Body wird **nicht** abgefragt.
- `scripts/tests/test_gh_board.py`: siehe Teststrategie.
- `docs/ai-workflow.md`: Schritt 6 der Ablauftabelle hält die Closing-Keyword-Verknüpfung fest.

### Reihenfolge

1. `scripts/gh-board.py` + Tests: zuerst `get_pull_request()` auf die erweiterte Feldliste umstellen (betrifft beide bestehenden Aufrufer und deren Fakes — diese Umstellung isoliert grün bekommen), danach die Verknüpfungsprüfung in `_resolve_pull_request()`. Der einzige testbare Anteil, ohne Abhängigkeit zu den Prozessdateien.
2. `.github/pull_request_template.md` — die Quelle, aus der das Keyword faktisch entsteht.
3. Prozessdateien: `ship-feature` (Schritt 6.3 und 8), `github-board` (Vorbedingung), `docs/ai-workflow.md`.

### Rollout (manuell durch Daniel, kein Code, kein Test)

Projekt-UI → Workflows → `Item closed` deaktivieren; `Pull request merged` und `Pull request linked to issue` deaktiviert lassen. **Ohne diesen Schritt entsteht mit dem ersten Keyword ein zweiter Schreiber auf das Status-Feld** — deshalb steht er als Akzeptanzkriterium und nicht als Fußnote. GraphQL bietet für native Workflows keine Deaktivierung (nur `deleteProjectV2Workflow`), der Schritt ist daher nicht automatisierbar.

## UI/UX

Nicht relevant — reine Prozess-/Tooling-Änderung an GitHub-Metadaten, Skill- und Doku-Dateien. Keine Berührung von `frontend/`, keine sichtbare Oberfläche der Anwendung.

## Teststrategie

Alle Tests laufen gegen den `FakeGh` in `scripts/tests/test_gh_board.py` (kein echtes `gh`, kein Netzwerk, injiziertes `run`-Callable) im bestehenden `demo-scripts`-CI-Job. Kein Coverage-Bezug (`scripts/` liegt außerhalb von `--cov-fail-under=80`), kein neues CI-Gate, kein Integrationstest-Pendant.

Geprüft wird GitHubs eigenes Parse-Ergebnis (`closingIssuesReferences`), nicht der PR-Body. **Sechs Testfälle:** Referenz vorhanden → Durchlauf; manuell verknüpftes Issue ohne Keyword → Durchlauf; leere Liste → `BoardError`; nur ein fremdes Issue referenziert → `BoardError`; gleiche Nummer in einem fremden Repository → `BoardError`; `baseRefName` ≠ Default-Branch → `BoardError`. Dazu die Argumentlisten-Prüfung (`--json state,url,baseRefName,closingIssuesReferences`, inklusive der Zusicherung, dass kein `body` mehr angefragt wird), der CLI-Fehlerfall als `{"error": ...}` mit Exit-Code 1, die Wiederholbarkeit nach dem Nachtragen der Verknüpfung und ein Charakterisierungstest für den Pfad ohne `--pr-number` (bleibt ungeprüft, damit niemand die Prüfung "sauberkeitshalber" in `get_pull_request()` verschiebt und den Ausnahmepfad bricht).

Der Fall "manuell verknüpft ohne Keyword" ist **Regressionsschutz für eine bewusste Entscheidung**, kein zweiter Positivfall: Vorgeschrieben ist die Zeile im Body, geprüft wird nur ihre Wirkung. Er hält fest, dass eine spätere Verengung (`gh api graphql` mit `excludeUserLinked: true`, Zusatzprüfung auf den Text) auffallen soll statt stillschweigend durchzugehen. Aus Sicht des Test-Doubles ist er von einem Keyword-Fall nicht unterscheidbar, weil die Herkunft der Referenz im Feld nicht auftaucht — das gehört als Begründung in den Docstring, sonst wirkt der Test wie ein Duplikat.

**In jedem Ablehnungsfall wird nicht nur die Spec-Datei gegengelesen (`**Status:** Accepted`), sondern zusätzlich das vollständige Aufruflog:** `{tuple(c[:3]) for c in fake.calls} == {("gh", "pr", "view")}`. Das beweist "vor **jedem** Board-Zugriff" statt nur "kein Schreibzugriff" und altert nicht mit neuen Schreibbefehlen.

**Bewusst nicht getestet:** Keyword-Schreibweisen, Doppelpunkt-Varianten, Referenzformen (`#NNN`, `owner/repo#NNN`, URL), Keyword in HTML-Kommentar/Code-Fence/Blockquote/PR-Titel, Präfix-Verwechslungen wie `#2620` vs. `#262`, mehrere Referenzen hinter einem Keyword, leerer Body. Das ist nach ADR 0046 kein eigener Code mehr, sondern Verhalten von GitHub — es nachzustellen hieße, ein Test-Double gegen fremdes Verhalten zu prüfen.

**Test-Double-Treue ist tragend:** Der `FakeGh` muss die reale Feldform spiegeln (`closingIssuesReferences` als Liste von `{number, url, repository: {name, owner: {login}}}` plus `baseRefName`), sonst ließe sich der repo-qualifizierte Vergleich gar nicht sinnvoll prüfen. Beide Aufrufer von `get_pull_request()` und die zwölf bestehenden `pull_requests={...}`-Literale sind betroffen — letztere über eine Hilfsfunktion mit erfülltem Default, nicht einzeln.

**Umgebungsvoraussetzung:** `closingIssuesReferences` ist über `gh pr view --json` erst ab `gh` 2.72.0 verfügbar; die Fehlermeldung bei unbekanntem JSON-Feld muss die Mindestversion nennen, damit sie nicht als "Verknüpfung fehlt" fehlgedeutet wird.

**Prozess-/Doku-Dateien** (`pull_request_template.md`, `ship-feature`/`github-board`-Skills, `docs/ai-workflow.md`) sind kein `pytest`-Gegenstand: `ship-feature` Schritt 6.3 ist die deterministische Erweiterung eines bestehenden, unbedingten Ablaufschritts — statischer Konsistenz-Check im `review-tests`-Durchlauf.

**Nicht automatisierbar** (Beobachtungspunkte): die UI-Anzeige beider Seiten, das tatsächliche Auto-Close beim Merge, der Zustand der drei nativen Board-Workflows und der Repo-Schalter "Auto-close issues with merged linked pull requests". Nachweis am realen Umsetzungs-PR selbst — er trägt die Zeile ohnehin und ist damit seine eigene Positiv-Probe.

Ergänzungen im Testkonzept ([`specs/architecture/0002-testkonzept.md`](../architecture/0002-testkonzept.md)) sind Teil dieser Spec.

## Security

**Sicherheitsrelevant, kein Blocker — im Ergebnis eine Verkleinerung der Angriffsfläche.** Reine Prozess-/Tooling-Änderung ohne Anwendungscode. Herleitung im Sicherheitskonzept ([`specs/architecture/0003-securitykonzept.md`](../architecture/0003-securitykonzept.md), Abschnitt "PR↔Issue-Verknüpfung über ein Closing-Keyword im PR-Body").

- **Keine neue Eingabe von außen.** Ein erster Entwurf hätte den PR-**Body** eingelesen und selbst nach einem Keyword durchsucht — das wäre die erste GitHub-Textquelle im Werkzeug gewesen, die ein Dritter ohne Repo-Schreibzugriff füllen kann (das Repo ist public, jeder kann forken und einen PR mit beliebigem Body eröffnen). Der finale Ansatz fragt stattdessen GitHubs eigenes Parse-Ergebnis ab; der Body wird gar nicht mehr abgefragt. Damit entfallen ersatzlos: die falsch-positive Parser-Divergenz, ein ReDoS-Angriffspunkt auf unbegrenztem Freitext, jede Abhängigkeit von undokumentiertem GitHub-Verhalten und die Notwendigkeit, Fremdtext aus den Fehlermeldungen herauszuhalten (der `github-board`-Skill spiegelt jede Fehlermeldung wörtlich in den Hauptsession-Kontext, der GitHub-Schreibzugriff hat).
- **Verwechslungsschutz ist Teil der Prüfung:** Akzeptiert wird nur ein repo-qualifiziert passender Eintrag (Owner/Repo/Nummer, kein reiner Zahlenvergleich) mit `baseRefName` = Default-Branch. Das schließt Cross-Repo-Verwechslung und einen gegen einen Nebenbranch gerichteten PR aus.
- **Fail-closed:** Kennt das lokale `gh` das Feld nicht (< 2.72.0), scheitert der Aufruf und `finalize` bricht ab, bevor Spec-Datei oder Board angefasst werden.
- **Manuell verknüpfte Issues werden mit akzeptiert** (`excludeUserLinked` bleibt Default) — sicherheitsseitig unkritisch: Diese Verknüpfung kann nur setzen, wer ohnehin Schreibzugriff hat; es entsteht kein Weg, auf dem ein Dritter die Prüfung beeinflussen könnte.
- **Command-Injection unverändert ausgeschlossen:** `gh`-Aufrufe in Listenform ohne `shell=True`, keine Interpolation gelesener Werte in Argumente, `--body-file`-Regel unberührt.
- **Neuer Seiteneffekt beim Merge fremder PRs (verbleibendes Restrisiko):** Das Mergen eines PRs wirkt erstmals auf den Zustand eines Issues. Für keyword-basiertes Schließen im selben Repo dokumentiert GitHub keine Berechtigungsprüfung des PR-Autors; das einzige Gate ist der Merge. Ein Fork-PR kann `Closes #<beliebiges Issue>` tragen; maßgeblich ist der Body **zum Merge-Zeitpunkt**, nicht der beim Review gelesene. Die `finalize`-Prüfung ist ein Vergessens-Schutz für den eigenen Ablauf, keine Kontrolle gegen einen absichtlich handelnden Dritten — sie läuft spec-gebunden nur für unsere eigenen Feature-PRs. Die `approved-for-agent`-Policy deckt Issues von Fremd-Accounts ab, nicht fremde PR-Bodies; beim Merge eines Fremd-PRs gehört die `Closes`-Zeile ausdrücklich zum Review-Blick.
- **Keyword nie in einer Commit-Nachricht:** GitHub wertet Closing-Keywords dokumentiert auch in Commit-Messages aus; bei `squash_merge_commit_message = COMMIT_MESSAGES` wandert es sonst in Merge-Commit, Changelog und den Body des release-please-PRs und wird beim nächsten Release-Merge erneut ausgeführt — die einzige Stelle, an der ein zweiter, unbeabsichtigter Schließpfad real entstehen kann.
- **Board-Integrität:** Der einmalige Rollout-Schritt (`Item closed` deaktivieren) verhindert einen zweiten, unkontrollierten Schreiber auf das Status-Feld. Bleibt er aus, ist die Folge ein nicht mehr durch eine lokale Quelle gedeckter Board-Wert — Nachvollziehbarkeitsverlust, kein Risiko an Nutzerdaten.
- **Keine neuen Secrets, keine geänderte Authentifizierung, keine neue Abhängigkeit** (unverändert die lokale `gh`-Session).

## Entscheidungen

- **Verifikationsquelle: GitHubs `closingIssuesReferences` statt eines eigenen Keyword-Parsers.** Der `architect` hatte zunächst einen Regex über den PR-Body vorgesehen; `security-engineer` und `test-engineer` haben unabhängig widersprochen, der `architect` hat den Einwand geprüft und ADR 0046 vor dem Commit überarbeitet. Ausschlaggebend: Die gefährliche Fehlerrichtung ist die falsch-positive, und die kann ein Nachbau prinzipiell nicht ausschließen — die Zusicherung "GitHub schließt dieses Issue beim Merge" kann nur GitHub geben.
- **Prüfkriterium bewusst weiter gefasst als der vorgeschriebene Herstellungsweg** (ADR 0046 Abschnitt 3a): Vorgeschrieben ist die Zeile im PR-Body, geprüft wird ihre Wirkung. Manuell per Seitenleiste verknüpfte Issues bestehen die Prüfung. Der Ausstiegsweg (`gh api graphql` mit `excludeUserLinked: true`) ist in der ADR festgehalten, falls die Regel je lückenlos erzwungen werden soll.
- **`Item closed` wird abgeschaltet, nicht ADR 0037 gelockert.** Der Preis: Schließt Daniel ein Issue künftig von Hand auf GitHub, zieht die Board-Spalte nicht mehr automatisch auf `Done` nach — der sanktionierte Weg ist `set-status --status Done` (setzt beides).
- **Keine repo-weite CI-Prüfung** — sie müsste die Ausnahme für PRs ohne Issue-Bezug heuristisch erraten und würde release-please- und Dependabot-PRs blockieren.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Die Story betrifft ausschließlich GitHub-Metadaten, Skill- und Doku-Dateien sowie `scripts/gh-board.py` — kein konkret benennbarer Anhaltspunkt für eine sichtbare Oberfläche der Anwendung, keine Datei unter `frontend/`.
- **`architect` (Schritt 1), `test-engineer` und `security-engineer` (Schritt 3) wurden konsultiert.**

## Offene Fragen

Beide Punkte sind Daniel vorzulegen; keiner blockiert die Umsetzung.

- **Restrisiko-Bestätigung:** Ist es akzeptabel, dass ein fremder Fork-PR beim Merge ein beliebiges Issue schließen kann? Einschätzung des `security-engineer`: ja — reversibel, keine Daten betroffen, Merge ist bewusste Einzelhandlung, aktuell 0 Forks, Board-Nebeneffekt entfällt mit dem Rollout-Schritt. Die Risikoannahme selbst ist Daniels Entscheidung.
- **`scripts/` im `review-security`-Trigger?** Die Trigger-Tabelle kennt nur `backend/`, `frontend/`, `.env.example`, `.github/workflows/` und Docker-Compose-Netzwerk. Der Umsetzungs-Branch dieser Spec würde also ohne Security-Perspektive reviewt, obwohl er die Auswertung von GitHub-Antworten und damit die Freigabe der Finalisierung ändert. Für diesen Branch wird die Perspektive einmalig explizit angefordert; die dauerhafte Aufnahme von `scripts/` ist eine separate Kosten-/ADR-Frage.

## Out of Scope

- **`CLAUDE.md`-Schärfung:** Der PR-Punkt im Abschnitt "Konventionen" ("referenzieren die zugehörige Spec/das Issue") könnte auf die verbindliche Closing-Zeile geschärft werden. Als Verfassungsdatei wird `CLAUDE.md` in dieser Spec bewusst nicht angefasst — separat Daniel vorzulegen.
- **Repo-weite CI-Prüfung** auf die Closing-Zeile (siehe "Entscheidungen").
- **Automatisierung des Rollout-Schritts** — GraphQL bietet für native Projekt-Workflows keine Deaktivierung.
- **Änderung des Regelwegs** (Issue wird weiterhin vor dem Merge durch `finalize` geschlossen, nicht erst durch GitHub beim Merge). Den Board-Endzustand von einem GitHub-Ereignis nach Sitzungsende abhängig zu machen, wäre das Gegenteil dessen, was diese Story absichert.
