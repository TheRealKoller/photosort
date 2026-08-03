import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Alert } from './alert'

describe('Alert', () => {
  it('renders the message with role alert', () => {
    render(<Alert>Fehler beim Laden der Fotos.</Alert>)

    expect(screen.getByRole('alert')).toHaveTextContent('Fehler beim Laden der Fotos.')
  })

  // Einheitliche Fehlerbanner-Komponente mit "Erneut versuchen" (specs/architecture/0004-design-
  // system.md, "Wiederkehrende Muster" -> "Fehlerzustand mit Retry") - zentralisiert das Muster,
  // das zuvor in jeder View einzeln als <button onClick={() => query.refetch()}> nachgebaut wurde.
  it('renders a retry button that calls onRetry when provided', async () => {
    const onRetry = vi.fn()
    const user = userEvent.setup()
    render(<Alert onRetry={onRetry}>Fehler beim Laden der Fotos.</Alert>)

    await user.click(screen.getByRole('button', { name: /erneut versuchen/i }))

    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('renders no retry button when onRetry is not provided', () => {
    render(<Alert>Fehler beim Laden der Fotos.</Alert>)

    expect(screen.queryByRole('button', { name: /erneut versuchen/i })).not.toBeInTheDocument()
  })
})
