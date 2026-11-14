# ADR 0147: Kooperativer Abbruch und Wartezustand der Läufe

**Status:** Accepted
**Datum:** 2026-11-14
**Bezug:** Spec 0641 / Issue #641, ADR 0019

## Kontext

Laufende Vorgänge (Scan, Ausschuss-Bewertung, Klassifizierung, Export nach OpenCloud, Klassifizierungsprüfung) lassen sich bisher nicht anhalten. Ein Lauf existiert in der DB erst, wenn der arq-Worker den Job übernimmt; ein eingereihter, wartender Vorgang ist für Nutzer und API unsichtbar und damit auch nicht abbrechbar.

ADR 0019 sichert hängende Läufe in zwei Schichten ab: `except asyncio.CancelledError` setzt `FAILED` (Timeout, Shutdown), der Cron-Reaper finalisiert stillstehende Läufe als `FAILED`. Eine Job-ID wird nicht gespeichert, `allow_abort_jobs` ist nicht gesetzt.

Issue #641 verlangt einen weichen Abbruch: Das angefangene Element wird fertig verarbeitet, bisherige Ergebnisse bleiben, Folgephasen entfallen, der Endzustand heißt „abgebrochen“ und ist weder Erfolg noch Fehler. Ein wartender Vorgang soll ebenfalls abbrechbar sein.

## Entscheidung

### 1. Merker `cancel_requested_at` und kooperative Prüfung

Die Lauftabellen `scan_runs`, `scoring_runs`, `criterion_scoring_runs`, `remote_category_classification_runs`, `export_runs` und die Prüfungstabelle bekommen die nullable Spalte `cancel_requested_at`. Die API setzt sie; der Worker liest sie an seinen bestehenden Prüfpunkten (vor jedem Element bzw. Commit-Batch, zwischen Phasen) frisch aus der DB und beendet den Lauf dort.

### 2. Wartezustand `QUEUED`, Übernahme per bedingtem UPDATE

`ScanStatus` und `ExportRunStatus` erhalten `QUEUED` und `CANCELLED`. Die Auslöser-Endpunkte legen die Laufzeile vor `enqueue_job` mit `QUEUED` an und übergeben `run_id`. Der Worker übernimmt mit `UPDATE … SET status='RUNNING' WHERE id=? AND status='QUEUED' AND cancel_requested_at IS NULL`; bei null Zeilen endet der Job ohne Arbeit. Einen wartenden Lauf setzt die API beim Abbruch direkt auf `CANCELLED`.

### 3. `CANCELLED` hat Vorrang vor `FAILED`

Sobald `cancel_requested_at` gesetzt ist, endet der Lauf immer `CANCELLED` — auch wenn danach eine Ausnahme fliegt, Schicht 1 (`CancelledError`) greift oder der Reaper (Schicht 2) den Lauf als stillstehend findet. Die Fehlerpfade lesen den Merker vor dem Finalisieren frisch. `error_message` bleibt beim Nutzer-Abbruch leer; der bestehende Text „Lauf abgebrochen (Job-Timeout oder Worker-Shutdown)“ bleibt Timeout und Shutdown vorbehalten.

### 4. Unterbrechbare Wartezeiten über ein Kontext-Token

Drosselungs- und Retry-Wartezeiten in `cloud_vision` können Minuten dauern. Ein `CancelToken` (Event plus Beobachter, der den Merker alle 2 s in eigener Session liest) liegt in einer `ContextVar`; `CloudRequestThrottle.acquire()` und die Retry-Wartezeit lassen den Schlaf gegen das Event laufen und werfen `RunCancelled`. Eine bereits gesendete Anfrage läuft zu Ende. `CancelledError` wird weder gefangen noch abgeschirmt.

### 5. Prüfpunkte und Teilergebnisse

Was bis zum Prüfpunkt committet ist, bleibt; Abschlussphasen (Aufräumen nach Scan, Clustering/Auto-Entscheidung/Gate, Ranking/Auswahlvorschlag, Fallbildung im Prüflauf) entfallen. Nutzerentscheidungen werden nie angefasst. Folgeschritte prüfen weiter auf `SUCCESS`, ein abgebrochener Lauf schaltet also nichts frei.

### 6. Abbruch über einen projektgebundenen Operations-Router

`GET /projects/{id}/operations` listet wartende und laufende Vorgänge, `POST …/{kind}/{run_id}/cancel` und `POST …/cancel-all` brechen ab. Die Endpunkte sind idempotent (200 mit unverändertem Zustand statt 4xx) und binden jede Anweisung an `project_id` (fremder Lauf → 404).

### 7. Nicht entschieden

arq `Job.abort()` wird nicht eingeführt. Eine Option „Teilergebnisse verwerfen“ gibt es nicht.

## Begründung

- Ein echter `asyncio`-Cancel (direkt oder über `Job.abort()`) unterbricht mitten im Element, verletzt den weichen Abbruch und kollidiert mit Schicht 1 von ADR 0019, die `CancelledError` als Fehler wertet. Er bräuchte zudem eine gespeicherte Job-ID.
- Der Merker nutzt die vorhandenen Commit-Punkte und kostet je Prüfung eine Primärschlüssel-Lesung.
- Der Wartezustand in der DB macht eingereihte Vorgänge sichtbar und abbrechbar, ohne die arq-Queue zu manipulieren; die bedingte Übernahme macht das Rennen zwischen Abbruch und Jobstart atomar.
- Die `ContextVar` vermeidet, ein Token durch alle Aufrufstellen von `post_vision_request` und die prozessweiten Schrittmacher zu reichen.

## Konsequenzen

- Neue Enum-Werte brauchen kein DDL (`native_enum=False`, Namen gespeichert); die Migration fügt nur sechs Spalten hinzu, ohne Backfill.
- Jeder Status-Konsument (Wächter, Polling, Stand-Zeile, Aktionsleiste) muss `queued` wie „läuft“ und `cancelled` als „nicht erledigt, kein Fehler“ behandeln.
- Der Reaper bekommt einen Block für hängende `QUEUED`-Läufe mit eigenem Schwellwert (24 h = Job-Timeout), weil Warten hinter vollen Worker-Plätzen legitim ist.
- Die Reaktionszeit eines Abbruchs ist die Dauer des angefangenen Elements bzw. Blocks plus höchstens 2 s in Wartezeiten.
- Job-Funktionen akzeptieren `run_id=None` für vor dem Deployment eingereihte Jobs.
