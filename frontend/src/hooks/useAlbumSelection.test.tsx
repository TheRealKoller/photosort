import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as albumSelectionApi from '../api/albumSelection'
import type { AlbumSelectionOut, PhotoOut } from '../api/types'
import { useAlbumDecisionMutation, useAlbumSelectionQuery } from './useAlbumSelection'

vi.mock('../api/albumSelection')

function photo(overrides: Partial<PhotoOut> = {}): PhotoOut {
  return {
    id: 1,
    relative_path: '1.jpg',
    taken_at: '2026-07-20T10:00:00',
    taken_at_original: '2026-07-20T10:00:00',
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
    ...overrides,
  }
}

function selection(items: PhotoOut[]): AlbumSelectionOut {
  return {
    participants: [
      { user_id: 1, username: 'daniel' },
      { user_id: 2, username: 'nora' },
    ],
    has_proposal: true,
    items,
  }
}

function sharedClient() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, wrapper }
}

beforeEach(() => {
  vi.mocked(albumSelectionApi.getAlbumSelection).mockReset()
  vi.mocked(albumSelectionApi.setAlbumDecision).mockReset()
})

describe('useAlbumSelectionQuery', () => {
  it('reads the selection under the broad photos prefix of the project', async () => {
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(selection([photo()]))
    const { queryClient, wrapper } = sharedClient()

    const { result } = renderHook(() => useAlbumSelectionQuery(7), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(albumSelectionApi.getAlbumSelection).toHaveBeenCalledWith(7)
    // Derselbe breite Praefix wie ueberall: eine Bewertung aus Raster/Einzelbild/Entwurf
    // invalidiert ihn mit.
    expect(queryClient.getQueryData<AlbumSelectionOut>(['photos', 7, 'selection'])).toBeDefined()
  })
})

describe('useAlbumDecisionMutation', () => {
  it('writes the affected entry FORWARD and reloads the selection not at all', async () => {
    // Zusicherung 25: Entscheiden laedt nicht nach. Der Zaehler auf `getAlbumSelection` traegt
    // die Zusage - eine breite Invalidierung traefe den eigenen Schluessel mit, und das
    // entschiedene Bild spraenge aus der Ergebnissicht.
    vi.mocked(albumSelectionApi.getAlbumSelection).mockResolvedValue(
      selection([photo({ id: 1, contested: true }), photo({ id: 2 })]),
    )
    vi.mocked(albumSelectionApi.setAlbumDecision).mockResolvedValue({
      photo_id: 1,
      included: true,
      updated_at: '2026-09-13T10:00:00',
    })
    const { queryClient, wrapper } = sharedClient()
    const query = renderHook(() => useAlbumSelectionQuery(7), { wrapper })
    await waitFor(() => expect(query.result.current.isSuccess).toBe(true))
    const callsBefore = vi.mocked(albumSelectionApi.getAlbumSelection).mock.calls.length

    const { result } = renderHook(() => useAlbumDecisionMutation(7), { wrapper })
    await result.current.mutateAsync({ photoId: 1, included: true })

    expect(albumSelectionApi.setAlbumDecision).toHaveBeenCalledWith(1, true)
    const cached = queryClient.getQueryData<AlbumSelectionOut>(['photos', 7, 'selection'])
    expect(cached?.items.map((item) => item.id)).toEqual([1, 2])
    expect(cached?.items[0].final_selection_decision).toBe(true)
    expect(cached?.items[0].in_final_selection).toBe(true)
    expect(cached?.items[0].contested).toBe(false)
    expect(vi.mocked(albumSelectionApi.getAlbumSelection).mock.calls.length).toBe(callsBefore)
  })

  it('invalidates the OTHER photo queries of the project and spares its own key', async () => {
    // Zwei Schluessel, einer unangetastet, einer invalidiert - sonst stuenden zwei Wahrheiten
    // ueber dasselbe Foto nebeneinander.
    vi.mocked(albumSelectionApi.setAlbumDecision).mockResolvedValue({
      photo_id: 1,
      included: false,
      updated_at: '2026-09-13T10:00:00',
    })
    const { queryClient, wrapper } = sharedClient()
    queryClient.setQueryData(['photos', 7, 'selection'], selection([photo({ id: 1 })]))
    queryClient.setQueryData(['photos', 7, null], { items: [], total: 0 })
    const invalidated: unknown[][] = []
    vi.spyOn(queryClient, 'invalidateQueries').mockImplementation((filters) => {
      const predicate = filters?.predicate
      for (const query of queryClient.getQueryCache().getAll()) {
        if (predicate === undefined || predicate(query)) {
          invalidated.push([...query.queryKey])
        }
      }
      return Promise.resolve()
    })

    const { result } = renderHook(() => useAlbumDecisionMutation(7), { wrapper })
    await result.current.mutateAsync({ photoId: 1, included: false })

    expect(invalidated).toContainEqual(['photos', 7, null])
    expect(invalidated).not.toContainEqual(['photos', 7, 'selection'])
  })

  it('leaves the cache alone when nothing is loaded yet', async () => {
    vi.mocked(albumSelectionApi.setAlbumDecision).mockResolvedValue({
      photo_id: 1,
      included: true,
      updated_at: '2026-09-13T10:00:00',
    })
    const { queryClient, wrapper } = sharedClient()

    const { result } = renderHook(() => useAlbumDecisionMutation(7), { wrapper })
    await result.current.mutateAsync({ photoId: 1, included: true })

    expect(queryClient.getQueryData(['photos', 7, 'selection'])).toBeUndefined()
  })
})
