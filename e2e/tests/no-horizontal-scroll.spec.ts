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

import type { Locator, Page } from '@playwright/test'

import {
  DEMO_PERSONS,
  DEMO_PROJECTS,
  demoProjectId,
  duplicateTiles,
  openDuplicateGroup,
  photoTiles,
} from '../lib/demo.ts'
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
type Precondition = { heading: string } | { role: 'group' | 'link'; name: string | RegExp }

/**
 * Der zugaengliche Name der Entscheidungsflaeche einer Entwurfskachel (specs/features/0558-...):
 * Sie nennt die Handlung. Die Kacheln des Album-Entwurfs tragen KEINEN Kachel-Link und sind
 * deshalb ueber `photoTiles()` nicht auffindbar - ihr Bedienelement ist der belastbare Beleg
 * dafuer, dass die Seite wirklich Kacheln traegt.
 */
const DRAFT_TILE_TOGGLE = /^(Streichen|Wieder aufnehmen): /

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

  // Dieselbe Ableitung wie oben, fuer die Duplikat-Vergleichsansicht: Der Pfad traegt eine
  // Foto-Id, und die vergibt der Seeder bei jedem Lauf neu. Genommen wird der ECHTE Einstieg aus
  // der nach Vorschlaegen gefilterten Fotoliste - seit Spec 0525 der einzige Weg dorthin; der
  // `&gate=1`-Modus samt kachelgenauem Link ist entfallen.
  const duplicatesId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  await page.goto(`/projects/${duplicatesId}/photos?filter=suggested`)
  const compareLink = page.getByRole('link', { name: /^Duplikate vergleichen —/ })
  await expect(compareLink, 'Einstieg in den Duplikat-Vergleich').toBeVisible()
  const compareHref = await compareLink.getAttribute('href')
  expect(compareHref, 'Ziel des Vergleichs-Einstiegs').toMatch(/\/photos\/\d+\/duplicates$/)

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
    // specs/features/0374-duplikate-vergleichen.md: Die Ansicht traegt bei 360 px zwei Spalten
    // Bildkacheln samt zweiteiliger Wahlzeile - die dichteste Stelle des Produkts nach der
    // Bewertungsleiste, und damit die, an der ein zu enges Raster zuerst uebersteht.
    {
      label: 'Duplikat-Vergleich',
      path: compareHref ?? '',
      role: 'group' as const,
      name: 'Ganze Gruppe',
    },
    // specs/features/0533-duplikatstapel-vergleichsansicht.md (B5): die Ausschuss-Uebersicht mit
    // Duplikat-Stapeln. Vorbedingung ist ein SICHTBARER Stapel - ohne ihn bestuende die Messung
    // gegen eine Uebersicht aus lauter Einzelkacheln, und der Versatz der hinteren Karten, der
    // hier ueberstehen koennte, waere gar nicht im Dokument.
    {
      label: 'Ausschuss mit Stapeln',
      path: `/projects/${duplicatesId}/pipeline/ausschuss`,
      role: 'link' as const,
      name: /^Duplikat-Gruppe mit \d+ Aufnahmen vergleichen/,
    },
    // Die globale Personenseite mit zwei Karten und der
    // Gefahrenzone. Die Karte des 40-Zeichen-Namens bricht um statt zu kuerzen - genau dort
    // stuende die Seite ueber.
    { label: 'Personen', path: '/persons', heading: 'Personen' },
    // specs/features/0551-personenuebersicht-je-projekt.md: Die Personenuebersicht eines Projekts.
    // Vorbedingung ist die Gruppe mit dem 40-Zeichen-Namen - ihre Ueberschrift, ihr Eintrag in der
    // Sprungleiste und ihre Karten brechen um statt zu kuerzen - UND die Statusleiste von "Ohne
    // Namen", die die Inhaltsbreite spannt.
    {
      label: 'Personenuebersicht',
      path: `/projects/${ratedId}/persons`,
      heading: DEMO_PERSONS.longest,
      requiresText: /^(Gesichter werden gesucht|Suche abgeschlossen)/,
    },
  ] satisfies ({
    label: string
    path: string
    requiresTile?: RegExp
    requiresText?: RegExp
  } & Precondition)[]

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
        : page.getByRole(route.role, { name: route.name }).first()
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

    // Vorbedingung 1c: ein Textbaustein, ohne den die Route ihre breiteste Stelle nicht traegt.
    if ('requiresText' in route && route.requiresText !== undefined) {
      await expect(
        page.getByText(route.requiresText).first(),
        `Text-Vorbedingung auf "${route.label}"`,
      ).toBeVisible()
    }

    // Zwei Bildwechsel abwarten: Gerechnete Kachelmaesse (`justifiedRows`) entstehen erst, wenn
    // der ResizeObserver die Rasterbreite gemeldet hat. Davor steht fuer einen Bildwechsel die
    // natuerliche Kachelbreite, und die Messung faenge diesen Zwischenstand statt der Seite.
    await page.evaluate(
      () =>
        new Promise<void>((resolve) => {
          requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
        }),
    )

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
 * Die Ablaufuebersicht bei 360 px. Gemessen am
 * Fehlerzustand-Projekt: Dort tragen die Kopfzeilen Lauf-Kennzeichen und sind am laengsten.
 *
 * Seite und Dialog stehen nicht seitlich ueber, und "Schliessen" liegt vor UND nach dem Scrollen
 * des Inhaltsbereichs im Bild - es scrollt nur der Inhalt, nie die Schaltflaechenzeile.
 */
