# 0207 - Projekt-Statistikseite

**Status:** Accepted
**Erstellt:** 2026-09-02
**Bezug:** [GitHub-Issue #207](https://github.com/TheRealKoller/photosort/issues/207) (Refinement vor dieser Spec-Erstellung abgeschlossen, Story-Inhalt unverändert übernommen)

## Ziel

Für ein Projekt gibt es heute keinen Ort, an dem sein Zustand als Ganzes ablesbar ist: Zahlen liegen über die Pipeline-Schritte verstreut, und für Remote-Berechnungen (Sehenswürdigkeiten-Erkennung, Kategorie-Klassifizierung) fließt echtes Geld, ohne dass im Nachhinein erkennbar wäre, wie viel ausgegeben wurde — es existiert nur eine Schätzung *vor* dem Lauf, die nirgends festgehalten wird.

Eine Statistikseite je Projekt schließt diese Lücke für die beiden Nutzer (Daniel und seine Frau) in vier Hinsichten: Kostenkontrolle, Fortschritts-Überblick, Rückblick auf den Projektinhalt und Vertrauen bzw. Fehlersuche ("ist alles korrekt durchgelaufen?").

Die Ist-Kosten werden ab Einführung erfasst; für frühere Läufe wird bewusst **nicht** nachträglich geschätzt. Daraus folgt: Jeder Lauf, der bis zur Umsetzung stattfindet, bleibt dauerhaft ohne Kostenangabe — der Nutzen der Story wächst also, je früher sie umgesetzt wird.

## User Story

Als Nutzer eines PhotoSort-Projekts möchte ich auf einer Statistikseite den Zustand des Projekts an einem Ort sehen — Umfang, Speicherbedarf, Kategorienverteilung, Bearbeitungsstand und die tatsächlich angefallenen Kosten für Remote-Berechnungen —, damit ich meine Ausgaben kontrollieren, den Fortschritt einschätzen, Auffälligkeiten erkennen und auf das Projekt zurückblicken kann, ohne Zahlen aus verschiedenen Ansichten zusammensuchen zu müssen.

## Akzeptanzkriterien

Die Kriterien der Story sind durch die `test-engineer`-Konsultation auf Testbarkeit geschärft; wo eine Formulierung präzisiert wurde, ist die fachliche Aussage unverändert.

**Zugang**

- [ ] Jedes Projekt hat eine eigene Statistikseite unter `/projects/:projectId/stats`, erreichbar über einen Sekundär-Button „Statistik" in der Projekt-Navigation neben „Einstellungen".
- [ ] **(A1)** Für ein Projekt ohne Fotos antwortet der Endpunkt mit 200. Alle Zähler sind 0, Zeitraum und Zeitpunkte sind leer („—" / „noch nie gelaufen"), alle Kategorien des Sets sind mit Anzahl 0 und Anteil 0 % gelistet, die Kostensumme ist 0,00 USD ohne „nicht vollständig erfasst"-Hinweis. Es erscheinen weder Fehlermeldung noch leerer Bereich noch `NaN`.

**Umfang und Speicher**

- [ ] Gesamtzahl der Fotos im Projekt.
- [ ] Speicherbedarf der Originaldateien in OpenCloud.
- [ ] **(S1)** Beträge unter 1 GB werden in MB, ab 1 GB in GB dargestellt, jeweils mit einer Nachkommastelle und deutschem Dezimalkomma (`de-DE`), Basis 1024. `0` wird als „0 MB" dargestellt, ein nicht ermittelbarer Wert als „—" mit kurzer Begründung.
- [ ] **(S2)** Die beiden Speicherwerte tragen die Beschriftungen „Originaldateien in OpenCloud" und „Lokal belegt (Thumbnail-Cache + Datenbestand)" und stehen als zwei getrennte, gleichrangige Kennzahlen nebeneinander. Der lokale Wert weist getrennt aus, welcher Anteil Thumbnail-Cache und welcher geschätzter Datenbank-Anteil ist; ist der Datenbank-Anteil nicht ermittelbar (Nicht-Postgres-Umgebung), wird er als „nicht ermittelbar" ausgewiesen und **nicht** als 0 dargestellt.
- [ ] Zeitraum der Aufnahmen im Projekt (ältestes und neuestes Foto). Bei leerem Projekt beide Werte leer; bei genau einem Foto bzw. identischen Zeitstempeln ist Anfang gleich Ende, ohne dass ein leerer Zeitraum-Text entsteht.

**Kategorien**

- [ ] **(K1)** Die Verteilung enthält **alle** Kategorien des festen Sets inklusive `nicht_erkannt` in Registry-Reihenfolge, auch solche mit Anzahl 0. Der Anteil ist der Bruchteil an den **klassifizierten** Fotos (Fotos mit einer `photo_rankings`-Zeile im letzten erfolgreichen Klassifizierungslauf), nicht an allen Fotos; bei 0 klassifizierten Fotos ist jeder Anteil 0. Fotos ohne Kategoriezuordnung werden als eigene Kennzahl „nicht klassifiziert" ausgewiesen und **nicht** in `nicht_erkannt` eingerechnet.
- [ ] **(K2)** Ausgewiesen wird die Anzahl der Fotos des Projekts mit gesetztem `category_override`, unabhängig davon, ob der gespeicherte Wert noch zum aktuellen Set gehört. Die manuell korrigierte Kategorie erscheint zugleich regulär in der Verteilung — der Zähler ist eine Zusatzangabe, keine Korrektur der Verteilung.
- [ ] Die Anzeigenamen der Kategorien stammen vom Server; das Frontend enthält keine eigene Übersetzungstabelle für Set-Keys (ADR 0049).

**Kosten für Remote-Berechnungen**

- [ ] Gesamtsumme der tatsächlich angefallenen Kosten dieses Projekts, aufgeschlüsselt nach Sehenswürdigkeiten-Erkennung und Kategorie-Klassifizierung. Beide Zwecke sind immer aufgeführt, auch mit Betrag 0.
- [ ] **(K3)** Der ausgewiesene Betrag ist die Summe der an den Lauf-Zeilen des Projekts gespeicherten Ist-Beträge. Die Vorab-Schätzung (`COST_PER_IMAGE_USD`, `GET /classify/estimate`) fließt an keiner Stelle ein; ein Projekt, dessen Läufe alle 0 kosten, zeigt 0,00 USD, auch wenn seine Schätzung ungleich 0 wäre.
- [ ] **(K4)** Beträge werden mit zwei Nachkommastellen und der Kennzeichnung „USD" ausgewiesen, erkennbar als Verbrauch dieses Projekts. Ein Betrag größer 0, der auf 0,00 runden würde, wird als „< 0,01 USD" dargestellt — auf einer Seite zur Kostenkontrolle darf ein tatsächlich angefallener Betrag nicht als „nichts ausgegeben" erscheinen. Die Summe entspricht exakt der Summe der beiden Einzelposten.
- [ ] **(K5)** Je Zweck wird ein Hinweis „Summe unvollständig erfasst" genau dann angezeigt, wenn mindestens einer der beiden Befunde aus ADR 0051 Punkt 5 zutrifft: **(a)** es existiert ein Lauf ohne erfassten Betrag (`cost_usd IS NULL`) **und** das Projekt besitzt mindestens ein Ergebnis dieser Art; oder **(b)** es existiert ein Lauf mit `api_calls > 0`, dessen `cost_usd` `NULL` oder `0` ist. Für keinen der Fälle wird etwas geschätzt oder hochgerechnet; der Betrag bleibt die Summe des tatsächlich Erfassten.

**Fortschritt**

- [ ] **(F1)** Je Verarbeitungsstufe wird „x von y Fotos" ausgewiesen: (1) gescannt (= Gesamtzahl Fotos), (2) Thumbnails erzeugt (Fotos mit vollständigem Cache-Paar), (3) lokal bewertet (Fotos mit `photo_scores`-Zeile), (4) klassifiziert/eingeordnet (Fotos mit `photo_rankings`-Zeile im letzten erfolgreichen Lauf), (5) remote klassifiziert (Fotos mit `photo_category_classifications`-Zeile). Bezugsgröße `y` ist überall die Gesamtzahl Fotos des Projekts; bei 0 Fotos steht überall „0 von 0".
- [ ] **(F2)** Die vier Bewertungswerte (Favorit / albumwürdig / aussortiert / noch nicht bewertet) beziehen sich ausschließlich auf Bewertungen des angemeldeten Nutzers, sind als solche beschriftet, und summieren sich exakt zur Gesamtzahl Fotos. Bewertungen des jeweils anderen Nutzers verändern keinen der vier Werte.
- [ ] **(F3)** Je Verarbeitungsart (Scan, lokale Bewertung, Klassifizierung, Remote-Kategorie-Klassifizierung) wird der `finished_at`-Zeitpunkt des zuletzt **erfolgreich** beendeten Laufs ausgewiesen; existiert keiner, steht „noch nie gelaufen". Ein laufender oder fehlgeschlagener Lauf verändert den angezeigten Zeitpunkt nicht.

**Vertrauen und Fehlersuche**

- [ ] **(D2)** Ausgewiesen wird `files_skipped` des zuletzt gestarteten Scan-Laufs des Projekts, unabhängig von dessen Status. Existiert kein Scan-Lauf, steht „noch nie gescannt" statt 0.
- [ ] **(D1)** Je Zweck wird die Anzahl der Fotos ausgewiesen, für die aktuell ein letzter fehlgeschlagener Cloud-Aufruf vermerkt ist. Das ist ein **Ist-Zustand, keine Historie**: ein später erfolgreicher Aufruf für dasselbe Foto senkt den Wert wieder; die Seite formuliert das entsprechend.
- [ ] **(D3)** Ausgewiesen wird die Anzahl der Fotos, die als Duplikat eines anderen Fotos markiert sind (das jeweilige Originalfoto zählt nicht mit).

**Darstellung und Abgrenzung**

- [ ] Die Seite ist eine Momentaufnahme des aktuellen Stands — kein Zeitverlauf, keine Historie vergangener Läufe, keine Verlaufsdiagramme.
- [ ] **(A3)** Die Seite enthält keine Foto-Vorschauen, keine Bewertungs- oder Kategorie-Bedienelemente, keine Auslöser für Verarbeitungsläufe und keine Filter-, Sortier- oder Export-Bedienelemente. Sie lädt ihre Daten einmal beim Öffnen und aktualisiert sie nicht selbsttätig.
- [ ] **(A2)** Zu mindestens folgenden Kennzahlen steht eine kurze Erläuterung unmittelbar bei der Zahl (aufklappbar oder als Beschreibungstext): geschätzter lokaler Datenbank-Anteil, „nicht erkannt" vs. „nicht klassifiziert", „Summe unvollständig erfasst" bei den Kosten, fehlgeschlagene Remote-Aufrufe als Ist-Zustand, übersprungene Dateien.
- [ ] Keine projektübergreifende Gesamtstatistik, keine nachträgliche Kostenschätzung für Läufe vor Einführung der Erfassung, keine Kennzahlen über den obigen Katalog hinaus, keine Duplizierung bestehender Anzeigen (Scan-Statistik im Scan-Schritt, Häufigkeitsliste der Feinlabels).

## Datenmodell-Bezug

Keine neue Entität. Additiv je vier Spalten an zwei bestehenden Run-Tabellen: `CriterionScoringRun.{landmark_api_calls, landmark_input_tokens, landmark_output_tokens, landmark_cost_usd}` und `RemoteCategoryClassificationRun.{api_calls, input_tokens, output_tokens, cost_usd}` — alle nullable, Python-Default `0`, `NULL` bedeutet „nicht erfasst" (Idiom `ScanRun.total_files`). Lesend berührt: `Photo`, `PhotoScore`, `PhotoRanking`, `PhotoCategoryClassification`, `PhotoLandmarkDetection`, `PhotoCloudVisionError`, `Rating`, `ScanRun`. Siehe [`docs/architecture.md`](../../docs/architecture.md).

## Architektur / Umsetzung

> Architekturentscheidung: ADR [`0051`](../decisions/0051-ist-kostenerfassung-remote-laeufe.md) — Ist-Kostenerfassung der Remote-Läufe aus dem tatsächlichen Token-Verbrauch. Ergänzt (löst nicht ab) ADR 0050 Punkt 5 (Vorab-Schätzung), ADR 0021 Punkt 5 und ADR 0032 Punkt 6 (Run-Tracking).

### Überblick

Die Statistikseite ist zu rund 85 % eine reine **Leseleistung** über bereits vorhandene Daten — ein neuer Endpunkt mit gut einem Dutzend Aggregat-Queries. Der einzige Teil, für den heute schlicht keine Daten existieren, sind die **Ist-Kosten**: sie erfordern eine neue Erfassung im Worker und acht neue Spalten.

### 1. Datenherkunft je Kennzahl

Ohne neue Persistenz ableitbar (alles Bestandsdaten):

| Kennzahl | Quelle |
|---|---|
| Gesamtzahl Fotos | `COUNT(photos)` je `project_id` |
| Speicher OpenCloud | `SUM(photos.content_length)` — bei 0 Fotos liefert `SUM` `NULL`, serverseitig auf `0` normalisieren |
| Aufnahme-Zeitraum | `MIN/MAX(photos.taken_at)` |
| Kategorienverteilung | `GROUP BY photo_rankings.category_key` des **letzten erfolgreichen** `CriterionScoringRun` |
| Manuell korrigierte Kategorien | `COUNT(photo_scores.category_override IS NOT NULL)` |
| Bearbeitungsstand | Existenz der jeweiligen Kindzeile je Foto (`photo_scores`, `photo_criterion_scores`, `photo_category_classifications`, `photo_rankings`) plus Cache-Messung |
| Bewertungsstand | `GROUP BY ratings.status` **gefiltert auf `ratings.user_id == current_user.id`**, „unbewertet" als Differenz zur Fotoanzahl |
| Letzte erfolgreiche Läufe | `MAX(finished_at)` je Run-Tabelle mit `status='success'` |
| Übersprungene Dateien | `scan_runs.files_skipped` des zuletzt gestarteten Laufs |
| Remote-Fehlschläge je Zweck | `GROUP BY photo_cloud_vision_errors.phase` |
| Duplikate | `COUNT(photo_scores.duplicate_of IS NOT NULL)` |
| Thumbnail-Cache-Größe | Dateisystem (`os.stat`, siehe Abschnitt 4) |

Neue Persistenz ausschließlich für die Ist-Kosten (ADR 0051 Punkt 3): je vier nullable Spalten an `criterion_scoring_runs` (`landmark_`-Präfix) und `remote_category_classification_runs`. `NULL` = „nicht erfasst" (Lauf aus der Zeit vor der Migration), `0` = „erfasst, keine Kosten".

**Maßgeblich für die Kategorie eines Fotos ist `photo_rankings.category_key`** des letzten erfolgreichen Laufs, nicht `photo_category_classifications.category_key`: nur ersteres ist die *wirksame* Kategorie (lokale Signale + Remote-Kandidaten + manueller Override zusammengeführt). Wiederverwendung von `api/photos.py::_latest_successful_criterion_scoring_run_id`. Ein Ranking-/Override-Wert außerhalb des festen Sets (Altbestand, Lesepfad ist laut Spec 0289 bewusst tolerant) erzeugt **keine** zusätzliche Zeile in der Verteilung und fließt in `unclassified_photo_count`, nicht in `nicht_erkannt`.

### 2. Ist-Kostenerfassung (ADR 0051)

**Messpunkt.** Beide Provider liefern den realen Verbrauch in jeder Antwort mit (Anthropic `usage.input_tokens`/`output_tokens`, Mistral `usage.prompt_tokens`/`completion_tokens`). Er wird heute gelesen und verworfen.

- `cloud_vision.py`: neu `TokenUsage(input_tokens, output_tokens)` (frozen dataclass) + `anthropic_usage_from_response()` / `mistral_usage_from_response()` — geben `None` zurück statt zu werfen; ein fehlender `usage`-Block darf eine erfolgreiche Klassifizierung nie scheitern lassen (WARNING-Zeile nach dem Muster ADR 0034 Punkt 5, ohne Rohantwort — siehe Abschnitt „Security").
- `landmark.py::LandmarkDetection` und `remote_classification.py::RemoteClassification` bekommen je ein Feld `usage: TokenUsage | None = None`. **Mit Default** — dadurch bleiben alle bestehenden Test-Doubles und die `Protocol`-Signaturen unverändert.
- `worker.py`: die Landmark-Blockschleife in `run_criterion_scoring` und die Foto-Schleife in `run_remote_category_classification` summieren Aufrufe und Tokens über die **erfolgreichen** Ergebnisse und schreiben sie zusammen mit dem einmal berechneten Betrag an die jeweilige Lauf-Zeile.
- **Verbindlich:** Die Landmark-Summen werden im bereits vorhandenen `finally`-Block der Cloud-Phase geschrieben (dort, wo auch `aclose()` läuft), **nicht** erst unmittelbar vor `status='success'`. Andernfalls verlöre ein Lauf, der nach der Cloud-Phase in der Kriterien-Phase scheitert, die bereits real angefallenen Kosten — Geld ausgegeben, Betrag `0`, und wegen `0` statt `NULL` nicht einmal als Lücke erkennbar.
- **Verbindlich:** `api_calls` zählt jeden **stattgefundenen** Aufruf, auch wenn dessen `usage`-Block fehlte (Tokenbeitrag dann 0). Sonst entsteht die stille Kombination „`api_calls == 0` bei real erfolgten Aufrufen", und die Belegkette der ADR (Tokens + Aufrufzahl neben dem Betrag) wäre wertlos — zugleich ist `api_calls > 0` der Auslöser für Befund (b) des „unvollständig erfasst"-Hinweises.

**Preisquelle.** Neues Modul `pricing.py` mit `MODEL_PRICING: dict[str, ModelPricing]`, Schlüssel ist die **Modell-ID** (`ANTHROPIC_VISION_MODEL`, `MISTRAL_VISION_MODEL` aus `cloud_vision.py`), Werte `input_usd_per_mtok`/`output_usd_per_mtok`. `compute_cost_usd(model, usage) -> float | None` ist eine reine Funktion, unit-testbar ohne DB und Netz. Unbekanntes Modell → `None` (fällt als „nicht erfasst" auf, statt sich als kostenloser Lauf zu tarnen). Code-Konstante, **kein** Settings-/env-Feld: eine Preisänderung ist eine belegpflichtige Tatsachenbehauptung mit Datum und Quelle, kein Deployment-Parameter. `remote_classification.py::COST_PER_IMAGE_USD` (Vorab-Schätzung) bleibt unverändert bestehen; beide Konstanten bekommen einen gegenseitigen Verweis („ein Preiswechsel betrifft beide").

**Unvollständigkeit.** Je Zweck wird ein Kennzeichen mitgeliefert (ADR 0051 Punkt 5, Befunde (a) und (b) — siehe Akzeptanzkriterium K5). Es wird nichts geschätzt und nichts hochgerechnet. **Währung:** USD (Abrechnungswährung beider Provider), so beschriftet, keine Umrechnung.

### 3. API-Design

**Ein Endpunkt**, neues Router-Modul `backend/src/photosort/api/stats.py` (`prefix="/projects"`, `tags=["stats"]`, in `main.py` registriert):

```
GET /projects/{project_id}/stats  ->  ProjectStatsOut
```

Ein Endpunkt statt mehrerer, weil die Seite eine **Momentaufnahme ohne Filter** ist: mehrere Endpunkte erzeugten mehrere Ladezustände für einen fachlich atomaren Stand. `current_user: User = Depends(get_current_user)` als expliziter Parameter (der Bewertungsstand braucht das `User`-Objekt) **und zusätzlich** `dependencies=[Depends(get_current_user)]` am Router — siehe „Security" Punkt 1. 404 über eine lokale `_get_project_or_404`-Kopie (dasselbe Muster existiert bereits in `api/projects.py`/`api/photos.py`); sie ist eine reine Existenzprüfung, **keine** Autorisierungsgrenze.

Response-Skizze (verschachtelte Pydantic-Modelle, gespiegelt zu den Abschnitten der Seite):

```jsonc
{
  "photo_count": 12043,
  "storage": {
    "opencloud_bytes": 48213456789,
    "local_cache_bytes": 3211234567,
    "local_database_bytes_estimate": 41234567   // null, wenn nicht Postgres
  },
  "taken_at_earliest": "2019-04-02T10:12:00",   // null bei leerem Projekt
  "taken_at_latest": "2019-04-19T18:44:00",
  "categories": {
    "classified_photo_count": 9800,
    "unclassified_photo_count": 2243,
    "entries": [ { "category_key": "strand", "display_name": "Strand",
                   "photo_count": 812, "share": 0.0829 } ]   // IMMER alle Set-Keys
  },
  "manual_category_override_count": 37,
  "cost": {
    "currency": "USD",
    "total_usd": 42.13,
    "by_purpose": [
      { "purpose": "landmark",        "cost_usd": 12.10, "has_unrecorded_runs": true },
      { "purpose": "remote_category", "cost_usd": 30.03, "has_unrecorded_runs": false }
    ]
  },
  "progress": { "scanned": 12043, "thumbnails_ready": 12040, "ausschuss_scored": 12043,
                "ranked": 9800, "remote_classified": 9800 },   // genau die fünf Stufen aus F1
  "ratings": { "favorite": 210, "album_worthy": 430, "rejected": 1200, "unrated": 10203 },
  "last_successful_runs": { "scan": "...", "scoring": "...", "classification": "...",
                            "remote_category_classification": null },
  "diagnostics": {
    "last_scan_files_skipped": 12,              // null, wenn nie gescannt
    "duplicate_photo_count": 341,
    "remote_failures": [ { "purpose": "landmark", "photo_count": 3 },
                         { "purpose": "remote_category", "photo_count": 1 } ]
  }
}
```

Festlegungen:

- **`purpose` nutzt den bestehenden `CloudVisionPhase`-Enum** (`landmark`/`remote_category`) statt eines neuen — er beschreibt bereits exakt diese beiden Zwecke und wird schon im Foto-Status verwendet. `by_purpose` und `remote_failures` enthalten immer beide Zwecke in Enum-Reihenfolge, auch mit 0.
- **`progress` führt genau die fünf Verarbeitungsstufen aus Akzeptanzkriterium F1** — maßgeblich ist F1, nicht diese Skizze: das Akzeptanzkriterium unter „Darstellung und Abgrenzung" schließt Kennzahlen über den dortigen Katalog hinaus ausdrücklich aus. Eine sechste Kennzahl „Kriterien berechnet" (`photo_criterion_scores`) entfällt deshalb; sie wäre für den Leser zudem redundant zu `ranked` (beide entstehen im selben Lauf). Die Zeile „Bearbeitungsstand" in der Datenherkunfts-Tabelle oben nennt `photo_criterion_scores` nur als eine der möglichen Quellen, nicht als eigene Kennzahl.
- **Kategorien immer vollständig**, auch mit `photo_count: 0`, in Registry-Anzeigereihenfolge inkl. `nicht_erkannt`; `display_name` kommt vom Server (ADR 0049: keine TypeScript-Spiegelung des Sets).
- **Bezugsgröße der Anteile** ist `classified_photo_count`; `unclassified_photo_count` macht die Differenz explizit. Es gilt `classified + unclassified == photo_count`.
- **`total_usd` wird serverseitig ungerundet ausgeliefert** und erst im Frontend formatiert, damit die Summe exakt der Summe der Einzelposten entspricht.
- Antwort ausschließlich über explizite Pydantic-`response_model`-Klassen, kein Durchreichen von ORM-Objekten.

**Performance.** Alle Aggregate sind `COUNT`/`SUM`/`GROUP BY` mit `project_id`-Skopierung; verwandte Zähler werden über `func.count().filter(...)` auf gemeinsamer `FROM`-Klausel gebündelt (Ziel: rund 6–8 Queries statt 15, kein N+1, insbesondere **kein** Query je Kategorie). Neue Indizes sind nicht nötig: `photos` ist über `uq_photo_project_path` mit `project_id` als führender Spalte abgedeckt, die Kindtabellen über ihren PK/Unique auf `photo_id`, `photo_rankings` über `uq_photo_ranking_run_photo`.

### 4. Speicherbedarf

- **OpenCloud:** `SUM(photos.content_length)` — kein OpenCloud-Zugriff nötig, der Wert liegt seit dem Scan in der DB.
- **Thumbnail-Cache:** neue reine Funktion `thumbnails.py::measure_cache_usage(cache_dir, photos) -> CacheUsage(total_bytes, complete_photo_count)`; `os.stat` auf `thumbnail_path`/`display_path` je Foto. Gehört in `thumbnails.py`, weil dort die Pfadbildung lebt, und ist mit `tmp_path` ohne DB testbar. Aufruf aus dem Endpunkt über `await asyncio.to_thread(...)`, damit die Event-Loop nicht blockiert. Der Messlauf liefert **`progress.thumbnails_ready` als Nebenprodukt** (Fotos mit *beiden* Varianten) — kein zweiter Durchlauf. Dateien mit veraltetem `etag`-Cache-Schlüssel zählen weder Bytes noch als fertig.
- **Datenbank-Anteil:** `SELECT pg_database_size(current_database())`, anteilig nach dem Fotoanteil des Projekts. Die Aufteilungsrechnung ist eine reine, unit-getestete Funktion (0 Gesamtfotos → kein `ZeroDivisionError`). Die Dialekt-Weiche läuft über `session.get_bind().dialect.name == "postgresql"`, **nicht** über ein `try/except` um fehlschlagendes SQL; außerhalb Postgres ist der Wert `None`. Feldname trägt `_estimate`, die Oberfläche beschriftet den Wert als Schätzung und unterscheidet `None` („nicht ermittelbar") sichtbar von `0`.

### 5. Frontend

| Datei | Änderung |
|---|---|
| `frontend/src/App.tsx` | Route `/projects/:projectId/stats` in `PROJECT_ROUTES` — bekommt dadurch automatisch den Sticky-Header-Projektlink |
| `frontend/src/pages/pipeline/ProjectPipelineLayout.tsx` | Einziger Einstiegspunkt: Sekundär-Button „Statistik" in der bestehenden `<nav>` neben „Einstellungen" |
| `frontend/src/pages/ProjectStatsPage.tsx` (neu) | Seite; Lade-/Fehler-/404-Zustände nach dem `ProjectSettingsPage`-Muster |
| `frontend/src/api/projects.ts` | `getProjectStats(id)` — als Projekt-Unterressource hier, konsistent mit `listFineLabels` |
| `frontend/src/api/types.ts` | `ProjectStatsOut` + verschachtelte Typen |
| `frontend/src/hooks/useProjects.ts` | `useProjectStatsQuery(id)` — **ohne** `refetchInterval` (Momentaufnahme), mit `refetchOnWindowFocus: false` und `staleTime` (siehe „Security" Punkt 3), Query-Key inkl. angemeldeter Identität (siehe „Security" Punkt 2) |
| `frontend/src/utils/formatStats.ts` (neu) | `formatBytes` (MB/GB, de-DE), `formatUsd`, `formatPercent` — reine Funktionen, eigene Unit-Tests |

Die Seite bleibt bewusst **außerhalb** der Pipeline-Schritt-Routen (`/pipeline/:step`): sie ist kein Schritt des Ablaufs, sondern eine Querschnittsansicht — dieselbe Einordnung wie die Einstellungsseite.

### 6. Migration

Eine additive Revision `<hash>_remote_cost_tracking.py` auf `e2f3a4b5c6d7`, nach dem Muster von `e2f3a4b5c6d7_classification_run_cloud_phase.py`:

- `op.batch_alter_table(...)` je Tabelle, acht `add_column` (`sa.Integer()`/`sa.Float()`, alle `nullable=True`, **kein** Server-Default — Bestandszeilen sollen genau `NULL` = „nicht erfasst" behalten).
- `downgrade()` verlustbehaftet, aber schema-vollständig umkehrbar.
- Ausführlicher Docstring mit der `NULL`-vs.-`0`-Semantik.
- Migrationstest nach dem etablierten Muster plus Erweiterung von `test_postgres_ddl_compatibility.py` (siehe Teststrategie).

### 7. Umsetzungsreihenfolge (verbindlich)

1. **`pricing.py` + `cloud_vision.py`** — `TokenUsage`, die beiden `*_usage_from_response`-Extraktoren, `MODEL_PRICING`, `compute_cost_usd`. Reine Funktionen, vollständig ohne DB/Netz testbar; hier die Preise beider Modelle mit Datum und Quelle im Kommentar belegen (wie bei `COST_PER_IMAGE_USD`).
2. **Clients** — `usage`-Feld an `LandmarkDetection`/`RemoteClassification` (mit Default), Befüllung in den vier Client-Implementierungen; Tests über `httpx.MockTransport` inklusive „Antwort ohne `usage`-Block".
3. **Modelle + Migration + Migrationstest** — acht Spalten, `NULL`/`0`-Semantik im Docstring.
4. **Worker** — Summierung in `run_criterion_scoring` (Landmark-Block, Schreiben im `finally`) und `run_remote_category_classification`. Teilfehlschläge dürfen die Summen nicht verfälschen.
5. **`api/stats.py`** — Pydantic-Modelle, Aggregat-Queries, Registrierung in `main.py`, Ergänzung in `test_auth_guard.py::_protected_router_operations()`. Zuerst die reinen DB-Kennzahlen, dann Kosten, zuletzt Speicher/Dateisystem.
6. **`thumbnails.py::measure_cache_usage`** + Einbindung über `asyncio.to_thread`.
7. **Frontend** — Typen/API/Hook, `formatStats.ts`, Seite, Route, Nav-Einstieg.
8. **Doku im selben PR nachziehen:** `docs/architecture.md` (Datenmodell: acht neue Spalten an beiden Run-Tabellen; Komponenten: `api/stats.py`, `pricing.py`). Testkonzept und Sicherheitskonzept sind bereits mit dieser Spec ergänzt worden — dort ist bei der Umsetzung nur nachzuziehen, was als „wird bei tatsächlicher Umsetzung um verifizierte Werte aktualisiert" markiert ist. Keine Änderung an `docs/setup.md`/`.env.example` — es kommt **keine** neue Umgebungsvariable hinzu.

Schritte 1–4 sind die eigentliche Neuerung (ADR 0051) und liefern ab Schritt 4 bereits echte Kostendaten; 5–7 sind Lesen und Darstellen.

### Betroffene Dateien

`backend/src/photosort/pricing.py` (neu), `api/stats.py` (neu), `cloud_vision.py`, `landmark.py`, `remote_classification.py`, `worker.py`, `models.py`, `thumbnails.py`, `main.py`, `alembic/versions/<neu>.py`; `frontend/src/pages/ProjectStatsPage.tsx` (neu), `utils/formatStats.ts` (neu), `App.tsx`, `api/projects.ts`, `api/types.ts`, `hooks/useProjects.ts`, `pages/pipeline/ProjectPipelineLayout.tsx` — jeweils plus Tests. Unverändert: `criteria.py`, `categories.py`, `ranking.py`, `classification.py`.

### Bekannte Grenzen (bewusst akzeptiert)

- **Läufe vor der Migration bleiben dauerhaft ohne Kostenangabe** — beabsichtigt, nicht nachholbar, in der Story ausdrücklich so gewollt.
- **Befund (a) des Unvollständigkeits-Hinweises hat beim Zweck `landmark` eine Blindstelle:** ein Altlauf, der Aufrufe abgesetzt, aber keine Sehenswürdigkeit gefunden hat, hinterlässt keine Ergebniszeile und löst den Hinweis nicht aus. Für Läufe nach der Migration schließt Befund (b) die Lücke; für Altläufe ist sie nicht schließbar, weil die Aufrufzahl von damals nirgends existiert. Per Test festgeschrieben.
- **Fehlgeschlagene Aufrufe tragen nichts zur Kostensumme bei** (ADR 0051 Punkt 6) — bei abgelehnten Requests fallen real keine Kosten an, bei einem Timeout nach begonnener Generierung entsteht eine kleine, nicht messbare Untererfassung. Die Fehlschläge selbst werden auf derselben Seite ausgewiesen.
- **Der Datenbank-Anteil ist eine Schätzung** und außerhalb Postgres gar nicht ermittelbar; die Oberfläche beschriftet ihn entsprechend.
- **Zwei Preiskonstanten** (Schätzung pro Bild, Ist-Preis pro Token) müssen bei einem Modell-/Preiswechsel gemeinsam gepflegt werden; beide tragen dazu einen gegenseitigen Verweis.

## UI/UX

Die Seite folgt dem Schema von `ProjectSettingsPage` und dem Scan-Schritt: mehrere fokussierte `<section>`-Blöcke mit `<h2>`-Überschrift statt einer Kachelwand. Kein Karten-Chrome, sondern Whitespace und Abschnittsgrenzen — konsistent mit dem Prinzip „Chrome tritt zurück" aus [`0004-design-system.md`](../architecture/0004-design-system.md). Keine neue Komponentenbibliothek, keine neue Abhängigkeit, insbesondere kein Diagramm-/Chart-Paket.

**Reihenfolge der Blöcke** (oben das, was zuerst überblickt werden soll):

1. Umfang und Speicher (inkl. Zeitraum der Aufnahmen)
2. Kosten für Remote-Berechnungen
3. Bearbeitungs- und Bewertungsstand
4. Kategorienverteilung
5. Vertrauen und Fehlersuche (letzte Läufe, übersprungene Dateien, Remote-Fehler, Duplikate)

**Kennzahl-Darstellung.** Wiederkehrendes Muster „Großzahl + Label": Wert in `text-2xl font-medium`, darunter das Label in `text-sm`. Rein typografisch, kein eigener Hintergrund, kein Rahmen. Mehrere Kennzahlen stehen auf breiten Schirmen nebeneinander (`flex flex-wrap gap-*`), auf dem Smartphone gestapelt. Dieses Muster wird im Design-System unter „Wiederkehrende Muster" aufgenommen (Aufgabe des `ux-ui-designer`, sobald die Umsetzung die endgültige Form zeigt — die Spec schreibt keine vorauseilende Dokumentation fest).

**Speicher.** Die beiden Werte stehen als gleichrangige Kennzahlen nebeneinander, beschriftet „Originaldateien in OpenCloud" und „Lokal belegt (Thumbnail-Cache + Datenbestand)". Der lokale Wert weist seine zwei Anteile darunter kleiner aus; der Datenbank-Anteil trägt den Zusatz „geschätzt" und bei `null` den Text „nicht ermittelbar" statt einer Zahl.

**Kategorienverteilung** als semantische `<table>` (`<thead>`, `<th scope="col">`), eine Zeile je Kategorie des Sets — auch mit Anzahl 0, in der vom Server gelieferten Reihenfolge, mit dem vom Server gelieferten Anzeigenamen. Spalten: Kategorie, Anzahl, Anteil. Kein Balken-/Kreisdiagramm und keine Verlaufsdarstellung. Die Zahl der manuell korrigierten Fotos steht als eigene Kennzahl **unter** der Tabelle, nicht als Spalte — sie ist projektweit, nicht je Kategorie. „Nicht klassifiziert" steht ebenfalls als eigene Kennzahl daneben und ist damit sichtbar von der Kategorie „Nicht erkannt" unterschieden.

**Textbausteine für fehlende und unvollständige Werte** (deutsch, wörtlich zu verwenden):

| Fall | Text |
|---|---|
| Zahlwert 0 | die Zahl „0" bzw. „0 MB" — nie „—" |
| Zeitraum bei leerem Projekt | „—" mit Erläuterung „Noch keine Fotos im Projekt." |
| Lauf nie ausgeführt | „noch nie gelaufen" |
| Kein Scan-Lauf vorhanden | „noch nie gescannt" |
| Datenbank-Anteil nicht ermittelbar | „nicht ermittelbar" mit Erläuterung „Der Datenbank-Anteil lässt sich nur bei einer PostgreSQL-Datenbank abschätzen." |
| Kosten unvollständig erfasst | „Summe unvollständig erfasst" mit Erläuterung „Für mindestens einen Lauf dieses Zwecks liegen keine Verbrauchsdaten vor. Es wird bewusst nichts geschätzt — der angezeigte Betrag ist die Summe des tatsächlich Erfassten." |
| Betrag > 0, der auf 0,00 rundet | „< 0,01 USD" |

Der Unvollständigkeits-Hinweis erscheint je Zweck unmittelbar bei dessen Betrag, in der dezenten Hinweis-Form des Design-Systems (kein Fehler-Rot — es ist kein Fehler, sondern eine Einschränkung der Aussage).

**Erläuterungen.** Wiederverwendung der bestehenden Muster, nichts Neues: das vorhandene Info-Popover (Radix, Klick-Auslöser, 44×44 px Trefferfläche) für mehrzeilige Erklärungen an einer einzelnen Kennzahl; natives `<details>/<summary>` wie im Scan-Schritt für kurze Erklärungen auf Abschnittsebene. **Kein `title`-Attribut** (auf Touchgeräten unzuverlässig). Erläutert werden mindestens die in Akzeptanzkriterium A2 genannten Kennzahlen.

**Zustände.**

- *Laden:* Inline-Ladeanzeige nach dem Muster der bestehenden Projektseiten, kein Vollbild-Spinner.
- *Fehler:* `Alert`-Banner mit der Server-`detail`-Nachricht, die Seite bleibt bedienbar.
- *404:* kurzer Text „Projekt nicht gefunden." wie in `ProjectSettingsPage`, keine Statistikblöcke.
- *Leeres Projekt:* die Seite wird **vollständig** mit Nullwerten gerendert. Kein „Projekt ist leer"-Sonderzustand und kein Onboarding-Banner — der Nullzustand ist der normale Anfangszustand, kein Fehlersignal.

**Responsivität und Barrierefreiheit.** Mobile first ab 320 px; kein horizontales Scrollen — die Kategorientabelle reduziert auf schmalen Schirmen die Anteilsspalte nicht, sondern bricht Zellinhalte um. Tabellen bleiben semantisch (`<table>`/`<th scope="col">`), Kennzahlen tragen ihre Einheit im Text (`formatBytes` liefert „2,3 GB", kein separates `aria-label`), große Zahlen mit deutschem Tausenderpunkt. Bedienelemente gibt es außer dem Einstiegs-Button und den Popover-Auslösern keine.

## Teststrategie

Grundlage: [`0002-testkonzept.md`](../architecture/0002-testkonzept.md), das im Zuge dieser Spec um die Abschnitte zu Preis-Registries, aggregierenden Nur-Lese-Endpunkten und dialektabhängigem SQL ergänzt wurde. Schwerpunkt bleibt die **Integrations-Ebene** (echte In-Memory-SQLite, `httpx.ASGITransport`, Fakes nur an der Außenschnittstelle).

### Unit-Ebene (reine Funktionen, kein I/O)

| Testdatei | Gegenstand | AK |
|---|---|---|
| `backend/tests/test_pricing.py` (neu) | `compute_cost_usd`: beide bepreisten Modelle, exakte MTok-Skalierung (1 000 000 Input-Token = genau `input_usd_per_mtok`), Input/Output getrennt gewichtet, `TokenUsage(0, 0)` → `0.0` (nicht `None`), **unbekannte Modell-ID → `None`**. Zusätzlich eine **Registry-Vollständigkeits-Invariante**: jede in `cloud_vision.py` geführte Modell-ID hat einen `MODEL_PRICING`-Eintrag (analog zu `CATEGORY_REGISTRY`/`CRITERION_REGISTRY`) — der einzige automatisierte Schutz gegen einen Modellwechsel ohne Preispflege. | K3 |
| `backend/tests/test_cloud_vision.py` (erweitert) | Die beiden `*_usage_from_response`: Happy Path mit den **providereigenen Feldnamen**; fehlender `usage`-Block → `None` + genau eine WARNING (`caplog`); Feld fehlt / falscher Typ → `None` statt `TypeError`; **Kreuz-Test**, dass der Anthropic-Extraktor keine Mistral-Feldnamen akzeptiert und umgekehrt. | K3 |
| `backend/tests/test_landmark.py`, `test_remote_classification.py` (erweitert) | Konstruktion **ohne** `usage` (Default `None`, Bestandsschutz für vorhandene Test-Doubles); echter Client füllt `usage` aus präparierter Antwort. | K3 |
| `backend/tests/test_thumbnails.py` (erweitert) | `measure_cache_usage` gegen `tmp_path`: Verzeichnis fehlt, leer, nur Thumbnail, nur Display, beide, veralteter `etag`, fremde Datei. `complete_photo_count` = Fotos mit **beiden** Varianten. | S2, F1 |
| `backend/tests/test_api_stats.py` (neu, Unit-Teil) | Anteilsrechnung für `local_database_bytes_estimate`: 0 Gesamtfotos (kein `ZeroDivisionError`), Projekt mit 0 von n Fotos, Einzelprojekt (Anteil 1,0). | S2 |

### Integrations-Ebene (Schwerpunkt)

| Testdatei | Gegenstand | AK |
|---|---|---|
| `backend/tests/test_api_stats.py` (neu) | `GET /projects/{id}/stats`: 200 mit vollständig befülltem Projekt; **leeres Projekt** (Nullwerte, kein 500); 404 für unbekannte ID; 401 ohne Token. **In jedem Aggregationstest existiert ein zweites Projekt** mit eigenen Fotos, Läufen, Fehler-Zeilen und Bewertungen — kein Wert darf projektübergreifend lecken. | alle |
| `backend/tests/test_auth_guard.py` (erweitert) | `stats.router` wird in `_protected_router_operations()` ergänzt, sonst gilt die 401-Vollständigkeitsgarantie für den neuen Router nicht. | Zugang |
| `backend/tests/test_worker_criterion_scoring.py` (erweitert) | Summierung im Landmark-Block: mehrere Erfolge → Summen an der Lauf-Zeile; **Teilfehlschlag** trägt nichts bei und lässt `photo_cloud_vision_errors` unverändert; Ergebnis ohne `usage` → Lauf erfolgreich, WARNING, `api_calls` trotzdem erhöht; unbekannte Modell-ID → Tokens erfasst, `landmark_cost_usd is None`; Lauf ohne Cloud-Nutzung → Spalten `0`, nicht `NULL`; **Lauf scheitert nach dem Landmark-Block → die bereits angefallenen Kosten stehen trotzdem an der Lauf-Zeile** (`finally`-Schreiben); zweiter Lauf trägt nur seine eigenen Kosten; `aclose()` weiterhin genau einmal. | K3, K5 |
| `backend/tests/test_worker_remote_category_classification.py` (erweitert) | dieselben Fälle für `api_calls`/`input_tokens`/`output_tokens`/`cost_usd`; früher Erfolgs-Rückweg (Cloud aus **oder** keine Kandidaten) → Spalten `0`. | K3 |
| `backend/tests/test_models.py` (erweitert) | Frische Run-Zeilen tragen Python-Default `0`; `NULL` bleibt für alle acht Spalten darstellbar. | K5 |

### Migration und Dialekt

| Testdatei | Gegenstand |
|---|---|
| `backend/tests/test_migration_ist_kostenerfassung.py` (neu) | Muster der bestehenden `test_migration_*.py` (`down_revision == "e2f3a4b5c6d7"`): alle acht Spalten existieren nach `upgrade` und sind nullbar, **Bestandszeilen behalten `NULL`** (nicht `0` — sonst wäre „nicht erfasst" von „kostenlos" nicht mehr unterscheidbar), `downgrade` entfernt sie wieder. |
| `backend/tests/test_postgres_ddl_compatibility.py` (erweitert) | Rendern der neuen Revision gegen den Postgres-Dialekt: acht `ADD COLUMN`, Typen `INTEGER`/`DOUBLE PRECISION`, **kein `DEFAULT` im erzeugten DDL** (Nachweis, dass der Python-Default nicht zum Server-Default wird). |
| `backend/tests/test_api_stats.py` (Dialekt-Teil) | Die `pg_database_size`-Abfrage wird gegen den Postgres-Dialekt **kompiliert und das SQL geprüft**; der Dialekt-Zweig läuft gegen ein Fake-Bind (`dialect.name`) mit Stub-`execute`; unter SQLite liefert der Endpunkt `local_database_bytes_estimate is None`. Kein `# pragma: no cover`. |

### Frontend (`vitest` + Testing Library)

| Testdatei | Gegenstand | AK |
|---|---|---|
| `frontend/src/utils/formatStats.test.ts` (neu) | `formatBytes` (0, unter/über/exakt an der MB→GB-Grenze, de-DE-Dezimalkomma, `null` → „—"), `formatUsd` (0 → „0,00 USD"; Betrag unter einem Cent → „< 0,01 USD"), `formatPercent` (0 %, Rundung, Bruch 0…1 als Eingabe). | S1, K4, K1 |
| `frontend/src/api/projects.test.ts` (erweitert) | `getProjectStats(id)` ruft `/projects/{id}/stats`, reicht `ApiError` durch. | Zugang |
| `frontend/src/pages/ProjectStatsPage.test.tsx` (neu) | Lade-/Fehler-/404-Zustand; **leeres Projekt** rendert Nullwerte ohne `NaN`/`Infinity`; volles Projekt; Kategorietabelle rendert **alle** Set-Keys inkl. `nicht_erkannt` in Server-Reihenfolge mit dem **vom Server gelieferten** Anzeigenamen (Regressionsschutz gegen eine zweite Label-Tabelle im Client); Kostenblock mit/ohne Unvollständigkeits-Hinweis je Zweck; `local_database_bytes_estimate: null` → „nicht ermittelbar" statt „0 B"; beide Speicherwerte tragen wörtlich geprüfte, unterschiedliche Beschriftungen; Bewertungsblock ist als **eigene** Bewertung beschriftet; **Negativ-Assertions zum Scope**: kein Filter-, Export-, Sortier- oder Auslöse-Bedienelement, keine Foto-Kacheln. | A1, A2, A3, S2, K1, K5, F2 |
| `frontend/src/hooks/useProjects.test.tsx` (erweitert) | `useProjectStatsQuery`: Query-Key enthält Projekt-ID und angemeldete Identität; **kein Polling** — mit `vi.useFakeTimers` mehrere Minuten vorspulen, genau ein API-Aufruf. | A3 |
| `frontend/src/pages/pipeline/ProjectPipelineLayout.test.tsx` (erweitert) | Sekundär-Button „Statistik" existiert und zeigt auf `/projects/{id}/stats`. | Zugang |
| `frontend/src/App.test.tsx` (erweitert) | `/projects/1/stats` in der `PROJECT_ROUTES`-Liste des parametrisierten Header-Tests — sonst fehlt der Sticky-Header-Projektlink stillschweigend (Alt-Bug aus Spec 0042/PR #101). | Zugang |

### Edge Cases, die sonst durchrutschen

1. **`Photo.taken_at` ist NOT NULL** (der Scan fällt auf `last_modified` zurück) — „Foto ohne Aufnahmedatum" ist am Datenmodell nicht darstellbar, dafür wird kein Test gebaut. Real sind: leeres Projekt (beide Werte `null`) und `earliest == latest`.
2. **`SUM(content_length)` liefert bei 0 Fotos `NULL`, nicht `0`** — serverseitig normalisieren.
3. **Anteil bei 0 klassifizierten Fotos** → alle `share` 0, Einträge existieren trotzdem.
4. **`_latest_successful_criterion_scoring_run_id` sortiert nach `started_at DESC`:** jeder Test mit mehr als einem Lauf muss `started_at` **explizit** setzen, sonst identischer Server-Default-Zeitstempel und sporadisch rotes CI. Fachlich zusätzlich: ein neuerer **fehlgeschlagener** Lauf darf den älteren erfolgreichen nicht verdrängen.
5. **Projekt mit Fotos, aber ohne erfolgreichen Scoring-Lauf** → alles „nicht klassifiziert", kein „nicht_erkannt = 100 %".
6. **Invariante `classified + unclassified == photo_count`** in jedem Aggregationstest mitprüfen (Ausschuss-/Duplikat-Fotos landen nicht in `photo_rankings`).
7. **`category_override` wirkt bereits im Worker** und steckt in `photo_rankings.category_key`: ein Foto mit Override erscheint genau einmal unter der überschriebenen Kategorie **und** im Override-Zähler.
8. **Ranking-/Override-Wert außerhalb des Sets** (Altbestand): keine zusätzliche Tabellenzeile, kein 500 — fließt in „nicht klassifiziert".
9. **Zweites Projekt** mit Daten in jeder aggregierten Tabelle, in jedem Aggregationstest.
10. **Zweitnutzer-Test:** nur der andere Nutzer hat bewertet → alle Fotos „noch nicht bewertet"; beide haben dasselbe Foto unterschiedlich bewertet → das Foto zählt genau einmal, unter dem Status des angemeldeten Nutzers. Invariante: Summe der vier Werte == `photo_count`.
11. **Vierfeldertafel des Unvollständigkeits-Hinweises:** (a) nur erfasste Läufe → Betrag, kein Hinweis; (b) erfasst + `NULL` mit Ergebniszeilen → Betrag + Hinweis; (c) nur `NULL` mit Ergebniszeilen → `0.0` + Hinweis; (d) **`NULL`-Läufe ohne Ergebniszeilen → `0.0` ohne Hinweis**; (e) Lauf mit `api_calls > 0` und `cost_usd` `NULL`/`0` → Hinweis (Befund b).
12. **`by_purpose` und `remote_failures` enthalten immer beide Zwecke**, auch bei 0.
13. **Landmark-Blindstelle** (Altlauf ohne gefundene Sehenswürdigkeit, siehe „Bekannte Grenzen") als dokumentiertes Verhalten festschreiben.
14. **Zweiter Lauf ohne neue Kandidaten** → 0 Aufrufe, `0`-Spalten, Projektsumme unverändert (prüft zugleich, dass über Läufe **summiert** und nicht der letzte gelesen wird).
15. **Rundung:** Summe der `by_purpose`-Beträge == `total_usd`.
16. **Cache:** Verzeichnis fehlt → `CacheUsage(0, 0)`; teilweise vorhandenes Variantenpaar; veralteter `etag` trägt weder Bytes noch `thumbnails_ready` bei.
17. **Nicht-Postgres:** `local_database_bytes_estimate is None`, in der Anzeige „nicht ermittelbar", nicht „0 B".
18. **`photo_cloud_vision_errors` ist Ist-Zustand** (ADR 0035: erfolgreicher Retry löscht die Zeile) — Test: nach erfolgreichem Retry sinkt der Fehlerzähler.
19. **Duplikate zählen Fotos, nicht Cluster:** ein Cluster aus drei Fotos ergibt **zwei** Duplikate.
20. **Übersprungene Dateien:** bei mehreren Scan-Läufen der zuletzt gestartete; ohne Scan-Lauf `null`, nicht `0`.

### Bewusst nicht automatisiert abgesichert

- Kein E2E-Test (Projektlinie unverändert).
- Die inhaltliche **Richtigkeit von `MODEL_PRICING`** gegen echte Anbieter-Abrechnungen — als bekannte Lücke im Testkonzept geführt, Ersatzverfahren: Abgleich der ersten realen Rechnung mit der Summe auf der Statistikseite; bei Abweichung Konstante korrigieren und Beträge aus den gespeicherten Tokens neu berechnen.
- Die **tatsächlichen `usage`-Feldnamen** der echten Provider-Antworten (nur gegen Fakes geprüft) — ebenfalls als bekannte Lücke geführt; Alarmzeichen ist ein Lauf mit Aufrufen, aber 0 Token.
- Antwortzeit und Query-Anzahl des Endpunkts (keine Performance-Tests im Projekt); N+1-Vermeidung bleibt Review-Aufgabe.

### Coverage-Gate

Das 80 %-Gate greift hier praktisch nicht: der Ist-Stand liegt bei 96 % (2913 Statements), diese Spec dürfte rund 570 vollständig ungetestete Statements hinzufügen, bevor die Marke reißt. Deshalb gilt **modulweise** statt global: `photosort/pricing.py`, `photosort/api/stats.py` sowie die geänderten Zeilen in `worker.py`/`thumbnails.py`/`cloud_vision.py` erreichen jeweils **≥ 95 %** mit leerer „Missing"-Spalte (`pytest --cov=photosort --cov-report=term-missing`), und die Gesamtabdeckung fällt durch diese Spec nicht unter 95 %. Jeder defensive Zweig (`is None`, `or 0`, fehlender Lauf, fehlender Scan) bekommt einen eigenen Fall aus der Edge-Case-Liste. Der `pg_database_size`-Pfad braucht **kein** `# pragma: no cover` (siehe Dialekt-Tests). Das Frontend hat weiterhin kein Gate — die oben genannten Testdateien sind daher Pflicht, nicht optional.

## Security

`security-engineer`-Konsultation: **sicherheitsrelevant, kein Blocker.** Vier Anknüpfungspunkte — neuer Endpunkt mit endpunkteigener Auth-Durchsetzung, personenbezogener Bewertungsstand, erster Dateisystem-/Datenbank-Introspektionspfad im Request-Zyklus, neuer Datenpfad aus Provider-Antworten inkl. Logging. Die Seite ist reine Anzeige: sie löst keinen Lauf aus, schreibt nichts und verursacht keine Provider-Kosten. [`0003-securitykonzept.md`](../architecture/0003-securitykonzept.md) wurde im Zuge dieser Spec ergänzt.

### 1. Auth-Durchsetzung am neuen Endpunkt

`GET /projects/{project_id}/stats` braucht das `User`-Objekt (Bewertungsstand), deshalb `current_user: User = Depends(get_current_user)` als expliziter Parameter — Muster wie `api/photos.py`/`api/ratings.py`.

- **Muss:** Der neue Router in `api/stats.py` bekommt **zusätzlich** `dependencies=[Depends(get_current_user)]`. FastAPI cached die Dependency innerhalb eines Requests (identischer Callable, identische SecurityScopes), der Torwächter kostet also weder eine zweite JWT-Prüfung noch ein zweites `session.get(User, ...)`. Er ist nötig, weil `stats.py` ein **neu angelegtes** Modul ist: ohne Router-Ebene hinge die Absicherung eines künftigen zweiten Endpunkts allein daran, dass niemand den Parameter vergisst. Die historische `photos.py`-Abweichung bleibt bestehen, wird aber für neue Module nicht fortgeschrieben.
- **Muss (Test):** 401 ohne `Authorization`-Header; 401 bei ungültigem/abgelaufenem Token; **401 statt 404 bei fehlendem Token auf eine nicht existierende `project_id`** — sonst wäre die Existenz von Projekt-IDs unauthentifiziert abfragbar.
- **Keine Projekt-Zugehörigkeitsprüfung** — es gibt kein projektbezogenes Berechtigungsmodell, beide Nutzer dürfen alle Projekte sehen (bereits als bewusst akzeptiertes Restrisiko im Sicherheitskonzept geführt). Die lokale `_get_project_or_404`-Kopie ist eine reine Existenzprüfung und darf im Code nicht als Autorisierungsgrenze kommentiert werden.
- **Muss:** Antwort ausschließlich über explizite Pydantic-`response_model`-Klassen, kein Durchreichen von ORM-Objekten.

### 2. Datensichtbarkeit zwischen den beiden Nutzern

Der Bewertungsstand ist die erste rein **personenbezogene Aggregatzahl** der Anwendung.

- **Muss:** Ermittlung ausschließlich über `Rating.user_id == current_user.id`, `user_id` stammt allein aus dem JWT — der Endpunkt hat keinen `user_id`-Parameter in Pfad, Query oder Body.
- **Muss:** „Noch nicht bewertet" wird als `photos_total − eigene Bewertungen` berechnet, **nie** als `photos_total − COUNT(ratings)` oder über ein `EXISTS(Rating …)` ohne User-Filter. Beide Varianten zählen die Bewertungen der anderen Person mit und machen deren Fortschritt aus der Differenz rekonstruierbar.
- **Muss (Test):** Fixture mit **zwei** Nutzern, bei der der zweite Fotos bewertet hat, die der erste nicht bewertet hat — der Aufruf als Nutzer 1 muss exakt dieselben Zahlen liefern wie ohne Nutzer 2.
- **Geprüft, unkritisch:** Kategorienverteilung inkl. `category_override`, Duplikate, übersprungene Dateien, Cloud-Fehler, Lauf-Zeitpunkte, Speicher- und Kostenzahlen tragen im Datenmodell keinen `user_id` und sind projektweit.
- **Muss (negativ):** Die Antwort schlüsselt **keine** Kennzahl nach Nutzer auf und enthält weder `user_id` noch `username` einer anderen Person, auch nicht implizit über „zuletzt geändert von".
- **Muss (Frontend):** Der Query-Key von `useProjectStatsQuery` enthält die angemeldete Identität. Grund: die Anmeldung ist eine reine SPA-Navigation ohne Full Reload, und der `QueryClient` wird beim Nutzerwechsel nicht geleert — auf einem gemeinsam genutzten Familiengerät zeigte der zweite Nutzer sonst kurzzeitig den zwischengespeicherten Bewertungsstand des ersten.

### 3. Speicher-Kennzahlen

- **Muss (kein Pfad-Leck):** `measure_cache_usage` behandelt `OSError` je Datei best-effort (`FileNotFoundError` → 0 Bytes). Ein `OSError` darf **nie** in `HTTPException(detail=...)` oder in ein Antwortfeld überführt werden — seine Meldung enthält den absoluten Cache-Pfad, also interne Deployment-Struktur.
- **Muss (kein Path Traversal):** Cache-Pfade entstehen ausschließlich aus `settings.photo_cache_dir` + den `thumbnails.py`-Helfern (SHA256-`cache_key` aus `photo_id`+`etag`); `measure_cache_usage` nimmt nie einen vom Client stammenden String entgegen. Der einzige Eingabewert des Endpunkts (`project_id: int`) geht in keinen Pfad ein.
- **Muss (Selbst-DoS begrenzen):** Der Cache ist ein flaches Verzeichnis ohne Projektzuordnung, eine projektbezogene Messung braucht zwei `os.stat` je Foto. Gegenmaßnahmen: Ausführung über `asyncio.to_thread` (Event-Loop blockiert nie) **und** `refetchOnWindowFocus: false` plus `staleTime > 0` (z.B. 60 s) am Hook — der `QueryClient` läuft sonst auf den Defaults und löst bei jedem Tab-Wechsel einen vollständigen neuen Scan aus. Kein Polling.
- **Bewusst akzeptiertes Restrisiko:** kein eigenes Rate-Limiting für diesen Endpunkt (`slowapi` hängt projektweit nur am Login). Der Endpunkt ist auth-pflichtig, und die Missbrauchswirkung (CPU/IO auf dem eigenen Homeserver) ist um Größenordnungen kleiner als beim bereits akzeptierten Fall `POST .../classify` (echtes Geld).
- **Muss:** Die Dialekt-Weiche wird über `session.get_bind().dialect.name == "postgresql"` entschieden, **nicht** über ein `try/except` um fehlschlagendes SQL — ein DBAPI-Fehlertext kann Datenbank-/Host-/Verbindungsangaben enthalten. Das SQL ist ein statisches Literal mit `current_database()`, nie ein per f-String zusammengesetzter Datenbankname.

### 4. Kostendaten, Preistabelle, `usage`-Auslesen

- **Preise und Tokenzahlen sind nicht schützenswert** (öffentliche Listenpreise, reine Zähler): `pricing.py` fällt nicht unter das Secrets-Handling. Die Code-Konstante statt eines `.env`-Feldes ist zugleich die sicherheitsfreundlichere Variante, weil eine Preisänderung nur über einen reviewten Commit geht.
- Der ausgewiesene **Betrag** ist private Ausgabeninformation der Familie: nur über den auth-pflichtigen Endpunkt, nie in einer Log-Zeile, nie in einer Fehlermeldung an den Client.
- **Muss — kein Rohantwort-Logging.** Die WARNING-Zeile bei fehlendem/unerwartetem `usage` folgt ADR 0034 Punkt 5 und enthält ausschließlich: feste Meldung, `type(exc).__name__`, Modell-ID sowie `photo.id`/`run.id`. **Verboten:** `payload`, `repr(payload)`, `response.text`, `response.json()`, `response.headers`, `exc_info=True`. Die Provider-Antwort enthält die Modellaussage über den **Bildinhalt** eines Familienfotos, im Fehlerfall potenziell ein Echo des Requests (Base64-Bilddaten) und Header (API-Key).
- **Muss (Test):** Ein Test mit strukturell kaputtem `usage`-Block prüft per `caplog`, dass die geloggte Zeile weder Rohtext der Provider-Antwort noch Base64-Anteile noch den API-Key enthält — nicht nur, dass überhaupt geloggt wurde.
- **Muss:** `compute_cost_usd` liefert bei unbekannter Modell-ID `None`, nie ein stilles `0.0` — auch sicherheitsrelevant als Beobachtbarkeit: ein stilles `0.0` würde unerwartet viele Läufe unter einem neuen Modell (z.B. über ein gestohlenes JWT) als „kostenlos" tarnen.
- **Keine neue Missbrauchsfläche:** `/stats` liest nur. Die Seite macht die Ist-Kosten erstmals sichtbar und wirkt damit eher als Erkennungsmechanismus für den bereits dokumentierten Missbrauchsfall „gestohlenes JWT → teure Läufe".
- **Frontend:** alle Zahlen und ggf. mitangezeigter Fremdtext rendern ausschließlich als React-Textknoten, nie `dangerouslySetInnerHTML`.

## Entscheidungen

- **Detailtiefe der Kostenerfassung: Tokens + Aufrufzahl + Betrag** (Daniel, `spec-writer`-Ablauf). Einzige Variante, die „beruht auf dem tatsächlichen Verbrauch" wörtlich erfüllt; ein später erkannter Preisfehler bleibt für Altläufe nachrechenbar. Kostet acht statt zwei Spalten und speichert Belegdaten ohne Anzeigepfad — bewusst getragene Ausnahme, begründet in ADR 0051 Punkt 3.
- **Bewertungsstand zeigt nur die Bewertungen des angemeldeten Nutzers** (Daniel). Bewertungen sind personenbezogen, alle bestehenden Ansichten zeigen ausschließlich die eigenen; eine getrennte Darstellung beider Personen machte den Stand der anderen erstmals außerhalb der Vergleichsansicht sichtbar, eine zusammengefasste Darstellung zählte uneinige Fotos doppelt.
- **Datenbank-Anteil als ausgewiesene Schätzung** (Daniel): Gesamtgröße anteilig nach Fotoanzahl, sichtbar als Schätzung beschriftet, außerhalb Postgres „nicht ermittelbar". Alternative wäre gewesen, den Datenbestand-Teil des Kriteriums zu streichen oder die instanzweite Größe unverfälscht zu zeigen.
- **Der Unvollständigkeits-Hinweis greift auch bei Erfassungslücken** (Daniel), nicht nur bei Altläufen vor der Migration: ein Lauf mit `api_calls > 0` und Betrag `NULL`/`0` löst ihn ebenfalls aus (ADR 0051 Punkt 5, Befund b). Auf einer Kostenkontrollseite ist „0,00 USD" die gefährlichste Falschaussage, weil sie wie eine belastbare Antwort aussieht; die Aufrufzahl wird ohnehin gespeichert, der Hinweis kostet also keine zusätzliche Spalte.
- **Landmark-Kosten werden im `finally`-Block der Cloud-Phase geschrieben** (technische Detailentscheidung im Rahmen dieser Spec), damit ein nach der Cloud-Phase scheiternder Lauf die real angefallenen Kosten nicht verliert.
- **`architect` konsultiert** (Schritt 1) — ADR 0051 angelegt.
- **`ux-ui-designer` konsultiert** (Schritt 2) — die Seite hat eine vollständig neue Oberfläche.
- **`test-engineer` konsultiert** (Schritt 3) — Akzeptanzkriterien auf Testbarkeit geschärft, Testkonzept ergänzt.
- **`security-engineer` konsultiert** (Schritt 3) — sicherheitsrelevant, kein Blocker; Sicherheitskonzept ergänzt.

## Offene Fragen

Keine — die drei Weggabelungen des `architect` und die Kosten-Lücken-Frage des `test-engineer` sind oben unter „Entscheidungen" beantwortet.

## Out of Scope

- Keine projektübergreifende Gesamtstatistik über alle Projekte (über dieselben acht Spalten später ohne Datenmodell-Änderung erreichbar).
- Keine nachträgliche Kostenschätzung oder Hochrechnung für Läufe vor Einführung der Erfassung.
- Keine Kennzahlen über den Katalog der Akzeptanzkriterien hinaus — insbesondere keine Kosten pro Foto und keine Lauf-Historie.
- Keine Duplizierung bestehender Anzeigen (Scan-Statistik im Scan-Schritt, Häufigkeitsliste der Feinlabels).
- Keine Umrechnung der Beträge in EUR (bräuchte einen Wechselkurs als neue Abhängigkeit oder gepflegte Konstante).
- Kein Refactoring bestehender Query-Keys auf Identitätsbezug (`usePhotos` mit Filter `unrated` ist latent betroffen, aber bestehender Zustand — nicht durch diese Spec eingeführt).
