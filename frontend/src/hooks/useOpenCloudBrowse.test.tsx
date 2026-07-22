import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import * as opencloudApi from '../api/opencloud'
import { useOpenCloudBrowseQuery } from './useOpenCloudBrowse'

vi.mock('../api/opencloud')

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useOpenCloudBrowseQuery', () => {
  it('fetches entries for the given path and keys the query by path', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([{ name: 'Sub', path: 'CostaRica/Sub' }])

    const { result } = renderHook(() => useOpenCloudBrowseQuery('CostaRica'), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(opencloudApi.browseFolder).toHaveBeenCalledWith('CostaRica')
    expect(result.current.data).toEqual([{ name: 'Sub', path: 'CostaRica/Sub' }])
  })

  it('loads the root level for an empty path', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([])

    const { result } = renderHook(() => useOpenCloudBrowseQuery(''), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(opencloudApi.browseFolder).toHaveBeenCalledWith('')
  })
})
