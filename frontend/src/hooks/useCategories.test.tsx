import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as categoriesApi from '../api/categories'
import { CATEGORY_SET } from '../test/categorySetFixture'
import { useCategoriesQuery } from './useCategories'

vi.mock('../api/categories')

// specs/features/0289-feste-kategorien.md, Teststrategie Abschnitt 9: Nachweis fuer den
// "langlebigen Cache" aus dem UI/UX-Abschnitt - `vi.mock` auf Modulebene plus Aufrufzaehler.
// Der QueryClient wird hier bewusst PRO TEST einmal erzeugt und an alle Konsumenten desselben
// Tests weitergereicht: nur so ist "ein zweiter Konsument loest keinen zweiten Request aus"
// ueberhaupt beobachtbar - ein Wrapper, der bei jedem Render einen neuen Client baut, wuerde die
// Aussage still unterlaufen.
function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  function wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
  return wrapper
}

describe('useCategoriesQuery', () => {
  beforeEach(() => {
    vi.mocked(categoriesApi.listCategories).mockReset()
    vi.mocked(categoriesApi.listCategories).mockResolvedValue(CATEGORY_SET)
  })

  it('loads the fixed category set in the order the server delivered it', async () => {
    const { result } = renderHook(() => useCategoriesQuery(), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(categoriesApi.listCategories).toHaveBeenCalledTimes(1)
    // Reihenfolge unveraendert uebernommen, nicht neu sortiert.
    expect(result.current.data?.map((entry) => entry.key)).toEqual(
      CATEGORY_SET.map((entry) => entry.key)
    )
  })

  it('serves a second consumer from the cache without a second request', async () => {
    const wrapper = makeWrapper()
    const first = renderHook(() => useCategoriesQuery(), { wrapper })
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true))

    const second = renderHook(() => useCategoriesQuery(), { wrapper })
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true))

    expect(categoriesApi.listCategories).toHaveBeenCalledTimes(1)
    expect(second.result.current.data).toEqual(CATEGORY_SET)
  })

  it('does not refetch a consumer that mounts again later (staleTime: Infinity)', async () => {
    const wrapper = makeWrapper()
    const first = renderHook(() => useCategoriesQuery(), { wrapper })
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true))
    first.unmount()

    const second = renderHook(() => useCategoriesQuery(), { wrapper })
    // Der Cache-Eintrag ueberlebt das Unmount (`gcTime: Infinity`) und gilt nicht als veraltet -
    // der zweite Konsument hat die Daten deshalb ohne Ladezustand sofort.
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true))

    expect(categoriesApi.listCategories).toHaveBeenCalledTimes(1)
  })

  it('reports the error state when the set cannot be loaded', async () => {
    vi.mocked(categoriesApi.listCategories).mockRejectedValue(new Error('offline'))

    const { result } = renderHook(() => useCategoriesQuery(), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.data).toBeUndefined()
  })
})
