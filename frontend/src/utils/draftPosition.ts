/** Die Oberkante eines Abschnitts des Album-Entwurfs und die Eventposition, für die er steht. */
export interface SectionTop {
  position: number
  top: number
}

/**
 * „Event p": der Abschnitt, dessen Oberkante zuletzt unter die Kopfleiste gelaufen ist (`top <=
 * edge`), in Dokumentreihenfolge. Vor dem ersten Abschnitt gilt Event 1. Ein zugeklappter Tag ist
 * EIN Abschnitt mit der Position seines ersten Events; Filter und Zuklappen nehmen keinen
 * Abschnitt heraus, p und E bleiben deshalb stabil.
 */
export function currentSectionPosition(sections: SectionTop[], edge: number): number {
  let position = sections[0]?.position ?? 1
  for (const section of sections) {
    if (section.top <= edge) {
      position = section.position
    }
  }
  return position
}
