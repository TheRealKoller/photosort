import { useEffect, useRef } from 'react'

/**
 * Nach einer erfolgreichen Abbruch-Anforderung ist der Knopf gesperrt und kann keinen
 * Fokus halten. Der Fokus geht deshalb auf die Statuszeile des Vorgangs - sie ist bereits
 * `aria-live="polite"` und traegt jetzt „… wird abgebrochen…".
 *
 * Bewegt wird der Fokus NUR fuer die EIGENE Anfrage. Deren Nachweis ist die Antwort der Mutation
 * (`cancelMutation.data ?? null`): sie liegt erst nach einem erfolgreichen Druck vor und ist bei
 * jedem Erfolg ein neues Objekt. Ein Poll, der einen Abbruch nachtraegt, den der Nutzer nicht
 * ausgeloest hat, laesst den Wert unveraendert - der Text dort ist eine Zustandsmeldung, keine
 * Antwort auf eine Bedienung, und ein Fokussprung risse den Nutzer aus seiner Arbeit. Beim Aufbau
 * der Seite liegt ebenfalls kein Wert vor; eine geladene, bereits angeforderte Seite springt nicht.
 */
export function useCancelRequestFocus<T extends HTMLElement>(ownRequest: unknown) {
  const ref = useRef<T>(null)
  const seen = useRef(ownRequest)

  useEffect(() => {
    if (ownRequest !== null && ownRequest !== seen.current) {
      ref.current?.focus()
    }
    seen.current = ownRequest
  }, [ownRequest])

  return ref
}
