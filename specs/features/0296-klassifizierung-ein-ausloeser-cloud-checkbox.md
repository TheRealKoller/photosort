# 0296 - Klassifizierung mit einem Auslöser und laufbezogener Cloud-Checkbox

**Status:** Accepted
**Erstellt:** 2026-09-01
**Bezug:** [GitHub-Issue #296](https://github.com/TheRealKoller/photosort/issues/296) (Refinement vor dieser Spec-Erstellung abgeschlossen, Story-Inhalt unverändert übernommen)

## Ziel

Die Klassifizierung eines Projekts zerfällt heute in zwei getrennt auszulösende Läufe, deren richtige Reihenfolge man kennen muss: erst die Remote-Kategorisierung, dann die Kriterien-Bewertung — weil die Remote-Ergebnisse erst durch einen (erneuten) lokalen Bewertungslauf in die Kategorie-Vorschläge einfließen. Diese Kopplung ist an der Oberfläche nicht selbsterklärend; sie wird heute nur durch einen Hinweistext nachträglich erklärt. Wer die Reihenfolge nicht kennt, erhält ein Ergebnis ohne die Cloud-Anreicherung, ohne dass etwas sichtbar schiefgeht.

Verschärfend kommt hinzu, dass die Trennung in "lokal" und "remote" faktisch nicht stimmt: auch der als lokal beschriebene Bewertungslauf ruft die Cloud auf (Sehenswürdigkeits-Erkennung), sobald die Cloud-Bilderkennung für das Projekt freigegeben ist. Der Erklärtext behauptet dort ausdrücklich das Gegenteil. Es gibt damit keine Stelle, an der verlässlich erkennbar oder steuerbar wäre, ob ein Durchlauf Cloud-Kosten verursacht.

Ziel ist ein einziger, verständlicher Auslöser für die gesamte Klassifizierung, bei dem die Cloud-Nutzung eine bewusste, sichtbare Entscheidung pro Durchlauf ist — statt einer Reihenfolge-Regel, die man auswendig können muss.

## User Story

Als Betreiber der PhotoSort-Installation möchte ich die Klassifizierung eines Projekts mit einem einzigen Auslöser starten und dabei über eine Checkbox entscheiden, ob dieser Durchlauf die Cloud nutzen darf, damit ich weder die richtige Reihenfolge zweier Läufe kennen muss noch im Unklaren bleibe, ob und wofür gerade Kosten entstehen.

## Akzeptanzkriterien

**Ein Auslöser**

- [ ] Die Klassifizierung wird über genau einen Auslöser gestartet; die bisherige getrennte Auslösung von Remote-Kategorisierung und Kriterien-Bewertung entfällt.
- [ ] Bei aktivierter Cloud-Nutzung laufen die Cloud-Anteile so früh im Durchlauf, dass ihre Ergebnisse noch im selben Durchlauf in die Kategorie-Vorschläge einfließen. Ein zweiter, manuell angestoßener Lauf ist dafür nicht mehr nötig.
- [ ] Der bisherige Hinweis, dass Remote-Ergebnisse erst durch einen (ggf. erneuten) Bewertungslauf wirksam werden, entfällt — er ist durch die Verkettung gegenstandslos.
- [ ] Während des Durchlaufs ist erkennbar, welcher Teilschritt gerade läuft und wie weit er fortgeschritten ist.

**Cloud-Nutzung pro Durchlauf steuerbar**

- [ ] Unmittelbar beim Auslöser steht eine Checkbox, mit der die Cloud-Nutzung für genau diesen einen Durchlauf an- und abgewählt wird.
- [ ] Ist die Cloud-Bilderkennung in den Projekteinstellungen freigegeben, ist die Checkbox vorausgewählt aktiv. Fehlt die Freigabe, ist sie abgewählt und nicht setzbar, mit Verweis auf die Projekteinstellungen.
- [ ] Die Checkbox erteilt selbst keine Freigabe. Die grundsätzliche Einwilligung zur Cloud-Verarbeitung bleibt ausschließlich die Projekteinstellung.
- [ ] Ist die Checkbox abgewählt, findet im gesamten Durchlauf kein einziger Cloud-Aufruf statt — auch nicht die Sehenswürdigkeits-Erkennung, die heute innerhalb der Bewertung mitläuft.

**Kosten sichtbar vor dem Start**

- [ ] Die Kostenschätzung (betroffene Fotoanzahl und geschätzter Betrag) ist unmittelbar an der Checkbox sichtbar, bevor der Durchlauf gestartet wird.
- [ ] Die Schätzung umfasst alle Cloud-Anteile, die die Checkbox freigibt — nicht nur die Kategorie-Klassifizierung.
- [ ] Der bisherige Bestätigungsdialog vor der kostenpflichtigen Aktion entfällt; die Schätzung ersetzt ihn an Ort und Stelle.
- [ ] Erkennbar bleibt, dass es sich um eine Schätzung und keine exakte Abrechnung handelt.

**Fehlerverhalten**

- [ ] Scheitert ein Cloud-Anteil, wird der Fehler sichtbar gemeldet und der lokale Bewertungsanteil läuft trotzdem vollständig durch.
- [ ] Nach einem solchen Durchlauf ist erkennbar, dass das Ergebnis ohne Cloud-Anreicherung entstanden ist.

**Zutreffende Erklärtexte**

- [ ] Die Erklärtexte beschreiben den Durchlauf zutreffend. Die Aussage, die Bewertung laufe vollständig lokal auf diesem Server, gilt künftig nur noch bei abgewählter Cloud-Nutzung.

## Datenmodell-Bezug

Additiv, drei Spalten auf der bestehenden Tabelle `criterion_scoring_runs` (`models.py::CriterionScoringRun`), eine Alembic-Migration, keine Datenmigration nötig (alle drei sind nullable bzw. haben einen Server-Default):

| Spalte | Typ | Bedeutung |
|---|---|---|
| `phase` | `VARCHAR(20)`, nullable | Aktueller Teilschritt des Laufs: `remote_categories` / `criteria`. `NULL`, sobald der Lauf beendet ist (und bei allen Altzeilen). |
| `cloud_requested` | `BOOLEAN`, `NOT NULL`, Server-Default `false` | War die Cloud-Nutzung für diesen Lauf angefordert? Altzeilen erhalten `false` — für sie ist die Frage nachträglich nicht beantwortbar, und `false` ist die Antwort, die nichts Falsches verspricht. |
| `cloud_error_message` | `TEXT`, nullable | Menschenlesbare Zusammenfassung der Cloud-Probleme dieses Laufs; `NULL` = keine. |

Neuer Enum `models.py::ClassificationPhase` (`StrEnum`, Werte `remote_categories`/`criteria`), analog `CloudVisionPhase` als `SQLEnum(..., native_enum=False, length=20)` gespeichert.

`remote_category_classification_runs` bleibt unverändert und behält ihre eigenständige Bedeutung — sie ist ab dieser Spec der Datensatz der **ersten Phase** des verketteten Laufs statt eines eigenständig ausgelösten Laufs. `docs/architecture.md` wird entsprechend nachgezogen (Abschnitt Datenmodell + Pipeline-Beschreibung).

## Architektur / Umsetzung

Architektonischer Ansatz und Begründung vollständig in der neuen ADR [`decisions/0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md`](../decisions/0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md). Kurzfassung:

**1. Neuer Orchestrator `worker.py::run_classification`** führt beide Phasen in einem Job aus:

```
run_classification(session, project, scoring_run_id, cache_dir, use_cloud=…)
  1. CriterionScoringRun(status=RUNNING, cloud_requested=use_cloud,
                         phase=REMOTE_CATEGORIES if cloud_active else CRITERIA) anlegen
  2. wenn cloud_active: run_remote_category_classification(...)     # Phase 1
        failed -> deren error_message in cloud_error_message aufnehmen, NICHT abbrechen
  3. phase = CRITERIA
  4. run_criterion_scoring(..., run=<der Datensatz aus 1>, use_cloud=use_cloud)   # Phase 2
        └─ Landmark-Teilphase nur bei use_cloud
        └─ derive_photo_category liest die in Phase 1 geschriebenen Remote-Zeilen
  5. phase = NULL, status = SUCCESS/FAILED
```

`cloud_active := use_cloud and project.cloud_vision_detection_enabled`.

**2. Cloud-Gate.** `run_criterion_scoring` bekommt einen keyword-only Parameter `use_cloud: bool = False` (fail-closed). Die bestehende Landmark-Bedingung `if project.cloud_vision_detection_enabled and rows:` wird zu `if use_cloud and project.cloud_vision_detection_enabled and rows:` — bei abgewählter Checkbox wird `build_landmark_client` gar nicht erst aufgerufen (dieselbe Muss-Eigenschaft, die der Consent-Schalter schon hatte). `run_remote_category_classification` bleibt unverändert; der Orchestrator ruft sie bei abgewählter Cloud-Nutzung schlicht nicht auf, es entsteht dann auch kein `RemoteCategoryClassificationRun`.

**3. Laufweite Cloud-Fehlermeldung.** `cloud_error_message` wird aus bis zu drei Teilen zusammengesetzt (Leerzeichen-getrennt, in dieser Reihenfolge):
1. Phase 1 `failed` → `"Remote-Kategorisierung fehlgeschlagen: <error_message>"`.
2. Landmark-Client nicht konstruierbar → `"Sehenswürdigkeits-Erkennung nicht verfügbar (Initialisierung fehlgeschlagen)."` — dieser Fall war bisher vollständig stumm.
3. Einzelne Landmark-Aufrufe fehlgeschlagen → `"Sehenswürdigkeits-Erkennung: N von M Fotos fehlgeschlagen."` (Zähl-Zusammenfassung, keine N Einzelmeldungen; die Einzelfehler bleiben pro Foto über `photo_cloud_vision_errors`/ADR 0035 abrufbar).

`run_criterion_scoring` hängt die Teile 2/3 an einen bereits vorhandenen Wert an, statt ihn zu überschreiben.

**4. API (`api/projects.py`).**

| neu | ersetzt |
|---|---|
| `POST /projects/{id}/classify`, Body `{scoring_run_id: int, use_cloud: bool}` → `202` | `POST .../score-criteria`, `POST .../classify-categories-remote` |
| `GET /projects/{id}/classify/estimate` | `GET .../classify-categories-remote/estimate` |

Alte Endpunkte werden ersatzlos entfernt (genau ein Client, siehe ADR Punkt 5). Guards von `POST .../classify` — Reihenfolge unverändert übernommen von `score-criteria`, plus eine neue: Feature-Flag `403` → Projekt `404` → kein erfolgreicher `ScoringRun` `409` → Gate nicht bestätigt `409` → `scoring_run_id` veraltet `409` → **`use_cloud=true` ohne `cloud_vision_detection_enabled` `403`**.

Die Schätzung liefert zusätzlich zu den bisherigen Feldern `remote_category_candidate_count` und `landmark_candidate_count`; `candidate_count` ist deren Summe. Neue Hilfsfunktion `_count_landmark_candidates(session, project_id)`: Fotos des Projekts mit `PhotoScore.suggested_status IS NULL`, deren bereits gespeicherte `PhotoCriterionScore`-Werte `criteria.py::is_landmark_candidate` erfüllen und die noch keine `landmark`-Kriterien-Zeile haben. Bewusst dieselbe reine Funktion wie im Live-Lauf (kein zweiter, auseinanderlaufender Schwellwert). Der Endpunkt bleibt wie bisher **unabhängig vom Consent** aufrufbar (`200`, kein `403`) — die Kosten sollen vor der Consent-Entscheidung sichtbar sein.

**5. Frontend.** Neue Komponente `components/ClassificationSection.tsx` ersetzt `components/RemoteCategoryClassificationSection.tsx` (wird gelöscht) **und** die bisher inline in `pages/pipeline/KriterienStepPage.tsx` liegende Kriterien-Bewertungs-Sektion. `KriterienStepPage.tsx` rendert danach nur noch diese eine Sektion. Die Feinlabel-Häufigkeitsliste (Spec 0289) zieht unverändert mit in die neue Komponente um.

Neues UI-Primitiv `components/ui/checkbox.tsx` (natives `<input type="checkbox">`, siehe UI/UX). `hooks/useProjects.ts`: `useTriggerScoreCriteriaMutation`/`useTriggerClassifyCategoriesRemoteMutation` → `useTriggerClassificationMutation(id)` mit Argument `{scoringRunId, useCloud}`; `useClassifyCategoriesRemoteEstimateQuery` → `useClassificationEstimateQuery`. `api/projects.ts`/`api/types.ts` entsprechend.

**Betroffene Dateien:**

- `backend/src/photosort/models.py` — `ClassificationPhase`, drei Spalten auf `CriterionScoringRun`.
- `backend/alembic/versions/<rev>_classification_run_cloud_phase.py` — neue Migration (down_revision = aktueller Head).
- `backend/src/photosort/worker.py` — `run_classification` (neu), `run_criterion_scoring` (`run`/`use_cloud`-Parameter, Landmark-Gate, Fehlerzusammenfassung), Job-Registrierung `classify` statt `score_criteria`/`classify_categories_remote`.
- `backend/src/photosort/api/projects.py` — `POST /classify`, `GET /classify/estimate`, `_count_landmark_candidates`, erweitertes `CriterionScoringRunSummary`; alte Endpunkte entfernt.
- `frontend/src/api/types.ts`, `frontend/src/api/projects.ts`, `frontend/src/hooks/useProjects.ts`.
- `frontend/src/components/ClassificationSection.tsx` (neu), `frontend/src/components/ui/checkbox.tsx` (neu), `frontend/src/components/RemoteCategoryClassificationSection.tsx` (gelöscht).
- `frontend/src/pages/pipeline/KriterienStepPage.tsx`.
- `docs/architecture.md`, `specs/architecture/0004-design-system.md`.
- Tests: siehe Teststrategie.

**Umsetzungsreihenfolge (TDD, rot vor grün):** Modell/Migration → Worker-Verkettung + Cloud-Gate → API → Frontend-Primitiv → Frontend-Sektion → Doku.

## UI/UX

Sichtbare Oberfläche: ja. Die Kriterien-Seite (`/projects/:id/pipeline/kriterien`) zeigt statt bisher zwei Sektionen nur noch **eine**: "Klassifizierung".

**Aufbau von oben nach unten:**

1. `<h2>Klassifizierung</h2>`
2. Erklärtext, der den Lauf zutreffend beschreibt: bewertet jedes verbleibende Foto nach mehreren Kriterien und leitet daraus Kategorie und Rangfolge ab. Die frühere Absolut-Aussage "läuft vollständig lokal auf diesem Server" wird an die Checkbox gebunden und erscheint als eigener, **zustandsabhängiger** Satz: bei abgewählter Checkbox "Dieser Durchlauf läuft vollständig lokal auf diesem Server — kein Foto verlässt ihn.", bei angewählter "Dieser Durchlauf sendet Fotos an <Provider> (Kategorie-Vorschläge und Sehenswürdigkeits-Erkennung)."
3. **Checkbox-Zeile** — das neue Bedienelement, unmittelbar über dem Auslöser:
   - Label "Cloud-Bilderkennung für diesen Durchlauf nutzen".
   - Vorbelegung = `project.cloud_vision_detection_enabled`; ohne Freigabe `disabled` **und** abgewählt, mit direkt darunter stehendem Verweis "Cloud-Bilderkennung ist für dieses Projekt nicht aktiviert. In den Projekteinstellungen aktivieren" (bestehender Link, unverändert übernommen).
   - Während eines laufenden Durchlaufs `disabled` (der Wert ist für den laufenden Durchlauf bereits entschieden).
   - Unmittelbar an der Checkbox, sichtbar nur bei angewählter Checkbox: die Schätzung `~N Fotos · ~$X` plus die dauerhaft sichtbare Relativierung "Schätzung, keine exakte Abrechnung." Bei `candidate_count === 0`: "Alle Fotos bereits klassifiziert". Solange die Schätzung lädt bzw. nicht ladbar ist: kein Betrag (und der Auslöser bleibt bei angewählter Checkbox deaktiviert — "kein Bypass", bestehende Regel aus Spec 0055).
4. Auslöse-Button "Klassifizierung starten" (Busy-Muster: "Wird klassifiziert…"), **ohne** vorgeschalteten Dialog.
5. Statuszeile (`StatusDot` + Text, `aria-live="polite"`) mit **Teilschritt-Benennung**, gespeist aus `phase`: "Remote-Kategorisierung läuft…" / "Kriterien-Bewertung läuft…".
6. Fortschritt des jeweils laufenden Teilschritts — bestehendes Muster (`<progress>` + "X von Y Fotos verarbeitet" + auf Zehnerschritte gedrosselte `aria-live`-Prozentansage). Die Zahlen stammen bei `phase === 'remote_categories'` aus `last_remote_category_classification_run`, sonst aus `last_criterion_scoring_run`.
7. Nach dem Lauf:
   - `cloud_error_message !== null` → `Alert` mit der Meldung, ergänzt um den Satz "Das Ergebnis ist ohne (vollständige) Cloud-Anreicherung entstanden." (deckt beide Fehler-Akzeptanzkriterien ab: Fehler sichtbar **und** Ergebnis-Charakter erkennbar).
   - `cloud_requested === false` bei erfolgreichem Lauf → neutraler Satz "Ohne Cloud-Anreicherung durchgeführt — die Cloud-Nutzung war für diesen Durchlauf abgewählt." Bewusst **kein** Fehler-Styling: das ist ein gewünschtes Ergebnis, keine Störung.
8. Feinlabel-Häufigkeitsliste (unverändert aus Spec 0289 übernommen).

**Neues Primitiv `components/ui/checkbox.tsx`:** natives `<input type="checkbox">` mit `accent-color`, keine neue Abhängigkeit — dieselbe Linie wie `switch.tsx`/`<dialog>` ("Radix-Primitives nur dort einsetzen, wo natives HTML nicht reicht"). Bewusst **kein** `Switch`: der `Switch` steht im Produkt bereits für die *dauerhafte* Projekteinstellung (`ProjectSettingsPage`), die Checkbox für eine *Einmal-Entscheidung dieses Durchlaufs*. Die unterschiedliche Optik ist hier ein Merkmal, kein Bruch — sie hält die beiden Bedeutungen auseinander, die die Story ausdrücklich getrennt wissen will. Touch-Ziel ≥ 44px über das umschließende `<label>` (`min-h-11`, Klick auf den Text schaltet mit), sichtbarer Fokusring wie bei den übrigen Bedienelementen.

**Design-System-Impact:** Der Eintrag "Bestätigungsdialog vor kostenpflichtiger Aktion" wird nachgezogen — er war seit Spec 0055 als Muster geführt und ist mit dieser Spec zurückgenommen: an seine Stelle tritt **"Dauerhaft sichtbare Kostenschätzung am Auslöser"**. Begründung im Dokument: ein Dialog zeigt die Kosten erst nach einem Klick und verschwindet wieder; eine ständig sichtbare Schätzung neben dem Freigabe-Schalter informiert früher und dauerhaft. Zusätzlich neuer Eintrag **"Checkbox für laufbezogene Freigabe neben Switch für Dauereinstellung"**. Ferner ein neuer Eintrag für die zustandsabhängige Datenschutz-Aussage: eine Zusicherung wie "verlässt diesen Server nicht" wird nie absolut formuliert, wenn sie von einem Bedienzustand abhängt, sondern an genau diesen Zustand gebunden.

## Security

Sicherheitsrelevant: ja — das Feature verändert das Gate eines produktiven Datenabflusses an einen externen Anbieter.

**Bedrohung 1 — die Laufeinstellung könnte die Einwilligung ersetzen.** Gegenmaßnahme: Das Gate ist eine reine Konjunktion `use_cloud AND project.cloud_vision_detection_enabled`, ausgewertet im Worker unmittelbar vor der Client-Konstruktion (für beide Cloud-Anteile). `use_cloud` kann damit nur *einschränken*, nie freigeben. Der Endpunkt weist `use_cloud=true` ohne Einwilligung zusätzlich mit `403` ab; diese Prüfung ist die sprechende Frührückmeldung, nicht das Sicherheitsnetz. Der Einwilligungs-Zustand selbst ist ausschließlich über `PUT .../cloud-vision-consent` änderbar — der neue Auslöser schreibt ihn nicht.

**Bedrohung 2 — stiller Datenabfluss bei abgewählter Checkbox.** Gegenmaßnahme: Bei `use_cloud=false` wird weder `build_landmark_client` noch `build_category_classification_client` aufgerufen; die Remote-Phase wird gar nicht erst betreten. Kein API-Key wird gelesen, keine Verbindung geöffnet. Der fail-closed-Default (`use_cloud: bool = False` in `run_criterion_scoring`) sorgt dafür, dass ein vergessener Parameter zu *weniger* statt zu mehr Datenabfluss führt. Explizit als Regressionstest abgesichert (siehe Teststrategie).

**Bedrohung 3 — irreführende Datenschutz-Zusicherung.** Die heutige Aussage "läuft vollständig lokal auf diesem Server" ist bei aktivem Consent unwahr und damit selbst ein Sicherheitsmangel (der Nutzer trifft Entscheidungen auf falscher Grundlage). Gegenmaßnahme: der Satz wird an den Checkbox-Zustand gebunden und erscheint nur noch, wenn er zutrifft.

**Bedrohung 4 — Fremdtext in der neuen Fehlermeldung.** `cloud_error_message` setzt sich aus `RemoteCategoryClassificationRun.error_message` (bereits an der Exception-Konstruktionsstelle sanitiert, ADR 0025/0031/0032/0034) und zwei fest codierten Textbausteinen mit eingesetzten Zählern zusammen — kein neuer, unsanitierter Kanal. Die Anzeige erfolgt als regulärer React-Textknoten, nie als HTML. Die bestehende Kappung auf 500 Zeichen der zugrundeliegenden Einzelmeldungen bleibt; die zusammengesetzte Meldung wird beim Schreiben ebenfalls defensiv gekappt.

**Keine Änderung** an: Auth (`get_current_user` gilt router-weit unverändert für die neuen Endpunkte), Datensichtbarkeit zwischen den beiden Nutzern (Projekte sind weiterhin für beide gleich sichtbar, ADR 0003), an dem, was ein Cloud-Request enthält (weiterhin ausschließlich die auf 2048px begrenzte display-Cache-Variante, kein EXIF/GPS, kein Dateiname, kein Pfad).

## Teststrategie

`specs/architecture/0002-testkonzept.md` bleibt unverändert — kein neues externes System, kein neuer Testtyp, nur neue Fälle in bereits etablierten Ebenen.

**Backend-Unit/Worker (`backend/tests/test_worker*.py`):**
- Verkettung: bei `use_cloud=True` und gesetztem Consent läuft die Remote-Phase **vor** der Kriterien-Phase, und die in Phase 1 geschriebene Klassifikations-Zeile beeinflusst die Kategorie in `PhotoRanking` **desselben** Laufs (das ist das Kern-Akzeptanzkriterium und wird direkt am Ergebnis geprüft, nicht an einer Aufrufreihenfolge).
- Cloud-Gate (Muss-Kriterium): `use_cloud=False` bei **gesetztem** Consent → weder `build_client` noch `build_landmark_client` werden aufgerufen (Fake-Builder, der beim Aufruf fehlschlägt/zählt), kein `RemoteCategoryClassificationRun` entsteht, keine `landmark`-Kriterien-Zeile.
- `use_cloud=True` bei **fehlendem** Consent → ebenfalls kein Cloud-Aufruf (Konjunktion, nicht Disjunktion).
- Fehlerverhalten: Phase 1 schlägt fehl → Gesamtlauf endet `success`, `PhotoRanking`-Zeilen sind vollständig geschrieben, `cloud_error_message` enthält die Phase-1-Meldung.
- Landmark-Client nicht konstruierbar → `cloud_error_message` gesetzt, Lauf `success`.
- Einzelne Landmark-Aufrufe schlagen fehl → Zähl-Zusammenfassung in `cloud_error_message`, übrige Fotos vollständig bewertet.
- `phase` steht während Phase 1 auf `remote_categories`, nach dem Lauf auf `NULL`; `cloud_requested` spiegelt das Argument.

**Backend-API (`backend/tests/test_api_projects*.py`):**
- `POST /classify` — `202` im Normalfall, Job wird mit `use_cloud` enqueued; `403` Feature-Flag, `404` unbekanntes Projekt, `409` ohne erfolgreichen ScoringRun / ohne Gate / bei veralteter `scoring_run_id`, **`403` bei `use_cloud=true` ohne Consent**.
- `GET /classify/estimate` — Summe beider Anteile, Landmark-Anteil zählt nur Fotos über der Schwelle ohne bestehende `landmark`-Zeile, `200` auch ohne Consent, `candidate_count=0` → `estimated_cost_usd=0.0`.
- Regression: die drei alten Endpunkte antworten mit `404`/`405` (existieren nicht mehr).
- `ProjectOut.last_criterion_scoring_run` transportiert die drei neuen Felder.

**Frontend (`vitest` + Testing Library):**
- `ClassificationSection.test.tsx` (neu, trägt die Verhaltensmatrix): Checkbox vorausgewählt bei Consent / abgewählt+`disabled` ohne Consent (samt Einstellungs-Link); Schätzung nur bei angewählter Checkbox sichtbar, mit "Schätzung, keine exakte Abrechnung"; Auslösen ruft die Mutation mit `useCloud` genau entsprechend dem Checkbox-Zustand auf (beide Richtungen); **kein Bestätigungsdialog** (Negativ-Assertion, Regressionsschutz für das zurückgenommene Muster); Teilschritt-Text und Fortschrittszahlen je `phase`; `cloud_error_message` erscheint als Alert samt "ohne (vollständige) Cloud-Anreicherung"; neutraler Hinweis bei `cloud_requested === false`; Negativ-Assertion, dass der alte Hinweistext ("fließen erst durch einen … Bewertungs-Lauf ein") nirgends mehr vorkommt; Erklärtext wechselt mit dem Checkbox-Zustand; Feinlabel-Liste unverändert (Lade-/Leer-/Fehler-/Erfolgsfall).
- `checkbox.test.tsx` (neu): kontrollierte Semantik, `disabled`, Label-Klick schaltet.
- `KriterienStepPage.test.tsx`: nur noch eine Sektion; die bisherigen Inline-Tests der Kriterien-Bewertung wandern in `ClassificationSection.test.tsx`; Negativ-Assertion, dass keine zweite Auslöse-Schaltfläche mehr existiert.
- `useProjects.test.tsx`: neue Mutation/Query samt Invalidierung der Schätzung.
- `RemoteCategoryClassificationSection.test.tsx` wird mit der Komponente gelöscht.

**Was nicht neu getestet wird:** die Kandidaten-/Override-Mechanik am Foto, `resolve_category`/`derive_photo_category` selbst, die Label-Normalisierung, der Provider-Dispatch — alle unverändert und bereits abgedeckt.

## Entscheidungen

- **Neue ADR [`0050`](../decisions/0050-verketteter-klassifizierungslauf-mit-laufbezogener-cloud-freigabe.md):** Die Änderung kehrt eine dokumentierte Architekturentscheidung um (ADR 0032 Punkt 5/6: eigenständiger Job, zwei Auslöse-Endpunkte) und verschärft eine zweite (ADR 0025 Punkt 5: projektweiter Consent als alleiniges Gate) — beides ADR-pflichtig laut `CLAUDE.md`.
- **Kein FK zwischen den beiden Run-Tabellen:** beide Läufe entstehen im selben Job unmittelbar nacheinander; ein FK formalisierte eine Zuordnung, die nur für Altdaten uneindeutig war (ADR 0050 Punkt 3).
- **Keine vierte Run-Tabelle für den Gesamtlauf:** `criterion_scoring_runs` + `phase` beantwortet dieselben Fragen ohne eine dritte Kopie derselben fünf Statusfelder (ADR 0050 Punkt 3).
- **Alte Endpunkte ersatzlos entfernt statt deprecated:** genau ein Client; ein zweiter Auslöseweg wäre exakt der Zustand, den diese Spec beseitigt (ADR 0050 Punkt 5).
- **Landmark-Schätzung aus den Vorwerten des letzten Laufs:** strukturell eine Schätzung; vor dem ersten Lauf 0. Die Alternative (Landmark-Anteil nicht schätzen) hätte die Schätzung erneut unvollständig gelassen — genau der Mangel, den diese Spec behebt (ADR 0050 Punkt 5).
- **`use_cloud`-Default `False` in `run_criterion_scoring`:** fail-closed an einer Vertrauensgrenze, auch um den Preis, dass Bestandstests den Parameter explizit setzen müssen (ADR 0050 Punkt 2).
- **Checkbox statt `Switch`:** hält die Einmal-Entscheidung dieses Durchlaufs optisch von der Dauereinstellung in den Projekteinstellungen getrennt (UI/UX-Abschnitt).
- **Rücknahme eines Design-System-Musters statt stiller Abweichung:** "Bestätigungsdialog vor kostenpflichtiger Aktion" wird im Design-System ausdrücklich zurückgenommen und ersetzt, nicht im Code unterlaufen.
- **Fachagenten in dieser Session nicht als Subagenten aufgerufen:** Die Architektur-, UI/UX-, Test- und Security-Abschnitte dieser Spec sind in der Hauptsession erarbeitet worden, weil die Ausführungsumgebung dieses Laufs den Einsatz von Subagenten untersagt. Inhalt und Umfang der Abschnitte entsprechen dem, was der jeweilige Ablauf verlangt; die Zuständigkeitszuordnung des `spec-writer`-Skills ist damit prozedural, nicht inhaltlich abgewichen.

## Offene Fragen

Keine — das Refinement-Gespräch (Issue #296, Story vollständig ausformuliert inkl. Restrisiko-Abwägung) und die technischen Festlegungen in dieser Spec/ADR 0050 haben alle Unklarheiten geklärt.

## Out of Scope

- Scan und Ausschuss-Erkennung bleiben eigenständige, getrennt ausgelöste Schritte der Pipeline.
- Die Kategorie-Kuratierung sowie das Übernehmen/Ablehnen einzelner erkannter Kategorien an einem Foto bleiben unverändert.
- Issue #297 (Sehenswürdigkeits-Erkennung als eigener Auslöser mit eigener Kostenschätzung) bleibt eine eigenständige Story. Diese Spec steuert die Sehenswürdigkeits-Erkennung nur mit über die Cloud-Checkbox, gibt ihr aber keinen eigenen Auslöser.
- Ein Abbrechen eines laufenden Durchlaufs, ein erneutes Ausführen nur einer Phase, sowie jede Änderung an Provider-Auswahl, Preistabelle oder Prompt.
