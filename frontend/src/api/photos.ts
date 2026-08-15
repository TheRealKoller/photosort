import { apiFetch, apiFetchBlob } from './client'
import type { PhotoListOut, PhotoVariant, RatingFilter } from './types'

export interface ListPhotosParams {
  ratingStatus?: RatingFilter
  limit?: number
  offset?: number
  // Kategorie-Kuratierung + Backfill (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-
  // backfill.md) - wenn gesetzt, ersetzt dieser Query-Modus ratingStatus/limit/offset vollstaendig
  // (eigenstaendige Kuratierungs-Ansicht, siehe backend api/photos.py::list_photos-Kommentar).
  topNPerCategory?: number
}

export function listPhotos(
  projectId: number,
  params: ListPhotosParams = {}
): Promise<PhotoListOut> {
  const query = new URLSearchParams()
  if (params.ratingStatus !== undefined) {
    query.set('rating_status', params.ratingStatus)
  }
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit))
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset))
  }
  if (params.topNPerCategory !== undefined) {
    query.set('top_n_per_category', String(params.topNPerCategory))
  }
  const queryString = query.toString()
  return apiFetch<PhotoListOut>(
    `/projects/${projectId}/photos${queryString ? `?${queryString}` : ''}`
  )
}

/**
 * Laedt ein Foto-Bild authentifiziert und liefert eine Object-URL - siehe
 * api/client.ts::apiFetchBlob fuer den Hintergrund (kein <img src> moeglich, da der
 * Authorization-Header sonst fehlen wuerde). Aufrufer ist fuer URL.revokeObjectURL()
 * verantwortlich, sobald die URL nicht mehr gebraucht wird (siehe components/PhotoImage.tsx).
 */
export async function fetchPhotoImageBlobUrl(
  photoId: number,
  variant: PhotoVariant
): Promise<string> {
  const blob = await apiFetchBlob(`/photos/${photoId}/image?variant=${variant}`)
  return URL.createObjectURL(blob)
}
