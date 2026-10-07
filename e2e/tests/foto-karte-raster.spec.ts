/**
 * Die Raster der Kuratierungskachel in Album-Entwurf, Alternativen-Band, Hinzufuegen-Panel und
 * Endauswahl - gemessen im echten Browser (specs/features/0579-kuratierungskacheln-foto-im-
 * mittelpunkt.md). jsdom hat keine Layout-Engine; hier steht die Wirkung der gerechneten Reihen.
 *
 * Je Raster: Bildflaeche im Seitenverhaeltnis des Fotos, gleiche Hoehe je Reihe, volle Reihe
 * buendig, Reihenhoehe bei 1280 px in [200, 350], jede Kachel >= 100 px, Knopfzeile einzeilig und
 * nicht breiter als die Kachel, Symbolmodus genau unterhalb der Schwelle der Kachelart.
 *
 * An EIN Projekt gebunden (`DESKTOP_ONLY`): Die Datei setzt ihre Breiten selbst.
 */

import type { Locator, Page } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId, photoTiles } from '../lib/demo.ts'
import { readOwnDraftStates, restoreOwnDraftStates } from '../lib/draft.ts'
import { expect, test } from '../lib/fixtures.ts'

const VIEWPORT_HEIGHT = 900
const WIDTHS = [360, 1280] as const
const TOLERANCE = 1
const SAME_ROW_TOLERANCE = 2
const TARGET_ROW_HEIGHT = 280
const IMAGE_LOAD_TIMEOUT_MS = 30_000
/** `HANDLES_FULL_WIDTH_PX` aus frontend/src/utils/curationLayout.ts, je erster Handlung. */
const THRESHOLDS: Record<string, number> = {
  Streichen: 208,
  'Wieder aufnehmen': 146,
  Tauschen: 206,
  Hinzufügen: 102,
  contested: 248,
  single: 124,
}

interface Tile {
  top: number
  width: number
  imageWidth: number
  imageHeight: number
  ratio: number
  objectFit: string
  rowWidth: number
  buttonTops: number[]
  kind: string
  iconOnly: boolean
}

interface Grid {
  width: number
  gap: number
  tiles: Tile[]
}

async function measure(grid: Locator): Promise<Grid> {
  await expect(grid.locator(':scope > li img').first()).toBeVisible()
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
    const style = window.getComputedStyle(list)
    const tiles = [...list.querySelectorAll(':scope > li')].flatMap((tile) => {
      const image = tile.querySelector('img')
      const buttons = [...tile.querySelectorAll('button[aria-label]')].filter(
        (button) => !/^Großansicht: /.test(button.getAttribute('aria-label') ?? ''),
      )
      if (image === null || buttons.length === 0) {
        return []
      }
      const area = image.parentElement!.getBoundingClientRect()
      const rect = tile.getBoundingClientRect()
      const row = buttons[0]!.parentElement!.getBoundingClientRect()
      const labels = buttons.map((button) => button.getAttribute('aria-label')!.split(':')[0])
      const kind = labels.includes('Nicht aufnehmen')
        ? 'contested'
        : labels[0] === 'Aufnehmen' || labels[0] === 'Herausnehmen'
          ? 'single'
          : (labels[0] ?? '')
      return [
        {
          top: rect.top,
          width: rect.width,
          imageWidth: area.width,
          imageHeight: area.height,
          ratio: image.naturalWidth / image.naturalHeight,
          objectFit: window.getComputedStyle(image).objectFit,
          rowWidth: row.width,
          buttonTops: buttons.map((button) => Math.round(button.getBoundingClientRect().top)),
          kind,
          iconOnly: buttons[0]!.querySelector('[data-tile-action-hint]') !== null,
        },
      ]
    })
    return {
      width: list.getBoundingClientRect().width,
      gap: parseFloat(style.columnGap) || 0,
      tiles,
    }
  })
}

function rowsOf(tiles: Tile[]): Tile[][] {
  const rows: Tile[][] = []
  for (const tile of tiles) {
    const row = rows.find((r) => Math.abs(r[0]!.top - tile.top) <= SAME_ROW_TOLERANCE)
    if (row === undefined) rows.push([tile])
    else row.push(tile)
  }
  return rows
}

