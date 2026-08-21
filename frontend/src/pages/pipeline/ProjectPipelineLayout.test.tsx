import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { createMemoryRouter, MemoryRouter, RouterProvider, Route, Routes, useOutletContext, useParams } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as projectsApi from '../../api/projects'
import type {
  CriterionScoringRunSummary,
  ProjectOut,
  ScanSummary,
  ScoringRunSummary,
} from '../../api/types'
import { ProjectPipelineLayout, type PipelineOutletContext } from './ProjectPipelineLayout'

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
    status: 'success',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: '2026-07-20T10:01:00Z',
    files_found: 5,
    total_files: 5,
    photos_added: 5,
    photos_updated: 0,
    photos_removed: 0,
    files_skipped: 0,
    error_message: null,
    ...overrides,
  }
}

function scoringRun(overrides: Partial<ScoringRunSummary> = {}): ScoringRunSummary {
  return {
    id: 1,
    status: 'success',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: '2026-07-20T10:01:00Z',
    photos_total: 10,
    photos_processed: 10,
    suggestions_found: 0,
    error_message: null,
    gate_confirmed_at: '2026-07-20T10:01:30Z',
    ...overrides,
  }
}

function criterionScoringRun(
  overrides: Partial<CriterionScoringRunSummary> = {}
): CriterionScoringRunSummary {
  return {
    status: 'success',
    started_at: '2026-07-20T10:02:00Z',
    finished_at: '2026-07-20T10:03:00Z',
    photos_total: 10,
    photos_processed: 10,
    error_message: null,
    ...overrides,
  }
}

function StepProbe() {
  const { step } = useParams()
  const { project: outletProject } = useOutletContext<PipelineOutletContext>()
  return (
    <p>
      Schritt-Inhalt: {step} / Projekt: {outletProject.name}
    </p>
  )
}

function renderLayout(initialPath = '/projects/1/pipeline') {
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
          <Route path="/projects/:projectId/pipeline" element={<ProjectPipelineLayout />}>
            <Route path=":step" element={<StepProbe />} />
          </Route>
        </Routes>
      </MemoryRouter>,
      { wrapper }
    ),
    queryClient,
  }
}

