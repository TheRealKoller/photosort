import type { ComponentType } from 'react'
import { useParams } from 'react-router'

import type { StepId } from '../../utils/pipelineSteps'
import { AusschussStepPage } from './AusschussStepPage'
import { GateStepPage } from './GateStepPage'
import { KriterienStepPage } from './KriterienStepPage'
import { KuratierungStepPage } from './KuratierungStepPage'
import { ScanStepPage } from './ScanStepPage'

// Feste Zuordnung Schritt -> Detailseiten-Komponente (Architektur-Abschnitt der Spec 0042).
// Bewusst HIER co-lokalisiert statt in utils/pipelineSteps.ts, obwohl der Architektur-Abschnitt
// der Spec wörtlich "utils/pipelineSteps.ts" nennt: diese Datei ist dort selbst explizit als
// reine, seiteneffekt-/fetch-freie Logik-Datei dokumentiert (analog utils/timeOfDay.ts) - eine
// Komponenten-/JSX-Zuordnung dort würde diese Eigenschaft aufweichen und pipelineSteps.test.ts
// unnötig an React koppeln. Technische Detailentscheidung innerhalb der akzeptierten Spec.
const STEP_COMPONENTS: Record<StepId, ComponentType> = {
  scan: ScanStepPage,
  ausschuss: AusschussStepPage,
  gate: GateStepPage,
  kriterien: KriterienStepPage,
  kuratierung: KuratierungStepPage,
}

/**
 * Dünne Zuordnungskomponente (Architektur-Abschnitt "Routing"): liest `:step` aus der URL, rendert
 * die zugehörige Detailseite. Der eigentliche Erreichbarkeits-/Redirect-Guard sitzt bereits
 * zentral in ProjectPipelineLayout - an dieser Stelle ist `:step` immer ein bekannter, aktuell
 * erreichbarer StepId-Wert (sonst hätte der Guard schon umgeleitet, bevor dieser Outlet
 * überhaupt gerendert wird).
 */
export function PipelineStepView() {
  const { step } = useParams<{ step: StepId }>()
  const StepComponent = step ? STEP_COMPONENTS[step] : undefined

  if (!StepComponent) {
    // Defensiver Fallback, durch den Guard in ProjectPipelineLayout praktisch unerreichbar - kein
    // bekannter Testfall, keine eigene Wiring-Testfall-Pflicht (analog zur bestehenden Praxis bei
    // anderen rein defensiven Fallbacks im Projekt).
    return null
  }

  return <StepComponent />
}
