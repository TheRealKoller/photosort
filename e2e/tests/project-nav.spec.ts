/**
 * Projekt-Navigationsgruppe in der Kopfzeile: Breakpoint, Kopfzeilenhoehe und Ueberlagerung.
 *
 * AUSSCHLIESSLICH DAS, WAS JSDOM PRINZIPIELL NICHT KANN (specs/features/0298-projektnavigation-in-
 * der-kopfzeile.md und specs/features/0347-navigation-nebenbereich.md, Teststrategie;
 * specs/architecture/0002-testkonzept.md, Sektion "Eine Zieltabelle, zwei Darstellungen"): In
 * jsdom greifen Tailwind-Klassen nicht, `hidden`/`lg:hidden` blenden dort nichts aus, das Panel
 * hat dort IMMER fuenf Zeilen. Ein `toBeVisible()` waere dort eine Zusicherung, die immer dasselbe
 * sagt - unabhaengig davon, ob die Utility ueberhaupt noch am Element haengt. Die
 * Breakpoint-Zusage lebt deshalb nur hier, ebenso die beiden gemessenen Abnahmemasse aus AK4/AK5
 * (Ausloeserbreite, Gruppenabstand) und die gerenderte Trennlinie. Die Verhaltenspruefungen (drei
 * Ziele, Sprungziele, aria-current, Escape, Landmark-Kardinalitaet) stehen in ProjectNav.test.tsx
 * und werden hier NICHT wiederholt.
 *
 * EIGENE VIEWPORT-BREITEN, an ein einziges Playwright-Projekt gebunden (wie `grid-columns`): Die
 * beiden Projekt-Viewports (360, 1280) liegen beide fern der Grenze und zeigten den Wechsel gar
 * nicht; ohne die Bindung liefe der Spec ausserdem zweimal mit identischem Ergebnis.
 *
 * ROT-NACHWEIS ERBRACHT (Spec 0347, erster ausfuehrbarer Lauf dieser Datei): Der aus Spec 0298
 * offen gebliebene Nachweis ist mit diesem Branch nachgeholt und um die drei neuen Zusicherungen
 * ergaenzt. Belegt wurde je einzeln, dass eine gezielte Verschlechterung diesen Spec ROT meldet:
 *
 *  - Breakpoint `lg:` -> `md:` am Leisten-Container  -> Grenztest rot,
 *  - Trenner-Utilities am Hauptzielblock entfernt    -> Absetzungspruefung rot,
 *  - `size="icon"` -> `size="default"` mit Beschriftung am Ausloeser -> AK4-Breitenpruefung rot,
 *  - `lg:hidden` am Hauptzielblock entfernt          -> Panelinhalts-Pruefung rot.
 *
 * Die Belege stehen in der PR-Beschreibung.
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
 * faende dort NULL Ziele und `toHaveCount(3)` liefe in die Zeitgrenze. Die DOM-Kardinalitaet wird
 * deshalb ueber `locator('a')`/`locator('button[aria-label=...]')` gefuehrt, die Sichtbarkeit
 * anschliessend GEMESSEN statt lokalisiert.
 */
function navTargetsInDom(page: import('@playwright/test').Page) {
  return projectNav(page).locator('a')
}

function menuTriggerInDom(page: import('@playwright/test').Page) {
  return page.locator('button[aria-label="Projektbereiche"]')
}

/*
 * `getByRole('banner')` UND NICHT `locator('header')`: Es gibt sechs `<header>` im Produkt. Fuenf
 * davon sind Seiten-Header INNERHALB von `<main>` (u.a. ProjectListPage - genau die Seite, die der
 * AK7-Test als Vergleich ohne Projektbezug ansteuert), einer ist die App-Shell-Kopfzeile
 * ausserhalb. Ein `locator('header')` traf auf `/` beide und brach mit einer Strict-Mode-Meldung ab.
 *
 * Die Rolle trennt sie sauber: `<header>` traegt `banner` nur, solange es nicht in
 * `main`/`article`/`section`/`aside`/`nav` verschachtelt ist - die fuenf Seiten-Header sind damit
 * rollenlos, nur die App-Shell-Kopfzeile ist ein `banner`. Zugleich die Rollen- statt
 * Klassennamen-Lokalisierung der Selektor-Konvention, und dasselbe Vorgehen wie in
 * `sticky-header.spec.ts` und `lib/auth.ts`.
 */
