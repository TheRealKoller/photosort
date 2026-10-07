import { vi } from 'vitest'

/**
 * Gezielter Stub fuer `Element.matches(':focus-visible')` (Spec 0585, Testkonzept).
 *
 * jsdom hat keine Zeiger-Heuristik und wertet `:focus-visible` nicht wie ein Browser aus. Alle
 * anderen Selektoren gehen an die echte Implementierung. Die Rueckgabe steuert, ob der folgende
 * Fokus als Tastaturfokus (`true`) oder als Fokus nach Tippen/Klick bzw. programmatischer
 * Rueckgabe (`false`) gilt. Jeder Fokusfall gehoert in BEIDE Haelften der Partition - nur so ist
 * "Filter wirkt" von "Fokus wird ignoriert" unterscheidbar. Zurueckgesetzt per
 * `vi.restoreAllMocks()`.
 */
export function stubFocusVisible(focusVisible: boolean): void {
  const original = Element.prototype.matches
  vi.spyOn(Element.prototype, 'matches').mockImplementation(function (this: Element, selector) {
    return selector === ':focus-visible' ? focusVisible : original.call(this, selector)
  })
}
