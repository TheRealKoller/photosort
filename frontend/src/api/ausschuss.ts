import { apiFetch } from './client'
import type { AusschussOut } from './types'

export interface ListAusschussParams {
  /** Seitengröße. Der Server führt dieselbe Vorgabe (60) und dieselben Grenzen (`ge=1, le=200`). */
  limit?: number
  offset?: number
  /**
   * Der Filterzweig für die Detailansicht: `items` trägt dann genau den passenden Eintrag oder
   * eine leere Liste, `total`/`open_count` bleiben projektweit. Damit ist ein Deep-Link auch auf
   * eine Aufnahme außerhalb der geladenen Seite eine definierte Antwort statt einer Lücke.
   */
  photoId?: number
}

/**
 * Der Ausschuss-BESTAND dieses Projekts: offene Vorschläge und getroffene Entscheidungen in einer
 * Ansicht (Spec 0525).
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
  const query = new URLSearchParams()
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit))
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset))
  }
  if (params.photoId !== undefined) {
    query.set('photo_id', String(params.photoId))
  }
  const queryString = query.toString()
  return apiFetch<AusschussOut>(
    `/projects/${projectId}/ausschuss${queryString ? `?${queryString}` : ''}`,
  )
}
