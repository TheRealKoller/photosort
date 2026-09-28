import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as photosApi from '../api/photos'
import type { PhotoOut, PhotoPersonOut } from '../api/types'
import { storePhotoPersons } from './usePhotoPersons'
import { PERSON_GROUP_PAGE_SIZE, usePersonGroupQuery } from './usePersonGroupQuery'

vi.mock('../api/photos')

const ANNA = 7

function photo(id: number, persons: PhotoPersonOut[]): PhotoOut {
  return { id, relative_path: `${id}.jpg`, persons } as unknown as PhotoOut
}

/** Ein Server-Stub, der wie der echte Endpunkt filtert: Ein Foto ohne den Namen fällt heraus, und
 * alle späteren rücken vor - ein falscher Offset überspringt dann wirklich ein Foto. */
function server(total: number) {
  const named = new Set(Array.from({ length: total }, (_, index) => index + 1))
  vi.mocked(photosApi.listPhotos).mockImplementation((_projectId, params = {}) => {
    const ids = [...named].sort((a, b) => a - b)
    const offset = params.offset ?? 0
    const slice = ids.slice(offset, offset + (params.limit ?? 60))
    return Promise.resolve({
      items: slice.map((id) => photo(id, [{ person_id: ANNA, origin: 'recognized', face: null }])),
      total: ids.length,
    })
  })
  return named
}

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  const view = renderHook(() => usePersonGroupQuery(3, ANNA), { wrapper })
  return { ...view, queryClient }
}

function removeName(queryClient: QueryClient, named: Set<number>, id: number) {
  named.delete(id)
  storePhotoPersons(queryClient, 3, id, [])
}

beforeEach(() => {
  vi.mocked(photosApi.listPhotos).mockReset()
})

describe('usePersonGroupQuery', () => {
  it('fragt mit Seitengröße 24, nur dieser Person und ohne Bewertungsfilter', async () => {
    server(3)
    const { result } = setup()

    await waitFor(() => expect(result.current.count).toBe(3))
    expect(photosApi.listPhotos).toHaveBeenCalledWith(3, {
      limit: PERSON_GROUP_PAGE_SIZE,
      offset: 0,
      personIds: [ANNA],
    })
  })

  it('zählt nach zwei entfernten Namen 28 und lädt ab Offset 22 genau die übrigen 6', async () => {
    const named = server(30)
    const { result, queryClient } = setup()
    await waitFor(() => expect(result.current.photos).toHaveLength(24))

    act(() => {
      removeName(queryClient, named, 3)
      removeName(queryClient, named, 10)
    })
    await waitFor(() => expect(result.current.count).toBe(28))
    expect(result.current.hasNextPage).toBe(true)

    await act(async () => {
      await result.current.fetchNextPage()
    })

    expect(photosApi.listPhotos).toHaveBeenLastCalledWith(3, {
      limit: PERSON_GROUP_PAGE_SIZE,
      offset: 22,
      personIds: [ANNA],
    })
    await waitFor(() => expect(result.current.photos).toHaveLength(28))
    const ids = result.current.photos.map((entry) => entry.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(result.current.count).toBe(28)
    expect(result.current.hasNextPage).toBe(false)
  })

  it('senkt die Anzahl nach dem letzten Nachladen und bietet keine weitere Seite an', async () => {
    const named = server(5)
    const { result, queryClient } = setup()
    await waitFor(() => expect(result.current.count).toBe(5))

    act(() => removeName(queryClient, named, 2))

    await waitFor(() => expect(result.current.count).toBe(4))
    expect(result.current.hasNextPage).toBe(false)
  })
})
