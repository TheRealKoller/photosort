import { useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'

import { ApiError } from '../api/client'
import { useMarkOverviewSeen, useOverviewSeen } from '../hooks/useOverviewSeen'
import { ProjectOverviewContext, type ProjectOverviewControls } from '../hooks/useProjectOverview'
import { useProjectQuery } from '../hooks/useProjects'
import { WorkflowOverviewDialog } from './WorkflowOverviewDialog'

/** Ohne gültige Projekt-Id gibt es keine Übersicht - der Auslöser erscheint dort ohnehin nicht,
 * weil kein Projekt lädt. */
const INERT_CONTROLS: ProjectOverviewControls = { open: () => undefined }

interface ProjectOverviewHostProps {
  /** Der Rohwert aus der Adresszeile (`matchProjectId`), ungeprüft und dekodiert. */
  projectIdParam: string
  children: ReactNode
}

/**
 * Stellt die Ablaufübersicht auf jeder Route mit Projektkontext bereit: Sie erscheint von selbst
 * beim ersten Öffnen eines Projekts, egal über welchen Weg, und lässt sich über
 * `useProjectOverview().open` jederzeit öffnen.
 *
 * SICHERHEIT: Die Projekt-Id aus der Adresszeile geht genau hier und genau einmal als geprüfte
 * Ganzzahl (`Number.isInteger(n) && n >= 1`) weiter. Sonst setzt der Host KEINE Anfrage ab: Ein
 * Rohwert wie `1/../..` (dekodiert aus `%2F`) lenkte den authentifizierten `PUT` auf einen anderen
 * Pfad derselben API.
 */
export function ProjectOverviewHost({ projectIdParam, children }: ProjectOverviewHostProps) {
  const projectId = Number(projectIdParam)
  if (!Number.isInteger(projectId) || projectId < 1) {
    return (
      <ProjectOverviewContext.Provider value={INERT_CONTROLS}>
        {children}
      </ProjectOverviewContext.Provider>
    )
  }
  return <ValidProjectOverviewHost projectId={projectId}>{children}</ValidProjectOverviewHost>
}

/**
 * Wann die Übersicht erscheint:
 *
 * - von selbst nur bei geladenem Projekt UND bekanntem "nicht gesehen" - oder bei einem
 *   Lesefehler, dann lieber einmal zu oft. Solange etwas lädt, bei `404` des Projekts und bei
 *   einer verspäteten Antwort "gesehen" erscheint sie nie, auch nicht kurz.
 * - Schließen (Schaltfläche, Esc) und der Klick auf einen Eintrag merken "gesehen". Schließen
 *   führt über `/pipeline` und dessen Weiterleitung zum nächsten anstehenden Schritt.
 *
 * Gemerkt wird ausschließlich über den einen `PUT`; Öffnen und Schließen ändern nichts am Projekt.
 */
function ValidProjectOverviewHost({
  projectId,
  children,
}: {
  projectId: number
  children: ReactNode
}) {
  const navigate = useNavigate()
  const projectQuery = useProjectQuery(projectId)
  const seenQuery = useOverviewSeen(projectId)
  const markSeen = useMarkOverviewSeen(projectId)
  const [isOpenedByHand, setIsOpenedByHand] = useState(false)

  const controls = useMemo<ProjectOverviewControls>(
    () => ({ open: () => setIsOpenedByHand(true) }),
    [],
  )

  const isUnseen = seenQuery.data?.seen === false || seenQuery.isError
  const project = projectQuery.data
  const isGone = projectQuery.error instanceof ApiError && projectQuery.error.status === 404

  function handleClose(): void {
    setIsOpenedByHand(false)
    markSeen()
    navigate(`/projects/${projectId}/pipeline`)
  }

  function handleOpenEntry(): void {
    setIsOpenedByHand(false)
    markSeen()
  }

  return (
    <ProjectOverviewContext.Provider value={controls}>
      {children}
      {/* Ohne geladenes Projekt kein Dialog. Ein `404` schlaegt dabei den Cache: Ist das Projekt
          inzwischen geloescht, haelt sein zwischengespeicherter Stand den Dialog nicht offen. Ein
          sonstiger, voruebergehender Abruffehler laesst einen offenen Dialog stehen. */}
      {project !== undefined && !isGone && (
        <WorkflowOverviewDialog
          project={project}
          open={isOpenedByHand || isUnseen}
          onClose={handleClose}
          onOpenEntry={handleOpenEntry}
        />
      )}
    </ProjectOverviewContext.Provider>
  )
}
