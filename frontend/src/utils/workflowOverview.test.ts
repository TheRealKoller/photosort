import { describe, expect, it } from 'vitest'

import { PIPELINE_STEPS, type OverviewEntryId } from './pipelineSteps'
import { STATION_LABELS } from './projectRoutes'
import { OVERVIEW_TEXTS, overviewEntryLabel } from './workflowOverview'

const ENTRY_IDS: OverviewEntryId[] = [
  'scan',
  'ausschuss',
  'kriterien',
  'kuratierung',
  'album',
  'selection',
]

describe('Erklärtexte der Ablaufübersicht', () => {
  it('nennt die Schritte exakt wie die Schrittleiste und die Stationen aus ihrer Quelle', () => {
    expect(ENTRY_IDS.slice(0, 4).map(overviewEntryLabel)).toEqual(
      PIPELINE_STEPS.map((step) => step.label),
    )
    expect(overviewEntryLabel('album')).toBe(STATION_LABELS.album)
    expect(overviewEntryLabel('selection')).toBe(STATION_LABELS.selection)
    expect(Object.keys(OVERVIEW_TEXTS).sort()).toEqual([...ENTRY_IDS].sort())
  })

  it.each(ENTRY_IDS)('erklärt "%s" in höchstens zwei Sätzen', (id) => {
    const sentences = OVERVIEW_TEXTS[id].purpose
      .split(/(?<=[.!?])\s+/)
      .filter((sentence) => sentence.trim() !== '')

    expect(sentences.length).toBeGreaterThan(0)
    expect(sentences.length).toBeLessThanOrEqual(2)
  })

  it.each([
    ['scan', 'beides'],
    ['ausschuss', 'beides'],
    ['kriterien', 'beides'],
    ['kuratierung', 'läuft von selbst'],
    ['album', 'beides'],
    ['selection', 'braucht dich'],
  ] as const)('kennzeichnet "%s" als "%s"', (id, kind) => {
    expect(OVERVIEW_TEXTS[id].worker.kind).toBe(kind)
    expect(OVERVIEW_TEXTS[id].worker.detail.trim()).not.toBe('')
  })

  it.each([
    ['scan', 'einer von euch, einmal für das ganze Projekt'],
    ['ausschuss', 'einer von euch, einmal für das ganze Projekt'],
    ['kriterien', 'einer von euch, einmal für das ganze Projekt'],
    ['kuratierung', null],
    ['album', 'jeder für sich – jeder von euch hat seinen eigenen Entwurf'],
    ['selection', 'ihr beide gemeinsam'],
  ] as const)('nennt für "%s" die Zuständigkeit %j', (id, responsibility) => {
    expect(OVERVIEW_TEXTS[id].responsibility).toBe(responsibility)
  })

  it.each([
    ['scan', null],
    ['ausschuss', 'scan'],
    ['kriterien', 'ausschuss'],
    ['kuratierung', 'kriterien'],
    ['album', 'kriterien'],
    ['selection', 'kriterien'],
  ] as const)('setzt für "%s" den Schritt %j voraus', (id, step) => {
    expect(OVERVIEW_TEXTS[id].prerequisite?.step ?? null).toBe(step)
  })

  it.each(ENTRY_IDS.filter((id) => id !== 'scan'))(
    'nennt in der Vorbedingung von "%s" den Schritt mit Namen und einen Grund',
    (id) => {
      const prerequisite = OVERVIEW_TEXTS[id].prerequisite
      expect(prerequisite).not.toBeNull()
      const name = overviewEntryLabel(prerequisite?.step ?? 'scan')
      const text = prerequisite?.text ?? ''

      expect(text).toContain(name)
      // Der Grund folgt dem Namen nach Gedankenstrich oder Komma ("denn", "damit").
      expect(text).toMatch(new RegExp(`${name}\\s*(–|,\\s*denn)\\s+\\S`))
    },
  )
})
