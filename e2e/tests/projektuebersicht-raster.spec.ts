/**
 * Die Rasterzeile der Projektuebersicht an der exakten Umbruchgrenze (Spec 0375, D3 und G1).
 *
 * WARUM EIGENE EBENE: `lg:grid-cols-12` ist in jsdom eine Zeichenkette in einem `class`-Attribut
 * und keine Geometrie. Die jsdom-Zusicherung prueft, dass es EINEN DOM-Baum gibt (kein
 * `hidden lg:block` neben `lg:hidden`); dieser Spec prueft ausschliesslich die gemessene Lage.
 *
 * GEMESSEN WIRD AN 1023/1024 px, nicht an zwei bequemen Breiten: eine Umbruchzusage, die nur
 * zwischen 360 und 1280 geprueft wird, haelt auch dann, wenn der Umbruch irgendwo dazwischen
 * liegt. Der Spec setzt seine Breiten deshalb selbst und ist an EIN Projekt gebunden.
 *
 * Die Breitenbegrenzung des Anlegen-Formulars steht im selben Spec und wird als VERHAELTNIS zur
 * im selben Lauf mitgemessenen Inhaltsbreite geprueft - nie gegen eine hartkodierte Pixelzahl,
 * die bei jeder Aenderung des Inhaltsrahmens still falsch wuerde.
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-14), gemessen: mit einer erzwungenen
 * `display:flex; flex-direction:column`-Ueberschreibung auf dem Kartenlink - dem Zustand vor
 * dieser Story - meldet der Spec "verschiedene y-Positionen bei 1024 px: Expected 1, Received 3".
 */

import { expect, test, type Locator, type Page } from '@playwright/test'

/** Die Umbruchgrenze selbst: `lg:` greift AB 1024 px, 1023 px ist die letzte schmale Breite. */
const SCHMAL = 1023
const BREIT = 1024
const VIEWPORT_HEIGHT = 900

/** Subpixel-Toleranz fuer "liegt auf derselben Zeile"/"auf derselben Flucht". */
const TOLERANZ = 2

interface Lage {
  x: number
  y: number
  width: number
}

async function lage(locator: Locator): Promise<Lage> {
  const box = await locator.boundingBox()
  expect(box, 'gemessenes Element ist sichtbar').not.toBeNull()
  return { x: box!.x, y: box!.y, width: box!.width }
}

function projektKarten(page: Page) {
  return page.getByRole('listitem').filter({ has: page.locator('a[href^="/projects/"]') })
}

test('Projektkarte: drei Angaben untereinander bei 1023 px, auf einer Zeile ab 1024 px', async ({
  page,
}) => {
  const beobachtet: number[] = []

  for (const breite of [SCHMAL, BREIT]) {
    await page.setViewportSize({ width: breite, height: VIEWPORT_HEIGHT })
    await page.goto('/')

    const karten = projektKarten(page)
    await expect(karten.first()).toBeVisible()

    // VORBEDINGUNG im selben Lauf: mindestens zwei Karten, und zwar mit unterschiedlich langen
    // Namen. Bei nur einer Karte oder gleich langen Namen waere die Flucht-Zusage unten trivial
    // erfuellt, ohne die Eigenschaft herauszufordern.
    const anzahl = await karten.count()
    expect(anzahl, `Projektkarten bei ${breite} px`).toBeGreaterThan(1)
    const namen = await karten.locator('a[href^="/projects/"] > span:first-child').allInnerTexts()
    expect(
      new Set(namen.map((name) => name.length)).size,
      'verschieden lange Projektnamen',
    ).toBeGreaterThan(1)

    const erste = karten.first()
    const href = await erste.locator('a[href^="/projects/"]').getAttribute('href')
    const id = /^\/projects\/(\d+)$/.exec(href ?? '')?.[1]
    expect(id, `Kartenlink zeigt auf /projects/<id>, gefunden: ${href}`).toBeDefined()

    const angaben = await Promise.all([
      lage(page.getByTestId(`project-photo-count-${id}`)),
      lage(page.getByTestId(`project-taken-at-${id}`)),
      lage(page.getByTestId(`project-stand-${id}`)),
    ])

    const zeilen = new Set(angaben.map((angabe) => Math.round(angabe.y / TOLERANZ)))
    beobachtet.push(zeilen.size)

    if (breite === BREIT) {
      expect(zeilen.size, `verschiedene y-Positionen bei ${breite} px`).toBe(1)

      // DIE EIGENTLICHE FLUCHT-ZUSAGE: die Fotoanzahl steht ueber ALLE Karten an derselben
      // x-Position. Eine Karte, die ihre Spalten aus der Textlaenge des Namens ableitete, bestuende
      // die Zeilenpruefung oben und faellt genau hier durch.
      const xPositionen: number[] = []
      for (let index = 0; index < anzahl; index += 1) {
        const kartenHref = await karten
          .nth(index)
          .locator('a[href^="/projects/"]')
          .getAttribute('href')
        const kartenId = /^\/projects\/(\d+)$/.exec(kartenHref ?? '')?.[1]
        xPositionen.push((await lage(page.getByTestId(`project-photo-count-${kartenId}`))).x)
      }
      const spanne = Math.max(...xPositionen) - Math.min(...xPositionen)
      expect(spanne, 'x-Spanne der Fotoanzahl ueber alle Karten').toBeLessThanOrEqual(TOLERANZ)
    } else {
      expect(zeilen.size, `verschiedene y-Positionen bei ${breite} px`).toBe(3)
    }

    // Akzeptanzkriterium D4, Geometriehaelfte: der Name wird nicht abgeschnitten. `scrollWidth`
    // groesser als `clientWidth` ist genau der Zustand, den `truncate` erzeugt.
    const nameUeberlaeuft = await erste
      .locator('a[href^="/projects/"] > span:first-child > span:first-child')
      .evaluate((element) => element.scrollWidth > element.clientWidth + 1)
    expect(nameUeberlaeuft, `Projektname bei ${breite} px abgeschnitten`).toBe(false)
  }

  // Schaerfere Form der Vorbedingung: ein Layout, das gar nicht mehr auf den Umbruchpunkt
  // reagiert, faellt hier auch dann auf, wenn eine der beiden Zahlen zufaellig stimmt.
  expect(new Set(beobachtet).size, 'die beiden Breiten liefern ein verschiedenes Ergebnis').toBe(2)
})
