import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Checkbox } from './checkbox'

// specs/features/0296-klassifizierung-ein-ausloeser-cloud-checkbox.md, UI/UX-Abschnitt: natives
// <input type="checkbox"> statt eines neuen Radix-Pakets - getestet wird die kontrollierte
// Semantik und die Bedienbarkeit ueber das umschliessende <label>.

describe('Checkbox', () => {
  it('renders the label and reflects the controlled checked state', () => {
    render(<Checkbox checked onCheckedChange={vi.fn()} label="Cloud nutzen" />)

    expect(screen.getByRole('checkbox', { name: 'Cloud nutzen' })).toBeChecked()
  })

  it('reports the new state on click', async () => {
    const onCheckedChange = vi.fn()
    const user = userEvent.setup()
    render(<Checkbox checked={false} onCheckedChange={onCheckedChange} label="Cloud nutzen" />)

    await user.click(screen.getByRole('checkbox', { name: 'Cloud nutzen' }))

    expect(onCheckedChange).toHaveBeenCalledWith(true)
  })

  it('toggles when the label text itself is clicked', async () => {
    const onCheckedChange = vi.fn()
    const user = userEvent.setup()
    render(<Checkbox checked onCheckedChange={onCheckedChange} label="Cloud nutzen" />)

    await user.click(screen.getByText('Cloud nutzen'))

    expect(onCheckedChange).toHaveBeenCalledWith(false)
  })

  it('does not report changes while disabled', async () => {
    const onCheckedChange = vi.fn()
    const user = userEvent.setup()
    render(
      <Checkbox checked={false} onCheckedChange={onCheckedChange} label="Cloud nutzen" disabled />
    )

    const checkbox = screen.getByRole('checkbox', { name: 'Cloud nutzen' })
    expect(checkbox).toBeDisabled()
    await user.click(checkbox)

    expect(onCheckedChange).not.toHaveBeenCalled()
  })

  it('keeps the controlled semantics even when a caller passes conflicting props', () => {
    // Analog switch.test.tsx: {...props} wird VOR den invarianten Attributen gespreadet.
    render(
      <Checkbox
        checked
        onCheckedChange={vi.fn()}
        label="Cloud nutzen"
        // @ts-expect-error - bewusst ein von CheckboxProps ausgeschlossenes Attribut
        type="text"
      />
    )

    expect(screen.getByRole('checkbox', { name: 'Cloud nutzen' })).toBeChecked()
  })
})
