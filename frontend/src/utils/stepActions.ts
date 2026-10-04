import type { ProjectOut } from '../api/types'
import { computeStepStates, PIPELINE_STEPS, RUN_FIELD_BY_STEP, type StepId } from './pipelineSteps'
import {
  ALBUM_OPEN_LABEL,
  AUSSCHUSS_CONFIRM_LABEL,
  NEXT_STEP_LABELS,
  NEXT_UNAVAILABLE_TEXT,
  RUN_STEP_TEXTS,
} from './stepActionTexts'

/** Die eine Hauptaktion einer Schrittseite. */
export type StepAction =
  | { kind: 'start'; label: string }
  | { kind: 'running'; label: string }
  | { kind: 'retry'; label: string }
  | { kind: 'confirm'; label: string; openCount: number | null }
  | { kind: 'next'; label: string; to: string }
  | { kind: 'nextUnavailable'; text: string }
  | { kind: 'open'; label: string; to: string }

export type StepActionKind = StepAction['kind']

export interface StepActionState {
  action: StepAction
  /** Der nachrangige „Erneut …"-Knopf - genau nach einem erfolgreichen letzten Lauf. */
  rerun: { label: string; explanation: string } | null
}

export interface StepActionInput {
  /** Offene Ausschuss-Vorschläge; `null`, solange der Bestand nicht geladen ist. */
  openCount: number | null
  /** Ausgelöst, aber noch keine Laufantwort (Mutation offen bzw. `useTriggerConfirmation`). */
  isTriggerPending: boolean
}

export function ausschussConfirmLabel(openCount: number | null): string {
  if (openCount === null || openCount === 0) {
    return AUSSCHUSS_CONFIRM_LABEL
  }
  const count = openCount === 1 ? '1 Vorschlag' : `${openCount} Vorschläge`
  return `${count} als Ausschuss übernehmen und abschließen`
}

/**
 * Die Hauptaktion je Schritt und Zustand (Tabelle der Spec 0568).
 *
 * KENNT KEINE EIGENE ERREICHBARKEITSREGEL: Ob es weitergeht, sagt `isReachable` des Folgeschritts
 * aus `computeStepStates`. Bei einem Fehlschlag gibt es kein „Erneut …", auch wenn ein früherer
 * Lauf erfolgreich war - sonst stünden zwei Wiederholungen auf der Seite.
 */
export function deriveStepAction(
  stepId: StepId,
  project: ProjectOut,
  { openCount, isTriggerPending }: StepActionInput,
): StepActionState {
  if (stepId === 'kuratierung') {
    return {
      action: { kind: 'open', label: ALBUM_OPEN_LABEL, to: `/projects/${project.id}/album` },
      rerun: null,
    }
  }

  const texts = RUN_STEP_TEXTS[stepId]
  const status = project[RUN_FIELD_BY_STEP[stepId]]?.status ?? null
  const rerun = status === 'success' ? texts.rerun : null

  if (isTriggerPending || status === 'running') {
    return { action: { kind: 'running', label: texts.running }, rerun }
  }
  if (status === 'failed') {
    return { action: { kind: 'retry', label: texts.start }, rerun: null }
  }
  if (status === null) {
    return { action: { kind: 'start', label: texts.start }, rerun: null }
  }

  if (stepId === 'ausschuss') {
    const gateConfirmedAt = project.last_scoring_run?.gate_confirmed_at ?? null
    // Eine unbekannte Anzahl (Bestand lädt oder ist nicht ladbar) zählt als „möglicherweise
    // offen": Ein Weiter-Link an dieser Stelle führte an offenen Vorschlägen vorbei.
    if (gateConfirmedAt === null || openCount === null || openCount > 0) {
      return {
        action: { kind: 'confirm', label: ausschussConfirmLabel(openCount), openCount },
        rerun,
      }
    }
  }

  const index = PIPELINE_STEPS.findIndex((step) => step.id === stepId)
  const nextId = PIPELINE_STEPS[index + 1].id as Exclude<StepId, 'scan'>
  const isNextReachable = computeStepStates(project).some(
    (state) => state.id === nextId && state.isReachable,
  )
  return {
    action: isNextReachable
      ? {
          kind: 'next',
          label: NEXT_STEP_LABELS[nextId],
          to: `/projects/${project.id}/pipeline/${nextId}`,
        }
      : { kind: 'nextUnavailable', text: NEXT_UNAVAILABLE_TEXT },
    rerun,
  }
}
