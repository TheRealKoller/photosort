import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CategoryOverrideMarker } from './CategoryOverrideMarker'

describe('CategoryOverrideMarker', () => {
  it('renders an accessible label describing the manual override', () => {
    render(<CategoryOverrideMarker />)

    expect(screen.getByLabelText('Kategorie manuell übersteuert')).toBeInTheDocument()
  })

  it('hides the decorative pencil glyph from assistive technology', () => {
    const { container } = render(<CategoryOverrideMarker />)

    const glyph = container.querySelector('[aria-hidden="true"]')
    expect(glyph).not.toBeNull()
    expect(glyph).toHaveTextContent('✎')
  })
})
