import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { OperationCancelButton } from './OperationCancelButton'

/*
 * Spec 0641, UI/UX "Abbrechen je Vorgang": `secondary`, sichtbar "Abbrechen", zugänglicher Name
 * "{Vorgang} abbrechen", nativ per Tastatur bedienbar, 44-px-Aufspannung über `tap-target`, ohne
 * Rückfrage. Angefordert: gesperrt, "Wird abgebrochen…".
 */
describe('OperationCancelButton', () => {
  it('trägt das sichtbare Wort im Namen und den Vorgang davor', () => {
    render(<OperationCancelButton operation="scan" cancelRequested={false} onCancel={vi.fn()} />)

    const button = screen.getByRole('button', { name: 'Scan abbrechen' })
    expect(button).toHaveTextContent('Abbrechen')
    expect(button).toHaveAttribute('type', 'button')
    expect(button).toBeEnabled()
  })

  it('ist sekundär, nie zerstörerisch, und spannt die 44-px-Trefferfläche auf', () => {
    render(<OperationCancelButton operation="export" cancelRequested={false} onCancel={vi.fn()} />)

    const button = screen.getByRole('button', { name: 'Export abbrechen' })
    expect(button).toHaveClass('border-border-control', 'tap-target')
    expect(button).not.toHaveClass('bg-danger')
  })

  it('löst beim Klick genau einmal aus, ohne Dialog', async () => {
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(<OperationCancelButton operation="review" cancelRequested={false} onCancel={onCancel} />)

    await user.click(screen.getByRole('button', { name: 'Prüfung abbrechen' }))

    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it.each(['{Enter}', ' '])('ist per Tab erreichbar und mit "%s" auslösbar', async (key) => {
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(
      <OperationCancelButton operation="ausschuss" cancelRequested={false} onCancel={onCancel} />,
    )

    await user.tab()
    expect(screen.getByRole('button', { name: 'Ausschuss abbrechen' })).toHaveFocus()
    await user.keyboard(key)

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('ist bei angefordertem Abbruch gesperrt und nennt den Zustand als Wort', async () => {
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(<OperationCancelButton operation="classification" cancelRequested onCancel={onCancel} />)

    const button = screen.getByRole('button', { name: 'Wird abgebrochen…' })
    expect(button).toBeDisabled()
    expect(screen.getByTestId('button-spinner')).toBeInTheDocument()
    await user.click(button)
    expect(onCancel).not.toHaveBeenCalled()
  })

  it('ist schon während der laufenden Anfrage gesperrt', () => {
    render(
      <OperationCancelButton operation="scan" cancelRequested={false} pending onCancel={vi.fn()} />,
    )

    expect(screen.getByRole('button', { name: 'Wird abgebrochen…' })).toBeDisabled()
  })
})
