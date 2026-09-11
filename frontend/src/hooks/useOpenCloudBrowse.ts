import { useQuery } from '@tanstack/react-query'

import { browseFolder } from '../api/opencloud'

export function useOpenCloudBrowseQuery(path: string) {
  return useQuery({
    queryKey: ['opencloud', 'browse', path],
    queryFn: () => browseFolder(path),
    // Jede Ebene ist unter ihrem eigenen Pfad-Query-Key gecached; ohne staleTime wuerde React
    // Query eine bereits geladene Ebene bei jedem erneuten Mounten (z.B. Breadcrumb-Ruecksprung)
    // trotzdem im Hintergrund neu anfragen - eine bereits geladene Ebene wird nicht erneut
    // angefragt.
    staleTime: Infinity,
  })
}
