import { describe, expect, it } from 'vitest'

import { referenceMarkerIndex } from './referenceMarker'

describe('referenceMarkerIndex', () => {
  it('places the marker at reference_index − offset, both ends included', () => {
    expect(referenceMarkerIndex(5, 3, 4)).toBe(2)
    expect(referenceMarkerIndex(3, 3, 4)).toBe(0)
    expect(referenceMarkerIndex(7, 3, 4)).toBe(4)
  })

  it('shows no marker outside the page and without a reference', () => {
    expect(referenceMarkerIndex(2, 3, 4)).toBeNull()
    expect(referenceMarkerIndex(8, 3, 4)).toBeNull()
    expect(referenceMarkerIndex(null, 0, 4)).toBeNull()
  })

  it('takes nothing but an integer as a position', () => {
    // Auflage 11: keine Fallback-Position für einen Wert, den der Server so nie liefert.
    expect(referenceMarkerIndex(1.5, 0, 4)).toBeNull()
    expect(referenceMarkerIndex(Number.NaN, 0, 4)).toBeNull()
  })

  it('stands at zero in an empty row', () => {
    expect(referenceMarkerIndex(0, 0, 0)).toBe(0)
  })
})
