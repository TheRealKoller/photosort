import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { ApiError } from '../api/client'
import { setPhotoPerson } from '../api/persons'
import type { PhotoPersonOut } from '../api/types'
import { PERSONS_QUERY_KEY } from './usePersons'

const GENERIC_DETAIL = 'Die Zuordnung konnte nicht gespeichert werden.'

/** Ersetzt `persons` des Fotos in einer Fotoliste - als Seitenfolge (`pages`) oder als einzelne
 * Liste (`items`). Andere Formen unter dem Präfix bleiben unberührt; ein Eintrag zählt nur als
 * dieses Foto, wenn er selbst eine `persons`-Liste trägt. */
function withPhotoPersons(data: unknown, photoId: number, persons: PhotoPersonOut[]): unknown {
  if (typeof data !== 'object' || data === null) {
    return data
  }
  if ('pages' in data && Array.isArray(data.pages)) {
    return { ...data, pages: data.pages.map((page) => withPhotoPersons(page, photoId, persons)) }
  }
  if ('items' in data && Array.isArray(data.items)) {
    return {
      ...data,
      items: data.items.map((item: unknown) =>
        typeof item === 'object' &&
        item !== null &&
        'id' in item &&
        item.id === photoId &&
        'persons' in item
          ? { ...item, persons }
          : item,
      ),
    }
  }
  return data
}

/**
 * Schreibt die wirksame Personenliste eines Fotos nach einer Korrektur in den Cache (Spec 0292).
 *
 * DAS AKTUELLE FOTO BLEIBT STEHEN: Die Fotolisten des Projekts werden nur als veraltet markiert
 * (`refetchType: 'none'`), nicht neu geladen. Passt das Foto nach dem Entfernen eines Namens nicht
 * mehr zum aktiven Personenfilter, fiele es sonst mitten in der Korrektur aus der geladenen Folge,
 * und die Detailansicht stünde auf "Foto nicht in der aktuellen Auswahl gefunden." Beim nächsten
 * Aufruf einer Liste lädt sie neu.
 */
export function storePhotoPersons(
  queryClient: QueryClient,
  projectId: number,
  photoId: number,
  persons: PhotoPersonOut[],
): void {
  queryClient.setQueriesData({ queryKey: ['photos', projectId] }, (data: unknown) =>
    withPhotoPersons(data, photoId, persons),
  )
  void queryClient.invalidateQueries({ queryKey: ['photos', projectId], refetchType: 'none' })
}

/**
 * Ergänzen/Entfernen einer Person auf einem Foto. Jede Person hat ihren eigenen Busy-Zustand -
 * zwei Zeilen können gleichzeitig laufen, deshalb `mutateAsync` je Aufruf statt der
 * Aufruf-Callbacks, die nur für den jeweils letzten Aufruf feuern.
 */
export function usePhotoPersonControls(projectId: number) {
  const queryClient = useQueryClient()
  const [pendingIds, setPendingIds] = useState<readonly number[]>([])
  const [error, setError] = useState<string | null>(null)
  const mutation = useMutation({
    mutationFn: (vars: { photoId: number; personId: number; applies: boolean }) =>
      setPhotoPerson(vars.photoId, vars.personId, vars.applies),
    onSuccess: (persons, vars) => storePhotoPersons(queryClient, projectId, vars.photoId, persons),
  })

  async function setApplies(photoId: number, personId: number, applies: boolean): Promise<void> {
    setPendingIds((ids) => [...ids, personId])
    setError(null)
    try {
      await mutation.mutateAsync({ photoId, personId, applies })
    } catch (cause) {
      setError(cause instanceof ApiError && cause.detail.length > 0 ? cause.detail : GENERIC_DETAIL)
      // Die Person ist inzwischen entfernt: Die Zeile verschwindet mit der neu geladenen Liste.
      if (cause instanceof ApiError && cause.status === 404) {
        void queryClient.invalidateQueries({ queryKey: PERSONS_QUERY_KEY })
      }
    } finally {
      setPendingIds((ids) => ids.filter((id) => id !== personId))
    }
  }

  return { setApplies, pendingIds, error }
}
