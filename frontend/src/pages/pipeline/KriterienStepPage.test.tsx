import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as projectsApi from '../../api/projects'
import type { CriterionScoringRunSummary, ProjectOut, ScoringRunSummary } from '../../api/types'
import { KriterienStepPage } from './KriterienStepPage'
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
    last_scoring_run: scoringRun(),
    last_criterion_scoring_run: null,
    last_remote_category_classification_run: null,
    category_selection_enabled: true,
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
    ...overrides,
  }
}

function scoringRun(overrides: Partial<ScoringRunSummary> = {}): ScoringRunSummary {
  return {
    id: 42,
    status: 'success',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: '2026-07-20T10:05:00Z',
    photos_total: 10,
    photos_processed: 10,
    suggestions_found: 0,
    error_message: null,
    gate_confirmed_at: '2026-07-20T10:05:00Z',
    ...overrides,
  }
}

function criterionScoringRun(
  overrides: Partial<CriterionScoringRunSummary> = {}
): CriterionScoringRunSummary {
  return {
    status: 'running',
    started_at: '2026-07-20T10:06:00Z',
    finished_at: null,
    photos_total: 0,
    photos_processed: 0,
    error_message: null,
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
  return render(
    <MemoryRouter initialEntries={['/x']}>
      <Routes>
        <Route element={<OutletHost project={initialProject} refetchProject={refetchProject} />}>
          <Route path="/x" element={<KriterienStepPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
}

describe('KriterienStepPage', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.triggerScoreCriteria).mockReset()
    vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockReset()
    vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue({
      candidate_count: 0,
      provider: 'anthropic',
      price_per_image_usd: 0.0045,
      estimated_cost_usd: 0,
    })
    vi.mocked(projectsApi.triggerClassifyCategoriesRemote).mockReset()
    // Die Remote-Kategorisierungs-Section laedt seit specs/features/0289-feste-kategorien.md
    // zusaetzlich die Feinlabel-Haeufigkeiten - ohne Mock liefe die Query in einen Fehler und
    // legte einen zweiten Alert auf die Seite.
    vi.mocked(projectsApi.listFineLabels).mockReset()
    vi.mocked(projectsApi.listFineLabels).mockResolvedValue([])
  })

  it('shows the explanation line and an enabled trigger once reachable', () => {
    renderPage(project({ last_criterion_scoring_run: null }))

    expect(
      screen.getByText(/bewertet jedes verbleibende foto nach mehreren kriterien/i)
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Kriterien-Bewertung starten' })).toBeEnabled()
  })

  it('sends the scoring_run_id of last_scoring_run when triggered', async () => {
    vi.mocked(projectsApi.triggerScoreCriteria).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderPage(project({ last_criterion_scoring_run: null }))

    await user.click(screen.getByRole('button', { name: 'Kriterien-Bewertung starten' }))

    expect(projectsApi.triggerScoreCriteria).toHaveBeenCalledWith(1, 42)
  })

  it('disables the button synchronously on click and sends exactly one request on a double click', async () => {
    vi.mocked(projectsApi.triggerScoreCriteria).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderPage(project({ last_criterion_scoring_run: null }))

    const button = screen.getByRole('button', { name: 'Kriterien-Bewertung starten' })
    await user.click(button)
    await user.click(button)

    expect(button).toBeDisabled()
    expect(projectsApi.triggerScoreCriteria).toHaveBeenCalledTimes(1)
  })

  it('re-enables the button and shows an error when the trigger request itself fails', async () => {
    vi.mocked(projectsApi.triggerScoreCriteria).mockRejectedValue(new ApiError(500, 'Serverfehler'))
    const user = userEvent.setup()
    renderPage(project({ last_criterion_scoring_run: null }))

    await user.click(screen.getByRole('button', { name: 'Kriterien-Bewertung starten' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Kriterien-Bewertung starten' })).toBeEnabled()
    )
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('shows granular "X von Y" progress with a native progress element while running', () => {
    renderPage(
      project({
        last_criterion_scoring_run: criterionScoringRun({ photos_total: 10, photos_processed: 4 }),
        last_remote_category_classification_run: null,
      })
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
      renderPage(
        project({
          last_criterion_scoring_run: criterionScoringRun({ photos_total: 0, photos_processed: 0 }),
          last_remote_category_classification_run: null,
        })
      )

      const progress = screen.getByRole('progressbar') as HTMLProgressElement
      expect(progress.hasAttribute('value')).toBe(false)
      expect(progress.hasAttribute('max')).toBe(false)
    }
  )

  it('shows a success status once the run succeeded', () => {
    renderPage(
      project({
        last_criterion_scoring_run: criterionScoringRun({
          status: 'success',
          finished_at: '2026-07-20T10:07:00Z',
          photos_total: 10,
          photos_processed: 10,
        }),
      })
    )

    expect(screen.getByText('Erfolgreich bewertet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Kriterien-Bewertung starten' })).toBeEnabled()
  })

  it('shows an inline error banner with a retry button on a failed run', async () => {
    vi.mocked(projectsApi.triggerScoreCriteria).mockResolvedValue({ status: 'queued' })
    const user = userEvent.setup()
    renderPage(
      project({
        last_criterion_scoring_run: criterionScoringRun({
          status: 'failed',
          error_message: 'Unerwarteter Fehler',
        }),
      })
    )

    expect(await screen.findByRole('alert')).toHaveTextContent('Unerwarteter Fehler')
    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

    expect(projectsApi.triggerScoreCriteria).toHaveBeenCalledWith(1, 42)
  })

  it('shows the remote category classification section after the criteria scoring section', () => {
    renderPage(project())

    const headings = screen.getAllByRole('heading', { level: 2 })
    const headingTexts = headings.map((heading) => heading.textContent)
    expect(headingTexts).toEqual(['Kriterien-Bewertung', 'Remote-Kategorisierung'])
  })

  it(
    'estimates, opens the confirmation dialog and triggers the remote classification on confirm',
    async () => {
      vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue({
        candidate_count: 5,
        provider: 'anthropic',
        price_per_image_usd: 0.0045,
        estimated_cost_usd: 0.0225,
      })
      vi.mocked(projectsApi.triggerClassifyCategoriesRemote).mockReturnValue(new Promise(() => {}))
      const user = userEvent.setup()
      renderPage(project({ cloud_vision_detection_enabled: true }))

      await screen.findByTestId('classify-categories-remote-estimate')
      await user.click(screen.getByRole('button', { name: /remote-kategorisierung starten/i }))
      await user.click(screen.getByRole('button', { name: /^starten$/i }))

      expect(projectsApi.triggerClassifyCategoriesRemote).toHaveBeenCalledWith(1)
    }
  )

  it('does not affect the criteria scoring section when the remote classification is triggered', async () => {
    vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue({
      candidate_count: 5,
      provider: 'anthropic',
      price_per_image_usd: 0.0045,
      estimated_cost_usd: 0.0225,
    })
    vi.mocked(projectsApi.triggerClassifyCategoriesRemote).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderPage(
      project({ cloud_vision_detection_enabled: true, last_criterion_scoring_run: null })
    )

    await screen.findByTestId('classify-categories-remote-estimate')
    await user.click(screen.getByRole('button', { name: /remote-kategorisierung starten/i }))
    await user.click(screen.getByRole('button', { name: /^starten$/i }))

    expect(screen.getByRole('button', { name: 'Kriterien-Bewertung starten' })).toBeEnabled()
    expect(projectsApi.triggerScoreCriteria).not.toHaveBeenCalled()
  })
})
