import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import * as projectsApi from '../api/projects'
import type { CriterionScoringRunSummary, ProjectOut } from '../api/types'
import {
  DEFAULT_SELECTION_TARGET,
  SAVED_HINT_MS,
  SELECTION_TARGET_LOCKED_TEXT,
  SelectionTargetField,
} from './SelectionTargetField'

vi.mock('../api/projects')

// Bewusst != 150: die Zahl im Standard-Hinweis muss aus der Serverantwort stammen, nicht aus
// einer im Frontend verdrahteten Konstante.
const SERVER_DEFAULT = 42

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
    effective_selection_target: SERVER_DEFAULT,
    has_selection_proposal: true,
    photo_count: 0,
    taken_at_earliest: null,
    taken_at_latest: null,
    ...overrides,
  }
}

function renderField(initialProject: ProjectOut) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrap = (element: ReactElement) => (
    <QueryClientProvider client={queryClient}>{element}</QueryClientProvider>
  )
  const view = render(wrap(<SelectionTargetField project={initialProject} />))
  return {
    rerenderWith: (next: ProjectOut) =>
      view.rerender(wrap(<SelectionTargetField project={next} />)),
  }
}

const FIELD = /richtwert \(bilder\)/i
const RESET = { name: 'Auf Standard zurücksetzen' }

