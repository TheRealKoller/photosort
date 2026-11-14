import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import type { ExportRunSummary } from '../api/types'
import {
  EXPORT_CANCELLED_BEFORE_START_TEXT,
  EXPORT_FOLDER_STAYS_TEXT,
  ExportSection,
} from './ExportSection'
import { useExport } from '../hooks/useExport'

const cancelMock = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false, isError: false }))

vi.mock('../hooks/useExport', () => ({ useExport: vi.fn() }))
vi.mock('../hooks/useOperations', () => ({ useCancelOperation: () => cancelMock }))

const mockedUseExport = vi.mocked(useExport)

function run(overrides: Partial<ExportRunSummary> = {}): ExportRunSummary {
  return {
    id: 1,
    status: 'success',
    started_at: '2026-11-01T10:00:00Z',
    finished_at: '2026-11-01T10:00:05Z',
    target_path: 'PhotoSort-Export/Costa Rica 2026-11-01 10-00-00.000000',
    photo_count: 3,
    exported_count: 3,
    failed_count: 0,
    error_message: null,
    cancel_requested_at: null,
    ...overrides,
  }
}

function setup(overrides: Record<string, unknown> = {}) {
  mockedUseExport.mockReturnValue({
    project: { data: undefined, refetch: vi.fn() },
    preview: { data: { photo_count: 3 }, isSuccess: true },
    trigger: { isPending: false, isError: false, error: null, mutate: vi.fn() },
    lastRun: null,
    runDetail: { data: undefined },
    awaiting: false,
    setAwaiting: vi.fn(),
    ...overrides,
  } as never)
}

describe('ExportSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('zeigt die Anzahl und den Auslöser', () => {
    setup()

    render(<ExportSection projectId={1} />)

    expect(screen.getByText('3 Fotos')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Nach OpenCloud exportieren' })).not.toBeDisabled()
  })

  it('sperrt den Auslöser bei leerer Endauswahl mit sichtbarem Grund', () => {
    setup({ preview: { data: { photo_count: 0 }, isSuccess: true } })

    render(<ExportSection projectId={1} />)

    expect(screen.getByRole('button', { name: 'Nach OpenCloud exportieren' })).toBeDisabled()
    expect(
      screen.getByText('Die Endauswahl ist leer — es gibt nichts zu exportieren'),
    ).toBeVisible()
  })

  it('zeigt während des Laufs Statuszeile und sperrt den Auslöser', () => {
    setup({ lastRun: run({ status: 'running', finished_at: null }) })

    render(<ExportSection projectId={1} />)

    expect(screen.getByText('Export läuft …')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Nach OpenCloud exportieren' })).toBeDisabled()
  })

  it('zeigt nach Abschluss Anzahl, Zielpfad und den Rerun-Auslöser', () => {
    setup({ lastRun: run() })

    render(<ExportSection projectId={1} />)

    expect(screen.getByText(/3 von 3 Fotos nach/)).toBeVisible()
    expect(screen.getByText(run().target_path as string)).toBeVisible()
    expect(screen.getByRole('button', { name: 'Erneut exportieren' })).toBeVisible()
  })

  it('zeigt bei Teilfehlern eine Warnung mit der Liste der nicht übertragenen Fotos', () => {
    setup({
      lastRun: run({ exported_count: 2, failed_count: 1 }),
      runDetail: {
        data: { failed_photos: [{ relative_path: 'kaputt.jpg', error: 'COPY kaputt' }] },
      } as never,
    })

    render(<ExportSection projectId={1} />)

    expect(screen.getByText('Einige Fotos konnten nicht übertragen werden')).toBeVisible()
    expect(screen.getByText('kaputt.jpg')).toBeVisible()
  })

  it('zeigt bei einem fehlgeschlagenen Lauf eine Fehlermeldung statt eines RerunBlocks', () => {
    setup({ lastRun: run({ status: 'failed', error_message: 'Zielordner nicht anlegbar' }) })

    render(<ExportSection projectId={1} />)

    expect(screen.getByText('Zielordner nicht anlegbar')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Erneut exportieren' })).not.toBeInTheDocument()
  })

  it('löst den Export beim Klick aus', async () => {
    const mutate = vi.fn()
    setup({ trigger: { isPending: false, isError: false, error: null, mutate } as never })

    const user = userEvent.setup()
    render(<ExportSection projectId={1} />)

    await user.click(screen.getByRole('button', { name: 'Nach OpenCloud exportieren' }))

    expect(mutate).toHaveBeenCalledTimes(1)
  })
})

