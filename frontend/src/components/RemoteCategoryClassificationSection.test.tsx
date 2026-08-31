import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as projectsApi from '../api/projects'
import type {
  ClassifyCategoriesRemoteEstimateOut,
  FineLabelCountOut,
  ProjectOut,
  RemoteCategoryClassificationRunSummary,
} from '../api/types'
import { RemoteCategoryClassificationSection } from './RemoteCategoryClassificationSection'

vi.mock('../api/projects')

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
    last_remote_category_classification_run: null,
    category_selection_enabled: true,
    cloud_vision_detection_enabled: true,
    cloud_vision_consent_at: '2026-08-21T10:00:00Z',
    ...overrides,
  }
}

function estimate(
  overrides: Partial<ClassifyCategoriesRemoteEstimateOut> = {}
): ClassifyCategoriesRemoteEstimateOut {
  return {
    candidate_count: 42,
    provider: 'anthropic',
    price_per_image_usd: 0.0045,
    estimated_cost_usd: 0.189,
    ...overrides,
  }
}

function runningRun(
  overrides: Partial<RemoteCategoryClassificationRunSummary> = {}
): RemoteCategoryClassificationRunSummary {
  return {
    status: 'running',
    started_at: '2026-08-23T10:00:00Z',
    finished_at: null,
    photos_total: 10,
    photos_processed: 4,
    error_message: null,
    ...overrides,
  }
}

function renderSection(initialProject: ProjectOut, refetchProject = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
  return render(
    <RemoteCategoryClassificationSection project={initialProject} refetchProject={refetchProject} />,
    { wrapper }
  )
}

