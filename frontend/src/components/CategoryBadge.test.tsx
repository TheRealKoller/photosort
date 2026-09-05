import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CategoryOut } from '../api/types'
import { CategoryBadge } from './CategoryBadge'

const CATEGORIES: CategoryOut[] = [
  { key: 'landschaft', display_name: 'Landschaft', definition: 'd', locally_available: true },
  {
    key: 'gebaeude_bauwerk',
    display_name: 'Gebäude & Bauwerk',
    definition: 'd',
    locally_available: true,
  },
  { key: 'nicht_erkannt', display_name: 'Nicht erkannt', definition: 'd', locally_available: false },
]

describe('CategoryBadge', () => {
  it('shows three uppercase characters of the display name, full name as accessible label', () => {
    render(<CategoryBadge categoryKey="landschaft" categories={CATEGORIES} />)

    const badge = screen.getByLabelText('Landschaft')
    expect(badge).toHaveTextContent('LAN')
  })

  it('derives the abbreviation from the display name, not from the raw key', () => {
    // specs/features/0289-feste-kategorien.md: "gebaeude_bauwerk" -> "Gebäude & Bauwerk" -> "GEB".
    render(<CategoryBadge categoryKey="gebaeude_bauwerk" categories={CATEGORIES} />)

    expect(screen.getByLabelText('Gebäude & Bauwerk')).toHaveTextContent('GEB')
  })

  it('renders a legacy key from the run history via the generic fallback', () => {
    // Edge Case 12 der Spec: vor dem ersten neuen Lauf stehen in der Laufhistorie noch Altwerte -
    // kein Absturz, kein leeres Badge.
    render(<CategoryBadge categoryKey="unerkannt" categories={CATEGORIES} />)

    expect(screen.getByLabelText('Unerkannt')).toHaveTextContent('UNE')
  })

  it('stays readable while the category set is still loading', () => {
    render(<CategoryBadge categoryKey="landschaft" categories={[]} />)

    expect(screen.getByLabelText('Landschaft')).toHaveTextContent('LAN')
  })

  /*
   * Alle dreizehn `category_key` liefern ein Farbpaar (decisions/0055 Punkt 6). Ueber das feste
   * Set iteriert statt dreizehn Faelle abzuschreiben - so kann eine vierzehnte Kategorie nicht
   * ungeprueft hinzukommen. Das Set ist hier bewusst als unabhaengige Sollgroesse ausgeschrieben
   * und nicht aus der Chip-Tabelle importiert.
   */
  it.each([
    'menschen',
    'tier',
    'pflanze',
    'landschaft',
    'gebaeude_bauwerk',
    'innenraum',
    'essen_trinken',
    'fahrzeug',
    'gegenstand',
    'dokument_screenshot',
    'kunst_kreatives',
    'sport_aktivitaet',
    'nicht_erkannt',
  ])('gives %s its own chip colour pair', (categoryKey) => {
    const { container } = render(<CategoryBadge categoryKey={categoryKey} categories={CATEGORIES} />)

    const chip = container.querySelector(`[data-category-key="${categoryKey}"]`)
    expect(chip).not.toBeNull()
    expect(chip!.className).toMatch(/bg-chip-[a-z-]+/)
    expect(chip!.className).toMatch(/text-chip-[a-z-]+-fg/)
  })

  it('gives twelve of the thirteen categories a pairwise distinct colour pair', () => {
    const keys = [
      'menschen',
      'tier',
      'pflanze',
      'landschaft',
      'gebaeude_bauwerk',
      'innenraum',
      'essen_trinken',
      'fahrzeug',
      'gegenstand',
      'dokument_screenshot',
      'kunst_kreatives',
      'sport_aktivitaet',
    ]
    const pairs = keys.map((categoryKey) => {
      const { container, unmount } = render(
        <CategoryBadge categoryKey={categoryKey} categories={CATEGORIES} />
      )
      const className = container.querySelector('[data-category-key]')!.className
      unmount()
      return className
    })

    expect(new Set(pairs).size).toBe(keys.length)
  })

  it.each(['unerkannt', 'landscape', 'people', 'constructor'])(
    'falls back to the neutral pair for the legacy key %s - no crash, no empty badge',
    (categoryKey) => {
      // `constructor` ist bewusst mit dabei: ohne Object.hasOwn-Pruefung lieferte der Lookup einen
      // geerbten Prototyp-Wert statt des Neutral-Fallbacks.
      const { container } = render(
        <CategoryBadge categoryKey={categoryKey} categories={CATEGORIES} />
      )

      const chip = container.querySelector('[data-category-key]')!
      expect(chip.className).toContain('bg-chip-nicht-erkannt')
      expect(chip.textContent).not.toBe('')
    }
  )

  it('gives the catch-all the neutral pair, not an error styling', () => {
    // Design-System-Muster "Auffangkorb-Kategorie mit erklaerend dezentem Signal": ein fehlendes
    // Erkennungsergebnis ist kein Fehler.
    const { container } = render(
      <CategoryBadge categoryKey="nicht_erkannt" categories={CATEGORIES} />
    )

    const chip = container.querySelector('[data-category-key="nicht_erkannt"]')!
    expect(chip.className).toContain('bg-chip-nicht-erkannt')
    expect(chip).toHaveTextContent('NIC')
  })

  it('keeps the full display name from the server set as the accessible label', () => {
    // Die Teil-Ruecknahme von Spec 0289 gilt NUR fuer Farben, nicht fuer Namen - dieser Test
    // haelt das fest.
    render(<CategoryBadge categoryKey="gebaeude_bauwerk" categories={CATEGORIES} />)

    const chip = screen.getByLabelText('Gebäude & Bauwerk')
    expect(chip).toHaveAttribute('title', 'Gebäude & Bauwerk')
  })
})
