import type {
  MotifAssessmentOut,
  MotifKey,
  MotifSetOut,
  MotifStrengthBandsOut,
  MotifStrengthOut,
} from '../api/types'
import { criterionPercentValue, formatCriterionPercent } from './formatStats'
import { formatMotifKey, isLocallyAssessable } from './motifLabels'

/** Der Satz statt der Motivreihe, solange ein Foto keinen Klassifizierungslauf gesehen hat. */
export const UNASSESSED_TEXT =
  'Noch nicht klassifiziert — dieses Foto hat noch keinen Klassifizierungslauf gesehen.'

const NOT_LOCALLY_ASSESSABLE_TEXT = 'lokal nicht beurteilbar'

/** Die vier Fuellstufen eines Motivsymbols. `none` heisst: kein Farbanteil, nur der Umriss. */
export type MotifFillStep = 'strong' | 'medium' | 'weak' | 'none'

/**
 * Die Fuellstufe eines Motivsymbols aus der wirksamen Staerke gegen die Baender aus `GET /motifs`
 * (ADR 0113 Punkt 1).
 *
 * `MotifStrengthOut.present` wird dafuer NIE gelesen: Die Praesenzgrenze 0.5 liegt mitten im
 * mittleren Band, aus beiden Skalen zugleich waere dieselbe Staerke einmal "mittel" und einmal
 * "nicht vertreten" und die Stufe "schwach" unerreichbar.
 *
 * Beide Grenzen sind EINSCHLIESSEND (`>=`), genau wie im Backend. Die Baender kommen als
 * EXPLIZITER Parameter herein - eine modul-globale, vom Query-Cache befuellte Skala machte die
 * Funktion nur noch mit Query-Zustand testbar (dieselbe Festlegung wie in `utils/motifLabels.ts`).
 *
 * `assessable === false` (lokale Grundlage, Motiv ohne Cloud-Aussage) ergibt `none` VOR jeder
 * Stufung: In der Reihe traegt dieser Fall dieselbe leere Fuellung wie "gar nicht vertreten",
 * unterschieden wird er in der aufgeklappten Zeile (AK7).
 */
export function motifFillStep(
  strength: number,
  bands: MotifStrengthBandsOut,
  assessable: boolean,
): MotifFillStep {
  if (!assessable || strength <= 0) {
    return 'none'
  }
  if (strength >= bands.strong) {
    return 'strong'
  }
  if (strength >= bands.medium) {
    return 'medium'
  }
  return 'weak'
}

export type MotifCorrectionState = 'applies' | 'rejected' | undefined

export function motifCorrectionState(correction: boolean | null): MotifCorrectionState {
  // Auf `=== null` geprueft, nie auf Falsyness: `false` ist eine Aussage, keine Abwesenheit.
  if (correction === null) {
    return undefined
  }
  return correction ? 'applies' : 'rejected'
}

/** Was an der Stelle des Werts steht - im zugaenglichen Namen des Symbols wie in der Detailzeile. */
export interface MotifValueText {
  text: string
  mono: boolean
}

function motifValueText(
  strength: MotifStrengthOut | undefined,
  showLocalGap: boolean,
): MotifValueText {
  const state = motifCorrectionState(strength?.correction ?? null)
  if (state !== undefined) {
    // STATT der Prozentzahl - die ueberstimmte Modellzahl steht nicht daneben.
    return {
      text: state === 'applies' ? 'Trifft zu (korrigiert)' : 'Trifft nicht zu (korrigiert)',
      mono: false,
    }
  }
  if (showLocalGap) {
    // Ein `0 %` waere hier die Aussage "nicht zu sehen" statt "nicht angesehen".
    return { text: NOT_LOCALLY_ASSESSABLE_TEXT, mono: false }
  }
  return { text: formatCriterionPercent(strength?.strength ?? 0), mono: true }
}

/** Die Anzeige eines Motivs in der Fuellstandsreihe. */
export interface MotifStrengthEntry {
  key: MotifKey
  displayName: string
  step: MotifFillStep
  /** Fuellhoehe, aus DERSELBEN Rundung wie die angezeigte Zahl. */
  fillPercent: number
  value: MotifValueText
  correctionState: MotifCorrectionState
}

/**
 * Die acht Motive eines klassifizierten Fotos in REGISTRY-Reihenfolge. EINE Ableitung fuer die
 * bedienbare Reihe (`MotifStrengthSection`) und die schreibgeschuetzte (`MotifStrengthRow`): Der
 * zugaengliche Name "{Motiv}: {Wert}" entsteht nur hier, und zwei getrennte Ableitungen liefen
 * still auseinander. Die Staerke wird je Schluessel nachgeschlagen, nie ueber den Index.
 */
export function motifStrengthEntries(
  motifSet: MotifSetOut,
  assessment: MotifAssessmentOut,
  motifs: readonly MotifStrengthOut[] | undefined,
): MotifStrengthEntry[] {
  const byKey = new Map((motifs ?? []).map((entry) => [entry.key, entry]))
  return motifSet.items.map((item) => {
    const strength = byKey.get(item.key)
    const showLocalGap =
      assessment.source === 'local' && !isLocallyAssessable(item.key, motifSet.items)
    const step = motifFillStep(strength?.strength ?? 0, motifSet.strength_bands, !showLocalGap)
    return {
      key: item.key,
      displayName: formatMotifKey(item.key, motifSet.items),
      step,
      // Bei `none` (Staerke 0 oder lokal nicht beurteilbar) bleibt die Fuellebene leer - eine
      // ungefaerbte Fuellung erbte sonst die Textfarbe und behauptete eine Staerke.
      fillPercent: step === 'none' ? 0 : criterionPercentValue(strength?.strength ?? 0),
      value: motifValueText(strength, showLocalGap),
      correctionState: motifCorrectionState(strength?.correction ?? null),
    }
  })
}
