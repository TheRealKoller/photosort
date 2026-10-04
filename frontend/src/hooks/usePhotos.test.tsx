import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type {
  AlbumDraftOut,
  DraftAlternativesOut,
  EventOut,
  PhotoListOut,
  PhotoOut,
  RatingStatus,
  RatingWriteOut,
} from '../api/types'
import { setToken } from '../auth/token'
import { draftMembership } from '../utils/albumDraft'
import { ownRatingStatus } from '../utils/ownRating'
import {
  applyWrittenRating,
  draftQueryKey,
  PHOTOS_PAGE_SIZE,
  useDeleteRatingMutation,
  useDraftAlternativesQuery,
  useDraftDecisionMutation,
  useDraftExchangeMutation,
  useDraftExchangeUndoMutation,
  useDraftQuery,
  usePhotoSequenceQuery,
  useSetFavoriteMutation,
  useSetRatingMutation,
} from './usePhotos'

vi.mock('../api/photos')
vi.mock('../api/ratings')

const USERNAME = 'testuser'
const USER_ID = 7

/** Ein syntaktisch gueltiges JWT mit dem gegebenen `username`-Claim. */
function tokenFor(username: string): string {
  return `header.${btoa(JSON.stringify({ sub: '7', username }))}.signature`
}

const EVENT: EventOut = {
  id: 42,
  position: 1,
  started_at: '2026-07-20T09:00:00',
  ended_at: '2026-07-20T13:00:00',
  place: null,
  place_name: null,
}

function photo(id: number, overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id,
    relative_path: `${id}.jpg`,
    taken_at: '2026-07-20T10:00:00Z',
    taken_at_original: '2026-07-20T10:00:00Z',
    time_offset_minutes: 0,
    camera: null,
    ratings: [],
    suggestion: null,
    ranking: null,
    criterion_scores: [],
    fine_labels: [],
    cloud_vision_status: [],
    final_selection_decision: null,
    in_final_selection: false,
    contested: false,
    persons: [],
    ...overrides,
  }
}

function page(items: number[], total: number): PhotoListOut {
  return { items: items.map((id) => photo(id)), total }
}

function alternativesPage(items: number[], total: number, offset = 0): DraftAlternativesOut {
  return { items: items.map((id) => photo(id)), total, offset, reference_index: 0 }
}

/** Eine Entwurfsantwort mit dem einen Event; die Kandidatenzahl spielt in diesen Fällen keine Rolle. */
function draftOf(items: PhotoOut[]): AlbumDraftOut {
  return { events: [EVENT], items, eligible_candidate_count: items.length }
}

/** Ein Foto des Entwurfs: im Event, mit Rangzeile, vorgeschlagen oder nicht. */
function draftPhoto(id: number, takenAt: string, proposed: boolean): PhotoOut {
  return photo(id, {
    taken_at: takenAt,
    event: EVENT,
    ranking: {
      event_id: EVENT.id,
      rank_score: 0.5,
      rank_position: id,
      proposed,
      partition_size: 4,
      curation_position: null,
    },
  })
}

function written(photoId: number, status: RatingStatus | null): RatingWriteOut {
  return {
    photo_id: photoId,
    user_id: USER_ID,
    status,
    favorite: false,
    updated_at: status === null ? null : '2026-09-13T10:00:00',
  }
}

function sharedClient() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const sharedWrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, sharedWrapper }
}

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

beforeEach(() => {
  setToken(tokenFor(USERNAME))
})

afterEach(() => {
  window.localStorage.clear()
})

