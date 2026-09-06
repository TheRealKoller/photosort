import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as projectsApi from '../../api/projects'
import type { ProjectOut, ScoringRunSummary } from '../../api/types'
import { KriterienStepPage } from './KriterienStepPage'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

// specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md: die Seite ist seit dieser
// Spec eine reine Verdrahtung von Outlet-Kontext zu ClassificationSection - die vollstaendige
// Verhaltensmatrix (Checkbox, Schaetzung, Teilschritte, Fehlerverhalten) liegt in
// components/ClassificationSection.test.tsx. Hier bleibt nur, was tatsaechlich Seiten-Ebene ist:
// dass genau EINE Sektion gerendert wird und der Outlet-Kontext korrekt durchgereicht wird.

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

function OutletHost({ project: contextProject, refetchProject }: PipelineOutletContext) {
  return (
    <Outlet context={{ project: contextProject, refetchProject } satisfies PipelineOutletContext} />
  )
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
    vi.mocked(projectsApi.triggerClassification).mockReset()
    vi.mocked(projectsApi.getClassificationEstimate).mockReset()
    vi.mocked(projectsApi.getClassificationEstimate).mockResolvedValue({
      candidate_count: 0,
      remote_category_candidate_count: 0,
      landmark_candidate_count: 0,
      provider: 'anthropic',
      model: 'claude-haiku-4-5',
      price_per_image_usd: 0.0052,
      estimated_cost_usd: 0,
    })
    vi.mocked(projectsApi.listFineLabels).mockReset()
    vi.mocked(projectsApi.listFineLabels).mockResolvedValue([])
  })

  it('renders exactly one section, the classification one', () => {
    renderPage(project())

    const headings = screen.getAllByRole('heading', { level: 2 })
    expect(headings.map((heading) => heading.textContent)).toEqual(['Klassifizierung'])
  })

  it('wires the outlet project through, so the trigger knows the current scoring run', () => {
    renderPage(project({ last_scoring_run: scoringRun({ id: 99 }) }))

    // Der Auslöser ist nur bedienbar, wenn ein ScoringRun aus dem Outlet-Kontext ankam.
    expect(screen.getByRole('button', { name: 'Klassifizierung starten' })).toBeEnabled()
  })

  it('disables the trigger when no scoring run reached the page', () => {
    renderPage(project({ last_scoring_run: null }))

    expect(screen.getByRole('button', { name: 'Klassifizierung starten' })).toBeDisabled()
  })
})
