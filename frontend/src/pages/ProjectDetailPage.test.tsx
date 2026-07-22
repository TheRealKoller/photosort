import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as projectsApi from '../api/projects'
import type { ProjectOut, ScanSummary } from '../api/types'
import { ProjectDetailPage } from './ProjectDetailPage'

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

function scan(overrides: Partial<ScanSummary> = {}): ScanSummary {
  return {
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    files_found: 0,
    photos_added: 0,
    photos_updated: 0,
    photos_removed: 0,
    files_skipped: 0,
    error_message: null,
    ...overrides,
  }
}

function renderPage(initialPath = '/projects/1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return {
    ...render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/" element={<p>Projektliste-Seite</p>} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        </Routes>
      </MemoryRouter>,
      { wrapper }
    ),
    queryClient,
  }
}

describe('ProjectDetailPage', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.getProject).mockReset()
    vi.mocked(projectsApi.triggerScan).mockReset()
  })

  it('shows a dedicated not-found state on a 404 instead of a broken page', async () => {
    vi.mocked(projectsApi.getProject).mockRejectedValue(new ApiError(404, 'Projekt nicht gefunden.'))

    renderPage()

    expect(await screen.findByText(/projekt nicht gefunden/i)).toBeInTheDocument()
  })

  it('shows project data and an active "Aktualisieren" button when never scanned', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scan: null }))

    renderPage()

    expect(await screen.findByText('Costa Rica')).toBeInTheDocument()
    expect(screen.getByText('CostaRica')).toBeInTheDocument()
    expect(screen.getByText(/noch nicht gescannt/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /aktualisieren/i })).toBeEnabled()
  })

  it('disables the button synchronously on click, before the response arrives', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scan: null }))
    let resolveTrigger: (value: { status: string }) => void = () => {}
    vi.mocked(projectsApi.triggerScan).mockReturnValue(
      new Promise((resolve) => {
        resolveTrigger = resolve
      })
    )
    const user = userEvent.setup()

    renderPage()
    const button = await screen.findByRole('button', { name: /aktualisieren/i })
    await user.click(button)

    expect(button).toBeDisabled()
    resolveTrigger({ status: 'queued' })
  })

  it('sends exactly one scan request on a rapid double click before the first response arrives', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scan: null }))
    vi.mocked(projectsApi.triggerScan).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()

    renderPage()
    const button = await screen.findByRole('button', { name: /aktualisieren/i })
    await user.click(button)
    await user.click(button)

    expect(projectsApi.triggerScan).toHaveBeenCalledTimes(1)
  })

  it('re-enables the button and shows an error when the trigger request itself fails', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scan: null }))
    vi.mocked(projectsApi.triggerScan).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    const user = userEvent.setup()

    renderPage()
    const button = await screen.findByRole('button', { name: /aktualisieren/i })
    await user.click(button)

    await waitFor(() => expect(button).toBeEnabled())
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('polls while running and stops exactly at the first success response, showing all counters', { timeout: 10000 }, async () => {
    vi.mocked(projectsApi.getProject)
      .mockResolvedValueOnce(project({ last_scan: null }))
      .mockResolvedValueOnce(project({ last_scan: scan({ status: 'running' }) }))
      .mockResolvedValue(
        project({
          last_scan: scan({
            status: 'success',
            finished_at: '2026-07-20T10:05:00Z',
            files_found: 12,
            photos_added: 10,
            photos_updated: 1,
            photos_removed: 0,
            files_skipped: 2,
          }),
        })
      )
    vi.mocked(projectsApi.triggerScan).mockResolvedValue({ status: 'queued' })
    const user = userEvent.setup()

    renderPage()
    const button = await screen.findByRole('button', { name: /aktualisieren/i })
    await user.click(button)

    await waitFor(() => expect(screen.getByRole('button', { name: /scan läuft/i })).toBeDisabled())

    await waitFor(() => expect(screen.getByText('10')).toBeInTheDocument(), { timeout: 8000 })
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /aktualisieren/i })).toBeEnabled()
  })

  it(
    'keeps the button disabled after a successful trigger response for a re-scan, until polling actually confirms "running"',
    { timeout: 10000 },
    async () => {
      // Regression fuer einen im Review gefundenen Bug: fuer ein Projekt, das schon einmal
      // gescannt wurde, ist last_scan VOR dem Klick bereits nicht-null (z.B. "failed" vom
      // vorherigen Lauf). Der Worker setzt status="running" erst asynchron
      // (backend/src/photosort/worker.py), nicht synchron mit der 202-Antwort - der
      // Invalidierungs-Refetch direkt nach dem Trigger kann also noch den ALTEN Status liefern.
      // Der Button darf trotzdem nicht vorzeitig wieder aktiv werden (specs/features/0005:
      // "bleibt es, bis entweder Polling running bestaetigt oder der Trigger selbst fehlschlaegt").
      const previousScan = scan({ status: 'failed', error_message: 'vorher fehlgeschlagen' })
      vi.mocked(projectsApi.getProject)
        .mockResolvedValueOnce(project({ last_scan: previousScan }))
        .mockResolvedValueOnce(project({ last_scan: previousScan }))
        .mockResolvedValue(project({ last_scan: scan({ status: 'running' }) }))
      vi.mocked(projectsApi.triggerScan).mockResolvedValue({ status: 'queued' })
      const user = userEvent.setup()

      renderPage()
      const button = await screen.findByRole('button', { name: /aktualisieren/i })
      await user.click(button)

      await waitFor(() => expect(projectsApi.getProject).toHaveBeenCalledTimes(2))
      // Der zweite (invalidierte) Fetch liefert noch immer "failed" - der Button muss trotzdem
      // deaktiviert bleiben, statt sich faelschlich zu reaktivieren.
      expect(screen.getByRole('button', { name: /scan läuft/i })).toBeDisabled()

      await waitFor(
        () => expect(screen.getByRole('button', { name: /scan läuft/i })).toBeDisabled(),
        { timeout: 8000 }
      )
      await waitFor(
        () =>
          expect(vi.mocked(projectsApi.getProject).mock.calls.length).toBeGreaterThanOrEqual(3),
        { timeout: 8000 }
      )
    }
  )

  it('shows the error message on a failed scan and re-enables the button immediately', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({
        last_scan: scan({
          status: 'failed',
          finished_at: '2026-07-20T10:01:00Z',
          error_message: 'OpenCloud nicht erreichbar',
        }),
      })
    )

    renderPage()

    expect(await screen.findByText('OpenCloud nicht erreichbar')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /aktualisieren/i })).toBeEnabled()
  })

  it('has a back link to the project list even in the generic (non-404) error state', async () => {
    vi.mocked(projectsApi.getProject).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    renderPage()

    await screen.findByRole('alert')
    expect(screen.getByRole('link', { name: /zurück/i })).toHaveAttribute('href', '/')
  })

  it('has a back link to the project list', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderPage()

    await screen.findByText('Costa Rica')
    expect(screen.getByRole('link', { name: /zurück/i })).toHaveAttribute('href', '/')
  })

  it('stops fetching after unmount while polling is active (no leaked interval)', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({ last_scan: scan({ status: 'running' }) })
    )

    const { unmount } = renderPage()
    await screen.findByText('Costa Rica')
    const callsBeforeUnmount = vi.mocked(projectsApi.getProject).mock.calls.length

    unmount()
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(vi.mocked(projectsApi.getProject).mock.calls.length).toBe(callsBeforeUnmount)
  })
})
