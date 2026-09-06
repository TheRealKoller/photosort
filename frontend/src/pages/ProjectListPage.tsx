import { Link } from 'react-router'

import { ApiError } from '../api/client'
import { StatusTag } from '../components/StatusTag'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Card } from '../components/ui/card'
import { Icon } from '../components/ui/icon'
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
          <h1 className="text-xl sm:text-2xl">Projekte</h1>
          {query.isSuccess && query.data.length > 0 && (
            <p className="text-xs text-text-muted">{query.data.length} Ordner</p>
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
              <Skeleton className="h-20 w-full rounded-lg" />
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
        Leerzustand: Symbol aus dem Zwoelfer-Satz des Boards auf einer erhoehten Flaeche, dazu die
        Zusicherung, dass nur gelesen wird - das ist die Frage, die sich beim ersten Verbinden
        eines Fotoordners tatsaechlich stellt. Der erklaerende Text steht bewusst in `--text` und
        NICHT in `--text-muted`: ein Leerzustand ist die Hauptaussage der Seite, keine
        Metadatenzeile (specs/features/0320-dark-utility-register.md, UI/UX-Abschnitt).
      */}
      {query.isSuccess && query.data.length === 0 && (
        // Ein einziger `flex-col gap-4` statt einer Kette einzelner `mb-*`/`mt-*` - der Abstand
        // steht damit an EINER Stelle und kann nicht mehr zwischen den Kindern auseinanderlaufen.
        // Die Schaltflaeche traegt das Board-Standardmass: der Leerzustand ist kein heisser Pfad.
        <div className="flex flex-col items-center gap-4 px-4 py-8 text-center">
          <span
            aria-hidden="true"
            className="grid size-16 place-items-center rounded-md bg-elevated text-accent"
          >
            <Icon name="image" size={40} />
          </span>
          <h2 className="text-lg">Noch nichts sortiert</h2>
          <p className="max-w-xs text-sm text-text">
            Zeig PhotoSort einen Ordner auf dem Cloud-Speicher — den ersten Durchgang übernimmt es
            für dich.
          </p>
          <Button asChild>
            <Link to="/projects/new">Ordner auswählen</Link>
          </Button>
          <p className="text-xs text-text-muted">
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
                <Card className="p-0">
                  {/* Die ganze Zeile ist EINE Trefferflaeche - `min-h-11` als Zeilenhoehe
                      einer zeilenweisen Liste (Trefferflaechen-Regel 3), nicht als
                      Schaltflaechenmass. */}
                  <Link
                    to={`/projects/${project.id}`}
                    className="flex min-h-11 flex-col justify-center gap-2 px-4 py-3"
                  >
                    <span className="flex min-w-0 flex-col">
                      <span className="text-lg font-semibold leading-tight text-text-h">{project.name}</span>
                      {/* Pfad in Festbreitenschrift und einzeilig gekuerzt (Vorlage): ein
                          Cloud-Pfad ist eine technische Kennung, kein Fliesstext. */}
                      <span className="truncate font-mono text-xs text-text">
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
