import { Link, Navigate, Outlet, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { ProjectOut } from '../../api/types'
import { Stepper } from '../../components/Stepper'
import { Alert } from '../../components/ui/alert'
import { Button } from '../../components/ui/button'
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
 * Uebernimmt die bisherige Verantwortung von ProjectDetailPage.tsx (specs/features/0042-
 * automatisierter-flow-stepper-detailseiten.md, Architektur-Abschnitt "Routing"): Laden/404/
 * Fehlerzustand (1:1 uebernommen), Projekt-Header, Sekundaernavigation, Stepper-Leiste,
 * Redirect-Guards - EINE zentrale Stelle statt fuenffacher Duplikation je Detailseite.
 *
 * "Zurueck zur Projektliste"-Link bewusst NICHT erneut ergaenzt, obwohl der Architektur-Abschnitt
 * der Spec ihn nennt: die Sekundaernavigation dieses Links wurde bereits mit Spec 0033 entfernt
 * (ersetzt durch den Sticky-Header-Wordmark-Link "PhotoSort") - ProjectDetailPage.test.tsx haelt
 * das explizit als Regressionsschutz fest ("no longer renders its own 'Zurueck zur
 * Projektliste'-Link ... now covered by the sticky header/wordmark link"). Ein erneutes Hinzufuegen
 * waere ein stiller Widerspruch zu diesem bereits getroffenen, weiterhin gueltigen
 * Bestandsschutz-Test - technische Detailentscheidung, die den tatsaechlichen (getesteten) Stand
 * ueber die inzwischen leicht veraltete Prosa-Aufzaehlung im Architektur-Abschnitt stellt.
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
    return (
      <Navigate to={`/projects/${project.id}/pipeline/${getDefaultStepId(states)}`} replace />
    )
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
      <header>
        <h1 className="text-2xl font-semibold text-text-h">{project.name}</h1>
        <p className="text-sm text-text">{project.opencloud_path}</p>
      </header>

      <Stepper projectId={project.id} project={project} states={states} activeStepId={step} />

      <div id="pipeline-content" className="flex flex-col gap-6">
        <Outlet context={outletContext} />
      </div>

      <nav aria-label="Fotos" className="flex flex-wrap gap-3">
        <Button asChild variant="secondary">
          <Link to={`/projects/${project.id}/photos`}>Fotos ansehen</Link>
        </Button>
        <Button asChild variant="secondary">
          <Link to={`/projects/${project.id}/compare`}>Bewertungen vergleichen</Link>
        </Button>
      </nav>
    </div>
  )
}
