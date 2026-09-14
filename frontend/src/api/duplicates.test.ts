import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from './client'
import { getDuplicateGroup, setDuplicateDecision, setDuplicateGroupDecision } from './duplicates'
import type { DuplicateGroupOut } from './types'

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
}))

const GROUP: DuplicateGroupOut = {
  items: [],
  position: 1,
  total: 2,
}

describe('api/duplicates', () => {
  it('liest die Gruppe ueber IRGENDEIN Mitglied - sie hat keine eigene Id', async () => {
    vi.mocked(apiFetch).mockResolvedValue(GROUP)

    const result = await getDuplicateGroup(7, 42)

    expect(apiFetch).toHaveBeenCalledWith('/projects/7/duplicate-groups/42')
    expect(result).toEqual(GROUP)
  })

  it('schreibt eine Einzelentscheidung mit `decision` als EINZIGEM Feld', async () => {
    // Der Koerper traegt ausschliesslich die Entscheidung (Auflage S6): kein `photo_id`, kein
    // `user_id`, keine Id-Liste. Die Entscheidung gehoert dem Projekt.
    vi.mocked(apiFetch).mockResolvedValue(GROUP)

    const result = await setDuplicateDecision(7, 42, 'discard')

    expect(apiFetch).toHaveBeenCalledWith('/projects/7/photos/42/duplicate-decision', {
      method: 'PUT',
      body: { decision: 'discard' },
    })
    expect(result).toEqual(GROUP)
  })

  it('schreibt die Gruppenentscheidung OHNE Id-Liste - die Menge bestimmt der Server', async () => {
    // Eine vom Aufrufer gelieferte Menge waere ein Massen-Schreibweg auf beliebige Fotos des
    // Projekts. Der Server bildet sie aus dem Stern.
    vi.mocked(apiFetch).mockResolvedValue(GROUP)

    const result = await setDuplicateGroupDecision(7, 42, 'keep')

    expect(apiFetch).toHaveBeenCalledWith('/projects/7/duplicate-groups/42/decision', {
      method: 'PUT',
      body: { decision: 'keep' },
    })
    expect(result).toEqual(GROUP)
  })

  it('kennt keinen Weg zurueck nach "noch nicht entschieden"', async () => {
    // Es gibt kein `DELETE` und keine Ruecknahme-Funktion: aendern heisst den anderen Wert
    // schreiben. Geprueft als Abwesenheit im Modul, nicht als Kommentar.
    const modul = await import('./duplicates')

    expect(Object.keys(modul).sort()).toEqual([
      'getDuplicateGroup',
      'setDuplicateDecision',
      'setDuplicateGroupDecision',
    ])
  })
})
