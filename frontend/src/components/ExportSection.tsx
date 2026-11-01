import { ApiError } from '../api/client'
import { useExport } from '../hooks/useExport'
import { formatDateTime } from '../utils/formatStats'
import { RerunBlock } from './RerunBlock'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Progress } from './ui/progress'

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

  const photoCount = preview.data?.photo_count ?? 0
  const isEmpty = preview.isSuccess && photoCount === 0
  const runStatus = lastRun?.status ?? null
  const isTriggerPending = trigger.isPending || awaiting
  const isBusy = isTriggerPending || runStatus === 'running'
  const failedPhotos = runDetail.data?.failed_photos ?? []

  const triggerError =
    trigger.isError && trigger.error instanceof ApiError ? trigger.error.detail : null

  function handleTrigger(): void {
    setAwaiting(true)
    trigger.mutate()
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
          busy={isBusy}
          onClick={handleTrigger}
        >
          Nach OpenCloud exportieren
        </Button>
        <p className="text-sm text-text">
          {isEmpty
            ? 'Die Endauswahl ist leer — es gibt nichts zu exportieren'
            : `${photoCount} Fotos`}
        </p>
      </div>

      {/* Waehrend: Statuszeile + indeterminierter Fortschritt. */}
      {runStatus === 'running' && (
        <div className="flex w-full flex-col gap-2" aria-live="polite">
          <p className="text-sm text-text">Export läuft …</p>
          <Progress />
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
    </section>
  )
}
