import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as opencloudApi from '../api/opencloud'
import { useOpenCloudFolderCountsQuery } from './useOpenCloudFolderCounts'

vi.mock('../api/opencloud')

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useOpenCloudFolderCountsQuery', () => {
  beforeEach(() => {
    vi.mocked(opencloudApi.fetchFolderCounts).mockReset()
  })

  it('fetches folder counts for the given path and keys the query by path', async () => {
    vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([
      { path: 'CostaRica/Sub', count: 42, at_limit: false, error: false },
    ])

    const { result } = renderHook(() => useOpenCloudFolderCountsQuery('CostaRica'), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(opencloudApi.fetchFolderCounts).toHaveBeenCalledWith('CostaRica')
    expect(result.current.data).toEqual([
      { path: 'CostaRica/Sub', count: 42, at_limit: false, error: false },
    ])
  })

  it('loads the root level for an empty path', async () => {
    vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([])

    const { result } = renderHook(() => useOpenCloudFolderCountsQuery(''), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(opencloudApi.fetchFolderCounts).toHaveBeenCalledWith('')
  })

  it('does not refetch counts for an already-loaded path (staleTime: Infinity, identisch zu useOpenCloudBrowseQuery)', async () => {
    vi.mocked(opencloudApi.fetchFolderCounts).mockResolvedValue([])
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const localWrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )

    const { rerender } = renderHook(
      ({ path }: { path: string }) => useOpenCloudFolderCountsQuery(path),
      { wrapper: localWrapper, initialProps: { path: 'CostaRica' } }
    )
    await waitFor(() => expect(opencloudApi.fetchFolderCounts).toHaveBeenCalledTimes(1))

    rerender({ path: 'CostaRica/Sub' })
    await waitFor(() => expect(opencloudApi.fetchFolderCounts).toHaveBeenCalledTimes(2))

    rerender({ path: 'CostaRica' })

    expect(opencloudApi.fetchFolderCounts).toHaveBeenCalledTimes(2)
  })

  it('surfaces a complete request failure (e.g. network error) as isError, not just a per-entry error flag', async () => {
    // Review-Fund (test-engineer): bisher nur getestet, dass ein EINZELNER Eintrag error:true
    // tragen kann - hier geht die gesamte Anfrage fehl (Netzwerkfehler o.ae.), nicht nur ein
    // Element der Antwortliste.
    vi.mocked(opencloudApi.fetchFolderCounts).mockRejectedValue(new Error('Netzwerkfehler'))

    const { result } = renderHook(() => useOpenCloudFolderCountsQuery('CostaRica'), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))

    expect(result.current.data).toBeUndefined()
  })
})