function expectCurationGrid(grid: Grid, viewport: number, label: string): void {
  expect(grid.tiles.length, `Kacheln ${label}`).toBeGreaterThan(0)
  for (const tile of grid.tiles) {
    expect(tile.objectFit, `object-fit ${label}`).toBe('contain')
    if (tile.ratio >= 0.5) {
      expect(
        Math.abs(tile.imageWidth / tile.ratio - tile.imageHeight),
        `Bildflaeche im Verhaeltnis des Fotos ${label}`,
      ).toBeLessThanOrEqual(TOLERANCE + 0.5)
    }
    expect(tile.width, `Kachel >= 100 px ${label}`).toBeGreaterThanOrEqual(100 - TOLERANCE)
    expect(tile.rowWidth, `Knopfzeile <= Kachel ${label}`).toBeLessThanOrEqual(
      tile.width + TOLERANCE,
    )
    expect(new Set(tile.buttonTops).size, `Knopfzeile einzeilig ${label}`).toBe(1)
    const threshold = THRESHOLDS[tile.kind]
    expect(threshold, `bekannte Kachelart ${tile.kind}`).toBeDefined()
    expect(tile.iconOnly, `Symbolmodus bei ${tile.width}px (${tile.kind}) ${label}`).toBe(
      Math.round(tile.width) < (threshold ?? 0),
    )
  }
  const rows = rowsOf(grid.tiles)
  rows.forEach((row, index) => {
    const height = row[0]!.imageHeight
    for (const tile of row) {
      expect(
        Math.abs(tile.imageHeight - height),
        `gleiche Hoehe je Reihe ${label}`,
      ).toBeLessThanOrEqual(TOLERANCE)
    }
    const natural = Math.abs(height - TARGET_ROW_HEIGHT) <= TOLERANCE
    if (index < rows.length - 1 && !natural) {
      const sum = row.reduce((total, tile) => total + tile.width, 0) + grid.gap * (row.length - 1)
      expect(Math.abs(sum - grid.width), `volle Reihe buendig ${label}`).toBeLessThanOrEqual(
        TOLERANCE + row.length,
      )
    }
    if (viewport === 1280 && row.length > 1) {
      expect(height, `Reihenhoehe ${label}`).toBeGreaterThanOrEqual(200 - TOLERANCE)
      expect(height, `Reihenhoehe ${label}`).toBeLessThanOrEqual(350 + TOLERANCE)
    }
  })
}

function draftGrid(page: Page): Locator {
  return page.locator('section[data-draft-position] > ul').first()
}

async function panelGrid(page: Page, trigger: Locator): Promise<Locator> {
  const panel = page.locator(`[id="${await trigger.getAttribute('aria-controls')}"]`)
  return panel.locator(':scope > :is(ul, ol):not([role="status"])')
}

test('Album-Entwurf, Band und Panel: justierte Reihen, Symbolmodus nach Breite', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: VIEWPORT_HEIGHT })
    await page.goto(`/projects/${projectId}/album`)
    expectCurationGrid(await measure(draftGrid(page)), width, `im Entwurf bei ${width} px`)

    const alternatives = page.getByRole('button', { name: /^Alternativen: / }).first()
    await alternatives.click()
    expectCurationGrid(
      await measure(await panelGrid(page, alternatives)),
      width,
      `im Band bei ${width} px`,
    )
    await alternatives.click()

    const addTrigger = page.getByRole('button', { name: /^Foto hinzufügen: / }).first()
    await addTrigger.click()
    expectCurationGrid(
      await measure(await panelGrid(page, addTrigger)),
      width,
      `im Panel bei ${width} px`,
    )
    await addTrigger.click()
  }
})

test('Endauswahl: justierte Reihen in Arbeits- und Ergebnissicht', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  const grid = page
    .locator('ul')
    .filter({
      has: page.getByRole('button', { name: /^(Aufnehmen|Nicht aufnehmen|Herausnehmen): / }),
    })
    .first()
  for (const width of WIDTHS) {
    await page.setViewportSize({ width, height: VIEWPORT_HEIGHT })
    await page.goto(`/projects/${projectId}/selection`)
    expectCurationGrid(await measure(grid), width, `Arbeitssicht bei ${width} px`)
    await page.getByRole('button', { name: 'Endauswahl', exact: true }).click()
    expectCurationGrid(await measure(grid), width, `Ergebnissicht bei ${width} px`)
  }
})

/**
 * Der geseedete Entwurf traegt je Event nur ein Foto. Das Event wird ueber die Oberflaeche mit
 * seinen gestrichenen Fotos aufgefuellt (das einzige Hochformat ist gestrichen) und im `finally`
 * ueber die API zurueckgesetzt.
 */
