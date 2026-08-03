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
  // `--accent-fg`-Vordergrundfarbe, NICHT `--chip-fg` (das ist nur fuer die Bewertungsfarben
  // kalibriert und verfehlt gegen die kraeftige Akzentfarbe WCAG-AA) - siehe index.css.
  it('uses the accent-fg foreground token (not chip-fg) for the solid accent tone', () => {
    render(<Badge tone="accent">i</Badge>)

    expect(screen.getByText('i').className).toContain('text-accent-fg')
    expect(screen.getByText('i').className).not.toContain('text-chip-fg')
  })

  // Copilot-Review-Fund (PR "Tailwind-Fundament"): der gedaempfte Vorschlags-Hintergrund ist nur
  // eine 10%-Tinte auf `--bg`, nicht die volle Bewertungsfarbe - `--chip-fg` ist in beiden
  // Farbschemata identisch (#000000) und waere im Dunkelmodus praktisch unsichtbar auf dem dann
  // ebenfalls sehr dunklen `--bg`-Tint. `--text-h` ist stattdessen pro Modus kalibriert.
  it('uses the mode-aware text-h token (not chip-fg) for the dampened suggested tone', () => {
    render(
      <Badge tone="rejected" suggested>
        ⚙✕
      </Badge>
    )

    expect(screen.getByText('⚙✕').className).toContain('text-text-h')
    expect(screen.getByText('⚙✕').className).not.toContain('text-chip-fg')
  })
})
