import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as projectsApi from '../api/projects'
import { ApiError } from '../api/client'
import type { ProjectOut } from '../api/types'
import { ProjectListPage } from './ProjectListPage'

vi.mock('../api/projects')

function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 1,
    name: 'Costa Rica',
    opencloud_drive_id: 'drive-1',
    opencloud_path: 'CostaRica',
    created_at: '2026-07-20T10:00:00Z',
    last_scan: null,
    ...overrides,
  }
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<ProjectListPage />} />
        <Route path="/projects/new" element={<p>Neues Projekt Seite</p>} />
        <Route path="/projects/:id" element={<p>Projekt-Detail-Seite</p>} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
}

describe('ProjectListPage', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.listProjects).mockReset()
  })

  it('shows a loading state distinct from the empty state while fetching', () => {
    vi.mocked(projectsApi.listProjects).mockReturnValue(new Promise(() => {}))

    renderPage()

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByText(/noch keine projekte/i)).not.toBeInTheDocument()
  })

  it('shows an error banner with a retry option distinct from the empty state on failure', async () => {
    vi.mocked(projectsApi.listProjects).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
    expect(screen.getByRole('button', { name: /erneut versuchen/i })).toBeInTheDocument()
    expect(screen.queryByText(/noch keine projekte/i)).not.toBeInTheDocument()
  })

  it('retries the fetch when "Erneut versuchen" is clicked', async () => {
    vi.mocked(projectsApi.listProjects)
      .mockRejectedValueOnce(new ApiError(500, 'Serverfehler'))
      .mockResolvedValueOnce([project()])
    const user = userEvent.setup()

    renderPage()

    await screen.findByRole('alert')
    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

    expect(await screen.findByText('Costa Rica')).toBeInTheDocument()
  })

  it('shows a hint and a link to /projects/new when there are no projects', async () => {
    vi.mocked(projectsApi.listProjects).mockResolvedValue([])

    renderPage()

    expect(await screen.findByText(/noch keine projekte/i)).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /neues projekt/i }).length).toBeGreaterThan(0)
  })

  it('always shows a link to /projects/new even with a non-empty list', async () => {
    vi.mocked(projectsApi.listProjects).mockResolvedValue([project()])

    renderPage()

    await screen.findByText('Costa Rica')
    expect(screen.getAllByRole('link', { name: /neues projekt/i }).length).toBeGreaterThan(0)
  })

  it('renders name, opencloud_path and a distinguishable status for each of the four scan states', async () => {
    vi.mocked(projectsApi.listProjects).mockResolvedValue([
      project({ id: 1, name: 'Never scanned', last_scan: null }),
      project({
        id: 2,
        name: 'Running',
        last_scan: {
          status: 'running',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: null,
          files_found: 0,
          photos_added: 0,
          photos_updated: 0,
          photos_removed: 0,
          files_skipped: 0,
          error_message: null,
        },
      }),
      project({
        id: 3,
        name: 'Succeeded',
        last_scan: {
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          files_found: 10,
          photos_added: 10,
          photos_updated: 0,
          photos_removed: 0,
          files_skipped: 0,
          error_message: null,
        },
      }),
      project({
        id: 4,
        name: 'Failed',
        last_scan: {
          status: 'failed',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:01:00Z',
          files_found: 0,
          photos_added: 0,
          photos_updated: 0,
          photos_removed: 0,
          files_skipped: 0,
          error_message: 'OpenCloud nicht erreichbar',
        },
      }),
    ])

    renderPage()

    await screen.findByText('Never scanned')
    const statuses = screen.getAllByTestId(/project-status-/)
    const labels = statuses.map((el) => el.textContent)
    expect(new Set(labels).size).toBe(4)
  })

  it('links each card to its project detail page', async () => {
    vi.mocked(projectsApi.listProjects).mockResolvedValue([project()])
    const user = userEvent.setup()

    renderPage()

    await user.click(await screen.findByRole('link', { name: /costa rica/i }))

    expect(await screen.findByText('Projekt-Detail-Seite')).toBeInTheDocument()
  })
})