test('Album-Entwurf: Hoch- und Querformat in einer Reihe, Band hinter der gerechneten Reihe', async ({
  page,
}) => {
  test.slow()
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.setViewportSize({ width: 1280, height: VIEWPORT_HEIGHT })
  await page.goto(`/projects/${projectId}/album`)
  await expect(page.getByRole('button', { name: /^Streichen: / }).first()).toBeVisible()
  const before = await readOwnDraftStates(page, projectId)

  try {
    const sections = page.locator('section[data-draft-position]')
    let mixed: Locator | null = null
    for (let index = 0; index < (await sections.count()); index += 1) {
      const section = sections.nth(index)
      const toggle = section.getByRole('button', { name: /^\d+ gestrichen – anzeigen$/ })
      if ((await toggle.count()) > 0) {
        await toggle.click()
        const readd = section.getByRole('button', { name: /^Wieder aufnehmen: / })
        while ((await readd.count()) > 0) {
          const count = await section.getByRole('button', { name: /^Streichen: / }).count()
          await readd.first().click()
          await expect(section.getByRole('button', { name: /^Streichen: / })).toHaveCount(count + 1)
        }
      }
      const grid = section.locator(':scope > ul').first()
      const tiles = (await measure(grid)).tiles
      if (tiles.some((t) => t.ratio < 1) && tiles.some((t) => t.ratio > 1)) {
        mixed = grid
        expectCurationGrid(await measure(grid), 1280, 'gemischte Reihe bei 1280 px')
        break
      }
    }
    expect(mixed, 'ein Event mit Hoch- UND Querformat').not.toBeNull()

    const trigger = mixed!.getByRole('button', { name: /^Alternativen: / }).first()
    await trigger.click()
    const bandId = await trigger.getAttribute('aria-controls')
    await expect(page.locator(`[id="${bandId}"]`)).toBeVisible()
    const placement = await mixed!.evaluate((list, id) => {
      const children = [...list.children]
      const bandIndex = children.findIndex((child) => child.id === id)
      const triggerTile = children.find((child) =>
        child.querySelector('button[aria-expanded="true"][aria-label^="Alternativen: "]'),
      )!
      const rowTop = triggerTile.getBoundingClientRect().top
      const before = children[bandIndex - 1]!.getBoundingClientRect()
      const after = children[bandIndex + 1]?.getBoundingClientRect()
      return {
        lastOfRow: Math.abs(before.top - rowTop) <= 2,
        nextBelow: after === undefined || after.top > rowTop + 2,
        bandFull:
          Math.abs(
            document.getElementById(id ?? '')!.getBoundingClientRect().width -
              list.getBoundingClientRect().width,
          ) <= 1,
      }
    }, bandId)
    expect(placement.lastOfRow, 'Band folgt der letzten Kachel der Reihe').toBe(true)
    expect(placement.nextBelow, 'nach dem Band beginnt eine neue Reihe').toBe(true)
    expect(placement.bandFull, 'Band ueber die volle Breite').toBe(true)
  } finally {
    await restoreOwnDraftStates(page, projectId, before)
  }
})

test('Leiste bei Bedarf: Hover und Tab-Fokus, innerhalb der Bildflaeche', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.setViewportSize({ width: 1280, height: VIEWPORT_HEIGHT })
  await page.goto(`/projects/${projectId}/album`)
  const tile = draftGrid(page).locator(':scope > li').first()
  const details = tile.locator('[data-tile-details]')
  await expect(details).not.toHaveAttribute('data-visible', 'true')

  await tile.locator('img').hover()
  await expect(details).toHaveAttribute('data-visible', 'true')
  const image = await tile.locator('img').locator('..').boundingBox()
  const strip = await details.boundingBox()
  expect(strip!.y).toBeGreaterThanOrEqual(image!.y - TOLERANCE)
  expect(strip!.y + strip!.height).toBeLessThanOrEqual(image!.y + image!.height + TOLERANCE)
  await page.mouse.move(0, 0)
  await expect(details).not.toHaveAttribute('data-visible', 'true')

  await tile.getByRole('button', { name: /^Großansicht: / }).focus()
  await page.keyboard.press('Tab')
  await expect(details).toHaveAttribute('data-visible', 'true')
})

