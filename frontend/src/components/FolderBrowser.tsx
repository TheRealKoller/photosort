import { useEffect } from 'react'

import { ApiError } from '../api/client'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { useOpenCloudBrowseQuery } from '../hooks/useOpenCloudBrowse'

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
    <div className="flex flex-col gap-2 rounded-xl border border-border p-3">
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
            <li key={entry.path}>
              <Button
                type="button"
                variant="ghost"
                className="w-full justify-start"
                onClick={() => onChange(entry.path)}
              >
                {entry.name}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
