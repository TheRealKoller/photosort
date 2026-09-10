/**
 * Sticky Kopfzeile beim Scrollen - in jsdom prinzipiell nicht pruefbar (`position: sticky` ohne
 * Layout-Engine ist eine Zeichenkette), bis zur Einfuehrung dieser Ebene deshalb ausnahmslos
 * "manueller visueller Smoke-Test vor Merge".
 *
 * Jede der drei Zusicherungen des ersten Tests waere FUER SICH auch auf einer kaputten Seite
 * gruen - erst gemeinsam sind sie eine Aussage: eine Seite, die gar nicht scrollt, faellt ueber
 * die erste; ein Header, der nie sticky war, ueber die dritte.
 *
 * Der erste Test ist zugleich der Nachweis fuer "das Verhalten aller uebrigen Ansichten am oberen
 * Seitenrand bleibt unveraendert" (Spec 0387): auf der Foto-Route ist die Kopfzeile weiterhin das
 * EINZIGE haftende Element.
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-05): siehe PR-Beschreibung - mit erzwungenem
 * `position: static` auf der Kopfzeile bzw. auf der Stepper-Leiste sind beide Tests rot.
 */

import type { Locator } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId, photoTiles } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Subpixel-Toleranz fuer "steht am oberen Rand" und fuer die Naht zwischen den beiden Leisten. */
const TOP_TOLERANCE = 1

interface Rect {
  y: number
  height: number
}

/**
 * TREFFERTEST STATT SICHTBARKEIT: `toBeVisible()` waere hier wertlos - das Fehlerbild, gegen das
 * dieser Spec steht, ist eine vollstaendig UEBERDECKTE, laut DOM aber sichtbare Kopfzeile. Nur
 * `elementFromPoint` sieht, dass eine durchscheinende Leiste (`bg-bg/95` plus `backdrop-blur-sm`)
 * ueber dem Nachbarn liegt; reine Kastengeometrie sieht das nicht.
 */
async function trefferInDerMitte(control: Locator): Promise<string> {
  return control.evaluate((element) => {
    const rect = element.getBoundingClientRect()
    const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)
    if (hit === null) {
      return 'nichts getroffen (Punkt ausserhalb des Sichtbereichs)'
    }
    if (hit === element || element.contains(hit)) {
      return 'Bedienelement'
    }
    return `Fremdelement <${hit.tagName.toLowerCase()}>`
  })
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
 * Auf den Pipeline-Routen gibt es ZWEI unabhaengige haftende Bereiche: die Kopfzeile der App-Huelle
 * und die Stepper-Leiste. Bis specs/features/0387-schrittleiste-fortschritt.md standen beide auf
 * `top-0`, die im DOM spaetere Leiste gewann, und die Kopfzeile war im gescrollten Zustand
 * vollstaendig verdeckt - samt "Abmelden" und dem Weg zurueck ins Projekt.
 *
 * Seitdem sind sie GEOMETRISCH getrennt: die Kopfzeile ist `h-header` hoch, die Leiste haftet auf
 * `top-header`, beide Werte kommen aus dem einen Token `--spacing-header`. Die Zusage hier bindet
 * genau das an das GERENDERTE Ergebnis statt an den Quelltext - und zwar in beide Richtungen:
 *
 *  - DISJUNKT: ein zu kleines Token liesse die Leiste die Kopfzeile ueberlappen.
 *  - FUGENLOS: ein zu grosses erzeugte eine sichtbare Fuge, durch die Inhalt durchscrollt.
 *
 * Gemessen wird ausschliesslich im GESCROLLTEN Zustand: ungescrollt liegen zwischen beiden die
 * 24px `py-6` des `<main>` - eine Messung davor pruefte die Polsterung statt der Fixierung.
 *
 * Rot-Nachweis (Spec 0387): siehe PR-Beschreibung - mit erzwungenem `top-0` an der Leiste sind
 * "disjunkt", "fugenlos" und der Treffertest rot; mit einem Token von `4rem` bei unveraenderter
 * Kopfzeilenhoehe ist "fugenlos" rot und "disjunkt" gruen. Der zweite Nachweis belegt, dass die
 * Fugen-Zusicherung nicht bloss eine schwaechere Kopie der Ueberlappungs-Zusicherung ist.
 */
