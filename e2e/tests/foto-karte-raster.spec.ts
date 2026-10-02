/**
 * Die Raster der Foto-Karte in Album-Entwurf und Endauswahl - gemessen im echten Browser
 * (specs/features/0563-groessere-unbeschnittene-fotos.md).
 *
 * Gemessen werden die Spaltenleiter (AK1, AK2), das Einpassen des Bildes (AK3) und die ruhige
 * Reihe mit gleich grosser, quadratischer Bildflaeche (AK4). jsdom hat keine Layout-Engine; der
 * Vertragstest `designSystem.contract.test.ts` haelt nur die Klassen fest, ihre Wirkung steht hier.
 *
 * An EIN Projekt gebunden (`DESKTOP_ONLY`): Die Datei setzt ihre Breiten selbst, in beiden
 * Projekten liefe sie mit identischem Ergebnis.
 */

import type { Locator, Page } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { readOwnDraftStates, restoreOwnDraftStates } from '../lib/draft.ts'
import { expect, test } from '../lib/fixtures.ts'

const VIEWPORT_HEIGHT = 900
/** Die Spaltenleiter aus AK1/AK2. Die Grenzbreiten selbst prueft die Spec bewusst nicht. */
const LADDER = [
  { width: 360, columns: 2 },
  { width: 800, columns: 3 },
  { width: 1280, columns: 4 },
] as const
/** Masstoleranz in px (AK4: ±1 px). */
const TOLERANCE = 1
/** Kacheln derselben Reihe duerfen sich in der Oberkante um Subpixel unterscheiden. */
const SAME_ROW_TOLERANCE = 2
/** Wartegrenze, bis alle Bilder eines Rasters geladen sind (je ein authentifizierter Blob-Abruf). */
const IMAGE_LOAD_TIMEOUT_MS = 30_000

/** Die Bedienelemente einer Endauswahl-Kachel in Arbeits- und Ergebnissicht. */
const SELECTION_TILE_CONTROL = /^(Aufnehmen|Nicht aufnehmen|Herausnehmen): /

interface TileMeasurement {
  /** Oberkante der Kachel - gruppiert die Reihen. */
  top: number
  objectFit: string
  naturalWidth: number
  naturalHeight: number
  area: { width: number; height: number }
  /** Lage des Elements unter der Bildflaeche (Kennzeichen und Dateiname), relativ zur Kachel. */
  belowArea: { x: number; y: number } | null
  /** Lage des Ecken-Handgriffs (Overlay neben der Bildflaeche), relativ zur Kachel. */
  cornerHandle: { x: number; y: number } | null
}

interface GridMeasurement {
  columns: number
  tiles: TileMeasurement[]
}

/** Die Spaltenzahl des gerenderten Rasters und je Kachel mit Foto ihre Masse. */
async function measureGrid(grid: Locator): Promise<GridMeasurement> {
  await expect(grid.locator(':scope > li img').first()).toBeVisible()
  // Ohne geladenes Bild waeren `naturalWidth`/`naturalHeight` 0 und die Formatpruefung leer.
  await expect
    .poll(
      () =>
        grid.evaluate((list) =>
          [...list.querySelectorAll(':scope > li img')].every(
            (image) =>
              image instanceof HTMLImageElement && image.complete && image.naturalWidth > 0,
          ),
        ),
      { timeout: IMAGE_LOAD_TIMEOUT_MS, message: 'alle Bilder des Rasters sind geladen' },
    )
    .toBe(true)

  return grid.evaluate((list) => {
    const columns = window
      .getComputedStyle(list)
      .gridTemplateColumns.split(' ')
      .filter((part) => part.length > 0).length
    const tiles = [...list.querySelectorAll(':scope > li')].flatMap((tile) => {
      const image = tile.querySelector('img')
      const area = image?.parentElement
      if (image === null || area === null || area === undefined) {
        return []
      }
      const tileRect = tile.getBoundingClientRect()
      const relative = (element: Element | null | undefined) => {
        if (element === null || element === undefined) {
          return null
        }
        const rect = element.getBoundingClientRect()
        return { x: rect.left - tileRect.left, y: rect.top - tileRect.top }
      }
      const areaRect = area.getBoundingClientRect()
      const corner = [...(area.parentElement?.querySelectorAll('button') ?? [])].find(
        (button) => button !== area && !area.contains(button),
      )
      return [
        {
          top: tileRect.top,
          objectFit: window.getComputedStyle(image).objectFit,
          naturalWidth: image.naturalWidth,
          naturalHeight: image.naturalHeight,
          area: { width: areaRect.width, height: areaRect.height },
          // Bei der Foto-Karte liegt die Bildflaeche in einem Rahmen mit den Overlays; die Zeile
          // darunter ist dessen Geschwister. Im Band ist die Bildflaeche selbst das Kind der Kachel.
          belowArea: relative(
            area.parentElement === tile
              ? area.nextElementSibling
              : area.parentElement?.nextElementSibling,
          ),
          cornerHandle: relative(corner),
        },
      ]
    })
    return { columns, tiles }
  })
}

