# 0144 - Die zählende Albumstufe folgt dem Verfahren des Laufs

**Status:** Accepted
**Datum:** 2026-11-08
**Bezug:** Issue [#621](https://github.com/TheRealKoller/photosort/issues/621), ADR
[`0138`](./0138-eye-als-dritte-grundlage-sidecar-schattentabellen.md) (Punkt 4 „Eye-Albumstufe nur
eigene Anzeige" und Punkt 6 „Schattenzeilen für alle je Eye-Lauf" werden abgelöst, die übrigen
Punkte gelten weiter), ADR [`0095`](./0095-albumtauglichkeit-vom-modell-qualitaet-getrennt-vom-inhalt.md)
(gilt weiter: Eye ist eine Modellstufe, kein lokal gebildeter Wert), ADR
[`0143`](./0143-modellwahl-je-projekt-und-taetigkeit.md) (die Kategorisierungswahl, deren Verfahren
hier zählt)

## Kontext

Rangwert, Event-Vorschlag und Entwurf entstehen in `_build_grouping_and_rankings` aus
`photo_album_suitability.level`. Ein Projekt mit `category_method='eye'` bekommt dort nie eine
Stufe und deshalb nie einen Entwurf. Eye trägt seine Stufe bereits in
`photo_eye_results.album_level` (1–5, dieselbe Skala). Die Projekteinstellung darf erst mit dem
nächsten erfolgreichen Lauf wirken; `rebuild_run_grouping` baut einen Lauf aber auch auf Request-Pfaden
(Versatz) neu auf und läse dort sonst die heutige Einstellung.

## Entscheidung

### 1. Die Quelle wird am Lauf eingefroren

`criterion_scoring_runs.album_level_source` (`CategoryMethod`, Werte `cloud`/`eye`, NOT NULL,
bleibender `server_default 'cloud'`) wird in `worker.py::_start_criterion_scoring_run` einmal aus
`project.category_method` gesetzt. Altzeilen tragen `cloud` wahrheitsgemäß: jeder frühere Lauf las
`photo_album_suitability`. `mode` ist dafür ungeeignet: auch ein `local`-Lauf bildet Rangwerte.

**Was gilt:** Kein Pfad, der Rangwerte bildet oder die zählende Stufe anzeigt, liest
`project.category_method`, solange ein erfolgreicher Lauf existiert. **Wo:** Worker, `api/photos.py`,
`feedback_log.py`. **Bei Verletzung:** ein Wechsel der Einstellung verschöbe Entwurf und Herkunft
sofort statt mit dem nächsten Lauf.

### 2. Ein Lesepunkt, kein Rückfall

`album_stage.py::load_album_levels(session, source, photo_ids) -> dict[int, int]` liest bei `cloud`
`PhotoAlbumSuitability.level`, bei `eye` `PhotoEyeResult.album_level`. Ein Foto ohne Zeile der
gewählten Quelle fehlt im Ergebnis — kein Rückfall auf die andere Quelle, kein lokaler Wert.
`compute_quality_score` und `normalize_level` bleiben unverändert; es gibt keine zweite Skala.

**Was gilt:** Rangbildung, Austausch-Diagnose und eingefrorener Feedback-Kontext lesen die Stufe nur
hierüber. **Wo:** `_build_grouping_and_rankings`, `api/photos.py::_exchange_sides`,
`feedback_log.load_frozen_context`. **Bei Verletzung:** die Feedback-Stufe stammte aus einem
anderen Verfahren als der eingefrorene Qualitätswert, und `within_level`/`across_level` liefen auseinander.

### 3. Die Eye-Phase holt nur fehlende Stufen nach

Kandidaten der Eye-Phase sind die Ausschuss-Überlebenden **ohne** `photo_eye_results`-Zeile;
`api/projects.py::_count_eye_candidates` zählt dieselbe Menge. Vorhandene Eye-Ergebnisse werden
nicht erneut bewertet und nicht ersetzt; Promotion (`upsert_assessment`, `local < eye < cloud`)
geschieht nur für neu analysierte Fotos. Ein Foto, dessen Aufruf scheiterte, hat keine Zeile und ist
im nächsten Eye-Lauf wieder Kandidat. Die Gesundheitsprüfung vor dem Einreihen bleibt auch bei null
Kandidaten.

**Was gilt:** Eye schreibt weiterhin **nie** in `photo_album_suitability`, `photo_fine_labels` oder
`fine_labels`. **Wo:** `_run_eye_phase`. **Bei Verletzung:** Eye verschöbe die Cloud-Kandidatenmenge
(`select_remote_category_candidates`) und die Kostenschätzung des nächsten Cloud-Laufs.

### 4. Die Herkunft reist mit der Stufe

`AlbumSuitabilityOut` bekommt `source: "cloud" | "eye"`. `PhotoOut.album_suitability` trägt die
zählende Stufe nach der Quelle des jüngsten erfolgreichen Laufs (ohne Lauf: `project.category_method`):
bei `eye` `level=album_level`, `reason=None`, `source="eye"`; fehlt die Zeile, `None`. Die
Oberfläche zeigt bei `source='eye'` anstelle der Begründung das Wort „Eye"; die Qualitätsstufe
bleibt `qualityLevel(rank_score)`. `PhotoOut.eye_result` behält seine Bedeutung (Kopfzeile `eye`).

Die Namensnennung (`EyeAttribution`, ADR 0138 Punkt 9) steht je Ansicht einmal — Entwurfsseite und
Endauswahl —, sobald dort ein Foto mit `source='eye'` erscheint, nicht an jeder Kachel: sie nennt
das Modell, das Wort „Eye" an der Kachel die Herkunft der einzelnen Stufe.

**Was gilt:** die Herkunft wird nie aus Projekt oder Kopfzeile geraten. **Wo:**
`api/photos.py::_to_photo_out` mit Pflichtparameter `album_level_source`. **Bei Verletzung:** eine
Kachel nennte „Eye" für eine Stufe, die nicht zählt, oder zeigte eine leere Begründungszeile.

### 5. Der Entwurf setzt keine Cloud-Freigabe mehr voraus

Die Oberfläche verlangt die Cloud-Freigabe für den Entwurf nur bei `category_method='cloud'`. Bei
Eye ohne erfolgreichen Lauf erscheint der bestehende Leerzustand mit dem Weg zur Klassifizierung,
bei abgeschaltetem Eye (`GET …/model-choice`, `eye_disabled`) ein eigener Satz mit Weg zu den
Einstellungen.

## Konsequenzen

- Ein Wechsel `cloud ↔ eye` wirkt mit dem nächsten erfolgreichen Lauf; Stufen beider Verfahren
  bleiben gespeichert und zählen nach Rückwechsel und Lauf wieder. Aufnahmen und Streichungen hängen
  an Bewertungen und bleiben.
- Eine neue `MAPPING_VERSION` erreicht bestehende Eye-Ergebnisse nicht mehr; `eye_photos_total`
  zählt die nachzuholenden Fotos.
- Ein Foto ohne zählende Stufe behält `event_id`, hat `rank_score = NULL`, wird nicht vorgeschlagen
  und zeigt aufgenommen „Noch nicht eingestuft".
- Bestehende Feedback-Ereignisse bleiben unverändert.
- Unverändert: Scan, Ausschuss-Gate, lokale Bewertung, Klassifizierungsprüfung, Cloud-Kandidatenmenge
  und Kostenschätzung.
