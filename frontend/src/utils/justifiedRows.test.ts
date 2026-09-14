import { describe, expect, it } from 'vitest'

import {
  FALLBACK_ASPECT_RATIO,
  GRID_GAP_PX,
  MIN_ROW_HEIGHT_PX,
  TARGET_ROW_HEIGHT_PX,
  justifiedRows,
} from './justifiedRows'

/*
 * specs/features/0489-fotouebersicht-ohne-beschnitt.md, AK2: Die reine Funktion traegt die vier
 * Zusagen "kein Beschnitt", "gemeinsame Zeilenhoehe", "buendiges Zeilenende" und "Rundungsrest auf
 * dem letzten Bild" allein - ohne DOM, ohne Breitenmessung, ohne Komponente.
 */

const WIDTH = 1000

function rowsOf(
  ratios: readonly (number | null)[],
  overrides: Partial<Parameters<typeof justifiedRows>[0]> = {},
) {
  return justifiedRows({
    ratios,
    containerWidth: WIDTH,
    gap: GRID_GAP_PX,
    targetRowHeight: TARGET_ROW_HEIGHT_PX,
    minRowHeight: MIN_ROW_HEIGHT_PX,
    ...overrides,
  })
}

function lineWidth(row: { tiles: { width: number }[] }, gap = GRID_GAP_PX): number {
  const images = row.tiles.reduce((sum, tile) => sum + tile.width, 0)
  return images + gap * (row.tiles.length - 1)
}

