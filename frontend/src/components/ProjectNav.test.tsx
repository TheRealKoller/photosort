import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import { describe, expect, it } from 'vitest'

import { PROJECT_NAV_PRIMARY_TARGETS, PROJECT_NAV_SECONDARY_TARGETS } from '../utils/projectRoutes'
import { ProjectNav } from './ProjectNav'

/**
 * specs/features/0298-projektnavigation-in-der-kopfzeile.md und
 * specs/features/0347-navigation-nebenbereich.md, Teststrategie.
 *
 * EIN AUSLOESER, ZWEI PANEL-INHALTE - UND IN JSDOM LIEGT IMMER DER GROESSERE DAVON IM DOM
 * (specs/architecture/0002-testkonzept.md, Sektion "Eine Zieltabelle, zwei Darstellungen"):
 * Tailwind-Klassen greifen hier nicht, `hidden`/`lg:hidden` blenden nichts aus. Daraus folgt
 * verbindlich: (a) `toBeVisible()` ist als Beleg fuer den Breakpoint WERTLOS und wird hier
 * nirgends benutzt - die Breakpoint-Zusage liegt ausschliesslich in e2e/tests/project-nav.spec.ts;
 * (b) jede Pruefung am geoeffneten Panel grenzt mit `within(panel)` ein; (c) Aussagen ueber
 * `aria-current` werden PRO DARSTELLUNG formuliert (Leiste / Panel / Ausloeser), nie dokumentweit
 * - auf einem Nebenziel liegt die Markierung zwangslaeufig doppelt vor (`true` am Ausloeser,
 * `page` an der Panelzeile), und das ist die Bauweise, kein Fehler.
 *
 * DAS PANEL HAT HIER IMMER FUENF ZEILEN (Edge Case 4 der Spec). Ein `toHaveLength(2)` waere in
 * jsdom schlicht falsch, und es darf ausdruecklich NICHT ueber ein `matchMedia`-Mock "repariert"
 * werden - das pruefte den Mock, nicht Tailwind.
 */

const PRIMARY_TARGETS = [
  { label: 'Projekt', href: '/projects/1/pipeline' },
  { label: 'Fotos', href: '/projects/1/photos' },
  { label: 'Vergleich', href: '/projects/1/compare' },
]

const SECONDARY_TARGETS = [
  { label: 'Einstellungen', href: '/projects/1/settings' },
  { label: 'Statistik', href: '/projects/1/stats' },
]

/** Die Reihenfolge im Panel unterhalb `lg:` - erst die drei Hauptziele, dann die zwei Nebenziele. */
const PANEL_TARGETS = [...PRIMARY_TARGETS, ...SECONDARY_TARGETS]

function LocationProbe() {
  const { pathname } = useLocation()
  return <p data-testid="pathname">{pathname}</p>
}

function renderNav(initialPath = '/projects/1/photos') {
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <ProjectNav projectId="1" />
      <LocationProbe />
    </MemoryRouter>,
  )
  return { user }
}

/** Die Leiste ist der eine Navigations-Landmark; das Panel liegt per Portal ausserhalb davon. */
function bar() {
  return screen.getByRole('navigation', { name: 'Projektbereiche' })
}

function trigger() {
  return screen.getByRole('button', { name: 'Projektbereiche' })
}

async function openPanel(user: ReturnType<typeof userEvent.setup>) {
  await user.click(trigger())
  return screen.getByRole('dialog')
}

/**
 * Der naechstgelegene gemeinsame Vorfahre - reine DOM-Struktur, keine CSS-Zusicherung. Genau so
 * wird die in jsdom pruefbare Haelfte von AK5 formuliert: dass die drei Hauptzielzeilen einen
 * eigenen Block bilden. Wie dieser Block optisch abgesetzt ist (Trennlinie, doppelter Abstand),
 * kann hier prinzipiell nicht gemessen werden und liegt in e2e/tests/project-nav.spec.ts.
 */
function nearestCommonAncestor(elements: Element[]): Element | null {
  const [first, ...rest] = elements
  let candidate: Element | null = first?.parentElement ?? null
  while (candidate !== null) {
    if (rest.every((element) => candidate!.contains(element))) {
      return candidate
    }
    candidate = candidate.parentElement
  }
  return null
}

