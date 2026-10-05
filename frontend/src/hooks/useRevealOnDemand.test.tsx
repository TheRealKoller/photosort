import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LONG_PRESS_MS, useRevealOnDemand } from './useRevealOnDemand'

function stubHover(matches: boolean): void {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockReturnValue({
      matches,
      media: '(hover: hover) and (pointer: fine)',
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  )
}

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

function press(element: HTMLElement, milliseconds: number): void {
  vi.useFakeTimers()
  act(() => {
    element.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }))
  })
  act(() => {
    vi.advanceTimersByTime(milliseconds)
  })
  act(() => {
    element.dispatchEvent(new MouseEvent('pointerup', { bubbles: true }))
    element.dispatchEvent(new MouseEvent('pointerout', { bubbles: true, relatedTarget: null }))
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('useRevealOnDemand: Ueberfahren', () => {
  it('reveals on hover with a fine pointer and hides on leave', () => {
    stubHover(true)
    const area = renderProbe()

    fireEvent.pointerOver(area)
    expect(screen.getByText('Angaben')).toBeInTheDocument()

    fireEvent.pointerOut(area, { relatedTarget: null })
    expect(screen.queryByText('Angaben')).toBeNull()
  })

  it('does not reveal on hover without a fine pointer', () => {
    stubHover(false)
    const area = renderProbe()

    fireEvent.pointerOver(area)

    expect(screen.queryByText('Angaben')).toBeNull()
  })
})

describe('useRevealOnDemand: langer Druck', () => {
  it(`does not reveal after ${LONG_PRESS_MS - 1} ms`, () => {
    stubHover(false)
    const area = renderProbe()

    press(area, LONG_PRESS_MS - 1)

    expect(screen.queryByText('Angaben')).toBeNull()
  })

  it(`reveals after ${LONG_PRESS_MS} ms and keeps it after the finger lifts`, () => {
    stubHover(false)
    const area = renderProbe()

    press(area, LONG_PRESS_MS)

    expect(screen.getByText('Angaben')).toBeInTheDocument()
  })

  it('swallows the click that follows a long press, but not the next one', () => {
    stubHover(false)
    const onActivate = vi.fn()
    const area = renderProbe(onActivate)
    const trigger = screen.getByRole('button', { name: 'Ausloeser' })

    press(area, LONG_PRESS_MS)
    fireEvent.click(trigger)
    expect(onActivate).not.toHaveBeenCalled()

    fireEvent.click(trigger)
    expect(onActivate).toHaveBeenCalledTimes(1)
  })

  it('closes on a press elsewhere', () => {
    stubHover(false)
    const area = renderProbe()
    press(area, LONG_PRESS_MS)

    fireEvent.pointerDown(screen.getByTestId('elsewhere'))

    expect(screen.queryByText('Angaben')).toBeNull()
  })

  it('closes on scroll', () => {
    stubHover(false)
    const area = renderProbe()
    press(area, LONG_PRESS_MS)

    fireEvent.scroll(window)

    expect(screen.queryByText('Angaben')).toBeNull()
  })
})

describe('useRevealOnDemand: Fokus', () => {
  it('reveals while any control inside has focus', () => {
    stubHover(false)
    renderProbe()

    act(() => screen.getByRole('button', { name: 'Ausloeser' }).focus())
    expect(screen.getByText('Angaben')).toBeInTheDocument()

    act(() => screen.getByRole('button', { name: 'Ausloeser' }).blur())
    expect(screen.queryByText('Angaben')).toBeNull()
  })
})

describe('useRevealOnDemand: ueberlappende Ausloeser', () => {
  it('stays visible while focus remains after hover ends', () => {
    stubHover(true)
    const area = renderProbe()

    act(() => screen.getByRole('button', { name: 'Ausloeser' }).focus())
    fireEvent.pointerOver(area)
    fireEvent.pointerOut(area, { relatedTarget: null })

    expect(screen.getByText('Angaben')).toBeInTheDocument()
  })

  it('stays visible while hovering after focus leaves', () => {
    stubHover(true)
    const area = renderProbe()

    fireEvent.pointerOver(area)
    act(() => screen.getByRole('button', { name: 'Ausloeser' }).focus())
    act(() => screen.getByRole('button', { name: 'Ausloeser' }).blur())

    expect(screen.getByText('Angaben')).toBeInTheDocument()
  })
})
