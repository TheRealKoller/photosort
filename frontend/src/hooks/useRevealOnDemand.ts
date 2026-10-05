import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

/** Ab dieser Druckdauer erscheinen die Angaben, statt die Kachel zu aktivieren. */
export const LONG_PRESS_MS = 500

/** Ein Geraet mit feinem Zeiger und Hover-Faehigkeit loest die Angaben durch Ueberfahren aus. */
const HOVER_QUERY = '(hover: hover) and (pointer: fine)'

export interface RevealOnDemand {
  visible: boolean
  /** Gehoeren an das Element, das die ganze Kachel umfasst. */
  handlers: {
    onPointerDown: () => void
    onPointerUp: () => void
    onPointerCancel: () => void
    onPointerEnter: (() => void) | undefined
    onPointerLeave: () => void
    onFocus: () => void
    onBlur: () => void
  }
  /**
   * Fuer den Klick, der einem langen Druck folgt: verhindert seine Standardwirkung und meldet
   * `true`, genau einmal je langem Druck. Der lange Druck blendet ein und aktiviert NICHTS -
   * ohne das folgte der Browser unmittelbar danach dem Link bzw. loeste den Knopf aus.
   */
  consumeSuppressedClick: (event: { preventDefault: () => void }) => boolean
}

/**
 * Angaben einer Kachel auf Anforderung: beim Ueberfahren (nur mit feinem Zeiger), solange ein
 * Bedienelement darin den Fokus hat, und nach einem Druck von mindestens `LONG_PRESS_MS`.
 *
 * JEDER AUSLOESER FUER SICH, nicht ein gemeinsamer Zustand: Ein TOUCH-Pointer wird nach `pointerup` vom
 * Browser zerstoert und feuert dabei `pointerleave`, ohne Zutun des Nutzers. Blendete das
 * Verlassen bedingungslos aus, verschwaenden die per langem Druck eingeblendeten Angaben im selben
 * Moment, in dem der Finger sie freigibt.
 */
export function useRevealOnDemand(): RevealOnDemand {
  // Drei unabhaengige Ausloeser: Das Ende des einen darf die anderen nie mitnehmen (Fokus bleibt,
  // auch wenn der Zeiger die Kachel verlaesst; ein langer Druck bleibt, auch wenn ein Touch-Pointer
  // beim Loslassen `pointerleave` feuert).
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [pressed, setPressed] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const suppressClickRef = useRef(false)

  // Einmal beim ersten Rendern gelesen: Die Geraeteklasse wechselt waehrend einer Sitzung nicht,
  // und ein Abonnement je Kachel waere bei zweihundert Kacheln zweihundert Abonnements.
  const hoverCapable = useMemo(
    () =>
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia(HOVER_QUERY).matches,
    [],
  )

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => clearTimer, [clearTimer])

  /*
   * Das Gegenstueck zum langen Druck: So eingeblendete Angaben schliessen beim naechsten Druck
   * IRGENDWO oder beim Rollen. Am Zeigegeraet uebernimmt das Verlassen der Kachel diese Rolle, am
   * Telefon gibt es das nicht.
   *
   * `capture: true` - ein `pointerdown` auf einem Bedienelement, das `stopPropagation` ruft,
   * erreichte die Blasenphase am Dokument sonst nie, und die Angaben blieben stehen.
   */
  useEffect(() => {
    if (!pressed) {
      return undefined
    }
    const close = (): void => setPressed(false)
    document.addEventListener('pointerdown', close, { capture: true })
    window.addEventListener('scroll', close, { passive: true })
    return () => {
      document.removeEventListener('pointerdown', close, { capture: true })
      window.removeEventListener('scroll', close)
    }
  }, [pressed])

  return {
    visible: hovered || focused || pressed,
    handlers: {
      onPointerDown: () => {
        if (hoverCapable) {
          return
        }
        clearTimer()
        timerRef.current = setTimeout(() => {
          timerRef.current = null
          suppressClickRef.current = true
          setPressed(true)
        }, LONG_PRESS_MS)
      },
      onPointerUp: clearTimer,
      onPointerCancel: clearTimer,
      onPointerEnter: hoverCapable ? () => setHovered(true) : undefined,
      onPointerLeave: () => {
        // Der laufende Druck wird IMMER abgebrochen; zurueckgenommen wird nur das Ueberfahren.
        clearTimer()
        setHovered(false)
      },
      onFocus: () => setFocused(true),
      onBlur: () => setFocused(false),
    },
    consumeSuppressedClick: (event) => {
      if (!suppressClickRef.current) {
        return false
      }
      suppressClickRef.current = false
      event.preventDefault()
      return true
    },
  }
}
