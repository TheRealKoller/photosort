import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as photosApi from '../api/photos'
import { useMotifCorrectionControls } from './useMotifCorrection'

vi.mock('../api/photos')

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

// specs/features/0427-motive-mit-staerke.md, UI/UX-Abschnitt: "Laufende Korrektur -> nur die
// Schaltflaechen DIESER ZEILE disabled + busy, die uebrige Liste bleibt bedienbar". Der Nachweis
// laeuft ueber `pendingMotifKeyFor(photoId)`, nicht ueber den globalen `isPending` der Mutation:
// eine Seite rendert potenziell Dutzende Kacheln, und EIN Mutation-Paar je Seite ist Absicht.
describe('useMotifCorrectionControls', () => {
  it('tracks the pending motif key only for the photo it was triggered for', async () => {
    let resolveMutation: (() => void) | undefined
    vi.mocked(photosApi.setMotifCorrection).mockReturnValue(
      new Promise((resolve) => {
        resolveMutation = () => resolve({ photo_id: 1, motif_key: 'menschen', applies: true })
      }),
    )

    const { result } = renderHook(() => useMotifCorrectionControls(1), { wrapper })

    act(() => {
      result.current.correctMotif(1, 'menschen', true)
    })

    expect(result.current.pendingMotifKeyFor(1)).toBe('menschen')
    expect(result.current.pendingMotifKeyFor(2)).toBeNull()
    await waitFor(() =>
      expect(photosApi.setMotifCorrection).toHaveBeenCalledWith(1, 'menschen', true),
    )

    resolveMutation?.()
    await waitFor(() => expect(result.current.pendingMotifKeyFor(1)).toBeNull())
  })

  it('passes a rejecting correction through unchanged', async () => {
    vi.mocked(photosApi.setMotifCorrection).mockResolvedValue({
      photo_id: 4,
      motif_key: 'tiere',
      applies: false,
    })

    const { result } = renderHook(() => useMotifCorrectionControls(1), { wrapper })

    act(() => {
      result.current.correctMotif(4, 'tiere', false)
    })

    await waitFor(() =>
      expect(photosApi.setMotifCorrection).toHaveBeenCalledWith(4, 'tiere', false),
    )
  })

  it('tracks the pending key of a withdrawal as well', async () => {
    let resolveMutation: (() => void) | undefined
    vi.mocked(photosApi.deleteMotifCorrection).mockReturnValue(
      new Promise((resolve) => {
        resolveMutation = () => resolve(undefined)
      }),
    )

    const { result } = renderHook(() => useMotifCorrectionControls(1), { wrapper })

    act(() => {
      result.current.withdrawCorrection(1, 'menschen')
    })

    expect(result.current.pendingMotifKeyFor(1)).toBe('menschen')
    await waitFor(() => expect(photosApi.deleteMotifCorrection).toHaveBeenCalledWith(1, 'menschen'))

    resolveMutation?.()
    await waitFor(() => expect(result.current.pendingMotifKeyFor(1)).toBeNull())
  })

  it('reports the backend detail of a failed correction together with the motif key', async () => {
    // Der `detail` des Backends wird WOERTLICH weitergereicht - die Meldung unter der Liste zeigt
    // ihn als Textknoten, nicht umformuliert. Der Motivschluessel gehoert dazu, sonst sagt die
    // Meldung nicht, WELCHE Zeile fehlgeschlagen ist.
    vi.mocked(photosApi.setMotifCorrection).mockRejectedValue(
      new ApiError(409, 'Die Korrektur dieses Motivs wurde gerade veraendert.'),
    )

    const { result } = renderHook(() => useMotifCorrectionControls(1), { wrapper })

    act(() => {
      result.current.correctMotif(1, 'menschen', true)
    })

    await waitFor(() => expect(result.current.error).not.toBeNull())
    expect(result.current.error?.motifKey).toBe('menschen')
    expect(result.current.error?.detail).toBe(
      'Die Korrektur dieses Motivs wurde gerade veraendert.',
    )
  })

  it('falls back to a generic detail for a failure without one', async () => {
    vi.mocked(photosApi.setMotifCorrection).mockRejectedValue(new Error('offline'))

    const { result } = renderHook(() => useMotifCorrectionControls(1), { wrapper })

    act(() => {
      result.current.correctMotif(1, 'menschen', true)
    })

    await waitFor(() => expect(result.current.error).not.toBeNull())
    expect(result.current.error?.detail).not.toBe('')
  })

  it('clears the error when the next correction succeeds', async () => {
    vi.mocked(photosApi.setMotifCorrection).mockRejectedValueOnce(new Error('kaputt'))
    vi.mocked(photosApi.setMotifCorrection).mockResolvedValue({
      photo_id: 1,
      motif_key: 'tiere',
      applies: true,
    })

    const { result } = renderHook(() => useMotifCorrectionControls(1), { wrapper })

    act(() => {
      result.current.correctMotif(1, 'menschen', true)
    })
    await waitFor(() => expect(result.current.error).not.toBeNull())

    act(() => {
      result.current.correctMotif(1, 'tiere', true)
    })

    await waitFor(() => expect(result.current.error).toBeNull())
  })
})
