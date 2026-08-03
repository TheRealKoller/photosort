import { Link } from 'react-router'

import { ApiError } from '../api/client'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import { useProjectsQuery } from '../hooks/useProjects'
import { deriveScanStatus } from '../utils/scanStatus'
import type { ScanStatusLabel } from '../utils/scanStatus'

const STATUS_LABELS: Record<ScanStatusLabel, string> = {
  never: 'Noch nicht gescannt',
  running: 'Scan läuft…',
  success: 'Erfolgreich',
  failed: 'Fehlgeschlagen',
}

// Prozess-Status-Farben (specs/architecture/0004-design-system.md) - "running" neutraler Akzent,
// "success"/"failed" teilen sich die Toene mit den Bewertungsfarben album_worthy/rejected. Nur der
// dekorative Punkt traegt die Farbe (aria-hidden), der Text daneben bleibt die primaere,
// screenreader-erreichbare Information (UX-Review-Nice-to-have "Status auf einen Blick").
const STATUS_DOT_CLASSES: Record<ScanStatusLabel, string> = {
  never: 'bg-border',
  running: 'bg-status-running animate-pulse motion-reduce:animate-none',
  success: 'bg-status-success',
  failed: 'bg-status-failed',
}

const SKELETON_CARD_COUNT = 4

export function ProjectListPage() {
  const query = useProjectsQuery()

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-text-h">Projekte</h1>
        <Button asChild>
          <Link to="/projects/new">Neues Projekt anlegen</Link>
        </Button>
      </header>

      {query.isLoading && (
        <ul role="status" aria-label="Projekte werden geladen…" className="flex flex-col gap-3">
          {Array.from({ length: SKELETON_CARD_COUNT }, (_, index) => (
            <li key={index}>
              <Skeleton className="h-20 w-full rounded-xl" />
            </li>
          ))}
        </ul>
      )}

      {query.isError && (
        <Alert onRetry={() => query.refetch()}>
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Projekte.'}
        </Alert>
      )}

      {query.isSuccess && query.data.length === 0 && (
        <div className="flex flex-col items-start gap-3 text-sm text-text">
          <p>Noch keine Projekte vorhanden.</p>
          <Button asChild>
            <Link to="/projects/new">Neues Projekt anlegen</Link>
          </Button>
        </div>
      )}

      {query.isSuccess && query.data.length > 0 && (
        <ul className="flex flex-col gap-3">
          {query.data.map((project) => {
            const status = deriveScanStatus(project)
            return (
              <li key={project.id}>
                <Card className="p-0">
                  <Link
                    to={`/projects/${project.id}`}
                    className="flex flex-wrap items-center justify-between gap-2 px-4 py-4 sm:px-5"
                  >
                    <span className="flex flex-col gap-0.5">
                      <span className="font-medium text-text-h">{project.name}</span>
                      <span className="text-sm text-text">{project.opencloud_path}</span>
                    </span>
                    <span
                      data-testid={`project-status-${project.id}`}
                      className="flex items-center gap-2 text-sm text-text"
                    >
                      <span aria-hidden="true" className={`size-2.5 rounded-full ${STATUS_DOT_CLASSES[status]}`} />
                      {STATUS_LABELS[status]}
                    </span>
                  </Link>
                </Card>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
