/**
 * Die Pruefseite einer Klassifizierung in echter Geometrie (specs/features/0616-
 * klassifizierungsverfahren-vergleichen.md, Stufe 7): jsdom kennt keine Layout-Engine, deshalb
 * laesst sich hier erstens messen, ob die Fallansicht ab der Breite zweispaltig steht, zweitens
 * ob die mitlaufende Kopfzeile die Foto-Ueberschrift verdeckt (die Tastatur springt per
 * Pfeiltaste darauf und fokussiert sie), drittens ob das `object-contain`-Bild an seinen Ecken
 * selbst getroffen wird und viertens ob die vier Urteilsflaechen bei 360 px treffbar sind.
 *
 * Vorbedingung ist eine GESEEDETE, ABGESCHLOSSENE Pruefung - der Spec loest den Job nie aus und
 * braucht deshalb kein Eye und keinen Cloud-Anbieter. Er laeuft in beiden Viewport-Projekten; die
 * Anordnung haengt an der Breite und wird je Projekt gegen die dort geltende Erwartung geprueft.
 *
 * Der Urteilsweg SCHREIBT (ein Urteil ist ein gespeicherter Zustand, kein Dialog): Beide Wege
 * beurteilen je einen noch offenen Fall, und ein Fall ohne Urteil bleibt uebrig. Ein zweiter Lauf
 * gegen denselben Bestand beurteilt den naechsten offenen Fall - der Spec sucht ihn, statt eine
 * feste Fallnummer anzunehmen.
 */

import type { Locator, Page } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Subpixel-Toleranz: Chromium meldet Bruchteile, ein echter Ueberstand ist groesser. */
const TOLERANCE = 1
/** `sm` - ab hier stehen Foto und Fallliste nebeneinander (UI-Zusage der Spec 0616). Die beiden
 * Projekt-Viewports (360 und 1280) liegen auf verschiedenen Seiten dieses Werts. */
const SM_BREAKPOINT = 640
/** Zugesicherte Mindest-Trefferflaeche in px (Design-System). */
const TAP_TARGET_SIZE = 44
/** Die vier Urteile, wie sie im zugänglichen Namen beginnen (die Taste steht dahinter). */
const VERDICT_NAMES = /^(A besser|B besser|beide ok|beide falsch)/

const casesOfPhoto = (page: Page): Locator => page.locator('li[data-testid^="review-case-"]')
const photoHeading = (page: Page): Locator =>
  page.getByRole('heading', { level: 2, name: /^Foto \d+ von \d+$/ })
const openCase = (page: Page): Locator =>
  casesOfPhoto(page).filter({ hasNot: page.locator('button[aria-pressed="true"]') })

/** Oeffnet Liste und Detailseite der geseedeten Pruefung und belegt beide Vorbedingungen. */
async function openSeededReview(page: Page): Promise<void> {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${projectId}/klassifizierung-pruefen`)

  const row = page.getByRole('link', { name: /angelegt von / }).first()
  await expect(row, 'Zeile der geseedeten Pruefung in der Liste').toBeVisible()
  await expect(row, 'Zustand der Pruefung in der Liste').toContainText(
    /Fällen offen|alle beurteilt/,
  )
  await row.click()

  await expect(page, 'Detailseite der Pruefung').toHaveURL(/\/klassifizierung-pruefen\/\d+/)
  await expect(photoHeading(page), 'Fallansicht mit einem Foto').toBeVisible()
  await expect(page.getByRole('group', { name: /^Urteil zu / }).first()).toBeVisible()
}

test('die Liste fuehrt in die Fallansicht einer abgeschlossenen Pruefung', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${projectId}/klassifizierung-pruefen`)
  await expect(
    page.getByRole('heading', { level: 1, name: 'Klassifizierung prüfen' }),
    'Ueberschrift der Liste',
  ).toBeVisible()

  await page
    .getByRole('link', { name: /angelegt von / })
    .first()
    .click()

  await expect(page, 'Adresse der Fallansicht').toHaveURL(/\/klassifizierung-pruefen\/\d+$/)
  await expect(
    page.getByRole('heading', { level: 1, name: 'Klassifizierung prüfen' }),
    'Ueberschrift der Fallansicht',
  ).toBeVisible()
  // Herkunft beider Seiten: ohne sie waere die Ansicht ein Vergleich zweier unbekannter Verfahren.
  await expect(
    page.getByRole('list', { name: 'Herkunft der Seiten' }).getByRole('listitem'),
    'beide Herkuenfte',
  ).toHaveCount(2)
  await expect(photoHeading(page), 'Fallansicht des ersten offenen Fotos').toBeVisible()
  await expect(page.getByRole('list', { name: 'Fälle dieses Fotos' })).toBeVisible()
})

