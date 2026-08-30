import { Link } from 'react-router'

import { ApiError } from '../api/client'
import { StatusTag } from '../components/StatusTag'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Skeleton } from '../components/ui/skeleton'
import { useProjectsQuery } from '../hooks/useProjects'
import { deriveScanStatus } from '../utils/scanStatus'

const SKELETON_CARD_COUNT = 4

export function ProjectListPage() {
  const query = useProjectsQuery()

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl">Projekte</h1>
          {query.isSuccess && query.data.length > 0 && (
            <p className="text-xs text-text">{query.data.length} Ordner</p>
          )}
        </div>
        <Button asChild>
          <Link to="/projects/new">Neues Projekt anlegen</Link>
        </Button>
      </header>

      {query.isLoading && (
        <ul role="status" aria-label="Projekte werden geladen…" className="flex flex-col gap-3">
          {Array.from({ length: SKELETON_CARD_COUNT }, (_, index) => (
            <li key={index} aria-hidden="true">
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

      {/*
        Leerzustand nach der Vorlage (Artboard 2): grosse weiche Kreisflaeche mit Symbol statt
        eines blossen Satzes, dazu die Zusicherung, dass nur gelesen wird - das ist die Frage, die
        sich beim ersten Verbinden eines Fotoordners tatsaechlich stellt.
      */}
      {query.isSuccess && query.data.length === 0 && (
        <div className="flex flex-col items-center px-6 py-10 text-center">
          <div className="relative mb-6 grid size-32 place-items-center rounded-full bg-accent-2-200">
            <span aria-hidden="true" className="absolute -right-1.5 top-0.5 size-11 rounded-full bg-accent-200" />
            <svg
              aria-hidden="true"
              width="52"
              height="52"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="relative text-accent-2-700"
            >
              <rect x="3" y="4" width="18" height="16" rx="4" />
              <circle cx="9" cy="10" r="2" />
              <path d="m4 18 5-4 4 3 3-3 4 4" />
            </svg>
          </div>
          <h2 className="mb-2 text-2xl">Noch nichts sortiert</h2>
          <p className="mb-6 max-w-xs text-sm text-text">
            Zeig PhotoSort einen Ordner auf dem Cloud-Speicher — den ersten Durchgang übernimmt es
            für dich.
          </p>
          <Button asChild className="h-[50px] px-6 text-base">
            <Link to="/projects/new">Ordner auswählen</Link>
          </Button>
          <p className="mt-5 text-xs text-text">
            Fotos werden nie kopiert oder verschoben — nur gelesen.
          </p>
        </div>
      )}

      {query.isSuccess && query.data.length > 0 && (
        <ul className="flex flex-col gap-3">
          {query.data.map((project) => {
            const status = deriveScanStatus(project)
            return (
              <li key={project.id}>
                <Card className="bg-neutral-100 p-0 shadow-warm-sm">
                  <Link to={`/projects/${project.id}`} className="flex flex-col gap-2.5 px-4 py-3.5 sm:px-5">
                    <span className="flex min-w-0 flex-col">
                      <span className="font-heading text-lg leading-tight text-text-h">{project.name}</span>
                      {/* Pfad in Festbreitenschrift und einzeilig gekuerzt (Vorlage): ein
                          Cloud-Pfad ist eine technische Kennung, kein Fliesstext. */}
                      <span className="truncate font-mono text-[10.5px] text-text">
                        {project.opencloud_path}
                      </span>
                    </span>
                    <span
                      data-testid={`project-status-${project.id}`}
                      className="flex flex-wrap items-center gap-2"
                    >
                      <StatusTag status={status} />
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
