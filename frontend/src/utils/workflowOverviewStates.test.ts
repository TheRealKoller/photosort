import { describe, expect, it } from 'vitest'

import {
  criterionRunSummary,
  enumerateProjects,
  projectFixture,
  scanSummary,
  scoringRunSummary,
  stepOfText,
  textOf,
} from '../test/projectStateSpace'
import {
  computeStepStates,
  deriveProjectStand,
  deriveWorkflowOverview,
  getBlockedReason,
  getDefaultStepId,
  PIPELINE_STEPS,
  STAND_KLASSIFIZIERUNG_ABGESCHALTET,
  type OverviewEntryId,
  type OverviewEntryState,
  type StepId,
} from './pipelineSteps'

/*
 * Gleichlauf von Ablaufübersicht, Schrittleiste und Stand-Zeile (Spec 0566) über dem vollständig
 * aufgezählten Eingaberaum der Stand-Zeile. `deriveWorkflowOverview` kennt keine eigene Regel;
 * diese Tests halten fest, dass das so bleibt.
 */

const projects = enumerateProjects()

/** Der Schritt, den die Stand-Zeile NENNT - `null`, wenn sie keinen nennt (Randfall B und C). */
function standStepOf(project: (typeof projects)[number]): StepId | null {
  const text = textOf(deriveProjectStand(project))
  if (text === null || text === STAND_KLASSIFIZIERUNG_ABGESCHALTET) {
    return null
  }
  return stepOfText(text)
}

describe('deriveWorkflowOverview: Einträge', () => {
  it('nennt die vier Schritte in der Reihenfolge der Schrittleiste, danach die beiden Stationen', () => {
    const ids = deriveWorkflowOverview(projectFixture()).map((entry) => entry.id)

    expect(ids).toEqual([...PIPELINE_STEPS.map((step) => step.id), 'album', 'selection'])
  })

  it('führt jeden Eintrag zu seinem Ziel - Schritte wie in der Schrittleiste', () => {
    const targets = Object.fromEntries(
      deriveWorkflowOverview(projectFixture({ id: 42 })).map((entry) => [entry.id, entry.to]),
    )

    expect(targets).toEqual({
      scan: '/projects/42/pipeline/scan',
      ausschuss: '/projects/42/pipeline/ausschuss',
      kriterien: '/projects/42/pipeline/kriterien',
      kuratierung: '/projects/42/pipeline/kuratierung',
      album: '/projects/42/album',
      selection: '/projects/42/selection',
    })
  })
})

