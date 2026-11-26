import { apiFetch, apiFetchBlob } from './client'
import type {
  FaceAssignmentOut,
  FaceOut,
  PersonOut,
  PhotoPersonOut,
  UnnamedFacesPageOut,
} from './types'

/**
 * Die Personen-Endpunkte. Namen gehen nur im JSON-Körper, nie in Pfad oder Query -
 * gefiltert und adressiert wird über die Id.
 */

/** Die wörtlichen `detail`-Texte, an denen die Oberfläche einen `409` unterscheidet. Sie stehen im
 * Backend als Klassen in `persons.py` - eine Änderung dort bricht die Tests hier. */
export const PERSON_REFUSALS = {
  limitReached: 'Es sind bereits zwei Personen festgelegt.',
  duplicateName: 'Eine Person mit diesem Namen gibt es schon.',
  faceNotFound: 'An dieser Stelle ist auf dem Foto kein Gesicht mehr zu finden.',
  faceAlreadyOnPhoto: 'Diese Person hat auf diesem Foto schon ein Gesicht.',
  faceOfOtherPerson: 'Dieses Gesicht gehört auf diesem Foto schon der anderen Person.',
} as const

export function listPersons(): Promise<PersonOut[]> {
  return apiFetch('/persons')
}

export function createPerson(
  name: string,
  photoId: number,
  faceIndex: number,
): Promise<FaceAssignmentOut> {
  return apiFetch('/persons', {
    method: 'POST',
    body: { name, photo_id: photoId, face_index: faceIndex },
  })
}

export function addReference(
  personId: number,
  photoId: number,
  faceIndex: number,
): Promise<FaceAssignmentOut> {
  return apiFetch('/persons/{person_id}/references', {
    method: 'POST',
    pathParams: { person_id: personId },
    body: { photo_id: photoId, face_index: faceIndex },
  })
}

export function deletePerson(personId: number): Promise<void> {
  return apiFetch('/persons/{person_id}', {
    method: 'DELETE',
    pathParams: { person_id: personId },
  })
}

export function listFaces(photoId: number): Promise<FaceOut[]> {
  return apiFetch('/photos/{photo_id}/faces', { pathParams: { photo_id: photoId } })
}

/** Der Ausschnitt eines Gesichts als Blob - der Aufrufer macht daraus eine Blob-URL und gibt sie
 * beim Zuklappen bzw. Fotowechsel wieder frei. */
export function fetchFaceImage(photoId: number, index: number): Promise<Blob> {
  return apiFetchBlob('/photos/{photo_id}/faces/{index}/image', {
    pathParams: { photo_id: photoId, index },
  })
}

/** Eine Seite "Ohne Namen" ab `afterId` (exklusiv). `maxPhotos = 1` ist die Einzelabfrage, mit der
 * ein schon durchsuchtes Foto neu abgefragt wird. */
export function listUnnamedFaces(
  projectId: number,
  afterId: number,
  maxPhotos?: number,
): Promise<UnnamedFacesPageOut> {
  return apiFetch('/projects/{project_id}/unnamed-faces', {
    pathParams: { project_id: projectId },
    query: {
      after_id: afterId,
      ...(maxPhotos !== undefined ? { max_photos: maxPhotos } : {}),
    },
  })
}

export function setPhotoPerson(
  photoId: number,
  personId: number,
  applies: boolean,
): Promise<PhotoPersonOut[]> {
  return apiFetch('/photos/{photo_id}/persons/{person_id}', {
    method: 'PUT',
    pathParams: { photo_id: photoId, person_id: personId },
    body: { applies },
  })
}
