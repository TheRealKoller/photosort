import { useOutletContext } from 'react-router'

import { ApiError } from '../../api/client'
import { StatusDot } from '../../components/StatusDot'
import { Alert } from '../../components/ui/alert'
import { Button } from '../../components/ui/button'
import { Progress } from '../../components/ui/progress'
import { useTriggerScoreCriteriaMutation } from '../../hooks/useProjects'
import { useTriggerConfirmation } from '../../hooks/useTriggerConfirmation'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

/**
 * 1:1-Migration der bisherigen Kriterien-Bewertungs-Section aus ProjectDetailPage.tsx
 * (Akzeptanzkriterium 7). Kein Feature-Flag-/Gate-"nicht verfuegbar"-Zweig mehr noetig: der
 * zentrale Redirect-Guard in ProjectPipelineLayout rendert diese Route nur, wenn
 * category_selection_enabled UND ein bestaetigtes Gate vorliegen (isReachable('kriterien')) - die
 * alten Erklaertexte leben als Blockiert-Gruende im Stepper-Popover weiter
 * (utils/pipelineSteps.ts::getBlockedReason).
 */
export function KriterienStepPage() {
  const { project, refetchProject } = useOutletContext<PipelineOutletContext>()
  const scoreCriteriaMutation = useTriggerScoreCriteriaMutation(project.id)

  const scoringRun = project.last_scoring_run
  const criterionScoringRun = project.last_criterion_scoring_run ?? null
  const criterionScoringStatus = criterionScoringRun?.status ?? null
  const criterionScoringStartedAt = criterionScoringRun?.started_at ?? null
  const [awaitingScoreCriteriaConfirmation, setAwaitingScoreCriteriaConfirmation] =
    useTriggerConfirmation(criterionScoringStatus, criterionScoringStartedAt, refetchProject)

  const isCriteriaBusy =
    scoreCriteriaMutation.isPending ||
    awaitingScoreCriteriaConfirmation ||
    criterionScoringStatus === 'running'

  function handleTriggerScoreCriteria(): void {
    if (isCriteriaBusy || scoringRun === null) {
      return
    }
    setAwaitingScoreCriteriaConfirmation(true)
    scoreCriteriaMutation.mutate(scoringRun.id, {
      onError: () => setAwaitingScoreCriteriaConfirmation(false),
    })
  }

  const scoreCriteriaTriggerErrorDetail =
    scoreCriteriaMutation.isError && scoreCriteriaMutation.error instanceof ApiError
      ? scoreCriteriaMutation.error.detail
      : scoreCriteriaMutation.isError
        ? 'Fehler beim Auslösen der Kriterien-Bewertung.'
        : null

  const criteriaPhotosProcessed = criterionScoringRun?.photos_processed ?? 0
  const criteriaPhotosTotal = criterionScoringRun?.photos_total ?? 0
  const criteriaPercent =
    criteriaPhotosTotal > 0
      ? Math.floor((criteriaPhotosProcessed / criteriaPhotosTotal) * 100)
      : 0
  const criteriaAnnouncedDecile = Math.floor(criteriaPercent / 10) * 10

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 className="text-lg font-semibold text-text-h">Kriterien-Bewertung</h2>
      <p className="text-sm text-text">
        Bewertet jedes verbleibende Foto nach mehreren Kriterien (Schärfe, Belichtung,
        Bildinhalt) und bildet daraus eine Rangfolge je Foto-Moment und Kategorie — läuft
        vollständig lokal auf diesem Server.
      </p>

      <Button
        type="button"
        onClick={handleTriggerScoreCriteria}
        disabled={isCriteriaBusy}
        busy={isCriteriaBusy}
      >
        {isCriteriaBusy ? 'Wird bewertet…' : 'Kriterien-Bewertung starten'}
      </Button>

      {scoreCriteriaTriggerErrorDetail && <Alert>{scoreCriteriaTriggerErrorDetail}</Alert>}

      <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
        <StatusDot status={criterionScoringStatus} />
        {criterionScoringRun === null && 'Noch nicht bewertet'}
        {criterionScoringStatus === 'running' && 'Wird verarbeitet…'}
        {criterionScoringStatus === 'success' && 'Erfolgreich bewertet'}
        {criterionScoringStatus === 'failed' && 'Fehlgeschlagen'}
      </p>

      {criterionScoringStatus === 'running' && (
        <div className="flex w-full max-w-sm flex-col gap-1.5">
          <p className="text-sm text-text">
            {criteriaPhotosProcessed} von {criteriaPhotosTotal} Fotos verarbeitet
          </p>
          {criteriaPhotosTotal > 0 ? (
            <Progress value={criteriaPhotosProcessed} max={criteriaPhotosTotal}>
              {criteriaPhotosProcessed}/{criteriaPhotosTotal}
            </Progress>
          ) : (
            <Progress />
          )}
          <p aria-live="polite" className="text-sm text-text">
            {criteriaAnnouncedDecile}% verarbeitet
          </p>
        </div>
      )}

      {criterionScoringStatus === 'failed' && (
        <Alert onRetry={handleTriggerScoreCriteria}>{criterionScoringRun?.error_message}</Alert>
      )}
    </section>
  )
}
