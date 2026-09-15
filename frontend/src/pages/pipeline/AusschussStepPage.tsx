import { Link, useOutletContext } from 'react-router'

import { ApiError } from '../../api/client'
import { Alert } from '../../components/ui/alert'
import { Button } from '../../components/ui/button'
import { Progress } from '../../components/ui/progress'
import { StatusDot } from '../../components/StatusDot'
import { useDuplicateGroupIndexQuery } from '../../hooks/useDuplicates'
import { useTriggerScoreMutation } from '../../hooks/useProjects'
import { useTriggerConfirmation } from '../../hooks/useTriggerConfirmation'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

/**
 * 1:1-Migration der bisherigen "Ausschuss aussortieren"-Section aus ProjectDetailPage.tsx
 * (Akzeptanzkriterium 7) - inkl. der bewusst UNGEGATETEN Erreichbarkeit (Akzeptanzkriterium 3: der
 * Trigger-Button war nie an `last_scan.status` gekoppelt, kein neues Gate hier eingefuehrt).
 */
export function AusschussStepPage() {
  const { project, refetchProject } = useOutletContext<PipelineOutletContext>()
  const scoreMutation = useTriggerScoreMutation(project.id)

  const scoringRun = project.last_scoring_run ?? null
  const scoringStatus = scoringRun?.status ?? null
  const scoringStartedAt = scoringRun?.started_at ?? null
  const [awaitingScoreConfirmation, setAwaitingScoreConfirmation] = useTriggerConfirmation(
    scoringStatus,
    scoringStartedAt,
    refetchProject,
  )

  // Nur nach einem erfolgreichen Lauf: Ohne ihn gibt es keine Vorschläge und damit keine Gruppen,
  // und jeder Aufruf dieses Schritts setzte eine Anfrage ab, die nichts beantworten kann.
  const duplicateGroupIndex = useDuplicateGroupIndexQuery(project.id, {
    enabled: scoringStatus === 'success',
  })

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
  const scoringAnnouncedDecile = Math.floor(scoringPercent / 10) * 10

  const suggestionsFound = scoringRun?.suggestions_found ?? 0
  const suggestionsFoundText =
    suggestionsFound === 1 ? '1 Vorschlag gefunden' : `${suggestionsFound} Vorschläge gefunden`

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 className="text-lg">Ausschuss-Erkennung</h2>
      <p className="text-sm text-text">
        Erkennt automatisch unscharfe, überbelichtete oder doppelte Fotos als Ausschuss-Vorschläge —
        läuft vollständig lokal auf diesem Server.
      </p>

      <Button type="button" onClick={handleTriggerScore} disabled={isScoreBusy} busy={isScoreBusy}>
        {isScoreBusy ? 'Wird aussortiert…' : 'Ausschuss aussortieren'}
      </Button>

      {scoreTriggerErrorDetail && <Alert>{scoreTriggerErrorDetail}</Alert>}

      <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
        <StatusDot status={scoringStatus} />
        {scoringRun === null && 'Noch nicht vorgeschlagen'}
        {scoringStatus === 'running' && 'Wird verarbeitet…'}
        {scoringStatus === 'success' && suggestionsFoundText}
        {scoringStatus === 'failed' && 'Fehlgeschlagen'}
      </p>

      {/* ZWEI GLEICHRANGIGE WEGE, nebeneinander und in derselben Button-Variante: Der eine
          sichtet Einzelvorschläge, der andere geht die Duplikat-Serien der Reihe nach durch. Der
          zweite erscheint nur, wenn es überhaupt eine Gruppe gibt — und bis die Auskunft da ist
          gar nicht, damit er nicht kurz aufblitzt und wieder verschwindet.

          Der zugängliche Name beginnt mit der sichtbaren Beschriftung (WCAG 2.5.3) und trägt den
          Zusatz nach einem GEDANKENSTRICH, nie nach einem Doppelpunkt: Der kachelgenaue Einstieg
          heißt `Duplikate vergleichen: <Dateiname>`, und der Prüfstack wählt ihn über genau dieses
          Präfixmuster. Ein zweiter Treffer führte ihn in die falsche Ansicht. */}
      {scoringStatus === 'success' && (
        <div className="flex flex-wrap gap-3">
          <Button asChild variant="secondary" size="sm">
            <Link
              to={`/projects/${project.id}/photos?filter=suggested`}
              aria-label="Vorschläge aus der Ausschuss-Aussortierung ansehen"
            >
              Vorschläge ansehen
            </Link>
          </Button>
          {duplicateGroupIndex.isSuccess && duplicateGroupIndex.data.first_photo_id !== null && (
            <Button asChild variant="secondary" size="sm">
              <Link
                to={`/projects/${project.id}/photos/${duplicateGroupIndex.data.first_photo_id}/duplicates`}
                aria-label="Duplikate vergleichen — alle Gruppen der Reihe nach durchgehen"
              >
                Duplikate vergleichen
              </Link>
            </Button>
          )}
        </div>
      )}

      {scoringStatus === 'running' && (
        <div className="flex w-full max-w-sm flex-col gap-2">
          <p className="text-sm text-text">
            {photosProcessed} von {photosTotal} Fotos verarbeitet
          </p>
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

      {scoringStatus === 'failed' && (
        <Alert onRetry={handleTriggerScore}>{scoringRun?.error_message}</Alert>
      )}
    </section>
  )
}
