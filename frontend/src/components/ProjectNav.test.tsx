import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import { describe, expect, it } from 'vitest'

import { PROJECT_NAV_TARGETS } from '../utils/projectRoutes'
import { ProjectNav } from './ProjectNav'

/**
 * specs/features/0298-projektnavigation-in-der-kopfzeile.md, Teststrategie.
 *
 * ZWEI DARSTELLUNGEN AUS EINER ZIELTABELLE, UND IN JSDOM LIEGEN BEIDE GLEICHZEITIG IM DOM
 * (specs/architecture/0002-testkonzept.md, Sektion "Eine Zieltabelle, zwei Darstellungen"):
 * Tailwind-Klassen greifen hier nicht, `hidden`/`lg:hidden` blenden nichts aus. Daraus folgt
 * verbindlich: (a) `toBeVisible()` ist als Beleg fuer den Breakpoint WERTLOS und wird hier
 * nirgends benutzt - die Breakpoint-Zusage liegt ausschliesslich in e2e/tests/project-nav.spec.ts;
 * (b) jede Pruefung am geoeffneten Panel grenzt mit `within(panel)` ein; (c) Aussagen ueber
 * `aria-current` werden PRO DARSTELLUNG formuliert, nie dokumentweit - bei geoeffnetem Panel liegt
 * die Markierung zwangslaeufig doppelt vor, und das ist die Bauweise, kein Fehler.
 */

const EXPECTED_TARGETS = [
  { label: 'Projekt', href: '/projects/1/pipeline' },
  { label: 'Fotos', href: '/projects/1/photos' },
  { label: 'Vergleich', href: '/projects/1/compare' },
  { label: 'Einstellungen', href: '/projects/1/settings' },
]

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
    </MemoryRouter>
  )
  return { user }
}

/** Die Leiste ist der eine Navigations-Landmark; das Panel liegt per Portal ausserhalb davon. */
function bar() {
  return screen.getByRole('navigation', { name: 'Projektbereiche' })
}

async function openPanel(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Projektbereiche' }))
  return screen.getByRole('dialog')
}

describe('ProjectNav - Leiste', () => {
  it('rendert genau vier Ziele mit den Sprungzielen der Zuordnungstabelle (AK1)', () => {
    renderNav()

    const links = within(bar()).getAllByRole('link')
    expect(links).toHaveLength(EXPECTED_TARGETS.length)
    expect(links.map((link) => link.textContent)).toEqual(
      EXPECTED_TARGETS.map((target) => target.label)
    )
    links.forEach((link, index) => {
      expect(link).toHaveAttribute('href', EXPECTED_TARGETS[index].href)
      // AK1: echte <a>-Elemente, gleichrangig - kein Ziel ist Elternelement eines anderen.
      expect(link.tagName).toBe('A')
    })
  })

  it('nutzt den sichtbaren Text als zugaenglichen Namen, ohne zusaetzliches aria-label (AK11b)', () => {
    renderNav()

    for (const target of EXPECTED_TARGETS) {
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
    ['/projects/1/settings', 'Einstellungen'],
  ])('markiert auf %s genau "%s" mit aria-current="page" (AK8a)', (path, expectedLabel) => {
    renderNav(path)

    const marked = within(bar())
      .getAllByRole('link')
      .filter((link) => link.getAttribute('aria-current') === 'page')
    expect(marked).toHaveLength(1)
    expect(marked[0]).toHaveAccessibleName(expectedLabel)
  })

  it.each(['/projects/1/stats', '/projects/1/curate'])(
    'markiert auf %s kein Ziel (AK8b)',
    (path) => {
      renderNav(path)

      const links = within(bar()).getAllByRole('link')
      expect(links).toHaveLength(EXPECTED_TARGETS.length)
      expect(links.filter((link) => link.hasAttribute('aria-current'))).toEqual([])
    }
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

describe('ProjectNav - Menue auf schmalen Bildschirmen', () => {
  it('traegt am Ausloeser den zugaenglichen Namen "Projektbereiche" bei rein symbolischem Inhalt (AK11b)', () => {
    renderNav()

    const trigger = screen.getByRole('button', { name: 'Projektbereiche' })
    expect(trigger.tagName).toBe('BUTTON')
    expect(trigger.textContent).toBe('')
    expect(trigger.querySelector('[data-icon="chevron-down"]')).toHaveAttribute(
      'aria-hidden',
      'true'
    )
  })

  it('haengt den Panel-Inhalt erst beim Oeffnen ein und bietet dann dieselben vier Ziele in derselben Reihenfolge (AK6)', async () => {
    const { user } = renderNav()

    // Solange geschlossen, existiert jedes Ziel genau einmal (kein forceMount) - erst das
    // Oeffnen verdoppelt sie, und genau deshalb grenzen alle folgenden Pruefungen ein.
    expect(screen.getAllByRole('link', { name: 'Fotos' })).toHaveLength(1)

    const panel = await openPanel(user)

    const links = within(panel).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual(
      EXPECTED_TARGETS.map((target) => target.label)
    )
    links.forEach((link, index) => {
      expect(link).toHaveAttribute('href', EXPECTED_TARGETS[index].href)
    })
  })

  it('markiert im Panel dasselbe Ziel wie in der Leiste (AK8a, je Darstellung eingegrenzt)', async () => {
    const { user } = renderNav('/projects/1/compare')

    const panel = await openPanel(user)

    const marked = within(panel)
      .getAllByRole('link')
      .filter((link) => link.getAttribute('aria-current') === 'page')
    expect(marked).toHaveLength(1)
    expect(marked[0]).toHaveAccessibleName('Vergleich')
  })

  it('navigiert bei Auswahl UND schliesst das Panel (AK6)', async () => {
    const { user } = renderNav('/projects/1/photos')

    const panel = await openPanel(user)
    await user.click(within(panel).getByRole('link', { name: 'Einstellungen' }))

    // BEIDE Haelften sind noetig: nur "Panel weg" bestuende auch, wenn das onClick die
    // Navigation verschluckte.
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(screen.getByTestId('pathname')).toHaveTextContent('/projects/1/settings')
  })

  it('schliesst per Escape und gibt den Fokus an den Ausloeser zurueck (AK11a)', async () => {
    const { user } = renderNav()

    const trigger = screen.getByRole('button', { name: 'Projektbereiche' })
    await user.click(trigger)
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })

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
    const expected = PROJECT_NAV_TARGETS.map((target) => target.label)

    expect(within(bar()).getAllByRole('link').map((link) => link.textContent)).toEqual(expected)
    expect(within(panel).getAllByRole('link').map((link) => link.textContent)).toEqual(expected)
  })
})
