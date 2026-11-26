import { useEffect, useRef, useState } from 'react'

import type { OperationOut } from '../api/types'
import { useCancelAllOperations, useOperationsQuery } from '../hooks/useOperations'
import {
  CANCEL_TEXTS,
  cancelAllDescription,
  operationStatusWord,
  operationsBarText,
} from '../utils/operationTexts'
import { Alert } from './ui/alert'
import { Button } from './ui/button'
import { Dialog } from './ui/dialog'

/**
 * Die Projektleiste fuer laufende und wartende Vorgaenge.
 *
 * Sie erscheint NUR, solange es etwas zu nennen gibt - ein Projekt ohne Vorgang bekommt keine
 * leere Zeile. Die Namen kommen aus der Antwort des Servers (`label`), dieselbe Vokabel wie in
 * den Schritten.
 *
 * Der Dialog friert Liste und Anzahl beim Oeffnen ein: Waehrend die Bestaetigung offen ist, kann
 * ein Vorgang enden; die Frage „diese drei anhalten?" muss dann dieselben drei nennen wie der
 * anschliessende Aufruf. Nach der Bestaetigung geht der Fokus auf die Statuszeile, weil der
 * Ausloeser-Knopf jetzt gesperrt ist und keinen Fokus halten kann.
 */
export function ProjectOperationsBar({ projectId }: { projectId: number }) {
  const operationsQuery = useOperationsQuery(projectId)
  const cancelAll = useCancelAllOperations(projectId)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [frozen, setFrozen] = useState<OperationOut[]>([])
  const statusRef = useRef<HTMLParagraphElement>(null)
  // Der Fokus wandert erst NACH dem Schliessen: `Dialog` gibt ihn zunaechst an den Ausloeser
  // zurueck, und der ist in diesem Moment schon gesperrt.
  const focusStatusOnClose = useRef(false)

  useEffect(() => {
    if (!isDialogOpen && focusStatusOnClose.current) {
      focusStatusOnClose.current = false
      statusRef.current?.focus()
    }
  }, [isDialogOpen])

  const operations = operationsQuery.data?.operations ?? []
  if (operations.length === 0) {
    return null
  }
  const allCancelRequested = operations.every((operation) => operation.cancel_requested)

  function openDialog(): void {
    setFrozen(operations)
    setIsDialogOpen(true)
  }

  function closeDialog(): void {
    if (!cancelAll.isPending) {
      setIsDialogOpen(false)
    }
  }

  function confirmCancelAll(): void {
    cancelAll.mutate(undefined, {
      onSuccess: () => {
        focusStatusOnClose.current = true
        setIsDialogOpen(false)
      },
    })
  }

  return (
    <div className="mb-6 flex flex-col gap-3 rounded-lg border border-border bg-surface p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p
          ref={statusRef}
          role="status"
          aria-live="polite"
          tabIndex={-1}
          className="min-w-0 text-sm text-text"
        >
          {operationsBarText(operations, allCancelRequested)}
        </p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          aria-haspopup="dialog"
          disabled={allCancelRequested || cancelAll.isPending}
          onClick={openDialog}
        >
          {CANCEL_TEXTS.all}
        </Button>
      </div>

      {cancelAll.isError && (
        <Alert onRetry={confirmCancelAll} retryLabel={CANCEL_TEXTS.retry}>
          {CANCEL_TEXTS.failed}
        </Alert>
      )}

      <Dialog
        open={isDialogOpen}
        onClose={closeDialog}
        title={CANCEL_TEXTS.dialogTitle}
        description={cancelAllDescription(frozen.length)}
        cancelLabel={CANCEL_TEXTS.keepRunning}
        cancelDisabled={cancelAll.isPending}
        actions={
          <Button
            type="button"
            variant="default"
            disabled={cancelAll.isPending}
            busy={cancelAll.isPending}
            onClick={confirmCancelAll}
          >
            {CANCEL_TEXTS.all}
          </Button>
        }
      >
        <ul className="flex flex-col gap-2 text-sm text-text">
          {frozen.map((operation) => (
            <li key={`${operation.kind}-${operation.run_id}`}>
              {`${operation.label} — ${operationStatusWord(operation.status)}`}
            </li>
          ))}
        </ul>
        <p className="text-sm text-text">{CANCEL_TEXTS.keepsRunning}</p>
      </Dialog>
    </div>
  )
}
