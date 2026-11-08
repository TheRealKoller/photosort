import { describe, expect, it } from 'vitest'

import {
  ALBUM_SUITABILITY_MAX_LEVEL,
  ALBUM_SUITABILITY_NOT_RATED_TEXT,
  formatAlbumSuitabilityLevel,
} from './albumSuitability'

describe('formatAlbumSuitabilityLevel', () => {
  it('names the level and the scale it belongs to', () => {
    expect(formatAlbumSuitabilityLevel(4)).toBe('Stufe 4 von 5')
  })

  it.each([1, 2, 3, 4, 5])('formats level %i', (level) => {
    expect(formatAlbumSuitabilityLevel(level)).toBe(`Stufe ${level} von 5`)
  })

  it('derives the upper bound from the constant instead of a second literal', () => {
    expect(formatAlbumSuitabilityLevel(1)).toContain(String(ALBUM_SUITABILITY_MAX_LEVEL))
  })
})

describe('ALBUM_SUITABILITY_NOT_RATED_TEXT', () => {
  it('is a sentence and not a placeholder character', () => {
    // Der Satz steht an genau EINER Stelle: Kachel und Bewertungsdetails tragen denselben, und ein
    // zweites Literal liefe davon weg. „bewertet" bleibt der menschlichen Bewertung vorbehalten.
    expect(ALBUM_SUITABILITY_NOT_RATED_TEXT.endsWith('eingestuft')).toBe(true)
    expect(ALBUM_SUITABILITY_NOT_RATED_TEXT).not.toBe('—')
  })
})
