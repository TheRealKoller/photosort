import { describe, expect, it } from 'vitest'

import {
  bestExposureIndices,
  bestSharpnessIndices,
  formatExposure,
  formatSharpness,
  formatSpan,
} from './duplicateMetrics'

describe('duplicateMetrics - formatSharpness', () => {
  it.each([
    [412.7, '413'],
    [0.7341, '0,734'],
    [1234.5, '1.230'],
    [0, '0'],
  ])('zeigt %s mit drei signifikanten Stellen als "%s"', (wert, erwartet) => {
    expect(formatSharpness(wert)).toBe(erwartet)
  })

  it('nennt einen fehlenden Messwert, statt ihn als Null zu zeigen', () => {
    expect(formatSharpness(null)).toBe('nicht gemessen')
  })
})

describe('duplicateMetrics - formatExposure', () => {
  it.each([
    [0.125, '12,5 % ohne Zeichnung'],
    [0.2, '20 % ohne Zeichnung'],
    [0.0004, '0 % ohne Zeichnung'],
    [0, '0 % ohne Zeichnung'],
  ])('zeigt den Anteil %s als "%s"', (wert, erwartet) => {
    expect(formatExposure(wert)).toBe(erwartet)
  })
})

describe('duplicateMetrics - formatSpan', () => {
  it.each([
    [0, 'unter einer Sekunde'],
    [1, '1 Sekunde'],
    [59, '59 Sekunden'],
    [60, '1 Minute'],
    [119, '1 Minute'],
    [3599, '59 Minuten'],
    [3600, '1 Stunde'],
    [3660, '1 Stunde 1 Minute'],
    [7320, '2 Stunden 2 Minuten'],
    // Die beiden Demo-Serien: 51 und 102 Minuten.
    [51 * 60, '51 Minuten'],
    [102 * 60, '1 Stunde 42 Minuten'],
  ])('nennt %s Sekunden als "%s"', (sekunden, erwartet) => {
    expect(formatSpan(sekunden)).toBe(erwartet)
  })
})

describe('duplicateMetrics - Auszeichnung je Messwert', () => {
  it.each<[string, (number | null)[], number[]]>([
    ['eindeutiges Maximum', [100, 200, 300], [2]],
    // DER TRAGENDE FALL: Die Rohwerte unterscheiden sich, angezeigt werden beide als "413".
    ['Gleichstand erst nach dem Runden', [412.7, 413.2, 100], [0, 1]],
    ['Gleichstand der Rohwerte', [300, 300, 100], [0, 1]],
    ['alle angezeigten Werte gleich', [300, 300], []],
    ['nur ein Wert', [300, null], []],
    ['gar kein Wert', [null, null], []],
    ['ein fehlender Wert zaehlt nicht mit', [300, null, 100], [0]],
  ])('schaerfste: %s', (_fall, werte, erwartet) => {
    expect([...bestSharpnessIndices(werte)].sort()).toEqual(erwartet)
  })

  it('zeichnet bei der Belichtung das MINIMUM der angezeigten Werte aus', () => {
    // 0,04 % und 0 % werden beide als "0 %" angezeigt - beide sind die beste Belichtung.
    expect([...bestExposureIndices([0.0004, 0.0, 0.2])].sort()).toEqual([0, 1])
  })

  it('zeichnet Schaerfe und Belichtung unabhaengig voneinander aus', () => {
    const schaerfe = [500, 100]
    const belichtung = [0.3, 0.1]

    expect([...bestSharpnessIndices(schaerfe)]).toEqual([0])
    expect([...bestExposureIndices(belichtung)]).toEqual([1])
  })

  it('traegt fuer einen fehlenden Wert nie eine Auszeichnung', () => {
    expect(bestSharpnessIndices([null, 5, 3]).has(0)).toBe(false)
    expect(bestExposureIndices([null, 0.5, 0.3]).has(0)).toBe(false)
  })
})
