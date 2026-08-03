import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getToken, setToken } from '../auth/token'
import * as authApi from '../api/auth'
import { LoginPage } from './LoginPage'

vi.mock('../api/auth')

function HomeStub() {
  return <p>Startseite</p>
}

function ProjectStub() {
  return <p>Projekt 42</p>
}

function renderLoginPage(initialEntries: Array<string | { pathname: string; state?: unknown }>) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )

  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/" element={<HomeStub />} />
        <Route path="/projects/:id" element={<ProjectStub />} />
        <Route path="/login" element={<LoginPage />} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.mocked(authApi.login).mockReset()
  })

  it('renders the login form with an autofocused username field', () => {
    renderLoginPage(['/login'])

    const usernameInput = screen.getByLabelText(/benutzername/i)
    expect(usernameInput).toHaveFocus()
    expect(screen.getByLabelText(/passwort/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Anmelden' })).toBeEnabled()
  })

  it('navigates to state.from after a successful login (deep-link case)', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: 'token-xyz',
      token_type: 'bearer',
    })
    const user = userEvent.setup()

    renderLoginPage([
      { pathname: '/login', state: { from: { pathname: '/projects/42' } } },
    ])

    await user.type(screen.getByLabelText(/benutzername/i), 'daniel')
    await user.type(screen.getByLabelText(/passwort/i), 'geheim')
    await user.click(screen.getByRole('button', { name: 'Anmelden' }))

    await waitFor(() => expect(screen.getByText('Projekt 42')).toBeInTheDocument())
    expect(getToken()).toBe('token-xyz')
  })

  it('navigates to / after a successful login without a deep-link target', async () => {
    vi.mocked(authApi.login).mockResolvedValue({
      access_token: 'token-xyz',
      token_type: 'bearer',
    })
    const user = userEvent.setup()

    renderLoginPage(['/login'])

    await user.type(screen.getByLabelText(/benutzername/i), 'daniel')
    await user.type(screen.getByLabelText(/passwort/i), 'geheim')
    await user.click(screen.getByRole('button', { name: 'Anmelden' }))

    await waitFor(() => expect(screen.getByText('Startseite')).toBeInTheDocument())
  })

  it('shows the backend detail message on failed login without storing a token', async () => {
    const { ApiError } = await import('../api/client')
    vi.mocked(authApi.login).mockRejectedValue(new ApiError(401, 'Ungültige Anmeldedaten'))
    const user = userEvent.setup()

    renderLoginPage(['/login'])

    await user.type(screen.getByLabelText(/benutzername/i), 'daniel')
    await user.type(screen.getByLabelText(/passwort/i), 'falsch')
    await user.click(screen.getByRole('button', { name: 'Anmelden' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Ungültige Anmeldedaten')
    expect(getToken()).toBeNull()
    expect(screen.queryByText('Startseite')).not.toBeInTheDocument()
    expect(screen.getByLabelText(/passwort/i)).toHaveValue('')
    expect(screen.getByLabelText(/benutzername/i)).toHaveValue('daniel')
  })

  it('shows the busy-button pattern while the login request is pending', async () => {
    let resolveLogin: (value: authApi.TokenResponse) => void = () => {}
    vi.mocked(authApi.login).mockReturnValue(
      new Promise((resolve) => {
        resolveLogin = resolve
      })
    )
    const user = userEvent.setup()

    renderLoginPage(['/login'])

    await user.type(screen.getByLabelText(/benutzername/i), 'daniel')
    await user.type(screen.getByLabelText(/passwort/i), 'geheim')
    await user.click(screen.getByRole('button', { name: 'Anmelden' }))

    expect(screen.getByRole('button', { name: 'Anmelden…' })).toBeDisabled()
    expect(screen.getByLabelText(/benutzername/i)).toBeDisabled()
    expect(screen.getByLabelText(/passwort/i)).toBeDisabled()

    resolveLogin({ access_token: 'token-xyz', token_type: 'bearer' })
    await waitFor(() => expect(screen.getByText('Startseite')).toBeInTheDocument())
  })

  it('redirects immediately without rendering the form when a token already exists', () => {
    setToken('already-valid-token')

    renderLoginPage(['/login'])

    expect(screen.getByText('Startseite')).toBeInTheDocument()
    expect(screen.queryByLabelText(/benutzername/i)).not.toBeInTheDocument()
  })

  // Funktionaler Fix 3 (specs/features/0012-visual-redesign.md): autocomplete-Attribute fuer
  // Passwortmanager/Browser-Autofill. War bereits vor dieser Spec im Code vorhanden, aber bisher
  // ohne Regressionstest - siehe Teststrategie-Abschnitt der Spec (explizit gefordert).
  it('sets the standard autocomplete values on the credential fields', () => {
    renderLoginPage(['/login'])

    expect(screen.getByLabelText(/benutzername/i)).toHaveAttribute('autocomplete', 'username')
    expect(screen.getByLabelText(/passwort/i)).toHaveAttribute('autocomplete', 'current-password')
  })

  it('shows a neutral session-expired hint when navigated with state.reason "expired"', () => {
    renderLoginPage([{ pathname: '/login', state: { reason: 'expired' } }])

    expect(screen.getByText(/sitzung abgelaufen/i)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
