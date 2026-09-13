import { describe, expect, it, vi } from 'vitest'

import { getAlbumSelection, setAlbumDecision } from './albumSelection'
import { apiFetch } from './client'
import type { AlbumDecisionOut, AlbumSelectionOut } from './types'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

const SELECTION: AlbumSelectionOut = {
  participants: [
    { user_id: 1, username: 'daniel' },
    { user_id: 2, username: 'nora' },
  ],
  has_proposal: true,
  items: [],
}

const WRITTEN: AlbumDecisionOut = {
  photo_id: 42,
  included: true,
  updated_at: '2026-09-13T10:00:00',
}

describe('api/albumSelection', () => {
  it('reads the whole selection in ONE request, without limit or offset', async () => {
    // Die Menge wird als Ganzes geliefert (kein `total`, keine Seitenweise) - beide Sichten
    // entstehen lokal aus derselben Antwort.
    vi.mocked(apiFetch).mockResolvedValue(SELECTION)

    const result = await getAlbumSelection(7)

    expect(apiFetch).toHaveBeenCalledWith('/projects/7/album-selection')
    expect(result).toEqual(SELECTION)
  })

  it('writes a decision via PUT /photos/{id}/album-decision with `included` as the only field', async () => {
    // Der Body traegt AUSSCHLIESSLICH `included` (Auflage S4): kein `photo_id`, kein `user_id`.
    // Die Entscheidung gehoert dem Projekt - wer angemeldet ist, spielt keine Rolle.
    vi.mocked(apiFetch).mockResolvedValue(WRITTEN)

    const result = await setAlbumDecision(42, true)

    expect(apiFetch).toHaveBeenCalledWith('/photos/42/album-decision', {
      method: 'PUT',
      body: { included: true },
    })
    expect(result).toEqual(WRITTEN)
  })

  it('writes the removal through the SAME endpoint - there is no DELETE', async () => {
    // "Wieder strittig werden" ist kein Zustand, den die Story kennt; aendern heisst den anderen
    // Wert schreiben.
    vi.mocked(apiFetch).mockResolvedValue({ ...WRITTEN, included: false })

    const result = await setAlbumDecision(42, false)

    expect(apiFetch).toHaveBeenCalledWith('/photos/42/album-decision', {
      method: 'PUT',
      body: { included: false },
    })
    expect(result.included).toBe(false)
  })
})
