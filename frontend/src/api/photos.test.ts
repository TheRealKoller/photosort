import { describe, expect, it, vi } from 'vitest'

import { apiFetch, apiFetchBlob } from './client'
import { deleteCategoryOverride, fetchPhotoImageBlobUrl, listPhotos, setCategoryOverride } from './photos'
import type { PhotoListOut } from './types'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
  apiFetchBlob: vi.fn(),
}))

const PHOTO_LIST: PhotoListOut = {
  items: [
    {
      id: 1,
      relative_path: 'a.jpg',
      taken_at: '2026-07-20T10:00:00Z',
      ratings: [],
      suggestion: null,
      ranking: null,
      criterion_scores: [],
      remote_category_labels: [],
      category_override: null,
      category_candidates: [],
      cloud_vision_status: [],
    },
  ],
  total: 1,
}

describe('api/photos', () => {
  it('fetches photos of a project without params', async () => {
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    const result = await listPhotos(1)

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/photos')
    expect(result).toEqual(PHOTO_LIST)
  })

  it('encodes rating_status/limit/offset as query params', async () => {
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    await listPhotos(1, { ratingStatus: 'unrated', limit: 30, offset: 60 })

    expect(apiFetch).toHaveBeenCalledWith(
      '/projects/1/photos?rating_status=unrated&limit=30&offset=60'
    )
  })

  it('encodes top_n_per_category as a query param', async () => {
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    await listPhotos(1, { topNPerCategory: 3 })

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/photos?top_n_per_category=3')
  })

  it('fetchPhotoImageBlobUrl requests the image and returns an object URL', async () => {
    const blob = new Blob(['bytes'])
    vi.mocked(apiFetchBlob).mockResolvedValue(blob)
    const createObjectURL = vi.fn().mockReturnValue('blob:fake-url')
    vi.stubGlobal('URL', { ...URL, createObjectURL })

    const result = await fetchPhotoImageBlobUrl(1, 'thumbnail')

    expect(apiFetchBlob).toHaveBeenCalledWith('/photos/1/image?variant=thumbnail')
    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(result).toBe('blob:fake-url')

    vi.unstubAllGlobals()
  })

  it('sets the category override via PUT /photos/{id}/category-override', async () => {
    vi.mocked(apiFetch).mockResolvedValue({ photo_id: 1, category_key: 'hund' })

    const result = await setCategoryOverride(1, 'hund')

    expect(apiFetch).toHaveBeenCalledWith('/photos/1/category-override', {
      method: 'PUT',
      body: { category_key: 'hund' },
    })
    expect(result).toEqual({ photo_id: 1, category_key: 'hund' })
  })

  it('deletes the category override via DELETE /photos/{id}/category-override', async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined)

    await deleteCategoryOverride(1)

    expect(apiFetch).toHaveBeenCalledWith('/photos/1/category-override', { method: 'DELETE' })
  })
})
