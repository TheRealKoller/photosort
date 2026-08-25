# 0058 - Cloud-Vision-Status-Transparenz in den Foto-Details

**Status:** Accepted
**Erstellt:** 2026-08-24
**Bezug:** [`inbox/0032-cloud-status-transparenz-foto-details.md`](../inbox/0032-cloud-status-transparenz-foto-details.md) (Ursprung, Daniel selbst, 2026-08-21), [`decisions/0035-cloud-vision-attempt-fehler-persistierung.md`](../decisions/0035-cloud-vision-attempt-fehler-persistierung.md) (neue ADR dieser Spec), [`features/0056-structured-logging-cloud-vision-errors.md`](./0056-structured-logging-cloud-vision-errors.md)/[`decisions/0034-strukturiertes-logging-cloud-vision-fehler.md`](../decisions/0034-strukturiertes-logging-cloud-vision-fehler.md) (paralleles, komplementäres Logging derselben Fehlerfälle — Server-Log statt App-UI, sanitierte Fehlermeldungs-Konstruktion hier wiederverwendet), [`features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md`](./0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md)/[`decisions/0025-cloud-landmark-erkennung.md`](../decisions/0025-cloud-landmark-erkennung.md) (Landmark-Lauf), [`features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](./0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md)/[`decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md`](../decisions/0032-remote-kategorie-klassifizierung-mit-kostenschaetzung.md) (Remote-Kategorie-Lauf, gemeinsamer Consent-Schalter), [`features/0041-bewertungsdetails-permanent-detailansicht.md`](./0041-bewertungsdetails-permanent-detailansicht.md) (bestehende permanente Detail-Sektion, an die diese Spec anknüpft)

## Ziel

Es gibt zwei Cloud-Vision-Läufe (Landmark-Erkennung, Remote-Kategorie-Klassifizierung), deren Ergebnis pro Foto bislang in der Foto-Detailansicht nicht durchgängig nachvollziehbar ist: Landmark-Ergebnisse werden laut ADR 0025 gar nicht angezeigt, Remote-Kategorie-Ergebnisse nur als Kategorie-Kandidat, aber ohne Unterscheidung zwischen "noch nie versucht", "kein Kandidat", "Consent aus" und "Fehler beim letzten Versuch". Diese Spec macht für jedes Foto und beide Läufe einen von sechs Zuständen sichtbar, damit Daniel direkt in der App nachvollziehen kann, warum ein erwartetes Ergebnis fehlt, ohne in Server-Logs nachsehen zu müssen.

## User Story

Als Betreiber der PhotoSort-Installation möchte ich in der Foto-Detailansicht für jedes Foto sehen, ob ein Cloud-Vision-Lauf (Landmark-Erkennung, Remote-Kategorie-Klassifizierung) stattgefunden hat — und falls nicht, warum nicht (kein Kandidat, Consent deaktiviert, noch kein Lauf) bzw. bei einem Fehler die Fehlermeldung —, damit ich fehlende Ergebnisse einordnen kann, ohne in `docker compose logs` nachsehen zu müssen.

## Akzeptanzkriterien

**Datenmodell:**
- [ ] Neue Migration: Tabelle `photo_cloud_vision_errors` (`photo_id` FK, `phase: CloudVisionPhase` [neuer Enum `landmark`/`remote_category`], `error_type: str`, `error_message: str` [max. 500 Zeichen, gekappt], `attempted_at: datetime`), composite Primary Key `(photo_id, phase)` — kein Verlauf, ein neuer Fehlschlag überschreibt (Upsert) den vorigen, ein erfolgreicher Retry löscht die Zeile.
- [ ] `Photo.cloud_vision_errors`-Relationship, `cascade="all, delete-orphan"`.

**Ableitungslogik (Read-Time, kein voller Status pro Foto persistiert):**
- [ ] Für jede der beiden `CloudVisionPhase` wird genau einer von 5 Rängen angezeigt, in dieser Reihenfolge geprüft (erster zutreffender Rang gewinnt, kein Merge mehrerer gleichzeitig zutreffender Signale):
  1. Erfolgssignal vorhanden (Landmark: `PhotoLandmarkDetection`-Zeile → `result`; sonst `PhotoCriterionScore(criterion_key="landmark")`-Zeile ohne `PhotoLandmarkDetection` vorhanden → `no_result`; Remote-Kategorie: mindestens eine `PhotoCategoryDetection`-Zeile → `result`, keinen `no_result`-Fall, siehe ADR 0032)
  2. sonst: `PhotoCloudVisionError`-Zeile für diese Phase vorhanden → `error`
  3. sonst: `project.cloud_vision_detection_enabled == False` → `consent_disabled`
  4. sonst: Kandidaten-Prüfung schlägt fehl (`criteria.py::is_landmark_candidate(...)` bzw. kein `PhotoScore` oder `suggested_status` gesetzt) → `not_candidate`
  5. sonst → `not_run`
- [ ] Explizit bindend (Überschneidungsfälle): `consent_disabled` UND `not_candidate` gleichzeitig zutreffend → `consent_disabled` gewinnt. `error` UND Consent inzwischen deaktiviert → `error` bleibt bestehen. `result`/`no_result` UND Consent nachträglich deaktiviert → `result`/`no_result` bleibt bestehen. Ein aussortiertes Foto oder ein Foto ganz ohne `PhotoScore`-Zeile → `not_candidate`, nicht `not_run`, für beide Phasen.
- [ ] Neue reine Funktion `criteria.py::is_landmark_candidate(values: dict[str, float]) -> bool`, extrahiert aus `worker.py::_select_landmark_candidates` — von Live-Lauf UND API-Ableitung gemeinsam genutzt (kein Auseinanderlaufen bei künftiger Schwellenwert-Änderung).

**Worker-Verdrahtung:**
- [ ] Neue Helfer `worker.py::_record_cloud_vision_error(session, photo_id, phase, exc, now)` / `_clear_cloud_vision_error(session, photo_id, phase)`.
- [ ] Vier neue Call-Sites: Landmark-Fehlerpfad (`run_criterion_scoring`, vor dem bestehenden `continue`) und Landmark-Erfolgspfad (nach `_upsert_criterion(..., "landmark", ...)`); Remote-Kategorie-Fehlerpfad und -Erfolgspfad (`run_remote_category_classification`).
- [ ] Bewusst getrennt von Spec 0056s `_log_cloud_vision_failure`-Logging-Helfer (Logging bleibt synchron/ephemer, Persistierung ein eigener async Vorgang mit Lösch-Pfad bei Erfolg) — beide teilen sich dieselben, einmal berechneten `type(exc).__name__`/`str(exc)`-Werte, keine doppelte Auswertung.
- [ ] `error_message` wird beim Schreiben auf 500 Zeichen gekappt.

**API:**
- [ ] Kein neuer Endpunkt: additives `PhotoOut.cloud_vision_status: list[CloudVisionStatusOut]`, immer genau 2 Einträge in fester Reihenfolge `[landmark, remote_category]` (unabhängig von DB-/Insert-Reihenfolge). `CloudVisionStatusOut{phase, status, error_message, attempted_at}`, neuer Enum `CloudVisionStatus` (`not_run`/`not_candidate`/`consent_disabled`/`error`/`no_result`/`result`).
- [ ] Neue Funktion `api/photos.py::_cloud_vision_status_out(photo, project)` wendet die Priorisierung an.
- [ ] `_photos_by_id`/die photoausliefernde Query bekommt zusätzliches `selectinload(Photo.cloud_vision_errors)`.

**Frontend:**
- [ ] Neue Komponente `components/CloudVisionStatusList.tsx` (reine Präsentationskomponente, analog `CriterionDetailsList`), Props: `cloudVisionStatus: CloudVisionStatusOut[]`.
- [ ] Neue permanente Sektion in `PhotoDetailPage.tsx`, platziert nach den Bewertungs-Buttons, vor der bestehenden `CriterionDetailsList`. Immer sichtbar (kein Ausblenden bei `not_candidate`/`not_run` — bewusste Stakeholder-Entscheidung, siehe "Entscheidungen").
- [ ] Jeder der 6 Zustände bekommt Icon + Text-Label (nie nur Farbe): `not_run`/`not_candidate`/`consent_disabled` neutral (`text-text`), `error` mit `text-status-failed` + Warnsymbol, `no_result`/`result` mit `text-status-success` + Haken. Bestehende Design-System-Tokens (`--status-success`/`--status-failed`), keine neuen Farbwerte.
- [ ] Bei `error`: `error_message` (gekürzt gerendert, max. 500 Zeichen laut Backend-Kappung) und `attempted_at` inline unter dem Status sichtbar, reiner Text-Knoten (kein `dangerouslySetInnerHTML`).
- [ ] Icons `aria-hidden`, Status niemals ausschließlich über Farbe kommuniziert.

**Sicherheit:**
- [ ] `error_message` wird im Frontend ausschließlich über einen regulären React-Textknoten gerendert, nie `dangerouslySetInnerHTML`.
- [ ] Vor Implementierung wird verifiziert, ob `str(exc)` bei einem von `httpx.HTTPError` gewrappten Netzwerkfehler (`LandmarkApiError`/`RemoteCategoryClassificationApiError`) URL-Query-Parameter enthalten könnte (Nachschärfung von ADR 0034 Punkt 5, da die Zielgruppe der Fehlermeldung jetzt vom Server-Log-Leser zum App-Nutzer wächst).

**Tests/Doku:**
- [ ] Migrationstest (`inspect()`, Composite-PK, Cascade bei Projekt-Löschung).
- [ ] `docs/architecture.md`-Ergänzung im selben PR.

## Datenmodell-Bezug

Neue Tabelle `photo_cloud_vision_errors` (siehe Akzeptanzkriterien/ADR 0035), neuer Enum `CloudVisionPhase`. Keine Änderung an bestehenden Tabellen. Migration additiv, kein Backfill nötig (Bestandsfotos ohne Zeile werden korrekt über die Ableitungslogik als `not_run`/`not_candidate` angezeigt).

## Architektur / Umsetzung

Siehe [`decisions/0035-cloud-vision-attempt-fehler-persistierung.md`](../decisions/0035-cloud-vision-attempt-fehler-persistierung.md) (Accepted, neue ADR) für die vollständige Begründung. Zusammenfassung:

**Zentraler Befund:** Nur der Fehlschlag-Fall ist heute tatsächlich unsichtbar. "Erfolgreich, nichts gefunden" hinterlässt bei Landmark bereits eine `PhotoCriterionScore(criterion_key="landmark")`-Zeile ohne `PhotoLandmarkDetection` (Code-verifiziert); bei Remote-Kategorie gibt es diesen Fall laut ADR 0032 nicht (Erfolg schreibt immer 1-3 Zeilen). Consent/Kandidat/Erfolg sind bereits aus `Project.cloud_vision_detection_enabled`, den lokalen `PhotoCriterionScore`-Schwellenwerten bzw. `PhotoScore.suggested_status` ableitbar — deshalb reicht eine schlanke, ausschließlich fehlschlagbezogene Tabelle statt eines vollen Status-Enums pro Foto×Lauf-Typ.

- **Neue Migration:** Tabelle `photo_cloud_vision_errors` (`photo_id`, `phase` [Enum `CloudVisionPhase`], `error_type`, `error_message`, `attempted_at`), composite PK `(photo_id, phase)`, kein Verlauf.
- **`models.py`:** neue Klasse `PhotoCloudVisionError`, neuer Enum `CloudVisionPhase`, neue `Photo.cloud_vision_errors`-Relationship (`cascade="all, delete-orphan"`).
- **`criteria.py`:** neue reine Funktion `is_landmark_candidate(values: dict[str, float]) -> bool`, extrahiert aus der bisher inline in `worker.py::_select_landmark_candidates` liegenden Schwellenwert-Prüfung.
- **`worker.py`:** zwei neue Helfer `_record_cloud_vision_error`/`_clear_cloud_vision_error` (analog `_upsert_landmark_detection`, reines `add`/`delete`, kein eigener Commit). Vier neue Call-Sites in `run_criterion_scoring`/`run_remote_category_classification`. Neue Modul-Konstante `_MAX_PERSISTED_CLOUD_VISION_ERROR_MESSAGE_LENGTH = 500`. Bewusst getrennt von Spec 0056s Logging-Helfer, geteilte, einmal berechnete Exception-Werte.
- **API (`api/photos.py`):** kein neuer Endpunkt. Additives `PhotoOut.cloud_vision_status`, neue Funktion `_cloud_vision_status_out(photo, project)`, `selectinload(Photo.cloud_vision_errors)`.
- **Empfohlene Umsetzungsreihenfolge:** (1) Migration + Datenmodell, (2) `criteria.py::is_landmark_candidate` inkl. Umstellung von `_select_landmark_candidates`, (3) die vier `worker.py`-Call-Sites (TDD über bestehende Fehlerfall-Tests), (4) `api/photos.py`-Erweiterung, (5) Frontend (`CloudVisionStatusList.tsx` + Einbindung), (6) `docs/architecture.md`-Ergänzung im selben PR.
- **Betroffene/neue Dateien:** `backend/src/photosort/models.py`, `backend/src/photosort/criteria.py`, `backend/src/photosort/worker.py`, `backend/src/photosort/api/photos.py`, neue Alembic-Migration, `frontend/src/pages/PhotoDetailPage.tsx`, neu `frontend/src/components/CloudVisionStatusList.tsx`.

## UI/UX

**Sichtbare Oberfläche:** Ja — neue, permanente Sektion in der Foto-Detailansicht.

**Layout & Platzierung:** Neue Sektion "Cloud-Vision-Status" unmittelbar nach den Bewertungs-Buttons (`RatingButtons`), vor der bestehenden `CriterionDetailsList`. Begründung: Bewertungs-Aktion bleibt primäres Interaktionselement oben; Cloud-Status ist Meta-Information über die Verfügbarkeit von Remote-Analysedaten, konzeptuell Teil der "Details"-Ebene; die Remote-Kategorie-Klassifizierung ist selbst ein Cloud-Vision-Lauf und gehört inhaltlich neben ihre eigenen Kategorie-Details.

**Format:** `<dl>`-Struktur analog `CriterionDetailsList`, zwei Zeilen (eine je Phase: "Landmark-Erkennung"/"Remote-Kategorie"), `text-sm text-text`, kein Card-Rahmen, dezent — konsistent mit "Die Fotos sind der Star".

**Sichtbarkeit:** Immer, für jedes Foto — bewusste Stakeholder-Entscheidung (siehe "Entscheidungen"), kein bedingtes Ausblenden bei irrelevanten Fotos.

**Sechs Zustände, sechs visuelle Behandlungen (nie nur Farbe, immer Icon + Text):**
- `not_run` — neutral, "Noch nicht verarbeitet".
- `not_candidate` — neutral, "Nicht als Kandidat qualifiziert".
- `consent_disabled` — neutral, "Cloud-Erkennung deaktiviert".
- `error` — `text-status-failed` + Warnsymbol, "Fehler beim Versuch"; darunter inline `error_message` (`text-xs`) und `attempted_at`.
- `no_result` (nur Landmark) — `text-status-success` + Haken, "Erfolgreich, keine Treffer".
- `result` — `text-status-success` + Haken, "Ergebnis vorhanden".

**Fehlerbehandlung:** `error_message` wird inline, dezent, rein textlich dargestellt (kein Alert-Banner, kein Modal) — Farbe des Icons reicht als Warn-Signal, kein zusätzlicher farbiger Hintergrund, konsistent mit der zurückhaltenden Metadaten-Gestaltung des Projekts.

**Design-System-Bezug:** Nutzt bestehende Status-Semantik (`--status-success`/`--status-failed`, bereits in `PhotoGridPage`/`PhotoComparePage`/`Stepper.tsx` etabliert), keine neuen Farb-Tokens. Icons `aria-hidden`, Text-Labels selbsterklärend — keine Information ausschließlich über Farbe.

## Security

Sicherheitsrelevant, aber eng begrenzt (`security-engineer`-Konsultation, 2026-08-24) — kein neuer Endpunkt, keine neue Auth-Logik. `PhotoOut.cloud_vision_status[]` hängt am bereits `get_current_user`-geschützten `GET /projects/{id}/photos`.

**Verschiebung Log (Spec 0056) → API bewusst geprüft, kein neues Risiko:** Die Fehlerdaten stammen aus denselben, bereits sanitierten `except`-Blöcken wie Spec 0056 (`type(exc).__name__`+`str(exc)`, ADR 0034 Punkt 5 verifiziert — nur Statuscode/Reason-Phrase, nie Rohdaten/Secrets/Traceback). Die App kennt laut `decisions/0003-auth-model.md` kein Rollenmodell — beide geseedeten Nutzer sehen ohnehin dieselben Projekt-/Fotodaten. Der neue API-Empfängerkreis deckt sich exakt mit der bereits als vertrauenswürdig geführten Zwei-Personen-Basis ("kein Innentäter-Modell") — keine neue Sichtbarkeitsasymmetrie zwischen den beiden Nutzern. Kein Sicherheitsproblem, allenfalls ein UX-Punkt (technische Fehlerdetails könnten für eine Nutzerin ohne technisches Interesse unverständlich wirken).

**500-Zeichen-Kappung ist Storage-/Degenerationsgrenze, keine Sanitisierungsmaßnahme** — die eigentliche Absicherung bleibt die in ADR 0034 verifizierte `str(exc)`-Konstruktion. Da die Zielgruppe der Fehlermeldung jetzt vom Server-Log-Leser zum App-Nutzer wächst, wird der in ADR 0034 offen gelassene Punkt (ob `str(exc)` bei einem gewrappten `httpx.HTTPError` URL-Query-Parameter enthalten könnte) jetzt als Muss-Kriterium bei Implementierung verifiziert (siehe Akzeptanzkriterien).

**Frontend-Rendering:** `error_message` ausschließlich über regulären React-Textknoten, nie `dangerouslySetInnerHTML` — erste Stelle im Projekt, an der ein roher, aus einer Exception stammender String direkt an die UI durchgereicht wird, defense in depth trotz aktuell unbedenklichem Inhalt.

**DoS-/Storage-Aspekt:** unproblematisch — composite PK `(photo_id, phase)`, kein Verlauf, Upsert/Löschung statt Anhäufung, Zeilenzahl strukturell auf max. `2 × Anzahl Fotos` begrenzt, kein von außen/durch einen App-Nutzer direkt auslösbarer Schreibpfad (Zeilen entstehen ausschließlich im bereits dokumentierten Worker-Kontext).

`specs/architecture/0003-securitykonzept.md` wurde im Rahmen dieser Konsultation bereits ergänzt (neuer projektweiter Grundsatz: operative, ursprünglich für Logs gedachte Diagnosedaten dürfen nur dann zusätzlich per API exponiert werden, wenn sie bereits an der Quelle nach der ADR-0034-Disziplin sanitiert sind).

## Teststrategie

`specs/architecture/0002-testkonzept.md` wurde bereits im Rahmen dieser Konsultation ergänzt (neue Sektion "Read-Time-Prioritäts-Kaskade über zwei Phasen + Fehlschlag-only-Persistenz mit Lösch-bei-Erfolg" — erstmals eine geordnete 5-Zweige-Prioritäts-Kaskade und erstmals eine Composite-PK-Upsert-Tabelle mit explizitem Lösch-bei-Erfolg-Pfad im Projekt).

**Testebenen:**
- **Unit** (`test_criteria.py`): `is_landmark_candidate` — Grenzfälle an `category_presence_threshold` (`>=`), leeres Dict → `False`.
- **Integration, In-Memory-SQLite** (`test_api_photos.py`, neue Sektion): `_cloud_vision_status_out` — vollständige Prioritäts-Kombinationsmatrix (siehe Akzeptanzkriterien), Landmark `no_result`/`not_run`-Abgrenzung, Datenanomalie-Regressionstest (Score>0 ohne Detection-Zeile → dennoch `no_result`).
- **Integration, In-Memory-SQLite** (`test_worker_criterion_scoring.py`/`test_worker_remote_category_classification.py`): `_record_cloud_vision_error`/`_clear_cloud_vision_error` — Upsert bei wiederholtem Fehlschlag, 500/501-Zeichen-Kappungsgrenze, tatsächliches Löschen der Fehler-Zeile bei Erfolg (eigener DB-Zustands-Test, unabhängig von der API-Sichtbarkeit).
- **Migration/Schema** (`test_models.py`): additive Tabelle + Composite-PK per `inspect()`, Cascade-Test bei Projekt-Löschung.
- **Frontend** (`vitest`/Testing Library): alle 6 Zustände mit Icon+Text, Fehlermeldung inline nur bei `error`, permanente Sichtbarkeit unabhängig vom Rating, gemischter Zustand beider Phasen gleichzeitig.

**Relevante Edge Cases:**
- Fehler → erfolgreicher Retry: Fehler-Zeile wird tatsächlich gelöscht.
- Mehrere `PhotoCategoryDetection`-Zeilen desselben Fotos mit potenziell unterschiedlichem `computed_at` (defensiv `max()`).
- Verwaiste Fehler-Zeile trotz vorhandenem Erfolgssignal — Kaskade muss trotzdem korrekt `result` liefern.
- `PhotoOut`-Serialisierungstests mit exaktem Dict-Vergleich brechen durch das neue Pflichtfeld — Retrofit-Pflicht.

## Entscheidungen (2026-08-24, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Beide Cloud-Vision-Läufe im Scope:** Daniel hat sich für Landmark-Erkennung UND Remote-Kategorie-Klassifizierung entschieden, nicht nur den (aktuell bereits teilweise sichtbaren) Remote-Kategorie-Lauf — konsistente Behandlung beider Fälle.
- **Neuer, persistierter Fehlerstatus statt grober Unterscheidung:** Daniel hat sich für die genauere Variante entschieden — die Recherche zeigte, dass "erfolgreich, nichts gefunden" von "noch nie versucht" bzw. "Fehler beim letzten Versuch" ohne neue Persistierung nicht unterscheidbar wäre.
- **Immer sichtbar, auch bei Nicht-Kandidaten:** Daniel wurde die Konsequenz gespiegelt (die große Mehrheit aller Fotos war nie Kandidat für einen der beiden Läufe, würde also dauerhaft `not_candidate`/`not_run` zeigen) und hat sich trotzdem für "immer sichtbar" entschieden — bewusstes Inkaufnehmen von Rauschen bei nicht-relevanten Fotos zugunsten von Konsistenz/Vorhersagbarkeit ("ich möchte das immer sehen").
- **Schlanke Persistenz statt vollem Status-Enum pro Foto×Lauf-Typ:** `architect` hat den ursprünglichen Entwurf von `requirements-engineer` (volle Status-Tabelle mit 6 Werten pro Foto×Lauf-Typ) durch Code-Verifikation vereinfacht — nur der Fehlschlag-Fall ist tatsächlich neu; alle anderen Zustände werden zur Anfragezeit aus bereits vorhandenen Signalen abgeleitet. Deutlich kleinerer Eingriff als ursprünglich skizziert.
- **Neue ADR 0035:** von `architect` als nötig eingeschätzt (neues Datenmodell-Muster: fehlschlag-only-Persistenz mit Read-Time-Prioritätskaskade), nicht Anhängsel an eine bestehende ADR.
- **Bewusst getrennt von Spec 0056s Logging-Helfer:** zwei unabhängige Schreibvorgänge (ephemeres Log vs. persistierter, lösch-fähiger Zustand) statt eines gemeinsamen Mechanismus — von `architect` begründet, geteilte Exception-Auswertung vermeidet aber doppelte Arbeit.
- **httpx-Query-Parameter-Verifikation als neues Muss-Kriterium:** `security-engineer` hat den in ADR 0034 offen gelassenen Punkt hochgestuft, weil sich die Zielgruppe der Fehlermeldung durch diese Spec vom Server-Log-Leser zum App-Nutzer erweitert.

## Offene Fragen

Keine — alle im Sharpening-Gespräch aufgetretenen Unklarheiten wurden mit Daniel geklärt (siehe Abschnitt "Entscheidungen").

## Out of Scope

- Verlauf/Historie fehlgeschlagener Versuche — nur der letzte Zustand wird persistiert.
- Manuelles erneutes Anstoßen eines einzelnen fehlgeschlagenen Fotos aus der Detailansicht heraus (bleibt beim bestehenden Mechanismus: nächster regulärer Lauf versucht es automatisch erneut).
- Änderung des best-effort-Fehlerverhaltens selbst (Retry-Strategie, Abbruchverhalten) — nur zusätzliche Sichtbarkeit.
- Aggregierte/projektweite Fehlerstatistik (z.B. "N Fotos mit Fehler") — nur Pro-Foto-Anzeige in der Detailansicht.
