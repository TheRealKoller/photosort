import type { ReactNode } from 'react'

import { Button } from './ui/button'

interface RerunBlockProps {
  rerun: { label: string; explanation: string }
  onRerun: () => void
  disabled?: boolean
  /** Ausgelöst, aber noch keine Laufantwort: Ladezeichen und gesperrt (Busy-Muster). */
  busy?: boolean
  /** Zusatz unter dem Erklärsatz, z.B. die Kostenschätzung der Klassifizierung. */
  children?: ReactNode
}

/**
 * Der nachrangige „Erneut …"-Auslöser im Schrittkopf. Der Erklärsatz steht immer sichtbar daneben
 * (kein Tooltip, kein Aufklapper), und es gibt keinen Bestätigungsdialog.
 */
export function RerunBlock({
  rerun,
  onRerun,
  disabled = false,
  busy = false,
  children,
}: RerunBlockProps) {
  return (
    <div data-testid="rerun-block" className="flex flex-col items-start gap-2">
      <div className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={onRerun}
          disabled={disabled}
          busy={busy}
        >
          {rerun.label}
        </Button>
        <p className="text-sm text-text">{rerun.explanation}</p>
      </div>
      {children}
    </div>
  )
}
