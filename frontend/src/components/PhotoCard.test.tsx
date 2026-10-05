import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createRef } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { LONG_PRESS_MS } from '../hooks/useRevealOnDemand'
import { PhotoCard } from './PhotoCard'
import type { PhotoCardProps } from './PhotoCard'

/*
 * Die Kuratierungskachel: Bildflaeche im eigenen Seitenverhaeltnis, Zustandszeichen in der
 * Bildecke, Angaben bei Bedarf ueber dem unteren Bildrand, Knopfzeile darunter.
 *
 * Geprueft ueber Rollen, Namen und `data-*`; Klassen nur dort, wo die Klasse selbst die Zusage
 * ist (`sr-only` der ruhenden Leiste).
 */

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

function renderCard(props: Partial<PhotoCardProps> = {}) {
  return render(
    <ul>
      <PhotoCard
        width={180}
        imageHeight={240}
        relativePath="2024/07/IMG_0042.jpg"
        image={<img alt="2024/07/IMG_0042.jpg" src="blob:x" />}
        onImageActivate={() => {}}
        imageTriggerLabel="Großansicht: 2024/07/IMG_0042.jpg"
        stateMark={<span role="img" aria-label="Vorschlag" />}
        details={<p>Angabe des Modells</p>}
        actions={
          <>
            <button type="button">Erster</button>
            <button type="button">Zweiter</button>
          </>
        }
        {...props}
      />
    </ul>,
  )
}

function strip(): HTMLElement {
  const found = document.querySelector<HTMLElement>('[data-tile-details]')
  if (found === null) {
    throw new Error('keine Leiste')
  }
  return found
}

beforeEach(() => {
  stubHover(false)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('PhotoCard: Aufbau', () => {
  it('orders image trigger, state, details, actions, error and footer', () => {
    renderCard({ error: 'Ging schief', footer: <p>Fusszeile</p> })

    const item = screen.getByRole('listitem')
    const order = [
      screen.getByRole('button', { name: /^Großansicht: / }),
      screen.getByRole('img', { name: 'Vorschlag' }),
      strip(),
      screen.getByRole('button', { name: 'Erster' }),
      screen.getByRole('button', { name: 'Zweiter' }),
      screen.getByRole('alert'),
      screen.getByText('Fusszeile'),
    ]
    const all = [...item.querySelectorAll('*')]
    const positions = order.map((element) => all.indexOf(element))
    expect(positions).toEqual([...positions].sort((a, b) => a - b))
    expect(positions.every((position) => position >= 0)).toBe(true)
  })

  it('makes the image trigger the first tab stop, then the actions in order', async () => {
    renderCard()

    await userEvent.tab()
    expect(screen.getByRole('button', { name: /^Großansicht: / })).toHaveFocus()
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'Erster' })).toHaveFocus()
    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'Zweiter' })).toHaveFocus()
  })

  it('carries the computed tile width and image height as numeric inline styles', () => {
    renderCard({ width: 158, imageHeight: 237 })

    const item = screen.getByRole('listitem')
    expect(item.style.width).toBe('158px')
    const trigger = screen.getByRole('button', { name: /^Großansicht: / })
    expect(trigger.parentElement?.style.height).toBe('237px')
    for (const element of [item, ...item.querySelectorAll<HTMLElement>('[style]')]) {
      for (const property of [...element.style]) {
        expect(element.style.getPropertyValue(property)).toMatch(/^\d+(\.\d+)?px$/)
      }
    }
  })

  it('keeps the state mark a sibling of the image trigger, never its child', () => {
    renderCard()

    const trigger = screen.getByRole('button', { name: /^Großansicht: / })
    expect(trigger.contains(screen.getByRole('img', { name: 'Vorschlag' }))).toBe(false)
  })

  it('renders the image area as neither link nor button without onImageActivate', () => {
    renderCard({ onImageActivate: undefined, actions: null })

    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('makes the image area a button that activates once and hands out its element', () => {
    const onImageActivate = vi.fn()
    const imageTriggerRef = createRef<HTMLButtonElement>()
    renderCard({ onImageActivate, imageTriggerRef })

    const trigger = screen.getByRole('button', { name: 'Großansicht: 2024/07/IMG_0042.jpg' })
    fireEvent.click(trigger)

    expect(onImageActivate).toHaveBeenCalledTimes(1)
    expect(imageTriggerRef.current).toBe(trigger)
  })

  it('does not open the large view from an action', () => {
    const onImageActivate = vi.fn()
    renderCard({ onImageActivate })

    fireEvent.click(screen.getByRole('button', { name: 'Erster' }))

    expect(onImageActivate).not.toHaveBeenCalled()
  })

  it('marks the anchored card', () => {
    renderCard({ anchored: true })

    expect(screen.getByRole('listitem')).toHaveAttribute('data-anchored', 'true')
  })
})