describe('usePhotoSequenceQuery', () => {
  it('fetches the first page with the given filter and page size', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(page([1, 2], 2))

    const { result } = renderHook(() => usePhotoSequenceQuery(1, 'unrated'), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(photosApi.listPhotos).toHaveBeenCalledWith(1, {
      ratingStatus: 'unrated',
      limit: PHOTOS_PAGE_SIZE,
      offset: 0,
      personIds: [],
    })
  })

  it('fetchNextPage requests the next offset and stops once total is reached', async () => {
    vi.mocked(photosApi.listPhotos)
      .mockResolvedValueOnce(page([1, 2], 3))
      .mockResolvedValueOnce(page([3], 3))
    const { result } = renderHook(() => usePhotoSequenceQuery(1, undefined, 2), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.hasNextPage).toBe(true)

    await result.current.fetchNextPage()

    await waitFor(() => expect(result.current.hasNextPage).toBe(false))
    expect(photosApi.listPhotos).toHaveBeenLastCalledWith(1, {
      ratingStatus: undefined,
      limit: 2,
      offset: 2,
      personIds: [],
    })
  })
})

describe('useDraftAlternativesQuery', () => {
  const reference = { eventId: 42, photoId: 7 }

  // Die Datei laeuft ohne `clearMocks`; diese Gruppe zaehlt Aufrufe und braucht deshalb einen
  // sauberen Ausgangszustand.
  beforeEach(() => {
    vi.mocked(photosApi.listDraftAlternatives).mockReset()
  })

  it('does not fetch while closed', async () => {
    // EINE Abfrage je GEOEFFNETEM Bild, nie eine je Kachel.
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(alternativesPage([4], 4))

    const { result } = renderHook(
      () => useDraftAlternativesQuery(1, { ...reference, enabled: false }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.fetchStatus).toBe('idle'))
    expect(photosApi.listDraftAlternatives).not.toHaveBeenCalled()
  })

  it('fetches the first page once opened, and asks without a reference for the add field', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(alternativesPage([4], 1))

    const band = renderHook(() => useDraftAlternativesQuery(1, { ...reference, enabled: true }), {
      wrapper,
    })
    const panel = renderHook(
      () =>
        useDraftAlternativesQuery(1, { eventId: 42, photoId: null, enabled: true, pageSize: 8 }),
      { wrapper },
    )

    await waitFor(() => expect(band.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(panel.result.current.isSuccess).toBe(true))
    expect(photosApi.listDraftAlternatives).toHaveBeenCalledWith(1, {
      eventId: 42,
      photoId: 7,
      limit: PHOTOS_PAGE_SIZE,
      offset: 0,
    })
    expect(photosApi.listDraftAlternatives).toHaveBeenCalledWith(1, {
      eventId: 42,
      limit: 8,
      offset: 0,
    })
  })

  it('fetchNextPage requests the SECOND page with the right offset and stops at total', async () => {
    vi.mocked(photosApi.listDraftAlternatives)
      .mockResolvedValueOnce(alternativesPage([4, 5], 3))
      .mockResolvedValueOnce(alternativesPage([6], 3, 2))

    const { result } = renderHook(
      () => useDraftAlternativesQuery(1, { ...reference, enabled: true, pageSize: 2 }),
      { wrapper },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.hasNextPage).toBe(true)

    await result.current.fetchNextPage()

    await waitFor(() => expect(result.current.hasNextPage).toBe(false))
    expect(photosApi.listDraftAlternatives).toHaveBeenLastCalledWith(1, {
      eventId: 42,
      photoId: 7,
      limit: 2,
      offset: 2,
    })
  })

  it('fetches the band as ONE window with nearest and never a following page', async () => {
    // Das Fenster schneidet allein der Server; `total` ist die Restmenge und liegt
    // ueber der Fenstergroesse - trotzdem gibt es keine Folgeseite.
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(
      alternativesPage([4, 5, 6, 7], 10, 3),
    )

    const { result } = renderHook(
      () => useDraftAlternativesQuery(1, { ...reference, enabled: true, nearest: 4 }),
      { wrapper },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(photosApi.listDraftAlternatives).toHaveBeenCalledTimes(1)
    expect(photosApi.listDraftAlternatives).toHaveBeenCalledWith(1, {
      eventId: 42,
      photoId: 7,
      nearest: 4,
    })
    expect(result.current.hasNextPage).toBe(false)
  })

  it('gives band, dialog and add panel three different keys under ["photos", id]', async () => {
    // Band (Bezugsbild, vier), Dialog (Bezugsbild, Seitenweise) und Panel (ohne Bezugsbild, acht)
    // holten unter einem gemeinsamen Schluessel dieselbe Cache-Zeile.
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(alternativesPage([4], 1))
    const { queryClient, sharedWrapper } = sharedClient()

    for (const params of [
      { ...reference, nearest: 4 },
      { ...reference },
      { eventId: 42, photoId: null, pageSize: 8 },
    ]) {
      const hook = renderHook(() => useDraftAlternativesQuery(1, { ...params, enabled: true }), {
        wrapper: sharedWrapper,
      })
      await waitFor(() => expect(hook.result.current.isSuccess).toBe(true))
    }

    expect(photosApi.listDraftAlternatives).toHaveBeenCalledTimes(3)
    const keys = queryClient
      .getQueryCache()
      .findAll({ queryKey: ['photos', 1] })
      .map((query) => query.queryKey)
    expect(keys).toHaveLength(3)
    // S4: die Identitaet steht in jedem Schluessel, hinter dem Praefix.
    for (const key of keys) {
      expect(key.slice(0, 4)).toEqual(['photos', 1, 'alternatives', USERNAME])
    }
  })

  it('lives under the ["photos", projectId] prefix so a rating invalidates it too', async () => {
    vi.mocked(photosApi.listDraftAlternatives).mockResolvedValue(alternativesPage([4], 1))
    vi.mocked(ratingsApi.setRating).mockResolvedValue(written(4, 'rejected'))
    const { sharedWrapper } = sharedClient()
    const alternatives = renderHook(
      () => useDraftAlternativesQuery(1, { ...reference, enabled: true }),
      { wrapper: sharedWrapper },
    )
    await waitFor(() => expect(alternatives.result.current.isSuccess).toBe(true))

    const { result } = renderHook(() => useSetRatingMutation(1), { wrapper: sharedWrapper })
    await result.current.mutateAsync({ photoId: 4, status: 'rejected' })

    await waitFor(() => expect(photosApi.listDraftAlternatives).toHaveBeenCalledTimes(2))
  })
})

describe('useDraftQuery', () => {
  beforeEach(() => {
    vi.mocked(photosApi.getAlbumDraft).mockReset()
  })

  it('reads the album draft endpoint, under a key that carries the identity', async () => {
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draftOf([]))
    const { queryClient, sharedWrapper } = sharedClient()

    const { result } = renderHook(() => useDraftQuery(1), { wrapper: sharedWrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(photosApi.getAlbumDraft).toHaveBeenCalledWith(1)
    expect(queryClient.getQueryData(['photos', 1, 'draft', USERNAME])).toEqual({
      events: [EVENT],
      items: [],
      eligible_candidate_count: 0,
    })
  })

  it('gives a second user in the same tab a different key', () => {
    // S4: Der `QueryClient` ueberlebt den Nutzerwechsel. Unter einem gemeinsamen Schluessel saehe
    // der zweite den Entwurf des ersten, bis das Neuladen abgeschlossen ist.
    const first = draftQueryKey(1)
    setToken(tokenFor('anna'))

    expect(draftQueryKey(1)).not.toEqual(first)
  })
})

describe('applyWrittenRating', () => {
  const proposed = draftPhoto(1, '2026-07-20T10:00:00', true)
  const candidate = draftPhoto(2, '2026-07-20T11:00:00', false)
  const DRAFT: AlbumDraftOut = draftOf([proposed, candidate])

  it('replaces the own entry and leaves the entry of the other user untouched', () => {
    const withBoth: AlbumDraftOut = {
      ...DRAFT,
      items: [
        {
          ...proposed,
          ratings: [
            { user_id: 9, username: 'other-user', status: 'album_worthy', favorite: false },
            { user_id: USER_ID, username: USERNAME, status: 'album_worthy', favorite: true },
          ],
        },
        candidate,
      ],
    }

    const next = applyWrittenRating(
      withBoth,
      { ...written(1, 'rejected'), favorite: true },
      USERNAME,
    )

    expect(next.items[0].ratings).toEqual([
      { user_id: 9, username: 'other-user', status: 'album_worthy', favorite: false },
      { user_id: USER_ID, username: USERNAME, status: 'rejected', favorite: true },
    ])
    // Das unbeteiligte Foto bleibt dieselbe Referenz - die Kachel rendert nicht neu.
    expect(next.items[1]).toBe(candidate)
    expect(next.events).toBe(DRAFT.events)
  })

  it('drops the own entry when the written row was emptied, and keeps a proposed photo', () => {
    const struck: AlbumDraftOut = {
      ...DRAFT,
      items: [
        {
          ...proposed,
          ratings: [{ user_id: USER_ID, username: USERNAME, status: 'rejected', favorite: false }],
        },
      ],
    }

    const next = applyWrittenRating(struck, written(1, null), USERNAME)

    expect(next.items.map((item) => item.id)).toEqual([1])
    expect(next.items[0].ratings).toEqual([])
  })

  it('removes a photo that leaves the answer set (DELETE on a struck candidate)', () => {
    // Gestrichen und nicht vorgeschlagen steht das Foto mit seiner Rangzeile in der Antwort; ohne
    // eigene Entscheidung gehoert es nicht mehr dazu - genau wie nach einem Neuladen.
    const struck: AlbumDraftOut = {
      ...DRAFT,
      items: [
        proposed,
        {
          ...candidate,
          ratings: [{ user_id: USER_ID, username: USERNAME, status: 'rejected', favorite: false }],
        },
      ],
    }

    const next = applyWrittenRating(struck, written(2, null), USERNAME)

    expect(next.items.map((item) => item.id)).toEqual([1])
  })

  it('leaves a draft without the written photo unchanged', () => {
    expect(applyWrittenRating(DRAFT, written(99, 'rejected'), USERNAME)).toEqual(DRAFT)
  })
})

describe('useDraftDecisionMutation', () => {
  beforeEach(() => {
    vi.mocked(photosApi.getAlbumDraft).mockReset()
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(ratingsApi.setRating).mockReset()
    vi.mocked(ratingsApi.deleteRating).mockReset()
  })

  it('withdraws with DELETE for status null and writes the answer into the cache', async () => {
    const struck = {
      ...draftPhoto(1, '2026-07-20T10:00:00', true),
      ratings: [
        { user_id: USER_ID, username: USERNAME, status: 'rejected' as const, favorite: false },
      ],
    }
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draftOf([struck]))
    vi.mocked(ratingsApi.deleteRating).mockResolvedValue(written(1, null))
    const { queryClient, sharedWrapper } = sharedClient()
    const draft = renderHook(() => useDraftQuery(1), { wrapper: sharedWrapper })
    await waitFor(() => expect(draft.result.current.isSuccess).toBe(true))

    const { result } = renderHook(() => useDraftDecisionMutation(1, USERNAME), {
      wrapper: sharedWrapper,
    })
    await result.current.mutateAsync({ photoId: 1, status: null })

    expect(ratingsApi.deleteRating).toHaveBeenCalledWith(1)
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
    expect(queryClient.getQueryData<AlbumDraftOut>(draftQueryKey(1))?.items[0].ratings).toEqual([])
  })

  it('inserts the added photo at its place, and reloads nothing of the draft', async () => {
    const first = draftPhoto(1, '2026-07-20T10:00:00', true)
    const third = draftPhoto(3, '2026-07-20T12:00:00', true)
    const added = draftPhoto(2, '2026-07-20T11:00:00', false)
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draftOf([first, third]))
    vi.mocked(ratingsApi.setRating).mockResolvedValue(written(2, 'album_worthy'))
    const { queryClient, sharedWrapper } = sharedClient()
    const draft = renderHook(() => useDraftQuery(1), { wrapper: sharedWrapper })
    await waitFor(() => expect(draft.result.current.isSuccess).toBe(true))

    const { result } = renderHook(() => useDraftDecisionMutation(1, USERNAME), {
      wrapper: sharedWrapper,
    })
    await result.current.mutateAsync({ photoId: 2, status: 'album_worthy', insert: added })

    const cached = queryClient.getQueryData<AlbumDraftOut>(draftQueryKey(1))
    expect(cached?.items.map((item) => item.id)).toEqual([1, 2, 3])
    expect(cached?.items[1].ratings[0]?.status).toBe('album_worthy')
    expect(photosApi.getAlbumDraft).toHaveBeenCalledTimes(1)
  })

  it('invalidates the other photo queries but not the own draft key', async () => {
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(
      draftOf([draftPhoto(1, '2026-07-20T10:00:00', true)]),
    )
    vi.mocked(photosApi.listPhotos).mockResolvedValue(page([1], 1))
    vi.mocked(ratingsApi.setRating).mockResolvedValue(written(1, 'rejected'))
    const { queryClient, sharedWrapper } = sharedClient()
    const draft = renderHook(() => useDraftQuery(1), { wrapper: sharedWrapper })
    const listing = renderHook(() => usePhotoSequenceQuery(1), { wrapper: sharedWrapper })
    await waitFor(() => expect(draft.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(listing.result.current.isSuccess).toBe(true))

    const { result } = renderHook(() => useDraftDecisionMutation(1, USERNAME), {
      wrapper: sharedWrapper,
    })
    await result.current.mutateAsync({ photoId: 1, status: 'rejected' })

    await waitFor(() => expect(photosApi.listPhotos).toHaveBeenCalledTimes(2))
    expect(queryClient.getQueryState(draftQueryKey(1))?.isInvalidated).toBe(false)
    expect(photosApi.getAlbumDraft).toHaveBeenCalledTimes(1)
  })
})

describe('useSetRatingMutation against the draft', () => {
  it('invalidates the draft key - a decision elsewhere must reach the draft', async () => {
    // Der Gegenfall zur Ausnahme oben: Im Raster oder in der Endauswahl bewertet, muss der Entwurf
    // beim naechsten Besuch neu laden.
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draftOf([]))
    vi.mocked(ratingsApi.setRating).mockResolvedValue(written(1, 'rejected'))
    const { queryClient, sharedWrapper } = sharedClient()
    const draft = renderHook(() => useDraftQuery(1), { wrapper: sharedWrapper })
    await waitFor(() => expect(draft.result.current.isSuccess).toBe(true))
    draft.unmount()

    const { result } = renderHook(() => useSetRatingMutation(1), { wrapper: sharedWrapper })
    await result.current.mutateAsync({ photoId: 1, status: 'rejected' })

    expect(queryClient.getQueryState(draftQueryKey(1))?.isInvalidated).toBe(true)
  })
})