describe('deriveWorkflowOverview: Gleichlauf über 256 Lagen', () => {
  it('rechnet den Eingaberaum vollständig durch', () => {
    expect(projects).toHaveLength(256)
  })

  it('zeigt höchstens einen Eintrag als "aktuell"', () => {
    for (const project of projects) {
      const current = deriveWorkflowOverview(project).filter((entry) => entry.state === 'aktuell')
      expect(current.length).toBeLessThanOrEqual(1)
    }
  })

  it('nennt als "aktuell" genau den Schritt der Stand-Zeile, und keinen, wo sie keinen nennt', () => {
    for (const project of projects) {
      const current =
        deriveWorkflowOverview(project).find((entry) => entry.state === 'aktuell')?.id ?? null

      expect(current).toBe(standStepOf(project))
    }
  })

  it('nennt als "aktuell" den Schritt, auf dem man über "Pipeline" landet', () => {
    for (const project of projects) {
      const current = deriveWorkflowOverview(project).find((entry) => entry.state === 'aktuell')
      if (current !== undefined) {
        expect(current.id).toBe(getDefaultStepId(computeStepStates(project)))
      }
    }
  })

  it('stellt einen Lauf der Stand-Zeile mit demselben Status an denselben Schritt', () => {
    for (const project of projects) {
      const stand = deriveProjectStand(project)
      if (stand.kind === 'lauf') {
        const entry = deriveWorkflowOverview(project).find(
          (candidate) => candidate.id === stepOfText(stand.label),
        )
        expect(entry?.run).toBe(stand.status)
      }
    }
  })

  it('stimmt je Schritt in "erledigt" (Haken) und "gesperrt" mit der Schrittleiste überein', () => {
    for (const project of projects) {
      const states = computeStepStates(project)
      for (const entry of deriveWorkflowOverview(project)) {
        const state = states.find((candidate) => candidate.id === entry.id)
        if (state === undefined) {
          continue
        }
        expect(entry.isDone).toBe(state.isDone)
        expect(entry.state === 'gesperrt' || entry.state === 'abgeschaltet').toBe(
          !state.isReachable,
        )
        if (entry.state === 'erledigt') {
          expect(state.isDone).toBe(true)
        }
      }
    }
  })

  it('beobachtet je Eintrag genau die erwarteten Zustände - in beiden Richtungen', () => {
    const expected: Record<OverviewEntryId, OverviewEntryState[]> = {
      scan: ['aktuell', 'erledigt'],
      ausschuss: ['aktuell', 'erledigt', 'offen'],
      kriterien: ['abgeschaltet', 'aktuell', 'erledigt', 'gesperrt', 'offen'],
      kuratierung: ['aktuell', 'gesperrt', 'offen'],
      album: ['gesperrt', 'jederzeit'],
      selection: ['gesperrt', 'jederzeit'],
    }
    const observed: Record<OverviewEntryId, Set<OverviewEntryState>> = {
      scan: new Set(),
      ausschuss: new Set(),
      kriterien: new Set(),
      kuratierung: new Set(),
      album: new Set(),
      selection: new Set(),
    }
    for (const project of projects) {
      for (const entry of deriveWorkflowOverview(project)) {
        observed[entry.id].add(entry.state)
      }
    }

    expect(
      Object.fromEntries(Object.entries(observed).map(([id, set]) => [id, [...set].sort()])),
    ).toEqual(expected)
  })

  it('zeigt die Stationen nie als erledigt - erreichbar genau mit der Kuratierung', () => {
    for (const project of projects) {
      const kuratierung = computeStepStates(project).find((step) => step.id === 'kuratierung')
      for (const entry of deriveWorkflowOverview(project)) {
        if (entry.id !== 'album' && entry.id !== 'selection') {
          continue
        }
        expect(entry.isDone).toBe(false)
        expect(entry.run).toBeNull()
        if (kuratierung?.isReachable === true) {
          expect(entry.state).toBe('jederzeit')
          expect(entry.blockedReason).toBeNull()
        } else {
          expect(entry.state).toBe('gesperrt')
          expect(entry.blockedReason).toBe(getBlockedReason('kuratierung', project))
        }
      }
    }
  })

  it('zeigt die abgeschaltete Klassifizierung nie als offen oder aktuell, auch nach einem Lauf', () => {
    for (const project of projects.filter((entry) => !entry.category_selection_enabled)) {
      const kriterien = deriveWorkflowOverview(project).find((entry) => entry.id === 'kriterien')
      expect(kriterien?.state).toBe('abgeschaltet')
      expect(kriterien?.blockedReason).toBe('Diese Funktion ist derzeit nicht aktiviert.')
    }
  })

  it('trägt den Sperrgrund der Schrittleiste wortgleich, und nur an gesperrten Einträgen', () => {
    for (const project of projects) {
      for (const entry of deriveWorkflowOverview(project)) {
        const isBlocked = entry.state === 'gesperrt' || entry.state === 'abgeschaltet'
        if (!isBlocked) {
          expect(entry.blockedReason).toBeNull()
        } else if (entry.id !== 'album' && entry.id !== 'selection') {
          expect(entry.blockedReason).toBe(getBlockedReason(entry.id, project))
        }
      }
    }
  })
})

describe('deriveWorkflowOverview: Einzelfälle', () => {
  it('nennt bei "Noch nicht gescannt" den Scan als aktuell', () => {
    const scan = deriveWorkflowOverview(projectFixture()).find((entry) => entry.id === 'scan')

    expect(scan?.state).toBe('aktuell')
    expect(scan?.run).toBeNull()
  })

  it('zeigt im Randfall C keinen Schritt als aktuell', () => {
    const entries = deriveWorkflowOverview(
      projectFixture({
        category_selection_enabled: false,
        last_scan: scanSummary('success'),
        last_scoring_run: scoringRunSummary('success', '2026-08-12T09:30:00Z'),
      }),
    )

    expect(entries.filter((entry) => entry.state === 'aktuell')).toEqual([])
    expect(entries.find((entry) => entry.id === 'kriterien')?.state).toBe('abgeschaltet')
  })

  it('zeigt einen fehlgeschlagenen Lauf auch an einem erledigten Schritt', () => {
    const entries = deriveWorkflowOverview(
      projectFixture({
        last_scan: scanSummary('success'),
        last_scoring_run: scoringRunSummary('failed', '2026-08-12T09:30:00Z'),
        last_criterion_scoring_run: criterionRunSummary('running'),
      }),
    )

    expect(entries.find((entry) => entry.id === 'ausschuss')).toMatchObject({
      state: 'erledigt',
      run: 'failed',
    })
    expect(entries.find((entry) => entry.id === 'kriterien')).toMatchObject({
      state: 'aktuell',
      run: 'running',
    })
  })
})