describe('ProjectNav - Leiste', () => {
  it('rendert genau die drei Hauptziele in fester Reihenfolge (AK1)', () => {
    renderNav()

    const links = within(bar()).getAllByRole('link')
    expect(links).toHaveLength(PRIMARY_TARGETS.length)
    expect(links.map((link) => link.textContent)).toEqual(
      PRIMARY_TARGETS.map((target) => target.label),
    )
    links.forEach((link, index) => {
      expect(link).toHaveAttribute('href', PRIMARY_TARGETS[index].href)
      // AK1: echte <a>-Elemente, gleichrangig - kein Ziel ist Elternelement eines anderen.
      expect(link.tagName).toBe('A')
    })
  })

  // AK2, erste Haelfte: die beiden Nebenziele liegen NICHT in der Leiste. Ohne diesen Fall
  // bestuende der Test oben auch dann, wenn sie zusaetzlich woanders im Landmark haengen wuerden.
  it.each(SECONDARY_TARGETS.map((target) => target.label))(
    'fuehrt "%s" nicht in der Leiste (AK2)',
    (label) => {
      renderNav()

      expect(within(bar()).queryByRole('link', { name: label })).not.toBeInTheDocument()
    },
  )

  it('nutzt den sichtbaren Text als zugaenglichen Namen, ohne zusaetzliches aria-label (AK11b)', () => {
    renderNav()

    for (const target of PRIMARY_TARGETS) {
      const link = within(bar()).getByRole('link', { name: target.label })
      expect(link).not.toHaveAttribute('aria-label')
    }
  })

  it.each([
    ['/projects/1', 'Projekt'],
    ['/projects/1/pipeline', 'Projekt'],
    ['/projects/1/pipeline/kriterien', 'Projekt'],
    ['/projects/1/photos', 'Fotos'],
    ['/projects/1/photos/42', 'Fotos'],
    ['/projects/1/compare', 'Vergleich'],
  ])('markiert auf %s genau "%s" mit aria-current="page" (AK8a)', (path, expectedLabel) => {
    renderNav(path)

    const marked = within(bar())
      .getAllByRole('link')
      .filter((link) => link.getAttribute('aria-current') === 'page')
    expect(marked).toHaveLength(1)
    expect(marked[0]).toHaveAccessibleName(expectedLabel)
  })

  // Auf einem Nebenziel traegt die LEISTE keinen Marker - dort steht das aktive Ziel gar nicht.
  // Die zugehoerige Positivaussage liegt am Ausloeser und im Panel, siehe unten.
  it.each(['/projects/1/settings', '/projects/1/stats', '/projects/1/curate'])(
    'markiert auf %s kein Ziel der Leiste (AK6/AK8b)',
    (path) => {
      renderNav(path)

      const links = within(bar()).getAllByRole('link')
      expect(links).toHaveLength(PRIMARY_TARGETS.length)
      expect(links.filter((link) => link.hasAttribute('aria-current'))).toEqual([])
    },
  )

  it('zeichnet das aktive Ziel nicht allein farblich aus (AK8c)', () => {
    renderNav('/projects/1/photos')

    const active = within(bar()).getByRole('link', { name: 'Fotos' })
    // Rand UND fetter Schnitt tragen die Markierung mit - eine reine Farbzusage waere fuer
    // Farbsehschwaechen wertlos. Bewusst die einzige CSS-nahe Zusicherung dieser Datei: sie
    // belegt ein Barrierefreiheits-Kriterium, keine Gestaltung.
    expect(active.className).toContain('border-accent')
    expect(active.className).toContain('font-bold')
    // Gegenprobe: ein ruhendes Ziel traegt beides nicht.
    const resting = within(bar()).getByRole('link', { name: 'Vergleich' })
    expect(resting.className).not.toContain('border-accent')
    expect(resting.className).not.toContain('font-bold')
  })
})

