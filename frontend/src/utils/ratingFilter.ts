import type { RatingFilter } from '../api/types'

const VALID_RATING_FILTERS: readonly RatingFilter[] = [
  'unrated',
  'suggested',
  'favorite',
  'album_worthy',
  'rejected',
]

/**
 * Validiert den `filter`-Query-Param gegen die bekannten RatingFilter-Werte (Code-Review-Fund:
 * ein unbekannter/getippter Wert wurde zuvor ungeprueft an die API weitergereicht und fuehrte zu
 * 422 statt eines robusten Fallbacks auf "kein Filter").
 */
export function parseRatingFilter(value: string | null): RatingFilter | '' {
  if (value !== null && (VALID_RATING_FILTERS as readonly string[]).includes(value)) {
    return value as RatingFilter
  }
  return ''
}
