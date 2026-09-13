import type { RatingOut, RatingStatus } from '../api/types'

/**
 * Ermittelt die eigene Bewertung anhand des `username`-Claims aus dem JWT (siehe auth/jwt.ts) -
 * gemeinsame Hilfsfunktion statt der zuvor in PhotoGridPage/PhotoDetailPage/PhotoComparePage
 * dreifach fast identisch dupliziert vorhandenen Logik (Architektur-Review-Fund).
 */
export function findOwnRating(
  ratings: RatingOut[],
  username: string | null,
): RatingOut | undefined {
  if (username === null) {
    return undefined
  }
  return ratings.find((rating) => rating.username === username)
}

/**
 * Die eigene ALBUMENTSCHEIDUNG - `null` auch dann, wenn eine eigene Zeile existiert, die
 * ausschließlich das Favoriten-Kennzeichen trägt. Seit ADR 0098 ist das Vorhandensein der Zeile
 * keine Aussage mehr über den Bewertungsstand.
 */
export function ownRatingStatus(
  ratings: RatingOut[],
  username: string | null,
): RatingStatus | null {
  return findOwnRating(ratings, username)?.status ?? null
}

/**
 * Das EIGENE Favoriten-Kennzeichen.
 *
 * SICHERHEIT (Auflage S6): ausschließlich über `findOwnRating` (Abgleich über den
 * `username`-Claim). Eine Zweitableitung wie `ratings.some(r => r.favorite)` oder "erster
 * Eintrag in `ratings[]`" stellte die Auszeichnung der anderen Person als die eigene dar - das
 * neue Feld lädt dazu ein, weil es für sich allein aussagekräftig aussieht.
 */
export function ownFavorite(ratings: RatingOut[], username: string | null): boolean {
  return findOwnRating(ratings, username)?.favorite ?? false
}
