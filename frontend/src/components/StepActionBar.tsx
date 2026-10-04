import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { StepAction } from '../utils/stepActions'
import { Button } from './ui/button'

interface StepActionBarProps {
  action: StepAction
  /** Die Statuszeile - die einzige Live-Region des Laufstatus einer Schrittseite. Ohne eigenen
   * Lauf (Kuratierung) bleibt sie leer. */
  status?: ReactNode
  /** Fortschrittsblock unter der Statuszeile, außerhalb der Live-Region. */
  detail?: ReactNode
  /** Auslöser für `start`, `retry` und `confirm`. */
  onAction?: () => void
  /** Sperrt `start`, `retry` und `confirm`. */
  disabled?: boolean
  /** Laufende Anfrage der Abschluss-Aktion. */
  busy?: boolean
}

const ACTION_CLASSES = 'h-11 w-full shrink-0 sm:h-8 sm:w-auto'

/**
 * Die haftende Fußleiste einer Schrittseite mit Statuszeile und der einen Hauptaktion.
 *
 * MUSS DAS LETZTE ELEMENT IM FLUSS DER SEITE SEIN und haftet über `sticky`, nie `fixed`: Sie
 * behält damit ihren Platz und schiebt die letzte Rasterzeile und „Mehr laden" beim Scrollen bis
 * zum Ende über sich, statt sie zu verdecken. Setzt ein Vorfahr `overflow`, haftet sie nicht mehr
 * am Viewport (gemessen in `e2e/tests/step-action-bar.spec.ts`).
 *
 * `next` und `open` sind Links: Sie navigieren und starten nichts.
 */
export function StepActionBar({
  action,
  status,
  detail,
  onAction,
  disabled = false,
  busy = false,
}: StepActionBarProps) {
  let control: ReactNode
  switch (action.kind) {
    case 'start':
    case 'retry':
    case 'confirm':
      control = (
        <Button
          type="button"
          className={ACTION_CLASSES}
          onClick={onAction}
          disabled={disabled}
          busy={busy}
        >
          {action.label}
        </Button>
      )
      break
    case 'running':
      control = (
        <Button type="button" className={ACTION_CLASSES} disabled busy>
          {action.label}
        </Button>
      )
      break
    case 'next':
    case 'open':
      control = (
        <Button asChild className={ACTION_CLASSES}>
          <Link to={action.to}>{action.label}</Link>
        </Button>
      )
      break
    case 'nextUnavailable':
      control = <p className="text-sm text-text">{action.text}</p>
      break
  }

  return (
    <div
      role="group"
      aria-label="Nächste Aktion"
      data-testid="step-action-bar"
      className="safe-area-bottom sticky bottom-0 z-10 w-full self-stretch border-t border-separator bg-bg pt-3"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <div className="flex min-w-0 flex-col gap-2">
          <p aria-live="polite" className="flex items-center gap-2 text-sm text-text">
            {status}
          </p>
          {detail}
        </div>
        {control}
      </div>
    </div>
  )
}
