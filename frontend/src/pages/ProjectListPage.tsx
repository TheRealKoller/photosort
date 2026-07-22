import { Link } from 'react-router'

import { ApiError } from '../api/client'
import { useProjectsQuery } from '../hooks/useProjects'
import { deriveScanStatus } from '../utils/scanStatus'
import type { ScanStatusLabel } from '../utils/scanStatus'

const STATUS_LABELS: Record<ScanStatusLabel, string> = {
  never: 'Noch nicht gescannt',
  running: 'Scan läuft…',
  success: 'Erfolgreich',
  failed: 'Fehlgeschlagen',
}

export function ProjectListPage() {
  const query = useProjectsQuery()

  return (
    <div>
      <header>
        <h1>Projekte</h1>
        <Link to="/projects/new">Neues Projekt anlegen</Link>
      </header>

      {query.isLoading && <p role="status">Projekte werden geladen…</p>}

      {query.isError && (
        <div role="alert">
          <p>{query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden der Projekte.'}</p>
          <button type="button" onClick={() => query.refetch()}>
            Erneut versuchen
          </button>
        </div>
      )}

      {query.isSuccess && query.data.length === 0 && (
        <div>
          <p>Noch keine Projekte vorhanden.</p>
          <Link to="/projects/new">Neues Projekt anlegen</Link>
        </div>
      )}

      {query.isSuccess && query.data.length > 0 && (
        <ul>
          {query.data.map((project) => {
            const status = deriveScanStatus(project)
            return (
              <li key={project.id}>
                <Link to={`/projects/${project.id}`}>
                  <span>{project.name}</span>
                  <span>{project.opencloud_path}</span>
                  <span data-testid={`project-status-${project.id}`}>{STATUS_LABELS[status]}</span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
