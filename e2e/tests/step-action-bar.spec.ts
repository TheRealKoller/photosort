/**
 * Die haftende Aktionsleiste der Schrittseiten (specs/features/0568-schrittseiten-aktionen.md) in
 * echter Geometrie - jsdom kennt kein `position: sticky`.
 *
 * Zugesichert, in beiden Viewport-Projekten:
 *  - Die Leiste liegt beim Aufruf, oben gescrollt und ganz unten gescrollt vollstaendig im
 *    Sichtbereich, und ihre Hauptaktion ist an allen vier Ecken treffbar (`elementFromPoint`).
 *  - Am Seitenende liegen die letzte Kachel und "Mehr laden" oberhalb der Leiste - gemessen gegen
 *    die im selben Lauf gemessene Leistenbox. Das gilt auch nach einmal "Mehr laden".
 *  - In der Detailansicht (`?photo`) verdeckt die Leiste weder die Entscheidungsknoepfe noch
 *    "Schliessen".
 *
 * Rot-Nachweis: siehe PR-Beschreibung - mit `position: static` an der Leiste sind die Lagen
 * "Aufruf" und "oben gescrollt" rot (die Leiste liegt unterhalb des Sichtbereichs), mit
 * `position: fixed; bottom: 0` ist "letzte Kachel oberhalb der Leiste" rot.
 */

import type { Locator, Page } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Subpixel-Toleranz fuer Kantenvergleiche. */
const TOLERANCE = 1

/** Abstand der Treffpunkte vom Rand der Hauptaktion. */
const CORNER_INSET = 2

const ABSCHLUSS = /als Ausschuss übernehmen und abschließen$|^Ausschuss abschließen$/

function leiste(page: Page): Locator {
  return page.getByRole('group', { name: 'Nächste Aktion' })
}

/** Ausschuss-Kacheln (Einzelaufnahmen und Stapel) des Rasters. */
function kacheln(page: Page): Locator {
  return page.locator('[data-ausschuss-grid] > li')
}

interface Box {
  top: number
  bottom: number
}

async function box(locator: Locator): Promise<Box> {
  return locator.evaluate((element) => {
    const rect = element.getBoundingClientRect()
    return { top: rect.top, bottom: rect.bottom }
  })
}

/** Die vier Ecken (leicht nach innen versetzt) und was dort getroffen wird. */
async function eckentreffer(control: Locator): Promise<string[]> {
  return control.evaluate((element, inset) => {
    const rect = element.getBoundingClientRect()
    const ecken: [number, number][] = [
      [rect.left + inset, rect.top + inset],
      [rect.right - inset, rect.top + inset],
      [rect.left + inset, rect.bottom - inset],
      [rect.right - inset, rect.bottom - inset],
    ]
    return ecken.map(([x, y]) => {
      const hit = document.elementFromPoint(x, y)
      if (hit === null) {
        return 'nichts getroffen (Punkt ausserhalb des Sichtbereichs)'
      }
      return hit === element || element.contains(hit)
        ? 'Hauptaktion'
        : `Fremdelement <${hit.tagName.toLowerCase()}>`
    })
  }, CORNER_INSET)
}

/** Leiste vollstaendig im Sichtbereich, Hauptaktion an allen vier Ecken treffbar. */
async function pruefeLeiste(page: Page, lage: string): Promise<Box> {
  const bar = leiste(page)
  const leistenBox = await box(bar)
  const viewportHeight = page.viewportSize()!.height
  expect(leistenBox.top, `Oberkante der Leiste (${lage})`).toBeGreaterThanOrEqual(-TOLERANCE)
  expect(leistenBox.bottom, `Unterkante der Leiste (${lage})`).toBeLessThanOrEqual(
    viewportHeight + TOLERANCE,
  )

  const aktion = bar.getByRole('button', { name: ABSCHLUSS })
  await expect(aktion, `Abschluss-Aktion (${lage})`).toBeEnabled()
  expect(await eckentreffer(aktion), `Treffer an den Ecken der Hauptaktion (${lage})`).toEqual([
    'Hauptaktion',
    'Hauptaktion',
    'Hauptaktion',
    'Hauptaktion',
  ])
  return leistenBox
}

