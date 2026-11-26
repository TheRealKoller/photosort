import { planningRatio } from './curationLayout'
import { GRID_GAP_PX, justifiedRows, naturalTiles } from './justifiedRows'
import type { JustifiedRow } from './justifiedRows'

/**
 * Das Raster der Vergleichsansicht einer Duplikat-Gruppe als justierte Reihen: jede Aufnahme im
 * eigenen Seitenverhaeltnis und unbeschnitten, alle Bildflaechen einer
 * Reihe gleich hoch, jede volle Reihe buendig mit der Liste.
 *
 * Anders als in der Kuratierung traegt jede Kachel einen waagerechten Rand um die Bildflaeche.
 * `justifiedRows` bleibt dafuer ungeaendert: Es plant die BILDFLAECHEN mit einem um den Rand
 * vergroesserten Zwischenraum auf einer um einen Rand verkleinerten Breite. Fuer eine volle Reihe
 * mit n Kacheln gilt dann Σb + (n−1)(12+20) = W − 20, also Σ(b+20) + (n−1)·12 = W.
 */

export const DUPLICATE_TARGET_ROW_HEIGHT_PX = 280
/** Gilt fuer Reihen mit mehr als einem Bild; zusammen mit der Mindestbreite bleibt 9:16 unverzerrt. */
export const DUPLICATE_MIN_ROW_HEIGHT_PX = 200
/** Eine volle Reihe darueber steht stattdessen wie die letzte (Zielhoehe, linksbuendig). */
export const DUPLICATE_MAX_ROW_HEIGHT_PX = 350

/**
 * Der waagerechte Kachelrand: 2 × (`px-2` 8 + `border-2` 2). ZWEI WAHRHEITEN DESSELBEN WERTS wie
 * bei `GRID_GAP_PX` - die Kachel in `DuplicatePhotoTile` traegt `px-2` an ALLEN Breiten, und der
 * Vertragstest haelt beide aneinander fest. Ein `sm:px-3` liesse jede volle Reihe ueberlaufen.
 */
export const DUPLICATE_TILE_INSET_X_PX = 20

/** Die breiteste einzelne Wahlschaltflaeche (gedrueckt „Ausschuss", ≈ 101 px) plus Reserve. */
export const DUPLICATE_MIN_IMAGE_WIDTH_PX = 112

/** Schmaler wird nicht geplant: 112 / 200. Liegt unter 9:16, also bleiben uebliche Hochformate
 * unverzerrt; ein noch schmaleres steht eingepasst im Feld. */
export const DUPLICATE_MIN_PLANNING_RATIO =
  DUPLICATE_MIN_IMAGE_WIDTH_PX / DUPLICATE_MIN_ROW_HEIGHT_PX

/** Breiter wird nicht geplant: (360 − 2·16 − 20) / 44. Damit ist eine Bildflaeche auch allein an
 * der schmalsten Breite mindestens 44 px hoch. */
export const DUPLICATE_MAX_PLANNING_RATIO = 7

/**
 * SICHERHEIT: Das Verhaeltnis kommt aus der API und endet als Zahl in Inline-Stilen. Es geht nur
 * ueber `planningRatio` hinein - alles andere als eine endliche, positive Zahl faellt auf 3:2 -
 * und wird dann auf das Band 0,56 bis 7 begrenzt.
 */
export function duplicatePlanningRatio(ratio: number | null | undefined): number {
  return Math.min(
    Math.max(planningRatio(ratio), DUPLICATE_MIN_PLANNING_RATIO),
    DUPLICATE_MAX_PLANNING_RATIO,
  )
}

/**
 * Die Reihen des Rasters; Breite und Hoehe jeder Kachel sind die der BILDFLAECHE, die Kachel ist
 * `DUPLICATE_TILE_INSET_X_PX` breiter. Vor der ersten Messung (`containerWidth <= 0`) steht jede
 * Bildflaeche in natuerlicher Breite auf der Zielhoehe, alle in einer Reihe - der Fluss der Liste
 * bricht sie um.
 */
export function duplicateGridRows(
  ratios: readonly (number | null)[],
  containerWidth: number,
): JustifiedRow[] {
  const planned = ratios.map(duplicatePlanningRatio)
  if (planned.length === 0) {
    return []
  }
  if (containerWidth <= 0) {
    return [
      {
        height: DUPLICATE_TARGET_ROW_HEIGHT_PX,
        tiles: naturalTiles(planned, DUPLICATE_TARGET_ROW_HEIGHT_PX),
      },
    ]
  }
  return justifiedRows({
    ratios: planned,
    containerWidth: containerWidth - DUPLICATE_TILE_INSET_X_PX,
    gap: GRID_GAP_PX + DUPLICATE_TILE_INSET_X_PX,
    targetRowHeight: DUPLICATE_TARGET_ROW_HEIGHT_PX,
    minRowHeight: DUPLICATE_MIN_ROW_HEIGHT_PX,
    maxRowHeight: DUPLICATE_MAX_ROW_HEIGHT_PX,
  })
}
