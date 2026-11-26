import { apiFetch } from './client'
import type { BrowseEntry, FolderCountOut } from './types'

/**
 * Laedt genau eine Ebene (die direkten Unterordner) des uebergebenen Pfads. Ein leerer Pfad laedt
 * die Wurzelebene ohne Query-Parameter.
 */
export function browseFolder(path: string): Promise<BrowseEntry[]> {
  return apiFetch('/opencloud/browse', { query: path ? { path } : {} })
}

/**
 * Laedt die rekursive Bilddatei-Anzahl (mit Obergrenze) fuer jeden direkten Unterordner des
 * uebergebenen Pfads - derselbe Pfad wie beim begleitenden browseFolder()-Aufruf.
 */
export function fetchFolderCounts(path: string): Promise<FolderCountOut[]> {
  return apiFetch('/opencloud/folder-counts', { query: path ? { path } : {} })
}