test('die Ablaufuebersicht scrollt bei 360 px nur im Inhalt, nie seitlich', async ({ page }) => {
  const errorId = await demoProjectId(page, DEMO_PROJECTS.error)
  await page.goto(`/projects/${errorId}/pipeline/scan`)
  await page.getByRole('button', { name: 'Ablauf' }).click()

  const dialog = page.getByRole('dialog', { name: 'Ablauf im Überblick' })
  await expect(dialog, 'geoeffnete Ablaufuebersicht').toBeVisible()
  const schliessen = dialog.getByRole('button', { name: 'Schließen' })
  const inhalt = dialog.getByRole('list', { name: 'Schritte' }).locator('xpath=..')

  // Vorbedingung: Der Inhaltsbereich traegt tatsaechlich mehr, als in ihn passt - sonst bestuende
  // die Zusage "Schliessen bleibt im Bild" auch ohne scrollenden Bereich.
  const vorher = await inhalt.evaluate((element) => ({
    scrollHeight: element.scrollHeight,
    clientHeight: element.clientHeight,
  }))
  expect(vorher.scrollHeight, 'Inhaltshoehe gegen sichtbare Hoehe').toBeGreaterThan(
    vorher.clientHeight + TOLERANCE,
  )
  await expect(schliessen, '"Schließen" vor dem Scrollen').toBeInViewport({ ratio: 1 })

  await inhalt.evaluate((element) => {
    element.scrollTop = element.scrollHeight
  })
  await expect(schliessen, '"Schließen" nach dem Scrollen').toBeInViewport({ ratio: 1 })

  const breiten = await page.evaluate(() => {
    const dialogElement = document.querySelector('dialog')
    // Seitlich scrollen kann nur ein Behaelter, dessen `overflow-x` das zulaesst - der negative
    // Rand des Inhaltsbereichs (Fokusring-Luft) ragt sichtbar ueber, scrollt aber nichts.
    const ueberstehend = [dialogElement, ...Array.from(dialogElement?.querySelectorAll('*') ?? [])]
      .filter((element): element is Element => element !== null)
      .filter(
        (element) =>
          ['auto', 'scroll'].includes(getComputedStyle(element).overflowX) &&
          element.scrollWidth > element.clientWidth + 1,
      )
    return {
      dokument: document.documentElement.scrollWidth,
      sichtbar: document.documentElement.clientWidth,
      dialogRechts: dialogElement?.getBoundingClientRect().right ?? Infinity,
      ueberstehend: ueberstehend.map((element) => element.tagName.toLowerCase()).slice(0, 5),
    }
  })
  expect(breiten.dokument, 'Dokumentbreite bei geoeffneter Uebersicht').toBeLessThanOrEqual(
    breiten.sichtbar + TOLERANCE,
  )
  expect(breiten.dialogRechts, 'rechte Kante des Dialogs').toBeLessThanOrEqual(
    breiten.sichtbar + TOLERANCE,
  )
  expect(breiten.ueberstehend, 'seitlich ueberstehende Elemente im Dialog').toEqual([])
})