describe('useDraftExchangeMutation', () => {
  beforeEach(() => {
    vi.mocked(photosApi.getAlbumDraft).mockReset()
    vi.mocked(photosApi.exchangeDraftPhoto).mockReset()
    vi.mocked(ratingsApi.setRating).mockReset()
  })

  it('writes ONE exchange call and no rating call at all', async () => {
    // DIE NEGATIVE ASSERTION IST DIE TRAGENDE: Ein stehengebliebener Doppelschreibweg erzeugte
    // je Tausch DREI Ereignisse statt einem.
    vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValue({
      taken: written(2, 'album_worthy'),
      struck: written(1, 'rejected'),
    })
    const { result } = renderHook(() => useDraftExchangeMutation(1, USERNAME), { wrapper })

    await result.current.mutateAsync({
      replaced: draftPhoto(1, '2026-07-20T10:00:00', true),
      chosen: draftPhoto(2, '2026-07-20T11:00:00', false),
    })

    // Das GEWAEHLTE Bild zuerst, das ersetzte danach - die Reihenfolge des Bodys.
    expect(vi.mocked(photosApi.exchangeDraftPhoto).mock.calls).toEqual([[1, 2, 1]])
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
  })

  it('keeps the replaced photo in the cache as struck and inserts the chosen one', async () => {
    // Das ersetzte Bild bleibt im Cache und traegt „gestrichen" - die Ansicht blendet es aus und
    // fuehrt es in der Gestrichen-Zeile. Die Alternative kommt an ihren chronologischen Platz.
    const replaced = draftPhoto(1, '2026-07-20T10:00:00', true)
    const chosen = draftPhoto(2, '2026-07-20T11:00:00', false)
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draftOf([replaced]))
    vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValue({
      taken: written(2, 'album_worthy'),
      struck: written(1, 'rejected'),
    })
    const { queryClient, sharedWrapper } = sharedClient()
    const draft = renderHook(() => useDraftQuery(1), { wrapper: sharedWrapper })
    await waitFor(() => expect(draft.result.current.isSuccess).toBe(true))

    const { result } = renderHook(() => useDraftExchangeMutation(1, USERNAME), {
      wrapper: sharedWrapper,
    })
    await result.current.mutateAsync({ replaced, chosen })

    const cached = queryClient.getQueryData<AlbumDraftOut>(draftQueryKey(1))
    expect(cached?.items.map((item) => item.id)).toEqual([1, 2])
    expect(cached?.items.map((item) => item.ratings[0]?.status)).toEqual([
      'rejected',
      'album_worthy',
    ])
    expect(photosApi.getAlbumDraft).toHaveBeenCalledTimes(1)
  })

  it('leaves the draft cache untouched when the exchange fails', async () => {
    const replaced = draftPhoto(1, '2026-07-20T10:00:00', true)
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draftOf([replaced]))
    vi.mocked(photosApi.exchangeDraftPhoto).mockRejectedValue(new Error('422'))
    const { queryClient, sharedWrapper } = sharedClient()
    const draft = renderHook(() => useDraftQuery(1), { wrapper: sharedWrapper })
    await waitFor(() => expect(draft.result.current.isSuccess).toBe(true))

    const { result } = renderHook(() => useDraftExchangeMutation(1, USERNAME), {
      wrapper: sharedWrapper,
    })
    await expect(
      result.current.mutateAsync({ replaced, chosen: draftPhoto(2, '2026-07-20T11:00:00', false) }),
    ).rejects.toThrow()

    expect(queryClient.getQueryData(draftQueryKey(1))).toEqual(draftOf([replaced]))
  })
})

