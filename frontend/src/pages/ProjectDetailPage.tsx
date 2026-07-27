import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import { POLL_INTERVAL_MS, useProjectQuery, useTriggerScanMutation } from '../hooks/useProjects'

export function ProjectDetailPage() {
  const { projectId } = useParams()
  const id = Number(projectId)

  const query = useProjectQuery(id)
  const scanMutation = useTriggerScanMutation(id)

  // Ueberbrueckt das Zeitfenster zwischen erfolgreichem Trigger (202) und dem ersten Poll, der
  // den neuen Scan tatsaechlich als "running" bestaetigt (siehe
  // specs/features/0005-minimal-project-frontend.md: Button bleibt deaktiviert, "bis entweder
  // Polling running bestaetigt oder der Trigger selbst fehlschlaegt"). Nur auf status==="running"
  // zu warten reicht NICHT: bei einem bereits zuvor gescannten Projekt ist last_scan schon vor
  // dem Klick nicht-null (z.B. "failed" vom letzten Lauf) - der Worker setzt status="running"
  // erst asynchron (backend/src/photosort/worker.py), der Invalidierungs-Refetch direkt nach der
  // 202-Antwort kann also noch den ALTEN, nicht-running Status liefern. Deshalb wird hier aktiv
  // weiterpolliert (statt sich auf das eingebaute, nur bei bereits bestaetigtem "running"
  // aktive refetchInterval von useProjectQuery zu verlassen), bis "running" tatsaechlich
  // beobachtet wird oder der Trigger selbst fehlschlaegt.
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false)
  const scanStatus = query.data?.last_scan?.status ?? null

  // Ref statt Abhaengigkeit auf `query` selbst: `query` ist ein bei jedem Render neues Objekt,
  // eine Abhaengigkeit darauf wuerde das Intervall bei jedem Render neu aufsetzen.
  const refetchRef = useRef(query.refetch)
  refetchRef.current = query.refetch

  useEffect(() => {
    if (!awaitingConfirmation) {
      return
    }
    if (scanStatus === 'running') {
      setAwaitingConfirmation(false)
      return
    }
    const interval = setInterval(() => {
      void refetchRef.current()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [awaitingConfirmation, scanStatus])

  if (query.isError && query.error instanceof ApiError && query.error.status === 404) {
    return (
      <div>
        <p>Projekt nicht gefunden.</p>
        <Link to="/">Zurück zur Projektliste</Link>
      </div>
    )
  }

  if (query.isLoading) {
    return <p role="status">Projekt wird geladen…</p>
  }

  if (query.isError || !query.data) {
    return (
      <div role="alert">
        <p>{query.error instanceof ApiError ? query.error.detail : 'Fehler beim Laden des Projekts.'}</p>
        <Link to="/">Zurück zur Projektliste</Link>
      </div>
    )
  }

  const project = query.data
  const isBusy = scanMutation.isPending || awaitingConfirmation || scanStatus === 'running'

  function handleTriggerScan(): void {
    if (isBusy) {
      return
    }
    setAwaitingConfirmation(true)
    scanMutation.mutate(undefined, {
      onError: () => setAwaitingConfirmation(false),
    })
  }

  const triggerErrorDetail =
    scanMutation.isError && scanMutation.error instanceof ApiError
      ? scanMutation.error.detail
      : scanMutation.isError
        ? 'Fehler beim Auslösen des Scans.'
        : null

  return (
    <div>
      <h1>{project.name}</h1>
      <p>{project.opencloud_path}</p>

      <button type="button" onClick={handleTriggerScan} disabled={isBusy}>
        {isBusy ? 'Scan läuft…' : 'Aktualisieren'}
      </button>

      {triggerErrorDetail && <p role="alert">{triggerErrorDetail}</p>}

      <p aria-live="polite">
        {project.last_scan === null && 'Noch nicht gescannt'}
        {project.last_scan?.status === 'running' && 'Scan läuft…'}
        {project.last_scan?.status === 'success' && 'Erfolgreich'}
        {project.last_scan?.status === 'failed' && 'Fehlgeschlagen'}
      </p>

      {project.last_scan?.status === 'success' && (
        <dl>
          <dt>Hinzugefügt</dt>
          <dd>{project.last_scan.photos_added}</dd>
          <dt>Aktualisiert</dt>
          <dd>{project.last_scan.photos_updated}</dd>
          <dt>Entfernt</dt>
          <dd>{project.last_scan.photos_removed}</dd>
          <dt>Übersprungen</dt>
          <dd>{project.last_scan.files_skipped}</dd>
          <dt>Dateien gefunden</dt>
          <dd>{project.last_scan.files_found}</dd>
        </dl>
      )}

      {project.last_scan?.status === 'failed' && (
        <p role="alert">{project.last_scan.error_message}</p>
      )}

      <nav aria-label="Fotos">
        <Link to={`/projects/${project.id}/photos`}>Fotos ansehen</Link>
        <Link to={`/projects/${project.id}/compare`}>Bewertungen vergleichen</Link>
      </nav>

      <Link to="/">Zurück zur Projektliste</Link>
    </div>
  )
}
