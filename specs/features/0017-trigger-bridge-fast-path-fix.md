# 0017 - Fortschrittsbalken/Button hängen bei schnellen Scan-/Scoring-Läufen

**Status:** Accepted
**Erstellt:** 2026-08-05
**Bezug:** Bug-Report aus `specs/inbox/0001-fortschrittsbalken-verschwindet-bei-vorauswahl.md`, geschärft in interaktiver Session mit Daniel (2026-08-05)

## Ziel

Beim Klick auf "Beste Fotos automatisch vorschlagen" (Scoring-Trigger aus Spec 0003) verschwindet der Fortschrittsbalken nach ca. 1 Sekunde, ohne dass sichtbar etwas passiert — der Button bleibt intern dauerhaft im Busy-Zustand ("Wird vorgeschlagen…") hängen. Root Cause: der Bridging-Effekt in `ProjectDetailPage.tsx`, der die Zeit zwischen dem `202`-Trigger und dem asynchron im Worker gesetzten `status="running"` überbrückt, setzt sein Warte-Flag nur zurück, wenn er den Zwischenzustand `running` tatsächlich beobachtet. Für Projekte mit weniger als `SCORE_COMMIT_BATCH_SIZE = 25` Fotos läuft der Scoring-Job im Worker komplett ohne `await`-Punkt durch (~6ms) — weit unter dem 2-Sekunden-Poll-Intervall — wodurch der Zwischenzustand nie beobachtet wird und das Flag für immer hängen bleibt. Derselbe strukturelle Bug existiert im analogen Scan-Trigger-Effekt, tritt dort aber praktisch nie auf, da Scans durch echte Netzwerk-I/O realistisch immer länger als das Poll-Intervall dauern. Diese Spec behebt beide Fälle im selben Zug.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich, dass mir beim Anstoßen von Scan oder automatischer Vorauswahl jederzeit ein korrekter Status angezeigt wird — auch wenn der Lauf so schnell durchläuft, dass der Zwischenzustand "running" beim Polling nie beobachtet wird — damit ich zuverlässig erkenne, ob der Vorgang erfolgreich war oder fehlgeschlagen ist, und der Button danach wieder bedienbar ist, statt dauerhaft im Busy-Zustand hängen zu bleiben.

## Akzeptanzkriterien

- [ ] Springt `scoringStatus` (bzw. `scanStatus`) beim ersten Poll nach dem Trigger direkt auf `success`, ohne dass `running` je beobachtet wurde, reaktiviert sich der jeweilige Button spätestens beim nächsten Render (Text zurück zum Ausgangszustand) — das interne `awaiting*Confirmation`-Flag darf nicht dauerhaft `true` bleiben.
- [ ] Dasselbe für einen direkten Sprung auf `failed`: Button reaktiviert sich, die Fehleranzeige (`Alert`, bei Scoring inkl. "Erneut versuchen") erscheint sofort und wird nicht durch die bisherige `!isScoreBusy`-Gate-Bedingung verzögert/unterdrückt.
- [ ] Kein geleaktes Polling-Intervall: springt der Status direkt auf `success`/`failed`, wird nach dem einen Bestätigungs-Refetch kein fortlaufendes `setInterval` mehr aktiv gehalten (bisher lief `setInterval` unbegrenzt weiter, da es nie terminiert wurde).
- [ ] Keine Cross-Contamination zwischen Scan- und Scoring-Hook-Instanz: ein Sprung auf `success`/`failed` beim Scan-Trigger beeinflusst nicht das `awaitingScoreConfirmation`-Flag und umgekehrt.
- [ ] Regressionsfrei: durchläuft der Status tatsächlich `running` (Normalfall bei ≥ 25 Fotos), bleibt das bestehende Verhalten (granularer Fortschrittsbalken, `aria-live`-Dezil-Ansagen, Abschluss-Ansage) exakt erhalten — bestehende Tests in `ProjectDetailPage.test.tsx` bleiben ohne Assertion-Anpassung grün.
- [ ] Neue Regressionstests für: Scan→`success` ohne `running`, Scan→`failed` ohne `running`, Scoring→`success` ohne `running`, Scoring→`failed` ohne `running` (inkl. Nachweis, dass die entfernte Gate-Bedingung den Fehler nicht mehr verzögert).

## Datenmodell-Bezug

Nicht betroffen — reiner Frontend-State-Timing-Fix, kein Backend-/Worker-Code, kein Datenmodell.

## Architektur / Umsetzung

**Betroffene Dateien:**
- `frontend/src/pages/ProjectDetailPage.tsx` (Fix + Refactoring)
- `frontend/src/pages/ProjectDetailPage.test.tsx` (neue Regressionstests)

Keine Backend-/Worker-Änderung nötig — `run_project_scoring` verhält sich korrekt; der Bug liegt ausschließlich in der Frontend-Annahme, dass der Zwischenzustand "running" beim Polling immer beobachtbar ist.

