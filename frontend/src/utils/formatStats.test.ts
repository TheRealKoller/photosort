import { describe, expect, it } from 'vitest'

import { formatBytes, formatCount, formatPercent, formatUsd } from './formatStats'

// specs/features/0207-projekt-statistikseite.md, Akzeptanzkriterien S1/K1/K4: reine
// Formatierungsfunktionen mit deutschem Zahlenformat. Sie tragen die Aussagen, an denen die
// Statistikseite fachlich haengt - insbesondere "ein tatsaechlich angefallener Betrag darf nie
// als 'nichts ausgegeben' erscheinen".

describe('formatBytes', () => {
  it('stellt 0 als "0 MB" dar, nicht als Strich', () => {
    expect(formatBytes(0)).toBe('0 MB')
  })

  it('stellt einen nicht ermittelbaren Wert als Strich dar', () => {
    expect(formatBytes(null)).toBe('—')
  })

  it('rechnet unterhalb von 1 GB in MB mit einer Nachkommastelle', () => {
    expect(formatBytes(1024 * 1024)).toBe('1,0 MB')
    expect(formatBytes(Math.round(2.5 * 1024 * 1024))).toBe('2,5 MB')
  })

  it('rechnet ab genau 1 GB in GB', () => {
    expect(formatBytes(1024 ** 3)).toBe('1,0 GB')
    expect(formatBytes(Math.round(2.3 * 1024 ** 3))).toBe('2,3 GB')
  })

  it('bleibt ein Byte unterhalb der Grenze noch bei MB', () => {
    expect(formatBytes(1024 ** 3 - 1)).toBe('1.024,0 MB')
  })

  it('nutzt das deutsche Dezimalkomma und den deutschen Tausenderpunkt', () => {
    expect(formatBytes(Math.round(1234.5 * 1024 ** 3))).toBe('1.234,5 GB')
  })

  it('stellt einen sehr kleinen, aber vorhandenen Wert als 0,0 MB dar, nicht als 0 MB', () => {
    // Bewusst unterschieden von der exakten Null oben: dort steht "0 MB" (nichts belegt), hier
    // ist etwas da, das nur unterhalb der angezeigten Genauigkeit liegt.
    expect(formatBytes(500)).toBe('0,0 MB')
  })
})

describe('formatUsd', () => {
  it('stellt 0 mit zwei Nachkommastellen und Waehrung dar', () => {
    expect(formatUsd(0)).toBe('0,00 USD')
  })

  it('stellt einen regulaeren Betrag mit zwei Nachkommastellen dar', () => {
    expect(formatUsd(12.1)).toBe('12,10 USD')
  })

  it('nutzt den deutschen Tausenderpunkt', () => {
    expect(formatUsd(1234.5)).toBe('1.234,50 USD')
  })

  it('rundet kaufmaennisch auf zwei Nachkommastellen', () => {
    expect(formatUsd(0.015)).toBe('0,02 USD')
  })

  it('zeigt einen Betrag unterhalb eines Cents als "< 0,01 USD"', () => {
    // Akzeptanzkriterium K4: auf einer Seite zur Kostenkontrolle darf ein tatsaechlich
    // angefallener Betrag nicht als "nichts ausgegeben" erscheinen.
    expect(formatUsd(0.004)).toBe('< 0,01 USD')
    expect(formatUsd(0.0000001)).toBe('< 0,01 USD')
  })

  it('zeigt genau an der Rundungsgrenze bereits einen Cent', () => {
    expect(formatUsd(0.005)).toBe('0,01 USD')
  })
})

describe('formatPercent', () => {
  it('erwartet einen Bruch zwischen 0 und 1', () => {
    expect(formatPercent(0.0829)).toBe('8,3 %')
    expect(formatPercent(1)).toBe('100,0 %')
  })

  it('stellt 0 ohne Nachkommastelle dar', () => {
    expect(formatPercent(0)).toBe('0 %')
  })

  it('rundet auf eine Nachkommastelle', () => {
    expect(formatPercent(1 / 3)).toBe('33,3 %')
    expect(formatPercent(2 / 3)).toBe('66,7 %')
  })
})

describe('formatCount', () => {
  it('setzt den deutschen Tausenderpunkt', () => {
    expect(formatCount(12043)).toBe('12.043')
    expect(formatCount(0)).toBe('0')
  })
})
