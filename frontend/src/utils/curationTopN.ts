/**
 * Der Standardwert und die Grenzen der Kuratierungs-Auswahl ("Top-Fotos pro Kategorie"), an EINER
 * Stelle (specs/features/0357-voller-bildvorrat-kuratierung.md, Entwurfsentscheidung 10).
 *
 * Zuvor stand die "3" dreimal im Code (`CurateCategoriesPage.tsx`, `KuratierungStepPage.tsx`
 * zweimal). Mit dem Anheben auf 10 waere das dreimal derselbe Wert gewesen, den eine kuenftige
 * Aenderung an zwei Stellen vergisst.
 *
 * Die Grenzen sind deckungsgleich mit der serverseitigen Durchsetzung
 * (`Query(None, ge=1, le=10)` auf `GET /projects/{id}/photos`, backend/src/photosort/api/
 * photos.py) - clientseitiges Klemmen ist nur ein Hinweis, die eigentliche Grenze gilt ohnehin
 * serverseitig.
 */
export const MIN_TOP_N = 1
export const MAX_TOP_N = 10
export const DEFAULT_TOP_N = 10

/**
 * Liest den `topN`-Suchparameter (oder einen Feldwert) und klemmt ihn in die gueltigen Grenzen.
 * Fehlender, leerer und nicht-numerischer Wert liefern den Standardwert; alles andere wird
 * gerundet und geklemmt.
 */
export function parseTopN(value: string | null): number {
  if (value === null || value === '') {
    return DEFAULT_TOP_N
  }
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) {
    return DEFAULT_TOP_N
  }
  return Math.min(MAX_TOP_N, Math.max(MIN_TOP_N, Math.round(parsed)))
}
