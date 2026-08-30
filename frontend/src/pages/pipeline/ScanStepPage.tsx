import { useOutletContext } from 'react-router'

import { ApiError } from '../../api/client'
import { Alert } from '../../components/ui/alert'
import { Button } from '../../components/ui/button'
import { Progress } from '../../components/ui/progress'
import { StatusDot } from '../../components/StatusDot'
import { useTriggerScanMutation } from '../../hooks/useProjects'
import { useTriggerConfirmation } from '../../hooks/useTriggerConfirmation'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

/**
 * 1:1-Migration der bisherigen Scan-Section aus ProjectDetailPage.tsx (Akzeptanzkriterium 7 der
 * Spec 0042) - fachliche Logik/Zustaende/Texte unveraendert, ergaenzt um die kurze Erklaerzeile aus
 * dem UI/UX-Abschnitt ("bekommen die drei bisher unkommentierten Schritte dieselbe kurze
 * Erklaerzeile wie die beiden bereits beschrifteten Schritte").
 */
export function ScanStepPage() {
  const { project, refetchProject } = useOutletContext<PipelineOutletContext>()
  const scanMutation = useTriggerScanMutation(project.id)

  const scanStatus = project.last_scan?.status ?? null
  const scanStartedAt = project.last_scan?.started_at ?? null
  const [awaitingConfirmation, setAwaitingConfirmation] = useTriggerConfirmation(
    scanStatus,
    scanStartedAt,
    refetchProject
  )

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

  const scanTotalFiles = project.last_scan?.total_files ?? null
  const scanFilesFound = project.last_scan?.files_found ?? 0
  const isScanEnumerating = project.last_scan?.status === 'running' && scanTotalFiles === null
  const isScanProcessing = project.last_scan?.status === 'running' && scanTotalFiles !== null
  const scanPercent =
    scanTotalFiles !== null && scanTotalFiles > 0
      ? Math.floor((scanFilesFound / scanTotalFiles) * 100)
      : 0
  const scanAnnouncedDecile = Math.floor(scanPercent / 10) * 10

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 className="text-lg">Scan</h2>
      <p className="text-sm text-text">
        Durchsucht den verknüpften OpenCloud-Ordner nach neuen, geänderten oder entfernten Fotos.
      </p>

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

      {isScanEnumerating && (
        <div className="flex w-full max-w-sm flex-col gap-1.5">
          <p className="text-sm text-text">Dateien werden gezählt…</p>
          <Progress />
        </div>
      )}

      {isScanProcessing && (
        <div className="flex w-full max-w-sm flex-col gap-1.5">
          <p className="text-sm text-text">
            {scanFilesFound} von {scanTotalFiles} Dateien verarbeitet
          </p>
          {scanTotalFiles !== null && scanTotalFiles > 0 ? (
            <Progress value={scanFilesFound} max={scanTotalFiles}>
              {scanFilesFound}/{scanTotalFiles}
            </Progress>
          ) : (
            <Progress />
          )}
          <p aria-live="polite" className="text-sm text-text">
            {scanAnnouncedDecile}% verarbeitet
          </p>
        </div>
      )}

      {project.last_scan?.status === 'success' && (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-text sm:grid-cols-3">
          <div className="flex gap-1">
            <dt className="text-text">Hinzugefügt</dt>
            <dd className="text-text-h">{project.last_scan.photos_added}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-text">Aktualisiert</dt>
            <dd className="text-text-h">{project.last_scan.photos_updated}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-text">
              <details>
                <summary className="cursor-pointer underline decoration-dotted decoration-text/60">
                  Entfernt
                </summary>
                <p className="mt-1 text-xs text-text">
                  Datei wurde am Ursprungsort in OpenCloud nicht mehr gefunden und daher aus
                  PhotoSort entfernt.
                </p>
              </details>
            </dt>
            <dd className="text-text-h">{project.last_scan.photos_removed}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-text">
              <details>
                <summary className="cursor-pointer underline decoration-dotted decoration-text/60">
                  Übersprungen
                </summary>
                <p className="mt-1 text-xs text-text">
                  Dateiendung wird nicht unterstützt (unterstützt: JPG, PNG, HEIC, HEIF).
                </p>
              </details>
            </dt>
            <dd className="text-text-h">{project.last_scan.files_skipped}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-text">Dateien gefunden</dt>
            <dd className="text-text-h">{project.last_scan.files_found}</dd>
          </div>
        </dl>
      )}

      {project.last_scan?.status === 'failed' && <Alert>{project.last_scan.error_message}</Alert>}
    </section>
  )
}
