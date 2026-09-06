/**
 * Popover-Positionierung: Kollisionsvermeidung am Bildschirmrand und die Hoehenschranke.
 *
 * Radix positioniert das Panel zur Laufzeit ueber gemessene Geometrie - in jsdom (keine
 * Layout-Engine, alle Rechtecke 0x0) ist davon nichts pruefbar, weshalb dieser Punkt bis zur
 * Einfuehrung dieser Ebene "manueller visueller Smoke-Test vor Merge" war. Die jsdom-Tests von
 * `CriterionDetailsPopover` (Oeffnen/Schliessen, Inhalt, Hover-Verhalten) bleiben unveraendert
 * bestehen; hier wird ausschliesslich Geometrie gemessen, nichts davon dupliziert.
 *
 * NUR IM SCHMALEN VIEWPORT (siehe `MOBILE_ONLY` in playwright.config.ts): Der Inhaltsbereich ist
 * auf `max-w-5xl` begrenzt und mittig gesetzt - bei 1280 px liegt jeder Trigger so weit vom
 * Fensterrand entfernt, dass eine naiv mittig gesetzte Panelbreite gar nicht anstiesse. Der Spec
 * liefe dort also gruen, ohne die Kollisionsvermeidung ueberhaupt herauszufordern; genau das
 * schliesst die Vorbedingung unten aus.
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-05): siehe PR-Beschreibung - mit einer erzwungenen
 * `margin-left: 120px`-Verschiebung des Panels meldete der Spec
 * "rechte Kante des Popovers auf \"Foto-Grid\": expected <= 361, received 408".
 */

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** `w-72` des Panels (frontend/src/components/ui/popover.tsx) - Grundlage der Vorbedingung. */
const POPOVER_WIDTH = 288
/** `max-h-[60vh]` desselben Panels. */
const MAX_HEIGHT_SHARE = 0.6
/** Subpixel-Toleranz fuer Kanten- und Hoehenvergleiche. */
const TOLERANCE = 1

test('geoeffnete Popover bleiben vollstaendig im Sichtbereich', async ({ page }) => {
  const ratedId = await demoProjectId(page, DEMO_PROJECTS.rated)

  const routes = [
    { label: 'Foto-Grid', path: `/projects/${ratedId}/photos` },
    { label: 'Statistik', path: `/projects/${ratedId}/stats` },
    { label: 'Kategorie-Kuratierung', path: `/projects/${ratedId}/curate` },
  ]

  const viewport = page.viewportSize()
  expect(viewport, 'Viewport-Groesse').not.toBeNull()

  for (const route of routes) {
    await page.goto(route.path)

    // Radix setzt aria-haspopup auf den Trigger - lokalisiert wird ueber dieses aria-Attribut,
    // nicht ueber Klassennamen (Selektor-Konvention des Testkonzepts).
    //
    // AUF `main` EINGEGRENZT (specs/features/0298-projektnavigation-in-der-kopfzeile.md): seit der
    // Projekt-Navigationsgruppe traegt auch die KOPFZEILE einen Popover-Trigger, und bei 360 px
    // steht er als erster im Dokument. Dokumentweit lokalisiert bliebe dieser Spec still gruen und
    // pruefte dreimal dasselbe Kopfzeilen-Panel statt der drei Panels der drei Seiten - der
    // gefaehrlichere der beiden Faelle, weil nichts rot wird.
    const triggers = page.getByRole('main').locator('button[aria-haspopup="dialog"]')
    await expect(triggers.first(), `Popover-Trigger auf "${route.label}"`).toBeAttached()

    // Der randnaechste Trigger der Seite - genau der, an dem sich Kollisionsvermeidung
    // entscheidet. Ein bequemer Trigger in der Bildmitte pruefte gar nichts.
    const boxes = await triggers.evaluateAll((elements) =>
      elements.map((element) => {
        const rect = element.getBoundingClientRect()
        return { centerX: rect.x + rect.width / 2, width: rect.width }
      })
    )
    const viewportWidth = viewport!.width
    const distances = boxes.map((box) => Math.min(box.centerX, viewportWidth - box.centerX))
    const nearestIndex = distances.indexOf(Math.min(...distances))
    const trigger = triggers.nth(nearestIndex)

    await trigger.scrollIntoViewIfNeeded()
    await expect(trigger).toBeVisible()

    // Vorbedingung: der gewaehlte Trigger ist NACHWEISLICH randnah - ein mittig an ihm
    // ausgerichtetes Panel der bekannten Breite ragte ueber den Rand hinaus und muss von der
    // Kollisionsvermeidung zurueckgeschoben werden. Ohne diese Zusicherung waere der Test auch
    // dann gruen, wenn die Kollisionsvermeidung gar nicht mehr griffe.
    const triggerBox = await trigger.boundingBox()
    expect(triggerBox, `Trefferflaeche des Triggers auf "${route.label}"`).not.toBeNull()
    const triggerCenterX = triggerBox!.x + triggerBox!.width / 2
    const edgeDistance = Math.min(triggerCenterX, viewportWidth - triggerCenterX)
    expect(
      edgeDistance,
      `Abstand des gewaehlten Triggers auf "${route.label}" zum naechsten Viewport-Rand`
    ).toBeLessThan(POPOVER_WIDTH / 2)

    await trigger.click()
    const panel = page.getByRole('dialog')
    await expect(panel, `Popover auf "${route.label}"`).toBeVisible()

    const panelBox = await panel.boundingBox()
    expect(panelBox, `Panel-Rechteck auf "${route.label}"`).not.toBeNull()
    const { x, y, width, height } = panelBox!

    // Groesse > 0 zuerst: ein auf 0x0 kollabiertes Panel laege sonst trivial "vollstaendig im
    // Sichtbereich".
    expect(width, `Breite des Popovers auf "${route.label}"`).toBeGreaterThan(0)
    expect(height, `Hoehe des Popovers auf "${route.label}"`).toBeGreaterThan(0)

    expect(x, `linke Kante des Popovers auf "${route.label}"`).toBeGreaterThanOrEqual(-TOLERANCE)
    expect(y, `obere Kante des Popovers auf "${route.label}"`).toBeGreaterThanOrEqual(-TOLERANCE)
    expect(x + width, `rechte Kante des Popovers auf "${route.label}"`).toBeLessThanOrEqual(
      viewportWidth + TOLERANCE
    )
    expect(y + height, `untere Kante des Popovers auf "${route.label}"`).toBeLessThanOrEqual(
      viewport!.height + TOLERANCE
    )

    // Die Hoehenschranke des Panels (`max-h-[60vh]`) - ohne sie koennte ein langer Inhalt das
    // Panel ueber die gesamte Seitenhoehe ziehen, statt in sich zu scrollen.
    expect(height, `Hoehenanteil des Popovers auf "${route.label}"`).toBeLessThanOrEqual(
      viewport!.height * MAX_HEIGHT_SHARE + TOLERANCE
    )

    await page.keyboard.press('Escape')
    await expect(panel, `Popover nach Escape auf "${route.label}"`).toBeHidden()
  }
})
