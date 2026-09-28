import {
  focusManager,
  onlineManager,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as personsApi from '../api/persons'
import type { UnnamedFacesPageOut } from '../api/types'
import { useUnnamedFaces } from './useUnnamedFaces'

vi.mock('../api/persons')

/*
 * Muster 0002 "Antworten im Flug": Jede Auflistungsanfrage bleibt offen, bis der Test sie von Hand
 * auflöst oder scheitern lässt - keine Zeitgeber. So sind Seite und Einzelabfrage in jeder
 * Reihenfolge nachstellbar.
 */
interface Call {
  afterId: number
  maxPhotos: number | undefined
  resolve: (page: UnnamedFacesPageOut) => void
  reject: (error: unknown) => void
}

let calls: Call[] = []

function page(
  faces: [number, number][],
  next: number | null,
  done: number,
  total: number,
  notReady: number[] = [],
): UnnamedFacesPageOut {
  return {
    faces: faces.map(([photoId, index]) => ({
      photo_id: photoId,
      face_index: index,
      crop_jpeg: `c${photoId}-${index}`,
    })),
    not_ready_photo_ids: notReady,
    next_after_id: next,
    photos_done: done,
    photos_total: total,
  }
}

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  const view = renderHook(() => useUnnamedFaces(3), { wrapper })
  return { ...view, queryClient }
}

function keys(faces: readonly { photo_id: number; face_index: number }[]): string[] {
  return faces.map((face) => `${face.photo_id}-${face.face_index}`)
}

/** Lässt Antworten und Folgeeffekte durchlaufen. TanStack meldet Änderungen gebündelt über eine
 * Makroaufgabe; drei Runden decken Antwort, Benachrichtigung und Folgeanfrage ab. Das sind keine
 * gesteuerten Zeitgeber - Antworten löst weiterhin nur der Test aus. */
async function settle() {
  for (let round = 0; round < 3; round += 1) {
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
  }
}

/** Die offene Anfrage mit genau diesem Stand; der Test scheitert, wenn es sie nicht gibt. */
function pending(afterId: number, maxPhotos?: number): Call {
  const call = calls.find((entry) => entry.afterId === afterId && entry.maxPhotos === maxPhotos)
  if (call === undefined) {
    throw new Error(`keine Anfrage after_id=${afterId} max_photos=${maxPhotos}`)
  }
  calls = calls.filter((entry) => entry !== call)
  return call
}

async function answer(call: Call, result: UnnamedFacesPageOut | Error) {
  if (result instanceof Error) {
    call.reject(result)
  } else {
    call.resolve(result)
  }
  await settle()
}

/** Erste Seite bis Foto 10 geladen, die zweite (ab 10) ist unterwegs. */
async function firstPageLoaded(
  faces: [number, number][] = [
    [3, 0],
    [5, 0],
    [5, 1],
    [8, 0],
  ],
) {
  const view = setup()
  await waitFor(() => expect(calls).toHaveLength(1))
  await answer(pending(0), page(faces, 10, 10, 30))
  await waitFor(() => expect(calls.some((call) => call.afterId === 10)).toBe(true))
  return view
}

beforeEach(() => {
  calls = []
  vi.mocked(personsApi.listUnnamedFaces).mockImplementation(
    (_projectId, afterId, maxPhotos) =>
      new Promise((resolve, reject) => {
        calls.push({ afterId, maxPhotos, resolve, reject })
      }),
  )
})

afterEach(() => {
  vi.mocked(personsApi.listUnnamedFaces).mockReset()
})

describe('useUnnamedFaces - Nachladen und Fortschritt', () => {
  it('lädt die nächste Seite selbsttätig, bis next_after_id fehlt', async () => {
    const { result } = await firstPageLoaded()
    expect(result.current.status).toBe('running')
    expect(result.current.progress).toEqual({ done: 10, total: 30 })

    await answer(pending(10), page([[12, 0]], null, 30, 30))
    await settle()

    expect(calls).toEqual([])
    expect(keys(result.current.faces)).toEqual(['3-0', '5-0', '5-1', '8-0', '12-0'])
    expect(result.current.status).toBe('complete')
  })

  it('stoppt bei einem Fehler und setzt mit dem after_id der gescheiterten Seite fort', async () => {
    const { result } = await firstPageLoaded()

    await answer(pending(10), new ApiError(500, 'kaputt'))
    await settle()

    expect(calls).toEqual([])
    expect(result.current.status).toBe('interrupted')
    expect(result.current.error?.message).toBe('kaputt')
    // Die gefundenen Gesichter bleiben stehen.
    expect(keys(result.current.faces)).toEqual(['3-0', '5-0', '5-1', '8-0'])

    act(() => result.current.retry())
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].afterId).toBe(10)
    expect(calls[0].maxPhotos).toBeUndefined()
  })

  it('nimmt aus einer Einzelabfrage weder Fortschritt noch Cursor', async () => {
    const { result } = await firstPageLoaded()

    act(() => result.current.refreshPhoto(5, 'b.jpg'))
    await answer(pending(4, 1), page([[5, 0]], 5, 2, 31))

    expect(result.current.progress).toEqual({ done: 10, total: 30 })
    // Die laufende Seite ab 10 ist die einzige weitere Anfrage - der Cursor sprang nicht auf 5.
    expect(calls.map((call) => call.afterId)).toEqual([10])
  })

  it('meldet ein Projekt ohne Fotos als eigenen Zustand', async () => {
    const { result } = setup()
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(result.current.status).toBe('initial')

    await answer(pending(0), page([], null, 0, 0))

    expect(result.current.status).toBe('empty')
  })
})