/**
 * Die Filterleiste der Fotouebersicht bei 360 px (specs/features/0489-..., AK11).
 *
 * ZWEI MESSUNGEN, nicht eine. „Die Seite scrollt nicht seitlich" allein bestuende auch gegen eine
 * Leiste, die ihre Eintraege abschneidet oder umbricht statt selbst zu scrollen - und genau das
 * ist der Fall, den Daniels Entscheidung ausschliesst. Belegt wird deshalb BEIDES: die Leiste
 * scrollt nachweislich selbst (`scrollWidth > clientWidth` UND ein tatsaechlich wirksamer
 * `scrollLeft`), und das Dokument daneben nicht.
 */
test('die Filterleiste ist bei 360 px ein eigener Scrollbereich', async ({ page }) => {
  const largeId = await demoProjectId(page, DEMO_PROJECTS.large)
  await page.goto(`/projects/${largeId}/photos`)

  const leiste = page.getByRole('group', { name: 'Filter' })
  await expect(leiste, 'Filterleiste').toBeVisible()
  // Vorbedingung: die Leiste traegt WIRKLICH alle Eintraege. Eine auf zwei Knoepfe geschrumpfte
  // Leiste braeuchte gar keinen Scrollbereich, und der Fall bestuende ohne Aussage.
  await expect(leiste.getByRole('button')).toHaveCount(6)

  const vorher = await leiste.evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }))
  expect(
    vorher.scrollWidth,
    'Inhaltsbreite der Filterleiste gegen ihre sichtbare Breite',
  ).toBeGreaterThan(vorher.clientWidth + TOLERANCE)

  const scrollLeft = await leiste.evaluate((element) => {
    element.scrollLeft = element.scrollWidth
    return element.scrollLeft
  })
  expect(scrollLeft, 'die Leiste laesst sich tatsaechlich seitlich rollen').toBeGreaterThan(0)

  const dokument = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(dokument.scrollWidth, 'Dokumentbreite neben der scrollenden Leiste').toBeLessThanOrEqual(
    dokument.clientWidth + TOLERANCE,
  )
})

/**
 * Die Personen-Filtergruppe bei 360 px.
 *
 * Dieselben zwei Messungen wie bei der Filterleiste: Die Gruppe scrollt nachweislich selbst, und
 * das Dokument daneben nicht. Der Anlass ist der Demo-Name mit der Hoechstlaenge von 40 Zeichen -
 * Namen werden nie gekuerzt, also muss die Gruppe ihn in sich aufnehmen. Zusaetzlich steht der
 * Name in seiner Schaltflaeche vollstaendig: Eine Gruppe, die ihn abschnitte, braeuchte gar
 * keinen Scrollbereich.
 */