function appHeader(page: import('@playwright/test').Page) {
  return page.getByRole('banner')
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

/** Die drei Hauptziele der Leiste, in Anzeigereihenfolge. */
const PRIMARY_LABELS = ['Projekt', 'Fotos', 'Vergleich']
/** Die zwei Nebenziele des Panels, in Anzeigereihenfolge. */
const SECONDARY_LABELS = ['Einstellungen', 'Statistik']

test('blendet an der exakten Grenze 1024 px die Leiste aus, ohne den Ausloeser anzutasten', async ({
  page,
}) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

  const measured: { width: number; visibleTargets: number; triggerVisible: boolean }[] = []

  for (const width of [BREAKPOINT, BREAKPOINT - 1]) {
    await page.setViewportSize({ width, height: VIEWPORT_HEIGHT })
    await page.goto(`/projects/${projectId}/photos`)

    await expect(projectNav(page), `Navigationsgruppe bei ${width} px`).toBeAttached()

    // Vorbedingung UND zugleich die DOM-Haelfte von AK5: im DOM liegen bei JEDER Breite genau drei
    // Leistenziele und GENAU EIN Ausloeser. Ohne die erste Zusicherung bestuende der
    // 1023-px-Durchlauf ("null sichtbare Ziele") auch dann, wenn die Leiste gar nicht mehr
    // gerendert wuerde; ohne die zweite bliebe die abgewaehlte Zwei-Instanzen-Variante unbemerkt.
    const targets = navTargetsInDom(page)
    await expect(targets, `Ziele im DOM bei ${width} px`).toHaveCount(3)
    const trigger = menuTriggerInDom(page)
    await expect(trigger, `Menue-Ausloeser im DOM bei ${width} px`).toHaveCount(1)

    // Gemessen wird ausschliesslich, wie viele davon TATSAECHLICH dargestellt werden.
    measured.push({
      width,
      visibleTargets: await visibleCount(targets),
      triggerVisible: (await visibleCount(trigger)) === 1,
    })
  }

  // AK4: ab 1024 px stehen die drei Hauptziele UND der Ausloeser gleichzeitig da.
  expect(measured[0], `Darstellung bei ${BREAKPOINT} px`).toEqual({
    width: BREAKPOINT,
    visibleTargets: 3,
    triggerVisible: true,
  })
  // AK5: einen Pixel darunter bleibt ausschliesslich der Ausloeser - die Leiste verschwindet, er
  // nicht.
  expect(measured[1], `Darstellung bei ${BREAKPOINT - 1} px`).toEqual({
    width: BREAKPOINT - 1,
    visibleTargets: 0,
    triggerVisible: true,
  })
  /*
   * DER WIRKSAMKEITSANKER HAENGT AUSSCHLIESSLICH AN DER ZAHL DER SICHTBAREN ZIELE (3 != 0) -
   * bitte nicht auf ein Tupel zurueckbauen. Bis Spec 0298 trug die Umkehrung BEIDER Messgroessen
   * den Beleg; seit Spec 0347 ist die Ausloeser-Sichtbarkeit auf beiden Seiten konstant `true`.
   * Eine Zusicherung auf das ganze Tupel saehe durch diese konstante Haelfte immer "unterschiedlich
   * genug" aus und bestuende auch bei voellig fehlendem Breakpoint.
   */
  expect(measured[0]!.visibleTargets, 'Messungen an der Grenze unterscheiden sich').not.toBe(
    measured[1]!.visibleTargets
  )
})