describe('useUnnamedFaces - removeFace', () => {
  it('entfernt ein Gesicht ohne Anfrage', async () => {
    const { result } = await firstPageLoaded()

    act(() => result.current.removeFace(5, 0))

    expect(keys(result.current.faces)).toEqual(['3-0', '5-1', '8-0'])
    expect(calls.map((call) => call.afterId)).toEqual([10])
  })

  it('wirkt auf eine Seite, die vor dem Entfernen gestartet ist', async () => {
    const { result } = await firstPageLoaded()

    act(() => result.current.removeFace(12, 0))

    await answer(
      pending(10),
      page(
        [
          [12, 0],
          [12, 1],
        ],
        null,
        30,
        30,
      ),
    )

    expect(keys(result.current.faces)).toEqual(['3-0', '5-0', '5-1', '8-0', '12-1'])
  })

  it('wirkt auf eine Einzelabfrage, die vor dem Entfernen gestartet ist', async () => {
    const { result } = await firstPageLoaded()

    act(() => result.current.refreshPhoto(5, 'b.jpg'))
    act(() => result.current.removeFace(5, 0))
    await answer(
      pending(4, 1),
      page(
        [
          [5, 0],
          [5, 1],
        ],
        5,
        2,
        30,
      ),
    )

    expect(keys(result.current.faces)).toEqual(['3-0', '5-1', '8-0'])
  })

  it('setzt ein Gesicht wieder ein, wenn die Einzelabfrage nach dem Entfernen startet', async () => {
    const { result } = await firstPageLoaded()

    act(() => result.current.removeFace(5, 0))
    act(() => result.current.refreshPhoto(5, 'b.jpg'))
    await answer(
      pending(4, 1),
      page(
        [
          [5, 0],
          [5, 1],
        ],
        5,
        2,
        30,
      ),
    )

    expect(keys(result.current.faces)).toEqual(['3-0', '5-0', '5-1', '8-0'])
  })
})

