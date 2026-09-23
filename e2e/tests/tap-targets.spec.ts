/**
 * Trefferflaechen der Bedienelemente des heissen Pfads bei 360 px.
 *
 * TREFFERTEST STATT KASTENMESSUNG: Bedienelemente sind seit dem Dark Utility Register sichtbar
 * 32 px hoch und werden ueber ein transparentes `::after`-Pseudo-Element (`tap-target` /
 * `tap-target-square` in `index.css`) auf >= 44 x 44 px aufgespannt. Ein Pseudo-Element taucht in
 * KEINER `boundingBox()` auf - eine Messung des Elementkastens meldete dauerhaft 32 px und waere
 * entweder falsch-rot oder auf 32 px "kalibriert" und damit wertlos. Geprueft wird deshalb per
 * `document.elementFromPoint()` an den vier Ecken des beabsichtigten 44 x 44-Bereichs.
 *
 * Dasselbe Verfahren deckt zwei weitere, zuvor als unpruefbar gefuehrte Fehlerklassen mit ab: das
 * Klippen durch einen Vorfahren mit `overflow: hidden` (dann liefert der Treffertest den
 * Vorfahren) und ueberlappende aufgespannte Trefferflaechen benachbarter Bedienelemente (dann
 * liefert er das NACHBARelement).
 *
 * Rot-Nachweis bei Einfuehrung (2026-09-05): siehe PR-Beschreibung - mit unterdruecktem
 * `::after`-Pseudo-Element (`button::after { content: none }`) meldete der Spec fuer
 * "Vorheriges Foto" an allen vier Ecken "Fremdelement <div>" statt "Bedienelement". Genau die
 * Elemente also, die ihre 44 px NUR aus der Aufspannung beziehen - die 44 px hohen
 * Bewertungs-Schaltflaechen blieben davon unberuehrt, was den Treffertest zusaetzlich bestaetigt.
 */

import type { Locator } from '@playwright/test'

import { DEMO_PROJECTS, demoProjectId, openDuplicateGroup, photoTiles } from '../lib/demo.ts'
import { expect, test } from '../lib/fixtures.ts'

/** Zugesicherte Mindest-Trefferflaeche in px (Design-System). */
const TAP_TARGET_SIZE = 44

/**
 * Die Bedienelemente des heissen Pfads, die dieser Spec prueft. Die Zahl ist am Ende Gegenstand
 * einer eigenen Zusicherung: ohne sie bestuende der Spec auch dann, wenn er - etwa nach einer
 * Umbenennung eines aria-Labels - gar kein Element mehr faende.
 */
const EXPECTED_CONTROL_COUNT = 21

