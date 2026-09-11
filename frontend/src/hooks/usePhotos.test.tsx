import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type { PhotoListOut } from '../api/types'
import {
  PHOTOS_PAGE_SIZE,
  useCurationCandidatesQuery,
  useDeleteCategoryOverrideMutation,
  useDeleteRatingMutation,
  usePhotoSequenceQuery,
  useSetCategoryOverrideMutation,
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
      ratings: [],
      suggestion: null,
      rankings: [],
      criterion_scores: [],
      fine_labels: [],
      remote_category: null,
      // specs/features/0299-kategorie-konfidenz-anzeigen.md: Basiswert "keine Angabe".
      category_confidence: null,
      category_override: null,
      category_candidates: [],
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
  const partition = { clusterKey: 'cluster-0', categoryKey: 'landschaft', afterRank: 3 }

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
      clusterKey: 'cluster-0',
      categoryKey: 'landschaft',
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
      clusterKey: 'cluster-0',
      categoryKey: 'landschaft',
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
      user_id: 1,
      username: 'daniel',
      status: 'rejected',
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

describe('useSetRatingMutation', () => {
  it('sets the rating and invalidates all photo queries of the project', async () => {
    vi.mocked(photosApi.listPhotos).mockResolvedValue(page([1], 1))
    vi.mocked(ratingsApi.setRating).mockResolvedValue({
      user_id: 1,
      username: 'daniel',
      status: 'favorite',
    })
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const listWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    const listHook = renderHook(() => usePhotoSequenceQuery(1), { wrapper: listWrapper })
    await waitFor(() => expect(listHook.result.current.isSuccess).toBe(true))
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useSetRatingMutation(1), { wrapper: listWrapper })
    await result.current.mutateAsync({ photoId: 1, status: 'favorite' })

    expect(ratingsApi.setRating).toHaveBeenCalledWith(1, 'favorite')
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

describe('useSetCategoryOverrideMutation', () => {
  it('sets the category override and invalidates all photo queries of the project', async () => {
    vi.mocked(photosApi.setCategoryOverride).mockResolvedValue({
      photo_id: 1,
      category_key: 'hund',
    })
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const listWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useSetCategoryOverrideMutation(1), {
      wrapper: listWrapper,
    })
    await result.current.mutateAsync({ photoId: 1, categoryKey: 'hund' })

    expect(photosApi.setCategoryOverride).toHaveBeenCalledWith(1, 'hund')
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['photos', 1] })
  })
})

describe('useDeleteCategoryOverrideMutation', () => {
  it('deletes the category override and invalidates all photo queries of the project', async () => {
    vi.mocked(photosApi.deleteCategoryOverride).mockResolvedValue(undefined)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const listWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useDeleteCategoryOverrideMutation(1), {
      wrapper: listWrapper,
    })
    await result.current.mutateAsync(1)

    expect(photosApi.deleteCategoryOverride).toHaveBeenCalledWith(1)
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['photos', 1] })
  })
})
