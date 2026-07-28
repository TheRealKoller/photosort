import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { RatingBadge } from './RatingBadge'

describe('RatingBadge', () => {
  it('labels an unrated photo as "Unbewertet"', () => {
    render(<RatingBadge status={null} />)

    expect(screen.getByLabelText('Unbewertet')).toBeInTheDocument()
  })

  it('labels a favorite rating', () => {
    render(<RatingBadge status="favorite" />)

    expect(screen.getByLabelText('Favorit')).toBeInTheDocument()
  })

  it('labels an album_worthy rating', () => {
    render(<RatingBadge status="album_worthy" />)

    expect(screen.getByLabelText('Album-würdig')).toBeInTheDocument()
  })

  it('labels a rejected rating', () => {
    render(<RatingBadge status="rejected" />)

    expect(screen.getByLabelText('Verworfen')).toBeInTheDocument()
  })

  it('prefixes a suggested rating with "Vorschlag:" in the accessible label', () => {
    render(<RatingBadge status="rejected" suggested />)

    expect(screen.getByLabelText('Vorschlag: Verworfen')).toBeInTheDocument()
  })

  it('marks a suggested badge with a data attribute, distinct from a confirmed rating', () => {
    const { container } = render(<RatingBadge status="rejected" suggested />)

    expect(container.querySelector('[data-suggested="true"]')).toBeInTheDocument()
  })

  it('does not set the suggested data attribute for a confirmed rating', () => {
    const { container } = render(<RatingBadge status="rejected" />)

    expect(container.querySelector('[data-suggested]')).not.toBeInTheDocument()
  })
})