describe('ExportSection: Abbrechen (Spec 0641)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    cancelMock.isPending = false
    cancelMock.isError = false
  })

  it.each(['running', 'queued'] as const)(
    'zeigt bei "%s" genau einen Abbrechen-Knopf, der ohne Rückfrage diesen Lauf abbricht',
    async (status) => {
      setup({ lastRun: run({ id: 7, status, finished_at: null }) })
      const user = userEvent.setup()
      render(<ExportSection projectId={1} />)

      expect(screen.getAllByRole('button', { name: /abbrechen$/i })).toHaveLength(1)
      await user.click(screen.getByRole('button', { name: 'Export abbrechen' }))

      expect(cancelMock.mutate).toHaveBeenCalledWith({ kind: 'export', runId: 7 })
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    },
  )

  it.each(['success', 'failed', 'cancelled'] as const)(
    'zeigt bei "%s" keinen Abbrechen-Knopf',
    (status) => {
      setup({ lastRun: run({ status }) })

      render(<ExportSection projectId={1} />)

      expect(screen.queryByRole('button', { name: /abbrechen/i })).not.toBeInTheDocument()
    },
  )

  it('zeigt ohne Lauf keinen Abbrechen-Knopf', () => {
    setup()

    render(<ExportSection projectId={1} />)

    expect(screen.queryByRole('button', { name: /abbrechen/i })).not.toBeInTheDocument()
  })

  it('zeigt "wartet" mit gesperrtem Auslöser ohne Ladezeichen', () => {
    setup({ lastRun: run({ status: 'queued', finished_at: null }) })

    render(<ExportSection projectId={1} />)

    expect(screen.getByText('Export wartet')).toBeVisible()
    const trigger = screen.getByRole('button', { name: 'Wartet auf Start…' })
    expect(trigger).toBeDisabled()
    expect(within(trigger).queryByTestId('button-spinner')).not.toBeInTheDocument()
  })

  it('sperrt den Knopf bei angefordertem Abbruch und nennt den Zustand', () => {
    setup({
      lastRun: run({
        status: 'running',
        finished_at: null,
        cancel_requested_at: '2026-11-01T10:00:03Z',
      }),
    })

    render(<ExportSection projectId={1} />)

    expect(screen.getByText('Export wird abgebrochen…')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Wird abgebrochen…' })).toBeDisabled()
  })

  it('nennt beim abgebrochenen Export Zielpfad, Anzahl und den dauerhaften Hinweis', () => {
    const cancelled = run({ status: 'cancelled', exported_count: 2, photo_count: 5 })
    setup({ lastRun: cancelled })

    render(<ExportSection projectId={1} />)

    expect(screen.getByText(/2 von 5 Fotos wurden bereits nach/)).toBeVisible()
    const path = screen.getByText(cancelled.target_path as string)
    expect(path).toHaveClass('font-mono', 'break-all')
    expect(screen.getByText(EXPORT_FOLDER_STAYS_TEXT)).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    // Kein Lösch-/Verwerfen-Angebot - nur der Auslöser bleibt, mit der Startbeschriftung.
    expect(screen.getAllByRole('button').map((button) => button.textContent)).toEqual([
      'Nach OpenCloud exportieren',
    ])
    expect(screen.getByRole('button', { name: 'Nach OpenCloud exportieren' })).toBeEnabled()
  })

  it('nennt beim Abbruch vor dem ersten Foto nur diesen Satz', () => {
    setup({ lastRun: run({ status: 'cancelled', target_path: null, exported_count: 0 }) })

    render(<ExportSection projectId={1} />)

    expect(screen.getByText(EXPORT_CANCELLED_BEFORE_START_TEXT)).toBeVisible()
    expect(screen.queryByText(/wurden bereits nach/)).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('zeigt bei gescheiterter Übermittlung einen Alert mit Wiederholung', async () => {
    cancelMock.isError = true
    setup({ lastRun: run({ id: 7, status: 'running', finished_at: null }) })
    const user = userEvent.setup()
    render(<ExportSection projectId={1} />)

    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Der Abbruch konnte nicht übermittelt werden.')
    await user.click(within(alert).getByRole('button', { name: 'Erneut versuchen' }))

    expect(cancelMock.mutate).toHaveBeenCalledWith({ kind: 'export', runId: 7 })
  })
})
