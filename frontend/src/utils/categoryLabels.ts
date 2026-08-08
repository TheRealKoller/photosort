import type { PhotoCategory } from '../api/types'

// Ausgeschriebene Kategorienamen (Detailansicht, aria-label/title auf der Grid-Kachel) - Muster
// analog ratingLabels.ts (specs/features/0024-top-photo-selection-category-mix.md).
export const CATEGORY_LABELS: Record<PhotoCategory, string> = {
  landscape: 'Landschaft',
  detail: 'Detailaufnahme',
  people: 'Menschen',
}

// Kollisionsfreie Ein-Buchstaben-Kuerzel fuer die Grid-Kachel (begrenzter Platz) - L/D/M statt der
// jeweils ersten Buchstaben von "landscape"/"detail"/"people", da "detail" und "people" sonst beide
// mit dem Buchstaben D anfangen wuerden bzw. keine natuerliche deutsche Abkuerzung ergaeben.
export const CATEGORY_ABBREVIATIONS: Record<PhotoCategory, string> = {
  landscape: 'L',
  detail: 'D',
  people: 'M',
}
