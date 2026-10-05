import { curationRows } from '../utils/curationLayout'
import type { JustifiedRow } from '../utils/justifiedRows'
import { useElementWidth } from './useElementWidth'

/**
 * Die Reihen eines Kuratierungsrasters zur gemessenen Innenbreite des Elements, an dem `ref`
 * haengt. Vor der ersten Messung gilt die natuerliche Breite auf der Zielhoehe.
 *
 * Reihen statt einer flachen Kachelliste: Band und Hinzufuegen-Panel stehen direkt hinter der
 * gerechneten Reihe ihres Ausloesers.
 */
export function useJustifiedRows<T extends Element>(
  ratios: readonly (number | null)[],
): { ref: (node: T | null) => void; rows: JustifiedRow[] } {
  const { ref, width } = useElementWidth<T>()
  return { ref, rows: curationRows(ratios, width) }
}
