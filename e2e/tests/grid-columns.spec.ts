/**
 * Die Geometrie der beiden Foto-Raster - gemessen im echten Browser.
 *
 * jsdom hat keine Layout-Engine: Dort ist jede Breite 0 und jedes Rechteck leer. Alles, was diese
 * Datei prueft, ist deshalb in keinem Komponententest pruefbar, und die Komponententests pruefen
 * umgekehrt nichts davon - keine Verdopplung in beide Richtungen.
 *
 * NEU GEFASST MIT SPEC 0489: Die Fotouebersicht misst keine feste Spaltenzahl mehr. Sie ist ein
 * justiertes ZEILENraster - alle Bilder einer Zeile auf gemeinsamer Hoehe, die Zeile buendig auf
 * die verfuegbare Breite, kein Bild beschnitten.
 *
 * SEIT SPEC 0638 gilt dasselbe fuer die Duplikat-Vergleichsansicht weiter unten: Auch dort ist die
 * feste Spaltenzahl entfallen (Spec 0374 AK3). Die beiden Teile messen jetzt DIESELBE Eigenschaft an
 * zwei Ansichten.
 *
 * Rot-Nachweis der neuen Fassung: siehe PR-Beschreibung.
 */

import type { Page } from '@playwright/test'

import { warteAufBilder, zaehleGeladeneBilder } from '../lib/bilder.ts'
import {
  DEMO_PROJECTS,
  demoProjectId,
  duplicateTiles,
  openDuplicateGroup,
  overrideDuplicateRatios,
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

interface TileMeasurement extends Box {
  naturalWidth: number
  naturalHeight: number
}

async function photoTileBoxes(page: Page): Promise<TileMeasurement[]> {
  // Zielzustand statt Wartezeit: das Raster existiert erst, wenn die Fotoabfrage geantwortet hat,
  // und die Bilder erst nach ihrem Blob-Abruf - vorher waeren `naturalWidth`/`naturalHeight` 0 und
  // der Beschnitt-Vergleich unten bedeutungslos.
  const tiles = photoTiles(page)
  await warteAufBilder(tiles, { flaeche: 'Fotoraster', was: 'Kachelbild', bild: 'img' })

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
function rowsOf<T extends Box>(boxes: T[]): T[][] {
  const rows: T[][] = []
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
 * specs/features/0638-duplikatansicht-originalformat.md, AK1-AK4 und AK6 - ERSETZT den
 * Duplikat-Fall dieses Specs, nicht gelockert: Spec 0374 AK3 (bei 360 px genau zwei, bei 1280 px
 * genau drei Spalten gleicher Breite) gilt nicht mehr. Die Vergleichsansicht ist wie die
 * Fotouebersicht ein justiertes ZEILENraster, und wie oben ist nichts davon in jsdom pruefbar.
 *
 * Die fruehere Fassung mass die Spaltenzahl und die Gleichheit der Kachelbreiten. Beides ist hier
 * nachweislich falsch: Eine Zeile traegt so viele Aufnahmen, wie ihre Verhaeltnisse zulassen, und
 * die Kachelbreite FOLGT dem Verhaeltnis. Die Zusagen, die an ihre Stelle treten, stehen unten.
 */

/** Die kleinste zugesagte Kachelbreite (AK3). */
const DUPLICATE_MIN_TILE_WIDTH_PX = 100
/** Die kleinste zugesagte Bildflaechenhoehe (AK3, Telefon). */
const DUPLICATE_MIN_IMAGE_HEIGHT_PX = 44

interface DuplicateTileMeasurement extends Box {
  /** Die BILDFLAECHE (`duplicate-image`), nicht die Kachel samt Text und Wahlzeile. */
  image: Box
  naturalWidth: number
  naturalHeight: number
  objectFit: string
}

/** Die gemessenen Kacheln samt Bildflaeche und dem tatsaechlich geladenen Bild. */
async function duplicateTileBoxes(page: Page): Promise<DuplicateTileMeasurement[]> {
  return duplicateTiles(page).evaluateAll((elements) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect()
      const button = element.querySelector('[data-testid="duplicate-image"]')
      const imageRect = button?.getBoundingClientRect()
      const image = button?.querySelector('img')
      return {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
        image: {
          x: imageRect?.x ?? 0,
          y: imageRect?.y ?? 0,
          width: imageRect?.width ?? 0,
          height: imageRect?.height ?? 0,
        },
        naturalWidth: image instanceof HTMLImageElement ? image.naturalWidth : 0,
        naturalHeight: image instanceof HTMLImageElement ? image.naturalHeight : 0,
        objectFit: image instanceof HTMLElement ? getComputedStyle(image).objectFit : '',
      }
    }),
  )
}

/** Das Bild einer Duplikat-Kachel, innerhalb ihrer Bildflaeche. */
const DUPLICATE_IMAGE = '[data-testid="duplicate-image"] img'

/** Wartet, bis JEDE Kachel ihr Bild geladen hat - vorher ist jeder Verhaeltnisvergleich leer. */
async function waitForDuplicateImages(page: Page): Promise<void> {
  await warteAufBilder(duplicateTiles(page), {
    flaeche: 'Duplikat-Raster',
    was: 'Kachelbild',
    bild: DUPLICATE_IMAGE,
  })
}

test('Duplikat-Vergleich setzt justierte Zeilen ohne Beschnitt', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  await page.setViewportSize({ width: 1280, height: VIEWPORT_HEIGHT })
  await openDuplicateGroup(page, projectId, 'gross')
  await waitForDuplicateImages(page)

  const tiles = await duplicateTileBoxes(page)
  // Die grosse Gruppe rendert JEDE ihrer sieben Aufnahmen - eine Umsetzung, die bei Platzmangel
  // Kacheln weglaesst, faellt hier auf und nicht erst beim Hinsehen.
  expect(tiles.length, 'Kacheln der grossen Gruppe').toBe(7)

  // Der Demo-Bestand fuehrt bewusst gemischte Formate (4:3, 3:4, 12:5, 1:1). Ohne sie waere ein
  // justiertes Raster von einem Spaltenraster nicht zu unterscheiden.
  const shapes = new Set(tiles.map((tile) => (tile.naturalWidth / tile.naturalHeight).toFixed(2)))
  expect(shapes.size, 'verschiedene Bildformate in der Gruppe').toBeGreaterThanOrEqual(3)

  // Die verfuegbare Breite kommt vom CONTAINER der Liste, nie aus den Kacheln selbst - sonst
  // maesse der Buendigkeitsvergleich sich selbst.
  const rasterWidth = await duplicateTiles(page)
    .first()
    .evaluate((element) => element.parentElement?.clientWidth ?? 0)
  expect(rasterWidth, 'gemessene Rasterbreite').toBeGreaterThan(0)

  const rows = rowsOf(tiles)
  expect(rows.length, 'Zeilen im Raster').toBeGreaterThan(1)

  // Die LETZTE Zeile ist ausgenommen: sie bleibt bewusst ungestreckt und linksbuendig stehen.
  for (const [index, row] of rows.slice(0, -1).entries()) {
    const heights = row.map((tile) => Math.round(tile.image.height))
    expect(new Set(heights).size, `verschiedene Bildhoehen in Zeile ${index + 1}`).toBe(1)
    // `items-start` haelt die Kacheln oben buendig - auch wenn unter dem Bild unterschiedlich
    // viel steht (Wahlzeile oder Begruendung).
    const tops = row.map((tile) => Math.round(tile.image.y))
    expect(new Set(tops).size, `verschiedene Oberkanten in Zeile ${index + 1}`).toBe(1)

    const lineWidth = row.reduce((sum, tile) => sum + tile.width, 0) + GRID_GAP * (row.length - 1)
    expect(
      Math.abs(lineWidth - rasterWidth),
      `buendiges Zeilenende in Zeile ${index + 1} (${lineWidth} gegen ${rasterWidth})`,
    ).toBeLessThanOrEqual(SAME_ROW_TOLERANCE)
  }

  // Und die letzte Zeile ist NACHWEISLICH kuerzer - ohne diese Gegenprobe bestuende die Aussage
  // "sie wird nicht aufgezogen" auch gegen eine Umsetzung, die sie mitstreckt.
  const lastRow = rows[rows.length - 1]!
  const lastLineWidth =
    lastRow.reduce((sum, tile) => sum + tile.width, 0) + GRID_GAP * (lastRow.length - 1)
  expect(lastLineWidth, 'die letzte Zeile bleibt ungestreckt').toBeLessThan(rasterWidth)

  // KEIN BESCHNITT - der eigentliche Beweis: Das Verhaeltnis der Bildflaeche folgt dem Verhaeltnis
  // des tatsaechlich geladenen Bildes. `object-cover` oder eine feste Form liessen hier lauter
  // gleiche Verhaeltnisse entstehen.
  for (const tile of tiles) {
    const imageRatio = tile.naturalWidth / tile.naturalHeight
    expect(
      Math.abs(tile.image.width / tile.image.height - imageRatio),
      `Kastenverhaeltnis gegen Bildverhaeltnis (${tile.image.width}x${tile.image.height} vs. ${tile.naturalWidth}x${tile.naturalHeight})`,
    ).toBeLessThanOrEqual(RATIO_TOLERANCE * imageRatio + RATIO_TOLERANCE)
    expect(tile.objectFit, 'das Bild ist eingepasst, nicht zugeschnitten').toBe('contain')
  }

  // VERSCHIEDENE Kachelbreiten in EINER Gruppe: die Gegenprobe gegen das Spaltenraster, das hier
  // bis Spec 0638 galt.
  expect(
    new Set(tiles.map((tile) => Math.round(tile.image.width))).size,
    'verschiedene Bildbreiten',
  ).toBeGreaterThan(1)

  for (const tile of tiles) {
    expect(tile.width, 'Kachel mindestens 100 px breit').toBeGreaterThanOrEqual(
      DUPLICATE_MIN_TILE_WIDTH_PX,
    )
  }
})

