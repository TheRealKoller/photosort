/**
 * Die zwei festen Viewport-Projekte (ADR 0057 Punkt 7). `mobile` ist die schmalste im
 * Testkonzept dokumentierte Breite, an der "kein horizontales Scrollen" zugesichert ist.
 *
 * Die Breakpoint-Leiter des Foto-Grids (grid-cols-2 sm:grid-cols-3 md:grid-cols-4) ist mit diesen
 * beiden Breiten NICHT vollstaendig sichtbar - der Wechsel 2 -> 3 liegt dazwischen. Der
 * `grid-columns`-Spec setzt seine Breiten deshalb selbst (Edge Case E1) und ist an genau ein
 * Projekt gebunden, sonst liefe er doppelt mit identischem Ergebnis.
 */

export interface ViewportSize {
  width: number
  height: number
}

export const VIEWPORTS = {
  mobile: { width: 360, height: 740 },
  desktop: { width: 1280, height: 800 },
} as const satisfies Record<string, ViewportSize>

export type ViewportName = keyof typeof VIEWPORTS

export function isViewportName(value: string): value is ViewportName {
  return Object.prototype.hasOwnProperty.call(VIEWPORTS, value)
}

export const VIEWPORT_NAMES = Object.keys(VIEWPORTS) as ViewportName[]
