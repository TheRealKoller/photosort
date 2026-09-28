import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as personsApi from '../api/persons'
import type { FaceAssignmentOut } from '../api/types'
import { personGroupQueryKey, useFaceAssignment } from './useFaceAssignment'
import { PERSONS_QUERY_KEY } from './usePersons'

vi.mock('../api/persons')

const RESULT: FaceAssignmentOut = {
  person: { id: 7, name: 'Anna', reference_count: 20 },
  learned: false,
  // Absichtlich anders als ein naives Anhängen: Die zweite Person war vorher schon da.
  photo_persons: [
    { person_id: 7, origin: 'corrected', face: 'assigned' },
    { person_id: 8, origin: 'recognized', face: null },
  ],
}

function setup(refreshGroup: boolean) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(['photos', 3, 'list'], {
    pages: [{ items: [{ id: 5, persons: [] }], total: 1 }],
  })
  const groupFetch = vi.fn(() => Promise.resolve({ pages: [] }))
  queryClient.setQueryData(PERSONS_QUERY_KEY, [])
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  const view = renderHook(() => useFaceAssignment(3, { refreshGroup }), { wrapper })
  return { ...view, queryClient, groupFetch }
}

beforeEach(() => {
  vi.mocked(personsApi.addReference).mockReset().mockResolvedValue(RESULT)
  vi.mocked(personsApi.createPerson).mockReset().mockResolvedValue(RESULT)
})

describe('useFaceAssignment', () => {
  it('schreibt photo_persons der Antwort unverändert in die Foto-Caches und reicht learned durch', async () => {
    const { result, queryClient } = setup(false)

    let answer: FaceAssignmentOut | undefined
    await act(async () => {
      answer = await result.current.mutateAsync({
        choice: { kind: 'reference', personId: 7 },
        photoId: 5,
        faceIndex: 1,
      })
    })

    expect(personsApi.addReference).toHaveBeenCalledWith(7, 5, 1)
    expect(answer?.learned).toBe(false)
    expect(queryClient.getQueryData(['photos', 3, 'list'])).toEqual({
      pages: [{ items: [{ id: 5, persons: RESULT.photo_persons }], total: 1 }],
    })
    expect(queryClient.getQueryState(PERSONS_QUERY_KEY)?.isInvalidated).toBe(true)
  })

  it('lädt in der Übersicht zusätzlich die Gruppe der Person neu', async () => {
    const { result, queryClient } = setup(true)
    const refetch = vi.spyOn(queryClient, 'refetchQueries')

    await act(async () => {
      await result.current.mutateAsync({
        choice: { kind: 'create', name: 'Anna' },
        photoId: 5,
        faceIndex: 0,
      })
    })

    expect(personsApi.createPerson).toHaveBeenCalledWith('Anna', 5, 0)
    expect(refetch).toHaveBeenCalledWith({ queryKey: personGroupQueryKey(3, 7) })
  })
})
