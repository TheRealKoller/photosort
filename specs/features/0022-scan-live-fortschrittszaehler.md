# 0022 - Live-Fortschrittszähler beim Scannen eines Projekts

**Status:** Implemented — AK1–AK9 umgesetzt in [PR #40](https://github.com/TheRealKoller/photosort/pull/40)
**Erstellt:** 2026-08-07
**Bezug:** Idee von Daniel selbst (interaktive Session, 2026-08-07), geschärft im Idea-Sharpening-Gespräch. Ursprüngliche Inbox-Notiz `specs/inbox/0007-fortschrittsanzeige-beim-scannen.md` wird nach Anlage dieser Spec gelöscht. Wiederverwendet das in [`decisions/0006-local-scoring-datamodel.md`](../decisions/0006-local-scoring-datamodel.md) etablierte Muster "periodischer Zwischen-Commit für Live-Fortschritt" (dort für `ScoringRun`/Spec 0003, hier zweitmalig angewendet auf `ScanRun`).

## Ziel

Der Scan-Vorgang ("Aktualisieren"-Button auf der Projekt-Detailseite, liest einen OpenCloud-Ordner ein) zeigt während des laufenden Scans aktuell keinerlei Zahlen-Feedback — nur einen Busy-Button mit dem Text "Scan läuft…". Diese Spec ergänzt einen live wachsenden Zähler ("N Dateien verarbeitet"), analog zum bereits bestehenden Live-Fortschritt beim Scoring-Lauf ("Beste Fotos automatisch vorschlagen", Spec 0003/0017) — aber bewusst ohne Prozent-/"X von Y"-Balken, da die Gesamtzahl der Dateien vor vollständigem Durchlauf des OpenCloud-Ordnerbaums technisch nicht bekannt ist.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich beim Scannen eines Projekts sehen, wie viele Dateien bereits verarbeitet wurden, damit ich erkenne, dass der Scan tatsächlich läuft und Fortschritte macht, statt nur auf einen unbestimmten Busy-Button zu starren, bis er irgendwann fertig ist.

## Akzeptanzkriterien

- [x] Während `project.last_scan?.status === 'running'` zeigt die Projekt-Detailseite eine Textzeile, die an `project.last_scan.files_found` gebunden ist. Über mehrere Polls hinweg wächst der angezeigte Wert monoton (nie rückläufig), gespeist durch periodische Backend-Commits statt eines einzigen Commits am Jobende.
- [x] Text-Formatierung (analog Spec 0021): "0 Dateien verarbeitet" bei `files_found === 0`, "1 Datei verarbeitet" bei `=== 1` (Singular), "N Dateien verarbeitet" bei `> 1` (Plural).
- [x] Kein `<progress>`-Element und kein "X von Y"-Text — nur der reine Zähler, zu keinem Zeitpunkt ein fester Nenner.
- [x] Die neue Zählertextzeile trägt selbst kein `aria-live`; einziger Ansage-Träger bleibt die bestehende Statuszeile ("Scan läuft…", bereits `aria-live="polite"`).
- [x] Sobald der Status auf `success` wechselt, verschwindet der laufende Zähler-Block; die bestehende Abschluss-Statistiktabelle (Hinzugefügt/Aktualisiert/Entfernt/Übersprungen inkl. "Dateien gefunden") zeigt weiterhin den finalen `files_found`-Wert unverändert.
- [x] Regression: Ein `OpenCloudError` aus `resolve_drive` (tritt vor Schleifenbeginn auf, z.B. ungültiges Laufwerk) liefert weiterhin `scan_run.status == FAILED`, `files_found` bleibt am Default (0), keine `Photo`-Zeilen in der DB — Verhalten unverändert gegenüber heute.
- [x] Neue, bewusst akzeptierte Verhaltensänderung: Ein Fehler, der während der Schleife auftritt, nachdem mindestens ein periodischer Zwischen-Commit stattgefunden hat, lässt die bis dahin bereits verarbeiteten `Photo`-Zeilen dauerhaft in der DB — kein `session.rollback()` verwirft den bereits committeten Fortschritt, trotz `scan_run.status == FAILED`.
- [x] `SCAN_COMMIT_BATCH_SIZE` ist eine modulweite, per Monkeypatch überschreibbare Konstante in `worker.py` mit Default `25`, analog `SCORE_COMMIT_BATCH_SIZE`.
- [x] Kein API-/Datenmodell-Impact: keine neue Spalte, keine Migration, kein geändertes `ScanSummary`/`ScanRun`-Frontend-Typ — nur geänderte Commit-Frequenz einer bereits existierenden Spalte (`ScanRun.files_found`).

## Datenmodell-Bezug

Keine Änderung. `ScanRun.files_found` (`backend/src/photosort/models.py`) existiert bereits, ebenso dessen vollständige Weiterleitung über `ScanSummary` (`backend/src/photosort/api/projects.py`) bis nach `frontend/src/api/types.ts`. Keine neue Migration.

## Architektur / Umsetzung

**Bezug:** Wiederverwendung des bereits in [`decisions/0006-local-scoring-datamodel.md`](../decisions/0006-local-scoring-datamodel.md) etablierten Musters "periodischer Zwischen-Commit für Live-Fortschritt", hier zweitmalig angewendet auf `ScanRun` statt `ScoringRun`.

### Backend

- `backend/src/photosort/worker.py::run_project_scan`: neue Modul-Konstante `SCAN_COMMIT_BATCH_SIZE` (analog `SCORE_COMMIT_BATCH_SIZE`, Default `25`, monkeypatchbar in Tests), die steuert, alle wie viele durchlaufene Dateien `scan_run.files_found` zwischen-committet wird. Platzierung des Checks **am Ende** jeder Schleifeniteration (nach `_generate_thumbnails`, analog zur Platzierung in `run_project_scoring`) — stellt sicher, dass die für diese Datei bereits vorgenommenen `Photo`-Mutationen vollständig abgeschlossen sind, bevor committet wird.
  - **Technische Korrektur nach Review (test-engineer/architect, 2026-08-07):** anders als `run_project_scoring` hat der Scan-Loop zwei `continue`-Zweige (übersprungene Dateiendung, unveränderter Etag) — ein Checkpoint ausschließlich nach `_generate_thumbnails` wäre für Iterationen, die einen dieser Zweige treffen, nie erreichbar und hätte im dominanten Realweltfall (erneuter Scan eines bereits gescannten Projekts, überwiegend unveränderte Dateien) den Live-Zähler faktisch nicht wachsen lassen. Tatsächliche Umsetzung: eine kleine lokale Closure `_commit_progress_checkpoint()`, aufgerufen an **allen drei** Ausstiegspunkten der Schleife (beide `continue`-Zweige sowie das reguläre Ende nach `_generate_thumbnails`) — erfüllt damit weiterhin die Kernanforderung "am Ende jeder Schleifeniteration, nachdem etwaige Mutationen für diese Datei abgeschlossen sind", nur für alle drei Ausstiegspfade statt nur für den einen ursprünglich benannten. Reine technische Detailkorrektur innerhalb der bereits akzeptierten Architektur, keine neue ADR nötig.
- **Entwurfsentscheidung/Konsequenz (bewusst, analog ADR 0006, mit Daniel bestätigt):** Da `session.commit()` die gesamte offene Transaktion committet, nicht nur das `files_found`-Feld, persistieren mit dieser Änderung ab sofort auch bereits verarbeitete `Photo`-Zeilen (neu/aktualisiert) unwiderruflich, auch wenn der Scan danach mit `OpenCloudError` fehlschlägt — anders als bisher, wo ein Fehlschlag den gesamten Lauf durch `session.rollback()` folgenlos macht. Bereits eingelesene Foto-Metadaten für tatsächlich verarbeitete Dateien sind korrekte Daten, kein Datenrisiko; ein erneuter Scan setzt dort fort. `photos_added`/`photos_updated`/`photos_removed`/`files_skipped` sowie die Entfernungs-Erkennung (`removed_paths`) bleiben unverändert nur am Ende gesetzt — dafür gibt es kein Akzeptanzkriterium für Live-Fortschritt, nur `files_found` soll live wachsen.
- Docstring-Korrektur: Kommentar an `ScoringRun` in `models.py` ("anders als `ScanRun`, das nur einmal am Ende committet") entfällt/wird angepasst, da nicht mehr zutreffend.
- `docs/architecture.md`: Beschreibung von `ScanRun`/`ScoringRun` entsprechend nachziehen (Klammerzusatz zu `ScoringRun`, der auf das bisherige Nur-Scoring-Verhalten verweist, streichen/umformulieren).
- Keine Änderung an `api/projects.py` — `ScanSummary` liefert `files_found` bereits in jedem Zustand inkl. `running`.

### Frontend

- `frontend/src/pages/ProjectDetailPage.tsx`: neue Textzeile innerhalb `project.last_scan?.status === 'running'` (aktuell nur die Statuszeile "Scan läuft…"), gebunden an `project.last_scan.files_found`, ohne `<Progress>`-Element und ohne zusätzliches `aria-live`.
- `useTriggerConfirmation`-Hook (Bridging-Effekt aus Spec 0017): keine Änderung nötig — kennt nur `status`/`startedAt`, entkoppelt von der Existenz eines Live-Zählers, deckt den Scan-Trigger bereits ab.
- Keine Änderung an `frontend/src/api/types.ts` oder `hooks/useProjects.ts` — `files_found` und das bestehende Poll-Intervall werden unverändert wiederverwendet.

### Reihenfolge der Umsetzung (TDD)

1. Backend zuerst, fehlschlagender Test in `backend/tests/test_worker_scan_project.py`: `SCAN_COMMIT_BATCH_SIZE` per Monkeypatch auf `1`, `FakeOpenCloudClient.walk()` liefert einige Einträge und wirft danach `OpenCloudError` (simuliert WebDAV-Abbruch mitten im Durchlauf). Assertion: `scan_run.status == FAILED` **und** bereits verarbeitete `Photo`-Zeilen sind in der DB vorhanden (nicht `[]`) — belegt periodischen Commit und die akzeptierte Verhaltensänderung in einem Test.
2. `SCAN_COMMIT_BATCH_SIZE`-Konstante + Zwischen-Commit-Logik implementieren — Test grün.
3. Bestehenden Test `test_scan_run_marked_failed_on_opencloud_error` (sofortiger Fehler vor der Schleife, weiterhin `photos == []`) unverändert als Regressionsschutz laufen lassen; Kommentar ergänzen, der die zwei scheinbar widersprüchlichen Assertions (`photos == []` vs. Fotos vorhanden) für den Review verständlich macht.
4. Docstring-Korrektur in `models.py` (`ScoringRun`).
5. Frontend: fehlschlagender Test in `ProjectDetailPage.test.tsx` (neuer Zähler-Text während `status='running'`, kein `<progress>`-Element, kein zusätzliches `aria-live`, monotones Update über zwei Polls, Verschwinden bei Übergang zu `success`), dann Implementierung, dann grün.
6. Vollständige Test-/Lint-/Typecheck-Läufe (`pytest`, `ruff`, `mypy --strict`, `vitest`, `oxlint`, `tsc`) vor PR.
7. `docs/architecture.md`-Korrektur im selben PR.

**Keine ADR nötig:** additive Zweitanwendung eines bereits in ADR 0006 akzeptierten, dokumentierten Musters (periodischer Zwischen-Commit für Live-Fortschritt bei einem lang laufenden Worker-Job) auf einen zweiten, strukturell analogen Job — keine neue Technologie, keine neue Datenmodell-Grundstruktur, keine externe Abhängigkeit. Konsistent mit dem Präzedenzfall von Spec 0017/0021.

## UI/UX

Sichtbare Oberfläche: ja (`ProjectDetailPage.tsx`, Scan-Statusbereich). Ergänzt eine zusätzliche Textzeile unterhalb der bestehenden Statuszeile, sichtbar nur bei `project.last_scan?.status === 'running'`, gebunden an `project.last_scan.files_found`: "N Dateien verarbeitet" (Singular "1 Datei verarbeitet" bei genau einem Treffer, sonst Plural, kein Sondertext bei 0 — analog zur Singular/Plural-Regel aus Spec 0021).

Explizit **kein** `<progress>`-Element: das im Design-System dokumentierte Muster "Determinierter Fortschritt bei hochfrequenten Zählern" setzt eine bekannte Gesamtzahl voraus, die hier wegen des lazy durchlaufenen Ordnerbaums nicht existiert — ein Balken ohne Nenner wäre irreführend. Kein eigenes `aria-live` auf der neuen Zeile: der Zähler kann sich potenziell bei jeder verarbeiteten Datei ändern, eine Live-Ansage bei jedem Wertwechsel würde die im Design-System begründete Drosselregel für hochfrequente Zähler verletzen. Die bestehende, unveränderte `aria-live="polite"`-Statuszeile ("Scan läuft…") bleibt alleiniger Ansage-Träger.

Kein zusätzliches Bewegungselement (Puls-/Spinner-Icon) neben dem Zählertext nötig, auch wenn der Zähler zwischen zwei Polls mal nicht wächst (z.B. großer Ordner ohne Bilddateien): der "läuft noch"-Zustand ist bereits doppelt sichtbar — der Trigger-Button zeigt während des Laufs einen rotierenden Spinner (busy-button-Muster), und der `StatusDot` neben der Statuszeile pulsiert bei `status === 'running'`. Ein drittes Bewegungselement wäre redundant.

Kein neues Muster im Design-System nötig — reine Anwendung des bestehenden "Aktions-Button während laufender Anfrage"-Musters plus einer einfachen Textzeile.

## Security

Nicht sicherheitsrelevant. Das Feature führt keinen neuen Endpunkt, kein neues Datenfeld und keine Berechtigungsänderung ein — `files_found` (`ScanRun`/`ScanSummary`) wird bereits heute über das bestehende, authentifizierte `GET /projects/{id}` (`last_scan`) für beide Nutzer ausgeliefert und lediglich künftig häufiger zwischengespeichert (periodisches Commit in `worker.py::run_project_scan`, analog zum bestehenden `SCORE_COMMIT_BATCH_SIZE`-Muster) statt nur am Ende.

Die bewusst akzeptierte Verhaltensänderung, dass bei einem mittendrin fehlschlagenden Scan (`OpenCloudError`) bereits verarbeitete `Photo`-Zeilen aus zuvor committeten Batches jetzt dauerhaft in der DB bleiben statt komplett per Rollback verworfen zu werden, wurde geprüft: kein neues Datenleck (dieselbe Datenkategorie ist bereits heute nach jedem erfolgreichen Scan über denselben Endpunkt für beide gegenseitig vertrauenswürdigen Nutzer sichtbar, siehe Bedrohungsmodell in `specs/architecture/0003-securitykonzept.md`) und keine neue Autorisierungs- oder Eingabevalidierungsfrage, sondern ein reines Daten-Konsistenz-/Produktthema — analog zum bereits akzeptierten Verhalten bei `ScoringRun`/`PhotoScore` (ADR 0006).

`specs/architecture/0003-securitykonzept.md` wird durch diese Spec nicht ergänzt.

## Teststrategie

**Backend — `backend/tests/test_worker_scan_project.py` (Integrationsebene, echte In-Memory-SQLite):**

- Starker Periodizitäts-Nachweis: `SCAN_COMMIT_BATCH_SIZE` per Monkeypatch auf `1`, `FakeOpenCloudClient.walk()` als Async-Generator, der z.B. 3 Einträge liefert und danach `OpenCloudError` wirft (simuliert einen WebDAV-Abbruch mitten im Ordnerbaum-Durchlauf). Assertion: `scan_run.status == FAILED` **und** `len(photos) == 3` (nicht `0`) — belegt zugleich den periodischen Commit und die akzeptierte Verhaltensänderung.
- Regressionstest unverändert: `test_scan_run_marked_failed_on_opencloud_error` (sofortiger Fehler vor der Schleife) bleibt unangetastet, Kommentar ergänzt, der auf den neuen Test verweist, damit die zwei scheinbar widersprüchlichen Assertions im Review nicht als Inkonsistenz missverstanden werden.
- Kein separater "Erfolgspfad mit kleiner Batch-Größe"-Test nötig — bestehende Erfolgspfad-Tests prüfen bereits, dass `scan_run.files_found` am Ende korrekt ist.

**Frontend — `frontend/src/pages/ProjectDetailPage.test.tsx` (Integrationsebene, echter Router+QueryClient, gemockte `api/projects.ts`):**

- Singular/Plural: separate Fälle für `files_found = 0`, `1`, `>1`.
- Monotones Update über zwei aufeinanderfolgende Poll-Antworten (z.B. `3` → `7`), Text aktualisiert sich entsprechend.
- Negativ-Assertion: kein `progressbar`-Element und kein "von"-Text im laufenden Block.
- Negativ-Assertion: im laufenden Block gibt es weiterhin genau ein Element mit `aria-live` (die bestehende Statuszeile) — der neue Zählertext liegt nicht innerhalb eines eigenen `aria-live`-Elements und ist auch keines selbst.
- Übergang running → success: neuer Zähler-Block verschwindet aus dem Dokument, "Dateien gefunden" in der Abschluss-Statistik zeigt weiterhin den finalen Wert.

**Kein Update von `specs/architecture/0002-testkonzept.md` nötig** — reine Zweitanwendung zweier bereits dokumentierter Muster: der periodische Zwischen-Commit-Mechanismus (Testkonzept, Abschnitt "Scoring/Vorschläge") und die Singular/Plural-Textkonvention (Spec 0021).

## Entscheidungen

- **Checkpoint-Platzierung im Review korrigiert (rein technisch, keine Rückfrage nötig):** die ursprünglich beschriebene Platzierung "nach `_generate_thumbnails`" hätte im Scan-Loop (zwei `continue`-Zweige, anders als bei `run_project_scoring`) im dominanten Realweltfall (Re-Scan mit überwiegend unveränderten Dateien) den Checkpoint faktisch nie erreicht. Korrigiert auf einen Aufruf an allen drei Ausstiegspunkten der Schleife (test-engineer-/architect-Review, 2026-08-07) — siehe Architektur-Abschnitt oben.
- **Kein Prozent-/"X von Y"-Balken, nur reiner Zähler:** der OpenCloud-Ordnerbaum wird lazy per BFS über WebDAV durchlaufen (`OpenCloudClient.walk()`), die Gesamtzahl der Dateien ist vor vollständigem Durchlauf nicht bekannt. Ein Vorab-Zähl-Durchlauf (doppelter WebDAV-Traversierungs-Aufwand) oder ein live wachsendes, potenziell "zurückspringendes" Y wurden von Daniel explizit verworfen — direkt mit Daniel geklärt, 2026-08-07.
- **Kein neues Datenmodell/keine Migration:** `ScanRun.files_found` existiert bereits vollständig verdrahtet bis zum Frontend-Typ — reine Änderung der Commit-Frequenz im Worker (architect-Konsultation, 2026-08-07).
- **Bereits verarbeitete Fotos bleiben bei einem späteren Fehlschlag erhalten** (kein Alles-oder-nichts-Rollback mehr): explizit mit Daniel bestätigt, nachdem der `architect` diese Konsequenz des periodischen Zwischen-Commits benannt hatte — analog zum bereits akzeptierten `ScoringRun`/`PhotoScore`-Verhalten (ADR 0006), 2026-08-07.
- **Kein zusätzliches Bewegungselement (Puls-/Spinner-Icon)** neben dem Zählertext: bereits doppelt abgedeckt durch den Button-Spinner (busy-button-Muster) und den pulsierenden `StatusDot` (ux-ui-designer-Konsultation, 2026-08-07).
- **Kein eigenes `aria-live` auf der Zählerzeile:** hochfrequente Wertwechsel würden die im Design-System begründete Drosselregel verletzen; die bestehende stabile Statuszeile bleibt alleiniger Ansage-Träger (ux-ui-designer-/test-engineer-Konsultation, 2026-08-07).
- **Keine ADR:** additive Zweitanwendung eines bereits akzeptierten Musters, keine neue Technologie/Grundstruktur (architect-Konsultation, 2026-08-07).
- **Nicht sicherheitsrelevant:** eigenständig geprüft (nicht nur von der Architektur-Einschätzung übernommen) — keine neue Eingabe, kein neuer Endpunkt, keine Berechtigungsänderung, die Verhaltensänderung bei Fehlschlag ist ein reines Datenkonsistenz-Thema (security-engineer-Konsultation, 2026-08-07).

## Offene Fragen

Keine.

## Out of Scope

- Ein exakter Prozent-/"X von Y"-Fortschrittsbalken für den Scan (bewusst verworfen, siehe "Entscheidungen").
- Layout-/Klarheits-Überarbeitung der finalen Statistik-Tabelle sowie Begründungen für übersprungene/entfernte Dateien (eigene, spätere Spec, siehe Inbox-Eintrag 0008).
- Dateianzahl-Anzeige beim Ordner-Auswählen vor dem eigentlichen Scan (eigene, spätere Spec, siehe Inbox-Eintrag 0006).