describe('useDraftExchangeUndoMutation', () => {
  const replaced = {
    ...draftPhoto(1, '2026-07-20T10:00:00', true),
    ratings: [
      { user_id: USER_ID, username: USERNAME, status: 'rejected' as const, favorite: false },
    ],
  }
  const chosen = {
    ...draftPhoto(2, '2026-07-20T11:00:00', false),
    ratings: [
      { user_id: USER_ID, username: USERNAME, status: 'album_worthy' as const, favorite: false },
    ],
  }
  const body = {
    photo_id: 2,
    replaced_photo_id: 1,
    photo_previous_status: null,
    replaced_previous_status: null,
  }

  beforeEach(() => {
    vi.mocked(photosApi.getAlbumDraft).mockReset()
    vi.mocked(photosApi.undoDraftExchange).mockReset()
  })

  it('writes both restored rows: the replaced photo returns, the alternative leaves', async () => {
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draftOf([replaced, chosen]))
    vi.mocked(photosApi.undoDraftExchange).mockResolvedValue({
      photo: written(2, null),
      replaced: written(1, null),
    })
    const { queryClient, sharedWrapper } = sharedClient()
    const draft = renderHook(() => useDraftQuery(1), { wrapper: sharedWrapper })
    await waitFor(() => expect(draft.result.current.isSuccess).toBe(true))

    const { result } = renderHook(() => useDraftExchangeUndoMutation(1, USERNAME), {
      wrapper: sharedWrapper,
    })
    await result.current.mutateAsync(body)

    expect(photosApi.undoDraftExchange).toHaveBeenCalledWith(1, body)
    const cached = queryClient.getQueryData<AlbumDraftOut>(draftQueryKey(1))
    expect(cached?.items.map((item) => item.id)).toEqual([1])
    expect(cached?.items[0].ratings).toEqual([])
  })

  it('leaves the cache untouched on a 409', async () => {
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draftOf([replaced, chosen]))
    vi.mocked(photosApi.undoDraftExchange).mockRejectedValue(new ApiError(409, 'veraendert'))
    const { queryClient, sharedWrapper } = sharedClient()
    const draft = renderHook(() => useDraftQuery(1), { wrapper: sharedWrapper })
    await waitFor(() => expect(draft.result.current.isSuccess).toBe(true))
    const before = queryClient.getQueryData(draftQueryKey(1))

    const { result } = renderHook(() => useDraftExchangeUndoMutation(1, USERNAME), {
      wrapper: sharedWrapper,
    })
    await expect(result.current.mutateAsync(body)).rejects.toThrow()

    expect(queryClient.getQueryData(draftQueryKey(1))).toBe(before)
  })
})

