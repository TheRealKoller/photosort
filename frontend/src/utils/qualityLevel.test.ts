import { describe, expect, it } from 'vitest'

import { QUALITY_LEVEL_LABELS, qualityLevel } from './qualityLevel'

describe('qualityLevel', () => {
  it('returns null when there is no local_quality_score', () => {
    expect(qualityLevel(null)).toBeNull()
  })

  it('returns "low" for a score below the low threshold', () => {
    expect(qualityLevel(10)).toBe('low')
  })

  it('returns "medium" for a score between the two thresholds', () => {
    expect(qualityLevel(50)).toBe('medium')
  })

  it('returns "high" for a score at or above the high threshold', () => {
    expect(qualityLevel(80)).toBe('high')
  })
})

describe('QUALITY_LEVEL_LABELS', () => {
  it('has a written-out German label for every level', () => {
    expect(QUALITY_LEVEL_LABELS.low).toBe('Einfache Bildqualität')
    expect(QUALITY_LEVEL_LABELS.medium).toBe('Gute Bildqualität')
    expect(QUALITY_LEVEL_LABELS.high).toBe('Hohe Bildqualität')
  })
})
