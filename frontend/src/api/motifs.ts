import { apiFetch } from './client'
import type { MotifSetOut } from './types'

/**
 * Das feste Achter-Motivset - kommt ausschliesslich vom Server, es gibt bewusst KEINE
 * TypeScript-Spiegelung: eine zweite Liste waere eine dauerhaft driftende Kopie, und die
 * Staerkeliste braucht das volle Set unabhaengig davon, was fuer ein einzelnes Foto beurteilt
 * wurde.
 *
 * Anzeigenamen, Reihenfolge, Erklaertexte UND die beiden Anzeigebaender der Statistik stammen
 * alle aus dieser Antwort. Die Reihenfolge wird uebernommen, nicht neu sortiert - schon gar nicht
 * nach Staerke: acht gleichnamige Korrekturschalter, die von Foto zu Foto die Position wechseln,
 * laden zum Fehlklick ein, und ein Fehlklick schreibt hier einen Datenwert.
 */
export function listMotifs(): Promise<MotifSetOut> {
  return apiFetch<MotifSetOut>('/motifs')
}