async function scrolleAnsEnde(page: Page): Promise<void> {
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  await expect
    .poll(
      async () =>
        page.evaluate(() =>
          Math.round(window.scrollY + window.innerHeight - document.documentElement.scrollHeight),
        ),
      { message: 'Abstand zum Seitenende' },
    )
    .toBeGreaterThanOrEqual(-TOLERANCE)
}

test('die Hauptaktion bleibt in jeder Scrolllage treffbar und verdeckt das Seitenende nicht', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.longAusschuss)
  await page.goto(`/projects/${projectId}/pipeline/ausschuss`)
  await expect(kacheln(page).first()).toBeVisible()
  const mehrLaden = page.getByRole('button', { name: 'Mehr laden' })
  await expect(mehrLaden, 'Vorbedingung: der Bestand reicht ueber eine Seite').toBeVisible()

  // Vorbedingung: die Seite scrollt wirklich - sonst bestuenden die Lagen leer.
  expect(
    await page.evaluate(
      () => document.documentElement.scrollHeight > document.documentElement.clientHeight,
    ),
    'Seite ist hoeher als der Sichtbereich',
  ).toBe(true)

  // Lage 1: beim Aufruf, oben gescrollt.
  expect(await page.evaluate(() => Math.round(window.scrollY)), 'Ausgangslage').toBe(0)
  await pruefeLeiste(page, 'Aufruf')

  // Lage 2: ganz unten - letzte Kachel und "Mehr laden" liegen oberhalb der Leiste.
  await scrolleAnsEnde(page)
  const leisteUnten = await pruefeLeiste(page, 'Seitenende')
  expect(
    (await box(kacheln(page).last())).bottom,
    'Unterkante der letzten Kachel',
  ).toBeLessThanOrEqual(leisteUnten.top + TOLERANCE)
  expect((await box(mehrLaden)).bottom, 'Unterkante von "Mehr laden"').toBeLessThanOrEqual(
    leisteUnten.top + TOLERANCE,
  )

  // Lage 3: nach einmal "Mehr laden" erneut ans Ende.
  const vorher = await kacheln(page).count()
  await mehrLaden.click()
  await expect
    .poll(async () => kacheln(page).count(), { message: 'Kachelzahl nach "Mehr laden"' })
    .toBeGreaterThan(vorher)
  await scrolleAnsEnde(page)
  const leisteNachLaden = await pruefeLeiste(page, 'Seitenende nach "Mehr laden"')
  expect(
    (await box(kacheln(page).last())).bottom,
    'Unterkante der letzten Kachel nach "Mehr laden"',
  ).toBeLessThanOrEqual(leisteNachLaden.top + TOLERANCE)
})

test('die Hauptaktion liegt auch bei kurzem Bestand beim Aufruf im Sichtbereich', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  await page.goto(`/projects/${projectId}/pipeline/ausschuss`)
  await expect(kacheln(page).first()).toBeVisible()

  await pruefeLeiste(page, 'Aufruf, Duplikat-Projekt')
})

test('in der Detailansicht verdeckt die Leiste weder Entscheidung noch "Schliessen"', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.longAusschuss)
  await page.goto(`/projects/${projectId}/pipeline/ausschuss`)
  await kacheln(page).first().getByRole('button').click()
  await expect(page).toHaveURL(/[?&]photo=\d+/)
  await expect(page.getByRole('heading', { name: 'Aufnahme im Ausschuss' })).toBeVisible()

  await pruefeLeiste(page, 'Detailansicht')

  const bedienelemente: [string, Locator][] = [
    ['Schließen', page.getByRole('button', { name: 'Detailansicht schließen' })],
    ['Ausschuss', page.getByRole('button', { name: /^Ausschuss \(Detailansicht\):/ })],
  ]
  for (const [name, control] of bedienelemente) {
    await control.evaluate((element) => element.scrollIntoView({ block: 'center' }))
    const treffer = await control.evaluate((element) => {
      const rect = element.getBoundingClientRect()
      const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)
      return hit !== null && (hit === element || element.contains(hit))
    })
    expect(treffer, `"${name}" in der Mitte treffbar`).toBe(true)
    const kontrolle = await box(control)
    const leistenBox = await box(leiste(page))
    expect(
      kontrolle.bottom <= leistenBox.top + TOLERANCE || kontrolle.top >= leistenBox.bottom,
      `"${name}" liegt nicht unter der Leiste`,
    ).toBe(true)
  }
})
