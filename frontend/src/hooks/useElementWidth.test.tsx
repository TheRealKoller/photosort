import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { installResizeObserver } from '../test/observers'
import { useElementWidth } from './useElementWidth'

function Probe() {
  const { ref, width } = useElementWidth<HTMLDivElement>()
  return (
    <div ref={ref} data-testid="container">
      <span data-testid="width">{width}</span>
    </div>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useElementWidth', () => {
  it('starts at zero before the first measurement', () => {
    installResizeObserver()

    render(<Probe />)

    expect(screen.getByTestId('width')).toHaveTextContent('0')
  })

  it('reports the width from the observer entry, not from the element', () => {
    // In jsdom sind `clientWidth` und `getBoundingClientRect().width` konstant 0. Ein Hook, der
    // daraus laese, waere im Komponententest nicht pruefbar - und das Raster damit auch nicht.
    const observer = installResizeObserver()
    render(<Probe />)

    observer.resizeTo(840)

    expect(screen.getByTestId('width')).toHaveTextContent('840')
    expect(screen.getByTestId('container').clientWidth).toBe(0)
  })

  it('follows a later change', () => {
    const observer = installResizeObserver()
    render(<Probe />)

    observer.resizeTo(840)
    observer.resizeTo(360)

    expect(screen.getByTestId('width')).toHaveTextContent('360')
  })

  it('stops observing when the element goes away', () => {
    const observer = installResizeObserver()
    const { unmount } = render(<Probe />)
    observer.resizeTo(840)

    unmount()

    expect(observer.observedCount()).toBe(0)
  })

  it('stays at zero and does not throw where ResizeObserver is missing', () => {
    // Kein `installResizeObserver()`: genau der Zustand eines Browsers ohne den Beobachter. Die
    // Seite bleibt benutzbar, statt beim Rendern zu brechen.
    vi.stubGlobal('ResizeObserver', undefined)

    expect(() => render(<Probe />)).not.toThrow()
    expect(screen.getByTestId('width')).toHaveTextContent('0')
  })
})
