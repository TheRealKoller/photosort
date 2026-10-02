import { useEffect, useState } from 'react'
import type { RefObject } from 'react'

import { currentSectionPosition } from '../utils/draftPosition'

export type ObserverFactory = (callback: () => void) => {
  observe: (target: Element) => void
  disconnect: () => void
}

const defaultObserver: ObserverFactory = (callback) =>
  new IntersectionObserver(callback, { threshold: [0, 1] })

/**
 * „Event p" der mitlaufenden Kopfleiste: Jeder Eventabschnitt (und jeder zugeklappte Tag) trägt
 * `data-draft-position`; bei jeder Meldung des Beobachters wird aus den Oberkanten und der
 * Unterkante der Leiste neu bestimmt (`currentSectionPosition`). Der Beobachter ist injizierbar,
 * jsdom kennt keinen. `layoutKey` wechselt, wenn Abschnitte entstehen oder verschwinden.
 */
export function useDraftPosition(
  containerRef: RefObject<HTMLElement | null>,
  barRef: RefObject<HTMLElement | null>,
  layoutKey: string,
  createObserver: ObserverFactory = defaultObserver,
): number {
  const [position, setPosition] = useState(1)

  useEffect(() => {
    const container = containerRef.current
    if (
      container === null ||
      (createObserver === defaultObserver && typeof IntersectionObserver === 'undefined')
    ) {
      return
    }
    const sections = [...container.querySelectorAll<HTMLElement>('[data-draft-position]')]
    const update = () => {
      const edge = barRef.current?.getBoundingClientRect().bottom ?? 0
      setPosition(
        currentSectionPosition(
          sections.map((section) => ({
            position: Number(section.dataset.draftPosition),
            top: section.getBoundingClientRect().top,
          })),
          edge,
        ),
      )
    }
    const observer = createObserver(update)
    for (const section of sections) {
      observer.observe(section)
    }
    window.addEventListener('scroll', update, { passive: true })
    update()
    return () => {
      observer.disconnect()
      window.removeEventListener('scroll', update)
    }
  }, [containerRef, barRef, layoutKey, createObserver])

  return position
}
