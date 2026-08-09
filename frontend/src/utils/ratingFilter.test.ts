import { describe, expect, it } from 'vitest'

import { parseRatingFilter } from './ratingFilter'

describe('parseRatingFilter', () => {
  it('accepts each known filter value', () => {
    expect(parseRatingFilter('unrated')).toBe('unrated')
    expect(parseRatingFilter('suggested')).toBe('suggested')
    expect(parseRatingFilter('favorite')).toBe('favorite')
    expect(parseRatingFilter('album_worthy')).toBe('album_worthy')
    expect(parseRatingFilter('rejected')).toBe('rejected')
  })

  it('falls back to no filter for a missing param', () => {
    expect(parseRatingFilter(null)).toBe('')
  })

  it('falls back to no filter for an unknown/tampered value instead of forwarding it to the API', () => {
    expect(parseRatingFilter('not-a-real-filter')).toBe('')
    expect(parseRatingFilter('')).toBe('')
  })
})
