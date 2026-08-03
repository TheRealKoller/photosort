import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../api/client'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Progress } from '../components/ui/progress'
import {
  POLL_INTERVAL_MS,
  useProjectQuery,
  useTriggerScanMutation,
  useTriggerScoreMutation,
} from '../hooks/useProjects'
import { PROCESS_STATUS_DOT_CLASSES } from '../utils/processStatus'
import type { ProcessStatus } from '../utils/processStatus'

/**
 * UX-/Architect-Review-Fund (Branch feature/0012-visual-redesign-views): faerbte urspruenglich den
 * sichtbaren Statustext direkt ein (`text-status-*`) - `--status-success`/`--status-failed` sind
 * aber nur als Flaechenfarbe kalibriert, nicht als Text-/Symbolfarbe (WCAG-AA gegen `--bg`
 * verfehlt, siehe architecture/0004-design-system.md, Abschnitt Farbpalette). Gleiches Muster wie
 * ProjectListPage jetzt auch hier: nur ein dekorativer, `aria-hidden` Punkt traegt die Farbe, der
 * Text daneben bleibt neutral (`text-text`/`text-text-h`).
 */
function StatusDot({ status }: { status: ProcessStatus | null | undefined }) {
  return (
    <span
      aria-hidden="true"
      className={`size-2.5 shrink-0 rounded-full ${status ? PROCESS_STATUS_DOT_CLASSES[status] : 'bg-border'}`}
    />
  )
}

