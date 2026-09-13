import { apiFetch } from './client'
import type { RatingStatus, RatingWriteOut } from './types'

/**
 * Setzt die ALBUMENTSCHEIDUNG und lässt das Favoriten-Kennzeichen unberührt.
 *
 * `null` ist kein zulässiger Wert: "keine Albumentscheidung" entsteht ausschließlich über
 * `deleteRating`.
 */
export function setRating(photoId: number, status: RatingStatus): Promise<RatingWriteOut> {
  return apiFetch<RatingWriteOut>(`/photos/${photoId}/rating`, {
    method: 'PUT',
    body: { status },
  })
}

/** Nimmt NUR die Albumentscheidung zurück; eine Zeile mit Favoriten-Kennzeichen bleibt stehen. */
export function deleteRating(photoId: number): Promise<void> {
  return apiFetch<void>(`/photos/${photoId}/rating`, { method: 'DELETE' })
}

/**
 * Setzt oder entfernt das Favoriten-Kennzeichen und lässt die Albumentscheidung unberührt.
 *
 * Eigener Endpunkt statt eines gemeinsamen Schreibpfads: Ein Aufruf, der beide Felder aus einem
 * teilbefüllten Zustand schriebe, setzte beim Markieren als Favorit die Albumentscheidung still
 * zurück.
 */
export function setFavorite(photoId: number, favorite: boolean): Promise<RatingWriteOut> {
  return apiFetch<RatingWriteOut>(`/photos/${photoId}/favorite`, {
    method: 'PUT',
    body: { favorite },
  })
}
