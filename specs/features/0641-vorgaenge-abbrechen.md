# 0641 - Laufende und wartende Vorgänge einzeln oder gesammelt abbrechen

**Status:** Accepted
**Erstellt:** 2026-11-14
**Bezug:** Issue [#641](https://github.com/TheRealKoller/photosort/issues/641)

## Ziel

Lange Hintergrundvorgänge eines Projekts — Fotos einlesen, Ausschuss vorschlagen, klassifizieren, exportieren und ein Klassifizierungsverfahren prüfen — lassen sich heute nur durch einen Neustart des Dienstes beenden. Wer einen Lauf falsch startet oder merkt, dass er Stunden dauert, muss ihn aussitzen; bei Cloud-Klassifizierung und Prüflauf laufen dabei weiter Kosten auf.

Nach dieser Story lässt sich jeder dieser Vorgänge einzeln oder gemeinsam für das geöffnete Projekt anhalten. Der Vorgang beendet das gerade bearbeitete Element noch, beginnt aber nichts Neues mehr. Alles bis dahin Erreichte bleibt erhalten und nutzbar. Ein abgebrochener Vorgang ist von einem erfolgreichen und einem fehlgeschlagenen unterscheidbar und wird nicht als Fehler dargestellt.

## User Story

Als Nutzer eines Projekts, der das Einlesen, die Ausschuss-Erkennung, die Klassifizierung, den Export oder einen Prüflauf gestartet hat, möchte ich einen laufenden oder wartenden Vorgang einzeln oder alle Vorgänge dieses Projekts zusammen anhalten können, wobei das gerade bearbeitete Element noch zu Ende geführt wird und alles bis dahin Erreichte erhalten bleibt, damit ich einen falsch gestarteten oder unerwartet langen Lauf nicht aussitzen muss und weder Rechenzeit noch Cloud-Kosten weiterlaufen.

## Akzeptanzkriterien

- [ ] **Sichtbar und erreichbar.** Solange einer der fünf Vorgänge (Scan, Ausschuss, Klassifizierung, Export, Prüflauf) läuft oder wartet, trägt seine Bedienstelle den Zustand und genau eine Aktion „Abbrechen“. Läuft oder wartet nichts, gibt es diese Aktion nicht. Der Einzelabbruch erfolgt ohne Rückfrage.
- [ ] **Einzeln.** Ein Abbruch trifft genau den gewählten Vorgang. Andere laufende Vorgänge desselben Projekts laufen unverändert weiter; ihr Fortschritt steigt nach dem Abbruch weiter.
- [ ] **Sanft.** Nach dem Abbruch beginnt der Vorgang kein neues Element: kein weiteres Foto, keinen weiteren Block, keine weitere Cloud-Anfrage. Ein zum Abbruchzeitpunkt begonnenes Element wird abgeschlossen. Wartezeiten, etwa auf eine Anbieter-Drosselung, werden abgebrochen statt ausgesessen. Der Endzustand ist spätestens mit Abschluss des begonnenen Elements erreicht; danach steigt kein Fortschrittszähler des Vorgangs mehr.
- [ ] **Eigener Endzustand, Schritt nicht abgeschlossen.** Ein abgebrochener Vorgang endet als „abgebrochen“ und ist an seiner Bedienstelle von „erfolgreich“ und „fehlgeschlagen“ unterscheidbar. Er wird nicht als Fehler dargestellt und erzeugt keine Fehlermeldung. Der Auslöser ist danach wieder bedienbar. Bei den Pipeline-Schritten gilt er weiterhin als nicht erledigt: die Stand-Zeile nennt ihn nicht „fehlgeschlagen“, der nächste Schritt bleibt gesperrt, und ein abgebrochener Ausschusslauf bestätigt den Ausschuss nicht.
- [ ] **Teilergebnisse bleiben erhalten.** Alles bis zum Abbruch fertig Verarbeitete bleibt erhalten und nutzbar: eingelesene Fotos samt Vorschaubildern, erkannte Ausschuss-Vorschläge, berechnete Bewertungen, bereits exportierte Fotos und bereits klassifizierte Prüffälle. Der Abbruch selbst nimmt nichts davon zurück; ein späterer Lauf überschreibt bzw. ergänzt nur, was er ohnehin täte.
- [ ] **Kein Verwerfen angeboten.** Ein Abbruch bietet keine Wahl zwischen Behalten und Verwerfen und keine Aktion, die von diesem Lauf erzeugte Daten löscht. Es gibt keinen Weg, über den Abbrechen oder ein späterer Schritt die Teilergebnisse eines abgebrochenen Laufs entfernt.
- [ ] **Abgebrochener Export bleibt sichtbar.** Ein abgebrochener Export hinterlässt den bereits angelegten Ordner samt kopierter Fotos auf OpenCloud; PhotoSort löscht ihn nicht. Zielpfad und Anzahl der bereits kopierten Fotos bleiben sichtbar, damit der Ordner bei Bedarf von Hand entfernt werden kann.
- [ ] **Abgebrochener Prüflauf.** Ein abgebrochener Prüflauf erlaubt keine Urteile; Urteile bleiben der erfolgreich abgeschlossenen Prüfung vorbehalten. Die bis dahin berechneten Ergebnisse bleiben einsehbar. Da der Prüflauf nicht mehr läuft, lässt sich unmittelbar eine neue Prüfung anlegen.
- [ ] **Alle abbrechen (projektweit).** Eine Aktion „Alle abbrechen“ hält alle gerade laufenden oder wartenden Vorgänge des geöffneten Projekts an, einschließlich des Prüflaufs. Vor der Ausführung nennt sie Anzahl und Bezeichnung der betroffenen Vorgänge; ohne betroffenen Vorgang ist sie nicht bedienbar. Nach Bestätigung gilt je Vorgang das oben Gesagte; kein Vorgang endet dadurch als „fehlgeschlagen“. Vorgänge anderer Projekte bleiben unberührt und laufen weiter.
- [ ] **Wartende Vorgänge.** Ein gestarteter, aber noch nicht begonnener Vorgang ist als wartend sichtbar und lässt sich abbrechen; er beginnt danach nicht mehr und hinterlässt keinen laufenden Zustand.
- [ ] **Robust gegen Wiederholung und Rennen.** Ein zweiter Abbruch ändert nichts und meldet keinen Fehler. Trifft ein Abbruch einen bereits beendeten Vorgang, bleibt dessen Endzustand unverändert, und die Rückmeldung ist keine Fehlermeldung.
- [ ] **Kein Rückfall in „Stillstand“.** Ein abgebrochener Vorgang wird auch dann nicht nachträglich als „fehlgeschlagen“ oder „hängt“ gekennzeichnet, wenn der Abbruch in einer Phase ohne Fortschrittsmeldung ausgelöst wurde. Sein Endzustand bleibt „abgebrochen“.
- [ ] **Anzeige danach.** Nach dem Abbruch bleibt der Fortschritt auf dem zuletzt erreichten Stand stehen (kein Rücksetzen auf 0), und es wird keine Restdauer mehr angezeigt.
- [ ] **Keine fremden Daten.** Der Abbruch berührt nie Daten, die nicht von diesem Lauf erzeugt wurden: Einzelentscheidungen im Ausschuss, manuelle Bewertungen, Album-Entwürfe, die Endauswahl und bereits gesetzte Prüfurteile bleiben in jedem Fall erhalten.
- [ ] **Beide Nutzer.** Beide Nutzer sehen den Zustand jedes Vorgangs und können ihn abbrechen. Ein Abbruch durch die eine Person erscheint bei der anderen als „abgebrochen“, nicht als Fehler.
- [ ] **Bedienbarkeit.** Die Abbrechen-Aktion ist per Tastatur erreichbar, mit mindestens 44 × 44 px treffbar, und ihr Zustand hängt nicht allein an der Farbe.

**Umfang:** über dem Richtwert von ~200 Zeilen, weil fünf Vorgangsarten mit je eigenem Prüfpunkt, ein neuer Endzustand und 16 Akzeptanzkriterien in einer Spec stehen.

## Datenmodell-Bezug

- `ScanStatus` (geteilt von `ScanRun`, `ScoringRun`, `CriterionScoringRun`, `RemoteCategoryClassificationRun`, `ClassificationReview`) und `ExportRunStatus` erhalten `QUEUED` und `CANCELLED` (kein DDL: `native_enum=False`, Name gespeichert).
- Neue nullable Spalte `cancel_requested_at` in `scan_runs`, `scoring_runs`, `criterion_scoring_runs`, `remote_category_classification_runs`, `export_runs` und der Prüfungstabelle; Migration ohne Backfill (`NULL` = kein Abbruch angefordert).
- Eine Laufzeile entsteht künftig beim Auslösen (`QUEUED`), nicht erst bei Jobstart.
- [`docs/architecture.md`](../../docs/architecture.md) wird im selben PR nachgezogen (Worker-Komponente, Datenmodell).

## Architektur / Umsetzung

Grundsatzentscheidung: ADR [`0147`](../decisions/0147-kooperativer-abbruch-und-wartezustand-der-laeufe.md) — kooperativer Abbruch über eine Merker-Spalte, eigener Wartezustand `queued`, Endzustand `cancelled` mit Vorrang vor `failed`.

### 1. Datenmodell (`backend/src/photosort/models.py`)

- `ScanStatus` (geteilt von `ScanRun`, `ScoringRun`, `CriterionScoringRun`, `RemoteCategoryClassificationRun`, `ClassificationReview`) und `ExportRunStatus` bekommen je `QUEUED = "queued"` und `CANCELLED = "cancelled"`. Die Spalten sind `native_enum=False, length=20` ohne CHECK-Constraint und speichern den Enum-**Namen**: neue Werte brauchen kein DDL.
- Sechs Tabellen bekommen `cancel_requested_at: Mapped[datetime | None]` (nullable, ohne Default): `scan_runs`, `scoring_runs`, `criterion_scoring_runs` (Klassifizierungslauf), `remote_category_classification_runs` (dessen Cloud-Phase), `export_runs`, `ClassificationReview`.
- `ClassificationPhase`, `CloudVisionPhase` und `ReviewPhase` bleiben unverändert. Ein abgebrochener Lauf behält seine letzte `phase` (Anzeige „Abgebrochen bei …“).
- Migration: Revisions-ID über `python3 scripts/nummern.py migration vorgaenge_abbrechen`. Sie fügt nur die sechs Spalten hinzu. Es gibt keinen Backfill, weil `NULL` für alle Bestandsläufe „kein Abbruch angefordert“ heißt.

### 2. Wartezustand und Übernahme

- Die Auslöser `api/projects.py::trigger_scan`, `trigger_score` und `trigger_classify` sowie `api/export.py::trigger_export` legen die Laufzeile **vor** `enqueue_job` mit `status=QUEUED` an, committen und reichen `run_id=` als Keyword an den Job.
  - Klassifizierung: Die API legt die `CriterionScoringRun`-Zeile nach der Logik von `worker.py::_start_criterion_scoring_run` an. Der `RemoteCategoryClassificationRun` entsteht weiter erst im Worker.
  - Scoring: Das projektweite Zurücksetzen von `auto_decided` passiert erst beim Übernehmen im Worker, nicht beim Anlegen.
  - Export: Ist `final_selection.included_photos` leer, legt die API keinen Lauf an und antwortet wie bisher `202 {"status":"queued"}`.
  - `api/classification_reviews.py::create_review` legt die Prüfung mit `QUEUED` statt `RUNNING` an.
- Die Job-Funktionen `scan_project`, `score_project`, `classify`, `export_project` und `run_classification_review` nehmen `run_id: int | None = None`. Mit `None` (ein Job, der vor dem Deployment eingereiht wurde) legen sie die Zeile wie bisher selbst an.
- Übernahme durch den Worker: `UPDATE … SET status='RUNNING', last_progress_at=now() WHERE id=:run_id AND status='QUEUED' AND cancel_requested_at IS NULL`.
  - Bei `rowcount == 0` endet der Job sofort ohne jede Arbeit. Der Lauf wurde in der Warteschlange abgebrochen; die API hat ihn schon auf `CANCELLED` gesetzt (Abschnitt 5).
  - `started_at` bleibt der Anlagezeitpunkt, die Wartezeit zählt also zur Laufzeit.
- `api/projects.py::_phase_remaining_seconds` liefert für `QUEUED` und `CANCELLED` `null`. Damit friert der Fortschritt beim letzten Stand ein und zeigt keine Restdauer.

### 3. Abbruchmechanismus

- **Kein `asyncio`-Cancel und kein arq `Job.abort()`.** Beide werfen `CancelledError` mitten in ein Element (halbe Foto-Verarbeitung, laufender COPY). ADR 0019 Schicht 1 bildet das bewusst auf `FAILED` ab, und für Timeout und Shutdown bleibt das so.
- **Merker statt Signal.**
  - Die API setzt `cancel_requested_at` mit einem bedingten `UPDATE … WHERE id=? AND project_id=? AND status IN ('QUEUED','RUNNING') AND cancel_requested_at IS NULL`.
  - Der Worker prüft an den bestehenden Commit-Punkten, also vor jedem neuen Element oder Block und zwischen Phasen.
  - Die Prüfung macht der neue Helfer `run_cancel.py::cancel_requested(session, run) -> bool`: ein `SELECT cancel_requested_at` je Prüfpunkt, ohne eigenes Intervall. Sie kostet eine Primärschlüssel-Lesung je Block bzw. Commit-Batch.
- **Unterbrechbare Wartezeiten.** In `run_cancel.py` liegen:
  - `class RunCancelled(Exception)`;
  - `class CancelToken`: ein `asyncio.Event` plus Beobachter-Task, der `cancel_requested_at` alle **2 s** in **eigener** Session liest;
  - `current_cancel_token: ContextVar[CancelToken | None]`.

  Der Job setzt das Token für die Dauer des Laufs. `asyncio.gather`-Kinder erben den Kontext.
- **Anpassung in `cloud_vision.py`.** `CloudRequestThrottle.acquire()` und die Wiederholungswartezeit in `post_vision_request` (`await throttle.sleep(wait)`) lassen den Schlaf gegen `token.event.wait()` laufen. Gewinnt das Event, werfen sie `RunCancelled`.
  - Es gibt weder `shield` noch das Fangen von `BaseException`, sodass die Docstring-Zusagen gelten.
  - Ein Kontextvariable statt eines Parameters, weil die Schrittmacher prozessweit je Anbieter existieren (`cloud_vision_throttle.py::_THROTTLES`) und `post_vision_request` vier Aufrufstellen hat.
  - Eine schon gesendete HTTP-Anfrage läuft zu Ende („angefangenes Element“).
- **Auswertung nach `gather`.** Die drei `gather(..., return_exceptions=True)`-Blöcke prüfen nach dem Block auf `RunCancelled`, analog zur bestehenden `CancelledError`-Prüfung:
  - Remote: `worker.py::run_remote_category_classification`;
  - Landmark: `worker.py::run_criterion_scoring`;
  - Prüflauf: `classification_review.py::_run_cloud_side`.

  Erfolgreiche Ergebnisse des Blocks werden gespeichert. `RunCancelled` zählt nicht als `failed_calls` und schreibt kein `_record_cloud_vision_error`. Danach endet die Schleife.
- **Abschluss.** Den Endzustand schreibt der Helfer `worker.py::_finish_cancelled(session, run)`, analog zu `_fail_run`: Rollback, dann `status=CANCELLED`, `finished_at=now()`, `error_message=None` (die letzte `phase` bleibt stehen), Commit.
  - `_fail_run`, `_fail_export_run`, `classification_review.py::_fail` und die `except asyncio.CancelledError`-Zweige lesen vorher `cancel_requested_at` frisch aus der DB.
  - Ist der Merker gesetzt, gehen sie nach `_finish_cancelled` statt nach `FAILED`. Bei `CancelledError` wird anschließend weiter re-raised.

### 4. Verhalten je Vorgang

|Vorgang|Prüfpunkt|Bleibt persistiert|Übersprungen|
|---|---|---|---|
|Scan (`run_project_scan`)|vor jedem Block in `_catch_up_aspect_ratios` und in Phase 2b, vor Phase 2a/2b|alle bis dahin committeten Fotos, Varianten, Zähler|Löschen von `removed_paths`, `cleanup_orphaned_cache`|
|Ausschuss (`run_project_scoring`)|vor jedem `SCORE_COMMIT_BATCH_SIZE`-Batch|geschriebene `PhotoScore` (in diesem Lauf neu bewertete Fotos ohne `suggested_status`)|Clustering, Auto-Entscheidung, `suggestions_found`, `gate_confirmed_at`|
|Klassifizierung (`run_classification`)|Remote: vor jedem Block; Eye: vor jedem Foto; Kriterien: vor jedem `CRITERION_SCORING_COMMIT_BATCH_SIZE`-Batch und jedem Landmark-Block; zwischen den Phasen|Remote-Detektionen und Kategorien bisheriger Blöcke, Kriterienwerte, Phasenkosten (`_commit_phase_costs`)|Eye-Analysen, die nur im Speicher liegen (die Phase schreibt erst am Ende), `RANKING`, `_build_grouping_and_rankings`, `_recognize_persons`, `_apply_run_selection`|
|Export (`run_export`)|vor jedem COPY|Ordner auf OpenCloud, `target_path`, `photo_count`, `exported_count`, `failed_count` (vor `_finish_cancelled` committen)|restliche COPYs|
|Prüflauf (`execute_classification_review`)|vor jedem Foto in Eye- und lokalen Seiten, vor jedem Cloud-Block, vor `CASES`|Ergebnisse aller fertigen Seiten und Blöcke; Kosten über das bestehende `finally`|`CASES`/`_write_cases`|

- Manuelle Entscheidungen, Bewertungen, Entwürfe, Endauswahl und Urteile fasst kein Abbruchpfad an.
- Prüflauf:
  - Urteile sind gesperrt, weil `put_case_verdict` und der Prüfungsexport `SUCCESS` verlangen. Ein abgebrochener Prüflauf hat ohnehin keine Fälle.
  - `_reject_while_a_review_runs` blockiert `QUEUED` und `RUNNING`, aber nicht `CANCELLED`. Eine neue Prüfung ist also sofort anlegbar.
  - `get_review` und `get_review_cases` liefern den Teilstand.
- Weitere Wächter, die `QUEUED` wie `RUNNING` behandeln: `projects.py::delete_project` und `_reject_while_a_criterion_run_is_active`. Neu-Auslösen schließt `QUEUED` mit ein.

### 5. Endpunkte (`backend/src/photosort/api/operations.py`, neu)

Der Router hängt unter `/projects/{project_id}/operations` und nutzt dieselbe routerweite Auth wie die übrigen Router. `kind` ist einer von `scan | ausschuss | classification | export | review`.

- `GET /projects/{project_id}/operations` → `200`:

  ```json
  {"operations": [{"kind": "...", "run_id": 1, "label": "Klassifizierung", "status": "queued|running", "cancel_requested": false}]}
  ```

  - Die Liste enthält je `kind` den jüngsten Lauf in `QUEUED` oder `RUNNING`; für `review` alle offenen Prüfungen des Projekts.
  - `label` ist der deutsche Anzeigename, serverseitig aus einer Konstante.
  - Sie dient als Vorschau für „Alle abbrechen“. Ist die Liste leer, ist die Aktion gesperrt.
- `POST /projects/{project_id}/operations/{kind}/{run_id}/cancel` (ohne Body) → `200 {"kind", "run_id", "status", "outcome": "cancel_requested" | "already_finished"}`.
  - `QUEUED`: Das bedingte `UPDATE` setzt `cancel_requested_at`, `status=CANCELLED` und `finished_at` in einer Anweisung.
  - `RUNNING`: Es setzt nur `cancel_requested_at`, und `status` bleibt `running`, bis der Worker abschließt.
  - Klassifizierung: Der Merker wird zusätzlich am zugehörigen `RemoteCategoryClassificationRun` gesetzt.
  - Idempotenz: Ein zweiter Abbruch, ein Abbruch nach Lauf-Ende oder ein verlorenes Rennen ergibt `0` Zeilen und dann `200` mit dem aktuellen, unveränderten Zustand und `already_finished`. Es gibt nie `409`.
  - Ein unbekannter Lauf oder ein Lauf eines anderen Projekts ergibt `404`, weil `project_id` in der `WHERE`-Klausel steht.
- `POST /projects/{project_id}/operations/cancel-all` → `200 {"cancelled": [{kind, run_id, status, outcome}, ...]}`.
  - Dieselbe Logik wird auf die Menge aus `GET` angewandt, strikt mit `project_id` in jeder Anweisung.
  - Eine leere Menge ergibt `200 {"cancelled": []}`. Es gibt kein Ergebnis „fehlgeschlagen“.

### 6. Watchdog (`worker.py::reap_stalled_runs`, ADR 0019 Schicht 2)

- `_fail_if_stalled` und `_fail_export_if_stalled` finalisieren einen hängenden Lauf mit gesetztem `cancel_requested_at` über `_finish_cancelled`, nie mit `FAILED`.
- Jeder der sechs Blöcke erfasst zusätzlich `status == QUEUED AND last_progress_at < now - QUEUED_STALL_THRESHOLD`.
  - Die neue Konstante `QUEUED_STALL_THRESHOLD = timedelta(seconds=JOB_TIMEOUT_SECONDS)` beträgt 24 h, weil ein Job hinter vollen `max_jobs`-Plätzen legitim lange wartet.
  - Ohne Merker wird der Lauf `FAILED` mit dem bestehenden Stillstandstext (Job verloren). Mit Merker wird er `CANCELLED`.

### 7. Pipeline-Status

- `cancelled` bedeutet „nicht erledigt, nicht fehlgeschlagen“.
- `confirm_ausschuss_gate` und `trigger_classify` verlangen den jüngsten `ScoringRun` in `SUCCESS`. Nach einem Abbruch bleibt der Folgeschritt dadurch ohne Codeänderung gesperrt, und `gate_confirmed_at` wird nie gesetzt.
- Frontend `utils/pipelineSteps.ts`:
  - `computeStepStates` wertet nur `success` als erledigt.
  - Der `lauf`-Status von `ProjectStand` wird um `'queued' | 'cancelled'` erweitert.
  - `deriveProjectStand` erzeugt die Texte „{Schritt} wartet“ und „{Schritt} abgebrochen“ ohne Fehlerton.

### 8. Frontend-Datenfluss

- **Typen.** `api/types.ts`: `ScanStatus` wird zu `'queued' | 'running' | 'success' | 'failed' | 'cancelled'`.
  - `ScanSummary` und `CriterionScoringRunSummary` bekommen `id`.
  - Alle Lauf-Zusammenfassungen und die Review-DTOs bekommen `cancel_requested_at: string | null`.
  - Backend-Gegenstück: `ScanSummary`, `ScoringRunSummary`, `ExportRunSummary`, `CriterionScoringRunSummary` in `projects.py` sowie `ReviewListItemOut` und `ReviewDetailOut`.
- **Status-Darstellung.** `utils/processStatus.ts` bekommt `queued` und `cancelled`. Der Punkt ist dekorativ; der Text trägt die Bedeutung, damit der Zustand nicht nur über Farbe erkennbar ist.
- **Polling.** `hooks/useProjects.ts::useProjectQuery` und `useClassificationReviews` pollen bei `'running' || 'queued'`. `useTriggerConfirmation` akzeptiert `'queued'` als Bestätigung.
- **Neuer Hook `hooks/useOperations.ts`.**
  - `useOperationsQuery(projectId)` fragt `GET` nur bei geöffnetem Dialog ab.
  - Dazu kommen `useCancelOperation()` und `useCancelAllOperations()`. Beide invalidieren `['project', id]`, die Review-Queries und `['operations', id]`.
- **Komponenten.**
  - `utils/stepActions.ts`: `StepAction` bekommt den Fall `queued` (busy, Label „… wartet“). `cancelled` wird zu `start` mit `texts.start`.
  - `components/StepActionBar.tsx`: Neben dem Busy-Button steht im Zustand `running`/`queued` ein Button „Abbrechen“ (`onCancel`, `min-h-11 min-w-11`) ohne Bestätigungsdialog. Bei gesetztem `cancel_requested_at` ist er gesperrt und zeigt „Wird abgebrochen …“.
  - Dieselbe Aktion bekommen `ExportSection.tsx`, `ClassificationSection.tsx` und `ClassificationReviewDetailPage.tsx`.
  - „Alle abbrechen“ sitzt in der neuen `ProjectOperationsBar` (siehe UI/UX) und öffnet einen Bestätigungsdialog mit Anzahl und `label`-Liste aus `useOperationsQuery`.
- **Weitere `'running'`/`'failed'`-Verzweigungen**, die gemäß der Liste in der Spec-Anlage `queued`/`cancelled` bekommen: `AusschussStepPage`, `ScanStepPage`, `ClassificationProgress`, `StatusTag`, `WorkflowOverviewDialog`, `classificationReviewLabels.ts::reviewListStand`, `classificationSteps.ts`, `scanStatus.ts`, `test/projectStateSpace.ts`.
- **Seeder.** `demo_state.py` bekommt je einen Lauf in `queued` und `cancelled` für die Oberflächenprüfung.

### 9. Umsetzungsreihenfolge

1. Modelle, Enum-Werte und Migration (`nummern.py migration`).
2. `run_cancel.py` mit `cancel_requested`, `CancelToken` und `RunCancelled`; Schrittmacher und `post_vision_request` unterbrechbar machen.
3. `_finish_cancelled` und das Umleiten der Fehlerpfade.
4. Je Vorgang Übernahme (`run_id`) und Prüfpunkte, in der Reihenfolge Export → Scan → Scoring → Klassifizierung → Prüflauf.
5. Reaper: Vorrang des Merkers, `QUEUED`-Block.
6. API: Auslöser legen `QUEUED` an, Wächter, Zusammenfassungsfelder, `operations.py` samt Router-Einbindung.
7. Frontend: Typen und Status, Polling, Hook, Aktionsleiste, Abschnitte, „Alle abbrechen“, Seeder.
8. `docs/architecture.md` nachziehen: Worker-Komponente (Merker, Übernahme, Reaper) und Datenmodell (sechs Spalten, zwei Enum-Werte).

## Teststrategie

Muster aus dem Testkonzept: Backend `pytest` gegen In-Memory-SQLite, Worker-Funktionen direkt aufgerufen (kein arq/Redis), Doubles nur an der Außengrenze (Fake-OpenCloud-Client, Vision-Transport); Frontend `vitest` mit gemockten Projekt-/Laufdaten. Kein Freeze-Time-Werkzeug, keine Wanduhr-Wartezeiten.

**Zeit und Abbruchzeitpunkt deterministisch.** Der Abbruch wird nie über Zeit ausgelöst, sondern über einen Haken im Test-Double: Der Fake-Client (Download, Upload, Vision-Antwort) setzt nach dem n-ten Element über eine zweite Session `cancel_requested_at` bzw. ruft den Cancel-Endpunkt auf. Erwartung: genau dieses Element wird fertig, danach kein Aufruf des Doubles mehr (Aufrufzähler). Drosselung: `CloudRequestThrottle` mit injiziertem `clock`/`sleep`; der Test-`sleep` blockiert auf einem `asyncio.Event`, der Test setzt währenddessen den Abbruch und gibt das Ereignis frei bzw. erwartet, dass das Warten ohne Freigabe endet. Watchdog: Zeilen mit explizit gealtertem `last_progress_at`, `reap_stalled_runs` direkt aufrufen.

| AK | Ebene | Prüfung |
|---|---|---|
| Sichtbar und erreichbar | vitest | je Vorgang: `running`/`queued` → genau ein „Abbrechen"; `success`/`failed`/`cancelled`/kein Lauf → keiner; Klick ruft Cancel-Mutation ohne Dialog |
| Einzeln | Integration | zwei Läufe desselben Projekts (z.B. Scan + Prüflauf); Abbruch des einen; der andere läuft danach zu Ende, sein Zähler endet über dem Stand zum Abbruchzeitpunkt |
| Sanft | Integration, je Vorgangsart | Haken nach Element n: Endzähler = n (+ laufender Block bei Scan/Prüflauf), Double danach 0 Aufrufe; Drosselungs-Wartezeit und 429-Retry-Wartezeit enden durch Abbruch, kein weiterer `post` |
| Eigener Endzustand | Integration + vitest | Status `cancelled`, `error_message` leer; Scoring: `gate_confirmed_at` bleibt `NULL`, kein Clustering; Klassifizierung: kein Ranking. vitest: Stand-Zeile „… abgebrochen", kein `role="alert"`, Auslöser aktiv, nächster Schritt gesperrt |
| Teilergebnisse | Integration | Zeilenzählung je Tabelle vor/nach Abbruch: `Photo` + Cache-Dateien, Vorschläge, `PhotoScore`, Prüffälle; Scan: Entfernen-/Cache-Aufräumen läuft nicht |
| Kein Verwerfen | Integration + vitest | Cancel-Endpunkte löschen nichts (Zeilenzählung aller Projekttabellen); UI bietet keine Lösch-/Verwerfen-Aktion am abgebrochenen Lauf |
| Export sichtbar | Integration + vitest | Fake-OpenCloud: kein `delete`-Aufruf; `ExportRun` behält Zielpfad und Kopierzahl; UI zeigt beides |
| Prüflauf | API-Integration + vitest | Urteil auf abgebrochene Prüfung → `409`; Ergebnisse lesbar (`200`); neue Prüfung sofort anlegbar (`201`) |
| Alle abbrechen | API-Integration + vitest | Projekt A mit allen fünf Arten laufend/wartend + Projekt B laufend: alle in A `cancelled`/`cancel_requested_at` gesetzt, B unverändert. vitest: Dialog nennt Anzahl und Bezeichnungen, deaktiviert ohne betroffenen Vorgang |
| Wartende Vorgänge | Integration | `queued` abbrechen → `cancelled`; danach gestarteter Job für dieselbe `run_id` kehrt ohne Verarbeitung zurück (Double 0 Aufrufe), Status bleibt `cancelled` |
| Wiederholung und Rennen | API-Integration | zweiter Cancel → `200`, `cancel_requested_at` unverändert; Cancel auf `success`/`failed` → `200`, Status unverändert; Rennen: Abbruch nach letztem Element vor Abschluss → `cancelled` und kein Gate/Ranking; Abschluss vor Abbruch → bleibt `success` |
| Kein Stillstand | Integration | `reap_stalled_runs` mit gealtertem Lauf und gesetztem `cancel_requested_at` → `cancelled`, nie `failed`, keine Stall-Meldung; `CancelledError` (Worker-Neustart) bei gesetztem Abbruchwunsch → `cancelled` |
| Anzeige danach | vitest | `cancelled` mit Zählerstand → Fortschritt zeigt letzten Stand, keine Restdauer, kein indeterminierter Balken |
| Keine fremden Daten | Integration | vor dem Abbruch gesetzt: Einzelentscheidungen, `Rating`, Album-Entwurf, Endauswahl, Prüfurteile → nach Abbruch zeilengleich |
| Beide Nutzer | API-Integration + vitest | Lauf von Nutzer A, Cancel mit Token von B → `200`; vitest: fremd abgebrochener Lauf erscheint als „abgebrochen" |
| Bedienbarkeit | vitest + E2E | Tab erreicht „Abbrechen", Enter/Space löst aus; Zustand als Text; 44 × 44 per Treffertest (`elementFromPoint`) im bestehenden `tap-targets`-Spec |

**Weitere Edge Cases (Integration).** Projektbindung: Cancel mit `run_id` aus Projekt B unter Pfad von A → `404`, B unverändert; unbekannte `kind` → `422`/`404`. `401` deckt der introspektive Auth-Guard-Test automatisch ab. Abbruch während des Export-Uploads eines Fotos: Foto wird fertig kopiert und gezählt.

**Testkonzept.** Ergänzung nötig: neues Muster „kooperativer Abbruch über Test-Double-Haken und blockierenden Fake-`sleep`"; die bekannte Lücke „eingereihter, nicht gestarteter Job" (Projektlöschung) ändert sich durch `queued`-Zeilen und ist dort nachzuziehen.

## UI/UX

Sichtbare Oberfläche: **ja** — an den fünf bestehenden Bedienstellen und an einer neuen, nur bei Bedarf sichtbaren Leiste. Es gibt keine neue Route, kein neues Symbol und kein neues Farbtoken. Abbrechen ist **keine zerstörerische Aktion**: Daten bleiben erhalten. Deshalb trägt sie die Ausprägung `secondary` und nie `destructive`. Zustände werden über **Wörter** unterschieden; Farbe und Punkt begleiten sie nur. Einen `## Design`-Abschnitt gibt es nicht, und für diese Story gibt es keinen Penpot-Entwurf.

### Vorgangsnamen (eine Quelle, neu in `utils/stepActionTexts.ts`)
`OPERATION_LABELS`: `Scan` · `Ausschuss` · `Klassifizierung` · `Export` · `Prüfung` (wie `TERMS.review`).

### Abbrechen je Vorgang
- **Ort:** im selben Block wie Statuszeile und Fortschritt des Vorgangs, rechts neben (ab `sm:`) bzw. unter (Telefon) dem belegten Startknopf, `gap-3`.
  - Scan, Ausschuss, Klassifizierung: in `StepActionBar` über die neue Prop `onCancel` und `cancelRequested`. `StepActionBar` rendert den Knopf nur bei `action.kind` `running`/`queued`.
  - Export: in `ExportSection` neben „Export läuft …“.
  - Prüfung: in `ClassificationReviewDetailPage` › `ReviewStand` hinter dem `StatusTag`. Die Listenzeile ist ein Link und bekommt keinen Knopf; dort wirkt die Projektleiste (unten).
- **Knopf:** `Button variant="secondary" size="sm"`, sichtbare Beschriftung `Abbrechen`. Der zugängliche Name ist `aria-label="{Vorgang} abbrechen"`, z. B. „Scan abbrechen“; das sichtbare Wort ist darin enthalten (WCAG 2.5.3). Sichtbar ist das Board-Maß 32 px; `tap-target` aus dem Grundelement erweitert die Trefferfläche auf 44 × 44 px. Er gehört **nicht** zur `h-11`-Liste, weil er kein heißer Pfad ist. Er ist ein natives `<button>` und damit per Tab sowie Enter/Leertaste bedienbar. Es gibt keine Tastenkürzel, weil Esc für Dialog und Detailansicht reserviert ist. Er fragt nicht nach.
- **Ein Vorgang, ein Knopf.** Es gibt kein Symbol `x-circle`, weil das Symbol „Aussortiert“ bedeutet.

### Zustand „Abbruch angefordert“ (läuft bis zum nächsten Prüfpunkt)
- Der Knopf bleibt an seiner Stelle, ist `disabled busy` und trägt die Beschriftung `Wird abgebrochen…`.
- Die Statuszeile zeigt `{Vorgang} wird abgebrochen…`; `StatusDot` läuft weiter.
- Der Fortschritt bleibt auf dem zuletzt gemeldeten Wert. Die Restdauer entfällt sofort: `EtaLine` wird in `ClassificationProgress` nicht gerendert.
- **Fokus:** Der deaktivierte Knopf kann keinen Fokus halten. Nach erfolgreicher Anforderung erhält deshalb die Statuszeile des Vorgangs den Fokus (`tabIndex={-1}`, bleibt `aria-live="polite"`).

### Endzustände und „wartet“
| Zustand | Statuszeile / `StatusTag` | Punkt / Ton | Auslöser |
|---|---|---|---|
| wartet | `{Vorgang} wartet` | `StatusDot` ohne Status (`bg-separator`) / Ton `never` | deaktiviert: `Wartet auf Start…`, ohne Spinner; daneben `Abbrechen` |
| abgebrochen | `{Vorgang} abgebrochen` | wie „wartet“: ohne Puls, nicht grün, nicht rot | wieder bedienbar mit der Startbeschriftung (`RUN_STEP_TEXTS.*.start` bzw. „Nach OpenCloud exportieren“) |

- **Abgebrochen ist keine Fehlermeldung.** Es erscheint kein `Alert`. Erfolg wird an den grünen Ton und Fehlschlag an den roten Ton plus `Alert` gebunden. Die Unterscheidung trägt das Wort, nicht die Farbe.
- **Fortschritt bleibt stehen:** Bei „abgebrochen“ bleibt der `detail`-Block stehen und zeigt den letzten Stand: `Abgebrochen bei {n} von {m} Dateien` (Scan) bzw. `… Fotos` (Ausschuss). Der Balken bleibt auf diesem Wert und läuft nicht unbestimmt weiter. Die Scan-Bilanz (`dl`) gilt weiterhin nur für einen erfolgreichen Lauf.
- **Klassifizierung:** `ClassificationProgress` bleibt auch bei „abgebrochen“ stehen und wird nicht durch `ClassificationBalance` ersetzt. Der unterbrochene Teilschritt trägt das Wort `abgebrochen`, spätere Teilschritte tragen `nicht begonnen` (neue Werte in `STATE_LABELS`/`data-step-state`). Es gibt keine Restdauer.
- **Stand-Zeile** (`ProjectStandLine`/`deriveProjectStand`): `{Schritt} wartet` bzw. `{Schritt} abgebrochen` mit `StatusTag` im Ton `never`, niemals `failed`. Der nächste Schritt bleibt gesperrt.
- **Export abgebrochen** (`ExportSection`): `Export abgebrochen ({Zeitpunkt}). {k} von {n} Fotos wurden bereits nach {Zielpfad} kopiert.` Der Zielpfad steht in `font-mono` und `break-all`. Dauerhaft darunter steht: `Der Ordner bleibt bestehen — PhotoSort löscht ihn nicht. Bei Bedarf in OpenCloud von Hand entfernen.` Wurde noch kein Ordner angelegt (Abbruch im Zustand „wartet“), steht dort nur: `Export abgebrochen, bevor ein Foto kopiert wurde.`
- **Prüfung abgebrochen** (`ReviewStand`, `reviewListStand`): `StatusTag` im Ton `never` mit dem Wort `abgebrochen`. Daneben steht der letzte Phasentext, z. B. `Abgebrochen bei: Seite B wird klassifiziert, 120 von 300 Fotos`.
  - Es gibt keine Urteilsschaltflächen (`judgeable=false`) und keine Übersichtstabelle (nur bei `success`).
  - Der Export ist gesperrt und dauerhaft erklärt: `Eine abgebrochene Prüfung lässt sich nicht exportieren.` (neu `REVIEW_DETAIL_TEXTS.exportBlockedCancelled`).
  - Auf der Liste erscheint kein `failedLatest`-Alert; „Neue Prüfung anlegen“ ist sofort bedienbar.

### Alle abbrechen (projektweit)
- **Ort:** Die neue Komponente `ProjectOperationsBar` steht oben im Inhaltsbereich jeder Projektseite, also in `ProjectOverviewHost` vor `<Outlet />` und damit auf Schrittseiten, Endauswahl und Prüfseiten an derselben Stelle. Sie ist nicht `sticky`, damit sie keine zweite haftende Leiste neben der Schrittleiste wird.
- **Sichtbarkeit:** Sie wird nur gerendert, solange mindestens ein Vorgang des Projekts läuft oder wartet. Sonst entfällt sie ganz; es gibt also keine deaktivierte Leiste.
- **Aufbau:** Fläche `--surface`, Rand `--border`, `rounded-lg`, `p-3`, `flex flex-wrap items-center justify-between gap-3`.
  - Text (`role="status"`, `aria-live="polite"`): `Läuft oder wartet: {Namen, kommagetrennt}`.
  - Knopf: `Button variant="secondary" size="sm"` mit `Alle abbrechen`. Er ist `disabled`, sobald jeder Vorgang bereits einen Abbruch angefordert hat. Der Text lautet dann `Wird abgebrochen: {Namen}`.
- **Dialog** (`ui/dialog.tsx`):
  - Titel: `Alle Vorgänge abbrechen?`
  - Beschreibung: `{n} Vorgänge werden angehalten:` bzw. `1 Vorgang wird angehalten:`.
  - Inhalt: `<ul>` mit einer Zeile je Vorgang, `{Name} — läuft` bzw. `{Name} — wartet`, darunter `Was bis jetzt fertig ist, bleibt erhalten. Ein gerade begonnenes Foto wird noch abgeschlossen.`
  - Aktion: `Button variant="default"` mit `Alle abbrechen`. `cancelLabel="Weiterlaufen lassen"`, damit es nicht zweimal „abbrechen“ mit gegensätzlicher Bedeutung gibt. Es gibt kein `icon`.
  - Liste und Anzahl werden beim Öffnen festgehalten. Es zählt also das, was bestätigt wird, und ein Poll verschiebt die Liste nicht unter dem Finger.
- **Fokus:** Der Erstfokus liegt auf `Weiterlaufen lassen`. Esc schließt, ein Klick auf den Hintergrund nicht. Während die Anfrage läuft, gilt `cancelDisabled` und `onClose` wird ignoriert. Nach Bestätigung schließt der Dialog, und der Fokus geht auf den Statustext der Leiste (`tabIndex={-1}`), weil der Auslöser dann deaktiviert ist. Bei Abbruch des Dialogs kehrt der Fokus zum Auslöser zurück.

### Fehler, Rennen, kein Verwerfen
- Scheitert nur die **Übermittlung** des Abbruchs (Netz/5xx), erscheint am Ort ein `Alert` mit `Der Abbruch konnte nicht übermittelt werden.` und `Erneut versuchen`. Der Vorgang läuft weiter und wird weiter angezeigt.
- Ein Abbruch, der einen bereits beendeten Lauf trifft, oder ein zweiter Abbruch erzeugt **keine** Meldung. Der nächste Poll zeigt den tatsächlichen Endzustand.
- Bei „abgebrochen“ gibt es **keine** Aktion, die etwas verwirft: kein „Teilergebnisse verwerfen“, kein „Ordner löschen“, keine Wahl Behalten/Verwerfen, weder im Dialog noch danach.

### Design-System nachziehen (`0004-design-system.md` + Skill `design-system`)
Neues Muster **„Vorgang abbrechen“**:
- Die Ausprägung ist `secondary`, nicht `destructive`; Begründung: nichts wird entfernt.
- Der Auslöser sitzt am Fortschritt.
- Zum Zustand „angefordert“ gehören `Wird abgebrochen…`, der deaktivierte Knopf und der Fokus auf der Statuszeile.
- „wartet“/„abgebrochen“ tragen den neutralen Ton `never` und ein Wort, ohne `Alert`.
- Im Dialog trägt der Ausweg die Beschriftung `Weiterlaufen lassen`.
- Die Leiste `ProjectOperationsBar` erscheint nur bei Bedarf.

Es gibt kein neues Token und kein neues Symbol.

## Security

**Sicherheitsrelevant: ja.** Zwei neue zustandsändernde Endpunkte mit fremdgesteuerten Pfad-Ids, ein neuer Endzustand, der in Watchdog, Sperren und Gates mitgedacht werden muss, und ein Rennen zwischen Request, Worker und Watchdog um dieselbe Zeile. Kein neues Secret, kein neuer externer Empfänger, keine neue Schreiboperation auf OpenCloud.

**Bedrohungen und Gegenmaßnahmen (Auflagen für developer):**

- **S1 Auth.** Beide Endpunkte hängen an einem Router mit `dependencies=[Depends(get_current_user)]`. Liegen sie in einem neuen Router, wird dieser in die Liste von `test_auth_guard.py::test_all_project_opencloud_and_stats_routes_require_token` eingetragen. `401` kommt vor jeder Aussage über Projekt oder Lauf.
- **S2 CSRF.** Kein zusätzlicher Mechanismus, wie bei allen bestehenden POSTs: Das Token geht ausschließlich als `Authorization: Bearer` mit, nie als Cookie (Sicherheitskonzept, Auth-Modell). Die Endpunkte dürfen weder ein Cookie noch einen GET-Weg zum Abbrechen akzeptieren.
- **S3 Beide Nutzer, kein BOLA-Bezug.** Laut Bedrohungsmodell darf jeder angemeldete Nutzer jeden Lauf abbrechen, eine Eigentümerprüfung gibt es nicht. Der Endpunkt hat kein Body-Modell und liest keine `user_id`. Wer abgebrochen hat, wird nicht gespeichert. `cancel_requested_at` reicht als Information.
- **S4 Projektbindung.** Den Lauf löst **eine** Anweisung auf: `WHERE id = :run_id AND project_id = :project_id`. Nie `session.get(Run, run_id)` mit nachträglicher Prüfung. Ein unbekanntes Projekt, eine unbekannte Lauf-Id und die Lauf-Id eines fremden Projekts ergeben dieselbe `404` (gleicher Body, Wert nicht gespiegelt). `cancel-all` schränkt **jede** der fünf Abfragen auf `project_id` ein und markiert nie einen Lauf eines anderen Projekts. Den Test dazu stellen zwei Projekte mit je einem laufenden Vorgang, danach läuft der fremde unverändert weiter.
- **S5 Geschlossene Eingaben.** `kind` ist ein `StrEnum` bzw. `Literal` aus genau fünf Werten (scan, ausschuss, classification, export, review). Ein unbekannter Wert ergibt `422` vor jedem DB-Zugriff, und `kind` wird nie zu einem Tabellen- oder Attributnamen zusammengesetzt (feste Zuordnung Enum → Modellklasse). `project_id` und `run_id` sind `Path(ge=1, le=MAX_…)`, sonst wird `>2^63` unter SQLite ein `OverflowError`/`500` (bestehendes Muster aus `album_decisions.py`/`persons.py`).
- **S6 Antworten ohne fremde Daten.** Die Antwort ist eine ausdrückliche Projektion auf `kind`, `run_id` und `status` (bei cancel-all eine Liste davon für dieses Projekt). Sie enthält kein serialisiertes Run-Objekt, keine `error_message`, keinen Exportpfad eines fremden Projekts und keine Nutzerdaten. Die Bestätigungsvorschau „Alle abbrechen“ (Anzahl, Bezeichnungen) speist sich aus dem projektgebundenen Projekt-Lesepfad, nicht aus einer projektübergreifenden Abfrage.
- **S7 Zustandswechsel nur per Compare-and-Set.** Jeder Übergang in einen Endzustand wird als bedingtes `UPDATE … WHERE status IN ('queued','running')` geschrieben, das gilt für Abbruch-Request, Worker-Abschluss und Watchdog gleichermaßen. Ein Endzustand (`success`/`failed`/`cancelled`) wird nie überschrieben. Ein zweiter Abbruch und ein Abbruch eines beendeten Laufs sind `200` mit dem tatsächlichen Status, nie `409`/`500`. Ein `queued`-Lauf wird direkt `cancelled`. Der Worker prüft beim Start, ob die Zeile noch `queued` ist, und beginnt sonst nichts.
- **S8 Kein Rückfall auf `failed`.** Der kooperative Abbruch läuft über `cancel_requested_at` und nicht über `arq` `Job.abort()`. Die bestehenden `except asyncio.CancelledError`-Zweige rufen `_fail_run` auf und würden den Lauf sonst als `failed` ausweisen. `reap_stalled_runs` lässt Zeilen mit gesetztem `cancel_requested_at` in Ruhe oder finalisiert sie als `cancelled`, nie als `failed`. `queued`-Zeilen dürfen nicht über `last_progress_at` (Server-Default beim Anlegen) als Stillstand gelten.
- **S9 „Aktiv“ heißt `running` oder `queued`, überall.** Alle bestehenden `409`-Sperren, die heute `== ScanStatus.RUNNING` prüfen, behandeln `queued` als aktiv. Bekannt sind `api/cameras.py::_reject_while_a_run_is_active`, die Projektlöschung in `api/projects.py` (~Z. 1006), `_reject_while_a_criterion_run_is_active` und die Prüfungs-Sperre in `classification_reviews.py` (~Z. 568). Sonst startet ein wartender Lauf später in Zeilen, die inzwischen beschrieben oder gelöscht wurden. Umgekehrt blockiert `cancelled` nichts.
- **S10 Gates bleiben zu.** `cancelled` zählt nirgends als `success`: Ausschuss-Gate-Autoset, Freischaltung des nächsten Schritts, „neuester erfolgreicher Lauf“ bei Rangfolge und Auswahl. Urteile im Prüflauf bleiben an `status == SUCCESS` gebunden (`put_case_verdict`, bestehende Prüfung beibehalten).
- **S11 Kosten und Daten.** Ein abgebrochener Cloud-Lauf friert seine Ist-Kosten auf demselben Pfad ein wie ein fehlgeschlagener, inklusive des noch abgeschlossenen Elements. Die unterbrechbare Drosselungswartezeit hält dabei keine DB-Transaktion offen. Der Abbruchpfad löscht nichts: kein `DELETE` auf Ergebniszeilen, keine neue WebDAV-Lösch- oder `MOVE`-Operation (der Exportordner bleibt).
- **S12 Logging.** Eine Zeile pro Abbruch mit `project_id`, `kind`, `run_id` und dem Ergebnis-Token (`cancelled`/`already_final`). Kein Username, keine `user_id`, kein Dateipfad, kein Exportzielpfad, kein Fototitel.

**Sicherheitskonzept anpassen: ja**, im Abschnitt „Job-Lauf-Terminierung/Watchdog“: der neue Endzustand `cancelled` und der Grundsatz „Endzustand nur per Compare-and-Set, Watchdog finalisiert nie einen abgebrochenen Lauf“. Dazu Ankerlisten-Zeilen für S4 (Projektbindung der Abbruch-Endpunkte), S7/S8 (CAS, kein `failed`) und S9 (aktiv = `running|queued` in allen `409`-Sperren). Eintragen tut das der umsetzende Pull Request, nicht die Spec.

**Keine Produktentscheidung offen.** Alle Punkte folgen aus Bedrohungsmodell (kein Innentäter zwischen den beiden Nutzern), Auth-Modell und bestehenden Ankern.

## Entscheidungen

- Skip-Entscheidungen: keine — alle vier Konsultationen (architect, ux-ui-designer, test-engineer, security-engineer) liefen.
- Abbruch ist kooperativ über `cancel_requested_at`, kein `asyncio`-Cancel und kein arq `Job.abort()` (ADR 0147).
- Wartende Vorgänge werden als `QUEUED`-Laufzeile beim Auslösen angelegt; Abbruch eines wartenden Laufs setzt ihn direkt auf `CANCELLED`.
- Rennen kurz vor Ende: Ein Abbruch nach dem letzten Element, aber vor der Abschlussphase endet `cancelled` ohne Gate/Ranking/Fälle; ein vorher abgeschlossener Lauf bleibt `success`.
- Rückmeldungen: zweiter Abbruch und Abbruch eines beendeten Laufs `200` (`already_finished`); fremder/unbekannter Lauf `404`; unbekanntes `kind` `422`; Urteil auf abgebrochenen Prüflauf `409`.
- Ein Worker-Abbruch (`CancelledError`) bei bereits gesetztem Merker endet `cancelled`, nicht `failed`.
- „Alle abbrechen“ sitzt in der neuen `ProjectOperationsBar` in `ProjectOverviewHost` (UX-Vorgabe), nicht in `ProjectNav`; die Liste der Vorgänge liefert `GET /projects/{id}/operations`.
- Der Einzel-Abbruchknopf nutzt `secondary`, nie `destructive`; das Design-System (`specs/architecture/0004-design-system.md`) wird im umsetzenden PR um das Muster „Vorgang abbrechen“ ergänzt.
- Vorgangsart heißt in der API `ausschuss` (nicht `scoring`); die feste Menge ist `scan | ausschuss | classification | export | review`.
- Ein abgebrochener Lauf behält seine letzte `phase` und seine Zähler (Ausnahme vom „`phase = None` wie jeder beendete“), damit die Anzeige „Abgebrochen bei …“ den letzten Stand nennen kann; `_finish_cancelled` setzt `phase` deshalb nicht zurück.
- Eye-Analysen, die nur im Speicher liegen, werden bei Abbruch verworfen; persistiert ist, was am Prüfpunkt committet war.
- Testkonzept (`specs/architecture/0002-testkonzept.md`) und Sicherheitskonzept (`specs/architecture/0003-securitykonzept.md`) werden im umsetzenden PR ergänzt (Muster Test-Double-Haken/blockierender Fake-`sleep`; Endzustand `cancelled`, Compare-and-Set, aktiv = `running|queued`).

## Out of Scope

- Harter Abbruch mitten in einem Element (Prozess-/Task-Kill); der Abbruch ist immer kooperativ.
- Verwerfen oder Zurückrollen von Teilergebnissen eines abgebrochenen Laufs.
- Automatisches Aufräumen eines abgebrochenen Export-Ordners auf OpenCloud.
- Fortsetzen eines abgebrochenen Laufs an der Abbruchstelle; ein neuer Lauf startet regulär.
- Vorgänge, die keine der fünf genannten sind.