describe('justifiedRows', () => {
  it('fills a full row exactly to the container width, gaps included', () => {
    // Acht gleiche Querformate brechen bei 1000px sicher mehr als eine Zeile um.
    const rows = rowsOf(Array.from({ length: 8 }, () => 1.5))

    expect(rows.length).toBeGreaterThan(1)
    for (const row of rows.slice(0, -1)) {
      expect(lineWidth(row)).toBe(WIDTH)
    }
  })

  it('gives every image of a row the same height', () => {
    const rows = rowsOf([1.5, 0.75, 2.4, 1, 1.5, 0.66, 3, 1.2])

    for (const row of rows) {
      for (const tile of row.tiles) {
        expect(tile.height).toBe(row.height)
      }
    }
  })

  it.each([
    {
      name: 'eine nicht glatt aufgehende Breite',
      ratios: [1.7, 1.3, 0.9, 2.5, 3, 1.1],
      width: 1001,
    },
    {
      name: 'zehn gleiche Verhaeltnisse',
      ratios: Array.from({ length: 10 }, () => 1),
      width: 1000,
    },
  ])('puts the rounding remainder on the last image ($name)', ({ ratios, width }) => {
    // Die Zeile ist voll, sobald sie die Zielhoehe unterschreitet; die kleine Zielhoehe laesst
    // alle Bilder garantiert in EINE volle Zeile fallen.
    const rows = justifiedRows({
      ratios,
      containerWidth: width,
      gap: GRID_GAP_PX,
      targetRowHeight: 100,
      minRowHeight: 40,
    })

    expect(rows).toHaveLength(1)
    expect(rows[0].tiles).toHaveLength(ratios.length)
    expect(lineWidth(rows[0])).toBe(width)
  })

  it('does not stretch the last, incomplete row', () => {
    const rows = rowsOf([1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5])
    const last = rows[rows.length - 1]

    expect(last.height).toBe(TARGET_ROW_HEIGHT_PX)
    expect(lineWidth(last)).toBeLessThan(WIDTH)
  })

  it('leaves a single image unstretched instead of blowing it up to full width', () => {
    // "Sonst entstuende aus einem einzelnen Restbild eine bildschirmhohe Kachel."
    const rows = rowsOf([1.5])

    expect(rows).toHaveLength(1)
    expect(rows[0].height).toBe(TARGET_ROW_HEIGHT_PX)
    expect(rows[0].tiles[0].width).toBe(Math.round(1.5 * TARGET_ROW_HEIGHT_PX))
  })

  it('plans an unknown ratio as 3:2 instead of dropping the image', () => {
    const rows = rowsOf([null])

    expect(FALLBACK_ASPECT_RATIO).toBe(3 / 2)
    expect(rows[0].tiles[0].width).toBe(Math.round(FALLBACK_ASPECT_RATIO * TARGET_ROW_HEIGHT_PX))
  })

  it('keeps every image, in order, exactly once', () => {
    const rows = rowsOf([1.5, 0.75, 2.4, null, 1.5, 0.66, 3, 1.2, 1.1, 0.8])

    const indices = rows.flatMap((row) => row.tiles.map((tile) => tile.index))
    expect(indices).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
  })

  it('never produces a width of zero or less', () => {
    const rows = rowsOf([0.05, 20, 0.05, 20, 1, 1, 1, 1])

    for (const row of rows) {
      for (const tile of row.tiles) {
        expect(tile.width).toBeGreaterThan(0)
      }
    }
  })

  describe('die Untergrenze der Zeilenhoehe', () => {
    it('breaks the row earlier instead of squashing it below the minimum', () => {
      // Ohne Untergrenze zoege das Panorama die ganze Zeile auf eine unbrauchbare Hoehe - nicht
      // nur sich selbst.
      const ratios = [1.5, 1.5, 12]

      const withMinimum = rowsOf(ratios)
      const withoutMinimum = rowsOf(ratios, { minRowHeight: 1 })

      expect(withMinimum).toHaveLength(2)
      expect(withMinimum[0].tiles.map((tile) => tile.index)).toEqual([0, 1])
      expect(withoutMinimum).toHaveLength(1)
      expect(withoutMinimum[0].height).toBeLessThan(MIN_ROW_HEIGHT_PX)
    })

    it('keeps every full row of more than one image at or above the minimum height', () => {
      const rows = rowsOf([1.5, 1.5, 12, 1, 0.7, 8, 1.4])

      const fullRows = rows.slice(0, -1)
      expect(fullRows.length).toBeGreaterThan(0)
      for (const row of fullRows.filter((row) => row.tiles.length > 1)) {
        expect(row.height).toBeGreaterThanOrEqual(MIN_ROW_HEIGHT_PX)
      }
    })

    it('accepts a single image that alone falls below the minimum', () => {
      // Ein Bild allein hat keine Nachbarn, die es hochziehen koennten. Die Untergrenze gilt
      // deshalb ausdruecklich nur fuer Zeilen mit mehr als einem Bild - andernfalls fiele eine
      // Panoramaaufnahme aus der Liste, statt bloss flach zu sein.
      const rows = rowsOf([20, 1.5, 1.5, 1.5, 1.5])

      const indices = rows.flatMap((row) => row.tiles.map((tile) => tile.index))
      expect(indices).toContain(0)
      const panorama = rows.find((row) => row.tiles.some((tile) => tile.index === 0))
      expect(panorama?.tiles).toHaveLength(1)
      expect(panorama?.height).toBeLessThan(MIN_ROW_HEIGHT_PX)
    })
  })

  describe('die Randfaelle der Eingabe', () => {
    it('returns no row for an empty input', () => {
      expect(rowsOf([])).toEqual([])
    })

    it.each([0, -50])('returns no row for a container width of %s', (containerWidth) => {
      // Statt NaN: In jsdom und im ersten Bild vor der ersten Messung ist die Breite 0.
      expect(rowsOf([1.5, 1.5], { containerWidth })).toEqual([])
    })

    it('produces no NaN anywhere', () => {
      const rows = rowsOf([1.5, null, 0.75, 2.4, 1, 1, 1, 1, 1])

      for (const row of rows) {
        expect(Number.isFinite(row.height)).toBe(true)
        for (const tile of row.tiles) {
          expect(Number.isFinite(tile.width)).toBe(true)
          expect(Number.isFinite(tile.height)).toBe(true)
        }
      }
    })

    it.each([Number.NaN, Number.POSITIVE_INFINITY, 0, -1])(
      'treats the unusable ratio %s like an unknown one',
      (ratio) => {
        // Der Server laesst ein entartetes Verhaeltnis gar nicht erst in die Spalte (Auflage S5).
        // Die Ausfallrichtung steht hier trotzdem: Eine einzige unbrauchbare Zahl darf nicht die
        // Hoehe einer ganzen Zeile entwerten.
        const rows = rowsOf([ratio])

        expect(rows[0].tiles[0].width).toBe(
          Math.round(FALLBACK_ASPECT_RATIO * TARGET_ROW_HEIGHT_PX),
        )
      },
    )
  })

  describe('die Konstanten', () => {
    it('names a gap that matches the utility the grid uses', () => {
      // "Zwei Wahrheiten desselben Werts": Der Zwischenraum ist eine Utility der 8-Punkt-Skala
      // (`gap-3` = 12px) UND eine Zahl in der Rechnung. Der Vertragstest haelt die Utility
      // zusaetzlich am Markup fest.
      expect(GRID_GAP_PX).toBe(12)
    })

    it('keeps the minimum below the target height', () => {
      expect(MIN_ROW_HEIGHT_PX).toBeLessThan(TARGET_ROW_HEIGHT_PX)
    })
  })
})
