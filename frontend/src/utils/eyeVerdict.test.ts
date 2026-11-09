import { describe, expect, it } from 'vitest'

import { eyeVerdict } from './eyeVerdict'

const EYE_RESULT = {
  album_level: 4,
  model_revision: 'v1.0.0',
  mapping_version: 'eye-4.2.3/v2',
  computed_at: '2026-09-12T10:00:00Z',
  fine_labels: ['beach', 'sunset'],
}

describe('eyeVerdict', () => {
  it('keeps the Eye labels in their order as display text', () => {
    expect(eyeVerdict(EYE_RESULT).fineLabels.map((label) => label.display_name)).toEqual([
      'beach',
      'sunset',
    ])
  })

  it('names Eye as the source of every label', () => {
    for (const label of eyeVerdict(EYE_RESULT).fineLabels) {
      expect(label.provider).toBe('eye')
      expect(label.raw_label).toBe(label.display_name)
    }
  })

  it('never builds the list key from the label text', () => {
    const labels = eyeVerdict({ ...EYE_RESULT, fine_labels: ['beach', 'beach'] }).fineLabels

    expect(new Set(labels.map((label) => label.canonical_key)).size).toBe(2)
    for (const label of labels) {
      expect(label.canonical_key).not.toContain('beach')
    }
  })

  it('yields no labels when Eye named none', () => {
    expect(eyeVerdict({ ...EYE_RESULT, fine_labels: [] }).fineLabels).toEqual([])
  })
})
