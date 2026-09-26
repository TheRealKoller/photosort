/**
 * specs/features/0531-kuratierung-grossansicht.md — die Zusagen der Großansicht, die jsdom nicht
 * messen kann: echte Geometrie (Einpassung, Ausdehnung an der `sm`-Grenze), der Top-Layer samt
 * `::backdrop`, echtes `popstate`, echtes Scrollen und ein echter Reload.
 *
 * SECHS FÄLLE im Album-Entwurf des Demo-Projekts „Bewertet":
 *
 * 1. Ausdehnung an der `sm`-Grenze (AK6/AK7) — 639 px randlos, 640 px mit 48/24 px Rand.
 * 2. Das Bild füllt die Bühne (AK5) — zwei verschiedene Formate, dazu mit aufgeklappten Details.
 * 3. Klick neben bzw. auf das Bild (AK10) — nur breit, an einem Hochformat.
 * 4. Schließwege, Platz und Fokus (AK10/AK11) — scrollY, URL und Fokus je Schließweg.
 * 5. Zweimal Escape (AK10) — synthetisch vor `popstate` und nativ über den CloseWatcher-Pfad.
 * 6. Reload (AK15).
 *
 * DER SPEC IST LESEND: Die Großansicht schreibt nichts, und keine Entscheidungsfläche wird
 * gedrückt.
 *
 * ER LÄUFT IN BEIDEN VIEWPORT-PROJEKTEN und steht deshalb in keiner der Listen
 * `MOBILE_ONLY`/`DESKTOP_ONLY`; `toolchain.spec.ts` bindet das fest.
 *
 * BEKANNTE LÜCKE: `dvh` gegen eine ein- und ausfahrende Browserleiste, die Android-Zurück-Geste
 * und Safaris Fokussemantik sind hier nicht belegbar (headless Chromium).
 */
import type { Locator, Page } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Zulässige Abweichung in px. Subpixel-Layout macht exakte Gleichheit unerreichbar. */
const TOLERANZ = 1

/** Der Rand der Überlagerung ab `sm` (`sm:inset-x-12 sm:inset-y-6`). */
const RAND_X = 48
const RAND_Y = 24

interface Rechteck {
  x: number
  y: number
  width: number
  height: number
}

/** Ausloeser der Großansicht im Raster - die Bildfläche jeder Kachel. */
function ausloeser(page: Page): Locator {
  return page.getByRole('button', { name: /^Großansicht: / })
}

function dialog(page: Page): Locator {
  return page.getByRole('dialog')
}

function buehne(page: Page): Locator {
  return page.getByTestId('lightbox-stage')
}

function bild(page: Page): Locator {
  return page.getByTestId('lightbox-image-box').locator('img')
}

/** Öffnet den Album-Entwurf über einen eigenen Verlaufseintrag nach der Projektseite und liefert
 *  deren URL - Ziel des abschließenden Zurück. */
async function oeffneEntwurf(page: Page): Promise<string> {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${projectId}`)
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}/pipeline`))
  const einstieg = page.url()
  await page.goto(`/projects/${projectId}/album`)
  await expect(ausloeser(page).first(), 'Auslöser der ersten Entwurfskachel').toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  return einstieg
}

