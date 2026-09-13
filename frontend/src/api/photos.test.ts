import { describe, expect, it, vi } from 'vitest'

import { apiFetch, apiFetchBlob } from './client'
import { fetchPhotoImageBlobUrl, listDraftAlternatives, listPhotos } from './photos'
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

  it('encodes the draft mode as a query param', async () => {
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    await listPhotos(1, { draft: true })

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/photos?draft=true')
  })

  it('sends no draft parameter without the draft mode', async () => {
    /* Der Gegenfall: `draft=false` ist der serverseitige Vorgabewert, und ein mitgesendeter
     * `false`-Parameter wäre eine zweite Schreibweise für denselben Zustand. */
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    await listPhotos(1, { limit: 30 })

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/photos?limit=30')
  })

  it('never sends the abolished selection parameter', async () => {
    /* Der abgeschaffte Parameter endet serverseitig in `422` - in BEIDEN Belegungen. Ein
     * Aufrufer, der ihn noch mitsendete, bekäme also gar keine Antwort mehr. */
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    await listPhotos(1, { draft: true })

    expect(vi.mocked(apiFetch).mock.calls.at(-1)?.[0]).not.toContain('selection')
  })

  it('requests the alternatives of one photo of one event', async () => {
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    const result = await listDraftAlternatives(1, {
      eventId: 42,
      photoId: 7,
      limit: 60,
      offset: 60,
    })

    expect(apiFetch).toHaveBeenCalledWith(
      '/projects/1/draft-alternatives?event_id=42&photo_id=7&limit=60&offset=60',
    )
    expect(result).toEqual(PHOTO_LIST)
  })

  it('addresses event and reference by their ids alone, with no free key anywhere', async () => {
    /* ALLE vier Query-Parameter dieses Endpunkts tragen Zahlen - es gibt keinen freien Schlüssel,
     * der etwas einschleusen könnte. Als eigener Fall, weil ein stehengebliebener
     * Schlüsselparameter serverseitig schlicht ignoriert würde und damit von jedem Positivtest
     * unbemerkt bliebe. */
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    await listDraftAlternatives(1, { eventId: 7, photoId: 3 })

    expect(apiFetch).toHaveBeenCalledWith('/projects/1/draft-alternatives?event_id=7&photo_id=3')
  })

  it('never calls the endpoint that was replaced', async () => {
    /* `GET /projects/{id}/curation-candidates` entfällt ersatzlos und antwortet `404`. Ein
     * stehengebliebener Aufrufer wäre ein toter Weg, der erst im Browser auffiele. */
    vi.mocked(apiFetch).mockResolvedValue(PHOTO_LIST)

    await listDraftAlternatives(1, { eventId: 7, photoId: 3 })

    expect(vi.mocked(apiFetch).mock.calls.at(-1)?.[0]).not.toContain('curation-candidates')
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
