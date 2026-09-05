/**
 * Kein horizontales Scrollen bei 360 px - die schmalste Breite, an der das Produkt eine Zusage
 * macht (mobile-first PWA). In jsdom ist das prinzipiell nicht pruefbar: ohne Layout-Engine ist
 * `scrollWidth` dort konstant 0.
 *
 * Bei einem Fehlschlag nennt der Spec die tatsaechlich ueberstehenden Elemente statt nur der
 * Zahlen - fuer einen Entwickler ohne Augen ist "welches Element ragt heraus" die eigentliche
 * Information, und ohne sie waere der rote Lauf nur der Anfang der Suche.
 *
 * ABGRENZUNG ZU EINEM BEKANNTEN, HIER NICHT ERFASSTEN DARSTELLUNGSFEHLER: Die Beschriftung der
 * Demo-Bilder ist beidseitig angeschnitten. Das passiert INNERHALB der Bilddatei (der Seeder
 * zeichnet den Text ins 4:3-Bild, die quadratische Kachel beschneidet ihn links und rechts) und
 * ist damit kein DOM-Ueberstand - dieser Spec wird davon weder falsch-rot noch deckt er den
 * Fehler zu, weil er ausschliesslich Elementgeometrie misst.
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-05): siehe PR-Beschreibung - mit einem eingefuegten,
 * 500 px breiten Element meldete der Spec "Dokumentbreite auf \"Projektliste\" (ueberstehende Elemente: <div> bis x=500: ...):
 * expected <= 361, received 500"
 * samt Fundstelle des ueberstehenden Elements.
 */

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Mindesthoehe des Inhaltsbereichs, ab der eine Route als "traegt wirklich Inhalt" gilt. */
const MIN_CONTENT_HEIGHT = 200
/** Subpixel-Toleranz: Chromium meldet Bruchteile, ein Ueberstand ist immer deutlich groesser. */
const TOLERANCE = 1

interface PageMetrics {
  scrollWidth: number
  clientWidth: number
  contentHeight: number
  overflowing: string[]
}

test('keine Route erzeugt horizontales Scrollen bei 360 px', async ({ page }) => {
  const emptyId = await demoProjectId(page, DEMO_PROJECTS.empty)
  const largeId = await demoProjectId(page, DEMO_PROJECTS.large)
  const ratedId = await demoProjectId(page, DEMO_PROJECTS.rated)
  const errorId = await demoProjectId(page, DEMO_PROJECTS.error)

  const routes = [
    { label: 'Projektliste', path: '/', heading: 'Projekte' },
    { label: 'Neues Projekt', path: '/projects/new', heading: 'Neues Projekt anlegen' },
    { label: 'Leeres Projekt', path: `/projects/${emptyId}/photos`, heading: 'Fotos' },
    { label: 'Grosse Sammlung', path: `/projects/${largeId}/photos`, heading: 'Fotos' },
    { label: 'Fehlerzustand', path: `/projects/${errorId}/photos`, heading: 'Fotos' },
    {
      label: 'Pipeline-Schritt',
      path: `/projects/${errorId}/pipeline/scan`,
      heading: DEMO_PROJECTS.error,
    },
    { label: 'Statistik', path: `/projects/${ratedId}/stats`, heading: 'Statistik' },
    { label: 'Kuratierung', path: `/projects/${ratedId}/curate`, heading: 'Kategorie-Kuratierung' },
    { label: 'Einstellungen', path: `/projects/${ratedId}/settings`, heading: 'Projekteinstellungen' },
  ]

  const viewportWidth = page.viewportSize()?.width
  expect(viewportWidth, 'Viewport-Breite des Projekts').toBe(360)

  for (const route of routes) {
    await page.goto(route.path)

    // Vorbedingung 1: die Route traegt WIRKLICH ihren Inhalt. Eine weisse Seite oder eine
    // Fehlerweiterleitung hat garantiert kein horizontales Scrollen und bestuende sonst
    // stillschweigend.
    await expect(
      page.getByRole('heading', { name: route.heading }),
      `Ueberschrift auf "${route.label}"`
    ).toBeVisible()

    const metrics: PageMetrics = await page.evaluate(() => {
      const root = document.documentElement
      const clientWidth = root.clientWidth
      const main = document.querySelector('main')
      const overflowing = Array.from(document.querySelectorAll('body *'))
        .filter((element) => element.getBoundingClientRect().right > clientWidth + 1)
        .slice(0, 5)
        .map((element) => {
          const rect = element.getBoundingClientRect()
          return `<${element.tagName.toLowerCase()}> bis x=${Math.round(rect.right)}: ${(
            element.textContent ?? ''
          )
            .trim()
            .slice(0, 40)}`
        })
      return {
        scrollWidth: root.scrollWidth,
        clientWidth,
        contentHeight: main?.getBoundingClientRect().height ?? 0,
        overflowing,
      }
    })

    // Vorbedingung 2: der Inhaltsbereich hat eine nennenswerte Hoehe - ein auf null kollabiertes
    // <main> koennte gar nicht ueberstehen.
    expect(metrics.contentHeight, `Hoehe des Inhaltsbereichs auf "${route.label}"`).toBeGreaterThan(
      MIN_CONTENT_HEIGHT
    )

    expect(
      metrics.scrollWidth,
      `Dokumentbreite auf "${route.label}" (ueberstehende Elemente: ${
        metrics.overflowing.length === 0 ? 'keine gefunden' : metrics.overflowing.join(' | ')
      })`
    ).toBeLessThanOrEqual(metrics.clientWidth + TOLERANCE)
  }
})
