import { FALLBACK_ASPECT_RATIO, GRID_GAP_PX, justifiedRows, naturalTiles } from './justifiedRows'
import type { JustifiedRow } from './justifiedRows'

/**
 * Die Raster der Kuratierung (Album-Entwurf, Endauswahl, Alternativen) als justierte Reihen: jedes
 * Foto im eigenen Seitenverhaeltnis, alle Kacheln einer Reihe gleich hoch, jede volle Reihe
 * buendig mit der Containerbreite.
 */

export const CURATION_TARGET_ROW_HEIGHT_PX = 280
export const CURATION_MIN_ROW_HEIGHT_PX = 200
/** Eine volle Reihe darueber steht stattdessen wie die letzte (Zielhoehe, linksbuendig). */
export const CURATION_MAX_ROW_HEIGHT_PX = 350

/** Zwei 44px-Symbolknoepfe mit 12px Abstand - die schmalste Kachel, die beide noch traegt. */
export const ICON_HANDLES_WIDTH_PX = 100

/**
 * Das schmalste Verhaeltnis, mit dem ein Foto geplant wird. Zusammen mit der Untergrenze der
 * Reihenhoehe ist damit jede Kachel mindestens `ICON_HANDLES_WIDTH_PX` breit; ein noch
 * schmaleres Foto wird in seinem Feld eingepasst statt beschnitten.
 */
export const MIN_PLANNING_RATIO = ICON_HANDLES_WIDTH_PX / CURATION_MIN_ROW_HEIGHT_PX

/**
 * Die Breite der vollen Knopfzeile je Kachelart: Symbol 14 + Abstand 4 + Wort (Inter 600, 12px)
 * + Polsterung 2 x 8, bei zwei Knoepfen plus 12 zwischen ihnen. Ist die Kachel schmaler, zeigen
 * ALLE ihre Knoepfe nur das Symbol.
 */
export const HANDLES_FULL_WIDTH_PX = {
  draft: 208,
  struck: 146,
  candidate: 206,
  panel: 102,
  'selection-contested': 248,
  'selection-single': 124,
} as const

export type HandlesKind = keyof typeof HANDLES_FULL_WIDTH_PX

/** Reine Funktion der gerechneten Breite, ohne DOM-Messung - sonst pendelte die Zeile. Genau an
 * der Schwelle steht das Wort. */
export function iconOnly(width: number, kind: HandlesKind): boolean {
  return width < HANDLES_FULL_WIDTH_PX[kind]
}

/**
 * SICHERHEIT: Das Verhaeltnis kommt aus der API und endet als Zahl in einem Inline-Stil. Nur eine
 * endliche, positive Zahl geht in die Planung; alles andere (auch eine Zeichenkette mit
 * CSS-Anteil) faellt auf 3:2 zurueck und erreicht den Stil nie.
 */
export function planningRatio(ratio: number | null | undefined): number {
  const usable =
    typeof ratio === 'number' && Number.isFinite(ratio) && ratio > 0 ? ratio : FALLBACK_ASPECT_RATIO
  return Math.max(usable, MIN_PLANNING_RATIO)
}

/**
 * Die Reihen eines Kuratierungsrasters. Vor der ersten Messung (`containerWidth <= 0`) steht jede
 * Kachel in natuerlicher Breite auf der Zielhoehe, alle in einer Reihe - der Fluss der Liste
 * bricht sie um.
 */
export function curationRows(
  ratios: readonly (number | null)[],
  containerWidth: number,
): JustifiedRow[] {
  const planned = ratios.map(planningRatio)
  if (planned.length === 0) {
    return []
  }
  if (containerWidth <= 0) {
    return [
      {
        height: CURATION_TARGET_ROW_HEIGHT_PX,
        tiles: naturalTiles(planned, CURATION_TARGET_ROW_HEIGHT_PX),
      },
    ]
  }
  return justifiedRows({
    ratios: planned,
    containerWidth,
    gap: GRID_GAP_PX,
    targetRowHeight: CURATION_TARGET_ROW_HEIGHT_PX,
    minRowHeight: CURATION_MIN_ROW_HEIGHT_PX,
    maxRowHeight: CURATION_MAX_ROW_HEIGHT_PX,
  })
}
