/**
 * specs/features/0497-bilddetail-urteil-zuerst.md — die drei Zusagen der Bilddetailansicht, die in
 * jsdom PRINZIPIELL nicht messbar sind: `dvh` und `calc` werden dort nicht ausgewertet,
 * `object-contain` erzeugt kein eigenes Kästchen, und eine Schriftgröße in Pixeln entsteht erst im
 * Layout.
 *
 * DREI FÄLLE, EINE ROUTE, EIN GESEEDETER DURCHGANG:
 *
 * 1. **Bühne** (AK2, AK3a/3b, AK10) — vier Formate durchblättern, Bühnenhöhe gleich, Bild
 *    vollständig eingepasst und an seinen vier Ecken tatsächlich getroffen.
 * 2. **Reservierter Platz** (AK6) — die Oberkante der Kopfzeile „Qualität — Einzelwerte" über vier Zustände.
 * 3. **Typografischer Abstand** (AK5) — das Verhältnis zweier im selben Lauf gemessener
 *    `font-size`-Werte.
 *
 * DER SPEC IST LESEND. Ein Motiv anzuheften ist reiner Client-Zustand; die Korrekturschalter
 * werden nur GEMESSEN, nie geklickt - ein Klick schriebe einen Datenwert in den geteilten
 * Demo-Bestand, den jeder folgende Spec sieht.
 *
 * ER LÄUFT IN BEIDEN VIEWPORT-PROJEKTEN und steht deshalb in keiner der Listen
 * `MOBILE_ONLY`/`DESKTOP_ONLY`; `toolchain.spec.ts` bindet das fest, sonst ließe sich die
 * Zweibreitigkeit später still wegkonfigurieren.
 *
 * BEKANNTE LÜCKE: `100dvh` gegen eine dynamische Browserleiste ist hier nicht belegbar - headless
 * Chromium hat keine ein- und ausfahrende Adressleiste. Belegt ist die RECHNUNG, nicht das
 * Verhalten auf einem echten Telefon.
 */
import type { Locator, Page } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId, photoTiles } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Wie viele Fotos durchgeblättert werden. Der Seeder reiht vier Formate durch (4:3 quer, 3:4
 *  hoch, 12:5 breit, 1:1 quadratisch), vier aufeinanderfolgende Fotos decken sie also alle ab. */
const FORMATE = 4

/** Zulässige Abweichung in px. Subpixel-Layout macht exakte Gleichheit unerreichbar. */
const TOLERANZ = 1

/** AK5: Das Urteil steht mindestens beim 1,4-fachen der Rasterschrift. Die Schwelle ist eine
 *  Produktzusage der Spec; `text-lg` gegen `text-sm` ergibt 1,43. */
const SCHRIFT_FAKTOR = 1.4

interface Rechteck {
  x: number
  y: number
  width: number
  height: number
}

/**
 * Das INHALTSRECHTECK eines `object-contain`-Bildes, gerechnet aus `naturalWidth`/`naturalHeight`
 * und dem Elementkasten.
 *
 * Es taucht in KEINER `boundingBox()` auf: Der Elementkasten ist der volle Kasten, das tatsächlich
 * bemalte Rechteck darin ist kleiner und zentriert. Ohne diese Rechnung prüfte der Fall die
 * Position eines Kastens, in dem das Bild auch gar nicht stehen könnte.
 */
