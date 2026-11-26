import { apiFetch } from './client'
import type { AusschussOut, ListAusschussParams } from './types'

/**
 * Der Ausschuss-BESTAND dieses Projekts: offene Vorschläge und getroffene Entscheidungen in einer
 * Ansicht.
 *
 * Die Reihenfolge kommt vom Server (`Photo.taken_at, Photo.id`) und wird hier nie nachsortiert —
 * eine zweite Sortierung im Client wäre eine zweite Fassung derselben Zusage.
 *
 * KEIN Schreibweg in diesem Modul: Der Abschluss liegt in `projects.ts::confirmAusschussGate`, die
 * Einzelentscheidung in `duplicates.ts`. Diese Datei liest.
 */
export function listAusschuss(
  projectId: number,
  params: ListAusschussParams = {},
): Promise<AusschussOut> {
  return apiFetch('/projects/{project_id}/ausschuss', {
    pathParams: { project_id: projectId },
    query: {
      ...(params.limit !== undefined ? { limit: params.limit } : {}),
      ...(params.offset !== undefined ? { offset: params.offset } : {}),
      ...(params.photoId !== undefined ? { photo_id: params.photoId } : {}),
      ...(params.autoDecided ? { auto_decided: true } : {}),
    },
  })
}
