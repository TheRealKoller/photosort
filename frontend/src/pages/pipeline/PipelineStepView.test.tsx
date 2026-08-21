import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import type { ProjectOut } from '../../api/types'
import type { StepId } from '../../utils/pipelineSteps'
import { PIPELINE_STEPS } from '../../utils/pipelineSteps'
import { PipelineStepView } from './PipelineStepView'
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

function OutletHost() {
  const context: PipelineOutletContext = { project: project(), refetchProject: vi.fn() }
  return <Outlet context={context} />
}

function renderAt(step: StepId) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/x/${step}`]}>
        <Routes>
          <Route path="/x" element={<OutletHost />}>
            <Route path=":step" element={<PipelineStepView />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

// Nachweis, dass JEDER bekannte StepId-Wert auf eine tatsaechlich unterscheidbare Detailseite
// abgebildet wird - je Seite reicht eine eindeutige, bereits durch die jeweilige *StepPage.test.tsx
// abgedeckte Textmarke als Stellvertreter, kein erneuter voller Inhaltstest hier.
const EXPECTED_MARKERS: Record<StepId, RegExp> = {
  scan: /durchsucht den verknüpften opencloud-ordner/i,
  ausschuss: /erkennt automatisch unscharfe/i,
  gate: /bestätige einmalig/i,
  kriterien: /bewertet jedes verbleibende foto/i,
  kuratierung: /zeigt pro foto-moment und kategorie/i,
}

describe('PipelineStepView', () => {
  for (const { id } of PIPELINE_STEPS) {
    it(`renders the ${id} detail page for :step="${id}"`, () => {
      renderAt(id)

      expect(screen.getByText(EXPECTED_MARKERS[id])).toBeInTheDocument()
    })
  }
})
