import { describe, expect, it } from 'vitest'

import type { PhotoOut } from '../api/types'
import { carriesPersons, filterByPersons, parsePersonIds, withPersonIds } from './personFilter'

function params(...values: string[]): URLSearchParams {
  const result = new URLSearchParams()
  for (const value of values) {
    result.append('person', value)
  }
  return result
}

function photo(id: number, persons: number[]): PhotoOut {
  return {
    id,
    persons: persons.map((personId) => ({ person_id: personId, origin: 'recognized' as const })),
  } as PhotoOut
}

describe('parsePersonIds', () => {
  it('liest einmal, zweimal und dedupliziert', () => {
    expect(parsePersonIds(params('3'))).toEqual([3])
    expect(parsePersonIds(params('3', '5'))).toEqual([3, 5])
    expect(parsePersonIds(params('3', '3'))).toEqual([3])
  })

  it('verwirft nicht Numerisches, 0 und einen dritten Wert', () => {
    expect(parsePersonIds(params('anna', '0', '-1', '1.5'))).toEqual([])
    expect(parsePersonIds(params('1', '2', '3'))).toEqual([1, 2])
  })

  it('schreibt die Auswahl zurück und entfernt sie bei leerer Auswahl', () => {
    const base = new URLSearchParams('rating=album_worthy&person=9')
    expect(withPersonIds(base, [1, 2]).toString()).toBe('rating=album_worthy&person=1&person=2')
    expect(withPersonIds(base, []).toString()).toBe('rating=album_worthy')
  })
})

describe('filterByPersons', () => {
  const photos = [photo(1, [7]), photo(2, [7, 8]), photo(3, [8]), photo(4, [])]

  it('filtert einzeln und bei beiden als UND', () => {
    expect(filterByPersons(photos, [7]).map((entry) => entry.id)).toEqual([1, 2])
    expect(filterByPersons(photos, [7, 8]).map((entry) => entry.id)).toEqual([2])
  })

  it('ein von Hand entfernter Name fehlt in persons und zählt nicht', () => {
    expect(carriesPersons(photo(5, []), [7])).toBe(false)
  })

  it('ein -> aus stellt alle Fotos wieder her', () => {
    expect(filterByPersons(filterByPersons(photos, [7]), [])).toHaveLength(2)
    expect(filterByPersons(photos, [])).toEqual(photos)
  })
})
