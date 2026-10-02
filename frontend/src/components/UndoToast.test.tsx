import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { UndoNoticeView } from './UndoToast'
import { UndoToast } from './UndoToast'

vi.mock('./PhotoImage', () => ({ PhotoImage: () => <img alt="" /> }))

const NOTICE: UndoNoticeView = {
  key: 1,
  title: 'Getauscht',
  photoId: 3,
  relativePath: 'reise/c.jpg',
}

function renderToast(props: Partial<Parameters<typeof UndoToast>[0]> = {}) {
  const onDismiss = vi.fn()
  const onUndo = vi.fn()
  const utils = render(
    <UndoToast
      notice={NOTICE}
      busy={false}
      error={null}
      restartKey={0}
      onUndo={onUndo}
      onDismiss={onDismiss}
      {...props}
    />,
  )
  return { ...utils, onDismiss, onUndo }
}

function stubHover(matches: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({ matches, media: query }))
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('UndoToast', () => {
  it('is visible at 7 999 ms and ends at 8 000 ms', () => {
    const { onDismiss } = renderToast()

    act(() => vi.advanceTimersByTime(7999))
    expect(onDismiss).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it.each([
    { fine: true, pauses: true },
    { fine: false, pauses: false },
  ])(
    'pauses under a pointer only with fine hover ($fine) and keeps the rest',
    ({ fine, pauses }) => {
      stubHover(fine)
      const { onDismiss, container } = renderToast()
      const toast = container.querySelector('[data-undo-toast]')!

      act(() => vi.advanceTimersByTime(3000))
      fireEvent.pointerEnter(toast)
      act(() => vi.advanceTimersByTime(10000))
      expect(onDismiss).toHaveBeenCalledTimes(pauses ? 0 : 1)
      if (pauses) {
        fireEvent.pointerLeave(toast)
        act(() => vi.advanceTimersByTime(4999))
        expect(onDismiss).not.toHaveBeenCalled()
        act(() => vi.advanceTimersByTime(1))
        expect(onDismiss).toHaveBeenCalledTimes(1)
      }
    },
  )

  it('pauses while the focus is inside', () => {
    const { onDismiss } = renderToast()

    act(() => vi.advanceTimersByTime(2000))
    act(() => screen.getByRole('button', { name: 'Rückgängig' }).focus())
    act(() => vi.advanceTimersByTime(20000))

    expect(onDismiss).not.toHaveBeenCalled()
  })

  it('ends with Esc while the focus is inside', () => {
    const { onDismiss } = renderToast()

    fireEvent.keyDown(screen.getByRole('button', { name: 'Rückgängig' }), { key: 'Escape' })

    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('is busy during the request and the time stands still', () => {
    const { onDismiss } = renderToast({ busy: true })

    act(() => vi.advanceTimersByTime(20000))

    expect(screen.getByRole('button', { name: 'Rückgängig' })).toBeDisabled()
    expect(onDismiss).not.toHaveBeenCalled()
  })

  it('shows the server reason as text in place of the button and restarts the 8 s', () => {
    const { onDismiss, rerender, onUndo } = renderToast()
    act(() => vi.advanceTimersByTime(6000))

    rerender(
      <UndoToast
        notice={NOTICE}
        busy={false}
        error="<b>veraendert</b>"
        restartKey={1}
        onUndo={onUndo}
        onDismiss={onDismiss}
      />,
    )

    expect(screen.queryByRole('button', { name: 'Rückgängig' })).toBeNull()
    expect(screen.getByText('<b>veraendert</b>')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(7999))
    expect(onDismiss).not.toHaveBeenCalled()
    act(() => vi.advanceTimersByTime(1))
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('keeps the same status node mounted and puts the button outside of it', () => {
    const { rerender, onDismiss, onUndo } = renderToast({ notice: null })
    const status = screen.getByRole('status')

    rerender(
      <UndoToast
        notice={NOTICE}
        busy={false}
        error={null}
        restartKey={0}
        onUndo={onUndo}
        onDismiss={onDismiss}
      />,
    )

    expect(screen.getByRole('status')).toBe(status)
    expect(status).toHaveTextContent('Getauscht')
    expect(status).toHaveTextContent('c.jpg')
    expect(status).not.toContainElement(screen.getByRole('button', { name: 'Rückgängig' }))
    expect(document.activeElement).toBe(document.body)
  })
})
