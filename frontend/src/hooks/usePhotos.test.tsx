import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import * as photosApi from '../api/photos'
import * as ratingsApi from '../api/ratings'
import type { PhotoListOut } from '../api/types'
import {
  PHOTOS_PAGE_SIZE,
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
      ranking: null,
      criterion_scores: [],
      remote_category_labels: [],
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
