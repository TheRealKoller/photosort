import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query'
import type { InfiniteData } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { listUnnamedFaces } from '../api/persons'
import type { UnnamedFaceOut, UnnamedFacesPageOut } from '../api/types'

/** Eine Seite samt dem logischen Zeitpunkt, zu dem ihre Anfrage startete. */
interface StampedPage extends UnnamedFacesPageOut {
  startedAt: number
}

/** Das Ergebnis einer Einzelabfrage: ersetzt ALLE Gesichter dieses Fotos aus den Seiten. */
interface PhotoOverride {
  faces: UnnamedFaceOut[]
  notReady: boolean
  startedAt: number
}

export interface RefreshFailure {
  photoId: number
  fileName: string | null
}

/**
 * - `initial`: vor der ersten Seite;
 * - `running`: Seiten geladen, weitere folgen;
 * - `interrupted`: ein Fehler hat die Suche angehalten;
 * - `complete`: alle Fotos durchgesehen;
 * - `empty`: das Projekt hat keine Fotos.
 */
export type UnnamedSearchStatus = 'initial' | 'running' | 'interrupted' | 'complete' | 'empty'

type UnnamedData = InfiniteData<StampedPage, number>
type UnnamedQueryKey = readonly ['unnamed-faces', number]

/**
 * "Ohne Namen": die Gesichter des Projekts, die keiner Person zugeordnet sind, seitenweise nach
 * Foto-Id und selbsttätig nachgeladen, solange die Übersicht offen ist.
 *
 * Der Schlüssel liegt bewusst AUSSERHALB von `['photos', projectId]`: Sonst startete jede breite
 * Invalidierung die Suche neu, und die Stelle ginge verloren. `gcTime: 0` wirft die Ausschnitte
 * beim Verlassen weg.
 *
 * Die Seiten im Cache bleiben die Serverantworten. Entfernte Gesichter und Einzelabfragen liegen
 * als Überlagerung daneben - ein `setQueryData` während einer Seite im Flug überschriebe TanStack
 * mit den Seiten, die beim Start der Anfrage galten. Jede Anfrage und jedes Entfernen bekommt einen
 * logischen Zeitpunkt: Ein Entfernen wirkt auf jede Antwort, deren Anfrage VOR ihm startete.
 */
