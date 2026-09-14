import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import * as projectsApi from '../../api/projects'
import type { CriterionScoringRunSummary, ProjectOut } from '../../api/types'
import { KuratierungStepPage, SAVED_HINT_MS } from './KuratierungStepPage'
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

  // Der eine Fall unten stellt die Uhr; ohne diese Rueckgabe liefe jeder folgende Fall in eine
  // stehende Uhr und damit in einen Zeitueberschreitungsfehler, der nichts mit ihm zu tun hat.
  afterEach(() => {
    vi.useRealTimers()
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

  it('leaves the field empty when nothing is set and shows the default in the hint', async () => {
    /* "Leer heißt Vorbelegung": stünde die vorbelegte Zahl IM Feld, wäre "vom System vorbelegt"
     * von "selbst eingestellt" nicht mehr zu unterscheiden. Der Hinweistext hängt per
     * `aria-describedby` am Feld, damit die Zahl auch vorgelesen wird. */
    renderPage(project({ selection_target: null, effective_selection_target: 42 }))

    const input = screen.getByLabelText(FIELD)
    expect((input as HTMLInputElement).value).toBe('')
    expect(input).toHaveAccessibleDescription(/leer = ein zehntel der bilderzahl \(zurzeit 42\)/i)
  })

  it('shows a set target in the field', () => {
    renderPage(project({ selection_target: 150, effective_selection_target: 150 }))

    expect((screen.getByLabelText(FIELD) as HTMLInputElement).value).toBe('150')
  })

  it('saves on blur', async () => {
    const user = userEvent.setup()
    renderPage(project())

    const input = screen.getByLabelText(FIELD)
    await user.type(input, '150')
    await user.tab()

    await waitFor(() => {
      expect(projectsApi.setSelectionTarget).toHaveBeenCalledWith(1, 150)
    })
  })

  it('saves on Enter', async () => {
    const user = userEvent.setup()
    renderPage(project())

    await user.type(screen.getByLabelText(FIELD), '150{Enter}')

    await waitFor(() => {
      expect(projectsApi.setSelectionTarget).toHaveBeenCalledWith(1, 150)
    })
  })

  it('does not call the endpoint for an unchanged value', async () => {
    /* Jedes Speichern rechnet den gesamten Vorschlag neu - ein Aufruf ohne Änderung wäre eine
     * vollständige Neuberechnung für nichts. */
    const user = userEvent.setup()
    renderPage(project({ selection_target: 150, effective_selection_target: 150 }))

    await user.click(screen.getByLabelText(FIELD))
    await user.tab()

    expect(projectsApi.setSelectionTarget).not.toHaveBeenCalled()
  })

  it('sends null when the field is cleared', async () => {
    /* Das Leeren des Feldes ist der EINZIGE Weg zur Vorbelegung - `0` weist der Endpunkt ab. */
    const user = userEvent.setup()
    renderPage(project({ selection_target: 150, effective_selection_target: 150 }))

    await user.clear(screen.getByLabelText(FIELD))
    await user.tab()

    await waitFor(() => {
      expect(projectsApi.setSelectionTarget).toHaveBeenCalledWith(1, null)
    })
  })

  it('disables the field while the request runs', async () => {
    const user = userEvent.setup()
    let resolveSave: ((value: ProjectOut) => void) | undefined
    vi.mocked(projectsApi.setSelectionTarget).mockReturnValue(
      new Promise<ProjectOut>((resolve) => {
        resolveSave = resolve
      }),
    )
    renderPage(project())

    await user.type(screen.getByLabelText(FIELD), '150')
    await user.tab()

    await waitFor(() => {
      expect(screen.getByLabelText(FIELD)).toBeDisabled()
    })

    resolveSave?.(project({ selection_target: 150, effective_selection_target: 150 }))
    await waitFor(() => {
      expect(screen.getByLabelText(FIELD)).toBeEnabled()
    })
  })

  it('confirms a successful save and takes the confirmation back again', async () => {
    /* "Für wenige Sekunden" ist die Zusage - ein dauerhafter Erfolgshinweis stünde nach Minuten
     * noch da. Beide Hälften in einem Fall: der Positivteil allein bestünde auch bei einem
     * bleibenden Hinweis. */
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    renderPage(project())

    await user.type(screen.getByLabelText(FIELD), '150')
    await user.tab()
    await waitFor(() => {
      expect(screen.getByText(/vorschlag neu berechnet/i)).toBeInTheDocument()
    })

    await act(async () => {
      vi.advanceTimersByTime(SAVED_HINT_MS + 1)
    })

    expect(screen.queryByText(/vorschlag neu berechnet/i)).not.toBeInTheDocument()
  })

  it('shows an error alert and keeps the typed value when the save fails', async () => {
    /* Das Feld behält den eingegebenen Wert, statt ihn stillschweigend zurückzusetzen - sonst
     * verliert der Nutzer seine Eingabe an einen Fehler, den er gerade erst gelesen hat. */
    const user = userEvent.setup()
    vi.mocked(projectsApi.setSelectionTarget).mockRejectedValue(
      new ApiError(409, 'Fuer dieses Projekt laeuft gerade eine Kriterien-Bewertung.'),
    )
    renderPage(project())

    await user.type(screen.getByLabelText(FIELD), '150')
    await user.tab()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/kriterien-bewertung/i)
    expect((screen.getByLabelText(FIELD) as HTMLInputElement).value).toBe('150')
  })

  it('takes the error back once the field holds the stored value again', async () => {
    /* Ohne diesen Fall bliebe "Richtwert nicht gespeichert" über einem Feld stehen, an dem nichts
     * mehr zu speichern ist: `commit()` kehrt bei unverändertem Wert früh zurück und ließe den
     * Fehlerzustand der Mutation sonst unberührt. Die Meldung behauptete dann etwas über eine
     * Eingabe, die es nicht mehr gibt. */
    const user = userEvent.setup()
    vi.mocked(projectsApi.setSelectionTarget).mockRejectedValue(
      new ApiError(409, 'Fuer dieses Projekt laeuft gerade eine Kriterien-Bewertung.'),
    )
    renderPage(project({ selection_target: 150, effective_selection_target: 150 }))

    const input = screen.getByLabelText(FIELD)
    await user.clear(input)
    await user.type(input, '200')
    await user.tab()
    expect(await screen.findByRole('alert')).toBeInTheDocument()

    await user.clear(input)
    await user.type(input, '150')
    await user.tab()

    await waitFor(() => {
      expect(screen.queryByRole('alert')).toBeNull()
    })
    expect(projectsApi.setSelectionTarget).toHaveBeenCalledTimes(1)
  })

  it('does not clamp a typed value - the endpoint decides', async () => {
    /* Der Nachfolger des früheren Klemm-Falls: das Frontend kennt die Grenze nicht mehr. Es setzt
     * `min={1}` am Feld, durchgesetzt wird sie allein serverseitig. Ein clientseitiges Klemmen
     * wäre eine zweite Wahrheit über die Grenze. */
    const user = userEvent.setup()
    renderPage(project())

    const input = screen.getByLabelText(FIELD)
    await user.type(input, '99999')
    await user.tab()

    expect((input as HTMLInputElement).value).toBe('99999')
    await waitFor(() => {
      expect(projectsApi.setSelectionTarget).toHaveBeenCalledWith(1, 99999)
    })
  })

  it('keeps the field narrow and marks it as a number field with a lower bound', () => {
    renderPage(project())

    const field = screen.getByLabelText(FIELD)
    expect(field).toHaveAttribute('type', 'number')
    expect(field).toHaveAttribute('min', '1')
    expect(field.className).toContain('w-24')
  })
})
