# 0056 - Remote-Grenze des Story-Lebenszyklus: gemessene Board-Fähigkeit statt Session-Erkennung, plus korrigierter Befund zu ADR 0052 Abschnitt 6

**Status:** Accepted

**Nachtrag (2026-09-05, nach dem Messschritt):** Die **Begründung** in Abschnitt 6 ist überholt, die **Entscheidungen** bleiben unverändert gültig. Diese ADR hat ADR 0052 Abschnitt 6 Punkt 1 mit dem Argument abgelöst, die Frage sei „Transport, nicht Autorisierung" — der vom Vermittler in der GraphQL-Meldung benannte REST-Weg trage die Issue-Schritte. Die Messung in einer echten Remote-Session widerlegt das: **Auch REST ist für `gh` gesperrt**, mit einer anderslautenden 403 (`GitHub access is not enabled for this session`); der REST-Verweis der GraphQL-Meldung ist in dieser Umgebung irreführend. Die Grenze verläuft weder an der Autorisierung (ADR 0052) noch am Transport (diese ADR), sondern **am Client**: Dieselbe Session liest und schreibt Issues über die GitHub-MCP-Werkzeuge, angemeldet als Repository-Eigentümer — nur `gh` ist auf beiden Transporten zu, und `scripts/gh-board.py` steht ausschließlich auf `gh`. Die Ablösung von ADR 0052 Abschnitt 6 Punkt 1 bleibt richtig, aber aus einem anderen Grund als hier angenommen: Der Ausschluss beruhte auf einer Annahme über die Ursache, die in keiner ihrer beiden Fassungen zutrifft. **Unverändert bestätigt** ist der Kernbefund und damit alles, was diese ADR tatsächlich entscheidet: Die vier Board-Schritte sind auf jedem in einer Remote-Session verfügbaren Weg verloren — Projects V2 spricht nur GraphQL, GraphQL ist für `gh` gesperrt, und der MCP-Weg bietet für Projects V2 keine einzige Operation an. Die Entscheidungen 1–7 (gemessene Board-Fähigkeit statt Session-Erkennung, einseitige Auswertung, `capabilities` als rein lesendes Betriebssignal, `doctor` unverändert, Entscheidungsvorlage) sind davon nicht berührt. Wortlaut und Ausgaben: [Messbericht an Issue #318](https://github.com/TheRealKoller/photosort/issues/318#issuecomment-5550813926). Reiner Verweis, kein nachträgliches Editieren der ursprünglichen Entscheidung/Begründung unten.

