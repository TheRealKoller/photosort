import type { ReactNode } from 'react'

import { ApiError } from '../api/client'
import type { DuplicateDecision } from '../api/types'
import { LAST_GROUP_TEXT } from '../utils/duplicateTexts'
import { Alert } from './ui/alert'
import { Button } from './ui/button'

export interface DuplicateGroupActionsProps {
  /** Ohne gefüllte Gruppe stehen nur `children` da - an derselben Stelle im Baum. */
  filled: boolean
  groupPending: boolean
  groupError: Error | null
  autoDecided: boolean
  confirmBlocked: boolean
  confirmPending: boolean
  confirmLabel: string
  lastGroupSaved: boolean
  confirmError: Error | null
  onGroupDecision: (decision: DuplicateDecision) => void
  onConfirm: () => void
  /** Raster oder Großansicht, zwischen Gruppenaktionen und Abschluss. */
  children: ReactNode
}

/** Gruppenaktionen über dem Raster, Abschluss und Live-Region darunter. */
export function DuplicateGroupActions({
  filled,
  groupPending,
  groupError,
  autoDecided,
  confirmBlocked,
  confirmPending,
  confirmLabel,
  lastGroupSaved,
  confirmError,
  onGroupDecision,
  onConfirm,
  children,
}: DuplicateGroupActionsProps) {
  return (
    <>
      {filled && (
        /* Beschriftete Schaltflächen, keine Symbole: Beide setzen in EINEM Aufruf den Zustand
            jeder Aufnahme der Gruppe, und eine Glyphe sagte nicht, welche Richtung. */
        <div className="flex flex-col gap-3">
          <div role="group" aria-label="Ganze Gruppe" className="flex flex-wrap gap-3">
            {(['keep', 'discard'] as const).map((wert) => (
              <Button
                key={wert}
                type="button"
                variant="outline"
                disabled={groupPending}
                busy={groupPending}
                onClick={() => onGroupDecision(wert)}
              >
                {wert === 'keep' ? 'Alle behalten' : 'Alle in den Ausschuss'}
              </Button>
            ))}
          </div>
          {groupError !== null && (
            <Alert>
              {groupError instanceof ApiError
                ? groupError.detail
                : 'Die Entscheidung für die Gruppe konnte nicht gespeichert werden.'}
            </Alert>
          )}
        </div>
      )}

      {children}

      {/* Der Abschluss schreibt den angezeigten Zustand fest, statt ihn zu ändern - es
          entsteht kein Gruppenzustand „erledigt". Gesperrt, solange eine Einzel- oder
          Gruppenentscheidung läuft: Er schriebe sonst gegen einen Stand, der gerade wechselt.
          Die Schaltfläche selbst ist die Wiederholung nach einem Fehler. */}
      {/* In einer automatisch entschiedenen Gruppe entfällt der Abschluss ganz (nicht
          `disabled`): Er schriebe einen Stand fest, der schon festgeschrieben ist. */}
      {filled && (
        <div className="flex flex-col items-start gap-3">
          {!autoDecided && (
            <Button
              type="button"
              disabled={confirmBlocked}
              busy={confirmPending}
              onClick={onConfirm}
            >
              {confirmLabel}
            </Button>
          )}
          {/* Die Live-Region steht im gefüllten Zustand IMMER da, nur ihr Text wechselt: Eine
              Region, die erst zusammen mit ihrem Text erscheint, sagen Screenreader oft nicht an. */}
          <p aria-live="polite" data-testid="duplicate-last-group" className="text-sm text-text">
            {lastGroupSaved ? LAST_GROUP_TEXT : ''}
          </p>
          {confirmError !== null && (
            <Alert>
              {confirmError instanceof ApiError
                ? confirmError.detail
                : 'Die Gruppe konnte nicht abgeschlossen werden.'}
            </Alert>
          )}
        </div>
      )}
    </>
  )
}
