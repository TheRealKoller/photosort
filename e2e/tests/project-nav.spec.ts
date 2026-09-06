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
 * ROT-NACHWEIS STEHT NOCH AUS: Dieser Spec wurde in einer Remote-Session ohne Docker-Daemon und
 * ohne installierbaren Browser geschrieben und konnte dort nicht ein einziges Mal laufen. Der von
 * der Teststrategie geforderte Nachweis (Breakpoint testweise auf `md:` verschieben, Spec muss rot
 * melden) ist beim ersten ausfuehrbaren Lauf zu erbringen und in der PR-Beschreibung
 * festzuhalten - bis dahin ist die Wirksamkeit dieser drei Tests behauptet, nicht belegt.
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

/*
 * DOM-LOKALISIERER STATT ROLLENLOKALISIERER, UND ZWAR ZWINGEND: `getByRole()` matcht laut eigener
 * Dokumentation (`playwright-core/types/types.d.ts`, Option `includeHidden`) standardmaessig NUR
 * nicht-verborgene Elemente - es sieht den Accessibility-Tree, nicht das DOM. Genau darauf beruht
 * dieser Spec aber: unterhalb `lg:` traegt die Leiste `display: none`, ein `getByRole('link')`
 * faende dort NULL Ziele und `toHaveCount(4)` liefe in die Zeitgrenze. Die DOM-Kardinalitaet wird
 * deshalb ueber `locator('a')`/`locator('button[aria-label=...]')` gefuehrt, die Sichtbarkeit
 * anschliessend GEMESSEN statt lokalisiert.
 */
function navTargetsInDom(page: import('@playwright/test').Page) {
  return projectNav(page).locator('a')
}

function menuTriggerInDom(page: import('@playwright/test').Page) {
  return page.locator('button[aria-label="Projektbereiche"]')
}

/** Anteil der tatsaechlich dargestellten Elemente einer DOM-Menge. */
async function visibleCount(locator: import('@playwright/test').Locator): Promise<number> {
  const rendered = await locator.evaluateAll((elements) =>
    elements.map((element) => {
      const rect = element.getBoundingClientRect()
      return rect.width > 0 && rect.height > 0
    })
  )
  return rendered.filter(Boolean).length
}