describe('ProjectPipelineLayout', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.getProject).mockReset()
  })

  it('shows a dedicated not-found state on a 404 instead of a broken page', async () => {
    vi.mocked(projectsApi.getProject).mockRejectedValue(new ApiError(404, 'Projekt nicht gefunden.'))

    renderLayout('/projects/1/pipeline/scan')

    expect(await screen.findByText(/projekt nicht gefunden/i)).toBeInTheDocument()
  })

  it('shows a loading state before the project data arrives', async () => {
    vi.mocked(projectsApi.getProject).mockReturnValue(new Promise(() => {}))

    renderLayout('/projects/1/pipeline/scan')

    expect(await screen.findByRole('status')).toHaveTextContent(/projekt wird geladen/i)
  })

  it('shows a generic error banner on a non-404 failure', async () => {
    vi.mocked(projectsApi.getProject).mockRejectedValue(new ApiError(500, 'Serverfehler'))

    renderLayout('/projects/1/pipeline/scan')

    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('redirects the base route without :step to the default step (Akzeptanzkriterium 10)', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderLayout('/projects/1/pipeline')

    expect(await screen.findByText(/schritt-inhalt: scan/i)).toBeInTheDocument()
  })

  it('redirects an unknown :step value to the highest reachable step (Akzeptanzkriterium 10)', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderLayout('/projects/1/pipeline/does-not-exist')

    expect(await screen.findByText(/schritt-inhalt: scan/i)).toBeInTheDocument()
  })

  it('redirects a currently-unreachable :step deep link to the highest reachable step (Akzeptanzkriterium 10)', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project({ last_scan: scan() }))

    // kriterien ist erst nach bestaetigtem Gate erreichbar - hier noch nicht der Fall.
    renderLayout('/projects/1/pipeline/kriterien')

    expect(await screen.findByText(/schritt-inhalt: ausschuss/i)).toBeInTheDocument()
  })

  it('renders the requested step content when it is currently reachable, via useOutletContext', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({
        last_scan: scan(),
        last_scoring_run: scoringRun(),
      })
    )

    renderLayout('/projects/1/pipeline/gate')

    expect(
      await screen.findByText('Schritt-Inhalt: gate / Projekt: Costa Rica')
    ).toBeInTheDocument()
  })

  it('renders the Stepper progress nav alongside the step content', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderLayout('/projects/1/pipeline/scan')

    await screen.findByText(/schritt-inhalt: scan/i)
    expect(screen.getByRole('navigation', { name: 'Fortschritt der Pipeline' })).toBeInTheDocument()
  })

  it('shows the project name/path header and secondary navigation links', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderLayout('/projects/1/pipeline/scan')

    await screen.findByText(/schritt-inhalt: scan/i)
    expect(screen.getByText('Costa Rica')).toBeInTheDocument()
    expect(screen.getByText('CostaRica')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /fotos ansehen/i })).toHaveAttribute(
      'href',
      '/projects/1/photos'
    )
    expect(screen.getByRole('link', { name: /vergleichen/i })).toHaveAttribute(
      'href',
      '/projects/1/compare'
    )
    // specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md: einzige aktuelle
    // Navigations-Einstiegsstelle in die neue Projekteinstellungs-Route.
    expect(screen.getByRole('link', { name: /einstellungen/i })).toHaveAttribute(
      'href',
      '/projects/1/settings'
    )
  })

  it(
    'redirects automatically once a live poll makes the currently viewed step unreachable, ' +
      'without any user navigation (Akzeptanzkriterium 11 - Rennen zwischen Redirect und Poll)',
    { timeout: 10000 },
    async () => {
      const doneThroughKriterien = project({
        // last_scan running haelt das Polling aktiv, unabhaengig vom (separaten)
        // Kriterien-Bewertungsstatus - simuliert einen zeitgleich laufenden Re-Scan.
        last_scan: scan({ status: 'running' }),
        last_scoring_run: scoringRun(),
        last_criterion_scoring_run: criterionScoringRun({ status: 'success' }),
      })
      vi.mocked(projectsApi.getProject)
        .mockResolvedValueOnce(doneThroughKriterien)
        .mockResolvedValue({
          ...doneThroughKriterien,
          last_criterion_scoring_run: criterionScoringRun({ status: 'failed' }),
        })

      renderLayout('/projects/1/pipeline/kuratierung')

      expect(await screen.findByText(/schritt-inhalt: kuratierung/i)).toBeInTheDocument()

      // Kriterien-Bewertung ist nach dem naechsten Poll nicht mehr erfolgreich - kuratierung wird
      // dadurch unerreichbar. Der neue Frontier ist "scan" (bleibt waehrend des gesamten Tests
      // absichtlich "running"/nicht erledigt, siehe getFrontierStepId-Kommentar in
      // utils/pipelineSteps.ts: der erste erreichbare, NICHT erledigte Schritt gewinnt, unabhaengig
      // davon, wie weit die Pipeline dahinter schon fortgeschritten ist).
      await waitFor(
        () => expect(screen.getByText(/schritt-inhalt: scan/i)).toBeInTheDocument(),
        { timeout: 8000 }
      )
    }
  )

  it(
    'produces no additional history entry when redirecting away from an unreachable deep ' +
      'link (Akzeptanzkriterium 10 - kein Zurueck-Button-Loop)',
    async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(project())
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
      })
      const router = createMemoryRouter(
        [
          { path: '/', element: <p>Projektliste-Seite</p> },
          {
            path: '/projects/:projectId/pipeline',
            element: <ProjectPipelineLayout />,
            children: [{ path: ':step', element: <StepProbe /> }],
          },
        ],
        { initialEntries: ['/', '/projects/1/pipeline/kriterien'], initialIndex: 1 }
      )

      render(
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      )

      // Fuer ein frisches Projekt (nur scan/ausschuss erreichbar) ist der hoechste erreichbare
      // Schritt "scan" (siehe utils/pipelineSteps.ts, getFrontierStepId).
      await screen.findByText(/schritt-inhalt: scan/i)

      router.navigate(-1)

      await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    }
  )

  it('stops fetching after unmount while polling is active (no leaked interval)', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({ last_scan: scan({ status: 'running' }) })
    )

    const { unmount } = renderLayout('/projects/1/pipeline/scan')
    await screen.findByText(/schritt-inhalt: scan/i)
    const callsBeforeUnmount = vi.mocked(projectsApi.getProject).mock.calls.length

    unmount()
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(vi.mocked(projectsApi.getProject).mock.calls.length).toBe(callsBeforeUnmount)
  })
})
