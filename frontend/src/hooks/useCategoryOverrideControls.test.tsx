import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import * as photosApi from '../api/photos'
import { useCategoryOverrideControls } from './useCategoryOverrideControls'

vi.mock('../api/photos')

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useCategoryOverrideControls', () => {
  it('tracks the pending override key only for the photo it was triggered for', async () => {
    let resolveMutation: (() => void) | undefined
    vi.mocked(photosApi.setCategoryOverride).mockReturnValue(
      new Promise((resolve) => {
        resolveMutation = () => resolve({ photo_id: 1, category_key: 'hund' })
      })
    )

    const { result } = renderHook(() => useCategoryOverrideControls(1), { wrapper })

    act(() => {
      result.current.overrideCategory(1, 'hund')
    })

    expect(result.current.pendingOverrideKeyFor(1)).toBe('hund')
    expect(result.current.pendingOverrideKeyFor(2)).toBeNull()
    await waitFor(() => expect(photosApi.setCategoryOverride).toHaveBeenCalledWith(1, 'hund'))

    resolveMutation?.()
    await waitFor(() => expect(result.current.pendingOverrideKeyFor(1)).toBeNull())
  })

  it('tracks the resetting photo id only for the photo it was triggered for', async () => {
    let resolveMutation: (() => void) | undefined
    vi.mocked(photosApi.deleteCategoryOverride).mockReturnValue(
      new Promise((resolve) => {
        resolveMutation = () => resolve(undefined)
      })
    )

    const { result } = renderHook(() => useCategoryOverrideControls(1), { wrapper })

    act(() => {
      result.current.resetOverride(1)
    })

    expect(result.current.isResetPendingFor(1)).toBe(true)
    expect(result.current.isResetPendingFor(2)).toBe(false)
    await waitFor(() => expect(photosApi.deleteCategoryOverride).toHaveBeenCalledWith(1))

    resolveMutation?.()
    await waitFor(() => expect(result.current.isResetPendingFor(1)).toBe(false))
  })
})
