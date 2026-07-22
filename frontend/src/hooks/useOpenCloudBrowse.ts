import { useQuery } from '@tanstack/react-query'

import { browseFolder } from '../api/opencloud'

export function useOpenCloudBrowseQuery(path: string) {
  return useQuery({
    queryKey: ['opencloud', 'browse', path],
    queryFn: () => browseFolder(path),
    // Jede Ebene ist unter ihrem eigenen Pfad-Query-Key gecached; ohne staleTime wuerde React
    // Query eine bereits geladene Ebene bei jedem erneuten Mounten (z.B. Breadcrumb-Ruecksprung)
    // trotzdem im Hintergrund neu anfragen (siehe specs/features/0005-minimal-project-frontend.md,
    // Akzeptanzkriterium "ohne dass eine bereits geladene Ebene erneut angefragt wird").
    staleTime: Infinity,
  })
}
