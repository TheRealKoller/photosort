import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as opencloudApi from '../api/opencloud'
import * as projectsApi from '../api/projects'
import type { ProjectOut } from '../api/types'
import { ProjectCreatePage } from './ProjectCreatePage'

vi.mock('../api/projects')
vi.mock('../api/opencloud')

function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 42,
    name: 'Costa Rica',
    opencloud_drive_id: 'drive-1',
    opencloud_path: 'CostaRica',
    created_at: '2026-07-20T10:00:00Z',
    last_scan: null,
    last_scoring_run: null,
    last_criterion_scoring_run: null,
    category_selection_enabled: true,
    ...overrides,
  }
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return render(
    <MemoryRouter initialEntries={['/projects/new']}>
      <Routes>
        <Route path="/" element={<p>Projektliste-Seite</p>} />
        <Route path="/projects/new" element={<ProjectCreatePage />} />
        <Route path="/projects/:id" element={<ProjectDetailStub />} />
      </Routes>
    </MemoryRouter>,
    { wrapper }
  )
}

function ProjectDetailStub() {
  return <p>Projekt-Detail-Seite</p>
}

describe('ProjectCreatePage', () => {
  beforeEach(() => {
    vi.mocked(projectsApi.createProject).mockReset()
    vi.mocked(opencloudApi.browseFolder).mockReset()
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([])
  })

  it('loads the root level of the folder browser on mount', async () => {
    renderPage()

    await waitFor(() => expect(opencloudApi.browseFolder).toHaveBeenCalledWith(''))
  })

  it('blocks submit when the name is empty or only whitespace', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(screen.getByRole('button', { name: /projekt anlegen/i })).toBeDisabled()

    await user.type(screen.getByLabelText(/name/i), '   ')
    expect(screen.getByRole('button', { name: /projekt anlegen/i })).toBeDisabled()
  })

  it('submits name and the currently selected folder path, then navigates to the new project on success', async () => {
    vi.mocked(opencloudApi.browseFolder).mockResolvedValue([{ name: 'Sub', path: 'Sub' }])
    vi.mocked(projectsApi.createProject).mockResolvedValue(project({ id: 42 }))
    const user = userEvent.setup()

    renderPage()

    await user.type(screen.getByLabelText(/name/i), 'Costa Rica')
    await user.click(await screen.findByRole('button', { name: 'Sub' }))
    await user.click(screen.getByRole('button', { name: /projekt anlegen/i }))

    await waitFor(() =>
      expect(projectsApi.createProject).toHaveBeenCalledWith({
        name: 'Costa Rica',
        opencloud_path: 'Sub',
      })
    )
    expect(await screen.findByText('Projekt-Detail-Seite')).toBeInTheDocument()
  })

  it('disables the submit button while the request is pending (double-click protection)', async () => {
    let resolveCreate: (value: ProjectOut) => void = () => {}
    vi.mocked(projectsApi.createProject).mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve
      })
    )
    const user = userEvent.setup()

    renderPage()

    await user.type(screen.getByLabelText(/name/i), 'Costa Rica')
    const submitButton = screen.getByRole('button', { name: /projekt anlegen/i })
    await user.click(submitButton)

    expect(submitButton).toBeDisabled()
    expect(projectsApi.createProject).toHaveBeenCalledTimes(1)

    resolveCreate(project())
    await screen.findByText('Projekt-Detail-Seite')
  })

  it('shows the backend detail and keeps the form on a 409 name conflict without redirecting', async () => {
    vi.mocked(projectsApi.createProject).mockRejectedValue(
      new ApiError(409, "Projekt 'Costa Rica' existiert bereits.")
    )
    const user = userEvent.setup()

    renderPage()

    await user.type(screen.getByLabelText(/name/i), 'Costa Rica')
    await user.click(screen.getByRole('button', { name: /projekt anlegen/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Projekt 'Costa Rica' existiert bereits."
    )
    expect(screen.getByLabelText(/name/i)).toHaveValue('Costa Rica')
    expect(screen.queryByText('Projekt-Detail-Seite')).not.toBeInTheDocument()
  })

  it('shows the backend detail and keeps the form editable on a 400 invalid-folder error', async () => {
    vi.mocked(projectsApi.createProject).mockRejectedValue(
      new ApiError(400, 'Ordner nicht gefunden')
    )
    const user = userEvent.setup()

    renderPage()

    await user.type(screen.getByLabelText(/name/i), 'Costa Rica')
    await user.click(screen.getByRole('button', { name: /projekt anlegen/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Ordner nicht gefunden')
    expect(screen.getByLabelText(/name/i)).toBeEnabled()
    expect(screen.queryByText('Projekt-Detail-Seite')).not.toBeInTheDocument()
  })

  it('disables submit while the folder browser reports a load error', async () => {
    vi.mocked(opencloudApi.browseFolder).mockRejectedValue(new ApiError(400, 'kaputt'))
    const user = userEvent.setup()

    renderPage()

    await user.type(screen.getByLabelText(/name/i), 'Costa Rica')

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /projekt anlegen/i })).toBeDisabled()
    )
  })

  it('has a cancel link back to /', () => {
    renderPage()

    expect(screen.getByRole('link', { name: /abbrechen/i })).toHaveAttribute('href', '/')
  })
})
