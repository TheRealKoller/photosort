import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { stubFocusVisible } from '../test/focusVisible'
import { LONG_PRESS_MS, useRevealOnDemand } from './useRevealOnDemand'

type PointerKind = 'touch' | 'mouse' | 'pen'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

function Probe({ onActivate }: { onActivate: () => void }) {
  const { visible, handlers, consumeSuppressedClick } = useRevealOnDemand()
  return (
    <div
      data-testid="area"
      {...handlers}
      onClickCapture={(event) => {
        if (consumeSuppressedClick(event)) {
          event.stopPropagation()
        }
      }}
    >
      <button type="button" onClick={onActivate}>
        Ausloeser
      </button>
      {visible && <p>Angaben</p>}
    </div>
  )
}

function renderProbe(onActivate: () => void = () => {}) {
  render(
    <>
      <Probe onActivate={onActivate} />
      <p data-testid="elsewhere">Anderswo</p>
    </>,
  )
  return screen.getByTestId('area')
}

function press(element: HTMLElement, milliseconds: number, pointerType: PointerKind): void {
  vi.useFakeTimers()
  act(() => {
    fireEvent.pointerDown(element, { pointerType })
  })
  act(() => {
    vi.advanceTimersByTime(milliseconds)
  })
  act(() => {
    fireEvent.pointerUp(element, { pointerType })
    // Wie im Browser: Ein Touch-Pointer feuert beim Loslassen `pointerleave`.
    fireEvent.pointerOut(element, { pointerType, relatedTarget: null })
  })
}

function focusTrigger(): void {
  act(() => screen.getByRole('button', { name: 'Ausloeser' }).focus())
}

describe('useRevealOnDemand: Eingabeart statt Geraet (AK5)', () => {
  it('never asks matchMedia', () => {
    const matchMedia = vi.fn()
    vi.stubGlobal('matchMedia', matchMedia)
    const area = renderProbe()

    fireEvent.pointerOver(area, { pointerType: 'mouse' })
    press(area, LONG_PRESS_MS, 'touch')

    expect(matchMedia).not.toHaveBeenCalled()
  })

  it('renders without any matchMedia at all', () => {
    vi.stubGlobal('matchMedia', undefined)
    const area = renderProbe()

    fireEvent.pointerOver(area, { pointerType: 'mouse' })

    expect(screen.getByText('Angaben')).toBeInTheDocument()
  })

  it('switches between touch and mouse within one session', () => {
    const area = renderProbe()

    press(area, LONG_PRESS_MS - 1, 'touch')
    expect(screen.queryByText('Angaben')).toBeNull()

    fireEvent.pointerOver(area, { pointerType: 'mouse' })
    expect(screen.getByText('Angaben')).toBeInTheDocument()
  })
})

describe('useRevealOnDemand: Ueberfahren (AK6)', () => {
  it.each(['mouse', 'pen'] as const)('reveals on %s hover and hides on leave', (pointerType) => {
    const area = renderProbe()

    fireEvent.pointerOver(area, { pointerType })
    expect(screen.getByText('Angaben')).toBeInTheDocument()

    fireEvent.pointerOut(area, { pointerType, relatedTarget: null })
    expect(screen.queryByText('Angaben')).toBeNull()
  })

  it('does not reveal when a touch pointer enters', () => {
    const area = renderProbe()

    fireEvent.pointerOver(area, { pointerType: 'touch' })

    expect(screen.queryByText('Angaben')).toBeNull()
  })
})

describe('useRevealOnDemand: langer Druck (AK2, AK3)', () => {
  it(`does not reveal after ${LONG_PRESS_MS - 1} ms`, () => {
    const area = renderProbe()

    press(area, LONG_PRESS_MS - 1, 'touch')

    expect(screen.queryByText('Angaben')).toBeNull()
  })

  it(`reveals after ${LONG_PRESS_MS} ms and keeps it after the finger lifts`, () => {
    const area = renderProbe()

    press(area, LONG_PRESS_MS, 'touch')

    expect(screen.getByText('Angaben')).toBeInTheDocument()
  })

  it.each(['mouse', 'pen'] as const)(
    'does not start a long press for %s, and the click still activates',
    (pointerType) => {
      const onActivate = vi.fn()
      const area = renderProbe(onActivate)

      press(area, 700, pointerType)
      fireEvent.click(screen.getByRole('button', { name: 'Ausloeser' }))

      expect(screen.queryByText('Angaben')).toBeNull()
      expect(onActivate).toHaveBeenCalledTimes(1)
    },
  )

  it('does not swallow the click after a short touch press', () => {
    const onActivate = vi.fn()
    const area = renderProbe(onActivate)

    press(area, LONG_PRESS_MS - 1, 'touch')
    fireEvent.click(screen.getByRole('button', { name: 'Ausloeser' }))

    expect(onActivate).toHaveBeenCalledTimes(1)
  })

  it('swallows the click that follows a long press, but not the next one', () => {
    const onActivate = vi.fn()
    const area = renderProbe(onActivate)
    const trigger = screen.getByRole('button', { name: 'Ausloeser' })

    press(area, LONG_PRESS_MS, 'touch')
    fireEvent.click(trigger)
    expect(onActivate).not.toHaveBeenCalled()

    fireEvent.click(trigger)
    expect(onActivate).toHaveBeenCalledTimes(1)
  })

  it('closes on a press elsewhere', () => {
    const area = renderProbe()
    press(area, LONG_PRESS_MS, 'touch')

    fireEvent.pointerDown(screen.getByTestId('elsewhere'), { pointerType: 'touch' })

    expect(screen.queryByText('Angaben')).toBeNull()
  })

  it('closes on scroll', () => {
    const area = renderProbe()
    press(area, LONG_PRESS_MS, 'touch')

    fireEvent.scroll(window)

    expect(screen.queryByText('Angaben')).toBeNull()
  })
})

describe('useRevealOnDemand: Fokus (AK1, AK7, AK9)', () => {
  it('reveals while a control inside has keyboard focus (:focus-visible)', () => {
    stubFocusVisible(true)
    renderProbe()

    focusTrigger()
    expect(screen.getByText('Angaben')).toBeInTheDocument()

    act(() => screen.getByRole('button', { name: 'Ausloeser' }).blur())
    expect(screen.queryByText('Angaben')).toBeNull()
  })

  it('does not reveal on focus that is not :focus-visible (tap, focus return)', () => {
    stubFocusVisible(false)
    renderProbe()

    focusTrigger()

    expect(screen.queryByText('Angaben')).toBeNull()
  })
})

describe('useRevealOnDemand: ueberlappende Ausloeser', () => {
  it('stays visible while keyboard focus remains after hover ends', () => {
    stubFocusVisible(true)
    const area = renderProbe()

    focusTrigger()
    fireEvent.pointerOver(area, { pointerType: 'mouse' })
    fireEvent.pointerOut(area, { pointerType: 'mouse', relatedTarget: null })

    expect(screen.getByText('Angaben')).toBeInTheDocument()
  })

  it('stays visible while hovering after focus leaves', () => {
    stubFocusVisible(true)
    const area = renderProbe()

    fireEvent.pointerOver(area, { pointerType: 'mouse' })
    focusTrigger()
    act(() => screen.getByRole('button', { name: 'Ausloeser' }).blur())

    expect(screen.getByText('Angaben')).toBeInTheDocument()
  })
})
