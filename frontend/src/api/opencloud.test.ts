import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import { browseFolder } from './opencloud'
import type { BrowseEntry } from './types'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

const ENTRIES: BrowseEntry[] = [{ name: 'Sub', path: 'CostaRica/Sub' }]

describe('api/opencloud', () => {
  it('fetches the root level when called without a path', async () => {
    vi.mocked(apiFetch).mockResolvedValue(ENTRIES)

    const result = await browseFolder('')

    expect(apiFetch).toHaveBeenCalledWith('/opencloud/browse')
    expect(result).toEqual(ENTRIES)
  })

  it('passes the path as a query parameter', async () => {
    vi.mocked(apiFetch).mockResolvedValue(ENTRIES)

    await browseFolder('CostaRica')

    expect(apiFetch).toHaveBeenCalledWith('/opencloud/browse?path=CostaRica')
  })

  it('URL-encodes path segments', async () => {
    vi.mocked(apiFetch).mockResolvedValue([])

    await browseFolder('Costa Rica/Sub Folder')

    expect(apiFetch).toHaveBeenCalledWith(
      '/opencloud/browse?path=Costa%20Rica%2FSub%20Folder'
    )
  })
})
