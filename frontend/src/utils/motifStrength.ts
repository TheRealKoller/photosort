import type { MotifStrengthBandsOut } from '../api/types'

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