/**
 * Extreme und unbekannte Verhaeltnisse (AK3, Sicherheit): Der Demo-Bestand traegt bewusst nur
 * Verhaeltnisse im Normalband, deshalb kommt hier der Antwort-Eingriff zum Einsatz. Geprueft wird
 * an der schmalsten Breite, weil dort jede Grenze zuerst greift.
 */
test('Duplikat-Vergleich passt extreme und unbekannte Verhaeltnisse ins Grenzband ein', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  await page.setViewportSize({ width: 360, height: VIEWPORT_HEIGHT })
  // 0,3 liegt unter dem Planungsband, 20 darueber, `null` heisst unbekannt.
  await overrideDuplicateRatios(page, [0.3, 20, null])
  await openDuplicateGroup(page, projectId, 'klein')
  await waitForDuplicateImages(page)

  const tiles = await duplicateTileBoxes(page)
  expect(tiles.length, 'Kacheln der kleinen Gruppe').toBe(3)

  // Das Planungsverhaeltnis: unten 0,56, oben 7, unbekannt 3:2 (AK1, AK3).
  const erwartet = [0.56, 7, 1.5]
  for (const [index, tile] of tiles.entries()) {
    expect(
      tile.image.width / tile.image.height,
      `Kastenverhaeltnis der Kachel ${index + 1}`,
    ).toBeCloseTo(erwartet[index]!, 1)
    expect(tile.objectFit, `Bild ${index + 1} ist eingepasst`).toBe('contain')
    expect(
      tile.image.height,
      `Bildflaeche ${index + 1} mindestens 44 px hoch`,
    ).toBeGreaterThanOrEqual(DUPLICATE_MIN_IMAGE_HEIGHT_PX - SAME_ROW_TOLERANCE)
    expect(tile.width, `Kachel ${index + 1} mindestens 100 px breit`).toBeGreaterThanOrEqual(
      DUPLICATE_MIN_TILE_WIDTH_PX,
    )
  }

  // Die Wahlzeile bleibt IN ihrer Kachel - gerade in der schmalsten, die das Grenzband zulaesst.
  const ueberstand = await duplicateTiles(page).evaluateAll((elements) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect()
      const knoepfe = [...element.querySelectorAll('[role="group"][aria-label^="Wahl: "] button')]
      return knoepfe.length === 0
        ? null
        : Math.max(...knoepfe.map((knopf) => knopf.getBoundingClientRect().right)) - rect.right
    }),
  )
  expect(
    ueberstand.filter((wert) => wert !== null).length,
    'Kacheln mit Wahlzeile',
  ).toBeGreaterThan(0)
  for (const wert of ueberstand) {
    expect(wert ?? 0, 'Wahlzeile innerhalb der Kachel').toBeLessThanOrEqual(SAME_ROW_TOLERANCE)
  }

  const scroll = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(scroll.scrollWidth, 'kein waagerechtes Scrollen').toBeLessThanOrEqual(
    scroll.clientWidth + SAME_ROW_TOLERANCE,
  )
})

