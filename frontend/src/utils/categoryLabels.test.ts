import { describe, expect, it } from 'vitest'

import { categoryAbbreviation, formatCategoryKey } from './categoryLabels'

describe('formatCategoryKey', () => {
  it('maps "gebaeude" to the umlaut display name "Gebäude" (specs/features/0045)', () => {
    expect(formatCategoryKey('gebaeude')).toBe('Gebäude')
  })

  it('falls back to generic capitalization for unmapped keys like "tier"', () => {
    // "tier" hat keinen Sonderzeichen-Bedarf - der generische Fallback reicht (Spec 0045: kein
    // Mapping-Eintrag fuer jedes kuenftige Kriterium noetig).
    expect(formatCategoryKey('tier')).toBe('Tier')
  })

  it('still falls back to generic capitalization for any other unknown key', () => {
    expect(formatCategoryKey('landscape')).toBe('Landscape')
    expect(formatCategoryKey('architecture')).toBe('Architecture')
  })

  it('handles the empty string without throwing', () => {
    expect(formatCategoryKey('')).toBe('')
  })

  it('does not fall through to an inherited Object.prototype property for keys like "toString"', () => {
    // Copilot-Review-Fund (PR #106): ein reiner Plain-Object-Zugriff ohne Own-Property-Check
    // liefert fuer "toString"/"constructor"/etc. das geerbte Prototype-Property statt undefined -
    // die Funktion darf so einen Key niemals als "Treffer" im Override-Mapping behandeln.
    // category_key ist laut Spec ein freier String, keine geschlossene Aufzaehlung.
    expect(formatCategoryKey('toString')).toBe('ToString')
    expect(formatCategoryKey('constructor')).toBe('Constructor')
    expect(formatCategoryKey('hasOwnProperty')).toBe('HasOwnProperty')
  })
})

describe('categoryAbbreviation', () => {
  it('is unaffected by the display-name mapping - stays derived from the raw key', () => {
    expect(categoryAbbreviation('gebaeude')).toBe('GEB')
  })
})
