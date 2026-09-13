import { apiFetch, apiFetchBlob } from './client'
import type {
  MotifCorrectionOut,
  MotifKey,
  PhotoListOut,
  PhotoVariant,
  RatingFilter,
} from './types'

export interface ListPhotosParams {
  ratingStatus?: RatingFilter
  limit?: number
  offset?: number
  // Auswahlmodus - gesetzt, ersetzt er ratingStatus/limit/offset vollstaendig (eigenstaendige
  // Kuratierungs-Ansicht, siehe backend api/photos.py::list_photos-Kommentar). Welche Fotos er
  // liefert, entscheidet allein der Lauf; das Frontend kennt weder eine Anzahl noch eine
  // Schwelle.
  selection?: boolean
  /** Nur die Fotos DIESER Kamera. Traegt die Fotoauswahl des Versatz-Vorschlags - ohne den
   * Filter kann die Oberflaeche die beiden Fotos desselben Moments nicht anbieten. */
  cameraId?: number
}

export interface ListCurationCandidatesParams {
  eventId: number
  /** Es werden nur Fotos mit `rank_position > afterRank` geliefert. */
  afterRank: number
  limit?: number
  offset?: number
}

export function listPhotos(
  projectId: number,
  params: ListPhotosParams = {},
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
  if (params.selection) {
    query.set('selection', 'true')
  }
  if (params.cameraId !== undefined) {
    query.set('camera_id', String(params.cameraId))
  }
  const queryString = query.toString()
  return apiFetch<PhotoListOut>(
    `/projects/${projectId}/photos${queryString ? `?${queryString}` : ''}`,
  )
}

/**
 * Die weiteren Kandidaten EINER Partition - alles jenseits von `afterRank`, aufsteigend nach
 * `rank_position`, seitenweise. `total` der Antwort ist die RESTMENGE der Partition und damit
 * unabhaengig von `limit`/`offset`.
 *
 * Bewusst ein eigener Endpunkt statt einer Erweiterung von `listPhotos`: dort gilt die Zusage,
 * dass `limit`/`offset` im Kuratierungsmodus nicht wirken.
 */
export function listCurationCandidates(
  projectId: number,
  params: ListCurationCandidatesParams,
): Promise<PhotoListOut> {
  const query = new URLSearchParams({
    event_id: String(params.eventId),
    after_rank: String(params.afterRank),
  })
  if (params.limit !== undefined) {
    query.set('limit', String(params.limit))
  }
  if (params.offset !== undefined) {
    query.set('offset', String(params.offset))
  }
  return apiFetch<PhotoListOut>(`/projects/${projectId}/curation-candidates?${query.toString()}`)
}

/**
 * Laedt ein Foto-Bild authentifiziert und liefert eine Object-URL - siehe
 * api/client.ts::apiFetchBlob fuer den Hintergrund (kein <img src> moeglich, da der
 * Authorization-Header sonst fehlen wuerde). Aufrufer ist fuer URL.revokeObjectURL()
 * verantwortlich, sobald die URL nicht mehr gebraucht wird (siehe components/PhotoImage.tsx).
 */
export async function fetchPhotoImageBlobUrl(
  photoId: number,
  variant: PhotoVariant,
): Promise<string> {
  const blob = await apiFetchBlob(`/photos/${photoId}/image?variant=${variant}`)
  return URL.createObjectURL(blob)
}

/**
 * Markiert ein Motiv fuer dieses Foto als zutreffend oder als nicht zutreffend (Spec 0427).
 *
 * Der Body traegt AUSSCHLIESSLICH `applies` - der Nutzer schaetzt nie eine Zahl ein. Weder
 * `user_id` noch `motif_key` noch eine Staerke gehen mit; der Schluessel steht im Pfad, der Nutzer
 * kommt serverseitig aus dem Token. `encodeURIComponent` haelt einen Altwert mit Sonderzeichen aus
 * der Pfadstruktur heraus - der Server weist ihn danach ohnehin mit `422` ab.
 */
export function setMotifCorrection(
  photoId: number,
  motifKey: MotifKey,
  applies: boolean,
): Promise<MotifCorrectionOut> {
  return apiFetch<MotifCorrectionOut>(
    `/photos/${photoId}/motif-corrections/${encodeURIComponent(motifKey)}`,
    { method: 'PUT', body: { applies } },
  )
}

/** Nimmt die Korrektur eines Motivs zurueck - idempotent, ohne Body. */
export function deleteMotifCorrection(photoId: number, motifKey: MotifKey): Promise<void> {
  return apiFetch<void>(`/photos/${photoId}/motif-corrections/${encodeURIComponent(motifKey)}`, {
    method: 'DELETE',
  })
}
