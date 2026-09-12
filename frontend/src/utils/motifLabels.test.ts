import { describe, expect, it } from 'vitest'

import { MOTIF_SET } from '../test/motifSetFixture'
import { formatMotifKey, isLocallyAssessable } from './motifLabels'

describe('formatMotifKey', () => {
  it('returns the display name from the loaded set', () => {
    expect(formatMotifKey('bauwerk_sehenswuerdigkeit', MOTIF_SET.items)).toBe(
      'Bauwerk und Sehenswürdigkeit',
    )
  })

  it('falls back generically for a key outside the set', () => {
    // Kein Absturz und kein leeres Label - praktisch nur fuer einen Altwert aus der Laufhistorie
    // und fuer die kurze Phase, in der das Set noch laedt.
    expect(formatMotifKey('unbekanntes_motiv', MOTIF_SET.items)).toBe('Unbekanntes_motiv')
  })

  it('falls back generically while the set is still empty', () => {
    expect(formatMotifKey('menschen', [])).toBe('Menschen')
  })

  it('returns an empty key unchanged instead of throwing', () => {
    expect(formatMotifKey('', MOTIF_SET.items)).toBe('')
  })

  it('does not reach through to Object.prototype', () => {
    // Lineare Suche ueber acht Eintraege statt eines aus dem Set gebauten Objekt-Lookups: ein Key
    // wie `toString` trifft strukturell keinen Eintrag und faellt korrekt auf den Fallback.
    expect(formatMotifKey('toString', MOTIF_SET.items)).toBe('ToString')
    expect(formatMotifKey('constructor', MOTIF_SET.items)).toBe('Constructor')
  })
})

describe('isLocallyAssessable', () => {
  it('reports the flag the server sent', () => {
    expect(isLocallyAssessable('menschen', MOTIF_SET.items)).toBe(true)
    expect(isLocallyAssessable('aktivitaet', MOTIF_SET.items)).toBe(false)
    expect(isLocallyAssessable('detail_stimmung', MOTIF_SET.items)).toBe(false)
  })

  it('treats an unknown key as assessable so no value is hidden', () => {
    // Die Ausfallrichtung ist Absicht: ein unbekannter Schluessel soll seine ZAHL zeigen, nicht
    // den Satz "lokal nicht beurteilbar" - der waere eine Aussage, die niemand getroffen hat.
    expect(isLocallyAssessable('unbekanntes_motiv', MOTIF_SET.items)).toBe(true)
  })

  it('treats every key as assessable while the set is still empty', () => {
    expect(isLocallyAssessable('aktivitaet', [])).toBe(true)
  })
})
