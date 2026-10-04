import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { RerunBlock } from './RerunBlock'

const RERUN = { label: 'Erneut erkennen', explanation: 'Bildet die Vorschläge neu.' }

describe('RerunBlock', () => {
  it('zeigt den Erklärsatz ohne Interaktion, ohne Aufklapper und ohne Dialog', () => {
    render(<RerunBlock rerun={RERUN} onRerun={vi.fn()} />)

    const block = screen.getByTestId('rerun-block')
    expect(within(block).getByText(RERUN.explanation)).toBeVisible()
    expect(block.querySelector('details')).toBeNull()
    expect(block.querySelector('[aria-expanded]')).toBeNull()
    expect(within(block).queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('löst den Lauf direkt aus, ohne Bestätigungsdialog', async () => {
    const onRerun = vi.fn()
    const user = userEvent.setup()
    render(<RerunBlock rerun={RERUN} onRerun={onRerun} />)

    await user.click(screen.getByRole('button', { name: RERUN.label }))

    expect(onRerun).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('ist nachrangig gestaltet (Umriss), nicht als Akzentfläche', () => {
    render(<RerunBlock rerun={RERUN} onRerun={vi.fn()} />)

    const button = screen.getByRole('button', { name: RERUN.label })
    expect(button).toHaveClass('border-border-control')
    expect(button).not.toHaveClass('bg-accent')
  })

  it('lässt sich sperren', () => {
    render(<RerunBlock rerun={RERUN} onRerun={vi.fn()} disabled />)

    expect(screen.getByRole('button', { name: RERUN.label })).toBeDisabled()
  })

  it('zeigt während des Auslösens das Ladezeichen und ist gesperrt', () => {
    render(<RerunBlock rerun={RERUN} onRerun={vi.fn()} busy />)

    const button = screen.getByRole('button', { name: RERUN.label })
    expect(button).toBeDisabled()
    expect(within(button).getByTestId('button-spinner')).toBeInTheDocument()
  })

  it('rendert den Zusatzplatz', () => {
    render(
      <RerunBlock rerun={RERUN} onRerun={vi.fn()}>
        <p>Kostenschätzung</p>
      </RerunBlock>,
    )

    expect(within(screen.getByTestId('rerun-block')).getByText('Kostenschätzung')).toBeVisible()
  })
})
