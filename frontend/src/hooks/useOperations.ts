import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import {
  cancelAllOperations,
  cancelOperation,
  listOperations,
  operationsQueryKey,
} from '../api/operations'
import type { OperationKind } from '../api/types'
import { POLL_INTERVAL_MS } from './useProjects'

/**
 * Die Vorgaenge des Projekts. Sie traegt die Projektleiste UND den Dialog - beide
 * brauchen dieselbe, live gepollte Liste, deshalb eine gemeinsame Abfrage.
 *
 * Gepollt wird nur, solange die Liste nicht leer ist: ein Projekt ohne laufenden Vorgang kostet
 * genau einen Abruf. Ausloeser und Abbruche invalidieren den Schluessel, damit ein gerade
 * gestarteter Vorgang sofort in der Leiste steht.
 */
export function useOperationsQuery(projectId: number) {
  return useQuery({
    queryKey: operationsQueryKey(projectId),
    queryFn: () => listOperations(projectId),
    refetchInterval: (query) => {
      const operations = query.state.data?.operations
      return operations !== undefined && operations.length > 0 ? POLL_INTERVAL_MS : false
    },
  })
}

/**
 * Nach einem Abbruch ist nicht nur das Projekt veraltet: die Pruefungsliste und der Pruefungskopf
 * zeigen denselben Lauf, der Export-Lauf seine Zaehler. Alle vier Praefixe werden deshalb
 * invalidiert - eine davon stehen zu lassen hiesse, zwei Wahrheiten ueber denselben Lauf zu
 * zeigen.
 */
function invalidateAfterCancel(queryClient: QueryClient, projectId: number): void {
  void queryClient.invalidateQueries({ queryKey: ['project', projectId] })
  void queryClient.invalidateQueries({ queryKey: ['classificationReviews', projectId] })
  void queryClient.invalidateQueries({ queryKey: ['classificationReview', projectId] })
  void queryClient.invalidateQueries({ queryKey: ['export-run', projectId] })
  void queryClient.invalidateQueries({ queryKey: operationsQueryKey(projectId) })
}

/** Bittet um den Abbruch EINES Vorgangs; der Knopf bleibt bis zum Ende gesperrt. */
export function useCancelOperation(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ kind, runId }: { kind: OperationKind; runId: number }) =>
      cancelOperation(projectId, kind, runId),
    onSuccess: () => invalidateAfterCancel(queryClient, projectId),
  })
}

/** Bittet um den Abbruch aller laufenden und wartenden Vorgaenge des Projekts. */
export function useCancelAllOperations(projectId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => cancelAllOperations(projectId),
    onSuccess: () => invalidateAfterCancel(queryClient, projectId),
  })
}
