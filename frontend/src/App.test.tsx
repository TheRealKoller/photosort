import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { apiFetch } from './api/client'
import { getToken, setToken } from './auth/token'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function makeToken(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.sig`
}

function renderApp(initialEntries: string[] = ['/']) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <App />
    </MemoryRouter>,
    { wrapper }
  )
}

describe('App', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('redirects to /login when no token is present', () => {
    renderApp(['/'])

    expect(screen.getByLabelText(/benutzername/i)).toBeInTheDocument()
  })

  it('shows the app shell with the username derived from the token when authenticated', () => {
    setToken(makeToken({ sub: '1', username: 'daniel' }))

    renderApp(['/'])

    expect(screen.getByText('PhotoSort')).toBeInTheDocument()
    expect(screen.getByText(/angemeldet als daniel/i)).toBeInTheDocument()
  })

  it('logs out without a backend call: clears the token and navigates to /login', async () => {
    setToken(makeToken({ sub: '1', username: 'daniel' }))
    const user = userEvent.setup()

    renderApp(['/'])

    await user.click(screen.getByRole('button', { name: /abmelden/i }))

    expect(getToken()).toBeNull()
    expect(screen.getByLabelText(/benutzername/i)).toBeInTheDocument()
  })

  it('navigates to /login with an expired-session hint when a real API call returns 401 mid-session', async () => {
    // Deckt den in architecture/0002-testkonzept.md geforderten Testfall "401 mitten in
    // laufender Session" ab: statt das Event manuell zu dispatchen, wird ein zweiter,
    // tatsaechlicher apiFetch-Aufruf simuliert (gueltiges Token beim Laden, die Anfrage selbst
    // liefert wegen zwischenzeitlichem Ablauf 401) - apiFetch loescht das Token und feuert das
    // Event dabei selbst, als echter Seiteneffekt, nicht als Testkonstruktion.
    setToken(makeToken({ sub: '1', username: 'daniel' }))
    vi.stubGlobal('fetch', vi.fn())
    vi.mocked(fetch).mockResolvedValue(jsonResponse(401, { detail: 'Nicht authentifiziert.' }))

    renderApp(['/'])
    expect(screen.getByText('PhotoSort')).toBeInTheDocument()

    await expect(apiFetch('/projects')).rejects.toBeInstanceOf(Error)

    await waitFor(() => expect(screen.getByLabelText(/benutzername/i)).toBeInTheDocument())
    expect(screen.getByText(/sitzung abgelaufen/i)).toBeInTheDocument()
    expect(getToken()).toBeNull()
  })
})
