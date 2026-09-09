import type {
  ClassificationPhase,
  CloudPhaseSummaryOut,
  CriterionScoringRunSummary,
} from '../api/types'

/**
 * Die Ableitung "welche Teilschritte hat dieser Klassifizierungslauf, in welchem Zustand, mit
 * welchem Fortschritt" (specs/features/0348-klassifizierungs-transparenz.md,
 * decisions/0068-klassifizierungslauf-vier-teilschritte-und-laufeigene-cloud-bilanz.md).
 *
 * Reine Funktion in einer eigenen Datei statt Ableitungslogik im JSX - dasselbe Muster wie
 * `pipelineSteps.ts`. Die Zuordnung "welcher Zähler gehört zu welchem Teilschritt" ist der
 * fehleranfälligste Teil der Anzeige (zwei Cloud-Einträge, zwei lokale Schritte, vier Zustände);
 * im JSX wäre sie weder isoliert prüfbar noch bei einer Umgestaltung überlebensfähig.
 */

export type ClassificationStepId = ClassificationPhase
export type ClassificationStepState = 'pending' | 'running' | 'done' | 'skipped'

export interface ClassificationStep {
  id: ClassificationStepId
  label: string
  state: ClassificationStepState
  /** Abgesetzte Aufrufe bzw. verarbeitete Fotos. `null` = unbekannt, NIE als 0 behandeln. */
  processed: number | null
  /** `null` heisst "kein Total bekannt" - für `ranking` immer, dort gibt es keinen Balken. */
  total: number | null
  /** Der Bilanz-Eintrag dieses Teilschritts, oder `null` bei einem nicht-Cloud-Teilschritt. */
  cloud: CloudPhaseSummaryOut | null
}

/**
 * Die Ausführungsreihenfolge - die Anzeigereihenfolge ist eine Zusage DIESER Ableitung, nicht der
 * Serverantwort. Der Server liefert `cloud_phases` zwar ebenfalls geordnet; sich darauf zu
 * verlassen hiesse, dieselbe Zusage an zwei Stellen zu führen.
 */
export const CLASSIFICATION_STEP_ORDER = [
  'remote_categories',
  'criteria',
  'landmark',
  'ranking',
] as const satisfies readonly ClassificationStepId[]

const STEP_LABELS: Record<ClassificationStepId, string> = {
  remote_categories: 'Kategorie-Vorschläge',
  criteria: 'Kriterien-Bewertung',
  landmark: 'Sehenswürdigkeits-Erkennung',
  ranking: 'Rangfolge',
}

/** Die beiden Teilschritte, die Fotos an einen Cloud-Anbieter senden, samt ihres Bilanz-Zwecks. */
const CLOUD_PURPOSE_BY_STEP = {
  remote_categories: 'remote_category',
  landmark: 'landmark',
} as const

function isCloudStep(id: ClassificationStepId): id is keyof typeof CLOUD_PURPOSE_BY_STEP {
  return id in CLOUD_PURPOSE_BY_STEP
}

export function deriveClassificationSteps(
  run: CriterionScoringRunSummary
): ClassificationStep[] {
  const isFinished = run.status !== 'running'
  // `phase === null` heisst "läuft nicht mehr". Der Zeiger steht dann hinter dem letzten Schritt,
  // alle liegen davor und gelten als erledigt. Für einen GESCHEITERTEN Lauf ist das eine
  // Vereinfachung - wo genau er gescheitert ist, sagt die Zeile nicht -, und sie ist folgenlos:
  // die Teilschrittliste wird nur während des Laufs gezeigt, danach tritt die Bilanz an ihre
  // Stelle (die den Fehler über `error_message`/`cloud_error_message` benennt).
  //
  // Ein `phase`-Wert, den DIESES Bundle nicht kennt, faellt auf denselben Zweig: `indexOf` liefert
  // dann `-1`, und ohne Abfangen laege der Zeiger vor dem ersten Schritt - jeder Schritt stuende
  // auf `pending`, waehrend der Lauf arbeitet. Das ist kein theoretischer Fall: PhotoSort ist eine
  // PWA, Bundles werden gecacht, und genau diese Aenderung haengt zwei Werte an den Enum an. Ein
  // alter Client saehe waehrend der Landmark-Phase "nichts passiert" statt des Fortschritts.
  // Neue Phasen werden angehaengt, also ist "alle BEKANNTEN Schritte liegen dahinter" die richtige
  // Naeherung - der unbekannte Schritt selbst kann ohnehin nicht angezeigt werden, weil er in der
  // Reihenfolge dieses Bundles fehlt (Copilot-Fund PR #367).
  const phaseIndex =
    run.phase === null ? -1 : CLASSIFICATION_STEP_ORDER.indexOf(run.phase)
  const currentIndex = phaseIndex === -1 ? CLASSIFICATION_STEP_ORDER.length : phaseIndex

  const steps: ClassificationStep[] = []

  for (const [index, id] of CLASSIFICATION_STEP_ORDER.entries()) {
    if (isCloudStep(id) && !run.cloud_requested) {
      // Ohne angeforderte Cloud-Nutzung hat der Teilschritt nie zur Disposition gestanden. Ihn
      // als "übersprungen" zu zeigen behauptete eine Auslassung, wo es keine Absicht gab.
      continue
    }

    const cloud = isCloudStep(id)
      ? (run.cloud_phases.find((phase) => phase.purpose === CLOUD_PURPOSE_BY_STEP[id]) ?? null)
      : null

    steps.push({
      id,
      label: STEP_LABELS[id],
      state: deriveState({ index, currentIndex, isFinished, isCloudStep: isCloudStep(id), cloud }),
      ...progressOf(id, run, cloud),
      cloud,
    })
  }

  return steps
}

function deriveState({
  index,
  currentIndex,
  isFinished,
  isCloudStep: isCloud,
  cloud,
}: {
  index: number
  currentIndex: number
  isFinished: boolean
  isCloudStep: boolean
  cloud: CloudPhaseSummaryOut | null
}): ClassificationStepState {
  // "Übersprungen" ist ausschliesslich eine Aussage über einen BEENDETEN Lauf: der Teilschritt war
  // angefordert, hat aber keine Spur hinterlassen - ein Altlauf ohne Bilanz oder eine zwischen
  // Auslösen und Start entzogene Einwilligung. Während des Laufs fehlt der Eintrag schlicht noch.
  if (isCloud && isFinished && cloud === null) {
    return 'skipped'
  }
  if (index < currentIndex) {
    return 'done'
  }
  if (index === currentIndex) {
    return 'running'
  }
  return 'pending'
}

function progressOf(
  id: ClassificationStepId,
  run: CriterionScoringRunSummary,
  cloud: CloudPhaseSummaryOut | null
): { processed: number | null; total: number | null } {
  if (isCloudStep(id)) {
    // Jeder Cloud-Teilschritt liest ausschliesslich SEINEN eigenen Eintrag - die beiden Quellen
    // sind nie geteilt, sonst bewegte sich die eine Zeile mit der anderen mit.
    return { processed: cloud?.photos_processed ?? null, total: cloud?.photos_total ?? null }
  }
  if (id === 'criteria') {
    return { processed: run.photos_processed, total: run.photos_total }
  }
  // `ranking` kennt kein Total: die Kategorieableitung läuft über Partitionen, nicht über eine
  // gezählte Fotomenge. `null` heisst hier "unbestimmter Fortschritt", und die Anzeige zeichnet
  // dort bewusst keinen Balken statt einen bei 0 % oder 100 %.
  return { processed: null, total: null }
}
