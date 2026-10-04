import { describe, expect, it } from 'vitest'

import type { ProjectOut, ScanStatus } from '../api/types'
import {
  criterionRunSummary,
  projectFixture,
  scanSummary,
  scoringRunSummary,
} from '../test/projectStateSpace'
import { computeStepStates, PIPELINE_STEPS, type StepId } from './pipelineSteps'
import { ausschussConfirmLabel, deriveStepAction, type StepActionKind } from './stepActions'
import {
  ALBUM_OPEN_LABEL,
  AUSSCHUSS_CONFIRM_LABEL,
  NEXT_STEP_LABELS,
  NEXT_UNAVAILABLE_TEXT,
  RUN_STEP_TEXTS,
  type RunStepId,
} from './stepActionTexts'

/*
 * Die Tabelle "Hauptaktion je Schritt und Zustand" über dem vollständig aufgezählten Eingaberaum:
 * Schritt x Laufstatus x isTriggerPending x (Ausschuss) gate_confirmed_at x openCount x
 * Erreichbarkeit des Folgeschritts. Die Erreichbarkeit kommt aus `computeStepStates`.
 */

const RUN_STATES: readonly (ScanStatus | null)[] = [null, 'running', 'success', 'failed']
const OPEN_COUNTS: readonly (number | null)[] = [null, 0, 1, 7]
const GATE = '2026-08-12T09:30:00Z'

interface Case {
  step: StepId
  project: ProjectOut
  status: ScanStatus | null
  isTriggerPending: boolean
  openCount: number | null
}

/** Ein Projekt, in dem der betrachtete Schritt den Lauf `status` trägt; die übrigen Felder
 * decken die Erreichbarkeit des Folgeschritts in beiden Richtungen ab. */
function enumerateCases(): Case[] {
  const cases: Case[] = []
  for (const status of RUN_STATES) {
    for (const isTriggerPending of [false, true]) {
      for (const categoryEnabled of [false, true]) {
        cases.push({
          step: 'scan',
          status,
          isTriggerPending,
          openCount: null,
          project: projectFixture({
            last_scan: status === null ? null : scanSummary(status),
            category_selection_enabled: categoryEnabled,
          }),
        })
        for (const gate of [null, GATE]) {
          for (const openCount of OPEN_COUNTS) {
            cases.push({
              step: 'ausschuss',
              status,
              isTriggerPending,
              openCount,
              project: projectFixture({
                last_scan: scanSummary('success'),
                last_scoring_run:
                  status === null
                    ? null
                    : scoringRunSummary(status, status === 'success' ? gate : null),
                category_selection_enabled: categoryEnabled,
              }),
            })
          }
        }
        cases.push({
          step: 'kriterien',
          status,
          isTriggerPending,
          openCount: null,
          project: projectFixture({
            last_scan: scanSummary('success'),
            last_scoring_run: scoringRunSummary('success', GATE),
            last_criterion_scoring_run: status === null ? null : criterionRunSummary(status),
            category_selection_enabled: categoryEnabled,
          }),
        })
      }
    }
  }
  return cases
}

const cases = enumerateCases()

function nextStepId(step: StepId): StepId | null {
  const index = PIPELINE_STEPS.findIndex((entry) => entry.id === step)
  return PIPELINE_STEPS[index + 1]?.id ?? null
}

function isNextReachable(c: Case): boolean {
  const next = nextStepId(c.step)
  return computeStepStates(c.project).find((state) => state.id === next)?.isReachable === true
}

function derive(c: Case) {
  return deriveStepAction(c.step, c.project, {
    openCount: c.openCount,
    isTriggerPending: c.isTriggerPending,
  })
}

