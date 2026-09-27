/**
 * Die Vergleichsansicht in echter Geometrie (specs/features/0533-duplikatstapel-vergleichsansicht.md,
 * A4/A6/A11). jsdom kennt keine Layout-Engine: Ob die Wahlzeile in ihre Karte passt, ob die
 * Seitenspalte neben oder unter der Buehne steht und ob das Buehnenbild unverfaelscht getroffen
 * wird, laesst sich nur hier messen. Der Spec bleibt LESEND - er klickt keine Entscheidung.
 *
 * Er laeuft in beiden Viewport-Projekten; die Anordnung der Grossansicht haengt an der Breite und
 * wird je Projekt gegen die dort geltende Erwartung geprueft.
 */

import type { Page } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId, duplicateTiles, openDuplicateGroup } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Subpixel-Toleranz: Chromium meldet Bruchteile, ein echter Ueberstand ist groesser. */
const TOLERANCE = 1
/** `lg` - ab hier steht die Seitenspalte neben der Buehne. */
const LG_BREAKPOINT = 1024

async function openEnlarged(page: Page): Promise<void> {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  await openDuplicateGroup(page, projectId, 'gross')
  await duplicateTiles(page)
    .nth(1)
    .getByRole('button', { name: /vergrößern$/ })
    .click()
  // Vorbedingung: die Grossansicht ist WIRKLICH offen. Ohne sie mass der Spec das Raster.
  await expect(
    page.getByRole('heading', { level: 2, name: /^Aufnahme 2 von \d+$/ }),
    'Grossansicht offen',
  ).toBeVisible()
}

test('die Wahlschaltflaechen liegen vollstaendig im Rechteck ihrer Karte', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  await openDuplicateGroup(page, projectId, 'gross')

  const karten = duplicateTiles(page)
  const anzahl = await karten.count()
  let gemessen = 0
  for (let index = 0; index < anzahl; index += 1) {
    const karte = karten.nth(index)
    const knoepfe = karte.getByRole('button', { name: /^(Behalten|Ausschuss): / })
    if ((await knoepfe.count()) === 0) {
      continue
    }
    const rahmen = await karte.boundingBox()
    expect(rahmen, `Karte ${index + 1}`).not.toBeNull()
    for (const knopf of await knoepfe.all()) {
      const box = await knopf.boundingBox()
      expect(box).not.toBeNull()
      if (rahmen === null || box === null) {
        continue
      }
      expect(box.x, `linke Kante in Karte ${index + 1}`).toBeGreaterThanOrEqual(
        rahmen.x - TOLERANCE,
      )
      expect(box.x + box.width, `rechte Kante in Karte ${index + 1}`).toBeLessThanOrEqual(
        rahmen.x + rahmen.width + TOLERANCE,
      )
      expect(box.y + box.height, `Unterkante in Karte ${index + 1}`).toBeLessThanOrEqual(
        rahmen.y + rahmen.height + TOLERANCE,
      )
    }
    gemessen += 1
  }
  // Ohne diese Zeile bestuende der Fall auch, wenn keine Karte eine Wahlzeile truege.
  expect(gemessen, 'Karten mit Wahlzeile').toBeGreaterThan(0)
})

test('die Grossansicht ordnet Buehne, Seitenspalte und Streifen nach der Breite an', async ({
  page,
}) => {
  await openEnlarged(page)
  const breite = page.viewportSize()?.width ?? 0

  const buehne = await page.getByTestId('duplicate-stage').boundingBox()
  const spalte = await page.getByTestId('duplicate-sidebar').boundingBox()
  const streifenLocator = page.getByRole('list', { name: 'Alle Aufnahmen der Gruppe' })
  const streifen = await streifenLocator.boundingBox()
  expect(buehne && spalte && streifen, 'alle drei Bereiche gerendert').toBeTruthy()
  if (buehne === null || spalte === null || streifen === null) {
    return
  }

  if (breite >= LG_BREAKPOINT) {
    // Nebeneinander: waagerecht disjunkt rechts, senkrecht ueberlappend.
    expect(spalte.x, 'Seitenspalte rechts der Buehne').toBeGreaterThanOrEqual(
      buehne.x + buehne.width - TOLERANCE,
    )
    expect(spalte.y, 'Seitenspalte beginnt vor dem Ende der Buehne').toBeLessThan(
      buehne.y + buehne.height,
    )
  } else {
    // Untereinander: die Seitenspalte beginnt unter der Buehne.
    expect(spalte.y, 'Seitenspalte unter der Buehne').toBeGreaterThanOrEqual(
      buehne.y + buehne.height - TOLERANCE,
    )
  }
  expect(streifen.y, 'Streifen unter Buehne und Seitenspalte').toBeGreaterThanOrEqual(
    Math.max(buehne.y + buehne.height, spalte.y + spalte.height) - TOLERANCE,
  )

  const streifenBreiten = await streifenLocator.evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }))
  expect(streifenBreiten.scrollWidth, 'Streifen scrollt nie waagerecht').toBeLessThanOrEqual(
    streifenBreiten.clientWidth + TOLERANCE,
  )
})

test('das Buehnenbild wird an allen vier Ecken selbst getroffen', async ({ page }) => {
  await openEnlarged(page)

  const bild = page.getByTestId('duplicate-stage').getByRole('img')
  await expect(bild, 'Buehnenbild').toBeVisible()
  // Vorbedingung: das Bild ist geladen - erst dann steht das Inhaltsrechteck fest.
  await expect
    .poll(() => bild.evaluate((element) => (element as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0)

  const treffer = await bild.evaluate((element) => {
    const img = element as HTMLImageElement
    // Mittig in den Sichtbereich: Die sticky Kopfzeile laege sonst ueber den oberen Ecken.
    img.scrollIntoView({ block: 'center' })
    const rect = img.getBoundingClientRect()
    // Das Inhaltsrechteck von `object-contain`: eingepasst und mittig.
    const scale = Math.min(rect.width / img.naturalWidth, rect.height / img.naturalHeight)
    const breite = img.naturalWidth * scale
    const hoehe = img.naturalHeight * scale
    const links = rect.x + (rect.width - breite) / 2
    const oben = rect.y + (rect.height - hoehe) / 2
    const rand = 2
    const ecken: [number, number][] = [
      [links + rand, oben + rand],
      [links + breite - rand, oben + rand],
      [links + rand, oben + hoehe - rand],
      [links + breite - rand, oben + hoehe - rand],
    ]
    return ecken.map(([x, y]) => {
      const getroffen = document.elementFromPoint(x, y)
      return getroffen === img ? 'Bild' : `<${getroffen?.tagName.toLowerCase() ?? 'nichts'}>`
    })
  })

  expect(treffer, 'nichts liegt ueber dem Buehnenbild').toEqual(['Bild', 'Bild', 'Bild', 'Bild'])
})
