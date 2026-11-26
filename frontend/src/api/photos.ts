import { apiFetch, apiFetchBlob } from './client'
import type {
  AlbumDraftOut,
  DraftAlternativesOut,
  DraftExchangeOut,
  DraftExchangeUndoIn,
  DraftExchangeUndoOut,
  ListDraftAlternativesParams,
  ListPhotosParams,
  MotifCorrectionOut,
  MotifKey,
  PhotoListOut,
  PhotoVariant,
} from './types'

/**
 * Die Fotos eines Projekts, seitenweise. Query-Werte gehen als typisiertes Objekt an die eine
 * Aufrufgrenze; `personIds` wird dort als wiederholter Schlüssel `person_id` serialisiert.
 */
export function listPhotos(
  projectId: number,
  params: ListPhotosParams = {},
): Promise<PhotoListOut> {
  return apiFetch('/projects/{project_id}/photos', {
    pathParams: { project_id: projectId },
    query: {
      ...(params.ratingStatus !== undefined ? { rating_status: params.ratingStatus } : {}),
      ...(params.limit !== undefined ? { limit: params.limit } : {}),
      ...(params.offset !== undefined ? { offset: params.offset } : {}),
      ...(params.cameraId !== undefined ? { camera_id: params.cameraId } : {}),
      ...(params.personIds ? { person_id: [...params.personIds] } : {}),
    },
  })
}

/**
 * Der Album-Entwurf des ANFRAGENDEN Nutzers samt Eventliste des letzten erfolgreichen Laufs - als
 * GANZES, ohne Seitenweise. Gestrichene Fotos stehen darin (die Ansicht blendet sie aus); die
 * Reihenfolge kommt vom Server und wird nie nachsortiert.
 */
export function getAlbumDraft(projectId: number): Promise<AlbumDraftOut> {
  return apiFetch('/projects/{project_id}/album-draft', {
    pathParams: { project_id: projectId },
  })
}

/**
 * Die Fotos eines Events abzueglich des eigenen Albums, seitenweise. Gestrichene sind darunter -
 * daraus folgt die Umkehrbarkeit des Tauschs.
 *
 * Die REIHENFOLGE KOMMT VOM SERVER und wird nie nachsortiert: Mit Bezugsbild ist sie zeitlich,
 * und die Stelle des Bezugsbildes liefert der Server als `reference_index` mit.
 */
export function listDraftAlternatives(
  projectId: number,
  params: ListDraftAlternativesParams,
): Promise<DraftAlternativesOut> {
  const band = params.series === true
  return apiFetch('/projects/{project_id}/draft-alternatives', {
    pathParams: { project_id: projectId },
    query: {
      event_id: params.eventId,
      ...(params.photoId !== undefined ? { photo_id: params.photoId } : {}),
      ...(band ? { series: true } : {}),
      ...(band || params.limit === undefined ? {} : { limit: params.limit }),
      ...(band || params.offset === undefined ? {} : { offset: params.offset }),
    },
  })
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
  const blob = await apiFetchBlob('/photos/{photo_id}/image', {
    pathParams: { photo_id: photoId },
    query: { variant },
  })
  return URL.createObjectURL(blob)
}

/**
 * Markiert ein Motiv fuer dieses Foto als zutreffend oder als nicht zutreffend.
 *
 * Der Body traegt AUSSCHLIESSLICH `applies` - der Nutzer schaetzt nie eine Zahl ein. Weder
 * `user_id` noch `motif_key` noch eine Staerke gehen mit; der Schluessel steht im Pfad, der Nutzer
 * kommt serverseitig aus dem Token.
 */
export function setMotifCorrection(
  photoId: number,
  motifKey: MotifKey,
  applies: boolean,
): Promise<MotifCorrectionOut> {
  return apiFetch('/photos/{photo_id}/motif-corrections/{motif_key}', {
    method: 'PUT',
    pathParams: { photo_id: photoId, motif_key: motifKey },
    body: { applies },
  })
}

/** Nimmt die Korrektur eines Motivs zurueck - idempotent, ohne Body. */
export function deleteMotifCorrection(photoId: number, motifKey: MotifKey): Promise<void> {
  return apiFetch('/photos/{photo_id}/motif-corrections/{motif_key}', {
    method: 'DELETE',
    pathParams: { photo_id: photoId, motif_key: motifKey },
  })
}

/**
 * Tauscht im eigenen Album-Entwurf ein Bild gegen ein anderes desselben Ereignisses — EIN Aufruf
 * statt zweier `setRating`.
 *
 * „B statt A" ist die Aussage; die beiden Bilder für sich tragen sie nicht. Der Body trägt
 * AUSSCHLIESSLICH die beiden Foto-Ids: kein `event_id`, kein Gewicht, kein Nutzer.
 */
export function exchangeDraftPhoto(
  projectId: number,
  photoId: number,
  replacedPhotoId: number,
): Promise<DraftExchangeOut> {
  return apiFetch('/projects/{project_id}/draft/exchange', {
    method: 'POST',
    pathParams: { project_id: projectId },
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
  return apiFetch('/projects/{project_id}/draft/exchange/undo', {
    method: 'POST',
    pathParams: { project_id: projectId },
    body,
  })
}
