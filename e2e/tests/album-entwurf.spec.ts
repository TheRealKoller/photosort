/**
 * Der Album-Entwurf im echten Browser (specs/features/0558-album-entwurf-verstaendlich.md), in
 * beiden Breiten.
 *
 * Geprueft wird nur, was jsdom prinzipiell nicht kann: die mitlaufende Kopfleiste beim Scrollen,
 * die Lage des Rueckgaengig-Hinweises im Sichtbereich, die unveraenderte Scrollposition nach dem
 * Streichen und der Gleichstand nach einem echten Neuladen. Die Zustandslogik selbst liegt in den
 * Vitest-Faellen.
 *
 * DER ERSTE SCHREIBENDE FALL DES PRUEFSATZES. Alle Specs teilen sich EINEN geseedeten Bestand;
 * deshalb setzt er die eigenen Entscheidungen im `finally` ueber die API zurueck
 * (`lib/draft.ts`) - auch dann, wenn genau die Oberflaeche der Grund des Fehlschlags ist.
 */

import type { Locator, Page } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { readOwnDraftStates, restoreOwnDraftStates } from '../lib/draft.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Subpixel-Toleranz fuer Lage- und Scrollvergleiche. */
const TOLERANCE = 1

function draftBar(page: Page): Locator {
  return page.locator('[data-draft-bar]')
}

/** Die Zaehlerzeile der Kopfleiste: „{n} im Album · Richtwert etwa … · … gestrichen". */
function counterLine(page: Page): Locator {
  return draftBar(page).getByText(/ im Album · Richtwert etwa /)
}

