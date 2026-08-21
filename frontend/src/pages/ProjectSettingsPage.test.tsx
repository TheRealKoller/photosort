import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as projectsApi from '../api/projects'
import type { ProjectOut } from '../api/types'
import { ProjectSettingsPage } from './ProjectSettingsPage'

vi.mock('../api/projects')

// specs/features/0047-sehenswuerdigkeit-erkennung-cloud-vision-api.md: erste dedizierte
// Projekteinstellungs-UI im Projekt - Toggle-Switch fuer die Cloud-Landmark-Einwilligung +
// Info-Popover (Muster: CriterionDetailsPopover.tsx, hier bewusst ohne dessen geraetespezifische
// Hover-Auto-Close-Logik - technische Detailentscheidung der Umsetzung, siehe
// ProjectSettingsPage.tsx-Kommentar, ein einzelner Einstellungs-Schalter braucht keine
// Hover-Ergonomie wie Dutzende Grid-Kacheln).

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

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/projects/1/settings']}>
        <Routes>
          <Route path="/projects/:projectId/settings" element={<ProjectSettingsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ProjectSettingsPage', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.getProject).mockReset()
    vi.mocked(projectsApi.setCloudLandmarkConsent).mockReset()
  })

  it('shows a loading state while the project is being fetched', () => {
    vi.mocked(projectsApi.getProject).mockReturnValue(new Promise(() => {}))

    renderPage()

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows a not-found message for an unknown project', async () => {
    vi.mocked(projectsApi.getProject).mockRejectedValue(
      new ApiError(404, 'Projekt nicht gefunden.')
    )

    renderPage()

    await screen.findByText('Projekt nicht gefunden.')
  })

  it('renders the toggle unchecked when consent is currently disabled', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderPage()

    const toggle = await screen.findByRole('switch', {
      name: /cloud-sehenswürdigkeit-erkennung/i,
    })
    expect(toggle).toHaveAttribute('aria-checked', 'false')
  })

  it('renders the toggle checked when consent is currently enabled', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({
        cloud_landmark_detection_enabled: true,
        cloud_landmark_consent_at: '2026-08-21T10:00:00Z',
      })
    )

    renderPage()

    const toggle = await screen.findByRole('switch', {
      name: /cloud-sehenswürdigkeit-erkennung/i,
    })
    expect(toggle).toHaveAttribute('aria-checked', 'true')
  })

  it('enables the consent via the PUT endpoint when the toggle is switched on', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    vi.mocked(projectsApi.setCloudLandmarkConsent).mockResolvedValue({
      cloud_landmark_detection_enabled: true,
      cloud_landmark_consent_at: '2026-08-21T10:00:00Z',
    })

    renderPage()
    const toggle = await screen.findByRole('switch', {
      name: /cloud-sehenswürdigkeit-erkennung/i,
    })
    await user.click(toggle)

    await waitFor(() =>
      expect(projectsApi.setCloudLandmarkConsent).toHaveBeenCalledWith(1, true)
    )
  })

  it('disables the consent via the PUT endpoint when an already-enabled toggle is switched off', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({
        cloud_landmark_detection_enabled: true,
        cloud_landmark_consent_at: '2026-08-21T10:00:00Z',
      })
    )
    vi.mocked(projectsApi.setCloudLandmarkConsent).mockResolvedValue({
      cloud_landmark_detection_enabled: false,
      cloud_landmark_consent_at: null,
    })

    renderPage()
    const toggle = await screen.findByRole('switch', {
      name: /cloud-sehenswürdigkeit-erkennung/i,
    })
    await user.click(toggle)

    await waitFor(() =>
      expect(projectsApi.setCloudLandmarkConsent).toHaveBeenCalledWith(1, false)
    )
  })

  it('shows the info popover explaining the cloud processing when the info trigger is clicked', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderPage()
    const infoTrigger = await screen.findByRole('button', {
      name: /erkläre cloud-sehenswürdigkeit-erkennung/i,
    })
    await user.click(infoTrigger)

    expect(
      await screen.findByText(/an die anthropic-cloud-api versendet/i)
    ).toBeInTheDocument()
  })

  it('disables the toggle while the consent update is in flight (busy-button pattern)', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    vi.mocked(projectsApi.setCloudLandmarkConsent).mockReturnValue(new Promise(() => {}))

    renderPage()
    const toggle = await screen.findByRole('switch', {
      name: /cloud-sehenswürdigkeit-erkennung/i,
    })
    await user.click(toggle)

    expect(toggle).toBeDisabled()
  })
})
