import { useId, useRef } from 'react'
import type { ReactNode } from 'react'

import { Button } from './button'
import { Icon } from './icon'
import type { IconName } from './icon'
import { cn } from '../../lib/utils'
import { useModalDialog } from '../../lib/useModalDialog'

export interface DialogProps {
  open: boolean
  /** Wird von Esc und von der Abbrechen-Schaltflaeche ausgeloest - NICHT vom Hintergrundklick. */
  onClose: () => void
  title: string
  /** Erklaerender Text, ueber `aria-describedby` mit dem Dialog verknuepft. */
  description?: string
  icon?: IconName
  children?: ReactNode
  /** Bestaetigende/eingreifende Aktionen. Sie stehen im DOM NACH der Abbrechen-Schaltflaeche,
   * damit der Erstfokus nie auf ihnen landet. */
  actions?: ReactNode
  cancelLabel?: string
  /** Deaktiviert die eingebaute Abbrechen-Schaltflaeche, solange der Aufrufer eine Anfrage
   * laufen hat. Die Zusage "Esc ruft IMMER `onClose`" bleibt davon unberuehrt - ein Aufrufer, der
   * waehrend seiner Anfrage nicht geschlossen werden
   * will, ignoriert `onClose` selbst; das ist hier ausdruecklich vorgesehen. */
  cancelDisabled?: boolean
}

/**
 * Ueberlagerung/Modal nach dem Board: Flaeche `--overlay`, Rand `--border`, Radius 16px,
 * Polsterung 24px, Titelzeile mit Symbol, Schaltflaechenzeile rechtsbuendig, verdunkelter
 * Hintergrund ueber `::backdrop`.
 *
 * Natives <dialog> statt eines neuen @radix-ui/react-dialog-Pakets - dieselbe Linie wie
 * switch.tsx und checkbox.tsx ("Radix-Primitives nur dort einsetzen, wo natives HTML nicht
 * reicht"). Die Grundelemente-Liste des Boards verlangt Ueberlagerungen als Teil des Fundaments;
 * ein Primitiv vor seinem ersten Konsumenten ist genau das, was ein Grundelemente-Satz ist.
 *
 * Fokusfalle, Esc, Scroll-Sperre und Fokus-Rueckgabe liefert `lib/useModalDialog.ts`.
 *
 * Verbindlich:
 *  - Erstfokus auf der am wenigsten eingreifenden Schaltflaeche (Abbrechen), nie auf einer
 *    bestaetigenden oder loeschenden Aktion.
 *  - Esc schliesst; ein Klick auf den verdunkelten Hintergrund schliesst NICHT (der erste
 *    Konsument ist ein Dialog vor einer kostenpflichtigen Aktion - versehentliches Verwerfen
 *    waere hier teuer).
 *  - Der Fokus kehrt beim Schliessen zum ausloesenden Element zurueck.
 *  - Der Hintergrund scrollt nicht mit.
 *  - Keine Oeffnungs-/Schliessanimation - es gibt keine im Board, und fuer eine Anwendung, in der
 *    Dialoge waehrend schneller Arbeit auftauchen, ist Sofortigkeit das bessere Verhalten.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  icon,
  children,
  actions,
  cancelLabel = 'Abbrechen',
  cancelDisabled = false,
}: DialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null)
  const modal = useModalDialog({ open, onClose, initialFocusRef: cancelRef })
  const titleId = useId()
  const descriptionId = useId()

  if (!open) {
    return null
  }

  return (
    <dialog
      {...modal}
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={description === undefined ? undefined : descriptionId}
      // Bewusst KEIN Hintergrundklick-Handler: der Klick auf den ::backdrop trifft das
      // <dialog>-Element selbst - ein `onClick`, das darauf schliesst, ist genau das versehentliche
      // Verwerfen, das hier ausgeschlossen ist.
      className={cn(
        'm-auto w-[min(32rem,calc(100vw-2rem))] rounded-xl border border-border bg-overlay p-6 text-text',
        'backdrop:bg-black/60',
      )}
    >
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-3">
          {icon !== undefined && <Icon name={icon} size={24} className="shrink-0 text-accent" />}
          <h2 id={titleId} className="text-lg font-bold text-text-h">
            {title}
          </h2>
        </div>
        {description !== undefined && (
          <p id={descriptionId} className="text-sm text-text">
            {description}
          </p>
        )}
        {children}
        <div className="flex flex-wrap justify-end gap-3">
          {/* Die harmloseste Aktion steht ZUERST im DOM - so kann der Erstfokus strukturell nicht
              auf einer bestaetigenden oder loeschenden Aktion landen. */}
          <Button
            ref={cancelRef}
            type="button"
            variant="secondary"
            disabled={cancelDisabled}
            onClick={onClose}
          >
            {cancelLabel}
          </Button>
          {actions}
        </div>
      </div>
    </dialog>
  )
}
