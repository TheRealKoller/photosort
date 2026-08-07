# 0021 - Zusammenfassung nach Scoring-Lauf: Anzahl gefundener Vorschläge

**Status:** Implemented ([PR #38](https://github.com/TheRealKoller/photosort/pull/38))
**Erstellt:** 2026-08-07
**Bezug:** Bug-Report von Daniel selbst (interaktive Session, 2026-08-07), als vermeintlicher Bug erfasst in `specs/inbox/0005-keine-sichtbaren-automatischen-vorschlaege.md`. Untersuchung ergab: kein Bug — Spec [0003](./0003-automatic-best-photo-selection.md) verhält sich korrekt (Phase A spricht laut ADR 0006 bewusst nie eine positive Empfehlung aus, nur Ablehnungen für unscharfe/duplizierte Fotos; ein Projekt ohne solche Fotos zeigt zurecht null Badges). Der eigentliche Missstand war der in Spec 0003 selbst als "Nice-to-have" vorgesehene, aber nie umgesetzte Zähler ("Optional: kurze Zusammenfassung nach dem letzten Lauf … analog zum bestehenden `last_scan`-Text"). Diese Spec holt genau das nach, direkt mit Daniel vereinbart (kein separates Schärfungsgespräch, kleine, in sich abgeschlossene Ergänzung eines bereits implementierten Features).

## Ziel

Nach einem abgeschlossenen Scoring-Lauf ("Beste Fotos automatisch vorschlagen") zeigt die Projekt-Detailseite an, **wie viele** Vorschläge der Lauf tatsächlich gefunden hat, statt nur des bisherigen generischen "Vorschläge aktualisiert". Das macht sichtbar, ob der Lauf korrekt durchlief und schlicht keine Auffälligkeiten fand, oder ob tatsächlich Vorschläge entstanden sind, die im Grid/Detail/Compare betrachtet werden können.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich nach einem Klick auf "Beste Fotos automatisch vorschlagen" sofort sehen, wie viele Vorschläge gefunden wurden, damit ich nicht rätseln muss, ob der Lauf funktioniert hat, wenn ich anschließend im Grid keine oder nur wenige Vorschlags-Badges sehe.

## Akzeptanzkriterien

- [x] `ScoringRun` bekommt ein neues Feld `suggestions_found: int` (Default `0`), das am Ende eines erfolgreichen Laufs auf die Anzahl der Fotos gesetzt wird, deren `PhotoScore.suggested_status` in diesem Lauf gesetzt wurde (Duplikat-Verlierer + zu unscharfe Fotos, siehe `worker.py::run_project_scoring`, Variable `rejected_ids`).
- [x] Ein fehlgeschlagener Lauf (`status=failed`) lässt `suggestions_found` auf `0` (Default) — der zählende Verarbeitungsschritt läuft erst nach der Duplikat-/Cluster-Erkennung, die bei einem Fehler davor möglicherweise nicht erreicht wurde; kein irreführender Teilstand.
- [x] `ScoringRunSummary` (Backend-Response-Model, `api/projects.py`) und das gleichnamige Frontend-Interface (`api/types.ts`) bekommen das neue Feld `suggestions_found: number`.
- [x] Projekt-Detailseite: nach einem erfolgreichen Lauf steht statt "Vorschläge aktualisiert" jetzt "`N` Vorschlag gefunden" (N=1) bzw. "`N` Vorschläge gefunden" (N≠1), unverändert `aria-live="polite"` bei Zustandswechsel angesagt (bestehendes Muster aus Spec 0017, nicht bei jedem Poll-Tick).
- [x] Bestehende Tests (`ProjectDetailPage.test.tsx`) für den bisherigen generischen Text werden auf den neuen, zählerbasierten Text angepasst; neue Testfälle für N=0, N=1, N>1.
- [x] Migration additiv (neue nullable-freie Spalte mit Server-Default `0` auf `scoring_runs`), keine Änderung an `photo_scores`, `ratings`, `photos`, `projects`, `scan_runs`.

## Datenmodell-Bezug

Additive Erweiterung von `ScoringRun` (Spec 0003) um `suggestions_found: int`. Kein neues Modell, keine Änderung an `PhotoScore`/`Rating`.

## Architektur / Umsetzung

**Betroffene Dateien:**

- `backend/src/photosort/models.py` — `ScoringRun.suggestions_found: Mapped[int] = mapped_column(default=0, server_default="0")`.
- Neue Alembic-Migration (analog `a1c2d3e4f5a6_add_scoring_tables.py`): `ALTER TABLE scoring_runs ADD COLUMN suggestions_found INTEGER NOT NULL DEFAULT 0`.
- `backend/src/photosort/worker.py::run_project_scoring` — direkt nach der Duplikat-/Cluster-Erkennung (wo `rejected_ids` feststeht, vor dem `for photo_id, ... in computed.items()`-Schreibpass bzw. direkt danach, vor `scoring_run.status = ScanStatus.SUCCESS`): `scoring_run.suggestions_found = len(rejected_ids)`.
- `backend/src/photosort/api/projects.py` — `ScoringRunSummary` um `suggestions_found: int` ergänzen (Pydantic-Feld, `from_attributes` greift automatisch über das neue Model-Feld).
- `frontend/src/api/types.ts` — `ScoringRunSummary` um `suggestions_found: number` ergänzen.
- `frontend/src/pages/ProjectDetailPage.tsx` — Zeile mit `{scoringStatus === 'success' && 'Vorschläge aktualisiert'}` (aktuell Zeile 284) ersetzen durch eine Ableitung aus `scoringRun.suggestions_found` mit Singular/Plural-Fallunterscheidung.

**Reihenfolge der Umsetzung (TDD):**

1. Backend-Migration + Model-Feld, dann Test in `test_worker_score_project.py` (fehlschlagend): Lauf mit bekannter Anzahl unscharfer/duplizierter Testfotos → `scoring_run.suggestions_found` erwartet `N`.
2. Worker-Zeile ergänzen — Test grün.
3. `ScoringRunSummary`-Serialisierungstest (`test_api_projects.py` o.ä.): `GET /projects/{id}` liefert `last_scoring_run.suggestions_found`.
4. Frontend: fehlschlagender Test in `ProjectDetailPage.test.tsx` für den neuen Text (N=0/1/>1), dann Implementierung, dann grün.

**Keine ADR nötig:** additive Erweiterung eines bereits akzeptierten Musters (ScoringRun/ScoringRunSummary aus Spec 0003), keine neue Technologie, kein strukturell neues Datenmodell.

## UI/UX

Ersetzt nur den bestehenden Text an derselben Stelle (`ProjectDetailPage.tsx`, Statuszeile unterhalb des Trigger-Buttons), kein neues Element, kein neues Muster im Design-System nötig. `aria-live`-Verhalten unverändert (Spec 0017): Text ändert sich nur beim Zustandswechsel, nicht bei jedem Poll.

- `N = 0`: "0 Vorschläge gefunden" — bewusst kein beschönigender Sondertext ("Alles bestens!" o.ä.), da die Zahl selbst bereits eindeutig ist und ein zusätzlicher Text nur eine weitere zu pflegende Formulierung wäre (Minimalismus, kein Mehrwert gegenüber der reinen Zahl).
- `N = 1`: "1 Vorschlag gefunden" (Singular).
- `N > 1`: "N Vorschläge gefunden" (Plural).

## Security

Nicht relevant. Rein additive Zähler-Spalte, serverseitig berechnet, kein neuer Eingabepfad, keine neue Sichtbarkeit über das bereits bestehende, dokumentierte `last_scoring_run`-Feld hinaus (Spec 0003, dort bereits als unbedenklich bewertet). Keine Ergänzung von `specs/architecture/0003-securitykonzept.md` nötig.

## Teststrategie

- *Integrations-Ebene* (`backend/tests/test_worker_score_project.py`): bestehendes Testmuster erweitern um Assertion auf `scoring_run.suggestions_found` für die bereits vorhandenen Szenarien (Duplikat-Cluster, unscharfes Foto, Mix aus beidem, keine Auffälligkeiten → `0`).
- *API-Ebene*: `ScoringRunSummary`-Serialisierung deckt das neue Feld ab (analog bestehendem Muster für `photos_total`/`photos_processed`).
- *Frontend*: `ProjectDetailPage.test.tsx` — drei neue/angepasste Fälle für N=0/1/>1 statt des bisherigen einen Falls für den generischen Text.

Kein neues Testmuster, keine Aktualisierung von `specs/architecture/0002-testkonzept.md` nötig — reine Anwendung bestehender Konventionen auf ein zusätzliches Feld.

## Entscheidungen

- **`suggestions_found` bleibt bei einem fehlgeschlagenen Lauf auf `0`** statt eines Teilstands: der Zählschritt läuft erst nach der vollständigen Duplikat-/Cluster-Erkennung, ein Teilstand davor wäre irreführend genauer als er ist. Direkt mit Daniel vereinbart.
- **Kein Sondertext für `N = 0`**, nur die nackte Zahl: vermeidet eine zusätzliche, weitere zu pflegende Formulierung ohne echten Mehrwert gegenüber der eindeutigen Zahl selbst.
- **Kleine Ergänzung direkt angelegt, kein separates Idea-Sharpening-Gespräch:** Daniel hat die Ergänzung nach der Bug-Diagnose direkt angefragt ("lege es direkt als kleine Ergänzung an") — die Diagnose selbst deckte bereits Verständnis, Ursache und Lösungsrichtung ab, ein weiteres Schärfungsgespräch hätte nur wiederholt, was schon geklärt war.

## Offene Fragen

Keine.

## Out of Scope

- Eine positive Empfehlung ("dieses Foto ist besonders gut") — bleibt Phase B (Ideenspeicher, siehe Spec 0003), unverändert durch diese Spec.
- Aufschlüsselung des Zählers nach Grund (Duplikat vs. unscharf) in der UI — die reine Gesamtzahl beantwortet die eigentliche Frage ("hat der Lauf etwas gefunden?") bereits vollständig; eine Aufschlüsselung wäre zusätzliche Komplexität ohne im Bug-Report angefragten Nutzen.
