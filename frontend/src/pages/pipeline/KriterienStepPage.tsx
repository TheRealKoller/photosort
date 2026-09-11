import { useOutletContext } from 'react-router'

import { ClassificationSection } from '../../components/ClassificationSection'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

/**
 * Der Klassifizierungs-Schritt der Pipeline. Kein Feature-Flag-/Gate-"nicht verfuegbar"-Zweig
 * noetig: der zentrale Redirect-Guard in ProjectPipelineLayout rendert diese Route nur, wenn
 * category_selection_enabled UND ein bestaetigtes Gate vorliegen (isReachable('kriterien')) - die
 * alten Erklaertexte leben als Blockiert-Gruende im Stepper-Popover weiter
 * (utils/pipelineSteps.ts::getBlockedReason).
 *
 * Die Seite traegt genau EINE Sektion: die frueher getrennten Bedienelemente "Kriterien-Bewertung"
 * (hier inline) und "Remote-Kategorisierung" (RemoteCategoryClassificationSection, seither
 * geloescht) sind zu einem Auslöser verschmolzen. Die gesamte Darstellung lebt in
 * ClassificationSection - die Seite bleibt bewusst eine reine Verdrahtung von Outlet-Kontext zu
 * Komponente.
 */
export function KriterienStepPage() {
  const { project, refetchProject } = useOutletContext<PipelineOutletContext>()

  return (
    <div className="flex flex-col gap-8">
      <ClassificationSection project={project} refetchProject={refetchProject} />
    </div>
  )
}
