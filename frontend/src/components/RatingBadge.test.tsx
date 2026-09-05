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

  /*
   * Akzeptanzkriterium "Die drei Bewertungszustaende bleiben auch ohne Farbwahrnehmung
   * unterscheidbar" (specs/features/0320-dark-utility-register.md). Geprueft als ACHROMATISCHE
   * Eigenschaft und als PAARWEISE Verschiedenheit - nicht als Vorhandensein einzelner Merkmale:
   * Favorit und Album-wuerdig liegen in Graustufen bei nur 1.10:1 zueinander, die Mehrfach-
   * codierung ist die einzige Stuetze dieses Kriteriums.
   */
  it('keeps the three rating states pairwise distinguishable without colour perception', () => {
    const signatures = (['favorite', 'album_worthy', 'rejected'] as const).map((status) => {
      const { container, unmount } = render(<RatingBadge status={status} />)
      const badge = container.querySelector('[data-rating-status]')!
      const signature = [
        badge.getAttribute('aria-label'),
        badge.querySelector('[data-icon]')!.getAttribute('data-icon'),
        badge.getAttribute('data-struck') ?? 'none',
      ].join('|')
      unmount()
      return signature
    })

    expect(new Set(signatures).size).toBe(3)
    // Jedes der drei Merkmale ist fuer sich schon paarweise verschieden bzw. eindeutig belegt.
    expect(new Set(signatures.map((s) => s.split('|')[0])).size).toBe(3)
    expect(new Set(signatures.map((s) => s.split('|')[1])).size).toBe(3)
    expect(signatures.filter((s) => s.endsWith('|true'))).toHaveLength(1)
  })

  it('marks the rejected state with the strikethrough as a DOM feature, not as a class name', () => {
    const { container } = render(<RatingBadge status="rejected" />)

    expect(container.querySelector('[data-struck="true"]')).toBeInTheDocument()
    expect(container.querySelector('[data-rating-status]')!.className).not.toContain('line-through')
  })

  it('prefixes a suggested rating with the cog symbol, keeping the rating symbol itself', () => {
    const { container } = render(<RatingBadge status="favorite" suggested />)

    const icons = [...container.querySelectorAll('[data-icon]')].map((node) =>
      node.getAttribute('data-icon')
    )
    expect(icons).toEqual(['cog', 'star'])
  })

  it('keeps the unrated "–" badge including its accessible label', () => {
    // Darf beim Umkleiden nicht als Aufraeumarbeit verschwinden: sonst waere "nicht bewertet"
    // von "Badge noch nicht geladen" nicht unterscheidbar.
    render(<RatingBadge status={null} />)

    expect(screen.getByLabelText('Unbewertet')).toHaveTextContent('–')
  })
})
