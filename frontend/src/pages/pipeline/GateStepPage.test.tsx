import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import type { ProjectOut, ScoringRunSummary } from '../../api/types'
import { GateStepPage } from './GateStepPage'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

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

function scoringRun(overrides: Partial<ScoringRunSummary> = {}): ScoringRunSummary {
  return {
    id: 1,
    status: 'success',
    started_at: '2026-07-20T10:00:00Z',
    finished_at: '2026-07-20T10:05:00Z',
    photos_total: 10,
    photos_processed: 10,
    suggestions_found: 2,
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
  return render(
    <MemoryRouter initialEntries={['/x']}>
      <Routes>
        <Route element={<OutletHost project={initialProject} refetchProject={refetchProject} />}>
          <Route path="/x" element={<GateStepPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
}

describe('GateStepPage', () => {
  it('shows a short explanation line (Akzeptanzkriterium 8)', () => {
    renderPage(project({ last_scoring_run: scoringRun({ gate_confirmed_at: null }) }))

    expect(screen.getByText(/bestätige einmalig/i)).toBeInTheDocument()
  })

  it('shows "Ausstehend" and a link into the gate screen while unconfirmed', () => {
    renderPage(project({ last_scoring_run: scoringRun({ gate_confirmed_at: null }) }))

    expect(screen.getByText('Ausstehend')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ausschuss sichten' })).toHaveAttribute(
      'href',
      '/projects/1/photos?filter=suggested&gate=1'
    )
  })

  it(
    'shows the persistent auto-confirmed status when no suggestions were found ' +
      '(Akzeptanzkriterium 8: bleibt "erledigt" im Stepper, aber hier nachvollziehbar)',
    () => {
      renderPage(
        project({
          last_scoring_run: scoringRun({ suggestions_found: 0, gate_confirmed_at: '2026-07-20T10:05:00Z' }),
        })
      )

      expect(screen.getByText('Kein Ausschuss gefunden — automatisch bestätigt')).toBeInTheDocument()
      expect(screen.queryByRole('link', { name: 'Ausschuss sichten' })).not.toBeInTheDocument()
    }
  )

  it('shows the confirmation date once manually confirmed', () => {
    renderPage(
      project({
        last_scoring_run: scoringRun({ suggestions_found: 3, gate_confirmed_at: '2026-07-20T10:05:00Z' }),
      })
    )

    expect(screen.getByText(/ausschuss gesichtet am/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Ausschuss sichten' })).not.toBeInTheDocument()
  })
})
