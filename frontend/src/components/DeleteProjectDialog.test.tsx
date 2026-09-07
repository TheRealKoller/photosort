import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DeleteProjectDialog, isExactProjectNameMatch } from './DeleteProjectDialog'
import { ApiError } from '../api/client'
import * as projectsApi from '../api/projects'

vi.mock('../api/projects')

/*
 * specs/features/0044-projekte-loeschen.md, Teststrategie "Frontend".
 *
 * Selektiert wird ueber `getByRole('dialog')` - ein natives `<dialog aria-modal>` traegt die Rolle
 * `dialog`, NICHT `alertdialog`. Fokusfalle, Erstfokus, Fokusrueckgabe und Scroll-Sperre werden
 * hier bewusst NICHT wiederholt (sie liegen in `ui/dialog.test.tsx`), und keine Assertion
 * behauptet echte Modalitaet oder `::backdrop` - beides ist in jsdom nur polyfillt.
 */

const PROJECT_NAME = 'Costa Rica 2019'

function LocationProbe() {
  const location = useLocation()
  return <span data-testid="location">{location.pathname}</span>
}

function renderDialog(props: { projectId?: number; projectName?: string } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const onClose = vi.fn()

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/projects/1/settings']}>
          <LocationProbe />
          <Routes>
            <Route path="/projects/1/settings" element={<>{children}</>} />
            <Route path="/projects" element={<span>Projektliste</span>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )
  }

  render(
    <DeleteProjectDialog
      open
      onClose={onClose}
      projectId={props.projectId ?? 1}
      projectName={props.projectName ?? PROJECT_NAME}
    />,
    { wrapper: Wrapper }
  )
  return { onClose, queryClient }
}

function confirmationField() {
  return screen.getByLabelText(/Projektnamen zur Bestätigung eintippen/)
}

function currentPath(): string {
  // Bewusst ein EXAKTER Vergleich und kein `toHaveTextContent`: '/projects' ist ein Teilstring von
  // '/projects/1/settings', eine Teilstring-Assertion waere hier trivial erfuellt und bewiese
  // weder die erfolgte noch die unterbliebene Navigation.
  return screen.getByTestId('location').textContent ?? ''
}

function deleteButton() {
  return screen.getByRole('button', { name: /Projekt löschen|Wird gelöscht/ })
}

