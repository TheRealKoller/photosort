import { ApiError } from '../api/client'
import { useCancelRequestFocus } from '../hooks/useCancelRequestFocus'
import { useExport } from '../hooks/useExport'
import { useCancelOperation } from '../hooks/useOperations'
import { formatDateTime } from '../utils/formatStats'
import { CANCEL_TEXTS, cancelRequestedText, waitingText } from '../utils/operationTexts'
import { QUEUED_TRIGGER_LABEL } from '../utils/stepActionTexts'
import { OperationCancelButton } from './OperationCancelButton'
import { RerunBlock } from './RerunBlock'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Progress } from './ui/progress'

/** Spec 0641: Der Abbruch VOR dem ersten Foto hat keinen Zielpfad - und nichts zu benennen. */
export const EXPORT_CANCELLED_BEFORE_START_TEXT =
  'Export abgebrochen, bevor ein Foto kopiert wurde.'

/**
 * Der dauerhafte Hinweis nach einem Abbruch: Der angelegte Ordner bleibt - PhotoSort raeumt ihn
 * nicht weg, und die Oberflaeche bietet deshalb kein „Verwerfen" an.
 */
export const EXPORT_FOLDER_STAYS_TEXT =
  'Der Ordner bleibt bestehen — PhotoSort löscht ihn nicht. Bei Bedarf in OpenCloud von Hand entfernen.'

/**
 * Der Auslöser des Exports in der Ergebnissicht der Endauswahl - die drei Antworten der Story an
 * derselben Stelle: Anzahl vorher, Laufzustand währenddessen, Bestätigung danach (Spec 0263,
 * Abschnitt UI/UX).
 *
 * Kein haftender Balken, kein Bestätigungsdialog: Der Export ist nicht destruktiv und jederzeit
 * wiederholbar; die sichtbare Anzahl ist der Schutz. Der Auslöser bleibt im Lauf DEAKTIVIERT, nicht
 * ausgeblendet (Busy-Button-Muster); bei leerer Endauswahl trägt er einen dauerhaft sichtbaren
 * Grund statt zu verschwinden.
 */
