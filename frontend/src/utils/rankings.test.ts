import { describe, expect, it } from 'vitest'

import type { PhotoOut, RankingOut } from '../api/types'
import { curatedRanking } from './rankings'

function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    event_id: 1,
    rank_score: 0.8,
    rank_position: 1,
    proposed: true,
    partition_size: 1,
    curation_position: 1,
    ...overrides,
  }
}

/** Nur die Felder, die `curatedRanking` liest - der Rest ist fuer diese reine Ableitung ohne
 * Belang und wird deshalb auch nicht mitgeschleppt. */
function photo(value: RankingOut | null | undefined): PhotoOut {
  return { ranking: value } as unknown as PhotoOut
}

describe('curatedRanking', () => {
  it('returns the ranking when it belongs to the requested selection', () => {
    const selected = ranking({ curation_position: 2 })

    expect(curatedRanking(photo(selected))).toBe(selected)
  })

  it('returns null when no selection was requested', () => {
    expect(curatedRanking(photo(ranking({ curation_position: null })))).toBeNull()
  })

  it('returns null for a photo without a ranking row', () => {
    expect(curatedRanking(photo(null))).toBeNull()
    expect(curatedRanking(photo(undefined))).toBeNull()
  })

  it('keeps a curation_position of 0 instead of dropping it as falsy', () => {
    /* DIE Zusage dieses Moduls: `0` ist keine gueltige Position (sie ist 1-basiert), aber ein
     * Falsyness-Filter verloere sie stillschweigend - und genau diese Klasse Fehler faellt in
     * keiner Ansicht auf, weil das Foto einfach fehlt. Geprueft wird deshalb auf `!== null`. */
    const atZero = ranking({ curation_position: 0 })

    expect(curatedRanking(photo(atZero))).toBe(atZero)
  })
})
