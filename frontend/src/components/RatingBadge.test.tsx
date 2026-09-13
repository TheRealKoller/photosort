import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { RatingBadge } from './RatingBadge'

describe('RatingBadge', () => {
  it('labels a photo without any decision as "Unbewertet"', () => {
    render(<RatingBadge status={null} />)

    expect(screen.getByLabelText('Unbewertet')).toBeInTheDocument()
  })

  it('labels an album_worthy rating', () => {
    render(<RatingBadge status="album_worthy" />)

    expect(screen.getByLabelText('Album-würdig')).toBeInTheDocument()
  })

  it('labels a rejected rating', () => {
    render(<RatingBadge status="rejected" />)

    expect(screen.getByLabelText('Verworfen')).toBeInTheDocument()
  })

  /*
   * DIE TRENNUNG (ADR 0098 Punkt 2): Favorit ist kein Bewertungsstatus mehr, sondern ein
   * eigenes Kennzeichen NEBEN der Albumentscheidung. Es muss deshalb zugleich mit ihr sichtbar
   * sein - ein einzelnes Kennzeichen koennte nur eines von beidem zeigen.
   */
  it('shows the favorite marker and the album decision side by side', () => {
    render(<RatingBadge status="album_worthy" favorite />)

    expect(screen.getByLabelText('Favorit')).toBeInTheDocument()
    expect(screen.getByLabelText('Album-würdig')).toBeInTheDocument()
  })

  it('shows only the favorite marker when no album decision exists', () => {
    render(<RatingBadge status={null} favorite />)

    expect(screen.getByLabelText('Favorit')).toBeInTheDocument()
    // Kein zusaetzliches "–": das Kennzeichen selbst beweist, dass das Badge geladen ist, und
    // "Favorit –" laese sich wie ein widerspruechlicher Zustand.
    expect(screen.queryByLabelText('Unbewertet')).not.toBeInTheDocument()
  })

  it('shows no favorite marker when the marker is not set', () => {
    render(<RatingBadge status="rejected" />)

    expect(screen.queryByLabelText('Favorit')).not.toBeInTheDocument()
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

  it('never marks the favorite badge as a suggestion', () => {
    // Ein Vorschlag ist immer eine ALBUMENTSCHEIDUNG (`PhotoScore.suggested_status`); es gibt
    // keinen vorgeschlagenen Favoriten.
    const { container } = render(<RatingBadge status="rejected" favorite suggested />)

    expect(container.querySelector('[data-rating-favorite]')).not.toHaveAttribute('data-suggested')
  })

  /*
   * Akzeptanzkriterium "Die drei Bewertungszustaende bleiben auch ohne Farbwahrnehmung
   * unterscheidbar" (specs/features/0320-dark-utility-register.md). Geprueft als ACHROMATISCHE
   * Eigenschaft und als PAARWEISE Verschiedenheit - nicht als Vorhandensein einzelner Merkmale:
   * Favorit und Album-wuerdig liegen in Graustufen bei nur 1.10:1 zueinander, die Mehrfach-
   * codierung ist die einzige Stuetze dieses Kriteriums.
   *
   * Die drei Zustaende sind seit ADR 0098 nicht mehr drei Werte EINES Feldes, die Zusage gilt
   * aber unveraendert fuer die drei sichtbaren Kennzeichen.
   */
  it('keeps the three rating states pairwise distinguishable without colour perception', () => {
    const cases = [
      <RatingBadge key="f" status={null} favorite />,
      <RatingBadge key="a" status="album_worthy" />,
      <RatingBadge key="r" status="rejected" />,
    ]
    const signatures = cases.map((element) => {
      const { container, unmount } = render(element)
      const badge = container.querySelector('[data-rating-status], [data-rating-favorite]')!
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
    const { container } = render(<RatingBadge status="album_worthy" suggested />)

    const icons = [...container.querySelectorAll('[data-icon]')].map((node) =>
      node.getAttribute('data-icon'),
    )
    expect(icons).toEqual(['cog', 'book'])
  })

  /*
   * Spec 0321, Etappe 2: Das Kennzeichen traegt jetzt zusaetzlich zum Symbol sein PRODUKTWORT
   * sichtbar - das ist die Haelfte der Graustufen-Zusage, die nicht ueber die Farbflaeche traegt
   * (Favorit und Album-wuerdig liegen achromatisch bei 1.08:1 zueinander).
   */
  it.each([
    ['album_worthy', 'Album-würdig'],
    ['rejected', 'Verworfen'],
  ] as const)('shows the product word of %s visibly', (status, word) => {
    const { container } = render(<RatingBadge status={status} />)

    expect(container.querySelector('[data-rating-status]')).toHaveTextContent(word)
  })

  it('shows the product word of the favorite marker visibly', () => {
    const { container } = render(<RatingBadge status={null} favorite />)

    expect(container.querySelector('[data-rating-favorite]')).toHaveTextContent('Favorit')
  })

  it('keeps the accessible name unchanged even though the word is now visible', () => {
    // Der sichtbare Text darf den zugaenglichen Namen nicht verdoppeln oder verschieben - die
    // e2e-Selektoren und tap-targets.spec.ts haengen wortgleich daran.
    render(<RatingBadge status="album_worthy" />)

    expect(screen.getByLabelText('Album-würdig')).toHaveAccessibleName('Album-würdig')
  })

  it('shows the product word for a suggestion too, without the "Vorschlag:" prefix in the text', () => {
    // Das Praefix bleibt dem zugaenglichen Namen vorbehalten; sichtbar unterscheidet der
    // Zahnrad-Praefix plus die Vorschlags-Konstruktion (getoente Flaeche, farbiger Rand).
    const { container } = render(<RatingBadge status="album_worthy" suggested />)

    const badge = container.querySelector('[data-rating-status]')!
    expect(badge).toHaveTextContent('Album-würdig')
    expect(badge.textContent).not.toContain('Vorschlag')
    expect(badge).toHaveAccessibleName('Vorschlag: Album-würdig')
  })

  it('keeps the unrated "–" badge including its accessible label', () => {
    // Darf beim Umkleiden nicht als Aufraeumarbeit verschwinden: sonst waere "nicht bewertet"
    // von "Badge noch nicht geladen" nicht unterscheidbar.
    render(<RatingBadge status={null} />)

    expect(screen.getByLabelText('Unbewertet')).toHaveTextContent('–')
  })
})
