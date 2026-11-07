import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createClassificationReview,
  getClassificationReviewEstimate,
  getClassificationReviewOptions,
  listClassificationReviews,
} from '../api/classificationReviews'
import type {
  ClassificationReviewCreateBody,
  ClassificationReviewListItemOut,
  ClassificationReviewSideIn,
} from '../api/types'
import { POLL_INTERVAL_MS } from './useProjects'

/**
 * Die Pruefungen eines Projekts, neueste zuerst - die Reihenfolge kommt vom Server und wird hier
 * nicht nachgebaut. Gepollt wird nur, solange wirklich eine Pruefung laeuft: ein stehender
 * Endpunkt wird nicht im Hintergrund belastet.
 */
export function useClassificationReviewsQuery(projectId: number) {
  return useQuery({
    queryKey: ['classificationReviews', projectId],
    queryFn: () => listClassificationReviews(projectId),
    refetchInterval: (query) => {
      const reviews = query.state.data as ClassificationReviewListItemOut[] | undefined
      return reviews?.some((review) => review.status === 'running') ? POLL_INTERVAL_MS : false
    },
  })
}

/** Waehlbare Verfahren samt Sperrgruenden. Geladen erst, wenn das Panel geoeffnet ist. */
export function useClassificationReviewOptionsQuery(projectId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['classificationReviewOptions', projectId],
    queryFn: () => getClassificationReviewOptions(projectId),
    enabled,
  })
}

/**
 * Die Kostenvorschau, sobald BEIDE Seiten gewaehlt sind. Vorher gibt es keinen Durchlauf, dessen
 * Kosten sie beschriebe - der Aufruf unterbleibt deshalb ganz (`enabled: false`).
 */
export function useClassificationReviewEstimateQuery(
  projectId: number,
  sides: { a: ClassificationReviewSideIn; b: ClassificationReviewSideIn } | null,
) {
  return useQuery({
    queryKey: ['classificationReviewEstimate', projectId, sides],
    queryFn: () => getClassificationReviewEstimate(projectId, sides!),
    enabled: sides !== null,
  })
}

/** Legt eine Pruefung an; danach ist die Liste veraltet und wird neu geladen. */
export function useCreateClassificationReviewMutation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: ClassificationReviewCreateBody) =>
      createClassificationReview(projectId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['classificationReviews', projectId] })
    },
  })
}