/**
 * Kurzbeschriftung im Symbolmodus, DETERMINISTISCH: Die echte Entwurfsantwort wird durchgereicht,
 * nur `aspect_ratio` jedes Fotos auf 1:2 gesetzt (Antwort-Eingriff fuer eine Geometrie-Zusage,
 * Testkonzept). Bei 360 px teilt sich jedes Foto mit dem 2:3-Hinzufuegen-Feld eine Reihe und ist
 * damit sicher schmaler als die Schwelle der Entwurfskachel.
 */
test('Kurzbeschriftung im Symbolmodus: bei Hover und Tastaturfokus sichtbar, innerhalb der Kachel', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.route('**/api/projects/*/album-draft*', async (route) => {
    const response = await route.fetch()
    const json = (await response.json()) as { items: { aspect_ratio: number | null }[] }
    json.items = json.items.map((item) => ({ ...item, aspect_ratio: 0.5 }))
    await route.fulfill({ response, json })
  })
  await page.setViewportSize({ width: 360, height: VIEWPORT_HEIGHT })
  await page.goto(`/projects/${projectId}/album`)

  const tile = draftGrid(page).locator(':scope > li').first()
  const strike = tile.getByRole('button', { name: /^Streichen: / })
  const alternatives = tile.getByRole('button', { name: /^Alternativen: / })
  await expect(strike, 'Vorbedingung: Symbolmodus').toHaveCount(1)
  const tileBox = (await tile.boundingBox())!
  expect(tileBox.width, 'Vorbedingung: Kachel schmaler als 208 px').toBeLessThan(208)

  const firstHint = strike.locator('[data-tile-action-hint]')
  const secondHint = alternatives.locator('[data-tile-action-hint]')
  await expect(firstHint).toBeHidden()
  await expect(secondHint).toBeHidden()

  // Hover: erster Knopf, Hinweis linksbuendig in der Kachel.
  await strike.hover()
  await expect(firstHint).toBeVisible()
  await expect(firstHint).toHaveText('Streichen')
  const hover = (await firstHint.boundingBox())!
  expect(hover.x, 'Hinweis links nicht ausserhalb der Kachel').toBeGreaterThanOrEqual(
    tileBox.x - TOLERANCE,
  )
  expect(hover.x + hover.width, 'Hinweis rechts nicht ausserhalb der Kachel').toBeLessThanOrEqual(
    tileBox.x + tileBox.width + TOLERANCE,
  )
  // Lage RELATIV ZUM KNOPF, nicht nur zur Kachel: linksbuendig am ersten Knopf und darueber. Ein
  // fehlender Positionskontext setzte den Hinweis an den naechsten positionierten Vorfahren.
  const strikeBox = (await strike.boundingBox())!
  expect(Math.abs(hover.x - strikeBox.x), 'linksbuendig am ersten Knopf').toBeLessThanOrEqual(
    TOLERANCE,
  )
  expect(hover.y + hover.height, 'Hinweis ueber dem ersten Knopf').toBeLessThanOrEqual(
    strikeBox.y + TOLERANCE,
  )
  expect(
    strikeBox.y - (hover.y + hover.height),
    'Hinweis dicht ueber dem Knopf',
  ).toBeLessThanOrEqual(8)
  await page.mouse.move(0, 0)
  await expect(firstHint).toBeHidden()

  // Tastaturfokus: zweiter Knopf, Hinweis rechtsbuendig in der Kachel.
  await strike.focus()
  await page.keyboard.press('Tab')
  await expect(alternatives).toBeFocused()
  await expect(secondHint).toBeVisible()
  await expect(secondHint).toHaveText('Alternativen')
  const focus = (await secondHint.boundingBox())!
  const buttonBox = (await alternatives.boundingBox())!
  expect(
    Math.abs(focus.x + focus.width - (buttonBox.x + buttonBox.width)),
    'rechtsbuendig am zweiten Knopf',
  ).toBeLessThanOrEqual(TOLERANCE)
  expect(focus.x, 'Hinweis links nicht ausserhalb der Kachel').toBeGreaterThanOrEqual(
    tileBox.x - TOLERANCE,
  )
  expect(focus.y + focus.height, 'Hinweis ueber dem Knopf').toBeLessThanOrEqual(
    buttonBox.y + TOLERANCE,
  )
})