**Datum:** 2026-09-05
**Bezug:** GitHub-Issue [`#318`](https://github.com/TheRealKoller/photosort/issues/318) ("Projekt-Board ist aus Cloud-Sessions nicht erreichbar - Konsequenz entscheiden"), `specs/features/0318-remote-lebenszyklus-grenze.md`, ADR [`0052`](./0052-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md) (Abschnitt 2/3 — kein Urteil vor dem Versuch; Abschnitt 4/5 — `doctor` rein lesend; **Abschnitt 6 Punkt 1 wird durch diese ADR abgelöst**), ADR [`0053`](./0053-gh-bereitstellung-per-umgebungs-setup-script.md) / ADR [`0054`](./0054-setup-script-fehlerregime-und-korrigierte-umgebungsannahmen.md) (`gh`-Bereitstellung remote — hier out of scope), ADR [`0043`](./0043-spec-nummer-gleich-issue-nummer-sync-tool-entfaellt.md) (`gh-board.py` als einzige Board-Schreibstelle), ADR [`0048`](./0048-board-operationen-zielzustands-idempotent.md) (Zielzustands-Idempotenz), ADR [`0037`](./0037-status-lebenszyklus-umsetzungsfortschritt-pr-merge-erkennung.md) (Abschnitt 5) und ADR [`0046`](./0046-pr-issue-verknuepfung-closing-keyword.md) (Abschnitt 5) — beide unverändert `Accepted`, ADR [`0017`](./0017-github-projects-v2-spec-sync.md) (Abschnitt 1 — `gh`-Subcommands statt roher Aufrufe; Abschnitt 5 — Härtungsregeln), `scripts/gh-board.py`, `docs/setup.md`, `specs/architecture/0003-securitykonzept.md`, `doctor`-Bericht Daniels aus einer echten Remote-Session vom 2026-09-05, `architect`-Konsultation für Story #318 am 2026-09-05.

## Kontext

Nach ADR 0053/0054 liegt `gh` in Remote-Sessions vor. Der erste `doctor`-Lauf, der überhaupt bis zu den Board-Prüfungen kommt, liefert damit zum ersten Mal eine Aussage über die *Umgebung* statt über ein fehlendes Binary — und sie fällt anders aus als in Spec 0309 und ADR 0053 angenommen.

**Der Bericht (gekürzt auf das Entscheidungsrelevante):**

```
verdict: blocked, gh_version 2.72.0
auth:  authenticated=false — "Failed to log in to github.com using token (GH_TOKEN)
       ... The token in GH_TOKEN is invalid."
repo_access, issue_read: HTTP 403 — "This GraphQL query is not enabled for this session
       — only the pinned set of PR-review operations is served.
       Use REST via `gh api repos/{owner}/{repo}/...` instead."
project_visible, fields, items: "unknown owner type"
blocked_lifecycle_steps: alle acht
```

Fünf Feststellungen bestimmen diese Entscheidung. Die ersten drei sind belastbar, die letzten zwei ausdrücklich nicht — und diese Trennung ist der eigentliche Ertrag des Laufs.

1. **Der 403 ist eine Endpunkt-Sperre des Vermittlers, keine Autorisierungsentscheidung von GitHub.** Der Wortlaut stammt nicht von GitHub (ein ungültiges Credential beantwortet GitHub mit `401 Bad credentials`, ein fehlender Scope mit einem `403`, der den Scope nennt), sondern von der Zwischenschicht der Session, und er benennt seine eigene Regel: bedient wird ein fest verdrahteter Satz von Pull-Request-Operationen, alles andere über GraphQL nicht. Die Anfrage erreicht GitHub gar nicht erst. **Damit ist die Frage an dieser Stelle Transport, nicht Autorisierung** — genau die Gegenaussage zu der Begründung, mit der ADR 0052 Abschnitt 6 Punkt 1 den Wechsel des Zugangswegs ausgeschlossen hat.

2. **Board-Schritte und Issue-Schritte sind verschieden gelagert.** GitHub Projects (V2) wird ausschließlich über GraphQL bedient; eine REST-Entsprechung existiert nach heutigem Stand der GitHub-API nicht (die REST-Endpunkte der abgelösten "Projects (classic)" sind abgeschaltet). Ein Wechsel des Zugangswegs hilft den vier Board-Schritten deshalb nicht — sie sind unter dieser Sperre strukturell verloren. Die Issue-Schritte dagegen scheitern an derselben Sperre, obwohl der Vermittler für sie ausdrücklich einen anderen Weg benennt (`gh api repos/{owner}/{repo}/...`), den `.claude/skills/ship-feature/SKILL.md` an anderer Stelle bereits erfolgreich benutzt. Ob dieser Weg für die Issue-Operationen wirklich trägt, ist **ungeprüft** und wird von der zugehörigen Story festgestellt, nicht hier entschieden.

3. **`doctor` überzeichnet die Sperre — richtig gemessen, zu weit zugeordnet.** `repo_access` (`gh repo view --json viewerPermission`) und `issue_read` (`gh issue list --json number`) sprechen beide GraphQL und fallen deshalb in denselben 403. Über die statische Zuordnungstabelle blockieren sie `idee-erfassen`, `issue-body-schreiben`, `pr-eroeffnen` und `abschluss-finalisieren` — obwohl gerade PR-Operationen zu dem Satz gehören, den der Vermittler laut eigener Auskunft bedient. Der Bericht ist an dieser Stelle nicht falsch (die Prüfung *ist* fehlgeschlagen), aber seine Zuordnung ist an eine Umgebung geraten, für die sie nicht entworfen wurde. Das ist ein Befund über den Bericht, kein Fehler, der hier zu beheben wäre — siehe Entscheidung 4.

4. **Die gemeldete ungültige Anmeldung ist unbewiesen und macht alles Übrige vorläufig.** `gh auth status` prüft das Token gegen die API; wird diese Prüfung von derselben Sperre abgewiesen, meldet `gh` "invalid" für ein möglicherweise völlig intaktes Token. Die Ursache ist mit den vorliegenden Daten nicht entscheidbar — und solange sie es nicht ist, sind alle Prüfungen, die eine gültige Anmeldung voraussetzen, nicht abschließend beurteilbar. Nur Feststellung 1 ist davon unberührt: Die Sperre greift vor der Authentifizierung, ihr Befund gilt unabhängig von der Token-Lage.

5. **"unknown owner type" ist kein eigenständiger Befund.** `gh project list --owner …` löst den Owner-Typ über GraphQL auf; wird das abgewiesen (Sperre) oder nicht authentifiziert (Punkt 4), kann `gh` ihn nicht klassifizieren und sagt genau das. Die Meldung darf weder als "Board existiert nicht" noch als eigene, dritte Ursache gelesen werden.

Der praktische Schaden, um den es geht, ist unabhängig davon, wie 4 und 2 ausgehen: Der Ablauf warnt an keiner Stelle. Wer eine Story remote beginnt, läuft irgendwo in der Mitte in eine `gh`-Fehlermeldung und lässt sie halb fortgeschrieben zurück.

Diese ADR ist wie 0013/0016/0017/0033/0037/0042–0046/0052–0054 eine Prozess-/Tooling-Entscheidung für den Entwicklungsablauf selbst. Sie berührt PhotoSorts Laufzeitsystem, sein Datenmodell und seine Produktiv-Abhängigkeiten an keiner Stelle.

## Entscheidung

### 1. Es wird keine "Remote-Session" erkannt, sondern die Board-Fähigkeit gemessen

Die Story verlangt, dass der Ablauf "eine Remote-Session erkennt, bevor ein Schritt scheitert". Umgesetzt wird die Wirkung, nicht der Wortlaut: **Erkannt wird nicht die Art der Session, sondern die Fähigkeit der Umgebung.**

Der Grund ist derselbe, aus dem ADR 0052 den textbasierten Preflight abgeschafft hat. Jedes verfügbare Merkmal für "das ist eine Remote-Session" — eine Umgebungsvariable, der Hostname, die von `gh` gemeldete Token-Quelle `GH_TOKEN`, das Fehlen eines Keyrings — ist eine Vermutung über eine fremde Umgebung. Ein lokal per Umgebungstoken betriebener `gh`, ein CI-Lauf und eine Remote-Session sind an diesen Merkmalen nicht unterscheidbar; umgekehrt könnte eine künftige Remote-Umgebung ohne diese Sperre laufen und würde trotzdem gewarnt. Beides sind falsch-negative Urteile aus Fremdtext vor dem Versuch — exakt die Fehlerklasse, die ADR 0052 strukturell beseitigt hat. Sie hier wieder einzuführen, nur weil sie diesmal "Remote-Erkennung" hieße, wäre ein Rückschritt.

Verlässlich feststellbar ist stattdessen genau eine Tatsache, und zwar durch Messung: **Lässt sich das Board auflösen oder nicht?** Der Aufruf dafür (`gh project list --owner …`) ist derselbe, den jeder schreibende Board-Pfad ohnehin als erstes absetzt.

Ausgewertet wird er **nur in der Richtung, in der der Schluss zwingend ist**, und das ist die entscheidende Einschränkung:

- **Scheitert die Auflösung, scheitert jeder Board-Schreibvorgang sicher.** Er läuft durch dieselbe Auflösung; was vor ihr scheitert, erreicht ihn nie. Dieser Schluss ist keine Prognose, sondern eine Eigenschaft des Codepfads (ADR 0052 Abschnitt 5 hält ihn bereits fest).
- **Gelingt die Auflösung, ist damit nichts über den Schreibvorgang bewiesen.** Ein gelungener Lesezugriff wird ausdrücklich nicht als Beleg für den zugehörigen Schreibvorgang geführt. In diesem Fall sagt die Messung nichts und der Ablauf verhält sich unverändert wie heute: Er versucht es.

Die Messung ist damit einseitig — sie kann Schritte als **sicher blockiert** ausweisen, aber niemals einen Schritt als "trägt" freigeben. Das ist keine Schwäche, sondern die Bedingung dafür, dass sie kein Orakel wird.

### 2. Die Messung lebt in `gh-board.py` als neues, rein lesendes Subkommando `capabilities`; die Konsequenz lebt in den Skills

Die Trennung ist scharf und beantwortet die Frage "im Script oder in den Skills" mit *beides, aber nicht dasselbe*:

- **`scripts/gh-board.py` misst und ordnet zu.** Es ist ohnehin die einzige Stelle, die das Board berührt (ADR 0043), es besitzt bereits die Lebenszyklus-Schritte als Datenbestand (`LIFECYCLE_STEPS`, `BOARD_LIFECYCLE_STEPS`, `PROBE_LIFECYCLE_STEPS`), und nur dort ist die Sache ohne Netzwerk testbar.
- **Die Skills entscheiden, was daraus folgt.** Welche Schritte ein Ablauf überhaupt vorhat, was davon schon erledigt ist und wie sein Abschlussbericht aussieht, weiß nur der jeweilige Skill. Das Script trifft dazu keine Aussage und kennt keinen Ablauf.

Neues Subkommando, ohne Argumente, rein lesend:

```
python3 scripts/gh-board.py capabilities
→ {"board_reachable": false,
   "blocked_lifecycle_steps": ["status-ready","status-in-progress","status-review","abschluss-finalisieren"],
   "detail": "<redigierte gh-Meldung samt Deutung>",
   "note": "Ein erreichbares Board ist kein Beleg fuer Schreibzugriff. Nicht genannte Schritte
            sind damit nicht als tragfaehig erwiesen."}
```

Verbindliche Eigenschaften:

1. **Genau ein Board-Aufruf** (`gh project list --owner … --format json`, über die bestehende `GhBoard.project()`-Auflösung samt `_explain_project_failure`); **im Fehlerfall zusätzlich der eine bestehende, rein lesende Deutungsaufruf `gh auth status`**, den `_explain_project_failure()` über `auth_info()` ohnehin absetzt. Also ein Aufruf im Erfolgsfall und beim umbenannten Board, zwei im Fehlerfall — testgesichert als exakte Aufrufliste, nicht als Obergrenze. Der Preis bleibt unter zwei Sekunden pro Ablauf statt neun Aufrufen wie bei `doctor`; das ist der Grund, warum es überhaupt vor jedem Ablauf stehen darf.

   *Korrektur gegenüber dem ersten Entwurf dieser ADR (2026-09-05):* Dort stand „genau ein `gh`-Aufruf". Das trifft nicht zu, sobald die Deutung über `_explain_project_failure` mitbenutzt wird — was Eigenschaft 6 gerade verlangt. `test-engineer` und `security-engineer` haben den Widerspruch unabhängig voneinander gemeldet. Die Alternative (Deutung weglassen, um bei einem Aufruf zu bleiben) wurde verworfen: Sie nähme `detail` die Ursachenunterscheidung, die das Akzeptanzkriterium „nachvollziehbarer Zustand" trägt, und träfe den Entwickler vor die Wahl, die Auflösung zu duplizieren — genau die Drift, die Eigenschaft 4 verhindern soll.
2. **Rein lesend**, mit demselben testgesicherten Nachweis über die protokollierten Argumentlisten wie bei `doctor`.
3. **Exit-Code 0, sobald ein Ergebnis entsteht.** `capabilities` wird damit die **zweite** dokumentierte Ausnahme von der `{"error": …}`/Exit-1-Konvention; ADR 0052 Abschnitt 4 hatte `doctor` als "einzige" bezeichnet, das gilt ab hier nicht mehr. Begründung ist dieselbe: Ein fehlgeschlagener Zugriff ist hier der Inhalt, nicht das Scheitern — ein Kommando, das genau dann mit Exit 1 abbricht, wenn seine Auskunft gebraucht wird, wäre nutzlos.
4. **Die blockierten Schritte werden aus `BOARD_LIFECYCLE_STEPS` abgeleitet, nicht daneben aufgezählt.** Ein Test hält fest, dass `capabilities` und die `project_visible`-Zeile der `doctor`-Tabelle dieselbe Menge nennen. Zwei Kommandos, die dieselbe Frage verschieden beantworten, wären schlimmer als kein zweites Kommando.
5. **Redaktion, Sanitisierung und Kürzung** jeder übernommenen Zeichenkette über dieselbe `redact_for_report`-Funktion — die Ausgabe kann in einem Abschlussbericht oder Issue-Kommentar landen.
6. **Kein Torwächter.** Kein Board-Befehl ruft `capabilities` auf, keiner wird dadurch verhindert. Jeder Befehl läuft unverändert los, wenn er aufgerufen wird. `capabilities` ist eine Auskunft, die ein Skill einholt — nicht eine Bedingung, die das Script prüft.

**Warum ein eigenes Kommando und nicht `doctor`:** `doctor` ist das Beweismittel (ADR 0052 Abschnitt 4) — neun Prüfungen, ein Bericht, der wörtlich in ein öffentliches Issue kopiert wird, mit den daraus folgenden Redaktionsauflagen. `capabilities` ist ein Betriebssignal — ein Bit, das ein Skill vor dem Losgehen abfragt. Verschiedene Rollen, verschiedene Kosten, verschiedene Änderungsrisiken: Würde `doctor` die Steuerungsrolle mit übernehmen, wäre jede spätere Änderung an der Diagnose zugleich eine Verhaltensänderung des gesamten Workflows. Verworfen wurde deshalb auch, `doctor` einen Umfangs-Schalter zu geben — das widerspräche zusätzlich ADR 0052 Abschnitt 5 ("`doctor` nimmt keine Argumente entgegen").

### 3. "Nachvollziehbarer Zustand" ohne Zustandsdatei: die Zielzustands-Idempotenz trägt ihn schon

ADR 0043 hat Zustandsdateien bewusst abgeschafft; eine neue einzuführen, um sich zu merken, welcher Board-Schritt noch aussteht, wäre ein Rückschritt aus demselben Grund wie damals — eine zweite Wahrheit neben dem Board.

Sie ist auch nicht nötig. Board-Operationen sind seit ADR 0048 **zielzustands-idempotent**: `set-status --issue NNN --status Ready` beschreibt einen Zielzustand, nicht einen Übergang, und ist beliebig oft wiederholbar. Was lokal nachzuholen ist, muss deshalb nicht *erinnert*, sondern nur *benannt* werden — es ist vollständig aus Issue-Nummer, Spec-Nummer und dem Schritt ableitbar, an dem der Ablauf stand. Der nachzuholende Befehl ist derselbe, den der Skill ohnehin abgesetzt hätte.

Verbindlich wird deshalb ein Ausgabeverhalten, kein Speicherformat. Trifft ein Ablauf auf einen sicher blockierten Schritt:

1. Er **führt aus, was geht**, und bricht nicht ab.
2. Er **versucht den blockierten Schritt nicht** — der Versuch ist bereits als aussichtslos gemessen.
3. Er **nennt ihn ausdrücklich als ausgelassen**, nie stillschweigend, im festen Abschnitt `## Lokal nachzuholen` seines Abschlussberichts, mit dem wörtlich kopierbaren Befehl.
4. Er **legt dieselbe Liste in das dauerhafte Artefakt**, das der Ablauf ohnehin schreibt (Issue-Kommentar bzw. der `## Lokal nachzuholen`-Abschnitt im PR-Body) — **sofern dieser Kanal in dieser Umgebung trägt**. Trägt er nicht, bleibt es beim Chat-Bericht, und der sagt ausdrücklich, dass er der einzige Träger ist.

Punkt 4 ist bewusst bedingt formuliert: Ob Issue-Schreibvorgänge remote tragen, ist offen (Kontext, Punkt 2). Ein Ablauf, der seine Nachhol-Liste in einen Kanal schreiben *muss*, der möglicherweise gesperrt ist, hätte das Problem nur verschoben.

### 4. `doctor` bleibt unverändert; die Feststellung ist ein einmaliger Handgriff, kein Code

Drei Änderungen an `doctor` liegen nahe und werden alle abgelehnt:

- **Die Prüfungen auf `gh api repos/…` (REST) umstellen, damit der Bericht in dieser Umgebung stimmt.** Das *ist* eine der zur Entscheidung stehenden Richtungen (Entscheidung 7, Richtung B). Sie im Diagnosewerkzeug vorwegzunehmen, hieße die Richtung zu entscheiden, die diese Story ausdrücklich offenlässt.
- **Eine Schreibprobe ergänzen, um Lesen von Schreiben zu trennen.** Verstößt gegen ADR 0052 Abschnitt 5 (rein lesend, testgesichert) und bräuchte eine ADR, die ihn ablöst. Der Wert wäre gering: eine einmalige Umgebungstatsache, für die ein dauerhaftes Werkzeug entsteht.
- **Den 403 als "Sperre des Vermittlers" deuten und anders zuordnen.** `doctor` liefert bewusst Daten statt Urteil (ADR 0052, Begründung zum zweiwertigen `verdict`). Eine Sonderregel für den Wortlaut einer fremden Zwischenschicht wäre wieder Textdeutung als Urteilsgrundlage.

Die von der Story verlangten Feststellungen — ist die Anmeldung wirklich ungültig, trägt der REST-Weg für die Issue-Schritte, welcher der acht Schritte trägt aus welchem Grund nicht — sind **einmalige Messungen in einer echten Remote-Session**, deren Ausgabe wörtlich an das Issue kommt. Sie sind ein manueller Schritt Daniels bzw. des Orchestrators, wie der Remote-Durchlauf in ADR 0052 und der Setup-Script-Eintrag in ADR 0053, und sie erzeugen bewusst **keine** Zeile Code. Maßgeblich ist die tatsächliche Ausgabe, nicht die Ableitung aus einer anderen Ausgabe; getrennt zu messen sind Lesen und Schreiben.

### 5. Die Grenze wird dort dokumentiert, wo vor einer Remote-Session nachgeschlagen wird — mit benanntem Verfallsdatum

`docs/setup.md` trägt seit ADR 0053/0054 den Abschnitt "GitHub-CLI (`gh`)" mit dem Unterabschnitt "Remote-/Cloud-Umgebungen". Genau dort — und nicht in einer neuen Datei — steht ab jetzt auch, was in einer Remote-Session vom Lebenszyklus **nicht** trägt und was das für den Ablauf bedeutet.

Damit die Warnung nicht zur Lüge wird, wenn die Sperre eines Tages fällt, wird an derselben Stelle der **Sensor** benannt, in derselben Form wie die Drift-Erkennung in ADR 0053 Abschnitt 4: Fällt die Sperre, meldet `python3 scripts/gh-board.py doctor` die Prüfung `project_visible` als erfolgreich und führt die vier Board-Schritte **nicht mehr** unter `blocked_lifecycle_steps`; `capabilities` meldet `board_reachable: true`, und die Abläufe hören von selbst auf zu warnen, weil ihre Warnung an der Messung hängt und nicht an einem eingetragenen Satz. Was dann noch nachzuziehen ist, ist die Prosa in `docs/setup.md` — und der Absatz sagt selbst, woran man merkt, dass er fällig ist.

Diese Selbstkorrektur ist der zweite Grund für Entscheidung 1: Eine an einem Umgebungsmerkmal festgemachte Warnung müsste von Hand zurückgenommen werden; eine gemessene verschwindet, sobald der Grund verschwindet.

### 6. ADR 0052 Abschnitt 6 Punkt 1 wird abgelöst — die Begründung ist widerlegt, der Ausschluss fällt, die Richtung bleibt offen

ADR 0052 Abschnitt 6 schließt den Wechsel auf direkte REST-/GraphQL-Aufrufe aus und begründet das wörtlich so: *"Die Frage ist Autorisierung — welche Rechte trägt der verfügbare Token —, nicht Transport; dieselbe Anfrage mit demselben Token scheitert über GraphQL identisch."*

Der Befund sagt das Gegenteil (Kontext, Punkt 1): Die Anfrage scheitert an einer Endpunkt-Sperre, bevor irgendein Recht geprüft wird, und der Vermittler benennt einen anderen Transport ausdrücklich als gangbar. Die tragende Prämisse des Ausschlusses trifft in dieser Umgebung nicht zu.

Daraus folgt genau so viel und nicht mehr:

- **Der Ausschluss fällt.** Der Wechsel des Zugangswegs für die **Issue-** und PR-Schritte ist ab hier eine zulässige, zu bewertende Richtung statt einer erledigten Frage.
- **Er wird nicht zur Empfehlung.** Die zweite Hälfte der damaligen Begründung — der Preis in Tests und Eigenimplementierung — steht unberührt und ist neu zu wägen. Auch bleibt offen, ob der Weg überhaupt trägt (ungeprüft).
- **Für die Board-Schritte ändert sich nichts.** Dort ist die Sperre strukturell (Kontext, Punkt 2), und der Ausschluss bliebe selbst dann richtig, wenn seine ursprüngliche Begründung falsch war.
- **Eine Präzisierung, die dabei erhalten bleibt:** `gh api repos/{owner}/{repo}/…` ist weiterhin ein `gh`-Subcommand. ADR 0017 Abschnitt 1 (kleinere Angriffsfläche durch `gh` statt roher HTTP-Aufrufe) wäre von dieser Richtung also **nicht** verletzt — das Bild vom "Umbau weg von `gh`" trifft sie nicht.

Der Rest von ADR 0052 bleibt unverändert in Kraft: der Wegfall des textbasierten Preflights (Abschnitt 2/3), `doctor` samt Rein-Lesend-Zusicherung (Abschnitt 4/5), der Ausschluss eines zusätzlichen dauerhaft abgelegten Geheimnisses und des nativen Projects-Workflows als Status-Schreiber (Abschnitt 6, Punkte 2 und 3). ADR 0052 wird deshalb **nicht als Ganzes** `Superseded`, sondern erhält — wie ADR 0017 durch ADR 0030 und ADR 0025 durch ADR 0031 — einen reinen Verweis-Nachtrag in der Kopfzeile, ohne dass Entscheidung oder Begründung darunter editiert werden. ADR 0037 Abschnitt 5 und ADR 0046 Abschnitt 5 bleiben unverändert `Accepted`; diese ADR markiert keine von beiden.

### 7. Entscheidungsvorlage: die Richtungen mit Tragweite, Preis und Gegenargument — ausdrücklich ohne Entscheidung

Die Richtungsentscheidung wird hier **nicht** getroffen und keine Konsequenz umgesetzt. Was hier steht, ist die Vorlage dafür — an derselben Stelle und in derselben Rolle wie ADR 0052 Abschnitt 6, der ebenfalls die Wege ordnete, ohne den nächsten zu wählen.

Zwei Punkte sind erst durch den Befund sichtbar geworden und liegen quer zu allen Richtungen:

- **Board-Schritte und Issue-Schritte müssen getrennt entschieden werden.** Keine einzelne Richtung löst beide. Jede Wahl ist entweder eine Teillösung oder eine Kombination.
- **Der bisherige Ausschluss des Zugangswegwechsels stand auf einer Annahme, die der Befund nicht stützt** (Entscheidung 6). Wer die Vorlage liest, darf Richtung B nicht als "schon abgelehnt" überspringen.

Alle Richtungen stehen zusätzlich unter dem Vorbehalt aus Kontext-Punkt 4: Solange die Anmeldung nicht geklärt ist, ist keine Bewertung endgültig.

| # | Richtung | Löst | Berührte Festlegungen | Preis / was dagegen spricht |
|---|---|---|---|---|
| A | **Nichts weiter tun** — es bleibt beim ehrlichen Ablauf aus dieser Story, Board-Schritte werden lokal nachgeholt | nichts zusätzlich | keine | Remote bleibt ein Teil-Arbeitsmodus; jede remote begonnene Story braucht einen lokalen Nachlauf, das Board hinkt zeitweise hinterher. Das Ziel "Remote ist ein normaler Arbeitsmodus" wird nicht erreicht |
| B | **Zugangsweg wechseln, wo er trägt:** Issue- (und ggf. PR-)Operationen über `gh api repos/{owner}/{repo}/…` statt über die GraphQL-sprechenden `gh`-Subcommands | die Issue-Schritte — **nie** die Board-Schritte | ADR 0052 Abschnitt 6 Punkt 1 (durch Entscheidung 6 bereits abgelöst); ADR 0017 Abschnitt 1 **nicht** verletzt, `gh api` ist ein `gh`-Subcommand | Ungeprüft, ob es trägt. Pro Operation ein selbst geschriebener API-Pfad samt JSON-Auswertung statt eines fertigen Subcommands — mehr Eigencode an einer bewusst dünnen Stelle, mehr Formatwissen im Repo. Die Testtechnik trägt (auch `gh api`-Aufrufe sind Argumentlisten), der Umbauaufwand ist also kleiner als ADR 0052 unterstellt hat, aber nicht klein. Und: ein Umbau für die Regeln einer fremden Zwischenschicht, die sich ändern können |
| C | **Vorhandenes Credential mit den nötigen Rechten ausstatten** (die von ADR 0052 offen gelassene erste Richtung) | vermutlich nichts | keine | **Durch den Befund weitgehend entwertet:** Die Sperre greift vor der Rechteprüfung. Mehr Rechte helfen nicht, wenn die Anfrage nicht ankommt. Zudem kein Hebel — das Credential stellt die Plattform |
| D | **Board-Operationen serverseitig ausführen**, `gh-board.py` bleibt der Schreiber (die von ADR 0052 offen gelassene zweite Richtung): ein `workflow_dispatch`-Workflow, aus der Session per `gh api …/actions/workflows/…` angestoßen | die Board-Schritte | ADR 0043 gewahrt (Schreiber bleibt `gh-board.py`); **kollidiert sehr wahrscheinlich mit ADR 0052 Abschnitt 6 Punkt 3** | Der `GITHUB_TOKEN` einer Action kann Projects (V2) auf Owner-Ebene nicht schreiben — es braucht ein hinterlegtes PAT-/App-Credential, also genau das ausgeschlossene zusätzliche Geheimnis. Dazu: Asynchronität (Fehler nicht mehr im Ablauf sichtbar), ein zweiter Ausführungsort, neue Dateien unter `.github/workflows/`. Offen, ob der Anstoß selbst durch die Sperre kommt |
| E | **Nativer Projects-Workflow plus Kommentar-Verlinkung** (Daniels Richtungstendenz aus dem Refinement) | die Board-Schritte, potenziell alle sechs Statuswerte | ADR 0037 Abschnitt 5 **und** ADR 0046 Abschnitt 5 müssten abgelöst werden; ADR 0043 nur dann nicht, wenn auch hier `gh-board.py` schreibt; ADR 0052 Abschnitt 6 Punkte 2 und 3 | Der alte Einwand "kann bestenfalls `Done` setzen" fällt, wenn ein Kommando-Kommentar der Auslöser ist — dafür kommen zwei neue: dasselbe Geheimnis-Problem wie D, und eine echte Angriffsfläche, weil das Repository öffentlich ist und **jeder** kommentieren kann; ein `issue_comment`-Auslöser müsste den Autor prüfen und wäre eine sicherheitsrelevante Konstruktion. Dazu Kommentar-Rauschen am Issue und ein zweiter Schreiber neben dem Ablauf |
| F | **Board-Aktualisierung bewusst entkoppeln:** remote wird gearbeitet, der Board-Zustand am Ende lokal gebündelt nachgezogen | nichts technisch — es macht A zur Regel statt zur Notlösung | keine | Ehrlichster kleinster Weg, ändert aber die Bedeutung des Boards: Es beschreibt dann nicht mehr verlässlich, was gerade in Arbeit ist — genau in dem Moment, in dem zwei Umgebungen im Spiel sind |
| G | **Warten und beobachten:** nichts bauen, `doctor`/`capabilities` als Sensor, Neubewertung, wenn die Sperre fällt | nichts | keine | Kosten null, Hebel null, Dauer unbestimmt. Vertretbar nur, solange A/F den Alltag tragen |

Sinnvolle Kombinationen (B für die Issue-Schritte plus A/F/G für die Board-Schritte) sind ausdrücklich zulässig; sie sind die einzige Form, in der beide Ursachen zugleich adressiert werden.

## Begründung

- **Warum "Fähigkeit messen" und nicht "Session erkennen", obwohl die Story das andere sagt:** Beide erfüllen das operative Ziel (vorher warnen), aber nur eines ist ohne Raten machbar. Eine Merkmalserkennung müsste über eine fremde Umgebung urteilen, bevor sie etwas versucht hat — die Fehlerklasse, die ADR 0052 abgeschafft hat —, und sie würde beim Wegfall der Sperre weiterwarnen, bis jemand sie von Hand zurücknimmt. Die Messung ist nicht die bequemere, sondern die einzige, die nicht altert. Dass die Story anders formuliert ist, ist kein Widerspruch, den man verschweigt: Es steht als bewusste Abweichung in der Spec, wie ADR 0053 Abschnitt 7 es mit einem überstimmten Kriterium gehalten hat.
- **Warum das kein wiederauferstandener Preflight ist:** Drei Unterschiede, jeder für sich hinreichend. Er urteilt nicht aus Fremdtext, sondern aus einem tatsächlich abgesetzten Aufruf. Er verhindert keinen Befehl — kein Board-Befehl fragt ihn, jeder läuft unverändert los. Und er ist einseitig: Er kann nur blockiert-melden, nie freigeben. Der abgeschaffte Preflight hatte alle drei Eigenschaften umgekehrt.
- **Warum die einseitige Auswertung nicht Bequemlichkeit ist:** Sie ist die logische Form des Befundes. "Auflösung scheitert ⇒ Schreibvorgang scheitert" ist zwingend, weil der Schreibvorgang durch die Auflösung hindurchmuss. Die Umkehrung ist es nicht — und genau das verlangt das Akzeptanzkriterium, das Lesen und Schreiben trennt.
- **Warum ein zweites Kommando neben `doctor` vertretbar ist:** Nicht wegen der Laufzeit allein, sondern wegen der Rollen. Eine Diagnose, die man gelegentlich zieht und in ein öffentliches Issue klebt, und ein Betriebssignal, das vor jedem Ablauf steht, haben verschiedene Anforderungen an Umfang, Ausgabestabilität und Änderungsrisiko. Die Gefahr des zweiten Kommandos ist Drift — die wird an der Wurzel adressiert, indem beide dieselbe Konstante lesen und ein Test ihre Übereinstimmung festhält.
- **Warum keine Zustandsdatei entsteht, obwohl "Zustand hinterlassen" gefordert ist:** Weil der Zustand schon irgendwo steht. Board-Operationen beschreiben Zielzustände (ADR 0048); was fehlt, ist damit ableitbar statt erinnerungspflichtig. Eine Datei, die aufschreibt, was ohnehin aus Issue-Nummer und Ablaufstelle folgt, wäre eine zweite Wahrheit mit eigenem Veralterungsrisiko — genau das, was ADR 0043 abgeschafft hat.
- **Warum die Feststellung Handarbeit bleibt, während 0309 dafür Code gebaut hat:** Der Unterschied ist die Wiederholbarkeit. 0309 brauchte eine Aussage über **alle acht Schritte in einem Lauf**, den kein manueller Ablauf liefert, der beim ersten Fehler abbricht — daraus wurde `doctor`. Hier geht es um zwei einzelne, einmalige Fragen (ist das Token wirklich kaputt; trägt der REST-Weg), deren Antworten Umgebungstatsachen sind und nach ihrer Beantwortung nie wieder gemessen werden müssen. Werkzeug dafür zu bauen, hieße die Antwort in Code zu gießen, bevor man sie kennt.
- **Warum die Korrektur an ADR 0052 jetzt passiert und nicht erst mit der Richtungsentscheidung:** Eine ADR ist unveränderlich; ihre Begründung wirkt weiter, bis eine neue sie ablöst. Bliebe die widerlegte Prämisse unkommentiert stehen, würde die nächste Betrachtung — von wem auch immer — Richtung B als "geprüft und ausgeschlossen" überspringen, auf einer Grundlage, die der Befund nicht trägt. Das Feststellen einer widerlegten Prämisse ist zudem keine Richtungsentscheidung: Der Ausschluss fällt, die Wahl bleibt offen. Genau diese Trennung verlangt die Story.

## Konsequenzen

- **`scripts/gh-board.py`:** neues Subkommando `capabilities` (Subparser ohne Argumente, `_dispatch`-Zweig, `cmd_capabilities()`), das die bestehende Board-Auflösung als Messung benutzt und die blockierten Schritte aus `BOARD_LIFECYCLE_STEPS` ableitet. Exit-Code 0, sobald ein Ergebnis entsteht; der Modul-Docstring wird von "einzige Ausnahme `doctor`" auf zwei benannte Ausnahmen korrigiert. `doctor` selbst bleibt **unverändert**; an den Prüfungen, ihrer Zuordnung und ihrer Transportwahl ändert sich keine Zeile.
- **`scripts/tests/test_gh_board.py`:** Tests entlang der bestehenden `FakeGh`-Technik — Erfolgs- und Fehlerfall, Exit-Code 0 in beiden, kein schreibender `gh`-Aufruf, die **exakte** Aufrufliste je Fall (ein Aufruf im Erfolgsfall und beim umbenannten Board, zwei im Fehlerfall — siehe Eigenschaft 1), Übereinstimmung der gemeldeten Schrittmenge mit der `project_visible`-Zeile aus `PROBE_LIFECYCLE_STEPS`, Ableitung aus `BOARD_LIFECYCLE_STEPS` per Monkeypatch der Quellkonstante statt bloßem Konstantenvergleich, Redaktion **und Kürzung** auf tokenförmigem bzw. gesprächigem `stderr`, fehlendes Binary als Befund statt Traceback, `capabilities` in der CLI-Parametrisierung. Die vollständige Pflicht-Test-Liste steht in `specs/features/0318-remote-lebenszyklus-grenze.md`, Abschnitt "Teststrategie".
- **Redaktion des zusammengesetzten `detail`-Texts:** `_explain_project_failure()` redigiert `str(error)` und hängt den Deutungstext **danach** an; `cmd_capabilities()` muss `redact_for_report` deshalb ein zweites Mal auf den fertigen Text anwenden, sonst gilt die 500-Zeichen-Kürzung aus Eigenschaft 5 für `capabilities` faktisch nicht. Eigener Pflicht-Test (`test-engineer`-Befund, 2026-09-05).
- **`.claude/skills/github-board/SKILL.md`:** `capabilities` in der Befehlstabelle; ein neuer Abschnitt beschreibt das Muster "Board nicht erreichbar" (ausführen was geht, blockierten Schritt nicht versuchen, ausdrücklich als ausgelassen melden, Nachhol-Befehl nennen, nicht abbrechen) **einmal vollständig** — die aufrufenden Skills verweisen darauf, statt es zu wiederholen.
- **`.claude/skills/capture/SKILL.md`, `.claude/skills/refinement/SKILL.md`, `.claude/skills/spec-writer/SKILL.md`, `.claude/skills/ship-feature/SKILL.md`:** je der Verweis, vor dem ersten Board-Aufruf `capabilities` auszuwerten und im Blockierungsfall dem Muster zu folgen, samt Abschnitt `## Lokal nachzuholen` im jeweiligen Abschlussbericht. `.claude/agents/developer.md` bleibt **unverändert** — sein Board-Schritt ist ausdrücklich ein Hinweis an den Aufrufer, und der ist über die Skills gebunden.
- **`docs/setup.md`:** der Unterabschnitt "Remote-/Cloud-Umgebungen" benennt die Grenze (welche Schritte remote nicht tragen und warum sie verschieden gelagert sind), das Verhalten des Ablaufs, und den Sensor, an dem auffällt, dass der Absatz überholt ist.
- **`docs/ai-workflow.md`:** ein kurzer Zusatz bei "Zwei Arbeitsmodi" mit Verweis auf `docs/setup.md` — der Ablauf bekommt an seinem Anfang eine Umgebungsprüfung, und die Tabelle dort ist laut eigener Aussage "die einzige Stelle für den Gesamtüberblick". Kein Umbau der Tabelle.
- **`docs/architecture.md` und Root-`README.md`: unverändert** — Entwickler-/Prozess-Tooling ohne Bezug zu Laufzeitarchitektur oder Datenmodell, gleiche Einordnung wie ADR 0017/0033/0037/0043/0046/0052/0053.
- **`specs/decisions/0052-…md`** erhält einen **reinen Verweis-Nachtrag** in der Kopfzeile (Abschnitt 6 Punkt 1 abgelöst durch diese ADR, alle übrigen Abschnitte unverändert gültig, ADR bleibt `Accepted`). Entscheidung und Begründung darunter werden nicht angefasst — dieselbe Form wie der Nachtrag in ADR 0017 und die Status-Zeilen-Ergänzung in ADR 0025.
- **Ein manueller Schritt außerhalb des `developer`-Auftrags:** die Feststellung in einer echten Remote-Session (Anmeldung klären, REST-Weg für die Issue-Schritte messen, Lesen und Schreiben getrennt, je Schritt Sperre vs. Zugangsweg) samt wörtlicher Ausgabe als Kommentar an Issue #318 — vor dem Merge, wie in ADR 0052 und ADR 0053. Vor dem Einfügen gilt der Lese-Muss-Schritt aus `.claude/skills/github-board/SKILL.md`.
- **Es entstehen nicht:** eine Zustandsdatei, eine Datei unter `.github/workflows/`, ein Secret, eine neue Variable in `.env.example`, eine Änderung an Board-Feldern oder Board-Workflows, eine Änderung an der `gh`-Bereitstellung aus ADR 0053/0054, eine Ausweitung auf autonom laufende Agenten.
- **Nicht Teil dieser Entscheidung:** die Richtungswahl aus Entscheidung 7 und jede ihrer Konsequenzen; eine Umgehung der Sperre; eine Umstellung irgendeines Aufrufs auf REST.
- Die Richtungswahl bleibt architekturrelevant und braucht eine eigene ADR, die die dann berührten Festlegungen benennt und ablöst. Ein späterer Wechsel *dieser* Entscheidung — etwa doch eine merkmalsbasierte Session-Erkennung, `capabilities` schreibend oder als Torwächter, oder ein Verzicht auf die Messung zugunsten eines eingetragenen Satzes in der Doku — bleibt ebenfalls architekturrelevant und braucht eine neue, diese ADR als `Superseded` markierende ADR.
