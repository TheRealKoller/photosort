import { useOutletContext } from 'react-router'

import { ApiError } from '../../api/client'
import { RerunBlock } from '../../components/RerunBlock'
import { StatusDot } from '../../components/StatusDot'
import { StepActionBar } from '../../components/StepActionBar'
import { Alert } from '../../components/ui/alert'
import { Progress } from '../../components/ui/progress'
import { useTriggerScanMutation } from '../../hooks/useProjects'
import { useTriggerConfirmation } from '../../hooks/useTriggerConfirmation'
import { deriveStepAction } from '../../utils/stepActions'
import type { PipelineOutletContext } from './ProjectPipelineLayout'

/**
 * Der Scan-Schritt: Erklärzeile und „Erneut einlesen" im Kopf, die Bilanz im Inhalt, Statuszeile,
 * Fortschritt und Hauptaktion in der haftenden Leiste am Ende.
 */
export function ScanStepPage() {
  const { project, refetchProject } = useOutletContext<PipelineOutletContext>()
  const scanMutation = useTriggerScanMutation(project.id)

  const scanStatus = project.last_scan?.status ?? null
  const scanStartedAt = project.last_scan?.started_at ?? null
  const [awaitingConfirmation, setAwaitingConfirmation] = useTriggerConfirmation(
    scanStatus,
    scanStartedAt,
    refetchProject,
  )

  const isTriggerPending = scanMutation.isPending || awaitingConfirmation
  const isBusy = isTriggerPending || scanStatus === 'running'
  const { action, rerun } = deriveStepAction('scan', project, {
    openCount: null,
    isTriggerPending,
  })

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
  const isScanEnumerating = scanStatus === 'running' && scanTotalFiles === null
  const isScanProcessing = scanStatus === 'running' && scanTotalFiles !== null
  const scanPercent =
    scanTotalFiles !== null && scanTotalFiles > 0
      ? Math.floor((scanFilesFound / scanTotalFiles) * 100)
      : 0
  const scanAnnouncedDecile = Math.floor(scanPercent / 10) * 10

  let statusText: string
  switch (action.kind) {
    case 'start':
      statusText = 'Noch nicht gescannt'
      break
    case 'running':
      statusText = isScanProcessing
        ? `Scan läuft… ${scanAnnouncedDecile}% verarbeitet`
        : 'Scan läuft…'
      break
    case 'retry':
      statusText = 'Scan fehlgeschlagen'
      break
    default:
      statusText = 'Erfolgreich'
  }

  return (
    <section className="flex flex-col items-start gap-3">
      <h2 className="text-lg">Scan</h2>
      <p className="text-sm text-text">
        Durchsucht den verknüpften OpenCloud-Ordner nach neuen, geänderten oder entfernten Fotos.
      </p>
      {rerun !== null && (
        <RerunBlock
          rerun={rerun}
          onRerun={handleTriggerScan}
          disabled={isBusy}
          busy={isTriggerPending}
        />
      )}

      {triggerErrorDetail && <Alert>{triggerErrorDetail}</Alert>}

      {project.last_scan?.status === 'success' && (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-text sm:grid-cols-3">
          <div className="flex gap-1">
            <dt className="text-text">Hinzugefügt</dt>
            <dd className="font-mono text-text-h">{project.last_scan.photos_added}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-text">Aktualisiert</dt>
            <dd className="font-mono text-text-h">{project.last_scan.photos_updated}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-text">
              <details>
                <summary className="cursor-pointer underline decoration-dotted decoration-text">
                  Entfernt
                </summary>
                <p className="mt-1 text-xs text-text">
                  Datei wurde am Ursprungsort in OpenCloud nicht mehr gefunden und daher aus
                  PhotoSort entfernt.
                </p>
              </details>
            </dt>
            <dd className="font-mono text-text-h">{project.last_scan.photos_removed}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-text">
              <details>
                <summary className="cursor-pointer underline decoration-dotted decoration-text">
                  Übersprungen
                </summary>
                <p className="mt-1 text-xs text-text">
                  Dateiendung wird nicht unterstützt (unterstützt: JPG, PNG, HEIC, HEIF).
                </p>
              </details>
            </dt>
            <dd className="font-mono text-text-h">{project.last_scan.files_skipped}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="text-text">Dateien gefunden</dt>
            <dd className="font-mono text-text-h">{project.last_scan.files_found}</dd>
          </div>
        </dl>
      )}

      {/* Ohne Wiederholung: Die einzige Wiederholung ist die Hauptaktion der Leiste. */}
      {project.last_scan?.status === 'failed' && <Alert>{project.last_scan.error_message}</Alert>}

      <StepActionBar
        action={action}
        status={
          <>
            <StatusDot status={action.kind === 'running' ? 'running' : scanStatus} />
            {statusText}
          </>
        }
        detail={
          (isScanEnumerating || isScanProcessing) && (
            <div className="flex w-full max-w-sm flex-col gap-2">
              <p className="text-sm text-text">
                {isScanEnumerating
                  ? 'Dateien werden gezählt…'
                  : `${scanFilesFound} von ${scanTotalFiles} Dateien verarbeitet`}
              </p>
              {scanTotalFiles !== null && scanTotalFiles > 0 ? (
                <Progress aria-hidden="true" value={scanFilesFound} max={scanTotalFiles} />
              ) : (
                <Progress aria-hidden="true" />
              )}
            </div>
          )
        }
        onAction={handleTriggerScan}
      />
    </section>
  )
}
