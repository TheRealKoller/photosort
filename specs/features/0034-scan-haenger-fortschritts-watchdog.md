# 0034 - Scan-Hänger-Detektion: Fortschritts-Watchdog gegen dauerhaft hängende Job-Läufe

**Status:** Implemented ([PR #67](https://github.com/TheRealKoller/photosort/pull/67))
**Erstellt:** 2026-08-09
**Bezug:** Bug-Report von Daniel selbst (interaktive Session, `specs/inbox/0012-scan-haengt-bei-scan-laeuft.md`, nach Aufnahme in diese Spec gelöscht). ADR [`decisions/0019-job-lauf-heartbeat-watchdog.md`](../decisions/0019-job-lauf-heartbeat-watchdog.md) (Accepted, 2026-08-09). Direkter Nachfolger von [Spec 0023](./0023-scan-fortschritt-batch-groesse-fix.md), die den Exception-basierten Hänger-Fall bereits behoben, den hier behandelten Fall aber explizit als "eigenständige, größere Funktionalität ... außerhalb des Scopes" ausgeklammert hatte ("Watchdog/Heartbeat-Mechanismus für Hänger *ohne* Exception").

## Ziel

Ein Scan-/Scoring-/Top-Selection-Lauf bleibt manchmal dauerhaft im Zustand "läuft", auch nach einem Neustart des Worker-Containers — der zugehörige DB-Eintrag (`ScanRun`/`ScoringRun`/`TopSelectionRun`) bleibt für immer auf `status="running"` stehen, ohne dass der Nutzer je einen Fehler oder Fortschritt sieht.

Root Cause (verifiziert, Details in ADR 0019): `arq` (der Job-Queue-Worker) verwendet ohne explizite Konfiguration seinen Default-`job_timeout` von 300 Sekunden. Läuft ein Job länger, bricht `arq` ihn per `asyncio.CancelledError` ab — derselbe Pfad wird auch bei einem geplanten Worker-Shutdown (z.B. Container-Neustart) ausgelöst. `run_project_scan`/`run_project_scoring`/`run_top_selection` fangen in ihrem Fehlerbehandlungs-Block bisher bewusst nur `except Exception`, `CancelledError` (seit Python 3.8 `BaseException`) läuft ungefangen durch — der zugehörige Run-Eintrag wird nie auf `FAILED` gesetzt. Zusätzlich requeued `arq` den abgebrochenen Job standardmäßig automatisch im Hintergrund (`retry_jobs=True`), wodurch bei jedem Versuch eine komplett neue Run-Zeile entsteht, während die alte(n), am Timeout gescheiterte(n) Zeile(n) als Karteileiche(n) auf `running` stehen bleiben.

Bindende Anforderung (per Rückfrage an Daniel bestätigt): legitim lange Scans (sehr große Fotobibliotheken) **müssen** erfolgreich durchlaufen können — ein festes Zeitlimit als primärer Fehlermechanismus ist nicht akzeptabel. Eine reine `job_timeout`-Erhöhung würde das ursprüngliche Problem nur auf eine größere Zahl verschieben, es aber nicht strukturell lösen. Diese Spec führt deshalb eine **fortschrittsbasierte** statt zeitbasierte Stillstandserkennung ein (siehe Architektur-Abschnitt).

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich einen Scan-/Scoring-/Top-Selection-Lauf durchführen können, ohne dass dieser unbegrenzt im Zustand "läuft" steckenbleibt — auch nicht bei sehr großen Fotobibliotheken, die legitim lange brauchen dürfen — damit ich mich darauf verlassen kann, dass der Lauf entweder erfolgreich abschließt oder mit einer erkennbaren Fehlermeldung endet, die ich über die bereits bestehende "Erneut versuchen"-UI direkt beantworten kann.

## Akzeptanzkriterien

- [ ] Bei `asyncio.CancelledError` in `run_project_scan`/`run_project_scoring`/`run_top_selection` (ausgelöst durch `job_timeout`-Ablauf, Worker-Shutdown oder einen künftigen `Job.abort()`) wird der zugehörige Run **vor** dem erneuten `raise` sofort auf `status=FAILED` mit gesetzter, erklärender `error_message` gesetzt — die Exception wird nicht verschluckt, `arq`s eigene Task-/Retry-Buchhaltung funktioniert unverändert weiter.
- [ ] `ScanRun`, `ScoringRun` und `TopSelectionRun` haben eine neue Spalte `last_progress_at` (additiv, Migration), die an genau den Stellen aktualisiert wird, an denen die drei Jobs heute bereits periodisch ihren Fortschrittszähler committen (`_commit_progress_checkpoint` bzw. die `processed % *_COMMIT_BATCH_SIZE == 0`-Blöcke).
- [ ] Ein neuer periodischer arq-Cron-Job `reap_stalled_runs` (alle 5 Minuten, `run_at_startup=True`) setzt jede `RUNNING`-Zeile in allen drei Tabellen, deren `last_progress_at` **strikt älter** als `STALL_THRESHOLD = 15 Minuten` ist, auf `FAILED` mit einer erklärenden `error_message` ("Kein Fortschritt seit über 15 Minuten erkannt — vermutlich hängender Verarbeitungsschritt."). Eine Zeile mit `last_progress_at` genau `15:00` alt oder jünger zählt **nicht** als stalled.
- [ ] Ein kontinuierlich fortschreitender Lauf (jeder Checkpoint < 15 Minuten Abstand) wird nie als `FAILED` markiert, unabhängig von der Gesamtlaufzeit — auch nicht nach mehreren Stunden.
- [ ] `scan_project`, `score_project`, `select_top_photos` sind über `arq.worker.func(..., timeout=86400, max_tries=1)` registriert (statt arq-Defaults `timeout=300`, `max_tries=5`). Ein durch `job_timeout` abgebrochener Job erzeugt keine zweite Run-Zeile durch automatischen Hintergrund-Retry.
- [ ] `OpenCloudClient.walk()` terminiert auch bei einem (hypothetischen) Zyklus in der WebDAV-Verzeichnisstruktur (Kind-Ordner verweist auf einen bereits besuchten Pfad) — jeder Pfad wird höchstens einmal geliefert.
- [ ] `reap_stalled_runs` behandelt alle drei Tabellen unabhängig voneinander; ein Fehler bei einer Zeile/Tabelle blockiert die Bereinigung der übrigen nicht.
- [ ] Ein Lauf, der zwischen zwei Cron-Ticks bereits über Schicht 1 (Exception-Pfad) auf `FAILED` gesetzt wurde, wird vom nächsten `reap_stalled_runs`-Tick nicht erneut angefasst (Query filtert auf `status=RUNNING`).

## Datenmodell-Bezug

Additive Spalte `last_progress_at: datetime` (`server_default=func.now()`, analog zu `started_at`) auf `ScanRun`, `ScoringRun`, `TopSelectionRun` (`backend/src/photosort/models.py`). Eine gemeinsame Alembic-Migration für alle drei Tabellen. Kein API-Response-Delta (Feld wird vorerst nicht nach außen exponiert, rein interne Watchdog-Buchhaltung). `docs/architecture.md` wird nicht im Rahmen dieser Spec, sondern im selben PR wie die tatsächliche Umsetzung durch den `architect`-Agenten aktualisiert (Worker-/Cron-Komponente, Datenmodell-Abschnitt der drei Run-Tabellen) — konsistent mit dem Vorgehen bei Spec 0023.

**Nebeneffekt der Migration:** Bereits heute in der Produktivdatenbank aus der Zeit vor diesem Fix hängende `running`-Zeilen (Karteileichen) erhalten beim `ALTER TABLE ADD COLUMN` ein `last_progress_at` mit dem Migrationszeitpunkt als Wert — `reap_stalled_runs` würde sie dadurch ca. 15 Minuten nach dem Deploy automatisch als `FAILED` erkennen und bereinigen, ohne dass das gesondert implementiert werden muss. Reiner Nebeneffekt, kein Akzeptanzkriterium (siehe "Out of Scope").

## Architektur / Umsetzung

**Bezug:** [`decisions/0019-job-lauf-heartbeat-watchdog.md`](../decisions/0019-job-lauf-heartbeat-watchdog.md) (Accepted) — dort das vollständige Zwei-Schichten-Modell, die Root-Cause-Kette und alle Begründungen. Kurzfassung:

- **Schicht 1 (Exception-basiert):** neue kleine Hilfsfunktion `_fail_run(session, run, error_message)` in `backend/src/photosort/worker.py` für die bisher 3× (bald 6×, je Funktion zweifach: `CancelledError`- und `Exception`-Zweig) duplizierte "Lauf auf FAILED setzen"-Logik — kein Decorator/Wrapper über die drei `run_*`-Funktionen (bleiben strukturell eigenständig, ihre Erfolgspfade unterscheiden sich zu stark). In `run_project_scan`, `run_project_scoring`, `run_top_selection` je ein neuer `except asyncio.CancelledError:`-Zweig **vor** dem bestehenden `except Exception:` — ruft `_fail_run(...)`, danach `raise` (kein Verschlucken einer `BaseException`).
- **Schicht 2 (fortschrittsbasiert, der eigentliche Watchdog):** neue Modulkonstante `STALL_THRESHOLD = timedelta(minutes=15)` (analog `SCAN_COMMIT_BATCH_SIZE` etc.). An den bereits bestehenden periodischen Checkpoint-Stellen zusätzlich `run.last_progress_at = _now_utc()` setzen — keine neue Kadenz, Zweitverwendung der bestehenden Infrastruktur aus Spec 0006/0022/0023. Neue Job-Funktion `reap_stalled_runs(ctx)`: sucht je Tabelle `RUNNING`-Zeilen mit `last_progress_at < now - STALL_THRESHOLD`, setzt sie via `_fail_run` auf `FAILED`.
- **Registrierung:** `WorkerSettings.functions` verwendet für die drei bestehenden Jobs `arq.worker.func(fn, timeout=86400, max_tries=1)` statt nackter Funktionsreferenzen — 24h als großzügiger Not-Anker (Schicht 2 greift für jeden echten Stillstand immer zuerst), `max_tries=1` deaktiviert `arq`s automatischen Hintergrund-Retry vollständig (verifiziert: `arq` prüft `job_try > max_tries` **vor** dem erneuten Coroutine-Aufruf, `arq/worker.py:550` — kein neuer DB-Eintrag durch einen Retry-Versuch). `WorkerSettings.cron_jobs` (neu, erste Nutzung von `arq`s Cron-Mechanismus im Projekt): `cron(reap_stalled_runs, minute=set(range(0, 60, 5)), run_at_startup=True)`.
- **`OpenCloudClient.walk()`** (`backend/src/photosort/opencloud/client.py`): `visited: set[str]` ergänzen, `child_relative` vor `queue.append` gegen bereits besuchte Pfade prüfen — niedrigste Priorität der drei Bausteine, kein beobachteter Auslöser, aber ohne diesen Schutz würde ein hypothetischer WebDAV-Zyklus `last_progress_at` laufend "fortschreiten" lassen und dadurch von Schicht 2 nicht erkannt.

**Betroffene Dateien:** `backend/src/photosort/models.py`, `backend/alembic/versions/` (neue Migration), `backend/src/photosort/worker.py`, `backend/src/photosort/opencloud/client.py`, `backend/tests/test_worker_scan_project.py` + Scoring-/Top-Selection-Pendants + neue `test_worker_reap_stalled_runs.py`, `backend/tests/test_opencloud_client.py`, `specs/architecture/0003-securitykonzept.md` (Owner: `security-engineer`, im Review nachzuziehen), `docs/architecture.md` (Owner: `architect`, im selben PR wie die Umsetzung).

**Reihenfolge der Umsetzung (TDD):**

1. Migration + additive Spalte `last_progress_at` (ohne Verhaltensänderung).
2. Schicht 1: fehlschlagender Test je Job-Funktion (Fake-Client wirft `asyncio.CancelledError` mitten im Lauf) → `_fail_run`-Helfer + `except CancelledError`-Zweig + `raise` implementieren → grün, für alle drei Funktionen einzeln.
3. `last_progress_at`-Pflege an den bestehenden Checkpoint-Stellen ergänzen.
4. `WorkerSettings`: `func(..., timeout=86400, max_tries=1)`-Registrierung.
5. Schicht 2: fehlschlagender Test für `reap_stalled_runs` (Run mit alter `last_progress_at` direkt in DB angelegt → Cron-Job setzt `FAILED`) → implementieren → grün; Cron-Registrierung in `WorkerSettings`.
6. `walk()`-Zyklenschutz: fehlschlagender Test mit zyklischer Fake-Verzeichnisstruktur → `visited`-Set implementieren → grün.
7. `specs/architecture/0003-securitykonzept.md` nachziehen (security-engineer).
8. Vollständige Test-/Lint-/Typecheck-Läufe vor PR; `docs/architecture.md` im selben PR aktualisieren.

**Keine neue ADR nötig zusätzlich zu ADR 0019** — bereits vorhanden und Accepted.

## UI/UX

**Nicht relevant, bestehende UI reicht unverändert aus** (ux-ui-designer-Konsultation, 2026-08-09). Der `Alert` mit "Erneut versuchen"-Button (Spec 0017/0023) reagiert bereits heute auf `status="failed"` und zeigt die `error_message` des jeweiligen Laufs an — kein neuer UI-Zustand, keine neue Komponente. Begründung: die neue Fehlermeldung ("Kein Fortschritt seit über 15 Minuten erkannt …") ist selbsterklärend, der bestehende Retry-Button ist für diesen Fehlertyp genauso angemessen wie für Netzwerk-/Verarbeitungsfehler — eine differenzierte Fehler-UI (z.B. "Systemfehler, bitte Logs prüfen") ist für zwei private Nutzer nicht nötig. Mittelbare Verbesserung: ein zuvor unsichtbar hängender Lauf zeigt nach diesem Fix zuverlässig entweder Fortschritt oder die bereits bestehende Fehleranzeige.

## Security

**Nicht relevant — `security-engineer` strukturell nicht konsultiert (Schritt 8):** keine neue Eingabe von außen, kein neuer Auth-/Berechtigungsbezug, keine Änderung an der Sichtbarkeit von Daten zwischen Daniel und seiner Frau. Reine Job-Orchestrierungs-/Terminierungs-Änderung an einer bereits bestehenden Interaktion mit derselben, bereits als vertrauensarm eingestuften WebDAV-Quelle — exakt dieselbe Bewertung wie im direkten thematischen Vorgänger [Spec 0023](./0023-scan-fortschritt-batch-groesse-fix.md#security) ("Kein neues Datenleck, keine neue Eingabe von außen … Verfügbarkeit/Robustheit ist der eigentliche Zweck"). Einzige inhaltliche Berührung: `specs/architecture/0003-securitykonzept.md`, Abschnitt "Job-Lauf-Terminierung", muss im Umsetzungs-PR korrigiert werden — die dortige Aussage, ein geplanter Worker-Shutdown markiere einen Lauf bewusst nicht als `failed`, ist durch ADR 0019 überholt (Shutdown und `job_timeout`-Ablauf lösen denselben `CancelledError`-Pfad aus und werden künftig beide als `FAILED` terminiert); Owner dafür bleibt `security-engineer` im Review des Feature-Branches, keine eigenständige Konsultation an dieser Stelle nötig.

## Teststrategie

Testkonzept-Ergänzung bereits vorgenommen: `specs/architecture/0002-testkonzept.md`, neue Sektion "Job-Lauf-Terminierung / Fortschritts-Watchdog (arq-Cron-Jobs)" — erster `arq`-Cron-Job im Projekt, erstes fortschrittsbasiertes statt zeitbasiertes Terminierungsmuster, als wiederverwendbares Vorbild für künftige langlaufende Jobs mit `RUNNING`-artigem DB-Zustand festgehalten.

Kernpunkte (test-engineer-Konsultation, 2026-08-09):

- **`CancelledError` mitten im Lauf:** neue Fake-Client-Variante analog zum bestehenden `WalkFailsWithUnexpectedErrorClient`, deren `walk()`-Generator nach einigen Elementen `asyncio.CancelledError` statt `OpenCloudError` wirft. `with pytest.raises(asyncio.CancelledError): await run_project_scan(...)`, anschließend `ScanRun` neu aus der DB lesen und `status=FAILED` + gesetzte `error_message` prüfen. Analog für `run_project_scoring`/`run_top_selection` (Exception dort aus der Verarbeitungsschleife, nicht `walk()`).
- **`reap_stalled_runs` ohne echte 15-Minuten-Wartezeit:** `RUNNING`-Zeilen direkt per ORM-Insert mit explizit in der Vergangenheit gesetztem `last_progress_at` anlegen (`now - 20min` für stalled, `now - 5min` für noch aktiv), `reap_stalled_runs(ctx)` als gewöhnliche Coroutine direkt aufrufen — kein echter `arq`-Scheduler/Redis nötig, konsistent mit dem bestehenden Muster, Worker-Jobs in Tests direkt statt über eine echte Job-Queue aufzurufen. Grenzfall-Test exakt auf der 15-Minuten-Schwelle (zählt nicht als stalled).
- **`walk()`-Zyklenschutz:** Unit-Test in `test_opencloud_client.py`, `list_folder` so gemockt, dass ein Kind-Ordner-Eintrag auf einen bereits besuchten Pfad zurückverweist — Assertion, dass `walk()` terminiert und jeder Pfad höchstens einmal geliefert wird.
- **Edge Cases:** Stillstand direkt nach Laufstart (kein Checkpoint erreicht) vs. mitten im Lauf; mehrere gleichzeitig hängende Läufe verschiedener Projekte/Run-Typen (jede Tabelle unabhängig behandelt, ein Fehler bei einer Zeile blockiert andere nicht); Race zwischen einem gerade committenden Checkpoint und `reap_stalled_runs` (durch normale Transaktionsisolation unkritisch, aber als expliziter Test aufgenommen); ein bereits über Schicht 1 auf `FAILED` gesetzter Lauf wird vom nächsten Cron-Tick nicht erneut angefasst (Query filtert auf `status=RUNNING`).
- **Bewusst nicht automatisiert:** ein echter `arq`-`job_timeout`-Ablauf oder ein echtes SIGTERM/Worker-Shutdown (bräuchte einen laufenden Worker-Prozess + Redis, unverhältnismäßiger Aufwand gegenüber der direkten `CancelledError`-Konstruktion, die denselben Codepfad prüft) — bleibt manueller Smoke-Test vor Merge (Worker-Container während eines laufenden Scans neu starten, danach `ScanRun.status` in der DB prüfen).

## Entscheidungen

- **Fortschrittsbasierte statt zeitbasierte Stillstandserkennung (Zwei-Schichten-Modell):** direkt aus der vom Stakeholder bestätigten, bindenden Anforderung abgeleitet ("lange Scans müssen durchlaufen können, kein festes Zeitlimit als primärer Mechanismus") — eine reine `job_timeout`-Erhöhung hätte diese Anforderung strukturell verletzt (architect-Konsultation, siehe ADR 0019).
- **`job_timeout=86400` (24h) nur als Not-Anker, nicht als primärer Mechanismus:** Schicht 2 (15-Minuten-Stillstandserkennung) greift für jeden echten Stillstand immer zuerst; der 24h-Wert begrenzt nur den Ressourcenverbrauch eines (heute nicht vorstellbaren) Defekts in Schicht 2 selbst (ADR 0019).
- **`max_tries=1` (arq-Hintergrund-Retry abgeschaltet):** ein automatischer, unsichtbarer Hintergrund-Retry hätte der etablierten UX widersprochen (Nutzer entscheidet aktiv über "Erneut versuchen") und hätte bei einem echten strukturellen Stillstand bis zu 5 identisch hängende Versuche verschleiert, bevor der Nutzer je einen sichtbaren Fehler gesehen hätte (ADR 0019). Strukturell gilt künftig: ein Nutzer-Trigger → genau ein Lauf → ein eindeutiger Endzustand.
- **`_fail_run`-Hilfsfunktion statt Decorator/Wrapper über die drei `run_*`-Funktionen:** die drei Funktionen bleiben eigenständig, konsistent mit dem bereits etablierten Codebase-Stil (drei eigenständige Run-Modelle ohne gemeinsame Basisklasse); nur die identische "auf FAILED setzen"-Logik wird extrahiert, kein versteckter Kontrollfluss (architect-Konsultation).
- **`walk()`-Zyklenschutz mit aufgenommen statt in eine eigene, spätere Spec ausgelagert:** anders als Spec 0023 (die den gesamten Stillstands-Themenkomplex noch bewusst ausklammerte), da diese Spec den Themenkomplex jetzt ohnehin bearbeitet und der Schutz mit einem `set[str]` sehr günstig zu schließen ist (architect-Konsultation).
- **Watchdog terminiert nur die DB-Zeile, nicht zwingend die zugrunde liegende arq-Task:** `allow_abort_jobs` + gespeicherte `job_id` pro Run-Zeile wäre zusätzliche Komplexität ohne aktuellen Anlass (Einzelnutzer-Homeserver, `max_jobs`-Default 10, keine beobachtete Ressourcenknappheit) — akzeptiertes Restrisiko, siehe ADR 0019 und "Out of Scope" unten.
- **Schwellwert-Parameter (`STALL_THRESHOLD=15min`, Cron-Intervall 5min, `job_timeout`-Anker 24h) als technische Detailentscheidungen ohne separate Rückfrage:** reine Kalibrierung innerhalb der bereits vom Stakeholder vorgegebenen Richtung, keine weitere Produktentscheidung nötig (ADR 0019).
- **`security-engineer` nicht konsultiert (Schritt 8):** keine neue Eingabe von außen, kein Auth-/Berechtigungs-/Datenmodell-Sichtbarkeitsbezug — reine Job-Orchestrierungs-/Terminierungs-Änderung an bereits bestehender Interaktion mit derselben, in Spec 0023 bereits als Robustheits- statt Sicherheitsthema bewerteten WebDAV-Quelle.

## Offene Fragen

Keine.

## Out of Scope

- Aktiver Abbruch der zugrunde liegenden, tatsächlich noch laufenden `arq`-Task durch den Watchdog selbst (`allow_abort_jobs` + gespeicherte `job_id` + `Job.abort()`) — der Watchdog terminiert nur den DB-Zustand; ein dauerhaft technisch hängender Worker-Task (z.B. echter Deadlock) belegt bis zum 24h-`job_timeout`-Ablauf bzw. einem Container-Neustart weiterhin einen Worker-Slot. Akzeptiertes Restrisiko ohne aktuellen Anlass (ADR 0019).
- Automatisierter Test für den in "Datenmodell-Bezug" beschriebenen Migrations-Nebeneffekt (rückwirkende Bereinigung bereits heute hängender Produktions-Zeilen) — reiner, nicht garantierter Nebeneffekt der `server_default`-Semantik, kein Akzeptanzkriterium dieser Spec.
- Differenzierte Fehler-UI je Fehlerursache (Watchdog-Stillstand vs. Netzwerkfehler vs. sonstige Exception) — laut ux-ui-designer-Konsultation nicht nötig, bestehende generische Fehleranzeige reicht.
- Echter `arq`-`job_timeout`-Ablauf oder SIGTERM/Worker-Shutdown als automatisierter Test — bleibt manueller Smoke-Test (siehe Teststrategie).