export function ExportSection({ projectId }: { projectId: number }) {
  const { preview, trigger, lastRun, runDetail, awaiting, setAwaiting } = useExport(projectId)
  const cancelMutation = useCancelOperation(projectId)

  const photoCount = preview.data?.photo_count ?? 0
  const isEmpty = preview.isSuccess && photoCount === 0
  const runStatus = lastRun?.status ?? null
  const isTriggerPending = trigger.isPending || awaiting
  const isBusy = isTriggerPending || runStatus === 'running' || runStatus === 'queued'
  // Spec 0641: Der Abbruch adressiert GENAU diesen Lauf.
  const isCancelRequested = lastRun?.cancel_requested_at != null
  const isCancelled = runStatus === 'cancelled'
  const statusRef = useCancelRequestFocus<HTMLDivElement>(cancelMutation.data ?? null)
  const failedPhotos = runDetail.data?.failed_photos ?? []

  const triggerError =
    trigger.isError && trigger.error instanceof ApiError ? trigger.error.detail : null

  function handleTrigger(): void {
    // Doppel-Ausloesen gesperrt: waehrend des Laufs/der Trigger-Bestaetigung wird nichts erneut
    // eingereiht - sonst queued ein Doppelklick zwei Jobs.
    if (isBusy) {
      return
    }
    setAwaiting(true)
    trigger.mutate()
  }

  function handleCancel(): void {
    if (lastRun !== null) {
      cancelMutation.mutate({ kind: 'export', runId: lastRun.id })
    }
  }

  return (
    <section className="flex flex-col items-start gap-3">
      <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:gap-3">
        <Button
          type="button"
          variant="default"
          size="sm"
          className="shrink-0"
          disabled={isEmpty || isBusy}
          busy={isBusy && runStatus !== 'queued'}
          onClick={handleTrigger}
        >
          {runStatus === 'queued' ? QUEUED_TRIGGER_LABEL : 'Nach OpenCloud exportieren'}
        </Button>
        <p className="text-sm text-text">
          {isEmpty
            ? 'Die Endauswahl ist leer — es gibt nichts zu exportieren'
            : `${photoCount} Fotos`}
        </p>
      </div>

      {/* Waehrend, wartend und abgebrochen stehen an DERSELBEN Stelle: eine Live-Region, die den
          letzten Stand nennt. Der Abbruch-Knopf sitzt beim Fortschritt seines Vorgangs; bei
          „abgebrochen" gibt es keinen mehr. */}
      {(runStatus === 'running' || runStatus === 'queued' || isCancelled) && lastRun !== null && (
        <div
          ref={statusRef}
          tabIndex={-1}
          aria-live="polite"
          className="flex w-full flex-col gap-2"
        >
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-text">
              {runStatus === 'running' &&
                (isCancelRequested ? cancelRequestedText('export') : 'Export läuft …')}
              {runStatus === 'queued' &&
                (isCancelRequested ? cancelRequestedText('export') : waitingText('export'))}
              {isCancelled && 'Export abgebrochen'}
            </p>
            {(runStatus === 'running' || runStatus === 'queued') && (
              <OperationCancelButton
                operation="export"
                cancelRequested={isCancelRequested}
                pending={cancelMutation.isPending}
                onCancel={handleCancel}
              />
            )}
          </div>
          {runStatus === 'running' && <Progress />}
          {isCancelled && lastRun.target_path === null && (
            <p className="text-sm text-text">{EXPORT_CANCELLED_BEFORE_START_TEXT}</p>
          )}
          {isCancelled && lastRun.target_path !== null && (
            <p className="text-sm text-text">
              Export abgebrochen ({formatDateTime(lastRun.finished_at ?? lastRun.started_at)}).{' '}
              {lastRun.exported_count} von {lastRun.photo_count} Fotos wurden bereits nach{' '}
              <span className="break-all font-mono">{lastRun.target_path}</span> kopiert.
            </p>
          )}
          {isCancelled && <p className="text-sm text-text">{EXPORT_FOLDER_STAYS_TEXT}</p>}
        </div>
      )}

      {/* Danach: Bestaetigung mit Anzahl, Zielpfad und Zeitpunkt. */}
      {runStatus === 'success' && lastRun !== null && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-text">
            {lastRun.exported_count} von {lastRun.photo_count} Fotos nach{' '}
            <span className="font-mono">{lastRun.target_path}</span> exportiert (
            {formatDateTime(lastRun.finished_at ?? lastRun.started_at)})
          </p>
          {failedPhotos.length > 0 && (
            <Alert variant="warning" title="Einige Fotos konnten nicht übertragen werden">
              <ul className="list-disc pl-4">
                {failedPhotos.map((failed) => (
                  <li key={failed.relative_path}>{failed.relative_path}</li>
                ))}
              </ul>
            </Alert>
          )}
          <RerunBlock
            rerun={{
              label: 'Erneut exportieren',
              explanation:
                'Ein neuer Export legt einen weiteren, eigenen Ordner an und lässt den vorherigen unverändert.',
            }}
            onRerun={handleTrigger}
            // Nach dem Leeren der Auswahl ist auch der Rerun gesperrt - ein Klick queued sonst
            // einen Job, der keinen Lauf anlegt.
            disabled={isEmpty || isBusy}
            busy={isBusy}
          />
        </div>
      )}

      {/* Lauf fehlgeschlagen: die einzige Wiederholung ist die Hauptaktion. */}
      {runStatus === 'failed' && (
        <Alert onRetry={handleTrigger}>
          {lastRun?.error_message ?? 'Der Export ist fehlgeschlagen.'}
        </Alert>
      )}

      {/* Fehler beim Ausloesen: Server-`detail` woertlich. */}
      {triggerError !== null && <Alert onRetry={handleTrigger}>{triggerError}</Alert>}

      {cancelMutation.isError && (
        <Alert onRetry={handleCancel} retryLabel={CANCEL_TEXTS.retry}>
          {CANCEL_TEXTS.failed}
        </Alert>
      )}
    </section>
  )
}
