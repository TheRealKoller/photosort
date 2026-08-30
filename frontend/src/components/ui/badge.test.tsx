import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Badge } from './badge'

// Test-engineer-Review-Fund (Branch feature/0012-visual-redesign-foundation): Badge enthaelt -
// anders als die rein praesentationellen Card/Skeleton/Progress - echte Verzweigungslogik (der
// AK-pflichtige "volle Fuellung = entschieden, Umrandung = Vorschlag"-Unterschied), die eine
// vertauschte solid/suggested-Zuordnung ohne Test unbemerkt liesse. Ueber data-badge-*-Attribute
// statt CSS-Klassen geprueft (Selektor-Stabilitaetsregel, specs/architecture/0002-testkonzept.md).
describe('Badge', () => {
  it('marks the neutral tone distinctly from colored tones', () => {
    render(<Badge tone="neutral">–</Badge>)

    expect(screen.getByText('–')).toHaveAttribute('data-badge-tone', 'neutral')
  })

  it('renders the solid (decided) variant by default for a colored tone', () => {
    render(<Badge tone="favorite">★</Badge>)

    expect(screen.getByText('★')).toHaveAttribute('data-badge-variant', 'solid')
  })

  it('renders the suggested (dampened) variant when suggested is set', () => {
    render(
      <Badge tone="rejected" suggested>
        ⚙✕
      </Badge>
    )

    expect(screen.getByText('⚙✕')).toHaveAttribute('data-badge-variant', 'suggested')
  })

  it('gives solid and suggested variants of the same tone visually distinct classes', () => {
    render(<Badge tone="rejected">✕</Badge>)
    const solid = screen.getByText('✕').className

    render(
      <Badge tone="rejected" suggested>
        ⚙✕
      </Badge>
    )
    const suggested = screen.getByText('⚙✕').className

    expect(solid).not.toBe(suggested)
  })

  // Review-Fund: `tone="accent"` braucht im vollflaechigen Zustand die dafuer kalibrierte
  // `--accent-fg`-Vordergrundfarbe, NICHT eine der Bewertungs-Vordergrundfarben (die sind gegen
  // die jeweilige Bewertungsfarbe kalibriert, nicht gegen den Akzent) - siehe index.css.
  it('uses the accent-fg foreground token for the solid accent tone', () => {
    render(<Badge tone="accent">i</Badge>)

    expect(screen.getByText('i').className).toContain('text-accent-fg')
    expect(screen.getByText('i').className).not.toContain('text-rating-')
  })

  // Copilot-Review-Fund (PR "Tailwind-Fundament"): der gedaempfte Vorschlags-Hintergrund ist nur
  // eine 10%-Tinte auf `--bg`, nicht die volle Bewertungsfarbe. Eine gegen die volle Fuellung
  // kalibrierte Vordergrundfarbe waere hier falsch (im Dunkelmodus praktisch unsichtbar auf dem
  // dann ebenfalls sehr dunklen Tint); `--text-h` ist stattdessen pro Modus kalibriert.
  it('uses the mode-aware text-h token for the dampened suggested tone', () => {
    render(
      <Badge tone="rejected" suggested>
        ⚙✕
      </Badge>
    )

    expect(screen.getByText('⚙✕').className).toContain('text-text-h')
    expect(screen.getByText('⚙✕').className).not.toContain('text-rating-rejected-fg')
  })

  /*
   * Organic-Design-Import (specs/features/0285-organic-design-import.md): die drei Bewertungstoene
   * der Vorlage tragen KEINE gemeinsame Vordergrundfarbe mit WCAG-AA. Gemessen gegen die hellen
   * Toene: schwarz haelt auf Ocker (7.88:1) und Salbei (4.99:1), faellt auf Ziegel aber auf
   * 3.53:1 durch; Creme haelt auf Ziegel (5.00:1), faellt auf Ocker aber auf 2.24:1. Deshalb hat
   * jeder Ton eine eigene, gegen genau diesen Ton gerechnete Vordergrundfarbe. Der Test haelt die
   * Kopplung fest: Fuellung und Vordergrund muessen zum selben Ton gehoeren - ein spaeteres
   * Vereinheitlichen auf einen gemeinsamen Vordergrund wuerde AA brechen und faellt hier auf.
   */
  it.each([
    ['favorite', '★'],
    ['album-worthy', '✓'],
    ['rejected', '✕'],
  ] as const)('pairs the solid %s tone with its own calibrated foreground token', (tone, symbol) => {
    render(<Badge tone={tone}>{symbol}</Badge>)

    const className = screen.getByText(symbol).className
    expect(className).toContain(`bg-rating-${tone}`)
    expect(className).toContain(`text-rating-${tone}-fg`)
  })
})