describe('deriveStepAction: Tabelle über den vollständigen Eingaberaum', () => {
  it('rechnet alle Lagen durch', () => {
    // 4 Status x 2 pending x 2 Flag x (1 Scan + 8 Ausschuss + 1 Klassifizierung)
    expect(cases).toHaveLength(160)
  })

  it('liefert je Lage genau eine Hauptaktion nach der Tabelle', () => {
    for (const c of cases) {
      const { action } = derive(c)
      let expected: StepActionKind
      if (c.status === 'running' || c.isTriggerPending) {
        expected = 'running'
      } else if (c.status === 'failed') {
        expected = 'retry'
      } else if (c.status === null) {
        expected = 'start'
      } else if (
        c.step === 'ausschuss' &&
        (c.project.last_scoring_run?.gate_confirmed_at === null || (c.openCount ?? 0) > 0)
      ) {
        expected = 'confirm'
      } else {
        expected = isNextReachable(c) ? 'next' : 'nextUnavailable'
      }
      expect(action.kind, JSON.stringify(c)).toBe(expected)
    }
  })

  it('setzt "Erneut …" genau nach einem erfolgreichen Lauf, nie bei Fehlschlag', () => {
    for (const c of cases) {
      const { rerun } = derive(c)
      expect(rerun !== null, JSON.stringify(c)).toBe(c.status === 'success')
      if (c.status === 'failed' && !c.isTriggerPending) {
        expect(derive(c).action.kind).toBe('retry')
      }
    }
  })

  it('gibt nie "next" bei nicht erreichbarem Folgeschritt, und "next.to" folgt PIPELINE_STEPS', () => {
    for (const c of cases) {
      const { action } = derive(c)
      if (action.kind !== 'next') {
        continue
      }
      expect(isNextReachable(c)).toBe(true)
      const next = nextStepId(c.step)
      expect(action.to).toBe(`/projects/${c.project.id}/pipeline/${next}`)
      expect(action.label).toBe(NEXT_STEP_LABELS[next as Exclude<StepId, 'scan'>])
    }
  })

  it('beschriftet Start, Wiederholung und Lauf aus derselben Konstanten', () => {
    for (const c of cases) {
      const { action, rerun } = derive(c)
      const texts = RUN_STEP_TEXTS[c.step as RunStepId]
      if (action.kind === 'start' || action.kind === 'retry') {
        expect(action.label).toBe(texts.start)
      }
      if (action.kind === 'running') {
        expect(action.label).toBe(texts.running)
      }
      if (rerun !== null) {
        expect(rerun).toEqual(texts.rerun)
      }
    }
  })

  it('beschriftet die Abschluss-Aktion mit der geladenen Anzahl', () => {
    for (const c of cases) {
      const { action } = derive(c)
      if (action.kind === 'confirm') {
        expect(action.label).toBe(ausschussConfirmLabel(c.openCount))
      }
    }
  })

  it('bleibt beim Ausschuss "confirm", wenn nach der Bestätigung Vorschläge neu offen sind', () => {
    const { action } = deriveStepAction(
      'ausschuss',
      projectFixture({ last_scoring_run: scoringRunSummary('success', GATE) }),
      { openCount: 3, isTriggerPending: false },
    )
    expect(action.kind).toBe('confirm')
  })

  it('führt die Kuratierung als Link in den Album-Entwurf, ohne "Erneut …"', () => {
    const result = deriveStepAction('kuratierung', projectFixture({ id: 9 }), {
      openCount: null,
      isTriggerPending: false,
    })
    expect(result).toEqual({
      action: { kind: 'open', label: ALBUM_OPEN_LABEL, to: '/projects/9/album' },
      rerun: null,
    })
  })

  it('nennt den neutralen Text, wenn die Klassifizierung abgeschaltet ist', () => {
    const { action } = deriveStepAction(
      'ausschuss',
      projectFixture({
        category_selection_enabled: false,
        last_scoring_run: scoringRunSummary('success', GATE),
      }),
      { openCount: 0, isTriggerPending: false },
    )
    expect(action).toEqual({ kind: 'nextUnavailable', text: NEXT_UNAVAILABLE_TEXT })
  })
})

describe('Wortregeln (Literal-Fälle)', () => {
  it('nennt die Anzahl im Singular und Plural, ohne Anzahl nur das Abschließen', () => {
    expect(ausschussConfirmLabel(1)).toBe('1 Vorschlag als Ausschuss übernehmen und abschließen')
    expect(ausschussConfirmLabel(7)).toBe('7 Vorschläge als Ausschuss übernehmen und abschließen')
    expect(ausschussConfirmLabel(0)).toBe(AUSSCHUSS_CONFIRM_LABEL)
    expect(ausschussConfirmLabel(null)).toBe(AUSSCHUSS_CONFIRM_LABEL)
    expect(AUSSCHUSS_CONFIRM_LABEL).toBe('Ausschuss abschließen')
  })

  it('verwendet für "Erneut …" das Verb des Startknopfs', () => {
    expect(RUN_STEP_TEXTS.scan.start).toBe('Fotos einlesen')
    expect(RUN_STEP_TEXTS.scan.rerun.label).toBe('Erneut einlesen')
    expect(RUN_STEP_TEXTS.ausschuss.start).toBe('Vorschläge erkennen')
    expect(RUN_STEP_TEXTS.ausschuss.rerun.label).toBe('Erneut erkennen')
    expect(RUN_STEP_TEXTS.kriterien.start).toBe('Klassifizierung starten')
    expect(RUN_STEP_TEXTS.kriterien.rerun.label).toBe('Erneut klassifizieren')
  })

  it('lässt den Knopf, der nur Vorschläge erzeugt, nichts aussortieren, löschen oder übernehmen', () => {
    for (const text of [
      RUN_STEP_TEXTS.ausschuss.start,
      RUN_STEP_TEXTS.ausschuss.running,
      RUN_STEP_TEXTS.ausschuss.rerun.label,
    ]) {
      expect(text).not.toMatch(/aussortieren|löschen|übernehmen/i)
    }
  })

  it('nennt im Erklärsatz zum Scan neue, geänderte und entfernte Fotos und den Ausschuss', () => {
    const { explanation } = RUN_STEP_TEXTS.scan.rerun
    for (const word of ['neue', 'geänderte', 'entfernte', 'Ausschuss']) {
      expect(explanation).toContain(word)
    }
  })
})
