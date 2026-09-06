import { useEffect } from 'react'

import { ApiError } from '../api/client'
import type { FolderCountOut } from '../api/types'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { useOpenCloudBrowseQuery } from '../hooks/useOpenCloudBrowse'
import { useOpenCloudFolderCountsQuery } from '../hooks/useOpenCloudFolderCounts'

interface Breadcrumb {
  label: string
  path: string
}

interface FolderBrowserProps {
  value: string
  onChange: (path: string) => void
  // Ueber die Spec-Prosa ("kontrollierte Komponente: value/onChange") hinausgehend, aber vom
  // Akzeptanzkriterium "Backend-Fehler beim Browse: Submit bleibt deaktiviert" verlangt
  // (specs/features/0005-minimal-project-frontend.md) - der Elternseite bleibt sonst keine
  // Moeglichkeit, den internen Ladefehler dieser Komponente zu kennen.
  onErrorChange?: (hasError: boolean) => void
}

// specs/features/0050-dateianzahl-im-ordner-browser.md, UI/UX-Abschnitt "Eager-Zaehler neben
// Listeneintraegen": vier moegliche Anzeigezustaende pro gelistetem Unterordner.
type FolderCountDisplay =
  | { kind: 'loading' }
  | { kind: 'count'; count: number }
  | { kind: 'at_limit' }
  | { kind: 'error' }

function folderCountDisplayFor(
  path: string,
  counts: { isLoading: boolean; isError: boolean; data: FolderCountOut[] | undefined }
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

/**
 * Kontrollierte Ordner-Navigation per Pfad-Drilldown (decisions/0004-frontend-app-shell.md,
 * specs/features/0005-minimal-project-frontend.md). Laedt pro Aufruf nur die direkten
 * Unterordner von `value` - "Navigation" entsteht rein client-seitig, React Query cached jede
 * Ebene unter ihrem eigenen Query-Key, kein separater Bestaetigen-Schritt: der aktuell
 * angezeigte Ordner ist immer der Kandidat fuer opencloud_path.
 */
export function FolderBrowser({ value, onChange, onErrorChange }: FolderBrowserProps) {
  const query = useOpenCloudBrowseQuery(value)
  // Loest eager parallel zum Browse-Request desselben Pfads aus (specs/features/0050-
  // dateianzahl-im-ordner-browser.md) - kein Klick noetig, die Liste rendert unveraendert sobald
  // browseFolder zurueck ist, die Zaehler trudeln pro Zeile nach.
  const counts = useOpenCloudFolderCountsQuery(value)

  useEffect(() => {
    onErrorChange?.(query.isError)
  }, [query.isError, onErrorChange])

  const errorDetail =
    query.isError && query.error instanceof ApiError
      ? query.error.detail
      : query.isError
        ? 'Unerwarteter Fehler beim Laden der Ordner.'
        : null

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

      {query.isLoading && <p role="status" className="text-sm text-text">Ordner werden geladen…</p>}
      {errorDetail && <Alert>{errorDetail}</Alert>}
      {query.isSuccess && query.data.length === 0 && (
        <p className="text-sm text-text">Keine Unterordner</p>
      )}
      {query.isSuccess && query.data.length > 0 && (
        <ul className="flex flex-col gap-1">
          {query.data.map((entry) => (
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
