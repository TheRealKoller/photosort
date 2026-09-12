import { describe, expect, it } from 'vitest'

import {
  MAX_TIME_OFFSET_MINUTES,
  NO_OFFSET_LABEL,
  applyOffsetToIsoTime,
  formatTimeOffset,
  offsetFromFields,
  offsetToFields,
  validateOffsetFields,
} from './timeOffset'

describe('formatTimeOffset', () => {
  it('nennt den fehlenden Versatz als Wort, nicht als Null', () => {
    // Eine "0:00" liest sich wie ein GESETZTER Wert - der Unterschied zwischen "nicht gesetzt"
    // und "auf null gesetzt" ist fuer den Nutzer genau der, auf den es hier ankommt.
    expect(formatTimeOffset(0)).toBe(NO_OFFSET_LABEL)
  })

  it.each([
    [-120, '−2:00'],
    [-13, '−0:13'],
    [-1, '−0:01'],
    [60, '+1:00'],
    [90, '+1:30'],
    [1, '+0:01'],
  ])('formatiert %i Minuten als %s', (minutes, expected) => {
    expect(formatTimeOffset(minutes)).toBe(expected)
  })

  it('nennt Tage erst, wenn es welche gibt', () => {
    expect(formatTimeOffset(23 * 60 + 59)).toBe('+23:59')
    expect(formatTimeOffset(24 * 60)).toBe('+1 Tag 0:00')
    expect(formatTimeOffset(-(24 * 60))).toBe('−1 Tag 0:00')
    expect(formatTimeOffset(2 * 24 * 60 + 61)).toBe('+2 Tage 1:01')
  })

  it('nutzt das typografische Minus, nicht den Bindestrich', () => {
    // Ein Bindestrich-Minus vor einer Uhrzeit liest sich als Trennstrich.
    expect(formatTimeOffset(-60).startsWith('−')).toBe(true)
  })
})

describe('offsetFromFields', () => {
  it('setzt den Versatz aus Richtung, Tagen, Stunden und Minuten zusammen', () => {
    expect(offsetFromFields({ direction: 'behind', days: 0, hours: 2, minutes: 0 })).toBe(120)
    expect(offsetFromFields({ direction: 'ahead', days: 0, hours: 2, minutes: 0 })).toBe(-120)
  })

  it('rechnet Tage mit', () => {
    expect(offsetFromFields({ direction: 'behind', days: 1, hours: 1, minutes: 1 })).toBe(
      24 * 60 + 61,
    )
  })

  it('macht aus lauter Nullen eine Null, unabhaengig von der Richtung', () => {
    expect(offsetFromFields({ direction: 'ahead', days: 0, hours: 0, minutes: 0 })).toBe(0)
    expect(offsetFromFields({ direction: 'behind', days: 0, hours: 0, minutes: 0 })).toBe(0)
  })

  it('ist die Umkehrung von offsetToFields', () => {
    // Umkehrprobe statt zweier abgeschriebener Wertetabellen: bricht auch, wenn nur eine der
    // beiden Richtungen das Vorzeichen falsch herum anlegt.
    for (const minutes of [0, 1, -1, 59, -59, 60, -60, 1440, -1440, 1501, -1501]) {
      expect(offsetFromFields(offsetToFields(minutes))).toBe(minutes)
    }
  })
})

describe('offsetToFields', () => {
  it('zerlegt einen negativen Versatz als vorgehende Uhr', () => {
    // NEGATIV heisst "die Zeiten werden zurueckgestellt", und das passiert, wenn die Kamerauhr
    // VORGING.
    expect(offsetToFields(-(24 * 60 + 61))).toEqual({
      direction: 'ahead',
      days: 1,
      hours: 1,
      minutes: 1,
    })
  })

  it('zerlegt einen positiven Versatz als nachgehende Uhr', () => {
    expect(offsetToFields(90)).toEqual({
      direction: 'behind',
      days: 0,
      hours: 1,
      minutes: 30,
    })
  })

  it('faellt fuer die Null auf die zurueckstellende Richtung', () => {
    expect(offsetToFields(0)).toEqual({ direction: 'ahead', days: 0, hours: 0, minutes: 0 })
  })
})

describe('validateOffsetFields', () => {
  it('nimmt die Raender an', () => {
    expect(validateOffsetFields({ direction: 'ahead', days: 0, hours: 0, minutes: 0 })).toBeNull()
    expect(validateOffsetFields({ direction: 'ahead', days: 0, hours: 23, minutes: 59 })).toBeNull()
  })

  it.each([
    ['hours', { direction: 'ahead', days: 0, hours: 24, minutes: 0 }],
    ['hours', { direction: 'ahead', days: 0, hours: -1, minutes: 0 }],
    ['minutes', { direction: 'ahead', days: 0, hours: 0, minutes: 60 }],
    ['minutes', { direction: 'ahead', days: 0, hours: 0, minutes: -1 }],
    ['days', { direction: 'ahead', days: -1, hours: 0, minutes: 0 }],
  ] as const)('weist ein %s-Feld ausserhalb seines Bereichs zurueck', (field, fields) => {
    const problem = validateOffsetFields(fields)

    expect(problem).not.toBeNull()
    expect(problem?.field).toBe(field)
  })

  it.each([
    ['days', { direction: 'ahead', days: 1.5, hours: 0, minutes: 0 }],
    ['hours', { direction: 'ahead', days: 0, hours: Number.NaN, minutes: 0 }],
    ['minutes', { direction: 'ahead', days: 0, hours: 0, minutes: 1.5 }],
  ] as const)('weist ein nicht ganzzahliges %s-Feld zurueck', (field, fields) => {
    expect(validateOffsetFields(fields)?.field).toBe(field)
  })

  it('weist einen Versatz jenseits der Gesamtgrenze zurueck', () => {
    const beyond = offsetToFields(MAX_TIME_OFFSET_MINUTES + 1)

    const problem = validateOffsetFields(beyond)

    expect(problem).not.toBeNull()
    expect(problem?.field).toBe('days')
  })

  it('nimmt die Gesamtgrenze selbst an', () => {
    expect(validateOffsetFields(offsetToFields(MAX_TIME_OFFSET_MINUTES))).toBeNull()
    expect(validateOffsetFields(offsetToFields(-MAX_TIME_OFFSET_MINUTES))).toBeNull()
  })
})

describe('applyOffsetToIsoTime', () => {
  it('verschiebt eine Zeit um den Versatz', () => {
    expect(applyOffsetToIsoTime('2026-08-12T14:32:00', -120)).toBe('2026-08-12T12:32:00')
    expect(applyOffsetToIsoTime('2026-08-12T14:32:00', 90)).toBe('2026-08-12T16:02:00')
  })

  it('laesst die Zeit bei Versatz null unberuehrt', () => {
    expect(applyOffsetToIsoTime('2026-08-12T14:32:00', 0)).toBe('2026-08-12T14:32:00')
  })

  it('rechnet ueber die Tagesgrenze', () => {
    expect(applyOffsetToIsoTime('2026-08-12T00:30:00', -60)).toBe('2026-08-11T23:30:00')
  })

  it('liefert null fuer eine unlesbare Zeit statt eines Invalid-Date-Strings', () => {
    expect(applyOffsetToIsoTime('kein Zeitstempel', 60)).toBeNull()
  })
})
