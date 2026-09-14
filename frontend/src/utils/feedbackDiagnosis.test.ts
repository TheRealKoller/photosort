import { describe, expect, it } from 'vitest'

import type { FeedbackDiagnosisOut, FeedbackExchangeStats } from '../api/types'
import {
  EXCHANGE_KIND_LABELS,
  MOTIF_ERROR_CASE_LABELS,
  exchangeQualityNote,
  hasCorrections,
} from './feedbackDiagnosis'

function diagnosis(correctionCount: number): FeedbackDiagnosisOut {
  return {
    correction_count: correctionCount,
    motif_errors: [],
    exchanges: [],
    criteria: [],
  }
}

function stats(partial: Partial<FeedbackExchangeStats>): FeedbackExchangeStats {
  return {
    kind: 'within_level',
    count: 0,
    preferred_lower_rated_count: 0,
    quality_incomparable_count: 0,
    ...partial,
  }
}

describe('hasCorrections', () => {
  it('unterscheidet den Leerzustand allein an der Zahl der Korrekturen', () => {
    // Der Leerzustand ist NICHT "keine Fehlerfälle": "N Korrekturen, 0 Fehler" ist eine Aussage,
    // "noch keine Korrekturen" ist keine - und beide dürfen nicht gleich aussehen.
    expect(hasCorrections(diagnosis(0))).toBe(false)
    expect(hasCorrections(diagnosis(1))).toBe(true)
  })
})

describe('exchangeQualityNote', () => {
  it('schweigt, solange es keinen Austausch dieser Art gibt', () => {
    expect(exchangeQualityNote(stats({ count: 0 }))).toBeNull()
  })

  it('nennt, wie oft ein schlechter bewertetes Bild vorgezogen wurde', () => {
    const note = exchangeQualityNote(stats({ count: 3, preferred_lower_rated_count: 2 }))

    expect(note).toBe('davon 2× ein schlechter bewertetes Bild vorgezogen')
  })

  it('führt die unvergleichbaren Paare als eigene Angabe, nie einer Seite zugeschlagen', () => {
    const note = exchangeQualityNote(
      stats({ count: 3, preferred_lower_rated_count: 1, quality_incomparable_count: 2 }),
    )

    expect(note).toBe(
      'davon 1× ein schlechter bewertetes Bild vorgezogen, 2× ohne vergleichbare Bewertung',
    )
  })

  it('nennt die unvergleichbaren Paare auch ohne vorgezogenes schlechteres Bild', () => {
    const note = exchangeQualityNote(stats({ count: 2, quality_incomparable_count: 2 }))

    expect(note).toBe('davon 2× ohne vergleichbare Bewertung')
  })

  it('schweigt, wenn es zur Qualität nichts zu sagen gibt', () => {
    // Alle Austausche zogen das besser bewertete Bild vor - eine Zeile "davon 0×" behauptete
    // eine Auffälligkeit, die es nicht gibt.
    expect(exchangeQualityNote(stats({ count: 2 }))).toBeNull()
  })
})

describe('Beschriftungen', () => {
  it('benennt jeden Fehlerfall ohne Fachjargon', () => {
    expect(Object.keys(MOTIF_ERROR_CASE_LABELS)).toEqual(['too_weak', 'missing', 'overcalled'])
    expect(Object.values(MOTIF_ERROR_CASE_LABELS).every((label) => label.length > 0)).toBe(true)
  })

  it('benennt jede Tauschklasse - die unbestimmte ist eine eigene, keine Restklasse', () => {
    expect(Object.keys(EXCHANGE_KIND_LABELS)).toEqual([
      'within_level',
      'across_level',
      'undetermined',
    ])
    expect(EXCHANGE_KIND_LABELS.undetermined).not.toBe(EXCHANGE_KIND_LABELS.across_level)
  })
})
