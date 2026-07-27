import type { RatingOut, RatingStatus } from '../api/types'

/**
 * Ermittelt die eigene Bewertung anhand des `username`-Claims aus dem JWT (siehe auth/jwt.ts) -
 * gemeinsame Hilfsfunktion statt der zuvor in PhotoGridPage/PhotoDetailPage/PhotoComparePage
 * dreifach fast identisch dupliziert vorhandenen Logik (Architektur-Review-Fund).
 */
export function findOwnRating(
  ratings: RatingOut[],
  username: string | null
): RatingOut | undefined {
  if (username === null) {
    return undefined
  }
  return ratings.find((rating) => rating.username === username)
}

export function ownRatingStatus(ratings: RatingOut[], username: string | null): RatingStatus | null {
  return findOwnRating(ratings, username)?.status ?? null
}
