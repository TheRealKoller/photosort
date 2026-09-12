import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import { listMotifs } from './motifs'
import { MOTIF_SET } from '../test/motifSetFixture'

vi.mock('./client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./client')>()),
  apiFetch: vi.fn(),
}))

describe('api/motifs', () => {
  it('fetches the motif set from GET /motifs', async () => {
    vi.mocked(apiFetch).mockResolvedValue(MOTIF_SET)

    const result = await listMotifs()

    expect(apiFetch).toHaveBeenCalledWith('/motifs')
    expect(result).toEqual(MOTIF_SET)
  })

  it('keeps the order the server sent', async () => {
    // Eine zweite Sortierung hier waere eine zweite, driftende Aussage darueber, in welcher
    // Reihenfolge die Motive stehen - und sie stehen auf jedem Foto in derselben.
    const result = await (async () => {
      vi.mocked(apiFetch).mockResolvedValue(MOTIF_SET)
      return listMotifs()
    })()

    expect(result.items.map((item) => item.key)).toEqual(MOTIF_SET.items.map((item) => item.key))
  })

  it('carries the strength bands from the server', async () => {
    vi.mocked(apiFetch).mockResolvedValue(MOTIF_SET)

    const result = await listMotifs()

    expect(result.strength_bands).toEqual(MOTIF_SET.strength_bands)
  })
})
