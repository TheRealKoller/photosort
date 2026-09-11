import { Navigate, Outlet, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { ProjectOut } from '../../api/types'
import { Stepper } from '../../components/Stepper'
import { Alert } from '../../components/ui/alert'
import { useProjectQuery } from '../../hooks/useProjects'
import {
  computeStepStates,
  getDefaultStepId,
  getHighestReachableStepId,
  isStepId,
} from '../../utils/pipelineSteps'

// Kontext, den jede der fuenf Detailseiten ueber useOutletContext liest (Akzeptanzkriterium 7) -
// kein eigener useProjectQuery-Aufruf je Detailseite. `refetchProject` ist bewusst als
// ReturnType<typeof useProjectQuery>['refetch'] typisiert statt eines eigenen, redundanten Typs -
// bleibt automatisch synchron mit der tatsaechlichen TanStack-Query-Signatur.
export interface PipelineOutletContext {
  project: ProjectOut
  refetchProject: ReturnType<typeof useProjectQuery>['refetch']
}

/**
 * Uebernimmt die frueher in ProjectDetailPage.tsx liegende Verantwortung: Laden/404/Fehlerzustand,
 * Projekt-Header, Sekundaernavigation, Stepper-Leiste, Redirect-Guards - EINE zentrale Stelle statt
 * fuenffacher Duplikation je Detailseite.
 *
 * "Zurueck zur Projektliste"-Link bewusst NICHT erneut ergaenzt: die Sekundaernavigation dieses
 * Links wurde bereits entfernt, ersetzt durch den Sticky-Header-Wordmark-Link "PhotoSort". Ein
 * erneutes Hinzufuegen waere ein stiller Widerspruch zu dieser weiterhin gueltigen Entscheidung.
 * Kein Test erzwingt die Abwesenheit hier; die Auflage steht deshalb in voller Aussage am Code.
 */
export function ProjectPipelineLayout() {
  const { projectId, step } = useParams()
  const id = Number(projectId)
  const query = useProjectQuery(id)

  if (query.isError && query.error instanceof ApiError && query.error.status === 404) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-text">Projekt nicht gefunden.</p>
      </div>
    )
  }

  if (query.isLoading) {
    return (
      <p role="status" className="text-sm text-text">
        Projekt wird geladen…
      </p>
    )
  }

  if (query.isError || !query.data) {
    return (
      <div className="flex flex-col items-start gap-3">
        <Alert>
          {query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden des Projekts.'}
        </Alert>
      </div>
    )
  }

  const project = query.data
  const states = computeStepStates(project)

  // Redirect-Guard (Akzeptanzkriterien 10-11): bei JEDEM Render neu aus den aktuellen (gepollten)
  // Projektdaten abgeleitet, kein zwischengespeicherter Navigationszustand - ein waehrend des
  // Betrachtens per Poll nicht mehr erreichbarer Schritt wird dadurch automatisch beim naechsten
  // Poll-Tick verlassen, ohne Nutzerinteraktion (AK11).
  if (step === undefined) {
    return <Navigate to={`/projects/${project.id}/pipeline/${getDefaultStepId(states)}`} replace />
  }

  if (!isStepId(step)) {
    return (
      <Navigate
        to={`/projects/${project.id}/pipeline/${getHighestReachableStepId(states)}`}
        replace
      />
    )
  }

  // isStepId(step) hat `step` oben bereits auf StepId verengt (TypeScript narrowing bleibt bis
  // zum Ende der Funktion erhalten) - kein erneuter Cast/keine erneute Suche noetig.
  const currentState = states.find((state) => state.id === step)
  if (!currentState?.isReachable) {
    return (
      <Navigate
        to={`/projects/${project.id}/pipeline/${getHighestReachableStepId(states)}`}
        replace
      />
    )
  }

  const outletContext: PipelineOutletContext = { project, refetchProject: query.refetch }

  return (
    <div className="flex flex-col gap-6">
      {/* Projektkennung wie in Artboard 4: Name in der Display-Schrift, darunter der Cloud-Pfad in
          Festbreitenschrift und einzeilig gekuerzt - der Pfad ist eine technische Kennung, kein
          Fliesstext, und darf die Zeile nicht sprengen. */}
      <header className="min-w-0">
        <h1 className="truncate text-xl sm:text-2xl">{project.name}</h1>
        <p className="truncate font-mono text-xs text-text-muted">{project.opencloud_path}</p>
      </header>

      <Stepper projectId={project.id} project={project} states={states} activeStepId={step} />

      <div id="pipeline-content" className="flex flex-col gap-6">
        <Outlet context={outletContext} />
      </div>

      {/* Hier stand zuletzt noch ein "Statistik"-Button - der letzte Rest der frueheren
          Sekundaernavigation am Seitenende.
          Er ist ersatzlos entfallen, weil die Statistikseite jetzt ein Nebenziel der
          Kopfzeilengruppe ist und damit von JEDER Projektseite aus erreichbar; ein zweiter
          Einstiegspunkt nur hier waere eine Dopplung. Die Seite endet damit mit ihrem
          Schrittinhalt. */}
    </div>
  )
}
