import { describe, expect, it } from 'vitest'

import type { PhotoOut, RankingOut } from '../api/types'
import { curatedRankings, primaryRanking } from './rankings'

function ranking(overrides: Partial<RankingOut> = {}): RankingOut {
  return {
    event_id: 1,
    category_key: 'landschaft',
    rank_score: 0.8,
    rank_position: 1,
    partition_size: 3,
    is_primary: true,
    curation_position: null,
    ...overrides,
  }
}

function photo(rankings: RankingOut[]): PhotoOut {
  return {
    id: 1,
    relative_path: 'a.jpg',
    taken_at: '2026-07-20T10:00:00Z',
    ratings: [],
    suggestion: null,
    rankings,
    criterion_scores: [],
    fine_labels: [],
    remote_category: null,
    category_confidence: null,
    category_override: null,
    category_candidates: [],
    cloud_vision_status: [],
  }
}

describe('primaryRanking', () => {
  it('liefert die Zugehoerigkeit mit is_primary', () => {
    const primary = ranking({ category_key: 'tier' })
    const secondary = ranking({ category_key: 'menschen', is_primary: false })

    expect(primaryRanking(photo([secondary, primary]))).toBe(primary)
  })

  it('liefert null ohne jede Zugehoerigkeit', () => {
    expect(primaryRanking(photo([]))).toBeNull()
  })

  it('liefert null, wenn die Liste keine Hauptzeile enthaelt', () => {
    // Der Fall darf nicht vorkommen (der Server sichert genau eine Hauptzeile zu) - "das erste
    // Element" waere hier trotzdem die falsche Antwort: die Funktion soll ihn sichtbar machen,
    // nicht eine Nebenkategorie zur Hauptkategorie erklaeren.
    expect(primaryRanking(photo([ranking({ is_primary: false })]))).toBeNull()
  })
})

describe('curatedRankings', () => {
  it('liefert nur Zugehoerigkeiten mit einer Auswahlposition', () => {
    const selected = ranking({ category_key: 'tier', curation_position: 2 })
    const unselected = ranking({ category_key: 'menschen', is_primary: false })

    expect(curatedRankings(photo([selected, unselected]))).toEqual([selected])
  })

  it('behaelt die Position 0 nicht faelschlich weg', () => {
    /* Geprueft wird auf `!== null`, NICHT auf Falsyness. `0` ist zwar keine Position, die der
     * Server heute vergibt (`row_number()` beginnt bei 1) - eine Falsyness-Pruefung waere aber
     * genau die Art stiller Annahme, die beim naechsten Formatwechsel Fotos verschwinden liesse. */
    const zero = ranking({ curation_position: 0 })

    expect(curatedRankings(photo([zero]))).toEqual([zero])
  })

  it('liefert eine leere Liste, wenn keine Auswahl angefordert wurde', () => {
    expect(curatedRankings(photo([ranking(), ranking({ is_primary: false })]))).toEqual([])
  })

  it('behaelt die Reihenfolge der Antwort bei', () => {
    const first = ranking({ category_key: 'menschen', curation_position: 1 })
    const second = ranking({ category_key: 'tier', is_primary: false, curation_position: 3 })

    expect(curatedRankings(photo([first, second]))).toEqual([first, second])
  })
})
