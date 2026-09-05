import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Button } from './button'

describe('Button', () => {
  it('renders its children as the accessible label', () => {
    render(<Button>Anmelden</Button>)

    expect(screen.getByRole('button', { name: 'Anmelden' })).toBeInTheDocument()
  })

  it('calls onClick when clicked', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<Button onClick={onClick}>Speichern</Button>)

    await user.click(screen.getByRole('button', { name: 'Speichern' }))

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled when the disabled prop is set', () => {
    render(<Button disabled>Speichern</Button>)

    expect(screen.getByRole('button', { name: 'Speichern' })).toBeDisabled()
  })

  // Busy-Button-Muster (specs/architecture/0004-design-system.md): "der Button wird deaktiviert
  // ... solange die auslösende Anfrage noch unterwegs ist" - behebt die in
  // specs/features/0012-visual-redesign.md (Funktionaler Fix 1) benannte Lücke, dass `disabled`
  // bisher unabhaengig von `busy` gesetzt werden musste. Ab jetzt erzwingt `busy` allein bereits
  // den deaktivierten Zustand, unabhaengig davon, ob der Aufrufer zusaetzlich `disabled` setzt.
  it('is disabled when busy is set, even without an explicit disabled prop', () => {
    render(<Button busy>Anmelden…</Button>)

    expect(screen.getByRole('button', { name: 'Anmelden…' })).toBeDisabled()
  })

  it('does not call onClick when busy (guards against double-submit)', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(
      <Button busy onClick={onClick}>
        Anmelden…
      </Button>
    )

    await user.click(screen.getByRole('button', { name: 'Anmelden…' }))

    expect(onClick).not.toHaveBeenCalled()
  })

  it('shows a decorative, non-announced spinner while busy', () => {
    render(<Button busy>Anmelden…</Button>)

    const spinner = screen.getByTestId('button-spinner')
    expect(spinner).toHaveAttribute('aria-hidden', 'true')
  })

  it('shows no spinner when not busy', () => {
    render(<Button>Anmelden</Button>)

    expect(screen.queryByTestId('button-spinner')).not.toBeInTheDocument()
  })

  it('keeps the underlying element a native button by default (type="button")', () => {
    render(<Button>Abbrechen</Button>)

    expect(screen.getByRole('button', { name: 'Abbrechen' })).toHaveAttribute('type', 'button')
  })

  // Review-Fund (Branch feature/0012-visual-redesign-foundation): cva reiht Varianten- vor
  // Groessen-Klassen ein, tailwind-merge loest Konflikte zugunsten der zuletzt vorkommenden Klasse
  // auf - ohne compoundVariants ueberschrieb die (Default-)Groesse (h-11/min-w-11/px-4 py-2) die
  // bewusst kompakten link-Klassen, ein Link-Button sah dadurch wie ein 44px-Vollbutton statt
  // einem Inline-Link aus.
  it('keeps the link variant compact instead of the default button size', () => {
    render(<Button variant="link">Zurück zum Grid</Button>)

    const button = screen.getByRole('button', { name: 'Zurück zum Grid' })
    expect(button.className).toContain('h-auto')
    // Auf das neue Board-Mass umgezogen (specs/features/0320-dark-utility-register.md): die
    // Standardhoehe ist 32px (h-8) statt 44px (h-11). Die alte Assertion waere nach der
    // Umstellung *vacuously true* gewesen - ein Test, der gruen bleibt und nichts mehr prueft,
    // ist schlimmer als ein gebrochener.
    expect(button.className).not.toMatch(/(^|\s)h-8(\s|$)/)
    // Die Trefferflaechen-Aufspannung gilt ausdruecklich NICHT fuer den Inline-Link: eine
    // unsichtbare 44px-Flaeche um Fliesstext herum wuerde Nachbarklicks schlucken.
    expect(button.className).not.toMatch(/(^|\s)tap-target(-square)?(\s|$)/)
  })

  /*
   * Board-Grundelement "Schaltflaechen": vier Auspraegungen (primaer, sekundaer, unaufdringlich,
   * deaktiviert) x drei Zustaende (normal, ueberfahren, gedrueckt), specs/features/0320-dark-
   * utility-register.md. Ueberfahren/gedrueckt sind in jsdom nicht feststellbar - nachgewiesen
   * wird deshalb die EXISTENZ der jeweiligen Variante am Primitive, mehr geht hier ehrlich nicht.
   */
  it.each([
    ['default', 'bg-accent'],
    ['secondary', 'border-border-control'],
    ['outline', 'border-border-control'],
    ['ghost', 'bg-transparent'],
  ] as const)('renders the %s variant with its board surface', (variant, marker) => {
    render(<Button variant={variant}>Aktion</Button>)

    expect(screen.getByRole('button', { name: 'Aktion' }).className).toContain(marker)
  })

  it.each(['default', 'secondary', 'outline', 'ghost'] as const)(
    'gives the %s variant both a hover and an active state (touch has no hover)',
    (variant) => {
      render(<Button variant={variant}>Aktion</Button>)

      const className = screen.getByRole('button', { name: 'Aktion' }).className
      expect(className).toMatch(/hover:/)
      expect(className).toMatch(/active:/)
    }
  )

  it('carries the board disabled state', () => {
    render(<Button disabled>Aktion</Button>)

    const className = screen.getByRole('button', { name: 'Aktion' }).className
    expect(className).toContain('disabled:text-text-disabled')
    expect(className).toContain('disabled:bg-surface')
  })

  // Akzeptanzkriterium "sichtbar 32px bei einer Trefferflaeche von mindestens 44x44 CSS-Pixeln".
  // Whitebox-Nachweis ueber die Klassen: jsdom hat keine Layout-Engine, getBoundingClientRect()
  // liefert 0 - ein Test, der ein Mass zu messen vorgaebe, pruefte in Wahrheit einen Klassennamen.
  it('is 32px tall and spans its tap target to at least 44px', () => {
    render(<Button>Speichern</Button>)

    const className = screen.getByRole('button', { name: 'Speichern' }).className
    expect(className).toMatch(/(^|\s)h-8(\s|$)/)
    expect(className).toMatch(/(^|\s)tap-target(\s|$)/)
  })

  it('spans the icon variant on both axes, not just the short one', () => {
    render(<Button size="icon" aria-label="Schließen" />)

    expect(screen.getByRole('button', { name: 'Schließen' }).className).toMatch(
      /(^|\s)tap-target-square(\s|$)/
    )
  })

  it('renders as the child element when asChild is set, preserving its own semantics', () => {
    render(
      <Button asChild>
        <a href="/projects/new">Neues Projekt anlegen</a>
      </Button>
    )

    const link = screen.getByRole('link', { name: 'Neues Projekt anlegen' })
    expect(link).toHaveAttribute('href', '/projects/new')
  })

  // Copilot-Review-Fund (PR "Tailwind-Fundament"): `aria-disabled` allein blockiert bei `asChild`
  // keine echte Interaktion, da das native `disabled`-Attribut nicht an ein `<a href>` gebunden
  // werden kann. `pointer-events-none`/`tabIndex={-1}` sind die tatsaechliche Absicherung (siehe
  // Kommentar in button.tsx) - deren Wirkung selbst (echte Browser-Hit-Test-/Fokus-Logik) ist in
  // jsdom nicht sinnvoll pruefbar, wohl aber der resultierende DOM-Vertrag (Attribute/Klassen).
  it('marks an asChild link as non-interactive when disabled, instead of only aria-disabled', () => {
    render(
      <Button asChild disabled>
        <a href="/projects/new">Neues Projekt anlegen</a>
      </Button>
    )

    const link = screen.getByRole('link', { name: 'Neues Projekt anlegen' })
    expect(link).toHaveAttribute('aria-disabled', 'true')
    expect(link).toHaveAttribute('tabIndex', '-1')
    expect(link.className).toMatch(/(^|\s)pointer-events-none(\s|$)/)
  })
})