test('die Personen-Filtergruppe mit dem laengsten Namen scrollt bei 360 px in sich', async ({
  page,
}) => {
  const ratedId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${ratedId}/photos`)

  const gruppe = page.getByRole('group', { name: 'Personen' })
  await expect(gruppe, 'Personen-Filtergruppe').toBeVisible()
  // Vorbedingung: "Alle", beide Namen und "Beide" - exakt, gegen den trivialen Gruen-Fall einer
  // Gruppe, die den langen Namen gar nicht traegt.
  await expect(gruppe.getByRole('button')).toHaveCount(4)
  const langerName = gruppe.getByRole('button', { name: DEMO_PERSONS.longest, exact: true })
  await expect(langerName, 'Eintrag mit dem 40-Zeichen-Namen').toBeVisible()

  const name = await langerName.evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }))
  expect(
    name.scrollWidth,
    'der lange Name steht ungekuerzt in seiner Schaltflaeche',
  ).toBeLessThanOrEqual(name.clientWidth + TOLERANCE)

  const vorher = await gruppe.evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }))
  expect(
    vorher.scrollWidth,
    'Inhaltsbreite der Personen-Filtergruppe gegen ihre sichtbare Breite',
  ).toBeGreaterThan(vorher.clientWidth + TOLERANCE)

  const scrollLeft = await gruppe.evaluate((element) => {
    element.scrollLeft = element.scrollWidth
    return element.scrollLeft
  })
  expect(scrollLeft, 'die Gruppe laesst sich tatsaechlich seitlich rollen').toBeGreaterThan(0)

  const dokument = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(dokument.scrollWidth, 'Dokumentbreite neben der scrollenden Gruppe').toBeLessThanOrEqual(
    dokument.clientWidth + TOLERANCE,
  )
})

/**
 * Die ERGEBNISSICHT der Endauswahl bei 360 px - eine ZWEITE Messung derselben Route.
 *
 * Sie entsteht nur ueber den Umschalter und ist ein ANDERES DOM als die Arbeitssicht: andere
 * Kachelmenge, eine statt zwei Schaltflaechen je Kachel, dazu das Kennzeichen "gemeinsam
 * entschieden" und die herausgenommenen Bilder mit durchgestrichenem Dateinamen. Die
 * Routenschleife oben misst je Route genau einmal und saehe davon nichts.
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
 * Misst das Dokument und nennt die ersten ueberstehenden Elemente. `container` ist der Beleg,
 * dass der gemessene Zustand WIRKLICH Inhalt traegt - seine Hoehe geht als `contentHeight` mit.
 */
async function measureWithin(page: Page, container: string): Promise<PageMetrics> {
  return page.evaluate((selector) => {
    const root = document.documentElement
    const clientWidth = root.clientWidth
    const open = document.querySelector(selector)
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
  }, container)
}

function expectNoOverflow(metrics: PageMetrics, label: string): void {
  expect(
    metrics.scrollWidth,
    `Dokumentbreite ${label} (ueberstehende Elemente: ${
      metrics.overflowing.length === 0 ? 'keine gefunden' : metrics.overflowing.join(' | ')
    })`,
  ).toBeLessThanOrEqual(metrics.clientWidth + TOLERANCE)
}

/**
 * „Tauschen" und „Hinzufügen" der ersten Alternative: untereinander,
 * je sichtbar mindestens 44 px hoch und mit mindestens 12 px Abstand, ohne Ueberlappung.
 */
async function expectStackedActions(band: Locator, label: string): Promise<void> {
  const exchange = await band
    .getByRole('button', { name: /^Tauschen: / })
    .first()
    .boundingBox()
  const add = await band
    .getByRole('button', { name: /^Hinzufügen: / })
    .first()
    .boundingBox()
  expect(exchange, `Tauschen ${label}`).not.toBeNull()
  expect(add, `Hinzufügen ${label}`).not.toBeNull()
  expect(exchange!.height, `Hoehe von Tauschen ${label}`).toBeGreaterThanOrEqual(44 - TOLERANCE)
  expect(add!.height, `Hoehe von Hinzufügen ${label}`).toBeGreaterThanOrEqual(44 - TOLERANCE)
  expect(
    add!.y - (exchange!.y + exchange!.height),
    `Abstand zwischen Tauschen und Hinzufügen ${label}`,
  ).toBeGreaterThanOrEqual(12 - TOLERANCE)
}

/**
 * Die durch eine Interaktion entstehenden Zustaende des Album-Entwurfs bei 360 px
 * (specs/features/0558-...) - eigene Messungen, weil die Routenschleife oben ausschliesslich Seiten
 * im Ruhezustand misst: das offene Alternativen-Band zugeklappt (Serie) und aufgeklappt (alle Fotos
 * des Events), das offene Hinzufuegen-Panel und die eingeblendeten
 * Gestrichenen.
 *
 * Band und Panel sind volle Rasterzeilen mit eigenem Raster aus Kachel und Handlungen darin - der
 * engste Fall des Entwurfs. Die aufgeklappte Reihe waechst an derselben Stelle und bricht im
 * Raster um; sie hat keinen eigenen Scrollcontainer.
 */
test('die offenen Zustaende des Album-Entwurfs erzeugen kein horizontales Scrollen bei 360 px', async ({
  page,
}) => {
  const ratedId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${ratedId}/album`)

  // Band: Vorbedingung ist mindestens eine Alternative - ein Band, das nur den Leertext traegt,
  // koennte nicht ueberstehen.
  const trigger = page.getByRole('button', { name: /^Alternativen: / }).first()
  await expect(trigger, 'Zugang zu den Alternativen auf der ersten Entwurfskachel').toBeVisible()
  await trigger.click()
  const band = page.locator(`[id="${await trigger.getAttribute('aria-controls')}"]`)
  await expect(
    band.getByRole('button', { name: /^Tauschen: / }).first(),
    'mindestens eine Alternative im Band',
  ).toBeVisible()
  expectNoOverflow(await measureWithin(page, 'main'), 'bei offenem Alternativen-Band')
  await expectStackedActions(band, 'in der Serie')

  // „Alle Fotos des Events": dieselbe Flaeche waechst zur vollen Reihe, kein Dialog.
  const toggle = band.getByRole('button', { name: 'Alle Fotos des Events', exact: true })
  await toggle.click()
  await expect(
    band.getByRole('button', { name: 'Weniger anzeigen', exact: true }),
    'aufgeklappter Umschalter',
  ).toHaveAttribute('aria-expanded', 'true')
  await expect(
    band
      .getByRole('list', { name: 'Alternativen, zeitlich geordnet' })
      .getByRole('button', { name: /^Tauschen: / })
      .first(),
    'mindestens eine Alternative in der aufgeklappten Reihe',
  ).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expectNoOverflow(await measureWithin(page, 'main'), 'bei aufgeklappter Reihe')
  await expectStackedActions(band, 'in der aufgeklappten Reihe')
  await page.keyboard.press('Escape')
  await expect(band).toBeHidden()

  // Panel: Ein zweites Panel schliesst das Band; Vorbedingung ist mindestens ein Kandidat.
  const addTrigger = page.getByRole('button', { name: /^Foto hinzufügen: / }).first()
  await addTrigger.click()
  await expect(
    page.getByRole('button', { name: /^Hinzufügen: / }).first(),
    'mindestens ein Foto im Hinzufügen-Panel',
  ).toBeVisible()
  expectNoOverflow(await measureWithin(page, 'main'), 'bei offenem Hinzufügen-Panel')
  await addTrigger.click()

  // Gestrichene eingeblendet: Vorbedingung ist mindestens eine gestrichene Kachel.
  await page
    .getByRole('button', { name: /^\d+ gestrichen – anzeigen$/ })
    .first()
    .click()
  await expect(
    page.getByRole('button', { name: /^Wieder aufnehmen: / }).first(),
    'eine eingeblendete gestrichene Kachel',
  ).toBeVisible()
  const struckMetrics = await measureWithin(page, 'main')
  expect(struckMetrics.contentHeight, 'Hoehe des Inhaltsbereichs').toBeGreaterThan(
    MIN_CONTENT_HEIGHT,
  )
  expectNoOverflow(struckMetrics, 'bei eingeblendeten Gestrichenen')
})

