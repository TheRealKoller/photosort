import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type { PhotoListOut } from '../api/types'
import {
  applyWrittenRating,
  PHOTOS_PAGE_SIZE,
  useCurationCandidatesQuery,
  useDeleteRatingMutation,
  useDraftDecisionMutation,
  useDraftQuery,
  usePhotoSequenceQuery,
  useSetFavoriteMutation,
  useSetRatingMutation,
} from './usePhotos'

vi.mock('../api/photos')
vi.mock('../api/ratings')

function page(items: number[], total: number): PhotoListOut {
  return {
    items: items.map((id) => ({
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
    })),
    total,
  }
}

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('usePhotoSequenceQuery', () => {
  it('fetches the first page with the given filter and page size', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(page([1, 2], 2))

    const { result } = renderHook(() => usePhotoSequenceQuery(1, 'unrated'), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(photosApi.listPhotos).toHaveBeenCalledWith(1, {
      ratingStatus: 'unrated',
      limit: PHOTOS_PAGE_SIZE,
      offset: 0,
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
    })
  })
})

describe('useCurationCandidatesQuery', () => {
  const partition = { eventId: 42, afterRank: 3 }

  // Die Datei laeuft ohne `clearMocks`; Aufrufzaehler und `…Once`-Warteschlange wandern sonst von
  // Testfall zu Testfall. Diese Gruppe zaehlt Aufrufe (statt nur ihre Argumente zu pruefen) und
  // braucht deshalb einen sauberen Ausgangszustand.
  beforeEach(() => {
    vi.mocked(photosApi.listCurationCandidates).mockReset()
  })

  it('does not fetch while the section is collapsed', async () => {
    vi.mocked(photosApi.listCurationCandidates).mockResolvedValue(page([4], 4))

    const { result } = renderHook(
      () => useCurationCandidatesQuery(1, { ...partition, enabled: false }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.fetchStatus).toBe('idle'))
    expect(photosApi.listCurationCandidates).not.toHaveBeenCalled()
  })

  it('fetches the first page once expanded', async () => {
    vi.mocked(photosApi.listCurationCandidates).mockResolvedValue(page([4], 1))

    const { result } = renderHook(
      () => useCurationCandidatesQuery(1, { ...partition, enabled: true }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(photosApi.listCurationCandidates).toHaveBeenCalledWith(1, {
      eventId: 42,
      afterRank: 3,
      limit: PHOTOS_PAGE_SIZE,
      offset: 0,
    })
  })

  it('fetchNextPage requests the SECOND page with the right offset and stops at total', async () => {
    // Die zweite Seite ist der Pflichtfall (Testkonzept, Sektion zu Spec 0357): die erste
    // bestuende auch bei einem fest verdrahteten `offset: 0`.
    vi.mocked(photosApi.listCurationCandidates)
      .mockResolvedValueOnce(page([4, 5], 3))
      .mockResolvedValueOnce(page([6], 3))

    const { result } = renderHook(
      () => useCurationCandidatesQuery(1, { ...partition, enabled: true, pageSize: 2 }),
      { wrapper },
    )
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.hasNextPage).toBe(true)

    await result.current.fetchNextPage()

    await waitFor(() => expect(result.current.hasNextPage).toBe(false))
    expect(photosApi.listCurationCandidates).toHaveBeenLastCalledWith(1, {
      eventId: 42,
      afterRank: 3,
      limit: 2,
      offset: 2,
    })
  })

  it('lives under the ["photos", projectId] prefix so a rating invalidates it too', async () => {
    // Zwei Queries ueber demselben Datensatz auf einem Bildschirm (Testkonzept, Sektion zu Spec
    // 0357): wird in der EINEN Liste bewertet, muss die ANDERE denselben Zustand zeigen. Der
    // Testgegenstand ist deshalb die Invalidierung, nicht der Ladepfad.
    vi.mocked(photosApi.listCurationCandidates)
      .mockResolvedValueOnce(page([4], 1))
      .mockResolvedValueOnce(page([4], 1))
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      photo_id: 4,
      user_id: 1,
      status: 'rejected',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const sharedWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    const candidates = renderHook(
      () => useCurationCandidatesQuery(1, { ...partition, enabled: true }),
      { wrapper: sharedWrapper },
    )
    await waitFor(() => expect(candidates.result.current.isSuccess).toBe(true))

    const { result } = renderHook(() => useSetRatingMutation(1), { wrapper: sharedWrapper })
    await result.current.mutateAsync({ photoId: 4, status: 'rejected' })

    await waitFor(() => expect(photosApi.listCurationCandidates).toHaveBeenCalledTimes(2))
  })
})

describe('useDraftQuery', () => {
  beforeEach(() => {
    vi.mocked(photosApi.listPhotos).mockReset()
  })

  it('asks for the draft mode, without any read parameter', async () => {
    // Welche Fotos der Entwurf umfasst, entscheidet der Server aus Lauf UND anfragendem Nutzer -
    // es gibt keinen Leseparameter, mit dem eine zweite Variante entstehen koennte.
    vi.mocked(photosApi.listPhotos).mockResolvedValue(page([1], 1))

    const { result } = renderHook(() => useDraftQuery(1), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(photosApi.listPhotos).toHaveBeenCalledWith(1, { draft: true })
  })
})

describe('useDraftDecisionMutation', () => {
  beforeEach(() => {
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(ratingsApi.setRating).mockReset()
  })

  /** Zwei Queries unter demselben Praefix: die Entwurfsabfrage und eine gewoehnliche Fotoliste. */
  function sharedClient() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const sharedWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    return { queryClient, sharedWrapper }
  }

  it('writes the decision into the cached draft entry and reloads nothing of the draft', async () => {
    // Zusicherung 22: Eine Entscheidung loest KEIN Neuladen der Entwurfsliste aus. Der Zaehler auf
    // `listPhotos` traegt die Zusage - eine breite Invalidierung ueber `['photos', projectId]`
    // traefe den Entwurfsschluessel mit, und die gerade gestrichene Kachel spraenge aus der Liste.
    vi.mocked(photosApi.listPhotos).mockResolvedValue(page([1], 1))
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      photo_id: 1,
      user_id: 7,
      status: 'rejected',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const { queryClient, sharedWrapper } = sharedClient()
    const draft = renderHook(() => useDraftQuery(1), { wrapper: sharedWrapper })
    await waitFor(() => expect(draft.result.current.isSuccess).toBe(true))
    const draftCallsBefore = vi
      .mocked(photosApi.listPhotos)
      .mock.calls.filter(([, params]) => params?.draft === true).length

    const { result } = renderHook(() => useDraftDecisionMutation(1, 'testuser'), {
      wrapper: sharedWrapper,
    })
    await result.current.mutateAsync({ photoId: 1, status: 'rejected' })

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'rejected')
    const cached = queryClient.getQueryData<PhotoListOut>(['photos', 1, 'draft'])
    expect(cached?.items.map((item) => item.id)).toEqual([1])
    expect(cached?.items[0].ratings).toEqual([
      { user_id: 7, username: 'testuser', status: 'rejected', favorite: false },
    ])
    const draftCallsAfter = vi
      .mocked(photosApi.listPhotos)
      .mock.calls.filter(([, params]) => params?.draft === true).length
    expect(draftCallsAfter).toBe(draftCallsBefore)
  })

  it('invalidates the OTHER photo queries of the project', async () => {
    // Die Gegenprobe zum Fall darueber: Was nicht der Entwurf ist, muss sehr wohl neu laden - die
    // Bewertung aendert die Zugehoerigkeit zu mehreren Rasterfiltern gleichzeitig.
    vi.mocked(photosApi.listPhotos).mockResolvedValue(page([1], 1))
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      photo_id: 1,
      user_id: 7,
      status: 'album_worthy',
      favorite: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const { sharedWrapper } = sharedClient()
    const listing = renderHook(() => usePhotoSequenceQuery(1), { wrapper: sharedWrapper })
    await waitFor(() => expect(listing.result.current.isSuccess).toBe(true))
    const listingCallsBefore = vi
      .mocked(photosApi.listPhotos)
      .mock.calls.filter(([, params]) => params?.draft !== true).length

    const { result } = renderHook(() => useDraftDecisionMutation(1, 'testuser'), {
      wrapper: sharedWrapper,
    })
    await result.current.mutateAsync({ photoId: 1, status: 'album_worthy' })

    await waitFor(() => {
      const listingCallsAfter = vi
        .mocked(photosApi.listPhotos)
        .mock.calls.filter(([, params]) => params?.draft !== true).length
      expect(listingCallsAfter).toBeGreaterThan(listingCallsBefore)
    })
  })
})

