import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import type { StepAction } from '../utils/stepActions'
import { StepActionBar } from './StepActionBar'

function renderBar(action: StepAction, extra: Partial<Parameters<typeof StepActionBar>[0]> = {}) {
  return render(
    <MemoryRouter>
      <StepActionBar action={action} status="Statustext" {...extra} />
    </MemoryRouter>,
  )
}

function bar(): HTMLElement {
  return screen.getByRole('group', { name: 'Nächste Aktion' })
}

describe('StepActionBar', () => {
  it('ist eine benannte Gruppe mit genau einer Live-Region für die Statuszeile', () => {
    renderBar({ kind: 'start', label: 'Fotos einlesen' })

    const live = bar().querySelectorAll('[aria-live]')
    expect(live).toHaveLength(1)
    expect(live[0]).toHaveAttribute('aria-live', 'polite')
    expect(live[0]).toHaveTextContent('Statustext')
  })

  it('haftet im Fluss am unteren Rand, deckend und mit Trennlinie', () => {
    renderBar({ kind: 'start', label: 'Fotos einlesen' })

    expect(bar()).toHaveClass('sticky', 'bottom-0', 'z-10', 'border-t', 'border-separator', 'bg-bg')
    expect(bar()).not.toHaveClass('fixed')
  })

  it.each([
    ['start', { kind: 'start', label: 'Fotos einlesen' }],
    ['retry', { kind: 'retry', label: 'Fotos einlesen' }],
    ['confirm', { kind: 'confirm', label: 'Ausschuss abschließen', openCount: null }],
  ] as const)('rendert "%s" als Schaltfläche, die die Aktion auslöst', async (_, action) => {
    const onAction = vi.fn()
    const user = userEvent.setup()
    renderBar(action, { onAction })

    const button = within(bar()).getByRole('button', { name: action.label })
    expect(button).toHaveAttribute('type', 'button')
    await user.click(button)
    expect(onAction).toHaveBeenCalledTimes(1)
  })

  it('sperrt Start, Wiederholung und Abschluss über `disabled`', () => {
    renderBar({ kind: 'retry', label: 'Klassifizierung starten' }, { disabled: true })

    expect(within(bar()).getByRole('button', { name: 'Klassifizierung starten' })).toBeDisabled()
  })

  it('zeigt "running" als gesperrte Schaltfläche in der Verlaufsform mit Ladezeichen', () => {
    renderBar({ kind: 'running', label: 'Fotos werden eingelesen…' })

    const button = within(bar()).getByRole('button', { name: 'Fotos werden eingelesen…' })
    expect(button).toBeDisabled()
    expect(within(button).getByTestId('button-spinner')).toBeInTheDocument()
  })

  it('zeigt die Abschluss-Aktion während der Anfrage mit Ladezeichen', () => {
    renderBar(
      { kind: 'confirm', label: 'Ausschuss abschließen', openCount: 0 },
      { busy: true, onAction: vi.fn() },
    )

    const button = within(bar()).getByRole('button', { name: 'Ausschuss abschließen' })
    expect(button).toBeDisabled()
    expect(within(button).getByTestId('button-spinner')).toBeInTheDocument()
  })

  it.each([
    [
      'next',
      { kind: 'next', label: 'Weiter zur Klassifizierung', to: '/projects/1/pipeline/kriterien' },
    ],
    ['open', { kind: 'open', label: 'Album-Entwurf öffnen', to: '/projects/1/album' }],
  ] as const)('rendert "%s" als echten Link ohne Schaltfläche', (_, action) => {
    renderBar(action)

    const link = within(bar()).getByRole('link', { name: action.label })
    expect(link).toHaveAttribute('href', action.to)
    expect(within(bar()).queryByRole('button')).not.toBeInTheDocument()
  })

  it('zeigt bei "nextUnavailable" einen neutralen Text ohne Aktion und ohne Alert', () => {
    renderBar({ kind: 'nextUnavailable', text: 'Kein nächster Schritt.' })

    expect(within(bar()).getByText('Kein nächster Schritt.')).toBeInTheDocument()
    expect(within(bar()).queryByRole('button')).not.toBeInTheDocument()
    expect(within(bar()).queryByRole('link')).not.toBeInTheDocument()
    expect(within(bar()).queryByRole('alert')).not.toBeInTheDocument()
  })

  it('gestaltet die Hauptaktion als einzige Akzentfläche', () => {
    renderBar({ kind: 'start', label: 'Fotos einlesen' })

    expect(within(bar()).getByRole('button', { name: 'Fotos einlesen' })).toHaveClass('bg-accent')
  })

  it('stellt den Fortschrittsblock außerhalb der Live-Region dar', () => {
    renderBar(
      { kind: 'running', label: 'Fotos werden eingelesen…' },
      { detail: <p>3 von 10 Dateien verarbeitet</p> },
    )

    const live = bar().querySelector('[aria-live]')
    expect(within(bar()).getByText('3 von 10 Dateien verarbeitet')).toBeInTheDocument()
    expect(live).not.toHaveTextContent('3 von 10')
  })
})
