import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as ausschussApi from '../api/ausschuss'
import type { AusschussOut, PhotoOut } from '../api/types'
import { AUSSCHUSS_PAGE_SIZE, useAusschussEntryQuery, useAusschussQuery } from './useAusschuss'

vi.mock('../api/ausschuss')

function photo(id: number): PhotoOut {
  return {
    id,
    relative_path: `Reise/serie-${id}.jpg`,
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
  }
}

function stand(ids: number[], total: number): AusschussOut {
  return {
    items: ids.map((id) => ({
      photo: photo(id),
      reason: 'duplicate',
      decision: null,
      group_anchor_photo_id: id,
      keep_possible: true,
    })),
    total,
    open_count: 0,
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
  vi.mocked(ausschussApi.listAusschuss).mockReset()
})

describe('useAusschussQuery', () => {
  it('liegt unter dem breiten Praefix des Projekts und laedt die erste Seite', async () => {
    // Derselbe `['photos', projectId, ...]`-Praefix wie Raster, Einzelbild und Gruppenabfrage:
    // Eine Entscheidung irgendwo invalidiert den Ausschuss-Bestand damit mit.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([42], 1))
    const { queryClient, wrapper } = sharedClient()

    const { result } = renderHook(() => useAusschussQuery(7, { enabled: true }), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(ausschussApi.listAusschuss).toHaveBeenCalledWith(7, {
      limit: AUSSCHUSS_PAGE_SIZE,
      offset: 0,
    })
    expect(queryClient.getQueryData(['photos', 7, 'ausschuss', 'liste'])).toEqual({
      pages: [stand([42], 1)],
      pageParams: [0],
    })
  })

  it('laedt die naechste Seite ueber die Zahl der bereits geladenen Eintraege', async () => {
    vi.mocked(ausschussApi.listAusschuss)
      .mockResolvedValueOnce(stand([42], 2))
      .mockResolvedValueOnce(stand([43], 2))
    const { wrapper } = sharedClient()

    const { result } = renderHook(() => useAusschussQuery(7, { enabled: true }), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    await result.current.fetchNextPage()

    expect(ausschussApi.listAusschuss).toHaveBeenLastCalledWith(7, {
      limit: AUSSCHUSS_PAGE_SIZE,
      offset: 1,
    })
  })

  it('fragt gar nicht, solange der Aufrufer es nicht freigibt', async () => {
    // Ohne erfolgreichen Erkennungslauf gibt es keinen Ausschuss-Bestand zu lesen.
    const { wrapper } = sharedClient()

    const { result } = renderHook(() => useAusschussQuery(7, { enabled: false }), { wrapper })

    expect(result.current.fetchStatus).toBe('idle')
    expect(ausschussApi.listAusschuss).not.toHaveBeenCalled()
  })
})

describe('useAusschussEntryQuery', () => {
  it('traegt die Foto-Id im Schluessel und liest genau diesen Eintrag', async () => {
    // Zwei Deep-Links auf zwei Aufnahmen teilten sich sonst einen Eintrag, und die zweite Ansicht
    // zeigte die erste Aufnahme.
    vi.mocked(ausschussApi.listAusschuss).mockResolvedValue(stand([42], 9))
    const { queryClient, wrapper } = sharedClient()

    const { result } = renderHook(() => useAusschussEntryQuery(7, 42), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(ausschussApi.listAusschuss).toHaveBeenCalledWith(7, {
      limit: AUSSCHUSS_PAGE_SIZE,
      offset: 0,
      photoId: 42,
    })
    expect(queryClient.getQueryData(['photos', 7, 'ausschuss', 'photo', 42])).toEqual(
      stand([42], 9),
    )
    expect(queryClient.getQueryData(['photos', 7, 'ausschuss', 'photo', 43])).toBeUndefined()
  })
})
