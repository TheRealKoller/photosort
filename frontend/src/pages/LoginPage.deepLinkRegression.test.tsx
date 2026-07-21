import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getToken } from '../auth/token'
import { useUnauthorizedRedirect } from '../auth/useUnauthorizedRedirect'
import { LoginPage } from './LoginPage'

// Regressionstest fuer einen im Review gefundenen Bug: api/client.ts::apiFetch behandelte
// JEDEN 401 generisch (Token loeschen + globales photosort:unauthorized-Event), auch den 401
// von POST /auth/login selbst bei einem einfachen Tippfehler im Passwort. Der globale Listener
// (useUnauthorizedRedirect, genutzt von App.tsx) navigierte daraufhin zu /login mit
// state={reason:'expired'} und ueberschrieb dabei state.from des urspruenglichen Tiefenlinks -
// ein zweiter, korrekter Loginversuch landete dann faelschlich auf "/" statt am
// Tiefenlink-Ziel. Dieser Test nutzt bewusst die echte api/auth.ts + api/client.ts (nur
// globales fetch gemockt, siehe architecture/0002-testkonzept.md "an der Schnittstelle nach
// aussen mocken") UND den echten useUnauthorizedRedirect-Listener - NICHT vi.mock('../api/auth')
// wie LoginPage.test.tsx und NICHT isoliert ohne den globalen Listener wie ein erster,
// unzureichender Versuch dieses Tests - genau diese Kombination war die Luecke, durch die der
// Bug durchgerutscht ist.

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function ProjectStub() {
  return <p>Projekt 42</p>
}

function LoginRoute() {
  useUnauthorizedRedirect()
  return <LoginPage />
}

function renderWithDeepLinkState() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  return render(
    <MemoryRouter
      initialEntries={[{ pathname: '/login', state: { from: { pathname: '/projects/42' } } }]}
    >
      <Routes>
        <Route path="/projects/:id" element={<ProjectStub />} />
        <Route path="/login" element={<LoginRoute />} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
}

describe('LoginPage deep-link survives a failed login attempt', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('still redirects to the original deep-link target after one failed attempt', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'Ungültige Anmeldedaten' }))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: 'token-xyz', token_type: 'bearer' }))
    const user = userEvent.setup()

    renderWithDeepLinkState()

    await user.type(screen.getByLabelText(/benutzername/i), 'daniel')
    await user.type(screen.getByLabelText(/passwort/i), 'falsch')
    await user.click(screen.getByRole('button', { name: 'Anmelden' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ungültige Anmeldedaten')

    await user.type(screen.getByLabelText(/passwort/i), 'richtig')
    await user.click(screen.getByRole('button', { name: 'Anmelden' }))

    await waitFor(() => expect(screen.getByText('Projekt 42')).toBeInTheDocument())
    expect(getToken()).toBe('token-xyz')
  })
})
