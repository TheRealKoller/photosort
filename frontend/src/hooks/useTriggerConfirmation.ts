import { useEffect, useRef, useState } from 'react'

import type { ProcessStatus } from '../utils/processStatus'
import { POLL_INTERVAL_MS } from './useProjects'

/**
 * Ueberbrueckt das Zeitfenster zwischen erfolgreichem Trigger (202) und dem ersten Poll, der den
 * neuen Scan-/Scoring-Lauf tatsaechlich bestaetigt: der Button bleibt deaktiviert, bis entweder
 * Polling running bestaetigt oder der Trigger selbst fehlschlaegt.
 *
 * Nur auf `status === 'running'` zu warten reicht NICHT: Bei einem zuvor gelaufenen Projekt ist
 * der beobachtete Status schon nicht-null, und ein sehr schneller Lauf springt direkt von null auf
 * `success`/`failed` - der Zwischenzustand wird nie beobachtet. Ein blosses `status !== null`
 * reicht ebenfalls NICHT: Der Refetch direkt nach der 202-Antwort kann noch den Endzustand des
 * VORHERIGEN Laufs liefern.
 *
 * Unterschieden wird deshalb ueber `started_at`: Jeder Lauf bekommt serverseitig einen frischen
 * Zeitstempel. Das awaiting-Flag wird zurueckgesetzt, sobald "running" oder "queued" beobachtet
 * wird ODER ein NEUER `started_at` zusammen mit einem beliebigen Endzustand (success/failed).
 */
export function useTriggerConfirmation(
  status: ProcessStatus | null,
  startedAt: string | null,
  refetch: () => unknown,
): [boolean, (value: boolean) => void] {
  const [awaiting, setAwaiting] = useState(false)

  // Ref statt Abhaengigkeit auf `refetch` selbst: `query.refetch` ist bei jedem Render eine neue
  // Funktionsreferenz, eine Abhaengigkeit darauf wuerde das Intervall bei jedem Render neu
  // aufsetzen. Bewusst als lokaler `useRef` INNERHALB des Hooks (statt als von aussen
  // hereingereichter Ref-Parameter) - so kann das react-hooks-Lint-Plugin die Stabilitaet der Ref
  // selbst erkennen, statt sie faelschlich als fehlende Abhaengigkeit zu melden.
  const refetchRef = useRef(refetch)
  refetchRef.current = refetch

  // Wird bei jedem Render aktualisiert, SOLANGE nicht gewartet wird - friert dadurch beim
  // Setzen von awaiting=true (Klick) automatisch auf den zuletzt bekannten, "alten" started_at
  // ein (gleiches Ref-statt-Effect-Update-Muster wie oben bei refetchRef).
  const baselineStartedAtRef = useRef(startedAt)
  if (!awaiting) {
    baselineStartedAtRef.current = startedAt
  }

  useEffect(() => {
    if (!awaiting) {
      return
    }
    const isNewRun = startedAt !== baselineStartedAtRef.current
    // `queued` bestaetigt den Trigger ebenfalls: der Auftrag ist angenommen, auch wenn
    // der Worker ihn noch nicht begonnen hat.
    if (status === 'running' || status === 'queued' || (status !== null && isNewRun)) {
      setAwaiting(false)
      return
    }
    const interval = setInterval(() => {
      void refetchRef.current()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [awaiting, status, startedAt])

  return [awaiting, setAwaiting]
}
