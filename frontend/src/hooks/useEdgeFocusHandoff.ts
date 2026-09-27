import { useCallback, useLayoutEffect, useRef } from 'react'

/**
 * Ein Vor-/Zurück-Paar ohne Rundlauf: Wird die fokussierte Schaltfläche am Rand `disabled`, geht
 * der Fokus auf die Gegenschaltfläche über, statt auf `body` zu fallen und die Tastaturbedienung
 * an den Seitenanfang zu werfen.
 *
 * `remember()` steht VOR jedem Blättern: Es hält fest, welche der beiden gerade den Fokus hat.
 * Wechselt danach ein Rand, springt der Fokus nur, wenn er noch auf der jetzt gesperrten
 * Schaltfläche oder ganz ohne Ziel liegt — ein Nutzer, der inzwischen anderswo steht, behält
 * seinen Platz.
 */
export function useEdgeFocusHandoff(atStart: boolean, atEnd: boolean) {
  const previousRef = useRef<HTMLButtonElement>(null)
  const nextRef = useRef<HTMLButtonElement>(null)
  const pending = useRef<'previous' | 'next' | null>(null)

  const remember = useCallback(() => {
    const aktiv = document.activeElement
    pending.current =
      aktiv === previousRef.current ? 'previous' : aktiv === nextRef.current ? 'next' : null
  }, [])

  useLayoutEffect(() => {
    const gesperrt =
      pending.current === 'previous' && atStart
        ? previousRef.current
        : pending.current === 'next' && atEnd
          ? nextRef.current
          : null
    if (gesperrt === null) {
      return
    }
    pending.current = null
    const aktiv = document.activeElement
    if (aktiv === gesperrt || aktiv === null || aktiv === document.body) {
      ;(gesperrt === previousRef.current ? nextRef : previousRef).current?.focus()
    }
  }, [atStart, atEnd])

  return { previousRef, nextRef, remember }
}
