import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import { deleteRating, setRating } from './ratings'
import type { RatingOut } from './types'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

const RATING: RatingOut = { user_id: 1, username: 'daniel', status: 'favorite' }

describe('api/ratings', () => {
  it('sets a rating via PUT /photos/{id}/rating', async () => {
    vi.mocked(apiFetch).mockResolvedValue(RATING)

    const result = await setRating(1, 'favorite')

    expect(apiFetch).toHaveBeenCalledWith('/photos/1/rating', {
      method: 'PUT',
      body: { status: 'favorite' },
    })
    expect(result).toEqual(RATING)
  })

  it('deletes a rating via DELETE /photos/{id}/rating', async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined)

    await deleteRating(1)

    expect(apiFetch).toHaveBeenCalledWith('/photos/1/rating', { method: 'DELETE' })
  })
})
