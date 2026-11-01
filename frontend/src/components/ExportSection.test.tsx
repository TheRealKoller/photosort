import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import type { ExportRunSummary } from '../api/types'
import { ExportSection } from './ExportSection'
import { useExport } from '../hooks/useExport'

vi.mock('../hooks/useExport', () => ({ useExport: vi.fn() }))

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
    expect(
      screen.getByRole('button', { name: 'Nach OpenCloud exportieren' }),
    ).not.toBeDisabled()
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
