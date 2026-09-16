import { describe, expect, it } from 'vitest'

import type { MotifStrengthBandsOut } from '../api/types'
import { MOTIF_SET } from '../test/motifSetFixture'
import { motifFillStep } from './motifStrength'

/**
 * specs/features/0490-motivstaerke-kompakt.md, AK3, und ADR 0113 Punkt 1.
 *
 * DIE BANDGRENZEN STEHEN NIE ALS DEZIMALLITERAL: `bands.strong` bzw. der Bruch selbst. Ein
 * `0.67` im Test pruefte die Kalibrierung des Backends statt die Stufung dieser Funktion - und
 * bliebe gruen, waehrend eine verschobene Grenze die Anzeige verfaelscht.
 */
const bands: MotifStrengthBandsOut = MOTIF_SET.strength_bands

describe('motifFillStep', () => {
  it.each([
    ['genau auf der oberen Grenze', bands.strong, 'strong'],
    ['oberhalb der oberen Grenze', 1, 'strong'],
    ['genau auf der unteren Grenze', bands.medium, 'medium'],
    ['zwischen den Grenzen', (bands.medium + bands.strong) / 2, 'medium'],
    ['knapp unterhalb der unteren Grenze', bands.medium / 2, 'weak'],
    ['knapp ueber null', 0.001, 'weak'],
    ['genau null', 0, 'none'],
  ])('stuft eine Staerke %s als %s ein', (_fall, strength, expected) => {
    expect(motifFillStep(strength, bands, true)).toBe(expected)
  })

  it('schliesst BEIDE Grenzen ein, genau wie das Backend', () => {
    // `>` statt `>=` verschoebe jeden Grenzwert um eine Stufe nach unten - an genau zwei Punkten,
    // die kein anderer Fall trifft.
    expect(motifFillStep(bands.strong, bands, true)).toBe('strong')
    expect(motifFillStep(bands.medium, bands, true)).toBe('medium')
  })

  it('liest die Grenzen aus dem Parameter, nicht aus einer eingebauten Skala', () => {
    // Mit verschobenen Grenzen faellt derselbe Wert in eine andere Stufe. Ohne diesen Fall
    // bestuende der Test auch dann, wenn die Funktion feste Zahlen mitbraechte.
    const verschoben: MotifStrengthBandsOut = { strong: 0.9, medium: 0.8 }
    expect(motifFillStep(0.85, verschoben, true)).toBe('medium')
    expect(motifFillStep(0.85, bands, true)).toBe('strong')
  })

  it('liefert fuer ein lokal nicht beurteilbares Motiv keine Fuellung', () => {
    // AK7: derselbe leere Umriss wie "gar nicht vertreten" - der Unterschied steht in der
    // aufgeklappten Zeile, nicht in der Reihe.
    expect(motifFillStep(0.95, bands, false)).toBe('none')
  })

  it('bevorzugt die Nichtbeurteilbarkeit vor jeder Stufe, auch bei Staerke 1', () => {
    expect(motifFillStep(1, bands, false)).toBe('none')
  })
})