describe('SelectionTargetField', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(projectsApi.setSelectionTarget).mockResolvedValue(project())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Standard und eigene Angabe', () => {
    it('leaves the field empty without an own setting and names the server default', () => {
      renderField(project())

      const input = screen.getByLabelText(FIELD) as HTMLInputElement
      expect(input.value).toBe('')
      expect(input).toHaveAttribute('placeholder', String(DEFAULT_SELECTION_TARGET))
      expect(input).toHaveAccessibleDescription(`Standard: ${SERVER_DEFAULT} Bilder.`)
      expect(screen.queryByRole('button', RESET)).not.toBeInTheDocument()
    })

    it('shows an own setting, says so and offers the way back to the default', () => {
      renderField(project({ selection_target: 80, effective_selection_target: 80 }))

      const input = screen.getByLabelText(FIELD) as HTMLInputElement
      expect(input.value).toBe('80')
      expect(input).toHaveAccessibleDescription(
        `Eigene Angabe – Standard wäre ${DEFAULT_SELECTION_TARGET} Bilder.`,
      )
      // Trefferfläche über die `tap-target`-Aufspannung des Buttons; sichtbare 44px bleiben
      // nach dem Design-Vertrag den heißen Pfaden vorbehalten.
      expect(screen.getByRole('button', RESET).className).toContain('tap-target')
    })

    it('never mentions the former tenth of the photo count', () => {
      renderField(project())
      expect(document.body.textContent).not.toMatch(/zehntel/i)
    })
  })

  describe('Speichern', () => {
    it('saves on blur', async () => {
      const user = userEvent.setup()
      renderField(project())

      await user.type(screen.getByLabelText(FIELD), '150')
      await user.tab()

      await waitFor(() => {
        expect(projectsApi.setSelectionTarget).toHaveBeenCalledWith(1, 150)
      })
    })

    it('saves on Enter', async () => {
      const user = userEvent.setup()
      renderField(project())

      await user.type(screen.getByLabelText(FIELD), '150{Enter}')

      await waitFor(() => {
        expect(projectsApi.setSelectionTarget).toHaveBeenCalledWith(1, 150)
      })
    })

    it('does not save on every keystroke', async () => {
      const user = userEvent.setup()
      renderField(project())

      await user.type(screen.getByLabelText(FIELD), '150')

      expect(projectsApi.setSelectionTarget).not.toHaveBeenCalled()
    })

    it('does not call the endpoint for an unchanged value', async () => {
      const user = userEvent.setup()
      renderField(project({ selection_target: 150, effective_selection_target: 150 }))

      await user.click(screen.getByLabelText(FIELD))
      await user.tab()

      expect(projectsApi.setSelectionTarget).not.toHaveBeenCalled()
    })

    it('sends null when the field is cleared', async () => {
      const user = userEvent.setup()
      renderField(project({ selection_target: 150, effective_selection_target: 150 }))

      await user.clear(screen.getByLabelText(FIELD))
      await user.tab()

      await waitFor(() => {
        expect(projectsApi.setSelectionTarget).toHaveBeenCalledWith(1, null)
      })
    })

    it('does not clamp a typed value - the endpoint decides', async () => {
      const user = userEvent.setup()
      renderField(project())

      const input = screen.getByLabelText(FIELD)
      await user.type(input, '99999')
      await user.tab()

      expect((input as HTMLInputElement).value).toBe('99999')
      await waitFor(() => {
        expect(projectsApi.setSelectionTarget).toHaveBeenCalledWith(1, 99999)
      })
    })

    it('keeps the field narrow and marks it as a number field with a lower bound', () => {
      renderField(project())

      const field = screen.getByLabelText(FIELD)
      expect(field).toHaveAttribute('type', 'number')
      expect(field).toHaveAttribute('min', '1')
      expect(field.className).toContain('w-24')
    })

    it('keeps the field usable while saving and only holds the reset button', async () => {
      /* Zustand „Speichert gerade": kein Spinner am Feld, Zurücksetzen nach dem Busy-Muster. */
      const user = userEvent.setup()
      let resolveSave: ((value: ProjectOut) => void) | undefined
      vi.mocked(projectsApi.setSelectionTarget).mockReturnValue(
        new Promise<ProjectOut>((resolve) => {
          resolveSave = resolve
        }),
      )
      renderField(project({ selection_target: 80, effective_selection_target: 80 }))

      const input = screen.getByLabelText(FIELD)
      await user.clear(input)
      await user.type(input, '90')
      await user.tab()

      await waitFor(() => {
        expect(screen.getByRole('button', RESET)).toBeDisabled()
      })
      expect(input).toBeEnabled()

      resolveSave?.(project({ selection_target: 90, effective_selection_target: 90 }))
      await waitFor(() => {
        expect(screen.getByRole('button', RESET)).toBeEnabled()
      })
    })

    it('serializes saving: a value typed while saving waits, survives the answer and is sent after', async () => {
      /* Zwei parallele Speichervorgänge könnten in vertauschter Reihenfolge ankommen und den
       * älteren Wert festschreiben. Und eine Eingabe verschwindet nie stillschweigend - auch
       * nicht, wenn die Antwort des vorigen Speicherns den gespeicherten Wert ändert. */
      const user = userEvent.setup()
      const resolvers: ((value: ProjectOut) => void)[] = []
      vi.mocked(projectsApi.setSelectionTarget).mockImplementation(
        () => new Promise<ProjectOut>((resolve) => resolvers.push(resolve)),
      )
      const { rerenderWith } = renderField(
        project({ selection_target: 80, effective_selection_target: 80 }),
      )

      const input = screen.getByLabelText(FIELD) as HTMLInputElement
      await user.clear(input)
      await user.type(input, '90')
      await user.tab()
      await waitFor(() => expect(projectsApi.setSelectionTarget).toHaveBeenCalledTimes(1))

      await user.clear(input)
      await user.type(input, '95')
      await user.tab()
      await user.clear(input)
      await user.type(input, '96')
      await user.tab()
      expect(projectsApi.setSelectionTarget).toHaveBeenCalledTimes(1)

      const saved90 = project({ selection_target: 90, effective_selection_target: 90 })
      resolvers[0]?.(saved90)
      rerenderWith(saved90)

      expect(input.value).toBe('96')
      await waitFor(() => expect(projectsApi.setSelectionTarget).toHaveBeenCalledTimes(2))
      expect(projectsApi.setSelectionTarget).toHaveBeenLastCalledWith(1, 96)

      const saved96 = project({ selection_target: 96, effective_selection_target: 96 })
      resolvers[1]?.(saved96)
      rerenderWith(saved96)
      await waitFor(() => expect(screen.getByText(/vorschlag neu berechnet/i)).toBeInTheDocument())
      expect(input.value).toBe('96')
      expect(projectsApi.setSelectionTarget).toHaveBeenCalledTimes(2)
    })

    it('does not resend a value typed while saving if it equals the value just saved', async () => {
      const user = userEvent.setup()
      let resolveSave: ((value: ProjectOut) => void) | undefined
      vi.mocked(projectsApi.setSelectionTarget).mockReturnValue(
        new Promise<ProjectOut>((resolve) => {
          resolveSave = resolve
        }),
      )
      const { rerenderWith } = renderField(
        project({ selection_target: 80, effective_selection_target: 80 }),
      )

      const input = screen.getByLabelText(FIELD) as HTMLInputElement
      await user.clear(input)
      await user.type(input, '90')
      await user.tab()
      await user.click(input)
      await user.tab()

      const saved90 = project({ selection_target: 90, effective_selection_target: 90 })
      resolveSave?.(saved90)
      rerenderWith(saved90)

      await waitFor(() => expect(screen.getByText(/vorschlag neu berechnet/i)).toBeInTheDocument())
      expect(projectsApi.setSelectionTarget).toHaveBeenCalledTimes(1)
      expect(input.value).toBe('90')
    })

    it('still takes over a value changed elsewhere while nothing was typed', () => {
      const { rerenderWith } = renderField(
        project({ selection_target: 80, effective_selection_target: 80 }),
      )

      rerenderWith(project({ selection_target: 120, effective_selection_target: 120 }))

      expect((screen.getByLabelText(FIELD) as HTMLInputElement).value).toBe('120')
    })

    it('confirms a recomputation after a run and takes the confirmation back again', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true })
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
      renderField(project())

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

    it('before the first run claims no recomputation but validity for the next proposal', async () => {
      const user = userEvent.setup()
      renderField(project({ last_criterion_scoring_run: null, has_selection_proposal: false }))

      await user.type(screen.getByLabelText(FIELD), '120')
      await user.tab()

      await waitFor(() => {
        expect(screen.getByLabelText(FIELD)).toHaveAccessibleDescription(
          `Standard: ${SERVER_DEFAULT} Bilder. Gilt für den nächsten Vorschlag.`,
        )
      })
      expect(screen.queryByText(/neu berechnet/i)).not.toBeInTheDocument()
    })

    it('after success then failure still confirms the recomputation of the existing proposal', async () => {
      /* Der neueste Lauf ist gescheitert, ein früherer erfolgreich: der `PUT` rechnet dessen
       * Vorschlag neu. Maßgeblich ist `has_selection_proposal`, nicht der Status des neuesten. */
      const user = userEvent.setup()
      renderField(
        project({
          last_criterion_scoring_run: criterionScoringRun({ status: 'failed' }),
          has_selection_proposal: true,
        }),
      )

      await user.type(screen.getByLabelText(FIELD), '120')
      await user.tab()

      await waitFor(() => {
        expect(screen.getByText(/vorschlag neu berechnet/i)).toBeInTheDocument()
      })
      expect(screen.queryByText(/nächsten Vorschlag/i)).not.toBeInTheDocument()
    })
  })

  describe('Auf Standard zurücksetzen', () => {
    it('sends literally null, empties the field and keeps the focus in the field', async () => {
      const user = userEvent.setup()
      renderField(project({ selection_target: 80, effective_selection_target: 80 }))

      await user.click(screen.getByRole('button', RESET))

      await waitFor(() => {
        expect(projectsApi.setSelectionTarget).toHaveBeenCalledWith(1, null)
      })
      const input = screen.getByLabelText(FIELD) as HTMLInputElement
      expect(input.value).toBe('')
      expect(input).toHaveFocus()
      expect(projectsApi.setSelectionTarget).toHaveBeenCalledTimes(1)
    })

    it('returns to the default state once the server answers with null', () => {
      const { rerenderWith } = renderField(
        project({ selection_target: 80, effective_selection_target: 80 }),
      )

      rerenderWith(project())

      expect((screen.getByLabelText(FIELD) as HTMLInputElement).value).toBe('')
      expect(screen.queryByRole('button', RESET)).not.toBeInTheDocument()
      expect(screen.getByLabelText(FIELD)).toHaveAccessibleDescription(
        `Standard: ${SERVER_DEFAULT} Bilder.`,
      )
    })
  })

  describe('Sperre während der Klassifizierung', () => {
    const running = () =>
      project({
        selection_target: 80,
        effective_selection_target: 80,
        last_criterion_scoring_run: criterionScoringRun({ status: 'running', finished_at: null }),
      })

    it('disables field and reset and names the reason at the field', () => {
      renderField(running())

      const input = screen.getByLabelText(FIELD)
      expect(input).toBeDisabled()
      expect(screen.getByRole('button', RESET)).toBeDisabled()
      expect(input).toHaveAccessibleDescription(
        `Eigene Angabe – Standard wäre ${DEFAULT_SELECTION_TARGET} Bilder. ${SELECTION_TARGET_LOCKED_TEXT}`,
      )
      expect(SELECTION_TARGET_LOCKED_TEXT).toMatch(/klassifizierung/i)
    })

    it('keeps an unsaved input across the lock and frees the field without reloading', async () => {
      const user = userEvent.setup()
      const idle = project({ selection_target: 80, effective_selection_target: 80 })
      const { rerenderWith } = renderField(idle)

      const input = screen.getByLabelText(FIELD) as HTMLInputElement
      await user.clear(input)
      await user.type(input, '95')

      rerenderWith(running())
      expect(input).toBeDisabled()
      expect(input.value).toBe('95')

      rerenderWith(idle)
      expect(input).toBeEnabled()
      expect(input.value).toBe('95')
      expect(screen.queryByText(SELECTION_TARGET_LOCKED_TEXT)).not.toBeInTheDocument()
    })
  })

  describe('Fehler', () => {
    it.each([
      [409, 'Fuer dieses Projekt laeuft gerade eine Klassifizierung.'],
      [422, 'Ungueltiger Richtwert.'],
      [500, 'Interner Fehler.'],
    ])('shows an alert and keeps the typed value on %i', async (status, detail) => {
      const user = userEvent.setup()
      vi.mocked(projectsApi.setSelectionTarget).mockRejectedValue(new ApiError(status, detail))
      renderField(project())

      await user.type(screen.getByLabelText(FIELD), '150')
      await user.tab()

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Richtwert nicht gespeichert')
      expect(alert).toHaveTextContent(detail)
      expect((screen.getByLabelText(FIELD) as HTMLInputElement).value).toBe('150')
    })

    it('falls back to a fixed text without a server detail', async () => {
      const user = userEvent.setup()
      vi.mocked(projectsApi.setSelectionTarget).mockRejectedValue(new Error('netz'))
      renderField(project())

      await user.type(screen.getByLabelText(FIELD), '150')
      await user.tab()

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Der Richtwert konnte nicht gespeichert werden.',
      )
    })

    it('takes the error back once the field holds the stored value again', async () => {
      const user = userEvent.setup()
      vi.mocked(projectsApi.setSelectionTarget).mockRejectedValue(
        new ApiError(409, 'Fuer dieses Projekt laeuft gerade eine Klassifizierung.'),
      )
      renderField(project({ selection_target: 150, effective_selection_target: 150 }))

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
  })
})
