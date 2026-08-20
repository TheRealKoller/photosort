import { useQuery } from '@tanstack/react-query'

import { fetchFolderCounts } from '../api/opencloud'

/**
 * Bilddatei-Anzahl pro direktem Unterordner (specs/features/0050-dateianzahl-im-ordner-
 * browser.md) - identisches Cache-Muster wie useOpenCloudBrowseQuery (eigener Query-Key pro
 * Pfad, staleTime: Infinity), damit ein zwischenzeitlicher Ruecksprung auf eine bereits
 * geladene Ebene keinen erneuten Request ausloest.
 */
export function useOpenCloudFolderCountsQuery(path: string) {
  return useQuery({
    queryKey: ['opencloud', 'folder-counts', path],
    queryFn: () => fetchFolderCounts(path),
    staleTime: Infinity,
  })
}
