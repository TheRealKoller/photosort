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

import { DEMO_PROJECTS, demoProjectId, photoTiles } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Mindesthoehe des Inhaltsbereichs, ab der eine Route als "traegt wirklich Inhalt" gilt. */
const MIN_CONTENT_HEIGHT = 200
/** Subpixel-Toleranz: Chromium meldet Bruchteile, ein Ueberstand ist immer deutlich groesser. */
const TOLERANCE = 1

/**
 * Vorbedingung einer Route: der Beleg, dass sie ihren Inhalt WIRKLICH traegt. Regelfall ist die
 * Seitenueberschrift. Die Foto-Detailseite hat bewusst kein `h1` (sie ist ein Bild, keine
 * Textseite) - dort traegt stattdessen die Bewertungsgruppe die Vorbedingung. Eine Route ohne
 * wirksame Vorbedingung waere genau der immer-gruene Spec, den das Testkonzept ausschliesst.
 */
type Precondition = { heading: string } | { role: 'group'; name: string }

/**
 * Der zugaengliche Name des Zweizustands einer Entwurfskachel. Die Kacheln des Album-Entwurfs
 * tragen KEINEN Kachel-Link und sind deshalb ueber `photoTiles()` nicht auffindbar - ihr
 * Bedienelement ist der belastbare Beleg dafuer, dass die Seite wirklich Kacheln traegt.
 */
const DRAFT_TILE_TOGGLE = /^(Im Album|Gestrichen): /

/**
 * Dasselbe fuer die Kacheln der gemeinsamen Endauswahl (specs/features/0431-...). Die Alternative
 * deckt beide Sichten ab: In der Arbeitssicht traegt eine Kachel "Aufnehmen" und "Nicht
 * aufnehmen", in der Ergebnissicht "Herausnehmen" oder "Aufnehmen".
 */
const SELECTION_TILE_CONTROL = /^(Aufnehmen|Nicht aufnehmen|Herausnehmen): /

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

  // Die Foto-Id kommt aus der Kachel selbst, nicht aus einer hartkodierten Zahl - der Seeder
  // vergibt bei jedem Lauf neue Ids (siehe lib/demo.ts).
  await page.goto(`/projects/${ratedId}/photos`)
  const firstTile = photoTiles(page).first()
  await expect(firstTile, 'erste Kachel des bewerteten Demo-Projekts').toBeVisible()
  const detailHref = await firstTile.getByRole('link').first().getAttribute('href')
  expect(detailHref, 'Ziel der ersten Kachel').toMatch(/\/photos\/\d+/)
  const detailPath = detailHref ?? ''

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
    // Der Album-Entwurf braucht MINDESTENS EINE KACHEL als Vorbedingung: seine Antwortmenge haengt
    // am Auswahlvorschlag des Laufs, und ein leerer Entwurf traegt zwar Ueberschrift und
    // Inhaltshoehe, aber genau die Elemente nicht, die hier ueberstehen koennten.
    {
      label: 'Album-Entwurf',
      path: `/projects/${ratedId}/album`,
      heading: 'Album-Entwurf',
      requiresTile: DRAFT_TILE_TOGGLE,
    },
    {
      label: 'Einstellungen',
      path: `/projects/${ratedId}/settings`,
      heading: 'Projekteinstellungen',
    },
    // Die Endauswahl braucht - wie der Album-Entwurf und aus demselben Grund - MINDESTENS EINE
    // KACHEL als Vorbedingung: Ihre Antwortmenge haengt am Auswahlvorschlag des Laufs und an den
    // Bewertungen beider Nutzer. Gemessen wird hier die ARBEITSSICHT (die Vorbelegung); die
    // Ergebnissicht ist ein anderes DOM und bekommt deshalb unten ihre eigene Messung - diese
    // Schleife misst je Route genau einmal.
    {
      label: 'Endauswahl (Arbeitssicht)',
      path: `/projects/${ratedId}/selection`,
      heading: 'Endauswahl',
      requiresTile: SELECTION_TILE_CONTROL,
    },
    // Die Detailseite traegt seit Spec 0321 die umbrechende Bewertungsleiste: drei Eintraege mit
    // Symbol, Beschriftung und Tasten-Kaestchen brauchen nebeneinander rund 400px, bei 360px
    // stehen 288px zur Verfuegung. Genau diese Route fehlte hier bisher.
    { label: 'Foto-Detail', path: detailPath, role: 'group' as const, name: 'Bewertung' },
  ] satisfies ({ label: string; path: string; requiresTile?: RegExp } & Precondition)[]

  const viewportWidth = page.viewportSize()?.width
  expect(viewportWidth, 'Viewport-Breite des Projekts').toBe(360)

  for (const route of routes) {
    await page.goto(route.path)

    // Vorbedingung 1: die Route traegt WIRKLICH ihren Inhalt. Eine weisse Seite oder eine
    // Fehlerweiterleitung hat garantiert kein horizontales Scrollen und bestuende sonst
    // stillschweigend.
    const marker =
      'heading' in route
        ? page.getByRole('heading', { name: route.heading })
        : page.getByRole(route.role, { name: route.name })
    await expect(marker, `Vorbedingung auf "${route.label}"`).toBeVisible()

    // Vorbedingung 1b, nur wo die Ueberschrift zu wenig sagt: Die Seite traegt tatsaechlich
    // Kacheln. Eine Route, deren Inhaltsmenge von Laufergebnissen abhaengt, bestuende sonst genau
    // dann, wenn sie leer ist.
    if ('requiresTile' in route && route.requiresTile !== undefined) {
      await expect(
        page.getByRole('button', { name: route.requiresTile }).first(),
        `Kachel-Vorbedingung auf "${route.label}"`,
      ).toBeVisible()
    }

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
      MIN_CONTENT_HEIGHT,
    )

    expect(
      metrics.scrollWidth,
      `Dokumentbreite auf "${route.label}" (ueberstehende Elemente: ${
        metrics.overflowing.length === 0 ? 'keine gefunden' : metrics.overflowing.join(' | ')
      })`,
    ).toBeLessThanOrEqual(metrics.clientWidth + TOLERANCE)
  }
})

