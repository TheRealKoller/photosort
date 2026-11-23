import type { ProjectOut, ScanStatus } from '../api/types'
import {
  PIPELINE_STEPS,
  STAND_KLASSIFIZIERUNG_ABGESCHALTET,
  STAND_OHNE_SCAN,
  type ProjectStand,
  type StepId,
} from '../utils/pipelineSteps'
import { makeProject } from './fixtures'

/*
 * Der vollständig aufgezählte Eingaberaum der Schrittzustände und die Rückabbildung der
 * Stand-Zeile auf ihren Schritt - gemeinsam genutzt von den Tests der Stand-Zeile
 * (`pipelineSteps.test.ts`) und der Ablaufübersicht, damit beide über DENSELBEN Lagen geprüft
 * werden. Zwei getrennte Aufzählungen liefen beim nächsten neuen Feld still auseinander.
 */

const RUN_STATES: readonly (ScanStatus | null)[] = [
  null,
  'queued',
  'running',
  'success',
  'failed',
  'cancelled',
]

export function scanSummary(status: ScanStatus): ProjectOut['last_scan'] {
  return { status, id: 1, cancel_requested_at: null } as ProjectOut['last_scan']
}

export function scoringRunSummary(
  status: ScanStatus,
  gateConfirmedAt: string | null,
): ProjectOut['last_scoring_run'] {
  return {
    status,
    id: 1,
    gate_confirmed_at: gateConfirmedAt,
    cancel_requested_at: null,
  } as ProjectOut['last_scoring_run']
}

export function criterionRunSummary(status: ScanStatus): ProjectOut['last_criterion_scoring_run'] {
  return { status, id: 1, cancel_requested_at: null } as ProjectOut['last_criterion_scoring_run']
}

/**
 * Der vollständig aufgezählte Eingaberaum: 6 Scan-Zustände x 6 Ausschuss-Zustände x 2
 * Gate-Zustände x 6 Kriterien-Zustände x 2 Feature-Flag-Zustände = 864 Projekte. Neu seit
 * Spec 0641: `queued` und `cancelled` sind eigene Zustände, keine Variante von `running` bzw.
 * `failed`.
 */
export function enumerateProjects(): ProjectOut[] {
  const projects: ProjectOut[] = []
  for (const scan of RUN_STATES) {
    for (const scoring of RUN_STATES) {
      for (const gateConfirmed of [false, true]) {
        for (const criterion of RUN_STATES) {
          for (const categoryEnabled of [false, true]) {
            projects.push(
              makeProject({
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

/** Die zwei Wortlaute, die KEINEN Schritt benennen, mit der Tabellenzeile, zu der sie gehören. */
export const SONDERWORTLAUTE: Readonly<Record<string, StepId>> = {
  [STAND_OHNE_SCAN]: 'scan',
  [STAND_KLASSIFIZIERUNG_ABGESCHALTET]: 'ausschuss',
}

const SUFFIXES = [' läuft…', ' fehlgeschlagen', ' wartet', ' abgebrochen'] as const

/**
 * Bildet den erzeugten TEXT auf seine Definition zurück. Wirft, sobald ein Text weder aus
 * PIPELINE_STEPS noch aus der Ausnahmeliste stammt - eine stille zweite Textquelle ist damit
 * ausgeschlossen.
 */
export function stepOfText(text: string): StepId {
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

/** Der Text, den die Ausprägung trägt - `fertig` trägt keinen (er entsteht erst beim Zeichnen). */
export function textOf(stand: ProjectStand): string | null {
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
