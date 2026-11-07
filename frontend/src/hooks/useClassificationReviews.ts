import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createClassificationReview,
  exportClassificationReview,
  getClassificationReview,
  getClassificationReviewEstimate,
  getClassificationReviewOptions,
  listClassificationReviewCases,
  listClassificationReviews,
  setClassificationReviewVerdict,
} from '../api/classificationReviews'
import type {
  ClassificationReviewCasesOut,
  ClassificationReviewCreateBody,
  ClassificationReviewDetailOut,
  ClassificationReviewListItemOut,
  ClassificationReviewSideIn,
  ClassificationVerdict,
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

/** Kopf und Zaehlungen EINER Pruefung; gepollt nur, solange sie laeuft. */
export function useClassificationReviewQuery(projectId: number, reviewId: number) {
  return useQuery({
    queryKey: ['classificationReview', projectId, reviewId],
    queryFn: () => getClassificationReview(projectId, reviewId),
    refetchInterval: (query) => {
      const review = query.state.data as ClassificationReviewDetailOut | undefined
      return review?.status === 'running' ? POLL_INTERVAL_MS : false
    },
  })
}

/**
 * Die vorgelegten Faelle - erst nach `SUCCESS` geladen. Waehrend des Laufs ist die Liste leer;
 * ein Abruf dann stuende nach dem Abschluss als veralteter leerer Stand im Zwischenspeicher.
 */
export function useClassificationReviewCasesQuery(
  projectId: number,
  reviewId: number,
  enabled: boolean,
) {
  return useQuery({
    queryKey: ['classificationReviewCases', projectId, reviewId],
    queryFn: () => listClassificationReviewCases(projectId, reviewId),
    enabled,
  })
}

/**
 * Setzt das Urteil EINES Falls. Die Antwort traegt Urteil und Schreiber; sie wird direkt in die
 * Fallliste geschrieben (kein Neuladen aller Faelle je Tastendruck). Die Zaehlungen im Kopf und
 * der Stand in der Liste haengen am Urteil und werden neu geladen.
 */
export function useSetClassificationReviewVerdictMutation(projectId: number, reviewId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ caseId, verdict }: { caseId: number; verdict: ClassificationVerdict }) =>
      setClassificationReviewVerdict(projectId, reviewId, caseId, verdict),
    onSuccess: (written) => {
      queryClient.setQueryData<ClassificationReviewCasesOut>(
        ['classificationReviewCases', projectId, reviewId],
        (current) =>
          current && {
            cases: current.cases.map((reviewCase) =>
              reviewCase.id === written.case_id
                ? {
                    ...reviewCase,
                    verdict: written.verdict,
                    updated_by: written.updated_by,
                    updated_at: written.updated_at,
                  }
                : reviewCase,
            ),
          },
      )
      void queryClient.invalidateQueries({
        queryKey: ['classificationReview', projectId, reviewId],
      })
      void queryClient.invalidateQueries({ queryKey: ['classificationReviews', projectId] })
    },
  })
}

/**
 * Laedt die Exportdatei authentifiziert als Blob und uebergibt sie dem Browser als Download. Kein
 * `<a href>` auf den Endpunkt: der Token ginge sonst nicht mit. Der Dateiname traegt wie der
 * Server-Header nur die Id der Pruefung.
 */
export function useExportClassificationReviewMutation(projectId: number, reviewId: number) {
  return useMutation({
    mutationFn: () => exportClassificationReview(projectId, reviewId),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `klassifizierungspruefung-${reviewId}.json`
      document.body.append(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    },
  })
}