describe('a sequence of draft actions', () => {
  it('keeps the cache equal to the answer set after every step, loading the draft once', async () => {
    /*
     * Streichen -> Rückgängig -> Wiederaufnehmen -> Hinzufügen -> Tausch -> Rückgängig. Nach jedem
     * Schritt ist die Cache-Menge die Menge der Fotos mit `draftMembership !== 'out'` in
     * Sortierfolge - der Stand, den ein Neuladen zeigte -, und `getAlbumDraft` lief genau einmal.
     */
    vi.mocked(photosApi.getAlbumDraft).mockReset()
    const proposedA = draftPhoto(1, '2026-07-20T10:00:00', true)
    const proposedB = draftPhoto(2, '2026-07-20T11:00:00', true)
    const candidateC = draftPhoto(3, '2026-07-20T12:00:00', false)
    const candidateD = draftPhoto(4, '2026-07-20T09:30:00', false)
    vi.mocked(photosApi.getAlbumDraft).mockResolvedValue(draftOf([proposedA, proposedB]))
    const { queryClient, sharedWrapper } = sharedClient()
    const draft = renderHook(() => useDraftQuery(1), { wrapper: sharedWrapper })
    await waitFor(() => expect(draft.result.current.isSuccess).toBe(true))
    const decision = renderHook(() => useDraftDecisionMutation(1, USERNAME), {
      wrapper: sharedWrapper,
    })
    const exchange = renderHook(() => useDraftExchangeMutation(1, USERNAME), {
      wrapper: sharedWrapper,
    })
    const undo = renderHook(() => useDraftExchangeUndoMutation(1, USERNAME), {
      wrapper: sharedWrapper,
    })

    function expectAnswerSet(ids: number[]) {
      const items = queryClient.getQueryData<AlbumDraftOut>(draftQueryKey(1))?.items ?? []
      expect(items.map((item) => item.id)).toEqual(ids)
      for (const item of items) {
        expect(draftMembership(item, ownRatingStatus(item.ratings, USERNAME))).not.toBe('out')
      }
    }

    // Streichen von A: bleibt als gestrichen in der Antwort.
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(1, 'rejected'))
    await decision.result.current.mutateAsync({ photoId: 1, status: 'rejected' })
    expectAnswerSet([1, 2])

    // Rückgängig ohne Vorzustand: DELETE, A ist wieder Vorschlag.
    vi.mocked(ratingsApi.deleteRating).mockResolvedValueOnce(written(1, null))
    await decision.result.current.mutateAsync({ photoId: 1, status: null })
    expectAnswerSet([1, 2])

    // Hinzufügen von D (früher als A): steht danach vorn.
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(4, 'album_worthy'))
    await decision.result.current.mutateAsync({
      photoId: 4,
      status: 'album_worthy',
      insert: candidateD,
    })
    expectAnswerSet([4, 1, 2])

    // Streichen und Wiederaufnehmen von D (nicht vorgeschlagen): wieder aufgenommen.
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(4, 'rejected'))
    await decision.result.current.mutateAsync({ photoId: 4, status: 'rejected' })
    vi.mocked(ratingsApi.setRating).mockResolvedValueOnce(written(4, 'album_worthy'))
    await decision.result.current.mutateAsync({ photoId: 4, status: 'album_worthy' })
    expectAnswerSet([4, 1, 2])

    // Tausch B gegen das unberührte C.
    vi.mocked(photosApi.exchangeDraftPhoto).mockResolvedValueOnce({
      taken: written(3, 'album_worthy'),
      struck: written(2, 'rejected'),
    })
    await exchange.result.current.mutateAsync({ replaced: proposedB, chosen: candidateC })
    expectAnswerSet([4, 1, 2, 3])

    // Rückgängig: B zurück zum Vorschlag, C verlässt die Antwort.
    vi.mocked(photosApi.undoDraftExchange).mockResolvedValueOnce({
      photo: written(3, null),
      replaced: written(2, null),
    })
    await undo.result.current.mutateAsync({
      photo_id: 3,
      replaced_photo_id: 2,
      photo_previous_status: null,
      replaced_previous_status: null,
    })
    expectAnswerSet([4, 1, 2])

    expect(photosApi.getAlbumDraft).toHaveBeenCalledTimes(1)
  })
})

