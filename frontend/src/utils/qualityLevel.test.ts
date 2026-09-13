import { describe, expect, it } from 'vitest'

import {
  LOW_MEDIUM_THRESHOLD,
  MEDIUM_HIGH_THRESHOLD,
  QUALITY_LEVEL_LABELS,
  qualityLevel,
} from './qualityLevel'

// specs/features/0428-albumtauglichkeit-vom-modell.md: die Dreistufigkeit ist ab hier eine
// DETERMINISTISCHE VERGRÖBERUNG der Modellstufe - Stufe 1-2 niedrig, 3 mittel, 4-5 hoch. Die zehn
// Fälle unten sind die fünf Modellstufen je bei lokaler Korrektur `L = 0` und `L = 1`
// (span = 0,1): 0 / 0,1 · 0,15 / 0,35 · 0,4 / 0,6 · 0,65 / 0,85 · 0,9 / 1,0.
//
// Die eigentliche Zusage sind die Paare 0,35 / 0,4 und 0,6 / 0,65 - dieselbe Modellstufe darf
// nicht in zwei Anzeigestufen erscheinen. Alles andere trägt sie nur.
const CASES: Array<{ score: number; level: 'low' | 'medium' | 'high'; modelLevel: number }> = [
  { score: 0, level: 'low', modelLevel: 1 },
  { score: 0.1, level: 'low', modelLevel: 1 },
  { score: 0.15, level: 'low', modelLevel: 2 },
  { score: 0.35, level: 'low', modelLevel: 2 },
  { score: 0.4, level: 'medium', modelLevel: 3 },
  { score: 0.6, level: 'medium', modelLevel: 3 },
  { score: 0.65, level: 'high', modelLevel: 4 },
  { score: 0.85, level: 'high', modelLevel: 4 },
  { score: 0.9, level: 'high', modelLevel: 5 },
  { score: 1, level: 'high', modelLevel: 5 },
]

describe('qualityLevel', () => {
  it('returns null when there is no rank_score', () => {
    expect(qualityLevel(null)).toBeNull()
  })

  it('treats a rank_score of 0 as a real value and not as "no value"', () => {
    // `0` ist ein GÜLTIGER Qualitätswert (Modellstufe 1 ohne lokale Korrektur). Eine
    // Falsyness-Prüfung im Pfad verlöre ihn lautlos und zeigte "Noch nicht bewertet".
    expect(qualityLevel(0)).toBe('low')
    expect(qualityLevel(0)).not.toBeNull()
  })

  it.each(CASES)(
    'maps a rank_score of $score (model level $modelLevel) to $level',
    ({ score, level }) => {
      expect(qualityLevel(score)).toBe(level)
    },
  )

  it('puts every model level in exactly one display step', () => {
    const stepsByModelLevel = new Map<number, Set<string>>()
    for (const testCase of CASES) {
      const steps = stepsByModelLevel.get(testCase.modelLevel) ?? new Set<string>()
      steps.add(qualityLevel(testCase.score) as string)
      stepsByModelLevel.set(testCase.modelLevel, steps)
    }

    expect([...stepsByModelLevel.keys()].sort()).toEqual([1, 2, 3, 4, 5])
    for (const [modelLevel, steps] of stepsByModelLevel) {
      expect(steps.size, `Modellstufe ${modelLevel} erscheint in mehreren Anzeigestufen`).toBe(1)
    }
  })
})

describe('the thresholds', () => {
  it('sits on the midpoints between two model levels', () => {
    // Literal festgenagelt: eine Schwelle, die nicht auf der Stufenmitte liegt, bricht die
    // Vergröberung oben - und zwar lautlos, weil jede einzelne Zuordnung weiterhin plausibel
    // aussieht.
    expect(LOW_MEDIUM_THRESHOLD).toBe(0.375)
    expect(MEDIUM_HIGH_THRESHOLD).toBe(0.625)
  })

  it('is inclusive at the boundary', () => {
    expect(qualityLevel(LOW_MEDIUM_THRESHOLD)).toBe('medium')
    expect(qualityLevel(MEDIUM_HIGH_THRESHOLD)).toBe('high')
  })

  it('puts the next smaller representable value below the boundary', () => {
    const justBelowLowMedium = 0.3749999999999999
    const justBelowMediumHigh = 0.6249999999999999

    expect(justBelowLowMedium).toBeLessThan(LOW_MEDIUM_THRESHOLD)
    expect(justBelowMediumHigh).toBeLessThan(MEDIUM_HIGH_THRESHOLD)
    expect(qualityLevel(justBelowLowMedium)).toBe('low')
    expect(qualityLevel(justBelowMediumHigh)).toBe('medium')
  })
})

describe('QUALITY_LEVEL_LABELS', () => {
  it('names the album suitability and no longer the image quality', () => {
    // Der Wert misst keine Bildgüte mehr: ein gestochen scharfes, langweiliges Foto trüge sonst
    // die Beschriftung „Einfache Bildqualität".
    expect(QUALITY_LEVEL_LABELS.low).toBe('Wenig albumtauglich')
    expect(QUALITY_LEVEL_LABELS.medium).toBe('Bedingt albumtauglich')
    expect(QUALITY_LEVEL_LABELS.high).toBe('Gut albumtauglich')
  })

  it('carries no word about image quality any more', () => {
    for (const label of Object.values(QUALITY_LEVEL_LABELS)) {
      expect(label.toLowerCase()).not.toContain('bildqualität')
    }
  })
})
