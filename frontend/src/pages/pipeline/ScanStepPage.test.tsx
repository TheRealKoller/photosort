import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as projectsApi from '../../api/projects'
import type { ProjectOut, ScanSummary } from '../../api/types'
import type { PipelineOutletContext } from './ProjectPipelineLayout'
import { ScanStepPage } from './ScanStepPage'

vi.mock('../../api/projects')

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
    cloud_landmark_detection_enabled: false,
    cloud_landmark_consent_at: null,
    ...overrides,
  }
}

function scan(overrides: Partial<ScanSummary> = {}): ScanSummary {
  return {
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    files_found: 0,
    total_files: null,
    photos_added: 0,
    photos_updated: 0,
    photos_removed: 0,
    files_skipped: 0,
    error_message: null,
    ...overrides,
  }
}

// Wiederverwendetes Test-Muster fuer alle fuenf *StepPage.test.tsx-Dateien (Testkonzept, Abschnitt
// "Mehrschritt-Routing", Punkt 5): stellt den PipelineOutletContext bereit, den die echte
// ProjectPipelineLayout ueber <Outlet context={...}/> liefern wuerde, ohne die volle Layout-
// Guard-/Ladelogik erneut mitzurendern.
function OutletHost({ project: contextProject, refetchProject }: PipelineOutletContext) {
  return <Outlet context={{ project: contextProject, refetchProject } satisfies PipelineOutletContext} />
}

function renderPage(initialProject: ProjectOut, refetchProject = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return {
    ...render(
      <MemoryRouter initialEntries={['/x']}>
        <Routes>
          <Route element={<OutletHost project={initialProject} refetchProject={refetchProject} />}>
            <Route path="/x" element={<ScanStepPage />} />
          </Route>
        </Routes>
      </MemoryRouter>,
      { wrapper }
    ),
    refetchProject,
  }
}

describe('ScanStepPage', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.triggerScan).mockReset()
  })

  it('shows a short explanation line (UI/UX-Abschnitt der Spec 0042)', () => {
    renderPage(project({ last_scan: null }))

    expect(screen.getByText(/durchsucht den verknüpften opencloud-ordner/i)).toBeInTheDocument()
  })

  it('shows an active button and a hint when never scanned', () => {
    renderPage(project({ last_scan: null }))

    expect(screen.getByRole('button', { name: /aktualisieren/i })).toBeEnabled()
    expect(screen.getByText(/noch nicht gescannt/i)).toBeInTheDocument()
  })

  it('disables the button synchronously on click and sends exactly one request on a double click', async () => {
    vi.mocked(projectsApi.triggerScan).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderPage(project({ last_scan: null }))

    const button = screen.getByRole('button', { name: /aktualisieren/i })
    await user.click(button)
    await user.click(button)

    expect(button).toBeDisabled()
    expect(projectsApi.triggerScan).toHaveBeenCalledTimes(1)
  })

  it('re-enables the button and shows an error when the trigger request itself fails', async () => {
    vi.mocked(projectsApi.triggerScan).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    const user = userEvent.setup()
    renderPage(project({ last_scan: null }))

    await user.click(screen.getByRole('button', { name: /aktualisieren/i }))

    await waitFor(() => expect(screen.getByRole('button', { name: /aktualisieren/i })).toBeEnabled())
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('shows "Dateien werden gezählt…" with an indeterminate progress bar during the enumeration phase', () => {
    renderPage(project({ last_scan: scan({ status: 'running', total_files: null, files_found: 5 }) }))

    expect(screen.getByText('Dateien werden gezählt…')).toBeInTheDocument()
    const progress = screen.getByRole('progressbar') as HTMLProgressElement
    expect(progress.hasAttribute('value')).toBe(false)
    expect(progress.hasAttribute('max')).toBe(false)
  })

  it('shows "X von Y Dateien verarbeitet" with a determinate progress bar during the processing phase', () => {
    renderPage(project({ last_scan: scan({ status: 'running', total_files: 12, files_found: 4 }) }))

    expect(screen.getByText('4 von 12 Dateien verarbeitet')).toBeInTheDocument()
    const progress = screen.getByRole('progressbar') as HTMLProgressElement
    expect(progress.max).toBe(12)
    expect(progress.value).toBe(4)
  })

  it('throttles the aria-live announcement to 10%-steps during the processing phase', () => {
    renderPage(project({ last_scan: scan({ status: 'running', total_files: 100, files_found: 34 }) }))

    const liveRegion = screen.getByText(/30% verarbeitet/i)
    expect(liveRegion).toHaveAttribute('aria-live', 'polite')
    expect(screen.queryByText(/34% verarbeitet/i)).not.toBeInTheDocument()
  })

  it(
    'shows an indeterminate progress bar instead of an invalid max=0 for an empty project ' +
      '(total_files === 0, already processing phase, not enumeration)',
    () => {
      renderPage(project({ last_scan: scan({ status: 'running', total_files: 0, files_found: 0 }) }))

      expect(screen.getByText('0 von 0 Dateien verarbeitet')).toBeInTheDocument()
      const progress = screen.getByRole('progressbar') as HTMLProgressElement
      expect(progress.hasAttribute('value')).toBe(false)
      expect(progress.hasAttribute('max')).toBe(false)
    }
  )

  it('shows the five-stat summary once the scan succeeded, with two initially-collapsed disclosures', () => {
    renderPage(
      project({
        last_scan: scan({
          status: 'success',
          finished_at: '2026-07-20T10:05:00Z',
          photos_added: 10,
          photos_updated: 1,
          photos_removed: 3,
          files_skipped: 2,
          files_found: 16,
        }),
      })
    )

    expect(screen.getByText('Erfolgreich')).toBeInTheDocument()
    expect(screen.getByText('Hinzugefügt').nextElementSibling).toHaveTextContent('10')
    expect(screen.getByText('Dateien gefunden').nextElementSibling).toHaveTextContent('16')
    const removedDetails = screen.getByText('Entfernt').closest('details')
    expect(removedDetails).not.toHaveAttribute('open')
  })

  it('toggles the "Entfernt" disclosure open on click', async () => {
    const user = userEvent.setup()
    renderPage(
      project({
        last_scan: scan({ status: 'success', finished_at: '2026-07-20T10:05:00Z', photos_removed: 3 }),
      })
    )

    const summary = screen.getByText('Entfernt')
    await user.click(summary)

    expect(summary.closest('details')).toHaveAttribute('open')
  })

  it('shows the error message on a failed scan and keeps the button enabled', () => {
    renderPage(
      project({
        last_scan: scan({ status: 'failed', error_message: 'OpenCloud nicht erreichbar' }),
      })
    )

    expect(screen.getByText('OpenCloud nicht erreichbar')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /aktualisieren/i })).toBeEnabled()
  })
})
