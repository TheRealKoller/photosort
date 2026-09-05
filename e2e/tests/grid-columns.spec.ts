/**
 * CSS-Grid-Spaltenzahl ueber die volle Breakpoint-Leiter.
 *
 * Diese Zusage war bis zur Einfuehrung dieser Ebene "manueller visueller Smoke-Test vor Merge":
 * jsdom hat keine Layout-Engine, `grid-cols-2 sm:grid-cols-3 md:grid-cols-4` ist dort eine
 * Zeichenkette in einem `class`-Attribut und keine Geometrie. Der Spec dupliziert die bestehende
 * jsdom-Zusicherung nicht - die prueft die DOM-Gruppierung, dieser hier ausschliesslich die
 * gemessene Geometrie.
 *
 * EIGENE VIEWPORT-BREITEN (Edge Case E1 der Spec 0174): Die beiden Projekt-Viewports (360, 1280)
 * zeigen den Wechsel 2 -> 3 gar nicht - er liegt am `sm:`-Breakpoint dazwischen. Der Spec setzt
 * seine drei Breiten deshalb selbst und ist in `playwright.config.ts` an ein einziges Projekt
 * gebunden, sonst liefe er zweimal mit identischem Ergebnis.
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-05): siehe PR-Beschreibung - mit einer erzwungenen
 * `grid-template-columns: repeat(2, ...)`-Ueberschreibung bei 1280 px meldete der Spec
 * "Spaltenzahl bei 1280 px: expected 4, received 2".
 */

import { DEMO_PROJECTS, demoProjectId, photoTiles, type Box } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/**
 * Die Leiter des Foto-Grids. Die drei erwarteten Zahlen sind EXAKT, nicht "mindestens" - eine
 * Mindestwert-Assertion auf einer Layout-Eigenschaft traegt den Fehlerfall praktisch immer mit.
 */
const LADDER = [
  { width: 360, expectedColumns: 2 },
  { width: 700, expectedColumns: 3 },
  { width: 1280, expectedColumns: 4 },
] as const

const VIEWPORT_HEIGHT = 900
/** Zeilen-Toleranz in px: Kacheln derselben Zeile duerfen sich um Subpixel unterscheiden. */
const SAME_ROW_TOLERANCE = 2

test('Foto-Grid rendert 2 / 3 / 4 Spalten ueber die Breakpoint-Leiter', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.large)
  const measuredColumns: number[] = []

  for (const { width, expectedColumns } of LADDER) {
    await page.setViewportSize({ width, height: VIEWPORT_HEIGHT })
    await page.goto(`/projects/${projectId}/photos`)

    const tiles = photoTiles(page)
    // Zielzustand statt Wartezeit: das Grid existiert erst, wenn die Fotoabfrage geantwortet hat.
    await expect(tiles.first()).toBeVisible()

    const boxes: Box[] = await tiles.evaluateAll((elements) =>
      elements.map((element) => {
        const rect = element.getBoundingClientRect()
        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
      })
    )
    // Ohne diese Zusicherung koennte die erste Zeile aus einer einzigen Kachel bestehen und der
    // Spec meldete "1 Spalte" statt "Grid gar nicht gerendert".
    expect(boxes.length, `Kacheln im Grid bei ${width} px`).toBeGreaterThan(
      LADDER[LADDER.length - 1]!.expectedColumns
    )

    const firstRowY = Math.min(...boxes.map((box) => box.y))
    const firstRow = boxes.filter((box) => Math.abs(box.y - firstRowY) <= SAME_ROW_TOLERANCE)

    expect(firstRow.length, `Spaltenzahl bei ${width} px`).toBe(expectedColumns)

    // Kacheln mit Breite 0 oder ungleicher Breite innerhalb einer Zeile fallen durch: eine
    // kollabierte Kachel liegt geometrisch weiterhin in der ersten Zeile und wuerde sonst als
    // vollwertige Spalte mitgezaehlt.
    const widths = firstRow.map((box) => Math.round(box.width))
    expect(Math.min(...widths), `schmalste Kachel bei ${width} px`).toBeGreaterThan(0)
    expect(new Set(widths).size, `verschiedene Kachelbreiten in Zeile 1 bei ${width} px`).toBe(1)

    measuredColumns.push(firstRow.length)
  }

  // Die schaerfere Form der Vorbedingung (Regel 2 des Testkonzepts): ein Grid, das ueberhaupt
  // nicht mehr auf den Breakpoint reagiert, faellt hier auch dann auf, wenn eine der drei Zahlen
  // zufaellig stimmt.
  expect(new Set(measuredColumns).size, 'paarweise verschiedene Spaltenzahlen').toBe(LADDER.length)
})
