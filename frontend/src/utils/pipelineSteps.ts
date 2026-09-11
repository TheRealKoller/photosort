import type { ProjectOut } from '../api/types'

export type StepId = 'scan' | 'ausschuss' | 'gate' | 'kriterien' | 'kuratierung'

export interface PipelineStepDefinition {
  id: StepId
  label: string
}

// Einzige Quelle der Wahrheit fuer Anzeigereihenfolge UND Routing-Zuordnung - sowohl der Stepper
// (Anzeigereihenfolge) als auch PipelineStepView (Komponenten-Zuordnung) und App.tsx
// (Routing-Erzeugung) leiten sich aus dieser Liste ab, statt die fuenf IDs an mehreren Stellen
// unabhaengig zu wiederholen.
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
 * `ProjectOut`-Feldern ab. Kein Seiteneffekt, kein Fetch.
 */
export function computeStepStates(project: ProjectOut): PipelineStepState[] {
  const gateConfirmedAt = project.last_scoring_run?.gate_confirmed_at ?? null
  const isAusschussDone = project.last_scoring_run?.status === 'success'
  const isKriterienDone = project.last_criterion_scoring_run?.status === 'success'
  const isKriterienReachable =
    project.category_selection_enabled === true && gateConfirmedAt !== null

  return [
    { id: 'scan', isDone: project.last_scan?.status === 'success', isReachable: true },
    // Bewusst ungegatet: `ausschuss` wird nicht an last_scan.status gekoppelt.
    { id: 'ausschuss', isDone: isAusschussDone, isReachable: true },
    { id: 'gate', isDone: gateConfirmedAt !== null, isReachable: isAusschussDone },
    { id: 'kriterien', isDone: isKriterienDone, isReachable: isKriterienReachable },
    // Kein Abschlusssignal im Datenmodell fuer einen offenen Review-Prozess - isDone bleibt
    // konstant false, unabhaengig vom Kriterien-Bewertungsstatus.
    { id: 'kuratierung', isDone: false, isReachable: isKriterienDone },
  ]
}

const FALLBACK_STEP_ID: StepId = 'kuratierung'

/**
 * Gemeinsame Ableitung fuer getDefaultStepId/getHighestReachableStepId. Beide MUESSEN fuer
 * dieselbe Zustandskombination dasselbe Ziel liefern: eine Basis-Route ohne :step und ein
 * unerreichbarer Deep-Link landen am selben Ort.
 *
 * getHighestReachableStepId deshalb NICHT woertlich als "letzter erreichbarer Schritt in
 * Reihenfolge, UNABHAENGIG vom isDone-Status" umsetzen: `ausschuss` ist IMMER erreichbar, auch
 * bevor `scan` erledigt ist. Bei einem frisch angelegten Projekt lieferten die beiden Funktionen
 * dann `scan` und `ausschuss` - zwei verschiedene Ziele.
 *
 * Die gemeinsame "Frontier"-Ableitung ist: der erste erreichbare, noch nicht erledigte Schritt;
 * fehlt ein solcher (z.B. Kriterien-Bewertung durch dauerhaft ausgeschaltetes Feature-Flag nie
 * gelaufen und nie erreichbar), der jeweils letzte erreichbare Schritt, sonst der feste Fallback
 * `kuratierung`.
 */
function getFrontierStepId(states: PipelineStepState[]): StepId {
  const frontier = states.find((step) => step.isReachable && !step.isDone)
  if (frontier) {
    return frontier.id
  }
  const reachableSteps = states.filter((step) => step.isReachable)
  return reachableSteps.length > 0 ? reachableSteps[reachableSteps.length - 1].id : FALLBACK_STEP_ID
}

export function getDefaultStepId(states: PipelineStepState[]): StepId {
  return getFrontierStepId(states)
}

export function getHighestReachableStepId(states: PipelineStepState[]): StepId {
  return getFrontierStepId(states)
}

/**
 * Erklaertext fuer einen aktuell blockierten Schritt (Stepper-Popover). `scan`/`ausschuss` sind
 * nie blockiert (siehe computeStepStates), der leere Default-Fall wird deshalb praktisch nie
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

export interface StepProgress {
  value: number
  max: number
}

/**
 * Fuellung des Fortschrittsbalkens unter der Schrittleiste.
 *
 * REINE FUNKTION STATT AUSDRUCK IM JSX: Der Balken ist ein natives `<progress value max>`, ein
 * berechneter Prozentwert liesse sich weder als Tailwind-Klasse noch als Inline-Style
 * ausdruecken. Die Skala ist bewusst doppelt so fein wie die Schrittzahl: `2 * index + 1` von
 * `2 * n` ist exakt die MITTE der `index`-ten von `n` gleich breiten Spalten - also
 * 10/30/50/70/90 % bei fuenf Schritten. Genau darauf beruht die Zusage, dass die rechte Kante der
 * Fuellung unter der Mitte des aktuellen Schritts liegt; die gleich breiten, abstandslosen
 * Spalten in Stepper.tsx sind dafuer tragende Geometrie.
 *
 * `max` wird aus PIPELINE_STEPS abgeleitet, nicht als Konstante gefuehrt - eine sechste Stufe
 * veraendert damit automatisch die Skala statt sie still zu verschieben. Ein unbrauchbarer Index
 * (kein aktiver Schritt, Deep-Link auf eine unbekannte Stufe) liefert 0: der Balken ist dann leer
 * statt zufaellig gefuellt.
 */
export function stepProgress(activeIndex: number): StepProgress {
  const max = 2 * PIPELINE_STEPS.length
  const isUsable =
    Number.isInteger(activeIndex) && activeIndex >= 0 && activeIndex < PIPELINE_STEPS.length
  return { value: isUsable ? 2 * activeIndex + 1 : 0, max }
}
