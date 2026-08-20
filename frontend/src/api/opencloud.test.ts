import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import { browseFolder, fetchFolderCounts } from './opencloud'
import type { BrowseEntry, FolderCountOut } from './types'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

const ENTRIES: BrowseEntry[] = [{ name: 'Sub', path: 'CostaRica/Sub' }]
const COUNTS: FolderCountOut[] = [
  { path: 'CostaRica/Sub', count: 42, at_limit: false, error: false },
]

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

  it('fetches folder counts for the root level when called without a path', async () => {
    vi.mocked(apiFetch).mockResolvedValue(COUNTS)

    const result = await fetchFolderCounts('')

    expect(apiFetch).toHaveBeenCalledWith('/opencloud/folder-counts')
    expect(result).toEqual(COUNTS)
  })

  it('passes the path as a query parameter for folder counts', async () => {
    vi.mocked(apiFetch).mockResolvedValue(COUNTS)

    await fetchFolderCounts('CostaRica')

    expect(apiFetch).toHaveBeenCalledWith('/opencloud/folder-counts?path=CostaRica')
  })

  it('URL-encodes path segments for folder counts', async () => {
    vi.mocked(apiFetch).mockResolvedValue([])

    await fetchFolderCounts('Costa Rica/Sub Folder')

    expect(apiFetch).toHaveBeenCalledWith(
      '/opencloud/folder-counts?path=Costa%20Rica%2FSub%20Folder'
    )
  })
})
