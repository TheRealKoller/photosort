import { describe, expect, it } from 'vitest'

import type { CriterionScoreOut } from '../api/types'
import { partitionByPresenceThreshold } from './criterionScores'

function score(overrides: Partial<CriterionScoreOut> = {}): CriterionScoreOut {
  return {
    criterion_key: 'sharpness',
    display_name: 'Schärfe',
    value: 0.8,
    source: 'local_heuristic',
    has_presence_threshold: false,
    ...overrides,
  }
}

describe('partitionByPresenceThreshold', () => {
  /* TABELLENGETRIEBEN (Teststrategie der Spec 0497): Die Aufteilung folgt AUSSCHLIESSLICH dem
     Registry-Flag, nie einer im Frontend gepflegten Schluesselliste. */
  it.each([
    {
      name: 'leere Eingabe',
      eingabe: [] as CriterionScoreOut[],
      quality: [] as string[],
      content: [] as string[],
    },
    {
      name: 'nur Qualitaet',
      eingabe: [score({ criterion_key: 'sharpness' }), score({ criterion_key: 'exposure' })],
      quality: ['sharpness', 'exposure'],
      content: [],
    },
    {
      name: 'nur Bildinhalt',
      eingabe: [score({ criterion_key: 'content_people', has_presence_threshold: true })],
      quality: [],
      content: ['content_people'],
    },
    {
      name: 'gemischt',
      eingabe: [
        score({ criterion_key: 'sharpness' }),
        score({ criterion_key: 'content_people', has_presence_threshold: true }),
        score({ criterion_key: 'exposure' }),
        score({ criterion_key: 'content_animal', has_presence_threshold: true }),
      ],
      quality: ['sharpness', 'exposure'],
      content: ['content_people', 'content_animal'],
    },
  ])('teilt $name auf', ({ eingabe, quality, content }) => {
    const partition = partitionByPresenceThreshold(eingabe)

    expect(partition.quality.map((entry) => entry.criterion_key)).toEqual(quality)
    expect(partition.content.map((entry) => entry.criterion_key)).toEqual(content)
  })

  /* Ein Kriterium OHNE das Feld faellt in den Qualitaetsblock - `undefined` ist keine Praesenz-
     Schwelle. Ohne diesen Fall verschoebe eine aeltere Server-Antwort die Zeile still. */
  it('zaehlt ein Kriterium ohne das Feld zur Qualität', () => {
    const ohneFeld = { ...score({ criterion_key: 'legacy' }) } as Record<string, unknown>
    delete ohneFeld.has_presence_threshold

    const partition = partitionByPresenceThreshold([ohneFeld as unknown as CriterionScoreOut])

    expect(partition.quality.map((entry) => entry.criterion_key)).toEqual(['legacy'])
    expect(partition.content).toEqual([])
  })

  /* ORDNUNGSERHALTEND: Die Reihenfolge innerhalb eines Blocks bleibt die vom Backend gelieferte
     Registry-Reihenfolge. Ein Sortieren hier machte die Reihenfolge der Registry wirkungslos. */
  it('erhält die Registry-Reihenfolge innerhalb beider Blöcke', () => {
    const partition = partitionByPresenceThreshold([
      score({ criterion_key: 'z_quality' }),
      score({ criterion_key: 'z_content', has_presence_threshold: true }),
      score({ criterion_key: 'a_quality' }),
      score({ criterion_key: 'a_content', has_presence_threshold: true }),
    ])

    expect(partition.quality.map((entry) => entry.criterion_key)).toEqual([
      'z_quality',
      'a_quality',
    ])
    expect(partition.content.map((entry) => entry.criterion_key)).toEqual([
      'z_content',
      'a_content',
    ])
  })

  /* Die Eingabe bleibt unberuehrt - beide Blöcke sind neue Listen. */
  it('lässt die Eingabeliste unverändert', () => {
    const eingabe = [score({ criterion_key: 'sharpness' })]

    partitionByPresenceThreshold(eingabe)

    expect(eingabe).toHaveLength(1)
  })
})