test('zeigt im Panel ueber die Grenze hinweg unterschiedliche Inhalte aus demselben DOM (AK2/AK5)', async ({
  page,
}) => {
  /*
   * `getByRole` sieht den ACCESSIBILITY-TREE: was `display: none` traegt, faellt heraus. Genau
   * darauf beruht diese Zusage - im DOM liegen bei beiden Breiten dieselben fuenf Zeilen, im
   * Accessibility-Tree ab 1024 px nur die zwei Nebenziele. Die DOM-Zaehlung daneben schliesst den
   * trivialen Gruen-Fall aus: ohne sie bestuende der 1024-px-Durchlauf auch dann, wenn die drei
   * Hauptzeilen gar nicht mehr gerendert wuerden - und unterhalb `lg:` waeren sie dann weg.
   */
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

  for (const [width, expectedLabels] of [
    [BREAKPOINT, SECONDARY_LABELS],
    [BREAKPOINT - 1, [...PRIMARY_LABELS, ...SECONDARY_LABELS]],
  ] as const) {
    await page.setViewportSize({ width, height: VIEWPORT_HEIGHT })
    await page.goto(`/projects/${projectId}/photos`)

    const trigger = menuTrigger(page)
    await expect(trigger, `Ausloeser bei ${width} px`).toBeVisible()
    await trigger.click()

    const panel = page.getByRole('dialog')
    await expect(panel, `Panel bei ${width} px`).toBeVisible()

    await expect(panel.locator('a'), `Panelzeilen im DOM bei ${width} px`).toHaveCount(5)
    await expect(
      panel.getByRole('link'),
      `dargestellte Panelzeilen bei ${width} px`
    ).toHaveText(expectedLabels)

    await page.keyboard.press('Escape')
    await expect(panel, `Panel nach Escape bei ${width} px`).toBeHidden()
  }
})

