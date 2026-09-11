import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  deleteCategoryOverride,
  listCurationCandidates,
  listPhotos,
  setCategoryOverride,
} from '../api/photos'
import { deleteRating, setRating } from '../api/ratings'
import type { CategoryKey, PhotoListOut, RatingFilter, RatingStatus } from '../api/types'

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

// Kategorie-Kuratierung (specs/features/0037-gatefuehrte-bewertungs-pipeline-mit-backfill.md):
// bewusst unter demselben ['photos', projectId, ...]-Praefix wie photosQueryKey oben - die
// bestehende, breite Invalidierung in useSetRatingMutation/useDeleteRatingMutation
// (queryKey: ['photos', projectId], ohne exact) invalidiert React-Query-seitig automatisch auch
// diese Query, ohne dass die Kuratierungs-Ansicht einen eigenen Invalidierungs-Pfad braucht.
function curationQueryKey(projectId: number, topN: number) {
  return ['photos', projectId, 'curate', topN] as const
}

export function useCurationQuery(projectId: number, topN: number) {
  return useQuery({
    queryKey: curationQueryKey(projectId, topN),
    queryFn: () => listPhotos(projectId, { topNPerCategory: topN }),
  })
}

// specs/features/0357-voller-bildvorrat-kuratierung.md: derselbe ['photos', projectId]-Praefix wie
// oben, und hier ist er nicht Bequemlichkeit, sondern Bedingung: die nachgeladenen Kandidaten sind
// eine ZWEITE Query ueber demselben Datensatz auf demselben Bildschirm. Dasselbe Foto kann in
// beiden Listen stehen; wird es in der einen verworfen, muss die andere denselben Zustand zeigen.
// Genau das leistet die bestehende breite Invalidierung - ohne den Praefix stuenden zwei
// Wahrheiten ueber dasselbe Foto nebeneinander.
function curationCandidatesQueryKey(
  projectId: number,
  clusterKey: string,
  categoryKey: string,
  afterRank: number,
) {
  return ['photos', projectId, 'curate', 'candidates', clusterKey, categoryKey, afterRank] as const
}

export interface CurationCandidatesQueryParams {
  clusterKey: string
  categoryKey: string
  afterRank: number
  /** Der Request laeuft ausschliesslich im AUFGEKLAPPTEN Zustand. */
  enabled: boolean
  pageSize?: number
}

export function useCurationCandidatesQuery(
  projectId: number,
  {
    clusterKey,
    categoryKey,
    afterRank,
    enabled,
    pageSize = PHOTOS_PAGE_SIZE,
  }: CurationCandidatesQueryParams,
) {
  return useInfiniteQuery({
    queryKey: curationCandidatesQueryKey(projectId, clusterKey, categoryKey, afterRank),
    queryFn: ({ pageParam }: { pageParam: number }) =>
      listCurationCandidates(projectId, {
        clusterKey,
        categoryKey,
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

// specs/features/0055-remote-kategorie-klassifizierung-mit-kostenschaetzung.md, ADR 0032 Punkt 7:
// wirkt sofort (worker.py::reassign_photo_category im selben API-Request) - dieselbe breite
// Invalidierung wie useSetRatingMutation genuegt, das Foto wechselt dadurch sichtbar in seine neue
// Cluster x Kategorie-Sektion, sobald die Kuratierungs-Query neu geladen wird.
export function useSetCategoryOverrideMutation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, categoryKey }: { photoId: number; categoryKey: CategoryKey }) =>
      setCategoryOverride(photoId, categoryKey),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['photos', projectId] })
    },
  })
}

export function useDeleteCategoryOverrideMutation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (photoId: number) => deleteCategoryOverride(photoId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['photos', projectId] })
    },
  })
}
