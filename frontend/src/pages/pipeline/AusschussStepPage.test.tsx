import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as projectsApi from '../../api/projects'
import type { ProjectOut, ScoringRunSummary } from '../../api/types'
import { AusschussStepPage } from './AusschussStepPage'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

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
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
    ...overrides,
  }
}

function scoringRun(overrides: Partial<ScoringRunSummary> = {}): ScoringRunSummary {
  return {
    id: 1,
    status: 'running',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: null,
    photos_total: 0,
    photos_processed: 0,
    suggestions_found: 0,
    error_message: null,
    gate_confirmed_at: null,
    ...overrides,
  }
}

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
            <Route path="/x" element={<AusschussStepPage />} />
          </Route>
        </Routes>
      </MemoryRouter>,
      { wrapper }
    ),
    refetchProject,
  }
}

describe('AusschussStepPage', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.triggerScore).mockReset()
  })

  it('shows a short explanation line (UI/UX-Abschnitt der Spec 0042)', () => {
    renderPage(project({ last_scoring_run: null }))

    expect(screen.getByText(/erkennt automatisch unscharfe/i)).toBeInTheDocument()
  })

  it('shows an active button and a hint when never scored', () => {
    renderPage(project({ last_scoring_run: null }))

    expect(screen.getByRole('button', { name: /ausschuss aussortieren/i })).toBeEnabled()
    expect(screen.getByText(/noch nicht vorgeschlagen/i)).toBeInTheDocument()
  })

  it(
    'keeps the button reachable even when scan has never run (Regressionsschutz: bewusst ' +
      'ungegatet, Akzeptanzkriterium 3)',
    () => {
      renderPage(project({ last_scan: null, last_scoring_run: null }))

      expect(screen.getByRole('button', { name: /ausschuss aussortieren/i })).toBeEnabled()
    }
  )

  it('disables the button synchronously on click and sends exactly one request on a double click', async () => {
    vi.mocked(projectsApi.triggerScore).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: null }))

    const button = screen.getByRole('button', { name: /ausschuss aussortieren/i })
    await user.click(button)
    await user.click(button)

    expect(button).toBeDisabled()
    expect(projectsApi.triggerScore).toHaveBeenCalledTimes(1)
  })

  it('re-enables the button and shows an error when the trigger request itself fails', async () => {
    vi.mocked(projectsApi.triggerScore).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    const user = userEvent.setup()
    renderPage(project({ last_scoring_run: null }))

    await user.click(screen.getByRole('button', { name: /ausschuss aussortieren/i }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /ausschuss aussortieren/i })).toBeEnabled()
    )
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('shows granular "X von Y" progress with a native progress element while running', () => {
    renderPage(
      project({ last_scoring_run: scoringRun({ photos_total: 10, photos_processed: 4 }) })
    )

    expect(screen.getByText(/4 von 10 fotos verarbeitet/i)).toBeInTheDocument()
    const progress = screen.getByRole('progressbar') as HTMLProgressElement
    expect(progress.max).toBe(10)
    expect(progress.value).toBe(4)
  })

  it(
    'shows an indeterminate progress bar instead of an invalid max=0 during the brief ' +
      'photos_total=0 window right after the trigger',
    () => {
      renderPage(project({ last_scoring_run: scoringRun({ photos_total: 0, photos_processed: 0 }) }))

      const progress = screen.getByRole('progressbar') as HTMLProgressElement
      expect(progress.hasAttribute('value')).toBe(false)
      expect(progress.hasAttribute('max')).toBe(false)
    }
  )

  it('shows a summary with the plural suggestion count once scoring succeeded, plus a link to review it', () => {
    renderPage(
      project({
        last_scoring_run: scoringRun({
          status: 'success',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 3,
        }),
      })
    )

    expect(screen.getByText('3 Vorschläge gefunden')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'Vorschläge aus der Ausschuss-Aussortierung ansehen' })
    ).toHaveAttribute('href', '/projects/1/photos?filter=suggested')
  })

  it('shows a singular suggestion count when exactly one suggestion was found', () => {
    renderPage(
      project({
        last_scoring_run: scoringRun({
          status: 'success',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 1,
        }),
      })
    )

    expect(screen.getByText('1 Vorschlag gefunden')).toBeInTheDocument()
  })

  it('shows an inline error banner with a retry button on a failed scoring run', async () => {
    vi.mocked(projectsApi.triggerScore).mockResolvedValue({ status: 'queued' })
    const user = userEvent.setup()
    renderPage(
      project({ last_scoring_run: scoringRun({ status: 'failed', error_message: 'Unerwarteter Fehler' }) })
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Unerwarteter Fehler')
    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

    expect(projectsApi.triggerScore).toHaveBeenCalledWith(1)
  })
})
