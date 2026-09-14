import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as duplicatesApi from '../api/duplicates'
import type { DuplicateGroupOut } from '../api/types'
import {
  useDuplicateDecisionMutation,
  useDuplicateGroupDecisionMutation,
  useDuplicateGroupQuery,
} from './useDuplicates'

vi.mock('../api/duplicates')

const GROUP: DuplicateGroupOut = { items: [], position: 1, total: 2 }

function sharedClient() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, wrapper }
}

beforeEach(() => {
  vi.mocked(duplicatesApi.getDuplicateGroup).mockReset()
  vi.mocked(duplicatesApi.setDuplicateDecision).mockReset()
  vi.mocked(duplicatesApi.setDuplicateGroupDecision).mockReset()
})

describe('useDuplicateGroupQuery', () => {
  it('liegt unter dem breiten photos-Praefix des Projekts, mit dem Foto im Schluessel', async () => {
    // Der Praefix ist keine Bequemlichkeit: Eine Bewertung, die anderswo geschrieben wird,
    // invalidiert die Gruppe damit mit. Das Foto gehoert in den Schluessel, weil zwei Gruppen
    // desselben Projekts sonst denselben Eintrag teilten.
    vi.mocked(duplicatesApi.getDuplicateGroup).mockResolvedValue(GROUP)
    const { queryClient, wrapper } = sharedClient()

    const { result } = renderHook(() => useDuplicateGroupQuery(7, 42), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(queryClient.getQueryData(['photos', 7, 'duplicates', 42])).toEqual(GROUP)
  })
})

describe('useDuplicateDecisionMutation', () => {
  it('schreibt die Antwort fort und invalidiert die Fotoliste des Projekts', async () => {
    // Ohne die Invalidierung zeigte die Ausschuss-Liste die entschiedenen Aufnahmen weiter, und
    // die Zahl am Gate bliebe stehen - kein Rendering-Test saehe das.
    const written: DuplicateGroupOut = { items: [], position: 1, total: 1 }
    vi.mocked(duplicatesApi.setDuplicateDecision).mockResolvedValue(written)
    const { queryClient, wrapper } = sharedClient()
    queryClient.setQueryData(['photos', 7, 'duplicates', 42], GROUP)
    queryClient.setQueryData(['photos', 7, 'suggested'], { items: [], total: 3 })
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useDuplicateDecisionMutation(7, 42), { wrapper })
    result.current.mutate({ photoId: 43, decision: 'discard' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(duplicatesApi.setDuplicateDecision).toHaveBeenCalledWith(7, 43, 'discard')
    expect(queryClient.getQueryData(['photos', 7, 'duplicates', 42])).toEqual(written)
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['photos', 7] })
  })

  it('entscheidet ueber das UEBERGEBENE Foto, nicht ueber den Anker der Gruppe', async () => {
    // Der Anker steht im Schluessel, das entschiedene Foto in der Mutation - ein verwechselter
    // Wert schriebe die Entscheidung auf ein anderes Bild derselben Gruppe.
    vi.mocked(duplicatesApi.setDuplicateDecision).mockResolvedValue(GROUP)
    const { wrapper } = sharedClient()

    const { result } = renderHook(() => useDuplicateDecisionMutation(7, 42), { wrapper })
    result.current.mutate({ photoId: 99, decision: 'keep' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(duplicatesApi.setDuplicateDecision).toHaveBeenCalledWith(7, 99, 'keep')
  })
})

describe('useDuplicateGroupDecisionMutation', () => {
  it('loest GENAU EINEN Aufruf aus, unabhaengig von der Mitgliederzahl', async () => {
    // AK9: Die Abkuerzung setzt alle Mitglieder in EINEM Aufruf; die Menge bestimmt der Server.
    // Eine Schleife ueber die Kacheln saehe im Ergebnis gleich aus und waere ein Massen-Schreibweg
    // mit n Transaktionen.
    vi.mocked(duplicatesApi.setDuplicateGroupDecision).mockResolvedValue(GROUP)
    const { queryClient, wrapper } = sharedClient()
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useDuplicateGroupDecisionMutation(7, 42), { wrapper })
    result.current.mutate('keep')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(duplicatesApi.setDuplicateGroupDecision).toHaveBeenCalledTimes(1)
    expect(duplicatesApi.setDuplicateGroupDecision).toHaveBeenCalledWith(7, 42, 'keep')
    expect(queryClient.getQueryData(['photos', 7, 'duplicates', 42])).toEqual(GROUP)
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['photos', 7] })
  })
})
