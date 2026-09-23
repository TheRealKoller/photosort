import { describe, expect, it, vi } from 'vitest'

import { listAusschuss } from './ausschuss'
import { apiFetch } from './client'
import type { AusschussOut } from './types'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

const STAND: AusschussOut = { items: [], total: 0, open_count: 0 }

describe('api/ausschuss', () => {
  it('liest den Bestand seitenweise, mit Seitengroesse und Versatz', async () => {
    vi.mocked(apiFetch).mockResolvedValue(STAND)

    const result = await listAusschuss(7, { limit: 60, offset: 0 })

    expect(apiFetch).toHaveBeenCalledWith('/projects/7/ausschuss?limit=60&offset=0')
    expect(result).toEqual(STAND)
  })

  it('setzt den photo_id-Filter der Detailansicht als eigenen Parameter', async () => {
    // Dieselbe Antwortform, derselbe Endpunkt: Die Detailansicht ist der Bestand mit gesetztem
    // Filter (AK5). `limit`/`offset` bleiben dabei stehen und sind im Filterzweig ohne Wirkung -
    // eine zweite Anfrageform daneben waere eine zweite Fassung derselben Zusage.
    vi.mocked(apiFetch).mockResolvedValue(STAND)

    await listAusschuss(7, { limit: 60, offset: 0, photoId: 42 })

    expect(apiFetch).toHaveBeenCalledWith('/projects/7/ausschuss?limit=60&offset=0&photo_id=42')
  })

  it('haengt ohne Parameter gar kein Fragezeichen an', async () => {
    // Der Endpunkt traegt seine Vorgaben selbst (limit 60, offset 0). Eine leere Abfrage ist
    // damit derselbe Aufruf wie der mit ausgeschriebenen Vorgaben - und keine zweite Form.
    vi.mocked(apiFetch).mockResolvedValue(STAND)

    await listAusschuss(7)

    expect(apiFetch).toHaveBeenCalledWith('/projects/7/ausschuss')
  })

  it('kennt keinen Schreibweg', async () => {
    // Der Abschluss laeuft ueber `projects.ts::confirmAusschussGate`, die Einzelentscheidung ueber
    // `duplicates.ts`. Dieses Modul liest - die Sollmenge steht ausgeschrieben, damit ein neuer
    // Export sie erweitern MUSS statt sie aufzuweichen.
    const modul = await import('./ausschuss')

    expect(Object.keys(modul).sort()).toEqual(['listAusschuss'])
  })
})
