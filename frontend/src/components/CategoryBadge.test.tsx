import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CategoryBadge } from './CategoryBadge'

describe('CategoryBadge', () => {
  it('shows the "L" abbreviation with the full name as accessible label for landscape', () => {
    render(<CategoryBadge category="landscape" />)

    const badge = screen.getByLabelText('Landschaft')
    expect(badge).toHaveTextContent('L')
  })

  it('shows the "D" abbreviation for detail', () => {
    render(<CategoryBadge category="detail" />)

    expect(screen.getByLabelText('Detailaufnahme')).toHaveTextContent('D')
  })

  it('shows the "M" abbreviation for people', () => {
    render(<CategoryBadge category="people" />)

    expect(screen.getByLabelText('Menschen')).toHaveTextContent('M')
  })

  it('uses the neutral badge tone, not a rating color', () => {
    const { container } = render(<CategoryBadge category="landscape" />)

    expect(container.querySelector('[data-badge-tone="neutral"]')).toBeInTheDocument()
  })
})