describe('useUnnamedFaces - refreshPhoto', () => {
  it('ersetzt alle Gesichter des Fotos an ihrer Stelle zwischen den Nachbarfotos', async () => {
    const { result } = await firstPageLoaded()

    act(() => result.current.refreshPhoto(5, 'b.jpg'))
    await answer(
      pending(4, 1),
      page(
        [
          [5, 0],
          [5, 1],
          [5, 2],
        ],
        5,
        2,
        30,
      ),
    )

    expect(keys(result.current.faces)).toEqual(['3-0', '5-0', '5-1', '5-2', '8-0'])
  })

  it('lässt die Gesichter entfallen, wenn die Antwort keine trägt', async () => {
    const { result } = await firstPageLoaded()

    act(() => result.current.refreshPhoto(5, 'b.jpg'))
    await answer(pending(4, 1), page([], 5, 2, 30))

    expect(keys(result.current.faces)).toEqual(['3-0', '8-0'])
  })

  it('zählt ein nicht bereites Foto einmal, auch wenn es zweimal gemeldet wird', async () => {
    const view = setup()
    await waitFor(() => expect(calls).toHaveLength(1))
    await answer(pending(0), page([[3, 0]], 10, 10, 30, [9]))
    const { result } = view

    act(() => result.current.refreshPhoto(9, 'i.jpg'))
    await answer(pending(8, 1), page([], 9, 9, 30, [9]))
    act(() => result.current.refreshPhoto(7, 'g.jpg'))
    await answer(pending(6, 1), page([], 7, 7, 30, [7]))

    expect(result.current.notReadyCount).toBe(2)
  })

  it('fügt die Gesichter eines anderen gelieferten Fotos nicht ein', async () => {
    const { result } = await firstPageLoaded()

    // Foto 5 ist inzwischen gelöscht, die Einzelabfrage liefert das nächste Foto.
    act(() => result.current.refreshPhoto(5, 'b.jpg'))
    await answer(pending(4, 1), page([[6, 0]], 6, 3, 29))

    expect(keys(result.current.faces)).toEqual(['3-0', '8-0'])
  })

  it('fragt ein Foto jenseits des Cursors nicht ab', async () => {
    const { result } = await firstPageLoaded()
    await answer(pending(10), new ApiError(500, 'kaputt'))
    await settle()

    act(() => result.current.refreshPhoto(20, 'u.jpg'))
    await settle()

    expect(calls).toEqual([])
  })

  it('merkt den Aufruf bei einer Seite im Flug vor und fragt nach deren Ankunft ab', async () => {
    const { result } = await firstPageLoaded()

    act(() => result.current.refreshPhoto(12, 'm.jpg'))
    await settle()
    expect(calls.map((call) => call.afterId)).toEqual([10])

    // Der Server hat Foto 12 vor dem Commit der Rücknahme bearbeitet - ohne das Gesicht.
    await answer(pending(10), page([[14, 0]], 20, 20, 30))
    await waitFor(() => expect(calls.some((call) => call.maxPhotos === 1)).toBe(true))
    await answer(pending(11, 1), page([[12, 0]], 12, 12, 30))

    expect(keys(result.current.faces)).toEqual(['3-0', '5-0', '5-1', '8-0', '12-0', '14-0'])
  })

  it('fragt nach einer gescheiterten Seite im Flug nicht ab', async () => {
    const { result } = await firstPageLoaded()

    act(() => result.current.refreshPhoto(12, 'm.jpg'))
    await answer(pending(10), new ApiError(500, 'kaputt'))
    await settle()

    expect(calls).toEqual([])
  })
})

describe('useUnnamedFaces - refreshFailures', () => {
  it('führt je Foto höchstens einen Eintrag und entfernt ihn nach gelungener Wiederholung', async () => {
    const { result } = await firstPageLoaded()

    act(() => result.current.refreshPhoto(5, 'b.jpg'))
    await answer(pending(4, 1), new ApiError(500, 'weg'))
    act(() => result.current.refreshPhoto(5, 'b.jpg'))
    await answer(pending(4, 1), new ApiError(500, 'weg'))

    expect(result.current.refreshFailures).toEqual([{ photoId: 5, fileName: 'b.jpg' }])
    // Seiten und Cursor bleiben unberührt.
    expect(keys(result.current.faces)).toEqual(['3-0', '5-0', '5-1', '8-0'])
    expect(result.current.progress).toEqual({ done: 10, total: 30 })
    expect(calls.map((call) => call.afterId)).toEqual([10])

    act(() => result.current.retryRefresh(5))
    await answer(pending(4, 1), page([[5, 1]], 5, 2, 30))

    expect(result.current.refreshFailures).toEqual([])
    expect(keys(result.current.faces)).toEqual(['3-0', '5-1', '8-0'])
  })

  it('führt den Eintrag ohne Dateinamen, wenn der Aufrufer keinen kennt', async () => {
    const { result } = await firstPageLoaded()

    act(() => result.current.refreshPhoto(5, null))
    await answer(pending(4, 1), new ApiError(500, 'weg'))

    expect(result.current.refreshFailures).toEqual([{ photoId: 5, fileName: null }])
  })
})

describe('useUnnamedFaces - Cache', () => {
  it('fragt nach einer breiten Invalidierung der Fotolisten nicht neu an', async () => {
    const { queryClient } = await firstPageLoaded()

    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: ['photos', 3] })
    })

    expect(calls.map((call) => call.afterId)).toEqual([10])
  })

  it('fragt bei Fokus und Reconnect nicht neu an', async () => {
    await firstPageLoaded()

    act(() => {
      focusManager.setFocused(false)
      focusManager.setFocused(true)
      onlineManager.setOnline(false)
      onlineManager.setOnline(true)
    })
    await settle()

    expect(calls.map((call) => call.afterId)).toEqual([10])
    focusManager.setFocused(undefined)
  })

  it('beginnt nach Aus- und erneutem Einhängen bei after_id 0', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
    const first = renderHook(() => useUnnamedFaces(3), { wrapper })
    await waitFor(() => expect(calls).toHaveLength(1))
    await answer(pending(0), page([[3, 0]], null, 5, 5))
    first.unmount()
    await settle()

    renderHook(() => useUnnamedFaces(3), { wrapper })

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].afterId).toBe(0)
  })
})