/**
 * Langer Grund in schmaler Kachel: 160 Zeichen bei etwa 100 px Kachelbreite. Die Leiste bleibt
 * innerhalb der Bildflaeche und laesst sich bis zum Dateinamen scrollen - nichts wird abgeschnitten.
 * Antwort-Eingriff wie oben: echte Entwurfsantwort, nur Verhaeltnis und Begruendung gesetzt.
 */
test('lange Begruendung in einer 100-px-Kachel bleibt vollstaendig erreichbar', async ({
  page,
}) => {
  const reason = 'Gesichter scharf, Licht weich und warm, Hintergrund ruhig. '
    .repeat(3)
    .slice(0, 160)
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.route('**/api/projects/*/album-draft*', async (route) => {
    const response = await route.fetch()
    const json = (await response.json()) as {
      items: { aspect_ratio: number | null; album_suitability: unknown }[]
    }
    json.items = json.items.map((item) => ({
      ...item,
      aspect_ratio: 0.5,
      album_suitability: { level: 3, reason },
    }))
    await route.fulfill({ response, json })
  })
  await page.setViewportSize({ width: 280, height: VIEWPORT_HEIGHT })
  await page.goto(`/projects/${projectId}/album`)

  const tile = draftGrid(page).locator(':scope > li').first()
  const image = tile.getByRole('button', { name: /^Großansicht: / })
  await expect(image).toBeVisible()
  const tileBox = (await tile.boundingBox())!
  expect(tileBox.width, 'Vorbedingung: Kachel um 100 px').toBeLessThanOrEqual(110)
  expect(tileBox.width).toBeGreaterThanOrEqual(100 - TOLERANCE)

  await image.hover()
  const strip = tile.locator('[data-tile-details]')
  await expect(strip).toHaveAttribute('data-visible', 'true')
  await expect(strip.locator('[data-album-suitability-reason]')).toContainText(reason)

  const imageBox = (await image.boundingBox())!
  const stripBox = (await strip.boundingBox())!
  expect(stripBox.y, 'Leiste nicht ueber der Bildflaeche').toBeGreaterThanOrEqual(
    imageBox.y - TOLERANCE,
  )
  expect(stripBox.y + stripBox.height, 'Leiste nicht unter der Bildflaeche').toBeLessThanOrEqual(
    imageBox.y + imageBox.height + TOLERANCE,
  )

  // Bis ans Ende scrollen: Der Dateiname - die letzte Zeile - steht dann sichtbar in der Leiste.
  const overflow = await strip.evaluate((element) => {
    element.scrollTop = element.scrollHeight
    return element.scrollHeight > element.clientHeight
  })
  expect(overflow, 'Vorbedingung: der Inhalt ist hoeher als die Leiste').toBe(true)
  await expect(strip).toHaveAttribute('tabindex', '0')
  const fileName = strip.locator(':scope > p').last()
  const nameBox = (await fileName.boundingBox())!
  const scrolled = (await strip.boundingBox())!
  expect(nameBox.y + nameBox.height, 'Dateiname nach dem Scrollen sichtbar').toBeLessThanOrEqual(
    scrolled.y + scrolled.height + TOLERANCE,
  )
  expect(nameBox.y).toBeGreaterThanOrEqual(scrolled.y - TOLERANCE)
})

