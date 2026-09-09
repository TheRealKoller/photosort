import { describe, expect, it } from 'vitest'

import { DEFAULT_TOP_N, MAX_TOP_N, MIN_TOP_N, parseTopN } from './curationTopN'

describe('utils/curationTopN', () => {
  it('DEFAULT_TOP_N is 10', () => {
    // GENAU EIN Testfall bindet den Standardwert an seinen Zahlwert - das ist die Produktzusage
    // (specs/features/0357-voller-bildvorrat-kuratierung.md, Akzeptanzkriterium 1/3). Alle
    // uebrigen Tests beider Seiten importieren die Konstante, statt sie abzuschreiben; dieselbe
    // Regel wie bei LOW_CONFIDENCE_THRESHOLD (Spec 0299).
    expect(DEFAULT_TOP_N).toBe(10)
  })

  it('keeps the bounds the server enforces', () => {
    // Deckungsgleich mit `Query(None, ge=1, le=10)` in backend/src/photosort/api/photos.py.
    expect([MIN_TOP_N, MAX_TOP_N]).toEqual([1, 10])
  })

  it.each([
    { value: null, expected: DEFAULT_TOP_N, why: 'kein Suchparameter' },
    { value: '', expected: DEFAULT_TOP_N, why: 'leeres Feld' },
    { value: 'abc', expected: DEFAULT_TOP_N, why: 'keine Zahl' },
    { value: '0', expected: MIN_TOP_N, why: 'unter der Untergrenze' },
    { value: '-3', expected: MIN_TOP_N, why: 'negativ' },
    { value: '0.4', expected: MIN_TOP_N, why: 'gerundet 0, damit unter der Untergrenze' },
    { value: '10.6', expected: MAX_TOP_N, why: 'gerundet 11, damit ueber der Obergrenze' },
    { value: '11', expected: MAX_TOP_N, why: 'ueber der Obergrenze' },
    { value: '1', expected: 1, why: 'genau die Untergrenze' },
    { value: '10', expected: 10, why: 'genau die Obergrenze' },
    { value: '4', expected: 4, why: 'gueltiger Zwischenwert' },
  ])('parseTopN($value) -> $expected ($why)', ({ value, expected }) => {
    expect(parseTopN(value)).toBe(expected)
  })
})