/**
 * AK6, zweite Ebene: Beim Eintreffen der Bilddaten darf sich NICHTS verschieben. Die Bildanfragen
 * werden dafuer angehalten und die Rechtecke vor und nach der Freigabe verglichen - gewartet wird
 * hier also nicht auf das Ereignis, sondern es wird beidseitig gemessen.
 */
test('Duplikat-Raster springt beim Eintreffen der Bilddaten nicht', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  await page.setViewportSize({ width: 1280, height: VIEWPORT_HEIGHT })
  // Der ECHTE Einstieg, damit der Anhaltepunkt erst nach der Liste greift: deren Bilder waeren
  // sonst beim Ansichtswechsel offene, gleich wieder abgebrochene Anfragen.
  await page.goto(`/projects/${projectId}/photos?filter=suggested`)
  const einstieg = page.getByRole('link', { name: /^Duplikate vergleichen —/ })
  await expect(einstieg, 'listenweiter Einstieg in den Duplikat-Vergleich').toBeVisible()
  await warteAufBilder(photoTiles(page), {
    flaeche: 'Fotoliste',
    was: 'Kachelbild',
    bild: 'img',
    ohneBildZulaessig: true,
  })

  // Der Ausloeser der Freigabe, vor dem Anhalten gesetzt; `let`, weil er im Handler entsteht.
  let oeffne: () => void = () => {}
  const halt = new Promise<void>((resolve) => {
    oeffne = resolve
  })
  let freigegeben = false
  await page.route(/\/photos\/\d+\/image\?/, async (route) => {
    if (!freigegeben) {
      await halt
    }
    try {
      await route.continue()
    } catch {
      // Die Anfrage wurde beim Wechsel der Ansicht abgebrochen - kein Fehler des Specs.
    }
  })

  await einstieg.click()
  await expect(duplicateTiles(page), 'Kacheln der grossen Gruppe').toHaveCount(7)

  // Vorbedingung: VOR der Freigabe ist kein Bild geladen - sonst maesse der Vergleich zweimal
  // denselben Endzustand.
  const geladene = await zaehleGeladeneBilder(duplicateTiles(page), DUPLICATE_IMAGE)
  expect(geladene, 'vor der Freigabe geladene Bilder').toBe(0)

  const vorher = await duplicateTileBoxes(page)
  freigegeben = true
  oeffne()
  await waitForDuplicateImages(page)
  const nachher = await duplicateTileBoxes(page)

  expect(nachher.length, 'Kacheln nach der Freigabe').toBe(vorher.length)
  for (const [index, rect] of vorher.entries()) {
    const spaeter = nachher[index]!
    for (const key of ['x', 'y', 'width', 'height'] as const) {
      expect(
        Math.abs(spaeter[key] - rect[key]),
        `Kachel ${index + 1}: ${key} vor (${rect[key]}) und nach (${spaeter[key]}) der Freigabe`,
      ).toBeLessThanOrEqual(1)
    }
    for (const key of ['x', 'y', 'width', 'height'] as const) {
      expect(
        Math.abs(spaeter.image[key] - rect.image[key]),
        `Bildflaeche ${index + 1}: ${key} vor (${rect.image[key]}) und nach (${spaeter.image[key]})`,
      ).toBeLessThanOrEqual(1)
    }
    expect(spaeter.objectFit, `Bild ${index + 1} nach der Freigabe eingepasst`).toBe('contain')
  }
})