function firstRow(tiles: TileMeasurement[]): TileMeasurement[] {
  const top = Math.min(...tiles.map((tile) => tile.top))
  return tiles.filter((tile) => Math.abs(tile.top - top) <= SAME_ROW_TOLERANCE)
}

function rowsOf(tiles: TileMeasurement[]): TileMeasurement[][] {
  const rows: TileMeasurement[][] = []
  for (const tile of tiles) {
    const row = rows.find(
      (candidate) => Math.abs((candidate[0]?.top ?? 0) - tile.top) <= SAME_ROW_TOLERANCE,
    )
    if (row === undefined) {
      rows.push([tile])
    } else {
      row.push(tile)
    }
  }
  return rows
}

const isPortrait = (tile: TileMeasurement) => tile.naturalHeight > tile.naturalWidth
const isLandscape = (tile: TileMeasurement) => tile.naturalWidth > tile.naturalHeight

/**
 * Spaltenzahl der Leiterstufe, kein Beschnitt, quadratische und gleich grosse Bildflaeche. Traegt
 * das Raster mindestens so viele Kacheln wie Spalten, muss die erste Reihe voll besetzt sein - nur
 * dann belegt ihre Kachelzahl die Spaltenzahl auch sichtbar.
 */
function expectLadderStep(
  measurement: GridMeasurement,
  expectedColumns: number,
  label: string,
): void {
  expect(measurement.columns, `Spaltenzahl ${label}`).toBe(expectedColumns)
  expect(measurement.tiles.length, `Kacheln mit Foto ${label}`).toBeGreaterThan(0)

  const row = firstRow(measurement.tiles)
  expect(row.length, `Kacheln in der ersten Reihe ${label}`).toBeLessThanOrEqual(expectedColumns)
  if (measurement.tiles.length >= expectedColumns) {
    expect(row.length, `volle erste Reihe ${label}`).toBe(expectedColumns)
  }

  for (const tile of measurement.tiles) {
    expect(tile.objectFit, `object-fit ${label}`).toBe('contain')
    expect(
      Math.abs(tile.area.width - tile.area.height),
      `quadratische Bildflaeche ${label} (${tile.area.width} x ${tile.area.height})`,
    ).toBeLessThanOrEqual(TOLERANCE)
  }
  const reference = row[0]?.area
  for (const tile of row) {
    expect(
      Math.abs(tile.area.width - (reference?.width ?? 0)),
      `Flaechenbreite ${label}`,
    ).toBeLessThanOrEqual(TOLERANCE)
    expect(
      Math.abs(tile.area.height - (reference?.height ?? 0)),
      `Flaechenhoehe ${label}`,
    ).toBeLessThanOrEqual(TOLERANCE)
  }
}

/** Das Albumraster des ersten Eventabschnitts. */
function draftGrid(page: Page): Locator {
  return page.locator('section[data-draft-position] > ul').first()
}

/** Das Raster der ersten Gruppe der Endauswahl (Arbeits- oder Ergebnissicht). */
function selectionGrid(page: Page): Locator {
  return page
    .locator('ul')
    .filter({ has: page.getByRole('button', { name: SELECTION_TILE_CONTROL }) })
    .first()
}

/** Das Kandidatenraster eines geoeffneten Bands bzw. Panels (die volle Rasterzeile mit `id`). */
async function panelGrid(page: Page, trigger: Locator): Promise<Locator> {
  const panel = page.locator(`[id="${await trigger.getAttribute('aria-controls')}"]`)
  return panel.locator(':scope > ul:not([role="status"])')
}

