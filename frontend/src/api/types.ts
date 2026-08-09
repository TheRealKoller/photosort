export type ScanStatus = 'running' | 'success' | 'failed'

export interface ScanSummary {
  status: ScanStatus
  started_at: string
  finished_at: string | null
  files_found: number
  photos_added: number
  photos_updated: number
  photos_removed: number
  files_skipped: number
  error_message: string | null
}

// Wiederverwendet ScanStatus (running/success/failed) statt eines eigenen Typs - identische
// Semantik fuer einen asynchron laufenden Worker-Job, siehe backend models.py::ScoringRun.
export interface ScoringRunSummary {
  status: ScanStatus
  started_at: string
  finished_at: string | null
  photos_total: number
  photos_processed: number
  suggestions_found: number
  error_message: string | null
}

// specs/features/0024-top-photo-selection-category-mix.md: wiederverwendet ScanStatus wie
// ScoringRunSummary oben - identische Semantik fuer einen asynchron laufenden Worker-Job.
// candidates_total/candidates_processed statt photos_total/photos_processed, da hier nur der
// bereits begrenzte Kandidatenpool pro Cluster gezaehlt wird.
export interface TopSelectionRunSummary {
  status: ScanStatus
  started_at: string
  finished_at: string | null
  top_n_per_cluster: number
  candidates_total: number
  candidates_processed: number
  suggestions_found: number
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
  last_top_selection_run: TopSelectionRunSummary | null
  // Globales Feature-Flag (specs/features/0024-top-photo-selection-category-mix.md), auf
  // ProjectOut statt einem eigenen Endpunkt exponiert - siehe backend api/projects.py-Kommentar.
  category_selection_enabled: boolean
}

export interface BrowseEntry {
  name: string
  path: string
}

export type RatingStatus = 'favorite' | 'album_worthy' | 'rejected'
export type RatingFilter = 'unrated' | 'suggested' | RatingStatus
export type PhotoVariant = 'thumbnail' | 'display'

export interface RatingOut {
  user_id: number
  username: string
  status: RatingStatus
}

export type SuggestionReason = 'duplicate' | 'low_quality' | 'top_pick'

// Lokal klassifizierte Motiv-Kategorie (specs/features/0024-top-photo-selection-category-mix.md,
// decisions/0015-lokale-kategorie-klassifikation.md) - nur 3 statt urspruenglich 4 geplanter
// Kategorien, siehe backend photosort.models.PhotoCategory.
export type PhotoCategory = 'landscape' | 'detail' | 'people'

// Automatischer Vorschlag aus PhotoScore, bewusst getrennt von RatingOut/ratings[] (ADR 0006,
// specs/decisions/0006-local-scoring-datamodel.md) - ein Vorschlag ist strukturell nie eine
// Bewertung, sondern wird erst durch aktive Bestaetigung (PUT /photos/{id}/rating) zu einer.
export interface SuggestionOut {
  status: RatingStatus
  reason: SuggestionReason
  duplicate_of: number | null
  local_quality_score: number | null
  sharpness: number
  exposure: number
  cluster_key: string | null
  // Additiv (Spec 0024): nur fuer reason "top_pick" gesetzt - Phase-A-Vorschlaege (duplicate/
  // low_quality) werden nie lokal klassifiziert (kein Kandidat des select-top-Jobs).
  category: PhotoCategory | null
  computed_at: string
}

export interface PhotoOut {
  id: number
  relative_path: string
  taken_at: string
  ratings: RatingOut[]
  suggestion: SuggestionOut | null
}

export interface PhotoListOut {
  items: PhotoOut[]
  total: number
}
