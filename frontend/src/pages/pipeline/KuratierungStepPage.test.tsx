import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import type { CriterionScoringRunSummary, ProjectOut } from '../../api/types'
import { KuratierungStepPage } from './KuratierungStepPage'
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
    last_criterion_scoring_run: criterionScoringRun(),
    last_remote_category_classification_run: null,
    category_selection_enabled: true,
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
    ...overrides,
  }
}

function criterionScoringRun(
  overrides: Partial<CriterionScoringRunSummary> = {}
): CriterionScoringRunSummary {
  return {
    status: 'success',
    started_at: '2026-07-20T10:06:00Z',
    finished_at: '2026-07-20T10:07:00Z',
    photos_total: 10,
    photos_processed: 10,
    error_message: null,
    phase: null,
    cloud_requested: false,
    cloud_error_message: null,
    ...overrides,
  }
}

function OutletHost({ project: contextProject, refetchProject }: PipelineOutletContext) {
  return <Outlet context={{ project: contextProject, refetchProject } satisfies PipelineOutletContext} />
}

function renderPage(initialProject: ProjectOut, refetchProject = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/x']}>
        <Routes>
          <Route element={<OutletHost project={initialProject} refetchProject={refetchProject} />}>
            <Route path="/x" element={<KuratierungStepPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('KuratierungStepPage', () => {
  it('does not show the remote category classification section (moved to KriterienStepPage, #218)', () => {
    renderPage(project())

    expect(
      screen.queryByRole('heading', { name: 'Remote-Kategorisierung' })
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /remote-kategorisierung starten/i })
    ).not.toBeInTheDocument()
  })

  it('shows the explanation line and links to /curate with the default top-N of 3', () => {
    renderPage(project())

    expect(
      screen.getByText(/zeigt pro foto-moment und kategorie die besten n fotos/i)
    ).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'Kuratierung öffnen' })
    expect(link).toHaveAttribute('href', '/projects/1/curate?topN=3')
    expect((screen.getByLabelText(/top-fotos pro kategorie/i) as HTMLInputElement).value).toBe('3')
  })

  it('reflects a typed top-N value in the curate link', async () => {
    const user = userEvent.setup()
    renderPage(project())

    const input = screen.getByLabelText(/top-fotos pro kategorie/i)
    await user.clear(input)
    await user.type(input, '5')

    expect(screen.getByRole('link', { name: 'Kuratierung öffnen' })).toHaveAttribute(
      'href',
      '/projects/1/curate?topN=5'
    )
  })

  it('clamps a typed value above the 1-10 range instead of forwarding it as-is', async () => {
    const user = userEvent.setup()
    renderPage(project())

    const input = screen.getByLabelText(/top-fotos pro kategorie/i)
    await user.clear(input)
    await user.type(input, '20')

    expect(screen.getByRole('link', { name: 'Kuratierung öffnen' })).toHaveAttribute(
      'href',
      '/projects/1/curate?topN=10'
    )
  })

  it('keeps the previous valid value instead of falling through to 0 when the field is cleared', async () => {
    const user = userEvent.setup()
    renderPage(project())

    const input = screen.getByLabelText(/top-fotos pro kategorie/i)
    await user.clear(input)

    expect(screen.getByRole('link', { name: 'Kuratierung öffnen' })).toHaveAttribute(
      'href',
      '/projects/1/curate?topN=3'
    )
  })
})
