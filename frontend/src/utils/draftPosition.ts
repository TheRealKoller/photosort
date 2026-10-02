/** Die Oberkante eines Abschnitts des Album-Entwurfs und die Eventposition, für die er steht. */
export interface SectionTop {
  position: number
  top: number
  /** Wo ein Sprung (Fokus-Scroll, `scrollIntoView`) die Oberkante absetzt: sein `scroll-margin-top`. */
  landing?: number
}

/**
 * „Event p": der Abschnitt, dessen Oberkante zuletzt unter die Kopfleiste gelaufen ist (`top <=
 * edge`), in Dokumentreihenfolge. Vor dem ersten Abschnitt gilt Event 1. Ein zugeklappter Tag ist
 * EIN Abschnitt mit der Position seines ersten Events; Filter und Zuklappen nehmen keinen
 * Abschnitt heraus, p und E bleiben deshalb stabil.
 *
 * Ein angesprungener Abschnitt steht an seinem Landeplatz, und der kann einige Pixel unter der
 * Leiste enden. Er gilt dort schon als aktuell - sonst nennte die Leiste nach dem Sprung das
 * vorige Event. Ein Landeplatz über der Leiste verschiebt die Kante nie nach oben. Am Landeplatz
 * gilt ein Pixel Spiel: Der Browser setzt die Oberkante dorthin mit Bruchteilen daneben.
 */
export function currentSectionPosition(sections: SectionTop[], edge: number): number {
  let position = sections[0]?.position ?? 1
  for (const section of sections) {
    const landing = section.landing === undefined ? edge : section.landing + LANDING_SUBPIXEL
    if (section.top <= Math.max(edge, landing)) {
      position = section.position
    }
  }
  return position
}

/** Bruchteil-Pixel, um die ein Sprung den Abschnitt neben seinem `scroll-margin` absetzt. */
const LANDING_SUBPIXEL = 1
