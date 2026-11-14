import type { OperationKind } from '../api/types'
import { cn } from '../lib/utils'
import { CANCEL_TEXTS, cancelAriaLabel, cancelRequestedText } from '../utils/operationTexts'
import { Button } from './ui/button'

interface OperationCancelButtonProps {
  /** Der Vorgang, zu dem der Knopf gehoert - traegt den zugaenglichen Namen. */
  operation: OperationKind
  /** Ein Abbruch ist angefordert: der Knopf bleibt an seiner Stelle und ist gesperrt. */
  cancelRequested: boolean
  /** Die Anfrage laeuft gerade (vor der ersten Antwort des Servers). */
  pending?: boolean
  onCancel: () => void
  className?: string
}

/**
 * Der EINE Abbruch-Knopf (Spec 0641): `secondary`, nie `destructive` - abgebrochen wird nichts
 * Vernichtendes, alles bis jetzt Fertige bleibt. Er sitzt beim Fortschritt seines Vorgangs, nicht
 * in einer Sammlung am Seitenrand. Die 44-px-Trefferflaeche spannt `tap-target` der Schaltflaeche
 * auf; die sichtbare Dichte bleibt bei 32 px.
 */
export function OperationCancelButton({
  operation,
  cancelRequested,
  pending = false,
  onCancel,
  className,
}: OperationCancelButtonProps) {
  const isRequested = pending || cancelRequested
  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      className={cn('shrink-0', className)}
      onClick={onCancel}
      disabled={isRequested}
      busy={isRequested}
      // Der Name nennt in BEIDEN Zustaenden den Vorgang: im gesperrten Zustand sonst drei
      // gleichnamige Knoepfe auf einer Seite mit drei Vorgaengen. Der sichtbare Text steckt
      // case-insensitiv im Namen (WCAG 2.5.3).
      aria-label={isRequested ? cancelRequestedText(operation) : cancelAriaLabel(operation)}
    >
      {isRequested ? CANCEL_TEXTS.requested : CANCEL_TEXTS.button}
    </Button>
  )
}
