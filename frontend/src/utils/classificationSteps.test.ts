import { describe, expect, it } from 'vitest'

import type { CloudPhaseSummaryOut, CriterionScoringRunSummary } from '../api/types'
import {
  CLASSIFICATION_STEP_ORDER,
  deriveClassificationSteps,
  type ClassificationStepId,
} from './classificationSteps'

/**
 * specs/features/0348-klassifizierungs-transparenz.md, decisions/0068-klassifizierungslauf-vier-
 * teilschritte-und-laufeigene-cloud-bilanz.md: die Ableitung "welche Teilschritte hat dieser Lauf,
 * in welchem Zustand, mit welchem Fortschritt" - reine Funktion, kein Provider, kein Router.
 *
 * Die beiden `cloud_phases`-Eintraege tragen in JEDER Fixture unterschiedliche Zahlen: bei
 * gleichen Werten waere eine Vertauschung der beiden Cloud-Schritte unsichtbar, und genau die
 * Zuordnung ist hier die Aussage.
 */

function cloudPhase(overrides: Partial<CloudPhaseSummaryOut> = {}): CloudPhaseSummaryOut {
  return {
    purpose: 'remote_category',
    photos_total: 7,
    photos_processed: 5,
    failed_calls: 1,
    responses_used: 4,
    input_tokens: 600,
    output_tokens: 60,
    cost_usd: 0.6,
    model: 'claude-haiku-4-5',
    provider: 'anthropic',
    ...overrides,
  }
}

const REMOTE_PHASE = cloudPhase()
const LANDMARK_PHASE = cloudPhase({
  purpose: 'landmark',
  photos_total: 3,
  photos_processed: 2,
  failed_calls: 0,
  responses_used: 2,
  input_tokens: 300,
  output_tokens: 30,
  cost_usd: 0.3,
})

function run(overrides: Partial<CriterionScoringRunSummary> = {}): CriterionScoringRunSummary {
  return {
    status: 'running',
    started_at: '2026-09-09T10:00:00Z',
    finished_at: null,
    photos_total: 20,
    photos_processed: 8,
    error_message: null,
    phase: 'criteria',
    cloud_requested: true,
    cloud_error_message: null,
    cloud_phases: [REMOTE_PHASE, LANDMARK_PHASE],
    estimated_cost_usd: 1.2,
    cloud_cost_total_usd: 0.9,
    ...overrides,
  }
}

function idsOf(summary: CriterionScoringRunSummary): ClassificationStepId[] {
  return deriveClassificationSteps(summary).map((step) => step.id)
}

function stateOf(
  summary: CriterionScoringRunSummary,
  id: ClassificationStepId,
): string | undefined {
  return deriveClassificationSteps(summary).find((step) => step.id === id)?.state
}

describe('deriveClassificationSteps: Menge und Reihenfolge', () => {
  it('liefert bei angeforderter Cloud-Nutzung alle vier Teilschritte in Ausführungsreihenfolge', () => {
    expect(idsOf(run())).toEqual(['remote_categories', 'criteria', 'landmark', 'ranking'])
  })

  it('lässt beide Cloud-Teilschritte ohne angeforderte Cloud-Nutzung ganz weg', () => {
    // Ohne Cloud-Freigabe finden sie nicht statt - sie als "übersprungen" zu zeigen behauptete
    // eine Auslassung, wo gar keine Absicht bestand.
    expect(idsOf(run({ cloud_requested: false }))).toEqual(['criteria', 'ranking'])
  })

  it('folgt der Reihenfolge der Ableitung, nicht der der Serverantwort', () => {
    const reversed = run({ cloud_phases: [LANDMARK_PHASE, REMOTE_PHASE] })

    expect(idsOf(reversed)).toEqual(['remote_categories', 'criteria', 'landmark', 'ranking'])
  })
})