**Entwurfsentscheidungen:**

1. Die beiden fast identischen Bridging-Effekte (Scan-Trigger, Scoring-Trigger) werden zu einem gemeinsamen, **dateilokalen** (nicht exportierten) Hook zusammengeführt, definiert oberhalb der Komponente in derselben Datei, zweimal aufgerufen (Scan, Scoring). Begründung: das Muster wird aktuell nachweislich nur hier zweimal gebraucht (per `grep` über `frontend/src` verifiziert) — eine Auslagerung nach `hooks/useProjects.ts` als exportierter, wiederverwendbarer Hook wäre Spekulation auf einen dritten Konsumenten, den es nicht gibt. Eine reine Erweiterung der Bedingung an beiden bisherigen Stellen hätte die bestehende Fast-Beinahe-Duplikation nur vergrößert.
2. Der Hook setzt sein `awaiting`-Flag künftig auch zurück, wenn der Status direkt auf `success` oder `failed` springt, nicht nur bei `running` (Kern des Fixes).
3. Der Hook kapselt weiterhin das bestehende `refetchRef`-Pattern (Ref statt direkter `query.refetch`-Abhängigkeit), unverändert gegenüber dem bisherigen Code, nur einmal statt zweimal implementiert.
4. Die zusätzliche `!isScoreBusy`-Gate-Bedingung auf der Scoring-Fehler-`Alert` entfällt ersatzlos, analog zur bereits ungegateten Scan-Fehleranzeige.
5. Die erklärenden Kommentare oberhalb der bisherigen Effekte werden auf den neuen Hook verschoben/aktualisiert und um den Fast-Path-Fall ergänzt (kein `await` zwischen RUNNING- und finalem Commit bei `photos_total < SCORE_COMMIT_BATCH_SIZE`, Verweis auf Spec 0017).

**Reihenfolge der Umsetzung (TDD):**
1. Regressionstests in `ProjectDetailPage.test.tsx` zuerst (fehlschlagend): Mock so aufsetzen, dass der Refetch nach dem Trigger direkt `status: 'success'` bzw. `status: 'failed'` liefert, ohne je `'running'` zu durchlaufen — für Scan und Scoring.
2. Hook extrahieren, Bedingung erweitern (Punkte 1-3) — Tests werden grün.
3. `!isScoreBusy`-Gate entfernen (Punkt 4) — zugehöriger Test wird grün.
4. Kommentare aktualisieren (Punkt 5).
5. Vollständige Test-/Lint-/Typecheck-Läufe (`vitest`, `oxlint`, `tsc`) vor PR.

**Keine ADR nötig:** Bugfix innerhalb eines bereits akzeptierten Musters (Bridging-Effekt aus Spec 0003/0005), keine neue Technologie, kein Datenmodell-Bezug. `architecture/0001-overview.md` und README bleiben unverändert.

## UI/UX

Sichtbare Oberfläche: ja (`ProjectDetailPage.tsx`, Scan- und Scoring-Trigger-Buttons). Der Fix wendet ausschließlich das bestehende, im Design-System dokumentierte "Aktions-Button während laufender Anfrage"-Muster korrekt an — kein neues Muster, keine Design-System-Aktualisierung nötig.

Bei sehr schnellen Läufen (< 25 Fotos) springt der Button-Text nach dem Fix abrupt (< 1s) von "Wird vorgeschlagen…" auf den Endzustand. Das ist **akzeptiertes, kein zu behebendes Verhalten**: eine künstliche Mindest-Anzeigedauer des Busy-Zustands würde dem Designprinzip "Ehrliche Ladezustände statt Warten erzwingen" (`architecture/0004-design-system.md`) widersprechen und ist unnötig, da das Ergebnis danach dauerhaft sichtbar bleibt (Statuszeile "Vorschläge aktualisiert"/Fehler-Alert mit Retry, keine verschwindende Toast-Meldung). Der Fortschrittsbalken selbst bleibt an `status === 'running'` gekoppelt und wird im Fast-Path korrekt nicht angezeigt — dieser Zwischenzustand existiert real nur für Sekundenbruchteile.

## Security

Nicht relevant. Reines React-State-Timing-Fix, keine neue API, kein neuer Endpunkt, kein Backend-Code betroffen, kein Auth-/Datenmodell-Bezug. Die entfernte Gate-Bedingung zeigt lediglich eine bereits vom Backend gelieferte, authentifizierte Fehlermeldung zuverlässiger an — keine neue Datenquelle, keine Ausweitung der Sichtbarkeit. Keine Ergänzung von `specs/architecture/0003-securitykonzept.md` nötig.

## Teststrategie

Integrationstest in `ProjectDetailPage.test.tsx` mit `@testing-library/react`, `MemoryRouter` + `QueryClientProvider`, gemockten API-Modulen — bestehende Projektkonvention, unverändert anwendbar. Kein separater Hook-Test, da der neue Hook dateilokal und nicht exportiert ist.

