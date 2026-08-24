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
  // verwendet fuer POST /score-criteria seit Spec 0037), auf ProjectOut statt einem eigenen
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
// 6.1: Kostenschaetzung vor dem Remote-Kategorisierungs-Lauf.
export interface ClassifyCategoriesRemoteEstimateOut {
  candidate_count: number
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

// Freier Kategorie-Schluessel (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
// backfill.md) - kein festes L/D/M-Kuerzelschema mehr (ersetzt den frueheren PhotoCategory-Enum
// aus Spec 0024). Server-seitig aktuell "landscape"/"detail"/"people", aber bewusst als `string`
// typisiert - das Frontend darf keine feste, geschlossene Liste annehmen (Registry-Erweiterung
// ist rein serverseitig, siehe backend criteria.py::CRITERIA_REGISTRY).
export type CategoryKey = string

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
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt 6:
// ein vom Vision-LLM geliefertes, auf einen kanonischen Eintrag aufgeloestes Roh-Label - immer
// eine Liste (0-3 Eintraege), nie null, analog `ratings`/`criterion_scores`.
export interface RemoteCategoryLabelOut {
  canonical_key: string
  display_name: string
  raw_label: string
  confidence: number
  provider: string
}

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, UI/UX-Abschnitt
// "Datenbedarf": die fuer DIESES Foto tatsaechlich gueltige Kategorie-Kandidatenmenge (lokal
// qualifizierende Kriterien + Remote-Erkennungen zusammen) - verhindert, dass das Frontend die
// Praesenz-Schwellenlogik (backend criteria.py::CRITERIA_REGISTRY) selbst nachbilden muss.
// `category_key` ist bereits im generischen Format (wie `RankingOut.category_key`). `provider`
// ist nur bei `origin === 'remote'` gesetzt.
export interface CategoryCandidateOut {
  category_key: CategoryKey
  origin: 'local' | 'remote'
  score: number
  provider: string | null
}

export interface PhotoOut {
  id: number
  relative_path: string
  taken_at: string
  ratings: RatingOut[]
  suggestion: SuggestionOut | null
  ranking: RankingOut | null
  criterion_scores: CriterionScoreOut[]
  // specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md: immer eine
  // Liste (0-3 Eintraege), nie null.
  remote_category_labels: RemoteCategoryLabelOut[]
  // Dauerhafte manuelle Uebersteuerung (PhotoScore.category_override), null ohne aktiven
  // Override.
  category_override: CategoryKey | null
  // Sortiert nach Score/Konfidenz absteigend (UI/UX-Abschnitt der Spec).
  category_candidates: CategoryCandidateOut[]
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
