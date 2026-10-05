import { describe, expect, it } from 'vitest'

import {
  CURATION_MAX_ROW_HEIGHT_PX,
  CURATION_MIN_ROW_HEIGHT_PX,
  CURATION_TARGET_ROW_HEIGHT_PX,
  HANDLES_FULL_WIDTH_PX,
  ICON_HANDLES_WIDTH_PX,
  MIN_PLANNING_RATIO,
  curationRows,
  iconOnly,
  planningRatio,
} from './curationLayout'
import type { HandlesKind } from './curationLayout'
import { FALLBACK_ASPECT_RATIO } from './justifiedRows'

describe('curationLayout: die Konstanten', () => {
  it('binds every constant once to its number', () => {
    expect(CURATION_TARGET_ROW_HEIGHT_PX).toBe(280)
    expect(CURATION_MIN_ROW_HEIGHT_PX).toBe(200)
    expect(CURATION_MAX_ROW_HEIGHT_PX).toBe(350)
    expect(ICON_HANDLES_WIDTH_PX).toBe(100)
    expect(MIN_PLANNING_RATIO).toBe(0.5)
    expect(HANDLES_FULL_WIDTH_PX).toEqual({
      draft: 208,
      struck: 146,
      candidate: 206,
      panel: 102,
      'selection-contested': 248,
      'selection-single': 124,
    })
  })
})

describe('curationLayout: das Planungsverhaeltnis', () => {
  it.each([
    [null, FALLBACK_ASPECT_RATIO],
    [0.4, 0.5],
    [0.5, 0.5],
    [9 / 16, 9 / 16],
    [3 / 2, 3 / 2],
  ])('plans %s as %s', (ratio, expected) => {
    expect(planningRatio(ratio)).toBe(expected)
  })

  it.each([NaN, Infinity, -1, 0, '1;background:url(x)'])(
    'a non-finite or non-numeric ratio falls back (%s)',
    (ratio) => {
      expect(planningRatio(ratio as unknown as number)).toBe(FALLBACK_ASPECT_RATIO)

      const rows = curationRows([ratio as unknown as number, 1.5], 1280)
      for (const row of rows) {
        for (const tile of row.tiles) {
          expect(Number.isFinite(tile.width)).toBe(true)
          expect(Number.isFinite(tile.height)).toBe(true)
        }
      }
    },
  )
})

describe('curationLayout: Symbol oder Wort', () => {
  const kinds = Object.keys(HANDLES_FULL_WIDTH_PX) as HandlesKind[]

  it.each(kinds)('switches %s to symbols strictly below its threshold', (kind) => {
    const threshold = HANDLES_FULL_WIDTH_PX[kind]

    expect(iconOnly(threshold - 1, kind)).toBe(true)
    expect(iconOnly(threshold, kind)).toBe(false)
    expect(iconOnly(threshold + 1, kind)).toBe(false)
  })
})

describe('curationLayout: die Telefonrechnung', () => {
  const PHONE_CONTENT_WIDTH = 328

  it('puts two 2:3 portraits into one row, each wide enough for two symbol handles', () => {
    const rows = curationRows([2 / 3, 2 / 3], PHONE_CONTENT_WIDTH)

    expect(rows).toHaveLength(1)
    for (const tile of rows[0].tiles) {
      expect(tile.width).toBeGreaterThanOrEqual(ICON_HANDLES_WIDTH_PX)
      expect(iconOnly(tile.width, 'draft')).toBe(true)
    }
  })

  it('lets a 3:2 landscape stand alone, with words', () => {
    const rows = curationRows([3 / 2], PHONE_CONTENT_WIDTH)

    expect(rows[0].tiles).toHaveLength(1)
    expect(iconOnly(rows[0].tiles[0].width, 'draft')).toBe(false)
  })

  it('keeps a single portrait at the target height instead of stretching it', () => {
    const rows = curationRows([2 / 3, 4], PHONE_CONTENT_WIDTH)

    expect(rows[0].height).toBe(CURATION_TARGET_ROW_HEIGHT_PX)
  })

  it('never plans a tile narrower than two symbol handles', () => {
    const rows = curationRows([0.4, 0.4, 0.4, 0.4, 0.4], 1280)

    for (const row of rows) {
      for (const tile of row.tiles) {
        expect(tile.width).toBeGreaterThanOrEqual(ICON_HANDLES_WIDTH_PX)
      }
    }
  })

  it('keeps every full row between 200 and 350 px at 1280 px', () => {
    const rows = curationRows([1.5, 2 / 3, 1.5, 1.5, 2 / 3, 9 / 16, 1.5, 1, 1.5, 2 / 3], 1280)

    for (const row of rows) {
      expect(row.height).toBeGreaterThanOrEqual(CURATION_MIN_ROW_HEIGHT_PX)
      expect(row.height).toBeLessThanOrEqual(CURATION_MAX_ROW_HEIGHT_PX)
    }
  })
})
