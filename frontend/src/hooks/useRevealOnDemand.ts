import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

/** Ab dieser Druckdauer erscheinen die Angaben, statt die Kachel zu aktivieren. */
export const LONG_PRESS_MS = 500

/** Ein Geraet mit feinem Zeiger und Hover-Faehigkeit loest die Angaben durch Ueberfahren aus. */
const HOVER_QUERY = '(hover: hover) and (pointer: fine)'

type RevealSource = 'hover' | 'focus' | 'press'

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
 * WOHER die Angaben kamen, nicht nur DASS sie da sind: Ein TOUCH-Pointer wird nach `pointerup` vom
 * Browser zerstoert und feuert dabei `pointerleave`, ohne Zutun des Nutzers. Blendete das
 * Verlassen bedingungslos aus, verschwaenden die per langem Druck eingeblendeten Angaben im selben
 * Moment, in dem der Finger sie freigibt.
 */
export function useRevealOnDemand(): RevealOnDemand {
  const [source, setSource] = useState<RevealSource | null>(null)
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
    if (source !== 'press') {
      return undefined
    }
    const close = (): void => setSource(null)
    document.addEventListener('pointerdown', close, { capture: true })
    window.addEventListener('scroll', close, { passive: true })
    return () => {
      document.removeEventListener('pointerdown', close, { capture: true })
      window.removeEventListener('scroll', close)
    }
  }, [source])

  return {
    visible: source !== null,
    handlers: {
      onPointerDown: () => {
        if (hoverCapable) {
          return
        }
        clearTimer()
        timerRef.current = setTimeout(() => {
          timerRef.current = null
          suppressClickRef.current = true
          setSource('press')
        }, LONG_PRESS_MS)
      },
      onPointerUp: clearTimer,
      onPointerCancel: clearTimer,
      onPointerEnter: hoverCapable ? () => setSource('hover') : undefined,
      onPointerLeave: () => {
        // Der laufende Druck wird IMMER abgebrochen; ausgeblendet wird nur, was durch
        // Ueberfahren kam.
        clearTimer()
        setSource((current) => (current === 'hover' ? null : current))
      },
      onFocus: () => setSource('focus'),
      onBlur: () => setSource((current) => (current === 'focus' ? null : current)),
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
