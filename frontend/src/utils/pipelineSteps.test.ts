import { describe, expect, it } from 'vitest'

import type { ProjectOut } from '../api/types'
import {
  computeStepStates,
  getDefaultStepId,
  getHighestReachableStepId,
  isStepId,
  PIPELINE_STEPS,
  type StepId,
} from './pipelineSteps'

// Literale Fixture-Fabrik, analog zur bestehenden Konvention kleiner literaler Testobjekte (siehe
// ProjectDetailPage.test.tsx) - deckt genau die Feldkombination ab, aus der computeStepStates
// ableitet (specs/architecture/0002-testkonzept.md, Abschnitt "Mehrschritt-Routing").
function project(overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: 1,
    name: 'Costa Rica',
    opencloud_drive_id: 'drive-1',
    opencloud_path: 'CostaRica',
    created_at: '2026-07-20T10:00:00Z',
    last_scan: null,
    last_scoring_run: null,
    last_criterion_scoring_run: null,
    category_selection_enabled: true,
    cloud_vision_detection_enabled: false,
    cloud_vision_consent_at: null,
    ...overrides,
  }
}

describe('PIPELINE_STEPS', () => {
  it('lists all 5 steps in the fixed order (Akzeptanzkriterium 2)', () => {
    expect(PIPELINE_STEPS.map((step) => step.id)).toEqual([
      'scan',
      'ausschuss',
      'gate',
      'kriterien',
      'kuratierung',
    ])
  })
})

describe('isStepId', () => {
  it('accepts every known step id', () => {
    for (const step of PIPELINE_STEPS) {
      expect(isStepId(step.id)).toBe(true)
    }
  })

  it('rejects an unknown/mistyped value', () => {
    expect(isStepId('kriterien-typo')).toBe(false)
    expect(isStepId('')).toBe(false)
  })
})

describe('computeStepStates (Akzeptanzkriterium 3)', () => {
  it('marks every step as not done and only scan/ausschuss as reachable for a fresh project', () => {
    const states = computeStepStates(project())

    expect(states).toEqual([
      { id: 'scan', isDone: false, isReachable: true },
      { id: 'ausschuss', isDone: false, isReachable: true },
      { id: 'gate', isDone: false, isReachable: false },
      { id: 'kriterien', isDone: false, isReachable: false },
      { id: 'kuratierung', isDone: false, isReachable: false },
    ])
  })

  it('marks scan done once the last scan succeeded', () => {
    const states = computeStepStates(
      project({ last_scan: { status: 'success' } as ProjectOut['last_scan'] })
    )

    expect(states.find((s) => s.id === 'scan')).toEqual({
      id: 'scan',
      isDone: true,
      isReachable: true,
    })
  })

  it(
    'keeps ausschuss reachable even when scan has never run (Regressionsschutz: bewusst ' +
      'ungegatet, keine neue Vorbedingung auf last_scan.status)',
    () => {
      const states = computeStepStates(project({ last_scan: null }))

      expect(states.find((s) => s.id === 'ausschuss')?.isReachable).toBe(true)
    }
  )

  it('marks ausschuss done once the last scoring run succeeded', () => {
    const states = computeStepStates(
      project({
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 0,
          error_message: null,
          gate_confirmed_at: null,
        },
      })
    )

    expect(states.find((s) => s.id === 'ausschuss')).toEqual({
      id: 'ausschuss',
      isDone: true,
      isReachable: true,
    })
  })

  it('makes gate reachable exactly once ausschuss succeeded, unconfirmed by default', () => {
    const states = computeStepStates(
      project({
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 3,
          error_message: null,
          gate_confirmed_at: null,
        },
      })
    )

    expect(states.find((s) => s.id === 'gate')).toEqual({
      id: 'gate',
      isDone: false,
      isReachable: true,
    })
  })

  it('marks gate done for an automatically confirmed gate (suggestions_found === 0)', () => {
    const states = computeStepStates(
      project({
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 0,
          error_message: null,
          gate_confirmed_at: '2026-07-20T10:05:00Z',
        },
      })
    )

    expect(states.find((s) => s.id === 'gate')?.isDone).toBe(true)
  })

  it('marks gate done identically for a manually confirmed gate (suggestions_found > 0)', () => {
    const states = computeStepStates(
      project({
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 3,
          error_message: null,
          gate_confirmed_at: '2026-07-20T10:06:00Z',
        },
      })
    )

    expect(states.find((s) => s.id === 'gate')?.isDone).toBe(true)
  })

  it('blocks kriterien while category_selection_enabled is false, even with a confirmed gate', () => {
    const states = computeStepStates(
      project({
        category_selection_enabled: false,
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 0,
          error_message: null,
          gate_confirmed_at: '2026-07-20T10:05:00Z',
        },
      })
    )

    expect(states.find((s) => s.id === 'kriterien')).toEqual({
      id: 'kriterien',
      isDone: false,
      isReachable: false,
    })
  })

  it('makes kriterien reachable once the gate is confirmed and the feature flag is on', () => {
    const states = computeStepStates(
      project({
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 0,
          error_message: null,
          gate_confirmed_at: '2026-07-20T10:05:00Z',
        },
      })
    )

    expect(states.find((s) => s.id === 'kriterien')?.isReachable).toBe(true)
  })

  it(
    'keeps kuratierung permanently not-done, even once the criterion scoring run succeeded ' +
      '(Regressionsschutz: kein Abschlusssignal im Datenmodell fuer einen offenen Review-Prozess)',
    () => {
      const states = computeStepStates(
        project({
          last_criterion_scoring_run: {
            status: 'success',
            started_at: '2026-07-20T10:00:00Z',
            finished_at: '2026-07-20T10:05:00Z',
            photos_total: 10,
            photos_processed: 10,
            error_message: null,
          },
        })
      )

      expect(states.find((s) => s.id === 'kuratierung')).toEqual({
        id: 'kuratierung',
        isDone: false,
        isReachable: true,
      })
    }
  )

  it('keeps kuratierung unreachable until the criterion scoring run succeeded', () => {
    const states = computeStepStates(project())

    expect(states.find((s) => s.id === 'kuratierung')?.isReachable).toBe(false)
  })
})

