/**
 * Die Geometrie der beiden Foto-Raster - gemessen im echten Browser.
 *
 * jsdom hat keine Layout-Engine: Dort ist jede Breite 0 und jedes Rechteck leer. Alles, was diese
 * Datei prueft, ist deshalb in keinem Komponententest pruefbar, und die Komponententests pruefen
 * umgekehrt nichts davon - keine Verdopplung in beide Richtungen.
 *
 * NEU GEFASST MIT SPEC 0489: Die Fotouebersicht misst keine feste Spaltenzahl mehr. Sie ist ein
 * justiertes ZEILENraster - alle Bilder einer Zeile auf gemeinsamer Hoehe, die Zeile buendig auf
 * die verfuegbare Breite, kein Bild beschnitten. Der Duplikat-Teil weiter unten bleibt
 * unveraendert: dort gilt die Spaltenzahl weiterhin.
 *
 * Rot-Nachweis der neuen Fassung: siehe PR-Beschreibung.
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

const VIEWPORT_HEIGHT = 900
/** Zeilen-Toleranz in px: Kacheln derselben Zeile duerfen sich um Subpixel unterscheiden. */
const SAME_ROW_TOLERANCE = 2
/** Der Zwischenraum zwischen zwei Kacheln (`gap-3` = `GRID_GAP_PX`). */
const GRID_GAP = 12
/** Zulaessige Abweichung beim Vergleich Kastenverhaeltnis gegen Bildverhaeltnis. */
const RATIO_TOLERANCE = 0.02
/** Wartegrenze, bis alle Kacheln einer Seite ihr Bild geladen haben. */
const IMAGE_LOAD_TIMEOUT_MS = 30_000

interface TileMeasurement extends Box {
  naturalWidth: number
  naturalHeight: number
}

async function photoTileBoxes(page: Page): Promise<TileMeasurement[]> {
  const tiles = photoTiles(page)
  // Zielzustand statt Wartezeit: das Raster existiert erst, wenn die Fotoabfrage geantwortet hat.
  await expect(tiles.first()).toBeVisible()
  // Und die Bilder selbst sind erst nach ihrem authentifizierten Blob-Abruf geladen - ohne dieses
  // Warten waeren `naturalWidth`/`naturalHeight` 0 und der Beschnitt-Vergleich unten bedeutungslos.
  await expect
    .poll(
      async () =>
        tiles.evaluateAll((elements) =>
          elements.every((element) => {
            const image = element.querySelector('img')
            return image !== null && image.complete && image.naturalWidth > 0
          }),
        ),
      {
        // Eine volle Seite sind sechzig einzeln authentifizierte Blob-Abrufe - die Vorgabe von
        // fuenf Sekunden reicht dafuer nicht verlaesslich, und ein Zeitablauf hier waere ein
        // sprunghafter Fehlschlag ohne Aussage ueber die Geometrie.
        timeout: IMAGE_LOAD_TIMEOUT_MS,
        message: 'alle Kacheln haben ihr Bild geladen',
      },
    )
    .toBe(true)

  return tiles.evaluateAll((elements) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect()
      const image = element.querySelector('img')
      return {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
        naturalWidth: image?.naturalWidth ?? 0,
        naturalHeight: image?.naturalHeight ?? 0,
      }
    }),
  )
}

/** Gruppiert die gemessenen Kacheln nach ihrer Oberkante zu Zeilen. */
function rowsOf(boxes: TileMeasurement[]): TileMeasurement[][] {
  const rows: TileMeasurement[][] = []
  for (const box of [...boxes].sort((a, b) => a.y - b.y || a.x - b.x)) {
    const row = rows[rows.length - 1]
    if (row !== undefined && Math.abs((row[0]?.y ?? 0) - box.y) <= SAME_ROW_TOLERANCE) {
      row.push(box)
    } else {
      rows.push([box])
    }
  }
  return rows
}