test('ein Urteil wird per Klick und per Taste geschrieben', async ({ page }) => {
  await openSeededReview(page)

  // Der Fall wird ueber seine Test-Id angeheftet: seine Rolle in "noch offen" wechselt mit dem
  // geschriebenen Urteil, ein Locator ueber den offenen Faellen traefe ihn danach nicht mehr.
  const clickedTestId = await openCase(page).first().getAttribute('data-testid')
  expect(clickedTestId, 'Test-Id des offenen Falls').not.toBeNull()
  const clicked = page.getByTestId(clickedTestId ?? '')
  await expect(clicked, 'ein noch offener Fall fuer den Klick').toBeVisible()
  const clickVerdict = clicked.getByRole('button', { name: /^B besser/ })
  await clickVerdict.click()
  await expect(clickVerdict, 'Urteil nach dem Klick').toHaveAttribute('aria-pressed', 'true')

  // --- Taste ---------------------------------------------------------------------------------
  // Der gezeigte Fall kann der LETZTE offene dieses Fotos gewesen sein: das Foto der Fallansicht
  // ist das erste mit einem offenen Fall, und nach mehreren Laeufen ohne neuen Seed bleiben
  // wenige uebrig. Dann traegt das naechste offene Foto den zweiten Fall.
  if ((await openCase(page).count()) === 0) {
    const naechstesOffenesFoto = page.getByRole('button', { name: 'Nächstes offenes Foto' })
    await expect(naechstesOffenesFoto, 'ein weiteres offenes Foto').toBeEnabled()
    await naechstesOffenesFoto.click()
  }
  const typedTestId = await openCase(page).first().getAttribute('data-testid')
  expect(typedTestId, 'Test-Id eines weiteren offenen Falls').not.toBeNull()
  expect(typedTestId, 'die Taste beurteilt einen anderen Fall').not.toBe(clickedTestId)
  const typed = page.getByTestId(typedTestId ?? '')
  await expect(typed, 'ein weiterer offener Fall fuer die Taste').toBeVisible()
  // Markieren per Klick auf den Block; danach nimmt genau dieser Fall die Taste entgegen.
  await typed.getByRole('heading', { level: 3 }).click()
  await expect(typed, 'markierter Fall').toHaveAttribute('aria-current', 'true')
  await page.keyboard.press('f')

  await expect(
    typed.getByRole('button', { name: /^beide falsch/ }),
    'Urteil nach der Taste',
  ).toHaveAttribute('aria-pressed', 'true')
  await expect(
    typed
      .getByRole('button', { name: VERDICT_NAMES })
      .and(page.locator('button[aria-pressed="true"]')),
    'genau ein gesetztes Urteil am Fall',
  ).toHaveCount(1)
})

test('die Fallansicht ordnet Foto und Faelle nach der Breite an', async ({ page }) => {
  await openSeededReview(page)
  const breite = page.viewportSize()?.width ?? 0

  const foto = await photoHeading(page).boundingBox()
  const faelle = await page.getByRole('list', { name: 'Fälle dieses Fotos' }).boundingBox()
  expect(foto && faelle, 'beide Spalten gerendert').toBeTruthy()
  if (foto === null || faelle === null) {
    return
  }

  if (breite >= SM_BREAKPOINT) {
    // Nebeneinander: die Fallliste beginnt rechts der Foto-Spalte, beide Spalten starten oben.
    expect(faelle.x, 'Fallliste rechts des Fotos').toBeGreaterThanOrEqual(
      foto.x + foto.width - TOLERANCE,
    )
    expect(Math.abs(faelle.y - foto.y), 'gleiche Oberkante beider Spalten').toBeLessThanOrEqual(40)
  } else {
    // Untereinander: die Fallliste beginnt unter der Foto-Ueberschrift, in derselben Spalte.
    expect(faelle.y, 'Fallliste unter der Foto-Ueberschrift').toBeGreaterThanOrEqual(
      foto.y + foto.height - TOLERANCE,
    )
    expect(Math.abs(faelle.x - foto.x), 'Fallliste in derselben Spalte').toBeLessThanOrEqual(1)
  }
})

test('die mitlaufende Kopfzeile verdeckt die fokussierte Foto-Ueberschrift nicht', async ({
  page,
}) => {
  await openSeededReview(page)
  // Der Tastaturweg springt auf das Nachbarfoto und fokussiert dort die Foto-Ueberschrift -
  // genau der Weg, auf dem die mitlaufende Kopfzeile sie verdecken koennte. Welche Richtung
  // traegt, haengt davon ab, wo das erste offene Foto der Pruefung liegt; das Urteil des
  // vorherigen Tests kann die Lage verschieben.
  const weiter = page.getByRole('button', { name: 'Nächstes Foto' })
  const zurueck = page.getByRole('button', { name: 'Vorheriges Foto' })
  const richtung = (await weiter.isEnabled()) ? 'ArrowRight' : 'ArrowLeft'
  expect(
    (await weiter.isEnabled()) || (await zurueck.isEnabled()),
    'ein Nachbarfoto mit Fall',
  ).toBe(true)

  // Ans Seitenende: die Ueberschrift liegt danach ausserhalb des Sichtbereichs, und das
  // Fokussieren rollt sie zwangslaeufig heran.
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0)
  await page.keyboard.press(richtung)

  const kopfzeile = await page.getByRole('banner').boundingBox()
  const ueberschrift = await photoHeading(page).boundingBox()
  expect(kopfzeile && ueberschrift, 'Kopfzeile und Ueberschrift gemessen').toBeTruthy()
  if (kopfzeile === null || ueberschrift === null) {
    return
  }
  expect(
    ueberschrift.y,
    'Oberkante der fokussierten Ueberschrift unter der Kopfzeile',
  ).toBeGreaterThanOrEqual(kopfzeile.y + kopfzeile.height - TOLERANCE)
})

