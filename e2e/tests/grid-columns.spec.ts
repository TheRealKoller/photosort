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

import type { Page } from '@playwright/test'

import {
  DEMO_PROJECTS,
  demoProjectId,
  duplicateTiles,
  openDuplicateGroup,
  photoTiles,
  type Box,
} from '../lib/demo.ts'
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
      }),
    )
    // Ohne diese Zusicherung koennte die erste Zeile aus einer einzigen Kachel bestehen und der
    // Spec meldete "1 Spalte" statt "Grid gar nicht gerendert".
    expect(boxes.length, `Kacheln im Grid bei ${width} px`).toBeGreaterThan(
      LADDER[LADDER.length - 1]!.expectedColumns,
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

/**
 * specs/features/0374-duplikate-vergleichen.md, AK3 und die Geometrie-Haelfte von AK8.
 *
 * ERWEITERUNG DIESES SPECS, kein neuer: Gemessen wird dieselbe Eigenschaft (Rastergeometrie) an
 * einer zweiten Ansicht - und wie oben ist sie in jsdom prinzipiell nicht pruefbar.
 *
 * DIE ZUSAGE LAUTET „bricht um, statt die Bilder kleiner zu machen". Sie ist nur ueber ZWEI
 * Gruppen verschiedener Groesse belegbar: Eine einzelne Gruppe zeigte zwar ihre Kacheln, aber
 * nicht, dass deren Breite an der Fensterbreite haengt und nicht an der Mitgliederzahl. Genau
 * deshalb fuehrt der Demo-Bestand eine Gruppe mit sieben und eine mit drei Aufnahmen.
 */
const DUPLICATE_LADDER = [
  { width: 360, expectedColumns: 2 },
  { width: 1280, expectedColumns: 3 },
] as const

/** Zulaessige Abweichung der Kachelbreite zwischen zwei Gruppen, in px. */
const WIDTH_TOLERANCE = 1

async function tileBoxes(page: Page): Promise<Box[]> {
  const tiles = duplicateTiles(page)
  await expect(tiles.first()).toBeVisible()
  return tiles.evaluateAll((elements) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect()
      return { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
    }),
  )
}

function firstRowOf(boxes: Box[]): Box[] {
  const firstRowY = Math.min(...boxes.map((box) => box.y))
  return boxes.filter((box) => Math.abs(box.y - firstRowY) <= SAME_ROW_TOLERANCE)
}

test('Duplikat-Vergleich bricht um, statt die Bilder zu verkleinern', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  const measuredColumns: number[] = []
  let wideTileWidth = 0

  for (const { width, expectedColumns } of DUPLICATE_LADDER) {
    await page.setViewportSize({ width, height: VIEWPORT_HEIGHT })
    await openDuplicateGroup(page, projectId, 'gross')

    const boxes = await tileBoxes(page)
    // Die grosse Gruppe rendert JEDE ihrer sieben Aufnahmen - eine Umsetzung, die bei
    // Platzmangel Kacheln weglaesst, faellt hier auf und nicht erst beim Hinsehen.
    expect(boxes.length, `Kacheln der grossen Gruppe bei ${width} px`).toBe(7)

    const firstRow = firstRowOf(boxes)
    expect(firstRow.length, `Spaltenzahl bei ${width} px`).toBe(expectedColumns)

    const widths = boxes.map((box) => Math.round(box.width))
    expect(Math.min(...widths), `schmalste Kachel bei ${width} px`).toBeGreaterThan(0)
    expect(new Set(widths).size, `verschiedene Kachelbreiten bei ${width} px`).toBe(1)

    measuredColumns.push(firstRow.length)
    if (width === 1280) {
      wideTileWidth = widths[0] ?? 0
    }
  }

  expect(new Set(measuredColumns).size, 'paarweise verschiedene Spaltenzahlen').toBe(
    DUPLICATE_LADDER.length,
  )

  // DAS eigentliche Paar: dieselbe Kachelbreite bei drei Mitgliedern wie bei sieben. Ohne diesen
  // Vergleich bestuende der Spec auch gegen eine Umsetzung, die alle Kacheln in EINE Zeile
  // presst - sie waeren dort ebenfalls gleich breit, nur eben kleiner.
  await page.setViewportSize({ width: 1280, height: VIEWPORT_HEIGHT })
  await openDuplicateGroup(page, projectId, 'klein')
  const smallBoxes = await tileBoxes(page)

  expect(smallBoxes.length, 'Kacheln der kleinen Gruppe').toBe(3)
  expect(
    Math.abs(Math.round(smallBoxes[0]?.width ?? 0) - wideTileWidth),
    `Kachelbreite bei 3 Mitgliedern (${smallBoxes[0]?.width ?? 0}) gegen 7 (${wideTileWidth})`,
  ).toBeLessThanOrEqual(WIDTH_TOLERANCE)
})