describe('deriveClassificationSteps: Zustände', () => {
  it.each(CLASSIFICATION_STEP_ORDER)(
    'markiert bei laufender Phase "%s" die vorherigen als erledigt und die folgenden als ausstehend',
    (phase) => {
      const steps = deriveClassificationSteps(run({ status: 'running', phase }))
      const currentIndex = CLASSIFICATION_STEP_ORDER.indexOf(phase)

      for (const step of steps) {
        const index = CLASSIFICATION_STEP_ORDER.indexOf(step.id)
        const expected =
          index < currentIndex ? 'done' : index === currentIndex ? 'running' : 'pending'
        expect(step.state, step.id).toBe(expected)
      }
    },
  )

  it('markiert nach einem erfolgreichen Lauf ohne laufende Phase alle Teilschritte als erledigt', () => {
    const steps = deriveClassificationSteps(run({ status: 'success', phase: null }))

    expect(steps.map((step) => step.state)).toEqual(['done', 'done', 'done', 'done'])
  })

  it('markiert einen angeforderten Cloud-Teilschritt ohne Bilanz-Eintrag als übersprungen (Altlauf)', () => {
    // Beide Einträge fehlen: ein Lauf von vor der Bilanz-Migration. Die Anzeige sagt das
    // ausdrücklich, statt Nullwerte zu erfinden.
    const oldRun = run({ status: 'success', phase: null, cloud_phases: [] })

    expect(stateOf(oldRun, 'remote_categories')).toBe('skipped')
    expect(stateOf(oldRun, 'landmark')).toBe('skipped')
    expect(stateOf(oldRun, 'criteria')).toBe('done')
  })

  it('markiert nur den fehlenden Cloud-Teilschritt als übersprungen (Einwilligung entzogen)', () => {
    // Die Einwilligung wurde zwischen Auslösen und Start entzogen: `cloud_requested` steht auf
    // true, aber nur die Remote-Phase hat stattgefunden.
    const partial = run({ status: 'success', phase: null, cloud_phases: [REMOTE_PHASE] })

    expect(stateOf(partial, 'remote_categories')).toBe('done')
    expect(stateOf(partial, 'landmark')).toBe('skipped')
  })

  it('markiert einen noch nicht erreichten Cloud-Teilschritt eines LAUFENDEN Laufs nicht als übersprungen', () => {
    // "Übersprungen" gilt nur für einen beendeten Lauf - währenddessen fehlt der Eintrag schlicht
    // noch, und ein durchgestrichener Kreis behauptete eine Auslassung, die es nicht gibt.
    const running = run({
      status: 'running',
      phase: 'remote_categories',
      cloud_phases: [REMOTE_PHASE],
    })

    expect(stateOf(running, 'landmark')).toBe('pending')
  })

  it('behauptet bei einem unbekannten Phasenwert nicht, es sei noch nichts passiert', () => {
    // PhotoSort ist eine PWA: Bundles werden gecacht, und diese Änderung hängt zwei Werte an den
    // Phasen-Enum an. Ein Client, der einen neueren Wert nicht kennt, bekäme aus `indexOf` eine
    // `-1` - ohne Abfangen stünde JEDER Schritt auf `pending`, während der Lauf arbeitet. Genau
    // das gemeldete Symptom der Story, nur durch einen veralteten Client erzeugt.
    const unknownPhase = run({
      status: 'running',
      phase: 'eine_kuenftige_phase' as CriterionScoringRunSummary['phase'],
    })

    const states = deriveClassificationSteps(unknownPhase).map((step) => step.state)

    expect(states).not.toContain('pending')
    expect(states.every((state) => state === 'done')).toBe(true)
  })
})

describe('deriveClassificationSteps: Fortschrittsquellen', () => {
  it('speist jeden Cloud-Teilschritt aus seinem EIGENEN Bilanz-Eintrag', () => {
    const steps = deriveClassificationSteps(run())
    const remote = steps.find((step) => step.id === 'remote_categories')
    const landmark = steps.find((step) => step.id === 'landmark')

    expect(remote?.processed).toBe(REMOTE_PHASE.photos_processed)
    expect(remote?.total).toBe(REMOTE_PHASE.photos_total)
    expect(remote?.cloud).toBe(REMOTE_PHASE)
    expect(landmark?.processed).toBe(LANDMARK_PHASE.photos_processed)
    expect(landmark?.total).toBe(LANDMARK_PHASE.photos_total)
    expect(landmark?.cloud).toBe(LANDMARK_PHASE)
  })

  it('füttert den Kriterien-Schritt nie aus einem Landmark-Eintrag', () => {
    const steps = deriveClassificationSteps(run())
    const criteria = steps.find((step) => step.id === 'criteria')

    expect(criteria?.processed).toBe(8)
    expect(criteria?.total).toBe(20)
    expect(criteria?.cloud).toBeNull()
  })

  it('füttert den Landmark-Schritt nie aus dem Remote-Eintrag und umgekehrt', () => {
    const steps = deriveClassificationSteps(run())
    const remote = steps.find((step) => step.id === 'remote_categories')
    const landmark = steps.find((step) => step.id === 'landmark')

    expect(remote?.cloud?.purpose).toBe('remote_category')
    expect(landmark?.cloud?.purpose).toBe('landmark')
  })

  it('lässt den Rangfolge-Schritt ohne Gesamtzahl (unbestimmter Fortschritt)', () => {
    const ranking = deriveClassificationSteps(run()).find((step) => step.id === 'ranking')

    expect(ranking?.total).toBeNull()
    expect(ranking?.processed).toBeNull()
  })

  it('reicht null unverändert durch, statt es zu 0 zu machen', () => {
    // Ein Cloud-Teilschritt, dessen Zähler noch nicht erfasst sind: `null` heisst "unbekannt".
    // Ein `?? 0` behauptete hier "es ist noch nichts passiert" - eine Aussage, die niemand
    // getroffen hat.
    const withoutCounters = run({
      cloud_phases: [
        cloudPhase({ photos_total: null, photos_processed: null, failed_calls: null }),
      ],
    })
    const remote = deriveClassificationSteps(withoutCounters).find(
      (step) => step.id === 'remote_categories',
    )

    expect(remote?.processed).toBeNull()
    expect(remote?.total).toBeNull()
  })

  it('rechnet und klemmt nicht: Werte werden unverändert durchgereicht', () => {
    const odd = run({
      cloud_phases: [cloudPhase({ photos_total: 2, photos_processed: 5 })],
    })
    const remote = deriveClassificationSteps(odd).find((step) => step.id === 'remote_categories')

    expect(remote?.processed).toBe(5)
    expect(remote?.total).toBe(2)
  })

  it('gibt jedem Teilschritt eine nicht-leere Beschriftung', () => {
    for (const step of deriveClassificationSteps(run())) {
      expect(step.label.trim(), step.id).not.toBe('')
    }
  })
})
