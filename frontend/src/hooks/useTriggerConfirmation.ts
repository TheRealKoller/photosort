import { useEffect, useRef, useState } from 'react'

import type { ProcessStatus } from '../utils/processStatus'
import { POLL_INTERVAL_MS } from './useProjects'

/**
 * Ueberbrueckt das Zeitfenster zwischen erfolgreichem Trigger (202) und dem ersten Poll, der den
 * neuen Scan-/Scoring-Lauf tatsaechlich bestaetigt: der Button bleibt deaktiviert, bis entweder
 * Polling running bestaetigt oder der Trigger selbst fehlschlaegt. Nur auf status==="running" zu
 * warten reicht NICHT, aus zwei Gruenden:
 *
 * 1. Bei einem bereits zuvor gelaufenen Projekt ist der beobachtete Status VOR dem Klick schon
 *    nicht-null (z.B. "failed" vom letzten Lauf) - der Worker setzt status="running" erst
 *    asynchron (backend/src/photosort/worker.py), der Invalidierungs-Refetch direkt nach der
 *    202-Antwort kann also noch den ALTEN Status liefern.
 * 2. Fast-Path: laeuft der Job im Worker so schnell durch, dass zwischen dem Setzen von
 *    status="running" und dem finalen Commit kein einziger await-Punkt liegt (z.B. Scoring bei
 *    photos_total < 25 == SCORE_COMMIT_BATCH_SIZE) - weit unter dem 2-Sekunden-Poll-Intervall.
 *    Der Zwischenzustand "running" wird dann nie beobachtet, der Status springt direkt von null
 *    auf "success"/"failed".
 *
 * Ein blosses `status !== null` reicht ebenfalls NICHT: bei einem erneuten, ebenso schnellen Lauf
 * auf einem bereits zuvor gelaufenen Projekt kann der unmittelbare Invalidierungs-Refetch noch
 * denselben (stale) Endzustand vom VORHERIGEN Lauf liefern (z.B. wieder "failed") - der wuerde
 * faelschlich als Bestaetigung des NEUEN Laufs durchgehen.
 *
 * Unterschieden wird deshalb ueber `started_at`: jeder Lauf bekommt serverseitig einen frischen
 * Zeitstempel (neue ScanRun/ScoringRun-Zeile, backend/src/photosort/worker.py). Das
 * awaiting-Flag wird zurueckgesetzt, sobald "running" beobachtet wird (kann nie ein stale Wert
 * sein, das Projekt kann nicht schon vor dem Klick "running" gewesen sein) ODER sobald ein NEUER
 * `started_at` zusammen mit einem beliebigen Endzustand (success/failed) beobachtet wird. Eine
 * Kollision zweier `started_at`-Werte ist praktisch ausgeschlossen: Postgres `func.now()` liefert
 * Mikrosekunden-Praezision.
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
    if (status === 'running' || (status !== null && isNewRun)) {
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
