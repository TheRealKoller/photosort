import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as projectsApi from '../../api/projects'
import type { CriterionScoringRunSummary, ProjectOut } from '../../api/types'
import { KuratierungStepPage } from './KuratierungStepPage'
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
    last_criterion_scoring_run: criterionScoringRun(),
    category_selection_enabled: true,
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
    selection_target: null,
    effective_selection_target: 42,
    has_selection_proposal: true,
    photo_count: 0,
    taken_at_earliest: null,
    taken_at_latest: null,
    ...overrides,
  }
}

function criterionScoringRun(
  overrides: Partial<CriterionScoringRunSummary> = {},
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
    cloud_phases: [],
    estimated_cost_usd: null,
    cloud_cost_total_usd: null,
    phase_remaining_seconds: null,
    persons_photos_total: null,
    persons_photos_processed: null,
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
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/x']}>
        <Routes>
          <Route element={<OutletHost project={initialProject} refetchProject={refetchProject} />}>
            <Route path="/x" element={<KuratierungStepPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const FIELD = /richtwert \(bilder\)/i

describe('KuratierungStepPage', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(projectsApi.setSelectionTarget).mockResolvedValue(project())
  })

  it('does not show the remote category classification section (moved to KriterienStepPage, #218)', () => {
    renderPage(project())

    expect(
      screen.queryByRole('heading', { name: 'Remote-Kategorisierung' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /remote-kategorisierung starten/i }),
    ).not.toBeInTheDocument()
  })

  it('links to /album without any search parameter', () => {
    /* Der Suchparameter `?topN=` ist mit ADR 0097 entfallen - der Umfang haengt am Projekt, nicht
     * am Aufruf der Ansicht. Das Ziel ist seit ADR 0098 der Album-Entwurf; die alte
     * Kuratierungsroute entfaellt ohne Weiterleitung, ein stehengebliebener Link liefe ins
     * Leere. */
    renderPage(project())

    expect(screen.getByRole('link', { name: 'Album-Entwurf öffnen' })).toHaveAttribute(
      'href',
      '/projects/1/album',
    )
  })

  it('explains that the target is a goal and not an upper bound', () => {
    renderPage(project())

    expect(screen.getByText(/ziel, keine obergrenze/i)).toBeInTheDocument()
    expect(screen.getByText(/mischt in jedem die vorkommenden motive/i)).toBeInTheDocument()
  })

  it('no longer promises that a rejected photo is replaced by the next best one', () => {
    // specs/features/0357-voller-bildvorrat-kuratierung.md, ADR 0071 Entscheidung 1: der Satz
    // "sortierst du eines aus, rückt automatisch das nächstbeste derselben Kategorie nach" ist
    // unwahr. Die Negativ-Assertion gehoert dazu - ein reiner Positivtest auf den neuen Text
    // bliebe auch dann gruen, wenn der alte Satz danebenstehen bliebe.
    renderPage(project())

    expect(screen.queryByText(/rückt automatisch das nächstbeste/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/nachrück/i)).not.toBeInTheDocument()
  })

  it('renders the shared target field with its server-side default and saves through it', async () => {
    /* Die Kuratierung nutzt DIESELBE Komponente wie der Klassifizierungs-Schritt. Die Zustaende
     * des Feldes prueft `SelectionTargetField.test.tsx`; hier nur, dass es da ist und speichert. */
    const user = userEvent.setup()
    renderPage(project({ selection_target: null, effective_selection_target: 42 }))

    const input = screen.getByLabelText(FIELD)
    expect((input as HTMLInputElement).value).toBe('')
    expect(input).toHaveAccessibleDescription('Standard: 42 Bilder.')
    expect(document.body.textContent).not.toMatch(/zehntel/i)

    await user.type(input, '150')
    await user.tab()

    await waitFor(() => {
      expect(projectsApi.setSelectionTarget).toHaveBeenCalledWith(1, 150)
    })
  })
})