export function ProjectDetailPage() {
  const { projectId } = useParams()
  const id = Number(projectId)

  const query = useProjectQuery(id)
  const scanMutation = useTriggerScanMutation(id)
  const scoreMutation = useTriggerScoreMutation(id)

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

  // Analoge Ueberbrueckung wie oben fuer den Scan-Trigger, hier fuer den Scoring-Trigger
  // (specs/features/0003-automatic-best-photo-selection.md) - derselbe Grund: score_project
  // setzt status="running" erst asynchron im Worker, nicht synchron mit der 202-Antwort.
  const [awaitingScoreConfirmation, setAwaitingScoreConfirmation] = useState(false)
  const scoringRun = query.data?.last_scoring_run ?? null
  const scoringStatus = scoringRun?.status ?? null

  useEffect(() => {
    if (!awaitingScoreConfirmation) {
      return
    }
    if (scoringStatus === 'running') {
      setAwaitingScoreConfirmation(false)
      return
    }
    const interval = setInterval(() => {
      void refetchRef.current()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [awaitingScoreConfirmation, scoringStatus])

  if (query.isError && query.error instanceof ApiError && query.error.status === 404) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-text">Projekt nicht gefunden.</p>
        <Button asChild variant="ghost">
          <Link to="/">Zurück zur Projektliste</Link>
        </Button>
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
        <Button asChild variant="ghost">
          <Link to="/">Zurück zur Projektliste</Link>
        </Button>
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

  const isScoreBusy =
    scoreMutation.isPending || awaitingScoreConfirmation || scoringStatus === 'running'

  function handleTriggerScore(): void {
    if (isScoreBusy) {
      return
    }
    setAwaitingScoreConfirmation(true)
    scoreMutation.mutate(undefined, {
      onError: () => setAwaitingScoreConfirmation(false),
    })
  }

  const scoreTriggerErrorDetail =
    scoreMutation.isError && scoreMutation.error instanceof ApiError
      ? scoreMutation.error.detail
      : scoreMutation.isError
        ? 'Fehler beim Auslösen der automatischen Vorauswahl.'
        : null

  const photosProcessed = scoringRun?.photos_processed ?? 0
  const photosTotal = scoringRun?.photos_total ?? 0
  const scoringPercent = photosTotal > 0 ? Math.floor((photosProcessed / photosTotal) * 100) : 0
  // Gedrosselte aria-live-Regel fuer hochfrequente Zaehler (UI/UX-Abschnitt der Spec): der
  // Screenreader bekommt nur bei vollen 10%-Schritten eine neue Ansage, nicht bei jedem
  // Poll-Tick - die exakte "X von Y"-Zeile darunter aktualisiert sich weiterhin bei jedem Poll,
  // ist aber bewusst NICHT Teil der aria-live-Region.
  const scoringAnnouncedDecile = Math.floor(scoringPercent / 10) * 10

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold text-text-h">{project.name}</h1>
        <p className="text-sm text-text">{project.opencloud_path}</p>
      </header>

      <section className="flex flex-col items-start gap-3">
        <Button type="button" onClick={handleTriggerScan} disabled={isBusy} busy={isBusy}>
          {isBusy ? 'Scan läuft…' : 'Aktualisieren'}
        </Button>

        {triggerErrorDetail && <Alert>{triggerErrorDetail}</Alert>}

        <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
          <StatusDot status={project.last_scan?.status} />
          {project.last_scan === null && 'Noch nicht gescannt'}
          {project.last_scan?.status === 'running' && 'Scan läuft…'}
          {project.last_scan?.status === 'success' && 'Erfolgreich'}
          {project.last_scan?.status === 'failed' && 'Fehlgeschlagen'}
        </p>

        {project.last_scan?.status === 'success' && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-text sm:grid-cols-3">
            <dt className="text-text">Hinzugefügt</dt>
            <dd className="text-text-h">{project.last_scan.photos_added}</dd>
            <dt className="text-text">Aktualisiert</dt>
            <dd className="text-text-h">{project.last_scan.photos_updated}</dd>
            <dt className="text-text">Entfernt</dt>
            <dd className="text-text-h">{project.last_scan.photos_removed}</dd>
            <dt className="text-text">Übersprungen</dt>
            <dd className="text-text-h">{project.last_scan.files_skipped}</dd>
            <dt className="text-text">Dateien gefunden</dt>
            <dd className="text-text-h">{project.last_scan.files_found}</dd>
          </dl>
        )}

        {project.last_scan?.status === 'failed' && (
          <Alert>{project.last_scan.error_message}</Alert>
        )}
      </section>

      <section className="flex flex-col items-start gap-3">
        <Button type="button" onClick={handleTriggerScore} disabled={isScoreBusy} busy={isScoreBusy}>
          {isScoreBusy ? 'Wird vorgeschlagen…' : 'Beste Fotos automatisch vorschlagen'}
        </Button>

        {scoreTriggerErrorDetail && <Alert>{scoreTriggerErrorDetail}</Alert>}

        {/* aria-live="polite" mit bewusst STABILEM Text waehrend "running" (UI/UX-Review-Fund):
            vorher stand der sich bei jedem Poll aendernde "X von Y"-Zaehler direkt in dieser
            aria-live-Zeile - das haette die 10%-Drosselung unten wirkungslos gemacht, da diese
            Zeile trotzdem bei jedem Tick neu angesagt worden waere. Aendert sich hier nur beim
            Uebergang zwischen Zustaenden (null -> running -> success/failed), nicht bei jedem Poll -
            dadurch wird ein abgeschlossener oder fehlgeschlagener Lauf zuverlaessig angesagt, ohne
            waehrend des Laufs selbst zu spammen. Der exakte Zaehler lebt separat unten. */}
        <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
          <StatusDot status={scoringStatus} />
          {scoringRun === null && 'Noch nicht vorgeschlagen'}
          {scoringStatus === 'running' && 'Wird verarbeitet…'}
          {scoringStatus === 'success' && 'Vorschläge aktualisiert'}
          {scoringStatus === 'failed' && 'Fehlgeschlagen'}
        </p>

        {scoringStatus === 'running' && (
          <div className="flex w-full max-w-sm flex-col gap-1.5">
            <p className="text-sm text-text">
              {photosProcessed} von {photosTotal} Fotos verarbeitet
            </p>
            {/* Copilot-Review-Fund (PR #6): direkt nach dem Trigger ist der Status bereits
                "running", aber photos_total kann noch kurz 0 sein (wird im Worker erst NACH dem
                Anlegen des ScoringRun gesetzt) - <progress max={0}> ist fuer native
                progress-Elemente ungueltig/mehrdeutig. Solange photosTotal 0 ist, daher bewusst ein
                indeterminiertes <progress/> ohne value/max statt eines irrefuehrenden 0/0-Balkens. */}
            {photosTotal > 0 ? (
              <Progress value={photosProcessed} max={photosTotal}>
                {photosProcessed}/{photosTotal}
              </Progress>
            ) : (
              <Progress />
            )}
            <p aria-live="polite" className="text-sm text-text">
              {scoringAnnouncedDecile}% verarbeitet
            </p>
          </div>
        )}

        {scoringStatus === 'failed' && !isScoreBusy && (
          <Alert onRetry={handleTriggerScore}>{scoringRun?.error_message}</Alert>
        )}
      </section>

      <nav aria-label="Fotos" className="flex flex-wrap gap-3">
        <Button asChild variant="secondary">
          <Link to={`/projects/${project.id}/photos`}>Fotos ansehen</Link>
        </Button>
        <Button asChild variant="secondary">
          <Link to={`/projects/${project.id}/compare`}>Bewertungen vergleichen</Link>
        </Button>
      </nav>

      <Button asChild variant="ghost" className="self-start">
        <Link to="/">Zurück zur Projektliste</Link>
      </Button>
    </div>
  )
}