describe('PhotoCard: die Leiste bei Bedarf', () => {
  it('stays in the DOM at rest, screen-reader only', () => {
    renderCard()

    expect(strip()).toHaveClass('sr-only')
    expect(strip()).not.toHaveAttribute('data-visible')
    expect(within(strip()).getByText('Angabe des Modells')).toBeInTheDocument()
  })

  it.each([/^Großansicht: /, 'Erster', 'Zweiter'])('shows while %s has focus', (name) => {
    renderCard()

    act(() => screen.getByRole('button', { name }).focus())

    expect(strip()).toHaveAttribute('data-visible', 'true')
    expect(strip()).not.toHaveClass('sr-only')
  })

  it('never grows above the image', () => {
    renderCard({ imageHeight: 211 })

    expect(strip().style.maxHeight).toBe('211px')
  })

  it('shows on a long press and does not open the large view', () => {
    const onImageActivate = vi.fn()
    renderCard({ onImageActivate })
    const trigger = screen.getByRole('button', { name: /^Großansicht: / })

    vi.useFakeTimers()
    act(() => {
      trigger.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true }))
    })
    act(() => {
      vi.advanceTimersByTime(LONG_PRESS_MS)
    })
    act(() => {
      trigger.dispatchEvent(new MouseEvent('pointerup', { bubbles: true }))
    })
    fireEvent.click(trigger)

    expect(strip()).toHaveAttribute('data-visible', 'true')
    expect(onImageActivate).not.toHaveBeenCalled()
  })

  it('ends with the base name of the file, never the folder part', () => {
    renderCard()

    const name = within(strip()).getByText('IMG_0042.jpg')
    expect(strip().lastElementChild).toBe(name)
    expect(screen.queryByText(/2024\/07\/IMG/)).toBeNull()
  })

  it('strikes the file name of a set-aside card', () => {
    renderCard({ setAside: true })

    expect(within(strip()).getByText('IMG_0042.jpg')).toHaveAttribute('data-struck', 'true')
  })

  it('does not strike the file name otherwise', () => {
    renderCard()

    expect(within(strip()).getByText('IMG_0042.jpg')).not.toHaveAttribute('data-struck')
  })

  it('never renders a hostile file name as markup', () => {
    const hostile = '<img src=x onerror="window.__pwned = true">.jpg'
    renderCard({ relativePath: `2024/07/${hostile}` })

    expect(screen.getByText(hostile)).toBeInTheDocument()
    expect(document.querySelector('img[src="x"]')).toBeNull()
    expect((window as unknown as Record<string, unknown>).__pwned).toBeUndefined()
  })
})

describe('PhotoCard: eine lange Leiste bleibt erreichbar', () => {
  it('scrolls vertically within the image height instead of clipping, and takes keyboard focus when it overflows', () => {
    // jsdom misst nicht: Der Ueberlauf wird ueber die beiden Masse vorgegeben, die der Baustein liest.
    vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockReturnValue(300)
    vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(120)
    renderCard({ imageHeight: 120 })

    act(() => screen.getByRole('button', { name: 'Erster' }).focus())

    expect(strip().style.maxHeight).toBe('120px')
    expect(strip().className).toContain('overflow-y-auto')
    expect(strip().className).not.toMatch(/\boverflow-hidden\b/)
    expect(strip()).toHaveAttribute('tabindex', '0')
  })

  it('is no tab stop at rest', () => {
    renderCard()

    expect(strip()).not.toHaveAttribute('tabindex', '0')
  })
})