test('Fotouebersicht setzt justierte Zeilen ohne Beschnitt', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.large)

  await page.setViewportSize({ width: 1280, height: VIEWPORT_HEIGHT })
  await page.goto(`/projects/${projectId}/photos`)
  const boxes = await photoTileBoxes(page)

  // Ohne diese Zusicherung koennte das Raster aus einer einzigen Kachel bestehen, und jede Aussage
  // ueber "Zeilen" waere leer.
  expect(boxes.length, 'Kacheln im Raster').toBeGreaterThan(4)

  const rows = rowsOf(boxes)
  expect(rows.length, 'Zeilen im Raster').toBeGreaterThan(1)

  // Der Demo-Bestand fuehrt bewusst gemischte Formate. Ohne sie waere ein justiertes Raster von
  // einem Spaltenraster gar nicht zu unterscheiden, und dieser Spec pruefte nichts.
  const shapes = new Set(boxes.map((box) => (box.naturalWidth / box.naturalHeight).toFixed(2)))
  expect(shapes.size, 'verschiedene Bildformate im Bestand').toBeGreaterThanOrEqual(3)

  // Die verfuegbare Breite kommt vom CONTAINER, nie aus den Kacheln selbst. Gegen eine aus den
  // Kacheln abgeleitete Breite maesse dieser Vergleich sich selbst: Er bliebe auch dann gruen,
  // wenn jede Kachel eine erzwungene Fremdbreite traegt - nachgewiesen im Rot-Nachweis, wo genau
  // diese erste Fassung gruen blieb.
  const rasterWidth = await page
    .locator('[data-photo-grid]')
    .evaluate((element) => element.clientWidth)
  expect(rasterWidth, 'gemessene Rasterbreite').toBeGreaterThan(0)

  // Die LETZTE Zeile ist ausgenommen: sie bleibt bewusst ungestreckt und linksbuendig stehen.
  for (const [index, row] of rows.slice(0, -1).entries()) {
    const heights = row.map((box) => Math.round(box.height))
    expect(new Set(heights).size, `verschiedene Hoehen in Zeile ${index}`).toBe(1)

    const lineWidth = row.reduce((sum, box) => sum + box.width, 0) + GRID_GAP * (row.length - 1)
    expect(
      Math.abs(lineWidth - rasterWidth),
      `buendiges Zeilenende in Zeile ${index} (${lineWidth} gegen ${rasterWidth})`,
    ).toBeLessThanOrEqual(SAME_ROW_TOLERANCE)
  }

  // Und die letzte Zeile ist NACHWEISLICH kuerzer - ohne diese Gegenprobe bestuende die Aussage
  // "sie wird nicht aufgezogen" auch gegen eine Umsetzung, die sie mitstreckt.
  const lastRow = rows[rows.length - 1]!
  const lastLineWidth =
    lastRow.reduce((sum, box) => sum + box.width, 0) + GRID_GAP * (lastRow.length - 1)
  expect(lastLineWidth, 'die letzte Zeile bleibt ungestreckt').toBeLessThan(rasterWidth)

  // KEIN BESCHNITT - der eigentliche Beweis: Das Kastenverhaeltnis jeder Kachel folgt dem
  // Verhaeltnis ihres tatsaechlich geladenen Bildes. Ein `object-cover` oder eine feste Form
  // liesse hier lauter gleiche Kastenverhaeltnisse entstehen.
  for (const box of boxes) {
    const imageRatio = box.naturalWidth / box.naturalHeight
    expect(
      Math.abs(box.width / box.height - imageRatio),
      `Kastenverhaeltnis gegen Bildverhaeltnis (${box.width}x${box.height} vs. ${box.naturalWidth}x${box.naturalHeight})`,
    ).toBeLessThanOrEqual(RATIO_TOLERANCE * imageRatio + RATIO_TOLERANCE)
  }
})

test('Fotouebersicht rechnet die Zeilen fuer jede Breite neu', async ({ page }) => {
  // Die schaerfere Form der Vorbedingung: Ein Raster, das gar nicht mehr auf die Breite reagiert,
  // faellt hier auch dann auf, wenn eine der beiden Messungen fuer sich stimmt.
  const projectId = await demoProjectId(page, DEMO_PROJECTS.large)
  const firstRowHeights: number[] = []
  const firstRowCounts: number[] = []

  for (const width of [700, 1280]) {
    await page.setViewportSize({ width, height: VIEWPORT_HEIGHT })
    await page.goto(`/projects/${projectId}/photos`)

    const rows = rowsOf(await photoTileBoxes(page))
    const firstRow = rows[0]!
    expect(firstRow.length, `Kacheln in Zeile 1 bei ${width} px`).toBeGreaterThan(0)
    firstRowHeights.push(Math.round(firstRow[0]!.height))
    firstRowCounts.push(firstRow.length)
  }

  expect(new Set(firstRowHeights).size, 'paarweise verschiedene Zeilenhoehen').toBe(2)
  // Die breitere Ansicht traegt mindestens so viele Bilder in der ersten Zeile wie die schmalere -
  // andernfalls waere die Hoehendifferenz oben ein anderer Effekt als der gesuchte.
  expect(firstRowCounts[1]!).toBeGreaterThanOrEqual(firstRowCounts[0]!)
})

test('Fotouebersicht laedt beim Scrollen nach, ohne Schaltflaeche', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.large)
  await page.setViewportSize({ width: 1280, height: VIEWPORT_HEIGHT })
  await page.goto(`/projects/${projectId}/photos`)

  const tiles = photoTiles(page)
  await expect(tiles.first()).toBeVisible()
  await expect(page.getByRole('button', { name: /weitere laden/i })).toHaveCount(0)

  const zaehlzeile = page.getByText(/^\d+ von \d+ geladen/)
  await expect(zaehlzeile, 'Zaehlzeile unter dem Raster').toBeVisible()
  const vorher = await tiles.count()

  await page.mouse.wheel(0, 100000)

  // Nachgeladen wird allein durch das Scrollen - kein Klick dazwischen.
  await expect.poll(async () => tiles.count()).toBeGreaterThan(vorher)
  await expect(zaehlzeile).toBeVisible()
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
