# 0309 - Story-Lebenszyklus in Remote-Sessions: Board-Zugriff probieren statt raten, plus Diagnose-Kommando `doctor`

**Status:** Accepted
**Erstellt:** 2026-09-02
**Bezug:** GitHub-Issue [`#309`](https://github.com/TheRealKoller/photosort/issues/309), ADR [`0051`](../decisions/0051-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md), `scripts/gh-board.py`, `specs/architecture/0002-testkonzept.md`, `specs/architecture/0003-securitykonzept.md`

## Ziel

Daniel möchte PhotoSort nicht nur lokal, sondern auch in Remote-Sessions (Claude Code im Browser/in der Cloud) weiterentwickeln — vom Erfassen einer Idee bis zum abgeschlossenen Pull Request. Ein erster Versuch schlug fehl; vermutet wurde, die GitHub-CLI sei dort nicht nutzbar, weil kein interaktiver Login möglich ist.

Die Vermutung trägt so nicht: `gh` authentifiziert sich problemlos non-interaktiv über einen Umgebungstoken — `.github/workflows/release-please.yml` tut das seit Langem. Die Untersuchung im Rahmen dieser Spec hat stattdessen einen konkreten, lokal beweisbaren Defekt im eigenen Werkzeug gefunden: `GhBoard.check_auth_scope()` urteilt vor jedem Board-Befehl anhand eines Substring-Tests über die `gh auth status`-Ausgabe und schickt bei Token-Authentifizierung in einen interaktiven Login, über den es nichts wissen kann.

Diese Spec behebt genau diesen Defekt und macht den verbleibenden, nur remote beantwortbaren Teil belegbar feststellbar — statt ihn zu raten. Sie baut nicht um, was nicht als fehlerhaft nachgewiesen ist.

## User Story

Als Daniel möchte ich eine Idee auch in einer Remote-Session vom Erfassen über das Schärfen und Umsetzen bis zum abgeschlossenen Pull Request durcharbeiten, damit ich nicht an meinen lokalen Rechner gebunden bin und der Board-Zustand dabei genauso verlässlich bleibt wie bei lokaler Arbeit.

## Akzeptanzkriterien

### Untersuchung

- [ ] Ein `doctor`-Lauf aus einer echten Remote-Session liefert einen JSON-Bericht, der für **jeden** Lebenszyklus-Schritt (`idee-erfassen`, `issue-body-schreiben`, `status-ready`, `spec-anlegen`, `status-in-progress`, `pr-eroeffnen`/`status-review`, `abschluss-finalisieren`) ein Urteil trägt. Kein Schritt bleibt "unbekannt, weil der Lauf vorher abgebrochen ist".
- [ ] Zu jedem blockierten Schritt nennt der Bericht die auslösende Prüfung, ihren `detail`-Text und das redigierte `stderr` des fehlgeschlagenen `gh`-Aufrufs — nicht nur "blockiert".
- [ ] Der Bericht ist wörtlich als Kommentar an Issue #309 gehängt, nach Eröffnung des Umsetzungs-PRs und **vor** dem Merge. (Das Werkzeug, das den Befund erzeugt, entsteht in diesem PR und kann ihm nicht vorausgehen; ausgeschlossen ist ein *unbelegter* Umbau, nicht das Erzeugen des Beweismittels.)
- [ ] Der Kommentar benennt getrennt, was der Bericht **nicht** belegt: Schreibzugriff wird nicht bewiesen, `viewerPermission` wird nur als Indiz gemeldet.

### Zielzustand — Preflight

- [ ] Bei `gh auth status`-Ausgabe mit `Token scopes: none` **und** bei ganz fehlender Scope-Zeile erreicht **jeder** Board-Befehl seinen ersten eigenen `gh`-Aufruf. Nachweis an den protokollierten Argumentlisten, nicht am Rückgabewert.
- [ ] `set-body` läuft ohne jede Scope-Auskunft vollständig durch (`gh issue edit` im Aufruflog).
- [ ] Scheitert die Board-Auflösung und fehlt `project` in einer **vorhandenen** Scope-Zeile des aktiven Kontos, enthält die Meldung `gh auth refresh -s project` **und** den ursprünglichen `gh`-stderr. Die ursprüngliche Meldung wird nie ersetzt, immer nur ergänzt.
- [ ] Enthält die Scope-Zeile `project` und scheitert der Aufruf trotzdem, erscheint **kein** refresh-Hinweis.
- [ ] Im ungestörten Erfolgsfall enthält das Aufruflog **kein** `gh auth status`.
- [ ] Ein erfolgreiches `gh project list` ohne Titeltreffer (umbenanntes Board) wird unverändert gemeldet — ohne Scope-Deutung und ohne `gh auth status`-Aufruf.

### Zielzustand — `doctor`

- [ ] `doctor` beendet sich mit Exit-Code 0 und gibt genau ein JSON-Objekt auf stdout aus, auch wenn jede Prüfung fehlschlägt — inklusive fehlendem `gh`-Binary (`FileNotFoundError`) und `auth_returncode != 0`. Kein Traceback auf stderr.
- [ ] Eine fehlgeschlagene Prüfung beendet den Lauf nicht: alle nachgelagerten Prüfungen sind im Bericht nachweislich ausgeführt.
- [ ] `verdict` ist `ok` genau dann, wenn `blocked_lifecycle_steps` leer ist (abgeleitet, nicht separat geführt).
- [ ] Das Aufruflog eines `doctor`-Laufs enthält **keinen** schreibenden `gh`-Aufruf (`project item-edit|item-add`, `issue create|close|edit`, `pr edit`, `label create`).
- [ ] Keine tokenförmige Zeichenkette erscheint irgendwo im serialisierten Bericht; harmloser Text mit token-ähnlichen Wortanfängen bleibt unverändert.
- [ ] Der Versionsvergleich gegen `MIN_GH_VERSION` ist numerisch, nicht lexikografisch (`2.9.0` ist älter als `2.72.0`).

### Zielzustand — Nicht-Regression

- [ ] Die vollständige bestehende Suite bleibt grün, ohne dass eine bestehende Assertion abgeschwächt wird. Kein bestehender Test wird gelöscht, ohne dass benannt ist, welcher neue Test seine Zusicherung übernimmt.
- [ ] Der Diff enthält keine neue Datei unter `.github/workflows/`, keine neue Variable in `.env.example`, keinen neuen Secret-Bezug — kein zusätzliches, dauerhaft in der Remote-Umgebung abgelegtes Geheimnis.
- [ ] Außer `.claude/skills/github-board/SKILL.md` ist keine Skill-Datei geändert; dort sind ausschließlich die `doctor`-Zeile, der Abschnitt "Fehler zuerst behandeln" und der Lese-vor-Einfügen-Schritt berührt. Keine Aufrufform eines bestehenden Befehls ändert sich.
- [ ] `gh-board.py` bleibt die einzige Board-Schreibstelle; kein nativer GitHub-Projects-Workflow wird aktiviert. ADR 0037 Abschnitt 5 und ADR 0046 Abschnitt 5 bleiben unverändert `Accepted`.

## Datenmodell-Bezug

Nicht relevant. Die Spec berührt ausschließlich Entwickler-Werkzeug (`scripts/gh-board.py`) und keine Anwendungsentität — weder Projekte, Fotos, Kategorien noch Klassifizierungsläufe. Keine Änderung an [`docs/architecture.md`](../../docs/architecture.md) nötig; die Einordnung entspricht ADR 0017/0037/0043/0046, die ebenfalls ohne `docs/`-Update auskamen.

## Architektur / Umsetzung

Die Spec umfasst zwei Dinge: den Fix eines lokal beweisbaren Defekts in der Scope-Prüfung, und ein rein lesendes Diagnose-Subkommando `doctor`, das den Remote-Befund belegbar macht. Grundlage ist ADR [`0051`](../decisions/0051-remote-lebenszyklus-diagnose-kommando-und-echter-board-preflight.md).

Die Grenze zum weiterhin ausgeschlossenen Umbau (ADR 0051, Abschnitt 1) ist mechanisch nachprüfbar: **Lässt sich das Fehlverhalten in einem Unit-Test mit injiziertem `run`-Callable zeigen, gehört es in diese Spec. Braucht es dafür eine echte Session, gehört es in die Folge-Story.** Der Preflight fällt auf die erste Seite, die Frage nach den tatsächlichen Rechten eines fremden Tokens auf die zweite. Ein REST-/GraphQL-Umbau und ein nativer Projects-Workflow als Status-Schreiber bleiben ausgeschlossen.

**Betroffene Dateien:**

| Datei | Änderung |
|---|---|
| `scripts/gh-board.py` | einzige Code-Datei: Preflight-Umbau + Subkommando `doctor` |
| `scripts/tests/test_gh_board.py` | Regressions- und Diagnose-Tests entlang der bestehenden `FakeGh`-Technik |
| `.claude/skills/github-board/SKILL.md` | `doctor` in der Befehlstabelle, Abschnitt "Fehler zuerst behandeln" angepasst, Lese-vor-Einfügen-Schritt |

Kein `docs/`-Update, keine Workflow-Datei, kein Secret, keine Änderung an Board-Feldern.

### Schritt 1 — Preflight: probieren statt raten (zuerst)

Zuerst, weil er den Preflight aus `main()` entfernt, den `doctor` sonst mit einer Sonderregel umgehen müsste, und weil jede Feststellung vorher in erster Linie den eigenen Defekt misst.

1. **Rot:** Test mit `auth_scopes="- Token scopes: none"` (bzw. ganz fehlender Scope-Zeile) — `set-status` läuft heute nicht bis zum `gh project item-edit` durch. Zweiter roter Test: `set-body` setzt heute nichts ab, obwohl es kein Projekt braucht.
2. **Grün:** `check_auth_scope()` samt Aufruf in `main()` entfernen.
3. **Rot→Grün:** `project()` fängt den `BoardError` aus `_run_json` und reichert ihn an — `gh auth status` **nur hier, nur im Fehlerfall**. Fehlt `project` in einer vorhandenen Scope-Zeile des **aktiven Kontos** → Hinweis auf `gh auth refresh -s project` anhängen; keine auswertbare Scope-Zeile → Auth-Quelle als Kontext anhängen. Die ursprüngliche `gh`-Meldung bleibt immer erhalten.

Die Textauswertung ist damit nicht abgeschafft, sondern entmachtet: Sie kann keinen Aufruf mehr verhindern, nur einen bereits gescheiterten erklären. Falsch-negative Urteile werden strukturell unmöglich, weil vor dem Versuch kein Urteil mehr gefällt wird. Nebeneffekt: Der Erfolgsfall kostet einen `gh`-Aufruf weniger, und `set-body` (das nie ein Projekt auflöst) hängt nicht länger an einer Bedingung, die für es nie galt.

**Pflicht-Tests Schritt 1:** Regressionsschutz Token-Auth (alle Board-Befehle laufen bis zum echten `gh`-Aufruf durch, nachgewiesen an den protokollierten Argumentlisten); echter Scope-Mangel bleibt erkennbar; keine Übererkennung; `set-body` läuft ohne jede Scope-Auskunft durch; kein `gh auth status` im Erfolgsfall.

### Schritt 2 — Diagnose-Subkommando `doctor`

**Ausgabe:** ein JSON-Objekt mit `verdict` (`"ok"`/`"blocked"`, bewusst zweiwertig), `gh_version`, `auth` (`authenticated`, `account`, `source`, `scopes`), `probes` (je `id`, `ok`, `lifecycle_steps`, `detail`, redigiertes `stderr`), `blocked_lifecycle_steps`, `note`. `auth.source` — die von `gh` gemeldete Token-Quelle (`keyring`/`oauth_token`/`GH_TOKEN`/`GITHUB_TOKEN`) — ist der wichtigste Einzelwert für die Feststellung.

| Prüfung | `gh`-Aufruf | blockiert bei Fehlschlag |
|---|---|---|
| `gh_binary` | `gh --version` | alle |
| `gh_version` | (dieselbe Ausgabe) gegen `MIN_GH_VERSION`, numerisch | `abschluss-finalisieren` |
| `auth` | `gh auth status` | alle |
| `scope_hint` | (kein eigener Aufruf) Auskunft der Scope-Zeile, **ohne Urteil** | — (reine Information) |
| `repo_access` | `gh repo view <owner>/<repo> --json viewerPermission` | `idee-erfassen`, `issue-body-schreiben`, `pr-eroeffnen` |
| `issue_read` | `gh issue list --limit 1 --json number` | `issue-body-schreiben`, `abschluss-finalisieren` |
| `project_visible` | `gh project list --owner … --format json` + Titel-Treffer | `status-ready`, `status-in-progress`, `status-review`, `abschluss-finalisieren` |
| `fields` | `gh project field-list` gegen `STATUS_VALUES`/`PRIORITY_VALUES` | dieselben |
| `items` | `board._item_list()` | dieselben |

`scope_hint` meldet nur, was die Scope-Zeile sagt — den Zugriff misst `project_visible` tatsächlich. Diese Trennung ist der Grund, warum der Bericht die beiden Ursachen unterscheiden kann.

Kanonisch für die Schrittnamen ist die Liste aus den Akzeptanzkriterien (`idee-erfassen`, `issue-body-schreiben`, `status-ready`, `spec-anlegen`, `status-in-progress`, `pr-eroeffnen`, `status-review`, `abschluss-finalisieren`), nicht eine daneben geführte Aufzählung von Board-Operationen: Der Bericht muss für *jeden* Lebenszyklus-Schritt ein Urteil tragen. `spec-anlegen` ist ein rein lokaler Schritt und wird nur von `gh_binary`/`auth` blockiert, von keiner Board-Prüfung. Die Zuordnungstabelle ist damit total — ein Test prüft das gegen die kanonische Liste.

**Verbindliche Entwurfsentscheidungen:**

1. **Rein lesend.** Kein `project item-edit`, kein `issue create/close/edit`, kein `pr edit`, kein `label create`.
2. **Exit-Code 0, sobald ein Bericht entsteht** — dokumentierte Ausnahme von der `{"error": …}`/Exit-1-Konvention. Fehlgeschlagene Prüfungen sind der Inhalt, nicht das Scheitern.
3. **Fehlendes `gh`-Binary** wirft `FileNotFoundError` statt Returncode ≠ 0 (heute nirgends gefangen) — als Befund melden, nicht als Traceback.
4. **Redaktion + Sanitisierung + Kürzung** jedes übernommenen `stderr` (Details im Abschnitt Security). `gh auth status` wird nie verbatim übernommen, nur extrahierte Felder.
5. **`doctor` nimmt keine Argumente entgegen** — der Subparser bekommt keine, damit gar keine Eingabefläche entsteht.

**Reihenfolge innerhalb Schritt 2:** (1) Redaktions-Helfer als reine Funktion; (2) Prüf-Datenstruktur + statische Lebenszyklus-Zuordnung; (3) Prüfungen einzeln rot→grün in Tabellenreihenfolge; (4) `cmd_doctor()` als Aggregator; (5) CLI-Subparser + `_dispatch`-Zweig.

**Pflicht-Tests Schritt 2:** `doctor` läuft bei `auth_returncode != 0` vollständig durch; `doctor` läuft bei fehlender Scope-Zeile durch und führt nachweislich alle weiteren Prüfungen aus; `gh project list` scheitert → `blocked_lifecycle_steps` enthält genau die vier Board-Schritte, **nicht** `idee-erfassen`; kein schreibender `gh`-Aufruf; Redaktion greift auf tokenförmigem stderr.

### Schritt 3 — `SKILL.md`

`doctor` in der Befehlstabelle; "Fehler zuerst behandeln" beschreibt den Scope-Hinweis als Anreicherung einer echten Fehlermeldung statt als Abbruch vor dem Versuch; Lese-vor-Einfügen-Schritt als Muss (siehe Security, Muss-Kriterium 10). Kein anderer Skill wird angefasst.

### Manueller Schritt außerhalb des `developer`-Auftrags

Daniel/Orchestrator, nach PR-Eröffnung und vor dem Merge (dann liegt der Branch auf dem Remote): Remote-Session auf `feature/0309-story-lebenszyklus-remote-sessions`, `python3 scripts/gh-board.py doctor` ausführen, Ausgabe nach Sichtprüfung als Kommentar an #309. Die schreibenden Schritte werden an **#309 selbst** versucht statt an einem Wegwerf-Issue (`show-status --issue 309`, `set-status --issue 309 --status Review`, später `finalize`) — sie sind ohnehin fällig, es entsteht kein Board-Müll. Scheitert einer, wörtliche Fehlermeldung ans Issue und den Schritt lokal nachholen; das Board bleibt gedeckt, weil in beiden Fällen `gh-board.py` schreibt und Board-Operationen seit Spec 0278 zielzustands-idempotent sind.

### Teststrategie

Alles auf Unit-Ebene gegen das injizierte `run`-Callable — kein echtes `gh`, kein Netzwerk (der CI-Job `demo-scripts` hat beides nicht). Das 80%-Coverage-Gate gilt hier **nicht**: `demo-scripts` fährt nur `ruff check .` + `pytest` über `scripts/`, ohne `--cov`; das Gate aus `CLAUDE.md` betrifft `backend/`. Ersatzmaßstab sind die Pflicht-Tests oben plus Struktur-Assertions auf den Berichtsaufbau (Schlüsselmenge oberste Ebene, Schlüsselmenge je Prüfung).

**Bestehende Tests, die umzuhängen sind — nicht zu löschen:** Die Sektion `# -- Auth-Scope` (`scripts/tests/test_gh_board.py:324`) ruft `check_auth_scope()` direkt auf; ihre drei Tests (Zeilen 327, 337, 345) tragen weiterhin gültige Zusicherungen und bekommen je einen benannten Nachfolger. Gefährdet, obwohl heute grün: der `("gh","auth","status")`-Zweig in `FakeGh._dispatch` (Zeile 145) **bleibt** (wird von Anreicherung und `doctor` gebraucht); `test_unbekanntes_projekt_wird_nicht_angelegt_sondern_gemeldet` (355) braucht eine zusätzliche Assertion, dass kein `gh auth status` läuft; `test_finalize_lehnt_einen_pr_ohne_wirksame_verknuepfung_ab` (Assertion 1541) ist der Sensor dafür, dass die Anreicherung nicht in `_run_text`/`_run_json` abrutscht und darf **nicht** aufgeweicht werden; `test_cli_kennt_alle_in_den_skills_dokumentierten_befehle` (1870) um `doctor` erweitern. `FakeGh` braucht neue Schalter: `auth_scopes=None`, `auth_stream` (stdout/stderr), Opt-in-`FileNotFoundError`.

**Zusätzliche Edge Cases** (über die Pflicht-Tests hinaus): `gh auth status` auf stderr statt stdout; `gh project list` mit Returncode 0 aber ungültigem JSON (kein Scope-Hinweis, nur Auth-Quellen-Kontext); mehrfache `gh auth status`-Aufrufe durch den leeren `project()`-Cache (Assertions dürfen nicht auf exakter Log-Länge aufsetzen); mehrzeiliges `gh --version` und Distributions-Suffixe; `gh issue list` → `[]` ist Erfolg; `viewerPermission` `TRIAGE`/`READ`/`NONE`/`null` sind **nicht** ok, nur `ADMIN`/`WRITE`/`MAINTAIN`; `scopes` muss vier Zustände unterscheiden (Liste mit `project` / ohne / `none` / gar keine Zeile); `gh auth status` ohne Login (Returncode 1) → Bericht entsteht, `account`/`source` sind `null`; `Priorität` (Umlaut) fehlt ganz vs. vorhanden mit fehlenden Optionen; strukturell falsches, aber gültiges JSON; Totalität der Zuordnungstabelle. Details in `specs/architecture/0002-testkonzept.md`, Abschnitt "Erweiterung für ADR 0051".

## UI/UX

Nicht relevant. Die Spec berührt ausschließlich Entwickler-Werkzeug (ein CLI-Subkommando und Skill-Dokumentation) und hat an keiner Stelle eine sichtbare Oberfläche — kein Pfad unter `frontend/`, keine dargestellten Daten, keine berührte Komponente.

## Security

Sicherheitsrelevant (kein Blocker). Kein Anwendungscode, keine Foto-/Projektdaten, kein neues Secret, keine geänderte Authentifizierung. Das führende Schutzziel ist hier ausnahmsweise **Vertraulichkeit**: Der `doctor`-Bericht ist dazu bestimmt, in ein Issue eines **öffentlichen** Repositories kopiert zu werden, und er übernimmt `gh`-stderr, also Fremdtext. Ausführliche Einordnung: `specs/architecture/0003-securitykonzept.md`, Abschnitt "Diagnose-Kommando `doctor` + Wegfall des Scope-Preflights".

**Muss-Kriterien (testgetrieben umzusetzen, im Review abhakbar):**

1. **Redaktion an genau einer Stelle, angewendet auf jede Zeichenkette.** Eine einzige Redaktionsfunktion; jeder Text, der in den Bericht gelangt (`stderr`, `detail`, `note`, jede aus einer `BoardError` gespeiste Meldung), läuft durch sie. Test: ein Bericht mit tokenförmigem Text in *jedem* dieser Felder enthält den Rohwert in keinem davon — geprüft über den vollständigen serialisierten Bericht, nicht über ein Einzelfeld.
2. **Redaktion greift auch im angereicherten Fehlerpfad von `project()`.** Diese Meldung geht über `{"error": …}` an die Skills, die sie wörtlich weiterreichen. Die Anreicherung übernimmt **keinen** Auszug aus `gh auth status`, sondern nur zwei abgeleitete Tatsachen: (a) fehlt `project` in der Scope-Zeile des aktiven Kontos → fester, im Code stehender Hinweis `gh auth refresh -s project`; (b) die Auth-Quelle, abgebildet auf eine geschlossene Menge von Literalen (`keyring`, `oauth_token`, `GH_TOKEN`, `GITHUB_TOKEN`, sonst `unbekannt`). Die ursprüngliche `gh`-Meldung bleibt erhalten, aber redigiert.
3. **Auth-Auskunft ausschließlich aus dem aktiven Konto.** `gh auth status` meldet pro Host mehrere Blöcke; maßgeblich ist der mit `Active account: true`. Test mit zweiblockiger Ausgabe (inaktives Konto *mit* `project`-Scope, aktives Konto ohne): Bericht und Fehlerhinweis beziehen sich auf das aktive Konto.
4. **Whitelist vor Blacklist.** Übernommen werden nur die benannten Felder `authenticated`, `account`, `source`, `scopes`; die `gh auth status`-Ausgabe wird nie verbatim durchgereicht. Der Tokenmuster-Filter (`gh[pousr]_…`, `github_pat_…`, mit Längenuntergrenze) ist zweite Reihe, nicht die tragende Schicht — er kennt weder Alt-PATs im 40-Hex-Format noch Credentials in URL-Form. Deshalb gilt Nr. 5 zusätzlich und unabhängig.
5. **Sanitisierung und Längenbegrenzung jedes übernommenen `stderr`.** Steuerzeichen (`Cc`), Formatzeichen (`Cf`), Bidi-Overrides, Zero-Width-Zeichen und ANSI-Escape-Sequenzen werden entfernt; der Rest wird auf 500 Zeichen pro Probe gekürzt, mit sichtbarer Kürzungsmarkierung. Verhindert, dass ein gesprächiges `gh` (`GH_DEBUG=api`, Stacktrace) halbe Umgebungszustände in ein öffentliches Issue schreibt.
6. **Kein von Dritten befüllbarer Inhalt im Bericht.** Nur strukturelle Metadaten (Zähler, Booleans, `viewerPermission`, Board-/Feldauflösung als Ja/Nein) — keine Issue-Titel, keine Bodies, keine Labels, keine Kommentare, keine fremden Projekttitel. Das Repository ist öffentlich, jeder kann ein Issue mit beliebigem Titel anlegen. Die Einschränkung von `gh issue list` auf `--json number` ist testzusichern.
7. **Rein lesend, testgesichert über die protokollierten Argumentlisten.** Sicherheits-Regressionstest, nicht nur Design-Zusicherung: Ein Diagnosewerkzeug, das in einer noch nicht beurteilten Umgebung beliebig oft laufen soll, darf keinen Zustand hinterlassen.
8. **Härtungsregeln ADR 0017 Abschnitt 5 unverändert:** kein `shell=True`, Argumente ausschließlich in Listenform über dasselbe injizierte `run`-Callable, keine Interpolation gelesener oder aus der Umgebung stammender Werte in Argumente (Owner, Repo, Board-Titel bleiben Modulkonstanten), Bodies weiterhin nur über temporäre Dateien, Spec-Nummern weiterhin gegen `^\d{4}$`.
9. **Prompt-Injection: Bericht ist Daten, keine Anweisung.** Der Bericht wird von einem Agenten mit GitHub-Schreibzugriff gelesen. Weil kein von Dritten befüllbares Feld hineingelangt (Nr. 6), bleibt als Quelle nur `gh`/die GitHub-API selbst. `.claude/skills/github-board/SKILL.md` beschreibt den Bericht ausdrücklich als weiterzugebenden **Befund**, dem nicht gefolgt und dessen Inhalt nicht als Handlungsanweisung ausgeführt wird.
10. **Lesen vor dem Einfügen als Muss-Schritt.** `.claude/skills/github-board/SKILL.md` verankert, dass `doctor`-Bericht und weiterzugebende Fehlermeldungen vor dem Einfügen in ein Issue gelesen werden. Der Filter ist eine Musterliste, keine Entropie-Erkennung; ein Fehlgriff in einem öffentlichen Repository ist nicht zurücknehmbar (Edit-Historie, Mail-Benachrichtigungen). Nicht automatisiert testbar, deshalb als Ablaufregel verankert.

**Ausdrücklich keine Schwächung — der Wegfall von `check_auth_scope()`:** Der Preflight war zu keinem Zeitpunkt eine Autorisierungsgrenze. Er lief lokal, auf dem Rechner, der den Token ohnehin besitzt, und urteilte über einen Text, den `gh` freiwillig ausgibt; durchgesetzt wird Autorisierung ausschließlich serverseitig von GitHub gegen den tatsächlichen Token. Das Werkzeug gewinnt keine neue Fähigkeit — es setzt dieselben `gh`-Subcommands mit denselben Argumenten ab wie zuvor, nur ohne vorgeschaltetes Textorakel. Entlastend zusätzlich: Im Erfolgsfall wird `gh auth status` gar nicht mehr aufgerufen.

**Bewusst in Kauf genommen (Nachvollziehbarkeit, kein Sicherheitsrisiko):** `cmd_create_issue` schreibt in der Reihenfolge `ensure_label` → `create_issue` → `add_item` → `set_status`; erst `add_item` löst das Projekt auf. Bisher brach der Preflight in einer Umgebung mit Repo-, aber ohne Projekt-Berechtigung ab, **bevor** ein Issue entstand — künftig entsteht das Issue und der Lauf scheitert danach an der Board-Aufnahme (Issue außerhalb des Boards). Kein Rechtezuwachs, die Fehlermeldung macht es sichtbar; ein Vorab-Auflösen des Projekts wäre der zurückkehrende Torwächter, den ADR 0051 gerade abschafft.

**Keine neuen Secrets:** unverändert die in der jeweiligen Umgebung bereits vorhandene `gh`-Authentifizierung (remote ein von der Plattform gestellter Umgebungstoken, den wir weder anlegen noch ablegen noch rotieren) — deckt sich mit ADR 0017 Abschnitt 2.

## Entscheidungen

- **Zuschnitt der Story (Daniel, 2026-09-02):** Von "Abhängigkeit zu `gh` entfernen" auf "Story-Lebenszyklus funktioniert in Remote-Sessions" umgeschnitten, lösungsoffen. Grund: Der im Issue vorgeschlagene Weg (Workflows + Closing-Keywords) kann höchstens `Done` setzen — die übrigen fünf Statuswerte und alle Body-Schreibvorgänge passieren, bevor ein PR existiert — und widerspricht ADR 0037 Abschnitt 5 sowie ADR 0046 Abschnitt 5.
- **Umfang der Spec (Daniel, 2026-09-02):** Untersuchung **und** Fix der falsch-negativen Scope-Prüfung in einer Spec, entgegen dem ursprünglichen Vorschlag des `architect`, nur die Untersuchung abzudecken. Grund: Der Fehlalarm ist ein lokal beweisbarer Defekt, kein Verdacht; die Story schließt Umbauten aus, deren *Notwendigkeit* unbelegt ist, nicht die Behebung nachgewiesenen Fehlverhaltens.
- **Preflight-Variante (`architect`, ADR 0051 Abschnitt 2):** Preflight entfällt, die echte Auflösung ist die Probe; die Scope-Auskunft bleibt als Deutung, aber erst *nach* dem Fehlschlag. Verworfen: Warnung statt Abbruch (bräche die "genau ein JSON-Objekt auf stdout"-Konvention); reine Scope-Reparatur (konserviert die Fehlerklasse "vor dem Versuch aus Fremdtext urteilen"); ersatzloser Wegfall ohne Rettung der Meldung (verschlechtert den einen bisher korrekt behandelten Fall).
- **Freigabe des Berichts (Daniel, 2026-09-02):** Lesen vor dem Einfügen wird als Muss-Schritt verankert, statt sich allein auf Whitelist + Redaktion zu verlassen.
- **Umfang des übernommenen `stderr` (Daniel, 2026-09-02):** vollständig, aber redigiert, sanitisiert und auf 500 Zeichen gekürzt — statt nur der ersten Zeile oder gar keinem stderr.
- **`ux-ui-designer` nicht konsultiert (Schritt 2):** Die Story berührt ausschließlich ein CLI-Werkzeug und Skill-Dokumentation; es existiert kein konkret benennbarer Anhaltspunkt für eine sichtbare Oberfläche — kein Pfad unter `frontend/`, keine dargestellten Daten, keine berührte Komponente.
- **Abhängigkeit zu Spec 0302 besteht nicht mehr:** PR #303 ist gemerged, die Änderung an `_item_list()` liegt vor. Die in der Schärfung notierte Reihenfolge-Auflage ist gegenstandslos.

## Offene Fragen

Keine. Die vier in der Konsultation aufgeworfenen Produktfragen (Zuschnitt, Spec-Umfang, Freigabe des Berichts, `stderr`-Umfang) sind entschieden und unter "Entscheidungen" festgehalten.

## Out of Scope

- **Umbau von `gh` auf direkte REST-/GraphQL-Aufrufe.** Ausgeschlossen mit der Begründung aus ADR 0017 Abschnitt 1 (kleinere Angriffsfläche) und weil die bestehenden Tests an den konstruierten `gh`-Argumentlisten hängen.
- **Nativer GitHub-Projects-Workflow als Schreiber des Status-Felds.** Ausgeschlossen; ADR 0037 Abschnitt 5 und ADR 0046 Abschnitt 5 bleiben unverändert `Accepted`.
- **Board-Schreibzugriffe über GitHub Actions.** Deckt den Lebenszyklus prinzipiell nicht ab, da `capture` und `refinement` vor jedem PR stattfinden.
- **Die Zusicherung, dass der Lebenszyklus remote vollständig durchläuft.** Sie hängt an den tatsächlichen Rechten des dort verfügbaren Tokens und ist durch keine Zeile Code hier zusicherbar. Der Remote-Durchlauf *stellt fest*; zeigt er noch eine Lücke, ist das der Auslöser für eine Folge-Story.
- **Ausweitung auf autonom, ohne Daniels Session laufende Agenten.** Der Lebenszyklus bleibt session-getriggert.
- **Änderungen am GitHub-Project-Board selbst** (Feldnamen, Statuswerte, Ansichten) und am Rollenmodell.
- **Nachziehen des `finalize` für Spec 0302** (steht trotz gemergtem PR #303 auf `Accepted`). Von Daniel ausdrücklich zurückgestellt.
