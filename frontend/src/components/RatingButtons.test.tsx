import { render, screen } from '@testing-library/react'
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
