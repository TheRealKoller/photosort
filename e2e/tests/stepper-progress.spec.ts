/**
 * Die rechte Kante der Fortschrittsfuellung liegt auf der waagerechten Mitte des aktuellen
 * Schritts (specs/features/0387-schrittleiste-fortschritt.md).
 *
 * WARUM DIESE EBENE: Die Zusage zerfaellt in drei Teile, die einzeln nichts beweisen. Der ANTEIL
 * `value/max` haengt am Unit-Test von `stepProgress`, der GERENDERTE WERT am `<progress>` haengt
 * an jsdom - die eigentliche Produktaussage ist aber die RAEUMLICHE KOINZIDENZ von Anteil und
 * Spaltenmitte, und die haengt an gleich breiten, abstandslosen Spalten und einem Balken, der
 * exakt denselben x-Bereich aufspannt wie die Schrittliste. Ein einziges `gap-3` am `<ol>`
 * verschiebt die Spaltenmitten gegenueber der Balkenskala, ohne dass eine der beiden anderen
 * Ebenen es merkt. Ohne diesen Spec ruhte die Produktzusage auf einem Quelltextkommentar.
 *
 * WAS HIER BEWUSST NICHT GEMESSEN WIRD: die tatsaechlich GEMALTE Kante der Fuellung. Sie liegt in
 * einem Browser-Pseudo-Element (`::-webkit-progress-value`), das in keiner `boundingBox()`
 * auftaucht - dieselbe Grenze, die das Testkonzept schon bei den Trefferflaechen festhaelt. Die
 * Kante wird deshalb aus dem gerenderten `value/max` und dem echten Balkenkasten GERECHNET. Damit
 * traegt der Spec genau EINE unbewiesene Annahme: dass Chromium ein `<progress>` mit
 * `appearance-none` linear ueber seinen Inhaltskasten fuellt. Das ist eine Eigenschaft der
 * Plattform, keine unseres Codes, und im Testkonzept als benannte Luecke gefuehrt.
 *
 * Laeuft in BEIDEN Breiten (kein Eintrag in MOBILE_ONLY/DESKTOP_ONLY, in `toolchain.spec.ts`
 * gebunden): die Spaltenaufteilung wechselt an `sm:` von "Marke ueber volle Spaltenbreite" auf
 * "Marke plus Beschriftung" - ein zweiter Lauf ist hier also kein Leerlauf.
 *
 * Rot-Nachweis (Spec 0387): siehe PR-Beschreibung - mit `gap-3` am `<ol>` ist der Fall rot.
 */

import type { Page } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Subpixel-Toleranz. Enger geht nicht sinnvoll: Browser runden Layoutkanten. */
const TOLERANCE = 1

/** Die Zahl der Pipeline-Schritte. Steht auch im Produkt als `PIPELINE_STEPS.length`; hier
 * bewusst als eigene Erwartung, damit ein stiller Wegfall eines Schritts auffaellt. */
const STEP_COUNT = 5

interface Messung {
  /** Waagerechte Mitte der Spalte des aktuellen Schritts, im Viewport. */
  mitteDesAktivenSchritts: number
  /** Aus `value/max` und dem echten Balkenkasten gerechnete rechte Kante der Fuellung. */
  gerechneteFuellkante: number
}

