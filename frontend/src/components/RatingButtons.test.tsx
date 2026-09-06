import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { RatingButtons } from './RatingButtons'

describe('RatingButtons', () => {
  it('renders one button per rating stage with an aria-label', () => {
    render(<RatingButtons currentStatus={null} onToggle={vi.fn()} />)

    expect(screen.getByRole('button', { name: /favorit/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /album-würdig/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /verwerfen/i })).toBeInTheDocument()
  })

  it('marks the currently active status as pressed', () => {
    render(<RatingButtons currentStatus="favorite" onToggle={vi.fn()} />)

    expect(screen.getByRole('button', { name: /favorit/i })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /verwerfen/i })).toHaveAttribute('aria-pressed', 'false')
  })

  it('calls onToggle with the clicked status', async () => {
    const onToggle = vi.fn()
    const user = userEvent.setup()

    render(<RatingButtons currentStatus={null} onToggle={onToggle} />)
    await user.click(screen.getByRole('button', { name: /favorit/i }))

    expect(onToggle).toHaveBeenCalledWith('favorite')
  })

  it('disables all buttons when disabled is set', () => {
    render(<RatingButtons currentStatus={null} onToggle={vi.fn()} disabled />)

    expect(screen.getByRole('button', { name: /favorit/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /album-würdig/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /verwerfen/i })).toBeDisabled()
  })

  it('shows an inline busy indicator while a rating request is in flight', () => {
    render(<RatingButtons currentStatus={null} onToggle={vi.fn()} disabled busy />)

    expect(screen.getByRole('status')).toHaveTextContent(/speichert/i)
  })

  it('shows no busy indicator when not busy', () => {
    render(<RatingButtons currentStatus={null} onToggle={vi.fn()} />)

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
      render(<RatingButtons currentStatus={null} onToggle={vi.fn()} />)

      expect(screen.getAllByRole('button', { name: label })).toHaveLength(1)
    }
  )

  it('keeps exactly three buttons in the group - the key box is not a control', () => {
    render(<RatingButtons currentStatus={null} onToggle={vi.fn()} />)

    expect(within(screen.getByRole('group', { name: 'Bewertung' })).getAllByRole('button')).toHaveLength(3)
  })

  it('shows the label of every entry visibly', () => {
    render(<RatingButtons currentStatus={null} onToggle={vi.fn()} />)

    for (const label of ['Favorit', 'Album-würdig', 'Verwerfen']) {
      expect(screen.getByRole('button', { name: label })).toHaveTextContent(label)
    }
  })

  // Regressionstest fuer den urspruenglich benannten Bug (Funktionaler Fix 1, specs/features/
  // 0012-visual-redesign.md): "disabled- und busy-Prop bisher unabhaengig" - busy alleine (ohne
  // dass der Aufrufer zusaetzlich disabled setzt) muss trotzdem tatsaechlich deaktivieren, nicht
  // nur den Inline-Indikator zeigen.
  it('disables all buttons and ignores clicks while busy is true, even without an explicit disabled prop', async () => {
    const onToggle = vi.fn()
    const user = userEvent.setup()

    render(<RatingButtons currentStatus={null} onToggle={onToggle} busy />)
    const button = screen.getByRole('button', { name: /favorit/i })

    expect(button).toBeDisabled()
    await user.click(button)

    expect(onToggle).not.toHaveBeenCalled()
  })
})