test('Album-Entwurf: Spaltenleiter 2/3/4, eingepasste Bilder, ruhige Reihe', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

  for (const { width, columns } of LADDER) {
    await page.setViewportSize({ width, height: VIEWPORT_HEIGHT })
    await page.goto(`/projects/${projectId}/album`)
    const label = `im Album-Entwurf bei ${width} px`

    const grid = await measureGrid(draftGrid(page))
    expectLadderStep(grid, columns, label)

    // Band: geoeffnet an der ersten Entwurfskachel.
    const alternatives = page.getByRole('button', { name: /^Alternativen: / }).first()
    await alternatives.click()
    const band = await panelGrid(page, alternatives)
    expectLadderStep(await measureGrid(band), columns, `im Alternativen-Band bei ${width} px`)
    await alternatives.click()

    // Panel: das Hinzufuegen-Feld des ersten Events.
    const addTrigger = page.getByRole('button', { name: /^Foto hinzufügen: / }).first()
    await addTrigger.click()
    const panel = await panelGrid(page, addTrigger)
    expectLadderStep(await measureGrid(panel), columns, `im Hinzufuegen-Panel bei ${width} px`)
    await addTrigger.click()
  }
})

/**
 * Nimmt jedes Foto eines Events in den Entwurf, das die Oberflaeche dafuer anbietet: zuerst die
 * gestrichenen ueber „Wieder aufnehmen", dann alle Kandidaten des Hinzufuegen-Panels - genau die
 * Handgriffe eines Nutzers. Liefert die Zahl der Albumkacheln danach.
 */
async function takeEverything(section: Locator): Promise<number> {
  const albumTiles = section.locator(':scope > ul').getByRole('button', { name: /^Streichen: / })

  const struckToggle = section.getByRole('button', { name: /^\d+ gestrichen – anzeigen$/ })
  if ((await struckToggle.count()) > 0) {
    await struckToggle.click()
    const readd = section.getByRole('button', { name: /^Wieder aufnehmen: / })
    while ((await readd.count()) > 0) {
      const count = await albumTiles.count()
      await readd.first().click()
      await expect(albumTiles, 'das wieder aufgenommene Foto im Raster').toHaveCount(count + 1)
    }
  }

  const addTrigger = section.getByRole('button', { name: /^Foto hinzufügen: / })
  for (;;) {
    if ((await addTrigger.getAttribute('aria-expanded')) !== 'true') {
      await addTrigger.click()
    }
    const panel = section.locator(`[id="${await addTrigger.getAttribute('aria-controls')}"]`)
    const add = panel.getByRole('button', { name: /^Hinzufügen: / })
    // Zielzustand statt Wartezeit: Kandidaten ODER der Leertext des Panels.
    await expect(add.first().or(panel.locator(':scope > p'))).toBeVisible()
    if ((await add.count()) === 0) {
      await addTrigger.click()
      return albumTiles.count()
    }
    const count = await albumTiles.count()
    await add.first().click()
    await expect(albumTiles, 'das hinzugefuegte Foto im Raster').toHaveCount(count + 1)
  }
}

/**
 * Der geseedete Entwurf traegt je Event nur ein Foto - zu wenig fuer eine Reihe. Die Events werden
 * deshalb ueber die Oberflaeche aufgefuellt und im `finally` ueber die API zurueckgesetzt.
 */