async function inhaltsRechteck(bild: Locator): Promise<Rechteck & { format: number }> {
  return bild.evaluate((node) => {
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

/**
 * Öffnet das Foto an Position `index` der Übersicht über den ECHTEN Einstieg (Kachel-Klick).
 *
 * WARTET AUF DIE SCHRIFTEN, bevor gemessen werden darf. Das Produkt lädt vier Inter-Schnitte über
 * `@fontsource` nach; bis sie da sind, setzt der Browser mit einer Ersatzschrift und anderen
 * Textmetriken. Jede Zeile, die dabei von ein- auf zweizeilig springt - die Grundlagenzeile des
 * Motivbereichs etwa -, verschiebt alles darunter um ihre Zeilenhöhe. Eine Messung vor dem
 * Schriftwechsel ist deshalb nicht falsch, sondern SPRUNGHAFT: Sie trifft je nach Auslastung mal
 * den einen, mal den anderen Zustand. Ohne dieses Warten fällt die Zusage „nichts darunter bewegt
 * sich" gelegentlich - und ein Fehlschlag, der nur manchmal kommt, ist kein verlässliches Signal.
 */
async function oeffneFoto(page: Page, projectId: number, index: number): Promise<void> {
  await page.goto(`/projects/${projectId}/photos`)
  const kacheln = photoTiles(page)
  await expect(kacheln.first(), 'Kacheln der Fotoübersicht').toBeVisible()
  await kacheln.nth(index).getByRole('link').first().click()
  await expect(page.getByRole('group', { name: 'Bewertung' })).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

function buehne(page: Page): Locator {
  return page.getByTestId('photo-detail-stage')
}

test.describe('Bilddetail: die Bühne', () => {
  test('hält Foto, Bewertung und Navigation ohne Scrollen im Sichtfenster', async ({ page }) => {
    const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

    const hoehen: number[] = []
    const formate: number[] = []

    for (let index = 0; index < FORMATE; index += 1) {
      await oeffneFoto(page, projectId, index)

      const bild = page.locator('[data-testid="photo-detail-stage-photo"] img')
      await expect(bild, `Foto ${index}`).toBeVisible()
      // Erst messen, wenn das Bild seine natürlichen Maße kennt - sonst ist das Format NaN.
      await expect
        .poll(() => bild.evaluate((node) => (node as HTMLImageElement).naturalWidth))
        .toBeGreaterThan(0)

      const sicht = page.viewportSize()!
      const scrollY = await page.evaluate(() => window.scrollY)
      const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight)

      // AK2, ZWEITER HALBSATZ: Die Seite trägt NACHWEISLICH weiteren Inhalt. Ohne ihn wäre die
      // Zusage auf einer zufällig kurzen Seite trivial erfüllt.
      expect(scrollY, `Foto ${index}: ungescrollt`).toBe(0)
      expect(scrollHeight, `Foto ${index}: die Seite trägt weiteren Inhalt`).toBeGreaterThan(
        sicht.height,
      )

      const rahmen = (await buehne(page).boundingBox())!
      hoehen.push(rahmen.height)

      // Bewertungsleiste UND Navigationszeile liegen vollständig im Sichtfenster.
      for (const [name, element] of [
        ['Bewertungsleiste', page.getByRole('group', { name: 'Bewertung' })],
        ['Navigation', page.getByRole('button', { name: 'Vorheriges Foto' })],
      ] as const) {
        const kasten = (await element.boundingBox())!
        expect(kasten.y, `Foto ${index}: ${name} oben im Bild`).toBeGreaterThanOrEqual(0)
        expect(
          kasten.y + kasten.height,
          `Foto ${index}: ${name} unten im Bild`,
        ).toBeLessThanOrEqual(sicht.height + TOLERANZ)
      }

      // AK3a — NICHT BESCHNITTEN: Das Inhaltsrechteck liegt vollständig im Elementkasten UND
      // vollständig im Sichtfenster.
      const inhalt = await inhaltsRechteck(bild)
      formate.push(inhalt.format)
      const kasten = (await bild.boundingBox())!
      expect(inhalt.x, `Foto ${index}: Inhalt links im Kasten`).toBeGreaterThanOrEqual(
        kasten.x - TOLERANZ,
      )
      expect(inhalt.y, `Foto ${index}: Inhalt oben im Kasten`).toBeGreaterThanOrEqual(
        kasten.y - TOLERANZ,
      )
      expect(inhalt.x + inhalt.width, `Foto ${index}: Inhalt rechts im Kasten`).toBeLessThanOrEqual(
        kasten.x + kasten.width + TOLERANZ,
      )
      expect(inhalt.y + inhalt.height, `Foto ${index}: Inhalt unten im Kasten`).toBeLessThanOrEqual(
        kasten.y + kasten.height + TOLERANZ,
      )
      expect(inhalt.y, `Foto ${index}: Inhalt oben im Sichtfenster`).toBeGreaterThanOrEqual(
        -TOLERANZ,
      )
      expect(
        inhalt.y + inhalt.height,
        `Foto ${index}: Inhalt unten im Sichtfenster`,
      ).toBeLessThanOrEqual(sicht.height + TOLERANZ)

      // AK3b — NICHT ÜBERLAGERT, NICHT GEKLIPPT: An den vier Ecken des INHALTSRECHTECKS (1 px
      // eingerückt) liefert `elementFromPoint` das Bild selbst oder einen Nachfahren. Gemessen
      // wird der TREFFER, nicht die Fläche: Eine Überlagerung ändert keine `boundingBox()`.
      const ecken = [
        [inhalt.x + 1, inhalt.y + 1],
        [inhalt.x + inhalt.width - 1, inhalt.y + 1],
        [inhalt.x + 1, inhalt.y + inhalt.height - 1],
        [inhalt.x + inhalt.width - 1, inhalt.y + inhalt.height - 1],
      ] as const
      for (const [ex, ey] of ecken) {
        const getroffen = await bild.evaluate(
          (node, punkt) => {
            const ziel = document.elementFromPoint(punkt[0], punkt[1])
            return ziel !== null && (ziel === node || node.contains(ziel))
          },
          [ex, ey] as [number, number],
        )
        expect(getroffen, `Foto ${index}: Ecke (${ex}, ${ey}) trifft das Bild`).toBe(true)
      }

      // AK3c — NICHT GEDÄMPFT: weder auf dem Bild noch auf einem seiner Vorfahren eine Deckkraft-,
      // Filter- oder Mischmodus-Utility.
      const gedaempft = await bild.evaluate((node) => {
        const befunde: string[] = []
        let aktuell: Element | null = node
        while (aktuell !== null) {
          const stil = getComputedStyle(aktuell)
          if (Number(stil.opacity) < 1) {
            befunde.push(`${aktuell.tagName}: opacity ${stil.opacity}`)
          }
          if (stil.filter !== 'none') {
            befunde.push(`${aktuell.tagName}: filter ${stil.filter}`)
          }
          if (stil.mixBlendMode !== 'normal') {
            befunde.push(`${aktuell.tagName}: mix-blend-mode ${stil.mixBlendMode}`)
          }
          aktuell = aktuell.parentElement
        }
        return befunde
      })
      expect(gedaempft, `Foto ${index}: keine Dämpfung auf dem Bild oder einem Vorfahren`).toEqual(
        [],
      )
    }

    // AK10 — VORBEDINGUNG: Die vier Eingaben sind PAARWEISE VERSCHIEDEN. Ohne sie ist die
    // Gleichheit der Bühnenhöhe trivial erfüllt, und der Fall prüfte nichts.
    const verschieden = new Set(formate.map((format) => format.toFixed(3)))
    expect(
      verschieden.size,
      `vier paarweise verschiedene Formate, gemessen: ${formate.map((f) => f.toFixed(3)).join(', ')}`,
    ).toBe(FORMATE)

    // AK10 — DIE AUSSAGE: Die Bühnenhöhe hängt am Sichtfenster, nicht am Bild. Ein
    // breitengeführtes Bild (`aspect-*`) fiele hier durch.
    const kleinste = Math.min(...hoehen)
    const groesste = Math.max(...hoehen)
    expect(
      groesste - kleinste,
      `Bühnenhöhe über vier Formate gleich, gemessen: ${hoehen.map((h) => h.toFixed(1)).join(', ')}`,
    ).toBeLessThanOrEqual(TOLERANZ)
  })
})

test.describe('Bilddetail: der reservierte Platz', () => {
  /** Wie viele Fotos nach einem mit bestehender Korrektur abgesucht werden. Bewusst GESUCHT statt
   *  über einen festen Index angesteuert: Welches Foto der Seeder korrigiert, ist seine Sache und
   *  keine Zusage an diesen Spec. Ein fester Index hinge still an einer Seeder-Konstante - und ein
   *  Fall, der auf einem im Bestand nachträglich entstandenen Datenwert beruht, wäre nach dem
   *  nächsten frischen Seed rot. Die Sonderzustände des Bestands (nicht klassifiziert, lokale
   *  Grundlage, ausgeschlossenes Dokument) liegen jenseits dieser Spanne. */
  const SUCHTIEFE = 5

  test('bewegt nichts unterhalb des Motivbereichs beim Auf- und Zuklappen', async ({ page }) => {
    const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

    let gefunden = false
    for (let index = 0; index < SUCHTIEFE; index += 1) {
      await oeffneFoto(page, projectId, index)
      const korrigiert = page.locator('[data-motif-corrected]')
      if ((await korrigiert.count()) > 0) {
        gefunden = true
        break
      }
    }
    expect(
      gefunden,
      `ein Foto mit bestehender Motivkorrektur unter den ersten ${SUCHTIEFE} - ohne es prüft ` +
        'Schritt (ii) den ungünstigsten Fall nicht',
    ).toBe(true)

    const symbole = page.locator('[data-motif-key]')
    await expect(symbole, 'die acht Motivsymbole').toHaveCount(8)

    // Das BEZUGSELEMENT steht UNTERHALB des wachsenden Bereichs: die Kopfzeile des
    // Einzelwerte-Rasters. Ein Bezugselement darüber bewegte sich auch dann nicht, wenn die
    // Reservierung fehlte.
    const bezug = page.getByRole('heading', { name: 'Qualität — Einzelwerte' })
    await expect(bezug, 'Kopfzeile des Qualitätsblocks als Bezugselement').toBeVisible()

    const detailId = await symbole.first().getAttribute('aria-controls')
    const zeile = page.locator(`[id="${detailId}"]`)
    await expect(zeile, 'die Detailzeile').toBeVisible()

    // AK6: Das längste Motiv wird ZUR LAUFZEIT aus den acht zugänglichen Namen ermittelt, NIE
    // hartkodiert - sonst wäre die Reservierung auf den heutigen Registry-Stand kalibriert und
    // bräche still, sobald ein Anzeigename wächst.
    const namen = await symbole.evaluateAll((nodes) =>
      nodes.map((node) => ({
        key: node.getAttribute('data-motif-key') ?? '',
        name: (node.getAttribute('aria-label') ?? '').split(':')[0] ?? '',
        korrigiert: node.getAttribute('data-motif-corrected') !== null,
      })),
    )
    const laengster = namen.reduce((a, b) => (b.name.length > a.name.length ? b : a))
    // Die Suche oben hat sichergestellt, dass es hier eines gibt.
    const mitKorrektur = namen.find((eintrag) => eintrag.korrigiert)!

    /* IN DOKUMENTKOORDINATEN gemessen, nicht in Fensterkoordinaten: `boundingBox()` ist
       fensterrelativ, und sowohl ein Klick als auch ein Tastaturfokus scrollen das Zielelement in
       den Sichtbereich. Auf der breiten Prüfbreite liegt der Motivbereich unterhalb der Bühne und
       damit unter dem Sichtrand - die Seite scrollt beim ersten Anheften um mehrere hundert
       Pixel, und eine fensterrelative Messung meldete genau diesen Betrag als Bewegung. Gemessen
       werden soll, ob sich das Element IM DOKUMENT verschiebt. */
    const oberkante = async (): Promise<number> =>
      bezug.evaluate((node) => node.getBoundingClientRect().y + window.scrollY)
    const inhalt = async (): Promise<string> => (await zeile.textContent()) ?? ''

    const start = await oberkante()
    let vorher = await inhalt()

    /**
     * Ein Zustandswechsel samt VORBEDINGUNG: Der Inhalt der Detailzeile hat nachweislich
     * gewechselt. Ohne diesen Nachweis bestünde der Fall auch dann, wenn gar nichts passierte.
     *
     * Der Mauszeiger wird vorher WEGGEFAHREN: Ein Klick lässt ihn auf dem Symbol stehen, und
     * „Angeheftet schlägt Zeigen" gilt nur für das Anheften - beim Lösen übernähme die Vorschau
     * unter dem Zeiger dieselbe Zeile, und der Inhalt wechselte trotz Zustandswechsel nicht.
     */
    async function schritt(name: string, handlung: () => Promise<void>): Promise<void> {
      await page.mouse.move(0, 0)
      await handlung()
      await expect
        .poll(inhalt, { message: `${name}: die Detailzeile hat gewechselt` })
        .not.toBe(vorher)
      vorher = await inhalt()
      expect(
        Math.abs((await oberkante()) - start),
        `${name}: nichts darunter bewegt sich`,
      ).toBeLessThanOrEqual(TOLERANZ)
    }

    /** Heftet ohne Messung an - eine Zwischenstellung, damit der nächste gemessene Schritt
     *  tatsächlich ein Wechsel ist. Nötig, wenn zwei der vier Schritte dasselbe Motiv träfen. */
    async function zwischenstellung(key: string): Promise<void> {
      await page.mouse.move(0, 0)
      await page.locator(`[data-motif-key="${key}"]`).click()
      await expect.poll(inhalt).not.toBe(vorher)
      vorher = await inhalt()
    }

    const neutral = namen.find(
      (eintrag) => eintrag.key !== laengster.key && eintrag.key !== mitKorrektur.key,
    )!

    // (i) das Motiv mit dem LÄNGSTEN Anzeigenamen angeheftet
    await schritt('längstes Motiv angeheftet', () =>
      page.locator(`[data-motif-key="${laengster.key}"]`).click(),
    )

    // (ii) ein Motiv MIT bestehender Korrektur angeheftet - dessen Zeile trägt die dritte
    // Schaltfläche und ist damit der ungünstigste Fall. NUR GEMESSEN, nie geklickt.
    //
    // Im Demo-Bestand KANN das dasselbe Motiv wie (i) sein; dann steht eine Zwischenstellung
    // dazwischen, damit (ii) ein echter Wechsel bleibt statt ein Weg-Klick.
    if (mitKorrektur.key === laengster.key) {
      await zwischenstellung(neutral.key)
    }
    await schritt('Motiv mit Korrektur angeheftet', () =>
      page.locator(`[data-motif-key="${mitKorrektur.key}"]`).click(),
    )
    await expect(
      page.getByRole('button', { name: `Zurücknehmen: ${mitKorrektur.name}` }),
      'die dritte Schaltfläche der Korrekturzeile',
    ).toBeVisible()
    expect(
      Math.abs((await oberkante()) - start),
      'drei Schaltflächen bewegen nichts',
    ).toBeLessThanOrEqual(TOLERANZ)

    // (iii) ein Motiv per TASTATURFOKUS vorangezeigt - erst das Anheften lösen, sonst schlägt
    // Angeheftet das Zeigen. Der Zeiger muss NACH dem Klick weg: Ein Klick lässt ihn auf dem
    // Symbol stehen, und die Vorschau unter dem Zeiger hielte dieselbe Zeile weiter offen.
    await page.locator(`[data-motif-key="${mitKorrektur.key}"]`).click()
    await page.mouse.move(0, 0)
    await expect.poll(inhalt, { message: 'Anheften gelöst' }).not.toBe(vorher)
    vorher = await inhalt()
    await schritt('Motiv per Tastaturfokus vorangezeigt', () =>
      page.locator(`[data-motif-key="${neutral.key}"]`).focus(),
    )

    // (iv) wieder zugeklappt
    await schritt('wieder zugeklappt', () =>
      page.locator(`[data-motif-key="${neutral.key}"]`).blur(),
    )
  })
})

test.describe('Bilddetail: der typografische Abstand', () => {
  test('setzt das Urteil deutlich größer als einen Rasterwert', async ({ page }) => {
    const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
    await oeffneFoto(page, projectId, 0)

    const urteil = page.locator('[data-album-suitability-level]')
    const rasterwert = page.locator('[data-criterion-value]').first()
    await expect(urteil, 'die Albumtauglichkeits-Zeile').toBeVisible()
    await expect(rasterwert, 'ein Wert im Einzelwerte-Raster').toBeVisible()

    // BEIDE IM SELBEN LAUF gemessen - zwei Läufe könnten verschiedene Zoomstufen erwischen, und
    // das Verhältnis wäre dann eine Aussage über zwei Zustände statt über einen.
    const schrift = async (element: Locator): Promise<number> =>
      Number.parseFloat(await element.evaluate((node) => getComputedStyle(node).fontSize))

    const urteilGroesse = await schrift(urteil)
    const rasterGroesse = await schrift(rasterwert)

    // Beide Bezugsgrößen vorher als > 0 zugesichert: Ein Verhältnis aus zwei Nullen oder aus NaN
    // bestünde sonst stillschweigend.
    expect(urteilGroesse, 'Schriftgröße des Urteils').toBeGreaterThan(0)
    expect(rasterGroesse, 'Schriftgröße eines Rasterwerts').toBeGreaterThan(0)

    expect(
      urteilGroesse / rasterGroesse,
      `Urteil ${urteilGroesse}px gegen Rasterwert ${rasterGroesse}px`,
    ).toBeGreaterThanOrEqual(SCHRIFT_FAKTOR)
  })

  test('stellt das Urteil im Dokument vor die Einzelwerte', async ({ page }) => {
    const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
    await oeffneFoto(page, projectId, 0)

    const urteil = page.getByTestId('verdict-section')
    const raster = page.getByTestId('criterion-score-grid')
    await expect(urteil).toBeVisible()
    await expect(raster).toBeVisible()

    expect((await urteil.boundingBox())!.y, 'Urteil steht über den Einzelwerten').toBeLessThan(
      (await raster.boundingBox())!.y,
    )
  })
})

test.describe('Bilddetail: der Tastaturhinweis', () => {
  /* Er nennt Tasten und nützt auf einem Telefon nichts, nähme der Fotofläche dort aber mehrere
     Zeilen Höhe. Sichtbar ist er deshalb erst ab der `sm:`-Schwelle.

     GEMESSEN STATT GEGLAUBT: Beide Viewport-Projekte laufen durch DIESELBE Zusicherung und
     prüfen je einen der beiden Zweige - 360 px erwartet unsichtbar, 1280 px sichtbar. Eine
     Zusicherung, die nur einen Zweig kennt, bestünde auch bei einer Utility, die immer greift
     oder nie. Im Dokument steht das Element in BEIDEN Breiten (AK9a): ausgeblendet wird ein
     Hinweis, nicht ein Abschnitt. */
  const SM_SCHWELLE = 640

  test('zeigt ihn erst ab der breiteren Prüfbreite', async ({ page }) => {
    const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
    await oeffneFoto(page, projectId, 0)

    const hinweis = page.getByText(/^Shortcuts:/)
    const breite = page.viewportSize()!.width

    // Im DOM steht er immer - die Abschnittsfolge ist auf beiden Breiten dieselbe.
    await expect(hinweis, 'der Hinweis steht im Dokument').toHaveCount(1)

    if (breite >= SM_SCHWELLE) {
      await expect(hinweis, `bei ${breite} px sichtbar`).toBeVisible()
    } else {
      await expect(hinweis, `bei ${breite} px ausgeblendet`).toBeHidden()
    }
  })
})

test.describe('Bilddetail: kein horizontales Scrollen', () => {
  /* AK9b. Der bestehende `no-horizontal-scroll.spec.ts` prüft die Route bereits; dieser Fall
     steht daneben, weil er die Bühne im GEÖFFNETEN Motivzustand prüft - da ist die Detailzeile am
     breitesten. */
  test('erzeugt auch mit aufgeklapptem Motiv keinen Querlauf', async ({ page }) => {
    const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
    await oeffneFoto(page, projectId, 0)

    const symbole = page.locator('[data-motif-key]')
    await expect(symbole).toHaveCount(8)
    const namen = await symbole.evaluateAll((nodes) =>
      nodes.map((node) => ({
        key: node.getAttribute('data-motif-key') ?? '',
        name: (node.getAttribute('aria-label') ?? '').split(':')[0] ?? '',
      })),
    )
    const laengster = namen.reduce((a, b) => (b.name.length > a.name.length ? b : a))
    await page.locator(`[data-motif-key="${laengster.key}"]`).click()

    const quer = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }))
    expect(quer.scrollWidth, 'kein horizontales Scrollen').toBeLessThanOrEqual(
      quer.clientWidth + TOLERANZ,
    )
  })
})