async function openDraft(page: Page): Promise<number> {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${projectId}/album`)
  await expect(counterLine(page), 'Zaehlerzeile der Kopfleiste').toBeVisible()
  return projectId
}

test('die Kopfleiste nennt nach dem Scrollen das Event des Abschnitts und bleibt sichtbar', async ({
  page,
}) => {
  await openDraft(page)
  const bar = draftBar(page)
  await expect(bar).toContainText(/Event 1 von \d+/)

  const total = Number(/Event \d+ von (\d+)/.exec((await bar.textContent()) ?? '')?.[1])
  // Vorbedingung: Es gibt ein ZWEITES Event - sonst bewiese „Event 1 von 1" nach dem Scrollen nichts.
  expect(total, 'Anzahl der Events im Demo-Entwurf').toBeGreaterThan(1)

  // Ein Sprung wie beim Fokus-Scroll: `scrollIntoView` setzt den Abschnitt an seinen
  // `scroll-margin`, und die Leiste nennt danach genau dieses Event.
  const target = 2
  await page.locator(`section[data-draft-position="${target}"]`).evaluate((section) => {
    section.scrollIntoView({ block: 'start' })
  })

  await expect(bar).toContainText(`Event ${target} von ${total}`)
  const box = await bar.boundingBox()
  const viewport = page.viewportSize()
  expect(box, 'Kopfleiste im Layout').not.toBeNull()
  expect(viewport).not.toBeNull()
  expect(box!.y, 'Oberkante der Kopfleiste').toBeGreaterThanOrEqual(-TOLERANCE)
  expect(box!.y + box!.height, 'Unterkante der Kopfleiste').toBeLessThanOrEqual(viewport!.height)
})

test('Streichen haelt die Scrollposition, ueberlebt ein Neuladen und ist rueckgaengig zu machen', async ({
  page,
}) => {
  const projectId = await openDraft(page)
  const before = await readOwnDraftStates(page, projectId)

  try {
    const initialCounts = await counterLine(page).textContent()

    // Das AUFGENOMMENE Foto des ersten Events: Mit Rangzeile bleibt es gestrichen in der
    // Antwortmenge und erscheint in der Gestrichen-Zeile seines Events. Es steht weit genug oben,
    // dass das Dokument unter dem Sichtbereich noch Inhalt traegt - am Seitenende muesste der
    // Browser die Scrollposition nach dem Herausfallen einer Rasterzeile zwangslaeufig kappen,
    // und die Messung saehe dann diese Kappung statt eines Scrollsprungs.
    const strike = page
      .getByRole('listitem')
      .filter({ has: page.locator('[data-album-state="taken"]') })
      .getByRole('button', { name: /^Streichen: / })
      .first()
    await expect(strike, 'Streichen an einem vorgeschlagenen Foto').toBeVisible()
    const path = ((await strike.getAttribute('aria-label')) ?? '').replace(/^Streichen: /, '')
    const position = await strike.evaluate(
      (button) =>
        button.closest('section[data-draft-position]')?.getAttribute('data-draft-position') ?? '',
    )
    const section = page.locator(`section[data-draft-position="${position}"]`)
    const struckLine = section.getByRole('button', { name: /^\d+ gestrichen – / })
    const initialStruck = (await struckLine.count()) === 0 ? null : await struckLine.textContent()

    await strike.evaluate((button) => button.scrollIntoView({ block: 'center' }))
    const scrollBefore = await page.evaluate(() => window.scrollY)
    await strike.click()

    // Der Hinweis: im Sichtbereich, treffbar, Knopf nicht abgeschnitten.
    const undo = page.getByRole('button', { name: 'Rückgängig', exact: true })
    await expect(undo, 'Rückgängig-Hinweis').toBeVisible()
    const geometry = await undo.evaluate((button) => {
      const rect = button.getBoundingClientRect()
      const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)
      return {
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom,
        hitsButton: hit !== null && button.contains(hit),
        clipped: button.scrollWidth > button.clientWidth + 1,
        viewportWidth: document.documentElement.clientWidth,
        viewportHeight: window.innerHeight,
        scrollWidth: document.documentElement.scrollWidth,
      }
    })
    expect(geometry.left, 'linke Kante des Knopfs').toBeGreaterThanOrEqual(0)
    expect(geometry.right, 'rechte Kante des Knopfs').toBeLessThanOrEqual(geometry.viewportWidth)
    expect(geometry.top, 'Oberkante des Knopfs').toBeGreaterThanOrEqual(0)
    expect(geometry.bottom, 'Unterkante des Knopfs').toBeLessThanOrEqual(geometry.viewportHeight)
    expect(geometry.hitsButton, 'der Knopf ist an seiner Mitte treffbar').toBe(true)
    expect(geometry.clipped, 'die Beschriftung des Knopfs ist abgeschnitten').toBe(false)
    expect(geometry.scrollWidth, 'Dokumentbreite mit Hinweis').toBeLessThanOrEqual(
      geometry.viewportWidth + TOLERANCE,
    )

    const scrollAfter = await page.evaluate(() => window.scrollY)
    expect(
      Math.abs(scrollAfter - scrollBefore),
      'Scrollposition nach dem Streichen',
    ).toBeLessThanOrEqual(TOLERANCE)
    await expect(counterLine(page)).not.toHaveText(initialCounts ?? '')
    await expect(page.getByRole('button', { name: `Streichen: ${path}`, exact: true })).toHaveCount(
      0,
    )

    // Rückgängig stellt die Anfangszahlen wieder her.
    await undo.click()
    await expect(undo).toBeHidden()
    await expect(counterLine(page)).toHaveText(initialCounts ?? '')
    await expect(page.getByRole('button', { name: `Streichen: ${path}`, exact: true })).toHaveCount(
      1,
    )

    // Erneut streichen und neu laden: Kopfzahlen und Gestrichen-Zeile sind identisch.
    await page.getByRole('button', { name: `Streichen: ${path}`, exact: true }).click()
    await expect(undo).toBeVisible()
    const struckCounts = await counterLine(page).textContent()
    const struckText = await struckLine.textContent()
    expect(struckText, 'Gestrichen-Zeile nach dem Streichen').not.toBe(initialStruck)

    await page.reload()
    await expect(counterLine(page)).toHaveText(struckCounts ?? '')
    await expect(struckLine).toHaveText(struckText ?? '')
  } finally {
    await restoreOwnDraftStates(page, projectId, before)
  }
})
