import { useInfiniteQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import type { InfiniteData } from '@tanstack/react-query'

import { listPhotos } from '../api/photos'
import type { PhotoListOut, PhotoOut } from '../api/types'
import { personGroupQueryKey } from './useFaceAssignment'
import type { PersonGroupQueryKey } from './useFaceAssignment'

/** Die Seitengröße der Übersicht - nicht `PHOTOS_PAGE_SIZE`: So stehen beide Personengruppen und
 * der Anfang von "Ohne Namen" in erreichbarer Nähe. */
export const PERSON_GROUP_PAGE_SIZE = 24

type GroupData = InfiniteData<PhotoListOut, number>

interface GroupState {
  /** Die geladenen Einträge, die den Namen noch tragen, nach Id entdoppelt. */
  remaining: PhotoOut[]
  /** Die Fotos hinter dem geladenen Fenster, so wie der Server sie beim letzten Abruf sah. */
  rest: number
}

/**
 * Verbleibend und Rest einer Gruppe. "Name entfernen" ändert über `storePhotoPersons` nur
 * `persons` im Cache; der Server zählt ein verlorenes Foto danach nicht mehr, und alle späteren
 * rücken um die Zahl der verlorenen vor. Deshalb ist der nächste Offset die Zahl der
 * verbleibenden Einträge, und die Anzahl ist verbleibend plus Rest - nie `total` der ersten Seite.
 * Ein Entfernen ändert den Rest nicht: Entfernen lässt sich nur, was geladen ist.
 */
function personGroupState(data: GroupData | undefined, personId: number): GroupState {
  if (data === undefined || data.pages.length === 0) {
    return { remaining: [], rest: 0 }
  }
  const seen = new Set<number>()
  const remaining: PhotoOut[] = []
  for (const page of data.pages) {
    for (const item of page.items) {
      if (!seen.has(item.id) && item.persons.some((entry) => entry.person_id === personId)) {
        seen.add(item.id)
        remaining.push(item)
      }
    }
  }
  const lastPage = data.pages[data.pages.length - 1]
  const lastOffset = data.pageParams[data.pageParams.length - 1] ?? 0
  const rest = Math.max(0, lastPage.total - (lastOffset + lastPage.items.length))
  return { remaining, rest }
}

/**
 * Die Gruppe einer Person in der Übersicht: die Personeneinschränkung des Bildbestands ohne
 * Bewertungsfilter, seitenweise. Eigener Schlüssel, NICHT der von `usePhotoSequenceQuery`: Dessen
 * Schlüssel enthält die Seitengröße nicht, und ein Neuladen setzte die Offsets mit der Seitengröße
 * des ladenden Beobachters ein - doppelte oder fehlende Fotos.
 */
export function usePersonGroupQuery(projectId: number, personId: number) {
  const query = useInfiniteQuery<PhotoListOut, Error, GroupData, PersonGroupQueryKey, number>({
    queryKey: personGroupQueryKey(projectId, personId),
    queryFn: ({ pageParam }) =>
      listPhotos(projectId, {
        limit: PERSON_GROUP_PAGE_SIZE,
        offset: pageParam,
        personIds: [personId],
      }),
    initialPageParam: 0,
    getNextPageParam: (_lastPage, pages, _lastParam, pageParams) => {
      const state = personGroupState({ pages, pageParams }, personId)
      return state.rest > 0 ? state.remaining.length : undefined
    },
  })
  // Gemerkt: Die Seite reicht die Fotos an die Großansicht weiter und darf nicht bei jedem
  // Rendern eine neue Liste bekommen.
  const { remaining, rest } = useMemo(
    () => personGroupState(query.data, personId),
    [query.data, personId],
  )
  return {
    ...query,
    photos: remaining,
    count: query.data === undefined ? undefined : remaining.length + rest,
  }
}
