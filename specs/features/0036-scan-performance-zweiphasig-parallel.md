# 0036 - Scan-Performance: Enumerationsphase, begrenzte Parallelisierung, echter Prozent-Fortschritt

**Status:** Implemented ([PR #73](https://github.com/TheRealKoller/photosort/pull/73))
**Erstellt:** 2026-08-09
**Bezug:** Inbox-Eintrag `specs/inbox/0014-scan-performance-zweiphasig-parallel.md` (nach Aufnahme in diese Spec gelöscht). ADR [`decisions/0020-scan-enumeration-und-parallele-verarbeitung.md`](../decisions/0020-scan-enumeration-und-parallele-verarbeitung.md) (Accepted). Baut auf Spec [`0022`](./0022-scan-live-fortschrittszaehler.md) (Live-Fortschrittszähler), [`0023`](./0023-scan-fortschritt-batch-groesse-fix.md) (Batch-Größe/Terminierung) und [`0034`](./0034-scan-haenger-fortschritts-watchdog.md)/ADR [`0019`](../decisions/0019-job-lauf-heartbeat-watchdog.md) (Fortschritts-Watchdog, gerade erst gemergt) auf.

## Ziel

Ein Scan eines großen OpenCloud-Ordners fühlt sich heute langsam und intransparent an: Der Fortschrittszähler zeigt nur eine rohe, wachsende Zahl ("N Dateien gefunden") ohne bekannten Gesamtwert, und die eigentliche Verarbeitung (EXIF-Download, Thumbnail-Erzeugung) läuft strikt sequentiell, eine Datei nach der anderen. Diese Spec führt drei zusammenhängende Verbesserungen ein:

1. Eine **Enumerationsphase** vor der eigentlichen Verarbeitung, die zuerst (günstig, ohne Download) alle Dateien auflistet — dadurch ist die Gesamtzahl früh bekannt und ein echter **prozentualer Fortschritt** möglich.
2. **Begrenzte Parallelisierung** von Download + Thumbnail-Erzeugung in der Verarbeitungsphase, statt eine Datei nach der anderen abzuarbeiten — echte Geschwindigkeitssteigerung.
3. **Explizite Absicherung des bereits bestehenden Resume-Verhaltens**: ein Neustart nach Abbruch verarbeitet bereits erledigte, unveränderte Dateien nicht erneut (Etag-Vergleich) — das gilt es durch diese Umstrukturierung nicht zu brechen, insbesondere für den neuen Fall "Abbruch mitten in einer parallelen Verarbeitungs-Charge".

Auslöser (per Rückfrage an Daniel bestätigt): ein konkret erlebtes Problem — ein Scan eines großen Ordners dauerte sehr lange, währenddessen war unklar, wie weit der Scan wirklich ist bzw. wie lange es noch dauert.

## User Story

Als Nutzer mit einer großen Fotobibliothek möchte ich, dass ein Scan von Anfang an einen verlässlichen prozentualen Fortschritt zeigt und durch parallele Verarbeitung spürbar schneller läuft, damit ich beim Warten nicht im Ungewissen bin und nicht unnötig lange auf das Ergebnis warten muss — auch wenn der Scan zwischendurch unterbrochen wird, soll bereits geleistete Arbeit nicht verloren gehen.

## Akzeptanzkriterien

**Zweiphasiger, prozentualer Fortschritt:**
- [ ] Solange die Enumerationsphase läuft, ist `ScanRun.total_files == null`; das Frontend zeigt in dieser Phase einen indeterminierten Fortschrittsbalken mit dem Text "Dateien werden gezählt…" statt der bisherigen reinen Zahl.
- [ ] Nach Abschluss der Enumerationsphase ist `ScanRun.total_files` gesetzt (Gesamtzahl aller gelisteten Einträge, unabhängig vom Dateityp) — inklusive des Sonderfalls `total_files == 0` bei einem leeren Projekt (explizite `is not None`-Prüfung nötig, um das nicht mit "Phase 1 noch offen" zu verwechseln).
- [ ] Ab da zeigt das Frontend einen echten, monoton bis 100% steigenden Prozent-Fortschritt (`files_found / total_files`), Text "X von Y Dateien verarbeitet" — exakt das bereits etablierte `Progress`-Muster von `ScoringRun`/`TopSelectionRun`, keine neue UI-Komponente.
- [ ] Der Fortschritt darf in der Verarbeitungsphase in Sprüngen der konfigurierten Chargengröße wachsen (nicht zwingend datei-granular) — bewusst akzeptierte v1-Einschränkung, siehe ADR 0020.
- [ ] `aria-live`-Ansage des Prozentwerts ist auf 10%-Dezil-Wechsel gedrosselt (bestehende Design-System-Regel), nur in der Verarbeitungsphase aktiv (mit unbekanntem Nenner in der Enumerationsphase nicht sinnvoll).
- [ ] Der Fortschritts-Watchdog (Spec 0034) erkennt eine legitim lange Enumerationsphase (sehr große/verschachtelte Ordnerstruktur) nicht fälschlich als Stillstand — `last_progress_at` wird auch während der Enumeration mit der bestehenden Checkpoint-Kadenz aktualisiert.

**Begrenzte Parallelisierung:**
- [ ] Download (EXIF-Range-Read, Volldownload) und Thumbnail-Erzeugung mehrerer Dateien laufen in der Verarbeitungsphase nachweislich nebenläufig, begrenzt auf eine konfigurierbare Obergrenze (`scan_download_concurrency`, Default 4, env-überschreibbar).
- [ ] Datenbankzugriffe bleiben strikt seriell (strukturell durch die Phasen-Trennung erzwungen, kein Nebenläufigkeits-Crash möglich).
- [ ] Eine tatsächliche Laufzeitverbesserung wird nicht automatisiert getestet (Timing in CI unzuverlässig) — manueller Smoke-Test mit einem realistisch großen Projekt vor dem Merge.

**Resume-/Idempotenz-Absicherung (bestehendes Verhalten, jetzt explizit testpflichtig):**
- [ ] Ein vollständiger Re-Scan eines unveränderten Projekts führt zu 0 erneuten Downloads (reiner Etag-Skip) — trotz erneuter vollständiger Enumerationsphase.
- [ ] Ein Abbruch mitten in einer parallelen Verarbeitungs-Charge hinterlässt keine `flush()`te, aber nie committete `Photo`-Zeile; ein nachfolgender Scan verarbeitet alle Einträge der abgebrochenen Charge korrekt erneut vollständig (nicht nur den fehlgeschlagenen Eintrag) — keine Duplikate, kein fälschliches Überspringen.
- [ ] Bereits in einer früher committeten Charge verarbeitete Einträge werden bei einem späteren Fehler an anderer Stelle desselben oder eines Folgelaufs nicht erneut heruntergeladen.
- [ ] Ein `asyncio.CancelledError` aus einer parallel laufenden I/O-Coroutine erreicht weiterhin unverändert den bestehenden `except asyncio.CancelledError`-Zweig (Fortschritts-Watchdog Schicht 1, Spec 0034/ADR 0019) als rohes `CancelledError`, nicht als `ExceptionGroup`.

## Datenmodell-Bezug

Additive Spalte `ScanRun.total_files: int | None` (`None` = Enumerationsphase noch nicht abgeschlossen, unterscheidet sich von `0` = leeres Projekt), `backend/src/photosort/models.py`. Alembic-Migration erforderlich. `ScanSummary` (`backend/src/photosort/api/projects.py`) bekommt korrespondierend `total_files: int | None`. `files_found` bleibt ein einziges, phasenübergreifend wiederverwendetes Feld (Bedeutungswechsel von "gelistet" auf "in Phase 2 verarbeitet" nach Abschluss der Enumeration, siehe ADR 0020) — kein zweites Zählerfeld.

## Architektur / Umsetzung

Siehe ADR [`decisions/0020-scan-enumeration-und-parallele-verarbeitung.md`](../decisions/0020-scan-enumeration-und-parallele-verarbeitung.md) für die vollständige Begründung. Zusammenfassung:

### Zwei-Phasen-Trennung in `worker.py::run_project_scan`

- **Phase 1 (Enumeration):** neuer privater Helfer materialisiert `client.walk(...)` zu einer In-Memory-Liste (kein DB-Schreibzugriff auf `Photo`), committet dabei mit der bestehenden Checkpoint-Kadenz (`SCAN_COMMIT_BATCH_SIZE`) periodisch `files_found` (Rohzähler "gelistet") + `last_progress_at`. Nach Abschluss: `ScanRun.total_files = len(entries)`, `files_found = 0` (Reset — Bedeutungswechsel).
- **Phase 2a (Klassifikation, reine Funktion):** iteriert die Phase-1-Liste gegen die vorab geladene `existing_photos`-Map, entscheidet Skip (falsche Endung / unveränderter Etag) vs. Arbeitsposten — kein Session-Zugriff, dadurch isoliert unit-testbar. Für Skips wird direkt danach committet (bestehende Kadenz).
- **Phase 2b (begrenzt parallele Verarbeitung):** Arbeitsposten in festen Blöcken (Größe = `scan_download_concurrency`, Default 4). Pro Block: sequentiell `Photo`-Zeilen anlegen/aktualisieren + `flush()` (ID für Thumbnail-Dateiname, **kein Commit**), dann `await asyncio.gather(*, return_exceptions=True)` über die reinen I/O-Coroutinen (EXIF-Range-Read, Download, Thumbnail-Erzeugung — kein Session-Zugriff), dann sequentiell Ergebnisse anwenden + **ein Commit pro Block**.

### Warum `asyncio.gather` über festen Blöcken statt `Semaphore`+`TaskGroup`

Zwei nicht verhandelbare Konstruktionsregeln:

1. `AsyncSession` ist nicht nebenläufigkeitssicher — parallelisiert wird ausschließlich der reine I/O-/CPU-Teil, nie ein DB-Zugriff.
2. `session.commit()` ist session-weit. Ein Commit während ein Objekt bereits `flush()`t, aber noch nicht fertig verarbeitet ist, würde die bestehende Etag-Resume-Idempotenz brechen. Deshalb: `flush()` ohne `commit()` vor Abschluss der I/O je Block, Commit erst nach erfolgreichem Block.

`asyncio.TaskGroup` wurde bewusst **nicht** gewählt: seine `ExceptionGroup`-Semantik bei einer äußeren Cancellation (arqs `job_timeout`, SIGTERM) müsste erst gegen den bestehenden, sicherheitskritischen `except asyncio.CancelledError`-Vertrag aus ADR 0019 verifiziert werden. `asyncio.gather()` propagiert eine äußere Cancellation als rohes `CancelledError` — der bestehende Handler funktioniert unverändert. Akzeptierter Trade-off: bei einem Fehler in einem Block laufen bereits gestartete Geschwister-Requests desselben (kleinen) Blocks noch zu Ende, statt sofort abgebrochen zu werden.

Feste Blockgröße statt separatem `Semaphore` — begrenzt Nebenläufigkeit strukturell und definiert zugleich die Commit-Grenze. Konsequenz: Live-Fortschritt wächst in der Verarbeitungsphase in Sprüngen der Blockgröße statt Datei für Datei (bewusste, einfache v1-Entscheidung).

### Konfiguration

Neues `Settings`-Feld `scan_download_concurrency: int = 4` (`config.py`, env-überschreibbar `SCAN_DOWNLOAD_CONCURRENCY`) — echter Betriebsparameter gegen Überlastung des Einzelnutzer-Homeserver-OpenCloud, nicht nur Test-Kalibrierung.

### Resume/Idempotenz (Scope-Bestätigung)

Kein neuer persistierter Walk-Fortsetzungspunkt (per Rückfrage an Daniel bestätigt, Devil's-Advocate-Fund: die teure Arbeit — Download, Thumbnail-Erzeugung — wird bei unverändertem Etag bereits heute übersprungen; nur das erneute, günstige Auflisten der Ordnerstruktur passiert nach einem Neustart nochmal von vorne). Diese Umstrukturierung darf die bestehende Etag-Skip-Idempotenz nicht brechen — dafür sorgt das `flush()`-ohne-Commit-Muster in Phase 2b.

### Betroffene Dateien

- `backend/src/photosort/worker.py` — `run_project_scan` umstrukturiert, neue private Helfer (Enumeration, Klassifikation, Fetch-und-Thumbnail), neue Konstante.
- `backend/src/photosort/config.py` — `scan_download_concurrency`.
- `backend/src/photosort/models.py` — `ScanRun.total_files`.
- `backend/alembic/versions/` — neue additive Migration.
- `backend/src/photosort/api/projects.py` — `ScanSummary.total_files`.
- `frontend/src/pages/ProjectDetailPage.tsx` — Prozent-Fortschritt für den Scan analog Scoring/Top-Selection, Phase-1-Text "Dateien werden gezählt…".
- `docs/architecture.md` — Vormerk-Eintrag bereits ergänzt (Owner `architect`), nach Umsetzung fertigzustellen.
- Nicht betroffen: `run_project_scoring`/`run_top_selection` (CPU-gebunden, kein Netzwerk-Flaschenhals, ausdrücklich außerhalb des Scopes von ADR 0020).

### Empfohlene Umsetzungsreihenfolge (TDD)

1. `ScanRun.total_files` + Migration + Modell-Test.
2. Enumerations-Helfer (Phase 1) inkl. Checkpoint-/Total-/Reset-Verhalten.
3. Klassifikations-Helfer (Phase 2a, reine Funktion) — isoliert unit-testbar.
4. Fetch-und-Thumbnail-Helfer (Extraktion aus bestehender Inline-Logik, Refactor bestehender EXIF-/Thumbnail-Tests).
5. Block-Orchestrierung (Phase 2b): Konfigurationswert, `gather`-Fehlerverhalten, Commit-nach-Block.
6. Regressionstests für die Crash-Sicherheits-Invariante (Abbruch vor Block-Commit → korrektes Reprozessieren) und `CancelledError`-Propagation durch `gather` (ADR-0019-Kompatibilität).
7. `ScanSummary`/Frontend — Prozent-Fortschritt nach dem `ScoringRun`-Vorbild.

## UI/UX

**1:1-Übertragung des bestehenden `ScoringRun`/`TopSelectionRun`-Fortschrittsmusters auf `ScanRun`**, mit Spezialbehandlung für die zwei Phasen:

- **Enumerationsphase** (`total_files` noch `None`): indeterminierter `<progress>` (kein `value`/`max`) + Label **"Dateien werden gezählt…"** statt der späteren "X von Y"-Form — macht sichtbar, dass eine aktive Vorbereitungsphase läuft und kein Hänger vorliegt (trifft direkt den ursprünglichen Auslöser der Idee: lange Wartezeit ohne erkennbaren Fortschritt).
- **Verarbeitungsphase** (`total_files` bekannt): determinierter `<progress value=files_found max=total_files>` + Text "X von Y Dateien verarbeitet", analog Scoring/Top-Selection.
- **`aria-live`-Ansage:** nur in der Verarbeitungsphase (mit bekanntem Nenner sinnvoll), Text "Y% verarbeitet", auf 10%-Dezil-Wechsel gedrosselt (bestehende Design-System-Regel "Determinierter Fortschritt bei hochfrequenten Zählern").
- **Fehler/Abbruch:** bestehendes Alert-Banner-Muster unverändert, kein neuer Zustand.
- **Design-System:** ausschließlich bestehende Komponenten (`Progress`, `Button.busy`, `aria-live`), keine neuen Bausteine. `specs/architecture/0004-design-system.md` um den Phase-1-Text als Ergänzung zu "Determinierter Fortschritt" zu erweitern.

## Security

**Nicht relevant** — `security-engineer` nicht konsultiert (siehe "Entscheidungen"): kein neuer Auth-/Datenmodell-Sichtbarkeits-/Secrets-/externe-Schnittstellen-Bezug. Reine Performance-/Nebenläufigkeitsänderung an der bereits bestehenden, authentifizierten Interaktion mit derselben WebDAV-Quelle — die neue `scan_download_concurrency`-Einstellung begrenzt die Parallelität sogar explizit (Robustheits-, kein Sicherheitsaspekt), analog zur Bewertung in Spec 0023/0034.

## Teststrategie

`specs/architecture/0002-testkonzept.md` ergänzt: neue Sektion "Intra-Job-Nebenläufigkeit (`asyncio.gather` in festen Blöcken)" — erste Intra-Job-Nebenläufigkeit im Projekt, neues Testmuster nötig (Nebenläufigkeits-Nachweis ohne Wall-Clock-Timing, `CancelledError`-durch-`gather`-Regression, Block-Grenzen, Resume-Rollback-Invariante).

**Testebenen:**
- **Integration (Schwerpunkt, `test_worker_scan_project.py`):** gegen In-Memory-SQLite + erweiterte Fake-OpenCloud-Client-Varianten (neue Fake-Coroutinen für `CancelledError`/Exception/Concurrency-Zähler).
- **Unit (neu):** Phase-2a-Klassifikation als reine Funktion (Liste `DavEntry` + `existing_photos` → Arbeitsposten/Skip); `scan_download_concurrency`/`SCAN_DOWNLOAD_CONCURRENCY` in `test_config.py`.
- **API/Serialisierung:** `ScanSummary.total_files` (`None`/`int`), analog `ScoringRunSummary`.
- **Frontend:** bestehende `Progress`-Komponente wiederverwenden, inkl. Test für `total_files === 0`.
- **Nicht automatisiert:** tatsächliche Geschwindigkeitsverbesserung (manueller Smoke-Test vor Merge).

**Edge Cases (Pflicht):**
- Blockgrenzen: Menge = Blockgröße; Menge = Blockgröße+1 (zwei Blöcke, letzter unvollständig); Menge < Blockgröße.
- `CancelledError` aus einer I/O-Coroutine in `gather` → rohes `CancelledError` erreicht bestehenden `except`-Zweig, `status == FAILED`.
- Einzelner regulärer Fehler in `gather(..., return_exceptions=True)`: Geschwister-Coroutinen laufen zu Ende, Fehler wird danach re-raised, ganzer Scan `FAILED`, vorherige committete Blöcke bleiben unangetastet.
- Leerer Ordner: `total_files = 0` (nicht `None`) nach Phase 1, kein Block, `SUCCESS`.
- Phasenübergang: `ScanRun`-Zustand direkt nach Phase 1 / vor erstem Phase-2-Commit (`total_files` gesetzt, `files_found == 0`).
- Abbruch mitten im Block → Re-Scan reprozessiert korrekt, keine Duplikate, kein fälschliches Skip.
- Erfolgreich committeter Block wird bei Re-Scan nicht erneut heruntergeladen (Call-Counter im Fake-Client).

## Entscheidungen

- **Drei Teilaspekte bewusst in einer gemeinsamen Spec** (per Rückfrage an Daniel bestätigt): Prozent-Fortschritt, Parallelisierung und Resume-Absicherung hängen technisch zusammen (alle drei berühren denselben `run_project_scan`-Loop) und wurden von Daniel als gleich wichtig eingestuft.
- **Devil's-Advocate-Fund, mit Daniel geklärt: kein neuer persistierter Walk-Fortsetzungspunkt.** Die teure Arbeit (Download, Thumbnail-Erzeugung) wird bei unverändertem Etag bereits heute übersprungen — ein Neustart verarbeitet also nicht wirklich "alles neu", wie der ursprüngliche Rohtext der Idee annahm, sondern nur die günstige Ordner-Auflistung erneut. Daniel hat bestätigt, dass das bestehende Verhalten ausreicht und lediglich explizit getestet/dokumentiert werden soll — kein zusätzlicher Persistenzmechanismus.
- **`asyncio.gather` in festen Blöcken statt `asyncio.Semaphore`+`asyncio.TaskGroup`** (architect-Konsultation, siehe ADR 0020): `TaskGroup`s `ExceptionGroup`-Semantik ist mit dem bestehenden `CancelledError`-Vertrag aus ADR 0019 nicht ohne Weiteres kompatibel; `gather` propagiert eine äußere Cancellation unverändert als rohes `CancelledError`.
- **`scan_download_concurrency` als Settings-Feld (Default 4), nicht als Modul-Konstante** (architect-Konsultation): echter Betriebsparameter gegen Überlastung des Einzelnutzer-Homeserver-OpenCloud.
- **Phase-1-UI zeigt expliziten Text "Dateien werden gezählt…"** statt eines undifferenzierten indeterminierten Balkens (ux-ui-designer-Konsultation, als technische Detailentscheidung im Sharpening-Gespräch bestätigt): trifft den ursprünglichen Auslöser der Idee direkt — sichtbar machen, dass eine aktive, erwartbare Phase läuft, kein Hänger.
- **Tatsächliche Laufzeitverbesserung kein automatisiertes Akzeptanzkriterium** (test-engineer-Konsultation): Timing-Messungen sind in CI unzuverlässig; bleibt manueller Smoke-Test vor Merge.
- **`security-engineer` nicht konsultiert (Schritt 8):** kein neuer Auth-/Datenmodell-Sichtbarkeits-/Secrets-/externe-Schnittstellen-Bezug — reine Performance-/Nebenläufigkeitsänderung an bereits bestehender, authentifizierter Interaktion mit derselben WebDAV-Quelle, analog zur Bewertung in Spec 0023/0034.
- **Roadmap-Priorität: Mittel** (`requirements-engineer`-Konsultation, nach Rückfrage bestätigt, 2026-08-09): direkte Alltagsauswirkung (Kernsystem-Performance + UX-Klarheit), aber nicht so akut wie ein aktiver UI-Bug (Spec 0030, Hoch). Kein Konflikt mit bereits Geplantem — orthogonal zu Spec 0033 (Navigation) und 0035 (Klassifizierungs-Recherche), verdrängt nichts.

## Offene Fragen

Keine.

## Out of Scope

- Persistierter Walk-Fortsetzungspunkt (würde auch das erneute Auflisten der Ordnerstruktur nach einem Neustart einsparen) — bewusst nicht Teil dieser Spec, siehe "Entscheidungen". Kann bei tatsächlichem Bedarf (z.B. falls sich die Enumerationsphase selbst als Flaschenhals erweist) später nachgezogen werden.
- Feinere Fortschrittsgranularität innerhalb einer Verarbeitungs-Charge (z.B. per `Semaphore`+`as_completed` statt fester Blöcke) — v1 akzeptiert Sprünge in Chargengröße.
- Parallelisierung von `run_project_scoring`/`run_top_selection` — beide sind CPU-gebunden ohne Netzwerk-Flaschenhals, andere Kostenstruktur, ausdrücklich außerhalb des Scopes von ADR 0020.
- Automatisierte Performance-/Timing-Regressionstests — bleibt manueller Smoke-Test.
- Dynamische Anpassung von `scan_download_concurrency` zur Laufzeit (z.B. adaptiv je nach beobachteter Serverlast) — fester, konfigurierbarer Default reicht für den aktuellen Bedarf.