beforeEach(() => {
  vi.mocked(projectsApi.deleteProject).mockReset()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('isExactProjectNameMatch', () => {
  /*
   * Ausgelagert und einzeln geprueft, weil genau das der Zweck ist: ein spaeterer
   * `trim()`/`toLowerCase()`-Refactor MUSS hier einen Test brechen. Der Vergleich ist bewusst
   * exakt - anders als serverseitig, wo getrimmt wird.
   */
  it.each([
    [PROJECT_NAME, PROJECT_NAME, true],
    [` ${PROJECT_NAME}`, PROJECT_NAME, false],
    [`${PROJECT_NAME} `, PROJECT_NAME, false],
    ['costa rica 2019', PROJECT_NAME, false],
    ['COSTA RICA 2019', PROJECT_NAME, false],
    ['', PROJECT_NAME, false],
    ['Costa', PROJECT_NAME, false],
    [' Rand ', ' Rand ', true],
  ])('isExactProjectNameMatch(%o, %o) === %s', (input, projectName, expected) => {
    expect(isExactProjectNameMatch(input, projectName)).toBe(expected)
  })
})

describe('DeleteProjectDialog', () => {
  it('shows the project name to type and the confirmation field', () => {
    renderDialog()

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Projekt löschen?' })).toBeInTheDocument()
    expect(screen.getByText('Diese Aktion kann nicht rückgängig gemacht werden.')).toBeVisible()
    expect(screen.getByText(PROJECT_NAME)).toBeVisible()
    expect(confirmationField()).toBeInTheDocument()
  })

  it('carries the input attributes without which the button never unlocks on mobile', () => {
    renderDialog()

    const field = confirmationField()
    expect(field).toHaveAttribute('autocomplete', 'off')
    expect(field).toHaveAttribute('autocapitalize', 'off')
    expect(field).toHaveAttribute('autocorrect', 'off')
    expect(field).toHaveAttribute('spellcheck', 'false')
  })

  it('unlocks the delete button only for an exact match', async () => {
    const user = userEvent.setup()
    renderDialog()

    expect(deleteButton()).toBeDisabled()

    await user.type(confirmationField(), PROJECT_NAME)
    expect(deleteButton()).toBeEnabled()

    await user.type(confirmationField(), '{backspace}')
    expect(deleteButton()).toBeDisabled()
  })

  it('does not submit on Enter (the dialog content is no form)', async () => {
    const user = userEvent.setup()
    renderDialog()

    await user.type(confirmationField(), `${PROJECT_NAME}{Enter}`)

    expect(projectsApi.deleteProject).not.toHaveBeenCalled()
  })

  it('deletes with the typed name, closes and navigates to the project list', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.deleteProject).mockResolvedValue(undefined)
    const { onClose } = renderDialog()

    await user.type(confirmationField(), PROJECT_NAME)
    await user.click(deleteButton())

    await waitFor(() => expect(currentPath()).toBe('/projects'))
    expect(projectsApi.deleteProject).toHaveBeenCalledWith(1, PROJECT_NAME)
    expect(onClose).toHaveBeenCalled()
  })

  it('disables field, delete and cancel while the request is running and ignores Escape', async () => {
    const user = userEvent.setup()
    let resolveDelete: (() => void) | undefined
    vi.mocked(projectsApi.deleteProject).mockReturnValue(
      new Promise<void>((resolve) => {
        resolveDelete = resolve
      })
    )
    const { onClose } = renderDialog()

    await user.type(confirmationField(), PROJECT_NAME)
    await user.click(deleteButton())

    await waitFor(() => expect(deleteButton()).toBeDisabled())
    expect(screen.getByRole('button', { name: 'Wird gelöscht…' })).toBeDisabled()
    expect(confirmationField()).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Abbrechen' })).toBeDisabled()

    // Eigener Fall: dass Esc nicht schliesst, ist KEINE Eigenschaft des Grundelements (dort ruft
    // Esc immer `onClose`), sondern eine Zusage dieses Aufrufers.
    // Am Dialog selbst ausgeloest statt ueber die Tastatur: waehrend der laufenden Anfrage ist
    // JEDES Bedienelement im Dialog deaktiviert, der Fokus liegt also auf dem <body> - ein
    // `user.keyboard` erreichte den Handler gar nicht und die Assertion darunter waere wertlos.
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()

    resolveDelete?.()
  })

  it('keeps field and button usable after a 409 and repeats on a second click', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.deleteProject).mockRejectedValue(
      new ApiError(409, 'Für dieses Projekt läuft gerade ein Vorgang.')
    )
    renderDialog()

    await user.type(confirmationField(), PROJECT_NAME)
    await user.click(deleteButton())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveAttribute('data-alert-variant', 'warning')
    expect(alert).toHaveTextContent('Für dieses Projekt läuft gerade ein Vorgang.')
    expect(confirmationField()).toBeEnabled()
    expect(confirmationField()).toHaveValue(PROJECT_NAME)
    expect(deleteButton()).toBeEnabled()

    await user.click(deleteButton())
    await waitFor(() => expect(projectsApi.deleteProject).toHaveBeenCalledTimes(2))
  })

  it('sets no further request of its own after a 409, not even after a minute', async () => {
    // Bewusst mit `fireEvent` statt `userEvent`: userEvent wartet intern auf echte Timer, was sich
    // mit den hier noetigen Fake-Timern beisst. Gebraucht wird nur der Zustand "409 steht", nicht
    // eine realistische Tippfolge - die deckt der Test darueber ab.
    vi.useFakeTimers()
    vi.mocked(projectsApi.deleteProject).mockRejectedValue(new ApiError(409, 'Ein Lauf läuft.'))
    renderDialog()

    fireEvent.change(confirmationField(), { target: { value: PROJECT_NAME } })
    fireEvent.click(deleteButton())
    await vi.waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())

    await vi.advanceTimersByTimeAsync(60_000)

    // Kein automatisches Polling, kein Timer: weder ein zweites DELETE noch ein Nachladen des
    // Projekts. Der Nutzer wartet den Lauf ab und drueckt selbst erneut.
    expect(projectsApi.deleteProject).toHaveBeenCalledTimes(1)
    expect(projectsApi.getProject).not.toHaveBeenCalled()
  })

  it('locks the dialog after a 404 without navigating on its own', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.deleteProject).mockRejectedValue(
      new ApiError(404, 'Projekt nicht gefunden.')
    )
    const { onClose } = renderDialog()

    await user.type(confirmationField(), PROJECT_NAME)
    await user.click(deleteButton())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveAttribute('data-alert-variant', 'warning')
    expect(alert).toHaveTextContent('Dieses Projekt existiert nicht mehr')
    // Die Zusage "keine automatische Navigation" - ein reiner Klick-Test deckt sie nicht ab.
    expect(currentPath()).toBe('/projects/1/settings')
    expect(confirmationField()).toBeDisabled()
    expect(deleteButton()).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Zur Projektliste' }))
    expect(currentPath()).toBe('/projects')
    // Der Ausweg meldet dem Aufrufer AUCH das Schliessen, nicht nur die Navigation (Copilot-Fund,
    // PR #351): sonst bliebe der Dialog beim Aufrufer offen, und mit ihm der Zustand isGone - ein
    // spaeter erneut geoeffneter Dialog waere sofort gesperrt.
    expect(onClose).toHaveBeenCalled()
  })

  it('takes the same way out of a 404 via Escape', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.deleteProject).mockRejectedValue(
      new ApiError(404, 'Projekt nicht gefunden.')
    )
    const { onClose } = renderDialog()

    await user.type(confirmationField(), PROJECT_NAME)
    await user.click(deleteButton())
    await screen.findByRole('alert')

    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })

    expect(currentPath()).toBe('/projects')
    expect(onClose).toHaveBeenCalled()
  })

  it('marks the field invalid after a 400 and keeps the typed text', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.deleteProject).mockRejectedValue(new ApiError(400, 'Name stimmt nicht.'))
    renderDialog()

    await user.type(confirmationField(), PROJECT_NAME)
    await user.click(deleteButton())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveAttribute('data-alert-variant', 'error')
    expect(confirmationField()).toHaveAttribute('aria-invalid', 'true')
    expect(confirmationField()).toHaveValue(PROJECT_NAME)
    expect(deleteButton()).toBeEnabled()
  })

  it('shows an error alert on a network failure and stays usable', async () => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.deleteProject).mockRejectedValue(new Error('Network down'))
    renderDialog()

    await user.type(confirmationField(), PROJECT_NAME)
    await user.click(deleteButton())

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveAttribute('data-alert-variant', 'error')
    expect(confirmationField()).toHaveValue(PROJECT_NAME)
    expect(deleteButton()).toBeEnabled()
    expect(confirmationField()).not.toHaveAttribute('aria-invalid', 'true')
  })

  it.each([
    [409, 'Ein Lauf läuft.'],
    [404, 'Weg.'],
    [400, 'Name stimmt nicht.'],
    [500, 'Kaputt.'],
  ])('offers no second retry control for status %s', async (status, detail) => {
    const user = userEvent.setup()
    vi.mocked(projectsApi.deleteProject).mockRejectedValue(new ApiError(status, detail))
    renderDialog()

    await user.type(confirmationField(), PROJECT_NAME)
    await user.click(deleteButton())
    await screen.findByRole('alert')

    // Das Weglassen von `onRetry` ist eine bewusste Entscheidung und nur negativ pruefbar: die
    // Löschen-Schaltflaeche IST die Wiederholung.
    expect(screen.queryByRole('button', { name: 'Erneut versuchen' })).not.toBeInTheDocument()
  })
})