describe('ProjectNav - Ausloeser des Nebenbereichs', () => {
  it('traegt den zugaenglichen Namen "Projektbereiche" bei rein symbolischem Inhalt (AK8)', () => {
    renderNav()

    expect(trigger().tagName).toBe('BUTTON')
    expect(trigger().textContent).toBe('')
    expect(trigger().querySelector('[data-icon="chevron-down"]')).toHaveAttribute(
      'aria-hidden',
      'true',
    )
  })

  /*
   * AK5, DOM-Haelfte: GENAU EIN Ausloeser im Dokument, bei jeder Breite derselbe. Die abgewaehlte
   * Zwei-Instanzen-Variante (eine `lg:hidden`, eine `hidden lg:block`) faellt hier auf - und zwar
   * als Kardinalitaet, nicht als "kein zweiter sichtbar", was in jsdom gar nicht messbar waere.
   */
  it('existiert im Dokument genau einmal (AK5)', () => {
    renderNav()

    expect(screen.getAllByRole('button', { name: 'Projektbereiche' })).toHaveLength(1)
    expect(document.querySelectorAll('button[aria-label="Projektbereiche"]')).toHaveLength(1)
  })

  it.each([
    ['/projects/1/settings', 'Einstellungen'],
    ['/projects/1/stats', 'Statistik'],
  ])(
    'markiert sich auf %s (aktives Nebenziel "%s") schon im geschlossenen Zustand (AK6)',
    (path) => {
      renderNav(path)

      expect(trigger()).toHaveAttribute('aria-current', 'true')
      /*
       * NICHT ALLEIN FARBLICH (AK6): der ruhende Ghost-Ausloeser hat GAR KEINEN Rand
       * (`ui/button.tsx`, Variante `ghost`) - der Rand selbst ist damit der nicht-farbliche
       * Traeger der Aussage, nicht nur seine Farbe.
       *
       * AN DER WORTGRENZE GEPRUEFT, NICHT PER TEILZEICHENKETTE: `toContain('border')` waere durch
       * `border-accent` vollstaendig subsumiert und koennte nie rot werden - ein auf
       * `'border-accent bg-overlay text-accent'` verkuerztes Rezept liesse den Ausloeser ohne
       * gerenderten Rand zurueck (reine Farbaussage, WCAG 1.4.1) und beide Zeilen blieben gruen.
       * Einen zweiten Waechter gibt es nicht: designSystem.contract.test.ts bindet dieses Literal
       * bewusst NICHT (ein Symbol-Button ist kein Board-Navigationselement).
       */
      expect(trigger().className).toMatch(/(^|\s)border(\s|$)/)
      expect(trigger().className).toContain('border-accent')
    },
  )

  /*
   * Edge Case 1 der Spec: /curate hat kein aktives Ziel - der Ausloeser darf daraus NICHT
   * ableiten, dass ein Nebenziel aktiv sei. Die drei Hauptzielrouten stehen daneben, weil dort
   * ein Ziel der Leiste aktiv ist und der Ausloeser trotzdem ruhen muss.
   */
  it.each([
    '/projects/1/curate',
    '/projects/1/photos',
    '/projects/1/pipeline',
    '/projects/1/compare',
  ])('bleibt auf %s ohne aria-current und ohne Aktivstil (AK6)', (path) => {
    renderNav(path)

    expect(trigger()).not.toHaveAttribute('aria-current')
    expect(trigger().className).not.toContain('border-accent')
  })

  it('oeffnet per Enter und schliesst per Escape, mit Fokusrueckgabe (AK8)', async () => {
    const { user } = renderNav()

    trigger().focus()
    expect(trigger()).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(trigger()).toHaveFocus()
  })

  it('oeffnet ebenso per Leertaste (AK8)', async () => {
    const { user } = renderNav()

    trigger().focus()
    await user.keyboard('[Space]')

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })
})