/**
 * Die Haltungskennzeichen der Endauswahl bei 360 px (specs/features/0558-...): Jedes Kennzeichen
 * steht EINZEILIG. Die Kachel ist bei zwei Spalten rund 150 px breit, und „Aufgenommen" samt
 * Symbol neben dem Teilnehmernamen ist der laengste Fall - ein Umbruch darin machte aus dem
 * Kennzeichen zwei Woerter-Fetzen, ohne dass irgendetwas uebersteht.
 *
 * Gemessen wird je Textknoten des Kennzeichens ueber `Range.getClientRects()`: genau ein Rechteck
 * heisst eine Zeile. Eine Kastenhoehe waere an die Zeilenhoehe kalibriert und damit wertlos.
 */
test('die Haltungskennzeichen der Endauswahl stehen bei 360 px einzeilig', async ({ page }) => {
  const ratedId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${ratedId}/selection`)

  const stances = page.locator('ul[aria-label^="Haltung zu "] > li')
  // Vorbedingung: Kennzeichen sind WIRKLICH da, und darunter mindestens eines der drei Wörter -
  // sonst liefe die Messung ueber lauter „–".
  await expect(stances.first(), 'mindestens eine Haltungszeile').toBeVisible()
  await expect(
    page.locator('ul[aria-label^="Haltung zu "] [data-album-state]').first(),
    'mindestens ein Zustandswort',
  ).toBeVisible()

  const lines = await stances.evaluateAll((rows) =>
    rows.map((row) => {
      const badge = row.lastElementChild
      const walker = document.createTreeWalker(badge ?? row, NodeFilter.SHOW_TEXT)
      const counts: number[] = []
      for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
        if ((node.textContent ?? '').trim() === '') {
          continue
        }
        const range = document.createRange()
        range.selectNodeContents(node)
        counts.push(range.getClientRects().length)
      }
      return { text: (badge?.textContent ?? '').trim(), counts }
    }),
  )

  expect(lines.length, 'Anzahl gemessener Haltungszeilen').toBeGreaterThan(0)
  for (const line of lines) {
    expect(line.counts, `Zeilen des Kennzeichens "${line.text}"`).toEqual([1])
  }
})

/**
 * Die Motivstaerke-Reihe bei 360 px (specs/features/0490-motivstaerke-kompakt.md, AK12).
 *
 * ERWEITERUNG DIESES SPECS STATT EINES NEUNTEN: Es ist dieselbe Breitenzusage, und der Einstieg
 * ueber die erste Kachel steht hier bereits.
 *
 * DREI MESSUNGEN, nicht eine. "Die Seite scrollt nicht seitlich" allein bestuende auch gegen eine
 * Reihe, die umbricht oder ein Symbol auf Breite 0 drueckt - beides ist bei acht Achteln von
 * 360 px genau der Fehler, der eintraete. Belegt werden deshalb: alle acht auf DERSELBEN Zeile
 * (gleiche Oberkante), jedes mindestens 24 x 24 px (WCAG 2.5.8 - die Mindestgroesse, auf die sich
 * ADR 0113 Punkt 5 beim bewussten Verzicht auf die waagerechten 44 px stuetzt, und damit die
 * einzige Stelle, an der diese Zahl ueberhaupt geprueft wird), und das Dokument daneben ohne
 * waagerechten Ueberstand.
 */
test('die acht Motivsymbole liegen bei 360 px in einer Zeile', async ({ page }) => {
  /** WCAG 2.5.8 (Stufe AA): die Mindestgroesse, die auf beiden Achsen gilt. */
  const MIN_TARGET_SIZE = 24

  const ratedId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${ratedId}/photos`)
  const tile = photoTiles(page).first()
  await expect(tile, 'erste Kachel des bewerteten Demo-Projekts').toBeVisible()
  await tile.getByRole('link').first().click()

  const reihe = page.getByRole('list', { name: 'Motive' })
  await expect(reihe, 'Motivstaerke-Reihe').toBeVisible()
  const symbole = reihe.getByRole('button')
  // Vorbedingung: die Reihe traegt WIRKLICH alle acht. Auf einem Foto ohne Klassifizierungslauf
  // stuende hier ein Satz statt der Reihe, und jede Messung darunter liefe ueber eine leere Menge.
  await expect(symbole, 'Symbole der Reihe').toHaveCount(8)

  const kaesten = await symbole.evaluateAll((elemente) =>
    elemente.map((element) => {
      const rect = element.getBoundingClientRect()
      return { top: Math.round(rect.top), width: rect.width, height: rect.height }
    }),
  )

  const oberkanten = [...new Set(kaesten.map((kasten) => kasten.top))]
  expect(
    oberkanten,
    'Oberkanten der acht Symbole (mehr als eine heisst: die Reihe bricht um)',
  ).toHaveLength(1)

  for (const [index, kasten] of kaesten.entries()) {
    expect(kasten.width, `Breite von Symbol ${index + 1}`).toBeGreaterThanOrEqual(MIN_TARGET_SIZE)
    expect(kasten.height, `Hoehe von Symbol ${index + 1}`).toBeGreaterThanOrEqual(MIN_TARGET_SIZE)
  }

  const dokument = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(dokument.scrollWidth, 'Dokumentbreite auf der Foto-Detailseite').toBeLessThanOrEqual(
    dokument.clientWidth + TOLERANCE,
  )
})

