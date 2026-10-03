import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import * as overviewApi from '../api/projectOverview'
import { clearToken, setToken } from '../auth/token'
import { overviewSeenQueryKey, useMarkOverviewSeen, useOverviewSeen } from './useOverviewSeen'

vi.mock('../api/projectOverview')

/** Ein unsigniertes JWT mit dem Nutzernamen im `username`-Claim - wie `decodeUsername` ihn liest. */
function tokenFor(username: string): string {
  const payload = btoa(JSON.stringify({ sub: '1', username }))
  return `header.${payload}.signature`
}

/** Bewusst OHNE Vorgaben: Der Test-Standard des Projekts setzt `retry: false` bereits - ein im
 * Hook vergessenes `retry: false` fiele damit nicht auf. */
function makeWrapper(queryClient = new QueryClient()) {
  return {
    queryClient,
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  }
}

afterEach(() => {
  clearToken()
  vi.mocked(overviewApi.getOverviewSeen).mockReset()
  vi.mocked(overviewApi.markOverviewSeen).mockReset()
})

describe('useOverviewSeen', () => {
  it('liest den Merker für das Projekt', async () => {
    setToken(tokenFor('daniel'))
    vi.mocked(overviewApi.getOverviewSeen).mockResolvedValue({ seen: false })
    const { wrapper } = makeWrapper()

    const { result } = renderHook(() => useOverviewSeen(7), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual({ seen: false })
    expect(overviewApi.getOverviewSeen).toHaveBeenCalledWith(7)
  })

  it('meldet einen Lesefehler sofort, mit genau einem Aufruf ohne Wiederholung', async () => {
    setToken(tokenFor('daniel'))
    vi.mocked(overviewApi.getOverviewSeen).mockRejectedValue(new Error('kaputt'))
    const { wrapper } = makeWrapper()

    const { result } = renderHook(() => useOverviewSeen(7), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(overviewApi.getOverviewSeen).toHaveBeenCalledTimes(1)
  })

  it('löst bei erneutem Rendern (Projekt-Poll) keinen zweiten Leseaufruf aus', async () => {
    setToken(tokenFor('daniel'))
    vi.mocked(overviewApi.getOverviewSeen).mockResolvedValue({ seen: true })
    const { wrapper } = makeWrapper()

    const { result, rerender } = renderHook(() => useOverviewSeen(7), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    rerender()
    rerender()
    const second = renderHook(() => useOverviewSeen(7), { wrapper })
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true))

    expect(overviewApi.getOverviewSeen).toHaveBeenCalledTimes(1)
  })

  it('trägt den Nutzernamen im Schlüssel - nach einem Personenwechsel kein fremder Cache', async () => {
    const { queryClient, wrapper } = makeWrapper()
    setToken(tokenFor('daniel'))
    vi.mocked(overviewApi.getOverviewSeen).mockResolvedValue({ seen: true })
    const first = renderHook(() => useOverviewSeen(7), { wrapper })
    await waitFor(() => expect(first.result.current.data).toEqual({ seen: true }))
    first.unmount()

    setToken(tokenFor('zweite'))
    vi.mocked(overviewApi.getOverviewSeen).mockResolvedValue({ seen: false })
    const second = renderHook(() => useOverviewSeen(7), { wrapper })

    expect(second.result.current.data).toBeUndefined()
    await waitFor(() => expect(second.result.current.data).toEqual({ seen: false }))
    expect(overviewApi.getOverviewSeen).toHaveBeenCalledTimes(2)
    expect(overviewSeenQueryKey(7)).toEqual(['overview-seen', 'zweite', 7])
    expect(queryClient.getQueryData(['overview-seen', 'daniel', 7])).toEqual({ seen: true })
  })
})

describe('useMarkOverviewSeen', () => {
  it('setzt den lokalen Wert sofort und merkt "gesehen" auf dem Server', async () => {
    setToken(tokenFor('daniel'))
    vi.mocked(overviewApi.markOverviewSeen).mockResolvedValue(undefined)
    const { queryClient, wrapper } = makeWrapper()

    const { result } = renderHook(() => useMarkOverviewSeen(7), { wrapper })
    act(() => result.current())

    expect(queryClient.getQueryData(overviewSeenQueryKey(7))).toEqual({ seen: true })
    expect(overviewApi.markOverviewSeen).toHaveBeenCalledWith(7)
  })

  it('schluckt einen Schreibfehler - der lokale Wert bleibt "gesehen"', async () => {
    setToken(tokenFor('daniel'))
    vi.mocked(overviewApi.markOverviewSeen).mockRejectedValue(new Error('kaputt'))
    const { queryClient, wrapper } = makeWrapper()

    const { result } = renderHook(() => useMarkOverviewSeen(7), { wrapper })
    act(() => result.current())
    await waitFor(() => expect(overviewApi.markOverviewSeen).toHaveBeenCalledTimes(1))
    await Promise.resolve()

    expect(queryClient.getQueryData(overviewSeenQueryKey(7))).toEqual({ seen: true })
  })
})
