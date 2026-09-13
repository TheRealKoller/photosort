import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import { deleteRating, setFavorite, setRating } from './ratings'
import type { RatingWriteOut } from './types'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

const WRITTEN: RatingWriteOut = {
  photo_id: 1,
  status: 'album_worthy',
  favorite: false,
  updated_at: '2026-09-13T10:00:00',
}

describe('api/ratings', () => {
  it('sets an album decision via PUT /photos/{id}/rating', async () => {
    vi.mocked(apiFetch).mockResolvedValue(WRITTEN)

    const result = await setRating(1, 'album_worthy')

    expect(apiFetch).toHaveBeenCalledWith('/photos/1/rating', {
      method: 'PUT',
      body: { status: 'album_worthy' },
    })
    expect(result).toEqual(WRITTEN)
  })

  it('deletes an album decision via DELETE /photos/{id}/rating', async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined)

    await deleteRating(1)

    expect(apiFetch).toHaveBeenCalledWith('/photos/1/rating', { method: 'DELETE' })
  })

  it('sets the favorite marker via its OWN endpoint, never via the rating one', async () => {
    // Der eigene Pfad ist die Zusage: ein gemeinsamer Schreibweg setzte die Albumentscheidung
    // beim Markieren als Favorit still zurueck.
    vi.mocked(apiFetch).mockResolvedValue({ ...WRITTEN, favorite: true })

    const result = await setFavorite(1, true)

    expect(apiFetch).toHaveBeenCalledWith('/photos/1/favorite', {
      method: 'PUT',
      body: { favorite: true },
    })
    expect(result.favorite).toBe(true)
  })

  it('clears the favorite marker through the same endpoint', async () => {
    vi.mocked(apiFetch).mockResolvedValue(WRITTEN)

    await setFavorite(7, false)

    expect(apiFetch).toHaveBeenCalledWith('/photos/7/favorite', {
      method: 'PUT',
      body: { favorite: false },
    })
  })
})
