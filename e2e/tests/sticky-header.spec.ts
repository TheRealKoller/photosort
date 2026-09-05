/**
 * Sticky Kopfzeile beim Scrollen - in jsdom prinzipiell nicht pruefbar (`position: sticky` ohne
 * Layout-Engine ist eine Zeichenkette), bis zur Einfuehrung dieser Ebene deshalb ausnahmslos
 * "manueller visueller Smoke-Test vor Merge".
 *
 * Jede der drei Zusicherungen des ersten Tests waere FUER SICH auch auf einer kaputten Seite
 * gruen - erst gemeinsam sind sie eine Aussage: eine Seite, die gar nicht scrollt, faellt ueber
 * die erste; ein Header, der nie sticky war, ueber die dritte.
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-05): siehe PR-Beschreibung - mit erzwungenem
 * `position: static` auf der Kopfzeile bzw. auf der Stepper-Leiste sind beide Tests rot.
 */

import { DEMO_PROJECTS, demoProjectId, photoTiles } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Subpixel-Toleranz fuer "steht am oberen Rand". */
const TOP_TOLERANCE = 1

interface Rect {
  y: number
  height: number
}

async function stickyElements(page: import('@playwright/test').Page): Promise<Rect[]> {
  return page.evaluate(() =>
    Array.from(document.querySelectorAll('*'))
      .filter((element) => getComputedStyle(element).position === 'sticky')
      .map((element) => {
        const rect = element.getBoundingClientRect()
        return { y: rect.y, height: rect.height }
      })
  )
}

test('Kopfzeile bleibt beim Scrollen am oberen Rand stehen', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.large)
  await page.goto(`/projects/${projectId}/photos`)
  await expect(photoTiles(page).first()).toBeVisible()

  const header = page.getByRole('banner')
  const heading = page.getByRole('heading', { name: 'Fotos' })
  const headingBefore = await heading.boundingBox()
  expect(headingBefore, 'Referenzelement vor dem Scrollen').not.toBeNull()

  await page.evaluate(() => window.scrollTo(0, 600))

  // Vorbedingung 1: die Seite ist WIRKLICH gescrollt. Ohne sie bestuende der Test auch auf einer
  // Seite mit zu wenig Inhalt - und zwar stillschweigend.
  await expect
    .poll(async () => page.evaluate(() => Math.round(window.scrollY)), {
      message: 'tatsaechliche Scroll-Position',
    })
    .toBeGreaterThan(0)

  // Vorbedingung 2: ein Referenzelement aus dem Seiteninhalt ist MITGEWANDERT. Damit faellt der
  // Fall auf, dass die Seite zwar einen Scroll-Offset meldet, der Inhalt aber in einem eigenen
  // Scroll-Container haengt und die Kopfzeile deshalb ohnehin nie in Bewegung geriet.
  const headingAfter = await heading.boundingBox()
  expect(headingAfter, 'Referenzelement nach dem Scrollen').not.toBeNull()
  expect(headingAfter!.y, 'Referenzelement ist nach oben gewandert').toBeLessThan(headingBefore!.y)

  // Erst jetzt die eigentliche Zusage.
  const headerBox = await header.boundingBox()
  expect(headerBox, 'Kopfzeile im gescrollten Zustand').not.toBeNull()
  expect(Math.abs(headerBox!.y), 'Abstand der Kopfzeile zum oberen Viewport-Rand').toBeLessThanOrEqual(
    TOP_TOLERANCE
  )
  expect(headerBox!.height, 'Hoehe der Kopfzeile').toBeGreaterThan(0)
  await expect(header).toBeVisible()

  // Exakte Kardinalitaet statt "mindestens eines": auf dieser Route ist die Kopfzeile das einzige
  // sticky Element. Ein zweites, unbeabsichtigtes waere genau die Fehlerklasse, die man ohne
  // Layout-Engine nicht sieht.
  expect((await stickyElements(page)).length, 'sticky Elemente auf der Foto-Route').toBe(1)
})

/**
 * Auf den Pipeline-Routen gibt es ZWEI unabhaengige `sticky top-0`-Elemente (Kopfzeile der
 * App-Huelle und Stepper-Leiste) - Edge Case E2 der Spec 0174.
 *
 * BEWUSST NICHT ENTHALTEN: die vom Testkonzept vorgesehene Zusicherung disjunkter y-Bereiche
 * beider Elemente im gescrollten Zustand. Sie ist gegen den aktuellen Stand der Anwendung ROT -
 * die Stepper-Leiste legt sich im gescrollten Zustand vollstaendig ueber die Kopfzeile (beide
 * `top-0`, gleicher z-index, die spaeter im DOM stehende Leiste gewinnt). Das ist ein echter,
 * hier erstmals sichtbar gewordener Layout-Fehler der Anwendung und keine Eigenschaft dieses
 * Pruefsatzes; er wird als eigene Story gefuehrt statt in diesem Zug mitgeaendert (die Spec 0174
 * aendert ausdruecklich keinen Frontend-Code). Die dadurch offene Zusage steht als benannte
 * Luecke im Testkonzept - der disjunkte y-Bereich wird die Regressionszusicherung des Fixes.
 *
 * Was hier trotzdem geprueft wird, ist der Teil, der heute gilt und der beim Beheben des Fehlers
 * gruen BLEIBT: beide Elemente sind sticky (exakte Anzahl) und beide stehen im gescrollten
 * Zustand vollstaendig im Sichtbereich.
 */
test('Stepper-Leiste und Kopfzeile bleiben auf der Pipeline-Route beide im Sichtbereich', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.error)

  // Eigene, flache Viewport-Hoehe: die Pipeline-Seiten sind mit dem Demo-Datenbestand kuerzer als
  // beide Projekt-Viewports und wuerden gar nicht scrollen - der sticky Zustand entstuende nie und
  // der Test bestuende leer. Die Breite bleibt die des Projekts, gemessen wird eine
  // hoehenabhaengige Eigenschaft.
  const width = page.viewportSize()?.width ?? 360
  const viewportHeight = 300
  await page.setViewportSize({ width, height: viewportHeight })
  await page.goto(`/projects/${projectId}/pipeline/scan`)

  const stepper = page.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
  await expect(stepper).toBeVisible()
  const stepperBefore = await stepper.boundingBox()
  expect(stepperBefore, 'Stepper-Leiste vor dem Scrollen').not.toBeNull()

  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  const scrollY = await page.evaluate(() => Math.round(window.scrollY))

  // Vorbedingung: es wurde WEITER gescrollt, als die Leiste urspruenglich vom Seitenanfang
  // entfernt war. Ohne sticky-Verhalten waere sie damit zwingend aus dem Sichtbereich
  // herausgelaufen - genau das macht die folgende Zusicherung aussagekraeftig statt trivial.
  expect(scrollY, 'Scroll-Weg gegenueber der Ausgangsposition der Stepper-Leiste').toBeGreaterThan(
    stepperBefore!.y
  )

  const sticky = await stickyElements(page)
  expect(sticky.length, 'sticky Elemente auf der Pipeline-Route').toBe(2)

  for (const rect of sticky) {
    expect(rect.height, 'Hoehe eines sticky Elements').toBeGreaterThan(0)
    expect(rect.y, 'Oberkante eines sticky Elements liegt im Sichtbereich').toBeGreaterThanOrEqual(
      -TOP_TOLERANCE
    )
    expect(
      rect.y + rect.height,
      'Unterkante eines sticky Elements liegt im Sichtbereich'
    ).toBeLessThanOrEqual(viewportHeight + TOP_TOLERANCE)
  }
})
