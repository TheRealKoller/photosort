import type { UseQueryResult } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'

import { ApiError } from '../api/client'
import type { BrowseEntry, FolderCountOut } from '../api/types'
import { cn } from '../lib/utils'
import { arrangeFolders, DEFAULT_FOLDER_SORT } from '../utils/folderListing'
import type { FolderSort } from '../utils/folderListing'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { useOpenCloudBrowseQuery } from '../hooks/useOpenCloudBrowse'
import { useOpenCloudFolderCountsQuery } from '../hooks/useOpenCloudFolderCounts'

const SORT_OPTIONS: { value: FolderSort; label: string }[] = [
  { value: 'name_asc', label: 'Name A–Z' },
  { value: 'name_desc', label: 'Name Z–A' },
  { value: 'count_desc', label: 'Bildanzahl, meiste zuerst' },
  { value: 'modified_desc', label: 'Änderungsdatum, neueste zuerst' },
]

const PROVISIONAL_HINT = 'Vorläufig nach Name sortiert – die Bildanzahl wird noch gezählt.'

interface Breadcrumb {
  label: string
  path: string
}

interface FolderBrowserProps {
  value: string
  onChange: (path: string) => void
  // Ueber die kontrollierte Komponente (value/onChange) hinausgehend, aber noetig, damit bei einem
  // Backend-Fehler beim Browse der Submit deaktiviert bleibt - der Elternseite bleibt sonst keine
  // Moeglichkeit, den internen Ladefehler dieser Komponente zu kennen.
  onErrorChange?: (hasError: boolean) => void
}

// Eager-Zaehler neben Listeneintraegen: vier moegliche Anzeigezustaende pro gelistetem Unterordner.
type FolderCountDisplay =
  { kind: 'loading' } | { kind: 'count'; count: number } | { kind: 'at_limit' } | { kind: 'error' }

function folderCountDisplayFor(
  path: string,
  counts: { isLoading: boolean; isError: boolean; data: FolderCountOut[] | undefined },
): FolderCountDisplay {
  if (counts.isLoading) {
    return { kind: 'loading' }
  }
  const match = counts.data?.find((item) => item.path === path)
  if (counts.isError || !match || match.error) {
    return { kind: 'error' }
  }
  if (match.at_limit) {
    return { kind: 'at_limit' }
  }
  return { kind: 'count', count: match.count }
}

/**
 * Rechtsbuendiger Zaehler-/Statusbereich neben einem Unterordner-Namen. Blockiert nie die
 * Navigation in den betroffenen Ordner - auch der Fehlerzustand ist rein informativ.
 */
function FolderCountIndicator({ display }: { display: FolderCountDisplay }) {
  if (display.kind === 'loading') {
    return (
      <span
        data-testid="folder-count-loading"
        aria-hidden="true"
        className="size-3.5 shrink-0 animate-spin motion-reduce:animate-none rounded-full border-2 border-current border-t-transparent text-text"
      />
    )
  }
  if (display.kind === 'error') {
    return (
      <span
        className="shrink-0 text-sm text-text"
        title="Zählung nicht verfügbar"
        aria-label="Zählung nicht verfügbar"
      >
        ?
      </span>
    )
  }
  if (display.kind === 'at_limit') {
    return (
      <span
        className="shrink-0 text-sm text-text"
        title="Mindestens 500 Bilder"
        aria-label="Mindestens 500 Bilder"
      >
        500+
      </span>
    )
  }
  return <span className="shrink-0 text-sm text-text">{display.count}</span>
}

function breadcrumbsFor(path: string): Breadcrumb[] {
  const segments = path.split('/').filter(Boolean)
  const crumbs: Breadcrumb[] = [{ label: 'Wurzel', path: '' }]
  let current = ''
  for (const segment of segments) {
    current = current ? `${current}/${segment}` : segment
    crumbs.push({ label: segment, path: current })
  }
  return crumbs
}

interface FolderLevelProps {
  browse: UseQueryResult<BrowseEntry[]>
  counts: UseQueryResult<FolderCountOut[]>
  sort: FolderSort
  onSortChange: (sort: FolderSort) => void
  onChange: (path: string) => void
}

/**
 * Eine Ebene des Browsers: Bedienzeile, Hinweiszeile, Liste bzw. Leerzustand. Wird je `value` neu
 * gemountet, damit der Suchbegriff bei jedem Ordnerwechsel leer beginnt.
 *
 * SICHERHEIT: Der Suchbegriff stammt allein aus dem Suchfeld und lebt nur in diesem Zustand - nie
 * aus URL oder Query-Parameter. Er erscheint ausschließlich als React-Textknoten; ein Markup-String
 * brächte über einen präparierten Link Skript in die Seite, das das JWT aus `localStorage` liest.
 */
