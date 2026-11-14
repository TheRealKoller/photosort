import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest'

import type { OperationOut } from '../api/types'
import { useCancelAllOperations, useOperationsQuery } from '../hooks/useOperations'
import { ProjectOperationsBar } from './ProjectOperationsBar'

vi.mock('../hooks/useOperations', () => ({
  useOperationsQuery: vi.fn(),
  useCancelAllOperations: vi.fn(),
}))

const SCAN: OperationOut = {
  kind: 'scan',
  run_id: 4,
  label: 'Scan',
  status: 'running',
  cancel_requested: false,
}
const EXPORT: OperationOut = {
  kind: 'export',
  run_id: 9,
  label: 'Export',
  status: 'queued',
  cancel_requested: false,
}
const REVIEW: OperationOut = {
  kind: 'review',
  run_id: 2,
  label: 'Prüfung',
  status: 'running',
  cancel_requested: false,
}

interface CancelAllState {
  mutate: Mock
  isPending: boolean
  isError: boolean
}

let cancelAll: CancelAllState

function setOperations(operations: OperationOut[] | undefined): void {
  vi.mocked(useOperationsQuery).mockReturnValue({
    data: operations === undefined ? undefined : { operations },
  } as never)
}

function setCancelAll(overrides: Partial<CancelAllState> = {}): void {
  cancelAll = { mutate: vi.fn(), isPending: false, isError: false, ...overrides }
  vi.mocked(useCancelAllOperations).mockReturnValue(cancelAll as never)
}

function trigger(): HTMLElement {
  return screen.getByRole('button', { name: 'Alle abbrechen' })
}

describe('ProjectOperationsBar (Spec 0641)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setCancelAll()
  })

  it.each([
    ['noch nicht geladen', undefined],
    ['leer', []],
  ] as const)('rendert nichts, solange die Liste %s ist', (_, operations) => {
    setOperations(operations === undefined ? undefined : [...operations])

    const { container } = render(<ProjectOperationsBar projectId={1} />)

    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('nennt ab einem Vorgang die Namen in der Statuszeile und bietet "Alle abbrechen"', () => {
    setOperations([SCAN, EXPORT])

    render(<ProjectOperationsBar projectId={1} />)

    expect(screen.getByRole('status')).toHaveTextContent('Läuft oder wartet: Scan, Export')
    expect(trigger()).toBeEnabled()
    expect(trigger()).not.toHaveClass('bg-danger')
  })

  it('sperrt "Alle abbrechen", sobald jeder Vorgang schon einen Abbruch angefordert hat', () => {
    setOperations([
      { ...SCAN, cancel_requested: true },
      { ...EXPORT, cancel_requested: true },
    ])

    render(<ProjectOperationsBar projectId={1} />)

    expect(trigger()).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Wird abgebrochen: Scan, Export')
  })

  it('nennt im Dialog Anzahl, Namen und läuft/wartet; Erstfokus auf "Weiterlaufen lassen"', async () => {
    setOperations([SCAN, EXPORT, REVIEW])
    const user = userEvent.setup()
    render(<ProjectOperationsBar projectId={1} />)

    await user.click(trigger())

    const dialog = screen.getByRole('dialog', { name: 'Alle Vorgänge abbrechen?' })
    expect(dialog).toHaveAccessibleDescription('3 Vorgänge werden angehalten:')
    const items = within(dialog)
      .getAllByRole('listitem')
      .map((item) => item.textContent)
    expect(items).toEqual(['Scan — läuft', 'Export — wartet', 'Prüfung — läuft'])
    expect(
      within(dialog).getByText(
        'Was bis jetzt fertig ist, bleibt erhalten. Ein gerade begonnenes Foto wird noch abgeschlossen.',
      ),
    ).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Weiterlaufen lassen' })).toHaveFocus()
    // Kein Verwerfen angeboten: nur Weiterlaufen und Alle abbrechen.
    expect(
      within(dialog)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual(['Weiterlaufen lassen', 'Alle abbrechen'])
    expect(cancelAll.mutate).not.toHaveBeenCalled()
  })

  it('beugt die Beschreibung für genau einen Vorgang', async () => {
    setOperations([EXPORT])
    const user = userEvent.setup()
    render(<ProjectOperationsBar projectId={1} />)

    await user.click(trigger())

    expect(screen.getByRole('dialog')).toHaveAccessibleDescription('1 Vorgang wird angehalten:')
  })

  it('hält Liste und Anzahl beim Öffnen fest - ein Poll verschiebt sie nicht', async () => {
    setOperations([SCAN, EXPORT])
    const user = userEvent.setup()
    const { rerender } = render(<ProjectOperationsBar projectId={1} />)
    await user.click(trigger())

    setOperations([EXPORT, REVIEW, { ...SCAN, run_id: 5 }])
    rerender(<ProjectOperationsBar projectId={1} />)

    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAccessibleDescription('2 Vorgänge werden angehalten:')
    expect(
      within(dialog)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Scan — läuft', 'Export — wartet'])
    // Die Statuszeile der Leiste selbst folgt dem Poll.
    expect(screen.getByRole('status')).toHaveTextContent('Läuft oder wartet: Export, Prüfung, Scan')
  })

  it('schließt mit "Weiterlaufen lassen" ohne Abbruch und gibt den Fokus an den Auslöser zurück', async () => {
    setOperations([SCAN])
    const user = userEvent.setup()
    render(<ProjectOperationsBar projectId={1} />)
    await user.click(trigger())

    await user.click(screen.getByRole('button', { name: 'Weiterlaufen lassen' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(cancelAll.mutate).not.toHaveBeenCalled()
    expect(trigger()).toHaveFocus()
  })

  it('bricht nach Bestätigung ab, schließt und setzt den Fokus auf die Statuszeile', async () => {
    setOperations([SCAN, EXPORT])
    cancelAll.mutate.mockImplementation((_: unknown, options: { onSuccess: () => void }) =>
      options.onSuccess(),
    )
    const user = userEvent.setup()
    render(<ProjectOperationsBar projectId={1} />)
    await user.click(trigger())

    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Alle abbrechen' }),
    )

    expect(cancelAll.mutate).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveFocus()
  })

  it('lässt sich während der laufenden Anfrage nicht schließen', async () => {
    setOperations([SCAN])
    const user = userEvent.setup()
    const { rerender } = render(<ProjectOperationsBar projectId={1} />)
    await user.click(trigger())

    setCancelAll({ isPending: true })
    rerender(<ProjectOperationsBar projectId={1} />)
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByRole('button', { name: 'Weiterlaufen lassen' })).toBeDisabled()
    await user.keyboard('{Escape}')

    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('zeigt bei gescheiterter Übermittlung einen Alert mit Wiederholung', async () => {
    setOperations([SCAN])
    setCancelAll({ isError: true })
    const user = userEvent.setup()
    render(<ProjectOperationsBar projectId={1} />)

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Der Abbruch konnte nicht übermittelt werden.')
    await user.click(within(alert).getByRole('button', { name: 'Erneut versuchen' }))

    expect(cancelAll.mutate).toHaveBeenCalledTimes(1)
  })
})
