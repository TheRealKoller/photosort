import { act, renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { ProcessStatus } from '../utils/processStatus'
import { POLL_INTERVAL_MS } from './useProjects'
import { useTriggerConfirmation } from './useTriggerConfirmation'

// Volle Zustandsmatrix an EINER Stelle bewiesen (specs/architecture/0002-testkonzept.md,
// Abschnitt "Mehrschritt-Routing", Punkt 4) - ersetzt die bisher dreifach (Scan/Ausschuss-
// Erkennung/Kriterien-Bewertung) indirekt ueber volle ProjectDetailPage-Integrationstests
// bewiesene Logik. Die fuenf neuen Detailseiten behalten dafuer nur noch einen schlanken
// Wiring-Nachweis (siehe *StepPage.test.tsx).
function setup(initialStatus: ProcessStatus | null, initialStartedAt: string | null) {
  const refetch = vi.fn()
  const hook = renderHook(
    ({ status, startedAt }: { status: ProcessStatus | null; startedAt: string | null }) =>
      useTriggerConfirmation(status, startedAt, refetch),
    { initialProps: { status: initialStatus, startedAt: initialStartedAt } }
  )
  return { ...hook, refetch }
}

describe('useTriggerConfirmation', () => {
  it('starts with awaiting=false', () => {
    const { result } = setup(null, null)

    expect(result.current[0]).toBe(false)
  })

  it('sets awaiting=true synchronously when triggered (click)', () => {
    const { result } = setup(null, null)

    act(() => result.current[1](true))

    expect(result.current[0]).toBe(true)
  })

  it('resets awaiting to false as soon as "running" is observed', () => {
    const { result, rerender } = setup(null, null)
    act(() => result.current[1](true))

    rerender({ status: 'running', startedAt: null })

    expect(result.current[0]).toBe(false)
  })

  it(
    'resets awaiting to false on a fast-path terminal status with a fresh started_at, ' +
      'without ever observing "running" (specs/features/0017)',
    () => {
      const { result, rerender } = setup(null, null)
      act(() => result.current[1](true))

      rerender({ status: 'success', startedAt: '2026-07-20T10:00:01Z' })

      expect(result.current[0]).toBe(false)
    }
  )

  it(
    'keeps awaiting=true when the observed status/started_at is still the stale value from a ' +
      'PREVIOUS run (started_at unchanged from the baseline captured at click time)',
    () => {
      const staleStartedAt = '2026-07-20T09:00:00Z'
      const { result, rerender } = setup('failed', staleStartedAt)
      act(() => result.current[1](true))

      // Der invalidierte Refetch direkt nach dem Trigger liefert noch denselben (stale)
      // Endzustand vom VORHERIGEN Lauf - started_at unveraendert gegenueber der beim Klick
      // eingefrorenen Baseline.
      rerender({ status: 'failed', startedAt: staleStartedAt })

      expect(result.current[0]).toBe(true)
    }
  )

  it('polls via refetch every POLL_INTERVAL_MS while awaiting stays true', () => {
    vi.useFakeTimers()
    try {
      const staleStartedAt = '2026-07-20T09:00:00Z'
      const { result, rerender, refetch } = setup('failed', staleStartedAt)
      act(() => result.current[1](true))
      rerender({ status: 'failed', startedAt: staleStartedAt })

      expect(refetch).not.toHaveBeenCalled()
      act(() => {
        vi.advanceTimersByTime(POLL_INTERVAL_MS)
      })
      expect(refetch).toHaveBeenCalledTimes(1)
    } finally {
      vi.useRealTimers()
    }
  })

  it('stops polling once awaiting becomes false again (no leaked interval)', () => {
    vi.useFakeTimers()
    try {
      const { result, rerender, refetch } = setup(null, null)
      act(() => result.current[1](true))
      rerender({ status: 'running', startedAt: null })

      expect(result.current[0]).toBe(false)
      act(() => {
        vi.advanceTimersByTime(POLL_INTERVAL_MS * 3)
      })
      expect(refetch).not.toHaveBeenCalled()
    } finally {
      vi.useRealTimers()
    }
  })
})
