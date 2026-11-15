import { describe, expect, it } from 'vitest'

import {
  DUPLICATE_MAX_PLANNING_RATIO,
  DUPLICATE_MAX_ROW_HEIGHT_PX,
  DUPLICATE_MIN_IMAGE_WIDTH_PX,
  DUPLICATE_MIN_PLANNING_RATIO,
  DUPLICATE_MIN_ROW_HEIGHT_PX,
  DUPLICATE_TARGET_ROW_HEIGHT_PX,
  DUPLICATE_TILE_INSET_X_PX,
  duplicateGridRows,
  duplicatePlanningRatio,
} from './duplicateLayout'
import { FALLBACK_ASPECT_RATIO, GRID_GAP_PX } from './justifiedRows'
import type { JustifiedRow } from './justifiedRows'

/** Die aeussere Breite einer Zeile: Kacheln samt Rand plus die Zwischenraeume der Liste. */
function outerWidth(row: JustifiedRow): number {
  return (
    row.tiles.reduce((sum, tile) => sum + tile.width + DUPLICATE_TILE_INSET_X_PX, 0) +
    (row.tiles.length - 1) * GRID_GAP_PX
  )
}

describe('duplicateLayout: die Konstanten', () => {
  it('binds every constant once to its number', () => {
    expect(DUPLICATE_TARGET_ROW_HEIGHT_PX).toBe(280)
    expect(DUPLICATE_MIN_ROW_HEIGHT_PX).toBe(200)
    expect(DUPLICATE_MAX_ROW_HEIGHT_PX).toBe(350)
    expect(DUPLICATE_TILE_INSET_X_PX).toBe(20)
    expect(DUPLICATE_MIN_IMAGE_WIDTH_PX).toBe(112)
    expect(DUPLICATE_MIN_PLANNING_RATIO).toBe(0.56)
    expect(DUPLICATE_MAX_PLANNING_RATIO).toBe(7)
  })
})

describe('duplicateLayout: das Planungsverhaeltnis', () => {
  it.each([
    [null, FALLBACK_ASPECT_RATIO],
    [0.5, 0.56],
    [0.56, 0.56],
    [9 / 16, 9 / 16],
    [3 / 2, 3 / 2],
    [7, 7],
    [20, 7],
  ])('plans %s as %s', (ratio, expected) => {
    expect(duplicatePlanningRatio(ratio)).toBe(expected)
  })

  it.each([NaN, Infinity, -1, 0, '1;background:url(x)'])(
    'a hostile or unusable ratio falls back to 3:2 and never reaches a style (%s)',
    (ratio) => {
      expect(duplicatePlanningRatio(ratio as unknown as number)).toBe(FALLBACK_ASPECT_RATIO)

      for (const width of [0, 328, 976]) {
        const rows = duplicateGridRows([ratio as unknown as number, 1.5], width)
        for (const row of rows) {
          for (const tile of row.tiles) {
            expect(typeof tile.width).toBe('number')
            expect(Number.isFinite(tile.width)).toBe(true)
            expect(Number.isFinite(tile.height)).toBe(true)
            const style = `${tile.width}px ${tile.height}px`
            expect(style).not.toContain('url(')
            expect(style).not.toContain(';')
            expect(style).not.toContain('background')
          }
        }
      }
    },
  )
})