**Timer-Entscheidung:** keine `vi.useFakeTimers()` einführen — konsistent mit den bisherigen Polling-Tests in dieser Datei, die reale Timer mit großzügigen `waitFor`-Timeouts nutzen. Die kritischen Regressionsfälle (Sprung auf `success`/`failed` ohne `running`) sind bereits synchron nach dem ersten aufgelösten Refetch sichtbar, brauchen keinen Zeitfortschritt. Für den Nachweis "kein geleaktes Intervall" reicht ein kurzer Real-Time-Wait über eine Poll-Periode hinaus (analog zum bestehenden Unmount-Test), der prüft, dass kein weiterer API-Call erfolgt.

**Neue Testfälle:**
1. Scan: Status springt direkt auf `success` → Button reaktiviert, kein weiterer `getProject`-Call.
2. Scan: Status springt direkt auf `failed` → Button reaktiviert, Fehleranzeige sofort sichtbar.
3. Scoring: Status springt direkt auf `success` → Button reaktiviert, kein weiterer `getProject`-Call.
4. Scoring: Status springt direkt auf `failed` → Button reaktiviert, Fehler-`Alert` inkl. "Erneut versuchen" sofort sichtbar (Nachweis, dass die entfernte Gate-Bedingung den Fehler nicht mehr verzögert).
5. Cross-Contamination-Test: Scan springt auf `success`, während Scoring gleichzeitig noch wartet → Scoring-Button bleibt unbeeinflusst busy.

Bestehende Running-Pfad-Tests bleiben unverändert als Regressionsschutz (keine neuen Tests nötig für den Normalfall).

`specs/architecture/0002-testkonzept.md`: keine Aktualisierung nötig — kein neues externes System, kein neues Mocking-Muster, kein neues Werkzeug, nur Anwendung der bestehenden Frontend-Integrationstest-Konvention auf einen konsolidierten Hook.

## Entscheidungen

- **Scan-Trigger wird mitgefixt**, obwohl der Bug dort bisher nie beobachtet wurde: gleicher Code, gleiche Fehlerklasse, geringer Zusatzaufwand — explizite Entscheidung von Daniel im Schärfungsgespräch (2026-08-05), um eine latente Lücke nicht ungefixt zu lassen.
- **Gemeinsamer dateilokaler Hook statt zweifacher Bedingungserweiterung:** verhindert, dass der Fix die bestehende Beinahe-Duplikation weiter vergrößert, ohne eine verfrühte, ungenutzte Abstraktion nach `hooks/useProjects.ts` zu exportieren (architect-Konsultation, 2026-08-05).
- **Keine Mindest-Anzeigedauer für den Busy-Zustand:** widerspräche dem Design-Prinzip "ehrliche Ladezustände", unnötig da das Ergebnis dauerhaft sichtbar bleibt (ux-ui-designer-Konsultation, 2026-08-05).
- **Keine `vi.useFakeTimers()`:** konsistent mit bestehender Testkonvention in `ProjectDetailPage.test.tsx`, für die kritischen Fälle nicht nötig (test-engineer-Konsultation, 2026-08-05).
- **Keine ADR:** reine Implementierungsdetail-Entscheidung innerhalb bereits akzeptierter Richtung (architect-Konsultation, 2026-08-05).
- **`started_at`-Vergleich statt blossem `status !== null`:** beim Implementieren stellte sich heraus, dass ein simples "Reset bei jedem nicht-null Status" (wörtliche Lesart von Entwurfsentscheidung 2) den bestehenden Regressionstest für Grund 1 (stale Status vom vorherigen Lauf direkt nach dem Trigger) gebrochen hätte. Der Hook vergleicht deshalb zusätzlich den beobachteten `started_at`-Zeitstempel (jeder Lauf bekommt serverseitig einen neuen, `backend/src/photosort/worker.py`) gegen einen vor dem Klick eingefrorenen Baseline-Wert, um einen genuinely neuen Lauf von einem stehengebliebenen alten zu unterscheiden. Technische Detailentscheidung des `developer`-Agenten innerhalb der akzeptierten Spec, im architect-Review (Pragmatiker/Senior-Entwickler/Pedant-Perspektive) als der `status !== null`-Alternative und den Alternativen (Generation-Zähler, `query.dataUpdatedAt`) überlegen bestätigt.

## Offene Fragen

Keine.

## Out of Scope

- Änderung an `SCORE_COMMIT_BATCH_SIZE` oder am Worker-Commit-Verhalten selbst — das Fast-Path-Timing ist korrektes, gewolltes Verhalten, nicht Teil des Bugs.
- Eine Mindest-Anzeigedauer/künstliche Verzögerung des Busy-Zustands (siehe UI/UX-Abschnitt).
