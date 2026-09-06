/**
 * Projekt-Navigationsgruppe in der Kopfzeile: Breakpoint, Kopfzeilenhoehe und Ueberlagerung.
 *
 * AUSSCHLIESSLICH DAS, WAS JSDOM PRINZIPIELL NICHT KANN (specs/features/0298-projektnavigation-in-
 * der-kopfzeile.md, Teststrategie; specs/architecture/0002-testkonzept.md, Sektion "Eine
 * Zieltabelle, zwei Darstellungen"): In jsdom greifen Tailwind-Klassen nicht, `hidden`/`lg:hidden`
 * blenden dort nichts aus, beide Darstellungen liegen gleichzeitig im DOM. Ein `toBeVisible()`
 * waere dort eine Zusicherung, die immer dasselbe sagt - unabhaengig davon, ob die Utility
 * ueberhaupt noch am Element haengt. Die Breakpoint-Zusage lebt deshalb nur hier. Die
 * Verhaltenspruefungen (vier Ziele, Sprungziele, aria-current, Escape, Landmark-Kardinalitaet)
 * stehen in ProjectNav.test.tsx und werden hier NICHT wiederholt.
 *
 * EIGENE VIEWPORT-BREITEN, an ein einziges Playwright-Projekt gebunden (wie `grid-columns`): Die
 * beiden Projekt-Viewports (360, 1280) liegen beide fern der Grenze und zeigten den Wechsel gar
 * nicht; ohne die Bindung liefe der Spec ausserdem zweimal mit identischem Ergebnis.
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-06): siehe PR-Beschreibung - mit einem auf `md:`
 * verschobenen Breakpoint (`hidden md:flex` / `md:hidden`) meldete der erste Test
 * "sichtbare Ziele bei 1023 px: expected 0, received 4".
 */

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Die Grenze aus dem UI/UX-Abschnitt der Spec: `lg:` = 1024 px. */
const BREAKPOINT = 1024
const VIEWPORT_HEIGHT = 900
/** Die schmale Breite des Produkts - dieselbe wie im `mobile`-Projekt. */
const MOBILE_WIDTH = 360
/** Subpixel-Toleranz fuer Hoehen- und Kantenvergleiche (AK7 nennt sie ausdruecklich). */
const TOLERANCE = 1

function projectNav(page: import('@playwright/test').Page) {
  return page.getByRole('navigation', { name: 'Projektbereiche' })
}

function menuTrigger(page: import('@playwright/test').Page) {
  return page.getByRole('button', { name: 'Projektbereiche' })
}

test('wechselt an der exakten Grenze 1024 px zwischen Leiste und Menue-Ausloeser', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

  const measured: { width: number; visibleTargets: number; triggerVisible: boolean }[] = []

  for (const width of [BREAKPOINT, BREAKPOINT - 1]) {
    await page.setViewportSize({ width, height: VIEWPORT_HEIGHT })
    await page.goto(`/projects/${projectId}/photos`)

    const nav = projectNav(page)
    await expect(nav, `Navigationsgruppe bei ${width} px`).toBeAttached()

    const targets = nav.getByRole('link')
    // Beide Darstellungen speisen sich aus derselben Zieltabelle - im DOM liegen immer genau vier
    // Ziele, unabhaengig von der Breite. Gemessen wird ausschliesslich, wie viele davon
    // TATSAECHLICH dargestellt werden.
    await expect(targets, `Ziele im DOM bei ${width} px`).toHaveCount(4)
    const visibility = await targets.evaluateAll((elements) =>
      elements.map((element) => element.getBoundingClientRect().height > 0)
    )

    measured.push({
      width,
      visibleTargets: visibility.filter(Boolean).length,
      triggerVisible: await menuTrigger(page).isVisible(),
    })
  }

  // AK5: ab 1024 px alle vier gleichzeitig sichtbar, kein Ausloeser.
  expect(measured[0], `Darstellung bei ${BREAKPOINT} px`).toEqual({
    width: BREAKPOINT,
    visibleTargets: 4,
    triggerVisible: false,
  })
  // AK6: einen Pixel darunter genau umgekehrt - ausschliesslich der Ausloeser.
  expect(measured[1], `Darstellung bei ${BREAKPOINT - 1} px`).toEqual({
    width: BREAKPOINT - 1,
    visibleTargets: 0,
    triggerVisible: true,
  })
  // Beide Messungen MUESSEN sich unterscheiden: waeren sie gleich, haette der Spec nur zweimal
  // denselben Zustand gesehen und bestuende auch bei voellig fehlendem Breakpoint.
  expect(measured[0]!.visibleTargets, 'Messungen an der Grenze unterscheiden sich').not.toBe(
    measured[1]!.visibleTargets
  )
})

