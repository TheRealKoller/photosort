import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError } from '../api/client'
import { deletePerson, listPersons } from '../api/persons'

/** Die festgelegten Personen - global, für alle Projekte. EIN Schlüssel, damit jede Stelle
 * (Detailansicht, Filter, `/persons`) nach einer Änderung dieselbe Liste neu lädt. */
export const PERSONS_QUERY_KEY = ['persons'] as const

export function usePersonsQuery() {
  return useQuery({ queryKey: PERSONS_QUERY_KEY, queryFn: listPersons })
}

/**
 * Entfernt eine Person. Ein `404` zählt als Erfolg: Die Person war schon entfernt, und das Ziel
 * des Nutzers ist damit erreicht. Danach lädt die Personenliste neu, und alle Fotolisten ALLER
 * Projekte gelten als veraltet - ihr `persons` nennt die entfernte Person noch.
 */
export function useDeletePersonMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (personId: number) => {
      try {
        await deletePerson(personId)
      } catch (cause) {
        if (!(cause instanceof ApiError && cause.status === 404)) {
          throw cause
        }
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PERSONS_QUERY_KEY })
      void queryClient.invalidateQueries({ queryKey: ['photos'] })
    },
  })
}
