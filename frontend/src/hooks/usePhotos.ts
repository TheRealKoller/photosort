import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { listPhotos } from '../api/photos'
import { deleteRating, setRating } from '../api/ratings'
import type { PhotoListOut, RatingFilter, RatingStatus } from '../api/types'

/**
 * Batch-Groesse fuer das Foto-Listing (specs/features/0002-manual-categorization.md: "Fotos
 * werden paginiert geladen (Batches statt Gesamt-Reload bei tausenden Fotos)"). Grid- und
 * Einzelbild-/Swipe-Ansicht teilen sich denselben Query-Key (siehe unten) und damit dieselben
 * bereits geladenen Batches - "Navigation/Shortcuts operieren auf der zuletzt geladenen,
 * gefilterten Foto-ID-Liste", kein separater "naechstes Foto"-Endpunkt noetig.
 */
export const PHOTOS_PAGE_SIZE = 60

function photosQueryKey(projectId: number, ratingStatus?: RatingFilter) {
  return ['photos', projectId, ratingStatus ?? null] as const
}

export function usePhotoSequenceQuery(
  projectId: number,
  ratingStatus?: RatingFilter,
  pageSize: number = PHOTOS_PAGE_SIZE
) {
  return useInfiniteQuery({
    queryKey: photosQueryKey(projectId, ratingStatus),
    queryFn: ({ pageParam }: { pageParam: number }) =>
      listPhotos(projectId, { ratingStatus, limit: pageSize, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage: PhotoListOut, allPages: PhotoListOut[]) => {
      const loaded = allPages.reduce((sum, loadedPage) => sum + loadedPage.items.length, 0)
      return loaded < lastPage.total ? loaded : undefined
    },
  })
}

export function useSetRatingMutation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, status }: { photoId: number; status: RatingStatus }) =>
      setRating(photoId, status),
    onSuccess: () => {
      // Ohne Filter im Key: invalidiert alle Filtervarianten dieses Projekts, da eine
      // Bewertungsaenderung die Zugehoerigkeit zu MEHREREN Filtern gleichzeitig aendern kann
      // (z.B. raus aus "unbewertet", rein in "favorite").
      void queryClient.invalidateQueries({ queryKey: ['photos', projectId] })
    },
  })
}

export function useDeleteRatingMutation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (photoId: number) => deleteRating(photoId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['photos', projectId] })
    },
  })
}