test.describe('Telefon (Touch, ohne Hover)', () => {
  test.use({ viewport: { width: 360, height: 800 }, hasTouch: true, isMobile: true })

  test('langer Druck zeigt die Leiste und oeffnet keine Grossansicht', async ({ page }) => {
    const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
    await page.goto(`/projects/${projectId}/album`)
    const tile = draftGrid(page).locator(':scope > li').first()
    const trigger = tile.getByRole('button', { name: /^Großansicht: / })
    const details = tile.locator('[data-tile-details]')
    await expect(trigger).toBeVisible()

    // Kurzer Druck: keine Leiste.
    await trigger.dispatchEvent('pointerdown', { pointerType: 'touch' })
    await page.waitForTimeout(200)
    await trigger.dispatchEvent('pointerup', { pointerType: 'touch' })
    await expect(details).not.toHaveAttribute('data-visible', 'true')

    // Langer Druck (>= 500 ms): Leiste sichtbar, der folgende Klick oeffnet nichts.
    await trigger.dispatchEvent('pointerdown', { pointerType: 'touch' })
    await page.waitForTimeout(700)
    await trigger.dispatchEvent('pointerup', { pointerType: 'touch' })
    await trigger.dispatchEvent('click')
    await expect(details).toHaveAttribute('data-visible', 'true')
    await expect(page.getByRole('dialog')).toHaveCount(0)
  })

  /*
   * Spec 0585: Ein kurzes Tippen oeffnet NUR die Grossansicht. Getippt wird mit `locator.tap()`,
   * nicht mit `dispatchEvent` - synthetisch verschickte Ereignisse fokussieren nicht, und der Fehler
   * hing gerade am Fokus, den das Tippen setzt (und den die Grossansicht beim Schliessen
   * zurueckgibt). Der Abschnitt "kurzer Druck" oben blieb deshalb gegen den Fehler gruen.
   */
  test('kurzes Tippen oeffnet nur die Grossansicht, auch nach dem Schliessen keine Leiste', async ({
    page,
  }) => {
    const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
    await page.goto(`/projects/${projectId}/album`)
    const tile = draftGrid(page).locator(':scope > li').first()
    const trigger = tile.getByRole('button', { name: /^Großansicht: / })
    const details = tile.locator('[data-tile-details]')
    await expect(trigger).toBeVisible()

    await trigger.tap()
    await expect(page.getByRole('dialog'), 'Tippen: Grossansicht offen').toHaveCount(1)
    await expect(details, 'Tippen: Leiste waehrend der Grossansicht').not.toHaveAttribute(
      'data-visible',
      'true',
    )

    // Geschlossen wird, wie am Tablet: per Tippen auf „Schließen". Esc ist eine Tastatureingabe -
    // danach meldet der Browser den zurueckgegebenen Fokus zu Recht als Tastaturfokus.
    await page.getByRole('dialog').getByRole('button', { name: 'Schließen' }).tap()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    // Vorbedingung gegen den trivialen Gruen-Fall: Der Fokus IST zurueckgekehrt.
    await expect(trigger, 'Tippen: Fokus nach dem Schliessen zurueck').toBeFocused()
    await expect(details, 'Tippen: Leiste nach dem Schliessen').not.toHaveAttribute(
      'data-visible',
      'true',
    )
  })

  /*
   * Der Kachel-Knopf ist "Alternativen", nicht "Streichen": Eine gestrichene Kachel verlaesst die
   * Ansicht (Spec 0558), dort bliebe keine Kachel, an der die Leiste zu pruefen waere.
   * "Alternativen" schreibt nichts; das Band nimmt beim Oeffnen den Fokus an seine Ueberschrift
   * (Spec 0558), der Knopf bleibt deshalb nicht fokussiert - geprueft wird die Leiste der Kachel.
   */
  test('kurzes Tippen auf einen Kachel-Knopf loest nur dessen Handlung aus, keine Leiste', async ({
    page,
  }) => {
    const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
    await page.goto(`/projects/${projectId}/album`)
    const tile = draftGrid(page).locator(':scope > li').first()
    const alternatives = tile.getByRole('button', { name: /^Alternativen: / })
    await expect(alternatives).toHaveAttribute('aria-expanded', 'false')

    await alternatives.tap()
    await expect(alternatives, 'Knopf: Handlung erfolgt').toHaveAttribute('aria-expanded', 'true')
    await expect(tile.locator('[data-tile-details]'), 'Knopf: Leiste').not.toHaveAttribute(
      'data-visible',
      'true',
    )
    await expect(page.getByRole('dialog')).toHaveCount(0)
  })

  test('kurzes Tippen auf eine Kachel der Fotouebersicht oeffnet nur die Detailansicht', async ({
    page,
  }) => {
    const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
    await page.goto(`/projects/${projectId}/photos`)
    const tile = photoTiles(page).first()
    await expect(tile).toBeVisible()
    const fileName = (await tile.locator('img').first().getAttribute('alt'))!.split('/').pop()!
    // Vorbedingung: Der Dateiname steht im Ruhezustand nicht im Dokument - er waere sonst kein
    // Merkmal der eingeblendeten Zeile.
    await expect(tile.getByText(fileName, { exact: true })).toHaveCount(0)

    await tile.getByRole('link').first().tap()
    await expect(
      page.getByRole('group', { name: 'Bewertung' }),
      'Detailansicht offen',
    ).toBeVisible()

    await page.goBack()
    const back = photoTiles(page).first()
    await expect(back).toBeVisible()
    await expect(back.getByText(fileName, { exact: true }), 'Zeile nach der Rueckkehr').toHaveCount(
      0,
    )
  })
})