function FolderLevel({ browse, counts, sort, onSortChange, onChange }: FolderLevelProps) {
  const [searchTerm, setSearchTerm] = useState('')
  const searchRef = useRef<HTMLInputElement>(null)
  const searchId = useId()
  const sortId = useId()

  // Reihenfolge, Hinweis und Zähler-Spinner hängen an derselben Bedingung im selben Render
  // (`counts.isLoading`) - ein nachziehender Effekt zeigte einen Zwischenstand und sortierte
  // zweimal.
  const arranged = browse.isSuccess
    ? arrangeFolders(browse.data, {
        sort,
        searchTerm,
        counts: counts.isError ? undefined : counts.data,
        countsSettled: !counts.isLoading,
      })
    : null
  const levelHasFolders = browse.isSuccess && browse.data.length > 0
  const showHint = levelHasFolders && arranged !== null && arranged.provisional
  const trimmedTerm = searchTerm.trim()

  const errorDetail =
    browse.isError && browse.error instanceof ApiError
      ? browse.error.detail
      : browse.isError
        ? 'Unerwarteter Fehler beim Laden der Ordner.'
        : null

  function handleSearchKeyDown(event: KeyboardEvent<HTMLInputElement>): void {
    // Das Feld steht im Formular der Projektanlage: Enter löste dort implizit "Projekt anlegen"
    // aus.
    if (event.key === 'Enter') {
      event.preventDefault()
    } else if (event.key === 'Escape' && searchTerm !== '') {
      setSearchTerm('')
    }
  }

  function resetSearch(): void {
    setSearchTerm('')
    searchRef.current?.focus()
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex flex-col gap-2 sm:flex-1">
            <label htmlFor={searchId} className="text-xs font-medium text-text-h">
              Unterordner durchsuchen
            </label>
            <Input
              id={searchId}
              ref={searchRef}
              type="text"
              placeholder="Teil des Ordnernamens"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              onKeyDown={handleSearchKeyDown}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label htmlFor={sortId} className="text-xs font-medium text-text-h">
              Sortierung
            </label>
            <select
              id={sortId}
              value={sort}
              onChange={(event) => onSortChange(event.target.value as FolderSort)}
              className="h-11 w-full sm:w-auto rounded-sm border border-border-control bg-surface px-3 text-sm text-text-h"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        {/* Ständig im DOM, damit das Erscheinen des Hinweises angesagt wird; ohne Text ohne Höhe
            und Abstand. */}
        <p role="status" className={cn('text-sm text-text', showHint && 'mt-2')}>
          {showHint ? PROVISIONAL_HINT : null}
        </p>
      </div>

      {browse.isLoading && (
        <p role="status" className="text-sm text-text">
          Ordner werden geladen…
        </p>
      )}
      {errorDetail && <Alert>{errorDetail}</Alert>}
      {browse.isSuccess && !levelHasFolders && (
        <p className="text-sm text-text">Dieser Ordner hat keine Unterordner.</p>
      )}
      {levelHasFolders && arranged?.entries.length === 0 && trimmedTerm !== '' && (
        <div className="flex flex-col gap-3 text-sm text-text">
          <p className="break-words">Kein Unterordner enthält „{trimmedTerm}“ im Namen.</p>
          <Button type="button" variant="outline" className="self-start" onClick={resetSearch}>
            Suche zurücksetzen
          </Button>
        </div>
      )}
      {arranged !== null && arranged.entries.length > 0 && (
        <ul className="flex flex-col gap-1">
          {arranged.entries.map((entry) => (
            <li key={entry.path} className="flex items-center justify-between gap-3">
              <Button
                type="button"
                variant="ghost"
                className="flex-1 justify-start"
                onClick={() => onChange(entry.path)}
              >
                {entry.name}
              </Button>
              <FolderCountIndicator display={folderCountDisplayFor(entry.path, counts)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * Kontrollierte Ordner-Navigation per Pfad-Drilldown. Laedt pro Aufruf nur die direkten Unterordner
 * von `value` - "Navigation" entsteht rein client-seitig, React Query cached jede Ebene unter ihrem
 * eigenen Query-Key, kein separater Bestaetigen-Schritt: der aktuell angezeigte Ordner ist immer
 * der Kandidat fuer opencloud_path. Sortierung und Suche rufen nie `onChange` auf.
 */
export function FolderBrowser({ value, onChange, onErrorChange }: FolderBrowserProps) {
  // Überdauert jeden Ordnerwechsel, weil diese Komponente über alle Werte von `value` gemountet
  // bleibt; gespeichert wird sie nicht.
  const [sort, setSort] = useState<FolderSort>(DEFAULT_FOLDER_SORT)
  const query = useOpenCloudBrowseQuery(value)
  // Loest eager parallel zum Browse-Request desselben Pfads aus - kein Klick noetig, die Liste
  // rendert unveraendert sobald browseFolder zurueck ist, die Zaehler trudeln pro Zeile nach.
  const counts = useOpenCloudFolderCountsQuery(value)

  useEffect(() => {
    onErrorChange?.(query.isError)
  }, [query.isError, onErrorChange])

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
      <nav aria-label="Ordnerpfad" className="flex flex-wrap items-center gap-1 text-sm text-text">
        {breadcrumbsFor(value).map((crumb, index, all) => (
          <span key={crumb.path} className="flex items-center gap-1">
            <Button type="button" variant="ghost" size="sm" onClick={() => onChange(crumb.path)}>
              {crumb.label}
            </Button>
            {index < all.length - 1 && <span aria-hidden="true">/</span>}
          </span>
        ))}
      </nav>

      <FolderLevel
        key={value}
        browse={query}
        counts={counts}
        sort={sort}
        onSortChange={setSort}
        onChange={onChange}
      />
    </div>
  )
}
