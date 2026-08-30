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
})