describe('RemoteCategoryClassificationSection', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.triggerClassifyCategoriesRemote).mockReset()
    vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockReset()
    vi.mocked(projectsApi.listFineLabels).mockReset()
    vi.mocked(projectsApi.listFineLabels).mockResolvedValue([])
  })

  it('eagerly loads the estimate and shows candidate count + cost next to the trigger', async () => {
    vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())

    renderSection(project())

    await waitFor(() =>
      expect(projectsApi.getClassifyCategoriesRemoteEstimate).toHaveBeenCalledWith(1)
    )
    const summary = await screen.findByTestId('classify-categories-remote-estimate')
    expect(summary).toHaveTextContent(/42 fotos/i)
    expect(summary).toHaveTextContent(/\$0[.,]19/)
  })

  it('proactively disables the trigger and explains missing consent with a settings link', async () => {
    vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())

    renderSection(project({ cloud_vision_detection_enabled: false }))

    expect(
      screen.getByRole('button', { name: /remote-kategorisierung starten/i })
    ).toBeDisabled()
    expect(screen.getByText(/cloud-bilderkennung ist .* nicht aktiviert/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /projekteinstellungen/i })).toHaveAttribute(
      'href',
      '/projects/1/settings'
    )
  })

  it('shows "already classified" and disables the trigger when candidate_count is 0', async () => {
    vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(
      estimate({ candidate_count: 0, estimated_cost_usd: 0 })
    )

    renderSection(project())

    expect(
      await screen.findByTestId('classify-categories-remote-estimate')
    ).toHaveTextContent(/alle fotos bereits klassifiziert/i)
    expect(
      screen.getByRole('button', { name: /remote-kategorisierung starten/i })
    ).toBeDisabled()
  })

  it('opens a confirmation dialog with the estimate details on click', async () => {
    vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())
    const user = userEvent.setup()
    renderSection(project())

    await screen.findByTestId('classify-categories-remote-estimate')
    await user.click(screen.getByRole('button', { name: /remote-kategorisierung starten/i }))

    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/42 fotos werden an/i)).toBeInTheDocument()
    expect(within(dialog).getByText(/anthropic/i)).toBeInTheDocument()
    expect(within(dialog).getByText(/schätzung, keine exakte abrechnung/i)).toBeInTheDocument()
    expect(projectsApi.triggerClassifyCategoriesRemote).not.toHaveBeenCalled()
  })

  it('triggers the classification only after confirming the dialog', async () => {
    vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())
    vi.mocked(projectsApi.triggerClassifyCategoriesRemote).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderSection(project())

    await screen.findByTestId('classify-categories-remote-estimate')
    await user.click(screen.getByRole('button', { name: /remote-kategorisierung starten/i }))
    await user.click(screen.getByRole('button', { name: /^starten$/i }))

    expect(projectsApi.triggerClassifyCategoriesRemote).toHaveBeenCalledWith(1)
  })

  it('does not trigger anything when the dialog is cancelled', async () => {
    vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())
    const user = userEvent.setup()
    renderSection(project())

    await screen.findByTestId('classify-categories-remote-estimate')
    await user.click(screen.getByRole('button', { name: /remote-kategorisierung starten/i }))
    await user.click(screen.getByRole('button', { name: /abbrechen/i }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(projectsApi.triggerClassifyCategoriesRemote).not.toHaveBeenCalled()
  })

  it('re-enables the trigger and shows an error when the request itself fails', async () => {
    vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())
    vi.mocked(projectsApi.triggerClassifyCategoriesRemote).mockRejectedValue(
      new ApiError(500, 'Serverfehler')
    )
    const user = userEvent.setup()
    renderSection(project())

    await screen.findByTestId('classify-categories-remote-estimate')
    await user.click(screen.getByRole('button', { name: /remote-kategorisierung starten/i }))
    await user.click(screen.getByRole('button', { name: /^starten$/i }))

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /remote-kategorisierung starten/i })
      ).toBeEnabled()
    )
    expect(await screen.findByRole('alert')).toHaveTextContent('Serverfehler')
  })

  it('shows a busy button and progress while a run is in progress', () => {
    renderSection(
      project({ last_remote_category_classification_run: runningRun() })
    )

    expect(screen.getByRole('button', { name: /wird klassifiziert/i })).toBeDisabled()
    expect(screen.getByText(/4 von 10 fotos verarbeitet/i)).toBeInTheDocument()
    const progress = screen.getByRole('progressbar') as HTMLProgressElement
    expect(progress.max).toBe(10)
    expect(progress.value).toBe(4)
    expect(
      screen.queryByText(/fließen erst durch einen.*kriterien-bewertungs-lauf/i)
    ).not.toBeInTheDocument()
  })

  it('shows a failed status with a retry alert', () => {
    renderSection(
      project({
        last_remote_category_classification_run: runningRun({
          status: 'failed',
          error_message: 'Cloud-API nicht erreichbar.',
        }),
      })
    )

    expect(screen.getByText('Fehlgeschlagen')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Cloud-API nicht erreichbar.')
    expect(
      screen.queryByText(/fließen erst durch einen.*kriterien-bewertungs-lauf/i)
    ).not.toBeInTheDocument()
  })

  it('shows no hint text when there is no run yet', () => {
    renderSection(project({ last_remote_category_classification_run: null }))

    expect(
      screen.queryByText(/fließen erst durch einen.*kriterien-bewertungs-lauf/i)
    ).not.toBeInTheDocument()
  })

  it('shows a hint that results only flow into category suggestions via a criteria scoring run once the run succeeded', () => {
    renderSection(
      project({
        last_remote_category_classification_run: runningRun({
          status: 'success',
          finished_at: '2026-08-23T10:05:00Z',
          photos_processed: 10,
        }),
      })
    )

    expect(screen.getByText('Erfolgreich klassifiziert')).toBeInTheDocument()
    expect(
      screen.getByText(/fließen erst durch einen.*kriterien-bewertungs-lauf/i)
    ).toBeInTheDocument()
  })

  // specs/features/0289-feste-kategorien.md, Teststrategie Abschnitt 9 und UI/UX-Abschnitt
  // "Feinlabel-Haeufigkeitsliste": macht sichtbar, welche Kategorie im festen Set gegebenenfalls
  // fehlt - das Set ist geschlossen, aber nicht fuer immer festgelegt, und diese Liste ist der
  // Aenderungspfad.
  describe('Feinlabel-Häufigkeitsliste', () => {
    function fineLabel(overrides: Partial<FineLabelCountOut> = {}): FineLabelCountOut {
      return { canonical_key: 'bluete', display_name: 'Blüte', photo_count: 17, ...overrides }
    }

    it('shows the fine labels in the order the server delivered them, with their counts', async () => {
      vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())
      vi.mocked(projectsApi.listFineLabels).mockResolvedValue([
        fineLabel(),
        fineLabel({ canonical_key: 'urlaub', display_name: 'Urlaub', photo_count: 9 }),
        fineLabel({ canonical_key: 'geburtstag', display_name: 'Geburtstag', photo_count: 9 }),
      ])

      renderSection(project())

      await waitFor(() => expect(projectsApi.listFineLabels).toHaveBeenCalledWith(1))
      const list = await screen.findByRole('list', { name: 'Häufigste Feinlabels' })
      // Serverreihenfolge (photo_count absteigend, Tie-Break canonical_key) wird UNVERAENDERT
      // uebernommen - das Frontend sortiert bewusst nicht nach.
      expect(within(list).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
        'Blüte17 Mal',
        'Urlaub9 Mal',
        'Geburtstag9 Mal',
      ])
    })

    it('limits the list to the most frequent entries', async () => {
      vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())
      vi.mocked(projectsApi.listFineLabels).mockResolvedValue(
        Array.from({ length: 25 }, (_, index) =>
          fineLabel({
            canonical_key: `label-${index}`,
            display_name: `Label ${index}`,
            photo_count: 100 - index,
          })
        )
      )

      renderSection(project())

      const list = await screen.findByRole('list', { name: 'Häufigste Feinlabels' })
      expect(within(list).getAllByRole('listitem')).toHaveLength(15)
      // Gekuerzt wird am ENDE (die seltensten Eintraege fallen weg), nicht am Anfang.
      expect(within(list).getByText('Label 0')).toBeInTheDocument()
      expect(within(list).queryByText('Label 15')).toBeNull()
    })

    it('renders a fine label as plain text, never as markup', async () => {
      // Security-Muss-Kriterium (specs/features/0289-feste-kategorien.md, Abschnitt 3):
      // `display_name` ist freier, extern erzeugter LLM-Text.
      vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())
      vi.mocked(projectsApi.listFineLabels).mockResolvedValue([
        fineLabel({ canonical_key: 'x', display_name: '<img src=x onerror=alert(1)>' }),
      ])

      renderSection(project())

      const list = await screen.findByRole('list', { name: 'Häufigste Feinlabels' })
      expect(within(list).getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument()
      expect(list.querySelector('img')).toBeNull()
    })

    it('states the empty case instead of rendering an empty list', async () => {
      vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())
      vi.mocked(projectsApi.listFineLabels).mockResolvedValue([])

      renderSection(project())

      expect(await screen.findByText('Keine zusätzlichen Label ermittelt.')).toBeInTheDocument()
      expect(screen.queryByRole('list', { name: 'Häufigste Feinlabels' })).toBeNull()
    })

    it('announces the loading state', async () => {
      vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())
      vi.mocked(projectsApi.listFineLabels).mockReturnValue(new Promise(() => {}))

      renderSection(project())

      expect(await screen.findByText('Feinlabels werden geladen…')).toBeInTheDocument()
    })

    it('shows an inline alert with a retry that triggers a new request', async () => {
      const user = userEvent.setup()
      vi.mocked(projectsApi.getClassifyCategoriesRemoteEstimate).mockResolvedValue(estimate())
      vi.mocked(projectsApi.listFineLabels).mockRejectedValue(new ApiError(500, 'kaputt'))

      renderSection(project())

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent(/feinlabels konnten nicht geladen werden/i)

      vi.mocked(projectsApi.listFineLabels).mockResolvedValue([fineLabel()])
      await user.click(within(alert).getByRole('button', { name: /erneut versuchen/i }))

      expect(await screen.findByRole('list', { name: 'Häufigste Feinlabels' })).toBeInTheDocument()
    })
  })
})