/** Wartet, bis das große Bild geladen ist und seine natürlichen Maße kennt. */
async function bildGeladen(page: Page): Promise<void> {
  await expect(bild(page)).toBeVisible()
  await expect
    .poll(() => bild(page).evaluate((node) => (node as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0)
}

/** Das natürliche Format des Kachelbildes hinter einem Auslöser (Vorschau im selben Format). */
async function kachelFormat(trigger: Locator): Promise<number> {
  const vorschau = trigger.locator('img')
  await expect
    .poll(() => vorschau.evaluate((node) => (node as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0)
  return vorschau.evaluate((node) => {
    const img = node as HTMLImageElement
    return img.naturalWidth / img.naturalHeight
  })
}

/** Das INHALTSRECHTECK des `object-contain`-Bildes aus natürlichen Maßen und Elementkasten. */
async function inhaltsRechteck(page: Page): Promise<Rechteck & { format: number }> {
  return bild(page).evaluate((node) => {
    const img = node as HTMLImageElement
    const kasten = img.getBoundingClientRect()
    const format = img.naturalWidth / img.naturalHeight
    const kastenFormat = kasten.width / kasten.height
    const breite = format > kastenFormat ? kasten.width : kasten.height * format
    const hoehe = format > kastenFormat ? kasten.width / format : kasten.height
    return {
      x: kasten.x + (kasten.width - breite) / 2,
      y: kasten.y + (kasten.height - hoehe) / 2,
      width: breite,
      height: hoehe,
      format,
    }
  })
}

async function rechteck(locator: Locator): Promise<Rechteck> {
  const box = await locator.boundingBox()
  expect(box, 'Element hat ein Rechteck').not.toBeNull()
  return box!
}

/** Prüft AK5: Inhalt in der Bühne, eine Achse bündig, Format wie das natürliche. */
async function pruefeEinpassung(page: Page, name: string): Promise<void> {
  const inhalt = await inhaltsRechteck(page)
  const flaeche = await rechteck(buehne(page))

  expect(inhalt.x, `${name}: links in der Bühne`).toBeGreaterThanOrEqual(flaeche.x - TOLERANZ)
  expect(inhalt.y, `${name}: oben in der Bühne`).toBeGreaterThanOrEqual(flaeche.y - TOLERANZ)
  expect(inhalt.x + inhalt.width, `${name}: rechts in der Bühne`).toBeLessThanOrEqual(
    flaeche.x + flaeche.width + TOLERANZ,
  )
  expect(inhalt.y + inhalt.height, `${name}: unten in der Bühne`).toBeLessThanOrEqual(
    flaeche.y + flaeche.height + TOLERANZ,
  )
  const buendig =
    Math.abs(inhalt.width - flaeche.width) <= TOLERANZ ||
    Math.abs(inhalt.height - flaeche.height) <= TOLERANZ
  expect(
    buendig,
    `${name}: in einer Achse bündig (Inhalt ${inhalt.width.toFixed(1)}×${inhalt.height.toFixed(1)}, ` +
      `Bühne ${flaeche.width.toFixed(1)}×${flaeche.height.toFixed(1)})`,
  ).toBe(true)
  const gerendert = inhalt.width / inhalt.height
  expect(
    Math.abs(gerendert / inhalt.format - 1),
    `${name}: gerendertes Format ${gerendert.toFixed(3)} gleich dem natürlichen ${inhalt.format.toFixed(3)}`,
  ).toBeLessThanOrEqual(0.01)
}

/** Ein Punkt der freien Bühnenfläche neben dem Bildkasten - `null`, wenn es keinen gibt. */
async function punktNebenDemBild(page: Page): Promise<{ x: number; y: number } | null> {
  const flaeche = await rechteck(buehne(page))
  const kasten = await rechteck(page.getByTestId('lightbox-image-box'))
  const seitlich = kasten.x - flaeche.x
  const oben = kasten.y - flaeche.y
  if (seitlich >= 10) {
    return { x: flaeche.x + seitlich / 2, y: flaeche.y + flaeche.height / 2 }
  }
  if (oben >= 10) {
    return { x: flaeche.x + flaeche.width / 2, y: flaeche.y + oben / 2 }
  }
  return null
}

async function scrollY(page: Page): Promise<number> {
  return page.evaluate(() => window.scrollY)
}

test.describe('Kuratierung: die Großansicht', () => {
  test('dehnt sich unter 640 px randlos und ab 640 px mit Rand über der abgedunkelten Seite', async ({
    page,
  }) => {
    await oeffneEntwurf(page)
    const hoehe = page.viewportSize()!.height
    await ausloeser(page).first().click()
    await expect(dialog(page)).toBeVisible()

    await page.setViewportSize({ width: 639, height: hoehe })
    const schmal = await rechteck(dialog(page))
    expect(schmal.x, '639: links bündig').toBeLessThanOrEqual(TOLERANZ)
    expect(schmal.y, '639: oben bündig').toBeLessThanOrEqual(TOLERANZ)
    expect(Math.abs(schmal.width - 639), '639: volle Breite').toBeLessThanOrEqual(TOLERANZ)
    expect(Math.abs(schmal.height - hoehe), '639: volle Höhe').toBeLessThanOrEqual(TOLERANZ)

    await page.setViewportSize({ width: 640, height: hoehe })
    const breit = await rechteck(dialog(page))
    expect(Math.abs(breit.x - RAND_X), '640: Rand links').toBeLessThanOrEqual(TOLERANZ)
    expect(Math.abs(breit.y - RAND_Y), '640: Rand oben').toBeLessThanOrEqual(TOLERANZ)
    expect(
      Math.abs(breit.width - (640 - 2 * RAND_X)),
      '640: Rand links und rechts',
    ).toBeLessThanOrEqual(TOLERANZ)
    expect(
      Math.abs(breit.height - (hoehe - 2 * RAND_Y)),
      '640: Rand oben und unten',
    ).toBeLessThanOrEqual(TOLERANZ)
    expect(breit, 'die beiden Ausdehnungen unterscheiden sich').not.toEqual(schmal)

    const treffer = await page.evaluate(() => {
      const ziel = document.elementFromPoint(8, 8)
      return ziel?.tagName ?? 'nichts'
    })
    expect(treffer, 'ein Treffer auf dem Rand liefert den Backdrop des Dialogs').toBe('DIALOG')

    const deckkraft = await dialog(page).evaluate((node) => {
      const farbe = getComputedStyle(node, '::backdrop').backgroundColor
      const mitSchraegstrich = /\/\s*([\d.]+%?)\s*\)$/.exec(farbe)
      if (mitSchraegstrich?.[1] !== undefined) {
        const wert = mitSchraegstrich[1]
        return wert.endsWith('%') ? Number(wert.slice(0, -1)) / 100 : Number(wert)
      }
      const rgba = /^rgba\(([^)]+)\)$/.exec(farbe)
      if (rgba?.[1] !== undefined) {
        return Number(rgba[1].split(',')[3])
      }
      return /^rgb\(/.test(farbe) ? 1 : 0
    })
    expect(deckkraft, 'Deckkraft der Abdunklung').toBeGreaterThan(0)
    await expect(page.getByRole('heading', { level: 1, includeHidden: true })).toBeAttached()
  })

  test('stellt „Schließen“ ab 640 px rechts in die Bedienzeile, darunter über die Bühne', async ({
    page,
  }) => {
    await oeffneEntwurf(page)
    await ausloeser(page).first().click()
    await expect(dialog(page)).toBeVisible()
    const schliessen = await rechteck(
      dialog(page).getByRole('button', { name: 'Schließen', exact: true }),
    )

    if (page.viewportSize()!.width >= 640) {
      const details = await rechteck(
        dialog(page).getByRole('button', { name: 'Details', exact: true }),
      )
      const panel = await rechteck(page.getByTestId('lightbox-panel'))
      const mitte = (kasten: Rechteck) => kasten.y + kasten.height / 2
      expect(
        Math.abs(mitte(schliessen) - mitte(details)),
        'in derselben Zeile wie „Details“',
      ).toBeLessThanOrEqual(2)
      expect(schliessen.x, 'rechts von „Details“').toBeGreaterThan(details.x + details.width)
      expect(schliessen.x, 'im Panel links').toBeGreaterThanOrEqual(panel.x - TOLERANZ)
      expect(schliessen.y, 'im Panel oben').toBeGreaterThanOrEqual(panel.y - TOLERANZ)
      expect(schliessen.x + schliessen.width, 'im Panel rechts').toBeLessThanOrEqual(
        panel.x + panel.width + TOLERANZ,
      )
      expect(schliessen.y + schliessen.height, 'im Panel unten').toBeLessThanOrEqual(
        panel.y + panel.height + TOLERANZ,
      )
    } else {
      const flaeche = await rechteck(buehne(page))
      expect(schliessen.y + schliessen.height, 'oberhalb der Bühne').toBeLessThanOrEqual(
        flaeche.y + TOLERANZ,
      )
    }
  })

  test('passt das Bild in zwei Formaten und mit aufgeklappten Details in die Bühne ein', async ({
    page,
  }) => {
    await oeffneEntwurf(page)
    const alle = ausloeser(page)
    const anzahl = await alle.count()

    // VORBEDINGUNG: zwei Fotos mit paarweise verschiedenem natürlichem Format - sonst wäre die
    // Einpassung an einem einzigen Format zufällig richtig.
    const gewaehlt: { index: number; format: number }[] = []
    for (let index = 0; index < anzahl && gewaehlt.length < 2; index += 1) {
      const format = await kachelFormat(alle.nth(index))
      if (gewaehlt.every((eintrag) => Math.abs(eintrag.format - format) > 0.05)) {
        gewaehlt.push({ index, format })
      }
    }
    expect(gewaehlt, 'zwei Fotos mit verschiedenem Format im Entwurf').toHaveLength(2)

    for (const { index } of gewaehlt) {
      await alle.nth(index).click()
      await bildGeladen(page)
      await pruefeEinpassung(page, `Foto ${index}`)

      const vorher = await rechteck(buehne(page))
      await dialog(page).getByRole('button', { name: 'Details', exact: true }).click()
      await expect(page.getByRole('region', { name: 'Bilddetails' })).toBeVisible()
      await expect
        .poll(async () => (await rechteck(buehne(page))).height, 'Bühne schrumpft')
        .toBeLessThan(vorher.height - TOLERANZ)
      await pruefeEinpassung(page, `Foto ${index} mit Details`)

      await page.keyboard.press('Escape')
      await expect(dialog(page)).toBeHidden()
    }
  })

  test('schließt bei einem Klick neben das Bild, nicht bei einem Klick darauf', async ({
    page,
  }) => {
    test.skip(page.viewportSize()!.width < 640, 'seitliche Lücke nur in der breiten Ansicht')
    await oeffneEntwurf(page)
    const alle = ausloeser(page)
    const anzahl = await alle.count()

    let hochformat = -1
    for (let index = 0; index < anzahl; index += 1) {
      if ((await kachelFormat(alle.nth(index))) < 0.95) {
        hochformat = index
        break
      }
    }
    expect(hochformat, 'ein Hochformat im Entwurf').toBeGreaterThanOrEqual(0)

    await alle.nth(hochformat).click()
    await bildGeladen(page)
    const flaeche = await rechteck(buehne(page))
    const kasten = await rechteck(page.getByTestId('lightbox-image-box'))
    const luecke = kasten.x - flaeche.x
    expect(luecke, 'seitliche Lücke neben dem Hochformat').toBeGreaterThanOrEqual(20)
    const neben = { x: flaeche.x + luecke / 2, y: flaeche.y + flaeche.height / 2 }
    const getroffen = await page.evaluate(
      (punkt) => document.elementFromPoint(punkt.x, punkt.y)?.getAttribute('data-testid') ?? null,
      neben,
    )
    expect(getroffen, 'der Punkt neben dem Bild trifft die Bühne').toBe('lightbox-stage')

    await page.mouse.click(kasten.x + kasten.width / 2, kasten.y + kasten.height / 2)
    await expect(dialog(page), 'Klick in die Bildmitte').toBeVisible()
    await dialog(page).getByRole('heading', { level: 2 }).click()
    await expect(dialog(page), 'Klick auf die Kopfzeile').toBeVisible()
    await page.mouse.click(neben.x, neben.y)
    await expect(dialog(page), 'Klick in die Lücke').toBeHidden()

    await alle.nth(hochformat).click()
    await expect(dialog(page)).toBeVisible()
    await page.mouse.click(8, 8)
    await expect(dialog(page), 'Klick auf den Rand').toBeHidden()
  })

  test('hält über jeden Schließweg Platz, URL und Fokus', async ({ page }) => {
    const einstieg = await oeffneEntwurf(page)
    const sichtHoehe = page.viewportSize()!.height
    const alle = ausloeser(page)

    // Ein Auslöser, der unterhalb des ersten Bildschirms beginnt - nach dem Scrollen liegt er
    // nur TEILWEISE im Sichtfenster.
    const oberkanten = await alle.evaluateAll((knoten) =>
      knoten.map((element) => element.getBoundingClientRect().top + window.scrollY),
    )
    const index = oberkanten.findIndex((oben) => oben > sichtHoehe)
    expect(index, 'ein Auslöser unterhalb des ersten Bildschirms').toBeGreaterThanOrEqual(0)
    const trigger = alle.nth(index)
    await page.evaluate(([oben, hoehe]) => window.scrollTo(0, oben - hoehe + 40), [
      oberkanten[index]!,
      sichtHoehe,
    ] as const)
    const vorher = await scrollY(page)
    const kasten = await rechteck(trigger)
    expect(vorher, 'die Seite ist gescrollt').toBeGreaterThan(0)
    expect(kasten.y + kasten.height, 'Auslöser ragt unter den Fensterrand').toBeGreaterThan(
      sichtHoehe,
    )
    const url = page.url()

    const wege: [string, () => Promise<void>][] = [
      ['Schließen', () => page.getByRole('button', { name: 'Schließen' }).click()],
      ['Escape', () => page.keyboard.press('Escape')],
      [
        'Klick neben das Bild',
        async () => {
          await bildGeladen(page)
          const punkt = await punktNebenDemBild(page)
          expect(punkt, 'freie Bühnenfläche neben dem Bild').not.toBeNull()
          await page.mouse.click(punkt!.x, punkt!.y)
        },
      ],
      ['Browser-Zurück', () => page.goBack().then(() => undefined)],
    ]

    // Zwei Arten zu öffnen: per Mausklick (Chromium fokussiert den Button) und per Klick, der
    // nicht fokussiert (wie Safari), bei ungescrollter Seite und vollständig verdecktem Auslöser.
    // Geprüft wird je Schließweg, dass scrollY, URL und Fokus unverändert bleiben. Dass die
    // Fokus-Rückgabe mit `preventScroll` fokussiert, erzwingt der Unit-Test
    // `useCurationLightbox.test.tsx > focuses the registered trigger without scrolling when the
    // photo closes`; in Chromium wird dieser Fall ohne `preventScroll` nicht rot.
    const oeffnungen: [string, number, () => Promise<void>][] = [
      ['Mausklick', vorher, () => page.mouse.click(kasten.x + kasten.width / 2, sichtHoehe - 20)],
      [
        'Klick ohne Fokus',
        0,
        () =>
          trigger.evaluate((element) => {
            ;(document.activeElement as HTMLElement | null)?.blur()
            ;(element as HTMLElement).click()
          }),
      ],
    ]

    for (const [art, ausgang, oeffnen] of oeffnungen) {
      await page.evaluate((y) => window.scrollTo(0, y), ausgang)
      expect(Math.abs((await scrollY(page)) - ausgang), `${art}: Ausgangslage`).toBeLessThanOrEqual(
        TOLERANZ,
      )
      if (ausgang === 0) {
        expect(
          (await rechteck(trigger)).y,
          `${art}: Auslöser vollständig verdeckt`,
        ).toBeGreaterThan(sichtHoehe)
      }
      for (const [weg, schliessen] of wege) {
        const name = `${art}, ${weg}`
        await oeffnen()
        await expect(dialog(page), `${name}: geöffnet`).toBeVisible()
        expect(
          Math.abs((await scrollY(page)) - ausgang),
          `${name}: scrollY offen`,
        ).toBeLessThanOrEqual(TOLERANZ)

        await schliessen()

        await expect(dialog(page), `${name}: geschlossen`).toBeHidden()
        await expect(trigger, `${name}: Fokus auf dem Auslöser`).toBeFocused()
        expect(
          Math.abs((await scrollY(page)) - ausgang),
          `${name}: scrollY danach`,
        ).toBeLessThanOrEqual(TOLERANZ)
        expect(page.url(), `${name}: URL unverändert`).toBe(url)
      }
    }

    await page.goBack()
    await expect(page, 'genau ein Zurück führt zur Projektseite').toHaveURL(einstieg)
  })

  test('verlässt die Kuratierung auch bei zweimal Escape nicht', async ({ page }) => {
    const einstieg = await oeffneEntwurf(page)
    const url = page.url()
    const ueberschrift = page.getByRole('heading', { level: 1, name: 'Album-Entwurf' })

    // (a) Zwei Escape in EINEM Aufruf - sicher vor dem asynchronen `popstate`.
    await ausloeser(page).first().click()
    await expect(dialog(page)).toBeVisible()
    await dialog(page).evaluate((node) => {
      for (let mal = 0; mal < 2; mal += 1) {
        node.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
      }
    })
    await expect(dialog(page)).toBeHidden()
    await expect(ueberschrift, 'synthetisch: Überschrift sichtbar').toBeVisible()
    expect(page.url(), 'synthetisch: URL der Kuratierung').toBe(url)

    // (b) Zweimal nativ - der CloseWatcher-Pfad von Chromium.
    await ausloeser(page).first().click()
    await expect(dialog(page)).toBeVisible()
    await page.keyboard.press('Escape')
    await page.keyboard.press('Escape')
    await expect(dialog(page)).toBeHidden()
    await expect(ueberschrift, 'nativ: Überschrift sichtbar').toBeVisible()
    expect(page.url(), 'nativ: URL der Kuratierung').toBe(url)

    await page.goBack()
    await expect(page, 'genau ein Zurück führt zur Projektseite').toHaveURL(einstieg)
  })

  test('öffnet nach einem Reload dasselbe Foto wieder', async ({ page }) => {
    await oeffneEntwurf(page)
    const trigger = ausloeser(page).first()
    await trigger.click()
    const titel = await dialog(page).getByRole('heading', { level: 2 }).textContent()
    expect(titel, 'Dateiname in der Kopfzeile').toBeTruthy()

    await page.reload()

    await expect(dialog(page), 'nach dem Reload wieder offen').toBeVisible()
    await expect(dialog(page).getByRole('heading', { level: 2, name: titel! })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog(page)).toBeHidden()
    await expect(trigger, 'Fokus auf dem Auslöser').toBeFocused()

    await page.reload()
    await expect(ausloeser(page).first()).toBeVisible()
    await expect(dialog(page), 'nach dem zweiten Reload nichts offen').toHaveCount(0)
  })
})
