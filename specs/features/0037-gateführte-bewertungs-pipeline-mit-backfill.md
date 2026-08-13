# 0037 - Gateführte Bewertungs-Pipeline mit Kriterien-Scoring und Kategorie-Kuratierung

**Status:** Accepted
**Erstellt:** 2026-08-13
**Bezug:** Idea-Sharpening-Gespräch mit Daniel am 2026-08-13. Ersetzt/fusioniert [`features/0003-automatic-best-photo-selection.md`](./0003-automatic-best-photo-selection.md) und [`features/0024-top-photo-selection-category-mix.md`](./0024-top-photo-selection-category-mix.md) (beide auf `Superseded` gesetzt, siehe dort). ADR [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](../decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md) (neu). Bezug zu [`features/0035-klassifizierung-qualitaet-inhalt-recherche.md`](./0035-klassifizierung-qualitaet-inhalt-recherche.md) (Recherche-Ergebnis in offenem PR #72) — die Wahl konkreter Kriterien und ihrer Quelle (lokal/Cloud) ist explizit **nicht** Teil dieser Spec, siehe "Out of Scope". Baut auf [`decisions/0019-job-lauf-heartbeat-watchdog.md`](../decisions/0019-job-lauf-heartbeat-watchdog.md) (Fortschritts-Watchdog) auf.

## Ziel

Die bisherige automatische Foto-Bewertung bestand aus zwei unabhängig auslösbaren, isolierten Schritten ("Ausschuss aussortieren", Spec 0003; "Top-Fotos auswählen", Spec 0024) ohne erzwungene Reihenfolge oder Qualitätssicherung dazwischen. Diese Spec ersetzt das durch einen durchgängigen, teils gateführten Prozess: Ausschuss wird erkannt und muss vom Nutzer einmal gesichtet werden, bevor die übrigen Fotos nach mehreren benannten Kriterien bewertet, geclustert/kategorisiert und als Top-N je Kategorie präsentiert werden — mit einem Nachrück-Mechanismus (Backfill), der beim Aussortieren eines Top-Fotos automatisch das nächstbeste Foto derselben Kategorie zeigt, ohne dass der Nutzer manuell nachfordern muss.

Das konkrete Kriterien-Set (scharf/unscharf, Landschaft, Mensch, Tier, Gebäude, Sehenswürdigkeit, Ästhetik, Goldener Schnitt, etc.) und ob einzelne Kriterien lokal-deterministisch, lokal per ML oder über eine Cloud-API berechnet werden, ist bewusst **nicht** Gegenstand dieser Spec — das entscheidet Daniel separat, nachdem die noch offene Recherche aus Spec 0035 (PR #72) vorliegt. Diese Spec liefert dafür ausschließlich die strukturelle Grundlage: ein erweiterbares Datenmodell für benannte Kriterien-Werte beliebiger Quelle, eine darauf aufbauende Rangfolgen-Bildung, sowie den gateführten Ablauf und die Kuratierungs-Oberfläche darum herum.

## User Story

Als Nutzer (Daniel oder seine Frau) möchte ich die Auswahl der besten Fotos eines Projekts als einen durchgängigen, geführten Prozess durchlaufen — erst den erkannten Ausschuss sichten, dann automatisch nach mehreren Kriterien bewertete und kategorisierte Top-Fotos angezeigt bekommen, mit der Möglichkeit, einzelne Fotos abzulehnen und sofort ein passendes Alternativ-Foto derselben Kategorie nachrücken zu sehen — damit ich ein zusammenhängendes, qualitätsgesichertes Kuratierungserlebnis habe statt zweier voneinander unabhängiger, isolierter Klicks.

## Akzeptanzkriterien

**Scan + Ausschuss-Erkennung (unverändert)**
- [ ] Scan (Spec 0036) und Ausschuss-Erkennung (`run_project_scoring`: Schärfe/Belichtung/Duplikat-Clustering, Zeitfenster-Clustering) sind inhaltlich unverändert gegenüber Spec 0003; bestehende Tests bleiben ohne Assertion-Anpassung grün.

**Ausschuss-Gate (neu, verpflichtend, projektweit)**
- [ ] `POST /projects/{id}/confirm-ausschuss-gate`: `409` ohne erfolgreichen `ScoringRun`; setzt bei vorhandenem erfolgreichem `ScoringRun` `gate_confirmed_at`; wiederholter Aufruf ist idempotent (kein Fehler, kein zweiter Effekt).
- [ ] Ein `ScoringRun` mit `suggestions_found == 0` (kein Ausschuss gefunden) setzt `gate_confirmed_at` selbst beim Jobabschluss automatisch — kein Blockieren mit leerer Liste. Ein nachfolgender expliziter `confirm-ausschuss-gate`-Aufruf bleibt trotzdem fehlerfrei möglich.
- [ ] Die Bestätigung ist **projektweit**, nicht personenbezogen (kein `user_id`-Bezug, konsistent mit `ScanRun`/`ScoringRun`/`CriterionScoringRun`): bestätigt einer der beiden Nutzer, ist der nächste Schritt für beide freigegeben.
- [ ] `POST /projects/{id}/score-criteria` vor Gate-Bestätigung (`gate_confirmed_at IS NULL`) wird mit `409` abgelehnt.
- [ ] Der Nutzer kann einzelne Ausschuss-Fotos während des Gates korrigieren (bestehender "Übernehmen"-Mechanismus bzw. manuelle Bewertungsänderung), muss das aber nicht — der Abschluss-Button ist unabhängig vom Bearbeitungsstand jeder einzelnen Kachel jederzeit klickbar (keine Einzelbestätigungspflicht pro Foto).

**Kriterien-Bewertung (generisches Datenmodell, Kriterien-Liste selbst außerhalb des Scopes)**
- [ ] Für ein Foto kann mindestens ein `PhotoCriterionScore` (`photo_id`, `criterion_key: str`, `value ∈ [0,1]`, `source`, `computed_at`) persistiert werden, ohne dass eine feste Kriterien-Liste im Datenmodell/Code verdrahtet ist — Nachweis der generischen Speicherung reicht, eine vollständige Kriterien-Liste ist explizit out of scope.
- [ ] `UniqueConstraint(photo_id, criterion_key)`: ein erneuter Kriterien-Lauf überschreibt (Upsert) den bestehenden Wert für dasselbe Paar, keine Historie/Duplikatzeile.
- [ ] Für dieses MVP werden konkret mindestens `sharpness`/`exposure` (transformiert aus bereits vorhandenen `PhotoScore`-Rohwerten, kein erneuter Bildzugriff) sowie mindestens zwei Inhalts-Kriterien (`content_people`/`content_landscape`, wiederverwendet aus `classification.py`) tatsächlich berechnet und geschrieben — konkreter Existenzbeweis der Pipeline, keine Erweiterung des fachlichen Kriterien-Umfangs gegenüber dem bisherigen Stand.
- [ ] `POST /projects/{id}/score-criteria` (ersetzt `/select-top`, kein `top_n_per_cluster`-Parameter mehr beim Start): `401` ohne Token, `409` ohne bestätigtes Gate, `409` bei veraltetem `scoring_run_id`-Bezug (siehe Edge Cases).
- [ ] Ein einzelner fehlgeschlagener Kriterien-Berechnungsversuch pro Foto bricht den Lauf nicht ab (best-effort, analog Spec 0003/0024); das betroffene Foto behält die übrigen erfolgreich berechneten Kriterien, das fehlgeschlagene Kriterium bleibt ungeschrieben (kein Platzhalterwert wie `0`).

**Cluster × Kategorie, Rangfolge**
- [ ] `category_key: str` (frei, nicht mehr fixes 3er-Enum) wird deterministisch aus den vorhandenen Inhalts-Kriterien-Werten abgeleitet (feste Prioritätskette, analog zur bisherigen `classify_category`-Kette).
- [ ] `ranking.py::rank_photos` ist eine reine, DB-freie Funktion; fehlt einem Kandidaten eines der in `weights` genannten Kriterien, wird das Gewicht auf die tatsächlich vorhandene Teilmenge renormiert statt das fehlende Kriterium stillschweigend mit `0` zu werten. Tie-Break bei gleichem `rank_score`: niedrigere `photo_id` gewinnt (Determinismus-Konvention aus Spec 0003/0024 fortgeführt).
- [ ] `photo_rankings` enthält für jede Partition (`cluster_key`×`category_key`) den **vollen** Kandidatenpool (nicht nur Top-N) mit fortlaufendem, 1-basiertem `rank_position` — Grundlage für Backfill.
- [ ] `POST /projects/{id}/score-criteria` mit einer `scoring_run_id`, die nicht mehr dem aktuell neuesten erfolgreichen `ScoringRun` entspricht (Re-Scan/Re-Scoring währenddessen), wird mit `409` abgelehnt; kein `CriterionScoringRun` wird angelegt; bestehende `Rating`-Zeilen und ein evtl. vorheriger, noch gültiger `photo_rankings`-Bestand bleiben unangetastet.

**Top-N je Partition + Backfill (neu)**
- [ ] `GET /projects/{id}/photos?top_n_per_category=N` liefert je Partition die besten N nach `rank_position`, serverseitig um vom aktuellen Nutzer `REJECTED`-bewertete Fotos gefiltert (`user_id` aus JWT, nie aus Query/Body) — ein von Nutzer A abgelehntes Foto bleibt für Nutzer B sichtbar, solange der es nicht selbst ablehnt.
- [ ] `top_n_per_category` ist serverseitig deklarativ begrenzt (`Field(ge=1, le=10)`, analog zum bestehenden `top_n_per_cluster`-Muster aus Spec 0024).
- [ ] Reicht der (gefilterte) Pool einer Partition nicht für N, werden weniger als N geliefert — kein Fehler, kein künstliches Auffüllen aus einer anderen Kategorie (Prinzip aus Spec 0024 fortgeführt, mit Daniel für den Backfill-Fall explizit bestätigt).
- [ ] Sortiert ein Nutzer ein sichtbares Top-Foto aus (`PUT /photos/{id}/rating status=REJECTED`, bestehender Endpunkt, kein neuer Mutationscode), liefert ein erneuter Abruf derselben Query automatisch das nächstbeste, bisher nicht gezeigte Foto **derselben Kategorie/desselben Clusters** — ohne dass irgendein Server-Code aktiv "nachrückt" (reiner Query-Effekt, kein Backfill-Endpoint).

**Migration**
- [ ] `PhotoScore.category`/`.local_quality_score` werden als Spalten gedroppt, Tabelle `top_selection_runs` gedroppt (erste nicht-additive Migration im Projekt); `ratings` und die verbleibenden `photo_scores`-Spalten (`sharpness`, `exposure`, `phash`, `duplicate_of`, `cluster_key`, `suggested_status`) bleiben unverändert erhalten.
- [ ] Ein zum Deploy-Zeitpunkt noch `RUNNING` befindlicher alter `TopSelectionRun` wird durch den Tabellen-Drop ersatzlos nicht mehr referenzierbar — dokumentiertes, akzeptiertes Verhalten (kein `Rating`-Datenverlust), kein stiller Fehlerzustand für den Nutzer.

**Export**
- [ ] Export ist explizit nicht Teil dieser Spec — kein Endpunkt, keine UI dafür in diesem Scope (bleibt Spec 0004).

## Datenmodell-Bezug

Siehe ADR [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](../decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md) für die vollständige Begründung. Neu: `PhotoCriterionScore`, `PhotoRanking`, `CriterionScoringRun` (ersetzt `TopSelectionRun`). Additiv: `ScoringRun.gate_confirmed_at`. Entfällt: `PhotoScore.category`, `PhotoScore.local_quality_score`, Tabelle `top_selection_runs`. `Rating` bleibt unverändert (siehe [`docs/architecture.md`](../../docs/architecture.md), wird im Umsetzungs-PR aktualisiert).

## Architektur / Umsetzung

**Bezug:** ADR [`decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md`](../decisions/0021-kriterien-datenmodell-kuratierungs-pipeline.md) (neu, Datenmodell-Grundstruktur-Entscheidungen im Detail), [`decisions/0006-local-scoring-datamodel.md`](../decisions/0006-local-scoring-datamodel.md), [`decisions/0015-lokale-kategorie-klassifikation.md`](../decisions/0015-lokale-kategorie-klassifikation.md), [`decisions/0019-job-lauf-heartbeat-watchdog.md`](../decisions/0019-job-lauf-heartbeat-watchdog.md).

Diese Spec ersetzt Spec 0024 vollständig (Top-Auswahl-Mechanik) und baut Spec 0003 im Kern unverändert weiter (Ausschuss-Erkennung bleibt). Das Datenmodell wird umgebaut, nicht rein additiv erweitert.

### Datenmodell

- **`PhotoScore`**: unverändert an `sharpness`, `exposure`, `phash`, `duplicate_of`, `cluster_key`, `suggested_status`, `computed_at`. **Entfällt:** `category`, `local_quality_score` (reiner, nie manuell editierter Ableitungszustand).
- **Neu `PhotoCriterionScore`** (`photo_criterion_scores`): `id`, `photo_id` (FK), `criterion_key: str` (freier String — Kern der Erweiterbarkeit, kein Enum), `value: float` (normiert `[0,1]`, höher = besser), `source: CriterionSource` (neues Enum: `local_heuristic`/`local_ml`/`cloud`), `computed_at`. `UniqueConstraint(photo_id, criterion_key)`, Upsert bei jedem Lauf.
- **Neu, in Code geführt (kein DB-Enum): `backend/src/photosort/criteria.py::CRITERIA_REGISTRY`** — pro `criterion_key` Anzeigename, `source`, optionale Compute-Funktion. Register-Erweiterung = einziger Aufwand für ein künftiges neues Kriterium, keine Migration.
- **Neu `CriterionScoringRun`** (`criterion_scoring_runs`, ersetzt `TopSelectionRun`): `id`, `project_id`, `scoring_run_id` (FK `scoring_runs.id` — bindet an den `ScoringRun`-Stand, dessen `cluster_key` er voraussetzt), `status` (`ScanStatus`), `started_at`/`finished_at`, `photos_total`/`photos_processed`, `last_progress_at` (Watchdog, ADR 0019), `error_message`.
- **Neu `PhotoRanking`** (`photo_rankings`): `id`, `criterion_scoring_run_id` (FK), `photo_id`, `cluster_key`, `category_key: str` (frei), `rank_score: float`, `rank_position: int` (1-basiert je Partition `cluster_key`+`category_key`). `UniqueConstraint(criterion_scoring_run_id, photo_id)`. Enthält immer den vollen Kandidatenpool, nicht nur Top-N.
- **`ScoringRun`**: additiv `gate_confirmed_at: datetime | None`.
- **`Rating`**: unverändert, wird für Schritt 7 (Aussortieren) wiederverwendet.

### Backend / Worker

- **`criteria.py`** (neu): Kriterien-Registry + Normierungsfunktionen. Übernimmt für `sharpness`/`exposure` die bereits vorhandenen `PhotoScore`-Rohwerte (keine erneute Bildverarbeitung), berechnet neue Inhalts-Kriterien über die bereits bestehenden `classification.py`-Funktionen (`detect_person`, `compute_uniform_area_fraction`). `category_key` wird über eine kleine, austauschbare Zuordnungsfunktion aus den Inhalts-Kriterien abgeleitet (deterministische Prioritätskette wie bisher, jetzt datengetrieben statt hart am mediapipe-Aufruf).
- **`ranking.py`** (neu, pure Funktionen, DB-frei, analog `scoring.py`/`classification.py`): `rank_photos(candidates: dict[photo_id, dict[criterion_key, float]], weights: dict[str, float]) -> list[RankedPhoto]`. Muss fehlende Kriterien pro Foto tolerieren (Gewichts-Renormierung auf die vorhandene Teilmenge) — strukturelle Anforderung, konkrete Default-Gewichtung ist bewusst austauschbar, nicht Teil dieser Spec.
- **Job `run_criterion_scoring`** (`worker.py`, ersetzt `select_top_photos`): Guard `409` falls `scoring_run_id` nicht der aktuell neueste erfolgreiche `ScoringRun` ist. Lädt alle Ausschuss-Überlebenden (`PhotoScore.suggested_status IS NULL`) des referenzierten `ScoringRun`, berechnet Kriterien je Foto (Live-Fortschritt wie bisher), ruft im selben Lauf `rank_photos` je `cluster_key`+`category_key`-Partition auf und schreibt `PhotoRanking`-Zeilen (reine In-Memory-Aggregation, kein separater Progress-Run dafür nötig).
- **Gate-Logik:** `run_project_scoring` setzt `gate_confirmed_at` beim Abschluss automatisch, falls `suggestions_found == 0`.

### API

- Neu: `POST /projects/{id}/confirm-ausschuss-gate` — setzt `gate_confirmed_at = now()` auf den aktuell neuesten `ScoringRun`, idempotent, `409` ohne erfolgreichen `ScoringRun`.
- Neu: `POST /projects/{id}/score-criteria` (ersetzt `/select-top`) — kein `top_n_per_cluster`-Body-Parameter mehr (N wird erst beim Lesen angewendet, nicht mehr beim Scoren). `403` analog `category_selection_enabled`-Flag, `409` ohne Gate-Bestätigung bzw. bei veraltetem `scoring_run_id`-Bezug.
- `GET /projects/{id}/photos`: neuer Query-Parameter `top_n_per_category` (`Field(ge=1, le=10)`) — liefert je Partition die besten N nach `rank_position`, gefiltert um vom aktuellen Nutzer `REJECTED`-bewertete Fotos. Das ist zugleich der gesamte Backfill-Mechanismus — keine eigene Backfill-Route, keine Mutation, reine Query.
- `SuggestionOut`: `category` → `category_key: str`, `reason` um einen Wert für "Rang-Vorschlag" erweitert (Detail-Benennung technische Umsetzungsentscheidung des `developer`-Agenten).

### Reihenfolge für den TDD-Einstieg

1. `PhotoCriterionScore`-Modell + Migration (inkl. Spalten-Drop `category`/`local_quality_score`, Tabellen-Drop `top_selection_runs`) + Migrations-Inspector-Test.
2. `criteria.py`-Registry + Normierung für `sharpness`/`exposure` (kleinster, isolierter erster Schritt).
3. `ranking.py::rank_photos` (pure Funktion, inkl. fehlender-Kriterien-Fall) — unabhängig testbar.
4. `CriterionScoringRun`+`PhotoRanking`-Modelle + Migration.
5. Worker-Job `run_criterion_scoring` (Guard, Fortschritt, Aufruf von `criteria.py`+`ranking.py`).
6. Gate: `ScoringRun.gate_confirmed_at` + Auto-Set bei leerem Ausschuss + `confirm-ausschuss-gate`-Endpunkt.
7. `score-criteria`-Endpunkt (409-Kette: Gate → `scoring_run_id`-Aktualität).
8. `GET /projects/{id}/photos`-Erweiterung (Top-N-Query inkl. Backfill-Filter).
9. Frontend (siehe UI/UX).

### Bekannter, akzeptierter Trade-off

Da N beim Scoren nicht mehr bekannt ist, entfällt der bisherige Kandidatenpool-Vorfilter aus Spec 0024 — `run_criterion_scoring` verarbeitet potenziell mehr Fotos als bisher. Kein Blocker, ggf. späteres eigenständiges Performance-Follow-up.

## UI/UX

Design-System: [`architecture/0004-design-system.md`](../architecture/0004-design-system.md) — für diese Spec ergänzt um drei neue Muster ("Gateführter Sammel-Review mit Einmal-Bestätigung", "Automatisch übersprungener Schritt bleibt sichtbar nachvollziehbar", "In-place Nachrücken (Backfill) statt Reflow") sowie eine Korrektur des bestehenden Eintrags "Kategorie-Kennzeichnung" (kein festes L/D/M-Kürzel mehr, da `category_key` frei ist).

**Navigationsstruktur:** kein neuer Wizard/Stepper. Fünf statt bisher zwei Sections nacheinander auf `ProjectDetailPage`, jede dauerhaft an fester Position sichtbar, bei fehlender Vorbedingung `disabled` mit Erklärtext statt zu verschwinden (bestehendes "Nicht verfügbare Aktion"-Muster):

1. **Scan** — unverändert.
2. **Ausschuss-Erkennung** — bisheriger Trigger, im Kern unverändert.
3. **Ausschuss-Gate** (neu) — aktiv, sobald Ausschuss-Erkennung `success` ist.
4. **Kriterien-Bewertung** (`POST score-criteria`, kein `top_n_per_cluster` mehr an dieser Stelle) — `disabled` + Erklärtext "Bestätige zuerst den Ausschuss oben.", bis `gate_confirmed_at !== null`.
5. **Kategorie-Kuratierung** — Top-N-Eingabefeld (1–10, Default 3) + Link zu neuer, eigenständiger Route `/projects/:projectId/curate`.

**Ausschuss-Gate-Screen:** kein neuer Screen, sondern die bestehende `PhotoGridPage?filter=suggested` um einen Gate-Modus (`&gate=1`) erweitert: Banner mit Erklärtext + Kandidatenanzahl + primärem Button "Ausschuss gesichtet, weiter" (löst `confirm-ausschuss-gate` aus, navigiert zurück zu `ProjectDetailPage`). Korrektur einzelner Fotos über bestehende Mechanismen (Übernehmen-Button, Bewertungsänderung in Detailansicht) — keine Einzelbestätigungspflicht, der Abschluss-Button ist unabhängig davon jederzeit klickbar. **Leerer Ausschuss:** die Gate-Section auf `ProjectDetailPage` zeigt direkt einen dauerhaft sichtbaren Status "Kein Ausschuss gefunden — automatisch bestätigt" statt eines flüchtigen Toasts, macht den Auto-Skip auch bei erneutem Betrachten nachvollziehbar. Nach manueller Bestätigung: "Ausschuss gesichtet am [Datum]".

**Kategorie-Kuratierungs-Ansicht** (`/projects/:projectId/curate`): pro Cluster (Foto-Moment) ein Abschnitt mit Zeitfenster-Überschrift, darin je Kategorie eine Untergruppe (Überschrift = ausgeschriebener `category_key`) mit einem Mini-Raster der bis zu N Top-Fotos. **Aussortieren:** bestehende `Rating`-Mechanik ("Verwerfen"). **Backfill:** neues Muster "In-place Nachrücken statt Reflow" — die Kachel bleibt an ihrer Position, zeigt kurz einen Skeleton-Platzhalter während des Nachladens (Refetch der gefilterten Query), dann erscheint das nächste Foto; kein Reflow der übrigen Kacheln. **Erschöpfter Pool:** eigener Leerzustand ("Kein weiteres Foto verfügbar"), kein Fehler-Styling. Da `Rating` personenbezogen ist, ist die gezeigte Top-N-Auswahl je Nutzer individuell — Seitenkopf zeigt "Deine Auswahl", um das nicht missverständlich wirken zu lassen.

**Zustände** (je Section auf `ProjectDetailPage`): Scan/Ausschuss-Erkennung unverändert. Ausschuss-Gate: ausstehend / automatisch bestätigt (leer) / manuell bestätigt. Kriterien-Bewertung: nicht verfügbar (Gate offen) / nie gestartet / läuft / Erfolg / Fehler. Kategorie-Kuratierung: nicht verfügbar (Kriterien-Bewertung fehlt) / aktiv. Kein Abschluss-/Export-Zustand (separate Spec).

**Dynamische Kategorie-Keys:** kein festes Kürzel-Schema mehr möglich. Grid-Kachel-Chip: erste drei Zeichen von `category_key` in Großbuchstaben, vollständiger Name via `aria-label`/`title` (seltene Präfix-Kollisionen sind für zwei bekannte Nutzer ein akzeptables Restrisiko). In der Kuratierungs-Ansicht dient derselbe Key als ausgeschriebene Abschnittsüberschrift ohne Platzbeschränkung. Reihenfolge: alphabetisch nach `category_key`.

## Security

**Sicherheitsrelevant: Ja** — drei neue/geänderte Endpunkte, eine Datenmodell-Umstrukturierung und eine bewusste strukturelle Vorbereitung (Kriterien-Quellen-Registry) mit potenziell künftiger externer Anbindung. Kein neuer Angriffsflächen-*Typ* (kein Upload, kein neues externes System, kein neues Secret) — daher schlank, aber nicht "nicht relevant".

- **Autorisierung:** Alle drei Endpunkte (`confirm-ausschuss-gate`, `score-criteria`, erweitertes `GET /photos`) hängen unverändert am selben Router-Torwächter (`dependencies=[Depends(get_current_user)]`, `api/projects.py`) — kein neuer Auth-Pfad, Muss-Kriterium wie bei jeder bisherigen Spec.
- **`top_n_per_category`:** Muss-Kriterium, serverseitig deklarativ begrenzt (`Field(ge=1, le=10)`, analog `top_n_per_cluster`) — kein Sicherheits-, aber ein Robustheits-/Ressourcen-Kriterium (potenziell sehr große Response über alle Partitionen).
- **Gate-Reichweite (projektweit, mit Daniel bestätigt):** Empfehlung von `architect` und `security-engineer` übereinstimmend, mit Daniel abgeglichen. Begründung: das Gate ist ein Workflow-Checkpoint ("wurde der Ausschuss überhaupt einmal gesichtet"), keine Zugriffsschranke zwischen den Nutzern — es steuert nicht *wer was sehen darf*, sondern nur *wann* ein gemeinsam sichtbarer Datenbestand für den nächsten Schritt freigegeben wird. Konsistent mit dem etablierten "kein Innentäter-Modell zwischen Daniel und seiner Frau" (`architecture/0003-securitykonzept.md`) und damit, dass alle anderen Run-Tabellen ebenfalls nie personenbezogen sind — nur `Rating` ist es, weil dort Vertraulichkeit zwischen den Nutzern eine echte Produktanforderung ist.
- **Backfill-Query:** kein neues IDOR-/Datenleck-Risiko über das bereits akzeptierte Modell hinaus. Der Filter "vom aktuellen Nutzer `REJECTED`-bewertete Fotos ausschließen" liest `user_id` ausschließlich aus dem JWT. `category_key`/`cluster_key` sind freie Strings, aber ausschließlich serverseitig aus lokaler Klassifikation erzeugt (nie Nutzereingabe), laufen als parametrisierte ORM-Filterwerte — keine Injection-Fläche.
- **Explizite Abgrenzung — keine Cloud-Anbindung durch diese Spec:** `CriterionSource.cloud` ist ein reiner Registry-Wert im Datenmodell, diese Spec implementiert weder einen `source=cloud`-Compute-Pfad noch eine Netzwerkverbindung zu einem externen Kriterien-Dienst, noch ein neues Secret/API-Key. Es fließen keine Bilddaten nach außen — konsistent mit ADR 0015 und dem noch offenen Phase-B-Vorbehalt aus Spec 0035. **Eine künftige Spec, die `source=cloud` produktiv einschaltet, braucht erneut eine vollständige, eigenständige Security-Konsultation** (Einwilligung, Datenversand-Umfang, neues Secret-Handling, neue externe Vertrauensgrenze) — diese Spec nimmt diese Entscheidung nicht vorweg.
- **Migration sicherheitsneutral:** das Entfernen von `PhotoScore.category`/`.local_quality_score`/`top_selection_runs` betrifft ausschließlich abgeleiteten, nie vom Nutzer editierten Zustand — kein Verlust personenbezogener Daten (`Rating` bleibt unangetastet).

`specs/architecture/0003-securitykonzept.md` wird durch diese Spec nicht ergänzt — keine neue Angriffsflächen-*Klasse*, durchgehend Anwendung bereits verankerter Prinzipien.

## Teststrategie

`specs/architecture/0002-testkonzept.md` ist bereits ergänzt: neue Sektionen "Generische Kriterien-Registry / pure Rangfolgen-Funktion mit fehlenden Werten" und "Backfill als reine Filter-Query statt Mutation" — erste Registry-statt-Spalten-Modellierung, erste pure Funktion mit Renormierungspflicht, erster Fall "Mutation wird vollständig durch Query ersetzt", erste nicht-additive Migration im Projekt.

**Testebenen:**
- **Unit:** `criteria.py` (`test_criteria.py`, neu) — jeder Registry-Eintrag mit lokaler Compute-Funktion liefert `[0,1]`, Wiederverwendungsnachweis für `detect_person`/`compute_uniform_area_fraction` (Spy statt Reimplementierung). `ranking.py::rank_photos` (`test_ranking.py`, neu) — Renormierung bei fehlenden Kriterien (Kernfall), Kandidat ohne jedes gewichtete Kriterium, Tie-Break, leere/einzelne Kandidatenliste, unbekannter `criterion_key` in `weights`. `category_key`-Ableitungsfunktion analog bestehendem `test_classification.py`-Muster, jetzt über ein Kriterien-Wert-Dict.
- **Integration (In-Memory-SQLite):** `run_criterion_scoring` (`test_worker_criterion_scoring.py`, ersetzt `test_worker_top_selection.py`) — Guard bei nicht bestätigtem Gate, Guard bei stale `scoring_run_id` (`409`), best-effort bei einzelnem Kriterien-Fehler, `photo_rankings` enthält vollen Pool je Partition. `run_project_scoring`-Erweiterung: Auto-Set von `gate_confirmed_at` bei `suggestions_found == 0`. Migrations-Inspector-Test: gedroppte Spalten/Tabelle tatsächlich weg, Restspalten unverändert.
- **API:** `POST /confirm-ausschuss-gate` (409/Idempotenz/Auto-Set), `POST /score-criteria` (401/409-Kette/202), `GET /photos?top_n_per_category=N` (Top-N-Auslieferung, Backfill-Nachweis über zwei aufeinanderfolgende Aufrufe vor/nach `REJECTED`, erschöpfter Pool, Personenbezug des Filters).
- **Frontend:** neue Route `/projects/:projectId/curate`, Gate-Banner auf `PhotoGridPage?filter=suggested&gate=1`, In-place-Backfill-Nachrücken per Refetch (Skeleton statt Reflow), eigener Leerzustand für erschöpften Pool.
- **Bewusst nicht getestet:** reale Kalibrierung der wiederverwendeten Schärfe-/Inhalts-Heuristiken (bekannte Lücke aus Spec 0003/0024, hier nicht neu).

**Edge Cases (Pflicht):**
- Leerer Ausschuss → Gate automatisch bestätigt, Endpunkt bleibt idempotent aufrufbar.
- Re-Scan/Re-Scoring mit veraltetem `scoring_run_id`-Bezug während laufender Kuratierung → `409`, keine `Rating`-Daten verloren.
- Erschöpfter Backfill-Pool (weniger Kandidaten als N nach Filterung) → weniger Treffer, kein Fehler.
- Fehlende Kriterien bei `rank_photos` → Gewichts-Renormierung; Kandidat ganz ohne ein in `weights` genanntes Kriterium hat ein dokumentiertes, getestetes Verhalten (Entscheidung liegt beim `developer`, muss begründet und getestet sein).
- Migration: Spalten-/Tabellen-Drop verifiziert, kein Kollateral-Drop benachbarter Spalten; verwaiste alte `RUNNING`-`TopSelectionRun`-Läufe zum Deploy-Zeitpunkt sind akzeptierter, dokumentierter Verlust ohne `Rating`-Bezug.

## Entscheidungen (2026-08-13, im Idea-Sharpening-Gespräch mit Daniel geklärt)

- **Fusion statt Erweiterung:** diese Spec ersetzt die bisherige, unabhängig auslösbare Zwei-Buttons-Mechanik (Spec 0003+0024) durch einen einzigen, gateführten Prozess (per Rückfrage bestätigt) — beide Vorgänger-Specs werden auf `Superseded` gesetzt.
- **Kriterien-Quelle bewusst nicht Teil dieser Spec:** ob ein Kriterium lokal-deterministisch, lokal-ML oder Cloud-KI berechnet wird, entscheidet Daniel separat, nach Vorliegen der noch offenen Recherche aus Spec 0035 (PR #72). Diese Spec liefert nur die dafür nötige, erweiterbare Datenstruktur (`PhotoCriterionScore` mit freiem `criterion_key` + `source`-Enum), implementiert selbst keine Cloud-Anbindung.
- **Export (Schritt 8) bewusst nicht Teil dieser Spec** (per Rückfrage bestätigt): bleibt bei der separaten, weiterhin `Proposed` Spec 0004, die eigene offene Fragen hat (Zielordner-Schema, welche Bewertung zählt, Re-Export-Verhalten) und nicht in dieser Sitzung mitgeschärft wird.
- **Ausschuss-Gate: einmalige Sammel-Bestätigung statt Einzelbestätigung pro Foto** (per Rückfrage bestätigt): Nutzer kann einzelne Fotos korrigieren, muss aber nur einmal insgesamt bestätigen — vermeidet Mühsal bei großen Ausschuss-Mengen, analog zum bereits etablierten Grid-Schnellbestätigen-Muster.
- **Backfill nur innerhalb derselben Kategorie, kein kategorieübergreifendes Nachziehen** (per Rückfrage bestätigt): konsistent mit der bereits in Spec 0024 bewusst getroffenen "kein künstliches Auffüllen"-Entscheidung.
- **Gate-Bestätigung projektweit, nicht personenbezogen** (per Rückfrage bestätigt, nach übereinstimmender Empfehlung von `architect` und `security-engineer`): das Gate ist ein Workflow-Checkpoint, keine Zugriffsschranke zwischen den Nutzern — konsistent mit allen anderen, ebenfalls projektweiten Run-Tabellen; nur `Rating` bleibt personenbezogen.
- **Datenmodell: generische `PhotoCriterionScore`-Tabelle statt weiterer fixer Spalten** (`architect`-Konsultation, ADR 0021): erlaubt künftig wachsende Kriterien-Listen ohne wiederholte Migrationen.
- **Rangfolge strukturell, nicht formelhaft festgelegt** (`architect`-Konsultation): `rank_photos` ist eine reine, gewichts-parametrisierte Funktion mit Renormierung bei fehlenden Kriterien — die konkrete Gewichtung folgt erst mit der künftigen Kriterien-Entscheidung.
- **Backfill als reine Filter-Query statt Mutation-Endpoint** (`architect`-Konsultation): der volle Rangfolge-Pool ist bereits serverseitig vorhanden (`PhotoRanking`), Nachrücken ist ein reiner Nebeneffekt einer erneuten Top-N-Abfrage nach einer `Rating`-Änderung.
- **`security-engineer` konsultiert (Schritt 8):** Datenmodell-/Sichtbarkeits-Bezug (Gate-Reichweite, Backfill-Filter-Personenbezug) — siehe Security-Abschnitt.
- **`ux-ui-designer` konsultiert (Schritt 7):** sichtbare Oberfläche in mehreren Views betroffen — siehe UI/UX-Abschnitt, Design-System bereits aktualisiert.
- **Roadmap-Priorität: Hoch** (`requirements-engineer`-Konsultation, 2026-08-13): fusioniert zwei bereits produktive, täglich genutzte Kernfeatures zu einem durchgängigen Workflow — vergleichbar mit bisherigen hochpriorisierten Produktverbesserungen (0030/0027/0034), keine Verdrängung bereits laufender Arbeit.

## Offene Fragen

Keine offenen Fragen mehr für den Scope dieser Spec.

## Out of Scope

- **Konkrete Kriterien-Liste und ihre Quelle** (lokal-deterministisch/lokal-ML/Cloud) für Kriterien über `sharpness`/`exposure`/`content_people`/`content_landscape` hinaus (Tier, Gebäude, Sehenswürdigkeit, Ästhetik, Goldener Schnitt, etc.) — eigene, spätere Entscheidung nach Vorliegen der Spec-0035-Recherche (PR #72).
- **Konkrete Rangfolge-Gewichtung/-Formel** — nur die strukturelle Fähigkeit (`rank_photos` mit variablem `weights`-Dict) ist Teil dieser Spec, kein konkreter Default.
- **Export nach OpenCloud** (Spec 0004) — bleibt eigenständige, separate Spec.
- **Personenbezogene Gate-Bestätigung** — bewusst projektweit, siehe "Entscheidungen"/Security.
- **Kategorieübergreifendes Backfill-Nachziehen** — bewusst nur innerhalb derselben Kategorie, siehe "Entscheidungen".
- **Einzelbestätigungspflicht pro Ausschuss-Foto** — bewusst nur einmalige Sammel-Bestätigung.
- **Performance-Optimierung des entfallenen Kandidatenpool-Vorfilters** — bekannter, akzeptierter Trade-off (siehe Architektur-Abschnitt), kein Teil dieser Spec.
