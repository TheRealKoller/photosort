import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { listCurationCandidates, listPhotos } from '../api/photos'
import { deleteRating, setFavorite, setRating } from '../api/ratings'
import type { PhotoListOut, RatingFilter, RatingStatus } from '../api/types'

/**
 * Batch-Groesse fuer das Foto-Listing: Fotos werden paginiert geladen (Batches statt Gesamt-Reload
 * bei tausenden Fotos). Grid- und Einzelbild-/Swipe-Ansicht teilen sich denselben Query-Key (siehe
 * unten) und damit dieselben bereits geladenen Batches - "Navigation/Shortcuts operieren auf der
 * zuletzt geladenen, gefilterten Foto-ID-Liste", kein separater "naechstes Foto"-Endpunkt noetig.
 */
export const PHOTOS_PAGE_SIZE = 60

function photosQueryKey(projectId: number, ratingStatus?: RatingFilter) {
  return ['photos', projectId, ratingStatus ?? null] as const
}

// Kuratierung: bewusst unter demselben ['photos', projectId, ...]-Praefix wie
// photosQueryKey oben - die bestehende, breite Invalidierung in
// useSetRatingMutation/useDeleteRatingMutation (queryKey: ['photos', projectId], ohne exact)
// invalidiert React-Query-seitig automatisch auch diese Query, ohne dass die Kuratierungs-Ansicht
// einen eigenen Invalidierungs-Pfad braucht.
function curationQueryKey(projectId: number) {
  return ['photos', projectId, 'curate'] as const
}

/**
 * Der Auswahlvorschlag des Projekts. KEIN Leseparameter mehr im Schluessel: welche Fotos der
 * Vorschlag umfasst, ist eine Eigenschaft des Laufs und keine der Anfrage - eine zweite Variante
 * desselben Projekts kann es nicht geben.
 */
export function useCurationQuery(projectId: number) {
  return useQuery({
    queryKey: curationQueryKey(projectId),
    queryFn: () => listPhotos(projectId, { selection: true }),
  })
}

// Derselbe ['photos', projectId]-Praefix wie oben, und hier ist er nicht Bequemlichkeit, sondern
// Bedingung: die nachgeladenen Kandidaten sind eine ZWEITE Query ueber demselben Datensatz auf
// demselben Bildschirm. Dasselbe Foto kann in beiden Listen stehen; wird es in der einen verworfen,
// muss die andere denselben Zustand zeigen. Genau das leistet die bestehende breite Invalidierung -
// ohne den Praefix stuenden zwei Wahrheiten ueber dasselbe Foto nebeneinander.
function curationCandidatesQueryKey(projectId: number, eventId: number, afterRank: number) {
  return ['photos', projectId, 'curate', 'candidates', eventId, afterRank] as const
}

export interface CurationCandidatesQueryParams {
  eventId: number
  afterRank: number
  /** Der Request laeuft ausschliesslich im AUFGEKLAPPTEN Zustand. */
  enabled: boolean
  pageSize?: number
}

export function useCurationCandidatesQuery(
  projectId: number,
  { eventId, afterRank, enabled, pageSize = PHOTOS_PAGE_SIZE }: CurationCandidatesQueryParams,
) {
  return useInfiniteQuery({
    queryKey: curationCandidatesQueryKey(projectId, eventId, afterRank),
    queryFn: ({ pageParam }: { pageParam: number }) =>
      listCurationCandidates(projectId, {
        eventId,
        afterRank,
        limit: pageSize,
        offset: pageParam,
      }),
    initialPageParam: 0,
    // Identisch zu usePhotoSequenceQuery: der naechste Offset ist die Zahl der bereits geladenen
    // Eintraege, und `total` ist die Restmenge der Partition (nicht die Seitengroesse).
    getNextPageParam: (lastPage: PhotoListOut, allPages: PhotoListOut[]) => {
      const loaded = allPages.reduce((sum, loadedPage) => sum + loadedPage.items.length, 0)
      return loaded < lastPage.total ? loaded : undefined
    },
    enabled,
  })
}

export function usePhotoSequenceQuery(
  projectId: number,
  ratingStatus?: RatingFilter,
  pageSize: number = PHOTOS_PAGE_SIZE,
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

/**
 * Das Favoriten-Kennzeichen - eigene Mutation auf einem eigenen Endpunkt, damit die
 * Albumentscheidung dabei unberührt bleibt.
 *
 * Dieselbe breite Invalidierung wie bei der Albumentscheidung: Das Kennzeichen entscheidet über
 * die Zugehörigkeit zum Filter "Favorit", und der Filter steckt im Query-Key.
 */
export function useSetFavoriteMutation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, favorite }: { photoId: number; favorite: boolean }) =>
      setFavorite(photoId, favorite),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['photos', projectId] })
    },
  })
}
