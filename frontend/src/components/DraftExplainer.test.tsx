import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DraftExplainer, explainerStorageKey } from './DraftExplainer'

afterEach(() => {
  window.localStorage.clear()
  vi.restoreAllMocks()
})

describe('DraftExplainer', () => {
  it('starts expanded with the three statements when nothing is stored', () => {
    render(<DraftExplainer username="daniel" />)

    expect(
      screen.getByText('Hier steht der Vorschlag des Systems als dein Entwurf.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/streichen, tauschen oder ein Foto hinzufügen/)).toBeInTheDocument()
    expect(screen.getByText(/Nichts muss bestätigt werden/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ausblenden' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
  })

  it('collapses, keeps the focus on the visible toggle and stores one fixed value per user', async () => {
    const user = userEvent.setup()
    render(<DraftExplainer username="daniel" />)

    await user.click(screen.getByRole('button', { name: 'Ausblenden' }))

    const toggle = screen.getByRole('button', { name: 'So funktioniert der Entwurf' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(toggle).toHaveAttribute('aria-controls')
    await waitFor(() => expect(toggle).toHaveFocus())
    expect(window.localStorage.getItem(explainerStorageKey('daniel'))).toBe('collapsed')
    expect(window.localStorage.length).toBe(1)
  })

  it('stays collapsed for the same user and is expanded for a second user', () => {
    window.localStorage.setItem(explainerStorageKey('daniel'), 'collapsed')

    const { unmount } = render(<DraftExplainer username="daniel" />)
    expect(screen.getByRole('button', { name: 'So funktioniert der Entwurf' })).toBeInTheDocument()
    unmount()

    render(<DraftExplainer username="anna" />)
    expect(screen.getByRole('button', { name: 'Ausblenden' })).toBeInTheDocument()
  })

  it('treats a foreign stored value as expanded', () => {
    window.localStorage.setItem(explainerStorageKey('daniel'), '{"collapsed":true}')

    render(<DraftExplainer username="daniel" />)

    expect(screen.getByRole('button', { name: 'Ausblenden' })).toBeInTheDocument()
  })

  it('is expanded and fully usable when the storage throws', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const user = userEvent.setup()
    render(<DraftExplainer username="daniel" />)

    await user.click(screen.getByRole('button', { name: 'Ausblenden' }))

    expect(screen.getByRole('button', { name: 'So funktioniert der Entwurf' })).toBeInTheDocument()
  })
})