/**
 * Die ERGEBNISSICHT der Endauswahl bei 360 px - eine ZWEITE Messung derselben Route.
 *
 * Sie entsteht nur ueber den Umschalter und ist ein ANDERES DOM als die Arbeitssicht: andere
 * Kachelmenge, eine statt zwei Schaltflaechen je Kachel, dazu das Kennzeichen "gemeinsam
 * entschieden" und die gedaempften, herausgenommenen Bilder. Die Routenschleife oben misst je
 * Route genau einmal und saehe davon nichts.
 */
test('die Ergebnissicht der Endauswahl erzeugt kein horizontales Scrollen bei 360 px', async ({
  page,
}) => {
  const ratedId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${ratedId}/selection`)

  await page.getByRole('button', { name: 'Endauswahl', exact: true }).click()

  // Vorbedingung: die Ergebnissicht traegt WIRKLICH Kacheln. Ohne sie bestuende der Fall auch
  // dann, wenn die Endauswahl leer waere - also genau dann, wenn nichts ueberstehen koennte.
  await expect(
    page.getByRole('button', { name: SELECTION_TILE_CONTROL }).first(),
    'mindestens eine Kachel in der Ergebnissicht',
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

  expect(metrics.contentHeight, 'Hoehe des Inhaltsbereichs der Ergebnissicht').toBeGreaterThan(
    MIN_CONTENT_HEIGHT,
  )
  expect(
    metrics.scrollWidth,
    `Dokumentbreite in der Ergebnissicht der Endauswahl (ueberstehende Elemente: ${
      metrics.overflowing.length === 0 ? 'keine gefunden' : metrics.overflowing.join(' | ')
    })`,
  ).toBeLessThanOrEqual(metrics.clientWidth + TOLERANCE)
})

/**
 * Der GEOEFFNETE Alternativen-Dialog bei 360 px - ein eigener Testfall, weil er nur ueber eine
 * Interaktion entsteht und die Routenschleife oben ausschliesslich Seiten im Ruhezustand misst.
 *
 * Er ist der engste Fall des Produkts: ein Bildraster mit zwei Spalten, Qualitaetsbeschriftung und
 * Abzeichen liegt in einem Dialog, der selbst schon Rand und Polsterung traegt. Genau dafuer ist
 * es ein Dialog und kein Popover geworden - die Zusage gehoert deshalb gemessen, nicht behauptet.
 */
test('der geoeffnete Alternativen-Dialog erzeugt kein horizontales Scrollen bei 360 px', async ({
  page,
}) => {
  const ratedId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${ratedId}/album`)

  const trigger = page.getByRole('button', { name: /^Alternativen: / }).first()
  await expect(trigger, 'Zugang zu den Alternativen auf der ersten Entwurfskachel').toBeVisible()
  await trigger.click()

  const dialog = page.getByRole('dialog')
  await expect(dialog, 'geoeffneter Alternativen-Dialog').toBeVisible()
  // Vorbedingung: der Dialog traegt WIRKLICH ein Raster. Ohne sie bestuende der Fall auch dann,
  // wenn das Event nichts weiter haelt und nur der Leerzustandstext dasteht - also genau dann,
  // wenn nichts ueberstehen koennte.
  await expect(
    dialog.getByRole('button', { name: /^Austauschen gegen: / }).first(),
    'mindestens eine Alternative im Raster',
  ).toBeVisible()

  const metrics: PageMetrics = await page.evaluate(() => {
    const root = document.documentElement
    const clientWidth = root.clientWidth
    const open = document.querySelector('dialog[open]')
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
      contentHeight: open?.getBoundingClientRect().height ?? 0,
      overflowing,
    }
  })

  expect(metrics.contentHeight, 'Hoehe des Dialogs').toBeGreaterThan(MIN_CONTENT_HEIGHT)
  expect(
    metrics.scrollWidth,
    `Dokumentbreite bei geoeffnetem Alternativen-Dialog (ueberstehende Elemente: ${
      metrics.overflowing.length === 0 ? 'keine gefunden' : metrics.overflowing.join(' | ')
    })`,
  ).toBeLessThanOrEqual(metrics.clientWidth + TOLERANCE)
})