async function assertTappable(
  control: Locator,
  label: string,
  options: { ariaDisabled?: boolean } = {},
): Promise<void> {
  await expect(control, `Bedienelement "${label}"`).toBeVisible()
  if (options.ariaDisabled === true) {
    // Der gesperrte Schritt der Schrittleiste (specs/features/0387-schrittleiste-fortschritt.md)
    // traegt `aria-disabled`, NIE `disabled` - Playwright zaehlt `aria-disabled` zu "disabled",
    // `toBeEnabled()` waere hier also falsch-rot. Dass Zeigerereignisse ihn trotzdem erreichen,
    // belegt der Treffertest unten selbst; mit `disabled` waere er es nicht, und der Sperrgrund
    // am Telefon unerreichbar. Beide Attribute werden geprueft, damit die Ausnahme nicht
    // versehentlich ein wirklich deaktiviertes Element durchwinkt.
    await expect(control, `"${label}" traegt aria-disabled`).toHaveAttribute(
      'aria-disabled',
      'true',
    )
    await expect(control, `"${label}" traegt kein disabled`).not.toHaveAttribute('disabled', /.*/)
  } else {
    // `disabled:pointer-events-none` im Button-Stil wuerde den Treffertest zwangslaeufig auf einen
    // Vorfahren umlenken - ein deaktiviertes Element waere also falsch-rot statt aussagekraeftig.
    await expect(control, `Bedienelement "${label}" ist bedienbar`).toBeEnabled()
  }

  // Mittig in den Sichtbereich rollen statt nur "gerade so hinein": die sticky Kopfzeile liegt
  // sonst ueber einem knapp oben stehenden Element, und der Treffertest meldete SIE.
  await control.evaluate((element) => element.scrollIntoView({ block: 'center' }))

  const hits = await control.evaluate((element, size) => {
    const rect = element.getBoundingClientRect()
    const centerX = rect.x + rect.width / 2
    const centerY = rect.y + rect.height / 2
    // Knapp innerhalb der Ecken des beabsichtigten Bereichs - exakt auf der Kante entschiede die
    // Rundung des Browsers, nicht die geprueft Eigenschaft.
    const half = size / 2 - 0.5
    const corners: [number, number][] = [
      [centerX - half, centerY - half],
      [centerX + half, centerY - half],
      [centerX - half, centerY + half],
      [centerX + half, centerY + half],
    ]
    return corners.map(([x, y]) => {
      const hit = document.elementFromPoint(x, y)
      if (hit === null) {
        return 'nichts getroffen (Punkt ausserhalb des Sichtbereichs)'
      }
      if (hit === element || element.contains(hit)) {
        return 'Bedienelement'
      }
      return `Fremdelement <${hit.tagName.toLowerCase()}>`
    })
  }, TAP_TARGET_SIZE)

  expect(hits, `Treffer an den vier Ecken der ${TAP_TARGET_SIZE}px-Flaeche von "${label}"`).toEqual(
    ['Bedienelement', 'Bedienelement', 'Bedienelement', 'Bedienelement'],
  )
}