describe('duplicateLayout: das Zeilenraster', () => {
  it('closes a full row flush with the list at 976 px', () => {
    const rows = duplicateGridRows([4 / 3, 4 / 3, 4 / 3, 4 / 3, 1], 976)

    expect(rows[0].tiles).toHaveLength(3)
    expect(outerWidth(rows[0])).toBe(976)
  })

  it('closes a single image flush with the list at 328 px', () => {
    const rows = duplicateGridRows([1.5, 1.5], 328)

    expect(rows).toHaveLength(2)
    for (const row of rows) {
      expect(outerWidth(row)).toBe(328)
    }
  })

  it('closes every full row flush at a width that does not divide evenly', () => {
    const rows = duplicateGridRows([1.5, 1, 0.75, 2.4, 1.5, 1.5], 701)

    expect(rows).toHaveLength(3)
    for (const row of rows) {
      expect(outerWidth(row)).toBe(701)
    }
  })

  it('gives every tile of a row the same height, the last row the target height', () => {
    const rows = duplicateGridRows([4 / 3, 4 / 3, 4 / 3, 4 / 3, 1], 976)

    for (const row of rows) {
      for (const tile of row.tiles) {
        expect(tile.height).toBe(row.height)
      }
    }
    const last = rows[rows.length - 1]
    expect(last.height).toBe(DUPLICATE_TARGET_ROW_HEIGHT_PX)
    expect(outerWidth(last)).toBeLessThan(976)
  })

  it('sets a row that would be taller than the maximum like the last row', () => {
    // 0,56 allein waere bei 308 px buendig 550 px hoch; das 3:2 dahinter drueckte unter 200.
    const rows = duplicateGridRows([0.56, 1.5], 328)

    expect(rows[0].tiles).toHaveLength(1)
    expect(rows[0].height).toBe(DUPLICATE_TARGET_ROW_HEIGHT_PX)
    expect(rows[0].tiles[0].width).toBe(Math.round(0.56 * DUPLICATE_TARGET_ROW_HEIGHT_PX))
    expect(outerWidth(rows[0])).toBeLessThan(328)
  })

  it('plans natural widths at the target height before the first measurement', () => {
    const rows = duplicateGridRows([4 / 3, null, 20], 0)

    expect(rows).toHaveLength(1)
    expect(rows[0].tiles).toEqual([
      { index: 0, width: Math.round((4 / 3) * 280), height: 280 },
      { index: 1, width: 420, height: 280 },
      { index: 2, width: 1960, height: 280 },
    ])
  })

  it('returns no rows for an empty group', () => {
    expect(duplicateGridRows([], 976)).toEqual([])
    expect(duplicateGridRows([], 0)).toEqual([])
  })
})

describe('duplicateLayout: die Untergrenzen', () => {
  const MIXES: (number | null)[][] = [
    [0.5, 0.5, 0.5, 0.5],
    [0.56, 0.56, 0.56],
    [0.75, 0.75, 0.75, 0.75, 0.75],
    [1, 1, 1, 1],
    [2.4, 2.4, 2.4],
    [7, 7],
    [20],
    [null, null, null, null],
    [0.5, 0.56, 0.75, 1, 2.4, 7, 20, null],
    [null, 4 / 3, 0.75, 2.4, 1, 0.56, 20, 0.5, 1.5],
  ]
  const WIDTHS = [328, 700, 976]

  const cases = MIXES.flatMap((ratios) => WIDTHS.map((width) => [ratios, width] as const))

  it.each(cases)('holds every lower bound for %j at %i px', (ratios, width) => {
    const rows = duplicateGridRows(ratios, width)
    const indices = rows.flatMap((row) => row.tiles.map((tile) => tile.index))

    expect(indices).toEqual(ratios.map((_, index) => index))
    for (const row of rows) {
      for (const tile of row.tiles) {
        expect(tile.width + DUPLICATE_TILE_INSET_X_PX).toBeGreaterThanOrEqual(130)
        expect(tile.width + DUPLICATE_TILE_INSET_X_PX).toBeLessThanOrEqual(width)
        expect(tile.height).toBeGreaterThanOrEqual(44)
      }
    }
  })
})

describe('duplicateLayout: Pflichtfaelle', () => {
  it('places a group of two side by side on the desktop', () => {
    const rows = duplicateGridRows([4 / 3, 3 / 4], 976)

    expect(rows).toHaveLength(1)
    expect(rows[0].tiles).toHaveLength(2)
  })

  it('stretches a single wide image to the list width', () => {
    const rows = duplicateGridRows([4], 976)

    expect(rows[0].tiles[0].width).toBe(976 - DUPLICATE_TILE_INSET_X_PX)
  })

  it('sets a single image that would be taller than the maximum at the target height', () => {
    const rows = duplicateGridRows([1.5], 976)

    expect(rows[0].height).toBe(DUPLICATE_TARGET_ROW_HEIGHT_PX)
    expect(rows[0].tiles[0].width).toBe(420)
  })

  it('puts two portraits with a ratio sum up to 1.38 side by side at 328 px', () => {
    const rows = duplicateGridRows([9 / 16, 3 / 4], 328)

    expect(rows).toHaveLength(1)
    expect(rows[0].tiles).toHaveLength(2)
    expect(outerWidth(rows[0])).toBe(328)
  })

  it('breaks two portraits just above 1.38 into two rows at 328 px', () => {
    const rows = duplicateGridRows([3 / 4, 3 / 4], 328)

    expect(rows).toHaveLength(2)
  })

  it('keeps a lone panorama at least 44 px high at 328 px', () => {
    const rows = duplicateGridRows([20], 328)

    expect(rows[0].tiles[0].height).toBeGreaterThanOrEqual(44)
    expect(outerWidth(rows[0])).toBe(328)
  })
})
