export type ScanStatus = 'running' | 'success' | 'failed'

export interface ScanSummary {
  status: ScanStatus
  started_at: string
  finished_at: string | null
  files_found: number
  // specs/features/0036-scan-performance-zweiphasig-parallel.md: null solange die
  // Enumerationsphase noch nicht abgeschlossen ist - unterscheidet sich bewusst von 0 (leeres
  // Projekt). Immer explizit `!== null`/`=== null` pruefen, nie truthy.
  total_files: number | null
  photos_added: number
  photos_updated: number
  photos_removed: number
  files_skipped: number
  error_message: string | null
}

// Wiederverwendet ScanStatus (running/success/failed) statt eines eigenen Typs - identische
// Semantik fuer einen asynchron laufenden Worker-Job, siehe backend models.py::ScoringRun.
export interface ScoringRunSummary {
  // Additiv (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md): wird als
  // scoring_run_id an POST /score-criteria weitergereicht (Staleness-Guard bei einem
  // zwischenzeitlichen Re-Scan/Re-Scoring).
  id: number
  status: ScanStatus
  started_at: string
  finished_at: string | null
  photos_total: number
  photos_processed: number
  suggestions_found: number
  error_message: string | null
  // Ausschuss-Gate (specs/features/0037): null = noch nicht bestaetigt.
  gate_confirmed_at: string | null
}

// specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md: die beiden Teilschritte
// eines verketteten Klassifizierungslaufs, in genau dieser Reihenfolge.
export type ClassificationPhase = 'remote_categories' | 'criteria'