describe('ProjectNav - Panel des Nebenbereichs', () => {
  it('haengt den Panel-Inhalt erst beim Oeffnen ein und fuehrt dann fuenf Zeilen in fester Reihenfolge (AK2/AK5)', async () => {
    const { user } = renderNav()

    // Solange geschlossen, existiert jedes Hauptziel genau einmal (kein forceMount) und kein
    // Nebenziel ueberhaupt - erst das Oeffnen bringt sie herein, und genau deshalb grenzen alle
    // folgenden Pruefungen ein.
    expect(screen.getAllByRole('link', { name: 'Fotos' })).toHaveLength(1)
    expect(screen.queryByRole('link', { name: 'Statistik' })).not.toBeInTheDocument()

    const panel = await openPanel(user)

    // FUENF, nicht zwei: in jsdom greift `lg:hidden` nicht (Edge Case 4). Die Zusage "ab 1024 px
    // nur die zwei Nebenziele" liegt ausschliesslich im E2E-Spec.
    const links = within(panel).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual(
      PANEL_TARGETS.map((target) => target.label),
    )
    links.forEach((link, index) => {
      expect(link).toHaveAttribute('href', PANEL_TARGETS[index].href)
    })
  })

  /*
   * AK5, in jsdom pruefbare Haelfte: die drei Hauptzielzeilen bilden einen eigenen Block - einen
   * gemeinsamen Vorfahren, der keine der beiden Nebenzeilen enthaelt und nicht das Panel selbst
   * ist. Genau dieser Block traegt im Produkt Trennlinie, Abstand und `lg:hidden`; ohne ihn haette
   * die Absetzung keinen Traeger, und die Nebenziele koennten unterhalb `lg:` gar nicht mehr von
   * den Hauptzielen unterschieden werden.
   */
  it('fasst die drei Hauptziele im Panel zu einem eigenen Block zusammen (AK5)', async () => {
    const { user } = renderNav()

    const panel = await openPanel(user)
    const rowOf = (label: string) => within(panel).getByRole('link', { name: label })
    const primaryRows = PRIMARY_TARGETS.map((target) => rowOf(target.label))
    const secondaryRows = SECONDARY_TARGETS.map((target) => rowOf(target.label))

    const block = nearestCommonAncestor(primaryRows)
    expect(block, 'gemeinsamer Vorfahre der Hauptzielzeilen').not.toBeNull()
    expect(block, 'der Block ist nicht das Panel selbst').not.toBe(panel)
    expect(panel.contains(block!), 'der Block liegt innerhalb des Panels').toBe(true)
    for (const row of secondaryRows) {
      expect(block!.contains(row), `Nebenzeile "${row.textContent}" ausserhalb des Blocks`).toBe(
        false,
      )
    }
  })

  it.each([
    ['/projects/1/compare', 'Vergleich'],
    ['/projects/1/settings', 'Einstellungen'],
    // specs/features/0347 (AK6): /stats ist als Positivfall zurueck - beim blossen Streichen aus
    // der frueheren "kein Ziel aktiv"-Tabelle waere die Zusage lautlos verschwunden.
    ['/projects/1/stats', 'Statistik'],
  ])(
    'markiert im Panel auf %s genau "%s" (AK6, je Darstellung eingegrenzt)',
    async (path, label) => {
      const { user } = renderNav(path)

      const panel = await openPanel(user)

      const marked = within(panel)
        .getAllByRole('link')
        .filter((link) => link.getAttribute('aria-current') === 'page')
      expect(marked).toHaveLength(1)
      expect(marked[0]).toHaveAccessibleName(label)
    },
  )

  it('markiert im Panel auf /projects/1/curate kein Ziel (AK6, Edge Case 1)', async () => {
    const { user } = renderNav('/projects/1/curate')

    const panel = await openPanel(user)

    expect(
      within(panel)
        .getAllByRole('link')
        .filter((link) => link.hasAttribute('aria-current')),
    ).toEqual([])
  })

  it.each([
    ['Statistik', '/projects/1/stats'],
    ['Vergleich', '/projects/1/compare'],
  ])(
    'navigiert bei Auswahl von "%s" UND schliesst das Panel (AK7)',
    async (label, expectedPath) => {
      const { user } = renderNav('/projects/1/photos')

      const panel = await openPanel(user)
      await user.click(within(panel).getByRole('link', { name: label }))

      // BEIDE Haelften sind noetig: nur "Panel weg" bestuende auch, wenn das onClick die
      // Navigation verschluckte. Auf Fokuszusagen baut dieser Fall bewusst nicht auf - Radix gibt
      // den Fokus beim Schliessen zurueck, waehrend gleichzeitig die Route wechselt.
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(screen.getByTestId('pathname')).toHaveTextContent(expectedPath)
    },
  )

  it('bleibt auch bei geoeffnetem Panel genau EIN navigation-Landmark "Projektbereiche" (AK3b)', async () => {
    const { user } = renderNav()

    await openPanel(user)

    expect(screen.getAllByRole('navigation', { name: 'Projektbereiche' })).toHaveLength(1)
  })
})

describe('ProjectNav - eine Zieltabelle', () => {
  it('rendert Leiste und Panel aus derselben Tabelle (Beschriftung steht nur dort)', async () => {
    const { user } = renderNav()

    const panel = await openPanel(user)

    expect(
      within(bar())
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(PROJECT_NAV_PRIMARY_TARGETS.map((target) => target.label))
    expect(
      within(panel)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual([
      ...PROJECT_NAV_PRIMARY_TARGETS.map((target) => target.label),
      ...PROJECT_NAV_SECONDARY_TARGETS.map((target) => target.label),
    ])
  })
})
