import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { TileAction } from './TileAction'
import type { TileActionProps } from './TileAction'

function renderAction(props: Partial<TileActionProps> = {}) {
  return render(
    <TileAction
      icon="x-circle"
      label="Streichen"
      accessibleName="Streichen: 2024/a.jpg"
      iconOnly={false}
      tileWidth={160}
      align="start"
      onClick={() => {}}
      {...props}
    />,
  )
}

function icons(element: HTMLElement): string[] {
  return [...element.querySelectorAll('[data-icon]')].map((icon) => icon.getAttribute('data-icon')!)
}

describe('TileAction: Symbol und Wort', () => {
  it('shows symbol and word, named "{action}: {path}"', () => {
    renderAction()

    const button = screen.getByRole('button', { name: 'Streichen: 2024/a.jpg' })
    expect(icons(button)).toEqual(['x-circle'])
    expect(button).toHaveTextContent('Streichen')
    expect(button.querySelector('[data-tile-action-hint]')).toBeNull()
  })

  it('keeps the same accessible name in the symbol-only form', () => {
    renderAction({ iconOnly: true })

    const button = screen.getByRole('button', { name: 'Streichen: 2024/a.jpg' })
    expect(icons(button)).toEqual(['x-circle'])
  })

  it('shows the word only as a hidden hint in the symbol-only form', () => {
    renderAction({ iconOnly: true, align: 'end' })

    const button = screen.getByRole('button', { name: 'Streichen: 2024/a.jpg' })
    const hint = button.querySelector<HTMLElement>('[data-tile-action-hint]')
    expect(hint).not.toBeNull()
    expect(hint).toHaveAttribute('aria-hidden', 'true')
    expect(hint).toHaveAttribute('data-align', 'end')
    expect(hint).toHaveTextContent('Streichen')
    expect(hint?.style.maxWidth).toBe('160px')
    // Ausserhalb des Hinweises steht kein Wort.
    expect(button.textContent).toBe('Streichen')
  })

  it('shows the hint while the button has keyboard focus', async () => {
    renderAction({ iconOnly: true })
    const button = screen.getByRole('button', { name: 'Streichen: 2024/a.jpg' })
    const hint = () => button.querySelector('[data-tile-action-hint]')

    expect(hint()).not.toHaveAttribute('data-shown')
    await userEvent.tab()
    expect(button).toHaveFocus()
    expect(hint()).toHaveAttribute('data-shown', 'true')
    await userEvent.tab()
    expect(hint()).not.toHaveAttribute('data-shown')
  })

  it('replaces the symbol by exactly one spinner while busy, keeping the word', async () => {
    const onClick = vi.fn()
    renderAction({ busy: true, onClick })

    const button = screen.getByRole('button', { name: 'Streichen: 2024/a.jpg' })
    expect(button.querySelectorAll('[data-testid="button-spinner"]')).toHaveLength(1)
    expect(icons(button)).toEqual([])
    expect(button).toHaveTextContent('Streichen')
    expect(button).toBeDisabled()

    await userEvent.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('a hostile file name stays text', () => {
    const hostile = '<img src=x onerror="window.__pwned = true">.jpg'
    const { container } = renderAction({ accessibleName: `Streichen: ${hostile}`, iconOnly: true })

    expect(screen.getByRole('button', { name: `Streichen: ${hostile}` })).toBeInTheDocument()
    expect(container.querySelector('img')).toBeNull()
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined()
  })

  it('passes disclosure attributes through', () => {
    renderAction({ 'aria-expanded': true, 'aria-controls': 'band-1' })

    const button = screen.getByRole('button', { name: 'Streichen: 2024/a.jpg' })
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(button).toHaveAttribute('aria-controls', 'band-1')
  })
})
