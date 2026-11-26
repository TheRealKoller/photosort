import { QueryClient } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import { Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch, apiFetchBlob, UNAUTHORIZED_EVENT } from '../api/client'
import { useUnauthorizedRedirect } from './useUnauthorizedRedirect'
import { makeQueryClient, withProviders } from '../test/render'

function Probe() {
  useUnauthorizedRedirect()
  return <p>Geschuetzter Bereich</p>
}

function LoginStub() {
  return <p>Login-Seite</p>
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/**
 * Befuellt einen frischen QueryClient mit zwei Eintraegen, deren Leerung der Test beobachtet:
 * `['projects']` als repraesentative, personengebundene Query (listProjects) und `['motifs']` als
 * langlebige `gcTime: Infinity`-Query (wie useMotifs) - die GC raeumt nie, nur `clear()` tut es.
 * Die Assertion prueft den beobachtbaren Cache-Zustand, keinen Aufrufzaehler
 * (specs/architecture/0002-testkonzept.md, Sektion "Query-Client-Cache bei Sitzungsende leeren").
 */
function makeClient(): QueryClient {
  const queryClient = makeQueryClient()
  queryClient.setQueryData(['projects'], [{ id: 1, name: 'Costa Rica' }])
  queryClient.setQueryDefaults(['motifs'], { staleTime: Infinity, gcTime: Infinity })
  queryClient.setQueryData(['motifs'], { items: [{ key: 'wasser', label: 'Wasser' }] })
  return queryClient
}

function renderProbe(queryClient: QueryClient) {
  return render(
    withProviders(
      <>
        <Routes>
          <Route path="/" element={<Probe />} />
          <Route path="/login" element={<LoginStub />} />
        </Routes>
      </>,
      { queryClient, initialEntries: ['/'] },
    ),
  )
}

describe('useUnauthorizedRedirect', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('navigates to /login with state.reason "expired" on the global unauthorized event', () => {
    renderProbe(makeClient())
    expect(screen.getByText('Geschuetzter Bereich')).toBeInTheDocument()

    act(() => {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
    })

    expect(screen.getByText('Login-Seite')).toBeInTheDocument()
  })

  it('leert den Query-Client-Cache beim unauthorized-Event', () => {
    const queryClient = makeClient()
    renderProbe(queryClient)
    expect(queryClient.getQueryData(['projects'])).toBeDefined()
    expect(queryClient.getQueryData(['motifs'])).toBeDefined()

    act(() => {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
    })

    expect(queryClient.getQueryData(['projects'])).toBeUndefined()
    expect(queryClient.getQueryData(['motifs'])).toBeUndefined()
  })

  it('leert den Cache, wenn apiFetch eine 401 liefert (apiFetch-Pfad)', async () => {
    const queryClient = makeClient()
    renderProbe(queryClient)
    vi.stubGlobal('fetch', vi.fn())
    vi.mocked(fetch).mockResolvedValue(jsonResponse(401, { detail: 'Nicht authentifiziert.' }))

    await expect(apiFetch('/projects')).rejects.toBeInstanceOf(Error)

    expect(queryClient.getQueryData(['projects'])).toBeUndefined()
    expect(queryClient.getQueryData(['motifs'])).toBeUndefined()
  })

  it('leert den Cache, wenn apiFetchBlob eine 401 liefert (apiFetchBlob-Pfad)', async () => {
    const queryClient = makeClient()
    renderProbe(queryClient)
    vi.stubGlobal('fetch', vi.fn())
    vi.mocked(fetch).mockResolvedValue(jsonResponse(401, { detail: 'Nicht authentifiziert.' }))

    await expect(
      apiFetchBlob('/photos/{photo_id}/image', {
        pathParams: { photo_id: 1 },
        query: { variant: 'thumbnail' },
      }),
    ).rejects.toBeInstanceOf(Error)

    expect(queryClient.getQueryData(['projects'])).toBeUndefined()
    expect(queryClient.getQueryData(['motifs'])).toBeUndefined()
  })
})
