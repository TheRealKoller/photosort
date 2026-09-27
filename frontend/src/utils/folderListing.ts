import type { BrowseEntry, FolderCountOut } from '../api/types'

/*
 * Sortieren und Filtern der Unterordner einer Ebene im Ordner-Browser — rein, ohne React-/DOM-Bezug.
 *
 * Gefiltert wird vor dem Sortieren und nur über `name`, nie über `path`: Der Name eines
 * Elternordners ist kein Treffer. Jeder Gleichstand fällt auf Name A–Z zurück, und Name A–Z selbst
 * endet im Codeeinheiten-Vergleich, damit die Reihenfolge nicht von der Lieferreihenfolge abhängt.
 */

export type FolderSort = 'name_asc' | 'name_desc' | 'count_desc' | 'modified_desc'

export const DEFAULT_FOLDER_SORT: FolderSort = 'name_asc'

export interface ArrangeOptions {
  sort: FolderSort
  searchTerm: string
  counts: FolderCountOut[] | undefined
  // Die Zähler-Query der Ebene lädt nicht mehr — dieselbe Bedingung wie beim Lade-Spinner.
  countsSettled: boolean
}

export interface ArrangedFolders {
  entries: BrowseEntry[]
  // Bildanzahl gewählt, Zähler noch nicht eingetroffen: vorläufig in Name A–Z.
  provisional: boolean
}

const NAME_COLLATOR = new Intl.Collator('de', { numeric: true, sensitivity: 'base' })

function compareNames(a: BrowseEntry, b: BrowseEntry): number {
  const collated = NAME_COLLATOR.compare(a.name, b.name)
  if (collated !== 0) {
    return collated
  }
  return a.name < b.name ? -1 : a.name > b.name ? 1 : 0
}

// Gruppen der Bildanzahl in fester Folge: 500+, exakte Zahl, Fehler (auch: kein Eintrag).
function countRank(count: FolderCountOut | undefined): number {
  if (!count || count.error) {
    return 2
  }
  return count.at_limit ? 0 : 1
}

function byCount(counts: FolderCountOut[] | undefined) {
  const byPath = new Map((counts ?? []).map((count) => [count.path, count]))
  return (a: BrowseEntry, b: BrowseEntry): number => {
    const countA = byPath.get(a.path)
    const countB = byPath.get(b.path)
    const rankA = countRank(countA)
    const rankB = countRank(countB)
    if (rankA !== rankB) {
      return rankA - rankB
    }
    if (rankA === 1 && countA && countB && countA.count !== countB.count) {
      return countB.count - countA.count
    }
    return compareNames(a, b)
  }
}

function byModified(a: BrowseEntry, b: BrowseEntry): number {
  const timeA = a.modified_at === null ? null : Date.parse(a.modified_at)
  const timeB = b.modified_at === null ? null : Date.parse(b.modified_at)
  if (timeA !== timeB) {
    if (timeA === null) {
      return 1
    }
    if (timeB === null) {
      return -1
    }
    return timeB - timeA
  }
  return compareNames(a, b)
}

function matchesTerm(entries: BrowseEntry[], searchTerm: string): BrowseEntry[] {
  const term = searchTerm.trim().toLocaleLowerCase('de')
  if (term === '') {
    return entries
  }
  return entries.filter((entry) => entry.name.toLocaleLowerCase('de').includes(term))
}

export function arrangeFolders(
  entries: BrowseEntry[],
  { sort, searchTerm, counts, countsSettled }: ArrangeOptions,
): ArrangedFolders {
  const matching = [...matchesTerm(entries, searchTerm)]
  const provisional = sort === 'count_desc' && !countsSettled

  if (provisional || sort === 'name_asc') {
    return { entries: matching.sort(compareNames), provisional }
  }
  if (sort === 'name_desc') {
    return { entries: matching.sort(compareNames).reverse(), provisional }
  }
  if (sort === 'count_desc') {
    return { entries: matching.sort(byCount(counts)), provisional }
  }
  return { entries: matching.sort(byModified), provisional }
}
