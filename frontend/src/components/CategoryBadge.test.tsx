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

  it('uses the neutral badge tone, not a rating color', () => {
    const { container } = render(
      <CategoryBadge categoryKey="landschaft" categories={CATEGORIES} />
    )

    expect(container.querySelector('[data-badge-tone="neutral"]')).toBeInTheDocument()
  })

  it('gives the catch-all the same neutral tone as any other category (no error styling)', () => {
    // Design-System-Muster "Auffangkorb-Kategorie mit erklaerend dezentem Signal": ein fehlendes
    // Erkennungsergebnis ist kein Fehler. Ueber `data-badge-tone` geprueft, nicht ueber
    // Klassennamen.
    const { container } = render(
      <CategoryBadge categoryKey="nicht_erkannt" categories={CATEGORIES} />
    )

    expect(container.querySelector('[data-badge-tone="neutral"]')).toBeInTheDocument()
    expect(screen.getByLabelText('Nicht erkannt')).toHaveTextContent('NIC')
  })
})