test('erzeugt bei 360 px keine zusaetzliche Kopfzeilenzeile', async ({ page }) => {
  // AK7: Die Gruppe darf den Seiteninhalt nicht nach unten schieben. Gemessen gegen DIESELBE
  // Kopfzeile ohne Projektbezug - eine feste Erwartungszahl waere auf den heutigen Zustand
  // kalibriert und ueberlebte keine legitime Aenderung der Kopfzeile.
  await page.setViewportSize({ width: MOBILE_WIDTH, height: VIEWPORT_HEIGHT })
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

  const header = page.locator('header')

  await page.goto('/')
  await expect(projectNav(page), 'Gruppe auf der Projektliste').toHaveCount(0)
  const withoutProject = await header.boundingBox()
  expect(withoutProject, 'Kopfzeile ohne Projektbezug').not.toBeNull()

  await page.goto(`/projects/${projectId}/photos`)
  await expect(menuTrigger(page), 'Menue-Ausloeser auf der Projektseite').toBeVisible()
  const withProject = await header.boundingBox()
  expect(withProject, 'Kopfzeile mit Projektbezug').not.toBeNull()

  // Groesse > 0 zuerst: zwei auf 0 kollabierte Kopfzeilen waeren sonst trivial "gleich hoch".
  expect(withoutProject!.height, 'Hoehe der Kopfzeile ohne Projektbezug').toBeGreaterThan(0)
  expect(
    Math.abs(withProject!.height - withoutProject!.height),
    `Hoehenunterschied der Kopfzeile bei ${MOBILE_WIDTH} px`
  ).toBeLessThanOrEqual(TOLERANCE)
})

test('legt das geoeffnete Panel vollstaendig sichtbar ueber den Seiteninhalt', async ({ page }) => {
  // AK12: zwei Zusagen in einem Test, weil einzeln jede fuer sich wertlos waere - ein Panel weit
  // ausserhalb des Sichtbereichs ueberdeckte nichts, und ein Panel, das nichts ueberdeckt, belegt
  // die Stapelreihenfolge nicht.
  await page.setViewportSize({ width: MOBILE_WIDTH, height: VIEWPORT_HEIGHT })
  const projectId = await demoProjectId(page, DEMO_PROJECTS.large)
  await page.goto(`/projects/${projectId}/photos`)

  const trigger = menuTrigger(page)
  await expect(trigger).toBeVisible()

  /** Pruefpunkte innerhalb eines Rechtecks: Mitte plus vier eingerueckte Ecken. */
  function probePoints(box: { x: number; y: number; width: number; height: number }) {
    const inset = 4
    return [
      [box.x + box.width / 2, box.y + box.height / 2],
      [box.x + inset, box.y + inset],
      [box.x + box.width - inset, box.y + inset],
      [box.x + inset, box.y + box.height - inset],
      [box.x + box.width - inset, box.y + box.height - inset],
    ] as [number, number][]
  }

  await trigger.click()
  const panel = page.getByRole('dialog')
  await expect(panel).toBeVisible()

  const box = await panel.boundingBox()
  expect(box, 'Panel-Rechteck').not.toBeNull()
  expect(box!.width, 'Panelbreite').toBeGreaterThan(0)
  expect(box!.height, 'Panelhoehe').toBeGreaterThan(0)

  // Vollstaendig im Sichtbereich.
  expect(box!.x, 'linke Panelkante').toBeGreaterThanOrEqual(-TOLERANCE)
  expect(box!.y, 'obere Panelkante').toBeGreaterThanOrEqual(-TOLERANCE)
  expect(box!.x + box!.width, 'rechte Panelkante').toBeLessThanOrEqual(MOBILE_WIDTH + TOLERANCE)
  expect(box!.y + box!.height, 'untere Panelkante').toBeLessThanOrEqual(
    VIEWPORT_HEIGHT + TOLERANCE
  )

  const points = probePoints(box!)

  const hitsWhileOpen = await panel.evaluate((element, coordinates) => {
    return (coordinates as [number, number][]).map(([x, y]) => {
      const hit = document.elementFromPoint(x, y)
      if (hit === null) return 'nichts getroffen'
      return hit === element || element.contains(hit) ? 'Panel' : `<${hit.tagName.toLowerCase()}>`
    })
  }, points)
  expect(hitsWhileOpen, 'getroffene Elemente an den Pruefpunkten des offenen Panels').toEqual(
    points.map(() => 'Panel')
  )

  // GEGENPROBE: An denselben Punkten liegt bei geschlossenem Panel nachweislich Seiteninhalt -
  // ohne sie bestuende der Test auch dann, wenn das Panel ueber einer leeren Flaeche schwebte und
  // gar nichts ueberdeckte.
  await page.keyboard.press('Escape')
  await expect(panel).toBeHidden()

  const contentHits = await page.evaluate((coordinates) => {
    const main = document.querySelector('main')
    return (coordinates as [number, number][]).map(([x, y]) => {
      const hit = document.elementFromPoint(x, y)
      return hit !== null && main !== null && main.contains(hit)
    })
  }, points)
  expect(
    contentHits.filter(Boolean).length,
    'Pruefpunkte, an denen ohne Panel Seiteninhalt liegt'
  ).toBeGreaterThan(0)
})
