/**
 * Die Duplikat-Stapel der Ausschuss-Uebersicht in echter Geometrie
 * (specs/features/0533-duplikatstapel-vergleichsansicht.md, B1/B4/B5), in beiden Viewport-Projekten.
 *
 * `pointer-events: none` macht die hinteren Karten fuer `elementFromPoint` unsichtbar. „Verdeckt
 * nicht" wird deshalb ueber das Enthaltensein der Rechtecke nachgewiesen, „kein eigenes Ziel" per
 * Treffertest auf die NUR von ihnen belegte Flaeche: Dort muss der eine Link liegen.
 */

import type { Locator, Page } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

const TOLERANCE = 1
const STAPEL_NAME = /^Duplikat-Gruppe mit \d+ Aufnahmen vergleichen/

async function openStacks(page: Page): Promise<Locator> {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  await page.goto(`/projects/${projectId}/pipeline/ausschuss`)
  const stapel = page
    .getByRole('listitem')
    .filter({ has: page.getByRole('link', { name: STAPEL_NAME }) })
  // Vorbedingung: GENAU zwei Stapel - der Demo-Bestand fuehrt zwei Gruppen. Weniger hiesse, dass
  // die Uebersicht nicht gruppiert; mehr, dass eine Gruppe ueber zwei Eintraege zerfaellt.
  await expect(stapel, 'Stapel der Demo-Duplikate').toHaveCount(2)
  return stapel
}

test('die hinteren Karten ragen oben und rechts ueber die vordere hinaus, innerhalb der Kachel', async ({
  page,
}) => {
  const stapel = await openStacks(page)

  for (const kachel of await stapel.all()) {
    const messung = await kachel.evaluate((li) => {
      const rechteck = (element: Element) => element.getBoundingClientRect()
      const vorne = li.querySelector('img')?.parentElement
      const hinten = Array.from(li.querySelectorAll('[data-stack-card]'))
      return {
        li: rechteck(li),
        vorne: vorne ? rechteck(vorne) : null,
        hinten: hinten.map((karte) => ({
          box: rechteck(karte),
          rand: Number.parseFloat(getComputedStyle(karte).borderTopWidth),
        })),
      }
    })
    expect(messung.vorne, 'vordere Karte mit Titelbild').not.toBeNull()
    expect(messung.hinten, 'zwei hintere Karten').toHaveLength(2)
    const vorne = messung.vorne
    if (vorne === null) {
      continue
    }
    for (const { box, rand } of messung.hinten) {
      expect(rand, 'Rahmenbreite der hinteren Karte').toBeGreaterThan(0)
      expect(box.top, 'hintere Karte ragt oben ueber').toBeLessThanOrEqual(vorne.top - TOLERANCE)
      expect(box.right, 'hintere Karte ragt rechts ueber').toBeGreaterThanOrEqual(
        vorne.right + TOLERANCE,
      )
      expect(box.top, 'innerhalb der Kachel oben').toBeGreaterThanOrEqual(
        messung.li.top - TOLERANCE,
      )
      expect(box.right, 'innerhalb der Kachel rechts').toBeLessThanOrEqual(
        messung.li.right + TOLERANCE,
      )
    }
  }
})

test('die Flaeche der hinteren Karten trifft denselben Link, Kennzeichen und Name liegen vorne', async ({
  page,
}) => {
  const stapel = await openStacks(page)

  for (const kachel of await stapel.all()) {
    await kachel.evaluate((li) => li.scrollIntoView({ block: 'center' }))
    const messung = await kachel.evaluate((li) => {
      const link = li.querySelector('a')
      const rect = li.getBoundingClientRect()
      // Die obere rechte Ecke liegt ausserhalb der vorderen Karte (Versatz 8px) - dort sind nur
      // die hinteren Karten zu sehen.
      const getroffen = document.elementFromPoint(rect.right - 3, rect.top + 3)
      const vorne = li.querySelector('img')?.parentElement?.getBoundingClientRect()
      const enthalten = (element: Element | null | undefined) => {
        if (!element || !vorne) {
          return false
        }
        const box = element.getBoundingClientRect()
        return (
          box.left >= vorne.left - 1 &&
          box.right <= vorne.right + 1 &&
          box.top >= vorne.top - 1 &&
          box.bottom <= vorne.bottom + 1
        )
      }
      const kennzeichen = Array.from(li.querySelectorAll('span')).find(
        (span) => span.textContent === 'Duplikat',
      )
      const dateiname = li.querySelector('.font-mono')
      return {
        trifftLink: getroffen !== null && link !== null && link.contains(getroffen),
        kennzeichenVorne: enthalten(kennzeichen),
        dateinameVorne: enthalten(dateiname),
      }
    })
    expect(messung, 'Treffertest und Enthaltensein').toEqual({
      trifftLink: true,
      kennzeichenVorne: true,
      dateinameVorne: true,
    })
  }
})

test('der Stapel kuerzt ausser dem Dateinamen keine Beschriftung und scrollt nie waagerecht', async ({
  page,
}) => {
  const stapel = await openStacks(page)

  for (const kachel of await stapel.all()) {
    const gekuerzt = await kachel.evaluate((li) =>
      Array.from(li.querySelectorAll('span'))
        .filter((span) => span.children.length === 0 && !span.classList.contains('font-mono'))
        .filter((span) => (span.textContent ?? '').trim() !== '')
        .filter((span) => span.scrollWidth > span.clientWidth + 1)
        .map((span) => span.textContent),
    )
    expect(gekuerzt, 'gekuerzte Beschriftungen ausser dem Dateinamen').toEqual([])
  }

  const dokument = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(dokument.scrollWidth, 'Dokumentbreite der Uebersicht').toBeLessThanOrEqual(
    dokument.clientWidth + TOLERANCE,
  )
})
