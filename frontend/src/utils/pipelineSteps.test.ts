import { describe, expect, it } from 'vitest'

import type { ProjectOut, ScanStatus } from '../api/types'
import {
  computeStepStates,
  deriveProjectStand,
  getDefaultStepId,
  getHighestReachableStepId,
  isStepId,
  PIPELINE_STEPS,
  RUN_FIELD_BY_STEP,
  STAND_KATEGORIE_ABGESCHALTET,
  STAND_OHNE_SCAN,
  stepProgress,
  type ProjectStand,
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
    selection_target: null,
    effective_selection_target: 1,
    photo_count: 0,
    taken_at_earliest: null,
    taken_at_latest: null,
    ...overrides,
  }
}

describe('PIPELINE_STEPS', () => {
  it('lists all 4 steps in the fixed order (Akzeptanzkriterium 1/2, Spec 0525)', () => {
    expect(PIPELINE_STEPS.map((step) => step.id)).toEqual([
      'scan',
      'ausschuss',
      'kriterien',
      'kuratierung',
    ])
  })

  it('traegt den zusammengelegten Schritt unter dem Label "Ausschuss"', () => {
    expect(PIPELINE_STEPS.find((step) => step.id === 'ausschuss')?.label).toBe('Ausschuss')
  })

  it('kennt kein gate mehr - der Schritt ist entfallen, nicht umbenannt', () => {
    expect(PIPELINE_STEPS.map((step) => step.label)).not.toContain('Ausschuss-Gate')
    expect(PIPELINE_STEPS.map((step) => step.id)).not.toContain('gate')
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

  it('lehnt das entfallene "gate" ab - ein alter Deep-Link laeuft in den Leerzustand', () => {
    expect(isStepId('gate')).toBe(false)
  })
})

describe('computeStepStates (Akzeptanzkriterium 3)', () => {
  it('marks every step as not done and only scan/ausschuss as reachable for a fresh project', () => {
    const states = computeStepStates(project())

    expect(states).toEqual([
      { id: 'scan', isDone: false, isReachable: true },
      { id: 'ausschuss', isDone: false, isReachable: true },
      { id: 'kriterien', isDone: false, isReachable: false },
      { id: 'kuratierung', isDone: false, isReachable: false },
    ])
  })

  it('marks scan done once the last scan succeeded', () => {
    const states = computeStepStates(
      project({ last_scan: { status: 'success' } as ProjectOut['last_scan'] }),
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
    },
  )

  it(
    'haelt ausschuss nach einem erfolgreichen Lauf offen, solange nicht bestaetigt ist ' +
      '(Spec 0525, AK13: die Erkennung ist nur die erste Haelfte des Schritts)',
    () => {
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
        }),
      )

      expect(states.find((s) => s.id === 'ausschuss')).toEqual({
        id: 'ausschuss',
        isDone: false,
        isReachable: true,
      })
    },
  )

  it('marks ausschuss done exactly when the gate is confirmed', () => {
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
      }),
    )

    expect(states.find((s) => s.id === 'ausschuss')).toEqual({
      id: 'ausschuss',
      isDone: true,
      isReachable: true,
    })
  })

  it.each([
    ['automatisch (suggestions_found === 0)', 0],
    ['manuell (suggestions_found > 0)', 3],
  ])('marks ausschuss done identically for a %s confirmation', (_name, suggestionsFound) => {
    const states = computeStepStates(
      project({
        last_scoring_run: {
          id: 1,
          status: 'success',
          started_at: '2026-07-20T10:00:00Z',
          finished_at: '2026-07-20T10:05:00Z',
          photos_total: 10,
          photos_processed: 10,
          suggestions_found: suggestionsFound,
          error_message: null,
          gate_confirmed_at: '2026-07-20T10:05:00Z',
        },
      }),
    )

    expect(states.find((s) => s.id === 'ausschuss')?.isDone).toBe(true)
  })

  it('bleibt nach der Bestaetigung erreichbar (AK11: der Schritt bleibt erneut aufrufbar)', () => {
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
      }),
    )

    expect(states.find((s) => s.id === 'ausschuss')?.isReachable).toBe(true)
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
      }),
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
      }),
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
            phase: null,
            cloud_requested: false,
            cloud_error_message: null,
            cloud_phases: [],
            estimated_cost_usd: null,
            cloud_cost_total_usd: null,
            phase_remaining_seconds: null,
          },
        }),
      )

      expect(states.find((s) => s.id === 'kuratierung')).toEqual({
        id: 'kuratierung',
        isDone: false,
        isReachable: true,
      })
    },
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
      name: 'Scan erledigt, Erkennung gelaufen, Bestaetigung ausstehend',
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
      expected: 'ausschuss',
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
          phase: null,
          cloud_requested: false,
          cloud_error_message: null,
          cloud_phases: [],
          estimated_cost_usd: null,
          cloud_cost_total_usd: null,
          phase_remaining_seconds: null,
        },
      },
      expected: 'kuratierung',
    },
    {
      name: 'alle erreichbaren Schritte bereits erledigt/erreicht',
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
          phase: null,
          cloud_requested: false,
          cloud_error_message: null,
          cloud_phases: [],
          estimated_cost_usd: null,
          cloud_cost_total_usd: null,
          phase_remaining_seconds: null,
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

/*
 * specs/features/0387-schrittleiste-fortschritt.md, Teststrategie "Unit: stepProgress".
 *
 * Die Funktion liefert die Fuellung des Fortschrittsbalkens unter der Schrittleiste. `max` wird
 * IMMER aus `PIPELINE_STEPS.length` hergeleitet und nie fest erwartet - sonst waere der Test
 * bei einer weiteren Pipeline-Stufe still falsch statt rot.
 */
describe('stepProgress', () => {
  const MAX = 2 * PIPELINE_STEPS.length

  it.each([
    { activeIndex: 0, value: 1 },
    { activeIndex: 1, value: 3 },
    { activeIndex: 2, value: 5 },
    { activeIndex: 3, value: 7 },
  ])('liefert fuer Index $activeIndex die Spaltenmitte $value/$max', ({ activeIndex, value }) => {
    expect(stepProgress(activeIndex)).toEqual({ value, max: MAX })
  })

  it.each([-1, PIPELINE_STEPS.length, 1.5, Number.NaN])(
    'liefert fuer den unbrauchbaren Index %p den Wert 0',
    (activeIndex) => {
      expect(stepProgress(activeIndex)).toEqual({ value: 0, max: MAX })
    },
  )

  /*
   * Invariante statt vier Einzelwerte: der Balken waechst streng monoton und ist NIE voll -
   * "fertig" gibt es in dieser Pipeline nicht (siehe `isDone: false` fuer `kuratierung`).
   */
  it('waechst streng monoton und bleibt echt zwischen 0 und max', () => {
    let previous = 0
    for (let index = 0; index < PIPELINE_STEPS.length; index += 1) {
      const { value, max } = stepProgress(index)
      expect(max).toBe(MAX)
      expect(value).toBeGreaterThan(previous)
      expect(value).toBeLessThan(max)
      previous = value
    }
  })
})

/*
 * deriveProjectStand - die Stand-Zeile der Projektkarte (Spec 0375, Akzeptanzkriterien A4/A6/S1).
 *
 * DIE WORTLAUT-TABELLE STEHT AUF DER AUSGABESEITE, NICHT AUF DER EINGABESEITE. Der Test rechnet
 * den ENDLICHEN Eingaberaum vollstaendig durch (256 Kombinationen), sammelt die beobachteten
 * Ergebnisse als Tripel `(kind, stepId, runStatus)` und vergleicht die MENGE gegen die Tabelle -
 * in beiden Richtungen. Nur das faengt ein vierzehntes Verhalten, eine unerreichbar gewordene
 * Zeile und eine zu zwei Zeilen kollabierte Unterscheidung.
 *
 * Den Anzeigetext bildet er auf seine Definition ZURUECK (Nachschlagen in PIPELINE_STEPS), statt
 * ihn abzutippen. Die zwei Sonderwortlaute stehen in einer ausdruecklichen Ausnahmeliste, sodass
 * jede weitere Abweichung rot wird statt zu einer stillen zweiten Textquelle.
 */

const RUN_STATES: readonly (ScanStatus | null)[] = [null, 'running', 'success', 'failed']

function scanSummary(status: ScanStatus): ProjectOut['last_scan'] {
  return { status } as ProjectOut['last_scan']
}

function scoringRunSummary(
  status: ScanStatus,
  gateConfirmedAt: string | null,
): ProjectOut['last_scoring_run'] {
  return { status, gate_confirmed_at: gateConfirmedAt } as ProjectOut['last_scoring_run']
}

function criterionRunSummary(status: ScanStatus): ProjectOut['last_criterion_scoring_run'] {
  return { status } as ProjectOut['last_criterion_scoring_run']
}

/**
 * Der vollstaendig aufgezaehlte Eingaberaum: 4 Scan-Zustaende x 4 Ausschuss-Zustaende x 2
 * Gate-Zustaende x 4 Kriterien-Zustaende x 2 Feature-Flag-Zustaende = 256 Projekte.
 */
function enumerateProjects(): ProjectOut[] {
  const projects: ProjectOut[] = []
  for (const scan of RUN_STATES) {
    for (const scoring of RUN_STATES) {
      for (const gateConfirmed of [false, true]) {
        for (const criterion of RUN_STATES) {
          for (const categoryEnabled of [false, true]) {
            projects.push(
              project({
                last_scan: scan === null ? null : scanSummary(scan),
                last_scoring_run:
                  scoring === null
                    ? null
                    : scoringRunSummary(scoring, gateConfirmed ? '2026-08-12T09:30:00Z' : null),
                last_criterion_scoring_run:
                  criterion === null ? null : criterionRunSummary(criterion),
                category_selection_enabled: categoryEnabled,
              }),
            )
          }
        }
      }
    }
  }
  return projects
}

/** Die zwei Wortlaute, die KEINEN Schritt benennen, mit der Tabellenzeile, zu der sie gehoeren. */
const SONDERWORTLAUTE: Readonly<Record<string, StepId>> = {
  [STAND_OHNE_SCAN]: 'scan',
  [STAND_KATEGORIE_ABGESCHALTET]: 'ausschuss',
}

const SUFFIXES = [' läuft…', ' fehlgeschlagen'] as const

/**
 * Bildet den erzeugten TEXT auf seine Definition zurueck. Wirft, sobald ein Text weder aus
 * PIPELINE_STEPS noch aus der Ausnahmeliste stammt - eine stille zweite Textquelle ist damit
 * ausgeschlossen.
 */
function stepOfText(text: string): StepId {
  const exact = PIPELINE_STEPS.find((step) => step.label === text)
  if (exact !== undefined) {
    return exact.id
  }
  for (const suffix of SUFFIXES) {
    if (text.endsWith(suffix)) {
      const base = text.slice(0, text.length - suffix.length)
      const step = PIPELINE_STEPS.find((entry) => entry.label === base)
      if (step !== undefined) {
        return step.id
      }
    }
  }
  if (Object.hasOwn(SONDERWORTLAUTE, text)) {
    return SONDERWORTLAUTE[text]
  }
  throw new Error(`Unbekannter Wortlaut der Stand-Zeile: ${JSON.stringify(text)}`)
}

/** Der Text, den die Ausprägung traegt - `fertig` traegt keinen (er entsteht erst beim Zeichnen). */
function textOf(stand: ProjectStand): string | null {
  switch (stand.kind) {
    case 'weiter':
      return stand.stepLabel
    case 'lauf':
    case 'hinweis':
      return stand.label
    case 'fertig':
      return null
  }
}

type Descriptor = `${ProjectStand['kind']}|${StepId | '-'}|${ScanStatus | '-'}`

function descriptorOf(stand: ProjectStand): Descriptor {
  const text = textOf(stand)
  const step = text === null ? '-' : stepOfText(text)
  const runStatus = stand.kind === 'lauf' ? stand.status : '-'
  return `${stand.kind}|${step}|${runStatus}`
}

/**
 * Die zwoelf Zeilen der Wortlaut-Tabelle aus dem Abschnitt UI/UX der Spec 0375.
 *
 * `erreichbar: false` bei Randfall B ist kein Schlupfloch, sondern die Buchfuehrung ueber einen
 * BEWUSST vorweggenommenen Zustand: `kuratierung.isDone` ist ohne Abschlusssignal im Datenmodell
 * konstant `false`, also ist "jeder Schritt erledigt" heute strukturell unerreichbar. Die Zeile
 * wird trotzdem gebaut und ihre Darstellung direkt an ProjectStandLine geprueft; erreichbar wird
 * sie von selbst, sobald es ein Abschlusssignal gibt.
 */
const WORTLAUT_TABELLE: readonly { descriptor: Descriptor; erreichbar: boolean }[] = [
  { descriptor: 'hinweis|scan|-', erreichbar: true }, // Randfall A: Noch nicht gescannt
  { descriptor: 'lauf|scan|running', erreichbar: true },
  { descriptor: 'lauf|scan|failed', erreichbar: true },
  { descriptor: 'lauf|ausschuss|running', erreichbar: true },
  { descriptor: 'lauf|ausschuss|failed', erreichbar: true },
  { descriptor: 'weiter|ausschuss|-', erreichbar: true },
  { descriptor: 'lauf|kriterien|running', erreichbar: true },
  { descriptor: 'lauf|kriterien|failed', erreichbar: true },
  { descriptor: 'weiter|kriterien|-', erreichbar: true },
  { descriptor: 'weiter|kuratierung|-', erreichbar: true },
  { descriptor: 'hinweis|ausschuss|-', erreichbar: true }, // Randfall C: Kategorie-Bewertung aus
  { descriptor: 'fertig|-|-', erreichbar: false }, // Randfall B: Alles erledigt
]

describe('deriveProjectStand', () => {
  const projects = enumerateProjects()

  it('rechnet den Eingaberaum vollstaendig durch (256 Kombinationen)', () => {
    expect(projects).toHaveLength(256)
  })

  it('beobachtet ueber dem ganzen Eingaberaum GENAU die erreichbaren Zeilen der Tabelle', () => {
    const observed = new Set(projects.map((entry) => descriptorOf(deriveProjectStand(entry))))
    const expected = new Set(
      WORTLAUT_TABELLE.filter((row) => row.erreichbar).map((row) => row.descriptor),
    )

    // Beide Richtungen: `toEqual` auf sortierten Listen faengt sowohl ein vierzehntes Verhalten
    // als auch eine unerreichbar gewordene Zeile.
    expect([...observed].sort()).toEqual([...expected].sort())
  })

  it('erzeugt paarweise verschiedene Texte - keine zwei Zeilen lesen sich gleich', () => {
    const texts = projects
      .map((entry) => textOf(deriveProjectStand(entry)))
      .filter((text): text is string => text !== null)

    expect(new Set(texts).size).toBe(WORTLAUT_TABELLE.filter((row) => row.erreichbar).length)
  })

  it('haelt den Schluesselvorrat der Lauf-Zuordnung gegen PIPELINE_STEPS', () => {
    // Ein weiterer Schritt macht diesen Test rot, statt ohne Lauf-Zuordnung durchzurutschen.
    expect(Object.keys(RUN_FIELD_BY_STEP).sort()).toEqual(PIPELINE_STEPS.map((s) => s.id).sort())
  })

  it('laesst kuratierung nie in kind:"lauf" landen - nur sie traegt keinen Lauf', () => {
    expect(RUN_FIELD_BY_STEP.kuratierung).toBeNull()

    for (const entry of projects) {
      const stand = deriveProjectStand(entry)
      if (stand.kind === 'lauf') {
        expect(['scan', 'ausschuss', 'kriterien']).toContain(stepOfText(stand.label))
      }
    }
  })

  /*
   * Akzeptanzkriterium S1(i) - eine BINDUNGSzusicherung, keine unabhaengige zweite Messung: ihr
   * Wert liegt darin, dass eine spaetere eigenstaendige Nachrechnung des Schritts hier rot wird.
   * Zugleich Akzeptanzkriterium S2: der Klick auf die Karte fuehrt ueber `/projects/:id` auf
   * genau `getDefaultStepId`.
   */
  it('benennt nie einen anderen Schritt als den, auf den der Klick fuehrt', () => {
    for (const entry of projects) {
      const stand = deriveProjectStand(entry)
      const text = textOf(stand)
      if (text === null) {
        continue
      }

      expect(stepOfText(text)).toBe(getDefaultStepId(computeStepStates(entry)))
    }
  })

  /*
   * Akzeptanzkriterium A6, Nachweis (i). Randfall B haengt an "jeder Schritt ist isDone", NICHT
   * an "die Frontier-Suche lief leer" - die naheliegende Umsetzung ist bei abgeschaltetem
   * category_selection_enabled heute schon ausloesbar und behauptete Fertigkeit fuer ein
   * Projekt, das nur abgeschnitten ist.
   */
  it('liefert ueber dem ganzen Eingaberaum in keinem Fall kind:"fertig"', () => {
    for (const entry of projects) {
      expect(deriveProjectStand(entry).kind).not.toBe('fertig')
    }
  })

  /* Akzeptanzkriterium A6, Nachweis (ii) - der konkrete Fall, an dem die falsche Bedingung kippt. */
  it('nennt ein abgeschnittenes Projekt mit vollem sonstigen Fortschritt nicht "erledigt"', () => {
    const stand = deriveProjectStand(
      project({
        category_selection_enabled: false,
        last_scan: scanSummary('success'),
        last_scoring_run: scoringRunSummary('success', '2026-08-12T09:30:00Z'),
        last_criterion_scoring_run: null,
      }),
    )

    expect(stand).toEqual({ kind: 'hinweis', label: STAND_KATEGORIE_ABGESCHALTET })
  })

  /*
   * Randfall C spricht eine Aussage ueber das Feature-Flag aus. Dass sie nie faellt, waehrend das
   * Flag AN ist, ist die Bedingung dafuer, dass der Wortlaut nicht luegt.
   */
  it('zeigt "Kategorie-Bewertung ist abgeschaltet" nur bei ausgeschaltetem Feature-Flag', () => {
    for (const entry of projects) {
      const stand = deriveProjectStand(entry)
      if (stand.kind === 'hinweis' && stand.label === STAND_KATEGORIE_ABGESCHALTET) {
        expect(entry.category_selection_enabled).toBe(false)
      }
    }
  })

  it('greift Randfall C nur bei ERLEDIGTEM Ausschuss, nie bei bloss ausgeschaltetem Flag', () => {
    const stand = deriveProjectStand(
      project({
        category_selection_enabled: false,
        last_scan: scanSummary('success'),
        last_scoring_run: scoringRunSummary('success', null),
      }),
    )

    expect(stand).toEqual({ kind: 'weiter', stepLabel: 'Ausschuss' })
  })

  /*
   * Randfall A greift an `last_scan === null`, NICHT an "Frontier ist Scan": ein laufender oder
   * fehlgeschlagener Scan ist ebenfalls Frontier und traegt trotzdem seinen Lauf-Wortlaut.
   */
  it.each([
    ['running', 'Scan läuft…'],
    ['failed', 'Scan fehlgeschlagen'],
  ] as const)('zeigt bei einem %s Scan den Lauf statt "Noch nicht gescannt"', (status, label) => {
    const stand = deriveProjectStand(project({ last_scan: scanSummary(status) }))

    expect(stand).toEqual({ kind: 'lauf', status, label })
  })

  it('zeigt Randfall A, solange nie gescannt wurde', () => {
    expect(deriveProjectStand(project({ last_scan: null }))).toEqual({
      kind: 'hinweis',
      label: STAND_OHNE_SCAN,
    })
  })

  /*
   * Ein laufender Lauf auf einem Schritt, der nicht Frontier ist, wird NICHT gezeigt: die Zeile
   * beantwortet "wo mache ich weiter", nicht "laeuft irgendwo etwas".
   */
  it('zeigt einen laufenden Lauf nicht, wenn er nicht am Frontier-Schritt haengt', () => {
    const stand = deriveProjectStand(
      project({
        last_scan: null,
        last_criterion_scoring_run: criterionRunSummary('running'),
      }),
    )

    expect(stand).toEqual({ kind: 'hinweis', label: STAND_OHNE_SCAN })
  })

  it('nennt den Schrittnamen woertlich aus PIPELINE_STEPS - "Kuratierung", nicht das Altwort', () => {
    const stand = deriveProjectStand(
      project({
        last_scan: scanSummary('success'),
        last_scoring_run: scoringRunSummary('success', '2026-08-12T09:30:00Z'),
        last_criterion_scoring_run: criterionRunSummary('success'),
      }),
    )

    expect(stand).toEqual({ kind: 'weiter', stepLabel: 'Kuratierung' })
  })
})
