import { apiFetch } from './client'
import type { BrowseEntry, FolderCountOut } from './types'

/**
 * Laedt genau eine Ebene (die direkten Unterordner) des uebergebenen Pfads. Ein leerer Pfad laedt
 * die Wurzelebene ohne Query-Parameter.
 */
export function browseFolder(path: string): Promise<BrowseEntry[]> {
  const query = path ? `?path=${encodeURIComponent(path)}` : ''
  return apiFetch<BrowseEntry[]>(`/opencloud/browse${query}`)
}

/**
 * Laedt die rekursive Bilddatei-Anzahl (mit Obergrenze) fuer jeden direkten Unterordner des
 * uebergebenen Pfads - derselbe Pfad wie beim begleitenden browseFolder()-Aufruf.
 */
export function fetchFolderCounts(path: string): Promise<FolderCountOut[]> {
  const query = path ? `?path=${encodeURIComponent(path)}` : ''
  return apiFetch<FolderCountOut[]>(`/opencloud/folder-counts${query}`)
}
