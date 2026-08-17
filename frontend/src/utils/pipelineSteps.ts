import type { ProjectOut } from '../api/types'

export type StepId = 'scan' | 'ausschuss' | 'gate' | 'kriterien' | 'kuratierung'

export interface PipelineStepDefinition {
  id: StepId
  label: string
}

// Einzige Quelle der Wahrheit fuer Anzeigereihenfolge UND Routing-Zuordnung
// (specs/features/0042-automatisierter-flow-stepper-detailseiten.md, Architektur-Abschnitt) -
// sowohl der Stepper (Anzeigereihenfolge) als auch PipelineStepView (Komponenten-Zuordnung) und
// App.tsx (Routing-Erzeugung analog zum bestehenden PROJECT_ROUTES-Muster) leiten sich aus dieser
// Liste ab, statt die fuenf IDs an mehreren Stellen unabhaengig zu wiederholen.
export const PIPELINE_STEPS: readonly PipelineStepDefinition[] = [
  { id: 'scan', label: 'Scan' },
  { id: 'ausschuss', label: 'Ausschuss-Erkennung' },
  { id: 'gate', label: 'Ausschuss-Gate' },
  { id: 'kriterien', label: 'Kriterien-Bewertung' },
  { id: 'kuratierung', label: 'Kategorie-Kuratierung' },
]

export interface PipelineStepState {
  id: StepId
  isDone: boolean
  isReachable: boolean
}

export function isStepId(value: string): value is StepId {
  return PIPELINE_STEPS.some((step) => step.id === value)
}

/**
 * Leitet den vollstaendigen Pipeline-Fortschritt ausschliesslich aus bereits vorhandenen
 * `ProjectOut`-Feldern ab (Akzeptanzkriterium 3 der Spec 0042) - 1:1 aus dem bisherigen,
 * produktiven Gating-Verhalten von ProjectDetailPage.tsx uebernommen (siehe dortige, jetzt
 * entfernte isGateSectionActive/isCriteriaGateDisabled/isCurationAvailable-Ableitungen), keine
 * neue/strengere Logik. Kein Seiteneffekt, kein Fetch (analog utils/timeOfDay.ts,
 * utils/qualityLevel.ts).
 */
export function computeStepStates(project: ProjectOut): PipelineStepState[] {
  const gateConfirmedAt = project.last_scoring_run?.gate_confirmed_at ?? null
  const isAusschussDone = project.last_scoring_run?.status === 'success'
  const isKriterienDone = project.last_criterion_scoring_run?.status === 'success'
  const isKriterienReachable =
    project.category_selection_enabled === true && gateConfirmedAt !== null

  return [
    { id: 'scan', isDone: project.last_scan?.status === 'success', isReachable: true },
    // Bewusst ungegatet (Akzeptanzkriterium 3, Abschnitt "Entscheidungen"): der "Ausschuss
    // aussortieren"-Button war nie an last_scan.status gekoppelt - kein neues, strengeres Gate.
    { id: 'ausschuss', isDone: isAusschussDone, isReachable: true },
    { id: 'gate', isDone: gateConfirmedAt !== null, isReachable: isAusschussDone },
    { id: 'kriterien', isDone: isKriterienDone, isReachable: isKriterienReachable },
    // Kein Abschlusssignal im Datenmodell fuer einen offenen Review-Prozess (Akzeptanzkriterium
    // 3) - isDone bleibt konstant false, unabhaengig vom Kriterien-Bewertungsstatus.
    { id: 'kuratierung', isDone: false, isReachable: isKriterienDone },
  ]
}

const FALLBACK_STEP_ID: StepId = 'kuratierung'

/**
 * Gemeinsame Ableitung fuer getDefaultStepId/getHighestReachableStepId - technische
 * Detailentscheidung innerhalb der akzeptierten Spec: Akzeptanzkriterium 4 fordert explizit, dass
 * beide Funktionen fuer dieselbe Zustandskombination dasselbe Ziel liefern ("Basis-Route ohne
 * :step und ein unerreichbarer Deep-Link landen konsistent am selben Ort"). Eine woertliche
 * Umsetzung von getHighestReachableStepId als "letzter erreichbarer Schritt in Reihenfolge,
 * UNABHAENGIG vom isDone-Status" widerspricht dieser Vorgabe in einem realen, durch
 * Akzeptanzkriterium 3 bewusst zugelassenen Fall: `ausschuss` ist IMMER erreichbar, auch bevor
 * `scan` erledigt ist (kein neues Gate). Bei einem frisch angelegten Projekt (nichts erledigt)
 * waeren `scan` (erster erreichbarer, noch nicht erledigter Schritt) und `ausschuss` (woertlich
 * "letzter erreichbarer Schritt in Reihenfolge", da `scan` UND `ausschuss` beide erreichbar sind)
 * zwei VERSCHIEDENE Ziele - genau der in Akzeptanzkriterium 4 ausgeschlossene Fall. Beide
 * oeffentlichen Funktionen nutzen deshalb dieselbe "Frontier"-Ableitung: der erste erreichbare,
 * noch nicht erledigte Schritt; fehlt ein solcher (z.B. Kriterien-Bewertung durch dauerhaft
 * ausgeschaltetes Feature-Flag nie gelaufen und nie erreichbar), der jeweils letzte erreichbare
 * Schritt, sonst der feste Fallback `kuratierung`.
 */
function getFrontierStepId(states: PipelineStepState[]): StepId {
  const frontier = states.find((step) => step.isReachable && !step.isDone)
  if (frontier) {
    return frontier.id
  }
  const reachableSteps = states.filter((step) => step.isReachable)
  return reachableSteps.length > 0
    ? reachableSteps[reachableSteps.length - 1].id
    : FALLBACK_STEP_ID
}

export function getDefaultStepId(states: PipelineStepState[]): StepId {
  return getFrontierStepId(states)
}

export function getHighestReachableStepId(states: PipelineStepState[]): StepId {
  return getFrontierStepId(states)
}

/**
 * Erklaertext fuer einen aktuell blockierten Schritt (Akzeptanzkriterium 5, Stepper-Popover) -
 * 1:1 aus den bisherigen Erklaertexten von ProjectDetailPage.tsx uebernommen. `scan`/`ausschuss`
 * sind nie blockiert (siehe computeStepStates), der leere Default-Fall wird deshalb praktisch nie
 * gerendert - nur als defensiver Fallback vorhanden.
 */
export function getBlockedReason(id: StepId, project: ProjectOut): string {
  switch (id) {
    case 'gate':
      return 'Sichte zuerst den Ausschuss oben.'
    case 'kriterien':
      return project.category_selection_enabled === false
        ? 'Diese Funktion ist derzeit nicht aktiviert.'
        : 'Bestätige zuerst den Ausschuss oben.'
    case 'kuratierung':
      return 'Führe zuerst die Kriterien-Bewertung oben aus.'
    default:
      return ''
  }
}