async function messe(page: Page, erwarteterIndex: number): Promise<Messung> {
  const stepper = page.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
  await expect(stepper).toBeVisible()

  const spalten = stepper.getByRole('listitem')
  await expect(spalten, 'Spalten der Schrittleiste').toHaveCount(STEP_COUNT)

  const kaesten = await spalten.evaluateAll((elemente) =>
    elemente.map((element) => {
      const rect = element.getBoundingClientRect()
      return {
        x: rect.x,
        width: rect.width,
        // DER AKTIVE SCHRITT KOMMT AUS DEM DOM, nicht aus der aufgerufenen URL: ein Redirect des
        // Routen-Waechters fuehrte sonst dazu, dass die falsche Spalte gemessen wird und der Fall
        // trotzdem gruen ist.
        istAktiv: element.querySelector('[aria-current="step"]') !== null,
      }
    }),
  )

  // VORBEDINGUNG SPALTENGEOMETRIE: fuenf Spalten mit Breite > 0, paarweise gleich breit und
  // lueckenlos aneinander. Das ist die Zusicherung, die ein `gap-*` am `<ol>` unmittelbar rot
  // macht.
  for (const [index, kasten] of kaesten.entries()) {
    expect(kasten.width, `Breite der Spalte ${index + 1}`).toBeGreaterThan(0)
    expect(
      Math.abs(kasten.width - kaesten[0]!.width),
      `Spalte ${index + 1} ist nicht so breit wie die erste`,
    ).toBeLessThanOrEqual(TOLERANCE)
    if (index > 0) {
      const vorherigesEnde = kaesten[index - 1]!.x + kaesten[index - 1]!.width
      expect(
        Math.abs(kasten.x - vorherigesEnde),
        `Abstand zwischen Spalte ${index} und ${index + 1}`,
      ).toBeLessThanOrEqual(TOLERANCE)
    }
  }

  const aktiveIndizes = kaesten
    .map((kasten, index) => (kasten.istAktiv ? index : -1))
    .filter((index) => index >= 0)
  expect(aktiveIndizes, 'genau ein Schritt traegt aria-current="step"').toHaveLength(1)
  const aktiverIndex = aktiveIndizes[0]!
  expect(aktiverIndex, 'Index des aktuellen Schritts').toBe(erwarteterIndex)

  const balken = stepper.locator('progress')
  await expect(balken, 'Fortschrittsbalken in der Leiste').toHaveCount(1)
  const balkenKasten = await balken.evaluate((element) => {
    const rect = element.getBoundingClientRect()
    const progress = element as HTMLProgressElement
    return { x: rect.x, width: rect.width, value: progress.value, max: progress.max }
  })

  // VORBEDINGUNG BALKENKASTEN: linke und rechte Kante stimmen mit der ersten bzw. letzten Spalte
  // ueberein. Ohne sie waere die Rechnung unten auf einen anderen Kasten bezogen als die Spalten.
  expect(
    Math.abs(balkenKasten.x - kaesten[0]!.x),
    'linke Kante des Balkens gegenueber der ersten Spalte',
  ).toBeLessThanOrEqual(TOLERANCE)
  const letzte = kaesten[kaesten.length - 1]!
  expect(
    Math.abs(balkenKasten.x + balkenKasten.width - (letzte.x + letzte.width)),
    'rechte Kante des Balkens gegenueber der letzten Spalte',
  ).toBeLessThanOrEqual(TOLERANCE)

  // `value`/`max` werden GELESEN, nicht angenommen - und zusaetzlich gegen die Skala gehalten,
  // sonst bestuende die Rechnung auch mit einem festgefahrenen Wert.
  expect(balkenKasten.max, 'Skala des Balkens').toBe(2 * STEP_COUNT)
  expect(balkenKasten.value, 'Wert des Balkens').toBe(2 * aktiverIndex + 1)

  const aktiveSpalte = kaesten[aktiverIndex]!
  return {
    mitteDesAktivenSchritts: aktiveSpalte.x + aktiveSpalte.width / 2,
    gerechneteFuellkante:
      balkenKasten.x + (balkenKasten.width * balkenKasten.value) / balkenKasten.max,
  }
}

test('die Fuellung des Fortschrittsbalkens endet unter der Mitte des aktuellen Schritts', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.error)

  /*
   * ZWEI MESSUNGEN, DIE SICH UNTERSCHEIDEN MUESSEN. Beide Schritte sind immer erreichbar, werden
   * also nie umgeleitet.
   *
   * INDEX 0 IST BEWUSST DABEI: er ist die empfindlichste Spalte. Ein `gap-3` verschoebe die Mitte
   * dort um rund 4,8px, in der MITTLEREN Spalte dagegen um exakt 0px - ein Fall, der nur den
   * mittleren Schritt misst, waere gegen genau den Fehler blind, gegen den er geschrieben wurde.
   */
  const faelle: [string, number][] = [
    ['scan', 0],
    ['ausschuss', 1],
  ]
  const gemesseneKanten: number[] = []

  for (const [step, index] of faelle) {
    await page.goto(`/projects/${projectId}/pipeline/${step}`)
    const { mitteDesAktivenSchritts, gerechneteFuellkante } = await messe(page, index)

    expect(
      Math.abs(gerechneteFuellkante - mitteDesAktivenSchritts),
      `Abstand der Fuellkante zur Spaltenmitte auf /pipeline/${step}`,
    ).toBeLessThanOrEqual(TOLERANCE)

    gemesseneKanten.push(gerechneteFuellkante)
  }

  // Ohne diese Zusicherung bestuende der Fall auch dann, wenn beide Durchlaeufe dieselbe Stelle
  // gemessen haetten - etwa weil der Balken gar nicht auf den aktuellen Schritt reagiert.
  expect(gemesseneKanten, 'Zahl der Messungen').toHaveLength(faelle.length)
  expect(
    Math.abs(gemesseneKanten[1]! - gemesseneKanten[0]!),
    'Unterschied der beiden Fuellkanten',
  ).toBeGreaterThan(TOLERANCE)
})
