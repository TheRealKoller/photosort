import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CategoryBadge } from './CategoryBadge'

describe('CategoryBadge', () => {
  it('shows the first three characters uppercased, full name as accessible label', () => {
    render(<CategoryBadge categoryKey="landscape" />)

    const badge = screen.getByLabelText('Landscape')
    expect(badge).toHaveTextContent('LAN')
  })

  it('works for an arbitrary, unknown category_key (server-driven, no fixed list)', () => {
    render(<CategoryBadge categoryKey="architecture" />)

    expect(screen.getByLabelText('Architecture')).toHaveTextContent('ARC')
  })

  it('uses the neutral badge tone, not a rating color', () => {
    const { container } = render(<CategoryBadge categoryKey="landscape" />)

    expect(container.querySelector('[data-badge-tone="neutral"]')).toBeInTheDocument()
  })
})
