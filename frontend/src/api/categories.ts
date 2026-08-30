import { apiFetch } from './client'
import type { CategoryOut } from './types'

/**
 * Das feste Kategorien-Set (specs/features/0289-feste-kategorien.md, ADR 0049
 * Entwurfsentscheidung 5) - kommt ausschliesslich vom Server, es gibt bewusst KEINE
 * TypeScript-Spiegelung: eine zweite Liste waere eine dauerhaft driftende Kopie, und die
 * Override-Auswahl braucht das volle Set unabhaengig davon, was fuer ein Foto erkannt wurde.
 *
 * Die Antwort steht in Anzeigereihenfolge der Server-Registry - diese Reihenfolge wird im
 * Frontend uebernommen, nicht neu sortiert.
 */
export function listCategories(): Promise<CategoryOut[]> {
  return apiFetch<CategoryOut[]>('/categories')
}
