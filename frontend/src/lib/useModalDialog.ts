import { useEffect, useRef } from 'react'
import type { KeyboardEvent, RefObject, SyntheticEvent } from 'react'

import { lockBodyScroll } from './scrollLock'

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

interface ModalDialogOptions {
  open: boolean
  /** Wird von Esc und von der nativen Schliessanfrage (`cancel`) ausgeloest. */
  onClose: () => void
  /** Das Element, das beim Oeffnen den Fokus bekommt. */
  initialFocusRef: RefObject<HTMLElement | null>
  /** `false`, wenn der Aufrufer den Fokus nach dem Schliessen selbst setzt: Die Rueckgabe hier
   * fokussiert ohne `preventScroll` und koennte einen verdeckten Ausloeser ins Bild scrollen. */
  returnFocus?: boolean
}

interface ModalDialogProps {
  ref: RefObject<HTMLDialogElement | null>
  onKeyDown: (event: KeyboardEvent<HTMLDialogElement>) => void
  onCancel: (event: SyntheticEvent<HTMLDialogElement>) => void
}

/**
 * Die Mechanik eines modalen nativen `<dialog>`: `showModal()`/`close()`, Fokusfalle, Esc,
 * Scroll-Sperre, Erstfokus und Fokus-Rueckgabe. Aussehen und Schliesswege darueber hinaus
 * (Hintergrundklick ja oder nein) legt der Aufrufer fest.
 *
 * FOKUSFALLE UND ESC SIND IN EIGENEM JS IMPLEMENTIERT, nicht dem nativen Element ueberlassen.
 * Grund ist keine Geschmacksfrage: jsdom implementiert weder `showModal()` noch die Fokusfalle
 * noch die Esc-Behandlung - eine Zusage, die allein auf dem nativen Verhalten beruhte, waere
 * untestbar, und der Projekt-Polyfill in setupTests.ts wuerde in einem Test nur sich selbst
 * bestaetigen.
 *
 * Verbindlich:
 *  - Esc ruft `onClose` bei JEDEM Druck; ein Riegel gegen wiederholtes Schliessen gehoert dem
 *    Aufrufer (siehe unten).
 *  - Der Fokus kehrt beim Schliessen zum vorher fokussierten Element zurueck, ausser der Aufrufer
 *    setzt ihn selbst (`returnFocus: false`).
 *  - Der Hintergrund scrollt nicht mit.
 *
 * Die zurueckgegebenen Props gehoeren unveraendert an das `<dialog>`.
 */
export function useModalDialog({
  open,
  onClose,
  initialFocusRef,
  returnFocus = true,
}: ModalDialogOptions): ModalDialogProps {
  const dialogRef = useRef<HTMLDialogElement>(null)
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
    initialFocusRef.current?.focus()

    // Zaehlende Sperre statt eigener Merkvariable: bei zwei gleichzeitig offenen Dialogen las die
    // zweite bereits 'hidden' als "vorherigen" Wert, und ein Schliessen in Anlegereihenfolge gab
    // den Hintergrund frei, obwohl noch ein Dialog offen war.
    const releaseScrollLock = lockBodyScroll()

    return () => {
      releaseScrollLock()
      // `close()` auf einem nicht offenen <dialog> kehrt laut Standard still zurueck (nur
      // `showModal()` wirft) - der Riegel steht hier also NICHT gegen eine Ausnahme, sondern
      // schreibt die Invariante hin: seit das native `cancel` angeschlossen ist, gibt es einen
      // Schliesspfad, der das Element bereits geschlossen haben kann, bevor dieser Cleanup laeuft.
      if (dialog.open) {
        dialog.close()
      }
      if (returnFocus) {
        previouslyFocusedRef.current?.focus()
      }
    }
  }, [open, initialFocusRef, returnFocus])

  function onKeyDown(event: KeyboardEvent<HTMLDialogElement>): void {
    if (event.key === 'Escape') {
      /*
       * `preventDefault()` unterdrueckt hier NICHT zuverlaessig, dass der Browser seine
       * Schliessanfrage stellt: die ist nicht als Standardaktion des `keydown` definiert. Der
       * dafuer vorgesehene Haken ist `cancel` (siehe `onCancel`). Was `preventDefault()` hier
       * tatsaechlich leistet, ist bescheidener und trotzdem richtig: es haelt Esc davon ab,
       * gleichzeitig etwas ausserhalb des Dialogs auszuloesen.
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
    // Der Ausreisserfall wurde zuvor NUR fuer Shift+Tab behandelt - vorwaerts traf kein Zweig zu
    // und der Fokus wanderte aus dem Modal heraus. Beide Richtungen fangen ihn jetzt gleich ab:
    // rueckwaerts auf das letzte, vorwaerts auf das erste Element.
    const hasStrayFocus = !dialog.contains(active)

    if (event.shiftKey && (hasStrayFocus || active === first)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && (hasStrayFocus || active === last)) {
      event.preventDefault()
      first.focus()
    }
  }

  // Der vom Standard vorgesehene Haken fuer die Schliessanfrage des Browsers (Esc, aber auch z.B.
  // eine Geste des Betriebssystems). `preventDefault()` haelt das Element davon ab, sich am Zustand
  // des Aufrufers vorbei selbst zu schliessen; geschlossen wird ueber `open`.
  function onCancel(event: SyntheticEvent<HTMLDialogElement>): void {
    event.preventDefault()
    if (escapeHandledRef.current) {
      // Folgeereignis zu dem Esc, das gerade selbst behandelt wurde - Markierung verbrauchen,
      // nicht ein zweites Mal schliessen.
      escapeHandledRef.current = false
      return
    }
    onClose()
  }

  return { ref: dialogRef, onKeyDown, onCancel }
}
