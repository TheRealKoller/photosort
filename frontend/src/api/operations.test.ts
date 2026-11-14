import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import {
  cancelAllOperations,
  cancelOperation,
  listOperations,
  operationsQueryKey,
} from './operations'

// `operations.ts` liest nur `apiFetch` aus dem Client - der Mock muss nichts weiter durchreichen.
vi.mock('./client', () => ({ apiFetch: vi.fn() }))

describe('operations API (Spec 0641)', () => {
  it('holt alle Vorgaenge des Projekts', async () => {
    const payload = {
      operations: [
        { kind: 'scan', run_id: 4, label: 'Scan', status: 'running', cancel_requested: false },
      ],
    }
    vi.mocked(apiFetch).mockResolvedValue(payload)

    await expect(listOperations(7)).resolves.toEqual(payload)
    expect(apiFetch).toHaveBeenCalledWith('/projects/7/operations')
  })

  it('bricht GENAU einen Lauf ab - Art und Id stehen im Pfad', async () => {
    const payload = {
      kind: 'scan',
      run_id: 4,
      status: 'running',
      outcome: 'cancel_requested',
    }
    vi.mocked(apiFetch).mockResolvedValue(payload)

    await expect(cancelOperation(7, 'scan', 4)).resolves.toEqual(payload)
    expect(apiFetch).toHaveBeenCalledWith('/projects/7/operations/scan/4/cancel', {
      method: 'POST',
    })
  })

  it('reicht `already_finished` als Ergebnis durch, nicht als Fehler', async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      kind: 'export',
      run_id: 9,
      status: 'success',
      outcome: 'already_finished',
    })

    await expect(cancelOperation(7, 'export', 9)).resolves.toMatchObject({
      outcome: 'already_finished',
    })
  })

  it('bricht alle Vorgaenge des Projekts ab', async () => {
    const payload = { cancelled: [] }
    vi.mocked(apiFetch).mockResolvedValue(payload)

    await expect(cancelAllOperations(7)).resolves.toEqual(payload)
    expect(apiFetch).toHaveBeenCalledWith('/projects/7/operations/cancel-all', { method: 'POST' })
  })

  it('bindet den Abfrageschluessel an das Projekt', () => {
    expect(operationsQueryKey(7)).toEqual(['operations', 7])
    expect(operationsQueryKey(7)).not.toEqual(operationsQueryKey(8))
  })
})
