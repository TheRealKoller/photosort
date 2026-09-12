import { describe, expect, it, vi } from 'vitest'

import { apiFetch, apiFetchBlob } from './client'
import { fetchPhotoImageBlobUrl, listCurationCandidates, listPhotos } from './photos'
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
      taken_at_original: '2026-07-20T10:00:00Z',
      time_offset_minutes: 0,
      camera: null,
      ratings: [],
      suggestion: null,
      ranking: null,
      criterion_scores: [],
      fine_labels: [],
      // specs/features/0299-kategorie-konfidenz-anzeigen.md: Basiswert "keine Angabe".
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
      '/projects/1/photos?rating_status=unrated&limit=30&offset=60',
    )
  })

  it('encodes top_n_per_event as a query param', async () => {
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    await listPhotos(1, { topNPerEvent: 3 })

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/photos?top_n_per_event=3')
  })

  it('requests further curation candidates of one partition', async () => {
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    const result = await listCurationCandidates(1, {
      eventId: 42,
      afterRank: 10,
      limit: 60,
      offset: 60,
    })

    expect(apiFetch).toHaveBeenCalledWith(
      '/projects/1/curation-candidates?event_id=42&after_rank=10&limit=60&offset=60',
    )
    expect(result).toEqual(PHOTO_LIST)
  })

  it('addresses the partition by event id alone, with no free key left', async () => {
    /* Seit Spec 0427 tragen ALLE drei Query-Parameter dieses Endpunkts Zahlen - es gibt keinen
     * freien Schlüssel mehr, der etwas einschleusen könnte. Als eigener Fall, weil ein
     * stehengebliebener Schlüsselparameter in der Abfrage serverseitig schlicht ignoriert würde
     * und damit von jedem Positivtest unbemerkt bliebe. */
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    await listCurationCandidates(1, { eventId: 7, afterRank: 0 })

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/curation-candidates?event_id=7&after_rank=0')
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
})