test('vergroesserte Kachel spannt die Rasterbreite und laesst die Gruppe im Blick', async ({
  page,
}) => {
  // AK8, Geometrie-Haelfte. Die Vergroesserung ist ausdruecklich KEIN Dialog: Die uebrige Gruppe
  // bleibt sichtbar, und genau das ist in jsdom nicht messbar.
  await page.setViewportSize({ width: 1280, height: VIEWPORT_HEIGHT })
  const projectId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  await openDuplicateGroup(page, projectId, 'gross')

  const before = await tileBoxes(page)
  const rasterWidth =
    Math.max(...before.map((box) => box.x + box.width)) - Math.min(...before.map((box) => box.x))

  // Die VIERTE Kachel: Bei sieben Mitgliedern in drei Spalten stehen dann Mitglieder ober- UND
  // unterhalb. Die erste haette nichts ueber sich.
  await duplicateTiles(page)
    .nth(3)
    .getByRole('button', { name: /vergrößern$/ })
    .click()
  await expect(page.getByRole('button', { name: /verkleinern$/ })).toBeVisible()

  // Mittig in den Sichtbereich rollen: Gemessen wird, ob die GRUPPE neben der Vergroesserung im
  // Blick bleibt - nicht, wo die Seite beim Klick zufaellig stand. Ohne das Rollen bestuende der
  // Fall je nach Kachelhoehe mal so, mal so.
  await duplicateTiles(page)
    .nth(3)
    .evaluate((element) => element.scrollIntoView({ block: 'center' }))

  const after = await tileBoxes(page)
  expect(after.length, 'alle Mitglieder bleiben im Dokument').toBe(7)

  const enlarged = after[3]
  expect(enlarged, 'vergroesserte Kachel').toBeDefined()
  expect(
    Math.abs(Math.round(enlarged?.width ?? 0) - Math.round(rasterWidth)),
    'Breite der vergroesserten Kachel gegen die Rasterbreite',
  ).toBeLessThanOrEqual(WIDTH_TOLERANCE)

  // Mindestens ein weiteres Mitglied ober- UND unterhalb im Sichtbereich - sonst waere die
  // Vergroesserung faktisch doch ein Vollbild, und der Vergleich, um den es geht, fiele weg.
  const sichtbar = after.filter((box) => box.y + box.height > 0 && box.y < VIEWPORT_HEIGHT)
  const mitte = enlarged?.y ?? 0
  expect(
    sichtbar.some((box) => box !== enlarged && box.y + box.height <= mitte + SAME_ROW_TOLERANCE),
    'mindestens ein Mitglied oberhalb im Sichtbereich',
  ).toBe(true)
  expect(
    sichtbar.some(
      (box) => box !== enlarged && box.y >= mitte + (enlarged?.height ?? 0) - SAME_ROW_TOLERANCE,
    ),
    'mindestens ein Mitglied unterhalb im Sichtbereich',
  ).toBe(true)
})
