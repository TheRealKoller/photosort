import { apiFetch } from './client'
import type { BrowseEntry } from './types'

/**
 * Laedt genau eine Ebene (die direkten Unterordner) des uebergebenen Pfads. Ein leerer Pfad
 * laedt die Wurzelebene ohne Query-Parameter (siehe specs/features/0005-minimal-project-frontend.md).
 */
export function browseFolder(path: string): Promise<BrowseEntry[]> {
  const query = path ? `?path=${encodeURIComponent(path)}` : ''
  return apiFetch<BrowseEntry[]>(`/opencloud/browse${query}`)
}
