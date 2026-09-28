import { useMutation, useQueryClient } from '@tanstack/react-query'

import { addReference, createPerson } from '../api/persons'
import type { FaceAssignmentOut } from '../api/types'
import { PERSONS_QUERY_KEY } from './usePersons'
import { storePhotoPersons } from './usePhotoPersons'

export type FaceChoice = { kind: 'reference'; personId: number } | { kind: 'create'; name: string }

export interface FaceAssignmentVariables {
  choice: FaceChoice
  photoId: number
  faceIndex: number
}

/** Der Schlüssel der Gruppe einer Person in der Übersicht - unter `['photos', projectId]`, damit
 * `storePhotoPersons` und die breiten Invalidierungen sie erreichen. */
export function personGroupQueryKey(projectId: number, personId: number) {
  return ['photos', projectId, 'person-group', personId] as const
}

/** Die Meldung nach einer gelungenen Zuordnung - bei `learned: false` mit dem Satz zur
 * Obergrenze. Gemeinsam für Detailansicht und "Ohne Namen". */
export function assignmentMessage(
  kind: FaceChoice['kind'],
  name: string,
  learned: boolean,
): string {
  if (kind === 'create') {
    return `${name} ist festgelegt.`
  }
  return learned
    ? `Gesicht als ${name} gezeigt.`
    : `Als ${name} benannt, aber nicht gelernt: Für ${name} sind schon genug Gesichter gezeigt.`
}

/**
 * Festlegen und Zeigen eines Gesichts - dieselbe Mutation für die Detailansicht und "Ohne Namen".
 *
 * Bei Erfolg steht `photo_persons` der ANTWORT in allen Foto-Caches des Projekts; es wird nichts
 * lokal zusammengesetzt. Die Personenliste lädt neu, in der Übersicht (`refreshGroup`) zusätzlich
 * die Gruppe der Person. Am Hook, nicht am Aufruf: Auch nach einem Fotowechsel mitten in der
 * Anfrage landet die Zuordnung im Cache.
 */
export function useFaceAssignment(projectId: number, { refreshGroup = false } = {}) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ choice, photoId, faceIndex }: FaceAssignmentVariables) =>
      choice.kind === 'create'
        ? createPerson(choice.name, photoId, faceIndex)
        : addReference(choice.personId, photoId, faceIndex),
    onSuccess: (result: FaceAssignmentOut, { photoId }) => {
      storePhotoPersons(queryClient, projectId, photoId, result.photo_persons)
      void queryClient.invalidateQueries({ queryKey: PERSONS_QUERY_KEY })
      if (refreshGroup) {
        void queryClient.refetchQueries({
          queryKey: personGroupQueryKey(projectId, result.person.id),
        })
      }
    },
  })
}
