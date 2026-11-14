import { useEffect, useRef } from 'react'

/**
 * Spec 0641: Nach einer erfolgreichen Abbruch-Anforderung ist der Knopf gesperrt und kann keinen
 * Fokus halten. Der Fokus geht deshalb auf die Statuszeile des Vorgangs - sie ist bereits
 * `aria-live="polite"` und traegt jetzt „… wird abgebrochen…". Der Wechsel wird beobachtet statt
 * vom Aufrufer gemeldet, damit ein spaeter eintreffender Poll denselben Sprung ausloest.
 */
export function useCancelRequestFocus<T extends HTMLElement>(isCancelRequested: boolean) {
  const ref = useRef<T>(null)
  // Startwert: beim Aufbau mit bereits angefordertem Abbruch wandert der Fokus NICHT - die Seite
  // wird dann geladen, nicht bedient.
  const wasRequested = useRef(isCancelRequested)

  useEffect(() => {
    if (isCancelRequested && !wasRequested.current) {
      ref.current?.focus()
    }
    wasRequested.current = isCancelRequested
  }, [isCancelRequested])

  return ref
}
