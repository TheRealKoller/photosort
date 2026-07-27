import { describe, expect, it } from 'vitest'

import type { RatingOut } from '../api/types'
import { findOwnRating, ownRatingStatus } from './ownRating'

const RATINGS: RatingOut[] = [
  { user_id: 1, username: 'testuser', status: 'favorite' },
  { user_id: 2, username: 'other-user', status: 'rejected' },
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
  it('returns the status for the matching username', () => {
    expect(ownRatingStatus(RATINGS, 'testuser')).toBe('favorite')
  })

  it('returns null when unrated by this user', () => {
    expect(ownRatingStatus(RATINGS, 'nobody')).toBeNull()
  })

  it('returns null when username is null', () => {
    expect(ownRatingStatus(RATINGS, null)).toBeNull()
  })
})
