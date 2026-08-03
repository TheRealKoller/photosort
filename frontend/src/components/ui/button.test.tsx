import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Button } from './button'

describe('Button', () => {
  it('renders its children as the accessible label', () => {
    render(<Button>Anmelden</Button>)

    expect(screen.getByRole('button', { name: 'Anmelden' })).toBeInTheDocument()
  })

  it('calls onClick when clicked', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(<Button onClick={onClick}>Speichern</Button>)

    await user.click(screen.getByRole('button', { name: 'Speichern' }))

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled when the disabled prop is set', () => {
    render(<Button disabled>Speichern</Button>)

    expect(screen.getByRole('button', { name: 'Speichern' })).toBeDisabled()
  })

  // Busy-Button-Muster (specs/architecture/0004-design-system.md): "der Button wird deaktiviert
  // ... solange die auslösende Anfrage noch unterwegs ist" - behebt die in
  // specs/features/0012-visual-redesign.md (Funktionaler Fix 1) benannte Lücke, dass `disabled`
  // bisher unabhaengig von `busy` gesetzt werden musste. Ab jetzt erzwingt `busy` allein bereits
  // den deaktivierten Zustand, unabhaengig davon, ob der Aufrufer zusaetzlich `disabled` setzt.
  it('is disabled when busy is set, even without an explicit disabled prop', () => {
    render(<Button busy>Anmelden…</Button>)

    expect(screen.getByRole('button', { name: 'Anmelden…' })).toBeDisabled()
  })

  it('does not call onClick when busy (guards against double-submit)', async () => {
    const onClick = vi.fn()
    const user = userEvent.setup()
    render(
      <Button busy onClick={onClick}>
        Anmelden…
      </Button>
    )

    await user.click(screen.getByRole('button', { name: 'Anmelden…' }))

    expect(onClick).not.toHaveBeenCalled()
  })

  it('shows a decorative, non-announced spinner while busy', () => {
    render(<Button busy>Anmelden…</Button>)

    const spinner = screen.getByTestId('button-spinner')
    expect(spinner).toHaveAttribute('aria-hidden', 'true')
  })

  it('shows no spinner when not busy', () => {
    render(<Button>Anmelden</Button>)

    expect(screen.queryByTestId('button-spinner')).not.toBeInTheDocument()
  })

  it('keeps the underlying element a native button by default (type="button")', () => {
    render(<Button>Abbrechen</Button>)

    expect(screen.getByRole('button', { name: 'Abbrechen' })).toHaveAttribute('type', 'button')
  })

  it('renders as the child element when asChild is set, preserving its own semantics', () => {
    render(
      <Button asChild>
        <a href="/projects/new">Neues Projekt anlegen</a>
      </Button>
    )

    const link = screen.getByRole('link', { name: 'Neues Projekt anlegen' })
    expect(link).toHaveAttribute('href', '/projects/new')
  })
})