// Ersetzt TopSelectionRunSummary (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
// backfill.md) - kein top_n_per_cluster/candidates_total/suggestions_found mehr: N wird erst
// beim Lesen angewendet (GET /photos?top_n_per_category=N), der Job berechnet immer den vollen
// Rangfolge-Pool je Partition statt eine Top-N-Auswahl zu treffen.
export interface CriterionScoringRunSummary {
  status: ScanStatus
  started_at: string
  finished_at: string | null
  photos_total: number
  photos_processed: number
  error_message: string | null
  // specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md: diese Zusammenfassung
  // beschreibt seit Spec 0296 den GESAMTEN Klassifizierungslauf, nicht mehr nur seine
  // Kriterien-Phase.
  //
  // `phase`: der gerade laufende Teilschritt; null = laeuft nicht mehr (beendet, oder Altlauf aus
  // der Zeit der getrennten Ausloesung). Waehrend 'remote_categories' stehen die Fortschritts-
  // zahlen in last_remote_category_classification_run, waehrend 'criteria' hier.
  phase: ClassificationPhase | null
  // War die Cloud-Nutzung fuer DIESEN Lauf angefordert? false heisst "das Ergebnis kann keine
  // Cloud-Anreicherung enthalten" - Grundlage des entsprechenden Hinweises in der Oberflaeche.
  cloud_requested: boolean
  // Laufweite Zusammenfassung der Cloud-Probleme, null = keine. Ein gesetzter Wert heisst NICHT,
  // dass der Lauf fehlgeschlagen ist: der lokale Bewertungsanteil laeuft trotzdem vollstaendig
  // durch, das Ergebnis ist nur nicht (vollstaendig) angereichert.
  cloud_error_message: string | null
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt 6:
// Run-Tracking analog CriterionScoringRunSummary, aber ohne Ausschuss-Gate-Bezug.
export interface RemoteCategoryClassificationRunSummary {
  status: ScanStatus
  started_at: string
  finished_at: string | null
  photos_total: number
  photos_processed: number
  error_message: string | null
}

export interface ProjectOut {
  id: number
  name: string
  opencloud_drive_id: string
  opencloud_path: string
  created_at: string
  last_scan: ScanSummary | null
  last_scoring_run: ScoringRunSummary | null
  last_criterion_scoring_run: CriterionScoringRunSummary | null
  // specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md
  last_remote_category_classification_run: RemoteCategoryClassificationRunSummary | null
  // Globales Feature-Flag (specs/features/0024-top-photo-selection-category-mix.md, weiterhin
  // verwendet fuer POST /classify seit Spec 0296), auf ProjectOut statt einem eigenen
  // Endpunkt exponiert - siehe backend api/projects.py-Kommentar.
  category_selection_enabled: boolean
  // Projektweiter Einwilligungs-Schalter fuer produktive Cloud-Vision-Datenfluesse (urspruenglich
  // nur die Cloud-Sehenswuerdigkeit-Erkennung, specs/features/0047-sehenswuerdigkeit-erkennung-
  // cloud-vision-api.md) - Default false, consent_at null solange nicht aktiviert. Gated seit
  // specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md zusaetzlich die
  // Remote-Kategorie-Klassifizierung.
  cloud_vision_detection_enabled: boolean
  cloud_vision_consent_at: string | null
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt
// 6.1, fortgeschrieben von specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md
// (ADR 0050 Punkt 5): Kostenschaetzung vor dem Lauf, jetzt ueber ALLE Cloud-Anteile, die die
// Checkbox am Ausloeser freigibt. `candidate_count` ist die Summe der beiden Einzelanteile und
// bleibt die eine anzuzeigende Zahl.
export interface ClassificationEstimateOut {
  candidate_count: number
  remote_category_candidate_count: number
  landmark_candidate_count: number
  provider: string
  price_per_image_usd: number
  estimated_cost_usd: number
}

export interface BrowseEntry {
  name: string
  path: string
}

// specs/features/0050-dateianzahl-im-ordner-browser.md: rekursive Bilddatei-Anzahl (mit
// Obergrenze) pro direktem Unterordner, wie von GET /opencloud/folder-counts geliefert. Bewusst
// kein Freitext-/Meldungsfeld (Security-Abschnitt der Spec) - error=true transportiert kein
// str(exc) vom Backend.
export interface FolderCountOut {
  path: string
  count: number
  at_limit: boolean
  error: boolean
}

export type RatingStatus = 'favorite' | 'album_worthy' | 'rejected'
export type RatingFilter = 'unrated' | 'suggested' | RatingStatus
export type PhotoVariant = 'thumbnail' | 'display'

export interface RatingOut {
  user_id: number
  username: string
  status: RatingStatus
}

export type SuggestionReason = 'duplicate' | 'low_quality'

// Automatischer Vorschlag aus PhotoScore, bewusst getrennt von RatingOut/ratings[] (ADR 0006,
// specs/decisions/0006-local-scoring-datamodel.md) - ein Vorschlag ist strukturell nie eine
// Bewertung, sondern wird erst durch aktive Bestaetigung (PUT /photos/{id}/rating) zu einer.
//
// "top_pick"/`category` (Spec 0024) sind mit specs/features/0037-gatefuehrte-bewertungs-
// pipeline-mit-backfill.md entfallen - der fruehere Top-Pick-Mechanismus ist durch die neue
// Kriterien-/Rangfolgen-Pipeline (PhotoRanking) ersetzt, deren Kontext jetzt im eigenstaendigen
// `PhotoOut.ranking`-Feld lebt statt in SuggestionOut (siehe backend api/photos.py::
// SuggestionOut-Docstring fuer die Begruendung dieser Trennung).
export interface SuggestionOut {
  status: RatingStatus
  reason: SuggestionReason
  duplicate_of: number | null
  sharpness: number
  exposure: number
  cluster_key: string | null
  computed_at: string
}

// Kategorie-Schluessel. Seit specs/features/0289-feste-kategorien.md ist die Menge fachlich
// GESCHLOSSEN (13 Eintraege, backend categories.py::CATEGORY_REGISTRY) - der TypeScript-Typ bleibt
// aber bewusst `string`: das Set kommt zur Laufzeit ueber `GET /categories` vom Server (ADR 0049,
// Entwurfsentscheidung 5), eine hier gespiegelte Union waere eine dauerhaft driftende zweite
// Liste. Zusaetzlich koennen aus der LAUFHISTORIE (`PhotoRanking.category_key` frueherer Laeufe)
// weiterhin Altwerte ausserhalb des Sets auftauchen ("unerkannt", "landscape", "people") - das
// Frontend muss sie ueber den generischen Fallback darstellen koennen, ohne Absturz.
export type CategoryKey = string

// specs/features/0289-feste-kategorien.md: ein Eintrag des festen Sets, wie ihn GET /categories
// liefert - in ANZEIGEREIHENFOLGE der Server-Registry (nicht alphabetisch). `locally_available`
// markiert die sechs ohne Remote-Lauf erreichbaren Kategorien.
export interface CategoryOut {
  key: CategoryKey
  display_name: string
  definition: string
  locally_available: boolean
}

// Kuratierungs-Kontext eines Fotos aus der Kriterien-/Rangfolgen-Pipeline
// (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md). Seit
// specs/features/0040-bewertungsdetails-info-popover.md auch im Standard-Listing befuellt (nicht
// mehr nur bei `top_n_per_category`).
export interface RankingOut {
  cluster_key: string
  category_key: CategoryKey
  rank_score: number
  rank_position: number
  // Groesse der GESAMTEN Cluster x Kategorie-Partition (nicht nur der angeforderten top_n), fuer
  // "Rang M von N" im Info-Popover (specs/features/0040-bewertungsdetails-info-popover.md).
  partition_size: number
}

// Herkunft eines Kriterien-Werts (backend models.py::CriterionSource) - aktuell nur zur Anzeige
// im Info-Popover, kein Frontend-Verhalten haengt vom konkreten Wert ab.
export type CriterionSource = 'local_heuristic' | 'local_ml' | 'cloud'

// Ein einzelner, bereits normierter Kriterien-Wert eines Fotos
// (specs/features/0040-bewertungsdetails-info-popover.md) - exponiert die seit Spec 0037
// vorhandene PhotoCriterionScore-Tabelle. Best-effort: nur Kriterien, fuer die tatsaechlich ein
// Wert berechnet wurde, sind enthalten (kein 0/Platzhalter fuer fehlende).
export interface CriterionScoreOut {
  criterion_key: string
  display_name: string
  value: number
  source: CriterionSource
  // specs/features/0209-bewertungsdetails-bloecke-qualitaet-kategorien.md,
  // Architektur-Entscheidung 1/2: spiegelt `CriterionDefinition.category_eligible` der
  // Backend-Registry und ist die ALLEINIGE Grundlage der Gliederung in die Bloecke
  // "Qualitaet" (false) / "Kategorien" (true) - im Frontend wird dazu bewusst keine
  // Merkmalsliste gepflegt. Pflichtfeld statt optional, damit `tsc` alle Test-Fixtures
  // erzwingt, statt stillschweigend `undefined` in die Blockbildung durchzureichen.
  category_eligible: boolean
}

// specs/features/0289-feste-kategorien.md: ein frei formuliertes, auf einen kanonischen Eintrag
// aufgeloestes Feinlabel - immer eine Liste (0-2 Eintraege), nie null. Reine ZUSATZINFORMATION am
// Foto, keine Kategoriequelle; `confidence` ist mit dieser Spec ersatzlos entfallen.
//
// SICHERHEITSHINWEIS: `display_name`/`raw_label` sind freier, extern erzeugter LLM-Text (backend
// zeichensaniert). Sie duerfen ausschliesslich als regulaerer React-Textknoten gerendert werden -
// nie ueber dangerouslySetInnerHTML, nie als HTML-String-Prop, nie in href/src/style.
export interface FineLabelOut {
  canonical_key: string
  display_name: string
  raw_label: string
  provider: string
}

// specs/features/0289-feste-kategorien.md: Haeufigkeit eines Feinlabels IN EINEM PROJEKT
// (GET /projects/{id}/fine-labels), absteigend sortiert - macht sichtbar, welche Kategorie im
// festen Set gegebenenfalls fehlt.
export interface FineLabelCountOut {
  canonical_key: string
  display_name: string
  photo_count: number
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt
// "Datenbedarf": die fuer DIESES Foto tatsaechlich gueltige Kategorie-Kandidatenmenge (lokal
// qualifizierende Kriterien + Remote-Erkennungen zusammen) - verhindert, dass das Frontend die
// Praesenz-Schwellenlogik (backend criteria.py::CRITERIA_REGISTRY) selbst nachbilden muss.
// `category_key` ist seit specs/features/0289-feste-kategorien.md IMMER ein Key des festen Sets;
// das frueher mitgelieferte `score`-Feld ist ersatzlos entfallen (die Auswahl entscheidet die
// feste Vorrangreihenfolge im Backend, nicht ein Zahlenvergleich). `provider` ist nur bei
// `origin === 'remote'` gesetzt. Die Liste ist reine ERKLAERUNG ("das hat das System erkannt") -
// sie beschraenkt NICHT mehr, was manuell uebersteuert werden darf.
export interface CategoryCandidateOut {
  category_key: CategoryKey
  origin: 'local' | 'remote'
  provider: string | null
}

// specs/features/0058-cloud-vision-status-transparenz.md, decisions/0035-cloud-vision-attempt-
// fehler-persistierung.md: die beiden unabhaengigen Cloud-Vision-Laeufe, fuer die pro Foto genau
// einer von sechs Zustaenden angezeigt wird.
export type CloudVisionPhase = 'landmark' | 'remote_category'

// Read-time aus bereits vorhandenen Signalen abgeleitet (backend api/photos.py::
// _cloud_vision_status_out) - kein voller Status pro Foto persistiert. `no_result` tritt nur bei
// `phase === 'landmark'` auf (ADR 0032 Punkt 3: Remote-Kategorie kennt keinen "nichts
// gefunden"-Fall, Erfolg schreibt immer 1-3 Zeilen).
export type CloudVisionStatus =
  | 'not_run'
  | 'not_candidate'
  | 'consent_disabled'
  | 'error'
  | 'no_result'
  | 'result'

// Ein Eintrag von `PhotoOut.cloud_vision_status` - immer genau zwei (einer je CloudVisionPhase),
// feste Reihenfolge [landmark, remote_category].
export interface CloudVisionStatusOut {
  phase: CloudVisionPhase
  status: CloudVisionStatus
  // Nur bei status === 'error' gesetzt.
  error_message: string | null
  // Nur bei status in {'error', 'no_result', 'result'} gesetzt.
  attempted_at: string | null
}

export interface PhotoOut {
  id: number
  relative_path: string
  taken_at: string
  ratings: RatingOut[]
  suggestion: SuggestionOut | null
  ranking: RankingOut | null
  criterion_scores: CriterionScoreOut[]
  // specs/features/0289-feste-kategorien.md: immer eine Liste (0-2 Eintraege), nie null.
  fine_labels: FineLabelOut[]
  // Die remote ermittelte Kategorie dieses Fotos, null ohne Remote-Klassifizierung. Bewusst
  // getrennt von `ranking.category_key` (dort steht die im Lauf tatsaechlich vergebene Kategorie).
  remote_category: CategoryKey | null
  // Dauerhafte manuelle Uebersteuerung (PhotoScore.category_override), null ohne aktiven
  // Override.
  category_override: CategoryKey | null
  // Sortiert in Registry-Anzeigereihenfolge (dieselbe Reihenfolge wie GET /categories).
  category_candidates: CategoryCandidateOut[]
  // specs/features/0058-cloud-vision-status-transparenz.md: immer genau 2 Eintraege, feste
  // Reihenfolge [landmark, remote_category].
  cloud_vision_status: CloudVisionStatusOut[]
}

export interface PhotoListOut {
  items: PhotoOut[]
  total: number
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt
// 6.3: Antwort von PUT /photos/{id}/category-override (der gesetzte Wert wird direkt
// zurueckgegeben, analog PUT /photos/{id}/rating).
export interface CategoryOverrideOut {
  photo_id: number
  category_key: CategoryKey
}
