import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as camerasApi from '../api/cameras'
import { ApiError } from '../api/client'
import * as projectsApi from '../api/projects'
import type { ProjectCameraOut, ProjectOut } from '../api/types'
import { ProjectSettingsPage } from './ProjectSettingsPage'

vi.mock('../api/projects')
vi.mock('../api/cameras')

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
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
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
    </QueryClientProvider>,
  )
}

function camera(overrides: Partial<ProjectCameraOut> = {}): ProjectCameraOut {
  return { id: 7, label: 'Canon EOS 5D', photo_count: 3, offset_minutes: 0, ...overrides }
}

describe('ProjectSettingsPage', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.getProject).mockReset()
    vi.mocked(projectsApi.setCloudVisionConsent).mockReset()
    vi.mocked(camerasApi.listCameras).mockReset()
    vi.mocked(camerasApi.listCameras).mockResolvedValue([])
  })

  it('shows a loading state while the project is being fetched', () => {
    vi.mocked(projectsApi.getProject).mockReturnValue(new Promise(() => {}))

    renderPage()

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('shows a not-found message for an unknown project', async () => {
    vi.mocked(projectsApi.getProject).mockRejectedValue(
      new ApiError(404, 'Projekt nicht gefunden.'),
    )

    renderPage()

    await screen.findByText('Projekt nicht gefunden.')
  })

  it('renders the toggle unchecked when consent is currently disabled', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderPage()

    const toggle = await screen.findByRole('switch', {
      name: /cloud-bilderkennung/i,
    })
    expect(toggle).toHaveAttribute('aria-checked', 'false')
  })

  it('renders the toggle checked when consent is currently enabled', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({
        cloud_vision_detection_enabled: true,
        cloud_vision_consent_at: '2026-08-21T10:00:00Z',
      }),
    )

    renderPage()

    const toggle = await screen.findByRole('switch', {
      name: /cloud-bilderkennung/i,
    })
    expect(toggle).toHaveAttribute('aria-checked', 'true')
  })

  it('enables the consent via the PUT endpoint when the toggle is switched on', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    vi.mocked(projectsApi.setCloudVisionConsent).mockResolvedValue({
      cloud_vision_detection_enabled: true,
      cloud_vision_consent_at: '2026-08-21T10:00:00Z',
    })

    renderPage()
    const toggle = await screen.findByRole('switch', {
      name: /cloud-bilderkennung/i,
    })
    await user.click(toggle)

    await waitFor(() => expect(projectsApi.setCloudVisionConsent).toHaveBeenCalledWith(1, true))
  })

  it('disables the consent via the PUT endpoint when an already-enabled toggle is switched off', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockResolvedValue(
      project({
        cloud_vision_detection_enabled: true,
        cloud_vision_consent_at: '2026-08-21T10:00:00Z',
      }),
    )
    vi.mocked(projectsApi.setCloudVisionConsent).mockResolvedValue({
      cloud_vision_detection_enabled: false,
      cloud_vision_consent_at: null,
    })

    renderPage()
    const toggle = await screen.findByRole('switch', {
      name: /cloud-bilderkennung/i,
    })
    await user.click(toggle)

    await waitFor(() => expect(projectsApi.setCloudVisionConsent).toHaveBeenCalledWith(1, false))
  })

  it('shows the info popover explaining the cloud processing when the info trigger is clicked', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())

    renderPage()
    const infoTrigger = await screen.findByRole('button', {
      name: /erkläre cloud-bilderkennung/i,
    })
    await user.click(infoTrigger)

    expect(await screen.findByText(/an die anthropic-cloud-api versendet/i)).toBeInTheDocument()
  })

  it('disables the toggle while the consent update is in flight (busy-button pattern)', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    vi.mocked(projectsApi.setCloudVisionConsent).mockReturnValue(new Promise(() => {}))

    renderPage()
    const toggle = await screen.findByRole('switch', {
      name: /cloud-bilderkennung/i,
    })
    await user.click(toggle)

    expect(toggle).toBeDisabled()
  })

  // specs/features/0044-projekte-loeschen.md: Gefahrenzone am Seitenende.
  it('offers the delete action in a danger zone at the end of the page', async () => {
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    renderPage()

    expect(
      await screen.findByRole('heading', { name: 'Gefahrenzone', level: 2 }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Projekt löschen' })).toBeInTheDocument()
    expect(screen.getByText(/Die Original-Fotos auf OpenCloud bleiben unverändert/)).toBeVisible()
  })

  it('shows no message at all on a plain page load', async () => {
    // "Kein `Alert`, kein `role=\"alert\"` in der Gefahrenzone" wird sonst von nichts gehalten -
    // eine Gefahrenzone ist ein dauerhafter Abschnitt, keine Meldung.
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    renderPage()

    await screen.findByRole('heading', { name: 'Gefahrenzone', level: 2 })
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('opens the confirmation dialog when the delete button is clicked', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Projekt löschen' }))

    const dialog = await screen.findByRole('dialog')
    expect(dialog).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Projekt löschen?' })).toBeInTheDocument()
  })

  it('forgets the typed confirmation when the dialog is closed and reopened', async () => {
    // Copilot-Fund (PR #351): der Dialog wurde unabhaengig von seinem Offen-Zustand gerendert und
    // blieb damit gemountet - wer den Namen einmal vollstaendig tippte und abbrach, fand die
    // Loeschen-Schaltflaeche beim naechsten Oeffnen SOFORT freigeschaltet. Genau die Reibung, die
    // der Zweck der Konstruktion ist, war damit weg - an der gefaehrlichsten Stelle des Produkts.
    const user = userEvent.setup()
    vi.mocked(projectsApi.getProject).mockResolvedValue(project())
    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Projekt löschen' }))
    const firstDialog = within(await screen.findByRole('dialog'))
    await user.type(
      firstDialog.getByLabelText(/Projektnamen zur Bestätigung eintippen/),
      'Costa Rica',
    )
    expect(firstDialog.getByRole('button', { name: 'Projekt löschen' })).toBeEnabled()

    await user.click(firstDialog.getByRole('button', { name: 'Abbrechen' }))
    expect(screen.queryByRole('dialog')).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Projekt löschen' }))

    const reopened = within(await screen.findByRole('dialog'))
    expect(reopened.getByLabelText(/Projektnamen zur Bestätigung eintippen/)).toHaveValue('')
    expect(reopened.getByRole('button', { name: 'Projekt löschen' })).toBeDisabled()
    expect(projectsApi.deleteProject).not.toHaveBeenCalled()
  })

  // specs/features/0426-zeitversatz-je-kamera.md, UI/UX Punkt 1.
  describe('Abschnitt "Kameras und Zeitversatz"', () => {
    it('zeigt je Kamera Bezeichnung, Fotoanzahl und geltenden Versatz', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(project())
      vi.mocked(camerasApi.listCameras).mockResolvedValue([
        camera(),
        camera({ id: 9, label: 'Apple iPhone 15', photo_count: 1, offset_minutes: -120 }),
      ])
      renderPage()

      const canon = within((await screen.findByText('Canon EOS 5D')).closest('li') as HTMLElement)
      expect(canon.getByText(/3 Fotos/)).toBeInTheDocument()
      // Eine "0:00" liest sich wie ein gesetzter Wert - die Liste nennt das Wort.
      expect(canon.getByText(/kein Versatz/)).toBeInTheDocument()

      const phone = within(
        (await screen.findByText('Apple iPhone 15')).closest('li') as HTMLElement,
      )
      expect(phone.getByText(/1 Foto\b/)).toBeInTheDocument()
      expect(phone.getByText(/−2:00/)).toBeInTheDocument()
    })

    it('haelt die Reihenfolge des Servers', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(project())
      vi.mocked(camerasApi.listCameras).mockResolvedValue([
        camera({ id: 9, label: 'Apple iPhone 15' }),
        camera({ id: 7, label: 'Canon EOS 5D' }),
      ])
      renderPage()

      await screen.findByText('Apple iPhone 15')
      const labels = screen
        .getAllByRole('listitem')
        .map((item) => item.querySelector('span')?.textContent)

      expect(labels).toEqual(['Apple iPhone 15', 'Canon EOS 5D'])
    })

    it('zeigt einen Ladezustand, solange die Kameras geladen werden', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(project())
      vi.mocked(camerasApi.listCameras).mockReturnValue(new Promise(() => {}))
      renderPage()

      expect(
        await screen.findByRole('status', { name: 'Kameras werden geladen' }),
      ).toBeInTheDocument()
    })

    it('erklaert den leeren Zustand ohne Fehlerton', async () => {
      // Dass ein Projekt noch keine Kamera kennt, ist der Normalfall vor dem ersten Scan - kein
      // `Alert`, kein `role="alert"`.
      vi.mocked(projectsApi.getProject).mockResolvedValue(project())
      vi.mocked(camerasApi.listCameras).mockResolvedValue([])
      renderPage()

      expect(await screen.findByText(/noch keine Kamera bekannt/)).toBeInTheDocument()
      expect(screen.queryByRole('alert')).toBeNull()
      expect(screen.queryByRole('listitem')).toBeNull()
    })

    it('oeffnet den Versatz-Dialog fuer genau diese Kamera', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(project())
      vi.mocked(camerasApi.listCameras).mockResolvedValue([camera()])
      const user = userEvent.setup()
      renderPage()

      await user.click(await screen.findByRole('button', { name: 'Versatz ändern' }))

      expect(await screen.findByRole('dialog')).toHaveAccessibleName(
        expect.stringContaining('Canon EOS 5D'),
      )
    })

    it('meldet einen Ladefehler der Kameraliste', async () => {
      vi.mocked(projectsApi.getProject).mockResolvedValue(project())
      vi.mocked(camerasApi.listCameras).mockRejectedValue(new ApiError(500, 'Serverfehler.'))
      renderPage()

      expect(await screen.findByText('Serverfehler.')).toBeInTheDocument()
    })
  })
})
