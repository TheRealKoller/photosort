import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback } from 'react'

import { getOverviewSeen, markOverviewSeen } from '../api/projectOverview'
import type { OverviewSeenOut } from '../api/types'
import { decodeUsername } from '../auth/jwt'
import { getToken } from '../auth/token'

/**
 * Schlüssel EINSCHLIESSLICH des Nutzernamens: Der Abfrage-Cache überlebt eine Abmeldung im selben
 * Tab, und ohne den Namen sähe die nächste Person den Merker der vorigen. `decodeUsername` trennt
 * nur den Cache und trägt keine Zugriffsentscheidung.
 */
export function overviewSeenQueryKey(projectId: number) {
  const token = getToken()
  return ['overview-seen', token ? decodeUsername(token) : null, projectId] as const
}

/**
 * `retry: false`, damit ein Lesefehler sofort als Fehler ankommt - der Host zeigt die Übersicht
 * dann lieber einmal zu oft. `staleTime: Infinity`: Der Merker ändert sich nur durch die eigene
 * Hand, ein Projekt-Poll löst keinen zweiten Leseaufruf aus.
 */
export function useOverviewSeen(projectId: number) {
  return useQuery({
    queryKey: overviewSeenQueryKey(projectId),
    queryFn: () => getOverviewSeen(projectId),
    retry: false,
    staleTime: Infinity,
  })
}

/**
 * Merkt "gesehen": lokal sofort, auf dem Server ohne Fehleranzeige. Scheitert das Schreiben,
 * erscheint die Übersicht in dieser Sitzung nicht erneut, nach einem Neuladen schon.
 */
export function useMarkOverviewSeen(projectId: number): () => void {
  const queryClient = useQueryClient()
  return useCallback(() => {
    queryClient.setQueryData<OverviewSeenOut>(overviewSeenQueryKey(projectId), { seen: true })
    markOverviewSeen(projectId).catch(() => undefined)
  }, [queryClient, projectId])
}
