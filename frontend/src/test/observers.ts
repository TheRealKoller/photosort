import { act } from '@testing-library/react'
import { vi } from 'vitest'

/*
 * TREIBBARE Attrappen fuer `ResizeObserver` und `IntersectionObserver`.
 *
 * jsdom kennt beide nicht (specs/architecture/0002-testkonzept.md). Eine No-op-Attrappe nach dem
 * `matchMedia`-Muster reicht hier NICHT: Beide Beobachter sind der einzige Weg, auf dem die
 * gemessene Containerbreite bzw. das Nachladen ueberhaupt ausgeloest wird. Eine Attrappe, die den
 * Rueckruf nie aufruft, macht jede daran haengende Zusage unpruefbar - und einen gruenen Test, der
 * nichts aussagt.
 *
 * `clientWidth` und `getBoundingClientRect().width` sind in jsdom konstant 0. Die Breite wird
 * deshalb IN DEN TEST HINEINGEGEBEN statt aus dem DOM gelesen; daraus folgt die Bauvorgabe an den
 * Produktivcode, dass `useElementWidth` sie aus dem Beobachter-Eintrag nimmt.
 */

type ResizeCallback = (entries: ResizeObserverEntry[], observer: ResizeObserver) => void
type IntersectionCallback = (
  entries: IntersectionObserverEntry[],
  observer: IntersectionObserver,
) => void

export interface ResizeObserverHarness {
  /** Meldet allen beobachteten Elementen die angegebene Breite. */
  resizeTo(width: number): void
  /** Wie viele Elemente gerade beobachtet werden - 0 nach dem Abbau. */
  observedCount(): number
}

export interface IntersectionObserverHarness {
  /** Meldet allen beobachteten Elementen den Sichtbarkeitszustand. */
  setIntersecting(isIntersecting: boolean): void
  observedCount(): number
}

/** Setzt eine treibbare `ResizeObserver`-Attrappe als globales Symbol. `vi.unstubAllGlobals()`
 * in einem `afterEach` raeumt sie wieder ab. */
export function installResizeObserver(): ResizeObserverHarness {
  const entries = new Map<Element, ResizeCallback>()
  const instances: ResizeObserver[] = []

  class FakeResizeObserver {
    readonly callback: ResizeCallback
    constructor(callback: ResizeCallback) {
      this.callback = callback
      instances.push(this as unknown as ResizeObserver)
    }
    observe(target: Element): void {
      entries.set(target, this.callback)
    }
    unobserve(target: Element): void {
      entries.delete(target)
    }
    disconnect(): void {
      for (const [target, callback] of entries) {
        if (callback === this.callback) {
          entries.delete(target)
        }
      }
    }
  }

  vi.stubGlobal('ResizeObserver', FakeResizeObserver)

  return {
    resizeTo(width: number): void {
      act(() => {
        for (const [target, callback] of [...entries]) {
          const entry = {
            target,
            contentRect: { width, height: 0, top: 0, left: 0, right: width, bottom: 0, x: 0, y: 0 },
          } as unknown as ResizeObserverEntry
          callback([entry], instances[0])
        }
      })
    },
    observedCount: () => entries.size,
  }
}

/** Setzt eine treibbare `IntersectionObserver`-Attrappe als globales Symbol. */
export function installIntersectionObserver(): IntersectionObserverHarness {
  const entries = new Map<Element, IntersectionCallback>()
  const instances: IntersectionObserver[] = []

  class FakeIntersectionObserver {
    readonly root = null
    readonly rootMargin = ''
    readonly thresholds: readonly number[] = []
    readonly callback: IntersectionCallback
    constructor(callback: IntersectionCallback) {
      this.callback = callback
      instances.push(this as unknown as IntersectionObserver)
    }
    observe(target: Element): void {
      entries.set(target, this.callback)
    }
    unobserve(target: Element): void {
      entries.delete(target)
    }
    disconnect(): void {
      for (const [target, callback] of entries) {
        if (callback === this.callback) {
          entries.delete(target)
        }
      }
    }
    takeRecords(): IntersectionObserverEntry[] {
      return []
    }
  }

  vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver)

  return {
    setIntersecting(isIntersecting: boolean): void {
      act(() => {
        for (const [target, callback] of [...entries]) {
          const entry = {
            target,
            isIntersecting,
            intersectionRatio: isIntersecting ? 1 : 0,
          } as unknown as IntersectionObserverEntry
          callback([entry], instances[0])
        }
      })
    },
    observedCount: () => entries.size,
  }
}