test('Stepper-Leiste und Kopfzeile stehen im gescrollten Zustand fugenlos untereinander', async ({
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

  const header = page.getByRole('banner')
  const stepper = page.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
  await expect(stepper).toBeVisible()
  const stepperBefore = await stepper.boundingBox()
  expect(stepperBefore, 'Stepper-Leiste vor dem Scrollen').not.toBeNull()

  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  const scrollY = await page.evaluate(() => Math.round(window.scrollY))

  // Vorbedingung: es wurde WEITER gescrollt, als die Leiste urspruenglich vom Seitenanfang
  // entfernt war. Ohne sticky-Verhalten waere sie damit zwingend aus dem Sichtbereich
  // herausgelaufen - genau das macht die folgenden Zusicherungen aussagekraeftig statt trivial.
  expect(scrollY, 'Scroll-Weg gegenueber der Ausgangsposition der Stepper-Leiste').toBeGreaterThan(
    stepperBefore!.y
  )

  const sticky = await stickyElements(page)
  // Exakte Kardinalitaet - und zugleich die Gegenprobe zur Aussage "was schmal fixiert bleibt":
  // haftete die Orientierungszeile versehentlich mit, waeren es drei.
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

  const headerBox = await header.boundingBox()
  const stepperBox = await stepper.boundingBox()
  expect(headerBox, 'Kopfzeile im gescrollten Zustand').not.toBeNull()
  expect(stepperBox, 'Stepper-Leiste im gescrollten Zustand').not.toBeNull()

  // 1. ZUORDNUNG STATT SORTIERUNG: "die Kopfzeile steht oben" ist eine Zusage der Spec, keine
  //    Hilfsannahme dieses Tests.
  expect(headerBox!.y, 'Oberkante der Kopfzeile gegenueber der Leiste').toBeLessThan(stepperBox!.y)

  const naht = stepperBox!.y - (headerBox!.y + headerBox!.height)

  // 2. DISJUNKT: die Unterkante der Kopfzeile liegt nicht unterhalb der Oberkante der Leiste.
  expect(naht, 'Ueberlappung zwischen Kopfzeile und Leiste').toBeGreaterThanOrEqual(-TOP_TOLERANCE)

  // 3. FUGENLOS: und auch nicht darueber. Erst zusammen binden (2.) und (3.) die Behauptung
  //    "ein Wert, zwei Aufrufstellen" an das gerenderte Ergebnis.
  expect(Math.abs(naht), 'Fuge zwischen Kopfzeile und Leiste').toBeLessThanOrEqual(TOP_TOLERANCE)

  // 4. BEDIENBARKEIT als Treffertest.
  const bedienelemente: [string, Locator][] = [
    ['Abmelden', page.getByRole('button', { name: 'Abmelden' })],
    ['Projektbereiche (Ausloeser der Projektnavigation)', page.getByRole('button', { name: 'Projektbereiche' })],
    ['erster Schritt der Leiste', page.getByRole('link', { name: /^Schritt 1 von 5: Scan/ })],
  ]
  for (const [name, control] of bedienelemente) {
    expect(await trefferInDerMitte(control), `Treffer in der Mitte von "${name}"`).toBe(
      'Bedienelement'
    )
  }

  // 5. SCHMAL ZUSAETZLICH: die Orientierungszeile ist NICHT mehr im Sichtbereich - sie gehoert
  //    seit Spec 0387 nicht mehr zum fixierten Bereich und scrollt mit dem Inhalt weg. Ab `sm:`
  //    ist sie ueberhaupt nicht dargestellt, dort waere die Messung gegenstandslos.
  if (width < 640) {
    const orientierung = page.getByText('Schritt 1 von 5: Scan', { exact: true })
    await expect(orientierung, 'Orientierungszeile im schmalen Viewport').toHaveCount(1)
    const zeile = await orientierung.boundingBox()
    expect(zeile, 'Kasten der Orientierungszeile').not.toBeNull()
    expect(
      zeile!.y + zeile!.height,
      'Unterkante der Orientierungszeile liegt oberhalb des Sichtbereichs'
    ).toBeLessThanOrEqual(0)
  }
})
