import { render, screen } from '@testing-library/react'
import { Outlet, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import type { StepId } from '../../utils/pipelineSteps'
import { PIPELINE_STEPS } from '../../utils/pipelineSteps'
import { PipelineStepView } from './PipelineStepView'
import type { PipelineOutletContext } from './ProjectPipelineLayout'
import { makeProject as project } from '../../test/fixtures'
import { makeQueryClient, withProviders } from '../../test/render'

function OutletHost() {
  const context: PipelineOutletContext = { project: project(), refetchProject: vi.fn() }
  return <Outlet context={context} />
}

function renderAt(step: StepId) {
  const queryClient = makeQueryClient()
  return render(
    withProviders(
      <>
        <Routes>
          <Route path="/x" element={<OutletHost />}>
            <Route path=":step" element={<PipelineStepView />} />
          </Route>
        </Routes>
      </>,
      { queryClient, initialEntries: [`/x/${step}`] },
    ),
  )
}

// Nachweis, dass JEDER bekannte StepId-Wert auf eine tatsaechlich unterscheidbare Detailseite
// abgebildet wird - je Seite reicht eine eindeutige, bereits durch die jeweilige *StepPage.test.tsx
// abgedeckte Textmarke als Stellvertreter, kein erneuter voller Inhaltstest hier.
const EXPECTED_MARKERS: Record<StepId, RegExp> = {
  scan: /durchsucht den verknüpften opencloud-ordner/i,
  ausschuss: /erkennt automatisch unscharfe/i,
  kriterien: /bewertet jedes verbleibende foto/i,
  kuratierung: /deckt alle foto-momente ab/i,
}

describe('PipelineStepView', () => {
  for (const { id } of PIPELINE_STEPS) {
    it(`renders the ${id} detail page for :step="${id}"`, () => {
      renderAt(id)

      expect(screen.getByText(EXPECTED_MARKERS[id])).toBeInTheDocument()
    })
  }
})
