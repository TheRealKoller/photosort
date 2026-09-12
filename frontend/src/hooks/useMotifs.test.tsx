import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as motifsApi from '../api/motifs'
import { MOTIF_SET } from '../test/motifSetFixture'
import { useMotifsQuery } from './useMotifs'

vi.mock('../api/motifs')

// specs/features/0427-motive-mit-staerke.md, UI/UX-Abschnitt: "ein Request fuer alle
// Konsumenten". Der QueryClient wird PRO TEST einmal erzeugt und an alle Konsumenten desselben
// Tests weitergereicht - nur so ist "ein zweiter Konsument loest keinen zweiten Request aus"
// ueberhaupt beobachtbar; ein Wrapper, der bei jedem Render einen neuen Client baut, wuerde die
// Aussage still unterlaufen. Muster wie useCategories.test.tsx.
function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return wrapper
}

describe('useMotifsQuery', () => {
  beforeEach(() => {
    vi.mocked(motifsApi.listMotifs).mockReset()
    vi.mocked(motifsApi.listMotifs).mockResolvedValue(MOTIF_SET)
  })

  it('loads the fixed motif set in the order the server delivered it', async () => {
    const { result } = renderHook(() => useMotifsQuery(), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(motifsApi.listMotifs).toHaveBeenCalledTimes(1)
    expect(result.current.data?.items.map((item) => item.key)).toEqual(
      MOTIF_SET.items.map((item) => item.key),
    )
  })

  it('serves a second consumer from the cache without a second request', async () => {
    const wrapper = makeWrapper()
    const first = renderHook(() => useMotifsQuery(), { wrapper })
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true))

    const second = renderHook(() => useMotifsQuery(), { wrapper })
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true))

    expect(motifsApi.listMotifs).toHaveBeenCalledTimes(1)
    expect(second.result.current.data).toEqual(MOTIF_SET)
  })

  it('does not refetch a consumer that mounts again later (staleTime: Infinity)', async () => {
    const wrapper = makeWrapper()
    const first = renderHook(() => useMotifsQuery(), { wrapper })
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true))
    first.unmount()

    const second = renderHook(() => useMotifsQuery(), { wrapper })
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true))

    expect(motifsApi.listMotifs).toHaveBeenCalledTimes(1)
  })

  it('reports the error state when the set cannot be loaded', async () => {
    vi.mocked(motifsApi.listMotifs).mockRejectedValue(new Error('offline'))

    const { result } = renderHook(() => useMotifsQuery(), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })

  it('does not share its cache entry with the category set', async () => {
    // Ein gemeinsamer `queryKey` liesse die eine Antwort als die andere gelten - und beide Listen
    // haben dieselbe Form aus Schluessel und Anzeigename.
    const wrapper = makeWrapper()
    const { result } = renderHook(() => useMotifsQuery(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.items).toHaveLength(MOTIF_SET.items.length)
  })
})
