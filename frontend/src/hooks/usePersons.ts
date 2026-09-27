import { useQuery } from '@tanstack/react-query'

import { listPersons } from '../api/persons'

/** Die festgelegten Personen - global, für alle Projekte. EIN Schlüssel, damit jede Stelle
 * (Detailansicht, Filter, `/persons`) nach einer Änderung dieselbe Liste neu lädt. */
export const PERSONS_QUERY_KEY = ['persons'] as const

export function usePersonsQuery() {
  return useQuery({ queryKey: PERSONS_QUERY_KEY, queryFn: listPersons })
}