describe('applyWrittenRating', () => {
  /** Die reine Ableitung hinter dem Fortschreiben - ohne QueryClient pruefbar. */
  const LIST: PhotoListOut = page([1, 2], 2)

  it('replaces the own entry and leaves the entry of the other user untouched', () => {
    const withBoth: PhotoListOut = {
      ...LIST,
      items: LIST.items.map((item) =>
        item.id === 1
          ? {
              ...item,
              ratings: [
                { user_id: 9, username: 'other-user', status: 'album_worthy', favorite: false },
                { user_id: 7, username: 'testuser', status: 'album_worthy', favorite: true },
              ],
            }
          : item,
      ),
    }

    const next = applyWrittenRating(
      withBoth,
      {
        photo_id: 1,
        user_id: 7,
        status: 'rejected',
        favorite: true,
        updated_at: '2026-09-13T10:00:00',
      },
      'testuser',
    )

    expect(next.items[0].ratings).toEqual([
      { user_id: 9, username: 'other-user', status: 'album_worthy', favorite: false },
      { user_id: 7, username: 'testuser', status: 'rejected', favorite: true },
    ])
  })

  it('appends the entry when the photo carried no own rating yet', () => {
    const next = applyWrittenRating(
      LIST,
      {
        photo_id: 2,
        user_id: 7,
        status: 'album_worthy',
        favorite: false,
        updated_at: '2026-09-13T10:00:00',
      },
      'testuser',
    )

    expect(next.items[1].ratings).toEqual([
      { user_id: 7, username: 'testuser', status: 'album_worthy', favorite: false },
    ])
    // Das unbeteiligte Foto bleibt dieselbe Referenz - die Kachel rendert nicht neu.
    expect(next.items[0]).toBe(LIST.items[0])
  })

  it('drops the entry when the written row was emptied', () => {
    const withOwn: PhotoListOut = {
      ...LIST,
      items: LIST.items.map((item) =>
        item.id === 1
          ? {
              ...item,
              ratings: [{ user_id: 7, username: 'testuser', status: 'rejected', favorite: false }],
            }
          : item,
      ),
    }

    const next = applyWrittenRating(
      withOwn,
      { photo_id: 1, user_id: 7, status: null, favorite: false, updated_at: null },
      'testuser',
    )

    expect(next.items[0].ratings).toEqual([])
  })

  it('leaves a list without the written photo unchanged', () => {
    const next = applyWrittenRating(
      LIST,
      {
        photo_id: 99,
        user_id: 7,
        status: 'rejected',
        favorite: false,
        updated_at: '2026-09-13T10:00:00',
      },
      'testuser',
    )

    expect(next).toEqual(LIST)
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
    vi.mocked(ratingsApi.deleteRating).mockResolvedValue(undefined)
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