test('das Foto wird im Inhaltsrechteck an allen vier Ecken selbst getroffen', async ({ page }) => {
  await openSeededReview(page)

  const bild = page.getByRole('img', { name: /^Foto \d+ von \d+$/ }).first()
  await expect(bild, 'Bild der Fallansicht').toBeVisible()
  await expect
    .poll(() => bild.evaluate((element) => (element as HTMLImageElement).naturalWidth))
    .toBeGreaterThan(0)

  const treffer = await bild.evaluate((element) => {
    const img = element as HTMLImageElement
    img.scrollIntoView({ block: 'center' })
    const rect = img.getBoundingClientRect()
    // Das Inhaltsrechteck von `object-contain`: eingepasst und mittig.
    const scale = Math.min(rect.width / img.naturalWidth, rect.height / img.naturalHeight)
    const breite = img.naturalWidth * scale
    const hoehe = img.naturalHeight * scale
    const links = rect.x + (rect.width - breite) / 2
    const oben = rect.y + (rect.height - hoehe) / 2
    // 8 px statt 2: das Bild traegt `rounded-md` (6 px Radius), und `elementFromPoint` respektiert
    // die Rundung - 2 px innerhalb der Ecke laege AUSSERHALB der Bildflaeche und traefe den
    // Elternblock. Geprueft wird damit weiter der aeusserste Punkt, den das Bild selbst besitzt.
    const rand = 8
    const ecken: [number, number][] = [
      [links + rand, oben + rand],
      [links + breite - rand, oben + rand],
      [links + rand, oben + hoehe - rand],
      [links + breite - rand, oben + hoehe - rand],
    ]
    return ecken.map(([x, y]) => {
      const getroffen = document.elementFromPoint(x, y)
      return getroffen === img ? 'Bild' : `<${getroffen?.tagName.toLowerCase() ?? 'nichts'}>`
    })
  })

  expect(treffer, 'nichts liegt ueber dem Foto').toEqual(['Bild', 'Bild', 'Bild', 'Bild'])
})

test('bei 360 px scrollt die Fallansicht nicht waagerecht und die vier Urteile treffen', async ({
  page,
}) => {
  test.skip((page.viewportSize()?.width ?? 0) !== 360, 'nur in der Telefonbreite gemessen')
  await openSeededReview(page)

  const breiten = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(breiten.scrollWidth, 'kein waagerechtes Scrollen').toBeLessThanOrEqual(
    breiten.clientWidth + TOLERANCE,
  )

  const fall = casesOfPhoto(page).first()
  const urteile = fall.getByRole('button', { name: VERDICT_NAMES })
  await expect(urteile, 'vier Urteilsflaechen').toHaveCount(4)
  for (const knopf of await urteile.all()) {
    const label = (await knopf.textContent())?.trim() ?? 'Urteil'
    await expect(knopf, `Urteilsflaeche "${label}"`).toBeEnabled()
    await knopf.evaluate((element) => element.scrollIntoView({ block: 'center' }))
    const treffer = await knopf.evaluate((element, size) => {
      const rect = element.getBoundingClientRect()
      const centerX = rect.x + rect.width / 2
      const centerY = rect.y + rect.height / 2
      const half = size / 2 - 0.5
      const ecken: [number, number][] = [
        [centerX - half, centerY - half],
        [centerX + half, centerY - half],
        [centerX - half, centerY + half],
        [centerX + half, centerY + half],
      ]
      return ecken.map(([x, y]) => {
        const getroffen = document.elementFromPoint(x, y)
        if (getroffen === null) {
          return 'nichts getroffen'
        }
        return getroffen === element || element.contains(getroffen)
          ? 'Bedienelement'
          : `Fremdelement <${getroffen.tagName.toLowerCase()}>`
      })
    }, TAP_TARGET_SIZE)
    expect(treffer, `Treffer an den Ecken der ${TAP_TARGET_SIZE}px-Flaeche von "${label}"`).toEqual(
      ['Bedienelement', 'Bedienelement', 'Bedienelement', 'Bedienelement'],
    )
  }
})
