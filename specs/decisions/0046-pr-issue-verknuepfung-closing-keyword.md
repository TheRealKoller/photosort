# 0046 - PR↔Issue-Verknüpfung über ein Closing-Keyword im PR-Body; Board-Status bleibt allein bei `gh-board.py`

**Status:** Accepted
**Datum:** 2026-08-30
**Bezug:** GitHub-Issue [`#251`](https://github.com/TheRealKoller/photosort/issues/251) ("pr sollte issue referenzieren"), `.github/pull_request_template.md`, `.claude/skills/ship-feature/SKILL.md` (Schritt 6/8), `scripts/gh-board.py` (`cmd_finalize`/`_resolve_pull_request`/`closing_pull_requests`), ADR [`0037`](./0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md) (Abschnitt 5 — keine native Board-Automatisierung als Schreiber des Status-Felds; bleibt unverändert gültig, wird hier nur präzisiert und erstmals durchgesetzt), ADR [`0042`](./0042-pre-merge-finalisierung-statt-nachzieh-pr.md) (Pre-Merge-Finalisierung, unverändert), ADR [`0043`](./0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md) (Spec-Nummer = Issue-Nummer, `gh-board.py` als einzige Board-Schreibstelle), ADR [`0045`](./0045-spec-writer-legt-feature-branch-an-ein-pr-pro-story.md) (Feature-Branch bleibt bis `ship-feature` rein lokal), `architect`-, `security-engineer`- und `test-engineer`-Konsultation für Story #251 am 2026-08-30 (die Verifikationsquelle in Abschnitt 3 geht auf den Einwand des `security-engineer` gegen einen selbst geschriebenen Keyword-Parser zurück; die Schema-Befunde zu `excludeUserLinked`/`userLinkedOnly` in Abschnitt 3a und zu `includeClosedPrs` in Abschnitt 3b auf den `test-engineer`).

**Nachtrag (2026-09-05):** **Abschnitt 5** (das Board-Status-Feld bleibt alleinige Domäne von `gh-board.py`, der Workflow `Item closed` wird abgeschaltet) ist durch ADR [`0057`](./0057-board-lebenszyklus-nativ-statt-eigenbau.md) abgelöst: `gh-board.py` entfällt, und `Item closed` wird ausdrücklich **eingeschaltet** — es ist ab dort der Schreiber des Werts `Done`. Der dortige Einwand (ein aus anderem Grund geschlossenes Issue landet dann ebenfalls auf `Done`) wird in ADR 0057, Abschnitt 3 ausdrücklich beantwortet statt überstimmt: `Done` heißt in diesem Projekt „vom Board“, nicht „ausgeliefert“; den Unterschied trägt GitHubs Close-Grund (`completed` gegen `not planned`). **Die Abschnitte 1–4 bleiben unverändert gültig und werden sogar tragend** — `Closes #NNN` im PR-Body erzeugt ab jetzt sowohl den Übergang nach `Review` als auch, über den Merge, den nach `Done`. Diese ADR bleibt `Accepted`. Reiner Verweis, kein nachträgliches Editieren der ursprünglichen Entscheidung/Begründung unten.

## Kontext

Ein Feature-PR nennt sein Issue heute nur als Fließtext (`- Issue: #209` aus `.github/pull_request_template.md`, dazu gelegentlich ein `Ref #NNN`-Trailer). Das erzeugt in GitHub lediglich einen Cross-Reference-Eintrag in der Issue-Timeline, **keine** strukturierte Verknüpfung: Weder zeigt der PR das Issue unter "Linked issues", noch das Issue den PR unter "Linked pull requests".

Drei am Bestand überprüfte Fakten bestimmen die Lösung:

1. **Der bereits eingebaute Ausnahmepfad ist heute funktionsunfähig.** `gh-board.py finalize` **ohne** `--pr-number` (Nachzug nach einem Merge außerhalb des üblichen Ablaufs, ADR 0042) löst den PR über `gh issue view --json closedByPullRequestsReferences` auf. Dieses Feld wird ausschließlich durch ein Closing-Keyword befüllt — für das zuletzt gemergte Issue #209 liefert es `[]`. Der Pfad konnte also seit seiner Einführung in keinem einzigen realen Fall greifen. Die Verknüpfung ist damit keine reine Bequemlichkeit, sondern die fehlende Voraussetzung eines schon getroffenen, getesteten Entwurfs.
2. **Es gibt keine API, um einen PR anders als über ein Closing-Keyword mit einem Issue zu verknüpfen.** Das GraphQL-Schema kennt für die Development-Verknüpfung nur `createLinkedBranch`/`deleteLinkedBranch` (Branch↔Issue, das was `gh issue develop` benutzt); eine Mutation "PR mit Issue verknüpfen" existiert nicht.
3. **Auf dem Board sind entgegen der Annahme von ADR 0037 native Workflows aktiv.** Stand 2026-08-30 im Projekt "PhotoSort Roadmap" (`TheRealKoller`, Projekt #8): `Item closed` **enabled**, `Auto-close issue` **enabled**, `Auto-add sub-issues to project` **enabled**; `Item added to project`, `Pull request linked to issue`, `Pull request merged` disabled. Solange nur `gh-board.py` Issues schließt — und zwar unmittelbar nachdem es selbst `Done` gesetzt hat — ist `Item closed` ein folgenloses Echo der eigenen Schreiboperation. Sobald aber GitHub das Issue beim Merge selbst schließt, wird daraus genau der zweite, unkontrollierte Schreiber auf das Status-Feld, den ADR 0037 Abschnitt 5 ausgeschlossen hat. Das Closing-Keyword ist die Ursache dieses Wechsels und muss die Bereinigung deshalb mitbringen.

Ergänzend relevant: Das Repository squasht mit `squash_merge_commit_message = COMMIT_MESSAGES` — der Merge-Commit übernimmt die **Commit**-Texte, nicht den PR-Body. Wo das Keyword steht, entscheidet damit, ob es in Changelog und release-please-PRs weiterwandert.

## Entscheidung

### 1. Vorgeschriebener Herstellungsweg ist genau einer: `Closes #NNN` im PR-Body

Jeder PR, der ein Issue umsetzt, trägt in seinem **Body** (nicht im Titel, nicht in einer Commit-Nachricht) die Zeile

```
Closes #NNN
```

`NNN` ist die Issue-Nummer, bei neuen Specs identisch mit der Spec-Nummer (ADR 0043), bei Altspecs `0001`–`0065` die Nummer aus der `**Bezug:**`-Zeile der Spec-Datei. Damit erledigt ein einziger Mechanismus beide Anforderungen der Story: GitHub zeigt die Verknüpfung beidseitig strukturiert an (PR: "Linked issues", Issue: "Linked pull requests") und schließt das Issue beim Merge nach `main` automatisch.

Eine manuell über die Development-Seitenleiste gepflegte Verknüpfung wird **nicht als Arbeitsschritt eingeführt** — sie entsteht aus dem Keyword ohnehin von selbst, und für eine automatisierte Herstellung gäbe es keine API (Kontext, Punkt 2).

Wichtig für das Verständnis der folgenden Abschnitte ist die Trennung zweier Dinge, die leicht verwechselt werden:

- **Herstellungsweg** (dieser Abschnitt, verbindlich): Die Verknüpfung wird über die Textzeile im PR-Body erzeugt. Das ist die Anweisung an Vorlage und `ship-feature`.
- **Prüfkriterium** (Abschnitt 3/3a): Verifiziert wird nicht die Zeile, sondern ihre Wirkung — die von GitHub gepflegte Verknüpfung. Diese Prüfung ist bewusst etwas weiter gefasst als der Herstellungsweg.

Das ist kein Widerspruch, sondern eine bewusste Asymmetrie: Vorgeschrieben wird ein Weg, geprüft wird ein Ergebnis. Wer den vorgeschriebenen Weg geht, besteht die Prüfung immer; wer auf anderem Weg dasselbe Ergebnis erzeugt, wird nicht künstlich abgelehnt. Die Begründung dieser Asymmetrie steht in Abschnitt 3a.

### 2. Das Keyword entsteht bei der PR-Eröffnung, verankert an zwei Stellen

- `.github/pull_request_template.md`: Der bisherige Fließtext-Verweis `- Issue: #` wird durch die Closing-Zeile ersetzt, mit einem HTML-Kommentar, der ihren Zweck und den Ausnahmefall erklärt. Der Erklärtext enthält hinter einem `#` **keine Ziffernfolge** — weder eine echte Nummer noch ein Beispiel. Ob GitHub ein Closing-Keyword innerhalb eines HTML-Kommentars auswertet, ist nicht dokumentiert (dokumentiert sind nur die Auswertungsorte PR-Description und Commit-Message, die Keyword-Liste und die Default-Branch-Bedingung); auf eine undokumentierte Eigenschaft stützt sich diese Vorlage nicht. Der Platzhalter `#NNN` ist ohnehin inert, weil `NNN` keine Zahl ist.
- `.claude/skills/ship-feature/SKILL.md`, Schritt 6.3: Die Zeile wird beim `gh pr create` ausgefüllt, nicht als optionale Zierde behandelt.

Das Keyword gehört **nicht** in Commit-Nachrichten: Bei `COMMIT_MESSAGES`-Squash landete es sonst im Merge-Commit, von dort im Changelog und im Body des release-please-Release-PRs — und würde beim Merge des Release-PRs erneut als Schließ-Anweisung ausgewertet.

### 3. `finalize --pr-number` prüft die Verknüpfung — und fragt dafür GitHub, statt den PR-Body selbst zu parsen

Verbindlichkeit, die nur in einer Vorlage steht, ist eine Bitte. Der einzige Punkt im Ablauf, der ohnehin schon mit dem offenen PR spricht, ist `_resolve_pull_request()` in `scripts/gh-board.py`. Dort wird geprüft, ob die Verknüpfung existiert — **nicht**, ob der Body einen Text enthält, der wie ein Closing-Keyword aussieht.

Maßgeblich ist `closingIssuesReferences` aus dem ohnehin abgesetzten `gh pr view` (`--json state,url,baseRefName,closingIssuesReferences` statt bisher `state,url` — kein zusätzlicher API-Aufruf). Das Feld ist GitHubs **eigenes Parse-Ergebnis** der Closing-Keywords dieses PRs. Akzeptiert wird der PR, wenn die Liste einen Eintrag mit `number == <Issue-Nummer>` **und** passendem `repository.owner.login`/`repository.name` enthält (die Einträge sind repo-qualifiziert; ein reiner Zahlenvergleich ließe eine Cross-Repo-Verwechslung zu) und `baseRefName` der Default-Branch ist. Andernfalls bricht `finalize` mit einem `{"error": ...}` ab, das benennt, was fehlt.

Warum nicht selbst parsen: Die gefährliche Richtung ist die **falsch-positive** — wir akzeptieren, GitHub verknüpft aber nicht, und nach dem Merge ist das nicht mehr reparabel. Ein eigener Regex kann diese Richtung prinzipiell nicht ausschließen, weil er GitHubs Parser nur nachbilden könnte: Keyword im HTML-Kommentar, im Code-Fence, im Blockquote, im PR-Titel, Doppelpunkt- und Schreibweisenvarianten, Referenzformen (`#123`, `owner/repo#123`, volle Issue-URL) und die Default-Branch-Bedingung sind teils undokumentiert und jederzeit einseitig änderbar. `closingIssuesReferences` schließt die falsch-positive Richtung dagegen per Konstruktion aus: Ist der Eintrag da, hat GitHub die Verknüpfung hergestellt. Am Beispiel überprüfbar: `microsoft/vscode` PR #332863 nennt seine Issues ausschließlich als volle URLs und liefert trotzdem fünf korrekt aufgelöste Referenzen — ein `#NNN`-Regex hätte hier falsch negativ geurteilt.

Nebeneffekt, der für sich schon zählt: Der PR-Body — von außen befüllbarer Fremdtext — wird gar nicht mehr eingelesen. Es gibt damit keinen Text, der in unserem Prozess interpretiert werden müsste.

Bleibt die Umgebungsvoraussetzung: `closingIssuesReferences` ist über `gh pr view --json` erst ab `gh` 2.72.0 verfügbar. Kein CI-Belang (der Job `demo-scripts` ruft nie ein echtes `gh` auf, das `run`-Callable ist injiziert), aber die Fehlermeldung bei unbekanntem JSON-Feld muss die Mindestversion nennen, damit sie nicht als "Verknüpfung fehlt" fehlgedeutet wird.

### 3a. Manuell verknüpfte Issues werden akzeptiert — geprüft wird die Zusicherung, nicht die Form

Aus der Schema-Introspektion: `closingIssuesReferences` kennt die Argumente `excludeUserLinked` und `userLinkedOnly`, beide mit Default `false`, und `gh pr view --json` übergibt keines von beiden — die Porcelain-Schnittstelle kann das gar nicht. Die Liste enthält damit **auch** Issues, die ohne Closing-Keyword über die Development-Seitenleiste manuell verknüpft wurden.

Daraus folgt eine Lücke, die hier ausdrücklich entschieden und nicht bloß hingenommen wird: Ein PR ganz **ohne** `Closes`-Zeile, dessen Issue nur per Seitenleiste verknüpft wurde, besteht die Prüfung. Die Entscheidung lautet, das so zu belassen und **nicht** über einen `gh api graphql`-Aufruf mit `excludeUserLinked: true` auf strikt keyword-verknüpfte Issues zu verengen.

Grund: Die Prüfung existiert, um genau eine Zusicherung zu geben — "GitHub schließt dieses Issue beim Merge". Ein manuell verknüpftes Issue wird beim Merge genauso geschlossen. Es abzulehnen wäre ein falsch negatives Urteil über einen inhaltlich korrekt verknüpften PR, und die einzige Abhilfe wäre das Nachtragen einer Zeile, die nichts hinzufügt. Die Prüfung wäre damit streng in der Form und blind für das, was sie eigentlich zusichern soll. Auch das Akzeptanzkriterium der Story ist ergebnis- und nicht textbezogen formuliert ("im GitHub-UI eindeutig als zu diesem Issue gehörig erkennbar") — das erfüllt eine manuelle Verknüpfung ebenso.

Bewusst in Kauf genommen: Ein PR kann die Prüfung theoretisch bestehen, ohne die in Abschnitt 1/2 vorgeschriebene Zeile im Body zu tragen. Das ist ein Formfehler mit korrektem Ergebnis, er ist beim Lesen des PR-Bodys sichtbar, und er ist nicht die Fehlerklasse, gegen die diese Prüfung gebaut wurde. Der verbindliche Weg, die Verknüpfung *herzustellen*, bleibt unverändert die Textzeile (Abschnitt 1/2) — Vorlage und `ship-feature` erzeugen sie, die Prüfung misst ihr Ergebnis.

Der zweite Grund wiegt schwerer, als er zunächst klingt: Eine Verengung wäre wieder ein **eigener Begriff von Verknüpfung** — "verknüpft ist nur, was per Keyword verknüpft ist" — und damit genau die Sorte Eigenlogik, die Abschnitt 3 gerade abgeschafft hat, nur eine Ebene höher. Der Unterschied wäre lediglich, dass diesmal GitHub den Filter ausführt statt wir.

Dritter, allein nicht tragender, aber gleichgerichteter Grund: `scripts/gh-board.py` spricht ausschließlich über `gh`-Unterbefehle mit GitHub. Eine handgeschriebene GraphQL-Abfrage allein für diese Verschärfung führte eine neue Zugriffskategorie in die Datei ein und gäbe den Vorteil auf, dass die Prüfung ohne zusätzlichen Aufruf im ohnehin abgesetzten `gh pr view` mitfährt.

Falls die Regel je lückenlos erzwungen werden soll, ist der Weg damit vorgezeichnet und hier festgehalten: Wechsel von `gh pr view --json` auf `gh api graphql` mit explizitem `excludeUserLinked: true`. Das ist keine Konfigurationsschraube, sondern ein Umbau der Abfrage — und eine Entscheidung, die diese ADR bewusst gegen sich getroffen hat.

### 3b. Der Pfad ohne `--pr-number` trägt — trotz irreführender Schema-Beschreibung

`Issue.closedByPullRequestsReferences` hat den Default `includeClosedPrs = false` und die Schema-Beschreibung "open pull requests". Daraus liest man leicht heraus, der Pfad ohne `--pr-number` — der gezielt einen **gemergten** PR sucht — müsse strukturell ins Leere laufen. Das ist falsch: Live geprüft an `cli/cli#10529` liefert das Feld den gemergten PR #10544. `includeClosedPrs` meint ohne Merge geschlossene PRs; gemergte sind immer enthalten, denn sie sind gerade die, die das Issue geschlossen haben.

Das ist hier festgehalten, weil die Schema-Beschreibung in die falsche Richtung zeigt und der Irrtum sonst beim nächsten Lesen erneut entsteht — mit dem naheliegenden, aber unnötigen Umbau des funktionierenden Ausnahmepfads als Folge.

Der Abbruch ist bewusst hart und bewusst früh: `_resolve_pull_request()` läuft vor dem Umschreiben der Spec-Datei und vor jedem Board-Zugriff, es ist also nichts passiert und der Aufruf ist nach einem `gh pr edit --body-file` wiederholbar. Der Zeitpunkt ist der billigste im gesamten Ablauf — der PR ist noch offen, das Nachtragen kostet einen Befehl. Nach dem Merge wäre die Verknüpfung dagegen nicht mehr herstellbar.

Der Pfad **ohne** `--pr-number` braucht keine eigene Prüfung: Er findet den PR über `closedByPullRequestsReferences` am Issue, das ohne hergestellte Verknüpfung leer bleibt. Beide Pfade lesen damit dieselbe von GitHub gepflegte Verknüpfung, nur aus den beiden Richtungen — das Werkzeug hat nach dieser Entscheidung an keiner Stelle mehr einen eigenen Begriff davon, was als Verknüpfung zählt.

### 4. Ausgenommen sind PRs ohne Issue-Bezug — und das bleibt folgenlos

Reine Doku-/Chore-PRs, Release-PRs von release-please und Dependabot-PRs haben kein Issue und lassen die Zeile weg (Template-Kommentar sagt das explizit). Ein Durchsetzungsmechanismus ist für sie weder nötig noch möglich: `finalize` ist per Konstruktion spec-gebunden, läuft für solche PRs also gar nicht. Es gibt bewusst **keine** repo-weite CI-Prüfung auf das Keyword — sie müsste dieselbe Ausnahme wieder heuristisch erraten und würde genau die fremden PRs blockieren, für die die Regel nie gedacht war.

### 5. Das Board-Status-Feld bleibt alleinige Domäne von `gh-board.py` — der Workflow `Item closed` wird abgeschaltet

ADR 0037 Abschnitt 5 bleibt in Kraft und wird hier erstmals tatsächlich durchgesetzt. Einmaliger, manueller Schritt im Projekt-UI (Projekt → Workflows), weil GraphQL für Projects-Workflows nur `deleteProjectV2Workflow` und keine Deaktivierung anbietet:

- **`Item closed` → ausschalten.** Das ist der Workflow, der das Status-Feld schreibt. Bisher war er ein folgenloses Echo, ab dem ersten `Closes #NNN` wäre er ein unabhängiger Schreiber.
- **`Pull request merged` und `Pull request linked to issue` → bleiben aus.** Sie waren bisher wirkungslos, weil unsere Items Issues sind und keine verknüpften PRs existierten; ab jetzt hätten sie einen Angriffspunkt. Ein späteres Einschalten ist eine architekturrelevante Änderung, keine Board-Einstellung nebenbei.
- **`Auto-close issue` → darf anbleiben.** Er schreibt nur den offen/geschlossen-Zustand des Issues, nicht das Status-Feld, und feuert ausschließlich als Reaktion auf ein `Done`, das `gh-board.py` selbst gerade gesetzt hat und dem es ohnehin ein eigenes `gh issue close` folgen lässt. Der Issue-Zustand war nie exklusiv unter Tool-Kontrolle (Daniel schließt/öffnet Issues jederzeit von Hand) — die Einbahnstraßen-Garantie aus ADR 0017/0037 gilt dem Status-Feld, nicht ihm.

Reihenfolge im Regelweg bleibt damit unverändert und ohne Beteiligung von GitHub-Automatik: `finalize` (Pre-Merge) setzt `Done` und schließt das Issue; der spätere Merge findet ein bereits geschlossenes Issue vor, das Keyword ist dort ein No-op. Erst im Ausnahmefall — Merge ohne vorherige Finalisierung — schließt GitHub das Issue selbst, und der nachgezogene `finalize`-Aufruf findet den PR dann über eben dieses Keyword.

## Begründung

- **Closing-Keyword statt Development-Verknüpfung:** Es ist der einzige über eine API erreichbare Weg (Kontext, Punkt 2), es liegt als Text im Repository und ist damit im PR-Template verankerbar statt als unsichtbarer Klick-Zustand, und es liefert Sichtbarkeit und automatisches Schließen in einem — zwei Mechanismen für zwei Akzeptanzkriterien wären hier reine Redundanz.
- **`gh issue develop` (verknüpfter Branch) verworfen:** `createLinkedBranch` würde die Verknüpfung schon bei `spec-writer` herstellen, verlangt dafür aber einen Branch auf dem Remote. ADR 0045 hält den Feature-Branch bis `ship-feature` bewusst rein lokal. Ein Push allein für eine Verknüpfung, die das Keyword ohnehin liefert, kehrt diese Entscheidung ohne Gegenwert um.
- **Vorgeschriebener Weg und Prüfkriterium dürfen auseinanderfallen:** Eine Prüfung, die enger ist als nötig, lehnt korrekte Zustände ab; eine, die genau die Zusicherung misst, um die es geht, tut das nicht. Die Verbindlichkeit der Textzeile ruht deshalb dort, wo sie hingehört (Vorlage und `ship-feature`), nicht in einem Torwächter, der Form mit Wirkung verwechselt.
- **GitHubs Parse-Ergebnis statt eines eigenen Parsers:** Der Zweck der Prüfung ist die Zusicherung "GitHub wird dieses Issue beim Merge schließen". Diese Zusicherung kann nur GitHub geben. Jede Eigenimplementierung wäre eine Nachbildung mit eigener Divergenzklasse, deren Fehler ausgerechnet in die irreparable Richtung zeigen. Dass das Feld ohne zusätzlichen Aufruf mitkommt, macht die schlechtere Variante zusätzlich grundlos.
- **Prüfung in `finalize` statt CI-Gate:** `finalize` läuft genau einmal pro Feature-PR, kennt Spec- und Issue-Nummer bereits, spricht schon mit dem PR und hat für den Fehlerfall eine etablierte, überall dokumentierte Konvention (`{"error": ...}`, nichts geschrieben, wiederholbar). Ein CI-Gate müsste dieselbe Prüfung mit weniger Kontext und mit einer heuristischen Ausnahme für fremde PRs nachbauen.
- **Warum die Prüfung überhaupt Code ist und nicht nur eine Zeile im Skill:** Der Schaden einer vergessenen Zeile fällt erst nach dem Merge auf, wenn sie nicht mehr nachtragbar ist. Genau für solche Fälle ist eine automatisierte, getestete Prüfung an einer ohnehin passierten Stelle verhältnismäßig — im Gegensatz zu einem eigenen Werkzeug, das es dafür nicht braucht.
- **`Item closed` abschalten statt tolerieren:** Es wäre verlockend zu argumentieren, der Workflow schreibe ja denselben Wert (`Done`), den wir ohnehin schreiben, und die von ADR 0037 befürchtete Flip-Flop-Schleife sei mit dem entfallenen vollen Sync-Lauf (ADR 0043) ohnehin nicht mehr möglich. Beides stimmt, trägt aber nicht: Er würde `Done` auch dann setzen, wenn ein Issue aus einem ganz anderen Grund geschlossen wird, während die Spec-Datei noch `Accepted` sagt — ein Board-Wert, den keine lokale Quelle mehr deckt und den nichts wieder zurückrechnet. Ein Sicherheitsnetz, das denselben Wert schreibt wie der kontrollierte Pfad, spart im Regelfall nichts und kostet im Sonderfall die Nachvollziehbarkeit.
- **Keine Änderung an der Reihenfolge von Finalisierung und Merge:** Das Issue vor dem Merge zu schließen (heutiger Regelweg) ist streng genommen etwas früh. Es zu ändern hieße, `finalize` das Schließen wegzunehmen und allein auf das Keyword zu vertrauen — das würde den Board-Endzustand von einem GitHub-Ereignis abhängig machen, das erst nach dem Ende jeder Claude-Session eintritt, und wäre damit das Gegenteil dessen, was diese ADR absichert. Der Preis (ein Issue gilt wenige Minuten vor dem Merge als geschlossen) ist niedriger als der Verlust der Kontrolle.

## Konsequenzen

- **`.github/pull_request_template.md`:** `- Issue: #` weicht der Closing-Zeile samt erklärendem HTML-Kommentar (Zweck, Ausnahmefall "PR ohne Issue-Bezug").
- **`.claude/skills/ship-feature/SKILL.md`:** Schritt 6.3 verlangt das ausgefüllte Keyword; Schritt 8 bekommt den neuen Fehlerfall aus Abschnitt 3 (fehlendes Keyword → `gh pr edit --body-file` nachziehen, `finalize` wiederholen) — er reiht sich in die dort schon beschriebene `{"error": ...}`-Behandlung ein.
- **`.claude/skills/github-board/SKILL.md`:** Die `finalize`-Beschreibung nennt die neue Vorbedingung und begründet, warum der Pfad ohne `--pr-number` sie nicht separat prüft.
- **`scripts/gh-board.py`:** `get_pull_request()` holt `state,url,baseRefName,closingIssuesReferences` statt `state,url` (Rückgabetyp weitet sich von `dict[str, str]` auf `dict[str, Any]` — relevant für `mypy --strict`); `_resolve_pull_request()` prüft im `--pr-number`-Zweig die Verknüpfung repo-qualifiziert gegen die Issue-Nummer plus den Default-Branch, vor jedem Schreibzugriff. Neue Modul-Konstanten neben `DEFAULT_OWNER` für Repository-Name und Default-Branch. Der PR-**Body** wird nicht mehr abgefragt. Umgebungsvoraussetzung `gh` >= 2.72.0 (erst ab dort kennt `gh pr view --json` das Feld) — gehört in die Fehlermeldung, damit ein unbekanntes JSON-Feld nicht als fehlende Verknüpfung fehlgedeutet wird. Tests in `scripts/tests/test_gh_board.py` (Referenz vorhanden / leer / nur auf ein fremdes Issue / gleiche Nummer in einem fremden Repository / falscher Base-Branch; im Ablehnungsfall bleiben Spec-Datei und Board nachweislich unangetastet).
- **`docs/ai-workflow.md`:** Schritt 6 der Ablauftabelle hält fest, dass der PR das Issue per Closing-Keyword verknüpft.
- **`CLAUDE.md`, Abschnitt "Konventionen":** Der PR-Punkt sollte von "referenzieren die zugehörige Spec/das Issue" auf die verbindliche Closing-Zeile geschärft werden. Diese Datei ist die Verfassung des Projekts — die Änderung ist Daniel vorzulegen, nicht nebenbei mitzunehmen.
- **Einmaliger manueller Rollout-Schritt (Daniel, Projekt-UI):** Workflow `Item closed` deaktivieren; `Pull request merged` und `Pull request linked to issue` bleiben deaktiviert. Ohne diesen Schritt entsteht mit dem ersten Keyword ein zweiter Schreiber auf das Status-Feld. Nicht skriptbar (GraphQL kennt keine Deaktivierung, nur `deleteProjectV2Workflow`).
- **Kein Effekt auf `docs/architecture.md`/`docs/setup.md`/Root-`README.md`** — reines Entwickler-/Prozess-Tooling ohne Bezug zur Laufzeitarchitektur oder zum Datenmodell der Anwendung, gleiche Einordnung wie ADR 0037/0042/0043/0045.
- **ADR 0037 bleibt unverändert `Accepted`** und wird nicht editiert: Ihre Entscheidung (Status-Feld nur über den getesteten Tool-Layer) wird hier nicht geändert, sondern erstmals auf dem Board tatsächlich hergestellt. Ein späteres Einschalten eines nativen Status-schreibenden Workflows bleibt architekturrelevant und braucht eine neue ADR, die diese hier als "Superseded" markiert.
