import { describe, expect, it } from 'vitest'

import type { RatingOut } from '../api/types'
import { findOwnRating, ownFavorite, ownRatingStatus } from './ownRating'

const RATINGS: RatingOut[] = [
  { user_id: 1, username: 'testuser', status: 'album_worthy', favorite: true },
  { user_id: 2, username: 'other-user', status: 'rejected', favorite: false },
]

// Eine Zeile, die AUSSCHLIESSLICH das Kennzeichen traegt: seit ADR 0098 ein gueltiger Zustand -
// vorhandene Zeile, aber keine Albumentscheidung.
const ONLY_FAVORITE: RatingOut[] = [
  { user_id: 1, username: 'testuser', status: null, favorite: true },
  { user_id: 2, username: 'other-user', status: 'album_worthy', favorite: true },
]

describe('findOwnRating', () => {
  it('returns the rating matching the given username', () => {
    expect(findOwnRating(RATINGS, 'other-user')).toEqual(RATINGS[1])
  })

  it('returns undefined when the username has no rating', () => {
    expect(findOwnRating(RATINGS, 'nobody')).toBeUndefined()
  })

  it('returns undefined when username is null (not yet decoded)', () => {
    expect(findOwnRating(RATINGS, null)).toBeUndefined()
  })
})

describe('ownRatingStatus', () => {
  it('returns the album decision for the matching username', () => {
    expect(ownRatingStatus(RATINGS, 'testuser')).toBe('album_worthy')
  })

  it('returns null when unrated by this user', () => {
    expect(ownRatingStatus(RATINGS, 'nobody')).toBeNull()
  })

  it('returns null when username is null', () => {
    expect(ownRatingStatus(RATINGS, null)).toBeNull()
  })

  it('returns null for a row that carries only the favorite marker', () => {
    // Das Vorhandensein der Zeile ist keine Aussage mehr: "keine Albumentscheidung" liest sich
    // hier genauso wie "gar keine Zeile".
    expect(ownRatingStatus(ONLY_FAVORITE, 'testuser')).toBeNull()
  })
})

describe('ownFavorite', () => {
  it('returns the own marker, never the one of the other user', () => {
    // Auflage S6: `ratings.some(r => r.favorite)` waere hier `true` und stellte die Auszeichnung
    // des anderen als die eigene dar.
    expect(ownFavorite([RATINGS[1]], 'testuser')).toBe(false)
  })

  it('returns true for a row that carries only the marker', () => {
    expect(ownFavorite(ONLY_FAVORITE, 'testuser')).toBe(true)
  })

  it('returns true when the marker sits next to an album decision', () => {
    expect(ownFavorite(RATINGS, 'testuser')).toBe(true)
  })

  it('returns false when this user has no row at all', () => {
    expect(ownFavorite(RATINGS, 'nobody')).toBe(false)
  })

  it('returns false when username is null (not yet decoded)', () => {
    expect(ownFavorite(RATINGS, null)).toBe(false)
  })
})