describe('useSetRatingMutation', () => {
  it('sets the rating and invalidates all photo queries of the project', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(page([1], 1))
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: 'album_worthy',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const listWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    const listHook = renderHook(() => usePhotoSequenceQuery(1), { wrapper: listWrapper })
    await waitFor(() => expect(listHook.result.current.isSuccess).toBe(true))
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useSetRatingMutation(1), { wrapper: listWrapper })
    await result.current.mutateAsync({ photoId: 1, status: 'album_worthy' })

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'album_worthy')
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['photos', 1] })
  })
})

describe('useSetFavoriteMutation', () => {
  it('writes through the favorite endpoint, never through the rating one', async () => {
    // Die Trennung der beiden Schreibwege ist der Zweck der Story: ein gemeinsamer Pfad setzte
    // die Albumentscheidung beim Markieren als Favorit still zurueck. Die Aufrufzaehler sind
    // datei-global; ohne diesen Reset traegt die Abwesenheits-Zusicherung unten nichts.
    vi.mocked(ratingsApi.setRating).mockReset()
    vi.mocked(ratingsApi.setFavorite).mockResolvedValue({
      photo_id: 1,
      user_id: 1,
      status: 'album_worthy',
      favorite: true,
      updated_at: '2026-09-13T10:00:00',
    })
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const listWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useSetFavoriteMutation(1), { wrapper: listWrapper })
    await result.current.mutateAsync({ photoId: 1, favorite: true })

    expect(ratingsApi.setFavorite).toHaveBeenCalledWith(1, true)
    expect(ratingsApi.setRating).not.toHaveBeenCalled()
    // Dieselbe breite Invalidierung: das Kennzeichen entscheidet ueber den Filter "Favorit",
    // und der Filter steckt im Query-Key.
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['photos', 1] })
  })
})

describe('useDeleteRatingMutation', () => {
  it('deletes the rating and invalidates all photo queries of the project', async () => {
    vi.mocked(ratingsApi.deleteRating).mockResolvedValue(written(1, null))
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const listWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useDeleteRatingMutation(1), { wrapper: listWrapper })
    await result.current.mutateAsync(1)

    expect(ratingsApi.deleteRating).toHaveBeenCalledWith(1)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['photos', 1] })
  })
})
