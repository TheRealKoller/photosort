# 0052 - Remote-Lebenszyklus: Diagnose-Kommando plus ein Preflight, der den Zugriff probiert statt ihn aus Text zu raten

**Status:** Accepted
**Datum:** 2026-09-02
**Bezug:** GitHub-Issue [`#309`](https://github.com/TheRealKoller/photosort/issues/309) ("Story-Lebenszyklus in Remote-Sessions"), `specs/features/0309-story-lebenszyklus-remote-sessions.md`, `scripts/gh-board.py` (`check_auth_scope`/`project`/`main`), ADR [`0017`](./0017-github-projects-v2-spec-sync.md) (Abschnitt 1 — `gh`-Subcommands statt roher GraphQL-Queries; Abschnitt 2 — kein eigener Bot-Token, bestehende `gh`-Session mit `project`-Scope, Prüfung durch Parsen von `gh auth status`), ADR [`0037`](./0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md) (Abschnitt 5), ADR [`0043`](./0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md) (`gh-board.py` als einzige Board-Schreibstelle), ADR [`0046`](./0046-pr-issue-verknuepfung-closing-keyword.md) (Abschnitt 5), `specs/architecture/0003-securitykonzept.md`, `architect`-Konsultation für Story #309 am 2026-09-02.

## Kontext

Story #309 will den Story-Lebenszyklus auch in Remote-Sessions (Claude Code im Browser/in der Cloud) durchlaufen können. Sie ist untersuchungsgetrieben formuliert: zuerst belegen, was tatsächlich scheitert, erst danach — und nur falls nötig — umbauen. "Kein Umbau auf Verdacht" ist ein eigenes Akzeptanzkriterium.

Fünf am Bestand geprüfte Fakten bestimmen die Lösung:

1. **`gh` braucht keinen interaktiven Login.** `.github/workflows/release-please.yml` betreibt dieselbe CLI seit Langem über `GH_TOKEN: ${{ secrets.RELEASE_PLEASE_TOKEN }}`. Die im Issue zitierte Vermutung ("die GitHub-CLI ist dort nicht nutzbar, weil kein interaktiver Login möglich ist") ist als generelle Aussage damit widerlegt, bevor irgendetwas untersucht wurde. Was sie *stattdessen* war, ist offen.

2. **`check_auth_scope()` lehnt ab, ohne etwas zu wissen — und das ist lokal beweisbar.** Die Prüfung (`scripts/gh-board.py:199`) testet, ob die Zeichenfolge `project` **irgendwo** in der Ausgabe von `gh auth status` vorkommt, und bricht sonst mit dem Rat `gh auth refresh -s project` ab. Lokal steht dort `Token scopes: 'gist', 'project', 'read:org', 'repo'` — die Prüfung greift. Authentifiziert sich `gh` dagegen über einen Umgebungstoken, meldet `gh auth status` die Quelle (`GH_TOKEN`/`GITHUB_TOKEN`) und für Fine-grained-Tokens `Token scopes: none`; das Wort fehlt, **auch wenn der Zugriff tatsächlich bestünde**. Das ist keine Vermutung über eine fremde Umgebung, sondern eine Eigenschaft unserer eigenen Zeilen: ein Unit-Test, der genau diese Ausgabe einspeist, führt den Fehlalarm hier und heute vor.

3. **Der Fehlalarm blockiert alles.** `main()` ruft `check_auth_scope()` in Zeile 849 vor **jedem** Dispatch auf — auch vor `set-body`, das gar kein Projekt auflöst. In einer token-authentifizierten Umgebung scheitert damit jeder Board-Befehl mit einer Meldung, die auf einen interaktiven Login verweist. Genau das ist die Beobachtung, aus der die Vermutung im Issue entstanden ist.

4. **Ein Preflight ist an dieser Stelle ohnehin redundant.** Jeder Board-Pfad löst über `GhBoard.project()` das Projekt per `gh project list --owner …` auf, bevor er schreibt. Dieser Aufruf ist die Frage, die der Preflight zu beantworten versucht — nur stellt er sie tatsächlich, statt sie aus Text zu erraten.

5. **Die Testtechnik liegt fertig da.** Alle 87 Tests in `scripts/tests/test_gh_board.py` hängen an einem injizierten `run`-Callable; `FakeGh` kann fehlschlagende Auth (`auth_returncode`), beliebige fehlschlagende Teilaufrufe (`failing`) und deren stderr (`failure_stderr`) simulieren, und die Auth-Ausgabe ist über `auth_scopes` frei setzbar. Beides — die Zugriffsprobe und ein Diagnosekommando — ist damit vollständig ohne Netzwerk testbar. Der CI-Job `demo-scripts` fährt `ruff` und `pytest` über `scripts/` ohne Coverage-Gate (das 80%-Gate aus `CLAUDE.md` gilt dem Backend-Package); die TDD-Pflicht besteht unverändert, ein Gate-Risiko nicht.

Diese ADR ist wie 0013/0016/0017/0037/0042–0046 eine Prozess-/Tooling-Entscheidung für den Entwicklungsprozess selbst, ohne Bezug zu PhotoSorts Laufzeitsystem oder Datenmodell.

## Entscheidung

### 1. Die Grenze: belegtes Fehlverhalten wird behoben, fehlende Rechte in fremder Umgebung bleiben offen

Die Story schließt Umbauten aus, deren *Notwendigkeit* unbelegt ist — nicht die Behebung eines nachgewiesenen Fehlverhaltens. Daraus folgt eine Trennlinie, an der sich alles Weitere ausrichtet:

- **In diese Spec gehört, was an unseren eigenen Zeilen als Fehlverhalten beweisbar ist, ohne eine Remote-Session befragen zu müssen.** Das trifft auf den Preflight zu (Kontext, Punkt 2): Er verlangt einen interaktiven Login, obwohl er über den tatsächlichen Zugriff nichts weiß, und ein Unit-Test führt das lokal vor. Ob dieser Defekt in einer Remote-Session *auch* zuschlägt, ist für die Frage, ob er ein Defekt ist, unerheblich.
- **Offen bleibt, was erst der Befund beantworten kann:** ob der in einer Remote-Umgebung verfügbare Token die nötigen Projects-V2-Rechte trägt, und was zu tun wäre, falls nicht. Das ist keine Eigenschaft unseres Codes, sondern einer fremden Umgebung, und keine Zeile hier kann es entscheiden.

Diese Grenze ist scharf und im Zweifel nachprüfbar: Lässt sich das Fehlverhalten in einem Unit-Test mit injiziertem `run`-Callable zeigen, gehört es hierher. Braucht es dafür eine echte Session, gehört es in die Folge-Story.

### 2. Der Preflight entfällt und wird durch die ohnehin stattfindende Auflösung ersetzt

`check_auth_scope()` und sein Aufruf in `main()` verschwinden. An seine Stelle tritt kein neuer Torwächter, sondern der Aufruf, der ohnehin passiert: `GhBoard.project()` löst das Board per `gh project list --owner …` auf, und **das** ist die Zugriffsprobe. Scheitert sie, scheitert der Befehl — mit dem, was tatsächlich vorgefallen ist.

Ein Befehl, der gar kein Projekt braucht (`set-body`, das nur `gh issue edit` absetzt), läuft damit auch dort, wo die Board-Auflösung scheitern würde. Das ist kein Nebeneffekt, den man in Kauf nimmt, sondern der Kern: Der Preflight hat bisher Befehle an einer Bedingung scheitern lassen, die für sie nie galt.

### 3. Die Scope-Auskunft bleibt erhalten — als Diagnosehilfe im Fehlerfall statt als Torwächter

Die bestehende Fehlermeldung hat einen echten Zweck: Eine lokale `gh`-Session ohne `project`-Scope ist ein realer, häufiger und mit genau einem Befehl behebbarer Zustand (`gh auth refresh -s project`, ADR 0017 Abschnitt 2), und wer stattdessen nur eine rohe `gh`-Fehlermeldung sieht, sucht länger. Sie geht deshalb nicht verloren, sondern wechselt die Rolle:

`project()` fängt den `BoardError` aus der fehlgeschlagenen Auflösung und reichert ihn an, bevor er weitergereicht wird. Nur in diesem Moment — **lazy, nur im Fehlerfall** — wird `gh auth status` überhaupt aufgerufen. Meldet es eine Scope-Zeile, in der `project` fehlt, wird der Hinweis auf `gh auth refresh -s project` an die ursprüngliche Meldung angehängt. Meldet es keine auswertbare Scope-Zeile (Token-Auth), bleibt die Meldung bei dem, was `gh` gesagt hat, ergänzt um die Auth-Quelle als Kontext. Die ursprüngliche `gh`-Meldung wird dabei nie ersetzt, immer nur ergänzt.

Damit ist die Textauswertung nicht abgeschafft, sondern entmachtet: Sie kann keinen Aufruf mehr verhindern, sie kann einen bereits gescheiterten Aufruf nur noch erklären. Falsch-negative Urteile sind strukturell unmöglich geworden, weil es kein Urteil vor dem Versuch mehr gibt. Ein Erfolgsfall kostet außerdem einen `gh`-Aufruf weniger als bisher.

Verworfen wurden dabei:

- **Preflight als bloße Warnung statt als Abbruch.** Die Ausgabekonvention ist "genau ein JSON-Objekt auf stdout" — eine Warnung dort bräche sie, auf stderr sähe kein aufrufender Skill sie. Vor allem aber wäre es eine Warnung, die in der Mehrzahl der Fälle falsch ist; solche Warnungen erziehen zum Wegsehen und machen den einen richtigen Fall unsichtbarer, nicht sichtbarer.
- **Die Scope-Zeile nur auswerten, wenn `gh auth status` überhaupt eine liefert, und bei Token-Auth durchlassen.** Das behebt den konkreten Fehlalarm mit der kleinsten Änderung, konserviert aber die Fehlerklasse: Es bliebe ein Urteil, das vor jedem Versuch aus Fremdtext gefällt wird, und das nächste Format eines fremden Werkzeugs erzeugt den nächsten Fehlalarm. Es wäre außerdem in sich uneinheitlich — manche Umgebungen dürften es versuchen, andere nicht, ohne dass der Unterschied etwas über den Zugriff aussagt.
- **Den Preflight ersatzlos streichen, ohne die Meldung zu retten.** Der Zustand "lokale Session ohne `project`-Scope" ist real und die Meldung ist die eingespielte, überall dokumentierte Reaktion darauf (`.claude/skills/github-board/SKILL.md`, Abschnitt "Fehler zuerst behandeln"). Sie fallenzulassen wäre eine Verschlechterung für den einen Fall, der bisher korrekt behandelt wurde.

### 4. Der Befund bekommt trotzdem ein Artefakt: das Subkommando `doctor`

Der Fix beseitigt eine Blockade. Er beantwortet nicht, ob der Lebenszyklus danach remote vollständig läuft — dafür braucht es weiterhin eine Feststellung, und die soll belegt statt anekdotisch sein.

`scripts/gh-board.py` bekommt deshalb ein Subkommando `doctor`, das die Fähigkeiten der Umgebung entlang der Lebenszyklus-Schritte **einzeln** prüft und einen einzelnen JSON-Bericht auf stdout ausgibt. Der Bericht ist das Beweismittel: Er wird unverändert als Kommentar an das Issue gehängt.

Kein neues Werkzeug, kein neues Package, keine neue Abhängigkeit — das Kommando lebt in der Datei, die ohnehin die einzige Board-Zugriffsstelle ist (ADR 0043), spricht wie sie ausschließlich über `gh`-Subcommands (ADR 0017 Abschnitt 1) und benutzt dasselbe injizierte `run`-Callable.

Zwei Eigenschaften, die keiner der übrigen Befehle hat und die es zur Feststellung befähigen:

- **Es läuft weiter, wo die anderen abbrechen.** Jede Prüfung ist unabhängig; eine fehlgeschlagene beendet den Lauf nicht. Ein Durchlauf deckt deshalb den gesamten Lebenszyklus ab statt nur bis zum ersten Fehler zu reichen — was das Akzeptanzkriterium ("die Feststellung deckt den gesamten Lebenszyklus ab") wörtlich verlangt.
- **Es ordnet jeden Befund einem Lebenszyklus-Schritt zu**, über eine statische Zuordnungstabelle. Der Bericht sagt damit nicht "Prüfung X ist rot", sondern "`Idee erfassen` geht, `Status setzen` und `Abschluss finalisieren` gehen nicht".

Dass `doctor` und der Fix aus Abschnitt 2/3 zusammen in einer Spec liegen, hat einen praktischen Grund: Solange der Preflight fälschlich abbricht, misst jede Feststellung in erster Linie unseren eigenen Defekt. Erst nach dem Fix sagt ein Remote-Durchlauf etwas über die Umgebung aus.

### 5. `doctor` ist rein lesend, und das wird per Test festgehalten

Das Kommando löst keinen einzigen schreibenden `gh`-Aufruf aus — kein `project item-edit`, kein `issue create/close/edit`, kein `pr edit`. Ein Test prüft das an den protokollierten Argumentlisten, nicht bloß die Absicht.

Damit ist die Feststellung beliebig oft wiederholbar, sie hinterlässt keinen Board-Wert und kein Wegwerf-Issue, und sie kann dem Kriterium "das Ergebnis ist dokumentiert, bevor irgendetwas umgebaut wird" nicht selbst zuwiderlaufen.

Der Preis ist eine Grenze, die der Bericht ausdrücklich mitführt statt sie zu verschweigen: Schreibzugriff wird **nicht** bewiesen, nur die Repository-Berechtigung (`viewerPermission`) als Indiz gemeldet. Das ist vertretbar, weil jeder schreibende Board-Pfad durch dieselben Auflösungen läuft, die `doctor` liest (Projekt → Feld → Item): Wo diese scheitern, scheitert der Schreibvorgang sicher. Die Gegenrichtung — Lesen grün, Schreiben rot — bleibt möglich und wird durch den begleitenden manuellen Durchlauf (Konsequenzen) abgedeckt, nicht durch ein Schreib-Probe-Kommando.

Weil Abschnitt 2 den Preflight aus `main()` entfernt, braucht `doctor` keine Ausnahme von ihm: Es gibt keinen mehr, den es umgehen müsste. Das ist der zweite Grund, den Fix vorzuziehen — er macht einen Sonderweg überflüssig, statt ihn zu erfordern.

### 6. Was der Umbau *nicht* werden darf, steht schon heute fest — was er wird, nicht

Diese ADR entscheidet nicht, wie ein etwaiger Rest-Umbau aussieht. Sie hält aber fest, welche naheliegenden Wege bereits jetzt ausscheiden, damit sie nicht neu hergeleitet und nicht unbemerkt gegriffen werden:

- **Umbau von `gh` auf direkte REST-/GraphQL-Aufrufe: ausgeschlossen.** Er löst das Problem nicht einmal dann, wenn es besteht. Die Frage ist Autorisierung — welche Rechte trägt der verfügbare Token —, nicht Transport; dieselbe Anfrage mit demselben Token scheitert über GraphQL identisch. Dazu käme der Preis: die 87 Tests prüfen konstruierte `gh`-Argumentlisten und wären praktisch vollständig zu ersetzen, und ADR 0017 Abschnitt 1 hat die kleinere Angriffsfläche von `gh`-Subcommands bewusst gewählt. Ein hoher Preis für keinen Effekt.
- **Ein nativer GitHub-Projects-Workflow als Schreiber des Status-Felds: unverändert ausgeschlossen.** ADR 0037 Abschnitt 5 und ADR 0046 Abschnitt 5 bleiben in Kraft; diese ADR markiert **keine** von beiden als `Superseded` und ändert an ihnen nichts. Der Weg trüge ohnehin nicht: Ein PR-/Closing-Keyword-getriggerter Workflow kann bestenfalls `Done` setzen, während `Unrefined`, `Ready`, `Todo`, `In Progress`, `Review` und sämtliche Body-Schreibvorgänge stattfinden, lange bevor ein PR existiert. Er löste also selbst im besten Fall einen von sieben Schritten und brächte dafür den zweiten, unkontrollierten Schreiber zurück, den beide ADRs ausgeschlossen haben.
- **Ein zusätzliches, dauerhaft in der Remote-Umgebung abgelegtes Geheimnis: ausgeschlossen.** Das ist ein Akzeptanzkriterium der Story und deckt sich mit `specs/architecture/0003-securitykonzept.md` sowie ADR 0017 Abschnitt 2 (kein Bot-Token, keine Secrets-Infrastruktur für Board-Operationen). Ein bereits vorhandenes Credential zu *benutzen* ist davon nicht berührt.

Zeigt der Durchlauf nach dem Fix noch eine Lücke, bleiben im Wesentlichen zwei Richtungen übrig: das in der Umgebung ohnehin vorhandene Credential mit den nötigen Rechten ausstatten, oder die Board-Operationen serverseitig ausführen lassen, wobei Schreiber weiterhin `gh-board.py` selbst wäre und damit keine der beiden genannten ADRs berührt würde. Welche trägt, hängt am Befund und ist hier bewusst nicht vorweggenommen.

## Begründung

- **Warum der Preflight-Fix kein Umbau auf Verdacht ist:** Weil sein Gegenstand kein Verdacht ist. Ein Test, der `gh auth status`-Ausgabe mit Token-Auth einspeist, zeigt heute, dass die Prüfung einen interaktiven Login verlangt, ohne über den Zugriff etwas zu wissen. Unbelegt ist nur, ob dieser Defekt der *einzige* Grund für den gescheiterten Remote-Versuch war — und darüber sagt diese Spec nichts zu, sondern stellt es fest.
- **Warum probieren statt raten, und nicht bloß besser raten:** Ein Torwächter, der vor dem Versuch aus Fremdtext urteilt, kann nur zwei Fehlerarten machen — er lässt zu viel durch (harmlos, der echte Aufruf scheitert ohnehin) oder er lehnt zu Unrecht ab (schädlich, es passiert nichts und die Meldung führt in die Irre). Nur die zweite Art ist das Problem, und sie verschwindet nicht dadurch, dass man die Heuristik verfeinert, sondern nur dadurch, dass vor dem Versuch kein Urteil mehr gefällt wird. Dass der Versuch ohnehin stattfindet (Kontext, Punkt 4), macht die Alternative kostenlos.
- **Warum die Meldung erhalten bleibt, obwohl der Torwächter fällt:** Der Wert der Meldung lag nie im Abbrechen, sondern im Deuten — sie übersetzt einen unspezifischen Fehlschlag in einen Befehl, der ihn behebt. Diese Leistung ist im Fehlerfall genauso verfügbar wie davor, nur ohne den Preis, dafür jeden Aufruf einem Vorurteil zu unterwerfen.
- **Warum die Feststellung überhaupt Code wird, statt eine Handvoll manueller Befehle zu sein:** Weil die manuelle Variante beim ersten Fehler abbricht und pro Versuch einen Datenpunkt liefert, während das Kriterium eine Aussage über den gesamten Lebenszyklus verlangt. Und weil zwei völlig verschiedene Ursachen sich in derselben Fehlermeldung äußern können; ein Werkzeug, das die Fragen getrennt stellt und ihre Antworten nebeneinander legt, ist hier kein Komfort, sondern die Bedingung dafür, dass der Befund etwas taugt.
- **Warum `doctor` trotzdem nicht überkonstruiert ist:** Der Umfang ist eine Handvoll unabhängiger Prüfungen, eine statische Zuordnungstabelle und ein Aggregat — keine Fehlerbehebung, keine Reparaturvorschläge, keine Schreibversuche, kein Zustand. Alles, was es tut, tun die bestehenden Befehle ohnehin; es tut es nur einzeln und ohne abzubrechen. Die Verlockung, daraus ein "repariert sich selbst"-Kommando zu machen, ist durch Abschnitt 5 ausgeschlossen.
- **Warum das Urteil zweiwertig bleibt (`ok`/`blocked`) statt eine Abstufung zu erfinden:** Eine dritte Stufe ("eingeschränkt nutzbar") wäre eine Bewertung, die das Werkzeug nicht treffen kann, ohne zu wissen, welcher Schritt gerade ansteht. Die Nuance trägt stattdessen die Liste der blockierten Lebenszyklus-Schritte — Daten statt Urteil. Dieselbe Trennung, die ADR 0046 Abschnitt 3 zwischen "Wirkung prüfen" und "Form prüfen" zieht.
- **Warum der Bericht redigiert wird:** Er ist dazu bestimmt, in ein öffentliches Issue kopiert zu werden, und er übernimmt `gh`-stderr wörtlich — also Fremdtext, dessen Inhalt wir nicht kontrollieren. `gh auth status` maskiert Token von sich aus, und `--show-token` wird nie übergeben; darauf allein zu bauen, wäre aber eine Zusicherung eines fremden Werkzeugs an einer Stelle, an der ein Fehlgriff nicht zurücknehmbar ist. Ein Filter über tokenförmige Zeichenketten kostet wenige Zeilen — dieselbe Verhältnismäßigkeit wie bei den Härtungsregeln aus ADR 0017 Abschnitt 5.

## Konsequenzen

- **`scripts/gh-board.py`, Preflight:** `check_auth_scope()` entfällt samt seinem Aufruf in `main()`. `project()` fängt den `BoardError` aus der fehlgeschlagenen Auflösung und reichert ihn an: `gh auth status` wird **nur an dieser Stelle und nur im Fehlerfall** aufgerufen; fehlt `project` in einer vorhandenen Scope-Zeile, wird der Hinweis auf `gh auth refresh -s project` angehängt, sonst die von `gh` gemeldete Auth-Quelle als Kontext. Die ursprüngliche `gh`-Meldung wird nie ersetzt. Befehle ohne Board-Bezug (`set-body`) laufen ab jetzt unabhängig von jeder Scope-Auskunft.
- **`scripts/gh-board.py`, Diagnose:** neues Subkommando `doctor` (Subparser ohne Argumente, `_dispatch`-Zweig, `cmd_doctor()`), unabhängige Prüf-Funktionen samt statischer Zuordnung Prüfung → Lebenszyklus-Schritte, eine Redaktions-Hilfsfunktion für tokenförmige Zeichenketten. `doctor` beendet sich mit Exit-Code 0, sobald es einen Bericht erzeugt hat — fehlgeschlagene Prüfungen sind sein Inhalt, nicht sein Scheitern. Das ist eine bewusste, dokumentierte Ausnahme von der `{"error": …}`/Exit-1-Konvention der übrigen Befehle: In der Lage, für die das Kommando existiert, wird der Bericht gebraucht und darf nicht als "kein Ergebnis" durchgereicht werden. Ein fehlendes `gh`-Binary (`FileNotFoundError` statt Returncode ≠ 0) wird gefangen und als Befund gemeldet, nicht als Traceback.
- **`scripts/tests/test_gh_board.py`:** Regressionstest mit einer Token-Auth-Ausgabe (`Token scopes: none` bzw. fehlende Scope-Zeile) — Board-Befehle laufen durch statt abzubrechen; Test, dass der echte Scope-Mangel weiterhin erkennbar bleibt (fehlgeschlagenes `gh project list` + Scope-Zeile ohne `project` → Meldung enthält `gh auth refresh -s project`); Test, dass `set-body` ohne jede Scope-Auskunft durchläuft; Tests für die `doctor`-Klassifikation entlang der bestehenden `FakeGh`-Technik, darunter zwingend: kein einziger schreibender `gh`-Aufruf.
- **`.claude/skills/github-board/SKILL.md`:** `doctor` in der Befehlstabelle mit dem Hinweis, dass es nichts schreibt und sein Bericht gefahrlos in ein Issue kopiert werden kann; der Abschnitt "Fehler zuerst behandeln" beschreibt den Scope-Hinweis ab jetzt als Anreicherung einer echten Fehlermeldung statt als Abbruch vor dem Versuch. Die Aufrufweise aller übrigen Befehle bleibt unverändert — kein anderer Skill wird angefasst.
- **ADR 0017 Abschnitt 2 wird in einem Punkt abgelöst:** Die dort festgelegte Prüfung des `project`-Scopes durch Parsen von `gh auth status` **vor** dem Zugriff gilt nicht mehr; an ihre Stelle tritt die echte Auflösung mit nachgelagerter Deutung. Die eigentliche Entscheidung von ADR 0017 Abschnitt 2 — kein eigener Bot-Token, kein `GH_TOKEN` in `.env.example`, Betrieb über die bereits authentifizierte `gh`-Session — bleibt unverändert gültig. ADR 0017 ist bereits durch ADR 0043 als `Superseded` markiert und wird deshalb nicht erneut umgeschrieben.
- **Kein Effekt auf `docs/architecture.md`/`docs/setup.md`/Root-`README.md`** — reines Entwickler-/Prozess-Tooling ohne Bezug zur Laufzeitarchitektur oder zum Datenmodell, gleiche Einordnung wie ADR 0017/0037/0043/0046. `docs/ai-workflow.md` bleibt unberührt: Ablauf und Rollenmodell ändern sich nicht.
- **Keine neue Datei unter `.github/workflows/`, kein neues Secret, keine Änderung an Board-Feldern oder Board-Workflows.**
- **Ein manueller Schritt, der nicht beim `developer` liegt:** Der Remote-Durchlauf (Bericht erzeugen, an #309 kommentieren, die schreibenden Schritte an #309 selbst versuchen) findet in einer echten Remote-Session statt und ist Sache Daniels bzw. des Orchestrators — wie die manuellen Rollout-Schritte in ADR 0037 Abschnitt 7 und ADR 0046. Sinnvoller Zeitpunkt ist nach der PR-Eröffnung und vor dem Merge, weil der Branch dann auf dem Remote liegt.
- **ADR 0037 und ADR 0046 bleiben unverändert `Accepted`** und werden weder editiert noch abgelöst. Sollte eine Folge-Story doch einen nativen, das Status-Feld schreibenden GitHub-Workflow wählen, bleibt das architekturrelevant und braucht eine neue ADR, die die betroffene als `Superseded` markiert — diese hier tut das ausdrücklich nicht.
- Ein späterer Wechsel dieser Entscheidung (etwa: doch wieder ein textbasierter Preflight, oder `doctor` schreibend erweitern) bleibt architekturrelevant und braucht eine neue, diese ADR als `Superseded` markierende ADR.