test('Album-Entwurf: Hoch- und Querformat ruhig in einer Reihe, Band unter seiner Reihe', async ({
  page,
}) => {
  // Auffuellen sind gut ein Dutzend einzeln geschriebene Handgriffe ueber vier Events.
  test.slow()
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.setViewportSize({ width: 1280, height: VIEWPORT_HEIGHT })
  await page.goto(`/projects/${projectId}/album`)
  await expect(page.getByRole('button', { name: /^Streichen: / }).first()).toBeVisible()
  const before = await readOwnDraftStates(page, projectId)

  try {
    // AK3/AK4 bei 1280 px: eine Reihe mit Hoch- UND Querformat, gesucht ueber alle Events.
    const sections = page.locator('section[data-draft-position]')
    const rows: TileMeasurement[][] = []
    let fullestIndex = 0
    let fullestCount = 0
    for (let index = 0; index < (await sections.count()); index += 1) {
      const section = sections.nth(index)
      const count = await takeEverything(section)
      if (count > 0) {
        rows.push(...rowsOf((await measureGrid(section.locator(':scope > ul').first())).tiles))
      }
      if (count > fullestCount) {
        fullestIndex = index
        fullestCount = count
      }
    }
    // Vorbedingung gegen den trivialen Gruen-Fall: ein rein quadratischer Bestand bewiese nichts.
    const mixedRow = rows.find((row) => row.some(isPortrait) && row.some(isLandscape))
    expect(mixedRow, 'eine Reihe mit Hoch- UND Querformat im Demo-Bestand').toBeDefined()
    const portrait = mixedRow?.find(isPortrait)
    const landscape = mixedRow?.find(isLandscape)

    for (const tile of [portrait, landscape]) {
      expect(tile?.objectFit, 'Bild eingepasst statt beschnitten').toBe('contain')
    }
    expect(
      Math.abs((portrait?.area.width ?? 0) - (landscape?.area.width ?? -9)),
      'gleich breite Bildflaeche bei Hoch- und Querformat',
    ).toBeLessThanOrEqual(TOLERANCE)
    expect(
      Math.abs((portrait?.area.height ?? 0) - (landscape?.area.height ?? -9)),
      'gleich hohe Bildflaeche bei Hoch- und Querformat',
    ).toBeLessThanOrEqual(TOLERANCE)
    for (const key of ['cornerHandle', 'belowArea'] as const) {
      const a = portrait?.[key]
      const b = landscape?.[key]
      expect(a, `${key} der Hochformat-Kachel`).not.toBeNull()
      expect(b, `${key} der Querformat-Kachel`).not.toBeNull()
      expect(Math.abs((a?.x ?? 0) - (b?.x ?? -9)), `${key}: waagerechte Lage`).toBeLessThanOrEqual(
        TOLERANCE,
      )
      expect(Math.abs((a?.y ?? 0) - (b?.y ?? -9)), `${key}: senkrechte Lage`).toBeLessThanOrEqual(
        TOLERANCE,
      )
    }

    // AK2 bei 800 px (drei Spalten): Das Band schliesst die Reihe seiner Kachel ab. Der Demo-Bestand
    // traegt je Event hoechstens zwei Fotos; mit dem Hinzufuegen-Feld ist das genau eine volle
    // Reihe zu drei Zellen - das Band muss hinter allen dreien stehen, nicht schon nach zweien.
    await page.setViewportSize({ width: 800, height: VIEWPORT_HEIGHT })
    expect(fullestCount, 'ein Event mit mindestens zwei Albumkacheln').toBeGreaterThanOrEqual(2)
    const grid = sections.nth(fullestIndex).locator(':scope > ul').first()
    await expect.poll(async () => (await measureGrid(grid)).columns).toBe(3)
    const trigger = grid.getByRole('button', { name: /^Alternativen: / }).first()
    await trigger.click()
    const bandId = await trigger.getAttribute('aria-controls')
    await expect(page.locator(`[id="${bandId}"]`), 'geoeffnetes Band').toBeVisible()

    const placement = await grid.evaluate((list, id) => {
      const children = [...list.children]
      const preceding = children.slice(
        0,
        children.findIndex((child) => child.id === id),
      )
      const tops = preceding.map((child) => child.getBoundingClientRect().top)
      return {
        cellsBefore: preceding.length,
        rowsBefore: new Set(tops.map((top) => Math.round(top))).size,
        lastRowBottom: Math.max(...preceding.map((child) => child.getBoundingClientRect().bottom)),
        bandTop: document.getElementById(id ?? '')?.getBoundingClientRect().top ?? 0,
      }
    }, bandId)

    expect(
      placement.cellsBefore,
      'Zellen vor dem Band (die volle Reihe der ausloesenden Kachel)',
    ).toBe(Math.min(3, fullestCount + 1))
    expect(placement.rowsBefore, 'die Zellen vor dem Band bilden genau eine Reihe').toBe(1)
    expect(placement.bandTop, 'Band unter der Reihe der ausloesenden Kachel').toBeGreaterThan(
      placement.lastRowBottom - TOLERANCE,
    )
  } finally {
    await restoreOwnDraftStates(page, projectId, before)
  }
})

test('Endauswahl: Spaltenleiter 2/3/4, eingepasste Bilder, ruhige Reihe', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

  for (const { width, columns } of LADDER) {
    await page.setViewportSize({ width, height: VIEWPORT_HEIGHT })
    await page.goto(`/projects/${projectId}/selection`)
    expectLadderStep(
      await measureGrid(selectionGrid(page)),
      columns,
      `in der Arbeitssicht der Endauswahl bei ${width} px`,
    )
  }

  // Die Ergebnissicht ist ein anderes DOM - bei der breitesten Stufe, wo die Leiter endet.
  await page.getByRole('button', { name: 'Endauswahl', exact: true }).click()
  await expect(
    page.getByRole('button', { name: SELECTION_TILE_CONTROL }).first(),
    'mindestens eine Kachel in der Ergebnissicht',
  ).toBeVisible()
  expectLadderStep(
    await measureGrid(selectionGrid(page)),
    4,
    'in der Ergebnissicht der Endauswahl bei 1280 px',
  )
})
