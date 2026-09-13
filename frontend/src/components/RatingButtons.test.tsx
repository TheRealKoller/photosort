import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { RatingButtons } from './RatingButtons'

function renderBar(
  props: Partial<React.ComponentProps<typeof RatingButtons>> = {},
): React.ComponentProps<typeof RatingButtons> {
  const merged: React.ComponentProps<typeof RatingButtons> = {
    currentStatus: null,
    favorite: false,
    onToggle: vi.fn(),
    onToggleFavorite: vi.fn(),
    ...props,
  }
  render(<RatingButtons {...merged} />)
  return merged
}

describe('RatingButtons', () => {
  it('renders one button per entry with an aria-label', () => {
    renderBar()

    expect(screen.getByRole('button', { name: /favorit/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /album-würdig/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /verwerfen/i })).toBeInTheDocument()
  })

  it('marks the currently active album decision as pressed', () => {
    renderBar({ currentStatus: 'album_worthy' })

    expect(screen.getByRole('button', { name: /album-würdig/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: /verwerfen/i })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  /*
   * DER KERN DER TRENNUNG (ADR 0098 Punkt 2): Favorit ist ein UNABHAENGIGER Zweizustand. Vor
   * dieser Story waren die drei Eintraege einander ausschliessend - das Markieren als Favorit
   * setzte eine bestehende Albumentscheidung still zurueck.
   */
  it('shows the favorite marker pressed at the same time as an album decision', () => {
    renderBar({ currentStatus: 'album_worthy', favorite: true })

    expect(screen.getByRole('button', { name: /favorit/i })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /album-würdig/i })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('shows the favorite marker pressed while no album decision exists', () => {
    renderBar({ currentStatus: null, favorite: true })

    expect(screen.getByRole('button', { name: /favorit/i })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /album-würdig/i })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    expect(screen.getByRole('button', { name: /verwerfen/i })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })

  it('calls onToggle with the clicked album decision and never onToggleFavorite', async () => {
    const user = userEvent.setup()
    const props = renderBar()

    await user.click(screen.getByRole('button', { name: /album-würdig/i }))

    expect(props.onToggle).toHaveBeenCalledWith('album_worthy')
    expect(props.onToggleFavorite).not.toHaveBeenCalled()
  })

  it('calls onToggleFavorite for the favorite entry and never onToggle', async () => {
    const user = userEvent.setup()
    const props = renderBar()

    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(props.onToggleFavorite).toHaveBeenCalledTimes(1)
    expect(props.onToggle).not.toHaveBeenCalled()
  })

  it('disables all buttons when disabled is set', () => {
    renderBar({ disabled: true })

    expect(screen.getByRole('button', { name: /favorit/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /album-würdig/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /verwerfen/i })).toBeDisabled()
  })

  it('shows an inline busy indicator while a rating request is in flight', () => {
    renderBar({ disabled: true, busy: true })

    expect(screen.getByRole('status')).toHaveTextContent(/speichert/i)
  })

  it('shows no busy indicator when not busy', () => {
    renderBar()

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  /*
   * specs/features/0321-dark-utility-register-ansichten.md, Etappe 3: Jeder Eintrag traegt jetzt
   * eine SICHTBARE Beschriftung und ein Tasten-Kaestchen mit seiner Ziffer.
   *
   * Die drei folgenden Faelle sichern zusammen die Zusage ab, dass der zugaengliche Name dadurch
   * NICHT laenger wird. Ohne sie hiesse er "Favorit 1", und `getByRole('button', { name, exact:
   * true })` in `e2e/tests/tap-targets.spec.ts` braeche erst in CI.
   */
  it.each(['Favorit', 'Album-würdig', 'Verwerfen'])(
    'keeps the accessible name of "%s" exact, despite the visible key box',
    (label) => {
      // Ein String als `name` ist in Testing Library eine EXAKTE Uebereinstimmung des ganzen
      // zugaenglichen Namens - "Favorit 1" wuerde hier nicht mehr gefunden.
      renderBar()

      expect(screen.getAllByRole('button', { name: label })).toHaveLength(1)
    },
  )

  it('keeps exactly three buttons in the group - the key box is not a control', () => {
    renderBar()

    expect(
      within(screen.getByRole('group', { name: 'Bewertung' })).getAllByRole('button'),
    ).toHaveLength(3)
  })

  it('keeps the key assignment 1 / 2 / 3 in the order favorite, album, reject', () => {
    // Die Ziffern stehen hier, die Belegung in `PhotoDetailPage` - beide koennen auseinander
    // laufen, deshalb prueft `PhotoDetailPage.test.tsx` sie tabellengetrieben gegeneinander.
    renderBar()

    const boxes = within(screen.getByRole('group', { name: 'Bewertung' }))
      .getAllByRole('button')
      .map((button) => button.textContent)

    expect(boxes).toEqual(['Favorit1', 'Album-würdig2', 'Verwerfen3'])
  })

  it('shows the label of every entry visibly', () => {
    renderBar()

    for (const label of ['Favorit', 'Album-würdig', 'Verwerfen']) {
      expect(screen.getByRole('button', { name: label })).toHaveTextContent(label)
    }
  })

  // Regressionstest fuer den urspruenglich benannten Bug (Funktionaler Fix 1, specs/features/
  // 0012-visual-redesign.md): "disabled- und busy-Prop bisher unabhaengig" - busy alleine (ohne
  // dass der Aufrufer zusaetzlich disabled setzt) muss trotzdem tatsaechlich deaktivieren, nicht
  // nur den Inline-Indikator zeigen.
  it('disables all buttons and ignores clicks while busy is true, even without an explicit disabled prop', async () => {
    const user = userEvent.setup()
    const props = renderBar({ busy: true })
    const button = screen.getByRole('button', { name: /favorit/i })

    expect(button).toBeDisabled()
    await user.click(button)

    expect(props.onToggleFavorite).not.toHaveBeenCalled()
  })
})