// Akzeptanzkriterium 4: beide Funktionen liefern fuer dieselbe Zustandskombination dasselbe Ziel.
// Ein einziger parametrisierter Test deckt beide gemeinsam ab (siehe Testkonzept) - ein
// zukuenftiger Refactor, der sie divergieren laesst, muss diesen Test sichtbar brechen.
describe('getDefaultStepId / getHighestReachableStepId (Akzeptanzkriterium 4)', () => {
  const cases: { name: string; project: Partial<ProjectOut>; expected: StepId }[] = [
    {
      name: 'frisches Projekt (nichts erledigt)',
      project: {},
      expected: 'scan',
    },
    {
      name: 'nur Scan erledigt',
      project: { last_scan: { status: 'success' } as ProjectOut['last_scan'] },
      expected: 'ausschuss',
    },
    {
      name: 'Scan+Ausschuss-Erkennung erledigt, Gate ausstehend',
      project: {
        last_scan: { status: 'success' } as ProjectOut['last_scan'],
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 3,
          error_message: null,
          gate_confirmed_at: null,
        },
      },
      expected: 'gate',
    },
    {
      name: 'Gate automatisch bestaetigt (suggestions_found === 0)',
      project: {
        last_scan: { status: 'success' } as ProjectOut['last_scan'],
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 0,
          error_message: null,
          gate_confirmed_at: '2026-07-20T10:05:00Z',
        },
      },
      expected: 'kriterien',
    },
    {
      name: 'Gate manuell bestaetigt',
      project: {
        last_scan: { status: 'success' } as ProjectOut['last_scan'],
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 3,
          error_message: null,
          gate_confirmed_at: '2026-07-20T10:06:00Z',
        },
      },
      expected: 'kriterien',
    },
    {
      name: 'Kriterien-Bewertung erledigt, category_selection_enabled: false (blockiert trotz erfuellter Vorbedingung)',
      project: {
        category_selection_enabled: false,
        last_scan: { status: 'success' } as ProjectOut['last_scan'],
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 0,
          error_message: null,
          gate_confirmed_at: '2026-07-20T10:05:00Z',
        },
        last_criterion_scoring_run: {
          status: 'success',
          started_at: '2026-07-20T10:06:00Z',
          finished_at: '2026-07-20T10:07:00Z',
          photos_total: 10,
          photos_processed: 10,
          error_message: null,
        },
      },
      expected: 'kuratierung',
    },
    {
      name: 'alle 5 Schritte bereits erledigt/erreicht',
      project: {
        last_scan: { status: 'success' } as ProjectOut['last_scan'],
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: 0,
          error_message: null,
          gate_confirmed_at: '2026-07-20T10:05:00Z',
        },
        last_criterion_scoring_run: {
          status: 'success',
          started_at: '2026-07-20T10:06:00Z',
          finished_at: '2026-07-20T10:07:00Z',
          photos_total: 10,
          photos_processed: 10,
          error_message: null,
        },
      },
      expected: 'kuratierung',
    },
  ]

  for (const { name, project: overrides, expected } of cases) {
    it(`${name}: beide Funktionen liefern "${expected}"`, () => {
      const states = computeStepStates(project(overrides))

      expect(getDefaultStepId(states)).toBe(expected)
      expect(getHighestReachableStepId(states)).toBe(expected)
      expect(getDefaultStepId(states)).toBe(getHighestReachableStepId(states))
    })
  }
})
