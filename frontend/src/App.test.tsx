import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'
import { apiFetch } from './api/client'
import * as photosApi from './api/photos'
import * as projectsApi from './api/projects'
import type { ProjectOut } from './api/types'
import { getToken, setToken } from './auth/token'

vi.mock('./api/projects')
vi.mock('./api/photos')

function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 1,
    name: 'Costa Rica',
    opencloud_drive_id: 'drive-1',
    opencloud_path: 'CostaRica',
    created_at: '2026-07-20T10:00:00Z',
    last_scan: null,
    last_scoring_run: null,
    last_criterion_scoring_run: null,
    category_selection_enabled: true,
    ...overrides,
  }
}

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
    vi.mocked(projectsApi.listProjects).mockReset()
    vi.mocked(projectsApi.listProjects).mockResolvedValue([])
    vi.mocked(projectsApi.getProject).mockReset()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })
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

  it('routes /projects/:id/photos to the photo grid within the app shell', async () => {
    setToken(makeToken({ sub: '1', username: 'daniel' }))

    renderApp(['/projects/1/photos'])

    expect(screen.getByText('PhotoSort')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Fotos' })).toBeInTheDocument()
  })

  it('routes /projects/:id/compare to the comparison view within the app shell', async () => {
    setToken(makeToken({ sub: '1', username: 'daniel' }))

    renderApp(['/projects/1/compare'])

    expect(screen.getByText('PhotoSort')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Vergleich' })).toBeInTheDocument()
  })
})

// specs/features/0033-sticky-titelleiste-projekt-link.md (AK2-AK4, AK8): der Header rendert auf
// den vier Projekt-Routen genau einen zusaetzlichen Link mit zugaenglichem Namen "Projekt", der
// immer auf /projects/{projectId} zeigt - unabhaengig von Subpfad/Query-Parametern.
describe('App - Header-Link "Projekt"', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.mocked(projectsApi.listProjects).mockReset()
    vi.mocked(projectsApi.listProjects).mockResolvedValue([])
    vi.mocked(projectsApi.getProject).mockReset()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    vi.mocked(photosApi.listPhotos).mockReset()
    vi.mocked(photosApi.listPhotos).mockResolvedValue({ items: [], total: 0 })
    setToken(makeToken({ sub: '1', username: 'daniel' }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  const PROJECT_ROUTES = [
    '/projects/1',
    '/projects/1/photos',
    '/projects/1/photos/42',
    '/projects/1/compare',
  ]

  it.each(PROJECT_ROUTES)(
    'renders a "Projekt" link targeting /projects/1 on %s (AK2/AK4)',
    async (path) => {
      renderApp([path])

      expect(screen.getByText('PhotoSort')).toBeInTheDocument()

      const link = await screen.findByRole('link', { name: 'Projekt' })
      expect(link).toHaveAttribute('href', '/projects/1')
    }
  )

  it('shows exactly one "Projekt" link on a project route (AK2)', async () => {
    renderApp(['/projects/1/photos'])

    const links = await screen.findAllByRole('link', { name: 'Projekt' })
    expect(links).toHaveLength(1)
  })

  it('does not render a "Projekt" link on / (AK3)', async () => {
    renderApp(['/'])

    expect(screen.getByText('PhotoSort')).toBeInTheDocument()
    // Wartet auf ein garantiert vorhandenes Element der Zielseite, bevor die
    // Abwesenheits-Assertion greift - sonst koennte der Link nur deshalb fehlen, weil die Seite
    // noch nicht fertig gerendert ist.
    await waitFor(() => expect(projectsApi.listProjects).toHaveBeenCalled())
    expect(screen.queryByRole('link', { name: 'Projekt' })).not.toBeInTheDocument()
  })

  it('does not render a "Projekt" link on /projects/new (AK3)', async () => {
    renderApp(['/projects/new'])

    expect(await screen.findByRole('heading', { name: /neues projekt/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Projekt' })).not.toBeInTheDocument()
  })

  it('does not render a "Projekt" link on /login (AK3)', () => {
    window.localStorage.clear()
    renderApp(['/login'])

    expect(screen.getByLabelText(/benutzername/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Projekt' })).not.toBeInTheDocument()
  })

  it('targets /projects/{projectId} unaffected by query parameters (AK4, edge case)', async () => {
    renderApp(['/projects/1/photos?filter=favorite'])

    const link = await screen.findByRole('link', { name: 'Projekt' })
    expect(link).toHaveAttribute('href', '/projects/1')
  })

  it('accepts a non-numeric projectId without client-side validation (AK4, edge case)', async () => {
    renderApp(['/projects/abc/photos'])

    const link = await screen.findByRole('link', { name: 'Projekt' })
    expect(link).toHaveAttribute('href', '/projects/abc')
  })

  it('targets /projects/1 from the nested photo detail route (AK4, edge case)', async () => {
    renderApp(['/projects/1/photos/42'])

    const link = await screen.findByRole('link', { name: 'Projekt' })
    expect(link).toHaveAttribute('href', '/projects/1')
  })

  it('self-links on the project detail page itself, without hiding/disabling it (AK8)', async () => {
    renderApp(['/projects/1'])

    const link = await screen.findByRole('link', { name: 'Projekt' })
    expect(link).toHaveAttribute('href', '/projects/1')
    expect(link).not.toHaveAttribute('aria-disabled')
  })

  it('redirects an unknown path to / without ever mounting the app shell with stale project context (edge case)', async () => {
    renderApp(['/some/unknown/path'])

    expect(await screen.findByText('PhotoSort')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Projekt' })).not.toBeInTheDocument()
  })

  it('has an accessible native link, keyboard-focusable without extra effort (AK6)', async () => {
    renderApp(['/projects/1/photos'])

    const link = await screen.findByRole('link', { name: 'Projekt' })
    expect(link.tagName).toBe('A')
    link.focus()
    expect(link).toHaveFocus()
  })
})
