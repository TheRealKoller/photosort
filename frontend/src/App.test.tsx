import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import App from './App'
import { UNAUTHORIZED_EVENT } from './api/client'
import { clearToken, getToken, setToken } from './auth/token'

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

  it('navigates to /login with an expired-session hint on a global unauthorized event', async () => {
    setToken(makeToken({ sub: '1', username: 'daniel' }))

    renderApp(['/'])
    expect(screen.getByText('PhotoSort')).toBeInTheDocument()

    // Spiegelt das reale Verhalten von api/client.ts::apiFetch bei 401: Token wird geloescht,
    // BEVOR das Event gefeuert wird - sonst wuerde LoginPages eigener
    // "bereits angemeldet"-Redirect (siehe LoginPage.tsx) hier faelschlich zurueck navigieren.
    clearToken()
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))

    await waitFor(() => expect(screen.getByLabelText(/benutzername/i)).toBeInTheDocument())
    expect(screen.getByText(/sitzung abgelaufen/i)).toBeInTheDocument()
  })
})