/**
 * Die GROSSANSICHT der Vergleichsansicht bei 360 px (specs/features/0533-..., A11) - ein anderes
 * DOM an derselben Route und deshalb eine eigene Messung statt eines zweiten Routeneintrags.
 *
 * Gemessen wird in der Gruppe mit der LANGEN Spanne: Ihr Kopf („... in 1 Stunde 42 Minuten") muss
 * umbrechen, statt ueberzustehen - die Ueberschrift ist deshalb selbst Teil der Messung.
 */
test('die Grossansicht und ein langer Kopf erzeugen kein horizontales Scrollen bei 360 px', async ({
  page,
}) => {
  const duplicatesId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  await openDuplicateGroup(page, duplicatesId, 'gross')

  const kopf = page.getByRole('heading', { level: 1, name: /Stunde/ })
  if ((await kopf.count()) === 0) {
    await openDuplicateGroup(page, duplicatesId, 'klein')
  }
  // Vorbedingung: der Kopf traegt WIRKLICH eine Spanne in Stunden - sonst waere er kurz genug,
  // um in eine Zeile zu passen, und die Messung saehe den Umbruch nie.
  await expect(kopf, 'Kopf mit Spanne in Stunden').toBeVisible()

  await duplicateTiles(page)
    .nth(1)
    .getByRole('button', { name: /vergrößern$/ })
    .click()
  await expect(
    page.getByRole('heading', { level: 2, name: /^Aufnahme 2 von \d+$/ }),
    'Grossansicht offen',
  ).toBeVisible()

  const messung = await page.evaluate(() => {
    const root = document.documentElement
    const ueberschrift = document.querySelector('h1')
    return {
      scrollWidth: root.scrollWidth,
      clientWidth: root.clientWidth,
      kopfRechts: ueberschrift?.getBoundingClientRect().right ?? Number.POSITIVE_INFINITY,
      kopfUeberlauf: (ueberschrift?.scrollWidth ?? 0) - (ueberschrift?.clientWidth ?? 0),
    }
  })

  expect(messung.kopfUeberlauf, 'Ueberschrift laeuft nicht in sich ueber').toBeLessThanOrEqual(
    TOLERANCE,
  )
  expect(messung.kopfRechts, 'Ueberschrift endet im Sichtbereich').toBeLessThanOrEqual(
    messung.clientWidth + TOLERANCE,
  )
  expect(messung.scrollWidth, 'Dokumentbreite in der Grossansicht').toBeLessThanOrEqual(
    messung.clientWidth + TOLERANCE,
  )
})
