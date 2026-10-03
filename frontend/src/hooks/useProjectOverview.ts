import { createContext, useContext } from 'react'

export interface ProjectOverviewControls {
  /** Öffnet die Ablaufübersicht des aktuellen Projekts von Hand. */
  open: () => void
}

/** Bereitgestellt von `ProjectOverviewHost` auf jeder Route mit Projektkontext. */
export const ProjectOverviewContext = createContext<ProjectOverviewControls | null>(null)

/** Wirft ohne Provider: Ein Auslöser, der still nichts täte, fiele erst in der Bedienung auf. */
export function useProjectOverview(): ProjectOverviewControls {
  const controls = useContext(ProjectOverviewContext)
  if (controls === null) {
    throw new Error('useProjectOverview braucht einen ProjectOverviewHost darüber.')
  }
  return controls
}