test('Bedienelemente des heissen Pfads sind auf 44 x 44 px treffbar', async ({ page }) => {
  const projectId = await demoProjectId(page, DEMO_PROJECTS.rated)
  const checked: string[] = []

  // --- Detailansicht: Bewertung und Weiter/Zurueck -----------------------------------------
  await page.goto(`/projects/${projectId}/photos`)
  const tiles = photoTiles(page)
  await expect(tiles.first()).toBeVisible()
  // Bewusst die ZWEITE Kachel: auf dem ersten Foto der Sequenz ist "Vorheriges Foto" deaktiviert
  // und damit per `pointer-events-none` gar nicht treffbar - der Spec pruefte dann einen Zustand,
  // den es auf dem heissen Pfad so nicht gibt.
  await tiles.nth(1).getByRole('link').first().click()
  await expect(page.getByRole('group', { name: 'Bewertung' })).toBeVisible()

  const ratingButtons = page.getByRole('group', { name: 'Bewertung' }).getByRole('button')
  // Exakte Kardinalitaet: die drei Bewertungsstatus des Produkts.
  await expect(ratingButtons, 'Bewertungs-Schaltflaechen').toHaveCount(3)
  for (const label of ['Favorit', 'Album-würdig', 'Verwerfen']) {
    await assertTappable(page.getByRole('button', { name: label, exact: true }), label)
    checked.push(label)
  }

  for (const label of ['Vorheriges Foto', 'Nächstes Foto']) {
    await assertTappable(page.getByRole('button', { name: label }), label)
    checked.push(label)
  }

  // --- Motivkorrektur in der Einzelbildansicht ----------------------------------------------
  // Die frueher hier gepruefte Trefferflaeche "Alle Kategorien" ist mit den Kategorien entfallen
  // (Spec 0427). An ihre Stelle treten die Korrekturschalter der Motivstaerke - und sie stehen
  // NICHT im Popover der Kachel (dort ist der Baustein schreibgeschuetzt), sondern in der
  // Einzelbildansicht. Genau diese Verschiebung macht den eigenen Testschritt noetig.
  //
  // SEIT SPEC 0490 ERST NACH EINEM KLICK: Die Schalter stehen in der Detailzeile unter der
  // Symbolreihe, nicht mehr an acht Listenzeilen. Gesucht wird deshalb im Abschnitt
  // (`data-testid="motifs-section"`), nicht in der Liste - die Zeile steht AUSSERHALB von <ul>.
  //
  // Die acht Symbole selbst gehoeren BEWUSST NICHT in diesen Pruefsatz (ADR 0113 Punkt 5): Sie
  // spannen nur die kurze Achse auf, waagerecht sind sie ein Achtel der Reihenbreite. Acht
  // nebeneinanderliegende 44-px-Flaechen brauchten 352 px zuzueglich Zwischenraeumen und
  // vertruegen sich nicht mit "alle acht in einer Zeile ohne waagerechtes Scrollen" - der
  // Treffertest meldete an den Ecken zwangslaeufig das Nachbarsymbol. Ihre Mindestgroesse
  // (WCAG 2.5.8, 24 x 24 px) belegt `no-horizontal-scroll.spec.ts`.
  await page.goto(`/projects/${projectId}/photos`)
  await expect(tiles.first()).toBeVisible()
  await tiles.nth(1).getByRole('link').first().click()
  const motifSection = page.getByTestId('motifs-section')
  await expect(motifSection).toBeVisible()

  const motifSymbol = motifSection.getByRole('list', { name: 'Motive' }).getByRole('button').first()
  await expect(motifSymbol, 'erstes Motivsymbol').toBeVisible()
  await motifSymbol.click()

  const appliesButton = motifSection.getByRole('button', { name: /^Trifft zu:/ }).first()
  await assertTappable(appliesButton, 'Trifft zu (Motivkorrektur)')
  checked.push('Trifft zu')

  // --- Die beiden Flaechen der Entwurfskachel (specs/features/0430-...) ----------------------
  // Heisser Pfad nach derselben Begruendung wie die Bewertungsleiste: Beim Durchgehen des Album-
  // Entwurfs wird hier viele Male hintereinander gedrueckt, und ein Fehlgriff schreibt einen
  // falschen Datenwert. Die zwei Flaechen liegen unmittelbar NEBENEINANDER - das ist genau die
  // Fehlerklasse "ueberlappende aufgespannte Trefferflaechen benachbarter Bedienelemente", die
  // der Treffertest mit abdeckt: er meldete dann das Nachbarelement.
  await page.goto(`/projects/${projectId}/album`)
  const albumToggle = page.getByRole('button', { name: /^(Im Album|Gestrichen): / }).first()
  await expect(albumToggle, 'erste Entwurfskachel').toBeVisible()
  await assertTappable(albumToggle, 'Albumentscheidung (Entwurfskachel)')
  checked.push('Albumentscheidung der Entwurfskachel')

  await assertTappable(
    page.getByRole('button', { name: /^Alternativen: / }).first(),
    'Alternativen (Entwurfskachel)',
  )
  checked.push('Alternativen der Entwurfskachel')

  // --- Die Bedienelemente der Endauswahl (specs/features/0431-...) ---------------------------
  // ERGAENZUNG, kein Nachziehen: Die abgeloeste Vergleichsseite stand nie in diesem Spec, weil
  // sie nur las. Die Endauswahl schreibt - und sie ist heisser Pfad nach derselben Begruendung
  // wie die Entwurfskachel: Beim Durchgehen der Unterschiede wird viele Male hintereinander
  // gedrueckt, und ein Fehlgriff aendert die Bildmenge, die als Album gilt.
  //
  // Die beiden Entscheidungsflaechen liegen unmittelbar NEBENEINANDER - genau die Fehlerklasse
  // "ueberlappende aufgespannte Trefferflaechen benachbarter Bedienelemente". Beide beziehen ihre
  // 44 px vollstaendig aus der Aufspannung: sie tragen bewusst KEINE eigene Hoehenklasse, und ein
  // `::after`-Pseudoelement ist in jsdom prinzipiell nicht messbar.
  await page.goto(`/projects/${projectId}/selection`)
  for (const label of ['Aufnehmen', 'Nicht aufnehmen']) {
    const control = page.getByRole('button', { name: new RegExp(`^${label}: `) }).first()
    await expect(control, `Entscheidungsflaeche "${label}" der Arbeitssicht`).toBeVisible()
    await assertTappable(control, `${label} (Kachel der Endauswahl)`)
    checked.push(`${label} der Endauswahl-Kachel`)
  }

  // Die beiden Umschalter der Sichten. Sie stehen mit 8 px Abstand nebeneinander - dem
  // Mindestabstand, unterhalb dessen sich zwei aufgespannte Trefferflaechen ueberlappen wuerden,
  // und in einer Ueberlappung gewinnt das obenliegende Element.
  for (const label of ['Unterschiede', 'Endauswahl']) {
    await assertTappable(
      page.getByRole('button', { name: label, exact: true }),
      `${label} (Umschalter der Endauswahl)`,
    )
    checked.push(`Umschalter ${label}`)
  }

  // --- Projekt-Navigationsgruppe in der Kopfzeile (Spec 0298, AK11c) -------------------------
  // Bei 360 px ist ausschliesslich der Menue-Ausloeser sichtbar; er ist ein `size="icon"`-Button
  // und bezieht seine 44 x 44 px vollstaendig aus der Aufspannung (`tap-target-square`) - genau
  // die Fehlerklasse, gegen die der Treffertest oben antritt.
  await page.goto(`/projects/${projectId}/photos`)
  const navTrigger = page.getByRole('button', { name: 'Projektbereiche' })
  await assertTappable(navTrigger, 'Projektbereiche (Menue-Ausloeser der Kopfzeile)')
  checked.push('Projektbereiche')

  // Die PANELZEILEN werden bewusst NICHT aufgespannt (Design-System-Regel "zeilenweise Listen
  // werden nicht aufgespannt") - dort ist die Zeile selbst die Trefferflaeche und traegt `min-h-11`.
  // Der Treffertest gilt trotzdem: 44 px sind 44 px, unabhaengig davon, woher sie kommen.
  //
  // FUENF ZEILEN SEIT specs/features/0347-navigation-nebenbereich.md: unterhalb `lg:` fuehrt das
  // Panel alle Ziele - erst die drei Hauptziele, dann die zwei Nebenziele.
  await navTrigger.click()
  const navPanel = page.getByRole('dialog')
  await expect(navPanel).toBeVisible()
  const navRows = navPanel.getByRole('link')
  await expect(navRows, 'Ziele im Panel der Projekt-Navigation').toHaveCount(5)
  await assertTappable(navRows.first(), 'Projekt (Panelzeile der Projekt-Navigation)')
  checked.push('Projekt (Panelzeile)')

  // "Statistik" ist das mit Spec 0347 neu erreichbare Bedienelement und zugleich die LETZTE Zeile
  // des Panels - die einzige, die unterhalb der Trennlinie und damit im zweiten Block liegt.
  // Bewusst zusaetzlich geprueft: die Absetzung darf die Trefferflaeche nicht beschneiden.
  await assertTappable(
    navPanel.getByRole('link', { name: 'Statistik' }),
    'Statistik (Panelzeile der Projekt-Navigation)',
  )
  checked.push('Statistik (Panelzeile)')

  // --- Schrittleiste der Pipeline (specs/features/0387-schrittleiste-fortschritt.md) -----------
  // Der Wechsel von `tap-target-square` am Marker auf `tap-target` am spaltenfuellenden
  // Bedienelement loest genau die beiden hier pruefbaren Fehlerklassen aus: waagerechter Ueberhang
  // und ueberlappende Trefferflaechen benachbarter Bedienelemente. Bei 360px ist eine Spalte nur
  // rund 72px breit - dort schlaegt ein Ueberhang sofort durch. Die Leiste ist auf jeder
  // Pipeline-Seite dauerhaft sichtbar und damit heisser Pfad nach derselben Begruendung, mit der
  // Spec 0298 den Kopfzeilen-Ausloeser aufgenommen hat.
  //
  // Geprueft werden ZWEI Bedienelemente: der ERSTE Schritt (Randspalte, dort ist ein Ueberhang am
  // wahrscheinlichsten) und ein GESPERRTER Schritt. Letzterer ist der neue `aria-disabled`-Knopf,
  // und der Treffertest ist zugleich der Nachweis, dass Zeigerereignisse ihn ueberhaupt erreichen -
  // mit `disabled` taeten sie es nicht, und der Sperrgrund waere am Telefon unerreichbar.
  //
  // Eigenes Demo-Projekt: im "bewertet"-Projekt ist jeder Schritt erreichbar, es gaebe dort gar
  // keinen gesperrten Schritt zu pruefen.
  const pipelineProjectId = await demoProjectId(page, DEMO_PROJECTS.error)
  await page.goto(`/projects/${pipelineProjectId}/pipeline/scan`)
  const stepper = page.getByRole('navigation', { name: 'Fortschritt der Pipeline' })
  await expect(stepper).toBeVisible()

  await assertTappable(
    stepper.getByRole('link', { name: /^Schritt 1 von 4: Scan/ }),
    'Schritt 1 der Schrittleiste (Randspalte)',
  )
  checked.push('Schritt 1 der Schrittleiste')

  const gesperrt = stepper.getByRole('button', { name: /, blockiert$/ })
  await expect(gesperrt, 'gesperrte Schritte der Leiste').toHaveCount(1)
  await assertTappable(gesperrt, 'gesperrter Schritt der Schrittleiste', { ariaDisabled: true })
  checked.push('gesperrter Schritt der Schrittleiste')

  // --- Die Wahlzeile der Duplikat-Vergleichsansicht (specs/features/0374-...) ----------------
  // Heisser Pfad nach derselben Begruendung wie die Entwurfskachel: Beim Durchgehen einer Serie
  // wird hier viele Male hintereinander gedrueckt. Ein Fehlgriff wiegt hier SCHWERER als dort -
  // er bestimmt mit, welche Bilddaten den Homeserver Richtung Cloud-Anbieter verlassen.
  //
  // Die beiden Flaechen liegen unmittelbar NEBENEINANDER und beziehen ihre 44 px vollstaendig aus
  // der Aufspannung: genau die Fehlerklasse "ueberlappende aufgespannte Trefferflaechen".
  const duplicatesProjectId = await demoProjectId(page, DEMO_PROJECTS.duplicates)
  await openDuplicateGroup(page, duplicatesProjectId, 'gross')
  for (const label of ['Behalten', 'Ausschuss']) {
    const control = page.getByRole('button', { name: new RegExp(`^${label}: `) }).first()
    await expect(control, `Wahlflaeche "${label}" der Vergleichsansicht`).toBeVisible()
    await assertTappable(control, `${label} (Kachel des Duplikat-Vergleichs)`)
    checked.push(`${label} der Duplikat-Kachel`)
  }

  // --- Die Gruppennavigation derselben Ansicht (specs/features/0486-...) ---------------------
  // Der heisse Pfad dieser Story: Zwischen zwei Gruppen wird beim Durchgehen einer Urlaubsserie
  // haeufiger gedrueckt als auf jede einzelne Wahlflaeche. Sie liegen ebenfalls unmittelbar
  // nebeneinander und beziehen ihre 44 px aus der Aufspannung.
  //
  // Die ERSTE Gruppe ist offen, "zurueck" dort also `disabled` und von `assertTappable` nicht
  // messbar - gemessen wird deshalb "vor". Ohne Aufnahme hier fehlte der einzige Nachweis der
  // 44-px-Zusage fuer diese beiden.
  const weiter = page.getByRole('button', { name: 'Vor zur nächsten Gruppe' })
  await expect(weiter, 'Gruppennavigation der Vergleichsansicht').toBeVisible()
  await assertTappable(weiter, 'Vor zur naechsten Gruppe')
  checked.push('Vor zur naechsten Gruppe')

  await weiter.click()
  const zurueck = page.getByRole('button', { name: 'Zurück zur vorherigen Gruppe' })
  await expect(zurueck, 'Gruppennavigation nach dem Blaettern').toBeEnabled()
  await assertTappable(zurueck, 'Zurueck zur vorherigen Gruppe')
  checked.push('Zurueck zur vorherigen Gruppe')

  // Ohne diese Zusicherung bestuende der Spec auch dann, wenn keine der Lokalisierungen oben noch
  // etwas faende und jede Schleife ueber eine leere Menge liefe.
  expect(checked.length, 'Anzahl tatsaechlich gepruefter Bedienelemente').toBe(
    EXPECTED_CONTROL_COUNT,
  )
})
