import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CategoryOverrideMarker } from './CategoryOverrideMarker'

describe('CategoryOverrideMarker', () => {
  it('renders an accessible label describing the manual override', () => {
    render(<CategoryOverrideMarker />)

    expect(screen.getByLabelText('Kategorie manuell übersteuert')).toBeInTheDocument()
  })

  it('exposes the label via an img role, not a bare span without semantics', () => {
    // Copilot-Review-Fund (PR #201): ein aria-label auf einem rollenlosen <span> kann von
    // Assistive Technology ignoriert werden - role="img" macht das Element zu einem
    // eigenstaendigen Accessibility-Tree-Knoten mit dem aria-label als Textalternative.
    render(<CategoryOverrideMarker />)

    expect(screen.getByRole('img', { name: 'Kategorie manuell übersteuert' })).toBeInTheDocument()
  })

  it('hides the decorative pencil glyph from assistive technology', () => {
    const { container } = render(<CategoryOverrideMarker />)

    const glyph = container.querySelector('[aria-hidden="true"]')
    expect(glyph).not.toBeNull()
    expect(glyph).toHaveTextContent('✎')
  })
})
