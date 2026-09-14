import type { ProjectOut, ScanStatus } from '../api/types'
import { deriveScanStatus } from './scanStatus'

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
  { id: 'kuratierung', label: 'Kuratierung' },
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

/**
 * Der Bearbeitungsstand eines Projekts, wie ihn die Projektkarte in EINER Zeile zeigt.
 *
 * Eine unterscheidbare Union statt einer vorformatierten Zeichenkette: die Zeile braucht Präfix,
 * Schriftschnitt und Kennzeichen-Optik getrennt. Der Text zu `fertig` entsteht erst beim Zeichnen
 * (ProjectStandLine) - hier gäbe es für ihn keine zweite Information zu tragen.
 */
export type ProjectStand =
  | { kind: 'weiter'; stepLabel: string }
  | { kind: 'hinweis'; label: string }
  | { kind: 'lauf'; status: 'running' | 'failed'; label: string }
  | { kind: 'fertig' }

/**
 * Welcher Lauf zu welchem Schritt gehört; `null` heißt „dieser Schritt trägt keinen Lauf".
 *
 * Die Zuordnung ist die unabhängige Sollgröße der Stand-Zeile - nicht der Wortlaut, der aus
 * `PIPELINE_STEPS[].label` kommt. Als `Record<StepId, …>` typisiert, damit ein sechster Schritt
 * hier einen Typfehler auslöst statt ohne Zuordnung durchzurutschen.
 */
export const RUN_FIELD_BY_STEP = {
  scan: 'last_scan',
  ausschuss: 'last_scoring_run',
  gate: null,
  kriterien: 'last_criterion_scoring_run',
  kuratierung: null,
} as const satisfies Record<
  StepId,
  'last_scan' | 'last_scoring_run' | 'last_criterion_scoring_run' | null
>

/** Randfall A. Ein Projekt, in dem noch nie etwas passiert ist, hat keinen *nächsten* Schritt,
 * sondern noch gar keinen - deshalb ausdrücklich nicht „Weiter: Scan". */
export const STAND_OHNE_SCAN = 'Noch nicht gescannt'

/** Randfall C. */
export const STAND_KATEGORIE_ABGESCHALTET = 'Kategorie-Bewertung ist abgeschaltet'

function stepLabelOf(id: StepId): string {
  const step = PIPELINE_STEPS.find((entry) => entry.id === id)
  return step === undefined ? id : step.label
}

/** Der Status des Laufs, der zu genau diesem Schritt gehört - `null`, wenn er keinen trägt oder
 * noch keiner existiert. */
function runStatusOfStep(project: ProjectOut, id: StepId): ScanStatus | null {
  const field = RUN_FIELD_BY_STEP[id]
  if (field === null) {
    return null
  }
  return project[field]?.status ?? null
}

/**
 * Der Bearbeitungsstand eines Projekts für die Stand-Zeile der Projektkarte.
 *
 * RUFT `computeStepStates` UND DIE FRONTIER-ABLEITUNG AUF UND RECHNET NICHTS NACH. Damit ist die
 * Zusage „der Klick landet auf dem Schritt, den die Zeile benennt" strukturell erfüllt statt durch
 * Nachhalten: dieselbe Ableitung bestimmt das Ziel der Weiterleitung von `/projects/:id`. Laufen
 * beide auseinander, benennt die Karte einen Schritt und führt auf einen anderen; nichts schlägt
 * dabei fehl, es stimmt nur nicht mehr.
 *
 * Die Zuordnung ist zweistufig und deshalb vollzählig: erst der Frontier-Schritt, dann der Lauf,
 * der zu genau diesem Schritt gehört. Ein Lauf auf einem Schritt, der nicht Frontier ist, wird
 * nicht gezeigt - die Zeile beantwortet „wo mache ich weiter", nicht „läuft irgendwo etwas".
 *
 * Drei Randfälle, jeder mit einer eigenen Bedingung:
 *
 * - **A** (`hinweis`): noch nie gescannt.
 * - **B** (`fertig`): JEDER Schritt ist `isDone` - ausdrücklich NICHT „die Frontier-Suche lief
 *   leer". Bei ausgeschaltetem `category_selection_enabled` läuft die Suche heute schon leer;
 *   ein daran gebundener Abschluss behauptete Fertigkeit für ein Projekt, das nur abgeschnitten
 *   ist. Weil `kuratierung.isDone` ohne Abschlusssignal konstant `false` ist, bleibt der Zustand
 *   heute unerreichbar und wird von selbst erreichbar, sobald es eines gibt.
 * - **C** (`hinweis`): die Frontier-Suche ist auf einen bereits ERLEDIGTEN Schritt
 *   zurückgefallen. Das kann nur bei ausgeschaltetem `category_selection_enabled` passieren (mit
 *   eingeschaltetem Flag gibt es immer einen erreichbaren offenen Schritt), und dort stünde sonst
 *   ein irreführendes „Weiter: Ausschuss-Gate" auf einem Schritt, der längst erledigt ist. Die
 *   Zeile benennt in diesem Fall keinen Schritt; das Klickziel bleibt unverändert das Gate.
 *   Geprüft wird der Rückfall selbst und nicht das Flag, weil genau der Rückfall die irreführende
 *   Lage ist: ein abgeschaltetes Flag bei noch offenem Gate oder erreichbarer Kuratierung hat
 *   sehr wohl einen nächsten Schritt und nennt ihn.
 */
export function deriveProjectStand(project: ProjectOut): ProjectStand {
  const states = computeStepStates(project)

  if (states.every((step) => step.isDone)) {
    return { kind: 'fertig' }
  }

  const frontierId = getDefaultStepId(states)
  if (states.find((step) => step.id === frontierId)?.isDone === true) {
    return { kind: 'hinweis', label: STAND_KATEGORIE_ABGESCHALTET }
  }

  if (frontierId === 'scan' && deriveScanStatus(project) === 'never') {
    return { kind: 'hinweis', label: STAND_OHNE_SCAN }
  }

  // Die Zusätze werden ANGEHÄNGT statt getippt - der Schrittname kommt wörtlich aus
  // `PIPELINE_STEPS[].label`, es wird kein neues Vokabular erfunden.
  const stepLabel = stepLabelOf(frontierId)
  switch (runStatusOfStep(project, frontierId)) {
    case 'running':
      return { kind: 'lauf', status: 'running', label: `${stepLabel} läuft…` }
    case 'failed':
      return { kind: 'lauf', status: 'failed', label: `${stepLabel} fehlgeschlagen` }
    // `success` kann am Frontier-Schritt nicht auftreten: ein erfolgreicher Lauf macht seinen
    // Schritt `isDone`, und ein erledigter Schritt ist nicht Frontier.
    default:
      return { kind: 'weiter', stepLabel }
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
