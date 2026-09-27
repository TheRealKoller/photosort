import { useEffect } from 'react'
import type { SetURLSearchParams } from 'react-router'

import { parsePersonIds, withPersonIds } from '../utils/personFilter'
import { usePersonsQuery } from './usePersons'

/**
 * Der Personenfilter einer Ansicht über `?person=<id>` (Spec 0292). Eine unbekannte Id wird erst
 * NACH dem Laden der Personen per `replace` aus der Adresse entfernt - solange die Liste lädt,
 * bleibt die Adresse unverändert.
 */
export function usePersonFilter(
  searchParams: URLSearchParams,
  setSearchParams: SetURLSearchParams,
) {
  const personsQuery = usePersonsQuery()
  const personIds = parsePersonIds(searchParams)
  const known = personsQuery.data
  const unknown =
    known !== undefined && personIds.some((id) => !known.some((person) => person.id === id))

  useEffect(() => {
    if (!unknown || known === undefined) {
      return
    }
    const kept = personIds.filter((id) => known.some((person) => person.id === id))
    setSearchParams(withPersonIds(searchParams, kept), { replace: true })
  }, [unknown, known, personIds, searchParams, setSearchParams])

  function setPersonIds(ids: readonly number[]): void {
    setSearchParams(withPersonIds(searchParams, ids))
  }

  return { personsQuery, personIds: unknown ? [] : personIds, setPersonIds }
}
