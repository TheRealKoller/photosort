import { apiFetch, apiFetchBlob } from './client'
import type {
  AlbumDraftOut,
  DraftExchangeOut,
  DraftExchangeUndoIn,
  DraftExchangeUndoOut,
  MotifCorrectionOut,
  MotifKey,
  DraftAlternativesOut,
  PhotoListOut,
  PhotoVariant,
  RatingFilter,
} from './types'

export interface ListPhotosParams {
  ratingStatus?: RatingFilter
  limit?: number
  offset?: number
  /** Nur die Fotos DIESER Kamera. Traegt die Fotoauswahl des Versatz-Vorschlags - ohne den
   * Filter kann die Oberflaeche die beiden Fotos desselben Moments nicht anbieten. */
  cameraId?: number
  /** Nur Fotos, die JEDE dieser Personen wirksam tragen (höchstens zwei). */
  personIds?: readonly number[]
}

export interface ListDraftAlternativesParams {
  eventId: number
  /** Das Bezugsbild des Tauschs. Es steuert die zeitliche Position (`reference_index`) und ist
   * nie selbst dabei. Ohne (Hinzufügen-Feld) ordnet der Server nach Qualität; der Parameter fehlt
   * dann ganz. */
  photoId?: number
  limit?: number
  offset?: number
  /** Das Band: die `nearest` zeitlich nächsten Alternativen, Fenster vom Server geschnitten. Nur
   * zusammen mit `photoId`; `limit`/`offset` werden dann nicht gesendet. */
  nearest?: number
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
  if (params.cameraId !== undefined) {
    query.set('camera_id', String(params.cameraId))
  }
  for (const personId of params.personIds ?? []) {
    query.append('person_id', String(personId))
  }
  const queryString = query.toString()
  return apiFetch<PhotoListOut>(
    `/projects/${projectId}/photos${queryString ? `?${queryString}` : ''}`,
  )
}

/**
 * Der Album-Entwurf des ANFRAGENDEN Nutzers samt Eventliste des letzten erfolgreichen Laufs - als
 * GANZES, ohne Seitenweise. Gestrichene Fotos stehen darin (die Ansicht blendet sie aus); die
 * Reihenfolge kommt vom Server und wird nie nachsortiert.
 */
export function getAlbumDraft(projectId: number): Promise<AlbumDraftOut> {
  return apiFetch<AlbumDraftOut>(`/projects/${projectId}/album-draft`)
}

/**
 * Die Fotos eines Events abzueglich des eigenen Albums, seitenweise. Gestrichene sind darunter -
 * daraus folgt die Umkehrbarkeit des Tauschs. `total` der Antwort ist die RESTMENGE und damit
 * unabhaengig von `limit`/`offset`.
 *
 * Die REIHENFOLGE KOMMT VOM SERVER und wird nie nachsortiert: Mit Bezugsbild ist sie zeitlich,
 * und die Stelle des Bezugsbildes liefert der Server als `reference_index` mit (Spec 0569).
 */
export function listDraftAlternatives(
  projectId: number,
  params: ListDraftAlternativesParams,
): Promise<DraftAlternativesOut> {
  const query = new URLSearchParams({ event_id: String(params.eventId) })
  if (params.photoId !== undefined) {
    query.set('photo_id', String(params.photoId))
  }
  if (params.nearest !== undefined) {
    query.set('nearest', String(params.nearest))
  } else {
    if (params.limit !== undefined) {
      query.set('limit', String(params.limit))
    }
    if (params.offset !== undefined) {
      query.set('offset', String(params.offset))
    }
  }
  return apiFetch<DraftAlternativesOut>(
    `/projects/${projectId}/draft-alternatives?${query.toString()}`,
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

/**
 * Tauscht im eigenen Album-Entwurf ein Bild gegen ein anderes desselben Ereignisses — EIN Aufruf
 * statt zweier `setRating` (Spec 0432).
 *
 * „B statt A" ist die Aussage; die beiden Bilder für sich tragen sie nicht. Zwei getrennte
 * Aufrufe waren nicht atomar — der zweite konnte fehlschlagen und einen halb ausgeführten
 * Austausch hinterlassen — und ihre Zusammengehörigkeit kannte allein der Client.
 *
 * Der Body trägt AUSSCHLIESSLICH die beiden Foto-Ids. Kein `event_id`, kein Gewicht, kein
 * Nutzer: Der Server löst alles über die Rangzeile des Laufs auf, und ein vom Client geliefertes
 * Gewicht ließe die eigene Korrektur in der global wirkenden Ableitung stärker zählen.
 */
export function exchangeDraftPhoto(
  projectId: number,
  photoId: number,
  replacedPhotoId: number,
): Promise<DraftExchangeOut> {
  return apiFetch<DraftExchangeOut>(`/projects/${projectId}/draft/exchange`, {
    method: 'POST',
    body: { photo_id: photoId, replaced_photo_id: replacedPhotoId },
  })
}

/**
 * Stellt nach einem Tausch beide eigenen Bewertungszeilen auf ihren Zustand davor zurück - beide
 * oder keine. Der Server lehnt mit `409` ab, wenn sich eine der beiden seit dem Tausch geändert
 * hat, und schreibt dann nichts.
 */
export function undoDraftExchange(
  projectId: number,
  body: DraftExchangeUndoIn,
): Promise<DraftExchangeUndoOut> {
  return apiFetch<DraftExchangeUndoOut>(`/projects/${projectId}/draft/exchange/undo`, {
    method: 'POST',
    body,
  })
}