export function useUnnamedFaces(projectId: number) {
  const queryClient = useQueryClient()
  const queryKey = useMemo<UnnamedQueryKey>(() => ['unnamed-faces', projectId], [projectId])
  const clock = useRef(0)
  /** Der `after_id` der Seite im Flug, sonst `null`. */
  const pageInFlight = useRef<number | null>(null)
  /** Einzelabfragen, die auf die Ankunft der Seite im Flug warten. */
  const deferred = useRef(new Map<number, string | null>())
  const [removals, setRemovals] = useState<ReadonlyMap<string, number>>(new Map())
  const [overrides, setOverrides] = useState<ReadonlyMap<number, PhotoOverride>>(new Map())
  const [refreshFailures, setRefreshFailures] = useState<readonly RefreshFailure[]>([])

  const runRefresh = useCallback(
    async (photoId: number, fileName: string | null) => {
      clock.current += 1
      const startedAt = clock.current
      try {
        const answer = await listUnnamedFaces(projectId, photoId - 1, 1)
        // Liefert die Antwort ein anderes Foto, ist das angefragte inzwischen gelöscht: Seine
        // Gesichter entfallen, die des gelieferten kommen mit dessen eigener Seite.
        const override: PhotoOverride = {
          faces: answer.faces.filter((face) => face.photo_id === photoId),
          notReady: answer.not_ready_photo_ids.includes(photoId),
          startedAt,
        }
        setOverrides((current) => {
          const previous = current.get(photoId)
          if (previous !== undefined && previous.startedAt > startedAt) {
            return current
          }
          return new Map(current).set(photoId, override)
        })
        setRefreshFailures((current) => current.filter((entry) => entry.photoId !== photoId))
      } catch {
        setRefreshFailures((current) => [
          ...current.filter((entry) => entry.photoId !== photoId),
          { photoId, fileName },
        ])
      }
    },
    [projectId],
  )

  const query = useInfiniteQuery<StampedPage, Error, UnnamedData, UnnamedQueryKey, number>({
    queryKey,
    queryFn: async ({ pageParam }) => {
      clock.current += 1
      const startedAt = clock.current
      pageInFlight.current = pageParam
      let cursor: number | null | undefined
      try {
        const answer = await listUnnamedFaces(projectId, pageParam)
        cursor = answer.next_after_id
        return { ...answer, startedAt }
      } finally {
        pageInFlight.current = null
        // Nach Ankunft oder Fehlschlag gegen den NEUEN Cursor entscheiden. Scheitert die Seite,
        // bleibt der Cursor bei `pageParam`, und die vorgemerkten Fotos liegen alle dahinter.
        const waiting = [...deferred.current]
        deferred.current.clear()
        for (const [photoId, fileName] of waiting) {
          const passed = cursor !== undefined && (cursor === null || photoId <= cursor)
          if (passed) {
            void runRefresh(photoId, fileName)
          }
        }
      }
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage) => lastPage.next_after_id ?? undefined,
    gcTime: 0,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })

  const { data, hasNextPage, isFetching, isError, fetchNextPage, refetch } = query

  useEffect(() => {
    if (hasNextPage && !isFetching && !isError) {
      void fetchNextPage()
    }
  }, [hasNextPage, isFetching, isError, fetchNextPage])

  const removeFace = useCallback((photoId: number, faceIndex: number) => {
    clock.current += 1
    const removedAt = clock.current
    setRemovals((current) => new Map(current).set(`${photoId}-${faceIndex}`, removedAt))
  }, [])

  /**
   * Holt ein schon durchsuchtes Foto einzeln neu und ersetzt seine Gesichter an ihrer Stelle. Ein
   * Foto, das die Suche noch nicht erreicht hat, findet sie ohnehin. Liegt eine Seite im Flug,
   * deren Bereich das Foto enthält, wird der Aufruf vorgemerkt: Der Server kann das Foto vor dem
   * Commit einer Rücknahme bearbeitet haben.
   */
  const refreshPhoto = useCallback(
    (photoId: number, fileName: string | null) => {
      if (pageInFlight.current !== null && photoId > pageInFlight.current) {
        deferred.current.set(photoId, fileName)
        return
      }
      // Hat die Suche dieses Foto schon passiert? Ohne Seite noch nicht; nach der letzten jedes.
      const lastPage = queryClient.getQueryData<UnnamedData>(queryKey)?.pages.at(-1)
      if (
        lastPage !== undefined &&
        (lastPage.next_after_id === null || photoId <= lastPage.next_after_id)
      ) {
        void runRefresh(photoId, fileName)
      }
    },
    [queryClient, queryKey, runRefresh],
  )

  const retryRefresh = useCallback(
    (photoId: number) => {
      const failure = refreshFailures.find((entry) => entry.photoId === photoId)
      if (failure !== undefined) {
        void runRefresh(photoId, failure.fileName)
      }
    },
    [refreshFailures, runRefresh],
  )

  /** Setzt die Suche an der Stelle fort, an der sie scheiterte - nie wieder bei `0`. */
  const retry = useCallback(() => {
    if (queryClient.getQueryData<UnnamedData>(queryKey) === undefined) {
      void refetch()
    } else {
      void fetchNextPage()
    }
  }, [queryClient, queryKey, fetchNextPage, refetch])

  const view = useMemo(() => {
    const pages = data?.pages ?? []
    const faces: UnnamedFaceOut[] = []
    const notReady = new Set<number>()
    const visible = (face: UnnamedFaceOut, startedAt: number) =>
      (removals.get(`${face.photo_id}-${face.face_index}`) ?? -1) < startedAt
    for (const entry of pages) {
      for (const face of entry.faces) {
        if (!overrides.has(face.photo_id) && visible(face, entry.startedAt)) {
          faces.push(face)
        }
      }
      for (const photoId of entry.not_ready_photo_ids) {
        notReady.add(photoId)
      }
    }
    for (const [photoId, override] of overrides) {
      faces.push(...override.faces.filter((face) => visible(face, override.startedAt)))
      if (override.notReady) {
        notReady.add(photoId)
      }
    }
    faces.sort((a, b) => a.photo_id - b.photo_id || a.face_index - b.face_index)
    const lastPage = pages.at(-1)
    return {
      faces,
      notReadyCount: notReady.size,
      progress:
        lastPage === undefined
          ? null
          : { done: lastPage.photos_done, total: lastPage.photos_total },
    }
  }, [data, removals, overrides])

  let status: UnnamedSearchStatus
  if (isError) {
    status = 'interrupted'
  } else if (view.progress === null) {
    status = 'initial'
  } else if (view.progress.total === 0) {
    status = 'empty'
  } else {
    status = hasNextPage ? 'running' : 'complete'
  }

  return {
    ...view,
    status,
    error: query.error,
    retry,
    removeFace,
    refreshPhoto,
    refreshFailures,
    retryRefresh,
  }
}

/** Der Zustand von "Ohne Namen", wie ihn die Seite an die Gruppe reicht. */
export type UnnamedFaces = ReturnType<typeof useUnnamedFaces>
