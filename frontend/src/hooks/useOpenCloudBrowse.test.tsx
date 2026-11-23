import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import * as opencloudApi from '../api/opencloud'
import { useOpenCloudBrowseQuery } from './useOpenCloudBrowse'
import { FreshQueryWrapper as wrapper } from '../test/render'

vi.mock('../api/opencloud')

describe('useOpenCloudBrowseQuery', () => {
  it('fetches entries for the given path and keys the query by path', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([
      { name: 'Sub', path: 'CostaRica/Sub', modified_at: null },
    ])

    const { result } = renderHook(() => useOpenCloudBrowseQuery('CostaRica'), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(opencloudApi.browseFolder).toHaveBeenCalledWith('CostaRica')
    expect(result.current.data).toEqual([{ name: 'Sub', path: 'CostaRica/Sub', modified_at: null }])
  })

  it('loads the root level for an empty path', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([])

    const { result } = renderHook(() => useOpenCloudBrowseQuery(''), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(opencloudApi.browseFolder).toHaveBeenCalledWith('')
  })
})