test('wechselt an der exakten Grenze 1024 px zwischen Leiste und Menue-Ausloeser', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

  const measured: { width: number; visibleTargets: number; triggerVisible: boolean }[] = []

  for (const width of [BREAKPOINT, BREAKPOINT - 1]) {
    await page.setViewportSize({ width, height: VIEWPORT_HEIGHT })
    await page.goto(`/projects/${projectId}/photos`)

    await expect(projectNav(page), `Navigationsgruppe bei ${width} px`).toBeAttached()

    // Beide Darstellungen speisen sich aus derselben Zieltabelle - im DOM liegen immer genau vier
    // Ziele und genau ein Ausloeser, unabhaengig von der Breite. Diese beiden Zusicherungen sind
    // die Vorbedingung der Messung: ohne sie bestuende der 1023-px-Durchlauf ("null sichtbare
    // Ziele") auch dann, wenn die Leiste gar nicht mehr gerendert wuerde.
    const targets = navTargetsInDom(page)
    await expect(targets, `Ziele im DOM bei ${width} px`).toHaveCount(4)
    const trigger = menuTriggerInDom(page)
    await expect(trigger, `Menue-Ausloeser im DOM bei ${width} px`).toHaveCount(1)

    // Gemessen wird ausschliesslich, wie viele davon TATSAECHLICH dargestellt werden.
    measured.push({
      width,
      visibleTargets: await visibleCount(targets),
      triggerVisible: (await visibleCount(trigger)) === 1,
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

/*
 * ZWEI BREITEN, EINE MESSTECHNIK - und zwei verschiedene Zusagen:
 *
 *  - 360 px deckt AK7 ab ("die Kopfzeile ist auf einer Projektseite genauso hoch wie auf einer
 *    Seite ohne Projektbezug, Toleranz 1 px"). Dort ist nur der Menue-Ausloeser dargestellt.
 *  - 1024 px deckt die verbindliche Regel des Architektur-Abschnitts ab ("die Kopfzeile darf bei
 *    keiner Breite in eine zweite Zeile umbrechen"). Das ist die SCHMALSTE Breite, bei der
 *    Wortmarke, VIER Beschriftungen, "Angemeldet als …" und "Abmelden" gleichzeitig in einer Zeile
 *    stehen muessen - also die einzige, an der die Regel tatsaechlich gefaehrdet ist. Der
 *    `lg:`-Breakpoint beruht in der Spec auf einer Schaetzung ("rund 800 px"), nicht auf einer
 *    Messung; ohne diese Zusicherung bliebe sie ungeprueft.
 *
 * WARUM DIE HOEHE UND NICHT EIN UEBERLAUF: Das `<header>` traegt `flex-wrap`. Ein Umbruch laeuft
 * deshalb STILL - nichts ragt heraus, nichts scrollt waagerecht, die Kopfzeile wird lediglich
 * zweizeilig. Gegen dieselbe Kopfzeile ohne Projektbezug gemessen statt gegen eine feste Zahl: die
 * waere auf den heutigen Zustand kalibriert und ueberlebte keine legitime Aenderung der Kopfzeile.
 */
const HEADER_HEIGHT_WIDTHS = [
  {
    width: MOBILE_WIDTH,
    zusage: 'AK7: keine zusaetzliche Kopfzeilenzeile durch die Gruppe',
    /** Bei 360 px ist ausschliesslich der Ausloeser dargestellt (AK6). */
    expectedVisibleTargets: 0,
    expectedTriggerVisible: true,
  },
  {
    width: BREAKPOINT,
    zusage: 'verbindliche Regel: kein Umbruch der Kopfzeile in eine zweite Zeile',
    /** Bei 1024 px stehen alle vier Beschriftungen in der Zeile (AK5) - genau das ist der Druck. */
    expectedVisibleTargets: 4,
    expectedTriggerVisible: false,
  },
] as const

for (const fall of HEADER_HEIGHT_WIDTHS) {
  test(`haelt die Kopfzeile bei ${fall.width} px einzeilig (${fall.zusage})`, async ({ page }) => {
    await page.setViewportSize({ width: fall.width, height: VIEWPORT_HEIGHT })
    const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

    /*
     * `getByRole('banner')` UND NICHT `locator('header')`: Es gibt sechs `<header>` im Produkt.
     * Fuenf davon sind Seiten-Header INNERHALB von `<main>` (u.a. ProjectListPage - genau die
     * Seite, die dieser Test als Vergleich ohne Projektbezug ansteuert), einer ist die App-Shell-
     * Kopfzeile ausserhalb. Ein `locator('header')` traf auf `/` beide und brach mit einer
     * Strict-Mode-Meldung ab.
     *
     * Die Rolle trennt sie sauber: `<header>` traegt `banner` nur, solange es nicht in
     * `main`/`article`/`section`/`aside`/`nav` verschachtelt ist - die fuenf Seiten-Header sind
     * damit rollenlos, nur die App-Shell-Kopfzeile ist ein `banner`. Zugleich die Rollen- statt
     * Klassennamen-Lokalisierung der Selektor-Konvention, und dasselbe Vorgehen wie in
     * `sticky-header.spec.ts` und `lib/auth.ts`.
     */
    const header = page.getByRole('banner')

    await page.goto('/')
    await expect(projectNav(page), 'Gruppe auf der Projektliste').toHaveCount(0)
    // Eindeutigkeit ZUGESICHERT statt vorausgesetzt: Kaeme spaeter ein zweiter `banner` dazu,
    // scheiterte die Messung sonst wieder mit einer Strict-Mode-Meldung ueber einen Lokalisierer
    // statt mit einer verstaendlichen Zusicherung ueber die Kopfzeile.
    await expect(header, 'Kopfzeilen-Landmark auf der Projektliste').toHaveCount(1)
    const withoutProject = await header.boundingBox()
    expect(withoutProject, 'Kopfzeile ohne Projektbezug').not.toBeNull()

    await page.goto(`/projects/${projectId}/photos`)
    await expect(projectNav(page), 'Gruppe auf der Projektseite').toBeAttached()
    await expect(header, 'Kopfzeilen-Landmark auf der Projektseite').toHaveCount(1)

    // Vorbedingung: bei DIESER Breite ist auch tatsaechlich die erwartete Darstellung zu sehen.
    // Ohne sie waere der Hoehenvergleich bei 1024 px wertlos - er bestuende auch dann, wenn die
    // vier Beschriftungen gar nicht dargestellt wuerden und deshalb nichts umbrechen koennte.
    expect(
      await visibleCount(navTargetsInDom(page)),
      `sichtbare Ziele bei ${fall.width} px`
    ).toBe(fall.expectedVisibleTargets)
    expect(
      (await visibleCount(menuTriggerInDom(page))) === 1,
      `Menue-Ausloeser sichtbar bei ${fall.width} px`
    ).toBe(fall.expectedTriggerVisible)

    const withProject = await header.boundingBox()
    expect(withProject, 'Kopfzeile mit Projektbezug').not.toBeNull()

    // Groesse > 0 zuerst: zwei auf 0 kollabierte Kopfzeilen waeren sonst trivial "gleich hoch".
    expect(withoutProject!.height, 'Hoehe der Kopfzeile ohne Projektbezug').toBeGreaterThan(0)
    expect(
      Math.abs(withProject!.height - withoutProject!.height),
      `Hoehenunterschied der Kopfzeile bei ${fall.width} px`
    ).toBeLessThanOrEqual(TOLERANCE)
  })
}

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