test(`haelt den Ausloeser bei ${BREAKPOINT} px erkennbar kompakter als ein Hauptziel (AK4)`, async ({
  page,
}) => {
  /*
   * AK4 woertlich: hoechstens 75 % der Breite des SCHMALSTEN dargestellten Hauptziels. Bezugsgroesse
   * ist das im selben Lauf mitgemessene Hauptziel, nie eine hartkodierte Pixelzahl - die waere auf
   * Schriftgrad und heutigen Beschriftungssatz kalibriert und ueberlebte keine legitime Aenderung.
   */
  await page.setViewportSize({ width: BREAKPOINT, height: VIEWPORT_HEIGHT })
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${projectId}/photos`)

  const trigger = menuTrigger(page)
  await expect(trigger, 'Ausloeser').toBeVisible()

  const targetWidths: number[] = []
  for (const label of PRIMARY_LABELS) {
    const target = projectNav(page).getByRole('link', { name: label })
    await expect(target, `Hauptziel "${label}"`).toBeVisible()
    const box = await target.boundingBox()
    expect(box, `Rechteck von "${label}"`).not.toBeNull()
    expect(box!.width, `Breite von "${label}"`).toBeGreaterThan(0)
    targetWidths.push(box!.width)
  }

  const triggerBox = await trigger.boundingBox()
  expect(triggerBox, 'Rechteck des Ausloesers').not.toBeNull()
  expect(triggerBox!.width, 'Breite des Ausloesers').toBeGreaterThan(0)

  const narrowest = Math.min(...targetWidths)
  expect(
    triggerBox!.width,
    `Ausloeser ${triggerBox!.width.toFixed(1)} px gegen schmalstes Hauptziel ` +
      `${narrowest.toFixed(1)} px (Breiten: ${targetWidths.map((w) => w.toFixed(1)).join(', ')})`
  ).toBeLessThanOrEqual(narrowest * 0.75)
})

test(`setzt die Nebengruppe im Panel bei ${MOBILE_WIDTH} px sichtbar ab (AK5)`, async ({ page }) => {
  /*
   * ZWEI EIGENSCHAFTEN, EINE ZUSAGE: die Absetzung besteht aus dem groesseren Abstand UND der
   * gerenderten Linie. Einzeln waere jede angreifbar - ein Abstand ohne Linie ist bei fuenf
   * gleichfoermigen Zeilen kaum als Gruppengrenze lesbar, und eine Linie mit Alphakanal 0 oder
   * `border-style: none` ist gar keine.
   *
   * Der Abstandswert wird gegen den groessten Abstand INNERHALB der Hauptgruppe gemessen, nicht
   * gegen eine Pixelzahl - dieselbe Regel wie bei AK4.
   */
  await page.setViewportSize({ width: MOBILE_WIDTH, height: VIEWPORT_HEIGHT })
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  await page.goto(`/projects/${projectId}/photos`)

  await menuTrigger(page).click()
  const panel = page.getByRole('dialog')
  await expect(panel).toBeVisible()

  const rowBoxes: { label: string; top: number; bottom: number }[] = []
  for (const label of [...PRIMARY_LABELS, ...SECONDARY_LABELS]) {
    const row = panel.getByRole('link', { name: label })
    await expect(row, `Panelzeile "${label}"`).toBeVisible()
    const box = await row.boundingBox()
    expect(box, `Rechteck der Zeile "${label}"`).not.toBeNull()
    expect(box!.height, `Hoehe der Zeile "${label}"`).toBeGreaterThan(0)
    rowBoxes.push({ label, top: box!.y, bottom: box!.y + box!.height })
  }

  const innerGaps = [
    rowBoxes[1]!.top - rowBoxes[0]!.bottom,
    rowBoxes[2]!.top - rowBoxes[1]!.bottom,
  ]
  const largestInnerGap = Math.max(...innerGaps)
  // Ohne diese Vorbedingung waere "mindestens doppelt so gross" bei einem Innenabstand von 0
  // trivial wahr - und genau dann saehe man ueberhaupt keine Gruppierung.
  expect(largestInnerGap, `groesster Abstand innerhalb der Hauptgruppe (${innerGaps.join(', ')})`)
    .toBeGreaterThan(0)

  const groupGap = rowBoxes[3]!.top - rowBoxes[2]!.bottom
  expect(
    groupGap,
    `Abstand "Vergleich" -> "Einstellungen" (${groupGap.toFixed(1)} px) gegen den groessten ` +
      `Abstand innerhalb der Hauptgruppe (${largestInnerGap.toFixed(1)} px)`
  ).toBeGreaterThanOrEqual(largestInnerGap * 2)

  /*
   * DAS TRENNENDE ELEMENT WIRD AUS DER STRUKTUR HERGELEITET, nicht ueber einen Klassennamen
   * lokalisiert (Selektor-Konvention): gesucht ist der naechstgelegene Vorfahre der drei
   * Hauptzeilen, der keine der beiden Nebenzeilen enthaelt und nicht das Panel selbst ist. Genau
   * dieses Element traegt die Trennlinie.
   */
  const separator = await panel.evaluate((element) => {
    const rows = Array.from(element.querySelectorAll('a'))
    const primary = rows.slice(0, 3)
    const secondary = rows.slice(3)
    let candidate: Element | null = primary[0]?.parentElement ?? null
    while (candidate !== null && candidate !== element) {
      if (
        primary.every((row) => candidate!.contains(row)) &&
        !secondary.some((row) => candidate!.contains(row))
      ) {
        const style = window.getComputedStyle(candidate)
        return {
          found: true,
          width: Number.parseFloat(style.borderBottomWidth),
          style: style.borderBottomStyle,
          color: style.borderBottomColor,
        }
      }
      candidate = candidate.parentElement
    }
    return { found: false, width: 0, style: 'none', color: 'transparent' }
  })

  expect(separator.found, 'eigener Block um die drei Hauptzeilen gefunden').toBe(true)
  expect(separator.width, `border-bottom-width des Trenners (${separator.color})`).toBeGreaterThan(0)
  expect(separator.style, 'border-bottom-style des Trenners').not.toBe('none')
  // `transparent` und jedes `rgba(..., 0)` sind gerenderte Linien ohne jede Sichtbarkeit.
  expect(separator.color, 'Farbe des Trenners').not.toBe('transparent')
  expect(separator.color, 'Alphakanal der Trennerfarbe').not.toMatch(/,\s*0\s*\)$/)
})

/*
 * ZWEI BREITEN, ZWEI VERSCHIEDENE EIGENSCHAFTEN - bewusst als zwei eigenstaendige Tests und nicht
 * mehr als eine Tabelle: Sie teilen sich zwar den Aufbau, messen aber Unterschiedliches, und eine
 * gemeinsame Tabelle taeuschte eine Gleichartigkeit vor, die es nicht gibt.
 *
 *  - 360 px: HOEHENGLEICHHEIT. Dort ist AK7 woertlich eine Aussage ueber die Kopfzeilenhoehe, und
 *    es kommt nur der `size="icon"`-Ausloeser hinzu, der wie jede andere Schaltflaeche der
 *    Kopfzeile `h-8` = 32 px hoch ist. Gleiche Hoehe ist dort also die richtige Frage.
 *  - 1024 px: EINZEILIGKEIT. Dort lautet die verbindliche Regel des Architektur-Abschnitts "die
 *    Kopfzeile darf bei keiner Breite in eine zweite Zeile umbrechen" - und dafuer waere
 *    Hoehengleichheit das falsche Instrument, siehe die Begruendung am Test selbst.
 */

/** Ein Rechteck, wie es `getBoundingClientRect()` liefert - nur die senkrechte Achse. */
interface VerticalExtent {
  top: number
  bottom: number
}

/**
 * Liegen alle Elemente in EINEM gemeinsamen waagerechten Band? Genau dann, wenn der tiefste
 * Oberrand noch ueber dem hoechsten Unterrand liegt - dann ueberlappen sich alle senkrecht, es
 * gibt also keine zweite Zeile. Bricht die Kopfzeile um, rutscht mindestens ein Kind vollstaendig
 * unter ein anderes und die Bedingung faellt.
 *
 * Bewusst eine reine Funktion und nicht inline in der Zusicherung vergraben: so ist sie unten
 * gegen synthetische Rechtecke pruefbar. Der eine ernste Fehlermodus einer Layout-Messung ist,
 * dass sie nichts findet und deswegen besteht.
 */
function sharesHorizontalBand(extents: VerticalExtent[]): boolean {
  if (extents.length < 2) {
    return true
  }
  const lowestTop = Math.max(...extents.map((extent) => extent.top))
  const highestBottom = Math.min(...extents.map((extent) => extent.bottom))
  return lowestTop < highestBottom
}

test('erkennt eine umgebrochene Zeile als solche (Selbsttest des Messverfahrens)', () => {
  // Eine Kopfzeile, deren zwei Gruppen nebeneinander stehen - unterschiedlich hoch, wie im
  // Produkt (34,8 px hohe Navigationsziele neben 32 px hohen Schaltflaechen).
  expect(
    sharesHorizontalBand([
      { top: 12, bottom: 46.8 },
      { top: 13.4, bottom: 45.4 },
    ]),
    'zwei nebeneinander stehende Gruppen'
  ).toBe(true)
  // Dieselben zwei Gruppen nach einem Umbruch: die zweite steht vollstaendig unter der ersten.
  expect(
    sharesHorizontalBand([
      { top: 12, bottom: 46.8 },
      { top: 58.8, bottom: 90.8 },
    ]),
    'zwei untereinander stehende Gruppen'
  ).toBe(false)
  // Randfall Beruehrung: Unterkante der einen genau auf der Oberkante der anderen ist bereits
  // ein Umbruch, keine gemeinsame Zeile.
  expect(
    sharesHorizontalBand([
      { top: 12, bottom: 46.8 },
      { top: 46.8, bottom: 78.8 },
    ]),
    'buendig aneinander grenzende Gruppen'
  ).toBe(false)
})

test(`haelt die Kopfzeile bei ${MOBILE_WIDTH} px genauso hoch wie ohne Projektbezug (AK7)`, async ({
  page,
}) => {
  /*
   * AK7 woertlich: "Bei 360 px ist die Kopfzeile auf einer Projektseite GENAUSO HOCH wie auf einer
   * Seite ohne Projektbezug (Toleranz 1 px)" - die Gruppe erzeugt also keine zusaetzliche
   * Kopfzeilenzeile und verschiebt den Seiteninhalt nicht nach unten.
   *
   * Gegen dieselbe Kopfzeile ohne Projektbezug gemessen statt gegen eine feste Zahl: die waere auf
   * den heutigen Zustand kalibriert und ueberlebte keine legitime Aenderung der Kopfzeile.
   */
  await page.setViewportSize({ width: MOBILE_WIDTH, height: VIEWPORT_HEIGHT })
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

  const header = appHeader(page)

  await page.goto('/')
  await expect(projectNav(page), 'Gruppe auf der Projektliste').toHaveCount(0)
  await expect(header, 'Kopfzeilen-Landmark auf der Projektliste').toHaveCount(1)
  const withoutProject = await header.boundingBox()
  expect(withoutProject, 'Kopfzeile ohne Projektbezug').not.toBeNull()

  await page.goto(`/projects/${projectId}/photos`)
  await expect(projectNav(page), 'Gruppe auf der Projektseite').toBeAttached()
  await expect(header, 'Kopfzeilen-Landmark auf der Projektseite').toHaveCount(1)

  // Vorbedingung: bei 360 px ist ausschliesslich der Ausloeser dargestellt (Spec 0347 AK5) -
  // genau die Darstellung, ueber die AK7 eine Aussage macht.
  expect(await visibleCount(navTargetsInDom(page)), 'sichtbare Ziele bei 360 px').toBe(0)
  expect(await visibleCount(menuTriggerInDom(page)), 'sichtbarer Ausloeser bei 360 px').toBe(1)

  const withProject = await header.boundingBox()
  expect(withProject, 'Kopfzeile mit Projektbezug').not.toBeNull()

  // Groesse > 0 zuerst: zwei auf 0 kollabierte Kopfzeilen waeren sonst trivial "gleich hoch".
  expect(withoutProject!.height, 'Hoehe der Kopfzeile ohne Projektbezug').toBeGreaterThan(0)
  expect(
    Math.abs(withProject!.height - withoutProject!.height),
    `Hoehenunterschied der Kopfzeile bei ${MOBILE_WIDTH} px`
  ).toBeLessThanOrEqual(TOLERANCE)
})

test(`haelt die Kopfzeile bei ${BREAKPOINT} px einzeilig (kein Umbruch)`, async ({ page }) => {
  /*
   * Die verbindliche Regel des Architektur-Abschnitts: "die Kopfzeile darf bei keiner Breite in
   * eine zweite Zeile umbrechen". 1024 px ist die SCHMALSTE Breite, bei der Wortmarke, DREI
   * Beschriftungen samt Ausloeser, "Angemeldet als …" und "Abmelden" gleichzeitig in eine Zeile
   * muessen - also die einzige, an der die Regel tatsaechlich gefaehrdet ist. Mit einer
   * Beschriftung weniger als bis Spec 0298 ist hier Reserve entstanden; sie ist ausdruecklich
   * Sicherheitsreserve gegen den Umbruch und kein Anlass, den Breakpoint zu verschieben. Der `lg:`-Breakpoint beruht in der
   * Spec auf einer Schaetzung ("rund 800 px"), nicht auf einer Messung.
   *
   * WARUM HIER NICHT DIE HOEHE VERGLICHEN WIRD - bitte nicht auf Hoehengleichheit zurueckbauen:
   * Die Navigationsziele sind das Board-Navigationselement und tragen `border px-3 py-2
   * text-xs` -> 1 + 8 + (12px * 1.4 Zeilenhoehe) + 8 + 1 = 34,8 px. Die uebrigen Bedienelemente
   * der Kopfzeile sind Schaltflaechen mit fester Hoehe `h-8` = 32 px. Die Kopfzeile waechst durch
   * die Gruppe also PLANMAESSIG um knapp 3 px - im CI-Lauf zu Commit cc7d6e8 gemessene 2,796875 px.
   * Das ist kein Umbruch, sondern die zeichengleiche Uebernahme des Rezepts aus Stepper.tsx, die
   * AK8c ausdruecklich verlangt. Eine Hoehengleichheits-Zusicherung scheitert daran dauerhaft,
   * ohne je einen Umbruch zu belegen - ein echter Umbruch ergaebe rund 46 px (eine weitere
   * 34,8-px-Zeile plus `gap-3`).
   *
   * Geprueft wird deshalb direkt die Eigenschaft, die die Regel meint: liegen alle direkten Kinder
   * der Kopfzeile in einem gemeinsamen waagerechten Band? Das ist gegen ein paar Pixel
   * Hoehenunterschied unempfindlich und faellt bei jedem echten Umbruch.
   *
   * `flex-wrap` sitzt auf dem `<header>` selbst; die beiden Gruppen darin tragen es NICHT und
   * koennen deshalb gar nicht umbrechen - ihr Fehlerbild waere waagerechter Ueberlauf, und den
   * deckt `no-horizontal-scroll.spec.ts` ab. Die direkten Kinder sind damit die richtige Ebene.
   */
  await page.setViewportSize({ width: BREAKPOINT, height: VIEWPORT_HEIGHT })
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)

  await page.goto(`/projects/${projectId}/photos`)
  const header = appHeader(page)
  await expect(header, 'Kopfzeilen-Landmark auf der Projektseite').toHaveCount(1)

  // Vorbedingung: die drei Beschriftungen UND der Ausloeser sind bei dieser Breite auch
  // tatsaechlich dargestellt - sonst koennte gar nichts umbrechen und die Messung waere wertlos.
  expect(await visibleCount(navTargetsInDom(page)), `sichtbare Ziele bei ${BREAKPOINT} px`).toBe(3)
  expect(
    await visibleCount(menuTriggerInDom(page)),
    `sichtbarer Ausloeser bei ${BREAKPOINT} px`
  ).toBe(1)

  const extents = await header.evaluate((element) =>
    Array.from(element.children).map((child) => {
      const rect = child.getBoundingClientRect()
      return { top: rect.top, bottom: rect.bottom }
    })
  )

  // Ohne diese Zusicherung bestuende der Test auch dann, wenn die Kopfzeile nur noch ein einziges
  // Kind haette - `sharesHorizontalBand` ist fuer weniger als zwei Elemente trivial wahr.
  expect(extents.length, 'direkte Kinder der Kopfzeile').toBeGreaterThanOrEqual(2)
  expect(
    sharesHorizontalBand(extents),
    `Kinder der Kopfzeile bei ${BREAKPOINT} px in einer Zeile (gemessen: ${JSON.stringify(extents)})`
  ).toBe(true)
})

test('legt das geoeffnete Panel vollstaendig sichtbar ueber den Seiteninhalt', async ({ page }) => {
  // AK12: zwei Zusagen in einem Test, weil einzeln jede fuer sich wertlos waere - ein Panel weit
  // ausserhalb des Sichtbereichs ueberdeckte nichts, und ein Panel, das nichts ueberdeckt, belegt
  // die Stapelreihenfolge nicht.
  //
  // Seit Spec 0347 traegt das Panel bei dieser Breite FUENF Zeilen plus Trenner statt vier - die
  // Zusage "vollstaendig im Sichtbereich" wird dadurch erst richtig scharf.
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
