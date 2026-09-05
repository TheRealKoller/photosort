import { useEffect, useId, useRef } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'

import { Button } from './button'
import { Icon } from './icon'
import type { IconName } from './icon'
import { cn } from '../../lib/utils'

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
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Ueberlagerung/Modal nach dem Board (specs/architecture/0005-board-dark-utility-register.md
 * Abschnitt 6): Flaeche `--overlay`, Rand `--border`, Radius 16px, Polsterung 24px, Titelzeile mit
 * Symbol, Schaltflaechenzeile rechtsbuendig, verdunkelter Hintergrund ueber `::backdrop`.
 *
 * Natives <dialog> statt eines neuen @radix-ui/react-dialog-Pakets - dieselbe Linie wie
 * switch.tsx und checkbox.tsx ("Radix-Primitives nur dort einsetzen, wo natives HTML nicht
 * reicht"). Die Grundelemente-Liste des Boards verlangt Ueberlagerungen als Teil des Fundaments;
 * ein Primitiv vor seinem ersten Konsumenten ist genau das, was ein Grundelemente-Satz ist.
 *
 * FOKUSFALLE UND ESC SIND IN EIGENEM JS IMPLEMENTIERT, nicht dem nativen Element ueberlassen.
 * Grund ist keine Geschmacksfrage: jsdom implementiert weder `showModal()` noch die Fokusfalle
 * noch die Esc-Behandlung - eine Zusage, die allein auf dem nativen Verhalten beruhte, waere
 * untestbar, und der Projekt-Polyfill in setupTests.ts wuerde in einem Test nur sich selbst
 * bestaetigen.
 *
 * Verbindlich (UI/UX-Abschnitt der Spec 0320):
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
}: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const cancelRef = useRef<HTMLButtonElement>(null)
  const previouslyFocusedRef = useRef<HTMLElement | null>(null)
  /* Esc und das native `cancel` treffen im Browser in DERSELBEN Interaktion ein - vor dem
   * naechsten Rendern, `open` ist dann noch `true`. Ohne Absprache liefe `onClose` doppelt; bei
   * einem Aufrufer, an dem daran mehr haengt als ein `setOpen(false)`, waere das ein echter
   * Fehler. In jsdom feuert `cancel` nie von selbst - der Doppelaufruf traete also nur im Browser
   * auf und bliebe hier unsichtbar.
   *
   * Die Richtung der Absprache ist bewusst gewaehlt: Esc SETZT die Markierung und schliesst immer,
   * `cancel` VERBRAUCHT sie und schliesst nur, wenn keine gesetzt war. Andersherum (ein Riegel,
   * der nach dem ersten Schliessen dauerhaft haelt) wuerde ein zweites Esc verschlucken, sobald
   * ein Aufrufer das erste bewusst ignoriert - z.B. um vor dem Verwerfen von Eingaben
   * nachzufragen. Esc ist der Weg, den Nutzer tatsaechlich nehmen; er muss immer tragen. */
  const escapeHandledRef = useRef(false)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    const dialog = dialogRef.current
    if (dialog === null) {
      return
    }
    if (!open) {
      return
    }

    escapeHandledRef.current = false
    previouslyFocusedRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    dialog.showModal()
    cancelRef.current?.focus()

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = previousOverflow
      // `close()` auf einem nicht offenen <dialog> kehrt laut Standard still zurueck (nur
      // `showModal()` wirft) - der Riegel steht hier also NICHT gegen eine Ausnahme, sondern
      // schreibt die Invariante hin: seit das native `cancel` angeschlossen ist, gibt es einen
      // Schliesspfad, der das Element bereits geschlossen haben kann, bevor dieser Cleanup laeuft.
      if (dialog.open) {
        dialog.close()
      }
      previouslyFocusedRef.current?.focus()
    }
  }, [open])

  if (!open) {
    return null
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDialogElement>): void {
    if (event.key === 'Escape') {
      /*
       * `preventDefault()` unterdrueckt hier NICHT zuverlaessig, dass der Browser seine
       * Schliessanfrage stellt: die ist nicht als Standardaktion des `keydown` definiert. Der
       * dafuer vorgesehene Haken ist `cancel`, und der haengt unten am Element. Was
       * `preventDefault()` hier tatsaechlich leistet, ist bescheidener und trotzdem richtig: es
       * haelt Esc davon ab, gleichzeitig etwas ausserhalb des Dialogs auszuloesen.
       *
       * Der Grund, Esc ueberhaupt selbst zu behandeln statt es allein `cancel` zu ueberlassen,
       * bleibt unveraendert: jsdom implementiert weder `showModal()` noch die Esc-Behandlung des
       * <dialog>-Elements - eine Zusage, die nur auf dem nativen Pfad beruhte, waere untestbar.
       */
      event.preventDefault()
      escapeHandledRef.current = true
      onClose()
      return
    }

    if (event.key !== 'Tab') {
      return
    }

    const dialog = dialogRef.current
    if (dialog === null) {
      return
    }
    const focusable = [...dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)]
    if (focusable.length === 0) {
      return
    }
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    const active = document.activeElement
    // Copilot-Review-Fund (PR #322): Der Ausreisserfall wurde zuvor NUR fuer Shift+Tab behandelt -
    // vorwaerts traf kein Zweig zu und der Fokus wanderte aus dem Modal heraus. Beide Richtungen
    // fangen ihn jetzt gleich ab: rueckwaerts auf das letzte, vorwaerts auf das erste Element.
    const hasStrayFocus = !dialog.contains(active)

    if (event.shiftKey && (hasStrayFocus || active === first)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && (hasStrayFocus || active === last)) {
      event.preventDefault()
      first.focus()
    }
  }

  return (
    <dialog
      ref={dialogRef}
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={description === undefined ? undefined : descriptionId}
      onKeyDown={handleKeyDown}
      // Der vom Standard vorgesehene Haken fuer die Schliessanfrage des Browsers (Esc, aber auch
      // z.B. eine Geste des Betriebssystems). `preventDefault()` haelt das Element davon ab, sich
      // an unserem Zustand vorbei selbst zu schliessen; geschlossen wird ueber `open`.
      onCancel={(event) => {
        event.preventDefault()
        if (escapeHandledRef.current) {
          // Folgeereignis zu dem Esc, das wir gerade selbst behandelt haben - Markierung
          // verbrauchen, nicht ein zweites Mal schliessen.
          escapeHandledRef.current = false
          return
        }
        onClose()
      }}
      // Bewusst KEIN Hintergrundklick-Handler: der Klick auf den ::backdrop trifft das
      // <dialog>-Element selbst - ein `onClick`, das darauf schliesst, ist genau das versehentliche
      // Verwerfen, das hier ausgeschlossen ist.
      className={cn(
        'm-auto w-[min(32rem,calc(100vw-2rem))] rounded-xl border border-border bg-overlay p-6 text-text',
        'backdrop:bg-black/60'
      )}
    >
      <div className="flex flex-col gap-5">
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
          <Button ref={cancelRef} type="button" variant="secondary" onClick={onClose}>
            {cancelLabel}
          </Button>
          {actions}
        </div>
      </div>
    </dialog>
  )
}
